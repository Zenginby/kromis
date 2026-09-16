"""Masaüstü istek kaynağı kapısının bekçisi (`netguard.LoopbackGuard`).

Kapatılan iki yol ayrı ayrı sınanıyor:

  * CSRF — kullanıcının tarayıcısındaki bir sayfa `multipart/form-data` alan
    uçlara (`/api/edit`, `/api/import`, `/api/assets/{kind}`) ÖN UÇUŞSUZ istek
    atabiliyordu; yanıtı okuyamasa da isteği çalıştırıyor, yani ücretli kotayı
    harcıyordu. Kapı yabancı `Origin`'i kesiyor.
  * DNS rebinding — `Host` hiç denetlenmiyordu; 127.0.0.1'e çözülen bir alan
    adı tarayıcıya sunucuyu aynı kaynak gösteriyordu.

Katman `app.py`'de DEĞİL, giriş noktalarında takılı (bkz. netguard.py). Bu
yüzden burada gerçek bir ASGI uygulaması sarılıp SOKET ÜZERİNDEN sınanıyor:
`TestClient(appmod.app)` kapıyı hiç görmez ve gördüğünü sanmak, mandalın
sessizce anlamsızlaşması demek olurdu.
"""
import socket
import threading
import time

import httpx
import pytest
import uvicorn

import netguard

# ── Konak adı ayrıştırma ────────────────────────────────────────────

@pytest.mark.parametrize("basligi,beklenen", [
    ("127.0.0.1:8765", "127.0.0.1"),
    ("127.0.0.1", "127.0.0.1"),
    ("LocalHost:52341", "localhost"),
    ("[::1]:8765", "[::1]"),          # köşeli parantezli IPv6 + port
    ("::1", "::1"),                   # çıplak IPv6, port yok
    ("evil.example.com:8765", "evil.example.com"),
])
def test_host_header_is_split_without_breaking_ipv6(basligi, beklenen):
    assert netguard.konak_adi(basligi) == beklenen


# ── Kapının kendisi (ASGI düzeyinde) ────────────────────────────────

async def _sahte_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"gecti"})


def _scope(host=b"127.0.0.1:8765", origin=None):
    headers = []
    if host is not None:
        headers.append((b"host", host))
    if origin is not None:
        headers.append((b"origin", origin))
    return {"type": "http", "headers": headers}


def _izinli(**kw) -> bool:
    return netguard.LoopbackGuard(_sahte_app)._izinli(_scope(**kw))


def test_loopback_host_without_origin_passes():
    """Sıradan bir GET: tarayıcı `Origin` göndermiyor, `Host` bizim."""
    assert _izinli() is True


@pytest.mark.parametrize("host", [b"127.0.0.1:8765", b"localhost:8765",
                                  b"[::1]:8765", b"127.0.0.1"])
def test_every_loopback_spelling_passes(host):
    assert _izinli(host=host) is True


def test_foreign_host_is_rejected_even_without_origin():
    """DNS rebinding: alan adı 127.0.0.1'e çözülse de `Host` onu ele veriyor."""
    assert _izinli(host=b"rebind.example.com:8765") is False


def test_missing_host_is_rejected():
    """HTTP/1.1'de zorunlu; yokluğu bir tarayıcı isteği değil."""
    assert _izinli(host=None) is False


def test_matching_origin_passes():
    assert _izinli(host=b"127.0.0.1:8765",
                   origin=b"http://127.0.0.1:8765") is True


def test_foreign_origin_is_rejected():
    """CSRF: sayfa `Origin`i uyduramıyor, tarayıcı kendi adresini yazıyor."""
    assert _izinli(host=b"127.0.0.1:8765",
                   origin=b"https://evil.example.com") is False


def test_same_host_but_different_port_is_rejected():
    """Aynı makinedeki BAŞKA bir yerel sunucu da yabancı bir kaynaktır."""
    assert _izinli(host=b"127.0.0.1:8765",
                   origin=b"http://127.0.0.1:9999") is False


def test_null_origin_is_rejected():
    """Sandbox'lı iframe / `file://` — eşleşmiyor, yani geçmiyor."""
    assert _izinli(host=b"127.0.0.1:8765", origin=b"null") is False


def test_lifespan_scope_bypasses_the_check_entirely():
    """Kesilirse açılış kancaları (dizin açma, yedek) HİÇ çalışmazdı.

    `_izinli` başlıksız bir kapsamı elbette reddeder; sınanan şey `__call__`ın
    o soruyu lifespan'da hiç SORMAMASI — yani isteğin sarılan uygulamaya
    devredilmesi."""
    import asyncio

    ulasildi = []

    async def _kaydet(scope, receive, send):
        ulasildi.append(scope["type"])

    guard = netguard.LoopbackGuard(_kaydet)
    asyncio.run(guard({"type": "lifespan"}, None, None))

    assert ulasildi == ["lifespan"]


# ── Uçtan uca: gerçek uvicorn, gerçek soket ─────────────────────────

def _bos_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def sunucu():
    """`netguard.sar` ile sarılmış bir uvicorn — desktop.py'nin kurduğu düzen."""
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/api/history")
    def _history():
        return {"images": []}

    @app.post("/api/import")
    def _import():
        return {"ok": True}

    port = _bos_port()
    # `ws="none"`: bu uygulamada websocket yok ve "auto" keşfi yalnızca
    # kullanılmayan bir kitaplığı import edip uyarı üretiyor.
    cfg = uvicorn.Config(netguard.sar(app), host="127.0.0.1", port=port,
                         log_level="error", ws="none")
    server = uvicorn.Server(cfg)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "sunucu açılmadı"
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(timeout=5)


def test_the_apps_own_request_still_works(sunucu):
    """Kapının BİRİNCİ ödevi: uygulamayı kendi kapısından çevirmemek."""
    r = httpx.get(f"{sunucu}/api/history")
    assert r.status_code == 200


def test_a_same_origin_post_still_works(sunucu):
    """Arayüzün `fetch`i güvenli olmayan yöntemde kendi kaynağını gönderiyor."""
    r = httpx.post(f"{sunucu}/api/import", headers={"Origin": sunucu})
    assert r.status_code == 200


def test_a_cross_origin_multipart_post_is_blocked(sunucu):
    """Asıl kapatılan delik: ön uçuşsuz geçen multipart isteği."""
    r = httpx.post(f"{sunucu}/api/import",
                   headers={"Origin": "https://evil.example.com"},
                   files={"file": ("x.png", b"\x89PNG", "image/png")})
    assert r.status_code == 403
    assert "yalnızca uygulamanın" in r.text
    # İKİ DİLLİ gövdenin bekçisi: İngilizce yarısı düşerse, dil bağlamı hiç
    # kurulmayan bu yanıt sessizce tek dile geri dönmüş olur.
    assert "Only this app's own window" in r.text


def test_a_rebound_hostname_is_blocked(sunucu):
    """`Host` başkasını gösteriyor: bağlantı loopback'e gelse de reddediliyor."""
    r = httpx.get(f"{sunucu}/api/history",
                  headers={"Host": "rebind.example.com"})
    assert r.status_code == 403


def test_the_rejection_is_not_cacheable(sunucu):
    """Bayat bir 403 arayüzü kalıcı olarak kilitlerdi."""
    r = httpx.get(f"{sunucu}/api/history", headers={"Host": "evil.example.com"})
    assert r.headers["cache-control"] == "no-store"


# ── Bağlantı: giriş noktaları kapıyı GERÇEKTEN takıyor mu ───────────

def test_desktop_serves_the_wrapped_app_not_the_bare_one():
    """Sunucuya SARMAL gitmezse kapı hiç devrede olmaz — sessiz başarısızlık."""
    with open("desktop.py", encoding="utf-8") as f:
        kaynak = f.read()
    assert "start_server(netguard.sar(appmod.app))" in kaynak
    assert "start_server(appmod.app)" not in kaynak


def test_run_sh_serves_through_the_factory_not_the_bare_app():
    """8765 sabit olduğu için CSRF'nin en kolay hedefi geliştirme sunucusu."""
    with open("run.sh", encoding="utf-8") as f:
        kaynak = f.read()
    assert "--factory netguard:korumali_app" in kaynak
    assert "exec uvicorn app:app" not in kaynak
