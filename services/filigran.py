# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Ücretsiz planın görsel filigranı — İŞÇİDE, `_uret` → `_yaz` arası, TEK nesne (Faz 3 / 4, K7).

`uygula(bayt) -> bayt`: sağlayıcının verdiği görseli PNG'ye çevirir
(`gorsel.to_png` — sağlayıcı JPEG/WebP verebilir; 50 MP sınırı da orada) ve
paketle gelen işareti (`bundled/filigran.png`) `composite.composite_logo`nun
konum/ölçek/gölge mantığıyla ALT-SAĞA bindirir: işaret genişliği görselin %6'sı,
opaklık 0,6, gölge `composite.SHADOW_OFFSET` aynen. Çıktı PNG; boyut korunur.

NEDEN BURADA, SERVİS ANINDA DEĞİL (docs/faz3-kredi-defteri-filigran.md §4, K7):
`GET /output/...` uygulama sürecinden bayt taşımıyor (Faz 2 K7: 302 → R2);
servis anında bindirme her indirmeyi uygulamadan geçirir ve kovanın sıfır çıkış
ücretinin sebebini yok ederdi. İki nesne (ham + filigranlı) saklamak ise
depolamayı ikiler ve "hangisi servis edilir" kararını rotaya taşır; yükseltince
geçmişin filigransız açılması ürün vaadi değil. Tek nesne: yazıldığı gibi
servis edilir, `medya.filigranli` yalnız arayüz bilgisi.

İŞARET DOSYASI YOKSA AÇIK HATA, SESSİZ FİLİGRANSIZ DEĞİL: `FiligranDosyasiYok`
işi `hata`ya düşürür (işçi `BEKLENMEYEN_HATASI: FiligranDosyasiYok` kodunu yazar,
rezerv iade edilir). Sessizce atlamak ücretsiz kullanıcıya ücretli katmanın
çıktısını verir ve kusur ancak biri fark edince görünürdü — imaja dosyanın
girdiğini `.dockerignore` bekçisi doğrular (tests/test_docker_kapisi.py), sahip
kendi işaretini `KROMIS_FILIGRAN_DOSYASI` ile gösterir.

MARKA-NÖTR İŞARET: dosya soyut bir işaret, "kromis" metni değil — ad ve logo
lisans DIŞI (MARKA.md), depodan kuran kişi kendi işaretini koyar. Dosyayı
`tools/make_filigran.py` deterministik üretir; işaret değişince golden
(`tests/fixtures/filigran/`) aynı araçla yeniden üretilir ve PR'a yazılır.

VİDEO DOKUNULMAZ: `kind == "video"` girdiyi aynen döndürür (işlev düzeyi
muhafız). Ücretsiz planda video modeli zaten kapalı (`planlar.Plan.video`,
K7) — ffmpeg imaja girmiyor; kural bir gün bozulursa bu muhafız filigransız
videoyu SESSİZCE değil, planlar kapısı açılırken bilinçli olarak geçirir.

Kullanıcıya konuşmaz (tests/test_i18n.py sınıflandırması): istisnaları
işçinin `hata.log`una ve `hata` sütununa KOD olarak gider, cümleyi ön yüz kurar.
"""
from __future__ import annotations

import io
import os

from fastapi import HTTPException
from PIL import Image

import composite
import paths
from services import gorsel

__all__ = ["DOSYA_ENV", "KONUM", "OLCEK", "OPAKLIK", "FiligranHatasi", "FiligranDosyasiYok",
           "GorselIslenemedi", "varsayilan_dosya", "dosya_yolu", "uygula"]

# `.env.example` platform bölümü ve `ALTYAPI` bekçisi (tests/test_docker_kapisi.py) aynı adı buradan okur.
DOSYA_ENV = "KROMIS_FILIGRAN_DOSYASI"
# Belge §4'ün sayıları: alt-sağ, görsel genişliğinin %6'sı, opaklık 0,6. Golden
# (tests/fixtures/filigran/golden-256.png) bu üçüne ve işaret dosyasına bağlı —
# biri değişirse `tools/make_filigran.py` ile yeniden üretilir.
KONUM = "bottom-right"
OLCEK = 0.06
OPAKLIK = 0.6


class FiligranHatasi(Exception):
    """Filigran bindirilemedi — işçi işi `hata`ya düşürür, sonucu filigransız YAZMAZ."""


class FiligranDosyasiYok(FiligranHatasi):
    """İşaret dosyası yok ya da PNG olarak açılamıyor (`KROMIS_FILIGRAN_DOSYASI` ya da paket)."""


class GorselIslenemedi(FiligranHatasi):
    """Sağlayıcının verdiği bayt görsel değil ya da 50 MP sınırını aşıyor (`gorsel.to_png` reddetti)."""


def varsayilan_dosya() -> str:
    """Paketle gelen işaret: `<kaynak kökü>/bundled/filigran.png` (i18n ve prompts ile aynı kök)."""
    return os.path.join(paths.resource_dir(), "bundled", "filigran.png")


def dosya_yolu(dosya: str | None = None) -> str:
    """Kullanılacak işaret dosyası: açık argüman > `KROMIS_FILIGRAN_DOSYASI` > paket."""
    return dosya or (os.environ.get(DOSYA_ENV) or "").strip() or varsayilan_dosya()


def _isaret(yol: str) -> io.BytesIO:
    """İşareti RGBA okur, alfasını `OPAKLIK` ile çarpar, `composite_logo`nun açacağı akış olarak verir.

    Opaklık BURADA, composite'te değil: `composite_logo`nun bir opaklık
    parametresi yok ve golden'ları taşıyan imzasına eklemek yerine işaretin
    alfa kanalını önceden ölçeklemek aynı sonucu verir (bindirme
    `alpha_composite`, alfa çarpımsal).
    """
    if not os.path.isfile(yol):
        raise FiligranDosyasiYok(yol)
    try:
        isaret = Image.open(yol).convert("RGBA")
    except Exception as e:
        raise FiligranDosyasiYok(yol) from e
    if isaret.width < 1 or isaret.height < 1:
        raise FiligranDosyasiYok(yol)
    alfa = isaret.getchannel("A").point(lambda a: round(a * OPAKLIK))
    isaret.putalpha(alfa)
    akis = io.BytesIO()
    isaret.save(akis, format="PNG")
    akis.seek(0)
    return akis


def uygula(png: bytes, *, dosya: str | None = None, kind: str = "image") -> bytes:
    """Görseli PNG'ye çevirip işareti alt-sağa bindirir; PNG bayt döner. Video girdi AYNEN döner.

    Çıktının boyutu girdinin boyutudur; şeffaflık KORUNUR (`keep_alpha` —
    sağlayıcının şeffaf arka planlı PNG'si filigranla da şeffaf kalır; composite'in
    kendi çağıranları RGB istiyor, o öntanım değişmedi).
    """
    if kind == "video":
        return png
    isaret = _isaret(dosya_yolu(dosya))
    try:
        temiz = gorsel.to_png(png)
    except HTTPException as e:
        # `to_png` web yolunun 422'sini kurar; işçide HTTP yok — gövdesi (çevrilmiş
        # cümle) değil, sınıfı taşınır: kullanıcıya KOD gider, metni ön yüz kurar.
        raise GorselIslenemedi(str(e.detail)) from e
    return composite.composite_logo(io.BytesIO(temiz), logo_path=isaret, position=KONUM,
                                    scale=OLCEK, keep_alpha=True)
