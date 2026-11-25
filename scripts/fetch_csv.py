"""公開ファイルの HTTPS 取得と、内閣府 CSV の取得条件。"""

from dataclasses import dataclass
from http.client import IncompleteRead, RemoteDisconnected
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .config import SOURCE_URL

TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 3
MAX_CSV_BYTES = 4 * 1024 * 1024
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


def require_https(url: str):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username is not None:
        raise ValueError(f"認証なしの HTTPS URL が必要です: {parts.hostname!r}")
    return parts


class HTTPSRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 最初の URL だけでなく、転送先でも HTTPS を必須とする。
        require_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class Download:
    body: bytes
    status: int
    content_type: str
    etag: str | None
    last_modified: str | None


def download(url: str, *, limit: int, accept: str) -> Download:
    require_https(url)
    request = Request(url, headers={
        "Accept": accept, "Accept-Encoding": "identity",
        "Cache-Control": "no-cache", "User-Agent": "Japan-Holiday-Data/0.01",
    })
    # 標準の HTTPSHandler がシステムの信頼ストアで証明書を検証する。
    opener = build_opener(HTTPSRedirects())
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}: {url}")
                length = response.headers.get("Content-Length")
                if length is not None and not 0 <= int(length) <= limit:
                    raise ValueError(f"Content-Length が許容範囲外です: {length!r} ({url})")
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise ValueError(f"ダウンロード上限 {limit} bytes を超えました: {url}")
                if length is not None and len(body) != int(length):
                    raise IncompleteRead(body, int(length) - len(body))
                return Download(body, response.status, response.headers.get_content_type(),
                                response.headers.get("ETag"), response.headers.get("Last-Modified"))
        except HTTPError as exc:
            exc.close()
            if exc.code not in RETRY_STATUS or attempt == MAX_ATTEMPTS:
                raise
            reason = f"HTTP {exc.code}"
        except (URLError, TimeoutError, ConnectionError, IncompleteRead, RemoteDisconnected) as exc:
            if isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError) or attempt == MAX_ATTEMPTS:
                raise
            reason = str(exc)
        delay = 2 ** (attempt - 1)
        print(f"取得再試行 {attempt}/{MAX_ATTEMPTS}: {url} ({reason}), {delay}s 待機")
        time.sleep(delay)
    raise AssertionError("unreachable")


def fetch_csv() -> bytes:
    result = download(SOURCE_URL, limit=MAX_CSV_BYTES, accept="text/csv, text/plain, */*;q=0.1")
    print(f"取得元 {SOURCE_URL} HTTP {result.status}, {len(result.body)} bytes, "
          f"Content-Type={result.content_type}, ETag={result.etag!r}, Last-Modified={result.last_modified!r}")
    if result.content_type not in {"text/csv", "application/csv", "text/plain", "application/octet-stream",
                                   "application/vnd.ms-excel"}:
        raise ValueError(f"CSV 以外の Content-Type です: {result.content_type}")
    if not result.body or result.body.removeprefix(b"\xef\xbb\xbf").lstrip().startswith(b"<"):
        raise ValueError("公式 CSV が空、または HTML/XML です")
    return result.body
