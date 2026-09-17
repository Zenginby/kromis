"""Paletler DB'de — Faz 1 / 6'nın bekçileri (docs/faz1-veritabani-hesaplar.md §6).

`services/depo_palet.py`: döküm `palette_store.create` kaydıyla anahtar anahtar
(SIRA dâhil) aynı; `colors` DONDURULMUŞ (yazıldığı gibi geri gelir, Türkçe
adlar dâhil, tarif değişse de yeniden hesaplanmaz); sıra en yeni başta; iki
kullanıcı izole; hesap silinince CASCADE. Sahip süzgeci/manifest bekçileri
test_galeri_db.py'de.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid

import pytest
from sqlalchemy import delete, func, select

import palette_store
from services import depo_palet, hesap, palet, tablolar, zaman

pytestmark = pytest.mark.usefixtures("depo_db")

RENKLER = [{"hex": "#c86a3c", "name": "Kiremit"}, {"hex": "#3c86c8", "name": "Gök Mavisi"},
           {"hex": "#6ac83c", "name": "Fıstık Yeşili"}]


def _ikinci_kullanici(db) -> uuid.UUID:
    k = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                           dogrulandi_at=hesap.simdi())
    db.add(k)
    db.flush()
    return k.id


def test_the_row_dump_equals_the_palette_store_record_key_for_key(db_oturumu, kullanici, tmp_path):
    an = dt.datetime(2026, 9, 17, 14, 3, 22, 123456).astimezone()
    eski = palette_store.create("Sonbahar", "#c86a3c", "triad", "balanced", RENKLER,
                                str(tmp_path), now=zaman.damga(an))
    yeni = depo_palet.olustur(db_oturumu, kullanici.id, "Sonbahar", "#c86a3c", "triad", "balanced",
                              RENKLER, now=an)
    assert list(eski) == list(yeni)
    for anahtar in eski:
        if anahtar != "id":
            assert eski[anahtar] == yeni[anahtar], anahtar
    assert re.fullmatch(r"[0-9a-f]{32}", yeni["id"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", yeni["created_at"])


def test_colors_are_frozen_and_survive_the_jsonb_round_trip(db_oturumu, kullanici, monkeypatch):
    """"Bu palet bana o görseli vermişti": ad çözücü değişse de kayıt aynı adları verir."""
    kayit = depo_palet.olustur(db_oturumu, kullanici.id, "Marka", "#c86a3c", "triad", "balanced", RENKLER)
    db_oturumu.commit()
    monkeypatch.setattr(palet, "resolve_palette", lambda *a, **k: [{"hex": "#000000", "name": "kara"}])
    okunan = depo_palet.bul(db_oturumu, kullanici.id, kayit["id"])
    assert okunan["colors"] == RENKLER, "renkler yeniden hesaplanmış ya da JSONB bozmuş"
    assert okunan == kayit
    # Üretim yolunun okuduğu şey de bu kayıt (services/palet.saved_palette).
    assert palet.saved_palette(db_oturumu, kullanici.id, kayit["id"])["colors"] == RENKLER
    assert palet.saved_palette(db_oturumu, kullanici.id, "deadbeefcafe") is None
    assert palet.saved_palette(db_oturumu, kullanici.id, None) is None


def test_palettes_are_listed_newest_first(db_oturumu, kullanici):
    taban = dt.datetime(2026, 9, 17, 12, 0, 0).astimezone()
    ids = [depo_palet.olustur(db_oturumu, kullanici.id, f"p{i}", "#c86a3c", "triad", "balanced", RENKLER,
                              now=taban.replace(microsecond=i))["id"] for i in range(3)]
    assert [p["id"] for p in depo_palet.listele(db_oturumu, kullanici.id)] == list(reversed(ids))


def test_two_users_never_see_each_others_palettes_at_the_repository_layer(db_oturumu, kullanici):
    a, b = kullanici.id, _ikinci_kullanici(db_oturumu)
    pa = depo_palet.olustur(db_oturumu, a, "A", "#c86a3c", "triad", "balanced", RENKLER)
    assert depo_palet.listele(db_oturumu, b) == []
    assert depo_palet.bul(db_oturumu, b, pa["id"]) is None
    assert palet.saved_palette(db_oturumu, b, pa["id"]) is None
    assert depo_palet.sil(db_oturumu, b, pa["id"]) is False
    assert depo_palet.bul(db_oturumu, a, pa["id"]) == pa


def test_deleting_the_account_cascades_its_palettes(db_oturumu, kullanici):
    b = _ikinci_kullanici(db_oturumu)
    depo_palet.olustur(db_oturumu, b, "B", "#c86a3c", "triad", "balanced", RENKLER)
    depo_palet.olustur(db_oturumu, kullanici.id, "A", "#c86a3c", "triad", "balanced", RENKLER)
    db_oturumu.execute(delete(tablolar.Kullanici).where(tablolar.Kullanici.id == b))
    assert db_oturumu.scalar(select(func.count()).select_from(tablolar.Palet)
                             .where(tablolar.Palet.kullanici_id == b)) == 0
    assert len(depo_palet.listele(db_oturumu, kullanici.id)) == 1


def test_legacy_and_bad_ids(db_oturumu, kullanici):
    db_oturumu.add(tablolar.Palet(id="aabbccddeeff", kullanici_id=kullanici.id, name="eski", seed="#c86a3c",
                                  mode="triad", strength="balanced", colors=RENKLER))
    db_oturumu.flush()
    assert depo_palet.bul(db_oturumu, kullanici.id, "aabbccddeeff")["name"] == "eski"
    for kotu in ("../../etc/passwd", "not-hex", "", None):
        assert depo_palet.bul(db_oturumu, kullanici.id, kotu) is None
        assert depo_palet.sil(db_oturumu, kullanici.id, kotu) is False
    assert depo_palet.sil(db_oturumu, kullanici.id, "aabbccddeeff") is True
    assert depo_palet.sil(db_oturumu, kullanici.id, "aabbccddeeff") is False
