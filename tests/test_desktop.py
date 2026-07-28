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

    fake_webview = types.ModuleType("webview")

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
