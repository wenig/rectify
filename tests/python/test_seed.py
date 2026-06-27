"""seed.ensure_site — first-boot seeding of the mounted site volume."""

from __future__ import annotations

from pathlib import Path

import pytest

from rectify.platform import seed


@pytest.fixture
def starter(tmp_path) -> Path:
    src = tmp_path / "starter"
    src.mkdir()
    (src / "index.html").write_text("<h1>hi</h1>", "utf-8")
    return src


def test_seeds_fresh_dir(tmp_path, starter):
    site = tmp_path / "site"
    seed.ensure_site(site, starter)
    assert (site / "index.html").read_text("utf-8") == "<h1>hi</h1>"


def test_seeds_when_only_lost_and_found(tmp_path, starter):
    # ext4 volumes (e.g. Railway) ship a lost+found dir, so the mount is never
    # literally empty — it must still be seeded.
    site = tmp_path / "site"
    (site / "lost+found").mkdir(parents=True)
    seed.ensure_site(site, starter)
    assert (site / "index.html").read_text("utf-8") == "<h1>hi</h1>"


def test_does_not_overwrite_existing_content(tmp_path, starter):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<h1>mine</h1>", "utf-8")
    seed.ensure_site(site, starter)
    assert (site / "index.html").read_text("utf-8") == "<h1>mine</h1>"


def test_missing_starter_leaves_empty_site(tmp_path):
    site = tmp_path / "site"
    seed.ensure_site(site, tmp_path / "nope")
    assert site.is_dir()
    assert not any(site.iterdir())
