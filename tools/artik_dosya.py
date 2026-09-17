#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Artık dosya taraması — DB'de satırı olmayan medya/varlık dosyaları (Faz 1 / 9).

    DATABASE_URL=… KROMIS_DATA_DIR=/data python tools/artik_dosya.py          # yalnız listele (--kuru öntanımlı)
    DATABASE_URL=… KROMIS_DATA_DIR=/data python tools/artik_dosya.py --sil    # sor, onaylanırsa sil
    DATABASE_URL=… KROMIS_DATA_DIR=/data python tools/artik_dosya.py --sil --evet   # sormadan sil (cron)

NEDEN VAR: dosya + satır ATOMİK DEĞİL (5. görevin borcu). `depo_medya.kaydet`
ve `depo_varlik.kaydet` önce dosyayı yazar sonra satırı ekler; satırın commit'i
düşerse (DB kesintisi, kısıt hatası) dosya diskte kalır ve hiçbir rota onu bir
daha görmez — `dosya_yolu` satırdan gider. `tools/ice_aktar.py`nin `temizle`si
yalnız KENDİ koşusunun kopyalarını siler. Bir de silinen hesap: `kullanicilar`
satırı gidince medya/varlık satırları CASCADE ile düşer, dosyalar düşmez.
Bu araç ikisini de bulur.

NE TARANIR: `<veri kökü>/kullanicilar/<uuid>/output/*` (`medya.filename`e
karşı) ve `assets/<tur>/*` (`varliklar.filename`e karşı, `tur` = dizin adı;
`assets_store.KINDS` dışındaki dizinler de taranır — eski `uploads` gibi bir
dizin oraya nasıl gelmişse gelsin, satırı yoktur). Yalnız MEDYA uzantıları
(`storage.MEDIA_TYPES` + varlıkların `.png`i): `guncelleme.json` gibi bir
önbellek ya da `.DS_Store` artık dosya SAYILMAZ, "medya değil" diye sayılır ve
hiç silinmez — aracın işi medya, başka bir dosyayı silmek onun kararı değil.
UUID'ye benzemeyen dizinler atlanır ve bildirilir.

SATIRI OLAN DOSYAYA DOKUNULMAZ — ne kuru ne gerçek koşuda; `--sil` yalnız bu
koşuda "artık" diye listelenenleri siler. Onay: TTY'de `e` ister, `--evet`
yoksa ve TTY yoksa siler DEĞİL, 1 ile çıkar (cron `--evet`i açıkça yazar).
Kullanıcı başına özet basılır (dosya sayısı, artık sayısı, boyut).

ÇIKIŞ KODLARI öteki araçlarla bir: 0 tamam (artık yok ya da hepsi silindi) ·
1 kullanıcı hatası (veri kökü yok, onay reddedildi — hiçbir şey silinmedi) ·
2 ortam (`DATABASE_URL` yok, sunucuya ulaşılamıyor) · 3 bitti ama artık
dosya DURUYOR (kuru koşuda bulundu ya da silinemedi) — cron'un "temiz mi"
sorusunu çıkış kodundan okuması için (`tools/ice_aktar.py`nin 3'üyle aynı sınıf).
"""
from __future__ import annotations

import argparse
import dataclasses
import os
import sys
import uuid

# Betik olarak koşarken (`python tools/artik_dosya.py`) `sys.path[0]` bu dizin
# ve kök modüller görünmez; testler `tools.artik_dosya` diye ithal ediyor.
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from services import ayar, db  # noqa: E402
from services.tablolar import Kullanici, Medya, Varlik  # noqa: E402
from storage import MEDIA_TYPES  # noqa: E402

CIKIS_TAMAM = 0
CIKIS_KULLANICI = 1
CIKIS_ORTAM = 2
CIKIS_ARTIK_VAR = 3

# Medya sayılan uzantılar: galeri türleri + varlıkların PNG'si (aynı küme).
MEDYA_UZANTILARI = frozenset(MEDIA_TYPES) | {".png"}


@dataclasses.dataclass
class KullaniciOzeti:
    """Bir `kullanicilar/<uuid>` dizininin tarama sonucu."""
    kullanici_id: uuid.UUID
    hesap_var: bool
    dosya: int = 0
    medya_degil: int = 0
    artiklar: list[str] = dataclasses.field(default_factory=list)   # mutlak yollar

    @property
    def artik_bayt(self) -> int:
        toplam = 0
        for yol in self.artiklar:
            try:
                toplam += os.path.getsize(yol)
            except OSError:
                pass
        return toplam


@dataclasses.dataclass
class Rapor:
    kullanicilar: list[KullaniciOzeti] = dataclasses.field(default_factory=list)
    atlanan_dizinler: list[str] = dataclasses.field(default_factory=list)   # UUID olmayan adlar
    silinen: int = 0
    silinemeyen: list[str] = dataclasses.field(default_factory=list)

    @property
    def artiklar(self) -> list[str]:
        return [y for k in self.kullanicilar for y in k.artiklar]


def _uuid(ad: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(ad)
    except ValueError:
        return None


def _dosyalar(dizin: str) -> list[str]:
    """Dizindeki düz dosya adları (alt dizinler değil); dizin yoksa boş."""
    try:
        return sorted(a for a in os.listdir(dizin) if os.path.isfile(os.path.join(dizin, a)))
    except FileNotFoundError:
        return []


def _satirdaki_adlar(oturum: Session, kullanici_id: uuid.UUID) -> tuple[set[str], dict[str, set[str]]]:
    """(`medya.filename` kümesi, {tur: `varliklar.filename` kümesi}) — bu kullanıcının."""
    medya = set(oturum.scalars(select(Medya.filename).where(Medya.kullanici_id == kullanici_id)))
    varliklar: dict[str, set[str]] = {}
    for tur, ad in oturum.execute(select(Varlik.tur, Varlik.filename)
                                  .where(Varlik.kullanici_id == kullanici_id)):
        varliklar.setdefault(tur, set()).add(ad)
    return medya, varliklar


def _kullaniciyi_tara(oturum: Session, genel: ayar.Ayarlar, kullanici_id: uuid.UUID) -> KullaniciOzeti:
    ozel = genel.kullanici_icin(kullanici_id)
    hesap_var = oturum.get(Kullanici, kullanici_id) is not None
    # Hesap yoksa satır da yok (CASCADE): sorgu boş küme verir, her medya dosyası artık.
    medya_adlari, varlik_adlari = _satirdaki_adlar(oturum, kullanici_id)
    ozet = KullaniciOzeti(kullanici_id=kullanici_id, hesap_var=hesap_var)

    def _ele(dizin: str, ad: str, satirdakiler: set[str]) -> None:
        ozet.dosya += 1
        if os.path.splitext(ad)[1].lower() not in MEDYA_UZANTILARI:
            ozet.medya_degil += 1
            return
        if ad not in satirdakiler:
            ozet.artiklar.append(os.path.join(dizin, ad))

    for ad in _dosyalar(ozel.output_dir):
        _ele(ozel.output_dir, ad, medya_adlari)
    try:
        turler = sorted(t for t in os.listdir(ozel.assets_dir)
                        if os.path.isdir(os.path.join(ozel.assets_dir, t)))
    except FileNotFoundError:
        turler = []
    for tur in turler:
        tur_dizini = os.path.join(ozel.assets_dir, tur)
        for ad in _dosyalar(tur_dizini):
            _ele(tur_dizini, ad, varlik_adlari.get(tur, set()))
    return ozet


def tara(oturum: Session, genel: ayar.Ayarlar) -> Rapor:
    """`<data_dir>/kullanicilar/*` altını tarar; hiçbir şey yazmaz, silmez."""
    rapor = Rapor()
    kok = os.path.join(genel.data_dir, ayar.KULLANICILAR_DIZINI)
    try:
        adlar = sorted(os.listdir(kok))
    except FileNotFoundError:
        return rapor
    for ad in adlar:
        if not os.path.isdir(os.path.join(kok, ad)):
            continue
        kimlik = _uuid(ad)
        if kimlik is None:
            rapor.atlanan_dizinler.append(ad)
            continue
        rapor.kullanicilar.append(_kullaniciyi_tara(oturum, genel, kimlik))
    return rapor


def sil(rapor: Rapor) -> None:
    """Raporda ARTIK diye listelenenleri siler — başka hiçbir yolu değil."""
    for yol in rapor.artiklar:
        try:
            os.remove(yol)
            rapor.silinen += 1
        except OSError:
            rapor.silinemeyen.append(yol)


def _onay(evet: bool) -> bool:
    if evet:
        return True
    if not sys.stdin.isatty():
        print("onay icin TTY yok; sormadan silmek icin --evet verin. Hicbir sey silinmedi.",
              file=sys.stderr)
        return False
    return input("Listelenen artik dosyalar SILINSIN mi? [e/H] ").strip().lower() == "e"


def _yazdir(rapor: Rapor, kok: str) -> None:
    print(f"veri koku: {kok}")
    for k in rapor.kullanicilar:
        etiket = "" if k.hesap_var else "  (HESABI YOK — satirlar CASCADE ile dusmus, dosyalar kalmis)"
        print(f"{k.kullanici_id}: {k.dosya} dosya, {len(k.artiklar)} artik "
              f"({k.artik_bayt} bayt), {k.medya_degil} medya degil{etiket}")
        for yol in k.artiklar:
            print(f"  artik: {os.path.relpath(yol, kok)}")
    for ad in rapor.atlanan_dizinler:
        print(f"atlandi (UUID degil): kullanicilar/{ad}")
    print(f"toplam: {len(rapor.kullanicilar)} kullanici, {len(rapor.artiklar)} artik dosya")


def _ayristirici() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="artik_dosya.py",
        description="DB'de satiri olmayan medya/varlik dosyalarini listeler (ontanimli --kuru), "
                    "--sil ile siler. DATABASE_URL + KROMIS_DATA_DIR ile.")
    p.add_argument("--veri-dizini", default=None,
                   help="web surumunun KROMIS_DATA_DIR'i; verilmezse ortamdaki KROMIS_DATA_DIR / paths.data_dir()")
    p.add_argument("--kuru", action="store_true", default=True,
                   help="yalnizca listele (ontanimli); --sil bunu kapatir")
    p.add_argument("--sil", action="store_true", help="listelenen artik dosyalari sil")
    p.add_argument("--evet", action="store_true", help="--sil icin onay sorma (betik/cron)")
    return p


def main(argv: list[str]) -> int:
    args = _ayristirici().parse_args(argv)
    url = db.baglanti_dizesi()
    if not url:
        print(f"{db.DATABASE_URL_ENV} verilmedi: bu arac satirlari veri tabanindan okur.", file=sys.stderr)
        return CIKIS_ORTAM
    genel = ayar.Ayarlar.varsayilan()
    if args.veri_dizini:
        genel = dataclasses.replace(genel, data_dir=os.path.abspath(args.veri_dizini))
    if not os.path.isdir(genel.data_dir):
        print(f"veri koku yok: {genel.data_dir}", file=sys.stderr)
        return CIKIS_KULLANICI

    motor = db.motor_kur(url)
    try:
        with Session(motor) as oturum:
            rapor = tara(oturum, genel)
    except SQLAlchemyError as hata:
        print(f"veri tabani hatasi ({type(hata).__name__}): {str(hata).splitlines()[0]}", file=sys.stderr)
        return CIKIS_ORTAM
    finally:
        motor.dispose()

    _yazdir(rapor, genel.data_dir)
    if not rapor.artiklar:
        return CIKIS_TAMAM
    if not args.sil:
        print("kuru kosu: hicbir sey silinmedi (silmek icin --sil)")
        return CIKIS_ARTIK_VAR
    if not _onay(args.evet):
        return CIKIS_KULLANICI
    sil(rapor)
    print(f"silindi: {rapor.silinen}")
    for yol in rapor.silinemeyen:
        print(f"silinemedi: {yol}", file=sys.stderr)
    return CIKIS_ARTIK_VAR if rapor.silinemeyen else CIKIS_TAMAM


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
