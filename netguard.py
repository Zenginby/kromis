"""Masaüstü sunucusunun istek kaynağı denetimi: Host + Origin kapısı.

`android_main.SessionCookieGuard`'ın MASAÜSTÜ karşılığı. O modülün docstring'i
sorunu zaten yazıyor: *"app.py'de ne CORS ne kimlik denetimi var ve bu sunucu
kullanıcının Azure anahtarını tutuyor."* Android'de karşılığı bir oturum
token'ıyla kurulmuştu; masaüstünde hiç kurulmamıştı ve kapatılan iki yol şu:

1. **CSRF.** `POST /api/edit`, `POST /api/import` ve `POST /api/assets/{kind}`
   `multipart/form-data` alıyor — yani CORS'un "basit istek" sınıfında ve ÖN
   UÇUŞ YOK. Kullanıcının tarayıcısındaki herhangi bir sayfa bu üç uca çapraz
   kaynaklı istek atabiliyordu. Yanıtı okuyamaz ama isteği ÇALIŞTIRIR:
   kullanıcının ücretli API kotasını harcar ve galerisine kayıt yazar. (JSON
   alan uçlar ön uçuşla zaten korunuyordu; delik tam olarak multipart olanlarda.)

2. **DNS rebinding.** `Host` başlığı hiç denetlenmiyordu. Saldırganın alan adı
   127.0.0.1'e çözülürse tarayıcı sunucuyu AYNI KAYNAK sayar; o noktada
   `/api/history`, `/api/chats` ve `/output/*` okunabilir hâle gelir.

NEDEN TOKEN DEĞİL, Android'deki gibi: tehdit modeli farklı. Android'de loopback
CİHAZDAKİ HER UYGULAMAYA açık, yani düşman yerel bir süreç olabiliyor ve onu
yalnız paylaşılan bir sır durdurur. Masaüstünde ise yerel bir süreç zaten
`~/.config/lumeo/credentials.env` dosyasını doğrudan okuyabilir — ona karşı
token da bir şey kazandırmazdı. Buradaki gerçek düşman TARAYICIDAKİ BİR SAYFA
ve tarayıcının kendisi bize iki güvenilir tanık veriyor: sayfanın uyduramadığı
`Origin` ve `Host` başlıkları. Kapı bu yüzden başlık düzeyinde, sırsız.

`app.py`'YE HİÇ DOKUNULMUYOR — `android_main`'in kararının aynısı ve aynı
gerekçeyle: kapı GİRİŞ NOKTALARINDA sarılıyor (`desktop.py` ve `run.sh`),
böylece testlerin kurduğu `TestClient` (Host: `testserver`) onu hiç görmüyor.
Kapının kendisi `tests/test_netguard.py`'de gerçek bir soket üzerinden
sınanıyor — sarmalın var olduğunu VARSAYAN bir test, mandalın sessizce
anlamsızlaşması demek olurdu.
"""
from __future__ import annotations

# Loopback sayılan konak adları. `::1` hem çıplak hem köşeli parantezli
# yazılabiliyor (`Host: [::1]:8765`) ve ikisi de aynı arayüzü gösteriyor.
LOOPBACK_KONAKLAR = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})

_REDDEDILDI = (
    "Bu sunucuya yalnızca uygulamanın kendi penceresi erişebilir.".encode("utf-8"))


def konak_adi(host_basligi: str) -> str:
    """`Host` başlığından PORTSUZ konak adı; küçük harfe indirilmiş.

    IPv6 iki ayrı biçimde gelebiliyor ve düz `split(":")` ikisini de bozar:
    `[::1]:8765` → parantez kapanışına kadar oku; portsuz çıplak `::1` →
    olduğu gibi bırak (birden fazla iki nokta varsa ortada port yoktur).
    """
    d = host_basligi.strip().lower()
    if d.startswith("["):
        return d.split("]", 1)[0] + "]"
    if d.count(":") > 1:
        return d
    return d.split(":", 1)[0]


class LoopbackGuard:
    """Yabancı `Host` ya da yabancı `Origin` taşıyan HER isteği 403 ile keser.

    `BaseHTTPMiddleware` DEĞİL, ham ASGI: `SessionCookieGuard`'ın gerekçesinin
    aynısı — burada yapılan iş iki başlık karşılaştırması ve Starlette'in o
    sınıfının istek başına kurduğu anyio görev grubunu taşımaya değmez.

    İKİ KURAL, ikisi de ayrı bir saldırıyı kapatıyor:

    * `Host` loopback OLMAK ZORUNDA → DNS rebinding kapanır. Başlığın hiç
      olmaması da reddediliyor: HTTP/1.1'de zorunlu, yani yokluğu bir tarayıcı
      isteği DEĞİL.
    * `Origin` VARSA kendi kaynağımız olmak zorunda → CSRF kapanır. Yoksa
      istek geçiyor ve bu bir boşluk değil: tarayıcılar güvenli olmayan her
      yöntemde (form gönderimi ve `fetch` dahil) `Origin` gönderiyor, çapraz
      kaynaklı bir sayfa da onu değiştiremiyor. `Origin: null` (sandbox'lı
      iframe, `file://`) eşleşmediği için reddediliyor.

    KENDİ KAYNAĞIMIZ `Host`'tan TÜRETİLİYOR, sabit yazılmıyor: `desktop.py`
    `port=0` ile açılıyor ve port her çalıştırmada değişiyor — sabit bir
    beklenen kaynak yazmak, katmanın kendi uygulamasını kilitlemesi demekti.

    ŞEMA `http`'ye çivili: uygulama loopback'te TLS konuşmuyor (sertifikanın
    anlamı yok, trafik makineden hiç çıkmıyor). Bir gün TLS sonlandıran bir
    vekil eklenirse bu satır ONU DA görmek zorunda — 403'ün metni sayesinde
    böyle bir kurulum sessizce değil, açıkça kırılır.
    """

    def __init__(self, app) -> None:
        self.app = app

    def _izinli(self, scope) -> bool:
        host = None
        origin = None
        for ad, deger in scope.get("headers") or ():
            if ad == b"host":
                host = deger.decode("latin-1")
            elif ad == b"origin":
                origin = deger.decode("latin-1")

        if host is None or konak_adi(host) not in LOOPBACK_KONAKLAR:
            return False
        if origin is None:
            return True
        return origin.strip().lower() == f"http://{host.strip().lower()}"

    async def __call__(self, scope, receive, send) -> None:
        # "lifespan" ve "websocket" tiplerine dokunulmuyor: lifespan'i kesmek
        # uygulamanın açılış kancalarını (dizin açma, yedek) hiç çalıştırmazdı;
        # websocket bu uygulamada hiç kullanılmıyor. `SessionCookieGuard` ile
        # aynı duruş.
        if scope.get("type") != "http" or self._izinli(scope):
            await self.app(scope, receive, send)
            return

        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8"),
                                # Reddedilen yanıt hiçbir yerde önbelleğe
                                # alınmasın: bayat bir 403 arayüzü kalıcı
                                # olarak kilitlerdi.
                                (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": _REDDEDILDI})


def sar(asgi_app):
    """Uygulamayı kapıyla SARAR ve sarmalı döndürür — `add_middleware` DEĞİL.

    Fark önemli ve ölçüldü. `app.app` modül düzeyinde TEK bir nesne ve
    `add_middleware` onu YERİNDE değiştiriyor; üstelik Starlette katman
    yığınını ilk istekte donduruyor, yani "uygulama başladıktan sonra"
    yapılan her ekleme `RuntimeError` veriyor (`android_main`'in `_token`
    notundaki aynı kısıt). Takma yolu denendiğinde `tests/test_desktop.py`
    tam olarak buna düştü: aynı süreçte önce bir `TestClient` yığını
    dondurmuş oluyordu.

    Sarmak bu sınıfı tümden kaldırıyor: paylaşılan nesne DEĞİŞMİYOR, çağrı
    kaç kez yapılırsa yapılsın yeni bir sarmal doğuyor ve uvicorn ASGI
    çağrılabilirinin FastAPI olmasını istemiyor. Lifespan de etkilenmiyor —
    `__call__` http olmayan kapsamı olduğu gibi devrediyor.
    """
    return LoopbackGuard(asgi_app)


def korumali_app():
    """`uvicorn --factory netguard:korumali_app` için giriş noktası.

    `run.sh` bunu kullanıyor. Fabrika olmasının sebebi `app.py`'ye dokunmamak:
    düz `uvicorn app:app` çağrısında katmanı takacak bir yer yok ve modül
    düzeyine `add_middleware` koymak, uygulamayı yalnızca import eden her
    testin de o kapıyı almasına yol açardı.

    NEDEN GELİŞTİRME YOLU DA KORUNUYOR: paketlenmiş uygulamada `port=0` ile
    port her açılışta değişiyor ve saldırganın onu taraması gerekiyor;
    `run.sh` ise 8765'e SABİT — yani CSRF'nin en kolay hedefi tam olarak
    geliştirme sunucusu.
    """
    import app as appmod

    return sar(appmod.app)
