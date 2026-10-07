# 茨城県 風景印地図（Ibaraki Scenic Postmarks Map）

初回リリース日：2026-10-06 ／ v2.1.0リリース日：2026-10-08 ／ 最終修正日：2026-10-08（日本時間）

制作・運営：Koji Komatsuzaki（こまつざき こうじ）｜連絡先：[GitHub Issues](https://github.com/kojikomatsuzaki/ibaraki-fukeiin-map/issues)

[公開サイト](https://kojikomatsuzaki.github.io/ibaraki-fukeiin-map/) · [郵便局一覧](https://kojikomatsuzaki.github.io/ibaraki-fukeiin-map/post-offices/) · [リリース](https://github.com/kojikomatsuzaki/ibaraki-fukeiin-map/releases) · [更新履歴](CHANGELOG.md)

茨城県の郵便局にある風景印を、実際の風景印画像で探せる非公式の案内地図です。地図上の画像をクリックすると、日本郵便の各風景印紹介ページが開きます。

## 使い方

- 郵便局名・市町村名で検索できます。
- 県北・県央・鹿行・県南・県西で絞り込めます。
- 通常表示は209局・210件です。「取扱中」「取扱終了（廃止・閉鎖）」「一時閉鎖」を個別に選べます。全て選ぶと全219局・224件を表示します。取扱中は確認日時点の状態で、現在の窓口営業時間を示すものではありません。
- 同じ郵便局の旧図案や複数の公式掲載も収録しています。
- 画像が重なる場合は地図を拡大するか、検索して探してください。

## 訪問先の選択・保存

地図の一覧または郵便局一覧で、持ち出したい郵便局を選択します。「表示中を全選択」も使えます。検索・地域・状態を変えても選択は保持され、ページ移動や再読み込みで解除されます。

- **KML**：Google マイマップ・QGISなど向け。
- **GPX**：ウェイポイント（地点）形式。GPS機器への取り込み可否・操作は機種ごとに異なります。Garmin Connectのコース取り込みとは別です。
- **CSV**：UTF-8 BOM付きの表計算向け形式。
- **Apple Mapsで開く**：各郵便局の位置をApple Mapsで開きます。一括インポートではありません。

選択した局は重複を除いて1局1地点にまとめ、同じ局の複数の公式紹介URLを残します。取扱中の図案がある局ではその位置を優先します。住所は地図表示に使用する現在住所または旧所在地です。郵便局名・住所・緯度経度（WGS84）・取扱状況・公式紹介URL・データ確認日に加え、旧所在地・概算位置を区別する位置注記を保存します。取り込み先によって一部の情報が省略される場合があります。

巡回ルートや経路最適化は含みません。画像は書き出しファイルに同梱しません。従来の全件CSV・表示中CSVは風景印単位の詳細データとして引き続き利用できます。

## データ

確認日：2026年10月5日。日本郵便の[茨城県の風景印一覧](https://www.post.japanpost.jp/enjoy/culture/stamp/fuke/result_pre.php?pref_id=8)をもとにしています。

位置は218件を日本郵便の店舗地図、6件を国土地理院の旧局所在地・住所補完で照合しました。大増郵便局・水戸駅前郵便局の2局は旧所在地に基づく概算位置で、画面に注記しています。廃止・一時閉鎖・取扱状況は変わることがあるため、訪問前に日本郵便の公式情報をご確認ください。

## 構成・更新

HTML・CSS・JavaScriptによる静的サイトです。GitHub Pagesでは`main`ブランチのルートを公開元にします。更新時にPythonで生成物を作成します。公開サーバー側のビルド処理やAPIキーは不要です。

- `source/catalog.json`：風景印と郵便局の正本データ（編集対象）
- `source/site.json`：公開先・SEO・地図設定の正本
- `scripts/build_site.py`：正本から全配布物を再生成するビルド
- `index.html`：地図画面（生成物）
- `post-offices/`：郵便局一覧（生成物）
- `print/`：印刷用リスト（生成物）
- `exports/stamps.csv`：表計算ソフト向けCSV（生成物）
- `data.json`：地図と各配布物が共有する整形済みデータ（生成物）
- `assets/stamps/`：風景印画像
- `assets/ibaraki.geojson`：地理データ
- `vendor/`：Leaflet 1.9.4

正本を変更したら、次のコマンドでGitHub Pages用の生成物を更新します。Sites版も同じ生成結果を使って公開します。

```sh
python3 scripts/build_site.py --target github --output .
python3 -B -m unittest discover -s tests -v
node --test tests/test_catalog_view.cjs tests/test_export.cjs
```

変更を`main`に反映すると、GitHub Pagesが更新されます。背景地図には国土地理院のオンライン地図を使用しています。

Pythonは更新作業時のみ必要で、閲覧・配信には不要です。検索エンジンへの登録は[Googleへの登録手順](SEARCH_INDEXING.md)を参照してください。

## 出典・権利表記

- 風景印画像・掲載情報：[日本郵便](https://www.post.japanpost.jp/enjoy/culture/stamp/fuke/result_pre.php?pref_id=8)。画像等の権利は日本郵便等の権利者に帰属します。
- 背景地図：[国土地理院 地理院タイル](https://maps.gsi.go.jp/development/ichiran.html)
- 地理データ：国土数値情報をもとにした[JapanCityGeoJson](https://github.com/niiyz/JapanCityGeoJson)を表示用に簡略化
- 地図ライブラリ：[Leaflet](https://leafletjs.com/) 1.9.4（BSD-2-Clause、[ライセンス](vendor/leaflet-LICENSE.txt)）

このリポジトリの公開は、第三者の画像・データに対する再利用許諾を与えるものではありません。本サイトは日本郵便の公式サイトではありません。
