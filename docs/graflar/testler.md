<!-- ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: tools/graf_uret.py · yenilemek için: python3 tools/graf_uret.py -->

# Test haritası

`tests/` altında 71 dosya. Bir modülü değiştirirken koşturulacak testler burada; sütun, test dosyasının o modülü İTHAL ETMESİNDEN çıkarıldı (kapsam ölçümü değil — hangi testin o modüle dokunduğunun haritası).

| modül | testler |
| --- | --- |
| `android_main` | `test_android_main.py` |
| `app` | `test_app.py`, `test_arena.py`, `test_arena_onyuz.py`, `test_assets_route.py`, `test_backup.py`, `test_banner.py`, `test_chat_route.py`, `test_chats_route.py`, `test_delete_route.py`, `test_edit_route.py`, `test_folders.py`, `test_fonts.py`, `test_guvenlik_baslik.py`, `test_id_contract.py`, `test_import_route.py`, `test_index.py`, `test_legacy_formats.py`, `test_logo.py`, `test_mobile.py`, `test_model_secimi.py`, `test_palette_route.py`, `test_paths.py`, `test_playwright_studio.py`, `test_prefs_route.py`, `test_provider_logos.py`, `test_settings_route.py`, `test_shimmer.py` |
| `assets_store` | `test_assets.py`, `test_assets_route.py`, `test_backup.py`, `test_banner.py`, `test_folders.py`, `test_legacy_formats.py`, `test_logo.py`, `test_palette_route.py`, `test_playwright_studio.py` |
| `azure_client` | `test_app.py`, `test_arena.py`, `test_azure_client.py`, `test_azure_client_edit.py`, `test_azure_client_http.py`, `test_banner.py`, `test_catalog.py`, `test_chat_client.py`, `test_credstore.py`, `test_delete_route.py`, `test_edit_route.py`, `test_folders.py`, `test_gemini_client.py`, `test_guvenlik_baslik.py`, `test_import_route.py`, `test_legacy_formats.py`, `test_logo.py`, `test_model_secimi.py`, `test_openai_client.py`, `test_palette_route.py`, `test_paths.py`, `test_prefs.py`, `test_providers.py`, `test_settings.py`, `test_settings_route.py` |
| `backup` | `test_backup.py` |
| `catalog` | `test_arena.py`, `test_arena_onyuz.py`, `test_catalog.py`, `test_chat_providers.py`, `test_credstore.py`, `test_errlog.py`, `test_gemini_client.py`, `test_index.py`, `test_logo.py`, `test_model_secimi.py`, `test_openai_chat.py`, `test_openai_client.py`, `test_playwright_studio.py`, `test_prefs.py`, `test_prefs_route.py`, `test_provider_logos.py`, `test_providers.py`, `test_settings_route.py`, `test_storage.py` |
| `chat_client` | `test_chat_client.py`, `test_chat_providers.py`, `test_openai_chat.py` |
| `chat_prompt` | `test_chat_prompt.py` |
| `chat_providers` | `test_chat_providers.py`, `test_provider_logos.py` |
| `chat_store` | `test_chat_store.py`, `test_chats_route.py` |
| `color_names` | `test_color_names.py`, `test_legacy_formats.py`, `test_palette_route.py` |
| `composite` | `test_composite.py` |
| `credstore` | `test_credstore.py`, `test_playwright_studio.py`, `test_prefs.py`, `test_settings_route.py` |
| `desktop` | `test_desktop.py` |
| `errlog` | `test_errlog.py` |
| `folders` | `test_folders.py`, `test_guvenlik_baslik.py`, `test_legacy_formats.py` |
| `gemini_client` | `test_gemini_client.py` |
| `guncelleme` | `test_depo_adresi.py`, `test_guncelleme.py` |
| `jsonstore` | `test_jsonstore.py` |
| `models` | `test_catalog.py`, `test_chat_client.py`, `test_chat_route.py`, `test_chats_route.py`, `test_composite.py`, `test_guvenlik_baslik.py`, `test_index.py`, `test_model_secimi.py`, `test_prefs.py`, `test_prefs_route.py`, `test_settings_route.py` |
| `netguard` | `test_netguard.py` |
| `openai_chat` | `test_chat_providers.py`, `test_chat_route.py`, `test_openai_chat.py` |
| `openai_client` | `test_openai_client.py` |
| `palette` | `test_color_names.py`, `test_palette.py`, `test_palette_route.py` |
| `palette_store` | `test_legacy_formats.py`, `test_palette_route.py`, `test_palette_store.py` |
| `paths` | `test_android_main.py`, `test_chat_prompt.py`, `test_paths.py` |
| `prefs` | `test_index.py`, `test_prefs.py`, `test_prefs_route.py` |
| `providers` | `test_gemini_client.py`, `test_provider_logos.py`, `test_providers.py` |
| `release_manifest` | `test_android_apk_name.py`, `test_release_manifest.py` |
| `screencolor` | `test_screencolor.py` |
| `storage` | `test_arena.py`, `test_chats_route.py`, `test_edit_route.py`, `test_folders.py`, `test_legacy_formats.py`, `test_palette_route.py`, `test_storage.py`, `test_storage_delete.py` |
| `tools.graf_uret` | `test_graflar.py` |
| `tools.make_legacy_fixtures` | — |
| `tools.make_logo_goldens` | — |
| `tools.render_brand_assets` | — |
| `tools.surum_karari` | `test_surum_karari.py` |
| `tools.surum_yaz` | `test_release_manifest.py`, `test_surum_yaz.py` |
| `version` | `test_backup.py`, `test_guncelleme.py`, `test_index.py`, `test_provider_logos.py`, `test_release_manifest.py`, `test_settings_route.py`, `test_version.py` |
| `winsec` | `test_settings.py`, `test_winsec.py` |

## Hiç ithal edilmeyen modüller

Bu modülleri hiçbir test dosyası ithal etmiyor. Dolaylı olarak sınanıyor olabilirler (`import app` app'in ithal ettiği her şeyi çalıştırır), ama doğrudan bekçileri yok.

* `tools.make_legacy_fixtures` (207 satır)
* `tools.make_logo_goldens` (107 satır)
* `tools.render_brand_assets` (71 satır)

## Hiçbir modülü ithal etmeyen testler

Yukarıdaki tablonun kör noktası: sütun ithal ilişkisinden çıktığı için ithali olmayan bir test hiçbir satırda görünmez. Bu dosyalar modül değil ARTEFAKT sınıyor (workflow YAML'ı, kodlama sözleşmesi, paketleme adı, Android geri tuşu) — yani bir `.yml`e ya da bir sözleşmeye dokunuyorsan koşturulacak testler burada.

* `tests/test_android_geri.py`
* `tests/test_android_packaging.py`
* `tests/test_ci_paketleme_kapisi.py`
* `tests/test_ci_sizinti.py`
* `tests/test_ci_varlik_saklama.py`
* `tests/test_encoding_contract.py`
* `tests/test_paket_icerik_listesi.py`

