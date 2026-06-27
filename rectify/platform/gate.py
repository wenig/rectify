"""ASGI wrapper that gates the mounted rectify app behind the owner session.

It wraps the whole application so it sees raw scopes — including WebSocket connects,
which is why auth can't live in a route dependency. Anything under ``/_rectify`` (the
editor's ws + overlay JS) requires a valid owner cookie; everything else passes
through to the inner app untouched.
"""

from __future__ import annotations

from .auth import is_owner_scope

GATED_PREFIX = "/_rectify"


class RectifyGate:
    def __init__(self, app, secret_key: str) -> None:
        self.app = app
        self.secret_key = secret_key

    async def __call__(self, scope, receive, send) -> None:
        scope_type = scope.get("type")
        path = scope.get("path", "")
        gated = scope_type in ("http", "websocket") and (
            path == GATED_PREFIX or path.startswith(GATED_PREFIX + "/")
        )

        if gated and not is_owner_scope(scope, self.secret_key):
            if scope_type == "websocket":
                await self._reject_ws(receive, send)
            else:
                await self._redirect_http(send)
            return

        await self.app(scope, receive, send)

    async def _redirect_http(self, send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 302,
                "headers": [(b"location", b"/login")],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    async def _reject_ws(self, receive, send) -> None:
        # Consume the connect event, then close without accepting. The browser fires
        # onclose; the overlay shows its disconnected state.
        await receive()
        await send({"type": "websocket.close", "code": 1008})
