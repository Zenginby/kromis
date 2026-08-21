"""OpenAI-uyumlu sohbet ucu — tests/test_chat_client.py'nin ikizi.

Sahte istemci kalıbı oradan alındı. Bu dosyanın ölçtüğü şey o dosyanın
ölçemediği taraf: AYNI tel, İKİ sağlayıcı, ayrışan tek iki şey (yol ve hata
metnindeki ad) ve ikisi de KATALOGDAN geliyor. İddiaların çoğu "OpenAI'ye
gitmesi gereken bir mesaj Azure'dan söz etmiyor" biçiminde, çünkü v0.6'da
ölçülmüş kırılma buydu: kullanıcı yanlış formu kurcalıyor.
"""
import httpx
import pytest

import catalog
import chat_client as cc
import openai_chat

OPENAI = catalog.chat_model("openai-gpt-5.6-terra")
GEMINI = catalog.chat_model("gemini-3.7-flash")
MESSAGES = [{"role": "user", "content": "kare instagram görseli"}]
CREDS = ("secret-key", "https://api.openai.com/v1")
GEMINI_CREDS = ("AIza-secret", "https://generativelanguage.googleapis.com")


def _ok_body(content="pong", finish_reason="stop"):
    return {"choices": [{"finish_reason": finish_reason,
                         "message": {"role": "assistant", "content": content}}]}


class FakeResponse:
    def __init__(self, status_code, json_body):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        return self._json


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.last_call = None

    def post(self, url, headers=None, json=None, timeout=None):
        self.last_call = {"url": url, "headers": headers, "json": json,
                          "timeout": timeout}
        return self._response


class RaisingClient:
    def __init__(self, exc):
        self._exc = exc

    def post(self, url, **kwargs):
        raise self._exc


def _cagir(m, creds, response=None, **kw):
    client = FakeClient(response or FakeResponse(200, _ok_body()))
    out = openai_chat.complete(m, MESSAGES, client=client, credentials=creds,
                               instructions="TALİMAT", **kw)
    return client, out


# ── Tel ────────────────────────────────────────────────────────────────


def test_OPENAI_yolu_chat_completions_ucuna_cikiyor():
    client, out = _cagir(OPENAI, CREDS)
    assert out["content"] == "pong"
    assert client.last_call["url"] == "https://api.openai.com/v1/chat/completions"


def test_GEMINI_yolu_UYUMLULUK_ucunden_geciyor():
    """Gemini'nin OpenAI-uyumlu ucu `/v1beta/openai/` altında yaşıyor.

    Kimliğin `base_url`ü görsel tarafıyla PAYLAŞILIYOR (`/v1beta/interactions`),
    yani yol katalogdan gelmezse aynı adres iki ayrı ucu birden gösteremezdi ve
    sohbet 404 dönerdi.
    """
    client, _ = _cagir(GEMINI, GEMINI_CREDS)
    assert client.last_call["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")


def test_YOL_kimligin_adresinin_sonundaki_egik_cizgiyi_iki_kez_yazmiyor():
    """Azure'ın adresi `…/openai/v1/` biçiminde bitiyor; kullanıcı OpenAI için
    de sonu eğik çizgili bir vekil adresi yazabiliyor. `//chat/completions`
    bazı vekillerde 404 döner."""
    client, _ = _cagir(OPENAI, ("k", "https://vekil.example/v1/"))
    assert client.last_call["url"] == "https://vekil.example/v1/chat/completions"


def test_ANAHTAR_bearer_basliginda_gidiyor():
    """Gemini'nin GÖRSEL ucu `x-goog-api-key` istiyor; uyumluluk ucu Bearer.

    İkisini karıştırmak 401 demek ve mesajı "anahtar geçersiz" diyeceği için
    kullanıcı çalışan anahtarını yeniden üretmeye çalışır.
    """
    client, _ = _cagir(GEMINI, GEMINI_CREDS)
    assert client.last_call["headers"]["Authorization"] == "Bearer AIza-secret"
    assert "x-goog-api-key" not in client.last_call["headers"]


def test_GOVDE_katalogdaki_wire_model_adini_tasiyor():
    """`id` bizim kararlı kimliğimiz, `wire_model` sağlayıcıya GİDEN ad."""
    client, _ = _cagir(OPENAI, CREDS)
    assert client.last_call["json"]["model"] == "gpt-5.6-terra"
    client, _ = _cagir(GEMINI, GEMINI_CREDS)
    assert client.last_call["json"]["model"] == "gemini-3.7-flash"


def test_GOVDE_chat_client_ile_AYNI_fonksiyondan_kuruluyor():
    """Minimal gövde duruşu PAYLAŞILIYOR: `temperature`/`max_tokens` YOK.

    İkinci bir gövde kurucusu yazılsaydı `chat_client.build_payload`'ın
    tripwire'ı bu dosyayı ölçmezdi ve bir gün buraya sessizce bir sampling
    parametresi girerdi — GPT-5 sınıfı modeller onu 400 ile reddediyor.
    """
    client, _ = _cagir(OPENAI, CREDS)
    govde = client.last_call["json"]
    assert set(govde) == {"model", "messages"}
    assert govde["messages"][0] == {"role": "system", "content": "TALİMAT"}
    assert govde["messages"][1:] == MESSAGES


def test_ZAMAN_ASIMI_chat_client_ile_PAYLASILIYOR():
    """Ağ davranışı sağlayıcıya göre değişmiyor; iki ayrı sayı tutmak birini
    ayarlayıp diğerini unutmanın kapısı olurdu."""
    client, _ = _cagir(OPENAI, CREDS)
    assert client.last_call["timeout"].read == cc.REQUEST_TIMEOUT


# ── Yanıt çözümlemesi (chat_client ile PAYLAŞILAN) ──────────────────────


def test_BOS_yanit_gurultulu_hata_oluyor():
    """`extract_content` PAYLAŞILIYOR: üç kapısı da (boş choices, boş içerik,
    yanıt uzunluğu tavanı) sağlayıcıdan bağımsız olgular."""
    with pytest.raises(cc.ChatError) as e:
        _cagir(OPENAI, CREDS, FakeResponse(200, {"choices": []}))
    assert "boş döndü" in str(e.value)


def test_finish_reason_yanitla_birlikte_donuyor():
    _, out = _cagir(OPENAI, CREDS, FakeResponse(200, _ok_body(finish_reason="length")))
    assert out["finish_reason"] == "length"


# ── Hata metinleri: ŞEKİL paylaşılıyor, METİN paylaşılmıyor ─────────────


@pytest.mark.parametrize("kod", [401, 403, 429, 500])
def test_HATA_metni_dogru_saglayiciyi_soyluyor(kod):
    """Metin "Azure" derse kullanıcı hiç ihtiyacı olmayan formu kurcalar.

    Ad KATALOGDAN geliyor (`Credential.label`), yani kullanıcı hatada okuduğu
    adı Ayarlar panelinde birebir buluyor.
    """
    with pytest.raises(cc.ChatError) as e:
        _cagir(OPENAI, CREDS, FakeResponse(kod, {"error": {"message": "nope"}}))
    mesaj = str(e.value)
    assert "OpenAI" in mesaj
    assert "Azure" not in mesaj
    assert "Gemini" not in mesaj


@pytest.mark.parametrize("kod", [401, 429])
def test_GEMINI_hatasi_kendi_adini_soyluyor(kod):
    with pytest.raises(cc.ChatError) as e:
        _cagir(GEMINI, GEMINI_CREDS, FakeResponse(kod, None))
    assert "Google Gemini" in str(e.value)
    assert "Azure" not in str(e.value)


def test_404_MODELIN_adini_soyluyor_dagitim_adindan_soz_ETMIYOR():
    """Bu uçta 404'ün tek anlamı "bu model yok". `chat_client`ın 404 metni ise
    dağıtım adı ayrışmasını anlatıyor — OpenAI'de girilecek bir dağıtım adı
    YOK, o metni göstermek kullanıcıyı olmayan bir alana yönlendirirdi."""
    with pytest.raises(cc.ChatError) as e:
        _cagir(OPENAI, CREDS, FakeResponse(404, None))
    mesaj = str(e.value)
    assert "gpt-5.6-terra" in mesaj
    assert "dağıtım" not in mesaj.lower()


def test_icerik_politikasi_reddi_ayrilabiliyor():
    with pytest.raises(cc.ChatError) as e:
        _cagir(OPENAI, CREDS,
               FakeResponse(400, {"error": {"message": "content policy"}}))
    assert "İçerik politikası" in str(e.value)


def test_AG_HATASI_metni_de_dogru_adi_soyluyor():
    """Metin `azure_client`'ta paylaşılıyor ama sağlayıcı adı düzeltiliyor —
    `openai_client._post`'un aynı satırı. Ölçülmezse "Azure'a bağlanılamadı"
    diyen bir cümle OpenAI hatasında kalırdı."""
    with pytest.raises(cc.ChatError) as e:
        openai_chat.complete(OPENAI, MESSAGES,
                             client=RaisingClient(httpx.ConnectError("boom")),
                             credentials=CREDS, instructions="T")
    assert "OpenAI" in str(e.value)
    assert "Azure" not in str(e.value)


def test_HATA_TURU_chat_client_ile_AYNI_SINIF():
    """`app.chat` sohbet çağrısını `except cc.ChatError` ile süzüyor. İkinci bir
    tür açmak o süzgeci ikiye bölerdi: sarmalanmayan hata ham 500 olur, arayüz
    gövdeyi JSON olarak ayrıştıramaz ve kullanıcı yalnızca "Hata (500)" görür."""
    with pytest.raises(cc.ChatError):
        _cagir(OPENAI, CREDS, FakeResponse(500, None))
