"""edit_file multiple-occurrence handling — the 'multiple placeholders' headline.

A snippet (old_string) may appear zero, one, or many times. rectify only edits
when it can pin the change to exactly one place; otherwise it refuses and asks for
more context. These tests lock that contract down.
"""

from __future__ import annotations

from rectify import tools, workspace


def _write(root, name, text):
    (root / name).write_text(text, encoding="utf-8")
    return name


def test_single_exact_occurrence_is_replaced(bound_workspace):
    name = _write(bound_workspace, "a.html", "<h1>Hello</h1>\n<p>body</p>\n")
    out = tools.edit_file(name, "<h1>Hello</h1>", "<h1>Hi</h1>")
    assert "Edited a.html" in out
    assert (bound_workspace / name).read_text() == "<h1>Hi</h1>\n<p>body</p>\n"
    # the write is recorded for diff reporting / undo
    assert len(workspace.pending_changes) == 1
    assert workspace.pending_changes[0].diff


def test_multiple_exact_occurrences_refused(bound_workspace):
    name = _write(bound_workspace, "a.html", "<li>item</li>\n<li>item</li>\n<li>item</li>\n")
    out = tools.edit_file(name, "<li>item</li>", "<li>changed</li>")
    assert "appears 3 times" in out
    assert "add surrounding context" in out
    # file untouched, nothing recorded
    assert (bound_workspace / name).read_text().count("<li>item</li>") == 3
    assert workspace.pending_changes == []


def test_zero_exact_but_single_fuzzy_match_edits_and_preserves_indent(bound_workspace):
    # Real file is indented; the model supplies the snippet with different (wrong)
    # leading whitespace. Fuzzy matching should still land the edit once.
    name = _write(bound_workspace, "a.py", "def f():\n        return  1\n")
    out = tools.edit_file(name, "return 1", "return 2")
    assert "matched ignoring whitespace" in out
    after = (bound_workspace / name).read_text()
    assert "return 2" in after
    # the file's own indentation is preserved (model's guessed indent dropped)
    assert "\n        return 2\n" in after


def test_multiple_fuzzy_matches_refused(bound_workspace):
    # old_string is NOT an exact substring (double spaces), so the exact path is
    # skipped; whitespace-flexible matching then finds it in two places.
    name = _write(bound_workspace, "a.py", "call def foo () here\nand def foo () there\n")
    out = tools.edit_file(name, "def  foo  ()", "def bar()")
    assert "matches 2 places" in out
    assert "whitespace-insensitive" in out
    assert workspace.pending_changes == []


def test_not_found_at_all(bound_workspace):
    name = _write(bound_workspace, "a.html", "<h1>Hello</h1>\n")
    out = tools.edit_file(name, "completely-absent-text", "x")
    assert "not found" in out
    assert workspace.pending_changes == []


def test_noop_when_new_equals_existing(bound_workspace):
    name = _write(bound_workspace, "a.html", "<h1>Hello</h1>\n")
    out = tools.edit_file(name, "<h1>Hello</h1>", "<h1>Hello</h1>")
    assert "No change" in out
    assert workspace.pending_changes == []


def test_missing_file(bound_workspace):
    out = tools.edit_file("does-not-exist.html", "a", "b")
    assert "File not found" in out
