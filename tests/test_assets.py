import json

import pytest

import assets_store as astore


def test_save_writes_file_and_manifest(tmp_path):
    out = str(tmp_path)
    rec = astore.save_asset("logos", b"\x89PNG", "KURUM mavi", out,
                            now="2026-07-23T10:00:00")
    kind_dir = tmp_path / "logos"
    assert (kind_dir / rec["filename"]).read_bytes() == b"\x89PNG"
    assert rec["name"] == "KURUM mavi"
    assert rec["kind"] == "logos"
    assert rec["created_at"] == "2026-07-23T10:00:00"
    assert rec["id"] == rec["filename"].rsplit(".", 1)[0]
    manifest = json.loads((kind_dir / "index.json").read_text())
    assert manifest[0]["id"] == rec["id"]


def test_list_assets_newest_first(tmp_path):
    out = str(tmp_path)
    astore.save_asset("banners", b"a", "one", out, now="2026-07-23T10:00:00")
    astore.save_asset("banners", b"b", "two", out, now="2026-07-23T11:00:00")
    items = astore.list_assets("banners", out)
    assert [i["name"] for i in items] == ["two", "one"]


def test_list_assets_empty_when_no_dir(tmp_path):
    assert astore.list_assets("logos", str(tmp_path)) == []


def test_kinds_are_isolated(tmp_path):
    out = str(tmp_path)
    astore.save_asset("logos", b"L", "logo", out, now="2026-07-23T10:00:00")
    astore.save_asset("banners", b"B", "banner", out, now="2026-07-23T10:00:00")
    assert [i["name"] for i in astore.list_assets("logos", out)] == ["logo"]
    assert [i["name"] for i in astore.list_assets("banners", out)] == ["banner"]


def test_invalid_kind_rejected(tmp_path):
    with pytest.raises(ValueError):
        astore.save_asset("evil", b"x", "n", str(tmp_path), now="2026-07-23T10:00:00")
    with pytest.raises(ValueError):
        astore.list_assets("../secrets", str(tmp_path))


def test_asset_path_resolves_and_guards(tmp_path):
    out = str(tmp_path)
    rec = astore.save_asset("logos", b"\x89PNG", "x", out, now="2026-07-23T10:00:00")
    path = astore.asset_path("logos", rec["id"], out)
    assert path is not None and path.endswith(f"{rec['id']}.png")
    # unknown id and traversal attempts return None
    assert astore.asset_path("logos", "deadbeef", out) is None
    assert astore.asset_path("logos", "../../etc/passwd", out) is None


def test_delete_removes_file_and_manifest_entry(tmp_path):
    out = str(tmp_path)
    rec = astore.save_asset("logos", b"\x89PNG", "x", out, now="2026-07-23T10:00:00")
    assert astore.delete_asset("logos", rec["id"], out) is True
    assert not (tmp_path / "logos" / rec["filename"]).exists()
    assert astore.list_assets("logos", out) == []
    # deleting again is a no-op
    assert astore.delete_asset("logos", rec["id"], out) is False


def test_delete_rejects_bad_id(tmp_path):
    assert astore.delete_asset("logos", "../../etc/passwd", str(tmp_path)) is False


def test_manifest_tolerates_corrupt_file(tmp_path):
    kind_dir = tmp_path / "logos"
    kind_dir.mkdir()
    (kind_dir / "index.json").write_text("{not json")
    assert astore.list_assets("logos", str(tmp_path)) == []
