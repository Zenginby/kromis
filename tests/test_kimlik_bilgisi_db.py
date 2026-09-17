"""Sağlayıcı kimlikleri DB'de — Faz 1 / 7'nin depo bekçileri (docs/faz1-veritabani-hesaplar.md §7).

`services/depo_kimlik_bilgisi.py`: `oku` = `read_env_values` (düz sözlük),
`yaz` = `save_env` (verilenleri yaz, ötekilere dokunma; boş = sil), `sil`,
`dondur` (anahtar döndürme). İki kullanıcı depo düzeyinde izole; ad envanteri
katalog + eski BYOK ile bir; `configured_map` sözlüğü boolean'a çevirir.
Postgres GERÇEK (`depo_db`). Şifreleme bekçileri tests/test_sifre.py'de.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

import catalog
import credstore
from services import depo_kimlik_bilgisi, hesap, sifre, tablolar, zaman
from tests.conftest import TEST_ESKI_KOK_ANAHTARI, TEST_KOK_ANAHTARI, sifre_anahtari

pytestmark = pytest.mark.usefixtures("depo_db")

AZURE = {"AZURE_IMAGE_API_KEY": "A-DUMMY-KEY", "AZURE_IMAGE_BASE_URL": "https://a/openai/v1/"}


def _ikinci_kullanici(db) -> uuid.UUID:
    k = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                           dogrulandi_at=hesap.simdi())
    db.add(k)
    db.flush()
    return k.id


def _satirlar(db, kullanici_id):
    return list(db.scalars(select(tablolar.SaglayiciKimligi)
                           .where(tablolar.SaglayiciKimligi.kullanici_id == kullanici_id)
                           .order_by(tablolar.SaglayiciKimligi.ad)))


def test_a_fresh_user_has_an_empty_mapping_and_nothing_configured(db_oturumu, kullanici):
    assert depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id) == {}
    assert credstore.configured_map(depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id)) == {
        c.id: False for c in catalog.CREDENTIALS}
    # Boş yazım satır açmaz (`save_env`in "dosyaya dokunma" kuralı).
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {})
    assert _satirlar(db_oturumu, kullanici.id) == []


def test_write_read_round_trips_and_configured_map_turns_it_into_booleans(db_oturumu, kullanici):
    an = zaman.an()
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {**AZURE, "GEMINI_API_KEY": "AIza-DUMMY"}, now=an)
    okunan = depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id)
    assert okunan == {**AZURE, "GEMINI_API_KEY": "AIza-DUMMY"}
    harita = credstore.configured_map(okunan)
    assert harita["azure_image"] is True and harita["gemini"] is True
    assert harita["openai"] is False and harita["anthropic"] is False
    assert all(isinstance(v, bool) for v in harita.values())
    satirlar = _satirlar(db_oturumu, kullanici.id)
    assert [s.ad for s in satirlar] == ["AZURE_IMAGE_API_KEY", "AZURE_IMAGE_BASE_URL", "GEMINI_API_KEY"]
    assert all(s.olusturuldu == an and s.guncellendi == an for s in satirlar)
    assert all(s.anahtar_surumu == sifre.parmak_izi(TEST_KOK_ANAHTARI) for s in satirlar)


def test_overwriting_one_name_leaves_the_others_and_moves_only_its_timestamp(db_oturumu, kullanici):
    """`save_env`: OKU → BİRLEŞTİR → yaz — dokunulmayan ad dokunulmamış kalır."""
    ilk = zaman.an()
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {**AZURE, "AZURE_CHAT_DEPLOYMENT": "d1"}, now=ilk)
    sonra = zaman.an()
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {"AZURE_CHAT_DEPLOYMENT": "d2"}, now=sonra)
    assert depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id) == {**AZURE, "AZURE_CHAT_DEPLOYMENT": "d2"}
    satirlar = {s.ad: s for s in _satirlar(db_oturumu, kullanici.id)}
    assert satirlar["AZURE_CHAT_DEPLOYMENT"].guncellendi == sonra
    assert satirlar["AZURE_CHAT_DEPLOYMENT"].olusturuldu == ilk, "ezme yeni satır açmaz"
    assert satirlar["AZURE_IMAGE_API_KEY"].guncellendi == ilk, "dokunulmayan ad dokunulmadı"


def test_an_empty_value_deletes_the_row_which_reads_as_not_configured(db_oturumu, kullanici):
    """`save_env`de `AD=` kalırdı ve okuma boş dizeyi yapılandırılmamış sayardı; burada satır gider."""
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {**AZURE, "AZURE_CHAT_DEPLOYMENT": "d"})
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {"AZURE_CHAT_DEPLOYMENT": ""})
    okunan = depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id)
    assert "AZURE_CHAT_DEPLOYMENT" not in okunan and okunan == AZURE
    assert credstore.settings_status(okunan)["chat_deployment"] == ""
    # Olmayan adı boşla silmek de sessizce geçer; `sil` var/yok'u söyler.
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {"OPENAI_API_KEY": ""})
    assert depo_kimlik_bilgisi.sil(db_oturumu, kullanici.id, "AZURE_IMAGE_API_KEY") is True
    assert depo_kimlik_bilgisi.sil(db_oturumu, kullanici.id, "AZURE_IMAGE_API_KEY") is False
    assert credstore.configured_map(depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id))["azure_image"] is False


def test_two_users_never_see_each_others_credentials_at_the_repository_layer(db_oturumu, kullanici):
    a, b = kullanici.id, _ikinci_kullanici(db_oturumu)
    depo_kimlik_bilgisi.yaz(db_oturumu, a, AZURE)
    depo_kimlik_bilgisi.yaz(db_oturumu, b, {"AZURE_IMAGE_API_KEY": "B-DUMMY-KEY",
                                            "AZURE_IMAGE_BASE_URL": "https://b/openai/v1/"})
    assert depo_kimlik_bilgisi.oku(db_oturumu, a) == AZURE
    assert depo_kimlik_bilgisi.oku(db_oturumu, b)["AZURE_IMAGE_API_KEY"] == "B-DUMMY-KEY"
    # B'nin silmesi/ezmesi A'ya dokunmaz.
    assert depo_kimlik_bilgisi.sil(db_oturumu, b, "AZURE_IMAGE_API_KEY") is True
    depo_kimlik_bilgisi.yaz(db_oturumu, b, {"AZURE_IMAGE_BASE_URL": ""})
    assert depo_kimlik_bilgisi.oku(db_oturumu, b) == {}
    assert depo_kimlik_bilgisi.oku(db_oturumu, a) == AZURE
    assert depo_kimlik_bilgisi.dondur(db_oturumu, b) == 0
    # Hesap silinince satırlar CASCADE ile gider.
    db_oturumu.execute(tablolar.Kullanici.__table__.delete().where(tablolar.Kullanici.id == b))
    assert _satirlar(db_oturumu, b) == []


def test_unknown_names_are_a_programming_error_and_the_inventory_matches_the_catalog(db_oturumu, kullanici):
    """Ad envanteri = katalog (`key_env`/`url_env`/`wire_from_env`, `.env.example`in kümesi) + eski BYOK."""
    with pytest.raises(ValueError):
        depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {"KROMIS_SECRET_KEY": "x"})
    with pytest.raises(ValueError):
        depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {"openai_api_key": "x"})
    katalog = {c.key_env for c in catalog.CREDENTIALS}
    katalog |= {c.url_env for c in catalog.CREDENTIALS if c.url_env}
    katalog |= {m.wire_from_env for m in catalog.CHAT_MODELS if m.wire_from_env}
    assert depo_kimlik_bilgisi.ADLAR == katalog | set(depo_kimlik_bilgisi.ESKI_BYOK)
    assert set(depo_kimlik_bilgisi.ESKI_BYOK) == {"REPLICATE_API_TOKEN", "COMFYUI_URL", "OLLAMA_URL"}
    assert not set(depo_kimlik_bilgisi.ESKI_BYOK) & katalog, "kataloğa giren ad eski listeden çıkar"
    # Envanterdeki her ad yazılabilir.
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {ad: "x" for ad in depo_kimlik_bilgisi.ADLAR})
    assert set(depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id)) == depo_kimlik_bilgisi.ADLAR


def test_rotation_re_encrypts_stale_rows_and_leaves_fresh_ones_alone(db_oturumu, kullanici, monkeypatch):
    """Operatörün yolu: eski anahtarla yazılmış satır → liste "yeni,eski" → `dondur` → eski düşer."""
    monkeypatch.setenv(sifre.ANAHTAR_ENV, sifre_anahtari(TEST_ESKI_KOK_ANAHTARI))
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, AZURE)
    eski_surum = sifre.parmak_izi(TEST_ESKI_KOK_ANAHTARI)
    assert {s.anahtar_surumu for s in _satirlar(db_oturumu, kullanici.id)} == {eski_surum}

    # Yalnız yeni anahtar: eski satır OKUNAMAZ, sessizce boş dönmez.
    monkeypatch.setenv(sifre.ANAHTAR_ENV, sifre_anahtari(TEST_KOK_ANAHTARI))
    with pytest.raises(sifre.SifreHatasi):
        depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id)

    # "yeni,eski": okunur; yeni yazım yeni anahtarla; eski satırlar eski sürümde kalır.
    monkeypatch.setenv(sifre.ANAHTAR_ENV, sifre_anahtari(TEST_KOK_ANAHTARI, TEST_ESKI_KOK_ANAHTARI))
    assert depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id) == AZURE
    depo_kimlik_bilgisi.yaz(db_oturumu, kullanici.id, {"GEMINI_API_KEY": "AIza-DUMMY"})
    surumler = {s.ad: s.anahtar_surumu for s in _satirlar(db_oturumu, kullanici.id)}
    yeni_surum = sifre.parmak_izi(TEST_KOK_ANAHTARI)
    assert surumler["GEMINI_API_KEY"] == yeni_surum
    assert surumler["AZURE_IMAGE_API_KEY"] == eski_surum

    guncellendi_once = {s.ad: s.guncellendi for s in _satirlar(db_oturumu, kullanici.id)}
    assert depo_kimlik_bilgisi.dondur(db_oturumu, kullanici.id) == 2
    assert {s.anahtar_surumu for s in _satirlar(db_oturumu, kullanici.id)} == {yeni_surum}
    assert {s.ad: s.guncellendi for s in _satirlar(db_oturumu, kullanici.id)} == guncellendi_once
    assert depo_kimlik_bilgisi.dondur(db_oturumu, kullanici.id) == 0

    # Eski anahtar düşer, her şey yeni anahtarla okunur.
    monkeypatch.setenv(sifre.ANAHTAR_ENV, sifre_anahtari(TEST_KOK_ANAHTARI))
    assert depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id) == {**AZURE, "GEMINI_API_KEY": "AIza-DUMMY"}
