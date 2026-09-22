# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İş uçları: kullanıcının üretim işleri — liste, tekil, iptal, akış, yeniden gönder; kota (Faz 2 / 4-5, 8); kredi (Faz 3 / 6).

Üretim rotaları (routers/uretim.py) 202 ile bir `is` döndürüyor; tarayıcı
sonucu buradan izler. 4. görevde izleme core.js'in 2 sn yoklamasıydı
(`GET /api/isler/{id}`); 5. görevde asıl yol SSE akışı `GET /api/isler/akis`
(static/isler.js paneli), yoklama `GET /api/isler`in 3 sn'lik YEDEK yolu —
`EventSource` üç kez düşerse istemci ona geçer (belge §5, K2).

HEPSİ KAPILI (`kimlik.aktif_kullanici`) ve SAHİP SÜZGEÇLİ: her sorgu
`kuyruk`un kullanıcı tarafı imzasından geçer (`(db, kullanici_id, …)`),
başkasının işi "yok" sayılır — 404, 403 değil (id uzayı sızmasın; depo
modüllerinin kararı). Dizin okumazlar: ayar nesnesi almazlar
(tests/test_kimlik.py `DIZINSIZ_KAPILI`).

`istek` DÖKÜLMEZ (`kuyruk._json`): prompt ve girdi anahtarları içeride kalır;
sonuç `sonuc.medya` id listesi, kayıtların kendisi `GET /api/history`den.
"Yeniden gönder" bu yüzden SUNUCUDA (`POST /api/isler/{id}/yeniden`): istemci
`istek`i görmez, kopyayı rota alır; girdi nesneleri KOPYALANMAZ, yeni iş eski
anahtarlara REFERANS verir (karar aşağıda, `is_yeniden`).

SSE AKIŞI (`akis`) — `async def`, `text/event-stream`:
* Döngü `AKIS_YOKLAMA_SN`de bir `kuyruk.listele(since=…)` sorar ve bunu
  `run_in_threadpool` içinde, YALNIZ SORGU SÜRESİNCE açık bir `Session`la yapar
  (`_akis_sorgusu`). İsteğin `OTURUM`u imzada duruyor ama gövdeye GİRMİYOR:
  rota ondan yalnız motoru alır (`db.get_bind()` — testlerin override'ı da
  buradan geçer, `app.state.motor` orada yok) ve `scope="function"` o
  oturumu rota DÖNERKEN kapatır; gövde akmaya başladığında isteğin bağlantısı
  çoktan havuza dönmüş. Akış dakikalarca açık ve havuz küçük (`pool_size=2`,
  services/db.py): bağlantıyı akış boyunca tutan bir akış ikinci sekmede
  bütün rotaları bekletirdi.
* `since` ÖRTÜŞMELİ (`AKIS_ORTUSME_SN`): `listele` "değişti"yi
  `GREATEST(olusturuldu, basladi, bitti) > since` ile ölçüyor ve o damgalar
  Python'da yazılıp commit'i biraz SONRA geliyor — bir turun sorgusundan
  sonra commit'lenen ama damgası sorgudan ÖNCEKİ bir satır, örtüşme olmadan
  bir sonraki turda da görünmezdi. Aynı satırın iki kez gelmesi zararsız
  (istemci id'ye göre yeniden çizer; sunucu da aynı hâli ikinci kez yazmaz).
* Olay `id:` sorgu ANI (ISO, mikrosaniyeli, dilimli): tarayıcı düşüp
  yeniden bağlanınca `Last-Event-ID` olarak geri gelir ve `?since=` ile aynı
  ayrıştırıcıdan (`_since`) geçer — kaldığı yerden sürer.
* İlk turda (`since` yok) AKTİF işler + son `AKIS_ILK_PENCERE_SN` içinde
  DEĞİŞENLER yazılır. Yalnız aktifler yetmiyordu, ÖLÇÜLDÜ (E2E "iki iş,
  yenileme"): istemci listeyi çekiyor, sonra akışa bağlanıyor ve bir iş o
  ARADA bitiyorsa artık aktif değil, ilk turda gelmez, sonraki turlar da
  "bağlandıktan sonra değişen"i sorar — satır panelde `calisiyor` diye
  donuyordu. Pencere o aralığı kapatır; geçmişin kalanı listeden.
* `: kalp` yorumu `AKIS_KALP_SN`de bir (vekiller boş bağlantıyı 30-60 sn'de
  kesiyor), `AKIS_AZAMI_SN` sonra akış KENDİNİ kapatır (uzun ömürlü bağlantı
  sızıntısı sınıfı; `EventSource` kendiliğinden yeniden bağlanır).
* `Cache-Control: no-store` ve `X-Accel-Buffering: no`: tamponlayan bir vekil
  olayları biriktirir, ikincisi nginx'e "biriktirme" der.
Üçü modül sabiti (env değil): testler `monkeypatch.setattr` ile saniyenin
altına çeker; `.env.example`/`ALTYAPI` envanteri büyümez.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import uuid
from collections.abc import AsyncIterator, Mapping

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import catalog
import i18n
from services import defter, dil, kapilar, kimlik, kota, kuyruk, planlar, platform_anahtari, zaman
from services.db import OTURUM
from services.tablolar import Kullanici

router = APIRouter()

# SSE akışının üç zamanı (belge §5): sorgu aralığı 1,5 sn (üretim dakikalarla
# ölçülüyor; daha sık sormak yalnız Postgres'e yük), kalp 15 sn, azami ömür
# 10 dk. Örtüşme 2 sn (gerekçe modül başında). Modül sabiti — testler yamalar.
AKIS_YOKLAMA_SN = 1.5
AKIS_KALP_SN = 15.0
AKIS_AZAMI_SN = 600.0
AKIS_ORTUSME_SN = 2.0
# İlk turun geriye bakışı (gerekçe modül başında): liste → bağlanma arası
# saniyelerle ölçülür, 30 sn yavaş bir ağda bile o aralığı örter.
AKIS_ILK_PENCERE_SN = 30.0

# Öntanımlı görünümün genişliği: "aktifler + son 50" (belge §4). Aktifler
# ayrı çekilir ki 51. sıraya düşmüş bir `bekliyor` iş listeden kaybolmasın —
# sayıları zaten tavanla sınırlı (kapilar.ES_ZAMANLI_IS_VARSAYILAN).
SON_IS_SAYISI = 50


def _since(ham: str | None) -> dt.datetime | None:
    """`?since=` — `zaman.damga` biçimi (`2026-09-18T12:00:00`, dilimsiz = yerel saat) ya da
    dilimli ISO 8601. Bozuksa 422: sessizce "hepsi"ni döndürmek istemciye
    yanlış bir "değişen yok / hepsi değişti" resmi çizerdi."""
    if not ham:
        return None
    try:
        an = dt.datetime.fromisoformat(ham)
    except ValueError:
        raise HTTPException(status_code=422, detail=i18n.t("err.bad_since", dil.aktif()))
    # Dilimsiz değer `damga`nın yazdığı YEREL saat (services/zaman.py); sorgu
    # `timestamptz` sütunlarla karşılaştırıyor, dilim burada bağlanır.
    return an.astimezone() if an.tzinfo is None else an


@router.get("/api/isler")
def isleri_listele(since: str | None = None, db: Session = OTURUM,
                   kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """`since` yoksa aktifler + son 50 (en yeni üstte); varsa o andan sonra değişenler."""
    an = _since(since)
    isler = kuyruk.listele(db, kullanici.id, since=an, limit=SON_IS_SAYISI)
    if an is None:
        gorunen = {i["id"] for i in isler}
        aktifler = kuyruk.listele(db, kullanici.id, limit=SON_IS_SAYISI,
                                  durumlar=kuyruk.AKTIF_DURUMLAR)
        isler += [i for i in aktifler if i["id"] not in gorunen]
        # `listele` her iki parçayı en yeni üstte veriyor; birleşik liste de öyle kalsın
        # (`olusturuldu` `zaman.damga` biçimi — sözlük sırası, dize sırasıyla aynı).
        isler.sort(key=lambda i: i["olusturuldu"] or "", reverse=True)
    return {"isler": isler}


@router.get("/api/kota")
def kota_durumu(db: Session = OTURUM,
                kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Kullanıcının kotası (Faz 2 / 8; belge §6 devri): günlük kalan kredi, saatlik iş sayısı, pencerelerin açılışı.

    `services/kota.py`nin İKİ kapısıyla aynı sorgular (`gunluk_durum`,
    `saatlik_durum`) — panel "günlük kalan"ı buradan okur (static/isler.js),
    kapının 429'unu beklemeden. Tavan kullanıcının ezmesi (`gunluk_kredi_tavani`)
    ya da ortam; `kalan` yalnız PLATFORM anahtarıyla koşan işlere karşı anlamlı
    (kendi anahtarı sayılmaz, services/kota.py). `acilis`: pencere içindeki en
    eski sayılan işin düşeceği an (`zaman.damga_utc` — öteki API damgalarıyla
    aynı dilimli biçim; tarayıcı `Date`e verirse doğru okur), sayılan iş yoksa
    `None`.
    """
    def _acilis(en_eski: dt.datetime | None, pencere: dt.timedelta) -> str | None:
        return zaman.damga_utc(en_eski + pencere) if en_eski is not None else None

    an = zaman.an()
    gunluk_tavan = (kullanici.gunluk_kredi_tavani if kullanici.gunluk_kredi_tavani is not None
                    else kota.gunluk_kredi_tavani())
    toplam, gunluk_en_eski = kota.gunluk_durum(db, kullanici.id, an)
    sayi, saatlik_en_eski = kota.saatlik_durum(db, kullanici.id, an)
    return {
        "gunluk": {"tavan": gunluk_tavan, "kullanilan": toplam, "kalan": max(0, gunluk_tavan - toplam),
                   "acilis": _acilis(gunluk_en_eski, kota.GUNLUK_PENCERE)},
        "saatlik": {"tavan": kota.saatlik_is_tavani(), "sayi": sayi,
                    "acilis": _acilis(saatlik_en_eski, kota.SAATLIK_PENCERE)},
    }


KREDI_HAREKET_SINIRI = 20
# Faz 4 / 4: bölmenin sipariş özeti — tam liste ve faturalar Polar portalında (K7).
KREDI_SIPARIS_SINIRI = 10


def _sonraki_ay_basi(an: dt.datetime) -> dt.datetime:
    """`an`ın ayından sonraki ayın ilk günü, 00:00, AYNI dilimde — `aylik_hibe_yaz`ın `%Y-%m` anahtarı
    `zaman.an()`ın yerel ayından kurulur; sonraki hibe tarihi de aynı takvimden okunmalı, UTC'den değil."""
    yil, ay = (an.year + 1, 1) if an.month == 12 else (an.year, an.month + 1)
    return an.replace(year=yil, month=ay, day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("/api/kredi")
def kredi_durumu(db: Session = OTURUM,
                 kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Kullanıcının kredisi (Faz 3 / 6; Faz 4 / 2 iki kova): bakiye (hibe kovası), paket_bakiye, toplam, plan,
    plan_bitis, hibe, sonraki hibe, plan kuralları, son 20 hareket.

    `/api/kota`nın YANINA, yerine değil: kota günlük tavan (kötüye kullanım, K9),
    kredi bakiye (para) — panel ikisini ayrı okur. Plan kuralları (`filigran`,
    `video`) `PLANLAR`dan geliyor ki arayüz plan kataloğunu tekrar etmesin;
    `hibe` planın aylık sayısı (ortam `KROMIS_FREE_AYLIK_HIBE`), `sonraki_hibe`
    gelecek ayın ilk günü (`zaman.damga_utc`, öteki damgalarla aynı biçim).
    Hareketler `defter.hareketler` (en yeni üstte, kullanıcı süzgeçli; RLS ikinci
    kapı) ve `defter._json` (admin id / idempotency anahtarı DÖKÜLMEZ; `kova` dökülür). Plan
    `kapilar.kullanici_plani`: yüklü nesneden, değilse DB'den (ayrılmış nesne dersi).

    İKİ KOVA (Faz 4 / 2, K3): `bakiye` HİBE kovası olarak KALIR (Faz 3'ün alanı,
    `kullanicilar.bakiye` sütunuyla aynı şey — anlamı değişmesin), `paket_bakiye`
    paket kovası, `toplam` ikisinin toplamı — composer "kalan" ve bölmenin büyük
    sayısı onu okur. `plan_bitis` iptal edilmiş aboneliğin dönem sonu (3. görev
    yazar) — bölmenin "dönem sonunda ücretsiz plana geçer" satırı (Faz 4 / 4).

    `siparisler` (Faz 4 / 4): son 10 Polar siparişi ÖZET (`defter.siparisler` —
    tarih, ürün adı, tutar, para birimi, sebep); fatura sayfası bizde yok (K7),
    bölme "faturalar Polar portalında" der. `/api/odeme/*`ye ayrı bir uç
    açılmadı: bölme zaten bu cevabı okuyor, ikinci istek ikinci yarış olurdu.
    """
    plan_adi = kapilar.kullanici_plani(db, kullanici)
    plan = planlar.PLANLAR[plan_adi]
    b = defter.bakiye(db, kullanici.id)
    plan_bitis = defter.plan_bitis_oku(db, kullanici.id)
    return {
        "bakiye": b.hibe,
        "paket_bakiye": b.paket,
        "toplam": b.toplam,
        "plan": plan_adi,
        "plan_bitis": zaman.damga_utc(plan_bitis) if plan_bitis is not None else None,
        "hibe": plan.aylik_hibe,
        "sonraki_hibe": zaman.damga_utc(_sonraki_ay_basi(zaman.an())),
        "filigran": plan.filigran,
        "video": plan.video,
        "son_hareketler": [defter._json(h) for h in
                           defter.hareketler(db, kullanici.id, limit=KREDI_HAREKET_SINIRI)],
        "siparisler": defter.siparisler(db, kullanici.id, limit=KREDI_SIPARIS_SINIRI),
    }


def _akis_sorgusu(motor: Engine, kullanici_id: uuid.UUID, since: dt.datetime | None) -> list[dict]:
    """Bir tur: `Session` yalnız bu sorgu için açılır ve kapanır (gerekçe modül başında)."""
    with Session(motor) as db:
        if since is not None:
            return kuyruk.listele(db, kullanici_id, since=since, limit=SON_IS_SAYISI)
        pencere = zaman.an() - dt.timedelta(seconds=AKIS_ILK_PENCERE_SN)
        yeni = kuyruk.listele(db, kullanici_id, since=pencere, limit=SON_IS_SAYISI)
        gorunen = {i["id"] for i in yeni}
        aktifler = kuyruk.listele(db, kullanici_id, limit=SON_IS_SAYISI,
                                  durumlar=kuyruk.AKTIF_DURUMLAR)
        yeni += [i for i in aktifler if i["id"] not in gorunen]
        yeni.sort(key=lambda i: i["olusturuldu"] or "", reverse=True)
        return yeni


async def _akis(request: Request, motor: Engine, kullanici_id: uuid.UUID,
                since: dt.datetime | None) -> AsyncIterator[str]:
    """Olay üreticisi. `retry:` ilk satır: başlıklar hemen gider (istemci `open` görür)."""
    yield f"retry: {int(AKIS_YOKLAMA_SN * 2000)}\n\n"
    baslangic = asyncio.get_running_loop().time()
    son_kalp = baslangic
    son_hal: dict[str, str] = {}
    while True:
        if await request.is_disconnected():
            return
        simdi_dongu = asyncio.get_running_loop().time()
        if simdi_dongu - baslangic >= AKIS_AZAMI_SN:
            return
        an = zaman.an()
        sorgu_since = since - dt.timedelta(seconds=AKIS_ORTUSME_SN) if since is not None else None
        isler = await run_in_threadpool(_akis_sorgusu, motor, kullanici_id, sorgu_since)
        since = an
        yazildi = False
        # `listele` en yeni üstte veriyor; olaylar eskiden yeniye gitsin ki
        # istemcinin "son gelen üstte" kuralı listeyle aynı sırayı üretsin.
        for is_ in reversed(isler):
            veri = json.dumps(is_, ensure_ascii=False, separators=(",", ":"))
            if son_hal.get(is_["id"]) == veri:
                continue
            son_hal[is_["id"]] = veri
            yield f"id: {an.isoformat()}\nevent: is\ndata: {veri}\n\n"
            yazildi = True
        if yazildi:
            son_kalp = simdi_dongu
        elif simdi_dongu - son_kalp >= AKIS_KALP_SN:
            yield ": kalp\n\n"
            son_kalp = simdi_dongu
        await asyncio.sleep(AKIS_YOKLAMA_SN)


@router.get("/api/isler/akis")
async def isleri_akit(request: Request, since: str | None = None, db: Session = OTURUM,
                      kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> StreamingResponse:
    """SSE: değişen işler `event: is` olarak; `Last-Event-ID` ya da `?since=` ile kaldığı yerden.

    SIRA BAĞLAYICI: bu rota `/api/isler/{is_id}`ten ÖNCE tanımlı olmak
    zorunda. Starlette yolu tanım sırasıyla eşler ve `{is_id}` "akis"i de
    eşler — UUID doğrulaması eşleşmeden SONRA koşar ve 422 verir (ölçüldü:
    rota tekilin altındayken akış 422 dönüyordu). Aşağı taşınırsa
    tests/test_isler_route.py ilk akış testinde kırmızıya döner.
    """
    # Motor isteğin oturumundan; oturumun kendisi gövdeye girmez (modül başı).
    motor = db.get_bind()
    assert isinstance(motor, Engine)
    # `Last-Event-ID` başlığı önce: tarayıcının yeniden bağlanması onu taşır,
    # `?since=` elle kurulan istemcinin (test, curl) yolu.
    an = _since(request.headers.get("last-event-id") or since)
    return StreamingResponse(
        _akis(request, motor, kullanici.id, an),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _bul(db: Session, kullanici_id: uuid.UUID, is_id: uuid.UUID) -> dict:
    is_ = kuyruk.bul(db, kullanici_id, is_id)
    if is_ is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.is_bulunamadi", dil.aktif()))
    return is_


@router.get("/api/isler/{is_id}")
def is_getir(is_id: uuid.UUID, db: Session = OTURUM,
             kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Tek iş; `is_id` UUID biçiminde değilse çerçeve 422 verir (yol eşleşmez)."""
    return {"is": _bul(db, kullanici.id, is_id)}


@router.post("/api/isler/{is_id}/iptal")
def is_iptal(is_id: uuid.UUID, db: Session = OTURUM,
             kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Yalnız `bekliyor` işi iptal eder; başka durumdaki iş 409, olmayan/başkasının işi 404.

    `kuyruk.iptal` tek `UPDATE … WHERE durum='bekliyor'`: işçi aynı anda `al`
    ile satırı kilitlemişse bu ifade onun commit'ini bekler, sonra 0 satır
    görür — yani "çalışıyor" cevabı bir yarışın kaybedilmiş hâli değil,
    Postgres'in satır kilidinin verdiği kesin cevap. Çalışan iş İPTAL EDİLMEZ:
    sağlayıcı çağrısı çoktan gitti ve faturalandı (K8), işçi sonucu yazar.

    İptal edilen işin rezervi geri (Faz 3 / 2, K2): `defter.iade` iptalle aynı
    transaksiyonda, kullanıcının bağlamında (`sahip` politikası yazar); BYOK iş
    rezerv taşımaz, `iade` `None` döner. Yalnız `bekliyor` iptal edildiği için
    iş hiç koşmadı — sağlayıcı faturası yok, iade tam.
    """
    if kuyruk.iptal(db, kullanici.id, is_id):
        defter.iade(db, is_id)
        return {"is": _bul(db, kullanici.id, is_id)}
    is_ = _bul(db, kullanici.id, is_id)      # yoksa 404
    raise HTTPException(status_code=409,
                        detail=i18n.t("err.is_iptal_edilemez", dil.aktif(), durum=is_["durum"]))


@router.post("/api/isler/{is_id}/yeniden", status_code=202)
def is_yeniden(is_id: uuid.UUID, db: Session = OTURUM,
               kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
               kimlikler: Mapping[str, str] = kimlik.KIMLIKLER) -> dict:
    """`hata`/`iptal` bir işi AYNI `istek`le yeni bir iş olarak kuyruğa koyar; 202 + yeni `is`.

    Neden sunucuda: `istek` (prompt, girdi anahtarları) `_json`la dökülmüyor
    (§4 sözleşmesi) ve üretim rotaları anahtar değil bayt/galeri id'si alıyor
    — istemcinin "aynı isteği yeniden POST etmesi" ya `istek`i dökmek ya
    girdi baytlarını tarayıcıda saklamak demekti (yenilemede kaybolur).

    GİRDİ NESNELERİ KOPYALANMAZ, REFERANS VERİLİR: yeni işin `istek.girdiler`i
    eski `isler/<eski_id>/…` anahtarlarına bakar. Kopya, her yeniden gönderimde
    referans görselleri ikinci kez yazmak demekti; 30 günlük saklama (10)
    satırla birlikte düşürürken bir işin dizinini ancak ona bakan hiçbir satır
    kalmadığında siler (`artik_dosya.py`nin ölçütü zaten satır, dosya adı değil).
    `arena_id` DÜŞER: tur çoktan kapandı, beşinci bir sütun `fillArenaSlot`ın
    beklediği bir şey değil — yeniden gönderilen iş tek başına koşar.

    Sıra üretim rotalarınınki (routers/uretim.py `_kapilar`): kaynak yok → 404;
    durum uymuyor → 409; plan kapsamıyor → 403 (Faz 3 / 3, `check_plan`;
    katalogdan düşmüş modelde sorulmaz); anahtar yok → 409; eş zamanlılık /
    saatlik iş / günlük kredi → 429; satır. Yeniden gönderim de bir iş doğurur,
    yani planı, kotayı ve anahtar kapısını ATLAYAMAZ — aksi hâlde "hata →
    yeniden gönder" döngüsü tavanın (ve planın: ücretsize düşen kullanıcının
    eski video işi) arka kapısı olurdu. `anahtar_kaynagi` eski satırdan KOPYALANMAZ,
    yeniden çözülür: kullanıcı arada kendi anahtarını girmiş (ya da silmiş)
    olabilir. `kredi_tahmini` eski satırdan (aynı model, aynı adet); işçi
    gerçek maliyeti yine kendi yazar.

    YENİ İŞ = YENİ REZERV (Faz 3 / 2, K2): eski işin defteri kapalı (`hata`/
    `iptal` → iade edilmişti); yeni satır platform anahtarıyla doğuyorsa
    tahmini yeniden düşer (`kapilar.rezerve_kredi`, satırla aynı transaksiyon),
    yetmezse 402 ve satır geri alınır. Bakiye ön denetimi (`check_bakiye`)
    günlük tavandan sonra (K9). "hata → yeniden gönder" döngüsü bakiyeyi
    değil yalnız saatlik tavanı yer — bilerek: iade tam, rezerv tam.
    """
    eski = kuyruk.satir(db, kullanici.id, is_id)
    if eski is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.is_bulunamadi", dil.aktif()))
    if eski.durum not in kuyruk.KAPANMIS_DURUMLAR:
        raise HTTPException(status_code=409,
                            detail=i18n.t("err.is_yeniden_gonderilemez", dil.aktif(), durum=eski.durum))
    spec = catalog.image_model(eski.model) or catalog.video_model(eski.model)
    # Katalogdan düşmüş bir model: plan ve anahtar kapısı soracak kayıt yok, işçi
    # zaten "bilinmeyen model" ile düşürür (test_isci); kaynak `kullanici` sayılır
    # ki platform toplamına girmesin.
    if spec is not None:
        kapilar.check_plan(db, kullanici, spec, kimlikler)
    kaynak = (kapilar.check_anahtar(spec.credential, kimlikler) if spec is not None
              else platform_anahtari.KAYNAK_KULLANICI)
    kapilar.check_is_tavani(db, kullanici.id)
    kota.check_saatlik(db, kullanici.id)
    kota.check_gunluk(db, kullanici, eski.kredi_tahmini, kaynak)
    kapilar.check_bakiye(db, kullanici, eski.kredi_tahmini, kaynak)
    istek = dict(eski.istek or {})
    if istek.get("arena_id") is not None:
        istek["arena_id"] = None
    yeni = kuyruk.ekle(db, kullanici.id, eski.tur, istek, eski.model, eski.kredi_tahmini,
                       anahtar_kaynagi=kaynak)
    kapilar.rezerve_kredi(db, kullanici, yeni.id, eski.kredi_tahmini, kaynak)
    return {"is": kuyruk._json(yeni)}
