"""Prompt Yönetmeni sohbet istemcisi — tests/test_azure_client_http.py'nin ikizi.

Sahte istemci kalıbı oradan alındı: ham httpx yüzeyi, kendi hata sınıfı, Türkçe
kullanıcı mesajları. Tek yapısal fark yanıtın çözümlenmesi (base64 görsel değil,
metin + finish_reason).
"""
import pytest

import azure_client as ac
import chat_client as cc
import models

CREDS = ("secret-key", "https://ex.azure.com/openai/v1/", "gpt-5.6-luna")
MESSAGES = [{"role": "user", "content": "kare instagram görseli"}]


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
    """httpx.Client yerine geçen minimal sahte istemci."""
    def __init__(self, response):
        self._response = response
        self.last_call = None

    def post(self, url, headers=None, json=None, timeout=None):
        self.last_call = {"url": url, "headers": headers, "json": json, "timeout": timeout}
        return self._response


class RaisingClient:
    """post()'ta taşıma hatası fırlatan istemci — ağ arızasını taklit eder."""
    def __init__(self, exc):
        self._exc = exc

    def post(self, url, **kwargs):
        raise self._exc


def test_complete_calls_the_chat_completions_endpoint():
    """Canlı doğrulandı: `api-version` sorgu parametresi GEREKMİYOR (HTTP 200)."""
    client = FakeClient(FakeResponse(200, _ok_body()))
    out = cc.complete(MESSAGES, client=client, credentials=CREDS, instructions="TALİMAT")

    assert out["content"] == "pong"
    assert client.last_call["url"] == "https://ex.azure.com/openai/v1/chat/completions"
    assert client.last_call["headers"]["Authorization"] == "Bearer secret-key"
    assert "api-version" not in client.last_call["url"]


def test_payload_carries_the_deployment_name_as_model():
    """Azure'da `model` alanı DAĞITIM adıdır, model ailesi adı değil.

    `gpt-5.6-luna` yazılmalı; `gpt-5.6` yazılırsa 404 döner ve hata mesajı
    "model bulunamadı" gibi görünmediği için teşhisi zordur.
    """
    client = FakeClient(FakeResponse(200, _ok_body()))
    cc.complete(MESSAGES, client=client, credentials=CREDS, instructions="TALİMAT")

    assert client.last_call["json"]["model"] == "gpt-5.6-luna"


def test_system_instructions_are_prepended_by_the_server():
    client = FakeClient(FakeResponse(200, _ok_body()))
    cc.complete(MESSAGES, client=client, credentials=CREDS, instructions="TALİMAT METNİ")

    messages = client.last_call["json"]["messages"]
    assert messages[0] == {"role": "system", "content": "TALİMAT METNİ"}
    assert messages[1:] == MESSAGES


def test_payload_stays_minimal():
    """TRIPWIRE: örnekleme parametresi eklenirse CANLI doğrulanmalı.

    GPT-5 sınıfı akıl yürüten dağıtımlar `temperature`/`top_p`'yi 400 ile
    reddedebiliyor ve `max_tokens` yerine `max_completion_tokens` istiyorlar.
    Hiçbiri gerekli değil: persona'nın tamamı sistem talimatında. "İyileştirme"
    niyetiyle eklenen bir alan sohbeti tümden kırar, bu test onu erken yakalar.
    """
    client = FakeClient(FakeResponse(200, _ok_body()))
    cc.complete(MESSAGES, client=client, credentials=CREDS, instructions="T")

    assert set(client.last_call["json"]) == {"model", "messages"}


def test_chat_sends_its_read_timeout_with_a_short_connect_timeout():
    """Okuma uzun, bağlanma kısa: yazım hatası olan bir endpoint okuma süresi
    kadar bekletmemeli.
    """
    client = FakeClient(FakeResponse(200, _ok_body()))
    cc.complete(MESSAGES, client=client, credentials=CREDS, instructions="T")

    sent = client.last_call["timeout"]
    assert sent.read == cc.REQUEST_TIMEOUT
    assert sent.connect == ac.CONNECT_TIMEOUT < cc.REQUEST_TIMEOUT


def test_image_generation_gets_at_least_as_much_time_as_chat():
    """Eskiden bunun TERSİ çivilenmişti: "talimat + akıl yürütme görselden uzun
    sürer" gerekçesiyle sohbet zaman aşımının görselden büyük olması isteniyordu.

    Ölçüm çürüttü (2026-08-04): gerçek sohbet turları 4,9 s ve 9,3 s sürerken
    görsel üretimi 120 s'yi aşıp ReadTimeout'a düştü. Yavaş olan taraf görsel
    üretimi ve tek istekte n görsel ürettiği için süresi adetle büyüyor.
    """
    assert ac.read_timeout_for(1) >= cc.REQUEST_TIMEOUT
    assert ac.read_timeout_for(4) > ac.read_timeout_for(1)


def test_complete_wraps_transport_errors_into_chat_error():
    """Sohbet de aynı ağın üstünde: sarmalanmayan httpx hatası `/api/chat`'in
    `except ChatError` süzgecinden geçip ham 500 olur ve kullanıcı Türkçe bir
    sebep görmez. Görsel tarafındaki ikizi: test_azure_client_http.py.
    """
    import httpx
    client = RaisingClient(httpx.ReadTimeout("timed out"))
    with pytest.raises(cc.ChatError) as exc:
        cc.complete(MESSAGES, client=client, credentials=CREDS, instructions="T")
    assert "zaman aşımı" in str(exc.value).lower()


# ── Hata eşlemesi ───────────────────────────────────────────────────────

def test_map_error_speaks_turkish_for_the_usual_failures():
    assert "401" in cc.map_error(401, None)
    assert "429" in cc.map_error(429, None)
    # İDDİA HARF DÖNÜŞÜMSÜZ: "İ".lower() Python'da "i" değil "i̇" (i + birleşen
    # nokta) üretir, yani `"içerik" in metin.lower()` Türkçe metinde DÜŞER.
    filtered = cc.map_error(400, {"error": {"message": "content filter triggered"}})
    assert "İçerik politikası reddi" in filtered


def test_map_error_names_the_deployment_for_404():
    """Bu uçta EN SIK hata: Ayarlar'daki ad ile Foundry'deki ad ayrışması.

    Genel "istek başarısız" metni kullanıcıyı hiçbir yere götürmez; 404 burada
    tek bir eyleme işaret ediyor, o yüzden kendi mesajı var.
    """
    message = cc.map_error(404, {"error": {"message": "not found"}})
    assert "404" in message
    assert "dağıtım" in message.lower()


def test_complete_raises_chat_error_on_http_failure():
    client = FakeClient(FakeResponse(404, {"error": {"message": "no such deployment"}}))
    with pytest.raises(cc.ChatError) as exc:
        cc.complete(MESSAGES, client=client, credentials=CREDS, instructions="T")
    assert "dağıtım" in str(exc.value).lower()


def test_complete_survives_an_unparsable_error_body():
    class Unparsable(FakeResponse):
        def json(self):
            raise ValueError("gövde JSON değil")

    client = FakeClient(Unparsable(500, None))
    with pytest.raises(cc.ChatError) as exc:
        cc.complete(MESSAGES, client=client, credentials=CREDS, instructions="T")
    assert "500" in str(exc.value)


# ── Yanıt çözümleme: boş içerik GÜRÜLTÜLÜ hata, boş baloncuk DEĞİL ──────

@pytest.mark.parametrize("body", [
    {"choices": []},
    {},
    {"choices": [{"message": {}}]},
    {"choices": [{"message": {"content": None}}]},
    {"choices": [{"message": {"content": "   "}}]},
])
def test_extract_content_turns_empty_replies_into_a_chat_error(body):
    """IndexError/KeyError DEĞİL: o ikisi 500 olur ve kullanıcı Türkçe hata görmez.

    Sessiz boş baloncuk daha da kötü — kullanıcı "cevap vermedi" der, iz kalmaz.
    """
    with pytest.raises(cc.ChatError):
        cc.extract_content(body)


def test_extract_content_puts_the_finish_reason_in_the_error():
    """`length` + boş içerik `max_completion_tokens` gerektiğinin tek işareti.

    Mesaja girmezse aynı hata birkaç tur boyunca teşhis edilemez.
    """
    with pytest.raises(cc.ChatError) as exc:
        cc.extract_content({"choices": [{"finish_reason": "length",
                                         "message": {"content": ""}}]})
    assert "length" in str(exc.value)


def test_extract_content_returns_the_content_and_finish_reason():
    assert cc.extract_content(_ok_body("metin", "stop")) == ("metin", "stop")


def test_a_reply_at_the_cap_passes_through():
    content = "y" * models.MAX_CHAT_REPLY_CHARS

    assert cc.extract_content(_ok_body(content)) == (content, "stop")


def test_a_reply_over_the_cap_is_a_turkish_chat_error():
    """Sınırı AŞAN yanıt burada, ayrıştırıldığı yerde patlar.

    Geçirilse ekrana çizilirdi ama `ChatMessage`'a sığmazdı: bir sonraki tur ve
    kaydetme İngilizce bir 422 ile geri dönerdi ve sohbet sessizce kilitlenirdi.
    Hata metni Türkçe ve eyleme dönük — rota bunu 502 olarak veriyor.
    """
    with pytest.raises(cc.ChatError) as exc:
        cc.extract_content(_ok_body("y" * (models.MAX_CHAT_REPLY_CHARS + 1)))

    assert "uzun" in str(exc.value)


def test_complete_reports_the_finish_reason_to_the_caller():
    """Kırpılmış bir yanıt arayüzde görünebilsin (içerik var ama tamamlanmamış)."""
    client = FakeClient(FakeResponse(200, _ok_body("yarım", "length")))
    out = cc.complete(MESSAGES, client=client, credentials=CREDS, instructions="T")

    assert out == {"content": "yarım", "finish_reason": "length"}


# ── Kimlik çözümü ───────────────────────────────────────────────────────

def test_load_credentials_falls_back_to_the_image_credentials(tmp_path, monkeypatch):
    env = tmp_path / "app.env"
    env.write_text("AZURE_IMAGE_API_KEY=K\n"
                   "AZURE_IMAGE_BASE_URL=https://ep/openai/v1/\n"
                   "AZURE_CHAT_DEPLOYMENT=gpt-5.6-luna\n", encoding="utf-8")

    assert cc.load_credentials(str(env)) == ("K", "https://ep/openai/v1/", "gpt-5.6-luna")


def test_load_credentials_prefers_the_chat_specific_keys(tmp_path):
    env = tmp_path / "app.env"
    env.write_text("AZURE_IMAGE_API_KEY=IMG\n"
                   "AZURE_IMAGE_BASE_URL=https://img/openai/v1/\n"
                   "AZURE_CHAT_API_KEY=CHAT\n"
                   "AZURE_CHAT_BASE_URL=https://chat/openai/v1/\n"
                   "AZURE_CHAT_DEPLOYMENT=d\n", encoding="utf-8")

    assert cc.load_credentials(str(env)) == ("CHAT", "https://chat/openai/v1/", "d")


def test_load_credentials_names_the_missing_deployment_in_turkish(tmp_path):
    env = tmp_path / "app.env"
    env.write_text("AZURE_IMAGE_API_KEY=K\n"
                   "AZURE_IMAGE_BASE_URL=https://ep/openai/v1/\n", encoding="utf-8")

    with pytest.raises(cc.ChatError) as exc:
        cc.load_credentials(str(env))
    assert "dağıtım" in str(exc.value).lower()


def test_load_credentials_reports_missing_azure_credentials(tmp_path):
    env = tmp_path / "app.env"
    env.write_text("AZURE_CHAT_DEPLOYMENT=d\n", encoding="utf-8")

    with pytest.raises(cc.ChatError) as exc:
        cc.load_credentials(str(env))
    assert "kimlik" in str(exc.value).lower()


def test_missing_instructions_file_becomes_a_chat_error(monkeypatch):
    """chat_prompt düz ValueError yükseltiyor; kullanıcıya ChatError olarak çıkmalı.

    Tek yönlü bağımlılık (chat_client → chat_prompt) döngüsel import'u imkânsız
    kılıyor; çeviri bu yüzden burada yapılıyor.
    """
    client = FakeClient(FakeResponse(200, _ok_body()))
    monkeypatch.setattr(cc.chat_prompt, "load_instructions",
                        lambda **kw: (_ for _ in ()).throw(ValueError("talimat yok")))

    with pytest.raises(cc.ChatError) as exc:
        cc.complete(MESSAGES, client=client, credentials=CREDS)
    assert "talimat" in str(exc.value).lower()
