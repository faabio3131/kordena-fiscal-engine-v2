#!/usr/bin/env python3
"""Serve the built FM NFCORE portal with conservative browser security headers."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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


class SecurePortalHandler(SimpleHTTPRequestHandler):
    """Static file handler that hardens the browser surface by default."""

    def end_headers(self) -> None:
        self.send_header("Content-Security-Policy", _PORTAL_CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()


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
