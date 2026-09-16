<!-- ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: tools/graf_uret.py · yenilemek için: python3 tools/graf_uret.py -->

# Modül grafı

62 Python modülü, 234 modül düzeyi + 14 erteli ithal kenarı.

Katman, o modülün depo içindeki en uzun bağımlılık zincirinin uzunluğu:
**katman 0 hiçbir depo modülüne dayanmaz**, en üst katman uygulamanın
giriş noktasıdır. Bir modülü değiştirdiğinizde etkilenebilecek yer,
onun `ithal eden` sütunudur — okuma yönü budur.

## Uygulama

```mermaid
flowchart TD
  subgraph katman12["katman 12"]
    n_android_main["android_main<br/>201 satır"]
  end
  subgraph katman11["katman 11"]
    n_desktop["desktop<br/>584 satır"]
  end
  subgraph katman10["katman 10"]
    n_netguard["netguard<br/>169 satır"]
  end
  subgraph katman9["katman 9"]
    n_app["app<br/>174 satır"]
  end
  subgraph katman8["katman 8"]
    n_routers_bindirme["routers.bindirme<br/>227 satır"]
    n_routers_galeri["routers.galeri<br/>325 satır"]
    n_routers_paletler["routers.paletler<br/>88 satır"]
    n_routers_sohbet["routers.sohbet<br/>223 satır"]
    n_routers_uretim["routers.uretim<br/>416 satır"]
  end
  subgraph katman7["katman 7"]
    n_chat_providers["chat_providers<br/>130 satır"]
    n_routers_ayarlar["routers.ayarlar<br/>283 satır"]
    n_routers_kok["routers.kok<br/>82 satır"]
    n_services_gorsel["services.gorsel<br/>138 satır"]
    n_services_kapilar["services.kapilar<br/>70 satır"]
    n_services_palet["services.palet<br/>177 satır"]
  end
  subgraph katman6["katman 6"]
    n_openai_chat["openai_chat<br/>180 satır"]
    n_services_dil["services.dil<br/>56 satır"]
    n_services_modeller["services.modeller<br/>295 satır"]
  end
  subgraph katman5["katman 5"]
    n_azure_flux_client["azure_flux_client<br/>289 satır"]
    n_azure_mai_client["azure_mai_client<br/>286 satır"]
    n_chat_client["chat_client<br/>191 satır"]
    n_fal_client["fal_client<br/>757 satır"]
    n_gemini_client["gemini_client<br/>295 satır"]
    n_openai_client["openai_client<br/>217 satır"]
    n_prefs["prefs<br/>249 satır"]
    n_providers["providers<br/>501 satır"]
    n_veo_client["veo_client<br/>629 satır"]
  end
  subgraph katman4["katman 4"]
    n_backup["backup<br/>190 satır"]
    n_color_names["color_names<br/>421 satır"]
    n_credstore["credstore<br/>198 satır"]
    n_models["models<br/>1056 satır"]
  end
  subgraph katman3["katman 3"]
    n_assets_store["assets_store<br/>205 satır"]
    n_azure_client["azure_client<br/>458 satır"]
    n_composite["composite<br/>165 satır"]
    n_etiket["etiket<br/>118 satır"]
    n_folders["folders<br/>252 satır"]
    n_palette["palette<br/>333 satır"]
  end
  subgraph katman2["katman 2"]
    n_chat_prompt["chat_prompt<br/>396 satır"]
    n_guncelleme["guncelleme<br/>356 satır"]
    n_i18n["i18n<br/>305 satır"]
    n_services_yollar["services.yollar<br/>53 satır"]
  end
  subgraph katman1["katman 1"]
    n_chat_store["chat_store<br/>256 satır"]
    n_palette_store["palette_store<br/>96 satır"]
    n_paths["paths<br/>306 satır"]
    n_services_redaksiyon["services.redaksiyon<br/>63 satır"]
    n_storage["storage<br/>418 satır"]
  end
  subgraph katman0["katman 0"]
    n_catalog["catalog<br/>1461 satır"]
    n_errlog["errlog<br/>116 satır"]
    n_jsonstore["jsonstore<br/>83 satır"]
    n_release_manifest["release_manifest<br/>92 satır"]
    n_screencolor["screencolor<br/>149 satır"]
    n_services_zaman["services.zaman<br/>17 satır"]
    n_version["version<br/>30 satır"]
    n_winclr["winclr<br/>337 satır"]
    n_winsec["winsec<br/>308 satır"]
  end
  n_android_main -.->|erteli| n_app
  n_android_main -.->|erteli| n_desktop
  n_android_main -.->|erteli| n_errlog
  n_android_main -.->|erteli| n_paths
  n_app --> n_assets_store
  n_app --> n_backup
  n_app --> n_catalog
  n_app --> n_chat_client
  n_app --> n_chat_prompt
  n_app --> n_composite
  n_app --> n_credstore
  n_app --> n_errlog
  n_app --> n_models
  n_app --> n_paths
  n_app --> n_providers
  n_app --> n_routers_ayarlar
  n_app --> n_routers_bindirme
  n_app --> n_routers_galeri
  n_app --> n_routers_kok
  n_app --> n_routers_paletler
  n_app --> n_routers_sohbet
  n_app --> n_routers_uretim
  n_app --> n_services_dil
  n_app --> n_services_gorsel
  n_app --> n_services_modeller
  n_app --> n_services_palet
  n_app --> n_services_redaksiyon
  n_app --> n_services_zaman
  n_app --> n_version
  n_assets_store --> n_i18n
  n_assets_store --> n_jsonstore
  n_azure_client --> n_i18n
  n_azure_client --> n_paths
  n_azure_client --> n_winsec
  n_azure_flux_client --> n_azure_client
  n_azure_flux_client --> n_catalog
  n_azure_flux_client --> n_credstore
  n_azure_flux_client --> n_i18n
  n_azure_flux_client --> n_providers
  n_azure_mai_client --> n_azure_client
  n_azure_mai_client --> n_catalog
  n_azure_mai_client --> n_credstore
  n_azure_mai_client --> n_i18n
  n_azure_mai_client --> n_providers
  n_backup --> n_assets_store
  n_backup --> n_chat_store
  n_backup --> n_folders
  n_backup --> n_jsonstore
  n_backup --> n_palette_store
  n_backup --> n_storage
  n_chat_client --> n_azure_client
  n_chat_client --> n_chat_prompt
  n_chat_client --> n_i18n
  n_chat_client --> n_models
  n_chat_prompt --> n_paths
  n_chat_providers --> n_azure_client
  n_chat_providers --> n_catalog
  n_chat_providers --> n_chat_client
  n_chat_providers --> n_credstore
  n_chat_providers --> n_etiket
  n_chat_providers --> n_i18n
  n_chat_providers --> n_openai_chat
  n_chat_store --> n_jsonstore
  n_color_names --> n_palette
  n_composite --> n_i18n
  n_credstore --> n_azure_client
  n_credstore --> n_catalog
  n_credstore --> n_etiket
  n_credstore --> n_i18n
  n_desktop --> n_errlog
  n_desktop --> n_i18n
  n_desktop --> n_netguard
  n_desktop --> n_paths
  n_desktop --> n_screencolor
  n_desktop --> n_version
  n_desktop --> n_winclr
  n_desktop -.->|erteli| n_app
  n_desktop -.->|erteli| n_prefs
  n_etiket --> n_catalog
  n_etiket --> n_i18n
  n_fal_client --> n_azure_client
  n_fal_client --> n_catalog
  n_fal_client --> n_credstore
  n_fal_client --> n_i18n
  n_fal_client --> n_providers
  n_folders --> n_i18n
  n_folders --> n_jsonstore
  n_folders --> n_storage
  n_gemini_client --> n_azure_client
  n_gemini_client --> n_catalog
  n_gemini_client --> n_credstore
  n_gemini_client --> n_i18n
  n_gemini_client --> n_providers
  n_guncelleme --> n_errlog
  n_guncelleme --> n_jsonstore
  n_guncelleme --> n_paths
  n_guncelleme --> n_version
  n_i18n --> n_paths
  n_models --> n_catalog
  n_models --> n_etiket
  n_models --> n_i18n
  n_models --> n_palette
  n_netguard -.->|erteli| n_app
  n_openai_chat --> n_azure_client
  n_openai_chat --> n_catalog
  n_openai_chat --> n_chat_client
  n_openai_chat --> n_chat_prompt
  n_openai_chat --> n_credstore
  n_openai_chat --> n_etiket
  n_openai_chat --> n_i18n
  n_openai_chat --> n_providers
  n_openai_client --> n_azure_client
  n_openai_client --> n_catalog
  n_openai_client --> n_credstore
  n_openai_client --> n_i18n
  n_openai_client --> n_providers
  n_palette --> n_i18n
  n_palette_store --> n_jsonstore
  n_paths --> n_errlog
  n_prefs --> n_catalog
  n_prefs --> n_i18n
  n_prefs --> n_jsonstore
  n_prefs --> n_models
  n_providers --> n_azure_client
  n_providers --> n_catalog
  n_providers --> n_credstore
  n_providers --> n_etiket
  n_providers --> n_i18n
  n_providers -.->|erteli| n_azure_flux_client
  n_providers -.->|erteli| n_azure_mai_client
  n_providers -.->|erteli| n_fal_client
  n_providers -.->|erteli| n_gemini_client
  n_providers -.->|erteli| n_openai_client
  n_providers -.->|erteli| n_veo_client
  n_routers_ayarlar --> n_azure_client
  n_routers_ayarlar --> n_catalog
  n_routers_ayarlar --> n_guncelleme
  n_routers_ayarlar --> n_i18n
  n_routers_ayarlar --> n_models
  n_routers_ayarlar --> n_paths
  n_routers_ayarlar --> n_prefs
  n_routers_ayarlar --> n_services_dil
  n_routers_ayarlar --> n_services_modeller
  n_routers_ayarlar --> n_services_yollar
  n_routers_ayarlar --> n_version
  n_routers_bindirme --> n_assets_store
  n_routers_bindirme --> n_composite
  n_routers_bindirme --> n_i18n
  n_routers_bindirme --> n_models
  n_routers_bindirme --> n_services_dil
  n_routers_bindirme --> n_services_gorsel
  n_routers_bindirme --> n_services_kapilar
  n_routers_bindirme --> n_services_yollar
  n_routers_bindirme --> n_services_zaman
  n_routers_bindirme --> n_storage
  n_routers_galeri --> n_folders
  n_routers_galeri --> n_i18n
  n_routers_galeri --> n_models
  n_routers_galeri --> n_services_dil
  n_routers_galeri --> n_services_gorsel
  n_routers_galeri --> n_services_kapilar
  n_routers_galeri --> n_services_yollar
  n_routers_galeri --> n_services_zaman
  n_routers_galeri --> n_storage
  n_routers_kok --> n_errlog
  n_routers_kok --> n_i18n
  n_routers_kok --> n_paths
  n_routers_kok --> n_services_dil
  n_routers_kok --> n_services_yollar
  n_routers_kok --> n_version
  n_routers_paletler --> n_color_names
  n_routers_paletler --> n_i18n
  n_routers_paletler --> n_models
  n_routers_paletler --> n_palette
  n_routers_paletler --> n_palette_store
  n_routers_paletler --> n_services_dil
  n_routers_paletler --> n_services_palet
  n_routers_paletler --> n_services_yollar
  n_routers_paletler --> n_services_zaman
  n_routers_sohbet --> n_catalog
  n_routers_sohbet --> n_chat_client
  n_routers_sohbet --> n_chat_prompt
  n_routers_sohbet --> n_chat_providers
  n_routers_sohbet --> n_chat_store
  n_routers_sohbet --> n_i18n
  n_routers_sohbet --> n_models
  n_routers_sohbet --> n_prefs
  n_routers_sohbet --> n_services_dil
  n_routers_sohbet --> n_services_modeller
  n_routers_sohbet --> n_services_yollar
  n_routers_sohbet --> n_services_zaman
  n_routers_uretim --> n_azure_client
  n_routers_uretim --> n_catalog
  n_routers_uretim --> n_etiket
  n_routers_uretim --> n_i18n
  n_routers_uretim --> n_models
  n_routers_uretim --> n_palette
  n_routers_uretim --> n_providers
  n_routers_uretim --> n_services_dil
  n_routers_uretim --> n_services_gorsel
  n_routers_uretim --> n_services_kapilar
  n_routers_uretim --> n_services_palet
  n_routers_uretim --> n_services_yollar
  n_routers_uretim --> n_services_zaman
  n_routers_uretim --> n_storage
  n_services_dil --> n_i18n
  n_services_dil --> n_prefs
  n_services_dil --> n_services_yollar
  n_services_gorsel --> n_i18n
  n_services_gorsel --> n_services_dil
  n_services_gorsel --> n_services_yollar
  n_services_gorsel --> n_storage
  n_services_kapilar --> n_assets_store
  n_services_kapilar --> n_chat_store
  n_services_kapilar --> n_folders
  n_services_kapilar --> n_i18n
  n_services_kapilar --> n_services_dil
  n_services_kapilar --> n_services_yollar
  n_services_kapilar --> n_storage
  n_services_modeller --> n_azure_client
  n_services_modeller --> n_catalog
  n_services_modeller --> n_credstore
  n_services_modeller --> n_etiket
  n_services_modeller --> n_i18n
  n_services_modeller --> n_prefs
  n_services_modeller --> n_services_yollar
  n_services_modeller --> n_version
  n_services_palet --> n_color_names
  n_services_palet --> n_i18n
  n_services_palet --> n_models
  n_services_palet --> n_palette
  n_services_palet --> n_palette_store
  n_services_palet --> n_services_dil
  n_services_palet --> n_services_yollar
  n_services_redaksiyon --> n_catalog
  n_services_yollar --> n_paths
  n_storage --> n_catalog
  n_storage --> n_jsonstore
  n_veo_client --> n_azure_client
  n_veo_client --> n_catalog
  n_veo_client --> n_credstore
  n_veo_client --> n_i18n
  n_veo_client --> n_providers
```

## Döngüler

Birbirini ithal eden öbekler. Kesikli (`erteli`) bir kenarla
kırılmış döngü KUSUR DEĞİL — işlev içinde yapılan ithal, import
anında bir zincir kurmuyor (bkz. providers.py'nin gerekçesi).

* azure_flux_client ↔ azure_mai_client ↔ fal_client ↔ gemini_client ↔ openai_client ↔ providers ↔ veo_client — erteli bir ithalle kırılmış

## Modüller

| modül | satır | katman | ithal ettiği | ithal eden | test |
| --- | --- | --- | --- | --- | --- |
| `android_main.py` | 201 | 12 | `app` (erteli), `desktop` (erteli), `errlog` (erteli), `paths` (erteli) | 0 | 2 |
| `app.py` | 174 | 9 | `assets_store`, `backup`, `catalog`, `chat_client`, `chat_prompt`, `composite`, `credstore`, `errlog`, `models`, `paths`, `providers`, `routers.ayarlar`, `routers.bindirme`, `routers.galeri`, `routers.kok`, `routers.paletler`, `routers.sohbet`, `routers.uretim`, `services.dil`, `services.gorsel`, `services.modeller`, `services.palet`, `services.redaksiyon`, `services.zaman`, `version` | 3 | 36 |
| `assets_store.py` | 205 | 3 | `i18n`, `jsonstore` | 5 | 9 |
| `azure_client.py` | 458 | 3 | `i18n`, `paths`, `winsec` | 14 | 30 |
| `azure_flux_client.py` | 289 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 1 |
| `azure_mai_client.py` | 286 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 1 |
| `backup.py` | 190 | 4 | `assets_store`, `chat_store`, `folders`, `jsonstore`, `palette_store`, `storage` | 1 | 1 |
| `catalog.py` | 1461 | 0 | — | 20 | 29 |
| `chat_client.py` | 191 | 5 | `azure_client`, `chat_prompt`, `i18n`, `models` | 4 | 3 |
| `chat_prompt.py` | 396 | 2 | `paths` | 4 | 1 |
| `chat_providers.py` | 130 | 7 | `azure_client`, `catalog`, `chat_client`, `credstore`, `etiket`, `i18n`, `openai_chat` | 1 | 2 |
| `chat_store.py` | 256 | 1 | `jsonstore` | 3 | 2 |
| `color_names.py` | 421 | 4 | `palette` | 2 | 3 |
| `composite.py` | 165 | 3 | `i18n` | 2 | 1 |
| `credstore.py` | 198 | 4 | `azure_client`, `catalog`, `etiket`, `i18n` | 11 | 5 |
| `desktop.py` | 584 | 11 | `errlog`, `i18n`, `netguard`, `paths`, `screencolor`, `version`, `winclr`, `app` (erteli), `prefs` (erteli) | 1 | 2 |
| `errlog.py` | 116 | 0 | — | 6 | 1 |
| `etiket.py` | 118 | 3 | `catalog`, `i18n` | 7 | 1 |
| `fal_client.py` | 757 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 2 |
| `folders.py` | 252 | 3 | `i18n`, `jsonstore`, `storage` | 4 | 4 |
| `gemini_client.py` | 295 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 1 |
| `guncelleme.py` | 356 | 2 | `errlog`, `jsonstore`, `paths`, `version` | 1 | 5 |
| `i18n.py` | 305 | 2 | `paths` | 32 | 3 |
| `jsonstore.py` | 83 | 0 | — | 8 | 1 |
| `models.py` | 1056 | 4 | `catalog`, `etiket`, `i18n`, `palette` | 10 | 14 |
| `netguard.py` | 169 | 10 | `app` (erteli) | 1 | 1 |
| `openai_chat.py` | 180 | 6 | `azure_client`, `catalog`, `chat_client`, `chat_prompt`, `credstore`, `etiket`, `i18n`, `providers` | 1 | 3 |
| `openai_client.py` | 217 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 1 |
| `palette.py` | 333 | 3 | `i18n` | 5 | 3 |
| `palette_store.py` | 96 | 1 | `jsonstore` | 4 | 2 |
| `paths.py` | 306 | 1 | `errlog` | 10 | 4 |
| `prefs.py` | 249 | 5 | `catalog`, `i18n`, `jsonstore`, `models` | 5 | 6 |
| `providers.py` | 501 | 5 | `azure_client`, `catalog`, `credstore`, `etiket`, `i18n`, `azure_flux_client` (erteli), `azure_mai_client` (erteli), `fal_client` (erteli), `gemini_client` (erteli), `openai_client` (erteli), `veo_client` (erteli) | 9 | 7 |
| `release_manifest.py` | 92 | 0 | — | 0 | 3 |
| `routers/ayarlar.py` | 283 | 7 | `azure_client`, `catalog`, `guncelleme`, `i18n`, `models`, `paths`, `prefs`, `services.dil`, `services.modeller`, `services.yollar`, `version` | 1 | 0 |
| `routers/bindirme.py` | 227 | 8 | `assets_store`, `composite`, `i18n`, `models`, `services.dil`, `services.gorsel`, `services.kapilar`, `services.yollar`, `services.zaman`, `storage` | 1 | 0 |
| `routers/galeri.py` | 325 | 8 | `folders`, `i18n`, `models`, `services.dil`, `services.gorsel`, `services.kapilar`, `services.yollar`, `services.zaman`, `storage` | 1 | 0 |
| `routers/kok.py` | 82 | 7 | `errlog`, `i18n`, `paths`, `services.dil`, `services.yollar`, `version` | 1 | 0 |
| `routers/paletler.py` | 88 | 8 | `color_names`, `i18n`, `models`, `palette`, `palette_store`, `services.dil`, `services.palet`, `services.yollar`, `services.zaman` | 1 | 0 |
| `routers/sohbet.py` | 223 | 8 | `catalog`, `chat_client`, `chat_prompt`, `chat_providers`, `chat_store`, `i18n`, `models`, `prefs`, `services.dil`, `services.modeller`, `services.yollar`, `services.zaman` | 1 | 0 |
| `routers/uretim.py` | 416 | 8 | `azure_client`, `catalog`, `etiket`, `i18n`, `models`, `palette`, `providers`, `services.dil`, `services.gorsel`, `services.kapilar`, `services.palet`, `services.yollar`, `services.zaman`, `storage` | 1 | 0 |
| `screencolor.py` | 149 | 0 | — | 1 | 1 |
| `services/dil.py` | 56 | 6 | `i18n`, `prefs`, `services.yollar` | 11 | 1 |
| `services/gorsel.py` | 138 | 7 | `i18n`, `services.dil`, `services.yollar`, `storage` | 4 | 3 |
| `services/kapilar.py` | 70 | 7 | `assets_store`, `chat_store`, `folders`, `i18n`, `services.dil`, `services.yollar`, `storage` | 3 | 0 |
| `services/modeller.py` | 295 | 6 | `azure_client`, `catalog`, `credstore`, `etiket`, `i18n`, `prefs`, `services.yollar`, `version` | 3 | 0 |
| `services/palet.py` | 177 | 7 | `color_names`, `i18n`, `models`, `palette`, `palette_store`, `services.dil`, `services.yollar` | 3 | 0 |
| `services/redaksiyon.py` | 63 | 1 | `catalog` | 1 | 0 |
| `services/yollar.py` | 53 | 2 | `paths` | 12 | 1 |
| `services/zaman.py` | 17 | 0 | — | 6 | 0 |
| `storage.py` | 418 | 1 | `catalog`, `jsonstore` | 8 | 8 |
| `veo_client.py` | 629 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 1 |
| `version.py` | 30 | 0 | — | 7 | 9 |
| `winclr.py` | 337 | 0 | — | 1 | 1 |
| `winsec.py` | 308 | 0 | — | 1 | 2 |

## Giriş noktaları ve öksüzler

Kimsenin ithal etmediği modüller. `app`, `desktop`, `android_main` uygulamanın giriş noktaları — geri kalanı ya bir betikten çağrılıyor ya da artık kullanılmıyor; ikincisi bir bulgudur.

* `android_main` — giriş noktası
* `release_manifest` — ithal eden yok — kullanımı elle doğrulanmalı

## Yardımcılar (`tools/`)

Pakete girmiyor, çalışma zamanına dokunmuyor (bkz. tools/__init__.py).

```mermaid
flowchart LR
  n_tools_graf_uret["tools.graf_uret"]
  n_tools_make_legacy_fixtures["tools.make_legacy_fixtures"]
  n_tools_make_legacy_fixtures --> n_assets_store["assets_store"]
  n_tools_make_legacy_fixtures --> n_folders["folders"]
  n_tools_make_legacy_fixtures --> n_palette_store["palette_store"]
  n_tools_make_legacy_fixtures --> n_storage["storage"]
  n_tools_make_logo_goldens["tools.make_logo_goldens"]
  n_tools_render_brand_assets["tools.render_brand_assets"]
  n_tools_surum_karari["tools.surum_karari"]
  n_tools_surum_karari --> n_version["version"]
  n_tools_surum_yaz["tools.surum_yaz"]
  n_tools_test_ortami["tools.test_ortami"]
```

