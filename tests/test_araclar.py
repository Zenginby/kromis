"""`tools/marj_raporu.py` ve `tools/tarife_kontrol.py` — sahibin mutabakat araçları (Faz 3 / 5; belge §5).

`marj_raporu`: GERÇEK Postgres (`depo_db`; `veritabani` fixture'ı `DATABASE_URL`i
bu DB'ye çevirir, araç motorunu oradan kurar — tests/test_kullanici_cli.py deseni).
Aynı sorgu admin "Marj" tablosunun (`depo_admin.marj`): CSV başlığı `SUTUNLAR`,
satırlar tohumla; bilinmeyen maliyet BOŞ hücre (sıfır değil); `DATABASE_URL`siz 2.

`tarife_kontrol`: aracın bulduğu küme, kataloğu BAĞIMSIZ bir yolla (satır bazlı:
`ImageModel(` blokları ve önündeki yorumlar) okuyan testin kümesiyle aynı — liste
ELLE DEĞİL (CLAUDE.md § 5: not silinince iki taraf birlikte düşer). Küme bugün
BOŞ: devreden dört Azure notu 2026-09-22'de kapandı (Faz 4 / 1b). Sayı
katalogdan türetilir, burada yazılı değil — bu cümle bir zamanlar dördünü tek
tek sayıyordu ve "burada yazılı değil" derken tam olarak onu yapıyordu.

BOŞ KÜME TARAYICIYI SINAMAZ: körelmiş bir tarayıcı da boş döner. O yüzden
ikinci bir test gerçek katalog kaynağına metin üstünde bilinen bir not ENJEKTE
edip tam olarak onu bulmayı bekliyor — bekçinin bekçisi artık orada.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import re
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

import catalog
from services import db, kuyruk, zaman
from tools import marj_raporu, tarife_kontrol

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── marj_raporu ──────────────────────────────────────────────────────────

def _is(depo_db, kid: uuid.UUID, *, durum: str, once: dt.timedelta, model: str, kredi: int = 8,
        gercek: int | None = None, maliyet_usd: str | None = None, sure_sn: int = 10) -> None:
    """`bitti = simdi - once`; rapor GERÇEK saatle koşar (`--an` yok), tohum ona göre."""
    an = zaman.an() - once
    with Session(depo_db) as s:
        is_ = kuyruk.ekle(s, kid, "generate", {"prompt": "x"}, model, kredi, an=an - dt.timedelta(seconds=sure_sn),
                          anahtar_kaynagi="platform")
        is_.durum = durum
        is_.basladi = an - dt.timedelta(seconds=sure_sn)
        is_.bitti = an
        is_.kredi_gercek = gercek
        is_.saglayici_maliyet_usd = Decimal(maliyet_usd) if maliyet_usd is not None else None
        s.commit()


def _oku(metin: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(metin)))


def test_the_report_writes_the_header_and_one_row_per_model_with_an_empty_cell_for_unknown_cost(
        depo_db, kullanici, tmp_path, capsys):
    with depo_db.begin() as c:
        from sqlalchemy import text
        c.execute(text("DELETE FROM isler"))
    gun = dt.timedelta(days=1)
    _is(depo_db, kullanici.id, durum="bitti", once=2 * gun, model="m-a", gercek=8, maliyet_usd="0.0389", sure_sn=10)
    _is(depo_db, kullanici.id, durum="bitti", once=20 * gun, model="m-a", gercek=6, sure_sn=20)
    _is(depo_db, kullanici.id, durum="hata", once=1 * gun, model="m-a", kredi=16)
    _is(depo_db, kullanici.id, durum="bitti", once=10 * gun, model="m-b", gercek=27, sure_sn=5)
    _is(depo_db, kullanici.id, durum="bitti", once=40 * gun, model="m-b", gercek=999)          # pencere dışı
    _is(depo_db, kullanici.id, durum="iptal", once=1 * gun, model="m-b", kredi=50)            # sayılmaz

    cikti = tmp_path / "marj.csv"
    assert marj_raporu.main(["--gun", "30", "--cikti", str(cikti)]) == 0
    with open(cikti, encoding="utf-8", newline="") as f:
        metin = f.read()
    assert metin.splitlines()[0] == ",".join(marj_raporu.SUTUNLAR)
    satirlar = _oku(metin)
    assert [r["model"] for r in satirlar] == ["m-a", "m-b"], "en çok iş üstte (hata dâhil), sonra ad"
    a, b = satirlar
    assert a == {"gun": "30", "model": "m-a", "adet": "2", "kredi": "14", "usd": "0.07",
                 "maliyet_usd": "0.0389", "maliyet_bilinen": "1", "ort_sure_sn": "15.0",
                 "hata": "1", "hata_kredi": "16"}
    assert b["adet"] == "1" and b["kredi"] == "27" and b["usd"] == "0.135"
    assert b["maliyet_usd"] == "" and b["maliyet_bilinen"] == "0", "bilinmeyen maliyet BOŞ, sıfır değil"
    assert b["ort_sure_sn"] == "5.0" and b["hata"] == "0" and b["hata_kredi"] == "0"
    assert "1 kredi" not in metin and str(kullanici.id) not in metin, "kullanıcı sütunu yok: rapor model başına"
    err = capsys.readouterr().err
    assert "marj.csv: 2 satir (30 gun)" in err

    # 7 günlük pencere stdout'a: yalnız m-a (2 gün önce biten + 1 gün önce düşen).
    assert marj_raporu.main(["--gun", "7"]) == 0
    out = capsys.readouterr().out
    yedi = _oku(out)
    assert [r["model"] for r in yedi] == ["m-a"] and yedi[0]["gun"] == "7"
    assert yedi[0]["adet"] == "1" and yedi[0]["kredi"] == "8" and yedi[0]["maliyet_bilinen"] == "1"


def test_the_report_refuses_to_run_without_a_database_url_and_with_a_nonsense_window(monkeypatch, capsys):
    monkeypatch.delenv(db.DATABASE_URL_ENV, raising=False)
    assert marj_raporu.main(["--gun", "30"]) == marj_raporu.CIKIS_ORTAM
    assert db.DATABASE_URL_ENV in capsys.readouterr().err
    assert marj_raporu.main(["--gun", "0"]) == marj_raporu.CIKIS_ORTAM


def test_the_csv_columns_are_exactly_the_keys_of_a_marj_row():
    """Başlık `depo_admin.marj`ın döktüğü anahtarlarla aynı küme, aynı ad: sütun eklenirse iki yer birden değişir."""
    import inspect

    from services import depo_admin
    kaynak = inspect.getsource(depo_admin.marj)
    anahtarlar = set(re.findall(r'^\s+"(\w+)":', kaynak, re.M))
    assert anahtarlar == set(marj_raporu.SUTUNLAR), anahtarlar ^ set(marj_raporu.SUTUNLAR)


# ── tarife_kontrol ───────────────────────────────────────────────────────

def _bagimsiz_bulgu() -> dict[str, list[str]]:
    """Kataloğu SATIR BAZLI okuyan ikinci uygulama (araç `ast` kullanır): `    ImageModel(` ile açılan
    blok `    ),` ile kapanır; bloğun kendi `#` satırları + hemen önündeki `#` satırları (araya başka
    kod girmemiş — demetin `= (` satırı ya da önceki bloğun `),`sı bekleyeni sıfırlar) o modele ait."""
    with open(os.path.join(REPO, "catalog.py"), encoding="utf-8") as f:
        satirlar = f.read().splitlines()
    bulgu: dict[str, list[str]] = {}
    bekleyen: list[str] = []
    blok: list[str] | None = None
    for s in satirlar:
        if blok is not None:
            blok.append(s)
            if s == "    ),":
                yorumlar = bekleyen + [b.strip() for b in blok if b.strip().startswith("#")]
                eslesen = [y for y in yorumlar if tarife_kontrol.DESEN.search(tarife_kontrol._katla(y))]
                if eslesen:
                    (kimlik,) = [m for b in blok for m in re.findall(r'^\s+id=(?:"([^"]+)"|(\w+)),$', b)]
                    bulgu[kimlik[0] or str(getattr(catalog, kimlik[1]))] = eslesen
                blok, bekleyen = None, []
            continue
        if s == "    ImageModel(":
            blok = []
        elif s.strip().startswith("#"):
            bekleyen.append(s.strip())
        elif s.strip():
            bekleyen = []
    return bulgu


def test_the_tool_finds_exactly_the_models_whose_price_comment_says_unverified_derived_from_the_catalog():
    beklenen = _bagimsiz_bulgu()
    with open(tarife_kontrol.KATALOG_YOLU, encoding="utf-8") as f:
        bulgular = tarife_kontrol.bul(f.read())
    assert {b.model for b in bulgular} == set(beklenen), (
        "araç ile bağımsız tarama ayrıştı — yorum bölgesi kuralı (tools/tarife_kontrol.py başlığı) değişti mi?")
    assert {b.model: list(b.satirlar) for b in bulgular} == beklenen
    # KÜME BOŞ ve bu HEDEFİN KENDİSİ (2026-09-22, Faz 4 / 1b): devreden dört
    # Azure notu düştü. Buraya kadar "bulgular boş değil" diye bir iddia vardı
    # — bekçinin bekçisiydi, çünkü hiçbir şey bulmayan bir tarayıcı da bu
    # testi geçerdi. Liste kalıcı olarak boşalınca o iddia tutulamaz hâle
    # geldi; tarayıcının GÖREBİLDİĞİ ayrı bir testle kanıtlanıyor (aşağıda),
    # gerçek kataloğun kirli kalmasıyla değil.
    assert beklenen == {}, f"katalogda doğrulanmamış tarife notu var: {sorted(beklenen)}"
    # Her id gerçekten katalogda (görsel ya da video); krediler katalogdaki
    # gerçek değerler, USD çapayla (`KREDI_USD_CAPASI`).
    idler = {m.id for m in catalog.IMAGE_MODELS} | {m.id for m in catalog.VIDEO_MODELS}
    assert {b.model for b in bulgular} <= idler
    for b in bulgular:
        spec = catalog.image_model(b.model) or catalog.video_model(b.model)
        assert spec is not None and b.credits == spec.credits and b.credits_by_quality == spec.credits_by_quality
        assert b.usd == Decimal(spec.credits) * catalog.KREDI_USD_CAPASI


def test_the_scanner_still_SEES_a_note_when_one_is_put_back_into_the_real_catalog():
    """Boş liste "tarayıcı çalışıyor" DEMEK DEĞİL — körelmiş bir tarayıcı da boş döner.

    Gerçek katalog kaynağına bilinen bir not ENJEKTE ediliyor (dosyaya
    dokunulmadan, metin üstünde) ve tam olarak o modelin bulunması bekleniyor.
    Sentetik bir kaynak parçası yerine gerçek dosyanın kullanılması bilinçli:
    `bul` yorumları AST'nin girdi bölgelerine göre eşliyor (kural
    `tools/tarife_kontrol.py`nin başlığında) ve uydurma bir iskelet o kuralı
    sınamazdı.
    """
    with open(tarife_kontrol.KATALOG_YOLU, encoding="utf-8") as f:
        kaynak = f.read()
    capa = "        credits=9,\n"
    assert kaynak.count(capa) == 1, "çapa satırı taşındı — test güncellensin"
    kirli = kaynak.replace(capa, "        # birim fiyat doğrulanamadı (deneme).\n" + capa)

    bulgular = tarife_kontrol.bul(kirli)
    assert [b.model for b in bulgular] == ["azure-flux-2-pro"]
    # Satırlar kırpılmış geliyor (araç girintiyi soyuyor) — rapor onları kendi
    # girintisiyle basıyor, ham kaynak girintisiyle değil.
    assert bulgular[0].satirlar == ("# birim fiyat doğrulanamadı (deneme).",)
    assert bulgular[0].credits == 9
    # Aynı kaynak notsuz hâliyle BOŞ dönüyor: fark gerçekten notun kendisi.
    assert tarife_kontrol.bul(kaynak) == []


def test_the_pattern_is_turkish_case_insensitive_and_needs_the_word_price_on_the_same_line():
    """`str.lower()` `I`yı `i` yapar (ölçüldü): "DOĞRULANAMADI" sade lower ile eşleşmezdi. `fiyat` şartı
    boyut/çözünürlük doğrulama notlarını ("boyut jetonu canlı DOĞRULANMADI") dışarıda bırakır."""
    assert "DOĞRULANAMADI".lower() != "doğrulanamadı", "ölçümün kendisi: Python'un lower'ı Türkçe değil"
    assert tarife_kontrol._katla("DOĞRULANAMADI") == "doğrulanamadı"
    for satir in ("# 2.6-Flash'ın yayınlanmış birim fiyatı DOĞRULANAMADI (Azure fiyat",
                  "# GEÇİCİ: birim fiyat doğrulanamadı, oran 2.6'nın yarısı varsayıldı.",
                  "# megapiksel fiyatı doğrulanmadı."):
        assert tarife_kontrol.DESEN.search(tarife_kontrol._katla(satir)), satir
    for satir in ("# canlı DOĞRULANMADI. Doğrulanmamış bir boyut jetonu beyan etmek arayüzde",
                  "# 1080p'si bu depoda doğrulanmadı, o yüzden tek jeton beyan ediyorlar ve",
                  "# birim fiyat 38 USD/M — belgeden doğrulandı"):
        assert not tarife_kontrol.DESEN.search(tarife_kontrol._katla(satir)), satir


def test_the_tool_prints_every_flagged_model_with_its_credits_and_expected_usd():
    """Rapor metni, ENJEKTE edilmiş bir notla sınanıyor — gerçek katalog artık temiz.

    `main`in bugünkü çıktısı "notlu model yok" (öteki test onu ölçüyor); satır
    biçimini sınamak için listenin DOLU olduğu bir hâl gerekiyor ve o hâl
    gerçek kataloğu kirli tutarak değil, kaynağı metin üstünde bozarak
    kuruluyor.
    """
    with open(tarife_kontrol.KATALOG_YOLU, encoding="utf-8") as f:
        kaynak = f.read()
    kirli = kaynak.replace("        credits=9,\n",
                           "        # birim fiyat doğrulanamadı (deneme).\n        credits=9,\n")
    bulgular = tarife_kontrol.bul(kirli)
    assert bulgular, "enjeksiyon tutmadı"

    out = tarife_kontrol.rapor(bulgular)
    assert out.startswith(f"{len(bulgular)} model dogrulama bekliyor (1 kredi = 0.005 USD):")
    for b in bulgular:
        assert f"  {b.model}: {b.credits} kredi ≈ {b.usd} USD" in out
        for s in b.satirlar:
            assert s in out, "eşleşen yorum satırı basılır: sahip 'neden listede' sorusunu buradan okur"


def test_the_tool_says_the_catalogue_is_clean_and_exits_zero(capsys):
    """Bugünkü GERÇEK çıktı: dört Azure notu 1b'de düştü, geriye not kalmadı."""
    assert tarife_kontrol.main([]) == 0
    assert capsys.readouterr().out.startswith("notlu model yok")
    assert tarife_kontrol.rapor([]).startswith("notlu model yok")
