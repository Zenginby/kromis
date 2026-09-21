# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Plan kataloğu — `free`/`temel`/`pro`, KODDA (Faz 3 / 3, K5). Saf: DB yok, cümle yok.

TABLO DEĞİL, SÖZLÜK (docs/faz3-kredi-defteri-filigran.md §3, K5): üç plan,
alanları sabit, fiyat yok. Tablo bugün üç satırlık bir sözlük olur ve göç +
depo + admin CRUD + bekçi ister — hiç değişmeyecek veri için. Ödeme gelince
(Faz 4, Polar) plan ↔ ürün id'si, fiyat, para birimi, dönem gerekir; o gün
`planlar` tablosu ve `kullanicilar.plan` FK'si göçle gelir, bu modülün arayüzü
(`PLANLAR[ad]`, `kapsiyor`) aynı kalır, okuyanlar değişmez.

`kullanicilar.plan` sütununun CHECK kümesi `services/tablolar.PLANLAR_KUMESI`;
bu sözlüğün anahtarları onunla EŞİT olmak zorunda (bekçi tests/test_planlar.py
+ aşağıdaki `assert`): DB'nin kabul ettiği ama kodun tanımadığı bir plan
`PLANLAR[plan]`da KeyError, kodun tanıdığı ama DB'nin reddettiği bir plan admin
rotasında 500 olurdu.

VİDEO KURALI PLANIN ÖZELLİĞİ, MODELİN DEĞİL (K7): katalogdaki `ImageModel.plan`
bugün her modelde `"free"` ve öyle kalıyor; ücretsiz planda video modellerinin
kapanması `Plan.video=False` ile bu katalogda. Sebep filigran yokluğu: sunucuda
video işleme aracı yok (ffmpeg imaja girmiyor, belge "BU FAZDA YOK"), ücretsiz
görsel işçide filigranlanır (4. görev), ücretsiz video filigransız çıkardı —
kapı o yüzden anahtar kaynağından BAĞIMSIZ, BYOK'lu ücretsiz kullanıcı da video
alamaz (anahtarın kimin olduğu filigranın yokluğunu değiştirmez).

`temel`/`pro` — KURAL KODDA, HİBE ORTAMDAN, FİYAT POLAR'DA (Faz 4 / 2, K5):
`planlar` tablosu YOK (Faz 3 K5'in "o gün gelir" cümlesinden SAPMA — fiyatın
gerçek sahibi Polar, bizde kopyası `urunler` aynası, `tools/polar_esitle.py`
4. görev); `fiyat` alanı None kalır ve kalacak. Dönem hibesi
`KROMIS_TEMEL_AYLIK_HIBE` / `KROMIS_PRO_AYLIK_HIBE` (boş = 1.000 / 3.000 — Faz
3'ün yer tutucuları; K5'in önerdiği 1.200 / 4.500 sahibin 4. görevde Polar
ürünlerini yazarken vereceği sayı). Ücretli plana geçiş 3. görevden itibaren
webhook (`subscription.*`), bugün admin (`POST /api/admin/kullanicilar/{id}/plan`).

ÜCRETLİ PLANIN HİBESİNİ KİM YATIRIR (K6): Faz 3'te bakım turu her planı kendi
sayısına tamamlıyordu; Faz 4'te ücretli planın dönem hibesi Polar'ın
`order.paid` olayıyla gelir (3. görev, `hibe:<u>:polar:<order_id>`), bakım turu
YALNIZ `free`yi tarar (`defter.hibe_turu`). 3 gelmeden 2 canlıda tek başına
dursun diye GEÇİCİ bayrak `KROMIS_UCRETLI_HIBE_BAKIMDA=1`: bakım turu eski
gibi ücretli planları da tamamlar (sahibin `pro` hesabı hibesiz kalmasın — belge
§2 "Risk"); 3. görev bayrağı kaldırır. Öntanım KAPALI: yanlışlıkla iki kez
hibe (tur + webhook) yerine yanlışlıkla eksik hibe — ilki para, ikincisi bir
ortam değişkeni.

`FREE_AYLIK_HIBE` ORTAMDAN (`KROMIS_FREE_AYLIK_HIBE`), kod sabiti değil: sayı
ürün kararı (K6 — 200 kredi ≈ 1 USD sağlayıcı maliyeti, ~25 Azure `medium`
görsel), sahip `.env`iyle değiştirir. Boş = 200; bozuk değer YÜKSEK SESLE
(`kota._tam_sayi`nin deyimi: sessizce 200'e düşen bir hibe, sahibin "500
yaptım" sanmasıyla biterdi); 0 GEÇERLİ (hibe kapalı — `defter.hibe_turu` o
planı atlar), negatif değil. Üç hibe de modül yüklenirken BİR kez okunur:
bakım turu her 5 dk aynı sayıyı görmeli, istek başına yeniden okumak burada
bir şey kazandırmaz (testler ortamı değil `PLANLAR`ı yamalar). Bayrak ise
HER ÇAĞRIDA okunur (`ucretli_hibe_bakimda`): geçici bir anahtar, testler ortamı yamalar.

Kullanıcının planını DB'den OKUYAN işlev burada değil `services/defter.py`de
(`plan_oku`): bu modül depo değil katalog — `(db, kullanici_id)` imza
sözleşmesi (tests/test_galeri_db.py) depo modüllerinin, saf bir sözlüğün değil.
403 gövdesini `services/kapilar.check_plan` kurar (`err.plan_kapsamiyor`),
rozeti ön yüz `sebep` alanından (`services/modeller`).
"""
from __future__ import annotations

import dataclasses
import os
from collections.abc import Mapping

import catalog
from services.tablolar import PLANLAR_KUMESI

__all__ = ["FREE_AYLIK_HIBE_ENV", "FREE_AYLIK_HIBE_VARSAYILAN", "FREE_AYLIK_HIBE",
           "TEMEL_AYLIK_HIBE_ENV", "TEMEL_AYLIK_HIBE_VARSAYILAN", "PRO_AYLIK_HIBE_ENV", "PRO_AYLIK_HIBE_VARSAYILAN",
           "UCRETLI_HIBE_BAKIMDA_ENV", "PLAN_VARSAYILAN",
           "Plan", "PLANLAR", "free_aylik_hibe", "aylik_hibe", "ucretli_hibe_bakimda", "kapsiyor"]

# `.env.example` 1. bölüm aynı adları buradan okur (bekçisi tests/test_docker_kapisi.py `ALTYAPI`).
FREE_AYLIK_HIBE_ENV = "KROMIS_FREE_AYLIK_HIBE"
FREE_AYLIK_HIBE_VARSAYILAN = 200
# Faz 4 / 2 (K5): ücretli planların dönem hibesi de ortamdan; boş = Faz 3'ün yer tutucuları.
TEMEL_AYLIK_HIBE_ENV = "KROMIS_TEMEL_AYLIK_HIBE"
TEMEL_AYLIK_HIBE_VARSAYILAN = 1_000
PRO_AYLIK_HIBE_ENV = "KROMIS_PRO_AYLIK_HIBE"
PRO_AYLIK_HIBE_VARSAYILAN = 3_000
# GEÇİCİ (Faz 4 / 2 → 3): `1` ise bakım turu ücretli planları da tamamlar (Faz 3 davranışı).
UCRETLI_HIBE_BAKIMDA_ENV = "KROMIS_UCRETLI_HIBE_BAKIMDA"
# `kullanicilar.plan` sütununun `server_default`ı ile aynı: satırı olmayan/plansız kullanıcı ücretsizdir.
PLAN_VARSAYILAN = "free"


def aylik_hibe(ad: str, varsayilan: int, ortam: Mapping[str, str] | None = None) -> int:
    """`ad` değişkeni; boşsa `varsayilan`. Bozuk ya da negatif değer `ValueError`; 0 geçerli (hibe kapalı)."""
    ham = ((os.environ if ortam is None else ortam).get(ad) or "").strip()
    if not ham:
        return varsayilan
    try:
        deger = int(ham)
    except ValueError as e:
        raise ValueError(f"{ad} tam sayi olmali, verilen: {ham!r}") from e
    if deger < 0:
        raise ValueError(f"{ad} negatif olamaz, verilen: {deger}")
    return deger


def free_aylik_hibe(ortam: Mapping[str, str] | None = None) -> int:
    """`KROMIS_FREE_AYLIK_HIBE`; boşsa 200 (Faz 3 / 3'ün imzası, `aylik_hibe`nin üstünde)."""
    return aylik_hibe(FREE_AYLIK_HIBE_ENV, FREE_AYLIK_HIBE_VARSAYILAN, ortam)


def ucretli_hibe_bakimda(ortam: Mapping[str, str] | None = None) -> bool:
    """`KROMIS_UCRETLI_HIBE_BAKIMDA`: boş/`0` = kapalı (bakım turu yalnız `free`), `1` = açık; başka değer `ValueError`.

    Her çağrıda okunur — geçici bir anahtar, sahibin 3. görev gelince
    kaldıracağı; testler ortamı yamalar. Sessizce "kapalı" sayılan bir yazım
    hatası (`yes`, `true`) sahibin `pro` hesabını hibesiz bırakırdı — gürültü.
    """
    ham = ((os.environ if ortam is None else ortam).get(UCRETLI_HIBE_BAKIMDA_ENV) or "").strip()
    if ham in ("", "0"):
        return False
    if ham == "1":
        return True
    raise ValueError(f"{UCRETLI_HIBE_BAKIMDA_ENV} 1 ya da 0 olmali, verilen: {ham!r}")


FREE_AYLIK_HIBE = free_aylik_hibe()


@dataclasses.dataclass(frozen=True)
class Plan:
    """Bir planın kod kataloğundaki satırı; `fiyat` HEP None — fiyat Polar'da, aynası `urunler` (Faz 4 / 2, K5)."""
    ad: str
    aylik_hibe: int
    filigran: bool
    video: bool
    fiyat: int | None = None


PLANLAR: dict[str, Plan] = {
    "free": Plan("free", aylik_hibe=FREE_AYLIK_HIBE, filigran=True, video=False),
    "temel": Plan("temel", aylik_hibe=aylik_hibe(TEMEL_AYLIK_HIBE_ENV, TEMEL_AYLIK_HIBE_VARSAYILAN),
                  filigran=False, video=True),
    "pro": Plan("pro", aylik_hibe=aylik_hibe(PRO_AYLIK_HIBE_ENV, PRO_AYLIK_HIBE_VARSAYILAN),
                filigran=False, video=True),
}
assert tuple(PLANLAR) == PLANLAR_KUMESI, "PLANLAR ↔ kullanicilar.plan CHECK kümesi ayrıştı"


def kapsiyor(plan: str, spec: catalog.ImageModel | catalog.ChatModel) -> bool:
    """Bu plan bu modeli KAPSIYOR mu — anahtardan bağımsız yarı (K7); `model_available` ve `check_plan` aynı soruyu buradan sorar.

    İki koşul: modelin kendi `plan` alanı `free` değilse ücretsiz plan onu
    almaz (katalog verisi, bugün hepsi `free`); model video ise plan videoyu
    açmış olmalı (plan verisi). `plan` CHECK'ten geliyor — tanınmayan ad
    KeyError, sessiz "free" değil.
    """
    return (spec.plan == PLAN_VARSAYILAN or plan != PLAN_VARSAYILAN) and (spec.kind != "video" or PLANLAR[plan].video)
