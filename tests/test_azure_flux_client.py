"""azure_flux_client: BFL telinin şekli, model-path eşlemesi ve 422 çevirisi.

Bu dosyanın en değerli üç iddiası:

  1. YOL DAĞITIM ADI DEĞİL. `FLUX.2-pro` gövdedeki `model` alanına gidiyor,
     yola ise `flux-2-pro` giriyor. İkisini karıştırmak 404 demek ve hata
     "model bulunamadı" derken kullanıcıyı anahtarını kurcalamaya iter.
  2. 422 MESAJ DEĞİL LİSTE taşıyor (`error.details[]`). Liste okunmazsa
     bütün 422'ler çıplak bir "HTTP 422"ya çöküyor.
  3. GÖVDEDE `steps`/`guidance` HİÇ YOK. Bu iki alan flex'in ekseniydi;
     flex 2026-09-22'de silindi (karar 1b-D — Azure adım sayısına değil
     megapiksele bakıyor, üç kademe de aynı parayı ödetiyordu). Geriye kalan
     pro'nun `quality` parametresi yok ve beyan edilmemiş bir alan göndermek
     "gönderdim, demek ki uygulandı" varsayımını doğururdu.

CANLI DOĞRULAMANIN SINIRI: FLUX'un 200 yanıtı bu depodan GÖRÜLMEDİ (şekil
Microsoft'un örnek deposundan). O yüzden `decode_images`ın sarmalama iddiası
bu dosyada en yüksek değerli test — şekil değişirse kullanıcı Türkçe bir
hata görmeli, ham 500 değil.
"""
import base64
import inspect

import pytest

import azure_client as ac
import azure_flux_client as flux
import catalog
import providers

PRO = catalog.image_model("azure-flux-2-pro")
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
    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json,
                           "timeout": timeout})
        return (self._responses[len(self.calls) - 1]
                if len(self._responses) > 1 else self._responses[0])


def _ok(sayi=1):
    b64 = base64.b64encode(b"\x89PNG").decode()
    return FakeResponse(200, {"data": [{"b64_json": b64}] * sayi})


# ── Yol eşlemesi ───────────────────────────────────────────────────────


def test_the_path_segment_is_NOT_the_deployment_name():
    """Tablo flex silindikten sonra TEK satır; eşleme yine de türetilmiyor.

    `FLUX.2-pro` gövdedeki `model` alanına, `flux-2-pro` yola gidiyor —
    noktayı tireye çeviren bir dönüşüm gibi görünüyor ama tablo elle tutuluyor
    ve bu bilinçli (gerekçe `_MODEL_PATHS`in yorumunda). Silinen ad artık
    tabloda YOK ve bunu ayrıca sınıyoruz: yol kalsaydı ölü kod olurdu.
    """
    assert flux.model_path("FLUX.2-pro") == "flux-2-pro"
    with pytest.raises(ac.ImageError):
        flux.model_path("FLUX.2-flex")


def test_an_UNMAPPED_wire_name_raises_a_TURKISH_error_not_a_KeyError():
    with pytest.raises(ac.ImageError) as exc:
        flux.model_path("FLUX.9-imaginary")
    assert "_MODEL_PATHS" in str(exc.value)


def test_EVERY_catalog_flux_entry_has_a_path():
    """Katalog ile tablo ayrışırsa model seçilebilir olur ve üretim 404 alır."""
    for m in catalog.IMAGE_MODELS:
        if m.provider == "azure-flux":
            assert flux.model_path(m.wire_model)


def test_the_endpoint_carries_the_api_version_query():
    assert flux.endpoint_for("https://ai-ornek.services.ai.azure.com/", "FLUX.2-pro") == (
        "https://ai-ornek.services.ai.azure.com/providers/blackforestlabs/v1/"
        "flux-2-pro?api-version=preview")


# ── Gövdenin şekli ─────────────────────────────────────────────────────


def test_the_payload_carries_width_height_and_num_images():
    govde = flux.build_payload("kedi", "1024x1536",
                               api_model="FLUX.2-pro")
    assert govde == {"model": "FLUX.2-pro", "prompt": "kedi",
                     "width": 1024, "height": 1536, "num_images": 1}


def test_PRO_never_sends_steps_or_guidance():
    """pro'nun `quality` parametresi YOK; beyan edilmemiş bir alan göndermek
    "gönderdim, demek ki uygulandı" varsayımını doğurur."""
    govde = flux.build_payload("kedi", "1024x1024",
                               api_model="FLUX.2-pro")
    assert "steps" not in govde and "guidance" not in govde


def test_the_adapter_signature_matches_its_MAI_sibling_now_that_the_axis_is_gone():
    """`quality` gövdeye HİÇ ulaşmıyor — `azure_mai_client`ın duruşu benimsendi.

    Parametre `generate`/`edit`te KALIYOR (sağlayıcı sözleşmesi: `providers`
    dört adaptörü aynı imzayla çağırıyor), ama `_uret` ve `build_payload`
    onu artık almıyor. Yarısını yapmak — imzada tutup gövdeye taşımak —
    Azure'ın tanımadığı bir alan göndermek olurdu.
    """
    assert "quality" not in inspect.signature(flux.build_payload).parameters
    assert "quality" not in inspect.signature(flux._uret).parameters
    for ad in ("generate", "edit"):
        assert "quality" in inspect.signature(getattr(flux, ad)).parameters, ad


# ── Referans görseller ─────────────────────────────────────────────────


def test_the_reference_images_are_numbered_from_TWO():
    """İlk alanın adı sonek TAŞIMIYOR ve bu telin kendi kuralı."""
    gorseller = [("a.png", b"AAA"), ("b.png", b"BBB"), ("c.png", b"CCC")]
    govde = flux.build_payload("p", "1024x1024",
                               api_model="FLUX.2-pro", images=gorseller)

    assert govde["input_image"] == base64.b64encode(b"AAA").decode()
    assert govde["input_image_2"] == base64.b64encode(b"BBB").decode()
    assert govde["input_image_3"] == base64.b64encode(b"CCC").decode()
    assert "input_image_1" not in govde


def test_generation_carries_NO_input_image_field():
    govde = flux.build_payload("p", "1024x1024",
                               api_model="FLUX.2-pro")
    assert not [k for k in govde if k.startswith("input_image")]


def test_edit_and_generate_hit_the_SAME_endpoint():
    """FLUX'ta düzenleme ayrı bir uç DEĞİL; iki fonksiyonu ayrı yazmak aynı
    döngüyü iki yerde bakıma sokardı."""
    c1, c2 = FakeClient(_ok()), FakeClient(_ok())
    flux.generate(PRO, "p", "1024x1024", "standard", 1,
                  client=c1, credentials=CREDS)
    flux.edit(PRO, "p", [("a.png", b"AAA")], "1024x1024", "standard", 1,
              client=c2, credentials=CREDS)

    assert c1.calls[0]["url"] == c2.calls[0]["url"]
    assert c2.calls[0]["json"]["input_image"]


# ── İstek ve zaman aşımı ───────────────────────────────────────────────


def test_generate_sends_the_api_key_header_and_decodes():
    client = FakeClient(_ok())
    out = flux.generate(PRO, "kedi", "1024x1024", "standard", 1,
                        client=client, credentials=CREDS)

    assert out == [b"\x89PNG"]
    cagri = client.calls[0]
    assert cagri["headers"][flux.AUTH_HEADER] == "FOUNDRYKEY"
    assert cagri["timeout"].read == providers.read_timeout_for(PRO, 1)
    assert cagri["timeout"].read == ac.READ_TIMEOUT_FIRST


def test_the_identity_is_resolved_LAZILY_when_credentials_are_given(monkeypatch):
    def patlat(*a, **k):
        raise AssertionError("credentials verilmişken credstore çağrılmamalı")

    monkeypatch.setattr("credstore.resolve", patlat)
    assert flux.generate(PRO, "kedi", "1024x1024", "standard", 1,
                         client=FakeClient(_ok()), credentials=CREDS) == [b"\x89PNG"]


# ── Yanıt ve hata ──────────────────────────────────────────────────────


@pytest.mark.parametrize("govde", [
    {},
    {"data": []},
    {"data": [{}]},
    {"data": {"b64_json": "x"}},
])
def test_an_UNEXPECTED_200_becomes_a_TURKISH_error_not_a_KeyError(govde):
    """Spec'in 1. riskinin azaltması: FLUX'un 200'ü bu depodan görülmedi."""
    with pytest.raises(ac.ImageError):
        flux.decode_images(govde)


def test_the_422_details_list_reaches_the_user_as_ONE_turkish_sentence():
    """Liste okunmazsa bütün 422'ler çıplak bir "HTTP 422"ya çöküyor."""
    client = FakeClient(FakeResponse(422, {"error": {"details": [
        {"loc": ["body", "width"], "msg": "must be a multiple of 32"},
        {"loc": ["body", "steps"], "msg": "must be <= 50"},
    ]}}))

    with pytest.raises(ac.ImageError) as exc:
        flux.generate(PRO, "kedi", "1024x1024", "standard", 1,
                      client=client, credentials=CREDS)

    mesaj = str(exc.value)
    assert "422" in mesaj
    assert "body.width: must be a multiple of 32" in mesaj
    assert "body.steps: must be <= 50" in mesaj


def test_a_422_with_an_EMPTY_details_list_still_says_something_useful():
    mesaj = flux.map_error(422, {"error": {"details": []}})
    assert "geçersiz" in mesaj


def test_the_429_message_tells_the_user_to_WAIT():
    """FLUX dağıtımlarının kapasitesi düşük (flex belgelenmiş RPM'de 5/dk) ve
    sonda sırasında `RateLimitReached` gerçekten görüldü."""
    assert "bekleyip" in flux.map_error(429, None)


def test_map_error_has_NO_content_policy_branch():
    """FLUX'ta yerleşik içerik filtresi YOK (Microsoft'un kendi uyarısı).

    İçerik reddi gibi görünen bir metin gelse bile o dal bilerek yok: boş bir
    dal ileride "neden hiç çalışmıyor" diye aranan bir şey olurdu.
    """
    mesaj = flux.map_error(400, {"error": {"message": "content policy"}})
    assert "İçerik politikası" not in mesaj
    assert "HTTP 400" in mesaj


def test_a_TIMEOUT_becomes_a_TURKISH_error_that_names_FOUNDRY():
    import httpx

    class RaisingClient:
        def post(self, url, **kwargs):
            raise httpx.ReadTimeout("boom")

    with pytest.raises(ac.ImageError) as exc:
        flux.generate(PRO, "kedi", "1024x1024", "standard", 1,
                      client=RaisingClient(), credentials=CREDS)

    mesaj = str(exc.value)
    assert "Foundry" in mesaj and "Azure" not in mesaj
