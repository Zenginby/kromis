"""Dil çözüm zinciri: başlık → çerez → HESABIN dili → Accept-Language → varsayılan.

Faz 0 / Adım 3 zinciri isteğin kendisinden çözdü (docs/faz0-web-first.md);
Faz 1 / 4 üçüncü halkayı diskteki `prefs.json`dan `kullanicilar.dil`e taşıdı
(docs/faz1-veritabani-hesaplar.md → 4). Bu dosya üç şeyi sabitliyor: zincirin
SIRASI, web yolunun tercih dosyasını HİÇ okumadığı ve isteğin dilinin isteğin
kendisiyle taşınabildiği (iki istemci, iki çerez).

Hesabın dili conftest'in autouse `kullanici` fixture'ından geliyor
(`kullanici.dil = "tr"`): override üretim yolundaki `kimlik.bagla`yı çağırıyor,
yani 3. halka burada da GERÇEK koddan geçiyor — yalnız kullanıcı DB'den değil
fixture'dan. DB'den okunan hâli (`gercek_kimlik`) tests/test_kimlik.py sınıyor.
`services/tercih.py`nin kendi birim testleri en altta duruyor: modül web
yolundan çıktı ama dondurulmuş kabuk için yaşıyor (6. görevde kararı).
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


def test_accept_language_is_honoured_only_when_the_account_has_no_language(client, kullanici):
    assert kullanici.dil is None, "öncül: hesap hiç dil seçmedi"
    assert _sayfa_dili(client.get("/", headers=TR_TARAYICI)) == "tr"
    assert _sayfa_dili(client.get("/", headers=EN_TARAYICI)) == "en"
    # Hesabın dili gelince başlık susuyor — kullanıcının seçimi tarayıcının varsayımını ezer.
    kullanici.dil = "en"
    assert _sayfa_dili(client.get("/", headers=TR_TARAYICI)) == "en"


def test_an_account_language_equal_to_the_default_still_beats_the_browser(client, kullanici):
    """`kullanicilar.dil` NULL ile `'en'`i ayırt ediyor (tablolar.py'nin gerekçesi):
    İngilizce'yi SEÇMİŞ bir kullanıcı Türkçe tarayıcıda Türkçe görmez."""
    kullanici.dil = i18n.DEFAULT
    assert _sayfa_dili(client.get("/", headers=TR_TARAYICI)) == i18n.DEFAULT


def test_the_cookie_beats_the_account_language_and_the_browser(client, kullanici):
    kullanici.dil = "en"
    assert _sayfa_dili(_cerezli("tr").get("/", headers=EN_TARAYICI)) == "tr"


def test_the_header_beats_the_cookie(client, kullanici):
    kullanici.dil = "tr"
    assert _sayfa_dili(_cerezli("tr").get("/", headers={dil.BASLIK: "en"})) == "en"


@pytest.mark.parametrize("bozuk", ["de", "", "TR", "../../etc/passwd", "tr; DROP"])
def test_an_invalid_cookie_or_header_is_ignored_and_the_chain_continues(client, kullanici, bozuk):
    """Geçersiz halka zinciri düşürmez: 400 yok, `FALLBACK`a düşme yok, sıra
    bir sonrakine geçer (hesabın dili)."""
    kullanici.dil = "tr"
    istemci = _cerezli(bozuk) if bozuk else client
    cevap = istemci.get("/", headers={dil.BASLIK: bozuk})
    assert cevap.status_code == 200
    assert _sayfa_dili(cevap) == "tr"


def test_an_invalid_account_language_falls_through_to_the_browser(client, kullanici):
    """DB'de `CHECK` var ama zincir ona güvenmiyor: bilinmeyen değer halkayı düşürür, isteği değil."""
    kullanici.dil = "de"
    assert _sayfa_dili(client.get("/", headers=TR_TARAYICI)) == "tr"


@pytest.mark.usefixtures("depo_db")   # `DELETE /api/image` artık `Session` istiyor (Faz 1 / 5)
def test_the_chain_reaches_route_errors_through_dil_aktif(client, kullanici):
    """Rotalar `dil.aktif()` okumaya devam ediyor (API sabit) ve o değer
    zincirden geliyor: çerezli istekte hata metni çerezin dilinde, çerezsizde
    hesabın dilinde — kapı 3. halkayı gövde koşmadan ÖNCE uyguladı."""
    kullanici.dil = "tr"
    assert client.delete("/api/image/yokboyle").json()["detail"] == "Görsel bulunamadı."
    cevap = _cerezli("en").delete("/api/image/yokboyle")
    assert cevap.json()["detail"] == "The image was not found."


# ── `coz`: zincirin tek yazılı hâli ──────────────────────────────────

@pytest.mark.parametrize("baslik, cerez, hesap, kabul, beklenen", [
    ("en", "tr", "tr", "tr", "en"),      # 1. başlık
    (None, "tr", "en", "en", "tr"),      # 2. çerez
    (None, None, "tr", "en", "tr"),      # 3. hesabın dili
    (None, None, None, "tr", "tr"),      # 4. Accept-Language
    (None, None, None, None, i18n.DEFAULT),
    ("de", "xx", "de", "tr", "tr"),      # geçersiz halkalar düşer, zincir sürer
])
def test_coz_applies_the_five_links_in_order(baslik, cerez, hesap, kabul, beklenen):
    """Ara katman (1-2, 4-5) ve kapı (3) zinciri ikiye bölerek uyguluyor; sıranın
    tek yazılı hâli `coz` ve ikisinin toplamı buna eşit olmalı."""
    from starlette.requests import Request
    basliklar = []
    if baslik is not None:
        basliklar.append((dil.BASLIK.lower().encode(), baslik.encode()))
    if cerez is not None:
        basliklar.append((b"cookie", f"{dil.CEREZ}={cerez}".encode()))
    if kabul is not None:
        basliklar.append((b"accept-language", kabul.encode()))
    istek = Request({"type": "http", "headers": basliklar, "state": {}})
    assert dil.coz(istek, hesap) == beklenen
    # Bölünmüş uygulama aynı sonucu veriyor: ara katmanın kararı + kapının halkası.
    acik = dil.acik_secim(istek)
    istek.state.dil_acik = acik is not None
    i18n.set_active(acik or dil.tarayici_dili(istek))
    dil.kullanici_dili(istek, hesap)
    assert i18n.active() == beklenen


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

def test_saving_the_language_sets_the_cookie_and_the_next_request_carries_it(client, out_dir, kullanici):
    """Ön yüz değişmedi: `settings.js` yazımdan sonra `location.reload()`
    yapıyor; yeni sayfa çerezle geldiği için dil tarayıcıdan geliyor."""
    cevap = client.post("/api/prefs", json={"language": "tr"})
    assert cevap.status_code == 200
    assert client.cookies.get(dil.CEREZ) == "tr"
    assert _sayfa_dili(client.get("/", headers=EN_TARAYICI)) == "tr"
    # …ve HESAP da yazıldı (Faz 1 / 4): çerezsiz bir istemci (aynı hesabın
    # başka cihazı) 3. halkadan görür. Tercih dosyası da yazılıyor — `GET
    # /api/prefs` onu gösteriyor; DB'ye taşınması 6. görev.
    assert kullanici.dil == "tr"
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


def test_a_rejected_write_sets_no_cookie_and_leaves_the_account_alone(client, kullanici):
    cevap = client.post("/api/prefs", json={"language": "de"})
    assert cevap.status_code == 422
    assert "set-cookie" not in cevap.headers
    assert kullanici.dil is None


# ── Tercih dosyası web yolunda OKUNMUYOR (çıkış ölçütü §4) ────────────

def test_the_web_chain_never_reads_the_preference_file(client, out_dir, kullanici, monkeypatch):
    """`prefs.json`da `tr` dursa da sayfa tarayıcının dilinde: dosya hiç açılmıyor.

    Faz 0 / 3'ün "20 istekte ≤1 okuma" ölçüsü burada "0 okuma"ya indi: 3.
    halka DB'den (fixture'dan) geliyor, `services/tercih.py` ve `prefs.read_stored`
    istek yolunda çağrılmıyor — çağrılırsa yama patlatır."""
    prefs.update({"language": "tr"}, out_dir)
    assert kullanici.dil is None

    def patlat(*a, **k):
        raise AssertionError("dil zinciri tercih dosyasını okudu")

    monkeypatch.setattr(prefs, "read_stored", patlat)
    monkeypatch.setattr(tercih, "dil", patlat)
    for _ in range(5):
        assert _sayfa_dili(client.get("/", headers=EN_TARAYICI)) == "en"
    assert _sayfa_dili(client.get("/")) == i18n.DEFAULT


def test_a_write_through_the_route_is_visible_to_a_cookieless_client_at_once(client):
    """Bayat dil YOK: rota yazar yazmaz ÇEREZSİZ bir istemci (aynı hesabın başka
    tarayıcısı) yeni dili görür — taşıyıcı hesap satırı, çerez tek yol değil."""
    oteki = TestClient(appmod.app)
    assert _sayfa_dili(oteki.get("/")) == i18n.DEFAULT      # hesap henüz dil seçmedi
    client.post("/api/prefs", json={"language": "tr"})
    assert _sayfa_dili(oteki.get("/")) == "tr"
    client.post("/api/prefs", json={"language": "en"})
    assert _sayfa_dili(oteki.get("/")) == "en"


# ── services/tercih.py — dondurulmuş kabuk için duran birim ──────────

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
    iki istek farklı dille doğru cevap alıyor — dil isteğin kendisiyle taşınıyor."""
    tr, en = _cerezli("tr"), _cerezli("en")

    def calis(istemci):
        return [_sayfa_dili(istemci.get("/")) for _ in range(5)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as havuz:
        sonuc_tr, sonuc_en = havuz.map(calis, [tr, en])
    assert sonuc_tr == ["tr"] * 5 and sonuc_en == ["en"] * 5
