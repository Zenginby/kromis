# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Palet uçları: harmoni önerisi ve kayıtlı palet kütüphanesi.

Adı ÇOĞUL (`paletler`), çünkü tekil `palet` rota dışı çözümlemenin modülü
(`services/palet.py`) ve iki dosyanın aynı adı taşıması `from services import
palet` satırını bu dosyada okunmaz yapardı.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

import color_names
import i18n
import palette
import palette_store
from models import SavePaletteRequest, SuggestRequest
from services import ayar, dil, kimlik, palet, zaman
from services.tablolar import Kullanici

router = APIRouter()


@router.post("/api/palette/suggest")
def suggest_palettes(req: SuggestRequest,
                     kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """KAPI DOĞRUDAN (Faz 1 / 4): veri okumaz ama `thecolorapi.com`a çıkıyor —
    anonim istek kotayı yer (belge §4). `kullanici` imzada, gövdede okunmuyor.

    Tohum renkten altı harmoni önerisi. Diske hiçbir şey yazmaz.

    İsimlendirme burada bilinçli olarak ÇEVRİMDIŞI: keşif sırasında 30 rengi
    thecolorapi'ye sormak ölçülen 2.5 sn'lik bir bekleme getiriyor ve kazanç
    marjinal (gömülü tablo "copper orange", "cobalt blue" gibi zaten iyi adlar
    veriyor). Buna karşılık çevrimdışı olması üç şey kazandırıyor: öneriler
    anında gelir, deterministiktir, ve kartta GÖRÜLEN ad ile prompt'a GİDEN ad
    birebir aynı olur (üretim yolu da çevrimdışı).

    thecolorapi kullanıcı paleti KAYDEDERKEN devreye girer: 5 renk, tek bütçe,
    kullanıcı kararını vermiş, ve sonuç kayda dondurulup palette_id ile
    gerçekten prompt'a girer (bkz. create_palette_route, palet.palette_prompt).
    """
    per_mode = {mode: palette.harmony(req.hex, mode) for mode in palette.MODES}
    resolved = color_names.names_map(
        [h for hexes in per_mode.values() for h in hexes], offline=True)
    return {
        "seed": req.hex,
        "items": [
            {"mode": mode,
             # Tekilleştirme palet BAŞINA yapılır: aynı ad farklı paletlerde
             # geçebilir (sorun değil), ama tek palet içinde geçemez.
             "colors": color_names.dedupe_names(
                 [{"hex": h, "name": resolved[h]} for h in hexes])}
            for mode, hexes in per_mode.items()
        ],
    }


@router.get("/api/palettes")
def list_palettes_route(ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> dict:
    return {"items": palette_store.list_palettes(ayarlar.output_dir)}


@router.post("/api/palettes")
def create_palette_route(req: SavePaletteRequest,
                         ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> dict:
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail=i18n.t("err.palette_name_required", dil.aktif()))
    # Renkleri SUNUCU yeniden hesaplar: istemci renk listesi göndermediği için
    # doğrulanacak istemci verisi yok ve tek doğruluk kaynağı korunur.
    #
    # thecolorapi'nin devreye girdiği TEK yer burası: yalnızca 5 renk, tek
    # bütçe, kullanıcı "bunu saklıyorum" demiş. Dönen adlar kayda dondurulur
    # ve palette_id ile prompt'a girer; API sonradan çökse bile bu palet
    # kaydedildiği günkü prompt'u üretmeye devam eder.
    colors = palet.resolve_palette(req.seed, req.mode, offline=False)
    # Çıkarma DONMA'dan önce uygulanır: kayıt kaç renk taşıyorsa o kadarı
    # prompt'a gider ve sonraki kullanımlarda çıkarma göndermek gerekmez.
    # Kalıcı olarak daha az renkli bir paletin tek yolu bu (bkz. models.drop).
    colors = palet.drop_colors(colors, req.drop)
    return {"palette": palette_store.create(name, req.seed, req.mode, req.strength,
                                            colors, ayarlar.output_dir, now=zaman.simdi())}


@router.delete("/api/palettes/{palette_id}")
def delete_palette_route(palette_id: str,
                         ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> dict:
    pid = os.path.basename(palette_id)
    if not palette_store.delete(pid, ayarlar.output_dir):
        raise HTTPException(status_code=404, detail=i18n.t("err.palette_missing", dil.aktif()))
    return {"deleted": pid}
