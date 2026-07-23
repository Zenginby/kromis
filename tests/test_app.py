import os
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


def test_output_directory_name_returns_404(tmp_path, monkeypatch):
    os.makedirs(os.path.join(str(tmp_path), "sub"))
    c = _client(tmp_path, monkeypatch)
    r = c.get("/output/sub")
    assert r.status_code == 404


def test_output_missing_file_returns_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/output/nope.png")
    assert r.status_code == 404
