"""gemini_client: Interactions telinin şekli, döngü ve hata çevirisi.

Bu dosyanın en değerli iki iddiası:

  1. ADET TEL ÜZERİNDE YOK. Interactions ucunun görsel tarafında `n` alanı
     bulunmuyor, yani n görsel n istek demek — ve zaman aşımı politikası tam
     olarak bu ayrımın üstünde duruyor (`providers.read_timeout_for` yanlış
     dalı seçerse n=4'te her isteğe 540 saniye verilir: 36 dakika).
  2. GÖRSEL YERİNE METİN dönen 200. Model bir prompt'u reddettiğinde HTTP
     200 ile geri dönüyor ve gerekçeyi metin bloğu olarak yazıyor; o metni
     yutmak kullanıcıya sebebi olmayan bir 502 vermek olurdu.

DİKKAT — canlı doğrulama YAPILMADI: iddialar tel formatının BELGELENEN hâlini
sabitliyor (ai.google.dev/gemini-api → image generation), gerçek bir Gemini
anahtarıyla çağrı yapılmadı. Şekil `openai_client`'ın aksine Azure ikiziyle
AYNI DEĞİL, yani buradaki risk daha yüksek ve bilinçli olarak kaydediliyor:
uç, başlık adı, `response_format` alanları ve `steps[].content[]` yanıtı ilk
gerçek anahtarla bir kez sınanmalı.
"""
import base64

import pytest

import azure_client as ac
import catalog
import gemini_client as gc
import providers

MODEL = catalog.image_model("gemini-nano-banana-2")
PRO = catalog.image_model("gemini-nano-banana-pro")
CREDS = ("AIzaTESTKEY", "https://generativelanguage.googleapis.com")


class FakeResponse:
    def __init__(self, status_code, json_body=None):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        if self._json is None:
            raise ValueError("gövde JSON değil")
        return self._json


class FakeClient:
    """`httpx.Client` yerine geçen minimal sahte istemci.

    `test_openai_client.py`'deki kardeşinden bir ayrım: BÜTÜN çağrıları
    biriktiriyor (`calls`), yalnız sonuncusunu değil. Döngü iddiası ölçülebilir
    olsun diye — tek bir `last_call` ile "n istek atıldı mı?" sorusu
    cevaplanamaz.
    """

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json,
                           "timeout": timeout})
        # Tek yanıt verildiyse her çağrıda o dönüyor (döngü testlerinin çoğu
        # yanıtın kendisiyle ilgilenmiyor).
        return (self._responses[len(self.calls) - 1]
                if len(self._responses) > 1 else self._responses[0])

    @property
    def last_call(self):
        return self.calls[-1]


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def _gorsel_yanit(ham=b"\x89PNG", metin=None):
    blok = [{"type": "image", "data": _b64(ham), "mime_type": "image/png"}]
    if metin:
        blok.insert(0, {"type": "text", "text": metin})
    return FakeResponse(200, {"status": "completed", "object": "interaction",
                             "steps": [{"type": "model_output", "content": blok}]})


# ── Tel formatı ────────────────────────────────────────────────────────


def test_uc_yolu_SURUM_onekini_kodda_tasiyor():
    """`GEMINI_BASE_URL` çıplak konak: sürüm geçişi kullanıcının kayıtlı
    adresini geçersiz kılan bir migrasyon OLMAMALI."""
    c = FakeClient(_gorsel_yanit())

    gc.generate(MODEL, "kedi", "1:1", "2K", 1, client=c, credentials=CREDS)

    assert c.last_call["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/interactions")


def test_adres_sonundaki_egik_cizgi_ucu_bozmuyor():
    c = FakeClient(_gorsel_yanit())

    gc.generate(MODEL, "k", "1:1", "2K", 1, client=c,
                credentials=("AIza", "https://generativelanguage.googleapis.com/"))

    assert c.last_call["url"].endswith("/v1beta/interactions")
    assert "//v1beta" not in c.last_call["url"]


def test_kimlik_GOOGLE_basligiyla_gidiyor_Bearer_ile_DEGIL():
    """Üç sağlayıcının üçüncü kimlik şekli: `x-goog-api-key`."""
    c = FakeClient(_gorsel_yanit())

    gc.generate(MODEL, "k", "1:1", "2K", 1, client=c, credentials=CREDS)

    assert c.last_call["headers"]["x-goog-api-key"] == "AIzaTESTKEY"
    assert "Authorization" not in c.last_call["headers"]


def test_ORAN_ve_COZUNURLUK_response_format_a_giriyor_size_quality_OLARAK_DEGIL():
    """Kataloğun `sizes`/`qualities` alanları Gemini'de BAŞKA iki tel alanına
    çözülüyor. Azure'ın `size`/`quality` adlarını göndermek 400 demek."""
    c = FakeClient(_gorsel_yanit())

    gc.generate(MODEL, "kedi", "16:9", "4K", 1, client=c, credentials=CREDS)

    govde = c.last_call["json"]
    assert govde["model"] == "gemini-3.1-flash-image"
    assert govde["response_format"] == {"type": "image", "aspect_ratio": "16:9",
                                        "image_size": "4K"}
    assert "size" not in govde and "quality" not in govde


def test_prompt_input_dizisinin_ILK_blogu():
    c = FakeClient(_gorsel_yanit())

    gc.generate(MODEL, "turuncu kedi", "1:1", "2K", 1, client=c, credentials=CREDS)

    assert c.last_call["json"]["input"] == [
        {"type": "text", "text": "turuncu kedi"}]


def test_iki_gemini_modeli_ayni_adaptorden_KENDI_adiyla_gidiyor():
    c = FakeClient(_gorsel_yanit())

    gc.generate(PRO, "k", "1:1", "2K", 1, client=c, credentials=CREDS)

    assert c.last_call["json"]["model"] == "gemini-3-pro-image"


# ── Adet: tel üzerinde YOK, döngüyle çözülüyor ─────────────────────────


def test_adet_TEL_UZERINDE_yok_DONGU_ile_cozuluyor():
    """`images_per_request=1` beyanının tel tarafındaki karşılığı."""
    c = FakeClient(_gorsel_yanit(b"BIR"), _gorsel_yanit(b"IKI"),
                   _gorsel_yanit(b"UC"))

    out = gc.generate(MODEL, "k", "1:1", "2K", 3, client=c, credentials=CREDS)

    assert len(c.calls) == 3, "adet gövdeye konmuş olabilir"
    assert all("n" not in ç["json"] for ç in c.calls)
    assert out == [b"BIR", b"IKI", b"UC"]


def test_dongunun_EN_KOTU_HALI_providers_total_budget_e_esit():
    """Asıl bulgu burada ölçülüyor: her isteğe verilen süre ADETLE BÜYÜMÜYOR,
    büyüyen şey döngünün toplamı.

    Karışsa n=4'te her isteğe 540 saniye verilirdi (36 dakikalık en kötü hâl);
    doğrusu her isteğe 180 ve toplamda 720.
    """
    c = FakeClient(_gorsel_yanit())

    gc.generate(MODEL, "k", "1:1", "2K", 4, client=c, credentials=CREDS)

    tek = providers.read_timeout_for(MODEL, 4)
    assert tek == ac.read_timeout_for(1)
    # `httpx.Timeout` nesnesinin okuma bacağı tam olarak o sayı olmalı.
    assert all(ç["timeout"].read == tek for ç in c.calls)
    assert len(c.calls) * tek == providers.total_budget(MODEL, 4)


def test_bir_istek_dusunce_KISMI_sonuc_donmuyor():
    """Sessiz sapma yasak: kullanıcı 3 istedi, 2 aldı ve bunu hiçbir yerde
    okumadı olmamalı. Adedi kısan tek yer `fillAxis`in yüksek sesle söylediği
    kademe."""
    c = FakeClient(_gorsel_yanit(b"BIR"), FakeResponse(429, None),
                   _gorsel_yanit(b"UC"))

    with pytest.raises(ac.ImageError, match="429"):
        gc.generate(MODEL, "k", "1:1", "2K", 3, client=c, credentials=CREDS)


# ── edit: referanslar AYNI dizide ──────────────────────────────────────


def test_referanslar_AYNI_input_dizisinde_base64_olarak_gidiyor():
    """Gemini'de düzenleme ayrı bir uç DEĞİL — `/images/edits` karşılığı yok."""
    c = FakeClient(_gorsel_yanit())

    gc.edit(MODEL, "logoyu ekle", [("ana.png", b"ANA"), ("ek.png", b"EK")],
            "3:2", "1K", 1, client=c, credentials=CREDS)

    girdi = c.last_call["json"]["input"]
    assert girdi[0] == {"type": "text", "text": "logoyu ekle"}
    # SIRA korunuyor: sözleşme "ilk görsel ana referans" diyor.
    assert [b["data"] for b in girdi[1:]] == [_b64(b"ANA"), _b64(b"EK")]
    assert all(b["mime_type"] == "image/png" for b in girdi[1:])
    assert c.last_call["url"].endswith("/v1beta/interactions")


def test_duzenleme_de_ayni_response_format_i_kullaniyor():
    c = FakeClient(_gorsel_yanit())

    gc.edit(MODEL, "p", [("a.png", b"A")], "9:16", "4K", 1,
            client=c, credentials=CREDS)

    assert c.last_call["json"]["response_format"]["aspect_ratio"] == "9:16"
    assert c.last_call["json"]["response_format"]["image_size"] == "4K"


# ── Yanıt çözümlemesi ──────────────────────────────────────────────────


def test_gorsel_bloklari_METIN_bloklariyla_ayni_listede_ayiklaniyor():
    """Model açıklama metnini görselin YANINA koyabiliyor; görsel yine çıkmalı."""
    c = FakeClient(_gorsel_yanit(b"PNGBAYT", metin="İşte istediğin görsel."))

    out = gc.generate(MODEL, "k", "1:1", "2K", 1, client=c, credentials=CREDS)

    assert out == [b"PNGBAYT"]


def test_gorsel_YOKSA_modelin_METNI_hataya_giriyor():
    """Reddi yutmak, sebebi olmayan bir 502 vermek olurdu."""
    c = FakeClient(FakeResponse(200, {
        "status": "completed",
        "steps": [{"type": "model_output", "content": [
            {"type": "text", "text": "Bu isteği yerine getiremiyorum."}]}]}))

    with pytest.raises(ac.ImageError, match="yerine getiremiyorum"):
        gc.generate(MODEL, "k", "1:1", "2K", 1, client=c, credentials=CREDS)


def test_tamamlanmamis_DURUM_mesaja_giriyor():
    c = FakeClient(FakeResponse(200, {"status": "failed", "steps": []}))

    with pytest.raises(ac.ImageError, match="failed"):
        gc.generate(MODEL, "k", "1:1", "2K", 1, client=c, credentials=CREDS)


def test_steps_YOKSA_Turkce_hata_ham_KeyError_DEGIL():
    """`KeyError` → ham 500 olurdu ve arayüz gövdeyi ayrıştıramazdı."""
    c = FakeClient(FakeResponse(200, {"candidates": [{"content": {}}]}))

    with pytest.raises(ac.ImageError, match="steps yok"):
        gc.generate(MODEL, "k", "1:1", "2K", 1, client=c, credentials=CREDS)


# ── Hata çevirisi ──────────────────────────────────────────────────────


def test_400_ANAHTAR_hatasi_ile_JETON_hatasini_ayiriyor():
    """Google ikisini de 400 ile döndürüyor. Ayrımı yapmamak, anahtarı doğru
    olan kullanıcıya "anahtarını kontrol et" demek — yani onu çalışan
    kurulumunu bozmaya davet etmek."""
    anahtar = gc.map_error(400, {"error": {"message": "API key not valid. "
                                                     "Please pass a valid API key."}})
    assert "anahtarı geçersiz" in anahtar

    jeton = gc.map_error(400, {"error": {"message": "Unsupported aspect_ratio: 7:3"}})
    assert "anahtar" not in jeton.lower()
    assert "7:3" in jeton


def test_404_MODEL_adini_soyluyor():
    """`openai-dall-e-3` deneyiminin dersi: hangi modelin bulunamadığını
    söylemeyen bir hata, kullanıcıyı anahtarını kurcalamaya iter."""
    mesaj = gc.map_error(404, {"error": {"message": "models/eski-ad is not found"}})
    assert "modeli tanımıyor" in mesaj
    assert "eski-ad" in mesaj


@pytest.mark.parametrize("kod,parca", [
    (401, "reddetti"),
    (403, "reddetti"),
    (429, "limiti aşıldı"),
    (500, "HTTP 500"),
])
def test_hata_metinleri_GEMINI_den_soz_ediyor(kod, parca):
    """METİN paylaşılmıyor: "OpenAI yetkilendirme hatası" diyen bir mesaj
    Gemini anahtarını kurcalayan kullanıcıyı yanlış forma yönlendirir."""
    mesaj = gc.map_error(kod, None)
    assert parca in mesaj
    assert "Gemini" in mesaj
    assert "OpenAI" not in mesaj and "Azure" not in mesaj


def test_tasima_hatasinin_mesaji_AZURE_demiyor():
    """`ac.transport_error_message` yeniden kullanılıyor (ÜCRET UYARISI dahil),
    ama sağlayıcı adı düzeltiliyor."""
    import httpx

    class Patlayan:
        def post(self, *a, **k):
            raise httpx.ConnectTimeout("zaman aşımı")

    with pytest.raises(ac.ImageError) as exc:
        gc.generate(MODEL, "k", "1:1", "2K", 1, client=Patlayan(), credentials=CREDS)

    assert "Azure" not in str(exc.value)
    assert "Gemini" in str(exc.value)
