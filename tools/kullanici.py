#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İlk (ya da herhangi bir) kullanıcıyı açan ve oturum düşüren CLI (Faz 1 / 8).

    DATABASE_URL=… python tools/kullanici.py olustur --eposta ali@ornek.com [--admin] [--dil tr]
    DATABASE_URL=… python tools/kullanici.py oturum-dusur --eposta ali@ornek.com
    DATABASE_URL=… python tools/kullanici.py admin --eposta ali@ornek.com [--kaldir]
    DATABASE_URL=… python tools/kullanici.py parola --eposta ali@ornek.com

NEDEN VAR: web sürümünde hesap açmak kayıt → e-posta doğrulama akışından
geçiyor (routers/hesap.py) ve o akış bir posta servisi istiyor. İlk kullanıcı
(sahip) posta servisi kurulmadan girebilmeli; `olustur` bu yüzden e-postayı
DOĞRULANMIŞ yazar (`dogrulandi_at = now`). `--admin` `is_admin=true` yazar —
Faz 2 / 8'den beri onu okuyan `kimlik.admin_kullanici` kapısı (`/admin`,
`/api/admin/*`). Var olan hesabı sonradan admin yapmanın (ya da bayrağı
kaldırmanın) yolu `admin` komutu: canlıda ilk admin sahibin KENDİ hesabıdır ve
o hesap çoktan açılmıştır; `UPDATE kullanicilar …`ı elle yazdırmak yerine
araç. Admin adminliği KENDİNDEN kaldırabilir — son admin bekçisi yok, bilerek:
CLI DB'ye doğrudan bağlanır, bayrak aynı komutla geri gelir.

PAROLA ARGÜMAN DEĞİL: `--parola` diye bir seçenek yok ve olmayacak — kabuk
geçmişine (`~/.bash_history`, `ps`) düşerdi. TTY'de `getpass` iki kez sorar;
betik/test için `--parola-stdin` standart girdinin İLK satırını okur (satır
sonu kırpılır, başka hiçbir şey kırpılmaz: baştaki/sondaki boşluk parolanın
parçası, `models.check_parola`nın kuralı). Parola hiçbir çıktıya yazılmaz.

KURAL KÜMESİ TEK: e-posta ve parola doğrulaması `models.check_eposta`/
`check_parola`, özet `services.hesap.parola_ozeti`, satır `hesap.kullanici_olustur`
— yani CLI'dan açılan hesap ile web'den açılan hesap aynı kapılardan geçer;
biri gevşetilirse öteki de, sessiz bir ayrışma olmaz.

`oturum-dusur`: kullanıcının BÜTÜN oturumlarını siler (`hesap.oturumlari_dusur`)
— çerezi sızmış bir hesabın acil kapısı; sayısını basar. Kullanıcı yoksa 1.

ÇIKIŞ KODLARI: 0 tamam · 1 kullanıcı hatası (var olan e-posta, bilinmeyen
e-posta, geçersiz girdi, parolalar uyuşmadı — hiçbir şey yazılmadı) ·
2 ortam hatası (`DATABASE_URL` yok, sunucuya ulaşılamıyor). Uygulama ayakta
olmadan çalışır: motor `services.db.motor_kur`, aynı bağlantı dizesi.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

# Betik olarak koşarken (`python tools/kullanici.py`) `sys.path[0]` bu dizin
# ve kök modüller görünmez; testler `tools.kullanici` diye ithal ediyor.
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import models  # noqa: E402
from services import db, hesap, kiraci  # noqa: E402
from services.tablolar import Oturum  # noqa: E402

CIKIS_TAMAM = 0
CIKIS_KULLANICI = 1
CIKIS_ORTAM = 2


class KullaniciHatasi(Exception):
    """Operatöre söylenecek, çıkış kodu 1 olan hata; mesajı zaten cümle."""


def _parola_al(stdin_den: bool) -> str:
    """Parolayı TTY'den (iki kez) ya da stdin'in ilk satırından; doğrulanmış döner."""
    if stdin_den:
        satir = sys.stdin.readline()
        if not satir:
            raise KullaniciHatasi("--parola-stdin verildi ama standart girdi bos.")
        parola = satir.rstrip("\r\n")
    else:
        parola = getpass.getpass("Parola: ")
        if getpass.getpass("Parola (tekrar): ") != parola:
            raise KullaniciHatasi("Parolalar uyusmadi; hicbir sey yazilmadi.")
    try:
        return models.check_parola(parola)
    except ValueError as hata:
        raise KullaniciHatasi(str(hata)) from None


def _eposta(ham: str) -> str:
    try:
        return models.check_eposta(ham)
    except ValueError as hata:
        raise KullaniciHatasi(str(hata)) from None


def olustur(oturum: Session, eposta: str, parola: str, *, admin: bool, dil: str | None) -> str:
    """Doğrulanmış (ve istenirse admin) hesabı yazar; kullanıcının id'sini döner. E-posta varsa hata."""
    if hesap.kullanici_bul(oturum, eposta) is not None:
        raise KullaniciHatasi(f"{eposta} zaten kayitli; hicbir sey yazilmadi.")
    kullanici = hesap.kullanici_olustur(oturum, eposta, parola, dil)
    hesap.dogrulandi(kullanici, hesap.simdi())
    kullanici.is_admin = admin
    oturum.flush()
    return str(kullanici.id)


def admin_yap(oturum: Session, eposta: str, *, admin: bool) -> bool:
    """`is_admin` bayrağını yazar; önceki değeri döner (çıktı "değişti/zaten öyleydi" desin). Kullanıcı yoksa hata."""
    kullanici = hesap.kullanici_bul(oturum, eposta)
    if kullanici is None:
        raise KullaniciHatasi(f"{eposta} diye bir kullanici yok.")
    onceki = bool(kullanici.is_admin)
    kullanici.is_admin = admin
    oturum.flush()
    return onceki


def parola_yaz(oturum: Session, eposta: str, parola: str) -> int:
    """Parolayı yeniden yazar ve kullanıcının BÜTÜN oturumlarını düşürür; düşen oturum sayısını döner.

    NEDEN VAR: parola geri alınamaz (argon2 özeti), web'deki sıfırlama akışı ise
    posta servisi istiyor — kurulmadığı bir ortamda (yerel geliştirme, taze
    dağıtım) sahibi kendi hesabından kilitleyen tek şey buydu. `olustur`la yeni
    hesap açmak hesabın planını, kredisini ve geçmişini geride bırakır.

    NEDEN OTURUMLAR DA DÜŞÜYOR: parola değiştirmek "bu hesabı artık ben
    yönetiyorum" demektir; eski çerez ayakta kalırsa değişiklik saldırganı DIŞARI
    ATMAZ, yalnız yeni girişi engeller. `oturum-dusur` komutunun yaptığının
    aynısı, tek işlemde.

    ÖZET TEK YERDEN: `hesap.parola_ozeti` — kayıt, web sıfırlaması ve bu araç
    aynı argon2 ayarını kullanır (modül başındaki "KURAL KÜMESİ TEK"); parola
    `_parola_al`da `models.check_parola`dan geçmiş olarak gelir.
    """
    kullanici = hesap.kullanici_bul(oturum, eposta)
    if kullanici is None:
        raise KullaniciHatasi(f"{eposta} diye bir kullanici yok.")
    kullanici.parola_ozeti = hesap.parola_ozeti(parola)
    sayi = oturum.scalar(select(func.count()).select_from(Oturum)
                         .where(Oturum.kullanici_id == kullanici.id)) or 0
    hesap.oturumlari_dusur(oturum, kullanici.id)
    oturum.flush()
    return sayi


def oturum_dusur(oturum: Session, eposta: str) -> int:
    """Kullanıcının bütün oturumlarını siler; kaç oturum düştüğünü döner."""
    kullanici = hesap.kullanici_bul(oturum, eposta)
    if kullanici is None:
        raise KullaniciHatasi(f"{eposta} diye bir kullanici yok.")
    sayi = oturum.scalar(select(func.count()).select_from(Oturum)
                         .where(Oturum.kullanici_id == kullanici.id)) or 0
    hesap.oturumlari_dusur(oturum, kullanici.id)
    return int(sayi)


def _ayristirici() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kullanici.py",
        description="Kromis web: kullanici ac / oturum dusur (DATABASE_URL ile, uygulama kapaliyken).")
    alt = p.add_subparsers(dest="komut", required=True)
    o = alt.add_parser("olustur", help="dogrulanmis yeni hesap; parola TTY'den sorulur")
    o.add_argument("--eposta", required=True)
    o.add_argument("--admin", action="store_true", help="is_admin=true (/admin ve /api/admin/* kapisi)")
    o.add_argument("--dil", choices=models.ALLOWED_LANGUAGES, default=None,
                   help="hesabin dili; verilmezse tarayici basligina dusulur")
    o.add_argument("--parola-stdin", action="store_true",
                   help="parolayi standart girdinin ilk satirindan oku (betik/test); TTY'de sorulmaz")
    d = alt.add_parser("oturum-dusur", help="kullanicinin BUTUN oturumlarini sil (sizan cerez)")
    d.add_argument("--eposta", required=True)
    a = alt.add_parser("admin", help="var olan hesabi admin yap (is_admin=true); --kaldir bayragi dusurur")
    a.add_argument("--eposta", required=True)
    a.add_argument("--kaldir", action="store_true", help="is_admin=false yaz")
    s = alt.add_parser("parola", help="var olan hesabin parolasini yeniden yaz; BUTUN oturumlar duser")
    s.add_argument("--eposta", required=True)
    s.add_argument("--parola-stdin", action="store_true",
                   help="parolayi standart girdinin ilk satirindan oku (betik/test); TTY'de sorulmaz")
    return p


def main(argv: list[str]) -> int:
    args = _ayristirici().parse_args(argv)
    url = db.baglanti_dizesi()
    if not url:
        print(f"{db.DATABASE_URL_ENV} verilmedi: bu arac veri tabanina baglanir.", file=sys.stderr)
        return CIKIS_ORTAM
    try:
        eposta = _eposta(args.eposta)
        # Parola DB'ye bağlanmadan ÖNCE alınır: ulaşılamayan bir sunucu yüzünden
        # iki kez parola yazdırmak gereksiz; girdi hatası da hemen görünür.
        parola = _parola_al(args.parola_stdin) if args.komut in ("olustur", "parola") else None
    except KullaniciHatasi as hata:
        print(str(hata), file=sys.stderr)
        return CIKIS_KULLANICI

    motor = db.motor_kur(url)
    try:
        # `app.rol = 'admin'` (RLS, Faz 2 / 7): iki komut da hesap tablolarında
        # (`kullanicilar`, `oturumlar`) ve onlar politikasız — bağlam bugün bir şey
        # değiştirmez, ama araç platformun elidir ve rolü açıkça taşır: yarın bir
        # iş tablosuna dokunan komut (8. görevin tavanı) bağlamsız kalmasın.
        with kiraci.baglam(rol=kiraci.ADMIN), Session(motor) as oturum:
            if args.komut == "olustur":
                assert parola is not None
                kimlik = olustur(oturum, eposta, parola, admin=args.admin, dil=args.dil)
                oturum.commit()
                print(f"olusturuldu: {eposta} (id {kimlik}, admin: {'evet' if args.admin else 'hayir'}, "
                      f"dogrulanmis: evet)")
            elif args.komut == "admin":
                onceki = admin_yap(oturum, eposta, admin=not args.kaldir)
                oturum.commit()
                yeni = "hayir" if args.kaldir else "evet"
                degisti = "degisti" if onceki == args.kaldir else "zaten oyleydi"
                print(f"{eposta}: admin = {yeni} ({degisti})")
            elif args.komut == "parola":
                assert parola is not None
                sayi = parola_yaz(oturum, eposta, parola)
                oturum.commit()
                print(f"{eposta}: parola yazildi, {sayi} oturum dusuruldu")
            else:
                sayi = oturum_dusur(oturum, eposta)
                oturum.commit()
                print(f"{eposta}: {sayi} oturum dusuruldu")
    except KullaniciHatasi as hata:
        print(str(hata), file=sys.stderr)
        return CIKIS_KULLANICI
    except SQLAlchemyError as hata:
        # Bağlantı dizesinde parola olabilir; SQLAlchemy mesajı URL'yi zaten
        # maskeliyor, yine de yalnız sınıf adı ve ilk satır basılıyor.
        print(f"veri tabani hatasi ({type(hata).__name__}): {str(hata).splitlines()[0]}",
              file=sys.stderr)
        return CIKIS_ORTAM
    finally:
        motor.dispose()
    return CIKIS_TAMAM


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
