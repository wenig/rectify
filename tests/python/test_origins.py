"""Origin allowlist — the CSWSH boundary for the unauthenticated local server."""

from __future__ import annotations

import pytest

from rectify.origins import origin_allowed, parse_origins

HOST = "localhost:4242"


def test_no_origin_allowed():
    # Browsers always send Origin on a WS handshake; absence means a non-browser
    # client (curl/wscat/tests), which is not a CSWSH vector.
    assert origin_allowed(None, HOST, ())
    assert origin_allowed("", HOST, ())


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "https://localhost",
        "http://app.localhost:8000",
        "http://[::1]:9000",
    ],
)
def test_loopback_allowed(origin):
    assert origin_allowed(origin, HOST, ())


@pytest.mark.parametrize(
    "origin",
    ["https://evil.example", "http://evil.example:80", "null"],
)
def test_foreign_and_null_rejected(origin):
    assert not origin_allowed(origin, HOST, ())


def test_same_origin_allowed():
    # How the platform's mounted overlay connects: Origin host == Host header.
    assert origin_allowed("https://my.site.com", "my.site.com", ())
    assert not origin_allowed("https://other.site.com", "my.site.com", ())


def test_explicitly_allowed_origin():
    allowed = ("https://my.site.com",)
    assert origin_allowed("https://my.site.com", HOST, allowed)
    assert not origin_allowed("https://nope.site.com", HOST, allowed)


def test_parse_origins():
    assert parse_origins(None) == ()
    assert parse_origins("") == ()
    assert parse_origins("https://a.com, https://b.com") == ("https://a.com", "https://b.com")
    assert parse_origins("https://a.com https://b.com") == ("https://a.com", "https://b.com")
