"""Kayıtlı sohbetler ve chats.json yönetimi.

Bu store v1.15'te KARAR 4'ün kapsamını daraltıyor: tamamlama rotası
(`POST /api/chat`) hâlâ diske hiçbir şey yazmıyor, yazan tek yol kullanıcının
başlattığı `/api/chats`. Testler bu ayrımı da, `palette_store`/`folders` ile
paylaşılan dayanıklılık desenlerini de (bozuk JSON, atomik yazım, `_SAFE_ID`)
mekanik hale getiriyor.
"""
import json
import os

import chat_store

THREAD = [{"role": "user", "content": "kare instagram görseli"},
          {"role": "assistant", "content": "**PROMPT**\n```\na cat\n```"}]


def _read_raw(output_dir) -> list:
    with open(os.path.join(str(output_dir), chat_store.CHATS_FILE), encoding="utf-8") as f:
        return json.load(f)


# ── Oluşturma ───────────────────────────────────────────────────────────

def test_create_writes_the_record_and_returns_it(tmp_path):
    out = str(tmp_path / "output")

    rec = chat_store.create("kare görsel", THREAD, out, now="2026-08-05T10:00:00")

    assert rec["title"] == "kare görsel"
    assert rec["messages"] == THREAD
    assert rec["created_at"] == rec["updated_at"] == "2026-08-05T10:00:00"
    assert len(rec["id"]) == 12
    assert _read_raw(out) == [rec]


def test_create_makes_the_output_dir(tmp_path):
    """İlk sohbet, hiç görsel üretilmemiş bir kurulumda kaydedilebilmeli."""
    out = str(tmp_path / "yok")

    chat_store.create("a", THREAD, out, now="2026-08-05T10:00:00")

    assert os.path.isdir(out)


def test_create_appends_without_touching_earlier_records(tmp_path):
    out = str(tmp_path / "output")
    first = chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")

    chat_store.create("iki", THREAD, out, now="2026-08-05T11:00:00")

    assert _read_raw(out)[0] == first


# ── Listeleme ───────────────────────────────────────────────────────────

def test_list_is_newest_first(tmp_path):
    """folders.list_folders / palette_store.list_palettes ile aynı sıra."""
    out = str(tmp_path / "output")
    chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")
    chat_store.create("iki", THREAD, out, now="2026-08-05T11:00:00")

    assert [c["title"] for c in chat_store.list_chats(out)] == ["iki", "bir"]


def test_list_does_not_leak_message_bodies(tmp_path):
    """Kenar paneli yalnız başlık gösteriyor; gövdeler `get` ile geliyor.

    Sohbet başına 60k karaktere kadar metin var — otuz sohbetin tamamını her
    açılışta göndermek boşuna trafik ve boşuna ayrıştırma olurdu.
    """
    out = str(tmp_path / "output")
    chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")

    summary = chat_store.list_chats(out)[0]

    assert "messages" not in summary
    assert summary["message_count"] == 2
    assert set(summary) == {"id", "title", "created_at", "updated_at", "message_count"}


def test_list_is_empty_when_nothing_saved(tmp_path):
    assert chat_store.list_chats(str(tmp_path / "output")) == []


# ── Okuma ───────────────────────────────────────────────────────────────

def test_get_returns_the_full_thread(tmp_path):
    out = str(tmp_path / "output")
    rec = chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")

    assert chat_store.get(rec["id"], out) == rec


def test_get_returns_none_for_unknown_id(tmp_path):
    out = str(tmp_path / "output")
    chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")

    assert chat_store.get("0123456789ab", out) is None


def test_get_rejects_an_unsafe_id_without_reading(tmp_path):
    """`_SAFE_ID` guard'ı: yol parçası taşıyan bir id dosyaya hiç ulaşmamalı."""
    out = str(tmp_path / "output")
    chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")

    assert chat_store.get("../../etc/passwd", out) is None
    assert chat_store.get("", out) is None


# ── Güncelleme ──────────────────────────────────────────────────────────

def test_update_replaces_messages_and_stamps_updated_at(tmp_path):
    out = str(tmp_path / "output")
    rec = chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")
    longer = THREAD + [{"role": "user", "content": "daha sıcak olsun"}]

    updated = chat_store.update(rec["id"], out, messages=longer,
                                now="2026-08-05T12:00:00")

    assert updated["messages"] == longer
    assert updated["updated_at"] == "2026-08-05T12:00:00"
    assert updated["created_at"] == "2026-08-05T10:00:00"   # ilk zaman korunur
    assert _read_raw(out)[0]["messages"] == longer


def test_update_can_rename_without_touching_messages(tmp_path):
    """Yeniden adlandırma gövdeyi göndermek zorunda olmamalı."""
    out = str(tmp_path / "output")
    rec = chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")

    updated = chat_store.update(rec["id"], out, title="yeni ad",
                                now="2026-08-05T12:00:00")

    assert updated["title"] == "yeni ad"
    assert updated["messages"] == THREAD


def test_update_returns_none_for_unknown_or_unsafe_id(tmp_path):
    out = str(tmp_path / "output")
    chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")

    assert chat_store.update("0123456789ab", out, title="x", now="n") is None
    assert chat_store.update("../x", out, title="x", now="n") is None


def test_update_does_not_write_when_nothing_changes(tmp_path):
    """Ne başlık ne gövde verilmediyse dosyaya dokunulmaz.

    Boş bir `PUT` "updated_at"i öne alıp sohbeti listenin başına taşırdı —
    kullanıcının yapmadığı bir iş, sıralamayı bozardı.
    """
    out = str(tmp_path / "output")
    rec = chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")

    assert chat_store.update(rec["id"], out, now="2026-08-05T12:00:00") == rec
    assert _read_raw(out)[0]["updated_at"] == "2026-08-05T10:00:00"


# ── Silme ───────────────────────────────────────────────────────────────

def test_delete_removes_only_the_named_chat(tmp_path):
    out = str(tmp_path / "output")
    keep = chat_store.create("kalan", THREAD, out, now="2026-08-05T10:00:00")
    doomed = chat_store.create("giden", THREAD, out, now="2026-08-05T11:00:00")

    assert chat_store.delete(doomed["id"], out) is True
    assert [c["id"] for c in _read_raw(out)] == [keep["id"]]


def test_delete_is_false_for_unknown_or_unsafe_id(tmp_path):
    out = str(tmp_path / "output")
    chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")

    assert chat_store.delete("0123456789ab", out) is False
    assert chat_store.delete("../../x", out) is False
    assert chat_store.delete("", out) is False


# ── Dayanıklılık (storage/folders/palette_store ile aynı duruş) ──────────

def test_corrupt_json_reads_as_empty_instead_of_crashing(tmp_path):
    out = str(tmp_path / "output")
    os.makedirs(out)
    with open(os.path.join(out, chat_store.CHATS_FILE), "w", encoding="utf-8") as f:
        f.write("{bu json değil")

    assert chat_store.list_chats(out) == []
    assert chat_store.get("0123456789ab", out) is None


def test_a_json_object_instead_of_a_list_reads_as_empty(tmp_path):
    out = str(tmp_path / "output")
    os.makedirs(out)
    with open(os.path.join(out, chat_store.CHATS_FILE), "w", encoding="utf-8") as f:
        json.dump({"neden": "yanlış şekil"}, f)

    assert chat_store.list_chats(out) == []


def test_write_is_atomic_and_leaves_no_temp_file(tmp_path):
    """`os.replace` deseni: yarı yazılmış bir chats.json kalmamalı."""
    out = str(tmp_path / "output")
    chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")

    assert os.listdir(out) == [chat_store.CHATS_FILE]


def test_turkish_characters_survive_the_round_trip(tmp_path):
    """`ensure_ascii=False`: başlıkta 'ş' kaçış dizisine dönüşmemeli."""
    out = str(tmp_path / "output")
    rec = chat_store.create("bağış kampanyası", THREAD, out, now="2026-08-05T10:00:00")

    with open(os.path.join(out, chat_store.CHATS_FILE), encoding="utf-8") as f:
        assert "bağış kampanyası" in f.read()
    assert chat_store.get(rec["id"], out)["title"] == "bağış kampanyası"
