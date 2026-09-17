"""Tercihler DB'de — Faz 1 / 6'nın bekçileri (docs/faz1-veritabani-hesaplar.md §6).

`services/depo_tercih.py`: `oku` = `prefs.read` (birleşik görünüm, `_SCHEMA`
sırası ve varsayılanları), `kayitli` = `prefs.read_stored` (NULL = hiç
yazılmamış; varsayılana EŞİT yazılmış değer korunur), `guncelle` =
`prefs.update` (aynı reddler — bilinmeyen anahtar, yanlış tür, küme dışı
değer, `chat_model` ↔ sağlayıcı çapraz kuralı — ama cümle yerine i18n
ANAHTARI taşıyan `GecersizTercih`); ötekiler korunur; bayat model DB'de
durur, okunurken varsayılana düşer; kullanıcı başına tek satır, CASCADE.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

import catalog
import i18n
import models
import prefs
from services import depo_tercih, hesap, tablolar

pytestmark = pytest.mark.usefixtures("depo_db")


def _ikinci_kullanici(db) -> uuid.UUID:
    k = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                           dogrulandi_at=hesap.simdi())
    db.add(k)
    db.flush()
    return k.id


def test_a_fresh_user_reads_the_defaults_in_schema_order_without_a_row(db_oturumu, kullanici):
    assert depo_tercih.oku(db_oturumu, kullanici.id) == prefs.DEFAULTS
    assert list(depo_tercih.oku(db_oturumu, kullanici.id)) == list(prefs.DEFAULTS) == list(prefs._SCHEMA)
    assert depo_tercih.kayitli(db_oturumu, kullanici.id) == {}
    assert db_oturumu.scalar(select(tablolar.Tercih).where(tablolar.Tercih.kullanici_id == kullanici.id)) is None
    # Boş güncelleme de satır AÇMAZ (`prefs.update`in "dosyaya dokunma" kuralı).
    assert depo_tercih.guncelle(db_oturumu, kullanici.id, {}) == prefs.DEFAULTS
    assert db_oturumu.scalar(select(tablolar.Tercih).where(tablolar.Tercih.kullanici_id == kullanici.id)) is None


def test_null_means_never_written_and_a_default_equal_value_is_still_written(db_oturumu, kullanici):
    """`read()`/`read_stored()` ayrımı sütun düzeyinde: dil zinciri tam bu farkı soruyor."""
    depo_tercih.guncelle(db_oturumu, kullanici.id, {"language": i18n.DEFAULT, "theme": "amber"})
    assert depo_tercih.kayitli(db_oturumu, kullanici.id) == {"theme": "amber", "language": i18n.DEFAULT}
    satir = db_oturumu.scalar(select(tablolar.Tercih).where(tablolar.Tercih.kullanici_id == kullanici.id))
    assert satir.autosave_sessions is None and satir.image_model is None, "yazılmayan sütun NULL kalır"
    goruntu = depo_tercih.oku(db_oturumu, kullanici.id)
    assert goruntu == {**prefs.DEFAULTS, "theme": "amber", "language": i18n.DEFAULT}
    # İkinci yazım ötekileri KORUR, tek satır kalır.
    depo_tercih.guncelle(db_oturumu, kullanici.id, {"autosave_sessions": False})
    assert depo_tercih.kayitli(db_oturumu, kullanici.id) == {
        "autosave_sessions": False, "theme": "amber", "language": i18n.DEFAULT}
    assert len(list(db_oturumu.scalars(select(tablolar.Tercih)
                                       .where(tablolar.Tercih.kullanici_id == kullanici.id)))) == 1


@pytest.mark.parametrize("degerler, kod", [
    ({"tema": "amber"}, "err.unknown_pref"),
    ({"autosave_sessions": "hayır"}, "err.bad_pref_type"),
    ({"theme": "neon"}, "err.bad_pref_value"),
    ({"language": "de"}, "err.bad_pref_value"),
    ({"image_model": "yok-boyle-model"}, "err.bad_pref_value"),
    ({"chat_model": "yok-boyle-model"}, "err.bad_pref_chat_model"),
])
def test_update_rejects_exactly_what_the_frozen_store_rejects_with_a_key_not_a_sentence(
        degerler, kod, db_oturumu, kullanici, tmp_path):
    """Kapılar `prefs.update` ile bir; depo cümle kurmaz, anahtar taşır — cümle rotada (`i18n.t`)."""
    with pytest.raises(ValueError):
        prefs.update(dict(degerler), str(tmp_path))
    with pytest.raises(depo_tercih.GecersizTercih) as hata:
        depo_tercih.guncelle(db_oturumu, kullanici.id, dict(degerler))
    assert hata.value.kod == kod
    assert i18n.t(kod, "tr", **hata.value.alanlar) != kod, "anahtar sözlükte yok ya da alan eksik"
    assert depo_tercih.kayitli(db_oturumu, kullanici.id) == {}, "reddedilen istek yazdı"


def test_the_enum_gates_are_the_shared_ones(db_oturumu, kullanici):
    """`_ENUMS` kopya değil ithal: `models.ALLOWED_*` ve katalog değişince depo kendiliğinden izler."""
    assert prefs._ENUMS["theme"] is models.ALLOWED_THEMES
    assert prefs._ENUMS["language"] is models.ALLOWED_LANGUAGES
    for tema in models.ALLOWED_THEMES:
        assert depo_tercih.guncelle(db_oturumu, kullanici.id, {"theme": tema})["theme"] == tema
    saglayici = catalog.DEFAULT_CHAT_PROVIDER
    model = catalog.chat_models_for(saglayici)[0].id
    assert depo_tercih.guncelle(db_oturumu, kullanici.id, {"chat_provider": saglayici,
                                                             "chat_model": model})["chat_model"] == model


def test_a_stale_model_in_the_row_falls_back_to_the_default_when_read(db_oturumu, kullanici):
    """Model sütunları CHECK'siz (katalog değişir); bayat değer okunurken düşer, satır düzeltilmez."""
    db_oturumu.add(tablolar.Tercih(kullanici_id=kullanici.id, image_model="katalogdan-kalkmis"))
    db_oturumu.flush()
    assert depo_tercih.kayitli(db_oturumu, kullanici.id) == {}
    assert depo_tercih.oku(db_oturumu, kullanici.id)["image_model"] == catalog.DEFAULT_IMAGE_MODEL
    satir = db_oturumu.scalar(select(tablolar.Tercih).where(tablolar.Tercih.kullanici_id == kullanici.id))
    assert satir.image_model == "katalogdan-kalkmis", "okuma yan etkisiz"
    depo_tercih.guncelle(db_oturumu, kullanici.id, {"image_model": catalog.DEFAULT_IMAGE_MODEL})
    db_oturumu.refresh(satir)
    assert satir.image_model == catalog.DEFAULT_IMAGE_MODEL


def test_two_users_have_separate_rows(db_oturumu, kullanici):
    a, b = kullanici.id, _ikinci_kullanici(db_oturumu)
    depo_tercih.guncelle(db_oturumu, a, {"theme": "amber"})
    assert depo_tercih.oku(db_oturumu, b) == prefs.DEFAULTS
    depo_tercih.guncelle(db_oturumu, b, {"theme": "ocean"})
    assert depo_tercih.oku(db_oturumu, a)["theme"] == "amber"
    assert depo_tercih.oku(db_oturumu, b)["theme"] == "ocean"


def test_deleting_the_account_cascades_its_preference_row(db_oturumu, kullanici):
    b = _ikinci_kullanici(db_oturumu)
    depo_tercih.guncelle(db_oturumu, b, {"theme": "amber"})
    db_oturumu.execute(delete(tablolar.Kullanici).where(tablolar.Kullanici.id == b))
    assert db_oturumu.scalar(select(tablolar.Tercih).where(tablolar.Tercih.kullanici_id == b)) is None
