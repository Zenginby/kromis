"""`tools/marj_raporu.py`, `tools/tarife_kontrol.py` ve `tools/polar_esitle.py` — sahibin araçları (Faz 3 / 5; Faz 4 / 4).

`marj_raporu`: GERÇEK Postgres (`depo_db`; `veritabani` fixture'ı `DATABASE_URL`i
bu DB'ye çevirir, araç motorunu oradan kurar — tests/test_kullanici_cli.py deseni).
Aynı sorgu admin "Marj" tablosunun (`depo_admin.marj`): CSV başlığı `SUTUNLAR`,
satırlar tohumla; bilinmeyen maliyet BOŞ hücre (sıfır değil); `DATABASE_URL`siz 2.

`tarife_kontrol`: aracın bulduğu küme, kataloğu BAĞIMSIZ bir yolla (satır bazlı:
`ImageModel(` blokları ve önündeki yorumlar) okuyan testin kümesiyle aynı — liste
ELLE DEĞİL (CLAUDE.md § 5: not silinince iki taraf birlikte düşer). Küme
2026-09-22'de BOŞALDI (devreden dört Azure notu kapandı, Faz 4 / 1b-C) ve
2026-09-23'te YENİDEN İKİ oldu (Faz 4 / 1b-D): GPT Image 2.5'in iki girdisi
krediyi `gpt-image-2`den KOPYALIYOR (sahibin "alt sınır kalsın" talimatı) ve
`credits` satırındaki not aracın desenine BİLEREK uyuyor — sahip ölçünce düşer.
Sayı katalogdan türetilir, burada yazılı değil.

BOŞ KÜME TARAYICIYI SINAMAZ: körelmiş bir tarayıcı da boş döner. O yüzden
ikinci bir test gerçek katalog kaynağına metin üstünde bilinen bir not ENJEKTE
edip tam olarak onu bulmayı bekliyor — bekçinin bekçisi orada; küme yeniden
dolduğu gün de kalıyor, çünkü "2 buldu" cümlesi de körelmiş bir tarayıcının
(iki satırı ezberlemiş) cümlesi olabilir.

`emeklilik` (Faz 4 / 1b-D): ikinci satır MODÜLÜ okur (tarih bir alan, yorum
değil); bugün hiçbir girdi tarih taşımıyor ve rapor "yok" diyor. Bekçi tarihi
YAMALAR (`tarife_kontrol.bugun`) ve kataloğa sentetik bir girdi sokup satırın
göründüğünü kanıtlar — tarife satırının enjeksiyon deseninin aynısı.
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
from services import db, kuyruk, polar, zaman
from services.tablolar import Urun
from tools import marj_raporu, polar_esitle, tarife_kontrol

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
    # KÜME BOŞ (2026-09-23, Faz 4 / 1b-D üçüncü commit): 2026-09-22'de dört
    # Azure notu düşmüştü; D'nin ilk commit'i GPT Image 2.5'in iki kopya
    # kredisini aracın desenine BİLEREK uydurdu (`== {sunburst, flare}`), aynı
    # gün sahip OpenAI'nin jeton tablosunu kaynaktan okudu (1/3/11) ve not
    # düştü. Küme burada ADIYLA (boş) yazılı, çünkü "hangi girdiler doğrulama
    # bekliyor" sorusunun cevabı bir PR kararı: bir girdiye not sızarsa burası
    # kırmızı olur.
    assert set(beklenen) == set(), (
        f"katalogda doğrulanmamış tarife notu var: {sorted(beklenen)}")
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

    temiz = [b.model for b in tarife_kontrol.bul(kaynak)]
    bulgular = tarife_kontrol.bul(kirli)
    # Enjeksiyon TAM BİR model ekliyor, başkasını düşürmüyor: fark yalnız FLUX.
    assert [b.model for b in bulgular if b.model not in temiz] == ["azure-flux-2-pro"]
    assert [b.model for b in bulgular if b.model in temiz] == temiz
    flux = next(b for b in bulgular if b.model == "azure-flux-2-pro")
    # Satırlar kırpılmış geliyor (araç girintiyi soyuyor) — rapor onları kendi
    # girintisiyle basıyor, ham kaynak girintisiyle değil.
    assert flux.satirlar == ("# birim fiyat doğrulanamadı (deneme).",)
    assert flux.credits == 9


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


def test_the_tool_reports_no_pending_tariffs_and_no_retirements_and_exits_zero(capsys):
    """Bugünkü GERÇEK çıktı (2026-09-23): notlu model yok, emekli olan yok.

    D PR'ının ilk commit'inde bu test "2 model dogrulama bekliyor" diyordu (GPT
    Image 2.5'in kopya kredileri); aynı gün sahip jeton tablosunu kaynaktan
    okuyunca not düştü. Emeklilik satırı D ile geldi. Çıkış kodu 0 — araç
    rapor, kapı değil."""
    assert tarife_kontrol.main([]) == 0
    out = capsys.readouterr().out
    assert out.startswith("notlu model yok")
    assert "openai-gpt-image-2-5" not in out
    assert out.rstrip().endswith("30 gun icinde emekli olacak model yok.")
    assert tarife_kontrol.rapor([]).startswith("notlu model yok")


# ── tarife_kontrol · emeklilik satırı (Faz 4 / 1b-D) ──────────────────────

BUGUN = dt.date(2026, 9, 23)


def test_no_catalogue_entry_carries_a_retirement_date_today_so_the_row_is_empty(monkeypatch):
    """Alan bugün her girdide `None` (katalog docstring'i "hiçbir girdi doldurmuyor" diyor) — ve
    rapor bunu "yok" diye söylüyor. Tarih yamalı: bu test 30 gün sonra da aynı şeyi ölçmeli."""
    monkeypatch.setattr(tarife_kontrol, "bugun", lambda: BUGUN)
    assert all(m.emeklilik is None for m in catalog.IMAGE_MODELS + catalog.VIDEO_MODELS)
    assert tarife_kontrol.emekliler() == []
    assert tarife_kontrol.emeklilik_raporu([]) == "30 gun icinde emekli olacak model yok."


def test_a_synthetic_entry_retiring_within_the_horizon_or_already_past_is_reported(monkeypatch):
    """Boş liste tarayıcıyı sınamaz (tarife satırının dersi): kataloğa SENTETİK girdiler sokup tam
    olarak onların görüldüğü kanıtlanıyor. Üç hâl: ufuk içinde (görünür), ufuk dışında (görünmez),
    GEÇMİŞ (görünür ve "GECTI" der — geçmişi saymayan bir rapor, kalkmış modeli sessizce saklardı)."""
    import dataclasses
    monkeypatch.setattr(tarife_kontrol, "bugun", lambda: BUGUN)
    taban = catalog.IMAGE_MODELS[0]
    yakin = dataclasses.replace(taban, id="sentetik-yakin", emeklilik=BUGUN + dt.timedelta(days=30))
    uzak = dataclasses.replace(taban, id="sentetik-uzak", emeklilik=BUGUN + dt.timedelta(days=31))
    gecmis = dataclasses.replace(taban, id="sentetik-gecmis", emeklilik=BUGUN - dt.timedelta(days=2))
    monkeypatch.setattr(catalog, "IMAGE_MODELS", catalog.IMAGE_MODELS + (yakin, uzak))
    monkeypatch.setattr(catalog, "VIDEO_MODELS", catalog.VIDEO_MODELS + (gecmis,))

    liste = tarife_kontrol.emekliler()
    assert [(e.model, e.kalan_gun) for e in liste] == [("sentetik-yakin", 30), ("sentetik-gecmis", -2)]
    out = tarife_kontrol.emeklilik_raporu(liste)
    assert out.startswith("2 model 30 gun icinde emekli oluyor")
    assert "sentetik-yakin: 2026-10-23 · 30 gun kaldi" in out
    assert "sentetik-gecmis: 2026-09-21 · 2 gun once GECTI" in out
    assert "sentetik-uzak" not in out
    # Ufuk sabiti tek yerden: 31. gün dışarıda kaldı, sayı burada tekrar yazılmıyor.
    assert tarife_kontrol.EMEKLILIK_UFKU_GUN == 30


def test_the_retirement_field_defaults_to_None_and_is_a_date_not_a_string():
    """Tarih bir `date`: dize olsaydı "30 gün içinde" hesabı yapılamaz, alan yine yoruma dönerdi."""
    alan = catalog.ImageModel.__dataclass_fields__["emeklilik"]
    assert alan.default is None
    assert alan.type == "date | None"


# ── polar_esitle (Faz 4 / 4) ─────────────────────────────────────────────
# Sahte Polar: `polar.urunleri_listele` yamalı (düz sözlükler — SDK `model_dump` biçimi);
# `urunler` gerçek Postgres. Araç `DATABASE_URL`i `veritabani` fixture'ından alır (marj_raporu deseni).

P_PAKET = "00000000-0000-4000-8000-00000000e001"
P_TEMEL = "00000000-0000-4000-8000-00000000e002"
P_BAGIS = "00000000-0000-4000-8000-00000000e0ff"


def _polar_urunu(kimlik: str, ad: str, meta: dict, fiyat: int = 500, birim: str = "usd", *, arsiv: bool = False,
                 fiyatlar: list | None = None, tekrarli: bool | None = None, aralik: str | None = "auto") -> dict:
    """Polar `Product`ının `model_dump(mode="json")` hâlinden okuduğumuz alanlar (SDK 0.32.0 adları).

    Öntanımlı kadans metadata'ya uyar (plan → aylık abonelik, paket → tek seferlik); `tekrarli`/`aralik`
    ile bilerek UYUMSUZ ürün kurulur (kadans bekçisi testleri)."""
    plan_mi = meta.get("kromis_tur") == "plan"
    tekrarli = plan_mi if tekrarli is None else tekrarli
    if aralik == "auto":
        aralik = "month" if tekrarli else None
    return {
        "id": kimlik, "name": ad, "is_archived": arsiv, "is_recurring": tekrarli, "recurring_interval": aralik,
        "metadata": meta,
        "prices": fiyatlar if fiyatlar is not None else [
            {"id": kimlik + "-p", "amount_type": "fixed", "price_amount": fiyat, "price_currency": birim,
             "is_archived": False, "type": "recurring" if tekrarli else "one_time"}],
    }


def _polar_listesi() -> list[dict]:
    return [
        _polar_urunu(P_PAKET, "500 kredi", {"kromis_tur": "paket", "kromis_kredi": "500"}),
        _polar_urunu(P_TEMEL, "Temel", {"kromis_tur": "plan", "kromis_plan": "temel", "kromis_kredi": 1200}, fiyat=900),
        _polar_urunu(P_BAGIS, "Bağış", {}),   # metadata yok → atlanır, WARNING
    ]


@pytest.fixture
def polar_ortami(depo_db, monkeypatch):
    monkeypatch.setenv(polar.JETON_ENV, "polar_oat_DUMMY")
    monkeypatch.delenv(polar.ORTAM_ENV, raising=False)
    with depo_db.begin() as c:
        from sqlalchemy import text
        c.execute(text("DELETE FROM siparisler"))
        c.execute(text("DELETE FROM urunler"))
    yield


def _ayna(depo_db) -> dict[str, Urun]:
    from sqlalchemy import select
    with Session(depo_db, expire_on_commit=False) as s:
        return {u.polar_urun_id: u for u in s.scalars(select(Urun))}


def test_polar_esitle_upserts_new_products_updates_changed_ones_archives_removed_and_skips_invalid_with_a_warning(
        depo_db, polar_ortami, monkeypatch, capsys):
    liste = _polar_listesi()
    monkeypatch.setattr(polar, "urunleri_listele", lambda: liste)
    assert polar_esitle.main([]) == 0
    cikti = capsys.readouterr()
    assert "UYARI URUN ATLANDI" in cikti.out and "kromis_tur eksik" in cikti.out and P_BAGIS in cikti.out
    assert "2 yeni, 0 degisen, 0 ayni, 1 atlanan, 0 kapanan" in cikti.out
    assert "2 urun yazildi, 0 bayat satir kapatildi (sandbox)" in cikti.err
    ayna = _ayna(depo_db)
    assert set(ayna) == {P_PAKET, P_TEMEL}, "geçersiz ürün aynaya sızmaz"
    paket, temel = ayna[P_PAKET], ayna[P_TEMEL]
    assert (paket.tur, paket.plan, paket.kredi, paket.fiyat_kurus, paket.para_birimi, paket.ad, paket.aktif) == \
        ("paket", None, 500, 500, "usd", "500 kredi", True)
    assert (temel.tur, temel.plan, temel.kredi, temel.fiyat_kurus, temel.ad) == ("plan", "temel", 1_200, 900, "Temel")
    ilk_guncelleme = paket.guncellendi
    # İkinci koşu: fiyat değişti, paket Polar'da arşivlendi → satır KALIR, `aktif=false`; sayı aynı, `guncellendi` ilerler.
    liste[0]["is_archived"] = True
    liste[1]["prices"][0]["price_amount"] = 1_200
    assert polar_esitle.main([]) == 0
    assert "0 yeni, 2 degisen, 0 ayni, 1 atlanan, 0 kapanan" in capsys.readouterr().out
    ayna = _ayna(depo_db)
    assert set(ayna) == {P_PAKET, P_TEMEL}
    assert ayna[P_PAKET].aktif is False and ayna[P_PAKET].id == paket.id, "arşiv: silinmez, aynı satır"
    assert ayna[P_TEMEL].fiyat_kurus == 1_200 and ayna[P_TEMEL].guncellendi > ilk_guncelleme
    # Üçüncü koşu, değişiklik yok: hepsi "ayni", yine yazılır ki tazelik damgası ilersin.
    assert polar_esitle.main([]) == 0
    assert "0 yeni, 0 degisen, 2 ayni, 1 atlanan, 0 kapanan" in capsys.readouterr().out
    assert _ayna(depo_db)[P_TEMEL].guncellendi > ayna[P_TEMEL].guncellendi


def test_polar_esitle_kontrol_prints_the_diff_to_stderr_without_writing_and_exits_2_only_when_there_is_one(
        depo_db, polar_ortami, monkeypatch, capsys):
    liste = _polar_listesi()
    monkeypatch.setattr(polar, "urunleri_listele", lambda: liste)
    assert polar_esitle.main(["--kontrol"]) == 2
    cikti = capsys.readouterr()
    assert cikti.out == "" and f"+ {P_PAKET}" in cikti.err and "2 yeni" in cikti.err
    assert _ayna(depo_db) == {}, "--kontrol yazmaz"
    assert polar_esitle.main([]) == 0
    capsys.readouterr()
    assert polar_esitle.main(["--kontrol"]) == 0, "ayna Polar'la aynı → fark yok"
    assert "0 yeni, 0 degisen, 2 ayni, 1 atlanan, 0 kapanan" in capsys.readouterr().err
    liste[1]["name"] = "Temel Plan"
    assert polar_esitle.main(["--kontrol"]) == 2
    assert f"~ {P_TEMEL}" in capsys.readouterr().err


def test_polar_esitle_refuses_without_a_database_url_or_a_token_and_reports_a_provider_failure_as_2(
        depo_db, monkeypatch, capsys):
    monkeypatch.delenv(db.DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv(polar.JETON_ENV, "polar_oat_DUMMY")
    assert polar_esitle.main([]) == 2 and db.DATABASE_URL_ENV in capsys.readouterr().err
    monkeypatch.setenv(db.DATABASE_URL_ENV, "postgresql+psycopg://x:y@127.0.0.1:1/z")
    monkeypatch.delenv(polar.JETON_ENV, raising=False)
    assert polar_esitle.main([]) == 2 and polar.JETON_ENV in capsys.readouterr().err
    monkeypatch.setenv(polar.JETON_ENV, "polar_oat_DUMMY")

    def _dusen():
        raise ConnectionError("DUMMY: sandbox-api.polar.sh unreachable")
    monkeypatch.setattr(polar, "urunleri_listele", _dusen)
    assert polar_esitle.main([]) == 2 and "Polar hatasi (ConnectionError)" in capsys.readouterr().err


def test_polar_esitle_closes_mirror_rows_that_polar_no_longer_lists_or_that_became_invalid(
        depo_db, polar_ortami, monkeypatch, capsys):
    """Silinmiş ürün (listede yok) ve geçersizleşmiş ürün (metadata bozuldu) aynı kapıdan `aktif=false`;
    bir kez kapanır (ikinci koşuda `kapanan` 0); `--kontrol` `-` satırıyla gösterir ve 2 döner."""
    liste = _polar_listesi()
    monkeypatch.setattr(polar, "urunleri_listele", lambda: liste)
    assert polar_esitle.main([]) == 0
    capsys.readouterr()
    silinen = liste.pop(0)                                  # paket Polar'dan silindi
    liste[0]["metadata"] = {"kromis_tur": "plna", "kromis_plan": "temel", "kromis_kredi": 1200}   # yazım hatası
    assert polar_esitle.main(["--kontrol"]) == 2
    err = capsys.readouterr().err
    assert f"- {P_PAKET}" in err and f"- {P_TEMEL}" in err and "0 yeni, 0 degisen, 0 ayni, 2 atlanan, 2 kapanan" in err
    assert all(u.aktif for u in _ayna(depo_db).values()), "--kontrol yazmaz"
    assert polar_esitle.main([]) == 0
    cikti = capsys.readouterr()
    assert f"- {P_PAKET}" in cikti.out and "0 urun yazildi, 2 bayat satir kapatildi" in cikti.err
    ayna = _ayna(depo_db)
    assert set(ayna) == {P_PAKET, P_TEMEL} and not any(u.aktif for u in ayna.values()), "satır silinmez, kapanır"
    assert polar_esitle.main([]) == 0
    assert "0 bayat satir kapatildi" in capsys.readouterr().err, "zaten kapalı satır yeniden sayılmaz"
    # Ürün geri gelirse (metadata düzeltildi) yeniden açılır.
    liste.insert(0, silinen)
    liste[1]["metadata"]["kromis_tur"] = "plan"
    assert polar_esitle.main([]) == 0
    assert all(u.aktif for u in _ayna(depo_db).values())


@pytest.mark.parametrize("meta, kadans, beklenen", [
    # plan tek seferlik satılmış → atla; paket abonelik → atla; plan yıllık → aylık fiyat yok → atla.
    ({"kromis_tur": "plan", "kromis_plan": "temel", "kromis_kredi": 1200}, {"tekrarli": False}, "abonelik degil"),
    ({"kromis_tur": "paket", "kromis_kredi": 500}, {"tekrarli": True}, "abonelik olamaz"),
    ({"kromis_tur": "plan", "kromis_plan": "temel", "kromis_kredi": 1200}, {"aralik": "year"}, "recurring_interval == 'month'"),
])
def test_satira_cevir_enforces_the_cadence_a_plan_is_a_monthly_subscription_and_a_pack_is_one_time(meta, kadans, beklenen):
    satir = polar_esitle.satira_cevir(_polar_urunu("p1", "Ürün", meta, **kadans))
    assert isinstance(satir, str) and beklenen in satir, satir


def test_satira_cevir_picks_the_monthly_price_of_a_legacy_product_that_also_carries_a_yearly_one():
    """Eski Polar ürünlerinde kadans FİYATTA (`legacy: true`, `recurring_interval`); yıllık önde dursa da aylık seçilir."""
    fiyatlar = [
        {"amount_type": "fixed", "is_archived": False, "price_amount": 9_000, "price_currency": "usd",
         "legacy": True, "recurring_interval": "year", "type": "recurring"},
        {"amount_type": "fixed", "is_archived": False, "price_amount": 900, "price_currency": "usd",
         "legacy": True, "recurring_interval": "month", "type": "recurring"},
    ]
    urun = _polar_urunu("p1", "Temel", {"kromis_tur": "plan", "kromis_plan": "temel", "kromis_kredi": 1200},
                        fiyatlar=fiyatlar, aralik=None)
    satir = polar_esitle.satira_cevir(urun)
    assert isinstance(satir, polar_esitle.Satir) and satir.fiyat_kurus == 900
    # Yalnız yıllık fiyatı olan legacy plan → atlanır.
    urun["prices"] = fiyatlar[:1]
    assert "recurring_interval == 'month'" in polar_esitle.satira_cevir(urun)


@pytest.mark.parametrize("meta, fiyatlar, beklenen", [
    ({"kromis_tur": "paket", "kromis_kredi": "500"}, None, ("paket", None, 500)),
    ({"kromis_tur": "paket", "kromis_kredi": 500.0}, None, ("paket", None, 500)),     # Polar float saklayabilir
    ({"kromis_tur": "plan", "kromis_plan": "pro", "kromis_kredi": 4500}, None, ("plan", "pro", 4_500)),
    ({"kromis_tur": "abonelik", "kromis_kredi": 1}, None, "kromis_tur"),
    ({"kromis_tur": "plan", "kromis_plan": "free", "kromis_kredi": 1}, None, "kromis_plan"),   # ücretsiz satılmaz
    ({"kromis_tur": "plan", "kromis_plan": "temel"}, None, "kromis_kredi"),
    ({"kromis_tur": "paket", "kromis_kredi": "0"}, None, "kromis_kredi"),
    ({"kromis_tur": "paket", "kromis_kredi": True}, None, "kromis_kredi"),
    ({"kromis_tur": "paket", "kromis_kredi": "²"}, None, "kromis_kredi"),         # `isdigit` doğru, `int()` çökerdi
    ({"kromis_tur": "paket", "kromis_kredi": 5}, [], "sabit fiyat yok"),
    ({"kromis_tur": "paket", "kromis_kredi": 5},
     [{"amount_type": "custom", "is_archived": False, "price_currency": "usd", "minimum_amount": 100}], "sabit fiyat yok"),
    ({"kromis_tur": "paket", "kromis_kredi": 5},
     [{"amount_type": "fixed", "is_archived": True, "price_amount": 100, "price_currency": "usd"},
      {"amount_type": "fixed", "is_archived": False, "price_amount": 700, "price_currency": "eur"}], ("paket", None, 5, 700, "eur")),
])
def test_satira_cevir_reads_the_metadata_contract_and_the_first_live_fixed_price(meta, fiyatlar, beklenen):
    satir = polar_esitle.satira_cevir(_polar_urunu("p1", " Ürün ", meta, fiyatlar=fiyatlar))
    if isinstance(beklenen, str):
        assert isinstance(satir, str) and beklenen in satir, satir
    else:
        assert isinstance(satir, polar_esitle.Satir) and satir.ad == "Ürün"
        assert (satir.tur, satir.plan, satir.kredi) == beklenen[:3]
        if len(beklenen) > 3:
            assert (satir.fiyat_kurus, satir.para_birimi) == beklenen[3:]


def test_urunleri_listele_walks_every_sdk_page_and_keeps_archived_products(monkeypatch):
    """SDK `products.list(is_archived=…, limit=100)` iki kez → `.result.items` + `.next()` zinciri."""
    class _Urun:
        def __init__(self, kimlik, arsiv):
            self.kimlik, self.arsiv = kimlik, arsiv

        def model_dump(self, mode="json"):
            return {"id": self.kimlik, "is_archived": self.arsiv, "mode": mode}

    class _Sonuc:
        def __init__(self, items):
            self.items = items

    class _Sayfa:
        def __init__(self, items, sonraki):
            self.result, self._sonraki = _Sonuc(items), sonraki

        def next(self):
            return self._sonraki

    cagrilar: list[dict] = []

    class _Products:
        def list(self, **kw):
            cagrilar.append(kw)
            if kw["is_archived"]:
                return _Sayfa([_Urun("z", True)], None)
            return _Sayfa([_Urun("a", False), _Urun("b", False)], _Sayfa([_Urun("c", False)], None))

    class _Istemci:
        products = _Products()

    monkeypatch.setattr(polar, "istemci", lambda: _Istemci())
    urunler = polar.urunleri_listele()
    assert [(u["id"], u["is_archived"]) for u in urunler] == [("a", False), ("b", False), ("c", False), ("z", True)]
    assert all(u["mode"] == "json" for u in urunler)
    assert cagrilar == [{"is_archived": False, "limit": 100}, {"is_archived": True, "limit": 100}], (
        "iki AÇIK çağrı: arşivlenen ürün `aktif=false` olmak zorunda, öntanımlıya güvenilmez")
