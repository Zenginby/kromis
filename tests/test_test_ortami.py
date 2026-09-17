"""Yerel test ortamı CI'ınkinden AYRIŞAMAZ — kalıcı kapı.

NEDEN VAR: `tools/test_ortami.py` "yerelde koştuğun şey CI'ın koştuğu şeydir"
diye bir SÖZ veriyor. O söz, aracın `_test.yml`i doğru okumasına dayanıyor —
ve araç onu salt kitaplık REGEX ile okuyor (gerekçesi orada: dosya, hiçbir
şeyin kurulu olmadığı bir yorumlayıcıda, SessionStart kancasında koşmak
zorunda). Regex'in kör noktası sessizdir: yanlış okuduğunda araç hata vermez,
YANLIŞ BİR ORTAM kurar ve "hazır" der. Bu deponun en pahalı kusur sınıfı tam
olarak budur — yanlış harita, hiç harita olmamasından kötüdür.

Bu yüzden kapı aynı dosyayı GERÇEK bir YAML ayrıştırıcısıyla (PyYAML, zaten
`requirements-dev.txt`te ve `test_release_manifest.py` de aynı sebeple
kullanıyor) ikinci kez okuyup karşılaştırıyor. İki bağımsız yol aynı cevabı
vermiyorsa takım kırmızı.

Kapının ölçtüğü ikinci şey daha basit ama daha kolay unutulan: CI'ın pytest
adımı `KROMIS_E2E_ZORUNLU` veriyor mu. O değişken, playwright kurulum adımı
bir gün sessizce kaybolursa takımın "yeşil ama eksik" kalmasını engelliyor;
yani kapının kendisinin bekçisi.
"""
from __future__ import annotations

import json
import os
import re

import yaml

from tests import conftest
from tools import test_ortami as ortam

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_WORKFLOW = os.path.join(REPO, ".github", "workflows", "_test.yml")


def _ci() -> dict:
    with open(TEST_WORKFLOW, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _adimlar() -> list[dict]:
    return [adim for is_ in _ci()["jobs"].values() for adim in is_.get("steps", [])]


def _kosanlar() -> str:
    return "\n".join(a.get("run", "") for a in _adimlar())


def test_the_python_version_is_read_from_the_ci_workflow():
    """Araç CI'ın Python pinini okuyor — kendi kopyasını taşımıyor."""
    beklenen = [a["with"]["python-version"] for a in _adimlar()
                if str(a.get("uses", "")).startswith("actions/setup-python")]
    assert beklenen, "_test.yml'de setup-python adımı yok"
    assert ortam.ci_sozlesmesi()["python"] == str(beklenen[0])


def test_the_requirement_files_are_read_from_the_ci_workflow():
    """`-r` ile kurulan dosyalar ve SIRALARI CI'la aynı."""
    yaml_dan = []
    for ad in re.findall(r"-r\s+(\S+)", _kosanlar()):
        if ad not in yaml_dan:
            yaml_dan.append(ad)
    assert yaml_dan, "_test.yml hiçbir gereksinim dosyası kurmuyor"
    assert ortam.ci_sozlesmesi()["gereksinimler"] == yaml_dan


def test_the_playwright_pin_is_read_from_the_ci_workflow():
    """Playwright sürümü CI'da neyse yerelde de O.

    Bu satırın kayması, bu aracın kapatmaya çalıştığı kusurun ta kendisini
    geri getirirdi: yerelde başka bir playwright, CI'da başka bir playwright.
    """
    m = re.search(r"pip install\s+(playwright\S*)", _kosanlar())
    assert m, "_test.yml playwright kurmuyor"
    assert ortam.ci_sozlesmesi()["playwright"] == m.group(1)


def test_the_browser_is_read_from_the_ci_workflow():
    """Hangi tarayıcı ve `--with-deps` verilip verilmediği de türetiliyor."""
    m = re.search(r"playwright install([^\n]*)", _kosanlar())
    assert m, "_test.yml tarayıcı kurmuyor"
    parcalar = m.group(1).split()
    sozlesme = ortam.ci_sozlesmesi()
    assert sozlesme["tarayicilar"] == [p for p in parcalar if not p.startswith("-")]
    assert sozlesme["with_deps"] == ("--with-deps" in parcalar)


def test_yaml_comments_do_not_leak_into_the_contract():
    """Gerekçe blokları KURULAN şey sayılmamalı.

    `_test.yml`in yorumları `requirements-dev.txt`i ve `playwright`ı bolca
    anıyor — hepsi de "oraya KONMUYOR, çünkü…" derken. Yorumları saymak,
    aracı CI'ın bilerek YAPMADIĞI şeyi yapmaya iterdi: playwright'ı
    `requirements-dev.txt`e kurmaya (bkz. test_playwright_kurulumu.py).
    """
    with open(TEST_WORKFLOW, encoding="utf-8") as f:
        metin = f.read()
    assert "requirements-dev.txt" in metin, "gerekçe bloğu taşınmış — test anlamsız"
    # Yorumlarda geçen her şey `run:` satırlarında da geçmiyor; sözleşmedeki
    # her gereksinim dosyası GERÇEKTEN `-r` ile kuruluyor olmalı.
    kosanlar = _kosanlar()
    for ad in ortam.ci_sozlesmesi()["gereksinimler"]:
        assert re.search(rf"-r\s+{re.escape(ad)}\b", kosanlar), (
            f"{ad} sözleşmede var ama CI onu `-r` ile kurmuyor")


def test_the_minimum_python_is_read_from_conftest():
    """Asgari sürümün TEK tanımı `tests/conftest.py`de; araç onu okuyor."""
    assert ortam.asgari_python() == conftest.ASGARI_PYTHON


# Satır başında duran bir `pytest.importorskip("playwright")` — yani modül
# düzeyindeki çağrı. Araç aynı soruyu AST ile soruyor; ölçüm BAĞIMSIZ olsun
# diye burada bilerek başka bir yoldan soruluyor (test_graflar.py'deki
# "sayılar depodan bağımsız biçimde yeniden ölçülüyor" disiplini).
_ATLAMA = re.compile(r"^pytest\.importorskip\(\s*[\"']playwright[\"']", re.M)


def test_the_e2e_files_are_measured_not_listed():
    """E2E dosyaları ölçülerek bulunuyor — elle yazılmış bir liste yok.

    NEDEN İKİ YÖNTEM: aracın ilk hâli düz metin araması yapıyordu ve
    `importorskip`i yalnız GEREKÇESİNDE anan iki dosyayı (bu dosya ile
    `test_playwright_kurulumu.py`) E2E sanıyordu — yani uyarı, atlanmayan
    dosyaları bildiriyordu. Aynı yöntemle yazılmış bir bekçi o kusuru
    göremezdi; bu yüzden burada satır-başı deseni kullanılıyor.
    """
    bulunan = ortam.e2e_dosyalari()
    assert bulunan, "hiç E2E dosyası bulunamadı — tarayıcı kör mü?"

    testler = os.path.join(REPO, "tests")
    beklenen = []
    for ad in sorted(os.listdir(testler)):
        if not (ad.startswith("test_") and ad.endswith(".py")):
            continue
        with open(os.path.join(testler, ad), encoding="utf-8") as f:
            if _ATLAMA.search(f.read()):
                beklenen.append(ad)
    assert bulunan == beklenen

    # Bu dosyanın KENDİSİ listede olmamalı: yukarıdaki `_ATLAMA` deseni de,
    # aracın anlattığı gerekçe de `importorskip("playwright"` dizesini taşıyor.
    assert os.path.basename(__file__) not in bulunan


def test_ci_gives_the_suite_a_postgres_service_and_tells_it_where(monkeypatch):
    """`_test.yml`: Postgres servis konteyneri + `KROMIS_TEST_DATABASE_URL` (Faz 1 / 1).

    K4: testte GERÇEK Postgres. Servis bir gün sessizce kalkarsa DB testleri
    atlanırdı; `KROMIS_E2E_ZORUNLU=1` onu da hataya çeviriyor (conftest) —
    bu test ise metnin kendisini mandallıyor. Değişken adı aracın okuduğuyla
    AYNI (`gecici_postgres.TEST_URL_ENV`), ikinci bir literal değil; araç o
    değişkeni görünce kaynağı `"env"` diye raporluyor.
    """
    from tools import gecici_postgres
    isler = _ci()["jobs"]
    servisler = [is_.get("services", {}).get("postgres") for is_ in isler.values()]
    servis = next((s for s in servisler if s), None)
    assert servis, "_test.yml'de postgres servisi yok"
    assert str(servis.get("image", "")).startswith("postgres:17"), servis.get("image")
    assert "pg_isready" in str(servis.get("options", "")), "servis sağlık denetimi yok"
    pytest_adimlari = [a for a in _adimlar() if "pytest" in a.get("run", "")]
    urller = [str(a.get("env", {}).get(gecici_postgres.TEST_URL_ENV, "")) for a in pytest_adimlari]
    assert any(u.startswith("postgresql+psycopg://") and "localhost:5432" in u for u in urller), urller
    monkeypatch.setenv(gecici_postgres.TEST_URL_ENV, urller[0])
    assert gecici_postgres.kaynak() == "env"


def test_the_readiness_check_requires_postgres_and_names_the_source():
    """`hazir()` Postgres'siz ortamı hazır SAYMAZ; rapor kurulum komutunu yazar."""
    from tools import gecici_postgres
    d = {"yorumlayici": ortam.venv_python(), "sozlesme": ortam.ci_sozlesmesi(),
         "asgari": ortam.asgari_python(), "surum": "3.13.0", "yeterli_python": True,
         "pytest": True, "playwright": True, "tarayici": True, "tarayici_hatasi": "",
         "postgres": None, "postgres_acildi": None, "postgres_hatasi": ""}
    assert not ortam.hazir(d)
    assert gecici_postgres.kurulum_yonergesi() in ortam.rapor(d)
    d["postgres"] = "env"
    assert ortam.hazir(d)
    assert gecici_postgres.TEST_URL_ENV in ortam.rapor(d)
    d["postgres"], d["postgres_acildi"], d["postgres_hatasi"] = "/usr/lib/postgresql/16/bin", False, "initdb basarisiz"
    assert not ortam.hazir(d)
    assert "initdb basarisiz" in ortam.rapor(d)


def test_ci_forbids_skipping_the_e2e_tests():
    """CI'ın pytest adımı `KROMIS_E2E_ZORUNLU` veriyor mu?

    Vermezse playwright kurulum adımının sessizce kaybolması takımı yeşil
    bırakır — E2E dosyaları atlanır ve kimse fark etmez. `_test.yml`in METNİNİ
    `test_playwright_kurulumu.py` sınıyor; bu test de o metnin GERÇEKTEN
    zorlanıp zorlanmadığını.
    """
    pytest_adimlari = [a for a in _adimlar() if "pytest" in a.get("run", "")]
    assert pytest_adimlari, "_test.yml pytest koşturmuyor"
    assert any(str(a.get("env", {}).get(conftest.E2E_ZORUNLU, "")) == "1"
               for a in pytest_adimlari), (
        f"pytest adımı {conftest.E2E_ZORUNLU}=1 vermiyor: "
        "E2E atlanırsa CI yine yeşil kalır")


def test_claude_md_points_at_the_setup_tool():
    """Deponun ilk okunan dosyası aracı GÖSTERMELİ.

    Mekanizma ancak bulunabilirse mekanizmadır: her oturum CLAUDE.md ile
    başlıyor ve "tam takımı koş" cümlesi, takımın bu makinede eksik
    koştuğunu söylemeden anlamsız.
    """
    with open(os.path.join(REPO, "CLAUDE.md"), encoding="utf-8") as f:
        metin = f.read()
    assert "tools/test_ortami.py" in metin


def test_the_session_hook_reports_the_test_environment():
    """SessionStart kancası ortamı da denetliyor mu? (üçüncü mekanizma)

    `.claude/settings.json` oturum başında depo haritasını gösteriyordu;
    ortamın E2E koşamadığını da AYNI yerde söylemesi gerekiyor, yoksa bilgi
    ancak aranırsa bulunur.
    """
    with open(os.path.join(REPO, ".claude", "settings.json"), encoding="utf-8") as f:
        ayarlar = json.load(f)
    komutlar = [k.get("command", "")
                for giris in ayarlar["hooks"]["SessionStart"]
                for k in giris["hooks"]]
    assert any("test_ortami.py" in k and "--ozet" in k for k in komutlar), (
        "SessionStart kancası test ortamını denetlemiyor")
