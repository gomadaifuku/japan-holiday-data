# Japan Holiday Data API v1

日本の祝日・休日を日付から引くための、認証不要の静的JSON APIです。JSONはUTF-8（BOMなし）、メディアタイプは `application/json` です。相対パスはすべてプロジェクトの基本URLを起点とします。Pages既定の基本URLは `https://gomadaifuku.github.io/japan-holiday-data/` です。実際の公開状況は [テスト結果](TEST_RESULTS.md) を参照してください。

| HTTPS GET | 取得内容 | サイズ設計目標 |
| --- | --- | --- |
| [manifest.json](https://gomadaifuku.github.io/japan-holiday-data/manifest.json) | 収録期間、確認時刻、全体・年別のバージョン | 16 KiB以内 |
| [holidays/2026.json](https://gomadaifuku.github.io/japan-holiday-data/holidays/2026.json) | 例として2026年の祝日のみ | 1年あたり8 KiB以内 |
| [holidays/2027.json](https://gomadaifuku.github.io/japan-holiday-data/holidays/2027.json) | 例として2027年の祝日のみ | 同上 |
| [data-license.json](https://gomadaifuku.github.io/japan-holiday-data/data-license.json) | 出典、公式CSVのURL、加工者、データの利用条件 | — |
| [トップページ](https://gomadaifuku.github.io/japan-holiday-data/) | 日本語の配信状況と年選択画面（HTML） | — |

収録年ごとのURLは `holidays/YYYY.json` です。年はManifestの `yearVersions` にある4桁のキーから選んでください。APIにページング、クエリパラメーター、全期間一括JSONはありません。

## JSONを再利用するときの出典・利用条件

データ提供元は内閣府です。gomadaifukuが、内閣府ホームページ「国民の祝日について」の公式CSVを年別JSONに加工して配信しています。本サービスは内閣府が運営する公式サービスではありません。[内閣府ホームページの取得元CSV](https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv) · [内閣府ホームページの掲載ページ](https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html)

内閣府由来の祝日データは公共データ利用規約（第1.0版、PDL1.0）に基づいて利用しています。プログラムのライセンスはMITです。[内閣府ホームページ利用規約](https://www.cao.go.jp/notice/rule.html) · [公共データ利用規約（第1.0版）原文](https://www.digital.go.jp/resources/open_data/public_data_license_v1.0) · [プログラムのMIT License](../LICENSE)

アプリからは基本URLを起点に `GET data-license.json` で出典・加工者・利用条件を取得できます。祝日データを再配布するときは、出典と規約のリンク、gomadaifukuによるCSVからJSONへの加工をアプリの情報画面や同梱文書に記載してください。さらに編集した場合はその内容と主体も明記してください。この情報は独立したファイルで提供するため、Manifest・年別JSONの既存スキーマとバージョン計算はそのまま利用できます。

`data-license.json` の `sourceUrl` は元のCSV、`dataLicenseUrl` は規約本文、`modifiedBy` と `modification` は加工者と加工内容を示します。`softwareLicense` はプログラムに適用するライセンスです。利用条件の案内は祝日データとは別に更新されるため、再配布時には最新の案内を確認してください。

## Manifest

| キー | JSON型 | 定義 |
| --- | --- | --- |
| schemaVersion | number（整数） | この契約は `1`。利用側の対応範囲を判定する |
| dataVersion | string | 全日付・名称のSHA-256、小文字16進数64桁 |
| minYear / maxYear | number（整数） | 最初・最後の収録年。両端を含む |
| recordCount | number（整数） | 全収録年の祝日・休日の日付数 |
| updatedAt | string | データ内容の最終変更を検知した時刻 |
| checkedAt | string | 公式CSVを正常に取得・検証した時刻 |
| source | string | `内閣府` |
| sourceUrl | string | データ元の公式CSVのHTTPS URL |
| yearVersions | object | すべての収録年をキー、各年のSHA-256を値とする辞書 |

時刻はISO 8601で、オフセットは `+09:00`（日本時間）です。データが同じ週は `checkedAt` のみ進みます。スキーマの変更は `schemaVersion` で識別します。[Manifestスキーマ](../schemas/manifest.schema.json)

## 年別JSON

| キー | JSON型 | 定義 |
| --- | --- | --- |
| schemaVersion | number（整数） | Manifestと同じスキーマバージョン |
| year | number（整数） | 要求したファイルの年 |
| dataVersion | string | Manifestの `yearVersions["YYYY"]` に対応するSHA-256 |
| holidays | object | ゼロ埋めした `MM-DD` → 公式CSVの日本語名称 |

構造とハッシュの**架空のテスト例**を示します。1件のみを収録したこの例では、名称に含まれる文字もハッシュの入力です。

```json
{"schemaVersion":1,"year":2030,"dataVersion":"90a4740107b9b7761b8be6024ad49dab60ea9410775c581b2b12e16f2ae1216a","holidays":{"01-01":"テスト休日"}}
```

該当年のファイルを正常に取得したうえで `holidays` に日付がなければ「この公式CSVに掲載されていない日」です。年が未収録、ファイルが取得できない、またはバージョン不一致なら、その年の祝日の有無は判定できません。提供元が「休日」とする名称もそのまま返します。[年別スキーマ](../schemas/holidays.schema.json)

## バージョンの計算

全体・年別とも、対象日の完全な日付 `YYYY-MM-DD` と名称をペアにして日付の昇順に並べます。この二次元配列を、日本語をエスケープせず、区切りに空白を入れないJSONとしてUTF-8に変換し、BOMや末尾の改行を加えずSHA-256を計算します。上記テスト例のハッシュ入力は `[["2030-01-01","テスト休日"]]` です。

日付順やCSVの文字コードの違い、CSVのHTTPヘッダー、ファイルの整形、取得日時はハッシュ値に影響しません。年別ハッシュを再計算するときはキーにファイルの年とハイフンを付け、完全な日付に戻してください。実装例は [version_manager.py](../scripts/version_manager.py) にあります。

## Garminなどの利用側での同期

1. ManifestをGETし、HTTP 200、JSON形式、対応済みの `schemaVersion` を確認します。
2. 必要な年の `yearVersions["YYYY"]` を取り出し、保存済みの**同じ年の**バージョンと比較します。一致すればその年の再取得を省けます。
3. 未保存または変更があれば、対応する `holidays/YYYY.json` をGETします。HTTP 200であること、JSONが読み取れること、`year` と `schemaVersion`、`dataVersion`、日付と名称の型を確認します。
4. すべて一致したときだけ、年別データとそのバージョンを一緒に保存します。通信中断・JSON異常・バージョン不一致のときは、最後に検証した年別データを保持します。
5. Pagesのキャッシュ反映中はManifestと年別ファイルが異なる世代のことがあります。間隔を空けてManifestからやり直してください。未収録年のHTTP 404や一時的なHTTPエラーを「祝日0件」として保存しないでください。

ファイルサイズの設計目標はGarmin端末の実測上限ではありません。受信上限、オフライン時の表示、端末での更新間隔はアプリ側で決めます。[Garmin Connect IQ Communications API](https://developer.garmin.com/connect-iq/api-docs/Toybox/Communications.html)
