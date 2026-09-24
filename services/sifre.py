# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Sağlayıcı anahtarlarının şifrelenmesi — Fernet, HKDF'li alt anahtar, döndürme (Faz 1 / 7).

`saglayici_kimlikleri.sifreli_deger` bu modülün ürettiği Fernet jetonu; düz
metin sütunu YOK. Kök anahtar `KROMIS_SECRET_KEY` (32 bayt, urlsafe base64):

* ZORUNLU ve sessiz varsayılan YOK. Anahtar yoksa `sifreci()` `AnahtarHatasi`
  fırlatır ve `app._lifespan` (DATABASE_URL verilmiş, yani web) uygulamayı
  AÇMAZ. Gömülü bir varsayılan anahtar, "şifreli" sütunu herkesin okuyabildiği
  bir sütuna çevirirdi — belge §7'nin tek satırlık kuralı.
* HKDF ile "kimlik" AMAÇLI alt anahtar: Fernet'e kök anahtarın kendisi değil,
  `info=b"kromis:kimlik"` ile türetilen 32 bayt veriliyor. Aynı kök bir gün
  başka bir amaçla da (oturum imzası, dışa aktarma) kullanılırsa iki kullanım
  aynı anahtarı paylaşmaz; türetme ucuz ve `lru_cache`li.
* DÖNDÜRME `MultiFernet` ile: değişken virgülle ayrılmış bir LİSTE olabilir,
  EN YENİSİ BAŞTA. Yazım hep ilk anahtarla; okuma listedeki herhangi biriyle
  (`MultiFernet.decrypt` sırayla dener). Yeni anahtar başa eklenir → dağıtım
  → `depo_kimlik_bilgisi.dondur` eski satırları yeniden şifreler → eski
  anahtar listeden düşer.
* `anahtar_surumu` SIRA NUMARASI DEĞİL, PARMAK İZİ: kök anahtarın SHA-256'sının
  ilk 4 baytı (31 bit, `integer` sütuna sığar). Sıra numarası liste değişince
  kayar (yeni anahtar başa gelir, eskisi sondan düşer) ve satırdaki sayı
  anlamını yitirirdi; parmak izi anahtara bağlı, listeye değil. Operatör
  `SELECT anahtar_surumu, count(*)` ile hangi anahtarın hâlâ kullanımda
  olduğunu görür, `parmak_izi()` ile elindeki anahtarınkini hesaplar.

Bu modül KONUŞMAZ (kullanıcıya): hataları operatöre gidiyor — uvicorn günlüğü
ve `hata.log`. Türkçe, ama komutlar ASCII (cp1252 konsol dersi, conftest).
"""
from __future__ import annotations

import base64
import functools
import hashlib
import os
from collections.abc import Mapping

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# Ortam değişkeninin adı — `.env.example`, `compose.yaml`, CI ve `app._lifespan`
# aynı adı buradan okur (bekçisi tests/test_docker_kapisi.py).
ANAHTAR_ENV = "KROMIS_SECRET_KEY"
ANAHTAR_BAYT = 32
# HKDF `info`: alt anahtarın AMACI. Değişirse hiçbir eski satır okunamaz.
_AMAC = b"kromis:kimlik"

# Operatörün anahtarı nasıl üreteceği — hata mesajı ve `.env.example` aynı komutu gösterir.
URETIM_KOMUTU = ('python -c "import secrets,base64;'
                 'print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"')


class AnahtarHatasi(RuntimeError):
    """`KROMIS_SECRET_KEY` yok ya da biçimi yanlış — uygulama bununla AÇILMAZ."""


class SifreHatasi(RuntimeError):
    """Bir satır listedeki hiçbir anahtarla çözülemedi (anahtar listeden düşmüş ya da veri bozuk)."""


def parmak_izi(kok: bytes) -> int:
    """Kök anahtarın 31 bitlik parmak izi — `anahtar_surumu` sütununun değeri."""
    return int.from_bytes(hashlib.sha256(kok).digest()[:4], "big") & 0x7FFFFFFF


def _turet(kok: bytes) -> bytes:
    """Kök → "kimlik" amaçlı Fernet anahtarı (32 bayt, urlsafe base64)."""
    alt = HKDF(algorithm=hashes.SHA256(), length=ANAHTAR_BAYT, salt=None, info=_AMAC).derive(kok)
    return base64.urlsafe_b64encode(alt)


def kok_anahtarlar(ham: str) -> list[bytes]:
    """Virgülle ayrılmış base64 listesini çözer; boş ya da bozuk öğe `AnahtarHatasi`."""
    parcalar = [p.strip() for p in ham.split(",")]
    if not ham.strip() or not all(parcalar):
        raise AnahtarHatasi(
            f"{ANAHTAR_ENV} verilmedi ya da bos: saglayici anahtarlari bu anahtarla "
            f"sifrelenir ve onsuz uygulama ACILMAZ (sessiz varsayilan anahtar yok). "
            f"Uret: {URETIM_KOMUTU}")
    kokler: list[bytes] = []
    for sira, parca in enumerate(parcalar, 1):
        try:
            kok = base64.urlsafe_b64decode(parca + "=" * (-len(parca) % 4))
        except (ValueError, TypeError) as e:
            raise AnahtarHatasi(
                f"{ANAHTAR_ENV} gecersiz: {sira}. oge base64 degil ({type(e).__name__}). "
                f"Her oge 32 baytin urlsafe base64'u olmali; uret: {URETIM_KOMUTU}") from e
        if len(kok) != ANAHTAR_BAYT:
            raise AnahtarHatasi(
                f"{ANAHTAR_ENV} gecersiz: {sira}. oge {len(kok)} bayt cozuldu, {ANAHTAR_BAYT} "
                f"olmali. Uret: {URETIM_KOMUTU}")
        kokler.append(kok)
    return kokler


class Sifreci:
    """Bir anahtar LİSTESİYLE şifreler/çözer; ilk anahtar yazar, hepsi okur."""

    def __init__(self, kokler: list[bytes]) -> None:
        if not kokler:
            raise AnahtarHatasi(f"{ANAHTAR_ENV} bos liste")
        self._coklu = MultiFernet([Fernet(_turet(k)) for k in kokler])
        self.surumler = [parmak_izi(k) for k in kokler]
        # Yazımda satıra yazılan sürüm — listenin İLK (en yeni) anahtarı.
        self.surum = self.surumler[0]

    def sifrele(self, deger: str) -> bytes:
        return self._coklu.encrypt(deger.encode("utf-8"))

    def coz(self, jeton: bytes) -> str:
        try:
            return self._coklu.decrypt(jeton).decode("utf-8")
        except InvalidToken as e:
            raise SifreHatasi(
                f"satir listedeki hicbir anahtarla cozulemedi: bu satiri sifreleyen anahtar "
                f"{ANAHTAR_ENV} listesinden dusmus olabilir (eski anahtari listenin SONUNA "
                f"ekleyip `depo_kimlik_bilgisi.dondur` ile yeniden sifreleyin)") from e

    def dondur(self, jeton: bytes) -> bytes:
        """Eski bir anahtarla yazılmış jetonu İLK anahtarla yeniden şifreler (düz metni açmadan döndürmez)."""
        try:
            return self._coklu.rotate(jeton)
        except InvalidToken as e:
            raise SifreHatasi("dondurulecek satir listedeki hicbir anahtarla cozulemedi") from e

    def guncel_mi(self, surum: int) -> bool:
        """Satırdaki parmak izi listenin ilk anahtarına mı ait? Değilse `dondur` gerekir."""
        return surum == self.surum


@functools.lru_cache(maxsize=4)
def _kur(ham: str) -> Sifreci:
    return Sifreci(kok_anahtarlar(ham))


def sifreci(ortam: Mapping[str, str] | None = None) -> Sifreci:
    """Ortamdaki `KROMIS_SECRET_KEY`den şifreci; aynı değer için aynı nesne (türetme bir kez).

    Her çağrıda ortam OKUNUR (önbellek değere göre): testler `monkeypatch.setenv`
    ile anahtar değiştirip döndürmeyi sınayabilsin. Yoksa/bozuksa `AnahtarHatasi`.
    """
    kaynak = os.environ if ortam is None else ortam
    return _kur(kaynak.get(ANAHTAR_ENV, ""))


def dogrula_ortam() -> None:
    """Açılış kapısı: anahtar yoksa ya da bozuksa `AnahtarHatasi` — `app._lifespan` çağırır."""
    sifreci()
