"""LOGIN_PAGE.format placeholders (sense A).

The template mixes a real {error} placeholder with escaped CSS braces {{ }}. These
tests ensure it renders in both states and guard against anyone adding an unescaped
{...} field that would KeyError at runtime.
"""

from __future__ import annotations

from string import Formatter

from rectify.platform.app import LOGIN_PAGE


def test_renders_with_empty_error():
    html = LOGIN_PAGE.format(error="")
    assert 'name="password"' in html
    # escaped CSS braces collapse to single braces in the output
    assert "body {" in html
    assert "{{" not in html and "}}" not in html


def test_renders_with_error_html():
    html = LOGIN_PAGE.format(error='<div class="err">Wrong password.</div>')
    assert "Wrong password." in html
    assert 'name="password"' in html


def test_only_field_is_error():
    # Guard: if someone adds another {field} without escaping, this catches it before
    # it becomes a runtime KeyError on the login page.
    fields = {name for _, name, _, _ in Formatter().parse(LOGIN_PAGE) if name}
    assert fields == {"error"}
