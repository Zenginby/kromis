<!-- ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: tools/graf_uret.py · yenilemek için: python3 tools/graf_uret.py -->

# Uç nokta grafı

45 HTTP rotası, 7 dosyada (`routers/` altındaki alan router'ları; bileşim kökü `app.py` yalnız takıyor). `modüller` sütunu, rotanın gövdesinin VE yardımcılarının (`services/`, aynı router'daki özel işlevler) dokunduğu KÜTÜPHANE modülleridir — yani bir modülü değiştirirken hangi isteklerin sınanması gerektiği burada yazılı; `routers.*`/`services.*` bilerek sütunda yok (gerekçe: tools/graf_uret.py, uc_noktalar). `ön yüz` sütunu o yolu çağıran tarayıcı betiği.

`paths` neredeyse her satırda görünüyor ve bu doğru: çıktı/varlık dizinleri `services/yollar.py` üzerinden `paths`ten akıyor ve rotalar o değeri depo modüllerine geçiriyor — yani `paths.py`'ye dokunmak gerçekten neredeyse her ucu etkiler.

| yöntem | yol | dosya | işlev | modüller | ön yüz |
| --- | --- | --- | --- | --- | --- |
| GET | `/` | `routers/kok.py` | `index`:28 | `errlog`, `i18n`, `paths`, `version` | — |
| GET | `/api/arena/{arena_id}` | `routers/galeri.py` | `arena_round_route`:164 | `paths`, `storage` | `chat.js` |
| POST | `/api/arena/{arena_id}/winner` | `routers/galeri.py` | `set_arena_winner_route`:179 | `i18n`, `models`, `paths`, `storage` | `chat.js` |
| GET | `/api/assets/{kind}` | `routers/bindirme.py` | `list_assets_route`:197 | `assets_store`, `i18n`, `paths` | `assets.js` |
| POST | `/api/assets/{kind}` | `routers/bindirme.py` | `upload_asset`:174 | `assets_store`, `i18n`, `paths` | `assets.js` |
| DELETE | `/api/assets/{kind}/{asset_id}` | `routers/bindirme.py` | `delete_asset_route`:210 | `assets_store`, `i18n`, `paths` | `assets.js` |
| POST | `/api/banner` | `routers/bindirme.py` | `add_banner`:149 | `assets_store`, `i18n`, `models`, `paths`, `storage` | `assets.js` |
| POST | `/api/banner/preview` | `routers/bindirme.py` | `preview_banner`:141 | `assets_store`, `i18n`, `models`, `paths` | `assets.js` |
| POST | `/api/chat` | `routers/sohbet.py` | `chat`:25 | `catalog`, `chat_client`, `chat_prompt`, `chat_providers`, `credstore`, `etiket`, `i18n`, `models`, `paths`, `prefs` | `chat.js` |
| DELETE | `/api/chats` | `routers/sohbet.py` | `delete_all_chats_route`:187 | `chat_store`, `paths` | `chat.js` |
| GET | `/api/chats` | `routers/sohbet.py` | `list_chats_route`:149 | `chat_store`, `paths` | `chat.js` |
| POST | `/api/chats` | `routers/sohbet.py` | `create_chat_route`:163 | `chat_store`, `i18n`, `models`, `paths`, `prefs` | `chat.js` |
| DELETE | `/api/chats/{chat_id}` | `routers/sohbet.py` | `delete_chat_route`:219 | `chat_store`, `i18n`, `paths` | `chat.js` |
| GET | `/api/chats/{chat_id}` | `routers/sohbet.py` | `get_chat_route`:155 | `chat_store`, `i18n`, `paths` | `chat.js` |
| PUT | `/api/chats/{chat_id}` | `routers/sohbet.py` | `update_chat_route`:197 | `chat_store`, `i18n`, `models`, `paths`, `prefs` | `chat.js` |
| POST | `/api/edit` | `routers/uretim.py` | `edit`:359 | `azure_client`, `catalog`, `chat_store`, `color_names`, `etiket`, `folders`, `i18n`, `models`, `palette`, `palette_store`, `paths`, `providers`, `storage` | `core.js` |
| GET | `/api/folders` | `routers/galeri.py` | `list_folders_route`:31 | `folders`, `paths`, `storage` | `folders.js` |
| POST | `/api/folders` | `routers/galeri.py` | `create_folder_route`:56 | `folders`, `i18n`, `models`, `paths` | `folders.js` |
| DELETE | `/api/folders/{folder_id}` | `routers/galeri.py` | `delete_folder_route`:72 | `folders`, `i18n`, `paths`, `storage` | `folders.js` |
| PATCH | `/api/folders/{folder_id}` | `routers/galeri.py` | `rename_folder_route`:129 | `folders`, `i18n`, `models`, `paths` | `folders.js` |
| GET | `/api/folders/{folder_id}/download` | `routers/galeri.py` | `download_folder_route`:86 | `folders`, `i18n`, `paths` | `folders.js` |
| POST | `/api/generate` | `routers/uretim.py` | `generate`:32 | `azure_client`, `catalog`, `chat_store`, `color_names`, `folders`, `i18n`, `models`, `palette`, `palette_store`, `paths`, `providers`, `storage` | `core.js` |
| GET | `/api/guncelleme` | `routers/ayarlar.py` | `get_guncelleme`:59 | `guncelleme`, `paths`, `prefs` | `settings.js` |
| POST | `/api/guncelleme` | `routers/ayarlar.py` | `post_guncelleme`:89 | `guncelleme`, `paths`, `prefs` | `settings.js` |
| GET | `/api/history` | `routers/galeri.py` | `history`:142 | `folders`, `i18n`, `paths`, `storage` | `folders.js` |
| DELETE | `/api/image/{image_id}` | `routers/galeri.py` | `delete_image`:195 | `i18n`, `paths`, `storage` | `core.js` |
| PATCH | `/api/image/{image_id}` | `routers/galeri.py` | `move_image`:154 | `folders`, `i18n`, `models`, `paths`, `storage` | `core.js` |
| DELETE | `/api/images` | `routers/galeri.py` | `delete_images`:215 | `i18n`, `models`, `paths`, `storage` | `folders.js` |
| PATCH | `/api/images` | `routers/galeri.py` | `move_images`:204 | `folders`, `i18n`, `models`, `paths`, `storage` | `folders.js` |
| POST | `/api/import` | `routers/galeri.py` | `import_image`:225 | `folders`, `i18n`, `paths`, `storage` | `folders.js` |
| POST | `/api/logo` | `routers/bindirme.py` | `add_logo`:73 | `assets_store`, `composite`, `i18n`, `models`, `paths`, `storage` | `assets.js` |
| POST | `/api/logo/preview` | `routers/bindirme.py` | `preview_logo`:64 | `assets_store`, `composite`, `i18n`, `models`, `paths` | `assets.js` |
| GET | `/api/output/{image_id}/download` | `routers/galeri.py` | `output_download`:290 | `i18n`, `paths`, `storage` | `core.js` |
| POST | `/api/palette/suggest` | `routers/paletler.py` | `suggest_palettes`:27 | `color_names`, `models`, `palette` | `palette.js` |
| GET | `/api/palettes` | `routers/paletler.py` | `list_palettes_route`:58 | `palette_store`, `paths` | `palette.js` |
| POST | `/api/palettes` | `routers/paletler.py` | `create_palette_route`:63 | `color_names`, `i18n`, `models`, `palette`, `palette_store`, `paths` | `palette.js` |
| DELETE | `/api/palettes/{palette_id}` | `routers/paletler.py` | `delete_palette_route`:84 | `i18n`, `palette_store`, `paths` | `palette.js` |
| GET | `/api/prefs` | `routers/ayarlar.py` | `get_prefs_route`:262 | `paths`, `prefs` | `chat.js`, `core.js`, `settings.js` |
| POST | `/api/prefs` | `routers/ayarlar.py` | `post_prefs_route`:268 | `models`, `paths`, `prefs` | `chat.js`, `core.js`, `settings.js` |
| GET | `/api/settings` | `routers/ayarlar.py` | `get_settings`:23 | `azure_client`, `catalog`, `credstore`, `etiket`, `guncelleme`, `i18n`, `paths`, `prefs`, `version` | `settings.js` |
| POST | `/api/settings` | `routers/ayarlar.py` | `post_settings`:117 | `azure_client`, `catalog`, `credstore`, `etiket`, `i18n`, `models`, `version` | `settings.js` |
| POST | `/api/video` | `routers/uretim.py` | `video`:71 | `azure_client`, `catalog`, `chat_store`, `folders`, `i18n`, `models`, `paths`, `providers`, `storage` | `core.js` |
| POST | `/api/video/animate` | `routers/uretim.py` | `animate`:178 | `azure_client`, `catalog`, `chat_store`, `etiket`, `folders`, `i18n`, `models`, `paths`, `providers`, `storage` | `core.js` |
| GET | `/assets/{kind}/{filename}` | `routers/bindirme.py` | `asset_file`:219 | `assets_store`, `i18n`, `paths` | `assets.js` |
| GET | `/output/{filename}` | `routers/galeri.py` | `output_file`:266 | `i18n`, `paths`, `storage` | `assets.js`, `chat.js`, `core.js`, `folders.js`, `viewer.js` |

## Öbek → modül

```mermaid
flowchart LR
  n__["/"]
  n__ --> n_errlog["errlog"]
  n__ --> n_i18n["i18n"]
  n__ --> n_paths["paths"]
  n__ --> n_version["version"]
  n__api_arena["/api/arena"]
  n__api_arena --> n_i18n["i18n"]
  n__api_arena --> n_models["models"]
  n__api_arena --> n_paths["paths"]
  n__api_arena --> n_storage["storage"]
  n__api_assets["/api/assets"]
  n__api_assets --> n_assets_store["assets_store"]
  n__api_assets --> n_i18n["i18n"]
  n__api_assets --> n_paths["paths"]
  n__api_banner["/api/banner"]
  n__api_banner --> n_assets_store["assets_store"]
  n__api_banner --> n_i18n["i18n"]
  n__api_banner --> n_models["models"]
  n__api_banner --> n_paths["paths"]
  n__api_banner --> n_storage["storage"]
  n__api_chat["/api/chat"]
  n__api_chat --> n_catalog["catalog"]
  n__api_chat --> n_chat_client["chat_client"]
  n__api_chat --> n_chat_prompt["chat_prompt"]
  n__api_chat --> n_chat_providers["chat_providers"]
  n__api_chat --> n_credstore["credstore"]
  n__api_chat --> n_etiket["etiket"]
  n__api_chat --> n_i18n["i18n"]
  n__api_chat --> n_models["models"]
  n__api_chat --> n_paths["paths"]
  n__api_chat --> n_prefs["prefs"]
  n__api_chats["/api/chats"]
  n__api_chats --> n_chat_store["chat_store"]
  n__api_chats --> n_i18n["i18n"]
  n__api_chats --> n_models["models"]
  n__api_chats --> n_paths["paths"]
  n__api_chats --> n_prefs["prefs"]
  n__api_edit["/api/edit"]
  n__api_edit --> n_azure_client["azure_client"]
  n__api_edit --> n_catalog["catalog"]
  n__api_edit --> n_chat_store["chat_store"]
  n__api_edit --> n_color_names["color_names"]
  n__api_edit --> n_etiket["etiket"]
  n__api_edit --> n_folders["folders"]
  n__api_edit --> n_i18n["i18n"]
  n__api_edit --> n_models["models"]
  n__api_edit --> n_palette["palette"]
  n__api_edit --> n_palette_store["palette_store"]
  n__api_edit --> n_paths["paths"]
  n__api_edit --> n_providers["providers"]
  n__api_edit --> n_storage["storage"]
  n__api_folders["/api/folders"]
  n__api_folders --> n_folders["folders"]
  n__api_folders --> n_i18n["i18n"]
  n__api_folders --> n_models["models"]
  n__api_folders --> n_paths["paths"]
  n__api_folders --> n_storage["storage"]
  n__api_generate["/api/generate"]
  n__api_generate --> n_azure_client["azure_client"]
  n__api_generate --> n_catalog["catalog"]
  n__api_generate --> n_chat_store["chat_store"]
  n__api_generate --> n_color_names["color_names"]
  n__api_generate --> n_folders["folders"]
  n__api_generate --> n_i18n["i18n"]
  n__api_generate --> n_models["models"]
  n__api_generate --> n_palette["palette"]
  n__api_generate --> n_palette_store["palette_store"]
  n__api_generate --> n_paths["paths"]
  n__api_generate --> n_providers["providers"]
  n__api_generate --> n_storage["storage"]
  n__api_guncelleme["/api/guncelleme"]
  n__api_guncelleme --> n_guncelleme["guncelleme"]
  n__api_guncelleme --> n_paths["paths"]
  n__api_guncelleme --> n_prefs["prefs"]
  n__api_history["/api/history"]
  n__api_history --> n_folders["folders"]
  n__api_history --> n_i18n["i18n"]
  n__api_history --> n_paths["paths"]
  n__api_history --> n_storage["storage"]
  n__api_image["/api/image"]
  n__api_image --> n_folders["folders"]
  n__api_image --> n_i18n["i18n"]
  n__api_image --> n_models["models"]
  n__api_image --> n_paths["paths"]
  n__api_image --> n_storage["storage"]
  n__api_images["/api/images"]
  n__api_images --> n_folders["folders"]
  n__api_images --> n_i18n["i18n"]
  n__api_images --> n_models["models"]
  n__api_images --> n_paths["paths"]
  n__api_images --> n_storage["storage"]
  n__api_import["/api/import"]
  n__api_import --> n_folders["folders"]
  n__api_import --> n_i18n["i18n"]
  n__api_import --> n_paths["paths"]
  n__api_import --> n_storage["storage"]
  n__api_logo["/api/logo"]
  n__api_logo --> n_assets_store["assets_store"]
  n__api_logo --> n_composite["composite"]
  n__api_logo --> n_i18n["i18n"]
  n__api_logo --> n_models["models"]
  n__api_logo --> n_paths["paths"]
  n__api_logo --> n_storage["storage"]
  n__api_output["/api/output"]
  n__api_output --> n_i18n["i18n"]
  n__api_output --> n_paths["paths"]
  n__api_output --> n_storage["storage"]
  n__api_palette["/api/palette"]
  n__api_palette --> n_color_names["color_names"]
  n__api_palette --> n_models["models"]
  n__api_palette --> n_palette["palette"]
  n__api_palettes["/api/palettes"]
  n__api_palettes --> n_color_names["color_names"]
  n__api_palettes --> n_i18n["i18n"]
  n__api_palettes --> n_models["models"]
  n__api_palettes --> n_palette["palette"]
  n__api_palettes --> n_palette_store["palette_store"]
  n__api_palettes --> n_paths["paths"]
  n__api_prefs["/api/prefs"]
  n__api_prefs --> n_models["models"]
  n__api_prefs --> n_paths["paths"]
  n__api_prefs --> n_prefs["prefs"]
  n__api_settings["/api/settings"]
  n__api_settings --> n_azure_client["azure_client"]
  n__api_settings --> n_catalog["catalog"]
  n__api_settings --> n_credstore["credstore"]
  n__api_settings --> n_etiket["etiket"]
  n__api_settings --> n_guncelleme["guncelleme"]
  n__api_settings --> n_i18n["i18n"]
  n__api_settings --> n_models["models"]
  n__api_settings --> n_paths["paths"]
  n__api_settings --> n_prefs["prefs"]
  n__api_settings --> n_version["version"]
  n__api_video["/api/video"]
  n__api_video --> n_azure_client["azure_client"]
  n__api_video --> n_catalog["catalog"]
  n__api_video --> n_chat_store["chat_store"]
  n__api_video --> n_etiket["etiket"]
  n__api_video --> n_folders["folders"]
  n__api_video --> n_i18n["i18n"]
  n__api_video --> n_models["models"]
  n__api_video --> n_paths["paths"]
  n__api_video --> n_providers["providers"]
  n__api_video --> n_storage["storage"]
  n__assets["/assets"]
  n__assets --> n_assets_store["assets_store"]
  n__assets --> n_i18n["i18n"]
  n__assets --> n_paths["paths"]
  n__output["/output"]
  n__output --> n_i18n["i18n"]
  n__output --> n_paths["paths"]
  n__output --> n_storage["storage"]
```

## Tarayıcıdan çağrılmayan rotalar

Bu rotaları `static/` altındaki hiçbir betik çağırmıyor. Sebebi meşru olabilir (masaüstü/Android kabuğu, tarayıcının doğrudan açtığı adres, indirme bağlantısı) — ama ölü bir rota da böyle görünür.

* `GET /` → `index`

