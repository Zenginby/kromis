"""Hesap akışı — `routers/hesap.py` + `services/{hesap,kimlik,cerez}.py` (Faz 1 / 3).

GERÇEK Postgres (`veritabani` fixture'ı), lifespan'lı `TestClient` (motor ve
postacı orada kuruluyor), konsol posta arka ucu: doğrulama ve sıfırlama
bağlantıları `app.state.postaci.son`dan okunuyor — bir gelen kutusundan
değil. `base_url` HTTPS: web modunda (DATABASE_URL var) oturum çerezi `Secure`
ve httpx `Secure` çerezi düz HTTP'ye geri göndermez; bu testler çerezin
gerçekten taşındığını ölçüyor, bayrağı gevşeterek değil şemayı doğru kurarak.

`client=("203.0.113.5", …)`: IP tabanlı hız sınırı gerçek bir adres ister
(`inet` sütunu `"testclient"`i reddeder) ve iki farklı IP'yi ayırt edebilmek
için adres testin elinde olmalı.

`gercek_kimlik` (Faz 1 / 4): conftest'in autouse `kullanici` override'ı bu
dosyada KURULMAZ — "çerezsiz `ben` 401" gibi iddialar kapının kendisini
ölçüyor, sahte bir kullanıcıyla anlamsız kalırdı.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

import app as appmod
import i18n
import models
from services import cerez, hesap, koken, posta
from services.tablolar import GirisDenemesi, Jeton, Kullanici, Oturum
from tests import conftest

pytestmark = pytest.mark.gercek_kimlik

EPOSTA = "ali@example.com"
PAROLA = "cok-gizli-parola"
IP_A = ("203.0.113.5", 40000)
IP_B = ("198.51.100.7", 40000)
HTTPS = "https://testserver"


@pytest.fixture(autouse=True)
def _ortam(monkeypatch, tmp_path, dizinler):
    """Konsol postacı, köken ayarsız, `Secure` öntanımlı; `posta.log` tmp'ye."""
    for ad in (posta.POSTA_ENV, posta.RESEND_ANAHTAR_ENV, posta.GONDEREN_ENV,
               koken.KOKEN_ENV, cerez.GUVENLI_ENV):
        monkeypatch.delenv(ad, raising=False)
    dizinler(data_dir=str(tmp_path))


def _temizle() -> None:
    """Dört hesap tablosunu boşaltır: `veritabani_url` MODÜL kapsamlı (dosya başına
    bir DB, conftest), bu dosyanın testleri ise "EPOSTA henüz yok" öncülüyle
    başlıyor. CASCADE `oturumlar`/`jetonlar`ı da götürür."""
    with _db() as db:
        db.execute(text("TRUNCATE kullanicilar CASCADE"))
        db.execute(text("TRUNCATE giris_denemeleri"))
        db.commit()


@pytest.fixture
def istemci(veritabani):
    with TestClient(appmod.app, base_url=HTTPS, client=IP_A) as c:
        _temizle()
        yield c


def _db() -> Session:
    return Session(appmod.app.state.motor)


def _son_posta() -> posta.Posta:
    son = appmod.app.state.postaci.son
    assert son is not None, "hiç e-posta gitmedi"
    return son


def _jeton(parametre: str) -> str:
    m = re.search(rf"\?{parametre}=([A-Za-z0-9_-]+)", _son_posta().metin)
    assert m, _son_posta().metin
    return m.group(1)


def _kayit(c: TestClient, eposta: str = EPOSTA, parola: str = PAROLA):
    # `sartlar: True` (Faz 4 / 6): kayıt kutusu zorunlu, onaysız 422 — tests/test_hukuk.py ölçer.
    return c.post("/api/hesap/kayit", json={"eposta": eposta, "parola": parola, "sartlar": True})


def _dogrula(c: TestClient) -> None:
    assert c.post("/api/hesap/dogrula", json={"jeton": _jeton("dogrula")}).status_code == 200


def _giris(c: TestClient, eposta: str = EPOSTA, parola: str = PAROLA):
    return c.post("/api/hesap/giris", json={"eposta": eposta, "parola": parola})


def _hazir_hesap(c: TestClient) -> None:
    """Kayıt + doğrulama; oturum AÇMAZ."""
    assert _kayit(c).status_code == 200
    _dogrula(c)


def _kullanici(eposta: str = EPOSTA) -> Kullanici | None:
    with _db() as db:
        return db.scalars(select(Kullanici).where(Kullanici.eposta == eposta)).first()


def _oturum_sayisi() -> int:
    with _db() as db:
        return db.scalar(select(func.count()).select_from(Oturum)) or 0


# ── Kayıt → doğrulama → giriş → ben → çıkış ─────────────────────────

def test_registration_creates_an_unverified_user_and_mails_a_verification_link(istemci):
    cevap = _kayit(istemci)
    assert cevap.status_code == 200 and cevap.json() == {"ok": True}
    k = _kullanici()
    assert k is not None and k.dogrulandi_at is None and k.is_admin is False
    assert k.parola_ozeti and k.parola_ozeti.startswith("$argon2id$")
    assert PAROLA not in k.parola_ozeti
    ileti = _son_posta()
    assert ileti.kime == EPOSTA
    assert f"{HTTPS}/giris?dogrula=" in ileti.metin, "bağlantı isteğin kökeninden"
    assert ileti.konu == i18n.t("posta.dogrulama_konu", "en"), "dil: isteğin dili (öntanımlı en)"


def test_the_verification_link_verifies_the_account_and_is_single_use(istemci):
    _kayit(istemci)
    jeton = _jeton("dogrula")
    assert istemci.post("/api/hesap/dogrula", json={"jeton": jeton}).status_code == 200
    k = _kullanici()
    assert k is not None and k.dogrulandi_at is not None
    tekrar = istemci.post("/api/hesap/dogrula", json={"jeton": jeton})
    assert tekrar.status_code == 400
    assert tekrar.json()["detail"] == i18n.t("err.hesap_jeton_gecersiz", "en")
    assert istemci.post("/api/hesap/dogrula", json={"jeton": "x" * 43}).status_code == 400


def test_an_expired_verification_token_is_rejected(istemci):
    _kayit(istemci)
    jeton = _jeton("dogrula")
    with _db() as db:
        j = db.scalars(select(Jeton)).one()
        j.bitis = hesap.simdi() - dt.timedelta(seconds=1)
        db.commit()
    assert istemci.post("/api/hesap/dogrula", json={"jeton": jeton}).status_code == 400
    k = _kullanici()
    assert k is not None and k.dogrulandi_at is None


def test_login_before_verification_is_refused_and_resends_the_mail(istemci):
    _kayit(istemci)
    ilk = _jeton("dogrula")
    cevap = _giris(istemci)
    assert cevap.status_code == 403
    assert cevap.json()["detail"] == i18n.t("err.hesap_dogrulanmamis", "en")
    assert "set-cookie" not in cevap.headers
    ikinci = _jeton("dogrula")
    assert ikinci != ilk, "yeni bağlantı gitmeli"
    # Eski bağlantı artık geçersiz (aynı amaçlı eski jetonlar silinir), yenisi geçerli.
    assert istemci.post("/api/hesap/dogrula", json={"jeton": ilk}).status_code == 400
    assert istemci.post("/api/hesap/dogrula", json={"jeton": ikinci}).status_code == 200


def test_wrong_password_and_unknown_email_get_the_same_generic_answer(istemci):
    _hazir_hesap(istemci)
    yanlis = _giris(istemci, parola="yanlis-parola")
    yok = _giris(istemci, eposta="yok@example.com", parola=PAROLA)
    assert yanlis.status_code == yok.status_code == 401
    assert yanlis.json() == yok.json() == {"detail": i18n.t("err.hesap_giris_hatali", "en")}
    assert "set-cookie" not in yanlis.headers


def test_login_sets_a_hardened_session_cookie_and_ben_returns_the_user(istemci):
    _hazir_hesap(istemci)
    cevap = _giris(istemci)
    assert cevap.status_code == 200
    govde = cevap.json()
    # `sartlar_guncel` (Faz 4 / 6): onaylanan sürüm bugünkü mü (tests/test_hukuk.py).
    assert set(govde) == {"id", "eposta", "dil", "is_admin", "sartlar_guncel"}
    assert govde["eposta"] == EPOSTA and govde["is_admin"] is False and govde["dil"] == "en"
    uuid.UUID(govde["id"])
    cerez_basligi = cevap.headers["set-cookie"].lower()
    assert cerez_basligi.startswith(f"{cerez.OTURUM_CEREZI}=")
    for bayrak in ("httponly", "samesite=lax", "path=/", f"max-age={cerez.OTURUM_OMRU_SN}", "secure"):
        assert bayrak in cerez_basligi, (bayrak, cerez_basligi)
    ham = cevap.cookies[cerez.OTURUM_CEREZI]
    assert len(ham) >= 43, "token_urlsafe(32)"
    with _db() as db:
        o = db.scalars(select(Oturum)).one()
        assert o.jeton_ozeti == hesap.ozet(ham) and ham.encode() not in o.jeton_ozeti
        assert str(o.ip) == IP_A[0]
        assert o.bitis - o.olusturuldu >= dt.timedelta(days=29, hours=23)
    ben = istemci.get("/api/hesap/ben")
    assert ben.status_code == 200 and ben.json() == govde


def test_ben_without_a_cookie_or_with_a_bogus_cookie_is_401(istemci):
    yok = istemci.get("/api/hesap/ben")
    assert yok.status_code == 401
    assert yok.json()["detail"] == i18n.t("err.hesap_giris_gerekli", "en")
    istemci.cookies.set(cerez.OTURUM_CEREZI, "sahte-jeton-sahte-jeton-sahte-jeton-sahte")
    assert istemci.get("/api/hesap/ben").status_code == 401
    assert istemci.post("/api/hesap/cikis").status_code == 401


def test_logout_deletes_the_session_row_and_clears_the_cookie(istemci):
    _hazir_hesap(istemci)
    _giris(istemci)
    assert _oturum_sayisi() == 1
    cevap = istemci.post("/api/hesap/cikis")
    assert cevap.status_code == 200 and cevap.json() == {"ok": True}
    silme = [h for h in cevap.headers.get_list("set-cookie")
             if h.lower().startswith(f"{cerez.OTURUM_CEREZI}=")]
    assert silme and ("max-age=0" in silme[-1].lower() or "expires=" in silme[-1].lower())
    assert _oturum_sayisi() == 0
    assert istemci.get("/api/hesap/ben").status_code == 401


def test_logout_touches_only_this_devices_session(istemci):
    _hazir_hesap(istemci)
    _giris(istemci)
    # İKİNCİ istemci `with`SİZ ve bilerek: iç içe iki lifespan aynı `app.state`i
    # paylaşır, içteki kapanırken motoru `dispose` eder ve dıştaki istemci
    # motorsuz kalırdı. `with`siz istemci dıştakinin motorunu ve postacısını
    # kullanır — ölçülen şey zaten ikinci bir TARAYICI, ikinci bir süreç değil.
    telefon = TestClient(appmod.app, base_url=HTTPS, client=IP_B)
    assert _giris(telefon).status_code == 200
    assert _oturum_sayisi() == 2
    assert istemci.post("/api/hesap/cikis").status_code == 200
    assert _oturum_sayisi() == 1
    assert telefon.get("/api/hesap/ben").status_code == 200


# ── Kayan ömür ───────────────────────────────────────────────────────

def _oturumu_yasland(dakika: int) -> None:
    with _db() as db:
        o = db.scalars(select(Oturum)).one()
        o.son_gorulme = hesap.simdi() - dt.timedelta(minutes=dakika)
        db.commit()


def test_the_session_slides_at_five_minute_resolution(istemci):
    _hazir_hesap(istemci)
    _giris(istemci)
    # 4 dk: dokunulmaz, çerez yeniden yazılmaz (istek başına UPDATE yok).
    _oturumu_yasland(4)
    cevap = istemci.get("/api/hesap/ben")
    assert cevap.status_code == 200 and "set-cookie" not in cevap.headers
    with _db() as db:
        assert hesap.simdi() - db.scalars(select(Oturum)).one().son_gorulme > dt.timedelta(minutes=3)
    # 6 dk: `son_gorulme` ve `bitis` ilerler, çerezin Max-Age'i yenilenir.
    _oturumu_yasland(6)
    cevap = istemci.get("/api/hesap/ben")
    assert cevap.status_code == 200
    assert f"max-age={cerez.OTURUM_OMRU_SN}" in cevap.headers["set-cookie"].lower()
    with _db() as db:
        o = db.scalars(select(Oturum)).one()
        assert hesap.simdi() - o.son_gorulme < dt.timedelta(minutes=1)
        assert o.bitis - hesap.simdi() > dt.timedelta(days=29, hours=23)


def test_an_expired_session_is_401_even_though_the_cookie_is_still_there(istemci):
    _hazir_hesap(istemci)
    _giris(istemci)
    with _db() as db:
        o = db.scalars(select(Oturum)).one()
        o.bitis = hesap.simdi() - dt.timedelta(seconds=1)
        db.commit()
    assert istemci.get("/api/hesap/ben").status_code == 401


# ── Hız sınırı ───────────────────────────────────────────────────────

def test_the_eleventh_failed_login_for_an_email_is_429_with_retry_after(istemci):
    _hazir_hesap(istemci)
    for _ in range(hesap.GIRIS_EPOSTA_SINIRI):
        assert _giris(istemci, parola="yanlis").status_code == 401
    kilit = _giris(istemci, parola=PAROLA)     # doğru parola bile: kilit önce
    assert kilit.status_code == 429
    bekle = int(kilit.headers["retry-after"])
    assert 0 < bekle <= int(hesap.GIRIS_PENCERESI.total_seconds()) + 1
    assert str(bekle) in kilit.json()["detail"]
    assert "set-cookie" not in kilit.headers
    # E-posta kilidi IP'den bağımsız: başka adresten de aynı hesap kilitli.
    baska = TestClient(appmod.app, base_url=HTTPS, client=IP_B)   # lifespan'sız (gerekçe yukarıda)
    assert _giris(baska).status_code == 429
    with _db() as db:
        assert db.scalar(select(func.count()).select_from(GirisDenemesi)
                         .where(GirisDenemesi.tur == hesap.DENEME_GIRIS)) == hesap.GIRIS_EPOSTA_SINIRI


def test_thirty_failures_from_one_ip_lock_the_ip_for_every_email(istemci):
    for i in range(hesap.GIRIS_IP_SINIRI):
        assert _giris(istemci, eposta=f"k{i}@example.com", parola="x" * 8).status_code == 401
    assert _giris(istemci, eposta="yepyeni@example.com", parola="x" * 8).status_code == 429


def test_a_successful_login_clears_the_email_counter_but_not_the_ip_counter(istemci):
    _hazir_hesap(istemci)
    for _ in range(hesap.GIRIS_EPOSTA_SINIRI - 1):
        _giris(istemci, parola="yanlis")
    assert _giris(istemci).status_code == 200
    with _db() as db:
        assert db.scalar(select(func.count()).select_from(GirisDenemesi)
                         .where(GirisDenemesi.eposta == EPOSTA,
                                GirisDenemesi.tur == hesap.DENEME_GIRIS)) == 0
    for _ in range(hesap.GIRIS_EPOSTA_SINIRI):
        _giris(istemci, parola="yanlis")
    assert _giris(istemci).status_code == 429, "sayaç sıfırlandıktan sonra yeniden dolar"


def test_registration_is_limited_to_five_per_hour_per_ip(istemci):
    for i in range(hesap.ISTEK_IP_SINIRI):
        assert _kayit(istemci, eposta=f"k{i}@example.com").status_code == 200
    kilit = _kayit(istemci, eposta="k9@example.com")
    assert kilit.status_code == 429 and "retry-after" in kilit.headers
    assert _kullanici("k9@example.com") is None
    baska = TestClient(appmod.app, base_url=HTTPS, client=IP_B)   # lifespan'sız (gerekçe yukarıda)
    assert _kayit(baska, eposta="k9@example.com").status_code == 200


def test_reset_requests_are_limited_per_ip_independently_of_login_failures(istemci):
    _hazir_hesap(istemci)
    for _ in range(hesap.GIRIS_EPOSTA_SINIRI - 1):
        _giris(istemci, parola="yanlis")
    # 9 başarısız giriş "parolamı unuttum"u KİLİTLEMEZ (ayrı sayaç, ayrı tür).
    for _ in range(hesap.ISTEK_IP_SINIRI):
        assert istemci.post("/api/hesap/sifirla", json={"eposta": EPOSTA}).status_code == 200
    assert istemci.post("/api/hesap/sifirla", json={"eposta": EPOSTA}).status_code == 429


# ── Yeniden kayıt ────────────────────────────────────────────────────

def test_registering_an_existing_unverified_email_resends_and_takes_the_new_password(istemci):
    _kayit(istemci, parola="ilk-parola-123")
    ilk = _jeton("dogrula")
    assert _kayit(istemci, parola=PAROLA).json() == {"ok": True}
    assert _jeton("dogrula") != ilk
    with _db() as db:
        assert db.scalar(select(func.count()).select_from(Kullanici)) == 1
    _dogrula(istemci)
    assert _giris(istemci, parola="ilk-parola-123").status_code == 401
    assert _giris(istemci, parola=PAROLA).status_code == 200


def test_registering_an_existing_verified_email_answers_the_same_and_mails_the_owner(istemci):
    _hazir_hesap(istemci)
    k_once = _kullanici()
    assert k_once is not None
    cevap = _kayit(istemci, parola="baskasinin-parolasi")
    assert cevap.status_code == 200 and cevap.json() == {"ok": True}, "var/yok ayırt edilmez"
    ileti = _son_posta()
    assert ileti.konu == i18n.t("posta.mevcut_hesap_konu", "en")
    assert "dogrula=" not in ileti.metin and f"{HTTPS}/giris" in ileti.metin
    k_sonra = _kullanici()
    assert k_sonra is not None and k_sonra.parola_ozeti == k_once.parola_ozeti, "hesaba dokunulmaz"
    assert _giris(istemci, parola="baskasinin-parolasi").status_code == 401


def test_email_lookup_is_case_insensitive(istemci):
    _kayit(istemci, eposta="Ali@Example.com")
    _dogrula(istemci)
    assert _giris(istemci, eposta="ali@example.com").status_code == 200
    assert _kayit(istemci, eposta="ALI@EXAMPLE.COM").status_code == 200
    with _db() as db:
        assert db.scalar(select(func.count()).select_from(Kullanici)) == 1


# ── Parola sıfırlama ─────────────────────────────────────────────────

def test_the_password_reset_flow_changes_the_password_drops_sessions_and_burns_the_token(istemci):
    _hazir_hesap(istemci)
    _giris(istemci)
    assert _oturum_sayisi() == 1
    assert istemci.post("/api/hesap/sifirla", json={"eposta": EPOSTA}).json() == {"ok": True}
    ileti = _son_posta()
    assert ileti.konu == i18n.t("posta.sifirlama_konu", "en")
    jeton = _jeton("sifirla")
    yeni = "yepyeni-parola-42"
    assert istemci.post("/api/hesap/sifirla/dogrula",
                        json={"jeton": jeton, "parola": yeni}).status_code == 200
    assert _oturum_sayisi() == 0, "parola değişti → bütün oturumlar düşer"
    assert istemci.get("/api/hesap/ben").status_code == 401
    assert istemci.post("/api/hesap/sifirla/dogrula",
                        json={"jeton": jeton, "parola": "bir-daha-bir-daha"}).status_code == 400
    assert _giris(istemci, parola=PAROLA).status_code == 401
    assert _giris(istemci, parola=yeni).status_code == 200


def test_a_reset_token_cannot_verify_and_a_verification_token_cannot_reset(istemci):
    _kayit(istemci)
    dogrulama = _jeton("dogrula")
    assert istemci.post("/api/hesap/sifirla/dogrula",
                        json={"jeton": dogrulama, "parola": PAROLA}).status_code == 400
    istemci.post("/api/hesap/sifirla", json={"eposta": EPOSTA})
    sifirlama = _jeton("sifirla")
    assert istemci.post("/api/hesap/dogrula", json={"jeton": sifirlama}).status_code == 400


def test_a_reset_request_for_an_unknown_email_answers_the_same_and_sends_nothing(istemci):
    _hazir_hesap(istemci)
    bilinen_onceki = appmod.app.state.postaci.son
    cevap = istemci.post("/api/hesap/sifirla", json={"eposta": "yok@example.com"})
    assert cevap.status_code == 200 and cevap.json() == {"ok": True}
    assert appmod.app.state.postaci.son is bilinen_onceki, "bilinmeyen adrese ileti yok"
    with _db() as db:
        assert db.scalar(select(func.count()).select_from(Jeton)
                         .where(Jeton.amac == hesap.AMAC_SIFIRLAMA)) == 0


def test_a_reset_also_verifies_an_unverified_account(istemci):
    _kayit(istemci)
    istemci.post("/api/hesap/sifirla", json={"eposta": EPOSTA})
    assert istemci.post("/api/hesap/sifirla/dogrula",
                        json={"jeton": _jeton("sifirla"), "parola": PAROLA}).status_code == 200
    k = _kullanici()
    assert k is not None and k.dogrulandi_at is not None
    assert _giris(istemci).status_code == 200


def test_the_reset_mail_speaks_the_users_stored_language_not_the_requesters(istemci):
    istemci.post("/api/hesap/kayit", json={"eposta": EPOSTA, "parola": PAROLA, "sartlar": True},
                 headers={"X-Kromis-Lang": "tr"})
    assert _son_posta().konu == i18n.t("posta.dogrulama_konu", "tr")
    k = _kullanici()
    assert k is not None and k.dil == "tr"
    istemci.post("/api/hesap/sifirla", json={"eposta": EPOSTA}, headers={"X-Kromis-Lang": "en"})
    assert _son_posta().konu == i18n.t("posta.sifirlama_konu", "tr")


# ── Doğrulama hataları, numaralandırma, sızıntı ─────────────────────

def test_invalid_email_and_short_password_are_422_in_the_interface_language(istemci):
    for lang, kotu in (("tr", "adres-degil"), ("en", "a@b")):
        cevap = istemci.post("/api/hesap/kayit", json={"eposta": kotu, "parola": PAROLA, "sartlar": True},
                             headers={"X-Kromis-Lang": lang})
        assert cevap.status_code == 422
        assert i18n.t("err.hesap_gecersiz_eposta", lang) in cevap.text
    kisa = istemci.post("/api/hesap/kayit", json={"eposta": EPOSTA, "parola": "kisa123", "sartlar": True},
                        headers={"X-Kromis-Lang": "tr"})
    assert kisa.status_code == 422
    assert i18n.t("err.hesap_parola_uzunluk", "tr", en_az=8, en_cok=128) in kisa.text
    assert "kisa123" not in kisa.text, "parola 422 gövdesine sızmamalı (services/redaksiyon.py)"
    assert _kullanici() is None


def test_extra_fields_are_rejected_on_every_account_request(istemci):
    for yol, govde in (("/api/hesap/kayit", {"eposta": EPOSTA, "parola": PAROLA, "sartlar": True}),
                       ("/api/hesap/giris", {"eposta": EPOSTA, "parola": PAROLA}),
                       ("/api/hesap/sifirla", {"eposta": EPOSTA}),
                       ("/api/hesap/dogrula", {"jeton": "x" * 43}),
                       ("/api/hesap/sifirla/dogrula", {"jeton": "x" * 43, "parola": PAROLA})):
        assert istemci.post(yol, json={**govde, "is_admin": True}).status_code == 422, yol


def test_a_mail_failure_is_a_503_and_leaves_no_user_behind(istemci, monkeypatch, tmp_path):
    monkeypatch.setattr(appmod.app.state, "postaci", posta.BozukPostaci("sahte ariza"))
    cevap = _kayit(istemci)
    assert cevap.status_code == 503
    assert cevap.json()["detail"] == i18n.t("err.hesap_posta_gonderilemedi", "en")
    assert _kullanici() is None, "ileti gitmediyse kayıt da geri alınır (rollback)"
    with open(tmp_path / "hata.log", encoding="utf-8") as f:
        assert "sahte ariza" in f.read()


def test_the_login_route_persists_the_failure_it_reports(istemci):
    """401 `JSONResponse`, `HTTPException` DEĞİL — aksi hâlde rollback sayacı siler (routers/hesap.py)."""
    _hazir_hesap(istemci)
    _giris(istemci, parola="yanlis")
    with _db() as db:
        assert db.scalar(select(func.count()).select_from(GirisDenemesi)
                         .where(GirisDenemesi.tur == hesap.DENEME_GIRIS)) == 1


# ── Çerez bayrağı kararı ─────────────────────────────────────────────

def test_the_secure_flag_defaults_on_in_web_mode_and_off_in_the_frozen_shell(monkeypatch):
    monkeypatch.delenv(cerez.GUVENLI_ENV, raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert cerez.guvenli() is False, "dondurulmuş kabuk: loopback http, Secure çerez saklanmaz"
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@y/z")
    assert cerez.guvenli() is True, "web modu: öntanımlı AÇIK (belge §3'ün bekçisi)"
    for kapat in ("0", "false", "hayir", "no", "off", " 0 "):
        monkeypatch.setenv(cerez.GUVENLI_ENV, kapat)
        assert cerez.guvenli() is False, kapat
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv(cerez.GUVENLI_ENV, "1")
    assert cerez.guvenli() is True
    monkeypatch.setenv(cerez.GUVENLI_ENV, "")
    assert cerez.guvenli() is False, "boş = öntanımlı kural"


def test_the_language_cookie_follows_the_same_decision(istemci):
    """İki çerez tek karar: web modunda dil çerezi de `Secure` (services/cerez.py).

    Önce giriş: `/api/prefs` kapının arkasında (Faz 1 / 4), tercih dosyası da
    kullanıcının kendi dizinine (`tmp_path/kullanicilar/<uuid>/output`) iniyor —
    `dizinler(output_dir=…)` artık burada bir şey yönlendirmiyor."""
    _hazir_hesap(istemci)
    assert _giris(istemci).status_code == 200
    cevap = istemci.post("/api/prefs", json={"language": "tr"})
    assert cevap.status_code == 200
    assert "secure" in cevap.headers["set-cookie"].lower()


def test_the_secure_flag_can_be_forced_off_for_plain_http_compose(veritabani, monkeypatch):
    monkeypatch.setenv(cerez.GUVENLI_ENV, "0")
    with TestClient(appmod.app, client=IP_A) as c:      # düz http://testserver
        _temizle()
        _hazir_hesap(c)
        cevap = _giris(c)
        assert cevap.status_code == 200 and "secure" not in cevap.headers["set-cookie"].lower()
        assert c.get("/api/hesap/ben").status_code == 200, "httpx çerezi düz HTTP'de taşıdı"


# ── Katman birimleri ─────────────────────────────────────────────────

def test_password_hashes_are_argon2id_and_verification_has_a_timing_decoy():
    ozet = hesap.parola_ozeti(PAROLA)
    assert ozet.startswith("$argon2id$") and PAROLA not in ozet
    assert hesap.parola_dogru(PAROLA, ozet) and not hesap.parola_dogru("yanlis", ozet)
    assert hesap.parola_dogru(PAROLA, None) is False
    assert hesap._sahte_ozet().startswith("$argon2id$")
    assert hesap.parola_ozeti(PAROLA) != ozet, "tuz her seferinde farklı"
    assert hesap.parola_yenilensin_mi(PAROLA, ozet) is None, "güncel parametre: yenileme yok"
    assert hesap.parola_yenilensin_mi("yanlis", ozet) is None


def test_tokens_are_random_url_safe_and_stored_only_as_sha256():
    a, b = hesap.yeni_jeton(), hesap.yeni_jeton()
    assert a != b and len(a) >= 43 and re.fullmatch(r"[A-Za-z0-9_-]+", a)
    assert len(hesap.ozet(a)) == 32 and hesap.ozet(a) != hesap.ozet(b)


def test_the_client_ip_is_taken_only_when_it_is_a_real_address():
    from starlette.requests import Request

    def _istek(host):
        return Request({"type": "http", "method": "GET", "path": "/", "headers": [],
                        "client": (host, 1) if host else None})
    assert hesap.ip_adresi(_istek("203.0.113.5")) == "203.0.113.5"
    assert hesap.ip_adresi(_istek("::1")) == "::1"
    assert hesap.ip_adresi(_istek("testclient")) is None
    assert hesap.ip_adresi(_istek(None)) is None


def test_the_password_limits_live_in_models_and_are_read_by_the_hash_layer():
    assert models.PAROLA_EN_AZ == 8 and models.PAROLA_EN_COK == 128
    assert models.check_parola("a" * 8) == "a" * 8 and models.check_parola("a" * 128)
    for kotu in ("a" * 7, "a" * 129):
        with pytest.raises(ValueError):
            models.check_parola(kotu)
    assert models.check_eposta("  Ali@Example.com ") == "Ali@Example.com"
    for kotu in ("ali", "ali@", "@x.com", "a b@c.d", "a@b", "a" * 250 + "@b.co"):
        with pytest.raises(ValueError):
            models.check_eposta(kotu)


# ── Sayfa ve rota envanteri ──────────────────────────────────────────

HESAP_ROTALARI = {
    ("POST", "/api/hesap/kayit"), ("POST", "/api/hesap/dogrula"),
    ("POST", "/api/hesap/giris"), ("POST", "/api/hesap/cikis"),
    ("POST", "/api/hesap/sifirla"), ("POST", "/api/hesap/sifirla/dogrula"),
    ("GET", "/api/hesap/ben"), ("GET", "/giris"),
    # Faz 4 / 5: hesap silme ve veri dışa aktarma (8 → 10; tests/test_hesap_silme.py).
    ("POST", "/api/hesap/sil"), ("GET", "/api/hesap/disa-aktar"),
    # Faz 4 / 6: şartlar onayı — var olan kullanıcı yeni sürümü damgalar (10 → 11; tests/test_hukuk.py).
    ("POST", "/api/hesap/sartlar-kabul"),
}


def test_the_account_routes_are_exactly_the_eight_the_document_names():
    """Belge §3: "öneri 8 rota" — liste birebir (Faz 4 / 5 ile 10, Faz 4 / 6 ile 11); 46 → 54 sayısı tests/test_app_bolme.py'de."""
    calisan = {(y, yol) for y, yol in conftest.duz_rotalar(appmod.app)
               if yol.startswith("/api/hesap") or yol == "/giris"}
    assert calisan == HESAP_ROTALARI


@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_the_login_page_is_served_translated_with_the_dictionary_inlined(lang, dizinler):
    from services import ayar
    dizinler(static_dir=ayar.Ayarlar.varsayilan().static_dir)
    cevap = TestClient(appmod.app).get("/giris", headers={"X-Kromis-Lang": lang})
    assert cevap.status_code == 200
    assert cevap.headers["cache-control"] == "no-store"
    html = cevap.text
    assert f'<html lang="{lang}">' in html
    assert "{{t:" not in html and "__APP_" not in html
    assert f'window.KROMIS_LANG="{lang}"' in html and "window.KROMIS_I18N={" in html
    assert i18n.t("giris.kayit_dugme", lang) in html
    import version
    assert set(re.findall(r"\?v=([^\"'\s>]+)", html)) == {version.APP_VERSION}


def test_the_login_page_loads_only_the_dictionary_and_its_own_script():
    html = TestClient(appmod.app).get("/giris").text
    betikler = re.findall(r'<script src="/static/([a-z0-9_.-]+)\?v=', html)
    assert betikler == ["i18n.js", "giris.js"], "stüdyo betikleri bu sayfada yüklenmez"
    stiller = re.findall(r'<link rel="stylesheet" href="/static/([a-z0-9_.-]+)\?v=', html)
    assert stiller == ["fonts.css", "flow-tokens.css", "giris.css"], "style.css yüklenmez (gerekçe giris.html)"


def test_every_id_the_login_script_binds_exists_in_the_login_page():
    """giris.js `KAPSAM_DISI`nda (tests/test_id_contract.py) — id bağlarının bekçisi burası."""
    import os
    kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(kok, "static", "giris.js"), encoding="utf-8") as f:
        js = f.read()
    with open(os.path.join(kok, "static", "giris.html"), encoding="utf-8") as f:
        html = f.read()
    idler = set(re.findall(r'id="([a-zA-Z0-9_-]+)"', html))
    bagli = set(re.findall(r'\bel\("([a-zA-Z0-9_-]+)"\)', js))
    bagli |= set(re.findall(r'querySelector\(["\']#([a-zA-Z0-9_-]+)', js))
    bagli |= {f"form-{s}" for s in re.findall(r'"(giris|kayit|sifirla|yeni-parola)"', js)}
    assert bagli, "tarama boş — desen bayatladı mı?"
    assert bagli <= idler, f"giris.js şu id'lere bağlanıyor ama sayfada yok: {sorted(bagli - idler)}"
    for yol in ("/api/hesap/giris", "/api/hesap/kayit", "/api/hesap/sifirla",
                "/api/hesap/sifirla/dogrula", "/api/hesap/dogrula", "/api/hesap/ben"):
        assert f'"{yol}"' in js, yol
