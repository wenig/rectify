"""The platform ASGI app: static host + owner login + mounted rectify editor.

Route order matters — real routes are registered before the catch-all static
handler so ``/login``, ``/_platform/health`` and the ``/_rectify`` mount win. The
whole app is wrapped in :class:`RectifyGate` so the editor's ws/JS require an owner
session even though that auth must see raw WebSocket scopes.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from importlib.resources import files as resource_files
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from rectify.server import create_app as create_rectify_app

from . import auth, seed, site
from .gate import RectifyGate
from .ratelimit import LoginRateLimiter
from .settings import Settings

log = logging.getLogger("rectify.platform")

LOGIN_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rectify — Log in</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #ffffff; color: #1a1d24;
    display: grid; place-items: center; min-height: 100vh; margin: 0; }}
  form {{ background: #f4f5f7; padding: 2rem; border: 1px solid #e4e6eb; border-radius: 12px;
    width: min(320px, 90vw); box-shadow: 0 10px 40px rgba(0,0,0,.08); }}
  h1 {{ font-size: 1.1rem; margin: 0 0 1rem; }}
  input {{ width: 100%; box-sizing: border-box; padding: .6rem .7rem; margin-bottom: .8rem;
    border-radius: 8px; border: 1px solid #d1d5db; background: #ffffff; color: #1a1d24; }}
  button {{ width: 100%; padding: .6rem; border: 0; border-radius: 8px; background: #4f7cff;
    color: white; font-weight: 600; cursor: pointer; }}
  .err {{ color: #b91c1c; font-size: .85rem; margin-bottom: .8rem; }}
</style></head>
<body><form method="post" action="/login">
  <h1>Rectify — owner login</h1>
  {error}
  <input type="password" name="password" placeholder="Owner password" autofocus required>
  <button type="submit">Log in to edit</button>
</form></body></html>
"""


def _starter_dir() -> Path:
    return Path(str(resource_files("rectify.platform") / "starter"))


def build_app(settings: Settings) -> RectifyGate:
    rectify_app = create_rectify_app(settings.rectify_config())
    login_limiter = LoginRateLimiter()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        seed.ensure_site(settings.site_dir, _starter_dir())
        yield

    app = FastAPI(title="Rectify Platform", lifespan=lifespan)

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        if auth.is_owner_from_cookie_header(request.headers.get("cookie"), settings.secret_key):
            return RedirectResponse("/", status_code=302)
        return HTMLResponse(LOGIN_PAGE.format(error=""))

    @app.post("/login")
    async def login_submit(request: Request):
        # Parse the urlencoded body manually so we don't need python-multipart
        # (Starlette's request.form() now hard-requires it even for urlencoded).
        client_ip = request.client.host if request.client else "unknown"
        if login_limiter.is_blocked(client_ip):
            return HTMLResponse(
                LOGIN_PAGE.format(
                    error='<div class="err">Too many attempts. Try again later.</div>'
                ),
                status_code=429,
            )
        body = (await request.body()).decode("utf-8", "replace")
        fields = parse_qs(body)
        password = (fields.get("password") or [""])[0]
        if not auth.check_password(password, settings.owner_password):
            login_limiter.record_failure(client_ip)
            return HTMLResponse(
                LOGIN_PAGE.format(error='<div class="err">Wrong password.</div>'),
                status_code=401,
            )
        login_limiter.reset(client_ip)
        # Mark the cookie Secure when we're actually behind HTTPS (Railway sets
        # X-Forwarded-Proto), but stay usable over plain HTTP for local testing.
        proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie(
            auth.COOKIE_NAME,
            auth.make_session_value(settings.secret_key, settings.session_max_age),
            max_age=settings.session_max_age,
            httponly=True,
            samesite="lax",
            secure=(proto == "https"),
            path="/",
        )
        return resp

    @app.get("/logout")
    def logout():
        resp = RedirectResponse("/", status_code=302)
        resp.delete_cookie(auth.COOKIE_NAME, path="/")
        return resp

    @app.get("/_platform/health")
    def health():
        return {"ok": True, "site": str(settings.site_dir)}

    # Editor: overlay JS + ws, gated by RectifyGate (below) for the owner only.
    app.mount("/_rectify", rectify_app)

    # Catch-all static host. Registered last so the routes above take precedence.
    @app.get("/{full_path:path}")
    def static(full_path: str, request: Request) -> Response:
        is_owner = auth.is_owner_from_cookie_header(
            request.headers.get("cookie"), settings.secret_key
        )
        return site.serve(request, settings.site_dir, is_owner)

    return RectifyGate(app, settings.secret_key)
