#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Katalogdaki DOĞRULANMAMIŞ tarifeleri basar — `credits` yorumu "doğrulanamadı" diyen modeller (Faz 3 / 5).

    python tools/tarife_kontrol.py

NEDEN VAR: `catalog.py` kredi değerlerinin yanına dürüstçe "birim fiyat
doğrulanamadı / GEÇİCİ" yazıyor (Azure fiyat sayfaları JS ile çiziliyor, tablo
boş döndü — 2026-09-08). O notlar yorumda, yani hiçbir test onları saymıyor ve
sahip bugün hangi dördünü doğrulamak zorunda olduğunu dosyayı okumadan
göremiyor. Bu araç notlu modelleri, bugünkü kredisini ve çapayla bekleneni
(`kredi × catalog.KREDI_USD_CAPASI`, 1 kredi ≈ 0,005 USD) yan yana basar:
sahip sağlayıcının fiyat sayfasıyla karşılaştırır, doğruysa yorumu siler,
değilse `credits`i düzeltir — ikisi de bir PR, geçmiş kayıtlar DEĞİŞMEZ
(`catalog.py`: "tarife değişince geçmiş retroaktif olarak yeniden yazılmasın").

KAYNAĞI OKUR, MODÜLÜ DEĞİL: aradığı şey yorum ve yorum çalışma zamanında
yok. `ast` ile modül düzeyindeki her demet atamasında (`IMAGE_MODELS`,
`VIDEO_MODELS`) her `ImageModel(...)` öğesinin satır aralığı bulunur; bir
modelin "yorum bölgesi" = ÖNCEKİ öğenin bittiği satırdan (ilk öğe için demetin
açıldığı satırdan — dosya başındaki yorumlar hiçbir modele ait değil) bu öğenin
bittiği satıra kadarki `#` satırları. Yani girdinin İÇİNDEKİ yorumlar ve hemen
ÜSTÜNDEKİ blok yorum o modele yazılır — blok yorum bir SONRAKİ girdiyi
anlatıyor sayılır (bugün MAI bloğu "2.6-Flash'ın birim fiyatı DOĞRULANAMADI"
diyor ama 2.6'nın üstünde duruyor; araç 2.6'yı da listeler ve eşleşen satırı
yanına basar ki sahip "neden" sorusunu cevaplasın — cümleyi Flash girdisinin
içine taşımak 2.6'yı listeden düşürür, kod değişmez).

DESEN: aynı yorum satırında `fiyat` VE `doğrulan(a)?madı`, Türkçe katlamayla
büyük/küçük harf duyarsız. `str.lower()` Türkçe `I`yı `i` yapar, `ı` değil —
"DOĞRULANAMADI".lower() "doğrulanamadı" ile EŞLEŞMEZ (ölçüldü); `_katla` önce
`I → ı`, `İ → i` çevirir. "doğrulanmadı" da sayılır (`azure-flux-2-flex`in
kalite kredileri "megapiksel fiyatı doğrulanmadı" ile işaretli, anlam aynı),
ama YALNIZ fiyatla birlikte: sade `doğrulan(a)?madı` deseni ÖLÇÜLDÜ, 8 model
buluyordu ve dördü boyut/çözünürlük notuydu ("boyut jetonu canlı DOĞRULANMADI",
"1080p'si bu depoda doğrulanmadı") — tarifeyle ilgisi yok. `fiyat` şartı
listeyi dörde indiriyor ve dördü de gerçekten tarife notu.

BEKÇİSİ tests/test_araclar.py: aracın bulduğu küme, kataloğu BAĞIMSIZ bir
yolla (satır bazlı tarama) okuyan testin kümesiyle aynı olmak zorunda; not
silinince iki taraf birlikte düşer, elle liste yok (CLAUDE.md § 5).

ÇIKIŞ KODU her zaman 0: bu bir rapor, kapı değil — notlu model olması hata
sayılmaz (sahibin bilinçli "GEÇİCİ" kararı).
"""
from __future__ import annotations

import ast
import dataclasses
import os
import re
import sys
from decimal import Decimal

# Betik olarak koşarken (`python tools/tarife_kontrol.py`) kök modüller görünmez
# (`tools/kullanici.py`nin aynı deyimi); testler `tools.tarife_kontrol` diye ithal ediyor.
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

import catalog  # noqa: E402

KATALOG_YOLU = os.path.join(_KOK, "catalog.py")
# Aynı satırda `fiyat` ve `doğrulan(a)?madı` — katlanmış (küçük harf, Türkçe) metinde aranır.
DESEN = re.compile(r"(?=.*fiyat)(?=.*doğrulan(?:a)?madı)")


def _katla(metin: str) -> str:
    """Türkçe küçük harfe katlama: `I → ı`, `İ → i`, sonra `lower()` (gerekçe modül başında)."""
    return metin.replace("I", "ı").replace("İ", "i").lower()


@dataclasses.dataclass(frozen=True)
class Bulgu:
    """Notlu bir model: kimliği, bugünkü kredisi, kalite kademeleri ve eşleşen yorum satırları."""
    model: str
    credits: int
    credits_by_quality: tuple[tuple[str, int], ...]
    satirlar: tuple[str, ...]

    @property
    def usd(self) -> Decimal:
        return Decimal(self.credits) * catalog.KREDI_USD_CAPASI


def _sabit(cagri: ast.Call, ad: str):
    """`ad=<literal>` anahtar argümanının değeri; yoksa `None`.

    Video girdileri `id`yi bir modül sabitiyle yazıyor (`id=WAN_ID` gibi): literal
    değil `Name` — değeri yüklü `catalog` modülünden okunur (aynı dosya, aynı ad).
    """
    for kw in cagri.keywords:
        if kw.arg != ad:
            continue
        if isinstance(kw.value, ast.Name):
            return getattr(catalog, kw.value.id, None)
        try:
            return ast.literal_eval(kw.value)
        except ValueError:
            return None
    return None


def bul(kaynak: str) -> list[Bulgu]:
    """Kaynak metnindeki notlu modeller, katalog sırasıyla (yorum bölgesi kuralı modül başında)."""
    agac = ast.parse(kaynak)
    satirlar = kaynak.splitlines()
    bulgular: list[Bulgu] = []
    for dugum in agac.body:
        deger = getattr(dugum, "value", None)
        if not isinstance(dugum, ast.Assign | ast.AnnAssign) or not isinstance(deger, ast.Tuple):
            continue
        # Demetin açıldığı satır (`IMAGE_MODELS: … = (`): ilk öğenin bölgesi buradan başlar.
        onceki_son = deger.lineno
        for oge in deger.elts:
            if not (isinstance(oge, ast.Call) and isinstance(oge.func, ast.Name) and oge.func.id == "ImageModel"):
                continue
            son = oge.end_lineno or oge.lineno
            # `satirlar` 0 tabanlı, `lineno` 1 tabanlı: `onceki_son` satırının KENDİSİ dışarıda
            # (demet açılışı ya da önceki öğenin kapanışı), sonrası içeride.
            bolge = [s for s in satirlar[onceki_son:son] if s.strip().startswith("#")]
            onceki_son = son
            eslesen = tuple(s.strip() for s in bolge if DESEN.search(_katla(s)))
            if not eslesen:
                continue
            model = _sabit(oge, "id")
            credits = _sabit(oge, "credits")
            if not isinstance(model, str) or not isinstance(credits, int):
                continue
            kademeler = _sabit(oge, "credits_by_quality") or ()
            bulgular.append(Bulgu(model, credits, tuple(tuple(k) for k in kademeler), eslesen))
    return bulgular


def rapor(bulgular: list[Bulgu]) -> str:
    """İnsan için tablo: model · kredi · ≈USD · kademeler · eşleşen yorum satırları."""
    if not bulgular:
        return "notlu model yok: katalogdaki her tarife dogrulanmis sayiliyor."
    parcalar = [f"{len(bulgular)} model dogrulama bekliyor (1 kredi = {catalog.KREDI_USD_CAPASI} USD):", ""]
    for b in bulgular:
        kademe = (" · " + ", ".join(f"{ad} {k} kr ≈ {Decimal(k) * catalog.KREDI_USD_CAPASI} USD"
                                    for ad, k in b.credits_by_quality)) if b.credits_by_quality else ""
        parcalar.append(f"  {b.model}: {b.credits} kredi ≈ {b.usd} USD{kademe}")
        for s in b.satirlar:
            parcalar.append(f"      {s}")
    return "\n".join(parcalar)


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__.split("\n\n", 1)[0])
        return 0
    with open(KATALOG_YOLU, encoding="utf-8") as f:
        kaynak = f.read()
    print(rapor(bul(kaynak)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
