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
        os.path.expanduser("~/Library/Application Support"), "GPT-Image Studio")
    assert paths.is_frozen()
    assert paths.data_dir() == expected_data
    assert paths.output_dir() == os.path.join(expected_data, "output")
    assert paths.assets_dir() == os.path.join(expected_data, "assets")


def test_frozen_mode_writes_under_local_appdata_on_windows(monkeypatch):
    """Windows dalı: veri `%LOCALAPPDATA%\\GPT-Image Studio` altına gider.

    Roaming (`%APPDATA%`) DEĞİL: bu dizin üretilen görselleri tutuyor ve etki
    alanı profilinde ağ üzerinden taşınması istenmez.
    """
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Kullanicilar\test\AppData\Local")

    expected_data = os.path.join(r"C:\Kullanicilar\test\AppData\Local",
                                 "GPT-Image Studio")
    assert paths.data_dir() == expected_data
    assert paths.output_dir() == os.path.join(expected_data, "output")
    assert paths.assets_dir() == os.path.join(expected_data, "assets")


def test_frozen_windows_falls_back_when_localappdata_is_missing(monkeypatch):
    """Ortam değişkeni yoksa yol yine çözülmeli — uygulama hiç açılmamaktansa."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    expected = os.path.join(os.path.expanduser("~"), "AppData", "Local",
                            "GPT-Image Studio")
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
    assert paths.bundled_logos_dir() == os.path.join(
        "/tmp/meipass-test", "bundled", "logos")


def test_builtin_logo_resolves_both_variants():
    tail = os.path.join("bundled", "logos", "kurum-logo-{}.png")
    assert paths.builtin_logo("blue").endswith(tail.format("blue"))
    assert paths.builtin_logo("white").endswith(tail.format("white"))


def test_builtin_logo_rejects_unknown_variant():
    with pytest.raises(ValueError):
        paths.builtin_logo("kirmizi")


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
