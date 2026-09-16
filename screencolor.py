# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Ekrandan renk seçme (damlalık) — macOS'un NSColorSampler'ına köprü.

NEDEN VAR: tarayıcıda damlalık `EyeDropper` API'siyle çalışıyor, ama o API
Chromium'a özel. Paket pywebview kullanıyor ve pywebview'ın macOS arka ucu
WKWebView (WebKit) — orada `window.EyeDropper` YOK, bu yüzden düğme v1.10'a
kadar app'te hiç görünmüyordu. macOS'un kendi büyüteçli seçicisi
(`NSColorSampler`, 10.15+) aynı işi yapıyor: ekranın her yerinden, başka
uygulamaların pencerelerinden de renk alınabiliyor.

THREAD MODELİ — bu dosyanın şeklini belirleyen şey:
  • AppKit UI ana thread'de çalışmak ZORUNDA.
  • uvicorn ayrı bir thread'de koşuyor, yani bir FastAPI ucu sampler'ı
    doğrudan gösteremez.
  • pywebview js_api metotlarını AYRI bir thread'de çağırıyor
    (webview/util.py: "executed in a separate thread to prevent blocking the
    UI thread"). Bekleme bu yüzden orada güvenli: ana döngü kilitlenmiyor.
Akış: js_api thread'i `pick()`'i çağırır → sampler ana kuyruğa gönderilir →
handler ana thread'de tetiklenir → Event kurulur → js_api thread'i hex'i
döndürür → pywebview JS Promise'ini çözer.

`pick()` sampler'ı ENJEKTE ALIYOR: bekleme/iptal/zaman aşımı mantığı böylece
pencere hiç açılmadan test edilebiliyor (tests/test_screencolor.py). AppKit'e
dokunan tek fonksiyon `show_sampler_on_main_thread` ve o elle doğrulanıyor.
"""
from __future__ import annotations

import sys
import threading
from collections.abc import Callable

# Kullanıcı seçiciyi açıp unutabilir; süresiz beklemek js_api thread'ini
# sonsuza kadar tutar. Cömert ama sonlu.
DEFAULT_TIMEOUT = 120.0


def _clamp_component(value: float) -> int:
    """0..1 aralığındaki bileşeni 0..255'e çevirir; gamut dışını kırpar.

    sRGB dönüşümü gamut dışı bir bileşen döndürebilir (negatif ya da >1).
    Kırpılmazsa `#-3300ff` gibi bir dize üretilir, `palette.parse_hex` onu
    reddeder ve kullanıcı damlalığın bozuk olduğunu düşünür.

    Yuvarlama, kırpma DEĞİL: 0.5 → 128 (127 değil). Alınan rengin birebir
    aynısı bekleniyor, çünkü palet önerileri o tohumdan üretiliyor.
    """
    return max(0, min(255, round(value * 255)))


def to_hex(ns_color) -> str:
    """NSColor → `#rrggbb`.

    `colorUsingColorSpace_(sRGB)` ZORUNLU: katalog ve desen renklerinde
    bileşen okuması dönüşüm olmadan istisna fırlatır. Dönüşüm None dönerse
    (dönüştürülemeyen renk) çağıran taraf yakalar.
    """
    try:
        import AppKit
        srgb_space = AppKit.NSColorSpace.sRGBColorSpace()
    except (ImportError, ModuleNotFoundError):
        srgb_space = None

    if srgb_space is not None:
        srgb = ns_color.colorUsingColorSpace_(srgb_space)
    elif hasattr(ns_color, "colorUsingColorSpace_"):
        srgb = ns_color.colorUsingColorSpace_(None)
    else:
        srgb = ns_color

    if srgb is None:
        raise ValueError("renk sRGB'ye dönüştürülemedi")
    return f"#{_clamp_component(srgb.redComponent()):02x}{_clamp_component(srgb.greenComponent()):02x}{_clamp_component(srgb.blueComponent()):02x}"


def show_sampler_on_main_thread(handler: Callable[[object | None], None]) -> None:
    """NSColorSampler'ı ANA thread'de gösterir; seçilen NSColor'ı handler'a verir.

    AppKit'e dokunan tek yer. `performSelectorOnMainThread_` yerine
    `NSOperationQueue.mainQueue()` kullanıldı: blok tabanlı API pyobjc'de
    ek bir NSObject alt sınıfı ve selector kaydı gerektirmiyor.

    `waitUntilFinished` YOK: burada beklemek çağıran thread'i sampler
    kapanana kadar tutar ve zaman aşımını anlamsız kılardı — bekleme
    `pick()`'in Event'inde, tek yerde.

    macOS DIŞINDA hemen `handler(None)`: Windows'ta bu köprü hiç gerekmiyor,
    çünkü WebView2 Chromium tabanlı ve `window.EyeDropper` orada VAR — damlalık
    tarayıcı API'siyle çalışıyor (bkz. static/palette.js). Kapı `import AppKit`
    hatasına bırakılmadı: platform kontrolü açıkça yazılınca niyet okunuyor ve
    AppKit'i başka bir sebeple import edilebilir kılan bir ortam sessizce yanlış
    yola girmiyor.
    """
    if sys.platform != "darwin":
        handler(None)
        return

    try:
        import AppKit
    except (ImportError, ModuleNotFoundError):
        handler(None)
        return

    def _present() -> None:
        AppKit.NSColorSampler.alloc().init().showSamplerWithSelectionHandler_(handler)

    AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(_present)


def pick(*, show_sampler: Callable[[Callable[[object | None], None]], None] | None = None,
         timeout: float = DEFAULT_TIMEOUT) -> str | None:
    """Ekrandan bir renk seçtirir; `#rrggbb` ya da seçim yoksa None döner.

    None dönen HER durum normaldir ve sessizdir: kullanıcı iptal etti, süre
    doldu, ya da renk okunamadı. Damlalık bir kolaylık — hiçbir arıza modu
    uygulamayı düşürmemeli, arayüz de sadece hiçbir şey olmamış gibi davranır.

    ÇAĞIRAN THREAD ANA THREAD OLMAMALI: burada beklemek ana döngüyü
    kilitlerdi ve handler hiç tetiklenemezdi. pywebview js_api'yi ayrı bir
    thread'de çalıştırdığı için bu sağlanıyor (bkz. modül başlığı).
    """
    if show_sampler is None:
        show_sampler = show_sampler_on_main_thread

    done = threading.Event()
    result: dict[str, str] = {}

    def _handler(ns_color) -> None:
        # Zaman aşımından SONRA da tetiklenebilir: `pick` çoktan None
        # döndürmüştür ve buraya yazılan değer okunmaz. Yine de patlamamalı —
        # bu blok AppKit'in içinde koşuyor, oradaki yakalanmayan bir istisna
        # teşhis edilemez.
        try:
            if ns_color is not None:
                result["hex"] = to_hex(ns_color)
        except Exception:
            pass
        finally:
            done.set()

    try:
        show_sampler(_handler)
    except Exception:
        return None

    if not done.wait(timeout):
        return None
    return result.get("hex")
