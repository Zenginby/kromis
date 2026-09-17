"""Kimlik kapısı ve kullanıcıya göre ayar nesnesi — Faz 1 / 4'ün bekçisi.

docs/faz1-veritabani-hesaplar.md → 4: oturumsuz 47 rota 401 (API) ya da 302
(`GET /`), açık rotalar ELLE tutulan bir listede GEREKÇESİYLE; iki kullanıcı
aynı süreçte birbirinin dizinini/medyasını görmüyor; `ayarlar()` aynı istekte
tek sorgu; dil DB'den (`kullanicilar.dil`), `prefs.json` okunmuyor.

GERÇEK Postgres (`veritabani`), lifespan'lı `TestClient`, GERÇEK çerez:
conftest'in autouse `kullanici` override'ı bu dosyada `gercek_kimlik` ile
kapalı — kapının kendisini sahte kullanıcıyla ölçmek mümkün değil. `base_url`
HTTPS: web modunda (DATABASE_URL var) oturum çerezi `Secure` ve httpx `Secure`
çerezi düz HTTP'ye geri göndermez (tests/test_hesap.py'nin gerekçesi).

AÇIK LİSTE BURADA, ÜRÜN KODUNDA DEĞİL: `services/kimlik.py` "kapı var/yok"
kararını rota İMZASINA bırakıyor (Faz 0 / 4 ilkesi); imzada ne olduğunu
sayan ve "ne olmalıydı"yı bilen taraf test. Liste `tests/test_i18n.py`nin
`KULLANICIYA_KONUSMAYAN` defteriyle aynı deyim: listede olmayan yeni bir rota
"kapılı" DEĞİL "sınıflandırılmamış"tır ve takım kırmızıdır (CLAUDE.md §5).
"""
from __future__ import annotations

import os
import re
import stat
import uuid

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

import app as appmod
import i18n
import prefs
from services import ayar, cerez, depo_medya, hesap, kimlik
from services.tablolar import Kullanici

pytestmark = pytest.mark.gercek_kimlik

HTTPS = "https://testserver"

# Oturum İSTEMEYEN rotalar — her biri gerekçesiyle. Kapı bağımlılığı taşımayan
# bir rota bu listede değilse test kırmızı; listede olup kapı taşıyan da.
ACIK_ROTALAR: dict[tuple[str, str], str] = {
    ("GET", "/health"): "sağlık sondası: HEALTHCHECK/orkestratör çerez taşımaz, cevap makine okur",
    ("GET", "/giris"): "giriş sayfasının kendisi — oturumsuz ziyaretçinin gideceği yer",
    ("POST", "/api/hesap/kayit"): "hesap açma: henüz kullanıcı yok",
    ("POST", "/api/hesap/dogrula"): "e-posta bağlantısından: kimlik kanıtı jeton, çerez değil",
    ("POST", "/api/hesap/giris"): "oturumu AÇAN rota",
    ("POST", "/api/hesap/sifirla"): "parolamı unuttum: giremeyen kullanıcının yolu",
    ("POST", "/api/hesap/sifirla/dogrula"): "sıfırlama bağlantısından: kimlik kanıtı jeton",
}

# Oturumsuz cevabı 302 olan (tarayıcı gezinmesi) rotalar; geri kalan kapılılar 401 JSON.
SAYFALAR = {("GET", "/")}

# Kapılı ama DİZİN OKUMAYAN rotalar — kapıyı `ayar.ayarlar` üzerinden değil doğrudan
# alırlar. Belgenin dört istisnası (§4) + Faz 1 / 5'te DB'ye taşınan ve dosyaya
# dokunmayan galeri/klasör rotaları + Faz 1 / 6'da taşınan sohbet, palet, tercih
# ve varlık LİSTESİ rotaları (satır okur/yazar, `output_dir`/`assets_dir` istemez).
# Dosyaya dokunanlar (`/output/*`, `/assets/*`, indirme, silme, üretim, içe
# aktarma, varlık yükleme/silme, bindirme) ve `guncelleme.json` okuyan üç
# güncelleme rotası listede DEĞİL: onlar ayar nesnesini almaya devam ediyor.
DIZINSIZ_KAPILI = {
    ("POST", "/api/settings"), ("POST", "/api/palette/suggest"),
    ("GET", "/api/hesap/ben"), ("POST", "/api/hesap/cikis"),
    ("GET", "/api/folders"), ("POST", "/api/folders"), ("PATCH", "/api/folders/{folder_id}"),
    ("DELETE", "/api/folders/{folder_id}"),   # görseller köke döner, dosya taşınmaz/silinmez
    ("GET", "/api/history"), ("PATCH", "/api/image/{image_id}"), ("PATCH", "/api/images"),
    ("GET", "/api/arena/{arena_id}"), ("POST", "/api/arena/{arena_id}/winner"),
    # Faz 1 / 6
    ("POST", "/api/chat"),                    # tur bağlamı `tercihler`den
    ("GET", "/api/chats"), ("POST", "/api/chats"), ("DELETE", "/api/chats"),
    ("GET", "/api/chats/{chat_id}"), ("PUT", "/api/chats/{chat_id}"),
    ("DELETE", "/api/chats/{chat_id}"),
    ("GET", "/api/palettes"), ("POST", "/api/palettes"), ("DELETE", "/api/palettes/{palette_id}"),
    ("GET", "/api/prefs"), ("POST", "/api/prefs"),
    ("GET", "/api/assets/{kind}"),            # yalnız satır; dosya yolları ayar ister
}

KAPI = {kimlik.aktif_kullanici, kimlik.sayfa_kullanicisi}

# Yol parametrelerinin doldurulacağı geçerli biçimli değerler: kapı gövdeden
# ve doğrulamadan ÖNCE koşuyor, ama yol eşleşmesi için biçim doğru olmalı.
YOL_DEGERLERI = {"image_id": "abcdef123456", "folder_id": "abcdef123456",
                 "chat_id": "abcdef123456", "palette_id": "abcdef123456",
                 "asset_id": "abcdef123456", "arena_id": "abcdef123456",
                 "kind": "logos", "filename": "abcdef123456.png"}


def _png() -> bytes:
    """Yükleme rotası gerçek bir PNG istiyor (`gorsel.to_png` yeniden kodluyor)."""
    import io

    from PIL import Image
    tampon = io.BytesIO()
    Image.new("RGBA", (8, 8), (200, 30, 30, 255)).save(tampon, "PNG")
    return tampon.getvalue()


def _rotalar() -> list[tuple[str, str, APIRoute]]:
    """(YÖNTEM, yol, rota) — conftest.duz_rotalar'ın rota nesnesini de veren ikizi."""
    bulunan: list[tuple[str, str, APIRoute]] = []

    def _yuru(rotalar, on_ek: str) -> None:
        for r in rotalar:
            ic = getattr(r, "original_router", None)
            if ic is not None:
                baglam = getattr(r, "include_context", None)
                _yuru(ic.routes, on_ek + (getattr(baglam, "prefix", "") or ""))
                continue
            for yontem in getattr(r, "methods", None) or ():
                if not r.path.startswith(("/docs", "/redoc", "/openapi")):
                    bulunan.append((yontem, on_ek + r.path, r))

    _yuru(appmod.app.routes, "")
    return bulunan


def _kapilar(dependant) -> set:
    """Rotanın bağımlılık ağacındaki kapı işlevleri (alt bağımlılıklar dâhil — `ayar.ayarlar` üstünden)."""
    bulunan = set()
    for alt in dependant.dependencies:
        if alt.call in KAPI:
            bulunan.add(alt.call)
        bulunan |= _kapilar(alt)
    return bulunan


KAPILI = {(y, p) for y, p, r in _rotalar() if _kapilar(r.dependant)}
ACIK = {(y, p) for y, p, r in _rotalar() if not _kapilar(r.dependant)}


# ── Bekçi: her rota ya kapılı ya gerekçeli açık ─────────────────────

def test_every_route_is_either_gated_or_openly_listed_with_a_reason():
    """Belge §4: 54 − 7 açık = 47 kapılı (44 stüdyo + `/` + `ben` + `cikis`)."""
    assert ACIK == set(ACIK_ROTALAR), (
        f"kapısız ama listede olmayan: {sorted(ACIK - set(ACIK_ROTALAR))}; "
        f"listede ama kapılı: {sorted(set(ACIK_ROTALAR) - ACIK)}")
    assert all(gerekce.strip() for gerekce in ACIK_ROTALAR.values())
    assert len(KAPILI) == 47 and len(ACIK) == 7 and len(KAPILI | ACIK) == 54, (
        "rota sayısı ya da kapı sayısı değişti — bilinçliyse belgeyi ve bu sayıları güncelle")


def test_only_the_studio_page_uses_the_redirecting_gate():
    """302 veren kapı yalnız tarayıcı gezinmesinde; API rotaları 401 JSON verir (fetch yönlendirme takip eder)."""
    sayfalar = {(y, p) for y, p, r in _rotalar()
                if kimlik.sayfa_kullanicisi in _kapilar(r.dependant)}
    assert sayfalar == SAYFALAR
    for y, p, r in _rotalar():
        assert _kapilar(r.dependant) != KAPI, f"{y} {p}: iki kapı birden"


def test_a_directory_reading_route_takes_the_user_scoped_settings_never_the_shared_ones():
    """`ayar.genel` yalnız açık rotalarda ve `GET /`de (static_dir): kullanıcı verisi okuyan rota
    paylaşılan yerleşimi alırsa iki kullanıcı aynı dizine yazar."""
    def _cagrilar(dependant) -> set:
        s = {alt.call for alt in dependant.dependencies}
        for alt in dependant.dependencies:
            s |= _cagrilar(alt)
        return s

    for y, p, r in _rotalar():
        cagrilar = _cagrilar(r.dependant)
        if ayar.genel in cagrilar:
            assert (y, p) in ACIK or (y, p) in SAYFALAR, f"{y} {p}: kapılı rota paylaşılan ayarı alıyor"
        if (y, p) in KAPILI and (y, p) not in SAYFALAR and ayar.ayarlar not in cagrilar:
            assert (y, p) in DIZINSIZ_KAPILI, (
                f"{y} {p}: dizin okumayan kapılı rota — `DIZINSIZ_KAPILI` listesinde değil")
        if (y, p) in DIZINSIZ_KAPILI:
            assert ayar.ayarlar not in cagrilar, f"{y} {p}: dizin okumuyor deniyor ama ayar nesnesi alıyor"


# ── Kapının davranışı ────────────────────────────────────────────────

@pytest.fixture
def istemci(veritabani, tmp_path, dizinler, monkeypatch):
    """Lifespan'lı istemci (motor kurulur), veri kökü `tmp_path` — kullanıcı dizinleri oraya."""
    monkeypatch.delenv(cerez.GUVENLI_ENV, raising=False)
    dizinler(data_dir=str(tmp_path))
    with TestClient(appmod.app, base_url=HTTPS) as c:
        yield c


def _kullanici_ac(dil: str | None = None) -> tuple[uuid.UUID, str, str]:
    """DB'de doğrulanmış kullanıcı + oturum; `(id, ham jeton, eposta)`."""
    eposta = f"{uuid.uuid4().hex[:8]}@example.com"
    an = hesap.simdi()
    with Session(appmod.app.state.motor) as db:
        k = Kullanici(eposta=eposta, parola_ozeti=None, dogrulandi_at=an, dil=dil)
        db.add(k)
        db.flush()
        jeton = hesap.oturum_ac(db, k, None, "test", an)
        kid = k.id
        db.commit()
    return kid, jeton, eposta


def _oturumlu(jeton: str) -> TestClient:
    """Bu oturumun çerezini taşıyan tarayıcı; motor `istemci`nin lifespan'ından (app.state ortak)."""
    return TestClient(appmod.app, base_url=HTTPS, cookies={cerez.OTURUM_CEREZI: jeton})


def _yol(p: str) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: YOL_DEGERLERI[m.group(1)], p)


@pytest.mark.parametrize("yontem, yol", sorted(KAPILI - SAYFALAR))
def test_every_gated_api_route_answers_401_json_without_a_session(istemci, yontem, yol):
    """Çerezsiz istek: gövde/doğrulama koşmadan 401 ve i18n'li `detail` (isteğin dilinde)."""
    cevap = istemci.request(yontem, _yol(yol))
    assert cevap.status_code == 401, (yontem, yol, cevap.text)
    assert cevap.json() == {"detail": i18n.t("err.hesap_giris_gerekli", "en")}
    cevap_tr = istemci.request(yontem, _yol(yol), headers={"X-Kromis-Lang": "tr"})
    assert cevap_tr.json() == {"detail": i18n.t("err.hesap_giris_gerekli", "tr")}


def test_a_bogus_cookie_is_401_and_the_open_routes_stay_open(istemci):
    sahte = TestClient(appmod.app, base_url=HTTPS, cookies={cerez.OTURUM_CEREZI: "x" * 43})
    assert sahte.get("/api/history").status_code == 401
    assert sahte.get("/", follow_redirects=False).status_code == 302
    assert istemci.get("/giris").status_code == 200
    assert istemci.get("/health").status_code == 200
    assert istemci.post("/api/hesap/giris", json={"eposta": "a@b.co", "parola": "x" * 8}).status_code == 401, (
        "giriş rotası açık: 401'i kapı değil yanlış parola verdi")


def test_the_studio_page_redirects_an_anonymous_browser_to_the_login_page(istemci):
    """Tarayıcı gezinmesi: 302 `/giris` (JSON değil), vekil saklamasın; oturumla 200 HTML."""
    cevap = istemci.get("/", follow_redirects=False)
    assert cevap.status_code == 302
    assert cevap.headers["location"] == kimlik.GIRIS_SAYFASI == "/giris"
    assert cevap.headers["cache-control"] == "no-store"
    assert not cevap.content, "yönlendirme gövde taşımıyor"
    # …ve yönlendirme takip edilince giriş sayfası geliyor.
    assert "id=\"form-giris\"" in istemci.get("/").text
    _, jeton, _ = _kullanici_ac()
    sayfa = _oturumlu(jeton).get("/", follow_redirects=False)
    assert sayfa.status_code == 200 and 'id="view-studio"' in sayfa.text


def test_the_login_page_is_served_to_a_logged_in_user_too(istemci):
    """`/giris` açık kalır: sayfa oturumu görüp stüdyoya kendisi döner (static/giris.js)."""
    _, jeton, _ = _kullanici_ac()
    assert _oturumlu(jeton).get("/giris").status_code == 200


# ── Çıkış ölçütü: iki kullanıcı, aynı süreç ──────────────────────────

def test_two_users_have_separate_directories_and_never_see_each_others_media(istemci, tmp_path):
    a_id, a_jeton, _ = _kullanici_ac()
    b_id, b_jeton, _ = _kullanici_ac()
    a, b = _oturumlu(a_jeton), _oturumlu(b_jeton)
    assert a.get("/api/history").json()["images"] == []
    assert b.get("/api/history").json()["images"] == []
    # Dizin, dizin OKUYAN ilk istekte açılır (`ayar.ayarlar`); `/api/history` artık DB'den (Faz 1 / 5).
    assert a.get("/output/yok.png").status_code == b.get("/output/yok.png").status_code == 404

    # Dizin yerleşimi: <data_dir>/kullanicilar/<uuid>/{output,assets}; kök 0o700.
    a_ayar = appmod.app.state.ayarlar.kullanici_icin(a_id)
    b_ayar = appmod.app.state.ayarlar.kullanici_icin(b_id)
    assert a_ayar.output_dir == str(tmp_path / "kullanicilar" / str(a_id) / "output")
    assert a_ayar.assets_dir == str(tmp_path / "kullanicilar" / str(a_id) / "assets")
    assert a_ayar.data_dir == b_ayar.data_dir == str(tmp_path)
    assert a_ayar.static_dir == b_ayar.static_dir == appmod.app.state.ayarlar.static_dir
    assert a_ayar.output_dir != b_ayar.output_dir
    for ozel in (a_ayar, b_ayar):
        assert os.path.isdir(ozel.output_dir) and os.path.isdir(ozel.assets_dir), "ilk istekte açıldı"
    kok = tmp_path / "kullanicilar" / str(a_id)
    assert stat.S_IMODE(kok.stat().st_mode) == 0o700

    # A'nın görseli (satır + dosya, Faz 1 / 5): A görür, B ne listede ne dosyada ne indirmede görür.
    with Session(appmod.app.state.motor) as db:
        kayit = depo_medya.kaydet(db, a_id, b"\x89PNG",
                                  {"prompt": "A'nin gorseli", "size": "1024x1024",
                                   "quality": "low", "parent_id": None, "folder_id": None,
                                   "palette": None, "prompt_sent": None, "model": ""},
                                  a_ayar.output_dir)
        db.commit()
    assert [g["prompt"] for g in a.get("/api/history").json()["images"]] == ["A'nin gorseli"]
    assert b.get("/api/history").json()["images"] == []
    assert a.get(f"/output/{kayit['filename']}").status_code == 200
    assert b.get(f"/output/{kayit['filename']}").status_code == 404
    assert b.get(f"/api/output/{kayit['id']}/download").status_code == 404
    assert b.delete(f"/api/image/{kayit['id']}").status_code == 404
    assert a.get(f"/output/{kayit['filename']}").status_code == 200, "B'nin denemesi A'nın dosyasına dokunmadı"
    assert not (tmp_path / "output").exists(), "paylaşılan output/ web yolunda hiç açılmadı"

    # Klasörler de (Faz 1 / 5): A'nın klasörü B'ye "yok" — 404, 403 değil (id uzayı sızmaz).
    klasor = a.post("/api/folders", json={"name": "A'nin klasoru"}).json()["folder"]["id"]
    assert a.patch(f"/api/image/{kayit['id']}", json={"folder_id": klasor}).status_code == 200
    assert [f["id"] for f in a.get("/api/folders").json()["items"]] == [klasor]
    assert b.get("/api/folders").json()["items"] == []
    assert b.get(f"/api/history?folder_id={klasor}").status_code == 404
    assert b.patch(f"/api/folders/{klasor}", json={"name": "calinti"}).status_code == 404
    assert b.get(f"/api/folders/{klasor}/download").status_code == 404
    assert b.post("/api/folders", json={"name": "alt", "parent_id": klasor}).status_code == 404
    assert b.patch(f"/api/image/{kayit['id']}", json={"folder_id": None}).status_code == 404
    assert b.request("PATCH", "/api/images", json={"ids": [kayit["id"]], "folder_id": None}).status_code == 404
    assert b.request("DELETE", "/api/images", json={"ids": [kayit["id"]]}).status_code == 404
    assert b.delete(f"/api/folders/{klasor}").status_code == 404
    assert a.get("/api/folders").json()["items"][0]["count"] == 1, "B'nin denemeleri A'nın klasörüne dokunmadı"
    assert a.get(f"/api/history?folder_id={klasor}").json()["images"][0]["id"] == kayit["id"]
    assert not (tmp_path / "kullanicilar" / str(b_id) / "output" / "history.json").exists()
    assert not (tmp_path / "kullanicilar" / str(a_id) / "output" / "folders.json").exists()

    # Sohbet, palet, varlık, tercih de (Faz 1 / 6): A yazar, B ne listede görür ne
    # id'siyle ulaşır (404); tercih kullanıcı başına, B'ninki varsayılanda kalır.
    sohbet = a.post("/api/chats", json={"title": "A sohbeti", "messages": [
        {"role": "user", "content": "kare"}]}).json()["chat"]["id"]
    palet = a.post("/api/palettes", json={"name": "A paleti", "seed": "#c86a3c",
                                          "mode": "triad"}).json()["palette"]["id"]
    varlik = a.post("/api/assets/logos", files={"file": ("l.png", _png(), "image/png")}).json()["asset"]
    assert a.post("/api/prefs", json={"theme": "amber", "autosave_sessions": False}).status_code == 200
    assert [c["title"] for c in a.get("/api/chats").json()["chats"]] == ["A sohbeti"]
    assert b.get("/api/chats").json() == {"chats": []}
    assert b.get(f"/api/chats/{sohbet}").status_code == 404
    assert b.put(f"/api/chats/{sohbet}", json={"title": "calinti"}).status_code == 404
    assert b.delete(f"/api/chats/{sohbet}").status_code == 404
    assert b.get("/api/palettes").json()["items"] == []
    assert b.delete(f"/api/palettes/{palet}").status_code == 404
    assert b.get("/api/assets/all").json()["items"] == []
    assert b.get(f"/assets/logos/{varlik['filename']}").status_code == 404
    assert b.delete(f"/api/assets/logos/{varlik['id']}").status_code == 404
    assert b.post("/api/logo/preview", json={"id": kayit["id"], "asset_id": varlik["id"]}).status_code == 404
    assert b.get("/api/prefs").json()["theme"] == "mono"
    assert a.get("/api/prefs").json()["theme"] == "amber"
    assert a.get(f"/api/chats/{sohbet}").json()["chat"]["title"] == "A sohbeti"
    assert [p["id"] for p in a.get("/api/palettes").json()["items"]] == [palet]
    assert a.get(f"/assets/logos/{varlik['filename']}").status_code == 200
    a_kok = tmp_path / "kullanicilar" / str(a_id)
    for dosya in ("output/chats.json", "output/palettes.json", "output/prefs.json",
                  "assets/logos/index.json"):
        assert not (a_kok / dosya).exists(), f"{dosya} web yolunda yazıldı"
    assert sorted(p.name for p in (a_kok / "assets" / "logos").iterdir()) == [varlik["filename"]]


def test_resolving_the_user_costs_exactly_one_query_per_request(istemci):
    """Belge: `oturumlar ⋈ kullanicilar` TEK sorgu; ayar nesnesi, dil halkası ve rota onu paylaşır.

    Faz 1 / 5'ten sonra `/api/history` İKİ sorgu: kimlik (1) + `medya` listesi (1) —
    rotanın kendi `Depends(kimlik.aktif_kullanici)`ı ve `OTURUM`u ek sorgu
    GETİRMEZ (FastAPI bağımlılık önbelleği, aynı `Session`). `/` hâlâ 1: dil
    zinciri `tercihler`e BAKMAZ (Faz 1 / 6 — Faz 0 / 3'ün "≤1 dosya okuma"
    ölçüsünün DB karşılığı: tercih için 0 ek sorgu). `GET /api/prefs` 2.
    """
    _, jeton, _ = _kullanici_ac(dil="tr")
    c = _oturumlu(jeton)
    sayac: list[str] = []

    def _say(conn, cursor, statement, parameters, context, executemany):
        sayac.append(statement)

    motor = appmod.app.state.motor
    event.listen(motor, "before_cursor_execute", _say)
    try:
        assert c.get("/api/history").status_code == 200
        assert len(sayac) == 2 and "oturumlar" in sayac[0] and "kullanicilar" in sayac[0], sayac
        assert "medya" in sayac[1] and "kullanici_id" in sayac[1], sayac
        sayac.clear()
        assert c.get("/", follow_redirects=False).status_code == 200
        assert len(sayac) == 1, sayac
        sayac.clear()
        assert c.get("/api/prefs").status_code == 200
        assert len(sayac) == 2 and "tercihler" in sayac[1] and "kullanici_id" in sayac[1], sayac
    finally:
        event.remove(motor, "before_cursor_execute", _say)


# ── Dil zincirinin 3. halkası DB'den ─────────────────────────────────

def _sayfa_dili(cevap) -> str:
    m = re.search(r'<html lang="(\w+)">', cevap.text)
    assert m is not None, cevap.text[:200]
    return m.group(1)


def test_the_interface_language_comes_from_the_account_row_not_the_preference_file(istemci, tmp_path):
    tr_id, tr_jeton, _ = _kullanici_ac(dil="tr")
    bos_id, bos_jeton, _ = _kullanici_ac(dil=None)
    tr, bos = _oturumlu(tr_jeton), _oturumlu(bos_jeton)
    en_tarayici = {"Accept-Language": "en-US,en;q=0.9"}
    # Hesap dili tarayıcıyı ezer; başlık ve çerez hesabı ezer.
    assert _sayfa_dili(tr.get("/", headers=en_tarayici)) == "tr"
    assert _sayfa_dili(tr.get("/", headers={**en_tarayici, "X-Kromis-Lang": "en"})) == "en"
    assert tr.delete("/api/image/yokboyle").json()["detail"] == i18n.t("err.image_missing", "tr")
    # Hesap dili NULL → tarayıcı; ve kullanıcının dizinindeki prefs.json OKUNMUYOR.
    bos.get("/api/history")     # dizin açılsın
    prefs.update({"language": "tr"}, appmod.app.state.ayarlar.kullanici_icin(bos_id).output_dir)
    assert _sayfa_dili(bos.get("/", headers=en_tarayici)) == "en"
    assert _sayfa_dili(bos.get("/", headers={"Accept-Language": "tr"})) == "tr"


def test_saving_the_language_writes_the_account_row_and_sets_the_cookie(istemci):
    kid, jeton, _ = _kullanici_ac(dil=None)
    c = _oturumlu(jeton)
    cevap = c.post("/api/prefs", json={"language": "tr"})
    assert cevap.status_code == 200
    assert c.cookies.get("kromis_lang") == "tr"
    with Session(appmod.app.state.motor) as db:
        assert db.scalar(select(Kullanici.dil).where(Kullanici.id == kid)) == "tr"
    # Çerezsiz başka cihaz aynı hesapla: dil DB'den.
    _, jeton2, _ = (kid, _oturum_ver(kid), None)
    assert _sayfa_dili(_oturumlu(jeton2).get("/", headers={"Accept-Language": "en"})) == "tr"
    # Başka bir tercih hesabın diline dokunmaz; reddedilen dil de.
    assert c.post("/api/prefs", json={"theme": "mono"}).status_code == 200
    assert c.post("/api/prefs", json={"language": "de"}).status_code == 422
    with Session(appmod.app.state.motor) as db:
        assert db.scalar(select(Kullanici.dil).where(Kullanici.id == kid)) == "tr"


def _oturum_ver(kid: uuid.UUID) -> str:
    """Var olan kullanıcıya ikinci bir oturum (başka cihaz)."""
    with Session(appmod.app.state.motor) as db:
        k = db.get(Kullanici, kid)
        assert k is not None
        jeton = hesap.oturum_ac(db, k, None, "ikinci cihaz", hesap.simdi())
        db.commit()
    return jeton


def test_the_401_of_the_gate_speaks_the_request_language_not_a_users(istemci):
    """Kullanıcı yokken 3. halka yok: mesaj başlık/çerez/Accept-Language'dan."""
    assert istemci.get("/api/history", headers={"Accept-Language": "tr"}).json()["detail"] == \
        i18n.t("err.hesap_giris_gerekli", "tr")


# ── Bağlama birimi ve dondurulmuş kabuk ─────────────────────────────

def test_bagla_puts_the_user_on_the_request_and_applies_the_third_link_only_when_nothing_explicit():
    from starlette.requests import Request

    def _istek(**state):
        r = Request({"type": "http", "app": appmod.app, "headers": [], "state": dict(state)})
        return r

    k = Kullanici(id=uuid.uuid4(), eposta="x@example.com", dil="tr")
    i18n.set_active("en")
    r = _istek(dil_acik=False)
    assert kimlik.bagla(r, k) is k and r.state.kullanici is k and i18n.active() == "tr"
    i18n.set_active("en")
    kimlik.bagla(_istek(dil_acik=True), k)
    assert i18n.active() == "en", "başlık/çerez konuştuysa hesap dili ezmez"
    i18n.set_active("en")
    kimlik.bagla(_istek(dil_acik=False), Kullanici(id=uuid.uuid4(), eposta="y@example.com", dil=None))
    assert i18n.active() == "en", "NULL dil halkayı düşürür"


def test_without_a_database_the_gate_says_503_not_500():
    """Dondurulmuş kabuk / `with`siz istemci: motor yok → `oturum` 503 KODU; kapı çökmez.

    Belgenin kararı (§1): veri tabanı olmadan hesap yok, hesap olmadan stüdyo
    yok — 44 rota bu sürümde DATABASE_URL'siz çalışmıyor.
    """
    c = TestClient(appmod.app)
    assert appmod.app.state.motor is None
    cevap = c.get("/api/history")
    assert cevap.status_code == 503 and cevap.json() == {"detail": "database_unavailable"}
    assert c.get("/", follow_redirects=False).status_code == 503
