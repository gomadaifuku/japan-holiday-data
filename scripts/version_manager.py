"""正規化済みの祝日だけを対象に、内容のバージョンを算出する。"""

import hashlib
import json


def data_version(records: dict[str, str]) -> str:
    # 年別でも完全なISO日付を使う。CSVの行順や配信JSONの整形には依存しない。
    canonical = json.dumps(sorted(records.items()), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
