# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_Nothing yet._

## [0.1.0]

Initial public release.

### Added

- **Self-hosted platform** (`python -m rectify.platform`) — a single-owner, password-gated
  host that serves a static site and live-edits its real source from a browser overlay.
- **Local agent** (`rectify`) — a dependency-light development tool that edits your own
  project's source from a browser overlay, with no login or hosting.
- **LLM-agnostic editing** via LiteLLM — point it at Anthropic, OpenAI, or a local Ollama
  model with environment variables.
- **Owner authentication** with signed sessions (`OWNER_PASSWORD`, `SECRET_KEY`,
  `SESSION_MAX_AGE`) and per-IP login rate limiting.
- **Sandboxed edits** restricted to `SITE_DIR`, with **Undo** for every change.
- **File uploads** support.
- **WebSocket origin checks** on the local agent to prevent cross-site WebSocket hijacking,
  configurable with `--allow-origin` / `RECTIFY_ALLOWED_ORIGINS`.
- **Deployment options**: bundled `Dockerfile` and `docker-compose.yml`, one-click Railway
  deploy, and direct local execution.
- **Bundled starter site** seeded on first boot.

[Unreleased]: https://github.com/wenig/rectify/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/wenig/rectify/releases/tag/v0.1.0
