import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import paths


def test_dev_mode_paths_match_the_repo_layout():
    """Geliştirmede yollar bugünküyle birebir aynı olmalı (599 testin dayandığı varsayım)."""
    assert not paths.is_frozen()
    assert paths.data_dir() == paths.REPO_DIR
    assert paths.resource_dir() == paths.REPO_DIR
    assert paths.output_dir() == os.path.join(paths.REPO_DIR, "output")
    assert paths.assets_dir() == os.path.join(paths.REPO_DIR, "assets")
    assert paths.static_dir() == os.path.join(paths.REPO_DIR, "static")


def test_dev_mode_matches_app_module_constants():
    """app.py'nin sabitleri paths.py ile aynı yerleri göstermeli."""
    import app as appmod
    assert appmod.OUTPUT_DIR == paths.output_dir()
    assert appmod.STATIC_DIR == paths.static_dir()
    assert appmod.ASSETS_DIR == paths.assets_dir()


def test_frozen_mode_writes_under_application_support(monkeypatch):
    """macOS dalı. `sys.platform` SAHTELENİYOR: bu iddia macOS'un yerleşimini
    ölçüyor, koşan makinenin yerleşimini değil — aksi halde aynı test Windows'ta
    kırmızıya düşer ve iki platformun yerleşimi tek testte karışırdı."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass-test", raising=False)

    expected_data = os.path.join(
        os.path.expanduser("~/Library/Application Support"), "Lumeo")
    assert paths.is_frozen()
    assert paths.data_dir() == expected_data
    assert paths.output_dir() == os.path.join(expected_data, "output")
    assert paths.assets_dir() == os.path.join(expected_data, "assets")


def test_frozen_mode_writes_under_local_appdata_on_windows(monkeypatch):
    """Windows dalı: veri `%LOCALAPPDATA%\\Lumeo` altına gider.

    Roaming (`%APPDATA%`) DEĞİL: bu dizin üretilen görselleri tutuyor ve etki
    alanı profilinde ağ üzerinden taşınması istenmez.
    """
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Kullanicilar\test\AppData\Local")

    expected_data = os.path.join(r"C:\Kullanicilar\test\AppData\Local",
                                 "Lumeo")
    assert paths.data_dir() == expected_data
    assert paths.output_dir() == os.path.join(expected_data, "output")
    assert paths.assets_dir() == os.path.join(expected_data, "assets")


def test_frozen_windows_falls_back_when_localappdata_is_missing(monkeypatch):
    """Ortam değişkeni yoksa yol yine çözülmeli — uygulama hiç açılmamaktansa."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    expected = os.path.join(os.path.expanduser("~"), "AppData", "Local",
                            "Lumeo")
    assert paths.data_dir() == expected


def test_dev_mode_ignores_the_platform(monkeypatch):
    """Geliştirmede iki platformda da kök repo dizini — 1150+ testin dayandığı
    varsayım, platform dalı eklenirken kazara değişmemeli."""
    monkeypatch.setattr(sys, "platform", "win32")
    assert paths.data_dir() == paths.REPO_DIR


def test_frozen_mode_reads_resources_from_meipass(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass-test", raising=False)

    # Beklenti os.path.join ile kurulur, elle "/" ile DEĞİL: kod zaten
    # os.path.join kullanıyor, yani Windows'ta ayraç "\" olur ve elle yazılmış
    # bir POSIX yolu testi üründe hiçbir kusur yokken kırmızıya düşürür
    # (Windows paketleme turunda birebir bu oldu).
    assert paths.resource_dir() == "/tmp/meipass-test"
    assert paths.static_dir() == os.path.join("/tmp/meipass-test", "static")
    assert paths.bundled_prompts_dir() == os.path.join(
        "/tmp/meipass-test", "bundled", "prompts")


# ── Android dalı ────────────────────────────────────────────────────
# Desen yukarıdakilerle aynı: platform SAHTELENİYOR (burada ortam değişkeniyle),
# böylece iddialar Android'in yerleşimini ölçüyor, koşan makinenin değil.


def test_android_branch_opens_only_with_the_env_var(monkeypatch):
    """Ortam değişkeni yoksa Android dalı KAPALI kalmalı.

    Bu testin var oluş sebebi: Chaquopy'de `sys.platform` "linux" döner. Dal
    platforma bakarak açılsaydı Linux'ta geliştiren biri sessizce Android
    yoluna düşerdi — dalı ortam değişkenine bağlama kararının tek koruması bu.
    """
    monkeypatch.delenv(paths.ANDROID_DATA_ENV, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    assert not paths.is_android()
    assert paths.data_dir() == paths.REPO_DIR


def test_android_writes_under_the_app_private_dir(monkeypatch):
    """Yazılabilir kök Kotlin'in bildirdiği `filesDir`; `~` HİÇ kullanılmıyor."""
    monkeypatch.setenv(paths.ANDROID_DATA_ENV, "/data/user/0/org.kurum.gpt_image_studio/files")
    # `~`'ı bilerek saçma bir yere çekiyoruz: bir yol expanduser'a uğrarsa
    # iddia kırmızıya düşsün. Android'de HOME'un tanımsız/"/" olması tam olarak
    # bu sınıf bir hatayı üretirdi.
    monkeypatch.setenv("HOME", "/olmayan-ev")

    kok = "/data/user/0/org.kurum.gpt_image_studio/files"
    assert paths.is_android()
    assert paths.data_dir() == kok
    assert paths.output_dir() == os.path.join(kok, "output")
    assert paths.assets_dir() == os.path.join(kok, "assets")
    assert paths.chat_instructions_override() == os.path.join(kok, "chat-instructions.md")


def test_android_beats_the_frozen_branch(monkeypatch):
    """Android dalı frozen dallarının ÖNÜNDE olmalı.

    Chaquopy'de `sys.frozen` yok, ama sıra tersine kurulsaydı bir gün
    eklenecek bir işaret uygulamayı APK'nın salt-okunur içine yazmaya
    çalıştırırdı. Sıra bir davranış, yorum değil — bu yüzden teste bağlandı.
    """
    monkeypatch.setenv(paths.ANDROID_DATA_ENV, "/data/veri")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass-test", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")

    assert paths.data_dir() == "/data/veri"


def test_android_resources_come_from_the_copied_dir(monkeypatch):
    """static/ ve bundled/ APK assets'inden değil, kopyalandıkları dizinden okunur."""
    monkeypatch.setenv(paths.ANDROID_DATA_ENV, "/data/veri")
    monkeypatch.setenv(paths.ANDROID_RESOURCE_ENV, "/data/veri/resources")

    assert paths.resource_dir() == "/data/veri/resources"
    assert paths.static_dir() == os.path.join("/data/veri/resources", "static")
    assert paths.bundled_prompts_dir() == os.path.join(
        "/data/veri/resources", "bundled", "prompts")


def test_android_resource_dir_falls_back_under_data_dir(monkeypatch):
    """Kaynak değişkeni bildirilmezse yerleşim yine çözülmeli.

    Kotlin tarafı kopyalamayı `filesDir/resources/` altına yapıyor; iki taraftan
    biri unutulduğunda uygulama hiç açılmamaktansa doğru yere baksın.
    """
    monkeypatch.setenv(paths.ANDROID_DATA_ENV, "/data/veri")
    monkeypatch.delenv(paths.ANDROID_RESOURCE_ENV, raising=False)

    assert paths.resource_dir() == os.path.join("/data/veri", "resources")


def test_desktop_credential_paths_are_unchanged(monkeypatch):
    """Kimlik yolları `paths`'e taşındı — masaüstü değerleri BİREBİR aynı kalmalı.

    Bu iki yol mevcut kurulumlardaki dosyaları gösteriyor; değişmesi
    kullanıcının Azure anahtarının "kaybolması" demek olurdu.
    """
    monkeypatch.delenv(paths.ANDROID_DATA_ENV, raising=False)

    assert paths.credentials_path() == os.path.expanduser(
        "~/.config/lumeo/credentials.env")
    assert paths.shared_credentials_path() == os.path.expanduser(
        "~/.config/claude-tools/azure-gpt-image2.env")


def test_android_credentials_live_in_the_app_private_dir(monkeypatch):
    monkeypatch.setenv(paths.ANDROID_DATA_ENV, "/data/veri")

    assert paths.credentials_path() == os.path.join("/data/veri", "credentials.env")
    # Paylaşılan claude-tools dosyasının telefonda karşılığı yok.
    assert paths.shared_credentials_path() is None


def test_azure_client_reads_the_paths_module(monkeypatch):
    """`azure_client`'ın sabitleri `paths` ile aynı yeri göstermeli."""
    import azure_client as ac
    assert ac.APP_ENV_PATH == paths.credentials_path()
    assert ac.DEFAULT_ENV_PATH == paths.shared_credentials_path()


def test_candidate_paths_drop_the_missing_shared_file(monkeypatch):
    """Aday listesi `None`'ı elemeli — Android'de paylaşılan dosya yok.

    Elenmeseydi `_parse_env_file(None)` TypeError verirdi: kimlik okumanın
    tamamı, yani uygulamanın açılışı, telefonda patlardı.
    """
    import azure_client as ac
    monkeypatch.setattr(ac, "APP_ENV_PATH", "/data/veri/credentials.env")
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", None)

    assert ac._candidate_paths(None) == ["/data/veri/credentials.env"]
    # Masaüstündeki sıra ve içerik korunuyor.
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", "/ev/paylasilan.env")
    assert ac._candidate_paths(None) == [
        "/data/veri/credentials.env", "/ev/paylasilan.env"]


def test_ensure_data_dirs_runs_on_startup_not_on_import(monkeypatch):
    """Dizin açmak da bir yan etkidir — tohumlamayla aynı gerekçe (I3).

    `import app` eden herhangi bir araç (test, tip denetleyici, betik)
    kullanıcının gerçek `~/Library/Application Support/...` ağacını
    yaratmamalı; dizinler sunucu gerçekten başlarken açılır.
    """
    import app as appmod
    recorder = MagicMock()
    monkeypatch.setattr(appmod.paths, "ensure_data_dirs", recorder)

    TestClient(appmod.app)  # context yok → lifespan çalışmaz
    recorder.assert_not_called()

    with TestClient(appmod.app):
        recorder.assert_called_once()


def test_ensure_data_dirs_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: str(tmp_path / "veri"))

    paths.ensure_data_dirs()
    (tmp_path / "veri" / "output" / "dokunma.txt").write_text("kalmalı", encoding="utf-8")
    paths.ensure_data_dirs()  # ikinci çağrı hiçbir şeyi silmemeli

    assert (tmp_path / "veri" / "output").is_dir()
    assert (tmp_path / "veri" / "assets").is_dir()
    assert (tmp_path / "veri" / "output" / "dokunma.txt").read_text(encoding="utf-8") == "kalmalı"
