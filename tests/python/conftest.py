"""Shared fixtures for the Python test suite.

Tests are additive only — they import the installed ``rectify`` package
(including its ``rectify.platform`` host subpackage) and never modify package
source.
"""

from __future__ import annotations

import pytest

from rectify import workspace


@pytest.fixture
def bound_workspace(tmp_path):
    """Bind rectify's global workspace to a fresh temp dir and reset its change log.

    rectify's workspace state is module-global (a deliberate one-root-per-process
    design), so each test rebinds it and clears the pending/undo stacks to stay
    isolated.
    """
    workspace.bind(tmp_path)
    workspace.pending_changes.clear()
    workspace.undo_stack.clear()
    yield tmp_path
    workspace.pending_changes.clear()
    workspace.undo_stack.clear()
