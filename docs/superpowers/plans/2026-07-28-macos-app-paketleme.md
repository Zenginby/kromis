# macOS Uygulaması Olarak Paketleme (v1.8) — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GPT-Image Studio'yu, terminal kullanamayan ofis çalışanlarının çift tıklayıp kullanabileceği, kendi penceresinde açılan bir macOS uygulamasına (`GPT-Image Studio.app`) dönüştürmek.

**Architecture:** FastAPI/uvicorn sunucusu `desktop.py` tarafından boş bir portta daemon thread'de başlatılır ve native WKWebView penceresinde (pywebview) gösterilir. Repo dışındaki `composite-logo.py` süreç içi `composite.py` modülüne port edilir (golden fixture'larla korunarak). Yazılabilir veri, paket içinde `~/Library/Application Support/GPT-Image Studio/` altına taşınır; geliştirmede yollar bugünküyle birebir aynı kalır. PyInstaller ile arm64 `.app` derlenir, ad-hoc imzalanır, zip olarak dağıtılır.

**Tech Stack:** Python 3.14.6, FastAPI, uvicorn, Pillow 11, pywebview 6.2.1 (pyobjc/WebKit), PyInstaller 6.21.0, pytest.

**Tasarım:** `docs/superpowers/specs/2026-07-28-macos-app-paketleme-design.md`

## Global Constraints

- Hedef **macOS**. Windows, universal2, notarization kapsam dışı.
- ⚠️ **Mimari (Task 6'da düzeltildi):** ofis makineleri arm64, ama **derleme
  makinesi Intel'dir** (`uname -m` → `x86_64`, iMac20,2). PyInstaller çapraz
  derleme yapamaz. İki hat: yerel **x86_64** derlemesi doğrulama için (Intel'de
  nativ çalışır → paketleme yolu uçtan uca sınanabilir), **GitHub Actions arm64**
  runner'ı gönderim paketi için. `build.sh` mimariyi host'tan almalı, sabitlemek
  yerine.
- Kod imzalama kimliği **yok** → yalnızca ad-hoc imza (`codesign --sign -`).
- Python **3.14.6**; bağımlılıklar `requirements.txt`'te pinli kalır. Yeni: `pywebview==6.2.*` (runtime), `pyinstaller==6.21.*` (yalnız build, `requirements-dev.txt`).
- **Test tabanı: 599 test** (`.venv/bin/python -m pytest tests/ -q`). Task 3'te 10 test bilinçli olarak yeniden yazılır; onun dışında hiçbir mevcut test elden geçmez ve suite her task sonunda **tamamen yeşil** olmalı.
- Hiçbir test ağa çıkmaz — Azure ve thecolorapi mock'lanır. Bu kural bozulmaz.
- Geliştirme modunda (`sys.frozen` yok) çözülen yollar bugünküyle **birebir aynı** olmalı; testler `app.OUTPUT_DIR`'ı çağrı anında monkeypatch ediyor, bu davranış korunur.
- Kod stili: PEP 8, tüm fonksiyon imzalarında type annotation, dosya başına 800 satır sınırı, mutasyon yerine yeni nesne.
- Kullanıcıya görünen tüm metin **Türkçe**.
- Dış `~/.config/claude-tools/composite-logo.py` **silinmez ve değiştirilmez** — blog routine'i onu kullanıyor.
- Commit mesajları conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`).

---

## Dosya yapısı

| Dosya | Durum | Sorumluluk |
|---|---|---|
| `paths.py` | yeni | frozen/dev yol çözümü, veri dizini oluşturma, gömülü logo yolları |
| `composite.py` | yeni | logo/motto filigranı bindirme (saf görüntü matematiği, I/O'su yalnız aç/kaydet) |
| `desktop.py` | yeni | uvicorn'u thread'de başlat + pywebview penceresi + kapanış |
| `seed.py` | yeni | ilk açılışta gömülü KURUM logolarını kullanıcı kütüphanesine tohumla |
| `bundled/logos/kurum-logo-{blue,white}.png` | yeni (commit) | pakete gömülen KURUM logoları |
| `gpt-image-studio.spec` | yeni | PyInstaller yapılandırması |
| `build.sh` | yeni | derle → ad-hoc imzala → zip |
| `KURULUM.md` | yeni | son kullanıcı talimatı (Türkçe) |
| `requirements-dev.txt` | yeni | build-only bağımlılıklar |
| `app.py` | değişir | `subprocess`/`tempfile` yerine `composite`; `BASE_DIR` türevleri yerine `paths` |
| `requirements.txt` | değişir | `pywebview` eklenir |
| `tests/test_paths.py`, `tests/test_composite.py`, `tests/test_seed.py`, `tests/test_desktop.py` | yeni | ilgili task'ların testleri |
| `tests/test_logo.py`, `tests/test_folders.py`, `tests/test_palette_route.py` | değişir | `subprocess` mock'u → `composite` mock'u (10 test) |
| `run.sh` | değişmez | geliştirme yolu korunur |

---

### Task 1: `paths.py` — frozen/dev yol çözümü

**Files:**
- Create: `paths.py`
- Create: `tests/test_paths.py`
- Modify: `app.py:33-36` (yol sabitleri), `app.py:7` (import bloğu)

**Interfaces:**
- Produces:
  - `APP_NAME: str = "GPT-Image Studio"`
  - `REPO_DIR: str` — bu dosyanın bulunduğu dizin
  - `is_frozen() -> bool`
  - `resource_dir() -> str` — salt-okunur paket içeriği kökü
  - `data_dir() -> str` — yazılabilir kullanıcı verisi kökü
  - `output_dir() -> str`, `assets_dir() -> str`, `static_dir() -> str`
  - `bundled_logos_dir() -> str`, `builtin_logo(variant: str) -> str`
  - `ensure_data_dirs() -> None`
- Consumes: yok (ilk task)

- [ ] **Step 1: Testleri yaz (başarısız olacak)**

`tests/test_paths.py`:

```python
import os
import sys

import paths


def test_dev_mode_paths_match_the_repo_layout():
    """Geliştirmede yollar bugünküyle birebir aynı olmalı (599 testin dayandığı varsayım)."""
    assert not paths.is_frozen()
    assert paths.data_dir() == paths.REPO_DIR
    assert paths.resource_dir() == paths.REPO_DIR
    assert paths.output_dir() == os.path.join(paths.REPO_DIR, "output")
    assert paths.assets_dir() == os.path.join(paths.REPO_DIR, "assets")
    assert paths.static_dir() == os.path.join(paths.REPO_DIR, "static")


def test_dev_mode_matches_app_module_constants():
    """app.py'nin sabitleri paths.py ile aynı yerleri göstermeli."""
    import app as appmod
    assert appmod.OUTPUT_DIR == paths.output_dir()
    assert appmod.STATIC_DIR == paths.static_dir()
    assert appmod.ASSETS_DIR == paths.assets_dir()


def test_frozen_mode_writes_under_application_support(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass-test", raising=False)

    expected_data = os.path.join(
        os.path.expanduser("~/Library/Application Support"), "GPT-Image Studio")
    assert paths.is_frozen()
    assert paths.data_dir() == expected_data
    assert paths.output_dir() == os.path.join(expected_data, "output")
    assert paths.assets_dir() == os.path.join(expected_data, "assets")


def test_frozen_mode_reads_resources_from_meipass(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass-test", raising=False)

    assert paths.resource_dir() == "/tmp/meipass-test"
    assert paths.static_dir() == "/tmp/meipass-test/static"
    assert paths.bundled_logos_dir() == "/tmp/meipass-test/bundled/logos"


def test_builtin_logo_resolves_both_variants():
    assert paths.builtin_logo("blue").endswith("bundled/logos/kurum-logo-blue.png")
    assert paths.builtin_logo("white").endswith("bundled/logos/kurum-logo-white.png")


def test_builtin_logo_rejects_unknown_variant():
    import pytest
    with pytest.raises(ValueError):
        paths.builtin_logo("kirmizi")


def test_ensure_data_dirs_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: str(tmp_path / "veri"))

    paths.ensure_data_dirs()
    (tmp_path / "veri" / "output" / "dokunma.txt").write_text("kalmalı")
    paths.ensure_data_dirs()  # ikinci çağrı hiçbir şeyi silmemeli

    assert (tmp_path / "veri" / "output").is_dir()
    assert (tmp_path / "veri" / "assets").is_dir()
    assert (tmp_path / "veri" / "output" / "dokunma.txt").read_text() == "kalmalı"
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını gör**

Run: `.venv/bin/python -m pytest tests/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'paths'`

- [ ] **Step 3: `paths.py`'yi yaz**

```python
"""Yol çözümü: PyInstaller paketi içinde ve geliştirmede farklı kökler.

Paket içinde `__file__` geçici çıkarma dizinine düşer; oraya yazılan geçmiş her
kapanışta kaybolur. Bu yüzden yazılabilir veri (output/, assets/) kullanıcının
Application Support dizinine, salt-okunur içerik (static/, bundled/) ise
PyInstaller'ın `sys._MEIPASS` dizinine bağlanır.

Geliştirmede (frozen değilken) her iki kök de repo dizinidir — mevcut testlerin
dayandığı yerleşim birebir korunur.
"""
from __future__ import annotations

import os
import sys

APP_NAME = "GPT-Image Studio"
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
_LOGO_VARIANTS = ("blue", "white")


def is_frozen() -> bool:
    """PyInstaller paketi içinde mi çalışıyoruz?"""
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> str:
    """Salt-okunur paket içeriğinin kökü (static/, bundled/)."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", REPO_DIR)
    return REPO_DIR


def data_dir() -> str:
    """Yazılabilir kullanıcı verisinin kökü (output/, assets/, manifest'ler)."""
    if is_frozen():
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    return REPO_DIR


def output_dir() -> str:
    return os.path.join(data_dir(), "output")


def assets_dir() -> str:
    return os.path.join(data_dir(), "assets")


def static_dir() -> str:
    return os.path.join(resource_dir(), "static")


def bundled_logos_dir() -> str:
    return os.path.join(resource_dir(), "bundled", "logos")


def builtin_logo(variant: str) -> str:
    """Gömülü KURUM logosunun yolu. variant: "blue" | "white"."""
    if variant not in _LOGO_VARIANTS:
        raise ValueError(f"geçersiz logo varyantı: {variant!r}")
    return os.path.join(bundled_logos_dir(), f"kurum-logo-{variant}.png")


def ensure_data_dirs() -> None:
    """Yazılabilir dizinleri oluşturur; var olanlara dokunmaz."""
    for path in (output_dir(), assets_dir()):
        os.makedirs(path, exist_ok=True)
```

- [ ] **Step 4: Testleri çalıştır — `test_dev_mode_matches_app_module_constants` hariç geçmeli**

Run: `.venv/bin/python -m pytest tests/test_paths.py -v`
Expected: `test_dev_mode_matches_app_module_constants` PASS (app.py zaten aynı yerleri gösteriyor), diğerleri PASS. Hepsi geçmeli.

- [ ] **Step 5: `app.py`'yi `paths.py`'ye bağla**

`app.py:33-36`'daki bloğu değiştir:

```python
BASE_DIR = paths.REPO_DIR                    # geriye uyum: mevcut kullanımlar bozulmasın
OUTPUT_DIR = paths.output_dir()
STATIC_DIR = paths.static_dir()
ASSETS_DIR = paths.assets_dir()
```

`COMPOSITE_SCRIPT` satırına **dokunma** (Task 3'te kalkacak). Import bloğuna (`app.py:21-27` alfabetik sıraya) ekle:

```python
import paths
```

Ayrıca `app.py`'nin sonundaki static mount'tan hemen önce yazılabilir dizinleri garanti altına al (`os.makedirs(STATIC_DIR, exist_ok=True)` satırının üstüne):

```python
paths.ensure_data_dirs()
```

- [ ] **Step 6: Tüm suite'i çalıştır — regresyon yok**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS, **606 test** (599 + 7 yeni). Tek bir mevcut test kırılmamalı.

- [ ] **Step 7: Commit**

```bash
git add paths.py tests/test_paths.py app.py
git commit -m "feat: frozen/dev yol çözümü için paths.py

Paket içinde output/ ve assets/ ~/Library/Application Support altına,
static/ ve bundled/ sys._MEIPASS altına çözülür. Geliştirmede yollar
bugünküyle birebir aynı kalır (mevcut 599 test dokunulmadan geçiyor)."
```

---

### Task 2: `composite.py` — dış script'in port'u + golden fixture'lar

**Files:**
- Create: `tools/make_logo_goldens.py` (fixture üretici, bir kez çalıştırılır)
- Create: `tests/fixtures/logo/base-light.png`, `tests/fixtures/logo/base-dark.png`
- Create: `tests/fixtures/logo/golden-*.png` (6 dosya)
- Create: `composite.py`
- Create: `tests/test_composite.py`
- Reference (okunacak, DEĞİŞTİRİLMEYECEK): `~/.config/claude-tools/composite-logo.py`
- Copy from: `/Users/kullanici/Documents/Projects/Claude Code Projects/Website/assets/kurum-logo-{blue,white}.png`

**Interfaces:**
- Consumes: `paths.builtin_logo(variant)` (Task 1)
- Produces:
  - `BRIGHTNESS_THRESHOLD: int = 140`
  - `POSITIONS: list[str]` (9'lu ızgara)
  - `region_box(img_w: int, img_h: int, position: str, frac: float = 0.22) -> tuple[int, int, int, int]`
  - `pick_logo(base: Image.Image, position: str, color: str, logo_blue: str, logo_white: str) -> str`
  - `paste_position(img_w: int, img_h: int, logo_w: int, logo_h: int, position: str, margin_px: int) -> tuple[int, int]`
  - `composite_logo(base_path: str, *, logo_blue: str, logo_white: str, position: str = "bottom-right", color: str = "auto", scale: float = 0.14, margin: float = 0.03, shadow_alpha: int = 120, shadow_blur: int = 6) -> bytes`

- [ ] **Step 1: Gömülü logoları repoya al**

```bash
cd "/Users/kullanici/Documents/Projects/Claude Code Projects/gpt-image-studio"
mkdir -p bundled/logos
cp "/Users/kullanici/Documents/Projects/Claude Code Projects/Website/assets/kurum-logo-blue.png" bundled/logos/
cp "/Users/kullanici/Documents/Projects/Claude Code Projects/Website/assets/kurum-logo-white.png" bundled/logos/
ls -la bundled/logos/
```

Expected: iki dosya, her biri ~300 KB. `assets/` gitignore'da; `bundled/` **gitignore'da değil** — kontrol et: `git check-ignore -v bundled/logos/kurum-logo-blue.png` çıktı vermemeli.

- [ ] **Step 2: Golden fixture üreticisini yaz**

`tools/make_logo_goldens.py` — bu script **mevcut dış script'i** subprocess ile çağırıp referans çıktıları üretir. Port yazılmadan ÖNCE çalıştırılır; ürettiği PNG'ler port'un davranış sözleşmesidir.

```python
#!/usr/bin/env python3
"""Golden fixture üretici — composite.py port'unun referansını dış script'ten alır.

BİR KEZ çalıştırılır (port yazılmadan önce). Ürettiği PNG'ler commit edilir ve
tests/test_composite.py bunlara karşı bayt bayt karşılaştırma yapar.

    .venv/bin/python tools/make_logo_goldens.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO, "tests", "fixtures", "logo")
SCRIPT = os.path.expanduser("~/.config/claude-tools/composite-logo.py")
LOGO_BLUE = os.path.join(REPO, "bundled", "logos", "kurum-logo-blue.png")
LOGO_WHITE = os.path.join(REPO, "bundled", "logos", "kurum-logo-white.png")

# (ad, base, position, color, scale, shadow_alpha, shadow_blur, overlay_or_None)
CASES = [
    ("defaults",        "base-light", "bottom-right", "auto",  0.14, 120, 6,  None),
    ("topleft-blue-lg", "base-light", "top-left",     "blue",  0.30, 0,   0,  None),
    ("center-white",    "base-dark",  "center",       "white", 0.14, 200, 12, None),
    ("auto-on-light",   "base-light", "bottom-center", "auto", 0.14, 120, 6,  None),
    ("auto-on-dark",    "base-dark",  "top-right",    "auto",  0.14, 120, 6,  None),
    ("custom-overlay",  "base-dark",  "center",       "auto",  0.20, 60,  4,  "overlay"),
]


def make_bases() -> None:
    """Deterministik iki temel görsel: biri açık, biri koyu (auto dalının iki yönü)."""
    os.makedirs(FIXTURES, exist_ok=True)
    for name, start, end in (("base-light", (245, 240, 230), (255, 255, 255)),
                             ("base-dark", (18, 20, 28), (40, 30, 60))):
        img = Image.new("RGB", (320, 240))
        draw = ImageDraw.Draw(img)
        for y in range(240):
            t = y / 239
            draw.line([(0, y), (320, y)],
                      fill=tuple(round(start[i] + (end[i] - start[i]) * t) for i in range(3)))
        img.save(os.path.join(FIXTURES, f"{name}.png"), "PNG")

    # Özel overlay dalı için küçük, yarı saydam bir işaret.
    overlay = Image.new("RGBA", (120, 40), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).ellipse([0, 0, 119, 39], fill=(220, 60, 90, 235))
    overlay.save(os.path.join(FIXTURES, "overlay.png"), "PNG")


def write_cases_manifest() -> None:
    """Vakaları JSON'a yazar; test buradan parametrize olur.

    Liste iki yerde (üretici + test) elle durursa sessizce ayrışır ve golden'lar
    yanlış vakayla karşılaştırılır. Tek kaynak burada.
    """
    keys = ("name", "base", "position", "color", "scale",
            "shadow_alpha", "shadow_blur", "overlay")
    with open(os.path.join(FIXTURES, "cases.json"), "w") as f:
        json.dump([dict(zip(keys, case)) for case in CASES], f,
                  ensure_ascii=False, indent=2)


def main() -> int:
    if not os.path.isfile(SCRIPT):
        print(f"HATA: dış script bulunamadı: {SCRIPT}", file=sys.stderr)
        return 1
    make_bases()
    write_cases_manifest()
    for (name, base, position, color, scale, sa, sb, overlay) in CASES:
        out = os.path.join(FIXTURES, f"golden-{name}.png")
        blue, white = LOGO_BLUE, LOGO_WHITE
        if overlay:
            blue = white = os.path.join(FIXTURES, "overlay.png")
        cmd = ["python3", SCRIPT, os.path.join(FIXTURES, f"{base}.png"), out,
               "--position", position, "--color", color, "--scale", str(scale),
               "--shadow-alpha", str(sa), "--shadow-blur", str(sb),
               "--logo-blue", blue, "--logo-white", white]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"HATA ({name}): {result.stderr}", file=sys.stderr)
            return 1
        print(f"✓ {os.path.basename(out)} ({os.path.getsize(out)} bayt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Fixture'ları üret ve gözle doğrula**

```bash
.venv/bin/python tools/make_logo_goldens.py
ls -la tests/fixtures/logo/
open tests/fixtures/logo/golden-auto-on-light.png tests/fixtures/logo/golden-auto-on-dark.png
```

Expected: 6 `golden-*.png` + 2 base + 1 overlay + `cases.json`. **Gözle kontrol:** açık zeminde MAVİ logo, koyu zeminde BEYAZ logo görünmeli (auto dalı iki yönü de kapsıyor). Toplam boyut ~1 MB'ı geçmemeli (`du -sh tests/fixtures/logo/`).

- [ ] **Step 4: Golden testleri yaz (başarısız olacak)**

`tests/test_composite.py`:

```python
"""composite.py, dış composite-logo.py ile bayt bayt aynı çıktı vermeli."""
import io
import json
import os

import pytest
from PIL import Image

import composite

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "logo")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_BLUE = os.path.join(REPO, "bundled", "logos", "kurum-logo-blue.png")
LOGO_WHITE = os.path.join(REPO, "bundled", "logos", "kurum-logo-white.png")
OVERLAY = os.path.join(FIXTURES, "overlay.png")

# Vakaların tek kaynağı üreticinin yazdığı manifest — elle ikinci bir liste
# tutulsa golden'lar sessizce yanlış vakayla eşleşebilirdi.
with open(os.path.join(FIXTURES, "cases.json")) as _f:
    CASES = json.load(_f)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_port_matches_the_external_script(case):
    name, base = case["name"], case["base"]
    blue, white = (OVERLAY, OVERLAY) if case["overlay"] else (LOGO_BLUE, LOGO_WHITE)
    produced = composite.composite_logo(
        os.path.join(FIXTURES, f"{base}.png"),
        logo_blue=blue, logo_white=white,
        position=case["position"], color=case["color"], scale=case["scale"],
        shadow_alpha=case["shadow_alpha"], shadow_blur=case["shadow_blur"])

    golden_path = os.path.join(FIXTURES, f"golden-{name}.png")
    with open(golden_path, "rb") as f:
        golden = f.read()

    if produced != golden:
        # Bayt farkı kodlayıcı metadata'sından da gelebilir; pikselleri de kıyasla ki
        # hata mesajı "gerçekten görüntü mü değişti" sorusunu yanıtlasın.
        a = Image.open(io.BytesIO(produced)).convert("RGB")
        b = Image.open(golden_path).convert("RGB")
        assert a.size == b.size, f"{name}: boyut değişti {a.size} != {b.size}"
        assert a.tobytes() == b.tobytes(), f"{name}: PİKSELLER değişti — port davranışı kaydırdı"
        pytest.fail(f"{name}: pikseller aynı ama baytlar farklı — PNG kodlayıcı ayarı değişmiş")


def test_auto_picks_blue_on_light_background():
    chosen = composite.pick_logo(
        Image.open(os.path.join(FIXTURES, "base-light.png")).convert("RGBA"),
        "bottom-right", "auto", LOGO_BLUE, LOGO_WHITE)
    assert chosen == LOGO_BLUE


def test_auto_picks_white_on_dark_background():
    chosen = composite.pick_logo(
        Image.open(os.path.join(FIXTURES, "base-dark.png")).convert("RGBA"),
        "bottom-right", "auto", LOGO_BLUE, LOGO_WHITE)
    assert chosen == LOGO_WHITE


def test_explicit_color_skips_brightness_sampling():
    base = Image.open(os.path.join(FIXTURES, "base-dark.png")).convert("RGBA")
    assert composite.pick_logo(base, "center", "blue", LOGO_BLUE, LOGO_WHITE) == LOGO_BLUE
    assert composite.pick_logo(base, "center", "white", LOGO_BLUE, LOGO_WHITE) == LOGO_WHITE


@pytest.mark.parametrize("position,expected", [
    ("top-left", (10, 10)),
    ("top-right", (100 - 20 - 10, 10)),
    ("bottom-left", (10, 80 - 15 - 10)),
    ("bottom-right", (100 - 20 - 10, 80 - 15 - 10)),
    ("center", ((100 - 20) // 2, (80 - 15) // 2)),
    ("top-center", ((100 - 20) // 2, 10)),
    ("center-left", (10, (80 - 15) // 2)),
])
def test_paste_position_covers_the_nine_grid(position, expected):
    assert composite.paste_position(100, 80, 20, 15, position, 10) == expected


def test_region_box_stays_inside_the_image():
    for position in composite.POSITIONS:
        x0, y0, x1, y1 = composite.region_box(200, 100, position)
        assert 0 <= x0 < x1 <= 200
        assert 0 <= y0 < y1 <= 100


def test_returns_png_bytes_without_touching_disk(tmp_path):
    out = composite.composite_logo(
        os.path.join(FIXTURES, "base-light.png"),
        logo_blue=LOGO_BLUE, logo_white=LOGO_WHITE)
    assert out[:8] == b"\x89PNG\r\n\x1a\n"
    assert list(tmp_path.iterdir()) == []  # geçici dosya bırakmıyor


def test_missing_base_raises_oserror():
    with pytest.raises(OSError):
        composite.composite_logo("/yok/boyle/bir/dosya.png",
                                 logo_blue=LOGO_BLUE, logo_white=LOGO_WHITE)
```

- [ ] **Step 5: Testleri çalıştır, başarısız olduklarını gör**

Run: `.venv/bin/python -m pytest tests/test_composite.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'composite'`

- [ ] **Step 6: `composite.py`'yi yaz**

Matematik dış script'ten **birebir** taşınır; tek fark: argparse yok, dosyaya yazma yok, bayt döner.

```python
"""KURUM logo/motto filigranı bindirme — composite-logo.py'nin süreç içi port'u.

Neden port: paket içinde ne `python3` ne de o script bulunur; subprocess çağrısı
Logo ve Banner uçlarını 500'e düşürürdü. Yan fayda: her canlı önizlemede bir
Python süreci başlatma maliyeti kalkar.

Dış script (~/.config/claude-tools/composite-logo.py) blog routine'i tarafından
bağımsız kullanıldığı için YERİNDE KALIR. Bu modül uygulamanın kaynağıdır; ikisi
arasındaki kayma riski tests/test_composite.py'deki golden fixture'larla ölçülür.
"""
from __future__ import annotations

import io

from PIL import Image, ImageFilter, ImageStat

BRIGHTNESS_THRESHOLD = 140  # 0-255; üstü "açık zemin" sayılır

POSITIONS = [
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
]


def _vh(position: str) -> tuple[str, str]:
    """Konum adını (dikey, yatay) belirteçlerine ayırır."""
    if position == "center":
        return ("center", "center")
    v, _, h = position.partition("-")
    return (v, h or "center")


def region_box(img_w: int, img_h: int, position: str,
               frac: float = 0.22) -> tuple[int, int, int, int]:
    """Logonun düşeceği alanın kutusu — parlaklık örneklemesi için."""
    rw, rh = int(img_w * frac), int(img_h * frac)
    v, h = _vh(position)
    x0 = 0 if h == "left" else (img_w - rw if h == "right" else (img_w - rw) // 2)
    y0 = 0 if v == "top" else (img_h - rh if v == "bottom" else (img_h - rh) // 2)
    return (x0, y0, x0 + rw, y0 + rh)


def pick_logo(base: Image.Image, position: str, color: str,
              logo_blue: str, logo_white: str) -> str:
    """color=auto ise zemin parlaklığına göre mavi/beyaz varyantı seçer."""
    if color == "blue":
        return logo_blue
    if color == "white":
        return logo_white
    box = region_box(*base.size, position)
    region = base.convert("RGB").crop(box)
    brightness = ImageStat.Stat(region).mean  # [R, G, B]
    luminance = 0.299 * brightness[0] + 0.587 * brightness[1] + 0.114 * brightness[2]
    return logo_blue if luminance > BRIGHTNESS_THRESHOLD else logo_white


def paste_position(img_w: int, img_h: int, logo_w: int, logo_h: int,
                   position: str, margin_px: int) -> tuple[int, int]:
    v, h = _vh(position)
    x = margin_px if h == "left" else (
        img_w - logo_w - margin_px if h == "right" else (img_w - logo_w) // 2)
    y = margin_px if v == "top" else (
        img_h - logo_h - margin_px if v == "bottom" else (img_h - logo_h) // 2)
    return (x, y)


def composite_logo(base_path: str, *, logo_blue: str, logo_white: str,
                   position: str = "bottom-right", color: str = "auto",
                   scale: float = 0.14, margin: float = 0.03,
                   shadow_alpha: int = 120, shadow_blur: int = 6) -> bytes:
    """Filigranı bindirip sonuç PNG'yi bayt olarak döndürür (diske yazmaz)."""
    base = Image.open(base_path).convert("RGBA")
    logo_path = pick_logo(base, position, color, logo_blue, logo_white)
    logo = Image.open(logo_path).convert("RGBA")

    logo_w = int(base.width * scale)
    logo_h = int(logo.height * (logo_w / logo.width))
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

    margin_px = int(base.width * margin)
    x, y = paste_position(base.width, base.height, logo_w, logo_h, position, margin_px)

    composed = base
    if shadow_alpha > 0:
        # Karmaşık zeminlerde okunurluk için yumuşak gölge.
        shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
        shadow_mask = logo.split()[-1]
        shadow_layer = Image.new("RGBA", logo.size,
                                 (0, 0, 0, max(0, min(255, shadow_alpha))))
        shadow_layer.putalpha(shadow_mask)
        shadow.paste(shadow_layer, (x + 4, y + 6), shadow_layer)
        shadow = shadow.filter(ImageFilter.GaussianBlur(max(0, shadow_blur)))
        composed = Image.alpha_composite(base, shadow)

    composed = composed.copy()
    composed.alpha_composite(logo, (x, y))
    out = io.BytesIO()
    composed.convert("RGB").save(out, format="PNG")
    return out.getvalue()
```

- [ ] **Step 7: Testleri çalıştır — 6 golden bayt bayt eşleşmeli**

Run: `.venv/bin/python -m pytest tests/test_composite.py -v`
Expected: PASS (hepsi).

Eğer "pikseller aynı ama baytlar farklı" hatası gelirse: `save(path, "PNG")` ile `save(BytesIO, format="PNG")` arasında kodlayıcı ayarı farkı var demektir. O durumda golden karşılaştırmasını **piksel eşitliğine** indir (assert'i `a.tobytes() == b.tobytes()` bırak, bayt eşitliğini kaldır) ve bu kararı testin docstring'ine yaz. Pikseller farklıysa DURDUR — port matematiği kaydırmış, dış script ile satır satır karşılaştır.

- [ ] **Step 8: Tüm suite + commit**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS, 606 + 19 = **625 test** (6 golden + 3 renk seçimi + 7 konum + region_box + PNG baytı + eksik dosya).

```bash
git add composite.py tests/test_composite.py tools/make_logo_goldens.py \
        tests/fixtures/logo bundled/logos
git commit -m "feat: composite-logo.py'yi composite.py olarak repoya port et

Paket içinde python3 + dış script bulunmadığı için logo bindirme subprocess
ile yapılamaz. Matematik birebir taşındı; 6 golden fixture dış script'in
çıktısıyla bayt bayt karşılaştırıyor. Dış script blog routine'i için yerinde
kalıyor. KURUM logoları bundled/logos'a alındı."
```

---

### Task 3: `app.py`'yi `composite.py`'ye bağla + subprocess'e bağlı 10 testi yeniden yaz

**Files:**
- Modify: `app.py:8-9` (import'lar), `app.py:37` (`COMPOSITE_SCRIPT` kalkar), `app.py:552-584` (`_composite_logo`)
- Modify: `tests/test_logo.py` (7 test)
- Modify: `tests/test_folders.py:test_logo_derivative_inherits_source_folder`, `tests/test_folders.py:test_move_does_not_touch_the_file_or_provenance`
- Modify: `tests/test_palette_route.py:test_logo_derivative_inherits_the_palette`

**Interfaces:**
- Consumes: `composite.composite_logo(...)` (Task 2), `paths.builtin_logo(variant)` (Task 1)
- Produces: `app._composite_logo(src_path: str, req: LogoRequest) -> bytes` — imza aynı kalır, gövdesi değişir

- [ ] **Step 1: Testleri yeni sözleşmeye göre yaz (başarısız olacaklar)**

`tests/test_logo.py`'nin başındaki `_fake_run_factory`'yi sil, yerine kwargs kaydeden bir sahte koy:

```python
def _fake_composite_factory(recorder=None):
    """composite.composite_logo yerine geçer: temel dosyayı okur, sonuna imza ekler.

    Eski _fake_run_factory komut dizisini kaydediyordu; artık çağrı kwargs'ı
    kaydediyoruz — port sonrası sözleşme bu.
    """
    def fake_composite(base_path, **kwargs):
        if recorder is not None:
            recorder.append(kwargs)
        with open(base_path, "rb") as f:
            return f.read() + b"+LOGO"
    return fake_composite
```

Sonra `monkeypatch.setattr(appmod.subprocess, "run", _fake_run_factory(...))` geçen **her satırı** şununla değiştir:

```python
monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))
```

(`calls` listesi gerekmeyen testlerde argümansız çağır.)

Komut dizisine bakan 4 testin assert'leri kwargs'a çevrilir:

```python
def test_logo_passes_options_to_composite(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={
        "id": src_id, "position": "top-center", "color": "white",
        "size": 0.22, "shadow_alpha": 0, "shadow_blur": 10})
    assert r.status_code == 200
    kw = calls[-1]
    assert kw["position"] == "top-center"
    assert kw["color"] == "white"
    assert kw["scale"] == 0.22          # LogoRequest.size -> composite scale
    assert kw["shadow_alpha"] == 0
    assert kw["shadow_blur"] == 10


def test_logo_builtin_uses_bundled_ila_logos(tmp_path, monkeypatch):
    """asset_id yoksa gömülü mavi/beyaz KURUM logoları geçilir (auto seçim composite'te)."""
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    assert c.post("/api/logo", json={"id": src_id}).status_code == 200
    kw = calls[-1]
    assert kw["logo_blue"].endswith("bundled/logos/kurum-logo-blue.png")
    assert kw["logo_white"].endswith("bundled/logos/kurum-logo-white.png")
    assert kw["logo_blue"] != kw["logo_white"]


def test_logo_asset_id_passes_custom_overlay_as_both_variants(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    asset = astore.save_asset("logos", b"\x89PNG-logo", "özel", str(tmp_path / "assets"),
                              now="2026-07-23T10:00:00")

    r = c.post("/api/logo", json={"id": src_id, "asset_id": asset["id"]})
    assert r.status_code == 200
    kw = calls[-1]
    assert kw["logo_blue"] == kw["logo_white"]
    assert kw["logo_blue"].endswith(f"{asset['id']}.png")


def test_motto_placement_resolves_from_mottos_library(tmp_path, monkeypatch):
    """Motto = logo tarzı konumlanabilir bindirme, ama 'mottos' kütüphanesinden."""
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])
    calls = []
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake_composite_factory(calls))

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    motto = astore.save_asset("mottos", b"\x89PNG-motto", "motto", str(tmp_path / "assets"),
                              now="2026-07-23T10:00:00")

    r = c.post("/api/logo", json={"id": src_id, "asset_id": motto["id"],
                                  "asset_kind": "mottos", "position": "center"})
    assert r.status_code == 200
    assert calls[-1]["logo_blue"].endswith(f"{motto['id']}.png")
    # motto id'si logos kütüphanesinde yok → yalnızca mottos'tan çözülebildi
    assert astore.asset_path("logos", motto["id"], str(tmp_path / "assets")) is None
```

Yeni test ekle — bindirme hatası 500'e sarılmalı (eski `returncode != 0` dalının karşılığı):

```python
def test_composite_failure_becomes_500(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG-base"])

    def boom(base_path, **kwargs):
        raise OSError("logo dosyası okunamadı")
    monkeypatch.setattr(appmod.composite, "composite_logo", boom)

    c = TestClient(appmod.app)
    src_id = _make_source(c)
    r = c.post("/api/logo", json={"id": src_id})
    assert r.status_code == 500
    assert "Logo bindirme başarısız" in r.json()["detail"]
```

`tests/test_folders.py` ve `tests/test_palette_route.py`'daki 3 testte de aynı değişiklik: `appmod.subprocess`/`run` mock'u → `appmod.composite`/`composite_logo` mock'u. O dosyalarda yerel bir `_fake_run_factory` varsa aynı şekilde kwargs alan bir sahteye çevir; yoksa satır içi lambda yeter:

```python
monkeypatch.setattr(appmod.composite, "composite_logo",
                    lambda base_path, **kw: open(base_path, "rb").read() + b"+LOGO")
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını gör**

Run: `.venv/bin/python -m pytest tests/test_logo.py tests/test_folders.py tests/test_palette_route.py -v`
Expected: FAIL — `AttributeError: module 'app' has no attribute 'composite'`

- [ ] **Step 3: `app.py`'yi bağla**

`app.py:8-9`'daki iki import'u **sil** (`_composite_logo` dışında kullanılmıyor):

```python
import subprocess
import tempfile
```

`app.py:37`'deki satırı **sil**:

```python
COMPOSITE_SCRIPT = os.path.expanduser("~/.config/claude-tools/composite-logo.py")
```

Import bloğuna ekle (alfabetik: `color_names`'ten sonra, `folders`'tan önce):

```python
import composite
```

`app.py:552-584`'ü tümüyle değiştir:

```python
def _composite_logo(src_path: str, req: LogoRequest) -> bytes:
    """Logo/motto filigranını süreç içinde bindirir (composite.py).

    asset_id verilirse seçilen tek görsel her iki varyant olarak geçilir: renk
    seçimi (auto/blue/white) hangisine düşerse düşsün aynı görsel kullanılır.
    """
    logo_blue = paths.builtin_logo("blue")
    logo_white = paths.builtin_logo("white")
    if req.asset_id:
        overlay_path = assets_store.asset_path(req.asset_kind, req.asset_id, ASSETS_DIR)
        if overlay_path is None:
            raise HTTPException(status_code=404, detail="görsel bulunamadı")
        logo_blue = logo_white = overlay_path
    try:
        return composite.composite_logo(
            src_path,
            logo_blue=logo_blue, logo_white=logo_white,
            position=req.position, color=req.color, scale=req.size,
            shadow_alpha=req.shadow_alpha, shadow_blur=req.shadow_blur,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500,
                            detail=f"Logo bindirme başarısız: {exc}") from exc
```

- [ ] **Step 4: Testleri çalıştır**

Run: `.venv/bin/python -m pytest tests/test_logo.py tests/test_folders.py tests/test_palette_route.py -v`
Expected: PASS (hepsi).

- [ ] **Step 5: Kalıntı kontrolü**

Run: `grep -n "subprocess\|tempfile\|COMPOSITE_SCRIPT" app.py`
Expected: **çıktı yok**.

- [ ] **Step 6: Tüm suite + gerçek logo ile canlı doğrulama**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS, **632 test** (631 + 1 yeni 500 testi; 10 test yeniden yazıldı, sayı değişmez).

Sonra gerçek uçtan uca (mock'suz):

```bash
./run.sh   # ayrı terminalde bırak
```
Tarayıcıda bir görsel üret → sol panelden "Logo ekle" → 3×3 konumdan birini seç → canlı önizleme **gelmeli** → "Uygula" → türev geçmişe düşmeli. Önizlemenin eskisinden hızlı geldiğini gözle teyit et (süreç başlatma maliyeti kalktı).

- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_logo.py tests/test_folders.py tests/test_palette_route.py
git commit -m "refactor: logo bindirme subprocess yerine composite.py ile süreç içinde

app.py artık repo dışındaki composite-logo.py'yi python3 ile çağırmıyor;
paket içinde ikisi de bulunmadığı için bu yol kırılıyordu. subprocess ve
tempfile import'ları düştü. Komut dizisine bakan 10 test kwargs sözleşmesine
taşındı, bindirme hatasının 500'e sarıldığını doğrulayan test eklendi."
```

---

### Task 4: Gömülü logoların ilk açılışta tohumlanması

**Files:**
- Create: `seed.py`
- Create: `tests/test_seed.py`
- Modify: `app.py` (Task 1'de eklenen `paths.ensure_data_dirs()` satırının hemen ardına tohumlama çağrısı)

**Interfaces:**
- Consumes: `paths.bundled_logos_dir()`, `paths.assets_dir()`, `paths.data_dir()` (Task 1); `assets_store.save_asset(kind, image_bytes, name, assets_dir, *, now)`
- Produces: `seed_builtin_logos(assets_dir: str, bundled_dir: str, marker_dir: str, *, now: str) -> list[dict]` — eklenen kayıtlar (zaten tohumlanmışsa boş liste)

**Neden marker dosyası:** "kütüphane boşsa tohumla" kuralı, kullanıcı logoları bilinçli silince onları geri getirir. Marker (`.logos-seeded`) tohumlamayı **bir kez** yapar; silinen logo silinmiş kalır.

- [ ] **Step 1: Testleri yaz (başarısız olacak)**

`tests/test_seed.py`:

```python
import os

import assets_store as astore
import seed

NOW = "2026-07-28T12:00:00"


def _make_bundled(tmp_path):
    bundled = tmp_path / "bundled" / "logos"
    bundled.mkdir(parents=True)
    (bundled / "kurum-logo-blue.png").write_bytes(b"\x89PNG-blue")
    (bundled / "kurum-logo-white.png").write_bytes(b"\x89PNG-white")
    return str(bundled)


def test_seeds_both_logos_into_an_empty_library(tmp_path):
    bundled = _make_bundled(tmp_path)
    assets = str(tmp_path / "assets")

    added = seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)

    assert len(added) == 2
    names = sorted(r["name"] for r in astore.list_assets("logos", assets))
    assert names == ["KURUM Logo Beyaz", "KURUM Logo Mavi"]
    stored = {r["name"]: open(os.path.join(assets, "logos", r["filename"]), "rb").read()
              for r in astore.list_assets("logos", assets)}
    assert stored["KURUM Logo Mavi"] == b"\x89PNG-blue"
    assert stored["KURUM Logo Beyaz"] == b"\x89PNG-white"


def test_second_call_does_not_duplicate(tmp_path):
    bundled = _make_bundled(tmp_path)
    assets = str(tmp_path / "assets")

    seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)
    added_again = seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)

    assert added_again == []
    assert len(astore.list_assets("logos", assets)) == 2


def test_does_not_restore_logos_the_user_deleted(tmp_path):
    bundled = _make_bundled(tmp_path)
    assets = str(tmp_path / "assets")

    added = seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)
    for record in added:
        astore.delete_asset("logos", record["id"], assets)
    assert astore.list_assets("logos", assets) == []

    seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)
    assert astore.list_assets("logos", assets) == []  # marker var → geri gelmez


def test_leaves_a_non_empty_library_alone(tmp_path):
    """Mevcut kurulumda (marker yok, kütüphane dolu) tohumlama yapılmaz."""
    bundled = _make_bundled(tmp_path)
    assets = str(tmp_path / "assets")
    astore.save_asset("logos", b"\x89PNG-mine", "kendi logom", assets, now=NOW)

    added = seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)

    assert added == []
    assert [r["name"] for r in astore.list_assets("logos", assets)] == ["kendi logom"]


def test_missing_bundled_dir_is_not_fatal(tmp_path):
    """Gömülü logolar yoksa (geliştirme kopyası) sessizce atlanır, çökmez."""
    assets = str(tmp_path / "assets")
    added = seed.seed_builtin_logos(assets, str(tmp_path / "yok"), str(tmp_path), now=NOW)
    assert added == []


def test_writes_the_marker_file(tmp_path):
    bundled = _make_bundled(tmp_path)
    seed.seed_builtin_logos(str(tmp_path / "assets"), bundled, str(tmp_path), now=NOW)
    assert (tmp_path / ".logos-seeded").is_file()
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını gör**

Run: `.venv/bin/python -m pytest tests/test_seed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'seed'`

- [ ] **Step 3: `seed.py`'yi yaz**

```python
"""İlk açılış tohumlaması: pakete gömülü KURUM logolarını kullanıcı kütüphanesine ekler.

Neden gerekli: assets/ gitignore'da ve kullanıcı verisi dizini boş başlar; tohumlama
olmadan Logo modalındaki kütüphane bomboş görünür.

Neden marker dosyası: "kütüphane boşsa tohumla" kuralı, kullanıcı logoları bilinçli
sildiğinde onları her açılışta geri getirirdi. Marker bir kez tohumlar.
"""
from __future__ import annotations

import os

import assets_store

MARKER_FILE = ".logos-seeded"
# (dosya adı, kütüphanede görünecek ad)
BUILTIN_LOGOS = (
    ("kurum-logo-blue.png", "KURUM Logo Mavi"),
    ("kurum-logo-white.png", "KURUM Logo Beyaz"),
)


def seed_builtin_logos(assets_dir: str, bundled_dir: str, marker_dir: str,
                       *, now: str) -> list[dict]:
    """Gömülü logoları bir kez kütüphaneye ekler; eklenen kayıtları döndürür."""
    marker_path = os.path.join(marker_dir, MARKER_FILE)
    if os.path.exists(marker_path):
        return []
    if not os.path.isdir(bundled_dir):
        return []
    # Kullanıcının hâlihazırda logosu varsa (mevcut kurulum) karışma.
    if assets_store.list_assets("logos", assets_dir):
        _touch(marker_path)
        return []

    added: list[dict] = []
    for filename, label in BUILTIN_LOGOS:
        source = os.path.join(bundled_dir, filename)
        if not os.path.isfile(source):
            continue
        with open(source, "rb") as f:
            added.append(assets_store.save_asset("logos", f.read(), label,
                                                 assets_dir, now=now))
    _touch(marker_path)
    return added


def _touch(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("")
```

- [ ] **Step 4: Testleri çalıştır**

Run: `.venv/bin/python -m pytest tests/test_seed.py -v`
Expected: PASS (6 test).

- [ ] **Step 5: `app.py`'ye bağla**

> ⚠️ **Uygulama sırasında değişti (insan kararı).** Bu adım ilk yazımda tohumlamayı
> **modül kapsamında** çağırıyordu. Review bunu haklı olarak kusur buldu: `run.sh`
> uygulamayı `uvicorn app:app` ile başlatıyor, yani modülü **import** ediyor →
> "test için import" ile "sunucu başlatma" arasında sınır yok, dolayısıyla her test
> gerçek `assets/` dizinine tohumlama tetikliyordu. Boş `assets/` olan bir makinede
> (temiz klon / CI) sadece test toplamak iki 300 KB PNG'yi gerçek kütüphaneye
> kopyalardı. Karar: tohumlama **lifespan hook'una** taşındı.

Import bloğuna ekle (alfabetik: `paths`'ten sonra, `storage`'tan önce):

```python
import seed
```

`app = FastAPI(...)` satırının hemen ÜSTÜNE lifespan'i tanımla ve bağla:

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Sunucu başlarken çalışır — import anında DEĞİL.

    Tohumlama gerçek dosya sistemine yazdığı için modül kapsamında olmamalı:
    app'i yalnızca import eden testler kullanıcının gerçek assets/ dizinine
    dokunmasın.
    """
    seed.seed_builtin_logos(ASSETS_DIR, paths.bundled_logos_dir(),
                            paths.data_dir(), now=_now())
    yield


app = FastAPI(title="GPT-Image Studio", lifespan=_lifespan)
```

Gövde başlangıçta çalıştığı için kendisinden sonra tanımlanan `_now`'a erişmesi
sorun değil. `@app.on_event("startup")` **kullanma** — bu FastAPI sürümünde
deprecated, suite'in 26'lık temiz uyarı tabanını bozar.

**Modül kapsamında KALMASI gerekenler** (dosya sonundaki blok):
`paths.ensure_data_dirs()` ve `os.makedirs(STATIC_DIR, exist_ok=True)`. İkincisi
zorunlu: `app.mount("/static", StaticFiles(...))` import anında kuruluyor ve dizin
yoksa patlıyor. İlki bilinçli minimal müdahale — iki boş dizin yaratmak, 600 KB
görsel kopyalamaktan bambaşka bir şey.

**İki kanıt testi** (`tests/test_seed.py`): `appmod.seed.seed_builtin_logos`'a casus
tak; (1) düz `TestClient(appmod.app)` ile hiç çağrılmadığını, (2) `with
TestClient(appmod.app)` altında tam bir kez çağrıldığını doğrula. İkincisi
paketlenmiş uygulamanın hâlâ tohumladığının kanıtıdır.

- [ ] **Step 6: Tüm suite — mevcut kurulumun kütüphanesi bozulmadı**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS, **641 test** (639 = 633 + 6 tohumlama; + 2 lifespan kanıt testi).

Sonra gerçek çalıştırma: `./run.sh` → Kütüphane modalını aç → logolar listesi **eskisiyle aynı** olmalı (senin makinende kütüphane dolu → tohumlama atlanır, yalnız marker yazılır). Kontrol: `ls -la .logos-seeded` (repo kökünde, geliştirme modunda `data_dir()` = repo).

- [ ] **Step 7: `.logos-seeded`'ı gitignore'a ekle + commit**

`.gitignore`'a ekle:

```
.logos-seeded
```

```bash
git add seed.py tests/test_seed.py app.py .gitignore
git commit -m "feat: ilk açılışta gömülü KURUM logolarını kütüphaneye tohumla

assets/ gitignore'da olduğu için yeni bir makinede logo kütüphanesi boş
başlıyordu. Tohumlama marker dosyasıyla bir kez yapılır: kullanıcı logoyu
silerse geri gelmez, dolu kütüphaneye hiç dokunulmaz."
```

---

### Task 5: `desktop.py` — gömülü sunucu + native pencere

**Files:**
- Create: `desktop.py`
- Create: `tests/test_desktop.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `paths.ensure_data_dirs()` (Task 1), `app.app` (FastAPI uygulaması)
- Produces:
  - `start_server(fastapi_app, host: str = "127.0.0.1", timeout: float = 15.0) -> tuple[uvicorn.Server, threading.Thread, int]`
  - `main() -> None`

- [ ] **Step 1: `pywebview`'ı bağımlılığa ekle**

`requirements.txt`'in sonuna:

```
pywebview==6.2.*
```

Kur: `.venv/bin/pip install -q -r requirements.txt`
Doğrula: `.venv/bin/python -c "import webview; print('ok')"` → `ok`

- [ ] **Step 2: Testi yaz (başarısız olacak)**

`tests/test_desktop.py` — mock yok, gerçek soket. pywebview'a hiç dokunmaz (pencere açılmaz), yalnız sunucu yaşam döngüsü test edilir.

```python
"""desktop.start_server gerçek bir sokete bağlanır — pencere kısmı manuel doğrulanır."""
import httpx
import pytest
from fastapi import FastAPI

import desktop


def _probe_app() -> FastAPI:
    probe = FastAPI()

    @probe.get("/ping")
    def ping() -> dict:
        return {"ok": True}

    return probe


def test_start_server_binds_a_free_port_and_serves():
    server, thread, port = desktop.start_server(_probe_app())
    try:
        assert port > 0
        r = httpx.get(f"http://127.0.0.1:{port}/ping", timeout=5)
        assert r.status_code == 200
        assert r.json() == {"ok": True}
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    assert not thread.is_alive()


def test_two_servers_get_different_ports():
    """port=0 çekirdekten boş port ister → run.sh'teki 8765 çakışma mantığı gereksiz."""
    a_server, a_thread, a_port = desktop.start_server(_probe_app())
    b_server, b_thread, b_port = desktop.start_server(_probe_app())
    try:
        assert a_port != b_port
    finally:
        for server, thread in ((a_server, a_thread), (b_server, b_thread)):
            server.should_exit = True
            thread.join(timeout=5)


def test_start_server_binds_only_to_loopback():
    server, thread, port = desktop.start_server(_probe_app())
    try:
        sock = server.servers[0].sockets[0]
        assert sock.getsockname()[0] == "127.0.0.1"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_timeout_raises_instead_of_hanging():
    with pytest.raises(RuntimeError, match="başlatılamadı"):
        desktop.start_server(_probe_app(), host="256.256.256.256", timeout=3.0)
```

- [ ] **Step 3: Testi çalıştır, başarısız olduğunu gör**

Run: `.venv/bin/python -m pytest tests/test_desktop.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'desktop'`

- [ ] **Step 4: `desktop.py`'yi yaz**

```python
"""Masaüstü başlatıcı: uvicorn'u thread'de çalıştırır, native pencerede gösterir.

Neden port=0: sabit port (run.sh'teki 8765) ikinci bir örnek açıldığında ya da
bayat bir süreç ayakta kaldığında çakışıyordu. Çekirdekten boş port istemek bu
sınıf hatayı tümüyle kaldırır; pencere gerçek portu çalışma anında öğrenir.

Pencere kapanınca uvicorn'a çıkış işaretlenir ve thread beklenir — süreç arkada
asılı kalmaz.
"""
from __future__ import annotations

import threading
import time

import uvicorn

import paths

WINDOW_TITLE = "GPT-Image Studio"
WINDOW_SIZE = (1440, 900)
MIN_WINDOW_SIZE = (1024, 700)
_POLL_INTERVAL = 0.02


def start_server(fastapi_app, host: str = "127.0.0.1",
                 timeout: float = 15.0) -> tuple[uvicorn.Server, threading.Thread, int]:
    """Sunucuyu boş bir portta daemon thread'de başlatır; (sunucu, thread, port) döner."""
    config = uvicorn.Config(fastapi_app, host=host, port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="uvicorn")
    thread.start()

    deadline = time.monotonic() + timeout
    while not server.started:
        if not thread.is_alive():
            raise RuntimeError("sunucu başlatılamadı (thread öldü)")
        if time.monotonic() > deadline:
            server.should_exit = True
            raise RuntimeError(f"sunucu başlatılamadı ({timeout} sn içinde hazır olmadı)")
        time.sleep(_POLL_INTERVAL)

    port = server.servers[0].sockets[0].getsockname()[1]
    return server, thread, port


def main() -> None:
    import webview  # yalnız pencere yolunda gerekir; testler bunu import etmez

    paths.ensure_data_dirs()
    import app as appmod  # yollar hazır olduktan sonra

    server, thread, port = start_server(appmod.app)
    try:
        webview.create_window(WINDOW_TITLE, f"http://127.0.0.1:{port}",
                              width=WINDOW_SIZE[0], height=WINDOW_SIZE[1],
                              min_size=MIN_WINDOW_SIZE)
        webview.start()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Testi çalıştır**

Run: `.venv/bin/python -m pytest tests/test_desktop.py -v`
Expected: PASS (4 test).

Sonra tüm suite: `.venv/bin/python -m pytest tests/ -q` → **645 test**.

- [ ] **Step 6: Pencereyi manuel doğrula (paketlemeden önce, kaynaktan)**

```bash
.venv/bin/python desktop.py
```

Kontrol listesi:
- Native bir pencere açılıyor (tarayıcı sekmesi değil), başlık "GPT-Image Studio".
- Arayüz yükleniyor; galeri, palet modalı, Kütüphane modalı açılıyor.
- Bir görsel üretiliyor (kimlik zaten yapılandırılmış).
- Pencereyi kapat → süreç ölüyor: `ps aux | grep -c "[d]esktop.py"` → `0`.

- [ ] **Step 7: Commit**

```bash
git add desktop.py tests/test_desktop.py requirements.txt
git commit -m "feat: native pencerede açılan masaüstü başlatıcı (desktop.py)

uvicorn daemon thread'de port=0 ile başlar, pywebview WKWebView penceresi
gerçek portu çalışma anında alır. Sabit 8765 portu ve run.sh'teki bayat
süreç devralma mantığı bu yolda gereksizleşir. Pencere kapanınca sunucuya
çıkış işaretlenir ve thread beklenir."
```

---

### Task 6: PyInstaller paketi, ad-hoc imza, kurulum belgesi

**Files:**
- Create: `requirements-dev.txt`
- Create: `gpt-image-studio.spec`
- Create: `build.sh`
- Create: `KURULUM.md`
- Modify: `README.md` (paketleme bölümü)
- Modify: `.gitignore` (`build/`, `dist/`)

**Interfaces:**
- Consumes: `desktop.py:main()` (Task 5), `bundled/logos/` (Task 2), `static/`
- Produces: `dist/GPT-Image Studio.app`, `dist/GPT-Image Studio.zip`

- [ ] **Step 1: Build bağımlılığını ayır**

`requirements-dev.txt` oluştur:

```
# Yalnız paket derlemek için gerekir; uygulamanın çalışma zamanı bağımlılığı DEĞİL.
pyinstaller==6.21.*
```

Kur: `.venv/bin/pip install -q -r requirements-dev.txt`
Doğrula: `.venv/bin/pyinstaller --version` → `6.21.x`

- [ ] **Step 2: Spec iskeletini üret (elle yazma — sürüm uyumlu olsun)**

```bash
cd "/Users/kullanici/Documents/Projects/Claude Code Projects/gpt-image-studio"
.venv/bin/pyi-makespec --windowed --name "GPT-Image Studio" \
  --osx-bundle-identifier org.zenginby.gptimagestudio \
  --target-arch arm64 desktop.py
mv "GPT-Image Studio.spec" gpt-image-studio.spec
```

- [ ] **Step 3: Spec'i düzenle — datas, hiddenimports, Info.plist**

`gpt-image-studio.spec` içinde `Analysis(...)` çağrısında:

```python
    datas=[
        ("static", "static"),
        ("bundled", "bundled"),
    ],
    hiddenimports=[
        # uvicorn'un çalışma anında seçtiği modüller statik analizde görünmez
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.loops.uvloop",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # uygulama modülleri desktop.py'de dolaylı import ediliyor
        "app", "paths", "seed", "composite", "storage", "folders",
        "assets_store", "azure_client", "models",
        "palette", "palette_store", "color_names",
    ],
```

`BUNDLE(...)` çağrısındaki `info_plist`'i şu şekilde ayarla (yoksa parametreyi ekle):

```python
    info_plist={
        "LSMultipleInstancesProhibited": True,   # iki kez çift tıklama ikinci sunucu doğurmaz
        "NSHighResolutionCapable": True,
        "CFBundleShortVersionString": "1.8.0",
        "CFBundleVersion": "1.8.0",
        "LSMinimumSystemVersion": "13.0",
    },
```

- [ ] **Step 4: `build.sh`'i yaz**

```bash
#!/usr/bin/env bash
# GPT-Image Studio'yu macOS uygulaması olarak derler, ad-hoc imzalar, zip'ler.
# Hedef: Apple Silicon (arm64). Notarization YOK — kullanıcı ilk açılışta
# Sistem Ayarları → Gizlilik ve Güvenlik → "Yine de Aç" yapar (bkz. KURULUM.md).
set -euo pipefail
cd "$(dirname "$0")"

APP="dist/GPT-Image Studio.app"
ZIP="dist/GPT-Image Studio.zip"

source .venv/bin/activate
pip install -q -r requirements.txt -r requirements-dev.txt

echo "→ testler"
python -m pytest tests/ -q

echo "→ temizlik"
rm -rf build dist

echo "→ derleme"
pyinstaller gpt-image-studio.spec --noconfirm

echo "→ ad-hoc imza"
codesign --force --deep --sign - "$APP"
codesign --verify --verbose "$APP"

echo "→ zip (ditto: .app'in sembolik bağları korunur, 'zip' bozar)"
rm -f "$ZIP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

echo "✓ hazır: $ZIP ($(du -h "$ZIP" | cut -f1))"
```

Çalıştırılabilir yap: `chmod +x build.sh`

- [ ] **Step 5: `.gitignore`'a build çıktılarını ekle**

```
build/
dist/
```

- [ ] **Step 6: Derle**

Run: `./build.sh`
Expected: `✓ hazır: dist/GPT-Image Studio.zip (60–90M civarı)`.

Derleme patlarsa sırayla bak:
1. `ModuleNotFoundError` → eksik modülü `hiddenimports`'a ekle, yeniden derle.
2. uvloop/httptools kaynaklı hata → `desktop.py`'deki `uvicorn.Config`'e `loop="asyncio"`, `http="h11"` ekle ve `hiddenimports`'tan uvloop/httptools satırlarını çıkar. (Tasarımdaki kabul edilen düşüş yolu.)
3. Pillow plugin hatası → `hiddenimports`'a `PIL._imaging`, `PIL.PngImagePlugin` ekle.

- [ ] **Step 7: Paketi temiz veri diziniyle canlı kabul testi**

```bash
# Varsa eski kullanıcı verisini yedekle (bu adım paketi ilk açılış gibi denemek için)
mv ~/Library/Application\ Support/GPT-Image\ Studio ~/Library/Application\ Support/GPT-Image\ Studio.bak 2>/dev/null || true
open "dist/GPT-Image Studio.app"
```

Kontrol listesi — hepsi geçmeli:
- [ ] Pencere açılıyor, arayüz yükleniyor (boş sayfa değil → `static/` paketlendi).
- [ ] Kimlik yapılandırılmamış olduğu için **Ayarlar modalı otomatik açılıyor**, "Üret" kilitli.
- [ ] Endpoint + key girilince kaydediyor; `ls -l ~/.config/gpt-image-studio/credentials.env` → izin `-rw-------`.
- [ ] Görsel üretiliyor ve galeride görünüyor.
- [ ] Kütüphane modalında **KURUM Logo Mavi + KURUM Logo Beyaz** duruyor (tohumlama çalıştı).
- [ ] Logo bindirme: canlı önizleme geliyor, "Uygula" türev üretiyor.
- [ ] Banner bindirme çalışıyor.
- [ ] Klasör oluşturma + sürükle-bırak taşıma çalışıyor.
- [ ] Palet önerisi geliyor, palet kaydedilebiliyor, üretimde uygulanıyor.
- [ ] Uygulamayı kapat, tekrar aç → **geçmiş yerinde** (`~/Library/Application Support/GPT-Image Studio/output/` dolu).
- [ ] İki kez çift tıkla → tek örnek kalıyor (`LSMultipleInstancesProhibited`).
- [ ] Pencereyi kapat → süreç ölüyor: `pgrep -f "GPT-Image Studio"` boş.

Sonra yedeği geri al: `mv ~/Library/Application\ Support/GPT-Image\ Studio.bak ~/Library/Application\ Support/GPT-Image\ Studio 2>/dev/null || true`

- [ ] **Step 8: Gatekeeper akışını gerçekten doğrula**

Quarantine bayrağı ancak indirme/AirDrop ile konur; yerel derlemede yok. Kullanıcının göreceği akışı taklit et:

```bash
xattr -w com.apple.quarantine "0083;00000000;Safari;" "dist/GPT-Image Studio.app"
open "dist/GPT-Image Studio.app"   # engellenmeli
```

Sistem Ayarları → Gizlilik ve Güvenlik → "Yine de Aç" akışının **çalıştığını gözle doğrula** ve gördüğün ekranların ekran görüntüsünü al (KURULUM.md'ye girecek). Sonra temizle: `xattr -dr com.apple.quarantine "dist/GPT-Image Studio.app"`

- [ ] **Step 9: `KURULUM.md`'yi yaz**

Adım 8'de aldığın ekran görüntülerini `docs/kurulum/` altına koy ve şu iskeleti doldur:

```markdown
# GPT-Image Studio — Kurulum (macOS)

Bilgisayarına Python veya başka bir şey kurman gerekmiyor. 5 dakika sürer.

## 1. Uygulamayı yerine koy
1. `GPT-Image Studio.zip` dosyasına çift tıkla — yanında `GPT-Image Studio` uygulaması çıkar.
2. Çıkan uygulamayı **Programlar (Applications)** klasörüne sürükle.

## 2. İlk açılış — bir kerelik güvenlik izni
Uygulama Apple'a ücretli geliştirici kaydıyla imzalanmadığı için macOS ilk açılışta
soru soruyor. Bir kez izin verirsin, sonraki açılışlarda sormaz.

1. Uygulamaya çift tıkla. "açılamadı" uyarısı çıkacak — **Tamam**'a bas.
2.  → **Sistem Ayarları** → **Gizlilik ve Güvenlik**.
3. Sayfayı aşağı kaydır: *"GPT-Image Studio engellendi"* satırını bul → **Yine de Aç**.
4. Çıkan onayda tekrar **Yine de Aç** → Mac şifreni gir.

(ekran görüntüleri: docs/kurulum/*.png)

## 3. Azure kimliğini gir
İlk açılışta Ayarlar penceresi kendiliğinden açılır ve "Üret" düğmesi kilitlidir.
1. **Endpoint** ve **API key** alanlarını Kurum'dan aldığın bilgilerle doldur.
2. **Kaydet**. Kilit açılır.

Key bilgisayarında `~/.config/gpt-image-studio/credentials.env` dosyasında, yalnız
senin okuyabileceğin izinle saklanır ve bir daha ekranda gösterilmez.

## 4. Kullan
Prompt yaz → **Üret**. Ürettiğin görseller bilgisayarında
`~/Library/Application Support/GPT-Image Studio/output/` altında saklanır;
uygulamayı kapatıp açsan da geçmişin durur.

## Sorun çıkarsa
- **Pencere boş açılıyor:** uygulamayı kapat, tekrar aç.
- **"Üret" kilitli:** Ayarlar (dişli) → endpoint + key girilmiş mi?
- **Görsel üretilmiyor, hata mesajı çıkıyor:** key süresi/rotasyonu için Kurum'ya yaz.
```

- [ ] **Step 10: `README.md`'ye paketleme bölümü ekle**

`## Test` bölümünden sonra:

```markdown
## Masaüstü uygulaması olarak paketleme
    ./build.sh          # → dist/GPT-Image Studio.zip (arm64, ad-hoc imzalı)
Pencereyi kaynaktan denemek için: `.venv/bin/python desktop.py`
Son kullanıcı talimatı: `KURULUM.md`. Tasarım/plan: `docs/superpowers/`.
```

- [ ] **Step 11: Commit**

```bash
git add requirements-dev.txt gpt-image-studio.spec build.sh KURULUM.md \
        README.md .gitignore docs/kurulum
git commit -m "feat: macOS uygulaması olarak paketleme (PyInstaller + ad-hoc imza)

build.sh: testler → pyinstaller → ad-hoc imza → ditto zip. static/ ve
bundled/ pakete gömülür; LSMultipleInstancesProhibited ile tek örnek.
KURULUM.md son kullanıcıya Gatekeeper'ın 'Yine de Aç' akışını ekran
görüntüleriyle anlatır — terminal gerekmiyor."
```

---

---

### Task 7: GitHub Actions arm64 gönderim hattı

**Files:**
- Create: `.github/workflows/build-macos-arm64.yml`
- Modify: `README.md` (gönderim paketinin nasıl alındığı)
- Modify: `KURULUM.md` (TODO satırının yanına: paketin nereden geldiği)

**Interfaces:**
- Consumes: `build.sh`, `gpt-image-studio.spec`, `requirements.txt`, `requirements-dev.txt` (Task 6)
- Produces: indirilebilir artifact — `GPT-Image Studio.zip` (arm64, ad-hoc imzalı)

**Neden gerekli:** derleme makinesi Intel; ofis makineleri Apple Silicon. PyInstaller
çapraz derleme yapamıyor (bkz. Global Constraints). `macos-14`+ runner'ları arm64.

- [ ] **Step 1: `build.sh`'in CI'da çalıştığını incele**

`build.sh` `source .venv/bin/activate` yapıyor; CI'da `.venv` yok. **Tek build
yolunu korumak için** workflow `.venv` oluşturur — `build.sh`'i CI'ya özel
dallanmayla kirletmek yerine. Bu, yerelde doğrulanan yolun birebir aynısının
gönderim paketini üretmesini garanti eder.

- [ ] **Step 2: Workflow'u yaz**

```yaml
name: macOS arm64 paketi

# Elle tetiklenir: her push'ta 25 MB artifact üretmek gereksiz ve private repo'da
# macOS dakikaları 10x sayılıyor.
on:
  workflow_dispatch:

jobs:
  build:
    runs-on: macos-14          # arm64 (Apple Silicon) runner
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.14'

      - name: Mimariyi doğrula (yanlış runner'da sessizce x86_64 üretmesin)
        run: |
          set -euo pipefail
          ARCH="$(uname -m)"
          echo "runner mimarisi: $ARCH"
          test "$ARCH" = "arm64" || { echo "HATA: arm64 bekleniyordu, $ARCH bulundu"; exit 1; }
          python -c "import sysconfig; print('python plat:', sysconfig.get_platform())"

      - name: venv kur (build.sh bunu bekliyor)
        run: |
          set -euo pipefail
          python -m venv .venv
          .venv/bin/pip install -q --upgrade pip

      - name: Derle (yerelde doğrulanan build.sh ile, değiştirmeden)
        run: ./build.sh

      - name: Paketi doğrula
        run: |
          set -euo pipefail
          APP="dist/GPT-Image Studio.app"
          lipo -archs "$APP/Contents/MacOS/GPT-Image Studio" | tee /dev/stderr | grep -qx arm64
          codesign --verify --strict "$APP"
          for f in static/index.html static/core.js \
                   bundled/logos/kurum-logo-blue.png bundled/logos/kurum-logo-white.png; do
            test -f "$APP/Contents/Resources/$f" || { echo "EKSİK: $f"; exit 1; }
          done
          du -sh "$APP" dist/*.zip

      - uses: actions/upload-artifact@v4
        with:
          name: gpt-image-studio-macos-arm64
          path: dist/GPT-Image Studio.zip
          retention-days: 30
```

**Doğrulama adımı neden şart:** yanlış runner etiketi (`macos-13` x86_64'tür)
sessizce Intel paketi üretir ve kimse fark etmez — ofis Mac'lerinde Rosetta ile
çalışacağı için hata bile vermez, sadece yavaş olur. `grep -qx arm64` bunu
build'i kırarak yakalar.

- [ ] **Step 3: `hiddenimports=[]` bulgusunu arm64'te teyit et**

Task 6 bunu x86_64'te PYZ arşivini sayarak kanıtladı ama host'a özgü. Workflow
başarılı olursa ve `Paketi doğrula` adımı geçerse bulgu arm64'te de geçerlidir.
Kırılırsa `.spec`'e yalnız **kanıtlanabilir** eksik modüller eklenir.

- [ ] **Step 4: Belgeleri güncelle**

`README.md`: gönderim paketinin Actions'tan `workflow_dispatch` ile alındığı,
yereldeki `./build.sh`'in **doğrulama** amaçlı x86_64 ürettiği.
`KURULUM.md`: iş arkadaşlarına giden zip'in arm64 olduğu (Rosetta gerekmez).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/build-macos-arm64.yml README.md KURULUM.md
git commit -m "ci: arm64 macOS paketi için Actions hattı

Derleme makinesi Intel, hedef makineler Apple Silicon; PyInstaller çapraz
derleme yapamıyor. macos-14 runner'ı yerelde doğrulanan build.sh'i
değiştirmeden çalıştırır. Mimari doğrulama adımı yanlış runner etiketinin
sessizce x86_64 üretmesini engeller."
```

> **Not:** workflow'u gerçekten çalıştırmak `push` gerektirir — bu dışa dönük bir
> işlem, kullanıcının kararı. Bu task yalnız hattı yazar.

---

## Bitirme

- [ ] Tüm suite son bir kez: `.venv/bin/python -m pytest tests/ -q` → **645 test PASS**
  (599 taban + 7 paths + 25 composite + 1 logo-500 + 1 logo-e2e + 8 seed + 4 desktop)
  Review sonrası eklenenler: composite 19→25 (4 doğrulama + 2 eksik konum),
  logo-e2e (tarayıcı adımının otomatik ikamesi), seed 6→8 (2 lifespan kanıtı)
- [ ] `git log --oneline 04dab75..HEAD` → 6 task = 6 commit + spec commit
- [ ] Wiki'yi güncelle (`Concepts/GPT-Image Studio.md`): v1.8 bölümü + `log.md` girdisi. Mutlaka yazılacak üç şey:
  1. `composite-logo.py`'nin **iki kopyası** olduğu (repo = uygulama kaynağı, `~/.config/claude-tools/` = blog routine'i) ve golden fixture'ların bu ikisi arasındaki kaymayı ölçtüğü.
  2. Paket içinde veri dizininin `~/Library/Application Support/GPT-Image Studio/` olduğu — kullanıcı verisi orada, silme/yedekleme oradan.
  3. v1.7 notundaki "app.py 921 satır" bilgisinin **stale** olduğu (04dab75 sonrası 765 satır).
- [ ] Zip'i ofis çalışanlarına gönder + `KURULUM.md`'yi ilet.

## Bu planda bilinçli olarak YAPILMAYAN

Windows `.exe`, Apple notarization, otomatik güncelleme, universal2/Intel, DMG
installer, `.app` ikonu (varsayılan PyInstaller ikonu kalır — istenirse ayrı,
küçük bir iş), dış `composite-logo.py`'nin repo modülünü çağıran sarmalayıcıya
indirilmesi.
