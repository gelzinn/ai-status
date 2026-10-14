"""Native HTTP behavior and credential handling; network tests use localhost."""
from contextlib import contextmanager
import ctypes as C
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import threading
import unittest
from unittest.mock import Mock, patch

from core import provider_http, windows_http as http
from tls_fixture import localhost_tls_context


class HTTPPolicyTests(unittest.TestCase):
    def test_dispatch_and_utf8(self):
        with patch("core.paths.IS_WINDOWS", True), patch.object(http, "request", return_value='{"text":"ação"}'.encode()) as api:
            self.assertEqual(json.loads(provider_http.request("https://example.invalid", {"Authorization": "Bearer test"})), {"text": "ação"})
        api.assert_called_once_with("https://example.invalid", {"User-Agent": "ai-status", "Authorization": "Bearer test"}, 8)

    def test_native_errors_hide_credentials(self):
        for error in (http.HTTPError(401), OSError("token secret-value")):
            with self.subTest(error=type(error).__name__), patch("core.paths.IS_WINDOWS", True), patch.object(http, "request", side_effect=error):
                with self.assertRaises(provider_http.QueryError) as result:
                    provider_http.request("https://example.invalid?token=secret-value")
                self.assertNotIn("secret-value", str(result.exception))
                if isinstance(error, http.HTTPError):
                    self.assertIn("401", str(result.exception))

    def test_same_origin_redirect_preserves_explicit_auth(self):
        headers = {"Authorization": "Bearer test", "Cookie": "session=test"}
        with patch.object(http, "_once", side_effect=[(302, "/usage"), (200, b"ok")]) as api:
            self.assertEqual(http.request("https://example.invalid/start", headers), b"ok")
        self.assertEqual(api.call_args.args[:2], ("https://example.invalid/usage", headers))

    def test_cross_origin_redirect_drops_all_account_headers(self):
        headers = {"Authorization": "Bearer test", "Cookie": "session=test", "ChatGPT-Account-Id": "test", "Accept": "application/json"}
        with patch.object(http, "_once", side_effect=[(302, "https://other.invalid/usage"), (200, b"ok")]) as api:
            http.request("https://example.invalid/start", headers)
        self.assertEqual(api.call_args.args[1], {"Accept": "application/json"})

    def test_insecure_redirect_and_redirect_loop_fail(self):
        for location in ("http://example.invalid", "/again"):
            with self.subTest(location=location), patch.object(http, "_once", return_value=(302, location)) as api:
                with self.assertRaises(OSError):
                    http.request("https://example.invalid", {"Authorization": "Bearer test"})
                self.assertLessEqual(api.call_count, 6)

    def test_invalid_urls_and_headers_never_reach_native_api(self):
        with patch.object(http, "_api") as api:
            for url, headers in [("file:///test", {}), ("https://user:secret@example.invalid", {}),
                                 ("https://example.invalid\r\n", {}), ("https://example.invalid", {"X-Test": "value\r\nAuthorization: test"})]:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    http.request(url, headers)
        api.assert_not_called()

    def test_proxy_bypass_and_explicit_proxy_credentials(self):
        with patch.object(http, "getproxies", return_value={"https": "http://user:p%40ss@localhost:8888"}), patch.object(http, "proxy_bypass", return_value=False):
            self.assertEqual(http._proxy("example.invalid", "https"), (3, "localhost:8888", ("user", "p@ss")))
        with patch.object(http, "getproxies", return_value={}), patch.object(http, "proxy_bypass", return_value=True):
            self.assertEqual(http._proxy("localhost", "https"), (1, None, None))

    def test_handles_close_on_http_and_transport_failure(self):
        for transport_failure in (True, False):
            with self.subTest(transport_failure=transport_failure):
                api = Mock()
                api.WinHttpOpen.return_value = 1
                api.WinHttpConnect.return_value = 2
                api.WinHttpOpenRequest.return_value = 3
                api.WinHttpSendRequest.return_value = not transport_failure

                def query(handle, flags, name, buffer, size, index):
                    C.cast(buffer, C.POINTER(http.DWORD))[0] = 401
                    return True

                api.WinHttpQueryHeaders.side_effect = query
                with patch.object(http, "_api", return_value=api), patch.object(http, "_proxy", return_value=(1, None, None)):
                    with self.assertRaises(OSError):
                        http.request("https://example.invalid", {"Authorization": "Bearer test"})
                self.assertEqual([call.args[0] for call in api.WinHttpCloseHandle.call_args_list], [3, 2, 1])


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/redirect", "/cross-origin"):
            self.send_response(302)
            self.send_header("Location", "/echo" if self.path == "/redirect" else self.server.other_url + "/echo")
            self.end_headers()
            return
        if self.path == "/unauthorized":
            self.send_response(401)
            self.end_headers()
            return
        if self.path == "/slow":
            # Wait for test teardown instead of leaking a long sleeping thread.
            self.server.stopped.wait(2)
            return
        payload = json.dumps({"path": self.path, "authorization": self.headers.get("Authorization"),
                              "cookie": self.headers.get("Cookie"), "text": "ação"}, ensure_ascii=False).encode()
        if self.path == "/gzip":
            payload = gzip.compress(payload)
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        if self.path == "/gzip":
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@contextmanager
def server(context=None):
    instance = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    instance.stopped = threading.Event()
    if context:
        instance.socket = context.wrap_socket(instance.socket, server_side=True)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield instance, f'{"https" if context else "http"}://127.0.0.1:{instance.server_port}'
    finally:
        instance.stopped.set()
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=2)


@unittest.skipUnless(sys.platform == "win32", "WinHTTP integration needs Windows")
class NativeHTTPTests(unittest.TestCase):
    def test_auth_redirect_gzip_and_http_errors(self):
        with server() as (first, url), server() as (_, other):
            first.other_url = other
            headers = {"Authorization": "Bearer test", "Cookie": "session=test"}
            for route in ("/echo?query=yes", "/redirect", "/gzip"):
                with self.subTest(route=route):
                    result = json.loads(http.request(url + route, headers, timeout=2))
                    self.assertEqual(result["authorization"], "Bearer test")
                    self.assertEqual(result["cookie"], "session=test")
                    self.assertEqual(result["text"], "ação")
            redirected = json.loads(http.request(url + "/cross-origin", headers, timeout=2))
            self.assertIsNone(redirected["authorization"])
            self.assertIsNone(redirected["cookie"])
            with self.assertRaises(http.HTTPError) as result:
                http.request(url + "/unauthorized", timeout=2)
            self.assertEqual(result.exception.code, 401)

    def test_native_timeout(self):
        with server() as (_, url), self.assertRaises(OSError):
            http.request(url + "/slow", timeout=0.1)

    def test_native_tls_rejects_untrusted_certificate(self):
        with server(localhost_tls_context()) as (_, url), self.assertRaises(OSError):
            http.request(url, timeout=2)


if __name__ == "__main__":
    unittest.main()
