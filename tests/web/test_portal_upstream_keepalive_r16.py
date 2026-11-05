"""Bounded internal API upstream HTTP keep-alive never shares request headers."""
from __future__ import annotations

import socket
from pathlib import Path
from runpy import run_path

# The portal server is deployed as a standalone script, not an importable
# application package; load the exact source without modifying sys.path.
_MODULE = run_path(
    str(Path(__file__).resolve().parents[2] / "scripts" / "serve_portal.py")
)
_borrow_upstream = _MODULE["_borrow_upstream"]
_release_upstream = _MODULE["_release_upstream"]


def test_pool_reuses_a_healthy_connection_without_external_network() -> None:
    key = ("http", "127.0.0.1", 54321)
    connection = _borrow_upstream(key)
    local, peer = socket.socketpair()
    try:
        connection.sock = local
        _release_upstream(key, connection, reusable=True)
        second = _borrow_upstream(key)
        assert second is connection
        second.close()
    finally:
        peer.close()


def test_pool_discards_nonreusable_connections() -> None:
    key = ("http", "127.0.0.1", 54322)
    first = _borrow_upstream(key)
    _release_upstream(key, first, reusable=False)
    second = _borrow_upstream(key)
    assert second is not first
    second.close()


def test_idle_connection_is_retired_before_api_keepalive_expires(monkeypatch) -> None:
    clock = [100.0]
    monkeypatch.setitem(_borrow_upstream.__globals__, "monotonic", lambda: clock[0])
    key = ("http", "127.0.0.1", 54323)
    connection = _borrow_upstream(key)
    local, peer = socket.socketpair()
    try:
        connection.sock = local
        _release_upstream(key, connection, reusable=True)
        clock[0] += 11.0
        second = _borrow_upstream(key)
        assert second is not connection
        assert connection.sock is None
        second.close()
    finally:
        connection.close()
        peer.close()


def test_closed_pooled_socket_is_discarded_without_any_request_replay() -> None:
    key = ("http", "127.0.0.1", 54324)
    connection = _borrow_upstream(key)
    local, peer = socket.socketpair()
    try:
        connection.sock = local
        _release_upstream(key, connection, reusable=True)
        connection.close()
        second = _borrow_upstream(key)
        assert second is not connection
        second.close()
    finally:
        peer.close()


def test_recent_connection_keeps_original_session_free_reuse(monkeypatch) -> None:
    clock = [500.0]
    monkeypatch.setitem(_borrow_upstream.__globals__, "monotonic", lambda: clock[0])
    key = ("http", "127.0.0.1", 54325)
    connection = _borrow_upstream(key)
    local, peer = socket.socketpair()
    try:
        connection.sock = local
        _release_upstream(key, connection, reusable=True)
        clock[0] += 2.0
        assert _borrow_upstream(key) is connection
    finally:
        connection.close()
        peer.close()


def test_first_request_after_idle_uses_fresh_socket_without_replay(monkeypatch) -> None:
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen = []
    closed = threading.Event()

    class Upstream(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):  # noqa: N802
            seen.append(self.path)
            self.send_response(401)
            self.send_header("Content-Length", "0")
            self.end_headers()
            # Model the API expiring a keep-alive socket without a new response.
            self.close_connection = True

        def finish(self):
            super().finish()
            closed.set()

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Upstream)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
    thread.start()
    key = ("http", "127.0.0.1", server.server_address[1])
    clock = [1000.0]
    monkeypatch.setitem(_borrow_upstream.__globals__, "monotonic", lambda: clock[0])
    first = _borrow_upstream(key)
    second = None
    try:
        first.request("GET", "/v1/portal/bootstrap")
        reply = first.getresponse()
        assert reply.status == 401
        reply.read()
        _release_upstream(key, first, reusable=True)
        assert closed.wait(2)
        clock[0] += 11.0
        second = _borrow_upstream(key)
        assert second is not first
        second.request("GET", "/v1/portal/bootstrap")
        reply = second.getresponse()
        assert reply.status == 401
        reply.read()
        assert seen == ["/v1/portal/bootstrap", "/v1/portal/bootstrap"]
    finally:
        first.close()
        if second is not None:
            second.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
