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
  n_assets_js["assets.js"] -->|5| n_core_js["core.js"]
  n_assets_js["assets.js"] -->|2| n_folders_js["folders.js"]
  n_chat_js["chat.js"] -->|13| n_core_js["core.js"]
  n_chat_js["chat.js"] -->|1| n_folders_js["folders.js"]
  n_chat_js["chat.js"] -->|1| n_palette_js["palette.js"]
  n_chat_js["chat.js"] -->|1| n_settings_js["settings.js"]
  n_core_js["core.js"] -->|10| n_chat_js["chat.js"]
  n_core_js["core.js"] -->|2| n_folders_js["folders.js"]
  n_core_js["core.js"] -->|3| n_palette_js["palette.js"]
  n_core_js["core.js"] -->|1| n_settings_js["settings.js"]
  n_folders_js["folders.js"] -->|17| n_core_js["core.js"]
  n_folders_js["folders.js"] -->|1| n_palette_js["palette.js"]
  n_palette_js["palette.js"] -->|4| n_core_js["core.js"]
  n_palette_js["palette.js"] -->|1| n_folders_js["folders.js"]
  n_settings_js["settings.js"] -->|1| n_assets_js["assets.js"]
  n_settings_js["settings.js"] -->|1| n_chat_js["chat.js"]
  n_settings_js["settings.js"] -->|11| n_core_js["core.js"]
  n_settings_js["settings.js"] -->|3| n_folders_js["folders.js"]
  n_settings_js["settings.js"] -->|1| n_palette_js["palette.js"]
  n_viewer_js["viewer.js"] -->|1| n_assets_js["assets.js"]
  n_viewer_js["viewer.js"] -->|3| n_core_js["core.js"]
```

## Betikler

| betik | satır | üst düzey tanım | çağırdığı sunucu yolları |
| --- | --- | --- | --- |
| `static/assets.js` | 544 | 25 | `/api/assets/{}`, `/api/assets/{}/{}`, `/api/banner`, `/api/banner/preview`, `/api/logo`, `/api/logo/preview`, `/assets/banners/{}`, `/assets/logos/{}`, `/assets/mottos/{}`, `/assets/{}/{}`, `/output/{}` |
| `static/chat.js` | 2453 | 87 | `/api/arena/{}`, `/api/arena/{}/winner`, `/api/chat`, `/api/chats`, `/api/chats/{}`, `/api/prefs`, `/output/{}.${videoMu ` |
| `static/core.js` | 2778 | 83 | `/api/edit`, `/api/generate`, `/api/image/{}`, `/api/output/{}/download`, `/api/prefs`, `/api/video`, `/api/video/animate`, `/output/`, `/output/{}` |
| `static/folders.js` | 1899 | 58 | `/api/folders`, `/api/folders/{}`, `/api/folders/{}/download`, `/api/history`, `/api/images`, `/api/import`, `/output/{}`, `/output/{}${videoMu ` |
| `static/mobile.js` | 52 | 0 | — |
| `static/palette.js` | 756 | 37 | `/api/palette/suggest`, `/api/palettes`, `/api/palettes/{}` |
| `static/pixel-canvas.js` | 347 | 0 | — |
| `static/settings.js` | 448 | 11 | `/api/prefs`, `/api/settings` |
| `static/viewer.js` | 504 | 0 | `/output/` |

