"""Sürüm yazıcısının sözleşmesi — dosya sistemine hiç dokunmadan.

`tools/surum_yaz.py` yayın hattının en sessiz kırılabilecek adımı: yanlış
yazarsa CI kırmızıya döner (bekçi testleri sayesinde), ama EKSİK yazarsa —
örneğin GUNCELLEME.md'deki elle yazılmış anlatımı silerse — hiçbir şey
kırmızıya dönmez ve kayıp ancak kullanıcı dosyayı okurken fark edilir.

Buradaki iddialar tam olarak o sınıfı kolluyor.
"""
from __future__ import annotations

import os
import subprocess

import pytest

from tools import surum_yaz as sy


# --------------------------------------------------------------------------
# version.py
# --------------------------------------------------------------------------

def test_version_py_yalniz_app_version_satirini_degistirir():
    kaynak = '"""Docstring: 0.4.2 diye bir sayı geçiyor."""\n\nAPP_VERSION = "0.4.2"\n'
    yeni = sy.version_py_yaz(kaynak, "0.5.0")
    assert 'APP_VERSION = "0.5.0"' in yeni
    # Docstring'deki sayı KORUNMALI: version.py'nin başlığı sürüm tarihçesi
    # anlatıyor ("v1.8'e kadar ?v=18 elle artırılıyordu"). Toplu bir değiştirme
    # o anlatımı bozardı.
    assert "Docstring: 0.4.2 diye" in yeni


def test_version_py_satiri_yoksa_sessizce_gecmez():
    with pytest.raises(ValueError):
        sy.version_py_yaz("hiç sürüm yok\n", "0.5.0")


# --------------------------------------------------------------------------
# README
# --------------------------------------------------------------------------

def test_readme_butun_surum_literallerini_gunceller():
    """Rozet ve başlık AYRI AYRI değil topluca değişiyor.

    `test_version.py::test_readme_version_literals_match_the_single_source`
    README'de farklı bir sürüm literali kalmasını da yasaklıyor ("kaçak"
    iddiası). İki hedefi tek tek saymak, üçüncü bir literal eklendiğinde bu
    betiği sessizce eksik bırakırdı — ve o eksiklik yayın yolunda kırmızıya
    dönerdi.
    """
    metin = (
        "[![Release](https://img.shields.io/badge/version-v0.4.2-blue.svg)](x)\n"
        "## ✨ Güncel Özellikler (v0.4.2 & Flow-UI)\n"
        "Ayrıca bir yerde v0.4.2 daha geçiyor.\n"
    )
    yeni = sy.readme_yaz(metin, "0.5.0")
    assert "v0.4.2" not in yeni
    assert yeni.count("v0.5.0") == 3


def test_readme_surum_olmayan_sayilara_dokunmaz():
    metin = "Android 8.0+ ve arm64-v8a destekleniyor. Python 3.14 kullanılıyor.\n"
    assert sy.readme_yaz(metin, "0.5.0") == metin


def test_kokteki_HER_readme_yazicinin_listesinde():
    """İkinci dil sessizce bayatlayabilecek tek yer burası.

    `test_version.py`'nin "kaçak sürüm literali" iddiası YALNIZ README.md'yi
    okuyor; README.en.md rozetinde bayat bir sürümle kalsa hiçbir test kırmızıya
    dönmezdi ve kusur ancak İngilizce sayfaya bakan kişide görünürdü — v0.4.1'de
    Türkçe rozetle yaşanan şeyin birebir aynısı.

    İddia elle yazılmış bir çift ada DEĞİL, depodaki gerçek dosya kümesine
    bağlı: köke üçüncü bir dil eklenirse (README.de.md) liste güncellenene
    kadar kırmızı kalır.
    """
    kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    izlenen = subprocess.run(
        ["git", "-C", kok, "ls-files", "README*.md"],
        check=True, capture_output=True, text=True).stdout.split()
    kok_readmeleri = {y for y in izlenen if "/" not in y}
    yazilanlar = {ad for ad, _ in sy.SURUM_DOSYALARI}

    assert kok_readmeleri, "kökte hiç README bulunamadı — kalıp bayatladı mı?"
    assert kok_readmeleri <= yazilanlar, (
        f"sürüm yazıcısının görmediği README(ler): "
        f"{sorted(kok_readmeleri - yazilanlar)} — rozetleri bayatlar")


def test_surum_yazicisinin_yazdigi_her_dosya_sahneleniyor():
    """Yazmak YETMİYOR: yayın işi dosyayı `git add` ile sahnelemezse yazdığı
    şey koşucuda kalır ve commit'e hiç girmez.

    Bu tam olarak yaşandı: `SURUM_DOSYALARI` README.en.md'yi içeriyordu ve
    `surum_yaz.py` onu her koşuda tazeliyordu, ama `release.yml`'deki
    `git add version.py README.md GUNCELLEME.md` satırında YOKTU. Sonuç:
    v0.19.0 yayımlandığında İngilizce sayfanın rozeti v0.18.0'da kaldı.

    Bir üstteki test yazıcının listesini kolluyor, bu test o listenin karşılığı
    olan sahneleme satırını — ikisi ayrı yerde yaşayan aynı gerçeğin iki
    yarısı. `test_kokteki_HER_readme_yazicinin_listesinde` tek başına yeşil
    kalabildiği için kusuru hiçbir şey görmemişti.
    """
    import yaml

    kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(kok, ".github", "workflows", "release.yml"),
              encoding="utf-8") as f:
        akis = yaml.safe_load(f)

    # Kabuk YORUMLARI ayıklanıyor: bu deponun yorumları kaldırılan/eklenen
    # komutu anlatıyor ve düz bir `in` araması anlatıyı da yakalardı.
    kod = "\n".join(
        s for adim in akis["jobs"]["surum-yaz"]["steps"]
        for s in str(adim.get("run") or "").splitlines()
        if not s.lstrip().startswith("#")
    )
    add_satirlari = [s for s in kod.splitlines() if s.lstrip().startswith("git add")]
    assert add_satirlari, "surum-yaz işinde `git add` satırı bulunamadı"
    sahnelenen = " ".join(add_satirlari)

    eksik = [ad for ad, _ in sy.SURUM_DOSYALARI if ad not in sahnelenen]
    assert not eksik, (
        f"sürüm yazıcısı bu dosyaları yazıyor ama release.yml sahnelemiyor: "
        f"{eksik} — yazdıkları her koşuda atılır"
    )


# --------------------------------------------------------------------------
# GUNCELLEME.md
# --------------------------------------------------------------------------

_GUNCELLEME = (
    "# Kromis Studio — Güncelleme\n\n"
    "Giriş metni.\n\n"
    "## Sürüm 0.4.2 — ne değişti\n\n"
    "- Elle yazılmış eski anlatım.\n\n"
    "---\n\n"
    "## Sürüm 0.4.0 — ne değişti\n\n"
    "- Daha da eski.\n"
)


def test_yeni_bolum_en_uste_girer_ve_eskiler_kalir():
    """Elle yazılmış metni silmek, otomasyonun yapabileceği en pahalı şey:
    kullanıcıya dönük tek anlatım orada ve kaybı hiçbir testte görünmez."""
    yeni = sy.guncelleme_yaz(_GUNCELLEME, "0.5.0", ["Bir şey düzeldi."])
    assert sy.en_ustteki_surum(yeni) == "0.5.0"
    assert "Elle yazılmış eski anlatım." in yeni
    assert "Daha da eski." in yeni
    # Yeni bölüm eskinin ÜSTÜNDE olmalı.
    assert yeni.index("Sürüm 0.5.0") < yeni.index("Sürüm 0.4.2")


def test_ayni_surum_ikinci_kez_yazilmaz():
    """İş yeniden koşabilir (ya da kendi kendini onarma kuralı aynı sürümü
    yeniden yayınlayabilir); bölüm tekrarlanmamalı."""
    bir = sy.guncelleme_yaz(_GUNCELLEME, "0.5.0", ["Bir şey."])
    iki = sy.guncelleme_yaz(bir, "0.5.0", ["Bir şey."])
    assert bir == iki


def test_notlar_madde_olarak_yazilir():
    yeni = sy.guncelleme_yaz(_GUNCELLEME, "0.5.0", ["Birinci.", "İkinci."])
    assert "- Birinci.\n- İkinci." in yeni


def test_not_yoksa_bos_bolum_birakilmaz():
    """Başlığı olup gövdesi olmayan bir bölüm, kullanıcıya "burada bir şey
    olmalıydı" dedirtir."""
    yeni = sy.guncelleme_yaz(_GUNCELLEME, "0.5.0", [])
    assert "Küçük düzeltmeler" in yeni


def test_eski_bicimli_baslik_da_taninir():
    """Dosyada tarihsel olarak "## Sürüm 0.4.0'da ne değişti" biçimi vardı.
    Yeni bölüm onun da üstüne girebilmeli, yoksa dosyanın sonuna düşerdi."""
    eski = "# Başlık\n\n## Sürüm 0.4.0'da ne değişti\n\n- Metin.\n"
    yeni = sy.guncelleme_yaz(eski, "0.5.0", ["Yeni."])
    assert yeni.index("Sürüm 0.5.0") < yeni.index("Sürüm 0.4.0")


def test_hic_surum_bolumu_yoksa_sona_eklenir():
    yeni = sy.guncelleme_yaz("# Başlık\n\nSadece metin.\n", "0.5.0", ["Yeni."])
    assert sy.en_ustteki_surum(yeni) == "0.5.0"
    assert yeni.startswith("# Başlık")


def test_turkce_ek_uretilmiyor():
    """Başlık bilinçle eksiz: "0.4.0'da" ama "0.4.2'de", "0.4.5'te" — ek sayının
    OKUNUŞUNA bağlı ve otomatik üretilirse er geç yanlış çıkar."""
    yeni = sy.guncelleme_yaz(_GUNCELLEME, "0.5.0", ["Bir şey."])
    assert "## Sürüm 0.5.0 — ne değişti" in yeni
