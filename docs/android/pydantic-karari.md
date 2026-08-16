# Faz 0 — pydantic kararı

**Durum:** Yol A uygulandı (wheel'i kendimiz derliyoruz). Yol B yazılı yedek olarak duruyor.
**Tarih:** 2026-08-16 · **Kapsam:** Android (Chaquopy) paketi · **Masaüstüne etkisi:** yok

## Sorun

Chaquopy 17 (2025-12) cihazda tam CPython koşturuyor ama `pip`'i `--only-binary`
ile çalışıyor: **sdist kurulmuyor, her bağımlılık wheel olmak zorunda.**

Bağımlılık listemizin tamamı bu kapıdan geçiyor — biri hariç:

| Paket | Durum |
|---|---|
| `fastapi`, `starlette`, `httpx`, `anyio`, `h11`, `certifi`, `idna`, `sniffio`, `python-multipart` | saf Python ✔ |
| `Pillow` | Chaquopy deposunda 11.0.0 var; `requirements.txt`'teki `Pillow==11.*` pinine uyuyor ✔ |
| `uvicorn` | `uvloop`/`httptools` native, ama **sade** uvicorn (asyncio + h11) saf Python ✔ — bu zaten kanıtlı: `gpt-image-studio.spec:97` masaüstü paketinde de bu dördünü dışarıda bırakıyor ve uygulama çalışıyor |
| **`pydantic-core`** | **YOK** ✘ — ne Chaquopy deposunda ne PyPI'de Android wheel'i var |

`pydantic-core` Rust ile yazılmış ve `pydantic`'in tamamı ona bağlı; `pydantic`
olmadan FastAPI hiç import edilmiyor. Projenin tek gerçek engeli bu.

Chaquopy'ye paket ekleyen PR (#1413) birleşmemiş ve bakımcı yeni paket kabul
etmediğini yazmış — yani "bekleyip depoya girmesini ummak" bir yol değil.

## Yol A — wheel'i kendimiz derleyelim *(seçilen)*

`cibuildwheel` 3.1+ Android'i hedefliyor (PEP 738: `arm64_v8a`, `x86_64`) ve
`pydantic-core` maturin ile `aarch64-linux-android` hedefine cross-compile
ediliyor.

- Workflow: `.github/workflows/build-pydantic-core-android.yml`
- Çıktı: `pydantic_core-<sürüm>-cp313-cp313-android_<API>_arm64_v8a.whl`
- Kurulum: `android/app/build.gradle` → `pip { install "./wheels/<dosya>" }`

### Düzeltme (2026-08-16) — wheel artık APK'nın önkoşulu değil

İlk kurgu wheel'i **yalnız elle** üretiyor ve repoya işlenmesini bekliyordu.
Sonuç, PR #28 incelemesinde çıktı: wheel repoya girmediği için `build.gradle`
her ortamda `GradleException` atıyordu ve APK **hiçbir yerde** derlenemiyordu.
Tek bir elle adım, telefona kurulacak paketin tamamını rehin alıyordu — üstelik
bir `v*` tag'i atıldığında bu, "yayın çıktı ama Android yok" olarak görünecekti.

Wheel workflow'u artık `workflow_call` ile de çağrılabiliyor ve
`build-android.yml` onu bir iş olarak koşturuyor. Wheel üç kaynaktan gelebiliyor
— repo > önbellek > derleme — ve üçü de aynı doğrulama kapısından geçiyor.

Karar DEĞİŞMEDİ, yalnız zorunluluktan çıktı: repodaki dosya hâlâ önceliklidir
ve yayın tekrarlanabilirliği için hâlâ önerilir (bkz. `android/wheels/README.md`).
"Her APK derlemesinde koşmasın" kaygısı önbellekle karşılanıyor: çivi başına
bir kez derleniyor, sonraki koşular saniyeler içinde geri yüklüyor.

**Ürün kodunda değişiklik: SIFIR.** `models.py` (588 satır, 14 `BaseModel`,
22 `field_validator`) ve masaüstü tarafı aynen kalıyor. Bu yüzden ilk denenen
yol bu oldu.

Risk noktaları ve nasıl kapatıldıkları:

| Risk | Kapı |
|---|---|
| `cp` sürümü Chaquopy'nin çalışma zamanı Python'uyla aynı olmalı | `android/pins.properties` tek kaynak; workflow etiketi `cp<XY>` ile doğruluyor |
| Etiketteki API seviyesi `minSdk`'dan büyük olamaz | Workflow `ETIKET_API -le API` kapısı |
| `pydantic` ↔ `pydantic-core` sürüm çifti uyuşmalı | İkisi de `pins.properties`'te çivili, `build.gradle` ikisini de oradan okuyor |
| Rust'ın NDK linker ayarı | NDK sürümü workflow'da açıkça yazılı, `rustup target add` ayrı adım |
| Etiketi doğru ama içi boş wheel | Workflow wheel'in içinde `.so` arıyor |

## Yol B — `models.py`'yi pydantic v1'e taşı *(yedek, uygulanmadı)*

pydantic v1 saf Python derlenebiliyor: `SKIP_CYTHON=1 pip wheel pydantic==1.10.22`
→ `pydantic-1.10.22-py3-none-any.whl`. Cross-compile hiç gerekmiyor, sıfır
derleme riski. FastAPI 0.115 v1'i hâlâ destekliyor
(`pydantic!=2.0.0,…,<3.0.0,>=1.7.4`).

Bedeli:

- `models.py`: 14 `BaseModel`, 22 `field_validator`, 1 `model_validator`,
  9 `model_config = ConfigDict(extra="forbid")`, `Annotated[str, Field(...)]`
  kullanımları — hepsi v1 karşılıklarına çevrilecek.
- `app.py`'de 5 `model_dump()` çağrısı (satır 615, 639, 732, 762).
- **Masaüstü de v1'e düşer.** 422 hata gövdelerinin biçimi değişir; `app.py:115`
  `_redact_validation_errors` ve `test_settings_route.py` dahil 422 gövdesine
  bakan testler gözden geçirilir.

**Çift-uyumluluk (v1/v2 aynı dosyada) reddedildi:** `models.py` bu projenin en
yoğun doğrulama noktası; iki API'yi aynı anda taşımak kalıcı bakım borcu üretir
ve masaüstü ile Android'in doğrulama davranışını sessizce ayrıştırır.

## Karar kuralı

> Yol A'ya **1 gün**. Wheel üretiliyor ve Chaquopy derlemesinde `import pydantic`
> geçiyorsa Yol A ile devam. Geçmiyorsa Yol B'ye geç ve kararı bu dosyaya
> gerekçesiyle yaz.

Doğrulama ikili ve hızlı: (1) wheel dosyası üretildi mi, (2) APK işindeki
`import pydantic` kapısı yeşil mi (`.github/workflows/build-android.yml`).

## Yol B'ye düşülürse

Bu dosyaya tarih + gerekçe eklenir, `android/pins.properties`'teki
`pydanticCoreVersion` kaldırılır ve `build.gradle`'ın `pip` bloğu
`install "pydantic==1.10.22"` ile değiştirilir. Wheel workflow'u silinmez —
gelecekte v2'ye dönüş için hazır durur.
