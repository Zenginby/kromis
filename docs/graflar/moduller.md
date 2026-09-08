<!-- ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: tools/graf_uret.py · yenilemek için: python3 tools/graf_uret.py -->

# Modül grafı

41 Python modülü, 90 modül düzeyi + 10 erteli ithal kenarı.

Katman, o modülün depo içindeki en uzun bağımlılık zincirinin uzunluğu:
**katman 0 hiçbir depo modülüne dayanmaz**, en üst katman uygulamanın
giriş noktasıdır. Bir modülü değiştirdiğinizde etkilenebilecek yer,
onun `ithal eden` sütunudur — okuma yönü budur.

## Uygulama

```mermaid
flowchart TD
  subgraph katman9["katman 9"]
    n_android_main["android_main<br/>194 satır"]
  end
  subgraph katman8["katman 8"]
    n_desktop["desktop<br/>558 satır"]
  end
  subgraph katman7["katman 7"]
    n_netguard["netguard<br/>157 satır"]
  end
  subgraph katman6["katman 6"]
    n_app["app<br/>2104 satır"]
  end
  subgraph katman5["katman 5"]
    n_chat_providers["chat_providers<br/>124 satır"]
  end
  subgraph katman4["katman 4"]
    n_openai_chat["openai_chat<br/>179 satır"]
  end
  subgraph katman3["katman 3"]
    n_backup["backup<br/>187 satır"]
    n_chat_client["chat_client<br/>182 satır"]
    n_gemini_client["gemini_client<br/>293 satır"]
    n_openai_client["openai_client<br/>215 satır"]
    n_prefs["prefs<br/>219 satır"]
    n_providers["providers<br/>389 satır"]
    n_veo_client["veo_client<br/>590 satır"]
  end
  subgraph katman2["katman 2"]
    n_credstore["credstore<br/>194 satır"]
    n_folders["folders<br/>248 satır"]
    n_models["models<br/>927 satır"]
  end
  subgraph katman1["katman 1"]
    n_assets_store["assets_store<br/>201 satır"]
    n_azure_client["azure_client<br/>458 satır"]
    n_chat_prompt["chat_prompt<br/>172 satır"]
    n_chat_store["chat_store<br/>253 satır"]
    n_color_names["color_names<br/>418 satır"]
    n_guncelleme["guncelleme<br/>219 satır"]
    n_palette_store["palette_store<br/>93 satır"]
    n_storage["storage<br/>415 satır"]
  end
  subgraph katman0["katman 0"]
    n_catalog["catalog<br/>1063 satır"]
    n_composite["composite<br/>158 satır"]
    n_errlog["errlog<br/>114 satır"]
    n_jsonstore["jsonstore<br/>80 satır"]
    n_palette["palette<br/>327 satır"]
    n_paths["paths<br/>167 satır"]
    n_release_manifest["release_manifest<br/>70 satır"]
    n_screencolor["screencolor<br/>150 satır"]
    n_version["version<br/>27 satır"]
    n_winclr["winclr<br/>331 satır"]
    n_winsec["winsec<br/>305 satır"]
  end
  n_android_main -.->|erteli| n_app
  n_android_main -.->|erteli| n_desktop
  n_android_main -.->|erteli| n_errlog
  n_android_main -.->|erteli| n_paths
  n_app --> n_assets_store
  n_app --> n_azure_client
  n_app --> n_backup
  n_app --> n_catalog
  n_app --> n_chat_client
  n_app --> n_chat_prompt
  n_app --> n_chat_providers
  n_app --> n_chat_store
  n_app --> n_color_names
  n_app --> n_composite
  n_app --> n_credstore
  n_app --> n_errlog
  n_app --> n_folders
  n_app --> n_guncelleme
  n_app --> n_models
  n_app --> n_palette
  n_app --> n_palette_store
  n_app --> n_paths
  n_app --> n_prefs
  n_app --> n_providers
  n_app --> n_storage
  n_app --> n_version
  n_assets_store --> n_jsonstore
  n_azure_client --> n_paths
  n_azure_client --> n_winsec
  n_backup --> n_assets_store
  n_backup --> n_chat_store
  n_backup --> n_folders
  n_backup --> n_jsonstore
  n_backup --> n_palette_store
  n_backup --> n_storage
  n_chat_client --> n_azure_client
  n_chat_client --> n_chat_prompt
  n_chat_client --> n_models
  n_chat_prompt --> n_paths
  n_chat_providers --> n_azure_client
  n_chat_providers --> n_catalog
  n_chat_providers --> n_chat_client
  n_chat_providers --> n_credstore
  n_chat_providers --> n_openai_chat
  n_chat_store --> n_jsonstore
  n_color_names --> n_palette
  n_credstore --> n_azure_client
  n_credstore --> n_catalog
  n_desktop --> n_errlog
  n_desktop --> n_netguard
  n_desktop --> n_paths
  n_desktop --> n_screencolor
  n_desktop --> n_version
  n_desktop --> n_winclr
  n_desktop -.->|erteli| n_app
  n_folders --> n_jsonstore
  n_folders --> n_storage
  n_gemini_client --> n_azure_client
  n_gemini_client --> n_catalog
  n_gemini_client --> n_credstore
  n_gemini_client --> n_providers
  n_guncelleme --> n_errlog
  n_guncelleme --> n_jsonstore
  n_guncelleme --> n_paths
  n_guncelleme --> n_version
  n_models --> n_azure_client
  n_models --> n_catalog
  n_models --> n_palette
  n_netguard -.->|erteli| n_app
  n_openai_chat --> n_azure_client
  n_openai_chat --> n_catalog
  n_openai_chat --> n_chat_client
  n_openai_chat --> n_chat_prompt
  n_openai_chat --> n_credstore
  n_openai_chat --> n_providers
  n_openai_client --> n_azure_client
  n_openai_client --> n_catalog
  n_openai_client --> n_credstore
  n_openai_client --> n_providers
  n_palette_store --> n_jsonstore
  n_prefs --> n_catalog
  n_prefs --> n_jsonstore
  n_prefs --> n_models
  n_providers --> n_azure_client
  n_providers --> n_catalog
  n_providers --> n_credstore
  n_providers -.->|erteli| n_gemini_client
  n_providers -.->|erteli| n_openai_client
  n_providers -.->|erteli| n_veo_client
  n_storage --> n_catalog
  n_storage --> n_jsonstore
  n_veo_client --> n_azure_client
  n_veo_client --> n_catalog
  n_veo_client --> n_credstore
  n_veo_client --> n_providers
```

## Döngüler

Birbirini ithal eden öbekler. Kesikli (`erteli`) bir kenarla
kırılmış döngü KUSUR DEĞİL — işlev içinde yapılan ithal, import
anında bir zincir kurmuyor (bkz. providers.py'nin gerekçesi).

* gemini_client ↔ openai_client ↔ providers ↔ veo_client — erteli bir ithalle kırılmış

## Modüller

| modül | satır | katman | ithal ettiği | ithal eden | test |
| --- | --- | --- | --- | --- | --- |
| `android_main.py` | 194 | 9 | `app` (erteli), `desktop` (erteli), `errlog` (erteli), `paths` (erteli) | 0 | 1 |
| `app.py` | 2104 | 6 | `assets_store`, `azure_client`, `backup`, `catalog`, `chat_client`, `chat_prompt`, `chat_providers`, `chat_store`, `color_names`, `composite`, `credstore`, `errlog`, `folders`, `guncelleme`, `models`, `palette`, `palette_store`, `paths`, `prefs`, `providers`, `storage`, `version` | 3 | 30 |
| `assets_store.py` | 201 | 1 | `jsonstore` | 3 | 9 |
| `azure_client.py` | 458 | 1 | `paths`, `winsec` | 10 | 27 |
| `backup.py` | 187 | 3 | `assets_store`, `chat_store`, `folders`, `jsonstore`, `palette_store`, `storage` | 1 | 1 |
| `catalog.py` | 1063 | 0 | — | 11 | 23 |
| `chat_client.py` | 182 | 3 | `azure_client`, `chat_prompt`, `models` | 3 | 3 |
| `chat_prompt.py` | 172 | 1 | `paths` | 3 | 1 |
| `chat_providers.py` | 124 | 5 | `azure_client`, `catalog`, `chat_client`, `credstore`, `openai_chat` | 1 | 2 |
| `chat_store.py` | 253 | 1 | `jsonstore` | 2 | 2 |
| `color_names.py` | 418 | 1 | `palette` | 1 | 3 |
| `composite.py` | 158 | 0 | — | 1 | 1 |
| `credstore.py` | 194 | 2 | `azure_client`, `catalog` | 7 | 4 |
| `desktop.py` | 558 | 8 | `errlog`, `netguard`, `paths`, `screencolor`, `version`, `winclr`, `app` (erteli) | 1 | 2 |
| `errlog.py` | 114 | 0 | — | 4 | 1 |
| `folders.py` | 248 | 2 | `jsonstore`, `storage` | 3 | 4 |
| `gemini_client.py` | 293 | 3 | `azure_client`, `catalog`, `credstore`, `providers` | 1 | 1 |
| `guncelleme.py` | 219 | 1 | `errlog`, `jsonstore`, `paths`, `version` | 1 | 2 |
| `jsonstore.py` | 80 | 0 | — | 8 | 1 |
| `models.py` | 927 | 2 | `azure_client`, `catalog`, `palette` | 3 | 13 |
| `netguard.py` | 157 | 7 | `app` (erteli) | 1 | 1 |
| `openai_chat.py` | 179 | 4 | `azure_client`, `catalog`, `chat_client`, `chat_prompt`, `credstore`, `providers` | 1 | 3 |
| `openai_client.py` | 215 | 3 | `azure_client`, `catalog`, `credstore`, `providers` | 1 | 1 |
| `palette.py` | 327 | 0 | — | 3 | 3 |
| `palette_store.py` | 93 | 1 | `jsonstore` | 3 | 3 |
| `paths.py` | 167 | 0 | — | 6 | 3 |
| `prefs.py` | 219 | 3 | `catalog`, `jsonstore`, `models` | 1 | 4 |
| `providers.py` | 389 | 3 | `azure_client`, `catalog`, `credstore`, `gemini_client` (erteli), `openai_client` (erteli), `veo_client` (erteli) | 5 | 5 |
| `release_manifest.py` | 70 | 0 | — | 0 | 2 |
| `screencolor.py` | 150 | 0 | — | 1 | 1 |
| `storage.py` | 415 | 1 | `catalog`, `jsonstore` | 4 | 10 |
| `veo_client.py` | 590 | 3 | `azure_client`, `catalog`, `credstore`, `providers` | 1 | 1 |
| `version.py` | 27 | 0 | — | 4 | 7 |
| `winclr.py` | 331 | 0 | — | 1 | 1 |
| `winsec.py` | 305 | 0 | — | 1 | 2 |

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
```

