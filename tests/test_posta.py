"""E-posta gönderimi — `services/posta.py` (Faz 1 / 3): iki arka uç, şablonlar, seçim.

Resend'e HİÇBİR test gerçek istek atmaz: `httpx.MockTransport` isteği
yakalar ve bu dosya onun BİÇİMİNİ sınar (adres, yetki başlığı, JSON gövde).
Konsol arka ucu diske yazıyor (`posta.log`) — `tmp_path`e.
"""
from __future__ import annotations

import json
import os

import httpx
import pytest
from fastapi.testclient import TestClient

import app as appmod
import i18n
from services import posta

KIME = "ali@example.com"


@pytest.fixture(autouse=True)
def _ortam(monkeypatch):
    for ad in (posta.POSTA_ENV, posta.RESEND_ANAHTAR_ENV, posta.GONDEREN_ENV):
        monkeypatch.delenv(ad, raising=False)


# ── Konsol ───────────────────────────────────────────────────────────

def test_the_console_backend_logs_the_mail_and_keeps_the_last_one(tmp_path):
    postaci = posta.KonsolPostaci(str(tmp_path / "veri"))
    assert postaci.son is None
    postaci.gonder(posta.Posta(KIME, "Konu", "Gövde\nikinci satır"))
    assert postaci.son == posta.Posta(KIME, "Konu", "Gövde\nikinci satır")
    with open(tmp_path / "veri" / posta.POSTA_LOG, encoding="utf-8", newline="") as f:
        metin = f.read()
    assert f"KIME: {KIME}" in metin and "KONU: Konu" in metin and "ikinci satır" in metin
    assert "\r\n" not in metin, "posta.log LF ile yazılmalı (.gitattributes disiplini)"


def test_the_console_backend_survives_an_unwritable_directory(tmp_path):
    """Günlük yazılamasa da `son` dolu: E2E bağlantıyı yine okur, hata `hata.log`a."""
    dosya = tmp_path / "dosya"
    dosya.write_text("x", encoding="utf-8")
    postaci = posta.KonsolPostaci(str(dosya))   # dizin DEĞİL dosya: makedirs/open düşer
    postaci.gonder(posta.Posta(KIME, "K", "M"))
    assert postaci.son is not None and postaci.son.kime == KIME


def test_no_backend_sends_to_an_invalid_address_because_that_is_the_deleted_accounts_domain(tmp_path):
    """Faz 4 / 5 (K9): silinen hesabın e-postası `silindi-<id>@anonim.invalid` — RFC 2606 rezerve TLD.
    İki arka uç da kapıda döner: konsol `son`u yazmaz, Resend'e istek hiç çıkmaz."""
    import uuid

    from services import hesap
    anonim = hesap.anonim_eposta(uuid.uuid4())
    assert anonim.endswith("@" + hesap.ANONIM_ALAN) and anonim.endswith(posta.GONDERILMEYEN_TLD)
    konsol = posta.KonsolPostaci(str(tmp_path / "veri"))
    with pytest.raises(posta.PostaHatasi, match="invalid"):
        konsol.gonder(posta.Posta(anonim, "K", "M"))
    assert konsol.son is None and not (tmp_path / "veri" / posta.POSTA_LOG).exists()
    istekler: list[httpx.Request] = []

    def _yakala(r: httpx.Request) -> httpx.Response:
        istekler.append(r)
        return httpx.Response(200, json={"id": "x"})
    resend = posta.ResendPostaci("re_DUMMY", "Kromis <no-reply@example.com>",
                                 httpx.Client(transport=httpx.MockTransport(_yakala)))
    with pytest.raises(posta.PostaHatasi, match="invalid"):
        resend.gonder(posta.Posta(anonim.upper(), "K", "M"))
    assert istekler == [], "Resend'e istek çıkmadı"
    resend.gonder(posta.Posta(KIME, "K", "M"))
    assert len(istekler) == 1, "sıradan adres yine gider"


@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_the_deletion_mail_says_when_the_content_goes_and_carries_no_link(lang):
    ileti = posta.silme_postasi(KIME, lang, gun=7)
    assert ileti.kime == KIME and ileti.konu == i18n.t("posta.silme_konu", lang) != "posta.silme_konu"
    assert "7" in ileti.metin and "{" not in ileti.metin and "http" not in ileti.metin, "geri alma bağlantısı yok (K9)"


# ── Şablonlar ────────────────────────────────────────────────────────

@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_the_verification_mail_carries_the_link_the_ttl_and_the_language(lang):
    ileti = posta.dogrulama_postasi(KIME, "https://x/giris?dogrula=JETON", lang, saat=24)
    assert ileti.kime == KIME
    assert ileti.konu == i18n.t("posta.dogrulama_konu", lang) != "posta.dogrulama_konu"
    assert "https://x/giris?dogrula=JETON" in ileti.metin and "24" in ileti.metin
    assert "{" not in ileti.metin, "yerleştirilmemiş değişken kaldı"


@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_the_reset_and_existing_account_mails_are_translated(lang):
    sifirla = posta.sifirlama_postasi(KIME, "https://x/giris?sifirla=J", lang, dakika=60)
    assert "https://x/giris?sifirla=J" in sifirla.metin and "60" in sifirla.metin
    assert sifirla.konu == i18n.t("posta.sifirlama_konu", lang)
    mevcut = posta.mevcut_hesap_postasi(KIME, "https://x/giris", lang)
    assert "https://x/giris" in mevcut.metin and "{" not in mevcut.metin


def test_the_two_languages_really_differ():
    tr = posta.dogrulama_postasi(KIME, "L", "tr", saat=24).metin
    en = posta.dogrulama_postasi(KIME, "L", "en", saat=24).metin
    assert tr != en and "Merhaba" in tr and "Hello" in en


# ── Resend ───────────────────────────────────────────────────────────

def _sahte_resend(durum: int, kayit: list[httpx.Request]) -> httpx.Client:
    def _cevapla(istek: httpx.Request) -> httpx.Response:
        kayit.append(istek)
        return httpx.Response(durum, json={"id": "e_1"} if durum < 300 else {"message": "hata"})
    return httpx.Client(transport=httpx.MockTransport(_cevapla))


def test_the_resend_backend_posts_the_expected_json_with_a_bearer_token():
    kayit: list[httpx.Request] = []
    postaci = posta.ResendPostaci("re_gizli", "Kromis <no-reply@example.com>",
                                  istemci=_sahte_resend(200, kayit))
    postaci.gonder(posta.Posta(KIME, "Konu", "Metin"))
    assert len(kayit) == 1
    istek = kayit[0]
    assert istek.method == "POST" and str(istek.url) == posta.RESEND_ADRESI
    assert istek.headers["authorization"] == "Bearer re_gizli"
    assert json.loads(istek.content) == {"from": "Kromis <no-reply@example.com>", "to": [KIME],
                                         "subject": "Konu", "text": "Metin"}


@pytest.mark.parametrize("durum", [400, 401, 422, 429, 500])
def test_a_non_2xx_from_resend_is_a_posta_error_naming_only_the_status(durum):
    postaci = posta.ResendPostaci("re_x", "a@b.c", istemci=_sahte_resend(durum, []))
    with pytest.raises(posta.PostaHatasi) as hata:
        postaci.gonder(posta.Posta(KIME, "K", "M"))
    assert str(durum) in str(hata.value) and KIME not in str(hata.value)


def test_a_network_failure_is_a_posta_error_too():
    def _kopar(istek: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("kopuk")
    postaci = posta.ResendPostaci("re_x", "a@b.c",
                                  istemci=httpx.Client(transport=httpx.MockTransport(_kopar)))
    with pytest.raises(posta.PostaHatasi):
        postaci.gonder(posta.Posta(KIME, "K", "M"))


def test_the_resend_backend_refuses_to_exist_without_key_or_sender():
    with pytest.raises(ValueError):
        posta.ResendPostaci("", "a@b.c")
    with pytest.raises(ValueError):
        posta.ResendPostaci("re_x", "")


# ── Seçim ────────────────────────────────────────────────────────────

def test_without_any_setting_the_console_backend_is_chosen(tmp_path):
    assert posta.secim() == "konsol"
    assert isinstance(posta.postaci_kur(str(tmp_path)), posta.KonsolPostaci)


def test_a_resend_key_alone_selects_resend(monkeypatch, tmp_path):
    monkeypatch.setenv(posta.RESEND_ANAHTAR_ENV, "re_x")
    monkeypatch.setenv(posta.GONDEREN_ENV, "a@b.c")
    assert posta.secim() == "resend"
    assert isinstance(posta.postaci_kur(str(tmp_path)), posta.ResendPostaci)


def test_an_explicit_console_setting_beats_the_key(monkeypatch, tmp_path):
    monkeypatch.setenv(posta.RESEND_ANAHTAR_ENV, "re_x")
    monkeypatch.setenv(posta.POSTA_ENV, "konsol")
    assert isinstance(posta.postaci_kur(str(tmp_path)), posta.KonsolPostaci)


@pytest.mark.parametrize("ortam", [
    {posta.POSTA_ENV: "resend"},                                   # anahtar yok
    {posta.POSTA_ENV: "resend", posta.RESEND_ANAHTAR_ENV: "re_x"},  # gönderen yok
    {posta.POSTA_ENV: "smtp"},                                     # tanınmayan
])
def test_a_misconfigured_backend_fails_loudly_at_send_time_not_silently_to_console(
        monkeypatch, tmp_path, ortam):
    for ad, deger in ortam.items():
        monkeypatch.setenv(ad, deger)
    postaci = posta.postaci_kur(str(tmp_path))
    assert isinstance(postaci, posta.BozukPostaci)
    with pytest.raises(posta.PostaHatasi) as hata:
        postaci.gonder(posta.Posta(KIME, "K", "M"))
    assert posta.POSTA_ENV in str(hata.value)
    assert not os.path.exists(tmp_path / posta.POSTA_LOG), "konsola düşmemeli"


# ── Lifespan ─────────────────────────────────────────────────────────

def test_the_lifespan_installs_a_mailer_and_removes_it_on_shutdown(dizinler, tmp_path):
    dizinler(data_dir=str(tmp_path))
    assert appmod.app.state.postaci is None
    with TestClient(appmod.app):
        assert isinstance(appmod.app.state.postaci, posta.KonsolPostaci)
        assert appmod.app.state.postaci.data_dir == str(tmp_path)
    assert appmod.app.state.postaci is None


def test_without_a_lifespan_the_account_routes_say_mail_is_unavailable_not_500(dizinler, tmp_path):
    """`with`siz TestClient: postacı yok → 503 + kod (services/db.py'nin 503 deseni)."""
    dizinler(data_dir=str(tmp_path))
    from routers import hesap as hesap_rotalari
    cevap = TestClient(appmod.app).post("/api/hesap/kayit",
                                        json={"eposta": KIME, "parola": "12345678", "sartlar": True})
    assert cevap.status_code == 503
    assert cevap.json()["detail"] in ("database_unavailable", hesap_rotalari.POSTACI_YOK)
