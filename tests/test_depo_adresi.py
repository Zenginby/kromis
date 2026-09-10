"""Depo adresi TEK kaynaktan mı akıyor: guncelleme.DEPO ↔ elle yazılan bağlantılar.

NEDEN VAR: hesap bir kez taşındı (eski hesap → `Zenginby`) ve adres o an
dört ayrı dosyada elle yazılıydı — guncelleme.py, static/index.html (iki kez),
README.md, GUNCELLEME.md. Hepsi elle düzeltildi; kaçırılan bir tanesi kırmızıya
düşmez, sessizce 404 verir.

Kaçmaya en uygun yer index.html'deki GUNCELLEME.md bağlantısı: hemen üstündeki
"indir" bağlantısının href'i çalışma anında `static/settings.js` tarafından
yeniden yazılıyor (yani o, gerçek adresiyle sınanıyor), alttaki hiç. Kullanıcı
oraya ancak "bende hangi adımlar var" diye baktığında tıklıyor.

version.py'nin README rozeti için kurulan bekçisiyle (bkz.
test_version.py → test_readme_version_literals_match_the_single_source) aynı
duruş: literal elle yazılıyorsa bekçisi de bir test olmak zorunda.

TARANMAYAN İKİ YER — ikisi de bilinçli:
  * `docs/superpowers/plans/` : taşınmadan önce açılmış PR bağlantıları. Onlar
    TARİHSEL kayıt; yeni adla yazılsalar var olmayan bağlantılar olurdu.
  * `tests/`                  : pakete girmiyor ve test_guncelleme.py yabancı
    bir sahibi BİLEREK kullanıyor (reddedilmesi gereken adres örneği).
"""
from __future__ import annotations

import os
import re
import subprocess

import guncelleme

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Bu projenin deposuna yapılan atıflar — başka projelerin GitHub adresleri
# (android/gradlew → gradle/gradle, static/fonts/OFL.txt → googlefonts) kalıba
# hiç girmesin diye depo ADI kalıbın içine sabitlendi.
_ATIF = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/kromis")

_TARANMAZ = ("docs/superpowers/", "tests/")


def _izlenen_dosyalar() -> list[str]:
    cikti = subprocess.run(
        ["git", "-C", REPO, "ls-files"], check=True, capture_output=True, text=True
    ).stdout
    return [y for y in cikti.splitlines() if y and not y.startswith(_TARANMAZ)]


def _atiflar() -> dict[str, set[str]]:
    """{dosya: {o dosyada geçen sahip adları}} — okunamayan (ikili) dosyalar atlanır."""
    bulunan: dict[str, set[str]] = {}
    for yol in _izlenen_dosyalar():
        try:
            with open(os.path.join(REPO, yol), encoding="utf-8") as f:
                metin = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        sahipler = set(_ATIF.findall(metin))
        if sahipler:
            bulunan[yol] = sahipler
    return bulunan


def test_her_depo_atifi_tek_kaynakla_ayni_sahibi_gosteriyor():
    sahip = guncelleme.DEPO.split("/")[0]
    sapan = {y: sorted(s) for y, s in _atiflar().items() if s != {sahip}}
    assert not sapan, (
        f"guncelleme.DEPO sahibi {sahip!r}, ama bu dosyalar başkasını gösteriyor: "
        f"{sapan} — tek kaynak bozuldu"
    )


def test_kullaniciya_gorunen_uc_dosya_gercekten_taraniyor():
    """Bekçinin kendisinin bekçisi: kalıp bir gün hiçbir şeyi yakalamaz hâle
    gelirse üstteki iddia BOŞ kümeyle yeşil kalır ve ayrışmayı hiç görmezdik."""
    bulunan = set(_atiflar())
    # guncelleme.py listede YOK: adresi orada `f"…/{DEPO}/…"` olarak kuruluyor,
    # yani kalıbın aradığı düz metin hiç geçmiyor — tek kaynağın kendisi o.
    for yol in ("static/index.html", "README.md", "GUNCELLEME.md"):
        assert yol in bulunan, f"{yol} içinde depo atıfı bulunamadı — kalıp bayatladı mı?"


def test_guncelleme_md_baglantisi_index_html_de_dogru_yolu_gosteriyor():
    """Adres doğru sahipte olup da yol yanlış olabilir; bu bağlantı çalışma
    anında yeniden yazılmadığı için tek bekçisi burası."""
    with open(os.path.join(REPO, "static/index.html"), encoding="utf-8") as f:
        metin = f.read()
    assert f"https://github.com/{guncelleme.DEPO}/blob/main/GUNCELLEME.md" in metin
