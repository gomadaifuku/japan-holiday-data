"""ネットワーク境界の回帰テスト。実際の通信なしで異常応答も検証する。"""

from email.message import Message
from io import BytesIO
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from scripts import fetch_csv, published
from scripts.generate_site import TEMPLATES
from scripts.generate_json import build_documents


BASE = "https://example.org/japan-holiday-data/"
URL = BASE + "manifest.json"


def http_error(code, url=URL):
    return HTTPError(url, code, "fixture", Message(), BytesIO(b""))


def response(data, media_type, declared_length=None):
    resp = MagicMock(status=200)
    resp.__enter__.return_value = resp
    resp.read.return_value = data
    resp.headers = Message()
    resp.headers["Content-Type"] = media_type
    if declared_length is not None:
        resp.headers["Content-Length"] = str(declared_length)
    return resp


class DownloadTests(unittest.TestCase):
    def test_plain_http_and_downgrade_redirects_rejected(self):
        with self.assertRaises(ValueError):
            fetch_csv.download("http://example.org", limit=100, accept="text/csv")
        with self.assertRaises(ValueError):
            fetch_csv.HTTPSRedirects().redirect_request(None, None, 302, "", {}, "http://example.org")

    @patch("scripts.fetch_csv.time.sleep")
    @patch("scripts.fetch_csv.build_opener")
    def test_transient_errors_then_csv(self, opener, sleep):
        csv = b"fixture"
        opener.return_value.open.side_effect = [http_error(503), URLError("timeout"),
                                                 response(csv, "text/csv", len(csv))]
        self.assertEqual(fetch_csv.fetch_csv(), csv)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])
        self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 30)

    @patch("scripts.fetch_csv.time.sleep")
    @patch("scripts.fetch_csv.build_opener")
    def test_t016_csv_download_failure_raises_after_third_attempt(self, opener, sleep):
        opener.return_value.open.side_effect = URLError("network unavailable")
        with self.assertRaises(URLError):
            fetch_csv.fetch_csv()
        self.assertEqual(opener.return_value.open.call_count, 3)

    @patch("scripts.fetch_csv.build_opener")
    def test_permanent_http_error_retains_status(self, opener):
        opener.return_value.open.side_effect = http_error(403)
        with self.assertRaises(HTTPError) as cm:
            fetch_csv.fetch_csv()
        self.assertEqual(cm.exception.code, 403)
        self.assertEqual(opener.return_value.open.call_count, 1)

    @patch("scripts.fetch_csv.build_opener")
    def test_bounded_stream_even_without_content_length(self, opener):
        for declared_length in (None, 5):
            with self.subTest(declared_length=declared_length):
                resp = response(b"12345", "text/csv", declared_length)
                opener.return_value.open.return_value = resp
                with self.assertRaises(ValueError):
                    fetch_csv.download(BASE, limit=4, accept="text/csv")
                if declared_length is None:
                    resp.read.assert_called_once_with(5)
                else:
                    resp.read.assert_not_called()

    @patch("scripts.fetch_csv.build_opener")
    def test_error_page_is_not_csv(self, opener):
        for content, mime in [(b"<html>error</html>", "text/csv"), (b"Service unavailable", "text/html"),
                              (b"", "text/csv")]:
            with self.subTest(mime=mime, content=content):
                opener.return_value.open.return_value = response(content, mime)
                with self.assertRaises(ValueError):
                    fetch_csv.fetch_csv()


class PublishedTests(unittest.TestCase):
    def setUp(self):
        self.records = {"2040-02-01": "休日", "2041-01-01": "年始"}
        self.manifest, self.years = build_documents(self.records, None, "2041-02-03T00:00:00+09:00")
        self.resources = {"manifest.json": (self.manifest, "application/json"),
                          "": ("<title>Japan Holiday Data</title>", "text/html"),
                          "site.css": ("body{}", "text/css"), "site.js": ("main();", "text/javascript")}
        license_info = json.loads((TEMPLATES / "data-license.json").read_bytes())
        self.resources["data-license.json"] = (license_info, "application/json")
        for year, doc in self.years.items():
            self.resources[f"holidays/{year}.json"] = (doc, "application/json")

    def fake_download(self, url, *, limit, accept):
        path = url.removeprefix(BASE)
        if path not in self.resources:
            raise http_error(404, url)
        body, kind = self.resources[path]
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False)
        return fetch_csv.Download(body.encode(), 200, kind, None, None)

    @patch("scripts.published.download")
    def test_t020_only_explicit_first_manifest_404_is_allowed(self, download):
        for initial, code in ((False, 404), (True, 403), (True, 503)):
            with self.subTest(initial=initial, code=code):
                download.side_effect = http_error(code)
                with self.assertRaises(HTTPError):
                    published.load_previous(BASE, initial=initial)
        download.side_effect = http_error(404)
        self.assertEqual(published.load_previous(BASE, initial=True), (None, {}))

    def test_first_run_with_existing_manifest_must_validate_all_years(self):
        with patch("scripts.published.download", side_effect=self.fake_download):
            self.assertEqual(published.load_previous(BASE, initial=True), (self.manifest, self.records))
            del self.resources["holidays/2041.json"]
            with self.assertRaises(HTTPError):
                published.load_previous(BASE, initial=True)

    def test_strict_json_read(self):
        for bad in (b'{"a":{"x":0,"x":1}}', b'{"x":NaN}', b'[]', b'\xef\xbb\xbf{}', b'{"x":"\xff"}'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                published.strict_json(bad)

    def test_verify_checks_all_public_files_and_unavailable_year(self):
        with patch("scripts.published.download", side_effect=self.fake_download) as download:
            published.verify_once(BASE, self.manifest)
            self.assertEqual({c.args[0] for c in download.call_args_list},
                             {BASE + p for p in self.resources} | {BASE + "holidays/2039.json"})
            self.resources["holidays/2039.json"] = ({}, "application/json")
            with self.assertRaisesRegex(ValueError, "404"):
                published.verify_once(BASE, self.manifest)

    def test_verify_rejects_outdated_attribution(self):
        self.resources["data-license.json"][0]["modifiedBy"] = "old publisher"
        with patch("scripts.published.download", side_effect=self.fake_download):
            with self.assertRaisesRegex(ValueError, "利用条件"):
                published.verify_once(BASE, self.manifest)

    def test_verify_rejects_bad_mime_and_stale_or_tampered_data(self):
        with patch("scripts.published.download", side_effect=self.fake_download):
            self.resources["manifest.json"] = (self.manifest, "text/plain")
            with self.assertRaisesRegex(ValueError, "Content-Type"):
                published.verify_once(BASE, self.manifest)
            self.resources["manifest.json"] = (self.manifest, "application/json")
            with self.assertRaisesRegex(ValueError, "Manifest"):
                published.verify_once(BASE, dict(self.manifest, checkedAt="2041-02-04T00:00:00+09:00"))
            self.years[2040]["holidays"]["02-01"] = "破損"
            with self.assertRaises(ValueError):
                published.verify_once(BASE, self.manifest)

    @patch("scripts.published.time.sleep")
    @patch("scripts.published.verify_once")
    def test_verify_retries_cache_lag(self, run, sleep):
        run.side_effect = [ValueError("cached"), None]
        published.verify(BASE, self.manifest)
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(10)
