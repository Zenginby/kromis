<!-- ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: tools/graf_uret.py · yenilemek için: python3 tools/graf_uret.py -->

# Test haritası

`tests/` altında 134 dosya. Bir modülü değiştirirken koşturulacak testler burada; sütun, test dosyasının o modülü İTHAL ETMESİNDEN çıkarıldı (kapsam ölçümü değil — hangi testin o modüle dokunduğunun haritası).

| modül | testler |
| --- | --- |
| `android_main` | `test_android_main.py`, `test_mobile.py` |
| `app` | `test_admin.py`, `test_app.py`, `test_app_bolme.py`, `test_arena.py`, `test_arena_onyuz.py`, `test_assets_route.py`, `test_backup.py`, `test_banner.py`, `test_chat_prompt.py`, `test_chat_route.py`, `test_chats_route.py`, `test_db.py`, `test_delete_route.py`, `test_dil.py`, `test_dosya.py`, `test_dosya_rotalari.py`, `test_edit_route.py`, `test_folders.py`, `test_fonts.py`, `test_galeri_db.py`, `test_guncelleme_route.py`, `test_gunluk.py`, `test_guvenlik_baslik.py`, `test_health.py`, `test_hesap.py`, `test_i18n.py`, `test_id_contract.py`, `test_import_route.py`, `test_index.py`, `test_isler_route.py`, `test_kimlik.py`, `test_koken.py`, `test_kota.py`, `test_legacy_formats.py`, `test_logo.py`, `test_mobile.py`, `test_model_secimi.py`, `test_palette_route.py`, `test_paths.py`, `test_platform_anahtari.py`, `test_playwright_dil.py`, `test_playwright_guncelleme.py`, `test_playwright_hesap.py`, `test_playwright_studio.py`, `test_posta.py`, `test_prefs_route.py`, `test_provider_logos.py`, `test_rls.py`, `test_search_predicate.py`, `test_sentry.py`, `test_settings_route.py`, `test_shimmer.py`, `test_sifre.py`, `test_video_onyuz.py`, `test_video_route.py` |
| `assets_store` | `test_assets.py`, `test_backup.py`, `test_galeri_db.py`, `test_ice_aktar.py`, `test_legacy_formats.py`, `test_tablolar.py`, `test_varlik_db.py` |
| `azure_client` | `test_app.py`, `test_app_bolme.py`, `test_arena.py`, `test_azure_client.py`, `test_azure_client_edit.py`, `test_azure_client_http.py`, `test_azure_flux_client.py`, `test_azure_mai_client.py`, `test_banner.py`, `test_catalog.py`, `test_chat_client.py`, `test_credstore.py`, `test_delete_route.py`, `test_dosya_rotalari.py`, `test_edit_route.py`, `test_fal_client.py`, `test_folders.py`, `test_galeri_db.py`, `test_gemini_client.py`, `test_gunluk.py`, `test_i18n.py`, `test_ice_aktar.py`, `test_import_route.py`, `test_isci.py`, `test_isler_route.py`, `test_legacy_formats.py`, `test_logo.py`, `test_model_secimi.py`, `test_openai_client.py`, `test_palette_route.py`, `test_paths.py`, `test_playwright_isler.py`, `test_providers.py`, `test_settings.py`, `test_settings_route.py`, `test_veo_client.py`, `test_video_route.py` |
| `azure_flux_client` | `test_azure_flux_client.py` |
| `azure_mai_client` | `test_azure_mai_client.py` |
| `backup` | `test_backup.py` |
| `catalog` | `test_admin.py`, `test_arena.py`, `test_arena_onyuz.py`, `test_azure_flux_client.py`, `test_azure_mai_client.py`, `test_catalog.py`, `test_chat_prompt.py`, `test_chat_providers.py`, `test_chat_route.py`, `test_credstore.py`, `test_docker_kapisi.py`, `test_errlog.py`, `test_fal_client.py`, `test_gemini_client.py`, `test_gunluk.py`, `test_i18n.py`, `test_index.py`, `test_isci.py`, `test_isler_route.py`, `test_kimlik_bilgisi_db.py`, `test_kota.py`, `test_logo.py`, `test_model_secimi.py`, `test_openai_chat.py`, `test_openai_client.py`, `test_platform_anahtari.py`, `test_playwright_dil.py`, `test_playwright_studio.py`, `test_prefs.py`, `test_prefs_route.py`, `test_provider_logos.py`, `test_providers.py`, `test_settings_route.py`, `test_storage.py`, `test_tercih_db.py`, `test_veo_client.py`, `test_video_onyuz.py`, `test_video_route.py` |
| `chat_client` | `test_chat_client.py`, `test_chat_providers.py`, `test_galeri_db.py`, `test_openai_chat.py` |
| `chat_prompt` | `test_chat_prompt.py` |
| `chat_providers` | `test_chat_providers.py`, `test_provider_logos.py` |
| `chat_store` | `test_chat_store.py`, `test_galeri_db.py`, `test_ice_aktar.py`, `test_sohbet_db.py`, `test_tablolar.py` |
| `color_names` | `test_color_names.py`, `test_legacy_formats.py`, `test_palette_route.py` |
| `composite` | `test_composite.py` |
| `credstore` | `test_credstore.py`, `test_kimlik_bilgisi_db.py`, `test_playwright_dil.py`, `test_playwright_studio.py`, `test_prefs.py`, `test_settings_route.py` |
| `desktop` | `test_desktop.py`, `test_windows_acilis.py` |
| `errlog` | `test_errlog.py`, `test_platform_anahtari.py` |
| `etiket` | `test_catalog.py` |
| `fal_client` | `test_fal_client.py`, `test_providers.py` |
| `folders` | `test_folders.py`, `test_galeri_db.py`, `test_guvenlik_baslik.py`, `test_legacy_formats.py`, `test_tablolar.py` |
| `gemini_client` | `test_gemini_client.py` |
| `guncelleme` | `test_depo_adresi.py`, `test_guncelleme.py`, `test_guncelleme_route.py`, `test_lisans.py`, `test_playwright_guncelleme.py`, `test_settings_route.py` |
| `i18n` | `test_admin.py`, `test_catalog.py`, `test_dil.py`, `test_hesap.py`, `test_i18n.py`, `test_isci.py`, `test_isler_route.py`, `test_kimlik.py`, `test_kota.py`, `test_playwright_admin.py`, `test_playwright_dil.py`, `test_playwright_hesap.py`, `test_posta.py`, `test_tercih_db.py` |
| `isci` | — |
| `jsonstore` | `test_jsonstore.py` |
| `kimlik_baglami` | `test_chat_providers.py`, `test_credstore.py`, `test_isci.py` |
| `models` | `test_catalog.py`, `test_chat_client.py`, `test_chat_prompt.py`, `test_chat_route.py`, `test_chats_route.py`, `test_composite.py`, `test_guvenlik_baslik.py`, `test_hesap.py`, `test_i18n.py`, `test_ice_aktar.py`, `test_index.py`, `test_model_secimi.py`, `test_prefs.py`, `test_prefs_route.py`, `test_settings_route.py`, `test_tablolar.py`, `test_tercih_db.py`, `test_video_onyuz.py` |
| `netguard` | `test_netguard.py` |
| `openai_chat` | `test_chat_providers.py`, `test_chat_route.py`, `test_openai_chat.py` |
| `openai_client` | `test_openai_client.py` |
| `palette` | `test_color_names.py`, `test_palette.py`, `test_palette_route.py` |
| `palette_store` | `test_galeri_db.py`, `test_legacy_formats.py`, `test_palet_db.py`, `test_palette_store.py`, `test_tablolar.py` |
| `paths` | `test_android_main.py`, `test_chat_prompt.py`, `test_galeri_db.py`, `test_i18n.py`, `test_paths.py` |
| `prefs` | `test_dil.py`, `test_galeri_db.py`, `test_i18n.py`, `test_ice_aktar.py`, `test_index.py`, `test_kimlik.py`, `test_prefs.py`, `test_prefs_route.py`, `test_tercih_db.py`, `test_video_onyuz.py` |
| `providers` | `test_azure_flux_client.py`, `test_azure_mai_client.py`, `test_catalog.py`, `test_gemini_client.py`, `test_gunluk.py`, `test_isci.py`, `test_isler_route.py`, `test_kota.py`, `test_playwright_isler.py`, `test_provider_logos.py`, `test_providers.py`, `test_rls.py`, `test_veo_client.py` |
| `release_manifest` | `test_android_apk_name.py`, `test_paketleme_dondurma.py`, `test_release_manifest.py` |
| `routers.admin` | — |
| `routers.ayarlar` | — |
| `routers.bindirme` | — |
| `routers.galeri` | — |
| `routers.hesap` | `test_posta.py` |
| `routers.isler` | `test_isler_route.py`, `test_rls.py` |
| `routers.kok` | — |
| `routers.paletler` | — |
| `routers.saglik` | `test_gunluk.py`, `test_health.py`, `test_sentry.py` |
| `routers.sohbet` | — |
| `routers.uretim` | — |
| `screencolor` | `test_screencolor.py` |
| `services.ayar` | `test_app_bolme.py`, `test_artik_dosya.py`, `test_gunluk.py`, `test_hesap.py`, `test_isci.py`, `test_isler_route.py`, `test_kimlik.py`, `test_kuyruk.py`, `test_paths.py`, `test_rls.py` |
| `services.cerez` | `test_admin.py`, `test_docker_kapisi.py`, `test_hesap.py`, `test_kimlik.py`, `test_playwright_hesap.py`, `test_rls.py` |
| `services.db` | `test_admin.py`, `test_anahtar_dondur.py`, `test_artik_dosya.py`, `test_db.py`, `test_dil.py`, `test_docker_kapisi.py`, `test_goc.py`, `test_guncelleme_route.py`, `test_health.py`, `test_ice_aktar.py`, `test_isci.py`, `test_kullanici_cli.py`, `test_playwright_studio.py`, `test_rls.py` |
| `services.depo_admin` | `test_admin.py`, `test_health.py` |
| `services.depo_kimlik_bilgisi` | `test_anahtar_dondur.py`, `test_ice_aktar.py`, `test_isci.py`, `test_kimlik_bilgisi_db.py`, `test_platform_anahtari.py`, `test_settings_route.py`, `test_sifre.py` |
| `services.depo_klasor` | `test_folders.py`, `test_galeri_db.py`, `test_guvenlik_baslik.py`, `test_legacy_formats.py`, `test_playwright_studio.py` |
| `services.depo_medya` | `test_artik_dosya.py`, `test_chats_route.py`, `test_dosya_rotalari.py`, `test_galeri_db.py`, `test_ice_aktar.py`, `test_isci.py`, `test_kimlik.py`, `test_legacy_formats.py`, `test_playwright_studio.py` |
| `services.depo_palet` | `test_legacy_formats.py`, `test_palet_db.py` |
| `services.depo_sohbet` | `test_chats_route.py`, `test_sohbet_db.py` |
| `services.depo_tercih` | `test_dil.py`, `test_ice_aktar.py`, `test_prefs_route.py`, `test_tercih_db.py` |
| `services.depo_varlik` | `test_artik_dosya.py`, `test_banner.py`, `test_folders.py`, `test_legacy_formats.py`, `test_logo.py`, `test_palette_route.py`, `test_playwright_studio.py`, `test_varlik_db.py` |
| `services.dil` | `test_dil.py`, `test_gunluk.py`, `test_i18n.py`, `test_isci.py`, `test_koken.py` |
| `services.dosya` | `test_artik_dosya.py`, `test_docker_kapisi.py`, `test_dosya.py`, `test_dosya_rotalari.py`, `test_gunluk.py`, `test_isci.py`, `test_medya_tasi.py`, `test_rls.py` |
| `services.gorsel` | `test_edit_route.py`, `test_model_secimi.py`, `test_video_route.py` |
| `services.gunluk` | `test_admin.py`, `test_docker_kapisi.py`, `test_gunluk.py` |
| `services.hata_izleme` | `test_docker_kapisi.py`, `test_sentry.py` |
| `services.hesap` | `test_admin.py`, `test_anahtar_dondur.py`, `test_artik_dosya.py`, `test_dosya_rotalari.py`, `test_galeri_db.py`, `test_hesap.py`, `test_ice_aktar.py`, `test_isci.py`, `test_isler_route.py`, `test_kimlik.py`, `test_kimlik_bilgisi_db.py`, `test_kullanici_cli.py`, `test_kuyruk.py`, `test_palet_db.py`, `test_playwright_hesap.py`, `test_rls.py`, `test_sohbet_db.py`, `test_tercih_db.py`, `test_varlik_db.py` |
| `services.isci` | `test_docker_kapisi.py`, `test_gunluk.py`, `test_isci.py`, `test_isler_route.py`, `test_kimlik.py`, `test_playwright_studio.py`, `test_rls.py` |
| `services.istek_kimligi` | `test_gunluk.py`, `test_koken.py`, `test_sentry.py` |
| `services.kapilar` | `test_docker_kapisi.py`, `test_isler_route.py`, `test_kota.py`, `test_platform_anahtari.py` |
| `services.kimlik` | `test_isler_route.py`, `test_kimlik.py`, `test_rls.py` |
| `services.kiraci` | `test_admin.py`, `test_rls.py`, `test_rls_kontrol.py` |
| `services.koken` | `test_docker_kapisi.py`, `test_gunluk.py`, `test_hesap.py`, `test_koken.py`, `test_playwright_hesap.py` |
| `services.kota` | `test_admin.py`, `test_docker_kapisi.py`, `test_kota.py` |
| `services.kuyruk` | `test_admin.py`, `test_artik_dosya.py`, `test_gunluk.py`, `test_health.py`, `test_isci.py`, `test_isler_route.py`, `test_kota.py`, `test_kuyruk.py`, `test_playwright_admin.py`, `test_rls.py` |
| `services.modeller` | — |
| `services.nesne_depo` | `test_artik_dosya.py`, `test_dosya.py`, `test_dosya_rotalari.py`, `test_medya_tasi.py`, `test_nesne_depo.py` |
| `services.palet` | `test_palet_db.py` |
| `services.platform_anahtari` | `test_admin.py`, `test_docker_kapisi.py`, `test_gunluk.py`, `test_kota.py`, `test_platform_anahtari.py` |
| `services.posta` | `test_docker_kapisi.py`, `test_hesap.py`, `test_playwright_hesap.py`, `test_posta.py` |
| `services.redaksiyon` | — |
| `services.sablon` | — |
| `services.sifre` | `test_anahtar_dondur.py`, `test_docker_kapisi.py`, `test_ice_aktar.py`, `test_kimlik_bilgisi_db.py`, `test_sifre.py` |
| `services.tablolar` | `test_admin.py`, `test_anahtar_dondur.py`, `test_artik_dosya.py`, `test_dosya_rotalari.py`, `test_folders.py`, `test_galeri_db.py`, `test_hesap.py`, `test_ice_aktar.py`, `test_isci.py`, `test_isler_route.py`, `test_kimlik.py`, `test_kimlik_bilgisi_db.py`, `test_kota.py`, `test_kullanici_cli.py`, `test_kuyruk.py`, `test_legacy_formats.py`, `test_palet_db.py`, `test_palette_route.py`, `test_platform_anahtari.py`, `test_playwright_admin.py`, `test_playwright_hesap.py`, `test_playwright_isler.py`, `test_rls.py`, `test_sohbet_db.py`, `test_tablolar.py`, `test_tercih_db.py`, `test_varlik_db.py` |
| `services.zaman` | `test_admin.py`, `test_galeri_db.py`, `test_gunluk.py`, `test_health.py`, `test_ice_aktar.py`, `test_isci.py`, `test_kimlik_bilgisi_db.py`, `test_kota.py`, `test_kuyruk.py`, `test_legacy_formats.py`, `test_palet_db.py`, `test_sohbet_db.py`, `test_varlik_db.py` |
| `storage` | `test_arena.py`, `test_folders.py`, `test_galeri_db.py`, `test_ice_aktar.py`, `test_legacy_formats.py`, `test_storage.py`, `test_storage_delete.py`, `test_tablolar.py`, `test_video_onyuz.py` |
| `tools.anahtar_dondur` | `test_anahtar_dondur.py` |
| `tools.artik_dosya` | `test_artik_dosya.py` |
| `tools.gecici_postgres` | `test_test_ortami.py` |
| `tools.goc` | `test_goc.py` |
| `tools.graf_uret` | `test_app_bolme.py`, `test_graflar.py`, `test_onyuz_lint_kapisi.py` |
| `tools.ice_aktar` | `test_ice_aktar.py` |
| `tools.kullanici` | `test_kullanici_cli.py` |
| `tools.make_legacy_fixtures` | — |
| `tools.make_logo_goldens` | — |
| `tools.medya_tasi` | `test_medya_tasi.py` |
| `tools.render_brand_assets` | — |
| `tools.rls_kontrol` | `test_rls_kontrol.py` |
| `tools.surum_karari` | `test_surum_karari.py` |
| `tools.surum_yaz` | `test_release_manifest.py`, `test_surum_yaz.py` |
| `tools.test_ortami` | `test_test_ortami.py` |
| `tools.uygulama_rolu` | `test_rls_kontrol.py` |
| `veo_client` | `test_veo_client.py` |
| `version` | `test_admin.py`, `test_db.py`, `test_guncelleme.py`, `test_guncelleme_route.py`, `test_health.py`, `test_hesap.py`, `test_index.py`, `test_playwright_guncelleme.py`, `test_provider_logos.py`, `test_release_manifest.py`, `test_sentry.py`, `test_settings_route.py`, `test_version.py` |
| `winclr` | `test_winclr.py` |
| `winsec` | `test_settings.py`, `test_winsec.py` |

## Hiç ithal edilmeyen modüller

Bu modülleri hiçbir test dosyası ithal etmiyor. Dolaylı olarak sınanıyor olabilirler (`import app` app'in ithal ettiği her şeyi çalıştırır), ama doğrudan bekçileri yok.

* `isci` (382 satır)
* `routers.admin` (136 satır)
* `routers.ayarlar` (401 satır)
* `routers.bindirme` (282 satır)
* `routers.galeri` (397 satır)
* `routers.kok` (40 satır)
* `routers.paletler` (101 satır)
* `routers.sohbet` (240 satır)
* `routers.uretim` (522 satır)
* `services.modeller` (317 satır)
* `services.redaksiyon` (68 satır)
* `services.sablon` (68 satır)
* `tools.make_legacy_fixtures` (211 satır)
* `tools.make_logo_goldens` (110 satır)
* `tools.render_brand_assets` (115 satır)

## Hiçbir modülü ithal etmeyen testler

Yukarıdaki tablonun kör noktası: sütun ithal ilişkisinden çıktığı için ithali olmayan bir test hiçbir satırda görünmez. Bu dosyalar modül değil ARTEFAKT sınıyor (workflow YAML'ı, kodlama sözleşmesi, paketleme adı, Android geri tuşu) — yani bir `.yml`e ya da bir sözleşmeye dokunuyorsan koşturulacak testler burada.

* `tests/test_android_geri.py`
* `tests/test_bagimlilik_pinleri.py`
* `tests/test_brand_assets.py`
* `tests/test_ci_sizinti.py`
* `tests/test_ci_varlik_saklama.py`
* `tests/test_dal_korumasi.py`
* `tests/test_dal_nobetcisi.py`
* `tests/test_encoding_contract.py`
* `tests/test_mypy_kapisi.py`
* `tests/test_paket_icerik_listesi.py`
* `tests/test_playwright_kurulumu.py`
* `tests/test_python_surumu.py`
* `tests/test_syntax_warnings.py`
* `tests/test_telif_basligi.py`

