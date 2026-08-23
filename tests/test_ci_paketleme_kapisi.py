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

Yapı YAML'dan AYRIŞTIRILIYOR (test_release_manifest.py'nin gerekçesi):
satır kaydırması iddiaları anlamsızlaştırmasın.
"""
from __future__ import annotations

import os

import pytest
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CI_YML = os.path.join(REPO, ".github", "workflows", "ci.yml")


@pytest.fixture(scope="module")
def ci() -> dict:
    with open(CI_YML, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def kapsam_betigi(ci: dict) -> str:
    adimlar = ci["jobs"]["kapsam"]["steps"]
    betikler = [a["run"] for a in adimlar if "run" in a]
    assert len(betikler) == 1, f"kapsam işinde beklenmeyen sayıda run adımı: {len(betikler)}"
    return betikler[0]


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
    """`fetch-depth: 0` olmadan taban commit'i yerelde OLMAZ.

    Diff artık ek bir fetch yapmıyor, tabanı doğrudan olaydan alıyor — o
    commit'in yerelde bulunmasının tek sebebi bu satır.
    """
    checkout = [a for a in ci["jobs"]["kapsam"]["steps"]
                if str(a.get("uses", "")).startswith("actions/checkout")]
    assert checkout, "kapsam işinde checkout adımı yok"
    assert checkout[0].get("with", {}).get("fetch-depth") == 0, checkout[0]


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


def test_kapsam_tabani_olaydan_okuyor(ci: dict, kapsam_kodu: str):
    """Taban, dal ADI değil olaydaki SHA olmalı.

    `origin/$TABAN` dalın O ANKİ tepesini gösteriyor ve merge ile ötelenebiliyor;
    `pull_request.base.sha` PR'ın gerçekten dallandığı commit'i gösteriyor ve
    yarışmıyor.
    """
    ortam = ci["jobs"]["kapsam"]["steps"][-1].get("env", {})
    assert ortam.get("TABAN_SHA") == "${{ github.event.pull_request.base.sha }}", ortam
    assert "$TABAN_SHA...HEAD" in kapsam_kodu, kapsam_kodu
    assert "origin/$TABAN..." not in kapsam_kodu, "taban hâlâ dal adından okunuyor"


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
