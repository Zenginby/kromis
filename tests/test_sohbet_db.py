"""Sohbetler DB'de — Faz 1 / 6'nın bekçileri (docs/faz1-veritabani-hesaplar.md §6).

`services/depo_sohbet.py` için tests/test_galeri_db.py'nin (iii) ŞEKİL ve (iv)
ANLAM aileleri: satırın dökümü `chat_store.create` kaydıyla anahtar anahtar
(SIRA dâhil) aynı, özet alanları `chat_store._SUMMARY_FIELDS` ile bir; sıra
`updated_at DESC`; boş güncelleme `updated_at`a dokunmaz; iki kullanıcı depo
düzeyinde izole; hesap silinince sohbetleri CASCADE ile gider. (i)/(ii)
aileleri (sahip süzgeci, manifest çağrısı yok) test_galeri_db.py'de.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid

import pytest
from sqlalchemy import delete, func, select

import chat_store
from services import depo_sohbet, hesap, tablolar, zaman

pytestmark = pytest.mark.usefixtures("depo_db")

THREAD = [{"role": "user", "content": "kare instagram görseli", "display": "Instagram karesi"},
          {"role": "assistant", "content": "hangi mecra?"}]
SONUC = {"role": "result", "image_ids": ["aaaa1111aaaa", "bbbb2222bbbb"],
         "params": {"kind": "generate", "size": "1024x1024", "quality": "medium"}}


def _ikinci_kullanici(db) -> uuid.UUID:
    k = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                           dogrulandi_at=hesap.simdi())
    db.add(k)
    db.flush()
    return k.id


# ── (iii) şekil ────────────────────────────────────────────────────────

@pytest.mark.parametrize("messages", [THREAD, THREAD + [SONUC]], ids=["kapaksiz", "kapakli"])
def test_the_row_dump_equals_the_chat_store_record_key_for_key(messages, db_oturumu, kullanici, tmp_path):
    """Anahtarlar, SIRA ve değerler aynı; yalnız `id` farklı. Kapak koşullu ve SONDA."""
    an = dt.datetime(2026, 9, 17, 14, 3, 22, 123456).astimezone()
    eski = chat_store.create("kare", messages, str(tmp_path), now=zaman.damga(an))
    yeni = depo_sohbet.olustur(db_oturumu, kullanici.id, "kare", messages, now=an)
    assert list(eski) == list(yeni)
    for anahtar in eski:
        if anahtar != "id":
            assert eski[anahtar] == yeni[anahtar], anahtar
    assert ("cover_image_id" in yeni) == (messages[-1] is SONUC)
    assert re.fullmatch(r"[0-9a-f]{32}", yeni["id"]) and chat_store.valid_id(yeni["id"])
    db_oturumu.commit()
    okunan = depo_sohbet.bul(db_oturumu, kullanici.id, yeni["id"])
    assert okunan == yeni, "JSONB gidiş-dönüşü dökümü değiştirdi"
    assert okunan["messages"][0]["display"] == "Instagram karesi"


def test_the_summary_matches_the_frozen_stores_list_shape(db_oturumu, kullanici, tmp_path):
    """Kenar paneli özeti: `_SUMMARY_FIELDS` + `message_count`, `cover_image_id` her zaman var (None olabilir)."""
    assert depo_sohbet.OZET_ALANLARI == chat_store._SUMMARY_FIELDS
    an = dt.datetime(2026, 9, 17, 14, 3, 22).astimezone()
    chat_store.create("a", THREAD, str(tmp_path), now=zaman.damga(an))
    chat_store.create("b", THREAD + [SONUC], str(tmp_path), now=zaman.damga(an))
    depo_sohbet.olustur(db_oturumu, kullanici.id, "a", THREAD, now=an)
    depo_sohbet.olustur(db_oturumu, kullanici.id, "b", THREAD + [SONUC], now=an.replace(microsecond=1))
    eski = chat_store.list_chats(str(tmp_path))
    yeni = depo_sohbet.listele(db_oturumu, kullanici.id)
    assert [c["title"] for c in eski] == [c["title"] for c in yeni] == ["b", "a"]
    for e, y in zip(eski, yeni):
        assert list(e) == list(y)
        assert {k: v for k, v in e.items() if k != "id"} == {k: v for k, v in y.items() if k != "id"}
    assert yeni[0]["cover_image_id"] == "aaaa1111aaaa" and yeni[1]["cover_image_id"] is None
    assert yeni[0]["message_count"] == 3 and "messages" not in yeni[0]


def test_timestamps_keep_the_manifest_format(db_oturumu, kullanici):
    kayit = depo_sohbet.olustur(db_oturumu, kullanici.id, "x", THREAD)
    for alan in ("created_at", "updated_at"):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", kayit[alan]), alan
    assert kayit["created_at"] == kayit["updated_at"]


# ── (iv) anlam ─────────────────────────────────────────────────────────

def test_list_is_ordered_by_updated_at_then_created_at(db_oturumu, kullanici):
    """En son GÜNCELLENEN başta (`chat_store.list_chats`in gerekçesi); eşitlikte yeni oluşturulan."""
    taban = dt.datetime(2026, 9, 17, 12, 0, 0).astimezone()
    eski = depo_sohbet.olustur(db_oturumu, kullanici.id, "eski", THREAD, now=taban)
    orta = depo_sohbet.olustur(db_oturumu, kullanici.id, "orta", THREAD, now=taban + dt.timedelta(minutes=1))
    yeni = depo_sohbet.olustur(db_oturumu, kullanici.id, "yeni", THREAD, now=taban + dt.timedelta(minutes=2))
    assert [c["id"] for c in depo_sohbet.listele(db_oturumu, kullanici.id)] == [yeni["id"], orta["id"], eski["id"]]
    depo_sohbet.guncelle(db_oturumu, kullanici.id, eski["id"], title="eski ama güncel",
                         now=taban + dt.timedelta(hours=1))
    assert [c["title"] for c in depo_sohbet.listele(db_oturumu, kullanici.id)] == ["eski ama güncel", "yeni", "orta"]
    # Aynı `updated_at`: yeni oluşturulan üstte (manifest sırasının tersi).
    ayni = taban + dt.timedelta(hours=2)
    a = depo_sohbet.olustur(db_oturumu, kullanici.id, "a", THREAD, now=ayni)
    b = depo_sohbet.olustur(db_oturumu, kullanici.id, "b", THREAD, now=ayni.replace(microsecond=5))
    assert [c["id"] for c in depo_sohbet.listele(db_oturumu, kullanici.id)][:2] == [b["id"], a["id"]]


def test_an_empty_update_returns_the_record_but_does_not_touch_updated_at(db_oturumu, kullanici):
    an = dt.datetime(2026, 9, 17, 12, 0, 0).astimezone()
    kayit = depo_sohbet.olustur(db_oturumu, kullanici.id, "x", THREAD, now=an)
    ayni = depo_sohbet.guncelle(db_oturumu, kullanici.id, kayit["id"], now=an + dt.timedelta(days=1))
    assert ayni == kayit
    # Gövde değişince kapak yeniden hesaplanır, yeniden adlandırmada korunur.
    kapakli = depo_sohbet.guncelle(db_oturumu, kullanici.id, kayit["id"], messages=THREAD + [SONUC],
                                   now=an + dt.timedelta(days=1))
    assert kapakli["cover_image_id"] == "aaaa1111aaaa" and kapakli["updated_at"] == zaman.damga(an + dt.timedelta(days=1))
    adli = depo_sohbet.guncelle(db_oturumu, kullanici.id, kayit["id"], title="yeni ad")
    assert adli["cover_image_id"] == "aaaa1111aaaa" and adli["messages"] == THREAD + [SONUC]
    kapaksiz = depo_sohbet.guncelle(db_oturumu, kullanici.id, kayit["id"], messages=THREAD)
    assert "cover_image_id" not in kapaksiz, "bayat kapak düşmedi"


def test_two_users_never_see_each_others_chats_at_the_repository_layer(db_oturumu, kullanici):
    a, b = kullanici.id, _ikinci_kullanici(db_oturumu)
    sa = depo_sohbet.olustur(db_oturumu, a, "A", THREAD)
    assert depo_sohbet.listele(db_oturumu, b) == []
    assert depo_sohbet.bul(db_oturumu, b, sa["id"]) is None
    assert depo_sohbet.guncelle(db_oturumu, b, sa["id"], title="calinti") is None
    assert depo_sohbet.sil(db_oturumu, b, sa["id"]) is False
    assert depo_sohbet.hepsini_sil(db_oturumu, b) == 0
    assert depo_sohbet.bul(db_oturumu, a, sa["id"])["title"] == "A"
    sb = depo_sohbet.olustur(db_oturumu, b, "B", THREAD)
    assert [c["id"] for c in depo_sohbet.listele(db_oturumu, a)] == [sa["id"]]
    assert depo_sohbet.hepsini_sil(db_oturumu, a) == 1
    assert depo_sohbet.bul(db_oturumu, b, sb["id"]) is not None, "A'nın 'tümünü sil'i B'ye dokundu"


def test_deleting_the_account_cascades_its_chats(db_oturumu, kullanici):
    b = _ikinci_kullanici(db_oturumu)
    depo_sohbet.olustur(db_oturumu, b, "B", THREAD)
    depo_sohbet.olustur(db_oturumu, kullanici.id, "A", THREAD)
    db_oturumu.execute(delete(tablolar.Kullanici).where(tablolar.Kullanici.id == b))
    assert db_oturumu.scalar(select(func.count()).select_from(tablolar.Sohbet)
                             .where(tablolar.Sohbet.kullanici_id == b)) == 0
    assert len(depo_sohbet.listele(db_oturumu, kullanici.id)) == 1


def test_legacy_and_bad_ids(db_oturumu, kullanici):
    """12 haneli eski id geçer; yol parçası taşıyan/boş id DB'ye hiç gitmez."""
    db_oturumu.add(tablolar.Sohbet(id="aabbccddeeff", kullanici_id=kullanici.id, title="eski",
                                   mesajlar=THREAD))
    db_oturumu.flush()
    assert depo_sohbet.bul(db_oturumu, kullanici.id, "aabbccddeeff")["title"] == "eski"
    for kotu in ("../../etc/passwd", "not-hex", "", None):
        assert depo_sohbet.bul(db_oturumu, kullanici.id, kotu) is None
        assert depo_sohbet.guncelle(db_oturumu, kullanici.id, kotu, title="x") is None
        assert depo_sohbet.sil(db_oturumu, kullanici.id, kotu) is False
    assert depo_sohbet.sil(db_oturumu, kullanici.id, "aabbccddeeff") is True
