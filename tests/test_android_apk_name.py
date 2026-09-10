"""Gradle'ın ürettiği APK adı ile workflow'un aradığı ad AYNI olmak zorunda.

Bu test var, çünkü hata gerçekten oldu: bir önceki yeniden adlandırmada Android
workflow'u APK'yı YENİ adıyla ararken `android/app/build.gradle`'ın
`outputFileName`'i ESKİ adda kaldı. Gradle APK'yı sorunsuz üretti, workflow onu
bulamadı ve iş "APK yok" diyerek düştü. (Aynı sınıf 2026-09-10'daki Kromis
adlandırmasında yine masadaydı; APK adı bu yüzden üç platformun yayın varlığı
adlarıyla AYNI commit'e bırakıldı.)

Kırılma sınıfı sinsi: iki dosya da kendi içinde tutarlı, hata yalnızca
BİRLEŞTİKLERİ yerde var ve ancak Android runner'ında (NDK + Gradle, dakikalar
süren bir iş) görünüyor. Yerelde koşan bu ucuz iddia aynı kaymayı saniyede
yakalıyor — `tests/test_release_manifest.py` ile birebir aynı gerekçe.
"""
from __future__ import annotations

import os
import re

import release_manifest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRADLE = os.path.join(REPO, "android", "app", "build.gradle")
# APK'yı üreten workflow'un adı manifestten okunuyor, buraya sabit yazılmıyor:
# dosya yeniden adlandırılırsa (build-android.yml → _paket-android.yml'de tam
# olarak bu oldu) test kırmızı değil, DOĞRU yere bakıyor olmalı.
_APK = "kromis-android-arm64.apk"
WORKFLOW = os.path.join(
    REPO, ".github", "workflows", release_manifest.PAKETLER[_APK]["workflow"]
)


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
    assert m, f"{os.path.basename(WORKFLOW)}'de release APK yolu bulunamadı"
    aranan = os.path.basename(m.group(1))

    assert aranan == expected, (
        f"workflow {aranan!r} arıyor, Gradle {expected!r} yazıyor — "
        "Gradle APK'yı üretir, workflow bulamaz ve iş 'APK yok' diye düşer"
    )


def test_yayin_adina_kopyalanan_dosya_manifestteki_ad():
    """Gradle'ın adıyla yayının adı arasındaki SON halka.

    Zincir şu: Gradle `kromis-android-arm64-release.apk` yazar → workflow onu
    yayın adına kopyalar → o ad manifeste (ve README'ye, GUNCELLEME'ye) girer.
    Yukarıdaki test zincirin ilk halkasını, `test_release_manifest.py` son
    halkasını çiviliyor; bu iddia ortadaki `cp`'yi kolluyor.

    Eskiden burada üçüncü bir ad daha vardı (`dist-kromis-android-arm64.apk`) ve
    yayın işi onu `mv` ile düzeltiyordu — ayrışabilecek fazladan bir isim. O ara
    ad kaldırıldı; workflow doğrudan yayın adına kopyalıyor.
    """
    workflow = _read(WORKFLOW)

    cp = re.search(r'cp "\$\{\{ steps\.dogrula\.outputs\.apk \}\}" (dist/[\w.-]+\.apk)', workflow)
    assert cp, f"{os.path.basename(WORKFLOW)}'de APK'yı yayın adına kopyalayan cp bulunamadı"

    assert cp.group(1) == f"dist/{_APK}", (
        f"workflow {cp.group(1)!r} üretiyor, manifest {_APK!r} bekliyor — "
        "varlık yayının küme denetiminden geçemez"
    )
