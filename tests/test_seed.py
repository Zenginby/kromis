import os
from unittest.mock import MagicMock

import app as appmod
import assets_store as astore
import seed
from fastapi.testclient import TestClient

NOW = "2026-07-28T12:00:00"


def _make_bundled(tmp_path):
    bundled = tmp_path / "bundled" / "logos"
    bundled.mkdir(parents=True)
    (bundled / "kurum-logo-blue.png").write_bytes(b"\x89PNG-blue")
    (bundled / "kurum-logo-white.png").write_bytes(b"\x89PNG-white")
    return str(bundled)


def test_seeds_both_logos_into_an_empty_library(tmp_path):
    bundled = _make_bundled(tmp_path)
    assets = str(tmp_path / "assets")

    added = seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)

    assert len(added) == 2
    names = sorted(r["name"] for r in astore.list_assets("logos", assets))
    assert names == ["KURUM Logo Beyaz", "KURUM Logo Mavi"]
    stored = {r["name"]: open(os.path.join(assets, "logos", r["filename"]), "rb").read()
              for r in astore.list_assets("logos", assets)}
    assert stored["KURUM Logo Mavi"] == b"\x89PNG-blue"
    assert stored["KURUM Logo Beyaz"] == b"\x89PNG-white"


def test_second_call_does_not_duplicate(tmp_path):
    bundled = _make_bundled(tmp_path)
    assets = str(tmp_path / "assets")

    seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)
    added_again = seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)

    assert added_again == []
    assert len(astore.list_assets("logos", assets)) == 2


def test_does_not_restore_logos_the_user_deleted(tmp_path):
    bundled = _make_bundled(tmp_path)
    assets = str(tmp_path / "assets")

    added = seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)
    for record in added:
        astore.delete_asset("logos", record["id"], assets)
    assert astore.list_assets("logos", assets) == []

    seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)
    assert astore.list_assets("logos", assets) == []  # marker var → geri gelmez


def test_leaves_a_non_empty_library_alone(tmp_path):
    """Mevcut kurulumda (marker yok, kütüphane dolu) tohumlama yapılmaz."""
    bundled = _make_bundled(tmp_path)
    assets = str(tmp_path / "assets")
    astore.save_asset("logos", b"\x89PNG-mine", "kendi logom", assets, now=NOW)

    added = seed.seed_builtin_logos(assets, bundled, str(tmp_path), now=NOW)

    assert added == []
    assert [r["name"] for r in astore.list_assets("logos", assets)] == ["kendi logom"]
    # Marker must be written even when no seeding occurs (protects against resurrection)
    assert (tmp_path / ".logos-seeded").is_file()


def test_missing_bundled_dir_is_not_fatal(tmp_path):
    """Gömülü logolar yoksa (geliştirme kopyası) sessizce atlanır, çökmez."""
    assets = str(tmp_path / "assets")
    added = seed.seed_builtin_logos(assets, str(tmp_path / "yok"), str(tmp_path), now=NOW)
    assert added == []


def test_writes_the_marker_file(tmp_path):
    bundled = _make_bundled(tmp_path)
    seed.seed_builtin_logos(str(tmp_path / "assets"), bundled, str(tmp_path), now=NOW)
    assert (tmp_path / ".logos-seeded").is_file()


def test_seeding_does_not_fire_on_plain_import(monkeypatch):
    """Seeding should NOT fire when app is imported or TestClient is created without context."""
    # Monkeypatch to track calls
    original_seed = appmod.seed.seed_builtin_logos
    call_recorder = MagicMock()
    monkeypatch.setattr(appmod.seed, "seed_builtin_logos", call_recorder)

    # Create TestClient without context manager — should NOT trigger lifespan startup
    client = TestClient(appmod.app)

    # Seeding should not have been called during client construction without `with`
    call_recorder.assert_not_called()

    # Restore for other tests
    monkeypatch.setattr(appmod.seed, "seed_builtin_logos", original_seed)


def test_seeding_fires_on_lifespan_startup(monkeypatch):
    """Seeding MUST fire when the ASGI app actually starts (within lifespan context)."""
    # Monkeypatch to track calls
    original_seed = appmod.seed.seed_builtin_logos
    call_recorder = MagicMock()
    monkeypatch.setattr(appmod.seed, "seed_builtin_logos", call_recorder)

    # Use context manager — this triggers lifespan startup
    with TestClient(appmod.app) as client:
        # Seeding should have been called exactly once during startup
        call_recorder.assert_called_once()
        # Verify it was called with the expected arguments
        args, kwargs = call_recorder.call_args
        assert args[0] == appmod.ASSETS_DIR
        assert args[1] == appmod.paths.bundled_logos_dir()
        assert args[2] == appmod.paths.data_dir()
        assert "now" in kwargs

    # Restore for other tests
    monkeypatch.setattr(appmod.seed, "seed_builtin_logos", original_seed)
