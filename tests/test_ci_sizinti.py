"""CI'daki `sizinti` işinin (Sızıntı taraması) sözleşmeleri.

Bu iş, bir sırrın depoya girip GEÇMİŞE yerleşmesini yakalayan tek mekanizma.
Kırılması sessiz: yeşil bir CI hâlâ "tarandı" gibi görünür, oysa tarama ya
geçmişi görmemiş ya da muafiyetler onu boşaltmış olur. Aşağıdaki iddialar tam
olarak o iki boşalma biçimini kapatıyor.

İlk koşunun kaydı (2026-08-28): 76 commit, ~3.4 MB, 405 ms, 14 bulgu — hepsi
bilerek sahte test/doküman sabiti, gerçek sır YOK. Gerçek bir sızıntı denemesi
(bir commit'e gerçek biçimli `sk-proj-…` anahtarı) aynı yapılandırmayla exit 1
verdi, yani kapı ölçülerek doğrulandı.

Yapı YAML'dan/TOML'dan AYRIŞTIRILIYOR: satır kaydırması iddiaları
anlamsızlaştırmasın.
"""
from __future__ import annotations

import os
import re

import pytest
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CI_YML = os.path.join(REPO, ".github", "workflows", "ci.yml")
CONFIG = os.path.join(REPO, ".gitleaks.toml")


@pytest.fixture(scope="module")
def is_() -> dict:
    with open(CI_YML, encoding="utf-8") as f:
        isler = yaml.safe_load(f)["jobs"]
    assert "sizinti" in isler, "sızıntı taraması işi CI'dan düşmüş"
    return isler["sizinti"]


@pytest.fixture(scope="module")
def betik(is_) -> str:
    (adim,) = [a for a in is_["steps"] if "run" in a]
    return adim["run"]


@pytest.fixture(scope="module")
def yapilandirma() -> str:
    with open(CONFIG, encoding="utf-8") as f:
        return f.read()


def test_the_scan_reads_the_whole_history_not_just_the_diff(is_, betik):
    """Sırrın silinmesi onu geçmişten SİLMEZ — commit hâlâ okunabiliyor.

    İki yarısı da gerekli: `fetch-depth: 0` olmadan geçmiş yerelde YOK (sığ
    klon), `git` altkomutu olmadan da gitleaks yalnız çalışma ağacına bakar.
    Biri düşerse tarama sessizce son commit'lik bir taramaya iner.
    """
    checkout = [a for a in is_["steps"] if str(a.get("uses", "")).startswith(
        "actions/checkout")]
    assert checkout, "checkout adımı yok"
    assert checkout[0].get("with", {}).get("fetch-depth") == 0, (
        "sığ klon: tarama geçmişi hiç görmüyor")
    assert re.search(r"gitleaks\s+git\b", betik), (
        "gitleaks `git` altkomutuyla çağrılmıyor: yalnız çalışma ağacı taranır")


def test_the_binary_is_pinned_by_version_and_checksum(is_, betik):
    """Sürüm + sha256 çifti: koşan ikili denetlenebilir, yükseltme diff'te görünür."""
    ortam = is_["steps"][-1].get("env", {})
    assert re.fullmatch(r"\d+\.\d+\.\d+", str(ortam.get("SURUM", ""))), (
        "gitleaks sürümü sabitlenmemiş")
    assert re.fullmatch(r"[0-9a-f]{64}", str(ortam.get("SHA256", ""))), (
        "indirilen arşivin sha256'sı yazılı değil")
    assert "sha256sum -c -" in betik, (
        "sağlama toplamı DOĞRULANMIYOR: yazılı olması tek başına bir şey kanıtlamaz")


def test_a_finding_fails_the_job_and_stays_out_of_the_log(betik):
    """Bulgu işi kırmızıya düşürüyor, ama sır günlüğe DÖKÜLMÜYOR."""
    assert "set -euo pipefail" in betik, (
        "sıfırdan farklı çıkış yutulur: bulgu varken iş yeşil kalır")
    assert "--redact" in betik, (
        "sır koşu günlüğüne yazılır: bulgu ikinci bir yere sızdırılmış olur")


def test_the_scan_uses_the_repository_config(betik, yapilandirma):
    assert "--config .gitleaks.toml" in betik, (
        "yapılandırma verilmiyor: muafiyetler hiç uygulanmaz, iş sürekli kırmızı")
    assert "useDefault = true" in yapilandirma, (
        "varsayılan kural kümesi devre dışı: tarama neredeyse hiçbir şey aramaz")


def test_the_allowlist_never_exempts_a_whole_directory():
    """Muafiyet DEĞERE bakıyor, yola değil.

    `paths = ['''^tests/''']` yazmak tarama yükünü sıfırlardı ve tam da
    fixture'ların yaşadığı yeri kör ederdi: bir gün gerçekten bir teste
    yapıştırılan gerçek anahtar sessizce geçerdi. Bugünkü muafiyetlerin hepsi
    tek tek yazılmış SAHTE değerler.
    """
    with open(CONFIG, encoding="utf-8") as f:
        tomlu = f.read()
    kod = "\n".join(s for s in tomlu.splitlines() if not s.lstrip().startswith("#"))
    assert not re.search(r"^\s*paths\s*=", kod, re.M), (
        "yol tabanlı muafiyet girmiş: taramanın gözü o dizinde kapanır")
    assert not re.search(r"^\s*stopwords\s*=", kod, re.M), (
        "stopwords listesi girmiş: muafiyet değerden değil kelimeden okunur")
