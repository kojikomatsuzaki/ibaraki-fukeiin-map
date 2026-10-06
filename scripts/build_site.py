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
    if config.get("version") != "2.0.0":
        raise ValueError("source/site.json version must be 2.0.0")
    for key in ("title", "prefecture", "pageTitle", "description", "canonicalUrl", "repositoryUrl"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise ValueError(f"site config requires non-empty {key}")
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
        record = dict(stamp)
        office = office_by_id[office_id]
        record.update(name=office["name"], city=office["city"], region=office["region"])
        record["stampId"] = stamp_id
        record["imageUrl"] = stamp["image"]
        record["verifiedAt"] = catalog["verifiedAt"]
        record["displayStatus"] = _display_status(stamp)
        record["status"] = record["displayStatus"] or "現行"
        record["displayAddress"] = stamp.get("currentAddress") or stamp.get("address") or "住所未確認"
        record["addressLabel"] = record["displayAddress"]
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


def _directory_rows(records: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for record in records:
        classes = "historical" if record["historical"] else ""
        status = html.escape(record["status"])
        rows.append(
            f'<tr class="{classes}" data-region="{html.escape(record["region"])}" data-status="{html.escape(record["status"])}">'
            f'<td><img src="../{html.escape(record["image"])}" alt="{html.escape(record["name"])}の風景印" loading="lazy"></td>'
            f'<td><a href="{html.escape(record["detailUrl"], quote=True)}" target="_blank" rel="noopener">{html.escape(record["name"])}</a><small>{html.escape(record["city"])} / {html.escape(record["region"])}</small></td>'
            f'<td>{html.escape(record["displayAddress"])}<small>{status}</small></td>'
            f'<td><a class="map-link" href="../?q={html.escape(record["name"], quote=True)}">地図で見る</a></td></tr>'
        )
    return "\n".join(rows)


def _print_rows(records: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for record in records:
        classes = "historical" if record["historical"] else ""
        rows.append(
            f'<tr class="{classes}" data-region="{html.escape(record["region"])}" data-historical="{str(record["historical"]).lower()}">'
            f'<td>{html.escape(record["name"])}</td><td>{html.escape(record["city"])}</td><td>{html.escape(record["region"])}</td>'
            f'<td>{html.escape(record["displayAddress"])}<br><small>{html.escape(record["status"])}</small></td>'
            f'<td><a href="{html.escape(record["detailUrl"], quote=True)}" target="_blank" rel="noopener">紹介</a></td></tr>'
        )
    return "\n".join(rows)


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
    source_revision = _digest({"site": config, "catalog": catalog})
    data_revision = _digest(records)
    output.mkdir(parents=True, exist_ok=True)
    for relative in ("index.html", "app.js", "data.json", "config.js", "catalog-view.js", "style.css", "directory.css", "print.css", "print.js", "post-offices", "print", "exports", "release.json", "sitemap.xml", ".nojekyll"):
        path = output / relative
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    _copy_public_assets(root, output)
    template = (root / "source/web/index.html").read_text(encoding="utf-8")
    _write(output / "index.html", _render_tokens(template, _index_values(config, catalog, records, target, source_revision, data_revision)))
    for filename in ("app.js", "style.css", "directory.css"):
        _write(output / filename, (root / "source/web" / filename).read_bytes())
    _write(output / "config.js", _config_js(config, catalog, records, target, source_revision, data_revision))
    _write(output / "catalog-view.js", r"""(function(){
  const cfg=window.ATLAS_CONFIG||{};
  const fields=cfg.csvFields||[];
  const text=value=>value===null||value===undefined?'':value===true?'true':value===false?'false':String(value);
  const csvCell=value=>{let s=text(value);if(/^[=+\-@\t\r]/.test(s))s="'"+s;return /[",\r\n]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;};
  const csvText=records=>'\ufeff'+[fields.map(field=>csvCell(field[1])).join(','),...records.map(record=>fields.map(field=>csvCell(record[field[0]])).join(','))].join('\r\n')+'\r\n';
  const downloadCsv=(records,name='ibaraki-fukeiin.csv')=>{const blob=new Blob([csvText(records)],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  const params=values=>new URLSearchParams(Object.entries(values).filter(([,value])=>value&&value!=='all')).toString();
  window.AtlasData={csvText,downloadCsv,params};
})();
""")
    _write(output / "data.json", _data_json(config, catalog, records, source_revision, data_revision))
    _write(output / "exports/stamps.csv", _csv_bytes(records))
    region_options = "".join(f'<option value="{html.escape(region["name"])}">{html.escape(region["name"])}</option>' for region in config["regions"])
    directory_template = r"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>茨城県の風景印・郵便局一覧｜茨城 風景印地図</title><meta name="description" content="茨城県の風景印224件を郵便局名・地域・住所で一覧できます。"><link rel="canonical" href="{{CANONICAL_URL}}post-offices/"><link rel="stylesheet" href="../style.css"><link rel="stylesheet" href="../directory.css"></head><body><header class="directory-header"><a href="../">← 地図へ戻る</a><p class="eyebrow">IBARAKI STAMP ATLAS</p><h1>茨城県の風景印・郵便局一覧</h1><p>{{COVERAGE}}。風景印画像は日本郵便の公式紹介ページへリンクしています。</p><nav><a href="../exports/stamps.csv">CSVをダウンロード</a><a href="../print/">印刷用リスト</a></nav></header><main class="directory-main"><div class="directory-tools"><label>検索 <input id="directory-search" type="search" placeholder="郵便局名・市町村・住所"></label><label>地域 <select id="directory-region"><option value="all">全地域</option>{{REGION_OPTIONS}}</select></label><label class="history-toggle"><input id="directory-history" type="checkbox"> 廃止・一時閉鎖を含める</label><span id="directory-count"></span></div><div class="table-wrap"><table><thead><tr><th>印</th><th>郵便局</th><th>住所・状態</th><th>地図</th></tr></thead><tbody id="directory-body">{{DIRECTORY_ROWS}}</tbody></table></div></main><script>const search=document.getElementById('directory-search'),region=document.getElementById('directory-region'),history=document.getElementById('directory-history'),rows=[...document.querySelectorAll('#directory-body tr')],count=document.getElementById('directory-count');function draw(){const q=search.value.normalize('NFKC').toLowerCase().replace(/[\s　]/g,'');let n=0;rows.forEach(row=>{const okRegion=region.value==='all'||row.dataset.region===region.value;const okHistory=history.checked||!row.classList.contains('historical');const okQuery=!q||row.textContent.normalize('NFKC').toLowerCase().replace(/[\s　]/g,'').includes(q);row.hidden=!(okRegion&&okHistory&&okQuery);if(!row.hidden)n++;});count.textContent=n+'件を表示';}search.addEventListener('input',draw);region.addEventListener('change',draw);history.addEventListener('change',draw);draw();</script></body></html>"""
    directory_values = _index_values(config, catalog, records, target, source_revision, data_revision)
    directory_values.update({"REGION_OPTIONS": region_options, "DIRECTORY_ROWS": _directory_rows(records)})
    _write(output / "post-offices/index.html", _render_tokens(directory_template, directory_values))
    print_template = """<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>茨城県の風景印・郵便局 印刷用リスト</title><link rel="canonical" href="{{CANONICAL_URL}}print/"><link rel="stylesheet" href="../print.css"></head><body><header><a href="../">← 地図へ戻る</a><p class="eyebrow">IBARAKI STAMP ATLAS / {{VERSION}}</p><h1>茨城県の風景印・郵便局リスト</h1><p>{{COVERAGE}}／確認日 {{VERIFIED_AT}}</p></header><div class="print-tools"><label>検索 <input id="print-search" type="search" placeholder="郵便局名・住所"></label><label>地域 <select id="print-region"><option value="all">全地域</option>{{REGION_OPTIONS}}</select></label><label><input id="print-history" type="checkbox"> 廃止・一時閉鎖を含める</label><button type="button" onclick="window.print()">印刷</button><a href="../exports/stamps.csv">CSV</a><span id="print-count"></span></div><div class="table-wrap"><table><thead><tr><th>郵便局</th><th>市町村</th><th>地域</th><th>住所・状態</th><th>紹介</th></tr></thead><tbody id="print-body">{{PRINT_ROWS}}</tbody></table></div><script src="print.js"></script></body></html>"""
    print_values = _index_values(config, catalog, records, target, source_revision, data_revision)
    print_values.update({"REGION_OPTIONS": region_options, "PRINT_ROWS": _print_rows(records)})
    _write(output / "print/index.html", _render_tokens(print_template, print_values))
    _write(output / "print.css", """@page{size:A4;margin:12mm}*{box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'Hiragino Kaku Gothic ProN','Yu Gothic',Meiryo,sans-serif;color:#173848;margin:0;font-size:12px}header{border-bottom:2px solid #173848;padding:12px 0 14px;margin-bottom:12px}header a{color:#165d77}.eyebrow{color:#ad3d33;letter-spacing:.16em;font-size:10px;font-weight:700;margin:8px 0}h1{font-size:22px;margin:0 0 7px}header p{margin:4px 0;color:#62737b}.print-tools{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:10px;padding:8px;background:#f2f6f7}.print-tools label{display:inline-flex;align-items:center;gap:5px}.print-tools input,.print-tools select,.print-tools button{font:inherit;border:1px solid #cbd6dc;border-radius:3px;padding:5px;background:white}.print-tools button{cursor:pointer}.print-tools a{color:#165d77}.print-tools span{margin-left:auto;color:#62737b}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd7dc;padding:5px 7px;text-align:left;vertical-align:top}th{background:#e9f0f2;font-weight:700}td small{display:block;color:#766c68;margin-top:3px}tr.historical{color:#6a7378;background:#fafafa}a{color:inherit}@media print{header a,.print-tools{display:none}body{font-size:9px}h1{font-size:17px}th,td{padding:3px 4px}.table-wrap{overflow:visible}tr.historical{display:none}}""")
    _write(output / "print.js", r"""const search=document.getElementById('print-search'),region=document.getElementById('print-region'),history=document.getElementById('print-history'),rows=[...document.querySelectorAll('#print-body tr')],count=document.getElementById('print-count');function draw(){const q=search.value.normalize('NFKC').toLowerCase().replace(/[\s　]/g,'');let n=0;rows.forEach(row=>{const okRegion=region.value==='all'||row.dataset.region===region.value;const okHistory=history.checked||row.dataset.historical!=='true';const okQuery=!q||row.textContent.normalize('NFKC').toLowerCase().replace(/[\s　]/g,'').includes(q);row.hidden=!(okRegion&&okHistory&&okQuery);if(!row.hidden)n++;});count.textContent=n+'件を表示';}search.addEventListener('input',draw);region.addEventListener('change',draw);history.addEventListener('change',draw);draw();""")
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
