import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app as appmod
import azure_client as ac
from services import gorsel

# Galeri/klasör/üretim rotaları DB'de (Faz 1 / 5): test kullanıcısı gerçek satır,
# `db.oturum` bu dosyanın motoruna bağlı — gerekçe tests/conftest.py::depo_db.
pytestmark = pytest.mark.usefixtures("depo_db")


def _png_bytes(color=(255, 0, 0)):
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buf, format="PNG")
    return buf.getvalue()


def _client(tmp_path, dizinler):
    dizinler(output_dir=str(tmp_path))
    return TestClient(appmod.app)


def test_edit_from_upload(tmp_path, monkeypatch, dizinler):
    monkeypatch.setattr(ac, "edit", lambda *a, **k: [b"\x89PNG-edited"])
    c = _client(tmp_path, dizinler)
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


def test_edit_from_source_id(tmp_path, monkeypatch, dizinler):
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    monkeypatch.setattr(ac, "edit", lambda *a, **k: [b"\x89PNG-edited"])
    c = _client(tmp_path, dizinler)
    gen = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                        "quality": "low", "n": 1}).json()
    src_id = gen["images"][0]["id"]
    r = c.post("/api/edit", data={"prompt": "make blue", "size": "1024x1024",
                                  "quality": "low", "n": "1", "source_id": src_id})
    assert r.status_code == 200, r.text
    assert r.json()["images"][0]["parent_id"] == src_id


def test_edit_labels_the_image_with_its_session(tmp_path, monkeypatch, dizinler):
    """Düzenleme de oturum içinde oluyor ("Düzenlendi · referanslı üretim")."""
    monkeypatch.setattr(ac, "edit", lambda *a, **k: [b"\x89PNG-edited"])
    c = _client(tmp_path, dizinler)

    r = c.post("/api/edit",
               data={"prompt": "make blue", "size": "1024x1024", "quality": "low",
                     "n": "1", "session_id": "beef1234beef"},
               files={"file": ("in.png", _png_bytes(), "image/png")})

    assert r.status_code == 200, r.text
    assert r.json()["images"][0]["session_id"] == "beef1234beef"


def test_edit_without_a_session_writes_no_session_key(tmp_path, monkeypatch, dizinler):
    monkeypatch.setattr(ac, "edit", lambda *a, **k: [b"\x89PNG-edited"])
    c = _client(tmp_path, dizinler)

    r = c.post("/api/edit",
               data={"prompt": "make blue", "size": "1024x1024", "quality": "low",
                     "n": "1"},
               files={"file": ("in.png", _png_bytes(), "image/png")})

    assert "session_id" not in r.json()["images"][0]


def test_edit_rejects_a_malformed_session_id(tmp_path, monkeypatch, dizinler):
    monkeypatch.setattr(ac, "edit", lambda *a, **k: [b"\x89PNG-edited"])
    c = _client(tmp_path, dizinler)

    r = c.post("/api/edit",
               data={"prompt": "make blue", "size": "1024x1024", "quality": "low",
                     "n": "1", "session_id": "../../etc/passwd"},
               files={"file": ("in.png", _png_bytes(), "image/png")})

    assert r.status_code == 422


def test_edit_rejects_both_file_and_source_id(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    r = c.post("/api/edit",
               data={"prompt": "x", "size": "1024x1024", "quality": "low",
                     "n": "1", "source_id": "abc"},
               files={"file": ("in.png", _png_bytes(), "image/png")})
    assert r.status_code == 422


def test_edit_rejects_neither(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    r = c.post("/api/edit", data={"prompt": "x", "size": "1024x1024",
                                  "quality": "low", "n": "1"})
    assert r.status_code == 422


def test_edit_rejects_bad_size(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    r = c.post("/api/edit",
               data={"prompt": "x", "size": "99x99", "quality": "low", "n": "1"},
               files={"file": ("in.png", _png_bytes(), "image/png")})
    assert r.status_code == 422


def test_edit_rejects_invalid_upload(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    r = c.post("/api/edit",
               data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
               files={"file": ("in.png", b"not-an-image", "image/png")})
    assert r.status_code == 422


def test_edit_rejects_oversized_upload(tmp_path, dizinler):
    c = _client(tmp_path, dizinler)
    big = b"\x00" * (10 * 1024 * 1024 + 1)  # > MAX_UPLOAD_BYTES
    r = c.post(
        "/api/edit",
        data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
        files={"file": ("big.png", big, "image/png")},
    )
    assert r.status_code == 413


def test_edit_unknown_source_404(tmp_path, monkeypatch, dizinler):
    c = _client(tmp_path, dizinler)
    r = c.post("/api/edit", data={"prompt": "x", "size": "1024x1024",
                                  "quality": "low", "n": "1", "source_id": "nope"})
    assert r.status_code == 404


def test_edit_rejects_huge_dimensions(tmp_path, monkeypatch, dizinler):
    monkeypatch.setattr(gorsel, "MAX_IMAGE_PIXELS", 100)  # tiny cap for the test
    c = _client(tmp_path, dizinler)
    # _png_bytes() makes a 32x32 = 1024px image, exceeds the 100px cap
    r = c.post(
        "/api/edit",
        data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
        files={"file": ("in.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 422


def _capture_edit(monkeypatch):
    """ac.edit çağrısındaki referans listesini yakalayan sahte."""
    seen = {}

    def fake_edit(prompt, refs, size, quality, n, **kw):
        seen["refs"] = refs
        return [b"\x89PNG-edited"]

    monkeypatch.setattr(ac, "edit", fake_edit)
    return seen


def test_edit_with_extra_upload_sends_both_images_in_order(tmp_path, monkeypatch, dizinler):
    seen = _capture_edit(monkeypatch)
    c = _client(tmp_path, dizinler)
    r = c.post(
        "/api/edit",
        data={"prompt": "birleştir", "size": "1024x1024", "quality": "low", "n": "1"},
        files=[
            ("file", ("base.png", _png_bytes((10, 20, 30)), "image/png")),
            ("extra_files", ("logo.png", _png_bytes((200, 100, 50)), "image/png")),
        ],
    )
    assert r.status_code == 200, r.text
    assert [name for name, _ in seen["refs"]] == ["upload.png", "ref2.png"]
    assert len(seen["refs"]) == 2


def test_edit_with_extra_source_id_uses_gallery_image(tmp_path, monkeypatch, dizinler):
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [_png_bytes()])
    c = _client(tmp_path, dizinler)
    ids = [
        c.post("/api/generate", json={"prompt": p, "size": "1024x1024",
                                      "quality": "low", "n": 1}).json()["images"][0]["id"]
        for p in ("cat", "dog")
    ]
    seen = _capture_edit(monkeypatch)
    r = c.post("/api/edit", data={"prompt": "birleştir", "size": "1024x1024", "quality": "low",
                                  "n": "1", "source_id": ids[0], "extra_source_ids": ids[1]})
    assert r.status_code == 200, r.text
    assert [name for name, _ in seen["refs"]] == [f"{ids[0]}.png", "ref2.png"]
    # provenance yalnızca ana görselden gelir
    assert r.json()["images"][0]["parent_id"] == ids[0]


def test_edit_rejects_more_than_max_images(tmp_path, monkeypatch, dizinler):
    _capture_edit(monkeypatch)
    c = _client(tmp_path, dizinler)
    extras = [("extra_files", (f"e{i}.png", _png_bytes(), "image/png")) for i in range(4)]
    r = c.post(
        "/api/edit",
        data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
        files=[("file", ("base.png", _png_bytes(), "image/png"))] + extras,
    )
    assert r.status_code == 422
    assert str(appmod.MAX_EDIT_IMAGES) in r.json()["detail"]


def test_edit_rejects_invalid_extra_upload(tmp_path, monkeypatch, dizinler):
    _capture_edit(monkeypatch)
    c = _client(tmp_path, dizinler)
    r = c.post(
        "/api/edit",
        data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
        files=[
            ("file", ("base.png", _png_bytes(), "image/png")),
            ("extra_files", ("bad.png", b"not-an-image", "image/png")),
        ],
    )
    assert r.status_code == 422


def test_edit_unknown_extra_source_404(tmp_path, monkeypatch, dizinler):
    _capture_edit(monkeypatch)
    c = _client(tmp_path, dizinler)
    r = c.post(
        "/api/edit",
        data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1",
              "extra_source_ids": "nope"},
        files={"file": ("base.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 404


def test_edit_ignores_empty_extra_fields(tmp_path, monkeypatch, dizinler):
    """Tarayıcı boş bir extra parçası gönderirse tek görselli akış bozulmamalı."""
    seen = _capture_edit(monkeypatch)
    c = _client(tmp_path, dizinler)
    r = c.post(
        "/api/edit",
        data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1",
              "extra_source_ids": "  "},
        files=[("file", ("base.png", _png_bytes(), "image/png")),
               ("extra_files", ("", b"", "application/octet-stream"))],
    )
    assert r.status_code == 200, r.text
    assert len(seen["refs"]) == 1


def test_edit_maps_azure_error(tmp_path, monkeypatch, dizinler):
    def boom(*a, **k):
        raise ac.AzureImageError("Azure isteği başarısız (HTTP 429).")
    monkeypatch.setattr(ac, "edit", boom)
    c = _client(tmp_path, dizinler)
    r = c.post("/api/edit",
               data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
               files={"file": ("in.png", _png_bytes(), "image/png")})
    assert r.status_code == 502
    assert "429" in r.json()["detail"]
