import base64
from fastapi.testclient import TestClient
import azure_client as ac
import app as appmod


def test_logo_creates_derivative(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])

    # sahte composite: girdi görselini alıp çıktı yoluna "logolu" yazar
    def fake_run(cmd, capture_output, text):
        base_path, out_path = cmd[-2], cmd[-1]
        with open(base_path, "rb") as s, open(out_path, "wb") as d:
            d.write(s.read() + b"+LOGO")
        class R:  # subprocess.CompletedProcess benzeri
            returncode = 0
            stderr = ""
        return R()
    monkeypatch.setattr(appmod.subprocess, "run", fake_run)

    c = TestClient(appmod.app)
    gen = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                        "quality": "medium", "n": 1}).json()
    src_id = gen["images"][0]["id"]

    r = c.post("/api/logo", json={"id": src_id})
    assert r.status_code == 200
    rec = r.json()["image"]
    assert rec["parent_id"] == src_id
    assert (tmp_path / rec["filename"]).read_bytes() == b"\x89PNG-base+LOGO"


def test_logo_404_for_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    c = TestClient(appmod.app)
    assert c.post("/api/logo", json={"id": "nope"}).status_code == 404
