import io

from fastapi.testclient import TestClient
from PIL import Image

import azure_client as ac
import app as appmod
import assets_store as astore


def _fake_composite_factory(recorder=None):
    """composite.composite_logo yerine geçer: temel dosyayı okur, sonuna imza ekler.

    Eski _fake_run_factory komut dizisini kaydediyordu; artık çağrı kwargs'ı
    kaydediyoruz — port sonrası sözleşme bu.
    """
    def fake_composite(base_path, **kwargs):
        if recorder is not None:
            recorder.append(kwargs)
        with open(base_path, "rb") as f:
            return f.read() + b"+LOGO"
    return fake_composite


def _make_source(c):
    gen = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                        "quality": "medium", "n": 1}).json()
    return gen["images"][0]["id"]


def test_logo_creates_derivative(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory())

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={"id": src_id})
    assert r.status_code == 200
    rec = r.json()["image"]
    assert rec["parent_id"] == src_id
    assert (tmp_path / rec["filename"]).read_bytes() == b"\x89PNG-base+LOGO"


def test_logo_passes_options_to_composite(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={
        "id": src_id, "position": "top-center", "color": "white",
        "size": 0.22, "shadow_alpha": 0, "shadow_blur": 10})
    assert r.status_code == 200
    kw = calls[-1]
    assert kw["position"] == "top-center"
    assert kw["color"] == "white"
    assert kw["scale"] == 0.22          # LogoRequest.size -> composite scale
    assert kw["shadow_alpha"] == 0
    assert kw["shadow_blur"] == 10


def test_logo_preview_returns_data_url_and_does_not_save(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory())

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


def test_logo_builtin_uses_bundled_ila_logos(tmp_path, monkeypatch):
    """asset_id yoksa gömülü mavi/beyaz KURUM logoları geçilir (auto seçim composite'te)."""
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    assert c.post("/api/logo", json={"id": src_id}).status_code == 200
    kw = calls[-1]
    assert kw["logo_blue"].endswith("bundled/logos/kurum-logo-blue.png")
    assert kw["logo_white"].endswith("bundled/logos/kurum-logo-white.png")
    assert kw["logo_blue"] != kw["logo_white"]


def test_logo_asset_id_passes_custom_overlay_as_both_variants(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    asset = astore.save_asset("logos", b"\x89PNG-logo", "özel", str(tmp_path / "assets"),
                              now="2026-07-23T10:00:00")

    r = c.post("/api/logo", json={"id": src_id, "asset_id": asset["id"]})
    assert r.status_code == 200
    kw = calls[-1]
    assert kw["logo_blue"] == kw["logo_white"]
    assert kw["logo_blue"].endswith(f"{asset['id']}.png")


def test_logo_asset_id_404_for_unknown_asset(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory())

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={"id": src_id, "asset_id": "deadbeef01"})
    assert r.status_code == 404


def test_motto_placement_resolves_from_mottos_library(tmp_path, monkeypatch):
    """Motto = logo tarzı konumlanabilir bindirme, ama 'mottos' kütüphanesinden."""
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    motto = astore.save_asset("mottos", b"\x89PNG-motto", "motto", str(tmp_path / "assets"),
                              now="2026-07-23T10:00:00")

    r = c.post("/api/logo", json={"id": src_id, "asset_id": motto["id"],
                                  "asset_kind": "mottos", "position": "center"})
    assert r.status_code == 200
    assert calls[-1]["logo_blue"].endswith(f"{motto['id']}.png")
    # motto id'si logos kütüphanesinde yok → yalnızca mottos'tan çözülebildi
    assert astore.asset_path("logos", motto["id"], str(tmp_path / "assets")) is None


def test_logo_rejects_bad_asset_kind(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    c = TestClient(appmod.app)
    r = c.post("/api/logo", json={"id": "x", "asset_id": "deadbeef01", "asset_kind": "banners"})
    assert r.status_code == 422


def test_composite_failure_becomes_500(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])

    def boom(base_path, **kwargs):
        raise OSError("logo dosyası okunamadı")
    monkeypatch.setattr(appmod.composite, "composite_logo", boom)

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={"id": src_id})
    assert r.status_code == 500
    assert "Logo bindirme başarısız" in r.json()["detail"]


def test_unexpected_composite_error_also_becomes_500(tmp_path, monkeypatch):
    """OSError/ValueError olmayan hatalar da Türkçe 500'e dönmeli.

    `Image.DecompressionBombError` doğrudan `Exception`'dan türüyor: dar bir
    except onu yakalamaz, kullanıcı "Logo bindirme başarısız" mesajı yerine
    çıplak bir sunucu hatası görürdü.
    """
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])

    def boom(base_path, **kwargs):
        raise Image.DecompressionBombError("görsel çok büyük (simüle)")
    monkeypatch.setattr(appmod.composite, "composite_logo", boom)

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={"id": src_id})
    assert r.status_code == 500
    assert "Logo bindirme başarısız" in r.json()["detail"]


def test_logo_end_to_end_with_real_compositing(tmp_path, monkeypatch):
    """composite.composite_logo hiç mocklanmadan, gerçek gömülü KURUM logolarıyla çalışır.

    Logo bindirme Azure'a çıkmaz; yalnızca azure_client.generate mocklanır (ağ
    yasağı ihlal edilmez). Bu, subprocess'ten composite.py'ye geçişin uçtan uca
    kanıtı — eskiden tarayıcıdan elle doğrulanan adımın yerini alır.
    """
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))

    src_img = Image.new("RGB", (320, 240), (200, 60, 60))
    buf = io.BytesIO()
    src_img.save(buf, format="PNG")
    src_bytes = buf.getvalue()
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [src_bytes])

    c = TestClient(appmod.app)
    src_id = _make_source(c)

    r = c.post("/api/logo", json={"id": src_id})
    assert r.status_code == 200, r.text
    rec = r.json()["image"]

    out_path = tmp_path / rec["filename"]
    assert out_path.exists()
    out_bytes = out_path.read_bytes()
    assert out_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    with Image.open(out_path) as out_img:
        out_img.load()
        assert out_img.size == src_img.size

    assert out_bytes != src_bytes
