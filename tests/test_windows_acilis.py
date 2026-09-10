"""Windows açılış zincirinin mandalları: .NET yapılandırması + CI açılış kapısı.

Bu dosyanın koruduğu şey KOD DEĞİL, KARARLAR. Üçü de "yapıldı görünen ama
hiçbir şey yapmayan" bir değişiklikle sessizce ölebilir:

  1. `Kromis.exe.config` exe'nin YANINDA olmak zorunda. CLR varsayılan
     AppDomain'in config'ini `<exe yolu>.config` diye arıyor; spec'in
     `datas`ına konsa `_internal/` altına iner ve HİÇ okunmaz.
  2. CI açılış kapısı exe'yi GERÇEKTEN beklemek zorunda. Paket
     `console=False`, yani `& $exe` biçiminde yazılmış bir kapı uygulama hiç
     açılmasa da yeşil kalır.
  3. Denetim bayrağının adı `desktop.py` ile workflow arasında paylaşılıyor.
     Bayrağı Python'da yeniden adlandırmak, CI kapısını sessizce kapatır.

Ayrıştırma deseni `tests/test_release_manifest.py`den: iddia KODU arar,
yorumdaki anlatıyı değil (bu deponun yorumları kaldırılan komutu tırnak içinde
anlatıyor).
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

import pytest
import yaml

import desktop

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(KOK, "branding", "Kromis.exe.config")
SPEC = os.path.join(KOK, "kromis.spec")
BUILD_PS1 = os.path.join(KOK, "build.ps1")
WORKFLOW = os.path.join(KOK, ".github", "workflows", "_paket-windows.yml")


def _oku(yol: str) -> str:
    with open(yol, encoding="utf-8") as f:
        return f.read()


def _kod(adim: dict) -> str:
    """Adımın `run` betiği — kabuk YORUMLARI ayıklanmış."""
    return "\n".join(
        s for s in str(adim.get("run") or "").splitlines()
        if not s.lstrip().startswith("#"))


@pytest.fixture(scope="module")
def acilis_kodu() -> str:
    """`--onyukleme-denetimi` koşturan CI adımının yorumsuz betiği."""
    with open(WORKFLOW, encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    adimlar = [a for a in wf["jobs"]["paket"]["steps"]
               if desktop.ONYUKLEME_BAYRAGI in _kod(a)]
    assert len(adimlar) == 1, (
        f"`{desktop.ONYUKLEME_BAYRAGI}` koşturan TAM BİR adım bekleniyordu, "
        f"{len(adimlar)} bulundu — kapı ya kaybolmuş ya çoğalmış")
    return _kod(adimlar[0])


@pytest.fixture(scope="module")
def acilis_adimi() -> dict:
    with open(WORKFLOW, encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    return next(a for a in wf["jobs"]["paket"]["steps"]
                if desktop.ONYUKLEME_BAYRAGI in _kod(a))


# --- 1. .NET yapılandırması -------------------------------------------------

def test_the_dotnet_config_enables_loading_from_remote_sources():
    """Dosyanın var olma sebebi tek bir bayrak; XML ayrıştırılarak okunuyor.

    Metin araması YETMEZDİ: `enabled="false"` de "loadFromRemoteSources"
    içeriyor ve dosya o hâlde hiçbir şey yapmazdı.
    """
    kok = ET.parse(CONFIG).getroot()
    ogesi = kok.find("runtime/loadFromRemoteSources")
    assert ogesi is not None, "loadFromRemoteSources öğesi yok"
    assert ogesi.get("enabled") == "true"


def test_the_config_declares_the_framework_pythonnet_needs():
    """pythonnet 3.x'in Python.Runtime.dll'i netstandard2.0 → .NET Fx 4.7.2."""
    kok = ET.parse(CONFIG).getroot()
    sr = kok.find("startup/supportedRuntime")
    assert sr is not None
    assert sr.get("version") == "v4.0"
    assert "4.7.2" in (sr.get("sku") or "")


def test_the_config_is_named_after_the_executable_in_the_spec():
    """Ad, exe'nin adına BAĞLI: CLR `<exe yolu>.config` arıyor.

    Spec'teki `name=` bir gün değişirse (ör. yeniden adlandırma) bu dosya
    sessizce okunmaz hâle gelirdi; bağı bu satır yazılı tutuyor.
    """
    ad = re.search(r"name='([^']+)'", _oku(SPEC))
    assert ad, "spec'te EXE adı bulunamadı"
    assert os.path.basename(CONFIG) == f"{ad.group(1)}.exe.config"


def test_the_spec_does_not_ship_the_config_as_a_data_file():
    """YASAK: `datas`a koymak `_internal/` altına indirir ve CLR onu HİÇ okumaz.

    "Yapıldı" görünen, hiçbir şey yapmayan değişikliğin tam tanımı. Dosya
    exe'nin yanına build.ps1 tarafından kopyalanıyor.
    """
    assert "Kromis.exe.config" not in _oku(SPEC)


def test_the_build_script_copies_the_config_beside_the_exe():
    kod = _oku(BUILD_PS1)
    assert '"$Exe.config"' in kod, "config exe'nin yanına kopyalanmıyor"
    assert "branding" in kod and "Kromis.exe.config" in kod


def test_the_package_job_asserts_the_config_sits_beside_the_exe():
    """Zip iddiası "bulundu" değil "exe ile AYNI kademede" demeli."""
    with open(WORKFLOW, encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    kod = "\n".join(_kod(a) for a in wf["jobs"]["paket"]["steps"])
    assert "Kromis.exe.config" in kod
    assert "$exeGirdi[0] + '.config'" in kod, (
        "config yalnız ADA göre aranıyor — yanlış yere düşmüş bir kopya geçer")


# --- 2. CI açılış kapısı ----------------------------------------------------

def test_the_open_check_gate_runs_on_every_package_build(acilis_adimi):
    """`if:` YOK: PR'da da yayın yolunda da koşmalı — kapının bütün anlamı bu."""
    assert "if" not in acilis_adimi, acilis_adimi


def test_the_gate_waits_for_the_windowed_executable(acilis_kodu):
    """`& $exe` KAPI DEĞİLDİR ve bu testin tek işi onu yasaklamak.

    Paket `console=False` (GUI alt sistemi): kabuk böyle bir exe'yi BEKLEMEZ,
    hemen döner ve `$LASTEXITCODE` o sürecin kodu bile olmaz. `&` ile yazılmış
    bir kapı, uygulama hiç açılmasa da yeşil kalır — yani adımın var olma
    sebebinin tam tersi. Bekleme `Start-Process -PassThru` + `WaitForExit` ile
    kuruluyor; zaman aşımı da şart, çünkü açılış hatasında `MessageBoxW` modal
    ve iş 45 dakikalık tavana çarpardı.
    """
    assert "Start-Process" in acilis_kodu
    assert "-PassThru" in acilis_kodu
    assert re.search(r"WaitForExit\(\d+\)", acilis_kodu), (
        "süresiz bekleme: modal bir uyarı işi tavana çarptırır")
    assert "ExitCode" in acilis_kodu
    assert not re.search(r"^\s*&\s*\$exe", acilis_kodu, re.MULTILINE)


def test_the_gate_bypasses_the_shell_reputation_check(acilis_kodu):
    """`-NoNewWindow` = UseShellExecute FALSE.

    Varsayılan ShellExecute, MOTW'li bir exe'de SmartScreen diyaloğunu
    tetikleyebilir ve modal pencere runner'da sonsuza kadar bekler. Ölçtüğümüz
    şey SmartScreen değil, assembly yükleme BÖLGESİ.
    """
    assert "-NoNewWindow" in acilis_kodu


def test_the_gate_reproduces_the_users_downloaded_package(acilis_kodu):
    """İKİ senaryo: MOTW'siz (elde doğrulanan hâl) ve MOTW'li (kullanıcının hâli).

    `ZipFile` indirme işaretini YAYMIYOR — yalnız Dosya Gezgini yayıyor. Elle
    basılmazsa ikinci senaryo birincinin kopyası olur: iki yeşil koşu, tek ölçüm.
    """
    assert "ZoneId=3" in acilis_kodu
    assert "Zone.Identifier" in acilis_kodu
    assert acilis_kodu.count("motw = ") == 2, (
        "iki senaryo bekleniyordu (MOTW'li ve MOTW'siz)")


def test_the_gate_proves_the_mark_actually_stuck(acilis_kodu):
    """ÖNCÜL DOĞRULAMASI: ADS yazılamadığı gün adım hiçbir şey ölçmeden yeşil
    kalır ve yalan söyler. Damganın yapıştığı ayrıca denetlenmeli."""
    assert "damgali" in acilis_kodu
    assert "Get-Item" in acilis_kodu and "-Stream" in acilis_kodu


def test_the_gate_prints_the_report_and_the_error_log(acilis_kodu):
    """Kırmızı bir kapının SEBEBİ görünmüyorsa kapı yarım iş yapıyor demektir."""
    assert desktop.ONYUKLEME_RAPORU in acilis_kodu
    assert "hata.log" in acilis_kodu
    assert "Get-Content" in acilis_kodu


def test_the_gate_starts_each_scenario_from_a_clean_data_directory(acilis_kodu):
    """İki senaryo `%LOCALAPPDATA%\\Kromis`yu PAYLAŞIYOR: temizlik unutulursa
    basılan kayıt bir öncekine ait olur ve teşhis yanlış yere bakar."""
    assert "Remove-Item" in acilis_kodu
    assert "hata.log*" in acilis_kodu


def test_the_gate_never_uses_artifact_storage(acilis_kodu, acilis_adimi):
    """2026-08-28'de Actions varlık kotası doldu ve yayın hattı kendi ürettiği
    ikilileri teslim edemedi. Rapor GÜNLÜĞE basılıyor, yüklenmiyor."""
    assert "uses" not in acilis_adimi
    assert "upload-artifact" not in acilis_kodu


# --- 3. iki literalin bağı --------------------------------------------------

def test_the_preflight_flag_in_the_workflow_matches_the_one_in_desktop(acilis_kodu):
    """Bayrak `desktop.py`de TEK kaynak; workflow onu metin olarak kullanıyor.

    Python tarafında yeniden adlandırmak, kapıyı sessizce "hiçbir şey
    çalıştırmayan bir adım" hâline getirirdi — ve o adım yine yeşil olurdu.
    """
    assert desktop.ONYUKLEME_BAYRAGI == "--onyukleme-denetimi"
    assert desktop.ONYUKLEME_BAYRAGI in acilis_kodu


def test_the_report_filename_in_the_workflow_matches_the_one_in_desktop(acilis_kodu):
    assert desktop.ONYUKLEME_RAPORU in acilis_kodu
