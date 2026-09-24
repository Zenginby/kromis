# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kota — saatlik iş tavanı ve günlük kredi tavanı, `isler`den sayılır (Faz 2 / 6, K5).

`services/hesap.py`nin deneme sayacının (`giris_denemeleri`: pencere, sayı,
`Retry-After`) ikizi; sayılan şey iş satırları. Defter YOK (Faz 3): birim
kataloğun kredisi (`catalog.cost_for`, 1 kredi ≈ 0,005 USD çıpası) ve sayılan
sayı rotanın yazdığı TAHMİN (`isler.kredi_tahmini`, üst sınır) — gerçek
maliyet Faz 3'ün mutabakatı, o güne kadar fatura tahminin altında kalır.

İKİ TAVAN, İKİ TEHDİT — biri ötekinin yerine geçmez (K5'in gerekçesi):

* **Saatlik iş** (`KROMIS_SAATLIK_IS_TAVANI`, öntanımlı 60): kullanıcının son
  60 dakikada sıraya aldığı iş sayısı (`iptal` hariç — sırada hiç
  koşmadı). HERKESE, BYOK'lu kullanıcı dâhil: kendi anahtarıyla da işçiyi
  meşgul ediyor. Faz 5'in "kötüye kullanım / IP limitleri" kartının tohumu.
* **Günlük kredi** (`KROMIS_GUNLUK_KREDI_TAVANI`, öntanımlı 2.000 ≈ 10 USD):
  son 24 saatte PLATFORM anahtarıyla koşan işlerin (`anahtar_kaynagi =
  'platform'`, `iptal` hariç) tahmin toplamı + yeni işin tahmini tavanı
  AŞARSA 429. BYOK'lu iş SAYILMAZ (kendi parası). Kullanıcı başına ezme
  `kullanicilar.gunluk_kredi_tavani` (NULL = öntanımlı; admin 8. görevde yazar).
  `hata`yla kapanan iş SAYILIR: sağlayıcı faturalamış olabilir (K8'in aynı
  kuşkusu), tahmin üst sınır kalsın.

`Retry-After` = pencere içindeki EN ESKİ sayılan işin pencereden çıkmasına
kalan saniye (+1, yuvarlama payı; `hesap._bekleme`nin aynı hesabı): o iş
düşünce sayı bir eksilir ve istek geçer. Günlük tavanda bu "pencerenin
açılışı" — gövde kalan krediyi ve o saati de söyler, çünkü ön yüz başlığı
okumaz (`routers/hesap.py::_cok_deneme`in aynı kararı).

Pencere sınırı `>` (dâhil değil) ve şimdi `zaman.an()` — testler onu yamalar
(`monkeypatch.setattr(zaman, "an", …)`) ve pencereyi kaydırır. Ortam her
çağrıda okunur (`kapilar.es_zamanli_is_tavani`nın gerekçesi); bozuk değer
YÜKSEK SESLE, sessizce öntanımlıya düşmez. Sayım `ix_isler_kullanici_olusturuldu`
üzerinden (`kullanici_id`, `olusturuldu`) — yeni indeks gerekmedi.
"""
from __future__ import annotations

import datetime as dt
import os
import uuid
from collections.abc import Mapping

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import i18n
from services import dil, zaman
from services.tablolar import DURUM_IPTAL, Is, Kullanici

__all__ = ["SAATLIK_IS_ENV", "SAATLIK_IS_VARSAYILAN", "SAATLIK_PENCERE",
           "GUNLUK_KREDI_ENV", "GUNLUK_KREDI_VARSAYILAN", "GUNLUK_PENCERE",
           "saatlik_is_tavani", "gunluk_kredi_tavani", "saatlik_durum", "saatlik_bekleme",
           "gunluk_durum",
           "check_saatlik", "check_gunluk"]

# `.env.example` 1. bölüm aynı adları buradan okur (bekçisi tests/test_docker_kapisi.py `ALTYAPI`).
SAATLIK_IS_ENV = "KROMIS_SAATLIK_IS_TAVANI"
SAATLIK_IS_VARSAYILAN = 60
SAATLIK_PENCERE = dt.timedelta(hours=1)

GUNLUK_KREDI_ENV = "KROMIS_GUNLUK_KREDI_TAVANI"
GUNLUK_KREDI_VARSAYILAN = 2000
GUNLUK_PENCERE = dt.timedelta(hours=24)


def _tam_sayi(ortam: Mapping[str, str], ad: str, varsayilan: int) -> int:
    ham = (ortam.get(ad) or "").strip()
    if not ham:
        return varsayilan
    try:
        deger = int(ham)
    except ValueError as e:
        raise ValueError(f"{ad} tam sayi olmali, verilen: {ham!r}") from e
    if deger < 1:
        raise ValueError(f"{ad} en az 1 olmali, verilen: {deger}")
    return deger


def saatlik_is_tavani(ortam: Mapping[str, str] | None = None) -> int:
    """`KROMIS_SAATLIK_IS_TAVANI`; boşsa 60. Bozuk değer `ValueError`."""
    return _tam_sayi(os.environ if ortam is None else ortam, SAATLIK_IS_ENV, SAATLIK_IS_VARSAYILAN)


def gunluk_kredi_tavani(ortam: Mapping[str, str] | None = None) -> int:
    """`KROMIS_GUNLUK_KREDI_TAVANI`; boşsa 2.000. Bozuk değer `ValueError`."""
    return _tam_sayi(os.environ if ortam is None else ortam, GUNLUK_KREDI_ENV,
                     GUNLUK_KREDI_VARSAYILAN)


def _bekleme_sn(en_eski: dt.datetime, pencere: dt.timedelta, an: dt.datetime) -> int:
    """En eski sayılan iş pencereden çıkınca kaç saniye geçmiş olur (en az 1)."""
    return max(1, int((en_eski + pencere - an).total_seconds()) + 1)


def saatlik_durum(db: Session, kullanici_id: uuid.UUID, an: dt.datetime | None = None,
                  ) -> tuple[int, dt.datetime | None]:
    """Son 60 dk'da sıraya alınan iş sayısı (`iptal` hariç) ve en eskisinin anı — `gunluk_durum`un saatlik ikizi.

    `saatlik_bekleme` bundan türer; `GET /api/kota` (Faz 2 / 8, belge §6 devri)
    sayıyı ve pencerenin açılışını doğrudan buradan okur.
    """
    an = an if an is not None else zaman.an()
    sayi, en_eski = db.execute(
        select(func.count(), func.min(Is.olusturuldu))
        .where(Is.kullanici_id == kullanici_id, Is.durum != DURUM_IPTAL,
               Is.olusturuldu > an - SAATLIK_PENCERE)).one()
    return int(sayi or 0), en_eski


def saatlik_bekleme(db: Session, kullanici_id: uuid.UUID, an: dt.datetime | None = None,
                    *, tavan: int | None = None) -> int | None:
    """Son 60 dk'daki iş sayısı tavana ulaştıysa beklenecek saniye; değilse `None`."""
    an = an if an is not None else zaman.an()
    tavan = tavan if tavan is not None else saatlik_is_tavani()
    sayi, en_eski = saatlik_durum(db, kullanici_id, an)
    if sayi < tavan or en_eski is None:
        return None
    return _bekleme_sn(en_eski, SAATLIK_PENCERE, an)


def gunluk_durum(db: Session, kullanici_id: uuid.UUID, an: dt.datetime | None = None,
                 ) -> tuple[int, dt.datetime | None]:
    """Son 24 saatte platform anahtarıyla sıraya alınan kredi toplamı ve en eski işin anı.

    Toplam `iptal` hariç, `anahtar_kaynagi = 'platform'` satırlar; ikinci
    değer `Retry-After`/pencere açılışı için (sayılan iş yoksa `None`).
    """
    an = an if an is not None else zaman.an()
    toplam, en_eski = db.execute(
        select(func.coalesce(func.sum(Is.kredi_tahmini), 0), func.min(Is.olusturuldu))
        .where(Is.kullanici_id == kullanici_id, Is.durum != DURUM_IPTAL,
               Is.anahtar_kaynagi == "platform",
               Is.olusturuldu > an - GUNLUK_PENCERE)).one()
    return int(toplam or 0), en_eski


def check_saatlik(db: Session, kullanici_id: uuid.UUID) -> None:
    """Saatlik iş tavanı: dolmuşsa 429 + `Retry-After` + `err.saatlik_is_tavani`; değilse sessiz."""
    tavan = saatlik_is_tavani()
    bekle = saatlik_bekleme(db, kullanici_id, tavan=tavan)
    if bekle is None:
        return
    raise HTTPException(status_code=429,
                        detail=i18n.t("err.saatlik_is_tavani", dil.aktif(), tavan=tavan,
                                      dakika=max(1, -(-bekle // 60))),
                        headers={"Retry-After": str(bekle)})


def check_gunluk(db: Session, kullanici: Kullanici, kredi_tahmini: int, anahtar_kaynagi: str | None,
                 ) -> None:
    """Günlük kredi tavanı — YALNIZ platform anahtarıyla koşacak iş için.

    Kullanıcının kendi anahtarı (`"kullanici"`) hiç sayılmaz ve sayaca
    girmez; tavan `kullanicilar.gunluk_kredi_tavani` (varsa) ya da ortam.
    Toplam + yeni tahmin > tavan → 429; gövde kalanı ve pencerenin açılış
    saatini söyler, `Retry-After` en eski sayılan işin düşüşü. Sayılan iş
    yokken tek başına tavanı aşan bir tahmin de 429 — o zaman "pencere"
    yok, cümle yine kalanı söyler ve `Retry-After` 1 saattir (yeniden
    denemek işe yaramaz, kullanıcının küçük bir iş seçmesi gerekir).
    """
    if anahtar_kaynagi != "platform":
        return
    tavan = (kullanici.gunluk_kredi_tavani if kullanici.gunluk_kredi_tavani is not None
             else gunluk_kredi_tavani())
    an = zaman.an()
    toplam, en_eski = gunluk_durum(db, kullanici.id, an)
    if toplam + kredi_tahmini <= tavan:
        return
    kalan = max(0, tavan - toplam)
    if en_eski is not None:
        bekle = _bekleme_sn(en_eski, GUNLUK_PENCERE, an)
        acilis = zaman.damga(en_eski + GUNLUK_PENCERE)
    else:
        bekle = int(SAATLIK_PENCERE.total_seconds())
        acilis = zaman.damga(an)
    raise HTTPException(status_code=429,
                        detail=i18n.t("err.gunluk_kredi_tavani", dil.aktif(), tavan=tavan,
                                      kalan=kalan, tahmin=kredi_tahmini,
                                      saat=acilis[11:16], tarih=acilis[:10]),
                        headers={"Retry-After": str(bekle)})
