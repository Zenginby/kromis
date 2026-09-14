"""fal_client: gövde kurma, uç seçimi ve alan tablosu.

Bu dosyanın en değerli iddiası ALAN TABLOSU. 2026-09-14'te canlı uçtan
ÖLÇÜLDÜ ki beyan edilmemiş bir alan 422 ÜRETMİYOR, SESSİZCE YOK SAYILIYOR —
Kling'in görsel→video ucu, şemasında hiç olmayan `aspect_ratio` ile şema
doğrulamasını geçti. Bu tabloyu gereksiz değil DAHA GEREKLİ kılıyor: 422
kendini gösterir, sessiz yok sayım göstermez. Kullanıcı 9:16 seçer, tel kabul
eder, video 16:9 döner ve hiçbir yerde hata okunmaz.

Model örnekleri BURADA kuruluyor, `catalog`tan okunmuyor: gövde kurucusu
katalog girdilerinden ÖNCE sınanabilir olmalı.
"""
import base64

import pytest

import catalog
import fal_client


def _model(model_id, wire, wire_edit):
    return catalog.ImageModel(
        id=model_id, label=model_id, provider="fal",
        wire_model=wire, wire_model_edit=wire_edit, credential="fal",
        sizes=("16:9", "9:16", "1:1"), qualities=("720p",), max_n=1,
        credits=16, durations=(5, 10), kind="video", supports_edit=True)


WAN = _model("fal-wan-3-0",
             "alibaba/wan-3.0/text-to-video",
             "alibaba/wan-3.0/image-to-video")
KLING = _model("fal-kling-v3-turbo-pro",
               "fal-ai/kling-video/v3/turbo/pro/text-to-video",
               "fal-ai/kling-video/v3/turbo/pro/image-to-video")

PNG = b"\x89PNG\r\n\x1a\n"
REFS = [("ilk.png", PNG)]


def test_the_edit_path_uses_the_SECOND_wire_endpoint():
    assert fal_client.wire_path_for(WAN, images=None) == WAN.wire_model
    assert fal_client.wire_path_for(WAN, images=REFS) == WAN.wire_model_edit


def test_wan_text_to_video_sends_aspect_ratio_and_resolution():
    p = fal_client.build_payload(WAN, "kedi", "16:9", "720p", 5, None)
    assert p == {"prompt": "kedi", "aspect_ratio": "16:9",
                 "resolution": "720p", "duration": 5}


def test_kling_IMAGE_to_video_sends_NEITHER_aspect_ratio_NOR_resolution():
    """Kling'in i2v şemasında o iki alan HİÇ yok.

    Göndermek 422 DEĞİL, SESSİZ SAPMA üretir (ölçüldü 2026-09-14): tel alanı
    kabul eder, kullanır mı belli değil, kullanıcı seçtiği oranı aldığını
    SANIR. Testin ölçtüğü şey gövdenin kendisi, telin cevabı değil — zaten
    bu yüzden ölçülebilir.
    """
    p = fal_client.build_payload(KLING, "kedi", "16:9", "1080p", 5, REFS)
    assert "aspect_ratio" not in p
    assert "resolution" not in p
    assert p["prompt"] == "kedi"
    assert p["duration"] == 5


def test_the_reference_image_travels_as_a_base64_data_uri():
    """Yükleme adımı YOK — `gemini_client`in inlineData duruşunun aynısı."""
    p = fal_client.build_payload(WAN, "kedi", "16:9", "720p", 5, REFS)
    onek = "data:image/png;base64,"
    assert p["image_url"].startswith(onek)
    assert base64.b64decode(p["image_url"][len(onek):]) == PNG


def test_only_the_FIRST_reference_is_sent():
    """`max_refs=1`; fazlası app.animate'in kapısında zaten eleniyor."""
    p = fal_client.build_payload(WAN, "kedi", "16:9", "720p", 5,
                                 [("bir.png", PNG), ("iki.png", b"XX")])
    assert base64.b64decode(p["image_url"].split(",", 1)[1]) == PNG


def test_every_field_table_entry_declares_prompt_and_only_i2v_takes_image_url():
    """Tablo ile katalog ayrışırsa gövde SESSİZCE boşalır — mandal bu."""
    for model_id, (t2v, i2v) in fal_client.ALANLAR.items():
        assert "prompt" in t2v and "prompt" in i2v, model_id
        assert "image_url" in i2v and "image_url" not in t2v, model_id


@pytest.mark.parametrize("tam_yol, uygulama", [
    ("alibaba/wan-3.0/text-to-video", "alibaba/wan-3.0"),
    ("alibaba/wan-3.0/image-to-video", "alibaba/wan-3.0"),
    ("fal-ai/pixverse/c1/text-to-video", "fal-ai/pixverse"),
    ("fal-ai/kling-video/v3/turbo/pro/text-to-video", "fal-ai/kling-video"),
    ("fal-ai/kling-video/v3/turbo/pro/image-to-video", "fal-ai/kling-video"),
])
def test_the_queue_path_keeps_only_the_owner_and_app_segments(tam_yol, uygulama):
    """ÖLÇÜLMÜŞ olgu (2026-09-14): yoklama adresi gönderim adresi DEĞİL.

    Tam yolla kurulan adres 404 değil BOŞ GÖVDE döndürüyor — yani döngü
    sessizce ölüyor ve üretim duvar saatine kadar bekliyor. Bu test o sessiz
    kusurun mandalı.
    """
    assert fal_client.queue_app_path(tam_yol) == uygulama
