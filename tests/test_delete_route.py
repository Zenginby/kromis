import pytest
from fastapi.testclient import TestClient

import app as appmod
import azure_client as ac

# Galeri/klasör/üretim rotaları DB'de (Faz 1 / 5): test kullanıcısı gerçek satır,
# `db.oturum` bu dosyanın motoruna bağlı — gerekçe tests/conftest.py::depo_db.
pytestmark = pytest.mark.usefixtures("depo_db")


def _client(tmp_path, dizinler):
    dizinler(output_dir=str(tmp_path))
    return TestClient(appmod.app)


def test_delete_existing_image(tmp_path, monkeypatch, dizinler):
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    c = _client(tmp_path, dizinler)
    gen = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                        "quality": "low", "n": 1}).json()
    iid = gen["images"][0]["id"]

    r = c.delete(f"/api/image/{iid}")
    assert r.status_code == 200
    assert r.json()["deleted"] == iid
    assert c.get("/api/history").json()["images"] == []


def test_delete_unknown_returns_404(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    assert c.delete("/api/image/nope").status_code == 404
