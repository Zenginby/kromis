<!-- ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: tools/graf_uret.py · yenilemek için: python3 tools/graf_uret.py -->

# Modül grafı

67 Python modülü, 240 modül düzeyi + 14 erteli ithal kenarı.

Katman, o modülün depo içindeki en uzun bağımlılık zincirinin uzunluğu:
**katman 0 hiçbir depo modülüne dayanmaz**, en üst katman uygulamanın
giriş noktasıdır. Bir modülü değiştirdiğinizde etkilenebilecek yer,
onun `ithal eden` sütunudur — okuma yönü budur.

## Uygulama

```mermaid
flowchart TD
  subgraph katman13["katman 13"]
    n_android_main["android_main<br/>204 satır"]
  end
  subgraph katman12["katman 12"]
    n_desktop["desktop<br/>588 satır"]
  end
  subgraph katman11["katman 11"]
    n_netguard["netguard<br/>169 satır"]
  end
  subgraph katman10["katman 10"]
    n_app["app<br/>216 satır"]
  end
  subgraph katman9["katman 9"]
    n_routers_bindirme["routers.bindirme<br/>231 satır"]
    n_routers_galeri["routers.galeri<br/>334 satır"]
    n_routers_paletler["routers.paletler<br/>90 satır"]
    n_routers_uretim["routers.uretim<br/>439 satır"]
  end
  subgraph katman8["katman 8"]
    n_routers_ayarlar["routers.ayarlar<br/>303 satır"]
    n_routers_kok["routers.kok<br/>81 satır"]
    n_routers_sohbet["routers.sohbet<br/>225 satır"]
    n_services_gorsel["services.gorsel<br/>140 satır"]
    n_services_kapilar["services.kapilar<br/>75 satır"]
    n_services_palet["services.palet<br/>181 satır"]
  end
  subgraph katman7["katman 7"]
    n_chat_providers["chat_providers<br/>133 satır"]
    n_services_dil["services.dil<br/>149 satır"]
  end
  subgraph katman6["katman 6"]
    n_openai_chat["openai_chat<br/>180 satır"]
    n_services_modeller["services.modeller<br/>295 satır"]
    n_services_tercih["services.tercih<br/>98 satır"]
  end
  subgraph katman5["katman 5"]
    n_azure_flux_client["azure_flux_client<br/>289 satır"]
    n_azure_mai_client["azure_mai_client<br/>286 satır"]
    n_chat_client["chat_client<br/>193 satır"]
    n_fal_client["fal_client<br/>757 satır"]
    n_gemini_client["gemini_client<br/>295 satır"]
    n_openai_client["openai_client<br/>217 satır"]
    n_prefs["prefs<br/>268 satır"]
    n_providers["providers<br/>505 satır"]
    n_services_tablolar["services.tablolar<br/>454 satır"]
    n_veo_client["veo_client<br/>629 satır"]
  end
  subgraph katman4["katman 4"]
    n_backup["backup<br/>190 satır"]
    n_color_names["color_names<br/>421 satır"]
    n_credstore["credstore<br/>201 satır"]
    n_models["models<br/>1056 satır"]
  end
  subgraph katman3["katman 3"]
    n_assets_store["assets_store<br/>205 satır"]
    n_azure_client["azure_client<br/>458 satır"]
    n_composite["composite<br/>165 satır"]
    n_etiket["etiket<br/>118 satır"]
    n_folders["folders<br/>253 satır"]
    n_palette["palette<br/>333 satır"]
    n_routers_saglik["routers.saglik<br/>112 satır"]
  end
  subgraph katman2["katman 2"]
    n_chat_prompt["chat_prompt<br/>396 satır"]
    n_guncelleme["guncelleme<br/>360 satır"]
    n_i18n["i18n<br/>305 satır"]
    n_services_ayar["services.ayar<br/>90 satır"]
  end
  subgraph katman1["katman 1"]
    n_chat_store["chat_store<br/>258 satır"]
    n_palette_store["palette_store<br/>96 satır"]
    n_paths["paths<br/>326 satır"]
    n_services_redaksiyon["services.redaksiyon<br/>63 satır"]
    n_storage["storage<br/>423 satır"]
  end
  subgraph katman0["katman 0"]
    n_catalog["catalog<br/>1461 satır"]
    n_errlog["errlog<br/>116 satır"]
    n_jsonstore["jsonstore<br/>83 satır"]
    n_release_manifest["release_manifest<br/>92 satır"]
    n_screencolor["screencolor<br/>149 satır"]
    n_services_db["services.db<br/>174 satır"]
    n_services_zaman["services.zaman<br/>17 satır"]
    n_version["version<br/>30 satır"]
    n_winclr["winclr<br/>339 satır"]
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
  n_app --> n_routers_saglik
  n_app --> n_routers_sohbet
  n_app --> n_routers_uretim
  n_app --> n_services_ayar
  n_app --> n_services_db
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
  n_routers_ayarlar --> n_services_ayar
  n_routers_ayarlar --> n_services_dil
  n_routers_ayarlar --> n_services_modeller
  n_routers_ayarlar --> n_services_tercih
  n_routers_ayarlar --> n_version
  n_routers_bindirme --> n_assets_store
  n_routers_bindirme --> n_composite
  n_routers_bindirme --> n_i18n
  n_routers_bindirme --> n_models
  n_routers_bindirme --> n_services_ayar
  n_routers_bindirme --> n_services_dil
  n_routers_bindirme --> n_services_gorsel
  n_routers_bindirme --> n_services_kapilar
  n_routers_bindirme --> n_services_zaman
  n_routers_bindirme --> n_storage
  n_routers_galeri --> n_folders
  n_routers_galeri --> n_i18n
  n_routers_galeri --> n_models
  n_routers_galeri --> n_services_ayar
  n_routers_galeri --> n_services_dil
  n_routers_galeri --> n_services_gorsel
  n_routers_galeri --> n_services_kapilar
  n_routers_galeri --> n_services_zaman
  n_routers_galeri --> n_storage
  n_routers_kok --> n_errlog
  n_routers_kok --> n_i18n
  n_routers_kok --> n_services_ayar
  n_routers_kok --> n_services_dil
  n_routers_kok --> n_version
  n_routers_paletler --> n_color_names
  n_routers_paletler --> n_i18n
  n_routers_paletler --> n_models
  n_routers_paletler --> n_palette
  n_routers_paletler --> n_palette_store
  n_routers_paletler --> n_services_ayar
  n_routers_paletler --> n_services_dil
  n_routers_paletler --> n_services_palet
  n_routers_paletler --> n_services_zaman
  n_routers_saglik --> n_services_ayar
  n_routers_saglik --> n_services_db
  n_routers_saglik --> n_version
  n_routers_sohbet --> n_catalog
  n_routers_sohbet --> n_chat_client
  n_routers_sohbet --> n_chat_prompt
  n_routers_sohbet --> n_chat_providers
  n_routers_sohbet --> n_chat_store
  n_routers_sohbet --> n_i18n
  n_routers_sohbet --> n_models
  n_routers_sohbet --> n_prefs
  n_routers_sohbet --> n_services_ayar
  n_routers_sohbet --> n_services_dil
  n_routers_sohbet --> n_services_modeller
  n_routers_sohbet --> n_services_zaman
  n_routers_uretim --> n_azure_client
  n_routers_uretim --> n_catalog
  n_routers_uretim --> n_etiket
  n_routers_uretim --> n_i18n
  n_routers_uretim --> n_models
  n_routers_uretim --> n_palette
  n_routers_uretim --> n_providers
  n_routers_uretim --> n_services_ayar
  n_routers_uretim --> n_services_dil
  n_routers_uretim --> n_services_gorsel
  n_routers_uretim --> n_services_kapilar
  n_routers_uretim --> n_services_palet
  n_routers_uretim --> n_services_zaman
  n_routers_uretim --> n_storage
  n_services_ayar --> n_paths
  n_services_dil --> n_i18n
  n_services_dil --> n_services_ayar
  n_services_dil --> n_services_tercih
  n_services_gorsel --> n_i18n
  n_services_gorsel --> n_services_dil
  n_services_gorsel --> n_storage
  n_services_kapilar --> n_assets_store
  n_services_kapilar --> n_chat_store
  n_services_kapilar --> n_folders
  n_services_kapilar --> n_i18n
  n_services_kapilar --> n_services_dil
  n_services_kapilar --> n_storage
  n_services_modeller --> n_azure_client
  n_services_modeller --> n_catalog
  n_services_modeller --> n_credstore
  n_services_modeller --> n_etiket
  n_services_modeller --> n_i18n
  n_services_modeller --> n_prefs
  n_services_modeller --> n_version
  n_services_palet --> n_color_names
  n_services_palet --> n_i18n
  n_services_palet --> n_models
  n_services_palet --> n_palette
  n_services_palet --> n_palette_store
  n_services_palet --> n_services_dil
  n_services_redaksiyon --> n_catalog
  n_services_tablolar --> n_assets_store
  n_services_tablolar --> n_models
  n_services_tercih --> n_prefs
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
| `android_main.py` | 204 | 13 | `app` (erteli), `desktop` (erteli), `errlog` (erteli), `paths` (erteli) | 0 | 2 |
| `app.py` | 216 | 10 | `assets_store`, `backup`, `catalog`, `chat_client`, `chat_prompt`, `composite`, `credstore`, `errlog`, `models`, `paths`, `providers`, `routers.ayarlar`, `routers.bindirme`, `routers.galeri`, `routers.kok`, `routers.paletler`, `routers.saglik`, `routers.sohbet`, `routers.uretim`, `services.ayar`, `services.db`, `services.dil`, `services.gorsel`, `services.modeller`, `services.palet`, `services.redaksiyon`, `services.zaman`, `version` | 3 | 39 |
| `assets_store.py` | 205 | 3 | `i18n`, `jsonstore` | 6 | 10 |
| `azure_client.py` | 458 | 3 | `i18n`, `paths`, `winsec` | 14 | 30 |
| `azure_flux_client.py` | 289 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 1 |
| `azure_mai_client.py` | 286 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 1 |
| `backup.py` | 190 | 4 | `assets_store`, `chat_store`, `folders`, `jsonstore`, `palette_store`, `storage` | 1 | 1 |
| `catalog.py` | 1461 | 0 | — | 20 | 30 |
| `chat_client.py` | 193 | 5 | `azure_client`, `chat_prompt`, `i18n`, `models` | 4 | 3 |
| `chat_prompt.py` | 396 | 2 | `paths` | 4 | 1 |
| `chat_providers.py` | 133 | 7 | `azure_client`, `catalog`, `chat_client`, `credstore`, `etiket`, `i18n`, `openai_chat` | 1 | 2 |
| `chat_store.py` | 258 | 1 | `jsonstore` | 3 | 3 |
| `color_names.py` | 421 | 4 | `palette` | 2 | 3 |
| `composite.py` | 165 | 3 | `i18n` | 2 | 1 |
| `credstore.py` | 201 | 4 | `azure_client`, `catalog`, `etiket`, `i18n` | 11 | 5 |
| `desktop.py` | 588 | 12 | `errlog`, `i18n`, `netguard`, `paths`, `screencolor`, `version`, `winclr`, `app` (erteli), `prefs` (erteli) | 1 | 2 |
| `errlog.py` | 116 | 0 | — | 6 | 1 |
| `etiket.py` | 118 | 3 | `catalog`, `i18n` | 7 | 1 |
| `fal_client.py` | 757 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 2 |
| `folders.py` | 253 | 3 | `i18n`, `jsonstore`, `storage` | 4 | 5 |
| `gemini_client.py` | 295 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 1 |
| `guncelleme.py` | 360 | 2 | `errlog`, `jsonstore`, `paths`, `version` | 1 | 5 |
| `i18n.py` | 305 | 2 | `paths` | 32 | 4 |
| `jsonstore.py` | 83 | 0 | — | 8 | 1 |
| `models.py` | 1056 | 4 | `catalog`, `etiket`, `i18n`, `palette` | 11 | 15 |
| `netguard.py` | 169 | 11 | `app` (erteli) | 1 | 1 |
| `openai_chat.py` | 180 | 6 | `azure_client`, `catalog`, `chat_client`, `chat_prompt`, `credstore`, `etiket`, `i18n`, `providers` | 1 | 3 |
| `openai_client.py` | 217 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 1 |
| `palette.py` | 333 | 3 | `i18n` | 5 | 3 |
| `palette_store.py` | 96 | 1 | `jsonstore` | 4 | 3 |
| `paths.py` | 326 | 1 | `errlog` | 9 | 4 |
| `prefs.py` | 268 | 5 | `catalog`, `i18n`, `jsonstore`, `models` | 5 | 7 |
| `providers.py` | 505 | 5 | `azure_client`, `catalog`, `credstore`, `etiket`, `i18n`, `azure_flux_client` (erteli), `azure_mai_client` (erteli), `fal_client` (erteli), `gemini_client` (erteli), `openai_client` (erteli), `veo_client` (erteli) | 9 | 7 |
| `release_manifest.py` | 92 | 0 | — | 0 | 3 |
| `routers/ayarlar.py` | 303 | 8 | `azure_client`, `catalog`, `guncelleme`, `i18n`, `models`, `paths`, `prefs`, `services.ayar`, `services.dil`, `services.modeller`, `services.tercih`, `version` | 1 | 0 |
| `routers/bindirme.py` | 231 | 9 | `assets_store`, `composite`, `i18n`, `models`, `services.ayar`, `services.dil`, `services.gorsel`, `services.kapilar`, `services.zaman`, `storage` | 1 | 0 |
| `routers/galeri.py` | 334 | 9 | `folders`, `i18n`, `models`, `services.ayar`, `services.dil`, `services.gorsel`, `services.kapilar`, `services.zaman`, `storage` | 1 | 0 |
| `routers/kok.py` | 81 | 8 | `errlog`, `i18n`, `services.ayar`, `services.dil`, `version` | 1 | 0 |
| `routers/paletler.py` | 90 | 9 | `color_names`, `i18n`, `models`, `palette`, `palette_store`, `services.ayar`, `services.dil`, `services.palet`, `services.zaman` | 1 | 0 |
| `routers/saglik.py` | 112 | 3 | `services.ayar`, `services.db`, `version` | 1 | 1 |
| `routers/sohbet.py` | 225 | 8 | `catalog`, `chat_client`, `chat_prompt`, `chat_providers`, `chat_store`, `i18n`, `models`, `prefs`, `services.ayar`, `services.dil`, `services.modeller`, `services.zaman` | 1 | 0 |
| `routers/uretim.py` | 439 | 9 | `azure_client`, `catalog`, `etiket`, `i18n`, `models`, `palette`, `providers`, `services.ayar`, `services.dil`, `services.gorsel`, `services.kapilar`, `services.palet`, `services.zaman`, `storage` | 1 | 0 |
| `screencolor.py` | 149 | 0 | — | 1 | 1 |
| `services/ayar.py` | 90 | 2 | `paths` | 10 | 2 |
| `services/db.py` | 174 | 0 | — | 2 | 2 |
| `services/dil.py` | 149 | 7 | `i18n`, `services.ayar`, `services.tercih` | 11 | 2 |
| `services/gorsel.py` | 140 | 8 | `i18n`, `services.dil`, `storage` | 4 | 3 |
| `services/kapilar.py` | 75 | 8 | `assets_store`, `chat_store`, `folders`, `i18n`, `services.dil`, `storage` | 3 | 0 |
| `services/modeller.py` | 295 | 6 | `azure_client`, `catalog`, `credstore`, `etiket`, `i18n`, `prefs`, `version` | 3 | 0 |
| `services/palet.py` | 181 | 8 | `color_names`, `i18n`, `models`, `palette`, `palette_store`, `services.dil` | 3 | 0 |
| `services/redaksiyon.py` | 63 | 1 | `catalog` | 1 | 0 |
| `services/tablolar.py` | 454 | 5 | `assets_store`, `models` | 0 | 1 |
| `services/tercih.py` | 98 | 6 | `prefs` | 2 | 1 |
| `services/zaman.py` | 17 | 0 | — | 6 | 0 |
| `storage.py` | 423 | 1 | `catalog`, `jsonstore` | 8 | 10 |
| `veo_client.py` | 629 | 5 | `azure_client`, `catalog`, `credstore`, `i18n`, `providers` | 1 | 1 |
| `version.py` | 30 | 0 | — | 8 | 11 |
| `winclr.py` | 339 | 0 | — | 1 | 1 |
| `winsec.py` | 308 | 0 | — | 1 | 2 |

## Giriş noktaları ve öksüzler

Kimsenin ithal etmediği modüller. `app`, `desktop`, `android_main` uygulamanın giriş noktaları — geri kalanı ya bir betikten çağrılıyor ya da artık kullanılmıyor; ikincisi bir bulgudur.

* `android_main` — giriş noktası
* `release_manifest` — ithal eden yok — kullanımı elle doğrulanmalı
* `services.tablolar` — ithal eden yok — kullanımı elle doğrulanmalı

## Yardımcılar (`tools/`)

Pakete girmiyor, çalışma zamanına dokunmuyor (bkz. tools/__init__.py).

```mermaid
flowchart LR
  n_tools_gecici_postgres["tools.gecici_postgres"]
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
  n_tools_test_ortami --> n_tools_gecici_postgres["tools.gecici_postgres"]
```

