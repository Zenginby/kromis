import io
from fastapi.testclient import TestClient
from PIL import Image
import azure_client as ac
import storage
import app as appmod


def _png_bytes(color=(255, 0, 0)):
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buf, format="PNG")
    return buf.getvalue()


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    return TestClient(appmod.app)


def test_edit_from_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "edit", lambda *a, **k: [b"\x89PNG-edited"])
    c = _client(tmp_path, monkeypatch)
    r = c.post(
        "/api/edit",
        data={"prompt": "make blue", "size": "1024x1024", "quality": "low", "n": "1"},
        files={"file": ("in.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 200, r.text
    imgs = r.json()["images"]
    assert len(imgs) == 1
    assert imgs[0]["parent_id"] is None
    assert imgs[0]["prompt"] == "make blue"


def test_edit_from_source_id(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    monkeypatch.setattr(ac, "edit", lambda *a, **k: [b"\x89PNG-edited"])
    c = _client(tmp_path, monkeypatch)
    gen = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                        "quality": "low", "n": 1}).json()
    src_id = gen["images"][0]["id"]
    r = c.post("/api/edit", data={"prompt": "make blue", "size": "1024x1024",
                                  "quality": "low", "n": "1", "source_id": src_id})
    assert r.status_code == 200, r.text
    assert r.json()["images"][0]["parent_id"] == src_id


def test_edit_rejects_both_file_and_source_id(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/edit",
               data={"prompt": "x", "size": "1024x1024", "quality": "low",
                     "n": "1", "source_id": "abc"},
               files={"file": ("in.png", _png_bytes(), "image/png")})
    assert r.status_code == 422


def test_edit_rejects_neither(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/edit", data={"prompt": "x", "size": "1024x1024",
                                  "quality": "low", "n": "1"})
    assert r.status_code == 422


def test_edit_rejects_bad_size(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/edit",
               data={"prompt": "x", "size": "99x99", "quality": "low", "n": "1"},
               files={"file": ("in.png", _png_bytes(), "image/png")})
    assert r.status_code == 422


def test_edit_rejects_invalid_upload(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/edit",
               data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
               files={"file": ("in.png", b"not-an-image", "image/png")})
    assert r.status_code == 422


def test_edit_rejects_oversized_upload(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    big = b"\x00" * (10 * 1024 * 1024 + 1)  # > MAX_UPLOAD_BYTES
    r = c.post(
        "/api/edit",
        data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
        files={"file": ("big.png", big, "image/png")},
    )
    assert r.status_code == 413


def test_edit_unknown_source_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/edit", data={"prompt": "x", "size": "1024x1024",
                                  "quality": "low", "n": "1", "source_id": "nope"})
    assert r.status_code == 404


def test_edit_rejects_huge_dimensions(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "MAX_IMAGE_PIXELS", 100)  # tiny cap for the test
    c = _client(tmp_path, monkeypatch)
    # _png_bytes() makes a 32x32 = 1024px image, exceeds the 100px cap
    r = c.post(
        "/api/edit",
        data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
        files={"file": ("in.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 422


def test_edit_maps_azure_error(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ac.AzureImageError("Azure isteği başarısız (HTTP 429).")
    monkeypatch.setattr(ac, "edit", boom)
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/edit",
               data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
               files={"file": ("in.png", _png_bytes(), "image/png")})
    assert r.status_code == 502
    assert "429" in r.json()["detail"]
