#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""`KROMIS_SECRET_KEY` döndürme — BÜTÜN kullanıcıların satırlarını yeni anahtara taşır (Faz 1 / 9).

    DATABASE_URL=… KROMIS_SECRET_KEY="yeni,eski" python tools/anahtar_dondur.py --kuru
    DATABASE_URL=… KROMIS_SECRET_KEY="yeni,eski" python tools/anahtar_dondur.py

NEDEN VAR: 7. görev döndürmeyi KULLANICI BAŞINA verdi
(`depo_kimlik_bilgisi.dondur(db, kullanici_id)`) ve toplu sarmalayıcıyı bu
göreve bıraktı. Onsuz döndürme akışı KAPANMAZ: yeni anahtar listenin başına
konup dağıtıldıktan sonra eski anahtar ancak HER satır yeniden şifrelendiyse
düşürülebilir; bir kullanıcının satırı eski anahtarda kalırsa o kullanıcı
Ayarlar'ı açtığında `SifreHatasi` görür. Akışın tamamı docs/isletme.md'de.

NE YAPAR: `saglayici_kimlikleri`nde satırı olan her kullanıcı için `dondur`
çağırır (düz metni bu sürece AÇMAZ — `MultiFernet.rotate`), sonda parmak izi
başına kaç satır kaldığını basar. İdempotent: her satır güncelse 0 satır döner.
`--kuru` yalnız sayar. Uygulama AÇIKKEN de koşabilir: yazan taraf hep ilk
anahtarla yazıyor, okuyan taraf listedeki hepsini deniyor; yarım kalmış bir
döndürme kimseyi kilitlemez, yalnız eski anahtarın düşürülmesini erteler.

ÇIKIŞ KODLARI öteki araçlarla bir: 0 tamam · 1 bir satır listedeki HİÇBİR
anahtarla çözülemedi (eski anahtarı listenin SONUNA ekleyip yeniden koşun;
hiçbir şey yazılmadı) · 2 ortam (`DATABASE_URL`/`KROMIS_SECRET_KEY` yok ya da
bozuk, sunucuya ulaşılamıyor).
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections import Counter

# Betik olarak koşarken (`python tools/anahtar_dondur.py`) `sys.path[0]` bu
# dizin ve kök modüller görünmez; testler `tools.anahtar_dondur` diye ithal ediyor.
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from services import db, depo_kimlik_bilgisi, kiraci, sifre  # noqa: E402
from services.tablolar import SaglayiciKimligi  # noqa: E402

CIKIS_TAMAM = 0
CIKIS_KULLANICI = 1
CIKIS_ORTAM = 2


def surum_dagilimi(oturum: Session) -> Counter[int]:
    """{anahtar_surumu (parmak izi): satır sayısı} — bütün kullanıcılar."""
    satirlar = oturum.execute(select(SaglayiciKimligi.anahtar_surumu, func.count())
                              .group_by(SaglayiciKimligi.anahtar_surumu))
    return Counter({int(surum): int(sayi) for surum, sayi in satirlar})


def bekleyen_kullanicilar(oturum: Session, guncel: int) -> list[uuid.UUID]:
    """Güncel olmayan en az bir satırı olan kullanıcılar."""
    return list(oturum.scalars(select(SaglayiciKimligi.kullanici_id).distinct()
                               .where(SaglayiciKimligi.anahtar_surumu != guncel)
                               .order_by(SaglayiciKimligi.kullanici_id)))


def dondur_hepsini(oturum: Session, *, kuru: bool) -> dict[uuid.UUID, int]:
    """Her bekleyen kullanıcı için `dondur`; {kullanıcı: döndürülen satır}. Kuru koşuda yalnız sayar."""
    s = sifre.sifreci()
    sonuc: dict[uuid.UUID, int] = {}
    for kid in bekleyen_kullanicilar(oturum, s.surum):
        if kuru:
            sonuc[kid] = int(oturum.scalar(
                select(func.count()).select_from(SaglayiciKimligi)
                .where(SaglayiciKimligi.kullanici_id == kid,
                       SaglayiciKimligi.anahtar_surumu != s.surum)) or 0)
        else:
            sonuc[kid] = depo_kimlik_bilgisi.dondur(oturum, kid)
    return sonuc


def _ayristirici() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="anahtar_dondur.py",
        description="KROMIS_SECRET_KEY listesinin ILK anahtariyla yazilmamis her satiri yeniden sifreler "
                    "(butun kullanicilar). DATABASE_URL + KROMIS_SECRET_KEY='yeni,eski' ile.")
    p.add_argument("--kuru", action="store_true", help="yalnizca say, hicbir sey yazma")
    return p


def main(argv: list[str]) -> int:
    args = _ayristirici().parse_args(argv)
    url = db.baglanti_dizesi()
    if not url:
        print(f"{db.DATABASE_URL_ENV} verilmedi: bu arac veri tabanina baglanir.", file=sys.stderr)
        return CIKIS_ORTAM
    try:
        s = sifre.sifreci()
    except sifre.AnahtarHatasi as hata:
        print(str(hata), file=sys.stderr)
        return CIKIS_ORTAM
    print(f"guncel anahtar (parmak izi): {s.surum}; listede {len(s.surumler)} anahtar")

    motor = db.motor_kur(url)
    try:
        # `app.rol = 'admin'` (RLS, Faz 2 / 7): döndürme HER kullanıcının
        # `saglayici_kimlikleri` satırını okur ve GÜNCELLER — admin politikasının
        # verdiği iki şey tam bunlar; bağlamsız oturum 0 satır görüp "hepsi güncel" derdi.
        with kiraci.baglam(rol=kiraci.ADMIN), Session(motor) as oturum:
            once = surum_dagilimi(oturum)
            sonuc = dondur_hepsini(oturum, kuru=args.kuru)
            if args.kuru:
                oturum.rollback()
            else:
                oturum.commit()
            sonra = surum_dagilimi(oturum)
    except sifre.SifreHatasi as hata:
        print(f"{hata}\nHicbir sey yazilmadi.", file=sys.stderr)
        return CIKIS_KULLANICI
    except SQLAlchemyError as hata:
        print(f"veri tabani hatasi ({type(hata).__name__}): {str(hata).splitlines()[0]}", file=sys.stderr)
        return CIKIS_ORTAM
    finally:
        motor.dispose()

    for kid, sayi in sonuc.items():
        print(f"{kid}: {sayi} satir {'dondurulecek' if args.kuru else 'donduruldu'}")
    print(f"toplam: {sum(sonuc.values())} satir, {len(sonuc)} kullanici"
          f"{' (kuru kosu, yazilmadi)' if args.kuru else ''}")
    dagilim = once if args.kuru else sonra
    for surum, sayi in sorted(dagilim.items()):
        print(f"parmak izi {surum}: {sayi} satir{' (guncel)' if surum == s.surum else ' (ESKI anahtar)'}")
    if not args.kuru and any(surum != s.surum for surum in sonra):
        print("eski anahtarla yazilmis satir kaldi; eski anahtari listeden DUSURMEYIN.", file=sys.stderr)
    return CIKIS_TAMAM


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
