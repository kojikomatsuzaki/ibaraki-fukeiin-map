#!/usr/bin/env python3
"""Build every public view from the version 2 catalogue.

The files in source/ are the only editorial input. This module deliberately
uses the standard library so the GitHub Pages and Sites builds are reproducible
without installing a package.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape
from urllib.parse import urlencode, urljoin


OFFICIAL_DETAIL_RE = re.compile(r"^https://www\.post\.japanpost\.jp/", re.I)
ALLOWED_OFFICE_STATUS = {"listed-in-official-directory", "closed", "temporarily-closed"}
CSV_FIELDS = [
    ("stampId", "風景印ID"),
    ("officeId", "郵便局ID"),
    ("name", "郵便局名"),
    ("city", "市町村"),
    ("region", "地域"),
    ("displayAddress", "表示住所"),
    ("address", "原住所"),
    ("currentAddress", "現在住所"),
    ("postalCode", "郵便番号"),
    ("status", "状態"),
    ("abolished", "風景印廃止"),
    ("historical", "履歴表示"),
    ("officeStatus", "郵便局状態"),
    ("officeStatusDate", "郵便局状態日"),
    ("endDate", "風景印終了日"),
    ("lat", "緯度"),
    ("lng", "経度"),
    ("coordinateBasis", "位置の基準"),
    ("coordinatePrecision", "位置精度"),
    ("coordinatesApproximate", "概算位置"),
    ("coordinateNote", "位置注記"),
    ("coordinateSourceUrl", "位置の出典URL"),
    ("description", "図案説明"),
    ("dateWarning", "日付注記"),
    ("detailUrl", "日本郵便紹介URL"),
    ("imageUrl", "画像URL"),
    ("verifiedAt", "確認日"),
]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing source file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()[:16]


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return value


def _validate_site_config(config: dict[str, Any]) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(config.get("version", ""))):
        raise ValueError("site version must use major.minor.patch")
    for key in ("title", "prefecture", "pageTitle", "description", "canonicalUrl", "repositoryUrl", "firstReleased", "releasedAt", "contentUpdated"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise ValueError(f"site config requires non-empty {key}")
    author = config.get("author")
    if not isinstance(author, dict) or any(not isinstance(author.get(key), str) or not author[key] for key in ("name", "reading", "contactLabel", "contactUrl")):
        raise ValueError("site config requires author name, reading, contactLabel, and contactUrl")
    if not author["contactUrl"].startswith("https://"):
        raise ValueError("author contactUrl must be an https URL")
    if not config["canonicalUrl"].startswith("https://") or not config["canonicalUrl"].endswith("/"):
        raise ValueError("canonicalUrl must be an https URL ending in /")
    targets = config.get("targets")
    if not isinstance(targets, dict) or not isinstance(targets.get("github"), dict) or not isinstance(targets.get("sites"), dict):
        raise ValueError("site config requires github and sites targets")
    for name, target in targets.items():
        if not isinstance(target.get("url"), str) or not target["url"].startswith("https://"):
            raise ValueError(f"target {name} requires an https url")
    if not isinstance(config.get("regions"), list) or len(config["regions"]) != 5:
        raise ValueError("site config must contain the five Ibaraki regions")
    region_names = [item.get("name") for item in config["regions"]]
    if len(set(region_names)) != len(region_names) or any(not isinstance(name, str) for name in region_names):
        raise ValueError("region names must be unique strings")
    bounds = config.get("bounds")
    if not isinstance(bounds, list) or len(bounds) != 2 or any(not isinstance(pair, list) or len(pair) != 2 for pair in bounds):
        raise ValueError("bounds must contain southwest and northeast pairs")
    for index, pair in enumerate(bounds):
        _finite_number(pair[0], f"bounds[{index}][0]")
        _finite_number(pair[1], f"bounds[{index}][1]")


def _display_status(stamp: dict[str, Any]) -> str:
    status = stamp.get("officeStatus")
    if status == "temporarily-closed":
        return "一時閉鎖" if not stamp.get("officeStatusDate") else f"{stamp['officeStatusDate']} 一時閉鎖"
    if stamp.get("abolished"):
        return "風景印廃止" if not stamp.get("endDate") else f"{stamp['endDate']} 風景印廃止"
    if status == "closed":
        return "郵便局閉鎖" if not stamp.get("officeStatusDate") else f"{stamp['officeStatusDate']} 郵便局閉鎖"
    return ""


def _validate_catalog(catalog: dict[str, Any], root: Path, config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if catalog.get("schemaVersion") != 2:
        raise ValueError("source/catalog.json schemaVersion must be 2")
    for key in ("verifiedAt", "sourceUrl"):
        if not isinstance(catalog.get(key), str) or not catalog[key]:
            raise ValueError(f"catalog requires non-empty {key}")
    offices = catalog.get("offices")
    stamps = catalog.get("stamps")
    if not isinstance(offices, list) or not isinstance(stamps, list):
        raise ValueError("catalog requires offices and stamps arrays")
    region_names = {item["name"] for item in config["regions"]}
    office_ids: set[str] = set()
    office_by_id: dict[str, dict[str, Any]] = {}
    for index, office in enumerate(offices):
        if not isinstance(office, dict):
            raise ValueError(f"offices[{index}] must be an object")
        for key in ("id", "name", "city", "region"):
            if not isinstance(office.get(key), str) or not office[key]:
                raise ValueError(f"offices[{index}] requires {key}")
        if office["id"] in office_ids:
            raise ValueError(f"duplicate office id: {office['id']}")
        if office["region"] not in region_names:
            raise ValueError(f"unknown office region: {office['region']}")
        office_ids.add(office["id"])
        office_by_id[office["id"]] = office

    stamp_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    referenced_offices: set[str] = set()
    for index, stamp in enumerate(stamps):
        if not isinstance(stamp, dict):
            raise ValueError(f"stamps[{index}] must be an object")
        stamp_id = stamp.get("id")
        if not isinstance(stamp_id, str) or not stamp_id:
            raise ValueError(f"stamps[{index}] requires a string id")
        if stamp_id in stamp_ids:
            raise ValueError(f"duplicate stamp id: {stamp_id}")
        stamp_ids.add(stamp_id)
        office_id = stamp.get("officeId")
        if office_id not in office_by_id:
            raise ValueError(f"stamp {stamp_id} references unknown office: {office_id}")
        referenced_offices.add(office_id)
        image = stamp.get("image")
        if not isinstance(image, str) or not image.startswith("assets/"):
            raise ValueError(f"stamp {stamp_id} image must be under assets/")
        if not (root / image).resolve().is_relative_to((root / "assets").resolve()):
            raise ValueError(f"stamp {stamp_id} image escapes assets/")
        if not (root / image).is_file():
            raise ValueError(f"stamp {stamp_id} image does not exist: {image}")
        detail_url = stamp.get("detailUrl")
        if not isinstance(detail_url, str) or not OFFICIAL_DETAIL_RE.match(detail_url):
            raise ValueError(f"stamp {stamp_id} detailUrl must be an official Japan Post URL")
        for key in ("abolished", "historical", "coordinatesApproximate"):
            if not isinstance(stamp.get(key), bool):
                raise ValueError(f"stamp {stamp_id} {key} must be boolean")
        office_status = stamp.get("officeStatus")
        if office_status not in ALLOWED_OFFICE_STATUS:
            raise ValueError(f"stamp {stamp_id} has unknown officeStatus: {office_status}")
        if (office_status in {"closed", "temporarily-closed"} or stamp["abolished"]) and not stamp["historical"]:
            raise ValueError(f"stamp {stamp_id} with an ended/closed status must be historical")
        lat = _finite_number(stamp.get("lat"), f"stamp {stamp_id}.lat")
        lng = _finite_number(stamp.get("lng"), f"stamp {stamp_id}.lng")
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError(f"stamp {stamp_id} coordinates are out of range")
        if any(key in stamp for key in ("name", "city", "region")):
            raise ValueError(f"stamp {stamp_id}: office name, city and region belong in offices")
        record = dict(stamp)
        office = office_by_id[office_id]
        record.update(name=office["name"], city=office["city"], region=office["region"])
        record["stampId"] = stamp_id
        record["imageUrl"] = urljoin(config["canonicalUrl"], stamp["image"])
        record["verifiedAt"] = catalog["verifiedAt"]
        record["displayStatus"] = _display_status(stamp)
        record["status"] = record["displayStatus"] or "現行"
        record["displayAddress"] = (stamp.get("address") if stamp.get("coordinateBasis") == "historical-office-location" else stamp.get("currentAddress") or stamp.get("address")) or "住所未確認"
        record["addressLabel"] = "旧所在地" if stamp.get("coordinateBasis") == "historical-office-location" else "現在の所在地"
        record["searchText"] = " ".join(str(value or "") for value in (record["name"], record["city"], stamp.get("address"), stamp.get("currentAddress")))
        record["locationLabel"] = "概算位置" if stamp["coordinatesApproximate"] else "位置確認済み"
        records.append(record)
    if referenced_offices != office_ids:
        missing = sorted(office_ids - referenced_offices)
        raise ValueError(f"offices without stamps: {', '.join(missing)}")
    return offices, records


def load_catalog(root: Path | str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    root = Path(root)
    config = _read_json(root / "source/site.json")
    catalog = _read_json(root / "source/catalog.json")
    _validate_site_config(config)
    offices, records = _validate_catalog(catalog, root, config)
    catalog["offices"] = offices
    return config, catalog, records


def _render_tokens(template: str, values: dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    unknown = re.findall(r"{{([A-Z0-9_]+)}}", rendered)
    if unknown:
        raise ValueError("unrendered template tokens: " + ", ".join(sorted(set(unknown))))
    return rendered


def _copy_public_assets(root: Path, output: Path) -> None:
    if root.resolve() == output.resolve():
        return
    for dirname in ("assets", "vendor"):
        source = root / dirname
        if source.is_dir():
            shutil.copytree(source, output / dirname, dirs_exist_ok=True)


def _write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def _record_counts(records: list[dict[str, Any]], office_count: int) -> dict[str, int]:
    active = [record for record in records if not record["historical"]]
    return {
        "offices": office_count,
        "stamps": len(records),
        "activeOffices": len({record["officeId"] for record in active}),
        "activeStamps": len(active),
    }


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    text = "true" if value is True else "false" if value is False else str(value)
    if text[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + text
    return text


def _csv_bytes(records: list[dict[str, Any]]) -> bytes:
    from io import StringIO
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow([label for _, label in CSV_FIELDS])
    for record in records:
        writer.writerow([_csv_value(record.get(key)) for key, _ in CSV_FIELDS])
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def _address_notes(record: dict[str, Any]) -> str:
    pieces = [f'{record["addressLabel"]}：{record["displayAddress"]}', record["status"]]
    if record["coordinateBasis"] == "current-office-location" and record.get("address") != record.get("currentAddress"):
        pieces.append("風景印紹介の住所：" + str(record.get("address") or "未確認"))
    if record["coordinatesApproximate"]:
        pieces.append("概算位置")
    if record.get("coordinateNote"):
        pieces.append(record["coordinateNote"])
    if record.get("dateWarning"):
        pieces.append(record["dateWarning"])
    return "<br>".join(html.escape(piece) for piece in pieces)


def _table_rows(records: list[dict[str, Any]], with_images: bool) -> str:
    rows = []
    for record in records:
        status_class = "historical" if record["historical"] else ""
        parameters = {"q": record["name"]}
        if record["historical"]:
            parameters["history"] = "true"
        map_url = "../?" + urlencode(parameters)
        row = f'<tr class="{status_class}" data-region="{html.escape(record["region"])}" data-historical="{str(record["historical"]).lower()}" data-search="{html.escape(record["searchText"], quote=True)}">'
        if with_images:
            row += f'<td><a href="{html.escape(record["detailUrl"], quote=True)}" target="_blank" rel="noopener noreferrer"><img src="../{html.escape(record["image"])}" alt="{html.escape(record["name"])}の風景印" loading="lazy" width="58" height="58"></a></td>'
        row += f'<td><a href="{html.escape(record["detailUrl"], quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(record["name"])}</a><small>{html.escape(record["city"])} / {html.escape(record["region"])} · 印ID {html.escape(record["id"])}</small></td>'
        row += '<td class="address-notes">' + _address_notes(record) + '</td>'
        row += f'<td><a class="map-link" href="{html.escape(map_url, quote=True)}">地図で見る</a></td></tr>'
        rows.append(row)
    return "\n".join(rows)


def _source_revision(root: Path, config: dict, catalog: dict) -> str:
    inputs = {"site": config, "catalog": catalog}
    # Hash code and factual assets as well as data. Targets share these inputs.
    inputs["builder"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    inputs["files"] = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for folder in ("source/web", "assets", "vendor")
        for path in sorted((root / folder).rglob("*"))
        if path.is_file() and not path.name.startswith(".")
    }
    return _digest(inputs)


def _index_values(config: dict[str, Any], catalog: dict[str, Any], records: list[dict[str, Any]], target: str, source_revision: str, data_revision: str) -> dict[str, str]:
    counts = _record_counts(records, len(catalog["offices"]))
    region_buttons = ['<button data-region="all" aria-pressed="true">茨城県全域</button>']
    for region in config["regions"]:
        name = html.escape(region["name"])
        region_buttons.append(f'<button data-region="{name}" aria-pressed="false">{name}</button>')
    target_url = config["targets"].get(target, config["targets"]["github"])["url"]
    verification = config["targets"].get(target, {}).get("googleVerification")
    verification_tag = f'<meta name="google-site-verification" content="{html.escape(verification, quote=True)}">' if verification else ""
    coverage = f'{counts["offices"]}局・{counts["stamps"]}件（現行表示 {counts["activeStamps"]}件）'
    return {
        "PAGE_TITLE": html.escape(config["pageTitle"], quote=True),
        "DESCRIPTION": html.escape(config["description"], quote=True),
        "CANONICAL_URL": html.escape(config["canonicalUrl"], quote=True),
        "TITLE": html.escape(config["title"]),
        "EYEBROW": html.escape(config["eyebrow"]),
        "PREFECTURE": html.escape(config["prefecture"]),
        "REGION_BUTTONS": "".join(region_buttons),
        "COVERAGE": html.escape(coverage),
        "ACTIVE_COVERAGE": html.escape(f'通常表示は現行{counts["activeStamps"]}件（{counts["activeOffices"]}局）'),
        "SOURCE_URL": html.escape(catalog["sourceUrl"], quote=True),
        "VERIFIED_AT": html.escape(catalog["verifiedAt"]),
        "CONTENT_UPDATED": html.escape(config["contentUpdated"]),
        "FIRST_RELEASED": html.escape(config["firstReleased"]),
        "RELEASED_AT": html.escape(config["releasedAt"]),
        "AUTHOR_NAME": html.escape(config["author"]["name"]),
        "AUTHOR_READING": html.escape(config["author"]["reading"]),
        "AUTHOR_CONTACT_LABEL": html.escape(config["author"]["contactLabel"]),
        "AUTHOR_CONTACT_URL": html.escape(config["author"]["contactUrl"], quote=True),
        "LOCATION_NOTE": html.escape("日本郵便の店舗地図に掲載された位置を使用します。旧局所在地や概算位置には注記を付けています。"),
        "TARGET_URL": html.escape(target_url, quote=True),
        "REPOSITORY_URL": html.escape(config["repositoryUrl"], quote=True),
        "VERIFICATION_TAG": verification_tag,
        "VERSION": html.escape(config["version"]),
        "SOURCE_REVISION": source_revision,
        "DATA_REVISION": data_revision,
        "TILE_ATTRIBUTION": html.escape(config["tileAttribution"]),
        "TILE_CREDIT_URL": html.escape(config["tileCreditUrl"], quote=True),
        "BOUNDARY_CREDIT_URL": html.escape(config["boundaryCreditUrl"], quote=True),
    }


def _config_js(config: dict[str, Any], catalog: dict[str, Any], records: list[dict[str, Any]], target: str, source_revision: str, data_revision: str) -> str:
    counts = _record_counts(records, len(catalog["offices"]))
    value = {
        "version": config["version"], "target": target, "canonicalUrl": config["canonicalUrl"],
        "targetUrl": config["targets"].get(target, config["targets"]["github"])["url"],
        "regions": [region["name"] for region in config["regions"]],
        "boundaryAsset": config["boundaryAsset"],
        "bounds": config["bounds"], "tileUrl": config["tileUrl"], "tileAttribution": config["tileAttribution"],
        "sourceUrl": catalog["sourceUrl"], "verifiedAt": catalog["verifiedAt"], "contentUpdated": config["contentUpdated"],
        "sourceRevision": source_revision, "dataRevision": data_revision, "counts": counts,
        "csvFields": [[key, label] for key, label in CSV_FIELDS],
    }
    return "window.ATLAS_CONFIG = " + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ";\n"


def _data_json(config: dict[str, Any], catalog: dict[str, Any], records: list[dict[str, Any]], source_revision: str, data_revision: str) -> str:
    counts = _record_counts(records, len(catalog["offices"]))
    value = {
        "schemaVersion": 2, "version": config["version"], "sourceUrl": catalog["sourceUrl"],
        "verifiedAt": catalog["verifiedAt"], "contentUpdated": config["contentUpdated"],
        "partial": bool(catalog.get("partial")), "sourceCount": len(records), "officeCount": len(catalog["offices"]),
        "activeStampCount": counts["activeStamps"], "activeOfficeCount": counts["activeOffices"],
        "sourceRevision": source_revision, "dataRevision": data_revision,
        "locationNote": "日本郵便の店舗地図に掲載された位置を使用します。旧局所在地や概算位置には注記を付けています。",
        "records": records,
    }
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _release(config: dict[str, Any], catalog: dict[str, Any], records: list[dict[str, Any]], target: str, source_revision: str, data_revision: str) -> dict[str, Any]:
    return {
        "version": config["version"], "target": target, "contentUpdated": config["contentUpdated"],
        "firstReleased": config["firstReleased"], "releasedAt": config["releasedAt"],
        "verifiedAt": catalog["verifiedAt"], "sourceUrl": catalog["sourceUrl"],
        "sourceRevision": source_revision, "dataRevision": data_revision,
        "counts": _record_counts(records, len(catalog["offices"])),
        "canonicalUrl": config["canonicalUrl"], "targetUrl": config["targets"].get(target, config["targets"]["github"])["url"],
    }


def _sitemap(config: dict[str, Any]) -> str:
    base = config["canonicalUrl"]
    urls = [base, base + "post-offices/", base + "print/"]
    body = "\n".join(f"  <url><loc>{xml_escape(url)}</loc></url>" for url in urls)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "\n</urlset>\n"


def build(root: Path | str, output: Path | str, target: str = "github") -> dict[str, Any]:
    root = Path(root)
    output = Path(output)
    config, catalog, records = load_catalog(root)
    if target not in config["targets"]:
        raise ValueError(f"unknown build target: {target}")
    source_revision = _source_revision(root, config, catalog)
    data_revision = _digest(records)
    output.mkdir(parents=True, exist_ok=True)
    _copy_public_assets(root, output)
    template = (root / "source/web/index.html").read_text(encoding="utf-8")
    _write(output / "index.html", _render_tokens(template, _index_values(config, catalog, records, target, source_revision, data_revision)))
    for filename in ("app.js", "style.css", "directory.css", "catalog-view.js", "print.css", "print.js"):
        _write(output / filename, (root / "source/web" / filename).read_bytes())
    _write(output / "config.js", _config_js(config, catalog, records, target, source_revision, data_revision))
    _write(output / "data.json", _data_json(config, catalog, records, source_revision, data_revision))
    _write(output / "exports/stamps.csv", _csv_bytes(records))
    region_options = "".join(f'<option value="{html.escape(region["name"])}">{html.escape(region["name"])}</option>' for region in config["regions"])
    values = _index_values(config, catalog, records, target, source_revision, data_revision)
    values["REGION_OPTIONS"] = region_options
    values["DIRECTORY_ROWS"] = _table_rows(records, with_images=True)
    values["PRINT_ROWS"] = _table_rows(records, with_images=False)
    for name, destination in (("directory.html", "post-offices/index.html"), ("print.html", "print/index.html")):
        template = (root / "source/web" / name).read_text(encoding="utf-8")
        _write(output / destination, _render_tokens(template, values))
    release = _release(config, catalog, records, target, source_revision, data_revision)
    _write(output / "release.json", json.dumps(release, ensure_ascii=False, indent=2) + "\n")
    _write(output / "sitemap.xml", _sitemap(config))
    _write(output / ".nojekyll", "")
    return release


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--target", choices=("github", "sites"), default="github")
    args = parser.parse_args()
    output = args.output or args.root
    release = build(args.root, output, target=args.target)
    print(json.dumps(release, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
