"""palette_store.py — kayıtlı palet deposu testleri (tests/test_assets.py stili)."""
import json
import os

import palette_store

COLORS = [{"hex": "#c86a3c", "name": "copper orange"},
          {"hex": "#2e5fa3", "name": "cobalt blue"}]


def _create(tmp_path, name="Kurban sıcak", mode="analogic", now="2026-07-27T12:00:00"):
    return palette_store.create(name, "#c86a3c", mode, "balanced", COLORS,
                                str(tmp_path), now=now)


def test_create_writes_the_file_and_returns_the_record(tmp_path):
    record = _create(tmp_path)
    assert len(record["id"]) == 12
    assert record["name"] == "Kurban sıcak"
    assert record["seed"] == "#c86a3c"
    assert record["mode"] == "analogic"
    assert record["strength"] == "balanced"
    assert record["colors"] == COLORS
    assert record["created_at"] == "2026-07-27T12:00:00"

    on_disk = json.loads((tmp_path / "palettes.json").read_text(encoding="utf-8"))
    assert on_disk == [record]


def test_colors_are_frozen_into_the_record(tmp_path):
    """Adlar kayıt anında dondurulur; thecolorapi değişse bile prompt aynı kalır."""
    record = _create(tmp_path)
    reread = palette_store.list_palettes(str(tmp_path))[0]
    assert reread["colors"] == COLORS


def test_list_returns_newest_first(tmp_path):
    first = _create(tmp_path, name="ilk")
    second = _create(tmp_path, name="ikinci")
    ids = [p["id"] for p in palette_store.list_palettes(str(tmp_path))]
    assert ids == [second["id"], first["id"]]


def test_list_is_empty_when_no_file_exists(tmp_path):
    assert palette_store.list_palettes(str(tmp_path)) == []


def test_create_makes_the_output_dir(tmp_path):
    nested = tmp_path / "output"
    palette_store.create("x", "#c86a3c", "triad", "hint", COLORS,
                         str(nested), now="2026-07-27T12:00:00")
    assert (nested / "palettes.json").exists()


def test_delete_removes_the_record(tmp_path):
    record = _create(tmp_path)
    assert palette_store.delete(record["id"], str(tmp_path)) is True
    assert palette_store.list_palettes(str(tmp_path)) == []


def test_delete_is_a_noop_the_second_time(tmp_path):
    record = _create(tmp_path)
    palette_store.delete(record["id"], str(tmp_path))
    assert palette_store.delete(record["id"], str(tmp_path)) is False


def test_delete_leaves_other_palettes_alone(tmp_path):
    keep = _create(tmp_path, name="kalan")
    doomed = _create(tmp_path, name="giden")
    palette_store.delete(doomed["id"], str(tmp_path))
    assert [p["id"] for p in palette_store.list_palettes(str(tmp_path))] == [keep["id"]]


def test_delete_rejects_unsafe_ids(tmp_path):
    _create(tmp_path)
    for bad in ("../../etc/passwd", "not-hex", "", "ZZZZZZZZZZZZ", "abc"):
        assert palette_store.delete(bad, str(tmp_path)) is False
    assert len(palette_store.list_palettes(str(tmp_path))) == 1


def test_corrupt_json_is_tolerated(tmp_path):
    (tmp_path / "palettes.json").write_text("{bozuk", encoding="utf-8")
    assert palette_store.list_palettes(str(tmp_path)) == []


def test_non_list_json_is_tolerated(tmp_path):
    (tmp_path / "palettes.json").write_text('{"a": 1}', encoding="utf-8")
    assert palette_store.list_palettes(str(tmp_path)) == []


def test_create_over_corrupt_file_recovers(tmp_path):
    (tmp_path / "palettes.json").write_text("[[[", encoding="utf-8")
    record = _create(tmp_path)
    assert palette_store.list_palettes(str(tmp_path)) == [record]


def test_no_temp_file_is_left_behind(tmp_path):
    _create(tmp_path)
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == []


def test_non_ascii_names_survive_the_round_trip(tmp_path):
    record = _create(tmp_path, name="Şeker Bayramı — sıcak ağırlıklı")
    assert palette_store.list_palettes(str(tmp_path))[0]["name"] == record["name"]
