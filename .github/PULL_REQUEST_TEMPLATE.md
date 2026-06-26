<!-- Thanks for contributing to Rectify! Keep PRs focused — one logical change per PR. -->

## Summary

<!-- What does this change do, and why? Link any related issue (e.g. "Closes #12"). -->

## Motivation

<!-- The "why" behind the change — the problem it solves or the need it addresses. -->

## Checks

- [ ] `uv run ruff check` passes
- [ ] `uv run ty check` passes
- [ ] `uv run pytest` passes
- [ ] Added or updated tests for the behavior change (or explained why none are needed)

## Security-sensitive paths

<!-- If this touches authentication, path handling under SITE_DIR, allowed WebSocket
     origins, or rate limiting, call it out here so a reviewer pays extra attention. -->

- [ ] This PR does **not** touch security-sensitive code, **or** I've flagged what it changes above.
