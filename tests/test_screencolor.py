"""screencolor.pick — ekran renk seçicisinin GUI'siz test edilebilen kısmı.

Neden bu dosya var: damlalık paket içinde bir AppKit çağrısına dayanıyor ve
AppKit UI'ı ana thread'de çalışmak zorunda. Riskli mantık (bekleme, iptal,
zaman aşımı, sRGB dönüşümü) sampler'ın KENDİSİNDEN ayrıldı ve enjekte
ediliyor — böylece pencere hiç açılmadan ölçülebiliyor. desktop.py'nin
"pencere kısmı manuel, gerisi sahte modülle test" deseninin aynısı.

Ana thread'e gönderim (`show_sampler_on_main_thread`) burada test EDİLMİYOR:
o gerçekten NSApplication çalışma döngüsü ister, paketin içinde elle
doğrulanıyor.
"""
import threading

import pytest

import screencolor


class _FakeColor:
    """NSColor yerine geçer; sRGB'ye dönüştürülmeden bileşen vermeyi REDDEDER.

    Gerçek NSColor'ın davranışını taklit ediyor: katalog/desen renklerinde
    `redComponent()` doğrudan çağrılırsa istisna fırlar. Dönüşüm adımı
    atlanırsa bu sahte nesne de patlar — yani test, dönüşümün varlığını
    yalnızca "çağrıldı mı" diye değil, gerçekten gerekli olduğu için ölçüyor.
    """

    def __init__(self, rgb=(0.784, 0.416, 0.235), *, converted=False):
        self._rgb = rgb
        self._converted = converted

    def colorUsingColorSpace_(self, _space):
        return _FakeColor(self._rgb, converted=True)

    def _component(self, index):
        if not self._converted:
            raise ValueError("renk uzayı dönüştürülmedi")
        return self._rgb[index]

    def redComponent(self):
        return self._component(0)

    def greenComponent(self):
        return self._component(1)

    def blueComponent(self):
        return self._component(2)


def test_to_hex_converts_through_srgb_first():
    """Dönüşüm atlanırsa katalog renklerinde bileşen okuması patlar."""
    assert screencolor.to_hex(_FakeColor((1.0, 0.0, 0.0))) == "#ff0000"
    assert screencolor.to_hex(_FakeColor((0.0, 0.0, 0.0))) == "#000000"
    assert screencolor.to_hex(_FakeColor((1.0, 1.0, 1.0))) == "#ffffff"


def test_to_hex_rounds_instead_of_truncating():
    """0.5/255 sınırında kırpma yapılırsa seçilen renk bir ton kayar.

    Kullanıcı damlalıkla aldığı rengin birebir aynısını beklediği için
    (palet önerileri o tohumdan üretiliyor) bu kayma sessiz ama gerçek.
    """
    # 0.5 * 255 = 127.5 → yuvarlama 128, kırpma 127
    assert screencolor.to_hex(_FakeColor((0.5, 0.5, 0.5))) == "#808080"


def test_pick_returns_the_selected_color_as_hex():
    def show(handler):
        handler(_FakeColor((0.784, 0.416, 0.235)))

    assert screencolor.pick(show_sampler=show) == "#c86a3c"


def test_pick_returns_none_when_the_user_cancels():
    """İptalde handler `None` ile çağrılır — hata değil, seçim yok."""
    assert screencolor.pick(show_sampler=lambda handler: handler(None)) is None


def test_pick_returns_none_on_timeout_instead_of_hanging_forever():
    """SIZAN THREAD'E KARŞI ASIL GUARD.

    `showSamplerWithSelectionHandler_`'ın iptalde handler'ı çağırıp
    çağırmadığı belgelenmemiş. Çağırmıyorsa, zaman aşımı olmadan pywebview'ın
    js_api thread'i sonsuza kadar asılır ve her iptal bir thread sızdırır —
    uygulama kapanana kadar birikir.
    """
    before = threading.active_count()
    assert screencolor.pick(show_sampler=lambda handler: None, timeout=0.05) is None
    assert threading.active_count() <= before


def test_pick_returns_none_when_the_handler_fires_late():
    """Zaman aşımından SONRA gelen handler çağrısı patlamamalı.

    Sampler bir kez gecikirse `pick` çoktan None dönmüştür; handler o noktada
    hâlâ ana thread'de tetiklenebilir ve ölü bir Event'e yazar. Bu bir hata
    değil, sessizce yutulmalı — aksi halde AppKit'in içinde yakalanmayan bir
    istisna kalır.
    """
    captured = {}

    def show(handler):
        captured["handler"] = handler

    assert screencolor.pick(show_sampler=show, timeout=0.05) is None
    captured["handler"](_FakeColor())  # geç gelen çağrı: patlamamalı


def test_pick_propagates_nothing_when_the_sampler_itself_explodes():
    """Sampler'ı gösterme denemesi patlarsa `pick` None döner, fırlatmaz.

    Köprünün üstündeki katman (desktop.Api) da yakalıyor, ama iki kapı
    bilinçli: bir renk seçme denemesi hiçbir koşulda uygulamayı düşürmemeli.
    """
    def boom(_handler):
        raise RuntimeError("sampler gösterilemedi")

    assert screencolor.pick(show_sampler=boom, timeout=0.05) is None


def test_pick_survives_a_color_that_cannot_be_converted():
    """Dönüşüm/okuma patlarsa seçim kaybolur ama uygulama ayakta kalır."""
    class _Hostile:
        def colorUsingColorSpace_(self, _space):
            return None

    assert screencolor.pick(show_sampler=lambda h: h(_Hostile()),
                            timeout=0.05) is None


@pytest.mark.parametrize("rgb", [(-0.2, 0.5, 1.4), (2.0, -1.0, 0.5)])
def test_to_hex_clamps_out_of_gamut_components(rgb):
    """sRGB dönüşümü gamut dışı bileşen döndürebilir (negatif ya da >1).

    Kırpılmazsa `#-3300ff` gibi bir dize üretilir; palette.parse_hex onu
    reddeder ve kullanıcı damlalığı çalışmıyor sanır.
    """
    hex_value = screencolor.to_hex(_FakeColor(rgb))
    assert len(hex_value) == 7 and hex_value[0] == "#"
    assert all(c in "0123456789abcdef" for c in hex_value[1:])
