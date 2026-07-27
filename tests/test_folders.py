import io
import json

from fastapi.testclient import TestClient
from PIL import Image

import app as appmod
import assets_store as astore
import azure_client as ac
import folders
import storage


def _png(color=(30, 80, 200, 255), size=(64, 64)) -> bytes:
    b = io.BytesIO()
    Image.new("RGBA", size, color).save(b, "PNG")
    return b.getvalue()


def _fake_composite(cmd, capture_output, text):
    """test_logo._fake_run_factory ile aynı sözleşme: cmd[2]=girdi, cmd[3]=çıktı."""
    with open(cmd[2], "rb") as s, open(cmd[3], "wb") as d:
        d.write(s.read())

    class R:
        returncode = 0
        stderr = ""
    return R()


def _client(tmp_path, monkeypatch, *, real_png=False):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(ac, "generate",
                        lambda *a, **k: [_png(size=(256, 256)) if real_png else b"\x89PNG"])
    monkeypatch.setattr(ac, "edit", lambda *a, **k: [b"\x89PNG-edited"])
    return TestClient(appmod.app)


def _new_folder(c, name="Kurban"):
    r = c.post("/api/folders", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["folder"]["id"]


def _generate(c, folder_id=None, prompt="cat"):
    body = {"prompt": prompt, "size": "1024x1024", "quality": "low", "n": 1}
    if folder_id is not None:
        body["folder_id"] = folder_id
    return c.post("/api/generate", json=body)


# ── klasör CRUD ─────────────────────────────────────────────────────────
def test_create_and_list_folder(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c, "Kurban 2026")
    items = c.get("/api/folders").json()["items"]
    assert [f["id"] for f in items] == [fid]
    assert items[0]["name"] == "Kurban 2026"
    assert items[0]["count"] == 0


def test_folder_list_reports_image_count(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    for _ in range(3):
        assert _generate(c, fid).status_code == 200
    _generate(c)  # klasörsüz: sayıya girmemeli
    items = c.get("/api/folders").json()["items"]
    assert items[0]["count"] == 3


def test_create_folder_rejects_blank_name(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/folders", json={"name": ""}).status_code == 422
    assert c.post("/api/folders", json={"name": "   "}).status_code == 422


def test_create_folder_rejects_unknown_field(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/folders", json={"name": "x", "color": "red"})
    assert r.status_code == 422


# ── alt klasörler (parent_id) ───────────────────────────────────────────
def test_create_subfolder_records_parent(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    parent = _new_folder(c, "Kurban")
    r = c.post("/api/folders", json={"name": "Afiş", "parent_id": parent})
    assert r.status_code == 200, r.text
    child = r.json()["folder"]
    assert child["parent_id"] == parent

    items = {f["id"]: f for f in c.get("/api/folders").json()["items"]}
    assert items[child["id"]]["parent_id"] == parent
    assert items[parent]["parent_id"] is None       # kök klasör
    assert items[parent]["child_count"] == 1
    assert items[child["id"]]["child_count"] == 0


def test_create_subfolder_with_unknown_parent_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/folders", json={"name": "Afiş", "parent_id": "deadbeef0123"})
    assert r.status_code == 404


def test_subfolder_images_do_not_leak_into_parent(tmp_path, monkeypatch):
    """Ebeveynin içi yalnızca kendi görselleri; alt klasörünkiler ayrı kalır."""
    c = _client(tmp_path, monkeypatch)
    parent = _new_folder(c, "Kurban")
    child = c.post("/api/folders", json={"name": "Afiş", "parent_id": parent}).json()["folder"]["id"]
    in_parent = _generate(c, parent, prompt="ebeveyn").json()["images"][0]["id"]
    in_child = _generate(c, child, prompt="çocuk").json()["images"][0]["id"]

    assert [r["id"] for r in c.get(f"/api/history?folder_id={parent}").json()["images"]] == [in_parent]
    assert [r["id"] for r in c.get(f"/api/history?folder_id={child}").json()["images"]] == [in_child]
    items = {f["id"]: f for f in c.get("/api/folders").json()["items"]}
    assert items[parent]["count"] == 1 and items[child]["count"] == 1


def test_delete_parent_removes_subtree_and_unfiles_all_images(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    parent = _new_folder(c, "Kurban")
    child = c.post("/api/folders", json={"name": "Afiş", "parent_id": parent}).json()["folder"]["id"]
    keep = _new_folder(c, "Kalan")
    p_img = _generate(c, parent).json()["images"][0]
    c_img = _generate(c, child).json()["images"][0]

    r = c.delete(f"/api/folders/{parent}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["deleted"]) == {parent, child}
    assert body["folders"] == 2
    assert body["unfiled"] == 2

    assert [f["id"] for f in c.get("/api/folders").json()["items"]] == [keep]
    # görsellerin hiçbiri silinmedi, ikisi de kökte
    root_ids = [r["id"] for r in c.get("/api/history").json()["images"]]
    assert p_img["id"] in root_ids and c_img["id"] in root_ids
    for rec in (p_img, c_img):
        assert (tmp_path / "output" / rec["filename"]).exists()


def test_delete_deep_chain_removes_every_level(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    a = _new_folder(c, "A")
    b = c.post("/api/folders", json={"name": "B", "parent_id": a}).json()["folder"]["id"]
    d = c.post("/api/folders", json={"name": "D", "parent_id": b}).json()["folder"]["id"]

    body = c.delete(f"/api/folders/{a}").json()
    assert set(body["deleted"]) == {a, b, d}
    assert c.get("/api/folders").json()["items"] == []


def test_delete_subfolder_keeps_parent(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    parent = _new_folder(c, "Kurban")
    child = c.post("/api/folders", json={"name": "Afiş", "parent_id": parent}).json()["folder"]["id"]
    c.delete(f"/api/folders/{child}")
    items = c.get("/api/folders").json()["items"]
    assert [f["id"] for f in items] == [parent]
    assert items[0]["child_count"] == 0


# ── görselleri klasöre kaydetme ve filtreleme ──────────────────────────
def test_generate_into_folder_files_the_image(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    rec = _generate(c, fid).json()["images"][0]
    assert rec["folder_id"] == fid


def test_root_history_excludes_filed_images(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    filed = _generate(c, fid, prompt="klasörde").json()["images"][0]["id"]
    unfiled = _generate(c, prompt="kökte").json()["images"][0]["id"]

    root_ids = [r["id"] for r in c.get("/api/history").json()["images"]]
    assert root_ids == [unfiled]

    folder_ids = [r["id"] for r in c.get(f"/api/history?folder_id={fid}").json()["images"]]
    assert folder_ids == [filed]


def test_generate_with_unknown_folder_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert _generate(c, "deadbeef0123").status_code == 404


def test_history_with_unknown_folder_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/history?folder_id=deadbeef0123").status_code == 404


def test_edit_into_folder(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    r = c.post("/api/edit",
               data={"prompt": "x", "size": "1024x1024", "quality": "low",
                     "n": "1", "folder_id": fid},
               files={"file": ("in.png", _png(), "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["images"][0]["folder_id"] == fid


def test_edit_with_unknown_folder_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/edit",
               data={"prompt": "x", "size": "1024x1024", "quality": "low",
                     "n": "1", "folder_id": "deadbeef0123"},
               files={"file": ("in.png", _png(), "image/png")})
    assert r.status_code == 404


# ── türevler kaynağın klasörünü miras alır ─────────────────────────────
def test_logo_derivative_inherits_source_folder(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(appmod.subprocess, "run", _fake_composite)
    fid = _new_folder(c)
    src_id = _generate(c, fid).json()["images"][0]["id"]
    rec = c.post("/api/logo", json={"id": src_id}).json()["image"]
    assert rec["folder_id"] == fid
    # ve klasör görünümünde çıkar
    ids = [r["id"] for r in c.get(f"/api/history?folder_id={fid}").json()["images"]]
    assert rec["id"] in ids


def test_banner_derivative_inherits_source_folder(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch, real_png=True)
    fid = _new_folder(c)
    src_id = _generate(c, fid).json()["images"][0]["id"]
    banner = astore.save_asset("banners", _png(size=(400, 60)), "footer",
                               str(tmp_path / "assets"), now="2026-07-25T10:00:00")
    rec = c.post("/api/banner", json={"id": src_id, "asset_id": banner["id"]}).json()["image"]
    assert rec["folder_id"] == fid


# ── taşıma (sürükle-bırak ucu) ─────────────────────────────────────────
def test_move_unfiled_image_into_folder(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    rec = _generate(c).json()["images"][0]
    assert rec["folder_id"] is None

    r = c.patch(f"/api/image/{rec['id']}", json={"folder_id": fid})
    assert r.status_code == 200, r.text
    assert r.json()["folder_id"] == fid

    assert [x["id"] for x in c.get("/api/history").json()["images"]] == []
    assert [x["id"] for x in c.get(f"/api/history?folder_id={fid}").json()["images"]] == [rec["id"]]
    assert c.get("/api/folders").json()["items"][0]["count"] == 1


def test_move_image_out_of_folder_to_root(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    rec = _generate(c, fid).json()["images"][0]

    r = c.patch(f"/api/image/{rec['id']}", json={"folder_id": None})
    assert r.status_code == 200, r.text
    assert r.json()["folder_id"] is None
    assert [x["id"] for x in c.get("/api/history").json()["images"]] == [rec["id"]]


def test_move_image_between_folders(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    src, dst = _new_folder(c, "Kaynak"), _new_folder(c, "Hedef")
    rec = _generate(c, src).json()["images"][0]

    assert c.patch(f"/api/image/{rec['id']}", json={"folder_id": dst}).status_code == 200
    assert [x["id"] for x in c.get(f"/api/history?folder_id={src}").json()["images"]] == []
    assert [x["id"] for x in c.get(f"/api/history?folder_id={dst}").json()["images"]] == [rec["id"]]


def test_move_does_not_touch_the_file_or_provenance(tmp_path, monkeypatch):
    """Klasör yalnızca etiket: dosya adı/yolu ve parent_id değişmemeli."""
    c = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(appmod.subprocess, "run", _fake_composite)
    fid = _new_folder(c)
    src_id = _generate(c).json()["images"][0]["id"]
    derived = c.post("/api/logo", json={"id": src_id}).json()["image"]

    c.patch(f"/api/image/{derived['id']}", json={"folder_id": fid})
    moved = c.get(f"/api/history?folder_id={fid}").json()["images"][0]
    assert moved["filename"] == derived["filename"]
    assert moved["parent_id"] == src_id
    assert (tmp_path / "output" / derived["filename"]).exists()


def test_move_to_unknown_folder_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    rec = _generate(c).json()["images"][0]
    assert c.patch(f"/api/image/{rec['id']}", json={"folder_id": "deadbeef0123"}).status_code == 404


def test_move_unknown_image_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    assert c.patch("/api/image/aabbccddeeff", json={"folder_id": fid}).status_code == 404


def test_move_rejects_unknown_field(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    rec = _generate(c).json()["images"][0]
    r = c.patch(f"/api/image/{rec['id']}", json={"folder_id": None, "position": "top"})
    assert r.status_code == 422


# ── çoklu seçim: toplu taşıma ve toplu silme ───────────────────────────
def test_bulk_move_files_all_selected_images(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    ids = [_generate(c, prompt=f"g{i}").json()["images"][0]["id"] for i in range(3)]
    keep = _generate(c, prompt="kalan").json()["images"][0]["id"]

    r = c.patch("/api/images", json={"ids": ids, "folder_id": fid})
    assert r.status_code == 200, r.text
    assert r.json() == {"moved": 3, "folder_id": fid}

    in_folder = [x["id"] for x in c.get(f"/api/history?folder_id={fid}").json()["images"]]
    assert sorted(in_folder) == sorted(ids)
    assert [x["id"] for x in c.get("/api/history").json()["images"]] == [keep]


def test_bulk_move_to_root_with_null_folder(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    ids = [_generate(c, fid, prompt=f"g{i}").json()["images"][0]["id"] for i in range(2)]
    assert c.patch("/api/images", json={"ids": ids, "folder_id": None}).json()["moved"] == 2
    assert c.get(f"/api/history?folder_id={fid}").json()["images"] == []
    assert len(c.get("/api/history").json()["images"]) == 2


def test_bulk_move_counts_only_known_ids(tmp_path, monkeypatch):
    """Bilinmeyen id sessizce atlanır; sayı gerçekten taşınanı verir."""
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    real = _generate(c).json()["images"][0]["id"]
    r = c.patch("/api/images", json={"ids": [real, "aabbccddeeff"], "folder_id": fid})
    assert r.json()["moved"] == 1


def test_bulk_move_with_no_known_ids_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.patch("/api/images", json={"ids": ["aabbccddeeff"]}).status_code == 404


def test_bulk_move_to_unknown_folder_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    rec = _generate(c).json()["images"][0]
    r = c.patch("/api/images", json={"ids": [rec["id"]], "folder_id": "deadbeef0123"})
    assert r.status_code == 404


def test_bulk_endpoints_reject_empty_and_unknown_fields(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.patch("/api/images", json={"ids": []}).status_code == 422
    assert c.request("DELETE", "/api/images", json={"ids": []}).status_code == 422
    r = c.patch("/api/images", json={"ids": ["aabbccddeeff"], "folder": "x"})
    assert r.status_code == 422


def test_bulk_delete_removes_files_and_records(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    recs = [_generate(c, prompt=f"g{i}").json()["images"][0] for i in range(3)]
    keep = _generate(c, prompt="kalan").json()["images"][0]
    doomed = recs[:2]

    r = c.request("DELETE", "/api/images", json={"ids": [x["id"] for x in doomed]})
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": 2}

    left = [x["id"] for x in c.get("/api/history").json()["images"]]
    assert sorted(left) == sorted([recs[2]["id"], keep["id"]])
    for rec in doomed:
        assert not (tmp_path / "output" / rec["filename"]).exists()
    assert (tmp_path / "output" / recs[2]["filename"]).exists()


def test_bulk_delete_unknown_ids_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _generate(c)
    assert c.request("DELETE", "/api/images",
                     json={"ids": ["aabbccddeeff"]}).status_code == 404
    assert len(c.get("/api/history").json()["images"]) == 1


def test_bulk_delete_updates_folder_counts(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    ids = [_generate(c, fid, prompt=f"g{i}").json()["images"][0]["id"] for i in range(3)]
    c.request("DELETE", "/api/images", json={"ids": ids[:2]})
    items = c.get("/api/folders").json()["items"]
    assert items[0]["count"] == 1


def test_bulk_helpers_guard_bad_ids(tmp_path, monkeypatch):
    out = str(tmp_path / "output")
    storage.save(b"\x89PNG", {"prompt": "x"}, out, now="2026-07-25T10:00:00")
    for bad in ("../../etc/passwd", "not-hex", ""):
        assert storage.set_folder_many([bad], None, out) == 0
        assert storage.delete_many([bad], out) == 0
    assert len(storage.list_history(out)) == 1


def test_set_folder_guards_bad_image_id(tmp_path, monkeypatch):
    out = str(tmp_path / "output")
    storage.save(b"\x89PNG", {"prompt": "x"}, out, now="2026-07-25T10:00:00")
    for bad in ("../../etc/passwd", "not-hex", ""):
        assert storage.set_folder(bad, None, out) is False


# ── klasör silme: görseller silinmez, köke döner ───────────────────────
def test_delete_folder_unfiles_images_without_deleting_them(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c)
    rec = _generate(c, fid).json()["images"][0]

    r = c.delete(f"/api/folders/{fid}")
    assert r.status_code == 200, r.text
    assert r.json()["unfiled"] == 1

    assert c.get("/api/folders").json()["items"] == []
    # dosya yerinde ve görsel artık kökte
    assert (tmp_path / "output" / rec["filename"]).exists()
    root_ids = [x["id"] for x in c.get("/api/history").json()["images"]]
    assert rec["id"] in root_ids


def test_delete_unknown_folder_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.delete("/api/folders/deadbeef0123").status_code == 404


def test_delete_folder_leaves_other_folders_intact(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    keep = _new_folder(c, "Kalan")
    drop = _new_folder(c, "Silinen")
    kept_img = _generate(c, keep).json()["images"][0]["id"]
    c.delete(f"/api/folders/{drop}")
    items = c.get("/api/folders").json()["items"]
    assert [f["id"] for f in items] == [keep]
    ids = [r["id"] for r in c.get(f"/api/history?folder_id={keep}").json()["images"]]
    assert ids == [kept_img]


# ── geriye uyum ve dayanıklılık ────────────────────────────────────────
def test_legacy_records_without_folder_id_are_treated_as_root(tmp_path, monkeypatch):
    """v1.5 öncesi kayıtlarda folder_id alanı hiç yok — kök kabul edilmeli."""
    out = tmp_path / "output"
    out.mkdir(parents=True)
    (out / "history.json").write_text(json.dumps([
        {"id": "aabbccddeeff", "filename": "aabbccddeeff.png", "prompt": "eski",
         "size": "1024x1024", "quality": "low", "created_at": "2026-07-01T10:00:00",
         "parent_id": None},
    ]), encoding="utf-8")
    c = _client(tmp_path, monkeypatch)
    ids = [r["id"] for r in c.get("/api/history").json()["images"]]
    assert ids == ["aabbccddeeff"]


def test_legacy_folders_without_parent_id_are_treated_as_root(tmp_path, monkeypatch):
    """v1.6 kayıtlarında parent_id alanı hiç yok — kök klasör kabul edilmeli (migration yok)."""
    out = tmp_path / "output"
    out.mkdir(parents=True)
    (out / "folders.json").write_text(json.dumps([
        {"id": "aabbccddeeff", "name": "Eski klasör", "created_at": "2026-07-25T10:00:00"},
    ]), encoding="utf-8")
    c = _client(tmp_path, monkeypatch)
    items = c.get("/api/folders").json()["items"]
    assert items[0]["parent_id"] is None
    assert items[0]["child_count"] == 0
    # eski klasör hâlâ hedef alınabiliyor ve silinebiliyor
    assert _generate(c, "aabbccddeeff").status_code == 200
    assert c.delete("/api/folders/aabbccddeeff").json()["unfiled"] == 1


def test_corrupt_folders_file_is_tolerated(tmp_path, monkeypatch):
    out = tmp_path / "output"
    out.mkdir(parents=True)
    (out / "folders.json").write_text("{bozuk", encoding="utf-8")
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/folders").json()["items"] == []


def test_folder_id_format_guard(tmp_path, monkeypatch):
    """Hex olmayan id hiçbir zaman var sayılmamalı (storage._SAFE_ID ile aynı guard)."""
    c = _client(tmp_path, monkeypatch)
    _new_folder(c)
    for bad in ("../../etc", "not-hex", ""):
        assert not folders.exists(bad, str(tmp_path / "output"))
    assert _generate(c, "../../etc").status_code == 404


def test_unfile_folder_returns_zero_when_nothing_matches(tmp_path, monkeypatch):
    out = str(tmp_path / "output")
    storage.save(b"\x89PNG", {"prompt": "x", "folder_id": None}, out, now="2026-07-25T10:00:00")
    assert storage.unfile_folder("aabbccddeeff", out) == 0


def test_descendants_of_unknown_folder_is_empty(tmp_path, monkeypatch):
    out = str(tmp_path / "output")
    folders.create("A", out, now="2026-07-25T10:00:00")
    assert folders.descendants("deadbeef0123", out) == []
    assert folders.delete_tree("deadbeef0123", out) == []
    assert len(folders.list_folders(out)) == 1


# ── İç içe klasör derinliği ─────────────────────────────────────────────────

def test_folder_nesting_is_capped(tmp_path, monkeypatch):
    """Sınırsız derinlik başlık şeridini taşırıyor ve geri dönüşü zorlaştırıyor."""
    c = _client(tmp_path, monkeypatch)
    parent = None
    for level in range(appmod.MAX_FOLDER_DEPTH):
        r = c.post("/api/folders", json={"name": f"k{level}", "parent_id": parent})
        assert r.status_code == 200, (level, r.text)
        parent = r.json()["folder"]["id"]
    r = c.post("/api/folders", json={"name": "bir fazla", "parent_id": parent})
    assert r.status_code == 422, r.text
    assert str(appmod.MAX_FOLDER_DEPTH) in r.json()["detail"]


def test_depth_of_a_root_folder_is_one(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    root = _new_folder(c)
    child = c.post("/api/folders", json={"name": "alt", "parent_id": root}
                   ).json()["folder"]["id"]
    out = str(tmp_path / "output")
    assert folders.depth(root, out) == 1
    assert folders.depth(child, out) == 2
    assert folders.depth("yoksa", out) == 0


def test_depth_survives_a_broken_parent_chain(tmp_path, monkeypatch):
    """Elle bozulmuş folders.json sonsuz döngüye düşürmemeli (descendants ile aynı duruş)."""
    c = _client(tmp_path, monkeypatch)
    root = _new_folder(c)
    out = str(tmp_path / "output")
    path = tmp_path / "output" / "folders.json"
    items = json.loads(path.read_text())
    items[0]["parent_id"] = items[0]["id"]  # kendi kendinin ebeveyni
    path.write_text(json.dumps(items), encoding="utf-8")
    assert folders.depth(root, out) >= 1  # dönmeli, asılmamalı
