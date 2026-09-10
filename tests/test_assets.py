import json

import pytest

import assets_store as astore


def test_save_writes_file_and_manifest(tmp_path):
    out = str(tmp_path)
    rec = astore.save_asset("logos", b"\x89PNG", "Logo Mavi", out,
                            now="2026-07-23T10:00:00")
    kind_dir = tmp_path / "logos"
    assert (kind_dir / rec["filename"]).read_bytes() == b"\x89PNG"
    assert rec["name"] == "Logo Mavi"
    assert rec["kind"] == "logos"
    assert rec["created_at"] == "2026-07-23T10:00:00"
    assert rec["id"] == rec["filename"].rsplit(".", 1)[0]
    manifest = json.loads((kind_dir / "index.json").read_text(encoding="utf-8"))
    assert manifest[0]["id"] == rec["id"]


def test_list_assets_newest_first(tmp_path):
    out = str(tmp_path)
    astore.save_asset("banners", b"a", "one", out, now="2026-07-23T10:00:00")
    astore.save_asset("banners", b"b", "two", out, now="2026-07-23T11:00:00")
    items = astore.list_assets("banners", out)
    assert [i["name"] for i in items] == ["two", "one"]


def test_list_assets_empty_when_no_dir(tmp_path):
    assert astore.list_assets("logos", str(tmp_path)) == []


def test_kinds_are_isolated(tmp_path):
    out = str(tmp_path)
    astore.save_asset("logos", b"L", "logo", out, now="2026-07-23T10:00:00")
    astore.save_asset("banners", b"B", "banner", out, now="2026-07-23T10:00:00")
    assert [i["name"] for i in astore.list_assets("logos", out)] == ["logo"]
    assert [i["name"] for i in astore.list_assets("banners", out)] == ["banner"]


def test_invalid_kind_rejected(tmp_path):
    with pytest.raises(ValueError):
        astore.save_asset("evil", b"x", "n", str(tmp_path), now="2026-07-23T10:00:00")
    with pytest.raises(ValueError):
        astore.list_assets("../secrets", str(tmp_path))


def test_asset_path_resolves_and_guards(tmp_path):
    out = str(tmp_path)
    rec = astore.save_asset("logos", b"\x89PNG", "x", out, now="2026-07-23T10:00:00")
    path = astore.asset_path("logos", rec["id"], out)
    assert path is not None and path.endswith(f"{rec['id']}.png")
    # unknown id and traversal attempts return None
    assert astore.asset_path("logos", "deadbeef", out) is None
    assert astore.asset_path("logos", "../../etc/passwd", out) is None


def test_delete_removes_file_and_manifest_entry(tmp_path):
    out = str(tmp_path)
    rec = astore.save_asset("logos", b"\x89PNG", "x", out, now="2026-07-23T10:00:00")
    assert astore.delete_asset("logos", rec["id"], out) is True
    assert not (tmp_path / "logos" / rec["filename"]).exists()
    assert astore.list_assets("logos", out) == []
    # deleting again is a no-op
    assert astore.delete_asset("logos", rec["id"], out) is False


def test_delete_rejects_bad_id(tmp_path):
    assert astore.delete_asset("logos", "../../etc/passwd", str(tmp_path)) is False


def test_manifest_tolerates_corrupt_file(tmp_path):
    kind_dir = tmp_path / "logos"
    kind_dir.mkdir()
    (kind_dir / "index.json").write_text("{not json", encoding="utf-8")
    assert astore.list_assets("logos", str(tmp_path)) == []


# ── Ölü `uploads` türünün göçü ──────────────────────────────────────
#
# Göç kullanıcı verisini YERİNDEN OYNATAN tek açılış adımı, o yüzden bekçileri
# yalnız "mutlu yol"u değil yarım kalmış koşuyu, çakışmayı ve öksüz kaydı da
# sayıyor: bir göçün asıl bedeli hata verdiğinde değil, SESSİZCE eksik
# çalıştığında ödenir.


def _eski_uploads(tmp_path, kayitlar, *, dosyalar=True):
    """Göç ÖNCESİ bir kurulumun `assets/uploads/` dizinini kurar."""
    d = tmp_path / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    for k in kayitlar:
        if dosyalar:
            (d / f"{k['id']}.png").write_bytes(b"PNG:" + k["id"].encode())
    (d / "index.json").write_text(json.dumps(kayitlar), encoding="utf-8")
    return d


def test_the_dead_kind_is_gone_from_the_public_kinds():
    assert "uploads" not in astore.KINDS
    assert astore.KINDS == ("logos", "banners", "mottos")


def test_legacy_uploads_move_to_logos_with_their_files(tmp_path):
    out = str(tmp_path)
    d = _eski_uploads(tmp_path, [
        {"id": "aaaaaaaa1111", "filename": "aaaaaaaa1111.png", "name": "Eski logo",
         "kind": "uploads", "created_at": "2026-01-01T10:00:00"},
    ])
    assert astore.migrate_legacy_uploads(out) == 1

    (kayit,) = astore.list_assets("logos", out)
    assert kayit["id"] == "aaaaaaaa1111"
    assert kayit["kind"] == "logos", "kayıt ölü türü taşımaya devam ediyor"
    assert kayit["name"] == "Eski logo"
    assert kayit["created_at"] == "2026-01-01T10:00:00", "geçmiş sırası bozuldu"
    assert (tmp_path / "logos" / "aaaaaaaa1111.png").read_bytes() == b"PNG:aaaaaaaa1111"
    assert not d.exists(), "boşalan ölü dizin bırakıldı"


def test_the_migration_is_a_noop_without_the_dead_directory(tmp_path):
    """Yeni kurulumun maliyeti tek bir `isdir` — ve hiçbir dizin yaratılmıyor."""
    assert astore.migrate_legacy_uploads(str(tmp_path)) == 0
    assert list(tmp_path.iterdir()) == []


def test_running_the_migration_twice_does_not_duplicate(tmp_path):
    out = str(tmp_path)
    _eski_uploads(tmp_path, [
        {"id": "bbbbbbbb2222", "filename": "bbbbbbbb2222.png", "name": "İki kez",
         "kind": "uploads", "created_at": "2026-01-01T10:00:00"},
    ])
    assert astore.migrate_legacy_uploads(out) == 1
    assert astore.migrate_legacy_uploads(out) == 0
    assert len(astore.list_assets("logos", out)) == 1


def test_a_half_finished_migration_is_completed_on_the_next_run(tmp_path):
    """Dosya taşındı, manifest yazılamadan çökdü: kayıt İKİNCİ koşuda yazılıyor.

    Sıra bilerek böyle (önce dosya, sonra manifest): ters sırada aynı çökme
    kullanıcıya kütüphanede KIRIK bir karo bırakırdı. Burada bıraktığı şey
    yalnız listelenmeyen bir dosya ve o kurtarılabilir — bu test tam olarak o
    kurtarmayı ölçüyor.
    """
    out = str(tmp_path)
    _eski_uploads(tmp_path, [
        {"id": "cccccccc3333", "filename": "cccccccc3333.png", "name": "Yarım",
         "kind": "uploads", "created_at": "2026-01-01T10:00:00"},
    ], dosyalar=False)
    (tmp_path / "logos").mkdir()
    (tmp_path / "logos" / "cccccccc3333.png").write_bytes(b"tasinmisti")

    assert astore.migrate_legacy_uploads(out) == 1
    (kayit,) = astore.list_assets("logos", out)
    assert kayit["id"] == "cccccccc3333"


def test_an_id_collision_does_not_hide_the_existing_logo(tmp_path):
    """Aynı id hedefte zaten varsa eski logo listeden DÜŞMÜYOR; göçen yeni id alıyor."""
    out = str(tmp_path)
    duran = astore.save_asset("logos", b"DURAN", "Duran logo", out,
                              now="2026-01-01T09:00:00")
    _eski_uploads(tmp_path, [
        {"id": duran["id"], "filename": duran["filename"], "name": "Çakışan",
         "kind": "uploads", "created_at": "2026-01-01T10:00:00"},
    ])

    assert astore.migrate_legacy_uploads(out) == 1
    kayitlar = astore.list_assets("logos", out)
    assert len(kayitlar) == 2, "çakışma bir varlığı yuttu"
    adlar = {k["name"] for k in kayitlar}
    assert adlar == {"Duran logo", "Çakışan"}
    idler = {k["id"] for k in kayitlar}
    assert len(idler) == 2, "iki kayıt aynı id'yi taşıyor"
    # Duran logonun dosyası da yerinde: göç onun üzerine YAZMADI.
    assert (tmp_path / "logos" / duran["filename"]).read_bytes() == b"DURAN"
    for k in kayitlar:
        assert (tmp_path / "logos" / k["filename"]).exists()


def test_an_orphan_record_without_a_file_is_dropped(tmp_path):
    """Dosyası olmayan kayıt taşınmıyor: kırık bir karo göç ettirmenin anlamı yok."""
    out = str(tmp_path)
    _eski_uploads(tmp_path, [
        {"id": "dddddddd4444", "filename": "dddddddd4444.png", "name": "Öksüz",
         "kind": "uploads", "created_at": "2026-01-01T10:00:00"},
    ], dosyalar=False)
    assert astore.migrate_legacy_uploads(out) == 0
    assert astore.list_assets("logos", out) == []


def test_a_file_the_app_never_listed_is_not_deleted(tmp_path):
    """Manifest'te kaydı olmayan dosya SİLİNMİYOR — ölü dizin yerinde kalıyor.

    Kullanıcının (ya da bir yedekleme aracının) oraya koyduğu bir dosyayı
    sessizce silmektense okunmayan bir dizin bırakmak yeğdir.
    """
    out = str(tmp_path)
    d = _eski_uploads(tmp_path, [])
    (d / "elle-konmus.png").write_bytes(b"KULLANICININ")

    assert astore.migrate_legacy_uploads(out) == 0
    assert (d / "elle-konmus.png").read_bytes() == b"KULLANICININ"
    assert not (d / "index.json").exists(), "boşalan manifest bırakıldı"
