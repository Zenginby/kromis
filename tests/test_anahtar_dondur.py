"""`tools/anahtar_dondur.py` — `KROMIS_SECRET_KEY` döndürmenin TOPLU sarmalayıcısı (Faz 1 / 9).

GERÇEK Postgres (`depo_db`). Kurgu 7. görevin akışı: satırlar ESKİ anahtarla
yazılır, ortam `"yeni,eski"` olur, araç bütün kullanıcıların satırlarını yeni
anahtara taşır; sonra eski anahtar düşürülebilir. Düz metin bu süreçte açılmaz
— iddia satırın çözülen değerinin AYNI kalması ve parmak izinin değişmesi.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

from services import db, depo_kimlik_bilgisi, hesap, sifre
from services.tablolar import SaglayiciKimligi
from tests.conftest import TEST_ESKI_KOK_ANAHTARI, TEST_KOK_ANAHTARI, sifre_anahtari
from tools import anahtar_dondur

pytestmark = pytest.mark.usefixtures("depo_db")

ESKI = sifre_anahtari(TEST_ESKI_KOK_ANAHTARI)
YENI = sifre_anahtari(TEST_KOK_ANAHTARI)
IKISI = sifre_anahtari(TEST_KOK_ANAHTARI, TEST_ESKI_KOK_ANAHTARI)     # yeni başta

A_DEGERLER = {"AZURE_IMAGE_API_KEY": "DUMMY-a-azure", "GEMINI_API_KEY": "DUMMY-a-gemini"}
B_DEGERLER = {"OPENAI_API_KEY": "DUMMY-b-openai"}


@pytest.fixture
def eski_anahtarla_yazilmis(db_oturumu, kullanici, monkeypatch):
    """İki kullanıcı, üç satır, hepsi ESKİ anahtarla; döner: (a_id, b_id)."""
    monkeypatch.setenv(sifre.ANAHTAR_ENV, ESKI)
    # Dosyanın DB'si testler arasında paylaşılıyor ve fixture COMMIT ediyor: önceki
    # testin döndürülmüş satırları temizlenir, e-posta benzersiz.
    db_oturumu.execute(delete(SaglayiciKimligi))
    b = hesap.kullanici_olustur(db_oturumu, f"b-{uuid.uuid4().hex[:8]}@example.com", "cok-gizli-parola-b", None)
    db_oturumu.flush()
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, A_DEGERLER)
    depo_kimlik_bilgisi.yaz(db_oturumu, b.id, B_DEGERLER)
    db_oturumu.commit()
    eski_iz = sifre.parmak_izi(TEST_ESKI_KOK_ANAHTARI)
    assert {s.anahtar_surumu for s in db_oturumu.scalars(select(SaglayiciKimligi))} == {eski_iz}
    return kullanici.id, b.id


def _satirlar(oturum) -> dict[tuple, tuple[int, bytes]]:
    oturum.expire_all()
    return {(s.kullanici_id, s.ad): (s.anahtar_surumu, s.sifreli_deger)
            for s in oturum.scalars(select(SaglayiciKimligi))}


def test_the_dry_run_counts_the_rows_per_user_and_writes_nothing(eski_anahtarla_yazilmis, db_oturumu,
                                                                  monkeypatch, capsys):
    a, b = eski_anahtarla_yazilmis
    once = _satirlar(db_oturumu)
    monkeypatch.setenv(sifre.ANAHTAR_ENV, IKISI)
    assert anahtar_dondur.main(["--kuru"]) == anahtar_dondur.CIKIS_TAMAM
    out = capsys.readouterr().out
    assert f"{a}: 2 satir dondurulecek" in out and f"{b}: 1 satir dondurulecek" in out
    assert "toplam: 3 satir, 2 kullanici (kuru kosu, yazilmadi)" in out
    assert _satirlar(db_oturumu) == once


def test_the_real_run_rotates_every_user_to_the_newest_key_and_values_survive(
        eski_anahtarla_yazilmis, db_oturumu, monkeypatch, capsys):
    """ASIL İDDİA: bütün satırlar yeni anahtarın parmak izinde, çözülen değerler aynı;
    ikinci koşu 0 satır; yalnız yeni anahtarla (eski düşürülmüş) okuma çalışıyor."""
    a, b = eski_anahtarla_yazilmis
    monkeypatch.setenv(sifre.ANAHTAR_ENV, IKISI)
    assert anahtar_dondur.main([]) == anahtar_dondur.CIKIS_TAMAM
    out, err = capsys.readouterr()
    assert f"{a}: 2 satir donduruldu" in out and "toplam: 3 satir, 2 kullanici" in out
    assert "ESKI anahtar" not in out and "DUSURMEYIN" not in err
    yeni_iz = sifre.parmak_izi(TEST_KOK_ANAHTARI)
    sonra = _satirlar(db_oturumu)
    assert {surum for surum, _ in sonra.values()} == {yeni_iz}
    assert f"parmak izi {yeni_iz}: 3 satir (guncel)" in out

    assert anahtar_dondur.main([]) == anahtar_dondur.CIKIS_TAMAM
    assert "toplam: 0 satir, 0 kullanici" in capsys.readouterr().out

    # 4. adım: eski anahtar listeden düşer, değerler yine okunur.
    monkeypatch.setenv(sifre.ANAHTAR_ENV, YENI)
    assert depo_kimlik_bilgisi.oku(db_oturumu, a) == A_DEGERLER
    assert depo_kimlik_bilgisi.oku(db_oturumu, b) == B_DEGERLER


def test_dropping_the_old_key_too_early_exits_1_and_writes_nothing(eski_anahtarla_yazilmis, db_oturumu,
                                                                     monkeypatch, capsys):
    """Eski anahtar listede değilse satırlar çözülemez: araç bunu söyler, hiçbir şey yazmaz."""
    once = _satirlar(db_oturumu)
    monkeypatch.setenv(sifre.ANAHTAR_ENV, YENI)
    assert anahtar_dondur.main([]) == anahtar_dondur.CIKIS_KULLANICI
    err = capsys.readouterr().err
    assert "cozulemedi" in err and "Hicbir sey yazilmadi" in err
    assert _satirlar(db_oturumu) == once


def test_environment_errors_exit_2(monkeypatch, capsys):
    monkeypatch.delenv(db.DATABASE_URL_ENV, raising=False)
    assert anahtar_dondur.main([]) == anahtar_dondur.CIKIS_ORTAM
    assert db.DATABASE_URL_ENV in capsys.readouterr().err


def test_a_missing_secret_key_exits_2_with_the_generation_command(depo_db, monkeypatch, capsys):
    monkeypatch.delenv(sifre.ANAHTAR_ENV, raising=False)
    assert anahtar_dondur.main([]) == anahtar_dondur.CIKIS_ORTAM
    assert sifre.URETIM_KOMUTU in capsys.readouterr().err
