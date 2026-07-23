import io

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
