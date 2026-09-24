# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Admin (Faz 2 / 8): `kimlik.admin_kullanici`, `/admin` sayfası, `/api/admin/*`, `GET /api/kota`.

docs/faz2-kuyruk-anahtarlar-depolama.md §8'in bekçisi. Üç katman:

* KAPI — admin olmayan oturum HER admin rotasında 403 (JSON, `err.admin_gerekli`),
  `/admin` sayfasında 403 HTML; oturumsuz 401/302 tests/test_kimlik.py'nin
  parametrik testinden geliyor (rotalar orada `KAPILI`).
* RLS — asıl kırılma sınıfı (belge §7 devri, madde 1 ve 5): admin rotası
  bağlamı BAĞLAMAZSA uygulama rolünde sessizce BOŞ döner. İki yönden ölçülür:
  ham `depo_admin` sorgusu bağlamsız boş / admin bağlamıyla dolu; kapılı
  rota uygulama rolü altında (test_rls'in `uygulama_motoru`su, `SET ROLE`)
  HERKESİN satırını listeler.
* DAVRANIŞ — liste/arama/sayfa, tavan yaz-sil ve 6. görevin kotasının onu
  okuması (gerçek çerezle: kapı kullanıcının SATIRINI her istekte yeniden
  çözer), oturum düşürme çerezi öldürür, admin iptali başkasının bekleyen
  işini kapatır (çalışan 409, olmayan 404), metrik alanları ve p50/p95 tohumla,
  `admin.html` iki dilde çevrili ve yalnız kendi betiğini yükler, admin.js'in
  id bağları sayfada var (betik `KAPSAM_DISI`, bekçisi burası), yazımlar
  `olay=admin.*` günlük satırı düşürür.

Çoğu test conftest'in `kullanici` override'ıyla koşar ve onu `is_admin=True`
yapar (`admin` fixture'ı: nesne + satır). Kullanıcının SATIRINI okuyan yollar
(kota tavanı, çerez ölümü) `gercek_kimlik`le, lifespan'lı istemci ve gerçek
çerezle koşar — override nesnesi tavan değişikliğini görmezdi.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import app as appmod
import catalog
import i18n
import version
from services import (
    cerez,
    db,
    defter,
    depo_admin,
    hesap,
    kiraci,
    kota,
    kuyruk,
    platform_anahtari,
    tablolar,
    zaman,
)
from services.tablolar import Kullanici
from tests.test_kimlik import ADMIN_ROTALAR, YOL_DEGERLERI
from tests.test_rls import uygulama_motoru  # noqa: F401 — SET ROLE fixture'ı (getfixturevalue)

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTTPS = "https://testserver"
GORSEL = {"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1}
MODEL_ID = catalog.DEFAULT_IMAGE_MODEL
SPEC = catalog.image_model(MODEL_ID)
assert SPEC is not None
KREDI = catalog.cost_for(SPEC, "medium")
AN = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)


# ────────────────────────────────────────────────────────── fixture'lar

@pytest.fixture(autouse=True)
def temiz(depo_db):
    """Her test boş iş/işçi tablolarıyla ve yalnız test kullanıcısıyla başlar."""
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM isler"))
        c.execute(text("DELETE FROM isciler"))
        c.execute(text("DELETE FROM kullanicilar WHERE eposta LIKE 'b-%@example.com'"))
    yield


@pytest.fixture
def admin(depo_db, kullanici) -> Kullanici:
    """conftest'in test kullanıcısı ADMİN olur — nesne (kapı bunu okur) ve satır (liste bunu gösterir)."""
    kullanici.is_admin = True
    with depo_db.begin() as c:
        c.execute(text("UPDATE kullanicilar SET is_admin = true WHERE id = :id"), {"id": kullanici.id})
    return kullanici


class _Yakalayici(logging.Handler):
    """`kromis.admin` kayıtları — pytest'in `caplog`u yerine doğrudan işleyici: kök yapılandırmadan bağımsız.

    Faz 2 / 9'dan beri olay YAPISAL: `satirlar` her kaydın alanlarını sözlük olarak
    tutar (`gunluk.alanlar` — JSON satıra girenin aynısı), mesaj değil.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.satirlar: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        from services import gunluk
        alanlar = gunluk.alanlar(record)
        # `istek_id` bağlamdan gelir ve her satırda VAR (istek kimliği ara katmanı); değeri
        # isteğe göre değişir, testler olayın kendi alanlarına bakar.
        assert alanlar.pop("istek_id", None), "admin olayı istek bağlamı dışında yazıldı"
        self.satirlar.append(alanlar)


@pytest.fixture
def gunluk() -> Iterator[_Yakalayici]:
    logger = logging.getLogger("kromis.admin")
    yakalayici = _Yakalayici()
    eski = logger.level
    # `depo_db` Alembic'i aynı süreçte koşturuyor ve `alembic/env.py`nin `fileConfig`i o ana
    # kadar yaratılmış her günlükçüyü KAPATIYOR (`disable_existing_loggers`; tests/test_platform_anahtari.py
    # aynı tuzağı ölçtü). Üretimde göç ayrı süreç (tools/goc.py); burada yeniden açılıyor.
    logger.disabled = False
    logger.addHandler(yakalayici)
    logger.setLevel(logging.INFO)
    try:
        yield yakalayici
    finally:
        logger.removeHandler(yakalayici)
        logger.setLevel(eski)


@pytest.fixture
def c(tmp_path, dizinler) -> TestClient:
    dizinler(data_dir=str(tmp_path))
    return TestClient(appmod.app)


def _ikinci(depo_db, *, oturum: bool = False, dogrulandi: bool = True) -> Kullanici:
    """B kullanıcısı (`b-…@example.com`); istenirse bir oturum satırıyla."""
    with Session(depo_db, expire_on_commit=False) as s:
        k = Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                      dogrulandi_at=hesap.simdi() if dogrulandi else None, dil=None)
        s.add(k)
        s.flush()
        if oturum:
            hesap.oturum_ac(s, k, None, "test", hesap.simdi())
        s.commit()
        return k


def _is(depo_db, kid: uuid.UUID, *, durum: str = "bekliyor", an: dt.datetime = AN,
        model: str = MODEL_ID, kredi: int = KREDI, kaynak: str | None = "platform",
        sure_sn: int | None = None, gercek: int | None = None,
        maliyet_usd: str | None = None) -> uuid.UUID:
    """Doğrudan `isler`e satır; `sure_sn` verilirse `basladi`/`bitti` ona göre (p50/p95 tohumu);
    `gercek`/`maliyet_usd` (Faz 3 / 5) `kredi_gercek`/`saglayici_maliyet_usd` sütunları (marj tohumu)."""
    with Session(depo_db) as s:
        is_ = kuyruk.ekle(s, kid, "generate", {"prompt": "x"}, model, kredi, an=an, anahtar_kaynagi=kaynak)
        is_.durum = durum
        is_.kredi_gercek = gercek
        is_.saglayici_maliyet_usd = Decimal(maliyet_usd) if maliyet_usd is not None else None
        if sure_sn is not None or durum in ("bitti", "hata", "calisiyor"):
            is_.basladi = an
        if sure_sn is not None:
            is_.bitti = an + dt.timedelta(seconds=sure_sn)
        elif durum in ("bitti", "hata", "iptal"):
            is_.bitti = an
        s.commit()
        return is_.id


def _yol(p: str) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: YOL_DEGERLERI[m.group(1)], p)


# ─────────────────────────────────────────────────────────────── kapı

@pytest.mark.parametrize("yontem, yol", sorted(ADMIN_ROTALAR))
def test_every_admin_route_answers_403_json_to_a_signed_in_non_admin(c, kullanici, yontem, yol):
    """Belge §8: admin değilse 403 — 404 DEĞİL (admin varlığı gizli değil); gövde i18n'li, isteğin dilinde."""
    assert kullanici.is_admin is False
    cevap = c.request(yontem, _yol(yol), json={} if yontem == "POST" else None)
    assert cevap.status_code == 403, (yontem, yol, cevap.text)
    assert cevap.json() == {"detail": i18n.t("err.admin_gerekli", "en")}
    tr = c.request(yontem, _yol(yol), json={} if yontem == "POST" else None, headers={"X-Kromis-Lang": "tr"})
    assert tr.json() == {"detail": i18n.t("err.admin_gerekli", "tr")}


def test_the_admin_page_is_403_html_for_a_non_admin_and_the_studio_link_stays(c, kullanici):
    cevap = c.get("/admin")
    assert cevap.status_code == 403
    assert cevap.headers["content-type"].startswith("text/html")
    assert cevap.headers["cache-control"] == "no-store"
    assert i18n.t("admin.yetki_yok", "en") in cevap.text and 'href="/"' in cevap.text
    assert i18n.t("admin.yetki_yok", "tr") in c.get("/admin", headers={"X-Kromis-Lang": "tr"}).text


def test_the_admin_gate_binds_the_admin_tenant_context_in_the_request(c, admin, monkeypatch):
    """Belge §7 devri (1): kapı `app.rol='admin'` + kendi id'sini bağlar; rota bağlamı bu hâliyle görür."""
    gorulen: list[kiraci.Baglam | None] = []
    asil = depo_admin.metrikler

    def _casus(db, an=None):
        gorulen.append(kiraci.aktif())
        return asil(db, an)
    monkeypatch.setattr(depo_admin, "metrikler", _casus)
    assert c.get("/api/admin/metrikler").status_code == 200
    assert gorulen == [kiraci.Baglam(kullanici_id=admin.id, rol=kiraci.ADMIN)]


# ─────────────────────────────────────────────────────────────── sayfa

@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_the_admin_page_is_served_translated_with_only_the_dictionary_and_its_own_script(c, admin, lang):
    cevap = c.get("/admin", headers={"X-Kromis-Lang": lang})
    assert cevap.status_code == 200 and cevap.headers["cache-control"] == "no-store"
    html = cevap.text
    assert f'<html lang="{lang}">' in html
    assert "{{t:" not in html and "__APP_" not in html
    assert f'window.KROMIS_LANG="{lang}"' in html and "window.KROMIS_I18N={" in html
    for anahtar in ("admin.sekme_kullanicilar", "admin.sekme_kuyruk", "admin.sekme_metrikler", "admin.sekme_odeme",
                    "admin.tavan_yaz"):
        assert i18n.t(anahtar, lang) in html, anahtar
    assert re.findall(r'<script src="/static/([a-z0-9_.-]+)\?v=', html) == ["i18n.js", "admin.js"]
    assert re.findall(r'<link rel="stylesheet" href="/static/([a-z0-9_.-]+)\?v=', html) == [
        "fonts.css", "flow-tokens.css", "admin.css"]
    assert set(re.findall(r"\?v=([^\"'\s>]+)", html)) == {version.APP_VERSION}


def test_every_id_the_admin_script_binds_exists_in_the_admin_page_and_it_calls_every_admin_route():
    """admin.js `KAPSAM_DISI`nda (tests/test_id_contract.py) — id bağlarının ve rota adlarının bekçisi burası."""
    with open(os.path.join(REPO, "static", "admin.js"), encoding="utf-8") as f:
        js = f.read()
    with open(os.path.join(REPO, "static", "admin.html"), encoding="utf-8") as f:
        html = f.read()
    idler = set(re.findall(r'id="([a-zA-Z0-9_-]+)"', html))
    bagli = set(re.findall(r'\bel\("([a-zA-Z0-9_-]+)"\)', js))
    bagli |= set(re.findall(r'querySelector(?:All)?\(["\']#([a-zA-Z0-9_-]+)', js))
    bagli |= {f"sekme-{s}" for s in re.findall(r'"(kullanicilar|kuyruk|metrikler|odeme)"', js)}
    assert bagli, "tarama boş — desen bayatladı mı?"
    assert bagli <= idler, f"admin.js şu id'lere bağlanıyor ama sayfada yok: {sorted(bagli - idler)}"
    for yol in ("/api/admin/kullanicilar", "/api/admin/isler", "/api/admin/metrikler", "/api/admin/odeme-olaylari"):
        assert f'"{yol}' in js or f"`{yol}" in js, yol
    for parca in ("/tavan`", "/oturum-dusur`", "/iptal`", "/plan`", "/kredi`", '"/giris?sonra="'):
        assert parca in js, parca
    assert "30000" in js, "sayfa 30 sn'de bir yenilenir (belge §8)"


def test_the_settings_script_offers_the_admin_link_only_to_admins_and_names_the_own_key():
    """Belge §8 (`settings.js` Hakkında) ve sahibe söz verilen not: "Kendi anahtarımı sil"in üstünde durum cümlesi."""
    with open(os.path.join(REPO, "static", "settings.js"), encoding="utf-8") as f:
        js = f.read()
    assert "if (ben.is_admin)" in js and 'admin.href = "/admin"' in js
    assert 't("hesap.admin_baglantisi")' in js
    assert 't("settings.kendi_anahtar_kullaniliyor")' in js
    assert 'kendi.hidden = kaynak !== "kullanici"' in js
    # Not, düğmeden ÖNCE ekleniyor (kullanıcı önce durumu, sonra eylemi okur).
    assert js.index("kendi-anahtar-notu") < js.index('sil = document.createElement("button")')


def test_the_job_panel_asks_the_quota_endpoint_for_the_daily_remaining_line():
    with open(os.path.join(REPO, "static", "isler.js"), encoding="utf-8") as f:
        js = f.read()
    with open(os.path.join(REPO, "static", "index.html"), encoding="utf-8") as f:
        html = f.read()
    assert '"/api/kota"' in js and 't("isler.gunluk_kalan"' in js
    assert 'id="isler-kota"' in html


# ─────────────────────────────────────────────────────── kullanıcılar

def test_users_are_listed_newest_first_with_derived_fields_searched_and_paged(c, depo_db, admin, monkeypatch):
    from services import zaman
    monkeypatch.setattr(zaman, "an", lambda: AN)
    b = _ikinci(depo_db, oturum=True)
    d = _ikinci(depo_db, dogrulandi=False)
    _is(depo_db, b.id, durum="bekliyor")                                  # aktif, sayılır
    _is(depo_db, b.id, durum="bitti", an=AN - dt.timedelta(hours=2))      # 24 sa içinde, sayılır
    _is(depo_db, b.id, durum="bitti", an=AN - dt.timedelta(hours=30))     # dışında
    _is(depo_db, b.id, durum="iptal")                                     # iptal sayılmaz
    _is(depo_db, b.id, durum="bitti", kaynak="kullanici")                 # BYOK sayılmaz
    r = c.get("/api/admin/kullanicilar")
    assert r.status_code == 200
    govde = r.json()
    assert govde["toplam"] == 3 and govde["sayfa"] == 1 and govde["adet"] == depo_admin.SAYFA_ADEDI
    satirlar = {k["eposta"]: k for k in govde["kullanicilar"]}
    assert set(satirlar) == {admin.eposta, b.eposta, d.eposta}
    assert [k["id"] for k in govde["kullanicilar"]] == [str(d.id), str(b.id), str(admin.id)], "en yeni üstte"
    bs = satirlar[b.eposta]
    assert bs["kredi_24sa"] == 2 * KREDI and bs["aktif_is"] == 1 and bs["son_gorulme"] is not None
    assert bs["gunluk_kredi_tavani"] is None and bs["is_admin"] is False and bs["dogrulandi"] is True
    assert satirlar[admin.eposta]["is_admin"] is True and satirlar[admin.eposta]["son_gorulme"] is None
    assert satirlar[d.eposta]["dogrulandi"] is False
    assert set(bs) == {"id", "eposta", "is_admin", "dogrulandi", "olusturuldu", "son_gorulme",
                       "gunluk_kredi_tavani", "kredi_24sa", "aktif_is", "plan", "bakiye",
                       "paket_bakiye", "polar_musteri_id", "silindi_at", "temizlendi_at"}
    assert bs["silindi_at"] is None and bs["temizlendi_at"] is None, "Faz 4 / 5: yaşayan hesapta iki damga boş"
    assert bs["plan"] == "free" and bs["bakiye"] == 0, "Faz 3 / 3: plan ve bakiye satırın kendi sütunları"
    assert bs["paket_bakiye"] == 0 and bs["polar_musteri_id"] is None, "Faz 4 / 4: paket kovası ve Polar kimliği"
    # Arama e-postada geçen metin; joker karakter düz metin.
    assert [k["id"] for k in c.get(f"/api/admin/kullanicilar?q={b.eposta[:10]}").json()["kullanicilar"]] == [str(b.id)]
    assert c.get("/api/admin/kullanicilar?q=%25").json()["toplam"] == 0
    # Sayfalama: adet=2 → 2 + 1.
    s1 = c.get("/api/admin/kullanicilar?adet=2&sayfa=1").json()
    s2 = c.get("/api/admin/kullanicilar?adet=2&sayfa=2").json()
    assert len(s1["kullanicilar"]) == 2 and len(s2["kullanicilar"]) == 1 and s2["toplam"] == 3
    assert c.get("/api/admin/kullanicilar?adet=0").status_code == 422
    assert c.get(f"/api/admin/kullanicilar?adet={depo_admin.SAYFA_ADEDI_AZAMI + 1}").status_code == 422


def test_writing_a_cap_updates_the_row_and_null_clears_it_and_bad_input_is_422_or_404(c, depo_db, admin, gunluk):
    b = _ikinci(depo_db)
    r = c.post(f"/api/admin/kullanicilar/{b.id}/tavan", json={"tavan": 500})
    assert r.status_code == 200 and r.json() == {"id": str(b.id), "gunluk_kredi_tavani": 500}
    with Session(depo_db) as s:
        assert s.scalar(select(Kullanici.gunluk_kredi_tavani).where(Kullanici.id == b.id)) == 500
    assert c.get("/api/admin/kullanicilar").json()["kullanicilar"][0]["gunluk_kredi_tavani"] == 500
    assert c.post(f"/api/admin/kullanicilar/{b.id}/tavan", json={"tavan": None}).json()["gunluk_kredi_tavani"] is None
    with Session(depo_db) as s:
        assert s.scalar(select(Kullanici.gunluk_kredi_tavani).where(Kullanici.id == b.id)) is None
    for kotu in ({"tavan": 0}, {"tavan": -5}, {"tavan": "bes"}, {"tavan": 10**10}):
        assert c.post(f"/api/admin/kullanicilar/{b.id}/tavan", json=kotu).status_code == 422, kotu
    yok = c.post(f"/api/admin/kullanicilar/{uuid.uuid4()}/tavan", json={"tavan": 5})
    assert yok.status_code == 404 and yok.json()["detail"] == i18n.t("err.kullanici_bulunamadi", "en")
    assert c.post("/api/admin/kullanicilar/abc/tavan", json={"tavan": 5}).status_code == 422
    assert gunluk.satirlar[0] == {"olay": "admin.tavan", "admin": str(admin.id), "hedef": str(b.id),
                                  "tavan": 500}, gunluk.satirlar
    assert gunluk.satirlar[1] == {"olay": "admin.tavan", "admin": str(admin.id), "hedef": str(b.id),
                                  "tavan": None}
    assert len(gunluk.satirlar) == 2, "422/404 günlüğe düşmez — yazım olmadı"


@pytest.mark.gercek_kimlik
@pytest.mark.gercek_anahtar
def test_a_cap_written_by_the_admin_moves_the_users_429_threshold_on_their_very_next_job(
        depo_db, tmp_path, dizinler, monkeypatch):
    """Çıkış ölçütü: admin tavanı değiştirir, kullanıcının 429'u YENİ tavana göre gelir; NULL öntanımlıya döner.

    Gerçek çerezle: kapı kullanıcının SATIRINI her istekte çözer (`oturumlar ⋈
    kullanicilar`), yani adminin commit'i bir sonraki istekte görünür — override
    nesnesi bunu göremezdi. Platform anahtarı ortamda ki iş `platform` sayılsın.
    """
    monkeypatch.delenv(cerez.GUVENLI_ENV, raising=False)
    monkeypatch.setenv(platform_anahtari.ONEK + "AZURE_IMAGE_API_KEY", "PLATFORM-TEST-ANAHTARI")
    monkeypatch.setenv(platform_anahtari.ONEK + "AZURE_IMAGE_BASE_URL", "https://p.openai.azure.com/openai/v1/")
    monkeypatch.delenv(kota.GUNLUK_KREDI_ENV, raising=False)
    dizinler(data_dir=str(tmp_path))
    with TestClient(appmod.app, base_url=HTTPS):
        a_id, a_jeton = _gercek_kullanici(admin=True)
        b_id, b_jeton = _gercek_kullanici()
        # Platform işi bakiye ister (Faz 3 / 2, 402): B'ye defterden kredi, tavan ölçümü 402'ye takılmasın.
        with Session(depo_db) as s:
            defter.hibe(s, b_id, 1000, f"{defter.ONEK_HIBE}{b_id}:2026-09")
            s.commit()
        a = TestClient(appmod.app, base_url=HTTPS, cookies={cerez.OTURUM_CEREZI: a_jeton})
        b = TestClient(appmod.app, base_url=HTTPS, cookies={cerez.OTURUM_CEREZI: b_jeton})
        assert b.get("/api/hesap/ben").json()["is_admin"] is False
        assert b.post("/api/admin/kullanicilar/" + str(a_id) + "/tavan", json={"tavan": 1}).status_code == 403
        ilk = b.post("/api/generate", json=GORSEL)
        assert ilk.status_code == 202 and ilk.json()["is"]["anahtar_kaynagi"] == "platform", ilk.text
        assert a.post(f"/api/admin/kullanicilar/{b_id}/tavan", json={"tavan": KREDI}).status_code == 200
        r = b.post("/api/generate", json=GORSEL)
        assert r.status_code == 429, r.text
        assert "Retry-After" in r.headers
        assert str(KREDI) in r.json()["detail"] and "2000" not in r.json()["detail"], "429 YENİ tavanı söyler"
        kota_g = b.get("/api/kota").json()["gunluk"]
        assert (kota_g["tavan"], kota_g["kullanilan"], kota_g["kalan"]) == (KREDI, KREDI, 0)
        assert kota_g["acilis"] is not None
        assert a.post(f"/api/admin/kullanicilar/{b_id}/tavan", json={"tavan": 3 * KREDI}).status_code == 200
        assert b.post("/api/generate", json=GORSEL).status_code == 202
        assert b.get("/api/kota").json()["gunluk"]["kalan"] == KREDI
        assert a.post(f"/api/admin/kullanicilar/{b_id}/tavan", json={"tavan": None}).status_code == 200
        assert b.get("/api/kota").json()["gunluk"]["tavan"] == kota.GUNLUK_KREDI_VARSAYILAN
        assert b.post("/api/generate", json=GORSEL).status_code == 202
        # Admin listede kullanıcının 24 sa kredisini ve tavanını görür.
        satir = next(k for k in a.get("/api/admin/kullanicilar").json()["kullanicilar"] if k["id"] == str(b_id))
        assert satir["kredi_24sa"] == 3 * KREDI and satir["gunluk_kredi_tavani"] is None and satir["aktif_is"] == 3


def _gercek_kullanici(*, admin: bool = False) -> tuple[uuid.UUID, str]:
    """Lifespan motorunda doğrulanmış kullanıcı + oturum; `(id, ham jeton)` (tests/test_kimlik.py deseni)."""
    an = hesap.simdi()
    with Session(appmod.app.state.motor) as s:
        k = Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                      dogrulandi_at=an, is_admin=admin)
        s.add(k)
        s.flush()
        jeton = hesap.oturum_ac(s, k, None, "test", an)
        kid = k.id
        s.commit()
    return kid, jeton


@pytest.mark.gercek_kimlik
def test_dropping_a_users_sessions_kills_their_cookie_and_leaves_the_admins(depo_db, tmp_path, dizinler,
                                                                            monkeypatch, gunluk):
    monkeypatch.delenv(cerez.GUVENLI_ENV, raising=False)
    dizinler(data_dir=str(tmp_path))
    with TestClient(appmod.app, base_url=HTTPS):
        a_id, a_jeton = _gercek_kullanici(admin=True)
        b_id, b_jeton = _gercek_kullanici()
        with Session(appmod.app.state.motor) as s:
            hesap.oturum_ac(s, s.get(Kullanici, b_id), None, "ikinci cihaz", hesap.simdi())
            s.commit()
        a = TestClient(appmod.app, base_url=HTTPS, cookies={cerez.OTURUM_CEREZI: a_jeton})
        b = TestClient(appmod.app, base_url=HTTPS, cookies={cerez.OTURUM_CEREZI: b_jeton})
        assert b.get("/api/hesap/ben").status_code == 200
        r = a.post(f"/api/admin/kullanicilar/{b_id}/oturum-dusur")
        assert r.status_code == 200 and r.json() == {"id": str(b_id), "dusurulen": 2}
        assert b.get("/api/hesap/ben").status_code == 401, "çerez öldü"
        assert b.get("/", follow_redirects=False).status_code == 302
        assert a.get("/api/hesap/ben").status_code == 200, "adminin oturumu durur"
        assert a.post(f"/api/admin/kullanicilar/{b_id}/oturum-dusur").json()["dusurulen"] == 0
        assert a.post(f"/api/admin/kullanicilar/{uuid.uuid4()}/oturum-dusur").status_code == 404
    assert gunluk.satirlar[0] == {"olay": "admin.oturum_dusur", "admin": str(a_id), "hedef": str(b_id),
                                  "adet": 2}


# ──────────────────────────────────────────────────────────────── kuyruk

def test_the_queue_view_lists_everyones_jobs_with_owner_and_summary_and_filters_by_status(
        c, depo_db, admin, monkeypatch):
    from services import zaman
    monkeypatch.setattr(zaman, "an", lambda: AN)
    b = _ikinci(depo_db)
    bek = _is(depo_db, b.id, durum="bekliyor", an=AN - dt.timedelta(seconds=90))
    cal = _is(depo_db, admin.id, durum="calisiyor", an=AN - dt.timedelta(seconds=30))
    _is(depo_db, b.id, durum="hata", an=AN - dt.timedelta(hours=1))
    _is(depo_db, b.id, durum="hata", an=AN - dt.timedelta(hours=30))    # 24 sa dışında
    r = c.get("/api/admin/isler")
    assert r.status_code == 200
    govde = r.json()
    assert [i["id"] for i in govde["isler"]] == [str(cal), str(bek)] + [i["id"] for i in govde["isler"][2:]]
    assert len(govde["isler"]) == 4
    sahipler = {i["id"]: (i["kullanici_id"], i["eposta"]) for i in govde["isler"]}
    assert sahipler[str(bek)] == (str(b.id), b.eposta) and sahipler[str(cal)] == (str(admin.id), admin.eposta)
    assert "istek" not in govde["isler"][0] and "isci_id" not in govde["isler"][0], "admin de prompt'u görmez"
    assert govde["ozet"] == {"bekleyen": 1, "calisan": 1, "hata_24sa": 1, "en_eski_bekleyen_sn": 90}
    assert [i["id"] for i in c.get("/api/admin/isler?durum=bekliyor").json()["isler"]] == [str(bek)]
    assert c.get("/api/admin/isler?durum=hata").json()["ozet"]["bekleyen"] == 1, "özet süzgeçten bağımsız"
    kotu = c.get("/api/admin/isler?durum=uydurma")
    assert kotu.status_code == 422 and kotu.json()["detail"] == i18n.t("err.is_durumu_gecersiz", "en", durum="uydurma")


def test_the_admin_cancels_another_users_waiting_job_but_not_a_running_one(c, depo_db, admin, gunluk):
    b = _ikinci(depo_db)
    bek = _is(depo_db, b.id, durum="bekliyor")
    cal = _is(depo_db, b.id, durum="calisiyor")
    r = c.post(f"/api/admin/isler/{bek}/iptal")
    assert r.status_code == 200, r.text
    assert r.json()["is"]["durum"] == "iptal" and r.json()["is"]["kullanici_id"] == str(b.id)
    assert r.json()["is"]["bitti"] is not None
    with Session(depo_db) as s:
        assert s.get(tablolar.Is, bek).durum == "iptal"
    tekrar = c.post(f"/api/admin/isler/{bek}/iptal")
    assert tekrar.status_code == 409 and tekrar.json()["detail"] == i18n.t("err.is_iptal_edilemez", "en", durum="iptal")
    r409 = c.post(f"/api/admin/isler/{cal}/iptal")
    assert r409.status_code == 409 and "calisiyor" in r409.json()["detail"]
    with Session(depo_db) as s:
        assert s.get(tablolar.Is, cal).durum == "calisiyor", "çalışan işe dokunulmadı (K8)"
    yok = c.post(f"/api/admin/isler/{uuid.uuid4()}/iptal")
    assert yok.status_code == 404 and yok.json()["detail"] == i18n.t("err.is_bulunamadi", "en")
    assert gunluk.satirlar == [{"olay": "admin.is_iptal", "admin": str(admin.id), "is": str(bek),
                                "sahip": str(b.id)}], "409/404 günlüğe düşmez"
    # Kullanıcının kendi iptali başkasının işine hâlâ 404 (routers/isler.py değişmedi).
    kullanici_c = TestClient(appmod.app)
    admin.is_admin = False
    assert kullanici_c.post(f"/api/isler/{cal}/iptal").status_code == 404


# ───────────────────────────────────────────────────────────── metrikler

def test_metrics_are_derived_from_isler_and_isciler_with_seeded_percentiles(c, depo_db, admin, monkeypatch):
    from services import zaman
    monkeypatch.setattr(zaman, "an", lambda: AN)
    b = _ikinci(depo_db)
    for sn in (10, 20, 30):                                                  # p50 20, p95 29
        _is(depo_db, b.id, durum="bitti", an=AN - dt.timedelta(hours=3), sure_sn=sn, kredi=100)
    _is(depo_db, admin.id, durum="bitti", an=AN - dt.timedelta(minutes=10), model="baska", sure_sn=5)
    _is(depo_db, b.id, durum="hata", an=AN - dt.timedelta(minutes=20))       # son 1 sa: hata
    _is(depo_db, b.id, durum="bekliyor", an=AN - dt.timedelta(seconds=45))
    _is(depo_db, b.id, durum="bekliyor", an=AN - dt.timedelta(seconds=15))
    _is(depo_db, b.id, durum="iptal", an=AN - dt.timedelta(minutes=5))       # hiçbir sayıma girmez
    _is(depo_db, b.id, durum="bitti", an=AN - dt.timedelta(hours=30), sure_sn=999, kredi=5000)   # 24 sa dışı
    _is(depo_db, b.id, durum="bitti", an=AN - dt.timedelta(hours=1), sure_sn=1, kaynak="kullanici")  # BYOK: krediye girmez
    with Session(depo_db) as s:
        kuyruk.isci_kaydet(s, "canli-konak", version.APP_VERSION, 2, AN - dt.timedelta(minutes=10))
        bayat = kuyruk.isci_kaydet(s, "bayat-konak", "0.0.1", 1, AN - dt.timedelta(hours=2))
        bayat.son_kalp = AN - dt.timedelta(minutes=5)
        s.execute(text("UPDATE isciler SET son_kalp = :an WHERE konak = 'canli-konak'"), {"an": AN})
        s.commit()
    r = c.get("/api/admin/metrikler")
    assert r.status_code == 200, r.text
    m = r.json()
    assert set(m) == {"an", "kuyruk", "son_1sa", "son_24sa", "modeller", "isciler", "marj", "gelir"}
    assert m["kuyruk"] == {"derinlik": 2, "calisan": 0, "en_eski_bekleyen_sn": 45}
    assert m["son_1sa"] == {"is": 4, "hata": 1, "hata_orani": 0.25}            # baska + hata + 2 bekleyen
    assert m["son_24sa"]["is"] == 8 and m["son_24sa"]["hata"] == 1          # 3 tohum + baska + hata + 2 bekleyen + BYOK
    assert m["son_24sa"]["hata_orani"] == 0.125
    # Faz 3 / 5: gerçek biliniyorsa gerçek, yoksa rezerv (`COALESCE`); tohumlarda gerçek yok → iki sayı aynı.
    assert m["son_24sa"]["platform_kredi"] == 3 * 100 + 4 * KREDI            # baska, hata, 2 bekleyen; BYOK ve iptal yok
    assert m["son_24sa"]["platform_kredi_rezerv"] == m["son_24sa"]["platform_kredi"]
    assert {r["gun"] for r in m["marj"]} <= {7, 30} and all(r["adet"] + r["hata"] > 0 for r in m["marj"])
    assert m["modeller"] == [
        {"model": MODEL_ID, "adet": 4, "p50_sn": 15.0, "p95_sn": 28.5},      # [1, 10, 20, 30] sn (BYOK da biten iş)
        {"model": "baska", "adet": 1, "p50_sn": 5.0, "p95_sn": 5.0},
    ]
    isciler = {i["konak"]: i for i in m["isciler"]}
    assert isciler["canli-konak"]["canli"] is True and isciler["canli-konak"]["es_zamanli"] == 2
    assert isciler["bayat-konak"]["canli"] is False and isciler["bayat-konak"]["surum"] == "0.0.1"


def test_percentiles_are_percentile_cont_over_bitti_minus_basladi(depo_db, admin, monkeypatch):
    """p50/p95 hesabı tohumla, doğrudan depo: [10, 20, 30] sn → p50 20, p95 29 (doğrusal ara değer)."""
    b = _ikinci(depo_db)
    for sn in (10, 20, 30):
        _is(depo_db, b.id, durum="bitti", an=AN - dt.timedelta(hours=1), sure_sn=sn)
    with Session(depo_db) as s:
        m = depo_admin.metrikler(s, AN)
    assert m["modeller"] == [{"model": MODEL_ID, "adet": 3, "p50_sn": 20.0, "p95_sn": 29.0}]
    assert m["son_24sa"]["hata_orani"] == 0.0 and m["kuyruk"]["en_eski_bekleyen_sn"] is None
    assert m["isciler"] == []


# ───────────────────────────────────────────────────────────────── marj (Faz 3 / 5)

def test_the_margin_rows_split_two_models_over_seven_and_thirty_days_with_known_and_unknown_cost(depo_db, admin):
    """Belge §5 çıkış ölçütü: iki model → iki satır; Σ kredi_gercek ve ≈USD (× 0,005) doğru; süre
    `AVG(bitti − basladi)`; sağlayıcı USD yalnız dolu satırlardan ve "bilinen n/N"; `hata` işleri ve
    TAHMİNİ kredileri ayrı; `iptal`/aktif ve pencere dışı işler girmez."""
    b = _ikinci(depo_db)
    g = dt.timedelta(days=1)
    _is(depo_db, b.id, durum="bitti", an=AN - 2 * g, sure_sn=10, gercek=8, maliyet_usd="0.0389")
    _is(depo_db, b.id, durum="bitti", an=AN - 5 * g, sure_sn=20, gercek=6)
    _is(depo_db, admin.id, durum="bitti", an=AN - 20 * g, sure_sn=30, gercek=10, maliyet_usd="0.05")
    _is(depo_db, b.id, durum="hata", an=AN - 1 * g, kredi=16)                          # K8 zararı
    _is(depo_db, b.id, durum="bitti", an=AN - 40 * g, sure_sn=1, gercek=999)          # 30 gün dışı
    _is(depo_db, b.id, durum="bitti", an=AN - 10 * g, model="baska", sure_sn=5, gercek=27)
    _is(depo_db, b.id, durum="iptal", an=AN - 1 * g, model="baska", kredi=50)         # girmez
    _is(depo_db, b.id, durum="bekliyor", an=AN - 1 * g, model="baska")                # girmez
    _is(depo_db, b.id, durum="calisiyor", an=AN - 1 * g, model="baska")               # girmez
    with Session(depo_db) as s:
        yedi = depo_admin.marj(s, 7, AN)
        otuz = depo_admin.marj(s, 30, AN)
    assert yedi == [{"model": MODEL_ID, "gun": 7, "adet": 2, "kredi": 14, "usd": 0.07,
                     "maliyet_usd": 0.0389, "maliyet_bilinen": 1, "ort_sure_sn": 15.0,
                     "hata": 1, "hata_kredi": 16}]
    assert otuz == [
        {"model": MODEL_ID, "gun": 30, "adet": 3, "kredi": 24, "usd": 0.12,
         "maliyet_usd": 0.0889, "maliyet_bilinen": 2, "ort_sure_sn": 20.0, "hata": 1, "hata_kredi": 16},
        {"model": "baska", "gun": 30, "adet": 1, "kredi": 27, "usd": 0.135,
         "maliyet_usd": None, "maliyet_bilinen": 0, "ort_sure_sn": 5.0, "hata": 0, "hata_kredi": 0},
    ], "bilinmeyen maliyet `None` (sıfır DEĞİL), sıra en çok iş üstte"
    assert depo_admin.MARJ_PENCERELERI == (7, 30)


def test_the_metrics_endpoint_carries_the_margin_rows_and_the_actual_credit_sum_beside_the_reserved_one(
        c, depo_db, admin, monkeypatch):
    from services import zaman
    monkeypatch.setattr(zaman, "an", lambda: AN)
    b = _ikinci(depo_db)
    _is(depo_db, b.id, durum="bitti", an=AN - dt.timedelta(hours=2), sure_sn=10, kredi=8, gercek=6)  # 2 iade edildi
    _is(depo_db, b.id, durum="bekliyor", an=AN - dt.timedelta(minutes=5), kredi=8)                  # gerçek yok → rezerv
    m = c.get("/api/admin/metrikler").json()
    assert m["son_24sa"]["platform_kredi"] == 6 + 8, "bitende GERÇEK (6), bekleyende rezerv (8)"
    assert m["son_24sa"]["platform_kredi_rezerv"] == 8 + 8, "rezerv edilen: tahminlerin toplamı"
    assert [(r["gun"], r["model"], r["adet"], r["kredi"]) for r in m["marj"]] == [(7, MODEL_ID, 1, 6), (30, MODEL_ID, 1, 6)]
    kullanicilar = {k["eposta"]: k for k in c.get("/api/admin/kullanicilar").json()["kullanicilar"]}
    assert kullanicilar[b.eposta]["kredi_24sa"] == 6 + 8, "`kullanicilar.kredi_24sa` aynı `COALESCE`"


def test_the_admin_page_renders_the_margin_table_with_its_own_keys_in_both_languages(c, admin):
    with open(os.path.join(REPO, "static", "admin.js"), encoding="utf-8") as f:
        js = f.read()
    assert 'el("admin-marj")' in js and "m.marj.map" in js and "platform_kredi_rezerv" in js
    for anahtar in ("admin.marj_bilinmiyor", "admin.marj_maliyet", "admin.marj_hata", "admin.metrik_rezerv"):
        assert f't("{anahtar}"' in js, anahtar
    for lang in i18n.LANGUAGES:
        html = c.get("/admin", headers={"X-Kromis-Lang": lang}).text
        assert 'id="admin-marj"' in html
        for anahtar in ("admin.metrik_marj", "admin.sutun_gun", "admin.sutun_kredi", "admin.sutun_usd",
                        "admin.sutun_maliyet_usd", "admin.sutun_ort_sure", "admin.sutun_hata"):
            assert i18n.t(anahtar, lang) in html, (lang, anahtar)


# ───────────────────────────────────────────────────────────── gelir (Faz 4 / 7)

def _siparis(depo_db, kid: uuid.UUID, an: dt.datetime, tutar: int, birim: str = "usd") -> None:
    """`siparisler` tohumu (webhook'un yazdığı satır); ürün aynası tek DUMMY paket."""
    from services.tablolar import Siparis, Urun
    with Session(depo_db) as s:
        urun = s.scalar(select(Urun).limit(1))
        if urun is None:
            urun = Urun(polar_urun_id="prod-DUMMY", tur="paket", plan=None, kredi=500, fiyat_kurus=500,
                        para_birimi="usd", ad="DUMMY paket")
            s.add(urun)
            s.flush()
        s.add(Siparis(kullanici_id=kid, polar_siparis_id=f"ord_{uuid.uuid4().hex[:10]}", urun_id=urun.id,
                      sebep="purchase", tutar_kurus=tutar, para_birimi=birim, olusturuldu=an))
        s.commit()


def test_the_revenue_rows_sum_usd_orders_per_window_and_estimate_the_polar_fee(depo_db, admin):
    """Belge §7 "gelir sütunu": dönem başına TEK satır (sipariş modele bağlanamaz) — adet, Σ USD, Polar ücreti
    TAHMİNİ (%6,5 + 0,50 varsayımı, `POLAR_UCRET_ORAN`/`POLAR_UCRET_SABIT_KURUS`), net; pencere dışı ve başka
    para birimindeki sipariş toplama GİRMEZ (ikincisi `diger_para_birimi`nde sayılır); sipariş yoksa bilinen 0."""
    b = _ikinci(depo_db)
    g = dt.timedelta(days=1)
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM siparisler"))
    _siparis(depo_db, b.id, AN - 2 * g, 1_400)            # 7 ve 30 gün
    _siparis(depo_db, admin.id, AN - 20 * g, 3_000)       # yalnız 30 gün
    _siparis(depo_db, b.id, AN - 40 * g, 99_900)          # pencere dışı
    _siparis(depo_db, b.id, AN - 1 * g, 700, birim="eur")  # toplanmaz, sayılır
    with Session(depo_db) as s:
        yedi = depo_admin.gelir(s, 7, AN)
        otuz = depo_admin.gelir(s, 30, AN)
        bos = depo_admin.gelir(s, 1, AN + 400 * g)   # pencere `>` alt sınırlı (marj'ın deyimi): ileride boş
    assert depo_admin.POLAR_UCRET_ORAN == Decimal("0.065") and depo_admin.POLAR_UCRET_SABIT_KURUS == 50
    assert yedi == {"gun": 7, "siparis": 1, "gelir_usd": 14.0, "polar_ucreti_usd": 1.41, "net_usd": 12.59,
                    "diger_para_birimi": 1}
    assert otuz == {"gun": 30, "siparis": 2, "gelir_usd": 44.0, "polar_ucreti_usd": 3.86, "net_usd": 40.14,
                    "diger_para_birimi": 1}, "14 + 30 USD; ücret 44 × 0,065 + 2 × 0,50"
    assert bos == {"gun": 1, "siparis": 0, "gelir_usd": 0.0, "polar_ucreti_usd": 0.0, "net_usd": 0.0,
                   "diger_para_birimi": 0}, "sipariş yokken bilinen sıfır — marj'ın `None`inden farklı"
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM siparisler"))


def test_the_metrics_endpoint_carries_one_revenue_row_per_margin_window_and_the_page_renders_the_table(
        c, depo_db, admin, monkeypatch):
    from services import zaman
    monkeypatch.setattr(zaman, "an", lambda: AN)
    b = _ikinci(depo_db)
    with depo_db.begin() as k:
        k.execute(text("DELETE FROM siparisler"))
    _siparis(depo_db, b.id, AN - dt.timedelta(hours=2), 500)
    m = c.get("/api/admin/metrikler").json()
    assert [(r["gun"], r["siparis"], r["gelir_usd"]) for r in m["gelir"]] == [(7, 1, 5.0), (30, 1, 5.0)]
    assert [r["gun"] for r in m["gelir"]] == list(depo_admin.MARJ_PENCERELERI), "marj ile aynı iki pencere"
    with open(os.path.join(REPO, "static", "admin.js"), encoding="utf-8") as f:
        js = f.read()
    assert 'el("admin-gelir")' in js and "m.gelir.map" in js and "polar_ucreti_usd" in js and 't("admin.gelir_diger"' in js
    for lang in i18n.LANGUAGES:
        html = c.get("/admin", headers={"X-Kromis-Lang": lang}).text
        assert 'id="admin-gelir"' in html
        for anahtar in ("admin.metrik_gelir", "admin.sutun_siparis", "admin.sutun_gelir_usd",
                        "admin.sutun_polar_ucreti", "admin.sutun_net_usd"):
            assert i18n.t(anahtar, lang) in html, (lang, anahtar)
        # Varsayım etikette YAZILI: okuyan sayının tahmin olduğunu tablo başlığından görür.
        assert "6,5" in i18n.t("admin.metrik_gelir", lang) or "6.5" in i18n.t("admin.metrik_gelir", lang)
    with depo_db.begin() as k:
        k.execute(text("DELETE FROM siparisler"))


# ─────────────────────────────────────────────────────────── GET /api/kota

def test_the_quota_endpoint_reports_daily_remaining_and_hourly_count_for_the_signed_in_user(
        c, depo_db, kullanici, monkeypatch):
    from services import zaman
    monkeypatch.setattr(zaman, "an", lambda: AN)
    monkeypatch.delenv(kota.GUNLUK_KREDI_ENV, raising=False)
    monkeypatch.delenv(kota.SAATLIK_IS_ENV, raising=False)
    bos = c.get("/api/kota").json()
    assert bos == {"gunluk": {"tavan": kota.GUNLUK_KREDI_VARSAYILAN, "kullanilan": 0,
                              "kalan": kota.GUNLUK_KREDI_VARSAYILAN, "acilis": None},
                   "saatlik": {"tavan": kota.SAATLIK_IS_VARSAYILAN, "sayi": 0, "acilis": None}}
    _is(depo_db, kullanici.id, durum="bitti", an=AN - dt.timedelta(hours=5), kredi=100)   # günlük: sayılır, saatlik: değil
    _is(depo_db, kullanici.id, durum="bekliyor", an=AN - dt.timedelta(minutes=10), kredi=50)
    _is(depo_db, kullanici.id, durum="iptal", an=AN - dt.timedelta(minutes=1), kredi=999)  # iptal sayılmaz
    _is(depo_db, kullanici.id, durum="bitti", an=AN - dt.timedelta(minutes=2), kredi=7, kaynak="kullanici")  # BYOK: günlüğe girmez, saatliğe girer
    baska = _ikinci(depo_db)
    _is(depo_db, baska.id, durum="bitti", an=AN, kredi=1000)                                  # başkasının
    kullanici.gunluk_kredi_tavani = 300
    g = c.get("/api/kota").json()
    from services import zaman as z
    assert g["gunluk"] == {"tavan": 300, "kullanilan": 150, "kalan": 150,
                           "acilis": z.damga_utc(AN - dt.timedelta(hours=5) + kota.GUNLUK_PENCERE)}
    assert g["saatlik"] == {"tavan": kota.SAATLIK_IS_VARSAYILAN, "sayi": 2,
                            "acilis": z.damga_utc(AN - dt.timedelta(minutes=10) + kota.SAATLIK_PENCERE)}
    assert g["gunluk"]["acilis"].endswith("Z") and g["saatlik"]["acilis"].endswith("Z"), "dilimli, öteki damgalar gibi"
    kullanici.gunluk_kredi_tavani = 100
    assert c.get("/api/kota").json()["gunluk"]["kalan"] == 0, "aşımda eksiye düşmez"


# ────────────────────────────────────────────────────────────────── RLS

def test_without_the_admin_context_the_admin_queries_return_nothing_under_the_application_role(
        request, depo_db, kullanici):
    """KIRILMA SINIFI (belge §7 devri, madde 5): bağlam bağlanmadan koşan admin sorgusu sızmaz, BOŞ döner."""
    motor = request.getfixturevalue("uygulama_motoru")
    b = _ikinci(depo_db)
    _is(depo_db, b.id, durum="bekliyor")
    _is(depo_db, kullanici.id, durum="bekliyor")
    with kiraci.baglam(), Session(motor) as s:      # bağlam YOK
        assert kiraci.aktif() is None
        assert depo_admin.is_listesi(s)["isler"] == []
        assert depo_admin.metrikler(s)["kuyruk"]["derinlik"] == 0
        assert {k["eposta"]: k["aktif_is"] for k in depo_admin.kullanicilar(s)[0]}[b.eposta] == 0, (
            "`kullanicilar` politikasız ama türetilen `isler` sayısı bağlamsız 0")
    with kiraci.baglam(kullanici_id=kullanici.id), Session(motor) as s:   # yalnız kullanıcı
        assert {i["kullanici_id"] for i in depo_admin.is_listesi(s)["isler"]} == {str(kullanici.id)}
    with kiraci.baglam(kullanici_id=kullanici.id, rol=kiraci.ADMIN), Session(motor) as s:
        assert {i["kullanici_id"] for i in depo_admin.is_listesi(s)["isler"]} == {str(kullanici.id), str(b.id)}
        assert depo_admin.metrikler(s)["kuyruk"]["derinlik"] == 2
        assert depo_admin.is_iptal(s, [i for i in s.scalars(select(tablolar.Is)) if i.kullanici_id == b.id][0].id)
        s.commit()
    with kiraci.baglam(), Session(motor) as s:
        assert depo_admin.is_iptal(s, _is(depo_db, b.id, durum="bekliyor")) is False, "bağlamsız UPDATE 0 satır"


def test_admin_routes_under_the_application_role_see_and_change_other_users_rows(
        request, depo_db, admin, c):
    """Uçtan uca, uygulama rolüyle (`SET ROLE`, ne süper kullanıcı ne sahip): kapı bağlar, rota herkesi görür,
    iptal `yonetici_gunceller`den geçer, tavan `kullanicilar`a yazılır."""
    motor = request.getfixturevalue("uygulama_motoru")
    b = _ikinci(depo_db, oturum=True)
    bek = _is(depo_db, b.id, durum="bekliyor")
    # Metrik rotası GERÇEK saatle (`an` almıyor) son 24 saate bakar: sabit `AN` (2026-09-18) ile
    # tohumlanan iş bir gün sonra pencerenin dışına düştü ve test kendiliğinden kırmızıya döndü
    # (ölçüldü 2026-09-19). Rotanın saatine göre tohumla.
    _is(depo_db, admin.id, durum="bitti", sure_sn=3, an=zaman.an() - dt.timedelta(minutes=1))

    def _uygulama_oturumu():
        with Session(motor) as s:
            yield s
            s.commit()

    appmod.app.dependency_overrides[db.oturum] = _uygulama_oturumu    # `kullanici` fixture'ı teardown'da düşürür
    isler = c.get("/api/admin/isler").json()
    assert {i["kullanici_id"] for i in isler["isler"]} == {str(admin.id), str(b.id)}
    assert isler["ozet"]["bekleyen"] == 1
    kullanicilar = {k["eposta"]: k for k in c.get("/api/admin/kullanicilar").json()["kullanicilar"]}
    assert kullanicilar[b.eposta]["aktif_is"] == 1 and kullanicilar[b.eposta]["son_gorulme"] is not None
    assert c.get("/api/admin/metrikler").json()["modeller"][0]["adet"] == 1
    assert c.post(f"/api/admin/isler/{bek}/iptal").status_code == 200
    assert c.post(f"/api/admin/kullanicilar/{b.id}/tavan", json={"tavan": 42}).status_code == 200
    assert c.post(f"/api/admin/kullanicilar/{b.id}/oturum-dusur").json()["dusurulen"] == 1
    with depo_db.connect() as s:
        assert s.execute(text("SELECT durum FROM isler WHERE id = :id"), {"id": bek}).scalar_one() == "iptal"
        assert s.execute(text("SELECT gunluk_kredi_tavani FROM kullanicilar WHERE id = :id"),
                         {"id": b.id}).scalar_one() == 42
        assert s.execute(text("SELECT count(*) FROM oturumlar WHERE kullanici_id = :id"),
                         {"id": b.id}).scalar_one() == 0
    # Aynı rolle admin OLMAYAN kullanıcı: 403, hiçbir şey değişmez.
    admin.is_admin = False
    assert c.get("/api/admin/isler").status_code == 403
    assert c.get("/api/isler").json()["isler"] and all(
        i["id"] != str(bek) for i in c.get("/api/isler").json()["isler"]), "kullanıcı rotası yalnız kendi işi"


def test_the_lifespan_wires_a_stdout_handler_so_admin_event_lines_actually_reach_the_process_output(
        depo_db, tmp_path, dizinler, admin, monkeypatch):
    """ÖLÇÜLEN KUSUR (duman, 2026-09-18): uvicorn kökü kurmaz, INFO satırı son çare işleyicide düşer —
    `olay=admin.*` hiçbir yere yazılmıyordu. `gunluk.kur` (app.py lifespan) bunu kapatır; iki kez kurulmaz."""
    import io

    from services import gunluk
    kok = logging.getLogger(gunluk.KOK)
    eski = list(kok.handlers)
    for h in eski:
        kok.removeHandler(h)
    akim = io.StringIO()
    try:
        assert gunluk.kur(akim) is kok and len(kok.handlers) == 1
        assert gunluk.kur(akim) is kok and len(kok.handlers) == 1, "ikinci lifespan ikinci işleyici eklemez"
        assert kok.propagate is False and kok.level == logging.INFO
        dizinler(data_dir=str(tmp_path))
        with TestClient(appmod.app):   # lifespan `kur()` çağırır — işleyici sayısı yine 1
            pass
        assert len(kok.handlers) == 1
        b = _ikinci(depo_db)
        assert TestClient(appmod.app).post(f"/api/admin/kullanicilar/{b.id}/tavan", json={"tavan": 7}).status_code == 200
        # Faz 2 / 9: satır JSON, alanlar yapısal, `istek_id` bağlamdan; erişim satırı da aynı akımda.
        satirlar = [json.loads(s) for s in akim.getvalue().splitlines()]
        (olay,) = [s for s in satirlar if s["logger"] == "kromis.admin"]
        assert (olay["seviye"], olay["olay"], olay["admin"], olay["hedef"], olay["tavan"]) == (
            "INFO", "admin.tavan", str(admin.id), str(b.id), 7), olay
        (erisim,) = [s for s in satirlar if s["logger"] == "kromis.istek"]
        assert erisim["istek_id"] == olay["istek_id"] and erisim["durum"] == 200
    finally:
        for h in list(kok.handlers):
            kok.removeHandler(h)
        for h in eski:
            kok.addHandler(h)


def test_the_repository_guard_exempts_depo_admin_by_module_with_a_reason():
    """CLAUDE.md §5: `depo_admin` kullanıcı süzgeci taşımaz ve bunu bekçinin defteri GEREKÇESİYLE söyler."""
    from tests import test_galeri_db as bekci
    assert "services/depo_admin.py" in bekci.KIRACISIZ_MODULLER
    assert "services/depo_admin.py" in bekci.DEPOLAR
    assert "admin_kullanici" in bekci.KIRACISIZ_MODULLER["services/depo_admin.py"], "gerekçe kapıyı adıyla anar"
