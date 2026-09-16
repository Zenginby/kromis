"""Paketleme DONDURULDU: hiçbir push/PR masaüstü ya da Android paketi derletmez.

NEDEN VAR (2026-09-16, Faz 0 / Adım 1 — web-first zemin). Masaüstü (macOS,
Windows) ve Android paketleri v0.23.1'de donduruldu; proje web-first ilerliyor
(docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md,
docs/faz0-web-first.md). Ölçülen bedel ikiliydi:

  • CI'daki `kapsam` kapısı `requirements*.txt` ya da `.github/workflows/`
    dokunan her PR'da üç paketi derletiyordu — ~40 dakika, macOS'ta 10x
    faturalanan dakika. Web tarafında bağımlılık taşıyan her PR bu sınıfa
    girer, yani kapı tam da yoğunlaşacağı dönemde dondurulmuş bir paket için
    ateşlenirdi.
  • `release.yml` main'e her merge'de üç paketi zorunlu kılıyordu; paketleme
    kırık olduğunda (Chaquopy wheel'i, pythonnet pini…) web değişikliği de
    yayınsız kalıyordu.

Paketleme SİLİNMEDİ, ELLE'ye alındı. Çağrılabilir `_paket-*.yml` dosyaları
ve `release.yml`in iç yapısı (karar → sürüm → taslak → üç paket → tek yazıcı)
olduğu gibi duruyor; `tests/test_release_manifest.py` onları aynı sertlikte
mandallamaya devam ediyor. Değişen tek şey TETİK: `release.yml` yalnız
`workflow_dispatch`, `ci.yml`de paket işi yok.

BU DOSYA O TETİĞİN BEKÇİSİ. Deponun "elle tutulan her kapsam listesinin bekçisi
bir testtir" kuralı (CLAUDE.md §5) burada tersine işliyor: kapsam listesi
değil, kapsamın YOKLUĞU mandallanıyor. Bir gün biri `push:`ı geri koyarsa ya
da `ci.yml`e bir `uses: ./.github/workflows/_paket-…` eklerse takım kırmızı
olur ve bu başlık ona neden burada olduğunu söyler.

YAML GERÇEKTEN AYRIŞTIRILIYOR (test_release_manifest.py'nin gerekçesi): `on:`
anahtarını PyYAML `True` diye okuyor (YAML 1.1 boolean), iddialar iki hâli de
karşılıyor — metin araması bu tuzağı göremezdi.
"""
from __future__ import annotations

import os

import pytest
import yaml

import release_manifest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_AKISLARI = os.path.join(REPO, ".github", "workflows")
CI_YML = os.path.join(IS_AKISLARI, "ci.yml")
YAYIN_YML = os.path.join(IS_AKISLARI, "release.yml")

# Bir push ya da PR'ın KENDİLİĞİNDEN başlattığı tetikler. `workflow_dispatch`
# (insan) ve `workflow_call` (başka bir workflow) bilerek dışarıda.
OTOMATIK_TETIKLER = frozenset({"push", "pull_request", "pull_request_target",
                               "schedule", "merge_group", "release"})

# Paket ÜRETEN workflow'lar: manifestteki üçü + Android wheel'i (APK'nın
# ön koşulu, `_paket-android.yml` onu iş olarak çağırıyor).
PAKET_WORKFLOWLARI = frozenset(
    k["workflow"] for k in release_manifest.PAKETLER.values()
) | {"build-pydantic-core-android.yml"}

# Dondurmanın kullanıcıya SÖYLENDİĞİ yer: iki README de bu belgeye bağlanmalı.
TASARIM_BELGESI = "docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md"


def _yaml(yol: str) -> dict:
    with open(yol, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _tetikler(veri: dict) -> set[str]:
    """`on:` bloğunun anahtarları — PyYAML `on`u `True` okuyor, ikisi de kabul."""
    on = veri.get("on", veri.get(True))
    assert on is not None, "workflow'da `on:` yok"
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return set(on)
    return set(on)


def _paket_cagiran_isler(veri: dict) -> list[str]:
    return [
        is_adi for is_adi, is_ in (veri.get("jobs") or {}).items()
        if os.path.basename(str(is_.get("uses") or "")) in PAKET_WORKFLOWLARI
    ]


def _workflow_dosyalari() -> list[str]:
    return sorted(ad for ad in os.listdir(IS_AKISLARI) if ad.endswith((".yml", ".yaml")))


# --------------------------------------------------------------------------
# Asıl değişmez: otomatik tetik → paket yok
# --------------------------------------------------------------------------

@pytest.mark.parametrize("dosya", _workflow_dosyalari())
def test_no_automatically_triggered_workflow_calls_a_package_build(dosya: str):
    """push/PR/zamanlayıcı ile başlayan hiçbir workflow bir paket işi çağırmaz.

    Doğrudan çağrıya bakılıyor; dolaylı yol yalnız `_paket-android.yml` →
    wheel ve o dosyanın kendisi `workflow_call`. Dolaylı bir yol açılırsa
    (ör. `ci.yml` → yeni bir ara workflow → `_paket-macos.yml`) ara workflow
    da bu listede olur ve onun tetiği `workflow_call` olduğu için iddia
    oradan geçer — o yüzden aşağıdaki `test_ci_has_no_package_job` ve
    `test_the_release_pipeline_only_runs_when_a_human_dispatches_it` ayrıca var:
    üç kapı, biri kaçarsa öteki yakalar.
    """
    veri = _yaml(os.path.join(IS_AKISLARI, dosya))
    if not (_tetikler(veri) & OTOMATIK_TETIKLER):
        return
    cagiranlar = _paket_cagiran_isler(veri)
    assert not cagiranlar, (
        f"{dosya} otomatik tetikleniyor ({sorted(_tetikler(veri) & OTOMATIK_TETIKLER)}) "
        f"ve paket derletiyor: {cagiranlar}. Paketleme 2026-09-16'da elle'ye alındı — "
        "bu dosyanın başlığını oku.")


def test_the_release_pipeline_only_runs_when_a_human_dispatches_it():
    """`release.yml`in tek tetiği `workflow_dispatch` — main'e merge yayın değil."""
    assert _tetikler(_yaml(YAYIN_YML)) == {"workflow_dispatch"}, (
        "release.yml'e otomatik bir tetik geri gelmiş: main'e her merge üç paketi "
        "derletir ve sürüm artırır")


def test_ci_has_no_package_job():
    """`ci.yml`de ne `kapsam` kapısı ne paket işi kalmalı."""
    isler = _yaml(CI_YML)["jobs"]
    assert "kapsam" not in isler, "paketleme kapsam kapısı ci.yml'e geri gelmiş"
    assert not _paket_cagiran_isler(_yaml(CI_YML)), (
        f"ci.yml paket derletiyor: {_paket_cagiran_isler(_yaml(CI_YML))}")


# --------------------------------------------------------------------------
# Dondurma, "CI'ı kapatmak" DEĞİL: testler, sızıntı taraması ve lint her PR'da
# --------------------------------------------------------------------------

def test_ci_still_runs_on_every_pull_request_and_on_main():
    assert {"pull_request", "push"} <= _tetikler(_yaml(CI_YML)), (
        "ci.yml artık her PR'da ve main'e push'ta koşmuyor")


def test_ci_still_runs_the_test_suite_the_leak_scan_and_lint():
    """Paket işleri gitti, geri kalan üç kapı DURUYOR — iddia adlarıyla sayıyor."""
    isler = _yaml(CI_YML)["jobs"]
    assert str(isler["test"].get("uses", "")).endswith("_test.yml"), (
        "ci.yml test takımını `_test.yml` üzerinden koşturmuyor")
    assert "sizinti" in isler, "sızıntı taraması ci.yml'den düşmüş"
    adimlar = isler["lint"].get("steps", [])
    komutlar = "\n".join(str(a.get("run") or "") for a in adimlar)
    assert "ruff check" in komutlar, "lint işi ruff koşturmuyor"
    assert "mypy" in komutlar, "lint işi mypy koşturmuyor"
    # Adım 6'dan (2026-09-16) beri mypy da KESİCİ: `continue-on-error: true`
    # geri gelirse kapı sessizce bilgiye döner ve yeşil kalır — burada yakalanır.
    kesmeyenler = [a.get("name") for a in adimlar
                   if ("mypy" in str(a.get("run") or "")) and a.get("continue-on-error")]
    assert not kesmeyenler, f"lint işinde mypy adımı PR'ı kesmiyor: {kesmeyenler}"


# --------------------------------------------------------------------------
# Paketleme ELLE hâlâ mümkün: dondurma silme değil
# --------------------------------------------------------------------------

@pytest.mark.parametrize("ad", sorted(release_manifest.PAKETLER))
def test_a_frozen_package_can_still_be_built_by_hand(ad: str):
    """Manifestteki her paketin workflow'u yerinde ve `release.yml` onu çağırıyor.

    `test_release_manifest.py` aynı şeyi daha ayrıntılı sınıyor; buradaki
    iddia dondurmanın SINIRINI yazıyor: tetik gitti, üretim yolu gitmedi.
    """
    kayit = release_manifest.PAKETLER[ad]
    yol = os.path.join(IS_AKISLARI, kayit["workflow"])
    assert os.path.exists(yol), f"{kayit['workflow']} silinmiş — dondurma silme değildi"
    assert "workflow_call" in _tetikler(_yaml(yol)), (
        f"{kayit['workflow']} artık çağrılabilir değil")
    assert kayit["is"] in _yaml(YAYIN_YML)["jobs"], (
        f"release.yml'de {kayit['is']} işi yok — elle yayın o paketi üretemez")


# --------------------------------------------------------------------------
# Kullanıcıya söylendi mi
# --------------------------------------------------------------------------

@pytest.mark.parametrize("readme, anahtar", [
    ("README.md", "dondur"),
    ("README.en.md", "frozen"),
])
def test_the_readme_tells_users_the_desktop_and_android_builds_are_frozen(
        readme: str, anahtar: str):
    """İndirme tablosunun yanında dondurma yazmalı ve tasarım belgesine bağlanmalı.

    Tablo `releases/latest/download/…` bağlantılarını koruyor (bunu
    `test_release_manifest.py` mandallıyor) — yani bağlantı çalışır ama
    kullanıcı "neden yeni sürüm yok" sorusunun cevabını README'de bulmalı.
    """
    with open(os.path.join(REPO, readme), encoding="utf-8") as f:
        metin = f.read()
    assert "v0.23.1" in metin, f"{readme} dondurulan sürümü söylemiyor"
    assert anahtar in metin.lower(), f"{readme} paketlerin dondurulduğunu söylemiyor"
    assert TASARIM_BELGESI in metin, f"{readme} tasarım belgesine bağlanmıyor"
    assert "docs/faz0-web-first.md" in metin, f"{readme} Faz 0 görev listesine bağlanmıyor"


def test_the_release_doc_records_that_packaging_became_manual():
    """docs/yayin-hatti.md ilk cümlesinde hâlâ "hiçbir şey yapmıyorsun" diyorsa yanlış."""
    with open(os.path.join(REPO, "docs", "yayin-hatti.md"), encoding="utf-8") as f:
        metin = f.read()
    assert "2026-09-16" in metin and "workflow_dispatch" in metin, (
        "docs/yayin-hatti.md paketlemenin elle'ye alındığını tarihiyle kaydetmiyor")
