"""Paketlerin İÇİNDE ada göre aranan dosyalar depoda gerçekten duruyor mu.

**Bu dosya, CI'daki paketleme kapısından ÇIKARILAN bir güvencenin yeni ve ucuz
karşılığıdır.** 2026-08-28'e kadar `static/` ve `bundled/` altına dokunan her PR
üç paketi birden derletiyordu. Kapının o kapsamı gerçekte tek bir kırılma
sınıfını yakalıyordu: paket doğrulamalarının ADA GÖRE aradığı bir dosyanın
silinmesi ya da yeniden adlandırılması. İçerik değişikliği paketlemeyi zaten
kıramaz, çünkü iki dizin de pakete DİZİN BÜTÜN olarak giriyor
(`gpt-image-studio.spec` → `datas=[('static','static'), ('bundled','bundled')]`;
`android/app/build.gradle` → `into("resources/static") { from("../../static") }`).

Depo `private` olduğu için o kapsamın bedeli gerçek: her ateşleme üç paket, macOS
dakikası 10x. Güvence bu yüzden buraya taşındı — ve taşınırken GENİŞLEDİ:

* eski kapı yalnız `static/` değişen PR'larda ateşleniyordu; bu test HER PR'da
  koşuyor, yani `core.js`i yeniden adlandıran bir değişiklik ötekiler `static/`e
  hiç dokunmasa bile yakalanıyor,
* bedeli üç paketleme koşusu değil, saniyenin altında.

Beklenen dosya listeleri workflow'lardan AYRIŞTIRILIYOR, buraya elle
kopyalanmıyor: elle kopyalanan bir liste, workflow'daki asıl liste değiştiği gün
sessizce ayrışır ve test doğru şeyi ölçmeyi bırakır (aynı gerekçe:
`tests/test_release_manifest.py`).
"""
from __future__ import annotations

import os
import re

import pytest
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = os.path.join(REPO, ".github", "workflows")

PAKET_ISLERI = ("_paket-macos.yml", "_paket-windows.yml", "_paket-android.yml")

# Android APK'da dosyalar `assets/resources/` önekiyle duruyor (Gradle sahneleme
# görevi böyle koyuyor); depo yoluna dönmek için önek atılıyor.
_APK_ONEK = "assets/resources/"

# `static/…` ya da `bundled/…` biçiminde bir veri dosyası yolu. Üç workflow üç
# ayrı kabukta yazılmış (bash `for` döngüsü, PowerShell dizisi, `BEKLENENLER`
# metin bloğu), o yüzden ayrıştırma sözdizimine değil YOLUN KENDİSİNE bakıyor.
_YOL = re.compile(r"(?:assets/resources/)?((?:static|bundled)/[A-Za-z0-9._/-]+)")


def _kod(betik: str) -> str:
    """Betiğin yalnız KODU — kabuk yorumları ayıklanmış.

    Deponun geleneği yorumun kusuru anlatması ve o anlatı dosya adı taşıyor
    (ör. `_paket-macos.yml`in başlığı `static/mobile.css`ten söz ediyor).
    Yorumdan toplanan bir yol, silinmiş bir kontrolü hâlâ varmış gibi
    gösterirdi.
    """
    return "\n".join(s for s in betik.splitlines()
                     if not s.lstrip().startswith("#"))


def _beklenen_yollar(dosya: str) -> set[str]:
    with open(os.path.join(WORKFLOWS, dosya), encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    yollar: set[str] = set()
    for isin in wf["jobs"].values():
        for adim in isin.get("steps", []):
            if "run" not in adim:
                continue
            yollar.update(m.group(1) for m in _YOL.finditer(_kod(adim["run"])))
    return {y[len(_APK_ONEK):] if y.startswith(_APK_ONEK) else y for y in yollar}


@pytest.fixture(scope="module")
def yollar() -> dict[str, set[str]]:
    return {d: _beklenen_yollar(d) for d in PAKET_ISLERI}


@pytest.mark.parametrize("dosya", PAKET_ISLERI)
def test_every_package_job_checks_a_data_file_list(yollar, dosya):
    """Ayrıştırma BOŞ dönerse test sessizce anlamsızlaşır — taban bu yüzden var.

    Bir doğrulama adımı kaldırılırsa ya da liste başka bir biçime taşınırsa
    aşağıdaki "dosyalar duruyor mu" iddiası hiçbir şey sınamadan yeşil kalırdı.
    Beş, bugünkü en dar listenin (Android, 6 yol) altında ve en geniş listenin
    (Windows, 10) çok altında: biçim değişimini yakalar, listeye bir dosya
    eklemeyi/çıkarmayı engellemez.
    """
    assert len(yollar[dosya]) >= 5, f"{dosya}: ayrıştırılan yol {yollar[dosya]}"


def test_files_verified_inside_packages_exist_in_the_repo(yollar):
    """Paketin içinde ADA GÖRE aranan her dosya depoda da o adla durmalı.

    Kırıldığı an: `static/core.js` yeniden adlandırılıp workflow listesi
    güncellenmediğinde. Eskiden bunu ancak paketleme koşusu (dakikalar, üç
    runner) söylüyordu ve yalnız PR `static/`e dokunmuşsa söylüyordu.
    """
    for dosya, kume in yollar.items():
        for yol in sorted(kume):
            tam = os.path.join(REPO, *yol.split("/"))
            assert os.path.isfile(tam), (
                f"{dosya} pakette `{yol}` arıyor ama depoda yok — dosya yeniden "
                f"adlandırıldıysa workflow listesi de güncellenmeli")


def test_the_verified_core_did_not_quietly_shrink(yollar):
    """Listelerin KÜÇÜLMESİ de sessiz bir kayıp; çekirdek burada mandallı.

    Yukarıdaki iddia "listedeki dosyalar var mı" diye soruyor — listeden bir
    satır SİLİNSE o iddia yeşil kalır ve kapsam kimseye haber vermeden daralır.
    Çekirdek, eksikliği hata üretmeyen ama uygulamayı sessizce bozan sınıftan
    seçildi: arayüzün giriş noktası, ana betik, mobil katman, yazı tipi ikilisi
    ve Yönetmen'in gömülü istemi.
    """
    birlesim = set().union(*yollar.values())
    cekirdek = {
        "static/index.html",
        "static/core.js",
        "static/mobile.css",
        "static/mobile.js",
        "static/fonts/dm-sans-v17-latin.woff2",
        "bundled/prompts/prompt-yonetmeni.md",
        # Video bölümü AYRI bir dosya ve düşerse özellik SESSİZCE yarım kalır:
        # `load_video_instructions` yokluğunda boş dönüyor (doğru çalışma-anı
        # davranışı), yani paketten düşen dosya hiçbir hata üretmeden yönetmeni
        # yalnız görsel bilen hâline indirirdi. Tam olarak fontun kapıya giriş
        # gerekçesi.
        "bundled/prompts/prompt-yonetmeni-video.md",
    }
    assert cekirdek <= birlesim, f"paket doğrulamalarından düşmüş: {cekirdek - birlesim}"
