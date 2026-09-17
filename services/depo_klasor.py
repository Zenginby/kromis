# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Klasör deposu — `klasorler` tablosu (Faz 1 / 5. görev).

`folders.py`nin DB ikizi: aynı işlev kümesi (`create/list/exists/depth/
descendants/delete_tree/rename/export_zip`), imzada `output_dir` yerine
`(db, kullanici_id)`. `folders.py` dondurulmuş kabuk ve `tools/ice_aktar.py`
için duruyor; saf süzgeci `safe_component` buradan da kullanılıyor.

Klasörler diskte dizin DEĞİL (folders.py'nin kararı aynen): görsel düz durur,
klasör kayıttaki bir etiket (`medya.folder_id`). Bu yüzden `/output/{filename}`
ve türev zincirleri taşımalardan etkilenmez.

HER SORGUDA `kullanici_id` — gerekçe services/depo_medya.py başında; bekçi
tests/test_galeri_db.py. Başkasının klasörü "yok" (404).

AĞAÇ YÜRÜYÜŞÜ PYTHON'DA, özyinelemeli CTE'de DEĞİL: kullanıcının klasör listesi
küçük (yüzler), tek `SELECT id, parent_id` yetiyor ve `folders.depth/
descendants`ın ziyaret-kümeli yürüyüşü birebir korunuyor — elle bozulmuş bir
zincirde (kendi kendinin ebeveyni; FK buna izin verir) asılı kalmamak dâhil.
CTE'nin `seviye < N` bekçisi aynı işi yapardı ama bozuk zincirde N döner,
1 değil; eski davranışı korumak daha ucuz.

SİLME: ağacın kökü silinir, alt klasörleri `klasorler.parent_id` FK'sının
`ON DELETE CASCADE`i düşürür; görseller `medya.folder_id`nin `SET NULL`ıyla
köke döner — rota sayıyı bilmek istediği için `depo_medya.klasorden_cikar`ı
ÖNCE çağırır (sıra belgede: ağacı çöz → görselleri çıkar → kayıtları sil).
"""
from __future__ import annotations

import datetime as dt
import os
import uuid
import zipfile
from collections.abc import Iterator
from typing import IO, cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from folders import _SAFE_ID, safe_component
from services import depo_medya, dosya, zaman
from services.tablolar import Klasor

__all__ = ["olustur", "listele", "var_mi", "derinlik", "altagac", "agaci_sil",
           "yeniden_adlandir", "zip_disa_aktar", "safe_component"]


def _json(k: Klasor) -> dict:
    """Satır → `folders.json` kaydı; anahtar sırası `folders.create` ile birebir."""
    return {"id": k.id, "name": k.name, "parent_id": k.parent_id,
            "created_at": zaman.damga(k.olusturuldu)}


def _gecerli(kimlik: str | None) -> bool:
    if not kimlik:
        return False
    return _SAFE_ID.fullmatch(kimlik) is not None


def _sahibin(kullanici_id: uuid.UUID):
    return select(Klasor).where(Klasor.kullanici_id == kullanici_id)


def olustur(db: Session, kullanici_id: uuid.UUID, name: str, *, parent_id: str | None = None,
            now: dt.datetime | None = None) -> dict:
    """`parent_id` None ise kök, doluysa o klasörün altında. Ebeveynin varlığını çağıran doğrular
    (`kapilar.check_folder`) — FK yalnız id'nin VAR olduğunu bilir, kimin olduğunu değil."""
    k = Klasor(id=uuid.uuid4().hex, kullanici_id=kullanici_id, name=name, parent_id=parent_id,
               olusturuldu=now if now is not None else zaman.an())
    db.add(k)
    db.flush()
    return _json(k)


def listele(db: Session, kullanici_id: uuid.UUID) -> list[dict]:
    """En yeni klasör başta (`folders.list_folders` ile aynı sıra)."""
    return [_json(k) for k in db.scalars(_sahibin(kullanici_id).order_by(Klasor.olusturuldu.desc()))]


def var_mi(db: Session, kullanici_id: uuid.UUID, folder_id: str | None) -> bool:
    if not _gecerli(folder_id):
        return False
    return db.scalar(select(Klasor.id).where(Klasor.kullanici_id == kullanici_id,
                                             Klasor.id == folder_id)) is not None


def _agac(db: Session, kullanici_id: uuid.UUID) -> dict[str, str | None]:
    """{id: parent_id} — kullanıcının bütün klasörleri, tek sorgu."""
    return {fid: pid for fid, pid in db.execute(select(Klasor.id, Klasor.parent_id)
                                                .where(Klasor.kullanici_id == kullanici_id))}


def derinlik(db: Session, kullanici_id: uuid.UUID, folder_id: str | None) -> int:
    """Kök klasör 1, altındaki 2… Klasör yoksa 0 (`folders.depth`in yürüyüşü, ziyaret kümeli)."""
    if not folder_id or not _gecerli(folder_id):
        return 0
    ebeveyn = _agac(db, kullanici_id)
    if folder_id not in ebeveyn:
        return 0
    gorulen: set[str] = set()
    seviye = 0
    su: str | None = folder_id
    while su and su in ebeveyn and su not in gorulen:
        gorulen.add(su)
        seviye += 1
        su = ebeveyn[su]
    return seviye


def altagac(db: Session, kullanici_id: uuid.UUID, folder_id: str | None) -> list[str]:
    """Klasörün kendisi + tüm alt klasörleri (üstten alta, BFS). Klasör yoksa boş."""
    if not folder_id or not _gecerli(folder_id):
        return []
    ebeveyn = _agac(db, kullanici_id)
    if folder_id not in ebeveyn:
        return []
    bulunan = [folder_id]
    gorulen = {folder_id}
    sira = [folder_id]
    while sira:
        ust = sira.pop(0)
        for fid, pid in ebeveyn.items():
            if pid == ust and fid not in gorulen:
                gorulen.add(fid)
                bulunan.append(fid)
                sira.append(fid)
    return bulunan


def agaci_sil(db: Session, kullanici_id: uuid.UUID, folder_id: str | None) -> list[str]:
    """Klasörü ve alt ağacını siler; silinen id'ler (yoksa boş). Görseller SİLİNMEZ (bkz. modül başı)."""
    hedefler = altagac(db, kullanici_id, folder_id)
    if not hedefler:
        return []
    # Bütün ağaç tek `DELETE … IN`: yalnız kökü silip CASCADE'e bırakmak da
    # olurdu, ama `rowcount` o zaman 1 olur ve sayının doğruluğu FK'nın yan
    # etkisine kalırdı. Süzgeç yine `kullanici_id` — `altagac` zaten yalnız
    # sahibin klasörlerini döndürdü.
    db.execute(delete(Klasor).where(Klasor.kullanici_id == kullanici_id, Klasor.id.in_(hedefler)))
    return hedefler


def yeniden_adlandir(db: Session, kullanici_id: uuid.UUID, folder_id: str | None,
                     new_name: str) -> dict | None:
    """Adı günceller. Klasör yoksa ya da ad boşsa None."""
    if not folder_id or not _gecerli(folder_id):
        return None
    ad = new_name.strip()
    if not ad:
        return None
    k = db.scalar(_sahibin(kullanici_id).where(Klasor.id == folder_id))
    if k is None:
        return None
    k.name = ad
    db.flush()
    return _json(k)


def zip_disa_aktar(db: Session, kullanici_id: uuid.UUID, folder_id: str | None,
                   output_dir: str, *, depo: dosya.Depo | None = None) -> tuple[Iterator[bytes], str] | None:
    """Klasör + alt ağacı, görselleriyle ZIP; `(bayt üreticisi, kök adı)`. Klasör yoksa None.

    `folders.export_zip`in ikizi; farkı hata biçimi: o `ValueError(i18n.t(…))`
    fırlatıyordu, burası konuşmuyor (depo katmanı kullanıcıya metin üretmez —
    `services/hesap.py` ile aynı karar), rota 404'ü kendi kurar.

    AKIŞLA (Faz 2 / 2): bir klasördeki videolar yüzlerce MB olabilir ve kovada
    dururken ZIP'i biz kuruyoruz (K7'nin tek istisnası) — bütününü belleğe
    almak yerine dosya dosya `depo.oku_akis` → `zipfile` → üretici. DB'ye
    dokunan her şey (klasör ağacı, kayıt listesi) ÜRETİCİDEN ÖNCE, burada:
    `StreamingResponse` gövdeyi rota döndükten sonra çekiyor ve isteğin
    `Session`ı o sırada kapanmış olabilir. Depoda bulunmayan dosya atlanır
    (eski `os.path.exists` kararı).
    """
    if not folder_id or not _gecerli(folder_id):
        return None
    satirlar = {k.id: k for k in db.scalars(_sahibin(kullanici_id))}
    kok = satirlar.get(folder_id)
    if kok is None:
        return None
    kok_adi = kok.name.strip()

    def _goreli_yol(fid: str) -> str:
        zincir: list[str] = []
        su: str | None = fid
        gorulen: set[str] = set()
        while su and su in satirlar and su not in gorulen:
            gorulen.add(su)
            zincir.append(satirlar[su].name.strip())
            if su == folder_id:
                break
            su = satirlar[su].parent_id
        zincir.reverse()
        return "/".join(safe_component(p) for p in zincir)

    agac = altagac(db, kullanici_id, folder_id)
    agac_kumesi = set(agac)
    kayitlar = depo_medya.klasorlerde(db, kullanici_id, agac)
    dizinler = [_goreli_yol(fid) for fid in agac]
    girdiler: list[tuple[str, str]] = []   # (arşiv adı, depo yolu)
    for kayit in kayitlar:
        ad = kayit.get("filename")
        if not ad:
            continue
        kf = kayit.get("folder_id")
        dizin = _goreli_yol(kf if isinstance(kf, str) and kf in agac_kumesi else folder_id)
        girdiler.append((f"{dizin}/{ad}", os.path.join(output_dir, ad)))
    secilen = depo or dosya.YEREL

    def _uret() -> Iterator[bytes]:
        akis = dosya.YazmaTamponu()
        # `ZipFile` `IO[bytes]` ister; tampon o protokolün yazma yüzü (write/flush) — typeshed
        # imzası tam nesneyi istiyor, çalışma zamanı yalnız bu iki adı çağırıyor.
        with zipfile.ZipFile(cast("IO[bytes]", akis), "w", zipfile.ZIP_DEFLATED) as zf:
            for goreli in dizinler:
                if goreli:
                    zf.writestr(f"{goreli}/", b"")
            for arsiv_adi, yol in girdiler:
                if not secilen.var(yol):
                    continue
                bilgi = zipfile.ZipInfo(arsiv_adi)
                bilgi.compress_type = zipfile.ZIP_DEFLATED   # `zf.write`in eski kipi; PNG/MP4 zaten sıkışık
                with zf.open(bilgi, "w", force_zip64=True) as hedef:
                    for parca in secilen.oku_akis(yol):
                        hedef.write(parca)
                        yield akis.bosalt()
            yield akis.bosalt()
        yield akis.bosalt()

    return _uret(), kok_adi
