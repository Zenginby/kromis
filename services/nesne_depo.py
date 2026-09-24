# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""S3 uyumlu nesne depolama istemcisi — SigV4 ELLE, HTTP `httpx` ile (Faz 2 / 2, K6).

NEDEN `boto3`/`minio` DEĞİL: ölçüldü (docs/faz2-kuyruk-anahtarlar-depolama.md,
giriş): `boto3` zinciri 7 tekerlek, 21 MB açılmış (`botocore` tek başına 19 MB,
~400 servisin modeli — bize BİRİ gerek), imaja +%7; `minio` 0,1 MB ama
`pycryptodome` + `urllib3` getiriyor (depo `httpx` taşıyor: Resend, OIDC,
sağlayıcı adaptörleri — ikinci bir HTTP yığını, ikinci pin ailesi). İkisi de
testte ya `moto`/gerçek uç ister ya kendi taşıyıcısını yamalatır. Elle imza
`hmac`/`hashlib` ile standart kütüphane, HTTP deponun MEVCUT `httpx` deyimi
(services/posta.py: `istemci` testte `httpx.MockTransport` ile veriliyor).
Bedeli: SigV4'ü doğru yazmak — bekçisi AWS'nin YAYIMLADIĞI imza örnekleri
(sabit anahtar/tarih/istek → bilinen imza; tests/test_nesne_depo.py) ve gerçek
bir R2 kovasına karşı canlı doğrulama (sahibin adımı, belgede).

KAPSAM asgari ve bilerek: `PUT/GET/HEAD/DELETE /<kova>/<anahtar>`, `ListObjectsV2`
(sayfalı, `continuation-token`), ön imzalı GET URL (sorgu imzası,
`response-content-disposition` ile indirme adı). ÇOK PARÇALI YÜKLEME YOK: en
büyük nesne bir video, sağlayıcılar onu tek gövde veriyor, `PUT` 5 GB'a kadar
tek parça. Yol biçimi PATH-STYLE (`https://<uç>/<kova>/<anahtar>`): R2 iki
biçimi de kabul ediyor, path-style uç noktayı kova adından bağımsız tutuyor
(tek `KROMIS_NESNE_DEPO_URL`, alan adı hesaplamak yok).

BÖLGE: R2 `auto` bekliyor (imza kapsamındaki dize; AWS'de `us-east-1` gibi).
İmza `s3` servisi için.

SIR: `Kimlik.gizli` `repr`e GİRMEZ (`field(repr=False)`), hiçbir istisna
mesajına ve günlüğe yazılmaz — `NesneHatasi` yalnız HTTP durum kodunu ve
yöntem/anahtarı taşır. İmza zinciri gizliyi yalnız `hmac` anahtarı olarak görür.

ZAMAN: `an` parametresi/`saat` çağrılabiliri — bilinen-cevap testleri sabit bir
tarihle imzalıyor (`2013-05-24T00:00:00Z`, AWS'nin örneği); üretimde `datetime.now(UTC)`.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from urllib.parse import quote, urlsplit

import httpx

ALGORITMA = "AWS4-HMAC-SHA256"
SERVIS = "s3"
BOS_OZET = hashlib.sha256(b"").hexdigest()
IMZASIZ_GOVDE = "UNSIGNED-PAYLOAD"
S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

# Bir nesne isteği için üst sınır: PUT'ta video gövdesi onlarca MB olabilir,
# okuma tarafında R2 ilk baytı saniyeler içinde verir. Bağlanma kısa, okuma/yazma uzun.
ZAMAN_ASIMI = httpx.Timeout(connect=10.0, read=120.0, write=300.0, pool=10.0)

# Akışla okumada parça boyutu (ZIP dışa aktarma bununla ilerler).
PARCA = 1024 * 1024


class NesneHatasi(Exception):
    """S3 ucu istenmeyen bir durum kodu döndü ya da bağlantı düştü. Gizli TAŞIMAZ."""

    def __init__(self, mesaj: str, durum: int | None = None) -> None:
        super().__init__(mesaj)
        self.durum = durum


class NesneYok(NesneHatasi):
    """404: anahtar kovada yok — `oku`/`bas`/`sil`in çağırana verdiği tek anlamlı ayrım."""


@dataclass(frozen=True)
class Kimlik:
    anahtar_id: str
    gizli: str = field(repr=False)
    bolge: str = "auto"


@dataclass(frozen=True)
class Nesne:
    """`listele`nin bir satırı: anahtar + bayt."""
    anahtar: str
    boyut: int


# ── SigV4 — saf işlevler (bilinen-cevap testleri bunları doğrudan çağırıyor) ──

def _sha256(veri: bytes) -> str:
    return hashlib.sha256(veri).hexdigest()


def _hmac(anahtar: bytes, mesaj: str) -> bytes:
    return hmac.new(anahtar, mesaj.encode("utf-8"), hashlib.sha256).digest()


def uri_kodla(metin: str, *, egik_cizgi_kalsin: bool = False) -> str:
    """AWS'nin "UriEncode"u: RFC 3986 ayrılmamışlar dışında her şey `%XX`, boşluk `%20`.

    `quote`un öntanımlı `safe="/"`i yalnız yol için doğru (S3 anahtardaki `/`yi
    KODLAMAZ); sorgu adı/değeri için `safe=""`. `~` ayrılmamış (3.7+ `quote` öyle sayıyor).
    """
    return quote(metin, safe="/" if egik_cizgi_kalsin else "")


def amz_tarih(an: dt.datetime) -> str:
    """`20130524T000000Z` — `x-amz-date`/`X-Amz-Date` biçimi, UTC."""
    return an.astimezone(dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def kapsam(an: dt.datetime, bolge: str) -> str:
    return f"{amz_tarih(an)[:8]}/{bolge}/{SERVIS}/aws4_request"


def imza_anahtari(gizli: str, an: dt.datetime, bolge: str) -> bytes:
    """`kSigning` — dört kademeli HMAC zinciri; gizli yalnız BURADA anahtar olur."""
    k_tarih = _hmac(("AWS4" + gizli).encode("utf-8"), amz_tarih(an)[:8])
    k_bolge = _hmac(k_tarih, bolge)
    k_servis = _hmac(k_bolge, SERVIS)
    return _hmac(k_servis, "aws4_request")


def kanonik_sorgu(sorgu: Mapping[str, str]) -> str:
    """Anahtara göre sıralı, ad ve değer AYRI AYRI kodlanmış `a=b&c=d`."""
    return "&".join(f"{uri_kodla(k)}={uri_kodla(v)}" for k, v in sorted(sorgu.items()))


def kanonik_istek(yontem: str, yol: str, sorgu: Mapping[str, str],
                  basliklar: Mapping[str, str], govde_ozeti: str) -> tuple[str, str]:
    """(kanonik istek, imzalanan başlık listesi).

    Başlık adları küçük harf, değerler kırpılmış, ada göre sıralı; her biri
    imzalanır (AWS "en az host"). Yol bölüm bölüm kodlanır, `/` kalır.
    """
    duz = {ad.lower(): " ".join(deger.strip().split()) for ad, deger in basliklar.items()}
    imzalananlar = ";".join(sorted(duz))
    kanonik_basliklar = "".join(f"{ad}:{duz[ad]}\n" for ad in sorted(duz))
    kanonik = "\n".join([yontem.upper(), uri_kodla(yol, egik_cizgi_kalsin=True),
                         kanonik_sorgu(sorgu), kanonik_basliklar, imzalananlar, govde_ozeti])
    return kanonik, imzalananlar


def imzala(kimlik: Kimlik, an: dt.datetime, kanonik: str) -> str:
    """Kanonik istekten imzaya: `StringToSign` → HMAC(kSigning) → hex."""
    dize = "\n".join([ALGORITMA, amz_tarih(an), kapsam(an, kimlik.bolge),
                      _sha256(kanonik.encode("utf-8"))])
    return hmac.new(imza_anahtari(kimlik.gizli, an, kimlik.bolge),
                    dize.encode("utf-8"), hashlib.sha256).hexdigest()


def yetki_basligi(kimlik: Kimlik, an: dt.datetime, yontem: str, yol: str,
                  sorgu: Mapping[str, str], basliklar: Mapping[str, str],
                  govde_ozeti: str) -> str:
    """`Authorization` başlığının değeri (başlık tabanlı imza). `basliklar` `host` ve
    `x-amz-date`i ZATEN içermeli — çağıran ne gönderiyorsa o imzalanır."""
    kanonik, imzalananlar = kanonik_istek(yontem, yol, sorgu, basliklar, govde_ozeti)
    imza = imzala(kimlik, an, kanonik)
    return (f"{ALGORITMA} Credential={kimlik.anahtar_id}/{kapsam(an, kimlik.bolge)}, "
            f"SignedHeaders={imzalananlar}, Signature={imza}")


def imzali_sorgu(kimlik: Kimlik, an: dt.datetime, sure: int, yontem: str, konak: str,
                 yol: str, sorgu: Mapping[str, str] | None = None) -> dict[str, str]:
    """Ön imzalı URL'nin sorgu parametreleri (`X-Amz-*` + `X-Amz-Signature`), sıralı.

    Yalnız `host` imzalanır, gövde `UNSIGNED-PAYLOAD`: tarayıcı `<img>`/`<video>`
    etiketi başka başlık taşıyamaz. `sure` saniye (AWS tavanı 7 gün).
    """
    parametreler = dict(sorgu or {})
    parametreler.update({
        "X-Amz-Algorithm": ALGORITMA,
        "X-Amz-Credential": f"{kimlik.anahtar_id}/{kapsam(an, kimlik.bolge)}",
        "X-Amz-Date": amz_tarih(an),
        "X-Amz-Expires": str(int(sure)),
        "X-Amz-SignedHeaders": "host",
    })
    kanonik, _ = kanonik_istek(yontem, yol, parametreler, {"host": konak}, IMZASIZ_GOVDE)
    parametreler["X-Amz-Signature"] = imzala(kimlik, an, kanonik)
    return dict(sorted(parametreler.items()))


# ── İstemci ────────────────────────────────────────────────────────────

class S3Istemci:
    """Tek kovaya bağlı S3 istemcisi. `istemci` testte `httpx.MockTransport` ile verilir.

    Bütün yöntemler ANAHTARLA konuşur (`kullanicilar/<uuid>/output/<ad>`); yol
    ↔ anahtar çevirisi çağıranın (services/dosya.py) işi.
    """

    def __init__(self, uc_nokta: str, kova: str, kimlik: Kimlik, *,
                 istemci: httpx.Client | None = None,
                 saat: Callable[[], dt.datetime] | None = None) -> None:
        if not uc_nokta or not kova or not kimlik.anahtar_id or not kimlik.gizli:
            raise ValueError("uc nokta, kova, anahtar id ve gizli dolu olmali")
        parcalar = urlsplit(uc_nokta)
        if parcalar.scheme not in ("http", "https") or not parcalar.netloc:
            raise ValueError("uc nokta https://<konak> biciminde olmali")
        self.uc_nokta = f"{parcalar.scheme}://{parcalar.netloc}"
        self.konak = parcalar.netloc
        self.kova = kova
        self.kimlik = kimlik
        self.istemci = istemci or httpx.Client(timeout=ZAMAN_ASIMI)
        self._saat = saat or (lambda: dt.datetime.now(dt.UTC))

    def __repr__(self) -> str:   # gizli görünmesin
        return f"S3Istemci(uc_nokta={self.uc_nokta!r}, kova={self.kova!r})"

    # ── iç ──

    def _yol(self, anahtar: str) -> str:
        return f"/{self.kova}/{anahtar}" if anahtar else f"/{self.kova}"

    def _istek(self, yontem: str, anahtar: str, *, sorgu: Mapping[str, str] | None = None,
               govde: bytes = b"", ek_basliklar: Mapping[str, str] | None = None,
               akis: bool = False) -> httpx.Response:
        an = self._saat()
        yol = self._yol(anahtar)
        sorgu = dict(sorgu or {})
        ozet = _sha256(govde)
        basliklar = {"host": self.konak, "x-amz-content-sha256": ozet, "x-amz-date": amz_tarih(an)}
        basliklar.update({k.lower(): v for k, v in (ek_basliklar or {}).items()})
        basliklar["authorization"] = yetki_basligi(self.kimlik, an, yontem, yol, sorgu, basliklar, ozet)
        # `host`u httpx kendisi koyar; imzada var, başlıkta yinelemeye gerek yok.
        gonderilen = {k: v for k, v in basliklar.items() if k != "host"}
        url = f"{self.uc_nokta}{yol}"
        if sorgu:
            url += "?" + kanonik_sorgu(sorgu)
        try:
            istek = self.istemci.build_request(yontem, url, headers=gonderilen, content=govde)
            return self.istemci.send(istek, stream=akis)
        except httpx.HTTPError as e:
            raise NesneHatasi(f"{yontem} {anahtar}: baglanti hatasi: {type(e).__name__}") from e

    @staticmethod
    def _kontrol(cevap: httpx.Response, yontem: str, anahtar: str) -> None:
        if cevap.status_code == 404:
            raise NesneYok(f"{yontem} {anahtar}: yok", 404)
        if cevap.status_code >= 300:
            # Gövde HATAYA GİRMEZ: S3 hata XML'i istek kimliğini ve bazen
            # imzalanan dizeyi (anahtar id dâhil) yansıtır — hata.log'a girmesin.
            raise NesneHatasi(f"{yontem} {anahtar}: HTTP {cevap.status_code}", cevap.status_code)

    # ── nesneler ──

    def koy(self, anahtar: str, veri: bytes, mime: str) -> None:
        cevap = self._istek("PUT", anahtar, govde=veri,
                            ek_basliklar={"content-type": mime, "content-length": str(len(veri))})
        self._kontrol(cevap, "PUT", anahtar)

    def al(self, anahtar: str) -> bytes:
        cevap = self._istek("GET", anahtar)
        self._kontrol(cevap, "GET", anahtar)
        return cevap.content

    def al_akis(self, anahtar: str, parca: int = PARCA) -> Iterator[bytes]:
        """Gövdeyi parça parça — ZIP dışa aktarma bir videoyu belleğe bütün almasın."""
        cevap = self._istek("GET", anahtar, akis=True)
        try:
            if cevap.status_code >= 300:
                cevap.read()
            self._kontrol(cevap, "GET", anahtar)
            yield from cevap.iter_bytes(parca)
        finally:
            cevap.close()

    def bas(self, anahtar: str) -> Nesne | None:
        """HEAD: varsa boyutuyla `Nesne`, yoksa None (404 burada istisna DEĞİL — soru "var mı")."""
        cevap = self._istek("HEAD", anahtar)
        if cevap.status_code == 404:
            return None
        self._kontrol(cevap, "HEAD", anahtar)
        return Nesne(anahtar, int(cevap.headers.get("content-length") or 0))

    def sil(self, anahtar: str) -> None:
        """DELETE idempotent: S3 olmayan anahtara da 204 der; 404 gelirse o da "yok" demek."""
        cevap = self._istek("DELETE", anahtar)
        if cevap.status_code == 404:
            return
        self._kontrol(cevap, "DELETE", anahtar)

    def listele(self, onek: str) -> Iterator[Nesne]:
        """`ListObjectsV2`, `continuation-token` ile sayfa sayfa; anahtar sırasıyla."""
        belirtec: str | None = None
        while True:
            sorgu = {"list-type": "2", "prefix": onek}
            if belirtec:
                sorgu["continuation-token"] = belirtec
            cevap = self._istek("GET", "", sorgu=sorgu)
            self._kontrol(cevap, "LIST", onek)
            try:
                kok = ET.fromstring(cevap.content)
            except ET.ParseError as e:
                raise NesneHatasi(f"LIST {onek}: XML okunamadi") from e
            for icerik in kok.iter(f"{S3_NS}Contents"):
                anahtar = icerik.findtext(f"{S3_NS}Key") or ""
                boyut = int(icerik.findtext(f"{S3_NS}Size") or 0)
                if anahtar:
                    yield Nesne(anahtar, boyut)
            if (kok.findtext(f"{S3_NS}IsTruncated") or "").lower() != "true":
                return
            belirtec = kok.findtext(f"{S3_NS}NextContinuationToken") or None
            if not belirtec:
                return

    def imzali_url(self, anahtar: str, sure: int, *, indirme_adi: str | None = None) -> str:
        """Ön imzalı GET URL'si. `indirme_adi` verilirse R2 `Content-Disposition: attachment`
        ile döner (`response-content-disposition`; RFC 6266 iki biçim, routers/galeri.py'nin kararı)."""
        sorgu: dict[str, str] = {}
        if indirme_adi:
            ascii_ad = indirme_adi.encode("ascii", "ignore").decode("ascii").replace('"', "") or "dosya"
            sorgu["response-content-disposition"] = (
                f'attachment; filename="{ascii_ad}"; filename*=UTF-8\'\'{quote(indirme_adi)}')
        yol = self._yol(anahtar)
        parametreler = imzali_sorgu(self.kimlik, self._saat(), sure, "GET", self.konak, yol, sorgu)
        return f"{self.uc_nokta}{uri_kodla(yol, egik_cizgi_kalsin=True)}?{kanonik_sorgu(parametreler)}"
