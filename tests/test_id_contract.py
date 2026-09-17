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
import subprocess

from fastapi.testclient import TestClient

import app as appmod

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "flow-ui" / "id-baseline.txt"
LEDGER = ROOT / "docs" / "flow-ui" / "id-defteri.md"

# index.html'e yüklenme sırasıyla; sıra bağlayıcı (core.js başta $ tanımlıyor).
# mobile.js EN SONDA: o da `$()` ile bir id'ye (#composer) bağlanıyor, yani
# aynı sarkma riskini taşıyor ve bu dosyanın kapsamı dışında kalmamalı.
#
# i18n.js EN BAŞTA ve buraya SONRADAN girdi (v0.23). PR #12'de eklenmişti ve
# listeye yazılmadığı için üst düzey adları bir tur boyunca hiç taranmadı —
# üstelik en çakışmaya açık adı O tanımlıyor: tek harflik `t`. Yani kapının
# kör noktası tam da en çok bakması gereken dosyadaydı. `KAPSAM_DISI` ile
# `test_the_scan_covers_every_shipped_script` bunun tekrarını engelliyor.
JS_FILES = ("i18n.js", "core.js", "folders.js", "assets.js", "palette.js",
            "settings.js", "viewer.js", "chat.js", "mobile.js")

# Taranmayan betikler — gerekçesiyle. Boş bırakılamaz bir defter: aşağıdaki
# kapı, `static/` altındaki HER betiğin ya listede ya burada olmasını şart
# koşuyor.
KAPSAM_DISI = {
    "pixel-canvas.js": "üçüncü parti (Ryan Mulligan, MIT); üst düzey adları "
                       "bizim sözleşmemize tabi değil — tests/"
                       "test_telif_basligi.py da onu ayrı tutuyor",
    "giris.js": "AYRI sayfanın betiği (`/giris` → static/giris.html, Faz 1 / 3): "
                "index.html'e yüklenmiyor, IIFE içinde ve küresel kapsama ad "
                "bırakmıyor — buradaki 'aynı sayfa, tek kapsam' iddialarının hiçbiri "
                "ona uygulanamaz. Kendi id bağları tests/test_hesap.py'de sınanıyor",
}

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



def test_go_disabled_tek_yerden_yaziliyor():
    """`#go.disabled`ın TEK yazarı olmalı ve o core.js'teki `syncGoGate`.

    Öncesinde dört ayrı yerden yazılıyordu (core.js iki, settings.js iki) ve
    chat.js beşinci bir mantık taşıyordu — yani şimdiden iki çelişen sahip
    vardı ve hangisinin son sözü söylediği çağrı SIRASINA kalıyordu. Kapı artık
    modu, meşguliyeti, sohbet yapılandırmasını ve seçili görsel modelinin
    durumunu BİRLİKTE görmek zorunda; ikinci bir yazar o bütünlüğü bozar.

    Ölçülen somut hata: `!configured` yalnız AZURE'u sınıyordu, yani yalnızca
    OpenAI anahtarı olan bir kullanıcıda "Üret" düğmesi kalıcı olarak ölüydü.
    """
    yazanlar = []
    for name, kaynak in _js_sources().items():
        for lineno, line in enumerate(kaynak.splitlines(), 1):
            if '("go").disabled' not in line:
                continue
            # OKUMA değil YAZMA arıyoruz: `= ` atamanın işareti.
            sag = line.split('("go").disabled', 1)[1].lstrip()
            if sag.startswith("=") and not sag.startswith("=="):
                yazanlar.append(f"{name}:{lineno}")

    assert len(yazanlar) == 1, (
        f"#go.disabled birden fazla yerden yazılıyor: {yazanlar}")
    assert yazanlar[0].startswith("core.js"), (
        f"tek yazar core.js olmalı (syncGoGate), bulunan: {yazanlar[0]}")


def test_the_scan_covers_every_shipped_script():
    """ÖLÇÜLEN KUSUR: `static/i18n.js` bir tur boyunca hiç taranmadı.

    PR #12'de eklendi, `JS_FILES`e yazılmadı ve kimse fark etmedi — çünkü liste
    ELLE tutuluyordu ve listede olmayan dosyanın öntanımlı hâli "taranmaz"dı.
    Oysa o dosya `index.html`de İLK yüklenen betik ve üst düzey `t` adını
    tanımlıyor: bu dosyadaki "hiçbir üst düzey ad iki dosyada tanımlı değil"
    iddiasının en çok ilgilendiği ad tam olarak oydu.

    `tests/test_i18n.py::test_every_shipped_module_is_classified` ile aynı
    kusur sınıfı ve aynı çözüm: liste kalıyor, ama artık EKSİKSİZ olmak
    zorunda. Yeni bir betik ya taranır ya gerekçesiyle `KAPSAM_DISI`na yazılır.
    """
    izlenen = subprocess.run(["git", "-C", str(ROOT), "ls-files", "static/*.js"],
                             check=True, capture_output=True, text=True).stdout
    betikler = {y.split("/")[-1] for y in izlenen.split()}
    assert len(betikler) > 5, f"kapsam şüpheli biçimde küçük: {len(betikler)}"

    bilinen = set(JS_FILES) | set(KAPSAM_DISI)
    assert not betikler - bilinen, (
        "SINIFLANMAMIŞ betik. Üst düzey ad tanımlıyor ya da `$()` ile bir id'ye "
        f"bağlanıyorsa `JS_FILES`e, değilse GEREKÇESİYLE `KAPSAM_DISI`na ekle: "
        f"{sorted(betikler - bilinen)}")
    assert not bilinen - betikler, (
        f"artık var olmayan betik sayılıyor: {sorted(bilinen - betikler)}")
    ikisinde = set(JS_FILES) & set(KAPSAM_DISI)
    assert not ikisinde, f"iki listede birden: {sorted(ikisinde)}"


def test_the_scan_follows_the_pages_load_order():
    """`JS_FILES`in SIRASI bağlayıcı (dosyanın başındaki not). Sıra sayfadan
    ayrışırsa "ilk tanımlayan kazanır" akıl yürütmesi sessizce yanlışlanır."""
    html = TestClient(appmod.app).get("/").text
    sayfada = [y for y in re.findall(r"/static/([a-z0-9_-]+\.js)", html)
               if y not in KAPSAM_DISI]
    assert sayfada == list(JS_FILES), (
        "yüklenme sırası ayrışmış - sayfa: "
        f"{sayfada} · liste: {list(JS_FILES)}")
