"""`/api/video` ve `/api/video/animate`: rota sözleşmesi ve yetenek kapıları.

Bu dosyanın dört iddiası:

  1. ANAHTAR `videos`, `images` DEĞİL. Bayat bir istemci `{"images": …}`
     bekleyip videoyu `<img>` olarak çizerdi — sessiz bir bozuk resim. Ayrı
     anahtar o hatayı YÜKSEK SESLE "images undefined"a çeviriyor.
  2. KAYIT TÜRÜ TAŞIYOR ve uzantı ONDAN türetiliyor (`.mp4`), yani servis
     ve indirme yolları doğru MIME'ı verebiliyor.
  3. YETENEK KAPISI İKİ UÇTA AYNI. JSON ucu pydantic ile, multipart uç elle
     doğruluyor (`app._check_video_form`) ve ikisinin ayrışması "arayüz bir
     süreyi sunar, bir uçta geçer, ötekinde 422 döner" demekti — o yüzden
     kapılar parametrik olarak İKİSİNDE BİRDEN ölçülüyor
     (`test_model_secimi.py`'nin kurulmuş deseni).
  4. GÖRSEL MODEL id'si REDDEDİLİYOR. `providers._resolve_video`
     `catalog.video_model`a bakıyor, `image_model`a değil: senkron bir görsel
     adaptörüne düşen bir video isteği, sessiz sapmanın en pahalı türü olurdu.

Sevk memuru MAYMUN-YAMALANIYOR (`appmod.providers.generate_video`), adaptör
değil: rota testinin işi sağlayıcı teli değil, rotanın kendi sözleşmesi.
Telin şekli `tests/test_veo_client.py`'de ölçülüyor.
"""
import io

import pytest
from PIL import Image
from fastapi.testclient import TestClient

import app as appmod
import azure_client as ac
import catalog

MP4 = b"\x00\x00\x00\x20ftypmp42"
GECERLI = {"prompt": "kedi koşuyor", "size": "16:9", "quality": "720p",
           "duration": 4}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(appmod.providers, "generate_video",
                        lambda *a, **k: [MP4])
    monkeypatch.setattr(appmod.providers, "animate_video",
                        lambda *a, **k: [MP4])
    return TestClient(appmod.app)


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, format="PNG")
    return buf.getvalue()


# ── Mutlu yol ──────────────────────────────────────────────────────────


def test_the_response_key_is_VIDEOS_not_images(client):
    """Bayat bir istemci videoyu `<img>` olarak çizmesin: anahtar AYRI."""
    r = client.post("/api/video", json=GECERLI)

    assert r.status_code == 200, r.text
    govde = r.json()
    assert "videos" in govde
    assert "images" not in govde


def test_the_record_carries_the_KIND_and_the_DURATION(client, tmp_path):
    r = client.post("/api/video", json=GECERLI)
    rec = r.json()["videos"][0]

    assert rec["kind"] == "video"
    assert rec["duration"] == 4
    # Uzantı `kind`dan TÜRETİLİYOR: ikinci bir gerçek kaynağı yok.
    assert rec["filename"] == f"{rec['id']}.mp4"
    assert (tmp_path / rec["filename"]).read_bytes() == MP4


def test_the_model_defaults_to_the_catalogs_video_default(client):
    """`model` göndermeyen bir istek varsayılan VİDEO modeline gidiyor —
    görselin varsayılanına DEĞİL."""
    rec = client.post("/api/video", json=GECERLI).json()["videos"][0]

    assert rec["model"] == catalog.DEFAULT_VIDEO_MODEL
    assert rec["model"] != catalog.DEFAULT_IMAGE_MODEL


def test_the_credit_cost_is_MULTIPLIED_by_the_duration(client):
    """Video modellerinde `credits` SANİYE BAŞINA (bkz.
    catalog.ImageModel.credits). Kayda ÜRETİM ANINDAKİ çözülmüş tam sayı
    yazılıyor, katalog işaretçisi değil — tarife değişince geçmiş retroaktif
    olarak yeniden yazılmasın."""
    spec = catalog.video_model(catalog.DEFAULT_VIDEO_MODEL)

    dort = client.post("/api/video", json=GECERLI).json()["videos"][0]
    sekiz = client.post("/api/video", json={**GECERLI, "duration": 8}) \
                  .json()["videos"][0]

    assert dort["credits"] == spec.credits * 4
    assert sekiz["credits"] == spec.credits * 8
    assert sekiz["credits"] == dort["credits"] * 2


def test_the_video_is_labelled_with_the_session_it_was_born_in(client):
    """`/api/generate`in aynı sözleşmesi: oturum etiketi koşullu yazılıyor."""
    icinde = client.post("/api/video", json={**GECERLI,
                                             "session_id": "beef1234beef"}) \
                   .json()["videos"][0]
    disinda = client.post("/api/video", json=GECERLI).json()["videos"][0]

    assert icinde["session_id"] == "beef1234beef"
    assert "session_id" not in disinda


def test_the_reference_frame_path_records_the_PARENT(client):
    """Türev zinciri: galeriden canlandırılan bir video kaynağını taşıyor."""
    import azure_client as ac_mod
    from unittest.mock import patch

    with patch.object(ac_mod, "generate", lambda *a, **k: [_png()]):
        with patch.object(appmod, "_to_png", lambda raw: _png()):
            kaynak = client.post("/api/generate",
                                 json={"prompt": "kedi", "size": "1024x1024",
                                       "quality": "medium", "n": 1}) \
                           .json()["images"][0]

    r = client.post("/api/video/animate",
                    data={**GECERLI, "source_id": kaynak["id"]})

    assert r.status_code == 200, r.text
    rec = r.json()["videos"][0]
    assert rec["parent_id"] == kaynak["id"]
    assert rec["kind"] == "video"


def test_an_UPLOADED_frame_is_accepted(client, monkeypatch):
    monkeypatch.setattr(appmod, "_to_png", lambda raw: _png())

    r = client.post("/api/video/animate", data=GECERLI,
                    files={"file": ("a.png", _png(), "image/png")})

    assert r.status_code == 200, r.text
    assert r.json()["videos"][0]["parent_id"] is None


# ── Bitiş görseli (son kare) ───────────────────────────────────────────


def _son_kare_yakala(monkeypatch):
    """Sevk memuruna ulaşan `last_frame`i yakalayan sahte."""
    gorulen = {}

    def sahte(*a, **k):
        gorulen["last_frame"] = k.get("last_frame")
        return [MP4]

    monkeypatch.setattr(appmod.providers, "animate_video", sahte)
    return gorulen


def test_the_LAST_FRAME_reaches_the_dispatcher_as_PNG_bytes(client, monkeypatch):
    """Bitiş görseli `refs`e KATILMIYOR, kendi argümanı olarak gidiyor.

    Katılsaydı `max_refs=1` kapısı (app.py'nin "en fazla N referans görsel"
    satırı) bitiş görseli seçen HER isteği 422 yapardı — yani yetenek eklenir
    eklenmez kendi kapısına takılırdı."""
    monkeypatch.setattr(appmod, "_to_png", lambda raw: _png())
    gorulen = _son_kare_yakala(monkeypatch)

    r = client.post("/api/video/animate", data=GECERLI,
                    files={"file": ("a.png", _png(), "image/png"),
                           "last_file": ("b.png", _png(), "image/png")})

    assert r.status_code == 200, r.text
    assert gorulen["last_frame"] is not None
    assert gorulen["last_frame"].startswith(b"\x89PNG")


def test_WITHOUT_a_last_frame_the_dispatcher_sees_None(client, monkeypatch):
    """Bugünkü yol DEĞİŞMEDİ: bitiş görseli seçmeyen istek aynı istek."""
    monkeypatch.setattr(appmod, "_to_png", lambda raw: _png())
    gorulen = _son_kare_yakala(monkeypatch)

    r = client.post("/api/video/animate", data=GECERLI,
                    files={"file": ("a.png", _png(), "image/png")})

    assert r.status_code == 200, r.text
    assert gorulen["last_frame"] is None


def test_AT_MOST_ONE_of_last_file_or_last_source_id(client, monkeypatch):
    """Ana karenin "tam olarak biri" kapısının ikizi — tek farkı bitiş
    görselinin İSTEĞE BAĞLI olması, yani "hiçbiri" geçerli bir cevap."""
    monkeypatch.setattr(appmod, "_to_png", lambda raw: _png())

    r = client.post("/api/video/animate",
                    data={**GECERLI, "last_source_id": "beef1234beef"},
                    files={"file": ("a.png", _png(), "image/png"),
                           "last_file": ("b.png", _png(), "image/png")})

    assert r.status_code == 422
    assert "last_file" in r.text


def test_a_last_frame_WITHOUT_a_first_frame_is_refused(client, monkeypatch):
    """Son kare tek başına anlamsız: neyin arasında geçiş yapılacağı yok.

    Kapı ANA KARENİN kapısından geliyor (`file` ya da `source_id` zorunlu), bu
    yüzden ayrı bir kural yazılmadı — ama davranışın mandallanması gerekiyor:
    ileride ana kare isteğe bağlı yapılırsa bu test kırılır ve kararı veren
    kişi bu yolu bilerek açmak zorunda kalır."""
    monkeypatch.setattr(appmod, "_to_png", lambda raw: _png())

    r = client.post("/api/video/animate", data=GECERLI,
                    files={"last_file": ("b.png", _png(), "image/png")})

    assert r.status_code == 422


def test_a_model_WITHOUT_the_capability_refuses_the_last_frame(client, monkeypatch):
    """Yetenek `supports_edit`ten AYRI: ilk kareyi alan bir model son kareyi
    almayabilir (Veo 3 ailesinin tamamı böyle)."""
    monkeypatch.setattr(appmod, "_to_png", lambda raw: _png())
    spec = catalog.video_model(catalog.DEFAULT_VIDEO_MODEL)
    monkeypatch.setattr(appmod.catalog, "video_model",
                        lambda mid: spec.__class__(
                            **{**spec.__dict__, "supports_last_frame": False}))

    r = client.post("/api/video/animate", data=GECERLI,
                    files={"file": ("a.png", _png(), "image/png"),
                           "last_file": ("b.png", _png(), "image/png")})

    assert r.status_code == 422
    assert "does not take a last frame" in r.text


def test_a_VIDEO_id_cannot_be_used_as_a_LAST_frame_either(client):
    """Ana karenin aynı kararı: `_output_png_path` uzantıyı ÇAKILI tutuyor ve
    bir MP4'ü kare olarak göndermenin karşılığı yok."""
    video = client.post("/api/video", json=GECERLI).json()["videos"][0]

    r = client.post("/api/video/animate",
                    data={**GECERLI, "last_source_id": video["id"]},
                    files={"file": ("a.png", _png(), "image/png")})

    assert r.status_code == 404


def test_the_capability_flows_to_the_UI_as_its_OWN_key(client):
    """Arayüz "bitiş yuvasını çizeyim mi" sorusunu bu anahtardan soruyor.
    `max_refs`ten türetmek, ikinci referans ile son kareyi aynı sayının
    arkasına saklamak olurdu.

    GÖREV 7 İLE SAĞLAYICIYA GÖRE AYRIŞTI: üç Veo girdisi hâlâ `True`
    (Veo 3.1 ailesinin ortak yeteneği), fal'ın üç modeli ise `False` — yani
    "her video modeli son kareyi alır" iddiası artık YANLIŞ (bkz.
    `test_fal_video_models_declare_no_last_frame` ve `fal_client.animate`'in
    kendi ikinci kapısı). İddia sağlayıcı başına doğru değere indi; görsel
    taraf HİÇ değişmedi.

    DÜZELTME (Görev 9, 2026-09-15): fal'ın `False` olma gerekçesi önceden
    "üç modelin hiçbirinin i2v şemasında `tail_image_url` yok" diye
    yazılıyordu — doğru ama BOŞ, çünkü o ad fal'da hiç kullanılmıyor. Ölçüm
    Wan'ın i2v ucunda GERÇEK bir son-kare alanı (`end_image_url`) olduğunu
    gösterdi; adaptör onu bu turda BİLİNÇLİ OLARAK göndermiyor. PixVerse ve
    Kling'de ise gerçekten hiçbir son-kare alanı yok. Buradaki iddia
    (`supports_last_frame` sağlayıcı başına doğru değere indi) etkilenmiyor.
    """
    ayar = client.get("/api/settings").json()

    for m in ayar["video_models"]:
        beklenen = m["provider"] != "fal"
        assert m["supports_last_frame"] is beklenen, m["id"]
    for m in ayar["image_models"]:
        assert m["supports_last_frame"] is False, m["id"]


# ── Yetenek kapıları: İKİ UÇTA AYNI ────────────────────────────────────
#
# Parametrik desen `tests/test_model_secimi.py`'den: aynı geçersiz değer iki
# uca da gönderiliyor ve İKİSİNİN de 422 dönmesi ölçülüyor. Kapıların
# ayrışması, arayüzün sunduğu bir değerin bir uçta geçip ötekinde reddedilmesi
# demekti.


def _iki_uc(client, monkeypatch, **degisiklik):
    monkeypatch.setattr(appmod, "_to_png", lambda raw: _png())
    govde = {**GECERLI, **degisiklik}
    json_yanit = client.post("/api/video", json=govde)
    form_yanit = client.post("/api/video/animate", data=govde,
                             files={"file": ("a.png", _png(), "image/png")})
    return json_yanit, form_yanit


@pytest.mark.parametrize("degisiklik, beklenen", [
    ({"size": "1:1"}, "does not support this ratio"),
    ({"size": "1024x1024"}, "does not support this ratio"),
    ({"quality": "1080p"}, "does not support this resolution"),
    ({"quality": "4K"}, "does not support this resolution"),
    ({"duration": 5}, "does not support this duration"),
    ({"duration": 0}, "does not support this duration"),
    ({"model": "azure-gpt-image-2"}, "unknown video model"),
    ({"model": "yok-boyle-bir-model"}, "unknown video model"),
])
def test_both_endpoints_refuse_the_same_bad_token(client, monkeypatch,
                                                  degisiklik, beklenen):
    json_yanit, form_yanit = _iki_uc(client, monkeypatch, **degisiklik)

    assert json_yanit.status_code == 422, json_yanit.text
    assert form_yanit.status_code == 422, form_yanit.text
    assert beklenen in json_yanit.text
    assert beklenen in form_yanit.text


def test_the_aspect_ratios_offered_are_ONLY_the_ones_veo_documents(client):
    """`catalog.ASPECT_RATIOS`in on jetonu video tarafında KULLANILMIYOR:
    Veo yalnız iki oran kabul ediyor ve ötekiler telde 400 demek, yani
    arayüzde seçilebilir bir hata."""
    spec = catalog.video_model(catalog.DEFAULT_VIDEO_MODEL)

    for oran in catalog.ASPECT_RATIOS:
        beklenen = 200 if oran in spec.sizes else 422
        r = client.post("/api/video", json={**GECERLI, "size": oran})
        assert r.status_code == beklenen, f"{oran}: {r.status_code}"


def test_the_json_endpoint_REFUSES_palette_fields(client):
    """`VideoRequest` `extra="forbid"` taşıyor ve palet alanı YOK: palet bir
    GÖRSEL prompt eki (bkz. o sınıfın gerekçesi). Sessizce yok saymak,
    kullanıcıya çalışmayan bir çip göstermek olurdu."""
    r = client.post("/api/video", json={**GECERLI, "palette_hex": "#ff0000"})

    assert r.status_code == 422


def test_the_json_endpoint_REFUSES_an_arena_id(client):
    """Arena video tarafında KAPSAM DIŞI: tek tıkla N tane dakikalarca süren
    ve saniyesi faturalanan üretim, kendi kararını ister."""
    r = client.post("/api/video", json={**GECERLI, "arena_id": "beef1234beef"})

    assert r.status_code == 422


def test_MORE_THAN_ONE_reference_is_refused(client, monkeypatch):
    """Katalog `max_refs=1` diyor (ilk kare). Kapı `refs` toplandıktan SONRA:
    erken davranmak `_collect_edit_refs`in kendi 413/422 mesajlarını
    ikizlemek olurdu."""
    monkeypatch.setattr(appmod, "_to_png", lambda raw: _png())
    import azure_client as ac_mod
    from unittest.mock import patch
    with patch.object(ac_mod, "generate", lambda *a, **k: [_png()]):
        kaynak = client.post("/api/generate",
                             json={"prompt": "kedi", "size": "1024x1024",
                                   "quality": "medium", "n": 1}) \
                       .json()["images"][0]

    r = client.post("/api/video/animate",
                    data={**GECERLI, "extra_source_ids": kaynak["id"]},
                    files={"file": ("a.png", _png(), "image/png")})

    assert r.status_code == 422
    assert "reference images" in r.text


def test_EXACTLY_ONE_of_file_or_source_id_is_required(client, monkeypatch):
    monkeypatch.setattr(appmod, "_to_png", lambda raw: _png())

    hicbiri = client.post("/api/video/animate", data=GECERLI)
    ikisi = client.post("/api/video/animate",
                        data={**GECERLI, "source_id": "beef1234beef"},
                        files={"file": ("a.png", _png(), "image/png")})

    assert hicbiri.status_code == 422
    assert ikisi.status_code == 422


def test_a_VIDEO_id_cannot_be_used_as_a_reference_frame(client):
    """`app._output_png_path` uzantıyı ÇAKILI tutuyor ve bu doğru: bir MP4'ü
    ilk kare olarak sağlayıcıya göndermek anlamsız, 404 doğru cevap
    (bkz. `_output_media_path`in docstring'i)."""
    video = client.post("/api/video", json=GECERLI).json()["videos"][0]

    r = client.post("/api/video/animate",
                    data={**GECERLI, "source_id": video["id"]})

    assert r.status_code == 404


# ── Hata çevirisi ──────────────────────────────────────────────────────


@pytest.mark.parametrize("yol, ek", [
    ("/api/video", {}),
    ("/api/video/animate", {"source_id": "yok"}),
])
def test_an_adapter_error_becomes_a_502_with_the_turkish_detail(
        client, monkeypatch, yol, ek):
    """`/api/generate`in aynı sözleşmesi: tek istisna türü, tek kapı, 502."""
    def boom(*a, **k):
        raise ac.ImageError("Veo erişimi reddedildi (403): ÜCRETSİZ KADEMESİ YOK.")

    monkeypatch.setattr(appmod.providers, "generate_video", boom)
    monkeypatch.setattr(appmod.providers, "animate_video", boom)
    monkeypatch.setattr(appmod, "_output_png_path",
                        lambda i: __import__("os").devnull)
    monkeypatch.setattr(appmod, "_read_png_file", lambda p: _png())

    r = client.post(yol, json=GECERLI) if not ek else client.post(yol, data={**GECERLI, **ek})

    assert r.status_code == 502
    assert "ÜCRETSİZ KADEMESİ YOK" in r.json()["detail"]


# ── Servis ve indirme ──────────────────────────────────────────────────


def test_the_drawing_route_serves_VIDEO_MP4(client):
    """v0.13'e kadar `image/png` ÇAKILIYDI ve tek tür varken doğruydu. MP4
    gelince çakılı tür sessiz bir kırılma olurdu: tarayıcı `image/png` diyen
    bir gövdeyi resim olarak çizmeye çalışır, `<video>` hiçbir şey oynatmaz
    ve konsolda bir hata bile çıkmaz."""
    rec = client.post("/api/video", json=GECERLI).json()["videos"][0]

    r = client.get(f"/output/{rec['filename']}")

    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    # Çizim rotası HÂLÂ inline: o adres galeri karosunun `src`i.
    assert "attachment" not in r.headers.get("content-disposition", "")


def test_the_download_route_uses_the_MP4_name_and_type(client):
    """Ad DİSKTEKİ dosyadan geliyor, `image_id`ye uzantı EKLENMİYOR:
    `f"{id}.png"` yazan bir indirme videoyu açılmayan bir adla teslim
    ederdi."""
    rec = client.post("/api/video", json=GECERLI).json()["videos"][0]

    r = client.get(f"/api/output/{rec['id']}/download")

    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    cd = r.headers["content-disposition"]
    assert cd.startswith("attachment;"), cd
    assert f'filename="{rec["id"]}.mp4"' in cd, cd
    assert r.content == MP4


def test_the_IMAGE_paths_are_untouched(client, monkeypatch):
    """"Kayıtlı kullanıcı için sıfır davranış değişikliği": görsel kaydı
    `kind`/`duration` alanlarını HİÇ taşımıyor ve hâlâ `image/png` sunuluyor."""
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])

    rec = client.post("/api/generate", json={"prompt": "kedi",
                                             "size": "1024x1024",
                                             "quality": "medium", "n": 1}) \
                .json()["images"][0]

    assert "kind" not in rec
    assert "duration" not in rec
    assert rec["filename"].endswith(".png")
    assert client.get(f"/output/{rec['filename']}").headers["content-type"] \
        == "image/png"


def test_the_settings_payload_carries_the_video_strip(client):
    """Şerit AYRI bir anahtarda: `image_models`a katmak, o listeyi okuyan her
    yerin (model kartları, arena sütun seçicisi, `secilebilirler`) videoyu
    görsel sanması demekti."""
    s = client.get("/api/settings").json()

    assert s["default_video_model"] == catalog.DEFAULT_VIDEO_MODEL
    assert [m["id"] for m in s["video_models"]] == list(catalog.video_model_ids())
    # Video id'lerinden HİÇBİRİ görsel şeridinde YOK.
    gorsel = {m["id"] for m in s["image_models"]}
    assert gorsel.isdisjoint(set(catalog.video_model_ids()))
    # İki şerit AYNI alan kümesini taşıyor (`app._model_payload` paylaşıldı):
    # birine alan ekleyip ötekini unutmak artık mümkün değil.
    assert sorted(s["video_models"][0]) == sorted(s["image_models"][0])


def test_the_duration_axis_is_EMPTY_for_image_models(client):
    """Arayüz süre satırının kapısını listenin BOŞLUĞUNDAN okuyor; ayrı bir
    `duration_hidden` bayrağı YOK ve olmaması bilinçli (aynı bilginin
    ayrışabilen kopyası olurdu)."""
    s = client.get("/api/settings").json()

    for m in s["image_models"]:
        assert m["durations"] == []
        assert m["default_duration"] == 0
    for m in s["video_models"]:
        assert m["durations"], f"{m['id']} süre taşımıyor"
        assert m["default_duration"] in [d["value"] for d in m["durations"]]


def test_an_EMPTY_last_source_id_means_no_end_frame(client, monkeypatch):
    """Boş form alanı "verilmedi" demek — "verildi ama boş" değil.

    Bütün alanlarını koşulsuz serileştiren bir istemci `last_source_id=""`
    yolluyor. `is not None` onu "bitiş görseli var" sayıyordu ve iki ayrı yanlış
    cevap üretiyordu: yeteneği olmayan bir modelde hiç bitiş karesi TAŞIMAYAN
    bir istek "… bitiş görseli almıyor." diye 422 yiyor, yetenekli modelde ise
    `_output_png_path("")` "Kaynak görsel bulunamadı." diye 404 dönüyordu.
    İkisi de kullanıcının yapmadığı bir şeyi anlatıyor.

    `_extra_refs` galeri id'lerini tam bu yüzden `strip()` ile süzüyor; buradaki
    normalleştirme de kapıdan ÖNCE, yani kapı ile rota AYNI değeri görüyor.
    """
    monkeypatch.setattr(appmod, "_to_png", lambda raw: _png())
    gorulen = _son_kare_yakala(monkeypatch)

    r = client.post("/api/video/animate",
                    data={**GECERLI, "last_source_id": "   "},
                    files={"file": ("a.png", _png(), "image/png")})

    assert r.status_code == 200, r.text
    assert gorulen["last_frame"] is None


def test_a_last_file_part_WITHOUT_a_filename_is_refused_BEFORE_the_route(client,
                                                                        monkeypatch):
    """Dosya tarafında ikiz bir süzgeç YOK ve olmamalı — mandallanan bu.

    Starlette dosya adı olmayan bir parçayı `UploadFile` değil düz `str` olarak
    çözüyor, declared `last_file: UploadFile | None` da onu rota gövdesine
    varmadan 422 yapıyor (`_extra_refs`in ham formu okumasının gerekçesi tam
    bu). Ana karenin `file` alanı da BİREBİR aynı davranıyor; `last_file` için
    ayrı bir süzgeç açmak iki kardeş alanı sessizce ayrıştırmak olurdu.

    Yani `last_source_id`in boş-dize normalleştirmesinin dosya tarafında bir
    karşılığı yok — ve bu bir eksik değil, ölçülmüş bir sınır.
    """
    monkeypatch.setattr(appmod, "_to_png", lambda raw: _png())

    r = client.post("/api/video/animate", data=GECERLI,
                    files={"file": ("a.png", _png(), "image/png"),
                           "last_file": ("", b"", "application/octet-stream")})

    assert r.status_code == 422
    assert "last_file" in r.text
