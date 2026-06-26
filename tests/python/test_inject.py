"""site.inject (multiple </body>) plus overlay_tag and path helpers."""

from __future__ import annotations

from starlette.requests import Request

from rectify.platform import site


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "scheme": "http",
        "server": ("testserver", 80),
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


# ---- inject: multiple-occurrence (sense B) --------------------------------

def test_inject_single_body():
    out = site.inject("<html><body>hi</body></html>", "<TAG>")
    assert out == "<html><body>hi<TAG>\n</body></html>"


def test_inject_targets_the_last_body_when_multiple():
    html = "<body>one</body>\n<body>two</body>"
    out = site.inject(html, "<TAG>")
    # tag lands before the LAST </body>, the first is left intact
    assert out == "<body>one</body>\n<body>two<TAG>\n</body>"
    assert out.count("<TAG>") == 1


def test_inject_appends_when_no_body():
    out = site.inject("<p>no body here</p>", "<TAG>")
    assert out.endswith("<TAG>\n")
    assert "<p>no body here</p>" in out


# ---- overlay_tag: scheme/host resolution ----------------------------------

def test_overlay_tag_defaults_to_ws_and_host_header():
    tag = site.overlay_tag(_request({"host": "myhost:8080"}))
    assert 'src="/_rectify/rectify.js"' in tag
    assert 'data-rectify-endpoint="ws://myhost:8080/_rectify/ws"' in tag
    assert "data-rectify-reload" in tag


def test_overlay_tag_uses_wss_and_forwarded_host_behind_https():
    tag = site.overlay_tag(
        _request({"host": "internal:80", "x-forwarded-proto": "https", "x-forwarded-host": "site.app"})
    )
    assert 'data-rectify-endpoint="wss://site.app/_rectify/ws"' in tag


def test_overlay_tag_takes_first_proto_from_chain():
    tag = site.overlay_tag(_request({"host": "site.app", "x-forwarded-proto": "https, http"}))
    assert tag.count("wss://") == 1


# ---- safe_path / resolve_target -------------------------------------------

def test_safe_path_rejects_traversal(tmp_path):
    assert site.safe_path(tmp_path, "../etc/passwd") is None
    inside = site.safe_path(tmp_path, "sub/page.html")
    assert inside is not None and str(inside).startswith(str(tmp_path))


def test_resolve_target_directory_resolves_to_index(tmp_path):
    (tmp_path / "index.html").write_text("<h1>home</h1>")
    assert site.resolve_target(tmp_path, "/") == tmp_path / "index.html"


def test_resolve_target_missing_returns_none(tmp_path):
    assert site.resolve_target(tmp_path, "/nope.html") is None
