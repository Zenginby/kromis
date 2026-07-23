from fastapi.testclient import TestClient
import azure_client as ac
import app as appmod


def _fake_run_factory(recorder=None):
    """base_image = cmd[2], output_path = cmd[3]; kalan argümanlar bayraklardır."""
    def fake_run(cmd, capture_output, text):
        if recorder is not None:
            recorder.append(cmd)
        base_path, out_path = cmd[2], cmd[3]
        with open(base_path, "rb") as s, open(out_path, "wb") as d:
            d.write(s.read() + b"+LOGO")

        class R:
            returncode = 0
            stderr = ""
        return R()
    return fake_run


def _make_source(c):
    gen = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                        "quality": "medium", "n": 1}).json()
    return gen["images"][0]["id"]


def test_logo_creates_derivative(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    monkeypatch.setattr(appmod.subprocess, "run", _fake_run_factory())

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={"id": src_id})
    assert r.status_code == 200
    rec = r.json()["image"]
    assert rec["parent_id"] == src_id
    assert (tmp_path / rec["filename"]).read_bytes() == b"\x89PNG-base+LOGO"


def test_logo_passes_options_to_script(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.subprocess, "run", _fake_run_factory(calls))

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={
        "id": src_id, "position": "top-center", "color": "white",
        "size": 0.22, "shadow_alpha": 0, "shadow_blur": 10})
    assert r.status_code == 200
    cmd = calls[-1]
    assert "--position" in cmd and cmd[cmd.index("--position") + 1] == "top-center"
    assert cmd[cmd.index("--color") + 1] == "white"
    assert cmd[cmd.index("--scale") + 1] == "0.22"
    assert cmd[cmd.index("--shadow-alpha") + 1] == "0"
    assert cmd[cmd.index("--shadow-blur") + 1] == "10"


def test_logo_preview_returns_data_url_and_does_not_save(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    monkeypatch.setattr(appmod.subprocess, "run", _fake_run_factory())

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    before = len(c.get("/api/history").json()["images"])

    r = c.post("/api/logo/preview", json={"id": src_id, "position": "center"})
    assert r.status_code == 200
    assert r.json()["b64"].startswith("data:image/png;base64,")
    # önizleme geçmişe eklenmemeli
    after = len(c.get("/api/history").json()["images"])
    assert after == before


def test_logo_rejects_bad_position(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    c = TestClient(appmod.app)
    r = c.post("/api/logo", json={"id": "x", "position": "middle-nowhere"})
    assert r.status_code == 422


def test_logo_rejects_bad_size(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    c = TestClient(appmod.app)
    assert c.post("/api/logo", json={"id": "x", "size": 0.9}).status_code == 422
    assert c.post("/api/logo", json={"id": "x", "shadow_alpha": 999}).status_code == 422


def test_logo_404_for_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    c = TestClient(appmod.app)
    assert c.post("/api/logo", json={"id": "nope"}).status_code == 404
    assert c.post("/api/logo/preview", json={"id": "nope"}).status_code == 404
