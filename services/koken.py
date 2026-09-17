# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Köken kapısı — CSRF'nin ikinci katı, `netguard`ın web karşılığı (Faz 1 / 3. görev).

Birinci kat çerezin kendisi: `SameSite=Lax` (services/cerez.py) başka siteden
gelen POST'ta oturum çerezini hiç göndermez. Bu ara katman ikinci kat: GET/HEAD/
OPTIONS dışındaki HER istekte tarayıcının söylediği kökene bakar ve başka bir
siteden geliyorsa 403 der — çerez bir gün `Lax`tan gevşese ya da eski bir
tarayıcı `SameSite`i tanımasa da durum değişmez. İki kat birbirinden bağımsız
ve ikisi de tek başına yeter; savunma derinliği bilerek.

KURAL (`izinli`), tarayıcının verdiği kanıtın gücüne göre sırayla:

1. `Sec-Fetch-Site` varsa SON SÖZ onun: `same-origin` ya da `none` (adres
   çubuğundan / yer iminden gelen istek) geçer; `same-site` ve `cross-site`
   403. Tarayıcı bu başlığı kendisi yazar, sayfa betiği değiştiremez — en
   güvenilir kanıt bu.
2. Yoksa `Origin`: `KROMIS_KOKEN` (env, `https://…`) ile ya da isteğin KENDİ
   kökeniyle (`scheme://host`) eşleşmeli; `null` dâhil her farklı değer 403.
   Kendi kökeni de sayılıyor, çünkü `KROMIS_KOKEN` yerelde ve compose'ta
   verilmez ve `Host` başlığını tarayıcı yazar, saldırganın sayfası değil.
3. O da yoksa `Referer`in köken kısmı aynı ölçütle.
4. ÜÇÜ DE YOKSA GEÇER. Bu gevşeklik değil, tehdidin tanımı: CSRF bir TARAYICI
   saldırısıdır — kurbanın çerezini ancak kurbanın tarayıcısı taşır ve bugünün
   her tarayıcısı çapraz siteden gelen POST'a `Sec-Fetch-Site` VE `Origin`
   yazar (form gönderimi dâhil, 2011'den beri). Üç başlığın da yokluğu
   "tarayıcı değil" demektir (curl, TestClient, bir sonda) ve o istemci
   kurbanın çerezini ödünç alamaz; ona 403 demek yalnız 178 `TestClient`
   çağrısını ve `curl`le sağlık yoklayan operatörü kırardı.

`KROMIS_KOKEN` İKİ İŞ görüyor: buradaki izin listesi VE e-posta bağlantılarının
tabanı (`taban`, services/posta.py). Aynı değişken, çünkü aynı gerçek —
"uygulama hangi adreste yaşıyor" — ve iki yerde yazılsa bir gün ayrışırdı.

`X-Kromis-Istek` gibi bir özel başlık BİLEREK YOK (belge §3): ön yüzün 15
JSON `fetch`i ve 5 multipart yükleyicisi zaten tarayıcının kendiliğinden
koyduğu başlıklarla geliyor; özel başlık her çağrıya bir satır ekler, hiçbir
ek kanıt getirmez.

403 GÖVDESİ BİR KOD (`cross_origin_rejected`), cümle DEĞİL: bu ara katman dil
ara katmanının DIŞINDA koşuyor (köken → dil → rota sırası; `app.py`), yani
isteğin dili henüz çözülmedi. Meşru bir kullanıcı bu cevabı hiç görmez —
tarayıcısı onu zaten aynı kökenden gönderiyor; cevabı okuyan bir geliştirici
ya da bir saldırı denemesinin günlüğü. `services/db.py`nin
`database_unavailable` kararıyla aynı sınıf; tests/test_i18n.py bu modülü
"konuşmayan" sayıyor.
"""
from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from fastapi import Request, Response
from fastapi.responses import JSONResponse

# Uygulamanın dış adresi, `https://studio.example.com` biçiminde (yol yok).
# Boş/yok = "kendi kökenim" — yerel geliştirme ve compose.
KOKEN_ENV = "KROMIS_KOKEN"

# Durum değiştirmeyen fiiller; kapı bunlara bakmaz. OPTIONS da burada: CORS
# ön uçuşu ve sondalar durum değiştirmez, üstelik tarayıcı ön uçuşa çerez
# koymaz.
GUVENLI_YONTEMLER = frozenset({"GET", "HEAD", "OPTIONS"})

# `Sec-Fetch-Site`in geçen değerleri. `same-site` GEÇMİYOR: alt alan adları
# bu uygulamanın parçası değil ve aynı site altındaki başka bir servisin
# ele geçirilmesi bu kapıyı açmamalı.
IZINLI_FETCH_SITE = frozenset({"same-origin", "none"})

# 403 gövdesindeki kod (gerekçesi modül başında).
REDDEDILDI = "cross_origin_rejected"


def yapilandirilan() -> str | None:
    """`KROMIS_KOKEN` — normalize (küçük harf, sondaki `/` yok); yoksa `None`."""
    ham = (os.environ.get(KOKEN_ENV) or "").strip()
    return _koken(ham) if ham else None


def _koken(adres: str) -> str | None:
    """`https://Host:443/yol?x` → `https://host:443`; şeması ya da konağı yoksa `None`.

    `null` (opak köken: sandbox iframe, `data:` sayfa, yönlendirme zinciri)
    burada `None`a düşer ve `izinli` onu eşleşmeyen sayar — RFC 6454 opak
    kökeni "hiçbir kökene eşit değil" diye tanımlıyor, biz de.
    """
    parca = urlsplit(adres.strip())
    if not parca.scheme or not parca.netloc:
        return None
    return f"{parca.scheme.lower()}://{parca.netloc.lower()}"


def istegin_kokeni(request: Request) -> str:
    """İsteğin kendi kökeni — `Host` (ve varsa `--proxy-headers`in çözdüğü şema)."""
    return f"{request.url.scheme.lower()}://{request.url.netloc.lower()}"


def izinli(request: Request) -> bool:
    """Bu istek kapıdan geçer mi? (kural modül başında, sırasıyla)"""
    if request.method in GUVENLI_YONTEMLER:
        return True
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None:
        return fetch_site.strip().lower() in IZINLI_FETCH_SITE
    kabul = {istegin_kokeni(request)}
    ayarli = yapilandirilan()
    if ayarli:
        kabul.add(ayarli)
    for baslik in ("origin", "referer"):
        deger = request.headers.get(baslik)
        if deger is not None:
            return _koken(deger) in kabul
    return True


async def koken_kapisi(request: Request,
                       call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Ara katman: geçmeyen isteğe 403 + kod, geçene dokunmaz. `app.py` takar."""
    if not izinli(request):
        return JSONResponse({"detail": REDDEDILDI}, status_code=403)
    return await call_next(request)


def taban(request: Request) -> str:
    """E-posta bağlantılarının tabanı: `KROMIS_KOKEN`, yoksa isteğin kendi kökeni.

    Yerelde `http://127.0.0.1:8765`, dağıtımda env'deki `https://…`. Env
    verilmeden vekil arkasında koşan bir dağıtım `http://iç-adres` üretir —
    o yüzden `.env.example` değişkeni "dağıtımda ZORUNLU" diye anlatıyor.
    """
    return yapilandirilan() or istegin_kokeni(request)
