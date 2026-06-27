"""Rectify Platform — a thin self-hosted host that wraps the rectify editor.

It serves a static site, mounts rectify in-process so its overlay + WebSocket are
already running (no terminal), and injects the overlay only for the logged-in
owner. It reuses the editor modules from its parent ``rectify`` package
(``rectify.server``, ``rectify.config``) directly.
"""

__version__ = "0.1.0"
