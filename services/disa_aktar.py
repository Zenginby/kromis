# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Veri dışa aktarma — kullanıcının bütün kayıtları tek ZIP'te, JSON/CSV (Faz 4 / 5; KVKK md. 11, GDPR md. 20).

`GET /api/hesap/disa-aktar` (routers/hesap.py) bu modülün ürettiği akışı
döndürür. Dokuz dosya:

    hesap.json            id, e-posta, dil, plan, plan_bitis, kayıt anı, şartlar onayı, dışa aktarma anı
    kredi_hareketleri.csv defterin TAMAMI (`defter.hareketler(limit=None)`) — `_json`un alanları
    siparisler.csv        bütün siparişler (`defter.siparisler(limit=None)`)
    isler.json            bütün işler (`kuyruk.listele(limit=None)`, `_json`: `istek` ve `saglayici_meta` YOK)
    sohbetler.json        gövdeleriyle (`depo_sohbet.hepsi`)
    paletler.json         `depo_palet.listele`
    klasorler.json        `depo_klasor.listele` + her klasörün galeri ZIP bağlantısı (`indirme`)
    medya.json            kayıtlar + her kaydın nesne yolu (`nesne`); BAYTLAR DEĞİL
    varliklar.json        logo/afiş/slogan kayıtları (`depo_varlik.listele`) — belge listesinde yoktu,
                          kullanıcının yüklediği veri olduğu için eklendi

MEDYA BAYTLARI BU ZIP'TE YOK (belge §5): 500 MB'lık bir galeri senkron ZIP
olmaz — kullanıcı onu galerinin klasör başına ZIP'iyle alır
(`GET /api/folders/{id}/download`), bu ZIP'in `klasorler.json`u o bağlantıları
taşır. `saglayici_meta` DÖKÜLMEZ: sağlayıcının `request_id`/`usage`ı
platformun operasyon verisi, kullanıcının kişisel verisi değil (`kuyruk._json`
zaten dışarıda tutuyor; burada da aynı işlev kullanılıyor, ikinci bir döküm
yazılmıyor).

AKIŞ `depo_klasor.zip_disa_aktar`ın deyimiyle: DB'ye dokunan her şey
üreticiden ÖNCE burada toplanır (`StreamingResponse` gövdeyi rota döndükten
sonra çeker, isteğin `Session`ı o sırada kapanmış olabilir), sonra
`dosya.YazmaTamponu` üstünden `zipfile` parça parça yazılır. Veri küçük
(metin), tek `BytesIO` da olurdu; aynı deyimi sürdürmek iki ZIP yolunun
ayrışmamasının garantisi.

KULLANICININ BAĞLAMINDA koşar: her depo işlevi `kullanici_id` süzgeci taşır
(tests/test_galeri_db.py) ve RLS `sahip` politikası ikinci kapı — başkasının
satırı bu ZIP'e giremez. Kota (saatte 1) ROTADA (`routers/hesap.py`): bu
modül HTTP bilmez.

Bu modül kullanıcıya KONUŞMAZ (tests/test_i18n.py sınıflandırması): dosya
adları ve sütun başlıkları ASCII kimlik, cümle değil.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import uuid
import zipfile
from collections.abc import Iterator
from typing import IO, Any, cast

from sqlalchemy.orm import Session

from services import (
    ayar,
    defter,
    depo_klasor,
    depo_medya,
    depo_palet,
    depo_sohbet,
    depo_varlik,
    dosya,
    kuyruk,
    zaman,
)
from services.tablolar import Kullanici

# Arşivdeki dosya adları — testler ve belge bu demeti okur (elle tutulan liste; bekçisi
# tests/test_hesap_silme.py `zip`in adlarını birebir karşılaştırır).
DOSYALAR: tuple[str, ...] = ("hesap.json", "kredi_hareketleri.csv", "siparisler.csv", "isler.json",
                             "sohbetler.json", "paletler.json", "klasorler.json", "medya.json",
                             "varliklar.json")
HAREKET_SUTUNLARI: tuple[str, ...] = ("id", "olusturuldu", "tur", "kova", "miktar", "is_id", "aciklama")
SIPARIS_SUTUNLARI: tuple[str, ...] = ("id", "olusturuldu", "urun", "tutar_kurus", "para_birimi", "sebep")


def _json_bayt(veri: Any) -> bytes:
    # `ensure_ascii=False`: prompt'lar ve sohbetler Türkçe — `\\u00e7` ile dolu bir döküm
    # "taşınabilir" değil, okunmaz. `default=str` UUID/datetime için.
    return json.dumps(veri, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _csv_bayt(sutunlar: tuple[str, ...], satirlar: list[dict[str, Any]]) -> bytes:
    # LF satır sonu (`lineterminator`): csv modülünün öntanımlısı CRLF ve depo disiplini LF (.gitattributes).
    tampon = io.StringIO()
    yazici = csv.DictWriter(tampon, fieldnames=list(sutunlar), extrasaction="ignore", lineterminator="\n")
    yazici.writeheader()
    for satir in satirlar:
        yazici.writerow({s: ("" if satir.get(s) is None else satir.get(s)) for s in sutunlar})
    return tampon.getvalue().encode("utf-8")


def _damga(t: dt.datetime | None) -> str | None:
    return zaman.damga_utc(t) if t is not None else None


def _hesap(kullanici: Kullanici, an: dt.datetime) -> dict[str, Any]:
    return {
        "id": str(kullanici.id),
        "eposta": kullanici.eposta,
        "dil": kullanici.dil,
        "plan": kullanici.plan,
        "plan_bitis": _damga(kullanici.plan_bitis),
        "olusturuldu": _damga(kullanici.olusturuldu),
        "dogrulandi_at": _damga(kullanici.dogrulandi_at),
        "sartlar_kabul_at": _damga(kullanici.sartlar_kabul_at),
        "sartlar_surumu": kullanici.sartlar_surumu,
        "disa_aktarildi": _damga(an),
        # Medya baytları bu arşivde yok; klasör başına ZIP bağlantıları `klasorler.json`da.
        "medya_indirme": "/api/folders/{folder_id}/download",
    }


def icerik(db: Session, kullanici_id: uuid.UUID, *, an: dt.datetime | None = None) -> list[tuple[str, bytes]]:
    """Arşivin dosyaları `(ad, bayt)` sırasıyla (`DOSYALAR`); kullanıcı satırı yoksa boş liste.

    `zip_akisi`nden ayrı ki testler ZIP'i açmadan içeriği okuyabilsin ve rota
    dosya listesini HTTP başlığına yazabilsin.
    """
    an = an if an is not None else zaman.an()
    kullanici = db.get(Kullanici, kullanici_id)
    if kullanici is None:
        return []
    hareketler = [defter._json(h) for h in defter.hareketler(db, kullanici_id, limit=None)]
    siparisler = defter.siparisler(db, kullanici_id, limit=None)
    klasorler = [{**k, "indirme": f"/api/folders/{k['id']}/download"}
                 for k in depo_klasor.listele(db, kullanici_id)]
    onek = f"{ayar.KULLANICILAR_DIZINI}/{kullanici_id}"
    medya = [{**m, "nesne": f"{onek}/output/{m.get('filename')}"} for m in depo_medya.hepsi(db, kullanici_id)]
    varliklar = [{**v, "nesne": f"{onek}/assets/{v.get('kind')}/{v.get('filename')}"}
                 for v in depo_varlik.listele(db, kullanici_id)]
    return [
        ("hesap.json", _json_bayt(_hesap(kullanici, an))),
        ("kredi_hareketleri.csv", _csv_bayt(HAREKET_SUTUNLARI, hareketler)),
        ("siparisler.csv", _csv_bayt(SIPARIS_SUTUNLARI, siparisler)),
        ("isler.json", _json_bayt(kuyruk.listele(db, kullanici_id, limit=None))),
        ("sohbetler.json", _json_bayt(depo_sohbet.hepsi(db, kullanici_id))),
        ("paletler.json", _json_bayt(depo_palet.listele(db, kullanici_id))),
        ("klasorler.json", _json_bayt(klasorler)),
        ("medya.json", _json_bayt(medya)),
        ("varliklar.json", _json_bayt(varliklar)),
    ]


def zip_akisi(db: Session, kullanici_id: uuid.UUID, *, an: dt.datetime | None = None) -> Iterator[bytes] | None:
    """ZIP'in bayt üreticisi; kullanıcı satırı yoksa `None`. DB işi burada biter, üretici yalnız sıkıştırır."""
    dosyalar = icerik(db, kullanici_id, an=an)
    if not dosyalar:
        return None

    def _uret() -> Iterator[bytes]:
        akis = dosya.YazmaTamponu()
        # `ZipFile` `IO[bytes]` ister; tampon yazma yüzünü veriyor (depo_klasor.zip_disa_aktar'ın notu).
        with zipfile.ZipFile(cast("IO[bytes]", akis), "w", zipfile.ZIP_DEFLATED) as zf:
            for ad, veri in dosyalar:
                zf.writestr(ad, veri)
                yield akis.bosalt()
        yield akis.bosalt()

    return _uret()
