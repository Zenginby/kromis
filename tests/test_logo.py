import io

from fastapi.testclient import TestClient
from PIL import Image

import app as appmod
import assets_store as astore
import azure_client as ac


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


def _logo_asset(tmp_path, monkeypatch, *, png: bytes = b"\x89PNG-logo",
                kind: str = "logos") -> str:
    """Kütüphaneye bir varlık koyar, id'sini döndürür; ASSETS_DIR'i de yönlendirir.

    Yerleşik logo kaldırıldığından /api/logo HER ZAMAN bir `asset_id`
    istiyor (bkz. models.LogoRequest) — bu yüzden bindirme yapan hemen her test
    önce kütüphaneye bir şey koymak zorunda.
    """
    assets_dir = str(tmp_path / "assets")
    monkeypatch.setattr(appmod, "ASSETS_DIR", assets_dir)
    rec = astore.save_asset(kind, png, "test varlığı", assets_dir,
                            now="2026-07-23T10:00:00")
    return rec["id"]


def _real_png(size=(64, 48), color=(20, 120, 200)) -> bytes:
    """Gerçek (mocklanmamış) bindirme için geçerli bir PNG — Pillow açabilmeli."""
    buf = io.BytesIO()
    Image.new("RGBA", size, color + (255,)).save(buf, format="PNG")
    return buf.getvalue()


def _make_source(c):
    gen = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                        "quality": "medium", "n": 1}).json()
    return gen["images"][0]["id"]


def test_logo_creates_derivative(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory())

    asset_id = _logo_asset(tmp_path, monkeypatch)
    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={"id": src_id, "asset_id": asset_id})
    assert r.status_code == 200
    rec = r.json()["image"]
    assert rec["parent_id"] == src_id
    assert (tmp_path / rec["filename"]).read_bytes() == b"\x89PNG-base+LOGO"


def test_logo_passes_options_to_composite(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))

    asset_id = _logo_asset(tmp_path, monkeypatch)
    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={
        "id": src_id, "asset_id": asset_id, "position": "top-center",
        "size": 0.22, "shadow_alpha": 0, "shadow_blur": 10})
    assert r.status_code == 200
    kw = calls[-1]
    assert kw["position"] == "top-center"
    assert kw["scale"] == 0.22          # LogoRequest.size -> composite scale
    assert kw["shadow_alpha"] == 0
    assert kw["shadow_blur"] == 10


def test_logo_preview_returns_data_url_and_does_not_save(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory())

    asset_id = _logo_asset(tmp_path, monkeypatch)
    c = TestClient(appmod.app)
    src_id = _make_source(c)
    before = len(c.get("/api/history").json()["images"])

    r = c.post("/api/logo/preview",
               json={"id": src_id, "asset_id": asset_id, "position": "center"})
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


def test_logo_without_asset_id_is_rejected(tmp_path, monkeypatch):
    """asset_id YOKSA istek reddedilir — yerleşik logo diye bir şey yok.

    Eskiden bu yol pakete gömülü yerleşik logo çiftine düşer ve 200 dönerdi. Ürün
    marka-nötr olduğundan artık bindirilecek görsel her zaman kullanıcının
    kütüphanesinden gelmek zorunda; sessizce bir varsayılana düşmek kullanıcının
    hiç seçmediği bir logoyu görselin üstüne basmak olurdu.
    """
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    called = []
    monkeypatch.setattr(appmod.composite, "composite_logo",
                        _fake_composite_factory(called))

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    for yol in ("/api/logo", "/api/logo/preview"):
        assert c.post(yol, json={"id": src_id}).status_code == 422, yol
    # Bindirme HİÇ çağrılmamalı: kapı uçta kapanıyor, composite'te değil.
    assert called == []


def test_logo_asset_id_is_passed_as_the_overlay(tmp_path, monkeypatch):
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
    assert calls[-1]["logo_path"].endswith(f"{asset['id']}.png")


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
    assert calls[-1]["logo_path"].endswith(f"{motto['id']}.png")
    # motto id'si logos kütüphanesinde yok → yalnızca mottos'tan çözülebildi
    assert astore.asset_path("logos", motto["id"], str(tmp_path / "assets")) is None


def test_logo_passes_offset_to_composite(tmp_path, monkeypatch):
    """Izgara noktasından sapma composite'e ORAN olarak geçmeli."""
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))

    asset_id = _logo_asset(tmp_path, monkeypatch)
    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={"id": src_id, "asset_id": asset_id,
                                  "offset_x": 0.08, "offset_y": -0.05})
    assert r.status_code == 200
    kw = calls[-1]
    assert kw["offset_x"] == 0.08
    assert kw["offset_y"] == -0.05


def test_logo_defaults_send_zero_offset(tmp_path, monkeypatch):
    """Alan gönderilmezse sıfır gitmeli — eski istemci birebir eski çıktıyı alır."""
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))

    asset_id = _logo_asset(tmp_path, monkeypatch)
    c = TestClient(appmod.app)
    src_id = _make_source(c)
    assert c.post("/api/logo",
                  json={"id": src_id, "asset_id": asset_id}).status_code == 200
    assert calls[-1]["offset_x"] == 0.0
    assert calls[-1]["offset_y"] == 0.0


def test_logo_rejects_out_of_range_offset(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    c = TestClient(appmod.app)
    assert c.post("/api/logo", json={"id": "x", "offset_x": 0.9}).status_code == 422
    assert c.post("/api/logo", json={"id": "x", "offset_y": -0.9}).status_code == 422


def test_motto_offset_also_reaches_composite(tmp_path, monkeypatch):
    """Motto logo ile aynı paneli paylaşıyor; kaydırma onda da çalışmalı.

    Arayüz tarafında ortak panel yeterli görünüyor ama sunucu sözleşmesinin de
    motto yolunda tuttuğu ayrıca kanıtlanmalı: asset_kind ayrı bir daldan
    geçiyor (_composite_logo'daki asset_id çözümlemesi).
    """
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
                                  "asset_kind": "mottos", "position": "bottom-center",
                                  "offset_x": -0.12, "offset_y": 0.04})
    assert r.status_code == 200
    kw = calls[-1]
    assert kw["logo_path"].endswith(f"{motto['id']}.png")
    assert (kw["offset_x"], kw["offset_y"]) == (-0.12, 0.04)


def test_offset_actually_moves_the_output(tmp_path, monkeypatch):
    """Mock YOK: kaydırmalı ve kaydırmasız bindirmenin PİKSELLERİ farklı olmalı.

    Uçtan uca kanıt. Yalnız kwargs'ı ölçen testler yeşil kalırken uç offset'i
    composite'e geçirmeyi unutabilir — kullanıcı slider'ı sürükler, hiçbir şey
    olmaz ve testler bunu görmez.
    """
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))

    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (200, 60, 60)).save(buf, format="PNG")
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [buf.getvalue()])

    asset_id = _logo_asset(tmp_path, monkeypatch, png=_real_png())
    c = TestClient(appmod.app)
    src_id = _make_source(c)

    plain = c.post("/api/logo", json={"id": src_id, "asset_id": asset_id})
    moved = c.post("/api/logo", json={"id": src_id, "asset_id": asset_id,
                                      "offset_x": -0.15, "offset_y": -0.15})
    assert plain.status_code == 200 and moved.status_code == 200

    a = (tmp_path / plain.json()["image"]["filename"]).read_bytes()
    b = (tmp_path / moved.json()["image"]["filename"]).read_bytes()
    with Image.open(io.BytesIO(a)) as ia, Image.open(io.BytesIO(b)) as ib:
        assert ia.size == ib.size
        assert ia.convert("RGB").tobytes() != ib.convert("RGB").tobytes()


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

    asset_id = _logo_asset(tmp_path, monkeypatch)
    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={"id": src_id, "asset_id": asset_id})
    assert r.status_code == 500
    assert "The overlay failed" in r.json()["detail"]


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

    asset_id = _logo_asset(tmp_path, monkeypatch)
    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={"id": src_id, "asset_id": asset_id})
    assert r.status_code == 500
    assert "The overlay failed" in r.json()["detail"]


def test_logo_end_to_end_with_real_compositing(tmp_path, monkeypatch):
    """composite.composite_logo hiç mocklanmadan, kütüphaneden gerçek bir logoyla çalışır.

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

    asset_id = _logo_asset(tmp_path, monkeypatch, png=_real_png())
    c = TestClient(appmod.app)
    src_id = _make_source(c)

    r = c.post("/api/logo", json={"id": src_id, "asset_id": asset_id})
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


def test_bindirme_KAYNAGIN_modelini_devraliyor(tmp_path, monkeypatch):
    """Bindirme TÜREV: kendi başına bir üretim değil.

    `folder_id`, `palette` ve `prompt_sent` gibi model de kaynaktan
    devralınmalı. Geçilmediğinde kayda VARSAYILAN model yazılıyordu — yani
    Nano Banana ile üretilmiş bir görselin logolu hâli geçmişte
    "azure-gpt-image-2" olarak duruyordu ve kredi ledger'ı onu yanlış
    sağlayıcıya yazacaktı.
    """
    import catalog

    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory())
    # Kataloğun İKİNCİ modeli: varsayılanla aynı olsa iddia hiçbir şey ölçmezdi.
    baska = catalog.ImageModel(
        id="test-baska-model", label="Test · başka", provider="azure",
        wire_model="test-model", credential="azure_image",
        sizes=("1024x1024",), qualities=("medium",), max_n=1,
        credits=7, images_per_request=1, supports_edit=True)
    monkeypatch.setattr(catalog, "IMAGE_MODELS", catalog.IMAGE_MODELS + (baska,))

    asset_id = _logo_asset(tmp_path, monkeypatch)
    c = TestClient(appmod.app)
    src = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                        "quality": "medium", "n": 1,
                                        "model": baska.id}).json()["images"][0]
    assert src["model"] == baska.id, "kaynak zaten varsayılana düştü"

    rec = c.post("/api/logo", json={"id": src["id"], "asset_id": asset_id}).json()["image"]

    assert rec["model"] == baska.id, (
        f"türev kaynağın modelini kaybetti: {rec['model']!r}")
