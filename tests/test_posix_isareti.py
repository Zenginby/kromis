"""POSIX varsayan testlerin DEFTERİ ve bekçisi (2026-09-19).

ÖLÇÜLEN KUSUR — sayı değil, sayının SESSİZCE BÜYÜMESİ: Windows'ta tam takım
2026-09-18'de "5 failed", 2026-09-19'da "9 failed" veriyordu. Dokuzunun da
sebebi testin kendi yalıtımının POSIX varsayması (`os.sep`, izin bitleri,
SIGTERM, `time.tzset`); üründe kusur yok, CI (Linux) hepsini yeşil görüyor.
Aradaki dört tanesi PR #52 ile geldi ve KİMSE FARK ETMEDİ — çünkü "zaten
kırmızı" bir listede bir satır daha kırmızı olmak görünmüyor. Onuncu kırmızı
GERÇEK bir gerileme olduğunda Windows'ta hiç ayırt edilemezdi.

Çare `tests/conftest.py::posix_gerekir`: dokuzu Windows'ta ATLANIYOR, atlama
takımın sonunda adıyla basılıyor ve CI'da `KROMIS_POSIX_ZORUNLU=1` ile HATA.

BU DOSYA O ÇÖZÜMÜN AÇIK KAPISINI KAPATIYOR. CLAUDE.md §5: "Elle tutulan her
KAPSAM listesinin bekçisi bir testtir." İşaretin nereye konacağı mekanik
ölçülemez — "bu test POSIX varsayıyor mu" sorusunu ancak bir insan yanıtlar —
yani liste ELLE tutuluyor ve elle tutulan listenin öntanımlı hâli *muaf*tır.
İşaret yanlış bir testin üstüne konsa (ya da bir testten sessizce düşse) hiçbir
mekanizma bağırmazdı: Windows'ta bir atlama eksilir, Linux'ta hiçbir şey
değişmez. `fal_client.py` ve `static/i18n.js` tam olarak böyle kaçmıştı;
`test_every_shipped_module_is_classified` ile
`test_the_scan_covers_every_shipped_script` ailesinin deyimi burada da aynı:
defter ile gerçek İKİ YÖNDE eşit olmak zorunda.

Defterin İKİNCİ işi belge: hangi testin neden atlandığını tek ekranda okumak.
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys

from tests import conftest

TESTLER = pathlib.Path(__file__).resolve().parent

# İŞARETLİ TESTLERİN DEFTERİ — `nodeid: ölçülen sebep`.
#
# Sebep sütunu, testin üstündeki `posix_gerekir(...)` gerekçesinin ÖZETİ değil,
# onun okunabilir kısaltması: burada NEYİN eksik olduğu bir bakışta görünsün.
# Tam gerekçe hep testin kendi başında duruyor.
#
# Bu listeye yeni bir satır eklemek "bir test daha Windows'ta koşmuyor"
# demektir; ucuz olmamalı. Önce sor: yalıtım POSIX'ten kurtarılabiliyor mu?
# Kurtulamıyorsa — izin bitleri, SIGTERM, `time.tzset` gibi yetenekler
# Windows'ta GERÇEKTEN yok — o zaman işaret doğru yanıttır.
DEFTER = {
    "tests/test_dosya.py::test_a_bucket_depo_refuses_an_absolute_path_outside_its_root":
        "os.sep — kök dışı anahtar ters bölülü, önek '/' ile kuruluyor",
    "tests/test_galeri_db.py::test_the_repository_list_matches_the_files_on_disk":
        "os.sep — elle liste '/', `os.path.relpath` taraması ters bölü",
    "tests/test_ice_aktar.py::test_the_v18_fixture_and_a_current_layout_land_in_the_db_field_by_field":
        "izin bitleri — 0o700 bekleniyor, Windows 0o777 veriyor",
    "tests/test_kimlik.py::test_two_users_have_separate_directories_and_never_see_each_others_media":
        "izin bitleri — 0o700 bekleniyor, Windows 0o777 (511) veriyor",
    "tests/test_isci.py::test_the_process_registers_a_worker_row_beats_and_exits_cleanly_on_sigterm":
        "SIGTERM — Windows'ta TerminateProcess, sinyal eli koşmuyor",
    "tests/test_isci.py::test_the_process_runs_a_maintenance_turn_at_startup_and_then_on_its_interval":
        "SIGTERM — Windows'ta TerminateProcess, sinyal eli koşmuyor",
    "tests/test_isci.py::test_the_process_keeps_beating_after_sigterm_until_the_draining_job_finishes":
        "SIGTERM — Windows'ta TerminateProcess, boşaltma penceresi açılmıyor",
    "tests/test_isci.py::test_the_process_rewrites_its_worker_row_when_it_disappears_underneath_it":
        "SIGTERM — Windows'ta TerminateProcess, sinyal eli koşmuyor",
    "tests/test_playwright_isler.py::"
    "test_the_elapsed_counter_starts_near_zero_in_a_browser_three_hours_east_of_the_server":
        "time.tzset — Windows'ta yok, sunucunun dilimi sabitlenemiyor",
}


def _kaynaktaki_isaretler() -> dict[str, int]:
    """`tests/` altında `@posix_gerekir(...)` taşıyan HER test — nodeid → satır.

    NEDEN KAYNAK OKUNUYOR, MODÜL İTHAL EDİLMİYOR: `test_playwright_isler.py`
    modül düzeyinde `importorskip` çağırıyor, yani playwright'sız bir makinede
    onu ithal etmek bu testi de atlatırdı — bekçi, bekçilik ettiği dosyanın
    varlığına bağlı olamaz.

    NEDEN PYTEST'İN TOPLADIĞI ÖĞELER DEĞİL: takım tek bir dosyayla da
    koşturulabiliyor (`pytest tests/test_posix_isareti.py`); o koşuda pytest
    yalnız bu dosyayı görür ve defterin geri kalanı "kayıp" sanılırdı. Kaynak
    her koşuda aynı yanıtı veriyor.
    """
    bulunan: dict[str, int] = {}
    for yol in sorted(TESTLER.glob("test_*.py")):
        agac = ast.parse(yol.read_text(encoding="utf-8"), filename=str(yol))
        for dugum in ast.walk(agac):
            if not isinstance(dugum, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for suslu in dugum.decorator_list:
                cagri = suslu.func if isinstance(suslu, ast.Call) else suslu
                ad = cagri.attr if isinstance(cagri, ast.Attribute) else getattr(cagri, "id", None)
                if ad == "posix_gerekir":
                    bulunan[f"tests/{yol.name}::{dugum.name}"] = dugum.lineno
    return bulunan


def test_the_ledger_and_the_marked_tests_are_the_same_set():
    """Defter ile işaret İKİ YÖNDE eşit — tek yön yetmez, ikisi ayrı kusuru yakalıyor.

    Deftere yazılıp işaretlenmemiş bir satır: test yeniden adlandırılmış ya da
    işaret düşmüş demektir; Windows'ta o test yine kırmızıya döner ve defter
    yalan söyler. İşaretlenip deftere yazılmamış bir test: sessizce bir atlama
    daha eklenmiş demektir — bu dosyanın var oluş sebebi olan kusurun ta
    kendisi (beşten dokuza, kimse fark etmeden).
    """
    bulunan = _kaynaktaki_isaretler()
    assert bulunan, (
        "hiçbir yerde `@posix_gerekir(...)` yok: işaretin adı mı değişti? "
        "Bu bekçi sessizce boş küme karşılaştırıyor olurdu")

    eksik = set(DEFTER) - set(bulunan)
    assert not eksik, (
        "DEFTERDE var, kaynakta İŞARET YOK — test yeniden mi adlandırıldı, "
        f"işaret mi düştü? {sorted(eksik)}")
    fazla = set(bulunan) - set(DEFTER)
    assert not fazla, (
        "İŞARETLİ ama defterde YOK. Yeni bir atlama sessizce eklenemez: "
        f"ölçülen sebebiyle `DEFTER`e yaz. {sorted(fazla)}")

    bos = [n for n, s in DEFTER.items() if not s.strip()]
    assert not bos, f"gerekçesiz defter satırı: {bos}"


def test_every_marked_test_carries_its_own_concrete_reason():
    """`reason` "Windows" demiyor, EKSİK OLAN ŞEYİ söylüyor.

    Paylaşılan tek bir gerekçe dokuz testin de neden atlandığını siler; özet
    (`_posix_atlama_ozeti`) o satırı okuyan kişiye düzeltmenin mümkün olup
    olmadığını söylemeli. Bu yüzden her gerekçe, Windows'ta gerçekten eksik
    olan YETENEĞİ adıyla anmak zorunda.

    `YETENEKLER` de elle tutulan bir defter: bugün bilinen dört POSIX boşluğu.
    Beşincisi çıkarsa bu test kırmızıya döner ve o boşluğu ADIYLA buraya
    yazmaya zorlar — istenen tam olarak budur, çünkü "işaret neden kondu"
    sorusunun yanıtı hiçbir zaman "Windows" olmamalı.
    """
    YETENEKLER = ("os.sep", "izin bitleri", "SIGTERM", "time.tzset")
    for yol in sorted(TESTLER.glob("test_*.py")):
        agac = ast.parse(yol.read_text(encoding="utf-8"), filename=str(yol))
        for dugum in ast.walk(agac):
            if not isinstance(dugum, ast.Call):
                continue
            if getattr(dugum.func, "id", None) != "posix_gerekir":
                continue
            assert len(dugum.args) == 1 and isinstance(dugum.args[0], ast.Constant), (
                f"{yol.name}:{dugum.lineno}: `posix_gerekir` tek bir dize gerekçe alır")
            sebep = dugum.args[0].value
            assert any(y in sebep for y in YETENEKLER), (
                f"{yol.name}:{dugum.lineno}: gerekçe Windows'ta eksik olan "
                f"YETENEĞİ anmıyor. Bilinen boşluklar: {YETENEKLER}. Yenisiyse "
                f"adını bu listeye ekle. Bulunan gerekçe: {sebep!r}")


def test_the_mark_skips_nothing_on_a_posix_machine():
    """Asıl ölçüm: işaret POSIX'te İNERT. Yoksa CI dokuz testi sessizce atlardı.

    `conftest.posix_atlananlar()` toplama anında dolan GERÇEK listedir, sabit
    değil — yani "koşul bozuldu ve Linux'ta da atlıyor" durumunu burada
    görürüz. Kardeşi `KROMIS_POSIX_ZORUNLU=1`: o takımı HİÇ başlatmıyor, bu
    ise kırmızı tek bir satır veriyor. İkisi farklı yerlerde iş görüyor —
    değişken yalnız CI'da verilmiş olsa bile bu test her koşuda burada.

    Windows'ta tersi sınanır: atlanan HER test defterde olmalı. Alt küme,
    çünkü takım bir dosyayla da koşturulabiliyor.
    """
    assert conftest.POSIX_ATLANACAK == (sys.platform == "win32"), (
        f"`POSIX_ATLANACAK` platformla uyuşmuyor ({sys.platform}): işaret ya "
        "yanlış makinede atlıyor ya da atlaması gereken yerde atlamıyor")
    atlanan = {nodeid for nodeid, _ in conftest.posix_atlananlar()}
    if conftest.POSIX_ATLANACAK:
        assert atlanan <= set(DEFTER), (
            f"defterde olmayan bir test atlandı: {sorted(atlanan - set(DEFTER))}")
        return
    assert not atlanan, (
        f"POSIX bir makinede ({sys.platform}) atlama var — `POSIX_ATLANACAK` "
        f"koşulu bozulmuş olmalı: {sorted(atlanan)}")


def test_the_mark_is_registered_so_it_cannot_become_a_typo():
    """Kayıtsız işaret pytest'te yalnız UYARI üretir; `--strict-markers` yoksa yazım hatası sessizdir.

    `pyproject.toml`daki kayıt, deponun `gercek_kimlik`/`gercek_anahtar` için
    yazdığı kuralın aynısı: uyarıyı susturmak değil, işareti ADIYLA kayda
    geçirmek.
    """
    kok = TESTLER.parent
    with open(os.path.join(kok, "pyproject.toml"), encoding="utf-8") as f:
        metin = f.read()
    assert "posix_gerekir(sebep):" in metin, (
        "`posix_gerekir` pyproject.toml'daki `markers` listesinde kayıtlı değil")
