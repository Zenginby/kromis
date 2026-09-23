"""Sözlük kapısı: iki dil AYNI anahtar kümesini taşımak zorunda.

NEDEN VAR: eksik bir çeviri SESSİZ. `i18n.t` bulamadığı anahtarı önce `tr`ye,
sonra anahtarın kendisine düşürüyor — yani `en.json`'a yazılmayan bir anahtar
İngilizce arayüzde Türkçe bir cümle olarak görünüyor. Ekranda bir şey durduğu
için kimse "bozuk" demiyor; kusur ancak İngilizce kullanan biri o ekrana
bakınca ortaya çıkıyor, o da genelde depoya rapor etmiyor.

Bu, depodaki "türetilen her şeyin bekçisi bir testtir" kuralının bu iş için
karşılığı: kataloglar el yazısı ama ARALARINDAKİ İLİŞKİ türetilmiş bir
gerçek ve elle korunamaz.

İkinci bir kusur sınıfı daha var ve o gürültülü: şablona yazılmış ama
kataloğa yazılmamış bir anahtar (`{{t:rail.studio}}` ↔ `rail.studo`). O da
ekranda ham anahtar olarak görünürdü; aşağıdaki kapılar yazım hatasını
kullanıcıya varmadan yakalıyor.
"""
import ast
import json
import os
import re
import subprocess

import pytest
from fastapi.testclient import TestClient

import app as appmod
import i18n
import models
import paths
from services import dil

# Galeri/klasör/üretim rotaları DB'de (Faz 1 / 5): test kullanıcısı gerçek satır,
# `db.oturum` bu dosyanın motoruna bağlı — gerekçe tests/conftest.py::depo_db.
pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N_DIR = os.path.join(REPO, "bundled", "i18n")
STATIC = os.path.join(REPO, "static")


def _yukle(lang):
    with open(os.path.join(I18N_DIR, f"{lang}.json"), encoding="utf-8") as f:
        return json.load(f)


def test_every_declared_language_has_a_catalog_file():
    """`i18n.LANGUAGES` bir SÖZ: o jetonu seçen kullanıcı bir sözlük bulmalı.

    Jeton eklenip dosya unutulursa `prefs` seçimi kabul eder, `catalog()` boş
    döner ve arayüz baştan sona ham anahtar gösterir — üstelik kullanıcının
    geri dönmesi gereken Ayarlar düğmesi de anahtara dönüştüğü için çıkış yolu
    kapanır.
    """
    for lang in i18n.LANGUAGES:
        yol = os.path.join(I18N_DIR, f"{lang}.json")
        assert os.path.exists(yol), f"sözlük dosyası yok: {yol}"


def test_the_catalogs_all_carry_the_same_keys():
    temel = set(_yukle(i18n.FALLBACK))
    for lang in i18n.LANGUAGES:
        if lang == i18n.FALLBACK:
            continue
        baska = set(_yukle(lang))
        eksik = temel - baska
        fazla = baska - temel
        assert not eksik, f"{lang}.json eksik anahtarlar: {sorted(eksik)[:10]}"
        assert not fazla, f"{lang}.json fazla anahtarlar: {sorted(fazla)[:10]}"


def test_no_catalog_value_is_empty():
    """Boş bir değer, eksik bir anahtardan DAHA sinsi: `t()` onu bulur ve
    döndürür, yani düşüş sırası hiç işlemez ve ekranda hiçbir şey yazmaz."""
    for lang in i18n.LANGUAGES:
        for anahtar, deger in _yukle(lang).items():
            assert deger.strip(), f"{lang}.json boş değer: {anahtar}"


def test_every_value_is_a_string():
    """Liste ya da sayı yazılmış bir çeviriyi `i18n.catalog` süzüyor, yani
    çalışma anında sessizce EKSİK anahtara dönüşüyor. Kapı depoda olmalı."""
    for lang in i18n.LANGUAGES:
        for anahtar, deger in _yukle(lang).items():
            assert isinstance(deger, str), f"{lang}.json dize değil: {anahtar}"


def test_the_same_variables_appear_in_every_translation_of_a_key():
    """`{adet}` bir dilde varken ötekinde yoksa o dil sayıyı GÖSTERMEZ.

    Ters yön daha da kötü: yalnız çeviride geçen bir `{sure}` çağıran onu
    vermediği için ham `{sure}` olarak ekranda kalır. `i18n.t` bilinmeyen
    değişkeni bilerek silmiyor (sessizlikten iyidir), ama o "bilerek" bir
    kusuru görünür kılmak içindi — kusurun kendisi burada kapanıyor.
    """
    temel = _yukle(i18n.FALLBACK)
    for lang in i18n.LANGUAGES:
        if lang == i18n.FALLBACK:
            continue
        baska = _yukle(lang)
        for anahtar, metin in temel.items():
            if anahtar not in baska:
                continue      # ayrı testin işi
            assert set(i18n._VAR.findall(metin)) == set(
                i18n._VAR.findall(baska[anahtar])), \
                f"{anahtar}: {i18n.FALLBACK} ↔ {lang} değişkenleri ayrışmış"


def test_no_translation_carries_html_markup():
    """`i18n.render` değeri KAÇIRIYOR, yani çeviriye yazılmış bir `<b>` ekranda
    `<b>` olarak GÖRÜNÜR. Bir etiket gerekiyorsa metin iki anahtara bölünür ve
    etiket şablonda kalır (o fonksiyonun docstring'indeki tercih)."""
    etiket = re.compile(r"<[a-zA-Z/!]")
    for lang in i18n.LANGUAGES:
        for anahtar, deger in _yukle(lang).items():
            assert not etiket.search(deger), \
                f"{lang}.json HTML etiketi taşıyor: {anahtar} → {deger!r}"


def test_the_model_layer_mirrors_the_language_list():
    """İki liste ayrışırsa `prefs` kabul ettiği bir dili sözlük tanımaz."""
    assert models.ALLOWED_LANGUAGES == i18n.LANGUAGES


def test_the_fallback_is_a_supported_language():
    assert i18n.FALLBACK in i18n.LANGUAGES


def test_the_default_language_is_english_and_supported():
    """Ön tanımlı dil (v0.22): hiç seçim yapmamış bir kurulum İNGİLİZCE açılır.

    LİTERAL karşılaştırma bilinçli — `i18n.DEFAULT`u kendisiyle kıyaslayan bir
    iddia, değeri değiştirmenin kimseyi uyandırmadığı bir test olurdu. Bu
    satır kırmızıya döndüğünde sorulacak soru "test bayat mı" değil, "bu ürün
    kararı gerçekten değişti mi".
    """
    assert i18n.DEFAULT == "en"
    assert i18n.DEFAULT in i18n.LANGUAGES


def test_the_preference_default_comes_from_the_language_module():
    """`prefs` varsayılanı `i18n.DEFAULT`u İTHAL ediyor, kopyalamıyor.

    İki yer ayrışsaydı "hiç seçim yokken hangi dil" sorusunun biri sunucu
    tarafında biri sözlükte olmak üzere iki cevabı olurdu — `LANGUAGES` ile
    `models.ALLOWED_LANGUAGES` arasındaki aynalamama kuralının aynısı."""
    import prefs
    assert prefs.DEFAULTS["language"] == i18n.DEFAULT


def test_the_client_side_fallback_matches_the_default():
    """`static/i18n.js` sunucusuz açılan bir şablonda kendi yedeğine düşüyor
    ve o değer `i18n.DEFAULT` ile AYNI olmak zorunda: ayrışsalardı aynı
    sayfanın şablon metinleri bir dilde, betiklerin ürettiği cümleler başka
    bir dilde görünürdü."""
    with open(os.path.join(STATIC, "i18n.js"), encoding="utf-8") as f:
        kaynak = f.read()
    assert f'window.KROMIS_LANG || "{i18n.DEFAULT}"' in kaynak, (
        "istemci yedeği i18n.DEFAULT ile ayrışmış")


def test_an_installation_with_no_stored_preference_is_served_in_english(tmp_path, dizinler):
    """UÇTAN UCA kapı: tercih dosyası HİÇ YOKKEN sayfa hangi dilde geliyor?

    Yukarıdaki iki test sabitlerin birbirini tuttuğunu söylüyor; bu, o
    sabitlerin gerçekten sayfaya ULAŞTIĞINI söylüyor — ara katman
    (`services.dil.dil_baglami`) tercihi okumayı bıraksa ötekiler yine yeşil kalırdı.
    """
    dizinler(output_dir=str(tmp_path))
    html = TestClient(appmod.app).get("/").text
    assert '<html lang="en">' in html
    assert 'window.KROMIS_LANG="en"' in html


# ── Çalışma anı davranışı ────────────────────────────────────────────

def test_an_unknown_language_token_falls_back():
    """`normalize` çalışma anındaki son savunma: `prefs` kapısını aşmış
    (ya da hiç ondan geçmemiş — bkz. desktop.py) bir jeton uygulamayı
    dilsiz bırakmamalı."""
    for jeton in ("de", "", None, "tr-TR", "../../etc/passwd"):
        assert i18n.normalize(jeton) == i18n.FALLBACK


def test_a_missing_key_returns_the_key_itself():
    """Sessiz boşluk değil GÖRÜNÜR anahtar: çevrilmemiş bir yüzey fark
    edilebilir olmalı."""
    assert i18n.t("yok.boyle.bir.anahtar", "tr") == "yok.boyle.bir.anahtar"


def test_a_key_missing_in_one_language_falls_back_to_turkish(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "bundled_i18n_dir", lambda: str(tmp_path))
    (tmp_path / "tr.json").write_text(
        json.dumps({"a": "Türkçe", "b": "Yalnız burada"}), encoding="utf-8")
    (tmp_path / "en.json").write_text(
        json.dumps({"a": "English"}), encoding="utf-8")
    i18n._cache.clear()
    assert i18n.t("a", "en") == "English"
    assert i18n.t("b", "en") == "Yalnız burada"
    i18n._cache.clear()


def test_a_corrupt_catalog_does_not_raise(tmp_path, monkeypatch):
    """Kullanıcının makinesindeki bozuk bir dosya uygulamayı kilitlememeli —
    `prefs._read_raw`'un duruşu. Ekranda ham anahtar, açılmayan bir
    uygulamadan iyidir."""
    monkeypatch.setattr(paths, "bundled_i18n_dir", lambda: str(tmp_path))
    (tmp_path / "tr.json").write_text("{ bozuk", encoding="utf-8")
    i18n._cache.clear()
    assert i18n.catalog("tr") == {}
    assert i18n.t("herhangi", "tr") == "herhangi"
    i18n._cache.clear()


def test_a_catalog_edit_is_picked_up_without_a_restart(tmp_path, monkeypatch):
    """Önbellek mtime anahtarlı: `run.sh` ile geliştirirken bir çeviri
    düzeltmesini görmek için sunucuyu yeniden başlatmak gerekmemeli
    (`app.index`in şablonu her istekte diskten okuma gerekçesinin aynısı)."""
    monkeypatch.setattr(paths, "bundled_i18n_dir", lambda: str(tmp_path))
    dosya = tmp_path / "tr.json"
    dosya.write_text(json.dumps({"a": "önce"}), encoding="utf-8")
    i18n._cache.clear()
    assert i18n.t("a", "tr") == "önce"
    dosya.write_text(json.dumps({"a": "sonra"}), encoding="utf-8")
    os.utime(dosya, (0, 0))          # mtime GARANTİLİ değişsin (aynı saniye tuzağı)
    assert i18n.t("a", "tr") == "sonra"
    i18n._cache.clear()


def test_variables_are_substituted_and_unknown_ones_are_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "bundled_i18n_dir", lambda: str(tmp_path))
    (tmp_path / "tr.json").write_text(
        json.dumps({"a": "{adet} görsel, {sure} sn"}), encoding="utf-8")
    i18n._cache.clear()
    assert i18n.t("a", "tr", adet=3, sure=8) == "3 görsel, 8 sn"
    # Eksik argüman SİLİNMİYOR: cümlenin ortasının buharlaşması daha sessiz
    # bir kusur olurdu.
    assert i18n.t("a", "tr", adet=3) == "3 görsel, {sure} sn"
    i18n._cache.clear()


def test_a_value_with_braces_but_no_variables_is_returned_untouched(tmp_path, monkeypatch):
    """Değişkensiz çağrıda `format` HİÇ çalışmıyor — bir JSON ya da CSS örneği
    taşıyan çeviri metni KeyError üretmemeli."""
    monkeypatch.setattr(paths, "bundled_i18n_dir", lambda: str(tmp_path))
    (tmp_path / "tr.json").write_text(
        json.dumps({"a": 'örnek: {"oran": "1:1"}'}), encoding="utf-8")
    i18n._cache.clear()
    assert i18n.t("a", "tr") == 'örnek: {"oran": "1:1"}'
    i18n._cache.clear()


def test_render_escapes_the_value(tmp_path, monkeypatch):
    """Kaçış bir enjeksiyon savunması değil DOĞRULUK meselesi: `&` taşıyan bir
    çeviri kaçışsız yazıldığında tarayıcı onu varlık başlangıcı sanar, `"`
    taşıyan bir çeviri de bir `title="…"` özniteliğini ortasından böler."""
    monkeypatch.setattr(paths, "bundled_i18n_dir", lambda: str(tmp_path))
    (tmp_path / "tr.json").write_text(
        json.dumps({"a": 'Ayarlar & "Dil"'}), encoding="utf-8")
    i18n._cache.clear()
    cikti = i18n.render('<p title="{{t:a}}">{{t:a}}</p>', "tr")
    # Çift tırnak KAÇIRILMIŞ olmalı, yoksa öznitelik ortasından kapanır ve
    # `Dil"` bir ÖZNİTELİK ADI olarak ayrıştırılırdı.
    assert cikti == ('<p title="Ayarlar &amp; &quot;Dil&quot;">'
                     'Ayarlar &amp; &quot;Dil&quot;</p>')
    i18n._cache.clear()


def test_render_leaves_the_apostrophe_alone(tmp_path, monkeypatch):
    """`&#x27;` doğru görünür ama hiçbir şeyi korumaz: Türkçe metin kesme
    işaretiyle dolu ("Medya'dan seç") ve şablondaki her öznitelik ÇİFT
    tırnaklı. Kaçış yalnızca servis edilen HTML'i okunamaz yapardı."""
    monkeypatch.setattr(paths, "bundled_i18n_dir", lambda: str(tmp_path))
    (tmp_path / "tr.json").write_text(
        json.dumps({"a": "Medya'dan seç"}), encoding="utf-8")
    i18n._cache.clear()
    assert i18n.render("<p>{{t:a}}</p>", "tr") == "<p>Medya'dan seç</p>"
    i18n._cache.clear()


def test_no_placeholder_sits_inside_a_single_quoted_attribute():
    """`render`ın kesme işaretini kaçırmama kararı ŞABLONUN tek tırnak
    kullanmamasına dayanıyor. Varsayım umut edilmiyor, ölçülüyor: tek
    tırnaklı bir özniteliğe konmuş yer tutucu, içindeki `'` yüzünden
    özniteliği ortasından kapatırdı."""
    with open(os.path.join(STATIC, "index.html"), encoding="utf-8") as f:
        html_metni = f.read()
    kotu = re.findall(r"=\s*'[^']*\{\{t:", html_metni)
    assert not kotu, f"tek tırnaklı özniteliğe konmuş yer tutucu: {kotu}"


def test_render_leaves_an_unknown_key_visible(tmp_path, monkeypatch):
    """Yer tutucu yer tutucu olarak KALMIYOR, anahtara dönüşüyor: ekranda
    `{{t:…}}` görmek "sunucu çeviriyi hiç çalıştırmadı" demektir ve o AYRI bir
    kusur — ikisini ayırt edebilmek teşhisi kısaltıyor."""
    monkeypatch.setattr(paths, "bundled_i18n_dir", lambda: str(tmp_path))
    (tmp_path / "tr.json").write_text("{}", encoding="utf-8")
    i18n._cache.clear()
    assert i18n.render("<p>{{t:a.b}}</p>", "tr") == "<p>a.b</p>"
    i18n._cache.clear()


def test_the_js_payload_cannot_close_the_script_tag(tmp_path, monkeypatch):
    """Sözlüğün içindeki bir `</script>` HTML ayrıştırıcısını erken kapatır ve
    sayfanın geri kalanı metin olarak ekrana dökülürdü."""
    monkeypatch.setattr(paths, "bundled_i18n_dir", lambda: str(tmp_path))
    (tmp_path / "tr.json").write_text(
        json.dumps({"a": "</script><b>x"}), encoding="utf-8")
    i18n._cache.clear()
    yuk = i18n.js_payload("tr")
    assert "</script>" not in yuk
    assert json.loads(yuk.replace("<\\/", "</"))["a"] == "</script><b>x"
    i18n._cache.clear()


# ── Uçtan uca ────────────────────────────────────────────────────────

def test_the_boot_failure_page_speaks_the_selected_language(monkeypatch, dizinler):
    """Şablon okunamadığında çıkan sayfa da çevriliyor — mekanizmanın uçtan
    uca çalıştığının kanıtı. İngilizce arayüzde Türkçe bir çöküş sayfası,
    kullanıcının "bu uygulama bana mı ait" sorusunu sorduğu an olurdu."""
    # `open` GENELİNE dokunulmuyor, yalnız şablonun DİZİNİ yanlışlanıyor:
    # `builtins.open`ı patlatmak sözlüğü de okunamaz yapar ve test kendi
    # ölçtüğü şeyi (çeviri) ortadan kaldırırdı — sayfa ham anahtar gösterip
    # yeşil kalabilirdi.
    dizinler(static_dir=os.path.join(REPO, "yok-boyle-dizin"))
    monkeypatch.setattr(dil, "aktif", lambda: "en")
    r = TestClient(appmod.app).get("/")
    assert r.status_code == 500
    assert "The interface could not be loaded" in r.text
    assert "Arayüz yüklenemedi" not in r.text


# ── Şablon ↔ katalog ─────────────────────────────────────────────────

def _sablon_anahtarlari():
    """`static/*.html` içindeki `{{t:…}}` anahtarları — HER sayfa (Faz 1 / 3'ten
    beri iki sayfa var: index.html ve giris.html). Yalnız index.html'i tarayan
    hâli giriş sayfasının anahtarlarını "ölü" sanırdı."""
    bulunan = set()
    for ad in sorted(os.listdir(STATIC)):
        if not ad.endswith(".html"):
            continue
        with open(os.path.join(STATIC, ad), encoding="utf-8") as f:
            bulunan |= set(i18n._PLACEHOLDER.findall(f.read()))
    return bulunan


# Anahtar BİÇİMİ: `bolum.ad` — en az bir nokta, küçük harf/rakam/alt çizgi.
# Tarama `t("…")` çağrısı ARAMIYOR, bu biçime uyan HER dizeyi topluyor ve bu
# bilinçli: anahtarların bir kısmı çağrı yerinde değil bir TABLODA duruyor
# (`HARMONY_KEYS`, `MODEL_EKSENLERI`, `MEDYA_TUR_SUZGECLERI` …) ve `t()` onlara
# değişkenle dokunuyor. Yalnız çağrı yerlerini taramak o tabloları "ölü anahtar"
# ilan ederdi.
# Tire de geçerli: model kimlikleri onu taşıyor (`model.gemini-veo-3-1.note`).
_ANAHTAR_BICIMI = re.compile(r'"([a-z][a-z0-9_-]*(?:\.[a-z0-9_.-]+)+)"')

# Şablonla KURULAN anahtar aileleri. `static/folders.js`in
# `MEDYA_TUR_SUZGECLERI` tablosu anahtarın ÖN EKİNİ taşıyor,
# `updateMediaRailCount` da ona `_one` / `_many` ekleyip `tc()`ye veriyor —
# çünkü sayıdan sonra çoğul eki Türkçe'de yok, İngilizce'de var.
#
# Yani taramanın bulduğu `media.images` bir ANAHTAR DEĞİL, iki anahtarın ön
# eki. Liste ELLE ve bu bir eksiklik değil tercih: statik tarama çalışma anını
# okumuyor (`tools/graf_uret.py`nin aynı duruşu) ve muafiyetin ADIYLA
# yazılması, sessizce atlanmasından iyidir.
COGUL_ON_EKLERI = ("media.images", "media.videos", "media.uploads")
DINAMIK_ANAHTARLAR = tuple(
    f"{on}_{ek}" for on in COGUL_ON_EKLERI for ek in ("one", "many"))


def _betik_anahtarlari():
    """`static/*.js` içinde anahtar biçimine uyan dizeler."""
    bulunan = set()
    for ad in sorted(os.listdir(STATIC)):
        if not ad.endswith(".js"):
            continue
        with open(os.path.join(STATIC, ad), encoding="utf-8") as f:
            bulunan |= set(_ANAHTAR_BICIMI.findall(f.read()))
    return bulunan - set(COGUL_ON_EKLERI)


def test_every_template_placeholder_has_a_translation():
    """Şablona yazılmış ama kataloğa yazılmamış bir anahtar ekranda HAM olarak
    görünür (`{{t:rail.studio}}` ↔ `rail.studo`). Yazım hatası kullanıcıya
    varmadan burada düşüyor."""
    for lang in i18n.LANGUAGES:
        eksik = _sablon_anahtarlari() - set(_yukle(lang))
        assert not eksik, f"{lang}.json'da olmayan şablon anahtarı: {sorted(eksik)}"


def test_every_script_key_has_a_translation():
    for lang in i18n.LANGUAGES:
        eksik = (_betik_anahtarlari() | set(DINAMIK_ANAHTARLAR)) - set(_yukle(lang))
        assert not eksik, f"{lang}.json'da olmayan betik anahtarı: {sorted(eksik)}"


def test_no_catalog_key_is_unused():
    """Ölü anahtar, sözlüğü zamanla okunamaz yapar ve çeviren kişiye var
    olmayan bir ekranı tarif eder. Kullanım YERİ iki yerden birinde olmak
    zorunda: şablon ya da betik.

    Sunucu tarafı anahtarlar (`err.*`, `boot.*`, `model.*.note`) bu taramada
    GÖRÜNMEZ — onlar Python'da `i18n.t("…")` ile çağrılıyor, o yüzden kaynak
    olarak `.py` dosyaları da taranıyor.
    """
    py_anahtarlari = set()
    for ad in _urun_modulleri():
        with open(os.path.join(REPO, ad), encoding="utf-8") as f:
            py_anahtarlari |= set(_ANAHTAR_BICIMI.findall(f.read()))
    kullanilan = (_sablon_anahtarlari() | _betik_anahtarlari() | py_anahtarlari
                  | set(DINAMIK_ANAHTARLAR))
    olu = set(_yukle(i18n.FALLBACK)) - kullanilan
    assert not olu, f"hiçbir yerde kullanılmayan anahtar: {sorted(olu)}"


def test_the_served_page_has_no_unsubstituted_translation_placeholder():
    """`test_index_has_no_unsubstituted_placeholder`ın ikizi. Ekranda `{{t:…}}`
    görmek "sunucu çeviriyi hiç çalıştırmadı" demek; ham bir ANAHTAR görmek
    ise "anahtar katalogda yok" demek — ikisi ayrı kusur ve ayrı testleri var."""
    assert "{{t:" not in TestClient(appmod.app).get("/").text


def test_the_page_is_served_in_the_selected_language(monkeypatch):
    monkeypatch.setattr(dil, "aktif", lambda: "en")
    html = TestClient(appmod.app).get("/").text
    assert '<html lang="en">' in html
    assert ">Studio<" in html and ">Stüdyo<" not in html


def test_the_dictionary_is_inlined_for_the_scripts(monkeypatch):
    """Betikler `window.KROMIS_I18N`i ÜST DÜZEYDE okuyabiliyor; bir `fetch`
    dönene kadar beklemek, sıranın başındaki i18n.js'in var olma sebebini
    ortadan kaldırırdı."""
    monkeypatch.setattr(dil, "aktif", lambda: "en")
    html = TestClient(appmod.app).get("/").text
    assert 'window.KROMIS_LANG="en"' in html
    assert "window.KROMIS_I18N={" in html
    # Sözlük betiklerin HEPSİNDEN önce gelmeli.
    assert html.index("window.KROMIS_I18N") < html.index("/static/core.js")


# ── Ayarlar'daki dil seçici ──────────────────────────────────────────

def test_the_language_pane_is_served():
    """Seçici Ayarlar'ın İÇİNDE: kullanıcı onu "dil" diye aradığında bulacağı
    yer orası, tema gibi ayrı bir slide-over değil."""
    html = TestClient(appmod.app).get("/").text
    assert 'data-pane="language"' in html, "dil bölmesi yok"
    assert 'id="language-select"' in html, "dil seçicisi yok"
    for jeton in i18n.LANGUAGES:
        assert f'<option value="{jeton}"' in html, jeton


def test_the_served_list_marks_the_language_the_page_was_drawn_in():
    """Açılır liste sayfanın DİLİNİ gösteriyor, varsayılanı değil.

    Sunucu `selected`i yazmasaydı liste her yüklemede ilk dili gösterirdi ve
    İngilizce arayüzde "Türkçe" yazardı — kullanıcıya, seçiminin kaydedilmediği
    yalanını söyleyen bir ekran.
    """
    for jeton in i18n.LANGUAGES:
        html = i18n.language_options_html(jeton)
        assert f'<option value="{jeton}" selected>' in html, jeton
        assert html.count(" selected") == 1, f"{jeton}: tek işaret olmalı"


def test_adding_a_language_costs_no_template_edit():
    """ÜÇÜNCÜ DİLİN BEDELİ ÖLÇÜLÜYOR: bir katalog dosyası + bir jeton.

    Seçenekler şablonda sabit dursaydı yeni bir dil İKİ dosyaya dokunmak
    olurdu ve birini unutmak sessiz kalırdı — katalog yerinde, seçenek yok.
    Bu test o sessizliği imkânsız kılıyor: liste yalnız sunucudan gelebilir.
    """
    with open(os.path.join(STATIC, "index.html"), encoding="utf-8") as f:
        sablon = f.read()
    assert "__APP_LANG_OPTIONS__" in sablon, "seçenekler sunucudan gelmiyor"
    bolme = sablon[sablon.find('data-pane="language"'):]
    bolme = bolme[:bolme.find("</section>")]
    for jeton in i18n.LANGUAGES:
        assert f'value="{jeton}"' not in bolme, (
            f"{jeton} şablona elle yazılmış — liste iki yerde")


def test_every_language_says_its_own_name():
    """Adı katalogdan GELMEK ZORUNDA: eksikse `t()` anahtarı döndürür ve
    kullanıcı listede "language.native_name" okur."""
    for jeton in i18n.LANGUAGES:
        ad = i18n.language_name(jeton)
        assert ad != "language.native_name", f"{jeton}: kendi adı yazılmamış"
        assert ad.strip() == ad and ad, f"{jeton}: {ad!r}"


def test_the_language_button_is_not_translated():
    """Yanlış dilde kalmış bir kullanıcının GERİ DÖNÜŞ yolu bu düğme.

    Çevrilirse aradığı kelimeyi göremez — yani dil seçicisi, ona en çok
    ihtiyaç duyulan anda bulunamaz olur. Bu yüzden iki katalogda da AYNI değer
    yazılı ve bu test o eşitliğin bekçisi.
    """
    degerler = {_yukle(lang)["settings.nav_language"] for lang in i18n.LANGUAGES}
    assert len(degerler) == 1, f"dil düğmesinin adı dile göre değişiyor: {degerler}"
    tek = degerler.pop()
    assert "Dil" in tek and "Language" in tek, (
        f"düğme iki dilin de sözcüğünü taşımıyor: {tek!r}")


def test_the_language_names_are_written_in_their_own_language():
    """Çeviren bir liste, İngilizce arayüzde Türkçe'yi "Turkish" diye
    gösterirdi — Türkçe konuşan kullanıcı kendi dilini tanımadığı bir adla
    arardı. Bu yüzden ad AKTİF dilden değil, dilin KENDİ kataloğundan geliyor:
    liste hangi dilde çizilirse çizilsin aynı sözcükleri gösteriyor.
    """
    listeler = {jeton: i18n.language_options_html(jeton) for jeton in i18n.LANGUAGES}
    adlar = {jeton: re.findall(r">([^<]+)</option>", html)
             for jeton, html in listeler.items()}
    tek = list(adlar.values())[0]
    assert all(v == tek for v in adlar.values()), (
        f"dil adları arayüz diline göre değişiyor: {adlar}")
    assert "Türkçe" in tek and "English" in tek, f"adlar kendi dillerinde değil: {tek}"


def test_changing_the_language_reloads_the_page():
    """Dili İSTEMCİDE uygulamak ikinci bir çeviri yolu açardı ve iki yol
    zamanla ayrışırdı — arayüzün bir köşesi eski dilde kalırdı. Metinleri
    sunucu çözüyor (`i18n.render`), yani tek doğru yol yeniden istemek."""
    js = TestClient(appmod.app).get("/static/settings.js").text
    govde = js[js.find("async function saveLanguagePref"):]
    govde = govde[:govde.find("\n}")]
    assert '"/api/prefs"' in govde and "language: dil" in govde, "tercih yazılmıyor"
    assert "window.location.reload()" in govde, "sayfa yenilenmiyor"
    assert govde.index('"/api/prefs"') < govde.index("window.location.reload()"), (
        "yenileme yazımdan ÖNCE: başarısız bir yazım kullanıcıyı eski dilde "
        "ve açıklamasız bırakır")


def test_the_language_switch_guards_unsent_text():
    """Yenileme composer'da yazılı metni siler; kullanıcının hiç beklemediği
    bir kayıp olurdu (sendChat'in başarısızlık dalının reddettiği şeyin
    aynısı). Kutu boşken soru sormak ise gereksiz bir tık."""
    js = TestClient(appmod.app).get("/static/settings.js").text
    govde = js[js.find("async function saveLanguagePref"):]
    govde = govde[:govde.find("\n}")]
    assert '$("prompt").value' in govde, "yazılı metin hiç sorulmuyor"
    assert "confirmDialog" in govde, "onay istenmiyor"
    assert "yazili &&" in govde, "kutu boşken de onay isteniyor"


def test_the_picker_reads_the_language_from_the_page_not_the_server():
    """Sunucu sayfayı ZATEN o dille çizdi: ekranda duran metin ile işaretli
    radyo tanım gereği aynı olmak zorunda. Ayrı bir uçtan sormak, ikisinin
    ayrışabildiği bir an açardı (`applyConfigured`ın "aynı yanıttan"
    gerekçesinin aynısı)."""
    js = TestClient(appmod.app).get("/static/settings.js").text
    govde = js[js.find("function syncLanguagePicker"):]
    govde = govde[:govde.find("\n}")]
    assert "KROMIS_DIL" in govde, "seçili dil sayfadan okunmuyor"
    assert "/api/prefs" not in govde, "seçili seçeneği kurmak için ağa çıkılıyor"


# ── Sunucu mesajları ─────────────────────────────────────────────────

def test_a_route_error_speaks_the_selected_language(tmp_path, dizinler, kullanici):
    """Yarım bir çeviri en çok HATA ANINDA göze batar: İngilizce bir arayüzde
    Türkçe bir hata kutusu, kullanıcının "bu uygulama bana mı ait" sorusunu
    sorduğu an olurdu.

    Seçili dil HESABIN dili (Faz 1 / 4, `kullanicilar.dil`; test kullanıcısı
    conftest'in `kullanici` fixture'ı) — `prefs.json`daki `language` web
    yolunda artık okunmuyor."""
    dizinler(output_dir=str(tmp_path / "output"))
    c = TestClient(appmod.app)
    kullanici.dil = "en"
    assert c.delete("/api/image/yokboyle").json()["detail"] == "The image was not found."
    kullanici.dil = "tr"
    assert c.delete("/api/image/yokboyle").json()["detail"] == "Görsel bulunamadı."


def test_a_provider_error_speaks_the_selected_language():
    """Sağlayıcı istemcileri dili PARAMETREYLE almıyor, isteğin bağlamından
    okuyor (`i18n.active()`). Beş kademelik bir imza genişletmesinden kaçınan
    kararın gerçekten çalıştığının kanıtı bu."""
    import azure_client
    i18n.set_active("en")
    try:
        assert "invalid" in azure_client.map_error(401, None)
    finally:
        i18n.set_active(i18n.FALLBACK)
    assert "geçersiz" in azure_client.map_error(401, None)


def test_the_active_language_is_per_request_not_global():
    """`ContextVar` seçimi burada ölçülüyor: iki eşzamanlı isteğin dili
    birbirine SIZAMAZ. Küresel bir değişken olsaydı, dili İngilizce olan bir
    kullanıcının isteği, aynı anda üreten Türkçe kullanıcının hata mesajını
    da çevirirdi."""
    import concurrent.futures

    def calis(dil):
        i18n.set_active(dil)
        return i18n.t("err.not_found")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as havuz:
        sonuc = list(havuz.map(calis, ["en", "tr"]))
    assert sonuc == ["not found", "bulunamadı"]
    # Ana bağlam HİÇ dokunulmadan kaldı: alt bağlamdaki `set` dışarı sızmıyor.
    assert i18n.active() == i18n.FALLBACK


def test_every_model_note_is_a_translation_key():
    """`catalog` DİLSİZ kalmak zorunda: onu on üç modül ithal ediyor ve
    hiçbirinin dille işi yok. Not bir metin olarak kalsaydı katalog tek bir
    dile çakılırdı."""
    import catalog
    for m in catalog.IMAGE_MODELS + catalog.VIDEO_MODELS + catalog.CHAT_MODELS:
        if m.note is None:
            continue
        assert m.note.startswith("model.") and m.note.endswith(".note"), (
            f"{m.id}: not bir çeviri anahtarı değil: {m.note!r}")
        for lang in i18n.LANGUAGES:
            assert m.note in _yukle(lang), f"{m.id}: {lang}.json'da yok"


# ── Belgeler ─────────────────────────────────────────────────────────

def test_the_readmes_no_longer_claim_a_turkish_only_interface():
    """README'nin iddiası ARTIK YANLIŞ olabilir ve bu sessiz bir kusur sınıfı:
    belge, kodun bir turda kazandığı yeteneği yok saymaya devam eder ve
    kullanıcı var olan bir özelliği hiç aramaz.

    İddia İKİ yönlü: eski cümlelerin gitmiş olması yetmez, yeni yeteneğin
    ADIYLA yazılı olması da gerekiyor — yoksa cümleyi silmek de testi
    yeşile döndürürdü.
    """
    en = open(os.path.join(REPO, "README.en.md"), encoding="utf-8").read()
    assert "The interface is Turkish only" not in en, (
        "README.en hâlâ arayüzün yalnız Türkçe olduğunu söylüyor")
    assert "Dil / Language" in en, "dil anahtarının nerede olduğu yazılı değil"

    tr_readme = open(os.path.join(REPO, "README.md"), encoding="utf-8").read()
    assert "Fikri Türkçe anlat" not in tr_readme, (
        "README hâlâ Yönetmen'e Türkçe yazmayı şart koşuyor")
    assert "Dil / Language" in tr_readme, "dil anahtarının nerede olduğu yazılı değil"


def test_the_readmes_still_explain_why_the_prompt_is_english():
    """İngilizce prompt kuralı KALKMADI ve kalkmamalı: o bir dil tercihi
    değil, görsel modellerinin ölçülmüş davranışı. Sebebi yazılı olmazsa
    kullanıcı onu bir eksiklik sanar ve "neden Türkçe yazmıyor" diye sorar."""
    for ad in ("README.md", "README.en.md"):
        metin = open(os.path.join(REPO, ad), encoding="utf-8").read()
        assert "İngilizce" in metin or "English" in metin, ad
        assert ("ölçülmüş" in metin or "measured" in metin), (
            f"{ad}: İngilizce prompt kuralının GEREKÇESİ yazılı değil")


# ── Kaçan Türkçe metin ───────────────────────────────────────────────

# Kullanıcıya METİN döndüren modüller. Liste ELLE tutuluyor ve bu bilinçli:
# "hangi modül kullanıcıya konuşuyor" sorusunun mekanik bir cevabı yok (bir
# `ValueError` kimi yerde 422 gövdesi, kimi yerde iç değişmez), yani otomatik
# bir ölçüt ya gürültü üretir ya da yanlış susar. Yeni bir modül metin
# döndürmeye başladığında buraya bir satır eklemek, o kararı GÖRÜNÜR yapıyor.
#
# ELLE ama EKSİKSİZ: aşağıdaki ikiz listeyle birlikte depodaki HER kök modülü
# kapsamak zorunda (`test_every_shipped_module_is_classified`). Liste tek
# başınayken yeni bir modülün öntanımlı hâli "muaf"tı ve `fal_client.py` tam
# oradan kaçtı.
# Ürün kodunun DİZİNLERİ: kök + Faz 0 / Adım 2'de doğan iki paket. `tools/`
# ve `tests/` bilerek dışarıda (gerekçesi test_every_shipped_module_is_classified'da).
# Hem sınıflandırma kapısı hem anahtar taraması bu listeyi kullanıyor: `app.py`
# bölündüğünde `i18n.t("err.…")` çağrıları `routers/` altına taşındı ve yalnız
# kökü tarayan bir `test_no_catalog_key_is_unused` her hata anahtarını "ölü"
# sanırdı.
URUN_PAKETLERI = ("routers", "services")


def _urun_modulleri() -> list[str]:
    """Kök ve paket altındaki ürün `.py` dosyaları, depo göreli yolla."""
    yollar = [ad for ad in sorted(os.listdir(REPO)) if ad.endswith(".py")]
    for paket in URUN_PAKETLERI:
        yollar += [f"{paket}/{ad}" for ad in sorted(os.listdir(os.path.join(REPO, paket)))
                   if ad.endswith(".py")]
    return yollar


KULLANICIYA_KONUSAN = (
    "android_main.py", "assets_store.py", "azure_client.py",
    "azure_flux_client.py", "azure_mai_client.py", "catalog.py",
    "chat_client.py", "chat_providers.py", "color_names.py", "composite.py",
    "credstore.py", "etiket.py", "fal_client.py", "folders.py",
    "gemini_client.py", "models.py", "netguard.py", "openai_chat.py",
    "openai_client.py", "palette.py", "prefs.py", "providers.py",
    "storage.py", "veo_client.py",
    # Rotalar: `app.py`nin HTTPException metinleri buraya taşındı (Adım 2).
    "routers/ayarlar.py", "routers/bindirme.py", "routers/galeri.py",
    "routers/hesap.py", "routers/paletler.py", "routers/sohbet.py",
    "routers/uretim.py",
    # Faz 2 / 4: iş uçları — 404/409/422 metinleri (`err.is_*`, `err.bad_since`).
    "routers/isler.py",
    # Faz 2 / 8: admin uçları — 404/409/422 metinleri (`err.kullanici_bulunamadi`, `err.is_durumu_gecersiz`).
    "routers/admin.py",
    # Rota dışı ama kullanıcıya 4xx gövdesi üreten yardımcılar.
    "services/gorsel.py", "services/kapilar.py", "services/modeller.py",
    "services/palet.py",
    # Faz 2 / 6: kota kapıları — 429 gövdesi (`err.saatlik_is_tavani`, `err.gunluk_kredi_tavani`).
    "services/kota.py",
    # Faz 1 / 3: kimlik kapısının 401 metni, e-posta gövdeleri, sayfa şablonunun
    # 500 metni (`boot.load_failed.*` — `routers/kok.py`den buraya taşındı).
    "services/kimlik.py", "services/posta.py", "services/sablon.py",
    # Faz 2 / 3: işçi `hata` sütununa KULLANICIYA gösterilecek metni yazar —
    # sağlayıcı hatasını aynen (adaptör zaten çevirmiş) ve eksik girdi nesnesi
    # için rotanın 404 metnini (`err.source_image_missing`), kullanıcının dilinde.
    "services/isci.py",
)

# …ve kullanıcıya KONUŞMAYANLAR, her biri gerekçesiyle. Bu liste bir muafiyet
# defteri: "taranmasın" demiyor, "burada taranacak bir şey YOK, sebebi şu"
# diyor. Listedeki bir modül kullanıcıya konuşmaya başlarsa satırı yukarıya
# taşınmalı — ve o an bu dosyayı okuyan birinin bakacağı tek yer burası.
KULLANICIYA_KONUSMAYAN = {
    "app.py": "bileşim kökü (Faz 0 / Adım 2): FastAPI kurulumu, router "
              "takma, mount — metin üreten her satır routers/ ve services/ altında",
    "backup.py": "yedek dizini adı üretimi; tek Türkçe satırı imkânsız bir "
                 "durumun `ValueError`'ı",
    "chat_prompt.py": "metin MODELE gidiyor, ekrana değil — Yönetmen "
                      "personası; `models.result_note` ile aynı sınıf",
    "chat_store.py": "sohbet kayıt katmanı; dışarıya veri döndürüyor, cümle değil",
    "desktop.py": "Türkçe satırları konsola basılan önyükleme dökümü; "
                  "geliştiriciye gidiyor",
    "errlog.py": "tanı günlüğü; dosyaya yazıyor, ekrana değil",
    "guncelleme.py": "sürüm verisi ve `DURUM_*` KODLARI döndürüyor; o kodları "
                     "cümleye çeviren yer ön yüz",
    "i18n.py": "çeviri mekanizmasının KENDİSİ; metni sözlük taşıyor",
    "jsonstore.py": "atomik JSON yazımı; metin üretmiyor",
    "palette_store.py": "palet kayıt katmanı; metin üretmiyor",
    "paths.py": "yol hesabı; tek Türkçe satırı `errlog`a gidiyor",
    "release_manifest.py": "yayın manifesti; makine okuyor",
    "screencolor.py": "damlalık köprüsü (yalnız `desktop.py` ithal ediyor); "
                      "tek Türkçe satırı AppKit renk uzayı iç değişmezi",
    "version.py": "sürüm literalleri",
    "winclr.py": ".NET köprüsünün önyükleme dökümü; konsola basılıyor",
    "winsec.py": "Windows ACL sarmalı; Türkçe satırları platform iç değişmezleri",
    "routers/__init__.py": "yalnız paket docstring'i",
    "routers/saglik.py": "sağlık sondası (`/health`): makine okuyan JSON — ok/version/"
                         "data_dir_writable; cümle yok, okuyucu HEALTHCHECK/orkestratör",
    "services/__init__.py": "yalnız paket docstring'i",
    "services/dil.py": "dil bağlamını KURAN ara katman; metni okumuyor, seçiyor",
    "services/redaksiyon.py": "422 gövdesinden gizli değeri SİLİYOR; cümle üretmiyor",
    "services/ayar.py": "veri dizinlerinin ayar nesnesi ve `Depends` işlevi; metin yok",
    "services/db.py": "veri tabanı motoru ve `Session` bağımlılığı (Faz 1 / 1); tek 503 "
                      "`detail`i bir KOD (`database_unavailable`), cümleyi ön yüz kurar",
    "services/zaman.py": "zaman damgası biçimi; metin yok",
    "services/platform_anahtari.py": "platform anahtarı birleştirmesi (Faz 2 / 6): ortam okur, sözlük "
                                     "döndürür; tek metni OPERATÖRE giden bir günlük uyarısı "
                                     "(bilinmeyen `KROMIS_PLATFORM_X`), cümleyi kullanıcıya rota kurar",
    "services/depo_medya.py": "medya deposu (Faz 1 / 5): SQL ve dosya; kullanıcıya konuşmaz, "
                              "404'ü rota kurar",
    "services/depo_klasor.py": "klasör deposu (Faz 1 / 5): `folders.export_zip`in i18n'li "
                               "ValueError'ı yerine None döner, metni rota kurar",
    "services/depo_sohbet.py": "sohbet deposu (Faz 1 / 6): SQL; veri döndürür, 404'ü rota kurar",
    "services/depo_palet.py": "palet deposu (Faz 1 / 6): SQL; veri döndürür, cümle değil",
    "services/depo_admin.py": "admin deposu (Faz 2 / 8): SQL; sözlük döndürür, 404/409 metnini rota kurar",
    "services/gunluk.py": "yapısal günlük (Faz 2 / 8-9): `kromis.*` günlükçülerine stdout işleyicisi, "
                          "JSON satır biçimleyici, bağlam; satırlar operatöre gider",
    "services/istek_kimligi.py": "istek kimliği ara katmanı (Faz 2 / 9): `X-Request-ID` ve erişim "
                                 "satırı; başlık adı ve günlük alanları ASCII, cümle yok",
    "services/hata_izleme.py": "Sentry kurulumu (Faz 2 / 9): tek metni OPERATÖRE giden kurulum "
                               "hatası satırı; kullanıcıya hiçbir şey göstermez",
    "services/depo_varlik.py": "varlık deposu (Faz 1 / 6): SQL ve dosya; kullanıcıya konuşmaz",
    "services/dosya.py": "dosya deposu soyutlaması (Faz 2 / 2): yerel disk / kova; hataları "
                         "kod (`DosyaHatasi`), 404 metnini rota kurar",
    "services/nesne_depo.py": "S3/R2 istemcisi (Faz 2 / 2): SigV4 ve HTTP; hata mesajı "
                              "OPERATÖRE (yöntem + durum kodu), arayüze cümle yok",
    "services/depo_tercih.py": "tercih deposu (Faz 1 / 6): `prefs.update`in i18n'li ValueError'ı "
                               "yerine ANAHTAR taşıyan `GecersizTercih`, cümleyi rota kurar",
    "services/tablolar.py": "veri modeli (Faz 1 / 2): tablo, sütun, kısıt tanımları; metin yok — "
                            "CHECK değer kümeleri bile kodun sabitleri, cümle değil",
    "routers/kok.py": "`/` rotası; yerleştirme ve 500 metni `services/sablon.py`ye "
                      "taşındı (Faz 1 / 3), burada yalnız çağrı kaldı",
    "services/cerez.py": "çerez adı ve bayrakları (Faz 1 / 3); metin yok",
    "services/sifre.py": "şifreleme (Faz 1 / 7): hataları OPERATÖRE gidiyor (uvicorn günlüğü, "
                         "`hata.log`), kullanıcıya değil — anahtar yokken uygulama hiç açılmıyor",
    "services/depo_kimlik_bilgisi.py": "sağlayıcı kimlik deposu (Faz 1 / 7): SQL ve şifreleme; "
                                       "değer döndürür, cümle rotanın (`routers/ayarlar.py`)",
    "kimlik_baglami.py": "isteğin kimlik sözlüğünün ContextVar'ı (Faz 1 / 7); metin yok",
    "services/kiraci.py": "kiracı bağlamının ContextVar'ı ve `set_config` ifadesi (Faz 2 / 7); "
                          "metin yok",
    "services/koken.py": "köken kapısı (Faz 1 / 3): 403 gövdesi bir KOD "
                         "(`cross_origin_rejected`) — dil ara katmanından ÖNCE koşuyor, "
                         "cümle kuramaz; `services/db.py` ile aynı karar",
    "services/hesap.py": "hesap katmanı (Faz 1 / 3): özet, oturum, jeton, sayaç — "
                         "`None`/`bool`/sayı döndürüyor, cümleyi routers/hesap.py kuruyor",
    "services/kuyruk.py": "iş kuyruğu ilkelleri (Faz 2 / 1): SQL; satır/`bool`/sayı döndürür, "
                          "`hata` sütununa yazdığı `isci yanit vermiyor` bir KOD, cümleyi ön yüz kurar",
    "services/defter.py": "kredi defteri (Faz 3 / 1): SQL; `Hareket`/`bool`/sayı döndürür, `YetersizBakiye` "
                          "iki SAYI taşır (402 gövdesini rota kurar, K11); tek metni OPERATÖRE giden "
                          "`defter.asim` günlük uyarısı",
    "services/planlar.py": "plan kataloğu (Faz 3 / 3, K5): üç `Plan` sabiti ve `kapsiyor` bool'u; 403 "
                           "gövdesini `kapilar.check_plan` (kod), rozeti ön yüz `sebep` alanından kurar; tek "
                           "metni OPERATÖRE giden `KROMIS_FREE_AYLIK_HIBE` `ValueError`ı",
    "services/filigran.py": "filigran bindirme (Faz 3 / 4, K7): bayt → bayt; istisnaları (`FiligranDosyasiYok`, "
                            "`GorselIslenemedi`) işçi `hata` sütununa TÜR ADIYLA kod olarak yazar, cümleyi ön yüz "
                            "kurar; `to_png`ün 422 gövdesi taşınmaz, yalnız sınıfı",
    # Faz 4 / 3: okuyucu Polar'ın sunucusu ve sahibin admin sekmesi — cümle yok, ASCII kod.
    "services/polar.py": "Polar sarmalı (Faz 4 / 3): ortam, imza doğrulama, SDK istemcisi; istisnaları "
                         "KOD taşır (`ImzaHatasi`), 400/503 gövdesini rota kurar",
    "services/odeme.py": "Polar olay işleme (Faz 4 / 3): defter/plan yazar, `Sonuc(durum, hata)` ASCII "
                         "kod döndürür — okuyucu Polar'ın teslimat günlüğü ve admin sekmesi",
    "routers/odeme.py": "`POST /api/odeme/webhook` (Faz 4 / 3): istemci Polar'ın sunucusu, `detail` "
                        "değerleri KOD (`imza_gecersiz`), dil bağlamı anlamsız",
    "services/disa_aktar.py": "veri dışa aktarma arşivi (Faz 4 / 5): depo işlevlerini JSON/CSV'ye döker; "
                              "dosya adları ve sütun başlıkları ASCII kimlik, 429/404 cümlesini rota kurar",
    "services/saglayici_meta.py": "sağlayıcı meta verisinin ContextVar yan kanalı (Faz 3 / 5, K8): "
                                  "adaptörden işçiye `usage`/`request_id` taşır; metin yok, `kimlik_baglami`nın ikizi",
    "isci.py": "işçi sürecinin bileşim kökü (Faz 2 / 3): kapılar, iş parçacıkları, kalp "
               "atışı, SIGTERM; çıktısı stdout'a ASCII, OPERATÖRE — işin metni services/isci.py'de",
}

# Türkçe kalması KARAR olan dizeler — gerekçesiyle. Muafiyet DİZE düzeyinde,
# dosya düzeyinde DEĞİL: bir dosyayı bütünüyle muaf tutmak, o dosyaya bir gün
# eklenen gerçek bir arayüz metnini de sessizce muaf tutardı.
TURKCE_KALANLAR = {
    # `models.result_note` TELE yazıyor, ekrana değil: Prompt Yönetmeni'nin
    # döküm bağlamı. Persona Türkçe, yani bu metinlerin dili modelin okuduğu
    # dille aynı olmak zorunda — arayüz diliyle değil.
    "[üretim]": "yönetmenin döküm bağlamı (models.result_note)",
    "görsel": "yönetmenin döküm bağlamı (models.result_note)",
    "düzenlendi": "yönetmenin döküm bağlamı (models.result_note)",
    "üretildi": "yönetmenin döküm bağlamı (models.result_note)",
    # `fal_client.TelBicimi.__post_init__` İTHAL ZAMANINDA patlıyor ve metni
    # GELİŞTİRİCİYE gidiyor: tablo kendi içinde tutarsızsa (görsel alanı,
    # görsel kümesinde yok) uygulama hiç açılmıyor, yani bu cümleyi bir
    # kullanıcı ekranda göremez. Çevirmek, `i18n`i katalog-öncesi bir ithal
    # zincirine sokmak olurdu.
    " gorsel kümesinde yok: ": "fal_client'ın ithal-zamanlı tablo denetimi",
    # `netguard._REDDEDILDI` ve Android ikizi İKİ DİLLİ — çevrilmedikleri için
    # değil, ÇEVRİLEMEDİKLERİ için: gövde ASGI sarmalından çıkıyor, FastAPI
    # yığınına hiç girmiyor ve `app._dil_baglami` koşmadığı için `i18n.active()`
    # her zaman yedek dile düşerdi. Ayarlar'daki dil düğmesiyle aynı çözüm.
    "Bu sunucuya yalnızca uygulamanın kendi penceresi erişebilir. / "
    "Only this app's own window can reach this server.":
        "dil bağlamı ÖNCESİ 403 gövdesi (netguard)",
    "Bu sunucuya yalnızca uygulama erişebilir. / "
    "Only this app can reach this server.":
        "dil bağlamı ÖNCESİ 403 gövdesi (android_main)",
    # Kotlin tarafı `filesDir`i vermezse uygulama HİÇ açılmıyor; metin gömülü
    # köprüyü yazan geliştiriciye gidiyor, ekrana değil.
    "data_dir boş olamaz (Kotlin tarafı filesDir'i vermeli)":
        "android_main'in açılış değişmezi",
}


def _turkce_sabitler(kaynak: str) -> list[tuple[int, str]]:
    """Docstring OLMAYAN, Türkçe harf taşıyan dize sabitleri.

    Docstring'ler ve yorumlar DIŞARIDA: bu deponun yazı geleneği onların
    Türkçe olmasını ŞART koşuyor (CLAUDE.md §5). Aranan şey kullanıcıya
    giden metin, geliştiriciye giden metin değil.
    """
    agac = ast.parse(kaynak)
    docstringler = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef)):
            ilk = dugum.body[0] if dugum.body else None
            if (isinstance(ilk, ast.Expr) and isinstance(ilk.value, ast.Constant)
                    and isinstance(ilk.value.value, str)):
                docstringler.add(id(ilk.value))
    return [(d.lineno, d.value) for d in ast.walk(agac)
            if isinstance(d, ast.Constant) and isinstance(d.value, str)
            and id(d) not in docstringler and _TURKCE_HARF.search(d.value)]


_TURKCE_HARF = re.compile(r"[şğıİŞĞÇçÖöÜü]")


def test_no_user_facing_module_still_carries_turkish_text():
    """ÖLÇÜLEN KUSUR: çeviriden KAÇMIŞ bir cümle.

    İlk turda `app.py`nin `HTTPException` metinleri ve sekiz `map_error`
    çevrildi, ama aynı kullanıcıya konuşan `models.py` doğrulayıcıları,
    `credstore.py` kurulum uyarıları ve `catalog.py` kalite etiketleri
    çevrilmeden kaldı — yani İngilizce arayüzde "Orta", "kredi" ve
    "Azure OpenAI · görsel" yazıyordu. Kaçış SESSİZDİ çünkü Türkçe arayüzde
    her şey doğru görünüyor; kusur yalnız öteki dilde var.

    Bu test o sessizliği kapatıyor: kullanıcıya konuşan bir modüle Türkçe bir
    cümle yazmak artık ya çeviriyi ya da `TURKCE_KALANLAR`a gerekçeli bir
    satırı gerektiriyor.
    """
    kacanlar = []
    for ad in KULLANICIYA_KONUSAN:
        yol = os.path.join(REPO, ad)
        assert os.path.exists(yol), f"{ad} listede ama dosya yok"
        with open(yol, encoding="utf-8") as f:
            for satir, deger in _turkce_sabitler(f.read()):
                if deger not in TURKCE_KALANLAR:
                    kacanlar.append(f"{ad}:{satir}: {deger!r}")
    assert not kacanlar, (
        "çevrilmemiş kullanıcı metni (ya `i18n.t` ya da gerekçeli muafiyet):\n"
        + "\n".join(kacanlar))


def test_the_exemption_list_has_no_dead_entry():
    """Muafiyet bir KARAR kaydı; kaydı kalan ama dizesi silinmiş bir satır,
    okuyana var olmayan bir kararı anlatır. `test_no_catalog_key_is_unused`
    ile aynı disiplin."""
    bulunan = set()
    for ad in KULLANICIYA_KONUSAN:
        with open(os.path.join(REPO, ad), encoding="utf-8") as f:
            bulunan |= {d for _, d in _turkce_sabitler(f.read())}
    olu = set(TURKCE_KALANLAR) - bulunan
    assert not olu, f"artık var olmayan dizeler muaf tutuluyor: {sorted(olu)}"


# ── Kapının KAPSAMI ──────────────────────────────────────────────────

def test_every_shipped_module_is_classified():
    """ÖLÇÜLEN KUSUR: yeni bir modül kapıya HİÇ GİRMEDEN geçti.

    `fal_client.py` v0.23'te geldi, on altı çevrilmemiş Türkçe cümle taşıdı ve
    yukarıdaki tarama onu hiç görmedi — çünkü `KULLANICIYA_KONUSAN` bir
    ALLOWLIST'ti ve listede olmayan dosya taranmıyordu. Kapının öntanımlı
    cevabı "muaf"tı; yön yanlıştı. Aynı turda `tests/test_telif_basligi.py`
    aynı dosyayı İLK GÜN yakaladı, çünkü onun kapsamı `git ls-files`ten
    TÜRETİLİYOR ve üstünde bir de "kapsam gerçekten doluyor mu" bekçisi var.

    LİSTE NEDEN KALKMIYOR: mekanik bir ölçütle değiştirmek ÖLÇÜLDÜ ve pahalı.
    Kapsam dışındaki 18 modülde 73 Türkçe dize vardı ve neredeyse hepsi
    geliştiriciye gidiyor (`desktop`/`winclr` önyükleme dökümü, `errlog`
    satırları, iç değişmezler, `chat_prompt`in persona metni). Hepsini muaf
    saymak muafiyet listesini okunamaz yapardı. Yani doğru araç liste;
    düzeltilen şey YÖNÜ: artık her kök modül iki listeden birinde olmak
    zorunda ve yeni bir modül, hangisi olduğuna karar verilene kadar takımı
    kırmızı tutuyor.

    `tools/` kapsam dışı ve bilinçli: geliştirici betikleri, pakete girmiyor
    ve kullanıcıya konuşan bir yüzleri yok (telif kapısının `tests/` için
    verdiği kararın aynısı). `routers/` ve `services/` İÇERİDE (Faz 0 /
    Adım 2): rotaların metni artık orada yaşıyor ve yalnız kökü sayan bir
    kapı, `fal_client.py`nin kaçtığı deliği paket düzeyinde yeniden açardı.
    """
    izlenen = subprocess.run(["git", "-C", REPO, "ls-files", "*.py"],
                             check=True, capture_output=True, text=True).stdout
    kok = {y for y in izlenen.split()
           if "/" not in y or y.startswith(tuple(f"{p}/" for p in URUN_PAKETLERI))}
    # Bekçinin bekçisi: kalıp bir gün hiçbir şey döndürmezse iki liste de
    # "eksiksiz" görünürdü (test_telif_basligi.py'deki aynı duruş).
    assert len(kok) > 30, f"kapsam şüpheli biçimde küçük: {len(kok)}"

    siniflanan = set(KULLANICIYA_KONUSAN) | set(KULLANICIYA_KONUSMAYAN)
    assert not kok - siniflanan, (
        "SINIFLANMAMIŞ modül. Kullanıcıya metin döndürüyorsa "
        "`KULLANICIYA_KONUSAN`a, döndürmüyorsa GEREKÇESİYLE "
        f"`KULLANICIYA_KONUSMAYAN`a ekle: {sorted(kok - siniflanan)}")
    assert not siniflanan - kok, (
        f"artık var olmayan dosya sınıflanıyor: {sorted(siniflanan - kok)}")
    ikisinde = set(KULLANICIYA_KONUSAN) & set(KULLANICIYA_KONUSMAYAN)
    assert not ikisinde, f"iki listede birden: {sorted(ikisinde)}"


def test_no_module_is_excused_without_a_reason():
    """Gerekçesiz muafiyet, muafiyet değil KÖR NOKTA: kararın NEDEN verildiğini
    söylemeyen satır, o kararı gözden geçirilemez yapar."""
    for ad, gerekce in KULLANICIYA_KONUSMAYAN.items():
        assert gerekce.strip(), f"{ad}: gerekçe yazılmamış"
