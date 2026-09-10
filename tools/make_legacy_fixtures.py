#!/usr/bin/env python3
"""v1.8 biçimli veri dizinini fixture olarak DONDURUR (bir kez çalıştırılır).

Neden: "yeni alan ekle, `.get()` ile oku, migration yazma" kuralı bugüne dek
doğru uygulandı (bkz. storage.py'deki folder_id / palette / prompt_sent
yorumları) ama hiçbir test onu korumuyordu. Bir alan yeniden ADLANDIRILIRSA
ofisteki çalışanın kütüphanesi okunamaz olur ve bunu ilk fark eden çalışan
olur. tests/test_legacy_formats.py bu ağaca karşı koşar.

ÜRETİM DÜRÜSTLÜĞÜ (tools/make_logo_goldens.py'deki dersin aynısı: vakaların
tek kaynağı üreticinin KENDİ çıktısı olmalı):
kromis.spec gönderilen sürümün 1.8.0 olduğunu söylüyor ve git tag
yok — yani v1.9 yazıcı değişikliği inmeden önce bugünkü çalışma ağacı 1.8.0
üreticisinin kendisidir. Bu yüzden kayıtlar GERÇEK yazıcılar çağrılarak
üretilir (storage.save / folders.create / palette_store.create /
assets_store.save_asset) ve cases.json onların DÖNDÜRDÜĞÜ kayıtlardan yazılır.
Ağacı elle yazmak, v1.8'in ne yazdığına dair İNANCI dondurmak olurdu; bir alanı
yanlış hatırlarsak test bir kurguyu kanonlaştırır ve özelliği tersine çevirip
yalancı bir güvenceye dönüştürür.

TEK KAÇINILMAZ İSTİSNA, etiketiyle: `folder_id`/`palette`/`prompt_sent`
anahtarlarının gerçekten YOK olduğu pre-v1.6 kaydı hiçbir yazıcıdan çıkamaz
(v1.8'in storage.save'i anahtarları her zaman yazar). O kayıt ve `parent_id`'si
olmayan legacy klasör elle yazılır ve cases.json'da "handmade" altında
listelenir. Şekilleri, hâlihazırda elle yazan iki testten alındı:
tests/test_folders.py ve tests/test_palette_route.py.

    .venv/bin/python tools/make_legacy_fixtures.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import assets_store  # noqa: E402
import folders  # noqa: E402
import palette_store  # noqa: E402
import storage  # noqa: E402

FIXTURES = os.path.join(REPO, "tests", "fixtures", "v18")
OUTPUT = os.path.join(FIXTURES, "output")
ASSETS = os.path.join(FIXTURES, "assets")

# Dondurulmuş ağaç sürüm kontrolüne giriyor: PNG'ler mümkün olan en küçük
# geçerli dosya olsun. 1x1 saydam PNG.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082")

# v1.8'de üretim yolunun yazdığı palet dict'i (app._palette_prompt'un `record`i).
# Türkçe adlar KASITLI: ensure_ascii=False de bu kancada.
FROZEN_COLORS = [
    {"hex": "#c86a3c", "name": "Kiremit"},
    {"hex": "#3c86c8", "name": "Gök Mavisi"},
    {"hex": "#6ac83c", "name": "Fıstık Yeşili"},
    {"hex": "#c83c86", "name": "Fuşya"},
    {"hex": "#3cc86a", "name": "Zümrüt"},
]


def _git_sha() -> str:
    try:
        out = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "bilinmiyor"


def _append_raw(path: str, record: dict) -> None:
    """Yazıcıyı ATLAYARAK kayıt ekler — elle yazılan legacy kayıtlar için.

    Yazıcı anahtarları her zaman yazdığı için "anahtarı hiç olmayan" kaydı
    yalnızca böyle üretebiliyoruz (bkz. modül docstring'i).
    """
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    items.append(record)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def main() -> int:
    if os.path.exists(FIXTURES):
        shutil.rmtree(FIXTURES)
    os.makedirs(OUTPUT)

    now = "2026-07-29T10:00:00"

    # ── klasörler ────────────────────────────────────────────────────────
    root_folder = folders.create("Kampanya", OUTPUT, parent_id=None, now=now)
    child_folder = folders.create("Instagram", OUTPUT,
                                  parent_id=root_folder["id"], now=now)

    # ── geçmiş kayıtları (gerçek yazıcı) ─────────────────────────────────
    plain = storage.save(TINY_PNG, {
        "prompt": "sade bir afiş", "size": "1024x1024", "quality": "high",
    }, OUTPUT, now=now)

    foldered = storage.save(TINY_PNG, {
        "prompt": "klasördeki görsel", "size": "1024x1024", "quality": "high",
        "folder_id": child_folder["id"],
    }, OUTPUT, now=now)

    with_palette = storage.save(TINY_PNG, {
        "prompt": "paletli görsel", "size": "1536x1024", "quality": "medium",
        "palette": {"seed": "#c86a3c", "mode": "triad", "strength": "balanced",
                    "colors": FROZEN_COLORS, "applied": True},
        "prompt_sent": "paletli görsel [renk yönlendirmesi]",
    }, OUTPUT, now=now)

    derivative = storage.save(TINY_PNG, {
        "prompt": "türev görsel", "size": "1024x1024", "quality": "high",
        "parent_id": plain["id"],
    }, OUTPUT, now=now)

    # ── paletler (gerçek yazıcı) ─────────────────────────────────────────
    saved_palette = palette_store.create(
        "Sonbahar", "#c86a3c", "triad", "balanced", FROZEN_COLORS, OUTPUT, now=now)
    palette_store.create(
        "Kış", "#3c86c8", "complementary", "strict",
        [{"hex": "#3c86c8", "name": "Buz"}, {"hex": "#c8863c", "name": "Kehribar"}],
        OUTPUT, now=now)

    # ── varlıklar (gerçek yazıcı, üç tür) ────────────────────────────────
    asset_ids: dict[str, list[str]] = {}
    for kind, names in (("logos", ["Şirket Logosu Mavi", "Şirket Logosu Beyaz"]),
                        ("banners", ["Alt Şerit"]),
                        ("mottos", ["Motto Beyaz"])):
        recs = [assets_store.save_asset(kind, TINY_PNG, name, ASSETS, now=now)
                for name in names]
        # list_assets en yeniyi başa alıyor → beklenti de o sırada dondurulur.
        asset_ids[kind] = [r["id"] for r in reversed(recs)]

    # ── ELLE yazılan legacy kayıtlar (yazıcıdan çıkamaz) ─────────────────
    legacy_image = {
        "id": "aaaaaaaaaaaa",
        "filename": "aaaaaaaaaaaa.png",
        "prompt": "pre-v1.6 kaydı: folder_id/palette/prompt_sent anahtarları YOK",
        "size": "1024x1024",
        "quality": "high",
        "created_at": "2026-07-01T09:00:00",
        "parent_id": None,
    }
    with open(os.path.join(OUTPUT, legacy_image["filename"]), "wb") as f:
        f.write(TINY_PNG)
    _append_raw(os.path.join(OUTPUT, storage.HISTORY_FILE), legacy_image)

    legacy_folder = {
        "id": "bbbbbbbbbbbb",
        "name": "Eski Klasör (parent_id anahtarı YOK)",
        "created_at": "2026-07-01T09:00:00",
    }
    _append_raw(os.path.join(OUTPUT, folders.FOLDERS_FILE), legacy_folder)

    # ── künye + beklentiler: yazıcıların DÖNDÜRDÜĞÜ kayıtlardan ──────────
    cases = {
        "produced_from": _git_sha(),
        "produced_at": now,
        "app_version": "1.8.0",
        "note": ("Bu ağaç 1.8.0'ı gönderen çalışma ağacının KENDİ yazıcılarıyla "
                 "üretildi; 'handmade' dışındaki hiçbir kayıt elle yazılmadı."),
        "handmade": [legacy_image["id"], legacy_folder["id"]],
        "expect": {
            # list_history en yeniyi başa alıyor; elle eklenen kayıt dosyanın
            # SONUNA yazıldığı için okurken EN BAŞTA gelir.
            "root_history_ids": [legacy_image["id"], derivative["id"],
                                 with_palette["id"], plain["id"]],
            "foldered": {child_folder["id"]: [foldered["id"]]},
            "folders": {
                "root": root_folder["id"],
                "child": child_folder["id"],
                "legacy_no_parent_id": legacy_folder["id"],
            },
            "derivative": {"id": derivative["id"], "parent_id": plain["id"]},
            "palette_record_image_id": with_palette["id"],
            "palette": {
                "id": saved_palette["id"],
                "name": saved_palette["name"],
                "seed": saved_palette["seed"],
                "mode": saved_palette["mode"],
                "strength": saved_palette["strength"],
                "colors": saved_palette["colors"],
            },
            "assets": asset_ids,
        },
    }
    with open(os.path.join(FIXTURES, "cases.json"), "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
        f.write("\n")

    for root, _dirs, files in os.walk(FIXTURES):
        for name in sorted(files):
            path = os.path.join(root, name)
            print(f"✓ {os.path.relpath(path, REPO)} ({os.path.getsize(path)} bayt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
