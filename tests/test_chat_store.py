"""Kayıtlı sohbetler ve chats.json yönetimi.

Bu store v1.15'te KARAR 4'ün kapsamını daraltıyor: tamamlama rotası
(`POST /api/chat`) hâlâ diske hiçbir şey yazmıyor, yazan tek yol kullanıcının
başlattığı `/api/chats`. Testler bu ayrımı da, `palette_store`/`folders` ile
paylaşılan dayanıklılık desenlerini de (bozuk JSON, atomik yazım, `_SAFE_ID`)
mekanik hale getiriyor.
"""
import json
import os
import threading
import time

import chat_store

THREAD = [{"role": "user", "content": "kare instagram görseli"},
          {"role": "assistant", "content": "**PROMPT**\n```\na cat\n```"}]

# Dökümdeki üçüncü rol (v2.0). Store rolleri DOĞRULAMIYOR — doğrulama
# models.ChatMessage'ta; buradaki tek ilgisi kapak id'sini türetmek.
def _result(*image_ids):
    return {"role": "result", "image_ids": list(image_ids),
            "params": {"kind": "generate", "size": "1024x1024", "quality": "medium"}}


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


def test_list_is_ordered_by_last_update_not_by_creation(tmp_path):
    """Panelde gösterilen damga `updated_at` — sıra da ONU izlemek zorunda.

    Dosya sırası oluşturma sırası: `update` kaydı yerinde değiştiriyor. Sıra
    dosyadan okunsa bugün devam edilen üç haftalık bir sohbet "14:32" yazıp
    listenin dibinde, haftalardır dokunulmamış ama daha yeni oluşturulmuş
    sohbetlerin ALTINDA kalırdı.
    """
    out = str(tmp_path / "output")
    old = chat_store.create("eski", THREAD, out, now="2026-07-15T10:00:00")
    chat_store.create("yeni", THREAD, out, now="2026-08-05T11:00:00")

    chat_store.update(old["id"], out, messages=THREAD, now="2026-08-05T14:32:00")

    assert [c["title"] for c in chat_store.list_chats(out)] == ["eski", "yeni"]


def test_records_without_a_stamp_sort_last_instead_of_crashing(tmp_path):
    """Elle düzenlenmiş/bayat bir kayıtta alan eksik olabilir: sıralama çökmemeli."""
    out = str(tmp_path / "output")
    chat_store.create("damgalı", THREAD, out, now="2026-08-05T10:00:00")
    raw = _read_raw(out)
    raw.append({"id": "beef1234beef", "title": "damgasız", "messages": []})
    chat_store._write(out, raw)

    assert [c["title"] for c in chat_store.list_chats(out)] == ["damgalı", "damgasız"]


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
    assert set(summary) == {"id", "title", "created_at", "updated_at",
                            # v2.0: liste küçük resmi için TEK id alanı. Gövdenin
                            # dışarıda kalma gerekçesi aynı — bu alan gövde değil,
                            # gövdeden türetilen 12 karakter (bkz. cover_from).
                            "cover_image_id", "message_count"}


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


def test_delete_all_empties_the_store_and_returns_the_count(tmp_path):
    """Karar D1'in ikinci güvencesi: tek tıkla "tümünü sil".

    Otomatik kayıt geçmişi kullanıcının istemediği kadar büyütebiliyor; tek tek
    silmek tek çıkış yolu olsaydı güvence lafta kalırdı.
    """
    out = str(tmp_path / "output")
    chat_store.create("bir", THREAD, out, now="2026-08-07T10:00:00")
    chat_store.create("iki", THREAD, out, now="2026-08-07T11:00:00")

    assert chat_store.delete_all(out) == 2
    assert chat_store.list_chats(out) == []
    assert _read_raw(out) == []


def test_delete_all_is_zero_on_an_empty_store(tmp_path):
    """Dosya yokken de çökmemeli ve dosya YARATMAMALI."""
    out = str(tmp_path / "output")

    assert chat_store.delete_all(out) == 0
    assert not os.path.exists(out)


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


def test_concurrent_creates_do_not_lose_records(tmp_path, monkeypatch):
    """"Oku → değiştir → yaz" bölünmez olmak zorunda (jsonstore kilidi).

    Rotalar senkron `def`, yani Starlette onları threadpool'da koşturuyor: tur
    sonu otomatik kaydı ile kullanıcının yeniden adlandırması GERÇEKTEN paralel
    çalışabiliyor. Kilit olmasa aşağıdaki dört yazımın üçü kaybolurdu — hepsi
    aynı bir-kayıtlık listeyi okuyup üstüne yazardı.
    """
    out = str(tmp_path / "output")
    chat_store.create("ilk", THREAD, out, now="2026-08-05T10:00:00")

    real_read = chat_store._read

    def slow_read(output_dir):
        items = real_read(output_dir)
        time.sleep(0.03)          # okuma ile yazım ARASINDA araya girme penceresi
        return items

    monkeypatch.setattr(chat_store, "_read", slow_read)
    threads = [threading.Thread(target=chat_store.create,
                                args=(f"eş{i}", THREAD, out),
                                kwargs={"now": "2026-08-05T11:00:00"})
               for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)

    titles = sorted(c["title"] for c in _read_raw(out))
    assert titles == ["eş0", "eş1", "eş2", "eş3", "ilk"]


def test_write_is_atomic_and_leaves_no_temp_file(tmp_path):
    """`os.replace` deseni: yarı yazılmış bir chats.json kalmamalı."""
    out = str(tmp_path / "output")
    chat_store.create("bir", THREAD, out, now="2026-08-05T10:00:00")

    assert os.listdir(out) == [chat_store.CHATS_FILE]


# ── v2.0: kapak görseli (liste küçük resmi) ─────────────────────────────
#
# Kapak PARAMETRE DEĞİL, dökümden TÜRETİLİYOR. Sebep: istemciden alınsaydı
# oturumun dökümünde HİÇ olmayan bir görseli kapak yapabilirdi — panelde
# gösterilen küçük resim ile açılan oturumun içeriği ayrışırdı. Türetme aynı
# zamanda tek kaynak bırakıyor: kapak, dökümün kendisi.

def test_a_session_without_a_result_has_no_cover_key(tmp_path):
    """Koşullu yazım (storage'ın `imported`/`session_id` deseni): sohbet-yalnız
    oturumlar bugünküyle aynı şekilde kalır."""
    out = str(tmp_path / "output")

    rec = chat_store.create("sohbet", THREAD, out, now="2026-08-07T10:00:00")

    assert "cover_image_id" not in rec
    assert "cover_image_id" not in _read_raw(out)[0]
    # Özet alanı yine de VAR ve None: panel `.cover_image_id` diye bakabilsin.
    assert chat_store.list_chats(out)[0]["cover_image_id"] is None


def test_cover_is_the_first_image_of_the_first_result(tmp_path):
    """İLK sonuç, son sonuç değil: kapak sabit kalmalı.

    Son sonuçtan alınsaydı liste küçük resmi her üretimde değişirdi — kullanıcı
    oturumu "o kırmızı afişli olan" diye tanıyorsa o iz kaybolur.
    """
    out = str(tmp_path / "output")
    thread = (THREAD + [_result("aaaa1111aaaa", "bbbb2222bbbb")]
              + [{"role": "user", "content": "bir de yatay"}]
              + [_result("cccc3333cccc")])

    rec = chat_store.create("üretimli", thread, out, now="2026-08-07T10:00:00")

    assert rec["cover_image_id"] == "aaaa1111aaaa"
    assert chat_store.list_chats(out)[0]["cover_image_id"] == "aaaa1111aaaa"


def test_update_derives_the_cover_when_the_first_result_arrives(tmp_path):
    """Otomatik kayıt (Adım 6) dökümü büyüterek yazıyor: kapak o turda doğar."""
    out = str(tmp_path / "output")
    rec = chat_store.create("sohbet", THREAD, out, now="2026-08-07T10:00:00")

    grown = chat_store.update(rec["id"], out,
                              messages=THREAD + [_result("aaaa1111aaaa")],
                              now="2026-08-07T10:05:00")

    assert grown["cover_image_id"] == "aaaa1111aaaa"


def test_renaming_keeps_the_cover(tmp_path):
    """`messages` verilmediyse döküme dokunulmuyor — kapak da öyle."""
    out = str(tmp_path / "output")
    rec = chat_store.create("üretimli", THREAD + [_result("aaaa1111aaaa")], out,
                            now="2026-08-07T10:00:00")

    renamed = chat_store.update(rec["id"], out, title="yeni ad",
                                now="2026-08-07T11:00:00")

    assert renamed["cover_image_id"] == "aaaa1111aaaa"


def test_cover_leaves_with_the_result_it_came_from(tmp_path):
    """Kapak dökümün DIŞINI gösteremez.

    Bayat bir alan kalsaydı panel, o oturumda artık bulunmayan bir görselin
    küçük resmini çizmeye devam ederdi — silinmiş görselin yer tutucusundan
    (§5) farklı bir şey: burada kayıt yanlış, orada görsel yok.
    """
    out = str(tmp_path / "output")
    rec = chat_store.create("üretimli", THREAD + [_result("aaaa1111aaaa")], out,
                            now="2026-08-07T10:00:00")

    trimmed = chat_store.update(rec["id"], out, messages=THREAD,
                                now="2026-08-07T11:00:00")

    assert "cover_image_id" not in trimmed
    assert chat_store.list_chats(out)[0]["cover_image_id"] is None


def test_cover_ignores_a_result_with_no_image_ids(tmp_path):
    """Elle düzenlenmiş/bayat bir kayıt: çökmek yerine kapaksız kalınır."""
    out = str(tmp_path / "output")
    thread = THREAD + [{"role": "result", "params": {}}, _result("aaaa1111aaaa")]

    rec = chat_store.create("bozuk", thread, out, now="2026-08-07T10:00:00")

    assert rec["cover_image_id"] == "aaaa1111aaaa"


def test_turkish_characters_survive_the_round_trip(tmp_path):
    """`ensure_ascii=False`: başlıkta 'ş' kaçış dizisine dönüşmemeli."""
    out = str(tmp_path / "output")
    rec = chat_store.create("bağış kampanyası", THREAD, out, now="2026-08-05T10:00:00")

    with open(os.path.join(out, chat_store.CHATS_FILE), encoding="utf-8") as f:
        assert "bağış kampanyası" in f.read()
    assert chat_store.get(rec["id"], out)["title"] == "bağış kampanyası"
