from fastapi.testclient import TestClient
import azure_client as ac
import app as appmod


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    return TestClient(appmod.app)


def test_delete_existing_image(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    c = _client(tmp_path, monkeypatch)
    gen = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                        "quality": "low", "n": 1}).json()
    iid = gen["images"][0]["id"]

    r = c.delete(f"/api/image/{iid}")
    assert r.status_code == 200
    assert r.json()["deleted"] == iid
    assert c.get("/api/history").json()["images"] == []


def test_delete_unknown_returns_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.delete("/api/image/nope").status_code == 404
