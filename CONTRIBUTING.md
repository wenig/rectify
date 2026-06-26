# Contributing to Rectify

Thanks for taking the time to contribute! Rectify is a small, self-hosted project, and
bug reports, docs fixes, and focused pull requests are all welcome.

## Ground rules

- **Open an issue first for anything non-trivial.** A quick discussion saves you from
  building something that doesn't fit the project's "single owner, no SaaS" direction.
- **Keep pull requests focused.** One logical change per PR is far easier to review than a
  grab-bag of unrelated edits.
- **Match the surrounding code.** Follow the naming, comment density, and idioms already in
  the file you're editing rather than introducing a new style.
- **Be kind.** Assume good faith in reviews and issues.

## Development setup

Rectify uses [uv](https://github.com/astral-sh/uv) for dependency management. From a clone
of the repo:

```bash
uv sync --dev          # install runtime + dev dependencies into .venv
```

That gives you the same environment CI uses, including the dev tools (`ruff`, `ty`,
`pytest`).

### Running it locally

The platform host and the standalone agent are both documented in the
[README](README.md) — see **Run the platform locally (no Docker)** and **Optional: run just
the agent locally**. In short:

```bash
# Platform (serves + live-edits a site)
OWNER_PASSWORD=secret LLM_API_KEY=sk-... SITE_DIR=./site uv run python -m rectify.platform

# Just the agent, pointed at a project you're developing
uv run rectify --root /path/to/your/project
```

You'll need a model id and API key for any change that exercises the agent —
`LLM_MODEL_ID` / `LLM_API_KEY` / `LLM_API_BASE` (see **Configuration** in the README). Most
tests, however, run without a live model.

## Checks

Before opening a pull request, run the same three checks CI runs (see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml)). All three must pass:

```bash
uv run ruff check       # lint
uv run ty check         # type-check
uv run pytest           # tests
```

`ruff` can fix many lint findings for you:

```bash
uv run ruff check --fix
uv run ruff format        # apply formatting
```

## Tests

Tests live in [`tests/python/`](tests/python) and run with `pytest` (config in
[`pytest.ini`](pytest.ini)). Please:

- Add or update tests for any behavior change — there's good existing coverage for auth,
  origins, rate limiting, file edits, uploads, and the workspace, so use those as a model.
- Name files `test_*.py` so they're picked up.
- Keep tests fast and offline; don't depend on a real LLM or network.

Run a single file or test while iterating:

```bash
uv run pytest tests/python/test_auth.py
uv run pytest tests/python/test_auth.py -k some_case
```

## Submitting a pull request

1. Fork the repo and create a branch off `main`.
2. Make your change, with tests and a clear commit message describing *why*.
3. For user-facing changes, add a line under the `[Unreleased]` section of
   [CHANGELOG.md](CHANGELOG.md).
4. Run the three checks above and make sure they're green.
5. Open the PR against `main`. Describe what changed, the motivation, and anything a
   reviewer should pay special attention to (security-sensitive paths especially).

CI runs `ruff`, `ty`, and `pytest` on every pull request to `main`; a green run is required
before merge.

## Security

Rectify edits real source files and gates editing behind a password, so security matters.
If you find a vulnerability, **please don't open a public issue** — report it privately as
described in [SECURITY.md](SECURITY.md) so it can be fixed before disclosure. When
contributing, be especially careful with anything touching authentication, path handling
under `SITE_DIR`, allowed WebSocket origins, or rate limiting.

## License

By contributing, you agree that your contributions are licensed under the project's
[MIT License](LICENSE.md).
