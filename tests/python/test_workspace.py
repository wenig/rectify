"""workspace — path boundary, change recording, and undo."""

from __future__ import annotations

import pytest

from rectify import tools, workspace


def test_resolve_refuses_paths_outside_root(bound_workspace):
    with pytest.raises(PermissionError):
        workspace.resolve("../outside.txt")
    # a normal path resolves inside the root
    inside = workspace.resolve("sub/page.html")
    assert str(inside).startswith(str(bound_workspace))


def test_record_write_builds_diff_and_tracks(bound_workspace):
    (bound_workspace / "a.txt").write_text("one\n")
    tools.edit_file("a.txt", "one", "two")
    assert len(workspace.pending_changes) == 1
    change = workspace.pending_changes[0]
    assert "a/a.txt" in change.diff and "b/a.txt" in change.diff
    assert "-one" in change.diff and "+two" in change.diff


def test_undo_reverts_last_write(bound_workspace):
    (bound_workspace / "a.txt").write_text("original\n")
    tools.edit_file("a.txt", "original", "edited")
    assert (bound_workspace / "a.txt").read_text() == "edited\n"
    reverted = workspace.undo_last()
    assert reverted is not None
    assert (bound_workspace / "a.txt").read_text() == "original\n"


def test_undo_removes_created_file(bound_workspace):
    tools.write_file("new.txt", "fresh content")
    assert (bound_workspace / "new.txt").is_file()
    workspace.undo_last()
    assert not (bound_workspace / "new.txt").exists()


def test_undo_on_empty_stack_returns_none(bound_workspace):
    assert workspace.undo_last() is None
