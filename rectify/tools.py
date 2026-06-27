"""File tools exposed to the agent. All access is confined to the project root via
``workspace.resolve``. These are the only way the LLM can touch the codebase.

The set is deliberately small: locate, read, search, edit, write. ``locate_source``
is the framework-agnostic linchpin — it finds the source that produced a chunk of
rendered DOM by searching for the visible text and class names the overlay saw.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from smolagents import tool

from . import workspace

# Directories and files never worth searching or editing.
_IGNORE_DIRS = {".git", "node_modules", "dist", "build", ".next", ".svelte-kit", "__pycache__", ".venv"}
_TEXT_SUFFIXES = {
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".vue", ".svelte", ".astro",
    ".md", ".mdx", ".json", ".php", ".erb", ".ejs", ".hbs", ".njk", ".liquid",
}
_MAX_BYTES = 2_000_000


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _IGNORE_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def _is_texty(path: Path) -> bool:
    return path.suffix.lower() in _TEXT_SUFFIXES


@tool
def list_files(pattern: str = "*") -> str:
    """List source files in the project matching a glob pattern.

    Args:
        pattern: A glob like ``*.html`` or ``src/**/*.tsx``. Defaults to all files.
    """
    root = workspace.root()
    matches = []
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern):
            matches.append(rel)
    matches.sort()
    if not matches:
        return f"No files match {pattern!r}."
    return "\n".join(matches[:500])


@tool
def read_file(path: str) -> str:
    """Read a text file from the project, returned with 1-based line numbers.

    Args:
        path: Project-relative path to the file.
    """
    p = workspace.resolve(path)
    if not p.is_file():
        return f"File not found: {path}"
    if p.stat().st_size > _MAX_BYTES:
        return f"File too large to read: {path}"
    text = p.read_text(encoding="utf-8", errors="replace")
    return "\n".join(f"{i:>5}  {line}" for i, line in enumerate(text.splitlines(), 1))


@tool
def grep(pattern: str, glob: str = "*") -> str:
    """Search the project for a regular expression and return matching lines.

    Args:
        pattern: A Python regular expression to search for.
        glob: Optional glob to limit which files are searched (e.g. ``*.tsx``).
    """
    root = workspace.root()
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex: {e}"
    results: list[str] = []
    for path in _iter_files(root):
        if not _is_texty(path):
            continue
        rel = path.relative_to(root).as_posix()
        if not (fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(path.name, glob)):
            continue
        try:
            for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    results.append(f"{rel}:{n}: {line.strip()[:200]}")
                    if len(results) >= 200:
                        return "\n".join(results) + "\n... (truncated)"
        except OSError:
            continue
    return "\n".join(results) if results else f"No matches for {pattern!r}."


@tool
def locate_source(text: str) -> str:
    """Find source files likely responsible for a piece of rendered DOM.

    Searches for the given snippet of visible text or class names across the
    codebase. Use the visible text of the selected element first (most specific),
    then fall back to distinctive class names. Returns candidate file:line hits
    ranked by how many search terms each file matched.

    Args:
        text: Visible text and/or class names taken from the selected element.
    """
    root = workspace.root()
    # Build search terms: quoted phrases of visible text, plus individual tokens.
    raw_terms = re.split(r"[\n]+", text.strip())
    terms: list[str] = []
    for t in raw_terms:
        t = t.strip()
        if len(t) >= 3:
            terms.append(t)
        terms.extend(tok for tok in re.split(r"\s+", t) if len(tok) >= 4)
    terms = list(dict.fromkeys(terms))[:12]
    if not terms:
        return "No usable search terms; provide visible text or class names."

    file_hits: dict[str, dict] = {}
    for path in _iter_files(root):
        if not _is_texty(path):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = content.splitlines()
        matched_terms = set()
        sample_line = None
        for term in terms:
            for n, line in enumerate(lines, 1):
                if term.lower() in line.lower():
                    matched_terms.add(term)
                    if sample_line is None:
                        sample_line = f"{rel}:{n}: {line.strip()[:160]}"
                    break
        if matched_terms:
            file_hits[rel] = {"score": len(matched_terms), "sample": sample_line}

    if not file_hits:
        return f"No source found for terms: {terms}. Try grep with a single distinctive term."
    ranked = sorted(file_hits.items(), key=lambda kv: kv[1]["score"], reverse=True)
    out = ["Candidate source files (best first):"]
    for rel, info in ranked[:10]:
        out.append(f"  [{info['score']}/{len(terms)}] {info['sample'] or rel}")
    return "\n".join(out)


def _fuzzy_spans(text: str, old: str) -> list[re.Match]:
    """Find old in text ignoring differences in surrounding/interior whitespace.

    Models frequently guess indentation wrong, so when an exact match fails we
    match the non-whitespace content and let any run of whitespace flex.
    """
    tokens = [t for t in re.split(r"\s+", old.strip()) if t]
    if not tokens:
        return []
    pattern = r"\s+".join(re.escape(t) for t in tokens)
    return list(re.finditer(pattern, text))


@tool
def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Replace a snippet in a file. Matched exactly if possible, otherwise ignoring
    whitespace/indentation differences. The snippet must identify exactly one place.

    Args:
        path: Project-relative path to the file to edit.
        old_string: Text to replace. Indentation need not match exactly, but include
            enough surrounding content to be unique.
        new_string: Replacement text.
    """
    p = workspace.resolve(path)
    if not p.is_file():
        return f"File not found: {path}"
    before = p.read_text(encoding="utf-8")

    count = before.count(old_string)
    note = ""
    if count == 1:
        after = before.replace(old_string, new_string, 1)
    elif count > 1:
        return f"old_string appears {count} times in {path}; add surrounding context to make it unique."
    else:
        # Exact match failed — retry ignoring whitespace differences.
        spans = _fuzzy_spans(before, old_string)
        if not spans:
            return f"old_string not found in {path}. Read the file and copy the exact text."
        if len(spans) > 1:
            return f"old_string matches {len(spans)} places in {path} (whitespace-insensitive); add more context."
        span = spans[0]
        # Insert at the matched content position, dropping the model's guessed
        # leading indentation so the file's real indentation is preserved.
        after = before[: span.start()] + new_string.lstrip(" \t") + before[span.end():]
        note = " (matched ignoring whitespace)"

    if after == before:
        return f"No change: new_string is identical to existing text in {path}."
    p.write_text(after, encoding="utf-8")
    change = workspace.record_write(p, before, after)
    return f"Edited {path}{note}.\n{change.diff or '(no textual diff)'}"


@tool
def write_file(path: str, content: str) -> str:
    """Create a new file or overwrite an existing one with the given content.

    Args:
        path: Project-relative path to write.
        content: Full file contents.
    """
    p = workspace.resolve(path)
    before = p.read_text(encoding="utf-8") if p.is_file() else None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    workspace.record_write(p, before, content)
    verb = "Created" if before is None else "Overwrote"
    return f"{verb} {path} ({len(content)} bytes)."


ALL_TOOLS = [list_files, read_file, grep, locate_source, edit_file, write_file]
