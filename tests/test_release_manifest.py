"""Yayına giren paket kümesi HER YERDE aynı mı: manifest ↔ CI ↔ README ↔ GUNCELLEME.

Bu dosyanın var olma sebebi tek bir cümle: **bir platformun atlanması yeşil bir
koşu üretebiliyordu.** v0.4.2'de yayını iki ayrı workflow yazıyordu ve
"yayında hangi paketler olmalı" sorusunun cevabı beş ayrı yerde, birbirinden
habersiz duruyordu — iki `files:` listesi, README tablosu, GUNCELLEME tablosu
ve APK'yı yayın adına taşıyan `mv`. Biri unutulduğunda CI hiçbir şey söylemez;
eksik yayını ancak indirmeye çalışan kullanıcı fark eder.

Artık cevap `release_manifest.py`'de TEK yerde. Buradaki iddialar o tek kaynağın
gerçekten tek kaynak olduğunu, yani ötekilerin ondan ayrışmadığını her PR'da,
saniyeler içinde kanıtlıyor. Dördüncü bir platform eklemek için manifeste bir
satır yazmak yetmez: README'si, GUNCELLEME satırı, çağrılabilir workflow'u ve
`release.yml`'deki işi gelene kadar takım kırmızı kalır.

YAML gerçekten AYRIŞTIRILIYOR (regex ile değil): `needs:` listesi ve `uses:`
yolu hakkındaki iddialar biçimlendirmeye dayanıklı olmalı, yoksa YAML'da bir
satır kaydırması testi sessizce anlamsızlaştırırdı.
"""
from __future__ import annotations

import os
import re

import pytest
import yaml

import release_manifest
import version

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_AKISLARI = os.path.join(REPO, ".github", "workflows")
YAYIN_YML = os.path.join(IS_AKISLARI, "release.yml")


def _oku(*parcalar: str) -> str:
    with open(os.path.join(REPO, *parcalar), encoding="utf-8") as f:
        return f.read()


def _yaml(yol: str) -> dict:
    with open(yol, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def yayin_yml() -> dict:
    return _yaml(YAYIN_YML)


# --------------------------------------------------------------------------
# Manifestin kendi sözleşmesi
# --------------------------------------------------------------------------

def test_manifest_bos_degil():
    """Boş bir manifest bütün kapıları sessizce açardı."""
    assert release_manifest.PAKETLER, "manifest boş — hiçbir kapı bir şey ölçmez"


@pytest.mark.parametrize("ad", sorted(release_manifest.PAKETLER))
def test_manifest_alanlari_tam(ad: str):
    kayit = release_manifest.PAKETLER[ad]
    for alan in ("is", "workflow", "sistem"):
        assert kayit.get(alan), f"{ad}: '{alan}' alanı eksik"


def test_eksikler_hem_eksigi_hem_fazlayi_bildirir():
    """Yayın işindeki küme denetiminin mantığı burada sınanıyor.

    O adım CI'da koşuyor ve ancak gerçek bir yayın koşusunda görülüyor; kuralın
    kendisi burada, bedava kanıtlanıyor."""
    hepsi = sorted(release_manifest.PAKETLER)
    assert release_manifest.eksikler(hepsi) == ([], [])
    assert release_manifest.eksikler(hepsi[1:]) == ([hepsi[0]], [])
    assert release_manifest.eksikler(hepsi + ["bayat.zip"]) == ([], ["bayat.zip"])


# --------------------------------------------------------------------------
# Manifest ↔ CI
# --------------------------------------------------------------------------

def test_yayin_isi_her_paketi_bekliyor(yayin_yml: dict):
    """`yayinla` işi manifestteki HER paket işini `needs:` içinde saymalı.

    Bir işi bu listeden düşürmek, o paket üretilmeden yayın oluşması demekti —
    ve `needs` kenarı olmadığı için hiçbir şey kırmızıya dönmezdi.
    """
    yayinla = yayin_yml["jobs"]["yayinla"]
    needs = yayinla["needs"]
    assert isinstance(needs, list), "yayinla.needs bir liste olmalı"
    for ad, kayit in release_manifest.PAKETLER.items():
        assert kayit["is"] in needs, (
            f"release.yml → yayinla işi {kayit['is']!r} işini beklemiyor; "
            f"{ad} üretilmeden yayın oluşabilir"
        )


def test_her_paket_isi_kendi_workflowunu_cagiriyor(yayin_yml: dict):
    """Manifestteki `is` gerçekten var mı ve manifestteki `workflow`'u mu çağırıyor?"""
    isler = yayin_yml["jobs"]
    for ad, kayit in release_manifest.PAKETLER.items():
        assert kayit["is"] in isler, \
            f"release.yml'de {kayit['is']!r} diye bir iş yok ({ad} için)"
        uses = isler[kayit["is"]].get("uses", "")
        assert uses.endswith(kayit["workflow"]), (
            f"{kayit['is']} işi {uses!r} çağırıyor, manifest {kayit['workflow']!r} diyor"
        )


@pytest.mark.parametrize("ad", sorted(release_manifest.PAKETLER))
def test_workflow_varligi_manifestteki_adla_yukluyor(ad: str):
    """Çağrılabilir workflow, varlığı manifestteki DOSYA ADIYLA yüklemeli.

    Ad kayarsa yayın işi paketi indirir ama küme denetimi onu tanımaz — ve o
    kırılma ancak gerçek bir yayın koşusunda, dakikalar sonra görünürdü.
    """
    kayit = release_manifest.PAKETLER[ad]
    yol = os.path.join(IS_AKISLARI, kayit["workflow"])
    assert os.path.exists(yol), f"{kayit['workflow']} yok ({ad} için)"

    veri = _yaml(yol)
    yollar = []
    for isim, is_ in veri["jobs"].items():
        for adim in is_.get("steps", []) or []:
            if str(adim.get("uses", "")).startswith("actions/upload-artifact"):
                yollar.append(adim.get("with", {}).get("path", ""))
    assert yollar, f"{kayit['workflow']} hiç artifact yüklemiyor"
    assert any(str(p).endswith(ad) for p in yollar), (
        f"{kayit['workflow']} varlığı {yollar} yoluyla yüklüyor, "
        f"manifest {ad!r} bekliyor"
    )


@pytest.mark.parametrize("ad", sorted(release_manifest.PAKETLER))
def test_workflow_bos_yuklemeye_karsi_korumali(ad: str):
    """`if-no-files-found: error` olmadan boş bir yükleme işi YEŞİL bırakır.

    2026-08-11'de tam olarak bu oldu: koşu yeşildi, çıktı boştu. Kapı üç
    workflow'da da duruyor; buradaki iddia dördüncü platform eklendiğinde
    unutulmasını engelliyor.
    """
    veri = _yaml(os.path.join(IS_AKISLARI, release_manifest.PAKETLER[ad]["workflow"]))
    for is_ in veri["jobs"].values():
        for adim in is_.get("steps", []) or []:
            if str(adim.get("uses", "")).startswith("actions/upload-artifact"):
                assert adim.get("with", {}).get("if-no-files-found") == "error", (
                    f"{ad}: upload-artifact adımında if-no-files-found: error yok"
                )


def test_yayini_yalnizca_tek_is_olusturuyor():
    """Yayına YAZAN iş bir taneden fazla olamaz.

    v0.4.2'de iki workflow aynı tag'e yazdı: APK'lı yayın 16:15:29'da yayımlandı,
    masaüstü zip'leri 16:17:04'te eklendi — arada ~95 saniye eksik bir yayın
    canlıydı ve masaüstü işi kırmızıya düşseydi öyle kalırdı. İkinci bir yazıcı
    geri gelirse bu iddia onu yakalar.
    """
    yazicilar = []
    for dosya in sorted(os.listdir(IS_AKISLARI)):
        if not dosya.endswith((".yml", ".yaml")):
            continue
        veri = _yaml(os.path.join(IS_AKISLARI, dosya))
        for is_adi, is_ in (veri.get("jobs") or {}).items():
            for adim in is_.get("steps", []) or []:
                if "action-gh-release" in str(adim.get("uses", "")):
                    yazicilar.append(f"{dosya}:{is_adi}")
    assert yazicilar == ["release.yml:yayinla"], (
        f"yayına yazan iş(ler): {yazicilar} — tek yazıcı olmalı"
    )


def test_butun_workflowlar_gecerli_yaml():
    """Bozuk bir YAML'ı GitHub sessizce YOK SAYAR — koşu hiç başlamaz.

    Yani "workflow kırıldı" belirtisi kırmızı bir koşu değil, KOŞUNUN
    OLMAMASI. Bu deponun yayın yolu artık main'e merge'e bağlı olduğu için o
    sessizlik "yayın çıkmadı ve kimse fark etmedi" demek olurdu.
    """
    for dosya in sorted(os.listdir(IS_AKISLARI)):
        if not dosya.endswith((".yml", ".yaml")):
            continue
        veri = _yaml(os.path.join(IS_AKISLARI, dosya))
        assert isinstance(veri, dict) and veri.get("jobs"), f"{dosya}: iş yok"


def test_cagrilan_workflow_dosyalari_var():
    """`uses: ./.github/workflows/…` yolundaki bir yazım hatası ancak gerçek bir
    koşuda görünür ve koşu daha ilk saniyede düşer — üstelik yayın yolunda."""
    for dosya in sorted(os.listdir(IS_AKISLARI)):
        if not dosya.endswith((".yml", ".yaml")):
            continue
        veri = _yaml(os.path.join(IS_AKISLARI, dosya))
        for is_adi, is_ in (veri.get("jobs") or {}).items():
            uses = str(is_.get("uses", ""))
            if not uses.startswith("./"):
                continue
            assert os.path.exists(os.path.join(REPO, uses[2:])), \
                f"{dosya}:{is_adi} olmayan bir workflow çağırıyor: {uses}"


def test_yayin_yalnizca_main_uzerinde_olusur(yayin_yml: dict):
    """Yayın işi `main` dalına ÇİVİLENMİŞ olmalı.

    `workflow_dispatch` herhangi bir daldan çalıştırılabiliyor ve `surum-yaz`
    işi `git push origin HEAD:main` yapıyor. Bu kapı olmadan, bir dal üzerinden
    (kuru provayı işaretlemeyi unutarak) tetiklenen tek bir koşu o dalın
    içeriğini main'e iter VE o paketlerle gerçek bir yayın yayımlardı — geri
    alması force-push gerektiren bir kaza.

    İddia `if:` metni üzerinden kuruluyor çünkü ölçülecek şey bir davranış
    değil, bir KOŞUL; ve o koşulun gerçekten koştuğunu ancak bir yayın koşusu
    gösterirdi — yani tam olarak sınamak istemediğimiz şey.
    """
    kosul = str(yayin_yml["jobs"]["yayinla"].get("if", ""))
    assert "github.ref == 'refs/heads/main'" in kosul, (
        "yayinla işi main dalına çivilenmemiş — bir daldan tetiklenen dispatch "
        f"gerçek yayın oluşturabilir. Mevcut koşul: {kosul!r}"
    )


def test_surum_yazma_isi_dal_kapisi_tasiyor(yayin_yml: dict):
    """`surum-yaz` main dışında push yapmamalı — kapının birinci yarısı."""
    adimlar = yayin_yml["jobs"]["surum-yaz"]["steps"]
    betikler = "\n".join(str(a.get("run", "")) for a in adimlar)
    assert "refs/heads/main" in betikler, \
        "surum-yaz işinde dal kapısı yok — daldan koşan bir dispatch main'e push edebilir"


def test_android_isi_sirlari_devraliyor():
    """`secrets: inherit` olmadan keystore çözülemez.

    Reusable workflow sırları KENDİLİĞİNDEN devralmaz; bu satır unutulursa
    Android işi imzasız APK üretir ve yayın yolundaki imza kapısı işi
    kırmızıya düşürür — yani yayın hiç çıkmaz. Ucuz bir iddiayla o koşuyu hiç
    başlatmamak daha iyi.
    """
    android_is = release_manifest.PAKETLER["lumeo-android-arm64.apk"]["is"]
    for yol in (YAYIN_YML, os.path.join(IS_AKISLARI, "ci.yml")):
        veri = _yaml(yol)
        is_ = veri["jobs"].get(android_is)
        if is_ is None:
            continue
        assert is_.get("secrets") == "inherit", (
            f"{os.path.basename(yol)}:{android_is} 'secrets: inherit' demiyor — "
            "keystore çözülemez"
        )


# --------------------------------------------------------------------------
# Manifest ↔ belgeler
# --------------------------------------------------------------------------

def test_readme_indirme_baglantilari_manifestle_birebir():
    """README'deki `releases/latest/download/…` kümesi manifestin TAM KENDİSİ olmalı.

    Eksik satır: kullanıcı o platformu hiç göremez. Fazla satır: bağlantı 404
    verir ve bunu hiçbir şey haber vermez — workflow yeşil kalır, yayın oluşur,
    yalnız README'deki bağlantı ölür.
    """
    metin = _oku("README.md")
    bulunan = set(re.findall(r"releases/latest/download/([\w.-]+)", metin))
    assert bulunan == release_manifest.varliklar(), (
        f"README'deki indirme kümesi {sorted(bulunan)}, "
        f"manifest {sorted(release_manifest.varliklar())}"
    )


def test_guncelleme_dosya_tablosu_manifestle_birebir():
    """GUNCELLEME.md'nin en üstündeki "Sistem / Dosya" tablosu manifestle aynı olmalı.

    Kullanıcının "hangi dosyayı indireceğim" sorusunu cevaplayan tek yer orası;
    bayatladığında kullanıcı var olmayan bir dosyayı arar.
    """
    metin = _oku("GUNCELLEME.md")
    satirlar = dict(re.findall(r"^\|\s*([^|]+?)\s*\|\s*`([\w.-]+)`\s*\|\s*$", metin, re.M))
    beklenen = {k["sistem"]: ad for ad, k in release_manifest.PAKETLER.items()}
    assert satirlar == beklenen, (
        f"GUNCELLEME.md tablosu {satirlar}, manifest {beklenen}"
    )


def test_guncelleme_en_ustteki_surum_bolumu_guncel():
    """GUNCELLEME.md'nin en üstteki sürüm bölümü APP_VERSION'ı anlatmalı.

    Bu test var, çünkü hata gerçekten oldu: version.py 0.4.2'deyken GUNCELLEME.md
    hâlâ "Sürüm 0.4.0'da ne değişti" diyordu. Zararı kozmetik değil — kullanıcıya
    dönük TEK anlatım orası ve bayat bir bölüm, gelen paketin ne getirdiğini
    yanlış anlatıyor.

    Bölümü `tools/surum_yaz.py` yazıyor; bu iddia o adımın gerçekten koştuğunun
    kanıtı.
    """
    from tools import surum_yaz

    ust = surum_yaz.en_ustteki_surum(_oku("GUNCELLEME.md"))
    assert ust == version.APP_VERSION, (
        f"GUNCELLEME.md en üstte {ust!r} anlatıyor, version.py {version.APP_VERSION!r}"
    )
