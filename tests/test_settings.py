"""azure_client kimlik yönetimi: kaydet/oku/fallback/durum."""
import os
import stat

import pytest

import azure_client as ac


def _read_env(path):
    return path.read_text()


def test_save_credentials_writes_file_0600(tmp_path):
    envp = tmp_path / "cfg" / "credentials.env"
    ac.save_credentials("KEY123", "https://x/openai/v1/", env_path=str(envp))
    assert envp.exists()
    mode = stat.S_IMODE(os.stat(envp).st_mode)
    assert mode == 0o600
    key, url = ac.load_credentials(env_path=str(envp))
    assert key == "KEY123"
    assert url == "https://x/openai/v1/"


def test_save_credentials_overwrite_keeps_0600(tmp_path):
    envp = tmp_path / "credentials.env"
    ac.save_credentials("A", "https://a/", env_path=str(envp))
    ac.save_credentials("B", "https://b/", env_path=str(envp))
    key, url = ac.load_credentials(env_path=str(envp))
    assert (key, url) == ("B", "https://b/")
    assert stat.S_IMODE(os.stat(envp).st_mode) == 0o600


def test_save_credentials_rejects_empty(tmp_path):
    envp = tmp_path / "credentials.env"
    with pytest.raises(ac.AzureImageError):
        ac.save_credentials("", "https://x/", env_path=str(envp))
    with pytest.raises(ac.AzureImageError):
        ac.save_credentials("K", "   ", env_path=str(envp))
    assert not envp.exists()


def test_save_credentials_rejects_non_http_url(tmp_path):
    envp = tmp_path / "credentials.env"
    with pytest.raises(ac.AzureImageError):
        ac.save_credentials("K", "ftp://x/", env_path=str(envp))
    assert not envp.exists()


def test_save_credentials_rejects_whitespace_only_key(tmp_path):
    envp = tmp_path / "credentials.env"
    with pytest.raises(ac.AzureImageError):
        ac.save_credentials("   ", "https://x/", env_path=str(envp))
    assert not envp.exists()


def test_save_credentials_rejects_newline(tmp_path):
    envp = tmp_path / "credentials.env"
    with pytest.raises(ac.AzureImageError):
        ac.save_credentials("abc\nAZURE_IMAGE_BASE_URL=evil", "https://x/", env_path=str(envp))
    with pytest.raises(ac.AzureImageError):
        ac.save_credentials("abc", "https://x/\nfoo", env_path=str(envp))
    assert not envp.exists()


def test_save_load_roundtrip_non_ascii(tmp_path):
    envp = tmp_path / "credentials.env"
    ac.save_credentials("kéy-şĞ", "https://exämple/openai/v1/", env_path=str(envp))
    key, url = ac.load_credentials(env_path=str(envp))
    assert key == "kéy-şĞ"
    assert url == "https://exämple/openai/v1/"


def test_parse_env_file_missing_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        ac._parse_env_file(str(tmp_path / "nope.env"))


def test_load_prefers_app_over_default(tmp_path, monkeypatch):
    app_env = tmp_path / "app.env"
    default_env = tmp_path / "default.env"
    default_env.write_text("AZURE_IMAGE_API_KEY=OLD\nAZURE_IMAGE_BASE_URL=https://old/\n")
    app_env.write_text("AZURE_IMAGE_API_KEY=NEW\nAZURE_IMAGE_BASE_URL=https://new/\n")
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(default_env))
    key, url = ac.load_credentials()
    assert (key, url) == ("NEW", "https://new/")


def test_load_falls_back_to_default_when_app_missing(tmp_path, monkeypatch):
    app_env = tmp_path / "missing.env"  # yazılmadı
    default_env = tmp_path / "default.env"
    default_env.write_text("AZURE_IMAGE_API_KEY=SHARED\nAZURE_IMAGE_BASE_URL=https://shared/\n")
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(default_env))
    key, url = ac.load_credentials()
    assert (key, url) == ("SHARED", "https://shared/")


def test_load_falls_back_when_app_incomplete(tmp_path, monkeypatch):
    app_env = tmp_path / "app.env"
    default_env = tmp_path / "default.env"
    app_env.write_text("AZURE_IMAGE_API_KEY=ONLYKEY\n")  # url eksik
    default_env.write_text("AZURE_IMAGE_API_KEY=SHARED\nAZURE_IMAGE_BASE_URL=https://shared/\n")
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(default_env))
    key, url = ac.load_credentials()
    assert (key, url) == ("SHARED", "https://shared/")


def test_load_raises_when_none_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(tmp_path / "none1.env"))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "none2.env"))
    with pytest.raises(ac.AzureImageError):
        ac.load_credentials()


def test_get_settings_status_configured(tmp_path, monkeypatch):
    app_env = tmp_path / "app.env"
    app_env.write_text("AZURE_IMAGE_API_KEY=SECRET\nAZURE_IMAGE_BASE_URL=https://ep/openai/v1/\n")
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "no.env"))
    status = ac.get_settings_status()
    assert status["configured"] is True
    assert status["endpoint"] == "https://ep/openai/v1/"
    # kesinlikle key sızdırmaz
    assert "SECRET" not in str(status)
    assert "api_key" not in status and "key" not in status


def test_get_settings_status_not_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(tmp_path / "no1.env"))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "no2.env"))
    status = ac.get_settings_status()
    assert status["configured"] is False
    assert status["endpoint"] is None
