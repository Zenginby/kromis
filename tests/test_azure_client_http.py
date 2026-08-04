import base64
import pytest
import azure_client as ac


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
        self.last_call = {"url": url, "headers": headers, "json": json}
        return self._response


def test_generate_calls_correct_endpoint_and_decodes():
    raw = b"\x89PNG"
    b64 = base64.b64encode(raw).decode()
    client = FakeClient(FakeResponse(200, {"data": [{"b64_json": b64}]}))
    out = ac.generate(
        "cat", "1024x1024", "medium", 1,
        client=client,
        credentials=("secret-key", "https://ex.azure.com/openai/v1/"),
    )
    assert out == [raw]
    assert client.last_call["url"] == "https://ex.azure.com/openai/v1/images/generations"
    assert client.last_call["headers"]["Authorization"] == "Bearer secret-key"
    assert client.last_call["json"]["model"] == "gpt-image-2"


def test_generate_raises_friendly_on_error():
    client = FakeClient(FakeResponse(401, {"error": {"message": "nope"}}))
    with pytest.raises(ac.AzureImageError) as exc:
        ac.generate("cat", "1024x1024", "medium", 1,
                    client=client, credentials=("k", "https://ex/"))
    assert "401" in str(exc.value)


class RaisingClient:
    """post()'ta taşıma hatası fırlatan istemci — ağ arızasını taklit eder."""
    def __init__(self, exc):
        self._exc = exc

    def post(self, url, **kwargs):
        raise self._exc


def test_generate_wraps_a_timeout_into_a_turkish_error():
    """Sarmalanmayan httpx hatası app.py'nin `except AzureImageError` süzgecinden
    GEÇER ve ham 500 + traceback olur. Arayüz o gövdeyi JSON ayrıştıramadığı için
    kullanıcı iki dakika bekledikten sonra yalnızca "Hata (500)" görüyor.

    2026-08-04'te canlıda oldu: yüksek kalite üretim 120 s'yi aştı, ReadTimeout
    fırladı, konsola dev bir traceback düştü. Zaman aşımı mesajı ayrıca isteğin
    Azure'da tamamlanmış (ve ÜCRETLENDİRİLMİŞ) olabileceğini söylemek zorunda:
    zaman aşımı istemcinin vazgeçmesidir, sunucunun değil.
    """
    import httpx
    client = RaisingClient(httpx.ReadTimeout("timed out"))
    with pytest.raises(ac.AzureImageError) as exc:
        ac.generate("cat", "1024x1024", "high", 4,
                    client=client, credentials=("k", "https://ex/"))
    msg = str(exc.value)
    assert "zaman aşımı" in msg.lower()
    assert str(int(ac.read_timeout_for(4))) in msg, (
        "kaç saniye beklendiği yazılmalı — ayar gerekiyorsa kanıt kullanıcıda olsun")
    assert "ücretlendirilmiş" in msg.lower(), "olası ücret uyarısı düşmüş"


def test_generate_wraps_a_connection_failure_separately():
    """Bağlanamamak ile yanıt gelmemek AYRI çıkışlar: ilkinde endpoint/ağ
    kontrol edilir, ikincisinde adet/kalite düşürülür. Tek mesaja indirilirse
    kullanıcı yanlış tarafı kurcalar.
    """
    import httpx
    client = RaisingClient(httpx.ConnectError("no route"))
    with pytest.raises(ac.AzureImageError) as exc:
        ac.generate("cat", "1024x1024", "medium", 1,
                    client=client, credentials=("k", "https://ex/"))
    msg = str(exc.value).lower()
    assert "bağlan" in msg
    assert "zaman aşımı" not in msg


def test_edit_wraps_transport_errors_too():
    """`edit` de aynı ağın üstünde: generate düzeltilip burası bırakılırsa
    düzenleme yolu ham 500 vermeye devam eder.
    """
    import httpx
    client = RaisingClient(httpx.ReadTimeout("timed out"))
    with pytest.raises(ac.AzureImageError):
        ac.edit("cat", [("a.png", b"\x89PNG")], "1024x1024", "medium", 1,
                client=client, credentials=("k", "https://ex/"))


def test_read_timeout_grows_with_the_image_count():
    """`build_payload` n'i TEK isteğe koyuyor: 4 görsel tek POST'ta üretiliyor,
    yani süre adetle uzuyor. Sabit bir değer ya n=4 için kısa kalır ya da n=1
    takıldığında boşuna dakikalar bekletir.
    """
    assert ac.read_timeout_for(1) == ac.READ_TIMEOUT_FIRST
    assert ac.read_timeout_for(4) == ac.READ_TIMEOUT_FIRST + 3 * ac.READ_TIMEOUT_EXTRA
    assert ac.read_timeout_for(0) == ac.READ_TIMEOUT_FIRST, "n<1 küçültmemeli"


def test_connect_timeout_is_short_and_separate_from_read():
    """Yazım hatası olan bir endpoint, okuma süresi kadar bekletmemeli: tek float
    geçilse httpx bağlanmayı da o değere kurar ve ölü adres dakikalarca asılır.
    """
    t = ac.request_timeout(ac.read_timeout_for(4))
    assert t.connect == ac.CONNECT_TIMEOUT
    assert t.connect < t.read
    assert t.read == ac.read_timeout_for(4)


def test_load_credentials_reads_env(tmp_path):
    env = tmp_path / "creds.env"
    env.write_text('AZURE_IMAGE_API_KEY=abc123\nAZURE_IMAGE_BASE_URL=https://x/openai/v1/\n')
    key, url = ac.load_credentials(str(env))
    assert key == "abc123"
    assert url == "https://x/openai/v1/"
