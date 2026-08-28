import io
import json

from fastapi.testclient import TestClient
from PIL import Image

import app as appmod
import assets_store as astore


def _png(color=(200, 30, 30, 255), size=(48, 24)) -> bytes:
    im = Image.new("RGBA", size, color)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    return TestClient(appmod.app)


def test_upload_lists_and_serves(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
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


def test_upload_derives_name_from_filename_when_blank(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/assets/banners",
               files={"file": ("footer-bar.png", _png(), "image/png")})
    assert r.status_code == 200
    assert r.json()["asset"]["name"] == "footer-bar"


def test_upload_rejects_non_image(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/assets/logos",
               files={"file": ("bad.png", b"not really a png", "image/png")})
    assert r.status_code == 422


def test_unknown_kind_is_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/assets/evil").status_code == 404
    assert c.post("/api/assets/evil",
                  files={"file": ("x.png", _png(), "image/png")}).status_code == 404


def test_delete_removes_asset(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    rec = c.post("/api/assets/logos",
                 files={"file": ("l.png", _png(), "image/png")}).json()["asset"]
    assert c.delete(f"/api/assets/logos/{rec['id']}").status_code == 200
    assert c.get("/api/assets/logos").json()["items"] == []
    assert c.delete(f"/api/assets/logos/{rec['id']}").status_code == 404


def test_serve_rejects_traversal_and_manifest(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    c.post("/api/assets/logos", files={"file": ("l.png", _png(), "image/png")})
    # manifest dosyası servis edilmez
    assert c.get(f"/assets/logos/{astore.MANIFEST_FILE}").status_code == 404
    # bilinmeyen dosya
    assert c.get("/assets/logos/deadbeef.png").status_code == 404


def test_the_dead_uploads_kind_is_no_longer_a_route(tmp_path, monkeypatch):
    """`uploads` D9'da bir yükleme hedefiydi; artık ne hedef ne de tür.

    Bu test eskiden türe yükleyip listeliyordu. Tür ÖLÜ olduğu için (hedef ve
    sekme kaldırılmıştı, oraya düşen varlık hiçbir bindirmede kullanılamıyordu)
    şimdi kapının kendisi kapalı: uç 404. Eski varlıklar kaybolmuyor, açılışta
    `logos`a göçüyorlar — bekçisi tests/test_assets.py.
    """
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/assets/uploads",
                  files={"file": ("user_upload.png", _png(), "image/png")}
                  ).status_code == 404
    assert c.get("/api/assets/uploads").status_code == 404
    assert c.delete("/api/assets/uploads/deadbeef12ab").status_code == 404


def test_list_all_assets_combines_kinds(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
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


def test_a_legacy_upload_becomes_a_usable_logo_after_startup(tmp_path, monkeypatch):
    """Göç AÇILIŞTA gerçekten koşuyor ve varlık artık KULLANILABİLİR bir logo.

    `assets_store` tarafındaki birim testleri göçün kendisini ölçüyor; bu test
    onun lifespan'a BAĞLI olduğunu ölçüyor. İkisi ayrı: göç kusursuz yazılıp
    hiç çağrılmasaydı birim testleri yeşil kalır, kullanıcının varlığı ise
    ortadan kaybolurdu (tür artık listelenmiyor).
    """
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(appmod.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(appmod.paths, "ensure_data_dirs", lambda: None)
    _eski_uploads_dizini(tmp_path)

    with TestClient(appmod.app) as c:
        items = c.get("/api/assets/logos").json()["items"]
        assert [i["name"] for i in items] == ["D9'dan kalma"]
        # Asıl kazanç: bindirmenin okuduğu türde ve dosyası servis edilebiliyor.
        assert c.get(f"/assets/logos/{items[0]['filename']}").status_code == 200
    assert not (tmp_path / "assets" / "uploads").exists()


def test_the_version_backup_runs_before_the_migration(tmp_path, monkeypatch):
    """SIRA: yedek göçten ÖNCE — yedeğin göç ÖNCESİ hâli taşıması için.

    Göç, açılışın kullanıcı verisini yerinden oynatan tek adımı. Sıra ters
    olsaydı sürüm değişiminde alınan yedek zaten göçmüş hâli dondururdu ve
    geri dönülecek bir nokta kalmazdı — yani yedek tam da en çok gerektiği
    sürümde işe yaramaz olurdu.
    """
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(appmod.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(appmod.paths, "ensure_data_dirs", lambda: None)
    sira: list[str] = []
    monkeypatch.setattr(appmod.backup, "backup_manifests_if_version_changed",
                        lambda *a, **k: sira.append("yedek"))
    monkeypatch.setattr(appmod.assets_store, "migrate_legacy_uploads",
                        lambda *a, **k: sira.append("goc"))
    with TestClient(appmod.app):
        pass
    assert sira == ["yedek", "goc"]
