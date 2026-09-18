#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""RLS'i ATLAMAYAN uygulama rolünü açar — `rls_kontrol` kırmızı dediğinde yürünen yol (Faz 2 / 7).

    DATABASE_URL=…            # göç/sahip rolü (süper kullanıcı olabilir)
    KROMIS_ROL_PAROLA=…       # açılacak rolün parolası (argüman DEĞİL: kabuk geçmişi)
    python tools/uygulama_rolu.py [--ad kromis_uygulama] [--kuru] [--tohum]

NEDEN VAR: `FORCE ROW LEVEL SECURITY` tablo sahibini kapsar ama süper
kullanıcıyı ve `BYPASSRLS` rolünü KAPSAMAZ. Yönetilen sağlayıcıların bir kısmı
kutudan tam da öyle bir rol veriyor — ÖLÇÜLDÜ (2026-09-18, Railway,
PostgreSQL 18.6): öntanımlı `postgres` rolü `rolsuper = t` ve
`rolbypassrls = t`. O bağlantıyla uygulama koşarsa 24 politika yerinde durur ve
hiçbir şey yapmaz. KURULUM.md'nin "ayrı rol" yolu bu yüzden bazı sağlayıcılarda
yedek değil ZORUNLU; bu betik o yolu elle yazılmış altı DDL satırı olmaktan
çıkarıp tekrarlanabilir bir komuta çeviriyor.

İŞ BÖLÜMÜ: göç (`tools/goc.py`) SAHİP rolüyle koşmaya devam eder — tabloları o
yaratır; `ALTER DEFAULT PRIVILEGES` buradan verilir ki SONRAKİ göçlerin
tabloları da yeni role açık doğsun (yoksa `0007` sonrası uygulama "permission
denied" alır ve sebep aylar sonra aranır). Uygulama ve işçi YALNIZ yeni rolle
bağlanır: `DATABASE_URL`in kullanıcı/parola kısmı değişir, gerisi aynı kalır
(betik sonda o dizeyi basar, parolayı YAZMADAN).

`--tohum` NEDEN VAR: `rls_kontrol`ün "bağlamsız `count(*)` → 0" kapısı BOŞ bir
tabloda kendiliğinden yeşildir ve hiçbir şey kanıtlamaz (aynı gün Railway'in
taze DB'sinde buna düşüldü). Tohum, o kapıyı anlamlı kılan tek satırı yazar:
bir hesap + bir klasör + bir medya. Tablo BOŞ DEĞİLSE yazmaz, var olan bir
`kullanici_id`yi basar — canlıda zaten gerçek veri vardır, uydurma satıra gerek
yoktur. Satırlar KİRACI BAĞLAMINDA yazılır (`kiraci.baglam`), admin rolüyle
değil: admin politikası INSERT vermiyor ve araç tek bir hesabın satırlarını
yazıyor (`tools/ice_aktar.py`nin aynı gerekçesi).

PAROLA DDL'e DEĞER OLARAK BAĞLANAMAZ (`CREATE ROLE` parametre almaz), bu yüzden
dizeye gömülüyor: tek tırnak ikilenerek ve `standard_conforming_strings`in
açık olduğu DOĞRULANARAK (kapalıysa ters eğik çizgi kaçış anlamı kazanır ve
ikileme yetmez — betik o durumda koşmayı reddeder). Rol adı da dizeye giriyor;
kabul edilen ad kümesi bu yüzden dar (`AD_KALIBI`).

ÇIKIŞ KODLARI: 0 tamam · 1 iş düştü (yeni rol de RLS'i atlıyor ya da DDL
hatası) · 2 ortam (`DATABASE_URL`/parola yok, geçersiz ad, sunucuya
ulaşılamıyor).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import uuid

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from services import db, hesap, kiraci  # noqa: E402
from services.tablolar import Klasor, Kullanici, Medya  # noqa: E402

CIKIS_TAMAM = 0
CIKIS_IS = 1
CIKIS_ORTAM = 2

PAROLA_ENV = "KROMIS_ROL_PAROLA"
ONTANIMLI_AD = "kromis_uygulama"

# Rol adı SQL'e tanımlayıcı olarak giriyor (bağlanamaz): dar tut — küçük harf,
# rakam, alt çizgi; tırnak/boşluk/noktalama yok.
AD_KALIBI = re.compile(r"[a-z_][a-z0-9_]{0,62}")


class KuralDisi(Exception):
    """Ortamın sözleşmeyi bozduğu hâl (bugün: `standard_conforming_strings` kapalı)."""


def parola_sql(parola: str) -> str:
    """Parolanın SQL literali — tek tırnak ikilenir. Bkz. modül başlığı."""
    kacik = parola.replace("'", "''")
    return f"'{kacik}'"


def deyimler(ad: str, parola_literali: str, rol_var_mi: bool) -> tuple[str, ...]:
    """Rolü açan/yetkilendiren DDL. `--kuru` bunları `<PAROLA>` ile basar, koşmaz.

    Rol varsa `ALTER`: betiği ikinci kez koşmanın anlamı "parolayı yenile"dir.
    """
    kur = "ALTER" if rol_var_mi else "CREATE"
    return (
        f"{kur} ROLE {ad} LOGIN PASSWORD {parola_literali}",
        f"GRANT USAGE ON SCHEMA public TO {ad}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ad}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ad}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {ad}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {ad}",
    )


def rolu_ac(motor, ad: str, parola: str) -> tuple[bool, bool]:
    """Rolü açar/günceller, yetkileri verir; rolün `(rolsuper, rolbypassrls)` niteliklerini döner.

    `AUTOCOMMIT`: `CREATE ROLE` küme genelinde bir nesne yaratır, bu betiğin
    transaksiyonuna ait değil — bir sonraki deyim düşse bile rol kalmalı ve
    komut yeniden koşulabilmeli.
    """
    with motor.connect().execution_options(isolation_level="AUTOCOMMIT") as baglanti:
        if baglanti.execute(text("SHOW standard_conforming_strings")).scalar_one() != "on":
            raise KuralDisi("standard_conforming_strings kapali: parola literali guvenli degil.")
        var_mi = baglanti.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :ad"),
                                  {"ad": ad}).scalar_one_or_none() is not None
        for deyim in deyimler(ad, parola_sql(parola), var_mi):
            baglanti.execute(text(deyim))
        nitelik = baglanti.execute(text(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :ad"), {"ad": ad}).one()
        return bool(nitelik[0]), bool(nitelik[1])


def tohumla(motor) -> tuple[uuid.UUID, bool]:
    """`medya` boşsa bir hesap + klasör + medya yazar; `(kullanici_id, yazildi_mi)`."""
    with Session(motor) as oturum:
        var = oturum.execute(text("SELECT kullanici_id FROM medya LIMIT 1")).scalar_one_or_none()
        if var is not None:
            return var, False
        kullanici = Kullanici(eposta=f"rls-prova-{uuid.uuid4().hex[:8]}@example.com",
                              parola_ozeti=None, dogrulandi_at=hesap.simdi(), dil=None)
        oturum.add(kullanici)
        oturum.flush()  # id gerekiyor: bağlam onun üstüne kuruluyor
        # KİRACI = tohumlanan hesap, admin DEĞİL: admin politikası INSERT vermiyor.
        with kiraci.baglam(kullanici_id=kullanici.id, oturum=oturum):
            klasor = Klasor(id=uuid.uuid4().hex, kullanici_id=kullanici.id, name="RLS provasi")
            oturum.add(klasor)
            oturum.flush()
            oturum.add(Medya(id=uuid.uuid4().hex[:12], kullanici_id=kullanici.id,
                             filename=f"{klasor.id}.png", prompt="rls provasi", size="1024x1024",
                             quality="high", folder_id=None, model="prova", credits=1))
            oturum.commit()
        return kullanici.id, True


def _ayristirici() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="uygulama_rolu.py",
        description="RLS'i atlamayan uygulama rolunu acar (DATABASE_URL sahip rolu, "
                    f"parola {PAROLA_ENV} ile).")
    p.add_argument("--ad", default=ONTANIMLI_AD, help=f"rol adi (ontanimli: {ONTANIMLI_AD})")
    p.add_argument("--kuru", action="store_true", help="hicbir sey yazma, kosacak DDL'i bas")
    p.add_argument("--tohum", action="store_true",
                   help="medya BOSSA bir hesap+klasor+medya yaz (bagsiz 0 kapisini anlamli kilar)")
    return p


def main(argv: list[str]) -> int:
    args = _ayristirici().parse_args(argv)
    if not AD_KALIBI.fullmatch(args.ad):
        print(f"--ad kucuk harf/rakam/alt cizgi olmali: {args.ad}", file=sys.stderr)
        return CIKIS_ORTAM

    if args.kuru:
        print(f"--kuru: hicbir sey yazilmadi. {args.ad} icin kosacak deyimler:\n")
        for deyim in deyimler(args.ad, "<PAROLA>", rol_var_mi=False):
            print(f"{deyim};")
        return CIKIS_TAMAM

    url = db.baglanti_dizesi()
    if not url:
        print(f"{db.DATABASE_URL_ENV} verilmedi: rol hangi kumede acilacak bilinmiyor.",
              file=sys.stderr)
        return CIKIS_ORTAM
    parola = os.environ.get(PAROLA_ENV)
    if not parola:
        print(f"{PAROLA_ENV} verilmedi: yeni rolun parolasi ortamdan okunur "
              "(argumanla verilse kabuk gecmisine duserdi).", file=sys.stderr)
        return CIKIS_ORTAM

    motor = create_engine(url, connect_args={"connect_timeout": db.BAGLANTI_ZAMAN_ASIMI_SN})
    try:
        super_mu, bypass_mi = rolu_ac(motor, args.ad, parola)
        print(f"rol {args.ad}: rolsuper={'t' if super_mu else 'f'} "
              f"rolbypassrls={'t' if bypass_mi else 'f'}")
        if super_mu or bypass_mi:
            print("YENI ROL DE RLS'i ATLIYOR: saglayici NOSUPERUSER bir rol vermiyor olabilir. "
                  "Uygulamayi bu rolle baglamak yalitimi ACMAZ.", file=sys.stderr)
            return CIKIS_IS
        if args.tohum:
            kullanici_id, yazildi = tohumla(motor)
            durum = "1 hesap + 1 klasor + 1 medya yazildi" if yazildi else "gerekmedi (medya dolu)"
            print(f"tohum: {durum} - kullanici_id = {kullanici_id}")
    except KuralDisi as hata:
        print(str(hata), file=sys.stderr)
        return CIKIS_ORTAM
    except SQLAlchemyError as hata:
        # SQLAlchemy mesajı URL'deki parolayı maskeliyor; yine de yalnız ilk satır.
        print(f"is dustu: {str(hata).splitlines()[0]}", file=sys.stderr)
        return CIKIS_IS
    finally:
        motor.dispose()

    govde = url.split("@", 1)[1] if "@" in url else url
    print(f"\nuygulamanin DATABASE_URL'i:  postgresql+psycopg://{args.ad}:<PAROLA>@{govde}")
    print("dogrula:  DATABASE_URL=<yeni dize> python tools/rls_kontrol.py --kullanici <uuid>")
    return CIKIS_TAMAM


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
