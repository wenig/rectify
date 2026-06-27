"""build_task — the multi-variable prompt f-string (sense A)."""

from __future__ import annotations

import json

from rectify.agent import SYSTEM_INTRO, build_task


def _ctx(**over):
    base = {
        "selector": "div.hero > h1",
        "url": "http://localhost/",
        "text": "Welcome",
        "classes": "hero title",
        "tag": "h1",
        "outerHTML": "<h1 class='hero title'>Welcome</h1>",
    }
    base.update(over)
    return base


def test_first_turn_includes_intro_and_all_context_fields():
    out = build_task("make it blue", _ctx(), first=True)
    assert SYSTEM_INTRO.strip()[:20] in out
    assert "make it blue" in out
    assert "http://localhost/" in out
    assert "<h1> selector `div.hero > h1`" in out
    assert "hero title" in out
    assert json.dumps("Welcome") in out  # visible text is JSON-encoded
    assert "<h1 class='hero title'>Welcome</h1>" in out


def test_followup_turn_uses_lighter_intro():
    out = build_task("now bigger", _ctx(), first=False)
    assert "follow-up request" in out
    assert SYSTEM_INTRO not in out


def test_oversized_outerhtml_is_truncated_and_fence_closes():
    big = "<div>" + "x" * 5000 + "</div>"
    out = build_task("change", _ctx(outerHTML=big), first=True)
    assert "…(truncated)" in out
    # outer is sliced to 2500 chars total ("<div>" + 2495 x's) before the marker
    assert "x" * 2400 in out
    assert "x" * 4000 not in out
    # the ```html fence still opens and closes around the (truncated) block
    assert out.count("```html") == 1
    assert out.count("```") >= 2


def test_missing_context_values_fall_back():
    out = build_task("do it", _ctx(), first=True)
    assert "(none)" not in out  # sanity: classes present here

    out = build_task("do it", {}, first=True)
    assert "(unknown)" in out   # url + selector
    assert "(none)" in out      # classes


def test_attachments_render_path_and_url():
    attachments = [{"name": "logo.png", "path": "uploads/logo.png", "url": "/uploads/logo.png"}]
    out = build_task("put this here", _ctx(), attachments=attachments, first=True)
    assert "Files the developer attached" in out
    assert "uploads/logo.png" in out
    assert "/uploads/logo.png" in out


def test_no_attachment_section_when_none():
    out = build_task("change", _ctx(), first=True)
    assert "Files the developer attached" not in out
