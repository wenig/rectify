"""Shared workspace state: the path boundary plus change/undo tracking.

The smolagents tools are plain functions, so they read the active root from here.
``bind(root)`` is called once at startup. Every write is recorded so the most
recent edit can be undone from the chat.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

_root: Path | None = None


@dataclass
class Change:
    path: Path
    before: str | None  # None means the file did not exist before
    after: str
    diff: str


# Changes made during the current instruction (cleared by the server per run).
pending_changes: list[Change] = []

# Stack of changes available to undo, most recent last.
undo_stack: list[Change] = []


def bind(root: Path) -> None:
    global _root
    _root = Path(root).resolve()


def root() -> Path:
    if _root is None:
        raise RuntimeError("workspace root not bound; call workspace.bind(root) first")
    return _root


def resolve(rel_path: str) -> Path:
    """Resolve a user/agent supplied path and refuse anything outside the root."""
    p = (root() / rel_path).resolve()
    try:
        p.relative_to(root())
    except ValueError:
        raise PermissionError(f"path {rel_path!r} is outside the project root")
    return p


def record_write(path: Path, before: str | None, after: str) -> Change:
    diff = "".join(
        difflib.unified_diff(
            (before or "").splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path.relative_to(root())}",
            tofile=f"b/{path.relative_to(root())}",
        )
    )
    change = Change(path=path, before=before, after=after, diff=diff)
    pending_changes.append(change)
    undo_stack.append(change)
    return change


def take_pending() -> list[Change]:
    changes = list(pending_changes)
    pending_changes.clear()
    return changes


def undo_last() -> Change | None:
    """Revert the most recent write. Returns the change that was reverted."""
    if not undo_stack:
        return None
    change = undo_stack.pop()
    if change.before is None:
        change.path.unlink(missing_ok=True)
    else:
        change.path.write_text(change.before, encoding="utf-8")
    return change
