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
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass-test", raising=False)

    expected_data = os.path.join(
        os.path.expanduser("~/Library/Application Support"), "GPT-Image Studio")
    assert paths.is_frozen()
    assert paths.data_dir() == expected_data
    assert paths.output_dir() == os.path.join(expected_data, "output")
    assert paths.assets_dir() == os.path.join(expected_data, "assets")


def test_frozen_mode_reads_resources_from_meipass(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass-test", raising=False)

    assert paths.resource_dir() == "/tmp/meipass-test"
    assert paths.static_dir() == "/tmp/meipass-test/static"
    assert paths.bundled_logos_dir() == "/tmp/meipass-test/bundled/logos"


def test_builtin_logo_resolves_both_variants():
    assert paths.builtin_logo("blue").endswith("bundled/logos/kurum-logo-blue.png")
    assert paths.builtin_logo("white").endswith("bundled/logos/kurum-logo-white.png")


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
    (tmp_path / "veri" / "output" / "dokunma.txt").write_text("kalmalı")
    paths.ensure_data_dirs()  # ikinci çağrı hiçbir şeyi silmemeli

    assert (tmp_path / "veri" / "output").is_dir()
    assert (tmp_path / "veri" / "assets").is_dir()
    assert (tmp_path / "veri" / "output" / "dokunma.txt").read_text() == "kalmalı"
