# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Dosya deposu soyutlaması — yerel disk ya da S3/R2 kovası, aynı arayüz (Faz 2 / 2).

NEDEN VAR: sahibin yığınında uygulama ve işçi AYRI süreçler, ayrı makineler,
ORTAK DİSKLERİ YOK (docs/faz2-kuyruk-anahtarlar-depolama.md, giriş). İşçinin
(3. görev) ürettiği MP4 işçinin diskine düşerse `GET /output/{filename}` onu hiç
göremez. Ortak zemin nesne depolama; yerel disk compose, test ve dondurulmuş
kabuk için KALIR. Medyanın YERİ değişir, rotaların şekli değişmez.

İKİ UYGULAMA, TEK SÖZLEŞME (`Depo`):

* `YerelDepo(kok)` — bugünkü disk. `url()` `None` döner, rota `FileResponse`a
  düşer; davranış Faz 1'inkiyle bayt bayt aynı.
* `NesneDepo(istemci, kok)` — `services/nesne_depo.S3Istemci` üstünde. `url()`
  15 dakikalık ön imzalı GET verir, rota **302** döner (K7): uygulama süreci
  medya baytı taşımaz, `<video>`nun aralık istekleri doğrudan R2'ye gider.

YOL ↔ ANAHTAR. Bütün yöntemler `yol` alır ve `yol` rotaların bugün yazdığı
şeyin kendisidir: `os.path.join(ayarlar.output_dir, filename)`, yani
`<data_dir>/kullanicilar/<uuid>/output/<ad>`. Kovadaki anahtar bu yolun
`data_dir`e (`kok`) GÖRELİ hâli, `/` ayraçlı: `kullanicilar/<uuid>/output/<ad>`
— belge §2'nin "anahtar = bugünkü yol" kararı. Çeviriyi depo yapar
(`NesneDepo._anahtar`), rota yapmaz: `ayar.Ayarlar.output_dir`/`assets_dir`
okuyan 42 rota ve iki depo modülü DEĞİŞMEDEN kalır (Faz 0 / 4'ün vaadi bir kez
daha), `output_dir`in ANLAMI kovada "önek" olur. Göreli bir `yol` da geçer
(`kullanicilar/...`): araçlar ve işçi anahtarla konuşur, `YerelDepo` onu
`kok`a ekler. `kok` DIŞINDA mutlak bir yol kovaya çevrilemez — `DosyaHatasi`,
çünkü o bir programlama hatasıdır (testlerde `dizinler(output_dir=tmp_path)`
yalnız `YerelDepo` ile anlamlı ve orada mutlak yol olduğu gibi kullanılır).

SEÇİM ORTAMDAN (`depo_kur`): `KROMIS_NESNE_DEPO_URL`, `_KOVA`, `_ANAHTAR_ID`,
`_GIZLI` dördü de doluysa `NesneDepo`; dördü de boşsa `YerelDepo`; YARISI
doluysa `YapilandirmaHatasi` — uygulama AÇILMAZ. Sessizce yerel diske düşen
bir dağıtım, işçi geldiğinde "video üretildi ama görünmüyor" olurdu; yarım
yapılandırma ilk saniyede görünmeli (`KROMIS_SECRET_KEY`nin aynı duruşu).
`_BOLGE` isteğe bağlı, R2 için `auto`.

`app.state.dosya` İTHAL ANINDA kurulur (`app.py`, `ayarlar` gibi), lifespan'da
DEĞİL — belgeden sapma, gerekçesi aynı: `TestClient(app)`i `with`siz kullanan
178 çağrı lifespan koşturmaz, nesne orada kurulsa her rota 500 verirdi.
Rotalar `Depends(dosya.depo)` ile alır; testler `app.state.dosya`yı yamalar.

VAR MI SORUSU HER İKİ DEPODA SORULUR: servis rotaları satır VE nesne ister
(Faz 1 / 5'in "satırı silinmiş bir dosya sunulmaz, dosyası silinmiş bir satır
404" sözleşmesi). Kovada bu bir HEAD — küçük resim başına bir tur. Kabul
edilen bedel: 302'nin `Cache-Control: private, max-age=600`ü aynı görselin
yeniden yüklenmesini tarayıcıda tutar; ölçülüp ağır bulunursa `var()` çağrısı
rotadan tek satırla düşer, sözleşme belgeye yazılır.

MODÜL KONUŞMAZ: hatalar birer kod/`DosyaHatasi`; 404 metnini rota kurar.
"""
from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from typing import Protocol

import httpx
from fastapi import Request

from services import nesne_depo
from services.nesne_depo import Nesne

URL_ENV = "KROMIS_NESNE_DEPO_URL"
KOVA_ENV = "KROMIS_NESNE_DEPO_KOVA"
ANAHTAR_ID_ENV = "KROMIS_NESNE_DEPO_ANAHTAR_ID"
GIZLI_ENV = "KROMIS_NESNE_DEPO_GIZLI"
BOLGE_ENV = "KROMIS_NESNE_DEPO_BOLGE"
ZORUNLU_ENV = (URL_ENV, KOVA_ENV, ANAHTAR_ID_ENV, GIZLI_ENV)
VARSAYILAN_BOLGE = "auto"

# Ön imzalı URL ömrü (sn) ve 302'nin tarayıcı önbelleği (sn): önbellek ömrün
# altında ki tarayıcı bayat bir adresi hiç kullanmasın (15 dk / 10 dk).
URL_SURESI = 15 * 60
ONBELLEK_SURESI = 10 * 60
CACHE_CONTROL = f"private, max-age={ONBELLEK_SURESI}"

__all__ = ["Depo", "DosyaHatasi", "DosyaYok", "YapilandirmaHatasi", "YerelDepo", "NesneDepo",
           "Nesne", "YazmaTamponu", "depo_kur", "depo", "YEREL", "URL_SURESI", "CACHE_CONTROL"]


class DosyaHatasi(Exception):
    """Depo işlemi başarısız (bağlantı, izin, beklenmeyen durum kodu, kök dışı yol)."""


class DosyaYok(DosyaHatasi):
    """`oku`/`oku_akis`: yol/anahtar depoda yok."""


class YapilandirmaHatasi(DosyaHatasi):
    """Ortam değişkenleri yarım: dördü de dolu ya da dördü de boş olmalı."""


class Depo(Protocol):
    def yaz(self, yol: str, veri: bytes, mime: str) -> None: ...
    def oku(self, yol: str) -> bytes: ...
    def oku_akis(self, yol: str) -> Iterator[bytes]: ...
    def sil(self, yol: str) -> bool: ...
    def var(self, yol: str) -> bool: ...
    def url(self, yol: str, sure: int, *, indirme_adi: str | None = None) -> str | None: ...
    def listele(self, onek: str) -> Iterator[Nesne]: ...


def _posix(anahtar: str) -> str:
    return anahtar.replace(os.sep, "/").lstrip("/")


class YerelDepo:
    """Yerel disk: `yol` mutlaksa olduğu gibi, göreliyse `kok` altında."""

    def __init__(self, kok: str) -> None:
        self.kok = kok

    def __repr__(self) -> str:
        return f"YerelDepo(kok={self.kok!r})"

    def _yol(self, yol: str) -> str:
        return yol if os.path.isabs(yol) else os.path.join(self.kok, *yol.split("/"))

    def _anahtar(self, yol: str) -> str:
        """Listeleme çıktısı: `kok` altındaysa göreli anahtar, değilse mutlak yol (testlerin tmp dizini)."""
        tam = self._yol(yol)
        goreli = os.path.relpath(tam, self.kok)
        return _posix(goreli) if not goreli.startswith("..") else tam

    def yaz(self, yol: str, veri: bytes, mime: str) -> None:
        tam = self._yol(yol)
        os.makedirs(os.path.dirname(tam), exist_ok=True)
        with open(tam, "wb") as f:
            f.write(veri)

    def oku(self, yol: str) -> bytes:
        try:
            with open(self._yol(yol), "rb") as f:
                return f.read()
        except FileNotFoundError as e:
            raise DosyaYok(yol) from e

    def oku_akis(self, yol: str) -> Iterator[bytes]:
        try:
            f = open(self._yol(yol), "rb")
        except FileNotFoundError as e:
            raise DosyaYok(yol) from e
        with f:
            while parca := f.read(nesne_depo.PARCA):
                yield parca

    def sil(self, yol: str) -> bool:
        tam = self._yol(yol)
        vardi = os.path.isfile(tam)
        # Bulma ile `remove` arasında dosya kaybolabilir (aynı görseli iki
        # sekmeden silmek yeter). Sonuç zaten istenen: dosya yok.
        with contextlib.suppress(FileNotFoundError):
            os.remove(tam)
        return vardi

    def var(self, yol: str) -> bool:
        return os.path.isfile(self._yol(yol))

    def url(self, yol: str, sure: int, *, indirme_adi: str | None = None) -> str | None:
        return None

    def listele(self, onek: str) -> Iterator[Nesne]:
        """S3 anlamıyla ÖNEK (dize başlangıcı), dizin değil: `kullanicilar/ab` `abc…`yi de bulur."""
        if not onek or onek in (".", "/"):
            dizin, onek_anahtar = self.kok, ""
        elif onek.endswith(("/", os.sep)):
            dizin = self._yol(onek).rstrip("/" + os.sep)
            onek_anahtar = self._anahtar(dizin) + "/"
        else:
            dizin = os.path.dirname(self._yol(onek))
            onek_anahtar = self._anahtar(self._yol(onek))
        if not os.path.isdir(dizin):
            return
        for kok, altlar, dosyalar in os.walk(dizin):
            altlar.sort()   # `os.walk` sırası dosya sistemine bağlı; çıktı kararlı olsun
            for ad in sorted(dosyalar):
                tam = os.path.join(kok, ad)
                anahtar = self._anahtar(tam)
                if anahtar.startswith(onek_anahtar):
                    yield Nesne(anahtar, os.path.getsize(tam))


class NesneDepo:
    """S3/R2 kovası: `yol` `kok` altındaki mutlak yol ya da göreli anahtar."""

    def __init__(self, istemci: nesne_depo.S3Istemci, kok: str) -> None:
        self.istemci = istemci
        self.kok = kok

    def __repr__(self) -> str:
        return f"NesneDepo(kova={self.istemci.kova!r}, kok={self.kok!r})"

    def _anahtar(self, yol: str) -> str:
        if os.path.isabs(yol):
            goreli = os.path.relpath(yol, self.kok)
            if goreli.startswith(".."):
                raise DosyaHatasi(f"yol veri kokunun disinda: {yol}")
            yol = goreli
        anahtar = _posix(os.path.normpath(yol)) if yol not in ("", ".") else ""
        if anahtar.startswith("../") or anahtar == "..":
            raise DosyaHatasi(f"yol veri kokunun disinda: {yol}")
        return anahtar

    def yaz(self, yol: str, veri: bytes, mime: str) -> None:
        try:
            self.istemci.koy(self._anahtar(yol), veri, mime)
        except nesne_depo.NesneHatasi as e:
            raise DosyaHatasi(str(e)) from e

    def oku(self, yol: str) -> bytes:
        try:
            return self.istemci.al(self._anahtar(yol))
        except nesne_depo.NesneYok as e:
            raise DosyaYok(yol) from e
        except nesne_depo.NesneHatasi as e:
            raise DosyaHatasi(str(e)) from e

    def oku_akis(self, yol: str) -> Iterator[bytes]:
        try:
            yield from self.istemci.al_akis(self._anahtar(yol))
        except nesne_depo.NesneYok as e:
            raise DosyaYok(yol) from e
        except nesne_depo.NesneHatasi as e:
            raise DosyaHatasi(str(e)) from e

    def sil(self, yol: str) -> bool:
        anahtar = self._anahtar(yol)
        try:
            vardi = self.istemci.bas(anahtar) is not None
            self.istemci.sil(anahtar)
        except nesne_depo.NesneHatasi as e:
            raise DosyaHatasi(str(e)) from e
        return vardi

    def var(self, yol: str) -> bool:
        try:
            return self.istemci.bas(self._anahtar(yol)) is not None
        except nesne_depo.NesneHatasi as e:
            raise DosyaHatasi(str(e)) from e

    def url(self, yol: str, sure: int, *, indirme_adi: str | None = None) -> str | None:
        return self.istemci.imzali_url(self._anahtar(yol), sure, indirme_adi=indirme_adi)

    def listele(self, onek: str) -> Iterator[Nesne]:
        try:
            yield from self.istemci.listele(self._anahtar(onek) if onek else "")
        except nesne_depo.NesneHatasi as e:
            raise DosyaHatasi(str(e)) from e


class YazmaTamponu:
    """`zipfile`in yazdığı, bir üreticinin okuduğu tampon — ZIP diske ya da belleğe BÜTÜN inmez.

    `tell`/`seek` YOK, bilerek: `ZipFile` aranamayan bir akışta veri
    tanımlayıcı (data descriptor) kipine geçer ve yazılan baytı geri
    alamayacağını bilir; üretici de yazılanı hemen boşaltır (`bosalt`).
    `services/depo_klasor.zip_disa_aktar` kullanıyor; burada duruyor çünkü
    depo modüllerinin her açık işlevi `(db, kullanici_id, …)` imzasına bağlı
    (tests/test_galeri_db.py bekçisi) ve `write`/`flush` adları dosya
    protokolünün kendisi.
    """

    def __init__(self) -> None:
        self.parcalar: list[bytes] = []

    def write(self, veri: bytes) -> int:
        self.parcalar.append(bytes(veri))
        return len(veri)

    def flush(self) -> None:
        return None

    def bosalt(self) -> bytes:
        veri = b"".join(self.parcalar)
        self.parcalar.clear()
        return veri


# Depoyu SÖYLEMEYEN çağıranın öntanımlısı: depo modülleri (`depo_medya.kaydet`
# vb.) `depo=None` alınca buraya düşer — bugünkü davranış, mutlak yollarla.
# Web rotaları depoyu HER ZAMAN söyler; bekçisi tests/test_dosya.py (kaynak taraması).
YEREL = YerelDepo(kok="")


def yapilandirma() -> dict[str, str]:
    """Dört zorunlu değişkenin kırpılmış değerleri (+ bölge); okuma tek yerde."""
    degerler = {ad: (os.environ.get(ad) or "").strip() for ad in ZORUNLU_ENV}
    degerler[BOLGE_ENV] = (os.environ.get(BOLGE_ENV) or "").strip() or VARSAYILAN_BOLGE
    return degerler


def nesne_depo_mu() -> bool:
    """Ortam nesne depolamayı seçmiş mi (dördü dolu)? Yarım yapılandırmayı `depo_kur` reddeder."""
    return all(yapilandirma()[ad] for ad in ZORUNLU_ENV)


def depo_kur(kok: str, *, istemci: httpx.Client | None = None) -> Depo:
    """Ortama göre depo: dördü dolu → `NesneDepo`, dördü boş → `YerelDepo(kok)`, yarım → hata.

    `istemci` testte `httpx.Client(transport=MockTransport(...))`.
    """
    ayar = yapilandirma()
    dolu = [ad for ad in ZORUNLU_ENV if ayar[ad]]
    if not dolu:
        return YerelDepo(kok)
    if len(dolu) != len(ZORUNLU_ENV):
        eksik = sorted(set(ZORUNLU_ENV) - set(dolu))
        raise YapilandirmaHatasi(f"nesne depolama yarim yapilandirilmis, eksik: {', '.join(eksik)} "
                                 "(dordu de dolu ya da dordu de bos olmali)")
    try:
        s3 = nesne_depo.S3Istemci(
            ayar[URL_ENV], ayar[KOVA_ENV],
            nesne_depo.Kimlik(ayar[ANAHTAR_ID_ENV], ayar[GIZLI_ENV], ayar[BOLGE_ENV]),
            istemci=istemci,
        )
    except ValueError as e:
        raise YapilandirmaHatasi(f"{URL_ENV}: {e}") from e
    return NesneDepo(s3, kok)


def depo(request: Request) -> Depo:
    """FastAPI bağımlılığı: sürecin deposu (`app.state.dosya`); oturum istemez, dosya yolu
    zaten `ayar.ayarlar`dan (kapılı) geliyor."""
    return request.app.state.dosya
