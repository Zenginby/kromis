"""Köken kapısı — `services/koken.py` (Faz 1 / 3): CSRF'nin ikinci katı.

Ölçüt: durum değiştiren (GET/HEAD/OPTIONS dışı) bir istek başka bir siteden
geliyorsa 403 + `cross_origin_rejected`; aynı kökenden ya da tarayıcı
olmayan bir istemciden geliyorsa kapıdan geçer. "Geçti"nin işareti burada
422: hedef `POST /api/palette/suggest` boş gövdeyle doğrulama hatası veriyor —
yani istek rotaya ULAŞTI; 403 ise ulaşmadı. O rota diske, ağa ve DB'ye
dokunmayan tek POST (`Depends` bile yok), böylece bu dosya `veritabani`
fixture'ına da `dizinler`e de muhtaç değil. (`/api/hesap/*` uygun değildi:
`OTURUM` bağımlılığı gövdeden ÖNCE çözülüyor ve motor yokken 503 diyor.)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

import app as appmod
from services import koken

HEDEF = "/api/palette/suggest"


def _istemci(**basliklar: str) -> TestClient:
    return TestClient(appmod.app, headers=basliklar)


def _gecti(cevap) -> bool:
    """Kapıdan geçen istek rotaya varır ve boş gövde 422 alır; 403 kapının kendisi."""
    assert cevap.status_code in (403, 422), cevap.status_code
    return cevap.status_code == 422


@pytest.fixture(autouse=True)
def _koken_ayarsiz(monkeypatch):
    monkeypatch.delenv(koken.KOKEN_ENV, raising=False)


# ── Sec-Fetch-Site: tarayıcının kendi yazdığı kanıt ─────────────────

@pytest.mark.parametrize("deger", ["cross-site", "same-site", "CROSS-SITE", " cross-site "])
def test_a_post_from_another_site_is_rejected_with_a_code(deger):
    cevap = _istemci(**{"Sec-Fetch-Site": deger}).post(HEDEF, json={})
    assert cevap.status_code == 403
    assert cevap.json() == {"detail": koken.REDDEDILDI}


@pytest.mark.parametrize("deger", ["same-origin", "none"])
def test_a_post_from_the_same_origin_or_the_address_bar_passes(deger):
    assert _gecti(_istemci(**{"Sec-Fetch-Site": deger}).post(HEDEF, json={}))


def test_sec_fetch_site_wins_over_origin_in_both_directions():
    """Başlık varsa son söz onun: iyi bir `Origin` kötü `Sec-Fetch-Site`i kurtarmaz, tersi de."""
    assert not _gecti(_istemci(**{"Sec-Fetch-Site": "cross-site",
                                  "Origin": "http://testserver"}).post(HEDEF, json={}))
    assert _gecti(_istemci(**{"Sec-Fetch-Site": "same-origin",
                              "Origin": "https://kotu.example"}).post(HEDEF, json={}))


# ── Origin / Referer: eski tarayıcılar ───────────────────────────────

def test_an_origin_equal_to_the_requests_own_origin_passes():
    assert _gecti(_istemci(Origin="http://testserver").post(HEDEF, json={}))
    assert _gecti(_istemci(Origin="HTTP://TestServer/").post(HEDEF, json={}))


@pytest.mark.parametrize("deger", ["https://kotu.example", "null", "http://testserver.evil",
                                   "https://testserver", "bozuk"])
def test_a_foreign_opaque_or_malformed_origin_is_rejected(deger):
    assert not _gecti(_istemci(Origin=deger).post(HEDEF, json={}))


def test_the_configured_public_origin_is_accepted_after_normalisation(monkeypatch):
    """Vekil arkasında isteğin kendi kökeni iç adres olur; `KROMIS_KOKEN` dış adresi tanıtır."""
    monkeypatch.setenv(koken.KOKEN_ENV, "https://Studio.Example.com/")
    assert _gecti(_istemci(Origin="https://studio.example.com").post(HEDEF, json={}))
    assert _gecti(_istemci(Origin="http://testserver").post(HEDEF, json={}))   # kendi kökeni de
    assert not _gecti(_istemci(Origin="https://studio.example.com.evil").post(HEDEF, json={}))


def test_referer_is_consulted_only_when_origin_is_absent():
    assert _gecti(_istemci(Referer="http://testserver/giris?x=1").post(HEDEF, json={}))
    assert not _gecti(_istemci(Referer="https://kotu.example/sayfa").post(HEDEF, json={}))
    # Origin varken Referer'a bakılmaz: kötü Origin, iyi Referer → 403.
    assert not _gecti(_istemci(Origin="https://kotu.example",
                               Referer="http://testserver/").post(HEDEF, json={}))


# ── Tarayıcı olmayan istemci ve güvenli fiiller ──────────────────────

def test_a_client_that_sends_none_of_the_three_headers_passes():
    """curl / TestClient / sonda: kurbanın çerezini taşıyamaz, CSRF tehdidi değil (gerekçe modülde)."""
    assert _gecti(TestClient(appmod.app).post(HEDEF, json={}))


@pytest.mark.parametrize("yontem", ["GET", "HEAD", "OPTIONS"])
def test_safe_methods_are_never_gated(yontem):
    cevap = _istemci(**{"Sec-Fetch-Site": "cross-site"}).request(yontem, "/")
    assert cevap.status_code != 403


@pytest.mark.parametrize("yontem", ["PUT", "DELETE", "PATCH"])
def test_every_unsafe_method_is_gated(yontem):
    cevap = _istemci(**{"Sec-Fetch-Site": "cross-site"}).request(yontem, "/api/palettes/x")
    assert cevap.status_code == 403


# ── Yerleşim ─────────────────────────────────────────────────────────

def test_the_gate_sits_right_inside_the_request_id_layer_and_before_language():
    """Belge §3 → §9: istek kimliği → köken → dil → rota. Starlette listede İLK olanı en dışa koyar;
    kimlik katmanı dışta ki köken 403'ü de `X-Request-ID` ve erişim satırı taşısın."""
    from services import dil, istek_kimligi
    zincir = [m.kwargs.get("dispatch") for m in appmod.app.user_middleware]
    assert zincir[0] is istek_kimligi.istek_kimligi and zincir[1] is koken.koken_kapisi, zincir
    assert dil.dil_baglami in zincir and zincir.index(dil.dil_baglami) > 1


def _istek(basliklar: dict[str, str], scheme: str = "http", host: str = "testserver") -> Request:
    return Request({"type": "http", "method": "POST", "scheme": scheme, "path": "/",
                    "headers": [(k.lower().encode(), v.encode()) for k, v in basliklar.items()],
                    "server": (host, 80), "app": appmod.app})


def test_the_link_base_is_the_public_origin_or_the_requests_own(monkeypatch):
    istek = _istek({"host": "127.0.0.1:8765"})
    assert koken.taban(istek) == "http://127.0.0.1:8765"
    monkeypatch.setenv(koken.KOKEN_ENV, "https://studio.example.com/")
    assert koken.taban(istek) == "https://studio.example.com"
    monkeypatch.setenv(koken.KOKEN_ENV, "   ")
    assert koken.yapilandirilan() is None
