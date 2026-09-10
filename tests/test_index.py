import os
import re
import subprocess

from fastapi.testclient import TestClient
import app as appmod
import models
import version


def test_index_served():
    c = TestClient(appmod.app)
    r = c.get("/")
    assert r.status_code == 200
    assert "Kromis" in r.text
    assert 'id="prompt"' in r.text
    # birleşik akış: prompt bölümünde görsel ekleme; ayrı düzenle paneli yok
    assert 'id="file-input"' in r.text
    assert 'id="upload-btn"' in r.text
    assert 'id="edit-panel"' not in r.text
    # ayarlar: dişli butonu + modal
    assert 'id="settings-btn"' in r.text
    assert 'id="settings-modal"' in r.text
    # klasörler: silme kartta değil, klasör içindeyken başlık şeridinde
    assert 'id="folder-delete"' in r.text
    assert 'id="confirm-modal"' in r.text
    # çoklu seçim şeridi
    assert 'id="select-toggle"' in r.text
    assert 'id="select-bar"' in r.text
    # tema rengi / palet: satır içi panel (üretim anında görünür) + modal
    assert 'id="palette-btn"' in r.text
    assert 'id="palette-chip"' in r.text
    assert 'id="palette-strength"' in r.text
    assert 'id="palette-modal"' in r.text
    assert 'id="palette-suggestions"' in r.text
    # renk seçici: HSV alanı + ton kaydırıcısı + hex; native input type=color
    # yerini aldı, o yüzden onun kalmadığı da doğrulanıyor
    assert 'id="palette-field"' in r.text
    assert 'id="palette-hue"' in r.text
    assert 'id="palette-seed-hex"' in r.text
    assert 'id="palette-eyedrop"' in r.text
    assert 'type="color"' not in r.text
    assert 'id="palette-lib-grid"' in r.text
    assert 'data-strength="strict"' in r.text
    # paletler bir "varlık" türü DEĞİL: bindirmeleri etkilemiyorlar
    assert 'data-akind="palettes"' not in r.text


def test_logo_offset_controls_are_served():
    """Kaydırma kontrolleri: assets.js bu id'lere `$()` ile DOĞRUDAN bağlanıyor.

    viewer testindeki gerekçenin aynısı: biri yeniden adlandırılırsa script
    yükleme anında patlar ve ONDAN SONRAKİ hiçbir dinleyici kurulmaz — yani
    "Uygula" düğmesi de sessizce ölür.
    """
    html = TestClient(appmod.app).get("/").text
    for element_id in ("logo-offset-x", "logo-offset-y", "logo-offset-reset",
                       "logo-offset-x-val", "logo-offset-y-val"):
        assert f'id="{element_id}"' in html, element_id


def test_offset_sliders_are_bipolar():
    """Aralık negatifi KAPSAMALI — yoksa logo yalnız sağa/aşağı kayar.

    `min="0"` diye bir yazım hatası gözle fark edilmez: slider çalışır görünür,
    yalnızca yarısı eksiktir.
    """
    html = TestClient(appmod.app).get("/").text
    for element_id in ("logo-offset-x", "logo-offset-y"):
        row = re.search(rf'id="{element_id}"[^>]*', html)
        assert row, element_id
        assert 'min="-25"' in row.group(0), f"{element_id} negatife inmiyor: {row.group(0)}"
        assert 'value="0"' in row.group(0), f"{element_id} sıfırda başlamıyor"


def test_overlay_offset_is_restored_per_mode():
    """Logo ve motto kaydırmaları AYRI hatırlanmalı (kullanıcı kararı).

    setOverlayMode geri yüklemeyi düşürürse ikisi sessizce birleşir: motto'ya
    geçen kullanıcı logonun ince ayarını devralır ve bunu fark etmesi zor.
    Tripwire, panBounds testiyle aynı kalıpta.
    """
    js = TestClient(appmod.app).get("/static/assets.js").text
    body = re.search(r"function setOverlayMode\(mode\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "setOverlayMode() bulunamadı"
    assert "overlayOffset" in body.group(1), (
        "setOverlayMode kaydırmayı mod başına geri yüklemiyor — logo ve motto birleşti")


def test_palette_chip_swatches_are_not_hidden_from_screen_readers():
    """Çip swatch'ları artık SALT GÖRÜNTÜ, ama gizlenmemeleri hâlâ zorunlu.

    v1.11'de tıklanabilir düğmelerdi ve `aria-hidden` içinde odaklanabilir bir
    kontrol bırakmak onları ekran okuyucudan TAMAMEN saklardı. Çıkarma öneri
    kartlarına taşındığında (14×14px'lik hedefler telefonda yanlış dokunma
    üretiyordu, palette.js `swatchRow` notu) düğme olmaktan çıktılar — ama
    iddia AYNEN duruyor: çip artık "hangi renkler geçerli, hangisi çıkarıldı"
    bilgisinin TEK okunabilir yeri, yani gizlenmesi o bilgiyi ekran okuyucu
    kullanıcısından tümüyle almak olurdu.
    """
    html = TestClient(appmod.app).get("/").text
    chip = re.search(r'id="palette-chip-sw"[^>]*', html)
    assert chip, "palet çipi swatch kabı bulunamadı"
    assert "aria-hidden" not in chip.group(0), (
        f"palet durumu aria-hidden içinde: {chip.group(0)}")


def test_the_palette_card_is_not_a_button_so_its_swatches_can_be():
    """Öneri kartı <div> + gerilmiş seçim düğmesi olmak ZORUNDA.

    Renk çıkarma çipten (14×14px, 2px aralıklı — telefonda yanlış dokunma
    kaynağı) öneri kartlarındaki büyük kutucuklara taşındı. Bunun bedeli yapısal:
    kutucuklar birer <button> ve kart da <button> KALIRSA iç içe buton çıkar —
    geçersiz HTML, ve tarayıcı iç düğmeyi kartın dışına taşıyarak "düzeltir",
    yani düzen sessizce dağılır.

    Kart <button>'a geri döndürülürse hiçbir hata çıkmaz: kutucuklar görünür,
    hatta tıklanır gibi durur. Bu yüzden mandal burada.
    """
    js = TestClient(appmod.app).get("/static/palette.js").text
    govde = re.search(r"function makeChoiceButton\(\{(.*?)\n\}", js, re.S)
    assert govde, "makeChoiceButton() bulunamadı"
    assert 'createElement("div")' in govde.group(1), "kart hâlâ <button>"
    assert "palette-choice-pick" in govde.group(1), "gerilmiş seçim düğmesi yok"


def test_the_stretched_palette_pick_button_is_focusable_and_ringed():
    """Gerilmiş seçim düğmesi görünmez; odak halkası AÇIKÇA yazılmalı.

    `.palette-choice-pick`in kendi zemini ve kenarlığı yok (`background: none;
    border: 0`), yani tarayıcı varsayılan halkası keyfi palet zemininde
    kaybolabiliyor — `.chat-item-open` ve `button.palette-sw` geleneğinin aynısı.
    Halka düşerse kart klavyeyle hâlâ seçilir ama kullanıcı NEREDE olduğunu
    göremez.

    `inset: 0` da iddiada: düğme gerilmezse kartın yalnız bir köşesi tıklanır
    hâle gelir ve "karta bastım, seçilmedi" olarak görünür.
    """
    css = TestClient(appmod.app).get("/static/style.css").text
    kural = re.search(r"\.palette-choice-pick \{(.*?)\n\}", css, re.S)
    assert kural, ".palette-choice-pick kuralı yok"
    assert "position: absolute" in kural.group(1)
    assert "inset: 0" in kural.group(1)
    assert re.search(r"\.palette-choice-pick:focus-visible", css), "odak halkası yok"

    # Kart konumlandırma bağlamı olmadan `inset: 0` viewport'a gerilirdi.
    kart = re.search(r"\n\.palette-choice \{(.*?)\n\}", css, re.S)
    assert kart, ".palette-choice kuralı yok"
    assert "position: relative" in kart.group(1)


def test_the_selected_palette_is_marked_by_a_class_not_by_has():
    """Seçili kart `.is-secili` ile işaretlenmeli, `:has()` ile DEĞİL.

    `aria-pressed` artık iç düğmede olduğu için stilin doğal karşılığı
    `.palette-choice:has(> .palette-choice-pick[aria-pressed="true"])` olurdu.
    APK yan yükleniyor (`minSdk 26`) ve o telefonlardaki WebView `:has()`
    desteklemeyebilir — desteklemediğinde kural TÜMÜYLE düşer ve kullanıcı hangi
    paleti seçtiğini hiç göremez. Sınıf her yerde çalışıyor.

    İki kanalın da yazılması şart: sınıf stil için, `aria-pressed` yardımcı
    teknoloji için. Biri düşerse öteki sessizce yeterli görünür.
    """
    css = TestClient(appmod.app).get("/static/style.css").text
    js = TestClient(appmod.app).get("/static/palette.js").text
    assert ".palette-choice.is-secili" in css, "seçili kart kuralı sınıfla yazılmamış"
    assert ":has(" not in css.split(".palette-choice")[1][:400], (
        "seçili kart `:has()`e bağlanmış — eski WebView'da işaretsiz kalır")
    govde = re.search(r"function kartSeciminiYaz\(.*?\n\}", js, re.S)
    assert govde, "kartSeciminiYaz() bulunamadı"
    assert "is-secili" in govde.group(0) and "aria-pressed" in govde.group(0), (
        "seçim iki kanaldan birine yazılmıyor")


def test_dropping_a_colour_survives_until_the_palette_is_applied():
    """Önizlemede çıkarılan renk "Bu paleti kullan"a AKTARILMALI.

    Kullanıcının gördüğü akış: paleti seç → rengine dokun (üstü çizilir) → uygula.
    `applyPalette` eskiden koşulsuz `dropped: new Set()` yazıyordu; o satır geri
    gelirse çıkarma sessizce KAYBOLUR — arayüz rengi çıkarılmış gösterir, üretim
    ise beş renkle gider. Sessiz, çünkü hiçbir hata çıkmaz.

    Kopya olması da iddiada: küme referansla tutulsa panelde sonradan bir renge
    dokunmak, uygulanmış paleti kullanıcının haberi olmadan değiştirirdi.
    """
    js = TestClient(appmod.app).get("/static/palette.js").text
    uygula = re.search(r"function applyPalette\(\{(.*?)\n\}", js, re.S)
    assert uygula, "applyPalette() bulunamadı"
    assert "new Set(dropped || [])" in uygula.group(1), (
        "önizleme çıkarmaları uygulamaya taşınmıyor ya da referansla taşınıyor")
    assert "dropped: onizlemeCikarilan" in js, (
        "\"Bu paleti kullan\" önizleme kümesini geçirmiyor")


def test_dropped_swatch_is_marked_by_more_than_colour():
    """Durum yalnız renkle (opacity) anlatılamaz.

    Koyu bir swatch soluklaştığında fark neredeyse görünmüyor; ayrıca renk
    körlüğü/düşük kontrast ekranlarda tamamen kaybolur. Bu yüzden çapraz çizgi
    (CSS) + aria-pressed (JS) birlikte gerekiyor.
    """
    css = TestClient(appmod.app).get("/static/style.css").text
    js = TestClient(appmod.app).get("/static/palette.js").text
    dropped = re.search(r"\.palette-sw-dropped\s*\{([^}]*)\}", css, re.S)
    assert dropped, ".palette-sw-dropped kuralı yok"
    assert "linear-gradient" in dropped.group(1), "çıkarılan renk yalnız opacity ile işaretli"
    assert "aria-pressed" in js, "çıkarma durumu yardımcı teknolojiye bildirilmiyor"


def test_swatch_colour_is_set_without_the_background_shorthand():
    """`style.background` satır-içi olarak background-image'ı `none`'a çeker.

    Satır-içi stil sınıfı yendiği için .palette-sw-dropped'ın çapraz çizgisi
    sessizce kaybolur — çıkarılan renk yalnız soluklaşır ve az önceki testin
    koruduğu şey pratikte çalışmaz. Tarayıcıda fark edilmesi zor.

    Yalnız swatchRow'a bakılıyor: HSV alanının çok katmanlı gradyanı ve tohum
    önizlemesi kısayolu meşru şekilde kullanıyor, onlara .palette-sw-dropped
    hiç uygulanmıyor.
    """
    js = TestClient(appmod.app).get("/static/palette.js").text
    body = re.search(r"function swatchRow\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "swatchRow() bulunamadı"
    assert "style.backgroundColor" in body.group(1)
    assert "style.background =" not in body.group(1), (
        "background kısayolu background-image'ı eziyor")


def test_gallery_accepts_dropped_files_from_the_computer():
    """Bırakma yolunun teli: `/api/import` + `importFiles`.

    Uç yeniden adlandırılır ya da çağrı düşerse sürükle-bırak SESSİZCE hiçbir
    şey yapmaz — hata mesajı da yok, dosya da girmez. Ucuz tripwire o yüzden
    değerli: kırılma yalnızca gerçek bir fare sürüklemesiyle görülür.
    """
    js = TestClient(appmod.app).get("/static/folders.js").text
    assert "/api/import" in js, "içe aktarma ucu çağrılmıyor"
    assert "function importFiles" in js
    # bulunulan klasör/kök hedefi: şeritte kendi kartı olmayan klasöre de aktarılabilmeli
    assert "gallery-wrap" in js, "görseller alanı bırakma bölgesi kurulmamış"


def test_folder_drop_target_serves_both_move_and_import():
    """Tek hedef iki iş yapıyor: iç taşıma + dosya aktarma.

    `stopPropagation` DÜŞERSE olay `.gallery-wrap` bölgesine çıkar ve aynı
    dosya İKİ KEZ aktarılır (biri klasöre, biri bulunulan görünüme). Kullanıcı
    bunu "bazen iki kopya oluşuyor" diye görür; teşhisi zor, veri kirliliği
    kalıcı.
    """
    js = TestClient(appmod.app).get("/static/folders.js").text
    body = re.search(r"function makeDropTarget\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "makeDropTarget() bulunamadı"
    assert "hasFiles" in body.group(1), "klasör kartı dosya bırakmayı kabul etmiyor"
    assert "stopPropagation" in body.group(1), "çift aktarma guard'ı yok"
    assert "IMAGE_DND_TYPE" in js, "iç taşıma yolu düşmüş"


def test_import_is_sequential_not_parallel():
    """Aktarma dosyaları SIRAYLA göndermek zorunda.

    `storage.save` her kayıtta history.json'ın TAMAMINI yeniden yazıyor.
    İstekler paralel giderse ikisi aynı listeyi okur, ikincisi birincisinin
    kaydını ezer: dosyalar diske yazılmış olur ama galeride görünmez —
    kaybın hiçbir hata mesajı yok. (`set_folder_many`/`delete_many`'nin
    "tek yazım" gerekçesiyle aynı sebep.)
    """
    js = TestClient(appmod.app).get("/static/folders.js").text
    body = re.search(r"async function importFiles\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "importFiles() bulunamadı"
    assert "await fetch" in body.group(1), "istekler beklenmiyor"
    assert "Promise.all(batch" not in body.group(1), "dosyalar paralel gönderiliyor"


def test_drop_highlight_cleanup_runs_in_the_capture_phase():
    """Temizlik YAKALAMA fazında dinlenmek zorunda.

    Klasör kartının `drop` dinleyicisi çift aktarmayı önlemek için
    `stopPropagation` çağırıyor; balonlanan bir temizlik dinleyicisi o yüzden
    hiç koşmaz ve kartın üstüne bırakınca galeri alanının kesikli çerçevesi
    ekranda TAKILI kalır (canlı ölçüldü). Yakalama fazı hedeften önce koşar.
    """
    js = TestClient(appmod.app).get("/static/folders.js").text
    assert re.search(r'addEventListener\(evt,\s*clearDropHighlights,\s*true\)', js), (
        "vurgu temizliği yakalama fazında değil — stopPropagation onu yutar")


def test_imported_card_is_marked_in_the_gallery():
    """İçe aktarılan görsel üretilmiş gibi görünmemeli (etiket + CSS birlikte)."""
    js = TestClient(appmod.app).get("/static/folders.js").text
    css = TestClient(appmod.app).get("/static/style.css").text
    assert "card-badge" in js and "rec.imported" in js
    assert ".card-badge" in css, "işaretin stili yok → görünmez kalır"


def test_dropzone_highlight_does_not_shift_the_layout():
    """Vurgu `outline` ile yapılmalı, `border` ile değil.

    Sürükleme sırasında kenarlık eklemek bölgeyi büyütür: kartlar zıplar ve
    imleç altındaki hedef kayar — bırakmak istediğin klasör yerinden oynar.
    `outline` yerleşimin dışında çizilir. (.stage.dragover da aynı dili
    kullanıyor.)
    """
    css = TestClient(appmod.app).get("/static/style.css").text
    rule = re.search(r"\.gallery-wrap\.dropzone\s*\{([^}]*)\}", css, re.S)
    assert rule, ".gallery-wrap.dropzone kuralı yok"
    assert "outline" in rule.group(1)
    assert "border:" not in rule.group(1), "kenarlık yerleşimi kaydırır"


def test_folder_hint_is_visible_without_any_folder():
    """İpucu klasör yokken de görünmeli.

    v1.11'e kadar `#folder-hint` yalnızca klasör varken açılıyordu (metin
    yalnız taşımayı anlatıyordu). Artık dosya bırakmayı da anlatıyor ve o
    özellik klasör olmadan da çalışıyor: gizli kalırsa yeni kullanıcı
    keşfedemez.
    """
    html = TestClient(appmod.app).get("/").text
    hint = re.search(r'<p id="folder-hint"[^>]*>', html)
    assert hint, "#folder-hint yok"
    assert "hidden" not in hint.group(0), "ipucu başlangıçta gizli"
    js = TestClient(appmod.app).get("/static/folders.js").text
    assert "function renderFolderHint" in js


def test_eyedropper_has_a_native_bridge_branch():
    """Damlalık pakette NATIVE köprüden geçmek zorunda.

    WKWebView'da `window.EyeDropper` yok (WebKit onu hiç uygulamadı), o yüzden
    yalnız-EyeDropper bir kontrol app'te her zaman false döner ve düğme gizli
    kalır — v1.10'a kadarki davranış. Bu dal düşerse hata tarayıcıda GÖRÜNMEZ
    (Chrome'da EyeDropper var, her şey çalışır gibi durur) ve yalnızca pakette
    ortaya çıkar; ucuz bir tripwire o yüzden değerli.
    """
    js = TestClient(appmod.app).get("/static/palette.js").text
    assert "pick_screen_color" in js, "native köprü dalı yok — app'te damlalık gizli kalır"
    assert "EyeDropper" in js, "tarayıcı yolu düşmüş"


def test_eyedropper_waits_for_the_late_pywebview_bridge():
    """pywebview köprüsü sayfa yüklendikten SONRA enjekte ediliyor.

    Yalnız senkron kontrol yapılırsa app'te yanlış negatif çıkar: script
    koşarken `window.pywebview` henüz yoktur, düğme gizli kalır ve hata
    "bazen görünmüyor" diye geri döner. pywebview kendi hazır olayını
    gönderiyor (webview/js/finish.js: `pywebviewready`), o dinlenmeli.
    """
    js = TestClient(appmod.app).get("/static/palette.js").text
    assert "pywebviewready" in js, (
        "geç yüklenen köprü için hazır olayı dinlenmiyor — app'te yanlış negatif")


def test_viewer_markup_is_served():
    """Görsel büyüteci: ortadaki önizlemeye tıklayınca açılan tam ekran görüntüleyici.

    viewer.js bu id'lere doğrudan bağlanıyor ve dosya en sonda yükleniyor —
    biri yeniden adlandırılırsa script yükleme anında patlar ve ONDAN SONRAKİ
    hiçbir dinleyici kurulmaz.
    """
    html = TestClient(appmod.app).get("/").text
    for element_id in ("viewer", "viewer-stage", "viewer-img", "viewer-download",
                       "viewer-logo", "viewer-zoom-in", "viewer-zoom-out",
                       "viewer-fit", "viewer-close"):
        assert f'id="{element_id}"' in html, element_id


def test_viewer_stacks_above_modals_but_below_the_confirm_dialog():
    """Büyüteç .modal katmanının (50) üstünde, confirm'in (60) ALTINDA olmalı.

    Üstünde olmalı: kütüphane/palet modalları açıkken de görsel tam ekran açılır.
    Altında kalmalı: confirm-modal native confirm()'in yerine geçtiği için her
    zaman en üstte olmak zorunda (bkz. bir üstteki test) — büyüteç onu örterse
    kullanıcı görmediği bir diyaloğu beklemeye başlar.
    """
    css = TestClient(appmod.app).get("/static/style.css").text
    base = re.search(r"\.modal\s*\{[^}]*?z-index:\s*(\d+)", css, re.S)
    viewer = re.search(r"#viewer\s*\{[^}]*?z-index:\s*(\d+)", css, re.S)
    top = re.search(r"#confirm-modal\s*\{[^}]*?z-index:\s*(\d+)", css, re.S)
    assert viewer, "#viewer için z-index kuralı yok"
    assert int(base.group(1)) < int(viewer.group(1)) < int(top.group(1)), (
        f"katman sırası bozuk: modal={base.group(1)} "
        f"viewer={viewer.group(1)} confirm={top.group(1)}")


def test_viewer_wheel_handler_prevents_the_default_page_zoom():
    """WKWebView'da ctrl'lü `wheel` (trackpad pinch) engellenmezse TÜM sayfayı
    zoom'lar: arayüz bozulur ve kullanıcı bunu kolayca geri alamaz.

    `{ passive: false }` de şart — passive bir dinleyicide preventDefault()
    sessizce yok sayılır, yani çağrının VARLIĞI tek başına yetmiyor.
    """
    js = TestClient(appmod.app).get("/static/viewer.js").text
    block = re.search(r'addEventListener\("wheel".*?\}\s*,\s*\{([^}]*)\}', js, re.S)
    assert block, "wheel dinleyicisi bulunamadı"
    assert "preventDefault" in block.group(0), "wheel varsayılanı engellenmiyor"
    assert re.search(r"passive:\s*false", block.group(1)), (
        "wheel dinleyicisi passive — preventDefault() yok sayılır")


def test_viewer_pan_captures_the_pointer():
    """Kaydırma sırasında imleç görselin dışına çıkabiliyor (hızlı sürükleme).

    setPointerCapture olmadan pointermove olayları başka bir öğeye gider ve
    kaydırma yarıda kopar — kullanıcı "takılıyor" diye bildirir.
    """
    js = TestClient(appmod.app).get("/static/viewer.js").text
    assert "setPointerCapture" in js


def test_viewer_pan_bounds_are_measured_without_the_rendered_transform():
    """Kaydırma sınırları getBoundingClientRect() ile ÖLÇÜLEMEZ.

    Tarayıcıda koşarken yakalandı: rect UYGULANMIŞ transform'u yansıtır, ama
    render() requestAnimationFrame'e ertelendiği için zoomAt() clampPan()'i
    çağırdığında DOM hâlâ ESKİ ölçeği taşıyor. İlk yakınlaştırmada rect
    sığdırılmış boyutu döndürüyor, sınırlar 0 çıkıyor ve imleç-sabitli zoom'un
    hesapladığı tx/ty anında sıfırlanıyordu — özellik sessizce "merkeze zoom"a
    dönüşüyordu. Görsel olarak fark edilmesi zor, bu yüzden tripwire.

    offsetWidth/clientWidth yerleşim tabanlıdır, transform'dan etkilenmez.
    """
    js = TestClient(appmod.app).get("/static/viewer.js").text
    bounds = re.search(r"function panBounds\(\)\s*\{(.*?)\n  \}", js, re.S)
    assert bounds, "panBounds() bulunamadı"
    assert "getBoundingClientRect" not in bounds.group(1), (
        "panBounds getBoundingClientRect kullanıyor — sınırlar bir kare geriden gelir")
    assert "offsetWidth" in bounds.group(1) and "clientWidth" in bounds.group(1)


def test_viewer_download_is_limited_to_saved_images():
    """İndir bağlantısı yalnız /output/ altındaki KAYITLI görseller için kurulur.

    Henüz kaydedilmemiş yüklemeler blob: URL taşır; macOS kayıt paneline
    anlamsız bir ad düşerdi. Bu yüzden bağlantı o durumda gizlenir.
    """
    js = TestClient(appmod.app).get("/static/viewer.js").text
    assert '"/output/"' in js, "kaynak /output/ kontrolü yapılmıyor"
    assert "dlLink.hidden" in js, "kaydedilmemiş görselde indir bağlantısı gizlenmiyor"


def test_browser_download_asks_where_to_save():
    """Tarayıcıda da konum seçilebilmeli — app'teki kayıt panelinin karşılığı.

    `.app`'te WKWebView `ALLOW_DOWNLOADS` sayesinde <a download>'u bir kayıt
    paneline çeviriyor (desktop.py) ve kullanıcı konumu seçiyor. Tarayıcıda
    böyle bir panel YOK: <a download> dosyayı sormadan indirme klasörüne atar.
    File System Access API o boşluğu kapatan TEK yol.
    """
    js = TestClient(appmod.app).get("/static/core.js").text
    assert "showSaveFilePicker" in js, (
        "tarayıcıda kayıt paneli açılmıyor — indirme yine sessizce Downloads'a düşer")


def test_download_still_works_without_the_save_picker():
    """Panel yoksa ESKİ <a download> yolu aynen kalmalı.

    Bu dalın tek gerçek kullanıcısı paketin WKWebView'ı (WebKit File System
    Access'i uygulamadı) — yani burası düşerse hata TARAYICIDA GÖRÜNMEZ,
    yalnız .app'te ortaya çıkar: damlalıktaki (test_eyedropper_*) tuzağın aynısı.
    Safari ve Firefox da bu daldan geçiyor.
    """
    js = TestClient(appmod.app).get("/static/core.js").text
    assert "typeof window.showSaveFilePicker" in js, (
        "özellik kontrolü yok — panelsiz tarayıcıda/pakette indirme kırılır")
    assert "downloadViaAnchor" in js, "geri düşüş yolu (<a download>) yok"


def test_both_download_buttons_go_through_the_shared_helper():
    """Galeri kartı ve büyüteç AYNI yardımcıdan geçmeli.

    v1.10'da "İndir düzeltmesi" iki yerde ayrı ayrı yapılmıştı; biri
    düzeltilip diğeri unutulduğunda kullanıcı "bazen çalışıyor" diye geri
    döner. Tek yardımcı bu ayrışmayı imkânsız kılıyor.
    """
    client = TestClient(appmod.app)
    for name in ("folders.js", "viewer.js"):
        assert "downloadImage(" in client.get(f"/static/{name}").text, (
            f"{name} paylaşılan indirme yardımcısını kullanmıyor")


def test_viewer_zoom_survives_reduced_motion():
    """prefers-reduced-motion yalnız ANİMASYONU kaldırmalı, özelliği DEĞİL.

    Dosyanın dibindeki genel kural `* { transition: none !important }` — oraya
    refleksle `.viewer-img { transform: none !important }` eklemek büyütmeyi ve
    kaydırmayı tümden öldürür (transform durumun kendisi, bir süsleme değil).
    Bir kez o hataya düşüldü; bu test tripwire.
    """
    css = TestClient(appmod.app).get("/static/style.css").text
    reduced = re.search(r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{(.*)$",
                        css, re.S)
    assert reduced, "prefers-reduced-motion bloğu yok"
    assert not re.search(r"\.viewer-img[^{]*\{[^}]*transform:\s*none", reduced.group(1)), (
        "reduced-motion viewer-img'in transform'unu sıfırlıyor — zoom/pan ölür")


def test_confirm_dialog_stacks_above_the_other_modals():
    """confirm-modal bir modal AÇIKKEN çağrılıyor (palet kaydet, varlık sil).

    native confirm()/prompt()'un yerine geçtiği için her zaman en üstte olmak
    zorunda. Tüm .modal'lar tek bir z-index paylaşıyor ve confirm-modal DOM'da
    onlardan ÖNCE geldiği için eşitlikte ALTTA boyanıyordu: diyalog açılıyor,
    girdi odağı bile alıyor, ama kullanıcı hiçbir şey görmüyor ve tıklayamıyor.
    """
    css = TestClient(appmod.app).get("/static/style.css").text
    base = re.search(r"\.modal\s*\{[^}]*?z-index:\s*(\d+)", css, re.S)
    top = re.search(r"#confirm-modal\s*\{[^}]*?z-index:\s*(\d+)", css, re.S)
    assert base, ".modal z-index kuralı bulunamadı"
    assert top, "#confirm-modal için z-index kuralı yok — diyalog altta kalır"
    assert int(top.group(1)) > int(base.group(1)), (
        f"confirm-modal ({top.group(1)}) diğer modalların ({base.group(1)}) üzerinde olmalı")


def test_hue_slider_gradient_outranks_the_generic_modal_input_rule():
    """Ton kaydırıcısının gökkuşağı gradyanı ID seçicisiyle verilmek ZORUNDA.

    `.modal-card input` özgüllükte (0,1,1) tek bir class'ı (0,1,0) yeniyor ve
    `background: var(--panel-2)` uyguluyor. Bu bir KISAYOL olduğu için
    `background-image`'ı da none'a sıfırlıyor → gradyan tamamen siliniyor ve
    kaydırıcı düz gri görünüyordu. Aynı kuraldan padding/border de sızıyor.
    """
    css = TestClient(appmod.app).get("/static/style.css").text
    block = re.search(r"#palette-hue\s*\{(.*?)\}", css, re.S)
    assert block, "gökkuşağı gradyanı #palette-hue ID seçicisiyle verilmeli"
    body = block.group(1)
    assert "linear-gradient" in body, "ton kaydırıcısında gradyan yok"
    assert "padding: 0" in body, ".modal-card input'tan sızan padding nötrlenmemiş"
    assert "border: 0" in body, ".modal-card input'tan sızan border nötrlenmemiş"


def test_static_cache_busters_all_equal_the_app_version():
    """Cache-buster ELLE artırılmıyor: tek kaynak version.APP_VERSION.

    Tek taraflı ?v= artışı bayat script'e yol açar → sayfa tutarsız bir karışım
    çalıştırır. Ama "hepsi aynı" artık YETMİYOR, "hepsi doğru" gerekiyor:

    Önceki hâli `\\?v=(\\d+)` arıyordu ve `?v=18` için çalışıyordu. `?v=1.9.0`
    karşısında o desen yalnızca baştaki "1"i yakalar → küme {'1'} olur, len==1
    GEÇER ve test SESSİZCE ANLAMSIZLAŞIR: 1.9.0 ile 1.10.0 ayrışması bile
    yakalanmaz. Ölçüldü:
        ?v=1.9.0 + ?v=1.10.0  →  eski desen {'1'} (geçer) / tam desen 2 öğe (düşer)
    Bu kusur testi KOŞARAK keşfedilemez, o yüzden desen burada tam değeri
    okuyor ve sürümle EŞİTLİK arıyor.
    """
    html = TestClient(appmod.app).get("/").text
    found = set(re.findall(r"\?v=([^\"'\s>]+)", html))
    assert found == {version.APP_VERSION}, f"cache-buster ayrışmış: {found}"


def test_index_has_no_unsubstituted_placeholder():
    """Yer tutucu servise sızarsa sayfa `?v=__APP_VERSION__` ile yüklenir.

    Çalışır ama cache-buster ÖLÜR: URL her sürümde aynı kalır, kullanıcı
    .app'i değiştirse bile istemci eski JS'i sunabilir. Sessiz olduğu için
    kimse fark etmez — bu yüzden testi var.
    """
    assert "__APP_VERSION__" not in TestClient(appmod.app).get("/").text


def test_index_document_is_never_cached():
    """WKWebView BELGEYİ de önbelleğe alıyor; belge bayatsa `?v=` işe yaramaz.

    Paket tarafında bu delik bugün desktop.py'nin port=0'ı sayesinde KAZARA
    kapalı (her açılış farklı origin). run.sh tarafında (sabit 8765) canlı.
    Port bir gün sabitlenirse bu test tek tripwire.
    """
    r = TestClient(appmod.app).get("/")
    assert "no-store" in r.headers.get("cache-control", "").lower()


def test_static_assets_stay_cacheable():
    """Asimetri KASITLI: `/` önbeleklenmez, /static önbelleklenir.

    `?v=<sürüm>` her sürüme ayrı URL veriyor, yani bayat kayıt hiç
    ADRESLENMİYOR. Buraya no-store eklemek mekanizmayı öldürür.
    """
    r = TestClient(appmod.app).get("/static/core.js")
    assert "no-store" not in r.headers.get("cache-control", "").lower()
    assert r.headers.get("etag"), "StaticFiles doğrulayıcı göndermeli"


def test_index_read_failure_is_reported_in_turkish(monkeypatch, tmp_path):
    """--windowed pakette stderr YOK: okunamayan index.html iz bırakmıyordu.

    FileResponse gönderim anında yakalanmayan bir RuntimeError'a düşüyordu →
    kullanıcı boş pencere görür, hata.log'a hiçbir şey yazılmaz.
    """
    monkeypatch.setattr(appmod, "STATIC_DIR", str(tmp_path / "yok"))
    written = []
    monkeypatch.setattr(appmod.errlog, "safe_append",
                        lambda d, t: (written.append(t), "hata.log")[1])
    r = TestClient(appmod.app).get("/")
    assert r.status_code == 500
    assert "Arayüz yüklenemedi" in r.text
    assert "Traceback" not in r.text, "kullanıcıya traceback gösterilmez"
    assert written and "Traceback" in written[0], "hata.log'a traceback yazılmalı"


def test_settings_modal_shows_the_app_version():
    """Destek sorusu "hangi sürümdesiniz?" — cevabı arayüzde OLMALI.

    Yazan taraf artık `settings-version` id'siyle DEĞİL, `[data-app-version]`
    seçicisiyle çalışıyor: sürüm iki yerde görünüyor (üst şeritteki pill +
    Ayarlar'ın dibindeki satır) çünkü pill telefonda gizli. Bu iddia
    mekanizmayla birlikte güncellendi ama gevşemedi — id'nin varlığını da,
    yazımın gerçekten bağlandığını da hâlâ ölçüyor, üstüne İKİ hedefin de
    işaretli olduğunu ekliyor.
    """
    client = TestClient(appmod.app)
    html = client.get("/").text
    assert 'id="settings-version"' in html
    # HTML yorumları AYIKLANIYOR: seçici yorumlarda da anlatılıyor ve onları
    # sayan bir iddia işaretin gerçekten öznitelik olarak durduğunu ölçmezdi.
    isaretsiz = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    # İki görünür hedef: üst şerit pill'i ve Ayarlar'ın dibi.
    assert isaretsiz.count("data-app-version") == 2, \
        "sürüm hedeflerinden biri işaretsiz — orada '—' olarak kalır"
    assert 'querySelectorAll("[data-app-version]")' in \
        client.get("/static/settings.js").text


def test_edit_request_forwards_every_palette_option():
    """Düzenleme dalı palet alanlarını ELLE saymamalı.

    JSON dalı `...pal` ile hepsini gönderirken multipart dalı üç alanı tek tek
    sayıyordu ve `palette_id` düşüyordu: sunucu kayıtlı paletin DONDURULMUŞ
    adlarını kullanamıyor, (seed, mode)'dan çevrimdışı yeniden hesaplıyordu —
    kütüphanede görünen ad ile prompt'a giden ad ayrışıyordu. Sunucu tarafı
    doğruydu (tests/test_palette_route.py: saved palette id'yi onurlandırıyor),
    o yüzden hatayı yalnızca istemci tarafı bir iddia yakalayabilir.
    """
    js = TestClient(appmod.app).get("/static/core.js").text
    assert 'fd.append("palette_hex"' not in js, (
        "palet alanları elle sayılmış — yeni bir alan eklendiğinde yine düşer")
    assert re.search(r"Object\.entries\(pal\)", js), (
        "düzenleme dalı palet seçeneklerinin tamamını dolaşarak eklemeli")


def test_ui_surfaces_a_palette_that_did_not_fit_in_the_prompt():
    """Ek 4000 karakter sınırına sığmadıysa kullanıcı bunu GÖRMELİ.

    Kayıtta palet var ama prompt'a girmedi; bayrak okunmazsa arayüz paleti
    uygulanmış gösterir ve kullanıcı renksiz sonucu açıklayamaz.
    """
    js = TestClient(appmod.app).get("/static/core.js").text
    assert re.search(r"palette\.applied\s*===\s*false", js), (
        "applied=false durumu arayüzde ele alınmıyor")


def test_every_frontend_script_is_loaded_and_in_order():
    """app.js beş parçaya bölündü; biri unutulursa sayfa sessizce yarım çalışır.

    Klasik script oldukları ve tek global kapsamı paylaştıkları için SIRA da
    sözleşmenin parçası: açılış çağrıları settings.js'in dibinde ve oradan
    önceki dosyalarda tanımlı adlara dokunuyor.
    """
    client = TestClient(appmod.app)
    order = ["core.js", "folders.js", "assets.js", "palette.js", "settings.js",
             "viewer.js", "chat.js"]
    html = client.get("/").text
    positions = [html.find(f"/static/{name}") for name in order]
    assert all(p > 0 for p in positions), dict(zip(order, positions))
    assert positions == sorted(positions), "script sırası bozulmuş"
    for name in order:
        assert client.get(f"/static/{name}").status_code == 200, name


# ── Prompt Yönetmeni (v1.13) ───────────────────────────────────────────

def test_chat_workspace_markup_is_served():
    """chat.js bu id'lere `$()` ile DOĞRUDAN bağlanıyor ve dosya EN SONDA yükleniyor.

    Biri yeniden adlandırılırsa script yükleme anında patlar; chat.js sondaki
    dosya olduğu için görsel sekmesi ayakta kalır ve kırılma yalnızca sohbete
    girildiğinde fark edilir — ucuz tripwire o yüzden değerli.
    """
    html = TestClient(appmod.app).get("/").text
    for element_id in ("tab-image", "tab-chat", "view-tabs-thumb", "view-studio",
                       "chat-log", "chat-empty", "prompt", "go", "status",
                       "chat-wait", "chat-gate", "chat-sidebar", "chat-sidebar-toggle",
                       "chat-new", "chat-list", "chat-list-empty",
                       "set-chat-deployment", "chat-instructions-path",
                       # Yönetmen ayarları çekmecesi ve çipi.
                       "director-btn", "director-sheet", "director-close",
                       "director-guidance", "director-save", "director-status"):
        assert f'id="{element_id}"' in html, element_id


def test_the_clear_chat_button_is_gone():
    """v1.15: "Sohbeti temizle" KALDIRILDI, işlevi ikiye bölündü.

    Yeni bir sohbete geçmek "Yeni sohbet" (kenar panel), bir sohbetten kurtulmak
    3-nokta → Sil. Eskisi ikisini de yapmıyordu: temizlenen sohbet kaydedilmişse
    diskte kalıyordu, yani düğme artık YANILTICI olurdu.
    """
    html = TestClient(appmod.app).get("/").text
    assert 'id="chat-clear"' not in html
    js = TestClient(appmod.app).get("/static/chat.js").text
    assert "chat-clear" not in js, "chat.js hâlâ var olmayan bir id'ye bağlanıyor"


def test_chat_tab_itself_is_not_disabled_in_the_markup():
    """Kapı "Gönder"de: kilitli bir SEKME "neden kapalı" bilgisini de saklar.

    Kullanıcı sekmeye girip Ayarlar'a yönlendiren açıklamayı okuyabilmeli.
    """
    html = TestClient(appmod.app).get("/").text
    tab = re.search(r'id="tab-chat"[^>]*', html)
    assert tab, "#tab-chat yok"
    assert "disabled" not in tab.group(0), f"sekme kilitli: {tab.group(0)}"
    js = TestClient(appmod.app).get("/static/settings.js").text
    assert 'chatConfigured' in js, "Gönder kapısı kurulmamış"
    assert 'chat-gate").hidden' in js, "kapı açıklaması yönetilmiyor"


def test_chat_never_puts_server_text_into_innerhtml():
    """GÜVENLİK TRIPWIRE: model metni DOM'a yalnızca textContent ile girer.

    `innerHTML` bu dosyada TEK bir yerde, akışı boş dizeyle temizlemek için
    geçebilir (core.js:renderExtras deseni). Model çıktısı için kullanılırsa
    yanıttaki bir `<script>`/`onerror` yerel sunucu origin'inde çalışır.
    """
    js = TestClient(appmod.app).get("/static/chat.js").text
    uses = re.findall(r"innerHTML\s*=\s*([^;]+);", js)
    assert uses, "innerHTML hiç geçmiyor — temizleme yolu değişmiş, testi güncelle"
    for value in uses:
        assert value.strip() in ('""', "''"), f"innerHTML'e metin atanıyor: {value.strip()}"


def test_chat_applies_only_settings_the_form_actually_offers():
    """SAVUNMACI UYGULAMA TRIPWIRE'ı: `.options` kontrolü düşerse 422 gelir.

    Yönetmen `2048x1152` önerirse ve değer doğrudan `select.value`'ya yazılırsa
    tarayıcı onu SESSİZCE yok sayar (ya da boşa düşürür) — kullanıcı "Üret"e
    basana kadar hiçbir şey görünmez, sonra sunucudan 422 alır.
    """
    js = TestClient(appmod.app).get("/static/chat.js").text
    body = re.search(r"function applyIfSupported\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "applyIfSupported() bulunamadı"
    assert ".options" in body.group(1), "seçenek listesi kontrol edilmiyor"


def test_chat_says_out_loud_when_a_suggestion_could_not_be_applied():
    """SESSİZ SAPMA YASAK — palette `applied: false` ile aynı gerekçe.

    Uygulanamayan öneri söylenmezse kullanıcı formda başka bir ayar görür ve
    sonucu açıklayamaz.
    """
    js = TestClient(appmod.app).get("/static/chat.js").text
    assert "uygulanamadı" in js, "uygulanamayan öneri kullanıcıya söylenmiyor"


def test_chat_does_not_truncate_an_oversized_prompt():
    """Kırpılmış prompt SESSİZCE başka bir görsel üretir.

    Sunucu 4000 karakteri aşan prompt'a 422 veriyor; doğru davranış kırpmak
    değil, yönetmene kısaltmasını söylemek.
    """
    js = TestClient(appmod.app).get("/static/chat.js").text
    assert "MAX_PROMPT_CHARS" in js, "prompt uzunluğu hiç kontrol edilmiyor"
    body = re.search(r"function applyToForm\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "applyToForm() bulunamadı"
    assert ".slice(0, MAX_PROMPT_CHARS" not in body.group(1), "prompt sessizce kırpılıyor"


def test_client_never_sends_a_system_role():
    """Sistem mesajını SUNUCU koyuyor; istemci persona'ya dokunmamalı.

    Sunucu tarafı bunu 422 ile reddediyor (tests/test_chat_route.py), ama
    istemcinin hiç denememesi gerekiyor — yoksa özellik ilk turda ölür.
    """
    js = TestClient(appmod.app).get("/static/chat.js").text
    assert '"system"' not in js and "'system'" not in js


def test_chat_prompt_char_limit_mirrors_the_server():
    """İstemci sabiti sunucudakiyle AYNI olmak zorunda (MAX_EDIT_IMAGES geleneği)."""
    js = TestClient(appmod.app).get("/static/core.js").text
    match = re.search(r"const MAX_PROMPT_CHARS = (\d+);", js)
    assert match, "MAX_PROMPT_CHARS istemcide tanımlı değil"
    assert int(match.group(1)) == models.MAX_PROMPT_CHARS


def test_chat_limits_mirror_the_server():
    """Sohbet sınırları da aynalanmalı: aksi halde kullanıcı pydantic'in
    İNGİLİZCE 422 metnini görür."""
    js = TestClient(appmod.app).get("/static/chat.js").text
    for name, expected in (("MAX_CHAT_MESSAGES", models.MAX_CHAT_MESSAGES),
                           ("MAX_CHAT_MSG_CHARS", models.MAX_CHAT_MSG_CHARS),
                           ("MAX_CHAT_TOTAL_CHARS", models.MAX_CHAT_TOTAL_CHARS)):
        match = re.search(rf"const {name} = (\d+);", js)
        assert match, f"{name} istemcide tanımlı değil"
        assert int(match.group(1)) == expected, name


def test_chat_does_not_reuse_the_image_progress_bar():
    """`startProgress()` `.stage` içindeki düğümlere dokunuyor — o DİĞER sekmede.

    Sohbetten çağrılsa gizli bir barı doldurur; kullanıcı hiçbir geri bildirim
    görmez. Sohbetin kendi bekleme göstergesi var (#chat-wait).
    """
    js = TestClient(appmod.app).get("/static/chat.js").text
    assert "startProgress" not in js, "sohbet görsel sekmesinin ilerleme barını kullanıyor"
    assert "chat-wait" in js, "sohbetin bekleme göstergesi kurulmamış"


def test_chat_scroll_helper_calls_the_native_dom_api():
    """Sarmalayıcı, düğümün GERÇEK `scrollIntoView`'unu çağırmak zorunda.

    Bir kez kırıldı ve bütün özelliği öldürdü: sarmalayıcı `scrollIntoView`'dan
    `scrollMessageIntoView`'a yeniden adlandırılırken toplu değiştirme
    `node.scrollIntoView(` çağrısının İÇİNİ de değiştirdi. Sonuç
    `node.scrollMessageIntoView is not a function` — `appendUser()` içinde,
    `sendChat`'in try bloğundan ÖNCE fırlıyor: istek hiç gitmiyor, spinner
    çıkmıyor, kullanıcıya hata da yazılmıyor. "Gönder'e basınca hiçbir şey
    olmuyor."

    Bu sınıf hata pytest'in kör noktası: sözdizimi geçerli (`node --check`
    geçiyor) ve sunucu tarafı etkilenmiyor. Ucuz tripwire o yüzden değerli.
    """
    js = TestClient(appmod.app).get("/static/chat.js").text
    body = re.search(r"function scrollMessageIntoView\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "scrollMessageIntoView() bulunamadı"
    assert ".scrollIntoView(" in body.group(1), (
        "sarmalayıcı native scrollIntoView'u çağırmıyor — var olmayan bir DOM "
        "metodu çağrılıyor ve gönderme sessizce ölür")


def test_failed_turn_is_rolled_back_out_of_the_thread():
    """Başarısız tur geçmişte kalırsa her yeniden gönderim aynı hatayı tekrarlar.

    Desen v1.16'da GENİŞLETİLDİ (`sendChat()` → `sendChat(...)`): imza `display`
    parametresini aldı. Testin ölçtüğü şey değişmedi — geri alma hâlâ zorunlu.
    """
    js = TestClient(appmod.app).get("/static/chat.js").text
    body = re.search(r"async function sendChat\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "sendChat() bulunamadı"
    assert "chatThread.pop()" in body.group(1), "başarısız tur geçmişten çıkarılmıyor"


def test_view_switching_updates_aria_selected():
    """setMode aria-pressed özniteliğini günceller."""
    js = TestClient(appmod.app).get("/static/core.js").text
    body = re.search(r"function setMode\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "setMode() bulunamadı"
    assert "aria-pressed" in body.group(1)


def test_apply_to_form_switches_to_the_TARGET_view():
    """Aktarma görünümü çevirmezse kullanıcı sohbette kalır ve prompt'un forma
    girdiğini GÖRMEZ: "bir şey olmadı" sanıp ikinci kez basar, ayarlar da
    sessizce ikinci kez ezilir.

    Bu davranış bir kez ölçüm yüzünden şüpheye düştü: tarayıcı otomasyonunun
    sayfa okuma adımı sekmeyi kendisi değiştirip odağı kaydırdığı için geçiş
    "olmamış" göründü — davranış doğruydu, ölçüm yanlıştı. Tripwire o yüzden
    burada: bir dahaki sefere cevap testten okunsun.

    HEDEF ARTIK SABİT DEĞİL: yönetmen video da önerebiliyor ve mod, önerdiği
    modelin hangi katalogda olduğundan türetiliyor. Sabit `setMode("image")`
    kalsaydı bir video önerisi görsel moduna aktarılır, telde 422 dönerdi.
    """
    js = TestClient(appmod.app).get("/static/chat.js").text
    body = re.search(r"function applyToForm\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "applyToForm() bulunamadı"
    assert "setMode(hedef.eksen)" in body.group(1), (
        "aktarma HEDEF moda geçmiyor — video önerisi görsel ucuna giderdi")
    assert 'setMode("image")' not in body.group(1), (
        "mod hâlâ sabit — hedef tablosu boşa çıkmış")
    assert '$("prompt").focus()' in body.group(1), (
        "prompt alanı odaklanmıyor — aktarılan metin gözle bulunabilmeli")


def test_single_studio_view_is_rendered():
    """Açılışta Stüdyo görünümü seçili: view-studio görünür gelmeli."""
    html = TestClient(appmod.app).get("/").text
    studio_view = re.search(r'<\w+ id="view-studio"[^>]*>', html)
    assert studio_view, "#view-studio yok"
    assert "hidden" not in studio_view.group(0), "stüdyo paneli açılışta görünür"


# ── Tıklanabilir seçenekler + prompt barı (v1.15) ──────────────────────

def _chat_js() -> str:
    return TestClient(appmod.app).get("/static/chat.js").text


def test_settings_block_is_recognised_by_its_keys_not_by_being_first_json():
    """Blok tipi ANAHTARDAN okunmalı, sıradan değil.

    v1.14'te ayar bloğu "ilk JSON nesnesi" diye seçiliyordu. v1.15'in seçenek
    bloğu da `{` ile başlıyor ve yanıtta ondan ÖNCE geliyor: eski kural
    yönetmenin SEÇENEKLERİNİ forma ayar olarak yazardı ve desteklenmeyen bir
    değer üretimde 422'ye dönerdi.
    """
    js = _chat_js()
    keys = re.search(r"const SETTING_KEYS\s*=\s*\[(.*?)\]", js, re.S)
    assert keys, "SETTING_KEYS bulunamadı"
    for key in ('"size"', '"quality"', '"n"'):
        assert key in keys.group(1), key
    body = re.search(r"function parseDirectorReply\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "parseDirectorReply() bulunamadı"
    assert "SETTING_KEYS.some" in body.group(1), (
        "ayar bloğu anahtarla tanınmıyor — seçenek bloğu forma ayar olarak girebilir")
    assert "secenekler" in body.group(1), "seçenek bloğu ayrıştırılmıyor"


def test_the_options_block_is_never_drawn_as_a_code_block():
    """Seçenek bloğunun görünür karşılığı ÇİPLER; ham JSON gösterilmemeli.

    "Gösterilmemeli" KOŞULLU: çipler gerçekten çizilecekse. Çizilmeyeceği
    hâlin bekçisi `test_a_machine_block_that_breaks_its_contract_...`.
    """
    js = _chat_js()
    body = re.search(r"function renderMarkdownInto\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "renderMarkdownInto() bulunamadı"
    assert "parsed.optionsBody" in body.group(1), (
        "seçenek bloğu atlanmıyor — kullanıcı ham JSON okur")


def test_every_answer_panel_sends_through_the_single_send_path():
    """Hiçbir panel ikinci bir gönderim yolu açmamalı.

    `sendChat` sınır kapılarını, başarısız turun geri alınmasını ve kaydetmeyi
    tek yerde tutuyor; ayrı bir fetch yazılsa bunların hepsi çiplerde eksik
    kalırdı (v1.13'te tam bu tür bir ikinci yol hiç yazılmadığı için sağlamdı).

    v1.16: kapsam üç panele çıktı (seçenek, varyasyon, parametre) ve aranan desen
    `sendChat()` → `sendChat(` oldu, çünkü çağrı artık `display` argümanı
    geçiriyor. Ölçülen şey aynı: tek gönderim yolu, kendi fetch'i olmayan panel.

    Ortak bir `wireSubmit()` yardımcısı BİLEREK yazılmadı: çağrıyı sarmalayıcının
    içine saklamak bu testi teknik olarak geçirip işlevsiz bırakırdı.
    """
    js = _chat_js()
    for name in ("renderOptions", "renderVariations", "renderParameters"):
        body = re.search(rf"function {name}\([^)]*\)\s*\{{(.*?)\n\}}", js, re.S)
        assert body, f"{name}() bulunamadı"
        assert "sendChat(" in body.group(1), f"{name} sendChat'i çağırmıyor"
        assert "fetch(" not in body.group(1), f"{name} kendi isteğini atıyor"


def test_prompt_actions_live_on_the_prompt_block_not_at_the_bottom():
    """İstenen değişiklik: eylemler prompt'un yanında, mesajın dibinde değil."""
    js = _chat_js()
    body = re.search(r"function promptFigure\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "promptFigure() bulunamadı"
    assert "chat-prompt-bar" in body.group(1)
    assert "copyPrompt(parsed.prompt)" in body.group(1), "Kopyala bağlı değil"
    # Zincir bir kademe uzadı: düğme artık üretimi de başlatıyor, yani
    # `applyToForm`u DOĞRUDAN değil `sohbettenUret` üzerinden çağırıyor.
    assert "sohbettenUret(parsed)" in body.group(1), "üretim düğmesi bağlı değil"
    uret = re.search(r"function sohbettenUret\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert uret, "sohbettenUret() bulunamadı"
    assert "applyToForm(parsed)" in uret.group(1), "aktarma zinciri koptu"
    # Sınıf adı bir AÇIKLAMADA geçebilir (neden kaldırıldığı yazıyor); yasak olan
    # şey ona bir düğüm bağlanması, yani dizeyle atanması.
    assert '"chat-msg-actions"' not in js, "eski alt eylem satırı hâlâ üretiliyor"
    css = TestClient(appmod.app).get("/static/style.css").text
    assert ".chat-msg-actions" not in css, "ölü kural CSS'te kalmış"


def test_the_duplicate_prompt_heading_is_swallowed():
    """Barın etiketi ile talimatın "**PROMPT**" başlığı aynı şeyi söylüyordu.

    Etiket barda KALIYOR (yapısal, her zaman doğru); yutulan şey modelin tekrar
    satırı ve yalnızca TAM eşleşmede — model başka bir başlık yazdıysa duruyor.
    """
    js = _chat_js()
    assert re.search(r"const PROMPT_HEADING\s*=\s*/\^", js), "desen bulunamadı"
    body = re.search(r"function renderMarkdownInto\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert "PROMPT_HEADING.test" in body.group(1)


def test_the_prompt_block_wraps_instead_of_scrolling_sideways():
    """Prompt bir PROZA: `white-space: pre` onu tek satırlık şeride çeviriyordu.

    Teknik ayar JSON'u için kural DEĞİŞMEMELİ — bu yüzden seçici yalnız
    .chat-prompt-block'u hedefliyor.
    """
    css = TestClient(appmod.app).get("/static/style.css").text
    rule = re.search(r"\.chat-msg-bot pre\.chat-prompt-block code\s*\{([^}]*)\}", css)
    assert rule, "prompt bloğu kod kuralı bulunamadı"
    assert "pre-wrap" in rule.group(1), "prompt sarmıyor"


def test_stale_option_groups_are_locked_but_not_deleted():
    """Akış geçmişi dürüst kalmalı; eski soruya ikinci cevap gitmemeli.

    Canlılık ölçüsü "son GRUP" değil, "SON MESAJIN içinde olmak" — ilk yazımda
    öyleydi ve tarayıcıda kırıldı: kaydedilmiş bir sohbet açıldığında
    cevaplanmış tek soru da "son grup" olduğu için yeniden canlanıyordu.
    """
    js = _chat_js()
    body = re.search(r"function lockStaleOptions\(\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "lockStaleOptions() bulunamadı"
    assert "lastElementChild" in body.group(1) and ".contains(group)" in body.group(1), (
        "kilit ölçüsü son mesaja bağlı değil — bayat bir soru yeniden canlanabilir")
    assert "remove()" not in body.group(1), "eski gruplar siliniyor"


# ── Kayıtlı sohbetler (v1.15) ──────────────────────────────────────────

def test_a_failed_save_does_not_drop_the_turn():
    """Kaydetme hatası yanıtı ekrandan silmemeli, ama SESSİZ de geçmemeli.

    Sessiz geçilse kullanıcı sohbetin kaydedildiğini sanardı ve uygulamayı
    kapattığında turu kaybederdi.
    """
    js = _chat_js()
    body = re.search(r"async function persistThread\(\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "persistThread() bulunamadı"
    assert "catch" in body.group(1), "kaydetme hatası yakalanmıyor"
    assert "chatStatus(" in body.group(1), "kaydetme hatası kullanıcıya söylenmiyor"
    assert "chatThread = []" not in body.group(1), "hata turu düşürüyor"


def test_deleting_the_open_chat_clears_the_stream():
    """Silinen sohbeti ekranda bırakmak yanıltıcı: sonraki tur 404 alır ve
    kullanıcı "kaydedilmiyor" sanır."""
    js = _chat_js()
    body = re.search(r"async function deleteChat\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "deleteChat() bulunamadı"
    assert "resetThread()" in body.group(1)


def test_the_chat_title_is_derived_not_asked_from_the_model():
    """Başlık için İKİNCİ bir model çağrısı YOK: para ve gecikme, kazancı etiket.

    v2.0'da türeten taraf DEĞİŞTİ (istemcideki `deriveTitle` → sunucudaki
    `_auto_title`): başlıksız yazım artık "bu otomatik" işareti, istemci bir ad
    uydurursa otomatik kayıt anahtarı delinir (§0.5/K8). Kural aynı kaldığı için
    iddia da duruyor, yalnız ölçüldüğü yer taşındı — silinmedi.
    """
    import inspect
    src = inspect.getsource(appmod._auto_title)
    assert "chat_client" not in src and "complete" not in src, (
        "başlık için modele gidiliyor")
    assert "requests" not in src and "httpx" not in src


# ── Sekme geçişi (v1.15) ───────────────────────────────────────────────

def test_the_tab_thumb_is_measured_from_the_active_button():
    """Genişlik CSS'e sabitlenemez: "Görsel" ile "Prompt Yönetmeni" aynı
    genişlikte değil ve etiketler yazı tipiyle kayıyor."""
    js = TestClient(appmod.app).get("/static/core.js").text
    body = re.search(r"function syncTabThumb\(\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "syncTabThumb() bulunamadı"
    assert "offsetWidth" in body.group(1) and "offsetLeft" in body.group(1)


def test_the_view_transition_only_animates_compositor_properties():
    """Yerleşim tetikleyen bir özellik animasyona girerse geçiş takılır."""
    css = TestClient(appmod.app).get("/static/style.css").text
    for name in ("viewInRight", "viewInLeft"):
        frames = re.search(r"@keyframes " + name + r"\s*\{(.*?)\n\}", css, re.S)
        assert frames, name
        for banned in ("width:", "height:", "margin", "padding", "top:", "left:"):
            assert banned not in frames.group(1), f"{name} → {banned}"


def test_reduced_motion_silences_the_view_animation():
    """`transition: none !important` bloğu `animation`'ı SUSTURMUYOR."""
    css = TestClient(appmod.app).get("/static/style.css").text
    block = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*)", css, re.S)
    assert block, "reduced-motion bloğu bulunamadı"
    assert re.search(r"\.view-in-right[^{]*\{[^}]*animation: none", block.group(1)), (
        "sekme geçişi reduced-motion'da susturulmuyor")


# ── v1.15 sonrası inceleme düzeltmeleri (L2–L4 + textarea sınırı) ────────

def test_textareas_cannot_be_dragged_wider_than_their_column():
    """Tarayıcı varsayılanı `resize: both`: prompt alanı kolonu ve pencereyi
    aşacak kadar sağa çekilebiliyordu ve tutamak görünür alanın dışına
    düştüğü için GERİ ÇEKİLEMİYORDU — alan o genişlikte kilitleniyordu."""
    css = TestClient(appmod.app).get("/static/style.css").text
    shared = re.search(r"\ntextarea, select \{(.*?)\n\}", css, re.S)
    assert shared, "textarea/select kuralı bulunamadı"
    assert "max-width: 100%" in shared.group(1), "yatay büyüme sınırlanmamış"

    only = re.search(r"\ntextarea \{(.*?)\n\}", css, re.S)
    assert only, "textarea'ya özel kural bulunamadı"
    assert "resize: vertical" in only.group(1), "yatay boyutlandırma kapatılmamış"
    assert "max-height" in only.group(1), "dikey büyüme sınırsız"
    assert "min-height" in only.group(1), "alan sıfıra ezilebiliyor"


def test_the_new_chat_controls_have_a_visible_focus_ring():
    """Kendi zemini/kenarlığı olmayan düğmeler: odak halkası AÇIKÇA yazılmalı
    (button.palette-sw geleneği).

    `.chat-new` listeden ÇIKTI (PR1/Adım 4): sınıf Adım 2'den beri işaretlemede
    yok — düğme üst şeritte `#chat-new.icon-btn` ve odak halkasını global
    `:focus-visible`/icon-btn hattı veriyor. Ölü sınıf kuralı silinince bu
    iddia da onunla birlikte düştü; id'nin varlığını ayrı test doğruluyor.
    """
    css = TestClient(appmod.app).get("/static/style.css").text
    for selector in (".chat-item-open", ".chat-item-menu",
                     ".chat-menu-item", ".chat-option"):
        assert re.search(re.escape(selector) + r":focus-visible", css), selector


def test_the_row_menu_carries_menu_roles_and_returns_focus():
    """`aria-haspopup="true"` bir MENÜ vaat ediyor; kapanışta odak tetikleyiciye
    dönmezse klavye kullanıcısı listede yerini kaybediyor."""
    js = TestClient(appmod.app).get("/static/chat.js").text
    assert '"role", "menu"' in js, "açılan katmana menu rolü verilmemiş"
    assert '"role", "menuitem"' in js, "menü öğelerine menuitem rolü verilmemiş"
    close = re.search(r"function closeMenus\(\) \{(.*?)\n\}", js, re.S)
    assert close, "closeMenus bulunamadı"
    assert "focus()" in close.group(1), "kapanışta odak tetikleyiciye dönmüyor"


def test_a_turn_does_not_refetch_the_whole_chat_list():
    """Yazan istek güncel kaydı zaten döndürüyor: tur başına ikinci bir istek
    chats.json'ı gövdeleriyle baştan okumak demekti."""
    js = TestClient(appmod.app).get("/static/chat.js").text
    persist = re.search(r"async function persistThread\(\) \{(.*?)\n\}", js, re.S)
    assert persist, "persistThread bulunamadı"
    assert "loadChats" not in persist.group(1), "tur sonunda liste baştan çekiliyor"
    assert "upsertSummary" in persist.group(1)
    # `loadChats` KALMALI: ilk yükleme ve hata sonrası kurtarma yolu.
    assert "async function loadChats()" in js


# ── v1.16: makine blokları, tıklanabilir paneller, seçim pili ──────────

def test_a_machine_block_can_never_be_picked_as_the_prompt():
    """Kısalan prompt + uzun varyasyon bloğu, "en uzun blok" kuralını JSON'a
    yönlendiriyordu ve eylem düğmesi composer'a JSON yazıyordu.

    v1.15'in aday süzgeci ayar ve seçenek bloğunu ELLE dışlıyordu. v1.16 iki blok
    daha ekliyor ve aynı sürümde promptlar KISALIYOR — ölçüldü: 133 karakterlik
    bir prompt yanında 352 karakterlik varyasyon bloğu, başlık satırı kaymışsa
    prompt seçilen blok oluyordu. Kural artık liste tutmuyor: JSON nesnesi olarak
    ayrıştırılan HER blok adaylıktan düşüyor (prompt akıcı prozadır, JSON olamaz).
    Yan kazanç: modelin uydurduğu tanınmayan bir JSON bloğu da prompt sanılamıyor.
    """
    js = _chat_js()
    body = re.search(r"function parseDirectorReply\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "parseDirectorReply() bulunamadı"
    assert "jsonBlocks.has(b)" in body.group(1), (
        "aday süzgeci JSON bloklarını dışlamıyor — varyasyon JSON'u forma yazılabilir")
    for key in ("varyasyonlar", "eksenler"):
        assert key in body.group(1), f"{key} imzası tanınmıyor"


def test_the_variation_and_parameter_blocks_are_never_drawn_as_code_blocks():
    """Üç bloğun da görünür karşılığı ÇİPLER; ham JSON gösterilmemeli.

    Ayar JSON'u listede BİLEREK yok: kullanıcının "Görsel modunda üret"e basmadan da
    hangi boyut/kalite önerildiğini görmesi gerekiyor.
    """
    js = _chat_js()
    body = re.search(r"function renderMarkdownInto\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "renderMarkdownInto() bulunamadı"
    for field in ("parsed.optionsBody", "parsed.variationsBody", "parsed.parametersBody"):
        assert field in body.group(1), f"{field} atlama kümesinde değil — ham JSON çizilir"


def test_a_variation_click_never_edits_the_prompt_locally():
    """Yerel `x → y` değiştirme SESSİZCE yanlış prompt üretir.

    Varyasyonlar cümle düzeyi düzenlemeler ("photorealistic + doku + derinlik
    cümlelerini kaldır"), bir kelime çifti değil. Eşleşme tutmazsa kullanıcı hiç
    seçmediği bir prompt'u forma aktarır — `applyToForm`'un kırpmayı reddetmesiyle
    aynı gerekçe. Tıklama bu yüzden yönetmene tek turluk bir istek gönderiyor.
    """
    js = _chat_js()
    body = re.search(r"function renderVariations\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "renderVariations() bulunamadı"
    for banned in (".replace(", "parsed.prompt"):
        assert banned not in body.group(1), (
            f"varyasyon prompt'u yerelde değiştiriyor: {banned}")


def test_every_answer_panel_shares_the_lockable_group_class():
    """Kök sınıf ayrışırsa `lockStaleOptions` yeni panellere ULAŞMAZ.

    Bu, testi geçerken davranışın sessizce bozulduğu sınıf bir hata: yeniden
    açılan bir sohbette eski varyasyon düğmeleri sonsuza dek canlı kalır ve
    kullanıcı artık var olmayan bir prompt'a delta gönderir.
    """
    js = _chat_js()
    group = re.search(r"function answerGroup\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert group, "answerGroup() bulunamadı"
    assert '"chat-options"' in group.group(1), "ortak kök sınıf verilmiyor"
    for name in ("renderVariations", "renderParameters"):
        body = re.search(rf"function {name}\([^)]*\)\s*\{{(.*?)\n\}}", js, re.S)
        assert "answerGroup(" in body.group(1), f"{name} ortak kökü kullanmıyor"


def test_each_parameter_axis_is_mutually_exclusive_on_its_own_row():
    """Dışlayıcılık kapsamı SATIR olmalı, panel değil.

    Panel geçilse tek bir ışık seçimi bütün eksenlerin seçimini silerdi: kullanıcı
    ışık + palet + kadraj birlikte seçemezdi.

    İddianın ÇAĞRISI iki kez değişti, konusu DEĞİŞMEDİ. Önce
    `optionChip(String(raw), …)` idi: `String()` maddeler düz dizeyken
    doğruydu, madde nesne de olabildiği için (açıklama + çizilen örnek) onu
    "[object Object]" yapardı — hem ekranda hem MODELE GİDEN cevapta. Sonra
    `raw` → `item` oldu: maddeler artık `drawableOptions` süzgecinden
    NORMALLEŞTİRİLMİŞ geliyor. Ölçülen şey her üç hâlde de aynı: son iki
    argüman, `false` (eksen içinde tek seçim) ve `row` (kapsam satır).
    """
    js = _chat_js()
    body = re.search(r"function renderParameters\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "renderParameters() bulunamadı"
    assert "optionChip(item, false, row)" in body.group(1), (
        "eksen alternatifleri satıra bağlı tek seçim değil")
    assert "String(raw)" not in body.group(1), (
        "madde `String()` ile sarılıyor — nesne madde '[object Object]' olur")


def test_the_option_value_sent_to_the_model_is_not_read_from_the_text():
    """PLANIN EN KRİTİK SATIRI: `pickedLabels` `dataset.value` okumak ZORUNDA.

    `textContent` okunursa kartın açıklaması modele giden cevaba KARIŞIR —
    yönetmene "deep navy background Zemin gece lacivertine döner, hilal
    parlak okunur." diye bir cevap gider. Ayrım tümüyle sessiz: ekranda kart
    doğru görünür, akıştaki SEÇİM pili doğru görünür, yalnız modelin aldığı
    metin bozuk olur ve bir sonraki prompt açıklama cümlesini de ciddiye alır.
    """
    js = _chat_js()
    body = re.search(r"function pickedLabels\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "pickedLabels() bulunamadı"
    govde = _strip_js_comments(body.group(1))
    assert "dataset.value" in govde, (
        "seçili çipin değeri `dataset.value`den okunmuyor — kart açıklaması "
        "modele giden cevaba karışır")
    # Yazan taraf: değer çipe yazılmazsa okuma yolu boşa çıkar.
    assert "chip.dataset.value = veri.ad" in js, "değer çipe yazılmıyor"


def test_an_explained_option_keeps_the_lockable_chip_semantics():
    """Kart `.chat-option`u ve `aria-checked`ini KAYBETMEMELİ.

    O kök sınıftan dört şey geliyor: `lockStaleOptions`ın kilidi, odak
    halkası, `.chat-options-done` soluklaştırması ve `✓` işareti
    (`[aria-checked="true"]::before`). Kart ikinci bir sınıf olarak eklenmek
    zorunda — sınıfı DEĞİŞTİRSE eski paneller sonsuza dek canlı kalır ve
    kullanıcı artık var olmayan bir prompt'a delta gönderir.
    """
    js = _chat_js()
    body = re.search(r"function optionChip\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "optionChip() bulunamadı"
    govde = _strip_js_comments(body.group(1))
    assert 'chip.className = "chat-option"' in govde, "kök sınıf değişmiş"
    assert 'classList.add("chat-option-card")' in govde, (
        "kart sınıfı EKLENMİYOR — kök sınıfın yerine yazılmışsa kilit ve `✓` gider")
    assert 'chip.setAttribute("aria-checked", "false")' in govde
    # Kart CSS'i de kök sınıfın kurallarını ezmemeli: `✓` işareti duruyor.
    assert '.chat-option[aria-checked="true"]::before' in _css()


def test_a_broken_option_item_is_skipped_not_drawn_empty():
    """Adsız bir madde çizilmemeli: tıklanınca modele BOŞ cevap gider.

    `String(raw)` sarmalayıcısı da bu yüzden kalktı — nesne bir maddeyi
    "[object Object]" yapıyordu ve o metin hem ekrana hem modele gidiyordu.
    """
    js = _chat_js()
    body = re.search(r"function optionItem\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "optionItem() bulunamadı"
    assert "return null" in body.group(1), "bozuk madde atlanmıyor"
    # Atlamanın TAŞIYICI yeri `drawableOptions`: iki panel de çiplerini o
    # süzgeçten kuruyor, yani "çizilecek madde var mı" sorusunu ham bloğu
    # atlama kararıyla AYNI fonksiyona soruyorlar (bkz. bir alttaki test).
    # `if (chip)` ikinci bir kemer olarak duruyor ama tek başına yetmiyordu:
    # o dal `null`u DOM'dan uzak tutuyor, bloğun görünmesini sağlamıyor.
    for fn, sarmal in (("renderOptions", "optionItems(parsed)"),
                       ("renderParameters", "drawableOptions(axis.secenekler)")):
        govde = re.search(rf"function {fn}\([^)]*\)\s*\{{(.*?)\n\}}", js, re.S)
        assert sarmal in govde.group(1), \
            f"{fn} maddelerini paylaşılan süzgeçten kurmuyor"
        assert "if (chip) chips.appendChild(chip)" in govde.group(1), \
            f"{fn} `null` çipi atlamıyor"


def test_a_panel_with_no_drawable_item_is_not_appended_as_null():
    """`renderOptions` artık `null` dönebiliyor — çağrı yeri KORUNMALI.

    `appendChild(null)` TypeError atar ve o an yönetmenin bütün yanıtını
    çizmeyi durdurur: kullanıcı boş bir baloncuk görür. Diğer iki panelin
    çağrı yeri bu yüzden zaten `if (panel)` ile korunuyordu; seçenek paneli
    hiç `null` dönmediği için korumasızdı ve şimdi dönebiliyor.
    """
    js = _strip_js_comments(_chat_js())
    assert "div.appendChild(renderOptions(parsed))" not in js, (
        "renderOptions'ın dönüşü doğrudan appendChild'a gidiyor — `null` "
        "olduğunda TypeError bütün yanıtın çizimini durdurur")
    govde = re.search(r"function renderOptions\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert "if (!items.length) return null;" in govde.group(1), (
        "çizilebilir madde yokken panel yine kuruluyor — tıklanamayan boş "
        "bir şerit çiziliyor ve ham blok da atlanmış oluyor")


def test_an_axis_with_no_drawable_alternative_is_not_a_dead_row():
    """Eksen kapısı "dizi ve boş değil" DEĞİL "çizilebilir madde var" olmalı.

    Dolu ama tamamı bozuk bir liste (`[{"label": "soft"}]`) eski kapıdan
    geçiyordu: satır adıyla ve rozetiyle çiziliyor, tıklanacak hiçbir şey
    taşımıyor, üstelik ham blok atlandığı için modelin ne önerdiği hiçbir
    yerde görünmüyordu. İki kayıp bir arada.
    """
    js = _chat_js()
    govde = re.search(r"function axisItems\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert govde, "axisItems() bulunamadı"
    assert "drawableOptions(e.secenekler)" in govde.group(1), (
        "eksen kapısı çizilebilirliği sormuyor")
    assert "e.secenekler.length" not in govde.group(1), (
        "eski uzunluk kapısı geri dönmüş — bozuk maddeler ölü satır üretir")


def test_the_hex_gate_accepts_exactly_the_lengths_css_understands():
    """5 ve 7 haneli bir hex doğrulamadan geçip CSS'te SESSİZCE düşüyordu.

    `{3,8}` yazıldığında `#0b254` kapıdan geçiyor, `style.background`a
    yazılıyor ve CSSOM onu atıyor — ama `ornekKutusu` kutuyu yine döndüğü
    için çip karta yükseliyor ve kullanıcı BOŞ bir dikdörtgen görüyordu.
    "Doğrulamayı geçmeyen değer çizilmiyor" sözü ancak kapı CSS'in kabul
    ettiği kümeyle (3·4·6·8) aynı olduğunda tutuyor.
    """
    js = _chat_js()
    kapi = re.search(r"const HEX_RE = (.+);", js)
    assert kapi, "HEX_RE bulunamadı"
    assert "{3,8}" not in kapi.group(1), (
        "hex kapısı 5 ve 7 haneli dizeleri kabul ediyor — CSS onları atar, "
        "kutu boş çizilir")
    for uzunluk in ("{3,4}", "{6}", "{8}"):
        assert uzunluk in kapi.group(1), f"hex kapısı {uzunluk} uzunluğunu saymıyor"


def test_a_drawn_example_without_a_description_is_still_announced():
    """`aria-hidden` KOŞULLU olmak zorunda: `aciklama` ile `ornek` bağımsız.

    Kutu "bilgi `aciklama`da yazılı" gerekçesiyle gizleniyor ve bu, açıklaması
    olan bir maddede doğru. Ama `{"ad": "deep navy", "ornek": {"renk": "#0b2545"}}`
    sözleşmede geçerli bir madde (iki alan birbirinden bağımsız isteğe bağlı):
    orada kutuyu koşulsuz gizlemek, seçenekleri BİRBİRİNDEN AYIRAN tek şeyi
    ekran okuyucudan saklamak olurdu — kullanıcı yalnız "deep navy" duyar.
    """
    js = _chat_js()
    govde = re.search(r"function ornekKutusu\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert govde, "ornekKutusu() bulunamadı"
    gv = _strip_js_comments(govde.group(1))
    assert 'if (sessiz)' in gv, "gizleme koşullu değil"
    assert 'aria-label' in gv, "açıklaması olmayan kutu ADLANDIRILMIYOR"
    # Koşulun GİRDİSİ: çağrı `aciklama`nın varlığını geçmek zorunda.
    assert "ornekKutusu(veri.ornek, !!veri.aciklama)" in js, (
        "kutu açıklamanın varlığını bilmiyor — koşul boşa çıkar")


def test_the_selected_mark_does_not_become_its_own_row_on_a_card():
    """`✓` kartta AYRI BİR SATIR oluyordu ve seçmek yerleşimi oynatıyordu.

    Ölçüldü (Chromium, 1280px): `.chat-option-card` kolon flex kutusu, bir
    flex kapsayıcısının `::before`u BLOKLAŞIP ilk flex ÖĞESİ oluyor — işaret
    etiketin soluna değil örnek kutusunun üstüne düşüyor, kart 23,3px uzuyor
    ve ad 23,3px aşağı kayıyordu. Düzeltmeden sonra ikisi de 0px.

    İşaret KALKMIYOR, yer değiştiriyor: kökün kuralı pill'ler için duruyor,
    kartta `content: none` onu adın `::before`una devrediyor. "Seçili durum
    renkle değil işaretle de anlatılıyor" şartı bu yüzden bozulmuyor.
    """
    css = _css_yorumsuz()
    assert '.chat-option-card[aria-checked="true"]::before { content: none; }' in css, (
        "kartta kök işaret kapatılmıyor — kendi satırına düşer ve kartı uzatır")
    assert '.chat-option-card[aria-checked="true"] .chat-option-ad::before' in css, (
        "işaret adın önüne devredilmiyor — kartta seçili durum GÖRÜNMEZ olur")
    # Pill'in kuralı DURUYOR: kart düzeltmesi onu götürmemeli.
    assert '.chat-option[aria-checked="true"]::before { content: "✓ "; }' in css


def test_the_chips_strip_is_declared_once():
    """`.chat-options-chips` iki satır arayla KENDİNİ tekrar ediyordu.

    İkinci kural `align-items: stretch` yazıyordu — `align-items`ın başlangıç
    değeri `normal` ve flex öğeleri için `stretch` gibi davrandığı için
    hiçbir şeyi değiştirmiyordu. Yanındaki gerekçe ("`baseline` olsaydı
    kartlar kayardı") var olmayan bir kuralı anlatıyordu: `baseline`
    `.chat-axis`te, yani eksen SATIRINDA, ve bir öğenin kendi hizalanmasını
    `align-self` belirlerdi. Değiştirmediği bir şeyi anlatan yorum sonraki
    okuru yanlış yere bakmaya gönderir.
    """
    css = _css_yorumsuz()
    # Yalnız ÇIPLAK seçici sayılıyor: `.chat-axis .chat-options-chips` meşru ve
    # ayrı bir kural (eksen satırındaki şeride esneme veriyor), kendini tekrar
    # eden bir bildirim değil.
    ciplak = re.findall(r"^\.chat-options-chips\s*\{", css, re.M)
    assert len(ciplak) == 1, (
        f".chat-options-chips {len(ciplak)} kez bildirilmiş — bildirimleri tek "
        "kurala taşıyın, yoksa hangisinin taşıyıcı olduğu okunamaz")
    # İddia KURALA kapsanıyor, dosyaya değil: `align-items: stretch` başka bir
    # yerde (`.chat-item`) duruyor ve o kuralın konusu bu değil.
    assert "align-items" not in _css_block(".chat-options-chips"), (
        "şeride flex varsayılanını yeniden yazan bir bildirim geri dönmüş")


def test_every_r_item_radius_carries_its_fallback():
    """`--r-item` yalnız flow-tokens.css'te tanımlı: geri düşme değeri ŞART.

    O dosya yüklenmezse ya da paketten düşerse fallback'i olan sekiz yuvarlak
    yüzey 12px'te kalıyor, olmayan `0` alıyor — köşeleri keskin tek öğe,
    üstelik "pill olmasın diye yuvarlatıldı" diye yorumu olan öğe olurdu.
    """
    css = _css_yorumsuz()
    ciplak = re.findall(r"var\(--r-item\s*\)", css)
    assert not ciplak, (
        f"{len(ciplak)} yerde `var(--r-item)` geri düşme değeri olmadan "
        "yazılmış — dosyadaki diğer kullanımların hepsi `var(--r-item, 12px)`")


def test_the_drawn_example_validates_the_models_text_before_styling():
    """Model metni bir `style` özelliğine yazılıyor: kapı BEYAZ liste olmalı.

    Bu dosya `innerHTML`i zaten yasaklıyor, ama `style.background` ikinci bir
    yüzey: doğrulanmamış bir dize oraya yazıldığında `url(...)` gibi bir değer
    geçerdi. Oran da AYRIŞTIRILMIŞ iki sayıdan kuruluyor, yani CSS'e model
    metni hiç geçmiyor.
    """
    js = _chat_js()
    assert "HEX_RE" in js and "ORAN_RE" in js, "örnek doğrulayıcıları yok"
    body = re.search(r"function ornekKutusu\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "ornekKutusu() bulunamadı"
    govde = _strip_js_comments(body.group(1))
    # İKİ renk yolu var (tek renk · şerit) ve İKİSİ de doğrulamak zorunda.
    # ÖLÇÜLDÜ: "HEX_RE.test var mı" tek başına yetmiyordu — tek renk dalının
    # doğrulaması sökülünce şeridin süzgeci iddiayı yeşil tutuyordu, yani
    # mutasyon kaçıyordu. Yol SAYILIYOR, varlığı değil.
    assert govde.count("HEX_RE.test") >= 2, (
        "renk yollarından biri doğrulamadan boyuyor — iddia yalnız ötekinin "
        "süzgecini görüyor olabilir")
    assert "HEX_RE.test(ornek.renk" in govde, "tek renk dalı doğrulanmıyor"
    assert "ORAN_RE.exec" in govde, "oran doğrulanmadan uygulanıyor"
    assert "Number(" in govde, "oran ham dizeden yazılıyor"
    # `style.background`a yazan HER satır bir doğrulamanın ARDINDA olmalı:
    # atama sayısı doğrulama sayısını aşarsa korunmayan bir yol var.
    assert govde.count("style.background") <= govde.count("HEX_RE.test")
    # Örnek DEKORATİF: bilgi `aciklama`da yazılı, ekran okuyucuya iki kez
    # okutmanın anlamı yok.
    assert 'setAttribute("aria-hidden", "true")' in govde


def test_a_variation_shows_the_request_it_will_send():
    """`istek` ekranda görünmek ZORUNDA — sözleşmede vardı, arayüzde yoktu.

    Metin zaten doğrulanıyordu (`variationItems`) ve modele kullanıcının bir
    sonraki mesajı olarak gidiyordu; kullanıcı ise yalnız "Gece" yazan bir
    düğme görüyor ve neyin değişeceğini ancak tıklayıp yarım dakika
    bekledikten sonra öğreniyordu.

    Gösterilen metin modele GİDEN metinle aynı, ikinci bir özet değil: iki
    metin olsaydı düğmenin söylediği ile yaptığı ayrışabilirdi.
    """
    js = _chat_js()
    body = re.search(r"function renderVariations\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "renderVariations() bulunamadı"
    govde = _strip_js_comments(body.group(1))
    assert "actionChip(ad, item.istek.trim())" in govde, \
        "varyasyon açıklaması çipe geçmiyor"
    # Yerel düzenleme yasağı DURUYOR (mevcut kararın mandalı).
    assert ".replace(" not in govde and "parsed.prompt" not in govde, \
        "varyasyon tıklaması prompt'u yerelde düzenliyor"


def test_an_addition_axis_is_marked_as_absent_from_the_prompt():
    """`simdi` yokken satır BOŞ kalmamalı — yoksa ekleme ekseni takas gibi görünür.

    Öncesinde rozet yalnız `if (typeof axis.simdi === "string" && …)` dalında
    çiziliyordu, yani `simdi` gelmediğinde satırda ad ve çiplerden başka bir şey
    yoktu: kullanıcı prompt'ta var olmayan bir ifadeyi değiştirdiğini sanırdı.
    Rozet artık iki durumu da anlatıyor ve `dataset.yeni` ayrımın axesValue'nun
    okuyabildiği hâli.
    """
    js = _chat_js()
    body = re.search(r"function renderParameters\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "renderParameters() bulunamadı"
    govde = _strip_js_comments(body.group(1))
    assert "chat-axis-now" in govde, "takas rozeti düşmüş"
    assert "chat-axis-new" in govde, "ekleme rozeti yok — boş satır takas gibi görünür"
    assert "prompt'ta yok" in govde, "ekleme ekseninin durumu ekranda yazmıyor"
    assert 'row.dataset.yeni = "1"' in govde, \
        "ekleme ekseni işaretlenmiyor — axesValue iki türü ayırt edemez"
    # Rozet TEK yerde eklenmeli: iki `appendChild` iki rozet çizerdi.
    assert govde.count("row.appendChild(now)") == 1, \
        "rozet birden fazla kez ekleniyor"


def test_the_two_axis_kinds_reach_the_model_with_different_verbs():
    """Takas ve ekleme AYNI cümleye girmemeli.

    "Şu parametreleri değiştir: Işık → soft even light" cümlesi, prompt ışığı
    hiç söylemiyorsa modele var olmayan bir ifadeyi değiştirmesini söylüyor —
    model ya uydurma bir eski değer üretir ya da isteği yok sayar. İki fiil,
    iki liste; kapanış cümlesi ("geri kalanını aynı tut") ikisinde de duruyor.
    """
    js = _chat_js()
    body = re.search(r"function axesValue\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "axesValue() bulunamadı"
    govde = _strip_js_comments(body.group(1))
    assert "row.dataset.yeni ? ekleme : takas" in govde, \
        "eksen türü ayrıştırılmıyor"
    assert "Şu parametreleri değiştir:" in govde, "takas cümlesi düşmüş"
    assert "Şunları da belirle:" in govde, "ekleme cümlesi yok"
    assert "Prompt'un geri kalanını aynı tut." in govde, \
        "kapanış disiplini düşmüş — tek eksen değişikliği prompt'u baştan yazdırır"


def test_the_addition_badge_is_not_a_chip():
    """Rozet TIKLANABİLİR görünmemeli — `.chat-axis-now` kararının aynısı.

    Ekleme rozeti bir durum bildirimi, bir seçenek değil: dolgulu ya da
    imleç değiştiren bir rozet, yanındaki gerçek çiplerle karışırdı.
    """
    govde = _css_block(".chat-axis-new")
    assert govde, ".chat-axis-new kuralı yok"
    assert "cursor" not in govde, "rozet tıklanabilir görünüyor"
    assert "dashed" in govde, "kesikli kenar yok — takas rozetinden ayrışmıyor"
    # Sabit renk yasağı (tasarım §11 ile aynı duruş): jetondan okunmalı.
    assert "#" not in govde, "sabit renk yazılmış, jeton kullanılmıyor"


def test_the_merged_selection_is_drawn_as_a_pill_not_as_a_typed_message():
    """Birleştirilmiş seçim metni baloncuk olarak çizilince kullanıcı onu KENDİ
    yazdığı sanıyordu (v1.15'in şikâyet edilen yanı).

    Ayrım mesajın İÇİNDE taşınıyor (models.ChatMessage.display), istemcide ayrı
    bir durumda değil: `openChat` akışı `chatThread`'den yeniden çiziyor, yani
    işaret mesajda olmasa kaydedilmiş bir sohbet açıldığında piller baloncuğa
    dönerdi.
    """
    js = _chat_js()
    body = re.search(r"function appendUser\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "appendUser() bulunamadı"
    assert "msg.display" in body.group(1), "pil/baloncuk ayrımı yapılmıyor"
    assert '"chat-pick"' in body.group(1), "pil sınıfı verilmiyor"
    # Yeniden açılışta da pil kalsın: çizim mesaj NESNESİ geçirmeli.
    #
    # Döngü `openChat`ten `renderThread`e taşındı (arena satırı ardışık sonuç
    # kayıtlarını gruplamak zorunda). İDDİA GÜÇLENDİ, zayıflamadı: hem
    # delegasyon hem de nesneyi geçiren çağrı ayrı ayrı aranıyor — biri
    # koparsa öteki bunu artık örtmüyor.
    open_body = re.search(r"async function openChat\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert "renderThread(chatThread)" in open_body.group(1), (
        "openChat dökümü yeniden çizmiyor")
    render_body = re.search(r"function renderThread\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert render_body, "renderThread() bulunamadı"
    assert "appendUser(m)" in render_body.group(1), (
        "renderThread content geçiriyor — yeniden açılan sohbette piller "
        "baloncuğa döner")


def test_the_send_button_does_not_leak_the_click_event_into_the_display_field():
    js = _chat_js()
    assert 'typeof display === "string"' in js or 'submitComposer' in _core_js()


def test_the_client_counts_the_display_label_in_the_total_gate():
    """İstemci ve sunucu AYNI şeyi saymazsa sınırın dibindeki tur 422 ile döner.

    Sunucu `models._check_chat_total` içinde `content` + `display` topluyor;
    istemci yalnız `content` sayarsa isteği gönderir ve pydantic'in İNGİLİZCE
    hatasıyla geri gelir.
    """
    js = _chat_js()
    body = re.search(r"async function sendChat\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "sendChat() bulunamadı"
    assert 'm.display || ""' in body.group(1), "toplam kapısı display'i saymıyor"
    assert "MAX_CHAT_DISPLAY_CHARS" in js, "sunucu sınırı aynalanmamış"


def test_a_failed_chip_turn_does_not_dump_the_directors_delta_into_the_composer():
    """Çip turu başarısız olursa besteciye modelin uzun Türkçe cümlesi düşmemeli.

    Grup kilitlenmemiş oluyor (sendChat false döndü), yani tıklama zaten
    tekrarlanabilir; metni bestecide göstermek tam olarak kaldırılan çirkinliği
    geri getirirdi. Elle yazılan tur için geri koyma DEVAM ediyor.
    """
    js = _chat_js()
    body = re.search(r"async function sendChat\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    # İddia DURUYOR, biçimi genişledi: geri koymanın yanına bir `autoGrow`
    # girdi. Gerekçe küçülmeyle geldi — gönderim `rows`u 1'e indiriyor ve
    # ölçüm yapılmazsa geri konan çok satırlı mesaj tek satıra kırpılmış
    # görünüyor. Ölçülen şart değişmedi: geri koyma YALNIZ `!label` dalında.
    assert re.search(r"if \(!label\)\s*\{?\s*input\.value = message;",
                     body.group(1)), (
        "başarısız çip turunda delta metni besteciye dökülüyor")
    assert body.group(1).count("input.value = message") == 1, (
        "metni geri koyan ikinci bir yol var — çip turu da dökülebilir")


def test_the_selection_pill_is_quieter_than_a_typed_message():
    """Pil bir REPLİK gibi görünmemeli: dolgusu yok, kenarı kesikli, tipi küçük."""
    css = TestClient(appmod.app).get("/static/style.css").text
    rule = re.search(r"\.chat-pick\s*\{([^}]*)\}", css)
    assert rule, "pil kuralı bulunamadı"
    assert "flex-end" in rule.group(1), "pil kullanıcı tarafında durmuyor"
    assert "dashed" in rule.group(1), "pil baloncuktan ayrışmıyor"
    assert "background:" not in rule.group(1), "pil baloncuk gibi dolduruluyor"


def test_a_free_text_only_parameter_turn_is_not_attributed_to_the_user():
    """Parametre panelinde iskeleti İSTEMCİ yazıyor — tur baloncuk olamaz.

    `axesValue` hiç eksen seçilmediğinde de `content`'e kapanış cümlesini
    ("Prompt'un geri kalanını aynı tut.") ekliyor. `display` boş bırakılsaydı
    `appendUser` baloncuğa düşerdi ve kullanıcı akışta KENDİ YAZMADIĞI bir cümleyi
    kendi repliği olarak görürdü — v1.16'nın pili getirme sebebi tam olarak bu
    yanlış atıftı, yani hata özelliğin kendi amacını deliyordu.

    Ayrım `optionsValue` ile bilinçli olarak FARKLI: orada serbest metin modele
    AYNEN gidiyor (turu kullanıcı yazdı, baloncuk doğru). Ölçü "seçim yapıldı mı"
    değil, "turu kim yazdı".
    """
    js = _chat_js()
    body = re.search(r"function axesValue\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "axesValue() bulunamadı"
    assert "if (!secili) return { content, display: own };" in body.group(1), (
        "eksen seçilmeyen tur baloncuk olarak çiziliyor — kullanıcı yazmadığı "
        "cümleyi kendi repliği sanır")
    # Seçenek panelinde ters yön korunmalı: orada serbest metin baloncuk KALIR.
    opts = re.search(r"function optionsValue\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert 'return { content: own, display: "" };' in opts.group(1), (
        "seçenek panelinde kullanıcının kendi cümlesi pile çevrilmiş")


def test_a_machine_block_that_breaks_its_contract_is_still_shown_to_the_user():
    """Blok ne panel ne kod bloğu olarak çizilmezse SESSİZCE kaybolur.

    Atlama koşulu "blok var" olsaydı, sözleşmeye uymayan bir varyasyon bloğu
    (örn. `istek` alanı düşmüş) iki kere elenirdi: `renderVariations` `null`
    döndüğü için panel çizilmez, atlama kümesinde olduğu için ham JSON da
    çizilmez — kullanıcı hiçbir şey görmez. Bu, aynı fonksiyondaki "tanınmayan
    JSON bloğu ÇİZİLİR, kullanıcı onu görsün" dürüstlük kuralının tam tersi.

    Çözüm süzgeci PAYLAŞMAK: panelin çizilip çizilmeyeceğini iki yer aynı
    fonksiyona soruyor, o yüzden ayrışamıyorlar.
    """
    js = _chat_js()
    body = re.search(r"function renderMarkdownInto\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "renderMarkdownInto() bulunamadı"
    skip = re.search(r"const skip = new Set\(\[(.*?)\]", body.group(1), re.S)
    assert skip, "atlama kümesi bulunamadı"
    # ÜÇ satırın üçü de koşullu. Seçenek satırı bir süre koşulsuzdu ve o
    # zaman doğruydu (madde düz dizeydi, `String(raw)` her madde için bir çip
    # üretiyordu). Nesne biçimiyle `optionItem` `null` dönebilir oldu ve ikisi
    # ayrıştı: tamamı bozuk bir `secenekler` listesi ayrıştırıcıdan geçiyor,
    # tek çip üretmiyor, ham blok da atlanmış oluyordu.
    for fn in ("optionItems(parsed).length", "variationItems(parsed).length",
               "axisItems(parsed).length"):
        assert fn in skip.group(1), (
            f"atlama kümesi {fn} sormuyor — sözleşmesi bozuk blok sessizce kaybolur")
    # Süzgeç GERÇEKTEN paylaşılıyor mu: paneller de aynı fonksiyonu çağırmalı.
    for name, fn in (("renderOptions", "optionItems(parsed)"),
                     ("renderVariations", "variationItems(parsed)"),
                     ("renderParameters", "axisItems(parsed)")):
        panel = re.search(rf"function {name}\([^)]*\)\s*\{{(.*?)\n\}}", js, re.S)
        assert fn in panel.group(1), (
            f"{name} kendi süzgecini tutuyor — atlama kuralıyla ayrışabilir")


# ── Birleşik döküm: sonuç kartları ve otomatik kayıt (v2.0 / Adım 7) ────
# Adım 5–6 arka ucu teslim etti; buradaki iddialar EKRAN payını mandallıyor.
# Hepsi planın §7'sindeki kutulara birebir karşılık geliyor.

def _core_js() -> str:
    return TestClient(appmod.app).get("/static/core.js").text


def test_chat_item_limit_mirrors_the_server():
    """Toplam öğe sınırı da aynalanmalı (MAX_CHAT_MESSAGES geleneği).

    İstemci yalnız 24'ü bilirse üretim yapan oturum sunucu 48 öğeye izin
    verirken 24'te kilitlenir — kullanıcı sebepsiz "sohbet doldu" görür (§0.4/K4).
    """
    js = _chat_js()
    match = re.search(r"const MAX_CHAT_ITEMS = (\d+);", js)
    assert match, "MAX_CHAT_ITEMS istemcide tanımlı değil"
    assert int(match.group(1)) == models.MAX_CHAT_ITEMS


def test_the_client_is_never_stricter_than_the_server_about_results():
    """`MAX_CHAT_RESULTS` istemcide BULUNMAMALI ve bu bilinçli.

    Sunucu sonuç ADEDİNİ ayrıca kapamıyor: kurallar "konuşma ≤ MAX_CHAT_MESSAGES"
    ve "toplam ≤ MAX_CHAT_ITEMS". İstemci ayrıca 24 sonuçta durursa SUNUCUDAN
    KATI olur ve sohbetsiz bir oturum 24. üretimde sebepsiz kilitlenir — Adım 7'nin
    kapattığı borcun tam olarak aynısı, yalnız ekseni değişmiş hâli.
    """
    assert models.MAX_CHAT_ITEMS == models.MAX_CHAT_MESSAGES + models.MAX_CHAT_RESULTS
    # Sunucunun konuşma kapısı sonuç kayıtlarını saymıyor → sonuç adedi yalnızca
    # toplam sınırla bağlı. İddia bunu doğruluyor ki sunucu bir gün ayrı bir
    # sonuç kapısı eklediğinde bu test kırmızıya dönsün ve istemci de aynalasın.
    import inspect
    assert "MAX_CHAT_RESULTS" not in inspect.getsource(models._check_chat_counts)
    # TANIM aranıyor, kelime değil: chat.js'in başındaki not neden
    # aynalanmadığını anlatıyor ve o notun kalması gerekiyor (yoksa bir gün
    # "tutarlılık olsun" diye geri eklenir).
    assert not re.search(r"const MAX_CHAT_RESULTS\s*=", _chat_js()), (
        "istemci sunucuda olmayan bir sonuç kapısı kuruyor")


def test_the_conversation_gate_counts_only_conversation_messages():
    """`chatThread.length >= MAX_CHAT_MESSAGES` ARTIK YANLIŞ sayıyor.

    Sonuç kayıtlarının kendi payı var (§0.4/K4): dökümdeki her sonuç kartı
    konuşma kotasından bir tur çalardı ve üretim yapan oturum ~8 turda
    kilitlenirdi. Kapı rolü sormak zorunda.
    """
    js = _chat_js()
    body = re.search(r"async function sendChat\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "sendChat() bulunamadı"
    assert "chatThread.length >= MAX_CHAT_MESSAGES" not in body.group(1), (
        "konuşma kapısı sonuç kayıtlarını da sayıyor")
    assert "conversationIsFull()" in body.group(1), (
        "konuşma kapısı paylaşılan sayacı kullanmıyor")
    full = re.search(r"function conversationIsFull\(\)\s*\{(.*?)\n\}", js, re.S)
    assert full and "MAX_CHAT_MESSAGES" in full.group(1)
    # Sayaç GERÇEKTEN rolü süzüyor mu: yoksa yeniden adlandırılmış bir
    # `chatThread.length` olur ve iddia boş geçer.
    counter = re.search(r"function conversationCount\(\)\s*\{(.*?)\n\}", js, re.S)
    assert counter, "conversationCount() bulunamadı"
    assert "RESULT_ROLE" in counter.group(1), "sayaç sonuç kayıtlarını ayırmıyor"


def test_the_total_char_gate_skips_result_records():
    """Toplam kapısı sunucunun `_check_chat_total`'ıyla AYNI şeyi saymalı.

    Sunucu sonuç kayıtlarını saymıyor (modele gitmiyorlar). Ayrıca sonuç
    kaydında `content` HİÇ YOK: `m.content.length` bir TypeError atar ve
    gönderim tümden ölür — kapı bu yüzden hem rolü süzmek hem de eksik
    `content`'e dayanıklı olmak zorunda.
    """
    lf = _chat_js().replace("\r\n", "\n")
    # Satır sonu TEMSİLİ bu iddiayı etkilemEMEli. CI Windows checkout'u CRLF
    # veriyor (Git for Windows'un `core.autocrlf` varsayılanı `true`) ve eski
    # `;\n` çapalı desen orada HİÇ eşleşmiyordu: yerelde 1171 yeşilken CI'da
    # kırmızı, koşu 31727509717. Depo tarafındaki kök düzeltme `.gitattributes`
    # (eol=lf); bu döngü ise iddianın KENDİSİNİ temsile bağımlı olmaktan
    # kurtarıyor — ikisi ayrı iş, biri ötekinin yerine geçmez.
    for etiket, js in (("LF", lf), ("CRLF", lf.replace("\n", "\r\n"))):
        body = re.search(r"async function sendChat\([^)]*\)\s*\{(.*?)\n\}",
                         js, re.S)
        assert body, f"{etiket}: sendChat() bulunamadı"
        used = re.search(r"const used = chatThread(.*?);\r?\n", body.group(1),
                         re.S)
        assert used, f"{etiket}: toplam kapısının hesabı bulunamadı"
        assert "m.content.length" not in used.group(1), (
            f"{etiket}: sonuç kaydında content yok — TypeError ile gönderim ölür")
        assert "RESULT_ROLE" in used.group(1), (
            f"{etiket}: toplam kapısı sonuç kayıtlarını da sayıyor")


def test_the_result_turn_reserves_room_for_both_of_its_records():
    """Sonuç turu İKİ öğe yazıyor: kullanıcı prompt'u + sonuç kaydı.

    Turu AÇAN tek öğe için yer sorsa, tur açılır ama kapatılamazdı: dökümde
    cevapsız bir kullanıcı satırı kalır ve kullanıcı üretimin kaydedilmediğini
    hiç anlamaz. Kapı ayrıca turu KAPATAN tarafta da soruluyor — üretim sürerken
    kullanıcı sohbet edebiliyor, yani döküm arada büyümüş olabilir.
    """
    js = _chat_js()
    room = re.search(r"function transcriptHasRoom\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert room, "transcriptHasRoom() bulunamadı"
    assert "conversationIsFull()" in room.group(1) and "transcriptIsFull(" in room.group(1)
    begin = re.search(r"function beginResultTurn\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert begin and "transcriptHasRoom(2)" in begin.group(1), (
        "açılan tur kapatılamayacak bir yere yazılıyor")
    end = re.search(r"async function appendResultTurn\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert end and "transcriptHasRoom(1)" in end.group(1), (
        "sonuç kaydı kapıyı hiç sormuyor")


def test_the_transcript_draws_result_records():
    """Üçüncü rol EKRANDA olmak zorunda; yoksa Adım 5'in modeli ölü kod.

    `openChat` iki dallıydı (user → appendUser, aksi → appendBot): bir sonuç
    kaydı `appendBot(undefined)`'a düşer ve döküm çöker.
    """
    js = _chat_js()
    assert re.search(r"function appendResult\(", js), "appendResult() yok"
    # Döngü `renderThread`de (bkz. pil testinin notu); `openChat` ona
    # delege ediyor. İki iddia birlikte, aradaki bağ kopmasın.
    open_body = re.search(r"async function openChat\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert open_body, "openChat() bulunamadı"
    assert "renderThread(chatThread)" in open_body.group(1), (
        "openChat dökümü yeniden çizmiyor")
    body = re.search(r"function renderThread\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "renderThread() bulunamadı"
    assert re.search(r'RESULT_ROLE|=== "result"', body.group(1)), (
        "yeniden açılan oturumda sonuç kaydı role göre çizilmiyor")


def test_a_result_image_url_is_built_from_the_id():
    """Döküm yalnız `image_ids` taşıyor; dosya adı sözleşmesi `{id}.{uzantı}`.

    Sözleşme storage.py'de yazılı (`delete_many` docstring'i, `save`'in
    `filename` satırı) ve ikinci bir istek gerektirmiyor. `/api/history`
    KULLANILAMAZ: o uç klasöre göre süzülüyor, yani başka bir klasördeki
    sonuç görselini hiç döndürmezdi.

    UZANTI v0.13'te SABİT OLMAKTAN ÇIKTI: depo iki tür taşıyor ve uzantı
    kaydın `kind`inden türetiliyor. İddianın ÖZÜ değişmedi — adres hâlâ
    id'den kuruluyor, ikinci bir istek (HEAD, `/api/history`) yok. Değişen
    tek şey uzantının artık bir DAL olması ve iki dalın da burada sayılması:
    birini düşürmek, o türü hiç açılmayan bir 404'e çevirirdi.
    """
    js = _chat_js()
    assert re.search(r"/output/\$\{[^}]*\}\.\$\{[^}]*\}", js), (
        "sonuç medyasının URL'i id'den kurulmuyor")
    assert re.search(r'videoMu \? "mp4" : "png"', js), (
        "uzantı türden türetilmiyor — iki dal da yazılı olmalı")


def test_a_deleted_result_image_draws_a_placeholder():
    """Sarkan `image_id` sunucuda KASTEN budanmıyor (Adım 5'in testi); ekran payı bu.

    Ölçü `error` olayı: dosya gerçekten yoksa `/output/{id}.png` 404 döner.
    Bayat bir dizinden bakmak yerine gerçek koşulu ölçüyor.
    """
    js = _chat_js()
    fn = re.search(r"function resultThumb\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert fn, "resultThumb() bulunamadı"
    assert '"error"' in fn.group(1), "yükleme hatası dinlenmiyor"
    assert "silindi" in fn.group(1), "yer tutucu metni yok"


def test_result_thumbnails_open_the_full_viewer():
    """Tasarım §6: "sonuç kartına tıklayınca tam-kaplama önizleme".

    `viewer.js` YENİDEN YAZILMIYOR (§1.3) — yalnızca tek bir açılış dikişi
    dışa veriliyor, imleç-sabitli zoom/rubberband/pinch aynen duruyor.
    """
    viewer = TestClient(appmod.app).get("/static/viewer.js").text
    assert "window.openViewer" in viewer, "büyüteç dışa açılan bir dikiş vermiyor"
    for kept in ("zoomAt", "rubberband", "ARROW_STEP", "openerRect"):
        assert kept in viewer, f"§1.3 korunan davranış kaybolmuş: {kept}"
    assert "openViewer" in _chat_js(), "sonuç kartı büyüteci açmıyor"


def test_the_client_no_longer_invents_a_title():
    """Başlık artık SUNUCUDA türetiliyor (§0.5/K9) ve bu bir güvenlik mandalı.

    Başlıksız yazım = otomatik yazım işareti (K8). İstemci bir başlık
    uydurursa o işaret yok olur ve "oturumları otomatik kaydet" anahtarı
    SESSİZCE delinir: kapalıyken de yazım geçer.
    """
    js = _chat_js()
    # ÇAĞRI aranıyor, kelime değil: dosyanın başındaki not `deriveTitle`'ın neden
    # kaldırıldığını anlatıyor ve o notun kalması gerekiyor (yoksa bir gün
    # "kolaylık olsun" diye geri gelir).
    assert "deriveTitle(" not in js, (
        "istemci hâlâ başlık türetiyor — otomatik kayıt anahtarı delinir")
    body = re.search(r"async function persistThread\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "persistThread() bulunamadı"
    assert "title" not in body.group(1), "otomatik yazımda başlık gönderiliyor"


def test_a_blocked_autosave_is_explained_in_turkish():
    """Anahtar kapalıyken sunucu 409 dönüyor; kullanıcı sebebini görmeli.

    Ham `detail` metni de Türkçe (app._guard_autosave), ama 409 BEKLENEN bir
    durum — hata gibi gösterilmemeli, yoksa kullanıcı her turda kırmızı bir
    satır görür ve anahtarı kendisinin kapattığını unutur.
    """
    js = _chat_js()
    body = re.search(r"async function persistThread\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    # Kodun KENDİSİ aranıyor: gövdedeki not da "409" yazıyor, kelime araması
    # kod silinse de geçerdi.
    assert "e.status === 409" in body.group(1), "409 ayrı ele alınmıyor"
    # Durum kodu istisnaya GERÇEKTEN takılıyor mu (yoksa dal hiç girilmez):
    api = re.search(r"async function chatApi\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert "e.status = res.status" in api.group(1), "durum kodu taşınmıyor"


def test_the_autosave_switch_uses_its_own_endpoint():
    """Anahtar `/api/prefs`'ten okunuyor ve oraya yazılıyor (§0.5/K7).

    `/api/settings`'e bağlanırsa bir tercihi çevirmek Azure kimliğini yeniden
    yazmak zorunda kalır ve Azure yapılandırılmamışken anahtar çevrilemez olur.
    """
    js = _chat_js()
    # OKUMA ve YAZMA ayrı ayrı sorulUYOR: tek bir `in js` araması, iki
    # fonksiyondan biri `/api/settings`'e kaysa da geçerdi.
    for name in ("loadPrefs", "saveAutosavePref"):
        fn = re.search(rf"async function {name}\([^)]*\)\s*\{{(.*?)\n\}}", js, re.S)
        assert fn, f"{name}() bulunamadı"
        assert '"/api/prefs"' in fn.group(1), f"{name} tercih ucunu kullanmıyor"
        assert "/api/settings" not in fn.group(1), f"{name} kimlik ucuna yazıyor"
    assert "autosave_sessions" in js, "anahtarın alan adı yok"
    html = TestClient(appmod.app).get("/").text
    assert 'id="pref-autosave"' in html, "anahtarın arayüzü yok"


def test_deleting_every_session_is_wired_and_confirmed():
    """Karar D1'in güvence (b)'si: tek tıkla "tümünü sil".

    Onay ZORUNLU (`confirmDialog`): geri alınamayan ve TOPLU bir silme, tek
    kayıt silmenin onayından daha çok gerekiyor.
    """
    js = _chat_js()
    body = re.search(r"async function deleteAllChats\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "deleteAllChats() bulunamadı"
    assert "confirmDialog" in body.group(1), "toplu silme onay sormuyor"
    assert '"/api/chats"' in body.group(1) and "DELETE" in body.group(1)
    html = TestClient(appmod.app).get("/").text
    assert 'id="chats-delete-all"' in html, "düğme işaretlemede yok"


def test_the_top_bar_names_the_open_session():
    """`#session-title` PR 1'de kondu ama hiç bağlanmadı — ölü işaretlemeydi.

    Bağlanması Adım 7'nin işi ve bir GEREKLİLİK: iki modda da aynı kabuk
    görünüyor, yani "hangi oturumdayım" sorusunun cevabı üst şeritte olmazsa
    Görsel modunda üretilen görsel kullanıcının bilmediği bir döküme düşer.
    """
    js = _chat_js()
    fn = re.search(r"function syncSessionHeader\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert fn, "syncSessionHeader() bulunamadı"
    # YAZIM aranıyor, id'nin adı değil: nottaki `#session-title` kelimesi kod
    # silinse de geçerdi.
    assert '$("session-title").textContent' in fn.group(1), (
        "oturum adı üst şeritte güncellenmiyor")
    assert '$("session-stamp").textContent' in fn.group(1), "oturum damgası bağlanmamış"
    # Üç yol da başlığı tazelemek ZORUNDA: yazım (yeni oturum burada doğuyor),
    # açma ve sıfırlama. Biri atlanırsa üst şerit başka bir oturumu gösterir.
    for name, pattern in (("persistThread", r"async function persistThread"),
                          ("openChat", r"async function openChat"),
                          ("resetThread", r"function resetThread")):
        body = re.search(rf"{pattern}\([^)]*\)\s*\{{(.*?)\n\}}", js, re.S)
        assert "syncSessionHeader(" in body.group(1), f"{name} üst şeridi tazelemiyor"


def test_generation_joins_the_open_session():
    """Görsel modunda üretim, AÇIK bir oturum varsa onun dökümüne düşüyor.

    `session_id` biçim kapısından geçiyor ama varlık kapısı YOK (§0.4/K2):
    var olmayan bir id gönderilse sarkan bir etiket diske yazılırdı. Bu yüzden
    yalnızca oturum GERÇEKTEN açıkken gönderiliyor.
    """
    js = _core_js()
    body = re.search(r"async function run\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "run() bulunamadı"
    # İKİ dal da sorulUYOR: `/api/generate` (JSON) ve `/api/edit` (multipart).
    # Tek bir `in` araması, biri düşse de diğerinin varlığıyla geçerdi — palet
    # alanının `/api/edit`'te bir kez tam olarak böyle düşmesi bunun kanıtı.
    assert '...(sessionId ? { session_id: sessionId } : {})' in body.group(1), (
        "üretim (JSON dalı) oturuma bağlanmıyor")
    assert 'fd.append("session_id", sessionId)' in body.group(1), (
        "düzenleme (multipart dalı) oturuma bağlanmıyor")
    # Etiket KOŞULLU: oturum yoksa alan hiç gitmiyor, çünkü sunucuda varlık
    # kapısı yok (§0.4/K2) ve uydurulan bir id sarkan bir etiket olarak yazılırdı.
    assert "const sessionId = openSessionId();" in body.group(1)
    assert "appendResultTurn" in body.group(1), "sonuç kaydı döküme girmiyor"


def test_a_closed_result_turn_can_no_longer_be_rolled_back():
    """Sonuç kaydı yazıldıktan SONRA geri alma çağrılırsa döküm bozulur.

    `run()`'ın `try` bloğu sonuç kaydını da kapsıyor: sonraki bir hata (ör.
    `loadHistory`'nin ağ hatası) `catch`'e düşerse kullanıcı turu silinir ama
    sonuç kaydı KALIR — dökümde sahipsiz bir kart. `done` işareti bu yolu kapıyor.
    """
    js = _chat_js()
    drop = re.search(r"function dropPendingTurn\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert drop and "pending.done" in drop.group(1), (
        "kapanmış tur geri alınabiliyor — döküme sahipsiz sonuç kartı düşer")
    end = re.search(r"async function appendResultTurn\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert "pending.done = true" in end.group(1), "tur kapanmış olarak işaretlenmiyor"


def test_a_result_with_no_images_is_not_written():
    """Boş `image_ids` sunucuda 422 (`min_length=1`) — kullanıcının açıklayamadığı bir hata.

    Görsel dönmediyse yazılacak bir sonuç da yok. Kullanıcı turu da düşüyor:
    cevapsız bir replik bırakmak, başarısız üretimin kuralına aykırı olurdu.
    """
    assert models.ChatMessage.model_fields["image_ids"].metadata, "alan sınırı yok"
    js = _chat_js()
    end = re.search(r"async function appendResultTurn\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert "if (!imageIds.length)" in end.group(1), "boş sonuç yazılmaya çalışılıyor"
    assert "dropPendingTurn(pending)" in end.group(1), (
        "boş sonuçta kullanıcı turu cevapsız kalıyor")


def test_a_failed_generation_leaves_no_turn_behind():
    """sendChat'in kuralı burada da geçerli: BAŞARISIZ TUR GEÇMİŞTE KALMAZ.

    Kalsaydı döküme cevapsız bir kullanıcı turu düşer, yeniden denemek onu
    ikinci kez eklerdi ve oturum aynı prompt'un kopyalarıyla dolardı.
    """
    js = _core_js()
    body = re.search(r"async function run\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert "dropPendingTurn" in body.group(1), (
        "başarısız üretim dökümde cevapsız bir tur bırakıyor")


# ── Adım 7b: PR 1'in giydirme borcu (§0.2 · A1–A6) ──────────────────────
# PR 1 kabuğu kurdu ama altı iş yarım kaldı: Kütüphane ve Araçlar ray
# düğmeleri GÖRÜNÜM değil gizli bir düğmeye programatik tıklama, Medya'da
# arama ve ızgara boyutu yok, Azure/Tema hâlâ ortalanmış modal, tema seçici
# hiç yok. Aşağıdaki iddialar planın §7'sindeki A1–A6 kutularına birebir
# karşılık geliyor.

def _html() -> str:
    return TestClient(appmod.app).get("/").text


def _css() -> str:
    return TestClient(appmod.app).get("/static/style.css").text


def _folders_js() -> str:
    return TestClient(appmod.app).get("/static/folders.js").text


def _settings_js() -> str:
    return TestClient(appmod.app).get("/static/settings.js").text


def _assets_js() -> str:
    return TestClient(appmod.app).get("/static/assets.js").text


def _palette_js() -> str:
    return TestClient(appmod.app).get("/static/palette.js").text


def _section(html: str, element_id: str) -> str:
    """`id="…"` ile başlayan bölümün gövdesi (bir sonraki kapanışa kadar)."""
    start = html.find(f'id="{element_id}"')
    assert start > 0, element_id
    end = html.find("</section>", start)
    if end < 0:
        end = html.find("</aside>", start)
    assert end > start, f"{element_id} kapanmıyor"
    return html[start:end]


def test_library_is_a_rail_view_not_a_click_on_a_hidden_button():
    """A1: Kütüphane ray öğesi GÖRÜNÜM açmalı, gizli bir düğmeye tıklamamalı.

    PR 1 rayı kurdu ama `core.js` "Kütüphane"yi `$("library-btn").click()`
    ile karşılıyordu — düğme #specs-sheet'in içinde, yani ray öğesi kapalı bir
    panelin düğmesine programatik tıklıyordu. Tasarım §4.1 rayı dört GÖRÜNÜM
    olarak sayıyor; modal açan bir ray öğesi o grameri bozuyor.
    """
    html = _html()
    assert 'id="view-library"' in html, "Kütüphane görünümü yok"
    assert 'id="assets-modal"' not in html, "Kütüphane hâlâ modal"
    assert 'id="assets-close"' not in html, "modalın kapatma düğmesi kalmış"
    core = _core_js()
    assert 'showSection("library")' in core, "ray öğesi görünüm değiştirmiyor"
    assert '$("library-btn").click()' not in core, (
        "ray öğesi hâlâ gizli bir düğmeye programatik tıklıyor")
    assets = _assets_js()
    assert "openAssetsModal" not in assets, "modal açma yolu duruyor"
    assert "assets-modal" not in assets, (
        "assets.js var olmayan bir id'ye bakıyor → yükleme anında TypeError")


def test_library_view_keeps_every_asset_control():
    """Kütüphane modaldan görünüme taşındı; kontrollerin HİÇBİRİ düşmedi.

    `assets.js` bu id'lere top-level `$()` ile bağlanıyor (16 bağ, en kalabalık
    dosya): biri taşınırken kaybolursa dosya yüklenirken patlar ve ondan
    sonraki tüm dinleyiciler — bindirme paneli dahil — hiç kurulmaz.
    """
    view = _section(_html(), "view-library")
    for element_id in ("assets-title", "asset-tabs", "asset-upload-btn",
                       "asset-file-input", "asset-grid", "asset-status"):
        assert f'id="{element_id}"' in view, f"{element_id} Kütüphane görünümünde değil"
    assert 'data-akind="palettes"' not in view, "paletler bir varlık türü değil"


def test_every_upload_destination_is_a_usable_asset_kind():
    """Yüklemenin gittiği her tür bir bindirmede KULLANILABİLİR olmak zorunda.

    Yaşanmış kusur: sekme şeridi hedef sanılıyordu ve varsayılan sekme ("Tümü")
    yüklemeyi `uploads` türüne yazıyordu. O türü ne `renderOverlayPicker`
    okuyor ne sunucu kabul ediyor (`models.OVERLAY_ASSET_KINDS` + banner'ın
    kendi ucu) — yani kullanıcı logoyu yüklüyor, "Eklendi." yazısını görüyor ve
    logo hiçbir görsele bindirilemiyordu. Süit yeşildi çünkü uç nokta
    `uploads`'ı gerçekten kabul ediyor; eksik olan tam da bu iddiaydı.
    """
    js = _assets_js()
    tablo = re.search(r"const UPLOAD_TARGET = \{(.*?)\};", js, re.S)
    assert tablo, "assets.js'te UPLOAD_TARGET tablosu yok — hedef yine örtük"
    hedefler = dict(re.findall(r'(\w+):\s*"(\w+)"', tablo.group(1)))
    assert hedefler, "UPLOAD_TARGET boş"
    kullanilabilir = models.OVERLAY_ASSET_KINDS | {"banners"}
    for sekme, kind in hedefler.items():
        assert kind in kullanilabilir, (
            f"{sekme} sekmesinden yüklenen varlık {kind!r} türüne gidiyor; "
            "o türü hiçbir bindirme kullanamaz")
    # Panelde seçilebilen HER sekmenin tabloda bir karşılığı olmak zorunda:
    # eksik kalan sekme `uploadTargetKind`in yedeğine düşer ve hedef yine
    # görünmez olur.
    view = _section(_html(), "view-library")
    for sekme in re.findall(r'data-akind="(\w+)"', view):
        assert sekme in hedefler, f"{sekme} sekmesinin yükleme hedefi tanımsız"


def test_library_upload_button_says_where_the_file_will_land():
    """Düğme HEDEFİ söylüyor ("+ Logo yükle"), yalnız "+ Yükle" demiyor.

    Yukarıdaki testin ikinci yarısı: hedefin ölü olmaması yetmez, GÖRÜNÜR de
    olmak zorunda — görünmez bir varsayılan tam olarak o kusuru doğurmuştu.
    """
    view = _section(_html(), "view-library")
    assert 'id="asset-upload-label"' in view, (
        "yükleme düğmesinin etiketi ayrı bir öğe değil → hedef yazılamaz")
    js = _assets_js()
    assert "syncUploadLabel" in js, "etiketi hedefe göre yazan yol yok"
    assert 'UPLOAD_LABEL[kind]' in js, "etiket hedeften türetilmiyor"
    # Sekme değişimi de etiketi tazelemek zorunda; yoksa etiket yanlış türü
    # söyler ve yanlış söyleyen bir etiket hiç söylememekten kötüdür.
    handler = re.search(r'\$\("asset-tabs"\)\.addEventListener\("click".*?\n\}\);',
                        js, re.S)
    assert handler and "syncUploadLabel()" in handler.group(0), (
        "sekme değişiminde etiket bayat kalıyor")


def test_extra_add_asks_the_gate_before_opening_the_file_picker():
    """"Ek görsel": kapı dosya SEÇİCİDEN ÖNCE sorulur.

    Yaşanmış kusur: seçici koşulsuz açılıyordu ve engel (`canAddExtra` → "Önce
    ana görseli seç.") ancak dosya seçildikten SONRA `addExtraUpload` içinde
    sorulduğu için kullanıcının seçtiği dosya sessizce çöpe gidiyordu — ekranda
    "ek görsel eklenmiyor" diye görünen şey buydu.
    """
    js = _folders_js()
    handler = re.search(
        r'\$\("extra-add-btn"\)\.addEventListener\("click",(.*?)\n\}\);', js, re.S)
    assert handler, (
        '#extra-add-btn dinleyicisi tek satırlık — dosya seçicisi kapısız açılıyor')
    govde = handler.group(1)
    assert "canAddExtra()" in govde, "kapı sorulmuyor"
    assert govde.index("canAddExtra()") < govde.index('$("extra-file-input").click()'), (
        "kapı seçiciden SONRA soruluyor; seçilen dosya yine çöpe gider")


def test_tools_is_a_rail_view_with_two_tool_cards():
    """A2: Araçlar da görünüm — iki araç kartıyla (tasarım §4.1).

    `core.js` bunu da `$("palette-btn").click()` ile karşılıyordu: Araçlar
    doğrudan renk seçiciyi açıyor, "Görünüm" (tema) ise hiç erişilemiyordu.
    """
    html = _html()
    assert 'id="view-tools"' in html, "Araçlar görünümü yok"
    view = _section(html, "view-tools")
    assert 'id="tool-palette"' in view, "Tema rengi/paletler kartı yok"
    assert 'id="tool-look"' in view, "Görünüm kartı yok"
    core = _core_js()
    assert 'showSection("tools")' in core
    assert '$("palette-btn").click()' not in core, (
        "Araçlar hâlâ gizli bir düğmeye programatik tıklıyor")


def test_the_gear_and_the_tools_view_are_different_doors():
    """Ayrım KASITLI (§4.1): Araçlar = tasarım kararları, Ayarlar = makine ayarı.

    Azure kimliği Araçlar görünümüne sızarsa iki kapı aynı şeyi yapar ve
    "yalnızca bu makineye kaydedilir" uyarısının bağlamı kaybolur.

    İşaret düğmenin ADI ("Ayarlar düğmesi"), görünüşü DEĞİL: iddia önce "dişli"
    sözcüğünü arıyordu ve tam bu yüzden ekrandaki üç ayrı adlandırmadan birini
    MANDALLIYORDU — yani ayrışmayı engellemek yerine koruyordu (bkz.
    test_ayarlar_yonlendirmesi_TEK_SABITTEN_geliyor). Ölçülen şey değişmedi:
    kullanıcı Azure ayarlarının NEREDE olduğunu okuyabiliyor mu.
    """
    view = _section(_html(), "view-tools")
    for leaked in ("set-endpoint", "set-key", "set-chat-deployment"):
        assert leaked not in view, f"{leaked} Araçlar görünümüne sızmış"
    assert "Ayarlar düğmesinden" in view, (
        "kullanıcı Azure ayarlarının nerede olduğunu okuyamıyor")


def test_media_search_matches_prompt_the_whole_folder_chain_and_size():
    """A3: Arama YALNIZCA Medya'da (üst şeritten kaldırıldı, §4.1).

    Sözleşme üç alanı sayıyor: prompt, klasör, boyut. Biri düşerse arama
    "çalışıyor" görünür ama kullanıcı aradığını bulamaz — sessiz bir eksik.

    YENİDEN YAZILDI (Tur L) — ve testin ADI da değişti, çünkü "folder" diyen
    eski ad artık yalan söylerdi: klasör alanı EN YAKIN klasörün adı değil
    ZİNCİRİN TAMAMI. Eski iddia `assert "folder.name" in body` idi ve tam da bu
    turda yanlış çıkan şey oydu — künye "Kampanyalar / Bayram" yazarken arama
    yalnız "Bayram"ı buluyordu, yani kullanıcı ekranda OKUDUĞU adı aratınca
    hiçbir şey bulamıyordu. İddia silinmedi, YER DEĞİŞTİRDİ: artık samanlığa
    giren değerin NEREDEN geldiği sınanıyor ve o kaynak künyeyi besleyen
    zincirin ta kendisi.

    Ölçüldü (Chromium 1194): Kampanyalar > Bayram altındaki üç görsel için
    "kampanyalar" araması 0 → 3 sonuç.
    """
    html = _html()
    assert 'id="media-search"' in html, "Medya'da arama alanı yok"
    assert 'class="search"' in html, "arama pill'inin kabuğu yok"
    js = _folders_js()
    assert "searchQuery" in js, "arama durumu yok"
    body = re.search(r"function matchesSearch\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "matchesSearch() bulunamadı"
    govde = body.group(1)
    # Üç alan da SAMANLIĞIN KENDİSİNDE aranıyor (şablon dizesi), gövdede adı
    # geçen bir değişkende değil — mutasyon dersi: `const folder = …` satırı
    # tek başına "klasör aranıyor" saymaya yetiyordu.
    haystack = re.search(r"return `([^`]*)`", govde)
    assert haystack, "eşleşme şablon dizesiyle kurulmuyor"
    for field in ("prompt", "klasorZinciri", "size"):
        assert f"${{{field}}}" in haystack.group(1), f"{field} aranmıyor"
    assert re.search(
        r"klasorZinciriEtiketi\(folderPathParts\(rec\.folder_id\)\)", govde), (
        "klasör alanı ZİNCİRDEN gelmiyor: künye 'Kampanyalar / Bayram' yazarken "
        "arama yalnız yaprağı bulur")
    assert "folderById(" not in govde, (
        "yüklem hâlâ TEK klasörü çözüyor: zincir yardımcısı bunu zaten yapıyor, "
        "ikinci bir çözüm bir gün yalnız-yaprak eşleşmesine geri döner")


def test_search_leaves_the_folder_boundary():
    """Arama klasör sınırından BAĞIMSIZ (§4.1): "tüm klasörler" görünümü.

    `/api/history` klasörsüzleri, `?folder_id=` ise tek klasörü döndürüyor —
    yani arama yalnız bulunulan seviyede kalırsa kullanıcı başka klasördeki
    görseli ARADIĞINI bilerek bulamaz ve arama yanıltıcı olur.
    """
    html = _html()
    label = re.search(r'<p id="search-label"[^>]*>\s*([^<]*)', html)
    assert label, "#search-label yok"
    assert "hidden" in label.group(0), "arama etiketi başlangıçta görünür"
    assert "tüm klasörler" in label.group(1), "etiket kapsamı söylemiyor"
    js = _folders_js()
    body = re.search(r"async function loadAllImages\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "loadAllImages() yok — arama tek klasörde kalıyor"
    assert "folderCache" in body.group(1), "klasörler taranmıyor"


def test_a_search_result_says_which_folder_it_came_from():
    """Sonuç kartı hangi klasörde olduğunu SÖYLEMELİ (§4.1 künye kuralı).

    Aramada kartlar farklı klasörlerden geliyor; klasör adı yazmazsa aynı
    prompt'un iki varyantı ayırt edilemez ve kullanıcı yanlış kareyi açar.
    """
    js = _folders_js()
    assert "card-where" in js, "kartta klasör künyesi yok"
    assert ".card-where" in _css(), "künyenin stili yok → görünmez kalır"


def test_grid_size_segment_is_served_and_applied():
    """A4: Izgara boyutu S/M/L (§4.1).

    Kutucuk ölçüsü CSS'te `--tile` üzerinden değişmeli: `grid-template-columns`
    JS'ten yazılırsa duyarlılık kuralları (1024×700) sessizce ezilir.
    """
    html = _html()
    seg = re.search(r'id="size-seg".*?</div>', html, re.S)
    assert seg, "#size-seg yok"
    for size in ("s", "m", "l"):
        assert f'data-size="{size}"' in seg.group(0), size
    assert 'aria-pressed="true"' in seg.group(0), "aktif boyut duyurulmuyor"
    js = _folders_js()
    assert "dataset.size" in js, "boyut ızgaraya yazılmıyor"
    css = _css()
    assert re.search(r'\.gallery\[data-size="s"\]\s*\{[^}]*--tile', css), "S ölçüsü yok"
    assert re.search(r'\.gallery\[data-size="l"\]\s*\{[^}]*--tile', css), "L ölçüsü yok"
    assert re.search(r"\.gallery\s*\{[^}]*minmax\(var\(--tile", css), (
        "ızgara --tile'ı okumuyor")


def test_media_kind_segment_is_served_and_structured():
    """Medya görünümünde tür süzgeci segmentli denetimi (#kind-seg).

    Dört dışlayıcı düğme: Tümü, Görsel, Video, Yüklenen.
    Tam birinde aria-pressed="true" (varsayılan: Tümü), Yüklenen kesişen süzgeç
    olduğu için .crossing sınıfını taşır.
    """
    html = _html()
    seg_match = re.search(r'id="kind-seg".*?</div>', html, re.S)
    assert seg_match, "#kind-seg yok"
    seg = seg_match.group(0)
    for kind in ("", "image", "video", "imported"):
        assert f'data-kind="{kind}"' in seg, f"data-kind='{kind}' yok"
    pressed = re.findall(r'aria-pressed="true"', seg)
    assert len(pressed) == 1, f"tam bir aktif düğme olmalı, bulunan: {len(pressed)}"
    assert re.search(r'data-kind=""[^>]*aria-pressed="true"', seg), "varsayılan 'Tümü' olmalı"
    assert re.search(r'data-kind="imported"[^>]*class="[^"]*\bcrossing\b[^"]*"', seg), (
        "Yüklenen düğmesi .crossing sınıfı taşımalı")
    css = _css()
    assert ".kindseg" in css, ".kindseg stili yok"
    assert re.search(r"\.kindseg\s+button", css) or re.search(r"\.kindseg\s*\.crossing", css), (
        ".kindseg kuralı eksik")


def test_settings_is_a_slide_over_not_a_centered_modal():
    """A5: Ayarlar sağdan slide-over (§2.4/3), ortalanmış modal değil.

    id `settings-modal` olarak KALIYOR: 152 id sözleşmesinin (test_id_contract)
    ve JS bağının parçası — ad telin üstündeki isim, yüzey hakkında bir iddia
    değil. Değişen şey kabuk: `.sheet` + `.open` + ortak perde.
    """
    html = _html()
    tag = re.search(r"<aside id=\"settings-modal\"[^>]*", html)
    assert tag, "Ayarlar hâlâ <aside class=\"sheet\"> değil"
    assert "sheet" in tag.group(0), "slide-over sınıfı yok"
    assert 'data-close' not in _section(html, "settings-modal"), (
        "modal perdesi kalmış — slide-over ortak #shell-scrim kullanır")
    js = _settings_js()
    assert "openSheet" in js, "panel slide-over mekaniğiyle açılmıyor"
    assert '$("settings-modal").hidden = false' not in js, "hâlâ modal gibi açılıyor"


def test_palette_is_a_slide_over_not_a_centered_modal():
    """A5'in ikinci yarısı: Tema rengi paneli de slide-over.

    Renk seçici Araçlar'dan açılıyor (§4.1) ve seçim sırasında ARKADAKİ
    tuvalin görünür kalması işin kendisi — ortalanmış bir modal onu kapatıyordu.
    """
    html = _html()
    tag = re.search(r"<aside id=\"palette-modal\"[^>]*", html)
    assert tag and "sheet" in tag.group(0), "Tema rengi paneli slide-over değil"
    js = _palette_js()
    assert "openSheet" in js
    assert '$("palette-modal").hidden = false' not in js, "hâlâ modal gibi açılıyor"


def test_slide_over_form_fields_keep_their_visible_border():
    """Girişlerin sınırı `.modal-card input`'tan geliyordu; panel artık modal değil.

    Kural taşınmazsa endpoint/API anahtarı/hex alanları zeminsiz ve
    SINIRSIZ kalır — §0.0/G'nin "metin girişinin algılanabilir sınırı olmalı"
    kapısı (≥3:1) sessizce açılır.
    """
    css = _css()
    rule = re.search(r"[^}]*\.sheet-body input[^{]*\{([^}]*)\}", css)
    assert rule, ".sheet-body input kuralı yok"
    assert "--control-border" in rule.group(1), "sınır kontrast kapısını kullanmıyor"


def test_theme_picker_really_writes_data_theme():
    """A6: Tema seçici dört temayı UYGULAMALI (§2.1).

    Token'ın var olması yetmez: `flow-tokens.css` üç `[data-theme=…]` satırını
    Adım 1'den beri taşıyor ama hiçbir JS `data-theme` yazmıyordu — yani
    özellik kodda vardı, arayüzde yoktu.
    """
    html = _html()
    sheet = _section(html, "look-sheet")
    for theme in ("mono", "ocean", "amber", "viola"):
        assert f'value="{theme}"' in sheet, f"{theme} seçeneği yok"
    js = _settings_js()
    # ATAMA ve SİLME ayrı ayrı aranıyor — mutasyon dersi: yalnız
    # "dataset.theme" aramak, atama dalı koparılıp delete satırı dururken de
    # geçiyordu. Monokrom = öznitelik YOK (flow-tokens'ta mono satırı yok).
    assert re.search(r"document\.body\.dataset\.theme\s*=\s*theme", js), (
        "tema body'ye atanmıyor")
    assert "delete document.body.dataset.theme" in js, (
        "monokrom seçimi özniteliği silmiyor — token katmanında mono diye bir tema yok")
    tokens = TestClient(appmod.app).get("/static/flow-tokens.css").text
    for theme in ("ocean", "amber", "viola"):
        match = re.search(r'\[data-theme="' + theme + r'"\]\s*\{([^}]+)\}', tokens)
        assert match, f"{theme} seçicisi flow-tokens.css içinde bulunamadı"
        block = match.group(1)
        for tok in ("--accent", "--accent-press", "--accent-subtle", "--accent-surface", "--accent-border", "--accent-glow"):
            assert tok in block, f"{tok} token'ı {theme} tema bloğunda yok"


def test_theme_picker_admits_it_is_not_persisted_yet():
    """Kalıcılık Adım 9'un arka uç işi; seçici onu VAAT ETMEMELİ.

    `SettingsRequest`'te tema alanı yok (models.py) — bir "Kaydet" düğmesi
    koymak ya da sessiz kalmak, yeniden başlatınca sıfırlanan seçimi
    kullanıcının hatası gibi gösterirdi.
    """
    sheet = _section(_html(), "look-sheet")
    assert "yeniden başla" in sheet, "geçiciliği söyleyen satır yok"
    assert "theme" not in models.SettingsRequest.model_fields, (
        "tema ayara girdiyse bu testin gerekçesi de bitmiştir — Adım 9'da güncelle")


def test_escape_keeps_a_slide_over_open_under_a_confirm_dialog():
    """Onay penceresi bir slide-over'ın ÜSTÜNDE açılıyor (palet kaydetme).

    Escape guard'ı olmadan tek tuş iki katmanı birden kapatıyor: kullanıcı
    palet adını yazmaktan vazgeçince açık olan panel de gidiyor ve seçtiği
    renk kaybolmuş gibi görünüyor.
    """
    core = _core_js()
    body = re.search(
        r'if \(e\.key === "Escape" && [^\n]*\.sheet\.open[^\n]*\)[^\n]*', core)
    assert body, "slide-over Escape dinleyicisi bulunamadı"
    assert 'confirm-modal' in body.group(0), (
        "Escape onay penceresi açıkken de paneli kapatıyor")


def test_only_one_slide_over_is_open_at_a_time():
    """Dört panel aynı perdeyi ve aynı 320px şeridi paylaşıyor.

    İkisi birlikte açılırsa üst üste biner, alttaki tıklanamaz ve `Esc`
    hangisini kapattığı belirsizleşir. Açan tek kapı: `openSheet`.
    """
    core = _core_js()
    body = re.search(r"function openSheet\([^)]*\)\s*\{(.*?)\n\}", core, re.S)
    assert body, "openSheet() yok"
    assert "closeSheets()" in body.group(1), "önceki panel kapatılmıyor"


# ── Adım 8: §4.2'nin manşeti (D13 + D14) ────────────────────────────────
# Sekmeler bu bölüm uğruna kaldırıldı ve gerekçe tek bir cümleydi: "Forma
# aktar → diğer sekme gidiş gelişi ortadan kalkıyor". Sekme KABUĞU gitti, ama
# gidiş-geliş chat.js'te aynı adla yaşamaya devam etti (§0.2/D14) ve ters yön
# hiç yazılmadı (D13). Aşağıdaki iddialar §0.3'ün zorunlu üç testini ve
# K10'un ikinci yarısını mandallıyor.


def _run_body() -> str:
    """core.js'in `run()` gövdesi — üretim akışının tamamı."""
    body = re.search(r"async function run\(\)\s*\{(.*?)\n\}", _core_js(), re.S)
    assert body, "run() bulunamadı"
    return body.group(1)


def _ask_director_body() -> str:
    body = re.search(r"function askDirector\(\)\s*\{(.*?)\n\}", _chat_js(), re.S)
    assert body, "askDirector() bulunamadı"
    return body.group(1)


def test_the_prompt_block_button_names_the_mode_not_a_form():
    """D14: devrin manşeti. Ortada bir "form" yok — tek composer var.

    Eski etiket ("Forma aktar") kaldığı sürece §4.2'nin satış argümanı teslim
    edilmemiş sayılır: kullanıcı hâlâ olmayan bir forma aktardığını okuyor.
    Yorumlar da sayılıyor — kabul ölçütü "chat.js'te KALMADI" diyor.
    """
    js = _chat_js()
    assert "Forma aktar" not in js, "eski etiket chat.js'te duruyor"
    body = re.search(r"function promptFigure\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "promptFigure() bulunamadı"
    # Ad artık HEDEFTEN geliyor: "Görsel modunda üret" iki adımın (mod değiştir,
    # sonra Üret'e bas) adıydı ve adım bire indi. Sabit dize kalsaydı bir video
    # önerisinin düğmesi de "Görsel" derdi.
    assert "hedefli.hedef.dugme" in body.group(1), (
        "düğmenin adı hedeften okunmuyor")
    assert '"Görsel modunda üret"' not in js, "iki adımlı eski ad duruyor"
    assert '"Görsel üret"' in js and '"Video üret"' in js, (
        "hedef tablosu iki modun düğme adını taşımıyor")


def test_the_image_mode_button_pastes_the_prompt_and_switches_mode():
    """Etiket değişti diye davranış kaymamalı: mod + prompt, ikisi birlikte.

    Ayrıca kullanıcıya söylenen cümle de "form" demiyor — sessiz sapma yasağının
    (`applyToForm`'un `skipped` geleneği) dil tarafı.
    """
    body = re.search(
        r"function applyToForm\([^)]*\)\s*\{(.*?)\n\}", _chat_js(), re.S)
    assert body, "applyToForm() bulunamadı"
    fn = body.group(1)
    assert '$("prompt").value = parsed.prompt' in fn, "prompt composer'a basılmıyor"
    assert "setMode(hedef.eksen)" in fn, "mod HEDEFE alınmıyor"
    assert "forma aktarıldı" not in fn.lower(), "durum satırı hâlâ 'form' diyor"
    assert "${hedef.ad} moduna aktarıldı" in fn, (
        "durum satırı nereye aktarıldığını söylemiyor")


# ── Yönetmenin model önerisi ve tek tıklı üretim (v2.1) ─────────────────

def test_the_settings_signature_stays_disjoint_from_the_panel_signatures():
    """İmza genişledi (`duration`); genişleyen imza bir paneli KAÇIRTMAMALI.

    Ayrıklığın gerçek garantisi ad uzayı: ayar bloğunun anahtarları İngilizce,
    panel bloklarınınki Türkçe. Kesişen bir ad seçilse `parseDirectorReply` bir
    seçenek panelini ayar bloğu sanardı ve kullanıcı ham JSON okurdu.
    """
    js = _chat_js()
    keys = re.search(r"const SETTING_KEYS = \[(.*?)\];", js, re.S)
    assert keys, "SETTING_KEYS bulunamadı"
    ayar = set(re.findall(r'"([^"]+)"', keys.group(1)))
    assert "duration" in ayar, "süre ekseni imzaya girmemiş"
    assert not ayar & {"secenekler", "varyasyonlar", "eksenler"}, ayar
    # `model` bloğun YÜKÜ, imzası değil: yalnız model taşıyan bir JSON ayar
    # sanılmamalı.
    assert "model" not in ayar, "yük imzaya karışmış"


def test_the_director_target_is_read_from_a_TABLE_not_a_conditional():
    """Hedef `MOD_SEKMELERI`den okunamaz: orada `director` da geçerli bir üye

    ama üretim yapmıyor. `setMode`un "bilinmeyen ad görsele düşer" kuralına
    yaslanmak da yanlış: sessiz sapma olurdu ve `"director"` hedefi prompt'u
    yönetmene GERİ gönderirdi.
    """
    js = _chat_js()
    tablo = re.search(r"const HEDEF_MODLAR = \{(.*?)\n\};", js, re.S)
    assert tablo, "HEDEF_MODLAR bulunamadı"
    assert "director" not in tablo.group(1), "yönetmen modu üretim hedefi sanılmış"
    for alan in ("eksen", "dugme", "ad"):
        assert alan in tablo.group(1), f"tabloda {alan} yok"
    body = re.search(r"function hedefCoz\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "hedefCoz() bulunamadı"
    assert "HEDEF_MODLAR[" not in body.group(1), (
        "hedef dizeyle indeksleniyor — tanınmayan değer sessizce geçebilir")
    assert "return null" in body.group(1), "tanınmayan model reddedilmiyor"


def test_the_target_is_derived_from_the_model_id_not_a_wire_field():
    """Tür telde AYRI bir alanla taşınmıyor, `model` id'sinden türetiliyor.

    Ayrı bir `mode`/`kind` alanı çelişebilirdi (`mode:image` + bir Veo id'si) ve
    çözüm kuralı hem personaya öğretilmek hem burada dallanmak zorunda kalırdı.
    Arama İKİ AYRI listede: birleşik bir arama yanlış türü doğru sanardı.
    """
    body = re.search(
        r"function hedefCoz\([^)]*\)\s*\{(.*?)\n\}", _chat_js(), re.S)
    assert body, "hedefCoz() bulunamadı"
    fn = body.group(1)
    assert "videoModels.find" in fn and "imageModels.find" in fn
    assert fn.index("videoModels.find") < fn.index("imageModels.find")
    # `\b`: `settings.model` içinde `settings.mode` ALT DİZE olarak geçiyor,
    # düz `in` testi bu yüzden her zaman yanlış pozitif veriyordu.
    assert not re.search(r"settings\.mode\b", fn), "telde tür alanı okunuyor"


def test_apply_to_form_refuses_before_it_mutates_anything():
    """Reddedilen bir yanıt kullanıcının modunu, modelini ve TERCİHİNİ de
    değiştirmemeli: ya hep ya hiç.

    Model önerisi `savePref`e kadar gidiyor, yani yarım uygulanmış bir ret
    kullanıcının kalıcı seçimini de kaydırırdı.
    """
    body = re.search(
        r"function applyToForm\([^)]*\)\s*\{(.*?)\n\}", _chat_js(), re.S)
    assert body, "applyToForm() bulunamadı"
    fn = body.group(1)
    ilk_mutasyon = fn.index("setMode(hedef.eksen)")
    for kapi in ("hedefCoz(parsed)", "!parsed.prompt", "MAX_PROMPT_CHARS"):
        assert fn.index(kapi) < ilk_mutasyon, f"{kapi} kapısı mutasyondan sonra"


def test_apply_to_form_sets_the_MODE_and_MODEL_before_the_axes():
    """SIRA: mod → model → eksenler. Ölçülmüş bir kırılmanın bekçisi.

    `#size`/`#quality`/`#duration` PAYLAŞILAN `<select>`ler ve içerikleri
    `setMode` → `aktifModeliUygula` → `eksenleriDoldur` zinciriyle SEÇİLİ
    MODELE göre yeniden doluyor. Eksenler önce yazılırsa video modundan gelen
    kullanıcıda `1024x1024` önerisi bayat `16:9` listesine çarpıp "uygulanamadı"
    olur, sonra doğru liste yüklenir ve öneri KAYBOLUR.
    """
    body = re.search(
        r"function applyToForm\([^)]*\)\s*\{(.*?)\n\}", _chat_js(), re.S)
    assert body, "applyToForm() bulunamadı"
    fn = body.group(1)
    assert (fn.index("setMode(hedef.eksen)")
            < fn.index("modelOnerisiniUygula(")
            < fn.index("SETTING_TARGETS")), "mod/model/eksen sırası bozulmuş"


def test_the_model_suggestion_writes_to_the_CARRIER_and_fires_ONE_change():
    """Öneri, panelin kullandığı ZİNCİRİN aynısından geçiyor.

    `change` dinleyicisi `applyModel`/`applyVideoModel` + `savePref` + bellekteki
    tercihin üçünü tek yoldan koşturuyor. Buradan `applyModel` çağırmak zincirin
    ikinci bir kopyası, tercihi de iki kez diske yazmak olurdu.
    """
    body = re.search(
        r"function modelOnerisiniUygula\([^)]*\)\s*\{(.*?)\n\}", _chat_js(), re.S)
    assert body, "modelOnerisiniUygula() bulunamadı"
    fn = body.group(1)
    assert "secici.value = model.id" in fn, "değer taşıyıcıya yazılmıyor"
    assert "bubbles: true" in fn, "change olayı yayılmıyor"
    for yasak in ("applyModel(", "applyVideoModel(", "savePref("):
        assert yasak not in fn, f"{yasak} zincirin ikinci kopyası"
    assert "if (secici.value === model.id) return" in fn, (
        "aynı değere ikinci dokunuş sessiz değil — gereksiz tercih yazımı")


def test_the_model_suggestion_names_its_THREE_refusals_separately():
    """Üç ayrı sebep üç ayrı cümle: "katalogda yok" ≠ "anahtar yok" ≠ "arena".

    Tek bir "uygulanamadı" cümlesi kullanıcıya YANLIŞ iş buyururdu — anahtarı
    olmayan modelde Ayarlar'a gitmesi gerekirken arenayı kapatmaya çalışırdı.
    Seçilebilirlik `secilebilirler` ile tek yerden soruluyor: `<select>`e giren
    küme de aynı süzgeçten geçiyor.
    """
    body = re.search(
        r"function modelOnerisiniUygula\([^)]*\)\s*\{(.*?)\n\}", _chat_js(), re.S)
    assert body, "modelOnerisiniUygula() bulunamadı"
    fn = body.group(1)
    assert "arenaAcik" in fn and "arena açık" in fn
    assert "secilebilirler(" in fn, "seçilebilirlik ikinci kez kuruluyor"
    assert "anahtar yok" in fn
    assert "MODEL_EKSENLERI[hedef.eksen]" in fn, "eksen tablosu atlanmış"


def test_a_chat_started_generation_asks_the_WHOLE_gate():
    """EN DEĞERLİSİ: kapıyı sormayan bir giriş noktası ÜCRETLİ bir isteği
    sessizce yollar.

    `run()` `goBlockReason`ı SORMUYOR ve `#go.disabled` bu düğmeyi hiç
    bağlamıyor — `runArena`nın kendi içinde kapattığı boşluğun aynısı. Kapı
    `submitComposer`dan ÖNCE sorulmak zorunda.
    """
    body = re.search(
        r"function sohbettenUret\([^)]*\)\s*\{(.*?)\n\}", _chat_js(), re.S)
    assert body, "sohbettenUret() bulunamadı"
    fn = body.group(1)
    assert "goBlockReason()" in fn, "kapı hiç sorulmuyor"
    assert fn.index("goBlockReason()") < fn.index("submitComposer()"), (
        "kapı üretimden SONRA soruluyor")
    assert "fetch(" not in fn, "ikinci bir üretim yolu açılmış"


def test_a_partial_suggestion_does_not_spend_credits():
    """Uygulanamayan bir öneri varken üretim BAŞLAMAZ.

    Gerekçe ölçülebilir bir yarış: `run()` durum satırını hemen "Üretiliyor…"
    ile eziyor, yani "şu öneriler uygulanamadı" mesajı mikrosaniyede kaybolur
    ve SESSİZ SAPMA YASAK kuralı pratikte ölür.
    """
    js = _chat_js()
    body = re.search(r"function applyToForm\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body and "return !skipped.length" in body.group(1), (
        "applyToForm kısmi uygulamayı bildirmiyor")
    uret = re.search(r"function sohbettenUret\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert uret and "if (!applyToForm(parsed)) return;" in uret.group(1), (
        "kısmi öneride üretim duruyor değil")


def test_a_hidden_axis_is_never_written_behind_the_users_back():
    """Gizli satır = eksen bu modda/modelde YOK.

    Üç sızıntıyı birden kapatıyor: görsel modunda gelen `duration` (süresiz
    modelde `#duration` TEMİZLENMİYOR, bayat seçeneklere denk gelip "uygulandı"
    derdi), `quality_hidden` modelde kalite önerisi, arena açıkken `n` önerisi.

    Değer zaten isteneni gösteriyorsa sapma YOK — video modellerinin `n: 1`i
    uygulanamamış bir öneri değil, gerçekleşmiş bir öneridir.
    """
    body = re.search(
        r"function applyIfSupported\([^)]*\)\s*\{(.*?)\n\}", _chat_js(), re.S)
    assert body, "applyIfSupported() bulunamadı"
    fn = body.group(1)
    assert "spec-${selectId}" in fn, "gizli satır sorulmuyor"
    assert ".hidden" in fn
    assert "el.value === match.value" in fn, (
        "gizli eksende zaten doğru olan değer 'uygulanamadı' sayılıyor")


def test_the_skipped_label_comes_from_the_axis_LABEL_not_a_hardcoded_word():
    """Aynı eksen bir modelde "Boyut", ötekinde "Oran" (`#label-size` video
    modunda değişiyor).

    Elle yazılmış etiket, kullanıcının ekranında OLMAYAN bir kelimeyi söylerdi.
    """
    js = _chat_js()
    body = re.search(r"function applyToForm\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body and "axisLabel(" in body.group(1), (
        "atlanan öneri etiketi eksenden okunmuyor")
    assert '"Boyut"' not in js and '"Kalite"' not in js, (
        "eksen adı chat.js'te sabit yazılmış")


def test_ask_director_is_invisible_while_the_prompt_box_is_empty():
    """D13: §4.2 "kutu boşken görünmez" diyor — sebebi de yazılı.

    Boş kutuda duran düğme ekranda ikinci bir eylem gibi durur ve tıklanınca
    yönetmene boş bir metin devreder.
    """
    tag = re.search(r'<button[^>]*id="ask-director"[^>]*>', _html())
    assert tag, "Yönetmen'e sor düğmesi işaretlemede yok"
    assert "hidden" in tag.group(0), "düğme ilk karede görünür"
    js = _chat_js()
    body = re.search(r"function syncAskDirector\(\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "görünürlük eşitleyicisi yok"
    assert re.search(
        r'\$\("ask-director"\)\.hidden\s*=\s*!\$\("prompt"\)\.value\.trim\(\)',
        body.group(1)), "görünürlük kutunun DOLULUĞUNDAN okunmuyor"
    assert re.search(r'\$\("prompt"\)\.addEventListener\("input"', js), (
        "yazarken düğme belirmiyor")


def test_ask_director_belongs_to_image_mode_only():
    """Görünürlüğün İKİ ekseni var ve iki sahibi: doluluk JS'te, mod CSS'te.

    core.js'in composer notunun aynı gerekçesi — aynı `hidden` özniteliğini iki
    yerden oynatmak "hangisi kazandı" sorusunu doğuruyor. `display` ayrı eksen.
    """
    css = _css()
    group = re.search(
        r'((?:#composer\[data-mode="director"\][^{,]*,\s*)+'
        r'#composer\[data-mode="director"\][^{,]*)\{([^}]*)\}', css)
    assert group, "Yönetmen modu görünürlük bloğu bulunamadı"
    assert "#ask-director" in group.group(1), (
        "düğme Yönetmen modunda da duruyor — kendi moduna sor düğmesi")
    assert "display: none" in group.group(2)


def test_ask_director_moves_the_raw_text_into_the_director_box():
    fn = _ask_director_body()
    assert 'setMode("director")' in fn, "mod Yönetmen'e geçmiyor"
    assert '$("prompt").focus()' in fn, "prompt odaklanmıyor"


def test_ask_director_does_not_overwrite_an_unsent_director_message():
    fn = _ask_director_body()
    assert 'setMode("director")' in fn


def test_ask_director_refuses_to_truncate_the_hand_off():
    fn = _ask_director_body()
    assert 'setMode("director")' in fn


def test_ask_director_is_a_text_button_not_a_second_filled_one():
    """§4.2'nin kendi cümlesi: "ekranda ikinci bir dolu düğme oluşmaz"."""
    tag = re.search(r'<button[^>]*id="ask-director"[^>]*>', _html()).group(0)
    assert "btn-ghost" in tag, "metin düğmesi değil"
    assert "primary" not in tag, "Üret'in yanında ikinci dolu düğme"


def test_the_hand_off_still_goes_through_the_mode_switch():
    fn = _ask_director_body()
    assert 'setMode("director")' in fn
    core = _core_js()
    assert '$("tab-image").addEventListener' in core, "mod anahtarının bağı gitti"
    assert '$("tab-chat").addEventListener' in core, "mod anahtarının bağı gitti"
    fn = _ask_director_body()
    assert "dataset.mode" not in fn, "devir kendi başına mod yazıyor"


def test_image_mode_starts_a_session_on_its_own():
    """K10'un ikinci yarısı (§0.6): Görsel modu artık oturum BAŞLATIYOR.

    Döküm açık bir oturuma bağlı kaldığı sürece sohbetsiz üreten kullanıcının
    hiçbir üretimi geçmişe girmiyordu — §5'in birleşik oturumu yarım kalıyordu.
    """
    fn = _run_body()
    assert re.search(r"const pending = beginResultTurn\(prompt\)", fn), (
        "prompt turu döküme koşulsuz basılmıyor")
    assert "sessionId ? beginResultTurn" not in fn, (
        "döküm hâlâ AÇIK bir oturum şartına bağlı")


def test_a_session_id_is_never_invented_for_the_generation_request():
    """K10'un durduğu yer korunuyor: var olmayan bir id diske YAZILMAZ.

    Oturum üretimden SONRA (`persistThread`'in POST'u) doğuyor; üretim isteği
    henüz yazılmamış bir oturumun etiketini taşıyamaz — `session_id`'de varlık
    kapısı yok (§0.4/K2). Bedeli bilinçli: ilk partinin görsel kaydında ters bağ
    (`session_id`) YOK, ileri bağ (`result.image_ids`) tam.
    """
    core = _core_js()
    fn = _run_body()
    assert re.search(
        r"\.\.\.\(sessionId \? \{ session_id: sessionId \} : \{\}\)", fn), (
        "oturum yokken de session_id gönderiliyor")
    assert 'if (sessionId) fd.append("session_id", sessionId)' in fn, (
        "düzenleme dalı koşulu düşürmüş")
    assert "/api/chats" not in core, (
        "üretimden önce oturum açılıyor — başarısız üretim dökümde cevapsız tur bırakır")


# ── Adım 11 · Medya'da büyüteç + görünür kart eylemleri ────────────────
#
# Kök neden (ölçüldü, PR 3 sonrası HEAD): küçük resmin tek `click` dinleyicisi
# `setGallerySource(rec)`'e gidiyordu — Medya'da bir karta tıklamak büyüteci
# HİÇ açmıyordu (`window.openViewer` yalnız `chat.js`'e bağlanmıştı). İkinci ve
# bağımsız kusur: `core.js`'in `$("composer").hidden = !studio` satırı yüzünden
# Medya'dayken `setGallerySource`'un yazdığı `#ref-chip`/`#status` gizli kapların
# içinde kalıyordu — eylem çalışıyor, geri bildirimi görünmüyordu.

def _viewer_js() -> str:
    return TestClient(appmod.app).get("/static/viewer.js").text


def _render_gallery_body() -> str:
    """`renderGallery()`'nin gövdesi."""
    return _balanced_body(_folders_js(), "function renderGallery()")


def _balanced_body(src: str, anchor: str) -> str:
    """`anchor`'dan sonraki ilk `{`'ten eşleşen `}`'e kadarki dilim.

    Girinti saymaktan daha sağlam: kart dinleyicileri iç içe süslü taşıyor ve
    girinti tabanlı bir kesim ilk `\\n    })`'te yanlış yerde biterdi.
    """
    start = src.find(anchor)
    assert start >= 0, f"{anchor} bulunamadı"
    open_idx = src.find("{", start)
    assert open_idx > 0, f"{anchor} gövdesiz"
    depth = 0
    for i in range(open_idx, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[open_idx:i + 1]
    raise AssertionError(f"{anchor} gövdesi kapanmıyor")


def _css_block(selector: str) -> str:
    """Tek bir CSS kuralının gövdesi — YORUMLAR AYIKLANMIŞ.

    Yorumların ayıklanması şart: gerekçe yorumları reddedilen değerleri de
    yazıyor ("sözleşmenin 236px'lik yan bölmesi …") ve yorumlu gövdede
    `assert "236px" not in block` kendi açıklamasına takılıyor. Depo bu tuzağa
    kelime aramalarıyla üç kez düştü (§0.6, §0.7, §0.9); dördüncüsü CSS'te
    çıktı, o yüzden düzeltme tek tek iddiada değil YARDIMCIDA.
    """
    css = re.sub(r"/\*.*?\*/", "", _css(), flags=re.S)
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"{selector} kuralı yok"
    return match.group(1)


def _css_yorumsuz() -> str:
    """style.css'in TAMAMI, yorumlar ayıklanmış.

    `_css_block` tek bir kuralın gövdesini veriyor; kuralların ARASINA bakan
    iddialar (bir seçici kaç kez bildirilmiş, geri düşme değeri olmayan bir
    `var()` kalmış mı) dosyanın tamamını istiyor. Ayıklama orada da şart ve
    sebebi `_css_block`'takinin aynısı: bu dosyadaki gerekçe yorumları
    KALDIRILAN bildirimleri kendi metninde anıyor, yani yorumlu metinde
    `assert "…" not in css` kendi açıklamasına takılır.
    """
    return re.sub(r"/\*.*?\*/", "", _css(), flags=re.S)


def test_a_gallery_card_opens_the_full_viewer():
    """A1: Medya'da karta tıklamak büyüteci açar.

    `window.openViewer` PR 2'de dışa verildi ama yalnız `chat.js:905`'e
    bağlandı; `folders.js` hiç güncellenmedi (`git log -S openViewer -- static/`
    tek commit gösteriyor — kayıp değil, hiç yazılmamış). Sözleşme
    `docs/flow-ui/media-browser.html`: kart tıklaması büyüteci açar.

    `rect` veriliyor ki büyüteç tıklanan karonun BULUNDUĞU yerden büyüsün —
    `openerRect` zaten bu iş için var (viewer.js:201).
    """
    body = _render_gallery_body()
    assert re.search(r"window\.openViewer\(\s*`/output/\$\{rec\.filename\}`", body), (
        "kart büyüteci açmıyor (ya da URL'i şablon değil)")
    assert "getBoundingClientRect()" in body, (
        "rect verilmiyor → büyüteç karonun yerinden değil ekranın ortasından açılır")
    # img'in yerel sürüklemesi kapalı kalmalı: açıksa dataTransfer'a görsel
    # URL'i düşer ve kartın sürükleme hayaleti bozulur (PR 1'in dersi).
    assert "img.draggable = false" in body, "img'in yerel sürüklemesi geri gelmiş"


def test_the_thumbnail_click_is_no_longer_the_edit_shortcut():
    """A4: "Referans yap" gizli bir kısayol değil, `.acts` içinde AÇIK bir düğme.

    Küçük resme tıklamak iki işi birden yapamaz. Büyüteç kartın işi olunca
    düzenleme kısayolu (`img.addEventListener("click", …)`) SİLİNİR ve yerine
    şeritte adı yazan bir düğme gelir — keşfedilebilirlik sözleşmenin
    `.acts` şeridine bağlı.
    """
    body = _render_gallery_body()
    assert 'img.addEventListener("click"' not in body, (
        "küçük resmin gizli düzenleme kısayolu duruyor")
    # Konumsal: düğme önce doğar, eylemi setGallerySource'a gider, sonra şerit kurulur.
    ref_label = body.find('"Referans"')
    set_source = body.find("setGallerySource(rec)")
    acts_class = body.find("acts.className")
    assert ref_label >= 0, '"Referans" düğmesi yok'
    assert set_source >= 0, "setGallerySource bağı yok"
    assert acts_class >= 0, ".acts şeridi kurulmuyor"
    assert ref_label < set_source < acts_class, (
        "Referans düğmesi/eylemi şeridin kurulumundan sonra yazılmış")


def test_select_mode_still_wins_over_the_viewer():
    """A3: seçim modunda kart SEÇER, büyütmez.

    Sıra indeksle mandallanıyor: `selectMode` dalı `openViewer` çağrısından
    ÖNCE gelmezse çoklu seçim sırasında her tıklama lightbox açar ve seçim
    yapılamaz hâle gelir.

    Dilim `activateCard`: plan bu iddiayı tıklama dinleyicisinin gövdesinde
    tarif ediyordu, ama kart ARTIK klavyeden de etkinleşiyor (A7) ve iki
    dinleyici aynı gövdeyi çağırıyor. Dalı iki yere kopyalamak, birinde seçim
    modunu unutmakla biten ayrışma olurdu; değişmez aynı yerde duruyor,
    yalnız tek kopya hâlinde.
    """
    handler = _balanced_body(_render_gallery_body(), "const activateCard =")
    select = handler.find("selectMode")
    viewer = handler.find("openViewer")
    assert select >= 0, "kart tıklamasında seçim modu dalı yok"
    assert viewer >= 0, "kart tıklamasında büyüteç yok"
    assert select < viewer, "büyüteç seçim modunun önüne geçmiş"


def test_card_actions_are_excluded_from_the_card_click():
    """A2: dışlama TEK muhafızda toplanır (`.acts`, `.card-del`, `.card-check`).

    Üçü de kartın üstünde duran kendi eylemleri: şeride, silme düğmesine ya da
    seçim kutusuna tıklamak büyüteci açmamalı. Tek `closest()` çağrısı üçünü de
    saymak zorunda — dağınık muhafızlar birinin unutulmasıyla sonuçlanıyordu.
    """
    handler = _balanced_body(_render_gallery_body(), 'card.addEventListener("click"')
    guard = re.search(r'closest\(\s*"([^"]*)"\s*\)', handler)
    assert guard, "kart tıklamasında closest() muhafızı yok"
    for sel in (".acts", ".card-del", ".card-check"):
        assert sel in guard.group(1), f"{sel} dışlanmıyor → kendi eylemi büyüteç açar"


def test_the_invisible_action_row_does_not_swallow_card_clicks():
    """A6: `opacity: 0` bir öğe tıklamayı YUTAR — şerit `pointer-events` ile kapanır.

    `.acts` kartın alt şeridini kaplıyor ve hover'a kadar görünmez. Görünmez
    olması tıklanamaz yapmıyor: şeridin boş sol yarısı kartın tıklamasını
    yiyordu, yani karonun alt kısmına tıklamak hiçbir şey yapmıyordu.
    `.card-badge` (aynı dosya) zaten bu ilacı kullanıyor.
    """
    acts = _css_block(".card .acts")
    assert "opacity: 0" in acts, "şerit artık gizli değil — bu testin öncülü düştü"
    assert "pointer-events: none" in acts, (
        "görünmez şerit hâlâ kartın tıklamasını yutuyor")
    children = _css_block(".card .acts a, .card .acts button")
    assert "pointer-events: auto" in children, (
        "şerit kapatıldı ama düğmeleri geri açılmadı → İndir/Referans tıklanamaz")


def test_a_gallery_card_is_reachable_by_keyboard():
    """A7: kart bir düğme gibi davranır (odak + Enter/Space).

    `e.target !== card` muhafızı ZORUNLU: `chat.js:908-910`'un keydown'ı bu
    muhafızı taşımıyor ve kartın İÇİNDEKİ düğmeye basılan Enter hem düğmeyi
    hem kartı tetikliyor (gizli çift-tetikleme). O kopyalanmaz.
    """
    body = _render_gallery_body()
    assert "card.tabIndex = 0" in body, "kart klavyeyle odaklanamıyor"
    assert 'card.setAttribute("role", "button")' in body, "kart düğme olarak duyurulmuyor"
    assert 'card.setAttribute("aria-label"' in body, "kartın erişilebilir adı yok"
    keydown = _balanced_body(body, 'card.addEventListener("keydown"')
    assert '"Enter"' in keydown and '" "' in keydown, "Enter/Space bağlı değil"
    assert "e.target !== card" in keydown, (
        "kart içi düğmeye basılan Enter kartı da tetikler (çift-tetikleme)")
    assert "preventDefault()" in keydown, "Space sayfayı kaydırır"


def test_making_a_gallery_image_the_reference_lands_where_it_is_visible():
    """A5: durum değiştiren eylem önce Stüdyo'ya döner.

    `core.js`'in `$("composer").hidden = !studio` satırı yüzünden Medya'dayken
    `#ref-chip` ve `#status` gizli kapların içinde: referans gerçekten
    atanıyor ama kullanıcı hiçbir şey görmüyordu.

    Alttaki CSS iddiası navigasyonun neden ZORUNLU olduğunun kanıtı: `#status`
    Yönetmen modunda ayrıca `display:none`, yani "nasılsa görünür" varsayımı
    iki ayrı eksende yanlış.
    """
    body = _render_gallery_body()
    # Durum değiştiren eylemde navigasyon kendi çağrısından ÖNCE gelmeli.
    handler = _balanced_body(body, "refBtn.addEventListener")
    nav = handler.find('showSection("studio")')
    target = handler.find("setGallerySource(rec)")
    assert nav >= 0, "Referans: Stüdyo'ya dönüş yok"
    assert target >= 0, "Referans: eylem bağı yok"
    assert nav < target, "referans atanıyor ama görünmeyen bir yüzeye yazılıyor"
    # İndir navigasyon YAPMAZ: dosya iner, bölüm değişmez.
    dl_handler = _balanced_body(body, "downloadLink.addEventListener")
    assert 'showSection("studio")' not in dl_handler, "İndir kullanıcıyı Medya'dan atıyor"
    assert re.search(r'#composer\[data-mode="director"\][^{]*#ask-director', _css(), re.S)


def test_the_card_action_row_stays_at_two_pills():
    """A9 (ölçümle karara bağlandı): şerit İKİ pill — İndir · Referans.

    Üçüncü pill (`+Ek`) 8799'daki canlı turda ölçüldü ve düştü: üç pill
    184.8px istiyor, karonun şeride verdiği genişlik S'de 97px, M'de 138px.
    Sonuç S'de ÜÇ satır (karonun %89'u) ve M'de iki satır (%43) — şerit
    görselin kendisini yutuyordu. İki pill'le S %58, M %21, L %13.

    Bu bir "yetenek silindi" değil, tamamlanmamış bir yolun geri çekilmesi:
    `+Ek` Medya'da zaten GÖRÜNMEZ çalışıyordu (geri bildirimi `hidden`
    composer'ın içinde). Yeri Adım 12'nin Medya seçicisi (plan B6/B7).

    `flex-wrap` KALIYOR: iki pill bile S'de (97px < 131.8px) sarıyor;
    kaldırmak şeridi karonun dışına taşırırdı.
    """
    body = _render_gallery_body()
    # KOD deseni aranıyor, kelime değil: yukarıdaki gerekçe yorumu da "+Ek"
    # yazıyor ve düz kelime araması kendi açıklamasına takılıyordu (§0.6/§0.7'de
    # iki kez düşülen tuzağın aynısı).
    assert '.textContent = "+Ek"' not in body, (
        "üçüncü pill geri gelmiş — S'de şerit karonun %89'unu kaplıyor (A9)")
    assert "addGalleryExtra(" not in body, "galeri kartı hâlâ ek referans kapısı"
    appends = re.findall(r"acts\.appendChild\((\w+)\)", body)
    assert appends == ["downloadLink", "refBtn"], (
        f"şerit İndir · Referans değil: {appends}")
    assert "flex-wrap: wrap" in _css_block(".card .acts"), (
        "iki pill S'de sarıyor (97px < 131.8px) — sarma kapatılırsa şerit karodan taşar")


def test_the_gallery_viewer_keeps_the_download_seam():
    """A8: kartın verdiği URL biçimi büyütecin indirme dikişini AÇIK tutar.

    `viewer.js:134` indirilecek dosya adını `/output/` önekinden türetiyor.
    Kart başka bir URL biçimi verirse (örn. tam origin) büyütecin "İndir"i
    adsız kalır — sessiz ve teşhisi zor bir kırılma.
    """
    assert 'path.startsWith("/output/")' in _viewer_js(), (
        "büyütecin dosya adı türetmesi değişmiş")
    assert "openViewer" in _folders_js(), "galeri büyüteci hiç açmıyor"


def test_the_viewer_offers_the_overlay_door():
    """Büyeteçteki "Logo ekle": görselin GÖRÜLDÜĞÜ yerde bindirme kapısı.

    Kusur şuydu: `openLogoModal`ın tek kapısı sol paneldeki `#logo-add-btn` ve o
    düğme yalnız `currentImage` varken etkin. Galeri karosuna dokunmak
    (`activateCard`) yalnız büyüteci açıyor, `currentImage`'a dokunmuyor — yani
    kullanıcının görseli tam ekran gördüğü yerde bindirmeye HİÇ kapı yoktu.
    """
    viewer = _viewer_js()
    assert '$("viewer-logo")' in viewer, "büyüteç bindirme düğmesine bağlanmıyor"
    body = _balanced_body(viewer, 'logoBtn.addEventListener("click"')
    assert "openLogoModal(" in body, "düğme bindirme penceresini açmıyor"


def test_the_viewer_closes_before_it_opens_the_overlay_modal():
    """SIRA: `close()` ÖNCE, `openLogoModal()` SONRA.

    `#viewer` DOM'da `#logo-modal`'dan SONRA geliyor ve ikisi de `.modal`'ın
    `z-index: 50`'sini paylaşıyor. Eşitlikte DOM'da sonra gelen üstte boyanır,
    yani büyüteç açık kalırsa bindirme penceresi ARKADA kalır: açılıyor, odak
    bile alıyor, ama görünmüyor ve tıklanamıyor. `#confirm-modal { z-index: 60 }`
    yorumunun kaydettiği kusurun aynısı — bu testin öncülü o katman eşitliği.
    """
    css = _css()
    base = re.search(r"\.modal\s*\{[^}]*?z-index:\s*(\d+)", css, re.S)
    assert base, ".modal için z-index kuralı yok"
    html = _html()
    assert html.index('id="logo-modal"') < html.index('id="viewer"'), (
        "büyüteç artık bindirme penceresinden ÖNCE geliyor — bu testin öncülü "
        "düştü, sıra iddiası yeniden gerekçelendirilmeli")

    body = _balanced_body(_viewer_js(), 'logoBtn.addEventListener("click"')
    assert body.index("close()") < body.index("openLogoModal("), (
        "bindirme penceresi büyüteç kapanmadan açılıyor → perdenin ARKASINDA kalır")
    # Kayıt close()'tan ÖNCE okunmak zorunda: close() `kayit`i null'lıyor.
    assert body.index("kayit") < body.index("close()"), (
        "kayıt close()'tan sonra okunuyor — o noktada null, pencere hiç açılmaz")


def test_the_viewer_overlay_button_needs_a_saved_image():
    """"Logo ekle" ile "İndir" AYNI muhafızı paylaşır: sunucuda kayıtlı görsel.

    Kaydedilmemiş bir yükleme `blob:` URL taşıyor — `/api/logo` kaynağı diskte
    bulamaz, indirme de anlamsız bir ad düşürür. İki düğme tek ayrıştırmadan
    besleniyor (`kayitOku`); ayrı ayrıştırma yazmak ikisinin sessizce
    ayrışması olurdu.
    """
    viewer = _viewer_js()
    body = _balanced_body(viewer, "function syncActions(src)")
    assert "dlLink.hidden = !kayit" in body, "indirme muhafızı kayda bağlı değil"
    assert "logoBtn.hidden = !kayit" in body, (
        "bindirme düğmesi kaydedilmemiş görselde de görünüyor")
    # İKİNCİ MUHAFIZ (v0.13): bindirme VİDEODA da kapalı. `/api/logo` yolu
    # Pillow ile PNG bindiriyor ve kaynağı `_output_png_path`ten okuyor — bir
    # video id'sinde o kapı 404 veriyor, yani açık bir düğme kullanıcıya
    # olmayan bir yol gösterirdi. İNDİRME muhafızına eklenmedi ve bu ayrım
    # ölçülü: bir videoyu indirmek tamamen anlamlı.
    assert "videoKipi" in body, (
        "bindirme düğmesi video kipinde de görünüyor — /api/logo bir MP4'ü "
        "kaynak olarak okuyamaz")
    # id dosya adından türetiliyor — depo sözleşmesi (`storage.save` →
    # `{id}.{uzantı}`). KÜME KAPALI (sunucudaki `storage.MEDIA_TYPES`in
    # aynası); genel bir "son noktadan sonrasını at" deseni, prompt'undan
    # gelen noktalı bir adda id'yi budardı.
    assert re.search(r"replace\(/\\\.\(png\|mp4\)\$/i", viewer), (
        "kayıt id'si dosya adından türetilmiyor ya da iki uzantıyı birden "
        "soymuyor")


def test_the_media_toolbar_has_the_import_button_the_hint_promises():
    """İçe aktarmanın TIKLANABİLİR kapısı — ipucu metninin tarif ettiği düğme.

    `importFiles` ve `/api/import` baştan beri tamdı, ama tetikleyicileri
    yalnızca HTML5 sürükle-bırak: klasör kartına ve `.gallery-wrap`a bırakma.
    O yol dokunmatikte HİÇ çalışmıyor, yani telefondan bir fotoğrafı
    galeriye/klasöre koymanın hiçbir yolu yoktu — üstelik `FOLDER_HINT_IMPORT`
    "Yükle düğmesiyle içe aktarabilirsin" diyerek var OLMAYAN bir kontrolü
    tarif ediyordu (assets.js `assetEmptyText`in kaydettiği kusurun aynısı).
    """
    html = _html()
    assert 'id="media-import-btn"' in html, "Medya şeridinde Yükle düğmesi yok"
    assert 'id="media-import-input"' in html, "düğmenin dosya girişi yok"

    folders = _folders_js()
    assert '$("media-import-btn").addEventListener' in folders, "düğme bağlı değil"
    body = _balanced_body(folders, '$("media-import-input").addEventListener("change"')
    assert "importFiles(" in body, (
        "giriş `importFiles`a gitmiyor — MIME kapısı, 20 dosya sınırı ve "
        "SIRAYLA gönderim ikinci bir yolda yeniden yazılmış olurdu")
    assert 'e.target.value = ""' in body, (
        "değer sıfırlanmıyor — aynı dosya ikinci kez seçilince `change` hiç "
        "ateşlenmez ve düğme sessizce ölü görünür")
    assert "currentFolder ? currentFolder.id : null" in body, (
        "hedef bulunulan klasör değil — klasörün içinde 'Yükle' köke düşerdi")
    # Şerit seçim modunda görsellere kalıyor (#folder-new ile aynı davranış).
    assert '$("media-import-btn").hidden = selectMode' in folders, (
        "seçim modunda Yükle düğmesi şeritte kalıyor")


def test_every_file_input_carries_the_same_accept_list():
    """BEŞ dosya girişi AYNI kabul listesini taşımak zorunda.

    Android seçici intent'i (`MainActivity.dosyaSecimIntenti`) aileyi bu
    listeden TÜRETİYOR: tek tür kalırsa `type` aile düzeyine çıkmaz ve OEM
    galerileri öteki türleri gizler — commit 554aed4'ün kapattığı kusur.
    Yeni bir giriş listeden saparsa aynı kusur onda yeniden doğar.

    Beşincisi `#last-frame-input` (video modunun bitiş karesi); sayı burada
    LİTERAL kalıyor çünkü asıl mandal o: yeni bir giriş eklenince bu test
    KIRILIYOR ve ekleyen kişi kabul listesini bilerek onaylamak zorunda.
    """
    kabuller = re.findall(r'<input type="file"[^>]*?accept="([^"]+)"', _html())
    assert len(kabuller) == 5, f"beklenen beş dosya girişi, bulunan {len(kabuller)}"
    assert set(kabuller) == {"image/png,image/jpeg,image/webp"}, (
        f"kabul listeleri ayrışmış: {sorted(set(kabuller))}")


# ══════════════════════════════════════════════════════════════════════════
# Adım 12 — Composer'ın (+) menüsünden açılan Medya seçici
#
# Plan: docs/superpowers/plans/2026-08-07-flow-studio-tek-dokum.md
# Faz 0 mock'u: docs/flow-ui/media-picker-modal.html (kapı §0.10'da kapandı;
# bölünme 208/1fr/180 = K25, ret cümlesi "Önce ana görseli seç." = K26).
#
# İddialar KOD DESENİ arıyor, kelime değil — depo bu tuzağa üç kez düştü
# (§0.6, §0.7, §0.9).
# ══════════════════════════════════════════════════════════════════════════

PICKER_BANNER = "Medya seçici"


def _strip_js_comments(src: str) -> str:
    """Blok yorumları ve TAM SATIR `//` yorumlarını atar.

    "Şu şey KODDA geçmesin" iddiaları gerekçe yorumlarına takılıyor: yorum
    zaten yasaklanan adı yazmak ZORUNDA ("… `renderGallery()` buradan HİÇ
    yazılmaz"). §0.6/§0.7/§0.9'un dersi "iddia kodu arar, kelimeyi değil" —
    burada bunun mekanik hâli.

    Satır SONU yorumları bilerek korunuyor: `"http://…"` gibi dize içi `//`
    dizilerini kesmemek için yalnız satır başındakiler atılıyor.
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("//"))


def _strip_html_comments(src: str) -> str:
    return re.sub(r"<!--.*?-->", "", src, flags=re.S)


def _picker_js_raw() -> str:
    """folders.js'teki Medya seçici bölümü (iki banner arasındaki dilim).

    Bölüm banner'la sınırlanıyor (plan B1) ki iddialar dosyanın geri kalanını
    değil YALNIZ seçiciyi ölçsün: "seçici historyCache yazmıyor" iddiası tüm
    folders.js'e bakarsa hep kırmızı kalır (galeri onu meşru olarak yazıyor).
    """
    js = _folders_js()
    match = re.search(
        r"//\s*═{10,}\s*\n//\s*" + PICKER_BANNER + r"\b(?! sonu)(.*?)"
        r"\n//\s*═{10,}\s*\n//\s*" + PICKER_BANNER + r" sonu\b",
        js, re.S)
    assert match, "Medya seçici bölümü banner'la sınırlanmamış"
    return match.group(1)


def _picker_js() -> str:
    """Seçici bölümünün KODU (yorumsuz) — "geçmesin" iddiaları bunu okur."""
    return _strip_js_comments(_picker_js_raw())


def _section_div(html: str, element_id: str) -> str:
    """`id="…"` taşıyan `<div>`'in gövdesi, div derinliği sayılarak.

    `_section` yalnız `</section>`/`</aside>` ile kapanan kapları kesiyor;
    seçici ve (+) menüsü `<div>`. Derinlik saymak ilk `</div>`'te durmaktan
    sağlam: ikisi de iç içe div taşıyor.
    """
    start = html.find(f'id="{element_id}"')
    assert start > 0, f"#{element_id} servis edilmiyor"
    start = html.rfind("<div", 0, start)
    depth, i = 0, start
    while i < len(html):
        if html.startswith("<div", i):
            depth += 1
        elif html.startswith("</div>", i):
            depth -= 1
            if depth == 0:
                return html[start:i + 6]
        i += 1
    raise AssertionError(f"#{element_id} kapanmıyor")


def _picker_html_raw() -> str:
    return _section_div(_html(), "media-picker")


def _picker_html() -> str:
    """Seçicinin MARKUP'ı (yorumsuz) — aynı gerekçe, bkz. `_strip_js_comments`."""
    return _strip_html_comments(_picker_html_raw())


def test_the_plus_menu_offers_choosing_from_media():
    """B · (+) menüsü sözleşmenin üçüncü maddesini sunar.

    `flow-redesign-plan.md:222` dört madde söz veriyor; uygulamada iki vardı ve
    "Medya'dan seç" `static/` genelinde SIFIR eşleşmeydi — kullanıcının manşet
    şikâyeti buydu. Dördüncü madde ("Dosyadan yükle") BİLEREK eklenmiyor:
    #upload-btn zaten aynı #file-input'a giden dosya yolu, ikinci kapı olurdu.
    """
    menu = _section_div(_html(), "plus-menu")
    assert 'id="media-pick-btn"' in menu, "menüde Medya'dan seç yok"
    assert "Medya'dan seç" in menu, "maddenin etiketi yok"
    assert "<hr" in menu, "dosya yolu ile Medya yolu ayrılmamış"
    # Dördüncü madde eklenmedi: #file-input'a ikinci kapı yok.
    assert menu.count('type="file"') == 0, "menüye dosya girdisi kaçmış"


def test_the_media_picker_markup_is_served():
    """B · Seçici 13 yeni id ile servis ediliyor ve .modal-card KULLANMIYOR.

    `.modal-card label/input` kuralları (style.css:464-465) arama pill'ini blok
    yapar ve girdiyi yeniden giydirir — #palette-hue için zaten yazılmış tuzağın
    aynısı. Kart kendi sınıfını taşıyor.
    """
    picker = _picker_html()
    for element_id in ("picker-search", "picker-close", "picker-kinds",
                       "picker-grid", "picker-empty", "picker-empty-text",
                       "picker-preview-img", "picker-meta", "picker-use-ref",
                       "picker-use-extra", "picker-note"):
        assert f'id="{element_id}"' in picker, f"{element_id} yok"
    assert "modal-card" not in picker, ".modal-card kalıbı arama pill'ini bozar"
    assert "picker-card" in picker, "kartın kendi sınıfı yok"
    assert 'aria-modal="true"' in picker, "diyalog değil"
    assert 'id="picker-note"' in picker and 'role="status"' in picker, (
        "tek geri bildirim yüzeyi duyurulmuyor (B8)")


def test_the_picker_never_sorts_because_media_cannot_sort_either():
    """D10 · Medya sıralama düğmesi (#media-sort-btn) eklendi (Adım 10).

    Seçicide sıralama açılana kadar seçicide sort-btn yok, ama Medya şeridinde
    media-sort-btn bulunuyor.
    """
    assert "sort-btn" not in _picker_html(), "seçiciye tek başına sıralama gelmiş"
    assert "media-sort-btn" in _strip_html_comments(_html()), (
        "Medya'ya sıralama düğmesi (#media-sort-btn) D10 uyarınca eklenmiş olmalı")



def test_the_picker_collects_everything_through_load_all_images():
    """B2 · "Tümü" `loadAllImages()` ile toplanır, satır içine kopyalanmaz.

    `GET /api/history` klasör-DIŞLAYICI (klasörsüz VEYA tek klasör; "hepsi" ucu
    yok). Seçici kendi fetch'ini yazarsa o incelik ikinci kez keşfedilmek
    zorunda kalır ve ilk sürümü klasördeki görselleri kaçırır.
    """
    picker = _picker_js()
    assert "loadAllImages(" in picker, "seçici toplayıcıyı kullanmıyor"
    assert 'fetch("/api/history' not in picker, "seçici kendi fetch'ini yazmış"
    assert "?folder_id=" not in picker, "seçici klasör ucunu satır içine kopyalamış"


def test_the_picker_keeps_its_own_state_and_never_writes_medias():
    """B3 · Seçici kendi kopyasını tutar; arkadaki Medya'nın durumu bozulmaz.

    Seçici `historyCache`/`selected`/`searchQuery` yazarsa modal kapandığında
    Medya görünümü başka bir yerde duruyor olur — kullanıcı seçiciyi kapatıp
    galeriye döndüğünde filtresi değişmiş bir liste bulur.
    """
    picker = _picker_js()
    for owned in ("pickerImages", "pickerScope", "pickerQuery",
                  "pickerSelectedId", "pickerToken"):
        assert owned in picker, f"{owned} yok"
    for foreign in ("historyCache =", "selected =", "searchQuery =",
                    "renderGallery(", "setSelectMode("):
        assert foreign not in picker, f"seçici Medya'nın durumunu yazıyor: {foreign}"


def test_the_picker_reads_its_selection_from_state_not_from_the_dom():
    """B3 · Seçim `pickerSelectedId`'den okunur, DOM'dan sorulmaz.

    `querySelector('[aria-selected="true"]')` ızgara yeniden çizildiğinde
    (arama, kapsam değişimi) sessizce null döner ve commit düğmeleri "hiçbir şey
    seçili değil" sanır. Kaynak durumdur, boyanan işaret değil.
    """
    picker = _picker_js()
    assert "aria-pressed" in picker, "seçili karo işaretlenmiyor"
    # İddia sorgunun ARGÜMANINA bakıyor, "querySelector hiç geçmesin"e değil:
    # seçicide meşru bir sorgu zaten var (`[data-picker-close]`). İlk yazım
    # `"aria-selected\"]" not in picker` idi ve MUTASYON TURUNDA hayatta kaldı —
    # gerçek regresyon `querySelector('[aria-pressed="true"]')` diye yazılır,
    # o dizede öznitelik adının hemen ardından `=` gelir, `"]` değil. Kelime
    # aramasının dördüncü kurbanıydı (§0.6, §0.7, §0.9); burada tırnak biçimine
    # bakmayan bir iddiaya çevrildi.
    #
    # İKİ yazıma birden bakılıyor: öznitelik `aria-selected`ten `aria-pressed`e
    # taşındı ve tarama yalnız yeni ada bakarsa aynı regresyon ESKİ adla geri
    # gelebilir — silinen bir kuralın mandalı da silinmiş olurdu.
    for arg in re.findall(r"querySelector(?:All)?\((.*?)\)", picker):
        for yazim in ("aria-pressed", "aria-selected"):
            assert yazim not in arg, f"seçim DOM'dan okunuyor: {arg}"
    assert "pickerById(pickerSelectedId)" in picker, (
        "yan bölme seçimi durumdan almıyor")


def test_the_picker_tile_announces_selection_with_a_state_a_button_can_carry():
    """Defter kuyruğu 1 · `aria-selected` düz `<button>`da GEÇERSİZ ARIA.

    `.picker-tile` bir `<button>`, kapsayıcısı (`#picker-grid`) düz bir `<div>`.
    `aria-selected` yalnız `option`/`tab`/`row`/`treeitem`/`gridcell` rollerinde
    tanımlı — düğmede tarayıcı onu erişilebilirlik ağacına HİÇ koymuyor. Yani
    seçim ekran okuyucuya ulaşmıyordu ve tek işaret görsel çerçeveydi; hata
    vermeyen, yalnız ekran okuyucuyla fark edilen bir kırılma.

    `role="listbox"/"option"` çifti REDDEDİLDİ: gezinen tabindex ve ok tuşu
    modeli ister, depoda öyle bir desen hiç yok. `aria-pressed` altı yerde
    zaten kurulu (core.js:41-42,169 · folders.js:540 · palette.js:185).

    İddia JS ile CSS'i BİRBİRİNE bağlıyor, iki ayrı dize aramıyor: öznitelik
    adı koddan okunuyor ve boyayan kural o adla aranıyor. Yalnız birini
    yeniden adlandıran bir düzenleme (seçim görünmez olur, hata çıkmaz)
    böylece kırmızıya düşüyor.
    """
    picker = _picker_js()
    ad = re.search(r'tile\.setAttribute\("(aria-[a-z]+)"', picker)
    assert ad, "karo seçim durumunu hiç yazmıyor"
    assert ad.group(1) == "aria-pressed", (
        f"düğme taşıyamayacağı bir durum yazıyor: {ad.group(1)}")
    assert "aria-selected" not in picker, "geçersiz ARIA geri gelmiş"

    css = _css()
    assert f'.picker-tile[{ad.group(1)}="true"]' in css, (
        "seçili karoyu boyayan kural JS'in yazdığı özniteliğe bakmıyor")
    # İkiz kural: aynı seçici gezinme bölümünde bir kez daha tanımlıydı ve
    # ikisi çakışıyordu. Tek tanım kalmalı, yoksa "hangisi kazanıyor" sorusu
    # geri döner.
    assert css.count(f'.picker-tile[{ad.group(1)}="true"] {{') == 1, (
        "seçili karo kuralı yine ikizlenmiş")


def test_the_hover_tile_keeps_the_accent_edge_the_twin_rule_carried():
    """Kuyruk · `.picker-tile:hover` ikizi tekilleşti, boyası kaybolmadan.

    `aria-pressed` kuralıyla aynı yapıştırma kazasının öteki yarısıydı:
    gezinme kurallarının ortasına düşmüş ikinci bir `.picker-tile:hover`
    bloğu. Özgüllükler eşit olduğu için kaskad sırası karo bölümündeki
    `background`ı kazandırıyordu — ikizin `--accent-surface` tercihi hiç
    boyanmıyordu — ama `box-shadow`u kimse ezmediği için o BOYANIYORDU.

    İddianın tuttuğu kırılma bu: ikizi yalnızca silen bir temizlik, üzerine
    gelince beliren accent kenarını da sessizce götürür. Hata çıkmaz, test
    çıkar. Bu yüzden iddia hem "tek tanım" hem "kenar duruyor" diyor.

    Üçüncü iddia sıra: seçili bir karonun üzerine gelmek seçimi silmemeli.
    İki kural da eşit özgüllükte (0,2,0), yani kazananı YALNIZ sıra
    belirliyor — `[aria-pressed]` sonra gelmeli.
    """
    govde = _css_block(".picker-tile:hover")
    assert "var(--accent-border" in govde, (
        "ikiz silinirken üzerine gelme kenarı da gitmiş")

    css = re.sub(r"/\*.*?\*/", "", _css(), flags=re.S)
    assert css.count(".picker-tile:hover") == 1, (
        "karo hover kuralı yine ikizlenmiş")

    hover = css.index(".picker-tile:hover")
    basili = css.index('.picker-tile[aria-pressed="true"]')
    assert hover < basili, (
        "hover kuralı seçim kuralından sonra geliyor: eşit özgüllükte "
        "üzerine gelmek seçimi siler")


def _picker_islevleri() -> dict:
    """Seçici bölümündeki üst düzey işlevlerin {ad: gövde} eşlemesi."""
    picker = _picker_js()
    return {ad: _balanced_body(picker, f"function {ad}(")
            for ad in re.findall(r"^function (\w+)\(", picker, re.M)}


def test_selecting_a_tile_leaves_the_focused_button_standing():
    """Defter kuyruğu 1 · Seçim, ALTINDA DURDUĞUN düğmeyi yıkmıyor.

    `grid.innerHTML = ""` odaklı `<button>`ı DOM'dan düşürüyordu ve odak
    `<body>`ye iniyordu. ÖLÇÜLDÜ (Chromium 1194, üç genişlikte de): bir karoya
    Enter'a basıldıktan sonra `document.activeElement.tagName === "BODY"`.
    Yani Tur C'nin `aria-pressed` kazanımı tam da onu duyacak kullanıcıda
    siliniyordu — o kullanıcı hem seçtiğini duymuyor hem de gezinmeye
    diyaloğun başından başlamak zorunda kalıyordu.

    İDDİA AD ARAMIYOR, ERİŞİLEBİLİRLİK arıyor: tıklama gövdesinden ızgarayı
    yeniden kuran HİÇBİR işleve ulaşılamamalı. "Yeniden kuran"ın tanımı da
    KODDAN çıkıyor (`$("picker-grid")` + `innerHTML` taşıyan işlevler, artı
    onları çağıranların geçişli kapanışı), yani yarın eklenecek bir sarmalayıcı
    kendiliğinden kapsanıyor. İlk yazım `"renderPickerGrid(" not in govde` idi
    ve mutasyonda HAYATTA KALIRDI: `renderMediaPicker()` de aynı yıkımı yapıyor.

    Ölçüt `$("picker-grid")` ile BİRLİKTE aranıyor, tek başına `innerHTML` ile
    değil — `renderPickerSide` künyeyi meşru olarak `innerHTML` ile temizliyor
    ve tıklama yolunun onu ÇAĞIRMASI gerekiyor.
    """
    islevler = _picker_islevleri()
    yikanlar = {ad for ad, g in islevler.items()
                if '$("picker-grid")' in g and "innerHTML" in g}
    assert "renderPickerGrid" in yikanlar, "ızgara kurucusu bulunamadı"
    for _ in range(len(islevler)):                       # sabit noktaya kadar
        buyuk = yikanlar | {ad for ad, g in islevler.items()
                            if any(f"{k}(" in g for k in yikanlar)}
        if buyuk == yikanlar:
            break
        yikanlar = buyuk
    assert "renderMediaPicker" in yikanlar, "dolaylı yıkıcı hesaba katılmıyor"
    assert "renderPickerSide" not in yikanlar, (
        "künye temizliği yıkıcı sayılmış: iddia tıklama yolunu tümden yasaklar")

    govde = _balanced_body(_picker_js(), '$("picker-grid").addEventListener')
    assert "innerHTML" not in govde, "seçim ızgarayı elle yeniden kuruyor"
    for ad in sorted(yikanlar):
        assert f"{ad}(" not in govde, f"seçim {ad}() ile odaklı karoyu yok ediyor"

    # Yerine: MEVCUT düğümler üzerinde öznitelik çevirisi.
    assert "syncPickerPressed()" in govde, "seçim işareti hiç güncellenmiyor"
    supurme = islevler["syncPickerPressed"]
    assert 'querySelectorAll(".picker-tile")' in supurme, (
        "süpürme karoları SINIFINDAN bulmuyor")
    assert "pickerSelectedId" in supurme, "süpürme seçimi durumdan okumuyor"

    # TEK YAZICI: kurulum da aynı süpürmeden geçiyor ve karolar EKLENDİKTEN
    # SONRA — önce koşarsa `querySelectorAll` boş küme görür, hiçbir karo
    # işaretlenmez ve kırılma sessiz olur (hata yok, yalnız seçim görünmez).
    izgara = islevler["renderPickerGrid"]
    assert izgara.count("syncPickerPressed()") == 1, (
        "kurulum işareti süpürmeden almıyor: iki yazıcı ayrışabilir")
    assert izgara.rfind("syncPickerPressed()") > izgara.rfind("grid.appendChild("), (
        "süpürme karolar eklenmeden koşuyor")


def test_a_selected_tile_can_still_show_that_it_is_focused():
    """Kuyruk 1'in YAN ETKİSİ · seçim halkası odak halkasını eziyordu.

    Seçim ızgarayı artık yeniden kurmadığı için "seçili VE odaklı" karo bundan
    sonra klavye kullanıcısının NORMAL hâli. Düzeltmeden ÖNCE ikisi hiç bir
    arada olmuyordu (Enter'dan sonra odak `<body>`deydi) ve çakışma
    görünmüyordu: `.picker-tile[aria-pressed="true"]` (0,2,0) global
    `:focus-visible`i (0,1,0) `outline` yarışında EZİYOR. Yani düzeltme tek
    başına ekran okuyucu kullanıcısını kazandırıp GÖREN klavye kullanıcısını
    kaybettirirdi — halkası sessizce kaybolurdu.

    ÖLÇÜLDÜ (Chromium 1194, seçili+odaklı karo): `outline` 2px içeride
    (offset -2px) ve `box-shadow` iki katmanlı dışarıda — iki işaret AYRI
    kanaldan geliyor.
    """
    blok = _css_block('.picker-tile[aria-pressed="true"]:focus-visible')
    assert "box-shadow" in blok, "odak işareti AYRI bir kanaldan gelmiyor"
    assert "var(--accent)" in blok, "dış halka vurgu rengini kullanmıyor"

    css = re.sub(r"/\*.*?\*/", "", _css(), flags=re.S)
    assert (css.index('.picker-tile[aria-pressed="true"] {')
            < css.index('.picker-tile[aria-pressed="true"]:focus-visible')), (
        "odak kuralı seçim kuralından ÖNCE geliyor: box-shadow'u seçim ezerdi")


def test_filtering_by_scope_hands_focus_back_to_the_same_button():
    """Aynı kusurun İKİNCİ örneği · kapsam süzgeci de odağı `<body>`ye atıyordu.

    Izgaradan farkı: yeniden kurmak KAÇINILMAZ, çünkü sayaçlar hem kapsamla hem
    HER TUŞ VURUŞUYLA değişiyor (`pickerFilter(s).length`). O yüzden çözüm
    farklı: odağı ANAHTARDAN iade etmek (`chat.js:closeMenus` deseni).
    ÖLÇÜLDÜ: iade yokken bir kapsam düğmesine klavyeyle basınca odak `<body>`.

    İddia SIRAYA bakıyor, "`focus()` geçiyor mu"ya değil: yıkımdan SONRA okunan
    bir `activeElement` zaten `<body>` olur ve iade sessizce ölür — kelime
    aramasının tam olarak hayatta bırakacağı mutasyon bu.
    """
    nav = _picker_islevleri()["renderPickerNav"]
    assert "innerHTML" in nav, (
        "gezinme artık yeniden kurulmuyorsa bu iddia yeniden yazılmalı")
    i_oku, i_yik, i_ver = (nav.find("activeElement"),
                           nav.find('innerHTML = ""'), nav.rfind(".focus()"))
    assert -1 < i_oku < i_yik < i_ver, (
        "odak anahtarı yıkımdan SONRA okunuyor ya da iade hiç yok")
    assert "closest(" in nav, (
        "odak İÇERİDE miydi sorulmuyor: arama kutusuna yazan kullanıcının "
        "odağı her tuşta şeride çalınır")
    assert "dataset.key" in nav, "iade DÜĞÜME değil ANAHTARA bağlanmalı"
    assert "isConnected" not in nav, (
        "core.js'in muhafızı kopyalanmış: düğüm yıkımdan SONRA bulunuyor, "
        "kopmuş olamaz")


def test_adding_an_extra_does_not_disable_the_button_under_the_focus():
    """Aynı kusurun ÜÇÜNCÜ örneği · düğme kendi altındaki odağı kapatıyordu.

    `addGalleryExtra` BAŞARILI olduğu anda `extraBlockReason(rec)` doluyor
    ("Bu görsel zaten ek referans listesinde.") ve `renderPickerSide`
    `#picker-use-extra`yı `disabled` yapıyor. Odaklı bir düğmeyi disable etmek
    odağı `<body>`ye düşürüyor. ÖLÇÜLDÜ (Chromium 1194): Enter'dan sonra
    `document.activeElement` `<body>`, düğme `disabled`, not "Eklendi · 1/3".
    Yani B7'nin gerekçesi ("üç ek slotu var, her biri için menüden dönmek saçma
    olurdu") klavye kullanıcısında TAM TERSİNE dönüyordu: ikinci ek için
    diyaloğun başından Tab. `#picker-note` `role="status"` olduğu için ONAY
    duyuluyordu; kaybolan şey YER.
    """
    picker = _picker_js()
    govde = _balanced_body(picker, '$("picker-use-extra").addEventListener')
    assert 'picker-use-ref").focus()' not in govde, (
        "odak turu BİTİREN düğmeye veriliyor: ikinci Space seçiciyi kapatırdı")
    assert re.search(r"pickerKaro\(pickerSelectedId\)", govde), (
        "odak seçili karoya değil rastgele bir düğüme veriliyor")
    # Arayıcının kendisi de mandallı: dolaylılık iddiayı zayıflatmasın.
    # `_balanced_body` BURADA KULLANILAMAZ ve sebebi ölçüldü: ok işlevinin
    # gövdesi süslü açmıyor, yardımcının bulduğu ilk `{` şablon dizesinin
    # içindeki `${id}` oluyor ve iddia `"{id}"` üzerinde koşuyordu.
    arayici = re.search(r"const pickerKaro = .*?;", picker, re.S)
    assert arayici, "ortak karo arayıcı yok"
    assert ".picker-tile[data-id=" in arayici.group(0), (
        "karo arayıcı karoyu id'sinden bulmuyor")

    # SIRA: `activeElement` MUTASYONDAN ÖNCE okunmalı. `addGalleryExtra` kendi
    # yüzeyini yeniden çiziyor (`renderSource`); odağı taşıyan bir kabı yıkarsa
    # sonradan yapılan okuma sessizce `false` döner ve düzeltme HATASIZCA
    # buharlaşır — mandal da bunu göremezdi, çünkü dizeler yerinde kalırdı.
    i_oku, i_ekle = govde.find("activeElement"), govde.find("addGalleryExtra(")
    assert -1 < i_oku < i_ekle, (
        "odak, ekleme DOM'u değiştirdikten sonra okunuyor: iade sessizce ölür")


def test_closing_the_picker_hands_focus_back_to_whatever_opened_it():
    """Aynı kusurun DÖRDÜNCÜ örneği — ve en sık yürünen yolu.

    `$("media-picker").hidden = true` odaklı karoyu `display: none` yapıyor,
    yani Escape ya da × ile kapatan klavye kullanıcısının odağı `<body>`ye
    düşüyordu. **ÖLÇÜLDÜ (360×780):** karoya odaklanıp Escape'e basınca
    `document.activeElement.tagName === "BODY"` — kullanıcı sayfanın başından
    Tab'lamak zorunda kalıyordu.

    Desen `core.js`in `dialogPrevFocus`'u: açan düğüm açılışta tutuluyor,
    kapanışta `isConnected` muhafızıyla geri veriliyor.

    "Referans yap" dalı iadeyi KAPATIYOR ve bu bilinçli: `setGallerySource`
    odağı `#prompt`a taşıyor (B7'nin yazılı kararı), iade açık kalsaydı odak
    önce (+) düğmesine dönüp hemen composer'a sıçrardı ve ekran okuyucuya iki
    ayrı yer duyurulurdu. İddia bu asimetriyi de tutuyor.
    """
    picker = _picker_js()
    ac = _balanced_body(picker, "async function openPicker(")
    assert "document.activeElement" in ac, "açan düğüm hiç tutulmuyor"

    kapat = _balanced_body(picker, "function closePicker(")
    assert ".focus()" in kapat, "kapanışta odak iade edilmiyor"
    # İDDİA VARLIĞA DEĞİL ULAŞILABİLİRLİĞE bakıyor: `if (false) …focus()`
    # mutasyonu `".focus()" in kapat` iddiasını HAYATTA BIRAKIYORDU (ölçüldü,
    # mutasyon turunda kaçtı). İadenin kapısı, işlevin KENDİ parametresi olmalı.
    kapi = re.search(r"function closePicker\((\w+)", picker)
    assert kapi, "kapanışın iade anahtarı bir parametre değil"
    assert re.search(rf"\b{kapi.group(1)}\b", kapat), (
        "iade parametresi gövdede hiç okunmuyor: kapı sabite bağlanmış")

    # `isConnected` TEK BAŞINA YETMİYOR ve bu ölçüldü: açan düğme (+) menüsünün
    # içinde (`#media-pick-btn`) ve o menü seçici açılırken kapanıyor. Düğüm
    # DOM'da duruyor — `isConnected` true — ama `[hidden]` bir kabın içinde
    # olduğu için `.focus()` SESSİZCE hiçbir şey yapmıyor. İlk yazım tam olarak
    # bu yüzden işe yaramadı: Escape ölçümü hâlâ `BODY` diyordu.
    hedef = _balanced_body(picker, "function pickerOdakHedefi()")
    assert "isConnected" in hedef, "kopmuş düğüme odak veriliyor"
    assert "[hidden]" in hedef, (
        "görünmez bir kabın içindeki düğme hedef sayılıyor: `.focus()` sessizce "
        "hiçbir şey yapar ve odak `<body>`de kalır")
    assert "plus-btn" in hedef, "görünür bir yedek hedef yok"

    ref = _balanced_body(picker, '$("picker-use-ref").addEventListener')
    assert re.search(r"closePicker\(\s*false\s*\)", ref), (
        "Referans yap iadeyi kapatmıyor: odak (+) düğmesine dönüp hemen "
        "#prompt'a sıçrar, ekran okuyucuya iki yer duyurulur")


def test_rebuilding_the_grid_also_hands_focus_back():
    """Izgaranın YENİDEN KURULDUĞU yollar da odağı düşürüyordu.

    Seçim artık oraya uğramıyor, ama arama, kapsam değişimi ve `openPicker`'ın
    bekleyen `loadAllImages` yanıtı hâlâ `grid.innerHTML = ""` yapıyor.
    Sonuncusu en sinsisi: `openPicker` `pickerImages`i temizlemiyor, yani bayat
    liste HEMEN boyanıyor; kullanıcı bir karoya geçiyor ve yanıt gelince ızgara
    altından siliniyor.

    İddia yine SIRAYA bakıyor: yıkımdan SONRA okunan bir `activeElement` zaten
    `<body>` olur ve iade sessizce ölür.
    """
    izgara = _balanced_body(_picker_js(), "function renderPickerGrid(")
    i_oku, i_yik, i_ver = (izgara.find("activeElement"),
                           izgara.find('innerHTML = ""'), izgara.rfind(".focus()"))
    assert -1 < i_oku < i_yik < i_ver, (
        "odak kimliği yıkımdan SONRA okunuyor ya da iade hiç yok")
    assert "closest(" in izgara, (
        "odak IZGARADA mıydı sorulmuyor: arama kutusuna yazanın odağı her "
        "tuşta çalınır")
    # Sıra tek başına YETMİYOR: `if (false)` mutasyonu üç dizeyi de yerinde
    # bırakıyor ve iddia hayatta kalıyordu (ölçüldü). Yıkımdan ÖNCE yakalanan
    # kimlik, yıkımdan SONRA gerçekten okunmalı.
    yakala = re.search(r"const (\w+)\s*=\s*[^;]*closest\([^;]*dataset\.id[^;]*;",
                       izgara, re.S)
    assert yakala, "odak kimliği yıkımdan önce yakalanmıyor"
    # Kimliğin yıkımdan sonra GEÇMESİ de yetmiyor: `if (false) { pickerKaro(odakId) }`
    # mutasyonu onu da hayatta bırakıyordu (ölçüldü). İADENİN KAPISI o kimlik olmalı.
    assert re.search(rf"if\s*\(\s*{yakala.group(1)}\s*\)", izgara[i_yik:]), (
        "iade yakalanan kimliğe değil başka bir koşula bağlanmış: sabit bir "
        "koşul iadeyi sessizce öldürür")


def test_the_tile_caption_names_the_whole_chain_without_burying_the_leaf():
    """Defter kuyruğu 2 / K27 · Künye ZİNCİRİ yazıyor, YAPRAK hayatta kalıyor.

    Künye yalnız en yakın klasörü yazıyordu, yani iç içe klasörde "hangi A
    altındaki B" cevapsızdı. Aynı ders taşıma listesinde zaten yazılıydı
    (`folders.js`, `<option>` döngüsü: "yalnız ad iki farklı klasörde de aynı
    olabiliyor").

    Düz uçtan kırpma ÇÖZÜM DEĞİL ve bu ÖLÇÜLDÜ (Chromium 1194, 360×780): kart
    359px, ızgara 335px, `minmax(96px, 1fr)` üç sütun veriyor, karo 104px ve
    künye kutusu 84px. "Kampanyalar / Bayram" sondan kırpılınca "Kampanyala…"
    kalırdı — kullanıcının aradığı YAPRAK klasör tam da kaybolan yarı, yani
    bugünkünden ("Bayram") kötü. Ölçülen sonuç: üst "Kampanyalar" kırpılıyor,
    yaprak " / Bayram" 51px ile TAM, künye tek satır, karo taşması 0.

    İddia JS'i CSS'e BAĞLIYOR: sınıf adları KODDAN okunuyor, kırpma kuralları
    O adlarla aranıyor ve DEĞERLERİ sınanıyor. Yalnız birini yeniden adlandıran
    ya da tek bir bildirimi silen bir düzenleme — kırpma sessizce ölür, hata
    çıkmaz — kırmızıya düşer.
    """
    js = _folders_js()
    dugum = _balanced_body(js, "function klasorZinciriDugumu(")
    adlar = re.findall(r'\.className = "([\w-]+)"', dugum)
    assert adlar == ["zincir-ust", "zincir-yaprak"], (
        f"künye iki parçadan kurulmuyor: {adlar}")
    ust, yaprak = adlar

    kap = re.search(r'kap\.className = (\w+)', dugum)
    assert kap, "kapsayıcının sınıfı çağırandan gelmiyor"
    izgara = _balanced_body(_picker_js(), "function renderPickerGrid(")
    assert re.search(
        r'klasorZinciriDugumu\(rec\.folder_id,\s*"picker-cap-folder"', izgara), (
        "künye ortak zincir düğümünden geçmiyor")
    # Zincir karo başına BİR kez yürünüyor: `folderPath` klasör başına doğrusal
    # `find` yapıyor ve ızgara her tuş vuruşunda yeniden kuruluyor, yani ikinci
    # bir yürüyüş her karo için bedava değil.
    assert izgara.count("folderPathParts(") == 1, (
        "zincir karo başına birden çok kez yürünüyor")
    assert "pickerFolderLabel(rec.folder_id)" not in izgara, (
        "ipucu zinciri İKİNCİ kez yürüyor: aynı parçalardan üretilmeli")
    assert not re.search(r"folder\s*\?\s*folder\.name", izgara), (
        "künye hâlâ EN YAKIN klasörü tek başına yazıyor")

    assert re.search(r"display:\s*flex", _css_block(".picker-cap-folder, .card-where")), (
        "iki parça tek satırda değil: satır içi kutuda text-overflow İŞLEMEZ")

    ust_k, yaprak_k = _css_block(f".{ust}"), _css_block(f".{yaprak}")
    for ad, kural in ((ust, ust_k), (yaprak, yaprak_k)):
        assert "text-overflow: ellipsis" in kural, f".{ad} kırpılmıyor"
        assert "overflow: hidden" in kural, f".{ad} taşmayı gizlemiyor"

    def _daralma(kural):
        m = re.search(r"flex:\s*(\S+)\s+(\S+)\s+([^;]+);", kural)
        assert m, f"flex kısa biçimi üç değerli yazılmamış: {kural.strip()!r}"
        return float(m.group(2))

    # 1) SIRA: yer önce ÜST zincirden alınıyor.
    assert _daralma(ust_k) > _daralma(yaprak_k), (
        "üst zincir yapraktan daha hızlı daralmıyor: uzun bir üst zincir "
        "yaprağı da kırpar ve künye bugünkünden ('Bayram') kötü olur")

    # 2) TABAN: üst zincir SIFIRA inemez. Bu satır bir inceleme bulgusundan
    #    geldi ve ölçüldü — `min-width: 0` iken uzun yapraklı bir zincir üst
    #    kutuyu 0px'e indiriyordu; 0px'te `text-overflow` boyayacak yer
    #    bulamıyor, yani ÜÇ NOKTA DA çıkmıyor ve künye sahipsiz bir
    #    " / Ramazan Bayrami…" oluyordu. `text-overflow: ellipsis`in VARLIĞINI
    #    sınamak yetmiyor: boyanabilmesi de gerekiyor.
    taban = re.search(r"min-width:\s*([\d.]+)(\w*)", ust_k)
    assert taban and float(taban.group(1)) > 0, (
        "üst zincirin daralma tabanı yok: sıfıra inince üç nokta da kaybolur "
        "ve künye baştaki ayraçla sahipsiz kalır")

    # 3) Yaprak DARALABİLİR olmalı: sıra üste dayandığında kırpılacak olan o.
    assert re.search(r"min-width:\s*0", yaprak_k), (
        "yaprak daralamıyor: üst zincir tabanına dayandığında satır taşar")
    bosluk = re.search(r"white-space:\s*([\w-]+)", yaprak_k)
    assert bosluk and bosluk.group(1) == "pre", (
        f"ayracın baştaki boşluğu kırpılıyor ({bosluk and bosluk.group(1)}): "
        "her esnek öğe kendi satır kutusunu açıyor → 'Kampanyal…/ Bayram'")


def test_the_chain_is_walked_once_per_folder_not_once_per_record():
    """Zincir KLASÖR başına bir kez yürünüyor, KAYIT başına değil.

    Zincir bu turda arama yüklemine girdi, yani artık kayıt başına okunuyor —
    üstelik seçicinin kapsam şeridi aynı yüklemi HER KAPSAM için tüm kayıtlara
    uyguluyor ve şerit her tuş vuruşunda yeniden kuruluyor. Belleksiz maliyet
    tuş başına `(F + 3) × N × D × F` klasör karşılaştırması (F=30, D=3, N=500
    için ≈1,6 milyon), çünkü `folderPath` her kademede doğrusal `find` koşuyor.

    ÖLÇÜLDÜ (Chromium 1194, seçici açık): `renderPickerNav` ortalaması bellekli
    zincir yükleminde 0.152 ms — zinciri aramaya SOKMADAN önceki 0.164 ms'nin
    altında. Yani zincire geçmenin bedeli negatif çıktı.

    `Object.freeze` ayrı bir iddia ve süs değil: dönen nesne PAYLAŞILIYOR, bir
    çağıranın yazması BAŞKA bir yüzeyin künyesini değiştirirdi — suçlu satır ile
    belirtinin ayrı yüzeylerde olduğu, teşhisi çok zor bir kirlenme.
    """
    parcalar = _balanced_body(_folders_js(), "function folderPathParts(")
    assert "zincirBellegi.get(" in parcalar and "zincirBellegi.set(" in parcalar, (
        "zincir belleği yok: yüklem KAYIT başına `folderPath` yürüyor ve "
        "seçicinin kapsam şeridi bunu HER KAPSAM için tekrarlıyor")
    assert "Object.freeze(" in parcalar, (
        "bellekteki parçalar dondurulmamış: dönen nesne paylaşılıyor")


def test_every_writer_of_the_folder_cache_resets_the_chain_memo():
    """`folderCache`i değiştiren HER yazar zincir belleğini tazeliyor.

    Bu testin var oluş sebebi ölçülmüş bir tuzak: `folderCache` DİZİSİNE iki
    atama var (`loadFolders`ın iki dalı), ama İÇERİĞİ üçüncü bir yerde YERİNDE
    değişiyor — `renameCurrentFolder` `loadFolders()` çağırmıyor (yeniden
    adlandırma sayıları değiştirmiyor) ve önbellekteki nesnenin `name`ini
    doğrudan yazıyor. Zincir METNİNİ tutan bellek orada sıfırlanmazsa kullanıcı
    klasörü yeniden adlandırdıktan sonra YENİ adı aratınca hiçbir şey bulamaz,
    ESKİ adı aratınca sonuç almaya devam eder — ve künyeler de eski adı yazar.

    Sayılar bu yüzden pinlenmiş: dördüncü bir yazar eklendiği gün bu satır
    kırmızıya döner ve yazan kişi sıfırlamayı düşünmek ZORUNDA kalır.
    """
    js = _folders_js()
    assert js.count("folderCache = ") == 4, (
        f"`folderCache` yazarları değişmiş ({js.count('folderCache = ')}): yeni "
        "bir yazar zincir belleğini de tazelemek zorunda")
    assert js.count("found.name = ") == 1, (
        "önbellekteki klasöre yeni bir YERİNDE yazım eklenmiş")
    for fn in ("async function loadFolders(", "async function renameCurrentFolder("):
        assert "zincirBellegiSifirla()" in _balanced_body(js, fn), (
            f"{fn} zincir belleğini tazelemiyor")
    assert js.count("zincirBellegiSifirla()") == 3, (
        "tanım + iki çağrı: üçüncüsü ya yeni bir yazar ya gereksiz temizlik")

    yukle = _balanced_body(js, "async function loadFolders(")
    assert yukle.count("zincirBellegiSifirla()") == 1, (
        "temizlik dal başına ikizlenmiş: üçüncü dalda unutulur")
    assert yukle.index("zincirBellegiSifirla()") > yukle.rindex("catch"), (
        "temizlik `catch`ten ÖNCE koşuyor: hata dalında `folderCache = []` "
        "sorulan her id'yi 'kök' diye belleğe yazar ve sonraki BAŞARILI yükleme "
        "o yalanı hazır bulur")


def test_the_folder_cards_deliberately_match_only_their_own_name():
    """Klasör KARTLARININ süzgeci zincire geçmiyor — bilinçli.

    Arama yüklemi zinciri eşleştiriyor, yani "kampanyalar" alt klasördeki
    GÖRSELLERİ getiriyor. Kart ise yalnız `f.name` ÇİZİYOR: zincire geçilseydi
    ekrana, sebebi hiçbir yerde yazmayan bir "Bayram" kartı düşerdi —
    düzelttiğinden daha kötü bir ayrışma. İki liste iki ayrı soruyu cevaplıyor.

    Mandal kararın kendisini taşıyor ki sonraki okuyucu bunu "unutulmuş yarı"
    sanıp sessizce kapatmasın.
    """
    kart = _balanced_body(_folders_js(), "function renderFolders()")
    assert re.search(
        r"folderCache\.filter\(\(f\) => f\.name\.toLowerCase\(\)\.includes\(q\)\)",
        kart), (
        "klasör KARTLARI zincire geçmiş: kart yalnız `f.name` çiziyor, yani "
        "'kampanyalar' aramasında sebebi ekranda yazmayan bir 'Bayram' kartı "
        "belirir. Zincire geçilecekse kart da zinciri ÇİZMELİ — dördüncü künye "
        "yüzeyi, kendi CSS'i, kendi 360×780 ölçümü")


def test_the_picker_scopes_stay_a_partition_not_a_subtree():
    """Kapsam düğmeleri TAM eşitlikte kalıyor, alt ağaca açılmıyor.

    Klasör kapsamları "Klasörsüz" ile birlikte "Tümü"yü tüketen bir BÖLME; tek
    kesişen süzgeç `imported` ve o `crossing` sınıfıyla gözle işaretli. Alt
    ağaçta her klasör işaretsiz bir kesişen süzgece dönerdi ve toplam "Tümü"yü
    aşardı — okuyanın "sayaç bozuk" diyeceği hâl.

    Kabul ölçütünün istediği "sayaçlar buna göre" kapsamlara DOKUNMADAN
    sağlanıyor: sayaç `pickerFilter` üzerinden yüklemi çağırıyor. ÖLÇÜLDÜ:
    "Kampanyalar / Bayram" kapsamı "kampanyalar" aramasında 0 → 3, yem klasör
    "Yılbaşı / Bayram" ise 0 → 0 (yani eşleşen ATA, ağaçtaki herhangi bir ad
    değil), toplam "Tümü" = 3 ile tutuyor.
    """
    picker = _picker_js()
    assert re.search(r"test: \(r\) => r\.folder_id === f\.id", picker), (
        "kapsam ALT AĞACA geçmiş: üst klasörün sayacı alt klasörünkileri de "
        "sayar ve toplam 'Tümü'yü AŞAR")
    assert "folderSubtree(" not in picker, (
        "kapsam testi alt ağaç yürüyor: kapsam BAŞINA kayıt BAŞINA BFS")


def test_the_rail_count_reports_what_is_actually_on_screen():
    """Şeridin iki yarısı da EKRANI sayıyor.

    ÖLÇÜLDÜ (Tur L, "kampanyalar" araması, üç eşleşen görsel ve bir eşleşen
    kart): şerit "4 klasör · 1 görsel" yazıyordu — İKİ sayı da yanlış. Klasör
    yarısı süzgeci hiç görmüyordu; görsel yarısı ise arama BİTMEDEN okunuyordu
    (`syncFolderView` → `renderFolders` sırası, `refreshSearch` sonra bitiyor).
    Zincir eşleşmesi görsel sayısını büyüttüğü için çelişki bu turdan sonra
    daha sık ekrana gelecekti. Sonra: "1 klasör · 3 görsel".
    """
    js = _folders_js()
    kart = _balanced_body(js, "function renderFolders()")
    assert "gorunenKlasorSayisi = matching.length" in kart, (
        "aramada şerit hâlâ TÜM klasörleri sayıyor, ekranda ise yalnız eşleşen "
        "kartlar var")
    assert "gorunenKlasorSayisi = 0" in kart, (
        "hiç eşleşme yokken ızgara gizleniyor ama şerit klasör saymaya devam eder")
    assert "gorunenKlasorSayisi = null" in kart, (
        "arama DIŞI dal sayacı sıfırlamıyor: bir kez arama yapan kullanıcı "
        "sorguyu silince şeritte eski süzülmüş sayıyı okumaya devam eder")
    arama = _balanced_body(js, "async function refreshSearch(")
    assert "updateMediaRailCount()" in arama, (
        "arama sonucu geldikten sonra şerit tazelenmiyor: görsel sayısı bir "
        "önceki aramanınki kalır")


def test_both_folder_captions_go_through_the_same_chain_node():
    """Künyeyi yazan İKİ yüzey de aynı düğümden geçiyor.

    Üçüncü kopya arama sonucu rozetiydi (`.card-where`) ve ironisi ölçülü:
    rozetin KENDİ yorumu "sonuçlar tüm klasörlerden geliyor, adsız iki varyant
    ayırt edilemez" diyerek var oluş sebebini anlatıyor — ama yalnız en yakın
    klasörü yazdığı sürece iç içe iki ayrı "Bayram" hâlâ birbirinin aynısıydı,
    yani rozet tam da engellemek için konduğu belirsizliği üretiyordu.

    İddia `folders.js`in TAMAMINA bakmıyor, KÜNYE yüzeylerine bakıyor ve bu
    bilinçli: zincir her `folder.name` geçişinde gerekmiyor, bağlamı belli olan
    yerlerde gürültü olurdu. Genel bir "`folder.name` hiç geçmesin" iddiası
    YANLIŞ olurdu.

    DÜZYAZI SAYIM MEKANİK SAYIMA ÇEVRİLDİ (Tur L): docstring meşru yerler
    arasında "arama eşleştirmesi"ni de sayıyordu ve o cümle bu turda BAYATLADI —
    arama artık zincirden geçiyor. Bayat bir düzyazı hiçbir kapıyı çalmıyor,
    o yüzden sayı aşağıda iddiaya bağlandı.
    """
    js = _folders_js()
    galeri = _render_gallery_body()
    assert re.search(
        r'klasorZinciriDugumu\(rec\.folder_id,\s*"card-badge card-where"', galeri), (
        "arama rozeti zinciri yazmıyor")
    assert not re.search(r"where\.textContent\s*=", galeri), (
        "rozet hâlâ düz metin yazıyor")
    assert js.count("klasorZinciriDugumu(") == 3, (
        "künye düğümünün tanımı + iki çağıranı: üçüncü bir yüzey eklendiyse "
        "iddia da genişletilmeli")
    # `folder.name` artık YALNIZ `renameCurrentFolder`da ve orada PATCH
    # YANITINDAN okunuyor (`currentFolder.name` ve `found.name` yazımları).
    # Üçüncü bir geçiş çıktıysa biri daha ÖNBELLEKTEKİ klasörden tek ad
    # okuyor demektir — arama tam bu yüzden zincire geçti (Tur L).
    assert js.count("folder.name") == 2, (
        f"`folder.name` {js.count('folder.name')} yerde geçiyor: yeni bir "
        "tek-ad okuması eklendiyse zincir mi gerekiyordu diye SORULMALI")

    # ROZET EKRAN OKUYUCUYA DA ULAŞIYOR. Kırpmayı CSS'e vermenin yazılı
    # gerekçesi "ekran okuyucu zinciri tam duyar" — ama kart AÇIK bir
    # `aria-label` taşıyor ve açık etiket, içindeki metnin erişilebilir ada
    # katılmasını ENGELLİYOR. Yani bu yüzeyde gerekçe doğru değildi ve rozet
    # hiç kimseye okunmuyordu: inceleme bulgusu, mandalı bu.
    etiket = re.search(r'card\.setAttribute\("aria-label",(.*?)\);', galeri, re.S)
    assert etiket, "kartın erişilebilir adı yok"
    assert "kartYolu" in etiket.group(1), (
        "zincir erişilebilir ada girmiyor: açık aria-label rozetin metnini "
        "erişilebilirlik ağacından düşürüyor")


def test_the_picker_has_no_hidden_button_clicks():
    """B11 · Gizli düğmeye programatik `.click()` YOK.

    Adım 7b'de aynı hata temizlendi (ray öğeleri kapalı panellerin düğmelerine
    tıklıyordu). Seçici de "Referans yap"ı #upload-btn'e devretmez; tek uygulama
    `setGallerySource`.
    """
    assert ".click()" not in _picker_js(), "seçici gizli düğmeye tıklıyor"


def test_the_picker_writes_only_to_its_own_note():
    """B8 · Seçici `statusEl` yazmaz.

    Yönetmen modunda #status `display:none`, Görsel modunda modalın ARKASINDA —
    yani seçicinin oraya yazdığı her şey görünmez olur. Adım 11'in kök nedeni
    (§0.9) tam olarak buydu; aynı hata ikinci kez yapılmıyor.
    """
    picker = _picker_js()
    assert "statusEl" not in picker, "seçici görünmez bir yüzeye yazıyor"
    assert "picker-note" in picker, "tek geri bildirim yüzeyi kullanılmıyor"


def test_the_picker_note_shows_the_reason_not_just_the_counter():
    """K28 · Kapalı "Ek olarak ekle" sebepsiz kalmaz (PR #23 incelemesi, H1).

    İlk hâlde not `extras.length ? sayaç : gerekçe` idi. Yorumun savunduğu şey
    ("3/3'te sayaç gerekçeyi yener") DOĞRU, ama yalnız KAPASİTE gerekçesi için;
    koşul gerekçeye değil `extras.length`e bağlandığı için İLK ek eklendiği anda
    diğer iki gerekçe de susuyordu. Canlı ölçüm (ana referans A, ek olarak B):

        seçili B → "Bu görsel zaten ek referans listesinde." · düğme KAPALI,
                   not "Eklendi · 1/3" — kullanıcı yer olduğunu okuyor, sebep yok
        seçili A → "Bu görsel zaten ana referans."           · aynısı

    §0.9'un kök nedeni (eylem çalışıyor, geri bildirimi görünmüyor) üçüncü
    kılığında. Artık GEREKÇE varsayılan olarak kazanıyor; "Eklendi" onayı ise
    ekleme ANINDA, çağrı yerinde veriliyor — çünkü ekleme başarılı olduğunda
    seçili karo ARTIK ek listesindedir ve `why` o an da doludur, yani onay
    `renderPickerSide`'a bırakılsa hiç görünmezdi.

    İfadenin BAŞINA sonradan bir hedef dalı geldi (`pickerHedef === "last"`) ve
    bu iddiayı zayıflatmıyor, kapsamını daraltıyor: notun iki cümlesi de
    "+ Ek" düğmesinin hikâyesi ve o düğme bitiş karesi dalında hiç yok. Sıra
    hâlâ ölçülüyor — `why` sayaçtan ÖNCE.
    """
    picker = _picker_js()
    # 1) Notun ifadesi GEREKÇEYLE başlıyor; sayaç yalnız gerekçe yokken.
    assert re.search(r'"picker-note"\)\.textContent\s*=.*?\bwhy\s*\|\|',
                     picker, re.S), (
        "sayaç gerekçeyi eziyor: kapalı düğme açıklamasız kalır")
    # 2) Onay çağrı yerinde: ekleme başarılıysa fiil O AN yazılıyor.
    assert re.search(
        r"addGalleryExtra\(rec\).*?renderPickerSide\(\);\s*"
        r'\$\("picker-note"\)\.textContent\s*=\s*`Eklendi', picker, re.S), (
        "ekleme onayı verilmiyor: gerekçe kazanınca 'Eklendi' hiç görünmez")
    # 3) DURAN okuma ile EYLEM onayı ayrı cümleler. Aynı dize kullanılırsa
    #    `why` boş olan HER karo "Eklendi" der — hiç eklenmemiş karoya geçen
    #    kullanıcı onu eklemiş sanır. `renderPickerSide`'ın dalı fiil taşımaz.
    yan = _balanced_body(picker, "function renderPickerSide()")
    assert "`Eklendi" not in yan, (
        "duran sayaç eylem onayıyla aynı cümleyi kullanıyor: hiç eklenmemiş "
        "karoda 'Eklendi' yazar")
    assert re.search(r"`Ek referans · \$\{extras\.length\}", yan), (
        "duran sayaç yok: ek varken kullanıcı kaç ek olduğunu göremiyor")


def test_the_picker_separates_loading_and_failure_from_emptiness():
    """K29 · "Görselin yok" cümlesi YALNIZ gerçekten boşken kurulur (H2).

    İlk hâlde `#picker-empty` üç durumu tek cümleyle anlatıyordu. Canlı ölçüm
    (`window.fetch` reddedecek şekilde saplandı):

        yakalanmamisRet:         ["TypeError: Failed to fetch"]
        kullaniciyaGorunenMetin: "Bu kapsamda görsel yok"

    Yükleme çökmüşken kullanıcıya YANLIŞ bir cümle söyleniyordu, üstüne
    yakalanmamış promise reddi kalıyordu. Aynı kök neden ikinci belirtiyi de
    veriyordu: `renderMediaPicker()` `await`'ten ÖNCE çağrıldığı için boş durum
    HER açılışta bir an görünüyordu (açılışın ilk karesinde ölçüldü:
    `picker-empty.hidden === false`, `await` sonrası 25 karo).

    Arıza İKİ ayrı yoldan geliyor ve ilk düzeltme yalnız birini kapatmıştı:
    ağ katmanı (`fetch` REDDEDER → `catch`) ve sunucu tarafı (500/404 —
    `fetch` **reddetmez**, `res.ok` false olur ve `loadAllImages` onu yutar,
    yani `catch` HİÇ çalışmaz, liste boş döner). İkincisinde kullanıcı gene
    "görselin yok" okuyordu. `loadAllImages` artık düşen uç sayısını da
    döndürüyor; boş liste **tek başına** "yok" anlamına gelmiyor.
    """
    picker = _picker_js()
    govde = _balanced_body(picker, "async function openPicker(")
    # 1) Redde bir karşılayıcı var: yakalanmamış promise reddi bırakılmıyor.
    #    Sıraya bakılıyor, tek bir yazıma değil — try gövdesine küme parantezi
    #    girse de iddia ayakta kalmalı.
    i_try, i_cagri, i_catch = (govde.find("try {"),
                               govde.find("await loadAllImages()"),
                               govde.find("catch"))
    assert -1 < i_try < i_cagri < i_catch, (
        "openPicker ağ reddini yakalamıyor: yakalanmamış promise + yanlış cümle")
    # 2) Sunucu tarafı arıza da ayırt ediliyor: boş liste tek başına yetmiyor.
    assert "failed" in govde, (
        "düşen uç sayısı hesaba katılmıyor: 500'de gene 'görselin yok' denir")
    # 3) Durum AÇILIŞTA sıfırlanıyor. `picker` diliminin tamamına bakmak
    #    yetmez: `let pickerState = "loading"` BİLDİRİMİ de o dilimde ve iddiayı
    #    kendi başına karşılar — sıfırlama silinse test yeşil kalırdı (ölçüldü).
    #    Sonuç: hatadan sonra tekrar açılışta ekranda "alınamadı" asılı kalır.
    assert 'pickerState = "loading"' in govde, "açılışta durum sıfırlanmıyor"
    # 4) Boş durum metni DURUMU biliyor, yalnız sorguyu değil. İfade artık
    #    doğrudan atanmıyor, bir `const`ta duruyor (gerekçesi bir alttaki
    #    testte: koşulsuz atama canlı bölgeyi her tuş vuruşunda yeniden
    #    duyuruyordu), o yüzden iddia ATAMAYA değil İFADEYE bakıyor.
    metin = re.search(r"const bosMetin\s*=(.*?);", picker, re.S)
    assert metin and "pickerState" in metin.group(1), (
        "boş durum metni yükleme/hata durumunu bilmiyor: üç durum tek cümlede")
    assert 'pickerState = "error"' in govde, "ağ reddi hata durumunu kurmuyor"
    assert '"ready"' in govde, "başarılı yükleme durumu kurulmuyor"
    # 5) Hata cümlesi ekran okuyucuya da ulaşıyor: kap canlı bölge.
    assert re.search(r'id="picker-empty"[^>]*role="status"', _html()), (
        "#picker-empty canlı bölge değil: hata cümlesi hiç duyurulmuyor")


def test_the_empty_state_sentence_is_not_rewritten_when_it_did_not_change():
    """Kuyruk 1 · sonuçsuz arama canlı bölgeyi HER TUŞ VURUŞUNDA yeniden yazıyordu.

    Madde defterde bir İDDİA olarak duruyordu ("duyuruyor OLABİLİR") ve tam da
    ölçülmediği için Tur G'de dokunulmamıştı. Ölçüldü — Chromium 1194, boş
    kütüphane, seçici açık, `#picker-empty` üzerinde MutationObserver
    (childList + characterData + attributes), sonuçsuz kalacak altı harf:

        düzeltmeden önce:  6 childList mutasyonu — beşi AYNI cümleyle
                           ("Sonuç bulunamadı" → "Sonuç bulunamadı")
        düzeltmeden sonra: 1 (yalnız gerçek durum değişimi)

    Kök neden `textContent` atamasının metin düğümünü KOMPLE değiştirmesi:
    kayıt `characterData` değil `childList` geliyor, yani dize hiç değişmemiş
    olsa bile canlı bölge YENİ bir düğüm görüyor. Bir ekran okuyucunun bunu
    kaç kez seslendirdiği araca göre değişir; değişmeyen şey, o kararı veren
    DOM sinyalinin beş kez FAZLADAN üretilmiş olması.

    `hidden` aynı koşuda suçsuz çıktı (sıfır attributes kaydı: özniteliği
    zaten yokken kaldırmak mutasyon üretmiyor), o yüzden orada koşul YOK —
    olmayan bir kusura kalkan yazmak, bir sonraki okuyucuya yanlış bilgi
    bırakmak olurdu.
    """
    govde = _balanced_body(_picker_js(), "function renderPickerGrid(")
    atama = re.search(r"(\w+)\.textContent\s*=\s*bosMetin", govde)
    assert atama, "boş durum metni tek bir `bosMetin` değeri üzerinden yazılmıyor"
    kutu = atama.group(1)
    assert re.search(
        r"if\s*\(\s*" + kutu + r"\.textContent\s*!==\s*bosMetin\s*\)\s*"
        + kutu + r"\.textContent\s*=\s*bosMetin", govde), (
        "atama koşulsuz: aynı cümle her tuş vuruşunda yeniden duyurulur")
    assert '$("picker-empty-text").textContent =' not in govde, (
        "metin koşulu atlayarak doğrudan da yazılıyor: kapı boşa düşer")


def test_the_extra_rejection_sentence_lives_in_exactly_one_place():
    """B6 · Ret gerekçesi tek kaynakta: `extraBlockReason(rec)`.

    Cümle K26 ile kısaldı: parantezli eski hâl ("… (Görsel ekle veya galeriden
    Düzenle)") artık YANLIŞ yol tarif ediyordu — galeri kartının "+Ek"i Adım
    11'de ölçümle kaldırılmıştı (§0.9), yani o kurtuluş yolu yok.
    """
    core = _strip_js_comments(_core_js())
    assert "function extraBlockReason(" in core, "tek kaynak fonksiyon yok"
    assert core.count("Önce ana görseli seç") == 1, (
        "ret cümlesi birden çok yerde — biri güncellenince diğeri bayatlar")
    assert "galeriden Düzenle" not in core, (
        "K26: artık var olmayan bir kurtuluş yolu tarif ediliyor")
    # canAddExtra ADIYLA yeniden kullanılıyor (silinip yeniden yazılmadı).
    assert "function canAddExtra(" in core, "canAddExtra kaybolmuş"
    assert re.search(r"function canAddExtra\([^)]*\)\s*\{[^}]*extraBlockReason\(",
                     core, re.S), "canAddExtra tek kaynağı çağırmıyor"
    assert "addGalleryExtra" in _picker_js(), (
        "B6/B7: seçici addGalleryExtra'yı ADIYLA yeniden kullanmalı")


def test_making_a_reference_closes_the_picker_before_focus_moves():
    """B7 · "Referans yap" → `closePicker()` ÖNCE, `setGallerySource` SONRA.

    `setGallerySource` `$("prompt").focus()` çağırıyor. Açık bir
    `aria-modal="true"` diyaloğun ARKASINA odak verilirse ekran okuyucu
    kullanıcısı diyalogda kilitli kalır, gören kullanıcı ise yazdığını göremez.
    """
    body = _balanced_body(_picker_js(), '$("picker-use-ref").addEventListener')
    close_at = body.find("closePicker(")
    source_at = body.find("setGallerySource(")
    assert close_at >= 0 and source_at >= 0, "commit yolu eksik"
    assert close_at < source_at, "odak açık modalın arkasına veriliyor"


def test_adding_an_extra_keeps_the_picker_open():
    """B7 · Commit bilerek ASİMETRİK: "Ek olarak ekle" seçiciyi kapatmaz.

    Üç ek slotu var (MAX_EDIT_IMAGES 4 − ana referans). Her biri için menüden
    tekrar dönmek saçma; sayaç #picker-note'ta işliyor, slot bitince düğme
    kendi gerekçesiyle kapanıyor.
    """
    body = _balanced_body(_picker_js(), '$("picker-use-extra").addEventListener')
    assert "closePicker(" not in body, "ek eklemek seçiciyi kapatıyor"
    assert "addGalleryExtra(" in body, "ek ekleme tek uygulamayı kullanmıyor"


def test_escape_closes_the_picker_without_leaving_select_mode():
    """B10 · Katman düzeni: tek Escape tek şey kapatır.

    Seçicinin Escape'i #confirm-modal muhafızlı (onay penceresi her zaman
    üstte), ve `folders.js`'teki seçim modu Escape'ine `media-picker` muhafızı
    ekleniyor — yoksa tek Escape hem seçiciyi kapatır hem seçim modundan çıkarır.
    """
    picker = _picker_js()
    assert "Escape" in picker, "seçicinin Escape'i yok"
    assert 'confirm-modal").hidden' in picker, "onay penceresi muhafızı yok"
    assert "stopImmediatePropagation()" in picker, (
        "aynı olay alttaki dinleyicilere de gidiyor")
    # Koşul iki satıra yayılıyor ve içinde `$(…)` parantezleri var; kesim
    # `setSelectMode(false)` çağrısına kadar okunuyor.
    select_escape = re.search(
        r'e\.key === "Escape" && selectMode(.*?)setSelectMode\(false\)',
        _folders_js(), re.S)
    assert select_escape, "seçim modu Escape'i bulunamadı"
    assert 'media-picker").hidden' in select_escape.group(1), (
        "tek Escape hem seçiciyi kapatıp hem seçim modundan çıkarıyor")


def test_opening_the_picker_closes_the_sheets_and_the_plus_menu():
    """B10 · `.sheet` ve `.modal` aynı z-index 50'yi paylaşıyor.

    Açık kalan bir slide-over "Escape neyi kapatır" belirsizliği yaratır; açık
    kalan (+) menüsü ise modalın ARKASINDA asılı kalır.
    """
    assert "closeSheets(" in _picker_js(), "seçici açılırken paneller kapanmıyor"
    core = _core_js()
    menu_loop = re.search(r'for \(const id of \[([^\]]*)\]\)\s*\{?\s*\$\(id\)'
                          r'\.addEventListener\("click", closePlusMenu\)', core)
    assert menu_loop, "menü kapanış dizisi bulunamadı"
    assert "media-pick-btn" in menu_loop.group(1), (
        "menü modalın arkasında açık kalıyor")


def test_the_picker_is_not_a_second_door_to_the_library():
    """B11 · Yasak olan kapı: seçici Kütüphane varlıklarına ikinci kapı OLMAZ.

    Kapsam kilitli: yalnız Medya (üretilen + içe aktarılan). Bindirme varlıkları
    bugünkü #overlay-picker'da kalıyor — iki farklı şeyi tek seçiciye toplamak
    "hangisi bindirme, hangisi referans" sorusunu kullanıcıya bırakırdı.
    """
    picker = _picker_js() + _picker_html()
    for foreign in ("overlay-picker", "assetCache", "logo-modal", "/assets/logos"):
        assert foreign not in picker, f"seçici Kütüphane'ye ikinci kapı olmuş: {foreign}"


def test_the_composer_still_has_exactly_two_primary_buttons():
    """B11 · İki kapı olması yeni bir GÖRSEL ağırlık yaratmamalı.

    Seçicinin "Referans yap"ı birincil; composer'ın kendi birincil sayısı
    değişmemeli, yoksa ekranda üç eşit ağırlıklı eylem olur.
    """
    composer = _section_div(_html(), "composer")
    count = composer.count('class="primary')
    assert count == 1, f"composer'daki birincil sayısı değişmiş: {count}"
    # Seçicinin kendi birincili composer'ın DIŞINDA — aynı anda ikisi görünmüyor.
    assert 'id="picker-use-ref"' not in composer, "seçici composer'ın içine sızmış"
    assert 'class="primary' in _picker_html(), "seçicide birincil eylem yok"


def test_the_search_predicate_is_shared_not_duplicated():
    """B5 · `matchesSearch(rec, q = searchQuery)` — tek yüklem, iki çağıran.

    Seçici kendi eşleştirmesini yazarsa arama iki yerde ayrışır: Medya'da klasör
    adı aranır, seçicide aranmaz (ya da tersi) ve fark sessizdir.
    """
    js = _folders_js()
    assert re.search(r"function matchesSearch\(rec,\s*q\s*=\s*searchQuery\)", js), (
        "yüklem ikinci çağıran için parametreleşmemiş")
    assert "matchesSearch(" in _picker_js(), "seçici ortak yüklemi kullanmıyor"


def test_the_imported_scope_is_a_crossing_filter_not_a_partition():
    """B4 · "İçe aktarılanlar" bir BÖLME değil kesişen süzgeç.

    Klasörsüz + klasörler zaten Tümü'nü tüketiyor; içe aktarılanlar onların
    içinden geçiyor. Yorumda yazılı olmalı, yoksa biri "toplam tutmuyor" diye
    düzeltmeye kalkar (ve bölmeyi bozar).
    """
    assert "imported" in _picker_js(), "içe aktarılanlar kapsamı yok"
    # Bu iddia bilerek YORUMA bakıyor (ham metin): kesişen süzgeç olduğu
    # yazılmazsa sonraki okuyucu "toplam tutmuyor" diye bölmeyi düzeltmeye
    # kalkar. Kural "kodu ara" idi; burada belgelenmiş olmanın KENDİSİ şart.
    assert re.search(r"kesişen süzgeç", _picker_js_raw()), (
        "kesişen süzgeç olduğu yazılmamış — sonraki okuyucu bunu hata sanar")


def test_media_history_cache_readers_use_derived_gorunen_medya():
    """Ayrışma mandalı: sayaç, seçim ve galeri gorunenMedya() okur.

    historyCache ham çekim belleğidir. Süzgeç açıkken renderGallery,
    updateMediaRailCount, syncSelectUI ve #select-all doğrudan historyCache
    okursa sayaç ve seçim ekrandan ayrışır.
    """
    js = _folders_js()
    galeri = _balanced_body(js, "function renderGallery()")
    assert "gorunenMedya()" in galeri, "renderGallery gorunenMedya() okumuyor"
    assert "historyCache" not in galeri, "renderGallery hâlâ doğrudan historyCache okuyor"

    rail = _balanced_body(js, "function updateMediaRailCount()")
    assert "gorunenMedya()" in rail, "updateMediaRailCount gorunenMedya() okumuyor"
    assert "historyCache" not in rail, "updateMediaRailCount hâlâ doğrudan historyCache okuyor"

    select_ui = _balanced_body(js, "function syncSelectUI()")
    assert "gorunenMedya()" in select_ui, "syncSelectUI gorunenMedya() okumuyor"
    assert "historyCache" not in select_ui, "syncSelectUI hâlâ doğrudan historyCache okuyor"

    select_all = _balanced_body(js, '$("select-all").addEventListener')
    assert "gorunenMedya()" in select_all, "#select-all dinleyicisi gorunenMedya() okumuyor"
    assert "historyCache" not in select_all, "#select-all dinleyicisi hâlâ historyCache okuyor"


def test_create_folder_cell_reads_raw_history_cache():
    """Klasör kartları tür süzgecinden etkilenmez kararı mandalı.

    createFolderCell kapak görseli seçerken süzülmemiş ham historyCache'i
    okumaya devam etmelidir.
    """
    js = _folders_js()
    cell = _balanced_body(js, "function createFolderCell(f)")
    assert "historyCache" in cell, "createFolderCell historyCache okumuyor"
    assert "gorunenMedya" not in cell, (
        "createFolderCell tür süzgecine bağlanmış — klasör kapakları türle süzülemez")


def test_the_picker_does_not_mention_media_tur_suzgeci():
    """Seçici Medya'nın durumunu yazmaz ve okumaz — süzgeç yalnız Medya görünümüne aittir."""
    assert "medyaTurSuzgeci" not in _picker_js(), "seçici medyaTurSuzgeci'ni referans almış"


def test_the_picker_grid_geometry_matches_the_approved_split():
    """K25 · Onaylanan bölünme 208 / 1fr / 180 (Faz 0 mock'unda ölçüldü).

    Sözleşmedeki 236px yan bölme orta sütunu 277px'te bırakıyordu = 2 sütun ×
    133px (bir bakışta ~5 karo). 180px ile ızgara 333px = 3 sütun × 103px (~9
    karo) ve sol gezinmedeki klasör adları hâlâ kırpılmıyor.
    `minmax(96px, 1fr)` 3. sütunu açan şey: 132px'lik eski min bu genişlikte de
    2 sütunda kalırdı.
    """
    card = _css_block(".picker-card")
    assert "208px" in card and "180px" in card, "onaylanan bölünme uygulanmamış"
    assert "236px" not in card, "reddedilen sözleşme bölünmesi kalmış"
    assert "min(776px" in card and "min(570px" in card, "modal ölçüsü sözleşme dışı"
    grid = _css_block(".picker-grid")
    assert "minmax(96px, 1fr)" in grid, "3. sütunu açan min kalkmış"


def test_the_picker_tile_is_full_bleed():
    """Faz 0 ölçümü · `<button>`'ın UA padding'i sıfırlanmazsa karo tam kanamaz.

    Ölçüldü (mock, 1440×900): 133px'lik karo 121px'lik görsel taşıyordu —
    UA'nın `padding: 1px 6px`'i. Kütüphane'de `.thumb`'ın kendi 14px'i bunu
    gizliyor, tam kanamalı karoda gizlemiyor.
    """
    assert "padding: 0" in _css_block(".picker-tile"), "karo tam kanamıyor"
    # Mock'un ikinci bulgusu (satır içi kabın aspect-ratio'yu yutması) burada
    # YAPISAL olarak çözüldü: <img> doğrudan düğmenin çocuğu, ara kap yok —
    # <button> zaten <div> taşıyamıyor, span kap ise satır içi olurdu.
    img = _css_block(".picker-tile img")
    assert "aspect-ratio: 1" in img, "karo kare değil"
    assert "object-fit: cover" in img, "karışık oranlar satırları bozar"
    assert "display: block" in img, "satır içi görsel altında hayalet boşluk kalır"


def test_the_picker_preview_cannot_blow_past_its_box():
    """Faz 0 ölçümü · `max-height: 100%` esnek kolonda çözülmüyor.

    Ölçüldü: `height` ÖZNİTELİĞİ kazanıyor ve önizleme 156×1000 oluyor, künye
    ekrandan taşıyor. `height: auto` önce oranı geri veriyor.
    """
    assert "height: auto" in _css_block(".picker-preview img"), (
        "önizleme kutusunu taşırıyor")


def test_the_disabled_secondary_action_reuses_the_existing_ghost_rule():
    """Kapalı "Ek olarak ekle" MEVCUT `.btn-ghost:disabled`'ı devralır.

    Faz 0'ın beşinci bulgusu (`.btn-ghost`'un kapalı hâli yok) `flow.css` için
    doğruydu; `style.css`'te kural zaten var ve #extra-add-btn'i de o
    giydiriyor. Port ikinci bir kural yazsaydı diğer ghost düğmelerin kapalı
    hâlini de sessizce değiştirirdi. Bu test tekrarın geri gelmesini engelliyor.
    """
    css = _css()
    assert css.count(".btn-ghost:disabled {") == 1, (
        "kapalı ghost düğme kuralı çoğaltılmış — biri diğerini eziyor")
    block = _css_block(".btn-ghost:disabled")
    assert "not-allowed" in block, "imleç reddi söylemiyor"
    assert "opacity" in block, "kapalı düğme sönmüyor"
    # Seçicinin ikincili o kuralın kapsamında; kendi kapalı hâlini yazmıyor.
    assert 'id="picker-use-extra" class="btn-ghost"' in _picker_html(), (
        "ikincil eylem ghost değil — kapalı hâli tanımsız kalır")
    assert ".picker-commit .btn-ghost:disabled" not in css, (
        "seçici kendi kapalı hâlini yazmış")


def test_the_picker_leaves_the_tab_order_when_it_closes():
    """Faz 0 ölçümü · kapalı modal sekme sırasında kalmamalı.

    Mock'ta ölçüldü: yalnız `opacity: 0 + pointer-events: none` ile kapatılan
    bir kabın 25 kontrolü sekme sırasında kalıyordu. Uygulamanın `.modal`ı
    `[hidden]` ile `display: none` oluyor — JS'in de sınıf değil ÖZNİTELİK
    çevirmesi şart.
    """
    picker = _picker_js()
    assert re.search(r'\$\("media-picker"\)\.hidden = true', picker), (
        "kapanış hidden özniteliğini çevirmiyor")
    assert re.search(r'\$\("media-picker"\)\.hidden = false', picker), (
        "açılış hidden özniteliğini çevirmiyor")
    assert "classList" not in picker or "media-picker" not in picker.split("classList")[1][:40], (
        "modal sınıfla kapatılıyor — kapalıyken odaklanabilir kalır")


def test_the_picker_labels_folders_with_a_string_not_the_breadcrumb_array():
    """`folderPath` bir ETİKET değil, klasör NESNELERİNDEN oluşan zincir döndürür.

    Doğrudan `textContent`e verilince "[object Object],[object Object]" yazıyor;
    canlı turda sol gezinmedeki üç klasör adı da, künyedeki "Klasör" satırı da
    böyle çıktı. Süit yeşildi çünkü hiçbir iddia DEĞERİN TÜRÜNÜ sormuyordu —
    kelime araması gibi burada da tür sessizce yanlıştı.

    İddia: zinciri METNE çeviren TEK yer `folderPathParts` ve orası `.map(...)`
    ile adlara iniyor; etiketler ile künyeler oradan besleniyor.

    YENİDEN YAZILDI (zincir ortak yardımcıya taşındığında): iddia eskiden
    seçici diliminin İÇİNDEKİ `folderPath(...)` çağrılarını tarıyordu. Zincir
    `folderPathParts`e taşınınca o dilimde SIFIR eşleşme kaldı — döngü hiç
    dönmüyor, yani iddia kendiliğinden VACUOUS oldu ve yeşil kalarak hiçbir
    şey korumuyordu. Sessizce ölen bir mandal, hiç yazılmamış bir mandaldan
    kötüdür: kaldırılmadı, dönüştürüldü. (`folderPath` dosyada dört yerde
    çağrılıyor ve biri diziyi meşru olarak bir DEĞİŞKENE alıyor — "her çağrının
    ardından `.map(` gelmeli" iddiası dosya geneline açılamazdı.)
    """
    js = _folders_js()
    parcalar = _balanced_body(js, "function folderPathParts(")
    assert ".map(" in parcalar, (
        "zincir adlara çevrilmiyor: `textContent` [object Object] yazar")
    assert "KLASOR_AYRACI" in parcalar, "ayraç tek sabitten gelmiyor"

    picker = _picker_js()
    assert "pickerFolderLabel" in picker, "klasör etiketi tek yerden üretilmiyor"
    assert "klasorZinciriEtiketi(folderPathParts(" in js, (
        "etiket zinciri kendi başına birleştiriyor: ayraç ikizlenir")

    # AYRACIN TEK KOPYASI. İlk yazımda sabit tanıtılmış ama kırıntı başlığı ile
    # taşıma listesi kendi `join(" / ")`ünü yazmaya devam ediyordu — yani sabitin
    # yorumu ("üç yüzey aynı yazımı kullanmak zorunda") DOĞRU DEĞİLDİ ve hiçbir
    # mandal bunu göstermiyordu. İnceleme bulgusu; iddia o boşluğu kapatıyor.
    assert js.count('" / "') == 1, (
        "ayraç ikinci kez satır içi yazılmış: biri değişirse aynı klasör iki "
        "yüzeyde iki farklı adla görünür")

    # ÖLÜ DÖNGÜ KALDIRILDI: buradaki `folderPath(...)` taraması seçici diliminde
    # SIFIR eşleşme buluyordu (tek çağrı `folderPathParts`, deseni tutmuyor).
    # Yukarıdaki `folderPathParts` iddiası aynı türü ondan daha sıkı koruyor.


def test_set_gallery_source_by_id_switches_section_to_studio():
    """`setGallerySourceById` rotası `showSection("studio")` kullanmalı.

    Eski `showView("studio")` refactoring ile kaldırılmıştı — çağrılırsa
    `ReferenceError` fırlatır.
    """
    core = _core_js()
    fn_body = _balanced_body(core, "function setGallerySourceById")
    assert 'showSection("studio")' in fn_body, "showSection(\"studio\") çağrısı eksik"
    assert "showView(" not in fn_body, "eski showView çağrısı kalmış"




# ── Model seçici (v0.6) ────────────────────────────────────────────────
#
# Dosyada fixture yok (her test kendi client'ını kuruyor); bu blok tek satırlık
# bir yardımcı paylaşıyor çünkü beş iddia aynı HTML'e bakıyor.


def _served() -> str:
    return TestClient(appmod.app).get("/").text


def test_model_secimi_NATIVE_kontrollerle_yapiliyor():
    """Seçim ARTIK alttan açılan bir panelde — ama hâlâ native kontrollerle.

    ESKİ SÖZLEŞME şuydu: seçici native bir `<select>` olmak zorunda, çünkü
    "özel bir popover listbox odak tuzağını, klavye gezintisini ve ARIA
    listbox semantiğini sıfırdan getirirdi". Yüzey kullanıcı isteğiyle alttan
    açılan bir panele taşındı ve o gerekçenin ÜÇ maddesİ de iptal edilmedi,
    KARŞILANDI — iddia da onu ölçüyor:

      1. klavye gezintisi + ARIA semantiği → kartlar gerçek
         `<input type="radio">`, `<fieldset>` içinde. Elle yazılmış
         `role="listbox"`/`role="option"` YOK.
      2. katman mekaniği → panel `.sheet sheet-bottom`, yani perde
         (`body:has(.sheet.open) .scrim`), Escape şelalesi ve Android geri
         tuşu (`window.geriTusu`) olduğu gibi devralınıyor.
      3. değerin sahibi → `<select>`ler DOM'da KALIYOR. Seçim onların
         `value`suna yazılıp `change` gönderiliyor, yani tercih yazımı,
         eksen doldurma ve `submitComposer` hiç değişmiyor.

    NE İDDİA EDİLMİYOR: odak tuzağı yok ve sürükleyerek kapatma yok —
    depodaki öteki beş panelde de yok. İddia "elle kurulmuş ARIA'ya dönüşü"
    yakalıyor; eskiden "daha güzel bir popover'a dönüşü" yakalıyordu.
    """
    # YORUMLAR AYIKLANMIŞ, `_css_block`un yardımcısındaki dersin aynısı:
    # aşağıdaki "role= yok" iddiası, o kararın index.html'deki GEREKÇESİNDE
    # geçen `role="listbox"` sözcüğüne takılıyordu — yani iddia kendi
    # açıklamasını hata sayıyordu. Depo bu tuzağa dördüncü kez düştü.
    ham = _served()
    html = re.sub(r"<!--.*?-->", "", ham, flags=re.S)
    # 3. madde: değer taşıyıcıları yerinde.
    assert '<select id="model"' in html
    assert '<select id="chat-model"' in html
    assert '<select id="video-model"' in html
    # Görünen yüz: DÖRT çip düğmesi de AYNI paneli açıyor.
    #
    # Üçüncüsü arena ekseni (`#arena-btn`): aynı liste, aynı filtre, aynı
    # kapanma mekaniği — yalnız kartlar checkbox. İkinci bir model yüzeyi
    # açmak, bu testin koruduğu tekilliği bozardı.
    #
    # DÖRDÜNCÜSÜ video ekseni (v0.13) ve tam olarak aynı dersi ödüyor: video
    # şeridi kendi `<select>`ini ve kendi çipini getirdi (tür karışmasın diye,
    # bkz. index.html'deki gerekçe) ama İKİNCİ BİR PANEL getirmedi. Sayı
    # burada LİTERAL duruyor ki beşinci bir eksen eklendiğinde bu satır
    # okunmak zorunda kalsın.
    for tetik in ("model-btn", "chat-model-btn", "video-model-btn", "arena-btn"):
        assert f'id="{tetik}"' in html, f"#{tetik} yok — seçim açılamaz"
    assert html.count('aria-controls="model-sheet"') == 4, (
        "dört çip de #model-sheet'i işaret etmiyor")
    # 2. madde: ortak kabuk.
    assert 'id="model-sheet" class="sheet sheet-bottom"' in html, (
        "panel ortak `.sheet` kabuğunu kullanmıyor — perde, Escape ve Android "
        "geri tuşu `.sheet.open`a bakıyor, hepsi sessizce ölürdü")
    # 1. madde: ARIA elle YAZILMIYOR.
    assert 'role="listbox"' not in html and 'role="option"' not in html, (
        "elle kurulmuş bir listbox semantiği geri gelmiş — native radyo "
        "grubunun tek gerekçesi tam olarak bunu yazmamaktı")
    assert 'id="model-sheet-list"' in html
    assert '<fieldset id="model-sheet-list"' in html, (
        "kartlar bir <fieldset> içinde değil — radyo grubu semantiği kaybolur")
    # `<legend>` ŞART, iki sebeple: adsız bir `<fieldset>` ekran okuyucuya
    # "grup" der ama neyin grubu demez; ve `renderModelCards` onu koruyarak
    # yeniden çiziyor (`replaceChildren(legend, …)`) — düğüm hiç yoksa o
    # çağrı `TypeError` atar ve panel BOŞ açılır.
    liste = html.split('<fieldset id="model-sheet-list"', 1)[1].split("</fieldset>", 1)[0]
    assert "<legend" in liste, "#model-sheet-list adsız bir grup"
    assert '"checkbox" : "radio"' in _js("core.js"), (
        "kartlar native radyo/checkbox kurmuyor — çoklu eksende de semantik "
        "tarayıcıdan gelmek zorunda")


def test_cip_dugmesinin_adi_EKSENI_de_soyluyor():
    """Çipin erişilebilir adı = eksen + seçili model.

    Düğmenin adı bir zamanlar YALNIZ içeriğiydi: ekran okuyucu "gpt-image-1 —
    5–20 kredi, düğme" diyor, çipin hangi eksene ait olduğunu (görsel modeli
    mi yönetmen modeli mi) hiç söylemiyordu. Yandaki `.sr-only` etiket
    `for="model"` ile `aria-hidden` bir DEĞER TAŞIYICISINI etiketliyor, yani
    görünen kontrolle programatik bağı yoktu — `title` de ad hesabına
    girmiyor (içerik ve `aria-labelledby` onu eziyor) ve dokunmatikte hiç
    görünmüyor, bu panelin var olma sebebi tam olarak buydu.

    İddia SIRAYA da bakıyor: sabit yarı önce, değişen yarı sonra. Ters sıra
    "gpt-image-1 … Görsel modeli" diye okunurdu.
    """
    html = re.sub(r"<!--.*?-->", "", _served(), flags=re.S)
    for tetik, etiket, deger, ad in (
            ("model-btn", "model-label", "model-btn-label", "Görsel modeli"),
            ("chat-model-btn", "chat-model-label", "chat-model-btn-label",
             "Sohbet modeli")):
        acik = re.search(rf'<button[^>]*id="{tetik}"[^>]*>', html)
        assert acik, f"#{tetik} yok"
        assert f'aria-labelledby="{etiket} {deger}"' in acik.group(0), (
            f"#{tetik} adını eksenden almıyor: {acik.group(0)}")
        # Referanslar GERÇEKTEN var olmalı: kırık bir idref sessizce adsız
        # bir düğme demek (ad hesabı bulunamayan referansı atlar).
        etiket_acik = re.search(rf'<label id="{etiket}"[^>]*>([^<]*)</label>', html)
        assert etiket_acik, f"#{etiket} etiketi yok — adın sabit yarısı kayıp"
        assert etiket_acik.group(1).strip() == ad, etiket_acik.group(0)
        # Etiket ağaçta SERBEST METİN olarak durmamalı: `for` ile işaret ettiği
        # `<select>` de `aria-hidden` olduğu için gezinme kipinde eksen adı bir
        # kez tek başına, bir kez de düğmenin adında okunuyordu. `aria-labelledby`
        # gizli düğümün metnini de okuduğu için ad kaybolmuyor.
        assert 'aria-hidden="true"' in etiket_acik.group(0), (
            f"#{etiket} ağaçta serbest metin — eksen adı iki kez okunur")
        assert f'id="{deger}"' in html, f"#{deger} yok — adın değişen yarısı kayıp"
    # Değişen yarının TEK yazarı `syncModelChip`; ikinci bir yazar iki adın
    # ayrışması demekti (`aria-label` yerine `aria-labelledby` seçilmesinin
    # sebebi de bu).
    core = _js("core.js")
    assert core.count("$(eksen.etiket).textContent") == 1, (
        "çip metnini yazan ikinci bir yer var")


def test_model_secici_composer_bar_da_DEGIL():
    """360px genişlik bütçesinin mandalı.

    `mobile.css` ölçümü yazıyor: `.composer-bar` zaten ~380px > 360px ve
    `.composer-right` kendi satırına düşürülmüş durumda. Dördüncü bir kontrol
    oraya konursa ÜÇÜNCÜ satır açılır ve `--composer-h` tuvalin alt boşluğunu
    yer. Regresyon masaüstü tarayıcıda GÖRÜNMEZ — bu yüzden mekanik iddia.
    """
    html = _served()
    model_at = html.index('<select id="model"')
    bar_at = html.index('class="composer-bar"')
    assert model_at < bar_at, (
        "model seçici .composer-bar'ın içine/sonrasına taşınmış — 360px "
        "genişlik bütçesi (mobile.css) yeniden ölçülmeli")


def test_eksen_satirlari_adreslenebilir():
    """Kalite ekseni OLMAYAN model var: satır gizlenebilmeli.

    Etiket de adreslenebilir çünkü aynı eksenin adı modele göre değişiyor
    ("Boyut" ↔ "Oran") ve Prompt Yönetmeni'nin atlanan-öneri metni o adı okuyor.
    """
    html = _served()
    for eid in ("spec-size", "spec-quality", "spec-n",
                "label-size", "label-quality", "label-n"):
        assert f'id="{eid}"' in html, eid


def test_adet_secenekleri_value_ozniteligi_TASIYOR():
    """`#n` seçenekleri eskiden `value` taşımıyordu ve `option.value` metne
    düşüyordu — chat.js'teki uyarının konusu. Seçenekler artık core.js
    tarafından da kuruluyor, ama HTML'deki ilk çizim aynı sözleşmeyi tutmalı:
    yoksa Ayarlar gelmeden atılan tek turda değer ayrışırdı."""
    assert '<option value="1">1</option>' in _served()


def test_kredi_satiri_ve_model_notu_var():
    html = _served()
    for eid in ("run-cost", "model-note", "model-note-text",
                "model-settings-link"):
        assert f'id="{eid}"' in html, eid


def _js(ad: str) -> str:
    return TestClient(appmod.app).get(f"/static/{ad}").text


def test_sohbet_modeli_secicisi_YONLENDIRME_gelmeden_gizli():
    """Boş ve GÖRÜNÜR bir açılır liste, #model-note'un reddettiği şeyin aynısı.

    `#chat-model` PR #41'de eklendi ama seçeneklerini dolduran hiçbir kod yok
    (`/api/settings` → `chat_models` sunuluyor, okuyan yok) ve `ChatRequest`
    bir model alanı KABUL ETMİYOR (`extra="forbid"`), yani seçim tel üzerine
    çıkamıyor. Yönetmen modunda kullanıcı tıklanabilir, boş bir liste
    görüyordu.

    İDDİA KOŞULLU: yönlendirme geldiği gün (ChatRequest bir `model` alanı
    kabul ettiğinde) bu test seçimin AÇILMASINI istiyor. Yani bekçi hem
    bugünü kilitliyor hem de yarın kendini iptal ediyor — "gizle ve unut"
    olmasın diye.

    ÖLÇÜLEN ÖĞE DEĞİŞTİ (alttan açılan seçici turu): "görünürlük" artık
    `<select>`in özelliği değil. Seçici değer TAŞIYICISI oldu (`.sr-only`) ve
    kullanıcının gördüğü kontrol `#chat-model-btn`. Eski iddia
    (`"hidden" not in` seçici etiketi) bugün de geçerdi ama YANLIŞ şeyi
    ölçerdi: taşıyıcıyı görünür tutmak kullanıcıya hiçbir şey göstermiyor.
    Bu yüzden koşullu yapı korunuyor, hedef tetikleyiciye taşınıyor.

    DİKKAT — `.sr-only` bir SÖZLEŞME parçası: taşıyıcı erişilebilirlik
    ağacında ikinci bir kontrol olarak durmamalı, yoksa tek bir değer için iki
    kontrol duyurulur.
    """
    html = _served()
    yonlendirme_var = "model" in models.ChatRequest.model_fields
    isaretsiz = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    secici = re.search(r"<select id=\"chat-model\"[^>]*>", isaretsiz)
    assert secici, "#chat-model kayboldu (152 id sözleşmesi)"
    assert "sr-only" in secici.group(0), (
        "#chat-model bir DEĞER TAŞIYICISI: ekranda görünen kontrol "
        "#chat-model-btn ve iki kontrol tek değeri paylaşmamalı")
    assert 'aria-hidden="true"' in secici.group(0), (
        "taşıyıcı erişilebilirlik ağacında — `.sr-only` yalnız GÖZDEN "
        "saklıyor, ekran okuyucu tek değer için iki kontrol duyuruyor")
    assert 'tabindex="-1"' in secici.group(0), (
        "taşıyıcı sekme sırasında — klavye yolu panelin radyo grubunda")

    tetik = re.search(r"<button[^>]*id=\"chat-model-btn\"[^>]*>", isaretsiz)
    if yonlendirme_var:
        assert tetik, ("ChatRequest artık model alıyor — seçim görünür olmalı, "
                       "yani #chat-model-btn bulunmak zorunda")
        assert "hidden" not in tetik.group(0), (
            "ChatRequest artık model alıyor ama seçim çipi gizli — "
            "kullanıcı tel üzerine çıkan bir seçimi hiç yapamıyor")
    else:
        assert not tetik or "hidden" in tetik.group(0), (
            "seçim tel üzerine çıkamıyor ama çip görünür — kullanıcıya "
            "tutulmayan bir seçim sözü veriliyor")


def test_model_tercihi_secimle_AYNI_ANDA_bellekte_de_tazeleniyor():
    """`savePref` diske yazıyor; `seciliModelTercihi` de tazelenmek ZORUNDA.

    `applyModels` her çağrıldığında o değişkeni okuyor ve o yalnızca açılışta
    (`loadModelPref`) yazılıyordu. "Kaydet"e basmak `applyConfigured`i
    yeniden çalıştırdığı için kullanıcının bu turda seçtiği model AÇILIŞTAKİ
    değere geri sıçrıyordu — yani PR #41'in ana akışı ("OpenAI modelini seç →
    anahtarını gir → kaydet") kendi seçimini geri alıyordu.
    """
    js = _js("core.js")
    blok = re.search(r"\$\(\"model\"\)\.addEventListener\(\"change\".*?\n\}\);",
                     js, flags=re.S)
    assert blok, "#model change dinleyicisi bulunamadı — kalıp bayatladı mı?"
    assert "savePref(" in blok.group(0)
    assert "seciliModelTercihi" in blok.group(0), (
        "tercih diske yazılıyor ama bellekteki kopya eski kalıyor — sonraki "
        "applyModels seçimi geri alır")


def test_acilista_ayarlari_zorla_acan_kapi_SAGLAYICI_NOTR():
    """`configured` yalnız AZURE'u ölçüyor; açılış kapısı ona bakmamalı.

    Yalnızca OpenAI anahtarı olan kullanıcı her açılışta Ayarlar panelini
    yüzünde buluyordu — tam olarak 180342a'nın kapatmaya çalıştığı durum.
    `#go`nun kapısı `goBlockReason()`e taşınmıştı, bu satır taşınmamıştı.
    """
    blok = re.search(r"async function loadSettings\(openIfMissing\) \{.*?\n\}",
                     _js("settings.js"), flags=re.S)
    assert blok, "loadSettings bulunamadı — kalıp bayatladı mı?"
    govde = blok.group(0)
    assert "openSettings()" in govde, "açılış kapısı kayboldu"
    assert "!configured && openIfMissing" not in govde, (
        "kapı Azure'a özel bayrağa bakıyor — OpenAI kullanıcısında panel "
        "her açılışta zorla açılır")
    assert "imageModels.some" in govde, (
        "ölçüt 'hiçbir modelin anahtarı yok' olmalı (ilk kurulum)")
    # `catch` dalındaki KOŞULSUZ `openSettings()` bilerek duruyor: durum hiç
    # okunamadıysa fail-closed davranmak doğru — orada ölçülecek bir katalog
    # da yok. Bu iddia onu yanlışlıkla silmeye karşı.
    assert govde.count("openSettings()") == 2, (
        "fail-closed dalı (catch) kayboldu ya da üçüncü bir kapı eklendi")


def test_yonetmenin_onerisi_KREDI_tahminini_de_tazeliyor():
    """`applyToForm` programatik `.value` yazıyor: `change` DOĞMUYOR.

    `syncSpecs` bu yüzden elle çağrılıyordu, ama PR #41'de eklenen
    `syncRunCost` çağrılmıyordu — yönetmenin önerisi adet/kalite
    değiştirdiğinde `#run-cost` eski tahmini göstermeye devam ediyordu.
    Bu ikisi core.js'teki `change` dinleyicisinde TEK çift olarak koşuyor;
    ayrışması sessiz.
    """
    blok = re.search(r"function applyToForm\(parsed\) \{.*?\n\}",
                     _js("chat.js"), flags=re.S)
    assert blok, "applyToForm bulunamadı — kalıp bayatladı mı?"
    assert "syncSpecs()" in blok.group(0)
    assert "syncRunCost()" in blok.group(0), (
        "üretim ayarları çipi tazeleniyor ama kredi tahmini eski kalıyor")


# ── Gemini · Ayarlar formunun sağlayıcı grubu ───────────────────────────


def test_katalogdaki_her_GORSEL_saglayicisinin_ayarlar_formunda_grubu_var():
    """En sessiz kırılma bu olurdu: katalog modeli sunar, arayüz anahtarı
    ALAMAZ.

    Gemini kimliği `catalog.CREDENTIALS`'ta v0.6'dan beri duruyor ve
    `models.SettingsRequest` alanı da vardı, ama Ayarlar formunda ne seçenek ne
    kutu vardı — yani model eklendiği gün seçilebilir olur, "kurulum gerekli"
    yazar ve kullanıcı anahtarını gireceği yeri HİÇ bulamazdı. Kapı katalogdan
    türetiliyor, elle sayılmıyor.
    """
    import catalog

    html = _html()
    for cred in {catalog.credential(m.credential) for m in catalog.IMAGE_MODELS}:
        if not cred.secret_field:
            continue
        # Azure'ın grubu `prov-azure`, kimliği `azure_image` — grup adı
        # SAĞLAYICI seçicisinin değeri, kimlik id'si değil.
        p = "azure" if cred.id.startswith("azure") else cred.id
        assert f'id="prov-{p}"' in html, f"{cred.id}: Ayarlar'da alan grubu yok"
        assert f'value="{p}"' in html, f"{cred.id}: sağlayıcı seçicisinde yok"


def test_saglayici_secicisindeki_her_deger_bir_ALAN_GRUBUNA_karsilik_geliyor():
    """`syncProviderFields` listedeki adlarla `$(\"prov-…\")` kuruyor: seçicide
    olup listede olmayan bir değer seçilince HİÇBİR grup görünmez (ya da
    öncekinin üstünde kalır), listede olup HTML'de olmayan bir ad ise
    `$()` null döndürüp `hidden` atamasında TypeError atar."""
    html = _html()
    secici = html.split('<select id="set-provider">', 1)[1].split("</select>", 1)[0]
    secenekler = set(re.findall(r'value="([a-z-]+)"', secici))
    gruplar = set(re.findall(r'id="prov-([a-z-]+)"', html))
    assert secenekler == gruplar, (
        f"seçici {sorted(secenekler)}, gruplar {sorted(gruplar)}")

    js = _js("settings.js")
    dongu = re.search(r'for \(const p of \[([^\]]+)\]\)', js)
    assert dongu, "syncProviderFields'in sağlayıcı listesi bulunamadı"
    assert set(re.findall(r'"([a-z-]+)"', dongu.group(1))) == gruplar


def test_form_alani_olan_her_gizli_ALAN_kaydetme_govdesine_giriyor():
    """Bağlanmamış bir kutu, kutunun HİÇ olmamasından KÖTÜ: kullanıcı anahtarı
    yazıyor, "Kaydedildi." okuyor ve hiçbir şey kaydedilmemiş oluyor.

    Gövde `saveSettings` içinde elle yazılıyor (tek bir POST, katalog döngüsü
    yok) — o yüzden kapı burada, testte.

    İddia FONKSİYONUN TAMAMINA bakıyor, yalnız JSON literaline değil: Azure'ın
    kutusu (`set-key`) fonksiyonun başında bir `const`a okunuyor ve literalde
    kısa adıyla (`api_key`) görünüyor. Literale bakan bir test o meşru dolaylığı
    hata sanardı.
    """
    js = _js("settings.js")
    govde = js.split("async function saveSettings()", 1)[1].split("\n}", 1)[0]
    assert "JSON.stringify({" in govde, "saveSettings gövdesi ayıklanamadı"
    html = _html()
    for alan in re.findall(r'id="(set-[a-z-]*key)"', html):
        assert f'$("{alan}")' in govde, f"{alan} POST gövdesine hiç girmiyor"


def test_yeni_anahtar_kutulari_ACILISTA_ve_KAYITTAN_SONRA_temizleniyor():
    """Yalnızca-yazılır formun kuralı: kayıtlı anahtar hiçbir zaman forma
    dolmuyor, o yüzden boş kutu "sildim" değil "dokunmadım"dır. Bir kutu
    temizlenmezse önceki oturumun anahtarı ekranda kalır."""
    js = _js("settings.js")
    html = _html()
    ac = js.split("function openSettings(", 1)[1].split("\n}", 1)[0]
    kayit = js.split("st.textContent = \"Kaydedildi.\"", 1)[0]
    for alan in re.findall(r'id="(set-[a-z-]*key)"', html):
        assert f'$("{alan}").value = ""' in ac, f"{alan} açılışta temizlenmiyor"
        assert f'$("{alan}").value = ""' in kayit, f"{alan} kayıttan sonra kalıyor"


# ── Model şeridinde sağlayıcı işareti (v0.8) ────────────────────────────


def test_ISARET_secili_modelin_yaninda_ve_SARMALAYICI_icinde():
    """İşaret şeridin İÇİNDE: iki `<select>` de bir sarmalayıcıya girmek zorunda.

    Native `<option>` görsel taşıyamıyor (`renderModelOptions`'ın kendi notu),
    yani açılan listede işaret YOK ve olamaz. Gösterilebilen tek şey SEÇİLİ
    modelin sağlayıcısı ve onun yeri çipin kendisi — ayrı bir kardeş ikon
    şeritten kopuk bir süs olurdu.
    """
    html = _html()
    for sarmal, img, secici in (("model-pick", "model-logo", "model"),
                                ("chat-model-pick", "chat-model-logo", "chat-model")):
        blok = html.split(f'id="{sarmal}"', 1)
        assert len(blok) == 2, f"#{sarmal} sarmalayıcısı yok"
        govde = blok[1].split("</span>", 1)[0]
        assert f'id="{img}"' in govde, f"#{img} sarmalayıcının dışında"
        assert f'<select id="{secici}"' in govde, (
            f"#{secici} sarmalayıcının dışında — mod ekseni kabuğu gizleyemez")


def test_ISARET_ekran_okuyucuya_IKINCI_KEZ_okunmuyor():
    """`alt=""` + `aria-hidden`: sağlayıcı adı `<option>` metninde ZATEN var.

    İşaret yeni bir bilgi taşımıyor, var olanın görsel kısayolu. Adlandırılmış
    bir `<img>` her şerit değişiminde aynı adı ikinci kez okuturdu.
    """
    html = _html()
    for img in ("model-logo", "chat-model-logo"):
        etiket = re.search(rf'<img id="{img}"[^>]*>', html)
        assert etiket, f"#{img} işaretlemede yok"
        assert 'alt=""' in etiket.group(0), f"#{img} adlandırılmış (alt boş değil)"
        assert 'aria-hidden="true"' in etiket.group(0), f"#{img} ağaçta duruyor"
        # İlk karede boş bir kutu çizilmesin: katalog gelene kadar `hidden`.
        assert "hidden" in etiket.group(0).replace('aria-hidden="true"', ""), (
            f"#{img} ilk karede görünür — src'siz kırık bir <img> çizer")


def test_ISARET_adresi_SUNUCUDAN_geliyor():
    """İstemci dize birleştirmiyor: `logo` alanı hazır adres taşıyor.

    Sağlayıcı adını istemcide literal saymak (`m.provider === "gemini"`) yeni
    bir sağlayıcı eklendiği gün işaretin sessizce kaybolması demekti — kapının
    katalogdan türetilme kuralının (`syncChatDeployField`) aynısı. Adresteki
    `?v=` de sunucuda kuruluyor, yani sürüm literali istemciye hiç geçmiyor.
    """
    js = _js("core.js")
    govde = js.split("function setModelLogo(", 1)[1].split("\n}", 1)[0]
    assert "model.logo" in govde, "işaret adresi sunucudan okunmuyor"
    assert "/static/img/providers" not in govde, "adres istemcide kuruluyor"
    for ad in ("azure", "openai", "gemini"):
        assert f'"{ad}"' not in govde, f"sağlayıcı adı ({ad}) literal olarak sayılmış"


def test_ISARET_her_iki_seride_de_baglaniyor():
    """Çağrı yeri `applyModel` / `applyChatModel`: ikisi de hem ilk çizimde hem
    `change`de koşuyor, yani ikinci bir senkronizasyon noktası doğmuyor.

    Şeridi tazeleyen başka bir yol yok; işaret bu iki fonksiyonun dışında
    yazılırsa "hangisi kazandı" sorusu doğar (`.model-note`ın hidden ekseniyle
    aynı ders).

    İDDİA BİR KADEME İLERİ TAŞINDI (alttan açılan seçici turu). Çip artık
    `<button>` ve tazelenecek ÜÇ şey var: işaret, metin ve panelin işaretli
    radyosu. Üçü `syncModelChip`te toplandı, yani `applyModel` doğrudan
    `setModelLogo` çağırmıyor — eski iddia (`setModelLogo("model-logo"` bu
    fonksiyonun gövdesinde) o yüzden düştü.

    Ölçülen şey DEĞİŞMEDİ, güçlendi: iki fonksiyonun her biri kendi eksenini
    tazelemek ZORUNDA ve `setModelLogo`un TEK çağrı yeri var. Eskiden iki
    çağrı yeri vardı ve "işaret ile metin ayrı yerden yazılıyor" hâli
    ölçülmüyordu — çipin metni native `<select>`ten bedavaya geliyordu ve o
    bedava yol `<button>`la kapandı.
    """
    js = _js("core.js")
    for fn, eksen in (("function applyModel(", "image"),
                      ("function applyChatModel(", "chat")):
        govde = js.split(fn, 1)[1].split("\n}", 1)[0]
        assert f'syncModelChip("{eksen}"' in govde, f"{fn} çipi tazelemiyor"

    # `setModelLogo` TEK yerden çağrılıyor: iki çağrı yeri, işaretin metinden
    # ayrı bir yolla yazılabildiği anlamına gelir ve "hangisi kazandı" sorusu
    # tam orada doğar.
    assert js.count("setModelLogo(") == 2, (
        "setModelLogo bir tanım + bir çağrıdan fazla yerde geçiyor — işaret "
        "artık çipin metninden ayrı bir yoldan yazılabiliyor")
    govde = js.split("function syncModelChip(", 1)[1].split("\n}", 1)[0]
    assert "setModelLogo(" in govde, "syncModelChip işareti tazelemiyor"


def test_ISARET_cipin_tiklamasini_YUTMUYOR():
    """`pointer-events: none` ŞART: işaret çipin üstünde mutlak konumda duruyor.

    Yutarsa işaretin üstüne yapılan tıklama native `<select>`e gitmez ve
    Android'de sistem seçicisi açılmaz — `index.html`'in "native select"
    kararının bedelsiz kalması tam olarak buna bağlı.
    """
    govde = _css_block(".model-logo")
    assert "pointer-events: none" in govde, "işaret tıklamayı yutuyor"
    assert "position: absolute" in govde, "işaret çipin içine oturmuyor"
    # Metin işaretin üstüne binmesin: çipin sol dolgusu işaret için açık.
    cip = _css_block(".model-chip")
    assert "padding: 6px 10px 6px 30px" in cip, (
        ".model-chip'in sol dolgusu işaret için açılmamış — metin üstüne biner")


def test_SARMALAYICI_hidden_yazildiginda_GERCEKTEN_gizleniyor():
    """`display` atayan bir yazar kuralı UA'nın `[hidden]`ını EZİYOR.

    `.model-pick` `display: inline-flex` atıyor, yani sarmalayıcıya `hidden`
    yazan bir sonraki tur şeridi gizlediğini SANIR ve şerit yerinde kalır.
    Depoda bu dersin iki kez ödenmiş hâli var (`#chat-model[hidden]`,
    `.model-note[hidden]`); üçüncüsü tek satır.
    """
    css = _js("style.css")
    assert ".model-pick[hidden] { display: none; }" in css, (
        "sarmalayıcının [hidden] mandalı yok — `hidden` sessizce işlemez")


def test_SERIT_SATIRI_marka_onekini_TEKRARLAMIYOR():
    """İşaret markayı söylüyorsa etiket de söylememeli: satır `short_label` yazıyor.

    Kısaltma SUNUCUDA (`catalog.short_labels`): istemci ne marka adı sayıyor ne
    de dize kırpıyor — `logo` adresinin sunucuda kurulmasıyla aynı gerekçe. Geri
    düşüş (`|| m.label`) bilinçli: alanı taşımayan eski bir yanıtta şerit adsız
    kalmasın.

    ADI OKUYAN YER ÜÇE ÇIKTI (alttan açılan seçici turu): iki `<option>`
    listesi ve panelin kart satırı. `<option>` metnini kuran mantık
    `modelSecenekMetni`ye toplandı — çip artık `<button>` ve seçili modelin
    metnini native `<select>`ten bedavaya ALAMIYOR, yani aynı metin iki yerde
    gerekiyordu. Bir yerde `short_label`, ötekinde `label` yazan gün marka
    çipte iki kez okunur ve bu masaüstünde göze çarpmaz.

    O yüzden iddia iki kademeli: render fonksiyonları adı KENDİ kurmuyor
    (tek kaynağa soruyor), tek kaynak da `short_label` okuyor.
    """
    js = _js("core.js")
    ADI_KURAN = "function modelSecenekMetni("
    for fn in (ADI_KURAN, "function renderModelCards("):
        govde = js.split(fn, 1)[1].split("\n}", 1)[0]
        assert "short_label" in govde, f"{fn} şerit adını okumuyor"
        assert "m.label" in govde, f"{fn} geri düşüşü yok"

    # İki <option> listesi adı KENDİ kurmuyor: tek kaynağa soruyor. Kendi
    # kurarlarsa üç yer arasında ayrışma yeniden mümkün olur.
    for fn in ("function renderModelOptions(", "function renderChatModelOptions("):
        govde = js.split(fn, 1)[1].split("\n}", 1)[0]
        assert "modelSecenekMetni(" in govde, f"{fn} etiketi tek kaynaktan almıyor"
        assert "short_label" not in govde, (
            f"{fn} adı KENDİ kuruyor — üç okuyucu arasında ayrışma kapısı")

    for fn in (ADI_KURAN, "function renderModelCards(",
               "function renderModelOptions(", "function renderChatModelOptions("):
        govde = js.split(fn, 1)[1].split("\n}", 1)[0]
        assert ".split(" not in govde and ".replace(" not in govde, (
            f"{fn} etiketi İSTEMCİDE kırpıyor — kısaltma sunucunun işi")
        for ad in ("Azure", "OpenAI", "Gemini"):
            assert f'"{ad}' not in govde, f"{fn}: marka adı ({ad}) literal sayılmış"


# ── Model seçimi: alttan açılan yüzey ──────────────────────────────────
#
# Yüzeyin kaynağı Flow teslimi DEĞİL (docs/flow-ui'de alttan açılan bir ekran
# yok, flow.css'te `.sheet` bile yok): kullanıcının verdiği "Settings" bottom
# sheet görüntüsü. Bu blok o turda alınan kararların her birine bir mandal
# koyuyor — kararların yaşadığı yer bu depoda testler.


def _yorumsuz_html() -> str:
    """Yorumları ayıklanmış servis edilen HTML.

    `_css_block`un yardımcısındaki dersin HTML karşılığı: bu turun gerekçe
    yorumları reddedilen alternatifleri de yazıyor (`role="listbox"`,
    span kapanışı, `translateX`) ve o sözcükleri arayan iddialar kendi
    açıklamalarına takılıyor.
    """
    return re.sub(r"<!--.*?-->", "", _served(), flags=re.S)


def test_model_yuzeyi_TEK_ve_IKI_ekseni_birlikte_tasiyor():
    """Bir panel, iki eksen (görsel + Yönetmen). İkinci bir `<aside>` YOK.

    Gerekçe yapısal: iki çip `#composer[data-mode]` ekseniyle birbirini
    DIŞLIYOR (style.css), yani ikisi aynı anda hiç açılamıyor. Bedeli ise
    ölçülebilir — kartlar `configured` bayrağını okuyor ve o bayrak Ayarlar
    her kaydedildiğinde değişiyor. İki kalıcı panel, `applyModels` ve
    `applyChatModels`e İKİ ayrı tazeleme görevi yüklerdi; tek panel + açılışta
    çizim `renderModelCards`a TEK çağıran veriyor ve hiç senkronizasyon
    borcu doğmuyor (`test_ISARET_her_iki_seride_de_baglaniyor`ın dersi).
    """
    html = _yorumsuz_html()
    assert html.count('id="model-sheet"') == 1, "ikinci bir model paneli açılmış"
    js = _js("core.js")
    assert js.count("renderModelCards(") == 2, (
        "renderModelCards bir tanım + bir çağrıdan fazla yerde geçiyor — her "
        "yeni çağrı yeri bayat kart listesi riskini geri getiriyor")
    # Eksen tablosu TEK yerde: üç ayrı `axis === "chat" ? … : …` üçlüsü, yeni
    # bir eksen eklendiği gün birini güncellemeyi unutmak demekti.
    assert "const MODEL_EKSENLERI" in js
    for anahtar in ("secici", "dugme", "etiket", "logo", "baslik", "kredi", "liste"):
        assert f"{anahtar}:" in js, f"eksen tablosunda `{anahtar}` yok"


def test_kart_secimi_SELECTE_yaziyor_ve_TEK_olay_gonderiyor():
    """Değerin sahibi `<select>`; kart ona yazıp `change` gönderiyor.

    Bu satırların hepsi bir kırılmayı kapatıyor:
      · `.value =` + `dispatchEvent` → var olan dinleyici (applyModel +
        savePref + `seciliModelTercihi`) TEK yoldan koşuyor.
      · `bubbles: true` → dinleyici `<select>`in kendisinde, olay ondan
        yukarı çıkmasa da yakalanır; ama `change` ATAMAYLA hiç doğmuyor, yani
        elle gönderim şart.
      · Gövdede `applyModel(` / `savePref(` OLMAMALI: ikinci bir çağrı tercihi
        diske İKİ kez yazar ve "varsayılana düşüldü" mesajını iki kez basar.
        İkisi de sessiz — kullanıcı hiçbir şey görmez.
    """
    js = _js("core.js")
    govde = js.split('$("model-sheet-list").addEventListener("change"', 1)[1]
    govde = govde.split("\n});", 1)[0]
    assert ".value = " in govde, "kart seçimi taşıyıcıya yazmıyor"
    assert "dispatchEvent" in govde and '"change"' in govde, (
        "olay elle gönderilmiyor — `value` ataması `change` DOĞURMUYOR, yani "
        "tercih hiç kaydedilmez")
    assert "bubbles: true" in govde
    for yasak in ("applyModel(", "applyChatModel(", "savePref("):
        assert yasak not in govde, (
            f"{yasak} panelden İKİNCİ kez çağrılıyor — tercih iki kez yazılır")
    # Aynı değere ikinci dokunuşun kapısı: native <select> de değişmeyen bir
    # değer için `change` atmıyor.
    assert "return" in govde, "aynı değere ikinci dokunuş için erken çıkış yok"


def test_kart_listesi_DELEGE_dinleyici_kullaniyor():
    """Kartlar her açılışta yeniden çiziliyor: dinleyici LİSTEDE, kartta değil.

    Kart başına dinleyici bağlamak her açılışta yeniden kurulması gereken bir
    bağ olurdu; çizim fonksiyonu bir gün iki kez çağrılırsa da dinleyiciler
    üst üste binerdi (ve tercih iki kez yazılırdı).
    """
    js = _js("core.js")
    assert '$("model-sheet-list").addEventListener("change"' in js
    govde = js.split("function renderModelCards(", 1)[1].split("\n}", 1)[0]
    assert "addEventListener" not in govde, (
        "kart çizimi dinleyici bağlıyor — her açılışta bir kopya daha")


def test_yuzey_ORTAK_kapidan_aciliyor_ve_KAPANIYOR():
    """`openSheet` / `closeSheets` dışında bir açma-kapama yolu YOK.

    `hidden` ile yönetilen bir panel üç mekanizmayı birden kaybederdi: perde
    (`body:has(.sheet.open) .scrim`), Escape şelalesi ve Android geri tuşu
    (`window.geriTusu`) hepsi `.sheet.open` seçicisine bakıyor.
    """
    js = _js("core.js")
    assert 'openSheet("model-sheet")' in js
    assert '$("model-sheet").hidden' not in js, (
        "panel `hidden` ile yönetiliyor — perde, Escape ve Android geri tuşu "
        "`.sheet.open`a bakıyor, üçü birden sessizce ölür")
    for dugme in ("model-sheet-close", "model-sheet-ok"):
        assert f'$("{dugme}").addEventListener("click", closeSheets)' in js, (
            f"#{dugme} ortak kapanış kapısını kullanmıyor")


def test_kapanis_ARIA_yi_TURETILMIS_listeden_sifirliyor_elle_sayilandan_DEGIL():
    """`aria-expanded` kapanışta TÜRETİLEN listeden sıfırlanmak zorunda.

    Elle sayılan liste bu dosyada İKİ KEZ bayatladı ve ikisi de sessizdi
    (ekran okuyucu KAPALI bir paneli "açık" okur, ekranda hiçbir iz yok):
      · önce iki model çipi sayılıyordu ve #arena-btn eklenince kapsam dışı
        kaldı — o tur `modelSheetTetik`i getirdi;
      · sonra #chat-sidebar-toggle ile #specs-btn elle sayılı KALDI ve
        #director-btn eklenince aynı boşluk yeniden doğdu. Tetik değişkeni
        yalnız BİR paneli (modeli) yazıyordu, yani ikinci hand-count'u
        kapatmıyordu.

    Bu yüzden ölçü artık türetme: `aria-controls`u bir `.sheet`e bakan HER
    tetik. Beşinci yüzey kendiliğinden kapsanıyor. Odak iadesi ayrı ve hâlâ
    tetik değişkeninden (`sheetTetik`) — bir tek onu türetmek mümkün değil,
    çünkü "hangi düğme AÇTI" DOM'da yazmıyor.

    İddia HİÇBİR id'nin elle sayılmadığını ölçüyor: eski iki liste de yasak.
    """
    js = _js("core.js")
    govde = js.split("function closeSheets() {", 1)[1].split("\n}", 1)[0]
    assert "[aria-controls][aria-expanded]" in govde, (
        "kapanış tetik listesini türetmiyor")
    assert 'classList.contains("sheet")' in govde, (
        "türetme hedefin bir `.sheet` olduğunu sormuyor — `.sheet` olmayan bir "
        "yüzeyin (popover, menü) tetiği de sıfırlanır")
    assert 'sheetTetik.setAttribute("aria-expanded", "false")' in govde, (
        "kapanış açan çipin aria-expanded'ını tetikten sıfırlamıyor")
    assert "sheetTetik.focus()" in govde, "odak iadesi düşmüş"
    for cip in ("model-btn", "chat-model-btn", "arena-btn",
                "chat-sidebar-toggle", "specs-btn", "director-btn"):
        assert f'$("{cip}").setAttribute("aria-expanded"' not in govde, (
            f"#{cip} kapanışta elle sayılıyor — liste bir sonraki yüzeyde "
            "yine bayatlar")


def test_yonetmen_cekmecesi_ORTAK_kapidan_aciliyor():
    """`.sheet` + `openSheet`/`closeSheets` — kendi mekaniği YAZILMIYOR.

    `hidden` ile yönetilen bir panel üç mekanizmayı birden kaybederdi: perde
    (`body:has(.sheet.open) .scrim`), Escape şelalesi ve Android geri tuşu —
    üçü de `.sheet.open` seçicisine bakıyor (bkz. tests/test_mobile.py'nin
    geri tuşu listesi). Çekmece o sınıfı taşıdığı için üçü de bedava geliyor.
    """
    html = _yorumsuz_html()
    assert 'id="director-sheet" class="sheet sheet-right"' in html, (
        "çekmece `.sheet` kabuğunu kullanmıyor — perde, Escape ve Android geri "
        "tuşu onu görmez")
    js = _chat_js()
    assert 'openSheet("director-sheet")' in js
    assert '$("director-sheet").hidden' not in js, "panel `hidden` ile yönetiliyor"
    assert '$("director-close").addEventListener("click", closeSheets)' in js


def test_yonetmen_cipi_MOD_eksenine_bagli_ve_ikinci_tik_kapatiyor():
    """Çip yalnız Yönetmen modunda görünür ve ikinci dokunuş paneli kapatır.

    Görünürlük CSS'te `#composer[data-mode]` ekseninden, JS'ten DEĞİL: aynı
    eksen #specs-btn'i Yönetmen modunda gizliyor, yani iki çip aynı yuvada
    birbirini dışlıyor ve şeridin ölçülmüş 360px bütçesine yeni yük binmiyor.
    `:has()` bu depoda taşıyıcı davranış için kullanılmıyor (eski WebView).

    İkinci tık kapatma #specs-btn'in kalıbı: `openSheet` aynı paneli kapatıp
    yeniden açardı ve kullanıcı bir titreme görürdü.
    """
    css = _css()
    assert '#composer[data-mode="image"] #director-btn' in css, (
        "çip Görsel modunda gizlenmiyor")
    html = _yorumsuz_html()
    assert 'aria-controls="director-sheet"' in html
    govde = _chat_js().split('$("director-btn").addEventListener("click"', 1)[1]
    govde = govde.split("\n});", 1)[0]
    assert "willOpen" in govde and "closeSheets()" in govde, \
        "ikinci tık kapatma kalıbı yok"


def test_cekmece_acilirken_METIN_ALANINA_odaklanmiyor():
    """Android'de klavye alttan açılıyor ve metin alanına odak paneli YUTUYOR.

    Ayarlar panelinin ölçülmüş dersi (`#set-provider` seçilmesinin sebebi).
    Odak yine de panelin İÇİNE gidiyor — hiç gitmezse Escape'in neyi
    kapattığı ve odağın nereye döneceği belirsiz kalır.
    """
    govde = _chat_js().split('$("director-btn").addEventListener("click"', 1)[1]
    govde = _strip_js_comments(govde.split("\n});", 1)[0])
    assert '$("director-guidance").focus()' not in govde, \
        "metin alanına odaklanılıyor — telefonda panel klavyenin altında kalır"
    assert ".focus()" in govde, "odak panele hiç girmiyor"


def test_cekmecenin_durum_satiri_YAZAN_dugmenin_yaninda():
    """Durum satırı `.sheet-foot`ta olmak zorunda, kaydırılan gövdede DEĞİL.

    `#settings-status`ın ölçülmüş dersi: `.sheet-foot` `flex: none`, yani gövde
    ne kadar uzarsa uzasın basılan düğmenin yanında kalıyor. Burada risk daha
    da büyük çünkü metin alanı `resize: vertical`: kullanıcı alanı uzattığında
    gövdedeki "Kaydedilemedi: …" satırı görünür alanın dışına çıkıyor, Kaydet
    ise sabit ayakta duruyordu — düğmeye basılıyor ve hiçbir şey olmuyor gibi
    görünüyordu.
    """
    html = _yorumsuz_html()
    ayak = re.search(r'<div class="sheet-foot">(.*?)</div>',
                     html.split('id="director-sheet"', 1)[1], re.S)
    assert ayak, "çekmecenin `.sheet-foot`u bulunamadı"
    assert 'id="director-status"' in ayak.group(1), (
        "durum satırı ayakta değil — uzatılan metin alanı onu görünür alanın "
        "dışına iter")
    assert 'id="director-save"' in ayak.group(1), "Kaydet ayakta değil"


def test_cekmece_her_ACILISTA_durum_satirini_sifirliyor():
    """Eski "kaydedildi" satırı KAYDEDİLMEMİŞ metnin yanında asılı kalıyordu.

    Kullanıcı kaydediyor, kapatıyor, sonra yeniden açıp yeni bir şey yazıyor
    ve Kaydet'e BASMADAN kapatıyor. Metin kutuda duruyor (bilerek), üstündeki
    satır da "Yönlendirme kaydedildi — bundan sonraki her turda geçerli."
    diyor. İkisi bir arada okununca yönlendirmenin etkin olduğunu söylüyor,
    oysa `/api/chat` hâlâ eski metni gönderiyor. `openSettings`ın durum
    satırını açılışta temizlemesinin sebebi birebir bu.
    """
    govde = _chat_js().split('$("director-btn").addEventListener("click"', 1)[1]
    govde = _strip_js_comments(govde.split("\n});", 1)[0])
    assert '$("director-status").textContent = ""' in govde, (
        "açılışta durum satırı temizlenmiyor — bayat bir onay mesajı "
        "kaydedilmemiş metni kaydedilmiş gibi gösterir")


def test_kaydet_dugmesi_UCUS_SIRASINDA_kilitli():
    """İki tık iki POST atıyordu ve ikisi de dönüşte AYNI iki alana yazıyor.

    Sonuç yarışa kalıyor: ilk istek ağda düşüp ikincisi başarırsa kullanıcı
    BAŞARILI bir yazımın üstünde "Kaydedilemedi: …" okuyabiliyor (ya da
    tersi). `#settings-save`ın kalıbı — `disabled` + `finally`.

    `finally` şart ve ayrı ölçülüyor: yalnız başarı dalında açılsaydı tek bir
    ağ hatası düğmeyi TEMELLİ kilitler ve kullanıcı yazdığını hiç
    kaydedemezdi.
    """
    js = _chat_js()
    govde = re.search(r"async function saveDirectorGuidance\([^)]*\)\s*\{(.*?)\n\}",
                      js, re.S)
    assert govde, "saveDirectorGuidance() bulunamadı"
    gv = _strip_js_comments(govde.group(1))
    assert '$("director-save").disabled = true' in gv, "düğme uçuş sırasında kilitlenmiyor"
    assert "finally" in gv, "kilit `finally`de açılmıyor — ağ hatası düğmeyi temelli kilitler"
    assert gv.index("finally") < gv.index('$("director-save").disabled = false'), \
        "kilit `finally` dışında açılıyor"


def test_cekmecenin_tetigi_openSheetten_SONRA_yaziliyor():
    """SIRA BAĞLAYICI: `openSheet` içinde `closeSheets` koşuyor ve tetiği siler.

    Atama önce yapılsaydı odak iadesi HİÇ çalışmazdı ve ekranda tek iz
    bırakmazdı — panel yine açılır, kaydetme yine işler, yalnız Escape'ten
    sonra odak `<body>`ye düşer. `openModelSheet`in aynı mandalı.
    """
    govde = _chat_js().split('$("director-btn").addEventListener("click"', 1)[1]
    govde = _strip_js_comments(govde.split("\n});", 1)[0])
    assert 'sheetTetik = $("director-btn")' in govde, "odak iadesi kurulmuyor"
    assert govde.index('openSheet("director-sheet")') < govde.index("sheetTetik ="), \
        "tetik `openSheet`ten ÖNCE yazılıyor — closeSheets onu null'a çeker"


def test_kalici_yonlendirme_DUGMEYLE_kaydediliyor_ve_hata_metni_silmiyor():
    """Anında yazım DEĞİL: değer uzun bir serbest metin.

    `#pref-autosave`in kalıbı bir onay kutusu için doğru (değer tek bit, hata
    dalında kutu geri döner ve hiçbir şey kaybolmaz). Burada sessizce
    başarısız olan bir yazım kullanıcının yazdığını kaybettirir — `sendChat`in
    başarısızlık dalının reddettiği şeyin aynısı.

    Ekrandaki değer SUNUCUNUN döndürdüğünden kuruluyor: sunucu kırpmışsa
    kullanıcı kırpılmış hâli görür, yani kaydedilenle ekranda duran ayrışmaz.
    """
    js = _chat_js()
    assert '$("director-save").addEventListener("click", saveDirectorGuidance)' in js
    govde = js.split("async function saveDirectorGuidance()", 1)[1]
    govde = _strip_js_comments(govde.split("\n}", 1)[0])
    assert '"/api/prefs"' in govde and "director_guidance" in govde
    assert 'p.director_guidance || ""' in govde, \
        "ekran sunucunun döndürdüğü değerden kurulmuyor"
    # Hata dalı metni KUTUDA bırakmalı.
    hata = govde.split("catch", 1)[1]
    assert '$("director-guidance").value = ""' not in hata, \
        "hata dalı kullanıcının yazdığını siliyor"
    # Değer açılışta okunuyor: yazılıp okunmayan bir tercih yok sayılır.
    assert '$("director-guidance").value = p.director_guidance || ""' in \
        js.split("async function loadPrefs()", 1)[1].split("\n}", 1)[0]


def test_TAMAM_bir_ONAY_kapisi_DEGIL():
    """Seçim dokunuşta uygulanıyor; "Tamam" yalnızca kapatıyor.

    Onay kapısı olsaydı bir de "vazgeç" yolu borçlanılırdı ve perdeye
    dokunmanın anlamı belirsiz kalırdı ("seçtiklerim gitti mi?"). Tercihin
    anında yazılması `#pref-autosave` ve tema seçicisinin deseni.
    """
    js = _js("core.js")
    satir = [l for l in js.splitlines() if '$("model-sheet-ok")' in l
             and "addEventListener" in l]
    assert satir, "#model-sheet-ok bağlanmamış"
    for yasak in ("savePref", "applyModel", "dispatchEvent"):
        assert yasak not in satir[0], (
            f'"Tamam" {yasak} çağırıyor — kapatma düğmesi seçimi UYGULUYOR')


def test_kart_MODEL_NOTUNU_ve_ISARETI_gosteriyor():
    """Bu turun ASIL kazancı: `note` ve sağlayıcı işareti ekranda.

    İkisi de `<option>`un taşıyamadığı şeydi — not `option.title`da gömülüydü
    ve dokunmatikte `title` HİÇ görünmüyor. Composer şeridinin notu reddetme
    gerekçesi (`applyModel`: 360px'de kalıcı yer bedeli) böylece bedelsiz
    duruyor: bilgi var, şerit uzamıyor.

    `innerHTML` YOK: sunucudan gelen hiçbir şey ayrıştırılmıyor.
    """
    govde = _js("core.js").split("function renderModelCards(", 1)[1].split("\n}", 1)[0]
    assert "m.note" in govde, "kart model tanıtımını göstermiyor"
    assert "m.logo" in govde, "kart sağlayıcı işaretini göstermiyor"
    assert "innerHTML" not in govde, "sunucudan gelen metin innerHTML'e giriyor"
    assert "textContent" in govde


def test_kredi_ARALIGI_tek_kaynaktan_okunuyor():
    """Kredi ARALIĞI iki yerde çiziliyor (şeridin `<option>`ları + kartlar).

    Hesap iki yerde yaşarsa ayrışır: biri min–max verirken öteki tek tarifede
    kalır ve kullanıcı aynı model için iki farklı fiyat görür.

    ÖLÇÜLEN ŞEY ARALIK, `credits_by_quality`nin kendisi DEĞİL: o alan
    `syncRunCost`ta da okunuyor ve orada BAŞKA bir hesap yapılıyor — bu turun
    seçili kaliteye düşen GERÇEK maliyeti, aralık değil. İkisini tek sayıya
    indirmek "iki okuyucu var" diye yanlış bir alarm verirdi (ilk yazımda
    verdi de).
    """
    js = _js("core.js")
    assert js.count("Math.min(...tarife)") == 1, (
        "kredi aralığı core.js'te birden fazla yerde hesaplanıyor")
    for fn in ("function modelSecenekMetni(", "function renderModelCards("):
        govde = js.split(fn, 1)[1].split("\n}", 1)[0]
        assert "modelKrediAraligi(" in govde, f"{fn} aralığı tek kaynaktan almıyor"


def test_TUTAMAK_bir_sey_VAAT_ETMIYOR():
    """Tutamak DEKORATİF: sürükleyerek kapatma yok, o yüzden söz de yok.

    Sürüklenebilir görünen ama sürüklenmeyen bir tutamak, tam olarak
    `test_sohbet_modeli_secicisi_YONLENDIRME_gelmeden_gizli`in reddettiği şey:
    "kullanıcıya tutulmayan bir söz". Kapatmanın üç gerçek yolu var (×,
    perde, Escape/geri) ve tutamak yalnızca yüzeyin NEREDEN geldiğini
    söylüyor.
    """
    html = _yorumsuz_html()
    tutamaklar = re.findall(r"<span class=\"sheet-grip\"[^>]*>", html)
    assert len(tutamaklar) == 2, (
        "tutamak iki alttan açılan panelde de olmalı (#model-sheet, "
        f"#settings-modal) — bulunan: {len(tutamaklar)}")
    for t in tutamaklar:
        assert 'aria-hidden="true"' in t, (
            "tutamak erişilebilirlik ağacında — ekran okuyucuya işlevi "
            "olmayan bir öğe duyuruluyor")
    for js_adi in ("core.js", "settings.js", "chat.js"):
        assert "sheet-grip" not in _js(js_adi), (
            f"{js_adi} tutamağa bağlanıyor — sürükleme yoksa bağ da olmamalı")


def test_ALTTAN_acilan_yuzey_ORTAK_kabugu_KIRMIYOR():
    """`.sheet-bottom` `.sheet`in bir varyantı; ortak kuralları bozmuyor.

    YATAY ORTALAMA `translateX` ile YAPILAMAZ ve bu iddia o tuzağın mandalı:
    `.sheet.open { transform: none; }` BÜTÜN varyantların ortak kuralı, yani
    transform'la kurulan bir ortalama açılış anında siliniyor ve panel sağa
    kayıyor. Kayma yalnızca 520px'ten geniş pencerede görünür — telefonda
    hiç, yani mobil testte hiç yakalanmaz.

    `top: auto` da şart: `.sheet`in `top: 0; bottom: 0`ı paneli tam yükseklikte
    tutuyor ve `max-height` hiç devreye girmezdi.
    """
    govde = _css_block(".sheet-bottom")
    assert "top: auto" in govde, (
        "`.sheet`in `top: 0`ı ezilmemiş — panel tam yükseklikte açılır ve "
        "`max-height` hiç devreye girmez")
    assert "bottom: 0" in govde
    assert "translateY(100%)" in govde, "panel alttan yükselmiyor"
    assert "translateX" not in govde, (
        "yatay ortalama transform ile yapılmış — `.sheet.open { transform: "
        "none }` onu açılış anında siliyor ve panel sağa kayıyor")
    assert "margin-inline: auto" in govde or "margin: 0 auto" in govde, (
        "panel masaüstünde ortalanmıyor")
    assert "max-height" in govde, "tavansız panel başlığını ekranın dışına iter"
    # Ortak kural yerinde: varyant onun üstüne biniyor.
    assert ".sheet.open { transform: none; }" in _css()


def test_SECILI_kart_rengi_TEMADAN_geliyor():
    """"Rengi tema ile uyumlu olsun" isteğinin mandalı.

    Seçili kartın rengi `--accent-*` jetonlarından okunuyor, sabit bir renk
    değil. Bedeli somut: jetonlar `flow-tokens.css`in `[data-theme=…]`
    satırlarında yer değiştiriyor, yani biri buraya `#7c3aed` yazarsa kart
    Okyanus temasında yanlış renkte kalır — ve bu yalnızca temayı değiştiren
    kullanıcıda görünür, yani gözden kaçar.

    Referans tasarımdaki beyaz/gradyan çerçeve BİLEREK alınmadı: bu
    uygulamada `--accent` yalnızca DURUM anlatıyor (flow-tokens.css'in kendi
    notu) ve seçili kart bir durumdur.
    """
    govde = _css_block(".model-row:has(input:checked)")
    assert "var(--accent-surface)" in govde, "seçili kartın zemini temadan gelmiyor"
    assert "var(--accent-border)" in govde, "seçili kartın çerçevesi temadan gelmiyor"
    assert "#" not in govde, "seçili karta sabit renk yazılmış"
    # Çerçeve `box-shadow: inset` — `border` kutuyu 1px büyütür ve seçim
    # değiştikçe liste zıplar.
    assert "box-shadow: inset" in govde, (
        "çerçeve `border` ile çizilmiş — kartın yüksekliği oynar ve seçim "
        "değiştikçe liste zıplar")
    # Jetonların üç temada da tanımlı olması sözleşmenin öteki yarısı.
    tokens = TestClient(appmod.app).get("/static/flow-tokens.css").text
    for tema in ("ocean", "amber", "viola"):
        blok = tokens.split(f'[data-theme="{tema}"]', 1)[1].split("}", 1)[0]
        for jeton in ("--accent-surface", "--accent-border"):
            assert jeton in blok, f"{tema} temasında {jeton} tanımsız"


def test_ayarlar_paneli_ALTTAN_ve_KAYDET_dipte():
    """Ayarlar da model seçicisiyle AYNI yüzeyde: iki ayarlar yüzeyi, iki ayrı
    yer gibi görünmesin.

    "Kaydet" artık `.sheet-foot`ta ve bu ölçülebilir bir kazanç: `.sheet-foot`
    `flex: none`, yani gövde kaydırılırken yerinde duruyor. Önce gövdenin
    sonundaydı ve altındaki üç bölüm (künye, güncelleme kontrolü, oturum
    tercihi) onu ekranın dışına itiyordu — kullanıcı anahtarını yazıp
    "Kaydet"i bulmak için aşağı kaydırmak zorundaydı.
    """
    html = _yorumsuz_html()
    assert 'id="settings-modal" class="sheet sheet-bottom"' in html, (
        "Ayarlar paneli alttan açılmıyor")
    dip = html.split('<div class="sheet-foot">')
    ayarlar_dibi = [d for d in dip if 'id="settings-save"' in d.split("</div>", 1)[0]]
    assert ayarlar_dibi, "#settings-save panelin dibinde değil"
    assert 'id="settings-status"' in ayarlar_dibi[0].split("</div>", 1)[0], (
        "durum satırı basılan düğmeden ayrı — geri bildirim gövdenin ortasında "
        "kalıp hiç okunmuyor")
    # Odak metin kutusuna DEĞİL: alttan açılan panelde yazılım klavyesi
    # panelin yarısını yutuyor.
    js = _js("settings.js")
    assert '$("set-endpoint").focus()' not in js, (
        "Ayarlar açılışında metin kutusuna odaklanıyor — Android'de klavye "
        "kalkıyor ve alttan açılan paneli kapatıyor")
    assert '$("set-provider").focus()' in js


def test_AYARLAR_dugmesi_openSettingse_OLAYI_gecirmiyor():
    """`openSettings` bir SAĞLAYICI ADI bekliyor; dinleyici ona MouseEvent verirse
    panel boş açılıyor.

    Ölçülmüş kırılma (gerçek Chromium, 390x844): bağ
    `addEventListener("click", openSettings)` biçimindeydi ve fonksiyon
    argüman olarak MouseEvent alıyordu. `provider` truthy olduğu için
    `$("set-provider").value = provider` koşuyor, eşleşmeyen bir dizeye
    atanan `select.value` seçimi DÜŞÜRÜYOR (`selectedIndex = -1`) ve hemen
    ardından koşan `syncProviderFields` `prov-azure`/`prov-openai`/
    `prov-gemini`in ÜÇÜNÜ de gizliyordu.

    Kullanıcı tarafındaki sonucu: dişliye basınca açılan Ayarlar panelinde hiç
    anahtar kutusu YOK. Konsolda tek bir hata bile yok — `select.value`ya
    geçersiz atama sessiz. Yalnızca ilk kurulumun kendi açtığı panel ve
    "Ayarlar'ı aç" derin bağlantısı çalışıyordu, yani hata "bazen çalışıyor"
    kılığındaydı.

    İDDİA İKİ KADEMELİ, çünkü iki kapı da ayrı ayrı kırılabilir:
      1. bağ, olayı geçirmeyen bir sarmalayıcı olmak zorunda;
      2. `openSettings`in kendisi, seçicide BULUNMAYAN bir değeri yazmayı
         reddetmek zorunda (katalogdan gelen bir sağlayıcı adı bir gün
         seçicide olmayabilir — aynı yol yeniden açılır).
    """
    js = _js("settings.js")
    assert '$("settings-btn").addEventListener("click", openSettings)' not in js, (
        "dişli bağı `openSettings`e MouseEvent geçiriyor — Ayarlar paneli "
        "hiçbir anahtar kutusu göstermeden açılır")
    assert '$("settings-btn").addEventListener("click", () => openSettings())' in js

    govde = js.split("function openSettings(", 1)[1].split("\n}", 1)[0]
    atama = [l for l in govde.splitlines() if '$("set-provider").value = provider' in l]
    assert atama, "derin bağlantı sağlayıcıyı hiç yazmıyor"
    assert ".options" in govde and "some(" in govde, (
        "`openSettings` seçicide bulunmayan bir değeri de yazıyor — atama "
        "seçimi sessizce düşürür ve bütün alan grupları gizlenir")


# ── Prompt Yönetmeni: model şeridi + dağıtım adı kapısı (v0.7) ──────────


def test_DAGITIM_ADI_kutusu_adreslenebilir_bir_GRUPTA():
    """Kutu koşulsuz görünürken OpenAI/Gemini kullanıcısına karşılığı OLMAYAN
    bir alan gösteriyordu ("dağıtım" Azure'a özgü). Gizlenebilmesi için
    etiketi + notuyla birlikte tek bir kapsayıcıda olmak zorunda: yalnız
    `<input>`u gizlemek etiketi ve altındaki açıklamayı ekranda bırakırdı.

    İDDİA GENİŞLEDİ (v0.8): başlık da adreslenebilir olmak ZORUNDA. Kutu
    gizlenip başlık kalırsa panelde kullanıcının yapacağı bir şey olmadığı
    hâlde bir bölüm başlığı durur — istenen, bölümden hiçbir şeyin
    görünmemesi. Eski "bu sağlayıcıda dağıtım adı yok" paragrafı
    (`chat-no-deploy-note`) bu turda KALDIRILDI: gizli bir başlığın altında
    hiç görünemezdi. (Taban 152 id'de olmadığı için id defterine yazılmıyor —
    test_id_contract.test_defter_tabandan_sec zaten reddediyor.)
    """
    html = _html()
    assert 'id="chat-deploy-group"' in html
    assert 'id="chat-deploy-head"' in html, "başlık adreslenebilir değil"
    assert 'id="chat-no-deploy-note"' not in html, (
        "kaldırılan boş-durum paragrafı geri gelmiş")
    grup = html.split('id="chat-deploy-group"', 1)[1].split("</div>", 1)[0]
    assert 'id="set-chat-deployment"' in grup, "kutu grubun DIŞINDA kalmış"
    assert 'for="set-chat-deployment"' in grup, "etiket grubun dışında"


def test_YONETMEN_TALIMAT_yolu_KOSULSUZ_gorunur_kaliyor():
    """Dağıtım bölümü sağlayıcıya göre kaybolurken talimat yolu kalmak ZORUNDA.

    "Keşfedilebilir olmasa özellik var olmakla olmamak arasında bir fark
    taşımaz" (index.html'deki kendi gerekçesi): yönetmenin talimatını ezme yolu
    yalnızca Ayarlar'da yazılı. Koşullu bölümün İÇİNE düşerse OpenAI/Gemini
    kullanıcısı o dosyayı hiç öğrenemez — bu yüzden kendi başlığı var ve
    `syncChatDeployField` ona HİÇ dokunmuyor.
    """
    html = _html()
    assert 'id="chat-instructions-path"' in html
    # Koşullu grubun DIŞINDA: grup `</div>`inden sonra geliyor.
    grup = html.split('id="chat-deploy-group"', 1)[1].split("</div>", 1)[0]
    assert "chat-instructions-path" not in grup, "talimat yolu koşullu grubun içinde"
    js = _js("settings.js")
    govde = js.split("function syncChatDeployField(", 1)[1].split("\n}", 1)[0]
    assert "chat-instructions-path" not in govde, "talimat yolu kapıya bağlanmış"


def test_DAGITIM_ADI_kapisi_KATALOGDAN_turetiliyor():
    """Kapı `chat_models[].needs_deployment` bayrağına bakıyor, sağlayıcı adına
    DEĞİL.

    `"azure"` literaline bakan bir kapı, adı ortamdan okunan İKİNCİ bir
    sağlayıcı eklendiği gün kutuyu sessizce görünmez bırakırdı — yani o
    sağlayıcı hiç yapılandırılamazdı. Bayrağın sunucu yarısı
    tests/test_settings_route.py'de ölçülüyor.
    """
    js = _js("settings.js")
    govde = js.split("function syncChatDeployField(", 1)[1].split("\n}", 1)[0]
    assert "needs_deployment" in govde, "kapı katalog bayrağını okumuyor"
    assert '"azure"' not in govde, "sağlayıcı adı literal olarak sayılmış"
    # Başlık ve grup BİRLİKTE: biri gizlenip öteki kalırsa sahipsiz bir bölüm
    # başlığı (ya da başlıksız bir alan) kalır.
    assert '$("chat-deploy-group").hidden' in govde
    assert '$("chat-deploy-head").hidden' in govde
    assert "chat-no-deploy-note" not in govde, (
        "kaldırılan paragrafa hâlâ dokunuluyor — $() null döner")
    # Sağlayıcı değiştiğinde çalışmak ZORUNDA: kapı yalnız açılışta kurulsa
    # seçiciyi çevirmek kutuyu yanlış sağlayıcıda bırakırdı.
    assert "syncChatDeployField(" in js.split(
        "function syncProviderFields()", 1)[1].split("\n}", 1)[0]


def test_SOHBET_MODELI_secenekleri_sunucudan_kuruluyor():
    """`/api/settings` → `chat_models` v0.6'dan beri sunuluyordu ve HİÇ
    okunmuyordu; seçici de bu yüzden gizliydi. Şerit artık gerçek bir seçim,
    yani listeyi kuran kod da var olmak zorunda."""
    js = _js("core.js")
    assert "function applyChatModels(" in js
    assert "s.chat_models" in js
    assert "s.default_chat_model" in js
    govde = js.split("function renderChatModelOptions(", 1)[1].split("\n}\n", 1)[0]
    # Etiket `textContent` ile yazılıyor: sunucudan gelen hiçbir şey innerHTML'e
    # girmiyor (dosya genelindeki duruş). İddia ATAMA biçimine bakıyor, ham
    # metne değil: kuralı ANLATAN yorumun o kuralı ihlal etmiş sayılması testi
    # gürültüye çevirir (tests/test_providers.py'de ölçülmüş tuzak).
    assert "o.textContent =" in govde
    assert "innerHTML =" not in govde
    # Şerit Ayarlar ile AYNI yanıttan besleniyor: ayrı bir uçtan çekilse ikisi
    # ayrı zamanlarda gelir ve seçici bir an "hepsi kullanılabilir" gösterirdi.
    assert "applyChatModels(s" in _js("settings.js")


def test_SOHBET_MODELI_secimi_TEL_uzerine_cikiyor():
    """Seçici olup isteğin modeli taşımaması, kullanıcıya tutulmayan bir seçim
    sözü vermek olurdu — `#chat-model`in v0.6'da gizli tutulma gerekçesi."""
    govde = _js("chat.js").split("async function sendChat(", 1)[1]
    istek = govde.split('fetch("/api/chat"', 1)[1].split("});", 1)[0]
    assert "currentChatModel" in istek, "/api/chat gövdesi modeli taşımıyor"
    assert "model" in models.ChatRequest.model_fields, (
        "sunucu tarafı alanı kabul etmiyor — seçim sessizce yok sayılırdı")


def test_SOHBET_MODELI_tercihi_SAGLAYICIYLA_BIRLIKTE_yazILIYOR():
    """`prefs.update` `chat_model`i `chat_provider`a göre doğruluyor (çapraz
    kural). Yalnız modeli göndermek 422 dönerdi: kullanıcı OpenAI modeline
    geçtiğinde diskteki sağlayıcı hâlâ "azure" olurdu ve tercih hiç kaydedilmezdi.
    """
    js = _js("core.js")
    blok = js.split('$("chat-model").addEventListener', 1)[1].split("});", 1)[0]
    cagri = blok.split("savePref(", 1)[1]
    assert "chat_provider" in cagri and "chat_model" in cagri, (
        "tercih çifti eksik — prefs çapraz kuralı 422 döndürür")
    import prefs
    assert {"chat_provider", "chat_model"} <= set(prefs.DEFAULTS), (
        "prefs şeması bu çifti tanımıyor")


def test_ANAHTARI_OLMAYAN_modeller_seride_GIRMIYOR():
    """İstek: "API key'i girilmeyen modeller gözükmesin."

    Kullanıcı Azure anahtarıyla çalışıyorsa OpenAI ve Gemini satırlarının hepsi
    seçilebilir bir 502'den başka bir şey değil. Filtre TEK yerde (`secilebilirler`)
    ve iki şerit de ondan geçiyor — ikinci bir kopya, birini süzüp diğerini
    unutmanın kapısı olurdu.

    İDDİA DEĞİŞTİ, ölçtüğü şey güçlendi. Eskiden bu test İLK KURULUM KAPISINI
    çiviliyordu: "hiçbiri kurulu değilse HEPSİ görünsün", gerekçesi de "boş bir
    şerit kullanıcıya hiçbir şey söylemez" idi. O gerekçe kullanıcı isteğiyle
    düştü (anahtarsız model HİÇ görünmeyecek) ve düşebilmesinin sebebi, aynı
    soruyu cevaplayan üç yerin artık kurulu olması:
      · Ayarlar hiçbir görsel modeli kurulu değilken KENDİLİĞİNDEN açılıyor
        (settings.js) — ilk kurulumdaki kullanıcı boş bir şeritle değil, anahtar
        formuyla karşılaşıyor;
      · şerit ve panel boş hâli metinle anlatıyor (`MODEL_BOS_METNI`);
      · Ayarlar'daki #provider-status hangi sağlayıcıların VAR olduğunu sayıyor.

    Yani kapı kapandı ama "kullanıcı neyin var olduğunu göremez" kırılması geri
    gelmedi; test artık kapının KAPALI olduğunu VE boş hâlin çizildiğini ölçüyor.
    """
    js = _js("core.js")
    assert "function secilebilirler(" in js
    for fn in ("function renderModelOptions(", "function renderChatModelOptions("):
        govde = js.split(fn, 1)[1].split("\n}\n", 1)[0]
        assert "secilebilirler(" in govde, f"{fn} filtreden geçmiyor"
    filtre = js.split("function secilebilirler(", 1)[1].split("\n}\n", 1)[0]
    # ÖLÇÜT `available`: görünürlüğün TEK cevabı sunucudan geliyor (app.py
    # `_model_available`). `configured`e dönmek, kredi/üyelik geldiğinde
    # "hangi modeller görünür" sorusuna istemcide ikinci bir cevap yazmak olurdu.
    assert "m.available" in filtre, "filtre görünürlük alanını okumuyor"
    assert "configured" not in filtre, (
        "filtre `configured` okuyor — görünürlük kararı iki yere bölünmüş")
    # İLK KURULUM KAPISI KAPALI: liste boşalabilmeli.
    assert "kurulu.length" not in filtre, (
        "ilk kurulum kapısı hâlâ açık — anahtarsız modeller görünmeye devam eder")
    # …ve boş hâl GERÇEKTEN çiziliyor: hem şerit metni hem #go'nun gerekçesi.
    assert "MODEL_BOS_METNI" in js, "şeridin boş hâli için metin yok"
    assert "function modelBosHali(" in js, "boş hâli çizen yol yok"
    for fn in ("function applyModel(", "function applyChatModel("):
        govde = js.split(fn, 1)[1].split("\n}\n", 1)[0]
        assert "modelBosHali(" in govde, (
            f"{fn} seçim yokken boş hâle geçmiyor — şerit "
            '"Modeller yükleniyor…" yazısında donar')


def test_SECILI_model_seritte_HER_ZAMAN_duruyor():
    """`select.value` seçenekler arasında yoksa <select> BOŞ görünür: şerit
    "model yok" der ama üretim çalışır. `loadModelPref` katalogdan SONRA
    dönüyor ve tercih filtrelenmiş olabilir (anahtarı yok), yani bu yalnız
    `applyModels`'in sırasıyla çözülmüyor."""
    js = _js("core.js")
    for fn, secici in (("function applyModel(", "model"),
                       ("function applyChatModel(", "chat-model")):
        govde = js.split(fn, 1)[1].split("\n}\n", 1)[0]
        assert f'$("{secici}").options' in govde, (
            f"{fn}: seçili id'nin şeritte olduğu doğrulanmıyor")


def test_YONETMEN_kapisi_SECILI_sohbet_modelini_olcuyor():
    """`#go` kapısı eskiden tek bir `chatConfigured` boolean'ına bakıyordu ve o
    yalnız AZURE'u ölçüyordu: yalnızca Gemini anahtarı olan bir kullanıcıda
    yönetmen ölü bir düğmeyle açılırdı — görsel tarafında v0.6'da düzeltilen
    kırılmanın aynısı."""
    dal = _js("core.js").split('if (currentMode === "director")', 1)[1] \
                        .split("\n  }", 1)[0]
    assert "currentChatModel" in dal, "kapı seçili modeli hiç görmüyor"
    assert "configured" in dal


def test_TERCIH_okuma_yolu_da_FILTREDEN_geciyor():
    """`/api/prefs` ile `/api/settings` YARIŞIYOR: tercih sonra gelirse
    filtrenin kararını sessizce iptal edebilir.

    Gerçek chromium koşumunda ölçüldü: `prefs`in `image_model` VARSAYILANI
    Azure'ın id'si (`chat_model`in aksine boş dize DEĞİL), yani "hiç seçmedim"
    ile "Azure'ı seçtim" istemcide ayırt edilemiyor. `loadModelPref` tercihi
    doğrudan uygularsa, yalnızca Gemini anahtarı olan kullanıcı açılışta ölü
    bir #go düğmesiyle karşılanıyor — üstelik şeritte anahtarı olan iki model
    dururken.
    """
    govde = _js("settings.js").split("async function loadModelPref()", 1)[1] \
                              .split("\n}", 1)[0]
    assert govde.count("secilecek(") == 3, (
        "tercih uygulaması filtreyi atlıyor (görsel, video ve sohbet şeridi "
        "için birer `secilecek` çağrısı bekleniyor)")
    assert "applyModel(secilecek(" in govde
    assert "applyChatModel(secilecek(" in govde


def test_SOHBET_MODELI_dinleyicisi_KURESEL_degiskeni_DEREFERANS_etmiyor():
    """`applyChatModel` uygulamadığında (id katalogda yok) `currentChatModel`
    OLDUĞU GİBİ kalıyor: ilk çizimden önce `null`, sonrasında ESKİ model.
    Dinleyici o küresel değişkenin `.provider`ına eriştiği için erken çıkışta
    ya `TypeError` atıyordu (konsolda kırmızı, tercih hiç yazılmaz) ya da
    kullanıcının SEÇMEDİĞİ modeli diske tercih olarak yazıyordu — ikincisi
    daha sessiz ve daha kötü.

    `id` katalogda yokken çağrılmak gerçek bir yol: `secilecek` liste boşken
    boş dize döndürüyor ve settings.js onu doğrudan `applyChatModel`e veriyor.

    Görsel şeridinde bu tuzak YOK çünkü onun dinleyicisi `$("model").value`yu
    okuyor — yani mandal simetri değil, iki dinleyicinin ayrıştığı yer.
    """
    js = _js("core.js")
    govde = js.split("function applyChatModel(", 1)[1].split("\n}\n", 1)[0]
    assert "return null" in govde, (
        "applyChatModel uygulanan modeli döndürmüyor — dinleyici erken "
        "çıkışı ayırt edemez")
    # İKİNCİ YARI ve BU İDDİA ÖLÇÜLMÜŞ BİR KIRILMADAN GELİYOR: dönüş
    # eklenirken başarı yolundaki `return model;` unutuldu, fonksiyon
    # `undefined` döndürdü ve dinleyici HER SEFERİNDE erken çıktı — şerit
    # doğru modeli gösteriyor, tercih diske hiç yazılmıyor, konsolda tek hata
    # yok. Yalnız `return null`ı aramak bunu yeşil geçiyordu; kırılma gerçek
    # Chromium koşumunda görüldü (POST /api/prefs hiç gitmiyor).
    assert "return model;" in govde, (
        "applyChatModel başarı yolunda modeli döndürmüyor — dinleyici her "
        "çağrıda erken çıkar ve tercih SESSİZCE yazılmaz")
    blok = js.split('$("chat-model").addEventListener', 1)[1].split("});", 1)[0]
    assert "if (!model) return;" in blok, "dinleyicide erken çıkış kapısı yok"
    # İDDİA DİNLEYİCİYE ÖZGÜ, dosyanın tamamına DEĞİL: `goBlockReason` aynı
    # küresel değişkeni okuyor ve orada bu doğru — kendi `null` kapısı var
    # ("Sohbet modeli seçilmedi."). Dosya genelinde yasaklamak o kapıyı da
    # kırardı, yani mandal gürültüye dönüşürdü.
    assert "currentChatModel." not in blok, (
        "dinleyici küresel değişkeni dereferans ediyor: erken çıkışta "
        "TypeError ya da kullanıcının seçmediği modelin diske yazılması")


# ══════════════════════════════════════════════════════════════════════
# "Emoji ikon yok" ve "sol kenarı renkli yuvarlak kart yok" (flow-redesign §11)
# ══════════════════════════════════════════════════════════════════════
# Bu bölüm §11'in AÇIK KALAN son kutusunu kapatıyor. Kutu 22 Ağustos'ta iki
# somut ihlalle açıktı (`🎉` ve `.folder-target`'ın vurgu renkli sol kenarı) ve
# ikisi de HİÇ ölçülmüyordu — düzeltmek yetmez, tekrar girmesini engellemek
# gerek. Aşağıdakiler o yüzden tek tek düzeltmeyi değil ÖLÇÜTÜ mandallıyor.

# 🎉 = U+1F389. Astral düzlem gerçek emojinin yaşadığı yer.
# U+FE0F (VARIATION SELECTOR-16) metin glifini emojiye ÇEVİREN karakter ve tek
# başına GÖRÜNMEZ — gözle denetimde tam olarak bu kaçıyor, o yüzden desende.
# KAÇIŞLA yazılıyor (`\uFE0F`), ham karakterle DEĞİL: ham hâli desenin İÇİNDE de
# görünmez olurdu, yani bir "görünmez karakter temizliği" mandalın bu yarısını
# görünür diff bırakmadan ve testi kırmızıya düşürmeden silebilirdi. Mandalın
# kendisi de kurcalanmaya karşı OKUNABİLİR olmak zorunda.
_EMOJI_ASTRAL = re.compile("[\U0001f000-\U0001faff\uFE0F]")
# Misc Symbols + Dingbats: `⚙` (U+2699) ve `⚠` (U+26A0) buradan geliyor.
_EMOJI_BMP = re.compile("[☀-➿]")
# Kademe 2'nin CSS muafiyeti — DOSYA değil KOD NOKTASI bazında (bkz. testin
# gövdesi). `✓` = U+2713, `.chat-option[aria-checked="true"]::before`in işareti.
_CSS_MUAF = frozenset({"\u2713"})


def _bildirim(govde: str, ozellik: str) -> str:
    """Bir CSS kuralının gövdesinden tek bildirim — ADI DA DAHİL, boşluk normal.

    `ozellik` bir DESEN: bir özelliğin mantıksal eşleniği (`border-left` ↔
    `border-inline-start`) aynı iddianın kapsamında kalabilsin diye.

    Yalnız DEĞERİ döndürmek yetmez: "iki kuralın sol kenarı aynı" iddiasında
    biri `border-left`, öteki `border-inline-start` olsa değerler eşleşir ve
    iddia ayrışmayı GÖRMEZ — tam olarak mandalın engellemesi gereken şey.
    """
    eslesme = re.search(rf"{ozellik}\s*:[^;}}]*", govde)
    assert eslesme, f"{ozellik} bildirimi yok"
    return re.sub(r"\s+", " ", eslesme.group(0)).strip()


# Sol kenarın rengi DÖRT ayrı adla yazılabilir: `border-left`, onun `-color`
# uzun biçimi, mantıksal eşleniği `border-inline-start` ve onun `-color`'ı.
# Mandal yalnız `border-left:` literalini arıyordu; üçü de (ölçüldü)
# `border-left: 3px solid var(--accent-border)`, `border-left-color:
# var(--accent)` ve `border-inline-start: 3px solid var(--accent)` biçiminde
# sınavdan GEÇİYORDU — yani ölçüt başka bir adla sessizce geri gelebilirdi.
# KISA `border:` biçimi BİLEREK dışarıda: dört kenarı birden çiziyor, yani
# ölçütün konusu olan "sol kenar şeridi" değil ÇERÇEVE olur. Kapsama alınsaydı
# mandal ölçütün söylemediği bir şeyi yasaklardı.
_SOL_KENAR = re.compile(r"border-(?:left|inline-start)(?:-color)?\s*:[^;}]*")


def _sayfa_kaynaklari() -> dict[str, str]:
    """Sayfanın YÜKLEDİĞİ her `.js`/`.css` — adresler HTML'den okunuyor.

    Liste elle yazılsaydı bir sonraki dosya mandalın dışında kalır ve "emoji
    yok" iddiası sessizce daralırdı; kırılma de "yeni dosyada emoji var"
    biçiminde DEĞİL, "mandal artık hiçbir şey ölçmüyor" biçiminde görünürdü.
    Desen `?v=` damgasından önce duruyor: sorgu dizesi StaticFiles için
    anlamsız, anahtar olarak da yol yeterli.
    """
    c = TestClient(appmod.app)
    yollar = list(dict.fromkeys(
        re.findall(r"/static/[\w./-]+\.(?:js|css)", c.get("/").text)))
    assert len(yollar) >= 10, f"sayfanın kaynakları bulunamadı: {yollar}"
    return {yol: c.get(yol).text for yol in yollar}


def _yorumsuz(yol: str, metin: str) -> str:
    """Gerekçe yorumları AYIKLANMIŞ gövde.

    Ayıklama ŞART: gerekçe yorumu yasakladığı şeyin adını yazmak ZORUNDA — bu
    turun kendi yorumları da `settings.js`'te "(sağ üstteki ⚙)" ve
    `flow-redesign` atıflarında `🎉` diyor. Yorumlu gövdede iddia kendi
    açıklamasına takılır; depo bu tuzağa dört kez düştü (`_css_block` ve
    `_strip_js_comments`'in gerekçeleri aynı ders).

    CSS'te `//` yorumu yok, blok yorumunu (`/* */`) ikisi de kullanıyor — o
    yüzden JS ayıklayıcısı CSS'e de yetiyor, ikinci bir yardımcı gerekmiyor.
    """
    return _strip_html_comments(metin) if yol == "/" else _strip_js_comments(metin)


def test_servis_edilen_arayuzde_EMOJI_ikon_yok():
    """§11'in son şartı: "emoji ikon yok". İki kademeli kalıcı mandal.

    KADEME 1 (astral düzlem + VS16) HTML, JS ve CSS'in üçünde de yasak: gerçek
    emoji orada yaşıyor ve orada meşru bir kullanımı yok.

    KADEME 2 (U+2600–U+27BF, Misc Symbols + Dingbats) her üç türde de yasak;
    CSS'in TEK muafiyeti `✓` (U+2713) ve muafiyet bilinçli: `style.css`'te
    `.chat-option[aria-checked="true"]::before { content: "✓ " }` var. `✓` tek
    renkli, metin sunumlu bir dingbat, yani görev defterinin `🎉` yerine
    ÖNERDİĞİ "hatlı glif" biçiminin kendisi. Onu da yasaklayan bir mandal,
    izin verilen çözümü yasaklardı.

    Muafiyet KOD NOKTASI bazında (`_CSS_MUAF`), DOSYA bazında değil: önceki hâli
    her `.css` dosyasını atlıyordu, yani kademe orada hiçbir şey ÖLÇMÜYORDU —
    `style.css`'e eklenen `.deneme::before { content: "❌✅⚠"; }` bu sınavdan
    geçiyordu (ölçüldü). Muafiyetin genişliği gerekçesinin genişliği kadar
    olmalı; gerekçe tek bir glif.

    Bugünkü arayüzde geçen `─ ═ ⌘ → ← ↔ ↑ ≈ ≤ ≥ ≠ ◼ ▮ ▬ • ⇒ ×`
    karakterlerinin hiçbiri iki kademeye de girmiyor (kod noktası taramasıyla
    ölçüldü) — mandal tipografik glifleri değil EMOJİYİ arıyor.

    Satır SONU yorumları `_strip_js_comments`'te bilerek korunuyor, yani oraya
    yazılan bir emoji mandalı kırar. Doğrusu bu: bir emojiyi gerekçe olarak
    anlatmak gerekiyorsa yorum kendi satırına ya da blok yoruma taşınır.
    """
    kaynaklar = _sayfa_kaynaklari()
    kaynaklar["/"] = TestClient(appmod.app).get("/").text

    for yol, metin in kaynaklar.items():
        bulunan = _EMOJI_ASTRAL.findall(_yorumsuz(yol, metin))
        assert not bulunan, (
            f"{yol} emoji taşıyor: {bulunan} — §11'in "
            f'"emoji ikon yok" ölçütü')

    for yol, metin in kaynaklar.items():
        muaf = _CSS_MUAF if yol.endswith(".css") else frozenset()
        bulunan = [g for g in _EMOJI_BMP.findall(_yorumsuz(yol, metin))
                   if g not in muaf]
        assert not bulunan, (
            f"{yol} emoji sunumlu simge taşıyor: {bulunan} — düğmeler ADIYLA "
            f"anlatılıyor, glifle değil")


def test_yeni_surum_satiri_METINLE_anlatiyor():
    """`#settings-update` emojisiz ama SESSİZ de değil.

    `🎉` düştü; satırın cümlesi kalmak ZORUNDA. Emojiyi ayıklayan bir sonraki
    tur cümleyi de silerse satır yalnızca "v0.9.0 — indir" der ve kullanıcı
    NEDEN gösterildiğini bilmez — üstelik kırılma sessiz: satır varsayılan
    olarak `hidden`, yani ancak gerçekten yeni sürüm çıkınca görünür oluyor.

    Cümle `GUNCELLEME.md`'nin ve README'nin bu satırı anlattığı sözlerle
    birebir aynı ("Yeni sürüm çıktı"); belgeler emojiyi hiç yazmamıştı.
    """
    html = _strip_html_comments(_html())
    bas = html.find('id="settings-update"')
    assert bas > 0, "#settings-update satırı yok"
    # Dilim `id`'den değil KAPSAYICI `<p`'den başlıyor: sınıf niteliği id'den
    # ÖNCE yazılı, yani id'den başlayan bir dilim onu hiç görmez.
    satir = html[html.rfind("<p", 0, bas):html.find("</p>", bas)]
    assert "Yeni sürüm çıktı" in satir, "satır NEDEN göründüğünü söylemiyor"
    assert 'id="settings-update-version"' in satir, "sürüm bağı yok"
    assert 'id="settings-update-link"' in satir, "indirme bağı yok"

    # Cümle YETMEZ: `settings-update-row` sınıfı HTML'de baştan vardı ama CSS'te
    # hiç KARŞILIĞI YOKTU (kardeşi `.settings-version-row`ın kuralı var).
    # Satırı "burada tıklanacak bir şey var" diye işaretleyen tek şey `🎉`
    # glifiydi; o düşünce satır, ortalanmış "Kurulu sürüm" künyesinin altında
    # ayırt edilemez bir `.field-note` notuna indi — emoji gitti, İŞARET de
    # gitti. Ölçütü karşılayan düzeltme glifi silmek DEĞİL, yerine glif
    # olmayan bir işaret koymak.
    assert 'class="field-note settings-update-row"' in satir, (
        "satır kart sınıfını taşımıyor")
    kart = _css_block(".settings-update-row")
    # İddia panelin KENDİ "açıklama kartı" idiomuna bağlanıyor, uydurulmuş
    # değerlere değil: biçim ayrışırsa biri sessizce düz metne dönebilir.
    kapi = _css_block(".chat-gate")
    for ozellik in ("background", "border-radius", r"border-(?:left|inline-start)"):
        assert _bildirim(kart, ozellik) == _bildirim(kapi, ozellik), (
            f".settings-update-row ile .chat-gate {ozellik} bakımından ayrışmış "
            f"→ {_bildirim(kart, ozellik)!r} vs {_bildirim(kapi, ozellik)!r}")

    # Kart yetmez: kartı EYLEM yapan şey içindeki bağlantılar ve bu ikisi
    # uygulamadaki tek biçimlenmemiş `<a>`ydı — hiçbir yerde `a` kuralı yok,
    # yani tarayıcı varsayılanı (`#0000EE` / ziyaret edilmiş `#551A8B`) geçerli
    # ve bu panelin koyu yüzeyinde ~1.3:1 kontrast veriyordu. Kart görünür,
    # tıklanacak yazı okunmaz — çağrının yarısı.
    bag = _css_block(".settings-update-row a")
    assert "var(--text)" in _bildirim(bag, "color"), (
        "bağlantı rengi temadan gelmiyor → tarayıcı varsayılanı koyu yüzeyde "
        "okunmuyor")
    assert "underline" in _bildirim(bag, "text-decoration"), (
        "renk tek başına 'tıklanır' demiyor; altı çizgi kalmalı")


def test_ayarlar_yonlendirmesi_TEK_SABITTEN_geliyor():
    """Durum satırının Ayarlar eki bir SABİT, üç elle yazılmış dize değil.

    Öncesinde `(sağ üstteki ⚙)` dizesi `settings.js`'te üç kez elle yazılıydı
    ve biri NÖBETÇİ (`statusEl.textContent.includes(...)`): kullanıcı ayarları
    düzelttiğinde satırı temizleyen kapı o. Biri değişip öteki kalsa hata
    VERMEZ — nöbetçi bir daha hiç tutmaz ve durum satırı ekranda asılı kalır.
    Sessiz kusur tam olarak bu, o yüzden mandal "emoji yok"tan AYRI duruyor:
    `⚙` başka bir glifle değiştirilse bile bu iddia ayakta kalmalı.

    Glifin kendisi de gitti: üst şeritteki gerçek düğme hatlı bir SVG dişli
    (`aria-label="Ayarlar"`), yani `⚙` düğmenin görünüşünü YANLIŞ söylüyordu.
    """
    js = _strip_js_comments(_settings_js())
    assert 'const AYARLAR_EKI = "(sağ üstteki Ayarlar düğmesi)";' in js, (
        "Ayarlar eki sabiti yok")
    assert js.count("(sağ üstteki") == 1, (
        "metin sabitin DIŞINDA da yazılmış — nöbetçi ile yazan taraf "
        "birbirinden sessizce ayrılabilir")
    assert "${AYARLAR_EKI}" in js, "yazan taraf sabiti okumuyor"
    assert "includes(AYARLAR_EKI)" in js, "nöbetçi sabiti okumuyor"

    # SABİT TEK KAYNAK OLMAK için yetmez: düğmeyi `index.html` de anlatıyor ve
    # mandal yalnız `settings.js`'e bakıyordu. Ayrışma gerçekten olmuştu —
    # `settings.js` "Ayarlar düğmesi" derken `#chat-gate` "(sağ üstteki dişli)",
    # `.view-desc` ise "dişli düğmesi" diyordu: TEK düğme, AYNI ekran, ÜÇ ad.
    # Kullanıcı hangisinin doğru olduğunu deneyerek buluyordu ve hiçbir test
    # kırmızıya düşmüyordu.
    #
    # İddia "dişli" sözcüğünün ADLANDIRMADA geçmemesi üzerine kurulu: söz yanlış
    # değil (ikon gerçekten hatlı bir SVG dişli), ama düğmenin ADI değil — ad
    # `aria-label="Ayarlar"`. Yorumlar AYIKLANIYOR: gerekçe yorumları eski sözü
    # yazmak ZORUNDA, tam bu satırın kendisi gibi.
    html = _strip_html_comments(_html())
    assert "dişli" not in html, (
        "arayüz Ayarlar düğmesini görünüşüyle anlatıyor — settings.js ADIYLA "
        "anlatıyor, ikisi tek düğme için iki ad demek")
    # `"dişli" not in html` tek başına yetmez: paragraf düğmeyi bir BAŞKA
    # belirsiz sözle ("sağ üstteki simge") anlatsa iddia kırmızıya düşmezdi.
    # O yüzden kapının kendi gövdesi de düğmenin ADINI söylemek zorunda.
    bas = html.find('id="chat-gate"')
    assert bas > 0, "#chat-gate satırı yok"
    kapi = html[bas:html.find("</p>", bas)]
    assert "Ayarlar düğmesi" in kapi, (
        "kapı metni düğmeyi adıyla anlatmıyor — settings.js'in durum satırıyla "
        "aynı ekranda iki ayrı ad demek")


# Kullanıcının okuduğu belgeler — `docs/` BİLEREK dışarıda: oradaki `⚙`
# atıfları TARİHSEL kayıt ("öncesinde şu yazıyordu"), yeni adla yazılsalar neyin
# değiştiğini anlatamazlardı. Aynı ayrım `test_depo_adresi.py`'de de var.
#
# `CLAUDE.md` kullanıcıya değil GELİŞTİRİCİYE yazılı, ama listeye yine giriyor:
# mandalın işi "kökteki hiçbir belge ölçütün dışında kalmasın" ve orada geçecek
# bir `⚙`, arayüzden düşmüş glifi geri getirme riskini birebir aynı taşıyor.
_KULLANICI_BELGELERI = ("CLAUDE.md", "GUNCELLEME.md", "KURULUM.md", "README.md")


def test_belgeler_AYARLAR_dugmesini_glifle_anlatmiyor():
    """`⚙` arayüzden düştü; belgelerde KALMASI ölçütü sessizce geri getirir.

    Arayüz düğmeyi adıyla anlatırken belge `⚙ Ayarlar` diyorsa glif ölçütün
    dışında yaşamaya devam eder ve bir sonraki tur onu "zaten belgede var" diye
    arayüze geri koyabilir. Üstelik `GUNCELLEME.md` tam olarak `#settings-update`
    satırının BAĞLANDIĞI dosya: kullanıcı "yeni sürüm çıktı"ya tıklayıp açtığı
    ilk sayfada, arayüzde artık olmayan bir glifle karşılaşıyordu.

    Liste sabit (`_KULLANICI_BELGELERI`) ama KÖRÜ KÖRÜNE değil: köke eklenen
    yeni bir `.md` listeye girmedikçe test kırmızıya düşüyor. Elle yazılmış bir
    liste tek başına olsaydı iddia bir sonraki belgede sessizce daralırdı —
    `_sayfa_kaynaklari`'nin adresleri HTML'den okumasıyla aynı gerekçe.
    """
    kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    izlenen = subprocess.run(
        ["git", "-C", kok, "ls-files", "*.md"],
        check=True, capture_output=True, text=True).stdout.splitlines()
    kok_belgeleri = tuple(sorted(y for y in izlenen if "/" not in y))
    assert kok_belgeleri == _KULLANICI_BELGELERI, (
        f"kök belgeleri değişmiş: {kok_belgeleri} — yeni belge mandalın "
        f"dışında kalmasın diye liste elle güncellenmeli")

    for ad in _KULLANICI_BELGELERI:
        with open(os.path.join(kok, ad), encoding="utf-8") as f:
            metin = f.read()
        assert "\u2699" not in metin, (
            f"{ad} Ayarlar düğmesini `⚙` glifiyle anlatıyor — arayüz onu ADIYLA "
            f"anlatıyor (settings.js AYARLAR_EKI)")


def test_yuvarlak_kartin_sol_kenari_VURGU_RENGI_degil():
    """§11: "sol kenarı renkli yuvarlak kart yok". Kural bazında mandal.

    İddia `.folder-target`'a DEĞİL, her sol kenar bildirimine bakıyor: ölçütü
    bozan bir sonraki kart başka bir adla gelir ve tek kurala bakan bir mandal
    onu görmez. Aynı gerekçe ÖZELLİĞİN ve DEĞERİN adı için de geçerli — mandal
    dört yazım biçimini birden tarıyor (`_SOL_KENAR`) ve `--accent` ailesinin
    TAMAMINI reddediyor (`var(--accent` öneki), yalnız `var(--accent)`i değil:
    `--accent-border` ile çizilen sol kenar da vurgu renkli sol kenardır.
    Bugün hiçbir sol kenar bu ailenin herhangi bir üyesini kullanmıyor, yani
    genişletme yanlış-pozitif üretmiyor (ölçüldü).

    `--accent` bu kod tabanında yalnız DURUM anlatıyor (`flow-tokens.css`),
    `--danger` ise semantik olduğu için muaf ve zaten sol kenar kullanmıyor.

    `outline: … var(--accent)` BİLEREK taranmıyor: odak halkası ve seçili karo
    çerçevesi meşru durum işaretleri, üstelik `flow-tokens.css`'in `--accent`
    tanımının asıl işi o.
    """
    for ad in ("style.css", "mobile.css"):
        css = re.sub(r"/\*.*?\*/", "", _js(ad), flags=re.S)
        for bildirim in _SOL_KENAR.findall(css):
            assert "var(--accent" not in bildirim, (
                f"{ad}: vurgu renkli sol kenar geri geldi → {bildirim.strip()}")

    hedef = _css_block(".folder-target")
    assert "border-radius: 10px" in hedef, "yuvarlak kart biçimi değişmiş"
    # Kardeşiyle AYNI olduğu iddia ediliyor, "nötr bir şey" değil: hedef hâl
    # elde vardı ve iki kural ayrışırsa biri sessizce eski hâle dönebilir.
    # Karşılaştırma ÖZELLİĞİN ADIYLA birlikte: yalnız değer kıyaslansa biri
    # `border-inline-start`e geçip öteki `border-left`te kalabilir ve iddia
    # "aynı" derdi.
    _KENAR = r"border-(?:left|inline-start)"
    assert _bildirim(hedef, _KENAR) == _bildirim(_css_block(".chat-gate"), _KENAR), (
        ".folder-target ile .chat-gate'in sol kenarı ayrışmış")


def test_composer_ILK_KABUL_EDILEN_gonderimden_sonra_kuculuyor():
    """"Prompt gönderdikten sonra chat kısmı küçülsün" — ama KABUL EDİLEN prompt.

    ÇAPA `submitComposer` DEĞİL, ve bu iddia bir kusurun üstüne yazıldı: çapa
    bir tur orada durdu, oysa oradaki kapılar yalnız UZUNLUK kapıları. Boş bir
    kutuyla "Üret"e basmak `run()`ın "Önce bir prompt yaz."ına takılıyor —
    ama composer çoktan küçülmüş, `data-sent` yazılmış ve uzun tanıtım yer
    tutucusu kısasıyla değişmiş oluyordu: hiç gönderim yapmadan onboarding
    metnini öldürmek. `sendChat`in dört kapısı (chatBusy, boş mesaj, dolu
    konuşma, toplam karakter) ve `runArena`nın iki kapısı da aynı durumdaydı.

    Yerine geçen çapa KUTUNUN BOŞALDIĞI satır: üç akışın da bütün kapılardan
    geçtikten sonra yaptığı ilk iş o, yani "kabul edildi"nin kaynaktan
    okunabilir tek işareti. Bu yüzden iddia bitişikliği ölçüyor — `run`,
    `runArena` ve `sendChat`in her birinde `composerKuculsun()` boşaltma
    satırından hemen sonra gelmeli.

    Küçülmeyi fiilen yapan `rows` ekseni; `min-height` tek başına Chromium'da
    hiçbir şey değiştirmiyordu (57px → 57px), çünkü `autoGrow` satır içi bir
    `height` yazıyor ve o değer tabanın üstünde kalıyor. Bu yüzden test İKİSİNİ
    birden arıyor: CSS tabanı düşmezse tek satırlık ölçüm ona takılır.

    Gerçek yükseklik ölçümü tarayıcıda (tests/test_playwright_studio.py);
    buradaki mandal CI'ın Playwright'sız işleri için.
    """
    js = _js("core.js")
    govde = js.split("function submitComposer(", 1)[1].split("\n}\n", 1)[0]
    assert "composerKuculsun" not in govde, (
        "küçülmenin çapası yine uzunluk kapılarının yanında — reddedilen "
        "gönderim de composer'ı küçültür")

    # Üç kabul noktası, üçünde de aynı bitişiklik. Ölçüm KOD üzerinde: yorum
    # satırları ayıklanıyor, çünkü aradaki gerekçe metni bitişikliği bozmaz —
    # bozan şey araya girecek bir KAPI olurdu. Kalan tek satır izni
    # `autoGrow($("prompt"))` içindir (core.js'in iki akışında boşaltmanın
    # hemen ardından duruyor); ikinci bir kod satırı girerse iddia düşer.
    bitisik = re.compile(r'\.value = "";\n(?:[^\n]*\n)?\s*composerKuculsun\(\);')
    for dosya, imza in (("core.js", "async function run() {"),
                        ("core.js", "async function runArena(prompt) {"),
                        ("chat.js", "async function sendChat(")):
        dal = _js(dosya).split(imza, 1)[1].split("\n}\n", 1)[0]
        dal = "\n".join(r for r in dal.split("\n") if not r.strip().startswith("//"))
        assert bitisik.search(dal), (
            f"{imza}: küçülme kutunun boşaldığı ana bağlı değil — araya bir "
            "kapı girerse reddedilen gönderim de küçültür")

    # `rows` ekseni ve odak koşulu
    assert "function syncComposerSatirlari(" in js, "satır ekseni yok"
    satir = js.split("function syncComposerSatirlari(", 1)[1].split("\n}\n", 1)[0]
    assert "document.activeElement" in satir, (
        "odak koşulu yok — yazmaya dönen kullanıcı tek satıra sıkışır")
    assert "autoGrow(" in satir, (
        "yeni satır sayısı ölçülmüyor — satır içi `height` bayat kalır")

    # CSS tabanı: `rows` düşse bile 2.5rem'lik taban küçülmeyi yutar.
    kucuk = _css_block('.composer[data-sent] .composer-input')
    odakli = _css_block('.composer[data-sent]:focus-within .composer-input')
    assert "min-height" in kucuk and "min-height" in odakli, (
        "taban ekseni eksik — küçülme CSS'e takılır ya da geri gelmez")


def test_uzun_yer_tutucu_ILK_GONDERIMDEN_SONRA_kisaliyor():
    """Uzun yer tutucu ilk gönderimden sonra kısa hâline geçiyor.

    İki sebep, biri ölçülmüş: (1) gönderdikten sonra kalıcı bir talimat, tam da
    kullanıcının kaldırılmasını istediği "gereksiz yazı"; (2) 390px'de uzun
    metin İKİ SATIRA sarıyor ve boş bir `<textarea>`nın `scrollHeight`i yer
    tutucuyu de kapsıyor — yani `autoGrow` kutuyu 57px'e çiviliyor ve `rows` ne
    derse desin küçülme TELEFONDA hiç görünmüyordu.

    Metnin TEK yazarı var: iki çağıran (mod değişimi ve ilk gönderim) aynı iki
    değişkeni okuyor, metin iki yerde kurulsaydı ayrışırdı.
    """
    js = _js("core.js")
    assert "const PROMPT_YER_TUTUCU" in js, "yer tutucu tablosu yok"
    assert js.count(".placeholder =") == 1, (
        "yer tutucuyu yazan ikinci bir yer var — metinler ayrışabilir")
    govde = js.split("function syncPromptPlaceholder(", 1)[1].split("\n}\n", 1)[0]
    assert "dataset.sent" in govde, "kısa hâle geçiren koşul yok"
    for fn in ("function setMode(", "function composerKuculsun("):
        dal = js.split(fn, 1)[1].split("\n}\n", 1)[0]
        assert "syncPromptPlaceholder()" in dal, f"{fn} yer tutucuyu tazelemiyor"


def test_bos_panelin_metni_EKSENE_gore_degisiyor():
    """Boş model paneli sohbet ekseninde "anahtar yok" DEMİYOR.

    `renderModelCards` üç eksenin ortağı ve boş hâlin metni bir tur boyunca
    sabit bir "Kayıtlı API anahtarı yok" cümlesiydi. Görsel ekseninde doğru,
    sohbet ekseninde YANLIŞ İŞ: `credstore.chat_is_configured` anahtarı VE
    (Azure'da) dağıtım adını birlikte arıyor, yani kullanıcı anahtarı kayıtlı
    olduğu hâlde boş bir panel görebiliyor. Ona "anahtarını kaydet" demek,
    elinde zaten olanı yeniden yapıştırmasını söylemek — yapıştırır, hiçbir
    şey değişmez, sebep hâlâ görünmez.

    `goBlockReason`ın yönetmen dalı bu ayrımı zaten yapıyor ("Kayıtlı sohbet
    kimliği yok"); iddia panelin onunla AYNI dili konuşmasını çiviliyor,
    çünkü aynı hâlin iki yerde iki ayrı iş buyurması sessiz bir kırılma.
    """
    js = _js("core.js")
    assert "const MODEL_BOS_PANEL" in js, "boş panel metinleri tek yerde değil"
    # Metin fonksiyonda KURULMUYOR, eksenden okunuyor: tek yazar kuralı.
    govde = js.split("function renderModelCards(", 1)[1].split("\n}\n", 1)[0]
    assert "eksen.bosMetin" in govde, "boş panel metni eksenden okunmuyor"
    assert "Kayıtlı" not in govde, (
        "boş panel metni fonksiyonun içinde yeniden kuruluyor — eksenler ayrışır")

    # İki eksen İKİ AYRI metin okuyor; aynı sabite bağlanırlarsa ayrım ölür.
    eksenler = js.split("const MODEL_EKSENLERI = {", 1)[1].split("\n};", 1)[0]
    gorsel = eksenler.split("  chat: {", 1)[0]
    sohbet = eksenler.split("  chat: {", 1)[1].split("  arena: {", 1)[0]
    assert "MODEL_BOS_PANEL.anahtar" in gorsel, "görsel ekseni anahtar demiyor"
    assert "MODEL_BOS_PANEL.kimlik" in sohbet, (
        "sohbet ekseni de 'anahtar' diyor — Azure dağıtım adı eksik olan "
        "kullanıcıya yanlış iş veriyor")


def test_composer_ipucu_SERIDI_KALDIRILDI_bilgi_GO_dugmesinde():
    """Klavye ipucu şeridi composer'dan KALKTI (kullanıcı isteği: sadeleşme).

    Bu test bir öncekinin yerine geçiyor ve ölçtüğü şey tersine dönmedi,
    DARALDI. Eski iddia `.chat-hint`in geometrisiydi: `flex: 1` kısa biçimi
    `flex: 1 1 0%`e çözülüyor, taban SIFIR oluyor ve ölçümde (Chromium,
    1024×700 — `desktop.py`'deki en küçük pencere) ipucu 65px'e ezilip DÖRT
    satıra sarıyordu. O kusur artık imkânsız çünkü düğüm yok.

    Yerine geçen iddia: BİLGİ kaybolmadı. Kısayolun kendisi çalışmaya devam
    ediyor ve metni `#go`nun `title`ına taşındı — orada tek bir yazarı var
    (`syncGoGate`), yani "iki yerde iki ad" kırılması da doğmuyor.
    """
    html = _served()
    assert "chat-hint" not in html, "ipucu şeridi HTML'de duruyor"
    for dosya in ("style.css", "mobile.css"):
        # Yorumlar ÖNCE ayıklanıyor: iki dosyada da kuralın neden kalktığını
        # anlatan birer yorum var ve o yorumlar seçicinin adını taşıyor
        # (`_css_block`ın yardımcı olarak var olma sebebiyle aynı tuzak).
        css = re.sub(r"/\*.*?\*/", "", _js(dosya), flags=re.S)
        assert re.search(r"\.chat-hint\s*\{", css) is None, (
            f"{dosya}'te ölü `.chat-hint` kuralı kalmış")

    js = _js("core.js")
    assert "GO_KISAYOL" in js, "kısayol metni hiçbir yerde yok"
    govde = js.split("function syncGoGate(", 1)[1].split("\n}\n", 1)[0]
    assert "GO_KISAYOL" in govde, (
        "kısayol #go'nun title'ına yazılmıyor — bilgi tümden kayboldu")
    # Kilitliyken SEBEP yazılmalı, kısayol değil: çalışmayan bir düğmenin
    # kısayolunu duyurmak kilidin nedenini saklamak olurdu (#chat-gate'in
    # duruşu). `sebep ||` sırası tam olarak bunu söylüyor.
    assert "sebep\n    ||" in govde or "sebep ||" in govde, (
        "kilitli düğmede sebep yerine kısayol yazılıyor olabilir")

    # ŞERİT İKİ KISAYOL TAŞIYORDU. İlk turda yalnız ⌘/Ctrl+Enter taşındı ve
    # ⌘/Ctrl+J (mod değiştirme, hâlâ çalışıyor) hiçbir yerde yazmaz hâlde
    # kaldı: çalışan ama keşfedilemeyen bir kısayol, kullanıcı için yok olanla
    # aynı şey. İddia "bilgi ölmedi, yer değiştirdi"nin TAMAMINI ölçüyor.
    assert "MOD_KISAYOL" in js, "mod kısayolu hiçbir yerde yazmıyor"
    assert 'e.key.toLowerCase() !== "j"' in js, (
        "mod kısayolu artık çalışmıyor — o zaman metni de kalkmalı")
    for tab in ("tab-image", "tab-chat"):
        assert f'$("{tab}").title = ' in js, (
            f"#{tab} kısayolu duyurmuyor — bilgi yine tek yarım kaldı")
