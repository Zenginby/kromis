"""Sentry — `services/hata_izleme.py` (Faz 2 / 9, K10): isteğe bağlı, tembel, redakte, PII kapalı.

Olaylar ağa DEĞİL bellek taşıyıcısına (`tasiyici=`, SDK'nın `transport=`
seçeneği): her test kendi listesine bakar ve sonunda `kapat()` istemciyi
çözer — sonraki test Sentry'siz başlar. "DSN yoksa modül ithal edilmez" ayrı
bir SÜREÇTE ölçülüyor: bu süreçte paket bir kez ithal edildi mi `sys.modules`
onu bir daha bırakmaz, iddia ancak taze bir yorumlayıcıda anlamlı.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import app as appmod
import version
from services import hata_izleme, istek_kimligi

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Sahte değerler `DUMMY` damgalı: sızıntı taraması (.gitleaks.toml) damgayı muaf tutar,
# başka her anahtar/DSN biçimli sabit geçmişte sonsuza dek bulgu olur.
DSN = "https://DUMMY0123456789@o1.ingest.sentry.io/1"
SAHTE_ANAHTAR = "sk-DUMMY" + "Q9w8E7r6" * 4
ADSIZ_DEGER = "DUMMYadsiz1234"


@pytest.fixture
def olaylar() -> Iterator[list[dict]]:
    """Sentry'yi sahte DSN + bellek taşıyıcısıyla kurar; testten sonra kapatır."""
    toplanan: list[dict] = []
    assert hata_izleme.kur(surec="test", ortam={hata_izleme.DSN_ENV: DSN,
                                                 hata_izleme.ORTAM_ENV: "deneme"},
                           tasiyici=toplanan.append) is True
    try:
        yield toplanan
    finally:
        hata_izleme.kapat()
        assert hata_izleme.etkin() is False


def _dokum(olay: dict) -> str:
    return json.dumps(olay, default=str)


def test_without_a_dsn_nothing_is_set_up_and_the_sdk_is_never_imported(tmp_path):
    """Taze süreç: `app` ithal edilip lifespan koşsa da `sentry_sdk` `sys.modules`ta yok (ağ yok, 2 MB yok)."""
    assert hata_izleme.kur(surec="test", ortam={}) is False
    assert hata_izleme.kur(surec="test", ortam={hata_izleme.DSN_ENV: "  "}) is False
    assert hata_izleme.etkin() is False
    ortam = {k: v for k, v in os.environ.items()
             if not k.startswith("KROMIS_NESNE_DEPO_") and k not in ("DATABASE_URL", hata_izleme.DSN_ENV)}
    ortam["KROMIS_DATA_DIR"] = str(tmp_path)
    betik = ("import sys, app\n"
             "from fastapi.testclient import TestClient\n"
             "with TestClient(app.app) as c:\n"
             "    c.get('/health')\n"
             "print('sentry_sdk' in sys.modules)\n")
    sonuc = subprocess.run([sys.executable, "-c", betik], cwd=KOK, env=ortam, capture_output=True,
                           text=True, encoding="utf-8", timeout=120)
    assert sonuc.returncode == 0, sonuc.stderr
    assert sonuc.stdout.strip() == "False", sonuc.stdout


def test_with_a_dsn_the_sdk_is_initialised_with_pii_off_no_request_bodies_and_the_app_release(olaylar):
    import sentry_sdk
    secenekler = sentry_sdk.get_client().options
    assert hata_izleme.etkin() is True
    assert secenekler["send_default_pii"] is False
    assert secenekler["max_request_body_size"] == "never"
    assert secenekler["release"] == f"kromis@{version.APP_VERSION}"
    assert secenekler["environment"] == "deneme"
    assert secenekler["before_send"] is hata_izleme.redakte
    assert secenekler["before_breadcrumb"] is hata_izleme.redakte
    entegrasyonlar = {type(e).__name__ for e in sentry_sdk.get_client().integrations.values()}
    assert {"FastApiIntegration", "StarletteIntegration", "SqlalchemyIntegration",
            "LoggingIntegration"} <= entegrasyonlar


def test_an_error_log_line_becomes_an_event_and_a_seeded_secret_is_scrubbed_from_it(olaylar):
    logging.getLogger("kromis.deneme").error("saglayici %s dedi; OPENAI_API_KEY=%s", SAHTE_ANAHTAR, ADSIZ_DEGER)
    import sentry_sdk
    sentry_sdk.flush()
    (olay,) = olaylar
    dokum = _dokum(olay)
    assert SAHTE_ANAHTAR not in dokum and ADSIZ_DEGER not in dokum, dokum
    assert "[REDACTED_API_KEY]" in dokum
    assert olay["tags"]["surec"] == "test" and olay["release"] == f"kromis@{version.APP_VERSION}"
    assert olay.get("user") in (None, {}) and "request" not in olay, "PII ve gövde yok"


def test_breadcrumbs_and_exception_values_are_scrubbed_too(olaylar):
    import sentry_sdk
    sentry_sdk.add_breadcrumb(message=f"sorgu {SAHTE_ANAHTAR}", data={"param": SAHTE_ANAHTAR})
    try:
        raise RuntimeError(f"istisna {SAHTE_ANAHTAR}")
    except RuntimeError:
        hata_izleme.istisna_bildir()
    sentry_sdk.flush()
    (olay,) = olaylar
    dokum = _dokum(olay)
    assert SAHTE_ANAHTAR not in dokum, dokum
    kirintilar = olay["breadcrumbs"]["values"]
    assert any("[REDACTED_API_KEY]" in (k.get("message") or "") for k in kirintilar)
    assert olay["exception"]["values"][0]["value"] == "istisna [REDACTED_API_KEY]"


def test_the_scrubber_walks_nested_structures_and_leaves_shape_and_innocent_values_alone():
    olay = {"message": f"a {SAHTE_ANAHTAR}", "extra": {"liste": [SAHTE_ANAHTAR, 3, None], "demet": (SAHTE_ANAHTAR,)},
            "tags": {"surec": "web"}, "sayi": 5}
    temiz = hata_izleme.redakte(olay, {"ipucu": 1})
    assert SAHTE_ANAHTAR not in _dokum(temiz)
    assert temiz["extra"]["liste"][1:] == [3, None] and isinstance(temiz["extra"]["demet"], tuple)
    assert temiz["tags"] == {"surec": "web"} and temiz["sayi"] == 5


def test_the_worker_job_scope_tags_events_with_the_job_and_user_id_and_is_isolated(olaylar):
    import sentry_sdk
    is_id, kullanici_id = uuid.uuid4(), uuid.uuid4()
    with hata_izleme.is_baglami(is_id, kullanici_id):
        sentry_sdk.capture_message("is icinde")
    sentry_sdk.capture_message("is disinda")
    sentry_sdk.flush()
    icinde, disinda = olaylar
    assert icinde["tags"]["is_id"] == str(is_id) and icinde["tags"]["kullanici_id"] == str(kullanici_id)
    assert "is_id" not in disinda.get("tags", {}), "kapsam iş bitince kapanır"


def test_a_route_exception_reaches_sentry_tagged_with_the_request_id(olaylar, monkeypatch):
    from routers import saglik

    def _patla(d):
        raise RuntimeError("sonda patladi")
    monkeypatch.setattr(saglik, "veri_dizini_yazilabilir", _patla)
    cevap = TestClient(appmod.app, raise_server_exceptions=False).get(
        "/health", headers={istek_kimligi.BASLIK: "sentry-istek"})
    assert cevap.status_code == 500
    import sentry_sdk
    sentry_sdk.flush()
    hatalar = [o for o in olaylar if "exception" in o]
    assert hatalar, olaylar
    olay = hatalar[-1]
    assert olay["exception"]["values"][-1]["value"] == "sonda patladi"
    assert olay["tags"]["istek_id"] == "sentry-istek" and olay["tags"]["surec"] == "test"


def test_a_bad_dsn_is_logged_and_does_not_stop_the_process():
    yakalanan: list[logging.LogRecord] = []

    class _Y(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            yakalanan.append(record)
    gunlukcu = logging.getLogger("kromis.sentry")
    gunlukcu.disabled = False
    y = _Y()
    gunlukcu.addHandler(y)
    try:
        assert hata_izleme.kur(surec="test", ortam={hata_izleme.DSN_ENV: "bu-bir-dsn-degil"}) is False
    finally:
        gunlukcu.removeHandler(y)
        hata_izleme.kapat()
    assert hata_izleme.etkin() is False
    assert any(r.levelno == logging.ERROR and getattr(r, "olay", "") == "sentry.hata" for r in yakalanan)


def test_the_no_op_helpers_do_nothing_when_sentry_is_off():
    assert hata_izleme.etkin() is False
    hata_izleme.etiketle(istek_id="x")
    hata_izleme.istisna_bildir()
    with hata_izleme.is_baglami(uuid.uuid4(), uuid.uuid4()):
        pass
    hata_izleme.kapat()


def test_the_env_names_are_the_sdks_own_and_the_dependency_is_pinned_in_the_runtime_file():
    assert (hata_izleme.DSN_ENV, hata_izleme.ORTAM_ENV) == ("SENTRY_DSN", "SENTRY_ENVIRONMENT")
    with open(os.path.join(KOK, "requirements.txt"), encoding="utf-8") as f:
        satirlar = [s.strip() for s in f if s.strip() and not s.startswith("#")]
    assert "sentry-sdk==2.*" in satirlar, satirlar
