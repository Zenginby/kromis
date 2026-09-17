"""credstore: sağlayıcı başına kimlik çözümü ve "kullanılabilir mi" kapısı.

Bu dosyanın ölçtüğü asıl şey tek bir cümle: arayüzün açtığı kapı ile isteğin
gerçekten kullandığı değerler AYRIŞMAMALI. Ayrışırlarsa arayüz modeli
seçilebilir gösterir, ilk üretim 502 döner ve kullanıcı sebebi görmez —
`azure_client.chat_credentials_of`un docstring'inde sohbet için yazılı olan
tuzağın N sağlayıcıya genellenmiş hâli.

KAYNAK BİR SÖZLÜK (Faz 1 / 7): `credentials.env` yok, her işlev `kimlikler`
alıyor — kullanıcının `saglayici_kimlikleri` satırlarından çözülen düz
`{env adı: değer}`. `None` isteğin bağlamı (`kimlik_baglami`), o da yoksa boş.
"""
import pytest

import azure_client as ac
import catalog
import credstore
import kimlik_baglami

AZURE = {"AZURE_IMAGE_API_KEY": "AZUREKEY", "AZURE_IMAGE_BASE_URL": "https://ep/openai/v1/"}


def test_bos_kurulumda_hicbir_saglayici_yapilandirilmis_degil():
    assert credstore.configured_map({}) == {c.id: False for c in catalog.CREDENTIALS}


def test_anahtar_yazilinca_yalnizca_o_saglayici_aciliyor():
    harita = credstore.configured_map({"GEMINI_API_KEY": "AIzaSyDUMMY1234567890abcdefghij"})
    assert harita["gemini"] is True
    assert harita["openai"] is False
    assert harita["azure_image"] is False


def test_varsayilan_adres_kullaniliyor_kullanici_girmese_de():
    """OpenAI/Gemini'de her kullanıcının kendi endpoint'i yok.

    Azure'ın aksine adres FORMDA sorulmuyor; katalogdaki varsayılan yeterli
    olmak zorunda, yoksa anahtarı kaydeden kullanıcı "adres yok" hatası alır.
    """
    key, url = credstore.resolve("openai", {"OPENAI_API_KEY": "sk-proj-DUMMY1234567890"})
    assert key == "sk-proj-DUMMY1234567890"
    assert url == catalog.credential("openai").default_base_url


def test_elle_yazilan_adres_varsayilani_eziyor():
    """Uyumlu bir vekil arkasına almak forma alan eklemeden mümkün olmalı."""
    kimlik = {"OPENAI_API_KEY": "sk-proj-DUMMY1234567890",
              "OPENAI_BASE_URL": "https://vekil.ornek/v1"}
    assert credstore.resolve("openai", kimlik)[1] == "https://vekil.ornek/v1"


def test_eksik_anahtar_hatasi_ORTAM_DEGISKENININ_adini_soyluyor():
    """"Kimlik eksik" demek, dört sağlayıcı varken hangisini kurcalayacağını
    söylemiyor. Mesaj sağlayıcı adını VE env adını birden taşımalı."""
    with pytest.raises(ac.ImageError) as exc:
        credstore.resolve("gemini", {})

    mesaj = str(exc.value)
    assert "GEMINI_API_KEY" in mesaj
    assert catalog.credential("gemini").label in mesaj


def test_azure_gorsel_yolu_credentials_of_a_devrediliyor():
    """Azure görselinin iki adı ve hata cümlesi `azure_client`ta, burada yeniden yazılmıyor.

    Faz 1 / 7'ye kadar `load_credentials` (iki dosyalı düşme) idi; sözlükte
    kullanıcı başına TEK kaynak var, ama cümle ve iki ad AYNI yerden geliyor —
    ikinci bir "eksik mi" mantığı iki yolu sessizce ayrıştırırdı.
    """
    assert credstore.resolve("azure_image", AZURE) == ac.credentials_of(AZURE)
    assert credstore.is_configured("azure_image", AZURE) is True
    with pytest.raises(ac.ImageError) as eksik:
        credstore.resolve("azure_image", {"AZURE_IMAGE_API_KEY": "yalniz-anahtar"})
    with pytest.raises(ac.ImageError) as dosya:
        ac.load_credentials("/yok/boyle/dosya.env")
    assert str(eksik.value) == str(dosya.value), "dosya yolu ile sözlük yolu aynı cümleyi kurmalı"


def test_azure_sohbeti_kendi_anahtari_yoksa_GORSELIN_kimligine_dusuyor():
    """Canlı doğrulanmış davranış: iki dağıtım aynı kaynakta, aynı anahtarla.

    `chat_credentials_of`a devrediliyor — ikinci bir düşme mantığı yazmak,
    tam olarak bu modülün önlemek için var olduğu ayrışma olurdu.
    """
    assert credstore.is_configured("azure_chat", AZURE) is True
    assert credstore.resolve("azure_chat", AZURE) == ("AZUREKEY", "https://ep/openai/v1/")


def test_azure_sohbetinin_kendi_anahtari_gorseli_eziyor():
    kimlik = {**AZURE, "AZURE_CHAT_API_KEY": "SOHBET",
              "AZURE_CHAT_BASE_URL": "https://sohbet/openai/v1/"}
    assert credstore.resolve("azure_chat", kimlik) == ("SOHBET", "https://sohbet/openai/v1/")


def test_tanimsiz_kimlik_ham_500_DEGIL_Turkce_hata():
    """Katalog ile kod ayrışması programlama hatası, ama yine de 502'ye
    çevrilebilir bir tür olmalı: ham 500'de arayüz gövdeyi ayrıştıramıyor."""
    with pytest.raises(ac.ImageError):
        credstore.resolve("boyle-bir-saglayici-yok", {})

    assert credstore.is_configured("boyle-bir-saglayici-yok", {}) is False


def test_is_configured_resolve_ile_AYNI_karari_veriyor():
    """İki ayrı "eksik mi?" mantığı olmamalı — biri diğerinden sapabilir.

    `is_configured` bilerek `resolve`'u çağırıp istisnayı yutuyor; bu test o
    bağın gerçekten kurulu olduğunu ölçüyor.
    """
    kimlik = {"GEMINI_API_KEY": "AIzaSyDUMMY1234567890abcdefghij"}
    for cred in catalog.CREDENTIALS:
        try:
            credstore.resolve(cred.id, kimlik)
        except ac.ImageError:
            beklenen = False
        else:
            beklenen = True
        assert credstore.is_configured(cred.id, kimlik) is beklenen, cred.id


# ── Kaynak: açık sözlük → istek bağlamı → boş ──────────────────────────


def test_baglam_yokken_hicbir_sey_yapilandirilmis_degil_ve_dosya_okunmaz(monkeypatch):
    """`kimlikler=None` ve istek bağlamı yok: boş sözlük — `credentials.env`e DÜŞÜLMEZ.

    Faz 1 / 7 çıkış ölçütü: web yolunda dosya hiç açılmıyor. Dosya okuyucu
    patlatılıyor; `credstore` onu çağırsa bu test kırmızı olur.
    """
    def _patlat(*a, **k):
        raise AssertionError("credstore dosya okudu")
    monkeypatch.setattr(ac, "_parse_env_all", _patlat)
    monkeypatch.setattr(ac, "read_env_values", _patlat)
    monkeypatch.setattr(ac, "load_credentials", _patlat)

    assert kimlik_baglami.aktif() is None
    assert credstore.degerler() == {}
    assert credstore.configured_map() == {c.id: False for c in catalog.CREDENTIALS}
    assert not any(credstore.chat_configured_map().values())
    with pytest.raises(ac.ImageError):
        credstore.resolve("azure_image")


def test_istek_baglami_bagliyken_acik_sozluk_verilmezse_o_okunur():
    """Adaptörlerin `credstore.resolve(m.credential)` çağrısı (sözlüksüz) isteğin kimliğini görür."""
    jeton = kimlik_baglami.bagla(AZURE)
    try:
        assert credstore.degerler() is AZURE
        assert credstore.resolve("azure_image") == ("AZUREKEY", "https://ep/openai/v1/")
        assert credstore.configured_map()["azure_image"] is True
    finally:
        kimlik_baglami.coz(jeton)
    assert kimlik_baglami.aktif() is None
    assert credstore.configured_map()["azure_image"] is False


def test_acik_sozluk_istek_baglamini_eziyor():
    """Rota `settings_payload(kimlikler)` ile açık veriyor; bağlamda başka bir şey olsa da açık olan kazanır."""
    jeton = kimlik_baglami.bagla({"GEMINI_API_KEY": "AIza"})
    try:
        assert credstore.configured_map(AZURE) == {
            **{c.id: False for c in catalog.CREDENTIALS},
            "azure_image": True, "azure_chat": True, "azure_foundry": False}
        assert credstore.configured_map({})["gemini"] is False
    finally:
        kimlik_baglami.coz(jeton)


def test_settings_status_sozlukten_dosya_yolunun_dokuz_alanini_kurar():
    """`ac.get_settings_status`un gövdesi `settings_status_of`ta saf; web yolu onu sözlükle çağırır."""
    kimlik = {**AZURE, "AZURE_CHAT_DEPLOYMENT": "d", "OPENAI_API_KEY": "sk-x",
              "COMFYUI_URL": "http://127.0.0.1:8188"}
    durum = credstore.settings_status(kimlik)
    assert durum == {
        "configured": True, "endpoint": "https://ep/openai/v1/", "chat_deployment": "d",
        "chat_configured": True, "has_openai_key": True, "has_fal_key": False,
        "has_replicate_token": False, "comfyui_url": "http://127.0.0.1:8188", "ollama_url": ""}
    assert "AZUREKEY" not in str(durum) and "sk-x" not in str(durum)
    assert credstore.settings_status({}) == {
        "configured": False, "endpoint": None, "chat_deployment": "",
        "chat_configured": False, "has_openai_key": False, "has_fal_key": False,
        "has_replicate_token": False, "comfyui_url": "", "ollama_url": ""}


# ── Azure AI Foundry (MAI + FLUX) ──────────────────────────────────────
#
# Bu bloğun ölçtüğü şey tek cümle: kullanıcıdan İKİNCİ bir anahtar ve İKİNCİ
# bir adres istemeden MAI/FLUX'a ulaşılabilmeli — ama tanınmayan bir hostta
# SESSİZCE yanlış bir adrese düşülmemeli.

FOUNDRY_AZURE = {"AZURE_IMAGE_API_KEY": "PAYLASILAN",
                 "AZURE_IMAGE_BASE_URL": "https://ai-ornek.openai.azure.com/openai/v1/"}


@pytest.mark.parametrize("gorsel_adresi, beklenen", [
    ("https://ai-ornek-swedencentral.openai.azure.com/openai/v1/",
     "https://ai-ornek-swedencentral.services.ai.azure.com"),
    ("https://ai-ornek-swedencentral.cognitiveservices.azure.com/",
     "https://ai-ornek-swedencentral.services.ai.azure.com"),
    ("https://ai-ornek-swedencentral.services.ai.azure.com",
     "https://ai-ornek-swedencentral.services.ai.azure.com"),
])
def test_foundry_adresi_TANINAN_hostlardan_turetiliyor(gorsel_adresi, beklenen):
    """Türetme bir TABLO, dize ameliyatı DEĞİL.

    `replace("openai", "services.ai")` gibi bir dokunuş kaynak adında "openai"
    geçen her kurulumu bozardı (`my-openai-lab.openai.azure.com`). Tablo yalnız
    tanınan SON EKİ çeviriyor ve kaynak adına hiç dokunmuyor.
    """
    assert credstore.derive_foundry_base_url(gorsel_adresi) == beklenen


@pytest.mark.parametrize("gorsel_adresi", [
    "https://vekil.sirket.local/azure/openai/v1/",
    "https://openai.azure.com/openai/v1/",     # alt alan adı YOK
    "ai-ornek.openai.azure.com/openai/v1/",      # şema YOK
    "",
])
def test_TANINMAYAN_host_HIC_turetmiyor(gorsel_adresi):
    """Sessiz düşme YOK: yanlış hosta atılan istek 404 döner ve sebebi
    kullanıcının hiçbir yerde okumadığı bir şey olur."""
    assert credstore.derive_foundry_base_url(gorsel_adresi) == ""


def test_foundry_anahtari_GORSELIN_anahtarina_dusuyor():
    """Sonda tek anahtarın üç yüzeyde de geçtiğini ölçtü (`azure_chat`in
    ikizi). İkinci bir anahtar istemek, aynı değeri iki kez yazdırmak olurdu."""
    key, url = credstore.resolve("azure_foundry", FOUNDRY_AZURE)
    assert key == "PAYLASILAN"
    assert url == "https://ai-ornek.services.ai.azure.com"
    assert credstore.is_configured("azure_foundry", FOUNDRY_AZURE) is True


def test_foundry_nun_KENDI_anahtari_gorseli_eziyor():
    """Ayrı bir kaynak/anahtar kullanan kurulum forma alan eklemeden mümkün
    olmalı (`azure_chat`in aynı davranışı)."""
    kimlik = {**FOUNDRY_AZURE, "AZURE_FOUNDRY_API_KEY": "FOUNDRY"}
    assert credstore.resolve("azure_foundry", kimlik)[0] == "FOUNDRY"


def test_ELLE_yazilan_foundry_adresi_turetmeyi_eziyor():
    kimlik = {**FOUNDRY_AZURE, "AZURE_FOUNDRY_BASE_URL": "https://ozel.ornek/foundry"}
    assert credstore.resolve("azure_foundry", kimlik)[1] == "https://ozel.ornek/foundry"


def test_TANINMAYAN_hostta_hata_ALAN_ADINI_soyluyor():
    """Çıkışı olmayan bir hata olmamalı: mesaj hangi env değişkenini
    doldurmak gerektiğini ADIYLA söylemeli."""
    kimlik = {"AZURE_IMAGE_API_KEY": "K",
              "AZURE_IMAGE_BASE_URL": "https://vekil.sirket.local/azure/openai/v1/"}
    with pytest.raises(ac.ImageError) as exc:
        credstore.resolve("azure_foundry", kimlik)

    mesaj = str(exc.value)
    assert "AZURE_FOUNDRY_BASE_URL" in mesaj
    assert credstore.is_configured("azure_foundry", kimlik) is False


def test_anahtarsiz_kurulumda_foundry_KAPALI():
    """Adres türetilse bile anahtar yoksa model seçilebilir olmamalı."""
    kimlik = {"AZURE_IMAGE_BASE_URL": "https://ai-ornek.openai.azure.com/openai/v1/"}
    assert credstore.is_configured("azure_foundry", kimlik) is False
