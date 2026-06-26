"""End-to-end platform behavior via Starlette TestClient.

Exercises the real wiring: anonymous visitors get a clean site, the owner gets the
overlay injected, and the mounted editor is gated. The lifespan seeds the temp site
from the bundled starter on first boot.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rectify.platform.app import build_app
from rectify.platform.auth import COOKIE_NAME
from rectify.platform.settings import Settings


def _settings(tmp_path):
    return Settings(
        site_dir=tmp_path,
        host="127.0.0.1",
        port=8080,
        owner_password="test123",
        secret_key="devsecret",
        session_max_age=3600,
    )


@pytest.fixture
def client(tmp_path):
    with TestClient(build_app(_settings(tmp_path))) as c:
        yield c


def test_anonymous_homepage_has_no_overlay(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "_rectify" not in r.text


def test_health(client):
    assert client.get("/_platform/health").json()["ok"] is True


def test_login_wrong_password(client):
    r = client.post("/login", data={"password": "nope"}, follow_redirects=False)
    assert r.status_code == 401


def test_login_rate_limited_after_repeated_failures(client):
    for _ in range(5):
        assert client.post("/login", data={"password": "nope"}, follow_redirects=False).status_code == 401
    # 6th attempt is locked out, and the lockout holds even for the right password.
    assert client.post("/login", data={"password": "nope"}, follow_redirects=False).status_code == 429
    assert client.post("/login", data={"password": "test123"}, follow_redirects=False).status_code == 429


def test_login_right_then_owner_sees_overlay(client):
    r = client.post("/login", data={"password": "test123"}, follow_redirects=False)
    assert r.status_code == 302
    assert COOKIE_NAME in r.cookies
    # the client now carries the cookie
    home = client.get("/", follow_redirects=False)
    assert '<script src="/_rectify/rectify.js"' in home.text
    assert client.get("/_rectify/rectify.js").status_code == 200


def test_rectify_gated_for_anonymous(client):
    r = client.get("/_rectify/rectify.js", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login"


def test_anonymous_websocket_rejected(client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/_rectify/ws"):
            pass


def test_upload_gated_for_anonymous(client):
    r = client.post("/_rectify/upload?name=x.png", content=b"data", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login"


def test_owner_upload_list_serve_delete_roundtrip(client, tmp_path):
    client.post("/login", data={"password": "test123"}, follow_redirects=False)

    up = client.post("/_rectify/upload?name=logo.png", content=b"PNGDATA")
    assert up.status_code == 200
    rec = up.json()
    assert rec["url"] == "/uploads/logo.png"
    assert (tmp_path / "uploads" / "logo.png").read_bytes() == b"PNGDATA"

    listed = client.get("/_rectify/uploads").json()["files"]
    assert [f["name"] for f in listed] == ["logo.png"]

    # the static host serves the saved file at its public url
    assert client.get("/uploads/logo.png").content == b"PNGDATA"

    deleted = client.delete("/_rectify/upload?name=logo.png").json()
    assert deleted["ok"] is True
    assert not (tmp_path / "uploads" / "logo.png").exists()
