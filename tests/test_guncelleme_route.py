"""`GET /api/guncelleme` — güncelleme cevabının ARDIL okunması.

NEDEN AYRI BİR UÇ VAR: `guncelleme.bilgi()` bayat önbellekte tazelemeyi arka
planda başlatıp `None` döner (guncelleme.py'nin 2. sözleşmesi: istek yolunu
asla bekletme). Modül bunu "birkaç saniye sonrakinde gerçek cevap gelir" diye
yazmıştı — ama ön yüz `/api/settings`'i YALNIZ açılışta bir kez soruyordu
(settings.js'nin tek `loadSettings(true)` çağrısı), yani "sonraki" istek hiç
gelmiyordu. Tazelenen cevap ancak BİR SONRAKİ uygulama açılışında okunuyordu:
yeni bir sürüm çıktığında bildirim, en iyi ihtimalle bir açılış gecikiyordu ve
kullanıcı için "bildirim hiç gelmiyor"dan ayırt edilemezdi.

Alan `/api/settings`'te DE duruyor ve orada kalmalı (app.py'deki gerekçe: sürüm
satırıyla aynı yanıtta gelmezse panel bir an "güncelsin" deyip fikir
değiştirir). Bu uç onun yerine geçmiyor, ARDINDAN geliyor: sürüm o an zaten
çizilmiş oluyor.
"""
from __future__ import annotations

import json
import os
import time

import pytest
from fastapi.testclient import TestClient

import app as appmod
import guncelleme
import version

# `guncelleme_kontrolu` tercihi `tercihler` satırından (Faz 1 / 6); önbellek
# dosyası (`guncelleme.json`) hâlâ diskte — gerekçe tests/conftest.py::depo_db.
pytestmark = pytest.mark.usefixtures("depo_db")


@pytest.fixture(autouse=True)
def _bayragi_sifirla():
    """Modül düzeyindeki "tazeleme koşuyor" bayrağı testler arasında sızmasın."""
    yield
    guncelleme._KOSUYOR = False


@pytest.fixture
def out_dir(tmp_path, dizinler):
    path = str(tmp_path / "output")
    os.makedirs(path, exist_ok=True)
    dizinler(output_dir=path)
    return path


@pytest.fixture
def client(out_dir):
    return TestClient(appmod.app)


def _onbellek_yaz(dizin: str, veri: dict) -> None:
    with open(os.path.join(dizin, guncelleme.ONBELLEK_DOSYASI), "w", encoding="utf-8") as f:
        json.dump(veri, f)


def test_a_newer_version_in_the_cache_reaches_the_browser(client, out_dir):
    """ASIL İDDİA: arka plan kontrolü önbelleği tazeledikten SONRA gelen istek
    cevabı görüyor. Bu uç olmadan cevap diskte kalıyor ve sayfa onu hiç
    sormuyordu."""
    _onbellek_yaz(out_dir, {"zaman": time.time(), "surum": "99.0.0",
                            "url": f"{guncelleme.GECERLI_URL_ONEKI}releases/tag/v99.0.0"})

    r = client.get("/api/guncelleme")

    assert r.status_code == 200
    assert r.json() == {"guncelleme": {
        "surum": "99.0.0",
        "url": f"{guncelleme.GECERLI_URL_ONEKI}releases/tag/v99.0.0"}}


def test_the_current_version_is_not_reported_as_an_update(client, out_dir):
    """Yeni sürüm YOKSA cevap `null` — arayüz satırı gizli tutuyor."""
    _onbellek_yaz(out_dir, {"zaman": time.time(), "surum": version.APP_VERSION})

    assert client.get("/api/guncelleme").json() == {"guncelleme": None}


def test_the_preference_switches_the_endpoint_off(client, out_dir):
    """3. sözleşme: tercih kapalıyken uç, önbellekte yeni bir sürüm DURSA BİLE
    `null` döner. Kapatmış kullanıcıya bildirim, kapatmanın anlamını siler."""
    _onbellek_yaz(out_dir, {"zaman": time.time(), "surum": "99.0.0"})
    client.post("/api/prefs", json={"guncelleme_kontrolu": False})

    assert client.get("/api/guncelleme").json() == {"guncelleme": None}


def test_the_endpoint_does_not_wait_for_the_network(client, out_dir, monkeypatch):
    """2. sözleşme bu uçta da geçerli: önbellek bayatsa ağ çağrısı ARKA PLANA
    gider, istek beklemez. Ön yüz bunu saniyeler içinde birkaç kez yokluyor —
    her yoklamanın 5 saniye asılması paneli değil tarayıcıyı kilitlerdi."""
    def _yavas_sor():
        time.sleep(5)
        return {"surum": "99.0.0", "url": guncelleme.YAYIN_SAYFASI}

    monkeypatch.setattr(guncelleme, "_sor", _yavas_sor)
    _onbellek_yaz(out_dir, {"zaman": 0})           # bayat: tazeleme tetiklenir

    basladi = time.monotonic()
    r = client.get("/api/guncelleme")

    assert time.monotonic() - basladi < 1.0
    assert r.json() == {"guncelleme": None}        # henüz cevap yok


# --------------------------------------------------------------------------
# `POST /api/guncelleme` — "Şimdi kontrol et"
# --------------------------------------------------------------------------

def test_the_manual_check_reaches_github_even_with_a_fresh_cache(
        client, out_dir, monkeypatch):
    """ASIL İDDİA. `GET` yalnız önbelleğe bakıyor ve önbellek 24 saat taze
    sayılıyor; yayın hızı bunun üstündeyse (ölçüldü: ~7.7 saatte bir) cevap
    bayat kalır ve kullanıcının tetikleyecek hiçbir yolu yoktur."""
    _onbellek_yaz(out_dir, {"zaman": time.time(), "son_deneme": time.time(),
                            "surum": version.APP_VERSION})
    monkeypatch.setattr(guncelleme, "_sor",
                        lambda: {"surum": "99.0.0", "url": guncelleme.YAYIN_SAYFASI})

    assert client.get("/api/guncelleme").json() == {"guncelleme": None}

    r = client.post("/api/guncelleme")

    assert r.status_code == 200
    assert r.json() == {"durum": "yeni",
                        "guncelleme": {"surum": "99.0.0",
                                       "url": guncelleme.YAYIN_SAYFASI}}


def test_the_manual_check_separates_up_to_date_from_unreachable(
        client, out_dir, monkeypatch):
    """İki durumda da `guncelleme` alanı `null`; farkı YALNIZ `durum` taşıyor.
    Arayüz bunları iki ayrı cümleye çeviriyor — "güncelsin" bir cevap,
    "soramadım" ise bir kusur bildirimi."""
    monkeypatch.setattr(guncelleme, "_sor",
                        lambda: {"surum": version.APP_VERSION,
                                 "url": guncelleme.YAYIN_SAYFASI})
    assert client.post("/api/guncelleme").json() == {"durum": "guncel",
                                                     "guncelleme": None}

    monkeypatch.setattr(guncelleme, "_sor", lambda: None)
    assert client.post("/api/guncelleme").json() == {"durum": "hata",
                                                     "guncelleme": None}


def test_the_preference_switches_the_manual_check_off_too(client, out_dir, monkeypatch):
    """3. sözleşme elle yolda da geçerli. Bir düğmenin varlığı, kullanıcının
    kapattığı şeyi açmanın gerekçesi değil."""
    def _patlar():
        raise AssertionError("kontrol kapalıyken ağa çıkıldı")

    monkeypatch.setattr(guncelleme, "_sor", _patlar)
    client.post("/api/prefs", json={"guncelleme_kontrolu": False})

    assert client.post("/api/guncelleme").json() == {"durum": "kapali",
                                                     "guncelleme": None}


def test_the_read_path_stays_side_effect_free(client, out_dir, monkeypatch):
    """GET yan etkisiz KALMALI: ön yüzün açılış yoklaması (`yoklaGuncelleme`)
    onu saniyeler içinde üç kez çağırıyor ve her biri senkron bir ağ çağrısı
    tetikleseydi 2. sözleşme çöker, üstelik anonim istek sınırı da yanardı.
    Yan etkili olan YALNIZ POST — aynı adres, ayrı yöntem."""
    cagrildi = []
    monkeypatch.setattr(guncelleme, "_kontrol_et",
                        lambda d: cagrildi.append(d) or True)
    _onbellek_yaz(out_dir, {"zaman": time.time(), "son_deneme": time.time(),
                            "surum": version.APP_VERSION})

    client.get("/api/guncelleme")

    assert cagrildi == []

