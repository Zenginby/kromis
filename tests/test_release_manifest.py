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


def _kod(adim: dict) -> str:
    """Adımın `run` betiği — kabuk YORUMLARI ayıklanmış.

    Gerekiyor çünkü bu deponun yorumları kaldırılan komutu tırnak içinde
    anlatıyor; "şu komut şurada geçiyor" iddiaları anlatıyı da yakalardı.
    §Yazı geleneği: iddia kodu arar, kelimeyi değil.
    """
    return "\n".join(
        s for s in str(adim.get("run") or "").splitlines()
        if not s.lstrip().startswith("#")
    )


def _adimlar(yol: str):
    for is_adi, is_ in (_yaml(yol).get("jobs") or {}).items():
        for adim in (is_.get("steps") or []):
            if isinstance(adim, dict):
                yield is_adi, adim


def _teslim_adimlari(workflow: str) -> list[dict]:
    """Paketi yerine ULAŞTIRAN adımlar: taslak yayına yükleyenler."""
    return [a for _, a in _adimlar(os.path.join(IS_AKISLARI, workflow))
            if "gh release upload" in _kod(a)]


def _teslim_komutlari(workflow: str) -> list[str]:
    """Yalnız `gh release upload` SATIRLARI — adımın tamamı değil.

    Adımın tamamına bakan bir iddia yeterli DEĞİL ve bu ölçüldü: teslim adımı
    sonunda dosya adını yazan bir `echo` taşıyor, yani komuttaki adı bozan bir
    mutasyon "ad adımda geçiyor" iddiasını hayatta bırakıyordu. Mandal
    ANLATIYI değil komutu doğrulamalı — deponun altı kez kaydettiği tuzak.
    """
    return [s for a in _teslim_adimlari(workflow)
            for s in _kod(a).splitlines() if "gh release upload" in s]


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
def test_workflow_delivers_the_asset_under_the_name_the_manifest_expects(ad: str):
    """Çağrılabilir workflow, paketi manifestteki DOSYA ADIYLA teslim etmeli.

    Ad kayarsa taslak dolar ama `yayinla`nın küme denetimi onu tanımaz — ve o
    kırılma ancak gerçek bir yayın koşusunda, dakikalar sonra görünürdü.

    Teslim yolu 2026-08-28'de değişti (Actions varlığı → taslak yayın), iddia
    da onunla taşındı: bakılan yer `upload-artifact`in `path:`i değil, `gh
    release upload` çağrısının kendisi.
    """
    kayit = release_manifest.PAKETLER[ad]
    yol = os.path.join(IS_AKISLARI, kayit["workflow"])
    assert os.path.exists(yol), f"{kayit['workflow']} yok ({ad} için)"

    komutlar = _teslim_komutlari(kayit["workflow"])
    assert komutlar, f"{kayit['workflow']} paketi hiçbir yere teslim etmiyor"
    assert any(ad in s for s in komutlar), (
        f"{kayit['workflow']} teslim KOMUTU {ad!r} yüklemiyor: {komutlar}"
    )


@pytest.mark.parametrize("ad", sorted(release_manifest.PAKETLER))
def test_a_missing_package_turns_the_delivery_red_instead_of_green(ad: str):
    """"Yeşil ama boş" 2026-08-11'de gerçekten oldu: koşu yeşildi, çıktı boştu.

    Eski teslim yolunda kapı `if-no-files-found: error` bayrağıydı. Yeni yolda
    kapı kabuğun kendisi: `gh release upload` var olmayan dosyada sıfırdan
    farklı çıkıyor ve `set -euo pipefail` onu adımın kırmızısına çeviriyor.
    Bayraksız bir `gh` çağrısı gibi, `set -e`siz bir betik de sessizce
    geçerdi — iddia o yüzden bayrağın değil KAPININ yerinde durduğunu ölçüyor.
    """
    workflow = release_manifest.PAKETLER[ad]["workflow"]
    for adim in _teslim_adimlari(workflow):
        kod = _kod(adim)
        assert "set -euo pipefail" in kod, (
            f"{workflow}: teslim adımı `set -euo pipefail` olmadan koşuyor — "
            "eksik dosya adımı kırmızıya düşürmez"
        )
        # Kabuk da iddianın parçası ve bu ÖLÇÜLDÜ: Windows runner'ında `run:`
        # varsayılanı pwsh, orada `set -euo pipefail` bir komut bile değil —
        # yani yukarıdaki iddia doğru görünüp hiçbir şey korumazdı.
        assert adim.get("shell") == "bash", (
            f"{workflow}: teslim adımı kabuğunu açıkça yazmıyor "
            f"({adim.get('shell')!r}) — `set -euo pipefail` her runner'da "
            "aynı şeyi yapmıyor"
        )


def test_the_release_path_never_touches_artifact_storage():
    """Yayın, ÜCRETSİZ OLMAYAN bir kaynağa bağlı kalmamalı.

    2026-08-28: Actions varlık kotası doldu; üç paket de hatasız DERLENDİ ve
    DOĞRULANDI ama teslim edilemedikleri için yayın çıkmadı. Kota boşaltıldıktan
    sonra bile sayaç saatlerce dolu kaldı, yani "biraz yer aç" bir çözüm
    değildi. Yayın varlıkları (Releases altındakiler) o kotaya HİÇ girmiyor;
    kırılgan olan tek şey aradaki ara kopyaydı.

    Bu iddia o kopyanın geri gelmesini yasaklıyor: yayın yolundaki hiçbir
    workflow varlık yüklemiyor ya da indirmiyor.
    """
    yayin_yolu = ["release.yml"] + [k["workflow"] for k in release_manifest.PAKETLER.values()]
    for workflow in yayin_yolu:
        for is_adi, adim in _adimlar(os.path.join(IS_AKISLARI, workflow)):
            eylem = str(adim.get("uses") or "")
            assert not eylem.startswith(("actions/upload-artifact",
                                         "actions/download-artifact")), (
                f"{workflow}:{is_adi} varlık deposuna dokunuyor ({eylem}) — "
                "yayın yolu 2026-08-28'de tam olarak bu yüzden kırıldı"
            )


def test_the_wheel_is_delivered_without_an_artifact_too():
    """Wheel 1.8 MB'dı ve yayını yine de kırdı: kota dolunca boyut önemsiz.

    `_paket-android.yml` wheel workflow'unu bir iş olarak çağırıyor ve wheel'i
    ÖNBELLEKTEN alıyor (ayrı, ücretsiz havuz). Varlık yüklemesi yalnız elle
    tetiklenen Yol A akışı için duruyor, o yüzden çağrıda açıkça kapatılıyor —
    bayrak unutulursa yayın yolu sessizce varlık deposuna geri döner.
    """
    veri = _yaml(os.path.join(IS_AKISLARI, "_paket-android.yml"))
    cagrilar = [i for i in veri["jobs"].values()
                if "build-pydantic-core-android.yml" in str(i.get("uses", ""))]
    assert len(cagrilar) == 1, "wheel workflow'u tam bir kez çağrılmalı"
    assert (cagrilar[0].get("with") or {}).get("varlik_yukle") is False, (
        "_paket-android.yml wheel'i varlık olarak yükletmeye devam ediyor"
    )


def test_only_one_job_may_turn_the_draft_into_a_release():
    """Yayına YAZAN iş bir taneden fazla olamaz.

    v0.4.2'de iki workflow aynı tag'e yazdı: APK'lı yayın 16:15:29'da
    yayımlandı, masaüstü zip'leri 16:17:04'te eklendi — arada ~95 saniye eksik
    bir yayın CANLIYDI ve masaüstü işi kırmızıya düşseydi öyle kalırdı.

    Teslim yolu 2026-08-28'de taslak yayına döndü, yani artık ÜÇ iş aynı yayın
    kaydına yazıyor. Güvence bozulmuyor çünkü yazdıkları şey TASLAK: kullanıcıya
    görünmüyor, tag'i bile yok. Kritik olan tek an, taslağı yayına çeviren
    an — ve iddia tam olarak onu sayıyor, yüklemeleri değil.
    """
    yayimlayanlar = []
    for dosya in sorted(os.listdir(IS_AKISLARI)):
        if not dosya.endswith((".yml", ".yaml")):
            continue
        for is_adi, adim in _adimlar(os.path.join(IS_AKISLARI, dosya)):
            yayimlar = ("--draft=false" in _kod(adim)
                        or "action-gh-release" in str(adim.get("uses", "")))
            if yayimlar:
                yayimlayanlar.append(f"{dosya}:{is_adi}")
    assert yayimlayanlar == ["release.yml:yayinla"], (
        f"yayına çeviren iş(ler): {yayimlayanlar} — tek yazıcı olmalı"
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
    android_is = release_manifest.PAKETLER["kromis-android-arm64.apk"]["is"]
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


# --------------------------------------------------------------------------
# Yayın kapısının KENDİSİ — gömülü betik, sentetik girdiyle
# --------------------------------------------------------------------------

def _kume_denetimi_betigi() -> str:
    """`yayinla` işindeki küme denetiminin gömülü Python'ı.

    Betik YALNIZCA gerçek bir yayın koşusunda çalışıyor, yani bir kusuru ancak
    sürüm harcayarak öğrenirdik — bu dosyanın `test_eksikler_…` testiyle aynı
    gerekçe, bir kat daha derinde: orada kütüphane işlevi sınanıyor, burada
    YAML'a gömülü olan ve `release_manifest`i gerçekten çağıran betiğin ta
    kendisi. TSV ayrıştırması da o betikte yaşıyor ve başka hiçbir yerde
    sınanmıyordu.
    """
    for _, adim in _adimlar(YAYIN_YML):
        kod = _kod(adim)
        if "python - <<'PY'" not in kod:
            continue
        govde = kod.split("python - <<'PY'", 1)[1]
        return govde.split("\nPY", 1)[0]
    raise AssertionError("yayinla işinde gömülü küme denetimi betiği yok")


def _kapiyi_kos(tmp_path, satirlar: list[str]):
    """Betiği verilen varliklar.tsv ile koşturur → (donus_kodu, cikti)."""
    import subprocess
    import sys

    (tmp_path / "varliklar.tsv").write_text(
        "".join(s + "\n" for s in satirlar), encoding="utf-8")
    ortam = dict(os.environ, PYTHONPATH=REPO, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "-"], input=_kume_denetimi_betigi(),
                       cwd=tmp_path, env=ortam, text=True,
                       encoding="utf-8", capture_output=True)
    return p.returncode, p.stdout + p.stderr


def _tam_kume() -> list[str]:
    return [f"{ad}\t{1024 * 1024}" for ad in sorted(release_manifest.PAKETLER)]


def test_the_release_gate_passes_a_complete_draft(tmp_path):
    kod, cikti = _kapiyi_kos(tmp_path, _tam_kume())
    assert kod == 0, cikti
    assert "birebir" in cikti, cikti


def test_the_release_gate_stops_a_draft_that_is_missing_a_package(tmp_path):
    """Asıl vaat: eksik bir paketle yayın OLUŞMAZ (v0.4.2'nin dersi)."""
    eksikli = _tam_kume()
    dusen = eksikli.pop(0).split("\t")[0]
    kod, cikti = _kapiyi_kos(tmp_path, eksikli)
    assert kod == 1, cikti
    assert dusen in cikti, cikti


def test_the_release_gate_stops_a_draft_carrying_something_unexpected(tmp_path):
    """FAZLA da hata: ya bir iş yanlış dosya yükledi ya manifest bayatladı."""
    kod, cikti = _kapiyi_kos(tmp_path, _tam_kume() + ["bayat.zip\t123"])
    assert kod == 1, cikti
    assert "bayat.zip" in cikti, cikti


def test_the_release_gate_stops_a_zero_byte_package(tmp_path):
    """"Yeşil ama boş"un yayın yolundaki son kapısı."""
    bozuk = _tam_kume()
    bozuk[0] = bozuk[0].split("\t")[0] + "\t0"
    kod, cikti = _kapiyi_kos(tmp_path, bozuk)
    assert kod == 1, cikti
    assert "0 baytlık" in cikti, cikti


# --------------------------------------------------------------------------
# Paket doğrulama — yayımlanan SHA-256 özetleri
# --------------------------------------------------------------------------
#
# NEDEN VAR: paketler imzasız dağıtılıyor (macOS noter onayı / Windows
# Authenticode yok). İmza olmayınca "bu dosya gerçekten bu hattan çıktı"
# diyebilmenin kalan tek yolu özet, ve özetin DEĞERİ yayının içinde durmasında:
# sahte bir paketi başka bir yerde dağıtan kişi bu sayfayı değiştiremez.
# Kullanıcıya anlatımı KURULUM.md → "Önce: dosya gerçekten buradan mı geldi?".

def _yayinla_adimlari(yayin_yml: dict) -> list[dict]:
    return yayin_yml["jobs"]["yayinla"]["steps"]


def _adim_sirasi(yayin_yml: dict, parca: str) -> int:
    for i, adim in enumerate(_yayinla_adimlari(yayin_yml)):
        if parca in str(adim.get("name") or ""):
            return i
    raise AssertionError(f"`yayinla` işinde {parca!r} adımı yok")


def test_the_release_publishes_a_checksum_file_for_the_packages(yayin_yml: dict):
    adim = _yayinla_adimlari(yayin_yml)[_adim_sirasi(yayin_yml, "SHA-256")]
    kod = _kod(adim)
    assert "sha256sum" in kod, "özet hiç hesaplanmıyor"
    assert "gh release upload" in kod and "SHA256SUMS.txt" in kod, \
        "özet dosyası yayına eklenmiyor — kullanıcı karşılaştıracak bir şey bulamaz"
    # Adlar manifestten okunuyor, `*` ile değil: bir paket eksikse `sha256sum`
    # kırmızıya düşsün ve çıktı sırası kararlı olsun.
    assert "release_manifest" in kod, \
        "özetlenecek dosya adları manifestten okunmuyor"


def test_the_checksum_step_runs_after_the_completeness_gate_and_before_publish(
        yayin_yml: dict):
    """Sıra anlamın kendisi: eksik bir kümenin özeti yanlış bir güven verirdi,
    yayımlandıktan SONRA eklenen bir özet ise kullanıcıya geç kalırdı."""
    kapi = _adim_sirasi(yayin_yml, "manifestle birebir mi")
    ozet = _adim_sirasi(yayin_yml, "SHA-256")
    yayim = _adim_sirasi(yayin_yml, "Taslağı yayımla")
    assert kapi < ozet < yayim, \
        f"adım sırası bozuk: kapı={kapi}, özet={ozet}, yayım={yayim}"


def test_the_generated_release_notes_are_kept_when_the_checksums_are_appended(
        yayin_yml: dict):
    """`--generate-notes` gövdesinin üzerine yazmak, sürüm notlarını SİLMEK
    olurdu; hattın kullanıcıya dönük tek anlatımı orada."""
    kod = _kod(_yayinla_adimlari(yayin_yml)[_adim_sirasi(yayin_yml, "SHA-256")])
    assert "--json body" in kod, "var olan not gövdesi hiç okunmuyor"
    assert "--notes-file" in kod, "notlar dosyadan yazılmıyor"


def test_the_release_gate_tolerates_a_checksum_file_left_by_a_half_run(tmp_path):
    """Hat yarım kalmış bir taslağı YENİDEN KULLANIYOR (bkz. `taslak` işi).
    İkinci koşu, birincisinin bıraktığı SHA256SUMS.txt'yi taslakta bulur.
    `TURETILEN` ayrımı olmasaydı kapı kendi çıktısını "fazla" sayar ve yayını
    durdururdu — üstelik ancak GERÇEK bir yayın koşusunda, sürüm harcayarak
    öğrenilebilecek bir kusur olarak."""
    kod, cikti = _kapiyi_kos(tmp_path, _tam_kume() + ["SHA256SUMS.txt\t256"])
    assert kod == 0, cikti
    assert "birebir" in cikti, cikti


def test_an_unexpected_file_is_still_caught_next_to_the_checksum_file(tmp_path):
    """`TURETILEN` istisnası, fazlalık denetimini TOPTAN gevşetmiş olmasın."""
    kod, cikti = _kapiyi_kos(
        tmp_path, _tam_kume() + ["SHA256SUMS.txt\t256", "bayat.zip\t123"])
    assert kod == 1, cikti
    assert "bayat.zip" in cikti, cikti


def test_kurulum_tells_the_user_how_to_check_a_package():
    """Özet yayımlanıp nasıl kullanılacağı hiçbir yerde yazmazsa, kimse
    kullanmaz. Üç sistemin üçü de anlatılmak zorunda: Windows'ta `shasum` yok,
    komut `Get-FileHash`."""
    metin = _oku("KURULUM.md")
    assert "SHA-256" in metin
    assert "shasum -a 256" in metin, "macOS/Android doğrulaması anlatılmamış"
    assert "Get-FileHash" in metin, "Windows doğrulaması anlatılmamış"
