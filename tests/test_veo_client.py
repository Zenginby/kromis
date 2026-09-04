"""veo_client: `predictLongRunning` telinin şekli, YOKLAMA döngüsü ve hata çevirisi.

Bu dosyanın en değerli dört iddiası — hepsi bu adaptörün öteki üçünden
AYRILDIĞI yerlerde:

  1. ÜÇ İSTEK, tek POST DEĞİL. Submit → yokla → indir. Öteki adaptörlerin
     tamamı tek vuruş; buradaki yaşam döngüsü `catalog.poll_timeout`
     alanının var olma sebebi.
  2. SON TARİH DUVAR SAATİYLE ölçülüyor (`providers.total_budget`), yoklama
     SAYISIYLA değil. Sayıya bağlamak, geri çekilme çarpanı değiştiğinde
     tavanın sessizce kayması demekti.
  3. 403/429 "ÜCRETSİZ KADEME YOK" DİYOR. Veo faturalı bir modeldir; görsel
     tarafında çalışan bir `GEMINI_API_KEY` burada reddedilebiliyor ve genel
     "anahtarını kontrol et" metni kullanıcıyı çalışan kurulumunu bozmaya
     davet ederdi.
  4. `done: true` + VİDEO YOK. Operation başarıyla biter ama içerik filtresi
     ya da bir üretim hatası videoyu engellemiş olabilir; gerekçe gövdede
     duruyor ve yutulursa kullanıcı sebebi olmayan bir 502 alır
     (`gemini_client.decode_images`in "200 ile gelen ret metni" dersinin
     video karşılığı).

CANLI DOĞRULAMA YOK ve bu depoda YAPILAMIYOR — gerekçesi `veo_client.py`'nin
başlığında yazılı: Veo'nun ücretsiz kademesi olmadığı için anahtarsız bir
çağrı `gemini_client`in aldığı "yol tanınıyor" sinyalini bile vermiyor.
Aşağıdaki her şey BELGEYE dayanıyor; risk en yüksek üç yer
(`generateVideoResponse.generatedSamples` yuvalanması, `parameters` alan
adları, indirme `GET`inin kimliği) ilk gerçek anahtarla bir kez sınanmalı.
"""
import base64

import pytest

import azure_client as ac
import catalog
import providers
import veo_client as vc

LITE = catalog.video_model("gemini-veo-3-1-lite")
KALITE = catalog.video_model("gemini-veo-3-1")
CREDS = ("AIzaTESTKEY", "https://generativelanguage.googleapis.com")
OP = "models/veo-3.1-lite-generate-preview/operations/abc123"
MP4 = b"\x00\x00\x00\x20ftypmp42"


class FakeResponse:
    def __init__(self, status_code, json_body=None, content=b"", headers=None):
        self.status_code = status_code
        self._json = json_body
        self.content = content
        # `headers` gerçek bir httpx yanıtında her zaman var; indirme
        # yönlendirmesi `location`ı oradan okuyor.
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("gövde JSON değil")
        return self._json


class FakeClient:
    """`httpx.Client` yerine geçen minimal sahte istemci.

    `test_gemini_client.py`'deki kardeşinin `request` sürümü: bu adaptör üç
    farklı yöntemi (POST submit, GET yokla, GET indir) TEK kapıdan geçiriyor
    (`veo_client._istek`), o yüzden sahte de tek yöntem sunuyor.

    BÜTÜN çağrılar biriktiriliyor (`calls`), yalnız sonuncusu değil — üç
    adımlı bir döngüde "kaç yoklama yapıldı?" sorusu tek bir `last_call` ile
    cevaplanamaz.
    """

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append({"method": method, "url": url, "headers": headers,
                           "json": json, "timeout": timeout})
        i = len(self.calls) - 1
        # Tek yanıt verildiyse her çağrıda o dönüyor (kardeş dosyanın kuralı).
        return self._responses[i] if len(self._responses) > 1 else self._responses[0]

    @property
    def last_call(self):
        return self.calls[-1]


@pytest.fixture(autouse=True)
def uyku_yok(monkeypatch):
    """Yoklama uykusu SIFIRLANIYOR — takım gerçek saniyeler beklemesin.

    `veo_client._bekle` modül düzeyinde bir işlev tam olarak bu dikiş için
    (bkz. onun docstring'i). `time.sleep`i küresel olarak yamalamak bütün
    takımı etkilerdi.
    """
    monkeypatch.setattr(vc, "_bekle", lambda saniye: None)


URI = "https://generativelanguage.googleapis.com/v1beta/files/x:download"


def _op(done=True, uri=URI, b64=None, hata=None, rai=None, rai_sayac=None):
    """Bir operation gövdesi. Belgedeki yuvalanma birebir kuruluyor.

    `uri=None` + `b64=None` → `generatedSamples` BOŞ, yani "video yok" hâli.
    `hata` ile `rai` AYRI parametreler çünkü anlamları ayrı (bkz.
    `veo_client._operation_hatasi` / `_filtre_gerekcesi`).
    """
    govde = {"name": OP, "done": done}
    if not done:
        return govde
    ornek = {}
    if uri:
        ornek["video"] = {"uri": uri}
    if b64:
        ornek["video"] = {"bytesBase64Encoded": base64.b64encode(b64).decode()}
    kap = {"generatedSamples": [ornek] if ornek else []}
    if rai is not None:
        kap["raiMediaFilteredReasons"] = rai
    if rai_sayac is not None:
        kap["raiMediaFilteredCount"] = rai_sayac
    govde["response"] = {"generateVideoResponse": kap}
    if hata:
        govde["error"] = {"code": 400, "message": hata}
    return govde


# ── Tel formatı ────────────────────────────────────────────────────────


def test_the_submit_path_carries_the_model_IN_THE_PATH_not_the_body():
    """Interactions ucundan AYRILDIĞI ilk yer: model YOLDA.

    `gemini_client` modeli gövdeye koyuyor (`payload["model"]`); Veo onu
    yolun içinde istiyor. Karışırsa uç 404 döner ve hata "model bulunamadı"
    kılığında görünür — yani sebebi yanlış yerde aratan bir mesaj.
    """
    c = FakeClient(FakeResponse(200, _op(done=False)),
                   FakeResponse(200, _op()),
                   FakeResponse(200, content=MP4))

    vc.generate(LITE, "kedi", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    submit = c.calls[0]
    assert submit["method"] == "POST"
    assert submit["url"] == (
        "https://generativelanguage.googleapis.com"
        "/v1beta/models/veo-3.1-lite-generate-preview:predictLongRunning")
    assert "model" not in submit["json"]


def test_the_endpoint_path_carries_the_VERSION_prefix_in_code():
    """`GEMINI_BASE_URL` çıplak konak: sürüm geçişi kullanıcının kayıtlı
    adresini geçersiz kılan bir migrasyon OLMAMALI (`gemini_client`in aynı
    kararı ve aynı gerekçesi)."""
    c = FakeClient(FakeResponse(200, _op()), FakeResponse(200, content=MP4))

    vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c,
                credentials=("AIza", "https://generativelanguage.googleapis.com/"))

    assert "/v1beta/models/" in c.calls[0]["url"]
    assert "//v1beta" not in c.calls[0]["url"]


def test_credentials_travel_in_the_GOOGLE_header_on_ALL_THREE_requests():
    """Kimlik üç isteğin ÜÇÜNDE de gerekiyor — indirme dahil.

    İmzalı `uri`ye anahtarsız bir `GET` 403 döner ve hata "video döndürmedi"
    kılığında görünür. `_istek`in tek kapı olması tam olarak bunun için.
    """
    c = FakeClient(FakeResponse(200, _op(done=False)),
                   FakeResponse(200, _op()),
                   FakeResponse(200, content=MP4))

    vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert len(c.calls) == 3
    for cagri in c.calls:
        assert cagri["headers"]["x-goog-api-key"] == "AIzaTESTKEY"
        assert "Authorization" not in cagri["headers"]


def test_the_knobs_go_into_PARAMETERS_not_into_size_and_quality():
    """Kataloğun `sizes`/`qualities`/`durations` alanları Veo'da ÜÇ BAŞKA tel
    alanına çözülüyor. Azure'ın `size`/`quality` adlarını göndermek 400 demek."""
    c = FakeClient(FakeResponse(200, _op()), FakeResponse(200, content=MP4))

    vc.generate(KALITE, "k", "9:16", "1080p", 8, 1, client=c, credentials=CREDS)

    govde = c.calls[0]["json"]
    assert govde["parameters"] == {"aspectRatio": "9:16", "resolution": "1080p",
                                   "durationSeconds": 8, "sampleCount": 1}
    assert "size" not in govde and "quality" not in govde


def test_the_prompt_lives_inside_a_single_INSTANCE():
    c = FakeClient(FakeResponse(200, _op()), FakeResponse(200, content=MP4))

    vc.generate(LITE, "kedi koşuyor", "16:9", "720p", 4, 1, client=c,
                credentials=CREDS)

    assert c.calls[0]["json"]["instances"] == [{"prompt": "kedi koşuyor"}]


def test_animate_puts_the_first_frame_INSIDE_the_same_instance():
    """Veo'da animasyon AYRI BİR UÇ DEĞİL: referans kare aynı isteğin bir
    alanı (`gemini_client`in düzenlemeyi `input[]`e katmasının aynı olgusu)."""
    c = FakeClient(FakeResponse(200, _op()), FakeResponse(200, content=MP4))

    vc.animate(LITE, "canlandır", [("a.png", b"\x89PNG")], "16:9", "720p", 4, 1,
               client=c, credentials=CREDS)

    instance = c.calls[0]["json"]["instances"][0]
    assert instance["prompt"] == "canlandır"
    assert instance["image"] == {
        "bytesBase64Encoded": base64.b64encode(b"\x89PNG").decode(),
        "mimeType": "image/png"}
    # Uç yine `predictLongRunning`: ikinci bir adres YOK.
    assert c.calls[0]["url"].endswith(":predictLongRunning")


def test_only_the_FIRST_reference_is_sent():
    """Katalog `max_refs=1` diyor (ilk kare) ve adaptör de kesiyor.

    Fazlasını göndermek telde 400 olurdu; sessizce göndermemek ise kullanıcının
    eklediği görselin nereye gittiğini belirsiz bırakırdı — o yüzden GERÇEK
    kapı arayüzde ve rotada (`goBlockReason`, `_check_video_form`), buradaki
    kesme yalnız son savunma.
    """
    c = FakeClient(FakeResponse(200, _op()), FakeResponse(200, content=MP4))

    vc.animate(LITE, "k", [("a.png", b"BIR"), ("b.png", b"IKI")], "16:9",
               "720p", 4, 1, client=c, credentials=CREDS)

    instance = c.calls[0]["json"]["instances"][0]
    assert base64.b64decode(instance["image"]["bytesBase64Encoded"]) == b"BIR"


def test_the_LAST_FRAME_rides_in_the_same_instance_as_the_first():
    """Son kare `instances[0].lastFrame` — `image` ile AYNI biçim.

    Biçim ortak bir yardımcıdan (`_kare`) geliyor: iki alanın ayrışması,
    birine `mimeType` eklenip ötekine unutulmasıyla biten türden bir kusur
    olurdu ve telin cevabı yalnız 400 derdi, hangi alan diye söylemezdi.
    """
    c = FakeClient(FakeResponse(200, _op()), FakeResponse(200, content=MP4))

    vc.animate(LITE, "geçiş", [("a.png", b"ILK")], "16:9", "720p", 4, 1,
               last_frame=b"SON", client=c, credentials=CREDS)

    instance = c.calls[0]["json"]["instances"][0]
    assert instance["image"] == {
        "bytesBase64Encoded": base64.b64encode(b"ILK").decode(),
        "mimeType": "image/png"}
    assert instance["lastFrame"] == {
        "bytesBase64Encoded": base64.b64encode(b"SON").decode(),
        "mimeType": "image/png"}
    # Uç yine `predictLongRunning` ve `parameters` DEĞİŞMEDİ: son kare bir
    # knob değil, bir girdi.
    assert c.calls[0]["url"].endswith(":predictLongRunning")
    assert set(c.calls[0]["json"]["parameters"]) == {
        "aspectRatio", "resolution", "durationSeconds", "sampleCount"}


def test_WITHOUT_a_last_frame_the_body_is_bit_for_bit_what_it_always_was():
    """Alanın adı canlı olarak DOĞRULANMADI (bkz. modül docstring'i), yani
    riskin nereye hapsedildiği önemli: `lastFrame` yalnız kullanıcı bir bitiş
    görseli seçtiğinde gövdeye giriyor. Ad yanlışsa kırılan tek şey o yeni
    yol olur; bitiş görseli seçmeyen herkesin isteği aynı kalır."""
    c = FakeClient(FakeResponse(200, _op()), FakeResponse(200, content=MP4))

    vc.animate(LITE, "k", [("a.png", b"ILK")], "16:9", "720p", 4, 1,
               client=c, credentials=CREDS)

    assert "lastFrame" not in c.calls[0]["json"]["instances"][0]

    # Metinden üretimde de yok — o yolda kare KAVRAMI bile yok.
    c2 = FakeClient(FakeResponse(200, _op()), FakeResponse(200, content=MP4))
    vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c2, credentials=CREDS)
    assert c2.calls[0]["json"]["instances"] == [{"prompt": "k"}]


# ── Yoklama döngüsü ────────────────────────────────────────────────────


def test_a_ready_operation_is_NOT_polled_again():
    """`done` İLK yanıtta da gelebiliyor: döngü uykuyla değil KONTROLLE
    başlıyor. Uykuyla başlamak, hazır olan bir sonucu bir saniye bekletmek —
    ve bir yoklama isteğini boşa harcamak — olurdu."""
    c = FakeClient(FakeResponse(200, _op()), FakeResponse(200, content=MP4))

    out = vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c,
                      credentials=CREDS)

    assert out == [MP4]
    # submit + indirme = 2. Arada YOKLAMA YOK.
    assert [cagri["method"] for cagri in c.calls] == ["POST", "GET"]


def test_the_loop_polls_until_done_and_THEN_downloads():
    c = FakeClient(FakeResponse(200, _op(done=False)),
                   FakeResponse(200, _op(done=False)),
                   FakeResponse(200, _op(done=False)),
                   FakeResponse(200, _op()),
                   FakeResponse(200, content=MP4))

    out = vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c,
                      credentials=CREDS)

    assert out == [MP4]
    yoklamalar = [cagri for cagri in c.calls[1:-1]]
    assert len(yoklamalar) == 3
    for y in yoklamalar:
        assert y["method"] == "GET"
        assert y["url"] == ("https://generativelanguage.googleapis.com/v1beta/" + OP)


def test_the_poll_requests_do_NOT_get_the_whole_poll_budget_as_read_timeout():
    """ÜÇ AYRI ZAMAN AŞIMI bu dosyanın taşıyıcı kararı.

    Yoklama bir metadata çağrısı; ona `poll_timeout`u (7 dakika) vermek, ölü
    bir ağda tek bir yoklamada o kadar beklemek olurdu. `read_timeout_for`ın
    sözleşmesi de "TEK isteğin okuma süresi" ve onu toplam son tarih olarak
    kullanmak o sözleşmeyi bozardı.
    """
    c = FakeClient(FakeResponse(200, _op(done=False)),
                   FakeResponse(200, _op()),
                   FakeResponse(200, content=MP4))

    vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    butce = providers.total_budget(LITE, 1)
    submit, yokla, indir = c.calls
    assert submit["timeout"].read == vc.POLL_READ_TIMEOUT
    assert yokla["timeout"].read == vc.POLL_READ_TIMEOUT
    assert indir["timeout"].read == vc.DOWNLOAD_READ_TIMEOUT
    # Üçünün hiçbiri toplam bütçeyi TEK isteğe vermiyor.
    assert vc.POLL_READ_TIMEOUT < butce
    assert vc.DOWNLOAD_READ_TIMEOUT < butce


def test_the_deadline_is_measured_on_the_WALL_CLOCK_not_the_poll_count(monkeypatch):
    """Son tarih `providers.total_budget`ten geliyor ve DUVAR SAATİ ölçüyor.

    Yoklama SAYISINA bağlamak, geri çekilme çarpanı (`POLL_BACKOFF`)
    değiştiğinde tavanın sessizce kayması demekti — yani bir sabiti
    ayarlayan kişi farkında olmadan zaman aşımı politikasını değiştirirdi.
    """
    saat = iter([0.0, 1.0, 2.0, 10_000.0])
    monkeypatch.setattr(vc, "_simdi", lambda: next(saat))
    c = FakeClient(FakeResponse(200, _op(done=False)))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    metin = str(hata.value)
    assert "bitmedi" in metin
    assert "420" in metin, "tavan metinde yazmıyor"
    # ÜCRET UYARISI: zaman aşımı İSTEMCİNİN vazgeçmesi, Google'ın değil.
    assert "ücretlendirilmiş olabilir" in metin


def test_the_backoff_is_capped():
    """Tavan olmadan üstel artış bir noktada son tarihi TEK bir uykuda aşardı
    ve kullanıcı sonucu hazır olduktan dakikalar sonra görürdü."""
    assert vc.POLL_INTERVAL_START < vc.POLL_INTERVAL_MAX
    assert vc.POLL_BACKOFF > 1


def test_the_sleep_never_overshoots_the_remaining_budget(monkeypatch):
    """Uyku KALAN bütçeyle de sınırlı: son tarihe 1 saniye kalmışken 10
    saniye uyumak, zaman aşımını 9 saniye geciktirmek olurdu."""
    uykular = []
    monkeypatch.setattr(vc, "_bekle", lambda s: uykular.append(s))
    # Sabit saat: geçen süre hep bütçenin 0,5 saniye altında.
    monkeypatch.setattr(vc, "_simdi",
                        lambda: 0.0 if not uykular else providers.total_budget(LITE, 1) - 0.5)
    c = FakeClient(FakeResponse(200, _op(done=False)),
                   FakeResponse(200, _op(done=False)),
                   FakeResponse(200, _op()),
                   FakeResponse(200, content=MP4))

    vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert uykular, "hiç uyunmadı"
    assert max(uykular) <= vc.POLL_INTERVAL_MAX
    assert uykular[-1] <= 0.5


# ── Sonucun okunması ───────────────────────────────────────────────────


def test_the_download_FOLLOWS_a_redirect_manually():
    """İmzalı `uri` depolama katmanına 302 ile yönlendiriyor ve httpx
    varsayılan olarak yönlendirmeyi İZLEMİYOR. İzlenmezse gövde boş bir 302
    olur ve hata "video döndürmedi" kılığında görünür — sebebi yanlış yerde
    aratan bir mesaj.

    İzleme ELLE (`veo_client._indir`) ve gerekçesi bir sonraki testte:
    `follow_redirects=True` özel başlıkları da taşıyordu.
    """
    hedef = "https://storage.example.com/imzali/x.mp4"
    c = FakeClient(FakeResponse(200, _op()),
                   FakeResponse(302, headers={"location": hedef}),
                   FakeResponse(200, content=MP4))

    out = vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c,
                      credentials=CREDS)

    assert out == [MP4]
    assert c.calls[-1]["url"] == hedef


def test_the_api_key_is_NOT_forwarded_to_a_NON_GOOGLE_redirect():
    """Bu dosyanın güvenlik iddiası.

    `follow_redirects=True` yönlendirmeyi izliyor VE `x-goog-api-key`
    başlığını yeni konağa da taşıyordu (httpx yalnız `Authorization`ı
    soyuyor). Hedef konak YANIT GÖVDESİNDEN geliyor, yani onu gövdeyi yazan
    taraf belirliyor — faturalı bir Gemini anahtarını Google dışı bir konağa
    vermek, anahtarı karşı tarafın eline bırakmak olurdu. İmzalı depolama
    adresleri kimlik istemiyor: imza zaten yetkilendirmenin kendisi.
    """
    c = FakeClient(FakeResponse(200, _op()),
                   FakeResponse(302, headers={
                       "location": "https://storage.example.com/x.mp4"}),
                   FakeResponse(200, content=MP4))

    vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    ilk_indirme, son_indirme = c.calls[1], c.calls[2]
    # Google konağına GİDİYOR…
    assert ilk_indirme["headers"]["x-goog-api-key"] == "AIzaTESTKEY"
    # …yabancı konağa GİTMİYOR.
    assert "x-goog-api-key" not in son_indirme["headers"]


def test_the_api_key_SURVIVES_a_redirect_that_stays_on_google():
    """Anahtarı koşulsuz düşürmek de yanlış olurdu: Google içi bir
    yönlendirme (ör. bölgesel bir uç) kimliği hâlâ isteyebilir."""
    c = FakeClient(FakeResponse(200, _op()),
                   FakeResponse(302, headers={
                       "location": "https://eu.googleapis.com/v1beta/files/x"}),
                   FakeResponse(200, content=MP4))

    vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert c.calls[-1]["headers"]["x-goog-api-key"] == "AIzaTESTKEY"


def test_a_RELATIVE_redirect_target_is_made_absolute():
    """Göreceli adres de geçerli (RFC 7231). Mutlaklaştırılmazsa konak boş
    görünür ve anahtar Google konağında bile DÜŞERDİ."""
    c = FakeClient(FakeResponse(200, _op()),
                   FakeResponse(302, headers={"location": "/v1beta/files/y"}),
                   FakeResponse(200, content=MP4))

    vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert c.calls[-1]["url"] == \
        "https://generativelanguage.googleapis.com/v1beta/files/y"
    assert c.calls[-1]["headers"]["x-goog-api-key"] == "AIzaTESTKEY"


def test_a_redirect_LOOP_ends_with_its_own_message():
    """Sonsuz döngü de bir hata hâli ve zaman aşımıyla değil kendi mesajıyla
    bitmeli — yoksa kullanıcı dakikalarca bekleyip "süre doldu" okur ve
    yanlış knob'u (süreyi) kurcalar."""
    dongu = FakeResponse(302, headers={"location": URI})
    c = FakeClient(FakeResponse(200, _op()), *([dongu] * 20))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert "yönlendirmeden sonra" in str(hata.value)


def test_a_redirect_WITHOUT_a_location_fails_loudly():
    c = FakeClient(FakeResponse(200, _op()), FakeResponse(302))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert "adres taşımıyor" in str(hata.value)


def test_an_INLINE_base64_video_needs_no_second_request():
    """Belge İKİ dal söylüyor: imzalı `uri` ya da `bytesBase64Encoded`.
    Birini atlamak, çalışan bir kurulumda "video döndürmedi" hatası vermek
    olurdu."""
    c = FakeClient(FakeResponse(200, _op(uri=None, b64=MP4)))

    out = vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c,
                      credentials=CREDS)

    assert out == [MP4]
    # submit + (done) — İNDİRME YOK.
    assert len(c.calls) == 1


def test_more_samples_than_requested_are_TRUNCATED():
    """`gemini_client._uret`in tavanıyla aynı gerekçe: fazlalık sessizce
    ilerlemiyor, ilerideki bir doğrulamada patlıyor (`ChatMessage.image_ids`
    `max_length=4`) — hem de video ÜRETİLDİKTEN ve ücret ödendikten sonra."""
    op = _op()
    op["response"]["generateVideoResponse"]["generatedSamples"] = [
        {"video": {"bytesBase64Encoded": base64.b64encode(b"BIR").decode()}},
        {"video": {"bytesBase64Encoded": base64.b64encode(b"IKI").decode()}},
    ]
    c = FakeClient(FakeResponse(200, op))

    out = vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c,
                      credentials=CREDS)

    assert out == [b"BIR"]


def test_a_FAILED_operation_reports_its_error_EVEN_IF_a_video_is_present():
    """`error` alanı operation'ın DÜŞTÜĞÜNÜ söylüyor: gövdede bir video
    görünse bile o sonuç geçerli değil, yani dal KOŞULSUZ yükseltiliyor.
    `gemini_client.decode_images`in "200 ile gelen ret metnini yutma"
    dersinin video karşılığı — gerekçe elimizdeyken "video üretilemedi"
    demek, kullanıcıya sebebi olmayan bir 502 vermek."""
    c = FakeClient(FakeResponse(200, _op(hata="quota exceeded for veo")),
                   FakeResponse(200, content=MP4))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert "quota exceeded for veo" in str(hata.value)
    # İNDİRME HİÇ DENENMEDİ: düşmüş bir işin videosu indirilmez.
    assert len(c.calls) == 1


def test_a_SAFETY_FILTERED_operation_reports_the_filter_reason():
    """RAI filtresi HİÇBİR HTTP durumuyla haber verilmiyor: reddedilen bir
    prompt da 200 + `done: true` dönüyor. Yutulursa kullanıcı sebebi
    olmayan bir hata alır — hem de gerekçe gövdede yazılıyken."""
    c = FakeClient(FakeResponse(200, _op(uri=None, rai=["Person/Face generation"])))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert "Person/Face generation" in str(hata.value)


def test_a_filter_COUNT_without_reasons_still_reports_something():
    c = FakeClient(FakeResponse(200, _op(uri=None, rai_sayac=1)))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert "güvenlik filtresi" in str(hata.value)


def test_a_PARTIAL_filter_still_DELIVERS_the_video_that_came():
    """Filtre KISMİ olabiliyor: n örnekten biri engellenir, geri kalanı
    teslim edilir. Gerekçeyi koşulsuz yükseltmek, Google'ın ÜRETTİĞİ ve
    FATURALADIĞI bir videoyu atmak olurdu. `max_n=1` olduğu sürece
    ulaşılamaz bir dal — bu test onun katalog tavanı yükseldiği gün de doğru
    kalmasını sağlıyor."""
    c = FakeClient(FakeResponse(200, _op(rai_sayac=1)),
                   FakeResponse(200, content=MP4))

    out = vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c,
                      credentials=CREDS)

    assert out == [MP4]


def test_an_unrecognised_shape_YIELDS_TO_the_filter_reason():
    """Şekil tanınmadı AMA filtre gerekçesi var: kullanıcının okumak
    istediği şey gerekçe, "generatedSamples yok" değil."""
    op = {"name": OP, "done": True,
          "response": {"raiMediaFilteredReasons": ["Celebrity likeness"]}}
    c = FakeClient(FakeResponse(200, op))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    metin = str(hata.value)
    assert "Celebrity likeness" in metin
    assert "generatedSamples" not in metin


def test_an_UNRECOGNISED_response_shape_names_the_keys_it_found():
    """Bu dosyanın en riskli varsayımı yuvalanma (canlı doğrulanmadı).
    Uç bir gün adı değiştirirse kullanıcının göreceği metin teşhisi TEK
    turda yapılabilir kılmalı — o yüzden mesaj BULUNAN anahtarları yazıyor."""
    c = FakeClient(FakeResponse(200, {"name": OP, "done": True,
                                      "response": {"videos": [{"uri": "x"}]}}))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    metin = str(hata.value)
    assert "generatedSamples" in metin
    assert "videos" in metin, "gövdede bulunan anahtarlar yazılmıyor"


def test_a_submit_without_an_operation_name_fails_loudly():
    c = FakeClient(FakeResponse(200, {"metadata": {}}))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert "operation adı yok" in str(hata.value)


# ── Hata çevirisi ──────────────────────────────────────────────────────


@pytest.mark.parametrize("kod", [401, 403])
def test_the_access_denied_message_says_VEO_HAS_NO_FREE_TIER(kod):
    """Bu dosyanın en önemli iddiası.

    Veo faturalı bir modeldir. Görsel tarafında ÇALIŞAN bir `GEMINI_API_KEY`,
    projesinde faturalandırma açık değilse burada reddediliyor — ve genel
    "anahtar geçersiz olabilir" metni, anahtarı gerçekten doğru olan
    kullanıcıyı çalışan kurulumunu bozmaya davet ederdi.
    """
    metin = vc.map_error(kod, {"error": {"message": "billing not enabled"}})

    assert "ÜCRETSİZ KADEMESİ YOK" in metin
    assert "faturalandırma" in metin
    assert "billing not enabled" in metin
    # "Anahtarını yeniden kaydet" DEMİYOR: yanlış iş.
    assert "yeniden kaydet" not in metin


def test_an_INVALID_KEY_400_is_told_apart_from_a_bad_token():
    """400 İKİ ANLAMLI ve ayrım gövdeden okunuyor — `gemini_client`in aynı
    kararı, aynı paylaşılan yüklemle (`providers.is_invalid_key`)."""
    anahtar = vc.map_error(400, [{"error": {"message": "API key not valid."}}])
    jeton = vc.map_error(400, {"error": {"message": "Invalid aspectRatio"}})

    assert "anahtarı geçersiz" in anahtar
    assert "anahtarı geçersiz" not in jeton
    assert "Invalid aspectRatio" in jeton


def test_a_404_NAMES_THE_MODEL_that_the_wire_actually_asked_for():
    """`openai-dall-e-3` deneyiminin dersi: "model bulunamadı" diyen ama
    hangi model olduğunu söylemeyen bir hata, kullanıcıyı anahtarını
    kurcalamaya iter."""
    metin = vc.map_error(404, None, wire_model="veo-3.1-lite-generate-preview")

    assert "veo-3.1-lite-generate-preview" in metin
    assert "şeritten başka bir model seç" in metin


def test_a_CONTENT_POLICY_400_says_so():
    metin = vc.map_error(400, {"error": {"message": "blocked by safety filters"}})

    assert "İçerik politikası" in metin


def test_the_error_texts_never_borrow_the_IMAGE_adapters_wording():
    """ŞEKİL paylaşılıyor, METİN paylaşılmıyor (`gemini_client`in duruşu).

    "Azure isteği başarısız" ya da "Gemini görsel döndürmedi" diyen bir metin,
    video faturasını arayan kullanıcıyı yanlış yere yönlendirirdi.

    "GÖRSEL" SÖZCÜĞÜ TÜMDEN YASAK DEĞİL ve bu ayrım bilinçli: 403 dalı
    "anahtar görsel üretiminde çalışıyorsa sorun anahtarda değil" diyor ve o
    cümle tam olarak bu adaptörün en değerli teşhisi — kullanıcının elindeki
    çalışan kurulumu işaret ediyor. Yasak olan şey görsel adaptörünün
    CÜMLELERİNİ devralmak.
    """
    for kod in (400, 401, 403, 404, 429, 500):
        metin = vc.map_error(kod, None)
        assert "Azure" not in metin
        assert "Gemini görsel" not in metin
        assert "Gemini isteği" not in metin


def test_a_non_200_SUBMIT_is_translated_and_the_loop_never_starts():
    c = FakeClient(FakeResponse(403, {"error": {"message": "no billing"}}))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert "ÜCRETSİZ KADEMESİ YOK" in str(hata.value)
    assert len(c.calls) == 1, "submit düştüğü hâlde yoklama başladı"


def test_a_non_200_POLL_is_translated():
    c = FakeClient(FakeResponse(200, _op(done=False)),
                   FakeResponse(429, {"error": {"message": "slow down"}}))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert "429" in str(hata.value)


def test_a_non_200_DOWNLOAD_is_translated():
    """Üçüncü isteğin de kendi hata yolu var: 200 alınmış bir operation'dan
    sonra indirmenin düşmesi, "video döndürmedi" DEĞİL bir HTTP hatası."""
    c = FakeClient(FakeResponse(200, _op()), FakeResponse(403, None))

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=c, credentials=CREDS)

    assert "403" in str(hata.value) or "ÜCRETSİZ KADEMESİ YOK" in str(hata.value)


def test_a_transport_error_is_WRAPPED_into_ImageError():
    """Sarmalanmayan bir httpx hatası `app.py`nin `except ac.AzureImageError`
    süzgeçinden GEÇER, ham 500 olur ve arayüz gövdeyi JSON olarak
    ayrıştıramaz: kullanıcı dakikalarca bekleyip yalnız "Hata (500)" görür
    (`ac.ImageError`in docstring'inde kayıtlı tuzak)."""
    import httpx

    class RaisingClient:
        def request(self, *a, **k):
            raise httpx.ConnectError("ağ yok")

    with pytest.raises(ac.ImageError) as hata:
        vc.generate(LITE, "k", "16:9", "720p", 4, 1, client=RaisingClient(),
                    credentials=CREDS)

    metin = str(hata.value)
    assert "Veo" in metin
    assert "Azure" not in metin, "sağlayıcı adı düzeltilmemiş"
