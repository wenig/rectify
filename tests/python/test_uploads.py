"""uploads — save/list/delete of user-uploaded assets and path safety."""

from __future__ import annotations

import pytest

from rectify import uploads


def test_save_upload_writes_under_uploads_and_reports_url(tmp_path):
    rec = uploads.save_upload(tmp_path, "logo.png", b"img-bytes")
    saved = tmp_path / "uploads" / "logo.png"
    assert saved.read_bytes() == b"img-bytes"
    assert rec == {"name": "logo.png", "path": "uploads/logo.png",
                   "url": "/uploads/logo.png", "size": len(b"img-bytes")}


def test_save_upload_de_collides_names(tmp_path):
    uploads.save_upload(tmp_path, "a.txt", b"one")
    second = uploads.save_upload(tmp_path, "a.txt", b"two")
    assert second["name"] == "a-1.txt"
    assert (tmp_path / "uploads" / "a.txt").read_bytes() == b"one"
    assert (tmp_path / "uploads" / "a-1.txt").read_bytes() == b"two"


def test_save_upload_enforces_size_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", 4)
    with pytest.raises(uploads.UploadTooLarge):
        uploads.save_upload(tmp_path, "big.bin", b"toolong")
    assert not (tmp_path / "uploads" / "big.bin").exists()


def test_safe_name_strips_directories_and_rejects_traversal():
    assert uploads.safe_name("../../etc/passwd") == "passwd"
    assert uploads.safe_name("a b!c.png") == "a-b-c.png"
    for bad in ["", "..", "/", "..."]:
        with pytest.raises(ValueError):
            uploads.safe_name(bad)


def test_list_uploads_sorted(tmp_path):
    assert uploads.list_uploads(tmp_path) == []
    uploads.save_upload(tmp_path, "b.txt", b"b")
    uploads.save_upload(tmp_path, "A.txt", b"a")
    names = [f["name"] for f in uploads.list_uploads(tmp_path)]
    assert names == ["A.txt", "b.txt"]


def test_delete_upload_removes_file_and_reports(tmp_path):
    uploads.save_upload(tmp_path, "gone.txt", b"x")
    assert uploads.delete_upload(tmp_path, "gone.txt") is True
    assert not (tmp_path / "uploads" / "gone.txt").exists()
    # deleting again is a no-op, not an error
    assert uploads.delete_upload(tmp_path, "gone.txt") is False


def test_delete_upload_cannot_escape_uploads(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("keep me")
    # traversal is neutralised by safe_name (basename only), so nothing outside dies
    uploads.delete_upload(tmp_path, "../secret.txt")
    assert secret.exists()
