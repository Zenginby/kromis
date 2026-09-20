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

`temel`/`pro` BUGÜN YALNIZ METADATA: hibe sayıları yer tutucu (1.000 / 3.000 —
Faz 4 fiyatla birlikte belirler), `fiyat` None; kimse o plana geçemez, admin
dışında (`POST /api/admin/kullanicilar/{id}/plan`). Sahip kendi hesabını `pro`
yapar ki videoyu görsün (belge §3 "Sahibin adımı") — bakım turu o hesabı da
yer tutucu sayıya tamamlar (K6), sahibin kendi platform anahtarına kendi harcaması.

`FREE_AYLIK_HIBE` ORTAMDAN (`KROMIS_FREE_AYLIK_HIBE`), kod sabiti değil: sayı
ürün kararı (K6 — 200 kredi ≈ 1 USD sağlayıcı maliyeti, ~25 Azure `medium`
görsel), sahip `.env`iyle değiştirir. Boş = 200; bozuk değer YÜKSEK SESLE
(`kota._tam_sayi`nin deyimi: sessizce 200'e düşen bir hibe, sahibin "500
yaptım" sanmasıyla biterdi); 0 GEÇERLİ (hibe kapalı — `defter.hibe_turu` o
planı atlar), negatif değil. Modül yüklenirken BİR kez okunur: bakım turu her
5 dk aynı sayıyı görmeli, istek başına yeniden okumak burada bir şey
kazandırmaz (testler ortamı değil `PLANLAR`ı yamalar).

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

__all__ = ["FREE_AYLIK_HIBE_ENV", "FREE_AYLIK_HIBE_VARSAYILAN", "FREE_AYLIK_HIBE", "PLAN_VARSAYILAN",
           "Plan", "PLANLAR", "free_aylik_hibe", "kapsiyor"]

# `.env.example` 1. bölüm aynı adı buradan okur (bekçisi tests/test_docker_kapisi.py `ALTYAPI`).
FREE_AYLIK_HIBE_ENV = "KROMIS_FREE_AYLIK_HIBE"
FREE_AYLIK_HIBE_VARSAYILAN = 200
# `kullanicilar.plan` sütununun `server_default`ı ile aynı: satırı olmayan/plansız kullanıcı ücretsizdir.
PLAN_VARSAYILAN = "free"


def free_aylik_hibe(ortam: Mapping[str, str] | None = None) -> int:
    """`KROMIS_FREE_AYLIK_HIBE`; boşsa 200. Bozuk ya da negatif değer `ValueError`; 0 geçerli (hibe kapalı)."""
    ham = ((os.environ if ortam is None else ortam).get(FREE_AYLIK_HIBE_ENV) or "").strip()
    if not ham:
        return FREE_AYLIK_HIBE_VARSAYILAN
    try:
        deger = int(ham)
    except ValueError as e:
        raise ValueError(f"{FREE_AYLIK_HIBE_ENV} tam sayi olmali, verilen: {ham!r}") from e
    if deger < 0:
        raise ValueError(f"{FREE_AYLIK_HIBE_ENV} negatif olamaz, verilen: {deger}")
    return deger


FREE_AYLIK_HIBE = free_aylik_hibe()


@dataclasses.dataclass(frozen=True)
class Plan:
    """Bir planın kod kataloğundaki satırı; `fiyat` Faz 4'e kadar None (ödeme yok)."""
    ad: str
    aylik_hibe: int
    filigran: bool
    video: bool
    fiyat: int | None = None


PLANLAR: dict[str, Plan] = {
    "free": Plan("free", aylik_hibe=FREE_AYLIK_HIBE, filigran=True, video=False),
    "temel": Plan("temel", aylik_hibe=1_000, filigran=False, video=True),
    "pro": Plan("pro", aylik_hibe=3_000, filigran=False, video=True),
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
