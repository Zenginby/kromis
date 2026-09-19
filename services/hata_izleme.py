# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Hata izleme — Sentry, yalnız `SENTRY_DSN` verilmişse; redakte, PII kapalı, gövde yok (Faz 2 / 9, K10).

İSTEĞE BAĞLI ve TEMBEL: `sentry_sdk` bu modülün ÜSTÜNDE ithal edilmez.
`kur()` DSN görmezse `False` döner ve paket hiç ithal edilmez — dondurulmuş
kabuk, testler ve DSN'siz bir dağıtım ne ağa çıkar ne 2 MB'lık paketi yükler
(bekçisi tests/test_sentry.py: DSN yokken `sys.modules`ta `sentry_sdk` yok).
Paket `requirements.txt`te yine de duruyor (saf Python; imajda hazır olsun,
DSN'i panelden girmek yeni imaj istemesin).

İKİ SÜREÇ, TEK KURULUM: web (`app._lifespan`) ve işçi (`isci.py`) aynı
`kur(surec=…)`u çağırır; `surec` etiketi (`web`/`isci`) Sentry'de ikisini
ayırır. Sürüm `version.APP_VERSION`dan (`kromis@0.x.y`) — ikinci literal yok;
ortam `SENTRY_ENVIRONMENT` (SDK'nın kendi adı; `production`/`staging`).

NE GİTMEZ: `send_default_pii=False` (çerez, IP, `Authorization` yok),
`max_request_body_size="never"` (istek gövdesi HİÇ — prompt kullanıcı verisi),
`before_send` ve `before_breadcrumb` olayın İÇİNDEKİ HER DİZEYİ
`errlog.redact_secrets`ten geçirir — mesaj, istisna değeri, iz, breadcrumb
(SQLAlchemy entegrasyonunun breadcrumb'ı sorgu parametresi taşıyabilir; belge
§9 risk). Aynı işlev, ikinci redaksiyon kopyası yok (services/gunluk.py'nin
kararı).

BOZUK DSN uygulamayı DURDURMAZ: `kur` yakalar, `kromis.sentry` günlüğüne
ERROR düşürür, `False` döner — hata izlemenin yokluğu üründen önemli değil
(`KROMIS_SECRET_KEY`in tersi; oradaki gerekçe burada yok).

İŞÇİ BAĞLAMI: `is_baglami(is_id, kullanici_id)` iş başına yalıtılmış bir
Sentry kapsamı açar ve `is_id` etiketini koyar (belge: `set_tag(is_id)`);
web'de isteğin kapsamını Starlette entegrasyonu açar, `istek_kimligi`
`etiketle(istek_id=…)` ile kimliği ekler. Bir yerde Sentry kurulu değilse bu
işlevlerin hepsi HİÇBİR ŞEY yapmaz — çağıranlar `etkin()`e bakmaz.

Kullanıcıya konuşmaz (tests/test_i18n.py sınıflandırması): tek metni
operatöre giden kurulum hatası satırı.
"""
from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Callable, Iterator, Mapping
from typing import Any

import errlog
import version
from services import gunluk

__all__ = ["DSN_ENV", "ORTAM_ENV", "dsn", "kur", "kapat", "etkin", "redakte", "etiketle",
           "is_baglami", "istisna_bildir"]

# Sentry SDK'nın kendi adları — sahibin panelden kopyaladığı DSN olduğu gibi girer.
DSN_ENV = "SENTRY_DSN"
ORTAM_ENV = "SENTRY_ENVIRONMENT"

_gunluk = logging.getLogger("kromis.sentry")
_ETKIN = False


def dsn(ortam: Mapping[str, str] | None = None) -> str | None:
    """`SENTRY_DSN` — boşsa `None`."""
    ortam = os.environ if ortam is None else ortam
    return (ortam.get(DSN_ENV) or "").strip() or None


def etkin() -> bool:
    """Bu süreçte Sentry kurulu mu (`kur` DSN'le başarılı döndü mü)?"""
    return _ETKIN


def _redakte(veri: Any) -> Any:
    if isinstance(veri, str):
        return errlog.redact_secrets(veri)
    if isinstance(veri, dict):
        return {k: (gunluk.MASKE if isinstance(k, str) and gunluk.GIZLI_AD.match(k) else _redakte(v))
                for k, v in veri.items()}
    if isinstance(veri, list):
        return [_redakte(v) for v in veri]
    if isinstance(veri, tuple):
        return tuple(_redakte(v) for v in veri)
    return veri



def redakte(veri: Any, _ipucu: Any = None) -> Any:
    """Olayın/breadcrumb'ın içindeki HER dizeyi `errlog.redact_secrets`ten geçirir; yapı aynen kalır.

    `before_send` ve `before_breadcrumb` imzası `(olay, ipucu)`; ikinci
    parametre okunmuyor. Sözlük ve listelerin içine inilir (istisna değerleri
    `exception.values[].value`, iz çerçeveleri `frames[].vars`, `breadcrumbs.
    values[].message/data`, `extra`, `tags` — hepsi aynı yürüyüşten geçer).
    Adı KEY/TOKEN/SECRET ile biten sözlük anahtarının değeri biçimine
    bakılmadan maskelenir (`gunluk.GIZLI_AD`, aynı kural).

    `logentry.params` DÜŞER (ölçüldü, tests/test_sentry.py): `logger.error(
    "OPENAI_API_KEY=%s", deger)` satırında `formatted` `AD=değer` biçimiyle
    yakalanır ama `params` listesinde değer ADSIZ durur ve hiçbir desen onu
    tanımaz. Sentry gruplamayı `message` (biçim dizesi) ile yapıyor; `params`
    yalnız gösterim, kaybı yok.
    """
    if isinstance(veri, dict) and isinstance(veri.get("logentry"), dict):
        veri = {**veri, "logentry": {k: v for k, v in veri["logentry"].items() if k != "params"}}
    return _redakte(veri)


def kur(*, surec: str, ortam: Mapping[str, str] | None = None,
        tasiyici: Callable[[Any], None] | None = None) -> bool:
    """DSN varsa `sentry_sdk.init(...)`; yoksa hiçbir şey ithal etmeden `False`.

    `tasiyici` test için: SDK'nın `transport=` seçeneği — olaylar ağa değil bu
    işleve gider (tests/test_sentry.py bellek taşıyıcısı). Üretimde `None`.
    """
    global _ETKIN
    adres = dsn(ortam)
    if adres is None:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        ortam_adi = (ortam if ortam is not None else os.environ).get(ORTAM_ENV) or None
        sentry_sdk.init(
            dsn=adres,
            release=f"kromis@{version.APP_VERSION}",
            environment=ortam_adi,
            send_default_pii=False,
            max_request_body_size="never",
            before_send=redakte,
            before_breadcrumb=redakte,
            # INFO satırları breadcrumb (istek/iş olayları hatanın öncesini anlatır),
            # ERROR ve üstü olay — `logger.exception` Sentry'ye de düşer.
            integrations=[StarletteIntegration(), FastApiIntegration(), SqlalchemyIntegration(),
                          LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
            transport=tasiyici,
        )
        sentry_sdk.set_tag("surec", surec)
    except Exception:
        _gunluk.exception("sentry kurulamadi; hata izleme kapali", extra={"olay": "sentry.hata"})
        _ETKIN = False
        return False
    _ETKIN = True
    return True


def kapat() -> None:
    """Kurulumu geri alır (testler): istemci çözülür, bayrak düşer. Kurulmamışsa hiçbir şey yapmaz."""
    global _ETKIN
    if _ETKIN:
        import sentry_sdk
        sentry_sdk.flush(timeout=0)
        sentry_sdk.get_global_scope().set_client(None)
    _ETKIN = False


def etiketle(**etiketler: Any) -> None:
    """Etkin kapsama etiket(ler) koyar; Sentry kurulu değilse hiçbir şey yapmaz."""
    if not _ETKIN:
        return
    import sentry_sdk
    for ad, deger in etiketler.items():
        sentry_sdk.set_tag(ad, str(deger))


@contextlib.contextmanager
def is_baglami(is_id: Any, kullanici_id: Any) -> Iterator[None]:
    """İşçide iş başına yalıtılmış kapsam + `is_id`/`kullanici_id` etiketi; kurulu değilse boş."""
    if not _ETKIN:
        yield
        return
    import sentry_sdk
    with sentry_sdk.isolation_scope() as kapsam:
        kapsam.set_tag("is_id", str(is_id))
        kapsam.set_tag("kullanici_id", str(kullanici_id))
        yield


def istisna_bildir() -> None:
    """Yakalanmış istisnayı (etkin `except` bloğundan) Sentry'ye gönderir; kurulu değilse hiçbir şey."""
    if not _ETKIN:
        return
    import sentry_sdk
    sentry_sdk.capture_exception()
