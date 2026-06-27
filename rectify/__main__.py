"""Package entry point for the editor CLI.

Both ``python -m rectify`` and the ``rectify`` console command run this. The
self-hosted platform host has its own main — ``python -m rectify.platform``
(see ``rectify.platform.__main__``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

from .config import Config
from .server import create_app
from .setup import run_setup


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rectify",
        description="Local agent that edits website source from browser selections.",
    )
    parser.add_argument("--root", default=".", help="Project root the agent may edit (default: cwd).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4242)
    parser.add_argument("--model", default=None, help="Override LLM_MODEL_ID (e.g. anthropic/claude-sonnet-4-6).")
    parser.add_argument(
        "--allow-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help="Extra browser origin allowed to connect (loopback and same-origin are "
        "always allowed). Repeatable. Use when your site isn't served from localhost.",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser(
        "setup",
        help="Let the agent inject the overlay <script> tag into your project's entry HTML.",
    )

    args = parser.parse_args()

    config = Config(
        root=Path(args.root),
        host=args.host,
        port=args.port,
    )
    if args.model:
        config.model_id = args.model
    if args.allow_origin:
        config.allowed_origins = tuple(config.allowed_origins) + tuple(args.allow_origin)

    if args.command == "setup":
        sys.exit(run_setup(config))

    print("Rectify agent")
    print(f"  root:  {config.root}")
    print(f"  model: {config.model_id}")
    print(f"  websocket: ws://{config.host}:{config.port}/ws")

    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
