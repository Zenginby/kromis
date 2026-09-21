"""Kredi defteri — `services/defter.py` + göç `0007_kredi` (Faz 3 / 1. görev).

Hepsi GERÇEK Postgres'e karşı (`depo_db`): sınanan şeylerin özü — `UPDATE …
WHERE bakiye >= :m` yarışı, `ON CONFLICT DO NOTHING`, `ON DELETE SET NULL`/
`CASCADE`, CHECK — SQLite'ta ya yok ya başka. Eş zamanlılık iki `Session` +
iki bağlantıyla, aynı süreçte (kilit sunucuda; Faz 2'nin kuyruk testi deseni).

Beş soru:

  (i)   ŞEMA — ileri-geri-ileri + `alembic check` boş; 14 tablo; iki indeks,
        UNIQUE anahtar, SET NULL/CASCADE FK'ler; anahtar biçimleri sözleşme.
  (ii)  DÜŞÜM — rezerv yeterli/yetersiz (`YetersizBakiye(bakiye, gereken)`,
        satır YAZILMAZ); iki eş zamanlı rezerv aynı bakiyeye → biri
        `YetersizBakiye`, 100 tekrarda çift düşüm 0, bakiye asla eksiye inmez
        (§1 çıkış ölçütü) — deterministik (kilit tutulur) ve zamanlamalı ikizi.
  (iii) KAPANIŞ — onay fark iade / sıfır / aşım (EK TAHSİLAT YOK + `WARNING
        olay=defter.asim`); iade tamamı; ikisi birbirini dışlar ve tekrar
        çağrıda no-op (satır sayısı ve bakiye SABİT).
  (iv)  HİBE, DÜZELTME, LİSTE, TUTARLILIK — `ON CONFLICT` no-op; admin
        düzeltmesi eksiye inebilir ve `admin_id` taşır; liste en yeni üstte,
        döküm iç alanları gizler; `tutarlilik` elle saptırılan önbelleği bulur.
  (v)   SINIR — iki kullanıcı depo düzeyinde izole; hesap silinince defter
        gider (CASCADE), iş silinince satır KALIR (`is_id` NULL); TEK YAZAR
        kaynak bekçisi (`kullanicilar.bakiye`ye UPDATE ve `kredi_hareketleri`ye
        INSERT kuran modül yalnız `services/defter.py`).

RLS iddiaları (kullanıcı başkasının hareketini okuyamaz, admin okur + EKLER,
SİLEMEZ) tests/test_rls.py'de, uygulama rolüyle.
"""
from __future__ import annotations

import ast
import glob
import logging
import os
import re
import threading
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from services import defter, hesap, kuyruk, tablolar, zaman

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UUID_DESENI = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

# Belge §1 "Risk": geri dönüşsüz adlar — Faz 4 bunları okuyacak. Biçim → regex.
ANAHTAR_BICIMLERI = {
    "rezerv": re.compile(rf"^rezerv:{UUID_DESENI}$"),
    "onay": re.compile(rf"^onay:{UUID_DESENI}$"),
    "iade": re.compile(rf"^iade:{UUID_DESENI}$"),
    "hibe": re.compile(rf"^hibe:{UUID_DESENI}:\d{{4}}-\d{{2}}$"),
    "duzeltme": re.compile(rf"^duzeltme:{UUID_DESENI}$"),
}


@pytest.fixture(autouse=True)
def temiz(depo_db):
    """Dosyanın testleri aynı DB'yi paylaşır; test kullanıcısı her testte yenilenir (CASCADE defterini götürür),
    ikinci kullanıcılar ve işler burada temizlenir."""
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM kullanicilar WHERE eposta LIKE 'b-%@example.com'"))
        c.execute(text("DELETE FROM isler"))
    yield


def _ikinci_kullanici(db: Session) -> uuid.UUID:
    k = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                           dogrulandi_at=hesap.simdi())
    db.add(k)
    db.flush()
    return k.id


def _is(db: Session, kullanici_id: uuid.UUID, tahmin: int = 10) -> uuid.UUID:
    return kuyruk.ekle(db, kullanici_id, "generate", {"prompt": "p"}, "m", tahmin).id


def _satirlar(db: Session, kullanici_id: uuid.UUID) -> list[tuple[str, int, str]]:
    return [tuple(r) for r in db.execute(text(
        "SELECT tur, miktar, idempotency_anahtari FROM kredi_hareketleri WHERE kullanici_id = :k "
        "ORDER BY olusturuldu, id"), {"k": kullanici_id}).all()]


def _sayi(db: Session) -> int:
    return int(db.execute(text("SELECT count(*) FROM kredi_hareketleri")).scalar_one())


def _bakiye_db(db: Session, kullanici_id: uuid.UUID) -> int:
    """Önbelleği ORM'siz okur — `defter.bakiye`nin kendisini sınayan testler ona güvenmesin."""
    return int(db.execute(text("SELECT bakiye FROM kullanicilar WHERE id = :k"), {"k": kullanici_id}).scalar_one())


class _Yakala(logging.Handler):
    """`kromis.defter` günlükçüsünün kayıtları — `kromis.*` köke yayılmaz (services/gunluk.py), doğrudan takılır."""

    def __init__(self) -> None:
        super().__init__()
        self.kayitlar: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.kayitlar.append(record)


@pytest.fixture
def yakala():
    gunlukcu = logging.getLogger("kromis.defter")
    y = _Yakala()
    # Aynı süreçte koşmuş Alembic `fileConfig` (şablon DB) günlükçüyü KAPATMIŞ olabilir;
    # `gunluk.kur` üretimde açar (services/gunluk.py), burada kurulum yok — elle (tests/test_isci.py deseni).
    kapaliydi, gunlukcu.disabled = gunlukcu.disabled, False
    gunlukcu.addHandler(y)
    yield y
    gunlukcu.removeHandler(y)
    gunlukcu.disabled = kapaliydi


# ── (i) şema ───────────────────────────────────────────────────────────

def test_upgrade_downgrade_upgrade_is_clean_and_check_reports_no_drift(veritabani, depo_db):
    """§1 çıkış ölçütü: 0007 geri alınınca tablo ve BEŞ sütun gider (13 tablo kalır), yeniden kurulunca 14; `check` boş."""
    from alembic.config import Config

    from alembic import command
    cfg = Config(os.path.join(REPO, "alembic.ini"))
    cfg.attributes["baglanti_dizesi"] = veritabani
    depo_db.dispose()                    # havuzdaki boş bağlantılar DDL'e takılmasın
    motor = create_engine(veritabani)
    try:
        command.downgrade(cfg, "0006_rls")
        denetci = sa_inspect(motor)
        tablolar_ = set(denetci.get_table_names())
        assert "kredi_hareketleri" not in tablolar_ and len(tablolar_) == 14  # 13 + alembic_version
        sutunlar = {t: {c["name"] for c in denetci.get_columns(t)} for t in ("kullanicilar", "isler", "medya")}
        assert not sutunlar["kullanicilar"] & {"bakiye", "plan"}
        assert not sutunlar["isler"] & {"kredi_gercek", "saglayici_meta", "saglayici_maliyet_usd"}
        assert "filigranli" not in sutunlar["medya"]
        assert "ck_kullanicilar_plan_kumesi" not in {c["name"] for c in denetci.get_check_constraints("kullanicilar")}
        command.upgrade(cfg, "head")
        assert set(sa_inspect(motor).get_table_names()) == set(tablolar.Base.metadata.tables) | {"alembic_version"}
        assert len(tablolar.Base.metadata.tables) == 14
        with motor.connect() as c:
            assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0007_kredi"
        command.check(cfg)               # fark varsa AutogenerateDiffsDetected
    finally:
        motor.dispose()


def test_the_ledger_table_has_its_two_indexes_the_unique_key_and_the_right_delete_rules(depo_db):
    """`(kullanici_id, olusturuldu)` liste, `(is_id)` "rezervi var mı"; anahtar UNIQUE; FK'ler CASCADE / SET NULL / SET NULL."""
    with depo_db.connect() as c:
        indeksler = {ad: tanim for ad, tanim in c.execute(text(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'kredi_hareketleri'")).all()}
        assert "(kullanici_id, olusturuldu)" in indeksler["ix_kredi_hareketleri_kullanici_olusturuldu"]
        assert "(is_id)" in indeksler["ix_kredi_hareketleri_is"]
        assert "UNIQUE" in indeksler["uq_kredi_hareketleri_idempotency_anahtari"]
        kurallar = {ad: kural for ad, kural in c.execute(text(
            "SELECT conname, confdeltype FROM pg_constraint WHERE conrelid = 'kredi_hareketleri'::regclass "
            "AND contype = 'f'")).all()}
    assert kurallar == {"fk_kredi_hareketleri_kullanici_id_kullanicilar": "c",   # CASCADE
                        "fk_kredi_hareketleri_is_id_isler": "n",                 # SET NULL
                        "fk_kredi_hareketleri_admin_id_kullanicilar": "n"}


def test_the_type_constants_and_key_prefixes_mirror_the_check_set_and_the_documented_formats():
    assert (defter.TUR_HIBE, defter.TUR_REZERV, defter.TUR_ONAY, defter.TUR_IADE, defter.TUR_DUZELTME,
            defter.TUR_SONA_ERME) == tablolar.HAREKET_TURLERI
    assert {defter.ONEK_REZERV, defter.ONEK_ONAY, defter.ONEK_IADE, defter.ONEK_HIBE, defter.ONEK_DUZELTME} == {
        f"{tur}:" for tur in ANAHTAR_BICIMLERI}


def test_every_key_the_module_writes_matches_the_documented_format(db_oturumu, kullanici):
    """Belge §1 "Risk": `rezerv:<is_id>`, `onay:<is_id>`, `iade:<is_id>`, `hibe:<u>:<YYYY-MM>`, `duzeltme:<uuid4>`."""
    u = kullanici.id
    defter.hibe(db_oturumu, u, 100, f"hibe:{u}:2026-09")
    a, b = _is(db_oturumu, u), _is(db_oturumu, u)
    defter.rezerve(db_oturumu, u, a, 10)
    defter.rezerve(db_oturumu, u, b, 10)
    defter.onayla(db_oturumu, a, 4)
    defter.iade(db_oturumu, b)
    d = defter.duzelt(db_oturumu, u, -5, "prova", u)
    anahtarlar = {tur: anahtar for tur, _, anahtar in _satirlar(db_oturumu, u)}
    for tur, desen in ANAHTAR_BICIMLERI.items():
        assert desen.match(anahtarlar[tur]), (tur, anahtarlar[tur])
    assert anahtarlar["rezerv"] in (f"rezerv:{a}", f"rezerv:{b}") and anahtarlar["onay"] == f"onay:{a}"
    assert anahtarlar["iade"] == f"iade:{b}"
    uuid.UUID(d.idempotency_anahtari.removeprefix("duzeltme:"))     # uuid4, çözülür


# ── (ii) düşüm ─────────────────────────────────────────────────────────

def test_balance_starts_at_zero_and_a_grant_adds_a_row_and_raises_the_cache(db_oturumu, kullanici):
    u = kullanici.id
    assert defter.bakiye(db_oturumu, u) == 0 and _satirlar(db_oturumu, u) == []
    an = zaman.an()
    assert defter.hibe(db_oturumu, u, 200, f"hibe:{u}:2026-09", "eylul hibesi", an=an) is True
    db_oturumu.commit()
    assert defter.bakiye(db_oturumu, u) == 200 == _bakiye_db(db_oturumu, u)
    (h,) = defter.hareketler(db_oturumu, u)
    assert (h.tur, h.miktar, h.aciklama, h.is_id, h.admin_id, h.olusturuldu) == ("hibe", 200, "eylul hibesi", None,
                                                                                   None, an)
    assert defter.bakiye(db_oturumu, uuid.uuid4()) == 0, "olmayan kullanıcı 0, hata değil"


def test_a_repeated_grant_with_the_same_key_is_a_no_op(db_oturumu, kullanici):
    """Bakım turu aynı ayın hibesini her turda dener; ikincisi satır yazmaz, bakiye oynamaz."""
    u = kullanici.id
    assert defter.hibe(db_oturumu, u, 200, f"hibe:{u}:2026-09") is True
    assert defter.hibe(db_oturumu, u, 200, f"hibe:{u}:2026-09") is False
    assert defter.hibe(db_oturumu, u, 999, f"hibe:{u}:2026-09") is False, "aynı anahtar, farklı miktar: yine no-op"
    assert (_sayi(db_oturumu), _bakiye_db(db_oturumu, u)) == (1, 200)
    assert defter.hibe(db_oturumu, u, 200, f"hibe:{u}:2026-10") is True, "yeni ay yeni anahtar"
    assert _bakiye_db(db_oturumu, u) == 400
    for kotu in (0, -1):
        with pytest.raises(ValueError):
            defter.hibe(db_oturumu, u, kotu, f"hibe:{u}:2026-11")


def test_reserve_deducts_the_estimate_and_writes_a_negative_row_keyed_by_the_job(db_oturumu, kullanici):
    u = kullanici.id
    defter.hibe(db_oturumu, u, 50, f"hibe:{u}:2026-09")
    is_id = _is(db_oturumu, u)
    an = zaman.an()
    h = defter.rezerve(db_oturumu, u, is_id, 30, an=an)
    db_oturumu.commit()
    assert (h.tur, h.miktar, h.is_id, h.kullanici_id, h.idempotency_anahtari, h.olusturuldu) == (
        "rezerv", -30, is_id, u, f"rezerv:{is_id}", an)
    assert _bakiye_db(db_oturumu, u) == 20
    assert _satirlar(db_oturumu, u)[-1] == ("rezerv", -30, f"rezerv:{is_id}")
    # Tam bakiye kadar rezerv geçer (`>=`), sıfır bırakır.
    defter.rezerve(db_oturumu, u, _is(db_oturumu, u), 20)
    assert _bakiye_db(db_oturumu, u) == 0
    with pytest.raises(ValueError):
        defter.rezerve(db_oturumu, u, _is(db_oturumu, u), -1)


def test_reserve_with_insufficient_balance_raises_with_balance_and_needed_and_writes_nothing(db_oturumu, kullanici):
    """Rota 402 gövdesini (`{bakiye, gereken}`, K11) bu iki sayıdan kurar; defterde iz kalmaz."""
    u = kullanici.id
    defter.hibe(db_oturumu, u, 7, f"hibe:{u}:2026-09")
    is_id = _is(db_oturumu, u)
    with pytest.raises(defter.YetersizBakiye) as hata:
        defter.rezerve(db_oturumu, u, is_id, 8)
    assert (hata.value.bakiye, hata.value.gereken) == (7, 8)
    assert hata.value.args == (7, 8)
    assert _bakiye_db(db_oturumu, u) == 7
    assert [t for t, *_ in _satirlar(db_oturumu, u)] == ["hibe"], "rezerv satırı YAZILMADI"
    assert defter.onayla(db_oturumu, is_id, 1) is None and defter.iade(db_oturumu, is_id) is None
    with pytest.raises(defter.YetersizBakiye) as bos:
        defter.rezerve(db_oturumu, uuid.uuid4(), is_id, 1)      # olmayan kullanıcı: 0 satır, bakiye 0
    assert (bos.value.bakiye, bos.value.gereken) == (0, 1)


def test_reserving_the_same_job_twice_does_not_deduct_twice(db_oturumu, kullanici):
    """Anahtar `rezerv:<is_id>` çakışır: ikinci çağrı düşümü geri alır ve var olan satırı döner."""
    u = kullanici.id
    defter.hibe(db_oturumu, u, 100, f"hibe:{u}:2026-09")
    is_id = _is(db_oturumu, u)
    ilk = defter.rezerve(db_oturumu, u, is_id, 30)
    ikinci = defter.rezerve(db_oturumu, u, is_id, 30)
    assert ikinci == ilk
    assert (_bakiye_db(db_oturumu, u), _sayi(db_oturumu)) == (70, 2)


def test_two_sessions_reserving_against_the_same_balance_leave_exactly_one_short_in_100_rounds(depo_db, db_oturumu,
                                                                                               kullanici):
    """§1 çıkış ölçütü: iki eş zamanlı rezerv aynı bakiyeye, 100 tekrar, çift düşüm 0, bakiye asla eksiye inmez.

    A düşer ve COMMIT ETMEZ (satır kilitli); B o sırada aynı düşümü dener ve
    kilitte BEKLER (bu yüzden iş parçacığında); A commit edince B güncel
    değeri görür (`WHERE bakiye >= :m` artık tutmaz) → `YetersizBakiye`. Yarış
    zamanlamaya bırakılmıyor, kilit gerçekten tutuluyor — deterministik; B'nin
    UPDATE'i A'nın commit'inden sonra varsa da sonuç aynı.
    """
    u = kullanici.id
    yetersiz = 0

    def _b(oturum: Session, is_b: uuid.UUID, sonuclar: list[object]) -> None:
        try:
            sonuclar.append(defter.rezerve(oturum, u, is_b, 10))
            oturum.commit()
        except defter.YetersizBakiye as e:
            oturum.rollback()
            sonuclar.append(e)

    with Session(depo_db) as a, Session(depo_db) as b:
        for tur in range(100):
            assert defter.hibe(db_oturumu, u, 10, f"hibe:{u}:tur{tur}") is True
            db_oturumu.commit()
            assert _bakiye_db(db_oturumu, u) == 10
            is_a, is_b = _is(db_oturumu, u), _is(db_oturumu, u)     # FK: gerçek iş satırı
            db_oturumu.commit()
            sonuclar: list[object] = []
            ha = defter.rezerve(a, u, is_a, 10)          # kilit A'da
            parca = threading.Thread(target=_b, args=(b, is_b, sonuclar))
            parca.start()
            a.commit()
            parca.join(10)
            assert not parca.is_alive(), f"tur {tur}: B kilitte kaldı"
            (sb,) = sonuclar
            assert isinstance(sb, defter.YetersizBakiye), f"tur {tur}: ÇİFT DÜŞÜM"
            assert (sb.bakiye, sb.gereken) == (0, 10) and ha.miktar == -10
            yetersiz += 1
            assert _bakiye_db(db_oturumu, u) == 0, f"tur {tur}: bakiye eksiye indi ya da düşmedi"
    assert yetersiz == 100
    rezervler = [r for r in _satirlar(db_oturumu, u) if r[0] == "rezerv"]
    assert len(rezervler) == 100, "her turda TEK rezerv satırı"
    assert _bakiye_db(db_oturumu, u) == 0 and defter.tutarlilik(db_oturumu) == []


def test_two_threads_racing_on_one_balance_never_overdraw_it(depo_db, db_oturumu, kullanici):
    """Aynı iddianın zamanlamaya bırakılmış ikizi: iki iş parçacığı bariyerle aynı anda, 20 tur; kim kazanırsa
    kazansın tur başına tek düşüm, bakiye hiç eksiye inmez, `SUM == bakiye`."""
    u = kullanici.id
    hatalar: list[BaseException] = []
    basari: dict[int, int] = {0: 0, 1: 0}
    kisa: dict[int, int] = {0: 0, 1: 0}

    def _tur(no: int, bariyer: threading.Barrier, is_id: uuid.UUID) -> None:
        try:
            with Session(depo_db) as s:
                bariyer.wait(5)
                try:
                    defter.rezerve(s, u, is_id, 10)
                    s.commit()
                    basari[no] += 1
                except defter.YetersizBakiye:
                    s.rollback()
                    kisa[no] += 1
        except BaseException as e:      # noqa: BLE001 — iş parçacığında yutulmasın, ana akışa taşınsın
            hatalar.append(e)

    for tur in range(20):
        defter.hibe(db_oturumu, u, 10, f"hibe:{u}:yaris{tur}")
        isler = [_is(db_oturumu, u), _is(db_oturumu, u)]
        db_oturumu.commit()
        bariyer = threading.Barrier(2)
        parcalar = [threading.Thread(target=_tur, args=(i, bariyer, isler[i])) for i in (0, 1)]
        for p in parcalar:
            p.start()
        for p in parcalar:
            p.join(30)
        assert not hatalar, hatalar
        assert _bakiye_db(db_oturumu, u) == 0, f"tur {tur}: bakiye {_bakiye_db(db_oturumu, u)}"
    assert basari[0] + basari[1] == 20 and kisa[0] + kisa[1] == 20
    assert len([r for r in _satirlar(db_oturumu, u) if r[0] == "rezerv"]) == 20
    assert defter.tutarlilik(db_oturumu) == []


# ── (iii) kapanış ──────────────────────────────────────────────────────

def test_confirm_refunds_the_difference_when_the_real_cost_is_lower(db_oturumu, kullanici):
    u = kullanici.id
    defter.hibe(db_oturumu, u, 100, f"hibe:{u}:2026-09")
    is_id = _is(db_oturumu, u)
    defter.rezerve(db_oturumu, u, is_id, 10)
    h = defter.onayla(db_oturumu, is_id, 6)
    db_oturumu.commit()
    assert h is not None and (h.tur, h.miktar, h.is_id, h.idempotency_anahtari) == ("onay", 4, is_id, f"onay:{is_id}")
    assert _bakiye_db(db_oturumu, u) == 94, "100 − 10 + 4"
    assert [(t, m) for t, m, _ in _satirlar(db_oturumu, u)] == [("hibe", 100), ("rezerv", -10), ("onay", 4)]


def test_confirm_writes_a_zero_row_when_the_real_cost_equals_the_estimate(db_oturumu, kullanici, yakala):
    u = kullanici.id
    defter.hibe(db_oturumu, u, 100, f"hibe:{u}:2026-09")
    is_id = _is(db_oturumu, u)
    defter.rezerve(db_oturumu, u, is_id, 10)
    h = defter.onayla(db_oturumu, is_id, 10)
    assert h is not None and (h.tur, h.miktar) == ("onay", 0), "iz: onaylandı"
    assert _bakiye_db(db_oturumu, u) == 90
    assert yakala.kayitlar == [], "aşım yok, uyarı yok"


def test_confirm_never_charges_more_when_the_real_cost_exceeds_the_estimate_but_logs_a_warning(db_oturumu,
                                                                                                kullanici, yakala):
    """Tahmin üst sınır olmalıydı (Faz 2 / 6); değilse kullanıcıdan fazlası ALINMAZ, `olay=defter.asim` (5 yakalar)."""
    u = kullanici.id
    defter.hibe(db_oturumu, u, 100, f"hibe:{u}:2026-09")
    is_id = _is(db_oturumu, u)
    defter.rezerve(db_oturumu, u, is_id, 10)
    h = defter.onayla(db_oturumu, is_id, 15)
    assert h is not None and (h.tur, h.miktar) == ("onay", 0)
    assert _bakiye_db(db_oturumu, u) == 90, "ek tahsilat yok"
    (uyari,) = yakala.kayitlar
    assert uyari.levelno == logging.WARNING and uyari.name == "kromis.defter"
    assert (uyari.olay, uyari.is_id, uyari.kullanici_id, uyari.tahmin, uyari.gercek) == (
        "defter.asim", str(is_id), str(u), 10, 15)
    with pytest.raises(ValueError):
        defter.onayla(db_oturumu, _is(db_oturumu, u), -1)


def test_confirm_and_refund_are_idempotent_and_mutually_exclusive(db_oturumu, kullanici):
    """`onayla` ×2, `iade` ×2, `onayla` → `iade`, `iade` → `onayla`: ikinci çağrı satır yazmaz, bakiye oynamaz."""
    u = kullanici.id
    defter.hibe(db_oturumu, u, 100, f"hibe:{u}:2026-09")
    a, b = _is(db_oturumu, u), _is(db_oturumu, u)
    defter.rezerve(db_oturumu, u, a, 10)
    defter.rezerve(db_oturumu, u, b, 10)
    assert _bakiye_db(db_oturumu, u) == 80

    assert defter.onayla(db_oturumu, a, 6) is not None
    assert defter.onayla(db_oturumu, a, 6) is None and defter.onayla(db_oturumu, a, 0) is None
    assert defter.iade(db_oturumu, a) is None, "onaylanmış iş iade edilmez"
    assert (_bakiye_db(db_oturumu, u), _sayi(db_oturumu)) == (84, 4)

    h = defter.iade(db_oturumu, b)
    assert h is not None and (h.tur, h.miktar, h.idempotency_anahtari) == ("iade", 10, f"iade:{b}")
    assert defter.iade(db_oturumu, b) is None, "`dusur` ve bayat düşürme aynı işi ikinci kez düşürebilir"
    assert defter.onayla(db_oturumu, b, 3) is None, "iade edilmiş iş onaylanmaz"
    assert (_bakiye_db(db_oturumu, u), _sayi(db_oturumu)) == (94, 5)
    assert defter.onayla(db_oturumu, uuid.uuid4(), 1) is None and defter.iade(db_oturumu, uuid.uuid4()) is None, \
        "rezervi olmayan iş (BYOK, göç öncesi) no-op"
    assert defter.tutarlilik(db_oturumu) == []


# ── (iv) hibe, düzeltme, liste, tutarlılık ─────────────────────────────

def test_an_admin_correction_may_drive_the_balance_negative_and_records_the_admin(db_oturumu, kullanici):
    """Admin düzeltmesi: kapı yok, iz var (`admin_id`); verilen anahtar tekrarında var olan satır döner."""
    u = kullanici.id
    admin = _ikinci_kullanici(db_oturumu)
    h = defter.duzelt(db_oturumu, u, -50, "yanlis hibe geri", admin)
    db_oturumu.commit()
    assert (h.tur, h.miktar, h.aciklama, h.admin_id, h.kullanici_id, h.is_id) == (
        "duzeltme", -50, "yanlis hibe geri", admin, u, None)
    assert _bakiye_db(db_oturumu, u) == -50, "eksiye iner — bilerek"
    assert defter.hibe(db_oturumu, u, 30, f"hibe:{u}:2026-09") is True and _bakiye_db(db_oturumu, u) == -20
    with pytest.raises(defter.YetersizBakiye):
        defter.rezerve(db_oturumu, u, _is(db_oturumu, u), 1)
    tekrar = defter.duzelt(db_oturumu, u, 25, None, admin, anahtar="duzeltme:prova-1")
    assert defter.duzelt(db_oturumu, u, 25, None, admin, anahtar="duzeltme:prova-1") == tekrar
    assert (_bakiye_db(db_oturumu, u), _sayi(db_oturumu)) == (5, 3)
    assert defter.duzelt(db_oturumu, u, 1, None, admin).idempotency_anahtari != tekrar.idempotency_anahtari


def test_movements_list_newest_first_with_the_limit_and_the_dump_hides_internal_fields(db_oturumu, kullanici):
    u = kullanici.id
    admin = _ikinci_kullanici(db_oturumu)
    baslangic = zaman.an()
    for i in range(5):
        defter.hibe(db_oturumu, u, 10 + i, f"hibe:{u}:2026-{i + 1:02d}", an=baslangic.replace(microsecond=i))
    is_id = _is(db_oturumu, u)
    defter.rezerve(db_oturumu, u, is_id, 5, an=baslangic.replace(microsecond=7))
    defter.duzelt(db_oturumu, u, -1, "d", admin, an=baslangic.replace(microsecond=9))
    hepsi = defter.hareketler(db_oturumu, u)
    assert [h.miktar for h in hepsi] == [-1, -5, 14, 13, 12, 11, 10], "en yeni üstte"
    assert [h.miktar for h in defter.hareketler(db_oturumu, u, limit=2)] == [-1, -5]
    dokum = defter._json(hepsi[0])
    assert list(dokum) == ["id", "tur", "miktar", "aciklama", "is_id", "olusturuldu"]
    assert "admin_id" not in dokum and "idempotency_anahtari" not in dokum and "kullanici_id" not in dokum
    assert dokum["olusturuldu"].endswith("Z") and dokum["is_id"] is None and dokum["aciklama"] == "d"
    assert defter._json(hepsi[1])["is_id"] == str(is_id)
    assert uuid.UUID(dokum["id"]) == hepsi[0].id


def test_consistency_finds_a_manually_skewed_cache_and_nothing_else(db_oturumu, kullanici):
    """`tutarlilik` ÖLÇER: bakiye ≠ SUM olan kullanıcı(lar) `(id, bakiye, toplam)`; hareketi olmayan kullanıcı toplam 0."""
    u = kullanici.id
    b = _ikinci_kullanici(db_oturumu)
    c = _ikinci_kullanici(db_oturumu)
    defter.hibe(db_oturumu, u, 100, f"hibe:{u}:2026-09")
    defter.rezerve(db_oturumu, u, _is(db_oturumu, u), 30)
    defter.hibe(db_oturumu, b, 50, f"hibe:{b}:2026-09")
    db_oturumu.commit()
    assert defter.tutarlilik(db_oturumu) == []
    # Test dosyası önbelleği elle saptırır (ürün kodunda tek yazar `defter`, aşağıdaki kaynak bekçisi).
    db_oturumu.execute(text("UPDATE kullanicilar SET bakiye = 99 WHERE id = :k"), {"k": u})
    db_oturumu.execute(text("UPDATE kullanicilar SET bakiye = 3 WHERE id = :k"), {"k": c})
    db_oturumu.commit()
    assert sorted(defter.tutarlilik(db_oturumu), key=lambda s: str(s[0])) == sorted(
        [(u, 99, 70), (c, 3, 0)], key=lambda s: str(s[0]))
    # `duzelt` sapmayı KAPATMAZ — iki tarafı birden oynatır (satır + önbellek), fark aynı kalır: önbellek
    # sapması bir defter hareketi değil, önbelleğin SUM'a çekilmesidir (7. görevin bakım turu karar verir;
    # belgenin "düzeltme admin `duzelt`" cümlesi buradaki ölçümle daraltıldı — "Yapıldığında" notu).
    defter.duzelt(db_oturumu, u, 5, "deneme", b)
    assert [(kid, bak - top) for kid, bak, top in defter.tutarlilik(db_oturumu) if kid == u] == [(u, 29)]
    # Önbellek SUM'a çekilince (bakım turunun yapacağı şey) sapma kapanır.
    db_oturumu.execute(text("UPDATE kullanicilar SET bakiye = 75 WHERE id = :k"), {"k": u})
    db_oturumu.execute(text("UPDATE kullanicilar SET bakiye = 0 WHERE id = :k"), {"k": c})
    db_oturumu.commit()
    assert defter.tutarlilik(db_oturumu) == []


# ── (v) sınır ───────────────────────────────────────────────────────────

def test_two_users_are_isolated_at_the_repository_layer(db_oturumu, kullanici):
    a, b = kullanici.id, _ikinci_kullanici(db_oturumu)
    defter.hibe(db_oturumu, a, 100, f"hibe:{a}:2026-09")
    defter.hibe(db_oturumu, b, 20, f"hibe:{b}:2026-09")
    is_a = _is(db_oturumu, a)
    defter.rezerve(db_oturumu, a, is_a, 40)
    db_oturumu.commit()
    assert (defter.bakiye(db_oturumu, a), defter.bakiye(db_oturumu, b)) == (60, 20)
    assert [h.kullanici_id for h in defter.hareketler(db_oturumu, b)] == [b]
    assert all(h.kullanici_id == a for h in defter.hareketler(db_oturumu, a)) and len(defter.hareketler(db_oturumu, a)) == 2
    with pytest.raises(defter.YetersizBakiye):
        defter.rezerve(db_oturumu, b, _is(db_oturumu, b), 21), "B, A'nın bakiyesinden düşemez"
    assert defter.iade(db_oturumu, is_a) is not None
    assert (defter.bakiye(db_oturumu, a), defter.bakiye(db_oturumu, b)) == (100, 20), "A'nın iadesi B'ye dokunmaz"


def test_deleting_the_user_cascades_the_ledger_but_deleting_the_job_keeps_the_row_with_a_null_job(db_oturumu,
                                                                                                    kullanici):
    """Hesap gider → defteri gider (KVKK Faz 4 yeniden bakar); iş gider (saklama, Faz 2 / 10) → para izi KALIR."""
    a, b = kullanici.id, _ikinci_kullanici(db_oturumu)
    defter.hibe(db_oturumu, a, 100, f"hibe:{a}:2026-09")
    defter.hibe(db_oturumu, b, 100, f"hibe:{b}:2026-09")
    is_a, is_b = _is(db_oturumu, a), _is(db_oturumu, b)
    defter.rezerve(db_oturumu, a, is_a, 10)
    defter.rezerve(db_oturumu, b, is_b, 10)
    defter.onayla(db_oturumu, is_b, 10)
    db_oturumu.commit()
    assert _sayi(db_oturumu) == 5

    db_oturumu.execute(text("DELETE FROM isler WHERE id = :i"), {"i": is_b})
    db_oturumu.commit()
    kalan = db_oturumu.execute(text("SELECT tur, is_id FROM kredi_hareketleri WHERE kullanici_id = :k ORDER BY tur"),
                               {"k": b}).all()
    assert [tuple(r) for r in kalan] == [("hibe", None), ("onay", None), ("rezerv", None)], "satır kaldı, `is_id` NULL"
    assert _bakiye_db(db_oturumu, b) == 90, "100 − 10 (gerçek = tahmin, onay 0)"
    assert defter.iade(db_oturumu, is_b) is None, "işi silinmiş rezerv artık iş kimliğiyle bulunmaz — para izi zaten kapanmış"

    db_oturumu.execute(text("DELETE FROM kullanicilar WHERE id = :k"), {"k": b})
    db_oturumu.commit()
    assert _sayi(db_oturumu) == 2 and {r[0] for r in _satirlar(db_oturumu, a)} == {"hibe", "rezerv"}


def test_deleting_the_admin_keeps_the_correction_with_a_null_admin(db_oturumu, kullanici):
    u, admin = kullanici.id, _ikinci_kullanici(db_oturumu)
    h = defter.duzelt(db_oturumu, u, 10, "x", admin)
    db_oturumu.commit()
    db_oturumu.execute(text("DELETE FROM kullanicilar WHERE id = :k"), {"k": admin})
    db_oturumu.commit()
    assert db_oturumu.execute(text("SELECT admin_id, miktar FROM kredi_hareketleri WHERE id = :i"),
                              {"i": h.id}).one() == (None, 10)
    assert _bakiye_db(db_oturumu, u) == 10


# ── (v) tek yazar — kaynak bekçisi ─────────────────────────────────────

TEK_YAZAR = "services/defter.py"


def _urun_dosyalari() -> list[str]:
    """Web ve işçi yolu + araçlar: bileşim kökleri, `routers/`, `services/`, `tools/` (testler dışarıda — tohum yazar).

    AYRAÇ `/`'A NORMALİZE EDİLİYOR ve bu satır kozmetik değil: `os.path.relpath`
    Windows'ta `routers\\admin.py` veriyor, oysa `TEK_YAZAR` ve hata iletileri
    `services/defter.py` biçiminde yazılı. Normalize edilmezse `TEK_YAZAR in
    _urun_dosyalari()` orada HİÇ tutmuyor ve bekçi, kendi körlük kontrolünde
    düşüyor — ölçüldü 2026-09-20, Windows'ta tek kırmızı buydu.

    İŞARETLEMEK DEĞİL ONARMAK doğru olan: bu testin konusu (bakiyeyi kimin
    yazdığı) platformdan bağımsız. `posix_gerekir` ile atlansaydı kapı
    Windows'ta hiç koşmaz, yani depo iki platformda geliştirilirken güvencenin
    yarısı kaybolurdu. Gerçek POSIX bağımlılıkları (SIGTERM, `time.tzset`,
    izin bitleri) işaretli; bu bir taşınabilirlik kayması, o defterde yeri yok.
    """
    return ["app.py", "isci.py"] + sorted(
        os.path.relpath(p, REPO).replace(os.sep, "/") for kalip in ("routers", "services", "tools")
        for p in glob.glob(os.path.join(REPO, kalip, "*.py")))


_BAKIYE_SQL = re.compile(r"UPDATE\s+kullanicilar\b.*\bbakiye\b", re.I | re.S)
_DEFTER_SQL = re.compile(r"INSERT\s+INTO\s+kredi_hareketleri\b", re.I)


def _yazimlar(yol: str) -> tuple[list[int], list[int]]:
    """`(bakiye yazan satırlar, defter satırı kuran satırlar)` — AST: ORM (`.values(bakiye=…)`, `x.bakiye = …`,
    `Kullanici(bakiye=…)`, `KrediHareketi(…)`, `insert(KrediHareketi)`) ve ham SQL dizeleri."""
    with open(os.path.join(REPO, yol), encoding="utf-8") as f:
        agac = ast.parse(f.read())
    bakiye: list[int] = []
    defter_: list[int] = []
    for d in ast.walk(agac):
        if isinstance(d, ast.Call):
            ad = d.func.attr if isinstance(d.func, ast.Attribute) else d.func.id if isinstance(d.func, ast.Name) else None
            if ad == "values" and any(k.arg == "bakiye" for k in d.keywords):
                bakiye.append(d.lineno)
            if ad == "Kullanici" and any(k.arg == "bakiye" for k in d.keywords):
                bakiye.append(d.lineno)
            if ad == "KrediHareketi":
                defter_.append(d.lineno)
            if ad == "insert" and any(isinstance(a, ast.Name) and a.id == "KrediHareketi" or
                                      isinstance(a, ast.Attribute) and a.attr == "KrediHareketi" for a in d.args):
                defter_.append(d.lineno)
        if isinstance(d, ast.Assign | ast.AugAssign):
            hedefler = d.targets if isinstance(d, ast.Assign) else [d.target]
            if any(isinstance(h, ast.Attribute) and h.attr == "bakiye" for h in hedefler):
                bakiye.append(d.lineno)
        if isinstance(d, ast.Constant) and isinstance(d.value, str):
            if _BAKIYE_SQL.search(d.value):
                bakiye.append(d.lineno)
            if _DEFTER_SQL.search(d.value):
                defter_.append(d.lineno)
    return bakiye, defter_


def test_only_the_ledger_module_writes_the_balance_cache_or_inserts_ledger_rows():
    """Belge §1 "Risk": `kullanicilar.bakiye`ye UPDATE kuran ve `kredi_hareketleri`ye satır yazan modül YALNIZ
    `services/defter.py` — rota ve işçi defteri ÇAĞIRIR, elle yazmaz (tests/test_galeri_db.py'nin AST deseni).
    Bekçinin bekçisi: defterin kendisi her ikisini de yapıyor görünmeli (tarama boşa dönmesin)."""
    assert TEK_YAZAR in _urun_dosyalari()
    for yol in _urun_dosyalari():
        bakiye, defter_ = _yazimlar(yol)
        if yol == TEK_YAZAR:
            assert bakiye and defter_, "defter.py'nin yazımları görünmüyor: bekçi kör"
            continue
        assert not bakiye, f"{yol}:{bakiye} `kullanicilar.bakiye` yazıyor — tek yazar services/defter.py"
        assert not defter_, f"{yol}:{defter_} `kredi_hareketleri`ye satır kuruyor — tek yazar services/defter.py"
