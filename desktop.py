"""Masaüstü başlatıcı: uvicorn'u thread'de çalıştırır, native pencerede gösterir.

Neden port=0: sabit port (run.sh'teki 8765) ikinci bir örnek açıldığında ya da
bayat bir süreç ayakta kaldığında çakışıyordu. Çekirdekten boş port istemek bu
sınıf hatayı tümüyle kaldırır; pencere gerçek portu çalışma anında öğrenir.

Pencere kapanınca uvicorn'a çıkış işaretlenir ve thread beklenir — süreç arkada
asılı kalmaz.
"""
from __future__ import annotations

import threading
import time

import uvicorn
from fastapi import FastAPI

import paths

WINDOW_TITLE = "GPT-Image Studio"
WINDOW_SIZE = (1440, 900)
MIN_WINDOW_SIZE = (1024, 700)
_POLL_INTERVAL = 0.02


def start_server(fastapi_app: FastAPI, host: str = "127.0.0.1",
                 timeout: float = 15.0) -> tuple[uvicorn.Server, threading.Thread, int]:
    """Sunucuyu boş bir portta daemon thread'de başlatır; (sunucu, thread, port) döner."""
    config = uvicorn.Config(fastapi_app, host=host, port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="uvicorn")
    thread.start()

    deadline = time.monotonic() + timeout
    while not server.started:
        if not thread.is_alive():
            raise RuntimeError("sunucu başlatılamadı (thread öldü)")
        if time.monotonic() > deadline:
            server.should_exit = True
            raise RuntimeError(f"sunucu başlatılamadı ({timeout} sn içinde hazır olmadı)")
        time.sleep(_POLL_INTERVAL)

    port = server.servers[0].sockets[0].getsockname()[1]
    return server, thread, port


def main() -> None:
    import webview  # yalnız pencere yolunda gerekir; testler bunu import etmez

    paths.ensure_data_dirs()
    import app as appmod  # yollar hazır olduktan sonra

    server, thread, port = start_server(appmod.app)
    try:
        webview.create_window(WINDOW_TITLE, f"http://127.0.0.1:{port}",
                              width=WINDOW_SIZE[0], height=WINDOW_SIZE[1],
                              min_size=MIN_WINDOW_SIZE)
        webview.start()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
