"""Mobil katmanın sözleşmeleri.

Depo geleneği: servis edilen artefakt doğrulanır (dosya değil), bu yüzden her
şey `TestClient` üstünden okunuyor — test_index.py ve test_id_contract.py ile
aynı yol.

Bu dosyadaki iddiaların ortak yanı: hepsi SESSİZ kırılmalara karşı. Bir mobil
CSS kuralının düşmesi ya da bir dinleyicinin bağlanmaması hiçbir hata üretmez,
yalnızca telefonda "düğme çalışmıyor" olarak görünür — ve o telefon CI'da yok.
"""
from __future__ import annotations

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
