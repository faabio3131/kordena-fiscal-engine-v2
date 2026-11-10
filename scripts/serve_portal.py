#!/usr/bin/env python3
"""Serve the built FM NFCORE portal with conservative browser security headers."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import queue
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import monotonic
from urllib.parse import unquote, urlsplit

_PORTAL_CSP = "; ".join(
    (
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "connect-src 'self'",
    )
)

_API_PREFIX = "/v1/"
# Only this signed, installation-scoped provider ingress is exposed outside /v1/.
# No /webhooks/* wildcard, arbitrary host paths or mutation method broadening.
_BLING_WEBHOOK_PATH = re.compile(r"/webhooks/bling/installations/[0-9a-f]{32}")
# Narrow, audited operator paths exposed without a general /internal/ proxy.
_SPECIAL_PROXY_PATHS = {
    "/runtime/profile": frozenset({"GET", "HEAD"}),
    "/internal/staging/commercial-trial-binding": frozenset({"POST"}),
}
_MAX_PROXY_REQUEST_BYTES = 1024 * 1024
_MAX_PROXY_RESPONSE_BYTES = 2 * 1024 * 1024
_PROXY_TIMEOUT_SECONDS = 15
_PROXY_REQUEST_HEADERS = (
    "Accept",
    "Origin",
    "Content-Type",
    "Cookie",
    "Idempotency-Key",
    "X-CSRF-Token",
    "X-Causation-Id",
    "X-Correlation-Id",
)
_PROXY_RESPONSE_HEADERS = (
    "Cache-Control",
    "Content-Type",
    "Retry-After",
    "WWW-Authenticate",
)

# Bounded idle HTTP/1.1 connection reuse toward the *internal* canonical API.
# Connections never retain Authorization/Cookie headers; each request supplies
# its own session. No fiscal mutation is retried if a pooled socket is stale.
_POOL_LOCK = threading.Lock()
_IDLE_UPSTREAM: dict[
    tuple[str, str, int], queue.LifoQueue[tuple[float, http.client.HTTPConnection]]
] = {}
_IDLE_CAPACITY = 16
# Keep this below the canonical API's 30s keep-alive timeout. Never replay a
# request to hide a stale socket: retire idle connections before sending it.
_MAX_UPSTREAM_IDLE_SECONDS = 10.0


def _borrow_upstream(
    origin: tuple[str, str, int],
) -> http.client.HTTPConnection:
    with _POOL_LOCK:
        idle = _IDLE_UPSTREAM.setdefault(
            origin, queue.LifoQueue(maxsize=_IDLE_CAPACITY)
        )
    while True:
        try:
            returned_at, connection = idle.get_nowait()
        except queue.Empty:
            scheme, host, port = origin
            cls = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
            return cls(host, port, timeout=_PROXY_TIMEOUT_SECONDS)
        if connection.sock is not None and monotonic() - returned_at < _MAX_UPSTREAM_IDLE_SECONDS:
            return connection
        connection.close()


def _release_upstream(
    origin: tuple[str, str, int],
    connection: http.client.HTTPConnection,
    *,
    reusable: bool,
) -> None:
    if not reusable or connection.sock is None:
        connection.close()
        return
    with _POOL_LOCK:
        idle = _IDLE_UPSTREAM.setdefault(
            origin, queue.LifoQueue(maxsize=_IDLE_CAPACITY)
        )
    try:
        idle.put_nowait((monotonic(), connection))
    except queue.Full:
        connection.close()



def _api_upstream() -> tuple[str, str, int] | None:
    raw = os.getenv("NFCORE_PORTAL_API_UPSTREAM", "").strip()
    if not raw:
        return None

    parsed = urlsplit(raw)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("NFCORE_PORTAL_API_UPSTREAM must be an absolute HTTP(S) origin")

    try:
        port = parsed.port
    except ValueError as exc:
        raise RuntimeError("NFCORE_PORTAL_API_UPSTREAM contains an invalid port") from exc

    return (
        parsed.scheme,
        parsed.hostname,
        port or (443 if parsed.scheme == "https" else 80),
    )


class SecurePortalHandler(SimpleHTTPRequestHandler):
    """Static portal + narrow same-origin reverse proxy for canonical NFCore APIs."""

    def end_headers(self) -> None:
        if not self._is_api_request():
            static_path = urlsplit(self.path).path
            if static_path in {"", "/", "/index.html"} or static_path.endswith(".html"):
                self.send_header("Cache-Control", "no-store")
            elif static_path.endswith((".css", ".js", ".svg")):
                self.send_header("Cache-Control", "no-cache, max-age=0, must-revalidate")
        self.send_header("Content-Security-Policy", _PORTAL_CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()

    def _is_api_request(self) -> bool:
        path = urlsplit(self.path).path
        return (
            path.startswith(_API_PREFIX)
            or self.command in _SPECIAL_PROXY_PATHS.get(path, frozenset())
            or (self.command == "POST" and _BLING_WEBHOOK_PATH.fullmatch(path) is not None)
        )

    def _json_error(self, status: int, message: str) -> None:
        body = json.dumps({"detail": message}, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _request_body(self) -> bytes | None:
        raw_length = self.headers.get("Content-Length", "0").strip() or "0"
        try:
            length = int(raw_length)
        except ValueError:
            self._json_error(400, "invalid content length")
            return None
        if length < 0:
            self._json_error(400, "invalid content length")
            return None
        if length > _MAX_PROXY_REQUEST_BYTES:
            self._json_error(413, "request body too large")
            return None
        return self.rfile.read(length) if length else b""

    def _proxy_api(self) -> None:
        try:
            upstream = _api_upstream()
        except RuntimeError:
            self._json_error(503, "portal API upstream is invalid")
            return

        if upstream is None:
            self._json_error(503, "portal API upstream is not configured")
            return

        body = self._request_body()
        if body is None:
            return

        parsed_request = urlsplit(self.path)
        if not self._is_api_request():
            self._json_error(404, "not found")
            return

        target = parsed_request.path
        if parsed_request.query:
            target = f"{target}?{parsed_request.query}"

        # Public trial explicitly rejects authenticated callers; never strip an
        # Authorization header into an apparently anonymous request upstream.
        public_path = unquote(parsed_request.path).rstrip("/")
        if public_path == "/v1/public/trials" and self.headers.get("Authorization"):
            self._json_error(403, "anonymous request required")
            return

        headers: dict[str, str] = {}
        for name in _PROXY_REQUEST_HEADERS:
            value = self.headers.get(name)
            if value:
                headers[name] = value
        if (
            self.command == "POST"
            and _BLING_WEBHOOK_PATH.fullmatch(parsed_request.path) is not None
        ):
            signature = self.headers.get("X-Bling-Signature-256")
            if signature:
                headers["X-Bling-Signature-256"] = signature

        connection = _borrow_upstream(upstream)
        reusable = False

        try:
            connection.request(
                self.command,
                target,
                body=body if body else None,
                headers=headers,
            )
            response = connection.getresponse()
            response_body = response.read(_MAX_PROXY_RESPONSE_BYTES + 1)
            if len(response_body) > _MAX_PROXY_RESPONSE_BYTES:
                self._json_error(502, "portal API upstream response too large")
                return
            reusable = not response.will_close

            self.send_response(response.status)
            for name in _PROXY_RESPONSE_HEADERS:
                value = response.getheader(name)
                if value:
                    self.send_header(name, value)
            for cookie in response.headers.get_all("Set-Cookie", []):
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            if self.command != "HEAD" and response_body:
                self.wfile.write(response_body)
        except (OSError, http.client.HTTPException):
            self._json_error(502, "portal API upstream is unavailable")
        finally:
            _release_upstream(upstream, connection, reusable=reusable)

    def do_GET(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._proxy_api()
            return
        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._proxy_api()
            return
        super().do_HEAD()

    def do_POST(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._proxy_api()
            return
        self._json_error(404, "not found")

    def do_PUT(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._proxy_api()
            return
        self._json_error(404, "not found")

    def do_PATCH(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._proxy_api()
            return
        self._json_error(404, "not found")

    def do_DELETE(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._proxy_api()
            return
        self._json_error(404, "not found")

    def do_OPTIONS(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._proxy_api()
            return
        self._json_error(404, "not found")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the FM NFCORE portal")
    parser.add_argument("--directory", default="/srv/portal")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()

    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        raise SystemExit(f"portal directory does not exist: {directory}")
    if not 1 <= args.port <= 65535:
        raise SystemExit("port must be between 1 and 65535")

    handler = partial(SecurePortalHandler, directory=str(directory))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
