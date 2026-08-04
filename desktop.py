"""Masaüstü başlatıcı: uvicorn'u thread'de çalıştırır, native pencerede gösterir.

Neden port=0: sabit port (run.sh'teki 8765) ikinci bir örnek açıldığında ya da
bayat bir süreç ayakta kaldığında çakışıyordu. Çekirdekten boş port istemek bu
sınıf hatayı tümüyle kaldırır; pencere gerçek portu çalışma anında öğrenir.

Pencere kapanınca uvicorn'a çıkış işaretlenir ve thread beklenir — süreç arkada
asılı kalmaz.

`main()` Finder'dan çift tıklamayla açılır: `--windowed` paket olduğu için
stderr yok, konsol yok. Bu yüzden `main()` tüm hataları yakalar, `hata.log`'a
yazar (bkz. errlog.py) ve kullanıcıya Türkçe bir sistem uyarısı gösterir —
aksi halde Dock ikonu bir kez zıplayıp sessizce kaybolurdu.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
import traceback

import uvicorn
from fastapi import FastAPI

import errlog
import paths
import screencolor

WINDOW_TITLE = "GPT-Image Studio"
WINDOW_SIZE = (1440, 900)
MIN_WINDOW_SIZE = (1024, 700)
_POLL_INTERVAL = 0.02
_JOIN_TIMEOUT = 5.0  # saniye — kapanışta uvicorn thread'inin ölmesini bekleme süresi


def start_server(fastapi_app: FastAPI, host: str = "127.0.0.1",
                 timeout: float = 15.0) -> tuple[uvicorn.Server, threading.Thread, int]:
    """Sunucuyu boş bir portta daemon thread'de başlatır; (sunucu, thread, port) döner."""
    config = uvicorn.Config(fastapi_app, host=host, port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="uvicorn")

    # uvicorn'un kendi thread'i içinde patlayan hata (ör. geçersiz host →
    # OSError → uvicorn'un kendisi sys.exit(1) çağırır) normalde yalnızca
    # threading'in varsayılan excepthook'una gider ve "thread öldü" mesajının
    # NEDENİ kaybolur. Burada geçici olarak yakalayıp önceki hook'a da
    # iletiyoruz (ör. pytest'in kendi excepthook'u — testlerdeki mevcut uyarı
    # davranışı bozulmasın diye) ve aşağıdaki RuntimeError'a ekliyoruz.
    thread_exceptions: list[BaseException] = []
    previous_hook = threading.excepthook

    def _capture_thread_exception(args: threading.ExceptHookArgs) -> None:
        if args.thread is thread:
            thread_exceptions.append(args.exc_value)
        previous_hook(args)

    threading.excepthook = _capture_thread_exception
    try:
        thread.start()

        deadline = time.monotonic() + timeout
        while not server.started:
            if not thread.is_alive():
                detail = f": {thread_exceptions[-1]!r}" if thread_exceptions else ""
                raise RuntimeError(f"sunucu başlatılamadı (thread öldü){detail}")
            if time.monotonic() > deadline:
                server.should_exit = True
                # En-iyi-çaba temizlik: should_exit yalnızca uvicorn ana
                # döngüsüne ULAŞMIŞSA gözlenir. Bu dalın koruduğu tam senaryo
                # (başlangıcın kendisi asılı kalması) içinde thread bu
                # işaretten sonra da canlı kalabilir. daemon=True olduğu için
                # süreç yine de arkada asılı kalmaz.
                raise RuntimeError(
                    f"sunucu başlatılamadı ({timeout} sn içinde hazır olmadı)")
            time.sleep(_POLL_INTERVAL)

        port = server.servers[0].sockets[0].getsockname()[1]
        return server, thread, port
    finally:
        threading.excepthook = previous_hook


def _safe_log(text: str) -> str:
    """errlog.safe_append'i paths.data_dir() ile çağırır — asla patlamaz."""
    return errlog.safe_append(paths.data_dir(), text)


def _escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _show_fatal_alert(log_path: str) -> None:
    """Kullanıcıya Türkçe, kritik bir sistem uyarısı gösterir.

    `subprocess.run(["osascript", ...])` tercih edildi (AppKit.NSAlert
    yerine): bu noktada pywebview'ın NSApplication çalışma döngüsünü
    başlatıp başlatmadığı belirsiz (hata `webview.start()` öncesinde de,
    sırasında da oluşabilir); osascript kendi ayrı sürecinde çalıştığından
    ana uygulamanın Cocoa durumuna hiç bağımlı değil — daha basit ve daha
    güvenilir. Bu fonksiyon KENDİSİ asla patlamamalı: bir uyarı gösterme
    denemesi başarısız olursa süreç yine de (main() içindeki) sys.exit(1)
    ile temiz çıkmalı.
    """
    title = "GPT-Image Studio başlatılamadı"
    message = (f"Uygulama açılamadı. Hata kaydı: {log_path} "
              "— lütfen bu dosyayı Kurum'ya iletin.")
    script = (f'display alert "{_escape_applescript(title)}" '
             f'message "{_escape_applescript(message)}" as critical')
    try:
        subprocess.run(["osascript", "-e", script], check=False,
                       timeout=30, capture_output=True)
    except Exception:
        pass


class Api:
    """pywebview js_api köprüsü — JS'ten `window.pywebview.api` olarak görünür.

    Tek üyesi damlalık. Tarayıcıda aynı işi `EyeDropper` yapıyor ama o API
    Chromium'a özel ve pywebview'ın macOS arka ucu WKWebView (WebKit) — orada
    yok. Bu köprü ikisini davranış olarak eşitliyor: her iki ortamda da ekranın
    her yerinden renk seçilebiliyor.

    pywebview bu metotları AYRI bir thread'de çağırıyor (webview/util.py), yani
    içindeki bekleme ana AppKit döngüsünü kilitlemiyor — screencolor'ın thread
    modeli buna dayanıyor.
    """

    # Test edilebilirlik için ayrı bir isim: testler sampler'ı buradan
    # değiştiriyor, gerçek AppKit yolunu hiç çalıştırmadan.
    _pick = staticmethod(screencolor.pick)

    def pick_screen_color(self) -> str | None:
        """Ekrandan seçilen rengi `#rrggbb` olarak döndürür; seçim yoksa None.

        HİÇBİR koşulda fırlatmaz. js_api metodundan çıkan bir istisna
        pywebview'ın worker thread'inde kalır ve `--windowed` pakette stderr
        olmadığı için izsiz kaybolur; kullanıcı yalnızca "düğme çalışmıyor"
        görür. Bu yüzden yakalanıp hata.log'a yazılıyor (errlog'un gerekçesi).
        """
        try:
            return self._pick()
        except Exception:
            _safe_log(traceback.format_exc())
            return None


def _shutdown(server: uvicorn.Server, thread: threading.Thread) -> None:
    """Sunucuya çıkışı işaretler, thread'in kapanmasını bekler.

    Zaman aşımına uğrarsa (thread hâlâ canlıysa) sessizce geçmez — hata.log'a
    yazar ki tekrarlayan kapanış sorunları görünür olsun. daemon=True olduğu
    için süreç yine de çıkar; bu yalnızca teşhis içindir.
    """
    server.should_exit = True
    thread.join(timeout=_JOIN_TIMEOUT)
    if thread.is_alive():
        _safe_log(f"uvicorn thread'i {_JOIN_TIMEOUT} sn içinde kapanmadı "
                 "(daemon olduğu için süreç yine de çıkacak).")


def _run() -> None:
    import webview  # yalnız pencere yolunda gerekir; testler bunu import etmez

    paths.ensure_data_dirs()
    import app as appmod  # yollar hazır olduktan sonra

    # WKWebView'da `<a download>` YALNIZCA bu ayar açıkken indirmeye dönüşür
    # (webview/platforms/cocoa.py: `action.shouldPerformDownload() and
    # webview_settings['ALLOW_DOWNLOADS']`). pywebview'ın varsayılanı False ve
    # kapalıyken tıklama sıradan bir gezinmeye düşüyordu: PNG'nin MIME türünü
    # WKWebView gösterebildiği için görsel uygulamanın YERİNE çiziliyor, hiçbir
    # şey kaydedilmiyor ve kullanıcı orada mahsur kalıyordu — Delete ile geri
    # gitme hareketi de aynı dosyada bilerek kapalı, yani çıkış yolu yok.
    #
    # Atama YERİNDE yapılmak ZORUNDA (`webview.settings[...] = True`).
    # cocoa.py modül düzeyinde `from webview import settings as webview_settings`
    # ile AYNI nesneye bağlanıyor; `webview.settings = {...}` diye yeniden
    # atamak o bağı koparır ve düzeltme sessizce ölür.
    webview.settings["ALLOW_DOWNLOADS"] = True

    server, thread, port = start_server(appmod.app)
    try:
        # js_api: damlalık için native köprü (bkz. Api). Olmadan
        # `window.pywebview.api` hiç oluşmaz ve WKWebView'da EyeDropper de
        # bulunmadığı için düğme sessizce gizli kalır.
        webview.create_window(WINDOW_TITLE, f"http://127.0.0.1:{port}",
                              width=WINDOW_SIZE[0], height=WINDOW_SIZE[1],
                              min_size=MIN_WINDOW_SIZE, js_api=Api())
        webview.start()
    finally:
        _shutdown(server, thread)


def main() -> None:
    """`_run()`'ı çalıştırır; her hatayı loglar + kullanıcıya gösterir.

    Neden gerekli: paket `--windowed` olduğu için hiçbir stderr görünmez.
    Sarmalama olmadan kullanıcı yalnızca Dock ikonunun bir kez zıplayıp
    kaybolduğunu görür, ne olduğunu asla öğrenemez — ve onu destekleyecek
    kişi de (terminal kullanamıyor) öğrenemez.
    """
    try:
        _run()
    except Exception:
        log_path = _safe_log(traceback.format_exc())
        _show_fatal_alert(log_path)
        sys.exit(1)


if __name__ == "__main__":
    main()
