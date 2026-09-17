"""Dal nöbetçisi: açık PR'lar main'le birleşebiliyor mu diye bakan iş.

NEDEN VAR: nöbetçinin kendisi bir CI ayarı, yani sessizce silinebilir ya da
işlevsizleştirilebilir — `tests/test_dal_korumasi.py`nin kapattığı kör noktanın
aynısı. Bu dosya, workflow'un ÖLÇÜLMÜŞ bir kusura verdiği cevabı yerinde
tutuyor: PR #17'nin dalı çakışmalı kaldığı sürece `pull_request` tetikleyicisi
birleştirme ref'i üretemedi ve o dalın on iki commit'inin hiçbirinde tek bir
check koşmadı. Nöbetçi o sessizliği duyulur yapıyor.
"""
from __future__ import annotations

import os

import pytest
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YOL = os.path.join(REPO, ".github", "workflows", "dal-nobetcisi.yml")


@pytest.fixture(scope="module")
def is_() -> dict:
    with open(YOL, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def betik(is_: dict) -> str:
    adimlar = is_["jobs"]["nobet"]["steps"]
    return "\n".join(a.get("run", "") for a in adimlar)


def test_the_watchdog_wakes_on_every_push_to_main(is_: dict):
    """Tetikleyici `main`'e push OLMAK ZORUNDA: çakışmayı doğuran olay tam
    olarak budur. Zamanlanmış bir iş aynı şeyi saatler sonra söylerdi."""
    # PyYAML `on:` anahtarını BOOLEAN True'ya çeviriyor (YAML 1.1 mirası).
    tetik = is_.get("on") or is_.get(True)
    assert tetik is not None, "workflow'da `on:` yok"
    assert tetik["push"]["branches"] == ["main"], tetik
    assert "workflow_dispatch" in tetik, "elle tetikleme yolu kapanmış"


def test_the_watchdog_can_mark_the_pull_request(is_: dict):
    """Yetki olmadan iş yeşil görünür ama hiçbir şey işaretlemez — en sinsi
    kırılma biçimi: nöbetçi vardır, nöbet tutmaz."""
    assert is_["permissions"]["pull-requests"] == "write"


def test_the_history_is_complete_enough_to_find_a_merge_base(is_: dict):
    """Sığ klonda ortak ata bulunamaz ve HER PR yalancıktan çakışık görünürdü —
    yani nöbetçi gürültüye dönüşür ve okunmaz olurdu."""
    adimlar = is_["jobs"]["nobet"]["steps"]
    checkout = [a for a in adimlar if str(a.get("uses", "")).startswith("actions/checkout")]
    assert checkout, "checkout adımı yok"
    assert checkout[0]["with"]["fetch-depth"] == 0


def test_the_check_is_a_dry_merge_not_a_test_run(betik: str):
    """İşin UCUZ kalması sözleşmenin parçası (gerekçe ci.yml'in başında: depo
    private, dakika faturalanıyor). Buraya bir takım koşumu eklenirse her main
    push'u ikinci bir tam CI demek olurdu."""
    assert "merge-tree" in betik, "kuru birleştirme yapılmıyor"
    assert "pytest" not in betik, "nöbetçi test koşmaya başlamış"
    assert "test_ortami" not in betik


def test_a_conflict_is_announced_once_and_cleared_automatically(betik: str):
    """İki yön de gerekli. Yalnız işaretleyip hiç kaldırmayan bir nöbetçi,
    çözülmüş PR'ları kalıcı olarak kirli gösterir ve etiket anlamını yitirir;
    her push'ta yeni yorum yazan bir nöbetçi de PR'ı okunamaz yapar."""
    assert "--add-label birlesmiyor" in betik
    assert "--remove-label birlesmiyor" in betik
    assert "gh pr comment" in betik, "çakışma haber verilmiyor"


def test_a_fork_branch_cannot_break_the_watch(betik: str):
    """`origin` çatalın dalını tanımıyor. `set -e` altında sessizce düşen bir
    `git fetch`, tek bir çatal PR'ı yüzünden ÖTEKİ bütün PR'ların denetimini
    iptal ederdi."""
    assert "git fetch -q origin" in betik
    assert "çatal" in betik, "çatal durumu ele alınmamış"
