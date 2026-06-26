"""FastAPI app: serves the overlay script and a WebSocket the overlay talks to.

Per instruction the (synchronous) smolagents run is executed in a thread and its
steps are streamed back to the browser over the socket. Rectify only edits source
and exposes the overlay + socket; hosting the site is left to the user.
"""

from __future__ import annotations

import asyncio
import time
import traceback
from importlib.resources import files as resource_files

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from . import uploads, workspace
from .agent import build_agent, build_task
from .config import Config
from .origins import LOOPBACK_ORIGIN_RE, origin_allowed

try:
    OVERLAY_JS: str | None = (resource_files("rectify") / "overlay" / "rectify.js").read_text("utf-8")
except (FileNotFoundError, ModuleNotFoundError):
    OVERLAY_JS = None

# Idle lifetime of a kept agent session. A reload opens a new socket but reuses
# the same session id, so memory survives; abandoned sessions are swept after this.
SESSION_TTL_SECONDS = 30 * 60


def _format_step(step) -> str | None:
    """Best-effort short, human-readable text for a streamed agent step."""
    # Tool/code observations and model thoughts vary by smolagents version; pull
    # whatever printable fields exist.
    for attr in ("model_output", "action_output", "observations"):
        val = getattr(step, attr, None)
        if isinstance(val, str) and val.strip():
            text = val.strip()
            return text if len(text) <= 1200 else text[:1200] + " …"
    err = getattr(step, "error", None)
    if err:
        return f"⚠ {err}"
    return None


def _final_text(step) -> str:
    for attr in ("action_output", "final_answer", "output"):
        val = getattr(step, attr, None)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return str(step)


def create_app(config: Config) -> FastAPI:
    workspace.bind(config.root)
    app = FastAPI(title="Rectify Agent")

    # Agent sessions keyed by the client-supplied session id, so memory survives a
    # page reload (which drops the old socket and opens a new one with the same id).
    # Each holds {agent, turns, last_active, lock}; the lock serialises runs in case
    # an old and a reloaded socket briefly overlap on the same session.
    sessions: dict[str, dict] = {}

    def get_session(sid: str | None) -> dict:
        now = time.monotonic()
        for key in [k for k, v in sessions.items() if now - v["last_active"] > SESSION_TTL_SECONDS]:
            sessions.pop(key, None)
        if sid is not None:
            sess = sessions.get(sid)
            if sess is not None:
                sess["last_active"] = now
                return sess
        # New session for a fresh id (or an ephemeral one when no id was sent).
        sess = {"agent": build_agent(config), "turns": 0, "last_active": now, "lock": asyncio.Lock()}
        if sid is not None:
            sessions[sid] = sess
        return sess

    # Dev tool served on localhost while the site runs on another origin (e.g. the
    # Vite dev server). The server is unauthenticated, so we don't open it to *any*
    # origin — only loopback, same-origin, and any explicitly configured origins may
    # call the HTTP API (the WS does its own check below). See rectify.origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_origin_regex=LOOPBACK_ORIGIN_RE,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/rectify.js")
    def overlay_js():
        if OVERLAY_JS is not None:
            return Response(OVERLAY_JS, media_type="application/javascript")
        return JSONResponse({"error": "overlay not found"}, status_code=404)

    @app.get("/health")
    def health():
        return {"ok": True, "root": str(config.root), "model": config.model_id}

    # ---- uploads --------------------------------------------------------------
    # Files are saved under <root>/uploads/, which the platform's static host
    # already serves at /uploads/<name>. Under the platform these routes sit
    # behind the /_rectify mount and are owner-gated by RectifyGate.

    @app.post("/upload")
    async def upload(request: Request, name: str):
        data = await request.body()
        try:
            saved = uploads.save_upload(config.root, name, data)
        except uploads.UploadTooLarge as e:
            return JSONResponse({"error": str(e)}, status_code=413)
        except (ValueError, PermissionError) as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return saved

    @app.get("/uploads")
    def uploads_list():
        return {"files": uploads.list_uploads(config.root)}

    @app.delete("/upload")
    def upload_delete(name: str):
        try:
            removed = uploads.delete_upload(config.root, name)
        except (ValueError, PermissionError) as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return {"ok": removed}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        # The local server has no password, so reject cross-origin handshakes before
        # accepting: otherwise any site the developer visits could drive the agent
        # over this socket (cross-site WebSocket hijacking). See rectify.origins.
        if not origin_allowed(
            websocket.headers.get("origin"),
            websocket.headers.get("host"),
            config.allowed_origins,
        ):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        # Reuse the agent for this session id so earlier turns are remembered across
        # reloads; without an id the session is ephemeral (per-connection).
        session = get_session(websocket.query_params.get("sid"))
        try:
            while True:
                msg = await websocket.receive_json()
                kind = msg.get("type")
                if kind == "instruction":
                    await _run_instruction(websocket, config, session, msg)
                elif kind == "undo":
                    change = workspace.undo_last()
                    if change:
                        rel = change.path.relative_to(config.root)
                        await websocket.send_json({"type": "step", "message": f"Reverted {rel}"})
                        await websocket.send_json({"type": "done", "summary": f"Undid last change to {rel}"})
                    else:
                        await websocket.send_json({"type": "done", "summary": "Nothing to undo."})
                elif kind == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            return

    return app


async def _run_instruction(websocket: WebSocket, config: Config, session: dict, msg: dict) -> None:
    instruction = (msg.get("instruction") or "").strip()
    context = msg.get("context") or {}
    attachments = msg.get("attachments") or []
    if not instruction:
        await websocket.send_json({"type": "error", "message": "Empty instruction."})
        return

    # Guard against an old and a reloaded socket overlapping on the same session:
    # agent memory isn't safe for concurrent runs, so serialise them.
    async with session["lock"]:
        await _run_agent(websocket, config, session, instruction, context, attachments)


async def _run_agent(
    websocket: WebSocket,
    config: Config,
    session: dict,
    instruction: str,
    context: dict,
    attachments: list[dict],
) -> None:
    workspace.take_pending()  # clear any leftover change log
    agent = session["agent"]
    first = session["turns"] == 0
    session["turns"] += 1
    session["last_active"] = time.monotonic()
    task = build_task(instruction, context, attachments=attachments, first=first)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def run_agent():
        try:
            last = None
            # reset memory only on the first turn; keep history for follow-ups.
            for step in agent.run(task, stream=True, reset=first):
                loop.call_soon_threadsafe(queue.put_nowait, ("step", step))
                last = step
            loop.call_soon_threadsafe(queue.put_nowait, ("final", last))
        except Exception:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", traceback.format_exc()))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("__end__", None))

    loop.run_in_executor(None, run_agent)

    final_step = None
    while True:
        kind, item = await queue.get()
        if kind == "__end__":
            break
        if kind == "error":
            await websocket.send_json({"type": "error", "message": str(item)[-2000:]})
            continue
        if kind == "final":
            final_step = item
            continue
        text = _format_step(item)
        if text:
            await websocket.send_json({"type": "step", "message": text})

    changes = workspace.take_pending()
    diffs = "\n".join(c.diff for c in changes if c.diff)
    files = [str(c.path.relative_to(config.root)) for c in changes]
    # Report the ground truth (did any file change?), not just the model's claim,
    # which can be optimistic when an edit silently failed to match.
    if changes:
        summary = _final_text(final_step) if final_step is not None else "Done."
    else:
        summary = "No files were changed — the edit did not match. Try rephrasing or re-selecting."
    await websocket.send_json({
        "type": "done",
        "changed": bool(changes),
        "summary": summary,
        "diff": diffs,
        "files": files,
    })
