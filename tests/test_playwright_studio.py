"""Playwright End-to-End Tests for Step 13 (Tek Döküm, Tek Composer — studio-session.html).

Tests:
1. Studio session loads single section #view-studio with sole textarea #prompt and submit button #go.
2. Mode switching updates data-mode, button label, and placeholder.
3. Keydown Enter submits composer according to active mode.
4. Reference chip image #ref-chip-img is created inside #ref-chip.
5. Single click on #go triggers submission without duplicate listener execution.
"""
from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
import pytest
from fastapi import FastAPI
import uvicorn

# Playwright isteğe bağlı bir bağımlılık: CI derleme işlerinde (build-macos-arm64)
# kurulu değil. Modül düzeyinde importorskip tüm test dosyasını atlar ve
# pytest'in toplama hatası (ImportError) yerine temiz bir SKIP üretir.
pytest.importorskip("playwright", reason="playwright kurulu değil — E2E testleri atlanıyor")

from playwright.sync_api import sync_playwright

from app import app


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class ServerThread(threading.Thread):
    def __init__(self, port: int):
        super().__init__(daemon=True)
        self.port = port
        self.config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
        self.server = uvicorn.Server(self.config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


def test_playwright_studio_single_thread_flow():
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    time.sleep(1.0)  # Wait for server to start

    base_url = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1. Open Studio application
            page.goto(base_url)
            page.wait_for_selector("#view-studio")

            # İLK KURULUM PERDESİ. Test ortamında hiç anahtar yok, o yüzden
            # settings.js Ayarlar'ı KENDİLİĞİNDEN açıyor (`openIfMissing`) ve
            # ortak perde (#shell-scrim, z-index 40) composer'ın üstüne
            # biniyor: aşağıdaki `page.click("#tab-chat")` 30 saniye bekleyip
            # "intercepts pointer events" diye düşüyordu. Bu dosya CI'da hiç
            # koşmuyor (playwright requirements'ta yok, modül düzeyinde
            # `importorskip`), o yüzden kırık hâli fark edilmemişti — 041fc2f'te
            # de kırık. Panel kapatılmadan bu testin ölçtüğü hiçbir şeye
            # ulaşılamıyor.
            if page.query_selector(".sheet.open"):
                page.keyboard.press("Escape")
                page.wait_for_selector(".sheet.open", state="detached")

            # 2. Assert single studio view is visible and retired IDs are absent
            assert page.is_visible("#view-studio")
            assert page.query_selector("#view-image") is None
            assert page.query_selector("#view-chat") is None
            assert page.query_selector("#chat-input") is None
            assert page.query_selector("#chat-send") is None

            # 3. Assert sole composer prompt textarea & go button exist
            prompt = page.query_selector("#prompt")
            go_btn = page.query_selector("#go")
            assert prompt is not None
            assert go_btn is not None

            # 4. Check initial mode (Image mode)
            composer = page.query_selector("#composer")
            assert composer.get_attribute("data-mode") == "image"
            assert page.inner_text("#go").strip() == "Üret"
            assert "Ne üretmek istiyorsun?" in prompt.get_attribute("placeholder")

            # 5. Switch to Director mode
            page.click("#tab-chat")
            page.wait_for_function('document.querySelector("#composer").getAttribute("data-mode") === "director"')
            assert page.inner_text("#go").strip() == "Gönder"
            assert "Yönetmen'e sor" in prompt.get_attribute("placeholder")

            # 6. Switch back to Image mode
            page.click("#tab-image")
            page.wait_for_function('document.querySelector("#composer").getAttribute("data-mode") === "image"')
            assert page.inner_text("#go").strip() == "Üret"

            # 7. Type prompt and check character count / autoGrow
            page.fill("#prompt", "A futuristic Turkish coffee cup on marble table, 8k render")
            page.wait_for_function('document.querySelector("#prompt").value.length > 0')

            # 8. Check reference chip img element exists in DOM
            ref_chip_img = page.query_selector("#ref-chip-img")
            assert ref_chip_img is not None

            # 9. Verify submission handling in Director mode without throwing duplicate listener errors
            page.click("#tab-chat")
            page.fill("#prompt", "Instagram için kare görsel fikri ver")
            # KAPI ÖNCE ÖLÇÜLÜYOR. Bu ortamda hiçbir sağlayıcı anahtarı yok, o
            # yüzden `syncGoGate` düğmeyi DOĞRU biçimde kilitliyor ("Sohbet
            # modeli için kimlik yok") ve `page.click` kilitli bir düğmeyi
            # "enabled" olana kadar bekleyip 30 saniyede düşüyordu — yani test
            # uygulamanın doğru davranışını hata sayıyordu. 041fc2f'te de öyle;
            # bu dosya CI'da hiç koşmadığı için fark edilmemişti.
            #
            # Çift dinleyici endişesinin ASIL bekçisi zaten statik
            # (`tests/test_id_contract.py::test_go_button_has_single_listener`).
            # Burada tarayıcının söyleyebileceği şey ölçülüyor: kapı kilitliyse
            # SEBEBİNİ söylüyor, açıksa gönderim çalışıyor — ikisinde de
            # çalışma zamanı hatası yok.
            if page.is_disabled("#go"):
                assert page.get_attribute("#go", "title"), (
                    "#go kilitli ama sebebini söylemiyor")
            else:
                page.click("#go")
                page.wait_for_timeout(300)
            # Status should show prompt sent / director responding status message, not runtime errors
            status = page.inner_text("#status")
            assert "Hata" not in status

            browser.close()
    finally:
        server.stop()


def test_playwright_model_sheet_alttan_aciliyor():
    """Alttan açılan model seçicisinin tarayıcı sözleşmesi.

    Buradaki dört iddia yalnız GERÇEK bir tarayıcıda ölçülebiliyor ve
    hiçbirini kaynak taraması yakalayamaz:

      · panelin gerçekten ALT kenardan yükseldiği — CSS kaynağı `bottom: 0`
        yazdığını söylüyor, kutunun nerede DURDUĞUNU söylemiyor. `.sheet.open
        { transform: none }`ın bir `translateX` ortalamasını silmesi tam bu
        yolla görülüyor (masaüstü iddiası).
      · seçimin diske TEK kez yazıldığı — çift `savePref` sessiz: ekranda
        hiçbir iz bırakmıyor, yalnız ağ trafiğinde görünüyor.
      · odağın çipe döndüğü — `document.activeElement` yalnız çalışan bir
        sayfada var.
      · aynı karta ikinci dokunuşun sessiz kaldığı.

    Depo geleneği bunu şart koşuyor: bu dosyanın ikizi olan üç kırılma
    (`applyChatModel`in dönüş değeri, 360px yatay kayma, sağlayıcı alan
    gruplarının gizlenmesi) pytest'te yeşilken yalnız Chromium'da görülmüştü.
    """
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    time.sleep(1.0)
    base_url = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            prefs_posts = []
            page.on("request", lambda r: prefs_posts.append(r.url)
                    if r.method == "POST" and "/api/prefs" in r.url else None)

            page.goto(base_url)
            page.wait_for_function(
                'document.querySelector("#model") && document.querySelector("#model").value !== ""')
            # İlk kurulumda (anahtar yok) Ayarlar kendiliğinden açılıyor —
            # perde composer'ı yutuyor, o yüzden önce kapatılıyor.
            if page.query_selector(".sheet.open"):
                page.keyboard.press("Escape")
                page.wait_for_selector(".sheet.open", state="detached")

            # 1. Çipe dokunmak paneli ALT kenardan yükseltiyor.
            page.click("#model-btn")
            page.wait_for_selector("#model-sheet.open")
            page.wait_for_function(
                'getComputedStyle(document.querySelector("#model-sheet")).transform === "none"')
            box = page.eval_on_selector("#model-sheet", "e => e.getBoundingClientRect()")
            assert abs(box["bottom"] - 844) < 2, f"panel alt kenara dayanmıyor: {box}"
            assert box["top"] > 0, "panel tepeye dayanmış — alttan açılmıyor"
            assert page.get_attribute("#model-btn", "aria-expanded") == "true"

            # 2. Kartlar: native radyo, işaretli olan seçili modeli gösteriyor,
            #    ve model tanıtımı EKRANDA (eskiden option.title'da gömülüydü).
            assert page.eval_on_selector_all("#model-sheet-list input[type=radio]",
                                             "e => e.length") > 1
            secili_once = page.input_value("#model")
            assert page.eval_on_selector("#model-sheet-list input:checked",
                                         "e => e.value") == secili_once
            assert page.eval_on_selector_all(
                "#model-sheet-list .model-row-txt > span", "e => e.length") > 0, (
                "kartlarda model tanıtımı yok")

            # 3. Başka bir model seç → <select>, çip etiketi ve tercih birlikte.
            degerler = page.eval_on_selector_all("#model-sheet-list input",
                                                 "e => e.map(x => x.value)")
            yeni = next(v for v in degerler if v != secili_once)
            prefs_posts.clear()
            page.check(f'#model-sheet-list input[value="{yeni}"]')
            page.wait_for_function(f'document.querySelector("#model").value === "{yeni}"')
            assert page.inner_text("#model-btn-label").strip(), "çip etiketi boş"
            page.wait_for_timeout(400)
            assert len(prefs_posts) == 1, (
                f"tercih {len(prefs_posts)} kez yazıldı — bir kez yazılmalı")

            # 4. AYNI karta ikinci dokunuş: ikinci POST YOK.
            prefs_posts.clear()
            page.click(f'#model-sheet-list input[value="{yeni}"]')
            page.wait_for_timeout(400)
            assert not prefs_posts, "aynı değere ikinci dokunuş diske yazıyor"

            # 5. Escape kapatıyor, odak çipe DÖNÜYOR, seçim bozulmuyor.
            page.keyboard.press("Escape")
            page.wait_for_selector("#model-sheet:not(.open)")
            assert page.evaluate("document.activeElement.id") == "model-btn", (
                "odak tetikleyiciye dönmüyor — klavye kullanıcısı sayfanın "
                "başına düşüyor")
            assert page.get_attribute("#model-btn", "aria-expanded") == "false"
            assert page.input_value("#model") == yeni

            # 6. Yönetmen ekseni AYNI paneli kullanıyor.
            page.click("#tab-chat")
            page.wait_for_function(
                'document.querySelector("#composer").getAttribute("data-mode") === "director"')
            page.click("#chat-model-btn")
            page.wait_for_selector("#model-sheet.open")
            assert page.inner_text("#model-sheet-title").strip() == "Yönetmen modeli"
            assert page.eval_on_selector("#model-sheet-list input:checked",
                                         "e => e.value") == page.input_value("#chat-model")
            page.keyboard.press("Escape")
            page.click("#tab-image")

            # 7. 360px'de yatay kayma YOK (ölçülmüş kırılma).
            page.set_viewport_size({"width": 360, "height": 780})
            page.wait_for_timeout(300)
            kaydi = page.evaluate("document.documentElement.scrollWidth >"
                                  " document.documentElement.clientWidth")
            assert not kaydi, "360px'de sayfa yatay kayıyor — composer taşıyor"

            # 8. Masaüstünde ORTALANMIŞ: `translateX` ile ortalanmış bir panel
            #    `.sheet.open { transform: none }` yüzünden sağa kayardı ve bu
            #    yalnız 520px'ten geniş pencerede görünür.
            page.set_viewport_size({"width": 1280, "height": 860})
            page.wait_for_timeout(200)
            page.click("#model-btn")
            page.wait_for_selector("#model-sheet.open")
            page.wait_for_function(
                'getComputedStyle(document.querySelector("#model-sheet")).transform === "none"')
            kenar = page.eval_on_selector(
                "#model-sheet",
                "e => { const b = e.getBoundingClientRect();"
                " return [b.left, 1280 - b.right]; }")
            assert abs(kenar[0] - kenar[1]) < 2, (
                f"panel ortalanmamış (sol {kenar[0]}, sağ {kenar[1]}) — yatay "
                "ortalama transform ile yapılmışsa `.sheet.open` onu siliyor")

            browser.close()
    finally:
        server.stop()


def test_playwright_ayarlar_paneli_alttan_ve_ALANLARI_gosteriyor():
    """Dişliyle açılan Ayarlar: alttan geliyor VE sağlayıcı alanları görünüyor.

    İkinci yarısı bu turda bulunan bir kırılmanın mandalı ve kırılma bu
    değişiklikten ÖNCE de vardı: `$("settings-btn").addEventListener("click",
    openSettings)` fonksiyona MouseEvent geçiriyordu, `provider` truthy
    oluyordu, `select.value` eşleşmeyen bir dizeye atanıp seçim düşüyordu ve
    `syncProviderFields` üç alan grubunun hepsini gizliyordu. Yani dişliye
    basan kullanıcı anahtar kutusu OLMAYAN bir Ayarlar paneli görüyordu.

    Kaynak taraması bunu yakalamıyor (kod her iki hâlde de "geçerli"), konsola
    da hata düşmüyor — `select.value`ya geçersiz atama sessiz.
    """
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    time.sleep(1.0)
    base_url = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(base_url)
            page.wait_for_selector("#set-provider")
            page.wait_for_timeout(800)
            if page.query_selector(".sheet.open"):
                page.keyboard.press("Escape")
                page.wait_for_selector(".sheet.open", state="detached")

            page.click("#settings-btn")
            page.wait_for_selector("#settings-modal.open")
            page.wait_for_function(
                'getComputedStyle(document.querySelector("#settings-modal")).transform'
                ' === "none"')

            box = page.eval_on_selector("#settings-modal", "e => e.getBoundingClientRect()")
            assert abs(box["bottom"] - 844) < 2, f"Ayarlar alt kenara dayanmıyor: {box}"
            assert box["top"] > 0, "Ayarlar tepeye dayanmış — alttan açılmıyor"

            # Sağlayıcı seçimi AYAKTA ve bir alan grubu görünür.
            assert page.input_value("#set-provider") == "azure", (
                "dişliyle açılınca sağlayıcı seçimi düşüyor — bütün anahtar "
                "kutuları gizlenir")
            gizli = page.evaluate(
                """() => ["azure", "openai", "gemini"]
                     .filter(p => !document.querySelector(`#prov-${p}`).hidden)""")
            assert gizli == ["azure"], f"görünen alan grubu beklenenden farklı: {gizli}"

            # "Kaydet" panelin dibinde: gövde kaydırılmadan erişilebilir.
            kaydet = page.eval_on_selector("#settings-save", "e => e.getBoundingClientRect()")
            assert 0 <= kaydet["top"] and kaydet["bottom"] <= 844, (
                f"Kaydet görünür alanın dışında: {kaydet}")

            # Odak metin kutusunda DEĞİL: alttan açılan panelde yazılım
            # klavyesi panelin yarısını yutuyor.
            assert page.evaluate("document.activeElement.id") != "set-endpoint"

            browser.close()
    finally:
        server.stop()
