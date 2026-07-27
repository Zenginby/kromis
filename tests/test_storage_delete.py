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


def test_delete_rejects_path_traversal(tmp_path):
    # output_subdir is nested one level under tmp_path; the sentinel file
    # sits in tmp_path itself (outside output_subdir). storage.delete always
    # appends ".png" to the id, so the traversal id must account for that
    # to actually reach the sentinel's real path/name.
    out_subdir = tmp_path / "output"
    out_subdir.mkdir()
    victim = tmp_path / "victim.png"
    victim.write_text("do not delete me")

    result = storage.delete("../victim", str(out_subdir))

    assert result is False
    assert victim.exists()
    assert victim.read_text() == "do not delete me"


def test_delete_rejects_slash_and_dots(tmp_path):
    out = str(tmp_path)
    assert storage.delete("a/b", out) is False
    assert storage.delete("..", out) is False
    assert storage.delete("evil.png", out) is False


def test_delete_survives_a_file_that_vanishes_mid_flight(tmp_path, monkeypatch):
    """`exists` ile `remove` arasında dosya kaybolursa 500 değil, normal silme.

    Yerel araç olsa da aynı görseli iki sekmeden silmek bunu tetikleyebiliyor.
    """
    out = str(tmp_path)
    rec = _save(out, "cat", "2026-07-23T10:00:00")
    real_remove = os.remove

    def racing_remove(path):
        real_remove(path)
        raise FileNotFoundError(path)  # sanki başka bir süreç önce silmiş

    monkeypatch.setattr(os, "remove", racing_remove)
    assert storage.delete(rec["id"], out) is True
    assert storage.delete_many([rec["id"]], out) == 0  # kayıt da dosya da gitti


def test_delete_many_survives_a_file_that_vanishes_mid_flight(tmp_path, monkeypatch):
    out = str(tmp_path)
    a = _save(out, "a", "2026-07-23T10:00:00")
    b = _save(out, "b", "2026-07-23T10:00:01")
    real_remove = os.remove

    def racing_remove(path):
        real_remove(path)
        raise FileNotFoundError(path)

    monkeypatch.setattr(os, "remove", racing_remove)
    assert storage.delete_many([a["id"], b["id"]], out) == 2
    assert json.loads((tmp_path / "history.json").read_text()) == []
