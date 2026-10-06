"""Acceptance checks for publishing both destinations from the version 2 master."""
import copy
import csv
import hashlib
import html
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_site", ROOT / "scripts/build_site.py")
BUILD_SITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_SITE)

EXPECTED_COUNTS = {
    "offices": 219,
    "stamps": 224,
    "activeOffices": 209,
    "activeStamps": 210,
}
GENERATED_FILES = {
    "index.html", "app.js", "data.json", "config.js", "catalog-view.js",
    "style.css", "directory.css", "print.css", "print.js",
    "post-offices/index.html", "print/index.html", "exports/stamps.csv",
    "release.json", "sitemap.xml",
}


class HeadTags(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.canonical = []
        self.google_verification = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical.append(attrs.get("href"))
        if tag == "meta" and attrs.get("name") == "google-site-verification":
            self.google_verification.append(attrs.get("content"))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_hashes(directory):
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*")) if path.is_file()
    }


class BuildAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="stamp-build-test-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.root = self.work / "master"
        self.root.mkdir()
        for name in ("source", "assets", "vendor"):
            shutil.copytree(ROOT / name, self.root / name)

    def test_both_targets_share_data_and_preserve_existing_exceptions(self):
        config, catalog, records = BUILD_SITE.load_catalog(self.root)
        self.assertEqual(catalog["schemaVersion"], 2)
        self.assertEqual(len(catalog["offices"]), 219)
        self.assertEqual(len(records), 224)
        self.assertEqual(len({record["id"] for record in records}), 224)
        self.assertTrue(all(record["officeId"] for record in records))
        self.assertEqual(sum(record["historical"] for record in records), 14)
        self.assertEqual(sum(record["abolished"] for record in records), 12)
        self.assertEqual(sum(record["coordinatesApproximate"] for record in records), 2)
        self.assertEqual(sum(bool(record["dateWarning"]) for record in records), 5)
        by_id = {record["id"]: record for record in records}
        self.assertEqual(by_id["4185"]["officeStatus"], "closed")
        self.assertFalse(by_id["4185"]["abolished"])
        self.assertEqual(by_id["4088"]["officeStatus"], "temporarily-closed")
        self.assertFalse(by_id["4088"]["abolished"])

        releases = {}
        for target in ("github", "sites"):
            with self.subTest(target=target):
                output = self.work / target
                release = BUILD_SITE.build(self.root, output, target=target)
                releases[target] = release
                self.assertTrue(GENERATED_FILES <= set(file_hashes(output)))
                self.assertEqual(release, read_json(output / "release.json"))
                self.assertEqual(release["target"], target)
                self.assertEqual(release["version"], config["version"])
                self.assertEqual(release["counts"], EXPECTED_COUNTS)
                self.assertTrue(release["sourceRevision"])
                self.assertTrue(release["dataRevision"])
                self.assertEqual(read_json(output / "data.json")["records"], records)
                tags = HeadTags((output / "index.html").read_text(encoding="utf-8"))
                self.assertEqual(tags.canonical, [config["canonicalUrl"]])
                if target == "github":
                    self.assertEqual(tags.google_verification,
                                     [config["targets"]["github"]["googleVerification"]])

        for filename in ("data.json", "exports/stamps.csv"):
            self.assertEqual((self.work / "github" / filename).read_bytes(),
                             (self.work / "sites" / filename).read_bytes())
        for key in ("version", "sourceRevision", "dataRevision", "counts"):
            self.assertEqual(releases["github"][key], releases["sites"][key])

    def test_master_edits_reach_map_directory_csv_and_print(self):
        catalog_path = self.root / "source/catalog.json"
        catalog = read_json(catalog_path)
        stamp = next(record for record in catalog["stamps"] if record["id"] == "4112")
        office = next(record for record in catalog["offices"] if record["id"] == stamp["officeId"])
        name = "移行確認・大洗 & 郵便局"
        address = "茨城県大洗町移行確認1-2, 3階"
        office["name"] = name
        stamp.update(address=address, currentAddress=address, lat=36.3344556, lng=140.5566778)
        write_json(catalog_path, catalog)

        config_path = self.root / "source/site.json"
        config = read_json(config_path)
        config["canonicalUrl"] = "https://example.invalid/stamp-test/"
        config["targets"]["github"]["googleVerification"] = "test-verification-token"
        write_json(config_path, config)

        output = self.work / "changed"
        BUILD_SITE.build(self.root, output)
        record = next(record for record in read_json(output / "data.json")["records"]
                      if record["id"] == stamp["id"])
        self.assertEqual(record["name"], name)
        for key in ("address", "currentAddress", "lat", "lng"):
            self.assertEqual(record[key], stamp[key])
        for page in ("post-offices/index.html", "print/index.html"):
            with self.subTest(page=page):
                content = html.unescape((output / page).read_text(encoding="utf-8"))
                self.assertIn(name, content)
                self.assertIn(address, content)
        with (output / "exports/stamps.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        changed_rows = [row for row in rows[1:] if stamp["id"] in row]
        self.assertEqual(len(changed_rows), 1)
        for value in (name, address, str(stamp["lat"]), str(stamp["lng"])):
            self.assertIn(value, changed_rows[0])
        tags = HeadTags((output / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(tags.canonical, [config["canonicalUrl"]])
        self.assertEqual(tags.google_verification, ["test-verification-token"])
        self.assertIn(config["canonicalUrl"], (output / "sitemap.xml").read_text(encoding="utf-8"))

    def test_invalid_master_inputs_fail_before_publication(self):
        path = self.root / "source/catalog.json"
        original = read_json(path)
        for case in ("duplicate-stamp-id", "unknown-office", "missing-image"):
            with self.subTest(case=case):
                catalog = copy.deepcopy(original)
                if case == "duplicate-stamp-id":
                    catalog["stamps"].append(copy.deepcopy(catalog["stamps"][0]))
                elif case == "unknown-office":
                    catalog["stamps"][0]["officeId"] = "office-does-not-exist"
                else:
                    catalog["stamps"][0]["image"] = "assets/stamps/does-not-exist.png"
                write_json(path, catalog)
                with self.assertRaises(ValueError):
                    BUILD_SITE.build(self.root, self.work / case)

    def test_repeated_builds_are_identical(self):
        first = self.work / "first"
        second = self.work / "second"
        first_release = BUILD_SITE.build(self.root, first)
        second_release = BUILD_SITE.build(self.root, second)
        self.assertEqual(first_release, second_release)
        self.assertEqual(file_hashes(first), file_hashes(second))


if __name__ == "__main__":
    unittest.main()
