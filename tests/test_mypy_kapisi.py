"""mypy KAPI: `[tool.mypy]` bayrakları gevşemez, CI'daki adım PR'ı keser.

NEDEN VAR (2026-09-16, Faz 0 / Adım 6). Adım 1'de mypy CI'a "bilgi amaçlı"
girdi (`continue-on-error: true`, 77 bulgu); bu adımda taban sıfırlandı ve
satır kalktı. Bir kapının en sessiz kırılma biçimi kapatılması değil
GEVŞETİLMESİDİR: `warn_unused_ignores` silinir, `platform` kalkar, winsec
muafiyeti `ignore_errors = true`ya genişler — `mypy .` yine "Success" der ve
hiç kimse fark etmez. Deponun "türetilen her şeyin bekçisi bir testtir"
kuralı (CLAUDE.md §5) burada yapılandırmaya uygulanıyor: sıfır bulguyu CI'ın
kendisi ölçüyor, bu dosya sıfırın NEYE GÖRE sıfır olduğunu mandallıyor.

`test_paketleme_dondurma.py` aynı kapının ci.yml yüzünü sınıyor (mypy adımı
var ve `continue-on-error` yok); burası pyproject yüzü. İkisi ayrı dosyada,
çünkü gerekçeleri ayrı: orası "dondurma CI'ı kapatmak değil" der, burası
"kapı gevşemez" der.

Sıkılaştırma kademeleri (`check_untyped_defs`, sonra modül modül `strict`)
geldiğinde `ZORUNLU_BAYRAKLAR`a EKLENİR, buradan hiçbir şey çıkmaz.
"""
from __future__ import annotations

import os
import tomllib

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYPROJECT = os.path.join(REPO, "pyproject.toml")

# Bayrak → beklenen değer. Her satırın gerekçesi pyproject.toml'un kendisinde;
# burada yalnız değerler mandallı.
ZORUNLU_BAYRAKLAR = {
    "python_version": "3.13",
    "platform": "linux",
    "warn_unused_ignores": True,
    "warn_redundant_casts": True,
    "strict_equality": True,
    "extra_checks": True,
    "no_implicit_reexport": True,
}

# Modül kapsamlı muafiyet yalnız bu modüle ve yalnız bu koda tanınıyor.
# `ignore_errors = true` gibi toptan bir susturma hiçbir modüle YOK.
IZINLI_MUAFIYETLER = {"winsec": {"name-defined"}}


def _mypy() -> dict:
    with open(PYPROJECT, encoding="utf-8") as f:
        return tomllib.loads(f.read())["tool"]["mypy"]


@pytest.mark.parametrize("bayrak, deger", sorted(ZORUNLU_BAYRAKLAR.items()))
def test_the_mypy_gate_keeps_every_tightened_flag(bayrak: str, deger: object):
    """Bayrak silinirse ya da gevşetilirse `mypy .` yeşil kalır — burada yakalanır."""
    ayar = _mypy()
    assert bayrak in ayar, f"[tool.mypy] `{bayrak}` bayrağı silinmiş"
    assert ayar[bayrak] == deger, f"[tool.mypy] `{bayrak}` = {ayar[bayrak]!r}, beklenen {deger!r}"


def test_no_module_is_silenced_wholesale():
    """Muafiyet ancak KOD BAZINDA ve GEREKÇELİ modüle: `ignore_errors` yasak.

    `exclude` listesi ithal edilen bir modülü SUSTURMAZ (mypy ithali izler ve
    hatayı yine yazar), yani dondurulmuş kabuk modüllerini oraya atmak kapıyı
    kapatmazdı — ve `ignore_errors = true` kapatır ama görünmez. İkisi de yok.
    """
    ayar = _mypy()
    for kural in ayar.get("overrides", []):
        assert not kural.get("ignore_errors"), (
            f"[[tool.mypy.overrides]] {kural.get('module')}: `ignore_errors` toptan susturma")
        moduller = kural.get("module")
        moduller = [moduller] if isinstance(moduller, str) else list(moduller or [])
        for modul in moduller:
            assert modul in IZINLI_MUAFIYETLER, (
                f"[[tool.mypy.overrides]] {modul}: gerekçesiz modül muafiyeti — "
                "önce kodu düzelt, olmuyorsa IZINLI_MUAFIYETLER'e gerekçesiyle ekle")
            fazla = set(kural.get("disable_error_code", [])) - IZINLI_MUAFIYETLER[modul]
            assert not fazla, f"{modul}: izin verilmeyen kod kapatılmış: {sorted(fazla)}"


def test_the_gate_does_not_hide_third_party_types_it_could_see():
    """`ignore_missing_imports` yalnız STUB'sız paketleri susturur; `follow_imports`
    `skip`e çekilirse ya da `disable_error_code` üst düzeyde açılırsa `mypy .`
    yine yeşil kalır ama hiçbir şey ölçmez."""
    ayar = _mypy()
    assert ayar.get("follow_imports", "normal") == "normal", "follow_imports gevşetilmiş"
    assert not ayar.get("disable_error_code"), (
        "[tool.mypy] üst düzeyde `disable_error_code` var — kod bazlı kapatma yalnız modül override'ında")
    assert not ayar.get("ignore_errors"), "[tool.mypy] `ignore_errors` toptan susturma"
