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
