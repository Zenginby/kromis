"""Gradle'ın ürettiği APK adı ile workflow'un aradığı ad AYNI olmak zorunda.

Bu test var, çünkü hata gerçekten oldu: Lumeo yeniden adlandırmasında
`build-android.yml` `lumeo-android-arm64-release.apk`'yı ararken
`android/app/build.gradle`'ın `outputFileName`'i `gpt-image-studio-...` olarak
kaldı. Gradle APK'yı sorunsuz üretti, workflow onu bulamadı ve iş "APK yok"
diyerek düştü.

Kırılma sınıfı sinsi: iki dosya da kendi içinde tutarlı, hata yalnızca
BİRLEŞTİKLERİ yerde var ve ancak Android runner'ında (NDK + Gradle, dakikalar
süren bir iş) görünüyor. Yerelde koşan bu ucuz iddia aynı kaymayı saniyede
yakalıyor — `test_version.py::test_readme_download_links_match_what_the_release_publishes`
ile birebir aynı gerekçe.
"""
from __future__ import annotations

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRADLE = os.path.join(REPO, "android", "app", "build.gradle")
WORKFLOW = os.path.join(REPO, ".github", "workflows", "build-android.yml")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _gradle_release_apk_name() -> str:
    """build.gradle'ın `release` varyantı için ürettiği APK dosya adı.

    Şablondaki `${variant.buildType.name}` yerine "release" konuyor — testin
    çözdüğü tek Gradle ifadesi bu; başka bir interpolasyon eklenirse aşağıdaki
    iddia (şablonda beklenmeyen `${...}` kalmaması) onu gürültülü biçimde
    bildirir.
    """
    text = _read(GRADLE)
    m = re.search(r'output\.outputFileName\s*=\s*"([^"]+)"', text)
    assert m, "build.gradle'da output.outputFileName bulunamadı"
    template = m.group(1)
    name = template.replace("${variant.buildType.name}", "release")
    assert "${" not in name, \
        f"APK adı şablonunda çözülmeyen ifade var: {template!r} — testi güncelle"
    return name


def test_workflow_looks_for_the_apk_gradle_actually_writes():
    """Workflow'un doğruladığı yolun dosya adı, Gradle'ın yazdığı adla aynı olmalı."""
    expected = _gradle_release_apk_name()
    workflow = _read(WORKFLOW)

    m = re.search(r'APK="(android/app/build/outputs/apk/release/[^"]+)"', workflow)
    assert m, "build-android.yml'de release APK yolu bulunamadı"
    aranan = os.path.basename(m.group(1))

    assert aranan == expected, (
        f"workflow {aranan!r} arıyor, Gradle {expected!r} yazıyor — "
        "Gradle APK'yı üretir, workflow bulamaz ve iş 'APK yok' diye düşer"
    )


def test_published_asset_name_matches_the_readme_download_link():
    """Yayına giren APK adı README'nin indirme bağlantısıyla aynı olmalı.

    `test_version.py` bunu `files:` listesi üzerinden zaten çiviliyor; buradaki
    iddia zinciri bir halka geriye götürüyor: `files:`e giren dosya, artifact'ten
    `mv` ile üretiliyor. O iki ad ayrışırsa `mv` hedefi yayına hiç eklenmez.
    """
    workflow = _read(WORKFLOW)

    mv = re.search(r'mv "\$f" (dist/[\w.-]+\.apk)', workflow)
    assert mv, "build-android.yml'de APK'yı yayın adına taşıyan mv bulunamadı"
    yayin = re.search(r'files:\s*(dist/[\w.-]+\.apk)', workflow)
    assert yayin, "build-android.yml'de yayına eklenen APK yolu bulunamadı"

    assert mv.group(1) == yayin.group(1), (
        f"mv {mv.group(1)!r} üretiyor ama yayına {yayin.group(1)!r} ekleniyor — "
        "varlık yayında hiç görünmez"
    )
