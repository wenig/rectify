"""Runtime configuration, sourced from CLI args and environment variables.

The model is intentionally chosen at runtime so the backend stays LLM-agnostic:
any provider reachable through LiteLLM works by setting LLM_MODEL_ID / LLM_API_BASE
/ LLM_API_KEY (e.g. ``anthropic/claude-sonnet-4-6``, ``openai/gpt-4o``,
``ollama/llama3`` with ``LLM_API_BASE=http://localhost:11434``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .origins import parse_origins


@dataclass
class Config:
    root: Path
    """Project root the agent is allowed to read and edit. Hard boundary."""

    host: str = "127.0.0.1"
    port: int = 4242

    model_id: str = field(default_factory=lambda: os.environ.get("LLM_MODEL_ID", "anthropic/claude-sonnet-4-6"))
    api_base: str | None = field(default_factory=lambda: os.environ.get("LLM_API_BASE") or None)
    api_key: str | None = field(default_factory=lambda: os.environ.get("LLM_API_KEY") or None)

    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: parse_origins(os.environ.get("RECTIFY_ALLOWED_ORIGINS"))
    )
    """Extra browser origins allowed to reach the WS/HTTP API, on top of loopback and
    same-origin. The local server is otherwise unauthenticated, so this is the CSWSH
    boundary — see :mod:`rectify.origins`."""

    confirm_before_write: bool = False
    """Reserved for a future 'ask before applying' mode."""

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
