#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Canlı bağlantının RLS'i gerçekten yediğini ölçer — sahibin dağıtım adımı (Faz 2 / 7).

    DATABASE_URL=… python tools/rls_kontrol.py [--kullanici <uuid>]

NEDEN VAR: `0006_rls` sekiz iş tablosuna politika + `FORCE ROW LEVEL SECURITY`
koyuyor, ama FORCE süper kullanıcıyı ve `BYPASSRLS` rolünü KAPSAMAZ. Yani şema
doğru, göç yeşil, takım yeşil olabilir ve canlıda yalıtımın ikinci katı yine
sessizce kapalı olabilir — tek belirleyici, `DATABASE_URL`deki rolün kim
olduğudur. Bunu CI ölçemez (canlı bağlantı orada yok) ve takım ölçemez (test
kümesi süper kullanıcıyla koşuyor; yalıtım orada ikinci bir rolle ölçülüyor,
tests/test_rls.py). Geriye sahibin tek seferlik adımı kalıyor; bu betik o adımı
elle yazılmış iki `psql` satırı olmaktan çıkarıp kapıya çeviriyor.

ÖLÇÜLDÜ (2026-09-18, Railway, PostgreSQL 18.6): servisin kutudan verdiği
`postgres` rolü `rolsuper = t` VE `rolbypassrls = t`. Yönetilen sağlayıcının
öntanımlı rolünün temiz olduğu VARSAYILAMAZ; KURULUM.md'nin ayrı rol yolu
orada zorunlu (`tools/uygulama_rolu.py`).

BOŞ TABLO TUZAĞI: "bağlamsız `count(*)` → 0" kapısı taze bir veri tabanında
KENDİLİĞİNDEN yeşil olur, çünkü sayılacak satır yoktur — süper kullanıcıyla
bile. Aynı gün buna düşüldü (Railway'in boş DB'sinde o kapı yeşildi ve hiçbir
şey söylemiyordu). Bu yüzden `--kullanici` verilmezse sonuç ZAYIF damgasıyla
basılır: kanıt, satırı OLAN bir tabloda bağlamsız 0 ile bağlamlı n'in birlikte
görülmesidir.

TABLO LİSTESİ ve bağlama ifadesi BURADA TEKRARLANMAZ: `services/kiraci.py`den
(`IS_TABLOLARI`, `uygula`, `YONETICI_EKLER_TABLOLARI`) gelir — göç ile aracın
ayrışması mümkün olmasın (CLAUDE.md §5; bekçisi tests/test_rls_kontrol.py).
Politika beklentisi tablo başına üç: `sahip`, `yonetici_okur`,
`yonetici_gunceller`; artı `yonetici_ekler` istisnası olan tablolarda bir —
Faz 3'ün kredi defteri (`0007_kredi`, K4) ve Faz 4'ün sipariş tablosu
(`0008_odeme`) — toplam `beklenen_politika()` (3 × 10 + 2 = 32).

ÇIKIŞ KODLARI öteki araçlarla bir: 0 tamam · 1 en az bir kapı kırmızı ·
2 ortam (`DATABASE_URL` yok, bozuk argüman ya da sunucuya ulaşılamıyor).
HİÇBİR ŞEY YAZMAZ: yalnız katalog ve sayım sorguları.
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from services import db, kiraci  # noqa: E402

CIKIS_TAMAM = 0
CIKIS_KIRMIZI = 1
CIKIS_ORTAM = 2

# Göçün her tabloya koyduğu politika sayısı: `sahip`, `yonetici_okur`, `yonetici_gunceller`.
POLITIKA_SAYISI = 3


def beklenen_politika() -> int:
    """Bütün iş tablolarında beklenen politika: 3 × tablo + admin INSERT istisnası olan tablo sayısı (Faz 3 / 1, Faz 4 / 2)."""
    return POLITIKA_SAYISI * len(kiraci.IS_TABLOLARI) + len(kiraci.YONETICI_EKLER_TABLOLARI)


def _kapi(ad: str, gecti: bool, ayrinti: str) -> bool:
    """Tek satırlık rapor; dönen değer kapının kendisi (çağıran biriktirir)."""
    print(f"  [{'OK ' if gecti else 'RED'}] {ad}: {ayrinti}")
    return gecti


def olc(baglanti, tablo: str, kullanici: uuid.UUID | None) -> tuple[bool, bool]:
    """Kapıları koşar; `(hepsi_yesil, zayif)`. `zayif`: bağlamsız 0 tohumla desteklenmedi."""
    rol, veritabani = baglanti.execute(text("SELECT current_user, current_database()")).one()
    print(f"rol={rol}  veritabani={veritabani}\n")

    yesil: list[bool] = []
    super_mu, bypass_mi = baglanti.execute(text(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
    yesil.append(_kapi("rolsuper", not super_mu, f"{'t' if super_mu else 'f'} (beklenen f)"))
    yesil.append(_kapi("rolbypassrls", not bypass_mi, f"{'t' if bypass_mi else 'f'} (beklenen f)"))

    # Nitelik `current_user`da yoksa bile rol ÜYELİKLE alınabilir: `SET ROLE` ile
    # ulaşılan atlayıcı bir rol, iki satır yukarıdaki "f | f"yi anlamsız kılar.
    uyelikler = [a for (a,) in baglanti.execute(text(
        "SELECT rolname FROM pg_roles WHERE (rolsuper OR rolbypassrls) "
        "AND rolname <> current_user AND pg_has_role(current_user, oid, 'MEMBER')"))]
    yesil.append(_kapi("uyelik", not uyelikler,
                       "yok" if not uyelikler else f"SET ROLE ile atlanabilir: {uyelikler}"))

    durum = {ad: (rls, force) for ad, rls, force in baglanti.execute(
        text("SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
             "WHERE relname = ANY(:t) AND relkind = 'r'"), {"t": list(kiraci.IS_TABLOLARI)})}
    eksik = [t for t in kiraci.IS_TABLOLARI if durum.get(t) != (True, True)]
    yesil.append(_kapi("ENABLE+FORCE", not eksik,
                       f"{len(kiraci.IS_TABLOLARI) - len(eksik)}/{len(kiraci.IS_TABLOLARI)} tablo"
                       + (f" - eksik: {eksik}" if eksik else "")))

    beklenen = beklenen_politika()
    politika = baglanti.execute(text("SELECT count(*) FROM pg_policies WHERE tablename = ANY(:t)"),
                                {"t": list(kiraci.IS_TABLOLARI)}).scalar_one()
    yesil.append(_kapi("politika", politika == beklenen, f"{politika}/{beklenen}"))

    # `tablo` argparse `choices` ile IS_TABLOLARI'na kısıtlı: dizeyi biçimlemek güvenli.
    bagsiz = baglanti.execute(text(f"SELECT count(*) FROM {tablo}")).scalar_one()
    yesil.append(_kapi(f"baglamsiz {tablo}", bagsiz == 0, f"{bagsiz} satir (beklenen 0)"))

    zayif = True
    if kullanici is not None:
        # Üretimdeki İFADENİN AYNISI (`kiraci.uygula`), elle yazılmış bir
        # `set_config` değil: ayarın adı ya da biçimi değişirse burası da değişsin.
        with kiraci.baglam(kullanici_id=kullanici):
            kiraci.uygula(baglanti)
            bagli = baglanti.execute(text(f"SELECT count(*) FROM {tablo}")).scalar_one()
        zayif = bagli == 0
        print(f"  [ .. ] baglamli {tablo}: {bagli} satir (o hesabin gercek sayisi)")
    return all(yesil), zayif


def _ayristirici() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rls_kontrol.py",
        description="DATABASE_URL'deki rol RLS'i atliyor mu? Okur, yazmaz.")
    p.add_argument("--kullanici", metavar="UUID",
                   help="bir hesabin id'si: baglamli sayim da olculur (bagsiz 0'i ANLAMLI kilar)")
    p.add_argument("--tablo", default="medya", choices=kiraci.IS_TABLOLARI,
                   help="sayimin kosulacagi is tablosu (ontanimli: medya)")
    return p


def main(argv: list[str]) -> int:
    args = _ayristirici().parse_args(argv)
    kullanici: uuid.UUID | None = None
    if args.kullanici:
        try:
            kullanici = uuid.UUID(args.kullanici)
        except ValueError:
            print(f"--kullanici bir uuid degil: {args.kullanici}", file=sys.stderr)
            return CIKIS_ORTAM
    url = db.baglanti_dizesi()
    if not url:
        print(f"{db.DATABASE_URL_ENV} verilmedi: olculecek bir baglanti yok.", file=sys.stderr)
        return CIKIS_ORTAM

    motor = create_engine(url, connect_args={"connect_timeout": db.BAGLANTI_ZAMAN_ASIMI_SN})
    try:
        # Tek transaksiyon: `SET LOCAL` gücündeki bağlam ayarı ancak burada yaşar.
        with motor.begin() as baglanti:
            hepsi, zayif = olc(baglanti, args.tablo, kullanici)
    except SQLAlchemyError as hata:
        # SQLAlchemy mesajı URL'deki parolayı maskeliyor; yine de yalnız ilk satır.
        print(f"veri tabanina ulasilamiyor: {str(hata).splitlines()[0]}", file=sys.stderr)
        return CIKIS_ORTAM
    finally:
        motor.dispose()

    if not hepsi:
        print("\nSONUC: EN AZ BIR KAPI KIRMIZI - KURULUM.md'deki ayri rol yolu "
              "(tools/uygulama_rolu.py) uygulanmali.")
        return CIKIS_KIRMIZI
    print("\nSONUC: rol RLS'i ATLAMIYOR." + (
        "  (ZAYIF: bagsiz 0 tohumsuz olculdu - --kullanici ile bagli sayimi da goster)"
        if zayif else ""))
    return CIKIS_TAMAM


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
