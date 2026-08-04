import re

from fastapi.testclient import TestClient
import app as appmod
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
             "viewer.js"]
    html = client.get("/").text
    positions = [html.find(f"/static/{name}") for name in order]
    assert all(p > 0 for p in positions), dict(zip(order, positions))
    assert positions == sorted(positions), "script sırası bozulmuş"
    for name in order:
        assert client.get(f"/static/{name}").status_code == 200, name
