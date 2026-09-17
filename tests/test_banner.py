import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app as appmod
import azure_client as ac
from services import depo_varlik

# Galeri/klasör/üretim rotaları DB'de (Faz 1 / 5): test kullanıcısı gerçek satır,
# `db.oturum` bu dosyanın motoruna bağlı — gerekçe tests/conftest.py::depo_db.
pytestmark = pytest.mark.usefixtures("depo_db")


def _png(color=(30, 80, 200, 255), size=(64, 64)) -> bytes:
    im = Image.new("RGBA", size, color)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _setup(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    dizinler(output_dir=str(tmp_path / "output"), assets_dir=str(tmp_path / "assets"))
    # gerçek PNG üret ki PIL banner bindirmesi çalışsın
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [_png(size=(256, 256))])
    c = TestClient(appmod.app)
    src_id = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                           "quality": "medium", "n": 1}).json()["images"][0]["id"]
    # Varlık satır + dosya (Faz 1 / 6): tohum `db_oturumu` ile, commit ŞART.
    banner = depo_varlik.kaydet(db_oturumu, kullanici.id, "banners", _png(size=(400, 60)),
                                "footer", str(tmp_path / "assets"))
    db_oturumu.commit()
    return c, src_id, banner["id"]


def test_banner_preview_returns_data_url_and_does_not_save(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    c, src_id, banner_id = _setup(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    before = len(c.get("/api/history").json()["images"])
    r = c.post("/api/banner/preview", json={"id": src_id, "asset_id": banner_id, "edge": "top"})
    assert r.status_code == 200
    assert r.json()["b64"].startswith("data:image/png;base64,")
    after = len(c.get("/api/history").json()["images"])
    assert after == before


def test_banner_apply_creates_derivative(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    c, src_id, banner_id = _setup(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    r = c.post("/api/banner", json={"id": src_id, "asset_id": banner_id})
    assert r.status_code == 200
    rec = r.json()["image"]
    assert rec["parent_id"] == src_id
    assert (tmp_path / "output" / rec["filename"]).exists()


def test_banner_rejects_bad_edge(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    c, src_id, banner_id = _setup(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    r = c.post("/api/banner", json={"id": src_id, "asset_id": banner_id, "edge": "middle"})
    assert r.status_code == 422


def test_banner_404_for_unknown_banner(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    c, src_id, _ = _setup(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    r = c.post("/api/banner", json={"id": src_id, "asset_id": "deadbeef01"})
    assert r.status_code == 404


def test_banner_404_for_unknown_source(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    c, _, banner_id = _setup(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    r = c.post("/api/banner", json={"id": "nope", "asset_id": banner_id})
    assert r.status_code == 404


# ── boyut / hizalama / kenar boşluğu ────────────────────────────────────
BASE_COLOR = (30, 80, 200)      # _setup'ta üretilen zemin (RGB'ye çevrilmiş hali)
BANNER_COLOR = (240, 40, 40)    # aşağıdaki testlerde kullanılan banner rengi


def _setup_colored(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    """256×256 mavi zemin + 400×40 kırmızı banner: piksel örneklemesi için."""
    dizinler(output_dir=str(tmp_path / "output"), assets_dir=str(tmp_path / "assets"))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [_png(BASE_COLOR + (255,), (256, 256))])
    c = TestClient(appmod.app)
    src_id = c.post("/api/generate", json={"prompt": "x", "size": "1024x1024",
                                           "quality": "low", "n": 1}).json()["images"][0]["id"]
    banner = depo_varlik.kaydet(db_oturumu, kullanici.id, "banners",
                                _png(BANNER_COLOR + (255,), (400, 40)), "footer",
                                str(tmp_path / "assets"))
    db_oturumu.commit()
    return c, src_id, banner["id"]


def _preview_image(client, body) -> Image.Image:
    r = client.post("/api/banner/preview", json=body)
    assert r.status_code == 200, r.text
    import base64
    raw = base64.b64decode(r.json()["b64"].split(",", 1)[1])
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _close(actual, expected, tol=12):
    return all(abs(a - e) <= tol for a, e in zip(actual, expected))


def test_banner_scale_and_right_align_places_strip_on_the_right(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    c, src_id, banner_id = _setup_colored(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    im = _preview_image(c, {"id": src_id, "asset_id": banner_id, "edge": "bottom",
                            "scale": 0.5, "align": "right", "margin": 0.0})
    # 256 genişlik * 0.5 = 128 px banner, 400x40 -> 128x13, alt kenara yapışık
    assert im.size == (256, 256)
    assert _close(im.getpixel((200, 250)), BANNER_COLOR)   # sağ alt: banner
    assert _close(im.getpixel((30, 250)), BASE_COLOR)      # sol alt: zemin (banner yok)


def test_banner_left_align_places_strip_on_the_left(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    c, src_id, banner_id = _setup_colored(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    im = _preview_image(c, {"id": src_id, "asset_id": banner_id, "edge": "bottom",
                            "scale": 0.5, "align": "left"})
    assert _close(im.getpixel((30, 250)), BANNER_COLOR)
    assert _close(im.getpixel((200, 250)), BASE_COLOR)


def test_banner_margin_pushes_strip_away_from_edge(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    c, src_id, banner_id = _setup_colored(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    im = _preview_image(c, {"id": src_id, "asset_id": banner_id, "edge": "bottom",
                            "scale": 1.0, "margin": 0.1})
    # 256 * 0.1 = 26 px boşluk -> en alt satır artık zemin, banner yukarı kaydı
    assert _close(im.getpixel((128, 255)), BASE_COLOR)
    assert _close(im.getpixel((128, 256 - 26 - 6)), BANNER_COLOR)


def test_banner_defaults_match_full_width_behaviour(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    """Seçenek gönderilmeyen istek, açıkça varsayılan gönderilenle aynı çıktıyı vermeli."""
    c, src_id, banner_id = _setup_colored(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    implicit = c.post("/api/banner/preview", json={"id": src_id, "asset_id": banner_id}).json()
    explicit = c.post("/api/banner/preview", json={
        "id": src_id, "asset_id": banner_id, "edge": "bottom",
        "scale": 1.0, "align": "center", "margin": 0.0}).json()
    assert implicit["b64"] == explicit["b64"]


def test_banner_rejects_bad_align(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    c, src_id, banner_id = _setup_colored(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    r = c.post("/api/banner", json={"id": src_id, "asset_id": banner_id, "align": "diagonal"})
    assert r.status_code == 422


def test_banner_rejects_unknown_field_instead_of_silently_ignoring(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    """Sürüm uyuşmazlığı sessiz kalmamalı: bilinmeyen alan 422 vermeli.

    Pydantic varsayılanı bilinmeyen alanı yok sayar; bu yüzden bayat bir sunucu
    süreci yeni arayüzün seçeneklerini görmezden gelip değişmemiş görseli 200 ile
    döndürüyordu ("ayar çalışmıyor" belirtisi, hata mesajı yok).
    """
    c, src_id, banner_id = _setup_colored(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    r = c.post("/api/banner/preview", json={"id": src_id, "asset_id": banner_id,
                                            "gelecekteki_secenek": 0.5})
    assert r.status_code == 422


def test_logo_rejects_unknown_field(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    c, src_id, _ = _setup_colored(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    r = c.post("/api/logo/preview", json={"id": src_id, "gelecekteki_secenek": 1})
    assert r.status_code == 422


def test_banner_rejects_out_of_range_scale_and_margin(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici):
    c, src_id, banner_id = _setup_colored(tmp_path, monkeypatch, dizinler, db_oturumu, kullanici)
    for body in ({"scale": 0.05}, {"scale": 1.5}, {"margin": -0.1}, {"margin": 0.5}):
        r = c.post("/api/banner", json={"id": src_id, "asset_id": banner_id, **body})
        assert r.status_code == 422, body
