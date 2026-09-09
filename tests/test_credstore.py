"""credstore: sağlayıcı başına kimlik çözümü ve "kullanılabilir mi" kapısı.

Bu dosyanın ölçtüğü asıl şey tek bir cümle: arayüzün açtığı kapı ile isteğin
gerçekten kullandığı değerler AYRIŞMAMALI. Ayrışırlarsa arayüz modeli
seçilebilir gösterir, ilk üretim 502 döner ve kullanıcı sebebi görmez —
`azure_client.resolve_chat_credentials`'ın docstring'inde sohbet için yazılı
olan tuzağın N sağlayıcıya genellenmiş hâli.
"""
import pytest

import azure_client as ac
import catalog
import credstore


@pytest.fixture
def env(tmp_path, monkeypatch):
    """İzole bir `credentials.env`. Paylaşılan legacy dosya da kapatılıyor.

    `DEFAULT_ENV_PATH` boş bir yola çekiliyor: geliştiricinin GERÇEK
    `~/.config/claude-tools/…` dosyası varsa Azure testleri sessizce onun
    üzerinden geçer ve "yapılandırılmamış" senaryosu hiç ölçülmezdi.
    """
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(tmp_path / "app" / "credentials.env"))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "yok.env"))
    return tmp_path


def test_bos_kurulumda_hicbir_saglayici_yapilandirilmis_degil(env):
    assert credstore.configured_map() == {c.id: False for c in catalog.CREDENTIALS}


def test_anahtar_yazilinca_yalnizca_o_saglayici_aciliyor(env):
    ac.save_env({"GEMINI_API_KEY": "AIzaSyDUMMY1234567890abcdefghij"})

    harita = credstore.configured_map()
    assert harita["gemini"] is True
    assert harita["openai"] is False
    assert harita["azure_image"] is False


def test_varsayilan_adres_kullaniliyor_kullanici_girmese_de(env):
    """OpenAI/Gemini'de her kullanıcının kendi endpoint'i yok.

    Azure'ın aksine adres FORMDA sorulmuyor; katalogdaki varsayılan yeterli
    olmak zorunda, yoksa anahtarı kaydeden kullanıcı "adres yok" hatası alır.
    """
    ac.save_env({"OPENAI_API_KEY": "sk-proj-DUMMY1234567890"})

    key, url = credstore.resolve("openai")
    assert key == "sk-proj-DUMMY1234567890"
    assert url == catalog.credential("openai").default_base_url


def test_elle_yazilan_adres_varsayilani_eziyor(env):
    """Uyumlu bir vekil arkasına almak forma alan eklemeden mümkün olmalı."""
    ac.save_env({"OPENAI_API_KEY": "sk-proj-DUMMY1234567890",
                 "OPENAI_BASE_URL": "https://vekil.ornek/v1"})

    assert credstore.resolve("openai")[1] == "https://vekil.ornek/v1"


def test_eksik_anahtar_hatasi_ORTAM_DEGISKENININ_adini_soyluyor(env):
    """"Kimlik eksik" demek, dört sağlayıcı varken hangisini kurcalayacağını
    söylemiyor. Mesaj sağlayıcı adını VE env adını birden taşımalı."""
    with pytest.raises(ac.ImageError) as exc:
        credstore.resolve("gemini")

    mesaj = str(exc.value)
    assert "GEMINI_API_KEY" in mesaj
    assert catalog.credential("gemini").label in mesaj


def test_azure_gorsel_yolu_load_credentials_a_devrediliyor(env):
    """Azure'ın İKİ DOSYALI düşmesi ve legacy paylaşılan dosyası korunmalı.

    Burada yeniden yazılsa o düşme sırası ikinci bir yerde yaşardı ve biri
    değişince diğeri sessizce ayrışırdı.
    """
    ac.save_credentials("AZUREKEY", "https://ep/openai/v1/")

    assert credstore.resolve("azure_image") == ac.load_credentials()
    assert credstore.is_configured("azure_image") is True


def test_azure_sohbeti_kendi_anahtari_yoksa_GORSELIN_kimligine_dusuyor(env):
    """Canlı doğrulanmış davranış: iki dağıtım aynı kaynakta, aynı anahtarla.

    `resolve_chat_credentials`'a devrediliyor — ikinci bir düşme mantığı
    yazmak, tam olarak bu modülün önlemek için var olduğu ayrışma olurdu.
    """
    ac.save_credentials("PAYLASILAN", "https://ep/openai/v1/")

    assert credstore.is_configured("azure_chat") is True
    assert credstore.resolve("azure_chat") == ("PAYLASILAN", "https://ep/openai/v1/")


def test_azure_sohbetinin_kendi_anahtari_gorseli_eziyor(env):
    ac.save_credentials("GORSEL", "https://gorsel/openai/v1/")
    ac.save_env({"AZURE_CHAT_API_KEY": "SOHBET",
                 "AZURE_CHAT_BASE_URL": "https://sohbet/openai/v1/"})

    assert credstore.resolve("azure_chat") == ("SOHBET", "https://sohbet/openai/v1/")


def test_tanimsiz_kimlik_ham_500_DEGIL_Turkce_hata(env):
    """Katalog ile kod ayrışması programlama hatası, ama yine de 502'ye
    çevrilebilir bir tür olmalı: ham 500'de arayüz gövdeyi ayrıştıramıyor."""
    with pytest.raises(ac.ImageError):
        credstore.resolve("boyle-bir-saglayici-yok")

    assert credstore.is_configured("boyle-bir-saglayici-yok") is False


def test_is_configured_resolve_ile_AYNI_karari_veriyor(env):
    """İki ayrı "eksik mi?" mantığı olmamalı — biri diğerinden sapabilir.

    `is_configured` bilerek `resolve`'u çağırıp istisnayı yutuyor; bu test o
    bağın gerçekten kurulu olduğunu ölçüyor.
    """
    ac.save_env({"GEMINI_API_KEY": "AIzaSyDUMMY1234567890abcdefghij"})
    for cred in catalog.CREDENTIALS:
        try:
            credstore.resolve(cred.id)
        except ac.ImageError:
            beklenen = False
        else:
            beklenen = True
        assert credstore.is_configured(cred.id) is beklenen, cred.id


# ── Azure AI Foundry (MAI + FLUX) ──────────────────────────────────────
#
# Bu bloğun ölçtüğü şey tek cümle: kullanıcıdan İKİNCİ bir anahtar ve İKİNCİ
# bir adres istemeden MAI/FLUX'a ulaşılabilmeli — ama tanınmayan bir hostta
# SESSİZCE yanlış bir adrese düşülmemeli.


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


def test_foundry_anahtari_GORSELIN_anahtarina_dusuyor(env):
    """Sonda tek anahtarın üç yüzeyde de geçtiğini ölçtü (`azure_chat`in
    ikizi). İkinci bir anahtar istemek, aynı değeri iki kez yazdırmak olurdu."""
    ac.save_credentials("PAYLASILAN", "https://ai-ornek.openai.azure.com/openai/v1/")

    key, url = credstore.resolve("azure_foundry")
    assert key == "PAYLASILAN"
    assert url == "https://ai-ornek.services.ai.azure.com"
    assert credstore.is_configured("azure_foundry") is True


def test_foundry_nun_KENDI_anahtari_gorseli_eziyor(env):
    """Ayrı bir kaynak/anahtar kullanan kurulum forma alan eklemeden mümkün
    olmalı (`azure_chat`in aynı davranışı)."""
    ac.save_credentials("GORSEL", "https://ai-ornek.openai.azure.com/openai/v1/")
    ac.save_env({"AZURE_FOUNDRY_API_KEY": "FOUNDRY"})

    assert credstore.resolve("azure_foundry")[0] == "FOUNDRY"


def test_ELLE_yazilan_foundry_adresi_turetmeyi_eziyor(env):
    ac.save_credentials("K", "https://ai-ornek.openai.azure.com/openai/v1/")
    ac.save_env({"AZURE_FOUNDRY_BASE_URL": "https://ozel.ornek/foundry"})

    assert credstore.resolve("azure_foundry")[1] == "https://ozel.ornek/foundry"


def test_TANINMAYAN_hostta_hata_ALAN_ADINI_soyluyor(env):
    """Çıkışı olmayan bir hata olmamalı: mesaj hangi env değişkenini
    doldurmak gerektiğini ADIYLA söylemeli."""
    ac.save_credentials("K", "https://vekil.sirket.local/azure/openai/v1/")

    with pytest.raises(ac.ImageError) as exc:
        credstore.resolve("azure_foundry")

    mesaj = str(exc.value)
    assert "AZURE_FOUNDRY_BASE_URL" in mesaj
    assert credstore.is_configured("azure_foundry") is False


def test_anahtarsiz_kurulumda_foundry_KAPALI(env):
    """Adres türetilse bile anahtar yoksa model seçilebilir olmamalı."""
    ac.save_env({"AZURE_IMAGE_BASE_URL": "https://ai-ornek.openai.azure.com/openai/v1/"})

    assert credstore.is_configured("azure_foundry") is False
