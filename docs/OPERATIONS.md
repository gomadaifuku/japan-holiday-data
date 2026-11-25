# Japan Holiday Data 運用手順（Ver.0.01）

## GitHubの初期設定と初回公開

1. リポジトリ管理者が `gomadaifuku/japan-holiday-data` の公開範囲が **Public**、既定ブランチが **main** であることを確認する。Visibility の変更は既存リポジトリの内容を公開する操作なので、必要な場合は所有者が判断する。
2. **Settings → Actions → General** で Actions と GitHub公式の `actions/*` の使用を許可する。Workflow permissionsの既定は読み取りでよい。ワークフロー内で権限をジョブ別に指定しており、個人用トークンやSecretsの登録は不要。
3. **Settings → Pages → Build and deployment → Source → GitHub Actions** を選ぶ。カスタムドメインは空欄とし、標準のHTTPS URLを使用する。**Settings → Environments → github-pages** のデプロイ許可ブランチを `main` に設定する。無人の定期更新を行う場合は、毎回の手動承認が必要な保護ルールを設定しない。
4. PRの **Checks → Check holiday data** で単体テスト、Runnerからの内閣府CSV取得、全件突合が成功したことを確認してレビュー・マージする。この検証は開発ブランチへのpushでも実行される。
5. 初回マージ直後の通常の更新は、まだ存在しないManifestの404で停止する。**Actions → Update holiday data → Run workflow** でブランチに `main` を選び、`initial` のみにチェックして実行する。初回フラグはManifest自体の404だけを許容する。既に存在するManifestは初回でも比較対象となる。
6. `build → deploy → verify` の3ジョブと最終検証の成功を確認する。**deployのSummaryに表示されたURL** を記録し、そのURLからトップページ、`manifest.json`、`holidays/YYYY.json` を開く。実端末で年を選択し、該当年のJSONを取得する。未収録年へのGETは404となる。
7. 初回公開後、内閣府へのリンクが設置されたサイトのURLを、管理者から内閣府大臣官房政策評価広報課へ連絡する。案内ページに記載された連絡先・フォームを使用する。[内閣府ホームページへのリンクについて](https://www.cao.go.jp/notice/aboutlink.html)

ブランチルールを利用する場合は、PRでの `Check holiday data` を必須チェックに指定できる。[GitHub Pagesのカスタムワークフロー](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

## 通常の更新・停止からの再開

毎週月曜日06:15（JST、UTCの日曜21:15）に `main` で更新する。GitHubのキュー状況で開始が遅れることがある。手動更新は **Actions → Update holiday data → Run workflow → main** で全入力を初期値のまま実行する。mainへのpushも同じ更新を起動する。同じ公開先への実行は取得・比較から公開検証まで直列化し、実行中のデプロイを中断しない。

Summaryの **Test → Fetch, compare and generate → deploy → verify** を順に確認する。CSVのHTTP応答、ETag・Last-Modified、文字コード、日付範囲、件数、前回・今回のハッシュ、追加・変更・削除された日付、生成サイズが記録される。ETagや取得時刻が変わっても内容が同じなら `updatedAt` と各ハッシュを維持し、正常なデプロイで `checkedAt` が進む。詳細な差分はビルドのログにも残る。

月1回および翌年分の追加が見込まれる2月頃に、Actionsの直近の成功日時、公式CSVの最終収録年、Pagesの表示、無料枠・利用条件を確認する。ページに最終確認から14日を超えた注意が出た場合は `checkedAt` と最後のRunのログを照合する。公開リポジトリで60日間アクティビティがないと定期ワークフローが無効化される場合がある。**Actions → Update holiday data** で無効化の表示を確認し、**Enable workflow** を選んでから通常の手動更新を実行する。その後、次の月曜のschedule実行を確認する。[GitHubの再有効化手順](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/disabling-and-enabling-a-workflow)

## 既存の日付が削除された場合

1. 通常更新の失敗ログで削除された日付と名称、名称変更、追加、収録範囲、今回の `dataVersion` を確認する。名称のみの変更や連続した新しい年の追加は自動処理される。
2. 内閣府の案内ページと実際のCSVを照合する。一時的な欠損や配布元の障害なら公開済みデータを維持し、公式データが回復してから再実行する。
3. 正当な削除と判断した管理者は、**Run workflow** の `approve_removals` に、レビューした候補全体のSHA-256（小文字16進64桁）を入力する。初回・復旧の入力は使用しない。実行時にCSVが変わって候補ハッシュが異なる場合は再び停止する。全日付削除・年の途中欠落・不正な日付など、品質検証の失敗はこの承認でも公開できない。

## 失敗箇所ごとの対応

| 段階 | 確認と操作 |
|---|---|
| CSVの通信 | 取得元URL、HTTPステータス、通信エラーを調べる。一時的な失敗は最大3回の試行後に停止する。解消後に手動更新する。 |
| CSVの形式・件数・前回データの取得 | ヘッダー、名称、欠損年、公開先URL・各年別JSONを確認する。既存Manifestを取得できないときはアクセスやPagesの配信状態を回復してから再試行する。 |
| build・テスト | Summaryと失敗ステップを読み、ローカルでテストとプレビューを実行する。更新失敗時も公開中のPagesを参照できる。 |
| deploy | Settings → Pages のSource、github-pages環境の許可ブランチ、デプロイ権限、Artifactの有効期限を確認する。サイトと現在のManifestを照合してから再実行する。 |
| verify | 公開先のURL、HTTP・Content-Type、日付件数、`checkedAt`・バージョンの不一致を調べる。検証はキャッシュ反映を待って再試行する。反映後に失敗したverifyジョブを再実行し、それでも不整合が続く場合は確認済みのバックアップを選ぶ。 |

## バックアップの取得と復旧

`build` は `holiday-backup-<実行試行番号>` Artifact（`public/` 全体と `data/raw/syukujitsu.csv`）と、公開用のPages Artifactを別々に作る。バックアップの保持設定は90日で、リポジトリ・組織側の上限にも従う。復旧元には**公開後のverifyまで成功したmainのUpdate holiday data** を使用する。Actionsのrun URL末尾の数値がRun ID。保存対象のRunとverifyジョブを削除すると復旧元の検証情報も失われる。

- **有効期間内の復旧**：手動実行で `restore_run_id` に正常時のRun IDを入力し、他の入力は初期値のまま実行する。同じRunで再実行した場合も以前のバックアップを保持する。ワークフローは、そのRunで直近に成功したverifyに記録されたZIPのSHA-256でArtifactを選択・検証し、元のCSVと保存済みJSONを全件突合して同じサイトを公開する。復旧後のverifyも実際の公開先に対して行う。
- **長期保存**：正常なRunのSummaryから、成功した検証に対応する `holiday-backup-<実行試行番号>` の元のZIPをダウンロードする。ZIPを展開・再圧縮せず、`holiday-backup.zip`、Run ID、公開された `dataVersion`、verifyの `Verified backup SHA-256` の値を保管する。Linuxでは `sha256sum holiday-backup.zip`、PowerShellでは `Get-FileHash holiday-backup.zip -Algorithm SHA256` で元のSHA-256と照合できる。このZIPのSHA-256は祝日データの `dataVersion` とは別の値である。
- **Artifact期限後の復旧**：管理者が、元のRunと同じリポジトリにタグ名 `pages-backup-<Run ID>` のGitHub Releaseを作成し、保存した元のZIPをファイル名 `holiday-backup.zip` で添付する。タグの対象には元Runのコミットを選ぶ。手動実行で `restore_run_id` を指定し、`restore_from_release` を有効にする。ワークフローはReleaseのZIPを元Runの成功したverifyステップに記録されたSHA-256で照合してから展開する。元のRun・ジョブ履歴または正しいZIPを失った場合はこの自動復旧は停止する。
- **復旧後**：元の正常時の日時・ハッシュが戻る。公開URL、年別JSON、トップページの表示を確認し、障害原因を取り除いて通常更新する。次のscheduleやmainへのpushも通常更新を実行するので、再発が予想される場合は原因の修正までワークフローを一時停止する。

現行の `data-license.json` と内容が異なるバックアップや、このファイルを欠く旧版は、復旧時の配信物検証で停止する。この場合は現行の利用条件に対応した正常版を選ぶ。該当版がなければ、保管した公式CSVから現行の出典・加工・利用条件表示を含む配信物を再構築し、全件突合とレビューを経て公開する。

有効なバックアップがない場合は、配信中のファイル一式の保存、公式CSVからの再生成と全件照合、PRでの修正レビューを行い、正常な内容を確認してから公開を再開する。

## アクションと公開範囲

PR・開発ブランチのワークフローは読み取り権限で検証する。本番ではbuildがcheckout、Pagesの基本URL解決、必要時の過去Run読み取りを行い、deployに `pages: write` と `id-token: write` を付与する。Pagesにアップロードする対象は検証済みの `public/` だけである。

実装時に各公式Actionのメタデータ・リリースを確認し、ワークフローの `uses` を完全なコミットSHAに固定した。更新時は対象リリースの入力・出力（特にArtifactの取得とハッシュ）、ランナー要件、リリースノートを確認し、PRのチェックを通す。

| 用途 | 公式Action |
|---|---|
| チェックアウト・Python | [checkout](https://github.com/actions/checkout)、[setup-python](https://github.com/actions/setup-python) |
| Pages URL取得・公開 | [configure-pages](https://github.com/actions/configure-pages)、[upload-pages-artifact](https://github.com/actions/upload-pages-artifact)、[deploy-pages](https://github.com/actions/deploy-pages) |
| バックアップ | [upload-artifact](https://github.com/actions/upload-artifact)、[download-artifact](https://github.com/actions/download-artifact) |

[README](../README.md) · [API仕様](API.md) · [実施済みテスト](TEST_RESULTS.md)
