"""desktop.start_server gerçek bir sokete bağlanır — pencere kısmı manuel doğrulanır."""
import sys
import threading
import time
import types

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

import desktop
import seed


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
                            min_size: tuple[int, int]) -> None:
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
    # app.app'in lifespan'ı gerçekten çalışıyor (bu testin amacı budur) ama
    # seed.seed_builtin_logos gerçek dosya sistemine (repo kökündeki .logos-seeded
    # ve assets/logos/) yazar — testler kullanıcının gerçek kütüphanesine dokunmamalı.
    monkeypatch.setattr(seed, "seed_builtin_logos", lambda *args, **kwargs: [])

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
                            min_size: tuple[int, int]) -> None:
        seen["at_create_window"] = fake_webview.settings["ALLOW_DOWNLOADS"]

    def fake_start() -> None:
        seen["at_start"] = fake_webview.settings["ALLOW_DOWNLOADS"]

    fake_webview.create_window = fake_create_window
    fake_webview.start = fake_start
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setattr("paths.ensure_data_dirs", lambda: None)
    monkeypatch.setattr(seed, "seed_builtin_logos", lambda *args, **kwargs: [])

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

    alert_calls: list[tuple] = []
    monkeypatch.setattr(desktop.subprocess, "run",
                        lambda *a, **k: alert_calls.append((a, k)))

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


def test_alert_failure_does_not_crash_main(monkeypatch, tmp_path):
    """I1: uyarı gösterme denemesinin kendisi patlarsa bile main() yine de
    (loglanmış, non-zero) temiz çıkmalı — kullanıcı hâlâ hiçbir şey görmese
    de süreç asılı kalmamalı."""
    monkeypatch.setattr(desktop.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(desktop, "_run", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    def boom_subprocess(*args, **kwargs):
        raise OSError("osascript bulunamadı (simüle)")

    monkeypatch.setattr(desktop.subprocess, "run", boom_subprocess)

    with pytest.raises(SystemExit) as exc_info:
        desktop.main()
    assert exc_info.value.code == 1
    assert (tmp_path / "hata.log").is_file()
