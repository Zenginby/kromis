"""Model seçiminin uçtan uca yolu: doğrulama → çağrı → kayıt → yankı.

Bu adımda katalogda hâlâ TEK model var (Azure). Bilinçli: riskli tesisatın
tamamı, 52 test dosyasıyla kaplı varsayılan yola karşı ölçülüyor — ikinci bir
sağlayıcı teşhisi bulandırmadan. Birden fazla modeli gerektiren iddialar
katalogu `monkeypatch` ile geçici olarak genişletiyor.
"""
import dataclasses

import pytest
from fastapi.testclient import TestClient

import app as appmod
import azure_client as ac
import catalog
import models
from services import gorsel


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    monkeypatch.setattr(ac, "edit", lambda *a, **k: [b"\x89PNG"])
    return TestClient(appmod.app)


@pytest.fixture
def genis_katalog(monkeypatch):
    """Kataloğa ikinci bir model ekler: farklı boyut kümesi, n=1, düzenleme YOK.

    Yetenek sisteminin tek modelle ölçülemeyen tarafını (kümelerin GERÇEKTEN
    modele bağlı olması) sınıyor. Şekil bir zamanlar `dall-e-3`ün gerçek
    kısıtlarıydı; o model kalktıktan sonra kısıtlar SENTETİK kaldı ve fikstür
    bu yüzden daha da gerekli — mekanizmayı taşıyan gerçek bir model yoksa
    onu ölçen tek şey burası.
    """
    tek = catalog.ImageModel(
        id="test-tek-atis", label="Test · tek atış", provider="azure",
        wire_model="test-model", credential="azure_image",
        sizes=("1024x1792",), qualities=("standard",), max_n=1,
        credits=10, images_per_request=1, supports_edit=False,
        quality_hidden=True)
    monkeypatch.setattr(catalog, "IMAGE_MODELS", catalog.IMAGE_MODELS + (tek,))
    return tek


# ── JSON ucu: /api/generate ────────────────────────────────────────────


def test_model_gonderilmeyen_istek_VARSAYILANA_gidiyor(client):
    """Bugünkü arayüzün gövdesi bayt bayt aynı kalıyor ve aynı modele gidiyor.

    "Kayıtlı Azure kullanıcısı için sıfır davranış değişikliği" güvencesinin
    ölçülen hâli.
    """
    r = client.post("/api/generate", json={"prompt": "kedi", "size": "1024x1024",
                                           "quality": "medium", "n": 1})

    assert r.status_code == 200, r.text
    assert r.json()["images"][0]["model"] == catalog.DEFAULT_IMAGE_MODEL


def test_kayit_modeli_ve_KREDI_maliyetini_tasiyor(client):
    """Kredi ÜRETİM ANINDAKİ çözülmüş tam sayı, katalog işaretçisi değil."""
    r = client.post("/api/generate", json={"prompt": "kedi", "size": "1024x1024",
                                           "quality": "high", "n": 1})

    kayit = r.json()["images"][0]
    spec = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    assert kayit["credits"] == catalog.cost_for(spec, "high")
    # Kalite maliyeti gerçekten değiştiriyor olmalı, yoksa iddia boş.
    assert catalog.cost_for(spec, "high") != catalog.cost_for(spec, "low")


def test_kredi_GORSEL_BASINA_yaziliyor_tur_toplami_DEGIL(client, monkeypatch):
    """n=3'lük bir turda her satıra turun toplamını yazmak toplamı üçe katlardı."""
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"A", b"B", b"C"])

    r = client.post("/api/generate", json={"prompt": "kedi", "size": "1024x1024",
                                           "quality": "low", "n": 3})

    spec = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    tek = catalog.cost_for(spec, "low")
    assert [k["credits"] for k in r.json()["images"]] == [tek, tek, tek]


def test_bilinmeyen_model_422_ve_TURKCE(client):
    r = client.post("/api/generate", json={"prompt": "k", "size": "1024x1024",
                                           "quality": "medium", "n": 1,
                                           "model": "yok-boyle-model"})
    assert r.status_code == 422
    assert "yok-boyle-model" in r.text


def test_modelin_desteklemedigi_boyut_422_ve_GECERLILERI_soyluyor(client, genis_katalog):
    """"Geçersiz size" demek yetmiyor: geçerli küme artık modele göre değişiyor
    ve kullanıcı arayüzde göremediği bir kısıtla karşılaşabiliyor."""
    r = client.post("/api/generate", json={"prompt": "k", "size": "1024x1024",
                                           "quality": "standard", "n": 1,
                                           "model": genis_katalog.id})
    assert r.status_code == 422
    assert "1024x1792" in r.text, "geçerli boyutlar mesajda yok"


def test_modelin_azami_adedi_asilirsa_422(client, genis_katalog):
    r = client.post("/api/generate", json={"prompt": "k", "size": "1024x1792",
                                           "quality": "standard", "n": 2,
                                           "model": genis_katalog.id})
    assert r.status_code == 422
    assert "at most 1 images" in r.text


def test_ayni_deger_BIR_modelde_gecerli_DIGERINDE_degil(client, genis_katalog):
    """Kümelerin gerçekten modele bağlı olduğunun kanıtı — tek modelle
    ölçülemeyen tek şey bu."""
    ortak = {"prompt": "k", "quality": "medium", "n": 1}
    assert client.post("/api/generate", json={**ortak, "size": "1024x1024"}
                       ).status_code == 200
    assert client.post("/api/generate",
                       json={**ortak, "size": "1024x1024", "quality": "standard",
                             "model": genis_katalog.id}).status_code == 422


def test_bayat_SUNUCU_yeni_alani_gorunce_yuksek_sesle_422(client):
    """`extra="forbid"`'in ikinci faydalanıcısı `model`.

    Bu iddia doğrudan ölçülemiyor (bayat sunucu yok), ama sözleşmesi ölçülebilir:
    modelde tanımlı OLMAYAN bir alan sessizce yok sayılmıyor.
    """
    r = client.post("/api/generate", json={"prompt": "k", "size": "1024x1024",
                                           "quality": "medium", "n": 1,
                                           "boyle_bir_alan_yok": "x"})
    assert r.status_code == 422


# ── Multipart uç: /api/edit ────────────────────────────────────────────


def _png():
    return ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png")


def test_edit_model_alanini_kayda_YANKILIYOR(client, tmp_path, monkeypatch):
    """Bayat sunucu tespitinin dayanağı: yanıt gönderilen modeli geri veriyor.

    Multipart'ta `extra="forbid"` karşılığı YOK — Starlette bilinmeyen form
    alanını sessizce atar ve 200 döner. Palet için kurulan yankı hilesinin
    aynısı, ama karşılaştırma DEĞERİN kendisi üzerinden: yanlış model sessizce
    geçerse kullanıcı hem beklediği estetiği hem doğru faturayı kaybeder.
    """
    monkeypatch.setattr(gorsel, "to_png", lambda raw: b"\x89PNG")

    r = client.post("/api/edit",
                    data={"prompt": "k", "size": "1024x1024", "quality": "medium",
                          "n": "1", "model": catalog.DEFAULT_IMAGE_MODEL},
                    files={"file": _png()})

    assert r.status_code == 200, r.text
    assert r.json()["images"][0]["model"] == catalog.DEFAULT_IMAGE_MODEL
    assert r.json()["images"][0]["credits"] > 0


def test_edit_model_alani_YOKKEN_varsayilana_dusuyor(client, monkeypatch):
    """Bugünkü arayüz alanı hiç göndermiyor; davranışı aynen almalı."""
    monkeypatch.setattr(gorsel, "to_png", lambda raw: b"\x89PNG")

    r = client.post("/api/edit",
                    data={"prompt": "k", "size": "1024x1024",
                          "quality": "medium", "n": "1"},
                    files={"file": _png()})

    assert r.status_code == 200, r.text
    assert r.json()["images"][0]["model"] == catalog.DEFAULT_IMAGE_MODEL


def test_edit_duzenlemeyi_desteklemeyen_modeli_reddediyor(client, genis_katalog,
                                                         monkeypatch):
    """Kataloğa `supports_edit=False` bir model girdiği gün canlı olacak yol;
    bugün fikstürle ölçülüyor (bkz. `genis_katalog`)."""
    monkeypatch.setattr(gorsel, "to_png", lambda raw: b"\x89PNG")

    r = client.post("/api/edit",
                    data={"prompt": "k", "size": "1024x1792", "quality": "standard",
                          "n": "1", "model": genis_katalog.id},
                    files={"file": _png()})

    assert r.status_code == 422
    assert "does not work with a reference image" in r.text


def test_edit_adet_tavani_MODELDEN_geliyor_literal_4_ten_DEGIL(client, monkeypatch):
    """v0.6'ya kadar burada literal `4` vardı — `MAX_IMAGES_PER_RUN` için ikinci
    bir kaynak, yani sessiz bir kayma noktası.

    "Literal değil" iddiasını ölçmenin tek dürüst yolu tavanı 4'ten FARKLI bir
    modele bakmak: mesaj 2 diyorsa sayı gerçekten modelden geliyor. 4 ile test
    etmek, eski literal hâlâ yerinde olsa da geçerdi.
    """
    monkeypatch.setattr(gorsel, "to_png", lambda raw: b"\x89PNG")
    ikili = dataclasses.replace(catalog.IMAGE_MODELS[0], id="test-ikili", max_n=2)
    monkeypatch.setattr(catalog, "IMAGE_MODELS", catalog.IMAGE_MODELS + (ikili,))

    r = client.post("/api/edit",
                    data={"prompt": "k", "size": "1024x1024", "quality": "medium",
                          "n": "3", "model": "test-ikili"},
                    files={"file": _png()})

    assert r.status_code == 422
    assert "at most 2 images" in r.text, r.text
    # Küresel tavan da DURUYOR: model daha cömert olsa bile MAX_IMAGES_PER_RUN
    # aşılamaz (o sayı aynı zamanda bir sonuç kaydının azami image_ids uzunluğu).
    comert = dataclasses.replace(catalog.IMAGE_MODELS[0], id="test-comert", max_n=99)
    monkeypatch.setattr(catalog, "IMAGE_MODELS", catalog.IMAGE_MODELS + (comert,))
    r2 = client.post("/api/edit",
                     data={"prompt": "k", "size": "1024x1024", "quality": "medium",
                           "n": str(models.MAX_IMAGES_PER_RUN + 1),
                           "model": "test-comert"},
                     files={"file": _png()})
    assert r2.status_code == 422
    assert f"between 1 and {models.MAX_IMAGES_PER_RUN}" in r2.text, r2.text


# ── Yetenek kapısı iki uçta da AYNI ────────────────────────────────────


@pytest.mark.parametrize("size,quality,n,gecerli", [
    ("1024x1024", "medium", 1, True),
    ("9999x9999", "medium", 1, False),
    ("1024x1024", "ultra", 1, False),
    ("1024x1024", "medium", 99, False),
])
def test_iki_ucun_yetenek_karari_AYRISMIYOR(client, monkeypatch, size, quality, n,
                                            gecerli):
    """JSON ucu pydantic'ten, multipart uç elle geçiyor — ikisi de
    `models.check_capabilities`'i çağırdığı için karar tek yerde.

    İki kopya yazılsa arayüz bir boyutu sunar, bir uçta geçer, diğerinde 422
    döner ve kullanıcı hangisinin doğru olduğunu bilemez.
    """
    monkeypatch.setattr(gorsel, "to_png", lambda raw: b"\x89PNG")

    json_ok = client.post("/api/generate",
                          json={"prompt": "k", "size": size, "quality": quality,
                                "n": n}).status_code == 200
    form_ok = client.post("/api/edit",
                          data={"prompt": "k", "size": size, "quality": quality,
                                "n": str(n)},
                          files={"file": _png()}).status_code == 200

    assert json_ok is gecerli
    assert form_ok is gecerli, "multipart uç JSON ucundan ayrıştı"


# ── ORAN jetonu: uçtan uca ─────────────────────────────────────────────


def test_ORAN_jetonu_dogrulamadan_gecip_KAYDA_yazilabiliyor(client, monkeypatch):
    """`sizes` alanının docstring'i bu günü tarif ediyordu: jeton `WxH` değil.

    Zincirin tamamı ölçülüyor çünkü kırılabilecek yer bir tane değil:
    `check_capabilities` (kümede mi), `storage.save` (alanı koşulsuz yazıyor) ve
    `ResultParams.size` (allowlist'siz olması BU yüzden). İkinci bir
    `aspect_ratio` alanı açmamanın bedeli tam olarak bu testin ölçtüğü şey.
    """
    monkeypatch.setattr(appmod.providers, "generate",
                        lambda *a, **k: [b"\x89PNG"])
    m = catalog.image_model("gemini-nano-banana-2")

    r = client.post("/api/generate", json={"prompt": "kedi", "size": "21:9",
                                           "quality": "4K", "n": 1,
                                           "model": m.id})

    assert r.status_code == 200, r.text
    kayit = r.json()["images"][0]
    assert kayit["size"] == "21:9"
    assert kayit["model"] == m.id
    # Kredi ÜRETİM ANINDA çözülüyor: 4K'nın kendi tarifesi var, tabana düşmüyor.
    assert kayit["credits"] == catalog.cost_for(m, "4K") == 12


def test_ORAN_secen_modelde_PIKSEL_jetonu_reddediliyor(client, monkeypatch):
    """Kümeler GERÇEKTEN modele bağlı: Azure'ın jetonu Gemini'de geçmiyor.

    Geçse sağlayıcıya `aspect_ratio: "1024x1024"` giderdi ve kullanıcı 400'ün
    sebebini Ayarlar'da arardı.
    """
    monkeypatch.setattr(appmod.providers, "generate",
                        lambda *a, **k: [b"\x89PNG"])

    r = client.post("/api/generate", json={"prompt": "k", "size": "1024x1024",
                                           "quality": "2K", "n": 1,
                                           "model": "gemini-nano-banana-2"})

    assert r.status_code == 422
    assert "does not support this size" in r.text
