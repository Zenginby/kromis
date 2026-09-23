# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Hesap katmanı — parola, kullanıcı, oturum, jeton, deneme sayacı (Faz 1 / 3. görev).

Rota dışı her hesap işlemi burada; `routers/hesap.py` yalnız HTTP'yi
(gövde, durum kodu, çerez, metin) bilir. Bu modül kullanıcıya KONUŞMAZ —
`None`/`bool`/sayı döndürür, cümleyi rota kurar (tests/test_i18n.py
sınıflandırması). Hiçbir işlev `commit` çağırmaz: commit `services/db.py`nin
`oturum` bağımlılığında, rota döner dönmez (oranın gerekçesi).

PAROLA — `pwdlib` + argon2id (belge §3: `pwdlib[argon2]==0.3.*`). Doğrudan
`argon2-cffi` de olurdu; pwdlib'in kazancı algoritma göçünün hazır olması:
`verify_and_update` bir gün parametreler değişince eski özeti girişte sessizce
yeniler. Kütüphane parametreleri (m=65536, t=3, p=4) olduğu gibi; NIST 800-63B
uyarınca uzunluk dışında KURAL YOK (8-128, `models.PAROLA_EN_AZ/EN_COK`;
karakter sınıfı, süre sonu yok — ikisi de parolayı tahmin edilebilir kılıyor,
güçlendirmiyor).

ZAMANLAMA — `parola_dogru` var olmayan kullanıcı için de BİR argon2 doğrulaması
koşturur (`_sahte_ozet`e karşı): yoksa "bu e-posta kayıtlı mı" sorusu cevap
süresinden okunurdu (kayıtlı → ~50 ms özet hesabı, kayıtsız → 1 ms). Cevap
metni de ayırt etmiyor (rota); sayaç da (`GirisDenemesi.kullanici_id` yok —
tablolar.py'nin gerekçesi).

OTURUM — sunucu tarafı, DB'de (K3, JWT DEĞİL). Giriş `secrets.token_urlsafe(32)`
üretir (256 bit), yalnız SHA-256 özeti `oturumlar.jeton_ozeti`ne yazılır, ham
jeton çerezde (services/cerez.py). DB sızsa oturum sızmaz: özetten jeton
türetilemez. Kayan ömür 30 gün; `son_gorulme` 5 dk çözünürlükle ilerler —
her istekte UPDATE değil, 5 dakikada en fazla bir (`SON_GORULME_COZUNURLUGU`);
ilerlediğinde `bitis` de ötelenir ve rota çerezi yeniden yazar.

JETON — e-posta doğrulama (24 saat) ve parola sıfırlama (1 saat). Aynı üretim:
ham jeton bağlantıda, özeti `jetonlar.ozet`te; TEK KULLANIM (`kullanildi_at`),
SÜRELİ (`bitis`), ve aynı amaçla yeni jeton istenince eskileri SİLİNİR —
kullanıcının gelen kutusunda geçerli bağlantı hep en sonuncusu. Süreler
belgede sayı olarak yoktu; 24 sa / 1 sa seçildi: doğrulama gelen kutusuna
gecikmeli bakan birine yetmeli, sıfırlama ise "şimdi" istenen bir şey ve
kısa ömür sızmış bir bağlantının değerini düşürür.

DENEME SAYACI — `giris_denemeleri`, Redis'siz (belge: Faz 2'de Redis gelirse
taşınır). Üç tür (`tur`): `giris` yalnız BAŞARISIZ girişleri sayar (e-posta
15 dk'da 10, IP 15 dk'da 30); `kayit` ve `sifirlama` her isteği sayar (IP
saatte 5). Kilit `Retry-After` için saniye döndürür: pencere içindeki EN ESKİ
denemenin pencereden çıkmasına kalan süre — "900 sn" demek yerine gerçek
bekleme. Başarılı giriş o e-postanın sayacını SİLER (kilit, parolasını
sonunda hatırlayan kullanıcıyı 15 dk daha bekletmesin); IP sayacı kalır.
IP bilinmiyorsa (`request.client` yok — bazı ASGI sondaları) IP kilidi
uygulanamaz, e-posta kilidi yine çalışır.
"""
from __future__ import annotations

import datetime as dt
import functools
import hashlib
import ipaddress
import secrets
import uuid

from fastapi import Request
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from services import cerez
from services.tablolar import GirisDenemesi, Jeton, Kullanici, Oturum

# Silinen hesabın e-postasının alan adı (Faz 4 / 5, K9): RFC 2606 rezerve TLD —
# hiçbir zaman çözülmez, `posta.py` bu soneki reddeder. `silindi-<id>@` öneki
# citext UNIQUE'i korur (id benzersiz) ve satırın "silinmiş" olduğunu adresten
# okunur kılar (admin listesi, `pg_dump`). Asıl adres GİDER: anonimleştirme
# KVKK md. 7'de silmeye denk, sonsuz soft delete değil.
ANONIM_ALAN = "anonim.invalid"

# Jeton amaçları — `tablolar.JETON_AMACLARI`nın iki üyesi, adıyla.
AMAC_DOGRULAMA = "eposta_dogrulama"
AMAC_SIFIRLAMA = "parola_sifirlama"
DOGRULAMA_OMRU = dt.timedelta(hours=24)
SIFIRLAMA_OMRU = dt.timedelta(hours=1)

OTURUM_OMRU = dt.timedelta(seconds=cerez.OTURUM_OMRU_SN)
SON_GORULME_COZUNURLUGU = dt.timedelta(minutes=5)

# Deneme türleri — `tablolar.DENEME_TURLERI`nin üyeleri, adıyla.
DENEME_GIRIS = "giris"
DENEME_KAYIT = "kayit"
DENEME_SIFIRLAMA = "sifirlama"
GIRIS_PENCERESI = dt.timedelta(minutes=15)
GIRIS_EPOSTA_SINIRI = 10
GIRIS_IP_SINIRI = 30
ISTEK_PENCERESI = dt.timedelta(hours=1)
ISTEK_IP_SINIRI = 5

_HASH = PasswordHash((Argon2Hasher(),))


def simdi() -> dt.datetime:
    """UTC, saat dilimli — `timestamptz` sütunlarıyla karşılaştırılabilir tek biçim."""
    return dt.datetime.now(dt.UTC)


# ── Parola ───────────────────────────────────────────────────────────

def parola_ozeti(parola: str) -> str:
    return _HASH.hash(parola)


@functools.cache
def _sahte_ozet() -> str:
    """Var olmayan kullanıcı için doğrulanan özet (gerekçe modül başında).

    İlk çağrıda üretilir, ithal anında DEĞİL: `import app` yapan 37 test
    dosyası argon2 hesaplamasın. Değerin ne olduğu önemsiz, süresi önemli.
    """
    return _HASH.hash(secrets.token_urlsafe(16))


def parola_dogru(parola: str, ozet: str | None) -> bool:
    """Parola özete uyuyor mu; `ozet` yoksa (kullanıcı yok / parolasız hesap) sabit süreli `False`."""
    if ozet is None:
        _HASH.verify(parola, _sahte_ozet())
        return False
    return _HASH.verify(parola, ozet)


def parola_yenilensin_mi(parola: str, ozet: str) -> str | None:
    """Doğru parolayla gelen eski parametreli özetin yenisi; güncelse `None` (pwdlib göç yolu)."""
    dogru, yeni = _HASH.verify_and_update(parola, ozet)
    return yeni if dogru else None


# ── Jeton yardımcıları ───────────────────────────────────────────────

def yeni_jeton() -> str:
    """256 bit rastgele, URL-güvenli — oturum çerezi ve e-posta bağlantıları aynı üretici."""
    return secrets.token_urlsafe(32)


def ozet(jeton: str) -> bytes:
    """Jetonun DB'de duran hâli. SHA-256 yeter: girdi 256 bit rastgele, sözlük saldırısı yok."""
    return hashlib.sha256(jeton.encode("ascii", "ignore")).digest()


def ip_adresi(request: Request) -> str | None:
    """İstemcinin IP'si `inet` sütununa yazılabilir biçimde; yoksa/geçersizse `None`.

    `TestClient` `client.host` olarak `"testclient"` veriyor — `inet` bunu
    reddederdi. Vekil arkasında gerçek adres `--proxy-headers` ile
    `request.client`a gelir; burası başlık okumaz.
    """
    if request.client is None:
        return None
    try:
        return str(ipaddress.ip_address(request.client.host))
    except ValueError:
        return None


# ── Kullanıcı ────────────────────────────────────────────────────────

def kullanici_bul(db: Session, eposta: str) -> Kullanici | None:
    """E-postaya göre (citext: büyük/küçük harf duyarsız); yumuşak silinmişler görünmez."""
    return db.scalars(select(Kullanici).where(Kullanici.eposta == eposta,
                                              Kullanici.silindi_at.is_(None))).first()


def kullanici_olustur(db: Session, eposta: str, parola: str, dil: str | None) -> Kullanici:
    """Doğrulanmamış yeni hesap; `dil` isteğin dili (zincirin 3. halkası, 4. görev okur)."""
    kullanici = Kullanici(eposta=eposta, parola_ozeti=parola_ozeti(parola), dil=dil)
    db.add(kullanici)
    db.flush()
    return kullanici


def dogrulandi(kullanici: Kullanici, an: dt.datetime) -> None:
    if kullanici.dogrulandi_at is None:
        kullanici.dogrulandi_at = an


# ── Hesap silme (Faz 4 / 5, K9) ──────────────────────────────────────

def anonim_eposta(kullanici_id: uuid.UUID) -> str:
    return f"silindi-{kullanici_id}@{ANONIM_ALAN}"


def anonimlestir(db: Session, kullanici: Kullanici, an: dt.datetime) -> None:
    """Hesabı ANINDA kilitler ve kişisel veriyi satırdan siler; satır KALIR (defter/sipariş FK'si için).

    `silindi_at = an`, `eposta` anonim, `parola_ozeti`/`dil` NULL; bütün
    `oturumlar` (giriş imkânsız — `oturum_dogrula` zaten `silindi_at IS NULL`
    süzer, satırın gitmesi ikinci kapı), bütün `jetonlar` (bekleyen sıfırlama
    bağlantısı hesabı geri açamasın) ve o adresin `giris_denemeleri` satırları
    (adres kayıtlardan çıkıyor; sayaç satırı adresi taşırdı — belge turun
    işi diyordu ama tur o an adresi BİLEMEZ, anonimleşmiş; silme anında
    silinir). `polar_musteri_id`/`polar_abonelik_id` KALIR: Polar mutabakatı
    ve `siparisler` satırları (K9); Polar'daki müşteri kaydını silmek sahibin
    adımı. `UPDATE … WHERE id`: nesne bu oturuma bağlı olmayabilir (kimlik
    kapısı başka transaksiyonda çözdü) — ORM özniteliği yazmak sessizce
    kaybolurdu. `bakiye`/`paket_bakiye` DOKUNULMAZ (tek yazar `defter.py`,
    AST bekçisi); tutarlılık turu anonim satırı da ölçer, sapma yok.
    """
    eposta = kullanici.eposta
    db.execute(update(Kullanici).where(Kullanici.id == kullanici.id)
               .values(silindi_at=an, eposta=anonim_eposta(kullanici.id), parola_ozeti=None, dil=None))
    db.execute(delete(Oturum).where(Oturum.kullanici_id == kullanici.id))
    db.execute(delete(Jeton).where(Jeton.kullanici_id == kullanici.id))
    db.execute(delete(GirisDenemesi).where(GirisDenemesi.eposta == eposta))


def silinecek_hesaplar(db: Session, an: dt.datetime, bekleme: dt.timedelta) -> list[uuid.UUID]:
    """`silindi_at < an - bekleme AND temizlendi_at IS NULL` — bakım turunun içerik silme adayları (admin bağlamı).

    Sınır KESİN küçük (`<`), `eskileri_sil`in deyimi: tam 7. günde tur
    dokunmaz, 7 gün + 1 sn'de siler. `bekleme = 0` → `silindi_at < an`, yani
    silme isteğinden sonraki ilk tur (`KROMIS_HESAP_SILME_BEKLEME_GUN=0`).
    """
    return list(db.scalars(select(Kullanici.id)
                           .where(Kullanici.silindi_at.is_not(None), Kullanici.silindi_at < an - bekleme,
                                  Kullanici.temizlendi_at.is_(None))
                           .order_by(Kullanici.id)))


def temizlendi(db: Session, kullanici_id: uuid.UUID, an: dt.datetime) -> None:
    """İçerik silindi damgası — ikinci tur bu satırı aday görmez (`temizlendi_at IS NULL` süzgeci)."""
    db.execute(update(Kullanici).where(Kullanici.id == kullanici_id).values(temizlendi_at=an))


# ── Oturum ───────────────────────────────────────────────────────────

def oturum_ac(db: Session, kullanici: Kullanici, ip: str | None, istemci: str | None,
              an: dt.datetime) -> str:
    """Yeni oturum satırı; dönen HAM jeton çereze gider, DB yalnız özetini tutar."""
    jeton = yeni_jeton()
    db.add(Oturum(kullanici_id=kullanici.id, jeton_ozeti=ozet(jeton), son_gorulme=an,
                  bitis=an + OTURUM_OMRU, ip=ip, istemci=(istemci or "")[:512] or None))
    db.flush()
    return jeton


def oturum_dogrula(db: Session, ham_jeton: str,
                   an: dt.datetime) -> tuple[Kullanici, bool] | None:
    """Çerezdeki jetondan kullanıcı; `(kullanici, yenilendi)` ya da `None`.

    Tek sorgu (`oturumlar ⋈ kullanicilar`). `yenilendi` = kayan ömür bu istekte
    ilerledi (5 dk çözünürlük), yani çağıran çerezi de yeniden yazmalı.
    """
    satir = db.execute(
        select(Oturum, Kullanici)
        .join(Kullanici, Oturum.kullanici_id == Kullanici.id)
        .where(Oturum.jeton_ozeti == ozet(ham_jeton), Oturum.bitis > an,
               Kullanici.silindi_at.is_(None))
    ).first()
    if satir is None:
        return None
    oturum, kullanici = satir
    yenilendi = an - oturum.son_gorulme >= SON_GORULME_COZUNURLUGU
    if yenilendi:
        oturum.son_gorulme = an
        oturum.bitis = an + OTURUM_OMRU
    return kullanici, yenilendi


def oturum_kapat(db: Session, ham_jeton: str) -> None:
    """Çıkış: yalnız bu çerezin oturumu düşer (öteki cihazlar açık kalır)."""
    db.execute(delete(Oturum).where(Oturum.jeton_ozeti == ozet(ham_jeton)))


def oturumlari_dusur(db: Session, kullanici_id: uuid.UUID) -> None:
    """Kullanıcının BÜTÜN oturumları — parola değişikliğinde (sızan çerezin ömrü burada kesilir)."""
    db.execute(delete(Oturum).where(Oturum.kullanici_id == kullanici_id))


# ── E-posta jetonları ────────────────────────────────────────────────

def jeton_ver(db: Session, kullanici: Kullanici, amac: str, an: dt.datetime) -> str:
    """`amac` için yeni tek kullanımlık jeton; aynı amaçlı eskileri siler. Ham jetonu döner."""
    omur = DOGRULAMA_OMRU if amac == AMAC_DOGRULAMA else SIFIRLAMA_OMRU
    db.execute(delete(Jeton).where(Jeton.kullanici_id == kullanici.id, Jeton.amac == amac))
    jeton = yeni_jeton()
    db.add(Jeton(kullanici_id=kullanici.id, amac=amac, ozet=ozet(jeton), bitis=an + omur))
    db.flush()
    return jeton


def jeton_kullan(db: Session, ham_jeton: str, amac: str, an: dt.datetime) -> Kullanici | None:
    """Geçerli (süresi dolmamış, kullanılmamış, doğru amaçlı) jetonu TÜKETİR ve sahibini döner.

    Tüketim `kullanildi_at` ile: satır silinmiyor ki "bu bağlantı kullanıldı"
    ile "bu bağlantı hiç var olmadı" gerektiğinde ayırt edilebilsin (bugün
    ikisi de aynı 400; kayıt duruyor).
    """
    satir = db.execute(
        select(Jeton, Kullanici)
        .join(Kullanici, Jeton.kullanici_id == Kullanici.id)
        .where(Jeton.ozet == ozet(ham_jeton), Jeton.amac == amac, Jeton.bitis > an,
               Jeton.kullanildi_at.is_(None), Kullanici.silindi_at.is_(None))
    ).first()
    if satir is None:
        return None
    jeton, kullanici = satir
    jeton.kullanildi_at = an
    return kullanici


# ── Deneme sayacı ────────────────────────────────────────────────────

def deneme_kaydet(db: Session, tur: str, eposta: str, ip: str | None, an: dt.datetime) -> None:
    db.add(GirisDenemesi(tur=tur, eposta=eposta, ip=ip, zaman=an))
    db.flush()


def _bekleme(db: Session, tur: str, sinir: int, pencere: dt.timedelta, an: dt.datetime,
             *, eposta: str | None = None, ip: str | None = None) -> int | None:
    """Pencere içindeki deneme sayısı `sinir`e ulaştıysa beklenecek saniye; değilse `None`."""
    sorgu = select(func.count(), func.min(GirisDenemesi.zaman)).where(
        GirisDenemesi.tur == tur, GirisDenemesi.zaman > an - pencere)
    if eposta is not None:
        sorgu = sorgu.where(GirisDenemesi.eposta == eposta)
    if ip is not None:
        sorgu = sorgu.where(GirisDenemesi.ip == ip)
    sayi, en_eski = db.execute(sorgu).one()
    if sayi < sinir or en_eski is None:
        return None
    return max(1, int((en_eski + pencere - an).total_seconds()) + 1)


def giris_kilidi(db: Session, eposta: str, ip: str | None, an: dt.datetime) -> int | None:
    """Girişe izin var mı: e-posta (10/15 dk) VE IP (30/15 dk) sınırlarının en uzunu."""
    bekle = [_bekleme(db, DENEME_GIRIS, GIRIS_EPOSTA_SINIRI, GIRIS_PENCERESI, an, eposta=eposta)]
    if ip is not None:
        bekle.append(_bekleme(db, DENEME_GIRIS, GIRIS_IP_SINIRI, GIRIS_PENCERESI, an, ip=ip))
    dolu = [b for b in bekle if b is not None]
    return max(dolu) if dolu else None


def istek_kilidi(db: Session, tur: str, ip: str | None, an: dt.datetime) -> int | None:
    """Kayıt / sıfırlama isteği: IP saatte 5. IP yoksa sayılamaz, `None`."""
    if ip is None:
        return None
    return _bekleme(db, tur, ISTEK_IP_SINIRI, ISTEK_PENCERESI, an, ip=ip)


def denemeleri_sil(db: Session, eposta: str) -> None:
    """Başarılı girişte o e-postanın başarısız giriş sayacı sıfırlanır (gerekçe modül başında)."""
    db.execute(delete(GirisDenemesi).where(GirisDenemesi.tur == DENEME_GIRIS,
                                           GirisDenemesi.eposta == eposta))
