#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Tarife–maliyet (marj) raporunu CSV'ye döker — admin "Marj" tablosunun aynı sorgusu (Faz 3 / 5).

    DATABASE_URL=… python tools/marj_raporu.py --gun 30 --cikti marj.csv
    DATABASE_URL=… python tools/marj_raporu.py --gun 7            # stdout

NEDEN VAR: admin sayfası son 7/30 günü gösterir, sahip ise ayda bir
sağlayıcının faturasını (fal, Azure) bir hesap tablosunda yan yana koyar.
Aynı sayıyı ekrandan kopyalamak yerine `services/depo_admin.marj` doğrudan
CSV'ye yazılır — tek sorgu, iki yüz; ekran ile dosya birbirinden sapmaz.

SÜTUNLAR (`SUTUNLAR`; başlık satırı aynen): `gun` pencere, `model`, `adet`
biten iş, `kredi` Σ gerçek kredi, `usd` kredi × çapa (tarifemizin USD
karşılığı), `maliyet_usd` Σ sağlayıcı USD (yalnız dolu satırlar, hiç yoksa
BOŞ hücre — sıfır DEĞİL: bilinmeyen maliyet sıfır maliyet değil),
`maliyet_bilinen` kaç satır dolu, `ort_sure_sn`, `hata`, `hata_kredi` (düşen
işlerin tahmini — K8 zararı). Marj farkını hesap tablosu çıkarır.

ADMİN BAĞLAMI `kiraci.baglam(rol=ADMIN)`: `isler` RLS altında (`0006_rls`) ve
bu araç uygulama rolüyle bağlanan bir `DATABASE_URL` ile de koşabilmeli —
bağlamsız sorgu sızmaz, sessizce BOŞ döner (tests/test_admin.py'nin ölçtüğü
kırılma sınıfı). `tools/kullanici.py` deseni: motor `services.db.motor_kur`,
uygulama ayakta olmadan çalışır.

ÇIKIŞ KODLARI: 0 tamam · 2 ortam hatası (`DATABASE_URL` yok, sunucuya
ulaşılamıyor). Kullanıcı hatası sınıfı yok: `--gun` argparse'ın elinde.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections.abc import Iterable
from typing import IO, Any

# Betik olarak koşarken kök modüller görünmez (`tools/kullanici.py`nin deyimi).
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from services import db, depo_admin, kiraci  # noqa: E402

CIKIS_TAMAM = 0
CIKIS_ORTAM = 2

# Başlık satırı: `depo_admin.marj` satırının anahtarları, bu sırayla (bekçisi tests/test_araclar.py).
SUTUNLAR = ("gun", "model", "adet", "kredi", "usd", "maliyet_usd", "maliyet_bilinen",
            "ort_sure_sn", "hata", "hata_kredi")


def yaz(satirlar: Iterable[dict[str, Any]], hedef: IO[str]) -> int:
    """Satırları CSV olarak `hedef`e yazar; yazılan satır sayısı. `None` boş hücre olur (csv'nin öntanımı)."""
    yazici = csv.DictWriter(hedef, fieldnames=SUTUNLAR, extrasaction="ignore", lineterminator="\n")
    yazici.writeheader()
    sayi = 0
    for satir in satirlar:
        yazici.writerow(satir)
        sayi += 1
    return sayi


def _ayristirici() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="marj_raporu.py",
        description="Kromis web: model basina tarife-maliyet satirlarini CSV'ye dok (DATABASE_URL ile).")
    p.add_argument("--gun", type=int, default=30, help="pencere (gun); ontanimli 30")
    p.add_argument("--cikti", default="-", help="CSV dosyasi; '-' (ontanimli) standart cikti")
    return p


def main(argv: list[str]) -> int:
    args = _ayristirici().parse_args(argv)
    if args.gun < 1:
        print("--gun en az 1 olmali.", file=sys.stderr)
        return CIKIS_ORTAM
    url = db.baglanti_dizesi()
    if not url:
        print(f"{db.DATABASE_URL_ENV} verilmedi: bu arac veri tabanina baglanir.", file=sys.stderr)
        return CIKIS_ORTAM
    motor = db.motor_kur(url)
    try:
        with kiraci.baglam(rol=kiraci.ADMIN), Session(motor) as oturum:
            satirlar = depo_admin.marj(oturum, args.gun)
        if args.cikti == "-":
            sayi = yaz(satirlar, sys.stdout)
        else:
            # `newline=""`: csv modülü satır sonunu kendi yazar; Windows'ta çift `\r` olmasın.
            with open(args.cikti, "w", encoding="utf-8", newline="") as f:
                sayi = yaz(satirlar, f)
            print(f"{args.cikti}: {sayi} satir ({args.gun} gun)", file=sys.stderr)
    except SQLAlchemyError as hata:
        # Bağlantı dizesinde parola olabilir; yalnız sınıf adı ve ilk satır (`kullanici.py`nin kararı).
        print(f"veri tabani hatasi ({type(hata).__name__}): {str(hata).splitlines()[0]}",
              file=sys.stderr)
        return CIKIS_ORTAM
    finally:
        motor.dispose()
    return CIKIS_TAMAM


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
