"""Veri modeli — `services/tablolar.py` + `alembic/versions/0001_veri_modeli.py` (Faz 1 / 2. görev).

Faz 2 / 1 iki tablo ekledi (`isler`, `isciler`; göç `0004_isler`): `isler`
sekizinci iş tablosu, `isciler` üçüncü sınıf — ne hesap ne iş, PLATFORMUN
(kullanıcı sütunu yok). Kuyruk davranışı tests/test_kuyruk.py'de; burada
yalnız şema, kısıt ve sınıflandırma.

Hepsi GERÇEK Postgres'e karşı (`veritabani` fixture'ı): sınanan şeylerin
çoğu — citext eşitliği, `ON DELETE CASCADE`/`SET NULL`, JSONB gidiş-dönüş,
`CHECK`in gerçekten reddetmesi — SQLite'ta ya yok ya farklı (K4). Göç hattının
mekanizması (`upgrade`/`downgrade`/`check`, URL kaynağı) `tests/test_db.py`de;
burası ŞEMANIN kendisi: doğru tablolar doğru kısıtlarla doğdu mu, ve model
ile göç dosyası aynı şeyi mi söylüyor.

İki bekçi bu dosyanın asıl sebebi:

* `test_every_business_table_carries_the_owner_column_its_fk_and_its_index` —
  çok kiracılılık kararı (tek DB, satır düzeyi `kullanici_id`) her iş
  tablosunda aynı üç şeyi ister; yedinci tablo eklenirken biri unutulursa
  burada kırmızı. Kapsam listesi `tablolar.IS_TABLOLARI` ve o liste de
  belgedeki envanterle eşitleniyor (CLAUDE.md §5: elle liste, bekçili).
* `test_check_constraints_accept_every_allowed_value_and_reject_the_rest` —
  `alembic check` CHECK kısıtlarını KARŞILAŞTIRMAZ (Alembic'in belgelediği
  sınır): `models.ALLOWED_THEMES`e yeni tema girse model değişir, göç
  dosyası değişmez, `check` yine "fark yok" der. Her izinli değeri gerçekten
  yazmayı deneyen bu test o sessizliği kapatıyor.
"""
from __future__ import annotations

import os
import re
import uuid

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import assets_store
import chat_store
import folders
import models
import palette_store
import storage
from services import tablolar

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BELGE = os.path.join(REPO, "docs", "faz1-veritabani-hesaplar.md")
BELGE_FAZ2 = os.path.join(REPO, "docs", "faz2-kuyruk-anahtarlar-depolama.md")
BELGE_FAZ3 = os.path.join(REPO, "docs", "faz3-kredi-defteri-filigran.md")

HESAP_TABLOLARI = {"kullanicilar", "oturumlar", "jetonlar", "giris_denemeleri"}
# Ne hesap ne iş: platformun kendi satırları (Faz 2 / 1). `kullanici_id` YOK,
# kiracı süzgeci anlamsız — o yüzden `IS_TABLOLARI` bekçisinin dışında.
ALTYAPI_TABLOLARI = {"isciler"}

# Belgenin "Kimlik kararı"ndaki beş liste tablosu: `id text` + `_SAFE_ID` CHECK'i
# + `(kullanici_id, olusturuldu)` indeksi. `tercihler` (PK = kullanici_id) ve
# `saglayici_kimlikleri` (PK = (kullanici_id, ad)) bu kalıbın DIŞINDA ve bilerek.
LISTE_TABLOLARI = ("medya", "klasorler", "sohbetler", "paletler", "varliklar")


@pytest.fixture
def motor(veritabani: str):
    m = create_engine(veritabani)
    yield m
    m.dispose()


@pytest.fixture
def temiz(motor):
    """Dosya içindeki testler aynı DB'yi paylaşır (modül kapsamı); her test boş kullanıcı tablosuyla başlasın."""
    with motor.begin() as c:
        c.execute(text("DELETE FROM giris_denemeleri"))
        c.execute(text("DELETE FROM kullanicilar"))   # iş tabloları CASCADE ile boşalır
    yield


def _kullanici(db: Session, eposta: str = "ali@example.com") -> tablolar.Kullanici:
    k = tablolar.Kullanici(eposta=eposta)
    db.add(k)
    db.flush()
    return k


def _her_is_tablosuna_bir_satir(db: Session, k: tablolar.Kullanici) -> None:
    """Dokuz iş tablosunun her birine, birbirine bağlı biçimde, bir satır."""
    klasor = tablolar.Klasor(id=uuid.uuid4().hex, kullanici_id=k.id, name="K")
    db.add(klasor)
    db.flush()
    db.add_all([
        # `filename` UNIQUE (küresel) — kullanıcı başına farklı ad.
        tablolar.Medya(id=uuid.uuid4().hex[:12], kullanici_id=k.id, filename=f"{klasor.id}.png",
                       prompt="p", size="1024x1024", quality="high", folder_id=klasor.id,
                       model="m", credits=1),
        tablolar.Sohbet(id=uuid.uuid4().hex, kullanici_id=k.id, title="S", mesajlar=[]),
        tablolar.Palet(id=uuid.uuid4().hex, kullanici_id=k.id, name="P", seed="#fff",
                       mode="mono", strength="orta", colors=[]),
        tablolar.Varlik(id=uuid.uuid4().hex, kullanici_id=k.id, filename="l.png",
                        name="L", tur="logos"),
        tablolar.Tercih(kullanici_id=k.id, theme="mono"),
        tablolar.SaglayiciKimligi(kullanici_id=k.id, ad="OPENAI_API_KEY",
                                  sifreli_deger=b"gAAAA", anahtar_surumu=1),
        tablolar.Is(kullanici_id=k.id, tur="generate", istek={"prompt": "p"}, model="m",
                    kredi_tahmini=1),
        # Faz 3 / 1: anahtar küresel UNIQUE — kullanıcı başına farklı.
        tablolar.KrediHareketi(kullanici_id=k.id, tur="hibe", miktar=1,
                               idempotency_anahtari=f"hibe:{k.id}:2026-09"),
    ])
    db.flush()


def _sayimlar(motor) -> dict[str, int]:
    with motor.connect() as c:
        return {t: c.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()
                for t in tablolar.IS_TABLOLARI}


# ──────────────────────────────────────────────────── Postgres GEREKMEYEN

def test_the_business_table_registry_matches_the_document_inventory():
    """`IS_TABLOLARI` elle tutulan bir kapsam listesi; belgedeki envanter onun bekçisi.

    Faz 1 belgesi (§2) yedi iş tablosunu "İş tabloları, envanterden birebir:"
    cümlesinde sayıyor; Faz 2 belgesi (§1, "Dokunulan") sekizinciyi
    "`IS_TABLOLARI` bekçi listesi 7 → 8: `isler`" diye ekliyor ve `isciler`i
    "DEĞİL — kullanıcı satırı yok" diye dışarıda bırakıyor; Faz 3 belgesi (§1,
    "Dokunulan") dokuzuncuyu "`IS_TABLOLARI` bekçi listesi 8 → 9:
    `kredi_hareketleri`" diye ekliyor. Dört küme (üç belge, liste, model)
    birbirinden ayrılırsa burada görünür.
    """
    with open(BELGE, encoding="utf-8") as f:
        belge = f.read()
    m = re.search(r"İş tabloları, envanterden birebir:(.*?)— hepsinde", belge, re.S)
    assert m, "belgede 'İş tabloları, envanterden birebir:' cümlesi yok"
    belgedeki = set(re.findall(r"`(\w+)`", m.group(1)))
    with open(BELGE_FAZ2, encoding="utf-8") as f:
        belge2 = f.read()
    m2 = re.search(r"`IS_TABLOLARI` bekçi listesi 7\s*→ 8: `(\w+)`", belge2)
    assert m2, "Faz 2 belgesinde '`IS_TABLOLARI` bekçi listesi 7 → 8: `…`' cümlesi yok"
    belgedeki.add(m2.group(1))
    with open(BELGE_FAZ3, encoding="utf-8") as f:
        belge3 = f.read()
    m4 = re.search(r"`IS_TABLOLARI` bekçi\s+listesi 8\s*→ 9: `(\w+)`", belge3)
    assert m4, "Faz 3 belgesinde '`IS_TABLOLARI` bekçi listesi 8 → 9: `…`' cümlesi yok"
    belgedeki.add(m4.group(1))
    m3 = re.search(r"`(\w+)` DEĞİL — kullanıcı satırı yok", belge2)
    assert m3 and {m3.group(1)} == ALTYAPI_TABLOLARI, "Faz 2 belgesinin dışarıda bıraktığı tablo ↔ ALTYAPI_TABLOLARI"
    assert belgedeki == set(tablolar.IS_TABLOLARI), (
        f"belge ↔ IS_TABLOLARI ayrıştı: {belgedeki ^ set(tablolar.IS_TABLOLARI)}")
    modeldeki = set(tablolar.Base.metadata.tables)
    siniflanan = HESAP_TABLOLARI | ALTYAPI_TABLOLARI | set(tablolar.IS_TABLOLARI)
    assert modeldeki == siniflanan, f"modelde sınıflanmamış tablo: {modeldeki ^ siniflanan}"
    assert len(modeldeki) == 14, "Faz 3 / 1'in çıkış ölçütü: 14 tablo (Faz 2 / 1: 13)"


def test_the_sql_id_pattern_is_the_safe_id_regex_of_every_json_store():
    """`ID_KALIBI` `_SAFE_ID`nin SQL'i — beş kopyanın hepsiyle (fullmatch = `^…$`).

    İçe aktarılan 12 haneli eski id ile yeni 32 haneli `uuid4().hex` aynı
    kapıdan geçmeli; kalıp bir yerde daralsa öteki yerde kabul edilen id
    DB'de reddedilirdi.
    """
    for depo in (storage, folders, chat_store, palette_store, assets_store):
        assert tablolar.ID_KALIBI == f"^{depo._SAFE_ID.pattern}$", depo.__name__
    assert re.fullmatch(tablolar.ID_KALIBI, uuid.uuid4().hex)
    assert re.fullmatch(tablolar.ID_KALIBI, uuid.uuid4().hex[:12])


def test_every_business_table_carries_the_owner_column_its_fk_and_its_index():
    """Çok kiracılılık üç şey ister, dokuz tablonun dokuzunda: sütun, CASCADE FK, önde `kullanici_id` olan indeks."""
    for ad in tablolar.IS_TABLOLARI:
        t = tablolar.Base.metadata.tables[ad]
        sutun = t.c["kullanici_id"]
        assert not sutun.nullable, f"{ad}.kullanici_id NULL olabilir"
        fkler = [fk for fk in sutun.foreign_keys if fk.column.table.name == "kullanicilar"]
        assert fkler and fkler[0].ondelete == "CASCADE", f"{ad}: kullanicilar'a CASCADE FK yok"
        onde = [tuple(c.name for c in ix.columns) for ix in t.indexes]
        onde.append(tuple(c.name for c in t.primary_key.columns))
        assert any(k and k[0] == "kullanici_id" for k in onde), (
            f"{ad}: ilk sütunu kullanici_id olan indeks/PK yok — sahibe göre süzgeç tam tarama olur")
    for ad in LISTE_TABLOLARI:
        t = tablolar.Base.metadata.tables[ad]
        assert (ad, ("kullanici_id", "olusturuldu")) in {
            (ad, tuple(c.name for c in ix.columns)) for ix in t.indexes}, (
            f"{ad}: (kullanici_id, olusturuldu) indeksi yok — list_history'nin sırası")
        assert any(str(ck.name) == f"ck_{ad}_id_bicimi" for ck in t.constraints
                   if ck.__class__.__name__ == "CheckConstraint"), f"{ad}: id CHECK'i yok"


def test_every_constraint_has_a_conventional_name():
    """Adsız kısıt = `alembic check`te sonsuz "fark var" + düşürülemeyen kısıt."""
    for t in tablolar.Base.metadata.tables.values():
        for k in t.constraints:
            assert k.name is not None, f"{t.name}: adsız {type(k).__name__}"
        for ix in t.indexes:
            assert ix.name and ix.name.startswith("ix_"), f"{t.name}: indeks adı {ix.name!r}"


# ─────────────────────────────────────────────────────── GERÇEK Postgres

def test_every_table_exists_after_upgrade_head_and_nothing_else_does(motor):
    """Göç = model: DB'deki tablo kümesi `Base.metadata` ile birebir (+ `alembic_version`)."""
    dbdeki = set(inspect(motor).get_table_names())
    assert dbdeki == set(tablolar.Base.metadata.tables) | {"alembic_version"}


def test_citext_makes_email_uniqueness_case_insensitive(motor, temiz):
    """`Ali@X.com` ile `ali@x.com` aynı hesap: UNIQUE DB'de, `lower()` çağrısı beklemeden."""
    with Session(motor) as db:
        _kullanici(db, "Ali@Example.com")
        db.commit()
        assert db.scalar(select(tablolar.Kullanici).where(
            tablolar.Kullanici.eposta == "ALI@EXAMPLE.COM")) is not None
        db.add(tablolar.Kullanici(eposta="ali@example.com"))
        with pytest.raises(IntegrityError) as hata:
            db.flush()
        assert "uq_kullanicilar_eposta" in str(hata.value)


def test_deleting_a_user_cascades_to_every_business_table(motor, temiz):
    """Hesap silinince dokuz tablodaki satırları da gider; başka kullanıcının satırı kalır."""
    with Session(motor) as db:
        ali = _kullanici(db, "ali@example.com")
        veli = _kullanici(db, "veli@example.com")
        _her_is_tablosuna_bir_satir(db, ali)
        _her_is_tablosuna_bir_satir(db, veli)
        db.commit()
        assert all(n == 2 for n in _sayimlar(motor).values()), _sayimlar(motor)
        db.delete(ali)
        db.commit()
    assert all(n == 1 for n in _sayimlar(motor).values()), _sayimlar(motor)


def test_a_business_row_cannot_exist_without_its_user(motor, temiz):
    with Session(motor) as db:
        db.add(tablolar.Palet(id=uuid.uuid4().hex, kullanici_id=uuid.uuid4(), name="P",
                              seed="#000", mode="mono", strength="orta", colors=[]))
        with pytest.raises(IntegrityError) as hata:
            db.flush()
    assert "fk_paletler_kullanici_id_kullanicilar" in str(hata.value)


def test_deleting_a_folder_unfiles_its_media_and_drops_its_subfolders(motor, temiz):
    """`storage.unfile_folders` → `SET NULL`, `folders.delete_tree` → `CASCADE`; ikisi DB'de."""
    with Session(motor) as db:
        k = _kullanici(db)
        ust = tablolar.Klasor(id="a" * 12, kullanici_id=k.id, name="üst")
        alt = tablolar.Klasor(id="b" * 12, kullanici_id=k.id, name="alt", parent_id=ust.id)
        gorsel = tablolar.Medya(id="c" * 12, kullanici_id=k.id, filename="c.png", prompt="p",
                                size="s", quality="q", folder_id=ust.id, model="m", credits=0)
        db.add_all([ust, alt, gorsel])
        db.commit()
        db.delete(ust)
        db.commit()
        db.expunge_all()        # kimlik haritası temiz: DB'nin yaptığını okuyalım, ORM'nin sandığını değil
        assert db.get(tablolar.Klasor, "b" * 12) is None
        kalan = db.get(tablolar.Medya, "c" * 12)
        assert kalan is not None and kalan.folder_id is None


def test_jsonb_round_trips_the_message_list_and_the_palette_object(motor, temiz):
    """`sohbetler.mesajlar` ve `medya.palette` JSONB: iç içe yapı, Unicode ve sıra korunur."""
    mesajlar = [
        {"role": "user", "content": "Kırmızı bir kedi çiz — 🎨"},
        {"role": "result", "image_ids": ["ab12cd34ef56"], "params": {"size": "1024x1024", "n": 2}},
    ]
    palet = {"name": "Gün batımı", "colors": [{"hex": "#ff5500", "name": "turuncu"}], "strength": "orta"}
    with Session(motor) as db:
        k = _kullanici(db)
        db.add(tablolar.Sohbet(id="d" * 12, kullanici_id=k.id, title="S", mesajlar=mesajlar))
        db.add(tablolar.Medya(id="e" * 12, kullanici_id=k.id, filename="e.png", prompt="p",
                              size="s", quality="q", model="m", credits=0, palette=palet))
        db.commit()
    with Session(motor) as db:
        assert db.get(tablolar.Sohbet, "d" * 12).mesajlar == mesajlar
        assert db.get(tablolar.Medya, "e" * 12).palette == palet
    with motor.connect() as c:      # JSONB operatörü çalışıyor: metin değil, yapı saklanmış
        assert c.execute(text("SELECT mesajlar->1->'params'->>'size' FROM sohbetler")).scalar_one() == "1024x1024"


def test_check_constraints_accept_every_allowed_value_and_reject_the_rest(motor, temiz):
    """CHECK'ler GERÇEKTEN reddediyor; ve izinli kümenin her üyesi geçiyor (gerekçe dosya başında)."""
    with Session(motor) as db:
        k = _kullanici(db)
        db.commit()
        kid = k.id

    def _reddediyor(nesne, kisit: str) -> None:
        with Session(motor) as db:
            db.add(nesne)
            with pytest.raises(IntegrityError) as hata:
                db.flush()
            assert kisit in str(hata.value), str(hata.value)

    def _kabul_ediyor(nesne) -> None:
        with Session(motor) as db:
            db.add(nesne)
            db.flush()
            db.rollback()

    def _klasor(id_: str) -> tablolar.Klasor:
        return tablolar.Klasor(id=id_, kullanici_id=kid, name="K")

    # `_SAFE_ID`: 8-32 küçük hex; büyük harf, 7 hane, nokta, boşluk reddedilir.
    for kotu in ("ABCDEF12", "abcdef1", "abcdef12.png", "abcd ef12", "", "x" * 12, "a" * 33):
        _reddediyor(_klasor(kotu), "ck_klasorler_id_bicimi")
    for iyi in ("abcdef12", uuid.uuid4().hex[:12], uuid.uuid4().hex):
        _kabul_ediyor(_klasor(iyi))

    # Tema ve dil kümeleri — her izinli değer geçer, dışı geçmez.
    for tema in models.ALLOWED_THEMES:
        _kabul_ediyor(tablolar.Tercih(kullanici_id=kid, theme=tema))
    _reddediyor(tablolar.Tercih(kullanici_id=kid, theme="neon"), "ck_tercihler_theme_kumesi")
    for dil in models.ALLOWED_LANGUAGES:
        _kabul_ediyor(tablolar.Tercih(kullanici_id=kid, language=dil))
        _kabul_ediyor(tablolar.Kullanici(eposta=f"{dil}@example.com", dil=dil))
    _reddediyor(tablolar.Tercih(kullanici_id=kid, language="de"), "ck_tercihler_language_kumesi")
    _reddediyor(tablolar.Kullanici(eposta="de@example.com", dil="de"), "ck_kullanicilar_dil_kumesi")
    _kabul_ediyor(tablolar.Tercih(kullanici_id=kid))     # NULL = hiç yazılmamış, CHECK'ten geçer

    # Varlık türü ve jeton amacı.
    for tur in assets_store.KINDS:
        _kabul_ediyor(tablolar.Varlik(id=uuid.uuid4().hex, kullanici_id=kid, filename="f",
                                      name="n", tur=tur))
    _reddediyor(tablolar.Varlik(id=uuid.uuid4().hex, kullanici_id=kid, filename="f", name="n",
                                tur="uploads"), "ck_varliklar_tur_kumesi")
    for amac in tablolar.JETON_AMACLARI:
        _kabul_ediyor(tablolar.Jeton(kullanici_id=kid, amac=amac, ozet=os.urandom(32),
                                     bitis=text("now() + interval '1 hour'")))
    _reddediyor(tablolar.Jeton(kullanici_id=kid, amac="giris", ozet=os.urandom(32),
                               bitis=text("now()")), "ck_jetonlar_amac_kumesi")

    # Deneme türü (3. görev, göç 0002): üç sayaç geçer, dördüncü geçmez; öntanımlı `giris`.
    for tur in tablolar.DENEME_TURLERI:
        _kabul_ediyor(tablolar.GirisDenemesi(tur=tur, eposta="d@example.com"))
    _reddediyor(tablolar.GirisDenemesi(tur="dogrulama", eposta="d@example.com"),
                "ck_giris_denemeleri_tur_kumesi")
    with Session(motor) as db:
        db.add(tablolar.GirisDenemesi(eposta="d@example.com"))
        db.flush()
        assert db.scalar(text("SELECT tur FROM giris_denemeleri LIMIT 1")) == "giris"
        db.rollback()

    # İş türü ve durumu (Faz 2 / 1, göç 0004): dört rota geçer, `chat` geçmez
    # (senkron kalıyor); beş durum geçer, altıncısı geçmez; öntanımlı `bekliyor`.
    def _is(**alan) -> tablolar.Is:
        alanlar: dict = {"kullanici_id": kid, "tur": "generate", "istek": {}, "model": "m",
                         "kredi_tahmini": 0}
        alanlar.update(alan)
        return tablolar.Is(**alanlar)

    for tur in tablolar.IS_TURLERI:
        _kabul_ediyor(_is(tur=tur))
    _reddediyor(_is(tur="chat"), "ck_isler_tur_kumesi")
    for durum in tablolar.IS_DURUMLARI:
        _kabul_ediyor(_is(durum=durum))
    _reddediyor(_is(durum="askida"), "ck_isler_durum_kumesi")
    # Anahtar kaynağı (Faz 2 / 6, göç 0005): iki değer geçer, NULL geçer (eski satır), üçüncüsü geçmez.
    for kaynak in tablolar.ANAHTAR_KAYNAKLARI:
        _kabul_ediyor(_is(anahtar_kaynagi=kaynak))
    _kabul_ediyor(_is(anahtar_kaynagi=None))
    _reddediyor(_is(anahtar_kaynagi="havuz"), "ck_isler_anahtar_kaynagi_kumesi")
    with Session(motor) as db:
        db.add(_is())
        db.flush()
        assert db.scalar(text("SELECT durum FROM isler LIMIT 1")) == "bekliyor"
        db.rollback()

    # Faz 3 / 1 (göç 0007): hareket türü — altı değer geçer (`sona_erme` dâhil: CHECK'te var,
    # yazan yok), Faz 4'ün `paket`i geçmez; plan — üç değer geçer, dördüncüsü geçmez.
    def _hareket(**alan) -> tablolar.KrediHareketi:
        alanlar: dict = {"kullanici_id": kid, "tur": "hibe", "miktar": 1,
                         "idempotency_anahtari": f"t:{uuid.uuid4()}"}
        alanlar.update(alan)
        return tablolar.KrediHareketi(**alanlar)

    assert set(tablolar.HAREKET_TURLERI) == {"hibe", "rezerv", "onay", "iade", "duzeltme", "sona_erme"}
    for tur in tablolar.HAREKET_TURLERI:
        _kabul_ediyor(_hareket(tur=tur))
    _reddediyor(_hareket(tur="paket"), "ck_kredi_hareketleri_tur_kumesi")
    assert set(tablolar.PLANLAR_KUMESI) == {"free", "temel", "pro"}
    for plan in tablolar.PLANLAR_KUMESI:
        _kabul_ediyor(tablolar.Kullanici(eposta=f"{plan}@example.com", plan=plan))
    _reddediyor(tablolar.Kullanici(eposta="kurumsal@example.com", plan="kurumsal"),
                "ck_kullanicilar_plan_kumesi")


def test_preferences_are_one_row_per_user(motor, temiz):
    with Session(motor) as db:
        k = _kullanici(db)
        db.add(tablolar.Tercih(kullanici_id=k.id, theme="mono"))
        db.commit()
        db.add(tablolar.Tercih(kullanici_id=k.id, theme="ocean"))
        with pytest.raises(IntegrityError) as hata:
            db.flush()
    assert "pk_tercihler" in str(hata.value)


def test_a_user_has_at_most_one_value_per_credential_name(motor, temiz):
    """`(kullanici_id, ad)` birincil anahtar: aynı env adına ikinci satır yok, ikinci kullanıcıya var."""
    with Session(motor) as db:
        ali = _kullanici(db, "ali@example.com")
        veli = _kullanici(db, "veli@example.com")
        db.add(tablolar.SaglayiciKimligi(kullanici_id=ali.id, ad="OPENAI_API_KEY",
                                         sifreli_deger=b"x", anahtar_surumu=1))
        db.add(tablolar.SaglayiciKimligi(kullanici_id=veli.id, ad="OPENAI_API_KEY",
                                         sifreli_deger=b"y", anahtar_surumu=1))
        db.commit()
        db.add(tablolar.SaglayiciKimligi(kullanici_id=ali.id, ad="OPENAI_API_KEY",
                                         sifreli_deger=b"z", anahtar_surumu=2))
        with pytest.raises(IntegrityError):
            db.flush()


def test_server_defaults_fill_ids_timestamps_and_flags(motor, temiz):
    """`gen_random_uuid()`, `now()`, `is_admin=false`: istemci göndermese de satır tam."""
    with Session(motor) as db:
        k = _kullanici(db)
        db.commit()
        db.refresh(k)
        assert isinstance(k.id, uuid.UUID)
        assert k.olusturuldu is not None and k.olusturuldu.tzinfo is not None, "timestamptz"
        assert k.is_admin is False
        assert k.dogrulandi_at is None and k.silindi_at is None and k.parola_ozeti is None
        # Faz 3 / 1: mevcut kullanıcı göçten dokunulmadan geçer — bakiye 0, plan `free`.
        assert (k.bakiye, k.plan) == (0, "free")
        m = tablolar.Medya(id="a1" * 6, kullanici_id=k.id, filename="a1.png", prompt="p", size="s",
                           quality="q", model="m", credits=1)
        db.add(m)
        db.commit()
        db.refresh(m)
        assert m.filigranli is False, "göç öncesi her kayıt filigransız: NOT NULL DEFAULT false"


def test_updated_at_moves_when_a_row_changes(motor, temiz):
    """`guncellendi` ORM `onupdate`: sohbete mesaj eklenince damga ilerler, `olusturuldu` durur."""
    with Session(motor) as db:
        k = _kullanici(db)
        s = tablolar.Sohbet(id="f" * 12, kullanici_id=k.id, title="S", mesajlar=[])
        db.add(s)
        db.commit()
        db.refresh(s)
        ilk_olusturuldu, ilk_guncellendi = s.olusturuldu, s.guncellendi
        db.execute(text("SELECT pg_sleep(0.01)"))
        s.mesajlar = [{"role": "user", "content": "selam"}]
        db.commit()
        db.refresh(s)
        assert s.olusturuldu == ilk_olusturuldu
        assert s.guncellendi > ilk_guncellendi


def test_downgrade_to_base_leaves_no_table_and_no_extension_behind(veritabani):
    """Geri alma TEMİZ: 14 tablo ve `citext` uzantısı gider, `upgrade` yeniden kurar.

    `test_db.py`nin döngü testi `alembic_version`a bakıyor; burası şemanın
    kendisine — bir tablo `downgrade`da unutulsa orada görünmez, burada görünür.
    """
    from alembic.config import Config

    from alembic import command
    cfg = Config(os.path.join(REPO, "alembic.ini"))
    cfg.attributes["baglanti_dizesi"] = veritabani
    motor = create_engine(veritabani)
    try:
        command.downgrade(cfg, "base")
        assert set(inspect(motor).get_table_names()) == {"alembic_version"}
        with motor.connect() as c:
            assert c.execute(text("SELECT count(*) FROM pg_extension WHERE extname='citext'")).scalar_one() == 0
        command.upgrade(cfg, "head")
        assert set(inspect(motor).get_table_names()) == set(tablolar.Base.metadata.tables) | {"alembic_version"}
        command.check(cfg)
    finally:
        motor.dispose()
