#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Yerel medyayı kovaya taşır — `KROMIS_DATA_DIR/kullanicilar/*` → S3/R2, AYNI anahtarla (Faz 2 / 2).

    KROMIS_NESNE_DEPO_URL=… _KOVA=… _ANAHTAR_ID=… _GIZLI=… \\
      python tools/medya_tasi.py --kaynak /data --kuru      # say: kaç dosya yüklenecek, kaçı zaten kovada
    … python tools/medya_tasi.py --kaynak /data             # yükle (PUT), her birini HEAD ile doğrula
    … python tools/medya_tasi.py --kaynak /data --yeniden   # kovadakini de yeniden yükle (boyut eşit olsa da)

NEDEN VAR: medya bugüne kadar yerel diskte (`kullanicilar/<uuid>/{output,assets}`),
Faz 2 / 2 ile kovaya geçiyor ve İKİLİ OKUMA KODU YOK, bilerek (belge §2): kesme
anı sahibin verisi (beta yok), sıra "araç → ortam değişkenleri → dağıt". İki yolu
aynı anda tutmak her okuma rotasına bir dal ve bir test eklerdi; kesmeyi bir
kez yapmak daha ucuz. Bu araç o kesmenin ilk adımı.

ANAHTAR = YOL: `kullanicilar/<uuid>/output/<ad>` ve `…/assets/<tur>/<ad>` —
`services/dosya.py`nin çevirisiyle birebir, yani uygulama kovaya geçince
aynı satırlar aynı dosyayı bulur. Yalnız MEDYA uzantıları (`tools/artik_dosya.py`
ile aynı küme); `guncelleme.json` gibi önbellekler kovaya gitmez. UUID
olmayan dizinler atlanır ve bildirilir.

İDEMPOTENT: her dosya için önce HEAD; kovada aynı BOYUTTA duruyorsa atlanır
(ikinci koşu 0 yükleme). `--yeniden` bunu kapatır. Yükleme sonrası HEAD ile
boyut doğrulanır; uyuşmazsa "dogrulanamadi" sayılır ve çıkış 3.

YERELİ HİÇ SİLMEZ — `--sil` YOK, bilerek: `ice_aktar`ın "kaynak dokunulmaz"
kuralı. Yerel kopyayı sahibi canlı doğrulamadan (KURULUM.md → Web sürümü →
nesne depolama) SONRA kendisi arşivler/siler.

ÇIKIŞ KODLARI öteki araçlarla bir: 0 tamam (her şey kovada) · 1 kullanıcı
hatası (kaynak dizin yok) · 2 ortam (nesne depolama yapılandırılmamış, kovaya
ulaşılamıyor) · 3 bitti ama iş KALDI (kuru koşuda yüklenecek var, gerçek koşuda
yüklenemeyen/doğrulanamayan var) — betiğin "taşıma tamam mı" sorusunu çıkış
kodundan okuması için.
"""
from __future__ import annotations

import argparse
import dataclasses
import os
import sys
import uuid

# Betik olarak koşarken (`python tools/medya_tasi.py`) `sys.path[0]` bu dizin
# ve kök modüller görünmez; testler `tools.medya_tasi` diye ithal ediyor.
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from services import ayar, dosya  # noqa: E402
from storage import MEDIA_TYPES, media_type_for  # noqa: E402

CIKIS_TAMAM = 0
CIKIS_KULLANICI = 1
CIKIS_ORTAM = 2
CIKIS_KALDI = 3

# `tools/artik_dosya.py::MEDYA_UZANTILARI` ile aynı küme: taşınan = taranan.
MEDYA_UZANTILARI = frozenset(MEDIA_TYPES) | {".png"}


@dataclasses.dataclass
class KullaniciOzeti:
    kullanici_id: uuid.UUID
    dosya: int = 0
    medya_degil: int = 0
    zaten_var: int = 0
    yuklenen: int = 0           # kuru koşuda: yüklenecek
    bayt: int = 0               # yüklenen (ya da yüklenecek) bayt
    basarisiz: list[str] = dataclasses.field(default_factory=list)   # anahtar: hata


@dataclasses.dataclass
class Rapor:
    kuru: bool
    kullanicilar: list[KullaniciOzeti] = dataclasses.field(default_factory=list)
    atlanan_dizinler: list[str] = dataclasses.field(default_factory=list)

    @property
    def yuklenen(self) -> int:
        return sum(k.yuklenen for k in self.kullanicilar)

    @property
    def basarisiz(self) -> list[str]:
        return [b for k in self.kullanicilar for b in k.basarisiz]


def _uuid(ad: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(ad)
    except ValueError:
        return None


def _dosyalar(kok: str) -> list[str]:
    """`kok` altındaki (bir düzeye kadar iç içe: `assets/<tur>/`) düz dosyaların mutlak yolları."""
    yollar: list[str] = []
    try:
        for ad in sorted(os.listdir(kok)):
            tam = os.path.join(kok, ad)
            if os.path.isfile(tam):
                yollar.append(tam)
            elif os.path.isdir(tam):
                yollar += [os.path.join(tam, alt) for alt in sorted(os.listdir(tam))
                           if os.path.isfile(os.path.join(tam, alt))]
    except FileNotFoundError:
        pass
    return yollar


def _anahtar(kaynak: str, yol: str) -> str:
    return os.path.relpath(yol, kaynak).replace(os.sep, "/")


def _kullaniciyi_tasi(istemci, kaynak: str, ozel: ayar.Ayarlar, kullanici_id: uuid.UUID, *,
                      kuru: bool, yeniden: bool) -> KullaniciOzeti:
    ozet = KullaniciOzeti(kullanici_id=kullanici_id)
    for yol in _dosyalar(ozel.output_dir) + _dosyalar(ozel.assets_dir):
        ozet.dosya += 1
        if os.path.splitext(yol)[1].lower() not in MEDYA_UZANTILARI:
            ozet.medya_degil += 1
            continue
        anahtar = _anahtar(kaynak, yol)
        boyut = os.path.getsize(yol)
        mevcut = istemci.bas(anahtar)
        if mevcut is not None and mevcut.boyut == boyut and not yeniden:
            ozet.zaten_var += 1
            continue
        ozet.yuklenen += 1
        ozet.bayt += boyut
        if kuru:
            continue
        with open(yol, "rb") as f:
            veri = f.read()
        istemci.koy(anahtar, veri, media_type_for(os.path.basename(yol)))
        # Doğrulama: yazdığımız boyut kovada da o mu? Yarım kalan/kesilen bir PUT
        # burada görünsün, "taşındı" denip yerel kopya arşivlenmesin.
        dogrulama = istemci.bas(anahtar)
        if dogrulama is None or dogrulama.boyut != boyut:
            ozet.yuklenen -= 1
            ozet.bayt -= boyut
            ozet.basarisiz.append(f"{anahtar}: dogrulanamadi (kovada {dogrulama.boyut if dogrulama else 'yok'}, "
                                  f"yerelde {boyut})")
    return ozet


def tasi(istemci, kaynak: str, *, kuru: bool = False, yeniden: bool = False) -> Rapor:
    """`<kaynak>/kullanicilar/*` altını kovaya taşır (kuru koşuda yalnız sayar). Yereli silmez."""
    rapor = Rapor(kuru=kuru)
    genel = ayar.Ayarlar(data_dir=kaynak, output_dir=os.path.join(kaynak, "output"),
                         assets_dir=os.path.join(kaynak, "assets"), static_dir="")
    kok = os.path.join(kaynak, ayar.KULLANICILAR_DIZINI)
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
        rapor.kullanicilar.append(_kullaniciyi_tasi(istemci, kaynak, genel.kullanici_icin(kimlik), kimlik,
                                                    kuru=kuru, yeniden=yeniden))
    return rapor


def _yazdir(rapor: Rapor, kaynak: str, kova: str) -> None:
    print(f"kaynak: {kaynak}  →  kova: {kova}{'  (KURU KOSU)' if rapor.kuru else ''}")
    fiil = "yuklenecek" if rapor.kuru else "yuklendi"
    for k in rapor.kullanicilar:
        print(f"{k.kullanici_id}: {k.dosya} dosya, {k.zaten_var} zaten kovada, "
              f"{k.yuklenen} {fiil} ({k.bayt} bayt), {k.medya_degil} medya degil"
              + (f", {len(k.basarisiz)} BASARISIZ" if k.basarisiz else ""))
        for satir in k.basarisiz:
            print(f"  basarisiz: {satir}")
    for ad in rapor.atlanan_dizinler:
        print(f"atlandi (UUID degil): kullanicilar/{ad}")
    print(f"toplam: {len(rapor.kullanicilar)} kullanici, {rapor.yuklenen} {fiil}, "
          f"{len(rapor.basarisiz)} basarisiz. Yerel dosyalara DOKUNULMADI.")


def _ayristirici() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="medya_tasi.py",
        description="KROMIS_DATA_DIR/kullanicilar/* altindaki medyayi ayni anahtarla kovaya yukler "
                    "(KROMIS_NESNE_DEPO_* ortamdan). Yereli SILMEZ.")
    p.add_argument("--kaynak", default=None,
                   help="web surumunun KROMIS_DATA_DIR'i; verilmezse ortamdaki KROMIS_DATA_DIR / paths.data_dir()")
    p.add_argument("--kuru", action="store_true", help="yalnizca say, hicbir sey yukleme")
    p.add_argument("--yeniden", action="store_true",
                   help="kovada ayni boyutta duran dosyayi da yeniden yukle")
    return p


def main(argv: list[str]) -> int:
    args = _ayristirici().parse_args(argv)
    kaynak = os.path.abspath(args.kaynak) if args.kaynak else ayar.Ayarlar.varsayilan().data_dir
    if not os.path.isdir(kaynak):
        print(f"kaynak dizin yok: {kaynak}", file=sys.stderr)
        return CIKIS_KULLANICI
    try:
        depo = dosya.depo_kur(kaynak)
    except dosya.YapilandirmaHatasi as hata:
        print(str(hata), file=sys.stderr)
        return CIKIS_ORTAM
    if not isinstance(depo, dosya.NesneDepo):
        print("nesne depolama yapilandirilmamis: " + ", ".join(dosya.ZORUNLU_ENV) + " dordu de gerekli.",
              file=sys.stderr)
        return CIKIS_ORTAM
    try:
        rapor = tasi(depo.istemci, kaynak, kuru=args.kuru, yeniden=args.yeniden)
    except dosya.DosyaHatasi as hata:
        print(f"kova hatasi: {hata}", file=sys.stderr)
        return CIKIS_ORTAM
    except Exception as hata:   # NesneHatasi dâhil: gizli taşımaz (services/nesne_depo.py)
        print(f"kova hatasi ({type(hata).__name__}): {hata}", file=sys.stderr)
        return CIKIS_ORTAM
    _yazdir(rapor, kaynak, depo.istemci.kova)
    if rapor.basarisiz or (args.kuru and rapor.yuklenen):
        return CIKIS_KALDI
    return CIKIS_TAMAM


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
