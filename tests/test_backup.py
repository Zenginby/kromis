"""Sürüm değişiminde manifest yedeği (backup.py).

Bu dosya tests/conftest.py'deki yedek guard'ından MUAF (bkz. o dosyanın
docstring'i): gerçek fonksiyonu çalıştırması gerekiyor. Bu yüzden lifespan
testleri `paths.data_dir`'i tmp_path'e yönlendirmek ZORUNDA — yoksa
geliştiricinin repo köküne yedek ve damga yazılır.

FİXTURE AYRIMI KASITLI: bu dosya tests/fixtures/v18/ ağacını genel girdi olarak
KULLANMAZ. backup.py hiç ayrıştırma yapmadığı için testleri yalnızca *bazı
baytlara* ihtiyaç duyuyor, ve bir test bilerek JSON OLMAYAN çöp kullanıp
bayt-özdeşlik iddia ediyor — iyi biçimli fixture üzerinde koşarsa o test bir
yalan olur. Ayrım hijyen değil semantik: burada mesele BAYT düzeyi,
tests/test_legacy_formats.py'de ŞEMA düzeyi. Tek kasıtlı temas noktası
`test_a_realistic_v18_tree_is_backed_up_byte_for_byte`.

Her test SABİT `now` ile: hiçbir dizin adı bugünün tarihine bağlı olmasın.
"""
import json
import os
import shutil
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app as appmod
import assets_store
import backup
import version

NOW = "2026-07-30T12:00:00"
FIXTURES_V18 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "fixtures", "v18")


def _dirs(tmp_path):
    """(data_dir, output_dir, assets_dir) — gerçek yerleşimi aynalar."""
    return str(tmp_path), str(tmp_path / "output"), str(tmp_path / "assets")


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _seed_library(tmp_path, *, history='[{"id": "aaaaaaaaaaaa"}]'):
    """Bütün manifest'leri yazar (içerik önemsiz — backup ayrıştırmıyor)."""
    _, output_dir, assets_dir = _dirs(tmp_path)
    _write(os.path.join(output_dir, "history.json"), history)
    _write(os.path.join(output_dir, "folders.json"), '[{"id": "bbbbbbbbbbbb"}]')
    _write(os.path.join(output_dir, "palettes.json"), '[{"id": "cccccccccccc"}]')
    _write(os.path.join(output_dir, "chats.json"), '[{"id": "dddddddddddd"}]')
    for kind in assets_store.KINDS:
        _write(os.path.join(assets_dir, kind, "index.json"), f'[{{"kind": "{kind}"}}]')


# ── birim: yükseltme yolu ─────────────────────────────────────────────────

def test_upgrade_copies_every_manifest_byte_for_byte(tmp_path):
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    _seed_library(tmp_path)
    backup.write_stamp(data_dir, "1.8.0")

    dest = backup.backup_manifests_if_version_changed(
        data_dir, output_dir, assets_dir, version="1.9.0", now=NOW)

    assert dest == os.path.join(data_dir, "backups", "1.8.0-2026-07-30")
    for rel, source in (("output/history.json", os.path.join(output_dir, "history.json")),
                        ("output/folders.json", os.path.join(output_dir, "folders.json")),
                        ("output/palettes.json", os.path.join(output_dir, "palettes.json")),
                        # v1.15: sohbetler. İçindeki prompt'lar başka hiçbir yerde
                        # durmuyor — bu manifest yedeklenmezse yükseltmede tek
                        # kopyaları risk altında olurdu.
                        ("output/chats.json", os.path.join(output_dir, "chats.json"))):
        with open(os.path.join(dest, *rel.split("/")), "rb") as a, open(source, "rb") as b:
            assert a.read() == b.read(), rel
    for kind in assets_store.KINDS:
        assert os.path.isfile(os.path.join(dest, "assets", kind, "index.json")), kind


def test_stamp_is_updated_after_a_successful_backup(tmp_path):
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    _seed_library(tmp_path)
    backup.write_stamp(data_dir, "1.8.0")
    backup.backup_manifests_if_version_changed(
        data_dir, output_dir, assets_dir, version="1.9.0", now=NOW)
    assert backup.read_stamp(data_dir) == "1.9.0"


def test_second_launch_with_the_same_version_is_a_no_op(tmp_path):
    """Damga çalışmazsa her açılış bir yedek daha üretir."""
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    _seed_library(tmp_path)
    backup.write_stamp(data_dir, "1.9.0")
    assert backup.backup_manifests_if_version_changed(
        data_dir, output_dir, assets_dir, version="1.9.0", now=NOW) is None
    assert not os.path.exists(backup.backups_root(data_dir))


def test_fresh_install_stamps_without_creating_a_backup_dir(tmp_path):
    """seed.py'nin "kopyalamadan damgala" mantığının aynısı.

    Taze bir makinede kullanıcının hiç verisi yok; boş bir backups/ dizini
    açmak anlamsız olurdu (ve kullanıcıya "bir şey yedeklendi" diye yalan söyler).
    """
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    assert backup.backup_manifests_if_version_changed(
        data_dir, output_dir, assets_dir, version="1.9.0", now=NOW) is None
    assert backup.read_stamp(data_dir) == "1.9.0"
    assert not os.path.exists(backup.backups_root(data_dir))


def test_missing_stamp_with_data_is_treated_as_an_unknown_upgrade(tmp_path):
    """v1.8 hiç damga yazmadı → v1.9'un İLK açılışı bu daldan geçecek.

    Özelliğin alacağı en değerli yedek bu: format değişikliğinin inebileceği
    geçiş tam olarak v1.8→v1.9.
    """
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    _seed_library(tmp_path)
    dest = backup.backup_manifests_if_version_changed(
        data_dir, output_dir, assets_dir, version="1.9.0", now=NOW)
    assert os.path.basename(dest) == "bilinmeyen-2026-07-30"


def test_non_json_garbage_is_copied_verbatim(tmp_path):
    """backup.py PARSER'SIZ olmak zorunda — kanıtı bu test.

    Bütün amaç dosyanın mevcut sürümce OKUNAMADIĞI durumu atlatmak; yedek
    yoluna bir json.load koymak, hedge ettiği hatayı miras almak olurdu.
    """
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    garbage = '{"yarım kalmış'
    _seed_library(tmp_path, history=garbage)
    backup.write_stamp(data_dir, "1.8.0")
    dest = backup.backup_manifests_if_version_changed(
        data_dir, output_dir, assets_dir, version="1.9.0", now=NOW)
    with open(os.path.join(dest, "output", "history.json"), encoding="utf-8") as f:
        assert f.read() == garbage
    with pytest.raises(json.JSONDecodeError):
        json.loads(garbage)  # gerçekten geçersiz olduğunu göster


def test_partial_library_creates_no_empty_directories(tmp_path):
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    _write(os.path.join(output_dir, "history.json"), "[]")
    backup.write_stamp(data_dir, "1.8.0")
    dest = backup.backup_manifests_if_version_changed(
        data_dir, output_dir, assets_dir, version="1.9.0", now=NOW)
    assert os.listdir(dest) == ["output"]
    assert os.listdir(os.path.join(dest, "output")) == ["history.json"]


def test_images_are_not_copied(tmp_path):
    """Görseller asıl hacim ve zaten yerlerinde; yedek birkaç KB kalmalı."""
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    _seed_library(tmp_path)
    _write(os.path.join(output_dir, "aaaaaaaaaaaa.png"), "PNGDEĞİL")
    backup.write_stamp(data_dir, "1.8.0")
    dest = backup.backup_manifests_if_version_changed(
        data_dir, output_dir, assets_dir, version="1.9.0", now=NOW)
    copied = [f for _r, _d, files in os.walk(dest) for f in files]
    assert not any(f.endswith(".png") for f in copied), copied


def test_an_unreadable_stamp_is_treated_as_unknown_not_fatal(tmp_path):
    """Damganın yerinde bir DİZİN varsa okuma OSError verir — ölümcül olmamalı."""
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    _seed_library(tmp_path)
    os.makedirs(backup.stamp_path(data_dir))
    assert backup.read_stamp(data_dir) is None


def test_same_day_retry_keeps_the_existing_backup(tmp_path):
    """Damgası düşmüş aynı-gün yeniden denemesi mevcut yedeği EZMEMELİ.

    Daha eski kopya hataya daha yakın hâli taşıyor.
    """
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    _seed_library(tmp_path, history='["ilk"]')
    backup.write_stamp(data_dir, "1.8.0")
    dest = backup.backup_manifests_if_version_changed(
        data_dir, output_dir, assets_dir, version="1.9.0", now=NOW)

    # damgayı geri al ve manifest'i değiştir → aynı ad yeniden hedeflenecek
    backup.write_stamp(data_dir, "1.8.0")
    _write(os.path.join(output_dir, "history.json"), '["sonra"]')
    again = backup.backup_manifests_if_version_changed(
        data_dir, output_dir, assets_dir, version="1.9.0", now=NOW)

    assert again == dest
    with open(os.path.join(dest, "output", "history.json"), encoding="utf-8") as f:
        assert f.read() == '["ilk"]'
    # sahneleme dizini arkada bırakılmadı
    assert os.listdir(backup.backups_root(data_dir)) == ["1.8.0-2026-07-30"]


def test_backups_accumulate_and_nothing_is_deleted(tmp_path):
    """RETENTION BİLEREK YOK: silme, kullanıcının veri dizininden dizin kaldıran
    tek kod olurdu ve arıza modu tam olarak bu özelliğin korumak için var
    olduğu şeyi yok etmek. Yedek başına birkaç KB.

    Aynı zamanda ADLANDIRMA değişmezini kilitliyor: dizin ESKİ (giden) sürümle
    adlandırılıyor, yenisiyle değil — o klasördeki baytları o sürüm yazdı ve
    geri yüklerken sorulan tek soru bu. 1.9.1 → 1.10.0 yükseltmesi
    "1.9.1-<tarih>" bırakır, "1.10.0-<tarih>" DEĞİL.
    """
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    _seed_library(tmp_path)
    for old, new, day in (("1.8.0", "1.9.0", "2026-07-30"),
                          ("1.9.0", "1.9.1", "2026-08-01"),
                          ("1.9.1", "1.10.0", "2026-09-15")):
        backup.write_stamp(data_dir, old)
        backup.backup_manifests_if_version_changed(
            data_dir, output_dir, assets_dir, version=new, now=f"{day}T00:00:00")
    assert sorted(os.listdir(backup.backups_root(data_dir))) == [
        "1.8.0-2026-07-30", "1.9.0-2026-08-01", "1.9.1-2026-09-15"]


def test_an_unparseable_directory_name_is_never_created(tmp_path):
    """Üretilen ad kendi desenine uymuyorsa hiç dizin açılmamalı.

    Ayrıştırılamayan bir ad, sonradan hiçbir aracın tanıyamayacağı bir dizin
    bırakmak olurdu.
    """
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    _seed_library(tmp_path)
    backup.write_stamp(data_dir, "../kaçış")
    with pytest.raises(ValueError):
        backup.backup_manifests_if_version_changed(
            data_dir, output_dir, assets_dir, version="1.9.0", now=NOW)
    assert not os.path.exists(backup.backups_root(data_dir))


def test_a_realistic_v18_tree_is_backed_up_byte_for_byte(tmp_path):
    """tests/fixtures/v18/ ile TEK kasıtlı temas noktası — BAYT düzeyinde.

    Alanlar üzerine hiçbir iddia yok (o tests/test_legacy_formats.py'nin işi):
    burada sorulan tek şey "gerçekçi bir v1.8 veri dizini sadakatle kopyalanıyor
    mu".
    """
    data_dir, output_dir, assets_dir = _dirs(tmp_path)
    shutil.copytree(FIXTURES_V18, tmp_path, dirs_exist_ok=True)
    dest = backup.backup_manifests_if_version_changed(
        data_dir, output_dir, assets_dir, version="1.9.0", now=NOW)
    for rel in ("output/history.json", "output/folders.json", "output/palettes.json",
                "assets/logos/index.json", "assets/banners/index.json",
                "assets/mottos/index.json"):
        parts = rel.split("/")
        with open(os.path.join(dest, *parts), "rb") as a, \
             open(os.path.join(str(tmp_path), *parts), "rb") as b:
            assert a.read() == b.read(), rel


# ── lifespan: bağlantı, sıra, hata izolasyonu ─────────────────────────────

def _isolate_lifespan(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(appmod.paths, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(appmod.paths, "ensure_data_dirs", lambda: None)
    assert str(tmp_path) not in ("", "/"), "izolasyon kurulmadı"


def test_backup_does_not_fire_on_plain_import(monkeypatch, tmp_path):
    """`import app` ve çıplak TestClient yan etkisiz kalmalı (I3 sözleşmesi)."""
    _isolate_lifespan(monkeypatch, tmp_path)
    recorder = MagicMock()
    monkeypatch.setattr(appmod.backup, "backup_manifests_if_version_changed", recorder)
    TestClient(appmod.app)
    recorder.assert_not_called()


def test_backup_fires_once_on_lifespan_startup(monkeypatch, tmp_path):
    _isolate_lifespan(monkeypatch, tmp_path)
    recorder = MagicMock(return_value=None)
    monkeypatch.setattr(appmod.backup, "backup_manifests_if_version_changed", recorder)
    with TestClient(appmod.app):
        recorder.assert_called_once()
    args, kwargs = recorder.call_args
    assert args == (str(tmp_path), appmod.OUTPUT_DIR, appmod.ASSETS_DIR)
    assert kwargs["version"] == version.APP_VERSION
    assert kwargs["now"]


def test_backup_runs_before_seeding(monkeypatch, tmp_path):
    """SIRA YÜK TAŞIYOR: seed assets/logos/index.json YAZIYOR.

    Tohumlama önce koşsa taze bir makinede yedek "kullanıcının verisi var" diye
    taze tohum verisinin işe yaramaz yedeğini alırdı. Yükseltmede sıra fark
    etmez (seed marker yüzünden no-op) — yani bu hata YALNIZCA taze kurulumda,
    yani ofiste görünürdü, asla geliştirmede. Bu yüzden yorum değil test.
    """
    _isolate_lifespan(monkeypatch, tmp_path)
    order = []
    monkeypatch.setattr(appmod.backup, "backup_manifests_if_version_changed",
                        lambda *a, **k: order.append("backup"))
    monkeypatch.setattr(appmod.seed, "seed_builtin_logos",
                        lambda *a, **k: order.append("seed") or [])
    with TestClient(appmod.app):
        pass
    assert order == ["backup", "seed"]


def test_lifespan_survives_a_backup_error_and_still_seeds(monkeypatch, tmp_path):
    """Yedek bir EMNİYET özelliği — patlaması uygulamayı KİLİTLEMEMELİ.

    Yedek yüzünden uygulamaya giremeyen kullanıcının verisine arayüzden hiçbir
    yolu kalmaz; bu, loglanmış-ama-alınmamış bir yedekten kesinlikle kötüdür.
    Ayrı guard'lar sayesinde tohumlama da yedek hatasından etkilenmiyor.
    """
    _isolate_lifespan(monkeypatch, tmp_path)
    seeded = []

    def boom(*args, **kwargs):
        raise OSError("disk dolu (simüle)")

    monkeypatch.setattr(appmod.backup, "backup_manifests_if_version_changed", boom)
    monkeypatch.setattr(appmod.seed, "seed_builtin_logos",
                        lambda *a, **k: seeded.append(True) or [])

    with TestClient(appmod.app) as client:
        assert client.get("/api/settings").status_code == 200

    assert seeded, "yedek hatası tohumlamayı da düşürmüş"
    log = tmp_path / "hata.log"
    assert log.is_file()
    assert "disk dolu" in log.read_text(encoding="utf-8")


def test_app_calls_backup_through_the_module_attribute(monkeypatch, tmp_path):
    """`from backup import ...` conftest guard'ını sessizce devre dışı bırakır.

    Guard çağrı anında modül attribute'una bakıyor; app.py bir yerel isme
    bağlarsa her test koşusu geliştiricinin repo köküne yedek yazabilir hale
    gelir. Bu yüzden import biçimi de sözleşmenin parçası.
    """
    assert appmod.backup is backup
