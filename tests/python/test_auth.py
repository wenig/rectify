"""auth — HMAC-signed session cookie round-trip, tampering, expiry."""

from __future__ import annotations

import time

from rectify.platform import auth

SECRET = "test-secret"


def test_sign_verify_roundtrip():
    token = auth.sign({"exp": int(time.time()) + 100}, SECRET)
    payload = auth.verify(token, SECRET)
    assert payload is not None and payload["exp"] > time.time()


def test_wrong_secret_rejected():
    token = auth.sign({"exp": int(time.time()) + 100}, SECRET)
    assert auth.verify(token, "other-secret") is None


def test_tampered_body_rejected():
    token = auth.sign({"exp": int(time.time()) + 100}, SECRET)
    body, sig = token.split(".", 1)
    forged = auth.sign({"exp": int(time.time()) + 999999}, SECRET).split(".", 1)[0]
    assert auth.verify(f"{forged}.{sig}", SECRET) is None


def test_expired_token_rejected():
    token = auth.sign({"exp": int(time.time()) - 1}, SECRET)
    assert auth.verify(token, SECRET) is None


def test_malformed_token_rejected():
    assert auth.verify("not-a-token", SECRET) is None
    assert auth.verify("", SECRET) is None


def test_make_session_value_is_verifiable():
    val = auth.make_session_value(SECRET, max_age=60)
    assert auth.verify(val, SECRET) is not None


def test_is_owner_from_cookie_header():
    val = auth.make_session_value(SECRET, max_age=60)
    header = f"foo=bar; {auth.COOKIE_NAME}={val}; baz=qux"
    assert auth.is_owner_from_cookie_header(header, SECRET) is True
    assert auth.is_owner_from_cookie_header("foo=bar", SECRET) is False
    assert auth.is_owner_from_cookie_header(None, SECRET) is False


def test_is_owner_scope_reads_raw_headers():
    val = auth.make_session_value(SECRET, max_age=60)
    scope = {"headers": [(b"cookie", f"{auth.COOKIE_NAME}={val}".encode())]}
    assert auth.is_owner_scope(scope, SECRET) is True
    assert auth.is_owner_scope({"headers": []}, SECRET) is False


def test_check_password():
    assert auth.check_password("hunter2", "hunter2") is True
    assert auth.check_password("nope", "hunter2") is False
