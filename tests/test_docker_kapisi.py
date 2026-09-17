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

`.dockerignore` da sınanıyor: `tests/`, `android/`, `docs/`, `.venv/` bağlama
girerse imaj şişer ve her test değişikliği katman önbelleğini boşa düşürür;
`.env`/`output/` girerse yerel sır ve veri imaj katmanına yazılır.
"""
from __future__ import annotations

import os
import re
import shlex

import yaml

import catalog
from services import cerez, db, koken, posta

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCKERFILE = os.path.join(KOK, "Dockerfile")
DOCKERIGNORE = os.path.join(KOK, ".dockerignore")
COMPOSE = os.path.join(KOK, "compose.yaml")
ENV_EXAMPLE = os.path.join(KOK, ".env.example")
CI_YML = os.path.join(KOK, ".github", "workflows", "ci.yml")
README = os.path.join(KOK, "README.md")


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
    eksik = {"tests", "android", "docs", ".venv", "node_modules", ".git",
             ".env", "output", "assets", "hata.log"} - _dislananlar()
    assert not eksik, f".dockerignore'da yok: {sorted(eksik)}"


def test_dockerignore_keeps_everything_the_app_serves_or_imports():
    """`COPY . /app` bağlamın tamamını aldığı için dışlama listesi kaynağı
    yutmamalı: static/ ve bundled/ olmadan uygulama açılır ama `/` 500 verir."""
    yasak = {"static", "bundled", "routers", "services", "requirements.txt",
             "app.py", "LICENSE", "NOTICE"} & _dislananlar()
    assert not yasak, f".dockerignore uygulamanın parçasını dışlıyor: {sorted(yasak)}"
    # `*.py` gibi bir kalıp da aynı sonucu verirdi; `**/*.md` ise
    # `bundled/prompts/*.md`yi (Yönetmen personası) yutardı — kök `*.md` yutmaz.
    assert not any(k in ("*.py", "*", "**/*.md", "**/*") for k in _dislananlar())
    assert os.path.exists(os.path.join(KOK, "bundled", "prompts", "prompt-yonetmeni.md"))


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
# `KROMIS_GUVENLI_CEREZ` (services/cerez.py). Adlar KAYNAKTAN, elle değil.
ALTYAPI = {"KROMIS_DATA_DIR", "PORT", db.DATABASE_URL_ENV, koken.KOKEN_ENV,
           posta.POSTA_ENV, posta.GONDEREN_ENV, posta.RESEND_ANAHTAR_ENV, cerez.GUVENLI_ENV}


def _katalog_adlari() -> set[str]:
    """Sağlayıcı değişken adları — KATALOGDAN, elle değil."""
    adlar = {c.key_env for c in catalog.CREDENTIALS}
    adlar |= {c.url_env for c in catalog.CREDENTIALS if c.url_env}
    adlar |= {m.wire_from_env for m in catalog.CHAT_MODELS if m.wire_from_env}
    return adlar


def test_env_example_lists_exactly_the_infra_vars_and_the_catalog_names():
    adlar = [ad for ad, _, _ in _atamalar()]
    assert len(adlar) == len(set(adlar)), "yinelenen ad"
    beklenen = ALTYAPI | _katalog_adlari()
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
    """Uygulama anahtarları `credentials.env`den okur (azure_client.read_env_values),
    `os.environ`dan değil; şablon bunu söylemezse `.env`e anahtar yazan kullanıcı
    'neden çalışmıyor' der."""
    metin = _oku(ENV_EXAMPLE)
    assert "SÜREÇ ORTAMINDAN" in metin and "credentials.env" in metin


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
    assert set(servisler) == {"kromis", "postgres"}, list(servisler)
    servis = servisler["kromis"]
    assert servis.get("build") == ".", "imaj yerelden derlenmeli, bir kayıt defterinden çekilmemeli"
    assert "image" not in servis
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
    assert "alembic" not in kod, (
        "göç compose'da koşturuluyor — açılışta göç yok (K6), 9. görevin `goc` servisi")


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
    adimlar = [a for a in is_.get("steps", []) if "docker run" in str(a.get("run", ""))]
    assert len(adimlar) == 1, adimlar
    adim = adimlar[0]
    assert "--network host" in adim["run"]
    assert f"-e {db.DATABASE_URL_ENV}" in adim["run"]
    url = str(adim.get("env", {}).get(db.DATABASE_URL_ENV, ""))
    assert url.startswith("postgresql+psycopg://") and "localhost:5432" in url, url
    # `curl -f` duruyor: 503 hâlâ kırmızı, sonda gevşetilmedi.
    assert "curl -fsS" in adim["run"] and "/health" in adim["run"]


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
