#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Yerel test ortamını CI'ınkiyle AYNI yapar — E2E DÂHİL.

NEDEN VAR (2026-09-13'te ÖLÇÜLDÜ, tahmin değil): `ci.yml` bu depoda dokuz kez
kırmızıya döndü ve SEKİZİNDE düşen testler `tests/test_playwright_*.py`
dosyalarındaydı. Dokuzuncusu da aynı ailenin öteki yüzü: `tests/test_index.py`
kök belge listesini sayan bir bekçiydi ve yerelde koşulsaydı 78 saniyede
görülürdü. Yani her iki durumda da CI, takımın İLK koştuğu yerdi.

E2E tarafının sebebi tek bir satır:

    pytest.importorskip("playwright", reason="playwright kurulu değil — …")

Playwright kurulu DEĞİLSE o 18 E2E testi ATLANIYOR ve pytest yine "yeşil"
diyor. Yani "takım geçti" cümlesi, E2E'nin hiç koşmadığı bir makinede
"takımın beşte dördü geçti" anlamına geliyor; geri kalanı ilk kez CI'da
koşuyor. Kırılma sınıfı da hep aynı: arayüz metni / ön tanımlı dil / DOM
çapası değişiyor, yalnız E2E görüyor (ör. v0.22.0'da ön tanımlı dil
İngilizce'ye çevrildi, 7 E2E testi birden düştü).

İKİNCİ YARISI DAHA SESSİZ: taze bir Claude Code oturumunun konteynerinde
takım HİÇ koşamıyor. Aynı gün aynı konteynerde ölçüldü:

    python3 -V                → 3.11.15   (bu depo 3.13+ istiyor, conftest durduruyor)
    python3 -m pytest         → No module named pytest
    pip install -r requirements.txt → proxy_tools tekerleği derlenmiyor
                                      (Debian setuptools, AttributeError: install_layout)

Yani CLAUDE.md'nin "tam takım (CI'ın koştuğu şey)" dediği komut o konteynerde
ya hiç koşmuyor ya da E2E'siz koşuyor. Bu araç ikisini birden kapatıyor:
3.13+ bir `.venv` kuruyor, `_test.yml`in kurduğu HER ŞEYİ kuruyor ve
tarayıcıyı gerçekten açılır hâle getiriyor.

NEDEN SÖZLEŞME `_test.yml`DEN OKUNUYOR (burada kopya YOK): bu deponun tekrar
eden kusur sınıfı "aynı gerçeğin iki yerde yazılması" (bkz. `_test.yml`in
kendi başlığı: pytest işi üç workflow'a kopyalanmıştı ve sessizce ayrıştı).
Python pini, gereksinim dosyaları, playwright sürümü ve tarayıcı adı bu
yüzden CI dosyasının SATIRLARINDAN okunuyor; `tests/test_test_ortami.py` de
aynı değerleri PyYAML ile bağımsızca ayrıştırıp karşılaştırıyor. Yani CI
pinini değiştiren bir PR, yerel ortamı kendiliğinden birlikte taşıyor.

NEDEN SALT KİTAPLIK (PyYAML YOK): bu dosya SessionStart kancasında, oturumun
KENDİ `python3`üyle koşuyor — yani hiçbir şeyin kurulu olmadığı yorumlayıcıyla.
`graf_uret.py` aynı sebeple salt kitaplık. Regex'in kör noktası kabul edilebilir
çünkü bekçi testi aynı dosyayı gerçek bir YAML ayrıştırıcısıyla okuyup
karşılaştırıyor.

TARAYICI İNDİRİLEMEYEN ORTAMLAR: Claude Code konteynerinde `cdn.playwright.dev`
ağ ilkesiyle KAPALI (ölçüldü: `403 request blocked: no rule or allowlist entry
allows host`). Ama aynı imaj `PLAYWRIGHT_BROWSERS_PATH` altında HAZIR bir
chromium taşıyor — yalnız yapı numarası playwright'ın istediğinden farklı
(1194 ≠ 1234) ve dizin düzeni de değişmiş. Bu araç o durumda indirmeyi
zorlamak yerine VAR OLAN ikiliyi playwright'ın aradığı ada bağlıyor. Ölçüldü:
18 E2E testinin 18'i 54 saniyede yeşil. Yaklaşıklık olduğu da SÖYLENİYOR —
tarayıcı yapısı CI'ınkiyle aynı değil, yani bu kapı CI'ın yerine geçmez; onun
ilk koşusunu tahmin edilebilir yapar.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_WORKFLOW = os.path.join(KOK, ".github", "workflows", "_test.yml")
TESTLER = os.path.join(KOK, "tests")
CONFTEST = os.path.join(TESTLER, "conftest.py")
VENV = os.path.join(KOK, ".venv")

# E2E'yi atlamayı YASAKLAYAN ortam değişkeni (tests/conftest.py okuyor).
# Adı burada da yazılı çünkü araç, önerdiği komutu yazarken kullanıyor.
E2E_ZORUNLU = "KROMIS_E2E_ZORUNLU"


# ---------------------------------------------------------------- CI sözleşmesi

def _ci_metni() -> str:
    with open(TEST_WORKFLOW, encoding="utf-8") as f:
        metin = f.read()
    # Tam satırlık YAML yorumları ATILIYOR: `_test.yml`in gerekçe blokları
    # `requirements-dev.txt` ve `playwright` adlarını bolca anıyor ve onlar
    # KURULAN şey değil, kurulmama SEBEBİ. Yorumları saymak, aracı CI'ın
    # yapmadığı bir şeyi yapmaya iterdi.
    return "\n".join(s for s in metin.splitlines() if not s.lstrip().startswith("#"))


def ci_sozlesmesi() -> dict:
    """`_test.yml` hangi ortamı kuruyor? Cevap onun satırlarından okunuyor."""
    metin = _ci_metni()

    python = re.search(r"python-version:\s*['\"]?(\d+\.\d+)", metin)

    # Sıra korunuyor: pip `-r` dosyalarını verildiği sırayla çözüyor ve
    # requirements.txt'in önce gelmesi tesadüf değil (bkz. o dosyaların başlığı).
    gereksinimler: list[str] = []
    for ad in re.findall(r"-r\s+(requirements[A-Za-z0-9._-]*\.txt)", metin):
        if ad not in gereksinimler:
            gereksinimler.append(ad)

    pw = re.search(r"pip install\s+[^\n]*?\bplaywright(==[^\s'\"]+)?", metin)
    kur = re.search(r"playwright install([^\n]*)", metin)
    parcalar = kur.group(1).split() if kur else []

    return {
        "python": python.group(1) if python else "",
        "gereksinimler": gereksinimler,
        # Pin'siz bir `pip install playwright` de geçerli bir cevap: o zaman
        # yerelde de pinsiz kuruyoruz, CI ne yapıyorsa o.
        "playwright": "playwright" + ((pw.group(1) or "") if pw else ""),
        "playwright_var": bool(pw),
        "tarayicilar": [p for p in parcalar if not p.startswith("-")],
        "with_deps": "--with-deps" in parcalar,
    }


def _modul_duzeyinde_atliyor(kaynak: str) -> bool:
    """Dosya, MODÜL DÜZEYİNDE `pytest.importorskip("playwright")` çağırıyor mu?

    NEDEN AST, metin araması DEĞİL — ölçülerek öğrenildi (2026-09-13): ilk
    hâli `'importorskip("playwright"' in metin` idi ve beş dosya buldu. İkisi
    E2E DEĞİLDİ: `test_playwright_kurulumu.py` ile `test_test_ortami.py` o
    diziyi yalnız GEREKÇESİNDE anıyor. Yani tarayıcı, kendisini anlatan
    yorumları da sayıyordu ve uyarı olmayan bir atlamayı bildiriyordu.

    `graf_uret.py` Python tarafında aynı sebeple AST kullanıyor: kaynağın
    ANLAMINI soran bir soruya metin araması cevap veremez.

    MODÜL DÜZEYİ şart: bir işlevin içindeki `importorskip` yalnız o testi
    atlar, dosyayı değil.
    """
    try:
        agac = ast.parse(kaynak)
    except SyntaxError:
        return False
    for dugum in agac.body:                      # yalnız üst düzey ifadeler
        if not isinstance(dugum, ast.Expr) or not isinstance(dugum.value, ast.Call):
            continue
        cagri = dugum.value
        if not isinstance(cagri.func, ast.Attribute):
            continue
        if cagri.func.attr != "importorskip":
            continue
        ilk = cagri.args[0] if cagri.args else None
        if isinstance(ilk, ast.Constant) and ilk.value == "playwright":
            return True
    return False


def e2e_dosyalari() -> list[str]:
    """Playwright yokken ATLANAN test dosyaları — liste DEĞİL, ÖLÇÜM.

    TEK TANIM BURADA, `tests/conftest.py` de bunu ithal ediyor: adları iki
    yerde saymak, yeni bir E2E dosyası eklendiğinde birinin geride kalması
    demekti — yani uyarı tam da kapsamı genişlediği anda daralırdı.

    Bu dosyanın SALT KİTAPLIK olması bu ithali mümkün kılan şey: conftest
    pytest başlarken yükleniyor ve orada üçüncü parti bir şey ithal etmek
    takımın kendisini kuruluma bağımlı yapardı.
    """
    bulunan = []
    for ad in sorted(os.listdir(TESTLER)):
        if not (ad.startswith("test_") and ad.endswith(".py")):
            continue
        with open(os.path.join(TESTLER, ad), encoding="utf-8") as f:
            if _modul_duzeyinde_atliyor(f.read()):
                bulunan.append(ad)
    return bulunan


def asgari_python() -> tuple[int, int]:
    """Deponun asgari Python'u — TEK tanım `tests/conftest.py`de, burada OKUNUYOR."""
    with open(CONFTEST, encoding="utf-8") as f:
        m = re.search(r"^ASGARI_PYTHON\s*=\s*\((\d+),\s*(\d+)\)", f.read(), re.M)
    if not m:                                   # tanım taşındıysa sessizce yanlış
        raise SystemExit("tests/conftest.py'de ASGARI_PYTHON bulunamadı")   # cevap vermektense dur
    return int(m.group(1)), int(m.group(2))


# ------------------------------------------------------------------ yorumlayıcı

def venv_python() -> str:
    alt, ad = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    return os.path.join(VENV, alt, ad)


def _surum(yorumlayici: str) -> tuple[int, int] | None:
    """Verilen yorumlayıcının (major, minor)'ı — yoksa None."""
    try:
        c = subprocess.run(
            [yorumlayici, "-c", "import sys; print('%d %d' % sys.version_info[:2])"],
            capture_output=True, text=True, timeout=30, encoding="utf-8")
    except (OSError, subprocess.SubprocessError):
        return None
    if c.returncode != 0:
        return None
    try:
        a, b = c.stdout.split()
        return int(a), int(b)
    except ValueError:
        return None


def _aday_yorumlayicilar(sozlesme: dict) -> list[str]:
    """`.venv` kurulacaksa hangi yorumlayıcıyla? CI'ın pini önce.

    NEDEN CI'IN PİNİ ÖNCE: yerelde 3.13, CI'da 3.14 koşan bir takım, sürüme
    bağlı bir kırılmayı yine CI'ın ilk koşusuna bırakırdı — bu aracın kapatmaya
    çalıştığı kusurun ta kendisi. Bulunamazsa asgariye kadar iniliyor; o da
    yoksa çalışan yorumlayıcı (yeterliyse) kullanılıyor.
    """
    adaylar: list[str] = []
    ci = sozlesme["python"]
    if ci:
        adaylar.append(f"python{ci}")
    asgari_major, asgari_minor = asgari_python()
    ci_minor = int(ci.split(".")[1]) if ci else asgari_minor
    for minor in range(max(ci_minor, asgari_minor), asgari_minor - 1, -1):
        ad = f"python{asgari_major}.{minor}"
        if ad not in adaylar:
            adaylar.append(ad)
    adaylar.append(sys.executable)
    return adaylar


# ----------------------------------------------------------------------- durum

_MODUL_BETIGI = """
import importlib.util, json, sys
print(json.dumps({
    "surum": "%d.%d.%d" % sys.version_info[:3],
    "pytest": importlib.util.find_spec("pytest") is not None,
    "playwright": importlib.util.find_spec("playwright") is not None,
}))
"""

# Tarayıcı sorusunun TEK dürüst cevabı onu AÇMAKTIR. `executable_path` bir
# vekil olurdu ve bu depo vekilden bir kez yandı zaten (bkz.
# tests/test_playwright_kurulumu.py): "paket kurulu mu" sorusu "tarayıcı var mı"
# sorusunun yerine geçmiş ve üç paketleme işini birden kırmızıya çevirmişti.
_TARAYICI_BETIGI = """
import json
from playwright.sync_api import sync_playwright
try:
    with sync_playwright() as p:
        t = p.chromium.launch(headless=True)
        t.close()
    print(json.dumps({"tamam": True}))
except Exception as hata:
    print(json.dumps({"tamam": False, "hata": str(hata)}))
"""


def _json_kos(yorumlayici: str, betik: str, saniye: int) -> dict:
    try:
        c = subprocess.run([yorumlayici, "-c", betik], capture_output=True,
                           text=True, timeout=saniye, encoding="utf-8")
        return json.loads(c.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return {}


def durum(tarayiciyi_ac: bool = True) -> dict:
    """Bu makine takımı CI'ın koştuğu gibi koşabilir mi?

    `tarayiciyi_ac=False` SessionStart kancası için: orada bütçe 30 saniye ve
    tarayıcı açmak ~1 saniyenin üstünde. Kanca "hazır DEĞİL"i erken söylesin
    diye ucuz kontrollerle yetiniyor; kesin cevabı `--kontrol` veriyor.
    """
    sozlesme = ci_sozlesmesi()
    yorumlayici = venv_python() if os.path.exists(venv_python()) else sys.executable
    asgari = asgari_python()

    d = {"yorumlayici": yorumlayici, "sozlesme": sozlesme, "asgari": asgari,
         "surum": "", "yeterli_python": False, "pytest": False,
         "playwright": False, "tarayici": None, "tarayici_hatasi": ""}

    moduller = _json_kos(yorumlayici, _MODUL_BETIGI, 60)
    if not moduller:
        return d
    d["surum"] = moduller["surum"]
    parcalar = tuple(int(p) for p in moduller["surum"].split(".")[:2])
    d["yeterli_python"] = parcalar >= asgari
    d["pytest"] = bool(moduller["pytest"])
    d["playwright"] = bool(moduller["playwright"])

    if d["playwright"] and tarayiciyi_ac:
        sonuc = _json_kos(yorumlayici, _TARAYICI_BETIGI, 180)
        d["tarayici"] = bool(sonuc.get("tamam"))
        d["tarayici_hatasi"] = str(sonuc.get("hata", ""))
    return d


def hazir(d: dict) -> bool:
    return bool(d["yeterli_python"] and d["pytest"] and d["playwright"]
                and d["tarayici"] is not False)


# --------------------------------------------------------------------- kurulum

def _kos(komut: list[str], sessiz: bool) -> int:
    if not sessiz:
        print("+ " + " ".join(komut))
    return subprocess.run(komut, cwd=KOK).returncode


def _venv_kur(sozlesme: dict, sessiz: bool) -> str:
    """3.13+ bir `.venv` — yoksa kurar, varsa ve yeterliyse dokunmaz."""
    yorumlayici = venv_python()
    if os.path.exists(yorumlayici) and (_surum(yorumlayici) or (0, 0)) >= asgari_python():
        return yorumlayici

    for aday in _aday_yorumlayicilar(sozlesme):
        s = _surum(aday)
        if s and s >= asgari_python():
            if _kos([aday, "-m", "venv", VENV], sessiz) == 0:
                return yorumlayici
    asgari = ".".join(str(p) for p in asgari_python())
    raise SystemExit(
        f"Python {asgari}+ bulunamadi. Bu depo daha eskisinde KOSAMAZ "
        "(tests/conftest.py durduruyor, gerekcesi orada). Kurup tekrar deneyin.")


def _tarayici_koku() -> str:
    """Playwright tarayıcıları nereye koyuyor? (belgelenmiş davranış)"""
    ozel = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if ozel and ozel != "0":
        return ozel
    ev = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(ev, "Library", "Caches", "ms-playwright")
    if os.name == "nt":
        return os.path.join(os.environ.get("LOCALAPPDATA", ev), "ms-playwright")
    return os.path.join(ev, ".cache", "ms-playwright")


def _ikili_ara(kok: str, adlar: tuple[str, ...]) -> str | None:
    """Kökün altında bu adlardan biri duruyor mu? (indirme kapalıysa tek umut)"""
    if not os.path.isdir(kok):
        return None
    for dizin, _, dosyalar in os.walk(kok):
        for ad in adlar:
            if ad in dosyalar:
                return os.path.join(dizin, ad)
    return None


def _shim_kur(beklenen: str, sessiz: bool) -> bool:
    """İndirme engelliyse: makinedeki chromium'u playwright'ın ARADIĞI ada bağlar.

    `beklenen` playwright'ın kendi hata mesajından geliyor — yani hangi yol ve
    hangi yapı numarası isteniyorsa O. Sürüm arasında dizin düzeni değişiyor
    (1194: `chrome-linux/headless_shell`, 1234: `chrome-headless-shell-linux64/
    chrome-headless-shell`), bu yüzden düzen TAHMİN EDİLMİYOR, sorulan yola
    bağ atılıyor.
    """
    if os.path.exists(beklenen):
        return True
    istenen_ad = os.path.basename(beklenen)
    # 1194'te adı `headless_shell`, 1234'te `chrome-headless-shell`; ikisi de
    # aynı ikili. Sıradaki yeniden adlandırmada bu demet uzar.
    adaylar = {"chrome-headless-shell": ("chrome-headless-shell", "headless_shell"),
               "headless_shell": ("headless_shell", "chrome-headless-shell"),
               "chrome": ("chrome",)}.get(istenen_ad, (istenen_ad,))
    varolan = _ikili_ara(_tarayici_koku(), adaylar)
    if not varolan:
        return False
    kok = _tarayici_koku()
    goreli = os.path.relpath(beklenen, kok)
    try:
        os.makedirs(os.path.dirname(beklenen), exist_ok=True)
        os.symlink(varolan, beklenen)
        # Playwright kurulumu "tamamlanmış" saysın diye: kendi `install`ı da
        # bu damgayı bırakıyor.
        damga = os.path.join(kok, goreli.split(os.sep)[0], "INSTALLATION_COMPLETE")
        if not os.path.exists(damga):
            with open(damga, "w", encoding="utf-8") as f:
                f.write("")
    except OSError as hata:
        if not sessiz:
            print(f"  bağ kurulamadı ({hata}) — tarayıcı elle kurulmalı")
        return False
    if not sessiz:
        print(f"  {goreli} → {varolan}")
    return True


def _tarayici_kur(yorumlayici: str, sozlesme: dict, sessiz: bool) -> None:
    """Önce CI'ın komutu; indirme engelliyse makinedekine bağ."""
    komut = [yorumlayici, "-m", "playwright", "install"]
    if sozlesme["with_deps"]:
        komut.append("--with-deps")
    komut += sozlesme["tarayicilar"]
    _kos(komut, sessiz)

    sonuc = _json_kos(yorumlayici, _TARAYICI_BETIGI, 180)
    if sonuc.get("tamam"):
        return

    hata = str(sonuc.get("hata", ""))
    beklenen = re.search(r"Executable doesn't exist at (\S+)", hata)
    if not beklenen:
        if not sessiz:
            print("tarayıcı açılmıyor ve sebebi okunamadı:\n  " + hata[:400])
        return
    if not sessiz:
        print("tarayıcı indirilemedi (ağ ilkesi?) — makinedekine bağ atılıyor:")
    if _shim_kur(beklenen.group(1), sessiz):
        ikinci = _json_kos(yorumlayici, _TARAYICI_BETIGI, 180)
        if not ikinci.get("tamam") and not sessiz:
            print("  bağ kuruldu ama tarayıcı yine açılmadı:\n  "
                  + str(ikinci.get("hata", ""))[:400])


def kur(sessiz: bool = False) -> int:
    sozlesme = ci_sozlesmesi()
    yorumlayici = _venv_kur(sozlesme, sessiz)

    _kos([yorumlayici, "-m", "pip", "install", "--upgrade", "pip"], sessiz)
    pip = [yorumlayici, "-m", "pip", "install"]
    for ad in sozlesme["gereksinimler"]:
        pip += ["-r", ad]
    if _kos(pip, sessiz) != 0:
        return 1
    if sozlesme["playwright_var"]:
        # AYRI ADIM, `requirements-dev.txt`E DEĞİL: paketleme işleri o dosyayı
        # kurup pytest'i tarayıcısız koşturuyor; playwright orada kurulu olursa
        # `importorskip` atlamayı bırakır ve E2E testleri düşer. Gerekçe ve
        # kapısı: tests/test_playwright_kurulumu.py.
        if _kos(pip[:4] + [sozlesme["playwright"]], sessiz) != 0:
            return 1
        _tarayici_kur(yorumlayici, sozlesme, sessiz)

    d = durum()
    if not sessiz:
        print()
        print(rapor(d))
    return 0 if hazir(d) else 1


# ------------------------------------------------------------------------ rapor

def kosma_komutu(d: dict) -> str:
    """Takımı CI gibi koşturan komut — ASCII, çünkü kopyalanacak."""
    yorumlayici = d["yorumlayici"]
    if os.path.abspath(yorumlayici).startswith(os.path.abspath(VENV)):
        yorumlayici = os.path.join(".venv", "Scripts" if os.name == "nt" else "bin",
                                   "python.exe" if os.name == "nt" else "python")
    return f"{yorumlayici} -m pytest tests/ -q"


def rapor(d: dict) -> str:
    satirlar = []
    asgari = ".".join(str(p) for p in d["asgari"])
    if not d["yeterli_python"]:
        satirlar.append(f"yorumlayici: {d['surum'] or 'okunamadi'} — {asgari}+ gerekiyor")
    if not d["pytest"]:
        satirlar.append("pytest kurulu degil — takim HIC kosmuyor")
    if not d["playwright"]:
        satirlar.append(f"playwright kurulu degil — {len(e2e_dosyalari())} E2E "
                        "dosyasi SESSIZCE atlanir")
    elif d["tarayici"] is False:
        satirlar.append("tarayici acilmiyor — E2E testleri duser")

    if not satirlar:
        return ("Test ortami hazir: E2E dahil tam takim kosabilir.\n"
                f"    {kosma_komutu(d)}")
    return ("Test ortami CI'inkiyle AYNI DEGIL:\n"
            + "\n".join("  - " + s for s in satirlar)
            + "\n  Duzeltmek icin: python3 tools/test_ortami.py")


def _ozet(d: dict) -> str:
    """SessionStart bağlamı: kısa, ve eyleme dönük kısmı ASCII."""
    if hazir(d):
        # "kurulu", "hazir" DEĞİL: bu kip tarayıcıyı AÇMIYOR (yukarıdaki
        # gerekçe), yani E2E'nin gerçekten koştuğunu kanıtlamış olmuyor.
        # Söylediğinden fazlasını iddia eden bir satır, tam da bu aracın
        # kapatmaya çalıştığı kusur olurdu.
        return ("Test ortami kurulu gorunuyor. KURAL: degisikligi itmeden ONCE "
                "E2E dahil tam takimi kos: " + kosma_komutu(d)
                + "  (kesin denetim: python3 tools/test_ortami.py --kontrol)")
    return (
        "Test ortami HAZIR DEGIL: `pytest tests/ -q` bu makinede ya hic kosmuyor "
        f"ya da {len(e2e_dosyalari())} E2E dosyasini sessizce atliyor. Bu depoda "
        "olculdu (2026-09-13): CI'in ilk kosusu dokuz kez kirmizi oldu, "
        "SEKIZINDE dusen testler tam olarak o atlanan dosyalardaydi. "
        "Degisikligi itmeden once `python3 tools/test_ortami.py` kos "
        "(surer birkac dakika), sonra tam takimi.")


def main(argv: list[str]) -> int:
    secenekler = set(argv[1:])
    bilinmeyen = secenekler - {"--kontrol", "--ozet", "--sessiz", "--json"}
    if bilinmeyen:
        print(f"bilinmeyen seçenek: {' '.join(sorted(bilinmeyen))}\n"
              "kullanım: test_ortami.py [--kontrol|--ozet] [--sessiz] [--json]",
              file=sys.stderr)
        return 2

    if "--ozet" in secenekler:
        # Kanca kipi: HER ZAMAN 0 döner. Sıfırdan farklı bir çıkış, oturumun
        # açılışında sebepsiz bir hata gibi görünür ve kancanın kapatılmasına
        # yol açar — graf_uret.py'deki aynı tercih.
        metin = _ozet(durum(tarayiciyi_ac=False))
        if "--json" in secenekler:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": metin}}, ensure_ascii=False))
        else:
            print(metin)
        return 0

    if "--kontrol" in secenekler:
        d = durum()
        if "--sessiz" not in secenekler:
            print(rapor(d), file=sys.stderr if not hazir(d) else sys.stdout)
        return 0 if hazir(d) else 1

    return kur("--sessiz" in secenekler)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
