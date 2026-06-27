"""Local agent WebSocket enforces the origin allowlist before accepting."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from rectify.config import Config
from rectify.server import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Config(root=tmp_path)))


def test_ws_rejects_foreign_origin(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"origin": "https://evil.example"}):
            pass


def test_ws_allows_loopback_origin(client):
    with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_ws_allows_no_origin(client):
    # Non-browser clients (no Origin) are allowed.
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_ws_allows_explicitly_configured_origin(tmp_path):
    cfg = Config(root=tmp_path, allowed_origins=("https://my.site.com",))
    client = TestClient(create_app(cfg))
    with client.websocket_connect("/ws", headers={"origin": "https://my.site.com"}) as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_cors_blocks_foreign_origin_on_upload(client):
    # Cross-origin preflight from a foreign site is not granted CORS headers.
    r = client.options(
        "/upload?name=x.png",
        headers={
            "origin": "https://evil.example",
            "access-control-request-method": "POST",
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_cors_allows_loopback_origin_on_upload(client):
    r = client.options(
        "/upload?name=x.png",
        headers={
            "origin": "http://localhost:5173",
            "access-control-request-method": "POST",
        },
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
