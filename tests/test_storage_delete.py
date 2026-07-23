import json
import os
import storage


def _save(out, prompt, now):
    return storage.save(b"\x89PNG", {"prompt": prompt, "size": "1024x1024",
                                     "quality": "low", "parent_id": None}, out, now=now)


def test_delete_removes_record_and_file(tmp_path):
    out = str(tmp_path)
    rec = _save(out, "cat", "2026-07-23T10:00:00")
    assert (tmp_path / rec["filename"]).exists()

    result = storage.delete(rec["id"], out)
    assert result is True
    assert not (tmp_path / rec["filename"]).exists()
    hist = json.loads((tmp_path / "history.json").read_text())
    assert all(r["id"] != rec["id"] for r in hist)


def test_delete_keeps_other_records(tmp_path):
    out = str(tmp_path)
    a = _save(out, "a", "2026-07-23T10:00:00")
    b = _save(out, "b", "2026-07-23T11:00:00")
    storage.delete(a["id"], out)
    remaining = [r["id"] for r in storage.list_history(out)]
    assert remaining == [b["id"]]
    assert (tmp_path / b["filename"]).exists()


def test_delete_unknown_returns_false(tmp_path):
    out = str(tmp_path)
    _save(out, "a", "2026-07-23T10:00:00")
    assert storage.delete("doesnotexist", out) is False
