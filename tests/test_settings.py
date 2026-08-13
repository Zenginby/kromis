"""azure_client kimlik yönetimi: kaydet/oku/fallback/durum."""
import os
import stat

import pytest

import azure_client as ac
import winsec


def _read_env(path):
    return path.read_text()


def _assert_yalniz_sahibine(path) -> None:
    """"Bu dosyayı yalnız sahibi okuyabilir" — platforma göre iki ayrı ölçüm.

    POSIX'te bu 0600 demek. Windows'ta `os.chmod` POSIX bitlerini uygulamıyor
    (Faz 0: 0o600 istenince dosya 0o666 kalıyor), güvence DACL ile kuruluyor —
    bu yüzden iddia orada `winsec.is_owner_only` ile ölçülüyor. Mod iddiasını
    Windows'ta ATLAMAK değil, karşılığıyla DEĞİŞTİRMEK: dosya Azure API
    anahtarını tutuyor, ölçülmeyen bir güvence yok sayılmış güvencedir.
    """
    if winsec.is_supported():
        assert winsec.is_owner_only(str(path)), winsec.dacl_sddl(str(path))
    else:
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_save_credentials_writes_file_0600(tmp_path):
    envp = tmp_path / "cfg" / "credentials.env"
    ac.save_credentials("KEY123", "https://x/openai/v1/", env_path=str(envp))
    assert envp.exists()
    _assert_yalniz_sahibine(envp)
    key, url = ac.load_credentials(env_path=str(envp))
    assert key == "KEY123"
    assert url == "https://x/openai/v1/"


def test_save_credentials_overwrite_keeps_0600(tmp_path):
    envp = tmp_path / "credentials.env"
    ac.save_credentials("A", "https://a/", env_path=str(envp))
    ac.save_credentials("B", "https://b/", env_path=str(envp))
    key, url = ac.load_credentials(env_path=str(envp))
    assert (key, url) == ("B", "https://b/")
    _assert_yalniz_sahibine(envp)


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


# ── Birleştirmeli yazım (v1.13: sohbet ayarı aynı dosyada yaşıyor) ──────
#
# save_credentials v1.12'ye kadar dosyayı SIFIRDAN iki satır yazıyordu. Sohbet
# dağıtımı aynı dosyada durduğu için o davranış "endpoint'i güncelle" eylemini
# sessizce "Prompt Yönetmeni'ni kapat" eylemine çeviriyordu.

def test_save_env_keeps_the_keys_it_was_not_asked_to_change(tmp_path):
    envp = tmp_path / "credentials.env"
    ac.save_credentials("KEY", "https://ep/openai/v1/", env_path=str(envp))
    ac.save_env({"AZURE_CHAT_DEPLOYMENT": "gpt-5.6-luna"}, env_path=str(envp))

    values = ac.read_env_values(str(envp))
    assert values["AZURE_IMAGE_API_KEY"] == "KEY"
    assert values["AZURE_IMAGE_BASE_URL"] == "https://ep/openai/v1/"
    assert values["AZURE_CHAT_DEPLOYMENT"] == "gpt-5.6-luna"


def test_saving_image_credentials_does_not_wipe_the_chat_deployment(tmp_path):
    """REGRESYON: sıfırdan yazan save_credentials bu satırı siliyordu."""
    envp = tmp_path / "credentials.env"
    ac.save_env({"AZURE_CHAT_DEPLOYMENT": "gpt-5.6-luna"}, env_path=str(envp))
    ac.save_credentials("KEY", "https://ep/openai/v1/", env_path=str(envp))

    assert ac.read_env_values(str(envp))["AZURE_CHAT_DEPLOYMENT"] == "gpt-5.6-luna"


def test_saving_the_chat_deployment_does_not_break_image_credentials(tmp_path):
    """Aynanın öteki yüzü: sohbet ayarı görsel üretimini bozmamalı."""
    envp = tmp_path / "credentials.env"
    ac.save_credentials("KEY", "https://ep/openai/v1/", env_path=str(envp))
    ac.save_env({"AZURE_CHAT_DEPLOYMENT": "gpt-5.6-luna"}, env_path=str(envp))

    assert ac.load_credentials(env_path=str(envp)) == ("KEY", "https://ep/openai/v1/")


def test_save_env_preserves_hand_written_extra_keys(tmp_path):
    """Elle eklenmiş bir değişken sessizce silinmemeli (bilinen anahtar süzgeci YOK)."""
    envp = tmp_path / "credentials.env"
    envp.write_text("ELLE_YAZILMIS=deger\nAZURE_IMAGE_API_KEY=K\n", encoding="utf-8")
    ac.save_env({"AZURE_CHAT_DEPLOYMENT": "d"}, env_path=str(envp))

    assert ac.read_env_values(str(envp))["ELLE_YAZILMIS"] == "deger"


def test_save_env_keeps_the_file_0600_and_the_directory_0700(tmp_path):
    envp = tmp_path / "cfg" / "credentials.env"
    ac.save_env({"AZURE_CHAT_DEPLOYMENT": "d"}, env_path=str(envp))

    _assert_yalniz_sahibine(envp)
    if winsec.is_supported():
        # 0700'ün karşılığı: dizin de yalnız sahibine ait olmalı. Dizindeki ACE
        # ayrıca KALITILABİLİR — geçici dosyanın yazımdan önceki korumasını
        # sağlayan şey bu (bkz. tests/test_winsec.py).
        assert winsec.is_owner_only(str(envp.parent)), \
            winsec.dacl_sddl(str(envp.parent))
    else:
        assert stat.S_IMODE(os.stat(envp.parent).st_mode) == 0o700


def test_save_env_rejects_newlines_in_values(tmp_path):
    """Satır sonu taşıyan bir değer dosyaya İKİNCİ bir anahtar enjekte ederdi.

    `chat_deployment` bir FORM alanı: uzunluk sınırı var ama içeriği serbest.
    save_credentials'taki aynı guard bu yolda da olmak zorunda.
    """
    envp = tmp_path / "credentials.env"
    with pytest.raises(ac.AzureImageError):
        ac.save_env({"AZURE_CHAT_DEPLOYMENT": "d\nAZURE_IMAGE_API_KEY=kotu"},
                    env_path=str(envp))
    assert not envp.exists()


def test_save_env_writes_an_empty_value_to_clear_a_setting(tmp_path):
    envp = tmp_path / "credentials.env"
    ac.save_env({"AZURE_CHAT_DEPLOYMENT": "gpt-5.6-luna"}, env_path=str(envp))
    ac.save_env({"AZURE_CHAT_DEPLOYMENT": ""}, env_path=str(envp))

    assert ac.read_env_values(str(envp)).get("AZURE_CHAT_DEPLOYMENT", "") == ""


def test_read_env_values_merges_the_candidate_files(tmp_path, monkeypatch):
    """Sohbet ayarı app dosyasında, görsel kimliği paylaşılan dosyada olabilir."""
    app_env = tmp_path / "app.env"
    default_env = tmp_path / "default.env"
    app_env.write_text("AZURE_CHAT_DEPLOYMENT=gpt-5.6-luna\n", encoding="utf-8")
    default_env.write_text("AZURE_IMAGE_API_KEY=SHARED\n"
                           "AZURE_IMAGE_BASE_URL=https://shared/openai/v1/\n",
                           encoding="utf-8")
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(default_env))

    values = ac.read_env_values()
    assert values["AZURE_CHAT_DEPLOYMENT"] == "gpt-5.6-luna"
    assert values["AZURE_IMAGE_API_KEY"] == "SHARED"


def test_read_env_values_lets_the_first_non_empty_value_win(tmp_path, monkeypatch):
    """Boş bir app değeri, dolu paylaşılan değeri GÖLGELEMEMELİ.

    `_first_complete_credentials`'ın fallback semantiğinin aynısı: yarım
    doldurulmuş app dosyası çalışan kurulumu bozmasın.
    """
    app_env = tmp_path / "app.env"
    default_env = tmp_path / "default.env"
    app_env.write_text("AZURE_IMAGE_API_KEY=\n", encoding="utf-8")
    default_env.write_text("AZURE_IMAGE_API_KEY=SHARED\n", encoding="utf-8")
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(default_env))

    assert ac.read_env_values()["AZURE_IMAGE_API_KEY"] == "SHARED"


# ── Sohbet kimliği çözümü ve durum alanları ────────────────────────────

def test_resolve_chat_credentials_falls_back_to_the_image_credentials(tmp_path, monkeypatch):
    app_env = tmp_path / "app.env"
    app_env.write_text("AZURE_IMAGE_API_KEY=K\n"
                       "AZURE_IMAGE_BASE_URL=https://ep/openai/v1/\n"
                       "AZURE_CHAT_DEPLOYMENT=gpt-5.6-luna\n", encoding="utf-8")
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "no.env"))

    assert ac.resolve_chat_credentials() == ("K", "https://ep/openai/v1/", "gpt-5.6-luna")


def test_resolve_chat_credentials_prefers_the_chat_specific_keys(tmp_path, monkeypatch):
    """Ayrı bir sohbet kaynağı kullanılabilsin (elle yazılan AZURE_CHAT_*)."""
    app_env = tmp_path / "app.env"
    app_env.write_text("AZURE_IMAGE_API_KEY=IMGKEY\n"
                       "AZURE_IMAGE_BASE_URL=https://img/openai/v1/\n"
                       "AZURE_CHAT_API_KEY=CHATKEY\n"
                       "AZURE_CHAT_BASE_URL=https://chat/openai/v1/\n"
                       "AZURE_CHAT_DEPLOYMENT=d\n", encoding="utf-8")
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "no.env"))

    assert ac.resolve_chat_credentials() == ("CHATKEY", "https://chat/openai/v1/", "d")


def test_status_exposes_the_chat_deployment_but_never_a_key(tmp_path, monkeypatch):
    app_env = tmp_path / "app.env"
    app_env.write_text("AZURE_IMAGE_API_KEY=SECRET\n"
                       "AZURE_IMAGE_BASE_URL=https://ep/openai/v1/\n"
                       "AZURE_CHAT_API_KEY=CHATSECRET\n"
                       "AZURE_CHAT_DEPLOYMENT=gpt-5.6-luna\n", encoding="utf-8")
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "no.env"))

    status = ac.get_settings_status()
    assert status["chat_deployment"] == "gpt-5.6-luna"
    assert status["chat_configured"] is True
    assert "SECRET" not in str(status)
    assert "CHATSECRET" not in str(status)
    assert "api_key" not in status and "key" not in status


def test_chat_is_not_configured_without_a_deployment_name(tmp_path, monkeypatch):
    """Dağıtım adı olmadan sohbet çalışamaz → arayüz kapısı kapalı kalmalı."""
    app_env = tmp_path / "app.env"
    app_env.write_text("AZURE_IMAGE_API_KEY=K\n"
                       "AZURE_IMAGE_BASE_URL=https://ep/openai/v1/\n", encoding="utf-8")
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "no.env"))

    status = ac.get_settings_status()
    assert status["chat_configured"] is False
    assert status["chat_deployment"] == ""


def test_chat_is_not_configured_without_any_credentials(tmp_path, monkeypatch):
    """Dağıtım adı tek başına yetmez: key/url yoksa istek Türkçe hatayla ölür.

    Kapı burada kapanmazsa arayüz sohbeti AÇAR ve kullanıcı ilk mesajında
    502 görür — teşhisi zor, oysa sebep basit.
    """
    app_env = tmp_path / "app.env"
    app_env.write_text("AZURE_CHAT_DEPLOYMENT=gpt-5.6-luna\n", encoding="utf-8")
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "no.env"))

    assert ac.get_settings_status()["chat_configured"] is False


def test_byok_settings_status_never_exposes_raw_keys(tmp_path, monkeypatch):
    app_env = tmp_path / "app.env"
    app_env.write_text(
        "OPENAI_API_KEY=sk-testkey123456\n"
        "FAL_KEY=fal-secret789\n"
        "REPLICATE_API_TOKEN=r8-secret000\n"
        "COMFYUI_URL=http://localhost:8188\n",
        encoding="utf-8"
    )
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(app_env))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "no.env"))

    status = ac.get_settings_status()
    assert status["has_openai_key"] is True
    assert status["has_fal_key"] is True
    assert status["has_replicate_token"] is True
    assert status["comfyui_url"] == "http://localhost:8188"
    assert "sk-testkey123456" not in str(status)
    assert "fal-secret789" not in str(status)

