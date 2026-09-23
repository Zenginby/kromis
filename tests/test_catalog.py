"""Model kataloğunun kendi sözleşmesi + `azure_client` ile ayrışma mandalı.

Katalog saf veri, o yüzden buradaki testler "çalışıyor mu"yu değil TUTARLILIĞI
ölçüyor: bir girdi eksik/çelişkili beyan edilirse bunun bedeli çalışma anında
sessiz bir 422 ya da kaydedilemeyen bir oturum olur.
"""
import ast
import pathlib

import pytest

import azure_client as ac
import azure_flux_client as flux_client
import catalog
import etiket
import i18n
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
    """Kalite eşlemesi ve adetle çarpım — beklenen sayılar KATALOGDAN türetilir.

    Burada üç literal yazılıydı (4/16/48) ve tarife her düzeltildiğinde test
    düşüyordu: 2026-09-22'de `gpt-image-2`nin çıktı jetonu ölçülüp krediler
    4/8/16 → 1/10/42 olunca da düştü. Oysa sınanan şey tarifenin DEĞERİ değil,
    `cost_for`un kaliteyi bulup adetle çarpması; değerin bekçisi katalogdaki
    yorum ve `tools/tarife_kontrol.py`.
    """
    m = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    kalite = dict(m.credits_by_quality)
    assert catalog.cost_for(m, "low") == kalite["low"]
    assert catalog.cost_for(m, "high") == kalite["high"]
    assert catalog.cost_for(m, "high", 3) == kalite["high"] * 3
    # Kademeler AYRIŞMALI: eşit olsalar üstteki üç iddia da boşa döner.
    assert kalite["low"] < kalite["high"]


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
    kisa = etiket.short_labels(catalog.IMAGE_MODELS)
    assert kisa["gemini-nano-banana-2"] == "Nano Banana 2"
    assert kisa["gemini-nano-banana-pro"] == "Nano Banana Pro"
    sohbet = etiket.short_labels(catalog.CHAT_MODELS)
    assert sohbet["openai-gpt-5.6-terra"] == "GPT-5.6 Terra"
    assert sohbet["gemini-3.7-flash"] == "3.7 Flash"


def test_CAKISAN_ad_tam_etiketini_KORUYOR():
    """Tek istisna ve ölçülmüş bir kırılma: katalogda iki `gpt-image-2` var.

    Önek ikisinden de düşerse açılan listede AYNI iki satır oluşuyor ve native
    bir `<option>` işaret taşıyamadığı için logo onları ayırmıyor — yani ikisinin
    de anahtarı olan kullanıcı hangisini seçtiğini bilemez. Bu iddia, "önek her
    yerden düşsün" diye sadeleştiren bir sonraki turu kırmızıya çeviriyor.
    """
    kisa = etiket.short_labels(catalog.IMAGE_MODELS)
    assert kisa["azure-gpt-image-2"] == "Azure · gpt-image-2"
    assert kisa["openai-gpt-image-2"] == "OpenAI · gpt-image-2"
    # Aynı listede TEKİL olan `Nano Banana 2` önekini bırakıyor: kural çakışmaya
    # bağlı, sağlayıcıya değil. (Bu rol `openai-gpt-image-1`deydi; girdi
    # 2026-09-21'de emekliliğinden önce silindi — Faz 4 / 1.)
    assert kisa["gemini-nano-banana-2"] == "Nano Banana 2"


def test_MARKA_ADIN_PARCASI_olan_etiket_kirpilmiyor():
    """`Azure AI Foundry dağıtımı` aynen kalıyor: orada marka adın parçası.

    Kırpma `"içinde marka geçiyor mu"` diye çalışsaydı bu etiket
    `AI Foundry dağıtımı`ya dönerdi — Azure'da model değil DAĞITIM olduğu
    bilgisini taşıyan tek satır o.
    """
    assert etiket.short_labels(catalog.CHAT_MODELS)["azure-deployment"] == (
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
    kisa = etiket.short_labels(models)
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
    adlar = list(etiket.short_labels(models).values())
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
    sentlerle ölçülüyordu.

    GÖREV 7 İLE SÜZGEÇ EKLENDİ ("en ucuz" artık yalnız Gemini bloğunda
    ölçülüyor): fal ölçüldüğünde PixVerse'in 720p'si (13 kredi) Veo Lite'ın
    16'sından GERÇEKTEN ucuz çıktı — yani "varsayılan = katalogdaki en ucuz
    GİRDİ" iddiası artık YANLIŞ, üçüncü taraf bir toplayıcı eklenince
    kaçınılmaz olarak böyle. Varsayılanın Veo Lite'ta KALMASININ gerekçesi de
    değişti: artık "en ucuz" değil, `test_the_default_video_model_is_UNCHANGED`
    testinin söylediği gibi "mevcut kullanıcının bir sonraki tıkına
    dokunmamak". Bu testin sorabileceği tek doğru soru "Veo ailesi kendi
    içinde artan mı" — fal'ın kendi sırası ayrı testte
    (`test_fal_video_models_are_ordered_by_ASCENDING_cost`) mandallı.
    """
    varsayilan = catalog.video_model(catalog.DEFAULT_VIDEO_MODEL)
    gemini = [m for m in catalog.VIDEO_MODELS if m.provider == "gemini"]

    assert varsayilan.credits == min(m.credits for m in gemini)
    # SIRA İDDİASI DÜŞTÜ (2026-09-23, Faz 4 / 1b-D): burada "ilk girdi
    # varsayılan" ve "Gemini bloğu artan maliyette" yazıyordu. Katalog artık
    # sahibin sıralı listesi (kaliteli → ucuz) ve varsayılan 10. sırada — sıra
    # ile varsayılan KODDA AYRI (`test_the_video_catalog_follows_the_owners_
    # RANKED_list`, `test_the_defaults_are_CONSTANTS_not_index_zero`).


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


def test_the_video_aspect_ratios_match_each_PROVIDERS_declared_set():
    """Veo yalnız iki oran kabul ediyor; `ASPECT_RATIOS`in onu buraya
    KOPYALANMADI — doğrulanmamış bir jeton, arayüzde seçilebilir bir 400.

    GÖREV 7 İLE SAĞLAYICI BAŞINA AYRIŞTI (eski adı
    `..._are_a_SUBSET_of_the_documented_ones`, tek sağlayıcı varken
    "eşit" ile "alt küme" aynı şeydi): fal `FAL_VIDEO_ASPECT_RATIOS` ile
    BİLEREK bir jeton FAZLA beyan ediyor (`1:1`, `catalog.py`'nin
    `FAL_VIDEO_ASPECT_RATIOS` yorumundaki gerekçeyle) — yani "her video
    modelinin oranı Veo'nunkiyle birebir aynı" iddiası artık YANLIŞ. Asıl
    korunan şey duruyor: her sağlayıcının seti KENDİ beyan ettiği demetle
    birebir eşleşiyor ve o set dokümante edilmiş `ASPECT_RATIOS`ın dışına
    taşmıyor.
    """
    for m in catalog.VIDEO_MODELS:
        beklenen = (catalog.FAL_VIDEO_ASPECT_RATIOS if m.provider == "fal"
                    else catalog.VIDEO_ASPECT_RATIOS)
        assert set(m.sizes) == set(beklenen), f"{m.id} kendi sağlayıcısının oran setiyle eşleşmiyor"
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
            assert etiket.quality_label(q) != q, f"{q} etiketsiz"


@pytest.mark.parametrize(
    "models", [catalog.VIDEO_MODELS], ids=["video"])
def test_VIDEO_kisa_adlari_LISTE_ICINDE_tekil(models):
    """Görsel/sohbet şeritlerinin aynı mandalı: iki satır aynı metni
    GÖSTEREMEZ. Kısa adlar şerit BAŞINA hesaplanıyor (`app._settings_payload`),
    yani çakışma kuralı bu listenin kendi içinde çalışmak zorunda."""
    adlar = list(etiket.short_labels(models).values())
    assert len(adlar) == len(set(adlar)), f"eşadlı satır: {adlar}"


def test_the_video_providers_all_have_a_LOGO():
    """`tests/test_provider_logos.py` adaptörü olan her sağlayıcı için dosya
    arıyor; video sağlayıcıları o taramaya `providers.video_adapter_ids()`
    üzerinden GİRMİYOR, o yüzden ikinci bir mandal burada."""
    for m in catalog.VIDEO_MODELS:
        assert catalog.provider_logo(m.provider), (
            f"{m.provider} işaretsiz — şerit işaretsiz çizilir")
        assert m.provider in catalog.PROVIDER_BRANDS


# ── Azure AI Foundry · MAI (v0.15) ─────────────────────────────────────


def test_MAI_jetonlari_PIKSEL_butcesine_uyuyor():
    """Bu testin ölçtüğü şey bir GÜVENLİK SINIRI, bir kolaylık değil.

    MAI hatalı bir `size` gönderildiğinde 400 DÖNMÜYOR, sessizce varsayılanla
    üretiyor — sondada ölçüldü (`size:"1x1"` yutuldu, iki gerçek görsel
    üretildi ve faturalandı). Yani sağlayıcı bir doğrulama katmanı değil;
    `models.check_capabilities` TEK kapı ve o da katalogdan besleniyor.
    Buradaki bir hata kullanıcıya hata değil, İSTEMEDİĞİ BOYUTTA BİR FATURA
    gösterir.
    """
    for jeton in catalog.MAI_SIZES:
        w, h = (int(p) for p in jeton.split("x"))
        assert w >= catalog.MAI_MIN_EDGE and h >= catalog.MAI_MIN_EDGE, (
            f"{jeton}: MAI kenarı {catalog.MAI_MIN_EDGE} pikselin altına inemiyor")
        assert w * h <= catalog.MAI_PIXEL_CAP, (
            f"{jeton}: {w * h} piksel, MAI tavanı {catalog.MAI_PIXEL_CAP}")


def test_MAI_jetonlari_AZURE_nun_uc_oranini_KARSILIYOR():
    """`test_gemini_oranlari_…`ın ikizi ve aynı gerekçesi: model değiştirmek
    ORANI TAŞIMALI, sebepsiz bir "varsayılana düşüldü" uyarısı basmamalı."""
    azure = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    azure_oranlari = {catalog.geometry_of(s)[1] for s in azure.sizes}
    mai_oranlari = {catalog.geometry_of(s)[1] for s in catalog.MAI_SIZES}

    assert azure_oranlari <= mai_oranlari, (
        "Azure'dan MAI'ye geçişte karşılığı olmayan oran: "
        f"{sorted(azure_oranlari - mai_oranlari)}")


def test_MAI_girdileri_jetonlari_PAYLASIYOR():
    """Üç girdiye elle üç kez yazmak, birine jeton ekleyip ötekini unutmanın
    kapısı olurdu (`ASPECT_RATIOS`in paylaşılma gerekçesi)."""
    mai = [m for m in catalog.IMAGE_MODELS if m.provider == "azure-mai"]
    assert len(mai) == 3, "katalogda üç MAI girdisi olmalı"
    for m in mai:
        assert m.sizes is catalog.MAI_SIZES, (
            f"{m.id}: jetonları kopyalamış, MAI_SIZES'ı paylaşmıyor")
        assert m.credential == "azure_foundry", m.credential
        # Adet TEL ÜZERİNDE YOK: MAI'de `n` parametresi hiç mevcut değil,
        # yani adet başına AYRI istek atılıyor (bkz. karar 5).
        assert m.images_per_request == 1
        # Kalite ekseni YOK: tek sentetik jeton + gizli knob (karar 4).
        assert m.quality_hidden is True
        # Düzenleme TEK referans alıyor (multipart `image`, tekrar YOK).
        assert m.supports_edit is True and m.max_refs == 1
        assert m.note and "Önizleme" in i18n.t(m.note, "tr"), (
            f"{m.id}: MAI ailesinin üçü de önizleme; notta yazılı olmalı "
            "(bkz. Azure MAI blok yorumu: kalkacağı belli olan girdi silinir)")


# ── Azure AI Foundry · FLUX.2 (v0.15) ──────────────────────────────────


def test_FLUX_jetonlari_gpt_image_2_ile_AYNI():
    """Aynı jeton kümesi = model değiştirirken "varsayılana düşüldü" uyarısı
    YOK. Ayrışırsa kullanıcı sebepsiz bir düşme uyarısı görür."""
    azure = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    assert set(catalog.FLUX_SIZES) == set(azure.sizes)


def test_FLUX_girdileri_jetonlari_PAYLASIYOR():
    flux = [m for m in catalog.IMAGE_MODELS if m.provider == "azure-flux"]
    assert len(flux) == 1, "flex 2026-09-22'de silindi (1b-D); geriye pro kaldı"
    for m in flux:
        assert m.sizes is catalog.FLUX_SIZES, (
            f"{m.id}: jetonları kopyalamış, FLUX_SIZES'ı paylaşmıyor")
        assert m.credential == "azure_foundry", m.credential
        assert m.images_per_request == 1
        # `num_images` tavanı ÖLÇÜLMEDİ: eksik beyan yalnızca bir yeteneği
        # kullanmamak, fazla beyan seçilebilir bir hata.
        assert m.max_n == 1, f"{m.id}: num_images tavanı ölçülmedi (karar 5)"
        assert m.supports_edit is True and m.max_refs == 4


def test_the_deleted_flex_entry_left_nothing_behind_in_the_catalog_or_the_adapter():
    """1b-D: girdi silindi, ADAPTÖR de temizlendi — yarısı kalsa seçilebilir bir tuzak olurdu.

    `openai-dall-e-3`ün ölçülmüş dersi: katalogda kalan ölü bir girdi arayüzde
    seçilebilir bir 404 demek. Bunun simetriği de doğru — girdi gidip yolu
    kalsaydı ölü kod, yol gidip girdi kalsaydı 404. İkisi birlikte taranıyor.
    """
    assert catalog.image_model("azure-flux-2-flex") is None
    assert "azure-flux-2-flex" not in catalog.image_model_ids()
    assert "FLUX.2-flex" not in flux_client._MODEL_PATHS
    assert not hasattr(flux_client, "_FLEX_QUALITY")
    assert not hasattr(flux_client, "quality_axis")
    # Kalite JETONLARI tabloda KALIYOR ve bu bilinçli: eski `history.json` ve
    # `ResultParams.quality` kayıtları hâlâ "hizli"/"dengeli"/"detayli"
    # taşıyor. `etiket.quality_label` bilinmeyen jetonu ham basıyor (hata
    # değil), ama etiketi silmek geçmiş kayıtları OKUNAKSIZ yapardı —
    # "eski işlerin kredisi değişmez" kuralının görüntü tarafı.
    for jeton in ("hizli", "dengeli", "detayli"):
        assert jeton in catalog.QUALITY_LABELS
        assert jeton not in {q for m in catalog.IMAGE_MODELS for q in m.qualities}


def test_FLUX_pro_nun_kalite_ekseni_GIZLI():
    """pro'da `quality` parametresi YOK: tek sentetik jeton + gizli knob (karar 4).

    Karşı örnek olan flex silindi (1b-D) — eksen gerçekti ama FATURADA
    karşılığı yoktu: Azure adım sayısına değil megapiksele bakıyor, üç kademe
    de aynı parayı ödetiyordu.
    """
    pro = catalog.image_model("azure-flux-2-pro")
    assert pro is not None
    assert pro.quality_hidden is True and pro.qualities == ("standard",)
    assert pro.credits == 9, "kademeli MP fiyatı: 0,03 + 0,015 = 0,045 USD"


# ── `note` sözleşmesi ──────────────────────────────────────────────────


@pytest.mark.parametrize("m", catalog.IMAGE_MODELS, ids=lambda m: m.id)
@pytest.mark.parametrize("dil", i18n.LANGUAGES)
def test_her_gorsel_modelinin_notu_NE_ZAMAN_SECILIR_i_cevapliyor(m, dil):
    """`note` seçicide model adının ALTINA yazılıyor (static/core.js) ve tek
    işi şu soruyu cevaplamak: "ne zaman bunu seçerim?".

    Boş bir not o satırı adı tekrar eden bir başlığa indiriyor. Uzunluk üst
    sınırı da gerçek ve ÖLÇÜLMÜŞ, yazılı olduğu yer `static/core.js:843`:
    360px'de not 36px, yani iki satır tutuyor; aşanı kaydırma üretiyor ve
    komşu satırların hizasını bozuyor. 110 karakter o 36px'in satır başına
    ~55 karakterle çevrilmiş hâli — kesin bir font ölçümü DEĞİL. Bağlayıcı
    da değil: en uzun gerçek not 88 karakter, yani %20 boşluk var.

    v0.21'den beri `note` bir ÇEVİRİ ANAHTARI ve sözleşme HER DİLDE geçerli
    olmak zorunda: 36px'lik kutu çeviriyle büyümüyor. Test bu yüzden dil
    ekseninde de parametreli — İngilizce bir notun taşması Türkçe'sine
    bakarak görülemezdi.
    """
    assert m.note, f"{m.id}: not yok — seçicideki satır sebepsiz kalıyor"
    metin = i18n.t(m.note, dil)
    assert metin != m.note, f"{m.id}: {dil}.json'da not yok"
    assert 20 <= len(metin) <= 110, (
        f"{m.id} ({dil}): not {len(metin)} karakter (beklenen 20-110)")
    # Adı TEKRAR ETMİYOR: etiket zaten satırın kendisi. Karşılaştırma
    # `·`DEN SONRAKİ PARÇAYLA yapılıyor, tam etiketle DEĞİL: tam etiket
    # ("OpenAI · gpt-image-2") hiçbir notta harfi harfine geçmez, yani tam
    # etiketle kıyaslayan bir iddia hiç ateşlenemezdi. Ölçüldü — notu
    # "gpt-image-1 artık kalkıyor…" yapan mutasyon, yani bu iddianın
    # ENGELLEMEK İÇİN VAR OLDUĞU kusur, tam etiket kıyasını geçiyordu.
    #
    # `etiket.short_labels()` burada işe YARAMAZ: onun ölçülmüş çakışma
    # istisnası iki `gpt-image-2` girdisinde öneki BİLEREK koruyor (seçicide
    # doğru olan bu), ki o da tam da bu iki girdide iddiayı yeniden boşa
    # düşürürdü. Buradaki soru ayrıştırma değil, notun modelin KENDİ adıyla
    # başlayıp satırı tekrar etmesi.
    ad = m.label.rsplit("·", 1)[-1].strip().lower()
    assert ad not in metin.lower(), (
        f"{m.id} ({dil}): not model adını ({ad}) tekrar ediyor")


def test_her_ONIZLEME_modelinin_notu_bunu_SOYLUYOR():
    """MAI ailesinin üçü de önizleme: ad ya da sözleşme haber vermeden
    değişebilir. `openai-gpt-image-1`in duruşu benimseniyor — notta yazılı,
    kalkacağı belli olunca girdi silinir (o girdi 2026-09-21'de tam böyle
    silindi, Faz 4 / 1). Yazılmazsa kullanıcı kararlı bir model sanır.
    """
    # Uyarı HER DİLDE durmak zorunda: yalnız Türkçe'ye bakan bir iddia,
    # İngilizce notta "Preview" unutulduğunda sessizce yeşil kalırdı.
    for m in catalog.IMAGE_MODELS:
        if m.provider == "azure-mai":
            assert "Önizleme" in i18n.t(m.note, "tr"), f"{m.id}: önizleme uyarısı yok"
            assert "Preview" in i18n.t(m.note, "en"), f"{m.id}: preview warning missing"


def test_hicbir_not_uygulamanin_YAPMADIGI_bir_seyi_vaat_etmiyor():
    """FLUX 8/10 referans alabiliyor ama ilk tur `app.MAX_EDIT_IMAGES` (4)
    tavanında kalıyor ve `max_n=1`. Seçicide "8 referans" yazmak, uygulamanın
    yapmadığı bir şeyi vaat etmek olurdu — bu deponun yasakladığı sessiz
    sapmanın kendisi. Sayı bir gün yükselirse önce bu test kırmızıya döner.
    """
    # Tavan (`app.MAX_EDIT_IMAGES`) mesaja ELDEN yazılıyor: `app`i ithal etmek
    # bu yaprak test dosyasını 6. katmandaki 2100 satırlık modüle bağlardı ve
    # ilgisiz bir `app.py` kırılması burayı da kırmızıya çevirip suçu
    # bulandırırdı. Değer değişirse bu satır bayatlar — ama iddia zaten
    # jetonlara bakıyor, mesaja değil.
    for m in catalog.IMAGE_MODELS:
        for sayi in ("8 referans", "10 referans"):
            assert sayi not in m.note, (
                f"{m.id}: not {sayi} vaat ediyor, tavan "
                f"{min(m.max_refs, 4)}")


def test_wire_model_edit_defaults_to_empty_on_every_existing_entry():
    """Alan EKLENİYOR ama mevcut girdilerin hiçbirinin telini değiştirmiyor.

    Varsayılanın "" olması, "düzenleme ve üretim AYNI uca gidiyor" demek —
    Azure, OpenAI, Gemini, MAI, FLUX ve Veo'nun tamamı böyle. Bu test alanın
    varsayılanını mandallıyor: bir gün varsayılan değişirse on üç girdi
    sessizce başka bir uca gitmeye başlardı.

    GÖREV 7 İLE SÜZGEÇ EKLENDİ: fal, metin→video ve görsel→video için AYRI
    uçlar kullanan İLK sağlayıcı (`catalog.ImageModel.wire_model_edit`in
    yorumundaki "fal.ai'da ... AYRI uçlar" notu), yani üç fal girdisi bu
    alanı BİLEREK dolduruyor. Süzgeç onu dışarıda bırakıyor, geri kalan on üç
    girdi için iddia AYNEN duruyor.
    """
    for m in catalog.IMAGE_MODELS + catalog.VIDEO_MODELS:
        if m.provider == "fal":
            continue
        assert m.wire_model_edit == "", f"{m.id} beklenmedik ikinci tel yolu"


def test_the_field_default_itself_is_empty():
    """(a)'daki döngü ileride fal girdileri gelince SÜZGEÇ kazanacak; bu
    iddia süzgeçten etkilenmiyor ve asıl korunan şeyi ölçüyor: VARSAYILAN.
    Varsayılan bir gün "" olmaktan çıkarsa on üç girdi sessizce başka bir uca
    gitmeye başlardı."""
    assert catalog.ImageModel.__dataclass_fields__["wire_model_edit"].default == ""


def test_MALIYET_ustunlugu_iddia_eden_not_GERCEKTEN_en_ucuz():
    """Seçici bir KARŞILAŞTIRMA yüzeyi: not, kredi rakamının tam yanında
    çiziliyor (static/core.js). "en ucuz" yazan bir not, kendisinden ucuz bir
    satır bir alt sırada dururken kullanıcıya yanlış söylüyor.

    Ölçülmüş kusur, bu turun kendisinden: `gemini-nano-banana-2`nin notu "en
    ucuz" diyordu (6 kredi), oysa AYNI dalda eklenen MAI-Image 2.6 Flash 4
    kredi. İddiayı yazan görev ile onu yanlışlayan görev aynı daldaydı ve iki
    görev incelemesi de göremedi, çünkü not sözleşmesi uzunluğa, ada,
    önizlemeye ve referans vaadine bakıyordu — KARŞILAŞTIRMAYA bakmıyordu.

    Hız üstünlüğü burada sınanmıyor: katalogda gecikme verisi yok, yani
    ölçülemez. Maliyet ölçülebilir, o yüzden mandalı bu.
    """
    for m in catalog.IMAGE_MODELS:
        _maliyet_iddiasini_sina(m, catalog.IMAGE_MODELS, "görsel kataloğu")


def _taban(m: catalog.ImageModel) -> int:
    """Modelin EN UCUZ kademesi: `credits_by_quality` varsa en küçüğü, yoksa `credits`."""
    return min((k for _, k in m.credits_by_quality), default=m.credits)


def _tavan(m: catalog.ImageModel) -> int:
    return max((k for _, k in m.credits_by_quality), default=m.credits)


def _maliyet_iddiasini_sina(m: catalog.ImageModel, havuz, kapsam: str) -> None:
    """Bir notun "en ucuz"/"en pahalı" iddiasını `havuz` içinde KADEME düzeyinde sınar.

    TÜRKÇE METİN okunuyor, anahtar DEĞİL (2026-09-23 düzeltmesi): v0.21 `note`u
    çeviri anahtarına çevirdiğinde mandal `m.note.lower()` kalmıştı ve
    "model.x.note" hiç "en ucuz" içermediği için SESSİZCE BOŞ ateşliyordu.
    Metin Türkçe, çünkü iddia sözcükleri Türkçe; İngilizce çeviri aynı iddiayı
    taşır (i18n eşliği ayrı bekçi).

    KADEME düzeyi (#80 incelemesi): ilk sürüm yalnız VARSAYILAN krediyi
    karşılaştırıyordu ve iki yanlışı geçirdi — H3 "fal'ın en ucuz kademesi"
    derken (768P 12) Wan 480p 10 kredi/sn'ydi; schnell "En ucuz görsel: 1"
    derken gpt-image-2'nin `low` kademesi de 1'di. Kural: NİTELENMEMİŞ "en ucuz"
    hem varsayılanda hem taban kademede havuzun TEK en ucuzu olmalı — eşitlik
    de yanlış, kullanıcı "en ucuz" okuyup bir alt satırda aynı rakamı görür.
    "varsayılan" sözcüğüyle nitelenmiş iddia ("en ucuz varsayılan kademe")
    yalnız varsayılan kredileri karşılaştırır; eşitlik burada da yanlış değil
    ama beklenmiyor. "en pahalı" simetrik (tavan kademe).
    """
    assert m.note is not None, f"{m.id}: notu yok (not sözleşmesi ayrı bekçi)"
    notu = i18n.t(m.note, "tr").lower()
    digerleri = [d for d in havuz if d.id != m.id]
    if "en ucuz" in notu:
        en_az = min(d.credits for d in havuz)
        assert m.credits == en_az, (
            f"{m.id}: not 'en ucuz' diyor ama varsayılanı {m.credits} kredi "
            f"({kapsam} içinde en az {en_az})")
        if "varsayılan" not in notu:
            esit_veya_ucuz = [d.id for d in digerleri if _taban(d) <= _taban(m)]
            assert not esit_veya_ucuz, (
                f"{m.id}: not nitelenmemiş 'en ucuz' diyor (taban {_taban(m)}) ama "
                f"{kapsam} içinde {esit_veya_ucuz} tabanı bundan ucuz ya da eşit — "
                f"'en ucuz varsayılan kademe' yaz ya da iddiayı kaldır")
    if "en pahalı" in notu:
        en_cok = max(d.credits for d in havuz)
        assert m.credits == en_cok, (
            f"{m.id}: not 'en pahalı' diyor ama varsayılanı {m.credits} kredi "
            f"({kapsam} içinde en çok {en_cok})")
        if "varsayılan" not in notu:
            esit_veya_pahali = [d.id for d in digerleri if _tavan(d) >= _tavan(m)]
            assert not esit_veya_pahali, (
                f"{m.id}: not nitelenmemiş 'en pahalı' diyor (tavan {_tavan(m)}) ama "
                f"{kapsam} içinde {esit_veya_pahali} tavanı bundan pahalı ya da eşit")


# ── Sahibin sıralı listesi = katalog sırası (Faz 4 / 1b-D, 2026-09-23) ────
#
# Belge §1b iki liste veriyor (13 görsel, 10 video) ve "Sıra ARAYÜZ sırası"
# diyor. Liste burada ADIYLA yazılı — türetilemez, çünkü ölçüt kalite/
# popülerlik, kredi değil (Seedance 95 birinci, MiniMax 12 dokuzuncu ama Veo
# Lite 10 onuncu). Bir girdi eklenirken listeye yazılmazsa burası kırmızı
# olur: seçicideki sıra sessizce kaymaz.

SIRALI_GORSEL = (
    "azure-gpt-image-2",
    "openai-gpt-image-2-5-sunburst",
    "openai-gpt-image-2-5-flare",
    "gemini-nano-banana-pro",
    "openai-gpt-image-2",
    "gemini-nano-banana-2",
    "azure-mai-image-2-5-pro",
    "azure-flux-2-pro",
    "azure-mai-image-2-6",
    "fal-qwen-image",
    "fal-seedream-v4",
    "azure-mai-image-2-6-flash",
    "fal-flux-1-schnell",
)
SIRALI_VIDEO = (
    "fal-seedance-2-5",
    "gemini-veo-3-1",
    "fal-flux-3",
    "fal-kling-v3-turbo-pro",
    "fal-kling-v3-pro",
    "gemini-veo-3-1-fast",
    "fal-pixverse-c1",
    "fal-wan-3-0",
    "fal-minimax-h3",
    "gemini-veo-3-1-lite",
)


def test_the_image_catalog_follows_the_owners_RANKED_list():
    assert tuple(m.id for m in catalog.IMAGE_MODELS) == SIRALI_GORSEL


def test_the_video_catalog_follows_the_owners_RANKED_list():
    assert tuple(m.id for m in catalog.VIDEO_MODELS) == SIRALI_VIDEO


def test_the_defaults_are_CONSTANTS_not_index_zero():
    """Belge §1b "SIRA İLE VARSAYILAN KODDA AYRI, YORUMDA DEĞİL": `catalog.py`nin
    başlığı "ilk girdi varsayılan" diyordu ve bu yalnız o günkü yerleşimin
    tarifiydi. Liste sıralanınca video varsayılanı SONA düştü; görselinki
    tesadüfen başta kaldı. Bu test ayrımı mandallıyor: varsayılan id ile
    aranır, demetin bir ucuna oturmak zorunda değil — ve bir sonraki okuyan
    "varsayılan Seedance" sanmasın.
    """
    assert catalog.VIDEO_MODELS[-1].id == catalog.DEFAULT_VIDEO_MODEL
    assert catalog.VIDEO_MODELS[0].id != catalog.DEFAULT_VIDEO_MODEL
    assert catalog.video_model(catalog.DEFAULT_VIDEO_MODEL) is catalog.VIDEO_MODELS[-1]
    assert catalog.image_model(catalog.DEFAULT_IMAGE_MODEL) is catalog.IMAGE_MODELS[0]


def test_the_ranked_lists_carry_thirteen_images_and_ten_videos():
    """Belgenin sayısı (§1b "SAYININ HESABI": 8 + 5 = 13, 6 + 4 = 10)."""
    assert len(catalog.IMAGE_MODELS) == 13
    assert len(catalog.VIDEO_MODELS) == 10


# ── Plan basamağı VERİ oldu (Faz 4 / 1b-D) ──────────────────────────────
#
# B PR'ı (`Plan.rank`, `kapsiyor`) makineyi kurdu, her girdi `"free"` kaldı;
# D PR'ı beş girdiye basamak yazdı. Eşleme ÖNERİ (sahip onaylamadı — belge
# §1b "Yapıldığında (D)") ama bir öneri de veri ve verinin bekçisi test:
# sahip bir kademeyi değiştirdiği gün önce burası kırmızı olur, sonra doğru
# sayıyla yeşile döner — sessiz kayma yok.

PLAN_BASAMAGI = {
    "openai-gpt-image-2-5-sunburst": "temel",
    "openai-gpt-image-2-5-flare": "temel",
    "fal-seedance-2-5": "pro",
    "fal-flux-3": "pro",
    "fal-kling-v3-pro": "temel",
}


def test_the_plan_tiers_are_exactly_the_proposed_five_and_everything_else_is_free():
    for m in catalog.IMAGE_MODELS + catalog.VIDEO_MODELS:
        assert m.plan == PLAN_BASAMAGI.get(m.id, "free"), f"{m.id}: plan={m.plan}"


def test_gpt_image_2_5_is_a_COPY_of_gpt_image_2_as_a_lower_bound():
    """Sahibin talimatı ("jetonları gpt-image-2'den KOPYALA, alt sınır kalsın"):
    iki 2.5 girdisinin yetenek jetonları VE kredisi `openai-gpt-image-2` ile
    birebir. Ayrışırsa iki şeyden biri olmuş demek: ya sahip 2.5'i ölçtü (o
    zaman bu test bilinçli güncellenir ve `tarife_kontrol` notu düşer) ya da
    biri kopyayı sessizce "iyileştirdi" — ikincisi seçilebilir bir 400.
    """
    kaynak = catalog.image_model("openai-gpt-image-2")
    for kimlik, tel in (("openai-gpt-image-2-5-sunburst", "gpt-image-2.5-sunburst"),
                        ("openai-gpt-image-2-5-flare", "gpt-image-2.5-flare")):
        m = catalog.image_model(kimlik)
        assert m is not None and m.provider == "openai" and m.credential == "openai"
        assert m.wire_model == tel
        for alan in ("sizes", "qualities", "default_quality", "max_n", "images_per_request",
                     "supports_edit", "max_refs", "credits", "credits_by_quality"):
            assert getattr(m, alan) == getattr(kaynak, alan), f"{kimlik}.{alan} kopya değil"


def test_schnell_jetonlari_BIR_megapikselin_ALTINDA():
    """fal 1 MP'ye YUKARI yuvarlıyor: 1024×1024 (1,048 MP) İKİ MP sayılır ve
    ücretsiz planın 1 kredilik modeli 2 krediye çıkar (belge §1b "13. satır").
    Bu test bir kolaylık değil FİYAT KAPISI — `credits=1` yalnız küme 1 MP'nin
    altındayken doğru. 32'nin katı olma şartı FLUX'un adım kısıtı."""
    m = catalog.image_model("fal-flux-1-schnell")
    assert m is not None and m.sizes is catalog.SCHNELL_SIZES and m.credits == 1
    for jeton in m.sizes:
        w, h = (int(p) for p in jeton.split("x"))
        assert w * h < 1_000_000, f"{jeton}: {w * h} piksel — fal iki MP sayar, kredi 2 olur"
        assert w % 32 == 0 and h % 32 == 0, f"{jeton}: 32'nin katı değil"
    assert "1024x1024" not in m.sizes
    assert not m.supports_edit, "schnell'in düzenleme ucu yok (redux ayrı model)"


def test_qwen_jetonlari_IKI_megapikseli_ASMIYOR():
    """`credits=8` = 0,02 USD/MP × 2 MP: kümeden biri 2 MP'yi aşarsa üç MP
    sayılır ve kredi 12 olur — etiket yalan söyler."""
    m = catalog.image_model("fal-qwen-image")
    assert m is not None and m.sizes is catalog.QWEN_SIZES and m.credits == 8
    for jeton in m.sizes:
        w, h = (int(p) for p in jeton.split("x"))
        assert 1_000_000 < w * h <= 2_000_000, f"{jeton}: {w * h} piksel, 1–2 MP bandı dışında"
    assert m.max_refs == 1, "qwen-image-edit tek `image_url` alıyor"


def test_seedream_jetonlari_semanin_kenar_araliginda():
    """Seedream V4 şeması kenar başına 1024–4096 istiyor; gpt-image-2'nin üçlüsü
    bu aralıkta ve sabit fiyat (6) boyuttan bağımsız."""
    m = catalog.image_model("fal-seedream-v4")
    assert m is not None and m.credits == 6 and m.credits_by_quality == ()
    for jeton in m.sizes:
        w, h = (int(p) for p in jeton.split("x"))
        assert 1024 <= w <= 4096 and 1024 <= h <= 4096, jeton
    assert set(m.sizes) == set(catalog.image_model("openai-gpt-image-2").sizes)
    assert m.max_refs == 4


def test_every_fal_IMAGE_model_declares_what_the_queue_needs():
    """Video ikizinin (`test_every_video_model_declares_what_the_pipeline_needs`)
    görsel yarısı: fal görsel de KUYRUKLU — `poll_timeout` yoksa `total_budget`
    görselin 180 sn formülüne düşer (bugün aynı sayı, ama tesadüfen); adet
    döngüsü adet başına ayrı istek (`images_per_request=1`, `num_images=1`);
    adaptörü `_ADAPTERS`ta olmalı."""
    import providers
    fal = [m for m in catalog.IMAGE_MODELS if m.provider == "fal"]
    assert [m.id for m in fal] == ["fal-qwen-image", "fal-seedream-v4", "fal-flux-1-schnell"]
    assert "fal" in providers.adapter_ids()
    for m in fal:
        assert m.poll_timeout, f"{m.id}: poll_timeout yok"
        assert m.images_per_request == 1 and m.quality_hidden and m.qualities == ("standard",)
        assert m.credential == "fal"
        if m.supports_edit:
            assert m.wire_model_edit and m.wire_model_edit != m.wire_model, m.id
        else:
            assert m.wire_model_edit == "", m.id


def test_no_entry_carries_a_retirement_date_today():
    """`emeklilik` alanı D'de açıldı, hiçbir girdi doldurmuyor; doldurulan gün
    `tools/tarife_kontrol.py` satır basar (bekçisi tests/test_araclar.py)."""
    assert all(m.emeklilik is None for m in catalog.IMAGE_MODELS + catalog.VIDEO_MODELS)


# ── fal.ai video modelleri (Görev 7 + Faz 4 / 1b-D) ────────────────────

FAL_IDLER = ("fal-wan-3-0", "fal-pixverse-c1", "fal-kling-v3-turbo-pro",
             "fal-seedance-2-5", "fal-flux-3", "fal-kling-v3-pro", "fal-minimax-h3")


@pytest.mark.parametrize("model_id", FAL_IDLER)
def test_every_fal_video_model_declares_BOTH_wire_endpoints(model_id):
    """Boş `wire_model_edit`, düzenleme isteğini METİN ucuna göndermek —
    yani telde 422 — demek olurdu."""
    m = catalog.video_model(model_id)
    assert m is not None, f"{model_id} katalogda yok"
    assert m.supports_edit
    assert m.wire_model_edit, f"{model_id} ikinci tel yolunu beyan etmiyor"
    assert m.wire_model != m.wire_model_edit


def test_the_default_video_model_is_UNCHANGED():
    """Varsayılanı kaydırmak her kullanıcının bir sonraki tıkına dokunurdu."""
    assert catalog.DEFAULT_VIDEO_MODEL == "gemini-veo-3-1-lite"


# `test_fal_video_models_are_ordered_by_ASCENDING_cost` ve
# `..._PIXVERSE_WAN_KLING` 2026-09-23'te DÜŞTÜ: fal'ın kendi içindeki artan
# maliyet sırası (Görev 7'nin ölçümü, PixVerse < Wan < Kling) sahibin sıralı
# listesiyle yer değiştirdi — yeni mandal `test_the_video_catalog_follows_the_
# owners_RANKED_list` (yukarıda). Ölçümün kendisi hâlâ doğru ve kredilerde
# yaşıyor (`test_fal_credits_are_derived_from_MEASURED_usd_per_second`).


@pytest.mark.parametrize("model_id", FAL_IDLER)
def test_fal_video_models_declare_no_last_frame(model_id):
    """Üçü de `supports_last_frame=False`.

    DÜZELTME (Görev 9, 2026-09-15): bu gerekçe önceden "üç modelin hiçbirinin
    i2v şemasında `tail_image_url` yok" diyordu — doğru ama BOŞ: o ad fal'da
    hiç kullanılmayan bir isim. Görev 8'in tam OpenAPI şema ölçümü
    (`olcum-uc-semalari.md`) Wan'ın i2v ucunda GERÇEK bir son-kare alanı
    (`end_image_url`) olduğunu gösterdi — `fal_client.ALANLAR` onu bu turda
    BİLİNÇLİ OLARAK göndermiyor, bayrak o yüzden dürüstçe `False`. PixVerse
    ve Kling'in şemalarında ise gerçekten hiçbir son-kare alanı yok. Karar
    (üçü de `False`) değişmedi, yalnız gerekçe düzeldi.
    """
    assert catalog.video_model(model_id).supports_last_frame is False


def test_fal_credits_are_derived_from_MEASURED_usd_per_second():
    """Kredi ÇAPASI Veo'yla AYNI: Azure `medium` = 8 kredi ≈ 0,04 USD, yani
    1 kredi ≈ 0,005 USD. Rakamlar brief'in tahmini DEĞİL,
    docs/superpowers/specs/2026-09-14-fal-video-saglayicisi-design.md'nin
    'Ölçüm sonuçları (2026-09-14, canlı uçtan)' tablosundaki USD/sn
    değerlerinden (fal.ai model sayfaları) türetildi:

        Wan     480p $0,05/sn·720p $0,10/sn·1080p $0,20/sn  → 10·20·40
        PixVerse 720p $0,065/sn (sesli) ·1080p $0,120/sn (sesli) → 13·24
        Kling   düz $0,14/sn (çözünürlükten bağımsız)        → 28

    PixVerse'in sesli/sessiz ayrımı `fal_client.ALANLAR`da YOK (adaptör ses
    alanı hiç göndermiyor) — hangisinin telde geçerli olduğu ölçülemedi, o
    yüzden YUKARI yuvarlamak için daha pahalı (sesli) rakam alındı: krediyi
    düşük göstermek kullanıcıyı ucuz sanıp tıklamaya davet ederdi.
    """
    wan = catalog.video_model("fal-wan-3-0")
    pixverse = catalog.video_model("fal-pixverse-c1")
    kling = catalog.video_model("fal-kling-v3-turbo-pro")

    assert dict(wan.credits_by_quality) == {"480p": 10, "720p": 20, "1080p": 40}
    assert wan.credits == 20
    assert dict(pixverse.credits_by_quality) == {"720p": 13, "1080p": 24}
    assert pixverse.credits == 13
    assert kling.credits == 28
    assert kling.credits_by_quality == ()

    # Faz 4 / 1b-D (2026-09-23) — fal.ai model sayfalarının saniye fiyatı
    # (erişim 2026-09-22, belge §1b tablosu), aynı çapa, en yakına yuvarlama:
    #
    #     Seedance 2.5  720p sesli $0,473 · 480p sesli $0,2205 → 95 · 44
    #     FLUX 3        720p $0,17 · 1080p $0,29               → 34 · 58
    #     Kling V3 Pro  sessiz $0,112 · sesli $0,168           → 22 · 34
    #     MiniMax H3    768P $0,06 · 2K $0,13                  → 12 · 26
    #
    # Belge H3 için 480p (10) ve 4K (32) de yazıyor; şemada üç kaynakla
    # görülmedi, beyan edilmedi (catalog.py blok yorumu) — kademe eklenirse
    # bu satır bilinçli güncellenir.
    seedance = catalog.video_model("fal-seedance-2-5")
    flux3 = catalog.video_model("fal-flux-3")
    kling_pro = catalog.video_model("fal-kling-v3-pro")
    h3 = catalog.video_model("fal-minimax-h3")
    assert dict(seedance.credits_by_quality) == {"480p": 44, "720p": 95} and seedance.credits == 95
    assert dict(flux3.credits_by_quality) == {"720p": 34, "1080p": 58} and flux3.credits == 34
    assert dict(kling_pro.credits_by_quality) == {"sessiz": 22, "sesli": 34} and kling_pro.credits == 22
    assert dict(h3.credits_by_quality) == {"768P": 12, "2K": 26} and h3.credits == 12
    # Çapa gerçekten bölüyor: 0,473 / 0,005 = 94,6 → 95; 0,112 / 0,005 = 22,4 → 22.
    assert round(0.473 / float(catalog.KREDI_USD_CAPASI)) == 95
    assert round(0.112 / float(catalog.KREDI_USD_CAPASI)) == 22


# ── Görev 9 — video notları için mandal ─────────────────────────────────
#
# `test_MALIYET_ustunlugu_iddia_eden_not_GERCEKTEN_en_ucuz`in docstring'i
# kendi ölçülmüş kusurunu kaydediyor: "iddiayı yazan görev ile onu
# yanlışlayan görev aynı daldaydı ve iki görev incelemesi de göremedi, çünkü
# not sözleşmesi ... KARŞILAŞTIRMAYA bakmıyordu." O mandal YALNIZ
# `IMAGE_MODELS` üzerinde dönüyordu — Görev 7/8'in eklediği üç video notu
# hiçbir kapının arkasında değildi. Görev 9'un kendi kusuru (Kling'in notunun
# ölçülmemiş "1080p ve lipsync" iddiası) TAM OLARAK bu boşluğa düştü ve NİHAİ
# İNCELEME de bunu ancak elle yakaladı. Aşağıdaki iki test o boşluğu kapatıyor.


def test_MALIYET_ustunlugu_iddia_eden_VIDEO_notu_SAGLAYICI_ICINDE_dogru():
    """Video notları BİLİNÇLİ OLARAK küresel değil AİLEYE göre konuşuyor:
    `gemini-veo-3-1-lite` "En ucuz Veo" diyor, `fal-pixverse-c1` "En ucuz fal
    kademesi" diyor. Küresel bir karşılaştırma YANLIŞ olurdu: Veo Lite 16
    kredi ama katalogdaki mutlak en ucuz PixVerse'in 13'ü (`VIDEO_MODELS`
    başlığındaki "BU İDDİA ARTIK KATALOG GENELİNDE DEĞİL" notu). Bu yüzden
    görsel tarafının mandalından (yukarıda, TÜM `IMAGE_MODELS`i tek havuzda
    karşılaştırır) FARKLI bir kapsam gerekiyor: burada karşılaştırma
    `provider` (gemini/fal) İÇİNDE — notun kendisinin konuştuğu aile de bu.

    Bu mandal video tarafında EKSİKTİ (I-2'nin yapısal yarısı, Görev 9): üç
    video notu hiçbir kapının arkasında değildi, tam da yukarıdaki
    docstring'in "iki görev incelemesi de göremedi" dediği desenin bu turda
    BİREBİR tekrarı — bu kez Kling'in notunda.
    """
    for provider in {m.provider for m in catalog.VIDEO_MODELS}:
        grup = [m for m in catalog.VIDEO_MODELS if m.provider == provider]
        for m in grup:
            # Metin, anahtar değil; kademe düzeyi (görsel ikizinin yardımcısı ve
            # gerekçesi). İlk gerçek sınavlar D'nin kendisi: PixVerse'in "En ucuz
            # fal kademesi" notu MiniMax H3 (12) gelince, Kling Turbo'nun "En
            # pahalı"sı Seedance (95) gelince YANLIŞLANDI; sonra H3'ün kendi "en
            # ucuz"u Wan 480p (10) karşısında kademe düzeyinde yanlış çıktı.
            _maliyet_iddiasini_sina(m, grup, provider)


_COZUNURLUK_JETONLARI = ("480p", "720p", "1080p")


def test_COZUNURLUK_iddia_eden_VIDEO_notu_GORUNUR_bir_jetona_dayanir():
    """Bir not bir çözünürlük jetonundan (480p/720p/1080p) söz ediyorsa, o
    jeton modelin `qualities`inde OLMALI VE `quality_hidden` `False` OLMALI.

    Gizli jeton (`quality_hidden=True`) arayüzün hiç göstermediği ve telin
    hiç taşımadığı SENTETİK bir değer (bkz. `ImageModel.qualities`in
    docstring'i) — onu notta vaat etmek I-2'nin ÖLÇÜLMÜŞ kusurunun ta
    kendisiydi: Kling'in eski notu "1080p" diyordu, ama Kling'in
    `qualities=("1080p",)` yalnız `quality_hidden=True` ile var olabiliyor
    çünkü iki ucun da şemasında `resolution` alanı HİÇ yok — jeton telde hiç
    gitmiyor, çıktının gerçek çözünürlüğü de ölçülmedi.

    KANIT (Görev 9'un sağlama turu, task-9-report.md'de tam çıktısı var): bu
    mandal yazılmadan ÖNCE mevcut altı video notu ondan geçirildi.
    `gemini-veo-3-1`in notu "1080p açık" diyor ve `qualities=('720p',
    '1080p')`, `quality_hidden=False` — GEÇTİ. Kling'in notu eski hâline
    ("...1080p ve lipsync...") döndürülünce bu test KIRILDI — yani mandal
    gerçekten mandal.
    """
    for m in catalog.VIDEO_MODELS:
        notu = i18n.t(m.note, "tr").lower()
        for jeton in _COZUNURLUK_JETONLARI:
            if jeton not in notu:
                continue
            assert jeton in m.qualities, (
                f"{m.id}: not {jeton!r} diyor ama qualities'te yok "
                f"({m.qualities})")
            assert m.quality_hidden is False, (
                f"{m.id}: not {jeton!r} diyor ama quality_hidden=True — "
                "telde hiç gitmeyen sentetik bir jetonu vaat ediyor")
