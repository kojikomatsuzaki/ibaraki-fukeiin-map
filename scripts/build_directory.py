"""Generate a readable, script-free directory and sitemap from the map dataset."""
import json
from collections import defaultdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "https://kojikomatsuzaki.github.io/ibaraki-fukeiin-map/"
CONTENT_UPDATED = "2026-10-06"  # Change only when the published page content changes.
REGIONS = [("県北", "kenpoku"), ("県央", "keno"), ("鹿行", "rokko"), ("県南", "kennan"), ("県西", "kensei")]
data = json.loads((ROOT / "data.json").read_text())
records = data["records"]
assert {r["region"] for r in records} <= {name for name, _ in REGIONS}
groups = defaultdict(list)
for record in records:
    groups[record["region"]].append(record)


def status(r):
    if r["officeStatus"] == "temporarily-closed":
        return f'{r.get("officeStatusDate") or ""} 一時閉鎖'
    if r["abolished"]:
        return f'{r.get("endDate") or ""} 風景印廃止'
    if r["officeStatus"] == "closed":
        return f'{r.get("officeStatusDate") or ""} 郵便局閉鎖'
    return ""


def entry(r):
    label = status(r)
    status_html = f'<p class="status">{escape(label.strip())}</p>' if label else ""
    approximate = '<p class="approximate">概算位置（旧所在地から補完）</p>' if r["coordinatesApproximate"] else ""
    address = r.get("currentAddress") if not r["historical"] else None
    address_label = "所在地" if address else "公式紹介ページの掲載住所"
    address = address or r.get("address") or ""
    address_html = f'<p class="address">{address_label}：{escape(address)}</p>' if address else ""
    return f'''<article class="entry" id="stamp-{escape(r['id'])}">
<a href="{escape(r['detailUrl'])}" target="_blank" rel="noopener noreferrer" aria-label="{escape(r['name'])}の風景印紹介（新しいタブ）"><img src="../{escape(r['image'])}" alt="{escape(r['name'])}の風景印" width="76" height="76" loading="lazy"></a>
<div class="entry-body"><h3>{escape(r['name'])}</h3><p>{escape(r['city'])}</p>{address_html}{status_html}{approximate}<a class="official-link" href="{escape(r['detailUrl'])}" target="_blank" rel="noopener noreferrer">日本郵便の風景印紹介を見る</a></div>
</article>'''


sections = []
for name, anchor in REGIONS:
    region_records = sorted(groups[name], key=lambda r: (r["city"], r["name"], int(r["id"])))
    count = len({r["name"] for r in region_records})
    cards = "\n".join(entry(r) for r in region_records)
    sections.append(f'<section class="region-section" id="{anchor}"><h2>{name}<span>{count}局・{len(region_records)}件</span></h2><div class="office-grid">{cards}</div></section>')
navigation = "".join(f'<a href="#{anchor}">{name}</a>' for name, anchor in REGIONS)
total_offices = len({r["name"] for r in records})
active = [r for r in records if not r["historical"]]
active_offices = len({r["name"] for r in active})
title = "茨城県の風景印・郵便局一覧｜茨城 風景印地図"
description = f"茨城県の風景印を県北・県央・鹿行・県南・県西の地域別に紹介。{total_offices}局・{len(records)}件の風景印画像と日本郵便の紹介ページを掲載。廃止・一時閉鎖の注記付き。"
page = f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><meta name="description" content="{description}">
<link rel="canonical" href="{ORIGIN}post-offices/"><meta name="robots" content="index,follow">
<meta property="og:type" content="website"><meta property="og:locale" content="ja_JP"><meta property="og:title" content="{title}"><meta property="og:description" content="{description}"><meta property="og:url" content="{ORIGIN}post-offices/">
<link rel="icon" href="../assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="../directory.css?v=1.0.0"></head>
<body><header class="guide-header"><a class="guide-brand" href="../">〒 茨城 風景印地図</a><a class="back-map" href="../">地図で探す →</a></header>
<main class="directory"><div class="intro"><p class="eyebrow">IBARAKI STAMP DIRECTORY</p><h1>茨城県の風景印・郵便局一覧</h1>
<p>日本郵便の公式一覧に掲載された{total_offices}局・{len(records)}件の風景印を、5つの地域に分けて紹介します。画像や紹介リンクから各郵便局の公式ページを開けます。</p>
<p><a href="../">風景印地図</a>では、郵便局の位置を見ながら名前や地域で検索できます。通常表示は{active_offices}局・{len(active)}件。本一覧は廃止・一時閉鎖や旧図案も含めて掲載しています。</p>
<p class="data-date">データ確認日：{escape(data['verifiedAt'])} ／ 日本郵便の公式サイトではない、個人による案内地図です。</p></div>
<nav class="region-nav" aria-label="地域別の郵便局一覧">{navigation}</nav>
{''.join(sections)}
<section class="guide-notes"><h2>一覧について</h2><p>同じ郵便局に複数の掲載がある場合は、画像・紹介ページごとに収録しています。廃止された風景印と一時閉鎖中の郵便局は区別して表示しています。訪問前に最新の取扱状況を日本郵便でご確認ください。</p>
<p>位置は218件を日本郵便の店舗地図、6件を国土地理院の旧局所在地・住所補完で照合しました。大増郵便局と水戸駅前郵便局は旧所在地から補った概算位置です。</p>
<p>出典：<a href="https://www.post.japanpost.jp/enjoy/culture/stamp/fuke/result_pre.php?pref_id=8" target="_blank" rel="noopener noreferrer">日本郵便「茨城県の風景印」</a>。風景印画像等の権利は日本郵便等の権利者に帰属します。</p></section></main>
<footer class="guide-footer"><a href="../">地図へ戻る</a><a href="https://github.com/kojikomatsuzaki/ibaraki-fukeiin-map/releases/tag/v1.0.0">v1.0.0</a><a href="https://github.com/kojikomatsuzaki/ibaraki-fukeiin-map/issues">情報の訂正・不具合を報告</a></footer></body></html>
'''
(ROOT / "post-offices").mkdir(exist_ok=True)
(ROOT / "post-offices" / "index.html").write_text(page)
(ROOT / "sitemap.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{ORIGIN}</loc><lastmod>{CONTENT_UPDATED}</lastmod></url>
  <url><loc>{ORIGIN}post-offices/</loc><lastmod>{CONTENT_UPDATED}</lastmod></url>
</urlset>
''')
print(f"Generated directory: {total_offices} offices, {len(records)} records; sitemap: 2 pages")
