"""Sağlayıcı işaretleri (model şeridindeki logolar) sözleşmesi.

Bu dosyanın varlık sebebi `test_fonts.py`'nin aynısı: **logo kusurları
SESSİZ.** Eksik bir dosya kırık bir `<img>` bırakır (Chromium konsolda 404
yazar, kullanıcı hiçbir şey görmez), yeni bir sağlayıcı eklenip eşlemeye
yazılmazsa şerit işaretsiz çizilir ve kimse fark etmez. Çalışma zamanı bunu
BİLEREK sessiz geçiyor (`catalog.provider_logo` None dönüyor, bir logo
eksikliği üretimi engellemez) — o yüzden sesi buradan çıkıyor.
"""
import re
import xml.dom.minidom
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as appmod
import catalog
import chat_providers
import providers
import version

STATIC = Path(appmod.app.state.ayarlar.static_dir)
LOGOS = STATIC / "img" / "providers"


def _istemci() -> TestClient:
    return TestClient(appmod.app)


def test_logo_dosyalari_gercek_svg():
    """Dosyalar depoda ve gerçekten SVG (LFS işaretçisi ya da hata sayfası değil)."""
    for ad in catalog.PROVIDER_LOGOS.values():
        p = LOGOS / ad
        assert p.exists(), f"{ad} yok — katalogda yazılı ama dosya gelmemiş"
        metin = p.read_text(encoding="utf-8")
        assert "<svg" in metin and "</svg>" in metin, f"{ad} SVG değil"
        assert "viewBox=" in metin, f"{ad} viewBox taşımıyor — CSS ölçüsü çözülemez"


def test_isaretler_GECERLI_XML_ve_ICSEL_boyutlu():
    """Ölçülmüş bir sessiz kusurun mandalı — ve bu dosyanın en pahalı dersi.

    İlk yazımda dosyaların başındaki gerekçe notu `--fg` yazıyordu. XML
    yorumlarında **çift tire yasak**, yani dosya geçerli XML olmaktan çıktı:
    sunucu 200 döndürdü, `img.complete` `true` oldu, `<img>`in CSS kutusu 14×14
    ölçüldü — ve tarayıcı HİÇBİR ŞEY çizmedi. Ne konsolda hata vardı ne de
    ağda; `naturalWidth === 0` ve boyanan piksellerin hepsinin panel arka planı
    olması dışında hiçbir izi yoktu.

    `width`/`height` da şart: içsel boyutu olmayan bir SVG `<img>` içinde
    motora göre 0×0 çözülebiliyor. `viewBox` tek başına CSS ölçüsüyle çalışsa
    bile, içsel boyut `naturalWidth`i anlamlı kılıyor — yani bu iddianın
    ölçebileceği bir şey bırakıyor.
    """
    for ad in catalog.PROVIDER_LOGOS.values():
        yol = LOGOS / ad
        try:
            xml.dom.minidom.parse(str(yol))
        except Exception as e:                      # pragma: no cover - mesaj için
            raise AssertionError(
                f"{ad} geçerli XML değil ({e}) — tarayıcı 200 alır ve HİÇBİR ŞEY "
                "çizmez. En sık sebep: yorum içinde çift tire.") from None
        metin = yol.read_text(encoding="utf-8")
        kok = re.search(r"<svg[^>]*>", metin).group(0)
        assert "width=" in kok and "height=" in kok, (
            f"{ad} içsel boyut taşımıyor — <img> içinde 0×0 çözülebilir")


def test_ADAPTORU_OLAN_her_saglayicinin_isareti_var():
    """Asıl mandal bu: adaptörü olan bir sağlayıcı işaretsiz kalamaz.

    Yeni bir adaptör eklemek (bir `_ADAPTERS` girdisi) katalogda bir model
    demek, model de şeritte bir satır. Eşleme elle tutulduğu için o gün
    unutulan tek şey işaret olur ve kimse fark etmez — bu iddia o günü
    kırmızıya çeviriyor.
    """
    adaptorlu = providers.adapter_ids() | chat_providers.adapter_ids()
    eksik = {p for p in adaptorlu if not catalog.provider_logo(p)}
    assert not eksik, (
        "adaptörü olup işareti olmayan sağlayıcı: " + ", ".join(sorted(eksik))
        + ". catalog.PROVIDER_LOGOS'a bir satır ve "
          "static/img/providers/ altına bir SVG gerekiyor.")


def test_eslemede_KARSILIGI_OLMAYAN_dosya_yok():
    """Ters yön: katalogda yazmayan bir dosya ölü ağırlıktır (pakete giriyor)."""
    diskte = {p.name for p in LOGOS.glob("*.svg")}
    fazla = diskte - set(catalog.PROVIDER_LOGOS.values())
    assert not fazla, (
        "katalogda karşılığı olmayan işaret dosyası: " + ", ".join(sorted(fazla)))


def test_isaretler_TEK_RENK_ve_sabit_renkli():
    """`<img>` içeriği sayfanın rengini MİRAS ALMAZ — `currentColor` işlemez.

    Dosya `<img src>` ile yükleniyor, satır içine gömülmüyor (sunucudan gelen
    hiçbir şey `innerHTML`e girmiyor). O yüzden renk dosyanın İÇİNDE sabit
    olmak zorunda; `currentColor` kullanılırsa işaret siyah çizilir ve koyu
    zeminde kaybolur.
    """
    for ad in catalog.PROVIDER_LOGOS.values():
        # Yorumlar DIŞARIDA: dosyaların başındaki gerekçe notu kelimenin
        # kendisini içeriyor ve iddia işaretlemeyi ölçüyor, yorumu değil.
        metin = re.sub(r"<!--.*?-->", "", (LOGOS / ad).read_text(encoding="utf-8"),
                       flags=re.S)
        assert "currentColor" not in metin, (
            f"{ad} `currentColor` kullanıyor — <img> ile yüklenen SVG'de işlemez")
        assert "#e8eaed" in metin, (
            f"{ad} `--fg` (#e8eaed) rengini taşımıyor — dört koyu temada da "
            "okunan tek varyant o")


def test_dosyalar_STATIC_altinda_servis_ediliyor():
    """Paketleme payı: `static/` dizini spec'e bütün olarak giriyor, yani
    doğru yerdeki bir dosya masaüstü paketinde de telefonda da açılıyor."""
    c = _istemci()
    for ad in catalog.PROVIDER_LOGOS.values():
        r = c.get(f"/static/img/providers/{ad}")
        assert r.status_code == 200, f"{ad} servis edilmiyor"
        assert "svg" in r.headers["content-type"], r.headers["content-type"]


@pytest.mark.usefixtures("depo_db")   # `/api/settings` tercih satırını okuyor (Faz 1 / 6)
def test_API_her_modelde_isaret_ADRESI_donduruyor():
    """Adresi SUNUCU kuruyor: istemcide sağlayıcı adı sayılmıyor, dize
    birleştirilmiyor. `?v=` cache-buster'ı `index()`in tek deseninden geliyor —
    işaretin çizimi değişirse tarayıcı eski dosyayı sunmasın."""
    s = _istemci().get("/api/settings").json()
    for anahtar in ("image_models", "chat_models"):
        assert s[anahtar], f"{anahtar} boş — katalog gelmedi"
        for m in s[anahtar]:
            assert "logo" in m, f"{anahtar}[{m['id']}] `logo` alanı taşımıyor"
            assert m["logo"], f"{m['id']} işaretsiz döndü"
            assert m["logo"].startswith("/static/img/providers/"), m["logo"]
            assert m["logo"].endswith(f"?v={version.APP_VERSION}"), (
                f"{m['id']} işaret adresi sürüm damgası taşımıyor: {m['logo']}")


def test_ISARETSIZ_saglayici_sessizce_gecilir():
    """Katalogda olmayan bir sağlayıcı None döndürüyor, istisna YÜKSELTMİYOR.

    Sessizlik burada bilinçli: bir logo eksikliği üretimi engellememeli.
    Yüksek sesle söyleyen yer bu dosyanın ikinci iddiası.
    """
    assert catalog.provider_logo("boyle-bir-saglayici-yok") is None
    assert appmod._provider_logo_url("boyle-bir-saglayici-yok") is None
