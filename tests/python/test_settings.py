"""Settings.from_env — provider-agnostic LLM_* mapping."""

from __future__ import annotations

import pytest

from rectify.platform.settings import ConfigError, Settings

# env vars the platform / rectify look at, cleared before each case
_LLM_ENV = ["LLM_API_KEY", "LLM_MODEL_ID", "LLM_API_BASE"]


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for k in _LLM_ENV:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OWNER_PASSWORD", "pw")
    monkeypatch.setenv("SECRET_KEY", "sk")
    monkeypatch.setenv("SITE_DIR", str(tmp_path))
    return monkeypatch


def test_llm_vars_populate_config(clean_env):
    clean_env.setenv("LLM_MODEL_ID", "openrouter/anthropic/claude-3.5-sonnet")
    clean_env.setenv("LLM_API_KEY", "sk-or-x")
    clean_env.setenv("LLM_API_BASE", "https://openrouter.ai/api/v1")
    cfg = Settings.from_env().rectify_config()
    assert cfg.model_id == "openrouter/anthropic/claude-3.5-sonnet"
    assert cfg.api_key == "sk-or-x"
    assert cfg.api_base == "https://openrouter.ai/api/v1"


def test_defaults_when_no_llm_vars(clean_env):
    cfg = Settings.from_env().rectify_config()
    # no LLM_* set: key/base unset, rectify's default model applies
    assert cfg.api_key is None
    assert cfg.model_id == "anthropic/claude-sonnet-4-6"
    assert cfg.api_base is None


def test_missing_owner_password_raises(clean_env):
    clean_env.delenv("OWNER_PASSWORD", raising=False)
    with pytest.raises(ConfigError):
        Settings.from_env()
