"""Kullanıcı tercihleri deposu (v2.0) — `prefs.json`.

Bu depo neden VAR: otomatik kayıt anahtarı (karar D1'in üçüncü güvencesi) bir
yere yazılmak zorunda ve iki aday da yanlıştı —
  · `credentials.env` bir KİMLİK dosyası (0600, `~/.config`): bir arayüz
    tercihini oraya koymak, anahtarı her tercih değişiminde yeniden yazmak
    demekti (`POST /api/settings` api_key + base_url istiyor);
  · istemci (localStorage) `desktop.py`'nin private mode penceresinde her
    kapanışta siliniyor — `chat_store`'un başındaki ölçülmüş sebep.

Yani tercihler kullanıcının VERİ dizinine, diğer beş manifestin yanına düşüyor;
mekanikler jsonstore'dan (atomik yazım + yazma kilidi) geliyor.
"""
import json
import os

import prefs


def _read_raw(output_dir) -> dict:
    with open(os.path.join(str(output_dir), prefs.PREFS_FILE), encoding="utf-8") as f:
        return json.load(f)


# ── Varsayılanlar ───────────────────────────────────────────────────────

def test_autosave_is_on_by_default(tmp_path):
    """Karar D1: oturumlar otomatik kaydedilir. Dosya yokken de bu geçerli —
    yeni kurulumda geçmişin boş kalması D1'in tersini uygulamak olurdu."""
    assert prefs.read(str(tmp_path / "yok"))["autosave_sessions"] is True


def test_reading_does_not_create_the_file(tmp_path):
    """Okuma yan etkisiz: uygulama açılışta okuyor, dokunmadan çıkmalı."""
    out = str(tmp_path / "output")
    prefs.read(out)

    assert not os.path.exists(out)


# ── Yazma ───────────────────────────────────────────────────────────────

def test_update_writes_and_returns_the_merged_view(tmp_path):
    out = str(tmp_path / "output")

    merged = prefs.update({"autosave_sessions": False}, out)

    assert merged["autosave_sessions"] is False
    assert _read_raw(out) == {"autosave_sessions": False}
    assert prefs.read(out)["autosave_sessions"] is False


def test_update_with_nothing_to_change_leaves_the_file_alone(tmp_path):
    """Boş güncelleme dosyaya DOKUNMAZ: `chat_store.update`'in duruşunun aynısı."""
    out = str(tmp_path / "output")

    assert prefs.update({}, out)["autosave_sessions"] is True
    assert not os.path.exists(out)


def test_update_keeps_the_other_preferences(tmp_path):
    """Tema (Adım 9) buraya girecek: tek alanı yazmak diğerini düşürmemeli.

    `azure_client.save_env`'in "dosyanın geri kalanını koru" kuralının aynısı ve
    aynı sebep — orada endpoint'i tek başına kaydetmek sohbet dağıtımını sessizce
    silmişti (v1.12 hatası).
    """
    out = str(tmp_path / "output")
    prefs.update({"autosave_sessions": False}, out)
    raw = _read_raw(out)
    raw["theme"] = "amber"                      # elle/ileride yazılmış başka tercih
    prefs._write(out, raw)

    prefs.update({"autosave_sessions": True}, out)

    assert _read_raw(out) == {"autosave_sessions": True, "theme": "amber"}


def test_an_unknown_preference_is_a_loud_error(tmp_path):
    """`extra="forbid"` ethos'u: bilinmeyen anahtar sessizce yazılmaz.

    Sessizce kabul edilse yazım tipo'su "ayar çalışmıyor" olarak görünürdü ve
    dosyada hiç okunmayan bir alan birikirdi.
    """
    out = str(tmp_path / "output")

    try:
        prefs.update({"autosav_sessions": False}, out)
    except ValueError as exc:
        assert "autosav_sessions" in str(exc)
    else:
        raise AssertionError("bilinmeyen tercih sessizce kabul edildi")
    assert not os.path.exists(out)


def test_a_wrong_type_is_a_loud_error(tmp_path):
    out = str(tmp_path / "output")

    try:
        prefs.update({"autosave_sessions": "hayır"}, out)
    except ValueError:
        pass
    else:
        raise AssertionError("bool olmayan değer kabul edildi")


# ── Dayanıklılık (beş depoyla aynı duruş) ───────────────────────────────

def test_corrupt_json_reads_as_defaults_instead_of_crashing(tmp_path):
    out = str(tmp_path / "output")
    os.makedirs(out)
    with open(os.path.join(out, prefs.PREFS_FILE), "w", encoding="utf-8") as f:
        f.write("{bu json değil")

    assert prefs.read(out)["autosave_sessions"] is True


def test_a_json_list_instead_of_an_object_reads_as_defaults(tmp_path):
    out = str(tmp_path / "output")
    os.makedirs(out)
    with open(os.path.join(out, prefs.PREFS_FILE), "w", encoding="utf-8") as f:
        json.dump(["yanlış şekil"], f)

    assert prefs.read(out)["autosave_sessions"] is True


def test_a_hand_edited_wrong_type_falls_back_to_the_default(tmp_path):
    """Elle `"false"` yazılmış bir dosya TAHMİN edilmiyor.

    `bool("false")` True'dur: dizeyi bool'a çevirmeye çalışmak kullanıcının
    "kapat" niyetini tam tersine döndürebilirdi. Yazma yolu bunu zaten
    reddediyor, okuma yolu da varsayılana düşüyor.
    """
    out = str(tmp_path / "output")
    os.makedirs(out)
    with open(os.path.join(out, prefs.PREFS_FILE), "w", encoding="utf-8") as f:
        json.dump({"autosave_sessions": "false"}, f)

    assert prefs.read(out)["autosave_sessions"] is True


def test_write_leaves_no_temp_file(tmp_path):
    out = str(tmp_path / "output")

    prefs.update({"autosave_sessions": False}, out)

    assert os.listdir(out) == [prefs.PREFS_FILE]
