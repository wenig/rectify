"""smolagents agent construction and per-request prompt assembly.

The agent is LLM-agnostic: the model is built from config via LiteLLM, so the same
code drives Anthropic, OpenAI, a local Ollama model, etc.
"""

from __future__ import annotations

import json
import textwrap

from smolagents import CodeAgent, LiteLLMModel

from .config import Config
from .tools import ALL_TOOLS

SYSTEM_INTRO = textwrap.dedent(
    """\
    You are Rectify, a coding agent that edits the SOURCE CODE of a website
    in response to a change a developer requested by selecting a region in their
    browser. You have file tools scoped to the project root.

    Your job each turn:
    1. Identify which source file(s) produced the selected DOM. Use `locate_source`
       with the visible text first, then `grep`/`list_files` to narrow down. The
       project may be plain HTML or any framework (React/Vue/Svelte/etc.) — find the
       file that contains the markup/text shown, not the built output.
    2. Read the relevant file(s) to understand the surrounding code.
    3. Make the smallest edit that satisfies the request, matching the existing code
       style. Prefer `edit_file` with a unique snippet; use `write_file` only for new
       files.
    4. Finish with a one or two sentence summary of what you changed and why.

    Never touch files outside the project. Do not run build steps. Keep changes minimal.
    """
)


# Cache the static system prompt (+ embedded tool docs) and the growing
# conversation prefix. LiteLLM applies these for Anthropic/Bedrock/Gemini and
# strips them for OpenAI/Ollama, so this stays provider-agnostic.
CACHE_CONTROL_INJECTION_POINTS = [
    {"location": "message", "role": "system"},
    {"location": "message", "index": -1},
]


def build_agent(config: Config) -> CodeAgent:
    model = LiteLLMModel(
        model_id=config.model_id,
        api_base=config.api_base,
        api_key=config.api_key,
        cache_control_injection_points=CACHE_CONTROL_INJECTION_POINTS,
    )
    agent = CodeAgent(
        tools=ALL_TOOLS,
        model=model,
        max_steps=12,
        additional_authorized_imports=["re", "json"],
    )
    return agent


def build_task(
    instruction: str,
    context: dict,
    attachments: list[dict] | None = None,
    first: bool = True,
) -> str:
    """Assemble the per-request task from the overlay's selection context.

    ``first`` controls whether the full system intro is prepended. On follow-up
    turns the agent already has the intro and prior turns in memory, so we send a
    lighter task and let it reference the conversation for context like "it".

    ``attachments`` is the list of files the developer uploaded with this request
    (``{name, path, url}`` each). They already live on disk under the project root
    and are served at their ``url``; the agent only needs the path/url to wire them
    into the source (e.g. an ``<img src="/uploads/…">``).
    """
    ctx = context or {}
    selector = ctx.get("selector") or "(unknown)"
    url = ctx.get("url") or "(unknown)"
    visible_text = (ctx.get("text") or "").strip()
    classes = ctx.get("classes") or ""
    tag = ctx.get("tag") or ""
    outer = (ctx.get("outerHTML") or "").strip()
    if len(outer) > 2500:
        outer = outer[:2500] + " …(truncated)"

    intro = (
        SYSTEM_INTRO
        if first
        else (
            "This is a follow-up request in the same session. Use the earlier turns "
            'for context (e.g. what "it" refers to and which files you already edited).'
        )
    )
    attach_section = ""
    if attachments:
        lines = [
            f"- {a.get('name') or a.get('path')}: project path `{a.get('path')}`, "
            f"served at `{a.get('url')}`"
            for a in attachments
        ]
        attach_section = (
            "## Files the developer attached with this request\n"
            "These are already saved under the project root and served at the URLs "
            "below. Reference them in the source as appropriate (e.g. an image goes in "
            'an `<img src="<url>">`). Do not try to recreate or move them.\n'
            + "\n".join(lines)
            + "\n\n"
        )

    return (
        f"{intro}\n\n"
        f"## The developer's request\n{instruction}\n\n"
        f"{attach_section}"
        f"## What they selected in the browser\n"
        f"- Page URL: {url}\n"
        f"- Element: <{tag}> selector `{selector}`\n"
        f"- CSS classes: {classes or '(none)'}\n"
        f"- Visible text:\n{json.dumps(visible_text)}\n"
        f"- Rendered HTML of the selection:\n```html\n{outer}\n```\n\n"
        f"Locate the source for this selection (if not already known), then make the change."
    )
