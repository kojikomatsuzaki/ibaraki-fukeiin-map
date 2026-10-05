# Googleへの登録手順

サイト側には正規URL・ページ説明・サイトマップを設定し、JavaScriptなしで読める郵便局一覧を用意しています。Googleへの送信はまだ行っていません。

2026-10-06：管理者から提供された所有権確認用のHTMLタグをトップページに追加しました。Search Consoleでの「確認」、サイトマップ送信、インデックス登録リクエストは未確認です。確認タグは所有権の維持に必要なため、今後の更新でも残してください。

## Google Search Console

1. [Search Console](https://search.google.com/search-console/)を、サイトを管理するGoogleアカウントで開きます。
2. 「プロパティを追加」で「URLプレフィックス」を選び、`https://kojikomatsuzaki.github.io/ibaraki-fukeiin-map/` を登録します。末尾の `/` まで含めます。`github.io` のDNSを管理できないため、「ドメイン」方式は使用しません。
3. 所有権確認の「HTMLタグ」を選び、表示された `<meta name="google-site-verification" content="...">` を、このリポジトリの `index.html` の `<head>` 内に追加します。確認値はGoogleが発行したものを使い、推測・自作しません。
4. `main`への反映とGitHub Pagesの配信完了を待ち、Search Consoleで「確認」を押します。確認タグは削除せず保持します。
5. 「サイトマップ」で `sitemap.xml` を送信します。送信対象の完全URLは `https://kojikomatsuzaki.github.io/ibaraki-fukeiin-map/sitemap.xml` です。
6. 「URL検査」でトップページと `https://kojikomatsuzaki.github.io/ibaraki-fukeiin-map/post-offices/` を検査し、必要に応じて「公開URLをテスト」から「インデックス登録をリクエスト」します。
7. 「ページのインデックス登録」などのレポートで、発見・取得・登録の状況を確認します。

サイトマップ送信と登録リクエストは、巡回や検索結果への掲載を保証するものではありません。反映には数日から数週間以上かかる場合があります。同じURLへの繰り返しのリクエストで処理が速くなるわけではありません。

## robots.txtについて

このサイトはGitHub Pagesのプロジェクトパスにあります。Googleが読むrobots.txtは `https://kojikomatsuzaki.github.io/robots.txt` です。このリポジトリ直下に置いて配信される `/ibaraki-fukeiin-map/robots.txt` は、巡回制御には使われません。そのため、効果のないファイルは追加していません。

2026-10-05の確認ではホスト直下のrobots.txtは404で、トップページはHTTP 200・noindexなしでした。robots.txtがないこと自体は巡回を妨げません。将来ホスト直下にrobots.txtを作る場合は、このサイトとCSS・JavaScript・JSON・画像を誤って遮断しないようにします。

## 更新時

`data.json`を更新した場合は、内容更新日に合わせて `scripts/build_directory.py` の `CONTENT_UPDATED` を更新し、`python3 scripts/build_directory.py` を実行します。生成される `post-offices/index.html` と `sitemap.xml` も一緒にコミットしてください。更新していないページの最終更新日を機械的に毎日変えることはしません。

## 公式資料

- [Google：再クロールを依頼する](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl?hl=ja)
- [Google：サイトマップの作成と送信](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap?hl=ja)
- [Search Console：サイトの所有権を確認する](https://support.google.com/webmasters/answer/9008080?hl=ja)
- [Google：robots.txtの作成場所](https://developers.google.com/crawling/docs/robots-txt/create-robots-txt)
