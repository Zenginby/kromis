# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Palet çözümü ve prompt'a renk yönlendirmesi — üretim ile palet kütüphanesinin ortak yolu.

Üretim router'ı (`/api/generate`, `/api/edit`) ve palet router'ı
(`/api/palettes`) aynı çözümlemeyi kullanıyor; kartta GÖRÜLEN ad ile prompt'a
GİDEN adın birebir aynı olması bu ortaklığa bağlı.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy.orm import Session

import color_names
import i18n
import palette
from models import MAX_PROMPT_CHARS, check_drop_indices
from services import depo_palet, dil


def resolve_palette(seed: str, mode: str, *, offline: bool = False) -> list[dict]:
    """`(seed, mod)` → `[{"hex", "name"}]`. offline=True ise ağa ÇIKMAZ.

    Adlar palet içinde tekilleştirilir: aynı ad iki farklı hex'le prompt'a
    girerse model hangisini kullanacağını bilemez (bkz. dedupe_names).
    """
    hexes = palette.harmony(seed, mode)
    names = color_names.names_for(hexes, offline=offline)
    return color_names.dedupe_names(
        [{"hex": h, "name": n} for h, n in zip(hexes, names)])


def saved_palette(db: Session, kullanici_id: uuid.UUID, palette_id: str | None) -> dict | None:
    """Kullanıcının kayıtlı paletini id ile bulur; yoksa None (hata DEĞİL — bkz. palette_prompt).

    `(db, kullanici_id)` Faz 1 / 6: kayıt `paletler` satırı; başkasının paleti
    de "yok" sayılır ve üretim `(seed, mode)`dan yeniden hesaplar.
    """
    if not palette_id:
        return None
    return depo_palet.bul(db, kullanici_id, os.path.basename(palette_id))


# Kaydın İÇERİĞİ doğrulanmalı (eskiden `palettes.json` elle düzenlenebilirdi;
# bugün `colors` JSONB ve içe aktarma aracı eski dosyayı olduğu gibi taşıyor):
# `mode` ve `seed` doğrudan palette.harmony'ye gidiyor ve orada ValueError
# üretip üretimi 500'e düşürüyordu. Bozuk alan sessizce yok sayılır ve istekle
# gelen değere düşülür — silinmiş palet nasıl bloke etmiyorsa bozuk palet de
# etmemeli.

def safe_seed(value) -> str | None:
    """Kayıttan gelen tohum hex'i; geçersizse None."""
    try:
        return palette.parse_hex(value)
    except (ValueError, TypeError):
        return None


def saved_colors(saved: dict) -> list[dict]:
    """Kayıttaki kullanılabilir renkler: hem `hex` hem `name` taşıyan girdiler."""
    raw = saved.get("colors")
    if not isinstance(raw, list):
        return []
    return [c for c in raw
            if isinstance(c, dict) and c.get("hex") and c.get("name")]


def palette_prompt(prompt: str, seed: str | None, mode: str, strength: str,
                   palette_id: str | None = None, *, task: str, db: Session,
                   kullanici_id: uuid.UUID, drop: Sequence[int] = ()) -> tuple[str, dict | None]:
    """Prompt'a renk yönlendirmesi ekler. Palet yoksa prompt aynen döner.

    `(db, kullanici_id)` yalnız KAYITLI palet aranırken okunuyor (`saved_palette`);
    anahtar-sözcük ve zorunlu, çünkü unutulması sessizce "kayıt yok" demek
    olurdu ve o da bu işlevin bilerek hata SAYMADIĞI bir durum.

    KAYITLI palet kullanılıyorsa renkler/adlar kaydın DONDURULMUŞ halinden
    okunur. Bu, kullanıcının kütüphanede gördüğü adlarla prompt'a giden adların
    her zaman birebir aynı olmasını garanti eder — yeniden hesaplasaydık
    sunucu yeniden başladıktan sonra (önbellek boş) yerel adlara düşer ve
    "bu palet bana o görseli vermişti" sözü tutulamazdı.

    Kayıt bulunamazsa (silinmiş palet) hata verilmez, `(seed, mode)`'dan
    yeniden hesaplanır: silinmiş bir palet üretimi bloke etmemeli.

    Ad çözümlemesi `offline=True`: üretim yolu thecolorapi'yi ASLA beklemez.
    Arayüz aynı tohum için /api/palette/suggest'i çağırdığından adlar
    önbellekte sıcaktır; değilse gömülü tablo mikrosaniyede yanıt verir.

    Prompt uzunluk sınırı kullanıcının metnini doğruluyor, ek sonradan geldiği
    için birleşik metin 4000'i aşabilir. Bu durumda EK DÜŞÜRÜLÜR, kullanıcının
    metni asla kırpılmaz ve istek reddedilmez: paletin görsel üretimini bloke
    etmesi, renk yönlendirmesinin kaybolmasından kötü.

    Düşen ek `applied: False` ile İŞARETLENİR. Kayıt yine tutulur ("istedim")
    ama arayüz bunu uygulanmış bir paletten ayırabilmek zorunda; ayıramazsa
    kullanıcı renksiz sonucu açıklayamaz. Bayrağı çıkarmak yerine koymak, aynı
    sessiz-sapma hatasının bindirme seçeneklerinde yaşanmış halinin tekrarı
    olmasını engelliyor (bkz. 15c6646).
    """
    if not seed:
        return prompt, None
    saved = saved_palette(db, kullanici_id, palette_id)
    if saved:
        mode = saved["mode"] if saved.get("mode") in palette.MODES else mode
        seed = safe_seed(saved.get("seed")) or seed
        colors = saved_colors(saved) or resolve_palette(seed, mode, offline=True)
    else:
        colors = resolve_palette(seed, mode, offline=True)

    # Çıkarma TEK NOKTADA, renkler çözüldükten SONRA uygulanıyor: indeksler
    # böylece kayıtlı paletin DONMUŞ listesinde de tutarlı oluyor (kullanıcı
    # çıkarıp kaydettiyse o liste 5'ten kısa olabilir).
    kept = drop_colors(colors, drop)
    if not kept:
        # models.check_drop_indices'in üst sınırı 5'lik listeye göre; 3 renkli
        # donmuş bir kayıtta [0,1,2] o kapıdan GEÇER ama sonuç boş palet olur.
        # Sessizce çıkarmayı yok saymak yerine gürültülü 422: renksiz sonucu
        # açıklayamayan kullanıcı, bu özelliğin engellemek için var olduğu şey.
        raise HTTPException(status_code=422,
                            detail=i18n.t("err.palette_empty", dil.aktif()))

    suffix = palette.prompt_suffix(kept, strength, task=task)
    applied = len(prompt) + len(suffix) <= MAX_PROMPT_CHARS
    record = {"seed": seed, "mode": mode, "strength": strength,
              # `colors` = KALANLAR: çip ve galeri bunu gösteriyor, yani
              # gösterilen şerit prompt'a gidenle birebir. `dropped` ise
              # geçmişten aynı durumu kurabilmek için.
              "colors": kept, "applied": applied,
              "dropped": sorted(set(drop))}
    if saved:
        record["id"] = saved["id"]
        record["name"] = saved.get("name", "")
    return (prompt + suffix if applied else prompt), record


def check_palette_hex(palette_hex: str | None) -> str | None:
    """Form'dan gelen tohum hex'i normalleştirir; boşsa None, geçersizse 422."""
    if not palette_hex:
        return None
    try:
        return palette.parse_hex(palette_hex)
    except ValueError:
        raise HTTPException(status_code=422, detail=i18n.t("err.bad_palette_hex", dil.aktif()))


def check_palette_drop(value: str | None) -> list[int]:
    """Form'dan gelen `"0,3"` biçimini indeks listesine çevirir; geçersizse 422.

    Arayüz hiçbir şey çıkarılmadığında alanı GÖNDERMİYOR; boş dize de "çıkarma
    yok" demek, hata değil.

    Biçim neden virgüllü metin: core.js palet seçeneklerini genel bir döngüyle
    (`Object.entries(pal)`) FormData'ya basıyor ve orada JS dizisi kendiliğinden
    `"0,3"`'e dönüyor. Döngüyü elle sayıma çevirmek bir kez `palette_id`'yi
    sessizce düşürmüştü (core.js'teki not), o yüzden ayrıştırma burada.
    """
    if not value:
        return []
    try:
        indices = [int(part) for part in value.split(",")]
    except ValueError:
        raise HTTPException(status_code=422, detail=i18n.t("err.bad_palette_drop", dil.aktif()))
    try:
        return check_drop_indices(indices)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def drop_colors(colors: list[dict], drop: Sequence[int]) -> list[dict]:
    """Verilen indeksleri çıkarır; KALANLARIN SIRASI korunur.

    Sıra prompt'ta anlam taşıyor (palette._ORDER_CUE: baştaki renkler geniş
    alanlara, sondaki küçük vurgu olarak). Yeniden dizilse kullanıcının çipte
    gördüğü şerit ile modele giden ağırlık sırası ayrışırdı.
    """
    if not drop:
        return colors
    excluded = set(drop)
    return [c for i, c in enumerate(colors) if i not in excluded]
