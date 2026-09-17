"""`services/nesne_depo.py` — SigV4 elle + httpx S3 istemcisi (Faz 2 / 2, K6).

İki katman, iki bekçi:

  1. İMZA DOĞRU MU — AWS'nin YAYIMLADIĞI örnekler (sabit anahtar/tarih/istek →
     bilinen imza). `moto` elendi (`boto3` ister), gerçek uç CI'da yok; imzanın
     doğruluğunu bağımsız bir kaynağa bağlamanın tek yolu bu dört vektör:
     GET (Range başlıklı), PUT (gövde özeti + `$` kodlaması), ön imzalı GET
     (sorgu imzası), ListObjects (sorgu dizesi). Dördü de S3'ün "Signature
     Calculations in the Authorization Header" ve "Query String" belgelerinden.
  2. TEL DOĞRU MU — `tests/sahte_s3.py` istemcinin GÖNDERDİĞİNİ aynı kurallarla
     yeniden imzalar: imzalanan başlık kümesi ile gönderilen küme ayrışırsa 403.
     Sayfalı listeleme, akışlı okuma, hata eşlemesi, sır sızıntısı burada.

Ağa HİÇ çıkılmaz: `httpx.MockTransport` (services/posta.py'nin test deyimi).
"""
from __future__ import annotations

import datetime as dt
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from services import nesne_depo as nd
from tests.sahte_s3 import SahteS3

# AWS'nin örnek kimliği ve tarihi (docs.aws.amazon.com, "Examples: Signature Calculations").
AWS_KIMLIK = nd.Kimlik("AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "us-east-1")
AWS_AN = dt.datetime(2013, 5, 24, tzinfo=dt.UTC)
AWS_KONAK = "examplebucket.s3.amazonaws.com"

KIMLIK = nd.Kimlik("AKID_TEST", "GIZLI_TEST_DEGERI", "auto")
UC = "https://hesap.r2.example"


def _istemci(sahte: SahteS3, **ek) -> nd.S3Istemci:
    return nd.S3Istemci(UC, sahte.kova, KIMLIK, istemci=sahte.istemci(), **ek)


# ── 1. Bilinen cevaplar ──────────────────────────────────────────────

def test_the_aws_get_object_example_signs_byte_for_byte():
    basliklar = {"host": AWS_KONAK, "range": "bytes=0-9",
                 "x-amz-content-sha256": nd.BOS_OZET, "x-amz-date": "20130524T000000Z"}
    yetki = nd.yetki_basligi(AWS_KIMLIK, AWS_AN, "GET", "/test.txt", {}, basliklar, nd.BOS_OZET)
    assert yetki == ("AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request, "
                     "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date, "
                     "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")


def test_the_aws_put_object_example_signs_the_payload_hash_and_encodes_the_dollar_sign():
    govde = b"Welcome to Amazon S3."
    ozet = nd._sha256(govde)
    assert ozet == "44ce7dd67c959e0d3524ffac1771dfbba87d2b6b4b4e99e42034a8b803f8b072"
    basliklar = {"host": AWS_KONAK, "date": "Fri, 24 May 2013 00:00:00 GMT",
                 "x-amz-content-sha256": ozet, "x-amz-date": "20130524T000000Z",
                 "x-amz-storage-class": "REDUCED_REDUNDANCY"}
    kanonik, imzalananlar = nd.kanonik_istek("PUT", "/test$file.text", {}, basliklar, ozet)
    assert kanonik.splitlines()[1] == "/test%24file.text"
    assert imzalananlar == "date;host;x-amz-content-sha256;x-amz-date;x-amz-storage-class"
    assert nd.imzala(AWS_KIMLIK, AWS_AN, kanonik) == \
        "98ad721746da40c64f1a55b78f14c238d841ea1380cd77a1b5971af0ece108bd"


def test_the_aws_presigned_url_example_signs_the_query_string():
    p = nd.imzali_sorgu(AWS_KIMLIK, AWS_AN, 86400, "GET", AWS_KONAK, "/test.txt")
    assert p["X-Amz-Signature"] == "aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"
    assert p["X-Amz-Credential"] == "AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request"
    assert p["X-Amz-Expires"] == "86400" and p["X-Amz-SignedHeaders"] == "host"
    assert list(p) == sorted(p), "parametreler sıralı — kanonik sorgu bu sırayla kurulur"


def test_the_aws_list_objects_example_signs_the_query_parameters():
    basliklar = {"host": AWS_KONAK, "x-amz-content-sha256": nd.BOS_OZET, "x-amz-date": "20130524T000000Z"}
    yetki = nd.yetki_basligi(AWS_KIMLIK, AWS_AN, "GET", "/", {"max-keys": "2", "prefix": "J"},
                             basliklar, nd.BOS_OZET)
    assert yetki.endswith("Signature=34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7")


def test_uri_encoding_follows_the_aws_rules_not_pythons_defaults():
    assert nd.uri_kodla("a b/c~d", egik_cizgi_kalsin=True) == "a%20b/c~d"
    assert nd.uri_kodla("a/b=c&d") == "a%2Fb%3Dc%26d"
    assert nd.kanonik_sorgu({"b": "2", "a": "x y"}) == "a=x%20y&b=2"


# ── 2. İstemci ↔ sahte S3 ────────────────────────────────────────────

def test_put_get_head_delete_round_trip_and_the_headers_the_fake_verifies():
    sahte = SahteS3("kova", KIMLIK)
    c = _istemci(sahte)
    c.koy("kullanicilar/u/output/a.png", b"\x89PNG-a", "image/png")
    assert sahte.nesneler["kullanicilar/u/output/a.png"] == (b"\x89PNG-a", "image/png")
    assert c.al("kullanicilar/u/output/a.png") == b"\x89PNG-a"
    assert c.bas("kullanicilar/u/output/a.png") == nd.Nesne("kullanicilar/u/output/a.png", 6)
    assert c.bas("kullanicilar/u/output/yok.png") is None
    c.sil("kullanicilar/u/output/a.png")
    assert c.bas("kullanicilar/u/output/a.png") is None
    c.sil("kullanicilar/u/output/a.png")   # idempotent: ikinci silme hata değil

    put = next(i for i in sahte.istekler if i.yontem == "PUT")
    assert put.yol == "/kova/kullanicilar/u/output/a.png"
    assert put.basliklar["content-type"] == "image/png"
    assert put.basliklar["x-amz-content-sha256"] == nd._sha256(b"\x89PNG-a")
    assert "SignedHeaders=content-length;content-type;host;x-amz-content-sha256;x-amz-date," in \
        put.basliklar["authorization"]


def test_the_fake_rejects_a_tampered_signature_so_the_round_trip_above_means_something():
    sahte = SahteS3("kova", KIMLIK)
    yanlis = nd.S3Istemci(UC, "kova", nd.Kimlik(KIMLIK.anahtar_id, "BASKA_GIZLI", "auto"),
                          istemci=sahte.istemci())
    with pytest.raises(nd.NesneHatasi) as hata:
        yanlis.koy("k", b"x", "image/png")
    assert hata.value.durum == 403
    assert "BASKA_GIZLI" not in str(hata.value)


def test_list_objects_follows_continuation_tokens_across_pages():
    sahte = SahteS3("kova", KIMLIK, sayfa=2)
    c = _istemci(sahte)
    for ad in ("u/output/a.png", "u/output/b.png", "u/output/c.mp4", "u/assets/logos/d.png", "v/output/e.png"):
        c.koy(f"kullanicilar/{ad}", ad.encode(), "application/octet-stream")
    sahte.istekler.clear()
    bulunan = list(c.listele("kullanicilar/u/"))
    assert [n.anahtar for n in bulunan] == ["kullanicilar/u/assets/logos/d.png", "kullanicilar/u/output/a.png",
                                            "kullanicilar/u/output/b.png", "kullanicilar/u/output/c.mp4"]
    assert [n.boyut for n in bulunan] == [len("u/assets/logos/d.png"), len("u/output/a.png"),
                                          len("u/output/b.png"), len("u/output/c.mp4")]
    listeler = [i for i in sahte.istekler if i.sorgu.get("list-type") == "2"]
    assert len(listeler) == 2, "4 anahtar, sayfa 2 → iki istek"
    assert "continuation-token" not in listeler[0].sorgu and listeler[1].sorgu["continuation-token"] == "2"
    assert all(i.sorgu["prefix"] == "kullanicilar/u/" for i in listeler)
    assert list(c.listele("kullanicilar/yok/")) == []


def test_streaming_read_yields_the_body_in_chunks_and_closes_the_response():
    sahte = SahteS3("kova", KIMLIK)
    c = _istemci(sahte)
    govde = bytes(range(256)) * 40   # 10 KB
    c.koy("k/buyuk.mp4", govde, "video/mp4")
    parcalar = list(c.al_akis("k/buyuk.mp4", parca=4096))
    assert b"".join(parcalar) == govde and len(parcalar) >= 3
    with pytest.raises(nd.NesneYok):
        list(c.al_akis("k/yok.mp4"))


def test_errors_map_to_the_two_exception_types_and_never_carry_the_secret():
    def _cevapla(istek: httpx.Request) -> httpx.Response:
        if istek.url.path.endswith("yok"):
            return httpx.Response(404, content=b"<Error/>")
        if istek.url.path.endswith("patla"):
            return httpx.Response(500, content=b"<Error><Message>GIZLI_TEST_DEGERI</Message></Error>")
        raise httpx.ConnectError("baglanti yok")
    c = nd.S3Istemci(UC, "kova", KIMLIK, istemci=httpx.Client(transport=httpx.MockTransport(_cevapla)))
    with pytest.raises(nd.NesneYok) as yok:
        c.al("yok")
    assert yok.value.durum == 404
    with pytest.raises(nd.NesneHatasi) as patla:
        c.al("patla")
    assert patla.value.durum == 500 and "GIZLI" not in str(patla.value), "gövde hataya girmez"
    with pytest.raises(nd.NesneHatasi) as kopuk:
        c.al("kopuk")
    assert kopuk.value.durum is None and "ConnectError" in str(kopuk.value)
    assert "GIZLI_TEST_DEGERI" not in repr(c) and "GIZLI_TEST_DEGERI" not in repr(KIMLIK)


def test_the_constructor_rejects_a_half_empty_configuration():
    with pytest.raises(ValueError):
        nd.S3Istemci("", "kova", KIMLIK)
    with pytest.raises(ValueError):
        nd.S3Istemci("hesap.r2.example", "kova", KIMLIK)     # şema yok
    with pytest.raises(ValueError):
        nd.S3Istemci(UC, "kova", nd.Kimlik("AKID", "", "auto"))


# ── 3. Ön imzalı URL ─────────────────────────────────────────────────

def test_the_presigned_url_carries_the_required_parameters_expiry_and_download_name():
    sabit = dt.datetime(2026, 9, 17, 12, 0, tzinfo=dt.UTC)
    sahte = SahteS3("kova", KIMLIK, saat=sabit)
    c = _istemci(sahte, saat=lambda: sabit)
    c.koy("kullanicilar/u/output/v.mp4", b"MP4" * 100, "video/mp4")
    url = c.imzali_url("kullanicilar/u/output/v.mp4", 900, indirme_adi="tanıtım videosu.mp4")

    parcalar = urlsplit(url)
    assert f"{parcalar.scheme}://{parcalar.netloc}" == UC
    assert parcalar.path == "/kova/kullanicilar/u/output/v.mp4"
    sorgu = {k: v[0] for k, v in parse_qs(parcalar.query, keep_blank_values=True).items()}
    assert sorgu["X-Amz-Algorithm"] == "AWS4-HMAC-SHA256"
    assert sorgu["X-Amz-Credential"] == f"{KIMLIK.anahtar_id}/20260917/auto/s3/aws4_request"
    assert sorgu["X-Amz-Date"] == "20260917T120000Z" and sorgu["X-Amz-Expires"] == "900"
    assert sorgu["X-Amz-SignedHeaders"] == "host" and len(sorgu["X-Amz-Signature"]) == 64
    assert sorgu["response-content-disposition"] == \
        "attachment; filename=\"tantm videosu.mp4\"; filename*=UTF-8''tan%C4%B1t%C4%B1m%20videosu.mp4"
    assert "GIZLI" not in url

    # Sahte imzayı yeniden hesaplayıp kabul ediyor; `Range` doğrudan nesneye ulaşıyor (<video> ileri sarma).
    tam = sahte.istemci().get(url)
    assert tam.status_code == 200 and tam.content == b"MP4" * 100
    assert tam.headers["content-disposition"].startswith("attachment;")
    aralik = sahte.istemci().get(url, headers={"Range": "bytes=3-5"})
    assert aralik.status_code == 206 and aralik.content == b"MP4" and aralik.headers["content-range"] == "bytes 3-5/300"


def test_an_expired_presigned_url_is_refused_by_the_fake():
    imza_ani = dt.datetime(2026, 9, 17, 12, 0, tzinfo=dt.UTC)
    sahte = SahteS3("kova", KIMLIK, saat=imza_ani + dt.timedelta(seconds=901))
    c = _istemci(sahte, saat=lambda: imza_ani)
    c.koy("k", b"x", "image/png")
    sahte.saat = imza_ani + dt.timedelta(seconds=901)
    assert sahte.istemci().get(c.imzali_url("k", 900)).status_code == 403
    sahte.saat = imza_ani + dt.timedelta(seconds=899)
    assert sahte.istemci().get(c.imzali_url("k", 900)).status_code == 200


def test_the_presigned_url_without_a_download_name_has_no_disposition_parameter():
    sahte = SahteS3("kova", KIMLIK)
    url = _istemci(sahte).imzali_url("k/a.png", 60)
    assert "response-content-disposition" not in url
    assert url.startswith(f"{UC}/kova/k/a.png?X-Amz-Algorithm=")
