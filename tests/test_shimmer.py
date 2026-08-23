"""Bekleme animasyonunun (pixel-canvas) sözleşmeleri.

Bu katmanın tamamı SESSİZ kırılır: bileşen kaydolmazsa, betik chat.js'ten
sonra yüklenirse ya da CSS kuralı düşerse hiçbir hata çıkmaz — yalnızca
üretim beklerken kutu boş kalır. Tarayıcı CI'da yok, o yüzden iddialar
servis edilen artefakt üzerinden (test_mobile.py ile aynı yol).
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

import app as appmod


@pytest.fixture(scope="module")
def istemci():
    return TestClient(appmod.app)


def _metin(istemci, yol: str) -> str:
    yanit = istemci.get(yol)
    assert yanit.status_code == 200, yol
    return yanit.text


def _kod(istemci, yol: str) -> str:
    """Betiğin YALNIZ kodu — `//` ile başlayan satırlar ayıklanmış.

    Gerekmesinin sebebi bu depoda kayıtlı: yorumlar KALDIRILAN satırı tırnak
    içinde anlatıyor (gelenek, kusuru kaydeden yorum) ve "şu satır olmasın"
    iddiaları o anlatıyı da yakalıyor. Aşağıdaki iki iddia ilk yazımda tam
    böyle düştü — pixel-canvas.js'in başındaki sapma listesi hem
    `this.animation = this.animate(name)`ı hem `new CSSStyleSheet()`i
    ANLATIYOR. Yorum kalmalı, iddia ise gerçekten koşan kodu ölçmeli.
    (test_ci_paketleme_kapisi.py'nin `kapsam_kodu`su ve test_index.py'nin
    `role=` iddiası aynı tuzağın öteki iki kaydı.)
    """
    return "\n".join(satir for satir in _metin(istemci, yol).splitlines()
                      if not satir.lstrip().startswith("//"))


def test_component_script_is_served_and_registers_the_element(istemci):
    kaynak = _metin(istemci, "/static/pixel-canvas.js")
    # Kayıt olmazsa `document.createElement("pixel-canvas")` bilinmeyen bir
    # eleman döndürür: `start()` yoktur, kutu sessizce boş kalır.
    assert 'customElements.define(tag, this)' in kaynak
    assert 'static register(tag = "pixel-canvas")' in kaynak
    # Çift tanım sayfayı TÜMDEN düşürmemeli (önbellek ıskası iki kez yükletebilir).
    assert "!customElements.get(tag)" in kaynak


def test_component_keeps_its_globals_to_itself(istemci):
    """`Pixel` küresel kapsamda durmamalı — betikler burada kapsamı paylaşıyor.

    Deponun ön yüzünde modül yok (docs/graflar/onyuz.md): üst düzeydeki her ad
    ötekilerin adıyla çakışabilir. Bileşenin dışa açılan yüzü elemanın kendisi,
    bir küresel ad değil.
    """
    kaynak = _metin(istemci, "/static/pixel-canvas.js")
    assert "(() => {" in kaynak
    assert not re.search(r"^class Pixel\b", kaynak, re.M), "Pixel küresel kapsamda"


def test_component_cancels_its_animation_on_disconnect(istemci):
    """Kart DOM'dan silinince rAF döngüsü de ölmeli.

    "appear" kipinde hiçbir piksel `isIdle` olmuyor, yani döngü kendiliğinden
    durmuyor. Bu satır düşerse her üretim kopmuş bir canvas'a çizen bir döngü
    daha bırakır ve oturum uzadıkça sekme ısınır — hiçbir hata vermeden.
    """
    kaynak = _metin(istemci, "/static/pixel-canvas.js")
    govde = kaynak.split("disconnectedCallback()", 1)
    assert len(govde) == 2, "disconnectedCallback yok"
    assert "cancelAnimationFrame(this.animation)" in govde[1].split("handleEvent", 1)[0]


def test_the_cancel_gate_is_not_disarmed_by_an_overwritten_handle(istemci):
    """İptal edilecek kimlik `undefined` OLMAMALI — kapının ikinci yarısı.

    Özgün bileşende `handleAnimation` şöyleydi:

        this.animation = this.animate(name);

    `animate()` değer DÖNDÜRMÜYOR: ilk çağrıda içeride kurulan rAF kimliğinin
    üstüne `undefined` biniyor ve kimlik ancak SIRADAKİ karede gerçek bir
    değere kavuşuyor. Yani bir üstteki testin mandalladığı
    `cancelAnimationFrame` o ilk karede hiçbir şeyi iptal etmiyordu — kart o
    aralıkta silinirse sızıntı yine kalıyordu. Kimliğin tek yazarı `animate`.
    """
    kaynak = _kod(istemci, "/static/pixel-canvas.js")
    assert "this.animation = this.animate(" not in kaynak, (
        "rAF kimliği `animate`in dönüşüyle eziliyor (dönüş yok: undefined)")
    govde = kaynak.split("handleAnimation(name) {", 1)
    assert len(govde) == 2, "handleAnimation yok"
    govde = govde[1].split("}", 1)[0]
    assert "cancelAnimationFrame(this.animation)" in govde, govde
    assert "this.animate(name)" in govde, govde


def test_shadow_style_does_not_need_constructable_stylesheets(istemci):
    """Gölge kökün stili `<style>` düğümüyle gelmeli.

    `new CSSStyleSheet()` + `adoptedStyleSheets` Safari 16.4'ten önce yok ve
    masaüstü paketi sistemin WebView'ini kullanıyor. Orada `connectedCallback`
    FIRLIYOR: eleman hiç kurulmuyor, `start()` çağrısı da bir şey yapmıyor ve
    kutu sessizce boş kalıyor — bu dosyanın var olma sebebi olan kırılma
    sınıfının tam kendisi. Kurulabilir sayfanın kazancı (örnekler arası
    paylaşım) burada zaten yok: aynı anda tek bir bekleme kartı yaşıyor.
    """
    kaynak = _kod(istemci, "/static/pixel-canvas.js")
    assert "new CSSStyleSheet" not in kaynak, "kurulabilir stil sayfası geri gelmiş"
    assert "adoptedStyleSheets" not in kaynak
    assert 'document.createElement("style")' in kaynak
    # Stil gölge köke GERÇEKTEN giriyor mu — düğümü kurup eklememek sessizce
    # stilsiz bir canvas demek (`:host` boyutu 0 kalır, tek piksel çizilmez).
    govde = kaynak.split("connectedCallback() {", 1)[1].split("disconnectedCallback", 1)[0]
    assert "stil.textContent = PixelCanvas.css" in govde, govde
    assert "this.shadowroot.append(stil, canvas)" in govde, govde


def test_component_loads_before_chat(istemci):
    """Sıra: pixel-canvas.js, chat.js'ten ÖNCE.

    chat.js üretim başlarken elemanı `createElement` ile kuruyor; tanım o an
    kayıtlı olmalı. Sıra tersine dönerse hata çıkmaz, kutu boş kalır.
    """
    html = _metin(istemci, "/")
    sira = re.findall(r'<script src="/static/([a-z-]+\.js)', html)
    assert "pixel-canvas.js" in sira, sira
    assert sira.index("pixel-canvas.js") < sira.index("chat.js"), sira


def test_pending_card_creates_a_manual_pixel_canvas(istemci):
    """chat.js kutuyu kurmalı ve tetiği KENDİSİ çekmeli.

    `data-manual` düşerse bileşen hover/odak bekler: üretim sürerken fare
    kartın üstüne gelmedikçe hiçbir şey olmaz. `start()` düşerse hiç olmaz.
    """
    kaynak = _metin(istemci, "/static/chat.js")
    assert 'document.createElement("pixel-canvas")' in kaynak
    assert 'setAttribute("data-manual"' in kaynak
    assert "pixels.start()" in kaynak
    assert 'className = "pending-shimmer"' in kaynak


def _px(kural: str, ad: str = "max-width") -> int:
    eslesme = re.search(rf"{ad}:\s*(\d+)px", kural)
    assert eslesme, f"{ad} yok: {kural}"
    return int(eslesme.group(1))


def test_pending_box_fits_inside_the_single_result_width(istemci):
    """Bekleme kutusu sonuç görselinden GENİŞ olmamalı.

    Geniş olursa sonuç indiği an akış içe doğru sıçrar. Eşit de değil: kutu
    #composer'ın kapattığı şeride sığmak zorunda (kuralın kendi yorumu).
    """
    css = _metin(istemci, "/static/style.css")
    kutu = re.search(r"\.pending-shimmer\s*\{[^}]*\}", css)
    assert kutu, ".pending-shimmer kuralı yok"
    sonuc = re.search(r'\.chat-result-grid\[data-count="1"\]\s*\{[^}]*\}', css)
    assert sonuc, "tek görsellik ızgara kuralı yok"
    assert _px(kutu.group(0)) <= _px(sonuc.group(0)), (kutu.group(0), sonuc.group(0))
    # Yuvarlatılmış kutunun dışına taşan canvas köşeleri.
    assert "overflow: hidden" in kutu.group(0)




def test_pending_card_is_the_scroll_target(istemci):
    """Kaydırma hedefi bekleme kartı olmalı, kullanıcı baloncuğu değil.

    Kart artık bir görsel yüksekliğinde: baloncuğa kaydırılırsa kutunun altı
    ve yüzde çubuğu #composer'ın arkasında kalır.
    """
    kaynak = _metin(istemci, "/static/chat.js")
    assert "scrollMessageIntoView(pendingDiv)" in kaynak


def test_simulated_percentage_is_gone(istemci):
    """Uydurma yüzde geri gelmemeli.

    Sağlayıcı tek yanıt döndürüyor: eski bar 160ms'lik bir setInterval ile
    ~%90'a doğru asimptotik dolup orada bekliyordu, yani sayı bir ÖLÇÜM
    değil süslemeydi. Geri getirilecekse ölçülecek bir şey de gelmeli
    (sağlayıcıdan akış yanıtı) — o yüzden bu kapı iddialı: ne düğüm, ne
    işlev, ne de CSS kuralı.
    """
    html = _metin(istemci, "/")
    for kimlik in ("progress", "progress-fill", "progress-pct"):
        assert f'id="{kimlik}"' not in html, kimlik
    core = _metin(istemci, "/static/core.js")
    # Parantezli aranıyor: adlar core.js'te NEDEN kaldırıldıklarını anlatan
    # yorumda geçiyor ve o yorum kalmalı. Tanım ya da çağrı parantez ister.
    assert "startProgress(" not in core and "stopProgress(" not in core
    css = _metin(istemci, "/static/style.css")
    for kural in (r"^\.progress\b", r"^\.bar\b", r"^\.bar-fill\b", r"^\.pct\b"):
        assert not re.search(kural, css, re.M), kural


def test_shimmer_is_the_only_thing_in_the_pending_card(istemci):
    """Bekleme kartının TEK içeriği shimmer kutusu.

    Kart bir zamanlar taşınabilir bir yüzde çubuğu barındırıyordu ve o çubuk
    `.studio-flow` ile kart arasında taşınıyordu; taşıma mantığı da gitti.
    Kartın silinmesi tek adım kalmalı, yoksa kopmuş bir düğüm geride kalır.
    """
    kaynak = _metin(istemci, "/static/chat.js")
    govde = kaynak.split("function beginResultTurn", 1)[1].split("\nfunction ", 1)[0]
    ekler = re.findall(r"pendingDiv\.appendChild\((\w+)\)", govde)
    assert ekler == ["shimmer"], ekler
    # Spinner ÖTEKİ hâllerde duruyor (yönetmen düşünüyor, logo önizleme);
    # shimmer'ın onu genel olarak süpürmediğinin kanıtı.
    assert '<div class="spinner"></div>' in _metin(istemci, "/")
