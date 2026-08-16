# android/wheels/

Chaquopy'nin pip'i sdist kurmuyor (`--only-binary`), yani PyPI'de Android
wheel'i olmayan her bağımlılık buraya elle konur.

Bugün buraya giren tek dosya **pydantic-core**:

```
pydantic_core-<sürüm>-cp313-cp313-android_26_arm64_v8a.whl
```

## Nasıl üretilir

1. `.github/workflows/build-pydantic-core-android.yml` workflow'unu elle tetikle
   (Actions → *pydantic-core Android wheel* → Run workflow). Sürümler boş
   bırakılırsa `android/pins.properties` okunur.
2. Koşu bitince `pydantic-core-android-arm64` varlığını indir.
3. `.whl` dosyasını bu dizine koy, **eski dosyayı sil** (biriktirme: bayat
   wheel'ler APK'yı şişirir) ve commit'le.
4. Sürüm değiştiyse `android/pins.properties` içindeki `pydanticCoreVersion`
   ve `pydanticVersion` çiftini de aynı commit'te güncelle —
   `android/app/build.gradle` wheel'in adını o çivilerden kuruyor.

> `.gitignore` `*.whl`'i **dışarıda bırakmıyor**: bu dosya kaynak sayılıyor,
> derleme çıktısı değil. Gerekçe: `docs/android/pydantic-karari.md`.
