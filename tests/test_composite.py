"""composite.py, dış composite-logo.py ile AYNI GÖRÜNTÜYÜ üretmeli.

Karşılaştırma **piksel** düzeyinde, bayt düzeyinde değil. İlk sürüm bayt
eşitliği arıyordu; golden'lar x86_64'te üretildiği ve PNG kodlayıcısı
platformlar arası bayt bayt yeniden üretilebilir OLMADIĞI için (Pillow'un
tekerlekleri farklı deflate kütüphaneleriyle derleniyor) bu değişmez taşınabilir
değildi. 2026-07-29'da arm64 runner'ında ölçüldü (Actions run 30402056066):
altı vakanın da pikselleri birebir aynı, sıkıştırılmış baytları farklı — yani
port doğru, iddia fazla katıydı. Planın Task 2 / Step 7 notu bu durumda
karşılaştırmayı piksel eşitliğine indirmeyi öngörüyordu.

Piksellerin farklı çıkması ise HÂLÂ durdurucu bir hatadır: port matematiği
kaydırmış demektir, dış script ile satır satır karşılaştırılmalı.
"""
import io
import json
import os
from typing import Any

import pytest
from PIL import Image

import composite

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "logo")
# Bu iki PNG bir zamanlar pakete gömülü yerleşik logolardı; uygulama marka-nötr
# olunca (yerleşik logo ve mavi/beyaz varyant seçimi kaldırıldı) paketten çıkıp
# YALNIZCA golden'ların girdisi olarak burada kaldılar. Golden PNG'ler onların
# piksellerini taşıdığı için başka bir görselle değiştirilemezler.
LOGO_BLUE = os.path.join(FIXTURES, "yerlesik-logo-blue.png")
LOGO_WHITE = os.path.join(FIXTURES, "yerlesik-logo-white.png")
OVERLAY = os.path.join(FIXTURES, "overlay.png")
# cases.json'daki `logo` alanı → dosya. Dış script her vakada fiilen hangi
# dosyayı bindirdiyse o; composite_logo tek `logo_path` aldığı için test onu
# doğrudan geçiyor ve pikseller birebir korunuyor.
LOGO_BY_NAME = {"blue": LOGO_BLUE, "white": LOGO_WHITE, "overlay": OVERLAY}

# Vakaların tek kaynağı üreticinin yazdığı manifest — elle ikinci bir liste
# tutulsa golden'lar sessizce yanlış vakayla eşleşebilirdi.
with open(os.path.join(FIXTURES, "cases.json"), encoding="utf-8") as _f:
    CASES = json.load(_f)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_port_matches_the_external_script(case: dict) -> None:
    name, base = case["name"], case["base"]
    produced = composite.composite_logo(
        os.path.join(FIXTURES, f"{base}.png"),
        logo_path=LOGO_BY_NAME[case["logo"]],
        position=case["position"], scale=case["scale"],
        shadow_alpha=case["shadow_alpha"], shadow_blur=case["shadow_blur"])

    golden_path = os.path.join(FIXTURES, f"golden-{name}.png")
    a = Image.open(io.BytesIO(produced)).convert("RGB")
    b = Image.open(golden_path).convert("RGB")

    assert a.size == b.size, f"{name}: boyut değişti {a.size} != {b.size}"
    assert a.tobytes() == b.tobytes(), f"{name}: PİKSELLER değişti — port davranışı kaydırdı"


@pytest.mark.parametrize("position,expected", [
    ("top-left", (10, 10)),
    ("top-right", (100 - 20 - 10, 10)),
    ("bottom-left", (10, 80 - 15 - 10)),
    ("bottom-right", (100 - 20 - 10, 80 - 15 - 10)),
    ("center", ((100 - 20) // 2, (80 - 15) // 2)),
    ("top-center", ((100 - 20) // 2, 10)),
    ("center-left", (10, (80 - 15) // 2)),
    ("bottom-center", ((100 - 20) // 2, 80 - 15 - 10)),
    ("center-right", (100 - 20 - 10, (80 - 15) // 2)),
])
def test_paste_position_covers_the_nine_grid(position: str, expected: tuple[int, int]) -> None:
    assert composite.paste_position(100, 80, 20, 15, position, 10) == expected


def test_returns_png_bytes_without_touching_disk() -> None:
    """PNG bayt döner; fixtures dizinine ve cwd'ye hiçbir şey yazmaz.

    Önceki sürüm boş bir tmp_path'in boş kaldığını doğruluyordu — composite_logo
    zaten o dizinden habersizdi, dolayısıyla iddia her koşulda geçerdi. Burada
    fonksiyonun gerçekten dokunabileceği iki yerin (fixtures dizini, cwd)
    çağrı öncesi/sonrası içerikleri karşılaştırılıyor.
    """
    fixtures_before = set(os.listdir(FIXTURES))
    cwd_before = set(os.listdir(os.getcwd()))
    out = composite.composite_logo(
        os.path.join(FIXTURES, "base-light.png"),
        logo_path=LOGO_BLUE)
    assert out[:8] == b"\x89PNG\r\n\x1a\n"
    assert set(os.listdir(FIXTURES)) == fixtures_before
    assert set(os.listdir(os.getcwd())) == cwd_before


def test_missing_base_raises_oserror() -> None:
    with pytest.raises(OSError):
        composite.composite_logo("/yok/boyle/bir/dosya.png",
                                 logo_path=LOGO_BLUE)


def test_composite_logo_rejects_invalid_position() -> None:
    with pytest.raises(ValueError):
        composite.composite_logo(
            os.path.join(FIXTURES, "base-light.png"),
            logo_path=LOGO_BLUE,
            position="bottom_right")  # alt çizgi yazım hatası — tireli değil


# ── Kaydırma (offset): ızgara noktası çapa, offset ondan sapma ────────

def test_offset_limit_matches_the_request_model() -> None:
    """models.py composite'i import ETMİYOR (kendi docstring'indeki gerekçe:
    konum kümesi de orada kopyalanmış). Kopyalanan sabit kayabilir:
    uçtaki sınır daha geniş olursa geçerli sayılan bir istek composite'te
    ValueError'a düşer ve kullanıcı ayarın nedenini anlamadığı Türkçe bir 500
    görür. Bu tripwire o kaymayı ucuza yakalar.
    """
    import models

    assert models.LOGO_OFFSET_LIMIT == composite.OFFSET_LIMIT


def test_offset_zero_is_a_no_op_for_paste_position() -> None:
    """GOLDEN'LARIN BEKÇİSİ: varsayılan kaydırma çapayı zerre oynatmamalı.

    Golden fixture'lar repo DIŞINDAKİ composite-logo.py'den üretildi
    (tools/make_logo_goldens.py) ve o script kaydırmayı bilmiyor. Yani
    `offset=0` yolunun matematiği değişmez olmak ZORUNDA. Bu iddia golden
    testinde de dolaylı olarak var, ama orada hata mesajı "pikseller değişti"
    diyor; burada hangi fonksiyonun kaydığını doğrudan söylüyor.
    """
    for position in composite.POSITIONS:
        assert (composite.paste_position(100, 80, 20, 15, position, 10)
                == composite.paste_position(100, 80, 20, 15, position, 10, 0, 0)), position


def test_offset_moves_the_logo_by_the_given_pixels() -> None:
    anchor = composite.paste_position(100, 80, 20, 15, "center", 10)
    moved = composite.paste_position(100, 80, 20, 15, "center", 10, 5, -6)
    assert moved == (anchor[0] + 5, anchor[1] - 6)


@pytest.mark.parametrize("offset,expected", [
    ((999, 999), (100 - 20, 80 - 15)),   # sağ/alt kenarda durur
    ((-999, -999), (0, 0)),              # sol/üst kenarda durur
])
def test_offset_clamps_at_the_frame_edge(offset: tuple[int, int],
                                         expected: tuple[int, int]) -> None:
    """Kullanıcı kararı: logo görselin dışına ASLA taşmaz, kenarda durur.

    `_composite_banner`'ın `margin` clamp'iyle (app.py) aynı mantık — o da
    banner'ı kenar dışına çıkarmıyor.
    """
    assert composite.paste_position(100, 80, 20, 15, "center", 10, *offset) == expected


def test_offset_never_produces_negative_coordinates_when_logo_exceeds_base() -> None:
    """Logo tabandan büyükse serbest alan NEGATİF olur.

    Tek katmanlı bir `min(v, img_w - logo_w)` bu durumda -30 gibi bir
    koordinat üretir ve logo kadrajın dışına yerleşirdi. Clamp'in içindeki
    ikinci `max(0, ...)` tam bunun için var.
    """
    assert composite.paste_position(50, 40, 80, 60, "center", 0, 30, 30) == (0, 0)


@pytest.mark.parametrize("bad", [{"offset_x": 0.9}, {"offset_y": -0.9}])
def test_composite_logo_rejects_out_of_range_offset(bad: dict) -> None:
    """position gibi offset de erken ve gürültülü reddedilir.

    Uçtaki Pydantic sınırı (LogoRequest ±0.5) tek kapı olsaydı, composite'i
    doğrudan çağıran herhangi bir yol (ör. blog routine'i bu modülü import
    etseydi) sessizce clamp'lenmiş bir sonuç alırdı.
    """
    with pytest.raises(ValueError):
        composite.composite_logo(
            os.path.join(FIXTURES, "base-light.png"),
            logo_path=LOGO_BLUE, **bad)


def test_offset_changes_the_rendered_pixels() -> None:
    """Parametre sessizce yutulmasın: kaydırma çıktıyı gerçekten oynatmalı.

    Yalnız `paste_position`'ı test etmek yetmez — `composite_logo` offset'i
    oradan geçirmeyi unutsa birim testler yeşil kalır, kullanıcı slider'ı
    sürükler ve hiçbir şey olmaz.
    """
    base = os.path.join(FIXTURES, "base-light.png")
    shared: dict[str, Any] = {"logo_path": LOGO_BLUE}  # `**shared` sayısal alanlara da açılıyor
    plain = composite.composite_logo(base, **shared)
    moved = composite.composite_logo(base, offset_x=-0.1, offset_y=-0.1, **shared)

    a = Image.open(io.BytesIO(plain)).convert("RGB")
    b = Image.open(io.BytesIO(moved)).convert("RGB")
    assert a.size == b.size
    assert a.tobytes() != b.tobytes()
