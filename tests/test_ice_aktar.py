"""`tools/ice_aktar.py` — tek kullanıcılı yerleşim → bir hesabın DB satırları (Faz 1 / 8).

Kaynak iki katman: `tests/fixtures/v18` (eski biçim, elle yazılmış kayıtlar
dâhil) + o ağacın üstüne GÜNCEL yazıcılarla üretilmiş kayıtlar (`storage.save`
arena/video/oturum etiketleriyle, `chat_store.create`, `prefs.update`, ölü
`uploads` türü). Araç `main(argv)` üzerinden koşuyor — `DATABASE_URL`i
`veritabani` fixture'ı veriyor, hedef `--hedef tmp_path/hedef`. GERÇEK Postgres.

İddialar kaynaktan TÜRETİLİYOR (tests/test_legacy_formats.py'nin duruşu):
her kayıt için satır alan alan kaynağa eşit VE satırın JSON dökümü kaynağın
anahtar kümesini kaybetmiyor. Sayılar aracın bastığı tablodan okunuyor
(`_tablo`): operatörün göreceği şey ile testin ölçtüğü şey aynı olsun.

`_PARSE_ENV`: conftest DB'li testlerde `azure_client._parse_env_all`i patlatıyor
(web yolu kimlik dosyası açmaz); bu araç o dosyayı okuyan TEK meşru yer, kimlik
testi özgün işlevi geri koyuyor. Modül ithalinde yakalanıyor: fixture'lar
sonra koşuyor.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import func, select

import assets_store
import azure_client as ac
import chat_store
import models
import prefs
import storage
from services import depo_kimlik_bilgisi, depo_medya, depo_tercih, hesap, sifre, tablolar, zaman
from tools import ice_aktar

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO, "tests", "fixtures", "v18")
_PARSE_ENV = ac._parse_env_all
PNG = b"\x89PNG\r\n\x1a\n-ice-aktarma-"

# Güncel yazıcılarla eklenen kayıtların sabitleri — iddialar bunları arıyor.
ARENA = "aaaa1111bbbb"
PREFS = {"theme": models.ALLOWED_THEMES[1], "language": "tr", "autosave_sessions": False,
         "director_guidance": "hep duz vektor"}
KIMLIKLER = {"AZURE_IMAGE_API_KEY": "DUMMY-azure-anahtari", "AZURE_IMAGE_BASE_URL": "https://a/openai/v1/",
             "GEMINI_API_KEY": "DUMMY-gemini"}


def _oku(*parcalar: str):
    with open(os.path.join(*parcalar), encoding="utf-8") as f:
        return json.load(f)


def _kaynak(tmp_path) -> str:
    """v1.8 fixture'ı + güncel yazıcıların kayıtları: gerçek bir `KROMIS_DATA_DIR` gibi."""
    kok = str(tmp_path / "kaynak")
    shutil.copytree(FIXTURES, kok)
    out = os.path.join(kok, "output")
    # Arena turu (iki sütun, biri kazanan), video, oturum etiketi, içe aktarılmış.
    a = storage.save(PNG + b"a", {"prompt": "arena a", "size": "1024x1024", "quality": "high",
                                  "arena_id": ARENA, "model": "azure-gpt-image-2", "credits": 3},
                     out, now="2026-08-01T12:00:00")
    b = storage.save(PNG + b"b", {"prompt": "arena b", "size": "1024x1024", "quality": "high",
                                  "arena_id": ARENA, "model": "openai-gpt-image-2", "credits": 5},
                     out, now="2026-08-01T12:00:00")
    assert storage.set_arena_winner(ARENA, b["id"], out)
    sohbet = chat_store.create("Kampanya oturumu", [
        {"role": "user", "content": "afiş"},
        {"role": "result", "image_ids": [a["id"], b["id"], "b6f4a17039ba"], "params": {"n": 2}},
    ], out, now="2026-08-01T12:05:00")
    storage.save(b"\x00\x00\x00\x18ftypmp4-", {"prompt": "klip", "size": "1280x720", "quality": "high",
                                              "kind": "video", "duration": 8,
                                              "session_id": sohbet["id"], "imported": True,
                                              "model": "", "credits": 0},
                 out, now="2026-08-02T09:00:00")
    prefs.update(dict(PREFS), out)
    # Ölü `uploads` türü — web `migrate_legacy_uploads`i artık çağırmıyor, araç taşır.
    yukleme = os.path.join(kok, "assets", assets_store.LEGACY_KIND)
    os.makedirs(yukleme)
    with open(os.path.join(yukleme, "dddd0000eeee.png"), "wb") as f:
        f.write(PNG + b"upload")
    with open(os.path.join(yukleme, "index.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": "dddd0000eeee", "filename": "dddd0000eeee.png", "name": "Eski yükleme",
                    "kind": "uploads", "created_at": "2026-06-01T08:00:00"}], f)
    return kok


def _agac_ozeti(kok: str) -> dict[str, str]:
    ozet = {}
    for dizin, _, dosyalar in os.walk(kok):
        for ad in dosyalar:
            yol = os.path.join(dizin, ad)
            with open(yol, "rb") as f:
                ozet[os.path.relpath(yol, kok)] = hashlib.sha256(f.read()).hexdigest()
    return ozet


def _tablo(cikti: str) -> dict[str, dict[str, int]]:
    """Aracın bastığı özet tablosu → {depo: {sütun: sayı}}."""
    sutunlar = ("aktarilan", "atlanan", "yeni_kimlik", "ezilen", "dosya_eksik", "dusurulen", "bozuk")
    satirlar = {}
    for m in re.finditer(r"^(\w+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", cikti, re.M):
        satirlar[m.group(1)] = dict(zip(sutunlar, (int(x) for x in m.groups()[1:]), strict=True))
    assert set(satirlar) == set(ice_aktar.DEPOLAR), cikti
    return satirlar


def _calistir(tmp_path, kaynak: str, eposta: str, *ek: str, capsys) -> tuple[int, dict, str, str]:
    kod = ice_aktar.main(["--kaynak", kaynak, "--eposta", eposta, "--hedef", str(tmp_path / "hedef"), *ek])
    out, err = capsys.readouterr()
    return kod, (_tablo(out) if kod in (0, ice_aktar.CIKIS_BOZUK) else {}), out, err


def _hedef(tmp_path, kullanici_id) -> str:
    return str(tmp_path / "hedef" / "kullanicilar" / str(kullanici_id))


def _sayi(db, tablo, kullanici_id) -> int:
    return int(db.scalar(select(func.count()).select_from(tablo).where(tablo.kullanici_id == kullanici_id)) or 0)


def _satirlar(db, tablo, kullanici_id) -> dict[str, object]:
    return {s.id: s for s in db.scalars(select(tablo).where(tablo.kullanici_id == kullanici_id))}


@pytest.fixture
def baska(db_oturumu):
    """Başka bir kullanıcı — çakışma testleri onun satırlarını tohumlar; sonunda silinir (CASCADE)."""
    k = tablolar.Kullanici(eposta=f"baska-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                           dogrulandi_at=hesap.simdi())
    db_oturumu.add(k)
    db_oturumu.commit()
    yield k
    db_oturumu.delete(k)
    db_oturumu.commit()


# ── alan alan ────────────────────────────────────────────────────────────

def test_the_v18_fixture_and_a_current_layout_land_in_the_db_field_by_field(tmp_path, capsys,
                                                                            db_oturumu, kullanici):
    kaynak = _kaynak(tmp_path)
    kod, sayilar, _, err = _calistir(tmp_path, kaynak, kullanici.eposta, capsys=capsys)
    assert kod == 0, err
    hedef = _hedef(tmp_path, kullanici.id)

    gecmis = _oku(kaynak, "output", "history.json")
    medya = _satirlar(db_oturumu, tablolar.Medya, kullanici.id)
    assert sayilar["medya"]["aktarilan"] == len(gecmis) == len(medya) == 8
    for r in gecmis:
        m = medya[r["id"]]
        assert (m.filename, m.prompt, m.size, m.quality) == (r["filename"], r["prompt"], r["size"], r["quality"])
        assert (m.parent_id, m.folder_id, m.palette, m.prompt_sent) == (
            r.get("parent_id"), r.get("folder_id"), r.get("palette"), r.get("prompt_sent"))
        assert m.model == (r.get("model") or "") and m.credits == int(r.get("credits") or 0)
        assert m.imported == (True if r.get("imported") else None)
        assert m.session_id == r.get("session_id") and m.arena_id == r.get("arena_id")
        assert m.kind == r.get("kind") and m.duration == r.get("duration")
        assert m.arena_win == (True if r.get("arena_win") else None)
        # Damga saniyesine kadar korunur; `damga` eski biçimi geri verir.
        assert zaman.damga(m.olusturuldu) == r["created_at"]
        assert not (set(r) - set(depo_medya._json(m))), f"{r['id']}: alan kaybı"
        with open(os.path.join(hedef, "output", m.filename), "rb") as h, \
                open(os.path.join(kaynak, "output", r["filename"]), "rb") as k:
            assert h.read() == k.read()
    # Liste sırası → `olusturuldu` sırası (aynı saniyedeki arena sütunları dâhil).
    sirali = sorted(medya.values(), key=lambda m: m.olusturuldu)
    assert [m.id for m in sirali if m.arena_id == ARENA] == [r["id"] for r in gecmis if r.get("arena_id") == ARENA]

    klasorler = _satirlar(db_oturumu, tablolar.Klasor, kullanici.id)
    kaynak_klasorler = _oku(kaynak, "output", "folders.json")
    assert sayilar["klasorler"]["aktarilan"] == len(kaynak_klasorler) == len(klasorler) == 3
    for f in kaynak_klasorler:
        k = klasorler[f["id"]]
        assert (k.name, k.parent_id) == (f["name"], f.get("parent_id"))
        assert zaman.damga(k.olusturuldu) == f["created_at"]

    sohbetler = _satirlar(db_oturumu, tablolar.Sohbet, kullanici.id)
    for c in _oku(kaynak, "output", "chats.json"):
        s = sohbetler[c["id"]]
        assert (s.title, s.mesajlar) == (c["title"], c["messages"])
        assert zaman.damga(s.olusturuldu) == c["created_at"] and zaman.damga(s.guncellendi) == c["updated_at"]
    assert sayilar["sohbetler"]["aktarilan"] == len(sohbetler) == 1

    paletler = _satirlar(db_oturumu, tablolar.Palet, kullanici.id)
    for p in _oku(kaynak, "output", "palettes.json"):
        pal = paletler[p["id"]]
        assert (pal.name, pal.seed, pal.mode, pal.strength, pal.colors) == (
            p["name"], p["seed"], p["mode"], p["strength"], p["colors"])
    assert sayilar["paletler"]["aktarilan"] == len(paletler) == 2

    varliklar = _satirlar(db_oturumu, tablolar.Varlik, kullanici.id)
    for tur in assets_store.KINDS:
        for a in _oku(kaynak, "assets", tur, "index.json"):
            v = varliklar[a["id"]]
            assert (v.filename, v.name, v.tur) == (a["filename"], a["name"], tur)
            assert os.path.isfile(os.path.join(hedef, "assets", tur, v.filename))
    assert sayilar["varliklar"]["aktarilan"] == len(varliklar) == 5

    assert depo_tercih.kayitli(db_oturumu, kullanici.id) == prefs.read_stored(os.path.join(kaynak, "output")) == PREFS
    db_oturumu.expire_all()
    assert db_oturumu.get(tablolar.Kullanici, kullanici.id).dil == "tr", "dil zinciri `kullanicilar.dil`i okuyor"
    assert sayilar["tercihler"]["aktarilan"] == len(PREFS)
    assert sayilar["kimlikler"] == dict.fromkeys(sayilar["kimlikler"], 0), "kimlik dosyası verilmedi"
    assert all(s["bozuk"] == 0 and s["yeni_kimlik"] == 0 for s in sayilar.values())
    # Kullanıcı kökü 0o700 (services/ayar.py kuralı); manifest kopyalanmadı.
    assert oct(os.stat(hedef).st_mode & 0o777) == "0o700"
    assert not os.path.exists(os.path.join(hedef, "output", "history.json"))


def test_the_dead_uploads_kind_becomes_logos(tmp_path, capsys, db_oturumu, kullanici):
    kaynak = _kaynak(tmp_path)
    kod, _, _, _ = _calistir(tmp_path, kaynak, kullanici.eposta, capsys=capsys)
    assert kod == 0
    v = db_oturumu.get(tablolar.Varlik, "dddd0000eeee")
    assert v is not None and v.tur == assets_store.LEGACY_TARGET and v.kullanici_id == kullanici.id
    assert os.path.isfile(os.path.join(_hedef(tmp_path, kullanici.id), "assets", "logos", "dddd0000eeee.png"))


def test_the_source_tree_is_left_byte_for_byte_unchanged(tmp_path, capsys, kullanici):
    kaynak = _kaynak(tmp_path)
    once = _agac_ozeti(kaynak)
    assert _calistir(tmp_path, kaynak, kullanici.eposta, capsys=capsys)[0] == 0
    assert _calistir(tmp_path, kaynak, kullanici.eposta, "--yeniden", capsys=capsys)[0] == 0
    assert _agac_ozeti(kaynak) == once


# ── çakışma ──────────────────────────────────────────────────────────────

def test_ids_owned_by_another_user_are_rederived_and_every_reference_follows(tmp_path, capsys,
                                                                             db_oturumu, kullanici, baska):
    """Başkasının satırıyla çakışan klasör, medya, sohbet ve arena id'leri türetilir; başvurular izler."""
    kaynak = _kaynak(tmp_path)
    gecmis = _oku(kaynak, "output", "history.json")
    sohbet = _oku(kaynak, "output", "chats.json")[0]
    arena_a = next(r for r in gecmis if r.get("arena_id") == ARENA and not r.get("arena_win"))
    an = zaman.an()
    db_oturumu.add(tablolar.Klasor(id="ba41347addfc", kullanici_id=baska.id, name="B'nin", olusturuldu=an))
    db_oturumu.add(tablolar.Medya(id="b6f4a17039ba", kullanici_id=baska.id, filename="b6f4a17039ba.png",
                                  prompt="", size="", quality="", model="", credits=0, olusturuldu=an))
    db_oturumu.add(tablolar.Medya(id="ffff9999ffff", kullanici_id=baska.id, filename="ffff9999ffff.png",
                                  prompt="", size="", quality="", model="", credits=0, arena_id=ARENA,
                                  olusturuldu=an))
    db_oturumu.add(tablolar.Sohbet(id=sohbet["id"], kullanici_id=baska.id, title="B", mesajlar=[],
                                   olusturuldu=an, guncellendi=an))
    db_oturumu.commit()

    kod, sayilar, _, err = _calistir(tmp_path, kaynak, kullanici.eposta, capsys=capsys)
    assert kod == 0, err
    yeni_klasor = ice_aktar.turet(kullanici.id, "klasorler", "ba41347addfc")
    yeni_medya = ice_aktar.turet(kullanici.id, "medya", "b6f4a17039ba")
    yeni_sohbet = ice_aktar.turet(kullanici.id, "sohbetler", sohbet["id"])
    yeni_arena = ice_aktar.turet(kullanici.id, "arena", ARENA)
    for yeni in (yeni_klasor, yeni_medya, yeni_sohbet, yeni_arena):
        assert storage.valid_id(yeni) and len(yeni) == 32

    medya = _satirlar(db_oturumu, tablolar.Medya, kullanici.id)
    klasorler = _satirlar(db_oturumu, tablolar.Klasor, kullanici.id)
    assert yeni_klasor in klasorler and "ba41347addfc" not in klasorler
    assert klasorler[yeni_klasor].parent_id == "acf949875158", "çakışmayan ebeveyn aynen"
    assert medya["a70272082f8a"].folder_id == yeni_klasor, "folder_id yeni klasörü izler"
    assert yeni_medya in medya and "b6f4a17039ba" not in medya
    assert medya[yeni_medya].filename == f"{yeni_medya}.png"
    assert medya["abf1d149451f"].parent_id == yeni_medya, "türev zinciri izler"
    assert os.path.isfile(os.path.join(_hedef(tmp_path, kullanici.id), "output", f"{yeni_medya}.png"))
    arena_sutunlari = [m for m in medya.values() if m.arena_id == yeni_arena]
    assert len(arena_sutunlari) == 2 and sum(1 for m in arena_sutunlari if m.arena_win) == 1
    assert not any(m.arena_id == ARENA for m in medya.values()), "kardeşler birlikte taşındı"
    assert medya[arena_a["id"]].arena_id == yeni_arena
    s = db_oturumu.get(tablolar.Sohbet, yeni_sohbet)
    assert s is not None and s.kullanici_id == kullanici.id
    goruntuler = next(m for m in s.mesajlar if m.get("role") == "result")["image_ids"]
    assert goruntuler[2] == yeni_medya and goruntuler[:2] == sohbet["messages"][1]["image_ids"][:2]
    klip = next(m for m in medya.values() if m.kind == "video")
    assert klip.session_id == yeni_sohbet, "session_id yeni sohbeti izler"
    assert (sayilar["klasorler"]["yeni_kimlik"], sayilar["medya"]["yeni_kimlik"],
            sayilar["sohbetler"]["yeni_kimlik"]) == (1, 1, 1)
    # Başkasının satırlarına dokunulmadı.
    assert _sayi(db_oturumu, tablolar.Medya, baska.id) == 2 and _sayi(db_oturumu, tablolar.Klasor, baska.id) == 1

    # İkinci koşu: türetilmiş id'ler bulunur, hiçbir şey yeniden açılmaz (rastgele id ile açılırdı).
    kod, sayilar2, _, _ = _calistir(tmp_path, kaynak, kullanici.eposta, capsys=capsys)
    assert kod == 0
    assert all(s["aktarilan"] == 0 for s in sayilar2.values())
    assert sayilar2["medya"]["atlanan"] == len(gecmis) and _sayi(db_oturumu, tablolar.Medya, kullanici.id) == len(gecmis)


def test_the_derived_id_is_deterministic_per_user_and_table(kullanici):
    a = ice_aktar.turet(kullanici.id, "medya", "b6f4a17039ba")
    assert a == ice_aktar.turet(kullanici.id, "medya", "b6f4a17039ba")
    assert a != ice_aktar.turet(kullanici.id, "klasorler", "b6f4a17039ba")
    assert a != ice_aktar.turet(uuid.uuid4(), "medya", "b6f4a17039ba")
    assert re.fullmatch(tablolar.ID_KALIBI, a) and len(a) == 32


# ── idempotenlik, yeniden, kuru ──────────────────────────────────────────

def test_a_second_run_imports_nothing_new(tmp_path, capsys, db_oturumu, kullanici):
    kaynak = _kaynak(tmp_path)
    assert _calistir(tmp_path, kaynak, kullanici.eposta, capsys=capsys)[0] == 0
    sayim = {t: _sayi(db_oturumu, t, kullanici.id) for t in (tablolar.Medya, tablolar.Klasor, tablolar.Sohbet,
                                                             tablolar.Palet, tablolar.Varlik)}
    kod, sayilar, _, _ = _calistir(tmp_path, kaynak, kullanici.eposta, capsys=capsys)
    assert kod == 0
    assert all(s["aktarilan"] == 0 and s["ezilen"] == 0 for s in sayilar.values())
    assert sayilar["medya"]["atlanan"] == 8 and sayilar["tercihler"]["atlanan"] == len(PREFS)
    assert {t: _sayi(db_oturumu, t, kullanici.id) for t in sayim} == sayim


def test_yeniden_overwrites_existing_rows_from_the_source_but_deletes_nothing(tmp_path, capsys,
                                                                              db_oturumu, kullanici):
    kaynak = _kaynak(tmp_path)
    assert _calistir(tmp_path, kaynak, kullanici.eposta, capsys=capsys)[0] == 0
    m = db_oturumu.get(tablolar.Medya, "b6f4a17039ba")
    m.prompt = "web'de degistirildi"
    db_oturumu.add(tablolar.Medya(id=uuid.uuid4().hex, kullanici_id=kullanici.id, filename="web.png",
                                  prompt="web", size="", quality="", model="", credits=0, olusturuldu=zaman.an()))
    depo_tercih.guncelle(db_oturumu, kullanici.id, {"theme": "mono"})
    db_oturumu.commit()
    kod, sayilar, _, _ = _calistir(tmp_path, kaynak, kullanici.eposta, "--yeniden", capsys=capsys)
    assert kod == 0
    db_oturumu.expire_all()
    assert db_oturumu.get(tablolar.Medya, "b6f4a17039ba").prompt == "sade bir afiş"
    assert sayilar["medya"]["ezilen"] == 8 and sayilar["medya"]["aktarilan"] == 0
    assert _sayi(db_oturumu, tablolar.Medya, kullanici.id) == 9, "web'de açılan satır silinmez"
    assert depo_tercih.kayitli(db_oturumu, kullanici.id)["theme"] == PREFS["theme"]


def test_a_dry_run_writes_neither_rows_nor_files(tmp_path, capsys, db_oturumu, kullanici):
    kaynak = _kaynak(tmp_path)
    kod, sayilar, out, _ = _calistir(tmp_path, kaynak, kullanici.eposta, "--kuru", capsys=capsys)
    assert kod == 0
    assert sayilar["medya"]["aktarilan"] == 8 and sayilar["varliklar"]["aktarilan"] == 5
    assert "KURU KOSU" in out
    assert _sayi(db_oturumu, tablolar.Medya, kullanici.id) == 0
    assert db_oturumu.get(tablolar.Tercih, kullanici.id) is None
    assert not (tmp_path / "hedef").exists()


# ── bozuk veri ───────────────────────────────────────────────────────────

def test_a_corrupt_record_is_reported_and_the_rest_is_imported(tmp_path, capsys, db_oturumu, kullanici):
    kaynak = _kaynak(tmp_path)
    yol = os.path.join(kaynak, "output", "history.json")
    gecmis = _oku(yol)
    gecmis += ["dize", {"id": "../etc", "filename": "x.png"}, {"id": "cccc0000cccc"}]   # 3 bozuk
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(gecmis, f)
    with open(os.path.join(kaynak, "output", "palettes.json"), "w", encoding="utf-8") as f:
        f.write("{ bozuk json")
    kod, sayilar, _, err = _calistir(tmp_path, kaynak, kullanici.eposta, capsys=capsys)
    assert kod == ice_aktar.CIKIS_BOZUK
    assert sayilar["medya"]["bozuk"] == 3 and sayilar["medya"]["aktarilan"] == 8
    assert sayilar["paletler"]["bozuk"] == 1 and sayilar["paletler"]["aktarilan"] == 0
    assert _sayi(db_oturumu, tablolar.Medya, kullanici.id) == 8
    assert _sayi(db_oturumu, tablolar.Klasor, kullanici.id) == 3, "öteki depolar sürdü"
    assert "palettes.json okunamadi" in err and "cccc0000cccc" in err


def test_a_dangling_folder_reference_is_nulled_and_counted(tmp_path, capsys, db_oturumu, kullanici):
    kaynak = _kaynak(tmp_path)
    yol = os.path.join(kaynak, "output", "history.json")
    gecmis = _oku(yol)
    gecmis[0]["folder_id"] = "9999deadbeef"
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(gecmis, f)
    kod, sayilar, _, _ = _calistir(tmp_path, kaynak, kullanici.eposta, capsys=capsys)
    assert kod == 0, "onarım bozukluk değil"
    assert db_oturumu.get(tablolar.Medya, gecmis[0]["id"]).folder_id is None
    assert sayilar["medya"]["dusurulen"] == 1


def test_a_missing_media_file_still_imports_the_row_and_says_so(tmp_path, capsys, db_oturumu, kullanici):
    kaynak = _kaynak(tmp_path)
    os.remove(os.path.join(kaynak, "output", "aaaaaaaaaaaa.png"))
    kod, sayilar, _, err = _calistir(tmp_path, kaynak, kullanici.eposta, capsys=capsys)
    assert kod == 0 and sayilar["medya"]["dosya_eksik"] == 1
    assert db_oturumu.get(tablolar.Medya, "aaaaaaaaaaaa") is not None
    assert "aaaaaaaaaaaa.png yok" in err


# ── kimlik dosyası ───────────────────────────────────────────────────────

def test_the_credentials_file_lands_encrypted_and_reads_back_through_the_repo(tmp_path, capsys, monkeypatch,
                                                                              db_oturumu, kullanici):
    monkeypatch.setattr(ac, "_parse_env_all", _PARSE_ENV)
    kaynak = _kaynak(tmp_path)
    dosya = tmp_path / "credentials.env"
    dosya.write_text("# yorum\n" + "".join(f"{a}={d}\n" for a, d in KIMLIKLER.items())
                     + "OPENAI_API_KEY=\nYABANCI_DEGISKEN=x\n", encoding="utf-8")
    kod, sayilar, out, err = _calistir(tmp_path, kaynak, kullanici.eposta, "--kimlik-dosyasi", str(dosya),
                                       capsys=capsys)
    assert kod == 0, err
    assert depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id) == KIMLIKLER
    assert sayilar["kimlikler"] == {"aktarilan": 3, "atlanan": 0, "yeni_kimlik": 0, "ezilen": 0,
                                    "dosya_eksik": 0, "dusurulen": 1, "bozuk": 0}
    assert "YABANCI_DEGISKEN" in err
    ham = db_oturumu.scalars(select(tablolar.SaglayiciKimligi.sifreli_deger)
                             .where(tablolar.SaglayiciKimligi.kullanici_id == kullanici.id)).all()
    assert len(ham) == 3 and all(b"DUMMY" not in h and h.startswith(b"gAAAA") for h in ham)
    for deger in KIMLIKLER.values():
        assert deger not in out and deger not in err, "anahtar değeri hiçbir çıktıya yazılmaz"
    # İkinci koşu: var olan adlar atlanır.
    kod, sayilar, _, _ = _calistir(tmp_path, kaynak, kullanici.eposta, "--kimlik-dosyasi", str(dosya),
                                   capsys=capsys)
    assert kod == 0 and sayilar["kimlikler"]["aktarilan"] == 0 and sayilar["kimlikler"]["atlanan"] == 3


def test_credentials_without_the_secret_key_stop_before_anything_is_written(tmp_path, capsys, monkeypatch,
                                                                             db_oturumu, kullanici):
    monkeypatch.delenv(sifre.ANAHTAR_ENV)
    kaynak = _kaynak(tmp_path)
    dosya = tmp_path / "credentials.env"
    dosya.write_text("AZURE_IMAGE_API_KEY=DUMMY\n", encoding="utf-8")
    kod = ice_aktar.main(["--kaynak", kaynak, "--eposta", kullanici.eposta, "--hedef", str(tmp_path / "hedef"),
                          "--kimlik-dosyasi", str(dosya)])
    assert kod == ice_aktar.CIKIS_ORTAM
    assert sifre.ANAHTAR_ENV in capsys.readouterr().err
    assert _sayi(db_oturumu, tablolar.Medya, kullanici.id) == 0 and not (tmp_path / "hedef").exists()


# ── girdi hataları ───────────────────────────────────────────────────────

def test_unknown_account_missing_source_and_missing_credentials_file_exit_1(tmp_path, capsys, kullanici):
    kaynak = _kaynak(tmp_path)
    hedef = str(tmp_path / "hedef")
    assert ice_aktar.main(["--kaynak", kaynak, "--eposta", "yok@example.com", "--hedef", hedef]) == 1
    assert "tools/kullanici.py olustur" in capsys.readouterr().err
    assert ice_aktar.main(["--kaynak", str(tmp_path / "yok"), "--eposta", kullanici.eposta, "--hedef", hedef]) == 1
    assert ice_aktar.main(["--kaynak", kaynak, "--eposta", kullanici.eposta, "--hedef", hedef,
                           "--kimlik-dosyasi", str(tmp_path / "yok.env")]) == 1
    assert not os.path.exists(hedef)


def test_without_database_url_the_tool_exits_2(tmp_path, capsys, monkeypatch, kullanici):
    from services import db
    monkeypatch.delenv(db.DATABASE_URL_ENV)
    assert ice_aktar.main(["--kaynak", _kaynak(tmp_path), "--eposta", kullanici.eposta]) == ice_aktar.CIKIS_ORTAM
    assert db.DATABASE_URL_ENV in capsys.readouterr().err


def test_the_script_runs_standalone():
    """`python tools/ice_aktar.py --help`: `sys.path` düzeni betik kipinde de kök modülleri buluyor."""
    c = subprocess.run([sys.executable, os.path.join(REPO, "tools", "ice_aktar.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=REPO)
    assert c.returncode == 0, c.stderr
    assert "--kuru" in c.stdout and "--yeniden" in c.stdout and "--kimlik-dosyasi" in c.stdout
