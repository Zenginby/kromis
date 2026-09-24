# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Hesap uçları — kayıt, doğrulama, giriş, çıkış, sıfırlama, `/giris` sayfası (Faz 1 / 3); silme ve dışa aktarma (Faz 4 / 5); şartlar onayı (Faz 4 / 6).

On bir rota: `POST /api/hesap/{kayit,dogrula,giris,cikis,sifirla,
sifirla/dogrula}`, `GET /api/hesap/ben`, `GET /giris` (belge Faz 1 §3) +
`POST /api/hesap/sil`, `GET /api/hesap/disa-aktar` (Faz 4 §5) +
`POST /api/hesap/sartlar-kabul` (Faz 4 §6). HTTP burada
(gövde, durum kodu, çerez, cümle); hesap mantığı `services/hesap.py`de, posta
`services/posta.py`de, kapı `services/kimlik.py`de, dışa aktarma arşivi
`services/disa_aktar.py`de.

ŞARTLAR ONAYI (Faz 4 / 6, K11 tıkla-onay): kayıt `sartlar: true` olmadan 422
(`models.KayitIstegi`); başarılı kayıt `sartlar_kabul_at` + `sartlar_surumu =
hukuk.HUKUK_SURUMU` yazar (`hesap.sartlar_damgala` — yeniden kayıt olan
doğrulanmamış hesapta da: onay bu isteğin). Var olan kullanıcı sürüm değişince
`GET /api/hesap/ben` `sartlar_guncel: false` görür, ayarlar banner'ı
`POST /api/hesap/sartlar-kabul` ile bugünkü sürümü damgalar
(`odeme.sartlar_kabul_yaz` — checkout'un 412 kapısıyla AYNI yazıcı, iki yazar
iki sürüm yazmasın). Sürüm sabiti TEK yerde: `services/hukuk.py`.

HESAP SİLME (Faz 4 / 5, K9) — anonimleştir + kilitle ANINDA, içerik 7 gün
sonra bakım turunda (`services/isci.py silme_turu`), defter ve sipariş KALIR.
Parola onayı `giris` ile AYNI kapıdan geçer: kilit (429) → parola (401, aynı
metin, aynı süre) — aksi hâlde bu uç oturumu çalınmış bir hesapta sınırsız
parola denemesi veren bir kâhin olurdu; yanlış parola `giris_denemeleri`ne
yazılır (o yüzden 401 `JSONResponse`, `HTTPException` değil — modül başındaki
commit gerekçesi). Parolasız hesap (Google, 3b — bugün yok) 409
`err.hesap_parolasiz`: belge e-posta jetonlu `sil-dogrula` akışını yazmıştı;
`jetonlar.amac` CHECK'i yeni bir amaç için GÖÇ ister ve bugün parolasız hesap
açan bir yol yok — kullanıcı "parolamı unuttum" ile (adresi kanıtlayarak) parola
belirleyip siler, aynı kanıt. Polar aboneliği ve e-posta silmeyi DURDURMAZ:
ikisi de dış hizmet; düşerlerse WARNING (`hesap.silme_abonelik`,
`hesap.silme_posta`) ve sahip elle kapatır — KVKK md. 7 silme hakkı bir dış
servisin ayakta olmasına bağlanamaz.

DIŞA AKTARMA saatte 1 (belge §5, `check_saatlik` deseni): sayaç bu sürecin
belleğinde (`_DISA_AKTARIMLAR`) — `giris_denemeleri.tur` CHECK'li ve yeni tür
göç isterdi; tek web süreci (K11) için bellek yeter, yeniden başlatma sayacı
sıfırlar (kabul edilen bedel: en kötü ihtimal bir ZIP daha). Kullanıcı başına
bir damga, silinen hesabın damgası oturumla birlikte anlamsızlaşır.

AYAR NESNESİ `ayar.genel` (Faz 1 / 4): bu rotaların altısı oturum İSTEMEZ —
kayıt olmadan kullanıcı, kullanıcı olmadan kullanıcı dizini yok; okudukları
tek şey paylaşılan `data_dir` (`hata.log`) ve `static_dir` (`/giris`).
`ayar.ayarlar` kullanıcıya göre kurulur ve kapıyı içinde taşır; burada o
kapı ya anlamsız (kayıt) ya da tam tersi (giriş) olurdu. `ben` ve `cikis`
kapıyı `kimlik.aktif_kullanici` ile doğrudan alıyor.

KULLANICI NUMARALANDIRMASINA KARŞI üç cevap AYNI (belge: "kayıt ve sıfırlama
cevapları e-posta var/yok ayırt ETMEZ"): `kayit` yeni hesapta da, var olan
doğrulanmamış hesapta da, var olan DOĞRULANMIŞ hesapta da `{"ok": true}` der
ve üçünde de bir e-posta gider (sonuncusuna "zaten hesabın var" iletisi — bu
hem kullanıcıya doğru bilgiyi verir hem cevap SÜRESİNİ eşitler: üç dalda da
bir argon2 hesabı ve bir posta çağrısı var). `giris` yanlış parolada ve
bilinmeyen e-postada aynı 401'i aynı sürede döner (`hesap.parola_dogru`nun
sahte özeti). `sifirla` bilinmeyen adreste posta göndermez; gövde aynı,
süre farkı posta sağlayıcısının gecikmesi kadar — bilinen ve kabul edilen
sınır (belgede yazılı).

BAŞARISIZ GİRİŞ 401'İ `JSONResponse`, `HTTPException` DEĞİL — ve bu deponun
commit kuralının doğrudan sonucu: `services/db.py::oturum` istisnada
ROLLBACK yapıyor, yani `HTTPException(401)` fırlatılsa aynı istekte yazılan
`giris_denemeleri` satırı da geri alınır ve hız sınırı hiç dolmazdı (11.
deneme 429 vermez). Başarısız girişin KAYDI isteğin başarısıdır; rota
normal döner, bağımlılık commit eder. Doğrulanmamış hesabın 403'ü de aynı
sebeple: o dalda yeni bir doğrulama jetonu yazılıyor ve iletisi gidiyor.
Hiçbir şey yazmayan hatalar (geçersiz jeton, 429, posta hatası) `HTTPException`
olarak kalıyor — rollback orada doğru davranış.

POSTA HATASI 503: ileti gitmediyse "gönderdik" denmez; kayıt rotasında
rollback yeni kullanıcı satırını da geri alır, kullanıcı yeniden dener.
Sebep `hata.log`a (yalnız durum kodu; alıcı adresi günlüğe girmez).
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

import errlog
import i18n
from models import (
    GirisIstegi,
    JetonIstegi,
    KayitIstegi,
    SifirlamaIstegi,
    SilmeIstegi,
    YeniParolaIstegi,
)
from services import (
    ayar,
    cerez,
    defter,
    depo_kimlik_bilgisi,
    dil,
    disa_aktar,
    gunluk,
    hesap,
    hukuk,
    isci,
    kimlik,
    kiraci,
    koken,
    kuyruk,
    odeme,
    planlar,
    polar,
    posta,
    sablon,
    zaman,
)
from services.db import OTURUM
from services.tablolar import Kullanici

router = APIRouter()

# `olay=hesap.*` satırlarının kaynağı (silme, abonelik/posta uyarıları); işleyici `kromis` kökünde.
_gunluk = logging.getLogger("kromis.hesap")

# Dışa aktarma kotası (gerekçe modül başında): kullanıcı → son aktarım anı; pencere 1 saat.
DISA_AKTARMA_PENCERESI = dt.timedelta(hours=1)
_DISA_AKTARIMLAR: dict[uuid.UUID, dt.datetime] = {}

# Lifespan koşmamış süreçte (`with`siz `TestClient`) postacı yok — `oturum`
# bağımlılığının `database_unavailable` koduyla aynı sınıf bir 503.
POSTACI_YOK = "mail_unavailable"


def _postaci(request: Request) -> posta.Postaci:
    postaci = getattr(request.app.state, "postaci", None)
    if postaci is None:
        raise HTTPException(status_code=503, detail=POSTACI_YOK)
    return postaci


def _gonder(request: Request, ileti: posta.Posta, ayarlar: ayar.Ayarlar) -> None:
    try:
        _postaci(request).gonder(ileti)
    except posta.PostaHatasi as e:
        errlog.safe_append(ayarlar.data_dir, f"posta gonderilemedi ({ileti.konu}): {e}")
        raise HTTPException(status_code=503,
                            detail=i18n.t("err.hesap_posta_gonderilemedi", dil.aktif()))


def _cok_deneme(saniye: int) -> HTTPException:
    """429 + `Retry-After` — belge §3. Metin saniyeyi de söylüyor: ön yüz başlığı okumaz."""
    return HTTPException(status_code=429,
                         detail=i18n.t("err.hesap_cok_deneme", dil.aktif(), saniye=saniye),
                         headers={"Retry-After": str(saniye)})


def _baglanti(request: Request, parametre: str, jeton: str) -> str:
    """`https://…/giris?dogrula=<jeton>` — sayfa parametreyi okuyup POST'a çevirir (static/giris.js)."""
    return f"{koken.taban(request)}/giris?{parametre}={jeton}"


def _ben(kullanici: Kullanici) -> dict:
    """`GET /api/hesap/ben`in gövdesi (belge: `{id, eposta, dil, is_admin}` + Faz 4 / 6 `sartlar_guncel`); giriş de aynısını döner.

    `sartlar_guncel`: onaylanan sürüm bugünkü metnin sürümü mü (`hukuk.guncel_mi`).
    Ön yüz (settings.js) `false` görünce "şartlar güncellendi" banner'ını çizer;
    sunucu kuralı burada, sayfa kopyalamaz.
    """
    return {"id": str(kullanici.id), "eposta": kullanici.eposta,
            "dil": kullanici.dil, "is_admin": kullanici.is_admin,
            "sartlar_guncel": hukuk.guncel_mi(kullanici.sartlar_surumu)}


def _dogrulama_gonder(request: Request, db: Session, kullanici: Kullanici,
                      an: dt.datetime, ayarlar: ayar.Ayarlar) -> None:
    """Yeni doğrulama jetonu + iletisi — kayıt ve doğrulanmamış giriş aynı yolu kullanıyor."""
    jeton = hesap.jeton_ver(db, kullanici, hesap.AMAC_DOGRULAMA, an)
    _gonder(request, posta.dogrulama_postasi(
        kullanici.eposta, _baglanti(request, "dogrula", jeton), dil.aktif(),
        saat=int(hesap.DOGRULAMA_OMRU.total_seconds() // 3600)), ayarlar)


def _ilk_hibe(db: Session, kullanici: Kullanici, an: dt.datetime) -> None:
    """Yeni hesaba AYIN hibesini hemen yatırır (Faz 3 / 3, K6) — bakım turunun 5 dk'sı beklenmez.

    Aynı anahtar (`defter.aylik_hibe_yaz`: `hibe:<u>:<YYYY-MM>`), aynı miktar
    (`PLANLAR["free"].aylik_hibe`; 0 ise hibe kapalı, satır yok): bakım turu bu
    ayı çakışık bulur, ikinci hibe yazmaz. Doğrulanmamış hesaba da yatar — hesap
    doğrulanmadan giriş yok (`giris` 403), yani harcayamaz; doğrulanmadan
    silinirse satır CASCADE ile gider. KİRACI BAĞLAMI ŞART: istek oturumsuz,
    `kredi_hareketleri`nin `sahip` politikası `app.kullanici_id` bekler —
    bağlamsız INSERT uygulama rolünde reddedilirdi (RLS; tests/test_planlar.py
    uygulama rolüyle ölçer). Transaksiyon açık (`kullanici_olustur` flush etti),
    `oturum=db` ayarı hemen yazar.
    """
    miktar = planlar.PLANLAR[planlar.PLAN_VARSAYILAN].aylik_hibe
    if miktar <= 0:
        return
    with kiraci.baglam(kullanici_id=kullanici.id, oturum=db):
        defter.aylik_hibe_yaz(db, kullanici.id, miktar, an)


@router.post("/api/hesap/kayit")
def kayit(req: KayitIstegi, request: Request,
          ayarlar: ayar.Ayarlar = Depends(ayar.genel), db: Session = OTURUM) -> dict:
    """Hesap açar (doğrulanmamış) ve doğrulama bağlantısını gönderir. Cevap her dalda aynı.

    Var olan DOĞRULANMAMIŞ hesaba yeniden kayıt: parola ve dil bu isteğinkiyle
    YENİLENİR ve doğrulama iletisi yeniden gider. Sahiplik henüz kimsede
    değil (adres doğrulanmadı), yani "ilk yazan kazanır" diye bir hak yok;
    adresin gerçek sahibi iletiyi alan kişi ve onun parolası geçerli olmalı.
    Doğrulanmış hesaba kayıt denemesi hesaba DOKUNMAZ, sahibine "zaten hesabın
    var" iletisi gider (gerekçe modül başında).
    """
    an = hesap.simdi()
    ip = hesap.ip_adresi(request)
    bekle = hesap.istek_kilidi(db, hesap.DENEME_KAYIT, ip, an)
    if bekle is not None:
        raise _cok_deneme(bekle)
    hesap.deneme_kaydet(db, hesap.DENEME_KAYIT, req.eposta, ip, an)
    kullanici = hesap.kullanici_bul(db, req.eposta)
    if kullanici is None:
        kullanici = hesap.kullanici_olustur(db, req.eposta, req.parola, dil.aktif())
        _ilk_hibe(db, kullanici, an)
        hesap.sartlar_damgala(kullanici, an, hukuk.HUKUK_SURUMU)
    elif kullanici.dogrulandi_at is None:
        kullanici.parola_ozeti = hesap.parola_ozeti(req.parola)
        kullanici.dil = dil.aktif()
        # Onay da bu isteğin: kutuyu işaretleyen kişi bu parolayı yazan kişi (modül başı).
        hesap.sartlar_damgala(kullanici, an, hukuk.HUKUK_SURUMU)
    else:
        hesap.parola_ozeti(req.parola)   # süre eşitliği (modül başı)
        _gonder(request, posta.mevcut_hesap_postasi(
            kullanici.eposta, f"{koken.taban(request)}/giris", kullanici.dil or dil.aktif()),
            ayarlar)
        return {"ok": True}
    _dogrulama_gonder(request, db, kullanici, an, ayarlar)
    return {"ok": True}


@router.post("/api/hesap/dogrula")
def dogrula(req: JetonIstegi, db: Session = OTURUM) -> dict:
    """E-posta bağlantısındaki jetonu tüketir, hesabı doğrulanmış işaretler."""
    an = hesap.simdi()
    kullanici = hesap.jeton_kullan(db, req.jeton, hesap.AMAC_DOGRULAMA, an)
    if kullanici is None:
        raise HTTPException(status_code=400,
                            detail=i18n.t("err.hesap_jeton_gecersiz", dil.aktif()))
    hesap.dogrulandi(kullanici, an)
    return {"ok": True}


@router.post("/api/hesap/giris", response_model=None)
def giris(req: GirisIstegi, request: Request,
          ayarlar: ayar.Ayarlar = Depends(ayar.genel), db: Session = OTURUM) -> Response:
    """Parola doğruysa oturum açar, çerezi kurar, `ben` gövdesini döner.

    Sıra bilinçli: önce kilit (429), sonra parola (401 — hem yanlış parola hem
    bilinmeyen adres, aynı metin, aynı süre), sonra doğrulama (403 + iletiyi
    yeniden gönder: parolayı bilen biri adresin sahibi olabilir ve gelen
    kutusundaki ilk ileti kaybolmuş olabilir — bu, ayrı bir "yeniden gönder"
    rotasının yerine geçiyor). Başarıda o e-postanın başarısız sayacı silinir
    ve eski parametreli bir özet varsa `verify_and_update` ile yenilenir.
    """
    an = hesap.simdi()
    ip = hesap.ip_adresi(request)
    bekle = hesap.giris_kilidi(db, req.eposta, ip, an)
    if bekle is not None:
        raise _cok_deneme(bekle)
    kullanici = hesap.kullanici_bul(db, req.eposta)
    if not hesap.parola_dogru(req.parola, kullanici.parola_ozeti if kullanici else None):
        hesap.deneme_kaydet(db, hesap.DENEME_GIRIS, req.eposta, ip, an)
        return JSONResponse({"detail": i18n.t("err.hesap_giris_hatali", dil.aktif())},
                            status_code=401)
    assert kullanici is not None and kullanici.parola_ozeti is not None
    if kullanici.dogrulandi_at is None:
        _dogrulama_gonder(request, db, kullanici, an, ayarlar)
        return JSONResponse({"detail": i18n.t("err.hesap_dogrulanmamis", dil.aktif())},
                            status_code=403)
    yeni_ozet = hesap.parola_yenilensin_mi(req.parola, kullanici.parola_ozeti)
    if yeni_ozet is not None:
        kullanici.parola_ozeti = yeni_ozet
    hesap.denemeleri_sil(db, req.eposta)
    jeton = hesap.oturum_ac(db, kullanici, ip, request.headers.get("user-agent"), an)
    cevap = JSONResponse(_ben(kullanici))
    cerez.oturum_yaz(cevap, jeton)
    return cevap


@router.post("/api/hesap/cikis")
def cikis(request: Request, response: Response,
          kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
          db: Session = OTURUM) -> dict:
    """Bu çerezin oturumunu düşürür ve çerezi siler; öteki cihazlar açık kalır."""
    ham = request.cookies.get(cerez.OTURUM_CEREZI)
    if ham:
        hesap.oturum_kapat(db, ham)
    cerez.oturum_sil(response)
    return {"ok": True}


@router.post("/api/hesap/sifirla")
def sifirla(req: SifirlamaIstegi, request: Request,
            ayarlar: ayar.Ayarlar = Depends(ayar.genel), db: Session = OTURUM) -> dict:
    """"Parolamı unuttum": hesap varsa sıfırlama bağlantısı gider; cevap her durumda aynı."""
    an = hesap.simdi()
    ip = hesap.ip_adresi(request)
    bekle = hesap.istek_kilidi(db, hesap.DENEME_SIFIRLAMA, ip, an)
    if bekle is not None:
        raise _cok_deneme(bekle)
    hesap.deneme_kaydet(db, hesap.DENEME_SIFIRLAMA, req.eposta, ip, an)
    kullanici = hesap.kullanici_bul(db, req.eposta)
    if kullanici is not None:
        jeton = hesap.jeton_ver(db, kullanici, hesap.AMAC_SIFIRLAMA, an)
        _gonder(request, posta.sifirlama_postasi(
            kullanici.eposta, _baglanti(request, "sifirla", jeton),
            kullanici.dil or dil.aktif(),
            dakika=int(hesap.SIFIRLAMA_OMRU.total_seconds() // 60)), ayarlar)
    return {"ok": True}


@router.post("/api/hesap/sifirla/dogrula")
def sifirla_dogrula(req: YeniParolaIstegi, db: Session = OTURUM) -> dict:
    """Yeni parola: jetonu tüketir, özeti yazar, BÜTÜN oturumları düşürür.

    Adres bu bağlantıyla kanıtlandı, yani doğrulanmamış bir hesap burada
    doğrulanmış olur (ayrı bir doğrulama iletisi beklemek anlamsız). Oturumların
    düşmesi K3'ün gerekçesi: sızan çerezin ömrü DB'den kesiliyor.
    """
    an = hesap.simdi()
    kullanici = hesap.jeton_kullan(db, req.jeton, hesap.AMAC_SIFIRLAMA, an)
    if kullanici is None:
        raise HTTPException(status_code=400,
                            detail=i18n.t("err.hesap_jeton_gecersiz", dil.aktif()))
    kullanici.parola_ozeti = hesap.parola_ozeti(req.parola)
    hesap.dogrulandi(kullanici, an)
    hesap.oturumlari_dusur(db, kullanici.id)
    hesap.denemeleri_sil(db, kullanici.eposta)
    return {"ok": True}


@router.get("/api/hesap/ben")
def ben(kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Ön yüzün açılışta sorduğu: kimim? Oturum yoksa kapı 401 verir."""
    return _ben(kullanici)


@router.post("/api/hesap/sartlar-kabul")
def sartlar_kabul(kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
                  db: Session = OTURUM) -> dict:
    """Bugünkü şartlar sürümünü damgalar (Faz 4 / 6): ayarlar banner'ının düğmesi; cevap `{"ok", "surum"}`.

    Gövde YOK: onaylanacak tek şey bugünkü metin ve sürümü sunucu bilir — istemcinin
    yazdığı bir sürüm eski bir metne onay iddia edebilirdi. Kullanıcı yoksa (yarışta
    silinmiş) 404; kapı zaten 401 verirdi, dal kâğıt üstünde.
    """
    if not odeme.sartlar_kabul_yaz(db, kullanici.id, hesap.simdi(), surum=hukuk.HUKUK_SURUMU):
        raise HTTPException(status_code=404, detail=i18n.t("err.hesap_giris_gerekli", dil.aktif()))
    return {"ok": True, "surum": hukuk.HUKUK_SURUMU}


@router.get("/giris")
def giris_sayfasi(ayarlar: ayar.Ayarlar = Depends(ayar.genel)) -> HTMLResponse:
    """`static/giris.html` — `index` ile aynı yerleştirme (services/sablon.py), aynı dil zinciri."""
    return sablon.sayfa(ayarlar, "giris.html")


# ── Hesap silme ve dışa aktarma (Faz 4 / 5) ──────────────────────────

def _abonelik_kapat(kullanici: Kullanici) -> None:
    """Aktif Polar aboneliğini HEMEN sonlandırır; başaramazsa WARNING — silmeyi durdurmaz (gerekçe modül başında).

    Ücretli planda ama `polar_abonelik_id` boşsa da uyarı: Polar'da bir abonelik
    tahsilata devam edebilir ve bizde onu bulan kimlik yok — sahip panelden bakar.
    Ücretsiz plan + abonelik yok = uyarı yok (sıradan durum, gürültü olmasın).
    """
    if kullanici.polar_abonelik_id:
        try:
            polar.abonelik_iptal(kullanici.polar_abonelik_id, cancel_at_period_end=False)
            return
        except Exception as e:  # SDK/ağ/yapılandırma — hepsi aynı sonuç: elle kapatılacak
            gunluk.olay(_gunluk, "hesap.silme_abonelik", "polar aboneligi kapatilamadi, sahip elle kapatmali",
                        seviye=logging.WARNING, kullanici_id=str(kullanici.id),
                        abonelik_id=kullanici.polar_abonelik_id, hata=type(e).__name__)
            return
    if kullanici.plan != planlar.PLAN_VARSAYILAN:
        gunluk.olay(_gunluk, "hesap.silme_abonelik", "ucretli planda hesap silindi ama abonelik kimligi yok",
                    seviye=logging.WARNING, kullanici_id=str(kullanici.id), plan=kullanici.plan,
                    polar_musteri_id=kullanici.polar_musteri_id)


def _silme_postasi(request: Request, kime: str, lang: str, gun: int, kullanici_id: uuid.UUID,
                   ayarlar: ayar.Ayarlar) -> None:
    """"Hesabın kapatıldı" iletisi ASIL adrese (anonimleşmeden önce alındı); gitmezse WARNING, silme sürer."""
    try:
        _postaci(request).gonder(posta.silme_postasi(kime, lang, gun))
    except (HTTPException, posta.PostaHatasi) as e:
        errlog.safe_append(ayarlar.data_dir, f"silme postasi gonderilemedi: {type(e).__name__}")
        gunluk.olay(_gunluk, "hesap.silme_posta", "hesap kapatildi iletisi gonderilemedi",
                    seviye=logging.WARNING, kullanici_id=str(kullanici_id), hata=type(e).__name__)


@router.post("/api/hesap/sil", response_model=None)
def sil(req: SilmeIstegi, request: Request,
        kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
        ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar), db: Session = OTURUM) -> Response:
    """Hesabı siler (anonimleştir + kilitle, K9); cevap 200 `{"ok", "bekleme_gun"}` ve çerez düşer.

    Sıra: kilit (429) → parolasız hesap (409) → parola (401 + deneme satırı) →
    kuyruktaki `bekliyor` işler iptal + rezerv iadesi (kullanıcının bağlamında,
    `sahip` politikası yazar) → BYOK anahtarları HEMEN → satır anonim, oturumlar/
    jetonlar/deneme sayacı gider → Polar aboneliği (dış, uyarıyla) → ileti ASIL
    adrese (dış, uyarıyla) → `olay=hesap.silindi`. Geri alma YOK: 7 günlük
    bekleme yalnız içeriğin kalıcı silinmesini erteler, hesap kapandı.
    """
    an = hesap.simdi()
    ip = hesap.ip_adresi(request)
    bekle = hesap.giris_kilidi(db, kullanici.eposta, ip, an)
    if bekle is not None:
        raise _cok_deneme(bekle)
    if kullanici.parola_ozeti is None:
        raise HTTPException(status_code=409, detail=i18n.t("err.hesap_parolasiz", dil.aktif()))
    if not hesap.parola_dogru(req.parola, kullanici.parola_ozeti):
        hesap.deneme_kaydet(db, hesap.DENEME_GIRIS, kullanici.eposta, ip, an)
        return JSONResponse({"detail": i18n.t("err.hesap_giris_hatali", dil.aktif())}, status_code=401)
    eposta, lang = kullanici.eposta, kullanici.dil or dil.aktif()
    gun = isci.hesap_silme_beklemesi().days
    iptaller = kuyruk.sahibin_islerini_iptal(db, kullanici.id, an)
    for is_id in iptaller:
        defter.iade(db, is_id, an=an)
    anahtar = depo_kimlik_bilgisi.hepsini_sil(db, kullanici.id)
    hesap.anonimlestir(db, kullanici, an)
    _abonelik_kapat(kullanici)
    _silme_postasi(request, eposta, lang, gun, kullanici.id, ayarlar)
    gunluk.olay(_gunluk, "hesap.silindi", "hesap anonimlestirildi ve kilitlendi",
                kullanici_id=str(kullanici.id), iptal_edilen_is=len(iptaller), silinen_anahtar=anahtar,
                bekleme_gun=gun)
    cevap = JSONResponse({"ok": True, "bekleme_gun": gun})
    cerez.oturum_sil(cevap)
    return cevap


def _disa_aktarma_beklemesi(kullanici_id: uuid.UUID, an: dt.datetime) -> int | None:
    """Son aktarım pencerenin içindeyse beklenecek saniye; değilse `None` (`kota._bekleme_sn` deyimi)."""
    son = _DISA_AKTARIMLAR.get(kullanici_id)
    if son is None or an - son >= DISA_AKTARMA_PENCERESI:
        return None
    return max(1, int((son + DISA_AKTARMA_PENCERESI - an).total_seconds()) + 1)


@router.get("/api/hesap/disa-aktar")
def disa_aktar_route(kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
                     db: Session = OTURUM) -> StreamingResponse:
    """Kullanıcının verisi ZIP olarak (services/disa_aktar.py); saatte 1, aşımı 429 + `Retry-After`.

    Damga ARŞİV KURULDUKTAN sonra yazılır: 429'a takılan istek damgayı
    ilerletmez, veri tabanı hatasıyla düşen istek de. Kullanıcı yoksa (yarışta
    silinmiş) 404 — kapı zaten 401 verirdi, bu dal kâğıt üstünde.
    """
    an = zaman.an()
    bekle = _disa_aktarma_beklemesi(kullanici.id, an)
    if bekle is not None:
        raise HTTPException(status_code=429,
                            detail=i18n.t("err.hesap_disa_aktar_sinir", dil.aktif(),
                                          dakika=max(1, -(-bekle // 60))),
                            headers={"Retry-After": str(bekle)})
    akis = disa_aktar.zip_akisi(db, kullanici.id, an=an)
    if akis is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.hesap_giris_gerekli", dil.aktif()))
    _DISA_AKTARIMLAR[kullanici.id] = an
    ad = f"kromis-verim-{zaman.damga_utc(an)[:10]}.zip"
    return StreamingResponse(akis, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{ad}"'})
