"""`/api/prefs` — kullanıcı tercihleri ucu (v2.0).

Anahtar BİLEREK `/api/settings`'te değil: o uç kimlik formu ve `api_key` +
`base_url` istiyor. Otomatik kayıt anahtarını oraya koymak, bir anahtarı
çevirmenin Azure kimliğini yeniden yazması demekti — hem gereksiz bir yazım hem
de Azure hiç yapılandırılmamışken anahtarın çevrilemez olması.
"""
import pytest
from fastapi.testclient import TestClient

import app as appmod
import prefs


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    path = str(tmp_path / "output")
    monkeypatch.setattr(appmod, "OUTPUT_DIR", path)
    return path


@pytest.fixture
def client(out_dir):
    return TestClient(appmod.app)


def test_get_reports_the_defaults(client):
    """Beklenti `prefs.DEFAULTS`'tan TÜRETİLİYOR, elle sayılmıyor.

    Sabit yazılmış bir sözlük, yeni bir tercih eklendiğinde bu testi de elle
    güncellenmesi gereken bir yer yapıyordu — yani koruduğu "tek kaynak"
    kuralının kendisini ihlal ediyordu. Kalan iddia asıl olan: uç, şemadaki
    varsayılanların TAMAMINI döndürmeli (bir tercihin uçtan hiç görünmemesi,
    arayüzde sessizce kaybolması demek).
    """
    assert client.get("/api/prefs").json() == prefs.DEFAULTS


def test_post_turns_autosave_off_and_get_reflects_it(client, out_dir):
    r = client.post("/api/prefs", json={"autosave_sessions": False})

    assert r.status_code == 200
    assert r.json() == {**prefs.DEFAULTS, "autosave_sessions": False}
    assert client.get("/api/prefs").json()["autosave_sessions"] is False
    assert prefs.read(out_dir)["autosave_sessions"] is False


def test_a_field_that_is_not_sent_is_not_touched(client):
    """`None` = "alan hiç gelmedi → DOKUNMA" (SettingsRequest geleneği).

    Bayat bir `settings.js` (cache-buster'ı atlatmış bir kopya) tema kaydederken
    otomatik kaydı sessizce açmasın.
    """
    client.post("/api/prefs", json={"autosave_sessions": False})

    r = client.post("/api/prefs", json={})

    assert r.json()["autosave_sessions"] is False


def test_an_unknown_field_is_rejected(client):
    """`extra="forbid"`: bayat sunucu süreci yeni bir tercihi sessizce yutmasın."""
    r = client.post("/api/prefs", json={"autosave_sessions": True, "tema": "amber"})

    assert r.status_code == 422


def test_a_non_boolean_value_is_rejected(client):
    assert client.post("/api/prefs",
                       json={"autosave_sessions": "hayır"}).status_code == 422


def test_the_settings_route_does_not_carry_the_switch(client):
    """Tek kaynak kuralı: aynı değer iki uçtan da okunsa ayrışabilirdi."""
    assert "autosave" not in client.get("/api/settings").text


def test_guncelleme_kontrolu_anahtari_KAYDEDILEBILIYOR(client):
    """Bu alan `PrefsRequest`'te EKSİKTİ ve `extra="forbid"` yüzünden uç 422
    dönüyordu.

    Kırılma sessiz değil GÜRÜLTÜLÜ ama yine de teşhis edilmemişti:
    `static/chat.js`'in "yeni sürüm çıkınca haber ver" anahtarı
    `{guncelleme_kontrolu: …}` POST ediyor, 422 alıyor, onay kutusunu geri alıp
    "Tercih kaydedilemedi" yazıyordu — yani anahtar HİÇ KAPATILAMIYORDU.
    `prefs._SCHEMA` alanı zaten tanıyordu; eksik olan yalnız istek modeliydi.
    """
    r = client.post("/api/prefs", json={"guncelleme_kontrolu": False})

    assert r.status_code == 200, r.text
    assert r.json()["guncelleme_kontrolu"] is False
    assert client.get("/api/prefs").json()["guncelleme_kontrolu"] is False

    # Geri açılabiliyor da olmalı: tek yönlü bir anahtar da kırık sayılır.
    assert client.post("/api/prefs", json={"guncelleme_kontrolu": True}
                       ).json()["guncelleme_kontrolu"] is True


def test_istek_modeli_ile_prefs_semasi_AYRISMIYOR(client):
    """`prefs._SCHEMA`'daki her tercih `/api/prefs`'ten yazılabilir olmalı.

    Rotanın notu "buraya düşmek pydantic ile prefs şemasının ayrışması demek
    olur" diyor — `guncelleme_kontrolu` tam olarak o ayrışmaydı ve bir yıl
    boyunca kimse fark etmedi. Bu iddia mekanik: yeni bir tercih eklerken
    istek modelini unutmak artık testte düşüyor.
    """
    import models
    import prefs as prefs_mod

    eksik = set(prefs_mod._SCHEMA) - set(models.PrefsRequest.model_fields)
    assert not eksik, f"prefs şemasında olup PrefsRequest'te olmayan: {sorted(eksik)}"


def test_secili_model_tercihi_gidip_geliyor(client):
    import catalog

    r = client.post("/api/prefs", json={"image_model": catalog.DEFAULT_IMAGE_MODEL})

    assert r.status_code == 200, r.text
    assert r.json()["image_model"] == catalog.DEFAULT_IMAGE_MODEL


def test_bilinmeyen_model_tercihi_422(client):
    r = client.post("/api/prefs", json={"image_model": "yok-boyle-model"})
    assert r.status_code == 422


def test_dil_tercihi_gidip_geliyor(client, out_dir):
    """Ayarlar'daki dil seçicisinin uç tarafı.

    `/api/settings` DEĞİL burası ve gerekçe bu dosyanın başlığında yazılı:
    o uç `api_key` + `base_url` istiyor, yani dili çevirmek Azure hiç
    yapılandırılmamış bir makinede imkânsız olurdu.
    """
    r = client.post("/api/prefs", json={"language": "en"})

    assert r.status_code == 200, r.text
    assert r.json()["language"] == "en"
    assert client.get("/api/prefs").json()["language"] == "en"
    assert prefs.read(out_dir)["language"] == "en"


def test_bilinmeyen_dil_422(client):
    """Sessiz kabul, arayüzü karşılığı olmayan bir sözlüğe düşürür ve ekran
    baştan sona ham anahtar gösterir."""
    assert client.post("/api/prefs", json={"language": "de"}).status_code == 422
