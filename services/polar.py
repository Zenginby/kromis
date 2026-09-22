# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Polar (Merchant of Record) sarmalı — ortam, istemci, webhook imzası, olay zarfı (Faz 4 / 3, K1/K4).

KONUŞMAZ: cümle yok, i18n yok (tests/test_i18n.py sınıflandırması). Polar'la
konuşan TEK modül burası; olayı deftere/plana çeviren `services/odeme.py`,
HTTP'yi kuran `routers/odeme.py`. Üç ortam değişkeni (`.env.example` 1. bölüm,
bekçisi tests/test_docker_kapisi.py `ALTYAPI`):

* `KROMIS_POLAR_ORTAM` — `sandbox` | `production`; **BOŞ = sandbox**. Yanlışlıkla
  canlıya bağlanmak yerine yanlışlıkla sandbox'a bağlanılır: ilk canlı denemede
  "ürün yok" diye fark edilir, tersi gerçek kart çeker. Başka değer `ValueError`
  (yazım hatası sessizce sandbox sayılmasın).
* `KROMIS_POLAR_ERISIM_JETONU` — organizasyon erişim jetonu; yalnız web süreci
  ve araçlar okur (4. görev checkout/portal/ürün listesi, 5. görev abonelik
  iptali). Webhook ucu bunu HİÇ kullanmaz.
* `KROMIS_POLAR_WEBHOOK_SIRRI` — Polar panelinde uç nokta için üretilen sır;
  yalnız web süreci okur.

İMZA — STANDARD WEBHOOKS, SDK'NIN AYNI İLKELİ (doğrulandı 2026-09-21, `polar-sdk`
0.32.0 kaynağı `polar_sdk/_webhooks/__init__.py`): `validate_event(body, headers,
secret)` = `standardwebhooks.Webhook(base64(secret)).verify(body, headers)` + tür
ayrımı + pydantic modeli. Biz aynı `Webhook` sınıfını kullanıyoruz ama SIR
DÖNÜŞÜMÜNDE SDK'DAN SAPIYORUZ: sır olduğu gibi verilir, kütüphane `whsec_`
önekini soyup base64'ü çözer (gerekçe ve ölçüm `_anahtar`da — SDK'nın dönüşümü
Polar'ın bugünkü sırrıyla her teslimatı 400'e düşürüyor). Pydantic modeline
GİRMİYORUZ — gerekçe belge §3
"Sapmalar (a)": SDK'nın modeli Polar şemasının o günkü hâlini ZORUNLU alan
alan ister; Polar bir enum değeri ya da alan eklediğinde bizim işimize yaramayan
bir doğrulama hatası 500 olur, Polar saatlerce yeniden dener ve sonunda ucu
kapatır. Doğrulama = imza + zaman (±5 dk, kütüphanenin) + JSON zarfı (`type`,
`data`); alan okumaları `services/odeme.py`de tolerant (`dict.get`). Sağlayıcı
şemasına bağlılık tests/fixtures/polar/*.json ile ölçülür: her yük SDK modelinden
geçer (`tests/test_odeme.py`), yani okuduğumuz alan adları SDK'nın şemasında var.

`imzala` doğrulamanın tersi: testler ve E2E'nin yerel "Polar"ı (4. görev) gerçek
HMAC üretir; `Webhook.verify` HİÇ yamalanmaz (Faz 0 netguard dersi: yamalanan
kapı sessizce anlamsızlaşır).

İSTEMCİ TEMBEL: `polar_sdk` ~1 MB, pydantic modelleri yüzlerce; webhook yolu ona
hiç ihtiyaç duymaz, testler onu hiç yüklemez. `istemci()` çağrılınca ithal edilir
(services/hata_izleme.py'nin Sentry deyimi). Sunucu adları SDK'nın
(`sdkconfiguration.SERVERS`): production `https://api.polar.sh`, sandbox
`https://sandbox-api.polar.sh` — `server="sandbox"` ile seçilir.

POLAR'A GİDEN ÜÇ ÇAĞRI (Faz 4 / 4, K7) — hepsi `istemci()` üstünden, hepsi
İNCE: `checkout_ac` (`POST /v1/checkouts/` → barındırılan ödeme sayfasının
URL'si), `portal_baglantisi` (`POST /v1/customer-sessions/` → müşteri portalı
URL'si), `urunleri_listele` (`GET /v1/products/` sayfa sayfa → düz sözlükler,
`tools/polar_esitle.py`nin girdisi). SDK'nın pydantic nesneleri bu modülün
DIŞINA ÇIKMAZ: çağıranlar `str`/`dict` alır, böylece rota ve araç SDK'nın
model adlarına bağlanmaz ve testler `polar.checkout_ac`ı tek satırla yamalar
(E2E'nin yerel Polar'ı). SDK'nın kendi istisnaları (`polar_sdk.models.SDKError`
ailesi, ağ hataları) OLDUĞU GİBİ yukarıya çıkar; rota onları 502
`err.odeme_saglayici`ye çevirir (`routers/odeme.py`) — burada yutulsa "URL
gelmedi" ile "Polar 500 verdi" ayrılamazdı.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from standardwebhooks.webhooks import Webhook, WebhookVerificationError

if TYPE_CHECKING:
    from polar_sdk import Polar

__all__ = ["ORTAM_ENV", "JETON_ENV", "WEBHOOK_SIRRI_ENV", "ORTAM_SANDBOX", "ORTAM_PRODUCTION", "ORTAMLAR",
           "BASLIK_ID", "BASLIK_ZAMAN", "BASLIK_IMZA",
           "YapilandirmaHatasi", "ImzaHatasi", "YukHatasi", "Olay",
           "ortam", "erisim_jetonu", "webhook_sirri", "olay_dogrula", "imzala", "istemci",
           "checkout_ac", "portal_baglantisi", "urunleri_listele"]

# `.env.example` 1. bölüm aynı adları buradan okur (bekçisi tests/test_docker_kapisi.py `ALTYAPI`).
ORTAM_ENV = "KROMIS_POLAR_ORTAM"
JETON_ENV = "KROMIS_POLAR_ERISIM_JETONU"
WEBHOOK_SIRRI_ENV = "KROMIS_POLAR_WEBHOOK_SIRRI"

ORTAM_SANDBOX = "sandbox"
ORTAM_PRODUCTION = "production"
ORTAMLAR: tuple[str, ...] = (ORTAM_SANDBOX, ORTAM_PRODUCTION)

# Standard Webhooks başlıkları (küçük harf; `Webhook.verify` başlık adlarını kendisi küçültür).
BASLIK_ID = "webhook-id"
BASLIK_ZAMAN = "webhook-timestamp"
BASLIK_IMZA = "webhook-signature"


class YapilandirmaHatasi(Exception):
    """Gerekli ortam değişkeni boş (jeton ya da webhook sırrı); mesaj değişkenin ADI."""


class ImzaHatasi(Exception):
    """Başlık eksik/bozuk, zaman toleransı dışında ya da imza uymuyor — rota 400."""


class YukHatasi(Exception):
    """İmza geçerli ama gövde JSON nesnesi değil ya da `type` yok — rota 400 (Polar böyle göndermez)."""


@dataclasses.dataclass(frozen=True)
class Olay:
    """Doğrulanmış bir teslimat: `webhook_id` (teslimat kimliği, K4 teslimat katmanı), `tur` (`order.paid` …),
    `zaman` (Polar'ın imzaladığı damga) ve HAM `govde` (JSON nesnesi — `odeme_olaylari.govde`ye redakte yazılır).

    `veri` = `govde["data"]` (nesne yoksa boş sözlük), `nesne_id` = `data.id` (sipariş/abonelik/müşteri kimliği).
    Alan okumaları tolerant: tanınmayan bir yük burada değil `services/odeme.py`de "atlandı" olur.
    """
    webhook_id: str
    tur: str
    zaman: dt.datetime
    govde: Mapping[str, Any]

    @property
    def veri(self) -> Mapping[str, Any]:
        data = self.govde.get("data")
        return data if isinstance(data, Mapping) else {}

    @property
    def nesne_id(self) -> str | None:
        kimlik = self.veri.get("id")
        return str(kimlik) if isinstance(kimlik, str) and kimlik else None


def _oku(ad: str, ortam_map: Mapping[str, str] | None) -> str:
    return ((os.environ if ortam_map is None else ortam_map).get(ad) or "").strip()


def ortam(ortam_map: Mapping[str, str] | None = None) -> str:
    """`KROMIS_POLAR_ORTAM`: boş → `sandbox`; `sandbox`/`production` aynen; başka değer `ValueError` (gerekçe modül başında)."""
    ham = _oku(ORTAM_ENV, ortam_map)
    if not ham:
        return ORTAM_SANDBOX
    if ham not in ORTAMLAR:
        raise ValueError(f"{ORTAM_ENV} {' ya da '.join(ORTAMLAR)} olmali, verilen: {ham!r}")
    return ham


def erisim_jetonu(ortam_map: Mapping[str, str] | None = None) -> str | None:
    """`KROMIS_POLAR_ERISIM_JETONU`; boşsa `None`."""
    return _oku(JETON_ENV, ortam_map) or None


def webhook_sirri(ortam_map: Mapping[str, str] | None = None) -> str | None:
    """`KROMIS_POLAR_WEBHOOK_SIRRI`; boşsa `None` — rota 503 verir, sırsız uç asla "geçerli" demez."""
    return _oku(WEBHOOK_SIRRI_ENV, ortam_map) or None


def _anahtar(sir: str) -> str:
    """Sır, `standardwebhooks`a OLDUĞU GİBİ verilir — kütüphane `whsec_` önekini soyar ve base64'ü çözer.

    SDK'DAN BİLEREK SAPMA, ÖLÇÜLDÜ 2026-09-22 (canlı sandbox). Burada
    `base64.b64encode(sir.encode())` yazıyordu — `polar_sdk` 0.32.0'ın
    `validate_event`i birebir bu (`_webhooks/__init__.py:122`). O dönüşüm
    Polar'ın BUGÜN ürettiği sırla ÇALIŞMIYOR: base64'lenmiş dize `whsec_` ile
    başlamadığı için kütüphane öneki soymaz, base64'ü çözer ve HMAC anahtarı
    sırın ASCII baytları olur. Oysa Polar, Standard Webhooks kuralıyla
    imzalıyor: anahtar = `whsec_` sonrasının base64 ÇÖZÜMÜ.

    Üç gerçek Polar teslimatı yakalanıp (başlık + ham gövde) dört aday anahtarla
    HMAC hesaplandı; yalnız bu kural eşleşti, üçünde de:

        imza = base64(HMAC-SHA256(b64decode(sır[6:]), f"{id}.{zaman}." + gövde))

    Belirti: her teslimat 400 `imza_gecersiz`, uç hiç çalışmaz, Polar saatlerce
    yeniden dener. Testler bunu GÖRMÜYORDU çünkü `imzala`/`olay_dogrula` aynı
    `_anahtar`la gidip geliyor — yanlış anahtar da kendi içinde tutarlıdır;
    bekçisi artık `test_odeme.py`de bağımsız hesaplanan gerçek bir imza.
    """
    return sir


def olay_dogrula(govde: bytes, basliklar: Mapping[str, str], *, sir: str | None = None) -> Olay:
    """HAM gövde + başlıklar → `Olay`; imza/zaman hatası `ImzaHatasi`, zarf hatası `YukHatasi`, sır yoksa `YapilandirmaHatasi`.

    Gövde JSON'a imza doğrulanmadan ÇEVRİLMEZ (`Webhook.verify` önce HMAC'i
    karşılaştırır, sonra `json.loads`): sırsız çağrının maliyeti bir HMAC (belge
    §3 "Risk"). `sir` verilmezse ortamdan okunur; testler sabit `DUMMY` sır verir.
    """
    sir = sir if sir is not None else webhook_sirri()
    if not sir:
        raise YapilandirmaHatasi(WEBHOOK_SIRRI_ENV)
    basliklar = {str(k).lower(): str(v) for k, v in basliklar.items()}
    try:
        veri = Webhook(_anahtar(sir)).verify(govde, basliklar)
    except WebhookVerificationError as e:
        raise ImzaHatasi(str(e)) from e
    except (ValueError, UnicodeDecodeError) as e:
        # `v1,...` biçimine uymayan imza parçası ya da base64 dışı imza: kütüphane
        # `ValueError`/`binascii.Error` fırlatıyor (kendi hatasına sarmıyor); UTF-8
        # olmayan gövde de öyle. Hepsi "bu Polar'dan gelmedi" — 400.
        raise ImzaHatasi(str(e)) from e
    if not isinstance(veri, Mapping):
        raise YukHatasi("govde JSON nesnesi degil")
    tur = veri.get("type")
    if not isinstance(tur, str) or not tur:
        raise YukHatasi("type yok")
    try:
        zaman = dt.datetime.fromtimestamp(float(basliklar[BASLIK_ZAMAN]), tz=dt.UTC)
    except (KeyError, ValueError, OverflowError, OSError) as e:   # pragma: no cover — verify çoktan reddetti
        raise ImzaHatasi(str(e)) from e
    return Olay(webhook_id=basliklar[BASLIK_ID], tur=tur, zaman=zaman, govde=veri)


def imzala(govde: bytes, sir: str, *, webhook_id: str, zaman: dt.datetime | None = None) -> dict[str, str]:
    """`olay_dogrula`nın tersi: bu gövde için üç Standard Webhooks başlığı (testler, E2E'nin yerel Polar'ı)."""
    zaman = zaman if zaman is not None else dt.datetime.now(tz=dt.UTC)
    imza = Webhook(_anahtar(sir)).sign(webhook_id, zaman, govde.decode())
    return {BASLIK_ID: webhook_id, BASLIK_ZAMAN: str(int(zaman.timestamp())), BASLIK_IMZA: imza}


def istemci(ortam_map: Mapping[str, str] | None = None) -> Polar:
    """`polar_sdk.Polar` — jetonla, `ortam()`ın sunucusunda; jeton yoksa `YapilandirmaHatasi`. SDK burada ithal edilir (tembel)."""
    jeton = erisim_jetonu(ortam_map)
    if not jeton:
        raise YapilandirmaHatasi(JETON_ENV)
    from polar_sdk import Polar
    return Polar(access_token=jeton, server=ortam(ortam_map))



def checkout_ac(*, urun_id: str, external_customer_id: str, customer_email: str | None,
                success_url: str, metadata: Mapping[str, str] | None = None) -> str:
    """Polar barındırılan checkout oturumu → ödeme sayfasının URL'si (K7; `POST /v1/checkouts/`).

    `external_customer_id` = `kullanicilar.id`: Polar müşteriyi bununla açar ve
    her olayda `customer.external_id` olarak geri gönderir — webhook'un
    kullanıcıyı çözdüğü ilk yol (`services/odeme.kullaniciyi_coz`). `metadata`
    siparişe ve aboneliğe KOPYALANIR (SDK `CheckoutCreate` notu): ikinci yol.
    `success_url` içindeki `{CHECKOUT_ID}` yer tutucusunu Polar doldurur —
    biçim çağıranın (`routers/odeme.py`), burada yorumlanmaz.
    """
    from polar_sdk import models  # tembel — `istemci()` ile aynı gerekçe
    istek = models.CheckoutCreate(products=[urun_id], external_customer_id=external_customer_id,
                                  success_url=success_url, metadata=dict(metadata or {}))
    if customer_email:
        istek.customer_email = customer_email
    cevap = istemci().checkouts.create(request=istek)
    return str(cevap.url)


def portal_baglantisi(polar_musteri_id: str) -> str:
    """Müşteri portalı oturumu → portal URL'si (`POST /v1/customer-sessions/`; iptal, kart, faturalar Polar'da).

    Polar kimliğiyle (`kullanicilar.polar_musteri_id`), `external_customer_id`
    ile değil: kimlik yoksa kullanıcı hiç satın almamıştır ve rota 404
    `err.musteri_yok` der — bu işlev ancak kimlik varken çağrılır. Bağlantı
    tek kullanımlık ve kısa ömürlü (Polar'ın), saklanmaz.
    """
    cevap = istemci().customer_sessions.create(request={"customer_id": polar_musteri_id})
    return str(cevap.customer_portal_url)


def urunleri_listele() -> list[dict[str, Any]]:
    """Organizasyonun BÜTÜN ürünleri (arşivlenmişler dâhil), sayfa sayfa; her ürün DÜZ SÖZLÜK (`model_dump`).

    Arşivlenmişler bilerek dâhil (`is_archived` süzgeci verilmiyor): ayna
    Polar'da kaldırılan ürünü `aktif=false` yapmak zorunda, yalnız aktifleri
    çekseydi kaldırılan ürün satışta görünmeye devam ederdi
    (`tools/polar_esitle.py`). Sayfalama SDK'nın `next()` zincirinden; 100'lük
    sayfa (Polar'ın tavanı) — bir düzine ürün için tek istek.
    """
    urunler: list[dict[str, Any]] = []
    sayfa = istemci().products.list(limit=100)
    while sayfa is not None:
        sonuc = getattr(sayfa, "result", None)
        for urun in (getattr(sonuc, "items", None) or []):
            urunler.append(urun.model_dump(mode="json") if hasattr(urun, "model_dump") else dict(urun))
        sonraki = getattr(sayfa, "next", None)
        sayfa = sonraki() if callable(sonraki) else None
    return urunler
