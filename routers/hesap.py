# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Hesap uçları — kayıt, doğrulama, giriş, çıkış, sıfırlama, `/giris` sayfası (Faz 1 / 3).

Sekiz rota (belge §3): `POST /api/hesap/{kayit,dogrula,giris,cikis,sifirla,
sifirla/dogrula}`, `GET /api/hesap/ben`, `GET /giris`. HTTP burada (gövde,
durum kodu, çerez, cümle); hesap mantığı `services/hesap.py`de, posta
`services/posta.py`de, kapı `services/kimlik.py`de.

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

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

import errlog
import i18n
from models import GirisIstegi, JetonIstegi, KayitIstegi, SifirlamaIstegi, YeniParolaIstegi
from services import ayar, cerez, defter, dil, hesap, kimlik, kiraci, koken, planlar, posta, sablon
from services.db import OTURUM
from services.tablolar import Kullanici

router = APIRouter()

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
    """`GET /api/hesap/ben`in gövdesi (belge: `{id, eposta, dil, is_admin}`); giriş de aynısını döner."""
    return {"id": str(kullanici.id), "eposta": kullanici.eposta,
            "dil": kullanici.dil, "is_admin": kullanici.is_admin}


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
    elif kullanici.dogrulandi_at is None:
        kullanici.parola_ozeti = hesap.parola_ozeti(req.parola)
        kullanici.dil = dil.aktif()
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


@router.get("/giris")
def giris_sayfasi(ayarlar: ayar.Ayarlar = Depends(ayar.genel)) -> HTMLResponse:
    """`static/giris.html` — `index` ile aynı yerleştirme (services/sablon.py), aynı dil zinciri."""
    return sablon.sayfa(ayarlar, "giris.html")
