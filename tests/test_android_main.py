"""android_main: oturum çerezi kapısı ve Android ortam hazırlığı.

Bu dosyanın var oluş sebebi Faz 3'teki güvenlik kararı: sunucu 127.0.0.1'i
dinliyor ama Android'de loopback cihazdaki HER uygulamaya açık ve `app.py`'de
ne CORS ne kimlik denetimi var. Kapı çalışmazsa yan yüklenmiş herhangi bir
uygulama `GET /api/settings` ile Azure anahtarına uzanabilir — yani buradaki
iddialar kozmetik değil.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import android_main
import paths


def _guarded_app(token: str) -> FastAPI:
    app = FastAPI()

    @app.get("/api/gizli")
    def gizli():
        return {"deger": "anahtar"}

    app.add_middleware(android_main.SessionCookieGuard, token=token)
    return app


def test_request_without_the_cookie_is_refused():
    with TestClient(_guarded_app("dogru-token")) as istemci:
        yanit = istemci.get("/api/gizli")
    assert yanit.status_code == 403
    # Gövde Türkçe ve JSON DEĞİL: bu yanıtı arayüz hiç görmüyor (uygulama her
    # zaman çerezli), gören taraf cihazdaki başka bir uygulama.
    assert "yalnızca uygulama" in yanit.text


def test_request_with_the_right_cookie_passes_through():
    istemci = TestClient(_guarded_app("dogru-token"))
    istemci.cookies.set(android_main.SESSION_COOKIE, "dogru-token")
    with istemci:
        yanit = istemci.get("/api/gizli")
    assert yanit.status_code == 200
    assert yanit.json() == {"deger": "anahtar"}


def test_wrong_token_is_refused():
    istemci = TestClient(_guarded_app("dogru-token"))
    istemci.cookies.set(android_main.SESSION_COOKIE, "yanlis-token")
    with istemci:
        assert istemci.get("/api/gizli").status_code == 403


def test_a_prefix_of_the_token_is_not_enough():
    """Eşitlik karşılaştırması TAM olmalı — `startswith` sınıfı bir kusur olmasın."""
    istemci = TestClient(_guarded_app("dogru-token"))
    istemci.cookies.set(android_main.SESSION_COOKIE, "dogru")
    with istemci:
        assert istemci.get("/api/gizli").status_code == 403


def test_the_cookie_is_found_among_others():
    """Çerez başlığında başka çerezler de varsa kapı yine açılmalı.

    WebView zamanla başka çerezler biriktirebilir; token'ı yalnız TEK çerez
    varken tanıyan bir kapı ilerde sessizce kilitlerdi.
    """
    istemci = TestClient(_guarded_app("dogru-token"))
    istemci.cookies.set("baska", "deger")
    istemci.cookies.set(android_main.SESSION_COOKIE, "dogru-token")
    istemci.cookies.set("ucuncu", "sey")
    with istemci:
        assert istemci.get("/api/gizli").status_code == 200


def test_static_files_are_not_exempt():
    """Muafiyet yok: arayüzün kendisi de token istiyor.

    index.html hangi uçların var olduğunu ve JS'in tamamını sızdırır; statik
    yolu muaf tutmak kapıyı yarı açık bırakırdı.
    """
    app = FastAPI()

    @app.get("/")
    def kok():
        return {"ok": True}

    app.add_middleware(android_main.SessionCookieGuard, token="t")
    with TestClient(app) as istemci:
        assert istemci.get("/").status_code == 403


def test_lifespan_still_runs_behind_the_guard():
    """Kapı `lifespan` mesajlarına DOKUNMAMALI.

    Kesseydi açılış kancaları (dizin açma → yedek → tohumlama) hiç koşmazdı ve
    uygulama telefonda boş bir galeriyle açılırdı.
    """
    izler: list[str] = []

    # `@app.on_event("startup")` DEĞİL: Starlette 1.0 onu kaldırdı, FastAPI
    # 0.128.3 yalnız uyumluluk için (DeprecationWarning ile) geri koydu.
    # Sınanan şey aynı — kapı lifespan mesajlarını geçiriyor mu — ve
    # uygulamanın kendisi de `app.py`de aynı `lifespan=` yolunu kullanıyor.
    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        izler.append("startup")
        yield

    app = FastAPI(lifespan=_lifespan)
    app.add_middleware(android_main.SessionCookieGuard, token="t")
    with TestClient(app):
        pass
    assert izler == ["startup"]


def test_tokens_are_unique_and_long_enough():
    tokenlar = {android_main.new_session_token() for _ in range(50)}
    assert len(tokenlar) == 50
    # token_urlsafe(32) base64'te ~43 karakter üretir.
    assert all(len(t) >= 40 for t in tokenlar)


def test_prepare_environment_opens_the_android_branch(monkeypatch):
    monkeypatch.delenv(paths.ANDROID_DATA_ENV, raising=False)
    monkeypatch.delenv(paths.ANDROID_RESOURCE_ENV, raising=False)

    android_main._prepare_environment("/data/veri", "/data/veri/resources")

    assert paths.is_android()
    assert paths.data_dir() == "/data/veri"
    assert paths.resource_dir() == "/data/veri/resources"


def test_prepare_environment_rejects_an_empty_data_dir(monkeypatch):
    """Boş bir kök sessizce kabul edilirse yazma yolları APK'nın içine düşer."""
    monkeypatch.delenv(paths.ANDROID_DATA_ENV, raising=False)
    with pytest.raises(ValueError):
        android_main._prepare_environment("", "")


def test_stop_is_safe_when_nothing_started():
    """Servis hiç başlamadan öldürülebilir; `stop()` bunu sessizce yutmalı."""
    android_main._state.clear()
    android_main.stop()  # fırlatmamalı


def test_stop_keeps_the_token_for_a_restart():
    """`stop()` token'ı SİLMEMELİ.

    Servis öldürülüp Activity uygulamayı geri getirdiğinde ikinci bir `start()`
    koşuyor. Token orada yenilenseydi WebView'deki çerez bayatlar ve arayüz —
    hiçbir şey görünürde bozulmadan — her istekte 403 alırdı. Ayrıca
    `app.add_middleware` ikinci kez çağrılamaz: Starlette katman yığınını ilk
    istekte kuruyor ve sonraki eklemeler RuntimeError veriyor.
    """
    android_main._state.clear()
    onceki = android_main._token
    try:
        android_main._token = "kalici-token"
        android_main.stop()
        assert android_main._token == "kalici-token"
    finally:
        android_main._token = onceki
