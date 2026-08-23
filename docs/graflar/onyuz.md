<!-- ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: tools/graf_uret.py · yenilemek için: python3 tools/graf_uret.py -->

# Ön yüz grafı

Betikler küresel kapsamda, `static/index.html`'deki SIRAYLA yükleniyor — modül sistemi yok, yani bir betiğin başka bir betiğin işlevini çağırması sıradan. Aşağıdaki kenarlar o çağrılardan çıkarıldı; ağırlık, paylaşılan ad sayısıdır (yöntem ve sınırı: tools/graf_uret.py).

## Yükleme sırası

1. `/static/pixel-canvas.js`
2. `/static/core.js`
3. `/static/folders.js`
4. `/static/assets.js`
5. `/static/palette.js`
6. `/static/settings.js`
7. `/static/viewer.js`
8. `/static/chat.js`
9. `/static/mobile.js`

Stiller: `/static/fonts.css`, `/static/style.css`, `/static/flow-tokens.css`, `/static/mobile.css`

## Betikler arası çağrı

```mermaid
flowchart LR
  n_assets_js["assets.js"] -->|4| n_core_js["core.js"]
  n_assets_js["assets.js"] -->|2| n_folders_js["folders.js"]
  n_chat_js["chat.js"] -->|10| n_core_js["core.js"]
  n_chat_js["chat.js"] -->|1| n_palette_js["palette.js"]
  n_chat_js["chat.js"] -->|1| n_settings_js["settings.js"]
  n_core_js["core.js"] -->|6| n_chat_js["chat.js"]
  n_core_js["core.js"] -->|2| n_folders_js["folders.js"]
  n_core_js["core.js"] -->|3| n_palette_js["palette.js"]
  n_core_js["core.js"] -->|1| n_settings_js["settings.js"]
  n_folders_js["folders.js"] -->|16| n_core_js["core.js"]
  n_folders_js["folders.js"] -->|1| n_palette_js["palette.js"]
  n_palette_js["palette.js"] -->|4| n_core_js["core.js"]
  n_palette_js["palette.js"] -->|1| n_folders_js["folders.js"]
  n_settings_js["settings.js"] -->|1| n_assets_js["assets.js"]
  n_settings_js["settings.js"] -->|1| n_chat_js["chat.js"]
  n_settings_js["settings.js"] -->|9| n_core_js["core.js"]
  n_settings_js["settings.js"] -->|3| n_folders_js["folders.js"]
  n_settings_js["settings.js"] -->|1| n_palette_js["palette.js"]
  n_viewer_js["viewer.js"] -->|2| n_core_js["core.js"]
```

## Betikler

| betik | satır | üst düzey tanım | çağırdığı sunucu yolları |
| --- | --- | --- | --- |
| `static/assets.js` | 492 | 22 | `/api/assets/{}`, `/api/assets/{}/{}`, `/api/banner`, `/api/banner/preview`, `/api/logo`, `/api/logo/preview`, `/assets/banners/{}`, `/assets/logos/{}`, `/assets/mottos/{}`, `/assets/{}/{}`, `/output/{}` |
| `static/chat.js` | 1796 | 70 | `/api/chat`, `/api/chats`, `/api/chats/{}`, `/api/prefs`, `/output/{}.png` |
| `static/core.js` | 1623 | 59 | `/api/edit`, `/api/generate`, `/api/image/{}`, `/api/output/{}/download`, `/api/prefs`, `/output/`, `/output/{}` |
| `static/folders.js` | 1430 | 50 | `/api/folders`, `/api/folders/{}`, `/api/folders/{}/download`, `/api/history`, `/api/images`, `/api/import`, `/output/{}` |
| `static/mobile.js` | 52 | 0 | — |
| `static/palette.js` | 756 | 37 | `/api/palette/suggest`, `/api/palettes`, `/api/palettes/{}` |
| `static/pixel-canvas.js` | 347 | 0 | — |
| `static/settings.js` | 418 | 11 | `/api/prefs`, `/api/settings` |
| `static/viewer.js` | 368 | 0 | `/output/` |

