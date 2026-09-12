"""`main` dal koruması: depodaki kural kümesi ↔ yayın hattının ihtiyacı.

NEDEN VAR: dal koruması GitHub AYARIDIR, depoda durmaz. "Türetilen her şeyin
bekçisi bir testtir" kuralının kör noktası tam olarak burası — ayar sessizce
değişir, kimse görmez. `.github/rulesets/main.json` o ayarın depodaki okunur
kopyası (GitHub kural kümelerini JSON olarak dışa/içe aktarıyor); bu dosya da
o kopyanın YAYIN HATTIYLA çelişmediğini her PR'da ölçüyor.

ASIL İDDİA — KURAL KÜMESİ BOTUN PUSH'UNU REDDETMEMELİ. `release.yml`'deki
`surum-yaz` işi sürüm commit'ini `GITHUB_TOKEN` ile DOĞRUDAN main'e itiyor
(`git push origin HEAD:main`). O token `github-actions[bot]`; yazma yetkisi var
ama admin değil. `pull_request` ya da `required_status_checks` gibi bir kural
eklenirse — ikisi de doğrudan push'u kapsıyor — bot reddedilir ve HER merge'de
yayın `surum-yaz` adımında kırmızıya düşer. Hattın kendi hata mesajı bunu zaten
öngörüyor ("main korumaya alınmış olabilir"), ama bir hata mesajı kapı değildir:
kusur ancak bir yayın harcandıktan SONRA görünürdü.

Yani buradaki kara liste bir yasak değil, bir SIRA: o kuralları açmadan önce
botun push'una bir yol açılmalı (admin PAT ya da bir GitHub App token'ı,
bkz. docs/dal-korumasi.md → "Aşama 2"). Yol açıldığında bu testin gerekçesi de
düşer, kara liste de.

GEREKÇE ÖLÇÜLÜYOR, VARSAYILMIYOR: aşağıdaki son iddia hattın main'e gerçekten
yazdığını `release.yml`'den okuyor. Hat bir gün main'e yazmayı bırakırsa kara
listenin sebebi kalmaz ve bunu bu test söyler.

GÖRMEDİĞİ ŞEY: GitHub'daki CANLI ayar. Bu dosya JSON'un ne dediğini ölçüyor,
kural kümesinin içe aktarılmış olduğunu değil — ikisinin ayrışması elle
denetlenir (docs/dal-korumasi.md → "Ayrışma riski").
"""
from __future__ import annotations

import json
import os

import pytest
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KURAL_KUMESI = os.path.join(REPO, ".github", "rulesets", "main.json")
YAYIN_YML = os.path.join(REPO, ".github", "workflows", "release.yml")

# Doğrudan push'u kapsayan, yani botun sürüm commit'ini reddedecek kural türleri.
# GitHub'ın kural adlarıyla birebir; başka bir adla yazılan bir kural burada
# yakalanmaz, o yüzden liste açıldıkça büyümeli.
BOTU_KESENLER = {
    "pull_request",
    "required_status_checks",
    "required_signatures",
    "required_linear_history",
}


@pytest.fixture(scope="module")
def kume() -> dict:
    with open(KURAL_KUMESI, encoding="utf-8") as f:
        return json.load(f)


def _kural_turleri(kume: dict) -> set[str]:
    return {k.get("type") for k in (kume.get("rules") or [])}


def test_ruleset_targets_the_default_branch_by_alias_not_by_name(kume: dict):
    """Dal ADIYLA hedeflenseydi yeniden adlandırma korumayı sessizce düşürürdü."""
    assert kume["target"] == "branch"
    ref = kume["conditions"]["ref_name"]
    assert ref["include"] == ["~DEFAULT_BRANCH"]
    assert ref["exclude"] == []


def test_ruleset_is_enforced_not_merely_evaluated(kume: dict):
    """`evaluate`/`disabled` bir kural kümesi hiçbir şeyi engellemez, yalnız rapor eder."""
    assert kume["enforcement"] == "active"


def test_deletion_and_force_push_are_blocked(kume: dict):
    """Aşama 1'in tamamı bu iki kural: telafisi olmayan iki kaza sınıfı.

    2026-09-10'da main BİLEREK yeniden yazıldı (kimlik temizliği); aynı şeyin
    kazayla olması geri dönüşsüz. Silme de öyle.
    """
    assert {"deletion", "non_fast_forward"} <= _kural_turleri(kume)


def test_no_rule_rejects_the_release_bots_direct_push(kume: dict):
    """Aşama 2 kuralları, botun push'una bir yol açılmadan eklenemez."""
    kesenler = _kural_turleri(kume) & BOTU_KESENLER
    assert not kesenler, (
        f"kural kümesinde botun push'unu kesen kural(lar) var: {sorted(kesenler)}. "
        "release.yml → surum-yaz sürüm commit'ini GITHUB_TOKEN ile doğrudan "
        "main'e itiyor; bu kurallar açılmadan önce ona bir yol açılmalı "
        "(docs/dal-korumasi.md → Aşama 2)."
    )


def test_bypass_list_is_explicit_in_the_file(kume: dict):
    """Muafiyet listesi dosyada YAZILI olmalı — içe aktarım sessizce muafiyet dağıtmasın."""
    assert isinstance(kume["bypass_actors"], list)


def test_the_release_pipeline_really_pushes_to_main(kume: dict):
    """Kara listenin GEREKÇESİ: hat main'e yazıyor mu? Ölçülüyor, varsayılmıyor.

    Hat bir gün main'e yazmayı bırakırsa (sürüm commit'i kalkarsa) bu iddia
    düşer ve `BOTU_KESENLER` listesinin var olma sebebi de kalmaz.
    """
    with open(YAYIN_YML, encoding="utf-8") as f:
        yayin = yaml.safe_load(f)

    # Kabuk YORUMLARI ayıklanıyor: bu deponun yorumları kaldırılan komutu
    # tırnak içinde anlatıyor (emsal: tests/test_release_manifest.py).
    komutlar = []
    for is_ in (yayin.get("jobs") or {}).values():
        for adim in (is_.get("steps") or []):
            if not isinstance(adim, dict):
                continue
            komutlar += [
                s for s in str(adim.get("run") or "").splitlines()
                if not s.lstrip().startswith("#")
            ]

    assert any("git push origin HEAD:main" in s for s in komutlar), (
        "release.yml artık main'e doğrudan yazmıyor görünüyor. Öyleyse "
        "BOTU_KESENLER kara listesinin gerekçesi düşmüştür: docs/dal-korumasi.md "
        "→ Aşama 2 artık bedelsiz açılabilir."
    )
