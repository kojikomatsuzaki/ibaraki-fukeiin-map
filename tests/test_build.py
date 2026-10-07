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
from urllib.parse import parse_qs, unquote, urlsplit


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
    "style.css", "directory.css", "print.css", "print.js", "export.js",
    "post-offices/index.html", "print/index.html", "exports/stamps.csv",
    "release.json", "sitemap.xml",
}


class HeadTags(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.canonical = []
        self.google_verification = []
        self.assets = []
        self.map_links = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.assets.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.assets.append(attrs["href"])
        if tag == "a" and "map-link" in attrs.get("class", "").split():
            self.map_links.append(attrs["href"])
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
        self.assertEqual(config["version"], "2.2.0")
        self.assertEqual(config["firstReleased"], "2026-10-06")
        self.assertEqual(config["releasedAt"], "2026-10-08")
        self.assertEqual(config["contentUpdated"], "2026-10-08")
        self.assertEqual(config["author"]["name"], "Koji Komatsuzaki")
        self.assertEqual(config["author"]["reading"], "こまつざき こうじ")
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
                self.assertIn("Koji Komatsuzaki", (output / "index.html").read_text(encoding="utf-8"))
                self.assertIn("v2.2.0リリース日", (output / "index.html").read_text(encoding="utf-8"))
                self.assertEqual(read_json(output / "data.json")["records"], records)
                for page in ("index.html", "post-offices/index.html", "print/index.html"):
                    page_text = (output / page).read_text(encoding="utf-8")
                    self.assertIn("<title>" + config["title"] + "</title>", page_text)
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

    def test_page_script_and_stylesheet_links_resolve(self):
        for target in ("github", "sites"):
            output = self.work / target
            BUILD_SITE.build(self.root, output, target=target)
            for page in ("index.html", "post-offices/index.html", "print/index.html"):
                tags = HeadTags((output / page).read_text(encoding="utf-8"))
                self.assertTrue(tags.assets, page)
                for url in tags.assets:
                    with self.subTest(target=target, page=page, url=url):
                        parsed = urlsplit(url)
                        self.assertFalse(parsed.scheme or parsed.netloc)
                        asset = ((output / page).parent / unquote(parsed.path)).resolve()
                        self.assertTrue(asset.is_relative_to(output.resolve()))
                        self.assertTrue(asset.is_file(), str(asset))

    def test_map_links_round_trip_special_names_and_history(self):
        catalog_path = self.root / "source/catalog.json"
        catalog = read_json(catalog_path)
        stamp = next(record for record in catalog["stamps"] if record["historical"])
        office = next(record for record in catalog["offices"] if record["id"] == stamp["officeId"])
        name = "移行確認・大洗 & 郵便局 + #?"
        office["name"] = name
        write_json(catalog_path, catalog)
        output = self.work / "links"
        BUILD_SITE.build(self.root, output)
        records = read_json(output / "data.json")["records"]
        for page in ("post-offices/index.html", "print/index.html"):
            tags = HeadTags((output / page).read_text(encoding="utf-8"))
            self.assertEqual(len(tags.map_links), len(records))
            for record, url in zip(records, tags.map_links):
                with self.subTest(page=page, stamp=record["id"]):
                    parsed = urlsplit(url)
                    self.assertEqual(parsed.path, "../")
                    self.assertEqual(parsed.fragment, "")
                    expected = {"q": [record["name"]]}
                    if record["historical"]:
                        expected["history"] = ["true"]
                    self.assertEqual(parse_qs(parsed.query), expected)

    def test_source_javascript_changes_revision_without_changing_data(self):
        first = BUILD_SITE.build(self.root, self.work / "before")
        script = self.root / "source/web/app.js"
        script.write_text(script.read_text(encoding="utf-8") + "\n// Revision regression probe.\n",
                          encoding="utf-8")
        second = BUILD_SITE.build(self.root, self.work / "after")
        self.assertNotEqual(first["sourceRevision"], second["sourceRevision"])
        self.assertEqual(first["dataRevision"], second["dataRevision"])
        self.assertEqual(first["counts"], second["counts"])


if __name__ == "__main__":
    unittest.main()
