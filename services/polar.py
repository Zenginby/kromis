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
ayrımı + pydantic modeli. Biz aynı `Webhook` sınıfını AYNI sır dönüşümüyle
çağırıyoruz (`_anahtar`: Polar'ın verdiği ham sır base64'lenir, kütüphane geri
çözer — HMAC anahtarı ham sırın baytları; `whsec_` önekli sır gelirse de SDK gibi
davranır, önek soyulmaz), pydantic modeline GİRMİYORUZ — gerekçe belge §3
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
"""
from __future__ import annotations

import base64
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
           "ortam", "erisim_jetonu", "webhook_sirri", "olay_dogrula", "imzala", "istemci"]

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
    """Polar'ın ham sırı → `standardwebhooks`un beklediği base64 (SDK `validate_event`in birebir dönüşümü)."""
    return base64.b64encode(sir.encode()).decode()


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

