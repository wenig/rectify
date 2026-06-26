# Rectify

[![CI](https://github.com/wenig/rectify/actions/workflows/ci.yml/badge.svg)](https://github.com/wenig/rectify/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**Deploy a website you can edit by drawing on it.** Log in, draw a box over anything on
the live page, describe the change in plain words — Rectify edits the **actual source** and
the page updates. Self-hosted, single owner, no SaaS.

<!--
  ⬇️ Demo video. Replace the link below with a real recording of Rectify in action.
  GitHub renders an <img>/<video> or a linked thumbnail inline. Easiest options:
    1. Drag an .mp4/.gif into a GitHub issue or release, copy the user-content URL it
       generates, and paste it as the `src` of the <video> tag below, or
    2. Use a thumbnail image that links to a hosted video (YouTube/Loom):
       [![Watch the demo](docs/demo-thumbnail.png)](https://youtu.be/REPLACE_WITH_VIDEO_ID)
-->
<!--
  Demo embed is disabled until a real recording exists, so the README doesn't render a
  broken image. Drop a recording at `docs/demo.gif` (or swap in an uploaded video / YouTube
  link) and uncomment the block below to show the tool live.

<p align="center">
  <a href="https://youtu.be/REPLACE_WITH_VIDEO_ID">
    <img src="docs/demo.gif" alt="Rectify in action — draw a box, describe a change, watch the source update" width="720">
  </a>
</p>
-->

<!--
  ⬇️ Railway "Deploy" button.
  Replace REPLACE_WITH_TEMPLATE_CODE below with your real template code after you publish
  this repo as a template at https://railway.com/new → "Create Template". The code is the
  last path segment of your template URL: https://railway.com/template/<code>
-->
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template/REPLACE_WITH_TEMPLATE_CODE)

> **Note for the maintainer:** the button above points at a placeholder. Publish this repo as
> a Railway template once, then paste your `railway.com/template/<code>` URL into the link.

One click gives you a running site with a bundled starter page. Set `OWNER_PASSWORD`,
`LLM_MODEL_ID`, and `LLM_API_KEY`, attach a volume at `/site`, and you're live — log in and
start editing.

## How it works

```
 Browser overlay (owner-only)  ──ws──▶  In-process agent (smolagents)
   draw a box + describe edit            edits the source in SITE_DIR
```

- **Visitors see a clean, fast static site.** The editing overlay is never served to anyone
  but you — anonymous visitors get plain markup, nothing stamped onto the DOM.
- **You log in at `/login`** with your `OWNER_PASSWORD`, and the overlay appears.
- **Draw a rectangle over any element, type what should change.** The agent finds the source
  behind your selection by searching the codebase, edits the real file under `SITE_DIR`, and
  the page updates. Every change is reversible with **Undo**.
- **Works for plain HTML _and_ frameworks** (React/Vue/Svelte/…) — the agent locates the
  source rather than relying on a build plugin.
- **Ships with a starter site** seeded on first boot. Bring your own by mounting files into
  `SITE_DIR`.
- **LLM-agnostic** via [LiteLLM]: point it at Anthropic, OpenAI, or a local Ollama model with
  environment variables.

## One-click deploy on Railway

1. Click **Deploy on Railway** above.
2. Set the environment variables (see [Configuration](#configuration) for defaults and
   details):
   - `OWNER_PASSWORD` — **required.** The password you'll log in with.
   - `SECRET_KEY` — recommended. Set it so owner logins survive restarts (otherwise it's
     random per boot and you'll be logged out on redeploy).
   - `LLM_MODEL_ID` — the LiteLLM model id, e.g. `anthropic/claude-sonnet-4-6`,
     `openai/gpt-4o`, or `ollama/llama3`.
   - `LLM_API_KEY` — your provider key for that model.
   - `LLM_API_BASE` — custom API base URL, e.g. for a self-hosted or proxied endpoint.
   - `SITE_DIR` — served/edited directory; leave at `/site` to match the volume below.
   - `SESSION_MAX_AGE` — owner session lifetime in seconds (default 30 days).
   - `FORWARDED_ALLOW_IPS` — defaults to `*`, which suits Railway's TLS proxy.
   - `HOST` / `PORT` — leave unset; Railway injects `$PORT` and `0.0.0.0` is already the
     default bind address.
3. **Attach a volume mounted at `/site`** (the default `SITE_DIR`). Without it, your edits are
   lost when the container restarts.

Railway builds the bundled `Dockerfile`, starts `python -m rectify.platform`, and uses
`/_platform/health` as the health check — no extra config file needed.

## Deploy anywhere with Docker

The same image runs on any container host (Render, Fly, a VPS, your laptop):

```bash
docker build -t rectify .
docker run -e OWNER_PASSWORD=secret \
           -e SECRET_KEY="$(openssl rand -hex 32)" \
           -e LLM_MODEL_ID=anthropic/claude-sonnet-4-6 \
           -e LLM_API_KEY=sk-... \
           -e LLM_API_BASE= \
           -e SITE_DIR=/site \
           -e HOST=0.0.0.0 \
           -e PORT=8080 \
           -e SESSION_MAX_AGE=2592000 \
           -e FORWARDED_ALLOW_IPS='*' \
           -p 8080:8080 \
           -v "$PWD/site:/site" \
           rectify
```

Only `OWNER_PASSWORD` is required; every other line above shows a variable at its default so
you can see the full set and tweak what you need (see [Configuration](#configuration)). Set
`LLM_API_BASE` for an Ollama/proxied endpoint, or drop the line to leave it unset.

Open <http://localhost:8080>, click **Log in**, enter your password, and edit. The `-v` mount
keeps your site (and every edit) on disk across restarts.

## Run the platform locally (no Docker)

Install the package, then start the platform host directly:

```bash
uv pip install -e .   # or: pip install -e .

OWNER_PASSWORD=secret \
SECRET_KEY="$(openssl rand -hex 32)" \
LLM_MODEL_ID=anthropic/claude-sonnet-4-6 \
LLM_API_KEY=sk-... \
LLM_API_BASE= \
SITE_DIR=./site \
HOST=0.0.0.0 \
PORT=8080 \
SESSION_MAX_AGE=2592000 \
FORWARDED_ALLOW_IPS='*' \
python -m rectify.platform
```

Only `OWNER_PASSWORD` is required; the other variables are shown at their defaults so you can
see the full set and adjust what you need (see [Configuration](#configuration)). Leave
`LLM_API_BASE` empty unless you're pointing at Ollama or a proxied endpoint.

It listens on `0.0.0.0:8080`, seeds `./site` from the bundled starter on first boot, and
exposes a health check at `/_platform/health`. Open <http://localhost:8080> and log in.

## Configuration

All platform configuration comes from environment variables.

| Variable          | Default                       | Description                                                                          |
| ----------------- | ----------------------------- | ------------------------------------------------------------------------------------ |
| `OWNER_PASSWORD`  | *(required)*                  | Password to log in as the owner and enable editing. Missing → the server won't boot. |
| `SECRET_KEY`      | *(random per start)*          | Session signing key. Set it to keep owners logged in across restarts.                |
| `SITE_DIR`        | `/site`                       | Directory served and edited; seeded from the bundled starter if empty. Mount a persistent volume here. |
| `HOST`            | `0.0.0.0`                     | Bind address.                                                                        |
| `PORT`            | `8080`                        | Listen port. Railway/Render inject `$PORT`.                                          |
| `SESSION_MAX_AGE` | `2592000` (30 days)           | Owner session lifetime, in seconds.                                                  |
| `FORWARDED_ALLOW_IPS` | `*`                       | Client IPs trusted to set `X-Forwarded-*`. `*` suits Railway/Render (TLS proxy, dynamic IPs); narrow it if exposed directly to untrusted clients. |
| `LLM_MODEL_ID`    | `anthropic/claude-sonnet-4-6` | LiteLLM model id. Use `openai/gpt-4o`, `ollama/llama3`, etc.                          |
| `LLM_API_KEY`     | *(none)*                      | Provider API key.                                                                    |
| `LLM_API_BASE`    | *(none)*                      | Custom API base URL, e.g. `http://localhost:11434` for Ollama.                       |

**Routes**

| Method   | Path                | Description                                                              |
| -------- | ------------------- | ----------------------------------------------------------------------- |
| `GET`    | `/login`            | Owner login form. `POST` here with `password` to sign in.               |
| `GET`    | `/logout`           | Clear the owner session.                                                |
| `GET`    | `/_platform/health` | Health check — JSON `{ "ok": true, "site": <path> }`. Used by Railway.  |
| —        | `/{path}`           | Your site. The overlay is injected only for the logged-in owner.        |

## Safety

Editing is gated behind your `OWNER_PASSWORD` — the overlay and edit socket are never served
to anonymous visitors, who only ever see the published site. The agent can read and write
files **only** under `SITE_DIR`; any path outside it is refused. Every edit is recorded and
reversible with the **Undo** button. Login attempts are rate-limited per IP to blunt password
guessing — so choose a strong `OWNER_PASSWORD`. For production, set `SECRET_KEY` (so sessions
persist) and mount a volume at `SITE_DIR` (so edits persist).

---

## Optional: run just the agent locally

You don't need the platform. The core of Rectify is a local, dependency-light agent that edits
**your own project's source** from a browser overlay while you develop — no login, no hosting.
Run your site however you already do, run the agent pointed at the same directory, and edit by
drawing on the page.

Install it as a tool so `rectify` is on your `PATH` (the overlay ships inside the package):

```bash
uv tool install .      # or: pipx install .
```

Set a model + key, then run it in the directory it should edit:

```bash
export LLM_MODEL_ID=anthropic/claude-sonnet-4-6
export LLM_API_KEY=sk-...

cd /path/to/your/project
rectify                       # serves the overlay + WebSocket on 127.0.0.1:4242
```

Let the agent inject the overlay `<script>` tag into your entry HTML for you:

```bash
rectify setup
```

Or paste it yourself (before `</body>`):

```html
<script src="http://localhost:4242/rectify.js"
        data-rectify-endpoint="ws://localhost:4242/ws"
        data-rectify-reload></script>
```

Then open your site, click the **Rectify logo**, draw a box, and describe the change. For
frameworks with HMR (Vite/React) the change hot-swaps in place; for plain static sites add
`data-rectify-reload` so the page refreshes itself once the edit lands.

**Commands & flags**

| Command / flag    | Default       | Description                                                              |
| ----------------- | ------------- | ----------------------------------------------------------------------- |
| *(default run)*   | —             | Serve the overlay and open the WebSocket the overlay talks to.          |
| `setup`           | —             | Use the agent to inject the overlay `<script>` tag into your entry HTML. |
| `--root`          | `.`           | Project root the agent may read and edit. Paths outside are refused.    |
| `--host`          | `127.0.0.1`   | Interface the server binds to.                                          |
| `--port`          | `4242`        | Port the server listens on.                                             |
| `--model`         | `LLM_MODEL_ID`| Override the model for this run (a LiteLLM id).                          |
| `--allow-origin`  | —             | Extra browser origin allowed to connect (repeatable). See below.        |

The same `LLM_MODEL_ID` / `LLM_API_KEY` / `LLM_API_BASE` env vars apply. The agent serves
`/rectify.js`, a `/health` check, and the `/ws` WebSocket. This is a **development tool**: it
has **no password** — anyone who can reach the port can drive the agent — so keep it bound to
`127.0.0.1` and never expose the port or ship the overlay script to production.

To stop a malicious website you happen to visit from quietly opening the socket from your
browser (cross-site WebSocket hijacking), the agent only accepts connections whose `Origin`
is **loopback** (`localhost` / `127.0.0.1`, any port), **same-origin**, or one you list with
`--allow-origin` / `RECTIFY_ALLOWED_ORIGINS`. If your site is served from a non-localhost host
during development, add it, e.g. `rectify --allow-origin https://dev.myapp.test`.

## Contributing

Bug reports and focused pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md)
for development setup, the checks CI runs (`ruff`, `ty`, `pytest`), and how to submit a PR.

[LiteLLM]: https://github.com/BerriAI/litellm
[smolagents]: https://github.com/huggingface/smolagents
