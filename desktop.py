# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
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

WINDOWS'A ÖZGÜ ÜÇ EK — hepsi 2026-09-04'te yaşanmış tek bir kusurdan doğdu.
İndirilen paket kullanıcıda HİÇ açılmadı; `hata.log`'daki tek iz (o günün
kaydı, olduğu gibi — uygulama o gün `Lumeo` adıyla yayınlanıyordu):

    webview/guilib.py:74 import_winforms -> clr.py:6 -> pythonnet/__init__.py:143
    RuntimeError: Failed to resolve Python.Runtime.Loader.Initialize from
      ...\\Lumeo\\_internal\\pythonnet\\runtime\\Python.Runtime.dll

pywebview Windows'ta pencereyi WinForms üzerinden açıyor ve o yol pythonnet ile
.NET Framework'e bağlanıyor; `webview.start()` içindeki bu halka koptuğunda
uygulamanın GERİ KALANI (uvicorn + FastAPI) sapasağlam olsa bile hiçbir şey
görünmüyordu. Eklenenler:

  1. `winclr.onyukle()` — `import webview`'DAN ÖNCE koşan .NET önyükleme
     denetimi (indirme işaretini kaldırır, eksik DLL'i ve eski .NET'i bulgular).
  2. Tarayıcı yedeği — pencere yolu patlarsa sunucu ayakta bırakılır ve
     uygulama varsayılan tarayıcıda açılır. Sebep ne olursa olsun kullanıcı
     uygulamayı KULLANABİLİR; `run.sh` zaten bu modda çalışıyor.
  3. `--onyukleme-denetimi` — pencere açmadan aynı zinciri kademe kademe
     deneyip rapor yazan kip. Hem CI açılış kapısı (`_paket-windows.yml`) hem
     kullanıcı destek aracı.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from typing import Callable

import uvicorn
from starlette.types import ASGIApp

import errlog
import netguard
import paths
import screencolor
import version
import winclr

WINDOW_TITLE = "Kromis Studio"
WINDOW_SIZE = (1440, 900)
MIN_WINDOW_SIZE = (1024, 700)
_POLL_INTERVAL = 0.02
_JOIN_TIMEOUT = 5.0  # saniye — kapanışta uvicorn thread'inin ölmesini bekleme süresi

# Pencere açmadan .NET/GUI zincirini deneyen kip. İki literal de `desktop.py`de
# TEK kaynak: `_paket-windows.yml`'deki açılış kapısı ikisini de metin olarak
# kullanıyor ve `tests/test_windows_acilis.py` bağın kopmadığını mandallıyor —
# bayrağı burada yeniden adlandırmak CI kapısını sessizce kapatamasın.
ONYUKLEME_BAYRAGI = "--onyukleme-denetimi"
ONYUKLEME_RAPORU = "onyukleme-denetimi.txt"


def start_server(asgi_app: ASGIApp, host: str = "127.0.0.1",
                 timeout: float = 15.0, *, loop: str = "auto",
                 http: str = "auto") -> tuple[uvicorn.Server, threading.Thread, int]:
    """Sunucuyu boş bir portta daemon thread'de başlatır; (sunucu, thread, port) döner.

    `loop`/`http` uvicorn'un kendi varsayılanlarıyla ("auto") aynı — yani bu iki
    parametre masaüstü davranışını HİÇ değiştirmiyor. Android girişi (bkz.
    android_main) bunları "asyncio"/"h11" olarak AÇIKÇA veriyor: Chaquopy'de
    uvloop ve httptools kurulu değil ve "auto" onları önce import etmeye
    çalışıp ImportError'a düşerek her açılışta gereksiz iş yapıyor. Seçimi
    çağıran tarafa bırakmak, bu bilgiyi desktop.py'ye gömmekten temiz.
    """
    config = uvicorn.Config(asgi_app, host=host, port=0, log_level="warning",
                            loop=loop, http=http)
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


def _alert_macos(title: str, message: str, *, kritik: bool = True) -> bool:
    """`osascript` ile uyarı; `kritik=False` bilgi kutusu. True = kutu çıktı.

    AppKit.NSAlert yerine subprocess tercih edildi: bu noktada pywebview'ın
    NSApplication çalışma döngüsünü başlatıp başlatmadığı belirsiz (hata
    `webview.start()` öncesinde de, sırasında da oluşabilir); osascript kendi
    ayrı sürecinde çalıştığından ana uygulamanın Cocoa durumuna hiç bağımlı
    değil — daha basit ve daha güvenilir.

    ZAMAN AŞIMI `kritik`e BAĞLI. Ölümcül uyarı "göster ve çık" olduğu için 30
    saniye cömert bir üst sınır; tarayıcı yedeğindeki kutu ise kullanıcı
    uygulamayı kapatana kadar (saatlerce) açık durmak ZORUNDA — orada 30 sn
    `TimeoutExpired` fırlatır ve süreci yedeğin tam ortasında öldürürdü.
    """
    tur = "as critical" if kritik else "as informational"
    script = (f'display alert "{_escape_applescript(title)}" '
             f'message "{_escape_applescript(message)}" {tur}')
    surec = subprocess.run(["osascript", "-e", script], check=False,
                           timeout=30 if kritik else None, capture_output=True)
    # ÇIKIŞ KODU, KUTUNUN GERÇEKTEN ÇIKTIĞININ TEK KANITI. `display alert`
    # kullanıcı Tamam'a basınca 0 ile döner; kutu hiç çizilemediyse (GUI
    # oturumu yok, otomasyon izni reddedildi, `osascript` bir sözdizimi
    # hatasına düştü) sıfırdan farklı bir kod ve boş bir bekleme. Bu ayrım
    # tarayıcı yedeği için hayati — gerekçe `_uyari_goster`de.
    return surec.returncode == 0


def _alert_windows(title: str, message: str, *, kritik: bool = True) -> bool:
    """`MessageBoxW` ile sistem uyarısı — ctypes, subprocess DEĞİL. True = çıktı.

    Burada osascript'in karşılığı `msg.exe`/PowerShell olurdu ama ikisi de yeni
    bir süreç açar: `--windowed` pakette bu bir konsol penceresi çaktırır ve
    `msg.exe` Home sürümlerinde hiç bulunmaz. `user32.MessageBoxW` çekirdeğin
    kendi diyaloğu — ek bağımlılık yok, konsol yok.

    MB_SYSTEMMODAL (0x1000) + MB_SETFOREGROUND (0x10000): pencere hiç açılmadığı
    için uyarı sahipsiz doğuyor ve bu bayraklar olmadan diğer pencerelerin
    ARKASINDA kalabiliyor — kullanıcı yine hiçbir şey görmeden uygulamanın
    öldüğünü sanardı, yani fonksiyonun var oluş sebebi boşa giderdi.

    `kritik=False` yalnız tarayıcı yedeğinde kullanılıyor ve orada bayrak
    kümesi bilerek FARKLI — gerekçesi aşağıda, dalın içinde.
    """
    import ctypes  # yalnız bu dalda gerekli

    MB_ICONERROR = 0x10
    MB_ICONINFORMATION = 0x40
    MB_SYSTEMMODAL = 0x1000
    MB_SETFOREGROUND = 0x10000
    if kritik:
        bayraklar = MB_ICONERROR | MB_SYSTEMMODAL | MB_SETFOREGROUND
    else:
        # MB_SYSTEMMODAL BİLEREK YOK. O bayrak "bir kez göster ve unut" için
        # doğru; tarayıcı yedeğindeki kutu ise kullanıcı uygulamayı kapatana
        # kadar açık duruyor ve o süre boyunca HER pencerenin üstünde durmak
        # düşmanca olurdu — kullanıcı tarayıcıda çalışmaya çalışıyor.
        bayraklar = MB_ICONINFORMATION | MB_SETFOREGROUND
    # MessageBoxW kutuyu KURAMAZSA 0 döner (bellek yok, oturumda pencere
    # istasyonu yok); kurabildiyse basılan düğmenin kimliği. Sıfır demek
    # "hiç bloklamadı" demek ve tarayıcı yedeği tam olarak o bloklamaya
    # dayanıyor — dönüş değerini yutmak o yedeği sessizce boşa çıkarır.
    return bool(ctypes.windll.user32.MessageBoxW(None, message, title, bayraklar))


def _uyari_goster(title: str, message: str, *, kritik: bool) -> bool:
    """Platforma göre sistem uyarısı; KENDİSİ asla patlamaz. True = kutu çıktı.

    Windows'ta ayrı bir dal ŞART, çünkü `--windowed` pakette stderr yok:
    osascript orada bulunamaz, uyarı hiç çıkmaz ve açılış hatası tamamen
    sessiz kalırdı (v1.8'de `errlog`'u doğuran gerekçenin birebir aynısı).

    DÖNÜŞ DEĞERİ SÜS DEĞİL. Ölümcül uyarı için sonuç önemsiz (süreç zaten
    çıkıyor), ama tarayıcı yedeği süreci ayakta tutmak için bu kutunun
    BLOKLAMASINA dayanıyor. Kutu hiç çizilemediyse — Windows'ta MessageBoxW
    0 döndü, ya da makine ne win32 ne macOS ve `osascript` hiç yok — çağrı
    anında dönüyor ve "gösterdim" demek bir yalan olurdu.
    """
    alert = _alert_windows if sys.platform == "win32" else _alert_macos
    try:
        return bool(alert(title, message, kritik=kritik))
    except Exception:
        return False


def _show_fatal_alert(log_path: str) -> None:
    """Kullanıcıya Türkçe, kritik bir sistem uyarısı gösterir.

    Bu fonksiyon KENDİSİ asla patlamamalı: bir uyarı gösterme denemesi
    başarısız olursa süreç yine de (main() içindeki) sys.exit(1) ile temiz
    çıkmalı.
    """
    _uyari_goster(
        "Kromis Studio başlatılamadı",
        f"Uygulama açılamadı. Hata kaydı: {log_path} "
        "— lütfen bu dosyayı teknik desteğe iletin.",
        kritik=True)


def _tarayici_yedegi(url: str, log_path: str) -> bool:
    """Pencere açılamadıysa uygulamayı TARAYICIDA ayakta tutar. True = tutuldu.

    NEDEN BU YEDEK VAR: `webview.start()` çöktüğünde ÖLEN ŞEY yalnızca native
    pencere yolu. uvicorn ayakta, FastAPI ayakta, uygulamanın tamamı zaten
    HTTP üzerinden çalışıyor ve tarayıcı da bir istemci — `run.sh` uygulamayı
    tam olarak böyle koşturuyor. Windows'ta .NET köprüsü (pythonnet) bu
    yüzden artık uygulamanın YAŞAM ŞARTI değil, yalnızca tercih edilen kabuğu.

    `webbrowser.open` Windows'ta `os.startfile`a düşüyor: yeni bir konsol
    penceresi çakmıyor (`--windowed` pakette bu görünür bir kusur olurdu).

    UYARI KUTUSU SÜSLEME DEĞİL, SÜRECİ AYAKTA TUTAN ŞEY. uvicorn thread'i
    `daemon=True`; ana thread burada bloklanmazsa `_run()` hemen döner, süreç
    ölür ve kullanıcının tarayıcı sekmesi boşluğa bakar. Kullanıcı Tamam'a
    bastığında `_run()`'ın `finally`si sunucuyu temiz kapatıyor.

    Damlalık düğmesi bu modda `window.pywebview.api` bulamıyor ama kayıp yok:
    tarayıcı Chromium tabanlıysa ön yüz kendi `EyeDropper`ına düşüyor.
    """
    try:
        if not webbrowser.open(url):
            return False
    except Exception:
        return False

    # DÖNÜŞ, KUTUNUN GERÇEKTEN BLOKLAMASINA BAĞLI. Koşulsuz `True` şunu
    # saklıyordu: kutu çizilemezse çağrı anında döner, `_run()` biter,
    # `finally: _shutdown()` uvicorn'u kapatır ve az önce açılan sekme
    # "bağlantı reddedildi" gösterir — çıkış kodu 0, ölümcül uyarı yok,
    # hiçbir iz yok. False dönmek `_run()`'daki `raise`ı serbest bırakıyor:
    # kullanıcı hiç değilse ölümcül uyarıyı ve hata.log'u görüyor.
    return _uyari_goster(
        "Kromis Studio tarayıcıda açıldı",
        f"Kromis Studio'nun kendi penceresi açılamadı, uygulama tarayıcınızda açıldı:\n"
        f"{url}\n\n"
        "BU PENCEREYİ KAPATMAYIN — kapattığınızda Kromis Studio da kapanır.\n"
        f"Hata kaydı: {log_path} — lütfen bu dosyayı teknik desteğe iletin.",
        kritik=False)


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


def _onyukle() -> None:
    """Windows .NET köprüsünü açılıştan önce denetler; bulgu varsa loglar.

    `import webview`'DAN ÖNCE koşmak ZORUNDA: `import clr` zincirin ta
    içinde, `webview.start()` çağrılırken tetikleniyor (kullanıcının
    traceback'i: `guilib.initialize` → `import_winforms` → `clr.py`). İndirme
    işareti o andan önce kaldırılmış olmalı, sonra kaldırmanın anlamı yok.

    Temiz bir makinede hiçbir şey yazmıyor — gerekçe `winclr.kayda_deger`.

    YALNIZ PAKETTE. Kaynaktan koşarken `resource_dir()` DEPO KÖKÜ ve orada
    `pythonnet/runtime/Python.Runtime.dll` hiç yok (pythonnet site-packages'ta
    duruyor) — denetim her açılışta "Python.Runtime.dll: YOK" diye YANLIŞ bir
    bulgu üretip depo köküne `hata.log` bırakırdı. Bu, `winclr.kayda_deger`in
    koruduğu sözleşmenin tam tersi: dosyanın varlığı "kötü haber" demek.
    Ölçülen şey PAKETİN içi; kaynak ağacında ölçülecek bir şey yok.
    `--onyukleme-denetimi` kipi bilerek dışarıda — o, kullanıcının AÇIKÇA
    istediği teşhis ve raporunu ayrı dosyaya yazıyor.
    """
    if not paths.is_frozen():
        return

    try:
        bulgu = winclr.onyukle(paths.resource_dir())
        if bulgu:
            _safe_log(bulgu)
    except Exception:
        # Bir ÖNYÜKLEME DENETİMİNİN açılışı engellemesinden kötü sonuç yok.
        # `winclr.onyukle` fırlatmamaya söz veriyor; söze GÜVENİLMİYOR.
        _safe_log(traceback.format_exc())


def _run() -> None:
    _onyukle()

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

    # İSTEK KAYNAĞI KAPISI. Pencere `http://127.0.0.1:{port}` yüklüyor, yani
    # kendi istekleri hem loopback `Host` hem eşleşen `Origin` taşıyor;
    # tarayıcıdaki yabancı bir sayfanın istekleri taşımıyor. Gerekçenin tamamı
    # netguard.py'nin başında. SARMAL, `add_middleware` DEĞİL: `appmod.app`
    # paylaşılan tek nesne ve yerinde değiştirilmemeli (bkz. netguard.sar).
    server, thread, port = start_server(netguard.sar(appmod.app))
    # TEK KAYNAK: pencere de tarayıcı yedeği de aynı adresi kullanmalı. İki
    # ayrı yerde kurulsaydı yedek, sunucunun gerçekte dinlediği porttan
    # başkasını açabilirdi ve kusur yalnız yedeğe DÜŞÜLDÜĞÜNDE görünürdü.
    url = f"http://127.0.0.1:{port}"
    try:
        try:
            # js_api: damlalık için native köprü (bkz. Api). Olmadan
            # `window.pywebview.api` hiç oluşmaz ve WKWebView'da EyeDropper de
            # bulunmadığı için düğme sessizce gizli kalır.
            webview.create_window(WINDOW_TITLE, url,
                                  width=WINDOW_SIZE[0], height=WINDOW_SIZE[1],
                                  min_size=MIN_WINDOW_SIZE, js_api=Api())
            webview.start()
        except Exception:
            # LOG ÖNCE, uyarı sonra: aşağıdaki kutu bloklar ve süreç o sırada
            # (Görev Yöneticisi'nden) öldürülürse geriye kalan tek iz bu kayıt
            # olur. Kabul edilen bedel: yedek de tutmazsa hata.log'a iki kayıt
            # düşer (biri burada, biri `main()`de) — iki kayıt, tek gerçek.
            log_path = _safe_log(traceback.format_exc())
            if not _tarayici_yedegi(url, log_path):
                raise           # yedek de tutmadı → main() ölümcül yola gider
    finally:
        _shutdown(server, thread)


def _onyukleme_kademeleri() -> list[tuple[str, Callable[[], str]]]:
    """Denetimin sırayla denediği kademeler: (ad, çağrılabilir).

    KADEMELİ OLMASI ŞART. Kullanıcının traceback'i BİRİNCİ kademede ölüyor
    (`import clr`), oysa son kademe (`guilib.initialize`) bir masaüstü
    oturumuna dokunuyor ve GitHub runner'ında bizim kusurumuzla İLGİSİZ bir
    sebeple düşebilir. Kalıcı yanlış-kırmızı bir kapı devre dışı bırakılır —
    kademeler ayrı olduğu için kapıyı ilk üçe indirmek tek satırlık karar,
    rapor da nereye kadar gelindiğini yazıyor.
    """
    def _clr():
        import clr
        return getattr(clr, "__file__", "(yol yok)")

    def _winforms_assembly():
        import clr
        clr.AddReference("System.Windows.Forms")
        return "System.Windows.Forms yüklendi"

    def _winforms_modulu():
        import webview.platforms.winforms as wf
        return getattr(wf, "__name__", "?")

    def _backend():
        # `from webview import guilib` DEĞİL — o biçim HER ZAMAN None veriyor.
        # `webview/__init__.py` önce `from webview.guilib import GUIType,
        # initialize` yapıyor (import düzeni alt modülü paketin bir NİTELİĞİ
        # olarak bağlar), sonra 157. satırda `guilib = None` ile o niteliğin
        # ÜSTÜNE yazıyor. Paketten çekilen ad bu yüzden None ve
        # `guilib.initialize()` AttributeError veriyor: kapı 2026-09-04'te tam
        # olarak buna düştü — üstelik ölçmek istediği halka SAĞLAMKEN (ilk üç
        # kademe geçmişti), yani kırmızı kendi kusurumuzdu. Alt modülü doğrudan
        # istemek çakışmayı atlıyor; `webview/__init__.py`nin kendi biçimi de bu.
        from webview.guilib import initialize

        secilen = initialize()
        # SEÇİLEN ARKA UÇ RAPORA YAZILIYOR: WebView2 bulunamazsa pywebview
        # sessizce `mshtml`e düşer ve kapı yeşil kalır. Bir gün oraya düşmek
        # başlı başına bir bulgudur; ancak bu satır sayesinde görünür.
        #
        # AMA MODÜL ADI ONU GÖSTERMEZ: Windows'ta `initialize()` her hâlükârda
        # `webview.platforms.winforms` döner; edgechromium/mshtml seçimi o
        # modülün İÇİNDE, import anında yapılıp `renderer`a yazılıyor
        # (winforms.py: `_is_chromium()` → 'edgechromium' | 'mshtml').
        # `webview/__init__.py:249` da renderer'ı oradan okuyor. Yani yukarıdaki
        # gerekçeyi gerçekten taşıyan alan bu ikincisi.
        return (f"{getattr(secilen, '__name__', repr(secilen))} "
                f"(renderer={getattr(secilen, 'renderer', '?')})")

    return [
        ("import clr", _clr),
        ("clr.AddReference(System.Windows.Forms)", _winforms_assembly),
        ("import webview.platforms.winforms", _winforms_modulu),
        ("webview.guilib.initialize()", _backend),
    ]


def _onyukleme_denetimi() -> int:
    """Pencere AÇMADAN .NET/GUI zincirini dener; raporu yazar, çıkış kodu döner.

    0 = zincir sağlam, 1 = bir kademe düştü, 2 = rapor bile yazılamadı.

    NEDEN DOSYA + ÇIKIŞ KODU: paket `console=False`, yani stdout YOK. Raporun
    tek çıkış yolu bir dosya, sonucun tek sinyali çıkış kodu. Bu kip iki işi
    birden görüyor — `_paket-windows.yml`'deki açılış kapısı ve kullanıcı
    desteği ("şunu koştur, çıkan dosyayı gönder").

    Bu kipte ölümcül uyarı BİLEREK gösterilmiyor: `MessageBoxW` modal ve CI
    runner'ında sonsuza kadar beklerdi.
    """
    satirlar = [
        "[Kromis Studio önyükleme denetimi]",
        f"sürüm      : {version.APP_VERSION}",
        f"platform   : {sys.platform}",
        f"frozen     : {paths.is_frozen()}",
        f"yorumlayıcı: {sys.executable}",
        f"paket kökü : {paths.resource_dir()}",
        f"veri kökü  : {paths.data_dir()}",
        "",
    ]

    try:
        satirlar.append(winclr.rapor(winclr.topla(paths.resource_dir())))
    except Exception:
        satirlar.append("[.NET köprüsü denetimi çöktü]\n" + traceback.format_exc())
    satirlar.append("")

    kod = 0
    for ad, adim in _onyukleme_kademeleri():
        try:
            satirlar.append(f"[GEÇTİ] {ad} → {adim()}")
        except Exception:
            satirlar.append(f"[DÜŞTÜ] {ad}\n{traceback.format_exc()}")
            kod = 1
            break       # sonraki kademeler bu halkaya dayanıyor; devam anlamsız

    rapor = "\n".join(satirlar)
    try:
        os.makedirs(paths.data_dir(), exist_ok=True)
        # `encoding` ZORUNLU (tests/test_encoding_contract.py). `newline`
        # varsayılan bırakılıyor — bu dosyayı Not Defteri açacak, orada CRLF
        # doğru tercih (graf üreticisinin `newline="\n"` kararının tersi;
        # orada bayt kararlılığı gerekiyordu, burada okunabilirlik).
        with open(os.path.join(paths.data_dir(), ONYUKLEME_RAPORU),
                  "w", encoding="utf-8") as f:
            f.write(rapor + "\n")
    except Exception:
        return 2

    if kod:
        # Kullanıcıdan TEK dosya istemek yeterli olsun: kusur hata.log'a da
        # düşüyor, çünkü KURULUM.md yıllardır o dosyayı istiyor.
        _safe_log(rapor)
    return kod


def _onyukleme_denetimi_guvenli() -> int:
    """`_onyukleme_denetimi`'nin kendisi patlarsa bile bir çıkış kodu üretir."""
    try:
        return _onyukleme_denetimi()
    except Exception:
        _safe_log(traceback.format_exc())
        return 2


def main(argv: list[str] | None = None) -> None:
    """`_run()`'ı çalıştırır; her hatayı loglar + kullanıcıya gösterir.

    Neden gerekli: paket `--windowed` olduğu için hiçbir stderr görünmez.
    Sarmalama olmadan kullanıcı yalnızca Dock ikonunun bir kez zıplayıp
    kaybolduğunu görür, ne olduğunu asla öğrenemez — ve onu destekleyecek
    kişi de (terminal kullanamıyor) öğrenemez.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    # `argparse` DEĞİL, düz üyelik testi. İki gerekçe: (1) `console=False`
    # pakette argparse'ın usage/hata çıktısı stderr'e gider, yani GÖRÜNMEZ ve
    # üstüne `SystemExit(2)` ile açılışı öldürür; (2) Explorer kısayolları ve
    # sürükle-bırak beklenmedik argüman geçirebiliyor — hiçbir argüman
    # uygulamanın normal açılışını engellememeli.
    if ONYUKLEME_BAYRAGI in args:
        sys.exit(_onyukleme_denetimi_guvenli())

    try:
        _run()
    except Exception:
        log_path = _safe_log(traceback.format_exc())
        _show_fatal_alert(log_path)
        sys.exit(1)


if __name__ == "__main__":
    main()
