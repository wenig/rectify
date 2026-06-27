"""Saving, listing and deleting user-uploaded assets.

Uploads land in an ``uploads/`` folder under the workspace root (the served site
directory on the platform), so they are reachable at ``/uploads/<name>`` by the
static host the moment they're written — exactly what an ``<img src>`` needs. The
agent references them by path; the overlay manages them through the routes in
``server.py``.

Every function is a pure operation on a base directory so it can be unit tested
without a running server. Path safety mirrors ``workspace.resolve`` /
``site.safe_path``: names are sanitised to a single path component and resolved
writes/deletes are refused if they escape ``uploads/``.
"""

from __future__ import annotations

import re
from pathlib import Path

UPLOADS_DIR_NAME = "uploads"
MAX_UPLOAD_BYTES = 25_000_000  # 25 MB

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class UploadTooLarge(ValueError):
    """Raised when an upload exceeds :data:`MAX_UPLOAD_BYTES`."""


def uploads_dir(root: Path) -> Path:
    """Return (creating if needed) the uploads folder under ``root``."""
    d = Path(root) / UPLOADS_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_name(name: str) -> str:
    """Reduce an arbitrary filename to a single safe path component.

    Keeps only the basename, whitelists ``[A-Za-z0-9._-]`` (other runs collapse to
    ``-``), and refuses empty / ``.`` / ``..`` results.
    """
    base = Path(name or "").name  # strip any directory part
    cleaned = _SAFE_CHARS.sub("-", base).strip("-")
    if not cleaned or cleaned in {".", ".."} or set(cleaned) == {"."}:
        raise ValueError(f"unsafe upload name: {name!r}")
    return cleaned


def _unique_path(folder: Path, name: str) -> Path:
    """Pick a non-colliding path in ``folder`` by suffixing ``-1``, ``-2``, …"""
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    i = 1
    while True:
        candidate = folder / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def _record(root: Path, path: Path) -> dict:
    rel = path.relative_to(Path(root)).as_posix()
    return {
        "name": path.name,
        "path": rel,
        "url": "/" + rel,
        "size": path.stat().st_size,
    }


def save_upload(root: Path, name: str, data: bytes) -> dict:
    """Write ``data`` to a uniquely-named file under ``uploads/``.

    Returns ``{name, path, url, size}``. Raises :class:`UploadTooLarge` if the
    payload exceeds the size cap and :class:`ValueError` for an unsafe name.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadTooLarge(f"upload is {len(data)} bytes; limit is {MAX_UPLOAD_BYTES}")
    folder = uploads_dir(root)
    target = _unique_path(folder, safe_name(name))
    target.write_bytes(data)
    return _record(root, target)


def list_uploads(root: Path) -> list[dict]:
    """Return the files in ``uploads/`` (name-sorted), each ``{name, path, url, size}``."""
    folder = uploads_dir(root)
    files = [_record(root, p) for p in folder.iterdir() if p.is_file()]
    files.sort(key=lambda f: f["name"].lower())
    return files


def _resolve_in_uploads(root: Path, name: str) -> Path:
    """Resolve ``name`` strictly within ``uploads/``, refusing traversal."""
    folder = uploads_dir(root)
    target = (folder / safe_name(name)).resolve()
    try:
        target.relative_to(folder.resolve())
    except ValueError:
        raise PermissionError(f"path {name!r} is outside the uploads folder")
    return target


def delete_upload(root: Path, name: str) -> bool:
    """Delete a file from ``uploads/``. Returns whether a file was removed."""
    target = _resolve_in_uploads(root, name)
    if target.is_file():
        target.unlink()
        return True
    return False
