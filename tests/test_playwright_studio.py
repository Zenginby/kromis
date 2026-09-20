"""Playwright End-to-End Tests for Step 13 (Tek Döküm, Tek Composer — studio-session.html).

Tests:
1. Studio session loads single section #view-studio with sole textarea #prompt and submit button #go.
2. Mode switching updates data-mode, button label, and placeholder.
3. Keydown Enter submits composer according to active mode.
4. Reference chip image #ref-chip-img is created inside #ref-chip.
5. Single click on #go triggers submission without duplicate listener execution.
"""
from __future__ import annotations

import io
import os
import socket
import threading
import time
import traceback

import pytest
import uvicorn

# Playwright isteğe bağlı bir bağımlılık: CI derleme işlerinde (build-macos-arm64)
# kurulu değil. Modül düzeyinde importorskip tüm test dosyasını atlar ve
# pytest'in toplama hatası (ImportError) yerine temiz bir SKIP üretir.
pytest.importorskip("playwright", reason="playwright kurulu değil — E2E testleri atlanıyor")

from playwright.sync_api import sync_playwright

import catalog
import credstore
from app import app

# Kapı GERÇEK (Faz 1 / 4): sunucu aynı süreçte, `veritabani` fixture'ı Postgres'i
# verir, `e2e_oturum` DB'ye kullanıcı yazıp çerezi tarayıcıya koyar (conftest).
# conftest'in autouse override'ı burada KURULMAZ — kurulsa çerez anlamsız
# olurdu ve bu dosya "oturumlu stüdyo"yu değil "kapısız stüdyo"yu ölçerdi.
pytestmark = pytest.mark.gercek_kimlik


def _ilk_kurulum_perdesini_kapat(page) -> None:
    """İlk kurulumda kendiliğinden açılan Ayarlar panelini kapatır.

    NEDEN ORTAK YARDIMCI: üç test de aynı perdeyi kapatıyordu ama ÜÇ AYRI
    çapaya bakarak — biri sayfa iskeletine (`#view-studio`), biri kataloğa,
    biri `#set-provider` + 800ms uykuya. İlkinin çapası panelden ÖNCE geliyor:
    `loadSettings` `/api/settings`i BEKLİYOR, yani iskelet hazırken karar
    henüz verilmemiş oluyor ve "açıksa kapat" iddiası boşa düşüyor. Panel
    sonra açılıyor, ortak perde (#shell-scrim) composer'ı yutuyor ve sıradaki
    tıklama 30 saniye bekleyip "intercepts pointer events" diye düşüyor.

    Yani kusur bir YARIŞTI ve testin hızına bağlıydı: sunucu sıcakken yanıt
    çapadan önce dönüyor, panel açılıyor, kapatma tutuyor ve test yeşil
    kalıyordu. Soğuk ilk koşumda (bu depoda ölçüldü) yanıt geç kalıyor ve
    aynı test kırmızı. Bir yarışı 800ms uykuyla kapatmak da aynı kusurun
    yavaş hâli, o yüzden o satır da gitti.

    ÇAPA `#model`in DEĞERİ: `loadSettings` yanıtı uyguladıktan sonra
    `openSettings()` kararını AYNI senkron blokta veriyor (`applyConfigured`
    → `applyModels` → `#model.value`, hemen ardından `if (…) openSettings()`).
    Değer görünür olduğunda karar VERİLMİŞTİR — JS tek iş parçacıklı, araya
    bir poll giremez. `|| .sheet.open` ikinci dalı fail-closed yol için:
    `/api/settings` hata verirse katalog boş kalıyor (`imageModels = []`) ve
    panel yine açılıyor, o dalda çapa panelin kendisi.
    """
    page.wait_for_function(
        '() => { const m = document.querySelector("#model");'
        ' return (m && m.value !== "") || !!document.querySelector(".sheet.open"); }')
    if page.query_selector(".sheet.open"):
        page.keyboard.press("Escape")
        # BEKLENEN KOŞUL `.open` SINIFININ GİTMESİ DEĞİL, PANELİN GERÇEKTEN
        # ÇEKİLMESİ. `closeSheets()` sınıfı ANINDA kaldırıyor, ama style.css
        # görünürlüğü bilerek geciktiriyor:
        #     .sheet { visibility: hidden;
        #              transition: transform var(--dur), visibility 0s linear var(--dur) }
        # yani panel sınıf gittikten SONRA 180ms daha `visibility: visible`
        # kalıyor (kapanma animasyonu görünsün diye) ve o pencerede isabet
        # testini YUTMAYA DEVAM EDİYOR.
        #
        # Bedeli ölçüldü (2026-09-11, CI'da Playwright ilk kez koşarken):
        # `test_..._karonun_ortasi_gercekten_seciyor` karonun ortasında
        # `DIV.settings-panes` buluyordu — `.sheet.open` çoktan yokken. Kırılma
        # yalnız panelin AÇILDIĞI makinede görünüyor, yani kimliksiz olanda:
        # CI'da kırmızı, kimlikleri kayıtlı geliştiricide yeşil.
        #
        # `visibility` doğru çapa çünkü isabet testini kesen ŞEY o; `transform`
        # bitse de `visibility: visible` kalan bir panel tıklamayı yutardı.
        page.wait_for_function(
            '() => [...document.querySelectorAll(".sheet")]'
            '.every((s) => getComputedStyle(s).visibility === "hidden")')


def _tum_kimlikler_kayitli(monkeypatch) -> None:
    """Sunucuyu "her sağlayıcının anahtarı kayıtlı" hâline getirir.

    NEDEN GEREKLİ: anahtarı girilmemiş modeller artık şeride HİÇ girmiyor
    (core.js `secilebilirler`; kullanıcı isteği). Anahtarsız bir sunucuda model
    paneli haklı olarak BOŞ açılıyor, yani kart/radyo hakkında ne söylenirse
    söylensin ölçülen şey panelin boşluğu olurdu. Bu testin ölçtüğü dört
    tarayıcı gerçeği (panelin alt kenardan yükselmesi, tercihin diske TEK kez
    yazılması, odağın çipe dönmesi, 360px'de kaymama) kartlar VARKEN anlamlı.

    `monkeypatch` gerçekten işliyor çünkü `ServerThread` uygulamayı AYNI süreçte
    koşturuyor: uç nokta `credstore.configured_map`i modül üzerinden çağırıyor.
    Diske hiçbir şey yazılmıyor — gerçek `credentials.env`e dokunmak,
    geliştiricinin kendi kurulumunu değiştirmek olurdu.
    """
    monkeypatch.setattr(
        credstore, "configured_map",
        lambda *a, **k: {c.id: True for c in catalog.CREDENTIALS})
    monkeypatch.setattr(
        credstore, "chat_configured_map",
        lambda *a, **k: {m.id: True for m in catalog.CHAT_MODELS})


def _hicbir_kimlik_kayitli_degil(monkeypatch) -> None:
    """Sunucuyu "hiçbir sağlayıcının anahtarı yok" hâline getirir.

    NEDEN GEREKLİ: `credstore` GERÇEK kimlik deposunu okuyor ve `ServerThread`
    uygulamayı aynı süreçte koşturuyor. Yani "anahtarsız kurulum" öncülü,
    kurgulanmadığı sürece TESTİN DEĞİL, testi koşturan MAKİNENİN özelliği
    oluyordu: CI'da (kimliksiz) yeşil, geliştiricinin kendi makinesinde
    (kimlikleri kayıtlı) kırmızı. Bu depoda ölçüldü — `configured_map()`
    azure_image/azure_chat/gemini/azure_foundry için True dönüyor, `loadSettings`
    paneli haklı olarak AÇMIYOR ve `.sheet.open` beklemesi 30sn'de düşüyordu.

    Kırmızının anlattığı şey uygulamayla ilgili DEĞİLDİ, o yüzden okuyanı da
    kaynağa götürmüyordu. `_tum_kimlikler_kayitli`nin tersi; ikisi de aynı
    duruşun parçası: öncül kurguyla kurulur, ortamdan UMULMAZ.
    """
    monkeypatch.setattr(credstore, "configured_map", lambda *a, **k: {})
    monkeypatch.setattr(credstore, "chat_configured_map", lambda *a, **k: {})


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def sunucu_hazir(port: int, tavan_sn: float = 10.0) -> None:
    """Uvicorn dinlemeye BAŞLAYANA KADAR yoklar — sabit uyku yerine.

    NEDEN: burada eskiden `time.sleep(1.0)` vardı ve bir saniye bir TAHMİNDİ.
    İki ucu da ıskalıyor: yüklü bir CI koşucusunda yetmiyor ve kusur ürünle
    ilgisi olmayan bir kırmızı olarak, `page.goto`da "connection refused"
    diye çıkıyor; bu makinede ise uvicorn ~0,15 sn'de dinlemeye başlıyor,
    yani her çağrı ~0,85 sn'yi boşa yakıyordu. Aynı gizli kırılganlık sınıfı
    e32e297 ve 1886360'ta kayıtlı, CLAUDE.md §3'te de anlatılıyor. Koşul
    yoklandığında iki uç birden kapanıyor: yavaş makine bekler, hızlısı
    beklemez.

    TAVAN VE İDDİA: yoklama sonsuz değil, yoksa sunucu hiç açılmadığında
    test "hangi adımda takıldı" demeden asılı kalırdı. Tavana varılırsa
    düşen şey portu ADIYLA söyleyen bir iddia — sonraki `page.goto`nun
    anlamsız "connection refused"ı değil.

    Deyim `tests/test_playwright_hesap.py`'deki `_bekle`den geliyor.
    """
    son = time.monotonic() + tavan_sn
    while time.monotonic() < son:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise AssertionError(
        f"sunucu {tavan_sn:g} sn içinde 127.0.0.1:{port} adresinde dinlemeye başlamadı")


class IsciThread(threading.Thread):
    """E2E'nin İŞÇİSİ: `isci.tek_tur` döngüsü, sunucuyla aynı süreçte (Faz 2 / 4).

    Üretim rotaları 202 döner ve sonucu bir işçi yazar (services/isci.py);
    tarayıcı akışı "üret → galeri" ancak kuyruğu boşaltan biri varsa biter.
    Süreç DEĞİL iş parçacığı (belge §3/§4: "testlerde işçi süreç değil
    işlev"): sağlayıcı yaması (`monkeypatch`) aynı süreçte işlesin, port ve
    alt süreç yönetimi olmasın. Kuyruk GERÇEK (aynı Postgres), depo ve
    yerleşim sunucununkiler (`app.state.dosya`, `app.state.ayarlar` — E2E
    fixture'ı ikisini de `tmp_path`e çekti). Boş kuyrukta 0,2 sn uyur; hata
    döngüyü ÖLDÜRMEZ (izi basar, sürer) — sessizce duran işçi, 30 sn sonra
    "galeri boş" diye düşen ve sebebini söylemeyen bir test demek.
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.dur = threading.Event()

    def run(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from services import db as db_modulu
        from services import isci

        motor = create_engine(os.environ[db_modulu.DATABASE_URL_ENV], pool_size=1, max_overflow=1)
        try:
            while not self.dur.is_set():
                kostu = False
                try:
                    with Session(motor) as oturum:
                        kostu = isci.tek_tur(oturum, app.state.dosya, ayarlar=app.state.ayarlar)
                except Exception:      # noqa: BLE001 — işçi döngüsü istisnada ölmez (services/isci.py kararı)
                    traceback.print_exc()
                if not kostu:
                    self.dur.wait(0.2)
        finally:
            motor.dispose()

    def stop(self):
        self.dur.set()


class ServerThread(threading.Thread):
    """uvicorn + işçi, ikisi de daemon iş parçacığı; `stop()` ikisini de durdurur."""

    def __init__(self, port: int):
        super().__init__(daemon=True)
        self.port = port
        self.config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
        self.server = uvicorn.Server(self.config)
        self.isci = IsciThread()

    def start(self):
        super().start()
        self.isci.start()

    def run(self):
        self.server.run()

    def stop(self):
        self.isci.stop()
        self.server.should_exit = True


def test_playwright_studio_single_thread_flow(veritabani, e2e_oturum):
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)

    base_url = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1. Open Studio application
            oturum.cerez(page, base_url)

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
            #
            # Kapatma buradan YARDIMCIYA taşındı: bu satırlar `#view-studio`
            # göründüğü an koşuyordu, yani panel açılmadan ÖNCE — kusuru
            # yalnızca yavaş koşumda gösteren bir yarış. Gerekçe yardımcının
            # kendi notunda.
            _ilk_kurulum_perdesini_kapat(page)

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
            assert page.inner_text("#go").strip() == "Generate"
            assert "What do you want to create?" in prompt.get_attribute("placeholder")

            # 5. Switch to Director mode
            page.click("#tab-chat")
            page.wait_for_function('document.querySelector("#composer").getAttribute("data-mode") === "director"')
            assert page.inner_text("#go").strip() == "Send"
            assert "Ask the Director" in prompt.get_attribute("placeholder")

            # 6. Switch back to Image mode
            page.click("#tab-image")
            page.wait_for_function('document.querySelector("#composer").getAttribute("data-mode") === "image"')
            assert page.inner_text("#go").strip() == "Generate"

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


def test_playwright_model_sheet_alttan_aciliyor(monkeypatch, veritabani, e2e_oturum):
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
    _tum_kimlikler_kayitli(monkeypatch)
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)
    base_url = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            prefs_posts = []
            page.on("request", lambda r: prefs_posts.append(r.url)
                    if r.method == "POST" and "/api/prefs" in r.url else None)

            oturum.cerez(page, base_url)


            page.goto(base_url)
            # Yardımcı KALIYOR ama artık asıl işi KATALOĞU BEKLEMEK: bu test
            # kimlikleri kayıtlı gösterdiği için Ayarlar kendiliğinden açılmıyor
            # (settings.js yalnız hiçbir model kurulu değilken açıyor). Çapa
            # `#model`in değeri, yani panelden önce kataloğun geldiği kesin.
            _ilk_kurulum_perdesini_kapat(page)

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
            assert page.inner_text("#model-sheet-title").strip() == "Director model"
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


def test_playwright_ayarlar_paneli_ortadan_ve_ALANLARI_gosteriyor(veritabani, e2e_oturum):
    """Dişliyle açılan Ayarlar: ORTADAN geliyor VE sağlayıcı alanları görünüyor.

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
    oturum = e2e_oturum()
    sunucu_hazir(port)
    base_url = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            oturum.cerez(page, base_url)

            page.goto(base_url)
            # `state="attached"`: seçici artık `.sr-only` (değeri tutan kutu
            # gizli, görünen yüz `#set-provider-btn`) ve varsayılan "visible"
            # ölçütü bir gün `.sr-only`nin 1x1 kutusuna takılırdı. Burada
            # sorulan şey zaten "iskelet geldi mi", görünürlük değil.
            page.wait_for_selector("#set-provider", state="attached")
            # 800ms'lik uyku KALKTI: yarışı yavaşlatmak kapatmak değil.
            _ilk_kurulum_perdesini_kapat(page)

            page.click("#settings-btn")
            page.wait_for_selector("#settings-modal.open")
            page.wait_for_function(
                'getComputedStyle(document.querySelector("#settings-modal")).transform'
                ' === "none"')

            # DİKEY ORTALAMA tarayıcıda ölçülüyor: `.sheet-center` konumu
            # `inset: 0` + `margin: auto` ile kuruyor ve `.sheet.open`ın
            # `transform: none`u onu silmiyor. transform'la kurulsaydı kaynak
            # taraması "ortalanmış" der, ekran köşeye kaymış bir pencere
            # gösterirdi — `.sheet-bottom`un ölçülmüş tuzağının aynısı.
            # 390x844'te pencere TAM EKRAN (mobile.css), o yüzden iki hâl de
            # kabul: ya iki kenardan eşit uzaklıkta ya da ekranı kaplıyor.
            box = page.eval_on_selector("#settings-modal", "e => e.getBoundingClientRect()")
            ust, alt = box["top"], 844 - box["bottom"]
            assert abs(ust - alt) < 2, (
                f"Ayarlar dikeyde ortalanmamış (üst {ust}, alt {alt}): {box}")
            sol, sag = box["left"], 390 - box["right"]
            assert abs(sol - sag) < 2, (
                f"Ayarlar yatayda ortalanmamış (sol {sol}, sağ {sag}): {box}")

            # Sağlayıcı seçimi AYAKTA ve bir alan grubu görünür.
            # Değer DOM'dan okunuyor: kutu `.sr-only`, yani görünürlük
            # gerektiren bir yardımcıya bağlanmanın anlamı yok.
            assert page.eval_on_selector("#set-provider", "e => e.value") == "azure", (
                "dişliyle açılınca sağlayıcı seçimi düşüyor — bütün anahtar "
                "kutuları gizlenir")
            gizli = page.evaluate(
                """() => ["azure", "openai", "gemini", "fal"]
                     .filter(p => !document.querySelector(`#prov-${p}`).hidden)""")
            assert gizli == ["azure"], f"görünen alan grubu beklenenden farklı: {gizli}"

            # "Kaydet" panelin dibinde: gövde kaydırılmadan erişilebilir.
            kaydet = page.eval_on_selector("#settings-save", "e => e.getBoundingClientRect()")
            assert 0 <= kaydet["top"] and kaydet["bottom"] <= 844, (
                f"Kaydet görünür alanın dışında: {kaydet}")

            # Odak metin kutusunda DEĞİL: bir metin kutusuna odaklanmak
            # Android'de yazılım klavyesini açıyor ve klavye pencereyi yutuyor.
            assert page.evaluate("document.activeElement.id") != "set-endpoint"

            # SAĞLAYICI PENCERESİ: ortadan açılıyor, Ayarlar AÇIK KALIYOR ve
            # Escape yalnız üstteki katmanı kapatıyor. Üçü de yalnız tarayıcıda
            # ölçülebilir — Escape sırası (yakalama evresi) kaynak taramasında
            # "geçerli" görünen iki farklı hâlden birini seçmek demek.
            page.click("#set-provider-btn")
            page.wait_for_selector("#provider-modal:not([hidden])")
            kartlar = page.eval_on_selector_all("#provider-list input", "e => e.length")
            # DÖRT: azure · openai · gemini · fal. Sayı `settings.js`teki
            # sağlayıcı listesinden geliyor, yani kart çizmeyi unutan bir
            # sağlayıcı eklenirse burada düşüyor. fal 0.23'te girdi.
            assert kartlar == 4, f"sağlayıcı kartları çizilmedi: {kartlar}"
            page.keyboard.press("Escape")
            # `state="attached"`: `[hidden]` bir öğe hiçbir zaman "visible"
            # olmuyor, yani varsayılan ölçütle bu satır zaman aşımına düşerdi.
            page.wait_for_selector("#provider-modal[hidden]", state="attached")
            assert page.is_visible("#settings-modal.open"), (
                "Escape iki katmanı birden kapattı — muhafız yakalama "
                "evresinde değil (core.js'in dinleyicisi ÖNCE kayıtlı)")

            # Seçim `<select>`e yönleniyor: kart → değer → alan grubu.
            page.click("#set-provider-btn")
            page.wait_for_selector("#provider-modal:not([hidden])")
            page.click("#provider-list input[value='gemini']")
            page.wait_for_selector("#provider-modal[hidden]", state="attached")
            assert page.eval_on_selector("#set-provider", "e => e.value") == "gemini", (
                "kart seçimi <select>e yönlenmiyor")
            gorunen = page.evaluate(
                """() => ["azure", "openai", "gemini"]
                     .filter(p => !document.querySelector(`#prov-${p}`).hidden)""")
            assert gorunen == ["gemini"], f"alan grubu değişmedi: {gorunen}"

            browser.close()
    finally:
        server.stop()


def test_playwright_yukleme_hedefi_ve_ek_gorsel_kapisi(veritabani, e2e_oturum):
    """İki sessiz kusurun tarayıcıdaki hâli — ikisi de DİSKE HİÇ DOKUNMADAN.

    Statik bekçileri `tests/test_index.py`'de; buradaki iddia kaynağın değil
    ÇALIŞAN arayüzün ne yaptığı, çünkü iki kusurun ikisi de "hiçbir hata
    vermeden hiçbir şey olmuyor" sınıfındaydı:

    1. **Kütüphane.** Sekme şeridi bir filtre, hedef değil; "Tümü" seçiliyken
       yükleme `uploads` türüne gidiyordu ve o türü hiçbir bindirme okuyamıyor
       — logo yükleniyor, logo hiçbir yerde görünmüyordu. Düğmenin etiketi
       artık hedefi SÖYLÜYOR, burada okunan o.
    2. **Ek görsel.** Ana referans yokken dosya seçici koşulsuz açılıyor,
       kullanıcı dosyayı seçiyor ve dosya `addExtraUpload`ın kapısında sessizce
       düşüyordu. Artık seçici HİÇ açılmıyor, gerekçe yazılıyor.

    Yükleme YAPILMIYOR: bu dosya gerçek `app`i koşuyor, yani bir POST
    kullanıcının asıl varlık dizinine yazardı. Ölçülen şey zaten yüklemenin
    ÖNCESİ — hedefin görünürlüğü ve seçicinin açılıp açılmadığı.
    """
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            oturum.cerez(page, f"http://127.0.0.1:{port}")

            page.goto(f"http://127.0.0.1:{port}")
            page.wait_for_selector("#view-studio")
            _ilk_kurulum_perdesini_kapat(page)

            # 1. Kütüphane: varsayılan sekme "Tümü" ve düğme hedefi söylüyor.
            page.click("#rail-library")
            page.wait_for_selector("#view-library:not([hidden])")
            assert page.inner_text("#asset-tabs button.active").strip() == "All"
            assert page.inner_text("#asset-upload-label").strip() == "Upload a logo", (
                "yükleme düğmesi hedefini söylemiyor")
            page.click('#asset-tabs button[data-akind="banners"]')
            assert page.inner_text("#asset-upload-label").strip() == "Upload a banner", (
                "sekme değişti, etiket bayat kaldı")
            assert page.query_selector('#asset-tabs button[data-akind="uploads"]') is None, (
                "kullanılamaz `uploads` türü hâlâ bir yükleme hedefi")

            # 2. Ek görsel: ana referans YOKKEN seçici açılmamalı.
            page.evaluate('showSection("studio")')
            page.click("#plus-btn")
            page.wait_for_selector("#plus-menu:not([hidden])")
            secici_acildi = True
            try:
                with page.expect_event("filechooser", timeout=1500):
                    page.click("#extra-add-btn")
            except Exception:
                secici_acildi = False
            assert not secici_acildi, (
                "ana referans yokken dosya seçici açılıyor — seçilen dosya "
                "kapıda sessizce düşer")
            assert "Pick the main image first." in page.inner_text("#status"), (
                "engel sessiz: kullanıcı neden hiçbir şey olmadığını okumuyor")

            browser.close()
    finally:
        server.stop()


def test_playwright_secilen_dosya_kapisi_TELEFONUN_gercegine_dayaniyor(veritabani, e2e_oturum):
    """`isAcceptedUpload` doğruluk tablosu — TARAYICIDA, saf işlev olarak.

    Bu kapının kusuru yalnız telefonda görünüyordu: Android WebView `File.type`ı
    ContentResolver'dan alıyor ve birçok sağlayıcı MIME yerine boş dize ya da
    `application/octet-stream` veriyor, bazıları dosya adını uzantısız veriyor.
    Yalnız türe bakan eski kapı o dosyaları — kullanıcı gerçekten PNG seçmiş
    olsa bile — "PNG, JPEG veya WebP bir görsel seç" diye geri çeviriyordu.

    Statik bekçisi `tests/test_mobile.py`'de; buradaki iddia işlevin GERÇEKTEN
    ne döndürdüğü. Tablo iki yönlü: telefonun ürettiği eksik bilgi geçmek
    zorunda, karşı kanıt taşıyan dosya (`.heic`, `.pdf`, `.gif`) düşmek zorunda
    — kapı tümden kalkmış olmasın.

    Hiçbir şey YÜKLENMİYOR: işlev saf, diske dokunulmuyor.
    """
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)

    # (ad, tür, beklenen) — telefonun gerçek ürettiği hâller ve karşı kanıtlar.
    TABLO = [
        ("a.png", "image/png", True),
        ("kurumsal-logo.JPG", "", True),                       # tür bildirilmemiş
        ("logo.png", "application/octet-stream", True),    # sağlayıcı "bilmiyorum"
        ("IMG_0042", "", True),                            # ne tür ne uzantı
        ("content-9182", "application/octet-stream", True),
        ("foto.heic", "image/heic", False),
        ("foto.heic", "", False),                          # uzantı karşı kanıt
        ("belge.pdf", "application/pdf", False),
        ("anim.gif", "image/gif", False),
    ]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            oturum.cerez(page, f"http://127.0.0.1:{port}")

            page.goto(f"http://127.0.0.1:{port}")
            page.wait_for_selector("#view-studio")
            _ilk_kurulum_perdesini_kapat(page)

            for ad, tur, beklenen in TABLO:
                sonuc = page.evaluate(
                    "(f) => isAcceptedUpload(f)", {"name": ad, "type": tur})
                assert sonuc is beklenen, (
                    f"isAcceptedUpload({ad!r}, {tur!r}) = {sonuc}, "
                    f"beklenen {beklenen}")

            assert page.evaluate("isAcceptedUpload(null)") is False, (
                "dosya yokken kapı açık")

            browser.close()
    finally:
        server.stop()


def test_playwright_secim_modunda_karonun_ortasi_gercekten_seciyor(veritabani, e2e_oturum):
    """Seçim modunda karonun ORTASINA basmak seçmeli — TARAYICIDA ölçülüyor.

    Kusur telefonda klasöre taşımayı tümden imkânsız kılıyordu ve statik bir
    iddiayla yakalanamaz, çünkü soru "hangi CSS kuralı var" değil "o noktada
    ISABET EDEN öğe hangisi": `.card .acts` şeridi karonun alt bandını kaplıyor
    ve dokunmatikte SÜREKLİ görünür, `.card-del`in de görünmez 44×44 hedefi var.
    Kart tıklaması ikisini dışlıyor (`closest(".acts, .card-del, .card-check")`),
    yani şeride düşen bir dokunuş seçmiyor — üstelik "Referans" düğmesine
    denk gelirse uygulama Stüdyo'ya ATLIYOR ve kullanıcı galeriden düşüyor.

    Ölçü `elementFromPoint` + gerçek tıklama; DİSKE HİÇ DOKUNULMUYOR: galeri
    kaydı `historyCache`e elle konuyor ve `renderGallery()` çağrılıyor (küçük
    resmin 404 olması ölçülen şeyi etkilemiyor — isabet testi yerleşim üstünde).
    Dokunmatik ölçüsü telefon genişliğinde alınıyor: şerit orada da sarmıyor
    ama karo en küçük hâlinde.
    """
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 780})
            oturum.cerez(page, f"http://127.0.0.1:{port}")

            page.goto(f"http://127.0.0.1:{port}")
            page.wait_for_selector("#view-studio")
            _ilk_kurulum_perdesini_kapat(page)

            # Galeriyi elle tohumla: tek kayıt, S ızgara (karonun en küçük hâli).
            page.evaluate("""() => {
                showSection("media");
                historyCache = [{id: "abc123abc123",
                                 filename: "abc123abc123.png",
                                 prompt: "deneme"}];
                renderGallery();
            }""")
            page.wait_for_selector("#gallery .card")

            # Şerit gerçekten ekranda mı? Değilse bu testin öncülü düşmüş olur.
            assert page.eval_on_selector(
                "#gallery .card .acts",
                "el => getComputedStyle(el).display !== 'none'"), (
                "eylem şeridi seçim DIŞI modda da gizli — testin öncülü düştü")

            page.evaluate("setSelectMode(true)")
            page.wait_for_selector("#gallery .card .card-check")

            # 1. İSABET: karonun tam ortasındaki nokta kartın kendisine düşmeli.
            isabet = page.eval_on_selector("#gallery .card", """el => {
                const r = el.getBoundingClientRect();
                const hedef = document.elementFromPoint(r.left + r.width / 2,
                                                        r.top + r.height / 2);
                return {
                    kart: el.contains(hedef),
                    engel: hedef && hedef.closest(".acts, .card-del") ? true : false,
                };
            }""")
            assert isabet["kart"], "karonun ortası kartın dışında bir öğeye düşüyor"
            assert not isabet["engel"], (
                "karonun ORTASI eylem şeridine/silme düğmesine düşüyor — dokunuş "
                "seçmiyor, 'Referans'a denk gelirse uygulama Stüdyo'ya atlıyor")

            # 2. DAVRANIŞ: o noktaya tıklamak seçiyor ve Medya'da kalıyoruz.
            page.click("#gallery .card")
            assert page.eval_on_selector(
                "#gallery .card", "el => el.classList.contains('selected')"), (
                "karonun ortasına tıklamak seçmedi")
            assert page.is_visible("#view-media"), (
                "tıklama uygulamayı Medya'dan attı — 'Referans' tetiklenmiş")
            assert page.eval_on_selector(
                "#select-move", "el => !el.disabled"), (
                "seçim var ama 'Taşı…' hâlâ kapalı")

            browser.close()
    finally:
        server.stop()


def test_playwright_buyutecte_logo_ekle_kayitli_gorselde_beliriyor(veritabani, e2e_oturum):
    """Büyeteçteki "Logo ekle" yalnız KAYITLI bir görselde görünmeli.

    İki yarım, ikisi de tarayıcıda: düğme `/output/…` taşıyan bir kaynakta
    beliriyor, `blob:` taşıyan (henüz kaydedilmemiş yükleme) bir kaynakta
    "İndir" ile birlikte gizli kalıyor. İkisi tek ayrıştırmadan besleniyor
    (`kayitOku`), yani bu test o dikişin ayrışmadığını da ölçüyor.

    Bindirme penceresi AÇILMIYOR: `/api/logo/preview` gerçek sunucuya gider.
    Ölçülen şey düğmenin görünürlüğü ve türettiği kayıt.
    """
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            oturum.cerez(page, f"http://127.0.0.1:{port}")

            page.goto(f"http://127.0.0.1:{port}")
            page.wait_for_selector("#view-studio")
            _ilk_kurulum_perdesini_kapat(page)

            page.evaluate('openViewer("/output/abc123abc123.png", "deneme")')
            page.wait_for_selector("#viewer:not([hidden])")
            assert page.is_visible("#viewer-logo"), (
                "kayıtlı görselde bindirme kapısı yok")
            assert page.is_visible("#viewer-download"), "testin öncülü düştü"

            # Kaydedilmemiş yükleme: iki düğme de çekilmeli.
            page.evaluate('openViewer("blob:http://localhost/deneme", "yerel")')
            assert page.is_hidden("#viewer-logo"), (
                "kaydedilmemiş görselde bindirme düğmesi duruyor — /api/logo "
                "kaynağı diskte bulamaz")
            assert page.is_hidden("#viewer-download"), "indirme muhafızı düşmüş"

            browser.close()
    finally:
        server.stop()


def test_playwright_anahtarsiz_acilis_BOS_HALI_anlatiyor(monkeypatch, veritabani, e2e_oturum):
    """Anahtar yokken şerit ve panel BOŞ HÂLİ anlatıyor, boş kalmıyor.

    Bu, kullanıcı isteğinin ("API key'i girilmeyen modeller gözükmesin")
    doğrudan bedeli ve tam olarak yalnız tarayıcıda ölçülebilen kısmı: filtre
    listeyi boşaltabildiği andan itibaren `applyModel` seçili model BULAMIYOR ve
    eski kodda erken çıkıyordu — çip "Modeller yükleniyor…" yazısında DONUYOR,
    kullanıcı sonsuza kadar yüklenen bir şerit görüyordu. Kaynak taraması bunu
    yakalayamaz: her iki hâlde de kod "doğru" görünüyor, fark ekranda.

    ÖNCÜL KURGULANIYOR. Burada "kimlikler bilerek kurgulanmıyor, bu testin
    öncülü zaten anahtarsız bir kurulum (CI'ın varsayılan hâli)" yazıyordu ve
    o cümle testi CI'a bağımlı kılıyordu: `credstore` gerçek kimlik deposunu
    okuduğu için öncül, testin değil MAKİNENİN özelliğiydi — kimlikleri kayıtlı
    her geliştiricide bu test kırmızıydı ve kırmızısı uygulama hakkında hiçbir
    şey söylemiyordu (bkz. `_hicbir_kimlik_kayitli_degil`).
    """
    _hicbir_kimlik_kayitli_degil(monkeypatch)
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            oturum.cerez(page, f"http://127.0.0.1:{port}")

            page.goto(f"http://127.0.0.1:{port}")
            page.wait_for_selector("#view-studio")
            # Ayarlar KENDİLİĞİNDEN açılıyor: kullanıcının çıkmaz sokakta
            # olmadığının birinci kanıtı ve kapının kapanabilmesinin sebebi.
            page.wait_for_selector(".sheet.open")
            _ilk_kurulum_perdesini_kapat(page)

            # 1. Çip boş hâli SÖYLÜYOR — yükleniyor yazısında donmuyor.
            etiket = page.inner_text("#model-btn-label").strip()
            assert "loading" not in etiket.lower(), (
                f"şerit yükleme yazısında donmuş: {etiket!r}")
            assert "Settings" in etiket, f"boş hâl anlatılmıyor: {etiket!r}"

            # 2. Şeritte gerçekten HİÇ model yok (kapı kapandı).
            assert page.eval_on_selector_all("#model option", "e => e.length") == 0, (
                "anahtarsız modeller seçiciye girmeye devam ediyor")

            # 3. Panel açıldığında kart yerine AÇIKLAMA var.
            page.click("#model-btn")
            page.wait_for_selector("#model-sheet.open")
            assert page.eval_on_selector_all(
                "#model-sheet-list input", "e => e.length") == 0
            assert page.is_visible(".model-sheet-empty"), (
                "boş panel hiçbir şey söylemiyor")
            page.keyboard.press("Escape")

            # 4. #go kilitli VE sebebi yazılı (kilidin nedenini saklamak yok).
            assert page.is_disabled("#go")
            assert "Settings" in (page.get_attribute("#go", "title") or ""), (
                "kilidin sebebi title'da yok")

            # 5. #model-note doğrudan Ayarlar'a giden düğmeyi gösteriyor.
            assert page.is_visible("#model-note")
            assert page.is_visible("#model-settings-link")

            browser.close()
    finally:
        server.stop()


def test_playwright_composer_GONDERIMDEN_SONRA_kuculuyor(monkeypatch, veritabani, e2e_oturum):
    """"Prompt gönderdikten sonra chat kısmı küçülsün" — ölçülen şey YÜKSEKLİK.

    Yalnız tarayıcıda ölçülebilir: küçülmeyi yapan `min-height` ve onu geri
    veren `:focus-within` CSS kuralları, pytest'te çalışmıyor. Kaynak taraması
    kuralın VARLIĞINI görür, kutunun gerçekten inip inmediğini görmez —
    üstelik `autoGrow` satır yüksekliğini satır içi `style.height` ile yazıyor,
    yani iki mekanizmanın birlikte doğru davrandığı ancak burada anlaşılıyor.
    """
    _tum_kimlikler_kayitli(monkeypatch)
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 860})
            oturum.cerez(page, f"http://127.0.0.1:{port}")

            page.goto(f"http://127.0.0.1:{port}")
            page.wait_for_selector("#view-studio")
            _ilk_kurulum_perdesini_kapat(page)

            kutu = lambda: page.eval_on_selector(
                "#prompt", "e => e.getBoundingClientRect().height")
            once = kutu()
            uzun_yer_tutucu = page.get_attribute("#prompt", "placeholder")
            assert page.get_attribute("#composer", "data-sent") is None, (
                "composer daha ilk gönderimden önce küçülmüş")

            # REDDEDİLEN GÖNDERİM KÜÇÜLTMEZ. Boş kutuyla "Üret" `#go`ya
            # takılmıyor (kapı prompt'un boşluğunu saymıyor, `goBlockReason`
            # modele ve referansa bakıyor) — reddi `run()` veriyor. Küçülmenin
            # çapası bir tur `submitComposer`daydı ve tam burada kırılıyordu:
            # hiç gönderim yapmadan `data-sent` yazılıyor, uzun tanıtım yer
            # tutucusu kısasıyla değişiyordu. Kaynak taraması bitişikliği
            # görüyor, kullanıcının gördüğü şeyi ise yalnız burası görüyor.
            assert not page.is_disabled("#go"), (
                "kapı boş kutuda kilitliymiş — reddi ölçen senaryo geçersiz")
            page.click("#go")
            page.wait_for_timeout(200)
            assert page.get_attribute("#composer", "data-sent") is None, (
                "reddedilen gönderim de composer'ı küçültüyor")
            assert page.get_attribute("#prompt", "placeholder") == uzun_yer_tutucu, (
                "reddedilen gönderim uzun tanıtım yer tutucusunu öldürüyor")

            page.fill("#prompt", "deneme prompt")
            page.click("#go")
            # Üretim ANAHTARSIZ sunucuda başarısız olacak ve bu testi
            # ilgilendirmiyor: küçülme gönderim ANINDA oluyor, sonucun
            # dönmesini beklemiyor.
            page.wait_for_function(
                'document.querySelector("#composer").dataset.sent === "true"')
            # Kutu ELLE boşaltılıyor. `run()` gönderimde boşaltıyor ama istek
            # başarısız olunca metni GERİ YAZIYOR (anahtarsız sunucuda tam da
            # bu oluyor) — ölçüm ise "boş kutu" ile "boş kutu"yu karşılaştırmak
            # zorunda, yoksa ölçülen şey küçülme değil metnin uzunluğu olurdu.
            page.fill("#prompt", "")
            # Odak kutunun DIŞINA alınıyor: `:focus-within` tabanı geri
            # veriyor ve küçülme yalnız odak yokken görünür.
            page.evaluate("document.activeElement.blur()")
            page.wait_for_timeout(200)
            sonra = kutu()
            assert sonra < once, (
                f"composer küçülmedi: {once}px → {sonra}px")

            # ODAKLANINCA GERİ BÜYÜYOR: küçülme akışa yer açmak içindi,
            # yazmayı zorlaştırmak için değil.
            page.focus("#prompt")
            page.wait_for_timeout(200)
            assert kutu() >= once - 1, (
                "odaklanan kullanıcı dar bir kutuya sıkışıyor")

            browser.close()
    finally:
        server.stop()


# ── Logo bindirme önizlemesi ────────────────────────────────────────


def _olcum_kutuphanesi(oturum) -> dict[str, str]:
    """Ölçüm için gerçek PNG tabanlar + bir logo ve bir banner varlığı.

    Dizinler OTURUMUN KULLANICISININ dizinleri (Faz 1 / 4: `ayar.ayarlar`
    kullanıcıya göre, `<data_dir>/kullanicilar/<uuid>/…`; `e2e_oturum` `data_dir`i
    `tmp_path`e çekti). Sunucu THREAD'İ BAŞLAMADAN tohumlanıyor: `ServerThread`
    uygulamayı aynı süreçte koşturuyor ve uçlar yolu ÇAĞRI ANINDA okuyor.
    Geliştiricinin kendi kütüphanesine dokunulmuyor.

    Varlıklar sayfa yüklenmeden önce kaydediliyor ve bu ŞART: `assetCache.logos`
    boş kalırsa `overlayNeedsAsset()` kısa devre yapıyor, sunucuya hiç
    gidilmiyor ve test sessizce "ham görsel sığıyor mu"ya dönüşüp yine yeşil
    kalıyor. `img.currentSrc.startsWith("data:")` iddiası o sessiz düşüşün
    bekçisi.
    """
    from PIL import Image

    from services import depo_varlik

    ayarlar = oturum.ayarlar()
    out, assets = ayarlar.output_dir, ayarlar.assets_dir

    tabanlar = {}
    for ad, boyut in LOGO_ORANLARI.items():
        dosya = f"{ad}.png"
        # Düz KOYU zemin: macenta logo yoklaması ancak kontrast varken anlamlı.
        Image.new("RGB", boyut, (40, 44, 52)).save(os.path.join(out, dosya), "PNG")
        tabanlar[ad] = dosya

    # Varlıklar satır + dosya (Faz 1 / 6): tohum kullanıcının `Session`ıyla,
    # manifest yazmak sunucuya görünmez.
    with oturum.db() as db:
        for tur, boyut in (("logos", (240, 60)), ("banners", (1024, 120))):
            buf = io.BytesIO()
            # Macenta: LANCZOS küçültmesi, PNG yeniden kodlaması ve tarayıcı
            # ölçeklemesinden sonra bile r>200 & b>200 & g<80 kalıyor.
            Image.new("RGBA", boyut, (255, 0, 200, 255)).save(buf, format="PNG")
            depo_varlik.kaydet(db, oturum.kullanici_id, tur, buf.getvalue(), f"olcum {tur}", assets)
        db.commit()
    return tabanlar


LOGO_ORANLARI = {
    "dikey": (1024, 1536),
    "kare": (1024, 1024),
    "yatay": (1536, 1024),
    "cok_dikey": (512, 2048),
}

# Önizleme kutusu ile görselin dikdörtgenleri; taşma POZİTİFSE kırpılıyor.
_TASMA_OKU = """() => {
  const w = document.querySelector('.logo-preview-wrap');
  const i = document.querySelector('#logo-preview-img');
  const wr = w.getBoundingClientRect(), ir = i.getBoundingClientRect();
  return {
    ust: wr.top - ir.top, alt: ir.bottom - wr.bottom,
    yan: Math.max(wr.left - ir.left, ir.right - wr.right),
    kutu: [wr.x, wr.y, wr.width, wr.height],
    kaynak: i.currentSrc.slice(0, 5),
  };
}"""


def _onizleme_bekle(page) -> None:
    page.wait_for_selector("#logo-modal:not([hidden])")
    page.wait_for_function(
        '() => { const i = document.querySelector("#logo-preview-img");'
        ' return i.currentSrc.startsWith("data:") && i.complete'
        ' && i.naturalWidth > 0; }', timeout=15000)


def _onizleme_tazelenmesini_bekle(page, eski: str) -> None:
    """Yeni base64 önizleme GELENE kadar bekler.

    `_onizleme_bekle` burada YETMEZ: `currentSrc` zaten bir `data:` URL'i, yani
    "data: ile başlıyor" iddiası bir öncekinin önünde de doğru. Kaydırıcı ve
    konum değişikliklerinin 220ms'lik gecikmesi de var (assets.js). Çapa bu
    yüzden DEĞERİN KENDİSİ: eskisinden farklı bir kaynak.
    """
    page.wait_for_function(
        "(eski) => { const i = document.querySelector('#logo-preview-img');"
        " return i.currentSrc !== eski && i.currentSrc.startsWith('data:')"
        " && i.complete && i.naturalWidth > 0; }",
        arg=eski, timeout=15000)


def _kaydiriciyi_ayarla(page, eleman_id: str, deger: int) -> None:
    eski = page.evaluate("() => document.querySelector('#logo-preview-img').currentSrc")
    page.evaluate(
        "([id, v]) => { const el = document.getElementById(id); el.value = String(v);"
        " el.dispatchEvent(new Event('input', { bubbles: true })); }",
        [eleman_id, deger])
    _onizleme_tazelenmesini_bekle(page, eski)


def _konumu_sec(page, konum: str) -> None:
    eski = page.evaluate("() => document.querySelector('#logo-preview-img').currentSrc")
    page.click(f'#logo-grid button[data-pos="{konum}"]')
    _onizleme_tazelenmesini_bekle(page, eski)


def _macenta_var_mi(png: bytes) -> bool:
    """Kırpıntıda macenta logodan bir piksel var mı.

    EŞİKLER ÖLÇÜLDÜ, tahmin değil: varlık (255, 0, 200) ve ekran görüntüsünde
    de birebir (255, 0, 200) olarak çıkıyor. İlk yazımda `b > 200` idi ve mavi
    kanal TAM 200 olduğu için yoklama düzeltme YERİNDEYKEN bile düşüyordu —
    yani eşik, ölçtüğünü sandığı şeyi değil kendi kenarını ölçüyordu.
    Kenarlardaki harmanlanmış pikseller ayıklansın diye pay yalnız mavide.
    """
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    # `im.getdata()` DEĞİL: Pillow 12.3 onu kullanımdan kaldırdı (14'te siliniyor)
    # ve takım bir gün DeprecationWarning'i hataya çevirirse ilk düşen yer bu
    # olurdu. `tobytes()` her sürümde aynı: RGB'de art arda üçlü bayt.
    ham = im.tobytes()
    return any(r > 200 and b > 150 and g < 80
               for r, g, b in zip(ham[0::3], ham[1::3], ham[2::3]))


def test_playwright_logo_onizlemesi_kare_OLMAYAN_tabanda_kirpilmiyor(veritabani, e2e_oturum):
    """Kullanıcı bildirimi (28 Ağustos): kare olmayan görselde alt/yan konumlar
    önizlemede gözükmüyor.

    NEDEN YALNIZ TARAYICIDA ÖLÇÜLEBİLİR: sunucu her zaman TAM kadrajı
    döndürüyor (`test_composite.py` dokuz konum × beş oranda logonun kadrajın
    içinde olduğunu zaten kanıtlıyor), yani kaynağa bakan hiçbir iddia farkı
    göremez — kusur çizimde. Bu test öteki yarıyı ölçüyor: **kadraj ⊆ görünür
    kutu**. Kullanıcıya görünen özellik ikisinin bileşkesi.

    DOKUZ KONUM TARAYICIDA GEZİLMİYOR ve bu bilinçli: geometri konumdan
    bağımsız, yani dokuz hücrelik bir döngü sunucuyu pahalı bir vekille ölçer
    ve CSS kırıkken bile — kırpma örneklenen hücreyi ıskaladığı sürece — yeşil
    kalabilirdi. Konum tarafını iki PİKSEL yoklaması taşıyor.

    ÖLÇÜLDÜ (Chromium 1194, 390×844, düzeltmeden ÖNCE): dikey 1024×1536 tabanda
    kutu 358×320.7 iken görsel 358×537, üst taşma 0 ve alt taşma +216.3 —
    taşmanın tamamı altta, yani 9'lu ızgaranın alt sırası ekranda hiç yoktu.
    Kare taban da +37.3 ile eşiğin üstünde; yatay taban (-41) kırpmıyordu, o
    yüzden "kare değilse" bir KATEGORİ değil EŞİK.
    """
    oturum = e2e_oturum()
    tabanlar = _olcum_kutuphanesi(oturum)
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    sunucu_hazir(port)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            oturum.cerez(page, f"http://127.0.0.1:{port}")

            page.goto(f"http://127.0.0.1:{port}")
            page.wait_for_selector("#view-studio")
            _ilk_kurulum_perdesini_kapat(page)
            page.wait_for_function(
                "() => typeof assetCache !== 'undefined'"
                " && assetCache.logos.length > 0")

            for ad, dosya in tabanlar.items():
                page.evaluate("([id, fn]) => openLogoModal({ id, filename: fn })",
                              [ad, dosya])
                _onizleme_bekle(page)
                t = page.evaluate(_TASMA_OKU)
                assert t["kaynak"] == "data:", (
                    "önizleme sunucudan gelmedi: logo varlığı seçilmemiş olabilir "
                    "ve test sessizce yalnız ham görseli ölçüyor")
                assert t["ust"] <= 1 and t["alt"] <= 1 and t["yan"] <= 1, (
                    f"{ad} tabanda önizleme kutusunu taşırıyor: üst={t['ust']:.1f} "
                    f"alt={t['alt']:.1f} yan={t['yan']:.1f}")
                page.evaluate("() => closeLogoModal()")

            # İki PİKSEL yoklaması: kusur "logo GÖZÜKMÜYOR" diye bildirildi,
            # yani geometrinin yanında logonun KENDİSİ de aranmalı — kutunun
            # kırpılan ucunda. Dikey taban, çünkü kırpılan yarı orada.
            page.evaluate("([id, fn]) => openLogoModal({ id, filename: fn })",
                          ["dikey", tabanlar["dikey"]])
            _onizleme_bekle(page)
            # Logo BÜYÜTÜLÜYOR (%14 → %40, kaydırıcının tavanı): 1024 genişlikli
            # taban 214px'e inince %14'lük logo ekranda ~30×7px kalıyor ve
            # kenarları koyu zeminle harmanlanıyor — yoklama o boyutta logonun
            # yokluğunu değil ÖLÇEĞİ ölçerdi. Ölçüldü: %14'te yoklama düşüyor,
            # %40'ta (~85×21px) sağlam geçiyor.
            _kaydiriciyi_ayarla(page, "logo-size", 40)
            # SIRA ÖNEMLİ: modal `bottom-right` ile açılıyor (assets.js), yani
            # ilk yoklama oradan başlasaydı tıklama AYNI görseli üretir, base64
            # değişmez ve "tazelendi" çapası sonsuza kadar beklerdi. Önce
            # `top-left`e geçiliyor, sonra geri dönülüyor: iki geçiş de gerçek.
            for konum, dilim in (("top-left", 0), ("bottom-right", 3)):
                _konumu_sec(page, konum)
                x, y, w, h = page.evaluate(_TASMA_OKU)["kutu"]
                ceyrek = page.screenshot(clip={
                    "x": x, "y": y + h * dilim / 4, "width": w, "height": h / 4})
                assert _macenta_var_mi(ceyrek), (
                    f"{konum} konumundaki logo kutunun görünür alanında yok")
            page.evaluate("() => closeLogoModal()")

            # Banner AYNI kutuyu kullanıyor ve `_composite_banner` da tam boy
            # görsel döndürüyor: kusur oradaydı, düzeltme onu da kapsıyor.
            # Varsayılan kenar `bottom`, yani en çok kırpılan hâl.
            page.evaluate("([id, fn]) => openLogoModal({ id, filename: fn })",
                          ["dikey", tabanlar["dikey"]])
            page.wait_for_selector("#logo-modal:not([hidden])")
            page.click('#logo-type button[data-type="banner"]')
            _onizleme_bekle(page)
            t = page.evaluate(_TASMA_OKU)
            assert t["ust"] <= 1 and t["alt"] <= 1, (
                f"banner önizlemesi taşıyor: üst={t['ust']:.1f} alt={t['alt']:.1f}")
            page.evaluate("() => closeLogoModal()")

            # MASAÜSTÜ GERİLEME BEKÇİSİ: kural mobil blokta duruyor ve orada
            # durmalı. Masaüstünde kabın kesin yüksekliği yok; bir `fr` satır
            # `align-content`in stretch dalını devre dışı bırakıp kısa görseli
            # kutunun TEPESİNE yapıştırırdı. Ölçüldü: düzeltmeden önce ve sonra
            # masaüstü sayıları BİREBİR aynı.
            page.set_viewport_size({"width": 1280, "height": 860})
            for ad, dosya in tabanlar.items():
                page.evaluate("([id, fn]) => openLogoModal({ id, filename: fn })",
                              [ad, dosya])
                _onizleme_bekle(page)
                t = page.evaluate(_TASMA_OKU)
                assert t["ust"] <= 1 and t["alt"] <= 1 and t["yan"] <= 1, (
                    f"masaüstünde {ad} tabanda kırpma doğdu: {t}")
                page.evaluate("() => closeLogoModal()")

            browser.close()
    finally:
        server.stop()


# ── Arama: klasör zinciri ───────────────────────────────────────────


def test_playwright_ust_klasor_aramasi_alt_klasoru_ve_SAYACLARI_getiriyor(veritabani, e2e_oturum):
    """Üst klasörün adı alt klasördeki görselleri VE sayaçları getiriyor.

    NEDEN DURUM ENJEKTE EDİLİYOR: arama %100 istemcide. Sunucuda arama ucu yok
    (`/api/history` yalnız TAM `folder_id` eşitliğiyle süzüyor), yani tam bir
    tur `loadAllImages`in klasör başına yayılımını ölçerdi — yüklemi değil.
    Enjeksiyon ölçülen şeyi daraltıyor: ÇİZİLEN sayaçlar.

    BU TESTİN ÖLÇTÜĞÜ, BAŞKA HİÇBİR KATMANIN ÖLÇEMEDİĞİ YARI:
    `tests/test_search_predicate.py` yüklemi node'da gerçekten koşturuyor ama
    yalnız yüklemi; `tests/test_index.py` kaynağın şeklini sınıyor. Sayaçların
    ekrana doğru çizildiğini yalnız burası görüyor — kabul ölçütü de tam olarak
    "kapsam sayaçları buna göre" diyor.

    ÖLÇÜLDÜ (Chromium 1194, "kampanyalar"): historyCache 0 → 3, şerit
    "4 klasör · 1 görsel" → "1 klasör · 3 görsel", seçicide "Tümü" 0 → 3 ve
    "Kampanyalar / Bayram" 0 → 3. YEM klasör "Yılbaşı / Bayram" 0 → 0 kaldı:
    eşleşen ATA, ağaçta geçen herhangi bir ad değil.
    """
    from PIL import Image

    from services import depo_klasor, depo_medya

    # Kullanıcının kendi `output/`u (Faz 1 / 4) — `tmp_path / "output"` artık sunucunun okuduğu yer değil.
    # Kayıtlar DB'de (Faz 1 / 5): tohum `oturum.db()` ile, manifest yazmak sunucuya görünmez.
    oturum = e2e_oturum()
    out = oturum.ayarlar().output_dir
    kid = oturum.kullanici_id

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (30, 30, 30)).save(buf, "PNG")
    ham = buf.getvalue()

    with oturum.db() as db:
        kampanyalar = depo_klasor.olustur(db, kid, "Kampanyalar", parent_id=None)
        bayram = depo_klasor.olustur(db, kid, "Bayram", parent_id=kampanyalar["id"])
        yilbasi = depo_klasor.olustur(db, kid, "Yılbaşı", parent_id=None)
        # YEM: aynı yaprak adı, BAŞKA bir ata. "kampanyalar" sorgusunda 0 kalmalı.
        yem = depo_klasor.olustur(db, kid, "Bayram", parent_id=yilbasi["id"])

        def koy(prompt: str, folder_id) -> None:
            depo_medya.kaydet(db, kid, ham, {"prompt": prompt, "size": "1024x1024",
                                             "quality": "medium", "folder_id": folder_id}, out)

        for i in range(3):
            koy(f"bayram gorsel {i}", bayram["id"])
        for i in range(2):
            koy(f"yem gorsel {i}", yem["id"])
        koy("kokteki gorsel", None)
        db.commit()

    port = get_free_port()
    server = ServerThread(port)
    server.start()
    sunucu_hazir(port)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            oturum.cerez(page, f"http://127.0.0.1:{port}")

            page.goto(f"http://127.0.0.1:{port}")
            page.wait_for_selector("#view-studio")
            _ilk_kurulum_perdesini_kapat(page)
            page.wait_for_function(
                "() => typeof folderCache !== 'undefined' && folderCache.length === 4")

            page.evaluate("() => showSection('media')")
            page.fill("#media-search", "kampanyalar")
            # Çapa SAYININ KENDİSİ: `refreshSearch` klasör başına bir istek
            # atıyor ve sabit bir uyku o yarışı kapatmaz, yavaşlatır.
            page.wait_for_function(
                "() => historyCache.length === 3", timeout=10000)

            rozetler = page.eval_on_selector_all(
                ".card-where", "els => els.map(e => e.textContent)")
            assert rozetler == ["Kampanyalar / Bayram"] * 3, (
                f"rozetler zinciri yazmıyor: {rozetler}")

            # ŞERİT EKRANI SAYIYOR: iki yarısı da. Önce ikisi de yanlıştı.
            kart_sayisi = page.eval_on_selector_all(
                "#folder-grid .folder-cell", "els => els.length")
            serit = page.text_content("#media-rail-count")
            # ÇOĞUL EKİ ARAYÜZÜN DİLİNDEN geliyor (`media.folders_one` /
            # `media.folders_many`) ve ön tanımlı dil İngilizce: "1 folder",
            # "2 folders". Türkçe'de ek yoktu, o yüzden bu satır önce tek
            # biçimdi — sayıyı elle çoğullamak, testin ölçtüğü şeyi
            # (şeridin ekranı sayması) değiştirmiyor.
            klasor_kelimesi = "folder" if kart_sayisi == 1 else "folders"
            assert serit == f"{kart_sayisi} {klasor_kelimesi} · 3 images", (
                f"şerit ekranla uyuşmuyor: {serit!r}, ekranda {kart_sayisi} kart")

            # TÜR SÜZGECİ: Video seçilince ızgara ve şerit tür birimiyle güncellenir
            page.click('#kind-seg button[data-kind="video"]')
            page.wait_for_function(
                "() => document.querySelector('#kind-seg button[data-kind=\"video\"][aria-pressed=\"true\"]')")
            page.wait_for_function(
                f"() => document.querySelector('#media-rail-count').textContent === "
                f"'{kart_sayisi} {klasor_kelimesi} · 0 videos'")
            assert page.eval_on_selector_all("#gallery video", "els => els.length") == 0
            assert page.eval_on_selector_all("#gallery .card", "els => els.length") == 0

            # Görsel seçilince 3 görsel geri gelir
            page.click('#kind-seg button[data-kind="image"]')
            page.wait_for_function(
                f"() => document.querySelector('#media-rail-count').textContent === "
                f"'{kart_sayisi} {klasor_kelimesi} · 3 images'")
            assert page.eval_on_selector_all("#gallery .card", "els => els.length") == 3

            # Tümü'ne dön
            page.click('#kind-seg button[data-kind=""]')
            page.wait_for_function(
                f"() => document.querySelector('#media-rail-count').textContent === "
                f"'{kart_sayisi} {klasor_kelimesi} · 3 images'")

            # KAPSAM SAYAÇLARI
            page.evaluate("() => openPicker()")
            page.wait_for_selector("#media-picker:not([hidden])")
            page.fill("#picker-search", "kampanyalar")
            # SEÇİCİ `#picker-kinds` İLE KAPSANMIŞ DURUMDA ve bu kapsam
            # YÜKLENMİŞ bir kısıt, süs değil: `.picker-nav-item` artık iki
            # yüzeyde kullanılıyor — medya seçicisinin kapsam şeridi ve
            # Ayarlar penceresinin sol gezinmesi. Kapsamsız sorgu Ayarlar'ın
            # düğümlerini de topluyordu ve onlarda sayaç `<em>`i yok:
            # `b.querySelector('em').textContent` null üzerinde patlıyor,
            # yani test ölçtüğü şeyle ilgisi olmayan bir TypeError ile
            # düşüyordu.
            page.wait_for_function(
                "() => [...document.querySelectorAll('#picker-kinds .picker-nav-item')]"
                ".some(b => +b.querySelector('em').textContent === 3)",
                timeout=10000)
            kapsamlar = dict(page.evaluate(
                "() => [...document.querySelectorAll('#picker-kinds .picker-nav-item')]"
                ".map(b => [b.querySelector('span').textContent,"
                " +b.querySelector('em').textContent])"))

            assert kapsamlar["Kampanyalar / Bayram"] == 3, (
                "alt klasörün kapsamı hâlâ 0: kullanıcı 'Tümü'de gördüğü "
                "görselleri kapsamına tıklayınca boş ızgara buluyor")
            assert kapsamlar["Yılbaşı / Bayram"] == 0, (
                "YEM kapsam doldu: eşleşme ATAYA değil ağaçtaki herhangi bir "
                "ada bakıyor")
            # BÖLME DEĞİŞMEZİ (kapsamlar alt ağaca AÇILMADI): klasör kapsamları
            # + Klasörsüz tam olarak Tümü'nü tüketiyor. `imported` bilerek
            # dışarıda — o `crossing`, yani kesişen tek süzgeç.
            #
            # KAPSAM ADLARI ARAYÜZ METNİ (`common.all` · `picker.scope_imported`)
            # ve ön tanımlı dil İngilizce, yani "All" / "Imported". Türkçe
            # adlar burada bayat kalırdı ve kusur SESSİZ olurdu: `k not in
            # (...)` hiçbir şeyi elemez, toplam şişer ve iddia "bölme bozuldu"
            # diye yanlış bir teşhis yazardı.
            bolme = sum(v for k, v in kapsamlar.items()
                        if k not in ("All", "Imported"))
            assert bolme == kapsamlar["All"], (
                f"kapsamlar artık bir BÖLME değil: parçalar {bolme}, "
                f"Tümü {kapsamlar['All']}")

            browser.close()
    finally:
        server.stop()


def test_playwright_yonetmen_cekmecesi_SAGDAN_aciliyor(monkeypatch, veritabani, e2e_oturum):
    """Yönetmen ayarları çekmecesinin tarayıcı sözleşmesi.

    Kaynak taramasının göremediği beş şey burada ölçülüyor:

      · çipin YALNIZ Yönetmen modunda göründüğü — CSS kaynağı kuralı yazdığını
        söylüyor, hesaplanan `display`i söylemiyor (kaskad özgüllük kadar SIRA
        demek, flow turunun dersi).
      · panelin gerçekten SAĞ kenardan geldiği.
      · odağın metin alanına GİTMEDİĞİ — Android'de klavye paneli yutuyor ve
        bu yalnız `document.activeElement` ile görülüyor.
      · Escape'ten sonra odağın çipe döndüğü — `sheetTetik` atamasının
        `openSheet`ten sonra olması gerektiği tam bu yolla kanıtlanıyor;
        yanlış sırada panel yine açılır, kaydetme yine işler ve tek kayıp
        odaktır.
      · tercihin diske TEK kez yazıldığı ve kaydedilen metnin geri okunduğu.
    """
    _tum_kimlikler_kayitli(monkeypatch)
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)
    base_url = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            prefs_posts = []
            page.on("request", lambda r: prefs_posts.append(r.url)
                    if r.method == "POST" and "/api/prefs" in r.url else None)

            oturum.cerez(page, base_url)


            page.goto(base_url)
            _ilk_kurulum_perdesini_kapat(page)

            # 1. GÖRSEL modunda çip GİZLİ — mod ekseni gerçekten uyguluyor.
            assert page.eval_on_selector(
                "#director-btn", 'e => getComputedStyle(e).display') == "none", (
                "Yönetmen ayarları çipi Görsel modunda görünüyor")

            page.click("#tab-chat")
            page.wait_for_function(
                'document.querySelector("#composer").getAttribute("data-mode")'
                ' === "director"')
            assert page.eval_on_selector(
                "#director-btn", 'e => getComputedStyle(e).display') != "none", (
                "çip Yönetmen modunda da gizli")

            # 2. Panel SAĞDAN geliyor ve sağ kenara dayanıyor.
            page.click("#director-btn")
            page.wait_for_selector("#director-sheet.open")
            page.wait_for_function(
                'getComputedStyle(document.querySelector("#director-sheet"))'
                '.transform === "none"')
            kutu = page.eval_on_selector(
                "#director-sheet", "e => e.getBoundingClientRect()")
            assert abs(kutu["right"] - 390) < 2, (
                f"panel sağ kenara dayanmıyor: {kutu}")
            assert page.get_attribute("#director-btn", "aria-expanded") == "true"

            # 3. Odak panelin İÇİNDE ama metin alanında DEĞİL.
            odak = page.evaluate("document.activeElement.id")
            assert odak != "director-guidance", (
                "odak metin alanında — Android'de klavye paneli yutar")
            assert page.evaluate(
                'document.querySelector("#director-sheet")'
                '.contains(document.activeElement)'), "odak panelin dışında"

            # 4. Kaydetme: TEK POST, ve metin sunucudan geri okunuyor.
            page.fill("#director-guidance", "her zaman düz vektör")
            page.click("#director-save")
            page.wait_for_function(
                'document.querySelector("#director-status").textContent'
                '.includes("was saved")')
            assert len(prefs_posts) == 1, (
                f"tercih {len(prefs_posts)} kez yazıldı — bir kez yazılmalı")

            # 5. Escape kapatıyor, odak ÇİPE dönüyor.
            page.keyboard.press("Escape")
            page.wait_for_selector("#director-sheet:not(.open)")
            assert page.evaluate("document.activeElement.id") == "director-btn", (
                "odak tetikleyiciye dönmüyor — klavye kullanıcısı sayfanın "
                "başına düşüyor")
            assert page.get_attribute("#director-btn", "aria-expanded") == "false"

            # 6. 360px'de yatay kayma YOK — Yönetmen modunda composer artık
            #    iki kontrol taşıyor (#director-btn + Gönder).
            page.set_viewport_size({"width": 360, "height": 780})
            page.wait_for_timeout(300)
            kaydi = page.evaluate("document.documentElement.scrollWidth >"
                                  " document.documentElement.clientWidth")
            assert not kaydi, "360px'de sayfa yatay kayıyor — composer taşıyor"

            # 7. "İkinci etkinleştirme kapatıyor" — KLAVYEYLE ölçülüyor.
            #
            # ÖLÇÜLDÜ ve iki kez şaşırttı; kayda geçiyor çünkü kalıbın
            # `willOpen` dalı ilk bakışta ÖLÜ görünüyor:
            #
            #   · 390×844'te telefonda `.sheet` tam genişlik (mobile.css
            #     `.sheet { width: 100% }`) ve açık panel çipin ÜSTÜNE
            #     biniyor: "subtree intercepts pointer events".
            #   · 1280×860'ta panel çipi kapatmıyor AMA perde kapatıyor:
            #     `.scrim` `position: fixed; inset: 0; z-index: 40` ve
            #     `#composer` `z-index: 5`, yani çip perdenin ALTINDA kalıyor
            #     ("#shell-scrim intercepts pointer events"). Fareyle ikinci
            #     tık HİÇBİR genişlikte çipe ulaşmıyor — ulaşan tık perdeye
            #     gidiyor ve perde de `closeSheets` çağırıyor, o yüzden
            #     kullanıcının GÖRDÜĞÜ sonuç aynı: panel kapanıyor.
            #
            # Dal yine de ölü DEĞİL: odak tuzağı yok, yani kullanıcı
            # Shift+Tab ile çipe dönüp Enter'a basabiliyor ve o yol
            # `willOpen`i gerçekten `false` ile çalıştırıyor. ÖLÇÜLDÜ:
            # #specs-btn de bire bir aynı davranıyor, yani bu #director-btn'in
            # getirdiği bir bedel değil, `.scrim` + `#composer` z-index
            # ilişkisinin yıllardır süren sonucu.
            page.set_viewport_size({"width": 1280, "height": 860})
            page.wait_for_timeout(200)
            page.click("#director-btn")
            page.wait_for_selector("#director-sheet.open")
            page.focus("#director-btn")
            page.keyboard.press("Enter")
            page.wait_for_selector("#director-sheet:not(.open)")
            assert page.get_attribute("#director-btn", "aria-expanded") == "false"

            browser.close()
    finally:
        server.stop()


# Yönetmenin tek bir yanıtı: prompt + varyasyon + üç eksen. İki eksen
# AÇIKLAMALI seçenek nesnesi taşıyor, biri düz dize; ikisinde `simdi` yok
# (ekleme ekseni). Tek bir yanıtın bu turda eklenen her yolu birden
# tetiklemesi bilinçli — paneller birbirinin yanında çizildiğinde hizalanma
# ve taşma ancak öyle ölçülüyor.
_ORNEK_YONETMEN_YANITI = """Sade bir kare kurdum.

**PROMPT**
```
A flat vector illustration of a tea glass on a plain cream background.
```

**Teknik ayarlar**
```json
{"size": "1024x1024", "quality": "medium", "n": 1}
```

```variations
{"varyasyonlar": [{"ad": "Gece", "istek": "Zemini derin lacivert gece gogune cevir. Geri kalanini ayni tut."}]}
```

```parameters
{"eksenler": [
  {"ad": "Zemin", "simdi": "plain cream background",
   "secenekler": [
     {"ad": "deep navy background", "aciklama": "Gece laciverti; hilal parlak okunur.",
      "ornek": {"renk": "#0b2545"}},
     {"ad": "soft grey background", "aciklama": "Notr gri; nesneler one cikar.",
      "ornek": {"renk": "#c9c9c9"}}]},
  {"ad": "Isik", "secenekler": ["soft even light", "warm side light"]},
  {"ad": "Oran",
   "secenekler": [{"ad": "portrait", "aciklama": "Dikey kadraj.", "ornek": {"oran": "2:3"}}]}
]}
"""


def test_playwright_aciklamali_oneri_karti_CIZILIYOR_ve_degeri_karismiyor(veritabani, e2e_oturum):
    """Açıklamalı öneri kartının tarayıcı sözleşmesi.

    Kaynak taraması bunların HİÇBİRİNİ göremiyor:

      · örnek kutusunun gerçekten BOYANDIĞI — `style.background`a yazılan
        dizenin geçerli bir renge çözülüp çözülmediğini yalnız
        `getComputedStyle` söylüyor. (Depo bu tuzağa bir kez düştü: çift
        tireli bir yorum yüzünden işaret dosyaları 200 dönüp HİÇBİR ŞEY
        çizmemişti ve konsolda tek hata yoktu.)
      · `✓` işaretinin KARTTA da göründüğü — kural `.chat-option`ın
        `::before`ından geliyor ve kart onu kaybedebilirdi.
      · MODELE GİDEN metnin açıklamayı TAŞIMADIĞI — `axesValue`ın çıktısı
        yalnız çalışan bir sayfada var ve bu, planın en kritik satırının
        (`dataset.value`) tek gerçek ölçümü.
      · takas ve ekleme eksenlerinin AYRI FİİLLE gittiği.
      · iki satırlı kartların 390px'de taşmadığı.
    """
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)
    base_url = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            oturum.cerez(page, base_url)

            page.goto(base_url)
            _ilk_kurulum_perdesini_kapat(page)
            page.click("#tab-chat")

            # Yanıt DOĞRUDAN çizdiriliyor: gerçek bir Azure turu olmadan
            # ayrıştırıcı + çizim yolu ölçülüyor. `appendBot` küresel kapsamda
            # (chat.js klasik betik), yani sahte bir sunucuya gerek yok.
            page.evaluate("t => appendBot(t)", _ORNEK_YONETMEN_YANITI)
            page.wait_for_selector(".chat-axes")

            # 1. Kartlar ve örnekler çizildi.
            assert page.eval_on_selector_all(
                ".chat-option-card", "e => e.length") == 4, "kartlar çizilmedi"
            assert page.eval_on_selector_all(
                ".chat-option-ornek", "e => e.length") == 3, "örnekler çizilmedi"

            # 2. Renk GERÇEKTEN boyandı (200 alıp hiçbir şey çizmemek gibi bir
            #    sessiz kayıp burada yakalanıyor).
            assert page.eval_on_selector(
                ".chat-axis[data-axis='Zemin'] .chat-option-ornek",
                "e => getComputedStyle(e).backgroundColor") == "rgb(11, 37, 69)"
            assert page.eval_on_selector(
                ".chat-option-ornek-oran",
                "e => getComputedStyle(e).aspectRatio") == "2 / 3"

            # 3. Ekleme ekseni ekranda AYIRT EDİLİYOR (`simdi` yok).
            rozetler = page.eval_on_selector_all(
                ".chat-axis-new", "e => e.map(x => x.textContent)")
            assert rozetler == ["not in the prompt", "not in the prompt"], rozetler

            # 4. Varyasyonun `istek`i ekranda.
            assert "Zemini derin lacivert" in page.eval_on_selector(
                ".chat-variation .chat-option-not", "e => e.textContent")

            # 5. MODELE GİDEN metin: açıklama KARIŞMIYOR, iki fiil AYRI.
            page.click(".chat-axis[data-axis='Zemin'] .chat-option-card")
            page.click(".chat-axis[data-axis='Isik'] .chat-option")
            deger = page.evaluate(
                "axesValue(document.querySelector('.chat-axes'))")
            assert "Change these parameters: Zemin → deep navy background." \
                in deger["content"], deger["content"]
            assert "Also set these: Isik → soft even light." \
                in deger["content"], deger["content"]
            assert "Keep the rest of the prompt the same." in deger["content"]
            for sizinti in ("Gece laciverti", "hilal parlak"):
                assert sizinti not in deger["content"], (
                    f"kart açıklaması modele giden cevaba karıştı: {sizinti}")
                assert sizinti not in deger["display"], (
                    "kart açıklaması akıştaki SEÇİM piline karıştı")

            # 6. `✓` işareti KARTTA da var — ve YERLEŞİMİ OYNATMIYOR.
            #
            # İşaret kartta kök sınıfın `::before`ından GELMİYOR, adın
            # `::before`ından geliyor ve sebebi ancak tarayıcıda görülüyor:
            # `.chat-option-card` bir kolon flex kutusu, bir flex
            # kapsayıcısının `::before`u da bloklaşıp İLK FLEX ÖĞESİ oluyor —
            # işaret etiketin soluna değil örnek kutusunun ÜSTÜNE, kendi
            # satırına düşüyordu. Ölçülen bedel: kart 23,3px uzuyor ve ad
            # 23,3px aşağı kayıyordu, yani SEÇMEK kartı zıplatıyordu. Kaynak
            # taraması bunu göremez — `::before`ın bloklaşması yalnız
            # yerleşim hesabında var, işaretin varlığında değil.
            assert page.eval_on_selector(
                ".chat-option-card[aria-checked='true'] .chat-option-ad",
                "e => getComputedStyle(e, '::before').content") == '"✓ "', \
                "seçili kartta işaret yok — seçili durum yalnız renkle anlatılır"
            # Kökün kuralı PILL'lerde duruyor: kart düzeltmesi onu götürmemeli.
            # (Isik ekseni düz pill; 5. adımda seçilmiş durumda.)
            assert page.eval_on_selector(
                ".chat-axis[data-axis='Isik'] .chat-option[aria-checked='true']",
                "e => getComputedStyle(e, '::before').content") == '"✓ "', \
                "pill'de işaret kayboldu — kart düzeltmesi kök kuralı götürmüş"
            # Düzeltmenin ASIL ölçüsü: seçmek yerleşimi oynatmıyor.
            oyn = page.eval_on_selector(
                ".chat-axis[data-axis='Zemin'] .chat-option-card",
                """k => {
                    const ad = k.querySelector('.chat-option-ad');
                    const olc = () => ({h: k.getBoundingClientRect().height,
                                        adTop: ad.getBoundingClientRect().top});
                    const secili = olc();
                    k.setAttribute('aria-checked', 'false');
                    const bos = olc();
                    k.setAttribute('aria-checked', 'true');
                    return {dh: Math.abs(secili.h - bos.h),
                            dad: Math.abs(secili.adTop - bos.adTop)};
                }""")
            assert oyn["dh"] < 1 and oyn["dad"] < 1, (
                f"seçmek kartın yerleşimini oynatıyor: {oyn} — işaret kendi "
                "flex satırına düşmüş")

            # 7. İki satırlı kartlar 390px'de taşmıyor.
            assert not page.evaluate(
                "document.documentElement.scrollWidth >"
                " document.documentElement.clientWidth"), "kartlar taşıyor"

            browser.close()
    finally:
        server.stop()

