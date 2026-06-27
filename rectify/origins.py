"""Origin allowlist for the local agent server — defense against CSWSH.

The local agent (``rectify`` CLI, bound to localhost) has no password: it's a
developer tool. But WebSockets are *not* subject to the same-origin policy, so any
website the developer visits could otherwise open a socket to ``ws://localhost:4242/ws``
and silently drive the agent (read/rewrite local source). This module decides which
``Origin`` values may connect.

The overlay legitimately runs on the developer's own site, which is usually a
*different* localhost port (e.g. a Vite dev server on ``:5173``), so we can't require
same-origin. Instead we allow:

* requests with **no** ``Origin`` header — browsers always send one on a WS
  handshake, so its absence means a non-browser client (curl, wscat, tests), which
  is not a CSWSH vector;
* **loopback** origins (``localhost`` / ``127.0.0.1`` / ``[::1]`` / ``*.localhost``,
  any scheme or port) — the developer's own machine;
* **same-origin** requests (``Origin`` host:port equals the ``Host`` header) — this
  is how the platform's mounted overlay connects;
* any origin explicitly configured via ``RECTIFY_ALLOWED_ORIGINS`` /
  ``Config.allowed_origins``.

Everything else (a remote site, or the ``null`` origin from a sandboxed iframe or
``file://`` page) is rejected.
"""

from __future__ import annotations

from urllib.parse import urlsplit

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Regex form of the loopback rule for Starlette's CORSMiddleware (HTTP side).
# Matches http/https on localhost / 127.0.0.1 / [::1] with an optional port.
LOOPBACK_ORIGIN_RE = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"


def parse_origins(raw: str | None) -> tuple[str, ...]:
    """Split a comma/space-separated ``RECTIFY_ALLOWED_ORIGINS`` value into a tuple."""
    if not raw:
        return ()
    return tuple(o.strip() for o in raw.replace(",", " ").split() if o.strip())


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    host = host.lower()
    return host in _LOOPBACK_HOSTS or host.endswith(".localhost")


def origin_allowed(origin: str | None, host_header: str | None, allowed) -> bool:
    """Return True if a WebSocket/HTTP request with this ``Origin`` may connect.

    Args:
        origin: The ``Origin`` request header (``None`` if absent).
        host_header: The ``Host`` request header, for the same-origin check.
        allowed: Extra origins to permit verbatim (e.g. ``Config.allowed_origins``).
    """
    if not origin:
        # No Origin → not a browser; CSWSH is browser-only, so this is safe.
        return True
    origin = origin.strip()
    if origin == "null":
        # Sandboxed iframe / file:// page. Configure it explicitly to allow.
        return False
    if origin in (allowed or ()):
        return True
    parts = urlsplit(origin)
    if _is_loopback(parts.hostname):
        return True
    if host_header and parts.netloc.lower() == host_header.lower():
        return True
    return False
