"""Single-owner session auth via a stdlib HMAC-signed cookie.

No third-party session library (itsdangerous isn't a guaranteed dependency, and a
hand-rolled cookie lets the WebSocket gate validate auth directly from the raw ASGI
scope without any middleware ordering). The cookie payload is a base64url JSON blob
``{"exp": <unix-ts>}`` plus an HMAC-SHA256 signature over it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from http.cookies import SimpleCookie

COOKIE_NAME = "rectify_session"


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def sign(payload: dict, secret_key: str) -> str:
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(secret_key.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64e(sig)}"


def verify(token: str, secret_key: str) -> dict | None:
    """Return the payload if the token is well-formed, unexpired, and authentic."""
    try:
        body, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret_key.encode(), body.encode(), hashlib.sha256).digest()
    try:
        if not hmac.compare_digest(expected, _b64d(sig)):
            return None
        payload = json.loads(_b64d(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)) or exp < time.time():
        return None
    return payload


def make_session_value(secret_key: str, max_age: int) -> str:
    return sign({"exp": int(time.time()) + max_age}, secret_key)


def check_password(supplied: str, owner_password: str) -> bool:
    return hmac.compare_digest(supplied.encode(), owner_password.encode())


def _cookie_from_header(cookie_header: str | None) -> str | None:
    if not cookie_header:
        return None
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:
        return None
    morsel = jar.get(COOKIE_NAME)
    return morsel.value if morsel else None


def is_owner_from_cookie_header(cookie_header: str | None, secret_key: str) -> bool:
    token = _cookie_from_header(cookie_header)
    return bool(token and verify(token, secret_key))


def is_owner_scope(scope: dict, secret_key: str) -> bool:
    """Owner check from a raw ASGI scope (works for http and websocket)."""
    for name, value in scope.get("headers", []):
        if name == b"cookie":
            return is_owner_from_cookie_header(value.decode("latin-1"), secret_key)
    return False
