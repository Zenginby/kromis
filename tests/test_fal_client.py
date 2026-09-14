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

import azure_client as ac
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


# ── Hata çevirisi ──────────────────────────────────────────────────────


def test_top_level_detail_list_is_read_like_fluxs_error_details():
    """fal FastAPI tabanlı: doğrulama hatası ÜST DÜZEY `detail` listesi.

    `providers.detail_of` `error.details[]` okuyor, üst düzey `detail`i
    DEĞİL — ve o fonksiyona dokunmak Azure/OpenAI/Gemini/FLUX yolunun
    baytlarını değiştirirdi. Sarmal bu yüzden burada.
    """
    govde = {"detail": [{"loc": ["body", "duration"],
                         "msg": "value is not a valid enumeration member"}]}
    assert "duration" in fal_client.detail_of(govde)


def test_a_plain_error_string_still_resolves():
    """Kuyruk `COMPLETED` iken hatayı düz bir dize olarak taşıyabiliyor."""
    assert fal_client.detail_of({"error": "boom"}) == "boom"


def test_401_names_the_fal_key_and_not_a_generic_key():
    mesaj = fal_client.map_error(401, {"detail": "Unauthorized"})
    assert "fal" in mesaj.lower()
    assert "401" in mesaj


def test_402_talks_about_BALANCE_and_never_about_the_key():
    """fal ÖN ÖDEMELİ. 'Anahtarını kontrol et' demek, anahtarı doğru olan
    kullanıcıyı çalışan kurulumunu bozmaya davet etmek olurdu —
    `veo_client`in 403/429 dalının birebir gerekçesi."""
    mesaj = fal_client.map_error(402, {"detail": "insufficient balance"})
    assert "bakiye" in mesaj.lower()
    assert "anahtar" not in mesaj.lower()


def test_429_talks_about_CONCURRENCY_and_not_about_the_key():
    mesaj = fal_client.map_error(429, None)
    assert "eşzamanlı" in mesaj.lower()
    assert "anahtar" not in mesaj.lower()


def test_content_refusal_is_recognised_through_the_shared_predicate():
    mesaj = fal_client.map_error(400, {"detail": "flagged by safety checker"})
    assert "içerik" in mesaj.lower()


def test_an_unknown_status_still_carries_the_detail():
    mesaj = fal_client.map_error(503, {"detail": "upstream down"})
    assert "503" in mesaj and "upstream down" in mesaj


def test_422_carries_the_top_level_detail_through_map_error():
    """Görev 5'in incelemesinden taşınan boşluk: 422 dalı `detail_of`
    üzerinden sınanmıştı ama `map_error` ÜZERİNDEN hiç — yani iki yeni
    işlevin arasındaki bağ ölçülmemişti."""
    mesaj = fal_client.map_error(422, {"detail": [
        {"loc": ["body", "duration"], "msg": "value is not a valid enumeration member"}]})
    assert "422" in mesaj
    assert "duration" in mesaj


# ── Kuyruk döngüsü ─────────────────────────────────────────────────────

CREDS = ("FALKEY", "https://queue.fal.run")
MP4 = b"\x00\x00\x00\x18ftypmp42"


class FakeResponse:
    def __init__(self, status_code, json_body=None, content=b"", headers=None):
        self.status_code = status_code
        self._json = json_body
        self.content = content
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("gövde JSON değil")
        return self._json


class FakeClient:
    """Sözleşmenin `client=` anahtarının açtığı dikiş."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append({"method": method, "url": url, "headers": headers or {},
                           "json": json, "timeout": timeout})
        return self._responses[min(len(self.calls) - 1,
                                   len(self._responses) - 1)]

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _saati_durdur(monkeypatch):
    """Uykuyu kaldırıyor; `_simdi`/`_bekle` dikişleri `veo_client`in deseni."""
    monkeypatch.setattr(fal_client, "_bekle", lambda s: None)


def _kuyruk_yanitlari(rid="abc123"):
    return [
        FakeResponse(200, {"request_id": rid,
                           # DÜŞMANCA adresler: ürün kodu bunları OKUMAMALI.
                           "status_url": "https://evil.example/status",
                           "response_url": "https://evil.example/response"}),
        FakeResponse(200, {"status": "IN_QUEUE", "queue_position": 2}),
        FakeResponse(200, {"status": "COMPLETED"}),
        FakeResponse(200, {"video": {"url": "https://v3.fal.media/x.mp4",
                                     "content_type": "video/mp4"}}),
        FakeResponse(200, content=MP4),
    ]


def test_the_happy_path_returns_the_downloaded_mp4_bytes():
    client = FakeClient(*_kuyruk_yanitlari())
    out = fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                              client=client, credentials=CREDS)
    assert out == [MP4]


def test_the_poll_and_result_urls_are_REBUILT_from_the_trusted_base():
    """Gövdedeki `status_url`/`response_url` OKUNMUYOR.

    `veo_client._indir`in ölçülmüş kararının aynısı: gövdeyi yazan taraf
    bizim GET'imizin hedefini seçememeli. fal'ın belgesi tersini öneriyor ve
    bu sapma bilinçli — bkz. fal_client başlığı.
    """
    client = FakeClient(*_kuyruk_yanitlari())
    fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                        client=client, credentials=CREDS)
    adresler = [c["url"] for c in client.calls]
    assert not any("evil.example" in u for u in adresler)
    # GÖNDERİM yolu tam (`…/text-to-video`), YOKLAMA yolu yalnız ilk iki
    # segment — ölçülmüş fark (bkz. `queue_app_path`).
    assert adresler[0] == (
        "https://queue.fal.run/alibaba/wan-3.0/text-to-video")
    assert adresler[1] == (
        "https://queue.fal.run/alibaba/wan-3.0/requests/abc123/status")
    assert adresler[3] == (
        "https://queue.fal.run/alibaba/wan-3.0/requests/abc123")


def test_the_download_step_carries_NO_credentials():
    """Çıktı adresi gövdeden geliyor; anahtar oraya GİTMEMELİ."""
    client = FakeClient(*_kuyruk_yanitlari())
    fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                        client=client, credentials=CREDS)
    indirme = client.calls[-1]
    assert indirme["url"] == "https://v3.fal.media/x.mp4"
    assert "Authorization" not in indirme["headers"]


def test_the_submit_step_uses_the_Key_prefixed_authorization_header():
    client = FakeClient(*_kuyruk_yanitlari())
    fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                        client=client, credentials=CREDS)
    assert client.calls[0]["headers"]["Authorization"] == "Key FALKEY"


def test_a_missing_request_id_fails_with_a_TURKISH_error():
    """`"fal" in mesaj` TEK BAŞINA neredeyse boş bir iddiaydı: modüldeki HER
    mesaj zaten "fal.ai" ile başlıyor. Asıl iddia mesajın HANGİ alanın
    eksik olduğunu (`request_id`) da adıyla söylemesi."""
    client = FakeClient(FakeResponse(200, {"queue_position": 0}))
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "fal" in str(exc.value).lower()
    assert "request_id" in str(exc.value)


def test_a_hostile_request_id_is_REJECTED_before_any_url_is_built():
    """Yola segment enjekte etmeyi deneyen bir id kabul edilmemeli.

    Yalnız `pytest.raises` mandal DEĞİL: süzgeç kaldırılsa döngü gerçek
    duvar saati bütçesini doldurup yine `ac.ImageError` atardı (yalnız
    dakikalarca sürerek) — test yine geçerdi. Asıl iddia submit'ten SONRA
    HİÇBİR yeni adresin kurulup çağrılmadığı."""
    client = FakeClient(FakeResponse(200, {"request_id": "../../../admin"}))
    with pytest.raises(ac.ImageError):
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert len(client.calls) == 1


def test_COMPLETED_without_a_video_is_a_TURKISH_error_not_a_KeyError():
    """`azure_flux_client.decode_images`in kararı: sarmalanmayan bir KeyError
    app.py'nin süzgecinden geçer ve kullanıcı dakikalarca bekledikten sonra
    yalnızca 'Hata (500)' görür."""
    client = FakeClient(
        FakeResponse(200, {"request_id": "abc123"}),
        FakeResponse(200, {"status": "COMPLETED"}),
        FakeResponse(200, {"seed": 7}),
    )
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "video" in str(exc.value).lower()


def test_a_failed_job_is_rejected_even_if_the_body_also_carries_a_video():
    """`COMPLETED` başarı demek değil: `veo_client._operation_hatasi`nin
    KOŞULSUZ kararının aynısı — düşmüş bir işin bayat/kısmi videosu, gövdede
    görünse bile teslim edilmemeli. Önceki tur bunu `and not video` ile
    yumuşatıyordu; bu test tam o dalı mandallıyor."""
    client = FakeClient(
        FakeResponse(200, {"request_id": "abc123"}),
        FakeResponse(200, {"status": "COMPLETED"}),
        FakeResponse(200, {"error": {"message": "iş düştü"},
                           "video": {"url": "https://v3.fal.media/x.mp4"}}),
    )
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "düştü" in str(exc.value)


def test_the_wall_clock_budget_ends_the_loop_with_its_own_message(monkeypatch):
    saat = iter([0.0] + [10_000.0] * 50)
    monkeypatch.setattr(fal_client, "_simdi", lambda: next(saat))
    client = FakeClient(
        FakeResponse(200, {"request_id": "abc123"}),
        FakeResponse(200, {"status": "IN_PROGRESS"}),
    )
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "bitmedi" in str(exc.value).lower()


def test_the_wall_clock_budget_is_shared_across_ALL_tours_not_reset_per_tour(
        monkeypatch):
    """`providers.total_budget` `n` ile ölçekleniyor ve docstring'i
    "DÖNGÜNÜN duvar saati tavanı" diyor — HER turun kendi bütçesi değil,
    turların TOPLAMI. Saat tur başına sıfırlansaydı 2 turluk bir üretimde
    gerçek tavan `2×butce` olurdu.

    `WAN` için `total_budget(WAN, 2) == 360.0` (`read_timeout_for`in
    `images_per_request=1` dalı: `180 sn × n`). Saat: BAŞLANGIÇ 0.0
    (`_uret`in `son_tarih`i hesapladığı an) → BİRİNCİ turun yoklaması 100.0
    (bütçe içinde, tur BAŞARIYLA biter) → İKİNCİ turun yoklaması 400.0
    (360'ı aşmış). Turlar arasında saat sıfırlanıyor olsaydı ikinci tur
    kendi TAZE 360 sn'lik bütçesiyle 400'ü de bütçe içinde sayar, submit'ten
    sonra bir yoklama GET'i daha atardı."""
    saat = iter([0.0, 100.0, 400.0] + [10_000.0] * 20)
    monkeypatch.setattr(fal_client, "_simdi", lambda: next(saat))
    client = FakeClient(
        FakeResponse(200, {"request_id": "tur1"}),
        FakeResponse(200, {"status": "COMPLETED"}),
        FakeResponse(200, {"video": {"url": "https://v3.fal.media/1.mp4"}}),
        FakeResponse(200, content=MP4),
        FakeResponse(200, {"request_id": "tur2"}),
    )
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 2,
                            client=client, credentials=CREDS)
    assert "bitmedi" in str(exc.value).lower()
    # İKİNCİ tur SUBMIT'ten öteye geçmedi: son tarih paylaşılan bir mutlak
    # an olduğu için yoklamanın İLK kontrolünde zaten dolmuştu.
    assert len(client.calls) == 5


def test_animate_uses_the_image_to_video_endpoint():
    client = FakeClient(*_kuyruk_yanitlari())
    fal_client.animate(WAN, "kedi", REFS, "16:9", "720p", 5, 1,
                       client=client, credentials=CREDS)
    assert client.calls[0]["url"].endswith("/image-to-video")


def test_animate_rejects_a_last_frame_since_none_of_the_three_wire_schemas_support_it():
    """`last_frame` sözleşmede var ama fal'ın üç modelinin de i2v şemasında
    `tail_image_url` yok (bkz. `animate`'in docstring'i) — ikinci kapı
    burada, ağa hiç çıkmadan."""
    with pytest.raises(ac.ImageError) as exc:
        fal_client.animate(WAN, "kedi", REFS, "16:9", "720p", 5, 1,
                           last_frame=b"\x89PNG")
    assert "bitiş" in str(exc.value).lower()


def test_a_download_redirect_is_followed_MANUALLY_and_capped():
    """`follow_redirects` KULLANILMIYOR: yönlendirme ELLE izleniyor ve
    `MAX_YONLENDIRME`yi aşınca kendi mesajıyla duruyor.

    Yalnız TAVAN mesajı yeterli bir mandal DEĞİLDİ: biri `_indir`i
    "düzeltip" ikinci atlayışta anahtar göndermeye başlasa ya da hedefi hiç
    DEĞİŞTİRMESE de bu test hâlâ geçerdi. Asıl iddia ikinci indirme
    çağrısının GERÇEKTEN yönlendirilen adrese gittiği ve kimlik taşımadığı.
    """
    yanitlar = _kuyruk_yanitlari()[:-1] + [
        FakeResponse(302, headers={"location": "https://cdn.example/y.mp4"}),
    ]
    client = FakeClient(*yanitlar)
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "yönlendirme" in str(exc.value).lower()
    # 4 kuyruk çağrısından (submit + 2 yoklama + sonuç) SONRAKİ indirme
    # denemeleri.
    indirme = client.calls[4:]
    assert indirme[0]["url"] == "https://v3.fal.media/x.mp4"
    assert indirme[1]["url"] == "https://cdn.example/y.mp4"
    assert "Authorization" not in indirme[1]["headers"]


def test_a_relative_redirect_location_is_resolved_against_the_current_url():
    """`Location` GÖRECELİ de olabiliyor (RFC 7231); `urljoin` onu
    mutlaklaştırıyor — bu davranış şimdiye kadar HİÇ sınanmamıştı."""
    yanitlar = _kuyruk_yanitlari()[:-1] + [
        FakeResponse(302, headers={"location": "/y.mp4"}),
        FakeResponse(200, content=MP4),
    ]
    client = FakeClient(*yanitlar)
    out = fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                              client=client, credentials=CREDS)
    assert out == [MP4]
    assert client.calls[-1]["url"] == "https://v3.fal.media/y.mp4"


def test_a_loopback_download_target_is_rejected_as_a_potential_SSRF():
    """ANAHTARSIZLIK sızıntıyı kapatıyor ama HEDEFİ serbest bırakırsa bir
    masaüstü uygulaması kendi loopback'ine GET atar ve dönen baytlar
    kullanıcıya "video" diye teslim edilir — `_indir`in ikinci kapısı bu
    ölçüyü kapatıyor."""
    yanitlar = _kuyruk_yanitlari()[:-1]
    yanitlar[3] = FakeResponse(200, {"video": {"url": "http://127.0.0.1:9/x.mp4"}})
    client = FakeClient(*yanitlar)
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "ssrf" in str(exc.value).lower()
    # İndirme GET'i HİÇ atılmadı: kapı ağa çıkmadan ÖNCE reddediyor.
    assert len(client.calls) == 4


def test_a_cloud_metadata_download_target_is_rejected_as_a_potential_SSRF():
    """169.254.169.254 bulut meta-veri servislerinin (AWS/GCP/Azure IMDS)
    adresi — SSRF'in klasik hedefi ve `is_link_local` süzgecinin ölçüsü."""
    yanitlar = _kuyruk_yanitlari()[:-1]
    yanitlar[3] = FakeResponse(
        200, {"video": {"url": "http://169.254.169.254/latest/meta-data"}})
    client = FakeClient(*yanitlar)
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "ssrf" in str(exc.value).lower()


def test_a_redirect_to_a_loopback_address_is_rejected_too():
    """Yönlendirme İLK adresi geçse bile YENİ hedefi de denetlemeli: kapı
    yalnız girişte durmuyor, HER `urljoin` sonrasında tekrar çalışıyor."""
    yanitlar = _kuyruk_yanitlari()[:-1] + [
        FakeResponse(302, headers={"location": "http://127.0.0.1:9/evil"}),
    ]
    client = FakeClient(*yanitlar)
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "ssrf" in str(exc.value).lower()
    # Yalnız İLK indirme denemesi yapıldı; loopback'e ikinci bir çağrı GİTMEDİ.
    assert len(client.calls) == 5
