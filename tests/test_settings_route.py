"""/api/settings route'ları: durum okuma + write-only kaydetme."""
import pytest
from fastapi.testclient import TestClient

import azure_client as ac
import app as appmod


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(tmp_path / "app" / "credentials.env"))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "default.env"))
    return TestClient(appmod.app)


def test_get_settings_not_configured(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False
    assert body["endpoint"] is None


def test_post_settings_saves_and_status_reflects(client):
    r = client.post("/api/settings", json={
        "api_key": "SUPERSECRET", "base_url": "https://ep/openai/v1/"})
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is True
    assert body["endpoint"] == "https://ep/openai/v1/"
    # response key sızdırmamalı
    assert "SUPERSECRET" not in r.text

    g = client.get("/api/settings")
    assert g.json()["configured"] is True
    assert "SUPERSECRET" not in g.text


def test_post_settings_rejects_bad_url(client):
    r = client.post("/api/settings", json={"api_key": "K", "base_url": "ftp://x/"})
    assert r.status_code == 422


def test_post_settings_rejects_empty_key(client):
    r = client.post("/api/settings", json={"api_key": "", "base_url": "https://x/"})
    assert r.status_code == 422


def test_post_blank_key_keeps_existing(client):
    # önce tam kayıt
    client.post("/api/settings", json={
        "api_key": "KEEPME", "base_url": "https://old/openai/v1/"})
    # sonra sadece endpoint güncelle (key boş)
    r = client.post("/api/settings", json={"api_key": "", "base_url": "https://new/openai/v1/"})
    assert r.status_code == 200
    assert r.json()["endpoint"] == "https://new/openai/v1/"
    # mevcut key korunmuş olmalı (dahili doğrulama; response'ta yok)
    key, url = ac.load_credentials()
    assert key == "KEEPME"
    assert url == "https://new/openai/v1/"


def test_validation_error_does_not_echo_api_key(client):
    # 500 karakter sınırını aşan key → pydantic doğrulama hatası; key gövdede yankılanmamalı
    secret = "S3CRET" + "x" * 600
    r = client.post("/api/settings", json={"api_key": secret, "base_url": "https://x/"})
    assert r.status_code == 422
    assert secret not in r.text
    assert "S3CRET" not in r.text


def test_get_settings_never_returns_key(client):
    client.post("/api/settings", json={
        "api_key": "TOPSECRETKEY", "base_url": "https://ep/openai/v1/"})
    g = client.get("/api/settings")
    assert "TOPSECRETKEY" not in g.text
    assert "api_key" not in g.json()
