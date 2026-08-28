"""CI'daki `kapsam` işinin (Paketleme kapsamı) sözleşmeleri.

Bu iş "hangi PR üç paketi de derlesin" sorusunu yanıtlıyor. Kırılması ÇİFT
maliyetli, ve ikinci yarısı sessiz: iş kırılınca `paketle` çıktısı boş kalıyor,
`if: needs.kapsam.outputs.paketle == 'evet'` koşulu tutmuyor ve macOS/Windows/
Android işleri ATLANIYOR — yani `static/` ya da `android/` değişmiş bir PR
paketleme kapısından hiç geçmemiş oluyor.

v0.9.1'de tam bu oldu (PR#50). Adım tabanı `--depth=1` ile çekiyordu; sığ çekim
`.git/shallow` graftını yazıp dalı tek commit'e kırpıyor, PR CI koşarken merge
edilince taban öteleniyor ve `git diff A...B` ortak ata bulamıyor:
`fatal: no merge base`, exit 128.

İlk düzeltme tabanı `pull_request.base.sha`dan okudu; kırılmayı bitirdi ama
kapsamı fazla açtı — o SHA olayın çekildiği andaki taban, HEAD ise merge ref'i
yeniden hesaplandıkça GÜNCEL tabanı içeriyor, yani senkronlanmayan bir PR'da
diff'e araya giren main commit'leri de giriyordu. Bugünkü taban merge
commit'in KENDİ ebeveynleri (`HEAD^1...HEAD^2`): yarışan bir dal tepesi yok.

Yapı YAML'dan AYRIŞTIRILIYOR (test_release_manifest.py'nin gerekçesi):
satır kaydırması iddiaları anlamsızlaştırmasın.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess

import pytest
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CI_YML = os.path.join(REPO, ".github", "workflows", "ci.yml")


@pytest.fixture(scope="module")
def ci() -> dict:
    with open(CI_YML, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _bak_adimi(ci: dict) -> dict:
    """Betiği koşan adım — SIRAYA göre değil `run` anahtarına göre bulunuyor.

    Bir zamanlar `steps[-1]` yazılıydı ve iddia "run adımı son adımdır"
    varsayımını taşıyordu; oysa bu dosyanın kendi gerekçesi satır/sıra
    kaymasından bağımsız olmak. Adıma bir `if:` ya da bir kurulum adımı
    eklendiği gün varsayım sessizce yanlışa dönerdi.
    """
    adimlar = [a for a in ci["jobs"]["kapsam"]["steps"] if "run" in a]
    assert len(adimlar) == 1, f"kapsam işinde beklenmeyen sayıda run adımı: {len(adimlar)}"
    return adimlar[0]


@pytest.fixture(scope="module")
def kapsam_betigi(ci: dict) -> str:
    return _bak_adimi(ci)["run"]


@pytest.fixture(scope="module")
def kapsam_kodu(kapsam_betigi: str) -> str:
    """Betiğin YALNIZ kodu — kabuk yorumları ayıklanmış.

    Gerekmesinin sebebi: adımın içindeki yorum kaldırılan satırları TIRNAK
    İÇİNDE anlatıyor (deponun geleneği, kusuru kaydeden yorum) ve "şu satır
    olmasın" iddiaları o anlatıyı da yakalıyordu. Yorum kalmalı, iddia ise
    gerçekten koşan kodu ölçmeli.
    """
    return "\n".join(satir for satir in kapsam_betigi.splitlines()
                     if not satir.lstrip().startswith("#"))


def test_kapsam_tam_gecmisle_checkout_ediyor(ci: dict):
    """`fetch-depth: 0` olmadan merge commit'in EBEVEYNLERİ yerelde olmaz.

    Diff ek bir fetch yapmıyor, tabanı `HEAD^1` olarak okuyor. Sığ bir çekimde
    yalnız merge commit'in kendisi iniyor: `HEAD^1` çözülemez, adım güvenli
    tarafa düşer ve kapı bir daha hiçbir PR'ı ayırt etmez — hep `evet` der.
    """
    checkout = [a for a in ci["jobs"]["kapsam"]["steps"]
                if str(a.get("uses", "")).startswith("actions/checkout")]
    assert checkout, "kapsam işinde checkout adımı yok"
    assert checkout[0].get("with", {}).get("fetch-depth") == 0, checkout[0]


def test_kapsam_merge_refini_checkout_ediyor(ci: dict):
    """`ref:` PINLENMEMELİ — `HEAD^2`nin var olma sebebi merge ref'i.

    `pull_request` olayında checkout'un varsayılanı `refs/pull/N/merge`, yani
    HEAD bir merge commit ve iki ebeveyni var. `ref: …head.sha` yazıldığı an
    HEAD sıradan bir commit'e döner, `HEAD^2` çözülemez ve kapı sessizce
    güvenli tarafa düşer: kırılmaz, ama ayırt etmeyi de bırakır.
    """
    checkout = [a for a in ci["jobs"]["kapsam"]["steps"]
                if str(a.get("uses", "")).startswith("actions/checkout")]
    assert "ref" not in checkout[0].get("with", {}), checkout[0]


def test_kapsam_tabani_sig_cekmiyor(kapsam_kodu: str):
    """Sığ çekim YASAK — v0.9.1'i kıran satır buydu.

    `--depth=1` bir `.git/shallow` graftı yazıyor ve dalı tek commit'e kırpıyor;
    PR CI koşarken merge edilirse `A...B` ortak ata bulamaz ve iş exit 128 ile
    ölür. checkout zaten tam geçmişi almış durumda, yani çekimin kendisi de
    gereksizdi.
    """
    assert "--depth" not in kapsam_kodu, "kapsam adımı sığ çekim yapıyor"
    assert "git fetch" not in kapsam_kodu, (
        "kapsam adımı yeniden fetch ediyor: checkout tam geçmişi aldı, ek çekim "
        "yalnızca graft riski getirir"
    )


def test_kapsam_tabani_merge_commitin_ebeveynlerinden_okuyor(ci: dict, kapsam_kodu: str):
    """Taban ne dal ADI ne olaydan gelen bir SHA: merge commit'in ebeveyni.

    `HEAD^1...HEAD^2` üç kusuru birden kapatıyor — dal tepesi merge ile
    ötelenemiyor (1. kusur), olaydan gelen taban eskiyip diff'e yabancı
    commit'ler sokamıyor (2. kusur) ve ek bir fetch gerekmiyor.
    """
    assert "HEAD^1...HEAD^2" in kapsam_kodu, kapsam_kodu
    assert "origin/$TABAN..." not in kapsam_kodu, "taban dal adından okunuyor"
    # `base.sha` fazla kapsayan hâlin imzası: geri gelirse iddia düşsün.
    assert "base.sha" not in kapsam_kodu, (
        "taban olaydan okunuyor: merge ref'i yeniden hesaplandıkça HEAD ilerler, "
        "o SHA ilerlemez ve diff araya giren main commit'lerini de kapsar")
    ortam = _bak_adimi(ci).get("env", {})
    assert "TABAN_SHA" not in ortam, (
        f"kullanılmayan taban değişkeni duruyor: {ortam}")
    assert "ETIKETLER" in ortam, "kaçış kapısının etiket girdisi kaybolmuş"


def test_kapsam_diff_kurulamazsa_guvenli_tarafa_dusuyor(kapsam_betigi: str):
    """Diff kurulamazsa kapı KIRILMAMALI, `evet` demeli.

    Kırılmanın bedeli paketlemenin sessizce atlanması; gereksiz bir paketleme
    koşusunun bedeli bedava runner dakikası. Yol listesinin bilinçle geniş
    tutulmasıyla aynı tercih.
    """
    assert 'if ! YOLLAR="$(git diff' in kapsam_betigi, (
        "diff hatası yakalanmıyor: `set -euo pipefail` altında iş ölür ve üç "
        "paketleme işi atlanır"
    )
    kurtarma = kapsam_betigi.split('if ! YOLLAR=', 1)[1].split("fi", 1)[0]
    assert "paketle=evet" in kurtarma, kurtarma


def test_paketleme_isleri_kapsama_bagli(ci: dict):
    """Üç paket de `kapsam` çıktısına bakmalı — kapının bir işi olduğunun kanıtı.

    Bu bağ kopsa yukarıdaki iddiaların hiçbirinin bir bedeli kalmaz.
    """
    for is_adi in ("paket-macos", "paket-windows", "paket-android"):
        isin = ci["jobs"][is_adi]
        assert "kapsam" in isin["needs"], is_adi
        assert isin["if"] == "needs.kapsam.outputs.paketle == 'evet'", is_adi


def test_kapsam_yol_listesi_bilincle_dar(kapsam_kodu: str):
    """Liste ne kazayla genişlemeli ne kazayla daralmalı — ikisi de bedelli.

    Kapı 2026-08-28'de DARALTILDI: `static/` ve `bundled/` çıkarıldı. Karar
    ölçüye dayanıyor — iki dizin de pakete DİZİN BÜTÜN olarak giriyor
    (`gpt-image-studio.spec`in `datas`ı, `android/app/build.gradle`ın sahneleme
    görevi), yani içerik değişikliği paketlemeyi kıramaz. Kırabilen tek sınıf
    (doğrulamaların ADA GÖRE aradığı bir dosyanın yeniden adlandırılması) artık
    `tests/test_paket_icerik_listesi.py`de, üç runner yerine saniyenin altında
    ve YALNIZ `static/` değil her PR'da ölçülüyor.

    Bedeli çift taraflı olduğu için iddia TAM KÜME: bir yol eklemek de çıkarmak
    da bu satırı değiştirmeyi gerektirir, yani karar yazılı kalır. Depo `private`
    (2026-08-28, REST) — listeye giren her yol faturalanan dakika, macOS'ta 10x.
    """
    desen = re.search(r"grep -qE '\^\(([^)]+)\)'", kapsam_kodu)
    assert desen, kapsam_kodu
    yollar = {y.replace("\\.", ".") for y in desen.group(1).split("|")}
    assert yollar == {
        "gpt-image-studio.spec",
        "build.sh",
        "build.ps1",
        "requirements.txt",
        "android/",
        ".github/workflows/",
        "branding/",
    }, yollar


def test_kapsam_dizin_butun_kopyalanan_yollari_izlemiyor(kapsam_kodu: str):
    """`static/` ve `bundled/` GERİ GELMEMELİ; sebebi bu iddianın kendisi.

    Ayrı bir iddia, çünkü tam küme testi bir gün meşru bir yol eklendiğinde
    güncellenecek ve o güncellemede bu ikisi sessizce geri sızabilir. Geri
    gelmelerinin tek meşru sebebi olurdu: spec'in `datas`ı ya da Gradle'ın
    sahneleme görevi dosyaları dizin olarak değil ADA GÖRE saymaya başlarsa.
    """
    for yol in ("static/", "bundled/"):
        assert f"|{yol}" not in kapsam_kodu, (
            f"`{yol}` kapıya geri gelmiş: pakete dizin bütün olarak giren bir "
            f"dizin, içeriği değiştiği için üç paketi derletmemeli "
            f"(bkz. tests/test_paket_icerik_listesi.py)")


# ══════════════════════════════════════════════════════════════════════
# Betiği GERÇEKTEN koşturan bölüm
#
# Yukarıdaki iddialar betiğin METNİNİ ölçüyor, kararını değil. Oysa bu işin tek
# ürünü bir karar (`paketle=evet|hayir`) ve o karar bugüne dek yalnız gerçek bir
# PR koşusunda görülebiliyordu — yani bir kusuru ya üç paketleme koşusu
# harcayarak ya da daha kötüsü kapıyı sessizce atlayarak öğrenirdik.
# `tests/test_release_manifest.py`in yayın kapısı için kurduğu desenin aynısı:
# betik YAML'dan çıkarılıyor, `git`in yerine sentetik bir diff konuyor.
# ══════════════════════════════════════════════════════════════════════

BASH = shutil.which("bash")

# Windows'ta Git Bash yoksa bu bölüm atlanır; metin iddiaları orada da koşuyor.
bash_gerekli = pytest.mark.skipif(BASH is None, reason="bash yok (Windows)")


def _kapsami_kos(tmp_path, degisen: list[str], etiketler: str = "",
                 git_duser: bool = False):
    """Kapsam betiğini sentetik bir diff ile koşturur → (dönüş kodu, karar, çıktı).

    Gerçek bir depo kurup merge commit üretmek yerine diff'in ÇIKTISI doğrudan
    veriliyor: ölçülen şey zaten diff değil, ondan çıkan karar.

    `git` bir KABUK İŞLEVİYLE değiştiriliyor, PATH'in başına konan sahte bir
    betikle DEĞİL. Sebebi ölçüldü, tahmin edilmedi: PATH yolu Linux'ta
    çalışıyordu, Windows'ta çalışmıyordu. Git Bash komut ararken uzantısız
    `git` dosyasını atlayıp gerçek `git.exe`i buluyor; betik depo OLMAYAN bir
    dizinde `git diff` koşuyor ("Not a git repository"), düşüyor ve kapı
    GÜVENLİ TARAFA düşüyor. Bedeli iki katmanlı ve ikincisi sinsi: `hayir`
    bekleyen beş test kırmızıya düşüyordu (Windows paketleme işi 60440da'da
    tam olarak bunu gösterdi), `evet` bekleyenler ise DOĞRU SEBEPLE DEĞİL
    kazara geçiyordu — yani o platformda test hiçbir şey ölçmüyordu.

    Kabuk işlevi harici komuttan önce çözüldüğü için üç platformda da aynı
    şeyi ölçüyor. Aşağıdaki `diff kurulamadı` iddiası da o sessiz hâlin
    kapısı: sahte `git` bir gün yine devreye girmezse test artık kazara
    geçmek yerine bunu SÖYLÜYOR.
    """
    if git_duser:
        onek = "git() { return 1; }\n"
    else:
        onek = ("git() { printf '%s\\n' "
                + " ".join(shlex.quote(y) for y in degisen) + "; }\n")

    cikti = tmp_path / "github_output"
    cikti.write_text("", encoding="utf-8")
    ortam = dict(os.environ, GITHUB_OUTPUT=str(cikti), ETIKETLER=etiketler)
    with open(CI_YML, encoding="utf-8") as f:
        betik = _bak_adimi(yaml.safe_load(f))["run"]
    p = subprocess.run([BASH, "-c", onek + betik], cwd=tmp_path, env=ortam,
                       text=True, encoding="utf-8", capture_output=True)
    karar = ""
    for satir in cikti.read_text(encoding="utf-8").splitlines():
        if satir.startswith("paketle="):
            karar = satir.split("=", 1)[1]
    tumu = p.stdout + p.stderr
    if not git_duser:
        assert "diff kurulamadı" not in tumu, (
            "sahte `git` devreye girmemiş: karar sentetik diff'ten değil "
            f"gerçek `git`ten geliyor — bu koşu hiçbir şey ölçmüyor.\n{tumu}")
    return p.returncode, karar, tumu


@bash_gerekli
@pytest.mark.parametrize("degisen", [
    ["static/core.js"],
    ["static/core.js", "static/mobile.css", "app.py", "tests/test_index.py"],
    ["bundled/prompts/prompt-yonetmeni.md"],
    ["app.py"],
    ["README.md", "docs/graflar/moduller.md"],
])
def test_the_gate_skips_packaging_when_nothing_can_break_it(tmp_path, degisen):
    """Turun ASIL vaadi: ön yüz PR'ı artık üç paketi derletmiyor.

    `static/` ve `bundled/` pakete dizin bütün olarak giriyor, yani içerikleri
    paketlemenin sonucunu değiştiremez. Depo `private` olduğu için bu koşuların
    bedeli gerçek (macOS dakikası 10x) — kararın kendisi bu yüzden ölçülüyor.
    """
    kod, karar, cikti = _kapsami_kos(tmp_path, degisen)
    assert kod == 0, cikti
    assert karar == "hayir", cikti


@bash_gerekli
@pytest.mark.parametrize("degisen", [
    ["gpt-image-studio.spec"],
    ["build.sh"],
    ["build.ps1"],
    ["requirements.txt"],
    ["android/app/build.gradle"],
    [".github/workflows/_paket-macos.yml"],
    ["branding/lumeo.ico"],
    ["static/core.js", "gpt-image-studio.spec"],
])
def test_the_gate_still_packages_what_can_actually_break(tmp_path, degisen):
    """Daraltma, kapının işini bırakması DEĞİL.

    Son satır karışık bir PR: paketlemeye dokunan tek bir dosya, `static/`
    yığınının içinde de olsa kapıyı açmaya yetiyor.
    """
    kod, karar, cikti = _kapsami_kos(tmp_path, degisen)
    assert kod == 0, cikti
    assert karar == "evet", cikti


@bash_gerekli
def test_the_full_matrix_label_overrides_the_path_filter(tmp_path):
    """Kaçış kapısı: daraltmadan sonra tam matris istemenin YOLU bu.

    `static/`e dokunan bir PR'da yine de üç paketi görmek isteyen bakımcı
    `tam-paket` etiketini koyuyor. Etiketsiz aynı diff `hayir` diyor (yukarıdaki
    test), yani bu iddia gerçekten etiketi ölçüyor.
    """
    kod, karar, cikti = _kapsami_kos(tmp_path, ["static/core.js"],
                                     etiketler="belgeler,tam-paket")
    assert kod == 0, cikti
    assert karar == "evet", cikti


@bash_gerekli
def test_the_gate_falls_to_the_safe_side_when_the_diff_fails(tmp_path):
    """v0.9.1'in kusuru: diff kurulamayınca kapı KIRILMAMALI, `evet` demeli.

    Metin iddiası (`test_kapsam_diff_kurulamazsa_guvenli_tarafa_dusuyor`) o
    satırın varlığını sınıyor; bu iddia `set -euo pipefail` altında işin
    gerçekten ölmediğini ve kararın `evet` çıktığını sınıyor.
    """
    kod, karar, cikti = _kapsami_kos(tmp_path, [], git_duser=True)
    assert kod == 0, cikti
    assert karar == "evet", cikti
