"""Durability lives on the mounted volume; this only seeds it on first boot.

rectify writes files directly to ``SITE_DIR``. When that directory is a freshly
mounted (empty) volume, we copy in the bundled starter site so the host serves
something on the very first request. Persistence afterwards is the volume's job.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

log = logging.getLogger("rectify.platform")

# Entries the volume itself creates, which don't count as site content. ext4
# volumes — like Railway's persistent volumes — ship a lost+found directory, so a
# freshly mounted volume is never literally empty and would otherwise skip seeding.
_VOLUME_ARTIFACTS = {"lost+found"}


def _is_empty(path: Path) -> bool:
    if not path.exists():
        return True
    return all(child.name in _VOLUME_ARTIFACTS for child in path.iterdir())


def ensure_site(site_dir: Path, starter_dir: Path) -> None:
    """Create the site dir and seed it from the starter on first boot."""
    site_dir.mkdir(parents=True, exist_ok=True)

    if not _is_empty(site_dir):
        return

    if starter_dir.is_dir():
        shutil.copytree(starter_dir, site_dir, dirs_exist_ok=True)
        log.info("Seeded starter site into %s", site_dir)
    else:
        log.warning("Starter site %s not found; serving an empty site", starter_dir)
