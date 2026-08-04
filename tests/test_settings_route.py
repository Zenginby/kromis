"""/api/settings route'ları: durum okuma + write-only kaydetme."""
import pytest
from fastapi.testclient import TestClient

import azure_client as ac
import app as appmod
import version


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


def test_get_settings_exposes_the_app_version(client):
    """Destek sorusu "hangi sürümdesiniz?" — arayüz bunu buradan okuyor.

    Sürüm azure_client'ın get_settings_status'una DEĞİL, route'a eklendi:
    kimlik bilgisi modülünün uygulama sürümünü bilmesi gereksiz bir bağ olurdu.
    """
    assert client.get("/api/settings").json()["version"] == version.APP_VERSION


def test_post_settings_does_not_claim_a_version(client):
    """Sürüm çalışma anında değişmez → mutasyon ucundan yansıtmak gürültü olur.

    settings.js'teki `if (s && s.version)` guard'ı tam bu yüzden var: aynı
    fonksiyon POST yanıtını da işliyor, guard olmadan "Kaydet"ten sonra sürüm
    satırı silinirdi.
    """
    r = client.post("/api/settings", json={"api_key": "K", "base_url": "https://x/"})
    assert "version" not in r.json()


def test_get_settings_never_returns_key(client):
    client.post("/api/settings", json={
        "api_key": "TOPSECRETKEY", "base_url": "https://ep/openai/v1/"})
    g = client.get("/api/settings")
    assert "TOPSECRETKEY" not in g.text
    assert "api_key" not in g.json()


# ── Prompt Yönetmeni dağıtım adı (v1.13) ───────────────────────────────

def test_chat_deployment_round_trips(client):
    r = client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ep/openai/v1/",
        "chat_deployment": "gpt-5.6-luna"})
    assert r.status_code == 200
    assert r.json()["chat_deployment"] == "gpt-5.6-luna"
    assert r.json()["chat_configured"] is True

    g = client.get("/api/settings")
    assert g.json()["chat_deployment"] == "gpt-5.6-luna"


def test_saving_only_the_endpoint_keeps_the_chat_deployment(client):
    """REGRESYON: `save_env` birleştirmezse bu test kırmızı olur.

    v1.12'nin `save_credentials`'ı dosyayı sıfırdan iki satır yazıyordu, yani
    "endpoint'i güncelle" eylemi Prompt Yönetmeni'ni sessizce kapatıyordu.
    """
    client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://old/openai/v1/",
        "chat_deployment": "gpt-5.6-luna"})
    r = client.post("/api/settings", json={
        "api_key": "", "base_url": "https://new/openai/v1/",
        "chat_deployment": "gpt-5.6-luna"})

    assert r.status_code == 200
    assert r.json()["endpoint"] == "https://new/openai/v1/"
    assert r.json()["chat_deployment"] == "gpt-5.6-luna"


def test_a_stale_client_that_omits_the_field_does_not_clear_it(client):
    """Alan HİÇ gönderilmediyse "dokunma" demek; boş dize "temizle" demek.

    İkisi ayrılmazsa `?v=` cache-buster'ını atlatmış bayat bir settings.js,
    kullanıcı endpoint'ini kaydettiği anda Prompt Yönetmeni'ni sessizce kapatır.
    """
    client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ep/openai/v1/",
        "chat_deployment": "gpt-5.6-luna"})
    r = client.post("/api/settings", json={"api_key": "", "base_url": "https://ep/openai/v1/"})

    assert r.json()["chat_deployment"] == "gpt-5.6-luna"


def test_an_explicit_empty_value_clears_the_chat_deployment(client):
    client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ep/openai/v1/",
        "chat_deployment": "gpt-5.6-luna"})
    r = client.post("/api/settings", json={
        "api_key": "", "base_url": "https://ep/openai/v1/", "chat_deployment": ""})

    assert r.json()["chat_deployment"] == ""
    assert r.json()["chat_configured"] is False


def test_chat_deployment_is_not_written_when_the_credentials_are_rejected(client):
    """Görsel kimliği doğrulamadan geçmeden sohbet ayarı yazılmaz."""
    r = client.post("/api/settings", json={
        "api_key": "K", "base_url": "ftp://x/", "chat_deployment": "gpt-5.6-luna"})
    assert r.status_code == 422

    assert client.get("/api/settings").json()["chat_deployment"] == ""


def test_settings_expose_where_the_instructions_file_can_be_overridden(client):
    """Ezme yolu keşfedilebilir olmalı: yoksa özellik var ama kimse bulamaz."""
    body = client.get("/api/settings").json()
    assert body["chat_instructions_path"].endswith("chat-instructions.md")


def test_settings_never_leak_a_hand_written_chat_api_key(client, tmp_path, monkeypatch):
    """Ayrı bir sohbet anahtarı ELLE yazılabiliyor; uç onu asla yankılamamalı."""
    envp = tmp_path / "app" / "credentials.env"
    envp.parent.mkdir(parents=True, exist_ok=True)
    envp.write_text("AZURE_IMAGE_API_KEY=K\n"
                    "AZURE_IMAGE_BASE_URL=https://ep/openai/v1/\n"
                    "AZURE_CHAT_API_KEY=CHATTOPSECRET\n"
                    "AZURE_CHAT_DEPLOYMENT=gpt-5.6-luna\n", encoding="utf-8")

    r = client.get("/api/settings")
    assert "CHATTOPSECRET" not in r.text
    assert r.json()["chat_configured"] is True


def test_chat_deployment_with_a_newline_is_rejected(client):
    """Satır sonu dosyaya ikinci bir anahtar enjekte ederdi (save_env guard'ı)."""
    r = client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ep/openai/v1/",
        "chat_deployment": "d\nAZURE_IMAGE_API_KEY=kotu"})

    assert r.status_code == 422
