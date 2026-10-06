# Ver.2 One Source, Multi Use

このリポジトリでは、風景印・郵便局の正本を source/catalog.json、公開設定と配布先を source/site.json に置きます。編集後は scripts/build_site.py が次の配布物を同じデータ改訂値から生成します。

- 地図画面と検索・地域絞り込み
- 郵便局別の一覧
- CSVダウンロード
- 印刷用リスト
- data.json、サイトマップ、SEOメタ情報

現行の確認済み範囲は郵便局219局・風景印224件です。通常表示は209局・210件で、風景印廃止・郵便局閉鎖・一時閉鎖などの履歴14件は切り替えて確認できます。座標の根拠、概算位置、現在住所と旧住所も正本から各配布物へ引き継ぎます。

更新時は、正本を変更してから次を実行します。

    python3 scripts/build_site.py --target github --output .
    python3 -B -m unittest discover -s tests -v

GitHub Pages版とSites版は、同じ正本から生成した dataRevision とCSVを共有します。release.json には対象、確認日、件数、改訂値を記録します。

