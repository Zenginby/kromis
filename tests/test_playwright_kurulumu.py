"""Playwright'ın PAKET'i ile TARAYICI'sı ayrılamaz — ve yalnız test işine girer.

NEDEN VAR (2026-09-11'de ölçüldü, tahmin değil): `pytest.importorskip("playwright")`
E2E dosyalarını paketin İMPORT EDİLEBİLİRLİĞİNE bakarak atlıyor. Bu bir VEKİL:
asıl sorulan şey "tarayıcı ikilisi var mı", ölçülen şey "pip paketi kurulu mu".
Vekil, paket yalnız tarayıcının da kurulduğu yerde kurulduğu sürece doğru.

`playwright` bir kez `requirements-dev.txt`e konunca vekil kırıldı: `build.sh`
ve `build.ps1` o dosyayı kuruyor VE pytest'i koşturuyor, ama tarayıcı
indirmiyor. Sonuç, üç paketleme işinde birden:

    14 failed … BrowserType.launch: Executable doesn't exist at
    /Users/runner/Library/Caches/ms-playwright/chromium_headless_shell-1234/…

yani atlanması gereken testler ATLANMADI, koşup düştü ve macOS paketi hiç
derlenmeden yayın yolu kırmızıya döndü. Kırılma sessiz değildi ama SEBEBİ
uzaktı: paketleme işinin günlüğünde bir tarayıcı hatası, bir requirements
satırına işaret etmiyor.

Bu dosya o iki sözleşmeyi kapıya çeviriyor.
"""
from __future__ import annotations

import os
import re

import yaml

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_WORKFLOW = os.path.join(KOK, ".github", "workflows", "_test.yml")
# `build.sh`/`build.ps1`ın kurduğu — yani pytest'in tarayıcısız koştuğu ortam.
PAKET_GEREKSINIMLERI = ("requirements.txt", "requirements-dev.txt")


def _adimlar() -> list[dict]:
    with open(TEST_WORKFLOW, encoding="utf-8") as f:
        veri = yaml.safe_load(f)
    isler = veri["jobs"].values()
    return [adim for is_ in isler for adim in is_.get("steps", [])]


def test_playwright_is_not_a_package_build_dependency():
    """Paket işleri pytest'i tarayıcısız koşturuyor — orada İMPORT EDİLEMEZ kalmalı.

    Kurulu olduğu anda `importorskip` atlamayı bırakır ve testler
    `Executable doesn't exist` ile düşer (bkz. dosya başlığı).
    """
    for ad in PAKET_GEREKSINIMLERI:
        with open(os.path.join(KOK, ad), encoding="utf-8") as f:
            satirlar = [s.split("#")[0].strip() for s in f]
        paketler = {re.split(r"[<>=!~\[]", s)[0].strip().lower() for s in satirlar if s}
        assert "playwright" not in paketler, (
            f"{ad} playwright taşıyor: build.sh/build.ps1 onu paketleme işine de "
            "kurar, tarayıcı olmadığı için E2E testleri atlanmak yerine düşer")


def test_the_test_job_installs_the_browser_in_the_same_step_as_the_package():
    """İkisi AYNI adımda — ayrı adımlar ayrışabilir, aynı adım ayrışamaz.

    Ayrı durduklarında birini eklemek ötekini eklemeden mümkün oluyor ve
    kırılma test işinde değil PAKETLEME işinde görünüyor.
    """
    kosanlar = [a.get("run", "") for a in _adimlar()]
    birlikte = [r for r in kosanlar
                if re.search(r"pip install[^\n]*playwright", r)
                and re.search(r"playwright install", r)]
    assert birlikte, (
        "_test.yml'de playwright paketini VE tarayıcısını birlikte kuran "
        "tek bir adım yok")
    assert "chromium" in birlikte[0], (
        "tarayıcı adı verilmemiş: `playwright install` üç motoru birden indirir")
