"""İş kuyruğu — `services/kuyruk.py` + göç `0004_isler` (Faz 2 / 1. görev).

Hepsi GERÇEK Postgres'e karşı (`depo_db`): sınanan şeylerin özü —
`FOR UPDATE SKIP LOCKED`, kısmi indeks, CHECK'in reddi, `ON DELETE CASCADE`,
`GREATEST` — SQLite'ta ya yok ya başka. Eş zamanlılık testleri iki `Session`
+ iki bağlantıyla, aynı süreçte (kilit sunucuda; belge, "Test stratejisi").

Dört soru:

  (i)   ALIM — iki alıcı aynı işi ALMAZ (100 tekrar, çift alım 0 — §1'in
        çıkış ölçütü); kilitli satır beklenmez, atlanır; sıra FIFO ve
        mikrosaniye; boş kuyruk `None`.
  (ii)  GEÇİŞLER — kalp/bitir/düşür yalnız `calisiyor`u, iptal yalnız
        `bekliyor`u değiştirir; bayat düşürme `hata`ya gider ve kuyruğa GERİ
        DÖNMEZ (K8); geç kalan işçi bayat düşürülmüş işi diriltemez; CHECK
        bilinmeyen tür/durumu reddeder.
  (iii) SINIR — iki kullanıcı depo düzeyinde izole; `_json` `istek`i dökmez;
        hesap silinince işler gider, işçi satırları kalır.
  (iv)  ŞEMA — ileri-geri-ileri + `alembic check` boş; kısmi indeksler
        gerçekten kısmi.
  (v)   SAKLAMA VE BAKIM (Faz 2 / 10) — `eskileri_sil` yalnız kapanmış ve
        30 günden eski satırları, yalnız verilen kullanıcının; `SilinenIs`
        kendi girdi dizinini ve referans verdiği dizinleri taşır;
        `girdi_referanslari`/`mevcut_isler` nesne süpürmesinin iki sorusu;
        `olu_iscileri_sil` kalbi eşikten uzun susan işçi satırını düşürür.
"""
from __future__ import annotations

import ast
import datetime as dt
import inspect
import os
import threading
import time
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services import ayar, hesap, kuyruk, tablolar, zaman

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ESIK = dt.timedelta(minutes=5)


@pytest.fixture(autouse=True)
def temiz(depo_db):
    """Dosyanın testleri aynı DB'yi paylaşır; her test boş kuyrukla başlar (işçi satırları da)."""
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM isler"))
        c.execute(text("DELETE FROM isciler"))
    yield


def _an(saniye: float = 0.0) -> dt.datetime:
    """Sabit bir başlangıçtan `saniye` sonrası — testler saatle oynamaz, `an` verir."""
    return dt.datetime(2026, 9, 17, 12, 0, 0, tzinfo=dt.UTC) + dt.timedelta(seconds=saniye)


def _ikinci_kullanici(db: Session) -> uuid.UUID:
    k = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                           dogrulandi_at=hesap.simdi())
    db.add(k)
    db.flush()
    return k.id


def _ekle(db: Session, kullanici_id: uuid.UUID, n: int = 1, *, bas: float = 0.0,
          adim: float = 0.000001) -> list[uuid.UUID]:
    """`n` iş, `olusturuldu` `adim` aralıklı (öntanımlı 1 µs: aynı saniye, farklı an)."""
    ids = []
    for i in range(n):
        is_ = kuyruk.ekle(db, kullanici_id, "generate", {"prompt": f"p{i}", "n": 1}, "m", 4,
                          an=_an(bas + i * adim))
        ids.append(is_.id)
    db.commit()
    return ids


def _durum(db: Session, is_id: uuid.UUID) -> str:
    return db.execute(text("SELECT durum FROM isler WHERE id = :id"), {"id": is_id}).scalar_one()


ISCI = uuid.uuid4()


# ── (i) alım ───────────────────────────────────────────────────────────

def test_enqueue_creates_a_pending_row_with_the_estimate_and_without_a_worker(db_oturumu, kullanici):
    is_ = kuyruk.ekle(db_oturumu, kullanici.id, "video", {"prompt": "kedi", "duration": 6}, "m-v", 60,
                      an=_an())
    db_oturumu.commit()
    db_oturumu.refresh(is_)
    assert isinstance(is_.id, uuid.UUID)
    assert (is_.durum, is_.tur, is_.model, is_.kredi_tahmini) == ("bekliyor", "video", "m-v", 60)
    assert is_.istek == {"prompt": "kedi", "duration": 6}
    assert is_.olusturuldu == _an()
    assert is_.isci_id is None and is_.basladi is None and is_.bitti is None and is_.kalp_atisi is None
    assert is_.sonuc is None and is_.hata is None
    # `an` verilmeden de girer: rota `zaman.an()` demek zorunda kalmaz.
    oncesi = zaman.an()
    serbest = kuyruk.ekle(db_oturumu, kullanici.id, "generate", {}, "m", 4)
    assert serbest.olusturuldu >= oncesi


def test_pickup_is_fifo_by_creation_time_at_microsecond_resolution(db_oturumu, kullanici):
    """Aynı saniyede sıraya giren dört iş, girildiği sırada alınır — Python'un mikrosaniyesi sayesinde."""
    ids = _ekle(db_oturumu, kullanici.id, 4)
    alinan = []
    for _ in range(4):
        is_ = kuyruk.al(db_oturumu, ISCI, _an(10))
        assert is_ is not None
        alinan.append(is_.id)
        db_oturumu.commit()
    assert alinan == ids
    assert kuyruk.al(db_oturumu, ISCI, _an(11)) is None, "boş kuyruk None"


def test_pickup_marks_the_job_running_and_stamps_worker_start_and_heartbeat(db_oturumu, kullanici):
    (is_id,) = _ekle(db_oturumu, kullanici.id)
    is_ = kuyruk.al(db_oturumu, ISCI, _an(3))
    db_oturumu.commit()
    assert is_ is not None and is_.id == is_id
    assert is_.durum == "calisiyor" and is_.isci_id == ISCI
    assert is_.basladi == _an(3) and is_.kalp_atisi == _an(3) and is_.bitti is None
    # RETURNING'in dediği DB'nin dediği: taze bir oturum aynı şeyi görür.
    with Session(db_oturumu.get_bind()) as taze:
        satir = taze.get(tablolar.Is, is_id)
        assert satir is not None and satir.durum == "calisiyor" and satir.isci_id == ISCI


def test_pickup_returns_none_on_an_empty_queue_and_does_not_touch_other_states(db_oturumu, kullanici):
    (is_id,) = _ekle(db_oturumu, kullanici.id)
    assert kuyruk.iptal(db_oturumu, kullanici.id, is_id, an=_an(1)) is True
    db_oturumu.commit()
    assert kuyruk.al(db_oturumu, ISCI, _an(2)) is None
    assert _durum(db_oturumu, is_id) == "iptal"


def test_two_sessions_picking_concurrently_never_take_the_same_job_in_100_rounds(depo_db, db_oturumu, kullanici):
    """§1'in çıkış ölçütü: iki eş zamanlı alıcı, 100 tekrar, çift alım 0.

    A alır ve COMMIT ETMEZ (satır kilitli), B o sırada alır: `SKIP LOCKED`
    A'nın satırını atlayıp sıradakini vermeli. Sonra ikisi commit. Yarış
    burada zamanlamaya bırakılmıyor, kilit gerçekten tutuluyor — deterministik.
    """
    ids = _ekle(db_oturumu, kullanici.id, 200)
    alinan: list[uuid.UUID] = []
    with Session(depo_db) as a, Session(depo_db) as b:
        for tur in range(100):
            ia = kuyruk.al(a, uuid.uuid4(), _an(100 + tur))
            ib = kuyruk.al(b, uuid.uuid4(), _an(100 + tur))
            assert ia is not None and ib is not None, f"tur {tur}: kuyruk erken boşaldı"
            assert ia.id != ib.id, f"tur {tur}: ÇİFT ALIM {ia.id}"
            alinan += [ia.id, ib.id]
            a.commit()
            b.commit()
    assert len(set(alinan)) == 200 and set(alinan) == set(ids)
    assert kuyruk.al(db_oturumu, ISCI, _an(300)) is None


def test_two_threads_racing_on_the_queue_take_every_job_exactly_once(depo_db, db_oturumu, kullanici):
    """Aynı testin zamanlamaya bırakılmış ikizi: iki iş parçacığı, bariyerle aynı anda, 60 iş."""
    ids = _ekle(db_oturumu, kullanici.id, 60)
    bariyer = threading.Barrier(2)
    sonuclar: dict[int, list[uuid.UUID]] = {0: [], 1: []}
    hatalar: list[BaseException] = []

    def _isci(no: int) -> None:
        try:
            with Session(depo_db) as s:
                isci = uuid.uuid4()
                bariyer.wait(5)
                while True:
                    is_ = kuyruk.al(s, isci, _an(500))
                    if is_ is None:
                        s.rollback()
                        return
                    sonuclar[no].append(is_.id)
                    s.commit()
        except BaseException as e:      # noqa: BLE001 — iş parçacığında yutulmasın, ana akışa taşınsın
            hatalar.append(e)

    parcalar = [threading.Thread(target=_isci, args=(i,)) for i in (0, 1)]
    for p in parcalar:
        p.start()
    for p in parcalar:
        p.join(30)
    assert not hatalar, hatalar
    hepsi = sonuclar[0] + sonuclar[1]
    assert len(hepsi) == 60 and len(set(hepsi)) == 60 and set(hepsi) == set(ids)
    assert sonuclar[0] and sonuclar[1], "iki işçi de iş almalı (biri hep kilitte beklemedi)"


def test_a_locked_row_is_skipped_not_waited_for(depo_db, db_oturumu, kullanici):
    """`SKIP LOCKED`in ölçüsü: A kilidi tutarken B'nin `al`ı saniyeler beklemez, anında başka iş alır."""
    ids = _ekle(db_oturumu, kullanici.id, 2)
    with Session(depo_db) as a, Session(depo_db) as b:
        ia = kuyruk.al(a, ISCI, _an(1))
        basla = time.monotonic()
        ib = kuyruk.al(b, uuid.uuid4(), _an(1))
        gecen = time.monotonic() - basla
        assert ia is not None and ib is not None and {ia.id, ib.id} == set(ids)
        assert gecen < 1.0, f"kilitli satırda beklendi: {gecen:.2f} sn"
        a.commit()
        b.commit()


def test_cancel_racing_with_pickup_lets_exactly_one_side_win(depo_db, db_oturumu, kullanici):
    """Kullanıcı iptal eder, işçi aynı anda alır: `UPDATE … WHERE durum='bekliyor'` kilidi bekler, 0 satır görür.

    Ters sırada (iptal önce commit'lenmişse) `al` o satırı hiç görmez —
    `test_pickup_returns_none_on_an_empty_queue_and_does_not_touch_other_states`.
    """
    (is_id,) = _ekle(db_oturumu, kullanici.id)
    sonuc: list[bool] = []
    with Session(depo_db) as a:
        alinan = kuyruk.al(a, ISCI, _an(1))
        assert alinan is not None and alinan.id == is_id

        def _iptal() -> None:
            with Session(depo_db) as b:
                sonuc.append(kuyruk.iptal(b, kullanici.id, is_id, an=_an(2)))
                b.commit()

        p = threading.Thread(target=_iptal)
        p.start()
        p.join(0.5)
        assert p.is_alive(), "iptal kilidi beklemeli, atlamamalı (SKIP LOCKED yalnız alımda)"
        a.commit()
        p.join(10)
    assert sonuc == [False]
    assert _durum(db_oturumu, is_id) == "calisiyor"


# ── (ii) geçişler ──────────────────────────────────────────────────────

def test_heartbeat_moves_only_a_running_job(db_oturumu, kullanici):
    a, b = _ekle(db_oturumu, kullanici.id, 2)
    assert kuyruk.kalp(db_oturumu, a, _an(1)) is False, "bekliyor işin kalbi yok"
    is_ = kuyruk.al(db_oturumu, ISCI, _an(2))
    assert is_ is not None and is_.id == a
    assert kuyruk.kalp(db_oturumu, a, _an(30)) is True
    db_oturumu.commit()
    db_oturumu.expire_all()
    assert db_oturumu.get(tablolar.Is, a).kalp_atisi == _an(30)
    assert db_oturumu.get(tablolar.Is, b).kalp_atisi is None


def test_finish_moves_running_to_done_and_records_the_result(db_oturumu, kullanici):
    (is_id,) = _ekle(db_oturumu, kullanici.id)
    kuyruk.al(db_oturumu, ISCI, _an(1))
    assert kuyruk.bitir(db_oturumu, is_id, {"medya": ["ab12cd34ef56"]}, _an(90)) is True
    db_oturumu.commit()
    db_oturumu.expire_all()
    satir = db_oturumu.get(tablolar.Is, is_id)
    assert satir.durum == "bitti" and satir.sonuc == {"medya": ["ab12cd34ef56"]}
    assert satir.bitti == _an(90) and satir.basladi == _an(1) and satir.hata is None


def test_fail_moves_running_to_error_and_redacts_secrets_in_the_message(db_oturumu, kullanici):
    """Sağlayıcı hatası anahtar taşıyabilir; redaksiyon YAZAN yerde (çağıran unutamaz)."""
    (is_id,) = _ekle(db_oturumu, kullanici.id)
    kuyruk.al(db_oturumu, ISCI, _an(1))
    gizli = "sk-" + "a" * 40
    assert kuyruk.dusur(db_oturumu, is_id, f"401 Unauthorized: bad key {gizli}", _an(5)) is True
    db_oturumu.commit()
    db_oturumu.expire_all()
    satir = db_oturumu.get(tablolar.Is, is_id)
    assert satir.durum == "hata" and satir.bitti == _an(5) and satir.sonuc is None
    assert gizli not in satir.hata and "[REDACTED_API_KEY]" in satir.hata
    assert satir.hata.startswith("401 Unauthorized")


def test_finish_and_fail_refuse_a_job_that_is_not_running(db_oturumu, kullanici):
    """Geçiş kuralı `WHERE`de: bekliyor/bitti/hata/iptal'den `bitir`/`dusur` 0 satır, durum değişmez."""
    bekleyen, biten, dusen, iptal_edilen = _ekle(db_oturumu, kullanici.id, 4)
    for _ in range(2):
        kuyruk.al(db_oturumu, ISCI, _an(1))           # bekleyen kalsın diye: al → hemen kapat
    # İlk iki iş `calisiyor`: birini bitir, birini düşür. (FIFO: bekleyen, biten sırasıyla alındı.)
    assert kuyruk.bitir(db_oturumu, bekleyen, {"medya": []}, _an(2)) is True
    assert kuyruk.dusur(db_oturumu, biten, "x", _an(2)) is True
    assert kuyruk.iptal(db_oturumu, kullanici.id, iptal_edilen, an=_an(2)) is True
    db_oturumu.commit()
    durumlar = {bekleyen: "bitti", biten: "hata", dusen: "bekliyor", iptal_edilen: "iptal"}
    for is_id, beklenen in durumlar.items():
        assert _durum(db_oturumu, is_id) == beklenen
        assert kuyruk.bitir(db_oturumu, is_id, {"medya": []}, _an(3)) is False
        assert kuyruk.dusur(db_oturumu, is_id, "gec", _an(3)) is False
        assert kuyruk.kalp(db_oturumu, is_id, _an(3)) is False
        assert _durum(db_oturumu, is_id) == beklenen
    db_oturumu.commit()


def test_cancel_only_affects_a_pending_job_of_the_owner(db_oturumu, kullanici):
    bekleyen, calisan = _ekle(db_oturumu, kullanici.id, 2)
    kuyruk.al(db_oturumu, ISCI, _an(1))              # FIFO: `bekleyen` alındı → yer değiştir
    bekleyen, calisan = calisan, bekleyen
    baskasi = _ikinci_kullanici(db_oturumu)
    assert kuyruk.iptal(db_oturumu, baskasi, bekleyen, an=_an(2)) is False, "başkasının işi 'yok'"
    assert kuyruk.iptal(db_oturumu, kullanici.id, calisan, an=_an(2)) is False, "calisiyor iptal edilmez"
    assert kuyruk.iptal(db_oturumu, kullanici.id, uuid.uuid4(), an=_an(2)) is False
    assert kuyruk.iptal(db_oturumu, kullanici.id, bekleyen, an=_an(2)) is True
    assert kuyruk.iptal(db_oturumu, kullanici.id, bekleyen, an=_an(3)) is False, "ikinci iptal 0 satır"
    db_oturumu.commit()
    db_oturumu.expire_all()
    satir = db_oturumu.get(tablolar.Is, bekleyen)
    assert satir.durum == "iptal" and satir.bitti == _an(2) and satir.basladi is None
    assert _durum(db_oturumu, calisan) == "calisiyor"


def test_stale_running_jobs_drop_to_error_and_are_never_requeued(db_oturumu, kullanici):
    """K8: kalp `esik`ten uzun susmuşsa iş `hata` ("isci yanit vermiyor"), kuyruğa GERİ DÖNMEZ.

    Eşik KESİN küçük (`kalp_atisi < an - esik`): tam eşikteki iş düşmez;
    `bekliyor` işlere dokunulmaz; taze kalpli iş kalır.
    """
    bayat, tam_esik, taze, bekleyen = _ekle(db_oturumu, kullanici.id, 4)
    for _ in range(3):
        kuyruk.al(db_oturumu, ISCI, _an(0))
    an = _an(1000)
    kuyruk.kalp(db_oturumu, bayat, an - ESIK - dt.timedelta(microseconds=1))
    kuyruk.kalp(db_oturumu, tam_esik, an - ESIK)
    kuyruk.kalp(db_oturumu, taze, an - dt.timedelta(seconds=30))
    db_oturumu.commit()
    assert kuyruk.bayatlari_dusur(db_oturumu, an, ESIK) == 1
    db_oturumu.commit()
    db_oturumu.expire_all()
    dusen = db_oturumu.get(tablolar.Is, bayat)
    assert dusen.durum == "hata" and dusen.hata == kuyruk.BAYAT_HATASI == "isci yanit vermiyor"
    assert dusen.bitti == an and dusen.isci_id == ISCI, "kim koştu kaydı durur"
    assert _durum(db_oturumu, tam_esik) == "calisiyor" and _durum(db_oturumu, taze) == "calisiyor"
    assert _durum(db_oturumu, bekleyen) == "bekliyor"
    # Kuyrukta hâlâ yalnız `bekleyen` var: düşen iş geri gelmedi.
    sirada = kuyruk.al(db_oturumu, uuid.uuid4(), an)
    assert sirada is not None and sirada.id == bekleyen
    assert kuyruk.al(db_oturumu, uuid.uuid4(), an) is None
    assert kuyruk.bayatlari_dusur(db_oturumu, an, ESIK) == 0, "idempotent"


def test_a_late_worker_cannot_resurrect_a_job_that_was_dropped_as_stale(db_oturumu, kullanici):
    """Bayat düşürülen işin işçisi sonra `bitir` derse 0 satır: sonuç yazılmaz, işçi telafiye gider (3. görev)."""
    (is_id,) = _ekle(db_oturumu, kullanici.id)
    kuyruk.al(db_oturumu, ISCI, _an(0))
    db_oturumu.commit()
    assert kuyruk.bayatlari_dusur(db_oturumu, _an(0) + ESIK + dt.timedelta(seconds=1), ESIK) == 1
    assert kuyruk.bitir(db_oturumu, is_id, {"medya": ["ab12cd34ef56"]}, _an(400)) is False
    assert kuyruk.kalp(db_oturumu, is_id, _an(400)) is False
    db_oturumu.commit()
    db_oturumu.expire_all()
    satir = db_oturumu.get(tablolar.Is, is_id)
    assert satir.durum == "hata" and satir.sonuc is None and satir.hata == kuyruk.BAYAT_HATASI


def test_check_constraints_reject_an_unknown_type_and_status(db_oturumu, kullanici):
    """CHECK gerçekten reddediyor — `alembic check` CHECK'leri karşılaştırmaz (test_tablolar'ın gerekçesi)."""
    with pytest.raises(IntegrityError) as hata:
        kuyruk.ekle(db_oturumu, kullanici.id, "chat", {}, "m", 1, an=_an())
    assert "ck_isler_tur_kumesi" in str(hata.value)
    db_oturumu.rollback()
    with pytest.raises(IntegrityError) as hata:
        db_oturumu.execute(text("INSERT INTO isler (kullanici_id, tur, durum, istek, model, kredi_tahmini) "
                                "VALUES (:k, 'generate', 'askida', '{}', 'm', 1)"), {"k": kullanici.id})
    assert "ck_isler_durum_kumesi" in str(hata.value)
    db_oturumu.rollback()
    with pytest.raises(IntegrityError) as hata:
        kuyruk.ekle(db_oturumu, uuid.uuid4(), "generate", {}, "m", 1, an=_an())
    assert "fk_isler_kullanici_id_kullanicilar" in str(hata.value)
    db_oturumu.rollback()


# ── (iii) sınır ────────────────────────────────────────────────────────

def test_active_count_counts_pending_and_running_only(db_oturumu, kullanici):
    ids = _ekle(db_oturumu, kullanici.id, 5)
    assert kuyruk.aktif_sayisi(db_oturumu, kullanici.id) == 5
    kuyruk.al(db_oturumu, ISCI, _an(1))
    kuyruk.al(db_oturumu, ISCI, _an(1))
    assert kuyruk.aktif_sayisi(db_oturumu, kullanici.id) == 5, "calisiyor da aktif"
    kuyruk.bitir(db_oturumu, ids[0], {"medya": []}, _an(2))
    kuyruk.dusur(db_oturumu, ids[1], "x", _an(2))
    kuyruk.iptal(db_oturumu, kullanici.id, ids[2], an=_an(2))
    db_oturumu.commit()
    assert kuyruk.aktif_sayisi(db_oturumu, kullanici.id) == 2
    assert kuyruk.aktif_sayisi(db_oturumu, uuid.uuid4()) == 0


def test_listing_is_newest_first_limited_and_filtered_by_the_last_change(db_oturumu, kullanici):
    """`since` = "şu andan beri ne DEĞİŞTİ": `olusturuldu`/`basladi`/`bitti`nin en büyüğü (SSE'nin sorusu)."""
    ids = _ekle(db_oturumu, kullanici.id, 3, bas=0, adim=10)      # 0, 10, 20 sn
    liste = kuyruk.listele(db_oturumu, kullanici.id)
    assert [i["id"] for i in liste] == [str(x) for x in reversed(ids)], "en yeni üstte"
    assert [i["id"] for i in kuyruk.listele(db_oturumu, kullanici.id, limit=2)] == [str(ids[2]), str(ids[1])]
    # 15 sn'den sonra: yalnız 20 sn'de sıraya giren.
    assert [i["id"] for i in kuyruk.listele(db_oturumu, kullanici.id, since=_an(15))] == [str(ids[2])]
    # En eski iş 30 sn'de alınıp 40 sn'de bitti: 25 sn'den beri DEĞİŞENLER ona da ids[2]'ye de dokunmalı… ids[2] 20'de girdi, 25'ten sonra değişmedi → yalnız ids[0].
    kuyruk.al(db_oturumu, ISCI, _an(30))
    kuyruk.bitir(db_oturumu, ids[0], {"medya": []}, _an(40))
    db_oturumu.commit()
    assert [i["id"] for i in kuyruk.listele(db_oturumu, kullanici.id, since=_an(25))] == [str(ids[0])]
    assert [i["id"] for i in kuyruk.listele(db_oturumu, kullanici.id, since=_an(35))] == [str(ids[0])]
    assert kuyruk.listele(db_oturumu, kullanici.id, since=_an(40)) == [], "`since` kesin büyük"
    assert kuyruk.listele(db_oturumu, uuid.uuid4()) == []


def test_the_dump_carries_the_contract_fields_and_never_the_request_body(db_oturumu, kullanici):
    """`_json`: on üç anahtar, `istek` YOK (prompt/klasör `medya`da, referans anahtarları iç iş),
    damgalar `medya` biçiminde. `arena_id`/`folder_id` `istek`ten dökülen iki alan (Faz 2 / 5:
    panel gruplaması ve önizlemenin klasörü) — ikisi de `medya`da zaten görünür, prompt değil."""
    is_ = kuyruk.ekle(db_oturumu, kullanici.id, "edit", {"prompt": "GİZLİ", "kaynaklar": ["k1"]}, "m", 8,
                      an=_an())
    db_oturumu.commit()
    dokum = kuyruk.listele(db_oturumu, kullanici.id)[0]
    assert list(dokum) == ["id", "tur", "durum", "model", "kredi_tahmini", "anahtar_kaynagi",
                           "olusturuldu", "basladi", "bitti", "sonuc", "hata", "arena_id", "folder_id"]
    assert dokum["arena_id"] is None and dokum["folder_id"] is None
    assert dokum["anahtar_kaynagi"] is None, "`ekle` kaynak verilmeden çağrıldı (Faz 2 / 6: rota verir)"
    assert "istek" not in dokum and "GİZLİ" not in repr(dokum) and "isci_id" not in dokum
    # Damgalar DİLİMLİ UTC, `Z` sonekli (Faz 2 / 10): panel `new Date()` ile karşılaştırıyor.
    assert dokum["id"] == str(is_.id) and dokum["olusturuldu"] == zaman.damga_utc(_an()) == "2026-09-17T12:00:00Z"
    assert dokum["basladi"] is None and dokum["bitti"] is None and dokum["sonuc"] is None
    kuyruk.al(db_oturumu, ISCI, _an(5))
    kuyruk.bitir(db_oturumu, is_.id, {"medya": ["ab12cd34ef56"]}, _an(9))
    db_oturumu.commit()
    dokum = kuyruk.listele(db_oturumu, kullanici.id)[0]
    assert dokum["basladi"] == zaman.damga_utc(_an(5)) and dokum["bitti"] == zaman.damga_utc(_an(9))
    assert dokum["basladi"].endswith("Z") and dt.datetime.fromisoformat(dokum["bitti"]) == _an(9)
    assert dokum["sonuc"] == {"medya": ["ab12cd34ef56"]} and dokum["durum"] == "bitti"
    # Kaynak düzeyinde de: `_json` `istek`ten yalnız İKİ anahtar okur (`.get("arena_id")`,
    # `.get("folder_id")` — Faz 2 / 5), başka hiçbir anahtar değil; `kalp_atisi`/`isci_id` hiç.
    govde = ast.parse(inspect.getsource(kuyruk._json))
    adlar = {d.attr for d in ast.walk(govde) if isinstance(d, ast.Attribute)}
    assert "kalp_atisi" not in adlar and "isci_id" not in adlar
    okunan = {c.args[0].value for c in ast.walk(govde)
              if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "get"
              and c.args and isinstance(c.args[0], ast.Constant)}
    assert okunan == {"arena_id", "folder_id"}, okunan


def test_two_users_are_isolated_at_the_repository_layer(db_oturumu, kullanici):
    a = kullanici.id
    b = _ikinci_kullanici(db_oturumu)
    ia = _ekle(db_oturumu, a, 2)
    ib = _ekle(db_oturumu, b, 1, bas=1)          # 1 sn sonra: FIFO iddiası bağ kurmasın
    assert {i["id"] for i in kuyruk.listele(db_oturumu, a)} == {str(x) for x in ia}
    assert [i["id"] for i in kuyruk.listele(db_oturumu, b)] == [str(ib[0])]
    assert kuyruk.aktif_sayisi(db_oturumu, a) == 2 and kuyruk.aktif_sayisi(db_oturumu, b) == 1
    assert kuyruk.iptal(db_oturumu, b, ia[0], an=_an(1)) is False
    assert kuyruk.iptal(db_oturumu, a, ib[0], an=_an(1)) is False
    assert _durum(db_oturumu, ia[0]) == "bekliyor" and _durum(db_oturumu, ib[0]) == "bekliyor"
    # Kuyruk ise KÜRESEL FIFO: işçi kimin işi olduğuna bakmaz.
    sira = [kuyruk.al(db_oturumu, ISCI, _an(2)).id for _ in range(3)]
    assert sira == ia + ib
    db_oturumu.commit()


def test_deleting_the_user_cascades_to_their_jobs_but_worker_rows_survive(db_oturumu, kullanici):
    b = _ikinci_kullanici(db_oturumu)
    _ekle(db_oturumu, kullanici.id, 2)
    (ib,) = _ekle(db_oturumu, b, 1)
    isci = kuyruk.isci_kaydet(db_oturumu, "konak-1", "0.0.0", 1, _an())
    db_oturumu.commit()
    db_oturumu.execute(text("DELETE FROM kullanicilar WHERE id = :id"), {"id": kullanici.id})
    db_oturumu.commit()
    kalan = db_oturumu.scalars(select(tablolar.Is.id)).all()
    assert kalan == [ib]
    assert db_oturumu.get(tablolar.Isci, isci.id) is not None


def test_worker_registration_heartbeat_and_deregistration(db_oturumu, kullanici):
    """İşçi açılışta satır, 30 sn'de bir kalp, kapanışta silme; işin `isci_id`si işçi gidince de durur."""
    isci = kuyruk.isci_kaydet(db_oturumu, "fly-abc", "0.23.1", 2, _an())
    db_oturumu.commit()
    db_oturumu.refresh(isci)
    assert isinstance(isci.id, uuid.UUID)
    assert (isci.konak, isci.surum, isci.es_zamanli) == ("fly-abc", "0.23.1", 2)
    assert isci.basladi == _an() and isci.son_kalp == _an()
    assert kuyruk.isci_kalp(db_oturumu, isci.id, _an(30)) is True
    db_oturumu.commit()
    db_oturumu.refresh(isci)
    assert isci.son_kalp == _an(30) and isci.basladi == _an()
    (is_id,) = _ekle(db_oturumu, kullanici.id)
    kuyruk.al(db_oturumu, isci.id, _an(31))
    db_oturumu.commit()
    assert kuyruk.isci_sil(db_oturumu, isci.id) is True
    assert kuyruk.isci_sil(db_oturumu, isci.id) is False
    assert kuyruk.isci_kalp(db_oturumu, isci.id, _an(60)) is False
    db_oturumu.commit()
    db_oturumu.expire_all()
    assert db_oturumu.get(tablolar.Is, is_id).isci_id == isci.id, "FK yok: 'kim koştu' kaydı durur"


# ── (v) saklama ve bakım (Faz 2 / 10) ─────────────────────────────────

SAKLAMA = dt.timedelta(days=30)
# Bakım anı: sabit başlangıçtan 40 gün sonra — "30 günden eski" ile "taze" arası yer kalsın.
BAKIM_ANI = _an(40 * 86400)


def _kapat(db: Session, is_id: uuid.UUID, durum: str, bitti: dt.datetime) -> None:
    """Satırı doğrudan kapatır (`al` FIFO'nun başını alır, belirli bir işi değil): `durum`, `bitti`."""
    db.execute(text("UPDATE isler SET durum = :d, bitti = :b, isci_id = :i WHERE id = :id"),
               {"d": durum, "b": bitti, "i": ISCI if durum != "iptal" else None, "id": is_id})


def test_retention_deletes_only_closed_jobs_older_than_the_window_and_only_the_owners(db_oturumu, kullanici):
    """`eskileri_sil`: kapanmış (`bitti`/`hata`/`iptal`) VE `bitti < an - saklama` — üçü de gider;
    tam sınırdaki, taze kapanan, `bekliyor` ve `calisiyor` KALIR; başka kullanıcının eski işi
    kullanıcı imzası yüzünden DOKUNULMAZ (RLS'te de ancak o kiracının bağlamında silinebilir).
    `saklama_sahipleri` iki sahibi de sayar; ikinci çağrı 0 (idempotent)."""
    b = _ikinci_kullanici(db_oturumu)
    eski_bitti, eski_hata, eski_iptal, sinir, taze, bekleyen, calisan = _ekle(db_oturumu, kullanici.id, 7,
                                                                          adim=1.0)
    (b_eski,) = _ekle(db_oturumu, b, bas=100)
    eski_an = BAKIM_ANI - SAKLAMA - dt.timedelta(seconds=1)
    _kapat(db_oturumu, eski_bitti, "bitti", eski_an)
    _kapat(db_oturumu, eski_hata, "hata", eski_an)
    _kapat(db_oturumu, eski_iptal, "iptal", eski_an)
    _kapat(db_oturumu, sinir, "bitti", BAKIM_ANI - SAKLAMA)          # tam sınır: `<` kesin, kalır
    _kapat(db_oturumu, taze, "hata", BAKIM_ANI - dt.timedelta(days=1))
    # `calisan` eski bir kalple `calisiyor`: yaşı ne olursa olsun saklama ona dokunmaz (bayat düşürmenin işi).
    db_oturumu.execute(text("UPDATE isler SET durum = 'calisiyor', basladi = :a, kalp_atisi = :a, isci_id = :i "
                            "WHERE id = :id"), {"a": _an(0), "i": ISCI, "id": calisan})
    _kapat(db_oturumu, b_eski, "bitti", eski_an)
    db_oturumu.commit()

    assert kuyruk.saklama_sahipleri(db_oturumu, BAKIM_ANI, SAKLAMA) == sorted([kullanici.id, b])
    silinenler = kuyruk.eskileri_sil(db_oturumu, kullanici.id, BAKIM_ANI, SAKLAMA)
    db_oturumu.commit()
    assert {s.is_id for s in silinenler} == {eski_bitti, eski_hata, eski_iptal}
    assert all(s.kullanici_id == kullanici.id for s in silinenler)
    kalan = set(db_oturumu.scalars(select(tablolar.Is.id)))
    assert kalan == {sinir, taze, bekleyen, calisan, b_eski}, "sınır, taze ve aktifler durur; B'nin işi dokunulmaz"
    assert kuyruk.eskileri_sil(db_oturumu, kullanici.id, BAKIM_ANI, SAKLAMA) == [], "idempotent"
    assert kuyruk.saklama_sahipleri(db_oturumu, BAKIM_ANI, SAKLAMA) == [b]
    assert [s.is_id for s in kuyruk.eskileri_sil(db_oturumu, b, BAKIM_ANI, SAKLAMA)] == [b_eski]
    db_oturumu.commit()
    assert kuyruk.saklama_sahipleri(db_oturumu, BAKIM_ANI, SAKLAMA) == []


def test_a_deleted_job_reports_its_own_input_directory_and_the_ones_its_request_references(db_oturumu, kullanici):
    """`SilinenIs.girdi_dizinleri`: kendi `isler/<id>/` dizini + `istek.girdiler`/`son_kare`
    anahtarlarının dizinleri (yeniden gönderilen iş eskisinin girdilerine bakar, Faz 2 / 5);
    `girdi_referanslari` KALAN satırların anahtarlarını verir (isteğe bağlı kullanıcı süzgeci),
    `mevcut_isler` hangi id'lerin hâlâ satırı var — nesne süpürmesi ikisini sorar (services/isci.py)."""
    b = _ikinci_kullanici(db_oturumu)
    eski = uuid.uuid4()
    referans = ayar.is_dizini(kullanici.id, eski) + "upload.png"
    yeniden = kuyruk.ekle(db_oturumu, kullanici.id, "animate",
                          {"prompt": "p", "girdiler": [{"ad": "upload.png", "anahtar": referans}],
                           "son_kare": {"ad": "son_kare.png", "anahtar": ayar.is_dizini(kullanici.id, eski) + "son_kare.png"}},
                          "m", 4, an=_an())
    kendi = kuyruk.ekle(db_oturumu, kullanici.id, "edit", {"prompt": "p", "girdiler": [
        {"ad": "ref1.png", "anahtar": "KENDI"}]}, "m", 4, an=_an(1))
    kendi.istek = {**kendi.istek, "girdiler": [{"ad": "ref1.png", "anahtar": ayar.is_dizini(kullanici.id, kendi.id) + "ref1.png"}]}
    b_is = kuyruk.ekle(db_oturumu, b, "edit", {"prompt": "p", "girdiler": [{"ad": "x.png", "anahtar": ayar.is_dizini(b, uuid.uuid4()) + "x.png"}]},
                       "m", 4, an=_an(2))
    duz = kuyruk.ekle(db_oturumu, kullanici.id, "generate", {"prompt": "p"}, "m", 4, an=_an(3))
    db_oturumu.commit()

    hepsi = kuyruk.girdi_referanslari(db_oturumu)
    assert hepsi == {referans, ayar.is_dizini(kullanici.id, eski) + "son_kare.png",
                     ayar.is_dizini(kullanici.id, kendi.id) + "ref1.png", b_is.istek["girdiler"][0]["anahtar"]}
    assert kuyruk.girdi_referanslari(db_oturumu, b) == {b_is.istek["girdiler"][0]["anahtar"]}
    assert kuyruk.girdi_referanslari(db_oturumu, uuid.uuid4()) == set()
    assert kuyruk.mevcut_isler(db_oturumu, [yeniden.id, eski, duz.id]) == {yeniden.id, duz.id}
    assert kuyruk.mevcut_isler(db_oturumu, []) == set()
    assert kuyruk._girdi_anahtarlari(yeniden.istek) == [referans, ayar.is_dizini(kullanici.id, eski) + "son_kare.png"]
    assert kuyruk._girdi_anahtarlari(None) == [] and kuyruk._girdi_anahtarlari({"girdiler": [{"ad": "anahtarsiz"}]}) == []

    _kapat(db_oturumu, yeniden.id, "hata", BAKIM_ANI - SAKLAMA - dt.timedelta(days=1))
    db_oturumu.commit()
    (silinen,) = kuyruk.eskileri_sil(db_oturumu, kullanici.id, BAKIM_ANI, SAKLAMA)
    db_oturumu.commit()
    assert silinen.is_id == yeniden.id and silinen.kullanici_id == kullanici.id
    assert silinen.girdi_dizinleri == {ayar.is_dizini(kullanici.id, yeniden.id), ayar.is_dizini(kullanici.id, eski)}
    assert kuyruk.girdi_referanslari(db_oturumu, kullanici.id) == {
        ayar.is_dizini(kullanici.id, kendi.id) + "ref1.png"}, "silinen satırın referansları listeden düştü"


def test_input_references_tolerate_a_request_whose_girdiler_is_not_an_array(db_oturumu, kullanici):
    """`jsonb_array_elements` skalerde HATA verir ("cannot extract elements from a scalar"): `girdiler`
    JSON `null` (SQL NULL değil — `COALESCE` görmez), dize ya da nesne olan TEK satır her bakım turunu
    düşürürdü, hem de satırlar silinip dizinler öksüz kaldıktan sonra. `jsonb_typeof` süzer; `son_kare`
    `null` da sorun değil (`?` skalerde `false`)."""
    referans = ayar.is_dizini(kullanici.id, uuid.uuid4()) + "upload.png"
    kuyruk.ekle(db_oturumu, kullanici.id, "edit", {"prompt": "p", "girdiler": [{"ad": "upload.png", "anahtar": referans}]},
                "m", 4, an=_an())
    kuyruk.ekle(db_oturumu, kullanici.id, "generate", {"prompt": "p", "girdiler": None, "son_kare": None}, "m", 4, an=_an(1))
    kuyruk.ekle(db_oturumu, kullanici.id, "generate", {"prompt": "p", "girdiler": "bozuk"}, "m", 4, an=_an(2))
    kuyruk.ekle(db_oturumu, kullanici.id, "generate", {"prompt": "p", "girdiler": {"anahtar": "nesne/degil.png"}}, "m", 4, an=_an(3))
    db_oturumu.commit()
    assert kuyruk.girdi_referanslari(db_oturumu) == {referans}
    assert kuyruk.girdi_referanslari(db_oturumu, kullanici.id) == {referans}


def test_dead_worker_rows_are_removed_past_the_heartbeat_threshold_and_live_ones_stay(db_oturumu, kullanici):
    """9'un devri: SIGKILL'le ölen işçi kendi satırını silemez; `olu_iscileri_sil` `son_kalp < an - esik`
    satırları düşürür (eşik bayat İŞ eşiğinin kendisi), tam sınır ve taze kalp kalır; `isler.isci_id` durur."""
    olu = kuyruk.isci_kaydet(db_oturumu, "olu-konak", "0.0.0", 1, _an(0))
    sinir = kuyruk.isci_kaydet(db_oturumu, "sinir-konak", "0.0.0", 1, _an(0))
    canli = kuyruk.isci_kaydet(db_oturumu, "canli-konak", "0.0.0", 1, _an(0))
    db_oturumu.commit()
    (is_id,) = _ekle(db_oturumu, kullanici.id)
    kuyruk.al(db_oturumu, olu.id, _an(1))
    an = _an(1000)
    kuyruk.isci_kalp(db_oturumu, olu.id, an - ESIK - dt.timedelta(microseconds=1))
    kuyruk.isci_kalp(db_oturumu, sinir.id, an - ESIK)
    kuyruk.isci_kalp(db_oturumu, canli.id, an - dt.timedelta(seconds=30))
    db_oturumu.commit()
    assert kuyruk.olu_iscileri_sil(db_oturumu, an, ESIK) == 1
    db_oturumu.commit()
    assert set(db_oturumu.scalars(select(tablolar.Isci.konak))) == {"sinir-konak", "canli-konak"}
    assert kuyruk.olu_iscileri_sil(db_oturumu, an, ESIK) == 0, "idempotent"
    db_oturumu.expire_all()
    assert db_oturumu.get(tablolar.Is, is_id).isci_id == olu.id, "FK yok: 'kim koştu' kaydı durur"
    assert kuyruk.isci_son_kalp(db_oturumu) == an - dt.timedelta(seconds=30), "/health canlıyı görür"


# ── (iv) şema ──────────────────────────────────────────────────────────

def test_the_queue_indexes_are_partial_in_the_database(depo_db):
    """Kısmi indeksler gerçekten kısmi: `pg_indexes` tanımında `WHERE`; kuyruk okuması bitenleri taramaz."""
    with depo_db.connect() as c:
        tanimlar = dict(c.execute(text(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'isler'")).all())
    assert set(tanimlar) == {"pk_isler", "ix_isler_kullanici_olusturuldu", "ix_isler_kuyruk",
                             "ix_isler_kullanici_aktif"}
    assert tanimlar["ix_isler_kuyruk"].endswith("WHERE (durum = 'bekliyor'::text)")
    assert "(durum, olusturuldu)" in tanimlar["ix_isler_kuyruk"]
    assert "WHERE (durum = ANY (ARRAY['bekliyor'::text, 'calisiyor'::text]))" in tanimlar["ix_isler_kullanici_aktif"]
    assert "(kullanici_id, olusturuldu)" in tanimlar["ix_isler_kullanici_aktif"]
    assert "WHERE" not in tanimlar["ix_isler_kullanici_olusturuldu"]


def test_upgrade_downgrade_upgrade_is_clean_and_check_reports_no_drift(veritabani, depo_db):
    """§1 çıkış ölçütü: 0004 geri alınınca iki tablo gider (11 kalır; Faz 3'ün `kredi_hareketleri`si de — `isler`e FK'lı,
    0007 önce düşer), yeniden kurulunca 14; `alembic check` boş."""
    from alembic.config import Config

    from alembic import command
    cfg = Config(os.path.join(REPO, "alembic.ini"))
    cfg.attributes["baglanti_dizesi"] = veritabani
    depo_db.dispose()                    # havuzdaki boş bağlantılar DDL'e takılmasın
    motor = create_engine(veritabani)
    try:
        command.downgrade(cfg, "0003_arena_win")
        tablolar_ = set(sa_inspect(motor).get_table_names())
        assert "isler" not in tablolar_ and "isciler" not in tablolar_ and len(tablolar_) == 12  # 11 + alembic_version
        command.upgrade(cfg, "head")
        assert set(sa_inspect(motor).get_table_names()) == set(tablolar.Base.metadata.tables) | {"alembic_version"}
        assert len(tablolar.Base.metadata.tables) == 14
        with motor.connect() as c:
            assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0007_kredi"
        command.check(cfg)               # fark varsa AutogenerateDiffsDetected
    finally:
        motor.dispose()
