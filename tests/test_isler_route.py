"""Üretim rotaları 202 döner, iş uçları (`/api/isler`) ve eş zamanlılık kapısı (Faz 2 / 4).

docs/faz2-kuyruk-anahtarlar-depolama.md §4'ün rota tarafı. Sağlayıcı YAMALI
(`providers.*`), kuyruk GERÇEK Postgres (`depo_db`), depo yerel disk
(`uret_ve_bitir` `data_dir`i `tmp_path`e çeker). Beş soru:

  (i)   202 GÖVDESİ — `{"is": kuyruk._json}`: durum `bekliyor`, tür, model
        (bayat sunucu yankısı), `kredi_tahmini = cost_for × n`; `istek` DÖKÜLMEZ.
  (ii)  DOĞRULAMA AYNEN — 422/413/404 aynı kodlarla ve kuyruğa İŞ YAZMAZ,
        depoya NESNE bırakmaz; sağlayıcı çağrısı rotada YOK (kaynak taraması).
  (iii) GİRDİ NESNELERİ — `kullanicilar/<uuid>/isler/<is_id>/<ad>` altında,
        `istek.girdiler` sözleşmesiyle; iş bitince SİLİNMEZ (§3 kararı (g)).
  (iv)  İŞ UÇLARI — liste (aktifler + son 50, `since`), tekil, iptal (yalnız
        `bekliyor`; 409), başkasının işi 404, biçimsiz id 422.
  (v)   EŞ ZAMANLILIK — 5. aktif iş 429 + `Retry-After: 30` + i18n gövde;
        arena 4 sütun geçer; tavan ortamdan; bitmiş iş sayılmaz.

Artı bir ölçüm: yamalı sağlayıcıyla `POST /api/generate` gecikmesi (çıkış
ölçütü 50 ms; iddia CI gürültüsüne pay bırakır, değer belgeye yazılır).

Faz 2 / 5 iki soru daha ekledi (belge §5):

  (vi)  SSE AKIŞI `GET /api/isler/akis` — ilk turda aktif işler, sonra yalnız
        DEĞİŞENLER; `?since=` ve `Last-Event-ID` aynı yerden sürer; `: kalp`
        yorumu; azami ömürde akış kendini kapatır; yalnız sahibin işleri;
        `no-store` + `X-Accel-Buffering: no`. Zamanlar modül sabiti, testler
        saniyenin altına çeker (`TestClient.stream` ile satır satır okunur).
  (vii) YENİDEN GÖNDER `POST /api/isler/{id}/yeniden` — `hata`/`iptal` iş →
        aynı `istek`le yeni `bekliyor` iş (202), girdi nesneleri REFERANS
        (kopya yok), `arena_id` düşer; aktif/bitmiş iş 409, başkasının 404,
        tavan 429.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import app as appmod
import azure_client as ac
import catalog
import i18n
import providers
from routers import isler as isler_rotasi
from services import ayar, hesap, isci, kapilar, kimlik, kuyruk, tablolar

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(16))
MP4 = b"\x00\x00\x00\x20ftypmp42"
GORSEL = {"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1}
VIDEO = {"prompt": "kedi kosuyor", "size": "16:9", "quality": "720p", "duration": 4}


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def temiz(depo_db):
    """Dosya aynı DB'yi paylaşır; her test boş kuyrukla başlar (eş zamanlılık sayacı sıfırdan)."""
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM isler"))
    yield


def _cikti(tmp_path, kullanici) -> str:
    """Kullanıcının GERÇEK çıktı dizini (`kullanici_icin`): işçi buraya yazar."""
    return str(tmp_path / "kullanicilar" / str(kullanici.id) / "output")


@pytest.fixture
def c(tmp_path, monkeypatch, dizinler, kullanici):
    # `output_dir` kullanıcının gerçek dizinine: bu dosyada işçi GERÇEK `Ayarlar`
    # ile koşuyor (`_tek_tur`), rota ise `kullanici` override'ının paylaşılan
    # yerleşimini okuyor — ikisi aynı yeri göstersin ki galeri referansı bulunsun.
    dizinler(data_dir=str(tmp_path), output_dir=_cikti(tmp_path, kullanici))
    # Sahte sağlayıcı ADEDİ SAYAR (`[PNG] * n`): n=2 iki kayıt yazmalı.
    monkeypatch.setattr(providers, "generate", lambda m, p, s, q, n, **k: [PNG] * n)
    monkeypatch.setattr(providers, "edit", lambda m, p, r, s, q, n, **k: [PNG] * n)
    monkeypatch.setattr(providers, "generate_video", lambda *a, **k: [MP4])
    monkeypatch.setattr(providers, "animate_video", lambda *a, **k: [MP4])
    return TestClient(appmod.app)


def _isler(depo_db) -> list[tablolar.Is]:
    with Session(depo_db) as db:
        return list(db.scalars(select(tablolar.Is)))


def _girdi_dizini(tmp_path, kullanici_id, is_id) -> list[str]:
    kok = tmp_path / "kullanicilar" / str(kullanici_id) / "isler" / str(is_id)
    return sorted(p.name for p in kok.iterdir()) if kok.exists() else []


def _tek_tur(depo_db) -> bool:
    with Session(depo_db) as db:
        return isci.tek_tur(db, appmod.app.state.dosya, ayarlar=appmod.app.state.ayarlar)


# ── (i) 202 gövdesi ─────────────────────────────────────────────────────

def test_generate_answers_202_with_the_job_and_no_provider_call(c, monkeypatch):
    monkeypatch.setattr(providers, "generate", lambda *a, **k: pytest.fail("rota sağlayıcıyı çağırmaz"))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: pytest.fail("rota adaptörü de çağırmaz"))

    r = c.post("/api/generate", json={**GORSEL, "n": 3})

    assert r.status_code == 202, r.text
    is_ = r.json()["is"]
    assert is_["durum"] == "bekliyor" and is_["tur"] == "generate"
    assert is_["model"] == catalog.DEFAULT_IMAGE_MODEL, "bayat sunucu tespiti `is.model` yankısından"
    spec = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    assert is_["kredi_tahmini"] == catalog.cost_for(spec, "medium") * 3
    assert is_["sonuc"] is None and is_["hata"] is None and is_["basladi"] is None
    assert set(is_) == {"id", "tur", "durum", "model", "kredi_tahmini", "anahtar_kaynagi", "olusturuldu",
                        "basladi", "bitti", "sonuc", "hata", "arena_id", "folder_id"}, "`istek` (prompt, anahtarlar) dökülmez"
    assert is_["anahtar_kaynagi"] == "kullanici", "conftest'in anahtar kapısı yaması `kullanici` der (Faz 2 / 6)"
    assert is_["arena_id"] is None and is_["folder_id"] is None, (
        "`istek`ten dökülen iki alan: tur etiketi (panel gruplaması) ve klasör (önizleme)")
    assert "kedi" not in r.text


def test_video_answers_202_and_the_estimate_carries_the_duration_cost(c):
    """Öntanımlı video modeli tek videoluk (`max_n=1`): tahmin süreye göre maliyet × 1."""
    r = c.post("/api/video", json={**VIDEO, "duration": 8})

    assert r.status_code == 202, r.text
    is_ = r.json()["is"]
    assert is_["tur"] == "video" and is_["model"] == catalog.DEFAULT_VIDEO_MODEL
    spec = catalog.video_model(catalog.DEFAULT_VIDEO_MODEL)
    assert is_["kredi_tahmini"] == catalog.cost_for(spec, "720p", duration=8)
    assert is_["kredi_tahmini"] > catalog.cost_for(spec, "720p", duration=4)
    assert "videos" not in r.json(), "eski `{\"videos\": …}` anahtarı 202 gövdesinde yok"


def test_the_job_finishes_through_the_worker_and_the_media_shows_up_in_history(c, depo_db, tmp_path, kullanici):
    """Belgenin test deseni uçtan uca: POST 202 → `tek_tur` → `bitti` + `sonuc.medya` → `GET /api/history`."""
    is_id = c.post("/api/generate", json={**GORSEL, "n": 2}).json()["is"]["id"]
    assert c.get("/api/history").json()["images"] == [], "sıraya girmek medya yazmaz"

    assert _tek_tur(depo_db)

    is_ = c.get(f"/api/isler/{is_id}").json()["is"]
    assert is_["durum"] == "bitti" and is_["basladi"] and is_["bitti"]
    assert len(is_["sonuc"]["medya"]) == 2
    gorunen = c.get("/api/history").json()["images"]
    assert sorted(g["id"] for g in gorunen) == sorted(is_["sonuc"]["medya"])
    assert all(g["prompt"] == "kedi" and g["model"] == catalog.DEFAULT_IMAGE_MODEL for g in gorunen)
    for g in gorunen:
        assert os.path.isfile(os.path.join(_cikti(tmp_path, kullanici), g["filename"]))


def test_a_provider_error_is_the_jobs_hata_not_a_502_at_the_route(c, depo_db, monkeypatch):
    """Eski `test_generate_maps_azure_error`in yeni yüzü: rota 202, hata işin sütununda, metin aynen."""
    def boom(*a, **k):
        raise ac.AzureImageError("Azure isteği başarısız (HTTP 429).")
    monkeypatch.setattr(providers, "generate", boom)

    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 202
    assert _tek_tur(depo_db)
    is_ = c.get(f"/api/isler/{r.json()['is']['id']}").json()["is"]

    assert is_["durum"] == "hata" and "429" in is_["hata"]
    assert c.get("/api/history").json()["images"] == []


# ── (ii) doğrulama aynen, iş yok ────────────────────────────────────────

@pytest.mark.parametrize("yol, istek, beklenen", [
    ("/api/generate", {"json": {**GORSEL, "size": "99x99"}}, 422),
    ("/api/generate", {"json": {**GORSEL, "session_id": "../../etc/passwd"}}, 422),
    ("/api/generate", {"json": {**GORSEL, "folder_id": "yok-boyle-klasor"}}, 404),
    ("/api/generate", {"json": {**GORSEL, "bilinmeyen": 1}}, 422),
    ("/api/video", {"json": {**VIDEO, "palette_hex": "#ff0000"}}, 422),
    ("/api/edit", {"data": {"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"}}, 422),
    ("/api/edit", {"data": {"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1",
                            "source_id": "yokyokyokyok"}}, 404),
    ("/api/edit", {"data": {"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
                   "files": {"file": ("a.png", b"bu png degil", "image/png")}}, 422),
    ("/api/video/animate", {"data": {**VIDEO, "source_id": "yokyokyokyok"}}, 404),
    ("/api/video/animate", {"data": VIDEO}, 422),
])
def test_validation_keeps_its_codes_and_writes_no_job_and_no_object(c, depo_db, tmp_path, yol, istek, beklenen):
    r = c.post(yol, **istek)

    assert r.status_code == beklenen, r.text
    assert _isler(depo_db) == [], "doğrulamadan düşen istek kuyruğa yazmaz"
    assert not (tmp_path / "kullanicilar").exists() or not any(
        (tmp_path / "kullanicilar").rglob("isler/*/*")), "düşen istek depoya nesne bırakmaz"


def test_an_oversized_upload_is_413_and_writes_nothing(c, depo_db):
    r = c.post("/api/edit", data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
               files={"file": ("a.png", _png(), "image/png")},
               headers={"content-length": str(60 * 1024 * 1024)})
    assert r.status_code == 413
    assert _isler(depo_db) == []


def test_the_production_routes_no_longer_import_the_provider_or_the_adapters():
    """Çıkış ölçütü "sağlayıcı çağrısı yalnız işçide"nin kaynak bekçisi: rota dosyası ne
    `providers`ı ne bir adaptörü ithal eder — çağrı kazara geri gelse önce burası kızarır."""
    with open(os.path.join(REPO, "routers", "uretim.py"), encoding="utf-8") as f:
        kaynak = f.read()
    ithaller = re.findall(r"^(?:import|from)\s+([\w.]+)", kaynak, re.M)
    assert "providers" not in ithaller and "azure_client" not in ithaller, ithaller
    assert not re.search(r"depo_medya\.kaydet\(", kaynak), "medya satırını işçi yazar"


# ── (iii) girdi nesneleri ───────────────────────────────────────────────

def test_edit_writes_the_references_under_the_jobs_prefix_in_adapter_order(c, depo_db, tmp_path, kullanici):
    r = c.post("/api/edit",
               data={"prompt": "mavi yap", "size": "1024x1024", "quality": "low", "n": "1"},
               files=[("file", ("in.png", _png(), "image/png")),
                      ("extra_files", ("ek.png", _png(), "image/png"))])

    assert r.status_code == 202, r.text
    is_id = r.json()["is"]["id"]
    assert _girdi_dizini(tmp_path, kullanici.id, is_id) == ["ref2.png", "upload.png"]
    (satir,) = _isler(depo_db)
    assert satir.istek["girdiler"] == [
        {"ad": "upload.png", "anahtar": f"kullanicilar/{kullanici.id}/isler/{is_id}/upload.png"},
        {"ad": "ref2.png", "anahtar": f"kullanicilar/{kullanici.id}/isler/{is_id}/ref2.png"},
    ], "sıra sözleşme: ana görsel → ek yüklemeler → ek galeri görselleri"
    assert satir.istek["parent_id"] is None and satir.istek["prompt_sent"] == "mavi yap"


def test_animate_writes_the_first_frame_and_the_last_frame_separately(c, depo_db, tmp_path, kullanici):
    r = c.post("/api/video/animate", data=VIDEO,
               files=[("file", ("ilk.png", _png(), "image/png")),
                      ("last_file", ("son.png", _png(), "image/png"))])

    assert r.status_code == 202, r.text
    is_id = r.json()["is"]["id"]
    assert _girdi_dizini(tmp_path, kullanici.id, is_id) == ["son_kare.png", "upload.png"]
    (satir,) = _isler(depo_db)
    assert [g["ad"] for g in satir.istek["girdiler"]] == ["upload.png"], "son kare `girdiler`e katılmaz"
    assert satir.istek["son_kare"] == {"ad": "son_kare.png",
                                       "anahtar": f"kullanicilar/{kullanici.id}/isler/{is_id}/son_kare.png"}
    assert satir.istek["duration"] == 4 and satir.tur == "animate"


def test_the_inputs_survive_the_job_by_decision_g(c, depo_db, tmp_path, kullanici):
    """§3 kararı (g), belge §4'ün "iş bitince silinir" satırından bilinçli sapma: girdi
    nesneleri işten sonra da durur — "yeniden gönder" (5) onları kullanır, saklama (10)
    ve `tools/artik_dosya.py` (`isler/` öneki) siler. Sonuç işçiden çıkar."""
    r = c.post("/api/edit", data={"prompt": "mavi", "size": "1024x1024", "quality": "low", "n": "1"},
               files={"file": ("in.png", _png(), "image/png")})
    is_id = r.json()["is"]["id"]

    assert _tek_tur(depo_db)

    is_ = c.get(f"/api/isler/{is_id}").json()["is"]
    assert is_["durum"] == "bitti", is_
    assert _girdi_dizini(tmp_path, kullanici.id, is_id) == ["upload.png"]
    assert len(c.get("/api/history").json()["images"]) == 1


def test_a_gallery_reference_records_the_parent_and_is_copied_into_the_jobs_prefix(c, depo_db, tmp_path, kullanici):
    """Galeriden seçilen kaynak `parent_id` olur (türev zinciri) ve bayt kopyası işe yazılır —
    kaynak silinse iş yine koşar (`istek`in "sonradan silinen … işi değiştirmez" sözü)."""
    ilk = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    assert _tek_tur(depo_db)
    kaynak = c.get(f"/api/isler/{ilk}").json()["is"]["sonuc"]["medya"][0]

    r = c.post("/api/edit", data={"prompt": "mavi", "size": "1024x1024", "quality": "low", "n": "1",
                                  "source_id": kaynak})
    assert r.status_code == 202, r.text
    is_id = r.json()["is"]["id"]
    satir = next(s for s in _isler(depo_db) if str(s.id) == is_id)
    assert satir.istek["parent_id"] == kaynak
    assert satir.istek["girdiler"][0]["ad"] == f"{kaynak}.png"
    assert _girdi_dizini(tmp_path, kullanici.id, is_id) == [f"{kaynak}.png"]


# ── (iv) iş uçları ──────────────────────────────────────────────────────

def test_the_list_is_newest_first_and_carries_the_same_shape_as_the_202_body(c):
    a = c.post("/api/generate", json=GORSEL).json()["is"]
    b = c.post("/api/video", json=VIDEO).json()["is"]

    r = c.get("/api/isler")

    assert r.status_code == 200
    assert [i["id"] for i in r.json()["isler"]] == [b["id"], a["id"]]
    assert r.json()["isler"][1] == a


def test_the_default_list_is_the_active_jobs_plus_the_last_fifty(c, depo_db, kullanici):
    """51. sıraya düşmüş bir `bekliyor` iş listeden kaybolmasın: aktifler AYRI çekilir."""
    eski_an = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    with Session(depo_db) as db:
        for i in range(60):
            is_ = kuyruk.ekle(db, kullanici.id, "generate", {"prompt": f"p{i}"}, "m", 1,
                              an=eski_an + dt.timedelta(minutes=i + 1))
            kuyruk.al(db, uuid.uuid4(), eski_an + dt.timedelta(hours=2))  # kuyruğun başı = bu iş
            kuyruk.bitir(db, is_.id, {"medya": []}, eski_an + dt.timedelta(hours=3))
        # 60 bitmiş işten de ESKİ bir `bekliyor`: son 50'ye girmez, aktif diye gelmeli.
        eski_aktif = kuyruk.ekle(db, kullanici.id, "generate", {"prompt": "eski"}, "m", 1, an=eski_an)
        eski_aktif_id = str(eski_aktif.id)
        db.commit()

    isler = c.get("/api/isler").json()["isler"]

    assert len(isler) == 51
    assert isler[-1]["id"] == eski_aktif_id and isler[-1]["durum"] == "bekliyor"
    assert all(isler[i]["olusturuldu"] >= isler[i + 1]["olusturuldu"] for i in range(len(isler) - 1))


def test_since_returns_only_what_changed_after_that_moment(c, depo_db):
    a = c.post("/api/generate", json=GORSEL).json()["is"]
    time.sleep(1.1)   # `since` saniye çözünürlüğünde (`zaman.damga`), sınır kesin olsun
    sinir = dt.datetime.now(dt.UTC).astimezone()
    time.sleep(0.05)
    b = c.post("/api/generate", json=GORSEL).json()["is"]

    sonra = c.get("/api/isler", params={"since": sinir.isoformat()}).json()["isler"]
    assert [i["id"] for i in sonra] == [b["id"]]

    # A çalışınca (basladi) yeniden "değişen" olur.
    assert _tek_tur(depo_db)
    sonra = c.get("/api/isler", params={"since": sinir.isoformat()}).json()["isler"]
    assert {i["id"] for i in sonra} == {a["id"], b["id"]}
    assert c.get("/api/isler", params={"since": "dun-aksam"}).status_code == 422


def test_a_single_job_is_readable_by_its_owner_only(c, depo_db, kullanici):
    is_id = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    with Session(depo_db) as db:
        baska = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                                   dogrulandi_at=hesap.simdi(), dil=None)
        db.add(baska)
        db.flush()
        baskasinin = kuyruk.ekle(db, baska.id, "generate", {"prompt": "gizli"}, "m", 1)
        baskasinin_id = str(baskasinin.id)
        db.commit()

    assert c.get(f"/api/isler/{is_id}").json()["is"]["id"] == is_id
    assert c.get(f"/api/isler/{baskasinin_id}").status_code == 404, "başkasının işi yok sayılır (403 değil)"
    assert c.get(f"/api/isler/{uuid.uuid4()}").status_code == 404
    assert c.get("/api/isler/bu-uuid-degil").status_code == 422
    assert c.post(f"/api/isler/{baskasinin_id}/iptal").status_code == 404
    assert [i["id"] for i in c.get("/api/isler").json()["isler"]] == [is_id], "liste de sahip süzgeçli"


def test_cancelling_a_waiting_job_takes_it_out_of_the_queue(c, depo_db, monkeypatch):
    monkeypatch.setattr(providers, "generate", lambda *a, **k: pytest.fail("iptal edilen iş koşmaz"))
    is_id = c.post("/api/generate", json=GORSEL).json()["is"]["id"]

    r = c.post(f"/api/isler/{is_id}/iptal")

    assert r.status_code == 200, r.text
    assert r.json()["is"]["durum"] == "iptal" and r.json()["is"]["bitti"]
    assert _tek_tur(depo_db) is False, "işçi iptal edilen işi almaz"
    assert c.post(f"/api/isler/{is_id}/iptal").status_code == 409, "ikinci iptal 409: artık bekliyor değil"


def test_a_running_or_finished_job_cannot_be_cancelled(c, depo_db, kullanici):
    calisan = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    with Session(depo_db) as db:
        assert kuyruk.al(db, uuid.uuid4(), dt.datetime.now(dt.UTC)) is not None
        db.commit()
    r = c.post(f"/api/isler/{calisan}/iptal")
    assert r.status_code == 409, r.text
    assert "calisiyor" in r.json()["detail"]

    biten = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    assert _tek_tur(depo_db)
    assert c.post(f"/api/isler/{biten}/iptal").status_code == 409
    assert c.get(f"/api/isler/{biten}").json()["is"]["durum"] == "bitti", "409 durumu değiştirmez"


# ── (v) eş zamanlılık ───────────────────────────────────────────────────

def test_the_fifth_active_job_is_429_with_retry_after_and_an_i18n_body(c, depo_db, tmp_path):
    for _ in range(kapilar.ES_ZAMANLI_IS_VARSAYILAN):
        assert c.post("/api/generate", json=GORSEL).status_code == 202

    r = c.post("/api/generate", json=GORSEL)

    assert r.status_code == 429, r.text
    assert r.headers["Retry-After"] == str(kapilar.RETRY_AFTER_SN) == "30"
    # Gövde i18n: test kullanıcısının dili yok, cümle isteğin dilinde (dil zinciri) — iki
    # dilden biri, anahtarın kendisi değil ve tavanı söylüyor.
    assert r.json()["detail"] in {i18n.t("err.is_kuyrugu_dolu", d, tavan=4) for d in ("tr", "en")}
    assert "4" in r.json()["detail"] and r.json()["detail"] != "err.is_kuyrugu_dolu"
    assert len(_isler(depo_db)) == 4, "429 kuyruğa yazmaz"

    # Çalışan iş de sayılır; biten sayılmaz.
    assert c.post("/api/edit", data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
                  files={"file": ("a.png", _png(), "image/png")}).status_code == 429
    assert not any((tmp_path / "kullanicilar").rglob("isler/*/*")), "429 depoya nesne bırakmaz"
    assert _tek_tur(depo_db)
    assert c.post("/api/generate", json=GORSEL).status_code == 202


def test_an_arena_round_of_four_columns_passes_the_gate(c):
    """Tavanın 4 olma sebebi: arena turu istemcide 2-4 ayrı istek; dördüncü sütun 429 yese
    tur "3/4" biterdi."""
    arena = "aaaa1111bbbb"
    cevaplar = [c.post("/api/generate", json={**GORSEL, "arena_id": arena}) for _ in range(4)]
    assert [r.status_code for r in cevaplar] == [202] * 4
    assert len({r.json()["is"]["id"] for r in cevaplar}) == 4


def test_the_cap_comes_from_the_environment_and_a_bad_value_is_loud(c, monkeypatch):
    monkeypatch.setenv(kapilar.ES_ZAMANLI_IS_ENV, "1")
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    r = c.post("/api/video", json=VIDEO)
    assert r.status_code == 429 and "1" in r.json()["detail"]

    assert kapilar.es_zamanli_is_tavani({}) == 4
    assert kapilar.es_zamanli_is_tavani({kapilar.ES_ZAMANLI_IS_ENV: " 7 "}) == 7
    with pytest.raises(ValueError):
        kapilar.es_zamanli_is_tavani({kapilar.ES_ZAMANLI_IS_ENV: "cok"})
    with pytest.raises(ValueError):
        kapilar.es_zamanli_is_tavani({kapilar.ES_ZAMANLI_IS_ENV: "0"})


def test_the_gate_counts_only_this_users_jobs(c, depo_db):
    """Sayaç kullanıcı başına: başkasının dolu kuyruğu beni 429'a düşürmez."""
    with Session(depo_db) as db:
        baska = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                                   dogrulandi_at=hesap.simdi(), dil=None)
        db.add(baska)
        db.flush()
        for _ in range(6):
            kuyruk.ekle(db, baska.id, "generate", {"prompt": "x"}, "m", 1)
        db.commit()
    assert c.post("/api/generate", json=GORSEL).status_code == 202


# ── ölçüm ───────────────────────────────────────────────────────────────

def test_post_generate_answers_within_the_latency_budget(c, depo_db):
    """Çıkış ölçütü: yamalı sağlayıcıyla `POST /api/generate` 50 ms altında 202.

    Ölçüm ORTANCA (20 istek), iddia 250 ms: CI koşucusu bu makineden yavaş ve
    Postgres aynı konteynerde; ölçülen değer belgede (§4 "Yapıldığında").
    Sağlayıcı yaması bile çağrılmıyor — rota gerçekten kuyruğa yazıp dönüyor.
    """
    sureler = []
    for _ in range(20):
        with depo_db.begin() as k:
            k.execute(text("DELETE FROM isler"))     # tavan (4) araya girmesin
        t0 = time.perf_counter()
        r = c.post("/api/generate", json=GORSEL)
        sureler.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 202
    sureler.sort()
    ortanca = sureler[len(sureler) // 2]
    print(f"\nPOST /api/generate gecikme: ortanca {ortanca:.1f} ms, en iyi {sureler[0]:.1f} ms, "
          f"en kotu {sureler[-1]:.1f} ms")
    assert ortanca < 250, f"ortanca {ortanca:.1f} ms"


def test_the_worker_writes_into_the_users_own_directory_when_given_the_real_layout(c, depo_db, tmp_path, kullanici):
    """`uret_ve_bitir`in paylaşılan yerleşimi bir test kolaylığı; gerçek `Ayarlar` ile işçi
    `kullanicilar/<uuid>/output`a yazar — E2E işçisinin (`IsciThread`) yolu bu."""
    c.post("/api/generate", json=GORSEL)
    assert _tek_tur(depo_db)
    ozel = ayar.Ayarlar.kullanici_icin(appmod.app.state.ayarlar, kullanici.id)
    assert ozel.output_dir == str(tmp_path / "kullanicilar" / str(kullanici.id) / "output")
    assert len(os.listdir(ozel.output_dir)) == 1


def test_the_finish_stamp_is_taken_when_the_job_finishes_not_when_it_starts(c, depo_db, monkeypatch):
    """ÖLÇÜLEN KUSUR (Faz 2 / 5 E2E): işçi `bitti`ye işin BAŞINDA aldığı anı yazıyordu; akışın
    `since` sorgusu (`GREATEST(olusturuldu, basladi, bitti)`) bitişi hiç görmüyor, panel
    `calisiyor`da donuyordu. Sağlayıcı 0,4 sn uyur; `bitti - basladi` en az o kadar."""
    def uyuyan(*a, **k):
        time.sleep(0.4)
        return [PNG]
    monkeypatch.setattr(providers, "generate", uyuyan)
    is_id = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    assert _tek_tur(depo_db)
    satir = next(s for s in _isler(depo_db) if str(s.id) == is_id)
    assert satir.durum == "bitti"
    assert (satir.bitti - satir.basladi).total_seconds() >= 0.35, (satir.basladi, satir.bitti)


# ── (vi) SSE akışı ──────────────────────────────────────────────────────

def _akis_hizli(monkeypatch, *, kalp: float = 60.0, azami: float = 3.0, ortusme: float = 0.0):
    """Akışın zamanlarını test ölçeğine çeker: sorgu 0,05 sn, ömür `azami` (akış KENDİ kapanır —
    TestClient'ta açık bir akışı dışarıdan kesmek portalda asılı kalabilir)."""
    monkeypatch.setattr(isler_rotasi, "AKIS_YOKLAMA_SN", 0.05)
    monkeypatch.setattr(isler_rotasi, "AKIS_KALP_SN", kalp)
    monkeypatch.setattr(isler_rotasi, "AKIS_AZAMI_SN", azami)
    monkeypatch.setattr(isler_rotasi, "AKIS_ORTUSME_SN", ortusme)


def _olaylar(satirlar) -> list[dict]:
    """SSE metnindeki `event: is` olaylarının `data` gövdeleri, sırayla."""
    olaylar: list[dict] = []
    olay: dict[str, str] = {}
    for satir in satirlar:
        if satir == "":
            if olay.get("event") == "is":
                olaylar.append({**json.loads(olay["data"]), "_id": olay.get("id")})
            olay = {}
        elif ":" in satir and not satir.startswith(":"):
            alan, deger = satir.split(":", 1)
            olay[alan] = deger.strip()
    return olaylar


class _AkisOkuyucu(threading.Thread):
    """Akışı AYRI iş parçacığında okur: `TestClient` gövdeyi portalda SONUNA KADAR toplayıp
    öyle döndürüyor (starlette.testclient `BytesIO`), yani akış açıkken test gövdesinden
    araya girmenin tek yolu isteği başka bir iş parçacığına vermek. Uygulama portalda
    koşarken ana iş parçacığı işçiyi çalıştırır, sonra `join` ile satırları alır."""

    def __init__(self, c: TestClient, **istek):
        super().__init__(daemon=True)
        self.c, self.istek = c, istek
        self.basliklar: dict = {}
        self.durum = 0
        self.satirlar: list[str] = []

    def run(self):
        with self.c.stream("GET", "/api/isler/akis", **self.istek) as r:
            self.durum = r.status_code
            self.basliklar = dict(r.headers)
            self.satirlar = list(r.iter_lines())


def test_the_stream_sends_the_active_jobs_first_and_then_every_change(c, depo_db, monkeypatch):
    """İlk tur aktifler (geçmişi istemci listeden aldı), sonra yalnız değişenler;
    aynı hâl ikinci kez YAZILMAZ; başlıklar vekil tamponunu kapatıyor."""
    _akis_hizli(monkeypatch, azami=1.5)
    is_id = c.post("/api/generate", json=GORSEL).json()["is"]["id"]

    okuyucu = _AkisOkuyucu(c)
    okuyucu.start()
    time.sleep(0.4)                 # ilk tur (bekliyor) yazıldı, döngü uyuyor
    assert _tek_tur(depo_db)        # akış AÇIKKEN işçi işi bitirir
    okuyucu.join(timeout=10)
    assert not okuyucu.is_alive(), "akış azami ömürde kapanmadı"

    assert okuyucu.durum == 200
    assert okuyucu.basliklar["content-type"].startswith("text/event-stream")
    assert okuyucu.basliklar["cache-control"] == "no-store"
    assert okuyucu.basliklar["x-accel-buffering"] == "no"
    assert okuyucu.satirlar[0] == "retry: 100", "yeniden bağlanma ipucu ilk satır: başlıklar hemen gitsin"
    olaylar = _olaylar(okuyucu.satirlar)
    assert [o["id"] for o in olaylar] == [is_id, is_id], "bekliyor → bitti: iki hâl, ikisi de tek kez"
    assert [o["durum"] for o in olaylar] == ["bekliyor", "bitti"]
    assert olaylar[1]["sonuc"]["medya"] and olaylar[1]["basladi"] and olaylar[1]["bitti"]
    assert all(o["_id"] for o in olaylar), "her olayın `id:`si var (Last-Event-ID buradan)"
    assert olaylar[0]["_id"] < olaylar[1]["_id"], "id sorgu anı: artan"


def test_since_and_last_event_id_resume_the_stream_from_that_moment(c, monkeypatch):
    _akis_hizli(monkeypatch, azami=0.3)
    a = c.post("/api/generate", json=GORSEL).json()["is"]
    time.sleep(1.1)   # `since` karşılaştırması damga çözünürlüğünde kesin olsun
    sinir = dt.datetime.now(dt.UTC).astimezone().isoformat()
    time.sleep(0.05)
    b = c.post("/api/generate", json=GORSEL).json()["is"]

    with c.stream("GET", "/api/isler/akis", params={"since": sinir}) as r:
        olaylar = _olaylar(r.iter_lines())
    assert [o["id"] for o in olaylar] == [b["id"]], "`since` yalnız sonrasını verir (a değil)"

    with c.stream("GET", "/api/isler/akis", headers={"Last-Event-ID": sinir}) as r:
        olaylar = _olaylar(r.iter_lines())
    assert [o["id"] for o in olaylar] == [b["id"]], "tarayıcının yeniden bağlanışı aynı yerden sürer"

    # Başlık `?since=`in ÖNÜNDE: ikisi birden gelirse tarayıcının bildiği an kazanır.
    with c.stream("GET", "/api/isler/akis", params={"since": "2000-01-01T00:00:00"},
                  headers={"Last-Event-ID": sinir}) as r:
        olaylar = _olaylar(r.iter_lines())
    assert [o["id"] for o in olaylar] == [b["id"]]
    assert a["id"] not in {o["id"] for o in olaylar}

    r = c.get("/api/isler/akis", params={"since": "dun"})
    assert r.status_code == 422, "bozuk `since` 422 (listeyle aynı kural)"


def test_the_stream_writes_a_heartbeat_comment_and_closes_itself_at_max_age(c, monkeypatch):
    """Vekiller boş bağlantıyı kesiyor → `: kalp`; uzun ömürlü bağlantı sızmasın → akış kendi kapanır."""
    _akis_hizli(monkeypatch, kalp=0.05, azami=0.4)
    t0 = time.perf_counter()
    with c.stream("GET", "/api/isler/akis") as r:
        satirlar = list(r.iter_lines())
    gecen = time.perf_counter() - t0
    assert ": kalp" in satirlar
    assert not _olaylar(satirlar), "iş yokken olay yok, yalnız kalp"
    assert 0.4 <= gecen < 3.0, f"akış azami ömürde kapanmadı: {gecen:.2f} sn"


def test_the_stream_carries_only_the_owners_jobs(c, depo_db, monkeypatch):
    _akis_hizli(monkeypatch, azami=0.3)
    benim = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    with Session(depo_db) as db:
        baska = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                                   dogrulandi_at=hesap.simdi(), dil=None)
        db.add(baska)
        db.flush()
        kuyruk.ekle(db, baska.id, "generate", {"prompt": "gizli"}, "m", 1)
        db.commit()

    with c.stream("GET", "/api/isler/akis") as r:
        olaylar = _olaylar(r.iter_lines())
    assert [o["id"] for o in olaylar] == [benim]
    assert "gizli" not in json.dumps(olaylar)


def test_the_stream_route_is_gated_reads_no_directory_and_holds_no_connection_while_streaming(
        c, depo_db, monkeypatch):
    """Kapı `aktif_kullanici` (401 sözleşmesi tests/test_kimlik.py'de her rota için ölçülüyor);
    `ayar.ayarlar` yok (`DIZINSIZ_KAPILI`). Havuz: akış AÇIKKEN isteğin bağlantısı havuza
    dönmüş olmalı (`pool_size=2`) — turlar arasında `checkedout() == 0`, tests/test_isci.py'nin
    "sağlayıcı çağrısında bağlantı yok" ölçümünün ikizi."""
    from services import ayar
    (rota,) = [r for r in isler_rotasi.router.routes if getattr(r, "path", "") == "/api/isler/akis"]
    cagrilar = {alt.call for alt in rota.dependant.dependencies}
    assert kimlik.aktif_kullanici in cagrilar
    assert ayar.ayarlar not in cagrilar

    _akis_hizli(monkeypatch, azami=1.0)
    c.post("/api/generate", json=GORSEL)
    okuyucu = _AkisOkuyucu(c)
    okuyucu.start()
    time.sleep(0.4)                 # akış açık, ilk tur yazılmış, döngü uykuda
    tutulan = depo_db.pool.checkedout()
    okuyucu.join(timeout=10)
    assert okuyucu.durum == 200 and _olaylar(okuyucu.satirlar)
    assert tutulan == 0, f"akış açıkken havuzdan tutulan bağlantı: {tutulan}"


# ── (vii) yeniden gönder ────────────────────────────────────────────────

def _hata_ver(monkeypatch):
    def boom(*a, **k):
        raise ac.AzureImageError("Azure isteği başarısız (HTTP 500).")
    monkeypatch.setattr(providers, "edit", boom)
    monkeypatch.setattr(providers, "generate", boom)


def test_a_failed_job_is_resubmitted_with_the_same_request_and_the_same_input_objects(
        c, depo_db, tmp_path, kullanici, monkeypatch):
    """Karar: girdi nesneleri KOPYALANMAZ — yeni iş eski `isler/<id>/` anahtarlarına referans verir."""
    _hata_ver(monkeypatch)
    r = c.post("/api/edit", data={"prompt": "mavi", "size": "1024x1024", "quality": "low", "n": "1"},
               files={"file": ("in.png", _png(), "image/png")})
    eski_id = r.json()["is"]["id"]
    assert _tek_tur(depo_db)
    assert c.get(f"/api/isler/{eski_id}").json()["is"]["durum"] == "hata"

    r = c.post(f"/api/isler/{eski_id}/yeniden")

    assert r.status_code == 202, r.text
    yeni = r.json()["is"]
    assert yeni["id"] != eski_id and yeni["durum"] == "bekliyor" and yeni["tur"] == "edit"
    assert yeni["model"] == c.get(f"/api/isler/{eski_id}").json()["is"]["model"]
    satirlar = {str(s.id): s for s in _isler(depo_db)}
    assert satirlar[yeni["id"]].istek == satirlar[eski_id].istek, "aynı `istek`, prompt dâhil"
    assert satirlar[yeni["id"]].istek["girdiler"][0]["anahtar"].endswith(f"isler/{eski_id}/upload.png")
    assert _girdi_dizini(tmp_path, kullanici.id, yeni["id"]) == [], "yeni işin kendi dizini yok: referans"
    assert satirlar[yeni["id"]].kredi_tahmini == satirlar[eski_id].kredi_tahmini
    assert "mavi" not in r.text, "`istek` 202 gövdesinde de dökülmez"

    # Sağlayıcı düzelince yeni iş eski girdiyle koşar ve biter.
    monkeypatch.setattr(providers, "edit", lambda m, p, r, s, q, n, **k: [PNG] * n)
    assert _tek_tur(depo_db)
    assert c.get(f"/api/isler/{yeni['id']}").json()["is"]["durum"] == "bitti"
    assert len(c.get("/api/history").json()["images"]) == 1


def test_a_cancelled_job_can_be_resubmitted_but_an_active_or_finished_one_cannot(c, depo_db):
    iptal = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    assert c.post(f"/api/isler/{iptal}/iptal").status_code == 200
    assert c.post(f"/api/isler/{iptal}/yeniden").status_code == 202

    bekleyen = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    r = c.post(f"/api/isler/{bekleyen}/yeniden")
    assert r.status_code == 409 and "bekliyor" in r.json()["detail"]

    with Session(depo_db) as db:
        for _ in range(2):        # iki bekleyen: yeniden gönderilmiş + bekleyen
            assert kuyruk.al(db, uuid.uuid4(), dt.datetime.now(dt.UTC)) is not None
        db.commit()
    assert c.post(f"/api/isler/{bekleyen}/yeniden").status_code == 409, "çalışan iş de 409"

    biten = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    assert _tek_tur(depo_db)
    assert c.get(f"/api/isler/{biten}").json()["is"]["durum"] == "bitti"
    assert c.post(f"/api/isler/{biten}/yeniden").status_code == 409, "bitmiş iş: sonuç galeride, çift fatura yok"
    assert c.post(f"/api/isler/{uuid.uuid4()}/yeniden").status_code == 404
    assert c.post("/api/isler/bu-uuid-degil/yeniden").status_code == 422


def test_resubmitting_someone_elses_job_is_404(c, depo_db):
    with Session(depo_db) as db:
        baska = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                                   dogrulandi_at=hesap.simdi(), dil=None)
        db.add(baska)
        db.flush()
        is_ = kuyruk.ekle(db, baska.id, "generate", {"prompt": "gizli"}, "m", 1)
        kuyruk.iptal(db, baska.id, is_.id)
        baskasinin = str(is_.id)
        db.commit()
    assert c.post(f"/api/isler/{baskasinin}/yeniden").status_code == 404
    assert len(_isler(depo_db)) == 1, "404 satır doğurmaz"


def test_resubmit_counts_against_the_concurrency_cap(c, depo_db, monkeypatch):
    _hata_ver(monkeypatch)
    dusen = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    assert _tek_tur(depo_db)
    for _ in range(kapilar.ES_ZAMANLI_IS_VARSAYILAN):
        assert c.post("/api/generate", json=GORSEL).status_code == 202

    r = c.post(f"/api/isler/{dusen}/yeniden")

    assert r.status_code == 429 and r.headers["Retry-After"] == str(kapilar.RETRY_AFTER_SN)
    assert len(_isler(depo_db)) == 5, "429 satır doğurmaz"


def test_resubmit_drops_the_arena_id_because_the_round_is_over(c, depo_db, monkeypatch):
    _hata_ver(monkeypatch)
    arena = "aaaa1111bbbb"
    is_ = c.post("/api/generate", json={**GORSEL, "arena_id": arena}).json()["is"]
    assert is_["arena_id"] == arena, "`_json` turun etiketini taşır (panel gruplaması)"
    assert _tek_tur(depo_db)

    yeni = c.post(f"/api/isler/{is_['id']}/yeniden").json()["is"]

    assert yeni["arena_id"] is None
    satir = next(s for s in _isler(depo_db) if str(s.id) == yeni["id"])
    assert satir.istek["arena_id"] is None and satir.istek["prompt"] == "kedi"


# ── Faz 2 / 6: panelin `hata` kodları eşlemesi ─────────────────────────

def test_the_panel_maps_every_hata_code_the_server_writes():
    """`hata` sütununa yazılan üç KOD (cümle değil) panelde i18n cümlesine çevrilir; isler.js
    kodları HARFİYEN taşımak zorunda — Python sabiti değişir de betik değişmezse kullanıcı
    ham kodu görür. Sabitler kaynaktan, betik metinden okunuyor."""
    with open(os.path.join(REPO, "static", "isler.js"), encoding="utf-8") as f:
        betik = f.read()
    for kod, anahtar in ((kuyruk.BAYAT_HATASI, "isler.hata_bayat"),
                         (isci.BEKLENMEYEN_HATASI, "isler.hata_beklenmeyen"),
                         (isci.KULLANICI_YOK_HATASI, "isler.hata_kullanici_yok")):
        assert f'["{kod}", "{anahtar}"]' in betik, (kod, anahtar)
    # İşçi beklenmeyen hatayı `KOD: TürAdı` yazar (services/isci.py); betik `:` ile ayırıyor.
    assert 'startsWith(kod + ":")' in betik
