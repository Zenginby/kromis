"""desktop.start_server gerçek bir sokete bağlanır — pencere kısmı manuel doğrulanır."""
import ctypes
import sys
import threading
import time
import types

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

import desktop


def _probe_app() -> FastAPI:
    probe = FastAPI()

    @probe.get("/ping")
    def ping() -> dict:
        return {"ok": True}

    return probe


class _FakeSettings(dict):
    """pywebview'ın `webview.settings`'i (ImmutableDict) gibi davranır.

    Düz bir dict KULLANILMADI: gerçek nesne var olmayan bir anahtara yazmayı
    reddediyor (webview/util.py: "Cannot add new key"). Anahtar adındaki bir
    yazım hatası (ör. ALLOW_DOWNLOAD) düz dict'te sessizce geçer, pakette ise
    açılışta KeyError'a düşer — yani test yeşil kalırken uygulama çöker.
    """

    def __setitem__(self, key, value):
        if key not in self:
            raise KeyError(f"Cannot add new key '{key}'.")
        super().__setitem__(key, value)


def _fake_webview_module() -> types.ModuleType:
    """`_run()`'ın dokunduğu yüzeyi taşıyan sahte modül (pencere hiç açılmaz)."""
    module = types.ModuleType("webview")
    module.settings = _FakeSettings(ALLOW_DOWNLOADS=False)
    return module


def test_start_server_binds_a_free_port_and_serves():
    server, thread, port = desktop.start_server(_probe_app())
    try:
        assert port > 0
        r = httpx.get(f"http://127.0.0.1:{port}/ping", timeout=5)
        assert r.status_code == 200
        assert r.json() == {"ok": True}
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    assert not thread.is_alive()


def test_two_servers_get_different_ports():
    """port=0 çekirdekten boş port ister → run.sh'teki 8765 çakışma mantığı gereksiz."""
    a_server, a_thread, a_port = desktop.start_server(_probe_app())
    b_server, b_thread, b_port = desktop.start_server(_probe_app())
    try:
        assert a_port != b_port
    finally:
        for server, thread in ((a_server, a_thread), (b_server, b_thread)):
            server.should_exit = True
            thread.join(timeout=5)


def test_start_server_binds_only_to_loopback():
    server, thread, port = desktop.start_server(_probe_app())
    try:
        sock = server.servers[0].sockets[0]
        assert sock.getsockname()[0] == "127.0.0.1"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_dead_thread_raises_instead_of_hanging():
    """Geçersiz host → uvicorn thread'i saniyeler içinde ölür; poll döngüsü
    deadline'ı beklemeden 'thread öldü' dalıyla çıkmalı (deadline dalı değil)."""
    with pytest.raises(RuntimeError, match="thread öldü"):
        desktop.start_server(_probe_app(), host="256.256.256.256", timeout=3.0)


def test_dead_thread_error_reports_the_underlying_exception(monkeypatch):
    """I1: 'thread öldü' NEDENsiz kalmamalı — thread'i öldüren gerçek istisna
    mesaja eklenmeli, aksi halde Finder'dan açan kullanıcı stderr'i göremediği
    için teşhis imkânsız kalır.

    Gerçek uvicorn yerine anında çöken sahte bir sunucu kullanılır (aynı desen
    `test_deadline_raises_when_server_never_starts`'ta) — geçersiz host'un
    tetiklediği gerçek soket/uvloop kurulumunu (ve onun üçüncü taraf
    uyarılarını) tekrar tetiklemeden yalnızca yakalama mekanizmasını sınar."""

    class _DiesImmediatelyServer:
        def __init__(self, config: uvicorn.Config) -> None:
            self.config = config
            self.started = False
            self.should_exit = False
            self.servers: list = []

        def run(self, sockets=None) -> None:
            raise ValueError("yapay çöküş")

    monkeypatch.setattr(desktop.uvicorn, "Server", _DiesImmediatelyServer)

    with pytest.raises(RuntimeError) as exc_info:
        desktop.start_server(_probe_app())
    message = str(exc_info.value)
    assert "thread öldü" in message
    assert "yapay çöküş" in message


def test_deadline_raises_when_server_never_starts(monkeypatch):
    """Thread canlı kalıp `started` hiç True olmazsa, poll döngüsü gerçekten
    deadline'da çıkmalı — bu, `test_dead_thread_raises_instead_of_hanging`'in
    kapsamadığı, brief'in asıl "sonsuz asılı kalma" korumasıdır."""

    class _NeverStartsServer:
        """uvicorn.Server yerine geçer: started hiç True olmaz, run() should_exit'e
        kadar canlı kalır (gerçek bir sunucunun asla hazır olmama senaryosu)."""

        def __init__(self, config: uvicorn.Config) -> None:
            self.config = config
            self.started = False
            self.should_exit = False
            self.servers: list = []

        def run(self, sockets=None) -> None:
            while not self.should_exit:
                time.sleep(0.02)

    monkeypatch.setattr(desktop.uvicorn, "Server", _NeverStartsServer)

    timeout = 0.5
    start = time.monotonic()
    with pytest.raises(RuntimeError, match="hazır olmadı"):
        desktop.start_server(_probe_app(), timeout=timeout)
    elapsed = time.monotonic() - start

    # Deadline'a yakın çıkmalı — asılı kalmadığının kanıtı (sabit sınır: 2 sn).
    assert timeout <= elapsed < 2.0

    # start_server, should_exit'i işaretleyip döner; thread'in de fiilen
    # kapandığını doğrula — sahte thread arkada asılı kalmasın.
    uvicorn_threads = [t for t in threading.enumerate() if t.name == "uvicorn"]
    for stray_thread in uvicorn_threads:
        stray_thread.join(timeout=1)
    assert all(not t.is_alive() for t in uvicorn_threads)


def test_pick_screen_color_returns_the_sampled_hex():
    """js_api köprüsü screencolor.pick'in sonucunu olduğu gibi geçirir."""
    api = desktop.Api()
    api._pick = lambda: "#c86a3c"        # sampler yerine sabit
    assert api.pick_screen_color() == "#c86a3c"


def test_pick_screen_color_returns_none_and_logs_when_the_bridge_fails(monkeypatch, tmp_path):
    """Bir renk seçme denemesi HİÇBİR koşulda uygulamayı düşürmemeli.

    js_api metodundan çıkan istisna pywebview'ın worker thread'inde kalır:
    kullanıcı yalnızca "hiçbir şey olmadı" görür ve neden olduğunu asla
    öğrenemez (paket --windowed, stderr yok). Bu yüzden yakalanıp hata.log'a
    yazılıyor — errlog'un var olma gerekçesinin aynısı.
    """
    monkeypatch.setattr("paths.data_dir", lambda: str(tmp_path))

    api = desktop.Api()

    def boom():
        raise RuntimeError("AppKit yok")

    api._pick = boom
    assert api.pick_screen_color() is None

    log = tmp_path / "hata.log"
    assert log.exists(), "köprü hatası loglanmadı"
    assert "AppKit yok" in log.read_text(encoding="utf-8")


def test_window_is_created_with_the_color_picker_api(monkeypatch):
    """Pencere js_api ile açılmalı, yoksa damlalık app'te SESSİZCE kaybolur.

    WKWebView'da `window.EyeDropper` yok (WebKit onu hiç uygulamadı), yani
    native köprü tek yol. `js_api` düşerse `window.pywebview.api` hiç
    oluşmaz, palette.js yetenek tespitinde ikisini de bulamaz ve düğmeyi
    gizler — tam olarak v1.10'daki davranışa geri dönülür.
    """
    captured: dict = {}
    fake_webview = _fake_webview_module()

    def fake_create_window(title: str, url: str, width: int, height: int,
                            min_size: tuple[int, int], js_api=None) -> None:
        captured["js_api"] = js_api

    fake_webview.create_window = fake_create_window
    fake_webview.start = lambda: None
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setattr("paths.ensure_data_dirs", lambda: None)

    desktop._run()

    api = captured["js_api"]
    assert api is not None, "create_window'a js_api geçilmiyor"
    assert callable(getattr(api, "pick_screen_color", None)), (
        "js_api pick_screen_color taşımıyor — JS tarafı onu arıyor")


def test_main_wires_real_port_into_window_and_shuts_down_cleanly(monkeypatch):
    """main(): sahte webview modülü enjekte edilir; pencere kısmı hiç gerçek açılmaz.

    Doğrulanan üç şey:
    - create_window'a sabit 8765 değil, sunucunun gerçekte bağlandığı port geçiyor;
    - modülün tanımladığı genişlik/yükseklik/min_size aynen iletiliyor;
    - webview.start() döndükten sonra sunucuya çıkış işaretlenmiş ve thread ölmüş
      (kapanan pencere arkada asılı bir uvicorn süreci bırakmıyor).
    """
    captured: dict = {}
    live_thread_at_start_return: dict = {}

    fake_webview = _fake_webview_module()

    def fake_create_window(title: str, url: str, width: int, height: int,
                            min_size: tuple[int, int], js_api=None) -> None:
        captured["title"] = title
        captured["url"] = url
        captured["width"] = width
        captured["height"] = height
        captured["min_size"] = min_size

    def fake_start() -> None:
        # main() içindeki thread'in henüz canlı olduğunu (server.should_exit
        # işaretlenmeden önce) burada yakalıyoruz — finally bloğunun gerçekten
        # kapanışı tetiklediğini kanıtlamak için.
        live_thread_at_start_return["alive_before_shutdown"] = captured["thread"].is_alive()
        return None

    fake_webview.create_window = fake_create_window
    fake_webview.start = fake_start
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    monkeypatch.setattr("paths.ensure_data_dirs", lambda: None)
    # app.app'in lifespan'ı gerçekten çalışıyor (bu testin amacı budur).
    # Lifespan'ın tek yan etkisi olan sürüm yedeği conftest'teki autouse guard
    # tarafından no-op'a çevriliyor — testler geliştiricinin gerçek verisine
    # dokunmamalı. (Buradaki üçüncü satır eskiden seed tohumlamasını da
    # susturuyordu; seed.py kaldırıldı.)

    real_start_server = desktop.start_server

    def spying_start_server(fastapi_app, host: str = "127.0.0.1",
                            timeout: float = 15.0):
        server, thread, port = real_start_server(fastapi_app, host=host, timeout=timeout)
        captured["server"] = server
        captured["thread"] = thread
        captured["port"] = port
        return server, thread, port

    monkeypatch.setattr(desktop, "start_server", spying_start_server)

    desktop.main()

    assert captured["title"] == desktop.WINDOW_TITLE
    assert captured["url"] == f"http://127.0.0.1:{captured['port']}"
    assert captured["port"] not in (0, 8765)
    assert captured["width"] == desktop.WINDOW_SIZE[0]
    assert captured["height"] == desktop.WINDOW_SIZE[1]
    assert captured["min_size"] == desktop.MIN_WINDOW_SIZE

    assert live_thread_at_start_return["alive_before_shutdown"] is True
    assert captured["server"].should_exit is True
    assert not captured["thread"].is_alive()


def test_downloads_are_enabled_before_the_window_opens(monkeypatch):
    """ARM Mac mini'de bildirilen hata: "İndir" hiçbir şey kaydetmiyor, görselin
    büyük hâli uygulamanın YERİNE açılıyordu.

    Nedeni istemcide değildi — folders.js standarda uygun `<a download>` üretiyor.
    WKWebView bu özniteliği YALNIZCA `ALLOW_DOWNLOADS` açıkken indirmeye çeviriyor
    (webview/platforms/cocoa.py: `action.shouldPerformDownload() and
    webview_settings['ALLOW_DOWNLOADS']`); pywebview'ın varsayılanı False. Kapalıyken
    tıklama sıradan gezinmeye düşüyor, PNG'nin MIME türü gösterilebilir olduğu için
    de görsel tam pencerede çiziliyordu — üstelik Delete-ile-geri hareketi aynı
    dosyada bilerek kapalı olduğu için geri dönüş yolu YOK.

    Ayar penceresel bir yan etki olduğundan otomatik olarak yalnızca burada
    yakalanabilir; hatanın kendisi sadece paketlenmiş .app'te görünür (tarayıcı
    kendi indirme yolunu kullandığı için run.sh ile test edilince sağlam görünür).
    """
    seen: dict = {}

    fake_webview = _fake_webview_module()
    settings_at_import = fake_webview.settings

    def fake_create_window(title: str, url: str, width: int, height: int,
                            min_size: tuple[int, int], js_api=None) -> None:
        seen["at_create_window"] = fake_webview.settings["ALLOW_DOWNLOADS"]

    def fake_start() -> None:
        seen["at_start"] = fake_webview.settings["ALLOW_DOWNLOADS"]

    fake_webview.create_window = fake_create_window
    fake_webview.start = fake_start
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setattr("paths.ensure_data_dirs", lambda: None)

    desktop._run()

    # Pencere açılmadan ÖNCE açılmış olmalı: ayar tıklama anında okunuyor ama
    # create_window'dan sonra yazmak yarış penceresi bırakır.
    assert seen["at_create_window"] is True, "indirmeler pencere açılmadan açılmalı"
    assert seen["at_start"] is True

    # Ayar YERİNDE değiştirilmeli. cocoa.py modül düzeyinde
    # `from webview import settings as webview_settings` ile bu nesneye bağlanıyor;
    # `webview.settings = {...}` diye yeniden atamak o bağı koparır ve backend
    # ESKİ nesneyi okumaya devam eder → düzeltme sessizce ölür, hata geri gelir.
    # Bu kusur testi koşarak keşfedilemez, o yüzden kimlik açıkça karşılaştırılıyor.
    assert fake_webview.settings is settings_at_import, (
        "settings yeniden atanmış — cocoa.py'nin bağlandığı nesne artık başkası")


def test_shutdown_logs_when_thread_join_times_out(monkeypatch, tmp_path):
    """Minor bulgu: `thread.join(timeout=...)` dönüş değeri eskiden atılıyordu
    — zaman aşımına uğrayan bir kapanış sessizce geçiyordu. Artık hata.log'a
    yazılmalı (isimli sabit `_JOIN_TIMEOUT`, `daemon=True` yine de süreci
    kurtarır — bkz. desktop.py docstring'i)."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))

    class _NeverJoinsThread:
        def is_alive(self) -> bool:
            return True

        def join(self, timeout: float | None = None) -> None:
            return None

    class _FakeServer:
        should_exit = False

    desktop._shutdown(_FakeServer(), _NeverJoinsThread())

    log_path = tmp_path / "hata.log"
    assert log_path.is_file()
    assert "kapanmadı" in log_path.read_text(encoding="utf-8")


class _SahteSurec:
    """`subprocess.run`ın döndürdüğü CompletedProcess yerine en küçük nesne.

    `_alert_macos` artık ÇIKIŞ KODUNU okuyor — kutunun gerçekten çıkıp
    çıkmadığının tek kanıtı o. `None` döndüren bir sahte, gerçek kodun asla
    girmediği bir dala (AttributeError → yutulan istisna) sokardı ve test
    yeşil kalırken hiçbir şey ölçmezdi.
    """

    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode


def _osascript_casusu(kayit: list, *, returncode: int = 0):
    """`subprocess.run` yerine geçen, çağrıyı kaydeden sahte."""
    def _run(*args, **kwargs):
        kayit.append((args, kwargs))
        return _SahteSurec(returncode)

    return _run


def test_main_logs_and_shows_alert_when_startup_fails(monkeypatch, tmp_path):
    """I1: Finder'dan açan kullanıcı stderr göremez — main() her hatayı
    hata.log'a yazmalı, native bir uyarı göstermeli ve süreç non-zero çıkmalı.

    `_run` doğrudan patlatılır (start_server/webview'ın gerçek başarısızlık
    yollarının hepsi zaten `_run` içinden aynı istisna sınıfıyla çıkar);
    burada asıl doğrulanan main()'in sarmalayıcı davranışı."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))

    def boom() -> None:
        raise RuntimeError("test patlaması")

    monkeypatch.setattr(desktop, "_run", boom)

    # Platform SAHTELENİYOR: ölçülen şey main()'in sarmalayıcı davranışı, koşan
    # makinenin işletim sistemi değil. Dal seçiminin kendisi ayrı testlerde.
    monkeypatch.setattr(desktop.sys, "platform", "darwin")
    alert_calls: list[tuple] = []
    monkeypatch.setattr(desktop.subprocess, "run", _osascript_casusu(alert_calls))

    with pytest.raises(SystemExit) as exc_info:
        desktop.main()
    assert exc_info.value.code == 1

    log_path = tmp_path / "hata.log"
    assert log_path.is_file()
    content = log_path.read_text(encoding="utf-8")
    assert "RuntimeError" in content
    assert "test patlaması" in content

    assert len(alert_calls) == 1
    args, kwargs = alert_calls[0]
    assert args[0][0] == "osascript"


def test_fatal_alert_uses_osascript_on_macos(monkeypatch):
    monkeypatch.setattr(desktop.sys, "platform", "darwin")
    calls: list[tuple] = []
    monkeypatch.setattr(desktop.subprocess, "run", _osascript_casusu(calls))

    desktop._show_fatal_alert("/tmp/hata.log")

    assert len(calls) == 1
    assert calls[0][0][0][0] == "osascript"
    assert "/tmp/hata.log" in calls[0][0][0][2]


def test_fatal_alert_uses_messagebox_on_windows(monkeypatch):
    """Windows'ta osascript YOK. Dal seçilmezse uyarı hiç çıkmaz ve `--windowed`
    pakette stderr de olmadığı için açılış hatası tamamen sessiz kalır."""
    monkeypatch.setattr(desktop.sys, "platform", "win32")
    subprocess_calls: list[tuple] = []
    monkeypatch.setattr(desktop.subprocess, "run",
                        lambda *a, **k: subprocess_calls.append((a, k)))
    alerts: list[tuple[str, str]] = []
    # `**kwargs`: `_uyari_goster` artık `kritik=` geçiriyor (ölümcül uyarı ile
    # tarayıcı yedeğinin kutusu aynı fonksiyondan çıkıyor, farklı bayraklarla).
    monkeypatch.setattr(desktop, "_alert_windows",
                        lambda title, message, **kwargs: alerts.append((title, message)))

    desktop._show_fatal_alert(r"C:\Users\x\hata.log")

    assert not subprocess_calls, "Windows'ta subprocess'e düşmemeli (konsol çakar)"
    assert len(alerts) == 1
    title, message = alerts[0]
    assert "Lumeo" in title
    assert r"C:\Users\x\hata.log" in message


def test_the_macos_alert_reports_whether_the_box_appeared(monkeypatch):
    """`display alert` kullanıcı Tamam'a basınca 0 ile döner. Sıfırdan farklı
    kod = kutu hiç çizilemedi (GUI oturumu yok, otomasyon izni reddedildi) ve
    çağrı BLOKLAMADI. Tarayıcı yedeği tam olarak o bloklamaya dayanıyor."""
    monkeypatch.setattr(desktop.sys, "platform", "darwin")

    monkeypatch.setattr(desktop.subprocess, "run", _osascript_casusu([]))
    assert desktop._uyari_goster("t", "m", kritik=False) is True

    monkeypatch.setattr(desktop.subprocess, "run",
                        _osascript_casusu([], returncode=1))
    assert desktop._uyari_goster("t", "m", kritik=False) is False


def test_the_windows_alert_reports_a_box_that_could_not_be_created(monkeypatch):
    """MessageBoxW kutuyu kuramazsa 0 döner ve HİÇ BLOKLAMAZ; kurabildiyse
    basılan düğmenin kimliğini döner. Bu ayrımı yutmak, tarayıcı yedeğini
    sessizce boşa çıkarır."""
    monkeypatch.setattr(desktop.sys, "platform", "win32")

    class _Windll:
        def __init__(self, sonuc: int) -> None:
            self.user32 = types.SimpleNamespace(
                MessageBoxW=lambda *args: sonuc)

    # `raising=False`: Linux'ta `ctypes.windll` YOK. `_alert_windows` ctypes'ı
    # gövdesinin içinde import ediyor, yani buradaki modül nesnesiyle aynısı.
    monkeypatch.setattr(ctypes, "windll", _Windll(1), raising=False)
    assert desktop._uyari_goster("t", "m", kritik=True) is True

    monkeypatch.setattr(ctypes, "windll", _Windll(0), raising=False)
    assert desktop._uyari_goster("t", "m", kritik=True) is False


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_alert_failure_does_not_crash_main(monkeypatch, tmp_path, platform):
    """I1: uyarı gösterme denemesinin kendisi patlarsa bile main() yine de
    (loglanmış, non-zero) temiz çıkmalı — kullanıcı hâlâ hiçbir şey görmese
    de süreç asılı kalmamalı. İki dalda da geçerli."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop, "_run", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(desktop.sys, "platform", platform)

    def boom_alert(*args, **kwargs):
        raise OSError("uyarı gösterilemedi (simüle)")

    monkeypatch.setattr(desktop.subprocess, "run", boom_alert)
    monkeypatch.setattr(desktop, "_alert_windows", boom_alert)

    with pytest.raises(SystemExit) as exc_info:
        desktop.main()
    assert exc_info.value.code == 1
    assert (tmp_path / "hata.log").is_file()


# --- Windows .NET köprüsü: önyükleme, tarayıcı yedeği, denetim kipi ---------
#
# Üçü de 2026-09-04'teki tek kusurdan doğdu: indirilen Windows paketi
# `webview.start()` içinde pythonnet'e takılıp HİÇ açılmadı (bkz. desktop.py
# docstring'i). Buradaki testler o üç mandalın gerçekten kurulu olduğunu
# ölçüyor — hiçbiri gerçek `webview`'ı, dolayısıyla `clr`'ı import etmiyor.


def _pencere_patlatan_webview(hata: Exception) -> types.ModuleType:
    """`webview.start()` çağrısı patlayan sahte modül (Windows kusurunun eşi)."""
    fake = _fake_webview_module()
    fake.create_window = lambda *a, **k: None

    def _start() -> None:
        raise hata

    fake.start = _start
    return fake


def test_the_clr_preflight_runs_before_the_window_is_created(monkeypatch):
    """SIRA SÖZLEŞMESİ: `import clr` zincirin içinde, `webview.start()`
    çağrılırken tetikleniyor. İndirme işareti o andan ÖNCE kaldırılmış olmak
    zorunda; sonra kaldırmanın hiçbir anlamı yok."""
    sira: list[str] = []
    monkeypatch.setattr(desktop.paths, "is_frozen", lambda: True)
    fake_webview = _fake_webview_module()
    fake_webview.create_window = lambda *a, **k: sira.append("create_window")
    fake_webview.start = lambda: sira.append("start")
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setattr("paths.ensure_data_dirs", lambda: None)
    monkeypatch.setattr(desktop.winclr, "onyukle",
                        lambda kok: sira.append("onyukle") or "")

    desktop._run()

    assert sira[0] == "onyukle"
    assert sira[1:] == ["create_window", "start"]


def test_a_preflight_finding_is_written_to_the_error_log(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop.paths, "is_frozen", lambda: True)
    monkeypatch.setattr(desktop.winclr, "onyukle",
                        lambda kok: "indirme işareti: 3 dosyada bulundu")

    desktop._onyukle()

    assert "indirme işareti" in (tmp_path / "hata.log").read_text(encoding="utf-8")


def test_a_clean_preflight_leaves_no_error_log_behind(monkeypatch, tmp_path):
    """HATA.LOG SÖZLEŞMESİ: dosyanın VARLIĞI "kötü haber" demek (KURULUM.md
    kullanıcıya "varsa gönder" diyor). Her açılışta satır yazmak onu sıradan
    bir günlüğe çevirir ve sözleşmeyi sessizce bozar."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop.paths, "is_frozen", lambda: True)
    monkeypatch.setattr(desktop.winclr, "onyukle", lambda kok: "")

    desktop._onyukle()

    assert not (tmp_path / "hata.log").exists()


def test_the_preflight_does_not_run_from_a_source_checkout(monkeypatch, tmp_path):
    """Kaynaktan koşarken `resource_dir()` DEPO KÖKÜ ve orada
    `pythonnet/runtime/Python.Runtime.dll` hiç yok (pythonnet site-packages'ta).
    Denetim orada her açılışta "Python.Runtime.dll: YOK" diye YANLIŞ bir bulgu
    üretip depo köküne hata.log bırakırdı — yukarıdaki sözleşmenin tam tersi.
    Ölçülen şey PAKETİN içi; kaynak ağacında ölçülecek bir şey yok."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop.paths, "is_frozen", lambda: False)
    monkeypatch.setattr(desktop.winclr, "onyukle",
                        lambda kok: pytest.fail("kaynakta denetim koşmamalı"))

    desktop._onyukle()

    assert not (tmp_path / "hata.log").exists()


def test_a_crashing_preflight_never_blocks_startup(monkeypatch, tmp_path):
    """Bir ÖNYÜKLEME DENETİMİNİN açılışı engellemesinden kötü sonuç yok."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop.paths, "is_frozen", lambda: True)

    def _patla(_kok):
        raise RuntimeError("denetim çöktü")

    monkeypatch.setattr(desktop.winclr, "onyukle", _patla)

    desktop._onyukle()          # fırlatmamalı

    assert "denetim çöktü" in (tmp_path / "hata.log").read_text(encoding="utf-8")


def test_the_browser_fallback_opens_the_same_url_the_window_would_have(
        monkeypatch, tmp_path):
    """Yedek, sunucunun GERÇEKTE dinlediği portu açmalı. İki ayrı yerde
    kurulsaydı kusur yalnız yedeğe düşüldüğünde görünürdü."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr("paths.ensure_data_dirs", lambda: None)
    monkeypatch.setitem(sys.modules, "webview",
                        _pencere_patlatan_webview(RuntimeError("Failed to resolve")))
    acilan: list[str] = []
    monkeypatch.setattr(desktop.webbrowser, "open",
                        lambda url: acilan.append(url) or True)
    # `True`: kutu GERÇEKTEN gösterildi demek. Yedek artık dönüşü buna
    # bağlıyor — `None` döndüren bir sahte "kutu çizilemedi" anlamına gelir.
    monkeypatch.setattr(desktop, "_uyari_goster", lambda *a, **k: True)

    pencere_url: dict = {}
    gercek = desktop.start_server

    def _casus(app, **kwargs):
        server, thread, port = gercek(app, **kwargs)
        pencere_url["port"] = port
        return server, thread, port

    monkeypatch.setattr(desktop, "start_server", _casus)

    desktop._run()

    assert acilan == [f"http://127.0.0.1:{pencere_url['port']}"]


def test_the_browser_fallback_keeps_the_server_alive_until_dismissed(
        monkeypatch, tmp_path):
    """Bloklayan kutu SÜS DEĞİL: uvicorn thread'i `daemon=True`, ana thread
    orada beklemezse süreç anında ölür ve kullanıcının sekmesi boşluğa bakar."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr("paths.ensure_data_dirs", lambda: None)
    monkeypatch.setitem(sys.modules, "webview",
                        _pencere_patlatan_webview(RuntimeError("Failed to resolve")))
    monkeypatch.setattr(desktop.webbrowser, "open", lambda url: True)

    durum: dict = {}
    yakalanan: dict = {}
    gercek = desktop.start_server

    def _casus(app, **kwargs):
        server, thread, port = gercek(app, **kwargs)
        yakalanan["server"], yakalanan["thread"] = server, thread
        return server, thread, port

    def _kutu(*a, **k):
        durum["alive"] = yakalanan["thread"].is_alive()
        durum["should_exit"] = yakalanan["server"].should_exit
        return True

    monkeypatch.setattr(desktop, "start_server", _casus)
    monkeypatch.setattr(desktop, "_uyari_goster", _kutu)

    desktop._run()

    assert durum["alive"] is True, "kutu gösterilirken sunucu ayakta olmalı"
    assert durum["should_exit"] is False
    # ve kutu döndükten sonra kapanış gerçekten koşmuş olmalı
    assert yakalanan["server"].should_exit is True
    assert not yakalanan["thread"].is_alive()


def test_the_window_failure_is_logged_before_the_blocking_alert(
        monkeypatch, tmp_path):
    """Kutu bloklarken süreç öldürülürse geriye kalan tek iz bu kayıt olur."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr("paths.ensure_data_dirs", lambda: None)
    monkeypatch.setitem(sys.modules, "webview",
                        _pencere_patlatan_webview(RuntimeError("Failed to resolve X")))
    monkeypatch.setattr(desktop.webbrowser, "open", lambda url: True)

    gorulen: dict = {}
    monkeypatch.setattr(desktop, "_uyari_goster", lambda *a, **k: gorulen.update(
        log=(tmp_path / "hata.log").read_text(encoding="utf-8")) or True)

    desktop._run()

    assert "Failed to resolve X" in gorulen["log"]


def test_a_successful_fallback_does_not_exit_non_zero(monkeypatch, tmp_path):
    """Yedek tuttuysa uygulama BAŞARIYLA çalıştı: `main()` SystemExit üretmemeli."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr("paths.ensure_data_dirs", lambda: None)
    monkeypatch.setitem(sys.modules, "webview",
                        _pencere_patlatan_webview(RuntimeError("Failed to resolve")))
    monkeypatch.setattr(desktop.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(desktop, "_uyari_goster", lambda *a, **k: True)

    desktop.main([])            # fırlatmamalı


def test_a_failing_browser_still_reaches_the_fatal_alert_and_exit_one(
        monkeypatch, tmp_path):
    """Yedek de tutmazsa eski davranış aynen geçerli: uyarı + exit 1."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr("paths.ensure_data_dirs", lambda: None)
    monkeypatch.setitem(sys.modules, "webview",
                        _pencere_patlatan_webview(RuntimeError("Failed to resolve")))
    monkeypatch.setattr(desktop.webbrowser, "open", lambda url: False)
    olumcul: list[str] = []
    monkeypatch.setattr(desktop, "_show_fatal_alert", lambda yol: olumcul.append(yol))

    with pytest.raises(SystemExit) as exc_info:
        desktop.main([])

    assert exc_info.value.code == 1
    assert len(olumcul) == 1


def test_a_fallback_whose_alert_never_appeared_is_not_a_success(
        monkeypatch, tmp_path):
    """UYARI KUTUSU SÜS DEĞİL, SÜREÇ TUTUCU. Çizilemezse çağrı anında döner:
    `_run()` biter, `finally: _shutdown()` uvicorn'u kapatır ve kullanıcının
    az önce açılan sekmesi "bağlantı reddedildi" gösterir."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(desktop, "_uyari_goster", lambda *a, **k: False)

    assert desktop._tarayici_yedegi("http://127.0.0.1:1", "/tmp/hata.log") is False


def test_a_fallback_without_a_blocking_alert_reaches_the_fatal_path(
        monkeypatch, tmp_path):
    """Ve sonucu görünür: sessiz bir sıfır çıkış yerine ölümcül uyarı + exit 1.
    Kullanıcı hiç değilse hata.log'u ve nereye bakacağını öğreniyor."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr("paths.ensure_data_dirs", lambda: None)
    monkeypatch.setitem(sys.modules, "webview",
                        _pencere_patlatan_webview(RuntimeError("Failed to resolve")))
    monkeypatch.setattr(desktop.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(desktop, "_uyari_goster", lambda *a, **k: False)
    olumcul: list[str] = []
    monkeypatch.setattr(desktop, "_show_fatal_alert", lambda yol: olumcul.append(yol))

    with pytest.raises(SystemExit) as exc_info:
        desktop.main([])

    assert exc_info.value.code == 1
    assert len(olumcul) == 1


def test_a_crashing_browser_call_is_not_a_second_crash(monkeypatch, tmp_path):
    """`webbrowser.open` fırlatırsa yedek False dönmeli, yeni bir istisna DEĞİL."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))

    def _patla(_url):
        raise OSError("tarayıcı yok")

    monkeypatch.setattr(desktop.webbrowser, "open", _patla)

    assert desktop._tarayici_yedegi("http://127.0.0.1:1", "/tmp/hata.log") is False


def _sahte_webview_guilib(renderer: str = "edgechromium"):
    """`webview` paketini AD ÇAKIŞMASIYLA birlikte kurar; (paket, guilib) döner.

    Çakışma sahtenin bir kaprisi değil, pywebview 6.2'nin gerçeği:
    `webview/__init__.py:29` `from webview.guilib import GUIType, initialize`
    yapıp alt modülü paketin niteliği olarak bağlıyor, `:157` ise
    `guilib = None` ile o niteliğin üstüne yazıyor.
    """
    paket = types.ModuleType("webview")
    paket.guilib = None                     # ÇAKIŞMA: paketin niteliği None
    guilib = types.ModuleType("webview.guilib")
    secilen = types.ModuleType("webview.platforms.winforms")
    secilen.renderer = renderer
    guilib.initialize = lambda: secilen
    return paket, guilib


def test_the_backend_stage_survives_the_guilib_name_collision(monkeypatch):
    """`from webview import guilib` HER ZAMAN None verir (gerekçe yukarıda) ve
    kademe `AttributeError` ile düşerdi — kapı 2026-09-04'te tam olarak buna
    düştü, üstelik ölçtüğü halka SAĞLAMKEN: kendi kusurumuz yüzünden kırmızı
    bir kapı, uzun yaşamaz."""
    paket, guilib = _sahte_webview_guilib()
    monkeypatch.setitem(sys.modules, "webview", paket)
    monkeypatch.setitem(sys.modules, "webview.guilib", guilib)

    kademeler = dict(desktop._onyukleme_kademeleri())
    metin = kademeler["webview.guilib.initialize()"]()

    assert "webview.platforms.winforms" in metin


def test_the_backend_stage_reports_the_renderer_not_just_the_module(monkeypatch):
    """Windows'ta `initialize()` HER hâlükârda `webview.platforms.winforms`
    döner; edgechromium→mshtml düşüşü o modülün `renderer` alanında görünüyor.
    Yalnız modül adını yazmak, "sessiz gerilemeyi görürüz" iddiasını boş bir
    cümleye çevirirdi."""
    paket, guilib = _sahte_webview_guilib(renderer="mshtml")
    monkeypatch.setitem(sys.modules, "webview", paket)
    monkeypatch.setitem(sys.modules, "webview.guilib", guilib)

    kademeler = dict(desktop._onyukleme_kademeleri())

    assert "mshtml" in kademeler["webview.guilib.initialize()"]()


def test_the_preflight_flag_exits_zero_when_the_gui_backend_initializes(
        monkeypatch, tmp_path):
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop.paths, "resource_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop, "_onyukleme_kademeleri",
                        lambda: [("import clr", lambda: "sahte"),
                                 ("backend", lambda: "edgechromium")])

    with pytest.raises(SystemExit) as exc_info:
        desktop.main([desktop.ONYUKLEME_BAYRAGI])

    assert exc_info.value.code == 0
    rapor = (tmp_path / desktop.ONYUKLEME_RAPORU).read_text(encoding="utf-8")
    assert "[GEÇTİ] import clr" in rapor
    # Seçilen arka uç rapora YAZILMALI: WebView2 bulunamazsa pywebview sessizce
    # mshtml'e düşer ve kapı yeşil kalır; gerileme ancak burada görünür.
    assert "edgechromium" in rapor


def test_the_preflight_flag_exits_non_zero_when_a_stage_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop.paths, "resource_dir", lambda: str(tmp_path))

    def _clr_patla():
        raise RuntimeError("Failed to resolve Python.Runtime.Loader.Initialize")

    monkeypatch.setattr(desktop, "_onyukleme_kademeleri",
                        lambda: [("import clr", _clr_patla),
                                 ("backend", lambda: pytest.fail("bu kademe koşmamalı"))])

    with pytest.raises(SystemExit) as exc_info:
        desktop.main([desktop.ONYUKLEME_BAYRAGI])

    assert exc_info.value.code == 1
    rapor = (tmp_path / desktop.ONYUKLEME_RAPORU).read_text(encoding="utf-8")
    assert "[DÜŞTÜ] import clr" in rapor
    assert "Failed to resolve" in rapor
    # Kusur hata.log'a da düşüyor: KURULUM.md yıllardır o dosyayı istiyor.
    assert "Failed to resolve" in (tmp_path / "hata.log").read_text(encoding="utf-8")


def test_the_preflight_flag_never_opens_a_window(monkeypatch, tmp_path):
    """CI runner'ında pencere açmak güvenilir değil; ölçtüğümüz şey zaten
    pencere değil, ondan ÖNCEKİ halka."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop.paths, "resource_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop, "_onyukleme_kademeleri", lambda: [])
    monkeypatch.setattr(desktop, "_run", lambda: pytest.fail("_run koşmamalı"))
    # Modal uyarı runner'ı sonsuza kadar bekletirdi.
    monkeypatch.setattr(desktop, "_uyari_goster",
                        lambda *a, **k: pytest.fail("bu kipte uyarı gösterilmemeli"))

    with pytest.raises(SystemExit) as exc_info:
        desktop.main([desktop.ONYUKLEME_BAYRAGI])

    assert exc_info.value.code == 0


def test_an_unrelated_argument_does_not_trigger_the_preflight(monkeypatch):
    """Explorer kısayolları ve sürükle-bırak beklenmedik argüman geçirebiliyor;
    hiçbiri normal açılışı engellememeli (argparse'ın kaçındığımız davranışı)."""
    kostu: list[str] = []
    monkeypatch.setattr(desktop, "_run", lambda: kostu.append("run"))
    monkeypatch.setattr(desktop, "_onyukleme_denetimi_guvenli",
                        lambda: pytest.fail("denetim kipi tetiklenmemeli"))

    desktop.main([r"C:\Users\x\Desktop\bir-dosya.png", "--baska-bir-sey"])

    assert kostu == ["run"]
