"""errlog: paketlenmiş uygulamanın tek teşhis çıkışı.

Kullanıcıya stderr hiç görünmediği için bu dosya silinmeden birikir; her
başarısız açılış tam bir traceback ekler. Bu yüzden büyümesi sınırlı olmalı ve
loglamanın kendisi asla asıl uyarının önüne geçmemeli.
"""
import os

import errlog


def test_append_writes_timestamped_text(tmp_path):
    path = errlog.append(str(tmp_path), "ilk hata")

    assert path == str(tmp_path / "hata.log")
    body = (tmp_path / "hata.log").read_text(encoding="utf-8")
    assert "ilk hata" in body
    assert "---" in body  # zaman damgası ayracı


def test_append_creates_a_missing_directory(tmp_path):
    target = tmp_path / "yok" / "bu-da-yok"

    errlog.append(str(target), "hata")

    assert (target / "hata.log").is_file()


def test_safe_append_never_raises_but_still_returns_the_path(tmp_path):
    """data_dir bir dosyaysa makedirs patlar; safe_append yine de yol döndürmeli.

    Çağıran bu yolu kullanıcıya gösterdiği uyarıya koyuyor — loglama hatası o
    uyarıyı engellememeli (bkz. desktop.main).
    """
    not_a_dir = tmp_path / "dizin-degil"
    not_a_dir.write_text("ben bir dosyayım", encoding="utf-8")

    path = errlog.safe_append(str(not_a_dir), "hata")

    assert path == str(not_a_dir / "hata.log")
    assert not_a_dir.is_file()  # dokunulmadı


def test_log_rotates_when_it_grows_past_the_cap(tmp_path):
    path = errlog.log_path(str(tmp_path))
    with open(path, "w", encoding="utf-8") as f:
        f.write("e" * (errlog.MAX_LOG_BYTES + 1))

    errlog.append(str(tmp_path), "yeni hata")

    assert os.path.isfile(path + ".1")  # önceki içerik kaybolmaz
    body = (tmp_path / "hata.log").read_text(encoding="utf-8")
    assert "yeni hata" in body
    assert len(body) < errlog.MAX_LOG_BYTES  # yeni dosya baştan başlar


def test_log_under_the_cap_is_not_rotated(tmp_path):
    errlog.append(str(tmp_path), "birinci")
    errlog.append(str(tmp_path), "ikinci")

    body = (tmp_path / "hata.log").read_text(encoding="utf-8")
    assert "birinci" in body and "ikinci" in body
    assert not os.path.exists(errlog.log_path(str(tmp_path)) + ".1")


def test_rotation_keeps_exactly_one_previous_file(tmp_path):
    """İkinci döndürme .1'i ezer — .2, .3 birikmez (disk sınırsız dolmasın)."""
    path = errlog.log_path(str(tmp_path))

    for marker in ("eski", "yeni"):
        with open(path, "w", encoding="utf-8") as f:
            f.write(marker + "e" * errlog.MAX_LOG_BYTES)
        errlog.append(str(tmp_path), "tetikleyici")

    assert not os.path.exists(path + ".2")
    assert open(path + ".1", encoding="utf-8").read().startswith("yeni")
