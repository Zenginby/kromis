"""`/api/assets/{kind}` ve `/assets/{kind}/{filename}` — varlık kütüphanesi rotaları.

Kayıt `varliklar` satırı, dosya kullanıcının `assets_dir`inde (Faz 1 / 6):
test kullanıcısı gerçek satır, `db.oturum` bu dosyanın motoruna bağlı —
gerekçe tests/conftest.py::depo_db. `index.json` web yolunda hiç yazılmaz.
"""
import io
import json
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app as appmod

pytestmark = pytest.mark.usefixtures("depo_db")


def _png(color=(200, 30, 30, 255), size=(48, 24)) -> bytes:
    im = Image.new("RGBA", size, color)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _client(tmp_path, dizinler) -> TestClient:
    dizinler(assets_dir=str(tmp_path / "assets"))
    return TestClient(appmod.app)


def test_upload_lists_and_serves(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    r = c.post("/api/assets/logos",
               files={"file": ("mylogo.png", _png(), "image/png")},
               data={"name": "Kurumsal"})
    assert r.status_code == 200
    rec = r.json()["asset"]
    assert rec["name"] == "Kurumsal"
    assert rec["kind"] == "logos"

    items = c.get("/api/assets/logos").json()["items"]
    assert [i["id"] for i in items] == [rec["id"]]

    served = c.get(f"/assets/logos/{rec['filename']}")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    # Manifest YOK: dizinde yalnız dosya (Faz 1 / 6 çıkış ölçütü).
    assert sorted(os.listdir(tmp_path / "assets" / "logos")) == [rec["filename"]]


def test_upload_derives_name_from_filename_when_blank(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    r = c.post("/api/assets/banners",
               files={"file": ("footer-bar.png", _png(), "image/png")})
    assert r.status_code == 200
    assert r.json()["asset"]["name"] == "footer-bar"


def test_upload_rejects_non_image(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    r = c.post("/api/assets/logos",
               files={"file": ("bad.png", b"not really a png", "image/png")})
    assert r.status_code == 422


def test_unknown_kind_is_404(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    assert c.get("/api/assets/evil").status_code == 404
    assert c.post("/api/assets/evil",
                  files={"file": ("x.png", _png(), "image/png")}).status_code == 404


def test_delete_removes_asset(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    rec = c.post("/api/assets/logos",
                 files={"file": ("l.png", _png(), "image/png")}).json()["asset"]
    assert c.delete(f"/api/assets/logos/{rec['id']}").status_code == 200
    assert c.get("/api/assets/logos").json()["items"] == []
    assert c.delete(f"/api/assets/logos/{rec['id']}").status_code == 404


def test_serve_rejects_traversal_and_a_file_without_a_row(tmp_path, dizinler):
    """Servis yolunun gerçeği `varliklar` satırı: eski `index.json` adı da, diskte
    duran ama satırı olmayan bir dosya da 404 (`/output/{filename}` kararı)."""
    c = _client(tmp_path, dizinler)
    c.post("/api/assets/logos", files={"file": ("l.png", _png(), "image/png")})
    (tmp_path / "assets" / "logos" / "index.json").write_text("[]", encoding="utf-8")
    assert c.get("/assets/logos/index.json").status_code == 404
    (tmp_path / "assets" / "logos" / "deadbeef0000.png").write_bytes(_png())
    assert c.get("/assets/logos/deadbeef0000.png").status_code == 404
    assert c.get("/assets/logos/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_the_dead_uploads_kind_is_no_longer_a_route(tmp_path, dizinler):
    """`uploads` D9'da bir yükleme hedefiydi; artık ne hedef ne de tür.

    Bu test eskiden türe yükleyip listeliyordu. Tür ÖLÜ olduğu için (hedef ve
    sekme kaldırılmıştı, oraya düşen varlık hiçbir bindirmede kullanılamıyordu)
    şimdi kapının kendisi kapalı: uç 404. Eski varlıklar kaybolmuyor: içe
    aktarma aracı (8. görev) `assets_store.migrate_legacy_uploads` ile `logos`a
    taşıyor — bekçisi tests/test_assets.py; web yolu göçü ÇAĞIRMAZ (aşağıda).
    """
    c = _client(tmp_path, dizinler)
    assert c.post("/api/assets/uploads",
                  files={"file": ("user_upload.png", _png(), "image/png")}
                  ).status_code == 404
    assert c.get("/api/assets/uploads").status_code == 404
    assert c.delete("/api/assets/uploads/deadbeef12ab").status_code == 404


def test_list_all_assets_combines_kinds(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    r1 = c.post("/api/assets/logos", files={"file": ("l.png", _png(), "image/png")}).json()["asset"]
    r2 = c.post("/api/assets/mottos", files={"file": ("u.png", _png(), "image/png")}).json()["asset"]

    all_items = c.get("/api/assets/all").json()["items"]
    ids = [item["id"] for item in all_items]
    assert r1["id"] in ids
    assert r2["id"] in ids
    assert len(all_items) >= 2


def _eski_uploads_dizini(tmp_path):
    d = tmp_path / "assets" / "uploads"
    d.mkdir(parents=True)
    (d / "aaaaaaaa1111.png").write_bytes(_png())
    (d / "index.json").write_text(json.dumps([
        {"id": "aaaaaaaa1111", "filename": "aaaaaaaa1111.png",
         "name": "D9'dan kalma", "kind": "uploads",
         "created_at": "2026-01-01T10:00:00"}]), encoding="utf-8")


def test_startup_leaves_a_legacy_uploads_directory_alone(tmp_path, monkeypatch, dizinler):
    """Lifespan `migrate_legacy_uploads` ÇAĞIRMAZ (Faz 1 / 6): manifest okuyan tek
    yol içe aktarma aracı. Eski `uploads/` ağacı açılıştan sonra da yerinde ve
    kütüphane boş — göç web sürecinin işi değil, aracın işi.
    """
    dizinler(data_dir=str(tmp_path), output_dir=str(tmp_path / "output"),
             assets_dir=str(tmp_path / "assets"))
    monkeypatch.setattr(appmod.paths, "ensure_data_dirs", lambda *dizinler: None)
    _eski_uploads_dizini(tmp_path)

    with TestClient(appmod.app) as c:
        assert c.get("/api/assets/logos").json()["items"] == []
    assert (tmp_path / "assets" / "uploads" / "aaaaaaaa1111.png").is_file()
    assert (tmp_path / "assets" / "uploads" / "index.json").is_file()
    assert not (tmp_path / "assets" / "logos").exists()
