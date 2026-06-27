"""Platform host entry point.

Started via ``python -m rectify`` (the package main delegates here) or directly
with ``python -m rectify.platform``. This is what the container runs; the
``rectify`` console command (see ``rectify.cli``) is the local editor tool instead.
"""

from __future__ import annotations

import logging
import sys

import uvicorn

from .app import build_app
from .settings import ConfigError, Settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("rectify.platform")

    try:
        settings = Settings.from_env()
    except ConfigError as e:
        log.error("%s", e)
        sys.exit(1)

    log.info("Rectify Platform")
    log.info("  site:  %s", settings.site_dir)
    log.info("  model: %s", settings.rectify_config().model_id)
    log.info("  listening on %s:%s", settings.host, settings.port)

    app = build_app(settings)
    # proxy_headers + forwarded_allow_ips so request.url.scheme / forwarded headers
    # are trusted behind Railway's TLS terminator (used to pick ws vs wss).
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips=settings.forwarded_allow_ips,
        log_level="info",
    )


if __name__ == "__main__":
    main()
