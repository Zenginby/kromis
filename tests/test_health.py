"""`GET /health` — konteynerin sondası (Faz 0 / Adım 8, routers/saglik.py).

Sonda üç şey söylüyor: ayakta mı (200/503), hangi sürüm, veri dizinine
yazılabiliyor mu. Üçüncüsü asıl mesele: konteynerde uygulama açılır, `/` 200
verir ve ilk üretimde `history.json` yazılamaz — bind-mount başka kullanıcıya
ait, birim salt okunur ya da disk dolu. Sonda bunu 200 değil 503 ile söyler ki
`HEALTHCHECK` ve orkestratör gövdeyi okumadan anlasın; gövde yine de tam döner.

TESTLER ROOT'TA DA ANLAMLI: bu takım hem CI koşucusunda hem Claude Code
konteynerinde çoğu zaman root olarak koşuyor ve root için `chmod` izin bitleri
bağlayıcı değil. Yazılamayan dizin bu yüzden İKİ yolla üretiliyor: dizin yerine
düz bir DOSYA (`mkstemp` → `NotADirectoryError`) ve hiç var olmayan yol —
ikisi de root'ta kırmızıya döner. Klasik `chmod 0o500` senaryosu ayrıca var
ama root'ta ve Windows'ta atlanıyor; sondanın `os.access` yerine gerçek yazım
denemesi kullanmasının gerekçesi de tam olarak bu (routers/saglik.py).
"""
from __future__ import annotations

import os
import re
import stat
import sys

import pytest
from fastapi.testclient import TestClient

import version
from routers import saglik


def _client() -> TestClient:
    # `with` YOK, bilerek: sonda lifespan'a muhtaç olmamalı — açılış adımı
    # (dizin açma, yedek) patlasa bile `/health` cevap vermeli ve o durumda
    # "yazılamıyor" demeli. `app` burada ithal ediliyor (conftest gerekçesi).
    import app as appmod
    return TestClient(appmod.app)


def test_health_is_200_with_the_documented_body_when_the_data_dir_is_writable(tmp_path, dizinler):
    dizinler(data_dir=str(tmp_path))
    cevap = _client().get("/health")
    assert cevap.status_code == 200
    assert cevap.json() == {"ok": True, "version": version.APP_VERSION,
                            "data_dir_writable": True}


def test_health_reports_the_apps_version_constant_not_a_second_literal(tmp_path, dizinler):
    """Sürüm `version.APP_VERSION`dan; rota kendi literalini taşımaz
    (deponun "sürüm literali tek yerde" kuralı, tests/test_version.py)."""
    dizinler(data_dir=str(tmp_path))
    surum = _client().get("/health").json()["version"]
    assert surum == version.APP_VERSION
    assert re.fullmatch(r"\d+\.\d+\.\d+", surum), surum


def test_health_leaves_no_trace_in_the_data_dir(tmp_path, dizinler):
    """Sonda her 30 sn'de bir koşacak; iz bıraksaydı `/data` geçici dosyayla dolardı."""
    dizinler(data_dir=str(tmp_path))
    istemci = _client()
    for _ in range(3):
        assert istemci.get("/health").status_code == 200
    assert os.listdir(tmp_path) == []


def test_health_is_503_when_the_data_dir_is_a_regular_file(tmp_path, dizinler):
    """Root'ta da çalışan "yazılamaz" senaryosu: dizin yerine dosya."""
    dosya = tmp_path / "dizin-degil"
    dosya.write_text("", encoding="utf-8")
    dizinler(data_dir=str(dosya))
    cevap = _client().get("/health")
    assert cevap.status_code == 503
    assert cevap.json() == {"ok": False, "version": version.APP_VERSION,
                            "data_dir_writable": False}


def test_health_is_503_when_the_data_dir_does_not_exist_and_does_not_create_it(tmp_path, dizinler):
    """Dizini `_lifespan` açar, sonda AÇMAZ: açamayan bir açılışı sonda gizlemesin."""
    yok = tmp_path / "yok"
    dizinler(data_dir=str(yok))
    cevap = _client().get("/health")
    assert cevap.status_code == 503
    assert cevap.json()["data_dir_writable"] is False
    assert not yok.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX izin bitleri")
@pytest.mark.skipif(getattr(os, "geteuid", lambda: 0)() == 0,
                    reason="root için izin bitleri bağlayıcı değil")
def test_health_is_503_when_the_data_dir_is_read_only(tmp_path, dizinler):
    salt = tmp_path / "salt"
    salt.mkdir()
    salt.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        dizinler(data_dir=str(salt))
        cevap = _client().get("/health")
        assert cevap.status_code == 503
        assert cevap.json()["data_dir_writable"] is False
    finally:
        salt.chmod(stat.S_IRWXU)


def test_health_is_not_cacheable(tmp_path, dizinler):
    """Bir ara vekil bu cevabı saklarsa sonda dakikalarca bayat "sağlıklı" okur."""
    dizinler(data_dir=str(tmp_path))
    assert _client().get("/health").headers["cache-control"] == "no-store"


def test_the_probe_helper_answers_from_the_filesystem_alone(tmp_path):
    """Yardımcı uygulamadan bağımsız; `Dockerfile` dışında da (bir betikten) kullanılabilir."""
    assert saglik.veri_dizini_yazilabilir(str(tmp_path)) is True
    dosya = tmp_path / "dosya"
    dosya.write_text("", encoding="utf-8")
    assert saglik.veri_dizini_yazilabilir(str(dosya)) is False
    assert saglik.veri_dizini_yazilabilir(str(tmp_path / "yok")) is False
    assert sorted(os.listdir(tmp_path)) == ["dosya"]
