"""Video modunun ÖN YÜZ sözleşmeleri: üçüncü mod, süre ekseni, oynatıcı.

Sunucu tarafı (`tests/test_video_route.py`) uçların sözleşmesini ölçüyor;
arayüzün asıl kırılganlığı ise burada, çünkü video PAYLAŞILAN düğümler
üzerinde yaşıyor:

  • dört `<select>` (`#size`/`#quality`/`#duration`/`#n`) iki üretim ekseni
    tarafından paylaşılıyor — sahibi o anda AKTİF olan mod,
  • `#model-note` da paylaşılıyor,
  • sonuç kartı ve galeri karosu aynı işlevden çiziliyor, ayrılan tek şey
    düğüm türü (`<img>` ↔ `<video>`).

Paylaşılan bir düğümün İKİ yazarı, hangisinin son sözü söylediğini çağrı
sırasına bırakmak demek — bu dosya o tekilliklerin bekçisi.

Yöntem depodaki kalıp: betikler servis edilip KAYNAK METNİ denetleniyor.
Tarayıcı ölçümü Playwright dosyasının işi (CI'da koşmuyor).

YORUMLAR AYIKLANIYOR (`_kodsuz`) ve bu ŞART: "burada şu yazmasın" biçimindeki
bir iddia, kararın GEREKÇESİNDE geçen aynı sözcüğe takılıyor — deponun DÖRT
kez düştüğü tuzak (bkz. tests/test_index.py, test_arena_onyuz.py,
test_shimmer.py).
"""
import re

from fastapi.testclient import TestClient

import app as appmod
import catalog
import models


def _metin(yol: str) -> str:
    return TestClient(appmod.app).get(yol).text


def _core() -> str:
    return _metin("/static/core.js")


def _chat() -> str:
    return _metin("/static/chat.js")


def _folders() -> str:
    return _metin("/static/folders.js")


def _viewer() -> str:
    return _metin("/static/viewer.js")


def _settings() -> str:
    return _metin("/static/settings.js")


def _html() -> str:
    return TestClient(appmod.app).get("/").text


def _css() -> str:
    return _metin("/static/style.css")


def _kodsuz(js: str) -> str:
    return re.sub(r"//[^\n]*", "", js)


def _govde(js: str, ad: str) -> str:
    m = re.search(rf"function {ad}\([^)]*\)\s*\{{(.*?)\n\}}", js, re.S)
    assert m, f"{ad}() bulunamadı"
    return m.group(1)


# ── Üçüncü mod ─────────────────────────────────────────────────────────


def test_the_third_mode_is_a_MODE_not_a_fourth_section():
    """Video, `#composer[data-mode]` ekseninde yaşıyor — `SECTION_VIEWS`ta
    DEĞİL. Böylece `setMode`, yer tutucular, model çipi, `#specs-btn` ve
    ⌘/Ctrl+J mantığının tamamı yeniden kullanılıyor; yeni bir kabuk yok."""
    js = _kodsuz(_core())

    assert 'id="tab-video"' in _html()
    assert '$("tab-video").addEventListener("click", () => setMode("video"))' in js
    # Yeni bir bölüm AÇILMADI.
    govde = _govde(js, "showSection")
    assert "video" not in govde


def test_the_mode_TABLE_is_the_single_mapping():
    """Mod → sekme eşlemesi TEK yerde (`MOD_SEKMELERI`) ve üç okuyanı var.
    Üçlü koşul olarak üç yerde yazılıydı: üçüncü mod eklenirken birini
    unutmak, sekmenin `aria-pressed`ının sessizce yanlış kalması demekti —
    ekran okuyucu "Görsel modu seçili" derken composer video üretirdi."""
    js = _kodsuz(_core())

    m = re.search(r"const MOD_SEKMELERI = \{(.*?)\};", js, re.S)
    assert m, "MOD_SEKMELERI tablosu yok"
    tablo = m.group(1)
    for ad in ("image", "video", "director"):
        assert ad in tablo, f"{ad} tabloda yok"
    # `setMode` tablodan DÖNGÜYLE okuyor, elle üç satır yazmıyor.
    govde = _govde(js, "setMode")
    assert "Object.entries(MOD_SEKMELERI)" in govde


def test_the_keyboard_shortcut_CYCLES_through_all_three_modes():
    """İki modda ⌘J bir "geçiş"ti; üçte SIRA gerekiyor ve sıra
    `MOD_SEKMELERI`nin anahtar sırası — yani sekmelerin ekrandaki sırası.
    İkinci bir liste, kısayolun sekmelerden farklı bir sırada dolaşması
    demekti."""
    js = _kodsuz(_core())

    assert "Object.keys(MOD_SEKMELERI)" in js
    assert re.search(r"sira\[\(sira\.indexOf\(currentMode\) \+ 1\) % sira\.length\]", js)


def test_each_mode_shows_EXACTLY_ONE_model_strip():
    """Üç şerit aynı yuvada ve birbirini dışlıyor: üçüncü şeridin genişlik
    bedeli SIFIR, yani composer'ın ölçülmüş 360px bütçesine yük binmiyor."""
    css = _css()

    for kural in [
        '#composer[data-mode="image"] #chat-model-pick',
        '#composer[data-mode="image"] #video-model-pick',
        '#composer[data-mode="director"] #model-pick',
        '#composer[data-mode="director"] #video-model-pick',
        '#composer[data-mode="video"] #model-pick',
        '#composer[data-mode="video"] #chat-model-pick',
    ]:
        assert kural in css, f"eksik kural: {kural}"


def test_ARENA_is_hidden_in_video_mode():
    """Arena aynı prompt'u N modelde koşturuyor; video tarafında bu, tek
    tıkla N tane dakikalarca süren ve saniyesi faturalanan üretim demek —
    kendi kararını isteyen bir şey."""
    assert '#composer[data-mode="video"] #arena-pick' in _css()


def test_the_SPECS_chip_stays_visible_in_video_mode():
    """Süre ve çözünürlük tam olarak orada seçiliyor; gizlemek video modunu
    ayarsız bırakmak olurdu. Yönetmen modunda gizli KALIYOR."""
    css = _css()

    assert '#composer[data-mode="director"] #specs-btn' in css
    assert '#composer[data-mode="video"] #specs-btn' not in css


# ── Değer taşıyıcıları: iki tür karışmıyor ─────────────────────────────


def test_the_SPECS_SHEET_carries_the_mode_too():
    """`#composer[data-mode]` ayar sayfasına UZANMIYOR — `#specs-sheet`
    composer'ın içinde değil, ayrı bir `<aside>`. Kanca bu yüzden ikinci bir
    düğüme de yazılıyor; ikinci bir DURUM değişkeni değil, aynı `mode`."""
    govde = _govde(_kodsuz(_core()), "setMode")

    assert '$("specs-sheet").dataset.mode = mode' in govde


def test_the_DEAD_controls_are_closed_in_video_mode():
    """Tema rengi / Logo ekle / Kütüphane video modunda ölü denetimdi.

    Palet `/api/video`ye HİÇ gitmiyor (`VideoRequest` `extra="forbid"`, ön yüz
    de göndermiyor — bkz. test_the_video_request_carries_NO_palette), yani
    seçilen tema rengi SESSİZCE düşüyordu: kullanıcı bir iş yapıyor, iş
    kayboluyor ve hiçbir yerde söylenmiyor. Logo bindirme de video kaydında
    zaten kapalı; Kütüphane onun varlıklarını yönetiyor.

    Gizleniyor, SİLİNMİYOR: üç id de `id-baseline.txt`te yazılı."""
    css = _css()

    assert '#specs-sheet[data-mode="video"] .palette-panel' in css
    assert '#specs-sheet[data-mode="video"] .assets-panel' in css
    # Görsel modunda üçü de DURUYOR — kural yalnız video moduna bakıyor.
    assert '#specs-sheet[data-mode="image"] .palette-panel' not in css
    # id'ler yerinde: gizleme silme değil.
    html = _html()
    for eleman in ("palette-btn", "logo-add-btn", "library-btn"):
        assert f'id="{eleman}"' in html


# ── İlk/son kare ───────────────────────────────────────────────────────


def test_the_FRAME_SLOTS_live_only_in_video_mode():
    """Kural `:not(...)` ile yazılıyor, `[data-mode="image"]` listesiyle değil.

    Gerekçe açılış anı: `setMode` çalışmadan önce `#specs-sheet`in
    `data-mode`u HİÇ YOK. Pozitif listeyle yazılsaydı panel o an GÖRÜNÜR olur,
    bir kare sonra kaybolurdu — en ucuz hâliyle titreme, en pahalısıyla
    yanlış moda ait bir kontrol."""
    css = _css()

    assert '#specs-sheet:not([data-mode="video"]) .frames-panel' in css
    # Panel gerçekten VAR ve iki yuvası da adreslenebilir.
    html = _html()
    for eleman in ("frames-panel", "first-frame-img", "last-frame-img",
                   "first-frame-pick", "last-frame-pick",
                   "first-frame-clear", "last-frame-clear",
                   "last-frame-input", "frames-note"):
        assert f'id="{eleman}"' in html, eleman


def test_the_START_frame_has_NO_second_state_variable():
    """Başlangıç yuvası `source`u OKUYOR — composer'daki `#ref-chip` ile aynı
    gerçek. İkinci bir değişken, birinin bayatlaması demekti: kullanıcı
    composer'dan referansı kaldırır, yuva dolu görünmeye devam ederdi.

    Bunun sonucu şu zorunluluk: `renderSource` yuvaları da çizmek zorunda."""
    js = _kodsuz(_core())

    assert "let sonKare = null" in js
    # Başlangıç için `ilkKare` diye bir ikiz YOK.
    assert "let ilkKare" not in js
    assert "renderFrames()" in _govde(js, "renderSource")
    assert "{ deger: source," in _govde(js, "renderFrames")


def test_clearing_the_source_ALSO_clears_the_end_frame():
    """Son kare tek başına `#go`yu kilitliyor (`goBlockReason`). Başlangıcı
    temizleyip bitişi bırakmak, kullanıcıyı sessizce o kilide düşürmek
    olurdu."""
    assert "clearSonKare()" in _govde(_kodsuz(_core()), "clearSource")


def test_the_end_frame_travels_in_its_OWN_form_fields():
    """`extra_*` kanalı DEĞİL: o kanal "ek REFERANS" demek ve video modunda üç
    ayrı kapıyla kapalı. Sunucuda da ayrı — `refs`e katılsaydı `max_refs=1`
    kapısı bitiş görseli seçen her isteği 422 yapardı."""
    js = _kodsuz(_core())
    # Dilim VİDEO dalı: `extra_source_ids` GÖRSEL dalında (`/api/edit`) meşru
    # olarak geçiyor, o yüzden dosyanın tamamında aramak yanlış olurdu.
    ucta = js.index("/api/video/animate")
    dal = js[js.rindex("if (videoMu) {", 0, ucta):ucta]

    assert 'fd.append("last_file", sonKare.file)' in dal
    assert 'fd.append("last_source_id", sonKare.id)' in dal
    # Ek referans yolu video dalında HÂLÂ kapalı: son kare oradan geçmiyor.
    assert "extra_source_ids" not in dal


def test_the_GATE_refuses_an_end_frame_that_stands_alone():
    """Sunucu da 422 diyor; kapı burada da duruyor çünkü sessizce ilerlemek,
    prompt yazıp üretime basıp dakikalar sonra bir 422 görmek olurdu."""
    govde = _govde(_kodsuz(_core()), "goBlockReason")

    assert "if (sonKare && !source) {" in govde
    assert "if (sonKare && !currentVideoModel.supports_last_frame) {" in govde


def test_the_PICKER_is_reused_for_the_end_frame_not_duplicated():
    """Aynı ızgara, aynı video süzgeci, aynı arama/kapsam gezinmesi — değişen
    tek şey onay düğmesinin ne yaptığı. İkinci bir modal, o süzgeci ve
    gezinmeyi ikinci kez yazmak olurdu.

    "Ek olarak ekle" bitiş hedefinde GİZLİ: ek referans video modunda zaten
    kapalı ve orada ikinci bir eylem sunmak, kullanıcıyı `goBlockReason`ın
    kilitlediği bir duruma davet etmek olurdu."""
    js = _kodsuz(_folders())

    assert 'async function openPicker(hedef = "ref")' in js
    assert '$("last-frame-pick").addEventListener("click", () => openPicker("last"))' in js
    assert 'if (pickerHedef === "last") {' in js
    assert '$("picker-use-extra").hidden = pickerHedef === "last"' in js


def test_the_video_strip_has_its_OWN_value_carrier():
    """`#model`in listesini modla değiştirmek DEĞİL, ayrı bir `<select>`.

    `#model`in değerini okuyan yerler (applyModel, secilecek,
    renderArenaOptions, `#model-settings-link`, chat.js'in yönetmen bağlamı)
    hepsi onu bir GÖRSEL modeli sanıyor; içine video id'si koymak o beş
    yerin her birinde sessiz bir tür karışması olurdu.
    """
    html = _html()

    assert '<select id="video-model"' in html
    assert 'id="video-model-btn"' in html
    assert 'id="video-model-logo"' in html


def test_the_two_catalogs_are_SEPARATE_arrays():
    js = _kodsuz(_core())

    assert re.search(r"let videoModels = \[\]", js)
    assert re.search(r"let currentVideoModel = null", js)
    # `imageModels`a video KATILMIYOR.
    govde = _govde(js, "applyVideoModels")
    assert "videoModels = s.video_models" in govde
    assert "imageModels" not in govde


def test_the_ACTIVE_model_is_asked_ONCE_not_five_times():
    """`aktifModel()` tek yardımcı, beş okuyanı var (`syncSpecs`,
    `syncRunCost`, `goBlockReason`, `run`, `#model-settings-link`). Beşinde
    ayrı bir mod koşulu yazmak, birini unuttuğunda yanlış modelin tarifesini
    gösteren ya da yanlış modelin id'sini gönderen bir kayma olurdu."""
    js = _kodsuz(_core())

    assert "function aktifModel()" in js
    assert js.count("aktifModel()") >= 4


def test_the_stale_client_gate_survives_a_server_WITHOUT_the_video_strip():
    """`video_models` alanı olmayan bir yanıt (v0.13 öncesi sunucu) sessizce
    geçiliyor, ama `goBlockReason` kapıyı GEREKÇESİYLE kapatıyor — bilgi
    kaybolmuyor, doğru yerde duruyor."""
    js = _kodsuz(_core())

    govde = _govde(js, "applyVideoModels")
    assert "Array.isArray(s.video_models)" in govde
    assert "Video modeli listesi alınamadı." in js


# ── Süre ekseni ────────────────────────────────────────────────────────


def test_the_duration_axis_is_gated_by_an_EMPTY_LIST_not_a_flag():
    """`qualities` HİÇ boş olamıyor (kalite ekseni olmayan model sentetik bir
    jeton beyan ediyor) ve o yüzden orada bir bayrak gerekiyordu; `durations`
    gerçekten boş olabiliyor, yani ikinci bir `duration_hidden` bayrağı aynı
    bilginin ayrışabilen kopyası olurdu."""
    js = _kodsuz(_core())
    govde = _govde(js, "eksenleriDoldur")

    assert "model.durations && model.durations.length" in govde
    assert '$("spec-duration").hidden = !sureli' in govde
    # Sunucu da bayrak GÖNDERMİYOR.
    assert "duration_hidden" not in _metin("/api/settings")


def test_the_duration_values_are_STRINGIFIED_before_fillAxis():
    """Ölçülü tuzak: sunucu süreyi SAYI gönderiyor ama bir `<option>`un
    `value`su her zaman DİZE. `fillAxis` eski seçimi `o.value === onceki` ile
    karşılaştırıyor — çevrilmezse eksen her doldurmada "varsayılana düşüldü"
    der ve kullanıcının seçtiği süre sessizce geri alınırdı."""
    js = _kodsuz(_core())
    govde = _govde(js, "sureSecenekleri")

    assert "String(d.value)" in govde


def test_the_axes_are_owned_by_the_ACTIVE_mode():
    """Dört `<select>` PAYLAŞILIYOR. `applyModel` ile `applyVideoModel` aynı
    anda yazsaydı son yazan kazanırdı — yani şerit bir modun jetonlarını
    öteki modda gösterirdi ve `check_video_capabilities` telde 422 dönerdi."""
    js = _kodsuz(_core())

    assert "function eksenleriDoldur(" in js
    assert 'if (currentMode !== "video") eksenleriDoldur(model' in js
    assert re.search(r'if \(currentMode === "video"\) \{\s*\n\s*eksenleriDoldur\(model',
                     js)
    # Mod değişimi yeniden dolduruyor.
    assert "aktifModeliUygula()" in _govde(js, "setMode")


def test_the_COUNT_row_hides_itself_when_the_model_offers_one():
    """Tek seçenekli bir açılır liste kullanıcıya bozuk bir kontrol gibi
    görünüyor. Kural modelin BEYANINDAN okunuyor (`max_n`), moddan değil."""
    js = _kodsuz(_core())

    assert '$("spec-n").hidden = model.max_n <= 1' in _govde(js, "eksenleriDoldur")
    # Bugün yalnız video modellerini etkiliyor.
    assert all(m.max_n == 1 for m in catalog.VIDEO_MODELS)
    assert all(m.max_n > 1 for m in catalog.IMAGE_MODELS)


def test_the_specs_chip_reads_the_HIDDEN_attribute_not_the_model():
    """Çipin kapısı `eksenleriDoldur`un yazdığı `hidden` özniteliği: modele
    İKİNCİ kez sormak, çipin eksenlerden ayrışması demekti ("kalite
    kayboldu" tuzağının süre/adet karşılığı)."""
    govde = _govde(_kodsuz(_core()), "syncSpecs")

    assert '!$("spec-duration").hidden' in govde
    assert '!$("spec-n").hidden' in govde


# ── Kredi: süre çarpanı ────────────────────────────────────────────────


def test_the_cost_is_multiplied_by_the_DURATION():
    """Video modellerinde `credits` SANİYE BAŞINA ve çarpım
    `catalog.cost_for`un yaptığının birebir aynısı — iki taraf aynı çarpımı
    yapmak zorunda, yoksa kullanıcı ekranda bir sayı görüp kaydında
    başkasını bulurdu."""
    govde = _govde(_kodsuz(_core()), "syncRunCost")

    assert 'Number($("duration").value' in govde
    assert "birim * sure" in govde


def test_the_UNIT_is_read_from_the_duration_list_not_a_second_field():
    """Sunucu ikinci bir "bu tarife saniyelik mi" alanı göndermiyor ve
    göndermemeli — aynı bilginin iki kopyası olurdu."""
    js = _kodsuz(_core())
    govde = _govde(js, "modelKrediAraligi")

    assert "kredi/sn" in govde
    assert "m.durations && m.durations.length" in govde


# ── Sonuç kartı: <video> ───────────────────────────────────────────────


def test_the_result_card_kind_comes_from_the_SHARED_params_field():
    """İkinci bir tür alanı (`media_kind`) AÇILMADI: `ResultParams`
    `extra="forbid"` taşıyor ve yeni bir zorunlu alan bütün ESKİ oturumları
    kaydedilemez kılardı. `kind` ise zaten her kayıtta var."""
    js = _kodsuz(_chat())

    assert "function sonucVideoMu(msg)" in js
    assert 'const VIDEO_RESULT_KINDS = ["video", "animate"]' in js
    # Sunucudaki kümenin AYNISI.
    assert models.VIDEO_RESULT_KINDS == {"video", "animate"}
    assert models.VIDEO_RESULT_KINDS <= models.RESULT_KINDS


def test_the_result_card_builds_a_VIDEO_element_for_video_kinds():
    js = _kodsuz(_chat())
    govde = _govde(js, "resultThumb")

    assert 'document.createElement(videoMu ? "video" : "img")' in govde
    assert "media.controls = true" in govde
    assert 'media.preload = "metadata"' in govde
    assert "media.playsInline = true" in govde


def test_the_deleted_media_probe_stays_the_ERROR_EVENT_for_both_types():
    """Sunucu sarkan `image_id`'yi kasten budamıyor ve dosya gerçekten yoksa
    adres 404 döner. `<video>` de `error` yayıyor, yani tespit tür
    değiştirmiyor — ayrıca tutulacak bir liste de bırakmıyor."""
    govde = _govde(_kodsuz(_chat()), "resultThumb")

    assert 'media.addEventListener("error"' in govde
    assert '"Video silindi"' in govde
    assert '"Görsel silindi"' in govde


def test_the_video_card_does_NOT_bind_a_zoom_click():
    """`<video controls>` kendi denetimlerini taşıyor ve karenin `click`
    dinleyicisi oynat/durdur ile büyüteci ÇAKIŞTIRIRDI — kullanıcı oynatmaya
    basarken büyüteç açılırdı."""
    govde = _govde(_kodsuz(_chat()), "resultThumb")

    assert "if (!videoMu) {" in govde
    m = re.search(r"if \(!videoMu\) \{(.*?)\n  \}", govde, re.S)
    assert m and "window.openViewer" in m.group(1), (
        "büyüteç bağlaması tür kapısının içinde değil")


def test_REFERANS_AL_is_not_offered_on_a_video():
    """Referans yolu bir PNG bekliyor (`app._output_png_path` uzantıyı çakılı
    tutuyor). Düğmeyi çizip sonra 404 göstermek, olmayan bir yol göstermek
    olurdu."""
    govde = _govde(_kodsuz(_chat()), "resultThumb")

    m = re.search(r"if \(videoMu\) \{\s*\n\s*actionsContainer\.append\(dl\);",
                  govde)
    assert m, "video kartında yalnız İndir bırakılmıyor"


def test_the_caption_carries_the_DURATION():
    """Videoda süre faturayı belirleyen eksen; "Video üretildi · 16:9 · 720p"
    yazan bir künye dört saniyelik bir klibi sekiz saniyelikten ayırt
    edemezdi. Eski kayıtlarda alan 0 ve o zaman hiç yazılmıyor: göç YOK."""
    govde = _govde(_kodsuz(_chat()), "resultCaption")

    assert "if (p.duration) parts.push" in govde


def test_the_run_branch_sends_the_right_endpoint_and_kind():
    js = _kodsuz(_core())
    govde = _govde(js, "run")

    assert 'fetch("/api/video"' in govde
    assert 'fetch("/api/video/animate"' in govde
    # Yanıt anahtarı da türe göre okunuyor.
    assert "videoMu ? govde.videos : govde.images" in govde
    # Döküm `kind`i dört değerli.
    assert 'videoMu ? (editing ? "animate" : "video")' in govde


def test_the_video_request_carries_NO_palette():
    """Uç palet alanı kabul etmiyor (`VideoRequest` `extra="forbid"`); palet
    bir GÖRSEL prompt eki. Göndermek 422 demekti."""
    govde = _govde(_kodsuz(_core()), "run")
    m = re.search(r'fetch\("/api/video", \{(.*?)\}\);', govde, re.S)
    assert m, "video JSON dalı bulunamadı"

    assert "pal" not in m.group(1)


def test_the_status_line_WARNS_about_the_wait():
    """Üretim dakikalarca sürüyor, istek o süre boyunca açık kalıyor ve
    ekranda yalnız shimmer var. "Üretiliyor…" yazan bir satır, kullanıcıya
    donmuş bir uygulama gibi görünürdü. İlerleme YÜZDESİ hâlâ yok ve o karar
    duruyor (uydurma olurdu); BEKLENEN SÜRE ise bir olgu."""
    govde = _govde(_kodsuz(_core()), "run")

    assert "sekmeyi kapatma" in govde
    assert "%" not in govde.split("statusEl.textContent = videoMu")[1][:200]


def test_the_DURATION_echo_is_checked_for_a_stale_server():
    """Bayat bir sunucu `duration`ı yok sayarsa kullanıcı 8 saniye isteyip 4
    saniye alır — ve FATURA da ona göre olur (kredi süreyle çarpılıyor).
    Model yankısının aynı iki yönlü gerekçesi."""
    govde = _govde(_kodsuz(_core()), "run")

    assert "images[0].duration !== duration" in govde


# ── Galeri ─────────────────────────────────────────────────────────────


def test_the_gallery_tile_is_a_VIDEO_for_video_records():
    """Ölçüt `kind` ve küme İKİ ÜYELİ — `chat.js`in aynasıyla birebir.

    Tek üyeli (`kind === "video"`) hâli bugün de doğru cevabı veriyordu, çünkü
    `app.py` her iki uçta da `"kind": "video"` yazıyor. Ama iki aynanın FARKLI
    olması sessiz bir ayrışma: bir gün `animate` kaydı düşerse galeri
    `<img src="….mp4">` çizer, kırık resim gösterir ve hiçbir yerde hata
    görünmez. İki listenin AYNI olması bu yüzden mandallanıyor.
    """
    js = _kodsuz(_folders())

    assert "function kayitVideoMu(rec)" in js
    assert 'const VIDEO_KAYIT_TURLERI = ["video", "animate"]' in js
    assert "VIDEO_KAYIT_TURLERI.includes((rec || {}).kind)" in js
    # `chat.js`teki ikizi AYNI iki üyeyi taşıyor.
    assert 'const VIDEO_RESULT_KINDS = ["video", "animate"]' in _kodsuz(_chat())
    govde = _govde(js, "renderGallery")
    assert 'document.createElement(videoMu ? "video" : "img")' in govde
    assert 'img.preload = "metadata"' in govde


def test_the_video_NODES_are_actually_STYLED():
    """Kartın `<video>` kurması YETMİYOR — ölçüsü de olmalı.

    Mobilde ölçülen iki kusurun TEK kökü buydu: depoda `<video>` etiketini
    hedefleyen hiçbir kural yoktu (tek istisna `#viewer-video`, o da
    `class="viewer-img"` sayesinde). Kuralsız bir `<video>` kendi DOĞAL
    ölçüsüne açılıyor (720p'de 1280×720) ve iki yerde birden kırılıyordu:

      • stüdyo kartında `.chat-media` kare + `overflow: hidden` olduğu için
        oynatıcının denetim çubuğu görünür alanın dışında kalıyor, yani video
        oynatılamıyordu (karta tıklama da bilerek bağlı değil),
      • galeride karo 720px boyunda bir kutuya dönüşüyor, `.gallery`de
        `grid-auto-rows` olmadığı için satır o boya çıkıyor ve `stretch`
        yüzünden aynı satırdaki GÖRSEL kartları da uzuyordu.

    Eski testlerin hepsi JS'in `createElement(videoMu ? "video" : "img")`
    satırını ölçüyordu ve o satır DOĞRUYDU — kusur CSS'te olduğu için hiçbiri
    görmedi. Delik burada kapanıyor.
    """
    css = _css()

    assert ".chat-media > video" in css, "stüdyo kartındaki video kuralsız"
    assert ".card :is(img, video)" in css, "galeri karosundaki video kuralsız"


def test_the_result_card_takes_the_VIDEO_ratio_not_the_square():
    """Kare kart bir 16:9 videoyu kırpardı — hem de kullanıcının saniyesi
    faturalanan çıktısını. Oran `params.size`ten geliyor: video modellerinde o
    alan ZATEN bir oran jetonu (`catalog.VIDEO_ASPECT_RATIOS`) ve bu dosya onu
    zaten okuyor (`resultCaption`), yani ikinci bir gerçek kaynağı yok.

    CSS'in `:has()`i DEĞİL JS tercih edildi: metadata inene kadar `<video>`
    300×150 durur ve kutu sonradan zıplardı."""
    js = _kodsuz(_chat())

    assert "function resultThumb(imageId, index, caption, videoMu = false, oran" in js
    govde = _govde(js, "resultThumb")
    assert 'fig.style.aspectRatio = oran.replace(":", " / ")' in govde
    # Oran ızgaranın tamamına BİR KEZ soruluyor — türle aynı gerekçe.
    assert 'const oran = (msg.params || {}).size || ""' in _govde(js, "appendResult")


def test_the_video_card_does_not_promise_a_ZOOM_it_never_binds():
    """`.chat-media`nın `cursor: zoom-in`i video kartında yalan söylüyordu:
    büyüteç video için bilerek bağlanmıyor (denetimler kartın içinde)."""
    assert ".chat-media.video { cursor: default; }" in _css()
    assert 'fig.classList.add("video")' in _govde(_kodsuz(_chat()), "resultThumb")


def test_the_gallery_tile_asks_the_browser_for_a_FIRST_FRAME():
    """`preload="metadata"` bazı WebView/iOS sürümlerinde ilk kareyi çözmüyor
    ve karo bomboş gri kalıyordu. Poster DOSYASI üretmek sunucuya ffmpeg
    bağımlılığı eklemek demek; medya parçası (`#t=0.1`) aynı işi bedelsiz
    yapıyor.

    Parça YALNIZ galeride: stüdyo kartında `<video>` gerçekten oynatılıyor ve
    orada klibin ilk anını atlatırdı."""
    govde = _govde(_kodsuz(_folders()), "renderGallery")

    assert 'img.src = `/output/${rec.filename}${videoMu ? "#t=0.1" : ""}`' in govde
    assert "#t=0.1" not in _kodsuz(_chat())


def test_the_gallery_tile_carries_a_DURATION_BADGE():
    """Bir video karosu hareketsiz ilk karesiyle bir görselden ayırt
    edilemiyor; rozet o ayrımı yapan tek şey."""
    govde = _govde(_kodsuz(_folders()), "renderGallery")

    assert "if (videoMu && !selectMode) {" in govde
    assert "rec.duration ?" in govde


def test_the_gallery_passes_the_TYPE_to_the_viewer():
    """Adresten çıkarmak da mümkündü ama uzantı ayrıştırmak, kaydın zaten
    taşıdığı bilgiyi ikinci bir yoldan türetmek olurdu."""
    govde = _govde(_kodsuz(_folders()), "renderGallery")

    assert 'videoMu ? "video" : "image"' in govde


# ── Büyüteç ────────────────────────────────────────────────────────────


def test_the_viewer_has_a_SECOND_node_for_video():
    """Tek elemanı tür değiştirmek MÜMKÜN DEĞİL: bütün yakınlaştırma/kaydırma
    mekaniği `#viewer-img` düğümüne bağlanmış durumda ve düğümü değiştirmek o
    dinleyicileri her açılışta yeniden kurmak olurdu."""
    html = _html()

    assert '<video id="viewer-video"' in html
    assert 'id="viewer-img"' in html


def test_zoom_and_pan_are_disabled_by_a_SINGLE_guard():
    """`wheel`, `dblclick`, pinch, −/+ düğmeleri ve klavye kısayolları HEPSİ
    `zoomAt`e varıyor. Muhafızı dinleyicilerin her birine koymak beş kopya
    olurdu ve birini unutmak, video oynatılırken sessizce ölçek değiştiren
    bir sahne demekti."""
    js = _kodsuz(_viewer())

    assert re.search(r"function zoomAt\([^)]*\)\s*\{\s*\n\s*if \(videoKipi\) return;", js), (
        "zoomAt'ın ilk satırı video muhafızı değil")
    assert re.search(r"function fit\(\)\s*\{\s*\n\s*if \(videoKipi\) return;", js)


def test_the_zoom_controls_are_HIDDEN_in_video_mode():
    """Gizleniyor, yalnız devre dışı BIRAKILMIYOR: `%100` yazan bir gösterge
    ve çalışmayan bir "Sığdır" düğmesi, kilidin neden orada olduğunu
    saklamak olurdu. "İndir" DURUYOR — o soru türe bağlı değil."""
    js = _kodsuz(_viewer())
    govde = _govde(js, "zoomKontrolleri")

    for eksen in ("viewer-zoom-out", "viewer-zoom-pct", "viewer-zoom-in",
                  "viewer-fit"):
        assert eksen in govde
    assert "viewer-download" not in govde


def test_the_viewer_CLEARS_the_video_src_on_close():
    """`hidden` bir `<video>` sesi çalmaya devam ediyor; yalnız `pause()`
    çağırmak da videoyu yeniden açıldığında kaldığı yerden başlatıyordu —
    iki hâl de şaşırtıcı."""
    govde = _govde(_kodsuz(_viewer()), "close")

    assert "vvid.pause()" in govde
    assert 'vvid.removeAttribute("src")' in govde
    assert "videoKipi = false" in govde


def test_the_viewer_RESETS_the_zoom_state_when_a_video_opens():
    """`fit()` video kipinde erken dönüyor (tek muhafız kuralı), yani ölçek
    ELLE sıfırlanmak zorunda. Ölçülebilir sonucu klavyede: ok tuşlarının
    dalı `scale > 1` ile açılıyor ve `preventDefault` çağırıyor — yani
    büyütülmüş bir görselden sonra açılan video, oynatıcının ileri/geri
    sarma tuşlarını yutuyordu. `.zoomed` sınıfı da düşüyor, yoksa imleç
    çalışmayan bir "tut ve kaydır" jestini davet ediyordu."""
    js = _kodsuz(_viewer())
    m = re.search(r"if \(videoKipi\) \{(.*?)\n    \}", js, re.S)
    assert m, "open()'ın video dalı bulunamadı"
    govde = m.group(1)

    assert "scale = 1" in govde
    assert "tx = 0" in govde and "ty = 0" in govde
    assert "syncCursor()" in govde


def test_the_viewer_STOPS_the_video_when_an_image_is_opened():
    """İki düğüm birbirini dışlıyor ve kapatılanın `src`i temizleniyor:
    bırakılan bir `<video src>` arka planda ses çalmaya devam edebiliyor."""
    js = _kodsuz(_viewer())
    m = re.search(r"function open\(src, alt, kind\)\s*\{(.*?)\n  \}", js, re.S)
    assert m, "open() bulunamadı"
    govde = m.group(1)

    assert "vimg.hidden = videoKipi" in govde
    assert "vvid.hidden = !videoKipi" in govde
    assert "vvid.pause()" in govde


def test_the_overlay_button_is_closed_for_video():
    """`/api/logo` yolu Pillow ile PNG bindiriyor ve kaynağı
    `_output_png_path`ten okuyor — bir video id'sinde o kapı 404 veriyor."""
    js = _kodsuz(_viewer())

    assert "logoBtn.hidden = !kayit || videoKipi" in js
    # Sol paneldeki ikinci kapı da kapalı.
    assert '!rec || rec.kind === "video"' in _kodsuz(_core())


def test_the_record_id_is_stripped_of_BOTH_extensions():
    """Depo sözleşmesi `{id}.{uzantı}` ve küme KAPALI (`storage.MEDIA_TYPES`in
    aynası): genel bir "son noktadan sonrasını at" deseni, prompt'undan gelen
    noktalı bir adda id'yi budardı."""
    js = _viewer()

    assert re.search(r"replace\(/\\\.\(png\|mp4\)\$/i", js)


# ── Tercih ─────────────────────────────────────────────────────────────


def test_the_video_model_preference_has_its_OWN_key():
    """İki şerit iki listeden besleniyor; tek anahtarda tutmak, mod
    değiştiren kullanıcının seçimini karşı listede GEÇERSİZ kılardı — yani
    her mod geçişinde sessizce varsayılana düşerdi."""
    js = _kodsuz(_core())

    assert "savePref({ video_model: model.id })" in js
    assert "let seciliVideoModeliTercihi" in _kodsuz(_settings())
    # Sunucu tarafı da ayrı anahtar biliyor.
    import prefs
    assert "video_model" in prefs.DEFAULTS
    assert prefs.DEFAULTS["video_model"] == catalog.DEFAULT_VIDEO_MODEL


def test_the_fail_closed_path_empties_the_video_catalog_too():
    """Eski bir listeyle kapı açık kalırsa kullanıcı artık geçerli olmayan
    bir modelle dakikalarca süren ve faturalanan bir üretim başlatmaya
    çalışır."""
    js = _kodsuz(_settings())

    assert "videoModels = []" in js
    assert "currentVideoModel = null" in js


# ── Video'nun UĞRAMADIĞI yollar ────────────────────────────────────────
#
# Bir MP4'ün ULAŞMAMASI gereken üç yüzey var ve üçünün ortak sebebi aynı:
# hepsi bir `<img src>` kuruyor ya da sunucudan bir PNG istiyor
# (`app._output_png_path`). Video oraya sızsa kırılma SESSİZ olurdu — kırık
# bir küçük resim ya da 404 — o yüzden kapılar tek tek mandallı.


def test_the_media_PICKER_filters_videos_out():
    """Bu seçici bir REFERANS GÖRSEL seçtiriyor. Bir video karosu burada iki
    kez kırılırdı: ızgara ve önizleme `<img src>` kuruyor, seçilirse de sunucu
    kaynağı `_output_png_path`ten okuyup 404 veriyor."""
    js = _kodsuz(_folders())

    assert "res.images.filter((r) => !kayitVideoMu(r))" in js
    # Süzgeç `pickerImages`e GİRİŞTE: gezinme sayaçları da aynı listeden
    # besleniyor (`pickerFilter(s).length`), yani kapsam düğmeleri "3 görsel"
    # derken ızgarada iki karo görünmesi olurdu.
    assert "pickerFilter = (scope, query = pickerQuery) =>\n  pickerImages.filter" in js


def test_a_FOLDER_COVER_is_never_a_video():
    """`<img>` bir MP4'ü çizemiyor. Yüklem "video DEĞİL", "görsel" değil: eski
    kayıtlarda `kind` alanı hiç yok ve onlar da kapak olabilmeli."""
    govde = _govde(_kodsuz(_folders()), "createFolderCell")

    assert "!kayitVideoMu(r)" in govde


def test_the_DIRECTOR_HANDOFF_is_closed_in_video_mode():
    """Yönetmen'in tur bağlamı `prefs["image_model"]`den geliyor
    (`app._director_context`), yani video modunda GÖRSEL modelinin jetonlarını
    öneriyor — video ucunda 422 dönen değerler. Kapı, Yönetmen video bağlamını
    öğrenene kadar duruyor (görev defteri madde 10d)."""
    assert '#composer[data-mode="video"] #ask-director' in _css()


def test_the_EXTRA_REFERENCE_strip_is_a_REMOVAL_surface_in_video_mode():
    """Veo tek bir ilk kare alıyor, yani EKLEME kapalı — ama şerit KOŞULSUZ
    gizlenemiyor ve bu ikinci koşul kilitlenmenin çıkış kapısı.

    Ölçülen kırılma şu: görsel modunda eklenen ekler moda geçerken
    silinmiyor, `goBlockReason` onlar yüzünden `#go`yu kilitliyor ve şerit
    koşulsuz gizliyse `×` düğmeleri hiç çizilmiyor — kullanıcı kilitli bir
    düğme ile göremediği bir ek arasında sıkışıyor. Şerit bu yüzden
    "eklenecek bir şey yoksa gizli, kaldırılacak bir şey varsa görünür".
    """
    js = _kodsuz(_core())
    govde = _govde(js, "renderSource")

    assert 'currentMode === "video" && extras.length === 0' in govde, (
        "şerit video modunda koşulsuz gizleniyor — eklenmiş bir ek "
        "kaldırılamaz hâle gelir")
    # EKLEME iki yoldan da kapalı: düğme ve paylaşılan gerekçe.
    assert 'currentMode === "video" || extraSlotsLeft() <= 0' in \
        _govde(js, "renderExtras")
    assert 'if (currentMode === "video") {' in _govde(js, "extraBlockReason")


def test_the_gate_REFUSES_an_extra_reference_in_video_mode():
    """Şeridin gizli olması TEK savunma değil: bayat bir sekme ya da görsel
    modunda eklenip video moduna geçilen bir referans hâlâ mümkün."""
    govde = _govde(_kodsuz(_core()), "goBlockReason")

    assert "if (extras.length) {" in govde
    assert "tek referans görsel alıyor" in govde


def test_the_OVERLAY_button_is_closed_for_a_video_record():
    """`/api/logo` Pillow ile PNG bindiriyor; iki kapı da (`#logo-add-btn` ve
    büyüteçteki `#viewer-logo`) kapalı."""
    assert '!rec || rec.kind === "video"' in _kodsuz(_core())
    assert "logoBtn.hidden = !kayit || videoKipi" in _kodsuz(_viewer())
