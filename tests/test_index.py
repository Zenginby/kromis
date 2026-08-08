import re

from fastapi.testclient import TestClient
import app as appmod
import models
import version


def test_index_served():
    c = TestClient(appmod.app)
    r = c.get("/")
    assert r.status_code == 200
    assert "GPT-Image Studio" in r.text
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
    """Çip swatch'ları v1.11'den beri tıklanabilir düğme (renk çıkarma).

    `aria-hidden="true"` içinde odaklanabilir bir kontrol bırakmak onu ekran
    okuyucudan TAMAMEN saklar: klavyeyle ulaşılan ama hiç duyurulmayan bir
    düğme kalır. Öznitelik geri eklenirse bu test düşer.
    """
    html = TestClient(appmod.app).get("/").text
    chip = re.search(r'id="palette-chip-sw"[^>]*', html)
    assert chip, "palet çipi swatch kabı bulunamadı"
    assert "aria-hidden" not in chip.group(0), (
        f"tıklanabilir swatch'lar aria-hidden içinde: {chip.group(0)}")


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
                       "viewer-zoom-in", "viewer-zoom-out", "viewer-fit", "viewer-close"):
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
    """Destek sorusu "hangi sürümdesiniz?" — cevabı arayüzde OLMALI."""
    client = TestClient(appmod.app)
    assert 'id="settings-version"' in client.get("/").text
    assert "settings-version" in client.get("/static/settings.js").text


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
    for element_id in ("tab-image", "tab-chat", "view-tabs-thumb", "view-image",
                       "view-chat", "chat-log", "chat-empty", "chat-input",
                       "chat-send", "chat-status", "chat-wait", "chat-gate",
                       # v1.15: kayıtlı sohbet paneli
                       "chat-sidebar", "chat-sidebar-toggle", "chat-new",
                       "chat-list", "chat-list-empty",
                       "set-chat-deployment", "chat-instructions-path"):
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
    assert 'chat-send").disabled' in js, "Gönder kapısı kurulmamış"
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
    """role="tab" verildiği anda ekran okuyucu seçili sekmeyi SINIFTAN değil
    aria-selected'dan okur; yalnız `.active` güncellenirse durum yanlış duyurulur.
    """
    js = TestClient(appmod.app).get("/static/core.js").text
    body = re.search(r"function showView\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "showView() bulunamadı"
    assert "aria-selected" in body.group(1)
    assert "hidden" in body.group(1)


def test_apply_to_form_switches_to_the_image_view():
    """Aktarma görünümü çevirmezse kullanıcı sohbette kalır ve prompt'un forma
    girdiğini GÖRMEZ: "bir şey olmadı" sanıp ikinci kez basar, ayarlar da
    sessizce ikinci kez ezilir.

    Bu davranış bir kez ölçüm yüzünden şüpheye düştü: tarayıcı otomasyonunun
    sayfa okuma adımı sekmeyi kendisi değiştirip odağı kaydırdığı için geçiş
    "olmamış" göründü — davranış doğruydu, ölçüm yanlıştı. Tripwire o yüzden
    burada: bir dahaki sefere cevap testten okunsun.
    """
    js = TestClient(appmod.app).get("/static/chat.js").text
    body = re.search(r"function applyToForm\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "applyToForm() bulunamadı"
    assert 'showView("image")' in body.group(1), (
        "aktarma görsel sekmesine geçmiyor — kullanıcı sonucu görmez")
    assert '$("prompt").focus()' in body.group(1), (
        "prompt alanı odaklanmıyor — aktarılan metin gözle bulunabilmeli")


def test_chat_view_is_hidden_on_first_paint():
    """Açılışta Görsel modu seçili: yönetmen paneli işaretlemede gizli gelmeli.

    Desen ETİKETTEN BAĞIMSIZ: iddia edilen şey panelin `hidden` gelmesi, hangi
    elementle sarıldığı değil. Flow kabuğunda iki panel `<div>` yerine
    `<section>` oldu (§ kabuk) ve `<div id="view-chat"` arayan eski desen bunu
    "panel yok" diye okuyordu — kapsanan davranış hiç değişmemişti.
    """
    html = TestClient(appmod.app).get("/").text
    chat_view = re.search(r'<\w+ id="view-chat"[^>]*>', html)
    assert chat_view, "#view-chat yok"
    assert "hidden" in chat_view.group(0), "yönetmen paneli açılışta görünür"
    image_view = re.search(r'<\w+ id="view-image"[^>]*>', html)
    assert image_view, "#view-image yok"
    assert "hidden" not in image_view.group(0), "görsel paneli açılışta gizli"


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
    """Seçenek bloğunun görünür karşılığı ÇİPLER; ham JSON gösterilmemeli."""
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
    assert "applyToForm(parsed)" in body.group(1), "Görsel modunda üret bağlı değil"
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
    for banned in (".replace(", '$("prompt")', "parsed.prompt"):
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
    """
    js = _chat_js()
    body = re.search(r"function renderParameters\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "renderParameters() bulunamadı"
    assert "optionChip(String(raw), false, row)" in body.group(1), (
        "eksen alternatifleri satıra bağlı tek seçim değil")


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
    # Yeniden açılışta da pil kalsın: openChat mesaj NESNESİ geçirmeli.
    open_body = re.search(r"async function openChat\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert "appendUser(m)" in open_body.group(1), (
        "openChat content geçiriyor — yeniden açılan sohbette piller baloncuğa döner")


def test_the_send_button_does_not_leak_the_click_event_into_the_display_field():
    """`("click", sendChat)` yazılsa MouseEvent `display` argümanı olurdu.

    Sonuç: pilde "[object MouseEvent]" görünür ve o dize `display` alanı olarak
    SUNUCUYA gider. Tek karakterlik bir sadeleştirmenin bedeli; sözdizimi geçerli
    olduğu için hiçbir şey uyarmaz.
    """
    js = _chat_js()
    assert re.search(r'\$\("chat-send"\)\.addEventListener\("click",\s*\(\)\s*=>\s*sendChat\(\)\)',
                     js), "gönder dinleyicisi sarmalanmamış — MouseEvent display olur"


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
    assert "if (!label) input.value = message;" in body.group(1), (
        "başarısız çip turunda delta metni besteciye dökülüyor")


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
    assert "if (!parts.length) return { content, display: own };" in body.group(1), (
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
    for fn in ("variationItems(parsed).length", "axisItems(parsed).length"):
        assert fn in skip.group(1), (
            f"atlama kümesi {fn} sormuyor — sözleşmesi bozuk blok sessizce kaybolur")
    # Süzgeç GERÇEKTEN paylaşılıyor mu: paneller de aynı fonksiyonu çağırmalı.
    for name, fn in (("renderVariations", "variationItems(parsed)"),
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
    js = _chat_js()
    body = re.search(r"async function sendChat\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    used = re.search(r"const used = chatThread(.*?);\n", body.group(1), re.S)
    assert used, "toplam kapısının hesabı bulunamadı"
    assert "m.content.length" not in used.group(1), (
        "sonuç kaydında content yok — TypeError ile gönderim ölür")
    assert "RESULT_ROLE" in used.group(1), (
        "toplam kapısı sonuç kayıtlarını da sayıyor")


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
    body = re.search(r"async function openChat\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "openChat() bulunamadı"
    assert re.search(r'RESULT_ROLE|=== "result"', body.group(1)), (
        "yeniden açılan oturumda sonuç kaydı role göre çizilmiyor")


def test_a_result_image_url_is_built_from_the_id():
    """Döküm yalnız `image_ids` taşıyor; dosya adı sözleşmesi `{id}.png`.

    Sözleşme storage.py'de yazılı (`delete_many` docstring'i, `save`'in
    `filename` satırı) ve ikinci bir istek gerektirmiyor. `/api/history`
    KULLANILAMAZ: o uç klasöre göre süzülüyor, yani başka bir klasördeki
    sonuç görselini hiç döndürmezdi.
    """
    js = _chat_js()
    assert re.search(r"/output/\$\{[^}]*\}\.png", js), (
        "sonuç görselinin URL'i id'den kurulmuyor")


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
    """Ayrım KASITLI (§4.1): Araçlar = tasarım kararları, dişli = makine ayarı.

    Azure kimliği Araçlar görünümüne sızarsa iki kapı aynı şeyi yapar ve
    "yalnızca bu makineye kaydedilir" uyarısının bağlamı kaybolur.
    """
    view = _section(_html(), "view-tools")
    for leaked in ("set-endpoint", "set-key", "set-chat-deployment"):
        assert leaked not in view, f"{leaked} Araçlar görünümüne sızmış"
    assert "dişli" in view, "kullanıcı Azure ayarlarının nerede olduğunu okuyamıyor"


def test_media_search_is_served_and_filters_by_prompt_folder_and_size():
    """A3: Arama YALNIZCA Medya'da (üst şeritten kaldırıldı, §4.1).

    Sözleşme üç alanı sayıyor: prompt, klasör, boyut. Biri düşerse arama
    "çalışıyor" görünür ama kullanıcı aradığını bulamaz — sessiz bir eksik.
    """
    html = _html()
    assert 'id="media-search"' in html, "Medya'da arama alanı yok"
    assert 'class="search"' in html, "arama pill'inin kabuğu yok"
    js = _folders_js()
    assert "searchQuery" in js, "arama durumu yok"
    body = re.search(r"function matchesSearch\([^)]*\)\s*\{(.*?)\n\}", js, re.S)
    assert body, "matchesSearch() bulunamadı"
    # Üç alan da SAMANLIĞIN KENDİSİNDE aranıyor (şablon dizesi), gövdede adı
    # geçen bir değişkende değil — mutasyon dersi: `const folder = …` satırı
    # tek başına "klasör aranıyor" saymaya yetiyordu.
    haystack = re.search(r"return `([^`]*)`", body.group(1))
    assert haystack, "eşleşme şablon dizesiyle kurulmuyor"
    for field in ("prompt", "folderName", "size"):
        assert f"${{{field}}}" in haystack.group(1), f"{field} aranmıyor"
    assert "folder.name" in body.group(1), "klasör ADI değil başka bir alan aranıyor"


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
    for theme in ("mono", "kurumsal", "amber", "viola"):
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
    for theme in ("kurumsal", "amber", "viola"):
        assert f'[data-theme="{theme}"]' in tokens, theme


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
    assert re.search(r'apply\.textContent\s*=\s*"Görsel modunda üret"', body.group(1)), (
        "prompt bloğunun eylem düğmesi §4.2'nin adını taşımıyor")


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
    assert 'showView("image")' in fn, "mod Görsel'e alınmıyor"
    assert "forma aktarıldı" not in fn.lower(), "durum satırı hâlâ 'form' diyor"
    assert "Görsel modu" in fn, "durum satırı nereye aktarıldığını söylemiyor"


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
    """"Devreder": kopyalamıyor, TAŞIYOR.

    Metin iki kutuda birden kalırsa Görsel'e dönüp Üret'e basmak yönetmene
    sorulmuş olan ham metni ayrıca üretir; düğme de görünür kalıp ikinci bir
    devir daha davet eder.
    """
    fn = _ask_director_body()
    assert '$("chat-input").value = merged' in fn, "metin yönetmenin kutusuna yazılmıyor"
    assert re.search(r'\$\("prompt"\)\.value\s*=\s*""', fn), (
        "ham metin Görsel modunda da kalıyor")
    assert 'showView("chat")' in fn, "mod Yönetmen'e geçmiyor"
    assert "syncAskDirector()" in fn, (
        "programatik temizlik `input` olayı doğurmaz — düğme görünür kalır")


def test_ask_director_does_not_overwrite_an_unsent_director_message():
    """Yönetmen kutusunda yazılmış ama gönderilmemiş bir mesaj olabilir.

    Üzerine yazmak sessiz veri kaybı olurdu (`applyToForm`'un kırpma yasağıyla
    aynı duruş): eldeki metin korunuyor, yeni metin ALTINA ekleniyor.
    """
    fn = _ask_director_body()
    assert re.search(r'const existing = \$\("chat-input"\)\.value', fn), (
        "kutudaki mevcut metin hiç okunmuyor")
    assert re.search(
        r"const merged = existing \? `\$\{existing\}[^`]*\$\{text\}` : text", fn), (
        "mevcut metin birleşime girmiyor — üzerine yazılıyor")


def test_ask_director_refuses_to_truncate_the_hand_off():
    """KIRPMA YOK: sunucu 6000 karakteri aşan kullanıcı mesajını reddediyor.

    Sessizce kırpmak yönetmene BAŞKA bir metin sorardı — `MAX_PROMPT_CHARS`
    dalının aynısı, yönü ters.
    """
    fn = _ask_director_body()
    guard = re.search(r"merged\.length > MAX_CHAT_MSG_CHARS", fn)
    assert guard, "tek mesaj sınırı hiç kontrol edilmiyor"
    write = fn.index('$("chat-input").value = merged')
    assert guard.start() < write, "sınır kontrolü yazımdan SONRA — kırpma bile değil"
    assert ".slice(0, MAX_CHAT_MSG_CHARS" not in fn, "metin sessizce kırpılıyor"
    # Ret GÖRÜNÜR satıra yazılmalı: devir olmadığı için mod Görsel'de kalıyor ve
    # `#chat-status` orada `display:none` (CSS'in mod ekseni). Canlı ölçümde
    # yakalandı — `chatStatus` ile ret sessizdi: düğme tıklanıyor, hiçbir şey
    # olmuyor, sebebi de görünmüyordu.
    refusal = fn[guard.start():write]
    assert "statusEl.textContent" in refusal, "sınır aşımı sessizce geçiliyor"
    assert "chatStatus(" not in refusal, (
        "ret Görsel modunda gizli olan #chat-status'a yazılıyor")


def test_ask_director_is_a_text_button_not_a_second_filled_one():
    """§4.2'nin kendi cümlesi: "ekranda ikinci bir dolu düğme oluşmaz"."""
    tag = re.search(r'<button[^>]*id="ask-director"[^>]*>', _html()).group(0)
    assert "btn-ghost" in tag, "metin düğmesi değil"
    assert "primary" not in tag, "Üret'in yanında ikinci dolu düğme"


def test_the_hand_off_still_goes_through_the_mode_switch():
    """§1.1: iki yeni yol mod anahtarının mandalını bozmuyor.

    `data-mode`'u kendi başına yazan bir kısayol, `showView`'un ölçtüğü kayan
    dolguyu ve `aria-selected`'ı geride bırakırdı — sekme düğmeleri yanlış
    tarafı seçili gösterirdi.
    """
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
    """`renderGallery()`'nin gövdesi (sütun 0'daki kapanış süslüsüne kadar)."""
    js = _folders_js()
    match = re.search(r"function renderGallery\(\)\s*\{(.*?)\n\}", js, re.S)
    assert match, "renderGallery bulunamadı"
    return match.group(1)


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
    assert re.search(r'#composer\[data-mode="director"\][^{]*#status', _css(), re.S), (
        "#status'un mod ekseninde de gizlendiği kuralı kayboldu")


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
    """B9 · Sıralama bilinçli olarak ERTELENDİ (D10, Adım 10).

    Yalnız modalda sıralama koymak, arkasındaki Medya görünümünde OLMAYAN bir
    kontrol demek — "çalışmayan arama kutusu konmadı" kuralının tersi. Bu test
    ertelemenin kaza değil karar olduğunu mandallıyor; D10 gelince silinmez,
    iki yüzeyi birlikte soracak şekilde YENİDEN YAZILIR (§1.2).
    """
    assert "sort-btn" not in _picker_html(), "seçiciye tek başına sıralama gelmiş"
    assert "sort-btn" not in _strip_html_comments(_html()), (
        "Medya'ya sıralama gelmiş (D10 açıldıysa bu test yeniden yazılır)")


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
    assert "aria-selected" in picker, "seçili karo işaretlenmiyor"
    # İddia sorgunun ARGÜMANINA bakıyor, "querySelector hiç geçmesin"e değil:
    # seçicide meşru bir sorgu zaten var (`[data-picker-close]`). İlk yazım
    # `"aria-selected\"]" not in picker` idi ve MUTASYON TURUNDA hayatta kaldı —
    # gerçek regresyon `querySelector('[aria-selected="true"]')` diye yazılır,
    # o dizede `aria-selected` hemen ardından `=` gelir, `"]` değil. Kelime
    # aramasının dördüncü kurbanıydı (§0.6, §0.7, §0.9); burada tırnak biçimine
    # bakmayan bir iddiaya çevrildi.
    for arg in re.findall(r"querySelector(?:All)?\((.*?)\)", picker):
        assert "aria-selected" not in arg, f"seçim DOM'dan okunuyor: {arg}"
    assert "pickerById(pickerSelectedId)" in picker, (
        "yan bölme seçimi durumdan almıyor")


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
    assert count == 2, f"composer'daki birincil sayısı değişmiş: {count}"
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

    İddia: seçicideki her `folderPath(...)` çağrısı sonucu ZİNCİR olarak işler
    (`.map(...)`), ham hâliyle etiket yerine geçmez. Tek üretim yeri
    `pickerFolderLabel`; ayraç kod tabanından ("A / B / C", folders.js:106).
    """
    picker = _picker_js()
    assert "pickerFolderLabel" in picker, "klasör etiketi tek yerden üretilmiyor"
    for m in re.finditer(r"folderPath\([^)]*\)(.{0,8})", picker):
        assert m.group(1).lstrip().startswith(".map("), (
            "folderPath'in DİZİSİ doğrudan etikete veriliyor → [object Object]")
