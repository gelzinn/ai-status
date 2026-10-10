"""Small synchronous WinHTTP client using Windows' TLS and certificate store.

Only GET is needed by the collectors. Keep credentials out of exceptions and
disable automatic redirects so authorization cannot cross origins. WinHTTP is
part of Windows 10/11; this avoids distributing a second TLS implementation.
"""
import ctypes as C
from functools import lru_cache
import time
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import getproxies, proxy_bypass

DWORD = C.c_uint32
HANDLE = C.c_void_p
MAX_RESPONSE = 8 * 1024 * 1024
REDIRECTS = {301, 302, 303, 307, 308}


class HTTPError(OSError):
    def __init__(self, code):
        self.code = code
        super().__init__(f"HTTP {code}")


@lru_cache(maxsize=1)
def _api():
    api = C.WinDLL("winhttp", use_last_error=True)
    signatures = {
        "WinHttpOpen": (HANDLE, [C.c_wchar_p, DWORD, C.c_wchar_p, C.c_wchar_p, DWORD]),
        "WinHttpSetTimeouts": (C.c_int32, [HANDLE, C.c_int32, C.c_int32, C.c_int32, C.c_int32]),
        "WinHttpConnect": (HANDLE, [HANDLE, C.c_wchar_p, C.c_uint16, DWORD]),
        "WinHttpOpenRequest": (HANDLE, [HANDLE, C.c_wchar_p, C.c_wchar_p, C.c_wchar_p,
                                        C.c_wchar_p, C.POINTER(C.c_wchar_p), DWORD]),
        "WinHttpSetOption": (C.c_int32, [HANDLE, DWORD, C.c_void_p, DWORD]),
        "WinHttpSetCredentials": (C.c_int32, [HANDLE, DWORD, DWORD, C.c_wchar_p, C.c_wchar_p, C.c_void_p]),
        "WinHttpSendRequest": (C.c_int32, [HANDLE, C.c_wchar_p, DWORD, C.c_void_p, DWORD, DWORD, C.c_size_t]),
        "WinHttpReceiveResponse": (C.c_int32, [HANDLE, C.c_void_p]),
        "WinHttpQueryHeaders": (C.c_int32, [HANDLE, DWORD, C.c_wchar_p, C.c_void_p,
                                          C.POINTER(DWORD), C.POINTER(DWORD)]),
        "WinHttpReadData": (C.c_int32, [HANDLE, C.c_void_p, DWORD, C.POINTER(DWORD)]),
        "WinHttpCloseHandle": (C.c_int32, [HANDLE]),
    }
    for name, (result, arguments) in signatures.items():
        function = getattr(api, name)
        function.restype, function.argtypes = result, arguments
    return api


def _check(result):
    if not result:
        raise OSError("Windows HTTP request failed")
    return result


def _option(api, handle, name, value):
    value = DWORD(value)
    _check(api.WinHttpSetOption(handle, name, C.byref(value), C.sizeof(value)))


def _url(url):
    if any(character in url for character in "\r\n\0"):
        raise ValueError("Invalid HTTP URL")
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.username is not None:
        raise ValueError("Invalid HTTP URL")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if not 0 < port <= 65535:
        raise ValueError("Invalid HTTP port")
    return parts, (parts.scheme, parts.hostname.lower(), port)


def _proxy(host, scheme):
    proxies = getproxies()
    if proxy_bypass(host):
        return 1, None, None  # WINHTTP_ACCESS_TYPE_NO_PROXY
    address = proxies.get(scheme)
    if not address:
        return 4, None, None  # Windows automatic proxy / PAC settings
    parts = urlsplit(address if "://" in address else "http://" + address)
    if parts.scheme != "http" or not parts.hostname:
        raise OSError("Unsupported HTTP proxy")
    hostname = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    credentials = ((unquote(parts.username), unquote(parts.password or ""))
                   if parts.username is not None else None)
    return 3, f"{hostname}:{parts.port or 80}", credentials


def _location(api, handle):
    size = DWORD()
    api.WinHttpQueryHeaders(handle, 33, None, None, C.byref(size), None)
    if not size.value or size.value > 32768:
        raise OSError("Invalid HTTP redirect")
    buffer = C.create_unicode_buffer((size.value + C.sizeof(C.c_wchar) - 1) // C.sizeof(C.c_wchar))
    _check(api.WinHttpQueryHeaders(handle, 33, None, buffer, C.byref(size), None))
    return buffer.value


def _once(url, headers, timeout):
    parts, (_, host, port) = _url(url)
    api = _api()
    handles = []
    try:
        access, proxy, credentials = _proxy(host, parts.scheme)
        session = _check(api.WinHttpOpen("ai-status", access, proxy, None, 0))
        handles.append(session)
        milliseconds = max(1, min(int(timeout * 1000), 2147483647))
        _check(api.WinHttpSetTimeouts(session, milliseconds, milliseconds, milliseconds, milliseconds))
        _option(api, session, 4, 1)  # One connection attempt, within the collector timeout.
        connection = _check(api.WinHttpConnect(session, host.encode("idna").decode("ascii"), port, 0))
        handles.append(connection)
        target = (parts.path or "/") + ("?" + parts.query if parts.query else "")
        handle = _check(api.WinHttpOpenRequest(connection, "GET", target, None, None, None,
                                             0x00800000 if parts.scheme == "https" else 0))
        handles.append(handle)
        _option(api, handle, 88, 0)  # Handle redirects ourselves.
        _option(api, handle, 63, 1)  # No implicit cookie jar (same behavior as urllib).
        _option(api, handle, 77, 2)  # Never automatically use the user's login credentials.
        _option(api, handle, 118, 3)  # Native gzip and deflate decompression.
        if credentials:
            _check(api.WinHttpSetCredentials(handle, 1, 1, *credentials, None))
        raw_headers = "".join(f"{name}: {value}\r\n" for name, value in headers.items())
        _check(api.WinHttpSendRequest(handle, raw_headers, len(raw_headers), None, 0, 0, 0))
        _check(api.WinHttpReceiveResponse(handle, None))
        status, size = DWORD(), DWORD(C.sizeof(DWORD))
        _check(api.WinHttpQueryHeaders(handle, 19 | 0x20000000, None,
                                      C.byref(status), C.byref(size), None))
        if status.value in REDIRECTS:
            return status.value, _location(api, handle)
        if not 200 <= status.value < 300:
            raise HTTPError(status.value)
        chunks, total = [], 0
        buffer, count = C.create_string_buffer(65536), DWORD()
        deadline = time.monotonic() + timeout
        while True:
            if time.monotonic() > deadline:
                raise OSError("HTTP response timed out")
            _check(api.WinHttpReadData(handle, buffer, len(buffer), C.byref(count)))
            if not count.value:
                return status.value, b"".join(chunks)
            total += count.value
            if total > MAX_RESPONSE:
                raise OSError("HTTP response too large")
            chunks.append(buffer.raw[:count.value])
    finally:
        for handle in reversed(handles):
            api.WinHttpCloseHandle(handle)


def request(url, headers=None, timeout=8):
    """Return bytes. Certificate/hostname validation remains enabled in WinHTTP."""
    if timeout <= 0:
        raise ValueError("HTTP timeout must be positive")
    headers = dict(headers or {})
    for name, value in headers.items():
        if (not name or any(character in name for character in ":\r\n\0")
                or any(character in value for character in "\r\n\0")):
            raise ValueError("Invalid HTTP header")
    for _ in range(6):
        _, origin = _url(url)
        status, data = _once(url, headers, timeout)
        if status not in REDIRECTS:
            return data
        destination = urljoin(url, data)
        _, next_origin = _url(destination)
        if origin[0] == "https" and next_origin[0] != "https":
            raise OSError("Insecure HTTP redirect")
        if next_origin != origin:
            headers = {name: value for name, value in headers.items()
                       if name.lower() in {"user-agent", "accept", "accept-language"}}
        url = destination
    raise OSError("Too many HTTP redirects")
