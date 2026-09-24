"""Konteyner KAPISI: Dockerfile, .dockerignore, compose.yaml, .env.example ve CI'daki `docker` işi.

NEDEN VAR (Faz 0 / Adım 8). Bu dosyaların hiçbiri pytest'in koşturduğu kod
değil; yanlış olsalar takım yine yeşil kalır ve kusur ilk `docker run`da,
yani en geç görünen yerde çıkar. Dört karar burada mandallı, her biri ölçülmüş
bir kusurun ya da spec'te yazılı bir gerekçenin karşılığı:

  * İmaj `uvicorn app:app` koşturur, `netguard:korumali_app` fabrikasını
    DEĞİL: `run.sh`in loopback kapısı konteynerde her isteği 403'ler
    (docs/faz0-web-first.md → 8). Bir gün "run.sh ile aynı olsun" diye
    kopyalanırsa burada kırmızı.
  * Sağlayıcı anahtar adları `.env.example`da ELLE LİSTE DEĞİL, katalogdan
    türetilmiş küme: `fal_key`in elle yazılmış daldan kaçışı
    (tests/test_settings_route.py) bu kapının sebebi. Test aynı kümeyi
    `catalog.CREDENTIALS`tan yeniden kurar ve eşitlik ister.
  * `.env.example`da HİÇBİR anahtar değeri yok. Şablon dosyası bir gün
    "denemek için" doldurulup commit'lenirse gitleaks'ten önce burada düşer.
  * CI'daki `docker` işi imajı DERLER ve `/health`i SORAR ama İTMEZ: kayıt
    defteri yok, kimlik yok — Faz 1 kararı.
  * Veri tabanı (Faz 1 / 1. görev): `/health` `db_reachable` ölçüyor ve DB'siz
    konteyner 503 verir. Bu yüzden `compose.yaml`da bir `postgres` servisi,
    CI'ın `docker` işinde bir Postgres servis konteyneri + `DATABASE_URL` var
    ve `.env.example` değişkeni açıklıyor. Sonda 503'e ALIŞTIRILMADI — kapı
    gevşetmek yerine konteynere gerçek DB verildi; burada mandallı.

  * Göç DAĞITIM ÖNCESİ komut (Faz 1 / 9, K6): imajın CMD'si yalnız uvicorn,
    `tools/goc.py` imajda; compose'ta ayrı `goc` servisi, CI'ın `docker` işi
    konteyneri açmadan önce onu koşturuyor — bir platformun yaptığı sırayla.
    "Açılışta göç" bayrağı yok ve olmamalı (iki replika yarışı).
  * İşletme belgesi `docs/isletme.md` (Faz 1 / 9): DB / medya / anahtar üç
    ayrı yedek, anahtar döndürme, geri yükleme tatbikatı — kod değil, ama
    yokluğu ilk felakette görünür.

`.dockerignore` da sınanıyor: `tests/`, `android/`, `docs/`, `.venv/` bağlama
girerse imaj şişer ve her test değişikliği katman önbelleğini boşa düşürür;
`.env`/`output/` girerse yerel sır ve veri imaj katmanına yazılır; `tools/`
ise İÇERİDE kalmak zorunda — operatör araçları konteynerde koşuyor.
"""
from __future__ import annotations

import os
import re
import shlex

import yaml

import catalog
from services import (
    cerez,
    db,
    dosya,
    filigran,
    gunluk,
    hata_izleme,
    isci,
    kapilar,
    koken,
    kota,
    planlar,
    platform_anahtari,
    polar,
    posta,
    sifre,
)

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCKERFILE = os.path.join(KOK, "Dockerfile")
DOCKERIGNORE = os.path.join(KOK, ".dockerignore")
COMPOSE = os.path.join(KOK, "compose.yaml")
ENV_EXAMPLE = os.path.join(KOK, ".env.example")
CI_YML = os.path.join(KOK, ".github", "workflows", "ci.yml")
README = os.path.join(KOK, "README.md")
KURULUM = os.path.join(KOK, "KURULUM.md")
ISLETME = os.path.join(KOK, "docs", "isletme.md")


def _oku(yol: str) -> str:
    with open(yol, encoding="utf-8") as f:
        return f.read()


def _yaml(yol: str) -> dict:
    with open(yol, encoding="utf-8") as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------
# Dockerfile
# --------------------------------------------------------------------------

def _yonergeler() -> list[tuple[str, str]]:
    """(YÖNERGE, argüman) çiftleri; yorumlar atılmış, `\\` devam satırları birleşmiş."""
    satirlar: list[str] = []
    for ham in _oku(DOCKERFILE).splitlines():
        satir = ham.strip()
        if not satir or satir.startswith("#"):
            continue
        if satirlar and satirlar[-1].endswith("\\"):
            satirlar[-1] = satirlar[-1][:-1] + " " + satir
        else:
            satirlar.append(satir)
    ciftler = []
    for satir in satirlar:
        yonerge, _, arg = satir.partition(" ")
        ciftler.append((yonerge.upper(), arg.strip()))
    return ciftler


def _kod_metni() -> str:
    """Dockerfile'ın yorum DIŞI metni — bir adın yorumda anılması sayılmaz."""
    return "\n".join(arg for _, arg in _yonergeler())


def _env() -> dict[str, str]:
    ortam: dict[str, str] = {}
    for yonerge, arg in _yonergeler():
        if yonerge == "ENV":
            for parca in shlex.split(arg):
                ad, esit, deger = parca.partition("=")
                if esit:
                    ortam[ad] = deger
    return ortam


def test_every_stage_starts_from_python_3_13_slim():
    """Çok aşamalı ve HER aşama aynı tabanda: ilk aşama başka bir imajda kurulan
    bir tekerlek ikinci aşamada başka bir libc/Python bulurdu."""
    tabanlar = [arg.split()[0] for yonerge, arg in _yonergeler() if yonerge == "FROM"]
    assert len(tabanlar) >= 2, "Dockerfile çok aşamalı değil"
    assert all(t == "python:3.13-slim" for t in tabanlar), tabanlar


def test_the_image_runs_the_bare_app_not_the_desktop_netguard_factory():
    metin = _kod_metni()
    assert "netguard" not in metin, "run.sh'in loopback kapısı konteynerde her isteği 403'ler"
    assert "--factory" not in metin
    cmd = [arg for yonerge, arg in _yonergeler() if yonerge == "CMD"]
    assert len(cmd) == 1, cmd
    assert "uvicorn app:app" in cmd[0]
    assert "--host 0.0.0.0" in cmd[0], "konteynerde loopback dışarıdan görünmez"
    assert "${PORT" in cmd[0], "port .env.example'daki PORT'tan gelmeli"


def test_the_image_never_migrates_on_startup_and_has_no_flag_for_it():
    """K6: CMD `alembic upgrade && uvicorn` DEĞİL — iki replika yarışır (Alembic kilit
    tutmaz). Göç `tools/goc.py` ile dağıtım öncesi; "açılışta göç" bayrağı bilerek YOK."""
    metin = _kod_metni()
    assert "alembic" not in metin and "goc.py" not in metin, "imaj açılışta göç koşturuyor"
    assert not any(ad.startswith("KROMIS_GOC") for ad in _env()), "açılışta göç bayrağı eklenmiş"
    assert not any(ad.startswith("KROMIS_GOC") for ad, _, _ in _atamalar()), ".env.example'a göç bayrağı girmiş"
    # Gerekçe Dockerfile'da yazılı: bir gün "kolaylık" diye eklenmesin.
    assert "tools/goc.py" in _oku(DOCKERFILE) and "replika" in _oku(DOCKERFILE)


def test_the_image_runs_as_a_non_root_user():
    kullanicilar = [arg for yonerge, arg in _yonergeler() if yonerge == "USER"]
    assert kullanicilar, "USER yönergesi yok — uygulama root olarak koşar"
    assert kullanicilar[-1] not in ("root", "0"), kullanicilar
    # USER, CMD'den ÖNCE: sondaki USER root'a geri dönmüyor (yukarıda) ve
    # `useradd` gerçekten var — aksi hâlde docker build "unknown user" der.
    assert re.search(r"useradd\b.*\b" + re.escape(kullanicilar[-1]) + r"\b", _kod_metni())


def test_the_image_declares_the_data_volume_the_port_and_a_healthcheck():
    ortam = _env()
    assert ortam.get("KROMIS_DATA_DIR") == "/data"
    # HOME de /data: kimlik dosyası `~/.config/kromis/credentials.env`
    # (paths.credentials_path) birime insin, konteynerle birlikte kaybolmasın.
    assert ortam.get("HOME") == "/data"
    yonergeler = dict(_yonergeler()[::-1])  # aynı yönergeden birden fazlaysa İLKİ
    assert yonergeler.get("VOLUME") == "/data"
    assert yonergeler.get("EXPOSE") == "8765"
    saglik = [arg for yonerge, arg in _yonergeler() if yonerge == "HEALTHCHECK"]
    assert saglik and "/health" in saglik[0], saglik


def test_the_image_installs_no_system_packages_and_needs_no_curl():
    """`slim`e apt katmanı eklenmiyor; sonda standart kütüphaneyle (urllib)."""
    metin = _kod_metni()
    assert "apt-get" not in metin and "apt " not in metin, "sistem paketi kurulmuş"
    assert "curl" not in metin, "sonda curl'e muhtaç — slim'de yok"
    assert "urllib" in metin


def test_the_runtime_deps_are_requirements_txt_itself():
    """Ayrı bir `requirements-web.txt` YOK — ölçüldü, web dışı paketler ~6 MB
    (Dockerfile başlığı). Biri eklenirse bu iddia ve o gerekçe birlikte değişir."""
    kopyalar = [arg for yonerge, arg in _yonergeler() if yonerge == "COPY"]
    assert any(arg.startswith("requirements.txt ") for arg in kopyalar), kopyalar
    assert not os.path.exists(os.path.join(KOK, "requirements-web.txt"))
    assert "pip install -r /tmp/requirements.txt" in _kod_metni()


# --------------------------------------------------------------------------
# .dockerignore
# --------------------------------------------------------------------------

def _dislananlar() -> set[str]:
    return {satir.strip().rstrip("/") for satir in _oku(DOCKERIGNORE).splitlines()
            if satir.strip() and not satir.startswith("#")}


def test_dockerignore_excludes_tests_docs_android_venv_and_local_secrets():
    # `.env*`, `.env` DEĞİL: yalın `.env` adın tamamını eşler, `.env.yedek-…`
    # gibi bir yedek yerel `docker build`de `COPY . /app` ile imaja girerdi —
    # .gitignore'la aynı kusur (tests/test_env_yok_sayma.py), burada bağlam için.
    eksik = {"tests", "android", "docs", ".venv", "node_modules", ".git",
             ".env*", "output", "assets", "hata.log"} - _dislananlar()
    assert not eksik, f".dockerignore'da yok: {sorted(eksik)}"


def test_dockerignore_keeps_everything_the_app_serves_or_imports():
    """`COPY . /app` bağlamın tamamını aldığı için dışlama listesi kaynağı
    yutmamalı: static/ ve bundled/ olmadan uygulama açılır ama `/` 500 verir."""
    # `isci.py` (Faz 2 / 3): işçi sürecinin girişi, aynı imajdan `python isci.py` ile
    # açılır — bağlamdan düşerse `docker compose up` `isci` servisi hiç başlamaz.
    yasak = {"static", "bundled", "routers", "services", "requirements.txt",
             "app.py", "isci.py", "LICENSE", "NOTICE", "alembic", "alembic.ini", "tools"} & _dislananlar()
    assert not yasak, f".dockerignore uygulamanın parçasını dışlıyor: {sorted(yasak)}"
    # `*.py` gibi bir kalıp da aynı sonucu verirdi; `**/*.md` ise
    # `bundled/prompts/*.md`yi (Yönetmen personası) yutardı — kök `*.md` yutmaz.
    assert not any(k in ("*.py", "*", "**/*.md", "**/*") for k in _dislananlar())
    assert os.path.exists(os.path.join(KOK, "bundled", "prompts", "prompt-yonetmeni.md"))
    # `bundled/filigran.png` (Faz 3 / 4): işçi ücretsiz planın görselini bununla
    # filigranlıyor; imajdan düşerse iş `hata`ya düşer (sessiz filigransız DEĞİL) —
    # yani kusur ancak ilk ücretsiz üretimde görünürdü. `*.png` gibi bir kalıp da yutardı.
    assert os.path.exists(os.path.join(KOK, "bundled", "filigran.png"))
    assert not any(k in ("*.png", "bundled/filigran.png", "bundled/*") for k in _dislananlar())
    # `bundled/hukuk/*.html` (Faz 4 / 6): hukuki metinler — `GET /hukuk/{slug}` parçayı buradan okur;
    # imajdan düşerse sayfa 404 verir ve kayıt kutusunun bağlandığı metin yok olur. `*.html` gibi bir
    # kalıp da yutardı (kök `*.md` kalıbının gerekçesiyle aynı sınıf).
    assert os.path.exists(os.path.join(KOK, "bundled", "hukuk", "kullanim-sartlari.tr.html"))
    assert not any(k in ("*.html", "**/*.html", "bundled/hukuk") for k in _dislananlar())


# `medya_tasi` (Faz 2 / 2): yerel medyayı kovaya taşır — konteyner içinden, `/data` birimine bakar.
# `rls_kontrol` + `uygulama_rolu` (Faz 2 / 7): canlı `DATABASE_URL` rolünü ölçer ve
# gerekirse RLS'i atlamayan rolü açar — ikisi de tam o bağlantının olduğu yerden,
# yani platformun kabuğundan/konteynerden koşuyor (KURULUM.md 1. adım).
# `marj_raporu` (Faz 3 / 5): canlı `DATABASE_URL`den marj CSV'si — sahibin aylık fatura
# mutabakatı konteynerin içinden koşar; `tarife_kontrol` ise kaynağı (catalog.py'nin
# YORUMLARINI) okur, depodan koşulur, .dockerignore'da.
# `polar_esitle` (Faz 4 / 4): Polar ürünlerini `urunler` aynasına yazar — canlı `DATABASE_URL` + Polar
# jetonuyla, web imajının içinden (jeton zaten o sürecin ortamında); sahibin fiyat değişikliği adımı.
OPERATOR_ARACLARI = ("goc", "kullanici", "ice_aktar", "artik_dosya", "anahtar_dondur",
                     "medya_tasi", "rls_kontrol", "uygulama_rolu", "marj_raporu", "polar_esitle")


def test_dockerignore_ships_the_operator_tools_and_only_the_dev_tools_stay_out():
    """`tools/` İMAJDA (Faz 1 / 9): `goc.py` platformun dağıtım öncesi komutu, ötekiler
    konteyner içinden koşuyor. Dışlama ADIYLA ve yalnız geliştirici araçları; listede
    olmayan yeni bir araç imaja GİRER. Her `tools/*.py` iki kümeden tam birinde."""
    dislanan = _dislananlar()
    for ad in OPERATOR_ARACLARI:
        assert os.path.exists(os.path.join(KOK, "tools", f"{ad}.py")), ad
        assert f"tools/{ad}.py" not in dislanan, f"{ad} operatör aracı — imajda kalmalı"
    dev = {a for a in dislanan if a.startswith("tools/")}
    diskteki = {f"tools/{a}" for a in os.listdir(os.path.join(KOK, "tools"))
                if a.endswith(".py") and a != "__init__.py"}
    assert dev <= diskteki, f"olmayan dosya dışlanıyor: {sorted(dev - diskteki)}"
    assert diskteki - dev == {f"tools/{ad}.py" for ad in OPERATOR_ARACLARI}, (
        "yeni tools/*.py: ya OPERATOR_ARACLARI'na ya .dockerignore'a, gerekçesiyle")


# --------------------------------------------------------------------------
# .env.example
# --------------------------------------------------------------------------

def _atamalar() -> list[tuple[str, str, bool]]:
    """(ad, değer, hemen üstünde yorum var mı) — dosya sırasıyla."""
    sonuc = []
    onceki_yorum = False
    for satir in _oku(ENV_EXAMPLE).splitlines():
        if not satir.strip():
            continue
        if satir.startswith("#"):
            onceki_yorum = True
            continue
        ad, esit, deger = satir.partition("=")
        assert esit and re.fullmatch(r"[A-Z][A-Z0-9_]*", ad), f"geçersiz satır: {satir!r}"
        sonuc.append((ad, deger.strip(), onceki_yorum))
        # Aynı bloktaki ikinci atama (anahtar + adres) yorumu paylaşır.
    return sonuc


# Altyapı değişkenleri — Faz 1 / 1 ile `DATABASE_URL` (services/db.py okuyor);
# Faz 1 / 3 ile hesap ve e-posta: `KROMIS_KOKEN` (services/koken.py),
# `KROMIS_POSTA`, `KROMIS_POSTA_GONDEREN`, `RESEND_API_KEY` (services/posta.py),
# `KROMIS_GUVENLI_CEREZ` (services/cerez.py); Faz 1 / 7 ile şifreleme anahtarı
# `KROMIS_SECRET_KEY` (services/sifre.py); Faz 2 / 2 ile nesne depolama
# `KROMIS_NESNE_DEPO_{URL,KOVA,ANAHTAR_ID,GIZLI,BOLGE}` (services/dosya.py);
# Faz 2 / 3 ile işçi süreci `KROMIS_ISCI_ES_ZAMANLI`, `KROMIS_IS_KALP_ESIGI_SN`
# (services/isci.py — yalnız `isci.py` okur, ama aynı imaj ve aynı şablon);
# Faz 2 / 4 ile kullanıcı başına eş zamanlı iş tavanı `KROMIS_KULLANICI_ES_ZAMANLI_IS`
# (services/kapilar.py); Faz 2 / 6 ile iki kota tavanı `KROMIS_SAATLIK_IS_TAVANI`,
# `KROMIS_GUNLUK_KREDI_TAVANI` (services/kota.py); Faz 2 / 9 ile günlük biçimi
# `KROMIS_GUNLUK_BICIMI` (services/gunluk.py) ve Sentry `SENTRY_DSN`,
# `SENTRY_ENVIRONMENT` (services/hata_izleme.py; web VE işçi); Faz 2 / 10 ile iş saklama
# `KROMIS_IS_SAKLAMA_GUN` (services/isci.py `bakim_turu`). Adlar KAYNAKTAN, elle değil.
ALTYAPI = {"KROMIS_DATA_DIR", "PORT", db.DATABASE_URL_ENV, koken.KOKEN_ENV,
           posta.POSTA_ENV, posta.GONDEREN_ENV, posta.RESEND_ANAHTAR_ENV, cerez.GUVENLI_ENV,
           sifre.ANAHTAR_ENV,
           dosya.URL_ENV, dosya.KOVA_ENV, dosya.ANAHTAR_ID_ENV, dosya.GIZLI_ENV, dosya.BOLGE_ENV,
           isci.ES_ZAMANLI_ENV, isci.KALP_ESIGI_ENV, isci.SAKLAMA_ENV, kapilar.ES_ZAMANLI_IS_ENV,
           isci.HESAP_SILME_BEKLEME_ENV,  # Faz 4 / 5: hesap silme → içerik temizliği beklemesi (gün)
           kota.SAATLIK_IS_ENV, kota.GUNLUK_KREDI_ENV,
           planlar.FREE_AYLIK_HIBE_ENV,   # Faz 3 / 3: ücretsiz planın aylık hibesi
           planlar.TEMEL_AYLIK_HIBE_ENV, planlar.PRO_AYLIK_HIBE_ENV,   # Faz 4 / 2: ücretli planların dönem hibesi
           polar.ORTAM_ENV, polar.JETON_ENV, polar.WEBHOOK_SIRRI_ENV,   # Faz 4 / 3: Polar ortamı, erişim jetonu, webhook sırrı
           filigran.DOSYA_ENV,            # Faz 3 / 4: ücretsiz planın filigran işareti
           gunluk.BICIM_ENV, hata_izleme.DSN_ENV, hata_izleme.ORTAM_ENV}


def _katalog_adlari() -> set[str]:
    """Sağlayıcı değişken adları — KATALOGDAN, elle değil."""
    adlar = {c.key_env for c in catalog.CREDENTIALS}
    adlar |= {c.url_env for c in catalog.CREDENTIALS if c.url_env}
    adlar |= {m.wire_from_env for m in catalog.CHAT_MODELS if m.wire_from_env}
    return adlar


def _platform_adlari() -> set[str]:
    """1d bölümü (Faz 2 / 6): `KROMIS_PLATFORM_` + katalog adı — öneki de katalogla kuruyoruz,
    `platform_anahtari.ADLAR`ı kopyalamıyoruz (o kümenin kendi bekçisi test_platform_anahtari)."""
    return {platform_anahtari.ONEK + ad for ad in _katalog_adlari()}


def _kodun_okudugu_adlar() -> set[str]:
    """Ürün kodunun `os.environ`dan okuduğu değişkenler — kaynağı regex'le tarayarak.

    `ALTYAPI` elle kurulu bir küme; bu tarama onun bekçisi: kod yeni bir
    değişken okumaya başlar da şablona girmezse burada görünür. Dondurulmuş
    kabuğun/Android'in kendi değişkenleri (`KROMIS_ANDROID_*`, `LOCALAPPDATA`)
    web'e ait değil, `paths.py`nin platform dalları — dışarıda.
    """
    adlar: set[str] = set()
    for kok, _, dosyalar in os.walk(KOK):
        goreli = os.path.relpath(kok, KOK)
        # `.claude` ATLAMA LİSTESİNDE, çünkü Claude Code oturumları depoya
        # `.claude/worktrees/<ad>/` altında TAM bir çalışma ağacı (kendi
        # `.venv`iyle birlikte) bırakıyor: ölçüldü 2026-09-18, 3.313 `.py`.
        # Tarama oraya indiğinde üçüncü parti paketlerin okuduğu değişkenleri
        # (`PYINSTALLER_*`, `PIP_*`, `WEBSOCKETS_*`, `XDG_*`) "ürün kodu
        # okuyor" sanıp `.env.example`da arıyor ve takım YERELDE kırmızıya
        # dönüyordu. CI'da böyle bir dizin hiç oluşmadığı için kusur yalnız
        # geliştirici makinesinde görünüyor — yani CI yeşilken yerel kırmızı.
        if goreli.split(os.sep)[0] in ("tests", "tools", "android", "docs", ".venv", "node_modules",
                                       "alembic", ".git", ".claude", "build", "dist"):
            continue
        for ad in dosyalar:
            if ad.endswith(".py"):
                adlar |= set(re.findall(r"os\.environ(?:\.get)?\(\s*\"([A-Z][A-Z0-9_]+)\"",
                                        _oku(os.path.join(kok, ad))))
    return adlar


def test_the_infra_set_is_exactly_what_the_web_build_reads_from_the_environment():
    """Bekçinin bekçisi: `ALTYAPI` sabitleri kaynaktan geliyor ama KÜME elle;
    kaynak taraması onunla bir olmalı (platform dalları hariç, gerekçe yukarıda)."""
    okunan = _kodun_okudugu_adlar()
    platform = {"LOCALAPPDATA"}
    beklenen = {ad for ad in okunan if not ad.startswith("KROMIS_ANDROID_")} - platform
    # Kod çoğu adı sabit üzerinden okuyor (`os.environ.get(DATABASE_URL_ENV)`); bu
    # tarama yalnız DİZE literalli okumaları görür — o yüzden alt küme, eşitlik değil.
    assert beklenen <= ALTYAPI, f"kodun okuduğu ama şablonda olmayan: {sorted(beklenen - ALTYAPI)}"
    for ad in ALTYAPI:
        assert ad in _oku(ENV_EXAMPLE), ad


def test_env_example_lists_exactly_the_infra_vars_and_the_catalog_names():
    adlar = [ad for ad, _, _ in _atamalar()]
    assert len(adlar) == len(set(adlar)), "yinelenen ad"
    beklenen = ALTYAPI | _katalog_adlari() | _platform_adlari()
    assert len(beklenen) > 10, "katalog şüpheli biçimde küçük"  # bekçinin bekçisi
    assert set(adlar) == beklenen, (
        f"eksik: {sorted(beklenen - set(adlar))}, fazla: {sorted(set(adlar) - beklenen)}")


def test_env_example_carries_no_secret_values():
    """Her sağlayıcı satırı BOŞ; altyapı değerleri anahtara benzemez."""
    for ad, deger, _ in _atamalar():
        if ad in ALTYAPI:
            assert not re.search(r"[A-Za-z0-9_\-]{20,}", deger), f"{ad} anahtara benziyor"
        else:
            assert deger == "", f"{ad} boş değil: şablona değer yazılmış"


def test_every_env_example_variable_is_explained():
    aciklamasiz = [ad for ad, _, yorum in _atamalar() if not yorum]
    assert not aciklamasiz, f"üstünde açıklama olmayan değişken: {aciklamasiz}"


def test_env_example_warns_that_provider_keys_are_not_read_from_the_environment():
    """KULLANICI anahtarını web kullanıcı başına DB'den okur (`saglayici_kimlikleri`,
    Faz 1 / 7), masaüstünde `credentials.env`den; 2. bölümün adlarıyla `os.environ`dan
    HİÇ değil. Şablon bunu söylemezse `.env`e `GEMINI_API_KEY=` yazan 'neden çalışmıyor'
    der. Ortamdan okunan tek anahtar PLATFORMUN (Faz 2 / 6) ve o ayrı önekle, 1d'de."""
    metin = _oku(ENV_EXAMPLE)
    assert "SÜREÇ ORTAMINDAN" in metin and "credentials.env" in metin
    assert "saglayici_kimlikleri" in metin and "ŞİFRELİ" in metin
    # Faz 0 / 8'in "ortamdan okuma (12-factor)" takibi kullanıcı anahtarı için KAPANDI diye
    # yazılı olmalı; platform anahtarı 1d'ye işaret etmeli.
    assert "12-factor" in metin and "KAPANDI" in metin
    assert platform_anahtari.ONEK in metin and "1d" in metin


def test_env_example_section_1d_is_the_catalog_names_with_the_platform_prefix_and_no_value():
    """Faz 2 / 6: 1d bölümü her katalog adını `KROMIS_PLATFORM_` önekiyle sayar, hepsi boş,
    ALTYAPI'dan sonra ve 2. bölümden önce; iki kota tavanı 1. bölümde (ALTYAPI) ve
    öntanımlıları (60 / 2000) açıklamasında yazılı."""
    adlar = [ad for ad, _, _ in _atamalar()]
    platform = [ad for ad in adlar if ad.startswith(platform_anahtari.ONEK)]
    assert set(platform) == _platform_adlari()
    ilk, son = adlar.index(platform[0]), adlar.index(platform[-1])
    assert ilk == len(ALTYAPI), "1d bölümü ALTYAPI'nın hemen ardından başlamalı"
    assert adlar[ilk:son + 1] == platform, "1d bölümü bir arada değil"
    assert all(deger == "" for ad, deger, _ in _atamalar() if ad.startswith(platform_anahtari.ONEK))
    metin = _oku(ENV_EXAMPLE)
    assert str(kota.SAATLIK_IS_VARSAYILAN) in metin and str(kota.GUNLUK_KREDI_VARSAYILAN) in metin
    assert "kullanıcının kendi satırı → buradaki değer → yok" in metin, "çözüm sırası yazılı olmalı"


def test_env_example_requires_the_secret_key_and_shows_the_generation_command():
    """`KROMIS_SECRET_KEY` (Faz 1 / 7): şablonda ADI var, DEĞERİ yok, ZORUNLU olduğu ve
    nasıl üretileceği yazılı — `services/sifre.py`nin hata mesajıyla AYNI komut."""
    degerler = {ad: deger for ad, deger, _ in _atamalar()}
    assert sifre.ANAHTAR_ENV in degerler and degerler[sifre.ANAHTAR_ENV] == ""
    metin = _oku(ENV_EXAMPLE)
    assert "ZORUNLU" in metin and "AÇILMAZ" in metin
    assert sifre.URETIM_KOMUTU in metin, "üretim komutu sifre.URETIM_KOMUTU ile birebir olmalı"
    assert "AYRI SAKLANIR" in metin, "anahtar DB yedeğinden ayrı — belge §7/§9"
    assert "tools/anahtar_dondur.py" in metin and "docs/isletme.md" in metin


def test_env_example_has_its_final_shape_infra_first_then_the_credentials_file_format():
    """Faz 1 / 9: 1. bölüm web'in okuduğu HER şey (sıra: veri kökü, port, DB, anahtar,
    köken, posta, çerez), 2. bölüm başlığı `credentials.env` biçimi olduğunu söyler —
    web bunları DB'de tutar. Şablonu okuyan işletmen önce kendi işini görür."""
    adlar = [ad for ad, _, _ in _atamalar()]
    altyapi_sirasi = [ad for ad in adlar if ad in ALTYAPI]
    assert altyapi_sirasi == adlar[:len(ALTYAPI)], "altyapı değişkenleri en başta ve bir arada değil"
    assert altyapi_sirasi[:4] == ["KROMIS_DATA_DIR", "PORT", db.DATABASE_URL_ENV, sifre.ANAHTAR_ENV]
    metin = _oku(ENV_EXAMPLE)
    assert ("credentials.env biçimi — dondurulmuş masaüstü/Android sürümü ve "
            "`tools/ice_aktar.py --kimlik-dosyasi` için; web sürümü bunları DB'de tutar") in metin
    assert "kullanicilar/<uuid>" in metin, "KROMIS_DATA_DIR'ın web'deki yerleşimi yazılı olmalı"
    assert "tools/goc.py" in metin, "şemanın dağıtım öncesi komutla kurulduğu yazılı olmalı"


def test_env_example_defaults_match_the_dockerfile():
    degerler = {ad: deger for ad, deger, _ in _atamalar()}
    assert degerler["KROMIS_DATA_DIR"] == _env()["KROMIS_DATA_DIR"]
    assert degerler["PORT"] == dict(_yonergeler()[::-1])["EXPOSE"]


def test_env_example_names_the_database_url_the_app_reads_and_leaves_it_empty():
    """Ad `services.db.DATABASE_URL_ENV` ile aynı (ikinci bir literal değil) ve
    değer BOŞ: compose kendi adresini verir, şablon parola taşımaz."""
    from services import db
    degerler = {ad: deger for ad, deger, _ in _atamalar()}
    assert db.DATABASE_URL_ENV in degerler
    assert degerler[db.DATABASE_URL_ENV] == ""
    metin = _oku(ENV_EXAMPLE)
    assert "postgresql+psycopg://" in metin, "biçim örneği yok — geliştirici sürücü adını tahmin eder"
    assert "db_reachable" in metin, "değişken yokken ne olduğu (503) yazılı olmalı"


# --------------------------------------------------------------------------
# compose.yaml
# --------------------------------------------------------------------------

def test_compose_is_dev_only_builds_locally_and_mounts_the_data_volume():
    assert "YALNIZ YEREL GELİŞTİRME" in _oku(COMPOSE)
    veri = _yaml(COMPOSE)
    servisler = veri["services"]
    assert set(servisler) == {"kromis", "goc", "isci", "postgres"}, list(servisler)
    servis = servisler["kromis"]
    assert servis.get("build") == ".", "imaj yerelden derlenmeli, bir kayıt defterinden çekilmemeli"
    # `image:` yalnız YEREL bir ad olabilir (iki servis aynı derlemeyi paylaşsın);
    # `/` ya da `:` taşıyan bir ad kayıt defterine işaret eder.
    assert not any(c in str(servis.get("image", "")) for c in "/:"), servis.get("image")
    assert "8765:8765" in servis.get("ports", [])
    baglar = [str(b) for b in servis.get("volumes", [])]
    assert any(b.endswith(":/data") for b in baglar), baglar


def test_compose_gives_the_app_a_postgres_and_waits_for_it_to_be_healthy():
    """DB'siz konteyner `/health` 503 verir; compose bunu kendi çözer (Faz 1 / 1).

    `environment:` `env_file`i ezer — `.env`deki boş `DATABASE_URL=` bu
    adresi gizleyemez. `service_healthy`: Postgres kabul etmeden uygulama
    açılıp ilk saniyelerde sebepsiz 503 demesin. Göç burada KOŞMAZ (K6).
    """
    from services import db
    veri = _yaml(COMPOSE)
    kromis, postgres = veri["services"]["kromis"], veri["services"]["postgres"]
    url = str(kromis.get("environment", {}).get(db.DATABASE_URL_ENV, ""))
    assert url.startswith("postgresql+psycopg://") and "@postgres:" in url, url
    assert kromis.get("depends_on", {}).get("postgres", {}).get("condition") == "service_healthy"
    assert str(postgres.get("image", "")).startswith("postgres:17"), postgres.get("image")
    assert "healthcheck" in postgres and "pg_isready" in str(postgres["healthcheck"].get("test"))
    baglar = [str(b) for b in postgres.get("volumes", [])]
    assert any(b.endswith("/var/lib/postgresql/data") for b in baglar), baglar
    # Yalnız loopback yayınlanıyor: ağdaki başka makine dev Postgres'ini görmesin.
    for port in postgres.get("ports", []):
        assert str(port).startswith("127.0.0.1:"), port
    # Yorum satırları atılıyor: gerekçe metni `alembic`i anıyor, komut anmıyor.
    kod = "\n".join(s for s in _oku(COMPOSE).splitlines() if not s.lstrip().startswith("#"))
    assert "alembic" not in kod, "göç `alembic` ile değil `tools/goc.py` ile — tek sarmalayıcı"
    assert "goc.py" not in str(kromis.get("command", "")), "uygulama servisi göç koşturuyor (K6)"


def test_compose_runs_the_migration_in_its_own_service_and_the_app_waits_for_it():
    """Faz 1 / 9, K6: `goc` aynı imajla `python tools/goc.py` koşturup biter; `kromis`
    onu `service_completed_successfully` ile bekler. Platformların "dağıtım öncesi
    komut"unun yerel ikizi — uygulama konteyneri hiçbir zaman göç koşturmaz."""
    veri = _yaml(COMPOSE)
    goc, kromis = veri["services"]["goc"], veri["services"]["kromis"]
    assert goc.get("build") == "." and goc.get("image") == kromis.get("image"), "aynı imaj olmalı"
    komut = goc.get("command")
    assert komut == ["python", "tools/goc.py"], komut
    assert goc.get("depends_on", {}).get("postgres", {}).get("condition") == "service_healthy"
    assert kromis.get("depends_on", {}).get("goc", {}).get("condition") == "service_completed_successfully"
    assert str(goc.get("environment", {}).get(db.DATABASE_URL_ENV, "")) == str(
        kromis["environment"][db.DATABASE_URL_ENV]), "göç uygulamanın DB'sine gitmeli"
    assert "ports" not in goc and "volumes" not in goc, "göç servisi ne port açar ne birim bağlar"
    assert str(goc.get("restart", "no")) == "no", "biten bir iş yeniden başlatılmaz"
    # `KROMIS_SECRET_KEY` (Faz 1 / 7): compose değeri `.env`/kabuktan yorumlar, yoksa
    # `:?` ile DURUR — dosyaya sabit anahtar YAZILMAZ (git'te anahtar demek).
    anahtar = str(kromis.get("environment", {}).get(sifre.ANAHTAR_ENV, ""))
    assert anahtar.startswith("${" + sifre.ANAHTAR_ENV + ":?"), anahtar


def test_compose_runs_the_worker_from_the_same_image_on_the_same_volume_after_the_migration():
    """Faz 2 / 3: `isci` servisi aynı imajla `python isci.py` koşturur (Dockerfile CMD
    değişmez — platform ikinci süreci bu komutla açar). Web ile AYNI `/data` birimi:
    yerel kipte medya diskte, işçinin yazdığını web ancak aynı dizinden görür. Göçü
    bekler: şemasız açılan işçi `isciler`e yazamaz. Aynı DB, aynı anahtar kapısı
    (`:?` — anahtarsız işçi de açılmaz); port yok (dışarıdan konuşulmaz)."""
    veri = _yaml(COMPOSE)
    isci_s, kromis = veri["services"]["isci"], veri["services"]["kromis"]
    assert isci_s.get("build") == "." and isci_s.get("image") == kromis.get("image"), "aynı imaj olmalı"
    assert isci_s.get("command") == ["python", "isci.py"], isci_s.get("command")
    assert isci_s.get("depends_on", {}).get("goc", {}).get("condition") == "service_completed_successfully"
    assert isci_s.get("depends_on", {}).get("postgres", {}).get("condition") == "service_healthy"
    assert str(isci_s.get("environment", {}).get(db.DATABASE_URL_ENV, "")) == str(
        kromis["environment"][db.DATABASE_URL_ENV]), "işçi uygulamanın DB'sine gitmeli"
    anahtar = str(isci_s.get("environment", {}).get(sifre.ANAHTAR_ENV, ""))
    assert anahtar.startswith("${" + sifre.ANAHTAR_ENV + ":?"), anahtar
    web_birim = [str(b) for b in kromis.get("volumes", []) if str(b).endswith(":/data")]
    assert web_birim and web_birim[0] in [str(b) for b in isci_s.get("volumes", [])], \
        "işçi web ile aynı /data birimini paylaşmalı (yerel kipte ortak disk)"
    assert "ports" not in isci_s, "işçi port açmaz"
    # Port açmamanın DOĞRUDAN sonucu: imajın `/health` yoklayan HEALTHCHECK'i
    # işçide hiçbir zaman yanıt alamaz, o yüzden bu serviste KAPALI olmak
    # zorunda. Kapatılmazsa kap kalıcı "unhealthy" görünür (2026-09-18'de
    # ölçüldü) ve yönetilen platformda yeniden başlatma döngüsüne girer.
    assert isci_s.get("healthcheck", {}).get("disable") is True, \
        "işçi port açmadığı için imajın /health denetimi bu serviste kapatılmalı"
    # Kapanış süresi (Faz 2 / 10): compose'un öntanımlı 10 sn'si bir görsel işini bile
    # bitirmeye yetmez, SIGKILL işi `calisiyor`da bırakır; belge 60 sn der.
    assert str(isci_s.get("stop_grace_period", "")) == "60s", isci_s.get("stop_grace_period")
    # Dockerfile CMD hâlâ web: ikinci süreç komutla ayrılır, ikinci imajla değil.
    cmd = [arg for yonerge, arg in _yonergeler() if yonerge == "CMD"]
    assert cmd and "uvicorn" in cmd[-1] and "isci" not in cmd[-1], cmd


# --------------------------------------------------------------------------
# ci.yml → `docker` işi
# --------------------------------------------------------------------------

def _docker_isi() -> dict:
    isler = _yaml(CI_YML)["jobs"]
    assert "docker" in isler, "ci.yml'de `docker` işi yok"
    return isler["docker"]


def _komutlar() -> str:
    return "\n".join(str(a.get("run") or "") for a in _docker_isi().get("steps", []))


def test_ci_builds_the_image_and_probes_health():
    komutlar = _komutlar()
    assert "docker build" in komutlar
    assert "docker run" in komutlar
    assert "/health" in komutlar, "iş imajı derliyor ama açılıp açılmadığını sormuyor"
    assert "docker rm -f" in komutlar, "konteyner temizlenmiyor"


def test_ci_docker_job_never_pushes_or_logs_in():
    komutlar = _komutlar()
    assert "docker push" not in komutlar and "docker login" not in komutlar
    kullanilan = [str(a.get("uses") or "") for a in _docker_isi().get("steps", [])]
    assert not any("login-action" in u or "build-push-action" in u for u in kullanilan), kullanilan


def test_ci_docker_job_runs_the_container_against_a_postgres_service():
    """Sonda `db_reachable` ölçtüğü için DB'siz konteyner 503 verir; iş kapıyı
    GEVŞETMEDİ (503 kabul etmiyor), konteynere gerçek DB verdi (Faz 1 / 1).

    `--network host`: servis konağın `localhost:5432`inde, `host.docker.internal`
    Linux koşucuda yok. `DATABASE_URL` `-e` ile içeri, adı `services.db` ile aynı.
    """
    from services import db
    is_ = _docker_isi()
    servis = is_.get("services", {}).get("postgres")
    assert servis, "docker işinde postgres servisi yok — konteyner 503 verir"
    assert str(servis.get("image", "")).startswith("postgres:17"), servis.get("image")
    assert "pg_isready" in str(servis.get("options", "")), "servis sağlık denetimi yok"
    adimlar = [a for a in is_.get("steps", []) if "docker run -d" in str(a.get("run", ""))]
    assert len(adimlar) == 1, adimlar
    adim = adimlar[0]
    assert "--network host" in adim["run"]
    assert f"-e {db.DATABASE_URL_ENV}" in adim["run"]
    # `KROMIS_SECRET_KEY` (Faz 1 / 7): DB'li süreç anahtarsız açılmaz; iş anahtarı
    # her koşuda ÜRETİR, workflow'a yazmaz (sabit değer git'te bir anahtar olurdu).
    # Faz 2 / 10: üretim ayrı bir adımda (`$GITHUB_ENV`), işçi ve web aynı anahtarı alır.
    assert f"-e {sifre.ANAHTAR_ENV}" in adim["run"]
    uretim = [a for a in is_.get("steps", []) if "secrets.token_bytes(32)" in str(a.get("run", ""))]
    assert len(uretim) == 1 and "GITHUB_ENV" in uretim[0]["run"], "anahtar tek adımda üretilip ortama yazılmalı"
    assert is_["steps"].index(uretim[0]) < is_["steps"].index(adim), "anahtar konteynerden önce üretilmeli"
    for a in is_.get("steps", []):
        assert sifre.ANAHTAR_ENV not in (a.get("env") or {}), "anahtar workflow'a sabit yazılmış"
    url = str(adim.get("env", {}).get(db.DATABASE_URL_ENV, ""))
    assert url.startswith("postgresql+psycopg://") and "localhost:5432" in url, url
    # `curl -f` duruyor: 503 hâlâ kırmızı, sonda gevşetilmedi.
    assert "curl -fsS" in adim["run"] and "/health" in adim["run"]
    assert "/giris" in adim["run"], "giriş sayfası da sorulmalı — şema kurulmadıysa orada görünür"


def test_ci_docker_job_migrates_from_the_image_before_starting_the_container():
    """Faz 1 / 9: göç adımı bir platformun yaptığı sırayla — `docker run --rm … python
    tools/goc.py` (dağıtım öncesi komut) ÖNCE, uygulama konteyneri SONRA; aynı
    Postgres, aynı `--network host`. İkinci koşu idempotenliği ölçüyor. İmaj boyutu
    da burada okunuyor (Faz 0 / 8'in ölçülmeyen sayısı)."""
    from services import db
    adimlar = _docker_isi().get("steps", [])
    komutlar = [str(a.get("run") or "") for a in adimlar]
    goc = [i for i, k in enumerate(komutlar) if "tools/goc.py" in k]
    sonda = [i for i, k in enumerate(komutlar) if "docker run -d" in k]
    derleme = [i for i, k in enumerate(komutlar) if "docker build" in k]
    assert len(goc) == 1 and len(sonda) == 1 and len(derleme) == 1, komutlar
    assert derleme[0] < goc[0] < sonda[0], "sıra: derle → göç → aç"
    adim = adimlar[goc[0]]
    assert adim["run"].count("docker run --rm --network host -e DATABASE_URL kromis python tools/goc.py") == 2, (
        "göç iki kez koşmalı: ilki boş DB → head, ikincisi idempotenlik")
    assert str(adim.get("env", {}).get(db.DATABASE_URL_ENV, "")) == str(
        adimlar[sonda[0]]["env"][db.DATABASE_URL_ENV]), "göç ve uygulama aynı DB'ye gitmeli"
    assert "set -euo pipefail" in adim["run"], "göç düşerse adım da düşmeli"
    assert "docker image ls" in komutlar[derleme[0]], "imaj boyutu basılmıyor"


def test_ci_docker_job_runs_the_worker_once_from_the_image_and_checks_the_worker_alive_field():
    """Faz 2 / 10: göçten SONRA, web konteynerinden ÖNCE aynı imajdan `python isci.py --tek-tur`
    (boş kuyruk → 0; işçi girişi imajda ve web'in kapılarından geçiyor). Sonda `/health`
    gövdesinde `worker_alive` ALANINI arar (Faz 2 / 9 sözleşmesi) — değerini değil, tek tur
    işçi çıktı. `_test.yml` DEĞİŞMEZ (belge §10)."""
    from services import db
    adimlar = _docker_isi().get("steps", [])
    komutlar = [str(a.get("run") or "") for a in adimlar]
    goc = [i for i, k in enumerate(komutlar) if "tools/goc.py" in k]
    isci_adim = [i for i, k in enumerate(komutlar) if "isci.py --tek-tur" in k]
    sonda = [i for i, k in enumerate(komutlar) if "docker run -d" in k]
    assert len(isci_adim) == 1, komutlar
    assert goc[0] < isci_adim[0] < sonda[0], "sıra: göç → işçi → web"
    adim = adimlar[isci_adim[0]]
    assert "docker run --rm --network host" in adim["run"] and f"-e {db.DATABASE_URL_ENV}" in adim["run"]
    assert f"-e {sifre.ANAHTAR_ENV}" in adim["run"], "işçi de anahtarsız açılmaz (isci.py)"
    assert "set -euo pipefail" in adim["run"]
    assert str(adim.get("env", {}).get(db.DATABASE_URL_ENV, "")) == str(
        adimlar[sonda[0]]["env"][db.DATABASE_URL_ENV]), "işçi web'in DB'sine gitmeli"
    assert "worker_alive" in komutlar[sonda[0]], "sonda `worker_alive` alanını sormuyor"
    test_yml = _oku(os.path.join(KOK, ".github", "workflows", "_test.yml"))
    assert "isci.py" not in test_yml, "_test.yml değişmez: işçi orada işlev düzeyinde sınanıyor"


def test_ci_docker_job_is_blocking_and_time_boxed():
    is_ = _docker_isi()
    assert not is_.get("continue-on-error")
    assert not any(a.get("continue-on-error") for a in is_.get("steps", []))
    assert is_.get("timeout-minutes"), "zaman sınırı yok — asılı bir sonda işi saatlerce beklerdi"


# --------------------------------------------------------------------------
# README
# --------------------------------------------------------------------------

def test_the_readme_tells_developers_how_to_run_the_image_and_probe_health():
    metin = _oku(README)
    assert "docker build" in metin and "/health" in metin and "KROMIS_DATA_DIR" in metin
    # Faz 1 / 1: sondanın DB ölçütü ve testlerin Postgres'i nereden aldığı yazılı.
    assert "DATABASE_URL" in metin and "db_reachable" in metin
    assert "KROMIS_TEST_DATABASE_URL" in metin and "tools/test_ortami.py" in metin
    # Adım 6'dan beri mypy KESİCİ; "bilgi amaçlı" cümlesi bayattı.
    assert "şimdilik bilgi amaçlı" not in metin
    # Faz 1 / 9: şema `tools/goc.py` ile, açılışta değil.
    assert "tools/goc.py" in metin


# --------------------------------------------------------------------------
# KURULUM.md ve docs/isletme.md — işletme belgeleri (Faz 1 / 9)
# --------------------------------------------------------------------------

def test_the_install_guide_names_the_pre_deploy_migration_command_per_platform():
    """İşletmen göçü nereye koyacağını buradan öğreniyor: platformların komut
    adları ve compose akışı yazılı olmalı; `alembic upgrade head`i açılışa koyan
    bir yönerge kalmamalı."""
    metin = _oku(KURULUM)
    assert "tools/goc.py" in metin
    for platform in ("release_command", "Railway", "Render"):
        assert platform in metin, platform
    assert "service_completed_successfully" in metin or "goc" in metin
    assert "docs/isletme.md" in metin
    assert "tools/artik_dosya.py" in metin


def test_the_operations_doc_separates_the_three_backups_and_has_a_restore_drill():
    """docs/isletme.md: DB yedeği platformun (PITR / pg_dump), medya dizini AYRI,
    `KROMIS_SECRET_KEY` ÜÇÜNCÜ yerde; anahtar döndürme `tools/anahtar_dondur.py` ile;
    geri yükleme tatbikatı adımlı (Faz 5'in kalemi için iskelet)."""
    assert os.path.exists(ISLETME), "docs/isletme.md yok"
    metin = _oku(ISLETME)
    for parca in ("pg_dump", "PITR", sifre.ANAHTAR_ENV, "kullanicilar/", "tatbikat",
                  "tools/anahtar_dondur.py", "tools/goc.py", "tools/artik_dosya.py",
                  "release_command"):
        assert parca in metin, parca
    # Üç yedek, üç yer: anahtar ne DB'nin ne medyanın yanında.
    assert "ÜÇÜNCÜ" in metin or "üçüncü" in metin
    # Tatbikat adımları numaralı ve doğrulanacak şeyler yazılı.
    assert re.search(r"^\s*1\.\s", metin, re.M) and "doğrula" in metin.lower()
    # Aynı kural şablonda da: anahtar yedekten ayrı.
    assert "AYRI SAKLANIR" in _oku(ENV_EXAMPLE)


def test_the_install_guide_and_operations_doc_cover_the_two_process_deployment_and_retention():
    """Faz 2 / 10: platform başına iki süreç tablosu (Fly `[processes]` + `kill_timeout`, Railway/
    Render ikinci servis, compose `stop_grace_period`), R2 kova düzeni (özel, sürümleme, yaşam
    döngüsü, isteğe bağlı `rclone`), iş saklama (`KROMIS_IS_SAKLAMA_GUN`, referanssız girdi
    dizini), bayat düşürme ve ölü işçi satırı, yedek tablosunda `isler`/`isciler` ve platform
    sırları, geri yükleme tatbikatının kova adımı, işletme akışı (dağıt, geri al, sağlık, günlük)."""
    isletme = _oku(ISLETME)
    for parca in ("[processes]", "kill_timeout", "isci = \"python isci.py\"", "[[vm]]", "release_command",
                  "Railway", "Render", "stop_grace_period", "SIGTERM",
                  "sürümleme", "isler/", "rclone", "KROMIS_IS_SAKLAMA_GUN", isci.KALP_ESIGI_ENV,
                  "isciler", "worker_alive", platform_anahtari.ONEK, dosya.GIZLI_ENV,
                  "geri al", "olay=bakim", "boşalt"):
        assert parca in isletme, parca
    kurulum = _oku(KURULUM)
    for parca in ("kill_timeout", "[processes]", "KROMIS_IS_SAKLAMA_GUN", "sürümleme", "yaşam döngüsü",
                  "stop_grace_period"):
        assert parca in kurulum, parca
    # Şablon saklama değişkenini açıklıyor ve boş bırakıyor.
    satir = [a for a in _atamalar() if a[0] == isci.SAKLAMA_ENV]
    assert satir and satir[0][1] == "" and satir[0][2], satir


def test_the_install_guide_readme_and_operations_doc_cover_plans_credits_and_the_ledger_check():
    """Faz 3 / 7: kredi defterinin İŞLETME yüzü üç belgede birden yazılı olmalı — yoksa
    sahip 402'yi, filigranı ve `tutarsiz_kullanici`yi ilk canlı koşuda öğrenirdi.

    KURULUM.md 10. adım: üç plan, hibe değişkeni ve "hibeye tamamla", BYOK düşmez, 402,
    filigran değişkeni, admin kredi/plan, Marj araçları, tutarlılık ölçümü, canlı kontrol
    listesi. README (tr + en) kısa bölüm + KURULUM'a bağlantı. docs/isletme.md: defter yedeği
    satırı "tablo yok"tan "kapandı"ya döndü (§ 6), `kredi_hareketleri` yedek tablosunda (§ 2),
    iki uyarı olayı ve bakım turunun iki yeni sayısı (§ 6, § 9), geri yükleme tatbikatında
    defter adımı (§ 5). Şablon iki Faz 3 değişkenini açıklıyor ve boş bırakıyor (ALTYAPI'da
    zaten; burada belge ↔ şablon aynı adı kullanıyor mu)."""
    kurulum = _oku(KURULUM)
    for parca in ("Planlar ve kredi", planlar.FREE_AYLIK_HIBE_ENV, filigran.DOSYA_ENV,
                  "hibeye tamamla", "402", "rezerve", "iade", "GET /api/kredi", "Kredi",
                  "filigran", "kendi anahtarıyla üreten harcamaz", "kredi ekle", "Marj",
                  "tools/marj_raporu.py", "tools/tarife_kontrol.py",
                  "olay=defter.tutarsiz", "tutarsiz_kullanici", "hibe_satiri",
                  "Canlı kontrol listesi", "docs/isletme.md"):
        assert parca in kurulum, parca
    for ad, parcalar in ((README, ("Planlar ve kredi", "KURULUM.md", "Kredi", "Marj")),
                         (os.path.join(KOK, "README.en.md"), ("Plans and credits", "KURULUM.md", "Credits", "Margin"))):
        metin = _oku(ad)
        for parca in parcalar:
            assert parca in metin, f"{os.path.basename(ad)}: {parca}"
    isletme = _oku(ISLETME)
    assert "Faz 3 (tablo yok)" not in isletme, "defter yedeği satırı Faz 3'te kapandı, eski cümle kalmamalı"
    for parca in ("kredi_hareketleri", "olay=defter.tutarsiz", "olay=defter.asim",
                  "tutarsiz_kullanici", "hibe_satiri", "defter.tutarlilik", "SUM",
                  planlar.FREE_AYLIK_HIBE_ENV, filigran.DOSYA_ENV, "KURULUM.md", "duzeltme"):
        assert parca in isletme, parca
    # Şablon: iki değişken açıklamalı ve boş (bekçi ALTYAPI'yı ayrıca ölçüyor; bu, belgeyle aynı ad).
    for ad in (planlar.FREE_AYLIK_HIBE_ENV, filigran.DOSYA_ENV):
        satir = [a for a in _atamalar() if a[0] == ad]
        assert satir and satir[0][1] == "" and satir[0][2], (ad, satir)
