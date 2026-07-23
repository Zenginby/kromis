import io

from fastapi.testclient import TestClient
from PIL import Image

import app as appmod
import assets_store as astore
import azure_client as ac


def _png(color=(30, 80, 200, 255), size=(64, 64)) -> bytes:
    im = Image.new("RGBA", size, color)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    # gerçek PNG üret ki PIL banner bindirmesi çalışsın
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [_png(size=(256, 256))])
    c = TestClient(appmod.app)
    src_id = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                           "quality": "medium", "n": 1}).json()["images"][0]["id"]
    banner = astore.save_asset("banners", _png(size=(400, 60)), "footer",
                               str(tmp_path / "assets"), now="2026-07-23T10:00:00")
    return c, src_id, banner["id"]


def test_banner_preview_returns_data_url_and_does_not_save(tmp_path, monkeypatch):
    c, src_id, banner_id = _setup(tmp_path, monkeypatch)
    before = len(c.get("/api/history").json()["images"])
    r = c.post("/api/banner/preview", json={"id": src_id, "asset_id": banner_id, "edge": "top"})
    assert r.status_code == 200
    assert r.json()["b64"].startswith("data:image/png;base64,")
    after = len(c.get("/api/history").json()["images"])
    assert after == before


def test_banner_apply_creates_derivative(tmp_path, monkeypatch):
    c, src_id, banner_id = _setup(tmp_path, monkeypatch)
    r = c.post("/api/banner", json={"id": src_id, "asset_id": banner_id})
    assert r.status_code == 200
    rec = r.json()["image"]
    assert rec["parent_id"] == src_id
    assert (tmp_path / "output" / rec["filename"]).exists()


def test_banner_rejects_bad_edge(tmp_path, monkeypatch):
    c, src_id, banner_id = _setup(tmp_path, monkeypatch)
    r = c.post("/api/banner", json={"id": src_id, "asset_id": banner_id, "edge": "middle"})
    assert r.status_code == 422


def test_banner_404_for_unknown_banner(tmp_path, monkeypatch):
    c, src_id, _ = _setup(tmp_path, monkeypatch)
    r = c.post("/api/banner", json={"id": src_id, "asset_id": "deadbeef01"})
    assert r.status_code == 404


def test_banner_404_for_unknown_source(tmp_path, monkeypatch):
    c, _, banner_id = _setup(tmp_path, monkeypatch)
    r = c.post("/api/banner", json={"id": "nope", "asset_id": banner_id})
    assert r.status_code == 404
