import base64
from fastapi.testclient import TestClient
import azure_client as ac
import app as appmod


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    return TestClient(appmod.app)


def test_generate_happy_path(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                      "quality": "medium", "n": 1})
    assert r.status_code == 200
    imgs = r.json()["images"]
    assert len(imgs) == 1 and imgs[0]["prompt"] == "cat"


def test_generate_rejects_bad_size(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/generate", json={"prompt": "x", "size": "99x99",
                                      "quality": "medium", "n": 1})
    assert r.status_code == 422


def test_generate_maps_azure_error(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ac.AzureImageError("Azure isteği başarısız (HTTP 429).")
    monkeypatch.setattr(ac, "generate", boom)
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/generate", json={"prompt": "x", "size": "1024x1024",
                                      "quality": "medium", "n": 1})
    assert r.status_code == 502
    assert "429" in r.json()["detail"]


def test_history_returns_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    c = _client(tmp_path, monkeypatch)
    c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                  "quality": "low", "n": 1})
    r = c.get("/api/history")
    assert r.status_code == 200 and len(r.json()["images"]) == 1
