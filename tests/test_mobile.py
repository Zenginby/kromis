"""Mobil katmanın sözleşmeleri.

Depo geleneği: servis edilen artefakt doğrulanır (dosya değil), bu yüzden her
şey `TestClient` üstünden okunuyor — test_index.py ve test_id_contract.py ile
aynı yol.

Bu dosyadaki iddiaların ortak yanı: hepsi SESSİZ kırılmalara karşı. Bir mobil
CSS kuralının düşmesi ya da bir dinleyicinin bağlanmaması hiçbir hata üretmez,
yalnızca telefonda "düğme çalışmıyor" olarak görünür — ve o telefon CI'da yok.
"""
from __future__ import annotations

import os
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


# Kotlin kaynağı SERVİS EDİLMİYOR (APK'nın içinde derleniyor), o yüzden dosyadan
# okunuyor — dosyanın kendisini okuyan `test_android_apk_name.py` ile aynı
# gerekçe: kırılma iki dosyanın BİRLEŞTİĞİ yerde ve yalnız Android runner'ında
# (dakikalar süren bir NDK + Gradle işi) görünüyor. Yerelde koşan ucuz bir iddia
# aynı kaymayı saniyede yakalıyor.
_KOTLIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "android", "app", "src", "main", "java", "org", "zenginby", "gptimagestudio",
    "MainActivity.kt",
)


def _kotlin_kaynagi() -> str:
    with open(_KOTLIN, encoding="utf-8") as f:
        return f.read()


# ── Bağlanma ────────────────────────────────────────────────────────


def test_mobile_layer_is_linked_after_the_other_stylesheets(istemci):
    """mobile.css SON stil dosyası olmak ZORUNDA.

    Kuralları style.css ile aynı özgüllükte; kazanmasının tek sebebi kaynak
    sırası. Sıra bozulursa hiçbir hata çıkmaz, mobil yerleşim sessizce
    masaüstü kurallarına döner — yani bu iddia `!important` kullanmama
    kararının bedelini ödeyen mandal.
    """
    satirlar = _metin(istemci, "/").split("\n")
    # `rel="stylesheet"` ARANIYOR, yalnız dosya adı değil: adın kendisi
    # yorumlarda da geçiyor ve orayı yakalayan bir iddia sırayı hiç ölçmezdi.
    stiller = [i for i, s in enumerate(satirlar) if 'rel="stylesheet"' in s]
    mobil = [i for i in stiller if "mobile.css" in satirlar[i]]
    assert len(mobil) == 1
    assert mobil[0] == max(stiller)


def test_mobile_script_is_served(istemci):
    assert "--composer-h" in _metin(istemci, "/static/mobile.js")


def test_viewport_opts_into_the_safe_area(istemci):
    """`viewport-fit=cover` olmadan `env(safe-area-inset-*)` HER ZAMAN 0 döner.

    Yani bu tek öznitelik düşerse mobile.css'teki güvenli alan hesaplarının
    tamamı sessizce etkisiz kalır ve büyüteç şeridi Android'in jest çubuğunun
    altında kalır — görünür ama basılamaz.
    """
    html = _metin(istemci, "/")
    assert "viewport-fit=cover" in html


# ── Yerleşim kuralları ──────────────────────────────────────────────


def test_the_rail_becomes_a_bottom_bar_on_phones(istemci):
    css = _metin(istemci, "/static/mobile.css")
    assert "@media (max-width: 768px)" in css
    # Izgara alanları ray'ı ALTA taşıyor; `position: fixed` bilerek kullanılmadı.
    assert '"topbar" "canvas" "rail"' in css


def test_the_canvas_padding_follows_the_real_composer_height(istemci):
    """Sabit 260px, referans görselleri eklenince composer uzayınca yetmiyordu."""
    css = _metin(istemci, "/static/mobile.css")
    assert "calc(var(--composer-h) + 16px)" in css
    # Geri düşüş: JS hiç çalışmazsa bugünkü 260px kalmalı.
    assert "--composer-h: 260px" in css


def test_touch_rules_hang_on_hover_none_not_on_width(istemci):
    """Hover'da beliren kontroller GENİŞLİĞE değil, GİRDİ TÜRÜNE bağlanmalı.

    Genişliğe bağlansaydı geniş bir dokunmatik ekranda (tablet) silme/indirme
    düğmeleri hiç görünmezdi — o cihazda da hover yok.
    """
    css = _metin(istemci, "/static/mobile.css")
    hover_blok = css.split("@media (hover: none)")[1]
    for secici in (".card .acts", ".card-del", ".asset-del",
                   ".palette-lib-del", ".extra-del",
                   ".chat-item-menu", ".chat-media-act"):
        assert secici in hover_blok, secici


def test_tap_targets_grow_without_resizing_the_controls(istemci):
    """Hedef büyütme ::after ile: görünen boyutlar korunuyor.

    Düğmeler gerçekten 44px yapılsaydı 105px'lik bir karonun neredeyse yarısını
    silme düğmesi kaplardı — galeriyi bozarak erişilebilirlik kazanmak.
    """
    css = _metin(istemci, "/static/mobile.css")
    assert "--tap: 44px" in css
    assert "width: var(--tap); height: var(--tap);" in css


def test_the_top_edge_is_inset_like_the_bottom_edge(istemci):
    """Güvenli alan İKİ kenarlı; üst kenar atlanmıştı.

    `viewport-fit=cover` sayfayı bilerek durum çubuğunun altına da yayıyor. Üst
    şerit 56px, Android durum çubuğu ~24-28dp — yani hamburger ile ⚙'nin üst
    yarısını sistem çubuğu yutuyor: düğmeler GÖRÜNÜYOR ama dokunuş onlara
    ulaşmıyor. Tam olarak bu dosyanın başındaki "telefonda düğme çalışmıyor"
    sınıfından bir kırılma ve CI'daki hiçbir tarayıcı bunu göstermiyor
    (masaüstü Chromium'da `env(safe-area-inset-top)` her zaman 0).

    Dolgu .app'e veriliyor, .topbar'a değil: .topbar bir ızgara satırı ve tam
    `var(--topbar-h)` yüksekliğinde, içine dolgu koymak içeriği ezer.
    """
    css = _metin(istemci, "/static/mobile.css")
    ust = "env(safe-area-inset-top, 0px)"
    # .app: üst şerit. Ölçü satırın kendisinde aranıyor ki kural başka bir
    # seçiciye kayarsa test düşsün.
    assert f".app {{\n  padding-top: {ust};" in css
    # Slide-over'lar `position: fixed` — .app'in dolgusunun dışında kalıyorlar.
    # İki kenar birden: panel tam ekran, dibindeki "Kaydet" ve "Kurulu sürüm"
    # satırı jest çubuğunun altında kalıyordu.
    assert f".sheet {{\n  padding-top: {ust};\n" \
           f"  padding-bottom: env(safe-area-inset-bottom, 0px);" in css
    # Tam ekran yüzeylerin başlığı da tepede.
    for secici in (".modal-card", ".picker-card"):
        blok = css.split(secici, 1)[1].split("}", 1)[0]
        assert ust in blok, secici


# ── Medya seçici · telefondaki yerleşim ─────────────────────────────


def _mobil_yerlesim(css: str) -> str:
    """`@media (max-width: 768px)` bloklarının gövdesi, YORUMSUZ ve birleşik.

    Aşağıdaki iddialar kuralı SORGUNUN İÇİNDE arıyor, dosyanın herhangi bir
    yerinde değil: sorgunun dışına kaçan bir `.picker-side` kuralı masaüstünün
    üç sütunlu bölmesini de ezer ve bunu hiçbir mobil iddia göstermez —
    kırılma yalnız 1024px'lik pencerede, gözle görülür.

    Yorumlar AYIKLANIYOR ve bu satır ölçümle kazanıldı: bu dosyanın kuralları
    gerekçesini kendi gövdesinde yazıyor, yani `max-height` bildirimini silen
    bir mutasyon "`max-height` devreye girdiği anda…" diyen YORUM sayesinde
    hayatta kalıyordu. `test_index.py:_strip_js_comments`'in aynı gerekçesi
    (§0.6/§0.7/§0.9: iddia KODU arar, kelimeyi değil) burada CSS için.
    Ayıklama brace sayımından ÖNCE: yorum içindeki bir `{` sayımı kaydırırdı.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    govdeler = []
    for m in re.finditer(r"@media \(max-width: 768px\)\s*\{", css):
        i, derinlik = m.end(), 1
        bas = i
        while i < len(css) and derinlik:
            if css[i] == "{":
                derinlik += 1
            elif css[i] == "}":
                derinlik -= 1
            i += 1
        assert derinlik == 0, "medya sorgusu kapanmıyor"
        govdeler.append(css[bas:i - 1])
    assert govdeler, "telefon genişliği sorgusu yok"
    return "\n".join(govdeler)


def _kural(govde: str, secici: str) -> str:
    eslesme = re.search(re.escape(secici) + r"\s*\{([^}]*)\}", govde)
    assert eslesme, f"{secici} kuralı yok"
    return eslesme.group(1)


def test_the_picker_side_cannot_squeeze_the_grid_off_the_screen(istemci):
    """Seçicinin sağ bölmesi telefonda ızgarayı EZİYORDU.

    Kart tek sütuna iniyor (`grid-template-areas: "phead" "pnav" "pbody"
    "pside"`) ama bölmenin ne kadar yer kaplayacağı hiç sınırlanmamıştı:
    masaüstü kuralları 180px'lik bir sütun için yazılmış, telefonda 360px'in
    tamamında koşuyordu. Ölçüm (360×780, düzeltme öncesi): önizleme
    `aspect-ratio: 1` ile ~328px kare, künye ~100px, düğmeler ~84px, not 36px,
    dolgu 32px → `pside` ≈ 600px. `pbody` ise `minmax(0, 1fr)`, TABANI SIFIR:
    geriye ~80px kalıyordu, yani yarım karo. Kullanıcının şikâyeti birebir
    buydu: "referans ekle'ye basınca görsel ekranın tamamını kaplıyor ve
    üstteki görselleri seçemiyorum."

    Asıl yer yiyen `aspect-ratio: 1` idi ve bu iddianın mandalladığı şey o:
    telefonda önizlemeye SABİT bir boy verilmezse kare geri gelir ve ızgara
    yine ezilir. `max-height` ikinci kilit — künye beklenmedik biçimde uzasa
    (iç içe klasör zinciri) bölme yine de ekranın %40'ını aşamıyor.
    """
    govde = _mobil_yerlesim(_metin(istemci, "/static/mobile.css"))

    onizleme = _kural(govde, ".picker-preview")
    assert re.search(r"height:\s*\d+px", onizleme), (
        "önizleme telefonda hâlâ içeriğine göre büyüyor: kare geri gelir")

    bolme = _kural(govde, ".picker-side")
    assert "max-height" in bolme, "bölmenin üst sınırı yok"
    # Küçülen SADECE künye satırı olmalı; `auto` satırlar küçülmez ve sınıra
    # dayanınca kırpılan ilk şey en alttaki düğmeler olurdu.
    #
    # İddia SATIR tanımına bakıyor, gövdede `minmax(0, 1fr)` aramıyor: aynı
    # değer `grid-template-columns`ta da var (künye sütunu) ve gevşek arama
    # satırları `auto auto`ya çeviren mutasyonda HAYATTA KALDI — ölçüldü.
    satirlar = re.search(r"grid-template-rows:\s*([^;]+);", bolme)
    assert satirlar and "minmax(0, 1fr)" in satirlar.group(1), (
        "satır tanımı esnemiyor: sınıra dayanınca düğmeler kırpılır")


def test_the_picker_side_carries_the_bottom_safe_area(istemci):
    """Kartın ALT güvenli alan payı hiç verilmemişti.

    `.picker-card` yukarıda yalnız `padding-top` alıyor; `.modal-card`'ın iki
    kenarlı kuralı seçiciyi bilerek kapsamıyor (kartın kendi sınıfı var).
    Sonuç: Android'in jest çubuğu "Ek olarak ekle"nin üstüne biniyordu —
    düğme GÖRÜNÜYOR ama basılamıyor, bu dosyanın başındaki kırılma sınıfının
    aynısı ve CI'daki hiçbir tarayıcı bunu göstermiyor.

    Pay bölmeye veriliyor çünkü sayfanın en alt öğesi o.
    """
    govde = _mobil_yerlesim(_metin(istemci, "/static/mobile.css"))
    bolme = _kural(govde, ".picker-side")
    assert "env(safe-area-inset-bottom, 0px)" in bolme, (
        "seçicinin en alt öğesi jest çubuğunun altında kalıyor")


def test_the_picker_commit_buttons_wrap_by_rule_not_by_measurement(istemci):
    """İki düğmenin sarması ÖLÇÜYE bağlı kalamaz.

    `.chat-hint` dersinin aynısı (defter, Tur B): Android WebView sistem yazı
    ölçeğini uyguluyor, piksel tabanlı bir eşik ölçeği büyütmüş telefonda iki
    satır, küçültmüşte tek satır verir — yerleşim cihazdan cihaza değişir.
    `rem` tabanı eşiği yazı boyuyla birlikte büyütüyor, yani kural her cihazda
    aynı kararı veriyor.

    `width: auto` da şart: masaüstünde `.picker-commit .primary` `width: 100%`
    (style.css) ve o kural düşmezse düğmeler yan yana HİÇ gelmez.
    """
    govde = _mobil_yerlesim(_metin(istemci, "/static/mobile.css"))
    dugmeler = _kural(govde, ".picker-commit .primary, .picker-commit .btn-ghost")
    assert re.search(r"flex:\s*1\s+1\s+[\d.]+rem", dugmeler), (
        "sarma eşiği piksel: yazı ölçeği değişince yerleşim de değişir")
    assert "width: auto" in dugmeler, "masaüstünün `width: 100%`'i eziliyor değil"
    assert "min-height: var(--tap)" in dugmeler, "dokunma hedefi 44px'in altında"
    # `.primary`nin `margin-top: 1rem`i (style.css) DİKEY yığın içindi ve yan
    # yana dizilimde düğmeyi satırın 16px'ini yiyerek kısaltıyor: ölçüm 44px'e
    # karşı 60px, iki düğme alt kenarlarından hizalı. Kural düşerse yerleşim
    # hata vermeden çarpılır.
    assert "margin-top: 0" in dugmeler, "yığın mirası kenar boşluğu düğmeleri eşitsizleştiriyor"


def test_the_installed_version_is_readable_on_a_phone(istemci):
    """Telefonda kurulu sürümü görmenin BİR yolu olmak zorunda.

    Üst şeritteki `.ver` pill'i mobile.css'te gizli (360px'de #session-title'ı
    eziyordu) ve index.html'in kendi yorumu o pill'in "Ayarlar modalının dibinden
    üst şeride TAŞINDIĞINI" söylüyor — yani gizlendiği an telefonda sürümü
    görmenin hiçbir yolu kalmıyordu. Bu, APK'nın güncel olup olmadığına karar
    vermenin tek yolu (README'nin indirme bölümü buraya yönlendiriyor) ve
    kaybolması hiçbir hata üretmez: rozet zaten gizli, kimse fark etmez.

    Kaynak TEK: settings.js `[data-app-version]` ile hepsini birden yazıyor.
    """
    css = _metin(istemci, "/static/mobile.css")
    html = _metin(istemci, "/")
    js = _metin(istemci, "/static/settings.js")

    # Öncül: pill gerçekten gizli. Gizlenmesi bırakılırsa bu testin gerekçesi
    # düşer, o yüzden iddia burada duruyor.
    assert ".ver," in css and "display: none" in css.split(".ver,")[1][:80]

    # Sürüm satırı bir .sheet'in içinde — .sheet telefonda tam ekran, görünür.
    # Yorumlar ayıklanıyor: seçici yorumlarda da anlatılıyor, sayılmamalı.
    ayarlar = re.sub(r"<!--.*?-->", "", html, flags=re.S) \
        .split('id="settings-modal"', 1)[1].split("</aside>", 1)[0]
    assert "settings-version-row" in ayarlar, "Ayarlar'da kurulu sürüm satırı yok"
    assert "data-app-version" in ayarlar, "satır tek kaynağa bağlı değil"

    # Yazan taraf: tek id yerine seçici, yoksa iki yerden biri "—" kalır.
    assert 'querySelectorAll("[data-app-version]")' in js
    # Stili olmayan bir satır panelin dibinde forma ait bir not gibi okunur.
    assert ".settings-version-row" in _metin(istemci, "/static/style.css")


def test_the_image_mode_composer_row_wraps_by_rule_not_by_measurement(istemci):
    """Sarma ÖLÇÜYE bağlı kalamaz: Android WebView sistem yazı ölçeğini uyguluyor.

    Görsel modunda çubuk dört kontrol taşıyor (.plus + .view-tabs +
    .composer-right, ölçüm 393px'te 446px > 369px) ve sarma kaçınılmaz. Ölçüye
    bağlı sarma, yazı ölçeğini büyütmüş bir telefonda iki satır, küçültmüş bir
    telefonda tek satır veriyordu — yani yerleşim cihazdan cihaza değişiyordu.
    `flex-basis: 100%` onu kurala bağlıyor.

    Yalnızca Görsel modu: Yönetmen modunda #specs-btn gizli ve tek "Gönder"
    düğmesi için ikinci satır açmak composer'ı 40px boşuna uzatırdı — telefonda
    composer zaten tuvalin ~%25'i.
    """
    css = _metin(istemci, "/static/mobile.css")
    blok = css.split('#composer[data-mode="image"] .composer-right', 1)
    assert len(blok) == 2, "Görsel modu kuralı yok"
    govde = blok[1].split("}", 1)[0]
    assert "flex: 1 1 100%" in govde, "sarma ölçüye bırakılmış"
    # style.css:273'ün `margin-left: auto`'su ikinci satırda da geçerli kalıyor
    # ve satırı sağa yapıştırıyordu: solda kocaman boşluk, çip ortada asılı.
    assert "margin-left: 0" in govde


def test_the_primary_button_is_not_full_width_inside_the_composer(istemci):
    """`.composer-send` iki sınıflı seçici olmak ZORUNDA.

    `.primary { width: 100% }` bu kuraldan 627 satır SONRA tanımlı ve eşit
    özgüllükte kaynak sırası onu kazandırıyor. Tek sınıflı hâli yıllardır hiç
    uygulanmıyordu; görünmemesinin nedeni `flex-shrink`ti — #go satırı taşırıyor,
    esneme onu içerik boyuna geri büzüyordu. Satırın SARMASI gereken her yerde
    (telefon) esneme payı kalmıyor ve kaza bozuluyor: #go tam satır genişliğine
    açılıp alt satıra düşüyor, composer 40px uzuyor.
    """
    css = _metin(istemci, "/static/style.css")
    assert ".composer .composer-send { width: auto;" in css
    assert "\n.composer-send { width: auto;" not in css, "tek sınıflı hâli geri geldi"


def test_the_selection_pill_actions_drop_to_their_own_row_as_icons(istemci):
    """Eylem satırı pilin İÇİNDE üçüncü bir sütun olarak sıkışıyordu.

    .chat-pick bir flex SATIRI, .chat-bubble-actions ise .chat-msg-user'ın BLOK
    akışı için yazılmış — orada kendiliğinden alt satıra düşüyor. Pil
    `max-width: 76%` ile sınırlı olduğu için iki etiketli düğme kalan yeri
    paylaşıp 44px'e iniyor ve etiketler HARF HARF sarıyordu: telefonda "Düzenle"
    dikey bir harf sütunu oluyordu (ölçüm: düğme 44×80px).

    `flex-basis: 100%` satırı kesin olarak alta indiriyor — yine ölçüye değil
    kurala bağlı, yazı ölçeği ne olursa olsun aynı.
    """
    css = _metin(istemci, "/static/style.css")
    govde = css.split(".chat-pick .chat-bubble-actions", 1)
    assert len(govde) == 2, "eylem satırı kuralı yok"
    assert "flex: 0 0 100%" in govde[1].split("}", 1)[0]
    # Etiketler kalkıyor; erişilebilir ad `title`'dan geliyor (chat.js).
    assert ".chat-pick .chat-action-btn span { display: none; }" in css
    js = _metin(istemci, "/static/chat.js")
    assert 'copyBtn.title = "Metni panoya kopyala"' in js
    assert 'restoreBtn.title = "Metni düzenlemek üzere kutuya aktar"' in js


def test_copy_feedback_survives_the_label_being_hidden(istemci):
    """Onay etikete bağlıydı; seçim pilinde etiket gizli.

    "Kopyalandı" tek geri bildirim olsaydı bir seçimi kopyalayan telefon
    kullanıcısı hiçbir şey görmezdi — pano işlemi sessizce başarılı olur ve
    kullanıcı tekrar basardı. chatStatus() composer'ın alt satırında görünüyor.
    """
    js = _metin(istemci, "/static/chat.js")
    govde = js.split("copyBtn.addEventListener", 1)[1].split("\n  });", 1)[0]
    assert 'copyLabel.textContent = "Kopyalandı"' in govde
    assert 'chatStatus("Panoya kopyalandı.")' in govde


def test_the_selection_pill_tap_targets_do_not_overlap(istemci):
    """İki ikon düğmesi 8px arayla duruyor — KARE hedef büyütme burada yanlış.

    Yukarıdaki `width/height: var(--tap)` kalıbı uygulansaydı iki 44px'lik
    görünmez kare birbirine 14px girerdi ve çakışmada DOM'da sonra gelen
    (Kopyala) kazanırdı: Düzenle'nin sağ yarısına basmak prompt kutusunu
    doldurmak yerine kopyalardı — yani hedef büyütmek yanlış eylemi tetikleyen
    bir hata üretirdi.

    Şerit kalıbı: dikeyde 44px, yatayda düğme + iki yana 4px. 4+4 = 8px, yani
    boşluğu tam paylaşıyorlar ve sınırları değiyor ama çakışmıyor.
    """
    css = _metin(istemci, "/static/mobile.css")
    blok = css.split(".chat-pick .chat-action-btn::after", 1)
    assert len(blok) == 2, "şerit kuralı yok"
    govde = blok[1].split("}", 1)[0]
    assert "height: var(--tap);" in govde
    assert "left: -4px; right: -4px;" in govde
    assert "width: var(--tap)" not in govde, "kare kalıba dönülmüş — hedefler çakışır"
    # Ara 8px olmak zorunda: küçülürse şeritler çakışmaya başlar.
    ara = css.split(".chat-pick .chat-bubble-actions {", 1)[1].split("}", 1)[0]
    assert "gap: 8px" in ara


# ── Dokunmatik etkileşim ────────────────────────────────────────────


def test_enter_does_not_send_on_touch_devices(istemci):
    """Telefonda Enter SATIR ATLAMALI, üretim göndermemeli.

    Android klavyesinde Shift+Enter pratikte basılamıyor; kural aynı kalsaydı
    çok satırlı bir prompt hiç yazılamaz ve her satır denemesi ÜCRETLİ bir
    üretim isteği gönderirdi.
    """
    js = _metin(istemci, "/static/core.js")
    assert "IS_TOUCH" in js
    assert "if (IS_TOUCH && !e.metaKey && !e.ctrlKey) return;" in js


def test_touch_detection_needs_both_conditions(istemci):
    js = _metin(istemci, "/static/core.js")
    assert '"(hover: none) and (pointer: coarse)"' in js


def test_the_viewer_supports_two_finger_zoom(istemci):
    """`.viewer-stage`de `touch-action: none` tarayıcının pinch'ini kapatıyor ve
    tek parmak kaydırma `scale <= 1` ile korunuyor — kendi pinch'imiz olmadan
    telefonda yakınlaştırmanın tek yolu −/+ düğmeleri kalırdı."""
    js = _metin(istemci, "/static/viewer.js")
    assert 'e.pointerType !== "touch"' in js
    assert "pinchOlc" in js
    # Pinch sonrası sentetik tıklama büyüteci KAPATMAMALI.
    assert "pinchBitis" in js


# ── Sürükle-bırakın karşılığı ───────────────────────────────────────


def test_the_move_dialog_exists_and_is_wired(istemci):
    """Dokunmatikte HTML5 sürükle-bırak hiç çalışmıyor; taşımanın başka yolu olmalı."""
    html = _metin(istemci, "/")
    for id_ in ("select-move", "move-modal", "move-target", "move-ok", "move-cancel"):
        assert f'id="{id_}"' in html, id_

    js = _metin(istemci, "/static/folders.js")
    for bag in ('$("select-move").addEventListener',
                '$("move-ok").addEventListener',
                '$("move-cancel").addEventListener'):
        assert bag in js, bag


def test_the_move_dialog_reuses_the_single_move_path(istemci):
    """Taşıma mantığı TEK yerde kalmalı (`moveImages`).

    İkinci bir fetch yazılsaydı sunucuya iki ayrı yazım yolu doğardı ve
    `moveImages`'in toplu taşıma davranışı (seçim modunda tüm seçimi taşıma)
    burada sessizce ayrışırdı.
    """
    js = _metin(istemci, "/static/folders.js")
    govde = js.split("async function confirmMove()")[1].split("\n}")[0]
    assert "moveImages(" in govde
    assert "fetch(" not in govde


def test_touch_hints_do_not_teach_drag_and_drop(istemci):
    """İpuçları girdi türüne göre değişmeli: dokunmatikte "sürükle" yanlış bilgi."""
    js = _metin(istemci, "/static/folders.js")
    assert "const FOLDER_HINT_DEFAULT = IS_TOUCH" in js
    assert "const FOLDER_HINT_IMPORT = IS_TOUCH" in js

# ── Izgara boyutu ───────────────────────────────────────────────────


def test_the_three_grid_sizes_really_differ_on_a_phone(istemci):
    """S, M ve L telefonda FARKLI sütun sayısı vermek zorunda.

    Kırılma buydu: `.gallery` `repeat(auto-fill, minmax(var(--tile), 1fr))`
    kullanıyor ve `minmax` bir ALT SINIR — tarayıcı sütun sayısını
    `floor((W + gap) / (tile + gap))` ile buluyor, sonra sütunları `1fr` ile
    geriyor. Aynı sütun sayısına düşen iki farklı `--tile` PİKSEL PİKSEL aynı
    çiziliyordu: 375px ve 390px genişlikte (en yaygın telefon ölçüleri) S (84px)
    de M (105px) de 3 sütun veriyordu, yani kullanıcı için "S ile M aynı".

    Bu yüzden dar ekranda sütun sayısı tahmin EDİLMİYOR, yazılıyor. Üç değerin
    farklı olması iddianın kendisi: `--tile`a geri dönülürse ya da ikisi eşitlenirse
    kusur aynen geri gelir ve yine hiçbir hata üretmez.
    """
    css = _metin(istemci, "/static/mobile.css")
    blok = css.split("@media (max-width: 560px)")
    assert len(blok) == 2, "telefon ızgara bloğu yok"
    govde = blok[1]

    sutunlar = {}
    for ad, desen in (("m", r"\.gallery \{[^}]*?--sutun:\s*(\d+)"),
                      ("s", r'\.gallery\[data-size="s"\] \{[^}]*?--sutun:\s*(\d+)'),
                      ("l", r'\.gallery\[data-size="l"\] \{[^}]*?--sutun:\s*(\d+)')):
        m = re.search(desen, govde, re.S)
        assert m, f"{ad} için sütun sayısı yazılmamış"
        sutunlar[ad] = int(m.group(1))

    assert len(set(sutunlar.values())) == 3, f"boyutlar ayrışmıyor: {sutunlar}"
    # Sıra da anlamlı: S en çok sütun (en küçük kutucuk), L en az.
    assert sutunlar["s"] > sutunlar["m"] > sutunlar["l"], sutunlar

    # `1fr` tek başına asgari İÇERİK boyutuna takılır ve kutucuk taşar.
    assert "minmax(0, 1fr)" in govde, "sütunlar 0'a inebilir değil — taşma riski"


# ── Logo bindirme önizlemesi ────────────────────────────────────────


def test_the_logo_preview_sticks_with_a_fixed_height(istemci):
    """Önizleme telefonda SABİT kalmalı — ve yüksekliği DEĞİŞMEMELİ.

    İki ayrı kusur, tek kural:

    1. `.logo-body` 760px altında tek sütuna iniyor ve DOM sırası önizlemeyi
       kontrollerin önüne koyuyor; "Boyut" ya da "Dikey kaydırma"ya uzanmak
       önizlemeyi ekrandan çıkarıyordu. Çözüm `position: sticky`.

    2. `height` — `min-height` DEĞİL. Her kaydırıcı hareketi 220ms gecikmeyle
       sunucudan yeni bir önizleme çekip `#logo-preview-img.src`'i base64 ile
       değiştiriyor (assets.js). Kutu yüksekliğini görselden alsa her tazelemede
       değişir ve KONTROLLER KULLANICININ PARMAĞININ ALTINDA KAYARDI — sticky
       sorunu çözmek yerine yenisini üretmiş olurdu. `min-height`a dönmek
       masaüstünde hiçbir fark yaratmaz, o yüzden mandal burada.
    """
    css = _metin(istemci, "/static/mobile.css")
    kural = re.search(r"\.logo-preview-wrap \{(.*?)\n  \}", css, re.S)
    assert kural, "mobil .logo-preview-wrap kuralı yok"
    govde = kural.group(1)
    assert "position: sticky" in govde
    assert re.search(r"\n\s*height:", govde), "sabit yükseklik yok"
    # `top: 0` durum çubuğunun ALTINA sokardı: .modal telefonda `inset: 0`.
    assert "safe-area-inset-top" in govde, "güvenli alan payı yok"


# ── İndirme ─────────────────────────────────────────────────────────


def test_downloads_go_through_the_attachment_route(istemci):
    """`/output/…` çizim adresi indirme adresine ÇEVRİLMEK zorunda.

    Android WebView HTML'in `download` özniteliğini yok sayıyor; başlıksız bir
    `image/png`'ye gitmek onun çizebileceği bir şey olduğu için kayıt dinleyicisi
    hiç tetiklenmiyor ve indirme SESSİZCE hiç olmuyordu. Çevirme TEK yerde
    (`indirmeAdresi`), üç indirme yolu da oradan geçiyor.
    """
    js = _metin(istemci, "/static/core.js")
    assert "function indirmeAdresi(" in js, "çevirme işlevi yok"
    assert "/api/output/" in js, "indirme ucu hiç kullanılmıyor"
    # Çıpa/köprü ile panelin fetch'i AYNI adresi kullanmalı; biri atlanırsa
    # kırılma "bazen çalışıyor" olarak geri döner.
    assert "const adres = indirmeAdresi(url)" in js
    assert "a.href = adres" in js
    assert "fetch(indirmeAdresi(url))" in js


def test_the_android_download_bridge_is_wired_on_both_sides(istemci):
    """İndirme köprüsünün adı JS ile Kotlin'de AYNI olmak zorunda.

    Telefonda indirmenin çalışmasının tek garantisi bu köprü: `<a download>`
    Android'de bir gezinme değil "renderer kaynaklı indirme" üretiyor, WebView'in
    indirme sistemi hiç yok ve devralma zinciri koptuğunda tıklama SESSİZCE
    hiçbir şey yapmıyor — hata da çıkmıyor.

    Ad ayrışırsa aynı sessizlik geri geliyor: `window.LumeoIndirme` tanımsız
    kalır, frontend eski çıpa yoluna düşer ve kimse bir şey fark etmez. Kırılma
    yine iki dosyanın BİRLEŞTİĞİ yerde — bu dosyadaki diğer mandallarla aynı
    sınıf.
    """
    js = _metin(istemci, "/static/core.js")
    kt = _kotlin_kaynagi()

    ad = re.search(r'window\.(\w+);', js.split("function androidKoprusu()")[1])
    assert ad, "core.js köprüyü `window.<ad>` ile hiç aramıyor"
    assert f'"{ad.group(1)}"' in kt, (
        f"Kotlin köprüyü `{ad.group(1)}` adıyla enjekte etmiyor")

    assert "addJavascriptInterface" in kt, "köprü WebView'e hiç takılmıyor"
    # `@JavascriptInterface` İŞARETİ ŞART (API 17+): işaretsiz yöntem JS'ten hiç
    # görünmez, yani köprü derlenir ama sessizce yok sayılırdı.
    assert "@JavascriptInterface" in kt, "köprü yöntemi JS'e açık değil"

    # SIRA: köprü sayfa YÜKLENMEDEN takılmak zorunda — enjeksiyon yükleme
    # sırasında yapılıyor, sonradan eklenen bir arayüz ancak bir SONRAKİ
    # yüklemede görünür ve ilk oturumda indirme yine ölürdü. Ölçülen şey metin
    # sırası değil ÇAĞRI sırası: `onCreate` önce `webViewiKur()`, sonra
    # `sunucuyuBaslat()` diyor; `loadUrl` ise ancak sunucu hazır olunca
    # (`sunucuHazir`) çalışıyor.
    kurulum = kt.split("private fun webViewiKur()")[1]
    assert "addJavascriptInterface" in kurulum, "köprü webViewiKur() dışında takılıyor"
    acilis = kt.split("override fun onCreate(")[1].split("\n    }")[0]
    assert acilis.index("webViewiKur()") < acilis.index("sunucuyuBaslat()"), \
        "WebView sunucudan sonra kuruluyor: köprü ilk yüklemeyi kaçırır"
    assert "webView.loadUrl" in kt.split("private fun sunucuHazir(")[1], \
        "sayfa artık başka bir yerden yükleniyor: sıra iddiası anlamsızlaştı"


def test_the_bridge_only_accepts_our_own_server(istemci):
    """Köprü, adresi KENDİ sunucumuza çivilemek zorunda.

    `addJavascriptInterface` nesneyi WebView'deki her sayfaya açıyor. Host
    denetimi olmasa sayfaya sızan herhangi bir içerik uygulamaya internetten
    dosya indirtebilirdi; port denetimi olmasa cihazdaki BAŞKA bir yerel sunucu
    aynı şeyi yapardı. `Downloader`ın çerezi yalnız loopback'e vermesiyle aynı
    disiplin.
    """
    kt = _kotlin_kaynagi()
    govde = kt.split("private fun koprudenIndir(")[1].split("\n    }")[0]
    assert '"127.0.0.1"' in govde, "host denetimi yok"
    assert "hedef.port == sunucu.port" in govde, "port denetimi yok"
    # Ad frontend'den geliyor ve klasör ZIP'inde KULLANICI metni — yol ayırıcı
    # taşıyabilir. Kırpmayı eskiden `guessFileName` yapıyordu.
    assert "guvenliAd" in govde, "dosya adı sanitasyonu atlanmış"


def test_the_download_listeners_no_longer_defer_to_the_bare_anchor(istemci):
    """Kayıt paneli yoksa çıpanın KENDİ gezinmesine bırakılmamalı.

    Galeri kartı ve büyüteç eskiden `if (!SUPPORTS_SAVE_PICKER) return;` diyerek
    araya hiç girmiyordu — masaüstü paketinde doğru, Android'de ise indirmenin hiç
    olmaması demekti. `downloadImage` panel yokken kendisi `downloadViaAnchor`'a
    düşüyor, yani pakette mekanizma değişmedi; değişen tek şey kararın TEK yerde
    olması.
    """
    for yol in ("/static/folders.js", "/static/viewer.js"):
        js = _metin(istemci, yol)
        # Yorumlarda adı geçmesi serbest; ARANAN erken dönüşün kendisi.
        assert "!SUPPORTS_SAVE_PICKER) return" not in js, yol


# ── Geri tuşu ───────────────────────────────────────────────────────


def test_the_back_button_has_a_single_gate_in_the_frontend(istemci):
    """Geri sıralaması JS'te olmak zorunda — Kotlin'in içine gömülü değil.

    Sıralama eskiden MainActivity.kt'nin içinde ÜÇ CSS seçicisiydi ve
    index.html'in yapısına dizeyle bağlıydı; koruyan hiçbir test yoktu. İki somut
    kırılma üretmişti: sohbet menüleri üç seçicinin hiçbirine uymuyordu (menü
    açıkken geri uygulamayı KAPATIYORDU) ve bölüm/klasör gezintisi geri yığınında
    hiç yoktu (Medya'dayken geri doğrudan çıkışa gidiyordu).

    Kotlin tarafı bu dosyadan okunuyor, servis edilen artefakttan değil: APK'nın
    içinde ama aynı depoda — kırılma iki dosyanın BİRLEŞTİĞİ yerde
    (test_android_apk_name.py ile aynı gerekçe).
    """
    js = _metin(istemci, "/static/core.js")
    assert "window.geriTusu" in js, "geri kapısı yok"
    govde = js.split("window.geriTusu = function ()")[1].split("\n};")[0]
    # Dört adım: katman → klasör → bölüm → çıkış.
    for beklenen in (".sheet.open", ".modal:not([hidden])", ".popover:not([hidden])",
                     ".chat-menu:not([hidden])", "#chats-kebab-menu:not([hidden])",
                     "folder-back", 'currentSection !== "studio"'):
        assert beklenen in govde, beklenen
    assert "return false" in govde, "çıkışa hiç düşmüyor"

    kt = _kotlin_kaynagi()
    assert "window.geriTusu" in kt, "Kotlin frontend kapısını çağırmıyor"
    assert ".sheet.open" not in kt, "Kotlin hâlâ kendi CSS seçicilerini taşıyor"


def test_the_folder_step_only_runs_inside_media(istemci):
    """Klasör basamağı YALNIZ Medya'dayken çalışmalı.

    `#folder-back`ın `hidden`i tek başına "klasördeyiz" demiyor: onu
    `syncFolderView` yalnız `currentFolder`a bakarak yazıyor ve `showSection`
    `currentFolder`ı HİÇ temizlemiyor. Bir alt klasördeyken Stüdyo'ya geçip geri
    basmak, GÖRÜNMEYEN düğmeyi tıklayıp `true` döndürüyordu: ekranda hiçbir şey
    olmuyor, üstelik çıkış yolu klasör yığını boşalana kadar erişilemez kalıyor —
    kullanıcı için "geri tuşu takıldı". Arama açıkken de aynısı (`.gallery-head`
    tümden gizli, düğmenin kendi `hidden`i hâlâ `false`).
    """
    js = _metin(istemci, "/static/core.js")
    govde = js.split("window.geriTusu = function ()")[1].split("\n};")[0]
    klasor_adimi = govde.split("folder-back")[1].split("return true")[0]
    assert 'currentSection === "media"' in klasor_adimi, (
        "klasör basamağı bölümden bağımsız çalışıyor")


def test_leaving_the_app_needs_two_back_presses(istemci):
    """Tek geri basışı uygulamayı KAPATMAMALI.

    Arayüzde kapatılacak bir şey kalmadığında tek bir basış (ya da kenardan tek
    bir kaydırma) oturumu kapatıyordu — süren bir üretimin ortasında bile. Jest
    gezinmesinde ekranın kenarına değmek kolay, yani kazayla çıkmak sıktı.

    `sistemGerisi()`ye giden TEK yol `cikisiOnayla()`: ikinci bir doğrudan çağrı
    eklenirse kapı sessizce baypas edilir ve kusur geri gelir.
    """
    kt = _kotlin_kaynagi()
    assert "private fun cikisiOnayla()" in kt, "çıkış kapısı yok"
    # `System.currentTimeMillis()` DEĞİL: duvar saati kullanıcı ya da ağ
    # tarafından geriye alınabilir, fark negatife düşer ve pencere bir daha hiç
    # açılmaz — "iki kez bastım, çıkmıyor". `= System.currentTimeMillis()`
    # ARANIYOR, çıplak ad değil: ad kararın gerekçesinde de geçiyor ve orayı
    # yakalayan bir iddia yorumu silmeye zorlardı.
    assert "SystemClock.elapsedRealtime()" in kt
    assert "= System.currentTimeMillis()" not in kt

    # `onBackPressed` çıkışa DOĞRUDAN gitmemeli — iki dalı da (perde görünürken
    # ve JS "false" dönerken) kapıdan geçmek zorunda. Doğrudan çağrı geri
    # eklenirse uyarı sessizce baypas edilir: hiçbir hata çıkmaz, uygulama yine
    # tek basışta kapanır.
    geri = kt.split("override fun onBackPressed()")[1].split("\n    }")[0]
    assert "sistemGerisi()" not in geri, "onBackPressed çıkışa doğrudan gidiyor"
    assert geri.count("cikisiOnayla()") == 2, geri

    kapi = kt.split("private fun cikisiOnayla()")[1].split("\n    }")[0]
    assert "sistemGerisi()" in kapi, "kapı çıkışa hiç düşmüyor"


def test_model_seridi_kapsayiciyi_genisletemiyor(istemci):
    """`.composer-head` `min-width: 0` taşımak ZORUNDA.

    Bu iddia ölçülmüş bir regresyonun mandalı. `#composer` bir flex kolon;
    `.composer-head` onun bir flex ÖĞESİ ve öğenin varsayılan `min-width: auto`
    değeri kendi min-content genişliğine çözülüyor. İçindeki çip DÜĞMESİNİN
    (`#model-btn`) min-content'i seçili modelin metni kadar ("Gemini · Nano
    Banana Pro — 27–48 kredi · kurulum gerekli"), yani satır kapsayıcının içerik
    kutusundan taşıyor VE kardeşlerini de kendisiyle birlikte genişletiyor.

    TAŞMANIN KAYNAĞI TAŞINDI, kural DEĞİL: ölçüm `<select id="model">` çipin
    görünen yüzüyken yapıldı ve o zaman baskı en uzun SEÇENEĞİN metninden
    geliyordu. Seçim alttan açılan panele taşındı, `<select>` `.sr-only`
    (position:absolute — akışta değil) oldu ve baskı artık çip düğmesinin
    etiketinden geliyor. Düğme kendi metnini KIRPMIYOR (native `<select>`
    kırpıyordu), yani `min-width: 0` olmadan `.model-chip-label`ın
    `text-overflow` kuralı hiç devreye girmiyor.

    Somut ölçüm (Chromium, 360×780): taşma varken composer'ın BÜTÜN çocukları
    334px'ten 357px'e çıkıyor ve sayfa 10px yatay kayıyor (`scrollWidth` 370,
    `clientWidth` 360). `main`'de taşma YOK, yani bu tümüyle model şeridinin
    getirdiği bir bedel.

    Neden mekanik bir CSS iddiası: kırılma yalnız DAR ekranda ve yalnız GERÇEK
    bir tarayıcıda görünüyor — pytest CSS'i çalıştırmıyor, masaüstü genişliğinde
    de hiç belirmiyor. Zayıf ama doğru yerde duran bir mandal; kuralı silen
    kişiye nedenini söylüyor.

    DİKKAT: `.model-chip`e (yani çipin KENDİSİNE) `min-width: 0` vermek
    YETMİYOR — denendi ve taşma sürdü. Kısıt öğenin kendisinde değil, onu tutan
    SATIRDA.
    """
    css = _metin(istemci, "/static/style.css")
    blok = css.split(".composer-head {", 1)
    assert len(blok) == 2, ".composer-head kuralı kaybolmuş"
    govde = blok[1].split("}", 1)[0]
    assert "min-width: 0" in govde, (
        ".composer-head'in `min-width: 0`ı silinmiş — 360px'de model şeridi "
        "composer'ın bütün çocuklarını genişletir ve sayfa yatay kayar")


def test_model_seridinin_SARMALAYICISI_da_kucultulebilir(istemci):
    """Sağlayıcı işareti gelince flex öğesi `.model-pick` oldu — kısıt ona taşındı.

    `.composer-head`in `min-width: 0`ı zinciri kapsayıcı tarafında açıyor, ama
    sarmalayıcının KENDİSİ varsayılan `min-width: auto` ile kalırsa içindeki çip
    DÜĞMESİNİN min-content genişliğinin altına inmiyor ve aynı 360px taşmasını
    bir katman aşağıda yeniden üretiyor. İki kural birlikte gerekiyor: biri
    satırda, biri sarmalayıcıda.

    Aynı blok `max-width: 100%` de taşımak zorunda: `.model-chip`in `max-width`i
    artık sarmalayıcının genişliğine göre çözülüyor.
    """
    css = _metin(istemci, "/static/style.css")
    blok = css.split(".model-pick {", 1)
    assert len(blok) == 2, ".model-pick kuralı kaybolmuş (işaret sarmalayıcısı)"
    govde = blok[1].split("}", 1)[0]
    assert "min-width: 0" in govde, (
        ".model-pick'in `min-width: 0`ı silinmiş — sarmalayıcı içindeki "
        "<select>in min-content genişliğinin altına inmez, 360px'de taşma döner")
    assert "max-width: 100%" in govde, ".model-pick genişlik tavanı taşımıyor"


def test_gizlenen_model_seridinin_KABUGU_da_gizleniyor(istemci):
    """Mod ekseni SARMALAYICIYI gizlemek zorunda, `<select>`i değil.

    İşaret şeridin içine girdiğinde `<select>` artık en dış öğe değil. Kural
    eski hâlinde kalsa (`#composer[data-mode="image"] #chat-model`) gizli
    şeridin kabuğu — sarmalayıcı + işaret — ekranda yer kaplamaya devam ederdi:
    Yönetmen modunda iki şerit birbirini dışlıyor ve "genişlik bedeli sıfır"
    güvencesi tam olarak buna dayanıyor.
    """
    css = _metin(istemci, "/static/style.css")
    assert '#composer[data-mode="image"] #chat-model-pick' in css, (
        "Görsel modunda sohbet şeridinin SARMALAYICISI gizlenmiyor")
    assert '#composer[data-mode="director"] #model-pick' in css, (
        "Yönetmen modunda görsel şeridinin SARMALAYICISI gizlenmiyor")


def test_composer_ipucu_TELEFONDA_hala_gizli(istemci):
    """`.chat-hint` telefonda `display: none` KALIYOR.

    Masaüstünde ipucunun taban genişliği `flex: 1`den (yani `flex: 1 1 0%`,
    taban SIFIR) içerik genişliğine çevrildi: `#status` uzun bir metin
    yazdığında ipucu 65px'e ezilip dört satıra sarıyordu (ölçüm: Chromium,
    1024×700). Telefonda ise ipucu ZATEN gizli ve gizli kalması gerekiyor —
    "⌘/Ctrl + Enter" dokunmatikte yanlış bilgi (Enter satır atlıyor) ve klavye
    açıkken satır boşuna yer kaplıyor.

    Mandal masaüstü düzeltmesinin telefon tarafına SIZMASINA karşı: kural
    `style.css`'te değil `mobile.css`'te ve iki dosya ayrı ayrı düzenleniyor,
    yani "ipucu artık sarmıyor, gizlemeye gerek yok" diye düşünen bir sonraki
    tur bu satırı sessizce silebilir. Kırılma CI'da görünmez — telefon yok.
    """
    css = _metin(istemci, "/static/mobile.css")
    blok = css.split(".chat-hint {", 1)
    assert len(blok) == 2, ".chat-hint kuralı mobile.css'ten kaybolmuş"
    assert "display: none" in blok[1].split("}", 1)[0], (
        "ipucu telefonda gizlenmiyor — klavye açıkken yer kaplar ve "
        "dokunmatikte yanlış kısayolu anlatır")


def test_alttan_acilan_yuzeyde_UST_guvenli_alan_ODENMIYOR(istemci):
    """`.sheet-bottom` `.sheet`in üst güvenli-alan dolgusunu geri alıyor.

    `.sheet { padding-top: env(safe-area-inset-top) }` yandan açılan panel için
    doğru: onun başlığı ekranın TEPESİNE dayanıyor ve çentiğin altında kalırdı.
    Alttan açılan panel tepeye hiç değmiyor (`top: auto` + `max-height`), yani
    o pay orada bir kazanç değil KAYIP — başlığın üstünde 24-44px ölü boşluk
    olarak duruyor ve listeden o kadar yer çalıyor.

    ALT dolgu KALIYOR ve iddia onu da koruyor: dipteki "Tamam"/"Kaydet" jest
    çubuğunun altında kalmamalı.

    MEKANİZMA SIRA: iki kuralın özgüllüğü eşit (`.sheet` 0,1,0 ve
    `.sheet-bottom` 0,1,0), yani kazanan SONRA gelen. Kurallar yer değiştirirse
    dolgu sessizce geri gelir — o yüzden iddia sırayı da ölçüyor.

    Kırılma masaüstü Chromium'da GÖRÜNMEZ: `env(safe-area-inset-*)` orada 0
    döndürüyor. Yalnız çentikli bir telefonda belirir.
    """
    css = _metin(istemci, "/static/mobile.css")
    ortak = css.find(".sheet {")
    varyant = css.find(".sheet-bottom { padding-top: 0; }")
    assert ortak != -1, ".sheet güvenli alan kuralı kaybolmuş"
    assert varyant != -1, (
        "`.sheet-bottom { padding-top: 0; }` yok — alttan açılan panelin "
        "başlığının üstünde çentik payı ölü boşluk olarak duruyor")
    assert varyant > ortak, (
        "varyant ortak kuraldan ÖNCE geliyor — özgüllükler eşit olduğu için "
        "ortak kural kazanıyor ve üst dolgu geri geliyor")
    # Alt kenar payı ORTAK kuralda ve orada kalmalı.
    govde = css[ortak:].split("}", 1)[0]
    assert "padding-bottom: env(safe-area-inset-bottom" in govde, (
        "alt güvenli alan payı silinmiş — dipteki düğme jest çubuğunun "
        "altında kalır")


def test_alttan_acilan_yuzey_telefonda_TAM_GENISLIK(istemci):
    """Masaüstü tavanı telefonda kalkıyor — ve id özgüllüğü tuzağı KURULMUYOR.

    `#palette-modal` bu tuzağa düştü: `#palette-modal.sheet { width: 420px }`
    id özgüllüğüyle medya sorgusunun `.sheet { width: 100% }` kuralını eziyordu
    ve mobile.css ikinci bir kural (`#palette-modal { width: 100% }`) yazmak
    zorunda kaldı. Alttan açılan panellerde genişlik `min(…, 100%)` yazılıyor,
    yani tavan telefonda kendiliğinden 100%'e çözülüyor ve id özgüllüğü bir
    sorun olmaktan çıkıyor.
    """
    mobil = _metin(istemci, "/static/mobile.css")
    assert ".sheet-bottom { width: 100%; max-width: 100%;" in mobil, (
        "alttan açılan panel telefonda tam genişlik almıyor")

    stil = _metin(istemci, "/static/style.css")
    for secici in (".sheet-bottom {", "#settings-modal.sheet-bottom {"):
        blok = stil.split(secici, 1)
        assert len(blok) == 2, f"{secici} kuralı kaybolmuş"
        govde = blok[1].split("}", 1)[0]
        genislik = [s for s in govde.split(";") if "width:" in s and "max-width" not in s]
        assert genislik, f"{secici} genişlik yazmıyor"
        assert "min(" in genislik[0] and "100%" in genislik[0], (
            f"{secici} sabit bir genişlik yazıyor — telefonda #palette-modal'ın "
            "id özgüllüğü tuzağı geri geliyor (mobile.css ikinci bir kural "
            "istemek zorunda kalır)")
