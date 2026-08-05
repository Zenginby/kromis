"""Beş manifest deposunun paylaştığı yazım mekaniği.

Buradaki iki şey, önceden beş dosyada kopyalanmış olduğu için beş kez
test edilemiyordu: geçici dosyanın İSTİSNADA da silinmesi ve dosya başına
yazma kilidi.
"""
import json
import os
import threading

import pytest

import jsonstore


def test_write_atomic_writes_utf8_json_and_leaves_no_temp_file(tmp_path):
    path = str(tmp_path / "manifest.json")

    jsonstore.write_atomic(path, [{"name": "Bağış görselleri"}])

    with open(path, encoding="utf-8") as f:
        assert json.load(f) == [{"name": "Bağış görselleri"}]
    # `ensure_ascii=False`: Türkçe karakter kaçış dizisi değil, kendisi.
    with open(path, encoding="utf-8") as f:
        assert "Bağış" in f.read()
    assert [p for p in os.listdir(tmp_path) if p.endswith(".tmp")] == []


def test_a_failed_write_leaves_neither_a_temp_file_nor_a_half_file(tmp_path, monkeypatch):
    """Eskiden `os.replace`e hiç gelinmiyordu ve `*.tmp` çöpü kullanıcının
    Finder'da gördüğü klasörde kalıyordu. Mevcut dosya da bozulmamalı."""
    path = str(tmp_path / "manifest.json")
    jsonstore.write_atomic(path, [{"id": "eski"}])

    def boom(*args, **kwargs):
        raise OSError("disk dolu")
    monkeypatch.setattr(jsonstore.json, "dump", boom)

    with pytest.raises(OSError):
        jsonstore.write_atomic(path, [{"id": "yeni"}])

    assert [p for p in os.listdir(tmp_path) if p.endswith(".tmp")] == []
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == [{"id": "eski"}]      # eski sürüm sağlam


def test_write_text_uses_the_same_mechanic(tmp_path):
    """Yedek damgası JSON değil ama aynı atomikliği ve aynı temizliği istiyor."""
    path = str(tmp_path / ".last-version")

    jsonstore.write_text(path, "1.15.0")

    with open(path, encoding="utf-8") as f:
        assert f.read() == "1.15.0"
    assert [p for p in os.listdir(tmp_path) if p.endswith(".tmp")] == []


def test_lock_is_per_file(tmp_path):
    """Aynı yol → aynı kilit; başka dosya → başka kilit (iki manifest birbirini
    beklemesin). Yol `abspath` ile normalleniyor."""
    a = str(tmp_path / "a.json")
    b = str(tmp_path / "b.json")

    assert jsonstore.lock_for(a) is jsonstore.lock_for(a)
    assert jsonstore.lock_for(a) is not jsonstore.lock_for(b)
    assert jsonstore.lock_for(a) is jsonstore.lock_for(os.path.join(str(tmp_path), ".", "a.json"))


def test_the_lock_is_reentrant(tmp_path):
    """Depo fonksiyonları birbirini çağırıyor (`storage.unfile_folder` →
    `unfile_folders`); düz bir `Lock` aynı iş parçacığında kilitlenirdi."""
    lock = jsonstore.lock_for(str(tmp_path / "a.json"))

    with lock:
        with lock:                      # düz Lock burada sonsuza beklerdi
            pass


def test_the_lock_actually_serializes_two_threads(tmp_path):
    order = []
    lock = jsonstore.lock_for(str(tmp_path / "a.json"))
    entered = threading.Event()

    def slow():
        with lock:
            order.append("başladı")
            entered.set()
            threading.Event().wait(0.05)
            order.append("bitti")

    def fast():
        entered.wait(1)
        with lock:
            order.append("ikinci")

    threads = [threading.Thread(target=slow), threading.Thread(target=fast)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(2)

    assert order == ["başladı", "bitti", "ikinci"]
