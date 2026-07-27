import re

from fastapi.testclient import TestClient
import app as appmod


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


def test_static_cache_busters_are_bumped_together():
    """Tek taraflı ?v= artışı bayat app.js'e yol açar → palet sessizce gönderilmez.

    Sürümden bağımsız: gelecekteki artışlarda da geçerli kalır.
    """
    r = TestClient(appmod.app).get("/")
    versions = set(re.findall(r"\?v=(\d+)", r.text))
    assert len(versions) == 1, f"style.css ve app.js sürümleri ayrışmış: {versions}"


def test_edit_request_forwards_every_palette_option():
    """Düzenleme dalı palet alanlarını ELLE saymamalı.

    JSON dalı `...pal` ile hepsini gönderirken multipart dalı üç alanı tek tek
    sayıyordu ve `palette_id` düşüyordu: sunucu kayıtlı paletin DONDURULMUŞ
    adlarını kullanamıyor, (seed, mode)'dan çevrimdışı yeniden hesaplıyordu —
    kütüphanede görünen ad ile prompt'a giden ad ayrışıyordu. Sunucu tarafı
    doğruydu (tests/test_palette_route.py: saved palette id'yi onurlandırıyor),
    o yüzden hatayı yalnızca istemci tarafı bir iddia yakalayabilir.
    """
    js = TestClient(appmod.app).get("/static/app.js").text
    assert 'fd.append("palette_hex"' not in js, (
        "palet alanları elle sayılmış — yeni bir alan eklendiğinde yine düşer")
    assert re.search(r"Object\.entries\(pal\)", js), (
        "düzenleme dalı palet seçeneklerinin tamamını dolaşarak eklemeli")


def test_ui_surfaces_a_palette_that_did_not_fit_in_the_prompt():
    """Ek 4000 karakter sınırına sığmadıysa kullanıcı bunu GÖRMELİ.

    Kayıtta palet var ama prompt'a girmedi; bayrak okunmazsa arayüz paleti
    uygulanmış gösterir ve kullanıcı renksiz sonucu açıklayamaz.
    """
    js = TestClient(appmod.app).get("/static/app.js").text
    assert re.search(r"palette\.applied\s*===\s*false", js), (
        "applied=false durumu arayüzde ele alınmıyor")
