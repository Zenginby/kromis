"""Kredi defteri — `services/defter.py` + göç `0007_kredi` (Faz 3 / 1) + göç `0008_odeme` iki kova (Faz 4 / 2).

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
        kaynak bekçisi (`kullanicilar.bakiye`/`paket_bakiye`ye UPDATE ve
        `kredi_hareketleri`ye INSERT kuran modül yalnız `services/defter.py`).
  (vi)  İKİ KOVA (Faz 4 / 2, K3) — rezerv bölüşümü üç durum (yalnız hibe /
        hibe + paket / yalnız paket), TEK atomik UPDATE, hibe önce; toplam
        yetersiz → satır yok; onay farkı ÖNCE pakete; iade iki satırı da kova
        kova geri koyar; `paket_yukle` idempotent; `dusur` `sona_erme` yalnız
        hibe kovasında; `tutarlilik` iki SUM; eş zamanlı rezerv iki kovada 100
        tekrar çift düşüm 0; anahtar `:paket` son eki; `hibe_turu` paket
        kovasını görmez; 0008 geri alma paket satırıyla DURUR.

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

# Faz 3 belge §1 "Risk" + Faz 4 "Veri modeli": geri dönüşsüz adlar. Biçim → regex.
# `:paket` son eki aynı işin ikinci kova satırı (Faz 4 / 2); `hibe` aylık YA DA
# Polar dönem hibesi (`hibe:<u>:polar:<order_id>`, 3. görev kurar); `paket` sipariş
# kimliği (Polar id biçimi doğrulanmadı — ASCII sözcük); `sona_erme` abonelik + gün.
ANAHTAR_BICIMLERI = {
    "rezerv": re.compile(rf"^rezerv:{UUID_DESENI}(:paket)?$"),
    "onay": re.compile(rf"^onay:{UUID_DESENI}(:paket)?$"),
    "iade": re.compile(rf"^iade:{UUID_DESENI}(:paket)?$"),
    "hibe": re.compile(rf"^hibe:{UUID_DESENI}:(\d{{4}}-\d{{2}}|polar:[A-Za-z0-9_-]+)$"),
    "duzeltme": re.compile(rf"^duzeltme:{UUID_DESENI}$"),
    "paket": re.compile(r"^paket:[A-Za-z0-9_-]+$"),
    "sona_erme": re.compile(rf"^sona_erme:{UUID_DESENI}:[A-Za-z0-9_-]+:\d{{4}}-\d{{2}}-\d{{2}}$"),
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
    """HİBE önbelleğini ORM'siz okur — `defter.bakiye`nin kendisini sınayan testler ona güvenmesin."""
    return int(db.execute(text("SELECT bakiye FROM kullanicilar WHERE id = :k"), {"k": kullanici_id}).scalar_one())


def _kovalar_db(db: Session, kullanici_id: uuid.UUID) -> tuple[int, int]:
    """`(bakiye, paket_bakiye)` — iki önbellek ORM'siz (Faz 4 / 2)."""
    r = db.execute(text("SELECT bakiye, paket_bakiye FROM kullanicilar WHERE id = :k"), {"k": kullanici_id}).one()
    return int(r[0]), int(r[1])


def _kovali_satirlar(db: Session, kullanici_id: uuid.UUID) -> list[tuple[str, str, int, str]]:
    """`(tur, kova, miktar, anahtar)` — Faz 4 / 2'nin iki kova iddiaları için."""
    return [tuple(r) for r in db.execute(text(
        "SELECT tur, kova, miktar, idempotency_anahtari FROM kredi_hareketleri WHERE kullanici_id = :k "
        "ORDER BY olusturuldu, idempotency_anahtari"), {"k": kullanici_id}).all()]


def _paket(db: Session, kullanici_id: uuid.UUID, miktar: int, siparis: str | None = None) -> bool:
    return defter.paket_yukle(db, kullanici_id, miktar, f"{defter.ONEK_PAKET}{siparis or uuid.uuid4().hex[:12]}")


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
    """§1 çıkış ölçütü: 0007 geri alınınca tablo ve BEŞ sütun gider (13 tablo kalır — 0008'in üçü de ondan önce),
    yeniden kurulunca 17; `check` boş."""
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
        assert len(tablolar.Base.metadata.tables) == 17
        with motor.connect() as c:
            assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0008_odeme"
        command.check(cfg)               # fark varsa AutogenerateDiffsDetected
    finally:
        motor.dispose()


def test_0008_downgrade_drops_three_tables_nine_columns_and_the_bucket_but_refuses_while_pack_rows_exist(
        veritabani, depo_db, db_oturumu, kullanici):
    """Faz 4 §2 çıkış ölçütü + "Veri modeli": 0008 geri alınınca `urunler`/`siparisler`/`odeme_olaylari`, dokuz
    sütun ve `kova` gider, `tur` CHECK'i altıya döner (`paket` reddedilir); AMA `kova`/`tur = 'paket'` satırı
    varsa göç DURUR — parayla alınmış kredi sessizce silinmez."""
    from alembic.config import Config

    from alembic import command
    cfg = Config(os.path.join(REPO, "alembic.ini"))
    cfg.attributes["baglanti_dizesi"] = veritabani
    u = kullanici.id
    assert _paket(db_oturumu, u, 500, "ord_geri") is True
    db_oturumu.commit()
    db_oturumu.close()
    depo_db.dispose()
    motor = create_engine(veritabani)
    try:
        with pytest.raises(RuntimeError, match="paket satiri"):
            command.downgrade(cfg, "0007_kredi")
        with motor.connect() as c:
            assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0008_odeme"
            assert c.execute(text("SELECT count(*) FROM kredi_hareketleri WHERE kova = 'paket'")).scalar_one() == 1
        with motor.begin() as c:      # test paket satırını kaldırır (üretimde sahibin elle kararı)
            c.execute(text("DELETE FROM kredi_hareketleri WHERE kova = 'paket'"))
            c.execute(text("UPDATE kullanicilar SET paket_bakiye = 0"))
        command.downgrade(cfg, "0007_kredi")
        denetci = sa_inspect(motor)
        tablolar_ = set(denetci.get_table_names())
        assert not tablolar_ & {"urunler", "siparisler", "odeme_olaylari"} and len(tablolar_) == 15  # 14 + alembic
        sutunlar = {c["name"] for c in denetci.get_columns("kullanicilar")}
        assert not sutunlar & {"paket_bakiye", "polar_musteri_id", "polar_abonelik_id", "plan_bitis",
                               "sartlar_kabul_at", "sartlar_surumu", "temizlendi_at"}
        assert "kova" not in {c["name"] for c in denetci.get_columns("kredi_hareketleri")}
        kisitlar = {c["name"] for c in denetci.get_check_constraints("kredi_hareketleri")}
        assert "ck_kredi_hareketleri_kova_kumesi" not in kisitlar and "ck_kredi_hareketleri_tur_kumesi" in kisitlar
        with motor.connect() as c, pytest.raises(Exception, match="ck_kredi_hareketleri_tur_kumesi"):
            c.execute(text("INSERT INTO kredi_hareketleri (kullanici_id, tur, miktar, idempotency_anahtari) "
                           "VALUES (:u, 'paket', 1, 'paket:x')"), {"u": u})
        command.upgrade(cfg, "head")
        assert set(sa_inspect(motor).get_table_names()) == set(tablolar.Base.metadata.tables) | {"alembic_version"}
        command.check(cfg)
        with motor.connect() as c:
            assert c.execute(text("SELECT kova FROM kredi_hareketleri LIMIT 1")).scalar() in (None, "hibe"), \
                "eski satırlar hibe kovasında"
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
            defter.TUR_SONA_ERME, defter.TUR_PAKET) == tablolar.HAREKET_TURLERI
    assert {defter.ONEK_REZERV, defter.ONEK_ONAY, defter.ONEK_IADE, defter.ONEK_HIBE, defter.ONEK_DUZELTME,
            defter.ONEK_PAKET, defter.ONEK_SONA_ERME} == {f"{tur}:" for tur in ANAHTAR_BICIMLERI}
    assert (defter.KOVA_HIBE, defter.KOVA_PAKET) == tablolar.KOVALAR and defter.EK_PAKET == ":paket"


def test_every_key_the_module_writes_matches_the_documented_format(db_oturumu, kullanici):
    """Faz 3 §1 "Risk" + Faz 4 "Veri modeli": `rezerv|onay|iade:<is_id>[:paket]`, `hibe:<u>:<YYYY-MM>`,
    `duzeltme:<uuid4>`, `paket:<order_id>`, `sona_erme:<u>:<abonelik>:<YYYY-MM-DD>`."""
    u = kullanici.id
    defter.hibe(db_oturumu, u, 15, f"hibe:{u}:2026-09")
    assert _paket(db_oturumu, u, 100, "ord_1") is True
    a, b = _is(db_oturumu, u), _is(db_oturumu, u)
    defter.rezerve(db_oturumu, u, a, 10)          # yalnız hibe
    defter.rezerve(db_oturumu, u, b, 10)          # hibe 5 + paket 5 → iki satır
    defter.onayla(db_oturumu, a, 4)
    defter.iade(db_oturumu, b)                    # iki satır
    d = defter.duzelt(db_oturumu, u, -5, "prova", u)
    defter.dusur(db_oturumu, u, 0, f"sona_erme:{u}:sub_1:2026-09-21")
    anahtarlar = [(tur, anahtar) for tur, _, _, anahtar in _kovali_satirlar(db_oturumu, u)]
    assert len(anahtarlar) == 10, anahtarlar
    for tur, anahtar in anahtarlar:
        assert ANAHTAR_BICIMLERI[tur].match(anahtar), (tur, anahtar)
    assert {a_ for t, a_ in anahtarlar if t == "rezerv"} == {f"rezerv:{a}", f"rezerv:{b}", f"rezerv:{b}:paket"}
    assert {a_ for t, a_ in anahtarlar if t == "iade"} == {f"iade:{b}", f"iade:{b}:paket"}
    assert {a_ for t, a_ in anahtarlar if t == "onay"} == {f"onay:{a}"}
    uuid.UUID(d.idempotency_anahtari.removeprefix("duzeltme:"))     # uuid4, çözülür
    assert defter.tutarlilik(db_oturumu) == []


# ── (ii) düşüm ─────────────────────────────────────────────────────────

def test_balance_starts_at_zero_and_a_grant_adds_a_row_and_raises_the_cache(db_oturumu, kullanici):
    u = kullanici.id
    assert defter.bakiye(db_oturumu, u) == defter.Bakiye(0, 0, 0) and _satirlar(db_oturumu, u) == []
    an = zaman.an()
    assert defter.hibe(db_oturumu, u, 200, f"hibe:{u}:2026-09", "eylul hibesi", an=an) is True
    db_oturumu.commit()
    b = defter.bakiye(db_oturumu, u)
    assert (b.hibe, b.paket, b.toplam) == (200, 0, 200) and _bakiye_db(db_oturumu, u) == 200
    (h,) = defter.hareketler(db_oturumu, u)
    assert (h.tur, h.kova, h.miktar, h.aciklama, h.is_id, h.admin_id, h.olusturuldu) == (
        "hibe", "hibe", 200, "eylul hibesi", None, None, an)
    assert defter.bakiye(db_oturumu, uuid.uuid4()) == defter.Bakiye(0, 0, 0), "olmayan kullanıcı 0, hata değil"


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
    assert (hata.value.bakiye, hata.value.gereken, hata.value.hibe, hata.value.paket) == (7, 8, 7, 0)
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
    assert list(dokum) == ["id", "tur", "kova", "miktar", "aciklama", "is_id", "olusturuldu"]
    assert "admin_id" not in dokum and "idempotency_anahtari" not in dokum and "kullanici_id" not in dokum
    assert dokum["olusturuldu"].endswith("Z") and dokum["is_id"] is None and dokum["aciklama"] == "d"
    assert dokum["kova"] == "hibe"
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
        [(u, 99, 70, 0, 0), (c, 3, 0, 0, 0)], key=lambda s: str(s[0]))
    # `duzelt` sapmayı KAPATMAZ — iki tarafı birden oynatır (satır + önbellek), fark aynı kalır: önbellek
    # sapması bir defter hareketi değil, önbelleğin SUM'a çekilmesidir (7. görevin bakım turu karar verir;
    # belgenin "düzeltme admin `duzelt`" cümlesi buradaki ölçümle daraltıldı — "Yapıldığında" notu).
    defter.duzelt(db_oturumu, u, 5, "deneme", b)
    assert [(s.kullanici_id, s.bakiye - s.hibe_toplam) for s in defter.tutarlilik(db_oturumu)
            if s.kullanici_id == u] == [(u, 29)]
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
    assert (defter.bakiye(db_oturumu, a).toplam, defter.bakiye(db_oturumu, b).toplam) == (60, 20)
    assert [h.kullanici_id for h in defter.hareketler(db_oturumu, b)] == [b]
    assert all(h.kullanici_id == a for h in defter.hareketler(db_oturumu, a)) and len(defter.hareketler(db_oturumu, a)) == 2
    with pytest.raises(defter.YetersizBakiye):
        defter.rezerve(db_oturumu, b, _is(db_oturumu, b), 21), "B, A'nın bakiyesinden düşemez"
    assert defter.iade(db_oturumu, is_a) is not None
    assert (defter.bakiye(db_oturumu, a).toplam, defter.bakiye(db_oturumu, b).toplam) == (100, 20), \
        "A'nın iadesi B'ye dokunmaz"


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


# ── (vi) iki kova (Faz 4 / 2, K3) ──────────────────────────────────────

def test_a_pack_load_writes_a_pack_row_in_the_pack_bucket_and_is_idempotent_per_order(db_oturumu, kullanici):
    """`paket_yukle`: `paket` satırı kova paket `+miktar`, `paket_bakiye` `+miktar`, hibe kovası DOKUNULMAZ;
    aynı sipariş ikinci kez (`paket:<order_id>` çakışır — K4) no-op; miktar pozitif."""
    u = kullanici.id
    defter.hibe(db_oturumu, u, 100, f"hibe:{u}:2026-09")
    an = zaman.an()
    assert defter.paket_yukle(db_oturumu, u, 500, "paket:ord_abc", "500 kredi paketi", an=an) is True
    db_oturumu.commit()
    assert _kovalar_db(db_oturumu, u) == (100, 500)
    assert defter.bakiye(db_oturumu, u) == defter.Bakiye(100, 500, 600)
    assert defter.paket_yukle(db_oturumu, u, 500, "paket:ord_abc") is False, "aynı sipariş ikinci olayla geldi"
    assert defter.paket_yukle(db_oturumu, u, 999, "paket:ord_abc") is False, "aynı anahtar, farklı miktar: yine no-op"
    assert _kovalar_db(db_oturumu, u) == (100, 500) and _sayi(db_oturumu) == 2
    (h, _) = defter.hareketler(db_oturumu, u)
    assert (h.tur, h.kova, h.miktar, h.aciklama, h.idempotency_anahtari, h.olusturuldu) == (
        "paket", "paket", 500, "500 kredi paketi", "paket:ord_abc", an)
    assert defter._json(h)["kova"] == "paket"
    for kotu in (0, -1):
        with pytest.raises(ValueError):
            defter.paket_yukle(db_oturumu, u, kotu, "paket:ord_kotu")
    assert defter.tutarlilik(db_oturumu) == []


@pytest.mark.parametrize("hibe, paket, m, beklenen", [
    (100, 500, 30, [("rezerv", "hibe", -30, "")]),                                        # yalnız hibe
    (10, 500, 30, [("rezerv", "hibe", -10, ""), ("rezerv", "paket", -20, ":paket")]),      # hibe + paket
    (0, 500, 30, [("rezerv", "paket", -30, "")]),                                          # yalnız paket
    (30, 500, 30, [("rezerv", "hibe", -30, "")]),                                          # hibe tam yeter (>=)
    (100, 500, 0, [("rezerv", "hibe", 0, "")]),                                            # sıfır tahmin: iz
], ids=["yalniz-hibe", "hibe-ve-paket", "yalniz-paket", "hibe-tam-yeter", "sifir"])
def test_reserve_splits_across_the_two_buckets_grant_first_in_one_statement(db_oturumu, kullanici, hibe, paket, m,
                                                                            beklenen):
    """§2: `LEAST` bölüşümü — hibe kovası ÖNCE tükenir, kalan paketten; satırlar `rezerv:<is_id>` (+`:paket`);
    iş tamamen paketten düştüyse ana satır paket kovasında, sıfır miktarlı hibe satırı yazılmaz."""
    u = kullanici.id
    if hibe:
        defter.hibe(db_oturumu, u, hibe, f"hibe:{u}:2026-09")
    _paket(db_oturumu, u, paket, "ord_1")
    is_id = _is(db_oturumu, u)
    ana = defter.rezerve(db_oturumu, u, is_id, m)
    db_oturumu.commit()
    hibe_dusen = min(hibe, m)
    assert _kovalar_db(db_oturumu, u) == (hibe - hibe_dusen, paket - (m - hibe_dusen))
    rezervler = [(t, k, mk, a.removeprefix(f"rezerv:{is_id}")) for t, k, mk, a in _kovali_satirlar(db_oturumu, u)
                 if t == "rezerv"]
    assert rezervler == beklenen
    assert ana.idempotency_anahtari == f"rezerv:{is_id}" and ana.is_id == is_id
    assert ana.kova == beklenen[0][1] and ana.miktar == beklenen[0][2]
    assert defter.tutarlilik(db_oturumu) == []


def test_reserve_fails_on_the_total_of_both_buckets_and_reports_each_bucket(db_oturumu, kullanici):
    """Toplam yetmezse (`bakiye + paket_bakiye < m`) iki kova da DOKUNULMAZ, satır yok, `YetersizBakiye(toplam,
    gereken, hibe=…, paket=…)` — 402 gövdesi `bakiye` = toplam, `hibe`/`paket` ayrı."""
    u = kullanici.id
    defter.hibe(db_oturumu, u, 4, f"hibe:{u}:2026-09")
    _paket(db_oturumu, u, 3, "ord_1")
    is_id = _is(db_oturumu, u)
    with pytest.raises(defter.YetersizBakiye) as hata:
        defter.rezerve(db_oturumu, u, is_id, 8)
    assert (hata.value.bakiye, hata.value.gereken, hata.value.hibe, hata.value.paket) == (7, 8, 4, 3)
    assert hata.value.args == (7, 8)
    assert _kovalar_db(db_oturumu, u) == (4, 3)
    assert [t for t, *_ in _satirlar(db_oturumu, u)] == ["hibe", "paket"], "rezerv satırı YAZILMADI"
    assert defter.rezerve(db_oturumu, u, is_id, 7).miktar == -4, "tam toplam kadar geçer (>=)"
    assert _kovalar_db(db_oturumu, u) == (0, 0)


def test_reserving_the_same_job_twice_across_two_buckets_restores_both_and_returns_the_main_row(db_oturumu,
                                                                                                kullanici):
    u = kullanici.id
    defter.hibe(db_oturumu, u, 10, f"hibe:{u}:2026-09")
    _paket(db_oturumu, u, 100, "ord_1")
    is_id = _is(db_oturumu, u)
    ilk = defter.rezerve(db_oturumu, u, is_id, 30)
    assert _kovalar_db(db_oturumu, u) == (0, 80)
    # İkinci çağrıda hibe kovası boş: bölüşüm bu kez tamamen paketten olurdu — geri alma yine iki kovayı doğru bulur.
    ikinci = defter.rezerve(db_oturumu, u, is_id, 30)
    assert ikinci == ilk and ilk.kova == "hibe" and ilk.miktar == -10
    assert _kovalar_db(db_oturumu, u) == (0, 80) and _sayi(db_oturumu) == 4, "hibe, paket, rezerv, rezerv:paket"
    assert defter.tutarlilik(db_oturumu) == []


@pytest.mark.parametrize("gercek, beklenen_satirlar, beklenen_kovalar", [
    (30, [("onay", "hibe", 0, "")], (0, 80)),                                                # fark 0: iz
    (25, [("onay", "paket", 5, "")], (0, 85)),                                               # fark ≤ paket: yalnız paket
    (10, [("onay", "paket", 20, "")], (0, 100)),                                             # fark == paket
    (5, [("onay", "hibe", 5, ""), ("onay", "paket", 20, ":paket")], (5, 100)),               # fark > paket: kalan hibe
    (0, [("onay", "hibe", 10, ""), ("onay", "paket", 20, ":paket")], (10, 100)),             # tamamı geri
    (45, [("onay", "hibe", 0, "")], (0, 80)),                                                # aşım: ek tahsilat yok
], ids=["fark-0", "yalniz-paket", "paket-tam", "paket-sonra-hibe", "tamami", "asim"])
def test_confirm_refunds_the_difference_to_the_pack_bucket_first(db_oturumu, kullanici, yakala, gercek,
                                                                  beklenen_satirlar, beklenen_kovalar):
    """K3 "hibeden önce paketi geri koy": rezerv hibe 10 + paket 20 (tahmin 30); fark önce paket kovasına (en son
    o düşmüştü, iade edilen paket devretmeyi sürdürür), kalan hibeye. Aşımda `onay` 0 + `defter.asim` uyarısı."""
    u = kullanici.id
    defter.hibe(db_oturumu, u, 10, f"hibe:{u}:2026-09")
    _paket(db_oturumu, u, 100, "ord_1")
    is_id = _is(db_oturumu, u)
    defter.rezerve(db_oturumu, u, is_id, 30)
    assert _kovalar_db(db_oturumu, u) == (0, 80)
    h = defter.onayla(db_oturumu, is_id, gercek)
    db_oturumu.commit()
    assert h is not None and h.idempotency_anahtari == f"onay:{is_id}"
    onaylar = [(t, k, mk, a.removeprefix(f"onay:{is_id}")) for t, k, mk, a in _kovali_satirlar(db_oturumu, u)
               if t == "onay"]
    assert onaylar == beklenen_satirlar
    assert _kovalar_db(db_oturumu, u) == beklenen_kovalar
    assert [k.olay for k in yakala.kayitlar] == (["defter.asim"] if gercek > 30 else [])
    assert defter.onayla(db_oturumu, is_id, gercek) is None and defter.iade(db_oturumu, is_id) is None
    assert defter.tutarlilik(db_oturumu) == []


def test_refund_returns_each_bucket_its_own_deduction_with_two_rows(db_oturumu, kullanici):
    """`iade`: hibeden düşen hibeye, paketten düşen pakete — `iade:<is_id>` + `iade:<is_id>:paket`; tekrar no-op;
    tamamen paketten düşmüş iş tek satırla paket kovasına döner."""
    u = kullanici.id
    defter.hibe(db_oturumu, u, 10, f"hibe:{u}:2026-09")
    _paket(db_oturumu, u, 100, "ord_1")
    a, b = _is(db_oturumu, u), _is(db_oturumu, u)
    defter.rezerve(db_oturumu, u, a, 30)          # hibe 10 + paket 20
    defter.rezerve(db_oturumu, u, b, 15)          # yalnız paket (hibe boş)
    assert _kovalar_db(db_oturumu, u) == (0, 65)
    h = defter.iade(db_oturumu, a)
    assert h is not None and (h.kova, h.miktar, h.idempotency_anahtari) == ("hibe", 10, f"iade:{a}")
    assert _kovalar_db(db_oturumu, u) == (10, 85)
    iadeler = [(k, mk, an) for t, k, mk, an in _kovali_satirlar(db_oturumu, u) if t == "iade"]
    assert iadeler == [("hibe", 10, f"iade:{a}"), ("paket", 20, f"iade:{a}:paket")]
    assert defter.iade(db_oturumu, a) is None and defter.onayla(db_oturumu, a, 1) is None
    hb = defter.iade(db_oturumu, b)
    assert hb is not None and (hb.kova, hb.miktar, hb.idempotency_anahtari) == ("paket", 15, f"iade:{b}")
    assert _kovalar_db(db_oturumu, u) == (10, 100) and _sayi(db_oturumu) == 8
    assert defter.tutarlilik(db_oturumu) == []


def test_two_sessions_reserving_against_two_buckets_leave_exactly_one_short_in_100_rounds(depo_db, db_oturumu,
                                                                                          kullanici):
    """§2 çıkış ölçütü: iki kovadan (hibe 5 + paket 5) iki eş zamanlı 10'luk rezerv, 100 tekrar, çift düşüm 0,
    hiçbir kova eksiye inmez — Faz 3'ün kilit deseni (A düşer commit etmez, B kilitte bekler, güncel değeri görür)."""
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
            assert defter.hibe(db_oturumu, u, 5, f"hibe:{u}:tur{tur}") is True
            assert _paket(db_oturumu, u, 5, f"ord_{tur}") is True
            db_oturumu.commit()
            assert _kovalar_db(db_oturumu, u) == (5, 5)
            is_a, is_b = _is(db_oturumu, u), _is(db_oturumu, u)
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
            assert (sb.bakiye, sb.gereken, sb.hibe, sb.paket) == (0, 10, 0, 0) and (ha.kova, ha.miktar) == ("hibe", -5)
            yetersiz += 1
            assert _kovalar_db(db_oturumu, u) == (0, 0), f"tur {tur}: bir kova eksiye indi ya da düşmedi"
    assert yetersiz == 100
    rezervler = [r for r in _kovali_satirlar(db_oturumu, u) if r[0] == "rezerv"]
    assert len(rezervler) == 200 and {r[1] for r in rezervler} == {"hibe", "paket"}, "her turda ana + paket satırı"
    assert defter.tutarlilik(db_oturumu) == []


def test_downgrade_expires_the_grant_bucket_down_to_the_new_plans_grant_and_leaves_the_pack_alone(db_oturumu,
                                                                                                    kullanici):
    """`dusur` (K3/K6): hibe kovası `hedef`in üstündeyse `sona_erme` satırı `-(bakiye - hedef)` kova hibe;
    paket kovası DOKUNULMAZ (devreder); altındaysa/eşitse `None`; aynı anahtar ikinci kez `None`, bakiye oynamaz."""
    u = kullanici.id
    defter.hibe(db_oturumu, u, 2_500, f"hibe:{u}:2026-09")
    _paket(db_oturumu, u, 800, "ord_1")
    anahtar = f"sona_erme:{u}:sub_1:2026-09-21"
    an = zaman.an()
    h = defter.dusur(db_oturumu, u, 200, anahtar, an=an)
    db_oturumu.commit()
    assert h is not None and (h.tur, h.kova, h.miktar, h.idempotency_anahtari, h.olusturuldu, h.is_id) == (
        "sona_erme", "hibe", -2_300, anahtar, an, None)
    assert _kovalar_db(db_oturumu, u) == (200, 800), "paket durur"
    assert defter.dusur(db_oturumu, u, 200, anahtar) is None, "aynı anahtar: no-op"
    assert defter.dusur(db_oturumu, u, 200, f"sona_erme:{u}:sub_1:2026-09-22") is None, "hedefe eşit: düşecek şey yok"
    assert defter.dusur(db_oturumu, u, 1_000, f"sona_erme:{u}:sub_1:2026-09-23") is None, "hedefin altında: no-op"
    assert (_kovalar_db(db_oturumu, u), _sayi(db_oturumu)) == ((200, 800), 3)
    with pytest.raises(ValueError):
        defter.dusur(db_oturumu, u, -1, "sona_erme:kotu")
    assert defter.dusur(db_oturumu, uuid.uuid4(), 0, "sona_erme:yok") is None, "olmayan kullanıcı: no-op"
    assert defter.tutarlilik(db_oturumu) == []


def test_an_admin_correction_can_target_the_pack_bucket(db_oturumu, kullanici):
    """`duzelt(kova='paket')` (iade kararı K6, admin "paket kredisi ekle" 4. görev): `duzeltme` satırı kova paket,
    `paket_bakiye` oynar, hibe kovası durmaz; tanınmayan kova `ValueError`, satır yok."""
    u, admin = kullanici.id, _ikinci_kullanici(db_oturumu)
    _paket(db_oturumu, u, 500, "ord_1")
    h = defter.duzelt(db_oturumu, u, -120, "kullanılmamış paket iadesi", admin, kova="paket")
    db_oturumu.commit()
    assert (h.tur, h.kova, h.miktar, h.admin_id) == ("duzeltme", "paket", -120, admin)
    assert _kovalar_db(db_oturumu, u) == (0, 380)
    assert defter.duzelt(db_oturumu, u, 7, None, admin).kova == "hibe", "öntanım hibe kovası"
    assert _kovalar_db(db_oturumu, u) == (7, 380)
    with pytest.raises(ValueError):
        defter.duzelt(db_oturumu, u, 1, None, admin, kova="hediye")
    assert _sayi(db_oturumu) == 3 and defter.tutarlilik(db_oturumu) == []


def test_consistency_measures_the_two_buckets_separately(db_oturumu, kullanici):
    """`tutarlilik` iki SUM: paket önbelleği saptırılınca `Sapma` paket alanlarında görünür, hibe alanları eşit;
    ikisi birden sapabilir; hareketi olmayan kullanıcı iki toplamda 0."""
    u = kullanici.id
    b = _ikinci_kullanici(db_oturumu)
    defter.hibe(db_oturumu, u, 100, f"hibe:{u}:2026-09")
    _paket(db_oturumu, u, 500, "ord_1")
    defter.rezerve(db_oturumu, u, _is(db_oturumu, u), 130)      # hibe 100 + paket 30
    db_oturumu.commit()
    assert _kovalar_db(db_oturumu, u) == (0, 470) and defter.tutarlilik(db_oturumu) == []
    db_oturumu.execute(text("UPDATE kullanicilar SET paket_bakiye = 471 WHERE id = :k"), {"k": u})
    db_oturumu.execute(text("UPDATE kullanicilar SET paket_bakiye = 9 WHERE id = :k"), {"k": b})
    db_oturumu.commit()
    sapmalar = {s.kullanici_id: s for s in defter.tutarlilik(db_oturumu)}
    assert sapmalar[u] == defter.Sapma(u, 0, 0, 471, 470) and sapmalar[b] == defter.Sapma(b, 0, 0, 9, 0)
    db_oturumu.execute(text("UPDATE kullanicilar SET bakiye = -3 WHERE id = :k"), {"k": u})
    db_oturumu.commit()
    assert {s.kullanici_id: (s.bakiye - s.hibe_toplam, s.paket_bakiye - s.paket_toplam)
            for s in defter.tutarlilik(db_oturumu)} == {u: (-3, 1), b: (0, 9)}
    db_oturumu.execute(text("UPDATE kullanicilar SET bakiye = 0, paket_bakiye = 470 WHERE id = :k"), {"k": u})
    db_oturumu.execute(text("UPDATE kullanicilar SET paket_bakiye = 0 WHERE id = :k"), {"k": b})
    db_oturumu.commit()
    assert defter.tutarlilik(db_oturumu) == []


def test_the_monthly_grant_tour_ignores_the_pack_bucket(db_oturumu, kullanici):
    """K3'ün sebebi: paketli kullanıcı hibesini kaybetmez — `hibe_turu` yalnız HİBE kovasına bakar; paket 5.000
    olsa da hibe kovası 0 ise `free` hibesi tam yatar."""
    from services import planlar
    u = kullanici.id
    _paket(db_oturumu, u, 5_000, "ord_1")
    db_oturumu.commit()
    an = zaman.an()
    assert defter.hibe_turu(db_oturumu, an) >= 1
    assert _kovalar_db(db_oturumu, u) == (planlar.PLANLAR["free"].aylik_hibe, 5_000)
    assert defter.tutarlilik(db_oturumu) == []


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


# İki önbellek sütunu (Faz 4 / 2): `bakiye` VE `paket_bakiye` — `\bbakiye\b` alt çizgiden sonra eşleşmez.
_ONBELLEK = ("bakiye", "paket_bakiye")
_BAKIYE_SQL = re.compile(r"UPDATE\s+kullanicilar\b.*\b(paket_)?bakiye\b", re.I | re.S)
_DEFTER_SQL = re.compile(r"INSERT\s+INTO\s+kredi_hareketleri\b", re.I)


def _sozluk_anahtarlari(d: ast.Call) -> set[str]:
    """`.values({"bakiye": …})` biçimi: anahtar sözcük yerine sözlük — o da yazımdır."""
    adlar: set[str] = set()
    for a in d.args:
        if isinstance(a, ast.Dict):
            adlar |= {k.value for k in a.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return adlar


def _yazimlar(yol: str) -> tuple[list[int], list[int]]:
    """`(bakiye yazan satırlar, defter satırı kuran satırlar)` — AST: ORM (`.values(bakiye=…)`/`.values({"bakiye": …})`,
    `x.bakiye = …`, `Kullanici(bakiye=…)`, `KrediHareketi(…)`, `insert(KrediHareketi)`) ve ham SQL dizeleri;
    `paket_bakiye` de aynı yerlerde."""
    with open(os.path.join(REPO, yol), encoding="utf-8") as f:
        agac = ast.parse(f.read())
    bakiye: list[int] = []
    defter_: list[int] = []
    for d in ast.walk(agac):
        if isinstance(d, ast.Call):
            ad = d.func.attr if isinstance(d.func, ast.Attribute) else d.func.id if isinstance(d.func, ast.Name) else None
            if ad == "values" and (any(k.arg in _ONBELLEK for k in d.keywords) or _sozluk_anahtarlari(d) & set(_ONBELLEK)):
                bakiye.append(d.lineno)
            if ad == "Kullanici" and any(k.arg in _ONBELLEK for k in d.keywords):
                bakiye.append(d.lineno)
            if ad == "KrediHareketi":
                defter_.append(d.lineno)
            if ad == "insert" and any(isinstance(a, ast.Name) and a.id == "KrediHareketi" or
                                      isinstance(a, ast.Attribute) and a.attr == "KrediHareketi" for a in d.args):
                defter_.append(d.lineno)
        if isinstance(d, ast.Assign | ast.AugAssign):
            hedefler = d.targets if isinstance(d, ast.Assign) else [d.target]
            if any(isinstance(h, ast.Attribute) and h.attr in _ONBELLEK for h in hedefler):
                bakiye.append(d.lineno)
        if isinstance(d, ast.Constant) and isinstance(d.value, str):
            if _BAKIYE_SQL.search(d.value):
                bakiye.append(d.lineno)
            if _DEFTER_SQL.search(d.value):
                defter_.append(d.lineno)
    return bakiye, defter_


def test_only_the_ledger_module_writes_the_balance_cache_or_inserts_ledger_rows():
    """Belge §1 "Risk": `kullanicilar.bakiye`/`paket_bakiye`ye UPDATE kuran ve `kredi_hareketleri`ye satır yazan
    modül YALNIZ `services/defter.py` — rota ve işçi defteri ÇAĞIRIR, elle yazmaz (tests/test_galeri_db.py'nin
    AST deseni). Bekçinin bekçisi: defterin kendisi her ikisini de yapıyor görünmeli (tarama boşa dönmesin) —
    iki kovanın ikisi de (`.values(bakiye=…)`, `.values(paket_bakiye=…)`, CTE'li ham `UPDATE`)."""
    assert TEK_YAZAR in _urun_dosyalari()
    with open(os.path.join(REPO, TEK_YAZAR), encoding="utf-8") as f:
        kaynak = f.read()
    assert ".values(bakiye=" in kaynak and ".values(paket_bakiye=" in kaynak, "iki kova da anahtar sözcükle yazılmalı"
    for yol in _urun_dosyalari():
        bakiye, defter_ = _yazimlar(yol)
        if yol == TEK_YAZAR:
            assert len(bakiye) >= 3 and defter_, "defter.py'nin yazımları görünmüyor: bekçi kör"
            continue
        assert not bakiye, f"{yol}:{bakiye} `kullanicilar.bakiye` yazıyor — tek yazar services/defter.py"
        assert not defter_, f"{yol}:{defter_} `kredi_hareketleri`ye satır kuruyor — tek yazar services/defter.py"
