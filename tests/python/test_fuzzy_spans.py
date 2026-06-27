"""_fuzzy_spans — whitespace-flexible matching that can return multiple spans."""

from __future__ import annotations

from rectify import tools


def test_single_match_across_reflowed_whitespace():
    text = "a = foo(\n    1,\n    2,\n)\n"
    spans = tools._fuzzy_spans(text, "foo( 1, 2, )")
    assert len(spans) == 1


def test_broad_token_match_returns_multiple_spans():
    text = "def foo():\n    pass\n\ndef    foo():\n    pass\n"
    spans = tools._fuzzy_spans(text, "def foo()")
    assert len(spans) == 2


def test_empty_old_returns_no_spans():
    assert tools._fuzzy_spans("anything", "   ") == []


def test_regex_special_chars_are_escaped():
    # tokens with regex metacharacters must be matched literally, not as a pattern
    text = "value = a+b*c (literal)\n"
    spans = tools._fuzzy_spans(text, "a+b*c (literal)")
    assert len(spans) == 1
