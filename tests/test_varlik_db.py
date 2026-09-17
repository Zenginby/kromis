"""Varlıklar DB'de — Faz 1 / 6'nın bekçileri (docs/faz1-veritabani-hesaplar.md §6).

`services/depo_varlik.py`: döküm `assets_store.save_asset` kaydıyla anahtar
anahtar aynı (`tur` sütunu dökümde `kind`); dosya yerleşimi
`<assets_dir>/<tur>/<id>.png` aynen, `index.json` YAZILMAZ; geçersiz tür ne
DB'ye ne diske gider (`uploads` satırını CHECK de reddeder); silme satır +
dosya sözleşmesi; servis/bindirme yolu satır VE dosya ister; iki kullanıcı
izole; CASCADE.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

import assets_store
from services import depo_varlik, hesap, tablolar, zaman

pytestmark = pytest.mark.usefixtures("depo_db")


def _ikinci_kullanici(db) -> uuid.UUID:
    k = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                           dogrulandi_at=hesap.simdi())
    db.add(k)
    db.flush()
    return k.id


@pytest.mark.parametrize("tur", assets_store.KINDS)
def test_the_row_dump_equals_the_manifest_record_and_the_file_layout_is_unchanged(tur, db_oturumu, kullanici, tmp_path):
    an = dt.datetime(2026, 9, 17, 14, 3, 22, 123456).astimezone()
    eski = assets_store.save_asset(tur, b"\x89PNG", "Logo Mavi", str(tmp_path / "eski"), now=zaman.damga(an))
    yeni = depo_varlik.kaydet(db_oturumu, kullanici.id, tur, b"\x89PNG", "Logo Mavi",
                              str(tmp_path / "yeni"), now=an)
    assert list(eski) == list(yeni)
    for anahtar in eski:
        if anahtar not in ("id", "filename"):
            assert eski[anahtar] == yeni[anahtar], anahtar
    assert yeni["kind"] == tur and yeni["filename"] == yeni["id"] + ".png"
    assert re.fullmatch(r"[0-9a-f]{32}", yeni["id"])
    dizin = tmp_path / "yeni" / tur
    assert (dizin / yeni["filename"]).read_bytes() == b"\x89PNG"
    assert sorted(os.listdir(dizin)) == [yeni["filename"]], "manifest yazıldı"
    db_oturumu.commit()
    assert depo_varlik.listele(db_oturumu, kullanici.id, tur) == [yeni]


def test_listing_all_kinds_is_newest_first_across_kinds(db_oturumu, kullanici, tmp_path):
    taban = dt.datetime(2026, 9, 17, 12, 0, 0).astimezone()
    sira = []
    for i, tur in enumerate(("logos", "banners", "mottos", "logos")):
        sira.append(depo_varlik.kaydet(db_oturumu, kullanici.id, tur, b"x", f"v{i}", str(tmp_path),
                                       now=taban.replace(microsecond=i))["id"])
    assert [v["id"] for v in depo_varlik.listele(db_oturumu, kullanici.id)] == list(reversed(sira))
    assert [v["id"] for v in depo_varlik.listele(db_oturumu, kullanici.id, "logos")] == [sira[3], sira[0]]
    assert depo_varlik.listele(db_oturumu, kullanici.id, "uploads") == []


def test_an_invalid_kind_never_reaches_the_disk_or_the_database(db_oturumu, kullanici, tmp_path):
    with pytest.raises(ValueError):
        depo_varlik.kaydet(db_oturumu, kullanici.id, "uploads", b"x", "eski", str(tmp_path))
    assert not (tmp_path / "uploads").exists()
    assert depo_varlik.dosya_yolu(db_oturumu, kullanici.id, "uploads", "aabbccddeeff", str(tmp_path)) is None
    assert depo_varlik.sil(db_oturumu, kullanici.id, "uploads", "aabbccddeeff", str(tmp_path)) is False
    # CHECK de reddeder: içe aktarma aracı ölü türü `logos`a taşımak zorunda.
    with pytest.raises(IntegrityError):
        db_oturumu.add(tablolar.Varlik(id="aabbccddeeff", kullanici_id=kullanici.id,
                                       filename="aabbccddeeff.png", name="eski", tur="uploads"))
        db_oturumu.flush()
    db_oturumu.rollback()


def test_the_paths_require_the_row_and_the_file(db_oturumu, kullanici, tmp_path):
    out = str(tmp_path)
    v = depo_varlik.kaydet(db_oturumu, kullanici.id, "logos", b"x", "l", out)
    yol = os.path.join(out, "logos", v["filename"])
    assert depo_varlik.dosya_yolu(db_oturumu, kullanici.id, "logos", v["id"], out) == yol
    assert depo_varlik.dosya_yolu_adiyla(db_oturumu, kullanici.id, "logos", v["filename"], out) == yol
    # Başka türden aranırsa yok (motto id'si logos kütüphanesinde çözülmez).
    assert depo_varlik.dosya_yolu(db_oturumu, kullanici.id, "mottos", v["id"], out) is None
    # Satırsız dosya sunulmaz…
    (tmp_path / "logos" / "deadbeef0000.png").write_bytes(b"x")
    assert depo_varlik.dosya_yolu(db_oturumu, kullanici.id, "logos", "deadbeef0000", out) is None
    assert depo_varlik.dosya_yolu_adiyla(db_oturumu, kullanici.id, "logos", "deadbeef0000.png", out) is None
    assert depo_varlik.dosya_yolu_adiyla(db_oturumu, kullanici.id, "logos", "index.json", out) is None
    # …dosyasız satır da.
    os.remove(yol)
    assert depo_varlik.dosya_yolu(db_oturumu, kullanici.id, "logos", v["id"], out) is None


def test_delete_removes_the_row_and_the_file_and_counts_either(db_oturumu, kullanici, tmp_path):
    out = str(tmp_path)
    v = depo_varlik.kaydet(db_oturumu, kullanici.id, "logos", b"x", "l", out)
    assert depo_varlik.sil(db_oturumu, kullanici.id, "logos", v["id"], out) is True
    assert not (tmp_path / "logos" / v["filename"]).exists()
    assert depo_varlik.listele(db_oturumu, kullanici.id, "logos") == []
    assert depo_varlik.sil(db_oturumu, kullanici.id, "logos", v["id"], out) is False
    # `assets_store.delete_asset` sözleşmesi: kaydı olmayan dosya da silinmiş sayılır.
    (tmp_path / "logos" / "deadbeef0000.png").write_bytes(b"x")
    assert depo_varlik.sil(db_oturumu, kullanici.id, "logos", "deadbeef0000", out) is True
    assert not (tmp_path / "logos" / "deadbeef0000.png").exists()
    for kotu in ("../../etc/passwd", "not-hex", "", None):
        assert depo_varlik.sil(db_oturumu, kullanici.id, "logos", kotu, out) is False
        assert depo_varlik.dosya_yolu(db_oturumu, kullanici.id, "logos", kotu, out) is None


def test_two_users_never_see_each_others_assets_at_the_repository_layer(db_oturumu, kullanici, tmp_path):
    a, b = kullanici.id, _ikinci_kullanici(db_oturumu)
    out_a, out_b = str(tmp_path / "a"), str(tmp_path / "b")
    va = depo_varlik.kaydet(db_oturumu, a, "logos", b"x", "A", out_a)
    assert depo_varlik.listele(db_oturumu, b) == []
    assert depo_varlik.dosya_yolu(db_oturumu, b, "logos", va["id"], out_a) is None
    assert depo_varlik.dosya_yolu_adiyla(db_oturumu, b, "logos", va["filename"], out_a) is None
    assert depo_varlik.sil(db_oturumu, b, "logos", va["id"], out_b) is False
    assert os.path.isfile(os.path.join(out_a, "logos", va["filename"]))
    assert depo_varlik.listele(db_oturumu, a) == [va]


def test_deleting_the_account_cascades_its_assets(db_oturumu, kullanici, tmp_path):
    b = _ikinci_kullanici(db_oturumu)
    depo_varlik.kaydet(db_oturumu, b, "logos", b"x", "B", str(tmp_path / "b"))
    depo_varlik.kaydet(db_oturumu, kullanici.id, "logos", b"x", "A", str(tmp_path / "a"))
    db_oturumu.execute(delete(tablolar.Kullanici).where(tablolar.Kullanici.id == b))
    assert db_oturumu.scalar(select(func.count()).select_from(tablolar.Varlik)
                             .where(tablolar.Varlik.kullanici_id == b)) == 0
    assert len(depo_varlik.listele(db_oturumu, kullanici.id)) == 1
