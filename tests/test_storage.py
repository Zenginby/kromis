import json
import storage


def test_save_writes_file_and_appends_history(tmp_path):
    out = str(tmp_path)
    rec = storage.save(b"\x89PNG", {"prompt": "cat", "size": "1024x1024",
                                    "quality": "medium", "parent_id": None},
                       out, now="2026-07-23T10:00:00")
    assert (tmp_path / rec["filename"]).read_bytes() == b"\x89PNG"
    assert rec["prompt"] == "cat"
    assert rec["created_at"] == "2026-07-23T10:00:00"
    assert rec["id"] == rec["filename"].rsplit(".", 1)[0]
    history = json.loads((tmp_path / "history.json").read_text())
    assert history[0]["id"] == rec["id"]


def test_list_history_newest_first(tmp_path):
    out = str(tmp_path)
    storage.save(b"a", {"prompt": "1", "size": "1024x1024", "quality": "low",
                        "parent_id": None}, out, now="2026-07-23T10:00:00")
    storage.save(b"b", {"prompt": "2", "size": "1024x1024", "quality": "low",
                        "parent_id": None}, out, now="2026-07-23T11:00:00")
    hist = storage.list_history(out)
    assert [h["prompt"] for h in hist] == ["2", "1"]


def test_list_history_empty_when_no_file(tmp_path):
    assert storage.list_history(str(tmp_path)) == []
