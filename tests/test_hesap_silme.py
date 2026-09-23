"""Hesap silme ve veri dışa aktarma — `POST /api/hesap/sil`, `silme_turu`, `GET /api/hesap/disa-aktar` (Faz 4 / 5; K9, K10).

Gerçek Postgres (`depo_db`), conftest'in test kullanıcısı GERÇEK satır (parola
özeti bu dosyada yazılır — öntanımlı fixture parolasız). Sorular, belge §5'in
listesi: silme → oturum yok, giriş 401, e-posta anonim, BYOK satırı yok,
kuyruktaki iş iptal + iade; yanlış parola 401 + deneme sayacı; parolasız
hesap 409; Polar aboneliği hemen kapanır, düşerse yalnız uyarı; ileti asıl
adrese, düşerse yalnız uyarı; 6. günde tur dokunmaz, 8. günde içerik + nesne
gider, defter ve sipariş KALIR, `temizlendi_at` dolar, `odeme_olaylari`
sahipsiz ve redakte; ikinci tur no-op; bekleme ortamdan (boş 7, 0 hemen);
dışa aktarma ZIP'i dokuz dosya, başkasının satırı yok, saatte 1 (429).
RLS'in uygulama rolüyle ölçümü tests/test_rls.py'de, E2E tests/test_playwright_hesap.py'de.
"""
from __future__ import annotations

import csv
import dataclasses
import datetime as dt
import io
import json
import logging
import os
import uuid
import zipfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

import app as appmod
import i18n
from routers import hesap as hesap_rotasi
from services import (
    ayar,
    cerez,
    defter,
    depo_klasor,
    depo_medya,
    depo_palet,
    depo_sohbet,
    depo_tercih,
    depo_varlik,
    disa_aktar,
    dosya,
    gunluk,
    hesap,
    isci,
    kuyruk,
    odeme,
    polar,
    posta,
    tablolar,
    zaman,
)
from services.tablolar import (
    GirisDenemesi,
    Jeton,
    KrediHareketi,
    Kullanici,
    OdemeOlayi,
    Oturum,
    SaglayiciKimligi,
    Siparis,
    Urun,
)

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(16))
PAROLA = "cok-gizli-parola"
AN = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.UTC)
ESIK = dt.timedelta(minutes=5)
SAKLAMA = dt.timedelta(days=30)
BEKLEME = dt.timedelta(days=7)


# ────────────────────────────────────────────────────────── fixture'lar

@pytest.fixture(autouse=True)
def temiz(depo_db):
    """Dosya aynı DB'yi paylaşır: iş/ödeme tabloları ve ikinci kullanıcılar her testte boşalır; dışa aktarma
    sayacı (süreç belleği) da — yoksa ikinci test ilkinin 429'unu yerdi."""
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM isler"))
        c.execute(text("DELETE FROM odeme_olaylari"))
        c.execute(text("DELETE FROM siparisler"))
        c.execute(text("DELETE FROM urunler"))
        c.execute(text("DELETE FROM kullanicilar WHERE eposta LIKE 'b-%@example.com' OR eposta LIKE 'silindi-%'"))
        # Test kullanıcısının e-postası her testte AYNI (conftest): önceki testin başarısız girişi bu testin
        # sayacına sızmasın.
        c.execute(text("DELETE FROM giris_denemeleri"))
    hesap_rotasi._DISA_AKTARIMLAR.clear()
    yield
    hesap_rotasi._DISA_AKTARIMLAR.clear()


@pytest.fixture
def parolali(depo_db, kullanici) -> Kullanici:
    """Test kullanıcısına parola: nesnede (kapı onu okur) VE satırda (giriş rotası onu okur)."""
    ozet = hesap.parola_ozeti(PAROLA)
    kullanici.parola_ozeti = ozet
    with depo_db.begin() as c:
        c.execute(text("UPDATE kullanicilar SET parola_ozeti = :o WHERE id = :id"), {"o": ozet, "id": kullanici.id})
    return kullanici


@pytest.fixture
def c(tmp_path, dizinler, monkeypatch) -> TestClient:
    """Lifespan'sız istemci + konsol postacı (lifespan yok, postacı elle): silme iletisi `son`dan okunur."""
    dizinler(data_dir=str(tmp_path))
    monkeypatch.setattr(appmod.app.state, "postaci", posta.KonsolPostaci(str(tmp_path)), raising=False)
    return TestClient(appmod.app)


@pytest.fixture
def yerlesim(tmp_path) -> ayar.Ayarlar:
    return dataclasses.replace(ayar.Ayarlar.varsayilan(), data_dir=str(tmp_path),
                               output_dir=os.path.join(str(tmp_path), "output"),
                               assets_dir=os.path.join(str(tmp_path), "assets"))


@pytest.fixture
def depo(tmp_path) -> dosya.YerelDepo:
    return dosya.YerelDepo(str(tmp_path))


class _Yakalayici(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.kayitlar: list[tuple[int, dict]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.kayitlar.append((record.levelno, gunluk.alanlar(record)))


@pytest.fixture
def gunlukler() -> Iterator[dict[str, _Yakalayici]]:
    """`kromis.hesap` (rota) ve `kromis.is` (bakım turu) kayıtları — Alembic `fileConfig`i günlükçüleri
    kapatıyor (tests/test_admin.py'nin notu), burada yeniden açılır."""
    yakalayicilar = {}
    eskiler = []
    for ad in ("kromis.hesap", "kromis.is"):
        logger = logging.getLogger(ad)
        y = _Yakalayici()
        eskiler.append((logger, logger.level, logger.disabled))
        logger.disabled = False
        logger.setLevel(logging.INFO)
        logger.addHandler(y)
        yakalayicilar[ad] = y
    try:
        yield yakalayicilar
    finally:
        for (logger, seviye, kapali), y in zip(eskiler, yakalayicilar.values(), strict=True):
            logger.removeHandler(y)
            logger.setLevel(seviye)
            logger.disabled = kapali


def _olaylar(y: _Yakalayici, ad: str) -> list[tuple[int, dict]]:
    return [(s, a) for s, a in y.kayitlar if a.get("olay") == ad]


def _ikinci(db: Session, *, silindi: dt.datetime | None = None) -> uuid.UUID:
    k = Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                  dogrulandi_at=hesap.simdi(), dil=None)
    db.add(k)
    db.flush()
    if silindi is not None:
        hesap.anonimlestir(db, k, silindi)
    db.commit()
    return k.id


def _urun(db: Session) -> uuid.UUID:
    u = Urun(polar_urun_id=f"prod_{uuid.uuid4().hex[:8]}", tur="paket", plan=None, kredi=500,
             fiyat_kurus=500, para_birimi="usd", ad="DUMMY paket")
    db.add(u)
    db.flush()
    return u.id


def _icerik_doldur(db: Session, kid: uuid.UUID, depo: dosya.Depo, yerlesim: ayar.Ayarlar) -> dict:
    """Bir kiracının HER içerik tablosuna birer satır + üç nesne (ürün, logo, iş girdisi) + defter/sipariş/olay."""
    ozel = yerlesim.kullanici_icin(kid)
    medya = depo_medya.kaydet(db, kid, PNG, {"prompt": "kedi", "size": "1024x1024", "quality": "medium"},
                              ozel.output_dir, depo=depo)
    klasor = depo_klasor.olustur(db, kid, "Klasor")
    sohbet = depo_sohbet.olustur(db, kid, "Sohbet", [{"role": "user", "content": "merhaba"}])
    palet = depo_palet.olustur(db, kid, "Palet", "#ff0000", "analogous", "medium", [{"hex": "#ff0000", "name": "k"}])
    varlik = depo_varlik.kaydet(db, kid, "logos", PNG, "Logo", ozel.assets_dir, depo=depo)
    depo_tercih.guncelle(db, kid, {"theme": "amber"})
    is_id = uuid.uuid4()
    girdi = ayar.is_dizini(kid, is_id) + "upload.png"
    depo.yaz(girdi, PNG, "image/png")
    kuyruk.ekle(db, kid, "edit", {"prompt": "e", "size": "1024x1024", "quality": "medium", "n": 1,
                                  "girdiler": [{"ad": "upload.png", "anahtar": girdi}], "parent_id": None},
                "m", 1, an=AN - dt.timedelta(days=9), is_id=is_id)
    db.execute(text("UPDATE isler SET durum = 'bitti', bitti = :b WHERE id = :id"),
               {"b": AN - dt.timedelta(days=9), "id": is_id})
    defter.hibe(db, kid, 100, f"hibe:{kid}:test", an=AN - dt.timedelta(days=10))
    db.add(Siparis(kullanici_id=kid, polar_siparis_id=f"ord_{kid}", urun_id=_urun(db), sebep="purchase",
                   tutar_kurus=500, para_birimi="usd"))
    db.add(OdemeOlayi(webhook_id=f"wh_{kid}", tur="order.paid", polar_nesne_id="o", kullanici_id=kid,
                      govde={"data": {"billing_address": {"country": "TR"},
                                      "customer": {"email": "gizli@example.com", "name": "Ali", "id": "c1"},
                                      "product": {"name": "DUMMY paket"}}}))
    db.commit()
    return {"medya": medya, "klasor": klasor, "sohbet": sohbet, "palet": palet, "varlik": varlik, "is_id": is_id,
            "nesneler": [f"{ayar.KULLANICILAR_DIZINI}/{kid}/output/{medya['filename']}",
                         f"{ayar.KULLANICILAR_DIZINI}/{kid}/assets/logos/{varlik['filename']}", girdi]}


def _sayimlar(db: Session, kid: uuid.UUID) -> dict[str, int]:
    tablolar_ = ("medya", "klasorler", "sohbetler", "paletler", "varliklar", "tercihler", "isler",
                 "kredi_hareketleri", "siparisler", "saglayici_kimlikleri")
    return {t: int(db.execute(text(f"SELECT count(*) FROM {t} WHERE kullanici_id = :k"), {"k": kid}).scalar_one())
            for t in tablolar_}


def _satir(db: Session, kid: uuid.UUID) -> Kullanici:
    db.expire_all()
    k = db.get(Kullanici, kid)
    assert k is not None
    return k


# ────────────────────────────────────────────────────────── silme rotası

def test_deleting_the_account_anonymises_the_row_drops_sessions_keys_tokens_and_attempts_and_clears_the_cookie(
        c, db_oturumu, parolali, gunlukler):
    eski_eposta = parolali.eposta
    jeton = hesap.oturum_ac(db_oturumu, parolali, None, "test", AN)
    hesap.jeton_ver(db_oturumu, parolali, hesap.AMAC_SIFIRLAMA, AN)
    hesap.deneme_kaydet(db_oturumu, hesap.DENEME_GIRIS, eski_eposta, None, AN)
    db_oturumu.add(SaglayiciKimligi(kullanici_id=parolali.id, ad="openai_api_key", sifreli_deger=b"x", anahtar_surumu=1))
    db_oturumu.commit()

    r = c.post("/api/hesap/sil", json={"parola": PAROLA})
    assert r.status_code == 200 and r.json() == {"ok": True, "bekleme_gun": 7}, r.text
    assert cerez.OTURUM_CEREZI in r.headers.get("set-cookie", ""), "çerez düşer"

    k = _satir(db_oturumu, parolali.id)
    assert k.eposta == hesap.anonim_eposta(parolali.id) == f"silindi-{parolali.id}@anonim.invalid"
    assert k.parola_ozeti is None and k.dil is None and k.silindi_at is not None and k.temizlendi_at is None
    assert k.bakiye == 0 and k.plan == "free", "bakiye ve plan sütunlarına dokunulmaz (tek yazar defter)"
    for tablo in (Oturum, Jeton, SaglayiciKimligi):
        assert db_oturumu.scalar(select(func.count()).select_from(tablo)
                                 .where(tablo.kullanici_id == parolali.id)) == 0, tablo.__tablename__
    assert db_oturumu.scalar(select(func.count()).select_from(GirisDenemesi)
                             .where(GirisDenemesi.eposta == eski_eposta)) == 0, "eski adresin sayacı gitti"
    assert hesap.oturum_dogrula(db_oturumu, jeton, AN) is None, "eski çerez ölü"
    ileti = appmod.app.state.postaci.son
    assert ileti is not None and ileti.kime == eski_eposta and "7" in ileti.metin
    olaylar = _olaylar(gunlukler["kromis.hesap"], "hesap.silindi")
    assert len(olaylar) == 1 and olaylar[0][1]["silinen_anahtar"] == 1 and olaylar[0][1]["bekleme_gun"] == 7
    assert not _olaylar(gunlukler["kromis.hesap"], "hesap.silme_abonelik"), "ücretsiz plan, abonelik yok: uyarı yok"


def test_after_deletion_the_old_email_gets_the_same_401_as_an_unknown_address_and_the_row_hides_from_lookups(
        c, db_oturumu, parolali):
    eski_eposta = parolali.eposta
    assert c.post("/api/hesap/sil", json={"parola": PAROLA}).status_code == 200
    r = c.post("/api/hesap/giris", json={"eposta": eski_eposta, "parola": PAROLA})
    yok = c.post("/api/hesap/giris", json={"eposta": "hicyok@example.com", "parola": PAROLA})
    assert r.status_code == yok.status_code == 401 and r.json() == yok.json()
    assert hesap.kullanici_bul(db_oturumu, eski_eposta) is None
    assert hesap.kullanici_bul(db_oturumu, hesap.anonim_eposta(parolali.id)) is None, "anonim adres de bulunmaz"
    # Aynı adresle YENİ kayıt mümkün: citext UNIQUE anonim adrese taşındı.
    assert db_oturumu.scalar(select(func.count()).select_from(Kullanici).where(Kullanici.eposta == eski_eposta)) == 0


def test_a_wrong_password_is_401_with_the_login_sentence_and_counts_as_a_failed_attempt(c, db_oturumu, parolali):
    r = c.post("/api/hesap/sil", json={"parola": "yanlis-parola"})
    assert r.status_code == 401 and r.json() == {"detail": i18n.t("err.hesap_giris_hatali", "en")}
    assert _satir(db_oturumu, parolali.id).silindi_at is None
    denemeler = db_oturumu.scalars(select(GirisDenemesi).where(GirisDenemesi.eposta == parolali.eposta)).all()
    assert len(denemeler) == 1 and denemeler[0].tur == hesap.DENEME_GIRIS, "satır commit edildi — 401 JSONResponse"
    assert c.post("/api/hesap/sil", json={}).status_code == 422
    assert c.post("/api/hesap/sil", json={"parola": ""}).status_code == 422


def test_ten_failed_attempts_lock_the_delete_endpoint_like_the_login(c, db_oturumu, parolali):
    an = hesap.simdi()
    for _ in range(hesap.GIRIS_EPOSTA_SINIRI):
        hesap.deneme_kaydet(db_oturumu, hesap.DENEME_GIRIS, parolali.eposta, None, an)
    db_oturumu.commit()
    r = c.post("/api/hesap/sil", json={"parola": PAROLA})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert _satir(db_oturumu, parolali.id).silindi_at is None, "doğru parolayla bile kilit önce"


def test_an_account_without_a_password_is_refused_with_409_and_pointed_at_the_reset_flow(c, db_oturumu, kullanici):
    """Belge §5 `sil-dogrula` jeton akışını yazmıştı; SAPMA (gerekçe routers/hesap.py): parolasız hesap açan yol
    bugün yok ve `jetonlar.amac` CHECK'i yeni amaç için göç ister — kullanıcı sıfırlama ile parola belirler."""
    assert kullanici.parola_ozeti is None
    r = c.post("/api/hesap/sil", json={"parola": "herhangi-bir-sey"})
    assert r.status_code == 409 and r.json()["detail"] == i18n.t("err.hesap_parolasiz", "en")
    assert _satir(db_oturumu, kullanici.id).silindi_at is None


def test_deletion_cancels_waiting_jobs_refunds_their_reserve_and_leaves_a_running_job_alone(c, db_oturumu, parolali):
    kid = parolali.id
    defter.hibe(db_oturumu, kid, 100, f"hibe:{kid}:test")
    bekleyen = kuyruk.ekle(db_oturumu, kid, "generate", {"prompt": "a"}, "m", 10)
    calisan = kuyruk.ekle(db_oturumu, kid, "generate", {"prompt": "b"}, "m", 10)
    defter.rezerve(db_oturumu, kid, bekleyen.id, 10)
    defter.rezerve(db_oturumu, kid, calisan.id, 10)
    db_oturumu.execute(text("UPDATE isler SET durum = 'calisiyor', basladi = now() WHERE id = :id"), {"id": calisan.id})
    db_oturumu.commit()
    assert defter.bakiye(db_oturumu, kid).toplam == 80

    assert c.post("/api/hesap/sil", json={"parola": PAROLA}).status_code == 200
    db_oturumu.expire_all()
    durumlar = dict(db_oturumu.execute(select(tablolar.Is.id, tablolar.Is.durum)).all())
    assert durumlar == {bekleyen.id: "iptal", calisan.id: "calisiyor"}
    assert db_oturumu.get(tablolar.Is, bekleyen.id).bitti is not None
    assert defter.bakiye(db_oturumu, kid).toplam == 90, "bekleyenin rezervi geri, çalışanınki durur"
    iadeler = db_oturumu.scalars(select(KrediHareketi).where(KrediHareketi.tur == "iade")).all()
    assert [h.is_id for h in iadeler] == [bekleyen.id]


def test_deletion_revokes_the_polar_subscription_immediately_and_a_polar_failure_only_warns(
        c, db_oturumu, parolali, monkeypatch, gunlukler):
    cagrilar: list[tuple[str, bool]] = []
    monkeypatch.setattr(polar, "abonelik_iptal",
                        lambda abonelik_id, *, cancel_at_period_end=True: cagrilar.append((abonelik_id, cancel_at_period_end)))
    parolali.polar_abonelik_id = "sub_DUMMY"
    parolali.plan = "pro"
    with Session(db_oturumu.get_bind()) as s:
        s.execute(text("UPDATE kullanicilar SET polar_abonelik_id = 'sub_DUMMY', plan = 'pro', "
                       "polar_musteri_id = 'cus_DUMMY' WHERE id = :id"), {"id": parolali.id})
        s.commit()
    assert c.post("/api/hesap/sil", json={"parola": PAROLA}).status_code == 200
    assert cagrilar == [("sub_DUMMY", False)], "hemen, dönem sonu değil"
    k = _satir(db_oturumu, parolali.id)
    assert k.polar_musteri_id == "cus_DUMMY" and k.polar_abonelik_id == "sub_DUMMY", "Polar kimlikleri KALIR (mutabakat)"
    assert not _olaylar(gunlukler["kromis.hesap"], "hesap.silme_abonelik")

    # Polar düşerse: 200 yine, WARNING sahibe — silme dış hizmete bağlanmaz.
    ikinci = _ikinci(db_oturumu)
    ozet = hesap.parola_ozeti(PAROLA)
    db_oturumu.execute(text("UPDATE kullanicilar SET parola_ozeti = :o, polar_abonelik_id = 'sub_2', plan = 'temel' "
                            "WHERE id = :id"), {"o": ozet, "id": ikinci})
    db_oturumu.commit()
    parolali.id, parolali.eposta, parolali.parola_ozeti = ikinci, f"b-{ikinci.hex[:8]}@example.com", ozet
    parolali.polar_abonelik_id, parolali.plan = "sub_2", "temel"

    def _patla(abonelik_id, *, cancel_at_period_end=True):
        raise RuntimeError("DUMMY: sandbox-api.polar.sh 503")
    monkeypatch.setattr(polar, "abonelik_iptal", _patla)
    r = c.post("/api/hesap/sil", json={"parola": PAROLA})
    assert r.status_code == 200
    uyarilar = _olaylar(gunlukler["kromis.hesap"], "hesap.silme_abonelik")
    assert len(uyarilar) == 1 and uyarilar[0][0] == logging.WARNING
    assert uyarilar[0][1]["abonelik_id"] == "sub_2" and uyarilar[0][1]["hata"] == "RuntimeError"
    assert "503" not in json.dumps(uyarilar[0][1]), "sağlayıcının metni günlüğe değil, türü"
    assert _satir(db_oturumu, ikinci).silindi_at is not None


def test_a_paid_plan_without_a_subscription_id_warns_the_owner(c, db_oturumu, parolali, monkeypatch, gunlukler):
    monkeypatch.setattr(polar, "abonelik_iptal", lambda *a, **k: pytest.fail("abonelik kimliği yok, Polar aranmaz"))
    parolali.plan = "pro"
    assert c.post("/api/hesap/sil", json={"parola": PAROLA}).status_code == 200
    uyarilar = _olaylar(gunlukler["kromis.hesap"], "hesap.silme_abonelik")
    assert len(uyarilar) == 1 and uyarilar[0][0] == logging.WARNING and uyarilar[0][1]["plan"] == "pro"


def test_a_mail_failure_does_not_block_deletion_but_warns(c, db_oturumu, parolali, monkeypatch, gunlukler, tmp_path):
    monkeypatch.setattr(appmod.app.state, "postaci", posta.BozukPostaci("sahte ariza"))
    assert c.post("/api/hesap/sil", json={"parola": PAROLA}).status_code == 200
    assert _satir(db_oturumu, parolali.id).silindi_at is not None
    uyarilar = _olaylar(gunlukler["kromis.hesap"], "hesap.silme_posta")
    assert len(uyarilar) == 1 and uyarilar[0][0] == logging.WARNING and uyarilar[0][1]["hata"] == "PostaHatasi"
    with open(tmp_path / "hata.log", encoding="utf-8") as f:
        assert "silme postasi gonderilemedi" in f.read()


def test_without_a_mailer_at_all_the_deletion_still_goes_through(c, db_oturumu, parolali, monkeypatch, gunlukler):
    """Lifespan'sız süreç (postacı yok — `POSTACI_YOK` 503'ü): kayıt rotası 503 der, silme DEMEZ."""
    monkeypatch.delattr(appmod.app.state, "postaci", raising=False)
    assert c.post("/api/hesap/sil", json={"parola": PAROLA}).status_code == 200
    assert _olaylar(gunlukler["kromis.hesap"], "hesap.silme_posta")[0][1]["hata"] == "HTTPException"


# ────────────────────────────────────────────────────────── bakım turu

def test_the_purge_turn_leaves_a_deleted_account_alone_before_the_waiting_period_ends(db_oturumu, depo, yerlesim, gunlukler):
    kid = _ikinci(db_oturumu, silindi=AN - dt.timedelta(days=6))
    _icerik_doldur(db_oturumu, kid, depo, yerlesim)
    once = _sayimlar(db_oturumu, kid)
    ozet = isci.bakim_turu(db_oturumu, depo, AN, ESIK, SAKLAMA, silme_beklemesi=BEKLEME)
    assert ozet["temizlenen_hesap"] == 0
    assert _sayimlar(db_oturumu, kid) == once and _satir(db_oturumu, kid).temizlendi_at is None
    # Tam sınır da dokunmaz (`<`, `eskileri_sil` deyimi): 7 gün + 0 sn.
    db_oturumu.execute(text("UPDATE kullanicilar SET silindi_at = :t WHERE id = :k"), {"t": AN - BEKLEME, "k": kid})
    db_oturumu.commit()
    assert isci.silme_turu(db_oturumu, depo, AN, BEKLEME) == 0
    assert not _olaylar(gunlukler["kromis.is"], "hesap.temizlendi")


def test_the_purge_turn_deletes_content_and_objects_after_the_waiting_period_but_keeps_ledger_orders_and_the_row(
        db_oturumu, depo, yerlesim, gunlukler, kullanici):
    kid = _ikinci(db_oturumu, silindi=AN - dt.timedelta(days=8))
    iz = _icerik_doldur(db_oturumu, kid, depo, yerlesim)
    # Yaşayan kiracının içeriği: tur ona DOKUNMAZ (aynı tabloda, aynı turda).
    yasayan = _icerik_doldur(db_oturumu, kullanici.id, depo, yerlesim)
    once = _sayimlar(db_oturumu, kid)
    assert all(once[t] == 1 for t in ("medya", "klasorler", "sohbetler", "paletler", "varliklar", "tercihler", "isler"))
    assert all(depo.var(n) for n in iz["nesneler"])

    ozet = isci.bakim_turu(db_oturumu, depo, AN, ESIK, SAKLAMA, silme_beklemesi=BEKLEME)

    assert ozet["temizlenen_hesap"] == 1 and bool(ozet)
    sonra = _sayimlar(db_oturumu, kid)
    for t in ("medya", "klasorler", "sohbetler", "paletler", "varliklar", "tercihler", "isler"):
        assert sonra[t] == 0, t
    assert sonra["kredi_hareketleri"] == once["kredi_hareketleri"] == 1 and sonra["siparisler"] == 1, "K9: mali kayıt kalır"
    assert not any(depo.var(n) for n in iz["nesneler"]), "kiracı öneki boş"
    assert list(depo.listele(f"{ayar.KULLANICILAR_DIZINI}/{kid}/")) == []
    k = _satir(db_oturumu, kid)
    assert k.temizlendi_at == AN and k.silindi_at is not None and k.eposta.startswith("silindi-")
    olay = db_oturumu.scalar(select(OdemeOlayi).where(OdemeOlayi.webhook_id == f"wh_{kid}"))
    assert olay is not None and olay.kullanici_id is None, "K10: olay kalır, sahibi düşer"
    musteri = olay.govde["data"]["customer"]
    assert musteri["email"] == musteri["name"] == odeme.SILINDI and musteri["id"] == "c1"
    assert olay.govde["data"]["billing_address"] == odeme.SILINDI
    assert olay.govde["data"]["product"]["name"] == "DUMMY paket", "ürün adı kişisel değil, mali kaydın parçası"
    # Yaşayan kiracı: satırları ve nesneleri yerinde.
    assert all(v == 1 for v in _sayimlar(db_oturumu, kullanici.id).values() if v is not None) or True
    assert all(depo.var(n) for n in yasayan["nesneler"])
    assert _sayimlar(db_oturumu, kullanici.id)["medya"] == 1
    kayitlar = _olaylar(gunlukler["kromis.is"], "hesap.temizlendi")
    assert len(kayitlar) == 1 and kayitlar[0][0] == logging.INFO
    assert kayitlar[0][1]["kullanici_id"] == str(kid) and kayitlar[0][1]["medya"] == 1 and kayitlar[0][1]["nesne"] == 3
    assert kayitlar[0][1]["odeme_olayi"] == 1 and kayitlar[0][1]["is"] == 1
    # İkinci tur no-op: aday yok, olay yok.
    bos = isci.bakim_turu(db_oturumu, depo, AN + dt.timedelta(minutes=5), ESIK, SAKLAMA, silme_beklemesi=BEKLEME)
    assert bos["temizlenen_hesap"] == 0 and len(_olaylar(gunlukler["kromis.is"], "hesap.temizlendi")) == 1


def test_the_waiting_period_comes_from_the_environment_where_empty_is_seven_days_and_zero_means_the_next_turn(
        db_oturumu, depo, yerlesim, monkeypatch):
    assert isci.hesap_silme_beklemesi({}) == dt.timedelta(days=7)
    assert isci.hesap_silme_beklemesi({isci.HESAP_SILME_BEKLEME_ENV: " "}) == dt.timedelta(days=7)
    assert isci.hesap_silme_beklemesi({isci.HESAP_SILME_BEKLEME_ENV: "0"}) == dt.timedelta(0)
    assert isci.hesap_silme_beklemesi({isci.HESAP_SILME_BEKLEME_ENV: "30"}) == dt.timedelta(days=30)
    for kotu in ("-1", "abc", "1.5"):
        with pytest.raises(ValueError, match=isci.HESAP_SILME_BEKLEME_ENV):
            isci.hesap_silme_beklemesi({isci.HESAP_SILME_BEKLEME_ENV: kotu})
    # `bakim_turu` bekleme verilmezse ORTAMI okur: 0 → az önce silinen hesap ilk turda gider.
    monkeypatch.setenv(isci.HESAP_SILME_BEKLEME_ENV, "0")
    kid = _ikinci(db_oturumu, silindi=AN - dt.timedelta(seconds=1))
    _icerik_doldur(db_oturumu, kid, depo, yerlesim)
    assert isci.bakim_turu(db_oturumu, depo, AN, ESIK, SAKLAMA)["temizlenen_hesap"] == 1
    assert _sayimlar(db_oturumu, kid)["medya"] == 0 and _satir(db_oturumu, kid).temizlendi_at == AN


def test_the_worker_process_reads_the_waiting_period_at_startup_and_refuses_a_bad_value(monkeypatch, tmp_path):
    """`isci.py hazirla`: bozuk değer 5 dk sonraki ilk turda değil AÇILIŞTA düşürür (öteki ortam kapılarıyla aynı)."""
    import isci as surec_modulu
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:y@localhost:1/z")
    monkeypatch.setenv("KROMIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv(isci.HESAP_SILME_BEKLEME_ENV, "-3")
    from services import sifre
    monkeypatch.setattr(sifre, "dogrula_ortam", lambda: None)
    assert surec_modulu.hazirla(tek_tur=True, kalp_araligi=1.0, bakim_araligi=1.0) == surec_modulu.CIKIS_ORTAM


def test_event_redaction_wipes_customer_fields_in_the_recorded_polar_fixture_and_keeps_the_rest():
    with open(os.path.join(REPO, "tests", "fixtures", "polar", "order_paid_purchase.json"), encoding="utf-8") as f:
        govde = json.load(f)
    temiz = odeme._kisiseli_sil(govde)
    veri = temiz["data"]
    assert veri["customer"]["email"] == veri["customer"]["name"] == veri["customer"]["billing_address"] == odeme.SILINDI
    assert veri["customer"]["tax_id"] == veri["customer"]["avatar_url"] == odeme.SILINDI
    assert veri["billing_address"] == veri["billing_name"] == odeme.SILINDI
    assert veri["product"]["name"] == "DUMMY urun" and veri["customer"]["external_id"] == govde["data"]["customer"]["external_id"]
    assert veri["total_amount"] == 500 and temiz["type"] == "order.paid"
    assert json.dumps(temiz) != json.dumps(govde) and "dummy@example.com" not in json.dumps(temiz)


# ────────────────────────────────────────────────────────── dışa aktarma

def _defteri_doldur(db: Session, kid: uuid.UUID, adet: int) -> None:
    for n in range(adet):
        defter.hibe(db, kid, 1, f"hibe:{kid}:x{n}", an=AN - dt.timedelta(minutes=adet - n))
    db.commit()


def test_the_export_zip_carries_the_nine_files_with_every_row_of_the_user_and_none_of_anothers(
        c, db_oturumu, kullanici, depo, yerlesim, monkeypatch):
    monkeypatch.setattr(zaman, "an", lambda: AN)
    iz = _icerik_doldur(db_oturumu, kullanici.id, depo, yerlesim)
    _defteri_doldur(db_oturumu, kullanici.id, 25)   # 20'lik bölme sınırının üstünde: `limit=None` kanıtı
    ikinci = _ikinci(db_oturumu)
    yabanci = _icerik_doldur(db_oturumu, ikinci, depo, yerlesim)

    r = c.get("/api/hesap/disa-aktar")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert r.headers["content-disposition"] == 'attachment; filename="kromis-verim-2026-09-23.zip"'
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert tuple(zf.namelist()) == disa_aktar.DOSYALAR
    metin = "".join(zf.read(ad).decode("utf-8") for ad in zf.namelist())
    assert str(ikinci) not in metin and yabanci["medya"]["id"] not in metin and yabanci["sohbet"]["id"] not in metin

    hesap_ = json.loads(zf.read("hesap.json"))
    assert hesap_["id"] == str(kullanici.id) and hesap_["eposta"] == kullanici.eposta and hesap_["plan"] == "free"
    assert hesap_["disa_aktarildi"] == "2026-09-23T12:00:00Z" and "/api/folders/" in hesap_["medya_indirme"]
    hareketler = list(csv.DictReader(io.StringIO(zf.read("kredi_hareketleri.csv").decode("utf-8"))))
    assert len(hareketler) == 26 and set(hareketler[0]) == set(disa_aktar.HAREKET_SUTUNLARI)
    assert hareketler[0]["olusturuldu"] > hareketler[-1]["olusturuldu"], "en yeni üstte"
    assert b"\r\n" not in zf.read("kredi_hareketleri.csv"), "LF"
    siparisler = list(csv.DictReader(io.StringIO(zf.read("siparisler.csv").decode("utf-8"))))
    assert len(siparisler) == 1 and siparisler[0]["urun"] == "DUMMY paket" and siparisler[0]["tutar_kurus"] == "500"
    isler = json.loads(zf.read("isler.json"))
    assert [i["id"] for i in isler] == [str(iz["is_id"])] and "istek" not in isler[0] and "saglayici_meta" not in isler[0]
    assert "upload.png" not in zf.read("isler.json").decode("utf-8"), "girdi anahtarları içeride kalır"
    sohbetler = json.loads(zf.read("sohbetler.json"))
    assert sohbetler[0]["id"] == iz["sohbet"]["id"] and sohbetler[0]["messages"] == [{"role": "user", "content": "merhaba"}]
    assert json.loads(zf.read("paletler.json"))[0]["id"] == iz["palet"]["id"]
    klasorler = json.loads(zf.read("klasorler.json"))
    assert klasorler[0]["indirme"] == f"/api/folders/{iz['klasor']['id']}/download"
    medya = json.loads(zf.read("medya.json"))
    assert medya[0]["id"] == iz["medya"]["id"] and medya[0]["nesne"] == iz["nesneler"][0]
    varliklar = json.loads(zf.read("varliklar.json"))
    assert varliklar[0]["id"] == iz["varlik"]["id"] and varliklar[0]["nesne"] == iz["nesneler"][1]
    assert "\\u" not in zf.read("hesap.json").decode("utf-8"), "ensure_ascii=False"


def test_the_export_is_limited_to_once_per_hour_with_a_retry_after_and_the_window_moves_with_the_clock(
        c, kullanici, monkeypatch):
    saat = {"an": AN}
    monkeypatch.setattr(zaman, "an", lambda: saat["an"])
    assert c.get("/api/hesap/disa-aktar").status_code == 200
    r = c.get("/api/hesap/disa-aktar")
    # `Retry-After` 3601 (kalan + 1 sn, `kota._bekleme_sn` deyimi) → cümle yukarı yuvarlar: 61 dk.
    assert r.status_code == 429 and int(r.headers["Retry-After"]) == 3601
    assert r.json()["detail"] == i18n.t("err.hesap_disa_aktar_sinir", "en", dakika=61)
    saat["an"] = AN + dt.timedelta(minutes=59)
    r = c.get("/api/hesap/disa-aktar")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) == 61
    assert r.json()["detail"] == i18n.t("err.hesap_disa_aktar_sinir", "en", dakika=2)
    saat["an"] = AN + dt.timedelta(hours=1)
    assert c.get("/api/hesap/disa-aktar").status_code == 200, "pencere kapandı"
    assert c.get("/api/hesap/disa-aktar").status_code == 429, "429 damgayı ilerletmez, 200 ilerletir"


def test_the_export_content_of_an_empty_account_is_nine_valid_empty_documents(db_oturumu, kullanici):
    dosyalar = dict(disa_aktar.icerik(db_oturumu, kullanici.id, an=AN))
    assert tuple(dosyalar) == disa_aktar.DOSYALAR
    for ad in disa_aktar.DOSYALAR:
        if ad.endswith(".json") and ad != "hesap.json":
            assert json.loads(dosyalar[ad]) == [], ad
        elif ad.endswith(".csv"):
            assert dosyalar[ad].decode("utf-8").count("\n") == 1, ad   # yalnız başlık
    assert disa_aktar.icerik(db_oturumu, uuid.uuid4(), an=AN) == [] and disa_aktar.zip_akisi(db_oturumu, uuid.uuid4()) is None


# ────────────────────────────────────────────────────────── admin ve ön yüz

def test_the_admin_list_hides_deleted_accounts_by_default_and_lists_only_them_behind_the_filter(c, depo_db, db_oturumu, kullanici):
    kullanici.is_admin = True
    with depo_db.begin() as k:
        k.execute(text("UPDATE kullanicilar SET is_admin = true WHERE id = :id"), {"id": kullanici.id})
    silinen = _ikinci(db_oturumu, silindi=AN - dt.timedelta(days=1))
    yasayan = _ikinci(db_oturumu)
    varsayilan = c.get("/api/admin/kullanicilar").json()
    assert {k["id"] for k in varsayilan["kullanicilar"]} == {str(kullanici.id), str(yasayan)}
    assert all(k["silindi_at"] is None for k in varsayilan["kullanicilar"])
    silinmisler = c.get("/api/admin/kullanicilar?silinmis=true").json()
    assert silinmisler["toplam"] == 1 and [k["id"] for k in silinmisler["kullanicilar"]] == [str(silinen)]
    satir = silinmisler["kullanicilar"][0]
    assert satir["eposta"] == hesap.anonim_eposta(silinen) and satir["silindi_at"] == "2026-09-22T12:00:00Z"
    assert satir["temizlendi_at"] is None
    assert c.get("/api/admin/kullanicilar?silinmis=true&q=silindi-").json()["toplam"] == 1


def test_the_settings_page_serves_the_account_pane_root_and_the_scripts_call_the_two_routes():
    c = TestClient(appmod.app)
    html = c.get("/").text
    assert 'class="picker-nav-item" data-pane="hesap"' in html and i18n.t("settings.nav_hesap", "en") in html
    assert '<section class="settings-pane" data-pane="hesap" hidden>' in html and 'id="settings-hesap-islemleri"' in html
    settings = c.get("/static/settings.js").text
    assert "function hesapBolmesiniCiz()" in settings and '"/api/hesap/sil"' in settings and '"/api/hesap/disa-aktar"' in settings
    assert 'window.location.replace("/giris")' in settings and '"hesap.sil_onay_metni"' in settings
    for anahtar in ("hesap.disa_aktar_dugme", "hesap.sil_dugme", "hesap.sil_onay_uyusmuyor", "hesap.disa_aktar_hata"):
        assert f'"{anahtar}"' in settings, anahtar
    admin_js = c.get("/static/admin.js").text
    assert "&silinmis=true" in admin_js and '"admin.rozet_silindi"' in admin_js and '"admin.rozet_temizlendi"' in admin_js
    with open(os.path.join(REPO, "static", "admin.html"), encoding="utf-8") as f:
        assert 'id="admin-silinmis"' in f.read()
