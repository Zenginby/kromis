"""Ön yüz lint KAPISI: eslint + prettier CI'da kesici, paylaşılan ad defteri doğru.

NEDEN VAR (2026-09-17, Faz 0 / Adım 7). `static/` altındaki dokuz ilk-el betik
modül değil: `static/index.html` onları sırayla TEK küresel kapsama yüklüyor
(docs/graflar/onyuz.md). eslint tek dosyaya bakar; `core.js`in tanımladığı
`closeSheets`i `assets.js`in çağırması ona "tanımsız ad" görünür. Ölçüldü:
yalnız tarayıcı küreselleriyle 1035 `no-undef` (92 ayrı ad) — hepsi başka
betikte tanımlı, hiçbiri gerçek kusur. Kuralı `off`a çekmek kapıyı
kapatmaktı; onun yerine dosyalar arası adlar ELLE TUTULAN bir deftere yazıldı
(`eslint.paylasilan-adlar.json`) ve `eslint.config.js` her betiğe yalnız
ÖTEKİ betiklerin adlarını `globals` olarak veriyor.

Elle tutulan her kapsam listesinin bekçisi bir testtir (CLAUDE.md §5). Defter
üç yönde bayatlayabilir ve eslint bunların yalnız BİRİNİ görür:

  * EKSİK ad → eslint `no-undef` ile CI'da yakalar; burada iddia yok.
  * FAZLA/BAYAT ad (işlev silindi, ad değişti, artık başka dosya kullanmıyor)
    → eslint sessiz kalır: verilen küresel hiçbir yerde geçmese de hata
    değildir. Bu dosya her adın gerçekten o dosyada tanımlı VE başka bir
    dosyada kullanılıyor olmasını şart koşuyor.
  * Depo haritasıyla AYRIŞMA: `docs/graflar/graf.json`un betik-arası kenarları
    aynı ilişkiyi başka yoldan ölçüyor. İki liste birbirini denetliyor;
    haritanın bilinen fazla sayımları (yorumda geçen ad) GEREKÇESİYLE
    defterde.

`no-unused-vars` `vars: "local"` ile koşuyor (gerekçe eslint.config.js'te):
üst düzey bir işlevin "kullanılmadığı" tek dosyadan bilinemez. Bu kararın
bedeli — ölü üst düzey ad artık eslint'te görünmez — burada ödeniyor:
hiçbir betikte ve index.html'de geçmeyen üst düzey ad KIRMIZI.

ci.yml yüzü `tests/test_paketleme_dondurma.py`nin `lint` işi için yaptığının
eşi: iş var, iki komut da koşuyor, `continue-on-error` yok, Node sürümü pinli.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

import pytest
import yaml

from tools import graf_uret as gu

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFTER = os.path.join(REPO, "eslint.paylasilan-adlar.json")
ESLINT_CONFIG = os.path.join(REPO, "eslint.config.js")
PACKAGE_JSON = os.path.join(REPO, "package.json")
PACKAGE_LOCK = os.path.join(REPO, "package-lock.json")
PRETTIERRC = os.path.join(REPO, ".prettierrc")
PRETTIERIGNORE = os.path.join(REPO, ".prettierignore")
CI_YML = os.path.join(REPO, ".github", "workflows", "ci.yml")
GRAF_JSON = os.path.join(REPO, "docs", "graflar", "graf.json")

# Üçüncü parti (Ryan Mulligan, MIT): lint ve biçimlendirme kapsamı dışında,
# tests/test_telif_basligi.py ve tests/test_id_contract.py ile aynı duruş.
UCUNCU_PARTI = "static/pixel-canvas.js"

# tests/test_id_contract.py'nin deseniyle aynı aile; `class` eklendi.
UST_DUZEY_TANIM = re.compile(
    r"^(?:(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"
    r"|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*="
    r"|class\s+([A-Za-z_$][\w$]*))", re.M)


def _oku(yol: str) -> str:
    with open(os.path.join(REPO, yol), encoding="utf-8") as f:
        return f.read()


def _json(yol: str) -> dict:
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def _defter() -> dict:
    return _json(DEFTER)


def _betikler() -> list[str]:
    cikti = subprocess.run(["git", "-C", REPO, "ls-files", "static/*.js"],
                           check=True, capture_output=True, text=True).stdout
    return sorted(y for y in cikti.splitlines() if y and y != UCUNCU_PARTI)


def _ust_duzey_adlar(metin: str) -> list[str]:
    return [next(g for g in m.groups() if g) for m in UST_DUZEY_TANIM.finditer(metin)]


def _ad_deseni(ad: str) -> re.Pattern:
    """`ad` bir TANIMLAYICI olarak: `.ad` (özellik) ve `xad` (başka ad) sayılmaz."""
    return re.compile(r"(?<![\w$.])" + re.escape(ad) + r"(?![\w$])")


def _kod(metin: str) -> str:
    """Yorumlar atılmış metin — iddia kodu arar, yorumdaki adı değil."""
    return gu._yorumsuz(metin)


def _ciftler() -> list[tuple[str, str]]:
    return [(dosya, ad) for dosya, adlar in sorted(_defter()["paylasilan"].items())
            for ad in adlar]


# --------------------------------------------------------------------------
# Defter: her ad tanımlı, her ad başka dosyada kullanılıyor, tek dosyada
# --------------------------------------------------------------------------

@pytest.mark.parametrize("dosya, ad", _ciftler())
def test_every_shared_name_is_declared_at_top_level_in_the_file_that_claims_it(
        dosya: str, ad: str):
    """Silinen ya da adı değişen bir işlev defterde kalırsa eslint sessizdir."""
    assert ad in _ust_duzey_adlar(_oku(dosya)), (
        f"{ad} defterde {dosya} altında ama orada üst düzey tanımı yok — "
        "adı değişti ya da silindi; defterden çıkar")


@pytest.mark.parametrize("dosya, ad", _ciftler())
def test_every_shared_name_is_actually_used_by_another_script(dosya: str, ad: str):
    """Artık kimsenin çağırmadığı bir ad küresel olarak verilmeye devam eder;
    o da bir gün silinip başka dosyada aynı adla yanlış bir şeye bağlanabilir."""
    desen = _ad_deseni(ad)
    kullananlar = [b for b in _betikler() if b != dosya and desen.search(_kod(_oku(b)))]
    assert kullananlar, (
        f"{ad} ({dosya}) başka hiçbir betiğin kodunda geçmiyor — defterden çıkar; "
        "yalnız kendi dosyasında kullanılıyorsa küresel verilmesine gerek yok")


def test_no_shared_name_is_listed_under_two_files():
    """İki dosya aynı adı tanımlarsa hangisi kazanır yükleme sırasına bağlı —
    tests/test_id_contract.py aynı çakışmayı kaynakta, burası defterde yakalıyor."""
    sahipler: dict[str, list[str]] = {}
    for dosya, ad in _ciftler():
        sahipler.setdefault(ad, []).append(dosya)
    cakisan = {ad: d for ad, d in sahipler.items() if len(d) > 1}
    assert not cakisan, f"defterde aynı ad iki dosyada: {cakisan}"


def test_the_ledger_only_names_scripts_that_ship():
    for dosya in _defter()["paylasilan"]:
        assert dosya in _betikler(), f"defterde {dosya} var ama static/ altında izlenmiyor"


# --------------------------------------------------------------------------
# Yazılabilir adlar ve iyimser kancalar — ikisi de gerekçeli istisna
# --------------------------------------------------------------------------

def test_every_writable_name_is_shared_and_really_assigned_from_another_file():
    """`writable` yalnız başka dosyanın ATADIĞI adlara: salt okunur kalanlar
    `no-global-assign` ile korunuyor, yani liste gevşedikçe kapı daralır."""
    defter = _defter()
    paylasilan = {ad: dosya for dosya, ad in _ciftler()}
    for ad in defter["yazilabilir"]:
        assert ad in paylasilan, f"yazılabilir {ad} paylaşılan adlar arasında değil"
        atama = re.compile(r"(?<![\w$.])" + re.escape(ad) + r"\s*(?:=(?!=)|\+\+|--|\+=|-=)")
        atayanlar = [b for b in _betikler()
                     if b != paylasilan[ad] and atama.search(_kod(_oku(b)))]
        assert atayanlar, (
            f"{ad} yazılabilir ama hiçbir başka betik ona atamıyor — salt okunura çevir")


def test_every_optimistic_hook_is_probed_with_typeof_and_defined_nowhere():
    """`typeof x === "function"` ile yoklanan ad: tanımlanırsa artık kanca
    değil paylaşılan ad — defterin öteki listesine geçmeli."""
    defter = _defter()
    tumu = "\n".join(_oku(b) for b in _betikler())
    for ad, gerekce in defter["iyimser_kancalar"].items():
        assert gerekce.strip(), f"{ad} kancasının gerekçesi boş"
        assert re.search(r"typeof\s+" + re.escape(ad) + r"\s*===?\s*\"function\"", tumu), (
            f"{ad} hiçbir betikte typeof ile yoklanmıyor — kanca değil")
        tanimlayan = [b for b in _betikler() if ad in _ust_duzey_adlar(_oku(b))]
        assert not tanimlayan, (
            f"{ad} artık {tanimlayan} içinde tanımlı: iyimser_kancalar'dan çıkar, paylasilan'a yaz")


# --------------------------------------------------------------------------
# Depo haritasıyla tutarlılık
# --------------------------------------------------------------------------

def test_the_ledger_agrees_with_the_repo_graphs_cross_script_edges():
    """graf.json'un `onyuz.kenarlar`ı aynı ilişkiyi çağrı deseninden ölçüyor.

    Haritanın bilinen fazla sayımı: yorumda geçen `foo()` da kenar üretiyor
    (tools/graf_uret.py'nin sınırı, docs/graflar/README.md son bölüm). Böyle bir
    ad ya defterde ya `graf_fazla_sayimlari`nda GEREKÇESİYLE — üçüncü seçenek yok.
    Fazla sayım listesi de bayatlayamaz: her girdi hâlâ bir kenar olmalı ve
    KODDA (yorumsuz metinde) çağrılmamalı; çağrılıyorsa gerçek paylaşılan addır.
    """
    defter = _defter()
    kenarlar = _json(GRAF_JSON)["onyuz"]["kenarlar"]
    kenar_adlari = {(k["hedef"], ad) for k in kenarlar for ad in k["adlar"]}
    fazla = defter["graf_fazla_sayimlari"]

    aciklanmayan = sorted(
        f"{hedef}:{ad}" for hedef, ad in kenar_adlari
        if ad not in defter["paylasilan"].get(hedef, []) and ad not in fazla)
    assert not aciklanmayan, (
        "harita betik-arası kenar görüyor, defter görmüyor: " + ", ".join(aciklanmayan)
        + "\nGerçek çağrıysa paylasilan'a, yalnız yorumda geçiyorsa gerekçesiyle "
          "graf_fazla_sayimlari'na yaz")

    for ad, gerekce in fazla.items():
        assert gerekce.strip(), f"{ad} fazla sayımının gerekçesi boş"
        assert any(a == ad for _, a in kenar_adlari), (
            f"{ad} artık haritada kenar değil — graf_fazla_sayimlari'ndan çıkar")
        cagri = re.compile(r"(?<![\w$.])" + re.escape(ad) + r"\s*\(")
        kodda = [b for b in _betikler()
                 if ad not in _ust_duzey_adlar(_oku(b)) and cagri.search(_kod(_oku(b)))]
        assert not kodda, (
            f"{ad} {kodda} KODUNDA çağrılıyor — fazla sayım değil, paylaşılan ad")


# --------------------------------------------------------------------------
# `vars: "local"`ın bedeli: ölü üst düzey ad burada
# --------------------------------------------------------------------------

@pytest.mark.parametrize("dosya", _betikler())
def test_no_top_level_name_is_dead(dosya: str):
    """Kendi dosyasında (tanımı dışında), başka betikte ya da index.html'de
    geçmeyen üst düzey ad ölüdür — eslint `vars: "local"` yüzünden bunu görmez."""
    kaynak = _kod(_oku(dosya))
    digerleri = "\n".join(_kod(_oku(b)) for b in _betikler() if b != dosya)
    html = _oku("static/index.html")
    olu = []
    for ad in _ust_duzey_adlar(_oku(dosya)):
        desen = _ad_deseni(ad)
        kendi = len(desen.findall(kaynak)) - 1
        if kendi <= 0 and not desen.search(digerleri) and not desen.search(html):
            olu.append(ad)
    assert not olu, f"{dosya}: hiçbir yerde kullanılmayan üst düzey ad: {olu}"


# --------------------------------------------------------------------------
# Yapılandırma gevşemez, CI kesici, pinler tam
# --------------------------------------------------------------------------

def test_the_eslint_rules_are_not_weakened():
    """Kapının en sessiz kırılışı kuralın `off`/`warn`a çekilmesi — CI yeşil kalır."""
    metin = _oku("eslint.config.js")
    for kural in ('"no-undef": "error"', '"no-unused-vars": ["error"', 'eqeqeq: "error"'):
        assert kural in metin, f"eslint.config.js'te `{kural}` yok — kural gevşetilmiş mi?"
    assert '"off"' not in metin and '"warn"' not in metin, (
        "eslint.config.js bir kuralı kapatıyor ya da uyarıya çekiyor")
    assert 'sourceType: "script"' in metin, (
        "betikler ES modül sayılmış: dosyalar arası adlar ayrıştırıcı düzeyinde yanlış okunur")
    assert UCUNCU_PARTI in metin, f"{UCUNCU_PARTI} lint kapsamından çıkarılmamış (üçüncü parti)"


def test_prettier_formats_only_first_party_scripts():
    ayar = _json(PRETTIERRC)
    assert ayar.get("printWidth") == 100, (
        "printWidth 100 ölçülerek seçildi (80: 2823, 100: 2182, 120: 1978 satır fark); "
        "değiştiren ölçümü yenilesin")
    yoksay = _oku(".prettierignore")
    for satir in (UCUNCU_PARTI, "static/*.css", "static/*.html", "docs/"):
        assert satir in yoksay, f".prettierignore `{satir}` satırını kaybetmiş"


def test_package_json_pins_every_tool_exactly_and_ships_nothing():
    paket = _json(PACKAGE_JSON)
    assert paket.get("private") is True, "package.json private değil"
    assert "dependencies" not in paket, (
        "package.json çalışma zamanı bağımlılığı taşıyor — static/ paketlenmiyor")
    gelistirme = paket.get("devDependencies", {})
    for arac in ("eslint", "prettier"):
        assert arac in gelistirme, f"devDependencies'te {arac} yok"
    for ad, surum in gelistirme.items():
        assert re.fullmatch(r"\d+\.\d+\.\d+", surum), (
            f"{ad}: `{surum}` tam pin değil — `npm ci` ancak kilit dosyasıyla aynı şeyi kurar")
    kilit = _json(PACKAGE_LOCK)
    assert kilit["packages"][""].get("devDependencies") == gelistirme, (
        "package-lock.json kök kaydı package.json ile aynı değil — `npm install` koş ve kilidi commit'le")


def _lint_onyuz() -> dict:
    with open(CI_YML, encoding="utf-8") as f:
        isler = yaml.safe_load(f)["jobs"]
    assert "lint-onyuz" in isler, "ci.yml'de lint-onyuz işi yok"
    return isler["lint-onyuz"]


def test_ci_runs_eslint_and_prettier_check_as_a_blocking_job():
    is_ = _lint_onyuz()
    adimlar = is_.get("steps", [])
    komutlar = "\n".join(str(a.get("run") or "") for a in adimlar)
    assert "npm ci" in komutlar, "lint-onyuz `npm ci` koşturmuyor (kilit dosyasıyla kurulum)"
    assert "eslint static/" in komutlar, "lint-onyuz eslint koşturmuyor"
    assert "prettier --check static/" in komutlar, "lint-onyuz prettier --check koşturmuyor"
    kesmeyenler = [a.get("name") for a in adimlar if a.get("continue-on-error")]
    assert not kesmeyenler, f"lint-onyuz adımları PR'ı kesmiyor: {kesmeyenler}"
    assert not is_.get("continue-on-error"), "lint-onyuz işi PR'ı kesmiyor"


def test_ci_pins_the_node_major():
    """Pinsiz `setup-node` bir gün başka bir Node kurar ve eslint'in `engines`
    kapısı kırmızı verir — pin diff'te GÖRÜNÜR bir karar olsun."""
    kurulum = [a for a in _lint_onyuz().get("steps", [])
               if str(a.get("uses") or "").startswith("actions/setup-node@")]
    assert len(kurulum) == 1, "lint-onyuz'da tam bir setup-node adımı bekleniyor"
    surum = str((kurulum[0].get("with") or {}).get("node-version", ""))
    assert re.fullmatch(r"\d+(\.\d+)*", surum), f"node-version pinli değil: {surum!r}"
