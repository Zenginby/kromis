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

VİDEO KURALI PLANIN ÖZELLİĞİ, MODELİN DEĞİL (K7): ücretsiz planda video
modellerinin kapanması `Plan.video=False` ile bu katalogda. Sebep filigran
yokluğu: sunucuda video işleme aracı yok (ffmpeg imaja girmiyor, belge "BU
FAZDA YOK"), ücretsiz görsel işçide filigranlanır (4. görev), ücretsiz video
filigransız çıkardı — kapı o yüzden anahtar kaynağından BAĞIMSIZ, BYOK'lu
ücretsiz kullanıcı da video alamaz (anahtarın kimin olduğu filigranın
yokluğunu değiştirmez).

KAPININ ÖTEKİ YARISI ARTIK ANAHTARA BAKIYOR (Faz 4 / 1b, 1b-A): `ImageModel.plan`
bugün hâlâ her girdide `"free"` — yani `kapsiyor` bu PR'da HİÇBİR davranışı
değiştirmiyor — ama 1b'nin katalog PR'ı o alanı VERİ yapacak ve o an, kendi
`gemini` anahtarını girmiş ücretsiz kullanıcı BİZE HİÇ MALİYETİ OLMAYAN bir
modeli göremez hâle gelirdi. Model eşiği bu yüzden yalnız PLATFORM anahtarıyla
koşan işlere uygulanıyor (`kapsiyor`un üçüncü parametresi). Makine önce
geliyor, veri sonra: ters sıra o boşluğu bir tur boyunca canlı bırakırdı.

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
`order.paid` olayıyla gelir (`services/odeme.py`, `hibe:<u>:polar:<order_id>`),
bakım turu YALNIZ `free`yi tarar (`defter.hibe_turu`). Faz 4 / 2'nin geçici
köprüsü `KROMIS_UCRETLI_HIBE_BAKIMDA` 3. görevle KALDIRILDI: köprü açık kalsa
tur + webhook aynı dönemi iki kez tamamlardı. Admin eliyle `pro` yapılmış bir
hesap (Polar aboneliği yok) artık dönem hibesi ALMAZ — sahibin yolu admin
"kredi ekle" (`defter.duzelt`), belge §3 "Sapmalar".

`FREE_AYLIK_HIBE` ORTAMDAN (`KROMIS_FREE_AYLIK_HIBE`), kod sabiti değil: sayı
ürün kararı (K6 — 200 kredi ≈ 1 USD sağlayıcı maliyeti, ~25 Azure `medium`
görsel), sahip `.env`iyle değiştirir. Boş = 200; bozuk değer YÜKSEK SESLE
(`kota._tam_sayi`nin deyimi: sessizce 200'e düşen bir hibe, sahibin "500
yaptım" sanmasıyla biterdi); 0 GEÇERLİ (hibe kapalı — `defter.hibe_turu` o
planı atlar), negatif değil. Üç hibe de modül yüklenirken BİR kez okunur:
bakım turu her 5 dk aynı sayıyı görmeli, istek başına yeniden okumak burada
bir şey kazandırmaz (testler ortamı değil `PLANLAR`ı yamalar).

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
           "PLAN_VARSAYILAN",
           "Plan", "PLANLAR", "free_aylik_hibe", "aylik_hibe", "kapsiyor"]

# `.env.example` 1. bölüm aynı adları buradan okur (bekçisi tests/test_docker_kapisi.py `ALTYAPI`).
FREE_AYLIK_HIBE_ENV = "KROMIS_FREE_AYLIK_HIBE"
FREE_AYLIK_HIBE_VARSAYILAN = 200
# Faz 4 / 2 (K5): ücretli planların dönem hibesi de ortamdan; boş = Faz 3'ün yer tutucuları.
TEMEL_AYLIK_HIBE_ENV = "KROMIS_TEMEL_AYLIK_HIBE"
TEMEL_AYLIK_HIBE_VARSAYILAN = 1_000
PRO_AYLIK_HIBE_ENV = "KROMIS_PRO_AYLIK_HIBE"
PRO_AYLIK_HIBE_VARSAYILAN = 3_000
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


FREE_AYLIK_HIBE = free_aylik_hibe()


@dataclasses.dataclass(frozen=True)
class Plan:
    """Bir planın kod kataloğundaki satırı; `fiyat` HEP None — fiyat Polar'da, aynası `urunler` (Faz 4 / 2, K5)."""
    ad: str
    aylik_hibe: int
    filigran: bool
    video: bool
    # BASAMAK (Faz 4 / 1b, karar 1b-B): free=0 < temel=1 < pro=2. Bugünkü
    # kapı İKİLİYDİ (`spec.plan != "free"` → temel de pro da geçer), yani
    # "YALNIZ pro" bir model İFADE EDİLEMİYORDU. 1b'nin kataloğunda fiyat
    # farkı 95 kata çıkıyor (`fal-flux-1-schnell` 1 kredi ↔ `fal-seedance-2-5`
    # 95 kredi/sn); ikili kapı, `temel` planın aylık hibesini TEK üretimde
    # eritebilecek bir modeli o plana açık bırakırdı.
    #
    # `video` BİLEREK AYRI EKSEN, basamağa katlanmadı: video kuralının
    # gerekçesi fiyat değil FİLİGRAN YOKLUĞU (sunucuda ffmpeg yok) ve onu bir
    # fiyat sıralamasının içine gömmek gerekçeyi görünmez kılardı.
    #
    # `PLANLAR_KUMESI`nden TÜRETİLMİYOR, açıkça yazılıyor: o demetin
    # sözleşmesi "`kullanicilar.plan` CHECK kümesi" (services/tablolar.py),
    # sıralama değil. Sırayı ona yüklersek demet bir gün yeniden sıralandığında
    # — CHECK için tamamen zararsız bir düzenleme — kapı SESSİZCE bozulurdu.
    # Bekçi ikisinin uyumunu ayrıca ölçüyor (tests/test_planlar.py).
    rank: int
    fiyat: int | None = None


PLANLAR: dict[str, Plan] = {
    "free": Plan("free", aylik_hibe=FREE_AYLIK_HIBE, filigran=True, video=False, rank=0),
    "temel": Plan("temel", aylik_hibe=aylik_hibe(TEMEL_AYLIK_HIBE_ENV, TEMEL_AYLIK_HIBE_VARSAYILAN),
                  filigran=False, video=True, rank=1),
    "pro": Plan("pro", aylik_hibe=aylik_hibe(PRO_AYLIK_HIBE_ENV, PRO_AYLIK_HIBE_VARSAYILAN),
                filigran=False, video=True, rank=2),
}
assert tuple(PLANLAR) == PLANLAR_KUMESI, "PLANLAR ↔ kullanicilar.plan CHECK kümesi ayrıştı"


def kapsiyor(plan: str, spec: catalog.ImageModel | catalog.ChatModel, *, platform_anahtariyla: bool) -> bool:
    """Bu plan bu modeli KAPSIYOR mu; `model_available` ve `check_plan` aynı soruyu buradan sorar.

    İKİ KOŞUL, AYRI EKSENLERDE — ve yalnız BİRİ anahtarın kimin olduğuna bakar:

    1. MODEL EŞİĞİ (basamaklı, 1b-B): kullanıcının planı modelin istediği
       basamağa erişiyor mu (`Plan.rank`). YALNIZ platform anahtarıyla koşan
       işlere uygulanır (1b-A): kendi anahtarını girmiş kullanıcının bize
       maliyeti yok, pahalı modeli ondan saklamanın gerekçesi de yok.
    2. VİDEO (anahtardan BAĞIMSIZ — K7 AYNEN DURUYOR): sunucuda video işleme
       aracı yok (ffmpeg imaja girmiyor), ücretsiz video FİLİGRANSIZ çıkardı,
       ve anahtarın kimin olduğu filigranın YOKLUĞUNU değiştirmez. BYOK'lu
       ücretsiz kullanıcı da video alamaz. Filigran kuralı da aynı sebeple
       dokunulmadan kaldı (`services/isci._filigranlanir` yalnız plana bakar).

    `platform_anahtariyla` BOOL, dizge değil: bu modül SAF (dosya başlığı "DB
    yok") ve `platform_anahtari.KAYNAK_PLATFORM`ı ithal etmek `planlar`a
    `depo_kimlik_bilgisi` üzerinden bir SQLAlchemy kenarı takardı. Karşılaştırma
    çağıranda, ikisi de o modülü zaten ithal ediyor.

    ANAHTAR SÖZCÜKLÜ ve ÖNTANIMSIZ, bilerek: üç çağıran var ve biri unutulursa
    öntanımlı bir değer MODEL EŞİĞİNİ SESSİZCE ATLATIRDI — §1b'nin risk notunun
    ("kapı sessizce gevşer") tam olarak korktuğu şey. Öntanımsız imzada
    unutulan çağıran `TypeError` verir. `plan` CHECK'ten geliyor: tanınmayan ad
    KeyError, sessiz "free" değil — aynı duruş, `spec.plan` için de geçerli.
    """
    esik = not platform_anahtariyla or PLANLAR[spec.plan].rank <= PLANLAR[plan].rank
    return esik and (spec.kind != "video" or PLANLAR[plan].video)
