"""Hukuki metinler ve rıza (Faz 4 / 6; docs/faz4-odeme-abonelik-kvkk.md §6, K11).

Sorular, belgenin listesi: dört slug × iki dil 200 + `Content-Language`;
bilinmeyen slug 404; metin çapaları ("filigran", "ticari", "Polar", "30 gün",
"silme" ve İngilizce karşılıkları); TASLAK damgası `HUKUK_ONAYLI`ya bağlı;
onaysız kayıt 422 (eksik de `false` da); onaylı kayıt damga + sürüm; sürüm
değişince `GET /api/hesap/ben` `sartlar_guncel: false`; `POST /api/hesap/
sartlar-kabul` bugünkü sürümü damgalar; sürüm sabiti TEK yerde (checkout da
onu okur); `bundled/hukuk` imajda; sayfalar metne bağlanıyor; DPA kontrol
listesi belgesi var ve her alıcının satırı var.

Gerçek Postgres (`depo_db`) yalnız kayıt/onay testlerinde; sayfa testleri
`sablon.sayfa`yı lifespan'sız `TestClient` ile ölçer (tests/test_hesap.py'nin
`/giris` deseni). Kayıt rotası postacı ister: konsol postacı elle takılır
(tests/test_hesap_silme.py `c` fixture'ının deseni). E2E tests/test_playwright_hesap.py'de.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import app as appmod
import i18n
import paths
from routers import odeme as odeme_rotasi
from services import ayar, hukuk, odeme, posta
from services.tablolar import Kullanici

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPOSTA = "hukuk@example.com"
PAROLA = "cok-gizli-parola"

# Belge §6 "çapa cümleleri": her metinde mutlaka geçmesi gereken sözcükler — metin
# yeniden yazılırsa bile bu kavramlar kaybolmasın (filigran kuralı, ticari kullanım,
# Polar'ın MoR rolü, 30 günlük cevap süresi, silme hakkı).
CAPALAR: dict[str, dict[str, tuple[str, ...]]] = {
    hukuk.SLUG_GIZLILIK: {
        "tr": ("Polar", "30 gün", "silme", "Sentry", "kart", "KVKK", "GDPR", "Cloudflare R2", "Neon", "Fly.io"),
        "en": ("Polar", "30 days", "deletion", "Sentry", "card", "KVKK", "GDPR", "Cloudflare R2", "Neon", "Fly.io"),
    },
    hukuk.SLUG_KULLANIM_SARTLARI: {
        "tr": ("Polar", "filigran", "ticari", "14 gün", "18 yaş", "deepfake", "devretmez", "devreder", "iade edilmez",
               "olduğu gibi"),
        "en": ("Polar", "watermark", "commercial", "14 days", "18 years", "deepfake", "does not roll over",
               "roll over", "not refunded", "as is"),
    },
    hukuk.SLUG_CEREZ: {
        "tr": ("kromis_oturum", "kromis_lang", "Secure", "HttpOnly", "localStorage", "Sentry", "izleme"),
        "en": ("kromis_oturum", "kromis_lang", "Secure", "HttpOnly", "localStorage", "Sentry", "tracking"),
    },
    hukuk.SLUG_TICARI_HAKLAR: {
        "tr": ("filigran", "ticari", "hak iddia etmez", "OpenAI", "Google", "Black Forest Labs", "fal.ai", "kişisel"),
        "en": ("watermark", "commercial", "claims no", "OpenAI", "Google", "Black Forest Labs", "fal.ai", "personal"),
    },
}

# DPA kontrol listesinin (belge §6) satır başlıkları: aydınlatma metnindeki her alıcı bir satır.
ALICILAR = ("Polar", "Azure", "Google", "fal", "Fly.io", "Neon", "Cloudflare R2", "Sentry", "Resend")


@pytest.fixture(autouse=True)
def temiz(depo_db):
    """Kayıt testleri aynı e-postayı kullanır; deneme sayacı ve önceki satır her testte gider."""
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM giris_denemeleri"))
        c.execute(text("DELETE FROM kullanicilar WHERE eposta = :e"), {"e": EPOSTA})
    yield


@pytest.fixture
def c(tmp_path, dizinler, monkeypatch) -> TestClient:
    """Lifespan'sız istemci: gerçek `static_dir` (sayfa), `tmp_path` veri dizini, konsol postacı (kayıt)."""
    dizinler(data_dir=str(tmp_path), static_dir=ayar.Ayarlar.varsayilan().static_dir)
    monkeypatch.setattr(appmod.app.state, "postaci", posta.KonsolPostaci(str(tmp_path)), raising=False)
    return TestClient(appmod.app)


def _satir(depo_db, eposta: str = EPOSTA) -> Kullanici | None:
    with Session(depo_db) as s:
        k = s.scalar(select(Kullanici).where(Kullanici.eposta == eposta))
        if k is not None:
            s.expunge(k)
        return k


def _kayit(c: TestClient, **govde):
    return c.post("/api/hesap/kayit", json={"eposta": EPOSTA, "parola": PAROLA, **govde},
                  headers={"X-Kromis-Lang": "tr"})


# ── Sayfa: dört slug × iki dil ────────────────────────────────────────

@pytest.mark.parametrize("lang", i18n.LANGUAGES)
@pytest.mark.parametrize("slug", hukuk.SLUGLAR)
def test_every_text_is_served_in_both_languages_inside_the_shell_with_content_language(slug, lang, c):
    cevap = c.get(f"/hukuk/{slug}", headers={"X-Kromis-Lang": lang})
    assert cevap.status_code == 200
    assert cevap.headers["content-language"] == lang
    assert cevap.headers["cache-control"] == "no-store"
    html = cevap.text
    assert f'<html lang="{lang}">' in html
    assert "{{t:" not in html and "__APP_" not in html and "__HUKUK_" not in html, "yer tutucu kaldı"
    assert "<h1>" in html and "<h2>" in html, "parça kabuğa yerleşmedi"
    assert i18n.t("hukuk.title", lang) in html
    # Sürüm satırı ve TASLAK damgası (öntanımlı `HUKUK_ONAYLI = False`): ikisi de görünür.
    assert f'<code id="hukuk-surum">{hukuk.HUKUK_SURUMU}</code>' in html
    assert re.search(r'<p id="hukuk-taslak" class="hukuk-taslak" role="note" >', html), "damga gizli çıktı"
    assert i18n.t("hukuk.taslak", lang) in html
    # Gezinme: dört bağlantı, yalnız bu sayfanınki `aria-current` — YALNIZ `<nav>` içinde bakılır,
    # metnin kendi iç bağlantıları (gizlilik → çerez gibi) gezinme değil.
    gezinme = re.search(r'<nav id="hukuk-gezinme".*?</nav>', html, re.S).group(0)
    baglar = re.findall(r'<a href="/hukuk/([a-z-]+)"( aria-current="page")?>', gezinme)
    assert [b[0] for b in baglar] == list(hukuk.SLUGLAR)
    assert [b[0] for b in baglar if b[1]] == [slug]
    # Betik yok: düz belge (hukuk.html'in gerekçesi).
    assert "<script" not in html


def test_an_unknown_slug_is_404_and_the_path_cannot_escape_the_whitelist(c):
    # `..` DEĞİL `%2e%2e`: düz `..`yi istemci daha yola çıkmadan `/`ye çözer (RFC 3986 nokta bölütü),
    # sunucuya hiç varmaz; kodlanmışı slug dizesi olarak gelir ve beyaz listeye çarpar.
    for kotu in ("yok", "gizlilik.tr", "%2e%2e", "kullanim-sartlari.en.html", "GIZLILIK"):
        cevap = c.get(f"/hukuk/{kotu}", headers={"X-Kromis-Lang": "tr"})
        assert cevap.status_code == 404, kotu
        assert cevap.json()["detail"] == i18n.t("err.hukuk_metni_yok", "tr"), kotu
    # Kodlanmış bölü: yol `/hukuk/gizlilik/../cerez`e çözülür, `{slug}` tek bölüt — rotaya hiç varmaz,
    # FastAPI'nin kendi 404'ü. Yine 404; beyaz liste sorgulanmadı bile.
    assert c.get("/hukuk/gizlilik%2F..%2Fcerez").status_code == 404


@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_every_text_carries_its_anchor_sentences(lang, c):
    """Belge §6: çapa cümleleri — metin yeniden yazılsa da bu kavramlar kalır."""
    for slug, capalar in CAPALAR.items():
        html = c.get(f"/hukuk/{slug}", headers={"X-Kromis-Lang": lang}).text
        # Büyük/küçük harf duyarsız: cümle başındaki "Deepfake" çapayı düşürmesin, kavram aranıyor.
        eksik = [capa for capa in capalar[lang] if capa.lower() not in html.lower()]
        assert not eksik, f"{slug}.{lang}: çapa yok: {eksik}"


def test_the_draft_stamp_disappears_only_when_the_texts_are_approved(c, monkeypatch):
    """`HUKUK_ONAYLI = True` PR'ı (sahibin adımı) yalnız bayrağı çevirir; damga şablonda `hidden` olur, metin aynı kalır."""
    once = c.get("/hukuk/gizlilik", headers={"X-Kromis-Lang": "tr"}).text
    monkeypatch.setattr(hukuk, "HUKUK_ONAYLI", True)
    sonra = c.get("/hukuk/gizlilik", headers={"X-Kromis-Lang": "tr"}).text
    assert '<p id="hukuk-taslak" class="hukuk-taslak" role="note" hidden>' in sonra
    assert i18n.t("hukuk.taslak", "tr") in sonra, "damga metni şablonda durur, yalnız gizlenir"
    # Damga satırı dışında sayfa aynı.
    assert once.replace('role="note" >', 'role="note" hidden>') == sonra


def test_the_language_chain_applies_to_an_anonymous_visitor(c):
    """Oturumsuz: başlık → çerez → Accept-Language → öntanımlı (services/dil.py). Sayfa kapısız, zincir yine tam."""
    assert c.get("/hukuk/cerez", headers={"Accept-Language": "tr-TR,tr;q=0.9"}).headers["content-language"] == "tr"
    assert c.get("/hukuk/cerez", headers={"Accept-Language": "de"}).headers["content-language"] == i18n.DEFAULT
    c.cookies.set("kromis_lang", "tr")
    assert c.get("/hukuk/cerez", headers={"Accept-Language": "en"}).headers["content-language"] == "tr"
    assert c.get("/hukuk/cerez", headers={"X-Kromis-Lang": "en"}).headers["content-language"] == "en"


def test_the_fragments_are_fragments_and_the_two_languages_have_the_same_shape():
    """Parça: kabuk yok (`<html>`/`<body>`/`<script>`), telif başlığı var, `<h1>` ile açılır; tr/en aynı bölüm sayısı."""
    for slug in hukuk.SLUGLAR:
        bolumler = {}
        for lang in i18n.LANGUAGES:
            with open(hukuk.dosya_yolu(slug, lang), encoding="utf-8") as f:
                metin = f.read()
            assert "<html" not in metin and "<body" not in metin and "<script" not in metin, f"{slug}.{lang}"
            assert "Copyright (C) 2026 Alperen Zengin" in metin[:400], f"{slug}.{lang}: telif başlığı"
            assert re.match(r"<!--.*?-->\s*<h1>", metin, re.S), f"{slug}.{lang}: `<h1>` ile açılmıyor"
            assert "\r" not in metin, f"{slug}.{lang}: CRLF"
            bolumler[lang] = metin.count("<h2>")
        assert len(set(bolumler.values())) == 1, f"{slug}: tr/en bölüm sayısı farklı: {bolumler}"
        assert bolumler["tr"] >= 5, slug


def test_the_version_constant_is_a_year_month_and_lives_in_exactly_one_module():
    """Belge §6: `HUKUK_SURUMU` tek sabit — kok, hesap, odeme onu okur; `odeme.SARTLAR_SURUMU` yer tutucusu gitti."""
    assert re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", hukuk.HUKUK_SURUMU)
    assert hukuk.HUKUK_ONAYLI is False, "avukat onayı sahibin PR'ıyla gelir"
    assert not hasattr(odeme, "SARTLAR_SURUMU")
    tanimlayan = subprocess.run(["git", "-C", REPO, "grep", "-l", r"^HUKUK_SURUMU = ", "--", "*.py"],
                                check=True, capture_output=True, text=True).stdout.split()
    assert tanimlayan == ["services/hukuk.py"]
    for yol in ("routers/odeme.py", "routers/hesap.py", "routers/kok.py"):
        with open(os.path.join(REPO, yol), encoding="utf-8") as f:
            assert "hukuk.HUKUK_SURUMU" in f.read() or yol == "routers/kok.py", yol
    with open(os.path.join(REPO, "routers", "kok.py"), encoding="utf-8") as f:
        assert "hukuk.HUKUK_SURUMU" in f.read()


def test_yer_tutucu_and_missing_acceptances_are_not_current():
    assert hukuk.guncel_mi(hukuk.HUKUK_SURUMU) is True
    assert hukuk.guncel_mi(None) is False
    assert hukuk.guncel_mi("0000-yer-tutucu") is False, "4. görevin metinsiz onayı yeniden onay ister (belge §4 b)"
    assert hukuk.guncel_mi("2000-01") is False


# ── Kayıtta tıkla-onay (K11) ───────────────────────────────────────────

def test_registration_without_consent_is_422_in_the_interface_language_and_creates_no_user(c, depo_db):
    eksik = _kayit(c)
    assert eksik.status_code == 422
    assert i18n.t("err.sartlar_gerekli", "tr") in eksik.text, "pydantic'in İngilizce 'Field required'ı değil"
    yanlis = _kayit(c, sartlar=False)
    assert yanlis.status_code == 422 and i18n.t("err.sartlar_gerekli", "tr") in yanlis.text
    assert _satir(depo_db) is None
    assert appmod.app.state.postaci.son is None, "onaysız kayıt posta göndermez"


def test_registration_with_consent_stamps_the_time_and_the_current_version(c, depo_db):
    assert _kayit(c, sartlar=True).json() == {"ok": True}
    k = _satir(depo_db)
    assert k is not None and k.sartlar_surumu == hukuk.HUKUK_SURUMU
    assert k.sartlar_kabul_at is not None
    assert abs((k.sartlar_kabul_at - dt.datetime.now(tz=dt.UTC)).total_seconds()) < 60
    # Doğrulanmamış hesaba yeniden kayıt: parola gibi onay da yenilenir (bu isteğin onayı).
    with depo_db.begin() as b:
        b.execute(text("UPDATE kullanicilar SET sartlar_surumu = 'eski', sartlar_kabul_at = NULL WHERE eposta = :e"),
                  {"e": EPOSTA})
    assert _kayit(c, sartlar=True, parola="baska-parola-123").json() == {"ok": True}
    k2 = _satir(depo_db)
    assert k2 is not None and k2.sartlar_surumu == hukuk.HUKUK_SURUMU and k2.sartlar_kabul_at is not None


def test_me_reports_whether_the_accepted_version_is_current(c, depo_db, kullanici, monkeypatch):
    """`GET /api/hesap/ben` `sartlar_guncel`: sürüm eşleşiyorsa `true`; eski, yer tutucu ya da hiç yoksa `false`."""
    def _yaz(surum):
        with depo_db.begin() as b:
            b.execute(text("UPDATE kullanicilar SET sartlar_surumu = :s WHERE id = :id"), {"s": surum, "id": kullanici.id})
        kullanici.sartlar_surumu = surum   # kapı fixture'ın nesnesini veriyor (conftest), satırı değil

    for surum, beklenen in ((hukuk.HUKUK_SURUMU, True), ("eski", False), ("0000-yer-tutucu", False), (None, False)):
        _yaz(surum)
        govde = c.get("/api/hesap/ben").json()
        assert govde["sartlar_guncel"] is beklenen, (surum, govde)
    # Sürüm sabiti ilerledi (metin değişti): bugünkü onay bir anda eskir — banner'ın tetiği bu.
    _yaz(hukuk.HUKUK_SURUMU)
    monkeypatch.setattr(hukuk, "HUKUK_SURUMU", "2099-01")
    assert c.get("/api/hesap/ben").json()["sartlar_guncel"] is False


def test_accepting_the_terms_stamps_the_current_version_and_the_banner_trigger_clears(c, depo_db, kullanici):
    with depo_db.begin() as b:
        b.execute(text("UPDATE kullanicilar SET sartlar_surumu = 'eski', sartlar_kabul_at = NULL WHERE id = :id"),
                  {"id": kullanici.id})
    cevap = c.post("/api/hesap/sartlar-kabul")
    assert cevap.status_code == 200 and cevap.json() == {"ok": True, "surum": hukuk.HUKUK_SURUMU}
    with Session(depo_db) as s:
        k = s.get(Kullanici, kullanici.id)
        assert k is not None and k.sartlar_surumu == hukuk.HUKUK_SURUMU and k.sartlar_kabul_at is not None
        kullanici.sartlar_surumu = k.sartlar_surumu
    assert c.get("/api/hesap/ben").json()["sartlar_guncel"] is True
    # Gövde yok sayılır: sürümü sunucu yazar, istemci eski bir sürüme onay iddia edemez.
    assert c.post("/api/hesap/sartlar-kabul", json={"surum": "2000-01"}).status_code == 200
    with Session(depo_db) as s:
        assert s.scalar(select(Kullanici.sartlar_surumu).where(Kullanici.id == kullanici.id)) == hukuk.HUKUK_SURUMU


def test_the_checkout_gate_reports_the_same_version_constant():
    """4. görevin 412'si `{"kod", "surum"}` — sürüm artık `hukuk.HUKUK_SURUMU` (tests/test_odeme_route.py uçtan uca ölçer)."""
    assert odeme_rotasi.KOD_SARTLAR_GEREKLI == "err.sartlar_gerekli"
    import inspect
    assert "surum=hukuk.HUKUK_SURUMU" in inspect.getsource(odeme_rotasi.checkout)
    assert inspect.signature(odeme.sartlar_kabul_yaz).parameters["surum"].default == hukuk.HUKUK_SURUMU


# ── Paket, sayfalar, belge ─────────────────────────────────────────────

def test_the_texts_ship_in_the_docker_image_and_are_tracked():
    """`COPY . /app` + `.dockerignore`: `bundled/` içeride, `*.html` gibi bir kalıp yok; sekiz dosya git'te."""
    with open(os.path.join(REPO, ".dockerignore"), encoding="utf-8") as f:
        dislanan = {s.strip().rstrip("/") for s in f.read().splitlines() if s.strip() and not s.startswith("#")}
    assert not dislanan & {"bundled", "bundled/hukuk", "bundled/*", "*.html", "**/*.html"}
    assert paths.bundled_hukuk_dir() == os.path.join(paths.resource_dir(), "bundled", "hukuk")
    izlenen = set(subprocess.run(["git", "-C", REPO, "ls-files", "bundled/hukuk"],
                                 check=True, capture_output=True, text=True).stdout.split())
    beklenen = {f"bundled/hukuk/{slug}.{lang}.html" for slug in hukuk.SLUGLAR for lang in i18n.LANGUAGES}
    assert izlenen == beklenen, f"eksik: {beklenen - izlenen}, fazla: {izlenen - beklenen}"
    for yol in beklenen:
        assert os.path.isfile(os.path.join(REPO, yol))


def test_the_pages_link_to_the_texts_and_the_registration_form_carries_the_consent_box():
    """Belge §6 "Footer bağlantıları `/giris`, `/planlar`, ayarlar Hakkında; `/planlar` ticari haklar cümlesi metne bağlanır"."""
    def _oku(*parcalar):
        with open(os.path.join(REPO, *parcalar), encoding="utf-8") as f:
            return f.read()
    dort = {f'href="/hukuk/{slug}"' for slug in hukuk.SLUGLAR}
    giris = _oku("static", "giris.html")
    assert dort <= set(re.findall(r'href="/hukuk/[a-z-]+"', giris))
    assert 'id="kayit-sartlar"' in giris and 'name="sartlar" type="checkbox"' in giris
    assert "required" not in re.search(r'<input id="kayit-sartlar"[^>]*>', giris).group(0), "kararı sunucu verir (giris.html)"
    assert 'sartlar: el("kayit-sartlar").checked' in _oku("static", "giris.js")
    planlar = _oku("static", "planlar.html")
    assert dort <= set(re.findall(r'href="/hukuk/[a-z-]+"', planlar))
    assert '"/hukuk/ticari-haklar"' in _oku("static", "planlar.js")
    index = _oku("static", "index.html")
    hakkinda = index[index.index('data-pane="about"', index.index('<div class="settings-panes">')):]
    assert dort <= set(re.findall(r'href="/hukuk/[a-z-]+"', hakkinda))
    assert 'id="settings-sartlar-banner"' in index
    settings = _oku("static", "settings.js")
    assert '"/api/hesap/sartlar-kabul"' in settings and "sartlar_guncel !== false" in settings
    # Kabuk `static/` altında, parçalar `bundled/` altında (hukuk.py'nin gerekçesi).
    assert "__HUKUK_GOVDE__" in _oku("static", "hukuk.html")


def test_the_dpa_checklist_document_exists_with_a_row_per_recipient():
    """Belge §6: sahibin doldurduğu tablo — test yalnız dosyanın ve satır başlıklarının varlığını ölçer."""
    yol = os.path.join(REPO, "docs", "hukuk-kontrol-listesi.md")
    assert os.path.isfile(yol)
    with open(yol, encoding="utf-8") as f:
        belge = f.read()
    for sutun in ("alıcı", "DPA", "DPF", "veri konumu", "kabul tarihi"):
        assert sutun in belge, sutun
    satirlar = [s for s in belge.splitlines() if s.startswith("| ")]
    for alici in ALICILAR:
        assert any(alici in s for s in satirlar), f"{alici} satırı yok"
    assert "HUKUK_ONAYLI" in belge and "KVKK md. 9" in belge
