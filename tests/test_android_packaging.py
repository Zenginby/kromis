"""Her proje modülü Chaquopy'nin `include "*.py"` desenine uymak ZORUNDA.

Bu dosyanın var oluş sebebi ölçülü bir tuzak: `android/app/build.gradle`'ın
Python kaynak kümesi `srcDirs = ["../.."]` + `include "*.py"` ile kurulu, yani
APK'ya YALNIZ repo kökündeki .py dosyaları giriyor. O desen bilinçli ve gradle
dosyasındaki yorumu gerekçesini yazıyor: `tests/`, `tools/`, `docs/`, `.venv/`
ve `android/` kendiliğinden dışarıda kalsın, büyüyen bir `exclude` listesi
tutulmasın diye.

Bedeli şu: bir gün kod `providers/` ya da `adapters/` gibi bir ALT PAKETE
taşınırsa o paket APK'ya HİÇ girmez. Kırılma sınıfı sinsi —

  • masaüstünde ve testte sorunsuz çalışır (PyInstaller statik analizle bulur,
    pytest repo kökünden koşar),
  • yalnız TELEFONDA `ModuleNotFoundError` verir,
  • ve ancak Android runner'ında (NDK + Gradle, dakikalar süren iş) derlenip
    gerçek bir cihazda açıldığında görünür.

Yani gradle yorumunun "kimsenin bir şeyi hatırlaması gerekmiyor" güvencesi tam
olarak burada tersine dönüyor: yeni bir dizin eklemek SESSİZCE Android'i
bozuyor. Bu test o hatırlamayı mekanik hale getiriyor —
`tests/test_android_apk_name.py` ile birebir aynı gerekçe.

Çoklu model kataloğu bu yüzden kökte düz dosyalar olarak duruyor
(`catalog.py`, `providers.py`, …) ve bir paket DEĞİL.
"""
from __future__ import annotations

import ast
import os
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
GRADLE = REPO / "android" / "app" / "build.gradle"

# Kökteki .py dosyaları = Android'e giren küme = projenin "düz" modül adları.
ROOT_MODULES = {p.stem for p in REPO.glob("*.py")}


def _root_python_dirs() -> set[str]:
    """Repo kökündeki, bir Python paketi gibi import EDİLEBİLECEK dizinler."""
    skip = {".git", ".venv", "tests", "tools", "docs", "android", "build",
            "dist", "__pycache__", "bundled", "static", "branding", "backups"}
    found = set()
    for entry in REPO.iterdir():
        if not entry.is_dir() or entry.name in skip or entry.name.startswith("."):
            continue
        # `__init__.py` olmadan da import edilebiliyor (namespace package):
        # içinde .py varsa aday sayılıyor, yoksa (örn. sadece varlık taşıyan
        # bir klasör) import edilemez ve konumuz değil.
        if any(entry.glob("*.py")):
            found.add(entry.name)
    return found


def test_gradle_hala_yalniz_kok_py_dosyalarini_aliyor():
    """Desen değiştiyse aşağıdaki iddiaların GEREKÇESİ de değişmiş olur.

    Bu iddia kendi başına bir kural değil, bir VARSAYIM MANDALI: `include`
    genişletilirse (örn. `include "*.py", "providers/**"`) alt paket yasağı
    kalkar ve bu dosyadaki diğer testler anlamsız biçimde kırmızı kalır.
    O gün burası düşer ve okuyan kişi neyi güncelleyeceğini bilir.
    """
    gradle = GRADLE.read_text(encoding="utf-8")
    assert re.search(r'include\s+"\*\.py"', gradle), (
        "Chaquopy include deseni değişmiş: bu dosyanın alt paket yasağını "
        "ve gerekçesini gözden geçir.")
    assert re.search(r'srcDirs\s*=\s*\["\.\./\.\."\]', gradle), (
        "Python kaynak dizini artık repo kökü değil: kök .py varsayımı düştü.")


def test_hicbir_proje_moduluu_alt_pakete_cozulmuyor():
    """Kökteki hiçbir modül, kökteki bir DİZİNİ import etmiyor olmalı.

    Import edilen ad hem kökte bir dizin hem de o dizinde .py varsa, o import
    Android'de çözülemez: dizin APK'ya girmiyor.
    """
    paket_adaylari = _root_python_dirs()
    ihlaller = []
    for path in sorted(REPO.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                adlar = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                adlar = [node.module.split(".")[0]]
            elif isinstance(node, ast.ImportFrom):
                # Göreli import (`from . import x`) kökte HİÇ olmamalı:
                # kök modüller paket değil, çalışma anında ImportError verir.
                ihlaller.append(f"{path.name}: göreli import (satır {node.lineno})")
                continue
            else:
                continue
            for ad in adlar:
                if ad in paket_adaylari:
                    ihlaller.append(f"{path.name}: `{ad}` bir alt paket "
                                    f"(satır {node.lineno})")
    assert not ihlaller, (
        "Android APK'sına GİRMEYEN bir pakete import var — telefonda "
        "ModuleNotFoundError olur:\n  " + "\n  ".join(ihlaller))


def test_app_in_import_ettigi_her_proje_modulu_kokte():
    """`app.py`'nin geçişli import kapanışı tümüyle kökte düz dosya olmalı.

    Yukarıdaki test "kökteki bir dizini import etmeyin" diyor; bu test bir
    adım öteye gidip GERÇEKTEN yüklenen kümeyi geziyor, yani ileride bir modül
    `sys.path` oyunuyla dışarıdan bir şey çekerse de yakalanır.
    """
    gorulen: set[str] = set()
    kuyruk = ["app"]
    while kuyruk:
        ad = kuyruk.pop()
        if ad in gorulen:
            continue
        gorulen.add(ad)
        dosya = REPO / f"{ad}.py"
        assert dosya.exists(), (
            f"`{ad}` kökte düz bir .py dosyası değil — Chaquopy'nin "
            f'`include "*.py"` deseni onu APK\'ya almaz.')
        tree = ast.parse(dosya.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                kuyruk += [a.name.split(".")[0] for a in node.names
                           if a.name.split(".")[0] in ROOT_MODULES]
            elif isinstance(node, ast.ImportFrom) and node.module:
                kok = node.module.split(".")[0]
                if kok in ROOT_MODULES:
                    kuyruk.append(kok)

    # Gezinmenin GERÇEKTEN çalıştığını doğrula. Bu iddia olmadan, bir gün
    # `app.py`'nin import'ları taranamaz hale gelirse (ya da yukarıdaki
    # ayrıştırma sessizce boş dönerse) test hiçbir şey ölçmeden yeşil kalırdı —
    # "boş küme üzerinde her şey doğrudur" tuzağı.
    #
    # Çapa olarak `models` ve `storage` seçildi: ikisi de `app.py`'nin
    # doğrudan import'u ve ikisi de kaldırılırsa uygulama zaten açılmaz, yani
    # bu çapanın bayatlaması mümkün değil.
    assert {"models", "storage"} <= gorulen, (
        f"import kapanışı beklenmedik biçimde küçük: {sorted(gorulen)}")
