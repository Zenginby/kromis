#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Aylık Polar mutabakatı: Polar'ın ödenmiş siparişleri ↔ bizim `siparisler` tablomuz, farkı CSV'ye döker (Faz 4 / 7, K4).

    DATABASE_URL=… KROMIS_POLAR_ERISIM_JETONU=… python tools/polar_mutabakat.py                       # geçen ay, stdout
    DATABASE_URL=… KROMIS_POLAR_ERISIM_JETONU=… python tools/polar_mutabakat.py --ay 2026-10 --cikti fark.csv
    …; echo $?    # 0 = sıfır fark · 2 = fark var · 3 = ortam/sağlayıcı hatası

NEDEN VAR: para Polar'da tahsil edilir, bizde yalnız webhook'un yazdığı
sipariş satırı vardır (`services/odeme.py`, K4 üç katman). Webhook kaçarsa
(uç 500 verdi ve Polar denemeyi bıraktı, sır yanlıştı, uç kapalıydı) kullanıcı
ödemiş ama kredisi yatmamıştır — bunu kullanıcının şikâyetinden önce görmenin
tek yolu Polar'ın listesini bizimkiyle yan yana koymaktır. `tools/marj_raporu.py`
giderin (sağlayıcı faturası), bu araç gelirin (Polar payout) yanına konur;
sahip ayda bir ikisini birlikte koşar (docs/isletme.md § 9, KURULUM.md 11).

İKİ YÖN, İKİ ÖNERİ (CSV `yon` sütunu):

* `polar_eksik` — Polar'da ödenmiş, bizde satırı YOK: webhook kaçtı. Öneri:
  Polar panelinden o siparişin `order.paid` olayını yeniden gönder (`webhook_id`
  yeni de olsa defter anahtarı `paket:<order_id>` / sipariş kimliği tek kredi
  yazar — K4). Olay `hata=urun_yok` ile bekliyorsa önce `polar_esitle.py`.
* `bizde_fazla` — bizde satır var, Polar'ın ödenmiş listesinde YOK: OLMAMALI
  (satırı yalnız Polar'ın imzalı olayı yazar). Öneri: incele — sandbox olayı
  production DB'ye mi yazılmış (`KROMIS_POLAR_ORTAM` karışmış), Polar'da sipariş
  iade/void olmuş mu (`order.refunded` yalnız WARNING düşürür, satır durur — o
  hâlde kredi iadesi admin `duzelt` kararı, K6), yoksa gerçekten yabancı bir olay mı.

DÖNEM: `--ay YYYY-MM` (öntanımlı GEÇEN ay — araç ay başında koşulur, payout o
ayın), UTC takvim ayı. Polar tarafı `created_at`, bizim taraf `olusturuldu`
(webhook'un işlediği an, saniyeler-dakikalar sonra). Ay SINIRINDA iki damga
farklı aya düşebilir; bu yüzden Polar listesi bir gün PAYLA çekilir
(`PAY = 1 gün`) ve iki yön böyle ölçülür: `polar_eksik` = dönemdeki Polar
siparişi, kimliği bizde HİÇ yok (tarihe bakılmaz — geç işlenen sipariş eksik
sayılmaz); `bizde_fazla` = dönemdeki bizim satır, kimliği Polar'ın PAYLI
listesinde yok. Pay dışına kayan bir satır ancak webhook günler geciktiyse
görünür — o zaman zaten incelenmeli.

ÖDENMİŞ = `paid` alanı doğru (SDK `Order.paid`); iade edilmiş sipariş de
ödenmiştir (`status` `refunded`/`partially_refunded` — satır bizde durur, K6).
`pending`/`draft`/`void` sipariş tabloya girmez ve girmemesi doğru (webhook
`order.paid` ancak ödemede gelir).

ADMİN BAĞLAMI `kiraci.baglam(rol=ADMIN)`: `siparisler` RLS'li iş tablosu
(`yonetici_okur`); bağlamsız sorgu sızmaz, sessizce BOŞ döner ve her sipariş
"polar_eksik" görünürdü (tests/test_admin.py'nin ölçtüğü kırılma sınıfı).
`marj_raporu.py` deseni: motor `services.db.motor_kur`, uygulama ayakta
olmadan; imajda (`OPERATOR_ARACLARI`), sahip konteynerin içinden koşar (jeton
web sürecinin ortamında zaten var). Polar'a `services.polar.siparisleri_listele`
ile çıkılır — testler o dikişi yamalar, gerçek ağ çağrısı yok.

ÇIKIŞ KODLARI: 0 sıfır fark · 2 fark var (CSV'de satır) · 3 ortam/sağlayıcı
hatası (`DATABASE_URL`/jeton yok, Polar'a ulaşılamadı, DB hatası, bozuk `--ay`).
`polar_esitle --kontrol`ün 0/2 kuralı; 3 AYRI çünkü cron "Polar'a ulaşamadım"
ile "fark buldum"u ayırmalı — ikincisi sahibi çağırır, birincisi yeniden dener.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import sys
from collections.abc import Iterable, Mapping
from typing import IO, Any

# Betik olarak koşarken kök modüller görünmez (`tools/kullanici.py`nin deyimi).
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from services import db, kiraci, polar, zaman  # noqa: E402
from services.tablolar import Siparis  # noqa: E402

CIKIS_TAMAM = 0
CIKIS_FARK = 2
CIKIS_ORTAM = 3

YON_POLAR_EKSIK = "polar_eksik"
YON_BIZDE_FAZLA = "bizde_fazla"
ONERI = {
    YON_POLAR_EKSIK: "webhook kacti: Polar panelinden order.paid olayini yeniden gonder (urun aynasi eksikse once polar_esitle)",
    YON_BIZDE_FAZLA: "olmamali: satiri yalniz Polar'in imzali olayi yazar - ortam karisikligi (sandbox/production), iade/void ya da yabanci olay; incele",
}
# Başlık satırı aynen (bekçisi tests/test_araclar.py).
SUTUNLAR = ("yon", "siparis_id", "olusturuldu", "tutar_kurus", "para_birimi", "musteri", "urun", "oneri")
# Ay sınırı payı (gerekçe modül başında): Polar `created_at` ↔ bizim `olusturuldu`.
PAY = dt.timedelta(days=1)
_AY_BICIMI = re.compile(r"^(\d{4})-(\d{2})$")


def donem(ay: str | None, an: dt.datetime | None = None) -> tuple[dt.datetime, dt.datetime, str]:
    """`--ay YYYY-MM` → `[baslangic, bitis)` UTC ve etiket; `None` = GEÇEN ay (`an`a göre). Bozuk biçim/ay → `ValueError`."""
    if ay is None:
        simdi = an if an is not None else zaman.an()
        ilk = simdi.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        onceki = (ilk - dt.timedelta(days=1)).replace(day=1)
        return onceki, ilk, onceki.strftime("%Y-%m")
    eslesme = _AY_BICIMI.match(ay.strip())
    if eslesme is None:
        raise ValueError(f"--ay YYYY-MM olmali, verilen: {ay!r}")
    yil, ay_no = int(eslesme.group(1)), int(eslesme.group(2))
    if not 1 <= ay_no <= 12:
        raise ValueError(f"--ay ayi 01-12 olmali, verilen: {ay!r}")
    baslangic = dt.datetime(yil, ay_no, 1, tzinfo=dt.UTC)
    bitis = dt.datetime(yil + (ay_no == 12), 1 if ay_no == 12 else ay_no + 1, 1, tzinfo=dt.UTC)
    return baslangic, bitis, f"{yil:04d}-{ay_no:02d}"


def odenmis(siparis: Mapping[str, Any]) -> bool:
    """Polar siparişi ödenmiş mi: `paid` doğru (iade edilmiş de ödenmişti); alan yoksa `status`a bakılır."""
    paid = siparis.get("paid")
    if isinstance(paid, bool):
        return paid
    return siparis.get("status") in ("paid", "refunded", "partially_refunded")


def _polar_zaman(siparis: Mapping[str, Any]) -> dt.datetime | None:
    return polar._zaman(siparis.get("created_at"))


def _polar_musteri(siparis: Mapping[str, Any]) -> str:
    """`customer.external_id` = bizim `kullanicilar.id` (webhook'un çözüm yolu); yoksa Polar müşteri kimliği."""
    musteri = siparis.get("customer")
    dis = musteri.get("external_id") if isinstance(musteri, Mapping) else None
    if isinstance(dis, str) and dis:
        return dis
    kimlik = siparis.get("customer_id")
    return str(kimlik) if kimlik else ""


def _polar_satiri(siparis: Mapping[str, Any]) -> dict[str, Any]:
    t = _polar_zaman(siparis)
    tutar = siparis.get("total_amount")
    return {"yon": YON_POLAR_EKSIK, "siparis_id": str(siparis.get("id") or ""),
            "olusturuldu": zaman.damga_utc(t) if t is not None else "",
            "tutar_kurus": tutar if isinstance(tutar, int) and not isinstance(tutar, bool) else "",
            "para_birimi": str(siparis.get("currency") or ""), "musteri": _polar_musteri(siparis),
            "urun": str(siparis.get("product_id") or ""), "oneri": ONERI[YON_POLAR_EKSIK]}


def _bizim_satir(s: Siparis) -> dict[str, Any]:
    return {"yon": YON_BIZDE_FAZLA, "siparis_id": s.polar_siparis_id, "olusturuldu": zaman.damga_utc(s.olusturuldu),
            "tutar_kurus": s.tutar_kurus, "para_birimi": s.para_birimi, "musteri": str(s.kullanici_id),
            "urun": str(s.urun_id), "oneri": ONERI[YON_BIZDE_FAZLA]}


def farklar(oturum: Session, polar_siparisleri: Iterable[Mapping[str, Any]],
            baslangic: dt.datetime, bitis: dt.datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Polar listesi (PAYLI dönem, ödenmiş/ödenmemiş karışık) ↔ `siparisler` → (fark satırları, özet sayılar).

    Ölçüm iki yönde farklı kümeyle (gerekçe modül başında): `polar_eksik` için
    bizim taraf KİMLİK kümesi tarihsiz (geç işlenen sipariş eksik değildir),
    `bizde_fazla` için Polar tarafı paylı listenin tamamı. Özet: dönemdeki
    ödenmiş Polar siparişi ve toplamı, dönemdeki bizim satır ve toplamı
    (para birimi ayrımı yapılmaz — payout'la yan yana okunur; karma birim
    `tutar_kurus` sütunundan görünür).
    """
    polar_odenmis = {str(s["id"]): s for s in polar_siparisleri if odenmis(s) and s.get("id")}
    donemdeki_polar = {k: s for k, s in polar_odenmis.items()
                       if (t := _polar_zaman(s)) is not None and baslangic <= t < bitis}
    bizim_kimlikler = set(oturum.scalars(select(Siparis.polar_siparis_id)))
    bizdekiler = list(oturum.scalars(select(Siparis).where(Siparis.olusturuldu >= baslangic,
                                                             Siparis.olusturuldu < bitis)
                                     .order_by(Siparis.olusturuldu, Siparis.id)))
    satirlar = [_polar_satiri(s) for k, s in sorted(donemdeki_polar.items(), key=lambda ks: (_polar_zaman(ks[1]) or bitis, ks[0]))
                if k not in bizim_kimlikler]
    satirlar += [_bizim_satir(s) for s in bizdekiler if s.polar_siparis_id not in polar_odenmis]
    ozet = {
        "polar_siparis": len(donemdeki_polar),
        "polar_kurus": sum(s.get("total_amount") or 0 for s in donemdeki_polar.values()
                           if isinstance(s.get("total_amount"), int)),
        "bizim_siparis": len(bizdekiler),
        "bizim_kurus": sum(s.tutar_kurus for s in bizdekiler),
        "polar_eksik": sum(1 for r in satirlar if r["yon"] == YON_POLAR_EKSIK),
        "bizde_fazla": sum(1 for r in satirlar if r["yon"] == YON_BIZDE_FAZLA),
    }
    return satirlar, ozet


def yaz(satirlar: Iterable[dict[str, Any]], hedef: IO[str]) -> int:
    """Satırları CSV olarak `hedef`e yazar (başlık her zaman — sıfır farkta da dosya okunur); yazılan satır sayısı."""
    yazici = csv.DictWriter(hedef, fieldnames=SUTUNLAR, extrasaction="ignore", lineterminator="\n")
    yazici.writeheader()
    sayi = 0
    for satir in satirlar:
        yazici.writerow(satir)
        sayi += 1
    return sayi


def _ayristirici() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="polar_mutabakat.py",
        description="Polar'in odenmis siparisleri ile `siparisler` tablosunun aylik farkini CSV'ye dok "
                    "(DATABASE_URL + KROMIS_POLAR_ERISIM_JETONU ile).")
    p.add_argument("--ay", default=None, help="donem, YYYY-MM (UTC takvim ayi); ontanimli GECEN ay")
    p.add_argument("--cikti", default="-", help="CSV dosyasi; '-' (ontanimli) standart cikti")
    return p


def main(argv: list[str]) -> int:
    args = _ayristirici().parse_args(argv)
    try:
        baslangic, bitis, etiket = donem(args.ay)
    except ValueError as hata:
        print(str(hata), file=sys.stderr)
        return CIKIS_ORTAM
    url = db.baglanti_dizesi()
    if not url:
        print(f"{db.DATABASE_URL_ENV} verilmedi: bu arac veri tabanina baglanir.", file=sys.stderr)
        return CIKIS_ORTAM
    if not polar.erisim_jetonu():
        print(f"{polar.JETON_ENV} verilmedi: bu arac Polar'a baglanir ({polar.ortam()}).", file=sys.stderr)
        return CIKIS_ORTAM
    try:
        polar_siparisleri = polar.siparisleri_listele(baslangic - PAY, bitis + PAY)
    except Exception as hata:   # noqa: BLE001 — SDK'nın istisna ailesi ve ağ; sınıf adı + ilk satır yeter
        print(f"Polar hatasi ({type(hata).__name__}): {str(hata).splitlines()[0] if str(hata) else ''}",
              file=sys.stderr)
        return CIKIS_ORTAM
    motor = db.motor_kur(url)
    try:
        with kiraci.baglam(rol=kiraci.ADMIN), Session(motor) as oturum:
            satirlar, ozet = farklar(oturum, polar_siparisleri, baslangic, bitis)
        if args.cikti == "-":
            yaz(satirlar, sys.stdout)
        else:
            # `newline=""`: csv modülü satır sonunu kendi yazar; Windows'ta çift `\\r` olmasın.
            with open(args.cikti, "w", encoding="utf-8", newline="") as f:
                yaz(satirlar, f)
        print(f"{etiket} ({polar.ortam()}): Polar {ozet['polar_siparis']} odenmis siparis "
              f"{ozet['polar_kurus'] / 100:.2f} · bizde {ozet['bizim_siparis']} satir {ozet['bizim_kurus'] / 100:.2f} · "
              f"Polar'da olup bizde olmayan {ozet['polar_eksik']} · bizde olup Polar'da olmayan {ozet['bizde_fazla']}"
              + (f" → {args.cikti}" if args.cikti != "-" else ""), file=sys.stderr)
    except SQLAlchemyError as hata:
        # Bağlantı dizesinde parola olabilir; yalnız sınıf adı ve ilk satır (`kullanici.py`nin kararı).
        print(f"veri tabani hatasi ({type(hata).__name__}): {str(hata).splitlines()[0]}", file=sys.stderr)
        return CIKIS_ORTAM
    finally:
        motor.dispose()
    return CIKIS_FARK if satirlar else CIKIS_TAMAM


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
