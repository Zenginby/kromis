"""İşçi — `services/isci.py` (`tek_tur`/`kos`/`kalp_turu`) ve `isci.py` süreci (Faz 2 / 3. görev).

Hepsi GERÇEK Postgres'e karşı (`depo_db`), sağlayıcı YAMALI (`providers.*` →
sahte bayt; 104 rota testinin deyimi), depo yerel disk (`YerelDepo(tmp_path)`).
Belge §3'ün "testlerde işçi süreç DEĞİL işlev" kararı: süreç yok, port yok,
uyku yok — yalnız (v)'nin süreç testleri `isci.py`yi alt süreç olarak açar
(anahtarsız açılmaz, `--tek-tur` boş kuyrukta 0, SIGTERM temiz kapanış, boşaltma
sırasında kalp, silinen satırın yeniden yazılması), çünkü kapılar ve sinyal
ancak süreçte ölçülür; `Surec.calistir`ın iş parçacığı düzeni ise süreçsiz,
sahte `kos`la ölçülür (aynı bölüm).

Beş soru:

  (i)   DÖRT TÜR — generate/edit/video/animate `tek_tur` ile `bitti`: `medya`
        satırı + nesne + `sonuc.medya`; girdiler depodan sırayla okunur; kredi
        GERÇEK katalog (tahmin değil); `prompt_sent` rotanın hesabı.
  (ii)  TELAFİ — satır düşerse nesne silinir ve iş `hata`; `bitir` 0 satır
        görürse (bayat düşürülmüş) nesne silinir, iş diriltilmez; sıra nesne → satır.
  (iii) HATA — sağlayıcı hatası redakte `hata`, satır yok; beklenmeyen istisna
        KOD + `hata.log`; metin KULLANICININ dilinde; eksik girdi 404 metni.
  (iv)  BAĞLAM — kimlik iş başına bağlanır ve ÇÖZÜLÜR (`[A, B]`); dil sıfırlanır;
        sağlayıcı çağrısı sırasında havuzdan bağlantı tutulmaz; iki işçi iki iş;
        kalp ilerler ve bayatı düşürür; işçi satırı yokken kalp onu aynı kimlikle
        yeniden yazar; bakım turu başka kiracının dizinine dokunmaz.
  (v)   SÜREÇ — `isci.py` web'in kapılarını taşır; anahtarsız 2; `--tek-tur`
        boş kuyrukta 0, dolu kuyrukta işi koşturur; `isciler` satırı + kalp +
        SIGTERM → 0 ve satır silinir.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import importlib
import json
import logging
import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
import uuid

import pytest
from sqlalchemy import event, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

import azure_client as ac
import catalog
import i18n
import kimlik_baglami
import providers
from services import (
    ayar,
    db,
    depo_kimlik_bilgisi,
    depo_medya,
    dil,
    dosya,
    hesap,
    isci,
    kuyruk,
    tablolar,
    zaman,
)

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(16))
PNG2 = b"\x89PNG\r\n\x1a\n" + bytes(range(16, 32))
MP4 = b"\x00\x00\x00\x20ftypmp42" + bytes(8)
GORSEL = catalog.DEFAULT_IMAGE_MODEL
VIDEO = catalog.DEFAULT_VIDEO_MODEL
ESIK = dt.timedelta(minutes=5)
ISCI = uuid.uuid4()


@pytest.fixture(autouse=True)
def temiz(depo_db):
    """Dosyanın testleri aynı DB'yi paylaşır; her test boş kuyrukla ve boş `isciler`le başlar."""
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM isler"))
        c.execute(text("DELETE FROM isciler"))
    yield


@pytest.fixture
def yerlesim(tmp_path) -> ayar.Ayarlar:
    """`data_dir = tmp_path`: işçi kullanıcı dizinini `kullanici_icin` ile buradan türetir."""
    return dataclasses.replace(ayar.Ayarlar.varsayilan(), data_dir=str(tmp_path),
                               output_dir=os.path.join(str(tmp_path), "output"),
                               assets_dir=os.path.join(str(tmp_path), "assets"))


@pytest.fixture
def depo(tmp_path) -> dosya.YerelDepo:
    return dosya.YerelDepo(str(tmp_path))


def _an(saniye: float = 0.0) -> dt.datetime:
    return dt.datetime(2026, 9, 18, 12, 0, 0, tzinfo=dt.UTC) + dt.timedelta(seconds=saniye)


def _ekle(db: Session, kullanici_id: uuid.UUID, tur: str = "generate", istek: dict | None = None,
          model: str = GORSEL, kredi: int = 999) -> uuid.UUID:
    """`kredi_tahmini` bilerek 999: satıra yazılan kredi katalogtan gelmeli, buradan değil."""
    govde = {"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1,
             "folder_id": None, "session_id": None}
    govde.update(istek or {})
    is_ = kuyruk.ekle(db, kullanici_id, tur, govde, model, kredi, an=_an())
    db.commit()
    return is_.id


def _is(db: Session, is_id: uuid.UUID) -> tablolar.Is:
    db.expire_all()
    satir = db.get(tablolar.Is, is_id)
    assert satir is not None
    return satir


def _medya(db: Session, kullanici_id: uuid.UUID) -> list[tablolar.Medya]:
    db.expire_all()
    return list(db.scalars(select(tablolar.Medya).where(tablolar.Medya.kullanici_id == kullanici_id)
                           .order_by(tablolar.Medya.olusturuldu)))


def _nesneler(tmp_path, kullanici_id: uuid.UUID) -> list[str]:
    kok = tmp_path / "kullanicilar" / str(kullanici_id) / "output"
    return sorted(p.name for p in kok.iterdir()) if kok.exists() else []


def _ikinci_kullanici(db: Session, dil_kodu: str | None = None) -> uuid.UUID:
    k = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                           dogrulandi_at=hesap.simdi(), dil=dil_kodu)
    db.add(k)
    db.commit()
    return k.id


def _dil_yaz(db: Session, kullanici_id: uuid.UUID, dil_kodu: str | None) -> None:
    db.execute(text("UPDATE kullanicilar SET dil = :d WHERE id = :id"), {"d": dil_kodu, "id": kullanici_id})
    db.commit()


# ── (i) dört tür ────────────────────────────────────────────────────────

def test_a_generate_job_ends_done_with_a_media_row_and_the_object_in_the_store(
        db_oturumu, kullanici, depo, yerlesim, tmp_path, monkeypatch):
    gorulen: list[tuple] = []
    monkeypatch.setattr(providers, "generate", lambda *a, **k: gorulen.append(a) or [PNG])
    is_id = _ekle(db_oturumu, kullanici.id, istek={"arena_id": "tur1", "session_id": "s1"})

    assert isci.tek_tur(db_oturumu, depo, _an(5), ayarlar=yerlesim, isci_id=ISCI) is True

    is_ = _is(db_oturumu, is_id)
    assert (is_.durum, is_.isci_id, is_.basladi) == ("bitti", ISCI, _an(5))
    assert is_.bitti is not None and is_.hata is None
    (m,) = _medya(db_oturumu, kullanici.id)
    assert is_.sonuc == {"medya": [m.id]}
    assert (m.prompt, m.size, m.quality, m.model, m.arena_id, m.session_id) == \
        ("kedi", "1024x1024", "medium", GORSEL, "tur1", "s1")
    assert m.kind is None and m.parent_id is None and m.filename == f"{m.id}.png"
    assert _nesneler(tmp_path, kullanici.id) == [m.filename]
    assert (tmp_path / "kullanicilar" / str(kullanici.id) / "output" / m.filename).read_bytes() == PNG
    # Sağlayıcı sözleşmesi DEĞİŞMEDİ: (model, prompt, size, quality, n).
    assert gorulen == [(GORSEL, "kedi", "1024x1024", "medium", 1)]


def test_an_edit_job_reads_its_inputs_from_the_store_in_order_and_records_the_parent(
        db_oturumu, kullanici, depo, yerlesim, tmp_path, monkeypatch):
    """`girdiler` sırası adaptör sözleşmesinin sırası (ilk = ana referans); anahtarlar
    depo YOLU (kök göreli, işçi anahtarla konuşur). Girdiler iş bitince SİLİNMEZ —
    karar rotanın (4. görev), işçi yalnız okur."""
    onek = f"kullanicilar/{kullanici.id}/isler/{uuid.uuid4().hex}"
    depo.yaz(f"{onek}/kaynak.png", PNG, "image/png")
    depo.yaz(f"{onek}/ref2.png", PNG2, "image/png")
    gorulen: list = []
    monkeypatch.setattr(providers, "edit",
                        lambda model, prompt, images, *a, **k: gorulen.append((model, prompt, images, a)) or [PNG2])
    is_id = _ekle(db_oturumu, kullanici.id, "edit", {
        "girdiler": [{"ad": "abc123.png", "anahtar": f"{onek}/kaynak.png"},
                     {"ad": "ref2.png", "anahtar": f"{onek}/ref2.png"}],
        "parent_id": "abc123", "n": 2})

    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True

    assert gorulen == [(GORSEL, "kedi", [("abc123.png", PNG), ("ref2.png", PNG2)], ("1024x1024", "medium", 2))]
    (m,) = _medya(db_oturumu, kullanici.id)
    assert m.parent_id == "abc123" and _is(db_oturumu, is_id).durum == "bitti"
    assert depo.var(f"{onek}/kaynak.png") and depo.var(f"{onek}/ref2.png"), "girdiler işçi tarafından silinmez"


def test_a_video_job_records_kind_duration_and_per_second_credits(
        db_oturumu, kullanici, depo, yerlesim, tmp_path, monkeypatch):
    gorulen: list = []
    monkeypatch.setattr(providers, "generate_video", lambda *a, **k: gorulen.append(a) or [MP4])
    is_id = _ekle(db_oturumu, kullanici.id, "video",
                  {"size": "16:9", "quality": "720p", "duration": 4}, model=VIDEO)

    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True

    assert gorulen == [(VIDEO, "kedi", "16:9", "720p", 4, 1)]
    (m,) = _medya(db_oturumu, kullanici.id)
    spec = catalog.video_model(VIDEO)
    assert spec is not None
    assert (m.kind, m.duration, m.model, m.filename) == ("video", 4, VIDEO, f"{m.id}.mp4")
    assert m.credits == catalog.cost_for(spec, "720p", duration=4), "kredi saniye başına, katalogtan"
    assert m.credits != 999, "tahmin (`kredi_tahmini`) satıra yazılmaz"
    assert _nesneler(tmp_path, kullanici.id) == [m.filename]
    assert _is(db_oturumu, is_id).durum == "bitti"


def test_an_animate_job_reads_the_first_and_last_frame_from_the_store(
        db_oturumu, kullanici, depo, yerlesim, monkeypatch):
    onek = f"kullanicilar/{kullanici.id}/isler/{uuid.uuid4().hex}"
    depo.yaz(f"{onek}/kare.png", PNG, "image/png")
    depo.yaz(f"{onek}/son.png", PNG2, "image/png")
    gorulen: list = []

    def sahte(model, prompt, images, size, quality, duration, n, *, last_frame=None, **k):
        gorulen.append((model, prompt, images, size, quality, duration, n, last_frame))
        return [MP4]

    monkeypatch.setattr(providers, "animate_video", sahte)
    _ekle(db_oturumu, kullanici.id, "animate", {
        "size": "16:9", "quality": "720p", "duration": 6, "parent_id": "kaynak1",
        "girdiler": [{"ad": "kaynak1.png", "anahtar": f"{onek}/kare.png"}],
        "son_kare": {"ad": "son.png", "anahtar": f"{onek}/son.png"}}, model=VIDEO)

    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True

    assert gorulen == [(VIDEO, "kedi", [("kaynak1.png", PNG)], "16:9", "720p", 6, 1, PNG2)]
    (m,) = _medya(db_oturumu, kullanici.id)
    assert (m.kind, m.duration, m.parent_id) == ("video", 6, "kaynak1")


def test_a_video_without_a_last_frame_passes_none(db_oturumu, kullanici, depo, yerlesim, monkeypatch):
    onek = f"kullanicilar/{kullanici.id}/isler/x"
    depo.yaz(f"{onek}/kare.png", PNG, "image/png")
    gorulen: list = []
    monkeypatch.setattr(providers, "animate_video",
                        lambda *a, last_frame=None, **k: gorulen.append(last_frame) or [MP4])
    _ekle(db_oturumu, kullanici.id, "animate", {
        "size": "16:9", "quality": "720p", "duration": 4,
        "girdiler": [{"ad": "k.png", "anahtar": f"{onek}/kare.png"}], "son_kare": None}, model=VIDEO)
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    assert gorulen == [None]


def test_credits_come_from_the_catalog_per_image_not_from_the_estimate(
        db_oturumu, kullanici, depo, yerlesim, monkeypatch):
    """Rota `kredi_tahmini`ni sıraya girerken yazar (× n); satıra GÖRSEL BAŞINA gerçek
    maliyet gider — bugünkü rotanın `catalog.cost_for(spec, quality)` çağrısı aynen."""
    monkeypatch.setattr(providers, "generate", lambda *a, **k: [PNG, PNG2, PNG])
    _ekle(db_oturumu, kullanici.id, istek={"n": 3, "quality": "high"}, kredi=999)
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    spec = catalog.image_model(GORSEL)
    assert spec is not None
    kayitlar = _medya(db_oturumu, kullanici.id)
    assert [m.credits for m in kayitlar] == [catalog.cost_for(spec, "high")] * 3


def test_n_results_become_n_rows_and_the_result_lists_them_in_production_order(
        db_oturumu, kullanici, depo, yerlesim, tmp_path, monkeypatch):
    monkeypatch.setattr(providers, "generate", lambda *a, **k: [PNG, PNG2])
    is_id = _ekle(db_oturumu, kullanici.id, istek={"n": 2})
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    kayitlar = _medya(db_oturumu, kullanici.id)
    assert len(kayitlar) == 2
    assert _is(db_oturumu, is_id).sonuc == {"medya": [m.id for m in kayitlar]}
    assert sorted(_nesneler(tmp_path, kullanici.id)) == sorted(m.filename for m in kayitlar)
    kok = tmp_path / "kullanicilar" / str(kullanici.id) / "output"
    assert [(kok / m.filename).read_bytes() for m in kayitlar] == [PNG, PNG2], "üretim sırası korunur"


def test_the_prompt_sent_is_the_routes_computation_and_is_recorded_only_when_the_palette_applied(
        db_oturumu, kullanici, depo, yerlesim, monkeypatch):
    """Palet hesabı ROTADA (`palet.palette_prompt`) ve `istek`te; işçi yeniden hesaplamaz —
    sağlayıcıya `prompt_sent` gider, satıra yalnız `applied` ise yazılır (storage sözleşmesi)."""
    gorulen: list[str] = []
    monkeypatch.setattr(providers, "generate", lambda m, p, *a, **k: gorulen.append(p) or [PNG])
    uygulanan = {"seed": "#ff0000", "mode": "analogic", "strength": "balanced", "applied": True}
    dusen = {**uygulanan, "applied": False}
    _ekle(db_oturumu, kullanici.id, istek={"prompt_sent": "kedi, renkler: kirmizi", "palette": uygulanan})
    _ekle(db_oturumu, kullanici.id, istek={"prompt_sent": "kedi", "palette": dusen})
    _ekle(db_oturumu, kullanici.id, istek={"palette": None})
    for _ in range(3):
        assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    assert gorulen == ["kedi, renkler: kirmizi", "kedi", "kedi"]
    a, b, c = _medya(db_oturumu, kullanici.id)
    assert (a.prompt, a.prompt_sent, a.palette) == ("kedi", "kedi, renkler: kirmizi", uygulanan)
    assert (b.prompt_sent, b.palette) == (None, dusen)
    assert (c.prompt_sent, c.palette) == (None, None)


def test_tek_tur_returns_false_on_an_empty_queue_and_touches_nothing(db_oturumu, kullanici, depo, yerlesim,
                                                                     tmp_path, monkeypatch):
    monkeypatch.setattr(providers, "generate", lambda *a, **k: pytest.fail("boş kuyrukta sağlayıcı çağrılmaz"))
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is False
    assert _medya(db_oturumu, kullanici.id) == [] and not (tmp_path / "kullanicilar").exists()


# ── (ii) telafi ─────────────────────────────────────────────────────────

def test_a_row_failure_deletes_the_written_object_and_marks_the_job_failed_with_a_code(
        db_oturumu, kullanici, depo, yerlesim, tmp_path, monkeypatch):
    """Faz 1 / 5'in borcu burada kapanır: `medya.folder_id` FK'sı olmayan klasörü reddeder
    (`flush` düşer) → nesne SİLİNİR, iş `hata` + KOD (istisna TÜRÜ, mesajı değil), iz `hata.log`da."""
    monkeypatch.setattr(providers, "generate", lambda *a, **k: [PNG])
    is_id = _ekle(db_oturumu, kullanici.id, istek={"folder_id": "olmayan-klasor"})

    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True

    is_ = _is(db_oturumu, is_id)
    assert is_.durum == "hata" and is_.hata == f"{isci.BEKLENMEYEN_HATASI}: IntegrityError"
    assert is_.sonuc is None and is_.bitti is not None
    assert _medya(db_oturumu, kullanici.id) == []
    assert _nesneler(tmp_path, kullanici.id) == [], "yazılan nesne telafiyle silindi"
    gunluk = (tmp_path / "hata.log").read_text(encoding="utf-8")
    assert str(is_id) in gunluk and "IntegrityError" in gunluk and "nesneler silindi" in gunluk


def test_a_failure_at_finish_time_also_compensates_every_object(db_oturumu, kullanici, depo, yerlesim,
                                                                tmp_path, monkeypatch):
    """Satırlar geçti, `bitir` düştü (DB hatası): commit HİÇ olmadı — satırlar geri alınır, nesneler silinir."""
    monkeypatch.setattr(providers, "generate", lambda *a, **k: [PNG, PNG2])

    def patlayan(*a, **k):
        raise RuntimeError("baglanti gitti")

    monkeypatch.setattr(kuyruk, "bitir", patlayan)
    is_id = _ekle(db_oturumu, kullanici.id, istek={"n": 2})
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    monkeypatch.undo()
    assert _is(db_oturumu, is_id).durum == "hata"
    assert _is(db_oturumu, is_id).hata == f"{isci.BEKLENMEYEN_HATASI}: RuntimeError"
    assert _medya(db_oturumu, kullanici.id) == [] and _nesneler(tmp_path, kullanici.id) == []


def test_a_job_dropped_as_stale_during_the_call_is_not_resurrected_and_its_object_is_deleted(
        depo_db, db_oturumu, kullanici, depo, yerlesim, tmp_path, monkeypatch):
    """Kalp 5 dk susmuş, bakım işi `hata`ya çekmiş; işçi çağrıdan dönüyor — `bitir` 0 satır:
    sonuç yazılmaz, nesne silinir, `hata` sütunu `BAYAT_HATASI` kalır (K8: dirilme yok)."""
    def sahte(*a, **k):
        with Session(depo_db) as bakim:
            assert kuyruk.bayatlari_dusur(bakim, _an(600), ESIK) == 1
            bakim.commit()
        return [PNG]

    monkeypatch.setattr(providers, "generate", sahte)
    is_id = _ekle(db_oturumu, kullanici.id)
    assert isci.tek_tur(db_oturumu, depo, _an(0), ayarlar=yerlesim) is True
    is_ = _is(db_oturumu, is_id)
    assert (is_.durum, is_.hata, is_.sonuc) == ("hata", kuyruk.BAYAT_HATASI, None)
    assert _medya(db_oturumu, kullanici.id) == [] and _nesneler(tmp_path, kullanici.id) == []
    assert "bayat" in (tmp_path / "hata.log").read_text(encoding="utf-8")


def test_the_object_is_written_before_the_row_and_the_job_closes_in_the_same_commit(
        db_oturumu, kullanici, depo, yerlesim, monkeypatch):
    """Belge §3 sırası: nesne → satır → `bitir` → TEK commit. Satır düşerse nesne artık
    kalır ve telafi bulur; tersi galeride kırık bir kutu olurdu."""
    sira: list[str] = []
    asil = depo.yaz

    def _yaz(*a, **k):
        sira.append("nesne")
        return asil(*a, **k)

    medya_yazanlar: set[int] = set()

    def _flush(session, ctx, instances):
        if any(isinstance(o, tablolar.Medya) for o in session.new):
            sira.append("satir")
            medya_yazanlar.add(id(session))

    def _commit(session):
        # Kimlik haritası zayıf: `kaydet` sözlük döndürür, satır nesnesi çoktan gitmiş
        # olabilir — oturumu flush anında işaretleyip commit'te ona bakıyoruz.
        if id(session) in medya_yazanlar:
            sira.append("commit")

    monkeypatch.setattr(depo, "yaz", _yaz)
    monkeypatch.setattr(providers, "generate", lambda *a, **k: [PNG])
    monkeypatch.setattr(kuyruk, "bitir", lambda *a, **k: sira.append("bitir") or True)
    event.listen(Session, "before_flush", _flush)
    event.listen(Session, "after_commit", _commit)
    try:
        _ekle(db_oturumu, kullanici.id)
        assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    finally:
        event.remove(Session, "before_flush", _flush)
        event.remove(Session, "after_commit", _commit)
    assert sira == ["nesne", "satir", "bitir", "commit"]


# ── (iii) hata ──────────────────────────────────────────────────────────

def test_a_provider_error_marks_the_job_failed_with_a_redacted_message_and_writes_no_row(
        db_oturumu, kullanici, depo, yerlesim, tmp_path, monkeypatch):
    def patlayan(*a, **k):
        raise ac.ImageError("Azure 401: key sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghij yanlis")

    monkeypatch.setattr(providers, "generate", patlayan)
    is_id = _ekle(db_oturumu, kullanici.id)
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    is_ = _is(db_oturumu, is_id)
    assert is_.durum == "hata" and is_.bitti is not None and is_.sonuc is None
    assert is_.hata is not None and "sk-proj-" not in is_.hata and "[REDACTED_API_KEY]" in is_.hata
    assert "Azure 401" in is_.hata, "teşhis metni durur, anahtar gider"
    assert _medya(db_oturumu, kullanici.id) == [] and _nesneler(tmp_path, kullanici.id) == []
    assert not (tmp_path / "hata.log").exists(), "sağlayıcı hatası beklenen bir hata: günlük yok"


def test_an_unexpected_exception_is_logged_to_hata_log_and_the_job_fails_with_a_type_code(
        db_oturumu, kullanici, depo, yerlesim, tmp_path, monkeypatch):
    def patlayan(*a, **k):
        raise KeyError("/gizli/yol/sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghij")

    monkeypatch.setattr(providers, "generate", patlayan)
    is_id = _ekle(db_oturumu, kullanici.id)
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    is_ = _is(db_oturumu, is_id)
    assert (is_.durum, is_.hata) == ("hata", f"{isci.BEKLENMEYEN_HATASI}: KeyError"), "mesaj değil TÜR"
    gunluk = (tmp_path / "hata.log").read_text(encoding="utf-8")
    assert str(is_id) in gunluk and "KeyError" in gunluk
    assert "sk-proj-" not in gunluk, "errlog redakte eder"


def test_an_unknown_model_fails_as_a_provider_error(db_oturumu, kullanici, depo, yerlesim):
    """`providers._resolve` katalogda olmayan modeli `ImageError` ile reddeder — yamasız yol."""
    is_id = _ekle(db_oturumu, kullanici.id, model="yok-boyle-model")
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    is_ = _is(db_oturumu, is_id)
    assert is_.durum == "hata" and is_.hata and not is_.hata.startswith(isci.BEKLENMEYEN_HATASI)


@pytest.mark.parametrize("dil_kodu", ["tr", "en"])
def test_a_missing_input_object_fails_the_job_with_the_routes_404_text_in_the_users_language(
        db_oturumu, kullanici, depo, yerlesim, monkeypatch, dil_kodu):
    _dil_yaz(db_oturumu, kullanici.id, dil_kodu)
    monkeypatch.setattr(providers, "edit", lambda *a, **k: pytest.fail("girdi okunamadı, çağrı olmaz"))
    is_id = _ekle(db_oturumu, kullanici.id, "edit",
                  {"girdiler": [{"ad": "a.png", "anahtar": f"kullanicilar/{kullanici.id}/isler/yok/a.png"}]})
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    assert _is(db_oturumu, is_id).hata == i18n.t("err.source_image_missing", dil_kodu)


@pytest.mark.parametrize("dil_kodu", ["tr", "en"])
def test_the_provider_error_text_is_produced_in_the_users_language(db_oturumu, kullanici, depo, yerlesim,
                                                                    monkeypatch, dil_kodu):
    """`hata` sütunu KULLANICIYA gösterilecek: adaptörlerin `map_error`ı dili `i18n.active()`ten
    okur, işçi onu `kullanicilar.dil`e kurar (istek yok, ara katman yok)."""
    _dil_yaz(db_oturumu, kullanici.id, dil_kodu)

    def patlayan(*a, **k):
        raise ac.ImageError(i18n.t("err.model_no_reference", dil.aktif(), model="X"))

    monkeypatch.setattr(providers, "generate", patlayan)
    is_id = _ekle(db_oturumu, kullanici.id)
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    beklenen = i18n.t("err.model_no_reference", dil_kodu, model="X")
    assert _is(db_oturumu, is_id).hata == beklenen
    assert beklenen != i18n.t("err.model_no_reference", "en" if dil_kodu == "tr" else "tr", model="X")


def test_a_user_who_never_chose_a_language_gets_the_product_default_not_the_fallback(
        db_oturumu, kullanici, depo, yerlesim, monkeypatch):
    """`dil` NULL = seçmemiş → `i18n.DEFAULT` (web'de tarayıcı başlığına düşerdi, işçide başlık yok);
    `FALLBACK` "kullanıcı yok" demek ve burada kullanıcı var."""
    _dil_yaz(db_oturumu, kullanici.id, None)
    gorulen: list[str] = []
    monkeypatch.setattr(providers, "generate", lambda *a, **k: gorulen.append(dil.aktif()) or [PNG])
    _ekle(db_oturumu, kullanici.id)
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    assert gorulen == [i18n.DEFAULT]


# ── (iv) bağlam ─────────────────────────────────────────────────────────

def test_the_credential_context_is_bound_per_job_and_unbound_afterwards(
        db_oturumu, kullanici, depo, yerlesim, monkeypatch):
    """Faz 1 / 7'nin `[A, B]` testinin işçi ikizi: aynı iş parçacığı A'nın sonra B'nin işini
    koşturur, adaptör HER seferinde o işin sahibinin anahtarını görür; işten sonra bağlam BOŞ
    (çözülmese B'nin işi A'nın anahtarıyla giderdi — 502 yerine sessiz bir fatura)."""
    b_id = _ikinci_kullanici(db_oturumu)
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {"AZURE_IMAGE_API_KEY": "A-DUMMY-ANAHTAR"})
    depo_kimlik_bilgisi.yaz(db_oturumu, b_id, {"AZURE_IMAGE_API_KEY": "B-DUMMY-ANAHTAR"})
    db_oturumu.commit()
    gorulen: list = []

    def sahte(*a, **k):
        aktif = kimlik_baglami.aktif()
        gorulen.append(None if aktif is None else aktif.get("AZURE_IMAGE_API_KEY"))
        return [PNG]

    monkeypatch.setattr(providers, "generate", sahte)
    _ekle(db_oturumu, kullanici.id)
    _ekle(db_oturumu, b_id)
    assert kimlik_baglami.aktif() is None
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    assert kimlik_baglami.aktif() is None, "iş bitti, bağlam çözüldü"
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    assert gorulen == ["A-DUMMY-ANAHTAR", "B-DUMMY-ANAHTAR"]
    assert kimlik_baglami.aktif() is None


def test_the_context_is_unbound_even_when_the_provider_raises(db_oturumu, kullanici, depo, yerlesim,
                                                              monkeypatch):
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {"AZURE_IMAGE_API_KEY": "A-DUMMY-ANAHTAR"})
    _dil_yaz(db_oturumu, kullanici.id, "en")

    def patlayan(*a, **k):
        assert kimlik_baglami.aktif() == {"AZURE_IMAGE_API_KEY": "A-DUMMY-ANAHTAR"}
        assert i18n.active() == "en"
        raise RuntimeError("x")

    monkeypatch.setattr(providers, "generate", patlayan)
    _ekle(db_oturumu, kullanici.id)
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    assert kimlik_baglami.aktif() is None and i18n.active() == i18n.FALLBACK


def test_no_pooled_connection_is_held_while_the_provider_call_runs(depo_db, db_oturumu, kullanici, depo,
                                                                    yerlesim, monkeypatch):
    """Belge §3 riski (b): çağrı dakikalarca sürer, havuz küçük — `kos` çağrı sırasında hiçbir
    `Session`i açık tutmaz (al → commit; çağrı; yeni oturum → yaz → commit)."""
    gorulen: list[int] = []
    monkeypatch.setattr(providers, "generate",
                        lambda *a, **k: gorulen.append(depo_db.pool.checkedout()) or [PNG])
    _ekle(db_oturumu, kullanici.id)
    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    assert gorulen == [0]


def test_siradakini_al_returns_a_detached_row_and_releases_the_connection(depo_db, db_oturumu, kullanici):
    is_id = _ekle(db_oturumu, kullanici.id)
    is_ = isci.siradakini_al(db_oturumu, ISCI, _an(7))
    assert is_ is not None and is_.id == is_id
    assert sa_inspect(is_).detached, "oturumdan ayrıldı: süresi geçmiş öznitelik okuması DB'ye gitmez"
    assert (is_.durum, is_.isci_id, is_.basladi, is_.istek["prompt"]) == ("calisiyor", ISCI, _an(7), "kedi")
    assert depo_db.pool.checkedout() == 0
    assert isci.siradakini_al(db_oturumu, ISCI, _an(8)) is None


def test_two_workers_take_two_different_jobs(depo_db, db_oturumu, kullanici, depo, yerlesim, monkeypatch):
    monkeypatch.setattr(providers, "generate", lambda *a, **k: [PNG])
    a, b = _ekle(db_oturumu, kullanici.id), _ekle(db_oturumu, kullanici.id)
    isci_a, isci_b = uuid.uuid4(), uuid.uuid4()
    with Session(depo_db) as s1, Session(depo_db) as s2:
        is_a = isci.siradakini_al(s1, isci_a, _an(1))
        is_b = isci.siradakini_al(s2, isci_b, _an(1))
    assert is_a is not None and is_b is not None
    assert {is_a.id, is_b.id} == {a, b} and is_a.id == a, "FIFO: ilk alan ilk işi alır"
    assert (_is(db_oturumu, a).isci_id, _is(db_oturumu, b).isci_id) == (isci_a, isci_b)
    for is_ in (is_a, is_b):
        assert isci.kos(is_, lambda: Session(depo_db), depo, yerlesim) is True
    assert {_is(db_oturumu, a).durum, _is(db_oturumu, b).durum} == {"bitti"}
    assert len(_medya(db_oturumu, kullanici.id)) == 2


def test_heartbeat_advances_the_worker_row_and_every_running_job(db_oturumu, kullanici):
    satir = kuyruk.isci_kaydet(db_oturumu, "konak", "0.0.0", 2, _an())
    db_oturumu.commit()
    a, b = _ekle(db_oturumu, kullanici.id), _ekle(db_oturumu, kullanici.id)
    kuyruk.al(db_oturumu, satir.id, _an(0))
    kuyruk.al(db_oturumu, satir.id, _an(0))
    db_oturumu.commit()
    assert isci.kalp_turu(db_oturumu, satir.id, [a, b], _an(30), ESIK) == (0, False)
    db_oturumu.expire_all()
    assert db_oturumu.get(tablolar.Isci, satir.id).son_kalp == _an(30)
    assert (_is(db_oturumu, a).kalp_atisi, _is(db_oturumu, b).kalp_atisi) == (_an(30), _an(30))
    assert (_is(db_oturumu, a).durum, _is(db_oturumu, b).durum) == ("calisiyor", "calisiyor")


def test_heartbeat_drops_jobs_whose_heart_stopped_beyond_the_threshold(db_oturumu, kullanici):
    """Ölen işçinin işi yaşayan işçinin kalp turunda `hata`ya çekilir (K8: kuyruğa dönmez)."""
    satir = kuyruk.isci_kaydet(db_oturumu, "konak", "0.0.0", 1, _an())
    db_oturumu.commit()
    olu_isci, benim = uuid.uuid4(), _ekle(db_oturumu, kullanici.id)
    olen = _ekle(db_oturumu, kullanici.id)
    kuyruk.al(db_oturumu, satir.id, _an(0))          # benim işim (FIFO: ilk eklenen)
    kuyruk.al(db_oturumu, olu_isci, _an(0))          # ölen işçinin işi
    db_oturumu.commit()
    assert isci.kalp_turu(db_oturumu, satir.id, [benim], _an(200), ESIK).dusen == 0
    assert isci.kalp_turu(db_oturumu, satir.id, [benim], _an(400), ESIK).dusen == 1
    assert (_is(db_oturumu, benim).durum, _is(db_oturumu, olen).durum) == ("calisiyor", "hata")
    assert _is(db_oturumu, olen).hata == kuyruk.BAYAT_HATASI


def test_the_heartbeat_rewrites_a_missing_worker_row_with_the_same_identity_only_when_given_one(
        db_oturumu, kullanici):
    """Yaşayan işçinin satırı gidebilir (başka işçinin `olu_iscileri_sil`i, 5 dk'lık kesinti,
    dağıtımda yeni işçinin açılış turu): `kayit` verilmişse kalp turu satırı AYNI `id` ve
    `basladi`yla yeniden yazar ve bunu söyler; `kayit`sız çağrı eski davranış — yok sayar."""
    satir = kuyruk.isci_kaydet(db_oturumu, "konak", "0.0.0", 2, _an())
    db_oturumu.commit()
    isci_id = satir.id
    kayit = kuyruk.IsciKaydi(konak="konak", surum="0.0.0", es_zamanli=2, basladi=_an())
    assert isci.kalp_turu(db_oturumu, isci_id, [], _an(30), ESIK, kayit=kayit) == (0, False), "satır varken yalnız kalp"
    kuyruk.isci_sil(db_oturumu, isci_id)
    db_oturumu.commit()
    # Silinen nesne bu oturumun kimlik haritasında duruyor; işçi her turu YENİ oturumda koşar,
    # burada aynı anahtarla yeniden `add` edilebilsin diye haritadan çıkarılıyor.
    db_oturumu.expunge(satir)
    assert isci.kalp_turu(db_oturumu, isci_id, [], _an(60), ESIK) == (0, False), "kimlik verilmedi: eski davranış"
    db_oturumu.commit()
    assert list(db_oturumu.scalars(select(tablolar.Isci.id))) == [], "kimliksiz tur satır yazmaz"
    ozet = isci.kalp_turu(db_oturumu, isci_id, [], _an(90), ESIK, kayit=kayit)
    assert ozet == (0, True) and ozet.yeniden_kaydoldu is True
    yeni = db_oturumu.get(tablolar.Isci, isci_id)
    assert yeni is not None
    assert (yeni.konak, yeni.surum, yeni.es_zamanli, yeni.basladi, yeni.son_kalp) == ("konak", "0.0.0", 2, _an(), _an(90))
    assert isci.kalp_turu(db_oturumu, isci_id, [], _an(120), ESIK, kayit=kayit) == (0, False), "bir kez yazıldı, sonrası kalp"
    assert kuyruk.isci_son_kalp(db_oturumu) == _an(120), "/health yeniden yazılan satırı görür"


def test_concurrency_and_threshold_come_from_the_environment_with_defaults_and_refuse_nonsense():
    assert isci.saklama({}) == dt.timedelta(days=30) and isci.saklama({isci.SAKLAMA_ENV: "7"}) == dt.timedelta(days=7)
    with pytest.raises(ValueError, match=isci.SAKLAMA_ENV):
        isci.saklama({isci.SAKLAMA_ENV: "0"})
    assert isci.es_zamanli({}) == 4 and isci.es_zamanli({isci.ES_ZAMANLI_ENV: " "}) == 4
    assert isci.es_zamanli({isci.ES_ZAMANLI_ENV: "2"}) == 2
    assert isci.kalp_esigi({}) == dt.timedelta(seconds=300)
    assert isci.kalp_esigi({isci.KALP_ESIGI_ENV: "60"}) == dt.timedelta(seconds=60)
    for kotu in ("0", "-1", "abc", "1.5"):
        with pytest.raises(ValueError, match=isci.ES_ZAMANLI_ENV):
            isci.es_zamanli({isci.ES_ZAMANLI_ENV: kotu})
    with pytest.raises(ValueError, match=isci.KALP_ESIGI_ENV):
        isci.kalp_esigi({isci.KALP_ESIGI_ENV: "0"})


# ── (iv-b) bakım turu (Faz 2 / 10) ─────────────────────────────────────

SAKLAMA = dt.timedelta(days=30)
BAKIM_ANI = _an(40 * 86400)


def _girdili(db: Session, kullanici_id: uuid.UUID, depo: dosya.Depo, *, kaynak: uuid.UUID | None = None,
             adlar: tuple[str, ...] = ("upload.png",)) -> uuid.UUID:
    """`edit` işi: girdileri KENDİ dizinine yazar; `kaynak` verilmişse o işin dizinine REFERANS verir (yeniden gönderim)."""
    is_id = uuid.uuid4()
    dizin = ayar.is_dizini(kullanici_id, kaynak if kaynak is not None else is_id)
    girdiler = [{"ad": ad, "anahtar": dizin + ad} for ad in adlar]
    if kaynak is None:
        for g in girdiler:
            depo.yaz(g["anahtar"], PNG, "image/png")
    kuyruk.ekle(db, kullanici_id, "edit", {"prompt": "e", "size": "1024x1024", "quality": "medium", "n": 1,
                                           "girdiler": girdiler, "parent_id": None},
                GORSEL, 1, an=_an(), is_id=is_id)
    db.commit()
    return is_id


def _kapat(db: Session, is_id: uuid.UUID, durum: str, bitti: dt.datetime) -> None:
    db.execute(text("UPDATE isler SET durum = :d, bitti = :b WHERE id = :id"), {"d": durum, "b": bitti, "id": is_id})
    db.commit()


def test_the_maintenance_turn_deletes_expired_rows_and_only_the_unreferenced_input_directories(
        db_oturumu, kullanici, depo, yerlesim):
    """Saklama + nesne süpürmesi + ölü işçi, tek turda (services/isci.py `bakim_turu`):

    A (eski, kapanmış, girdileri kendi dizininde) — B yeniden gönderilmiş, A'nın dizinine
    REFERANS veriyor ve taze → A'nın SATIRI gider, DİZİNİ KALIR (B bakıyor). C (eski, kapanmış,
    kendi girdileri, kimse bakmıyor) → satır ve nesneleri gider. D taze → kalır. `medya`
    dokunulmaz. Ölü işçi satırı gider, canlı kalır. Boş ikinci tur `False` (olay düşmez)."""
    a = _girdili(db_oturumu, kullanici.id, depo, adlar=("upload.png", "ref2.png"))
    b = _girdili(db_oturumu, kullanici.id, depo, kaynak=a, adlar=("upload.png", "ref2.png"))
    c = _girdili(db_oturumu, kullanici.id, depo, adlar=("upload.png",))
    d = _girdili(db_oturumu, kullanici.id, depo)
    eski_an = BAKIM_ANI - SAKLAMA - dt.timedelta(days=1)
    _kapat(db_oturumu, a, "bitti", eski_an)
    _kapat(db_oturumu, b, "hata", BAKIM_ANI - dt.timedelta(hours=1))
    _kapat(db_oturumu, c, "iptal", eski_an)
    medya = depo_medya.kaydet(db_oturumu, kullanici.id, PNG, {"prompt": "urun"}, yerlesim.kullanici_icin(kullanici.id).output_dir, depo=depo)
    olu = kuyruk.isci_kaydet(db_oturumu, "olu", "0.0.0", 1, _an())
    canli = kuyruk.isci_kaydet(db_oturumu, "canli", "0.0.0", 1, _an())
    kuyruk.isci_kalp(db_oturumu, olu.id, BAKIM_ANI - ESIK - dt.timedelta(seconds=1))
    kuyruk.isci_kalp(db_oturumu, canli.id, BAKIM_ANI - dt.timedelta(seconds=10))
    db_oturumu.commit()

    ozet = isci.bakim_turu(db_oturumu, depo, BAKIM_ANI, ESIK, SAKLAMA)

    assert ozet == {"silinen_is": 2, "silinen_nesne": 1, "korunan_dizin": 1, "silinen_isci": 1} and bool(ozet)
    db_oturumu.expire_all()
    assert set(db_oturumu.scalars(select(tablolar.Is.id))) == {b, d}
    assert depo.var(ayar.is_dizini(kullanici.id, a) + "upload.png") and depo.var(ayar.is_dizini(kullanici.id, a) + "ref2.png"), (
        "A'nın dizini B'nin referansı yüzünden durur")
    assert not depo.var(ayar.is_dizini(kullanici.id, c) + "upload.png"), "C'ye kimse bakmıyor: nesnesi gitti"
    assert depo.var(ayar.is_dizini(kullanici.id, d) + "upload.png")
    assert [k.konak for k in db_oturumu.scalars(select(tablolar.Isci))] == ["canli"]
    assert db_oturumu.get(tablolar.Medya, medya["id"]) is not None and depo.var(
        f"{ayar.KULLANICILAR_DIZINI}/{kullanici.id}/output/{medya['filename']}"), "ürün galeride durur"
    bos = isci.bakim_turu(db_oturumu, depo, BAKIM_ANI, ESIK, SAKLAMA)
    assert not bos and dict(bos) == {"silinen_is": 0, "silinen_nesne": 0, "korunan_dizin": 0, "silinen_isci": 0}


def test_the_maintenance_turn_frees_a_referenced_directory_once_the_last_referrer_expires(
        db_oturumu, kullanici, depo, yerlesim):
    """A silinmiş (satırı yok), B ona bakıyordu; B de süresini doldurunca A'nın dizini — kendi satırı
    olmayan ama B'nin `istek`inden gelen aday — bu turda gider. Tanınmayan biçimde bir anahtar
    (`foo/bar.png`) ise adaya bile girmez: körlemesine bir `foo/` silinmez."""
    a = uuid.uuid4()
    depo.yaz(ayar.is_dizini(kullanici.id, a) + "upload.png", PNG, "image/png")
    depo.yaz("foo/bar.png", PNG, "image/png")
    b = _girdili(db_oturumu, kullanici.id, depo, kaynak=a)
    db_oturumu.execute(text("UPDATE isler SET istek = istek || :ek WHERE id = :id"),
                       {"ek": '{"son_kare": {"ad": "bar.png", "anahtar": "foo/bar.png"}}', "id": b})
    _kapat(db_oturumu, b, "hata", BAKIM_ANI - SAKLAMA - dt.timedelta(seconds=1))
    ozet = isci.bakim_turu(db_oturumu, depo, BAKIM_ANI, ESIK, SAKLAMA)
    assert ozet["silinen_is"] == 1 and ozet["silinen_nesne"] == 1 and ozet["korunan_dizin"] == 0
    assert not depo.var(ayar.is_dizini(kullanici.id, a) + "upload.png")
    assert depo.var("foo/bar.png"), "tanınmayan anahtar biçimi süpürülmez"


class _Yakala(logging.Handler):
    """`kromis.*` köke yayılmaz (services/gunluk.py); olay kayıtları doğrudan günlükçüden toplanır."""

    def __init__(self) -> None:
        super().__init__()
        self.kayitlar: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.kayitlar.append(record)


def test_the_maintenance_turn_leaves_another_tenants_directory_alone_even_if_a_deleted_request_points_at_it(
        db_oturumu, kullanici, depo, yerlesim):
    """Derinlikli savunma: silinen işin `istek`i BAŞKA kiracının `isler/<id>/` dizinine bakıyorsa o
    dizin aday olmaz (referanssız ve satırsız olsa bile), `olay=bakim.yabanci_dizin` uyarısı düşer;
    işin kendi dizini yine gider. Bugün `istek`i yalnız sunucu yazar — bu dal boş; kapı yine dursun."""
    yabanci = _ikinci_kullanici(db_oturumu)
    yabanci_is = uuid.uuid4()
    yabanci_dizin = ayar.is_dizini(yabanci, yabanci_is)
    depo.yaz(yabanci_dizin + "gizli.png", PNG, "image/png")
    b = _girdili(db_oturumu, kullanici.id, depo)
    db_oturumu.execute(text("UPDATE isler SET istek = jsonb_set(istek, '{girdiler}', (istek->'girdiler') || CAST(:ek AS jsonb)) "
                            "WHERE id = :id"),
                       {"ek": json.dumps([{"ad": "gizli.png", "anahtar": yabanci_dizin + "gizli.png"}]), "id": b})
    _kapat(db_oturumu, b, "bitti", BAKIM_ANI - SAKLAMA - dt.timedelta(days=1))
    yakala = _Yakala()
    gunlukcu = logging.getLogger("kromis.is")
    # Aynı süreçte koşmuş Alembic `fileConfig` (şablon DB) günlükçüyü KAPATMIŞ olabilir;
    # `gunluk.kur` üretimde açar (services/gunluk.py), burada kurulum yok — elle.
    kapaliydi, gunlukcu.disabled = gunlukcu.disabled, False
    gunlukcu.addHandler(yakala)
    try:
        ozet = isci.bakim_turu(db_oturumu, depo, BAKIM_ANI, ESIK, SAKLAMA)
    finally:
        gunlukcu.removeHandler(yakala)
        gunlukcu.disabled = kapaliydi
    assert ozet == {"silinen_is": 1, "silinen_nesne": 1, "korunan_dizin": 0, "silinen_isci": 0}
    assert not depo.var(ayar.is_dizini(kullanici.id, b) + "upload.png"), "işin kendi dizini gider"
    assert depo.var(yabanci_dizin + "gizli.png"), "başka kiracının dizinine dokunulmaz"
    (uyari,) = [k for k in yakala.kayitlar if getattr(k, "olay", None) == "bakim.yabanci_dizin"]
    assert uyari.levelno == logging.WARNING
    assert (uyari.dizin, uyari.is_id, uyari.kullanici_id) == (yabanci_dizin, str(b), str(kullanici.id))
    # Çözücü iki kimliği de verir; tanınmayan biçim `None` (eski `is_dizini_ayristir` yalnız iş kimliği).
    assert ayar.is_dizini_coz(yabanci_dizin) == (yabanci, yabanci_is)
    assert ayar.is_dizini_ayristir(yabanci_dizin) == yabanci_is
    assert ayar.is_dizini_coz("foo/") is None and ayar.is_dizini_coz(f"kullanicilar/{yabanci}/isler/x/") is None


# ── (v) süreç ───────────────────────────────────────────────────────────

def _kaynak(ad: str) -> str:
    with open(os.path.join(REPO, ad), encoding="utf-8") as f:
        return f.read()


def test_the_entry_point_carries_the_same_gates_as_the_web_and_sizes_its_own_pool():
    """`app._lifespan`in kapıları işçide de: anahtar (`sifre.dogrula_ortam`), depo
    (`dosya.depo_kur`), motor (`db.motor_kur` — `es_zamanli + 1`), SIGTERM düzeni.
    Kaynak taraması: bir kapı silinirse süreç testleri onu ancak dolaylı görür."""
    kaynak = _kaynak("isci.py")
    for parca in ("sifre.dogrula_ortam()", "dosya.depo_kur(", "db.motor_kur(url, pool_size=es_zamanli + 1)",
                  "signal.SIGTERM", "signal.SIGINT", "kuyruk.isci_kaydet(", "kuyruk.isci_sil(",
                  "isci.kalp_turu(", "isci.siradakini_al(", "isci.kos(", "isci.tek_tur(",
                  "isci.bakim_turu(", "isci.saklama()", "kayit=self.kayit", "self.kapat.wait(",
                  'name="kromis-isci-bakim"'):
        assert parca in kaynak, parca
    assert "uvicorn" not in kaynak and "FastAPI" not in kaynak, "işçi web değil: rota yok, port yok"


def test_the_heartbeat_keeps_beating_after_stop_while_a_job_drains_and_shutdown_is_ordered(
        veritabani_url, depo_db, db_oturumu, kullanici, depo, yerlesim, tmp_path, monkeypatch):
    """`Surec.calistir` süreçsiz, sahte (bloklayan) `kos`la: `durdur` kalktıktan (SIGTERM) sonra
    eldeki iş bitene dek `isciler.son_kalp` ve işin `kalp_atisi` İLERLEMEYİ SÜRDÜRÜR — tek bayrakla
    kalp SIGTERM'de susuyordu ve 300 sn'ye yakın boşalan iş yeni işçinin bayat düşürmesine
    yakalanıyordu. Kapanış sırası: iş bitti → `kapat` → kalp/bakım beklendi → satır silindi.
    Açılış bakım turu bu düzenin içinde bir kez koşar."""
    surec_modulu = importlib.import_module("isci")
    is_id = _ekle(db_oturumu, kullanici.id)
    basladi, birak = threading.Event(), threading.Event()
    kosulan: list[uuid.UUID] = []

    def sahte_kos(is_, oturum_ac, depo_, ayarlar, **k):
        kosulan.append(is_.id)
        basladi.set()
        assert birak.wait(30), "test işi serbest bırakmadı"
        return True

    bakimlar: list[int] = []
    gercek_bakim = isci.bakim_turu

    def sayan_bakim(*a, **k):
        bakimlar.append(1)
        return gercek_bakim(*a, **k)

    monkeypatch.setattr(isci, "kos", sahte_kos)
    monkeypatch.setattr(isci, "bakim_turu", sayan_bakim)
    motor = db.motor_kur(veritabani_url, pool_size=2)
    surec = surec_modulu.Surec(motor, depo, yerlesim, 1, ESIK, 0.05, SAKLAMA, 3600.0)
    surec.kaydol()

    def _son_kalp():
        with depo_db.connect() as c:
            return c.execute(text("SELECT son_kalp FROM isciler WHERE id = :i"), {"i": surec.isci_id}).scalar_one_or_none()

    def _kalp_atisi():
        with depo_db.connect() as c:
            return c.execute(text("SELECT kalp_atisi FROM isler WHERE id = :i"), {"i": is_id}).scalar_one()

    ana = threading.Thread(target=surec.calistir, name="test-calistir")
    ana.start()
    try:
        assert basladi.wait(30), "iş alınmadı"
        surec.durdur.set()                       # SIGTERM işleyicisinin yaptığı tek şey
        kalp1, atis1 = _son_kalp(), _kalp_atisi()
        time.sleep(0.4)
        kalp2, atis2 = _son_kalp(), _kalp_atisi()
        assert ana.is_alive() and not surec.kapat.is_set(), "iş sürüyor: kapanış başlamamalı"
        assert kalp1 is not None and kalp2 is not None and kalp2 > kalp1, "durdur'dan sonra işçi kalbi sustu"
        assert atis1 is not None and atis2 > atis1, "durdur'dan sonra işin kalp_atisi tazelenmedi"
    finally:
        birak.set()
        ana.join(30)
    assert not ana.is_alive() and surec.kapat.is_set()
    assert kosulan == [is_id]
    assert _son_kalp() is None, "kapanışta satır silinir"
    assert bakimlar == [1], "açılış bakım turu bir kez, kalpten ayrı"
    assert not (tmp_path / "hata.log").exists()


def _ortam(url: str | None, tmp_path, **ek: str) -> dict[str, str]:
    ortam = {k: v for k, v in os.environ.items() if not k.startswith("KROMIS_NESNE_DEPO_")}
    ortam["KROMIS_DATA_DIR"] = str(tmp_path)
    ortam.pop("DATABASE_URL", None)
    if url is not None:
        ortam["DATABASE_URL"] = url
    ortam.update(ek)
    return ortam


def _kos(argv: list[str], ortam: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "isci.py", *argv], cwd=REPO, env=ortam,
                          capture_output=True, text=True, encoding="utf-8", timeout=120)


def _olaylar(cikti: str) -> list[dict]:
    """Sürecin stdout'u satır başına JSON (Faz 2 / 9; services/gunluk.py) — her satır açılmak ZORUNDA."""
    return [json.loads(s) for s in cikti.splitlines() if s.strip()]


def _yavas_saglayici(tmp_path, saniye: float) -> str:
    """Alt sürece `sitecustomize` ile yamalı sağlayıcı: `providers.generate` `saniye` uyur, sonra PNG döner.

    Gerçek süreçte sağlayıcıyı `monkeypatch`leyemeyiz; `PYTHONPATH`in başındaki
    dizinden gelen `sitecustomize` yorumlayıcı açılırken koşar ve `isci.py`
    ithal etmeden önce modül özniteliğini değiştirir (`_uret` onu çağrı anında
    okur). Ağa çıkılmaz, iş `bitti`ye varır — boşaltma penceresi ölçülebilir.
    """
    kanca = tmp_path / "kanca"
    kanca.mkdir()
    (kanca / "sitecustomize.py").write_text(textwrap.dedent(f"""
        import time
        import providers

        def _yavas(model_id, prompt, size, quality, n, **k):
            time.sleep({saniye!r})
            return [{PNG!r}] * n

        providers.generate = _yavas
    """), encoding="utf-8")
    return str(kanca) + os.pathsep + REPO


def _hata_mesaji(sonuc: subprocess.CompletedProcess[str]) -> str:
    """Kapı hatası JSON satırıyla stdout'a düşer (`olay=isci.hata`, ERROR); stderr boş kalır."""
    hatalar = [o for o in _olaylar(sonuc.stdout) if o.get("olay") == "isci.hata"]
    assert hatalar and sonuc.stderr == "", (sonuc.stdout, sonuc.stderr)
    assert all(o["seviye"] == "ERROR" for o in hatalar)
    return hatalar[-1]["mesaj"]


def test_the_process_refuses_to_start_without_the_secret_key_or_the_database_url(veritabani_url, tmp_path):
    """Web'in TEK istisnası işçide de: anahtarsız açılmaz (çözeceği satır var) — çıkış 2, adı söyler."""
    ortam = _ortam(veritabani_url, tmp_path)
    ortam.pop("KROMIS_SECRET_KEY", None)
    sonuc = _kos(["--tek-tur"], ortam)
    assert sonuc.returncode == 2, sonuc.stderr
    mesaj = _hata_mesaji(sonuc)
    assert "KROMIS_SECRET_KEY" in mesaj and "ACILMAZ" in mesaj
    assert (tmp_path / "hata.log").exists(), "iz hata.log'a da (app._lifespan gibi)"

    sonuc = _kos(["--tek-tur"], _ortam(None, tmp_path))
    assert sonuc.returncode == 2 and "DATABASE_URL" in _hata_mesaji(sonuc)


def test_the_process_refuses_a_half_configured_object_store_and_a_bad_concurrency_value(veritabani_url, tmp_path):
    sonuc = _kos(["--tek-tur"], _ortam(veritabani_url, tmp_path, KROMIS_NESNE_DEPO_URL="https://x.example"))
    assert sonuc.returncode == 2 and "yarim" in _hata_mesaji(sonuc), sonuc.stdout
    sonuc = _kos([], _ortam(veritabani_url, tmp_path, KROMIS_ISCI_ES_ZAMANLI="0"))
    assert sonuc.returncode == 2 and "KROMIS_ISCI_ES_ZAMANLI" in _hata_mesaji(sonuc), sonuc.stdout


def test_tek_tur_flag_exits_zero_on_an_empty_queue_without_registering_a_worker(veritabani_url, depo_db,
                                                                               tmp_path):
    """CI `docker` işinin koşturacağı komut (10. görev): boş kuyrukta 0, `isciler`e satır yazmaz."""
    sonuc = _kos(["--tek-tur"], _ortam(veritabani_url, tmp_path))
    assert sonuc.returncode == 0, sonuc.stderr
    (olay,) = _olaylar(sonuc.stdout)
    assert (olay["olay"], olay["mesaj"], olay["kostu"]) == ("isci.tek_tur", "kuyruk bos", False)
    with depo_db.connect() as c:
        assert c.execute(text("SELECT count(*) FROM isciler")).scalar_one() == 0


def test_tek_tur_flag_runs_a_queued_job_end_to_end_in_the_real_process(veritabani_url, db_oturumu, kullanici,
                                                                       tmp_path):
    """Yamasız gerçek süreç: kimliği olmayan kullanıcının işi adaptörde "anahtar yok" ile
    düşer (`credstore`) — ağa çıkılmaz, iş `hata`ya iner, hangi anahtarın eksik olduğunu söyler."""
    is_id = _ekle(db_oturumu, kullanici.id)
    sonuc = _kos(["--tek-tur"], _ortam(veritabani_url, tmp_path))
    assert sonuc.returncode == 0, sonuc.stderr
    olaylar = _olaylar(sonuc.stdout)
    assert [o["olay"] for o in olaylar] == ["is.alindi", "is.basladi", "is.hata", "isci.tek_tur"], olaylar
    assert olaylar[-1]["mesaj"] == "bir is kostu" and olaylar[-1]["kostu"] is True
    assert all(o["is_id"] == str(is_id) for o in olaylar[:3]), "iş satırları `is_id` taşır"
    is_ = _is(db_oturumu, is_id)
    assert is_.durum == "hata" and is_.hata and "AZURE_IMAGE_API_KEY" in is_.hata
    assert not (tmp_path / "kullanicilar").exists(), "düşen iş nesne bırakmaz"


def test_the_process_registers_a_worker_row_beats_and_exits_cleanly_on_sigterm(veritabani_url, depo_db,
                                                                              tmp_path):
    """`isciler` satırı açılışta, `son_kalp` ilerler (aralık testte 0,2 sn), SIGTERM → 0 ve satır silinir."""
    surec = subprocess.Popen([sys.executable, "isci.py", "--kalp-araligi", "0.2"], cwd=REPO,
                             env=_ortam(veritabani_url, tmp_path, KROMIS_ISCI_ES_ZAMANLI="2"),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        def _satir():
            with depo_db.connect() as c:
                return c.execute(text("SELECT konak, surum, es_zamanli, basladi, son_kalp FROM isciler")).first()

        son = time.monotonic() + 30
        satir = None
        while satir is None and time.monotonic() < son:
            assert surec.poll() is None, surec.stderr.read() if surec.stderr else ""
            satir = _satir()
            time.sleep(0.1)
        assert satir is not None, "işçi 30 sn içinde kaydolmadı"
        assert satir.es_zamanli == 2 and satir.surum and satir.konak
        ilk = satir.son_kalp
        son = time.monotonic() + 15
        while time.monotonic() < son:
            satir = _satir()
            if satir is not None and satir.son_kalp > ilk:
                break
            time.sleep(0.1)
        assert satir is not None and satir.son_kalp > ilk, "kalp ilerlemedi"
        assert satir.basladi < satir.son_kalp

        surec.send_signal(signal.SIGTERM)
        cikti, hata = surec.communicate(timeout=30)
    finally:
        if surec.poll() is None:
            surec.kill()
            surec.wait(timeout=10)
    assert surec.returncode == 0, hata
    olaylar = _olaylar(cikti)
    assert [o["olay"] for o in olaylar] == ["isci.basladi", "isci.sinyal", "isci.kapandi"], cikti
    assert olaylar[0]["es_zamanli"] == 2 and olaylar[0]["konak"] and olaylar[1]["sinyal"] == 15
    assert olaylar[0]["isci_id"] == olaylar[2]["isci_id"]
    assert _satir() is None, "kapanışta satır silinir"
    assert not (tmp_path / "hata.log").exists(), hata


def test_the_process_runs_a_maintenance_turn_at_startup_and_then_on_its_interval(veritabani_url, depo_db,
                                                                                  db_oturumu, kullanici, tmp_path):
    """Faz 2 / 10: ölü işçinin satırı ve süresi dolmuş iş, yeni işçi kalkar kalkmaz gider (açılış turu);
    `olay=bakim` sayıları söyler; sonra `--bakim-araligi`de bir tekrar (ikinci süresi dolmuş satır da gider)."""
    with Session(depo_db) as s:
        olu = kuyruk.isci_kaydet(s, "olu-konak", "0.0.0", 1, zaman.an() - dt.timedelta(hours=2))
        kuyruk.isci_kalp(s, olu.id, zaman.an() - dt.timedelta(hours=1))
        s.commit()
    eski = _ekle(db_oturumu, kullanici.id)
    db_oturumu.execute(text("UPDATE isler SET durum = 'hata', bitti = :b WHERE id = :id"),
                       {"b": zaman.an() - dt.timedelta(days=31), "id": eski})
    db_oturumu.commit()

    def _sayilar():
        with depo_db.connect() as c:
            return (c.execute(text("SELECT count(*) FROM isciler")).scalar_one(),
                    c.execute(text("SELECT count(*) FROM isler")).scalar_one())

    surec = subprocess.Popen([sys.executable, "isci.py", "--kalp-araligi", "0.2", "--bakim-araligi", "0.5"],
                             cwd=REPO, env=_ortam(veritabani_url, tmp_path, KROMIS_ISCI_ES_ZAMANLI="1"),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        son = time.monotonic() + 30
        while time.monotonic() < son and _sayilar() != (1, 0):
            assert surec.poll() is None, surec.stderr.read() if surec.stderr else ""
            time.sleep(0.1)
        assert _sayilar() == (1, 0), "açılış turu ölü satırı ve eski işi silmedi"
        # İkinci tur: aralık dolduktan sonra yeni bir eski satır da gider.
        ikinci = _ekle(db_oturumu, kullanici.id)
        db_oturumu.execute(text("UPDATE isler SET durum = 'iptal', bitti = :b WHERE id = :id"),
                           {"b": zaman.an() - dt.timedelta(days=31), "id": ikinci})
        db_oturumu.commit()
        son = time.monotonic() + 15
        while time.monotonic() < son and _sayilar() != (1, 0):
            time.sleep(0.1)
        assert _sayilar() == (1, 0), "aralıklı tur koşmadı"
        surec.send_signal(signal.SIGTERM)
        cikti, hata = surec.communicate(timeout=30)
    finally:
        if surec.poll() is None:
            surec.kill()
            surec.wait(timeout=10)
    assert surec.returncode == 0, hata
    olaylar = _olaylar(cikti)
    adlar = [o["olay"] for o in olaylar]
    assert adlar[:2] == ["isci.basladi", "bakim"] and adlar[-2:] == ["isci.sinyal", "isci.kapandi"], adlar
    bakimlar = [o for o in olaylar if o["olay"] == "bakim"]
    assert bakimlar[0]["silinen_isci"] == 1 and bakimlar[0]["silinen_is"] == 1 and bakimlar[0]["silinen_nesne"] == 0
    assert len(bakimlar) == 2 and bakimlar[1]["silinen_is"] == 1, "boş turlar olay düşürmez, dolu ikinci tur düşürür"
    assert _sayilar() == (0, 0), "kapanışta kendi satırı da silindi"
    assert not (tmp_path / "hata.log").exists(), hata


def test_the_process_keeps_beating_after_sigterm_until_the_draining_job_finishes(veritabani_url, depo_db,
                                                                                 db_oturumu, kullanici, tmp_path):
    """Gerçek süreç, yavaş sağlayıcı (4 sn): iş `calisiyor`ken SIGTERM → süreç kapanmaz, `son_kalp` ve
    işin `kalp_atisi` SIGTERM'den sonra da ilerler, iş `bitti`ye varır (medya satırı + nesne), sonra 0.
    Olay sırası: `isci.sinyal` → `is.bitti` → `isci.kapandi`."""
    is_id = _ekle(db_oturumu, kullanici.id)
    ortam = _ortam(veritabani_url, tmp_path, KROMIS_ISCI_ES_ZAMANLI="1", PYTHONPATH=_yavas_saglayici(tmp_path, 4.0))
    surec = subprocess.Popen([sys.executable, "isci.py", "--kalp-araligi", "0.2"], cwd=REPO, env=ortam,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        def _is_satiri():
            with depo_db.connect() as c:
                return c.execute(text("SELECT durum, kalp_atisi FROM isler WHERE id = :i"), {"i": is_id}).one()

        def _son_kalp():
            with depo_db.connect() as c:
                return c.execute(text("SELECT max(son_kalp) FROM isciler")).scalar_one()

        son = time.monotonic() + 30
        while time.monotonic() < son and _is_satiri().durum != "calisiyor":
            assert surec.poll() is None, surec.stderr.read() if surec.stderr else ""
            time.sleep(0.1)
        assert _is_satiri().durum == "calisiyor", "iş 30 sn içinde alınmadı"
        surec.send_signal(signal.SIGTERM)
        kalp1, atis1 = _son_kalp(), _is_satiri().kalp_atisi
        time.sleep(1.0)
        assert surec.poll() is None, "eldeki iş sürüyor: süreç SIGTERM'de kapanmamalı"
        kalp2, atis2 = _son_kalp(), _is_satiri().kalp_atisi
        assert kalp2 > kalp1, "SIGTERM'den sonra işçi kalbi sustu"
        assert atis2 > atis1, "SIGTERM'den sonra işin kalp_atisi tazelenmedi (bayat düşürmeye açık)"
        cikti, hata = surec.communicate(timeout=30)
    finally:
        if surec.poll() is None:
            surec.kill()
            surec.wait(timeout=10)
    assert surec.returncode == 0, hata
    is_ = _is(db_oturumu, is_id)
    assert is_.durum == "bitti" and is_.sonuc and len(is_.sonuc["medya"]) == 1, is_.hata
    adlar = [o["olay"] for o in _olaylar(cikti)]
    assert adlar[0] == "isci.basladi" and adlar[-1] == "isci.kapandi", adlar
    assert adlar.index("isci.sinyal") < adlar.index("is.bitti") < adlar.index("isci.kapandi"), adlar
    assert "bayat" not in adlar, "boşalan iş bayat düşürülmedi"
    assert _son_kalp() is None, "kapanışta satır silinir"
    assert not (tmp_path / "hata.log").exists(), hata


def test_the_process_rewrites_its_worker_row_when_it_disappears_underneath_it(veritabani_url, depo_db, tmp_path):
    """Satır dışarıdan silinir (başka işçinin ölü süpürmesi, admin): bir sonraki kalp turu onu AYNI `id`
    ve `basladi`yla geri yazar, `olay=isci.yeniden_kaydoldu` (WARNING) düşer; kapanışta yine silinir."""
    surec = subprocess.Popen([sys.executable, "isci.py", "--kalp-araligi", "0.2"], cwd=REPO,
                             env=_ortam(veritabani_url, tmp_path, KROMIS_ISCI_ES_ZAMANLI="1"),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        def _satir():
            with depo_db.connect() as c:
                return c.execute(text("SELECT id, basladi, son_kalp FROM isciler")).first()

        son = time.monotonic() + 30
        while time.monotonic() < son and _satir() is None:
            assert surec.poll() is None, surec.stderr.read() if surec.stderr else ""
            time.sleep(0.1)
        ilk = _satir()
        assert ilk is not None, "işçi 30 sn içinde kaydolmadı"
        with depo_db.begin() as c:
            c.execute(text("DELETE FROM isciler"))
        son = time.monotonic() + 15
        while time.monotonic() < son and _satir() is None:
            time.sleep(0.05)
        yeni = _satir()
        assert yeni is not None, "silinen satır kalp turunda geri yazılmadı"
        assert (yeni.id, yeni.basladi) == (ilk.id, ilk.basladi), "aynı kimlik, gerçek açılış anı"
        assert yeni.son_kalp > ilk.son_kalp
        surec.send_signal(signal.SIGTERM)
        cikti, hata = surec.communicate(timeout=30)
    finally:
        if surec.poll() is None:
            surec.kill()
            surec.wait(timeout=10)
    assert surec.returncode == 0, hata
    olaylar = _olaylar(cikti)
    yeniden = [o for o in olaylar if o["olay"] == "isci.yeniden_kaydoldu"]
    assert len(yeniden) == 1 and yeniden[0]["seviye"] == "WARNING" and yeniden[0]["isci_id"] == str(ilk.id), cikti
    assert [o["olay"] for o in olaylar][-1] == "isci.kapandi"
    assert _satir() is None, "kapanışta satır silinir"
    assert not (tmp_path / "hata.log").exists(), hata
