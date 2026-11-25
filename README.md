# japan-holiday-data
Japanese public holiday data distribution service.

Japan Holiday Data は、内閣府が公開する「国民の祝日・休日」のCSVを、年別の日本語JSONとしてHTTPSで配信する非公式サービスです。収録期間は毎回CSVから読み取ります。利用側は必要な年だけ取得し、その年のデータが変わるまでローカルに保存できます。

## 公開先

GitHub Pagesの標準URLは以下のとおりです。初回の `deploy` ジョブが出力するURLが実際の公開先です。

| 用途 | 公開予定URL |
| --- | --- |
| 配信状況と年別カレンダー | <https://gomadaifuku.github.io/japan-holiday-data/> |
| 全体・年別の更新情報 | <https://gomadaifuku.github.io/japan-holiday-data/manifest.json> |
| データの出典・加工者・利用条件 | <https://gomadaifuku.github.io/japan-holiday-data/data-license.json> |
| 年別の祝日（2026年の例） | <https://gomadaifuku.github.io/japan-holiday-data/holidays/2026.json> |

## ローカルで試す

Python 3.12と標準ライブラリを使用します。以下をリポジトリのルートで実行してください。WindowsのPythonランチャーを使う場合は、`python` を `py -3.12` に読み替えられます。

```sh
python -m unittest discover -s tests -v
python -m scripts.update_holidays --preview
python -m http.server 8765 --bind 127.0.0.1 --directory public
```

プレビューは内閣府からCSVを取得して検証し、`public/` にサイトを生成します。ブラウザーでローカルのポート8765を開くと、年選択とJSON取得を試せます。プレビュー単独では前回公開分との比較やデプロイを行いません。テストの実行記録は [テスト結果](docs/TEST_RESULTS.md) にあります。

## 自動更新

月曜日の06:15（日本時間）にGitHub Actionsが公式CSVを確認します。配信中のManifest・年別ファイルを読み取り、新しいCSVとの全件差分を記録します。レコードの削除を検出すると自動公開を停止します。閲覧者は、トップページの「最終確認日時」からいつ公式CSVを確認したか判断できます。初回公開、削除の承認、停止時の再開、バックアップ・復旧については [運用手順](docs/OPERATIONS.md) を参照してください。

## データの出典と利用条件

**出典**は内閣府「国民の祝日について」掲載のCSVです。内閣府ホームページ利用規約で案内されている公共データ利用規約（第1.0版、PDL1.0）に基づいて利用しています。[内閣府ホームページ「国民の祝日について」](https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html) · [内閣府ホームページの取得元CSV](https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv) · [内閣府ホームページ利用規約](https://www.cao.go.jp/notice/rule.html) · [公共データ利用規約（第1.0版）原文](https://www.digital.go.jp/resources/open_data/public_data_license_v1.0)

**加工者**はgomadaifukuです。公式CSVの日付表記を統一し、年別のJSON形式に変換しています。本サービスは内閣府が運営する公式サービスではありません。

**プログラムのライセンス**は [MIT License](LICENSE) です。内閣府由来の祝日データには上記の利用条件を参照してください。PDL1.0は、出典の明記などの条件に従って複製、加工、公衆送信、商用利用を認めています。再配布時に使える表記例を以下に示します。さらに加工した場合は、自分が行った加工とその主体も明記してください。

> 出典：内閣府「国民の祝日について」掲載CSV（https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv ）、公共データ利用規約（第1.0版）（https://www.digital.go.jp/resources/open_data/public_data_license_v1.0 ）。gomadaifukuが公式CSVを年別JSONに加工。

JSONを直接利用するアプリは、配信元の `data-license.json` から出典・加工者・利用条件を取得できます。[API仕様](docs/API.md)

## 開発資料

- [開発仕様と検証条件](SPECIFICATION.md)
- [API仕様・Garmin向け取得手順](docs/API.md)
- [運用・保守手順](docs/OPERATIONS.md)
- [テスト結果・公開環境での確認状況](docs/TEST_RESULTS.md)
- [変更履歴](CHANGELOG.md)
