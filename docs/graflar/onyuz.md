<!-- ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: tools/graf_uret.py · yenilemek için: python3 tools/graf_uret.py -->

# Ön yüz grafı

Betikler küresel kapsamda, `static/index.html`'deki SIRAYLA yükleniyor — modül sistemi yok, yani bir betiğin başka bir betiğin işlevini çağırması sıradan. Aşağıdaki kenarlar o çağrılardan çıkarıldı; ağırlık, paylaşılan ad sayısıdır (yöntem ve sınırı: tools/graf_uret.py).

## Yükleme sırası

1. `/static/i18n.js`
2. `/static/pixel-canvas.js`
3. `/static/core.js`
4. `/static/folders.js`
5. `/static/assets.js`
6. `/static/palette.js`
7. `/static/settings.js`
8. `/static/viewer.js`
9. `/static/chat.js`
10. `/static/mobile.js`

Stiller: `/static/fonts.css`, `/static/style.css`, `/static/flow-tokens.css`, `/static/mobile.css`

## Betikler arası çağrı

```mermaid
flowchart LR
  n_assets_js["assets.js"] -->|5| n_core_js["core.js"]
  n_assets_js["assets.js"] -->|2| n_folders_js["folders.js"]
  n_assets_js["assets.js"] -->|1| n_i18n_js["i18n.js"]
  n_chat_js["chat.js"] -->|18| n_core_js["core.js"]
  n_chat_js["chat.js"] -->|1| n_folders_js["folders.js"]
  n_chat_js["chat.js"] -->|1| n_i18n_js["i18n.js"]
  n_chat_js["chat.js"] -->|1| n_palette_js["palette.js"]
  n_chat_js["chat.js"] -->|2| n_settings_js["settings.js"]
  n_core_js["core.js"] -->|10| n_chat_js["chat.js"]
  n_core_js["core.js"] -->|2| n_folders_js["folders.js"]
  n_core_js["core.js"] -->|2| n_i18n_js["i18n.js"]
  n_core_js["core.js"] -->|3| n_palette_js["palette.js"]
  n_core_js["core.js"] -->|1| n_settings_js["settings.js"]
  n_folders_js["folders.js"] -->|20| n_core_js["core.js"]
  n_folders_js["folders.js"] -->|2| n_i18n_js["i18n.js"]
  n_folders_js["folders.js"] -->|1| n_palette_js["palette.js"]
  n_palette_js["palette.js"] -->|4| n_core_js["core.js"]
  n_palette_js["palette.js"] -->|1| n_folders_js["folders.js"]
  n_palette_js["palette.js"] -->|1| n_i18n_js["i18n.js"]
  n_settings_js["settings.js"] -->|1| n_assets_js["assets.js"]
  n_settings_js["settings.js"] -->|1| n_chat_js["chat.js"]
  n_settings_js["settings.js"] -->|12| n_core_js["core.js"]
  n_settings_js["settings.js"] -->|3| n_folders_js["folders.js"]
  n_settings_js["settings.js"] -->|1| n_i18n_js["i18n.js"]
  n_settings_js["settings.js"] -->|1| n_palette_js["palette.js"]
  n_viewer_js["viewer.js"] -->|1| n_assets_js["assets.js"]
  n_viewer_js["viewer.js"] -->|3| n_core_js["core.js"]
  n_viewer_js["viewer.js"] -->|1| n_i18n_js["i18n.js"]
```

## Betikler

| betik | satır | üst düzey tanım | çağırdığı sunucu yolları |
| --- | --- | --- | --- |
| `static/assets.js` | 586 | 25 | `/api/assets/{}`, `/api/assets/{}/{}`, `/api/banner`, `/api/banner/preview`, `/api/logo`, `/api/logo/preview`, `/assets/banners/{}`, `/assets/logos/{}`, `/assets/mottos/{}`, `/assets/{}/{}`, `/output/{}` |
| `static/chat.js` | 2771 | 90 | `/api/arena/{}`, `/api/arena/{}/winner`, `/api/chat`, `/api/chats`, `/api/chats/{}`, `/api/prefs`, `/output/{}.${videoMu ` |
| `static/core.js` | 3137 | 88 | `/api/edit`, `/api/generate`, `/api/image/{}`, `/api/output/{}/download`, `/api/prefs`, `/api/video`, `/api/video/animate`, `/output/`, `/output/{}`, `/output/{}.png` |
| `static/folders.js` | 2172 | 60 | `/api/folders`, `/api/folders/{}`, `/api/folders/{}/download`, `/api/history`, `/api/images`, `/api/import`, `/output/{}`, `/output/{}${videoMu ` |
| `static/i18n.js` | 84 | 2 | — |
| `static/mobile.js` | 55 | 0 | — |
| `static/palette.js` | 844 | 37 | `/api/palette/suggest`, `/api/palettes`, `/api/palettes/{}` |
| `static/pixel-canvas.js` | 347 | 0 | — |
| `static/settings.js` | 874 | 22 | `/api/guncelleme`, `/api/prefs`, `/api/settings` |
| `static/viewer.js` | 540 | 0 | `/output/` |

