# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İstek kimliği ara katmanı — `X-Request-ID` içeri/dışarı, günlük bağlamı, erişim satırı (Faz 2 / 9).

Her HTTP isteğinin bir kimliği var: gelen `X-Request-ID` başlığı (platform
vekilleri — Fly, Railway, Cloudflare — çoğu zaman verir; kabul edilirse
platformun günlüğüyle bizimki aynı kimlikle eşlenir) ya da `uuid4`. Kimlik
üç yere gider: cevabın `X-Request-ID` başlığına (kullanıcı hata bildirirken
"şu istek" diyebilsin), `request.state.istek_id`ye ve `services/gunluk.py`nin
bağlamına — istek boyunca yazılan HER günlük satırı `istek_id` taşır (rota,
depo, adaptör; hiçbiri kimliği bilmek zorunda değil).

GELEN DEĞER SÜZÜLÜR (`gecerli`): yalnız kısa, boşluksuz ASCII. Başlık istemciden
geliyor; JSON satırına her şey kaçırılarak girer ama metin biçiminde ve
toplayıcının aramasında rastgele bir dize (satır sonu, 8 KB'lık çöp) kimlik
değil gürültüdür — geçersizse yeni kimlik üretilir, istek reddedilmez.

ERİŞİM SATIRI istek SONUNDA, buradan: `olay=istek`, `yontem`, `rota` (yol —
sorgu dizesi YOK: `?sonra=/admin` gibi parçalar kullanıcı verisi taşıyabilir),
`durum`, `sure_ms`, `kullanici_id` (kimlik kapısı çözdüyse — `request.state.
kullanici_id`, `services/kimlik.py::bagla`). uvicorn'un erişim günlüğü KAPALI
(`--no-access-log`, Dockerfile): iki satır aynı şeyi söylerdi ve uvicorn'unki
ne kimlik ne süre ne kullanıcı bilir. `SESSIZ_YOLLAR` (`/health`, `/static/`)
DEBUG'a düşer: sonda 30 sn'de bir sorar, statik dosyalar sayfa başına onlarca
— sinyal değil (gerekçe services/gunluk.py). Rota istisna fırlatırsa satır
`durum=500` ile yine yazılır ve istisna yükselir (uvicorn 500 döner).

AKAN CEVAPTA (SSE, `GET /api/isler/akis`) `call_next` başlıklar gönderilince
döner, gövde sonra akar: erişim satırı akışın başında yazılır ve `sure_ms`
"başlıklara kadar geçen süre"dir — akışın ömrü değil. Bilinçli: akış dakikalarca
açık kalır ve satırı akışın sonuna bırakmak, kopan bağlantıda hiç yazılmaması
demek.

EN DIŞ ARA KATMAN: `app.py` bunu köken kapısından SONRA ekler ve Starlette son
ekleneni en dışa koyar — sıra `istek kimliği → köken → dil → rota` (belge §9).
Köken kapısının 403'ü de kimlik ve erişim satırı taşır; öteki türlü reddedilen
istek görünmez kalırdı. Kullanıcıya konuşmaz (tests/test_i18n.py): başlık adı
ve günlük alanları ASCII, cümle yok.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from services import gunluk, hata_izleme

__all__ = ["BASLIK", "ALAN", "SESSIZ_YOLLAR", "uret", "gecerli", "aktif", "istek_kimligi"]

BASLIK = "X-Request-ID"
# Bağlamdaki ve JSON satırındaki alan adı.
ALAN = "istek_id"
# Erişim satırı DEBUG olan yollar — önek eşleşmesi (`/static/…`), gerekçe başlıkta.
SESSIZ_YOLLAR: tuple[str, ...] = ("/health", "/static/")

# uuid, ULID, base64url, `req-…`: hepsi bu kümede; 128 üstü ve boşluk içeren değer değil.
_GECERLI = re.compile(r"^[A-Za-z0-9._:/+=-]{1,128}$")
_gunluk = logging.getLogger("kromis.istek")


def uret() -> str:
    """Yeni kimlik — `uuid4`, dize."""
    return str(uuid.uuid4())


def gecerli(deger: str | None) -> bool:
    """Gelen `X-Request-ID` kullanılabilir mi (kısa, boşluksuz ASCII)?"""
    return bool(deger) and _GECERLI.match(deger or "") is not None


def aktif() -> str | None:
    """Bu isteğin kimliği (günlük bağlamından); istek bağlamı yoksa `None`."""
    deger = gunluk.aktif().get(ALAN)
    return str(deger) if deger is not None else None


def _erisim(request: Request, durum: int, baslangic: float) -> None:
    yol = request.url.path
    seviye = logging.DEBUG if yol.startswith(SESSIZ_YOLLAR) else logging.INFO
    # `request.state.kullanici_id` (düz uuid; services/kimlik.py `bagla`), `kullanici.id` DEĞİL:
    # istek bitince oturum kapalı, ORM nesnesinin özniteliği okunamaz (ölçüldü).
    kullanici_id = getattr(request.state, "kullanici_id", None)
    gunluk.olay(_gunluk, "istek", seviye=seviye, yontem=request.method, rota=yol, durum=durum,
                sure_ms=round((time.perf_counter() - baslangic) * 1000, 1),
                kullanici_id=str(kullanici_id) if kullanici_id is not None else None)


async def istek_kimligi(request: Request,
                        call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Ara katman: kimliği kur, bağla, cevaba yaz, erişim satırını düşür. `app.py` takar."""
    gelen = request.headers.get(BASLIK)
    istek_id = gelen if gelen is not None and gecerli(gelen) else uret()
    request.state.istek_id = istek_id
    baslangic = time.perf_counter()
    jeton = gunluk.bagla(**{ALAN: istek_id})
    hata_izleme.etiketle(**{ALAN: istek_id})
    try:
        cevap = await call_next(request)
    except Exception:
        _erisim(request, 500, baslangic)
        raise
    else:
        cevap.headers[BASLIK] = istek_id
        _erisim(request, cevap.status_code, baslangic)
        return cevap
    finally:
        gunluk.coz(jeton)
