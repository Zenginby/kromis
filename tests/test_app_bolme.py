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
from fastapi.testclient import TestClient

import app as appmod
from services import ayar
from tests import conftest
from tools import graf_uret as gu

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. görevin çıkış ölçütü "< 300" (docs/faz0-web-first.md). Bölünme günü 173
# satır, 4. görevde (dizin sabitleri gitti, ayar nesnesi geldi) 175; pay, yeni
# bir ara katman ya da mount eklenebilsin diye.
APP_SATIR_TAVANI = 300

# Bileşim kökü + iki paket: dizinlerin ve `sys.modules`ün ARANDIĞI kaynaklar.
def _urun_dosyalari() -> list[str]:
    return ["app.py"] + _paket_dosyalari("routers") + _paket_dosyalari("services")

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


def _sys_modules_okuyor(kaynak: str, yol: str) -> bool:
    """Kaynakta `sys.modules` ERİŞİMİ var mı (yorum/docstring sayılmaz)."""
    return any(isinstance(d, ast.Attribute) and d.attr == "modules"
               and isinstance(d.value, ast.Name) and d.value.id == "sys"
               for d in ast.walk(ast.parse(kaynak, filename=yol)))


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
    # `appmod.app.routes` DEĞİL: FastAPI 0.137'den beri ağaç (bkz. conftest).
    calisan = {(yontem, yol) for yontem, yol in conftest.duz_rotalar(appmod.app)
               if not yol.startswith(("/docs", "/redoc", "/openapi"))}
    assert graftaki == calisan, (
        f"takılmamış: {sorted(graftaki - calisan)}; kaynakta olmayan: "
        f"{sorted(calisan - graftaki)}")
    # 46 (Faz 0) + 8 hesap rotası (Faz 1 / 3: docs/faz1-veritabani-hesaplar.md §3)
    # + 3 iş rotası (Faz 2 / 4) + 2 (Faz 2 / 5) + 8 admin/kota (Faz 2 / 8:
    # docs/faz2-kuyruk-anahtarlar-depolama.md §8 — `/admin`, 6 `/api/admin/*`, `/api/kota`).
    # 67 → 69 (Faz 3 / 3: admin `plan` ve `kredi` rotaları); 69 → 70 (Faz 3 / 6: `GET /api/kredi`).
    assert len(graftaki) == 70, "rota sayısı değişti — bilinçliyse bu sayıyı güncelle"


def test_directories_are_read_at_request_time_not_bound_at_import():
    """Hiçbir router/service dizini İTHAL ANINDA bağlamaz (Faz 0 / Adım 4).

    Üç yasak: (1) `OUTPUT_DIR`/`ASSETS_DIR`/`STATIC_DIR` adları — eski modül
    sabitleri; (2) `paths.output_dir()`/`paths.assets_dir()` çağrısı — kendi
    kopyasını alan bir router `app.state.ayarlar`ı ıskalar ve o rotayı sınayan
    test geliştiricinin gerçek veri dizinine yazar (2. görevin ölçtüğü sızıntı
    sınıfı); (3) bir modülün `app.py`yi `sys.modules` üzerinden adıyla
    okuması — `services/yollar.py`nin geçici mekanizmasıydı, artık yok.
    Tek istisna `services/ayar.py`: ayar nesnesini `paths`ten KURAN yer.
    """
    for yol in _urun_dosyalari():
        kaynak = _oku(yol)
        # AST'den, metinden DEĞİL: gerekçe yorumları eski mekanizmayı adıyla anıyor.
        assert not _sys_modules_okuyor(kaynak, yol), (
            f"{yol}: `sys.modules` okuyor — dizin (ya da başka bir şey) adıyla değil "
            "`Depends(ayar.ayarlar)` ile gelir")
        if yol in ("app.py", "services/ayar.py"):
            continue    # bileşim kökü ve ayar nesnesini kuran modül
        for ad in ("OUTPUT_DIR", "ASSETS_DIR", "STATIC_DIR"):
            assert not re.search(rf"\b{ad}\b", kaynak), (
                f"{yol}: `{ad}` sabitine bağlanıyor — `ayarlar.{ad.lower()}` kullan")
        assert "paths.output_dir(" not in kaynak and "paths.assets_dir(" not in kaynak, (
            f"{yol}: dizini doğrudan paths'ten okuyor — ayar nesnesini ıskalar")


def test_app_exposes_no_directory_constants():
    """`appmod.OUTPUT_DIR = …` yamasının hedefi kalmadı; ad da kalmamalı.

    Ad dursaydı eski alışkanlıkla yazılan bir yama sessizce hiçbir şeyi
    değiştirmezdi — ölü yama kapısının (`_to_png`) dizin sürümü.
    """
    for ad in ("OUTPUT_DIR", "ASSETS_DIR", "STATIC_DIR", "BASE_DIR"):
        assert not hasattr(appmod, ad), f"app.{ad} hâlâ var — ayar nesnesi app.state.ayarlar"
    assert isinstance(appmod.app.state.ayarlar, ayar.Ayarlar)


def test_every_route_that_touches_a_directory_declares_the_dependency():
    """Dizin okuyan her rota ayar nesnesini `Depends(ayar.ayarlar)` ya da `Depends(ayar.genel)` ile ister.

    Sayı DEĞİL kapsam ölçülüyor: `ayarlar.` yazan her rota dosyasında bu ad
    bir `Depends` parametresinden gelmeli. Rota dışı yardımcılar dizini
    parametre alıyor, yani `ayarlar.` yalnız rota gövdelerinde görünür.
    İki bağımlılık (Faz 1 / 4): `ayarlar` kullanıcıya göre ve kapılı, `genel`
    paylaşılan ve açık — hangisinin nerede meşru olduğu tests/test_kimlik.py'nin işi.
    """
    for yol in _paket_dosyalari("routers"):
        kaynak = _oku(yol)
        if "ayarlar." in kaynak:
            assert "Depends(ayar.ayarlar)" in kaynak or "Depends(ayar.genel)" in kaynak, (
                f"{yol}: ayar nesnesini nereden alıyor?")


@pytest.mark.usefixtures("depo_db")
def test_redirecting_the_settings_object_reaches_the_routers(tmp_path, dizinler, monkeypatch, uret_ve_bitir):
    """Mekanizmanın kendisi: `app.state.ayarlar` yönlendirmesi rotaya ULAŞIYOR.

    `dizinler` fixture'ının bekçisi — fixture yamayı yanlış yere yazsa 60'tan
    fazla test yeşil kalıp geliştiricinin gerçek `output/`una yazardı. Kanıt
    üretim rotasının yazdığı DOSYA (Faz 1 / 5: kayıt DB'de, dosya `ayarlar.output_dir`de).
    """
    import azure_client as ac
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    dizinler(output_dir=str(tmp_path / "output"))
    c = TestClient(appmod.app)
    kayit = uret_ve_bitir(c, "/api/generate", json={"prompt": "kanit", "size": "1024x1024",
                                          "quality": "low", "n": 1}).json()["images"][0]
    gorunen = c.get("/api/history").json()["images"]
    assert [g["prompt"] for g in gorunen] == ["kanit"]
    assert (tmp_path / "output" / kayit["filename"]).is_file()


def test_the_dependency_reads_the_live_settings_object(tmp_path, dizinler, kullanici):
    """`ayar.genel(request)` her çağrıda `app.state`e bakıyor, kopya tutmuyor;
    `ayar.ayarlar` da ondan türüyor (kullanıcı kökü altında, `data_dir` aynı)."""
    from starlette.requests import Request
    istek = Request({"type": "http", "app": appmod.app, "headers": []})
    once = ayar.genel(istek)
    yeni = dizinler(assets_dir=str(tmp_path / "a"), data_dir=str(tmp_path))
    assert ayar.genel(istek) is yeni and yeni is not once
    assert ayar.genel(istek).assets_dir == str(tmp_path / "a")
    ozel = ayar.ayarlar(istek, kullanici)
    assert ozel.data_dir == str(tmp_path) and ozel.static_dir == yeni.static_dir
    assert ozel.assets_dir == str(tmp_path / "kullanicilar" / str(kullanici.id) / "assets")


def test_the_patched_helpers_are_not_re_exported_from_app():
    """Ölü yama kapısı: `appmod._to_png = …` yeni yerini göremez, o yüzden ad yok."""
    for ad in ("_to_png", "_dil", "_now", "_output_png_path", "_read_png_file"):
        assert not hasattr(appmod, ad), (
            f"app.{ad} var — yamalanan yardımcı yeniden dışa aktarılmamalı "
            "(services.gorsel / services.dil yamalanır)")
