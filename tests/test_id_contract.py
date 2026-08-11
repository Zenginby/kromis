"""id sözleşmesi mandalı — Flow taşımasının güvenlik ağı.

Taşıma başlarken kural "id diff boş olmalı" idi. Tasarım bazı öğeleri gerçekten
kaldırdığı için (sekmeler, üst şerit araması, ayrı düzenle paneli) o kural
6 Ağustos kararıyla düştü: kaldırılan öğenin testi de onunla güncellenebiliyor.
Boş diff'in yerini bu dosya aldı ve **daha güçlü** bir yeri tutuyor —

    diff yalnızca id'nin YOKLUĞUNU görüyordu.
    Buradaki ikinci iddia JS bağının da silinmiş olmasını şart koşuyor,
    yani yeniden ADLANDIRMAYI da yakalıyor.

Kaldırmanın neden pahalı olduğu: `core.js:10`'da
`const $ = (id) => document.getElementById(id)`. Bu yolla 145 id'ye dokunuluyor
ve 56'sı top-level bağ — dosya yüklenirken çalışan `$("x").addEventListener(…)`
satırları. Böyle bir id kaybolursa `$()` `null` döner, `addEventListener`
`TypeError` atar ve o dosyanın o satırdan sonraki dinleyicilerinin HİÇBİRİ
kurulmaz. `pytest` bunu kendi başına göremez (HTML'i okuyor, JS'i çalıştırmıyor),
üçüncü iddia o boşluğu kapatıyor.

Depo geleneği: servis edilen artefakt doğrulanır (dosya değil), bu yüzden
`TestClient` üstünden okunuyor — `test_index.py` ile aynı yol.
"""

import pathlib
import re

from fastapi.testclient import TestClient

import app as appmod

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "flow-ui" / "id-baseline.txt"
LEDGER = ROOT / "docs" / "flow-ui" / "id-defteri.md"

# index.html'e yüklenme sırasıyla; sıra bağlayıcı (core.js başta $ tanımlıyor).
JS_FILES = ("core.js", "folders.js", "assets.js", "palette.js", "settings.js",
            "viewer.js", "chat.js")

_TOP_LEVEL_DECLARATION_RE = re.compile(
    r"^(?:(?:async\s+)?function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=)", re.M
)


def _baseline_ids():
    """Dondurulmuş taban: 25713f8'deki 152 id. `#` ile başlayan satırlar not."""
    lines = BASELINE.read_text(encoding="utf-8").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def _retired_ids():
    """Defterdeki tablonun ilk hücresi: `| \\`id\\` | … |`.

    Yorum içindeki örnek satır ayıklanmamalı, o yüzden HTML yorumları
    önce atılıyor.
    """
    text = re.sub(r"<!--.*?-->", "", LEDGER.read_text(encoding="utf-8"), flags=re.S)
    return set(re.findall(r"^\|\s*`([a-zA-Z0-9_-]+)`\s*\|", text, re.M))


def _served_ids():
    html = TestClient(appmod.app).get("/").text
    return set(re.findall(r'id="([a-zA-Z0-9_-]+)"', html))


def _js_sources():
    c = TestClient(appmod.app)
    return {name: c.get(f"/static/{name}").text for name in JS_FILES}


def _js_hits(id_, sources):
    """Bir id'ye JS'ten yapılan atıflar: `$("x")`, `getElementById("x")`,
    `querySelector("#x")`. Dosya adı + satır numarasıyla döner."""
    patterns = (
        rf"""\$\(\s*["']{re.escape(id_)}["']\s*\)""",
        rf"""getElementById\(\s*["']{re.escape(id_)}["']\s*\)""",
        rf"""querySelector(?:All)?\(\s*["'][^"']*#{re.escape(id_)}\b""",
    )
    hits = []
    for name, src in sources.items():
        for lineno, line in enumerate(src.splitlines(), start=1):
            if any(re.search(p, line) for p in patterns):
                hits.append(f"{name}:{lineno}")
    return hits


def test_baseline_matches_frozen_commit():
    """Taban 152 id ile dondurulmuş; kazara güncellenmesi kendisi bir hatadır."""
    assert len(_baseline_ids()) == 152, (
        "id-baseline.txt 25713f8'in anlık görüntüsü, canlı liste değil. "
        "Kaldırma id-defteri.md'ye yazılır, taban düzenlenmez."
    )


def test_kayip_id_defterde_yazili():
    """1. iddia: defterde gerekçesiyle yazmayan hiçbir id kaybolamaz."""
    kayip = _baseline_ids() - _served_ids() - _retired_ids()
    assert not kayip, (
        "Tabanda olup servis edilen HTML'de olmayan ve defterde de yazmayan id: "
        + ", ".join(sorted(kayip))
        + ".\nid kaldırmak serbest ama sessiz değil: docs/flow-ui/id-defteri.md'ye "
          "hangi tasarım kararıyla gittiğini, JS bağını nerede kaldırdığını ve "
          "hangi testi güncellediğini yaz."
    )


def test_kaldirilan_idnin_js_bagi_da_gitmis():
    """2. iddia: defterdeki id'ye JS'ten hâlâ dokunuluyorsa hata.

    R1'in gerçek çökme mekanizmasını yakalayan iddia bu. Yeniden adlandırmayı da
    yakalar: id değişip JS eski adı çağırmaya devam ederse burada düşer.
    """
    sources = _js_sources()
    sarkan = {i: h for i in sorted(_retired_ids()) if (h := _js_hits(i, sources))}
    assert not sarkan, (
        "Defterde kaldırılmış yazan id'ye JS hâlâ bakıyor:\n"
        + "\n".join(f"  {i} → {', '.join(h)}" for i, h in sarkan.items())
        + "\n$() null dönecek; top-level bir bağsa addEventListener TypeError atar "
          "ve o dosyanın kalan dinleyicileri hiç kurulmaz."
    )


def test_defter_durust():
    """3. iddia: defterde kaldırıldığı yazan id HTML'de duruyorsa defter yanlış."""
    hala_duran = _retired_ids() & _served_ids()
    assert not hala_duran, (
        "Defterde kaldırıldığı yazan ama HTML'de duran id: "
        + ", ".join(sorted(hala_duran))
        + ". Defter kaydı silinmeli ya da element gerçekten kaldırılmalı."
    )


def test_defter_tabandan_sec():
    """Defter yalnızca tabandaki id'leri kaldırabilir; hiç var olmamış bir id'yi
    'kaldırdım' diye yazmak kaydı anlamsız kılar ve iddiaları zayıflatır."""
    hayali = _retired_ids() - _baseline_ids()
    assert not hayali, (
        "Defterde tabanda hiç bulunmayan id: " + ", ".join(sorted(hayali))
    )


def test_toplevel_baglar_htmlde_duruyor():
    """Ağın en dar yeri: top-level `$("x").addEventListener(…)` satırlarındaki her
    id servis edilen HTML'de bulunmak ZORUNDA — defterde yazsa bile. Yazıyorsa
    2. iddia zaten düşer; bu test aynı çöküşü ters yönden, JS'ten bakarak kapatır.
    """
    served = _served_ids()
    eksik = {}
    for name, src in _js_sources().items():
        for lineno, line in enumerate(src.splitlines(), start=1):
            # girintisiz satır = modül gövdesi, yüklenirken çalışır
            if line[:1] in ("$", "c", "l") and (m := re.match(
                    r"""(?:const|let)?\s*[a-zA-Z_]*\s*=?\s*\$\(\s*["']([a-zA-Z0-9_-]+)["']\s*\)""",
                    line)):
                if m.group(1) not in served:
                    eksik.setdefault(m.group(1), []).append(f"{name}:{lineno}")
    assert not eksik, (
        "Yükleme anında bağlanan ama HTML'de bulunmayan id:\n"
        + "\n".join(f"  {i} → {', '.join(h)}" for i, h in eksik.items())
        + "\nBu, uygulama açılırken TypeError demek."
    )


def test_clear_preview_is_not_called():
    """Emekliye ayrılan clearPreview fonksiyonunun JS dosyalarında çağrısı olmamalı."""
    for name, src in _js_sources().items():
        assert "clearPreview(" not in src, f"{name} içinde silinen clearPreview() çağrısı kalmış"


def test_go_button_has_single_listener():
    """#go butonunun yalnızca tek bir addEventListener çağrısı olmalı (core.js:submitComposer)."""
    hits = []
    for name, src in _js_sources().items():
        for lineno, line in enumerate(src.splitlines(), start=1):
            if '$("go").addEventListener' in line:
                hits.append(f"{name}:{lineno}")
    assert len(hits) == 1, f"#go butonuna birden fazla addEventListener bağlı: {hits}"
    assert hits[0].startswith("core.js"), f"#go listener'ı core.js dışında bağlı: {hits[0]}"


def test_hicbir_ust_duzey_ad_iki_dosyada_tanimli_degil():
    """4. iddia: aynı üst düzey ad iki dosyada tanımlıysa SONRAKİ öncekini ezer.

    `JS_FILES` klasik script (ES module değil) ve hepsi TEK global kapsamı
    paylaşıyor — bu dosyanın başındaki sıra notu zaten bunu söylüyor. İki dosya
    aynı adı `function`/`const`/`let` ile tanımlarsa index.html'de sonra
    yüklenen kazanır ve önceki tanım **hata vermeden** kaybolur.

    Bu test Adım 12'de gerçekten olan bir kusurdan doğdu: Medya seçicisinin
    `renderPicker`'ı `palette.js`in aynı adlı (renk seçici) fonksiyonuyla
    çarpıştı; palette.js sonra yüklendiği için `openPicker()` medya seçicisini
    değil renk paletini çiziyordu. Seçici bomboş açılıyordu, konsolda tek satır
    hata yoktu — süit yeşil, ekran boş. Yalnız canlı tur yakaladı; bir daha
    yakalamak zorunda kalmasın.
    """
    # Yorumlar ayıklanıyor: gerekçe yorumları yasaklanan adı yazmak ZORUNDA
    # ("Adı `renderPicker` DEĞİL: palette.js aynı adı …") ve ham metinde
    # aranırsa iddia kendi açıklamasına takılır (§0.6/§0.7/§0.9'un dersi).
    nerede = {}
    for name, src in _js_sources().items():
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        src = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("//"))
        for m in _TOP_LEVEL_DECLARATION_RE.finditer(src):
            nerede.setdefault(m.group(1) or m.group(2), set()).add(name)

    carpisan = {ad: sorted(fs) for ad, fs in nerede.items() if len(fs) > 1}
    assert not carpisan, (
        "Aynı üst düzey ad birden çok dosyada tanımlı:\n"
        + "\n".join(f"  {ad} → {', '.join(fs)}" for ad, fs in sorted(carpisan.items()))
        + "\nindex.html'de sonra yüklenen öncekini SESSİZCE ezer."
    )


def test_ust_duzey_ad_taramasi_async_fonksiyonlari_yakalar():
    """`test_hicbir_ust_duzey_ad_iki_dosyada_tanimli_degil` regex'i async fonksiyonları da taramalı."""
    folders_src = _js_sources()["folders.js"]
    bulunanlar = {m.group(1) or m.group(2) for m in _TOP_LEVEL_DECLARATION_RE.finditer(folders_src)}
    assert "openPicker" in bulunanlar
    assert "loadFolders" in bulunanlar
    assert "refreshSearch" in bulunanlar


def test_refresh_search_matches_search_i_bare_referansla_cagirmadigi_mandallanir():
    """`refreshSearch` `matchesSearch`'i `all.filter(matchesSearch)` biçiminde çağırmamalı.

    `Array.prototype.filter` 2. parametre olarak `index` (0, 1, 2...) geçirir;
    `matchesSearch(rec, q = searchQuery)` imzası `q = index` alarak varsayılan
    sorguyu ezer ve Medya aramasını bozar.
    """
    folders_src = _js_sources()["folders.js"]
    assert "all.filter(matchesSearch)" not in folders_src, (
        "historyCache = all.filter(matchesSearch) kullanımı index parametresini q'ya zorlar!"
    )

