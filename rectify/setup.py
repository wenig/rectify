"""``setup`` subcommand: let the agent inject the overlay ``<script>`` tag.

Embedding the overlay normally means hand-pasting the snippet from the README into
your HTML before ``</body>``. Rather than guessing the entry file with heuristics,
this runs the same LLM agent (with the same file tools) and asks it to find the
project's main HTML document and insert the tag in the right place — so it works for
plain HTML and for whatever templating a framework uses.
"""

from __future__ import annotations

import textwrap

from . import workspace
from .agent import build_agent
from .config import Config


def _snippet(host: str, port: int) -> str:
    display_host = "localhost" if host in ("127.0.0.1", "0.0.0.0", "::1") else host
    return (
        "<!-- Rectify overlay (dev only). Served by the agent. -->\n"
        f'<script src="http://{display_host}:{port}/rectify.js" '
        f'data-rectify-endpoint="ws://{display_host}:{port}/ws"></script>'
    )


def _build_task(snippet: str) -> str:
    return textwrap.dedent(
        f"""\
        You are setting up the Rectify overlay in this project. Your only job
        is to insert the snippet below into the project's main HTML entry document —
        the HTML page a browser actually loads. Do not change anything else.

        Snippet to insert (verbatim, both lines):
        ```html
        {snippet}
        ```

        Steps:
        1. Find the entry HTML document with `list_files`/`grep`. Prefer a top-level
           or `public/` `index.html`; for a framework, the single root HTML template
           that contains a `<body>` (never a built file under `dist`/`build`).
        2. Read it. If it already loads `rectify.js`, change nothing and say so.
        3. Otherwise use `edit_file` to insert the snippet just before `</body>` (or
           before `</head>` if there is no body), matching the surrounding indentation.
        4. Finish with one sentence naming the file you changed.
        """
    )


def _step_text(step) -> str | None:
    for attr in ("model_output", "action_output", "observations"):
        val = getattr(step, attr, None)
        if isinstance(val, str) and val.strip():
            text = val.strip()
            return text if len(text) <= 800 else text[:800] + " …"
    err = getattr(step, "error", None)
    return f"⚠ {err}" if err else None


def run_setup(config: Config) -> int:
    """Have the agent inject the overlay tag into the project. Returns an exit code."""
    workspace.bind(config.root)
    workspace.take_pending()  # clear any leftover change log

    snippet = _snippet(config.host, config.port)
    print(f"Setting up the overlay in {config.root}")
    print(f"  model: {config.model_id}\n")

    agent = build_agent(config)
    try:
        for step in agent.run(_build_task(snippet), stream=True, reset=True):
            text = _step_text(step)
            if text:
                print(text)
    except Exception as exc:  # surface model/provider errors plainly
        print(f"\n✗ Agent failed: {exc}")
        return 1

    changes = workspace.take_pending()
    if not changes:
        print("\n✗ No file was changed (the overlay may already be installed, or no HTML was found).")
        return 1
    for c in changes:
        print(f"\n✓ Updated {c.path.relative_to(config.root)}")
    return 0
