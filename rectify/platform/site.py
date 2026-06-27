"""Static site serving with owner-only overlay injection.

A single catch-all handler serves files from the site directory. HTML responses get
the rectify overlay ``<script>`` injected *only* for authenticated owners — anonymous
visitors receive clean markup and never load the editor.
"""

from __future__ import annotations

from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, Response

# Where the mounted rectify app lives; the overlay's ws + JS hang off this prefix.
RECTIFY_PREFIX = "/_rectify"

_HTML_SUFFIXES = {".html", ".htm"}


def safe_path(site_dir: Path, url_path: str) -> Path | None:
    """Resolve a URL path under site_dir, refusing traversal outside it."""
    candidate = (site_dir / url_path.lstrip("/")).resolve()
    try:
        candidate.relative_to(site_dir)
    except ValueError:
        return None
    return candidate


def resolve_target(site_dir: Path, url_path: str) -> Path | None:
    """Map a URL to an on-disk file, resolving directories to index.html."""
    target = safe_path(site_dir, url_path)
    if target is None:
        return None
    if target.is_dir():
        target = target / "index.html"
    return target if target.is_file() else None


def _scheme_host(request: Request) -> tuple[str, str]:
    headers = request.headers
    proto = headers.get("x-forwarded-proto", request.url.scheme)
    # X-Forwarded-Proto may be a comma list (proto chain); take the first.
    proto = proto.split(",")[0].strip()
    host = headers.get("x-forwarded-host") or headers.get("host") or request.url.netloc
    return proto, host


def overlay_tag(request: Request) -> str:
    """Build the overlay <script> tag pointed at this origin's mounted editor."""
    proto, host = _scheme_host(request)
    ws_scheme = "wss" if proto == "https" else "ws"
    endpoint = f"{ws_scheme}://{host}{RECTIFY_PREFIX}/ws"
    return (
        f'<script src="{RECTIFY_PREFIX}/rectify.js" '
        f'data-rectify-endpoint="{endpoint}" '
        f"data-rectify-reload></script>"
    )


def inject(html: str, tag: str) -> str:
    """Insert the overlay tag just before the last </body> (else append)."""
    idx = html.rfind("</body>")
    if idx == -1:
        return html + "\n" + tag + "\n"
    return html[:idx] + tag + "\n" + html[idx:]


def serve(request: Request, site_dir: Path, is_owner: bool) -> Response:
    target = resolve_target(site_dir, request.url.path)
    if target is None:
        not_found = site_dir / "404.html"
        if not_found.is_file():
            return HTMLResponse(not_found.read_text("utf-8"), status_code=404)
        return HTMLResponse("<h1>404 — Not found</h1>", status_code=404)

    if target.suffix.lower() in _HTML_SUFFIXES:
        html = target.read_text("utf-8")
        if is_owner:
            html = inject(html, overlay_tag(request))
        # Owner/anon variants differ, so never let a shared cache serve one for the other.
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    return FileResponse(target)
