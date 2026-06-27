# Security Policy

Rectify edits real source files on disk and gates editing behind a password, so security
issues are taken seriously. Thanks for helping keep it and its users safe.

## Supported versions

Rectify is pre-1.0. Security fixes are made against the latest `0.1.x` release and `main`.

| Version | Supported |
| ------- | --------- |
| 0.1.x   | ✅        |
| < 0.1   | ❌        |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub's **"Report a vulnerability"** button under this repository's
[**Security** tab](https://github.com/wenig/rectify/security/advisories/new) (GitHub Security
Advisories). This keeps the report confidential until a fix is ready, and lets us collaborate
on a patch and coordinated disclosure.

Please include, where possible:

- the affected version or commit,
- the deployment mode (self-hosted platform, local agent, Docker, or Railway),
- steps to reproduce or a proof of concept,
- the impact you believe it has.

You can expect an initial acknowledgement within a few days. Once a fix is available we'll
publish an advisory and credit you if you'd like.

## Areas that are especially sensitive

If you're auditing the code, these paths handle the security-critical behavior:

- **Authentication** — owner login, session signing, and `SESSION_MAX_AGE`.
- **Path handling under `SITE_DIR`** — the agent must only read/write inside the configured
  site directory; any path escape is a vulnerability.
- **Allowed WebSocket origins** — the local agent rejects non-loopback / unlisted origins to
  prevent cross-site WebSocket hijacking.
- **Rate limiting** — login attempts are throttled per IP to blunt password guessing.

## Hardening reminders for operators

- Set a strong, unique `OWNER_PASSWORD`.
- Set `SECRET_KEY` in production so sessions can't be forged and survive restarts.
- Never expose the **local agent** (`rectify`) beyond `127.0.0.1` — it has no password.
