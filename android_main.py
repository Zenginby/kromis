# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Android girişi: Chaquopy bu modülü çağırır, uvicorn'u ayağa kaldırır.

`desktop.py`'nin Android karşılığı, ama pencere açmaz — kabuk Kotlin tarafında
(`MainActivity` + `ServerService`). Buradan dönen `(port, token)` çifti ile
WebView `http://127.0.0.1:<port>` adresini yüklüyor.

ÜÇ İŞ YAPIYOR, üçü de bilerek burada:

1. **Yolları AÇIYOR.** `paths.py`'nin Android dalı iki ortam değişkenine bakıyor
   ve bunlar `import app`'ten ÖNCE yazılmak zorunda: `app.py` modül düzeyinde
   `OUTPUT_DIR`/`STATIC_DIR`/`ASSETS_DIR` sabitlerini hesaplıyor, yani sıra
   ters olsa uygulama APK'nın salt-okunur içine bakardı. Değişkenleri Kotlin'e
   yazdırmak yerine burada, import'un hemen üstünde yazmak bu sırayı tek bir
   yerde ve gözle görülür kılıyor.

2. **Oturum token'ı üretiyor ve zorunlu kılıyor.** Sunucu 127.0.0.1'i dinliyor
   ama Android'de loopback CİHAZDAKİ HER UYGULAMAYA açık: `app.py`'de ne CORS
   ne kimlik denetimi var ve bu sunucu kullanıcının Azure anahtarını tutuyor.
   Rastgele token bir çerezle WebView'e yazılıyor, buradaki ince ASGI katmanı
   her isteği ona karşı doğruluyor.

3. **Kapanışı yönetiyor.** Servis öldüğünde uvicorn'a çıkış işaretleniyor.

`app.py`'YE HİÇ DOKUNULMUYOR: kimlik katmanı `app.add_middleware` ile burada
takılıyor, yani masaüstü paketi ve 1188 testin hiçbiri onu görmüyor.
"""
from __future__ import annotations

import os
import secrets
import threading
import traceback

# Çerezin adı JS'te HİÇ geçmiyor — 27 fetch çağrısının hepsi göreli olduğu için
# tarayıcı çerezi kendiliğinden gönderiyor. Bu yüzden ad yalnızca iki tarafın
# (Kotlin + bu modül) anlaştığı bir sabit; frontend'de karşılığı yok.
SESSION_COOKIE = "kromis_session"

# Token uzunluğu: 32 bayt (256 bit). Aynı cihazdaki kötü niyetli bir uygulama
# portu tarayıp deneyebilir; bu uzunlukta deneme yanılma anlamsız.
_TOKEN_BYTES = 32

_state: dict[str, object] = {}

# Token ve kimlik katmanı SÜREÇ ömürlü, sunucu ömürlü DEĞİL.
#
# Gerekçe iki yönlü ve ikisi de yeniden başlatma yolunda ortaya çıkıyor
# (servis öldürülüp Activity uygulamayı geri getirdiğinde):
#   1. `app.add_middleware` yalnızca uygulama HİÇ başlamamışken çalışıyor;
#      Starlette ilk istekte katman yığınını kuruyor ve sonraki her ekleme
#      RuntimeError veriyor. İkinci `start()` çağrısı bu yüzden katmanı
#      yeniden EKLEMEMELİ.
#   2. Token değişseydi WebView'deki çerez bayatlardı: arayüz yeniden
#      yüklenene kadar her istek 403 alır ve kullanıcı çalışan bir uygulamada
#      "Bu sunucuya yalnızca uygulama erişebilir" görürdü.
_token: str | None = None


class SessionCookieGuard:
    """Doğru oturum çerezi taşımayan HER isteği 403 ile kesen ASGI katmanı.

    `BaseHTTPMiddleware` DEĞİL, ham ASGI: Starlette'in o sınıfı her istek için
    ek bir anyio task grubu kuruyor ve gövdeyi akıtırken araya giriyor —
    burada yapılan iş tek bir başlık karşılaştırması, o maliyeti taşımaya değmez.

    Muafiyet YOK: statik dosyalar da, `/` de token istiyor. Gerekçe — arayüzün
    kendisi (index.html) hangi uçların var olduğunu ve JS'in tamamını sızdırır;
    üstelik çerez WebView'e sayfa YÜKLENMEDEN önce yazıldığı için ilk istek de
    onu taşıyor, yani muafiyete ihtiyaç da yok.
    """

    def __init__(self, app, token: str, cookie_name: str = SESSION_COOKIE) -> None:
        self.app = app
        self._token = token
        self._cookie_name = cookie_name

    def _authorized(self, scope) -> bool:
        for name, value in scope.get("headers") or ():
            if name != b"cookie":
                continue
            for chunk in value.decode("latin-1").split(";"):
                key, _, val = chunk.partition("=")
                if key.strip() != self._cookie_name:
                    continue
                # compare_digest: karşılaştırma süresinden token sızdırmasın.
                # Aynı cihazdaki bir saldırgan istek süresini rahatça ölçebilir.
                if secrets.compare_digest(val.strip(), self._token):
                    return True
        return False

    async def __call__(self, scope, receive, send) -> None:
        # "lifespan" ve "websocket" tiplerine dokunulmuyor: lifespan'i kesmek
        # uygulamanın açılış kancalarını (dizin açma, yedek, tohumlama) hiç
        # çalıştırmazdı; websocket ise bu uygulamada hiç kullanılmıyor.
        if scope.get("type") != "http" or self._authorized(scope):
            await self.app(scope, receive, send)
            return

        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8"),
                                # Reddedilen bir yanıt hiçbir yerde önbelleğe
                                # alınmasın: token yenilendiğinde bayat bir 403
                                # arayüzü kalıcı olarak kilitlerdi.
                                (b"cache-control", b"no-store")]})
        # İki dilli: `netguard._REDDEDILDI` ile AYNI gerekçe — bu gövde de ASGI
        # katmanından çıkıyor ve `app._dil_baglami` hiç koşmuyor.
        await send({"type": "http.response.body",
                    "body": ("Bu sunucuya yalnızca uygulama erişebilir. / "
                             "Only this app can reach this server."
                             ).encode("utf-8")})


def new_session_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def _prepare_environment(data_dir: str, resource_dir: str) -> None:
    """`paths.py`'nin Android dalını açar. `import app`'ten ÖNCE çağrılmalı."""
    import paths

    if not data_dir:
        raise ValueError("data_dir boş olamaz (Kotlin tarafı filesDir'i vermeli)")
    os.environ[paths.ANDROID_DATA_ENV] = data_dir
    if resource_dir:
        os.environ[paths.ANDROID_RESOURCE_ENV] = resource_dir


def start(data_dir: str, resource_dir: str = "") -> dict:
    """Sunucuyu başlatır; `{"port": int, "token": str}` döner.

    Kotlin bu sözlüğü okuyup çerezi yazıyor ve WebView'i yüklüyor. Dönüş tipi
    bilerek düz bir `dict`: Chaquopy Python nesnelerini Java tarafına
    `PyObject` olarak veriyor ve sözlükten alan okumak, özel bir sınıfın
    metotlarını çağırmaktan hem kısa hem kırılgan değil.

    İKİNCİ ÇAĞRI YENİDEN BAŞLATMAZ: servis yeniden yaratıldığında (Android
    süreci canlı tutup Service'i geri getirebilir) aynı sunucuya bağlanmak
    gerekiyor — aksi halde ikinci bir uvicorn ikinci bir portta doğar, WebView
    hâlâ eskisine bakar ve üretim isteği iki sunucu arasında kaybolurdu.
    """
    global _token

    if _state.get("server") is not None:
        return {"port": _state["port"], "token": _state["token"]}

    _prepare_environment(data_dir, resource_dir)

    import desktop  # start_server'ın thread + hata yakalama mantığı burada
    import paths

    paths.ensure_data_dirs()
    import app as appmod  # yollar hazır OLDUKTAN sonra

    # Katman yalnız İLK çağrıda takılıyor (bkz. `_token`'ın açıklaması).
    if _token is None:
        _token = new_session_token()
        appmod.app.add_middleware(SessionCookieGuard, token=_token)
    token = _token

    # loop/http AÇIKÇA: Chaquopy'de uvloop ve httptools yok (ikisi de native
    # uzantı). "auto" bırakılsaydı uvicorn her açılışta onları import etmeye
    # çalışıp ImportError'a düşerdi — sonuç aynı, ama boşuna iş.
    server, thread, port = desktop.start_server(
        appmod.app, loop="asyncio", http="h11")

    _state.update(server=server, thread=thread, port=port, token=token)
    return {"port": port, "token": token}


def stop() -> None:
    """uvicorn'a çıkış işaretler ve thread'i bekler. Asla fırlatmaz."""
    server = _state.get("server")
    thread = _state.get("thread")
    if server is None:
        return
    try:
        server.should_exit = True
        if isinstance(thread, threading.Thread):
            thread.join(timeout=5.0)
    except Exception:
        _safe_log(traceback.format_exc())
    finally:
        _state.clear()


def _safe_log(text: str) -> str:
    """Hata kaydını veri dizinine yazar; kendisi asla patlamaz.

    Android'de `--windowed` paketin karşılığı daha da sert: kullanıcının
    stderr'e hiçbir erişimi yok, logcat de yok. Masaüstündeki `hata.log`
    disiplininin aynısı burada da tek teşhis yolu.
    """
    try:
        import errlog
        import paths
        return errlog.safe_append(paths.data_dir(), text)
    except Exception:
        return ""
