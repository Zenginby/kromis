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
    # SON KARE `supports_edit`i ŞART koşuyor: ilk kare olmadan son kare
    # anlamsız (neyin arasında geçiş yapılacağı yok) ve `app.animate` de
    # ana kareyi zorunlu tutuyor. Tersi serbest — ilk kareyi alan bir model
    # son kareyi almayabilir (Veo 3 ailesinin tamamı böyle).
    if m.supports_last_frame:
        assert m.supports_edit, f"{m.id}: son kare var, ilk kare yolu yok"


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


# ── Şeritte gösterilen KISA ad ──────────────────────────────────────────
#
# Sağlayıcı markası artık çipin solundaki işaretle geliyor (v0.8), yani etikette
# ikinci kez yazması gereksiz bir tekrar. Kısaltma SUNUCUDA yapılıyor; buradaki
# iddialar hem kuralı hem de tek istisnasını (çakışma) sabitliyor.


def test_KISA_ad_marka_onekini_dusuruyor():
    """Kural: `"{marka} · "` öneki düşüyor, geri kalanı aynen kalıyor."""
    kisa = catalog.short_labels(catalog.IMAGE_MODELS)
    assert kisa["gemini-nano-banana-2"] == "Nano Banana 2"
    assert kisa["gemini-nano-banana-pro"] == "Nano Banana Pro"
    sohbet = catalog.short_labels(catalog.CHAT_MODELS)
    assert sohbet["openai-gpt-5.6-terra"] == "GPT-5.6 Terra"
    assert sohbet["gemini-3.7-flash"] == "3.7 Flash"


def test_CAKISAN_ad_tam_etiketini_KORUYOR():
    """Tek istisna ve ölçülmüş bir kırılma: katalogda iki `gpt-image-2` var.

    Önek ikisinden de düşerse açılan listede AYNI iki satır oluşuyor ve native
    bir `<option>` işaret taşıyamadığı için logo onları ayırmıyor — yani ikisinin
    de anahtarı olan kullanıcı hangisini seçtiğini bilemez. Bu iddia, "önek her
    yerden düşsün" diye sadeleştiren bir sonraki turu kırmızıya çeviriyor.
    """
    kisa = catalog.short_labels(catalog.IMAGE_MODELS)
    assert kisa["azure-gpt-image-2"] == "Azure · gpt-image-2"
    assert kisa["openai-gpt-image-2"] == "OpenAI · gpt-image-2"
    # Aynı listede TEKİL olan `gpt-image-1` önekini bırakıyor: kural çakışmaya
    # bağlı, sağlayıcıya değil.
    assert kisa["openai-gpt-image-1"] == "gpt-image-1"


def test_MARKA_ADIN_PARCASI_olan_etiket_kirpilmiyor():
    """`Azure AI Foundry dağıtımı` aynen kalıyor: orada marka adın parçası.

    Kırpma `"içinde marka geçiyor mu"` diye çalışsaydı bu etiket
    `AI Foundry dağıtımı`ya dönerdi — Azure'da model değil DAĞITIM olduğu
    bilgisini taşıyan tek satır o.
    """
    assert catalog.short_labels(catalog.CHAT_MODELS)["azure-deployment"] == (
        "Azure AI Foundry dağıtımı")


@pytest.mark.parametrize(
    "models", [catalog.IMAGE_MODELS, catalog.CHAT_MODELS],
    ids=["gorsel", "sohbet"])
def test_KISA_ad_her_modelde_var_ve_BOS_DEGIL(models):
    """Şerit adsız satır çizemez: `id` başına dolu bir ad garanti.

    Markası `PROVIDER_BRANDS`ta yazmayan bir sağlayıcı eklenirse etiket AYNEN
    dönüyor (kırpma yok) — sessiz ama zararsız yol; boş dize ise şeritte
    görünmez bir satır demekti.
    """
    kisa = catalog.short_labels(models)
    assert set(kisa) == {m.id for m in models}
    assert all(ad.strip() for ad in kisa.values()), kisa


@pytest.mark.parametrize(
    "models", [catalog.IMAGE_MODELS, catalog.CHAT_MODELS],
    ids=["gorsel", "sohbet"])
def test_KISA_adlar_LISTE_ICINDE_tekil(models):
    """Asıl mandal: iki satır aynı metni GÖSTEREMEZ.

    Çakışma kuralı tam olarak bunu sağlamak için var; kural bozulursa (ya da
    katalogda üçüncü bir eşadlı model, örneğin bir `Gemini · gpt-image-2`
    doğarsa) burada kırmızı yanıyor.
    """
    adlar = list(catalog.short_labels(models).values())
    assert len(adlar) == len(set(adlar)), f"eşadlı satır: {adlar}"


@pytest.mark.parametrize(
    "models", [catalog.IMAGE_MODELS, catalog.CHAT_MODELS],
    ids=["gorsel", "sohbet"])
def test_KATALOGDAKI_her_saglayicinin_MARKA_ADI_yazili(models):
    """`PROVIDER_LOGOS` mandalının kardeşi ve aynı sessizliği kapatıyor.

    Marka adı eksik olan bir sağlayıcı hata vermiyor — etiket AYNEN dönüyor,
    yani önek ekranda kalıyor ve satır işaretin yanında markayı ikinci kez
    yazıyor. Tam olarak bu turun düzelttiği kusur, yalnız bir sonraki
    sağlayıcıda. Görülebilir tek yer burası.
    """
    eksik = {m.provider for m in models if m.provider not in catalog.PROVIDER_BRANDS}
    assert not eksik, (
        "marka adı yazılmayan sağlayıcı: " + ", ".join(sorted(eksik))
        + ". catalog.PROVIDER_BRANDS'e bir satır gerekiyor, yoksa şerit "
          "satırında marka öneki ekranda kalır.")


# ── Video kataloğu (v0.13) ─────────────────────────────────────────────


def test_the_two_model_families_NEVER_share_an_id():
    """`catalog.image_model()` ve `video_model()` iki AYRI demeti tarıyor ve
    çakışan bir id, çağıranın hangisini bulacağını arama sırasına bırakırdı."""
    gorsel = set(catalog.image_model_ids())
    video = set(catalog.video_model_ids())

    assert gorsel.isdisjoint(video), f"iki demette birden: {gorsel & video}"


def test_no_VIDEO_model_leaks_into_the_image_catalog():
    """Ayrı demetin BÜTÜN gerekçesi bu (bkz. VIDEO_MODELS'in başlığı): bir
    video girdisi `IMAGE_MODELS`a düşse `/api/generate`de seçilebilir olurdu
    — senkron bir görsel ucuna 7 dakikalık bir video isteği."""
    assert all(m.kind == "image" for m in catalog.IMAGE_MODELS)
    assert all(m.kind == "video" for m in catalog.VIDEO_MODELS)
    assert catalog.video_model(catalog.DEFAULT_IMAGE_MODEL) is None
    assert catalog.image_model(catalog.DEFAULT_VIDEO_MODEL) is None


def test_the_default_video_model_is_IN_the_catalog():
    assert catalog.video_model(catalog.DEFAULT_VIDEO_MODEL) is not None


def test_the_default_video_model_is_the_CHEAPEST_tier():
    """Görsel tarafında varsayılan "en güçlü"; burada değil — ayrımın sebebi
    fiyat farkının BÜYÜKLÜĞÜ: yanlışlıkla atılan tek bir tık lite'ta 4 saniye
    için ~0,32 USD, kalite kademesinde ~1,60 USD. Bir görselde o fark
    sentlerle ölçülüyordu."""
    varsayilan = catalog.video_model(catalog.DEFAULT_VIDEO_MODEL)

    assert varsayilan.credits == min(m.credits for m in catalog.VIDEO_MODELS)
    # SIRA da artan maliyete göre: ilk girdi varsayılan.
    assert catalog.VIDEO_MODELS[0].id == catalog.DEFAULT_VIDEO_MODEL
    krediler = [m.credits for m in catalog.VIDEO_MODELS]
    assert krediler == sorted(krediler), f"sıra artan maliyette değil: {krediler}"


@pytest.mark.parametrize("m", catalog.VIDEO_MODELS, ids=lambda m: m.id)
def test_every_video_model_declares_what_the_pipeline_needs(m):
    """Video yolunun ÇALIŞMASI için gereken beyanlar. Biri eksik olsa
    kırılma çalışma anında ve pahalı bir yerde görünürdü."""
    # Kimlik `CREDENTIALS`ta olmalı, yoksa `credstore.resolve` patlar.
    assert catalog.credential(m.credential) is not None
    # Adaptörü olmayan bir sağlayıcı, seçilebilir bir çalışma-anı hatası.
    import providers
    assert m.provider in providers.video_adapter_ids()
    # `poll_timeout` YOKSA `total_budget` görselin formülüne düşer (180 sn) ve
    # dakikalarca süren bir üretim her seferinde zaman aşımına uğrar.
    assert m.poll_timeout, "poll_timeout yok — döngünün tavanı görselin formülü olur"
    # Süre ekseni olmayan bir video modeli, `durationSeconds`ı gönderemez.
    assert m.durations, "durations boş"
    assert catalog.default_duration_of(m) in m.durations
    # `qualities` HİÇ boş olamıyor (ResultParams `min_length=1`).
    assert m.qualities
    assert catalog.default_quality_of(m) in m.qualities
    assert catalog.default_size_of(m) in m.sizes


def test_the_video_credits_are_PER_SECOND():
    """`credits` alanının birimi `kind`e BAĞLI ve ayrım `cost_for`da yaşıyor.
    Video tarafında üretim-başına yazmak, süre ekseni olan bir modelde
    etiketi anlamsız kılardı: 4 sn ile 8 sn aynı krediyi gösterir, fatura
    iki katı olurdu."""
    m = catalog.video_model(catalog.DEFAULT_VIDEO_MODEL)

    assert catalog.cost_for(m, "720p", 1, duration=4) == m.credits * 4
    assert catalog.cost_for(m, "720p", 1, duration=8) == m.credits * 8
    # Görsel yolu DEĞİŞMEDİ: süre verilmeyen çağrı üretim-başına kalıyor.
    g = catalog.IMAGE_MODELS[0]
    assert catalog.cost_for(g, "medium", 2) == \
        dict(g.credits_by_quality)["medium"] * 2


def test_a_ZERO_duration_never_zeroes_the_cost():
    """0 ve None aynı anlamda ("süre ekseni yok") ve çarpan olarak 0
    kullanmak, ücretsiz görünen bir video demekti."""
    m = catalog.video_model(catalog.DEFAULT_VIDEO_MODEL)

    assert catalog.cost_for(m, "720p", 1, duration=0) == m.credits
    assert catalog.cost_for(m, "720p", 1) == m.credits


def test_the_video_aspect_ratios_are_a_SUBSET_of_the_documented_ones():
    """Veo yalnız iki oran kabul ediyor; `ASPECT_RATIOS`in onu buraya
    KOPYALANMADI — doğrulanmamış bir jeton, arayüzde seçilebilir bir 400."""
    for m in catalog.VIDEO_MODELS:
        assert set(m.sizes) == set(catalog.VIDEO_ASPECT_RATIOS)
        assert set(m.sizes) <= set(catalog.ASPECT_RATIOS), (
            "video oranları GEOMETRY_LABELS'ın tanıdığı kümenin dışına çıktı — "
            "etiket çıplak jetona düşer")


def test_the_duration_axis_is_EMPTY_for_every_image_model():
    """Arayüz süre satırının kapısını listenin BOŞLUĞUNDAN okuyor."""
    for m in catalog.IMAGE_MODELS:
        assert m.durations == ()
        assert catalog.default_duration_of(m) == 0


def test_every_video_quality_token_has_a_LABEL():
    """Bilinmeyen jeton hata değil (etiketi kendisi olur) ama çirkin: video
    seçicisinde "720p · HD" ile çıplak "720p" arasındaki fark, kalite
    ekseninin okunabilirliği."""
    for m in catalog.VIDEO_MODELS:
        for q in m.qualities:
            assert catalog.quality_label(q) != q, f"{q} etiketsiz"


@pytest.mark.parametrize(
    "models", [catalog.VIDEO_MODELS], ids=["video"])
def test_VIDEO_kisa_adlari_LISTE_ICINDE_tekil(models):
    """Görsel/sohbet şeritlerinin aynı mandalı: iki satır aynı metni
    GÖSTEREMEZ. Kısa adlar şerit BAŞINA hesaplanıyor (`app._settings_payload`),
    yani çakışma kuralı bu listenin kendi içinde çalışmak zorunda."""
    adlar = list(catalog.short_labels(models).values())
    assert len(adlar) == len(set(adlar)), f"eşadlı satır: {adlar}"


def test_the_video_providers_all_have_a_LOGO():
    """`tests/test_provider_logos.py` adaptörü olan her sağlayıcı için dosya
    arıyor; video sağlayıcıları o taramaya `providers.video_adapter_ids()`
    üzerinden GİRMİYOR, o yüzden ikinci bir mandal burada."""
    for m in catalog.VIDEO_MODELS:
        assert catalog.provider_logo(m.provider), (
            f"{m.provider} işaretsiz — şerit işaretsiz çizilir")
        assert m.provider in catalog.PROVIDER_BRANDS
