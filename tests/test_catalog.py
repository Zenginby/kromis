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


def test_katalogdaki_her_alan_adi_ayarlar_formunda_var():
    """Katalog ↔ `SettingsRequest` eşlemesi tripwire.

    `app.post_settings` yazma yolunu `cred.secret_field` / `cred.url_field`
    üzerinden kuruyor ve `getattr(req, ...)` ile okuyor. Katalogda var olup
    formda olmayan bir ad SESSİZCE hiç yazılmaz — anahtar kaydedildi sanılır,
    üretim "anahtar yok" der ve ikisi arasındaki bağ görünmez.
    """
    from models import SettingsRequest

    alanlar = set(SettingsRequest.model_fields)
    for cred in catalog.CREDENTIALS:
        if cred.secret_field:
            assert cred.secret_field in alanlar, (
                f"{cred.id}: `{cred.secret_field}` SettingsRequest'te yok")
        if cred.url_field:
            assert cred.url_field in alanlar, (
                f"{cred.id}: `{cred.url_field}` SettingsRequest'te yok")


def test_adres_alani_beyan_eden_kimligin_url_env_i_de_var():
    """`url_field` varsa yazılacak bir env adı da olmalı.

    Biri olmadan diğeri: `post_settings` `updates[None] = ...` yazar ve
    `save_env` çağrısı anlamsız bir anahtar üretir.
    """
    for cred in catalog.CREDENTIALS:
        if cred.url_field:
            assert cred.url_env, f"{cred.id}: url_field var, url_env yok"


def test_adressiz_kimligin_varsayilan_adresi_var():
    """Kullanıcı adres giremiyorsa katalog bir adres SAĞLAMAK zorunda.

    Yoksa anahtarı kaydeden kullanıcı "adres yok" hatası alır ve formda
    dolduracak bir kutu bulamaz — çıkışı olmayan bir hata.
    """
    for cred in catalog.CREDENTIALS:
        if cred.id.startswith("azure"):
            continue    # Azure'da adres FORMDA sorulur, varsayılanı yok
        assert cred.default_base_url, f"{cred.id}: ne varsayılan adres ne form alanı"


# ── Varsayılan jetonlar ve etiketler ───────────────────────────────────


@pytest.mark.parametrize("m", catalog.IMAGE_MODELS, ids=lambda m: m.id)
def test_varsayilan_jetonlar_MODELIN_kumesinde(m):
    """`default_size`/`default_quality` beyan edilen kümeden OLMAK zorunda.

    v0.6'ya kadar ölçülmeyen bir boşluktu ve bedeli sessiz: arayüz `fillAxis`
    ile o değeri arıyor, bulamıyor ve "model bu ayarları desteklemiyor,
    varsayılana düşüldü" diyor — yani modelin KENDİ varsayılanı için düşme
    uyarısı basıyor. Gemini girdileri `default_size`ı açıkça yazan ilk
    girdiler olduğu için kapı burada kuruldu.
    """
    assert catalog.default_size_of(m) in m.sizes, (
        f"{m.id}: varsayılan boyut kümesinde yok")
    assert catalog.default_quality_of(m) in m.qualities, (
        f"{m.id}: varsayılan kalite kümesinde yok")


@pytest.mark.parametrize("m", catalog.IMAGE_MODELS, ids=lambda m: m.id)
def test_beyan_edilen_her_jetonun_TURKCE_etiketi_var(m):
    """Bilinmeyen jetonun etiketi kendisi olur (`geometry_of`) ve bu bilinçli
    bir SAĞLAMLIK kararı — ama KENDİ katalogumuzdaki bir jetonun etiketsiz
    kalması ayrı bir şey: seçicide "9:16" satırı Azure'ın "◼ 1:1" satırıyla
    aynı hizada durmuyor ve kalite ekseninde çıplak jeton ("2K") Türkçe
    listenin ortasında yabancı görünüyor.
    """
    for jeton in m.sizes:
        assert jeton in catalog.GEOMETRY_LABELS, (
            f"{m.id}: `{jeton}` GEOMETRY_LABELS'ta yok")
    for jeton in m.qualities:
        assert jeton in catalog.QUALITY_LABELS, (
            f"{m.id}: `{jeton}` QUALITY_LABELS'ta yok")


def test_gemini_oranlari_AZURE_nun_uc_boyutunun_karsiligini_tasiyor():
    """Model değiştirmek ORANI TAŞIMALI, varsayılana düşmemeli.

    core.js'in `fillAxis` fonksiyonunun ikinci kademesi `ratio` üzerinden
    çalışıyor: Azure'ın `1024x1536`ı da Gemini'nin `2:3`ü de aynı oranı
    bildiriyorsa geçiş SESSİZ oluyor. Bir oran eksik kalırsa kullanıcı model
    değiştirdiğinde sebepsiz bir "varsayılana düşüldü" uyarısı görür.
    """
    azure = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    azure_oranlari = {catalog.geometry_of(s)[1] for s in azure.sizes}
    gemini_oranlari = {catalog.geometry_of(s)[1] for s in catalog.ASPECT_RATIOS}

    assert azure_oranlari <= gemini_oranlari, (
        "Azure'dan Gemini'ye geçişte karşılığı olmayan oran: "
        f"{sorted(azure_oranlari - gemini_oranlari)}")


def test_oran_jetonlari_TEK_kaynaktan_geliyor():
    """İki Gemini girdisi aynı demeti paylaşıyor: elle iki kez yazmak, birine
    oran ekleyip diğerini unutmanın kapısı olurdu."""
    gemini = [m for m in catalog.IMAGE_MODELS if m.provider == "gemini"]
    assert gemini, "katalogda Gemini modeli yok"
    for m in gemini:
        assert m.sizes is catalog.ASPECT_RATIOS, (
            f"{m.id}: oranları kopyalamış, ASPECT_RATIOS'u paylaşmıyor")


# ── Kalkmış modeller ───────────────────────────────────────────────────


@pytest.mark.parametrize("olu", ["dall-e-3", "dall-e-2"])
def test_KALKMIS_model_adlari_katalogda_yok(olu):
    """Ölmüş bir girdiyi katalogda tutmanın bedeli ÖLÇÜLDÜ: kullanıcı
    seçebiliyor, üretim 404 alıyor ve hata "model bulunamadı" diyor — yani
    kullanıcı hatayı kendi anahtarında arıyor.

    `dall-e-2`/`dall-e-3` 12 Mayıs 2026'da OpenAI API'sinden kalktı. Bu test
    girdinin geri EKLENMESİNE karşı bir tripwire; `wire_model`e bakıyor çünkü
    kimliği (`openai-dall-e-3`) yeniden adlandırmak kapıyı açık bırakırdı.
    """
    assert olu not in {m.wire_model for m in catalog.IMAGE_MODELS}


# ── Sohbet modelleri (v0.7: yönetmen çoklu sağlayıcı) ──────────────────


def test_varsayilan_sohbet_modeli_listenin_basinda():
    """Sıra seçicinin sırası ve varsayılan başta durmalı — görsel tarafın kuralı.

    Ayrıca somut bir güvence: varsayılanı listenin ortasına almak, kayıtlı
    Azure kullanıcısının yönetmenini sessizce başka bir sağlayıcıya (yani başka
    bir faturaya) taşımanın en sessiz yolu.
    """
    assert catalog.CHAT_MODELS[0].id == catalog.DEFAULT_CHAT_MODEL
    assert catalog.CHAT_MODELS[0].provider == catalog.DEFAULT_CHAT_PROVIDER


@pytest.mark.parametrize("m", catalog.CHAT_MODELS, ids=lambda m: m.id)
def test_sohbet_modelinin_adi_TEK_kaynaktan_geliyor(m):
    """`wire_model` ile `wire_from_env` AYNI ANDA dolu olamaz.

    İkisi de doluysa hangisinin kazandığı `chat_providers.wire_model_of`'un
    satır sırasına kalır ve o sıra bir gün değişirse kullanıcının Ayarlar'a
    yazdığı dağıtım adı sessizce yok sayılır — istek 404 döner ve sebebi
    görünmez olur. Kural tek cümle: adı ya katalog bilir ya kullanıcı.
    """
    assert bool(m.wire_model) != bool(m.wire_from_env), (
        f"{m.id}: adın kaynağı belirsiz "
        f"(wire_model={m.wire_model!r}, wire_from_env={m.wire_from_env!r})")


@pytest.mark.parametrize("m", catalog.CHAT_MODELS, ids=lambda m: m.id)
def test_dagitim_adi_KAPISI_ortamdan_okumayla_ayni_sey(m):
    """`chat_needs_deployment` tek bir olguya bakıyor: ad ortamdan mı okunuyor.

    Ayarlar formundaki dağıtım kutusunun kapısı bu bayrak (bkz. settings.js
    `syncChatDeployField`). İkinci bir ölçüte (sağlayıcı adı, bir `needs_*`
    alanı) kaymak, kutuyu adı ortamdan okuyan İKİNCİ bir sağlayıcıda sessizce
    görünmez bırakırdı — yani o sağlayıcı hiç yapılandırılamazdı.
    """
    assert catalog.chat_needs_deployment(m) is bool(m.wire_from_env)


@pytest.mark.parametrize("m", catalog.CHAT_MODELS, ids=lambda m: m.id)
def test_sohbet_yolu_CHAT_COMPLETIONS_ucuna_cikiyor(m):
    """Üç sağlayıcının teli AYNI ve adaptör bunu VARSAYIYOR.

    `openai_chat.complete` gövdeyi `chat_client.build_payload` ile kuruyor ve
    yanıtı `extract_content` ile okuyor: ikisi de `/chat/completions`
    sözleşmesi. Başka bir uç (`/v1/messages`, `/v1beta/interactions`) o
    fonksiyonlarla konuşamaz — Anthropic'in katalogda olmama gerekçesi tam
    olarak bu. Yol buraya girerse adaptör de yazılmış olmalı.
    """
    assert m.endpoint_path.startswith("/"), "yol göreli olamaz (base_url'e ekleniyor)"
    assert m.endpoint_path.endswith("/chat/completions"), (
        f"{m.id}: {m.endpoint_path} — OpenAI-uyumlu olmayan bir uç için "
        "`openai_chat` yerine kendi adaptörü gerekiyor")


@pytest.mark.parametrize(
    "m", catalog.IMAGE_MODELS + catalog.CHAT_MODELS, ids=lambda m: m.id)
def test_PREVIEW_jetonu_beyan_edilmiyor(m):
    """"preview" adları geçici: GA olurken kalkıyorlar ve arayüzde seçilebilir
    bir 404 bırakıyorlar — DALL·E 3'ün katalogdan çıkarılma gerekçesinin
    aynısı, yalnız daha hızlı olanı.

    Somut örnek bu turda ölçüldü: Gemini'nin Pro sohbet modeli bugün yalnız
    `gemini-3.1-pro-preview` olarak var, o yüzden katalogda YOK. Kural yazılı
    olmasa bir sonraki tur onu "en güçlü Gemini" diye eklerdi.
    """
    assert "preview" not in (m.wire_model or "").lower(), (
        f"{m.id}: preview jetonu beyan edilmiş ({m.wire_model})")
