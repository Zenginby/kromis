# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Sahte S3 — bellek sözlüğünde kova; testler için `httpx.MockTransport`, duman için HTTP sunucu.

NEDEN VAR (Faz 2 / 2, test stratejisi): `moto` `boto3` ister (K6 onu eledi),
MinIO ikilisi CI'a ikinci bir servis (Faz 1 / K4'ün "Docker'sız" kısıtı bu
makinede aynen). Buradaki 200 satır `services/nesne_depo.py`nin kullandığı
alt kümeyi konuşur: `PUT/GET/HEAD/DELETE /<kova>/<anahtar>`, `ListObjectsV2`
(sayfalı, `max-keys` küçük tutulabilir ki sayfalama testi 3 nesneyle geçsin),
ön imzalı GET (`X-Amz-*` sorgusu), `Range` (206 + `Content-Range` — `<video>`
ileri sarma yolu).

İMZAYI DOĞRULAR, `kimlik` verilirse: gelen `Authorization`ı aynı kanonik
kurallarla YENİDEN HESAPLAR (`nesne_depo.yetki_basligi`/`imzali_sorgu`) ve
uyuşmazsa 403. Bu döngüsel görünür (aynı kodla imzalıyor ve doğruluyor) ama
sınadığı şey farklı: istemcinin İMZALADIĞI başlık/sorgu kümesi ile GÖNDERDİĞİ
küme aynı mı (httpx bir başlığı düşürse ya da sorguyu yeniden sıralasa burada
görünür). İmzanın kendisinin doğruluğu AWS'nin yayımlı örnekleriyle
(`tests/test_nesne_depo.py`). Biçim denetimi kimliksiz de yapılır.

İKİ ADAPTÖR, TEK ÇEKİRDEK (`cevapla`): `mock_transport()` testlerin senkron
`httpx.Client`i için; `sun()` gerçek bir HTTP sunucusu (`http.server`,
iş parçacıklı) — canlı duman testi uvicorn'u buna karşı koşturuyor
(`python tests/sahte_s3.py --port 9000 --kova kromis`). Diske yazmaz.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import re
import sys
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, quote, unquote, urlsplit
from xml.sax.saxutils import escape

import httpx

# Betik olarak koşarken (`python tests/sahte_s3.py`) kök modüller görünmez;
# pytest ithalinde bu satır etkisiz (kök zaten yolda). `tools/*.py`nin deyimi.
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from services import nesne_depo  # noqa: E402

YETKI_BICIMI = re.compile(
    r"^AWS4-HMAC-SHA256 Credential=(?P<akid>[^/]+)/(?P<tarih>\d{8})/(?P<bolge>[^/]+)/s3/aws4_request, "
    r"SignedHeaders=(?P<basliklar>[a-z0-9;\-]+), Signature=(?P<imza>[0-9a-f]{64})$")
ON_IMZA_PARAMETRELERI = ("X-Amz-Algorithm", "X-Amz-Credential", "X-Amz-Date", "X-Amz-Expires",
                         "X-Amz-SignedHeaders", "X-Amz-Signature")
AZAMI_SURE = 7 * 24 * 3600


@dataclass
class Istek:
    """Kaydedilen bir istek — testler "hangi başlıklarla gitti" diye buraya bakar."""
    yontem: str
    yol: str
    sorgu: dict[str, str]
    basliklar: dict[str, str]
    govde: bytes


@dataclass
class SahteS3:
    kova: str
    kimlik: nesne_depo.Kimlik | None = None
    sayfa: int = 1000                       # `max-keys` verilmezse bir sayfada kaç anahtar
    nesneler: dict[str, tuple[bytes, str]] = field(default_factory=dict)   # anahtar → (bayt, mime)
    istekler: list[Istek] = field(default_factory=list)
    saat: dt.datetime | None = None          # ön imzalı URL süresi bu ana göre ölçülür (None = şimdi)

    # ── çekirdek ──

    def cevapla(self, yontem: str, yol: str, sorgu: dict[str, str], basliklar: dict[str, str],
                govde: bytes) -> tuple[int, dict[str, str], bytes]:
        basliklar = {k.lower(): v for k, v in basliklar.items()}
        self.istekler.append(Istek(yontem, yol, dict(sorgu), basliklar, govde))
        hata = self._yetki(yontem, yol, sorgu, basliklar, govde)
        if hata:
            return 403, {"content-type": "application/xml"}, self._hata_xml("SignatureDoesNotMatch", hata)
        yol = unquote(yol)
        onek = f"/{self.kova}"
        if yol != onek and not yol.startswith(onek + "/"):
            return 404, {"content-type": "application/xml"}, self._hata_xml("NoSuchBucket", "kova yok")
        anahtar = yol[len(onek) + 1:]
        if not anahtar:
            if yontem == "GET" and sorgu.get("list-type") == "2":
                return self._listele(sorgu)
            return 405, {}, b""
        if yontem == "PUT":
            self.nesneler[anahtar] = (govde, basliklar.get("content-type", "binary/octet-stream"))
            return 200, {"etag": '"' + hashlib.md5(govde).hexdigest() + '"'}, b""
        if yontem == "DELETE":
            self.nesneler.pop(anahtar, None)
            return 204, {}, b""
        if yontem in ("GET", "HEAD"):
            kayit = self.nesneler.get(anahtar)
            if kayit is None:
                return 404, {"content-type": "application/xml"}, self._hata_xml("NoSuchKey", "anahtar yok")
            veri, mime = kayit
            cevap_basliklari = {"content-type": mime, "content-length": str(len(veri)),
                                "accept-ranges": "bytes"}
            if "response-content-disposition" in sorgu:
                cevap_basliklari["content-disposition"] = sorgu["response-content-disposition"]
            if yontem == "HEAD":
                return 200, cevap_basliklari, b""
            aralik = basliklar.get("range")
            if aralik:
                m = re.fullmatch(r"bytes=(\d*)-(\d*)", aralik.strip())
                if m and (m.group(1) or m.group(2)):
                    bas = int(m.group(1)) if m.group(1) else max(0, len(veri) - int(m.group(2)))
                    son = int(m.group(2)) if (m.group(1) and m.group(2)) else len(veri) - 1
                    son = min(son, len(veri) - 1)
                    if bas > son:
                        return 416, {"content-range": f"bytes */{len(veri)}"}, b""
                    parca = veri[bas:son + 1]
                    cevap_basliklari.update({"content-length": str(len(parca)),
                                             "content-range": f"bytes {bas}-{son}/{len(veri)}"})
                    return 206, cevap_basliklari, parca
            return 200, cevap_basliklari, veri
        return 405, {}, b""

    def _listele(self, sorgu: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
        onek = sorgu.get("prefix", "")
        adet = int(sorgu.get("max-keys") or self.sayfa)
        anahtarlar = sorted(a for a in self.nesneler if a.startswith(onek))
        baslangic = 0
        belirtec = sorgu.get("continuation-token")
        if belirtec:
            try:
                baslangic = int(belirtec)
            except ValueError:
                return 400, {}, self._hata_xml("InvalidArgument", "belirtec")
        sayfa = anahtarlar[baslangic:baslangic + adet]
        kesildi = baslangic + adet < len(anahtarlar)
        satirlar = "".join(
            f"<Contents><Key>{escape(a)}</Key><Size>{len(self.nesneler[a][0])}</Size></Contents>"
            for a in sayfa)
        sonraki = (f"<NextContinuationToken>{baslangic + adet}</NextContinuationToken>" if kesildi else "")
        xml = (f'<?xml version="1.0" encoding="UTF-8"?>'
               f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
               f"<Name>{escape(self.kova)}</Name><Prefix>{escape(onek)}</Prefix>"
               f"<KeyCount>{len(sayfa)}</KeyCount><MaxKeys>{adet}</MaxKeys>"
               f"<IsTruncated>{'true' if kesildi else 'false'}</IsTruncated>{sonraki}{satirlar}"
               f"</ListBucketResult>")
        return 200, {"content-type": "application/xml"}, xml.encode("utf-8")

    @staticmethod
    def _hata_xml(kod: str, mesaj: str) -> bytes:
        return f"<Error><Code>{kod}</Code><Message>{escape(mesaj)}</Message></Error>".encode()

    # ── yetki ──

    def _yetki(self, yontem: str, yol: str, sorgu: dict[str, str], basliklar: dict[str, str],
               govde: bytes) -> str | None:
        """Biçim her zaman; imza yalnız `kimlik` verildiyse. Hata metni ya da None."""
        if "X-Amz-Signature" in sorgu:
            return self._on_imza(yontem, yol, sorgu, basliklar)
        yetki = basliklar.get("authorization", "")
        m = YETKI_BICIMI.match(yetki)
        if not m:
            return f"Authorization bicimi bozuk: {yetki[:40]!r}"
        imzalananlar = set(m.group("basliklar").split(";"))
        for zorunlu in ("host", "x-amz-date", "x-amz-content-sha256"):
            if zorunlu not in imzalananlar:
                return f"{zorunlu} imzalanmamis"
        if basliklar.get("x-amz-content-sha256") != hashlib.sha256(govde).hexdigest():
            return "x-amz-content-sha256 govdeyle uyusmuyor"
        for ad in imzalananlar:
            if ad not in basliklar:
                return f"imzalanan baslik gonderilmemis: {ad}"
        if self.kimlik is None:
            return None
        if m.group("akid") != self.kimlik.anahtar_id:
            return "anahtar id yanlis"
        an = dt.datetime.strptime(basliklar["x-amz-date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.UTC)
        beklenen = nesne_depo.yetki_basligi(
            self.kimlik, an, yontem, unquote(yol), sorgu,
            {ad: basliklar[ad] for ad in imzalananlar}, basliklar["x-amz-content-sha256"])
        return None if beklenen == yetki else "imza uyusmuyor"

    def _on_imza(self, yontem: str, yol: str, sorgu: dict[str, str], basliklar: dict[str, str]) -> str | None:
        for ad in ON_IMZA_PARAMETRELERI:
            if ad not in sorgu:
                return f"on imzali sorguda {ad} yok"
        if sorgu["X-Amz-Algorithm"] != nesne_depo.ALGORITMA or sorgu["X-Amz-SignedHeaders"] != "host":
            return "algoritma/imzalanan basliklar"
        sure = int(sorgu["X-Amz-Expires"])
        if not 1 <= sure <= AZAMI_SURE:
            return "sure araligi"
        an = dt.datetime.strptime(sorgu["X-Amz-Date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.UTC)
        simdi = self.saat or dt.datetime.now(dt.UTC)
        if simdi > an + dt.timedelta(seconds=sure):
            return "on imzali URL suresi dolmus"
        if self.kimlik is None:
            return None
        if not sorgu["X-Amz-Credential"].startswith(self.kimlik.anahtar_id + "/"):
            return "anahtar id yanlis"
        digerleri = {k: v for k, v in sorgu.items() if not k.startswith("X-Amz-")}
        beklenen = nesne_depo.imzali_sorgu(self.kimlik, an, sure, yontem, basliklar.get("host", ""),
                                           unquote(yol), digerleri)
        return None if beklenen["X-Amz-Signature"] == sorgu["X-Amz-Signature"] else "on imza uyusmuyor"

    # ── adaptörler ──

    def mock_transport(self) -> httpx.MockTransport:
        def _isle(istek: httpx.Request) -> httpx.Response:
            sorgu = dict(parse_qsl(istek.url.query.decode("ascii"), keep_blank_values=True))
            basliklar = dict(istek.headers)
            basliklar.setdefault("host", istek.url.netloc.decode("ascii"))
            durum, cevap_basliklari, govde = self.cevapla(istek.method, istek.url.path, sorgu,
                                                          basliklar, istek.content)
            return httpx.Response(durum, headers=cevap_basliklari, content=govde)
        return httpx.MockTransport(_isle)

    def istemci(self) -> httpx.Client:
        return httpx.Client(transport=self.mock_transport())

    def sun(self, port: int = 0) -> tuple[ThreadingHTTPServer, str]:
        """Gerçek HTTP sunucu (arka plan iş parçacığı); `(sunucu, "http://127.0.0.1:<port>")`."""
        kova = self

        class _Isleyici(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_: object) -> None:   # duman çıktısını kirletmesin
                return

            def _isle(self) -> None:
                parcalar = urlsplit(self.path)
                sorgu = dict(parse_qsl(parcalar.query, keep_blank_values=True))
                uzunluk = int(self.headers.get("content-length") or 0)
                govde = self.rfile.read(uzunluk) if uzunluk else b""
                basliklar = {k.lower(): v for k, v in self.headers.items()}
                durum, cevap_basliklari, cevap = kova.cevapla(self.command, parcalar.path, sorgu,
                                                             basliklar, govde)
                self.send_response(durum)
                for k, v in cevap_basliklari.items():
                    if k != "content-length":
                        self.send_header(k, v)
                self.send_header("content-length", str(len(cevap)) if self.command != "HEAD"
                                 else cevap_basliklari.get("content-length", "0"))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(cevap)

            do_GET = do_PUT = do_HEAD = do_DELETE = _isle

        sunucu = ThreadingHTTPServer(("127.0.0.1", port), _Isleyici)
        threading.Thread(target=sunucu.serve_forever, daemon=True).start()
        return sunucu, f"http://127.0.0.1:{sunucu.server_address[1]}"


def anahtar_yolu(kova: str, anahtar: str) -> str:
    """`/<kova>/<anahtar>` — test iddiaları için, istemcinin kodladığı biçimde."""
    return quote(f"/{kova}/{anahtar}", safe="/")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sahte S3 sunucusu (bellek); duman testi icin.")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--kova", default="kromis")
    p.add_argument("--anahtar-id", default="")
    p.add_argument("--gizli", default="")
    args = p.parse_args(argv)
    kimlik = nesne_depo.Kimlik(args.anahtar_id, args.gizli) if args.anahtar_id and args.gizli else None
    sunucu, adres = SahteS3(args.kova, kimlik).sun(args.port)
    print(f"sahte S3 dinliyor: {adres} kova={args.kova} imza dogrulama={'acik' if kimlik else 'kapali'}",
          flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        sunucu.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
