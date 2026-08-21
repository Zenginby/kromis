"""openai_client: tel formatı, hata çevirisi ve `azure_client` ile kayma mandalı.

Bu dosyanın en değerli iddiası SON test: `ac.build_payload` ile bu dosyanın
`build_payload`'ı PAYLAŞILAN anahtarlar üzerinde aynı sözlüğü üretmeli.
İki dosyanın bilinçli ikiz olmasının bedeli tam olarak kayma riski; mandal o
riski ölçülebilir kılıyor.

DİKKAT — canlı doğrulama YAPILMADI: buradaki iddialar tel formatının
BELGELENEN hâlini sabitliyor, gerçek bir OpenAI anahtarıyla çağrı yapılmadı.
Uç, endpoint ve alan adları Azure ikiziyle aynı olduğu için risk düşük
(o yol canlı doğrulanmış), ama `dall-e-3`'ün URL dönen dalı gerçek bir
anahtarla bir kez sınanmalı.
"""
import base64

import pytest

import azure_client as ac
import catalog
import openai_client as oc

MODEL = catalog.image_model("openai-gpt-image-1")
DALLE = catalog.image_model("openai-dall-e-3")
CREDS = ("sk-test-key", "https://api.openai.com/v1")


class FakeResponse:
    def __init__(self, status_code, json_body=None, content=b""):
        self.status_code = status_code
        self._json = json_body
        self.content = content

    def json(self):
        if self._json is None:
            raise ValueError("gövde JSON değil")
        return self._json


class FakeClient:
    """`httpx.Client` yerine geçen minimal sahte istemci.

    `tests/test_azure_client_http.py`'deki kardeşinin aynısı, iki eklemeyle:
    `data`/`files` (multipart dalı) ve `get` (URL dönen yanıt dalı).
    """

    def __init__(self, response, get_response=None):
        self._response = response
        self._get_response = get_response
        self.last_call = None
        self.get_calls = []

    def post(self, url, headers=None, json=None, data=None, files=None, timeout=None):
        self.last_call = {"url": url, "headers": headers, "json": json,
                          "data": data, "files": files}
        return self._response

    def get(self, url, timeout=None):
        self.get_calls.append(url)
        return self._get_response


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


# ── generate ───────────────────────────────────────────────────────────


def test_generate_dogru_uca_gidiyor_ve_cozuyor():
    ham = b"\x89PNG"
    c = FakeClient(FakeResponse(200, {"data": [{"b64_json": _b64(ham)}]}))

    out = oc.generate(MODEL, "kedi", "1024x1024", "medium", 1,
                      client=c, credentials=CREDS)

    assert out == [ham]
    assert c.last_call["url"] == "https://api.openai.com/v1/images/generations"
    assert c.last_call["headers"]["Authorization"] == "Bearer sk-test-key"
    # Model KATALOGDAN geliyor, sabit değil — iki OpenAI modeli aynı adaptörü
    # paylaşıyor ve ayrımı yalnız bu alan taşıyor.
    assert c.last_call["json"]["model"] == "gpt-image-1"


def test_dalle_ayni_adaptorden_KENDI_adiyla_gidiyor():
    c = FakeClient(FakeResponse(200, {"data": [{"b64_json": _b64(b"X")}]}))

    oc.generate(DALLE, "kedi", "1024x1024", "standard", 1,
                client=c, credentials=CREDS)

    assert c.last_call["json"]["model"] == "dall-e-3"
    assert c.last_call["json"]["quality"] == "standard"


def test_adres_sonundaki_egik_cizgi_ucu_bozmuyor():
    c = FakeClient(FakeResponse(200, {"data": [{"b64_json": _b64(b"X")}]}))

    oc.generate(MODEL, "k", "1024x1024", "low", 1, client=c,
                credentials=("sk", "https://api.openai.com/v1/"))

    assert c.last_call["url"] == "https://api.openai.com/v1/images/generations"


def test_URL_donen_yanit_ikinci_bir_istekle_indiriliyor():
    """`dall-e-3` varsayılan olarak URL döndürüyor ve `response_format`
    göndermemeyi tercih ettik (gpt-image-1 onu kabul etmiyor).

    Adaptör sözleşmesi "çözülmüş PNG baytları döndür" diyor — URL dalı o
    sözleşmenin OpenAI tarafındaki bedeli. Çağıran taraf hangi şeklin geldiğini
    HİÇ öğrenmiyor; `azure_client.decode_images`'ın koşulsuz `b64_json`
    varsayımına dokunmadan bu mümkün oluyor.
    """
    c = FakeClient(FakeResponse(200, {"data": [{"url": "https://cdn/x.png"}]}),
                   get_response=FakeResponse(200, content=b"INDIRILEN"))

    out = oc.generate(DALLE, "k", "1024x1024", "standard", 1,
                      client=c, credentials=CREDS)

    assert out == [b"INDIRILEN"]
    assert c.get_calls == ["https://cdn/x.png"]


def test_ne_b64_ne_url_varsa_TURKCE_hata():
    """`KeyError` → ham 500 olurdu ve arayüz gövdeyi ayrıştıramazdı."""
    c = FakeClient(FakeResponse(200, {"data": [{"revised_prompt": "x"}]}))

    with pytest.raises(ac.ImageError, match="görsel alınamadı"):
        oc.generate(MODEL, "k", "1024x1024", "low", 1, client=c, credentials=CREDS)


def test_bos_data_TURKCE_hata():
    c = FakeClient(FakeResponse(200, {"data": []}))

    with pytest.raises(ac.ImageError, match="boş döndü"):
        oc.generate(MODEL, "k", "1024x1024", "low", 1, client=c, credentials=CREDS)


def test_indirme_basarisiz_olursa_TURKCE_hata():
    c = FakeClient(FakeResponse(200, {"data": [{"url": "https://cdn/x.png"}]}),
                   get_response=FakeResponse(404))

    with pytest.raises(ac.ImageError, match="indirilemedi"):
        oc.generate(DALLE, "k", "1024x1024", "standard", 1,
                    client=c, credentials=CREDS)


# ── edit ───────────────────────────────────────────────────────────────


def test_edit_multipart_alanlarini_AZURE_ILE_AYNI_kuruyor():
    """`ac.build_image_files` YENİDEN YAZILMIYOR, çağrılıyor.

    O fonksiyon canlı doğrulanmış bir tel detayı taşıyor (tek görselde `image`,
    çoklu görselde tekrarlanan `image[]`). Kopyalamak, iki yerde birden yanlış
    olabilecek bir detay üretirdi.
    """
    c = FakeClient(FakeResponse(200, {"data": [{"b64_json": _b64(b"E")}]}))

    out = oc.edit(MODEL, "k", [("a.png", b"AAA")], "1024x1024", "medium", 1,
                  client=c, credentials=CREDS)

    assert out == [b"E"]
    assert c.last_call["url"] == "https://api.openai.com/v1/images/edits"
    assert c.last_call["data"]["model"] == "gpt-image-1"
    # `n` multipart'ta DİZE olmak zorunda (ac.edit'in aynısı).
    assert c.last_call["data"]["n"] == "1"
    assert c.last_call["files"] == {"image": ("a.png", b"AAA", "image/png")}
    # Content-Type YOK: multipart sınırını istemci koyuyor.
    assert "Content-Type" not in c.last_call["headers"]


def test_edit_coklu_referansta_tekrarlanan_alan_kullaniyor():
    c = FakeClient(FakeResponse(200, {"data": [{"b64_json": _b64(b"E")}]}))

    oc.edit(MODEL, "k", [("a.png", b"A"), ("b.png", b"B")],
            "1024x1024", "medium", 1, client=c, credentials=CREDS)

    assert c.last_call["files"] == [("image[]", ("a.png", b"A", "image/png")),
                                   ("image[]", ("b.png", b"B", "image/png"))]


# ── Hata çevirisi ──────────────────────────────────────────────────────


@pytest.mark.parametrize("status,parca", [
    (401, "yetkilendirme"),
    (403, "erişimi olmayabilir"),
    (429, "limit"),
])
def test_hata_mesajlari_OPENAI_diyor_azure_DEMIYOR(status, parca):
    """"Azure yetkilendirme hatası" diyen bir metin OpenAI anahtarını
    kurcalayan kullanıcıyı yanlış forma yönlendirir."""
    mesaj = oc.map_error(status, {"error": {"message": "detay"}})

    assert parca in mesaj.lower()
    assert "OpenAI" in mesaj
    assert "Azure" not in mesaj


def test_icerik_politikasi_reddi_ayri_mesaj():
    mesaj = oc.map_error(400, {"error": {"message": "content policy violation"}})
    assert "İçerik politikası" in mesaj


def test_bilinmeyen_durum_detayi_TASIYOR():
    mesaj = oc.map_error(500, {"error": {"message": "iç hata"}})
    assert "500" in mesaj and "iç hata" in mesaj


def test_tasima_hatasi_ucret_uyarisini_KORUYOR(monkeypatch):
    """Zaman aşımı İSTEMCİNİN vazgeçmesidir: istek karşı tarafta tamamlanmış ve
    FATURALANMIŞ olabilir. `azure_client`'ın bu uyarısı sağlayıcı adı
    değiştirilirken kaybolmamalı — kredi sistemi geldiğinde daha da önemli."""
    import httpx

    class Patlayan:
        def post(self, *a, **k):
            raise httpx.ConnectTimeout("zaman aşımı")

    with pytest.raises(ac.ImageError) as exc:
        oc.generate(MODEL, "k", "1024x1024", "low", 1,
                    client=Patlayan(), credentials=CREDS)

    mesaj = str(exc.value)
    assert "ücretlendirilmiş olabilir" in mesaj
    assert "OpenAI" in mesaj and "Azure" not in mesaj


# ── Kayma mandalı ──────────────────────────────────────────────────────


def test_gövde_azure_ikizi_ile_AYRISMIYOR():
    """İki dosyanın bilinçli ikiz olmasının bedeli kayma riski.

    Paylaşılan anahtarlar (`prompt`, `size`, `quality`, `n`) aynı değerleri
    taşımalı; ayrılan tek anahtar `model` — orada Azure sabit bir ada, OpenAI
    katalogdaki `wire_model`'e bakıyor.

    Bu mandal düşerse yapılacak şey belli: ÜÇÜNCÜ bir ikiz varsa
    `openai_wire.py` çıkarılır (openai_client.py'nin başlığındaki not).
    """
    azure = ac.build_payload("kedi", "1024x1024", "medium", 2)
    openai = oc.build_payload("kedi", "1024x1024", "medium", 2,
                              api_model="gpt-image-1")

    assert set(azure) == set(openai), "alan KÜMESİ ayrışmış"
    for anahtar in set(azure) - {"model"}:
        assert azure[anahtar] == openai[anahtar], anahtar
    assert azure["model"] == ac.MODEL_NAME
    assert openai["model"] == "gpt-image-1"
