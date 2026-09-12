<!-- ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: tools/graf_uret.py · yenilemek için: python3 tools/graf_uret.py -->

# Uç nokta grafı

`app.py` içinde 45 HTTP rotası. `modüller` sütunu, rotanın gövdesinin VE app.py içi yardımcılarının dokunduğu depo modülleridir — yani bir modülü değiştirirken hangi isteklerin sınanması gerektiği burada yazılı. `ön yüz` sütunu o yolu çağıran tarayıcı betiği.

`paths` neredeyse her satırda görünüyor ve bu doğru: çıktı/varlık dizinleri app.py'nin modül düzeyi sabitlerinden akıyor (`OUTPUT_DIR = paths.output_dir()`) ve rotalar o sabiti depo modüllerine geçiriyor — yani `paths.py`'ye dokunmak gerçekten neredeyse her ucu etkiler.

| yöntem | yol | işlev (app.py) | modüller | ön yüz |
| --- | --- | --- | --- | --- |
| GET | `/` | `index`:2200 | `errlog`, `i18n`, `paths`, `version` | — |
| GET | `/api/arena/{arena_id}` | `arena_round_route`:1762 | `paths`, `storage` | `chat.js` |
| POST | `/api/arena/{arena_id}/winner` | `set_arena_winner_route`:1777 | `i18n`, `models`, `paths`, `storage` | `chat.js` |
| GET | `/api/assets/{kind}` | `list_assets_route`:2104 | `assets_store`, `i18n`, `paths` | `assets.js` |
| POST | `/api/assets/{kind}` | `upload_asset`:2082 | `assets_store`, `i18n`, `paths` | `assets.js` |
| DELETE | `/api/assets/{kind}/{asset_id}` | `delete_asset_route`:2116 | `assets_store`, `i18n`, `paths` | `assets.js` |
| POST | `/api/banner` | `add_banner`:2051 | `assets_store`, `i18n`, `models`, `paths`, `storage` | `assets.js` |
| POST | `/api/banner/preview` | `preview_banner`:2043 | `assets_store`, `i18n`, `models`, `paths` | `assets.js` |
| POST | `/api/chat` | `chat`:1402 | `catalog`, `chat_client`, `chat_prompt`, `chat_providers`, `credstore`, `etiket`, `i18n`, `models`, `paths`, `prefs` | `chat.js` |
| DELETE | `/api/chats` | `delete_all_chats_route`:1590 | `chat_store`, `paths` | `chat.js` |
| GET | `/api/chats` | `list_chats_route`:1552 | `chat_store`, `paths` | `chat.js` |
| POST | `/api/chats` | `create_chat_route`:1566 | `chat_store`, `i18n`, `models`, `paths`, `prefs` | `chat.js` |
| DELETE | `/api/chats/{chat_id}` | `delete_chat_route`:1622 | `chat_store`, `i18n`, `paths` | `chat.js` |
| GET | `/api/chats/{chat_id}` | `get_chat_route`:1558 | `chat_store`, `i18n`, `paths` | `chat.js` |
| PUT | `/api/chats/{chat_id}` | `update_chat_route`:1600 | `chat_store`, `i18n`, `models`, `paths`, `prefs` | `chat.js` |
| POST | `/api/edit` | `edit`:842 | `azure_client`, `catalog`, `chat_store`, `color_names`, `etiket`, `folders`, `i18n`, `models`, `palette`, `palette_store`, `paths`, `providers`, `storage` | `core.js` |
| GET | `/api/folders` | `list_folders_route`:1630 | `folders`, `paths`, `storage` | `folders.js` |
| POST | `/api/folders` | `create_folder_route`:1654 | `folders`, `i18n`, `models`, `paths` | `folders.js` |
| DELETE | `/api/folders/{folder_id}` | `delete_folder_route`:1669 | `folders`, `i18n`, `paths`, `storage` | `folders.js` |
| PATCH | `/api/folders/{folder_id}` | `rename_folder_route`:1726 | `folders`, `i18n`, `models`, `paths` | `folders.js` |
| GET | `/api/folders/{folder_id}/download` | `download_folder_route`:1682 | `folders`, `i18n`, `paths` | `folders.js` |
| POST | `/api/generate` | `generate`:469 | `azure_client`, `catalog`, `chat_store`, `color_names`, `folders`, `i18n`, `models`, `palette`, `palette_store`, `paths`, `providers`, `storage` | `core.js` |
| GET | `/api/guncelleme` | `get_guncelleme`:1131 | `guncelleme`, `paths`, `prefs` | `settings.js` |
| POST | `/api/guncelleme` | `post_guncelleme`:1160 | `guncelleme`, `paths`, `prefs` | `settings.js` |
| GET | `/api/history` | `history`:1740 | `folders`, `i18n`, `paths`, `storage` | `folders.js` |
| DELETE | `/api/image/{image_id}` | `delete_image`:1793 | `i18n`, `paths`, `storage` | `core.js` |
| PATCH | `/api/image/{image_id}` | `move_image`:1752 | `folders`, `i18n`, `models`, `paths`, `storage` | `core.js` |
| DELETE | `/api/images` | `delete_images`:1813 | `i18n`, `models`, `paths`, `storage` | `folders.js` |
| PATCH | `/api/images` | `move_images`:1802 | `folders`, `i18n`, `models`, `paths`, `storage` | `folders.js` |
| POST | `/api/import` | `import_image`:1823 | `folders`, `i18n`, `paths`, `storage` | `folders.js` |
| POST | `/api/logo` | `add_logo`:1976 | `assets_store`, `composite`, `i18n`, `models`, `paths`, `storage` | `assets.js` |
| POST | `/api/logo/preview` | `preview_logo`:1967 | `assets_store`, `composite`, `i18n`, `models`, `paths` | `assets.js` |
| GET | `/api/output/{image_id}/download` | `output_download`:2161 | `i18n`, `paths`, `storage` | `core.js` |
| POST | `/api/palette/suggest` | `suggest_palettes`:1864 | `color_names`, `models`, `palette` | `palette.js` |
| GET | `/api/palettes` | `list_palettes_route`:1895 | `palette_store`, `paths` | `palette.js` |
| POST | `/api/palettes` | `create_palette_route`:1900 | `color_names`, `i18n`, `models`, `palette`, `palette_store`, `paths` | `palette.js` |
| DELETE | `/api/palettes/{palette_id}` | `delete_palette_route`:1921 | `i18n`, `palette_store`, `paths` | `palette.js` |
| GET | `/api/prefs` | `get_prefs_route`:1477 | `paths`, `prefs` | `chat.js`, `core.js`, `settings.js` |
| POST | `/api/prefs` | `post_prefs_route`:1483 | `models`, `paths`, `prefs` | `chat.js`, `core.js`, `settings.js` |
| GET | `/api/settings` | `get_settings`:1096 | `azure_client`, `catalog`, `credstore`, `etiket`, `guncelleme`, `i18n`, `paths`, `prefs`, `version` | `settings.js` |
| POST | `/api/settings` | `post_settings`:1187 | `azure_client`, `catalog`, `credstore`, `etiket`, `i18n`, `models`, `version` | `settings.js` |
| POST | `/api/video` | `video`:508 | `azure_client`, `catalog`, `chat_store`, `folders`, `i18n`, `models`, `paths`, `providers`, `storage` | `core.js` |
| POST | `/api/video/animate` | `animate`:615 | `azure_client`, `catalog`, `chat_store`, `etiket`, `folders`, `i18n`, `models`, `paths`, `providers`, `storage` | `core.js` |
| GET | `/assets/{kind}/{filename}` | `asset_file`:2125 | `assets_store`, `i18n`, `paths` | `assets.js` |
| GET | `/output/{filename}` | `output_file`:2137 | `i18n`, `paths`, `storage` | `assets.js`, `chat.js`, `core.js`, `folders.js`, `viewer.js` |

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

