"""Runtime configuration for the platform, sourced entirely from env vars.

A deployment is configured through the Railway/Render deploy wizard, so everything
lives in the environment. ``OWNER_PASSWORD`` is the only hard requirement.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import overload

from rectify.config import Config

log = logging.getLogger("rectify.platform")


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


@overload
def _env(name: str, default: str) -> str: ...
@overload
def _env(name: str, default: None = None) -> str | None: ...
def _env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    return val


@dataclass
class Settings:
    site_dir: Path
    host: str
    port: int
    owner_password: str
    secret_key: str
    session_max_age: int
    forwarded_allow_ips: str = "*"
    model_id: str | None = field(default=None)
    api_key: str | None = field(default=None)
    api_base: str | None = field(default=None)

    @classmethod
    def from_env(cls) -> "Settings":
        owner_password = _env("OWNER_PASSWORD")
        if not owner_password:
            raise ConfigError(
                "OWNER_PASSWORD is required. Set it in your deploy environment so you "
                "can log in to edit the site."
            )

        secret_key = _env("SECRET_KEY")
        if not secret_key:
            secret_key = secrets.token_urlsafe(32)
            log.warning(
                "SECRET_KEY not set — generated a random one. Sessions will reset on "
                "every restart. Set SECRET_KEY to keep owners logged in across restarts."
            )

        return cls(
            site_dir=Path(_env("SITE_DIR", "/site")).resolve(),
            host=_env("HOST", "0.0.0.0"),
            # Railway/Render inject $PORT; fall back for local runs.
            port=int(_env("PORT", "8080")),
            owner_password=owner_password,
            secret_key=secret_key,
            session_max_age=int(_env("SESSION_MAX_AGE", str(60 * 60 * 24 * 30))),
            # Which client IPs may set X-Forwarded-* (used to detect HTTPS for the
            # Secure cookie + ws/wss). Defaults to "*" because Railway/Render terminate
            # TLS at a proxy with non-fixed IPs; narrow this (e.g. to the proxy's CIDR)
            # for any deployment exposed directly to untrusted clients.
            forwarded_allow_ips=_env("FORWARDED_ALLOW_IPS", "*"),
            # Provider-agnostic LLM config (works with Anthropic, OpenRouter, OpenAI,
            # or any LiteLLM provider).
            model_id=_env("LLM_MODEL_ID"),
            api_key=_env("LLM_API_KEY"),
            api_base=_env("LLM_API_BASE"),
        )

    def rectify_config(self) -> Config:
        """Build the rectify Config the mounted editor runs with.

        We map the platform's LLM_* env vars onto rectify's Config fields. Each is set
        only when present, so unset values fall back to rectify's own defaults
        (model_id → anthropic/claude-sonnet-4-6). Only the root is always pinned to the
        served site directory.
        """
        cfg = Config(root=self.site_dir)
        if self.model_id:
            cfg.model_id = self.model_id
        if self.api_key:
            cfg.api_key = self.api_key
        if self.api_base:
            cfg.api_base = self.api_base
        return cfg
