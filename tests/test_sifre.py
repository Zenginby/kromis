"""services/sifre: sağlayıcı anahtarlarının şifrelenmesi — Faz 1 / 7'nin bekçileri.

Dört soru: gidiş-dönüş (şifrele → çöz aynı metin, jeton düz metni taşımaz),
yanlış anahtar (başka kökle çözülemez, hata Türkçe ve operatöre), döndürme
(`MultiFernet`: yeni anahtar başta, eski satır okunur, yazım yeni anahtarla,
`dondur` eski satırı yeniden şifreler) ve KAPI (`KROMIS_SECRET_KEY` yoksa
ya da bozuksa `AnahtarHatasi`; DB'li uygulama AÇILMAZ, DB'siz açılır).

DB'de düz metin YOK ölçümü de burada: `depo_kimlik_bilgisi.yaz` sonrası ham
`SELECT` — `pg_dump`ın göreceği şey — anahtarı içermiyor (Postgres GERÇEK).
"""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app as appmod
from services import depo_kimlik_bilgisi, sifre
from tests.conftest import TEST_ESKI_KOK_ANAHTARI, TEST_KOK_ANAHTARI, sifre_anahtari

GIZLI = "sk-proj-DUMMY-cok-gizli-anahtar-1234567890"


def test_encrypt_decrypt_round_trips_and_the_token_carries_no_plaintext():
    s = sifre.Sifreci([TEST_KOK_ANAHTARI])
    jeton = s.sifrele(GIZLI)
    assert isinstance(jeton, bytes) and jeton.startswith(b"gAAAA"), "Fernet jetonu"
    assert GIZLI.encode() not in jeton and b"DUMMY" not in jeton
    assert s.coz(jeton) == GIZLI
    # Türkçe karakter ve boş dize de gidip geliyor.
    assert s.coz(s.sifrele("kéy-şĞ")) == "kéy-şĞ"
    assert s.coz(s.sifrele("")) == ""
    # Her şifreleme farklı jeton (Fernet IV): aynı anahtar iki kullanıcıda aynı görünmez.
    assert s.sifrele(GIZLI) != jeton


def test_a_different_root_key_cannot_decrypt_and_says_so_in_turkish():
    jeton = sifre.Sifreci([TEST_KOK_ANAHTARI]).sifrele(GIZLI)
    baska = sifre.Sifreci([TEST_ESKI_KOK_ANAHTARI])
    with pytest.raises(sifre.SifreHatasi) as e:
        baska.coz(jeton)
    assert sifre.ANAHTAR_ENV in str(e.value) and "cozulemedi" in str(e.value)
    assert GIZLI not in str(e.value)
    with pytest.raises(sifre.SifreHatasi):
        baska.dondur(jeton)


def test_the_fernet_key_is_derived_with_hkdf_not_the_root_key_itself():
    """Kök anahtar Fernet'e DOĞRUDAN verilmiyor: "kimlik" amaçlı alt anahtar."""
    from cryptography.fernet import Fernet, InvalidToken
    jeton = sifre.Sifreci([TEST_KOK_ANAHTARI]).sifrele(GIZLI)
    dogrudan = Fernet(base64.urlsafe_b64encode(TEST_KOK_ANAHTARI))
    with pytest.raises(InvalidToken):
        dogrudan.decrypt(jeton)
    assert Fernet(sifre._turet(TEST_KOK_ANAHTARI)).decrypt(jeton) == GIZLI.encode()
    assert sifre._turet(TEST_KOK_ANAHTARI) != sifre._turet(TEST_ESKI_KOK_ANAHTARI)


def test_rotation_reads_rows_written_with_an_older_key_and_writes_with_the_newest():
    """Liste "yeni,eski": eski jeton okunur, yeni yazım ilk anahtarla, sürüm parmak izi."""
    eski = sifre.Sifreci([TEST_ESKI_KOK_ANAHTARI])
    eski_jeton = eski.sifrele(GIZLI)

    donen = sifre.Sifreci([TEST_KOK_ANAHTARI, TEST_ESKI_KOK_ANAHTARI])
    assert donen.coz(eski_jeton) == GIZLI
    assert donen.surum == sifre.parmak_izi(TEST_KOK_ANAHTARI)
    assert donen.surumler == [sifre.parmak_izi(TEST_KOK_ANAHTARI), sifre.parmak_izi(TEST_ESKI_KOK_ANAHTARI)]
    assert donen.guncel_mi(eski.surum) is False and donen.guncel_mi(donen.surum) is True

    yeni_jeton = donen.dondur(eski_jeton)
    assert yeni_jeton != eski_jeton
    # Yeni jeton yalnız yeni anahtarla okunur: eski anahtar listeden düşebilir.
    assert sifre.Sifreci([TEST_KOK_ANAHTARI]).coz(yeni_jeton) == GIZLI
    with pytest.raises(sifre.SifreHatasi):
        eski.coz(yeni_jeton)
    # Yazım da hep ilk anahtarla.
    assert sifre.Sifreci([TEST_KOK_ANAHTARI]).coz(donen.sifrele(GIZLI)) == GIZLI


def test_the_version_column_is_a_fingerprint_of_the_root_key_not_a_list_position():
    """Liste değişince sıra kayar, parmak izi kaymaz; 31 bit `integer`a sığar, kökü ele vermez."""
    p = sifre.parmak_izi(TEST_KOK_ANAHTARI)
    assert 0 <= p < 2 ** 31
    assert sifre.Sifreci([TEST_KOK_ANAHTARI]).surum == p
    assert sifre.Sifreci([TEST_ESKI_KOK_ANAHTARI, TEST_KOK_ANAHTARI]).surumler[1] == p
    assert p != sifre.parmak_izi(TEST_ESKI_KOK_ANAHTARI)


# ── Ortamdan okuma ve kapı ─────────────────────────────────────────────


def test_the_environment_variable_is_parsed_as_a_comma_list_newest_first(monkeypatch):
    monkeypatch.setenv(sifre.ANAHTAR_ENV,
                       " " + sifre_anahtari(TEST_KOK_ANAHTARI, TEST_ESKI_KOK_ANAHTARI).replace(",", " , ") + " ")
    s = sifre.sifreci()
    assert s.surumler == [sifre.parmak_izi(TEST_KOK_ANAHTARI), sifre.parmak_izi(TEST_ESKI_KOK_ANAHTARI)]
    # Aynı değer → aynı nesne (türetme bir kez); farklı değer → yeni nesne.
    assert sifre.sifreci() is s
    monkeypatch.setenv(sifre.ANAHTAR_ENV, sifre_anahtari(TEST_KOK_ANAHTARI))
    assert sifre.sifreci() is not s
    # Dolgusuz base64 de kabul (bazı üreteçler `=` düşürüyor).
    ham = sifre_anahtari(TEST_KOK_ANAHTARI).rstrip("=")
    assert sifre.kok_anahtarlar(ham) == [TEST_KOK_ANAHTARI]


@pytest.mark.parametrize("deger, parca", [
    ("", "verilmedi"),
    ("   ", "verilmedi"),
    (sifre_anahtari(TEST_KOK_ANAHTARI) + ",", "verilmedi"),      # boş öğe
    ("kisa", "bayt"),                                              # 3 bayt
    (base64.urlsafe_b64encode(b"x" * 31).decode(), "31 bayt"),
    ("!!!bu base64 degil!!!", "gecersiz"),
])
def test_a_missing_or_malformed_key_is_refused_with_the_generation_command(monkeypatch, deger, parca):
    """Sessiz varsayılan YOK: hata adı, sebebi ve üretim komutunu söyler."""
    monkeypatch.setenv(sifre.ANAHTAR_ENV, deger)
    with pytest.raises(sifre.AnahtarHatasi) as e:
        sifre.dogrula_ortam()
    mesaj = str(e.value)
    assert sifre.ANAHTAR_ENV in mesaj and parca in mesaj
    assert "secrets.token_bytes(32)" in mesaj, "operatör anahtarı nasıl üreteceğini okumalı"
    monkeypatch.delenv(sifre.ANAHTAR_ENV)
    with pytest.raises(sifre.AnahtarHatasi):
        sifre.sifreci()


def test_the_app_refuses_to_start_without_the_key_when_a_database_is_configured(
        veritabani, tmp_path, dizinler, monkeypatch):
    """Belge §7: `KROMIS_SECRET_KEY` yoksa uygulama AÇILMAZ — guard yok, hata `hata.log`da ve yükselir."""
    dizinler(data_dir=str(tmp_path))
    monkeypatch.delenv(sifre.ANAHTAR_ENV)
    with pytest.raises(sifre.AnahtarHatasi) as e:
        with TestClient(appmod.app):
            pass
    assert "ACILMAZ" in str(e.value)
    gunluk = (tmp_path / "hata.log").read_text(encoding="utf-8")
    assert "AnahtarHatasi" in gunluk and sifre.ANAHTAR_ENV in gunluk
    assert appmod.app.state.motor is None, "açılmayan uygulama motor bırakmadı"

    # Anahtar verilince aynı süreç açılır.
    monkeypatch.setenv(sifre.ANAHTAR_ENV, sifre_anahtari(TEST_KOK_ANAHTARI))
    with TestClient(appmod.app) as c:
        assert c.get("/health").status_code == 200


def test_without_a_database_the_key_is_not_required(tmp_path, dizinler, monkeypatch):
    """DB'siz süreç (dondurulmuş kabuk, `/health` sondası): okunacak kimlik satırı yok, kapı yok."""
    dizinler(data_dir=str(tmp_path))
    monkeypatch.delenv(sifre.ANAHTAR_ENV)
    with TestClient(appmod.app) as c:
        assert c.get("/health").status_code == 503     # db_reachable:false, anahtardan değil
        assert c.get("/health").json()["db_reachable"] is False


# ── DB'de düz metin YOK ────────────────────────────────────────────────


@pytest.mark.usefixtures("depo_db")
def test_the_raw_row_holds_ciphertext_only(db_oturumu, kullanici):
    """`pg_dump`ın göreceği ham satır: `sk-` yok, değer yok; sürüm parmak izi, `ad` düz."""
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {"OPENAI_API_KEY": GIZLI,
                                                       "AZURE_IMAGE_API_KEY": "AZURE-DUMMY-KEY-XYZ"})
    db_oturumu.commit()
    satirlar = db_oturumu.execute(text(
        "SELECT ad, sifreli_deger, anahtar_surumu FROM saglayici_kimlikleri "
        "WHERE kullanici_id = :k ORDER BY ad"), {"k": kullanici.id}).all()
    assert [r.ad for r in satirlar] == ["AZURE_IMAGE_API_KEY", "OPENAI_API_KEY"]
    dokum = b"".join(bytes(r.sifreli_deger) for r in satirlar)
    for gizli in (GIZLI, "AZURE-DUMMY-KEY-XYZ", "sk-", "DUMMY"):
        assert gizli.encode() not in dokum, gizli
    assert all(bytes(r.sifreli_deger).startswith(b"gAAAA") for r in satirlar)
    assert {r.anahtar_surumu for r in satirlar} == {sifre.parmak_izi(TEST_KOK_ANAHTARI)}
    # Ve çözülünce aynı değer.
    assert depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id)["OPENAI_API_KEY"] == GIZLI
