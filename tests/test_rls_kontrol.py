"""`tools/rls_kontrol.py` + `tools/uygulama_rolu.py` — canlı rolün RLS'i atlayıp atlamadığını ölçen çift (Faz 2 / 7).

NEDEN VAR: bu iki araç, takımın ÖLÇEMEDİĞİ tek şeyi ölçmek için yazıldı —
canlıdaki `DATABASE_URL` rolünün kim olduğunu. Kendileri ölçüsüz kalırsa sessiz
bir "yeşil" üretebilirler ve bu, RLS'in kapalı olduğu bir dağıtımı "doğrulanmış"
sanmaktan daha kötüdür. Buradaki testler ikisini de GERÇEK Postgres'te, gerçek
bir ikinci rolle koşturuyor: süper kullanıcı kırmızı, açılan uygulama rolü
yeşil, tohumsuz yeşil ise ZAYIF damgalı.

Üç kusuru özellikle kapıda tutuyor:

1. **Boş tablo tuzağı** — "bağlamsız `count(*)` → 0" taze bir DB'de kendiliğinden
   yeşildir. 2026-09-18'de Railway'in boş DB'sinde tam olarak buna düşüldü;
   `test_a_green_result_without_a_seeded_row_is_marked_weak` o dersin bekçisi.
2. **Liste kopyası** — tablo listesi `services/kiraci.py`den gelmeli, araçta
   ikinci bir literal olmamalı (CLAUDE.md §5: elle tutulan her kapsam listesi
   ayrışır).
3. **Parola kaçırma** — `CREATE ROLE` parametre almıyor, parola dizeye
   gömülüyor; tek tırnaklı bir parola ya sözdizimi hatası ya da daha kötüsü
   olurdu.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from services import kiraci
from tools import rls_kontrol, uygulama_rolu

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAROLA = "gizli-prova-parolasi"


@pytest.fixture(autouse=True)
def temiz(depo_db):
    """Her test boş `medya` ile başlar: tohum kapısının iddiaları sıraya bağlı olmasın."""
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM medya"))
        c.execute(text("DELETE FROM klasorler"))
        c.execute(text("DELETE FROM kullanicilar WHERE eposta LIKE 'rls-prova-%'"))
    yield


@pytest.fixture
def rol_adi(depo_db):
    """Küme genelinde benzersiz bir rol adı; test bitince yetkileriyle birlikte düşer.

    `ALTER DEFAULT PRIVILEGES … REVOKE` şart: verilen öntanımlı yetki role
    bağımlılık sayılır ve `DROP ROLE` onsuz "cannot be dropped" der (ölçüldü).
    """
    ad = f"kromis_kontrol_t_{os.urandom(3).hex()}"
    yield ad
    with depo_db.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        for deyim in (f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {ad}",
                      f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {ad}",
                      f"REVOKE ALL ON SCHEMA public FROM {ad}",
                      f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {ad}",
                      f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {ad}",
                      f"DROP ROLE IF EXISTS {ad}"):
            try:
                c.execute(text(deyim))
            except Exception:  # noqa: BLE001 — temizlik testi düşürmemeli
                pass


def _rol_urlsi(url: str, ad: str) -> str:
    return make_url(url).set(username=ad, password=PAROLA).render_as_string(hide_password=False)


def _rolu_ac(monkeypatch, url: str, ad: str, *args: str) -> int:
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv(uygulama_rolu.PAROLA_ENV, PAROLA)
    return uygulama_rolu.main(["--ad", ad, *args])


# ─────────────────────────────────────────────── rls_kontrol: ortam ve argüman

def test_the_check_says_which_variable_is_missing_instead_of_crashing(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert rls_kontrol.main([]) == rls_kontrol.CIKIS_ORTAM
    assert "DATABASE_URL" in capsys.readouterr().err


def test_the_check_refuses_a_user_argument_that_is_not_a_uuid(monkeypatch, veritabani_url, capsys):
    """Politika `::uuid`e çeviriyor: çöp değer DB'de dönüşüm hatası olurdu, kapıda argüman hatası olsun."""
    monkeypatch.setenv("DATABASE_URL", veritabani_url)
    assert rls_kontrol.main(["--kullanici", "BURAYA_UUID"]) == rls_kontrol.CIKIS_ORTAM
    assert "uuid degil" in capsys.readouterr().err


# ─────────────────────────────────────────────────────── rls_kontrol: ölçümler

def test_under_the_superuser_the_check_is_red_because_force_does_not_cover_it(
        monkeypatch, veritabani_url, capsys):
    """Takımın kendi rolü süper kullanıcı: araç bunu KIRMIZI saymalı, yoksa canlıda da saymaz."""
    monkeypatch.setenv("DATABASE_URL", veritabani_url)
    assert rls_kontrol.main([]) == rls_kontrol.CIKIS_KIRMIZI
    cikti = capsys.readouterr().out
    assert "[RED] rolsuper: t" in cikti
    # Şema kapıları yine yeşil: göç koştu, kırmızı olan yalnız ROL.
    assert f"[OK ] politika: {rls_kontrol.POLITIKA_SAYISI * len(kiraci.IS_TABLOLARI)}" in cikti


def test_the_application_role_it_opens_turns_every_gate_green(
        monkeypatch, veritabani_url, depo_db, rol_adi, capsys):
    """Uçtan uca: rolü aç, tohumla, o rolle ölç — canlıda yürünecek yolun aynısı."""
    assert _rolu_ac(monkeypatch, veritabani_url, rol_adi, "--tohum") == uygulama_rolu.CIKIS_TAMAM
    capsys.readouterr()
    with depo_db.connect() as c:
        kullanici_id = c.execute(text("SELECT kullanici_id FROM medya")).scalar_one()

    monkeypatch.setenv("DATABASE_URL", _rol_urlsi(veritabani_url, rol_adi))
    assert rls_kontrol.main(["--kullanici", str(kullanici_id)]) == rls_kontrol.CIKIS_TAMAM
    cikti = capsys.readouterr().out
    assert "[OK ] rolsuper: f" in cikti and "[OK ] rolbypassrls: f" in cikti
    assert "[OK ] baglamsiz medya: 0 satir" in cikti
    assert "baglamli medya: 1 satir" in cikti
    assert "ZAYIF" not in cikti


def test_a_green_result_without_a_seeded_row_is_marked_weak(
        monkeypatch, veritabani_url, rol_adi, capsys):
    """2026-09-18 dersi: boş tabloda "bağlamsız 0" kendiliğinden yeşildir ve hiçbir şey kanıtlamaz."""
    assert _rolu_ac(monkeypatch, veritabani_url, rol_adi) == uygulama_rolu.CIKIS_TAMAM
    capsys.readouterr()
    monkeypatch.setenv("DATABASE_URL", _rol_urlsi(veritabani_url, rol_adi))
    assert rls_kontrol.main([]) == rls_kontrol.CIKIS_TAMAM
    assert "ZAYIF" in capsys.readouterr().out


def test_the_table_list_comes_from_kiraci_and_is_not_copied_into_the_tool():
    """CLAUDE.md §5: iki liste ayrışır. Göçün kapsamı tek yerde (`kiraci.IS_TABLOLARI`)."""
    with open(os.path.join(REPO, "tools", "rls_kontrol.py"), encoding="utf-8") as f:
        kaynak = f.read()
    assert "kiraci.IS_TABLOLARI" in kaynak
    # `medya` muaf: sayımın öntanımlı tablosu, liste değil. Ötekilerden biri
    # geçiyorsa listenin kopyası çıkarılmış demektir.
    for tablo in kiraci.IS_TABLOLARI:
        if tablo != "medya":
            assert tablo not in kaynak, f"{tablo} literali araca kopyalanmis"


# ────────────────────────────────────────────────────────── uygulama_rolu

def test_a_dry_run_prints_the_ddl_and_opens_nothing(monkeypatch, depo_db, rol_adi, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert uygulama_rolu.main(["--ad", rol_adi, "--kuru"]) == uygulama_rolu.CIKIS_TAMAM
    cikti = capsys.readouterr().out
    assert f"CREATE ROLE {rol_adi} LOGIN PASSWORD <PAROLA>" in cikti
    assert "ALTER DEFAULT PRIVILEGES" in cikti  # sonraki göçlerin tabloları da açılsın
    with depo_db.connect() as c:
        assert c.execute(text("SELECT count(*) FROM pg_roles WHERE rolname = :a"),
                         {"a": rol_adi}).scalar_one() == 0


def test_the_role_name_is_checked_before_it_reaches_sql(monkeypatch, capsys):
    """Ad tanımlayıcı olarak dizeye giriyor (bağlanamaz): kabul kümesi dar olmalı."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert uygulama_rolu.main(["--ad", 'kotu"; DROP TABLE medya; --']) == uygulama_rolu.CIKIS_ORTAM
    assert "--ad" in capsys.readouterr().err


def test_a_password_holding_a_quote_survives_the_literal(
        monkeypatch, veritabani_url, depo_db, rol_adi):
    """`CREATE ROLE` parametre almıyor; tek tırnak ikilenmezse rol ya açılmaz ya da yanlış açılır."""
    assert uygulama_rolu.parola_sql("a'b") == "'a''b'"
    tirnakli = "on'iki'uc"
    monkeypatch.setenv("DATABASE_URL", veritabani_url)
    monkeypatch.setenv(uygulama_rolu.PAROLA_ENV, tirnakli)
    assert uygulama_rolu.main(["--ad", rol_adi]) == uygulama_rolu.CIKIS_TAMAM
    with depo_db.connect() as c:
        assert c.execute(text("SELECT rolcanlogin FROM pg_roles WHERE rolname = :a"),
                         {"a": rol_adi}).scalar_one() is True
    # Asıl kanıt sunucunun kendi doğrulaması: o parolayla GERÇEKTEN giriliyor mu.
    motor = create_engine(make_url(veritabani_url).set(username=rol_adi, password=tirnakli)
                          .render_as_string(hide_password=False))
    try:
        with motor.connect() as c:
            assert c.execute(text("SELECT current_user")).scalar_one() == rol_adi
    finally:
        motor.dispose()


def test_the_seed_keeps_its_hands_off_a_table_that_already_has_rows(
        monkeypatch, veritabani_url, depo_db, rol_adi, capsys):
    """Canlıda gerçek veri vardır: araç oraya uydurma satır YAZMAMALI."""
    assert _rolu_ac(monkeypatch, veritabani_url, rol_adi, "--tohum") == uygulama_rolu.CIKIS_TAMAM
    assert "1 hesap + 1 klasor + 1 medya yazildi" in capsys.readouterr().out
    assert _rolu_ac(monkeypatch, veritabani_url, rol_adi, "--tohum") == uygulama_rolu.CIKIS_TAMAM
    assert "gerekmedi (medya dolu)" in capsys.readouterr().out
    with depo_db.connect() as c:
        assert c.execute(text("SELECT count(*) FROM medya")).scalar_one() == 1


def test_the_seeded_rows_carry_the_tenant_of_the_account_they_belong_to(
        monkeypatch, veritabani_url, depo_db, rol_adi):
    """Tohum admin bağlamıyla değil hesabın kendi bağlamıyla yazılır (admin politikası INSERT vermiyor)."""
    assert _rolu_ac(monkeypatch, veritabani_url, rol_adi, "--tohum") == uygulama_rolu.CIKIS_TAMAM
    with depo_db.connect() as c:
        medya_sahibi = c.execute(text("SELECT kullanici_id FROM medya")).scalar_one()
        klasor_sahibi = c.execute(text("SELECT kullanici_id FROM klasorler")).scalar_one()
        eposta = c.execute(text("SELECT eposta FROM kullanicilar WHERE id = :k"),
                           {"k": medya_sahibi}).scalar_one()
    assert isinstance(medya_sahibi, uuid.UUID) and medya_sahibi == klasor_sahibi
    assert eposta.startswith("rls-prova-")
