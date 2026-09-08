"""azure_mai_client: MAI telinin şekli, döngü ve hata çevirisi.

Bu dosyanın en değerli iddiası tel formatının EKSİLERİ: `size`, `quality` ve
`n` gövdede BULUNMAMALI. MAI tanımadığı alanı 400 ile reddetmiyor, SESSİZCE
yutuyor (sondada `size:"1x1"` yutuldu ve iki gerçek görsel üretildi), yani
fazladan gönderilen bir alanın bedeli yanlış boyutlu bir fatura — ve o kusur
hiçbir yerde görünmüyor. Görülebilir tek yer burası.

CANLI ÇAĞRI YOK: `FakeClient` dikişi tests/test_azure_client_http.py'nin
aynısı, `client=` anahtarı da o yüzden adaptör sözleşmesinde duruyor.
"""
import base64

import pytest

import azure_client as ac
import azure_mai_client as mai
import catalog
import providers

MODEL = catalog.image_model("azure-mai-image-2-6")
FLASH = catalog.image_model("azure-mai-image-2-6-flash")
CREDS = ("FOUNDRYKEY", "https://ai-ornek.services.ai.azure.com")


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

    BÜTÜN çağrıları biriktiriyor (`calls`), yalnız sonuncusunu değil: tek bir
    `last_call` ile "n istek atıldı mı?" sorusu cevaplanamaz ve bu dosyanın
    döngü iddiası tam olarak onu ölçüyor (`gemini_client` testlerinin aynı
    ayrımı).
    """

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, headers=None, json=None, data=None, files=None,
             timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json,
                           "data": data, "files": files, "timeout": timeout})
        return (self._responses[len(self.calls) - 1]
                if len(self._responses) > 1 else self._responses[0])


def _ok(sayi=1):
    b64 = base64.b64encode(b"\x89PNG").decode()
    return FakeResponse(200, {"data": [{"b64_json": b64}] * sayi})


# ── Geometri: jeton → int ──────────────────────────────────────────────


@pytest.mark.parametrize("jeton, beklenen", [
    ("1024x1024", (1024, 1024)),
    ("1024x768", (1024, 768)),
    ("1365x768", (1365, 768)),
    ("768x1365", (768, 1365)),
])
def test_split_size_converts_the_token_to_two_ints(jeton, beklenen):
    assert mai.split_size(jeton) == beklenen


@pytest.mark.parametrize("bozuk", ["1:1", "1024", "", "axb"])
def test_a_broken_token_raises_a_TURKISH_error_not_a_ValueError(bozuk):
    """Ham `ValueError` app.py'nin süzgecinden GEÇER ve ham 500 olur; arayüz o
    gövdeyi JSON ayrıştıramaz ve kullanıcı yalnızca "Hata (500)" görür."""
    with pytest.raises(ac.ImageError):
        mai.split_size(bozuk)


def test_EVERY_catalog_token_is_convertible():
    """Katalogla adaptör ayrışmasın: beyan edilen her jeton çevrilebilmeli."""
    for jeton in catalog.MAI_SIZES:
        w, h = mai.split_size(jeton)
        assert w >= catalog.MAI_MIN_EDGE and h >= catalog.MAI_MIN_EDGE


# ── Gövdenin şekli ─────────────────────────────────────────────────────


def test_the_payload_carries_width_and_height_NOT_size():
    govde = mai.build_payload("kedi", "1248x832", api_model="MAI-Image-2.6")
    assert govde == {"model": "MAI-Image-2.6", "prompt": "kedi",
                     "width": 1248, "height": 832}


@pytest.mark.parametrize("olmamali", ["size", "quality", "n"])
def test_the_payload_NEVER_carries_a_field_MAI_does_not_know(olmamali):
    """Tanınmayan alan 400 DEĞİL, sessizce yutulan bir alan — yani "gönderdim,
    demek ki uygulandı" varsayımı yanlış bir faturaya dönüşür."""
    govde = mai.build_payload("kedi", "1024x1024", api_model="MAI-Image-2.6")
    assert olmamali not in govde


def test_generate_hits_the_MAI_path_with_the_api_key_header():
    client = FakeClient(_ok())
    out = mai.generate(MODEL, "kedi", "1024x1024", "standard", 1,
                       client=client, credentials=CREDS)

    assert out == [b"\x89PNG"]
    cagri = client.calls[0]
    assert cagri["url"] == (
        "https://ai-ornek.services.ai.azure.com/mai/v1/images/generations")
    assert cagri["headers"][mai.AUTH_HEADER] == "FOUNDRYKEY"
    assert cagri["headers"]["Content-Type"] == "application/json"


def test_the_wire_name_comes_from_the_catalog_not_from_a_constant():
    """`azure_client.MODEL_NAME` gibi bir sabit BURADA YOK ve olmamalı: bu
    modül üç dağıtımı birden konuşuyor."""
    client = FakeClient(_ok())
    mai.generate(FLASH, "kedi", "1024x1024", "standard", 1,
                 client=client, credentials=CREDS)

    assert client.calls[0]["json"]["model"] == "MAI-Image-2.6-Flash"


# ── Döngü ve zaman aşımı ───────────────────────────────────────────────


def test_four_images_become_FOUR_separate_requests():
    """MAI'de `n` YOK: adet başına ayrı istek (bkz. karar 5)."""
    client = FakeClient(_ok())
    out = mai.generate(MODEL, "kedi", "1024x1024", "standard", 4,
                       client=client, credentials=CREDS)

    assert len(out) == 4
    assert len(client.calls) == 4


def test_the_read_timeout_does_NOT_grow_with_the_count():
    """Karışsa n=4'te her isteğe 540 saniye verilirdi: 36 dakikalık en kötü
    hâl (bkz. providers.read_timeout_for)."""
    client = FakeClient(_ok())
    mai.generate(MODEL, "kedi", "1024x1024", "standard", 4,
                 client=client, credentials=CREDS)

    beklenen = providers.read_timeout_for(MODEL, 4)
    assert beklenen == ac.READ_TIMEOUT_FIRST
    for cagri in client.calls:
        assert cagri["timeout"].read == beklenen


def test_a_response_with_MORE_images_than_asked_is_trimmed():
    """`models.MAX_IMAGES_PER_RUN` 4 ve `ChatMessage.image_ids` `max_length=4`:
    fazlalık sessizce ilerlemiyor, ÜCRET ÖDENDİKTEN SONRA patlıyordu."""
    client = FakeClient(_ok(3))
    out = mai.generate(MODEL, "kedi", "1024x1024", "standard", 2,
                       client=client, credentials=CREDS)

    assert len(out) == 2
    assert len(client.calls) == 1, "ilk yanıt yettiyse ikinci istek atılmamalı"


# ── Düzenleme ──────────────────────────────────────────────────────────


def test_edit_posts_ONE_multipart_image_to_the_edits_path():
    client = FakeClient(_ok())
    out = mai.edit(MODEL, "arka planı sil", [("in.png", b"\x89PNG")],
                   "1024x768", "standard", 1,
                   client=client, credentials=CREDS)

    assert out == [b"\x89PNG"]
    cagri = client.calls[0]
    assert cagri["url"] == (
        "https://ai-ornek.services.ai.azure.com/mai/v1/images/edits")
    assert cagri["json"] is None, "düzenleme multipart, JSON değil"
    assert cagri["data"] == {"model": "MAI-Image-2.6", "prompt": "arka planı sil",
                             "width": "1024", "height": "768"}
    assert set(cagri["files"]) == {"image"}
    assert "Content-Type" not in cagri["headers"], (
        "multipart sınırını istemci koyuyor; elle yazmak gövdeyi bozar")


def test_a_SECOND_reference_image_is_refused_LOUDLY():
    """Görsel düzenleme rotası model başına `max_refs`e BAKMIYOR
    (`app._collect_edit_refs` yalnız küresel MAX_EDIT_IMAGES'e bakıyor), yani
    ikinci kapı burada olmak zorunda. Sessizce düşürmek, kullanıcının
    gönderdiği referansın yok sayıldığını hiçbir yerde okumaması olurdu."""
    with pytest.raises(ac.ImageError) as exc:
        mai.edit(MODEL, "p", [("a.png", b"\x89PNG"), ("b.png", b"\x89PNG")],
                 "1024x1024", "standard", 1,
                 client=FakeClient(_ok()), credentials=CREDS)

    assert "tek referans" in str(exc.value)


def test_an_EMPTY_reference_list_is_refused():
    with pytest.raises(ac.ImageError):
        mai.edit(MODEL, "p", [], "1024x1024", "standard", 1,
                 client=FakeClient(_ok()), credentials=CREDS)


# ── Yanıt ve hata ──────────────────────────────────────────────────────


@pytest.mark.parametrize("govde", [
    {},
    {"data": []},
    {"data": [{}]},
    {"data": "bir dize"},
])
def test_an_UNEXPECTED_200_becomes_a_TURKISH_error_not_a_KeyError(govde):
    """Sarmalanmayan bir `KeyError` app.py'nin `except ac.AzureImageError`
    süzgecinden GEÇER ve ham 500 olur (spec 1. risk)."""
    with pytest.raises(ac.ImageError):
        mai.decode_images(govde)


@pytest.mark.parametrize("kod, parca", [
    (401, "401"),
    (404, "404"),
    (429, "kotası doldu"),
    (500, "HTTP 500"),
])
def test_map_error_speaks_TURKISH_for_every_status(kod, parca):
    mesaj = mai.map_error(kod, {"error": {"code": "x", "message": "boom"}})
    assert parca in mesaj


def test_the_429_message_tells_the_user_to_WAIT_not_that_it_is_broken():
    """Foundry kapasitesi düşük ve sonda sırasında `RateLimitReached` görüldü;
    ham bir 502 kullanıcıya "bozuk" der."""
    client = FakeClient(FakeResponse(429, {"error": {"message": "RateLimitReached"}}))
    with pytest.raises(ac.ImageError) as exc:
        mai.generate(MODEL, "kedi", "1024x1024", "standard", 1,
                     client=client, credentials=CREDS)

    assert "bekleyip" in str(exc.value)


def test_the_MAI_error_body_shape_is_read_through_providers_detail_of():
    """MAI'nin gövdesi (`error.code` + `message` + `details`) OpenAI şekline
    yeterince yakın: `azure_client.map_error`ın mantığı KOPYALANMIYOR."""
    assert providers.detail_of(
        {"error": {"code": "BadRequest", "message": "prompt is required"}}
    ) == "prompt is required"
    assert "prompt is required" in mai.map_error(
        400, {"error": {"code": "BadRequest", "message": "prompt is required"}})


def test_a_TIMEOUT_becomes_a_TURKISH_error_that_names_FOUNDRY():
    """"Azure'a bağlanılamadı" diyen bir metin kullanıcıyı Endpoint alanını
    kurcalamaya iter, oysa çözülemeyen adres Foundry'nin."""
    import httpx

    class RaisingClient:
        def post(self, url, **kwargs):
            raise httpx.ConnectTimeout("boom")

    with pytest.raises(ac.ImageError) as exc:
        mai.generate(MODEL, "kedi", "1024x1024", "standard", 1,
                     client=RaisingClient(), credentials=CREDS)

    mesaj = str(exc.value)
    assert "Foundry" in mesaj and "Azure" not in mesaj


def test_the_identity_is_resolved_LAZILY_when_credentials_are_given(monkeypatch):
    """Erken çözüm `providers._azure_generate`in yorumundaki 104 testlik
    dersin tekrarı olurdu."""
    def patlat(*a, **k):
        raise AssertionError("credentials verilmişken credstore çağrılmamalı")

    monkeypatch.setattr("credstore.resolve", patlat)
    out = mai.generate(MODEL, "kedi", "1024x1024", "standard", 1,
                       client=FakeClient(_ok()), credentials=CREDS)
    assert out == [b"\x89PNG"]
