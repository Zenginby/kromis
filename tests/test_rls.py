# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""RLS ikinci kat (Faz 2 / 7): göç `0006_rls`, `services/kiraci.py`, `Session` kancası, işçi ve araç rolü.

ÖLÇÜM İKİNCİ BİR ROLLE, ve bu dosyanın en önemli kararı: takımın Postgres'i
süper kullanıcı (CI servisi `postgres`, geçici küme `kromis`), ve süper
kullanıcı RLS'i `FORCE`a rağmen ATLAR. Öteki 3.600 test o motorla koşuyor —
orada politika görünmez, yani "testler yeşil" RLS hakkında hiçbir şey demez.
Buradaki yalıtım iddiaları `kromis_rls_test` adlı NOLOGIN bir rol yaratır,
tablolara ayrıcalık verir ve uygulama motorunun her bağlantısında `SET ROLE`
yapar: o bağlantı ne süper kullanıcı ne tablo sahibi — canlıdaki uygulama
rolünün ta kendisi. Canlı rolün de öyle olduğunu sahibi `pg_roles`tan doğrular
(KURULUM.md; `test_the_superuser_bypasses_…` bu tuzağı yeşil bir testle
belgeliyor).

İki katman ayrı ayrı sınanır: (1) POLİTİKA — ham `Connection` ve `set_config`
ile, uygulama kodu olmadan (bağlamsız 0 satır; sahip yalnız kendi satırı;
başkasının id'siyle INSERT reddi; başkasının satırına UPDATE/DELETE 0 satır;
admin okur ve günceller, silemez/ekleyemez; boş dize dönüşüm hatası vermez;
`SET LOCAL` transaksiyonla düşer). (2) UYGULAMA — `Session` kancası bağlamı
transaksiyonun ilk ifadesi yapar, kimlik kapısı gerçek girişte aynı
transaksiyona yazar, kapılı rota uygulama rolü altında kendi satırlarını
listeler, işçi kuyruğu admin olarak alır ve sonucu işin kiracısı olarak yazar,
araçlar bağlam taşır (kaynak bekçisi). Göç: 9 tablo + FORCE (`pg_class`),
üç politika (`pg_policies`), downgrade geri alır, `alembic check` temiz.

FAZ 3 / 1 (`0007_kredi`): dokuzuncu tablo `kredi_hareketleri` aynı üç politika +
yalnız orada DÖRDÜNCÜ, `yonetici_ekler` INSERT (K4: admin düzeltmesi ve işçinin
bakım turu admin bağlamında yazar). Ölçülen dört iddia: kullanıcı başkasının
hareketini okuyamaz, admin okur, admin EKLER, admin SİLEMEZ; öteki sekiz tabloda
dördüncü politika BULUNMAZ. Politika sayısı 24 → 28.

FAZ 4 / 2 (`0008_odeme`): onuncu tablo `siparisler` aynı üç politika + `yonetici_ekler`
(webhook oturumsuz, admin bağlamında yazar — 3. görev); `urunler` ve `odeme_olaylari`
POLİTİKASIZ altyapı tabloları (kullanıcı sütunu yok / NULL'lanabilir). İş tablosu
türetimi bu yüzden NOT NULL `kullanici_id` arar. Politika sayısı 28 → 32.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
import re
import uuid

import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

import app as appmod
import providers
from services import ayar, cerez, db, defter, dosya, hesap, isci, kimlik, kiraci, kuyruk, tablolar
from services.tablolar import Kullanici, Medya

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(16))

# Ne süper kullanıcı ne tablo sahibi: canlıdaki uygulama rolünün test ikizi.
ROL = "kromis_rls_test"
# Hesap tabloları politikasız (services/kiraci.py, `IS_TABLOLARI`nın gerekçesi).
HESAP_TABLOLARI = {"kullanicilar", "oturumlar", "jetonlar", "giris_denemeleri"}
# `Session(` açan HER araç kiracı bağlamı taşımak zorunda — elle tutulan liste,
# bekçisi `test_every_tool_that_opens_a_session_binds_a_tenant_context`
# (dosya sisteminden türetilen kümeyle karşılaştırılır; `medya_tasi.py` ve
# `goc.py` oturum açmaz — biri yalnız dosya taşır, öteki Alembic'e devreder).
BAGLAM_TASIYAN_ARACLAR = {"anahtar_dondur.py", "artik_dosya.py", "ice_aktar.py",
                          "kullanici.py", "uygulama_rolu.py",
                          # Faz 3 / 5: `isler`i admin bağlamında okur (bağlamsız RLS boş döner).
                          "marj_raporu.py"}


# ────────────────────────────────────────────────────────── fixture'lar

@pytest.fixture(scope="module")
def uygulama_motoru(veritabani_url: str):
    """Uygulama rolüyle bağlanan motor: rol yaratılır, tablolara yetki verilir, her bağlantı `SET ROLE`.

    Rol küme genelidir (`IF NOT EXISTS` deyimi `KROMIS_TEST_DATABASE_URL`in
    tekrar koşularında gerekir); yetkiler bu modülün DB'sine. `SET ROLE`
    transaksiyonel: bağlantı kancasında COMMIT edilmeden havuza dönerdi ve
    SQLAlchemy'nin iade `rollback`ı rolü geri alırdı — ölçüldü, o yüzden
    `dbapi.commit()`. `pool_size=1`: "havuzdan dönen bağlantı kiracı taşımaz"
    testi aynı bağlantıyı ikinci kez almak zorunda.
    """
    yonetici = create_engine(veritabani_url, isolation_level="AUTOCOMMIT")
    try:
        with yonetici.connect() as c:
            c.execute(text(f"""DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROL}') THEN
                    CREATE ROLE {ROL} NOLOGIN;
                END IF; END $$"""))
            c.execute(text(f"GRANT USAGE ON SCHEMA public TO {ROL}"))
            c.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROL}"))
            satir = c.execute(text(f"SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = '{ROL}'")).one()
            assert tuple(satir) == (False, False), "rol RLS'i atlıyor olsaydı ölçüm anlamsızdı"
    finally:
        yonetici.dispose()

    motor = create_engine(veritabani_url, pool_size=1, max_overflow=0)

    @event.listens_for(motor, "connect")
    def _rol(dbapi_baglanti, _kayit):
        with dbapi_baglanti.cursor() as imlec:
            imlec.execute(f"SET ROLE {ROL}")
        dbapi_baglanti.commit()

    yield motor
    motor.dispose()


@pytest.fixture(autouse=True)
def temiz(depo_db):
    """Her test boş iş tablolarıyla başlar; `kullanici` fixture'ının test kullanıcısı kalır (o kendini yeniler)."""
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM isler"))
        c.execute(text("DELETE FROM isciler"))
        c.execute(text("DELETE FROM kullanicilar WHERE eposta LIKE 'b-%@example.com'"))
        # Faz 4 / 2: ürün aynası platformun — kullanıcıyla gitmez, sipariş ona FK'lı (önce sipariş).
        c.execute(text("DELETE FROM siparisler"))
        c.execute(text("DELETE FROM urunler"))
    yield


@pytest.fixture
def ikinci(db_oturumu) -> uuid.UUID:
    k = Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                  dogrulandi_at=hesap.simdi(), dil=None)
    db_oturumu.add(k)
    db_oturumu.commit()
    return k.id


@pytest.fixture
def tohum(db_oturumu, kullanici, ikinci) -> tuple[uuid.UUID, uuid.UUID]:
    """Dokuz tablonun her birine A (test kullanıcısı) ve B için birer satır; `(A, B)`. Süper kullanıcı yazar."""
    for kid in (kullanici.id, ikinci):
        _her_tabloya_bir_satir(db_oturumu, kid)
    db_oturumu.commit()
    return kullanici.id, ikinci


def _urun(s: Session) -> uuid.UUID:
    """Faz 4 / 2: `siparisler.urun_id` NOT NULL FK; ürün aynası platformun (politikasız), süper kullanıcı yazar."""
    u = tablolar.Urun(polar_urun_id=f"prod_{uuid.uuid4().hex[:8]}", tur="paket", kredi=500, fiyat_kurus=500,
                      para_birimi="usd", ad="500 kredi")
    s.add(u)
    s.flush()
    return u.id


def _her_tabloya_bir_satir(s: Session, kid: uuid.UUID) -> None:
    klasor = tablolar.Klasor(id=uuid.uuid4().hex, kullanici_id=kid, name="K")
    s.add(klasor)
    s.flush()
    urun_id = _urun(s)
    s.add_all([
        Medya(id=uuid.uuid4().hex[:12], kullanici_id=kid, filename=f"{klasor.id}.png", prompt="p",
              size="1024x1024", quality="high", folder_id=None, model="m", credits=1),
        tablolar.Sohbet(id=uuid.uuid4().hex, kullanici_id=kid, title="S", mesajlar=[]),
        tablolar.Palet(id=uuid.uuid4().hex, kullanici_id=kid, name="P", seed="#fff", mode="mono",
                       strength="orta", colors=[]),
        tablolar.Varlik(id=uuid.uuid4().hex, kullanici_id=kid, filename=f"{klasor.id}-l.png", name="L",
                        tur="logos"),
        tablolar.Tercih(kullanici_id=kid, theme="mono"),
        tablolar.SaglayiciKimligi(kullanici_id=kid, ad="OPENAI_API_KEY", sifreli_deger=b"gAAAA",
                                  anahtar_surumu=1),
        tablolar.Is(kullanici_id=kid, tur="generate", istek={"prompt": "p"}, model="m", kredi_tahmini=1),
        tablolar.KrediHareketi(kullanici_id=kid, tur="hibe", miktar=5, idempotency_anahtari=f"hibe:{kid}:2026-09"),
        tablolar.Siparis(kullanici_id=kid, polar_siparis_id=f"ord_{kid}", urun_id=urun_id, sebep="purchase",
                         tutar_kurus=500, para_birimi="usd"),
    ])
    s.flush()


def _sayimlar(baglanti) -> dict[str, int]:
    return {t: baglanti.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in kiraci.IS_TABLOLARI}


def _bagla_sql(baglanti, *, kullanici_id: uuid.UUID | None = None, rol: str | None = None) -> None:
    """Politikanın okuduğu ayarı UYGULAMA KODU OLMADAN yazar — (1) katmanı tek başına ölçülsün."""
    baglanti.execute(text("SELECT set_config('app.kullanici_id', :k, true), set_config('app.rol', :r, true)"),
                     {"k": str(kullanici_id) if kullanici_id else "", "r": rol or ""})


def _izle(motor) -> tuple[list[tuple[str, object]], object]:
    """`before_cursor_execute` izi: `(ifade, parametreler)` listesi ve `event.remove` için dinleyici."""
    iz: list[tuple[str, object]] = []

    def _say(conn, cursor, statement, parameters, context, executemany):
        iz.append((statement, parameters))

    event.listen(motor, "before_cursor_execute", _say)
    return iz, _say


# ────────────────────────────────────────────── göç: kapsam, FORCE, politikalar

def test_the_ten_tenant_tables_and_only_they_have_rls_enabled_and_forced(depo_db):
    """Beş kaynak aynı kümeyi söyler: `IS_TABLOLARI`, üç göçün literalleri (0006: 8, 0007: 9, 0008: 10), metadata
    (NOT NULL `kullanici_id` − hesap; `odeme_olaylari`nın NULL'lanabilir sütunu onu iş tablosu yapmaz); DB'de hepsi FORCE."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    turetilen = {ad for ad, t in tablolar.Base.metadata.tables.items()
                 if "kullanici_id" in t.c and not t.c["kullanici_id"].nullable} - HESAP_TABLOLARI
    assert turetilen == set(kiraci.IS_TABLOLARI) and len(kiraci.IS_TABLOLARI) == 10
    assert tablolar.Base.metadata.tables["odeme_olaylari"].c["kullanici_id"].nullable, "sahibi olmayan olay satırı"
    betikler = ScriptDirectory.from_config(Config(os.path.join(REPO, "alembic.ini")))
    goc6 = betikler.get_revision("0006_rls").module
    goc7 = betikler.get_revision("0007_kredi").module
    goc8 = betikler.get_revision("0008_odeme").module
    assert tuple(goc8.TABLOLAR) == kiraci.IS_TABLOLARI, "0008 literali ile kod listesi ayrıştı"
    assert tuple(goc7.TABLOLAR) == kiraci.IS_TABLOLARI[:9], "0007 literali (tarihçe) ilk dokuz"
    assert tuple(goc6.TABLOLAR) + tuple(goc7.RLS_TABLOLAR) + tuple(goc8.RLS_TABLOLAR) == kiraci.IS_TABLOLARI, \
        "0006 (8) + 0007 (1) + 0008 (1) = 10"
    assert tuple(goc7.YONETICI_EKLER) + tuple(goc8.YONETICI_EKLER) == kiraci.YONETICI_EKLER_TABLOLARI == (
        "kredi_hareketleri", "siparisler")

    with depo_db.connect() as c:
        satirlar = c.execute(text("SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                                  "WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace")).all()
    acik = {ad for ad, rls, _ in satirlar if rls}
    assert acik == set(kiraci.IS_TABLOLARI), f"RLS açık tablolar listeyle aynı değil: {sorted(acik)}"
    assert all(force for ad, _, force in satirlar if ad in acik), "FORCE eksik: tablo sahibi politikayı atlar"
    assert {ad for ad, *_ in satirlar} >= HESAP_TABLOLARI | {"isciler", "urunler", "odeme_olaylari"}, \
        "kapsam dışı tablolar var ve politikasız"


def test_every_tenant_table_carries_the_owner_policy_and_the_two_admin_policies(depo_db):
    """…ve YALNIZ `kredi_hareketleri` ile `siparisler` dördüncüyü (`yonetici_ekler` INSERT, Faz 3 K4 / Faz 4 / 2);
    öteki sekizde dört BULUNMAZ."""
    with depo_db.connect() as c:
        satirlar = c.execute(text("SELECT tablename, policyname, cmd, permissive, qual, with_check "
                                  "FROM pg_policies WHERE schemaname = 'public'")).all()
    for tablo in kiraci.IS_TABLOLARI:
        p = {ad: (cmd, izin, qual, wc) for t, ad, cmd, izin, qual, wc in satirlar if t == tablo}
        beklenen = {"sahip", "yonetici_okur", "yonetici_gunceller"}
        if tablo in kiraci.YONETICI_EKLER_TABLOLARI:
            beklenen.add("yonetici_ekler")
            assert p["yonetici_ekler"][0] == "INSERT" and p["yonetici_ekler"][2] is None, "INSERT: yalnız WITH CHECK"
            assert "app.rol" in p["yonetici_ekler"][3] and "admin" in p["yonetici_ekler"][3]
        assert set(p) == beklenen, (tablo, sorted(p))
        assert p["sahip"][0] == "ALL" and "app.kullanici_id" in p["sahip"][2] and "app.kullanici_id" in p["sahip"][3]
        assert "NULLIF" in p["sahip"][2], "boş dize NULL sayılmalı, `''::uuid` hata verir"
        assert p["yonetici_okur"][0] == "SELECT" and "app.rol" in p["yonetici_okur"][2]
        assert p["yonetici_gunceller"][0] == "UPDATE" and "app.rol" in p["yonetici_gunceller"][2]
        assert all(izin == "PERMISSIVE" for izin in (v[1] for v in p.values())), "admin kendi satırını da görsün"
    assert not {t for t, *_ in satirlar} - set(kiraci.IS_TABLOLARI), "politika yalnız iş tablolarında"
    assert len(satirlar) == 32, "3 × 10 + 2 (tools/rls_kontrol.py `beklenen_politika` ile aynı sayı)"


def test_downgrade_removes_the_policies_and_disables_rls_and_upgrade_restores_them(veritabani, depo_db,
                                                                                 uygulama_motoru):
    """0008 (sipariş tablosu + 4 politika), 0007 (kredi tablosu + 4) ve 0006 (8 × 3) geri alınır: 0 politika,
    RLS'li tablo yok; head 32 politika."""
    from alembic.config import Config

    from alembic import command
    cfg = Config(os.path.join(REPO, "alembic.ini"))
    cfg.attributes["baglanti_dizesi"] = veritabani
    depo_db.dispose()
    uygulama_motoru.dispose()            # havuzdaki bağlantılar DDL'e takılmasın
    motor = create_engine(veritabani)
    try:
        command.downgrade(cfg, "0007_kredi")
        with motor.connect() as c:
            assert c.execute(text("SELECT count(*) FROM pg_policies WHERE schemaname = 'public'")).scalar_one() == 28
            assert c.execute(text("SELECT to_regclass('siparisler')")).scalar_one() is None
        command.downgrade(cfg, "0006_rls")
        with motor.connect() as c:
            assert c.execute(text("SELECT count(*) FROM pg_policies WHERE schemaname = 'public'")).scalar_one() == 24
            assert c.execute(text("SELECT to_regclass('kredi_hareketleri')")).scalar_one() is None
        command.downgrade(cfg, "0005_kota")
        with motor.connect() as c:
            assert c.execute(text("SELECT count(*) FROM pg_policies WHERE schemaname = 'public'")).scalar_one() == 0
            assert c.execute(text("SELECT count(*) FROM pg_class WHERE relrowsecurity OR relforcerowsecurity")
                             ).scalar_one() == 0
        command.upgrade(cfg, "head")
        with motor.connect() as c:
            assert c.execute(text("SELECT count(*) FROM pg_policies WHERE schemaname = 'public'")).scalar_one() == 32
            assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0008_odeme"
        command.check(cfg)               # politika metadata'da değil; `check` şemayı görür, fark yok
        # `kredi_hareketleri`/`siparisler` DÜŞÜP YENİDEN KURULDU: `GRANT … ON ALL TABLES` eski nesneye verilmişti, yeni
        # tablo yetkisiz doğar ve bu dosyanın sonraki uygulama-rolü testleri "permission denied" görürdü
        # (ölçüldü). Fixture'ın verdiği yetki yeniden verilir; canlıda `tools/uygulama_rolu.py`nin
        # `ALTER DEFAULT PRIVILEGES`i aynı boşluğu kapatır.
        with motor.begin() as c:
            c.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROL}"))
    finally:
        motor.dispose()


# ──────────────────────────────────────── (1) politika, uygulama kodu olmadan

def test_the_superuser_bypasses_forced_rls_which_is_why_isolation_is_measured_under_a_second_role(depo_db, tohum):
    """CI TUZAĞI, yeşil testle belgelenmiş: takımın motoru süper kullanıcı ve bağlamsız her satırı görür."""
    with depo_db.connect() as c:
        assert c.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar_one() is True
        assert _sayimlar(c) == dict.fromkeys(kiraci.IS_TABLOLARI, 2)


def test_without_a_binding_an_unfiltered_select_returns_no_rows_not_an_error(uygulama_motoru, tohum):
    """Süzgeç unutulursa sonuç BOŞ, sızıntı değil — ve 500 de değil (`current_setting(…, true)` NULL)."""
    with uygulama_motoru.connect() as c:
        assert c.execute(text("SELECT current_user")).scalar_one() == ROL
        assert c.execute(text("SELECT current_setting('app.kullanici_id', true)")).scalar_one() in (None, "")
        assert _sayimlar(c) == dict.fromkeys(kiraci.IS_TABLOLARI, 0)


def test_a_bound_user_sees_only_their_own_rows_in_every_tenant_table(uygulama_motoru, tohum):
    a, b = tohum
    with uygulama_motoru.connect() as c:
        _bagla_sql(c, kullanici_id=a)
        assert _sayimlar(c) == dict.fromkeys(kiraci.IS_TABLOLARI, 1)
        for t in kiraci.IS_TABLOLARI:
            assert c.execute(text(f"SELECT DISTINCT kullanici_id FROM {t}")).scalars().all() == [a], t
        assert c.execute(text("SELECT count(*) FROM medya WHERE kullanici_id = :b"), {"b": b}).scalar_one() == 0


def test_an_empty_setting_yields_no_rows_instead_of_a_cast_error(uygulama_motoru, tohum):
    """`''::uuid` hata verirdi; politika `NULLIF` ile boş dizeyi "bağlı değil" sayar (kiraci.uygula boş dize yazar)."""
    with uygulama_motoru.connect() as c:
        _bagla_sql(c)                      # ikisi de ''
        assert c.execute(text("SELECT current_setting('app.kullanici_id', true)")).scalar_one() == ""
        assert _sayimlar(c) == dict.fromkeys(kiraci.IS_TABLOLARI, 0)


def test_an_insert_carrying_another_users_id_is_rejected_by_with_check(uygulama_motoru, tohum):
    a, b = tohum
    with uygulama_motoru.connect() as c:
        _bagla_sql(c, kullanici_id=a)
        with pytest.raises(sa_exc.ProgrammingError, match="row-level security"):
            c.execute(text("INSERT INTO klasorler (id, kullanici_id, name) VALUES (:id, :k, 'x')"),
                      {"id": uuid.uuid4().hex, "k": b})


def test_an_update_or_delete_of_another_users_row_touches_nothing_and_raises_nothing(uygulama_motoru, depo_db,
                                                                                     tohum):
    a, b = tohum
    with uygulama_motoru.connect() as c:
        _bagla_sql(c, kullanici_id=a)
        assert c.execute(text("UPDATE medya SET prompt = 'ele gecti' WHERE kullanici_id = :b"), {"b": b}).rowcount == 0
        assert c.execute(text("DELETE FROM medya WHERE kullanici_id = :b"), {"b": b}).rowcount == 0
        assert c.execute(text("UPDATE medya SET prompt = 'benim' WHERE kullanici_id = :a"), {"a": a}).rowcount == 1
        c.commit()
    with depo_db.connect() as c:
        assert c.execute(text("SELECT prompt FROM medya WHERE kullanici_id = :b"), {"b": b}).scalar_one() == "p"
        assert c.execute(text("SELECT count(*) FROM medya")).scalar_one() == 2


def test_the_admin_role_reads_and_updates_every_row_but_cannot_insert_or_delete(uygulama_motoru, depo_db, tohum):
    """8. görevin ihtiyacı tam bu: tavan/iptal yazar (UPDATE), listeler (SELECT); silmez, eklemez."""
    a, b = tohum
    with uygulama_motoru.connect() as c:
        _bagla_sql(c, rol=kiraci.ADMIN)
        assert _sayimlar(c) == dict.fromkeys(kiraci.IS_TABLOLARI, 2)
        assert c.execute(text("UPDATE isler SET durum = 'iptal' WHERE kullanici_id = :b"), {"b": b}).rowcount == 1
        assert c.execute(text("DELETE FROM isler")).rowcount == 0, "admin politikası DELETE vermez"
        with pytest.raises(sa_exc.ProgrammingError, match="row-level security"):
            c.execute(text("INSERT INTO klasorler (id, kullanici_id, name) VALUES (:id, :k, 'x')"),
                      {"id": uuid.uuid4().hex, "k": a})
        c.rollback()
    with uygulama_motoru.connect() as c:
        # admin + kullanıcı birlikte: rota kendi satırını da görür (PERMISSIVE), sahip yazımı sürer.
        _bagla_sql(c, kullanici_id=a, rol=kiraci.ADMIN)
        assert c.execute(text("SELECT count(*) FROM medya")).scalar_one() == 2
        assert c.execute(text("DELETE FROM medya WHERE kullanici_id = :a"), {"a": a}).rowcount == 1
        c.rollback()


def test_the_admin_role_inserts_into_the_credit_ledger_but_still_cannot_delete_from_it(uygulama_motoru, depo_db,
                                                                                      tohum):
    """Faz 3 / 1 dördüncü iddia (K4): admin `kredi_hareketleri`ye B adına EKLER (`yonetici_ekler` — düzeltme ve bakım
    turu bu bağlamda yazar), yine SİLEMEZ (append-only); öteki sekiz tabloda INSERT hâlâ reddedilir (0006 durur).
    Kullanıcı A ise B'nin hareketini ne okur ne B adına ekler (`sahip` WITH CHECK)."""
    a, b = tohum
    with uygulama_motoru.connect() as c:
        _bagla_sql(c, rol=kiraci.ADMIN)
        assert c.execute(text("INSERT INTO kredi_hareketleri (kullanici_id, tur, miktar, admin_id, idempotency_anahtari) "
                              "VALUES (:b, 'duzeltme', -3, :a, :k)"),
                         {"b": b, "a": a, "k": f"duzeltme:{uuid.uuid4()}"}).rowcount == 1
        assert c.execute(text("SELECT count(*) FROM kredi_hareketleri")).scalar_one() == 3
        assert c.execute(text("DELETE FROM kredi_hareketleri")).rowcount == 0, "admin politikası DELETE vermez"
        with pytest.raises(sa_exc.ProgrammingError, match="row-level security"):
            c.execute(text("INSERT INTO isler (kullanici_id, tur, istek, model, kredi_tahmini) "
                           "VALUES (:b, 'generate', '{}', 'm', 1)"), {"b": b})
        c.rollback()
    with uygulama_motoru.connect() as c:
        _bagla_sql(c, kullanici_id=a)
        assert c.execute(text("SELECT count(*) FROM kredi_hareketleri WHERE kullanici_id = :b"), {"b": b}
                         ).scalar_one() == 0
        with pytest.raises(sa_exc.ProgrammingError, match="row-level security"):
            c.execute(text("INSERT INTO kredi_hareketleri (kullanici_id, tur, miktar, idempotency_anahtari) "
                           "VALUES (:b, 'hibe', 100, :k)"), {"b": b, "k": f"hibe:{uuid.uuid4()}"})
        c.rollback()
    with depo_db.connect() as c:
        assert c.execute(text("SELECT count(*) FROM kredi_hareketleri")).scalar_one() == 2, "hiçbir şey kalıcı olmadı"


def test_the_admin_role_inserts_orders_for_a_user_but_a_user_cannot_insert_anothers_order(uygulama_motoru, depo_db,
                                                                                         tohum):
    """Faz 4 / 2 (K4 devamı): webhook admin bağlamında B adına `siparisler`e EKLER (`yonetici_ekler` — 3. görevin
    tek yazım yolu), SİLEMEZ; kullanıcı A B'nin siparişini ne okur ne B adına ekler; `urunler` politikasız —
    uygulama rolü bağlamsız da okur (fiyat listesi herkese)."""
    a, b = tohum
    with depo_db.connect() as c:
        urun_id = c.execute(text("SELECT id FROM urunler LIMIT 1")).scalar_one()
    with uygulama_motoru.connect() as c:
        assert c.execute(text("SELECT count(*) FROM urunler")).scalar_one() == 2, "ürün aynası bağlamsız okunur"
        _bagla_sql(c, rol=kiraci.ADMIN)
        assert c.execute(text("INSERT INTO siparisler (kullanici_id, polar_siparis_id, urun_id, sebep, tutar_kurus, "
                              "para_birimi) VALUES (:b, :s, :u, 'purchase', 500, 'usd')"),
                         {"b": b, "s": f"ord_{uuid.uuid4().hex[:8]}", "u": urun_id}).rowcount == 1
        assert c.execute(text("SELECT count(*) FROM siparisler")).scalar_one() == 3
        assert c.execute(text("DELETE FROM siparisler")).rowcount == 0, "admin politikası DELETE vermez"
        c.rollback()
    with uygulama_motoru.connect() as c:
        _bagla_sql(c, kullanici_id=a)
        assert c.execute(text("SELECT count(*) FROM siparisler WHERE kullanici_id = :b"), {"b": b}).scalar_one() == 0
        assert c.execute(text("SELECT count(*) FROM siparisler")).scalar_one() == 1
        with pytest.raises(sa_exc.ProgrammingError, match="row-level security"):
            c.execute(text("INSERT INTO siparisler (kullanici_id, polar_siparis_id, urun_id, sebep, tutar_kurus, "
                           "para_birimi) VALUES (:b, :s, :u, 'purchase', 500, 'usd')"),
                      {"b": b, "s": f"ord_{uuid.uuid4().hex[:8]}", "u": urun_id})
        c.rollback()
    with depo_db.connect() as c:
        assert c.execute(text("SELECT count(*) FROM siparisler")).scalar_one() == 2, "hiçbir şey kalıcı olmadı"


def test_set_local_falls_at_the_end_of_the_transaction_so_a_pooled_connection_carries_no_tenant(uygulama_motoru,
                                                                                               tohum):
    """Pooler transaksiyon kipinin ön koşulu: ayar COMMIT'le düşer; havuzdan aynı bağlantıyı alan sonraki
    transaksiyon kiracısızdır (`pool_size=1`, aynı DBAPI bağlantısı olduğu doğrulanır)."""
    a, _ = tohum
    with uygulama_motoru.connect() as c:
        _bagla_sql(c, kullanici_id=a)
        assert c.execute(text("SELECT count(*) FROM medya")).scalar_one() == 1
        ilk = id(c.connection.dbapi_connection)
        c.commit()
        assert c.execute(text("SELECT current_setting('app.kullanici_id', true)")).scalar_one() in (None, "")
        assert c.execute(text("SELECT count(*) FROM medya")).scalar_one() == 0
    with uygulama_motoru.connect() as c:
        assert id(c.connection.dbapi_connection) == ilk, "havuz aynı bağlantıyı vermedi; ölçüm başka şeyi ölçer"
        assert c.execute(text("SELECT count(*) FROM medya")).scalar_one() == 0


# ─────────────────────────────────────────── (2) uygulama: kanca, kapı, rota

def test_the_after_begin_hook_is_registered_on_the_session_class_and_stays_silent_without_a_context(
        uygulama_motoru, tohum):
    assert event.contains(Session, "after_begin", db.kiraci_bagla)
    iz, dinleyici = _izle(uygulama_motoru)
    try:
        kiraci.sifirla()
        with Session(uygulama_motoru) as s:
            assert s.scalar(select(func.count()).select_from(Medya)) == 0
    finally:
        event.remove(uygulama_motoru, "before_cursor_execute", dinleyici)
    assert len(iz) == 1 and "set_config" not in iz[0][0], iz


def test_the_session_hook_binds_the_context_as_the_first_statement_and_rebinds_after_commit(uygulama_motoru,
                                                                                            tohum):
    """Aynı `Session`, iki transaksiyon, iki kiracı: kanca her transaksiyonun başında o anki bağlamı yazar."""
    a, b = tohum
    iz, dinleyici = _izle(uygulama_motoru)
    try:
        with Session(uygulama_motoru) as s:
            with kiraci.baglam(kullanici_id=a):
                assert s.scalars(select(Medya.kullanici_id)).all() == [a]
                s.commit()
            with kiraci.baglam(kullanici_id=b):
                assert s.scalars(select(Medya.kullanici_id)).all() == [b]
                s.commit()
            with kiraci.baglam(rol=kiraci.ADMIN):
                assert set(s.scalars(select(Medya.kullanici_id)).all()) == {a, b}
    finally:
        event.remove(uygulama_motoru, "before_cursor_execute", dinleyici)
    ifadeler = [i for i, _ in iz]
    assert [("set_config" in i) for i in ifadeler] == [True, False, True, False, True, False], ifadeler
    assert str(a) in str(iz[0][1]) and str(b) in str(iz[2][1]) and "admin" in str(iz[4][1])


def test_uygula_writes_into_an_open_transaction_and_defers_to_the_hook_on_a_fresh_session(uygulama_motoru,
                                                                                          tohum):
    """`kimlik._coz` ve `isci.siradakini_al`in dayandığı iki davranış: açık transaksiyona yazar, taze oturumda susar."""
    a, _ = tohum
    with kiraci.baglam(kullanici_id=a), Session(uygulama_motoru) as s:
        assert kiraci.uygula(s) is False, "transaksiyon yok: kanca yazacak, iki kez gitmesin"
        kiraci.sifirla()
        assert s.scalar(select(func.count()).select_from(Medya)) == 0      # kanca bağlamsız geçti
        kiraci.bagla(kullanici_id=a)
        assert kiraci.uygula(s) is True                                     # açık transaksiyona sonradan
        assert s.scalar(select(func.count()).select_from(Medya)) == 1
    kiraci.sifirla()
    assert kiraci.uygula(Session(uygulama_motoru)) is False, "bağlam yokken hiçbir şey yazılmaz"


def test_kimlik_bagla_binds_the_tenant_context_of_the_resolved_user(kullanici):
    """Kapının tek bağlama noktası (`kimlik.bagla`) kiracıyı da bağlar — override'lı 3.100 test bu yoldan geçer."""
    from starlette.requests import Request
    kiraci.sifirla()
    istek = Request({"type": "http", "headers": [], "method": "GET", "path": "/", "query_string": b""})
    kimlik.bagla(istek, kullanici)
    assert kiraci.aktif() == kiraci.Baglam(kullanici_id=kullanici.id, rol=None)


@pytest.mark.gercek_kimlik
def test_the_real_login_path_binds_the_tenant_right_after_the_identity_query(veritabani, tmp_path, dizinler,
                                                                            monkeypatch):
    """BEKÇİ — her kapılı rota bağlamla koşar: test_kimlik her rotanın kapılı ya da gerekçeli açık olduğunu
    sınıyor, kapının tek çözüm noktası `_coz` burada ölçülüyor: kimlik sorgusu → aynı transaksiyona
    `set_config(kullanıcı)` → rotanın ilk iş tablosu sorgusu. Açık rotalar hesap tablolarında."""
    from fastapi.testclient import TestClient
    monkeypatch.delenv(cerez.GUVENLI_ENV, raising=False)
    dizinler(data_dir=str(tmp_path))
    with TestClient(appmod.app, base_url="https://testserver"):   # lifespan: motor kurulur
        motor = appmod.app.state.motor
        an = hesap.simdi()
        with Session(motor) as s:
            k = Kullanici(eposta=f"{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None, dogrulandi_at=an)
            s.add(k)
            s.flush()
            jeton = hesap.oturum_ac(s, k, None, "test", an)
            kid = k.id
            s.commit()
        iz, dinleyici = _izle(motor)
        try:
            r = TestClient(appmod.app, base_url="https://testserver", cookies={cerez.OTURUM_CEREZI: jeton}
                           ).get("/api/history")
        finally:
            event.remove(motor, "before_cursor_execute", dinleyici)
    assert r.status_code == 200
    ifadeler = [i for i, _ in iz]
    assert len(ifadeler) == 3, ifadeler
    assert "oturumlar" in ifadeler[0] and "kullanicilar" in ifadeler[0]
    assert "set_config" in ifadeler[1] and str(kid) in str(iz[1][1]), iz[1]
    assert "medya" in ifadeler[2] and "set_config" not in ifadeler[2]


def test_a_gated_route_under_the_application_role_lists_only_the_users_rows(uygulama_motoru, depo_db, tohum,
                                                                             kullanici):
    """Uçtan uca, uygulama rolüyle: rota BOŞ dönmez (kırılma sınıfı (a)) ve yalnız kendi satırlarını görür."""
    from fastapi.testclient import TestClient
    a, b = tohum

    def _uygulama_oturumu():
        with Session(uygulama_motoru) as s:
            yield s
            s.commit()

    appmod.app.dependency_overrides[db.oturum] = _uygulama_oturumu    # `kullanici` fixture'ı teardown'da düşürür
    iz, dinleyici = _izle(uygulama_motoru)
    try:
        c = TestClient(appmod.app)
        gorseller = c.get("/api/history").json()["images"]
        isler = c.get("/api/isler").json()["isler"]
    finally:
        event.remove(uygulama_motoru, "before_cursor_execute", dinleyici)
    with depo_db.connect() as s:
        a_medya = s.execute(text("SELECT id FROM medya WHERE kullanici_id = :a"), {"a": a}).scalars().all()
        a_is = s.execute(text("SELECT id::text FROM isler WHERE kullanici_id = :a"), {"a": a}).scalars().all()
    assert [g["id"] for g in gorseller] == a_medya and a_medya
    assert [i["id"] for i in isler] == a_is and a_is
    assert "set_config" in iz[0][0] and str(a) in str(iz[0][1]), "isteğin ilk ifadesi kiracı bağlaması"
    assert str(b) not in str(iz), "başkasının id'si hiçbir ifadede yok"


def test_the_sse_stream_under_the_application_role_carries_the_tenant_into_its_own_sessions(
        uygulama_motoru, depo_db, db_oturumu, kullanici, ikinci, monkeypatch):
    """`GET /api/isler/akis` sorgularını `run_in_threadpool` içinde KENDİ kısa oturumlarıyla yapar
    (routers/isler.py): isteğin görevinde bağlanan kiracı o kopyaya taşınmalı — taşınmasa akış
    uygulama rolünde sessizce BOŞ kalır (sızıntı değil, ama panel donar)."""
    from fastapi.testclient import TestClient

    from routers import isler as isler_rotasi
    monkeypatch.setattr(isler_rotasi, "AKIS_YOKLAMA_SN", 0.05)
    monkeypatch.setattr(isler_rotasi, "AKIS_AZAMI_SN", 0.3)
    govde = {"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1, "folder_id": None,
             "session_id": None}
    a_is = kuyruk.ekle(db_oturumu, kullanici.id, "generate", govde, "m", 1)
    kuyruk.ekle(db_oturumu, ikinci, "generate", govde, "m", 1)
    db_oturumu.commit()

    def _uygulama_oturumu():
        with Session(uygulama_motoru) as s:
            yield s
            s.commit()

    appmod.app.dependency_overrides[db.oturum] = _uygulama_oturumu
    with TestClient(appmod.app).stream("GET", "/api/isler/akis") as r:
        assert r.status_code == 200
        satirlar = list(r.iter_lines())
    olaylar = [json.loads(satir.split(":", 1)[1]) for satir in satirlar if satir.startswith("data:")]
    assert olaylar, "akış hiç `is` olayı yazmadı: kiracı akışın oturumlarına taşınmadı"
    assert {i["id"] for i in olaylar} == {str(a_is.id)}, satirlar


# ──────────────────────────────────────────────────────── (2) işçi ve araçlar

@pytest.fixture
def yerlesim(tmp_path) -> ayar.Ayarlar:
    return dataclasses.replace(ayar.Ayarlar.varsayilan(), data_dir=str(tmp_path),
                               output_dir=os.path.join(str(tmp_path), "output"),
                               assets_dir=os.path.join(str(tmp_path), "assets"))


def test_the_worker_takes_another_users_job_as_admin_and_writes_the_result_as_that_user(uygulama_motoru, depo_db,
                                                                                      db_oturumu, kullanici,
                                                                                      ikinci, yerlesim, tmp_path,
                                                                                      monkeypatch):
    """İşçi platformun ama iş kiracının: `al` admin (kuyruğun başı B'nin işi, bağlam A iken bile), `kos` B."""
    monkeypatch.setattr(providers, "generate", lambda *a, **k: [PNG])
    is_ = kuyruk.ekle(db_oturumu, ikinci, "generate",
                      {"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1,
                       "folder_id": None, "session_id": None}, "m", 1)
    db_oturumu.commit()
    assert kiraci.aktif().kullanici_id == kullanici.id, "fixture test kullanıcısını bağladı; işçi bunu ezmemeli"
    iz, dinleyici = _izle(uygulama_motoru)
    try:
        with Session(uygulama_motoru) as s:
            assert isci.tek_tur(s, dosya.YerelDepo(str(tmp_path)), ayarlar=yerlesim) is True
    finally:
        event.remove(uygulama_motoru, "before_cursor_execute", dinleyici)
    assert kiraci.aktif().kullanici_id == kullanici.id, "iş bitti, dış bağlam yerinde"
    with depo_db.connect() as c:
        assert c.execute(text("SELECT durum FROM isler WHERE id = :i"), {"i": is_.id}).scalar_one() == "bitti"
        assert c.execute(text("SELECT kullanici_id FROM medya")).scalars().all() == [ikinci]
    ifadeler = [(i, str(p)) for i, p in iz]
    admin_sirasi = next(n for n, (i, p) in enumerate(ifadeler) if "set_config" in i and "admin" in p)
    alim_sirasi = next(n for n, (i, _) in enumerate(ifadeler) if i.startswith("UPDATE isler"))
    b_sirasi = next(n for n, (i, p) in enumerate(ifadeler) if "set_config" in i and str(ikinci) in p)
    assert admin_sirasi < alim_sirasi < b_sirasi, "alım admin bağlamında, sonrası işin kiracısında"
    assert str(kullanici.id) not in str(iz), "test kullanıcısının id'si işçinin hiçbir ifadesine sızmadı"


def test_the_worker_heartbeat_drops_stale_jobs_of_every_tenant_as_admin(uygulama_motoru, depo_db, db_oturumu,
                                                                        ikinci):
    an = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)
    with depo_db.begin() as c:
        c.execute(text("INSERT INTO isler (kullanici_id, tur, durum, istek, model, kredi_tahmini, olusturuldu, "
                       "basladi, kalp_atisi) VALUES (:k, 'generate', 'calisiyor', '{}', 'm', 1, :t, :t, :t)"),
                  {"k": ikinci, "t": an - dt.timedelta(minutes=30)})
    with Session(uygulama_motoru) as s:
        assert isci.kalp_turu(s, uuid.uuid4(), [], an, dt.timedelta(minutes=5)).dusen == 1
    with depo_db.connect() as c:
        assert c.execute(text("SELECT durum, hata FROM isler")).one() == ("hata", kuyruk.BAYAT_HATASI)


def test_the_worker_heartbeat_refunds_the_stale_job_of_another_tenant_through_the_admin_insert_policy(
        uygulama_motoru, depo_db, db_oturumu, ikinci):
    """Faz 3 / 2 × K4: bayat düşürmenin iadesi admin bağlamında `kredi_hareketleri`ye B adına yazar —
    `yonetici_ekler` INSERT politikasının tek üretim yolu; uygulama rolüyle, süper kullanıcı değil."""
    an = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)
    defter.hibe(db_oturumu, ikinci, 100, f"{defter.ONEK_HIBE}{ikinci}:2026-09")
    is_ = kuyruk.ekle(db_oturumu, ikinci, "generate", {}, "m", 20, an=an - dt.timedelta(minutes=30))
    defter.rezerve(db_oturumu, ikinci, is_.id, 20, an=an - dt.timedelta(minutes=30))
    assert kuyruk.al(db_oturumu, uuid.uuid4(), an - dt.timedelta(minutes=30)) is not None
    db_oturumu.commit()
    assert defter.bakiye(db_oturumu, ikinci).toplam == 80
    with Session(uygulama_motoru) as s:
        assert isci.kalp_turu(s, uuid.uuid4(), [], an, dt.timedelta(minutes=5)).dusen == 1
    with depo_db.connect() as c:
        assert c.execute(text("SELECT durum FROM isler WHERE id = :i"), {"i": is_.id}).scalar_one() == "hata"
        assert c.execute(text("SELECT tur, miktar, kullanici_id, admin_id FROM kredi_hareketleri "
                              "WHERE is_id = :i ORDER BY olusturuldu"), {"i": is_.id}).all() == [
            ("rezerv", -20, ikinci, None), ("iade", 20, ikinci, None)]
        assert c.execute(text("SELECT bakiye FROM kullanicilar WHERE id = :k"), {"k": ikinci}).scalar_one() == 100


def test_every_tool_that_opens_a_session_binds_a_tenant_context():
    """Kaynak bekçisi (CLAUDE.md §5): `Session(` açan araç `kiraci.baglam(` taşır; liste dosya sisteminden türetilenle aynı."""
    acan: set[str] = set()
    for ad in sorted(os.listdir(os.path.join(REPO, "tools"))):
        if not ad.endswith(".py") or ad == "__init__.py":
            continue
        with open(os.path.join(REPO, "tools", ad), encoding="utf-8") as f:
            kaynak = f.read()
        if re.search(r"\bSession\(", kaynak):
            acan.add(ad)
            assert "kiraci.baglam(" in kaynak, f"tools/{ad} oturum açıyor ama kiracı bağlamı taşımıyor"
    assert acan == BAGLAM_TASIYAN_ARACLAR, f"listeyi güncelle: {sorted(acan)}"
