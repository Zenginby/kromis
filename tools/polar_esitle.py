#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Polar ürün kataloğunu `urunler` aynasına yazar — fiyat listesinin ve webhook eşlemesinin tek kaynağı (Faz 4 / 4, K5).

    DATABASE_URL=… KROMIS_POLAR_ERISIM_JETONU=… python tools/polar_esitle.py            # yazar
    DATABASE_URL=… KROMIS_POLAR_ERISIM_JETONU=… python tools/polar_esitle.py --kontrol  # yalnız farkı basar

NEDEN VAR: fiyatın gerçek sahibi Polar (MoR onu tahsil eder); bizde tablo
değil AYNA (`services/tablolar.Urun`, belge K5). Webhook `order.paid`
`product_id`sini bu aynada arar (`services/odeme.urun_bul`): satır yoksa
para YATMAZ, olay `hata=urun_yok` ile bekler ve sahip bu aracı koşar,
Polar panelinden olayı yeniden gönderir. Satış sayfası (`/planlar`) da
fiyatı buradan gösterir — sahip Polar'da fiyat değiştirip bu aracı
koşmazsa sayfa bayat fiyat gösterir (ödeme yine Polar'ın doğru fiyatıyla);
`urunler.guncellendi` 7 günden eskiyse admin "Ödeme" sekmesi uyarır.

POLAR'DAKİ SÖZLEŞME — ürün `metadata`sı (sahip panelde yazar):

    kromis_tur    plan | paket           (zorunlu)
    kromis_plan   temel | pro            (yalnız plan; `PLANLAR`dan)
    kromis_kredi  tam sayı               (paket: yüklenen kredi; plan: dönem hibesi — bilgi,
                                          kural `services/planlar.py`de)

Metadata'sı eksik/bozuk ürün ATLANIR ve WARNING basılır (`URUN ATLANDI`):
Polar'da başka amaçla duran bir ürün (bağış, eski deneme) aynaya sızmasın,
ama sahip yazım hatasını görsün. KADANS da doğrulanır: `plan` ürünü
AYLIK abonelik olmalı (`recurring_interval == "month"` — `subscription.*`
olayları ve K6'nın "dönem hibesi" aritmetiği aylık döneme göre yazıldı,
yıllık plan ilk sürümde yok), `paket` TEK SEFERLİK olmalı (abonelik
sebebiyle gelen paket webhook'ta `urun_sebep_uyumsuz` ile para yatırmazdı —
hata aynaya girmeden burada görünür). Fiyat ürünün ilk arşivlenmemiş sabit
fiyatından (`prices[].amount_type == "fixed"`): planda AYLIK olan seçilir
(eski "legacy" ürünlerde yıllık + aylık iki fiyat yan yana durabilir),
pakette tek seferlik. Sabit fiyatı olmayan ürün (`custom`/`metered`/
`seat_based`, "pay what you want") de atlanır — satış sayfası tek fiyat
gösterir. Polar'da arşivlenen ürün `aktif=false` olur, SİLİNMEZ (eski
siparişler FK'yle ona bakar). Upsert `polar_urun_id` UNIQUE üstünden
(`INSERT … ON CONFLICT DO UPDATE`), `guncellendi` her koşuda ilerler.

BAYAT SATIRLAR DA KAPANIR: aynada olup Polar'ın GEÇERLİ kümesinde olmayan
her satır `aktif=false` yapılır — Polar'da silinmiş ürün ve geçersizleşmiş
ürün (metadata yazım hatası, fiyatı kaldırılmış) aynı kapıdan. Aksi hâlde
sahip Polar'da bir ürünü bozduğunda ayna onu satmaya devam eder, checkout
Polar'da düşer. Kapanan satırlar `- <id>` ile basılır, `--kontrol` fark sayar.

ARŞİVLİLER AÇIKÇA ÇEKİLİR: `products.list` iki kez (`is_archived=False`,
`is_archived=True`) — süzgeç verilmezse Polar'ın öntanımlısının ikisini de
döndürdüğüne güvenmek yerine ikisi de istenir; arşivli ürün gelmezse ayna
onu satışta bırakırdı.

`--kontrol`: Polar'ı okur, farkı (eklenecek / değişecek / arşivlenecek) basar,
YAZMAZ; fark varsa 2, yoksa 0 — CI değil, sahibin "ne değişecek" bakışı.

RLS'SİZ TABLO, AMA BAĞLAM YİNE KURULUR: `urunler` ALTYAPI tablosu (kullanıcı
sütunu yok, politika yok) — okumak/yazmak için kiracı bağlamı GEREKMEZ. Yine
de oturum `kiraci.baglam(rol=ADMIN)` altında açılıyor: tests/test_rls.py'nin
kaynak bekçisi "`Session(` açan her araç bağlam taşır" der ve istisna
defteri yerine kuralı sürdürmek daha ucuz — bir gün bu araç `siparisler`e de
bakarsa (RLS'li) sessizce boş dönmez. `tools/marj_raporu.py` deseni: motor
`services.db.motor_kur`, uygulama ayakta olmadan çalışır; imajda
(`OPERATOR_ARACLARI`), sahip konteynerin içinden koşar (web sürecinin
ortamında jeton zaten var).

ÇIKIŞ KODLARI: 0 tamam (ya da `--kontrol` farksız) · 2 ortam/sağlayıcı hatası
(`DATABASE_URL`/jeton yok, Polar'a ulaşılamadı, DB hatası) ya da `--kontrol`
fark buldu.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import os
import sys
from collections.abc import Iterable, Mapping
from typing import Any

# Betik olarak koşarken kök modüller görünmez (`tools/kullanici.py`nin deyimi).
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from services import db, kiraci, kuyruk, planlar, polar  # noqa: E402
from services.tablolar import URUN_TURLERI, Urun  # noqa: E402

CIKIS_TAMAM = 0
CIKIS_ORTAM = 2

META_TUR = "kromis_tur"
META_PLAN = "kromis_plan"
META_KREDI = "kromis_kredi"
URUN_PLAN, URUN_PAKET = URUN_TURLERI


@dataclasses.dataclass(frozen=True)
class Satir:
    """Aynaya yazılacak tek satır — `Urun` sütunlarının birebir karşılığı."""
    polar_urun_id: str
    tur: str
    plan: str | None
    kredi: int
    fiyat_kurus: int
    para_birimi: str
    ad: str
    aktif: bool

    def ayni(self, u: Urun) -> bool:
        return (self.tur, self.plan, self.kredi, self.fiyat_kurus, self.para_birimi, self.ad, self.aktif) == \
            (u.tur, u.plan, u.kredi, u.fiyat_kurus, u.para_birimi, u.ad, u.aktif)


@dataclasses.dataclass
class Fark:
    """`--kontrol`ün çıktısı ve yazımın özeti: eklenen, değişen, aynı kalan, atlanan (uyarı metinleri),
    kapanacak (aynada var, Polar'ın geçerli kümesinde yok — `aktif=false` olur; gerekçe modül başında)."""
    eklenen: list[Satir] = dataclasses.field(default_factory=list)
    degisen: list[Satir] = dataclasses.field(default_factory=list)
    ayni: int = 0
    atlanan: list[str] = dataclasses.field(default_factory=list)
    kapanacak: list[str] = dataclasses.field(default_factory=list)

    @property
    def var(self) -> bool:
        return bool(self.eklenen or self.degisen or self.kapanacak)


def _tam_sayi(deger: Any) -> int | None:
    """Metadata değeri `str`/`int`/`float` gelebilir (Polar üçünü de saklar); bool ve negatif geçersiz."""
    if isinstance(deger, bool):
        return None
    if isinstance(deger, int):
        return deger if deger >= 0 else None
    if isinstance(deger, float) and deger.is_integer():
        return int(deger) if deger >= 0 else None
    # `isdecimal`, `isdigit` DEĞİL: "²" `isdigit()` için doğru ama `int("²")` `ValueError` — araç çökerdi.
    if isinstance(deger, str) and deger.strip().isdecimal():
        return int(deger.strip())
    return None


AYLIK = "month"


def _fiyat_aylik_mi(f: Mapping[str, Any], urun: Mapping[str, Any]) -> bool:
    """Fiyatın kadansı: eski ("legacy") fiyatlar `recurring_interval`i kendinde taşır, yenilerde ürünün alanı."""
    aralik = f.get("recurring_interval") if f.get("legacy") else urun.get("recurring_interval")
    return aralik == AYLIK


def _ilk_sabit_fiyat(urun: Mapping[str, Any], *, aylik: bool) -> tuple[int, str] | None:
    """Ürünün ilk arşivlenmemiş `fixed` fiyatı → (`price_amount`, `price_currency`); yoksa `None`.

    `aylik=True` (plan): yalnız AYLIK kadanslı fiyat sayılır — legacy üründe
    yıllık + aylık yan yana durabilir, yıllık seçilseydi sayfa 12 katı fiyat
    gösterirdi. `aylik=False` (paket): tek seferlik ürünün fiyatı kadans taşımaz.
    """
    fiyatlar = urun.get("prices")
    if not isinstance(fiyatlar, list):
        return None
    for f in fiyatlar:
        if not isinstance(f, Mapping) or f.get("is_archived") or f.get("amount_type") != "fixed":
            continue
        if aylik and not _fiyat_aylik_mi(f, urun):
            continue
        miktar, birim = f.get("price_amount"), f.get("price_currency")
        if isinstance(miktar, int) and not isinstance(miktar, bool) and isinstance(birim, str) and birim:
            return miktar, birim.lower()
    return None


def satira_cevir(urun: Mapping[str, Any]) -> Satir | str:
    """Polar ürünü (düz sözlük) → `Satir`; geçersizse ATLAMA GEREKÇESİ (dize) — çağıran WARNING basar."""
    kimlik = urun.get("id")
    ad = urun.get("name")
    if not isinstance(kimlik, str) or not kimlik:
        return "id yok"
    if not isinstance(ad, str) or not ad.strip():
        return f"{kimlik}: ad yok"
    meta = urun.get("metadata")
    meta = meta if isinstance(meta, Mapping) else {}
    tur = meta.get(META_TUR)
    if tur not in URUN_TURLERI:
        return f"{kimlik} ({ad}): {META_TUR} eksik ya da gecersiz ({tur!r}; plan|paket)"
    plan = meta.get(META_PLAN)
    if tur == URUN_PLAN:
        if not isinstance(plan, str) or plan not in planlar.PLANLAR or plan == planlar.PLAN_VARSAYILAN:
            return f"{kimlik} ({ad}): {META_PLAN} eksik ya da gecersiz ({plan!r}; ucretli plan adi)"
    else:
        plan = None
    kredi = _tam_sayi(meta.get(META_KREDI))
    if kredi is None or (tur == URUN_PAKET and kredi <= 0):
        return f"{kimlik} ({ad}): {META_KREDI} eksik ya da gecersiz ({meta.get(META_KREDI)!r})"
    # Kadans (gerekçe modül başında): plan AYLIK abonelik, paket tek seferlik.
    tekrarli = bool(urun.get("is_recurring"))
    if tur == URUN_PLAN and not tekrarli:
        return f"{kimlik} ({ad}): plan urunu abonelik degil (is_recurring false)"
    if tur == URUN_PAKET and tekrarli:
        return f"{kimlik} ({ad}): paket urunu abonelik olamaz (is_recurring true)"
    fiyat = _ilk_sabit_fiyat(urun, aylik=tur == URUN_PLAN)
    if fiyat is None:
        return (f"{kimlik} ({ad}): sabit fiyat yok (prices[].amount_type == 'fixed'"
                + (", recurring_interval == 'month'" if tur == URUN_PLAN else "") + ")")
    return Satir(polar_urun_id=kimlik, tur=tur, plan=plan, kredi=kredi, fiyat_kurus=fiyat[0],
                 para_birimi=fiyat[1], ad=ad.strip(), aktif=not bool(urun.get("is_archived")))


def satirlara_cevir(urunler: Iterable[Mapping[str, Any]]) -> tuple[list[Satir], list[str]]:
    """Polar listesi → (geçerli satırlar, atlama gerekçeleri)."""
    satirlar: list[Satir] = []
    atlanan: list[str] = []
    for urun in urunler:
        satir = satira_cevir(urun)
        if isinstance(satir, str):
            atlanan.append(satir)
        else:
            satirlar.append(satir)
    return satirlar, atlanan


def fark_hesapla(oturum: Session, urunler: Iterable[Mapping[str, Any]]) -> Fark:
    """Polar listesi ↔ ayna: yeni / değişen / aynı; geçersizler `atlanan`da; aynada olup geçerli kümede
    olmayan AKTİF satırlar `kapanacak`ta (zaten `aktif=false` olan sayılmaz — bir kez kapanır)."""
    mevcut = {u.polar_urun_id: u for u in oturum.scalars(select(Urun))}
    satirlar, atlanan = satirlara_cevir(urunler)
    fark = Fark(atlanan=atlanan)
    for satir in satirlar:
        eski = mevcut.get(satir.polar_urun_id)
        if eski is None:
            fark.eklenen.append(satir)
        elif satir.ayni(eski):
            fark.ayni += 1
        else:
            fark.degisen.append(satir)
    gecerli = {s.polar_urun_id for s in satirlar}
    fark.kapanacak = sorted(k for k, u in mevcut.items() if k not in gecerli and u.aktif)
    return fark


def bayatlari_kapat(oturum: Session, gecerli: set[str], an: dt.datetime) -> int:
    """Geçerli kümede olmayan aktif satırlar → `aktif=false`, `guncellendi = an`; kapanan satır sayısı."""
    sonuc = oturum.execute(update(Urun).where(Urun.aktif.is_(True), Urun.polar_urun_id.not_in(gecerli))
                           .values(aktif=False, guncellendi=an))
    return kuyruk._etkilenen(sonuc)


def yaz(oturum: Session, satirlar: Iterable[Satir], an: dt.datetime) -> int:
    """Upsert `polar_urun_id` üstünden; `guncellendi = an` her satırda (ayna tazeliği). Yazılan satır sayısı."""
    sayi = 0
    for s in satirlar:
        degerler = dataclasses.asdict(s) | {"guncellendi": an}
        oturum.execute(pg_insert(Urun).values(**degerler)
                       .on_conflict_do_update(index_elements=["polar_urun_id"],
                                              set_={k: v for k, v in degerler.items() if k != "polar_urun_id"}))
        sayi += 1
    return sayi


def _satir_metni(s: Satir) -> str:
    return (f"{s.polar_urun_id}  {s.tur}{'/' + s.plan if s.plan else ''}  {s.kredi} kredi  "
            f"{s.fiyat_kurus / 100:.2f} {s.para_birimi}  {s.ad!r}  {'aktif' if s.aktif else 'ARSIV'}")


def farki_bas(fark: Fark, hedef: Any) -> None:
    for gerekce in fark.atlanan:
        print(f"UYARI URUN ATLANDI: {gerekce}", file=hedef)
    for s in fark.eklenen:
        print(f"+ {_satir_metni(s)}", file=hedef)
    for s in fark.degisen:
        print(f"~ {_satir_metni(s)}", file=hedef)
    for kimlik in fark.kapanacak:
        print(f"- {kimlik}  aynada var, Polar'da gecerli degil -> aktif=false", file=hedef)
    print(f"{len(fark.eklenen)} yeni, {len(fark.degisen)} degisen, {fark.ayni} ayni, "
          f"{len(fark.atlanan)} atlanan, {len(fark.kapanacak)} kapanan", file=hedef)


def _ayristirici() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="polar_esitle.py",
        description="Polar urunlerini `urunler` aynasina yaz (DATABASE_URL + KROMIS_POLAR_ERISIM_JETONU ile).")
    p.add_argument("--kontrol", action="store_true", help="yalnizca farki bas, yazma; fark varsa cikis 2")
    return p


def main(argv: list[str]) -> int:
    args = _ayristirici().parse_args(argv)
    url = db.baglanti_dizesi()
    if not url:
        print(f"{db.DATABASE_URL_ENV} verilmedi: bu arac veri tabanina baglanir.", file=sys.stderr)
        return CIKIS_ORTAM
    if not polar.erisim_jetonu():
        print(f"{polar.JETON_ENV} verilmedi: bu arac Polar'a baglanir ({polar.ortam()}).", file=sys.stderr)
        return CIKIS_ORTAM
    try:
        urunler = polar.urunleri_listele()
    except Exception as hata:   # noqa: BLE001 — SDK'nın istisna ailesi ve ağ; sınıf adı + ilk satır yeter
        print(f"Polar hatasi ({type(hata).__name__}): {str(hata).splitlines()[0] if str(hata) else ''}",
              file=sys.stderr)
        return CIKIS_ORTAM
    motor = db.motor_kur(url)
    try:
        with kiraci.baglam(rol=kiraci.ADMIN), Session(motor) as oturum:
            fark = fark_hesapla(oturum, urunler)
            farki_bas(fark, sys.stderr if args.kontrol else sys.stdout)
            if args.kontrol:
                return CIKIS_ORTAM if fark.var else CIKIS_TAMAM
            # Aynı kalanlar da yazılır: `guncellendi` ilerlesin (tazelik göstergesi bu sütun).
            satirlar, _ = satirlara_cevir(urunler)
            an = dt.datetime.now(tz=dt.UTC)
            sayi = yaz(oturum, satirlar, an)
            kapanan = bayatlari_kapat(oturum, {s.polar_urun_id for s in satirlar}, an)
            oturum.commit()
            print(f"{sayi} urun yazildi, {kapanan} bayat satir kapatildi ({polar.ortam()})", file=sys.stderr)
    except SQLAlchemyError as hata:
        # Bağlantı dizesinde parola olabilir; yalnız sınıf adı ve ilk satır (`kullanici.py`nin kararı).
        print(f"veri tabani hatasi ({type(hata).__name__}): {str(hata).splitlines()[0]}", file=sys.stderr)
        return CIKIS_ORTAM
    finally:
        motor.dispose()
    return CIKIS_TAMAM


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
