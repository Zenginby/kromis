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
    assert client.get("/api/prefs").json() == {"autosave_sessions": True, "theme": "mono"}


def test_post_turns_autosave_off_and_get_reflects_it(client, out_dir):
    r = client.post("/api/prefs", json={"autosave_sessions": False})

    assert r.status_code == 200
    assert r.json() == {"autosave_sessions": False, "theme": "mono"}
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
