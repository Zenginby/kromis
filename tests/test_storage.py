import json
import storage


def test_save_writes_file_and_appends_history(tmp_path):
    out = str(tmp_path)
    rec = storage.save(b"\x89PNG", {"prompt": "cat", "size": "1024x1024",
                                    "quality": "medium", "parent_id": None},
                       out, now="2026-07-23T10:00:00")
    assert (tmp_path / rec["filename"]).read_bytes() == b"\x89PNG"
    assert rec["prompt"] == "cat"
    assert rec["created_at"] == "2026-07-23T10:00:00"
    assert rec["id"] == rec["filename"].rsplit(".", 1)[0]
    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert history[0]["id"] == rec["id"]


def test_list_history_newest_first(tmp_path):
    out = str(tmp_path)
    storage.save(b"a", {"prompt": "1", "size": "1024x1024", "quality": "low",
                        "parent_id": None}, out, now="2026-07-23T10:00:00")
    storage.save(b"b", {"prompt": "2", "size": "1024x1024", "quality": "low",
                        "parent_id": None}, out, now="2026-07-23T11:00:00")
    hist = storage.list_history(out)
    assert [h["prompt"] for h in hist] == ["2", "1"]


def test_list_history_empty_when_no_file(tmp_path):
    assert storage.list_history(str(tmp_path)) == []


def test_list_history_tolerates_corrupt_file(tmp_path):
    (tmp_path / "history.json").write_text("{not json", encoding="utf-8")
    assert storage.list_history(str(tmp_path)) == []


def test_save_produces_valid_json_after_multiple_writes(tmp_path):
    out = str(tmp_path)
    storage.save(b"a", {"prompt": "1", "size": "1024x1024", "quality": "low",
                        "parent_id": None}, out, now="2026-07-23T10:00:00")
    storage.save(b"b", {"prompt": "2", "size": "1024x1024", "quality": "low",
                        "parent_id": None}, out, now="2026-07-23T11:00:00")
    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert isinstance(history, list)
    assert len(history) == 2


def test_generated_record_has_no_imported_key(tmp_path):
    """İçe aktarma işareti üretilen kayıtlara SIZMAMALI.

    Alan koşullu yazılıyor (`imported` yalnızca True iken). Koşul düşerse
    üretilen her kayda `"imported": false` girer: history.json'daki bütün
    kayıtlar değişir, "içe aktarıldı" işaretini `rec.imported` ile arayan
    arayüz de yanlış yerde false/true ayrımı yapmaya başlar.
    """
    rec = storage.save(b"\x89PNG", {"prompt": "cat", "size": "1024x1024",
                                    "quality": "low", "parent_id": None},
                       str(tmp_path), now="2026-08-04T10:00:00")
    assert "imported" not in rec
    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert "imported" not in history[0]


def test_imported_flag_is_written_when_asked(tmp_path):
    rec = storage.save(b"\x89PNG", {"prompt": "kedi.png", "size": "48x24",
                                    "quality": "", "parent_id": None,
                                    "imported": True},
                       str(tmp_path), now="2026-08-04T10:00:00")
    assert rec["imported"] is True
    assert json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))[0]["imported"] is True


# ── v2.0: oturum etiketi (birleşik döküm) ───────────────────────────────

def test_record_made_outside_a_session_has_no_session_id_key(tmp_path):
    """`imported` ile BİREBİR aynı koşullu desen — ve aynı gerekçe.

    Koşul düşerse bugün üretilen her kayda `"session_id": null` girer:
    history.json'ın TAMAMI değişir (eski-biçim testleri ve galeri buna bağlı) ve
    "bu görsel bir oturumdan mı doğdu?" sorusunu `.session_id` ile soran arayüz
    null ile yok arasında gereksiz bir ayrım yapmaya başlar. Oturumsuz üretim
    (Medya'dan doğrudan, ya da otomatik kayıt kapalıyken) kalıcı bir hâl —
    geçici bir durum değil.
    """
    rec = storage.save(b"\x89PNG", {"prompt": "cat", "size": "1024x1024",
                                    "quality": "low", "parent_id": None},
                       str(tmp_path), now="2026-08-07T10:00:00")

    assert "session_id" not in rec
    assert "session_id" not in json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))[0]


def test_session_id_is_written_when_the_image_is_born_in_a_session(tmp_path):
    """Oturum id'si `chats.json`'ın MEVCUT `id`'si — yeni bir kimlik uzayı yok."""
    rec = storage.save(b"\x89PNG", {"prompt": "cat", "size": "1024x1024",
                                    "quality": "low", "parent_id": None,
                                    "session_id": "beef1234beef"},
                       str(tmp_path), now="2026-08-07T10:00:00")

    assert rec["session_id"] == "beef1234beef"
    raw = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert raw[0]["session_id"] == "beef1234beef"


def test_kayit_ureten_modeli_ve_kredi_maliyetini_tasiyor(tmp_path):
    """`imported`/`session_id`'nin KOŞULLU deseni burada BİLEREK kullanılmıyor.

    Ayrım şu: o iki alan gerçek bir YOKLUK hâlini anlatıyor (kayıt içe
    aktarılmadıysa `imported` hiç olmaz, oturum dışı üretimin `session_id`'si
    hiç olmaz). Model ise HER üretilen kayıtta vardır; alanın yokluğu ancak
    "o günün varsayılanı" demek olurdu ve varsayılan DEĞİŞECEK.
    """
    rec = storage.save(b"x", {"prompt": "k", "size": "1024x1024", "quality": "low",
                              "parent_id": None, "model": "azure-gpt-image-2",
                              "credits": 7},
                       str(tmp_path), now="2026-01-01T00:00:00")

    assert rec["model"] == "azure-gpt-image-2"
    assert rec["credits"] == 7
    diskte = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))[0]
    assert diskte["model"] == "azure-gpt-image-2"
    assert diskte["credits"] == 7


def test_model_verilmezse_varsayilana_dusuyor(tmp_path):
    """Doğrudan `storage.save` çağıran (rota olmayan) yollar da kayıt bırakabiliyor."""
    import catalog

    rec = storage.save(b"x", {"prompt": "k", "size": "1024x1024", "quality": "low",
                              "parent_id": None},
                       str(tmp_path), now="2026-01-01T00:00:00")

    assert rec["model"] == catalog.DEFAULT_IMAGE_MODEL
    assert rec["credits"] == 0


def test_ESKI_kayitlar_model_alani_olmadan_da_okunuyor(tmp_path):
    """Göç YOK: eski `history.json` dokunulmadan kalıyor.

    Okuyan taraf `.get("model") or DEFAULT` diyor — folder_id/palette ile aynı
    "yokluğun tanımlı anlamı var" disiplini.
    """
    eski = [{"id": "aaaa1111aaaa", "filename": "aaaa1111aaaa.png", "prompt": "k",
             "size": "1024x1024", "quality": "low", "created_at": "2026-01-01",
             "parent_id": None}]
    (tmp_path / "history.json").write_text(json.dumps(eski), encoding="utf-8")

    okunan = storage.list_history(str(tmp_path))

    assert len(okunan) == 1
    assert "model" not in okunan[0], "eski kayıt YENİDEN YAZILMIŞ"
    assert okunan[0].get("model") is None
