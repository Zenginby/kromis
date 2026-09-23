"""fal_client GÖRSEL yolu (Faz 4 / 1b-D, 2026-09-23): gövde kurma, uç seçimi, alan tablosu, PNG garantisi.

Video ikizinin (tests/test_fal_client.py) duruşu aynen: ölçülen şey GÖVDENİN
KENDİSİ ve döngünün mekaniği, telin cevabı değil. Üç görsel modelinin şeması
fal.ai'den okunamadı (egress) — açık kaynak istemcilerden çapraz okundu
(fal_client.py başlığı) — yani "fal bu gövdeyi kabul eder" iddiası burada
YOK; buradaki iddia "kod tabloya sadık, tablo katalogla aynı, sonuç PNG".
Canlı doğrulama sahibin sandbox turu.

Model örnekleri KATALOGDAN okunuyor (video testleri kendi örneğini kuruyor):
görselde `sizes` ve `max_refs` gövdeye giriyor (`image_size`, liste kesmesi),
sentetik bir örnek o iki alanın katalogla ayrışmasını göremezdi.
"""
import base64
import io

import pytest

import azure_client as ac
import catalog
import fal_client
import providers
from tests.test_fal_client import CREDS, FakeClient, FakeResponse

QWEN = catalog.image_model("fal-qwen-image")
SEEDREAM = catalog.image_model("fal-seedream-v4")
SCHNELL = catalog.image_model("fal-flux-1-schnell")
assert QWEN and SEEDREAM and SCHNELL

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
REFS = [("ilk.png", PNG), ("iki.png", b"\x89PNG\r\n\x1a\nB"), ("uc.png", b"\x89PNG\r\n\x1a\nC"),
        ("dort.png", b"\x89PNG\r\n\x1a\nD"), ("bes.png", b"\x89PNG\r\n\x1a\nE")]


def _jpeg() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _saati_durdur(monkeypatch):
    monkeypatch.setattr(fal_client, "_bekle", lambda s: None)


# ── Tablo ↔ katalog ────────────────────────────────────────────────────────


def test_the_image_field_table_covers_exactly_the_fal_image_models_in_the_catalog():
    """Video tablosunun aynı mandalı: ayrışma `build_image_payload`da KeyError = anında 500."""
    katalog = {m.id for m in catalog.IMAGE_MODELS if m.provider == "fal"}
    assert katalog == set(fal_client.GORSEL_ALANLAR), katalog ^ set(fal_client.GORSEL_ALANLAR)


def test_supports_edit_in_the_catalog_matches_the_presence_of_an_edit_endpoint_in_the_table():
    """Katalog "düzenler" derken tablo "ucu yok" dese (ya da tersi) kullanıcı ya
    seçilebilir bir hata ya da gizli bir yetenek görürdü."""
    for m in catalog.IMAGE_MODELS:
        if m.provider != "fal":
            continue
        bicim = fal_client.GORSEL_ALANLAR[m.id]
        assert m.supports_edit == (bicim.duzenleme is not None), m.id
        assert bool(m.wire_model_edit) == (bicim.duzenleme is not None), m.id


def test_the_table_invariants_are_enforced_at_import_time():
    with pytest.raises(ValueError):
        fal_client.GorselTelBicimi(metin=frozenset({"prompt"}),
                                   duzenleme=frozenset({"prompt"}), gorsel_alani="image_url")
    with pytest.raises(ValueError):
        fal_client.GorselTelBicimi(metin=frozenset({"prompt"}), duzenleme=None,
                                   gorsel_alani="image_url")


# ── Gövde ─────────────────────────────────────────────────────────────────


def test_qwen_text_to_image_sends_image_size_as_a_width_height_object_and_asks_for_png():
    p = fal_client.build_image_payload(QWEN, "kedi", "1664x928", 3, None)
    assert p == {"prompt": "kedi", "image_size": {"width": 1664, "height": 928},
                 "num_images": 1, "output_format": "png"}


def test_num_images_is_ALWAYS_one_because_the_count_loop_lives_in_the_queue_loop():
    """`n` gövdeye girmiyor: fal'ın `num_images` tavanı modele göre değişiyor ve
    ölçülmedi; adet başına ayrı istek her tavanın altında (`images_per_request=1`)."""
    for m in (QWEN, SEEDREAM, SCHNELL):
        assert fal_client.build_image_payload(m, "kedi", m.sizes[0], 4, None)["num_images"] == 1
        assert m.images_per_request == 1


def test_qwen_edit_sends_a_SINGLE_image_url_and_no_image_size():
    """`fal-ai/qwen-image-edit` tek `image_url` okuyor (2509/plus varyantları liste alır,
    listede değiller); `image_size` o uca gönderilmiyor — şemada üç kaynakla görülmedi."""
    p = fal_client.build_image_payload(QWEN, "kedi", "1328x1328", 1, REFS)
    assert set(p) == {"prompt", "image_url", "num_images", "output_format"}
    onek = "data:image/png;base64,"
    assert p["image_url"].startswith(onek)
    assert base64.b64decode(p["image_url"][len(onek):]) == PNG


def test_seedream_edit_sends_an_image_urls_LIST_capped_at_max_refs_and_keeps_image_size():
    p = fal_client.build_image_payload(SEEDREAM, "kedi", "1024x1536", 1, REFS)
    assert set(p) == {"prompt", "image_urls", "image_size", "num_images"}
    assert isinstance(p["image_urls"], list) and len(p["image_urls"]) == SEEDREAM.max_refs == 4
    assert base64.b64decode(p["image_urls"][0].split(",", 1)[1]) == PNG
    assert p["image_size"] == {"width": 1024, "height": 1536}


def test_seedream_does_NOT_ask_for_an_output_format_the_schema_was_not_seen_to_declare():
    """Beyan edilmemiş alan fal'da 422 değil SESSİZ yok sayım (video turunun ölçümü);
    PNG garantisi bu modelde yerelde (`_png_garantile`)."""
    p = fal_client.build_image_payload(SEEDREAM, "kedi", "1024x1024", 1, None)
    assert "output_format" not in p


def test_schnell_has_no_edit_endpoint_and_the_adapter_says_so_before_touching_the_network():
    """İkinci kapı: `providers.edit` katalogdan zaten reddediyor; adaptör kendi
    başına çağrılsa da referansı metin ucuna DÜŞÜRMÜYOR."""
    with pytest.raises(ac.ImageError) as exc:
        fal_client.build_image_payload(SCHNELL, "kedi", "960x960", 1, REFS[:1])
    assert "referans" in str(exc.value).lower()
    client = FakeClient()
    with pytest.raises(ac.ImageError):
        fal_client.edit(SCHNELL, "kedi", REFS[:1], "960x960", "standard", 1,
                        client=client, credentials=CREDS)
    assert client.calls == []
    with pytest.raises(ac.ImageError) as exc2:
        providers.edit("fal-flux-1-schnell", "kedi", REFS[:1], "960x960", "standard", 1)
    assert "referans görselle çalışmıyor" in str(exc2.value)


@pytest.mark.parametrize("m", [QWEN, SEEDREAM, SCHNELL], ids=lambda m: m.id)
def test_every_catalog_size_token_of_the_model_splits_into_the_declared_geometry(m):
    for jeton in m.sizes:
        w, h = fal_client._boyut(jeton)
        assert f"{w}x{h}" == jeton


# ── Döngü ve PNG garantisi ────────────────────────────────────────────────


def _gorsel_yanitlari(govde: bytes, rid="img123", url="https://v3.fal.media/x.png"):
    return [
        FakeResponse(200, {"request_id": rid}),
        FakeResponse(200, {"status": "IN_PROGRESS"}),
        FakeResponse(200, {"status": "COMPLETED"}),
        FakeResponse(200, {"images": [{"url": url, "content_type": "image/png",
                                       "width": 960, "height": 960}], "seed": 7}),
        FakeResponse(200, content=govde),
    ]


def test_the_happy_path_submits_to_the_image_endpoint_polls_the_app_root_and_returns_the_png():
    client = FakeClient(*_gorsel_yanitlari(PNG))
    out = fal_client.generate(SCHNELL, "kedi", "960x960", "standard", 1,
                              client=client, credentials=CREDS)
    assert out == [PNG]
    adresler = [c["url"] for c in client.calls]
    assert adresler[0] == "https://queue.fal.run/fal-ai/flux/schnell"
    # Yoklama yolu ilk iki segment (`fal-ai/flux`) — videonun ölçülmüş kuralı.
    assert adresler[1] == "https://queue.fal.run/fal-ai/flux/requests/img123/status"
    assert adresler[3] == "https://queue.fal.run/fal-ai/flux/requests/img123"
    assert client.calls[0]["json"]["image_size"] == {"width": 960, "height": 960}
    assert client.calls[0]["headers"]["Authorization"] == "Key FALKEY"
    assert "Authorization" not in client.calls[-1]["headers"], "indirme anahtarsız"


def test_the_edit_path_goes_to_the_edit_endpoint():
    client = FakeClient(*_gorsel_yanitlari(PNG))
    fal_client.edit(SEEDREAM, "kedi", REFS[:1], "1024x1024", "standard", 1,
                    client=client, credentials=CREDS)
    assert client.calls[0]["url"] == "https://queue.fal.run/fal-ai/bytedance/seedream/v4/edit"
    assert client.calls[0]["json"]["image_urls"]


def test_a_non_png_download_is_re_encoded_as_png_so_the_contract_holds():
    """Seedream `output_format` almıyor ve JPEG dönebiliyor; sözleşme PNG istiyor
    (`storage.save` `.png` yazar). Bayt yerelde çevriliyor, sessizce `.png`
    adıyla JPEG yazılmıyor."""
    client = FakeClient(*_gorsel_yanitlari(_jpeg()))
    out = fal_client.generate(SEEDREAM, "kedi", "1024x1024", "standard", 1,
                              client=client, credentials=CREDS)
    assert out[0].startswith(b"\x89PNG\r\n\x1a\n")
    from PIL import Image
    with Image.open(io.BytesIO(out[0])) as im:
        assert im.size == (8, 8)


def test_a_png_download_passes_through_UNCHANGED():
    assert fal_client._png_garantile(PNG) is PNG


def test_bytes_that_are_not_an_image_become_a_TURKISH_error_not_an_UnidentifiedImageError():
    client = FakeClient(*_gorsel_yanitlari(b"<html>not an image</html>"))
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(SEEDREAM, "kedi", "1024x1024", "standard", 1,
                            client=client, credentials=CREDS)
    assert "fal" in str(exc.value).lower() and "görsel" in str(exc.value).lower()


def test_COMPLETED_without_images_is_a_TURKISH_error_naming_the_missing_key():
    client = FakeClient(
        FakeResponse(200, {"request_id": "img123"}),
        FakeResponse(200, {"status": "COMPLETED"}),
        FakeResponse(200, {"seed": 7}),
    )
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(QWEN, "kedi", "1328x1328", "standard", 1,
                            client=client, credentials=CREDS)
    assert "images[0].url" in str(exc.value)


def test_a_failed_job_is_rejected_with_the_IMAGE_wording_not_the_video_one():
    client = FakeClient(
        FakeResponse(200, {"request_id": "img123"}),
        FakeResponse(200, {"status": "COMPLETED"}),
        FakeResponse(200, {"error": {"message": "iş düştü"},
                           "images": [{"url": "https://v3.fal.media/x.png"}]}),
    )
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(QWEN, "kedi", "1328x1328", "standard", 1,
                            client=client, credentials=CREDS)
    assert "görsel üretmedi" in str(exc.value) and "düştü" in str(exc.value)


def test_n_images_mean_n_queue_tours_each_with_num_images_one():
    yanitlar = _gorsel_yanitlari(PNG)
    client = FakeClient(*(yanitlar + yanitlar))
    out = fal_client.generate(SCHNELL, "kedi", "960x960", "standard", 2,
                              client=client, credentials=CREDS)
    assert out == [PNG, PNG]
    submitler = [c for c in client.calls if c["method"] == "POST"]
    assert len(submitler) == 2 and all(c["json"]["num_images"] == 1 for c in submitler)


def test_the_ssrf_gate_guards_the_image_download_too():
    """Kapı paylaşılan döngüde (`_kuyruk_dongusu`): videoda sıkılan şey görselde gevşemez."""
    yanitlar = _gorsel_yanitlari(PNG, url="http://127.0.0.1:9/x.png")[:-1]
    client = FakeClient(*yanitlar)
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(SCHNELL, "kedi", "960x960", "standard", 1,
                            client=client, credentials=CREDS)
    assert "ssrf" in str(exc.value).lower()
    assert len(client.calls) == 4


def test_the_dispatcher_routes_fal_image_models_to_fal_client_and_video_models_to_generate_video():
    """`providers` iki tabloda farklı çift çekiyor: görsel `(generate, edit)`, video
    `(generate_video, animate)`. Biri ötekine karışsa görsel isteği `duration` ister."""
    assert providers._pair("fal") == (fal_client.generate, fal_client.edit)
    assert providers._video_pair("fal") == (fal_client.generate_video, fal_client.animate)
