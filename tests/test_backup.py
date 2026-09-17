"""Sürüm değişiminde manifest yedeği (backup.py).

DONDURULMUŞ KABUK (Faz 1 / 6): web yolu bu modülü artık çağırmıyor — manifest
kalmadı, veri DB'de. Birim testleri masaüstü paketinin yedeği için duruyor;
lifespan bağını ölçen testler en altta yeni sözleşmeye döndü (ithal YOK).

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
import pathlib
import shutil

import pytest
from fastapi.testclient import TestClient

import app as appmod
import assets_store
import backup

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
    """"Kopyalamadan damgala": taze bir makinede kullanıcının hiç verisi yok; boş bir backups/ dizini
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


# ── lifespan: yedek ARTIK ÇAĞRILMIYOR (Faz 1 / 6) ─────────────────────────
#
# Bu bölüm dört testle lifespan'ın yedeği tam bir kez, modül niteliği üzerinden
# çağırdığını ve hatasını yuttuğunu ölçüyordu. Manifestler DB'ye taşındı
# (docs/faz1-veritabani-hesaplar.md §6): yedeklenecek dosya kalmadı, DB yedeği
# platformun işi (9. görev). Yukarıdaki birim testleri dondurulmuş masaüstü
# kabuğu için duruyor; buradaki iki test yeni sözleşmeyi tutuyor — `app.py`
# `backup`ı hiç ithal etmez ve açılış adımı patlasa da uygulama açılır.

def _isolate_lifespan(monkeypatch, tmp_path, dizinler):
    # Üç dizin de ayar nesnesinden (Faz 0 / Adım 4): lifespan `paths.data_dir()`
    # okumuyor, `app.state.ayarlar.data_dir` okuyor — yama oraya.
    dizinler(data_dir=str(tmp_path), output_dir=str(tmp_path / "output"),
             assets_dir=str(tmp_path / "assets"))
    assert str(tmp_path) not in ("", "/"), "izolasyon kurulmadı"


def test_the_app_no_longer_imports_or_calls_the_backup_module():
    """Web yolunda `backup` YOK: ne ithal ne çağrı (AST — yorumlar adı anabilir).

    conftest'in eski `_guard_against_real_backups` fixture'ı bu yüzden kalktı:
    yamalanacak bir çağrı kalmadı. Bir gün geri gelirse önce o guard geri gelmeli
    (geliştiricinin repo köküne yedek yazma sızıntısı, conftest başlığı).
    """
    import ast
    kaynak = (pathlib.Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    for dugum in ast.walk(ast.parse(kaynak)):
        if isinstance(dugum, ast.Import):
            assert all(a.name != "backup" for a in dugum.names), "app.py `backup` ithal ediyor"
        if isinstance(dugum, ast.ImportFrom):
            assert dugum.module != "backup", "app.py `from backup import …` yapıyor"
    assert not hasattr(appmod, "backup") and "backup" not in appmod.__all__


def test_lifespan_survives_a_startup_error(monkeypatch, tmp_path, dizinler):
    """Açılış adımı patlasa da uygulama AÇILIR, hata `hata.log`a düşer.

    Eskiden yedeğin hatasıyla ölçülüyordu; adım gitti, guard'ın gerekçesi
    kalıyor: guard olmadan uvicorn'un startup()'ı hiç bitmez ve kullanıcı boş
    bir pencere görür. Kalan tek adım `paths.ensure_data_dirs` — onu patlatıyoruz.
    """
    _isolate_lifespan(monkeypatch, tmp_path, dizinler)

    def boom(*args, **kwargs):
        raise OSError("disk dolu (simüle)")

    monkeypatch.setattr(appmod.paths, "ensure_data_dirs", boom)

    with TestClient(appmod.app) as client:
        assert client.get("/health").status_code in (200, 503)

    log = tmp_path / "hata.log"
    assert log.is_file()
    assert "disk dolu" in log.read_text(encoding="utf-8")
