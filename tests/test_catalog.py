"""Model kataloğunun kendi sözleşmesi + `azure_client` ile ayrışma mandalı.

Katalog saf veri, o yüzden buradaki testler "çalışıyor mu"yu değil TUTARLILIĞI
ölçüyor: bir girdi eksik/çelişkili beyan edilirse bunun bedeli çalışma anında
sessiz bir 422 ya da kaydedilemeyen bir oturum olur.
"""
import ast
import pathlib

import pytest

import azure_client as ac
import catalog
import models


def test_katalog_yaprak_kalmali():
    """Katalog PROJE İÇİNDEN hiçbir şey import etmemeli.

    Bu testin varlık sebebi mekanik: katalog `models.py`, `prefs.py`,
    `storage.py` ve her adaptör tarafından import ediliyor. Bir gün buraya
    `import azure_client` girerse döngü riski geri gelir ve kataloğu `paths`
    olmadan test etmek imkânsızlaşır. `version.py`'nin bağımlılıksızlığını
    zorlayan testin (tests/test_version.py) kardeşi.

    Kaynak AST ile taranıyor, `sys.modules`'e bakılmıyor: import zaten
    gerçekleşmişse geç kalınmış olurdu.
    """
    root = pathlib.Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "catalog.py").read_text(encoding="utf-8"))
    # Kök dizindeki .py dosyaları = projenin modül adları (Android'in
    # `include "*.py"` deseniyle aynı küme).
    proje = {p.stem for p in root.glob("*.py")} - {"catalog"}

    bulunan = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bulunan.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            bulunan.add(node.module.split(".")[0])

    assert not (bulunan & proje), (
        f"catalog.py yaprak olmaktan çıktı: {sorted(bulunan & proje)}")


def test_azure_girdisi_azure_client_ile_ayrismiyor():
    """Tripwire: katalogdaki Azure yetenekleri ile `azure_client`'ın sabitleri.

    İkisi de duruyor ve ikisi de okunuyor — `ALLOWED_SIZES`/`ALLOWED_QUALITIES`
    hâlâ `app._check_edit_form`'da ve kendi testlerinde kullanılıyor. Kopya
    BİLİNÇLİ (katalog yaprak kalsın diye, dosyanın başındaki not), ama kayma
    ölçülmek zorunda: biri değişip diğeri kalırsa arayüz bir boyutu sunar,
    sunucu 422 döner ve sebebi görünmez olur.

    `models.LOGO_OFFSET_LIMIT` ↔ `composite.OFFSET_LIMIT` deseninin aynısı.
    """
    m = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    assert m is not None
    assert set(m.sizes) == ac.ALLOWED_SIZES
    assert set(m.qualities) == ac.ALLOWED_QUALITIES
    assert m.wire_model == ac.MODEL_NAME


def test_kimlik_env_adlari_azure_client_ile_ayrismiyor():
    """Aynı tripwire, kimlik tarafı: env adları iki yerde birden yazılı."""
    assert catalog.credential("azure_image").key_env == ac.IMAGE_KEY
    assert catalog.credential("azure_image").url_env == ac.IMAGE_URL
    assert catalog.credential("azure_chat").key_env == ac.CHAT_KEY
    assert catalog.credential("azure_chat").url_env == ac.CHAT_URL
    assert (catalog.chat_model(catalog.DEFAULT_CHAT_MODEL).wire_from_env
            == ac.CHAT_DEPLOYMENT)


def test_id_ler_tekil():
    assert len(catalog.image_model_ids()) == len(set(catalog.image_model_ids()))
    assert len(catalog.chat_model_ids()) == len(set(catalog.chat_model_ids()))


def test_varsayilanlar_katalogda_var():
    """Varsayılan bir modele işaret etmiyorsa `prefs` ilk açılışta çöker."""
    assert catalog.image_model(catalog.DEFAULT_IMAGE_MODEL) is not None
    assert catalog.chat_model(catalog.DEFAULT_CHAT_MODEL) is not None
    assert catalog.DEFAULT_CHAT_PROVIDER in catalog.chat_provider_ids()


def test_varsayilan_gorsel_modeli_listenin_basinda():
    """Sıra arayüzdeki seçicinin sırası; varsayılan başta durmalı."""
    assert catalog.IMAGE_MODELS[0].id == catalog.DEFAULT_IMAGE_MODEL


@pytest.mark.parametrize("m", catalog.IMAGE_MODELS, ids=lambda m: m.id)
def test_her_gorsel_modeli_tutarli_beyan_ediyor(m):
    """Kalite ekseni HİÇ boş olamaz ve `max_n` küresel tavanı aşamaz.

    Boş `qualities`: `ResultParams.quality` `min_length=1` istiyor, yani o
    modelle üretilmiş oturum BİR DAHA KAYDEDİLEMEZ olurdu (bkz. catalog.py'deki
    gerekçe). `max_n` tavanı: `MAX_IMAGES_PER_RUN` aynı zamanda bir sonuç
    kaydının azami `image_ids` uzunluğu — aşan bir model dökümü bozardı.
    """
    assert m.sizes, "en az bir geometri jetonu gerekli"
    assert m.qualities, "en az bir kalite jetonu gerekli (bkz. karar Q1)"
    assert 1 <= m.max_n <= models.MAX_IMAGES_PER_RUN
    assert m.images_per_request >= 1
    assert catalog.credential(m.credential) is not None, m.credential
    # Kalite bazlı tarife yalnız BEYAN EDİLMİŞ kaliteler için yazılabilir;
    # yoksa `cost_for` sessizce tabana düşer ve tarife yazılmamış gibi olur.
    assert set(dict(m.credits_by_quality)) <= set(m.qualities)
    if m.quality_hidden:
        assert len(m.qualities) == 1, "gizli eksen tek jeton taşımalı"
    if m.supports_edit:
        assert m.max_refs >= 1


@pytest.mark.parametrize("m", catalog.CHAT_MODELS, ids=lambda m: m.id)
def test_her_sohbet_modeli_bir_ada_cozuluyor(m):
    """`wire_model` boşsa ORTAMDAN okunacak bir ad beyan edilmiş olmalı."""
    assert m.wire_model or m.wire_from_env, "modelin adı hiçbir yerden gelmiyor"
    assert catalog.credential(m.credential) is not None, m.credential


def test_cost_for_kaliteye_gore_ve_adetle_carpiyor():
    m = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    assert catalog.cost_for(m, "low") == 4
    assert catalog.cost_for(m, "high") == 16
    assert catalog.cost_for(m, "high", 3) == 48


def test_cost_for_bilinmeyen_kalitede_tabana_dusuyor_hata_YUKSELTMIYOR():
    """Maliyet metadata'sı bir üretimi ENGELLEMEMELİ (bkz. cost_for docstring)."""
    m = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    assert catalog.cost_for(m, "boyle-bir-kalite-yok") == m.credits


def test_bilinmeyen_id_None_donuyor():
    assert catalog.image_model("yok") is None
    assert catalog.chat_model("yok") is None
    assert catalog.credential("yok") is None


def test_gizli_alan_ve_env_adlari_turetiliyor():
    """Redaksiyon ve log sansürü BU kümelerden besleniyor.

    Elle tutulan bir liste BYOK üçlüsünü kapsamamıştı; katalogdan türetildiği
    için bundan sonra bir sağlayıcı beyan etmek ikisini de kendiliğinden
    genişletiyor. Adres alanı DIŞARIDA: endpoint gizli değil.
    """
    assert "api_key" in catalog.secret_field_names()
    assert catalog.secret_env_names() >= {ac.IMAGE_KEY, ac.CHAT_KEY}
    assert ac.IMAGE_URL not in catalog.secret_env_names()
