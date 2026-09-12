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
import json
import os
import re

from fastapi.testclient import TestClient

import app as appmod
import i18n
import models
import paths

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

def test_the_boot_failure_page_speaks_the_selected_language(monkeypatch):
    """Şablon okunamadığında çıkan sayfa da çevriliyor — mekanizmanın uçtan
    uca çalıştığının kanıtı. İngilizce arayüzde Türkçe bir çöküş sayfası,
    kullanıcının "bu uygulama bana mı ait" sorusunu sorduğu an olurdu."""
    # `open` GENELİNE dokunulmuyor, yalnız şablonun DİZİNİ yanlışlanıyor:
    # `builtins.open`ı patlatmak sözlüğü de okunamaz yapar ve test kendi
    # ölçtüğü şeyi (çeviri) ortadan kaldırırdı — sayfa ham anahtar gösterip
    # yeşil kalabilirdi.
    monkeypatch.setattr(appmod, "STATIC_DIR", os.path.join(REPO, "yok-boyle-dizin"))
    monkeypatch.setattr(appmod, "_dil", lambda: "en")
    r = TestClient(appmod.app).get("/")
    assert r.status_code == 500
    assert "The interface could not be loaded" in r.text
    assert "Arayüz yüklenemedi" not in r.text
