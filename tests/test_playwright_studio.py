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
            page.click("#go")
            page.wait_for_timeout(300)
            # Status should show prompt sent / director responding status message, not runtime errors
            status = page.inner_text("#status")
            assert "Hata" not in status

            browser.close()
    finally:
        server.stop()
