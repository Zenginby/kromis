"""`app.py` bir BİLEŞİM KÖKÜ olarak kalıyor mu — Faz 0 / Adım 2'nin bekçisi.

NEDEN VAR: bölünme tek seferlik bir iş değil, korunması gereken bir durum.
`app.py` 2.299 satır ve 45 rotayken "şu küçük rotayı buraya ekleyeyim" her
zaman en kolay yoldu; paketler doğduktan sonra da öyle kalacak. Bu dosya o
yolu kapatıyor: kökte rota dekoratörü göründüğü, satır sayısı tavanı aştığı
ya da bir service `app`/`routers` ithal ettiği (döngü) anda takım kırmızı.

Ölçümler KAYNAKTAN (AST/metin), çalışma anından değil — `tests/test_catalog.py`
ve `tests/test_graflar.py`nin aynı gerekçesi: ithal zaten olmuşsa geç
kalınmış olurdu. Yalnız "her router takılı mı" sorusu çalışan uygulamaya
bakıyor, çünkü onun cevabı ancak `include_router` çağrıldıktan sonra var.
"""
from __future__ import annotations

import ast
import os
import re

import pytest

import app as appmod
from tools import graf_uret as gu

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. görevin çıkış ölçütü "< 300" (docs/faz0-web-first.md). Bölünme günü 173
# satır; pay, geriye-uyum bloğunun 4. görevde küçülmesini beklerken yeni bir
# ara katman ya da mount eklenebilsin diye.
APP_SATIR_TAVANI = 300

_ROTA_DEKORATORU = re.compile(
    r"^@app\.(?:get|post|put|delete|patch|head|options)\(", re.M)


def _oku(yol: str) -> str:
    with open(os.path.join(REPO, yol), encoding="utf-8") as f:
        return f.read()


def _paket_dosyalari(paket: str) -> list[str]:
    return sorted(f"{paket}/{a}" for a in os.listdir(os.path.join(REPO, paket))
                  if a.endswith(".py") and a != "__init__.py")


def _ithal_ettigi_kok_modüller(yol: str) -> set[str]:
    """Dosyanın ithal ettiği depo modüllerinin KÖK adları (`services.dil` → `services`)."""
    bulunan: set[str] = set()
    for dugum in ast.walk(ast.parse(_oku(yol), filename=yol)):
        if isinstance(dugum, ast.Import):
            bulunan.update(a.name.split(".")[0] for a in dugum.names)
        elif isinstance(dugum, ast.ImportFrom) and dugum.level == 0 and dugum.module:
            bulunan.add(dugum.module.split(".")[0])
    return bulunan


def test_app_py_stays_a_thin_composition_root():
    satir = len(_oku("app.py").splitlines())
    assert satir < APP_SATIR_TAVANI, (
        f"app.py {satir} satır — tavan {APP_SATIR_TAVANI}. Rota ya da yardımcı "
        "eklendiyse yeri routers/ ya da services/ (docs/faz0-web-first.md → 2)")


def test_no_route_is_declared_in_app_py():
    """Kökte `@app.<fiil>(` yok: her rota bir router'da yaşıyor."""
    assert not _ROTA_DEKORATORU.findall(_oku("app.py")), (
        "app.py'de rota dekoratörü var — routers/ altına taşı")


@pytest.mark.parametrize("yol", _paket_dosyalari("routers"))
def test_every_router_module_declares_one_router_and_at_least_one_route(yol: str):
    kaynak = _oku(yol)
    assert re.search(r"^router = APIRouter\(\)$", kaynak, re.M), (
        f"{yol}: `router = APIRouter()` yok (routers/__init__.py sözleşmesi)")
    assert re.search(r"^@router\.(?:get|post|put|delete|patch|head|options)\(",
                     kaynak, re.M), f"{yol}: hiç rota tanımlamıyor"
    # Yollar ÖNEKSİZ ve birebir: `include_router(prefix=)` okumadan grep'lenebilsin.
    assert not re.search(r"APIRouter\(\s*prefix=", kaynak), f"{yol}: prefix kullanıyor"


@pytest.mark.parametrize("yol", _paket_dosyalari("routers"))
def test_a_router_imports_neither_app_nor_another_router(yol: str):
    """Yön tek: app → routers → services. Router'lar arası paylaşım services'te."""
    ithal = _ithal_ettigi_kok_modüller(yol)
    assert "app" not in ithal, f"{yol}: `import app` — döngü"
    assert "routers" not in ithal, f"{yol}: başka bir router'ı ithal ediyor"


@pytest.mark.parametrize("yol", _paket_dosyalari("services"))
def test_a_service_imports_neither_app_nor_routers(yol: str):
    ithal = _ithal_ettigi_kok_modüller(yol)
    assert not ithal & {"app", "routers"}, f"{yol}: yukarı katmanı ithal ediyor: {ithal}"


def test_every_router_module_is_included_in_the_app():
    """`routers/` altına eklenen ama takılmayan bir dosya sessizce ölü rota olur.

    Grafın saydığı rota kümesi (kaynaktan, her router dosyasından) ile çalışan
    uygulamanın rota kümesi aynı olmalı — biri fazlaysa bir `include_router`
    unutulmuştur.
    """
    graftaki = {(r["yontem"], r["yol"]) for r in gu.graf_topla()["uc_noktalar"]}
    calisan = {(yontem, r.path) for r in appmod.app.routes
               if hasattr(r, "methods") for yontem in r.methods
               if not r.path.startswith(("/docs", "/redoc", "/openapi"))}
    assert graftaki == calisan, (
        f"takılmamış: {sorted(graftaki - calisan)}; kaynakta olmayan: "
        f"{sorted(calisan - graftaki)}")
    assert len(graftaki) == 45, "rota sayısı değişti — bilinçliyse bu sayıyı güncelle"


def test_directories_are_read_at_request_time_not_bound_at_import():
    """`OUTPUT_DIR`/`ASSETS_DIR`/`STATIC_DIR` adları router ve service'lerde GEÇMEZ.

    Bir router `from app import OUTPUT_DIR` ya da `paths.output_dir()` ile kendi
    kopyasını alırsa `monkeypatch.setattr(appmod, "OUTPUT_DIR", …)` o rotayı
    ıskalar ve 47 test geliştiricinin gerçek veri dizinine yazar — 2. görevin
    ölçtüğü sızıntı. Tek okuma noktası `services.yollar` (gerekçesi orada).
    """
    for yol in _paket_dosyalari("routers") + _paket_dosyalari("services"):
        kaynak = _oku(yol)
        if yol == "services/yollar.py":
            continue    # okuma noktasının kendisi
        for ad in ("OUTPUT_DIR", "ASSETS_DIR", "STATIC_DIR"):
            assert not re.search(rf"\b{ad}\b", kaynak), (
                f"{yol}: `{ad}` sabitine bağlanıyor — `yollar.{ad.lower()}()` kullan")
        assert "paths.output_dir(" not in kaynak and "paths.assets_dir(" not in kaynak, (
            f"{yol}: dizini doğrudan paths'ten okuyor — yamayı ıskalar")


def test_patching_output_dir_on_app_reaches_the_routers(monkeypatch, tmp_path):
    """Mekanizmanın kendisi: `app.OUTPUT_DIR` yaması `services.yollar`dan görünüyor."""
    from services import yollar
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    assert yollar.output_dir() == str(tmp_path)
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "a"))
    assert yollar.assets_dir() == str(tmp_path / "a")


def test_the_patched_helpers_are_not_re_exported_from_app():
    """Ölü yama kapısı: `appmod._to_png = …` yeni yerini göremez, o yüzden ad yok."""
    for ad in ("_to_png", "_dil", "_now", "_output_png_path", "_read_png_file"):
        assert not hasattr(appmod, ad), (
            f"app.{ad} var — yamalanan yardımcı yeniden dışa aktarılmamalı "
            "(services.gorsel / services.dil yamalanır)")
