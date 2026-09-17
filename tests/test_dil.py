"""Dil çözüm zinciri (Faz 0 / Adım 3): çerez → kayıtlı tercih → Accept-Language → varsayılan.

Ölçülen kusur: ara katman her istekte `prefs.read` ile diski okuyordu ve dil
tek kullanıcının `prefs.json`undan geliyordu (docs/faz0-web-first.md, 3. görev).
Bu dosya üç şeyi sabitliyor: zincirin SIRASI, önbelleğin BAYATLAMAMASI ve
isteğin dilinin isteğin kendisiyle taşınabildiği (iki istemci, iki çerez).
"""
import concurrent.futures
import re

import pytest
from fastapi.testclient import TestClient

import app as appmod
import i18n
import prefs
from services import dil, tercih

TR_TARAYICI = {"Accept-Language": "tr-TR,tr;q=0.9,en;q=0.5"}
EN_TARAYICI = {"Accept-Language": "en-US,en;q=0.9"}


@pytest.fixture
def out_dir(tmp_path, dizinler):
    path = str(tmp_path / "output")
    dizinler(output_dir=path)
    return path


@pytest.fixture
def client(out_dir):
    return TestClient(appmod.app)


def _sayfa_dili(cevap) -> str:
    """`/`nin çizildiği dil — şablonun `lang` özniteliğinden."""
    eslesme = re.search(r'<html lang="(\w+)">', cevap.text)
    assert eslesme is not None, cevap.text[:200]
    return eslesme.group(1)


def _cerezli(deger: str) -> TestClient:
    """`kromis_lang=<deger>` taşıyan bir tarayıcı. Çerez İSTEMCİDE kuruluyor,
    istekte değil: httpx istek başına çerezi kaldırıyor (kalıcılığı belirsiz
    diye) ve zaten ölçülen şey "bu tarayıcı şu çerezi taşıyor" hâli."""
    return TestClient(appmod.app, cookies={dil.CEREZ: deger})


# ── Zincirin sırası ─────────────────────────────────────────────────

def test_with_no_signal_at_all_the_page_is_served_in_the_default_language(client):
    """Çerez yok, kayıt yok, `Accept-Language` yok → `i18n.DEFAULT` (v0.22: en).

    `TestClient` bu başlığı kendiliğinden göndermiyor, yani bu test gerçekten
    "hiçbir işaret yok" hâlini ölçüyor."""
    assert _sayfa_dili(client.get("/")) == i18n.DEFAULT == "en"


def test_accept_language_is_honoured_only_when_nothing_is_stored(client, out_dir):
    assert _sayfa_dili(client.get("/", headers=TR_TARAYICI)) == "tr"
    assert _sayfa_dili(client.get("/", headers=EN_TARAYICI)) == "en"
    # Kayıt gelince başlık susuyor — kullanıcının seçimi tarayıcının varsayımını ezer.
    prefs.update({"language": "en"}, out_dir)
    assert _sayfa_dili(client.get("/", headers=TR_TARAYICI)) == "en"


def test_a_stored_preference_equal_to_the_default_still_beats_the_browser(client, out_dir):
    """`read()` "hiç yazılmamış" ile "en yazılmış"ı ayırt edemezdi; zincir
    `read_stored` üstünden geçtiği için ayırt ediyor: İngilizce'yi SEÇMİŞ bir
    kullanıcı Türkçe tarayıcıda Türkçe görmez."""
    prefs.update({"language": i18n.DEFAULT}, out_dir)
    assert _sayfa_dili(client.get("/", headers=TR_TARAYICI)) == i18n.DEFAULT


def test_the_cookie_beats_the_stored_preference_and_the_browser(client, out_dir):
    prefs.update({"language": "en"}, out_dir)
    assert _sayfa_dili(_cerezli("tr").get("/", headers=EN_TARAYICI)) == "tr"


def test_the_header_beats_the_cookie(client, out_dir):
    prefs.update({"language": "tr"}, out_dir)
    assert _sayfa_dili(_cerezli("tr").get("/", headers={dil.BASLIK: "en"})) == "en"


@pytest.mark.parametrize("bozuk", ["de", "", "TR", "../../etc/passwd", "tr; DROP"])
def test_an_invalid_cookie_or_header_is_ignored_and_the_chain_continues(client, out_dir, bozuk):
    """Geçersiz halka zinciri düşürmez: 400 yok, `FALLBACK`a düşme yok, sıra
    bir sonrakine geçer (kayıtlı tercih)."""
    prefs.update({"language": "tr"}, out_dir)
    istemci = _cerezli(bozuk) if bozuk else client
    cevap = istemci.get("/", headers={dil.BASLIK: bozuk})
    assert cevap.status_code == 200
    assert _sayfa_dili(cevap) == "tr"


def test_the_chain_reaches_route_errors_through_dil_aktif(client, out_dir):
    """Rotalar `dil.aktif()` okumaya devam ediyor (API sabit) ve o değer
    zincirden geliyor: çerezli istekte hata metni çerezin dilinde."""
    prefs.update({"language": "tr"}, out_dir)
    assert client.delete("/api/image/yokboyle").json()["detail"] == "Görsel bulunamadı."
    cevap = _cerezli("en").delete("/api/image/yokboyle")
    assert cevap.json()["detail"] == "The image was not found."


# ── Accept-Language ayrıştırıcısı ────────────────────────────────────

@pytest.mark.parametrize("baslik, beklenen", [
    ("tr-TR,tr;q=0.9", "tr"),
    ("en-US,en;q=0.9", "en"),
    ("en;q=0.8,tr;q=0.9", "tr"),          # ağırlık sırayı ezer
    ("en,tr", "en"),                       # eşit ağırlıkta başlıktaki sıra
    ("de-DE,de;q=0.9,tr;q=0.1", "tr"),     # tanınmayanlar atlanır, desteklenen kalır
    ("TR", "tr"),                          # büyük harf normalize
    ("de,fr", None),                       # hiçbiri desteklenmiyor
    ("*", None),                           # joker cevabı DEFAULT'a bırakır
    ("tr;q=0", None),                      # q=0 "istemiyorum"
    ("tr;q=abc,en", "en"),                 # bozuk q parçayı düşürür, başlığı değil
    ("", None),
    (None, None),
    (",,;;", None),
])
def test_the_accept_language_parser(baslik, beklenen):
    assert dil.accept_language(baslik) == beklenen


# ── Çerez ─────────────────────────────────────────────────────────────

def test_saving_the_language_sets_the_cookie_and_the_next_request_carries_it(client, out_dir):
    """Ön yüz değişmedi: `settings.js` yazımdan sonra `location.reload()`
    yapıyor; yeni sayfa çerezle geldiği için dil tarayıcıdan geliyor."""
    cevap = client.post("/api/prefs", json={"language": "tr"})
    assert cevap.status_code == 200
    assert client.cookies.get(dil.CEREZ) == "tr"
    assert _sayfa_dili(client.get("/", headers=EN_TARAYICI)) == "tr"
    # …ve disk de yazıldı (geriye dönük yol): çerezsiz bir istemci de görür.
    assert prefs.read(out_dir)["language"] == "tr"
    assert _sayfa_dili(TestClient(appmod.app).get("/", headers=EN_TARAYICI)) == "tr"


def test_the_cookie_attributes_are_long_lived_http_only_and_site_wide(client):
    cevap = client.post("/api/prefs", json={"language": "en"})
    baslik = cevap.headers["set-cookie"].lower()
    assert baslik.startswith(f"{dil.CEREZ}=en;")
    assert "httponly" in baslik and "samesite=lax" in baslik and "path=/" in baslik
    assert f"max-age={dil.CEREZ_OMRU}" in baslik
    # `Secure` bu testte yok ve bu doğru: `DATABASE_URL` verilmemiş (dondurulmuş
    # kabuk, loopback http) — karar services/cerez.py'de, web modundaki açık hâli
    # tests/test_hesap.py sınıyor.
    assert "secure" not in baslik


def test_saving_another_preference_does_not_touch_the_cookie(client):
    cevap = client.post("/api/prefs", json={"theme": "mono"})
    assert cevap.status_code == 200
    assert "set-cookie" not in cevap.headers


def test_a_rejected_write_sets_no_cookie(client):
    cevap = client.post("/api/prefs", json={"language": "de"})
    assert cevap.status_code == 422
    assert "set-cookie" not in cevap.headers


# ── Önbellek ──────────────────────────────────────────────────────────

def test_the_preference_file_is_not_read_on_every_request(client, out_dir, monkeypatch):
    """ASIL ÖLÇÜ: N istekte en fazla BİR disk okuması (ısınma dâhil)."""
    prefs.update({"language": "tr"}, out_dir)
    sayac = {"read_stored": 0, "read": 0}
    gercek = prefs.read_stored

    def sayan(*a, **k):
        sayac["read_stored"] += 1
        return gercek(*a, **k)

    monkeypatch.setattr(prefs, "read_stored", sayan)
    monkeypatch.setattr(prefs, "read", lambda *a, **k: sayac.__setitem__("read", sayac["read"] + 1))
    for _ in range(20):
        assert _sayfa_dili(client.get("/")) == "tr"
    assert sayac["read_stored"] <= 1, sayac
    assert sayac["read"] == 0, "ara katman birleşik görünümü hiç okumamalı"


def test_a_missing_file_is_cached_too(client, out_dir, monkeypatch):
    """Hiç tercih yazmamış bir kurulumda her istek `open` denemesin."""
    sayac = 0
    gercek = prefs.read_stored

    def sayan(*a, **k):
        nonlocal sayac
        sayac += 1
        return gercek(*a, **k)

    monkeypatch.setattr(prefs, "read_stored", sayan)
    for _ in range(10):
        client.get("/")
    assert sayac <= 1


def test_a_write_through_the_route_is_visible_to_a_cookieless_client_at_once(client, out_dir):
    """Bayat dil YOK: rota yazar yazmaz ÇEREZSİZ bir istemci (başka tarayıcı)
    yeni dili görür — yani önbellek düşürüldü, çerez tek taşıyıcı değil."""
    oteki = TestClient(appmod.app)
    assert _sayfa_dili(oteki.get("/")) == i18n.DEFAULT      # önbellek ısındı: kayıt yok
    client.post("/api/prefs", json={"language": "tr"})
    assert _sayfa_dili(oteki.get("/")) == "tr"
    client.post("/api/prefs", json={"language": "en"})
    assert _sayfa_dili(oteki.get("/")) == "en"


def test_a_write_behind_the_caches_back_is_picked_up_by_the_file_signature(client, out_dir):
    """`sifirla()` ÇAĞRILMADAN diske yazılırsa (başka bir süreç, elle düzenleme)
    önbellek dosya imzasından anlamalı — `write_atomic` yeni inode getiriyor."""
    prefs.update({"language": "tr"}, out_dir)
    assert _sayfa_dili(client.get("/")) == "tr"
    prefs.update({"language": "en"}, out_dir)      # rotayı ATLIYOR, sifirla yok
    assert _sayfa_dili(client.get("/")) == "en"
    prefs.update({"language": "tr"}, out_dir)
    assert _sayfa_dili(client.get("/")) == "tr"


def test_the_cache_is_keyed_by_directory(tmp_path):
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    prefs.update({"language": "tr"}, a)
    prefs.update({"language": "en"}, b)
    assert tercih.dil(a) == "tr" and tercih.dil(b) == "en"
    assert tercih.dil(str(tmp_path / "yok")) is None


def test_read_stored_returns_only_what_is_actually_and_validly_written(tmp_path):
    out = str(tmp_path)
    assert prefs.read_stored(out) == {}
    prefs.update({"language": "tr", "theme": "mono"}, out)
    assert prefs.read_stored(out) == {"language": "tr", "theme": "mono"}
    # Çöp değer "yazılmamış" sayılır — read() ile aynı kapı, iki kopya yok.
    (tmp_path / prefs.PREFS_FILE).write_text(
        '{"language": "de", "theme": 3, "autosave_sessions": false}', encoding="utf-8")
    assert prefs.read_stored(out) == {"autosave_sessions": False}
    assert prefs.read(out)["language"] == i18n.DEFAULT


# ── Çıkış ölçütü: aynı süreçte iki istemci, iki dil ──────────────────

def test_two_clients_with_different_cookies_get_different_languages_concurrently(out_dir):
    """docs/faz0-web-first.md, 3. görevin çıkış ölçütü: aynı süreçte eş zamanlı
    iki istek farklı dille doğru cevap alıyor — `prefs.json` hiç okunmadan
    (dizinde dosya yok)."""
    tr, en = _cerezli("tr"), _cerezli("en")

    def calis(istemci):
        return [_sayfa_dili(istemci.get("/")) for _ in range(5)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as havuz:
        sonuc_tr, sonuc_en = havuz.map(calis, [tr, en])
    assert sonuc_tr == ["tr"] * 5 and sonuc_en == ["en"] * 5
