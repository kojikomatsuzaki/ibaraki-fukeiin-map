# 茨城 風景印地図

[公開サイト](https://kojikomatsuzaki.github.io/ibaraki-fukeiin-map/) · [郵便局一覧](https://kojikomatsuzaki.github.io/ibaraki-fukeiin-map/post-offices/) · [リリース](https://github.com/kojikomatsuzaki/ibaraki-fukeiin-map/releases) · [更新履歴](CHANGELOG.md)

茨城県の郵便局にある風景印を、実際の風景印画像で探せる非公式の案内地図です。地図上の画像をクリックすると、日本郵便の各風景印紹介ページが開きます。

## 使い方

- 郵便局名・市町村名で検索できます。
- 県北・県央・鹿行・県南・県西で絞り込めます。
- 通常表示は209局・210件です。「廃止・一時閉鎖も含める」で全219局・224件を表示します。
- 同じ郵便局の旧図案や複数の公式掲載も収録しています。
- 画像が重なる場合は地図を拡大するか、検索して探してください。

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
node --test tests/test_catalog_view.cjs
```

変更を`main`に反映すると、GitHub Pagesが更新されます。背景地図には国土地理院のオンライン地図を使用しています。

Pythonは更新作業時のみ必要で、閲覧・配信には不要です。検索エンジンへの登録は[Googleへの登録手順](SEARCH_INDEXING.md)を参照してください。

## 出典・権利表記

- 風景印画像・掲載情報：[日本郵便](https://www.post.japanpost.jp/enjoy/culture/stamp/fuke/result_pre.php?pref_id=8)。画像等の権利は日本郵便等の権利者に帰属します。
- 背景地図：[国土地理院 地理院タイル](https://maps.gsi.go.jp/development/ichiran.html)
- 地理データ：国土数値情報をもとにした[JapanCityGeoJson](https://github.com/niiyz/JapanCityGeoJson)を表示用に簡略化
- 地図ライブラリ：[Leaflet](https://leafletjs.com/) 1.9.4（BSD-2-Clause、[ライセンス](vendor/leaflet-LICENSE.txt)）

このリポジトリの公開は、第三者の画像・データに対する再利用許諾を与えるものではありません。本サイトは日本郵便の公式サイトではありません。
