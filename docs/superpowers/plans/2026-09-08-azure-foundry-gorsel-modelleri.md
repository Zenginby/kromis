# Azure Foundry Görsel Modelleri (MAI + FLUX.2) — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kullanıcının Azure kaynağında dağıtılmış beş görsel modelini (MAI-Image ×3, FLUX.2 ×2) kataloğa alıp üretim + düzenlemede gerçekten çalıştırmak — `azure_client.py`'ye HİÇ dokunmadan.

**Architecture:** İki yeni düz adaptör modülü (`azure_mai_client.py`, `azure_flux_client.py`) `providers._ADAPTERS`'e geç bağlamayla giriyor; tek yeni `Credential` (`azure_foundry`) anahtarı mevcut `AZURE_IMAGE_API_KEY`'e, adresi de `AZURE_IMAGE_BASE_URL`'ün HOSTundan türetilen bir tabloya düşüyor. Geometri tek alanda (`sizes` jetonu, `"1024x768"`) kalıyor; adaptör `x`'ten bölüp `width`/`height` int'lerine çeviriyor. Mevcut Azure yolu bayt bayt dokunulmuyor.

**Tech Stack:** Python 3 · FastAPI · pydantic v2 · httpx (tembel import) · dataclasses · pytest · klasik (ES module OLMAYAN) tarayıcı betikleri

**Spec:** [docs/superpowers/specs/2026-09-08-azure-foundry-gorsel-modelleri-design.md](../specs/2026-09-08-azure-foundry-gorsel-modelleri-design.md)

## Global Constraints

Her görevin gereksinimleri bu bölümü ÖRTÜK olarak içeriyor.

* **`azure_client.py` DOKUNULMUYOR.** Tek satır bile değişmiyor: `build_payload`'ın ürettiği sözlük `tests/test_azure_client.py`'de donmuş ve "kayıtlı Azure kullanıcısı için sıfır davranış değişikliği" güvencesi buna dayanıyor.
* **Yeni Python modülleri KÖKTE ve DÜZ.** Alt paket olamaz: `android/app/build.gradle` Chaquopy kaynak kümesini `include "*.py"` ile kuruyor, alt paket APK'ya girmez ve hata YALNIZ telefonda görünür. Mandal: `tests/test_android_packaging.py`.
* **Adaptörler `importlib` ile DEĞİL düz `import` ifadesiyle bağlanıyor** (fonksiyon içinde olabilir). `gpt-image-studio.spec`'in `hiddenimports=[]` değeri PyInstaller'ın statik analizine dayanıyor. Mandal: `tests/test_providers.py::test_adaptorler_STATIK_import_ediliyor`.
* **Adaptör sözleşmesi:** `generate(m, prompt, size, quality, n, *, client=None, credentials=None) -> list[bytes]` ve `edit(m, prompt, images, size, quality, n, *, client=None, credentials=None) -> list[bytes]`. `images`: sıralı `[(dosya_adı, png_baytları), ...]`, ilk görsel ana referans. Dönen değer ÇÖZÜLMÜŞ PNG BAYTLARI.
* **Kimlik TEMBEL çözülüyor** — adaptörün kendi istek fonksiyonunun İÇİNDE, `credstore.resolve(m.credential)` ile. Öne almak 104 testi düşürür (bkz. `providers._azure_generate` yorumu).
* **MAI geometri sınırı:** w,h ≥ **768** VE w·h ≤ **1.048.576**.
* **FLUX geometri sınırı:** ≤ **4 MP**.
* **MAI'de `quality` YOK, `n` YOK.** FLUX.2-pro'da `quality` YOK; FLUX.2-flex'te `steps` (≤50, varsayılan 50) + `guidance` (1.5–10, varsayılan 4.5).
* **Kredi çapası:** Azure `medium` = 8 kredi ≈ 0,04 USD (1 kredi ≈ 0,005 USD).
* **`models.MAX_IMAGES_PER_RUN` = 4**, `app.MAX_EDIT_IMAGES` = 4. Hiçbir model bunları aşamaz.
* **Yollar:** MAI → `/mai/v1/images/generations` · `/mai/v1/images/edits`. FLUX → `/providers/blackforestlabs/v1/<model-path>?api-version=preview` (`flux-2-pro` · `flux-2-flex`).
* **Host:** ikisi de `<kaynak>.services.ai.azure.com`. Tek `api-key` üç yüzeyde de geçiyor.
* **Yanıt şekli:** üçünde de `data[].b64_json`, senkron (yoklama YOK).
* **Yazı geleneği:** yorumlar ve kullanıcıya dönen metinler **Türkçe**; test işlev adları İngilizce cümleler. Yorum "ne yaptığını" değil **NEDEN öyle olduğunu** anlatır. Metin dosyası açan her çağrı `encoding` VERMEK ZORUNDA (`tests/test_encoding_contract.py`). Satır sonları LF.
* **CANLI ÇAĞRI YOK.** Adaptör testleri `FakeClient` dikişiyle, tıpkı `tests/test_azure_client_http.py` gibi.
* **Her commit graf dosyalarını İÇERİYOR.** `.py` ya da `static/` dosyası değişen her commit'te önce:
  ```bash
  python tools/graf_uret.py && python tools/graf_uret.py --kontrol
  ```
  (POSIX'te `python3`.) Mandal: `tests/test_graflar.py`.

## Spec'ten Bilinçli Sapmalar

Bunlar plan yazılırken kaynağa bakınca çıkan düzeltmeler; her biri gerekçesiyle uygulanacak ve ilgili görevde tekrar yazılı.

1. **`app.py`'de KOD DEĞİŞİKLİĞİ YOK.** Spec "ayarlar rotasında yeni alanın gidiş-dönüşü" diyor, ama `app.post_settings`'in adres döngüsü (app.py:1167-1181) `cred.url_field`/`cred.url_env` üzerinden KATALOGDAN türetiliyor — yeni alan kendiliğinden yazılıyor. Yorumunun verdiği söz bu. Sadece bir gidiş-dönüş TESTİ eklenecek.
2. **Mevcut görsel modeli sayısı BEŞ, altı değil** (`azure-gpt-image-2`, `openai-gpt-image-2`, `openai-gpt-image-1`, `gemini-nano-banana-2`, `gemini-nano-banana-pro`). Spec "altı girdi" diyor; not gözden geçirmesi bu beş girdiye uygulanacak.
3. **FLUX kalite jetonları ASCII:** `hizli` / `dengeli` / `detayli`. Spec `hızlı`/`detaylı` yazıyor, ama katalogdaki HER jeton bugün ASCII (`low`, `1K`, `720p`, tema jetonları) ve Türkçe metin `QUALITY_LABELS`'ta yaşıyor. Jeton `history.json`'a, `prefs.json`'a ve `ResultParams.quality`'ye yazılıyor — orada ASCII kalması deponun kurulu deseni.
4. **FLUX notları 8/10 referans SÖZÜ VERMİYOR.** Spec'in not tablosu "8 referansa kadar düzenleme" / "10 referans" diyor, ama aynı spec ilk turu `app.MAX_EDIT_IMAGES` (4) tavanında bırakıyor ve `max_n=1`. Uygulamanın yapmadığı bir şeyi seçicide vaat etmek bu deponun yasakladığı sessiz sapmanın ta kendisi; notlar gerçek yeteneğe göre yazıldı.
5. **MAI notlarına "Önizleme." ekleniyor** — spec'in 4. riski bunu şart koşuyor ("notta yazılı, kalkınca girdi silinir"), not tablosu yazmayı atlamış.
6. **Kimlik başlığı `api-key`.** Spec başlık adını ölçmemiş; "aynı `api-key` üç yüzeyde de geçiyor" cümlesindeki adı ve `services.ai.azure.com`'un kendi geleneğini izliyoruz. `Authorization: Bearer` tek satır uzakta ve modül sabitiyle (`AUTH_HEADER`) tek yerde duruyor. Canlı ilk çağrı 401 dönerse değiştirilecek TEK yer o sabit. Bkz. Açık Kalemler.
7. **`max_refs` GÖRSEL düzenleme rotasında DOĞRULANMIYOR.** `app._collect_edit_refs` yalnız küresel `MAX_EDIT_IMAGES`e bakıyor (app.py:768); `spec.max_refs` kapısı yalnız VİDEO yolunda var (app.py:621). MAI ilk `max_refs=1` görsel modeli, yani kapı adaptörde kurulacak (Türkçe `ImageError` → 502). Rota kapısı eklemek bütün sağlayıcıları etkileyen yeni bir kapı olurdu; kapsam dışı, Açık Kalemler'de.
8. **`AZURE_FOUNDRY_BASE_URL` formdan TEMİZLENEMİYOR.** `app.post_settings`'in adres döngüsü `default_base_url`ü olmayan kimlikte boş değeri "dokunmadım" sayıyor (ölçülmüş bir veri kaybının düzeltmesi). Yani elle yazılmış bir Foundry adresini silip türetmeye dönmek `credentials.env`'i elle düzenlemek demek. Yanlış yazılan adres YENİSİYLE düzeltilebiliyor; kayıp yetenek yok. Açık Kalemler'de.

---

## Dosya Yapısı

| dosya | sorumluluk | görev |
| --- | --- | --- |
| `azure_mai_client.py` | **YENİ** — MAI teli: JSON üretim, multipart düzenleme, MAI'ye özgü Türkçe hata metinleri | 2 |
| `azure_flux_client.py` | **YENİ** — BFL teli: model-path eşlemesi, `input_image_N` referansları, flex'in `steps`/`guidance`ı, 422 çevirisi | 3 |
| `static/img/providers/microsoft.svg` | **YENİ** — MAI sağlayıcı işareti | 2 |
| `static/img/providers/blackforestlabs.svg` | **YENİ** — FLUX sağlayıcı işareti | 3 |
| `catalog.py` | 1 `Credential` (1) · `MAI_SIZES`/`FLUX_SIZES` + 5 `ImageModel` + 2 `PROVIDER_LOGOS` + 2 `PROVIDER_BRANDS` + `GEOMETRY_LABELS`/`QUALITY_LABELS` satırları (2, 3) · not gözden geçirmesi (4) | 1,2,3,4 |
| `credstore.py` | `azure_foundry` dalı + host türetme tablosu | 1 |
| `models.py` | `SettingsRequest.azure_foundry_base_url` | 1 |
| `providers.py` | `_ADAPTERS`'e 2 satır + 2 geç bağlama işlevi · `detail_of`'a `error.details[]` dalı | 2,3 |
| `static/index.html` | `#prov-azure` içine tek yeni `<input id="set-foundry-url">` + alan notu | 1 |
| `static/settings.js` | `saveSettings` gövdesine `azure_foundry_base_url` | 1 |
| `azure_client.py` | **DOKUNULMUYOR** | — |
| `app.py` | **KOD DEĞİŞİKLİĞİ YOK** (bkz. Sapma 1) | — |
| `tests/test_azure_mai_client.py` | **YENİ** | 2 |
| `tests/test_azure_flux_client.py` | **YENİ** | 3 |
| `tests/test_credstore.py` | türetme tablosu, anahtar düşmesi, tanınmayan host | 1 |
| `tests/test_settings_route.py` | yeni alanın gidiş-dönüşü | 1 |
| `tests/test_catalog.py` | piksel bütçesi, oran taşıma, FLUX jeton eşitliği, 5 girdinin bütünlüğü | 2,3 |
| `tests/test_providers.py` | `detail_of`un liste dalı | 3 |
| `docs/graflar/*` | her commit'te `tools/graf_uret.py` ile yenilenir | 1,2,3,4 |

Zaten var olan ve yeni satırları KENDİLİĞİNDEN kapsayan kapılar (bunlara dokunulmuyor, ama kırmızıya düşerlerse sebep yeni satırlardır): `test_providers.py::test_katalogdaki_her_saglayicinin_adaptoru_kayitli`, `test_provider_logos.py` (yedi iddia), `test_catalog.py::test_her_gorsel_modeli_tutarli_beyan_ediyor` · `test_varsayilan_jetonlar_MODELIN_kumesinde` · `test_beyan_edilen_her_jetonun_TURKCE_etiketi_var` · `test_katalogdaki_her_alan_adi_ayarlar_formunda_var` · `test_KATALOGDAKI_her_saglayicinin_MARKA_ADI_yazili`, `test_settings_route.py::test_dogrulama_hatasi_hicbir_alanin_degerini_yankilamiyor` (parametrik, yeni alanı eklendiği gün kapsıyor), `test_android_packaging.py`, `test_graflar.py`.

---

## Task 1: Kimlik — `azure_foundry` Credential, host türetmesi ve form alanı

**Files:**
- Modify: `catalog.py` (`CREDENTIALS` demetinin sonu, ~satır 271)
- Modify: `credstore.py` (modül başlığı altına türetme tablosu; `resolve` içine yeni dal, ~satır 60)
- Modify: `models.py:330-332` (`SettingsRequest`'in `*_base_url` bloğu)
- Modify: `static/index.html:1189-1201` (`#prov-azure` grubu)
- Modify: `static/settings.js:296-299` (`saveSettings` gövdesi)
- Test: `tests/test_credstore.py` (dosya sonuna yeni blok)
- Test: `tests/test_settings_route.py` (dosya sonuna yeni blok)

**Interfaces:**
- Consumes: `azure_client.read_env_values`, `azure_client.IMAGE_KEY` (`"AZURE_IMAGE_API_KEY"`), `azure_client.IMAGE_URL` (`"AZURE_IMAGE_BASE_URL"`), `azure_client.ImageError`, `catalog.credential`.
- Produces:
  - `catalog.Credential(id="azure_foundry", label="Azure AI Foundry · MAI ve FLUX", key_env="AZURE_FOUNDRY_API_KEY", url_env="AZURE_FOUNDRY_BASE_URL", secret_field=None, url_field="azure_foundry_base_url")`
  - `credstore.derive_foundry_base_url(image_base_url: str) -> str` — tanınmayan hostta `""`.
  - `credstore.resolve("azure_foundry") -> tuple[str, str]` — `(key, base_url)`; eksikse Türkçe `ac.ImageError`.
  - `models.SettingsRequest.azure_foundry_base_url: str | None`
  - DOM: `#set-foundry-url`

- [ ] **Step 1: `catalog.CREDENTIALS`'a `azure_foundry` girdisini ekle**

`catalog.py`'de `anthropic` girdisinden SONRA, `)` kapanışından önce:

```python
    # MAI ve FLUX aynı Azure kaynağında ama BAŞKA bir hostta yaşıyor
    # (`<kaynak>.services.ai.azure.com`) ve `/openai/v1` onları SERVİS
    # ETMİYOR: şema doğrulamasını geçen istek "Model not supported with
    # Responses API" ile düşüyor. Sebep Entra sondasıyla kanıtlandı — iki
    # AYRI veri eylemi (`…/accounts/OpenAI/images/generations/action` ve
    # `…/accounts/MaaS/images/generations/action`). Yani bu modelleri
    # `azure_image` kimliğinin altına koymak, bu dosyanın uyardığı
    # "arayüzde seçilebilir bir 400"ün tam kendisi olurdu.
    #
    # `secret_field=None` ve bu `azure_chat`in duruşunun aynısı: anahtar
    # `AZURE_IMAGE_API_KEY`e DÜŞÜYOR (sonda tek anahtarın üç yüzeyde de
    # geçtiğini ölçtü), yani forma ikinci bir gizli alan eklemek kullanıcıya
    # aynı değeri iki kez yazdırmak olurdu. Forma giren TEK yeni alan
    # `azure_foundry_base_url` ve o gizli DEĞİL — yani
    # `app._redact_validation_errors`'ın katalogdan türettiği redaksiyon
    # kümesi değişmiyor.
    #
    # `default_base_url` YOK çünkü sabit bir adres yok: adres ya elle yazılıyor
    # ya da görselin adresinin HOSTundan türetiliyor
    # (bkz. credstore.derive_foundry_base_url).
    Credential(
        id="azure_foundry",
        label="Azure AI Foundry · MAI ve FLUX",
        key_env="AZURE_FOUNDRY_API_KEY",
        url_env="AZURE_FOUNDRY_BASE_URL",
        secret_field=None,
        url_field="azure_foundry_base_url",
    ),
```

- [ ] **Step 2: `models.SettingsRequest`'e adres alanını ekle**

`models.py`'de `anthropic_base_url` satırından SONRA:

```python
    # Azure AI Foundry (MAI + FLUX) KÖK adresi. GİZLİ DEĞİL ve boş
    # bırakılabilir: boşken `credstore` onu `AZURE_IMAGE_BASE_URL`ün HOSTundan
    # türetiyor (bkz. credstore.derive_foundry_base_url). Ayrı bir ANAHTAR
    # alanı YOK — aynı `AZURE_IMAGE_API_KEY` üç yüzeyde de geçiyor.
    azure_foundry_base_url: str | None = Field(default=None, max_length=500)
```

- [ ] **Step 3: Türetme tablosunun testini yaz (kırmızı)**

`tests/test_credstore.py` dosyasının SONUNA:

```python
# ── Azure AI Foundry (MAI + FLUX) ──────────────────────────────────────
#
# Bu bloğun ölçtüğü şey tek cümle: kullanıcıdan İKİNCİ bir anahtar ve İKİNCİ
# bir adres istemeden MAI/FLUX'a ulaşılabilmeli — ama tanınmayan bir hostta
# SESSİZCE yanlış bir adrese düşülmemeli.


@pytest.mark.parametrize("gorsel_adresi, beklenen", [
    ("https://ai-ornek-swedencentral.openai.azure.com/openai/v1/",
     "https://ai-ornek-swedencentral.services.ai.azure.com"),
    ("https://ai-ornek-swedencentral.cognitiveservices.azure.com/",
     "https://ai-ornek-swedencentral.services.ai.azure.com"),
    ("https://ai-ornek-swedencentral.services.ai.azure.com",
     "https://ai-ornek-swedencentral.services.ai.azure.com"),
])
def test_foundry_adresi_TANINAN_hostlardan_turetiliyor(gorsel_adresi, beklenen):
    """Türetme bir TABLO, dize ameliyatı DEĞİL.

    `replace("openai", "services.ai")` gibi bir dokunuş kaynak adında "openai"
    geçen her kurulumu bozardı (`my-openai-lab.openai.azure.com`). Tablo yalnız
    tanınan SON EKİ çeviriyor ve kaynak adına hiç dokunmuyor.
    """
    assert credstore.derive_foundry_base_url(gorsel_adresi) == beklenen


@pytest.mark.parametrize("gorsel_adresi", [
    "https://vekil.sirket.local/azure/openai/v1/",
    "https://openai.azure.com/openai/v1/",     # alt alan adı YOK
    "ai-ornek.openai.azure.com/openai/v1/",      # şema YOK
    "",
])
def test_TANINMAYAN_host_HIC_turetmiyor(gorsel_adresi):
    """Sessiz düşme YOK: yanlış hosta atılan istek 404 döner ve sebebi
    kullanıcının hiçbir yerde okumadığı bir şey olur."""
    assert credstore.derive_foundry_base_url(gorsel_adresi) == ""


def test_foundry_anahtari_GORSELIN_anahtarina_dusuyor(env):
    """Sonda tek anahtarın üç yüzeyde de geçtiğini ölçtü (`azure_chat`in
    ikizi). İkinci bir anahtar istemek, aynı değeri iki kez yazdırmak olurdu."""
    ac.save_credentials("PAYLASILAN", "https://ai-ornek.openai.azure.com/openai/v1/")

    key, url = credstore.resolve("azure_foundry")
    assert key == "PAYLASILAN"
    assert url == "https://ai-ornek.services.ai.azure.com"
    assert credstore.is_configured("azure_foundry") is True


def test_foundry_nun_KENDI_anahtari_gorseli_eziyor(env):
    """Ayrı bir kaynak/anahtar kullanan kurulum forma alan eklemeden mümkün
    olmalı (`azure_chat`in aynı davranışı)."""
    ac.save_credentials("GORSEL", "https://ai-ornek.openai.azure.com/openai/v1/")
    ac.save_env({"AZURE_FOUNDRY_API_KEY": "FOUNDRY"})

    assert credstore.resolve("azure_foundry")[0] == "FOUNDRY"


def test_ELLE_yazilan_foundry_adresi_turetmeyi_eziyor(env):
    ac.save_credentials("K", "https://ai-ornek.openai.azure.com/openai/v1/")
    ac.save_env({"AZURE_FOUNDRY_BASE_URL": "https://ozel.ornek/foundry"})

    assert credstore.resolve("azure_foundry")[1] == "https://ozel.ornek/foundry"


def test_TANINMAYAN_hostta_hata_ALAN_ADINI_soyluyor(env):
    """Çıkışı olmayan bir hata olmamalı: mesaj hangi env değişkenini
    doldurmak gerektiğini ADIYLA söylemeli."""
    ac.save_credentials("K", "https://vekil.sirket.local/azure/openai/v1/")

    with pytest.raises(ac.ImageError) as exc:
        credstore.resolve("azure_foundry")

    mesaj = str(exc.value)
    assert "AZURE_FOUNDRY_BASE_URL" in mesaj
    assert credstore.is_configured("azure_foundry") is False


def test_anahtarsiz_kurulumda_foundry_KAPALI(env):
    """Adres türetilse bile anahtar yoksa model seçilebilir olmamalı."""
    ac.save_env({"AZURE_IMAGE_BASE_URL": "https://ai-ornek.openai.azure.com/openai/v1/"})

    assert credstore.is_configured("azure_foundry") is False
```

- [ ] **Step 4: Testleri koş, kırmızı olduklarını gör**

Run: `python -m pytest tests/test_credstore.py -q`
Expected: FAIL — `AttributeError: module 'credstore' has no attribute 'derive_foundry_base_url'`

- [ ] **Step 5: `credstore.py`'ye türetme tablosunu ve `azure_foundry` dalını ekle**

Modül başındaki import bloğunu şöyle yap (`urlsplit` MODÜL DÜZEYİNDE: stdlib, PyInstaller'ın statik analizi görüyor, `hiddenimports=[]` korunuyor):

```python
from __future__ import annotations

from urllib.parse import urlsplit

import azure_client as ac
import catalog
```

`_values` tanımından SONRA, `resolve`'dan ÖNCE:

```python
# ── Azure AI Foundry adresinin TÜRETİLMESİ ─────────────────────────────
#
# MAI ve FLUX dağıtımları `<kaynak>.services.ai.azure.com` üzerinde duruyor;
# uygulamanın bildiği Azure adresi ise `<kaynak>.openai.azure.com`. Sonda
# ikisinin AYNI anahtarla çalıştığını ölçtü, yani kullanıcıdan ikinci bir
# anahtar istemek gereksiz — değişen tek şey HOST.
#
# TÜRETME BİR TABLO, DİZE AMELİYATI DEĞİL: `replace("openai", "services.ai")`
# gibi bir dokunuş kaynak adında "openai" geçen her kurulumu bozardı
# (`my-openai-lab.openai.azure.com`). Tablo yalnız TANINAN son ekleri
# çeviriyor; tanınmayan bir host (vekil, özel alan adı) HİÇ türetmiyor ve
# `resolve` Türkçe bir hatayla `AZURE_FOUNDRY_BASE_URL`ü ADIYLA istiyor.
# Sessiz düşme YOK: yanlış hosta atılan istek 404 döner ve sebebi kullanıcının
# hiçbir yerde okumadığı bir şey olur — bu modülün var olma sebebinin tam
# tersi. Mandal: tests/test_credstore.py.
_FOUNDRY_HOST = "services.ai.azure.com"
_FOUNDRY_SOURCES: tuple[str, ...] = (
    "openai.azure.com",
    "cognitiveservices.azure.com",
    _FOUNDRY_HOST,
)


def derive_foundry_base_url(image_base_url: str) -> str:
    """`AZURE_IMAGE_BASE_URL`ün HOSTundan Foundry KÖK adresi; tanınmazsa "".

    YOL ve SORGU BİLEREK DÜŞÜYOR: görsel adresi `/openai/v1/` ile bitiyor,
    Foundry yolları ise adaptörlerin kendi sabitleri (`/mai/v1/…`,
    `/providers/blackforestlabs/v1/…`). Kök adresi döndürmek o iki sabitin
    TEK yerde kalmasını sağlıyor — burada birleştirilse yol bilgisi iki
    dosyada birden yaşardı.
    """
    host = (urlsplit(image_base_url.strip()).hostname or "").lower()
    for son in _FOUNDRY_SOURCES:
        if host.endswith("." + son):
            kaynak = host[: -len(son) - 1]
            return f"https://{kaynak}.{_FOUNDRY_HOST}"
    return ""
```

`resolve` içinde, `azure_chat` dalından SONRA ve genel `values = _values(env_path)` satırından ÖNCE:

```python
    if cred_id == "azure_foundry":
        # `azure_chat` dalının İKİZİ ve aynı ölçülmüş olguya dayanıyor: tek
        # anahtar üç yüzeyde de geçiyor (Azure OpenAI, MAI, FLUX).
        #
        # ADRES İKİ KADEMELİ ve sıra bağlayıcı: elle yazılan
        # `AZURE_FOUNDRY_BASE_URL` KAZANIYOR (vekil ya da ayrı bir kaynak
        # kullanan kurulum), boşsa görselin adresinden türetiliyor. Tersi
        # olsaydı kullanıcının yazdığı adres sessizce yok sayılırdı.
        values = _values(env_path)
        key = values.get(cred.key_env) or values.get(ac.IMAGE_KEY, "")
        url = (values.get(cred.url_env, "").strip()
               or derive_foundry_base_url(values.get(ac.IMAGE_URL, "")))
        if not key:
            raise ac.ImageError(
                f"{cred.label} anahtarı yok: Ayarlar'dan Azure API anahtarını "
                f"kaydet (ortam değişkeni: {cred.key_env} ya da {ac.IMAGE_KEY}).")
        if not url:
            raise ac.ImageError(
                f"{cred.label} adresi çözülemedi: Azure adresin tanınan bir "
                f"Foundry hostu değil. Ayarlar'daki Foundry adresi alanına "
                f"https://<kaynak>.{_FOUNDRY_HOST} yaz "
                f"(ortam değişkeni: {cred.url_env}).")
        return key, url
```

- [ ] **Step 6: Testleri koş, yeşil olduklarını gör**

Run: `python -m pytest tests/test_credstore.py tests/test_catalog.py -q`
Expected: PASS (tümü). `test_catalog.py` de yeşil olmalı — `test_katalogdaki_her_alan_adi_ayarlar_formunda_var` yeni `url_field`ı `SettingsRequest`te buluyor, `test_adressiz_kimligin_varsayilan_adresi_var` ise `azure`la başlayan kimlikleri atlıyor.

- [ ] **Step 7: Ayarlar rotasının gidiş-dönüş testini yaz (kırmızı)**

`tests/test_settings_route.py` dosyasının SONUNA:

```python
# ── Azure AI Foundry adresi (MAI + FLUX) ───────────────────────────────


def test_foundry_adresi_gidip_geliyor(client):
    """`post_settings`in adres döngüsü KATALOGDAN türetiliyor, elle
    sayılmıyor — yani yeni bir `url_field` rotada kod değişikliği İSTEMİYOR.

    Bu test o sözü ölçüyor: söz tutulmazsa alan sessizce hiç yazılmaz,
    kullanıcı "kaydettim" sanır ve üretim "adres çözülemedi" der.
    """
    import credstore

    r = client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ai-ornek.openai.azure.com/openai/v1/",
        "azure_foundry_base_url": "https://ozel.ornek/foundry"})

    assert r.status_code == 200, r.text
    assert credstore.resolve("azure_foundry")[1] == "https://ozel.ornek/foundry"


def test_foundry_adresi_YOKKEN_gorselin_adresinden_turetiliyor(client):
    """Kullanıcı hiçbir şey yazmadan MAI/FLUX çalışmalı: forma yeni bir
    ZORUNLU alan eklemek, bugün Azure'ı kurulu olan herkesi yeniden
    yapılandırmaya zorlamak olurdu."""
    import credstore

    client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ai-ornek.openai.azure.com/openai/v1/"})

    assert credstore.resolve("azure_foundry") == (
        "K", "https://ai-ornek.services.ai.azure.com")


def test_SEMASIZ_foundry_adresi_reddediliyor(client):
    """Adres kapısı (`ac.check_base_url`) katalog döngüsünde duruyor: şemasız
    bir yapıştırma 200 almamalı, hata ilk üretimde "bağlanılamadı" kılığında
    görünmemeli."""
    r = client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ai-ornek.openai.azure.com/openai/v1/",
        "azure_foundry_base_url": "ai-ornek.services.ai.azure.com"})

    assert r.status_code == 422


def test_BOS_foundry_adresi_yazilmis_degeri_KORUYOR(client):
    """`default_base_url`ü olmayan kimlikte boş adres "varsayılana dön" değil
    "dokunmadım" demek (app.post_settings'in ölçülmüş veri kaybı düzeltmesi).

    İstemci alanı KOŞULSUZ gönderiyor, yani bu kural olmasa Foundry adresini
    yazan kullanıcı bir sonraki kayıtta onu kaybederdi.
    """
    import credstore

    client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ai-ornek.openai.azure.com/openai/v1/",
        "azure_foundry_base_url": "https://ozel.ornek/foundry"})

    client.post("/api/settings", json={"azure_foundry_base_url": ""})

    assert credstore.resolve("azure_foundry")[1] == "https://ozel.ornek/foundry"
```

- [ ] **Step 8: Testleri koş — üçü yeşil, biri kırmızı olmalı**

Run: `python -m pytest tests/test_settings_route.py -q`
Expected: PASS (tümü). Kırmızı gelirse sebep `catalog`/`models` adımlarından biridir; `app.py`'ye KOD eklenmemeli.

- [ ] **Step 9: `static/index.html`'e adres alanını ekle**

`#prov-azure` grubundaki `<p class="field-note">` bloğundan SONRA, `</div>` kapanışından ÖNCE:

```html
        <label for="set-foundry-url">Foundry adresi (MAI · FLUX)</label>
        <input id="set-foundry-url" type="url" autocomplete="off" spellcheck="false"
               placeholder="boş bırak: Endpoint'ten türetilir" />
        <p class="field-note">
          MAI ve FLUX modelleri aynı kaynakta ama başka bir hostta
          (<code>services.ai.azure.com</code>) duruyor. <strong>Boş bırakılırsa
          adres yukarıdaki Endpoint'ten türetilir</strong> ve anahtar da aynı
          kalır — yani çoğu kurulumda burada yapılacak bir şey yok. Yalnızca
          vekil arkasındaki ya da ayrı bir kaynaktaki dağıtımlar için doldur.
        </p>
```

Not: `#set-foundry-url` YENİ bir id ve `docs/flow-ui/id-defteri.md`'ye kayıt GEREKMİYOR — defter yalnız KALDIRILAN id'leri sayıyor, taban ise 152 id'lik donmuş bir anlık görüntü (bkz. `tests/test_id_contract.py::test_baseline_matches_frozen_commit`). Alan `saveSettings` içinde okunuyor, top-level bir bağ DEĞİL, yani `test_toplevel_baglar_htmlde_duruyor` da kapsamıyor.

- [ ] **Step 10: `static/settings.js`'te gövdeye alanı ekle**

`saveSettings` içindeki `JSON.stringify({...})` çağrısını şöyle yap:

```javascript
      body: JSON.stringify({ api_key, base_url,
                             chat_deployment: $("set-chat-deployment").value.trim(),
                             // Adres alanı KOŞULSUZ gidiyor, gizli alanlarla
                             // aynı gerekçeyle: sunucu "alan yok" ile "boş"
                             // arasında ayrım yapıyor ve boş değer
                             // `default_base_url`ü olmayan kimlikte
                             // "dokunmadım" demek (app.post_settings). Yani
                             // yazılmış bir Foundry adresi bir sonraki
                             // kayıtta silinmiyor.
                             azure_foundry_base_url: $("set-foundry-url").value.trim(),
                             openai_api_key: $("set-openai-key").value,
                             gemini_api_key: $("set-gemini-key").value }),
```

Alan GİZLİ DEĞİL, o yüzden `openSettings`te ve kayıttan sonra temizlenmiyor (`#set-chat-deployment`in duruşu).

- [ ] **Step 11: Ön yüz kapılarını ve tam takımı koş**

Run: `python -m pytest tests/test_id_contract.py tests/test_index.py tests/test_settings_route.py tests/test_credstore.py tests/test_catalog.py -q`
Expected: PASS

- [ ] **Step 12: Grafları yenile ve commit'le**

```bash
python tools/graf_uret.py && python tools/graf_uret.py --kontrol
```

```bash
git add catalog.py credstore.py models.py static/index.html static/settings.js tests/test_credstore.py tests/test_settings_route.py docs/graflar
git commit -m "feat(foundry): azure_foundry kimligi, host turetme tablosu ve adres alani

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: MAI — adaptör modülü, üç katalog girdisi ve Microsoft işareti

**Files:**
- Create: `azure_mai_client.py`
- Create: `static/img/providers/microsoft.svg`
- Modify: `catalog.py` (`MAI_SIZES` sabiti; `GEOMETRY_LABELS`'a 6 satır; `PROVIDER_LOGOS`+`PROVIDER_BRANDS`'e 1'er satır; `IMAGE_MODELS`'ın SONUNA 3 girdi)
- Modify: `providers.py` (`_mai_adapter` + `_ADAPTERS` satırı)
- Test: `tests/test_azure_mai_client.py` (yeni)
- Test: `tests/test_catalog.py` (MAI blokları)

**Interfaces:**
- Consumes (Task 1'den): `credstore.resolve("azure_foundry")`, `catalog.Credential` id `"azure_foundry"`.
- Consumes (mevcut): `providers.read_timeout_for(m, n) -> float`, `providers.detail_of(body) -> str`, `providers.is_content_policy(detail) -> bool`, `azure_client.ImageError`, `azure_client.request_timeout(read)`, `azure_client.transport_error_message(exc, timeout)`.
- Produces:
  - `azure_mai_client.AUTH_HEADER: str` (`"api-key"`)
  - `azure_mai_client.GENERATE_PATH` / `EDIT_PATH`
  - `azure_mai_client.split_size(token: str) -> tuple[int, int]`
  - `azure_mai_client.build_payload(prompt: str, size: str, *, api_model: str) -> dict`
  - `azure_mai_client.build_image_file(images) -> dict`
  - `azure_mai_client.decode_images(response_json: dict) -> list[bytes]`
  - `azure_mai_client.map_error(status_code: int, body: dict | list | None) -> str`
  - `azure_mai_client.generate(...)` / `azure_mai_client.edit(...)` — adaptör sözleşmesi
  - `catalog.MAI_SIZES: tuple[str, ...]`, `catalog.MAI_PIXEL_CAP: int`, `catalog.MAI_MIN_EDGE: int`
  - Katalog id'leri: `azure-mai-image-2-6`, `azure-mai-image-2-6-flash`, `azure-mai-image-2-5-pro`; provider anahtarı `azure-mai`

- [ ] **Step 1: `catalog.py`'ye MAI geometri kümesini ve etiketlerini ekle**

`ASPECT_RATIOS` tanımının yanına (`# ── Görsel modelleri ──` başlığından ÖNCE):

```python
# MAI'nin GEOMETRİ BÜTÇESİ — canlı ölçüldü: w,h ≥ 768 VE w·h ≤ 1.048.576.
#
# Jetonlar `gpt-image-2`den KOPYALANMIYOR ve sebep sert: `1024x1536` ile
# `1536x1024` 1.572.864 piksel eder, yani tavanı %50 aşar. Kopyalamak iki
# jetonu doğrudan hataya sokardı.
#
# BU LİSTE BİR KOLAYLIK DEĞİL, GÜVENLİK SINIRI. MAI hatalı bir `size`
# gönderildiğinde 400 DÖNMÜYOR, sessizce varsayılanla ÜRETİYOR — sondada
# ölçüldü: `size:"1x1"` yutuldu ve iki gerçek 1024×1024 görsel üretildi.
# Yani sağlayıcı artık bir doğrulama katmanı DEĞİL ve
# `models.check_capabilities` TEK kapı; buradaki bir hata kullanıcıya hata
# değil İSTEMEDİĞİ BOYUTTA BİR FATURA gösterir.
#
# Küme mevcut oranların HEPSİNİ karşılıyor (1:1, 4:3, 3:4, 3:2, 2:3, 16:9,
# 9:16), yani `gpt-image-2`den MAI'ye geçen kullanıcı "varsayılana düşüldü"
# uyarısı ALMIYOR (bkz. core.js `fillAxis`in ikinci kademesi).
#
# Mandal: tests/test_catalog.py::test_MAI_jetonlari_PIKSEL_butcesine_uyuyor.
MAI_MIN_EDGE = 768
MAI_PIXEL_CAP = 1_048_576
MAI_SIZES: tuple[str, ...] = (
    "1024x1024",   # 1.048.576 · 1:1
    "1024x768",    #   786.432 · 4:3
    "768x1024",    #   786.432 · 3:4
    "1248x832",    # 1.038.336 · 3:2
    "832x1248",    # 1.038.336 · 2:3
    "1365x768",    # 1.048.320 · 16:9
    "768x1365",    # 1.048.320 · 9:16
)
```

`GEOMETRY_LABELS` sözlüğünün SONUNA (`"21:9"` satırından sonra):

```python
    # MAI'nin bütçeye uyan jetonları (bkz. MAI_SIZES). `ratio` sütunu Azure ve
    # Gemini'nin oranlarıyla AYNI dizeleri veriyor — `fillAxis`in ikinci
    # kademesi model değiştirirken oranı böyle taşıyor. Glif YÖNÜ söylüyor:
    # ◼ kare, ▮ dikey, ▬ yatay.
    "1024x768": ("▬ 4:3", "4:3"),
    "768x1024": ("▮ 3:4", "3:4"),
    "1248x832": ("▬ 3:2", "3:2"),
    "832x1248": ("▮ 2:3", "2:3"),
    "1365x768": ("▬ 16:9", "16:9"),
    "768x1365": ("▮ 9:16", "9:16"),
```

`PROVIDER_LOGOS`'a: `"azure-mai": "microsoft.svg",`
`PROVIDER_BRANDS`'e: `"azure-mai": "Microsoft",`

- [ ] **Step 2: Katalog kapılarının testini yaz (kırmızı)**

`tests/test_catalog.py` dosyasının SONUNA:

```python
# ── Azure AI Foundry · MAI (v0.15) ─────────────────────────────────────


def test_MAI_jetonlari_PIKSEL_butcesine_uyuyor():
    """Bu testin ölçtüğü şey bir GÜVENLİK SINIRI, bir kolaylık değil.

    MAI hatalı bir `size` gönderildiğinde 400 DÖNMÜYOR, sessizce varsayılanla
    üretiyor — sondada ölçüldü (`size:"1x1"` yutuldu, iki gerçek görsel
    üretildi ve faturalandı). Yani sağlayıcı bir doğrulama katmanı değil;
    `models.check_capabilities` TEK kapı ve o da katalogdan besleniyor.
    Buradaki bir hata kullanıcıya hata değil, İSTEMEDİĞİ BOYUTTA BİR FATURA
    gösterir.
    """
    for jeton in catalog.MAI_SIZES:
        w, h = (int(p) for p in jeton.split("x"))
        assert w >= catalog.MAI_MIN_EDGE and h >= catalog.MAI_MIN_EDGE, (
            f"{jeton}: MAI kenarı {catalog.MAI_MIN_EDGE} pikselin altına inemiyor")
        assert w * h <= catalog.MAI_PIXEL_CAP, (
            f"{jeton}: {w * h} piksel, MAI tavanı {catalog.MAI_PIXEL_CAP}")


def test_MAI_jetonlari_AZURE_nun_uc_oranini_KARSILIYOR():
    """`test_gemini_oranlari_…`ın ikizi ve aynı gerekçesi: model değiştirmek
    ORANI TAŞIMALI, sebepsiz bir "varsayılana düşüldü" uyarısı basmamalı."""
    azure = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    azure_oranlari = {catalog.geometry_of(s)[1] for s in azure.sizes}
    mai_oranlari = {catalog.geometry_of(s)[1] for s in catalog.MAI_SIZES}

    assert azure_oranlari <= mai_oranlari, (
        "Azure'dan MAI'ye geçişte karşılığı olmayan oran: "
        f"{sorted(azure_oranlari - mai_oranlari)}")


def test_MAI_girdileri_jetonlari_PAYLASIYOR():
    """Üç girdiye elle üç kez yazmak, birine jeton ekleyip ötekini unutmanın
    kapısı olurdu (`ASPECT_RATIOS`in paylaşılma gerekçesi)."""
    mai = [m for m in catalog.IMAGE_MODELS if m.provider == "azure-mai"]
    assert len(mai) == 3, "katalogda üç MAI girdisi olmalı"
    for m in mai:
        assert m.sizes is catalog.MAI_SIZES, (
            f"{m.id}: jetonları kopyalamış, MAI_SIZES'ı paylaşmıyor")
        assert m.credential == "azure_foundry", m.credential
        # Adet TEL ÜZERİNDE YOK: MAI'de `n` parametresi hiç mevcut değil,
        # yani adet başına AYRI istek atılıyor (bkz. karar 5).
        assert m.images_per_request == 1
        # Kalite ekseni YOK: tek sentetik jeton + gizli knob (karar 4).
        assert m.quality_hidden is True
        # Düzenleme TEK referans alıyor (multipart `image`, tekrar YOK).
        assert m.supports_edit is True and m.max_refs == 1
        assert m.note and "Önizleme" in m.note, (
            f"{m.id}: MAI ailesinin üçü de önizleme; notta yazılı olmalı "
            "(bkz. openai-gpt-image-1'in duruşu)")
```

- [ ] **Step 3: Testleri koş, kırmızı olduklarını gör**

Run: `python -m pytest tests/test_catalog.py -q -k "MAI"`
Expected: FAIL — `test_MAI_girdileri_jetonlari_PAYLASIYOR` "katalogda üç MAI girdisi olmalı" diyor (piksel bütçesi ve oran testleri Step 1 sayesinde zaten yeşil).

- [ ] **Step 4: `azure_mai_client.py`'yi yaz**

```python
"""Azure AI Foundry · MAI-Image ailesi — `/mai/v1/images/{generations,edits}`.

`azure_client.py`'nin İKİZİ DEĞİL, KARDEŞİ: tel formatı gerçekten farklı ve
fark tek bir alanda değil ÜÇ eksende birden —

  • host `<kaynak>.services.ai.azure.com`, `/openai/v1` DEĞİL;
  • geometri `size:"1024x1024"` değil `width`+`height` (int);
  • `quality` ve `n` parametreleri HİÇ YOK.

`/openai/v1`in bu modelleri servis ETMEDİĞİ kanıtlandı: şema doğrulamasını
geçen istek "Model not supported with Responses API" ile düşüyor ve Entra
sondası sebebi gösterdi — iki AYRI veri eylemi
(`…/accounts/OpenAI/images/generations/action` ve
`…/accounts/MaaS/images/generations/action`). Yani bu modelleri
`gpt-image-2`nin ikizi olarak beyan etmek, `catalog.py`nin uyardığı
"arayüzde seçilebilir bir 400"ün tam kendisi olurdu.

BU DOSYANIN EN PAHALI DERSİ, ve her satırını okuyan bunu bilmeli:
**MAI TANIMADIĞI ALANI SESSİZCE YUTUYOR.** Sondada `size:"1x1"` gönderildi;
MAI'nin `size` diye bir parametresi OLMADIĞI için alan yok sayıldı, istek
reddedilmedi ve İKİ GERÇEK GÖRSEL üretilip faturalandı (1024×1024). Sonuç:
sağlayıcı artık bir doğrulama katmanı DEĞİL. `models.check_capabilities` tek
kapı, `catalog.MAI_SIZES` de o kapının verisi — oradaki bir hata kullanıcıya
hata değil, istemediği boyutta bir fatura gösterir.

`azure_client.py` BU TURDA HİÇ DÜZENLENMİYOR: `build_payload`ın ürettiği tam
sözlük tests/test_azure_client.py'de donmuş durumda ve "kayıtlı Azure
kullanıcısı için sıfır davranış değişikliği" güvencesi buna dayanıyor.

DOSYA KÖKTE ve DÜZ olmak ZORUNDA — bir `azure_foundry/` alt paketi olamaz.
`android/app/build.gradle` Chaquopy kaynak kümesini `include "*.py"` ile
kuruyor, yani APK'ya YALNIZ kök düzeyindeki .py dosyaları giriyor: alt paket
masaüstünde çalışır, telefonda `ModuleNotFoundError` verir. Mandal:
tests/test_android_packaging.py.

CANLI DOĞRULAMANIN SINIRI (2026-09-08): yol, host, geometri alanları, `n`/
`quality`nin YOKLUĞU ve hata gövdesinin şekli kullanıcının KENDİ kaynağına
atılan gerçek isteklerle ölçüldü. 200 yanıtının şekli de görüldü
(`data[].b64_json` + `usage.num_output_tokens = 1024`). ÖLÇÜLMEYEN taraf:
kimlik BAŞLIĞININ adı (bkz. AUTH_HEADER) ve düzenleme ucunun multipart alan
adları — ikisi de planın Açık Kalemler'inde yazılı.
"""
from __future__ import annotations

import base64

import azure_client as ac
import catalog
import credstore
import providers

GENERATE_PATH = "/mai/v1/images/generations"
EDIT_PATH = "/mai/v1/images/edits"

# KİMLİK BAŞLIĞI TEK YERDE ve bu bilinçli: sonda anahtarın üç yüzeyde de
# geçtiğini ölçtü ama BAŞLIĞIN ADINI ölçmedi. `services.ai.azure.com`un kendi
# geleneği `api-key`; `Authorization: Bearer` (bu deponun Azure OpenAI yolunda
# kullandığı) da kabul edilebiliyor. Canlı ilk çağrı 401 dönerse değiştirilecek
# TEK yer bu sabit — iki fonksiyonda birden yazılı olsaydı biri değişip öteki
# kalabilirdi. Mandal: tests/test_azure_mai_client.py.
AUTH_HEADER = "api-key"


def split_size(token: str) -> tuple[int, int]:
    """`"1024x768"` → `(1024, 768)`. Bozuk jetonda Türkçe `ImageError`.

    ÇEVİRİM ADAPTÖRDE, katalogda DEĞİL: `sizes` demeti jetonları STRING olarak
    taşımaya devam ediyor, yani `ResultParams.size`, `history.json` kayıtları,
    `storage.save` ve core.js'in oran-taşıma kademesi HİÇ değişmiyor. Bu,
    `ImageModel.sizes` docstring'inde Gemini için verilen kararın aynısı —
    "jeton, piksel değil".

    Ham `ValueError` BIRAKILMIYOR: bayat bir istemci ya da Prompt Yönetmeni'nin
    önerdiği bir jeton buraya ulaşabiliyor ve o durumun cevabı ham 500 değil,
    502'ye çevrilebilir Türkçe bir hata olmalı.
    """
    genislik, _, yukseklik = token.partition("x")
    try:
        return int(genislik), int(yukseklik)
    except ValueError:
        raise ac.ImageError(
            f"MAI geometri jetonunu anlamadı: {token} "
            "(beklenen biçim: GENİŞLİKxYÜKSEKLİK).") from None


def build_payload(prompt: str, size: str, *, api_model: str) -> dict:
    """MAI üretim gövdesi. `quality` ve `n` BİLEREK YOK.

    İkisi de MAI'de mevcut DEĞİL ve göndermek zararsız da değil: tanınmayan
    alan sessizce yutuluyor (bkz. dosya başlığı), yani "gönderdim, demek ki
    uygulandı" varsayımı yanlış bir faturaya dönüşür. Beyan edilmeyen alan
    hiç gönderilmiyor.
    """
    w, h = split_size(size)
    return {"model": api_model, "prompt": prompt, "width": w, "height": h}


def build_image_file(images):
    """MAI düzenlemesi TEK görsel alıyor: `image` alanı, tekrarlanan `image[]` YOK.

    `ac.build_image_files` KULLANILMIYOR ve bu bilinçli: o fonksiyon çoklu
    görselde `image[]` tekrarına geçiyor (OpenAI/Azure'ın canlı doğrulanmış
    teli) ve MAI o alanı tanımıyor — tanınmayan alan da SESSİZCE yutuluyor,
    yani kullanıcı gönderdiği üç referansın yok sayıldığını hiçbir yerde
    okumazdı.

    KAPI BURADA olmak ZORUNDA: görsel düzenleme rotası (`app._collect_edit_refs`)
    yalnız küresel `MAX_EDIT_IMAGES`e bakıyor, model başına `max_refs`e
    BAKMIYOR — o kapı bugün yalnız video yolunda var. MAI, `max_refs=1` beyan
    eden ilk GÖRSEL modeli, yani ikinci kapı olmadan sessiz sapma gerçek
    olurdu.
    """
    if not images:
        raise ac.ImageError("En az bir görsel gerekli.")
    if len(images) > 1:
        raise ac.ImageError(
            "MAI düzenlemede tek referans görsel alıyor; "
            f"{len(images)} görsel gönderildi. Ek referansları kaldır ya da "
            "gpt-image-2'ye geç.")
    filename, data = images[0]
    return {"image": (filename, data, "image/png")}


def decode_images(response_json: dict) -> list[bytes]:
    """`data[].b64_json` → PNG baytları. Beklenmeyen şekil ham `KeyError` DEĞİL.

    `ac.decode_images`ın koşulsuz `data[].b64_json` varsayımı Azure'ın özel
    meselesi ve orada kalıyor (bkz. providers.py'nin başlığı). Buradaki kopya
    aynı şekli okuyor ama SARMALIYOR: sarmalanmayan bir `KeyError`
    `app.py`nin `except ac.AzureImageError` süzgecinden GEÇER, ham 500 olur ve
    kullanıcı beklemenin sonunda yalnızca "Hata (500)" görür.
    """
    data = response_json.get("data")
    if not isinstance(data, list) or not data:
        raise ac.ImageError("MAI yanıtı boş döndü (data yok). Tekrar deneyin.")
    out: list[bytes] = []
    for item in data:
        b64 = item.get("b64_json") if isinstance(item, dict) else None
        if not b64:
            raise ac.ImageError(
                "MAI yanıtı beklenmedik biçimde geldi (b64_json yok).")
        out.append(base64.b64decode(b64))
    return out


def map_error(status_code: int, body: dict | list | None) -> str:
    """HTTP durumunu Türkçe mesaja çevirir. ŞEKİL paylaşılıyor, METİN paylaşılmıyor.

    `providers.detail_of` gövde şeklini çözüyor — MAI'nin gövdesi
    (`error.code` + `message` + `details`) OpenAI şekline yeterince yakın.
    `azure_client.map_error`ın mantığı buraya KOPYALANMIYOR ve ORTAK bir
    yardımcıya da ÇIKARILMIYOR: iki satırlık bir zincir, paylaşılan bir
    soyutlamanın iki sağlayıcıyı birbirine kaynatmasından ucuz (bkz. karar 8).

    429 AYRI bir dal ve gerekçesi ölçülmüş: Foundry dağıtımlarının kapasitesi
    düşük ve sonda sırasında `RateLimitReached` birkaç kez görüldü. Ham bir
    502 kullanıcıya "bozuk" der; doğru cevap "kota doldu, biraz bekle".
    """
    detail = providers.detail_of(body)
    if status_code == 401:
        return ("Azure AI Foundry yetkilendirme hatası (401): api-key geçersiz "
                "veya bu kaynağa ait değil. Ayarlar'dan yeniden kaydet.")
    if status_code == 404:
        return ("MAI dağıtımı bulunamadı (404): bu model Foundry'de dağıtılmamış "
                "olabilir, ya da Ayarlar'daki Foundry adresi başka bir kaynağı "
                "gösteriyor." + (f" {detail}" if detail else ""))
    if status_code == 429:
        return ("MAI kotası doldu (429): biraz bekleyip tekrar deneyin. "
                "Adedi düşürmek de yardımcı olur.")
    if providers.is_content_policy(detail):
        return "İçerik politikası reddi: prompt MAI tarafından engellendi."
    return (f"MAI isteği başarısız (HTTP {status_code})."
            + (f" {detail}" if detail else ""))


def _post(endpoint: str, key: str, *, client, read: float,
          json=None, data=None, files=None) -> dict:
    """Ortak POST + hata çevirisi; `generate` ve `edit` PAYLAŞIYOR.

    `client` sözleşmede KORUNUYOR (adaptör sözleşmesinin `client=` anahtarı):
    testler `FakeClient` geçiriyor ve döngülü üretimde tek istemciyi yeniden
    kullanmak bağlantı başına TLS el sıkışmasını da ortadan kaldırıyor.

    `Content-Type` YALNIZ JSON gövdede: multipart'ta sınırı istemci koyuyor ve
    elle yazmak gövdeyi bozar.
    """
    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    headers = {AUTH_HEADER: key}
    if json is not None:
        headers["Content-Type"] = "application/json"
    try:
        resp = client.post(endpoint, headers=headers, json=json, data=data,
                           files=files, timeout=ac.request_timeout(read))
    except httpx.TransportError as exc:
        # Mesaj `azure_client`tan geliyor, sağlayıcı adı düzeltiliyor: "Azure'a
        # bağlanılamadı" diyen bir metin kullanıcıyı Endpoint alanını
        # kurcalamaya iter, oysa çözülemeyen adres Foundry'nin. ÜCRET UYARISI
        # korunuyor.
        raise ac.ImageError(
            ac.transport_error_message(exc, read).replace("Azure", "Foundry")) from exc
    finally:
        if owns:
            client.close()

    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = None
        raise ac.ImageError(map_error(resp.status_code, body))
    return resp.json()


def _uret(m: catalog.ImageModel, prompt: str, size: str, n: int, images,
          *, client, credentials) -> list[bytes]:
    """`generate` ve `edit`in PAYLAŞILAN gövdesi — tek fark `images`.

    KİMLİK BURADA, TEMBEL çözülüyor (`credstore.resolve`): erken çözüm
    `providers._azure_generate`in yorumunda anlatılan 104 testlik dersin
    tekrarı olurdu — rota testleri adaptörü monkeypatch'liyor ve kimliği HİÇ
    yapılandırmıyor.

    DÖNGÜ ve ZAMAN AŞIMI: MAI'de `n` YOK, yani n görsel n istek.
    `providers.read_timeout_for` `images_per_request=1` gördüğü için adetle
    BÜYÜMEYEN tek isteğin süresini döndürüyor; döngünün toplamı da
    `providers.total_budget`e eşit oluyor. Karışsa n=4'te her isteğe 540
    saniye verilirdi: 36 dakikalık en kötü hâl.

    HATA KISMİ SONUÇ BIRAKMIYOR: ikinci istek düşerse birincinin görseli de
    kaybediliyor ve 502 dönüyor. Alternatif (eldekini döndürüp sessizce eksik
    teslim etmek) bu deponun "sessiz sapma yasak" duruşuna aykırı.

    `out[:n]` bir süsleme değil: `decode_images` tek yanıttan birden çok görsel
    döndürebiliyor ve fazlalık `models.MAX_IMAGES_PER_RUN` (4) ile
    `ChatMessage.image_ids`in `max_length=4`ünde patlar — hem de görseller
    ÜRETİLDİKTEN ve ücret ödendikten sonra.
    """
    key, base_url = (credentials if credentials is not None
                     else credstore.resolve(m.credential))
    read = providers.read_timeout_for(m, n)
    kok = base_url.rstrip("/")
    w, h = split_size(size)

    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        out: list[bytes] = []
        while len(out) < n:
            if images is None:
                govde = _post(kok + GENERATE_PATH, key, client=client, read=read,
                              json=build_payload(prompt, size,
                                                 api_model=m.wire_model))
            else:
                # Multipart alanları STRING: `azure_client.edit`in `"n": str(n)`
                # duruşunun aynısı — httpx sayıyı `data=` içinde kabul etmiyor.
                govde = _post(kok + EDIT_PATH, key, client=client, read=read,
                              data={"model": m.wire_model, "prompt": prompt,
                                    "width": str(w), "height": str(h)},
                              files=build_image_file(images))
            out.extend(decode_images(govde))
        return out[:n]
    finally:
        if owns:
            client.close()


def generate(m: catalog.ImageModel, prompt: str, size: str, quality: str, n: int,
             *, client=None, credentials=None) -> list[bytes]:
    """`quality` BİLEREK YOK SAYILIYOR: MAI'nin kalite parametresi yok.

    İmzada duruyor çünkü adaptör SÖZLEŞMESİNİN parçası (bkz. providers.py'nin
    başlığı) ve katalog tek sentetik jeton + `quality_hidden=True` beyan
    ediyor — boş `qualities` `ResultParams`ta 422 demekti, yani o modelle
    üretilmiş bir oturumun bir daha kaydedilememesi.
    """
    return _uret(m, prompt, size, n, None,
                 client=client, credentials=credentials)


def edit(m: catalog.ImageModel, prompt: str, images, size: str, quality: str,
         n: int, *, client=None, credentials=None) -> list[bytes]:
    """`images`: sıralı [(dosya_adı, png_baytları), ...] — MAI yalnız İLKİNİ alır
    ve fazlası SESSİZCE düşmez, `build_image_file` yüksek sesle reddeder."""
    return _uret(m, prompt, size, n, images,
                 client=client, credentials=credentials)
```

- [ ] **Step 5: `providers.py`'ye MAI adaptörünü kaydet**

`_veo_adapter` tanımından SONRA:

```python
def _mai_adapter():
    """`_gemini_adapter`ın aynı gerekçesi: `azure_mai_client` bu modülü import
    ediyor (`read_timeout_for`, `detail_of`, `is_content_policy` için), yani
    modül düzeyinde import etmek DÖNGÜ olurdu. Düz `import` ifadesi, yalnız
    fonksiyon içinde — PyInstaller'ın statik analizi onu da görüyor, yani
    `hiddenimports=[]` korunuyor."""
    import azure_mai_client
    return (azure_mai_client.generate, azure_mai_client.edit)
```

`_ADAPTERS` sözlüğüne, `"gemini"` satırından sonra:

```python
    # Azure AI Foundry'nin İKİ AYRI teli, TEK anahtar altında: MAI ile FLUX
    # aynı hostta ve aynı `api-key` ile çalışıyor ama gövdeleri, yolları ve
    # hata şekilleri farklı. Tek bir `azure-foundry` anahtarı olsaydı iki tel
    # formatı bir modülde yaşardı, hata eşlemesi bulanıklaşırdı ve
    # `PROVIDER_LOGOS` tek anahtara düşerdi — oysa üretici GERÇEKTEN iki
    # (Microsoft ve Black Forest Labs).
    "azure-mai": _mai_adapter,
```

- [ ] **Step 6: Üç MAI katalog girdisini ekle**

`IMAGE_MODELS` demetinin SONUNA (gemini girdilerinden sonra, `)` kapanışından önce):

```python
    # ── Azure AI Foundry · MAI-Image (Microsoft) ────────────────────────
    #
    # ÜÇÜ DE ÖNİZLEME ve notlarında yazılı: ad ya da sözleşme haber vermeden
    # değişebilir. `openai-gpt-image-1` girdisinin duruşu benimseniyor —
    # kalktığı gün girdi SİLİNİR, çünkü katalogda kalan ölü bir girdi
    # arayüzde seçilebilir bir 404 demek (`openai-dall-e-3`ün ölçülmüş dersi).
    #
    # KREDİ ÇAPASI görsel tarafındakiyle AYNI: Azure `medium` = 8 kredi
    # ≈ 0,04 USD, yani 1 kredi ≈ 0,005 USD. MAI token bazlı faturalanıyor ve
    # sonda ölçüyü verdi: 1024×1024 görsel için `usage.num_output_tokens`
    # = 1024. 2.6 → 1024 tok × 38 USD/M = 0,0389 USD → 8 kredi;
    # 2.5-Pro → 1024 tok × 47 USD/M = 0,0481 USD → 10 kredi.
    # 2.6-Flash'ın yayınlanmış birim fiyatı DOĞRULANAMADI (Azure fiyat
    # sayfaları JS ile çiziliyor, tablo boş döndü) — 4 kredi GEÇİCİ.
    #
    # KABUL EDİLEN YAKLAŞIKLIK: `cost_for`un boyut ekseni yok, oysa MAI'de
    # token = piksel. Kredi VARSAYILAN boyuttaki maliyeti gösteriyor;
    # düzeltmek `cost_for`a üçüncü bir eksen eklemek demek ve bu turun
    # kapsamı dışında.
    #
    # `max_n=4`: MAI'de `n` parametresi HİÇ YOK, tavan
    # `models.MAX_IMAGES_PER_RUN`dan geliyor ve dört AYRI istek atılıyor.
    ImageModel(
        id="azure-mai-image-2-6",
        label="Microsoft · MAI-Image 2.6",
        provider="azure-mai",
        wire_model="MAI-Image-2.6",
        credential="azure_foundry",
        sizes=MAI_SIZES,
        default_size="1024x1024",
        # Kalite ekseni YOK (karar 4): tek sentetik jeton + gizli knob. Boş
        # bırakmak `ResultParams`ta 422 demekti, yani o modelle üretilmiş bir
        # oturumun BİR DAHA KAYDEDİLEMEMESİ.
        qualities=("standard",),
        quality_hidden=True,
        max_n=4,
        images_per_request=1,
        supports_edit=True,
        # Düzenleme ucu TEK görsel alıyor (canlı ölçüldü). `max_refs=1` beyan
        # eden ilk GÖRSEL modeli bu, yani ikinci kapı adaptörde
        # (`azure_mai_client.build_image_file`) — görsel düzenleme rotası
        # model başına `max_refs`e bakmıyor.
        max_refs=1,
        credits=8,
        note="Fotogerçekçi ürün ve portre işi; metin işlemede MAI'nin en "
             "iyisi. Önizleme.",
    ),
    ImageModel(
        id="azure-mai-image-2-6-flash",
        label="Microsoft · MAI-Image 2.6 Flash",
        provider="azure-mai",
        wire_model="MAI-Image-2.6-Flash",
        credential="azure_foundry",
        sizes=MAI_SIZES,
        default_size="1024x1024",
        qualities=("standard",),
        quality_hidden=True,
        max_n=4,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        # GEÇİCİ: birim fiyat doğrulanamadı, oran 2.6'nın yarısı varsayıldı.
        credits=4,
        note="2.6'nın hızlı ve ucuz kardeşi; taslak ve deneme turları için. "
             "Önizleme.",
    ),
    ImageModel(
        id="azure-mai-image-2-5-pro",
        label="Microsoft · MAI-Image 2.5 Pro",
        provider="azure-mai",
        wire_model="MAI-Image-2.5-Pro",
        credential="azure_foundry",
        sizes=MAI_SIZES,
        default_size="1024x1024",
        qualities=("standard",),
        quality_hidden=True,
        max_n=4,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        credits=10,
        note="Kalabalık sahnelerde nesne ve karakter tutarlılığı; pahalı. "
             "Önizleme.",
    ),
```

- [ ] **Step 7: `microsoft.svg`'yi yaz**

`static/img/providers/microsoft.svg` — kardeş dosyaların sözleşmesi: geçerli XML (**yorumda çift tire YASAK**, Türkçe harf de YOK), kökte `viewBox=`/`width=`/`height=`, `currentColor` YOK, `#e8eaed` VAR.

```xml
<!-- Microsoft (MAI-Image) · saglayici isareti.
     Kaynak: simple-icons · microsoft, lisans CC0-1.0. Marka adlari ve
     isaretleri sahiplerinin tescilli markalaridir; burada YALNIZCA hangi
     saglayicinin secili oldugunu gostermek icin kullaniliyor.

     TEK RENK ve renk DOSYADA sabit (fill), currentColor DEGIL: dosya <img> ile
     yukleniyor ve <img> icerigi sayfanin rengini miras almaz. Sabit deger
     tema katmanindaki fg (#e8eaed) ile ayni ve uygulamanin DORT temasi da
     koyu, yani tek varyant hepsinde okunuyor. Bir gun acik tema gelirse dogru
     yol mask-image + background: currentColor'a gecmek olur.

     DORT KARE TEK RENK: gercek isaret dort ayri renk tasiyor, ama bu dosya
     <img> ile yuklendigi icin tema rengiyle boyanmasi mumkun degil ve
     kardes dosyalarla ayni tek renk kurali gecerli. Silueti yine ayirt
     edici.

     DIKKAT: bu yorumda cift tire (XML'de yasak) ve Turkce harf YOK, ikisi de
     olcum sonucu. Ilk yazimda "fg" token'i cift tireyle yaziliydi; dosya
     gecerli XML olmaktan cikti, tarayici 200 alip HICBIR SEY cizmedi ve
     naturalWidth 0 kaldi. Sessiz kusur tam olarak buydu (bkz.
     tests/test_provider_logos.py). -->
<svg width="24" height="24" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#e8eaed"><title>Microsoft</title><path d="M11.4 24H0V12.6h11.4zM24 24H12.6V12.6H24zM11.4 11.4H0V0h11.4zM24 11.4H12.6V0H24z"/></svg>
```

- [ ] **Step 8: Katalog + sağlayıcı + işaret kapılarını koş**

Run: `python -m pytest tests/test_catalog.py tests/test_providers.py tests/test_provider_logos.py -q`
Expected: PASS

- [ ] **Step 9: MAI adaptörünün testini yaz (kırmızı bekleniyor)**

Create `tests/test_azure_mai_client.py`:

```python
"""azure_mai_client: MAI telinin şekli, döngü ve hata çevirisi.

Bu dosyanın en değerli iddiası tel formatının EKSİLERİ: `size`, `quality` ve
`n` gövdede BULUNMAMALI. MAI tanımadığı alanı 400 ile reddetmiyor, SESSİZCE
yutuyor (sondada `size:"1x1"` yutuldu ve iki gerçek görsel üretildi), yani
fazladan gönderilen bir alanın bedeli yanlış boyutlu bir fatura — ve o kusur
hiçbir yerde görünmüyor. Görülebilir tek yer burası.

CANLI ÇAĞRI YOK: `FakeClient` dikişi tests/test_azure_client_http.py'nin
aynısı, `client=` anahtarı da o yüzden adaptör sözleşmesinde duruyor.
"""
import base64

import pytest

import azure_client as ac
import azure_mai_client as mai
import catalog
import providers

MODEL = catalog.image_model("azure-mai-image-2-6")
FLASH = catalog.image_model("azure-mai-image-2-6-flash")
CREDS = ("FOUNDRYKEY", "https://ai-ornek.services.ai.azure.com")


class FakeResponse:
    def __init__(self, status_code, json_body=None):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        if self._json is None:
            raise ValueError("gövde JSON değil")
        return self._json


class FakeClient:
    """`httpx.Client` yerine geçen minimal sahte istemci.

    BÜTÜN çağrıları biriktiriyor (`calls`), yalnız sonuncusunu değil: tek bir
    `last_call` ile "n istek atıldı mı?" sorusu cevaplanamaz ve bu dosyanın
    döngü iddiası tam olarak onu ölçüyor (`gemini_client` testlerinin aynı
    ayrımı).
    """

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, headers=None, json=None, data=None, files=None,
             timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json,
                           "data": data, "files": files, "timeout": timeout})
        return (self._responses[len(self.calls) - 1]
                if len(self._responses) > 1 else self._responses[0])


def _ok(sayi=1):
    b64 = base64.b64encode(b"\x89PNG").decode()
    return FakeResponse(200, {"data": [{"b64_json": b64}] * sayi})


# ── Geometri: jeton → int ──────────────────────────────────────────────


@pytest.mark.parametrize("jeton, beklenen", [
    ("1024x1024", (1024, 1024)),
    ("1024x768", (1024, 768)),
    ("1365x768", (1365, 768)),
    ("768x1365", (768, 1365)),
])
def test_split_size_converts_the_token_to_two_ints(jeton, beklenen):
    assert mai.split_size(jeton) == beklenen


@pytest.mark.parametrize("bozuk", ["1:1", "1024", "", "axb"])
def test_a_broken_token_raises_a_TURKISH_error_not_a_ValueError(bozuk):
    """Ham `ValueError` app.py'nin süzgecinden GEÇER ve ham 500 olur; arayüz o
    gövdeyi JSON ayrıştıramaz ve kullanıcı yalnızca "Hata (500)" görür."""
    with pytest.raises(ac.ImageError):
        mai.split_size(bozuk)


def test_EVERY_catalog_token_is_convertible():
    """Katalogla adaptör ayrışmasın: beyan edilen her jeton çevrilebilmeli."""
    for jeton in catalog.MAI_SIZES:
        w, h = mai.split_size(jeton)
        assert w >= catalog.MAI_MIN_EDGE and h >= catalog.MAI_MIN_EDGE


# ── Gövdenin şekli ─────────────────────────────────────────────────────


def test_the_payload_carries_width_and_height_NOT_size():
    govde = mai.build_payload("kedi", "1248x832", api_model="MAI-Image-2.6")
    assert govde == {"model": "MAI-Image-2.6", "prompt": "kedi",
                     "width": 1248, "height": 832}


@pytest.mark.parametrize("olmamali", ["size", "quality", "n"])
def test_the_payload_NEVER_carries_a_field_MAI_does_not_know(olmamali):
    """Tanınmayan alan 400 DEĞİL, sessizce yutulan bir alan — yani "gönderdim,
    demek ki uygulandı" varsayımı yanlış bir faturaya dönüşür."""
    govde = mai.build_payload("kedi", "1024x1024", api_model="MAI-Image-2.6")
    assert olmamali not in govde


def test_generate_hits_the_MAI_path_with_the_api_key_header():
    client = FakeClient(_ok())
    out = mai.generate(MODEL, "kedi", "1024x1024", "standard", 1,
                       client=client, credentials=CREDS)

    assert out == [b"\x89PNG"]
    cagri = client.calls[0]
    assert cagri["url"] == (
        "https://ai-ornek.services.ai.azure.com/mai/v1/images/generations")
    assert cagri["headers"][mai.AUTH_HEADER] == "FOUNDRYKEY"
    assert cagri["headers"]["Content-Type"] == "application/json"


def test_the_wire_name_comes_from_the_catalog_not_from_a_constant():
    """`azure_client.MODEL_NAME` gibi bir sabit BURADA YOK ve olmamalı: bu
    modül üç dağıtımı birden konuşuyor."""
    client = FakeClient(_ok())
    mai.generate(FLASH, "kedi", "1024x1024", "standard", 1,
                 client=client, credentials=CREDS)

    assert client.calls[0]["json"]["model"] == "MAI-Image-2.6-Flash"


# ── Döngü ve zaman aşımı ───────────────────────────────────────────────


def test_four_images_become_FOUR_separate_requests():
    """MAI'de `n` YOK: adet başına ayrı istek (bkz. karar 5)."""
    client = FakeClient(_ok())
    out = mai.generate(MODEL, "kedi", "1024x1024", "standard", 4,
                       client=client, credentials=CREDS)

    assert len(out) == 4
    assert len(client.calls) == 4


def test_the_read_timeout_does_NOT_grow_with_the_count():
    """Karışsa n=4'te her isteğe 540 saniye verilirdi: 36 dakikalık en kötü
    hâl (bkz. providers.read_timeout_for)."""
    client = FakeClient(_ok())
    mai.generate(MODEL, "kedi", "1024x1024", "standard", 4,
                 client=client, credentials=CREDS)

    beklenen = providers.read_timeout_for(MODEL, 4)
    assert beklenen == ac.READ_TIMEOUT_FIRST
    for cagri in client.calls:
        assert cagri["timeout"].read == beklenen


def test_a_response_with_MORE_images_than_asked_is_trimmed():
    """`models.MAX_IMAGES_PER_RUN` 4 ve `ChatMessage.image_ids` `max_length=4`:
    fazlalık sessizce ilerlemiyor, ÜCRET ÖDENDİKTEN SONRA patlıyordu."""
    client = FakeClient(_ok(3))
    out = mai.generate(MODEL, "kedi", "1024x1024", "standard", 2,
                       client=client, credentials=CREDS)

    assert len(out) == 2
    assert len(client.calls) == 1, "ilk yanıt yettiyse ikinci istek atılmamalı"


# ── Düzenleme ──────────────────────────────────────────────────────────


def test_edit_posts_ONE_multipart_image_to_the_edits_path():
    client = FakeClient(_ok())
    out = mai.edit(MODEL, "arka planı sil", [("in.png", b"\x89PNG")],
                   "1024x768", "standard", 1,
                   client=client, credentials=CREDS)

    assert out == [b"\x89PNG"]
    cagri = client.calls[0]
    assert cagri["url"] == (
        "https://ai-ornek.services.ai.azure.com/mai/v1/images/edits")
    assert cagri["json"] is None, "düzenleme multipart, JSON değil"
    assert cagri["data"] == {"model": "MAI-Image-2.6", "prompt": "arka planı sil",
                             "width": "1024", "height": "768"}
    assert set(cagri["files"]) == {"image"}
    assert "Content-Type" not in cagri["headers"], (
        "multipart sınırını istemci koyuyor; elle yazmak gövdeyi bozar")


def test_a_SECOND_reference_image_is_refused_LOUDLY():
    """Görsel düzenleme rotası model başına `max_refs`e BAKMIYOR
    (`app._collect_edit_refs` yalnız küresel MAX_EDIT_IMAGES'e bakıyor), yani
    ikinci kapı burada olmak zorunda. Sessizce düşürmek, kullanıcının
    gönderdiği referansın yok sayıldığını hiçbir yerde okumaması olurdu."""
    with pytest.raises(ac.ImageError) as exc:
        mai.edit(MODEL, "p", [("a.png", b"\x89PNG"), ("b.png", b"\x89PNG")],
                 "1024x1024", "standard", 1,
                 client=FakeClient(_ok()), credentials=CREDS)

    assert "tek referans" in str(exc.value)


def test_an_EMPTY_reference_list_is_refused():
    with pytest.raises(ac.ImageError):
        mai.edit(MODEL, "p", [], "1024x1024", "standard", 1,
                 client=FakeClient(_ok()), credentials=CREDS)


# ── Yanıt ve hata ──────────────────────────────────────────────────────


@pytest.mark.parametrize("govde", [
    {},
    {"data": []},
    {"data": [{}]},
    {"data": "bir dize"},
])
def test_an_UNEXPECTED_200_becomes_a_TURKISH_error_not_a_KeyError(govde):
    """Sarmalanmayan bir `KeyError` app.py'nin `except ac.AzureImageError`
    süzgecinden GEÇER ve ham 500 olur (spec 1. risk)."""
    with pytest.raises(ac.ImageError):
        mai.decode_images(govde)


@pytest.mark.parametrize("kod, parca", [
    (401, "401"),
    (404, "404"),
    (429, "kotası doldu"),
    (500, "HTTP 500"),
])
def test_map_error_speaks_TURKISH_for_every_status(kod, parca):
    mesaj = mai.map_error(kod, {"error": {"code": "x", "message": "boom"}})
    assert parca in mesaj


def test_the_429_message_tells_the_user_to_WAIT_not_that_it_is_broken():
    """Foundry kapasitesi düşük ve sonda sırasında `RateLimitReached` görüldü;
    ham bir 502 kullanıcıya "bozuk" der."""
    client = FakeClient(FakeResponse(429, {"error": {"message": "RateLimitReached"}}))
    with pytest.raises(ac.ImageError) as exc:
        mai.generate(MODEL, "kedi", "1024x1024", "standard", 1,
                     client=client, credentials=CREDS)

    assert "bekleyip" in str(exc.value)


def test_the_MAI_error_body_shape_is_read_through_providers_detail_of():
    """MAI'nin gövdesi (`error.code` + `message` + `details`) OpenAI şekline
    yeterince yakın: `azure_client.map_error`ın mantığı KOPYALANMIYOR."""
    assert providers.detail_of(
        {"error": {"code": "BadRequest", "message": "prompt is required"}}
    ) == "prompt is required"
    assert "prompt is required" in mai.map_error(
        400, {"error": {"code": "BadRequest", "message": "prompt is required"}})


def test_a_TIMEOUT_becomes_a_TURKISH_error_that_names_FOUNDRY():
    """"Azure'a bağlanılamadı" diyen bir metin kullanıcıyı Endpoint alanını
    kurcalamaya iter, oysa çözülemeyen adres Foundry'nin."""
    import httpx

    class RaisingClient:
        def post(self, url, **kwargs):
            raise httpx.ConnectTimeout("boom")

    with pytest.raises(ac.ImageError) as exc:
        mai.generate(MODEL, "kedi", "1024x1024", "standard", 1,
                     client=RaisingClient(), credentials=CREDS)

    mesaj = str(exc.value)
    assert "Foundry" in mesaj and "Azure" not in mesaj


def test_the_identity_is_resolved_LAZILY_when_credentials_are_given(monkeypatch):
    """Erken çözüm `providers._azure_generate`in yorumundaki 104 testlik
    dersin tekrarı olurdu."""
    def patlat(*a, **k):
        raise AssertionError("credentials verilmişken credstore çağrılmamalı")

    monkeypatch.setattr("credstore.resolve", patlat)
    out = mai.generate(MODEL, "kedi", "1024x1024", "standard", 1,
                       client=FakeClient(_ok()), credentials=CREDS)
    assert out == [b"\x89PNG"]
```

- [ ] **Step 10: Testleri koş ve yeşile getir**

Run: `python -m pytest tests/test_azure_mai_client.py -q`
Expected: PASS. Kırmızı gelirse Step 4'teki modülü düzelt — TEST DEĞİL; testler tel sözleşmesinin mandalı.

- [ ] **Step 11: Tam takımı koş**

Run: `python -m pytest tests/ -q`
Expected: PASS (tamamı)

- [ ] **Step 12: Grafları yenile ve commit'le**

```bash
python tools/graf_uret.py && python tools/graf_uret.py --kontrol
```

```bash
git add azure_mai_client.py providers.py catalog.py static/img/providers/microsoft.svg tests/test_azure_mai_client.py tests/test_catalog.py docs/graflar
git commit -m "feat(foundry): MAI-Image adaptoru ve uc katalog girdisi

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: FLUX — adaptör modülü, iki katalog girdisi, `detail_of` liste dalı ve BFL işareti

**Files:**
- Create: `azure_flux_client.py`
- Create: `static/img/providers/blackforestlabs.svg`
- Modify: `providers.py` (`detail_of`'a `error.details[]` dalı + `_flux_adapter` + `_ADAPTERS` satırı)
- Modify: `catalog.py` (`FLUX_SIZES`; `QUALITY_LABELS`'a 3 satır; `PROVIDER_LOGOS`+`PROVIDER_BRANDS`'e 1'er satır; `IMAGE_MODELS`'ın SONUNA 2 girdi)
- Test: `tests/test_azure_flux_client.py` (yeni)
- Test: `tests/test_providers.py` (`detail_of` bloğunun sonuna)
- Test: `tests/test_catalog.py` (FLUX bloğu)

**Interfaces:**
- Consumes (Task 1, 2'den): `credstore.resolve("azure_foundry")`, `catalog.MAI_SIZES` deseni, `azure_mai_client`'ın kurduğu `AUTH_HEADER` geleneği.
- Produces:
  - `azure_flux_client.AUTH_HEADER: str` (`"api-key"`), `API_VERSION: str` (`"preview"`), `NUM_IMAGES: int` (`1`)
  - `azure_flux_client.model_path(wire_model: str) -> str`
  - `azure_flux_client.endpoint_for(base_url: str, wire_model: str) -> str`
  - `azure_flux_client.split_size(token: str) -> tuple[int, int]`
  - `azure_flux_client.quality_axis(quality: str) -> tuple[int, float] | None`
  - `azure_flux_client.build_payload(prompt, size, quality, *, api_model, images=None) -> dict`
  - `azure_flux_client.decode_images(response_json: dict) -> list[bytes]`
  - `azure_flux_client.map_error(status_code: int, body) -> str`
  - `azure_flux_client.generate(...)` / `edit(...)` — adaptör sözleşmesi
  - `providers.detail_of` artık `error.details[]` LİSTESİNİ de okuyor (imza AYNI)
  - `catalog.FLUX_SIZES: tuple[str, ...]`
  - Katalog id'leri: `azure-flux-2-pro`, `azure-flux-2-flex`; provider anahtarı `azure-flux`

- [ ] **Step 1: `detail_of`un liste dalının testini yaz (kırmızı)**

`tests/test_providers.py`'de `test_detail_of_duz_NESNE_yolunu_degistirmiyor`'dan SONRA:

```python
# ── FLUX'un ÜÇÜNCÜ hata şekli: `error.details[]` ───────────────────────
#
# Mevcut hiçbir çözümleyici bu listeyi tanımıyordu ve bedeli ölçülebilir:
# `error.message` boş olduğu için BÜTÜN 422'ler çıplak bir "HTTP 422"ya
# çöküyor, yani kullanıcı hangi alanın yanlış olduğunu hiçbir yerde okumuyor.


def test_detail_of_FLATTENS_the_flux_details_list():
    govde = {"error": {"details": [
        {"loc": ["body", "width"], "msg": "must be a multiple of 32"},
    ]}}
    assert providers.detail_of(govde) == "body.width: must be a multiple of 32"


def test_detail_of_joins_at_most_THREE_details():
    """Sınır bir süsleme değil: doğrulayıcı onlarca madde döndürebiliyor ve
    hepsini tek satıra dizmek kullanıcıya okunamayan bir duvar gösterirdi."""
    govde = {"error": {"details": [
        {"loc": ["body", f"a{i}"], "msg": "bad"} for i in range(6)
    ]}}
    detay = providers.detail_of(govde)
    assert detay.count(";") == 2, detay
    assert "a3" not in detay


def test_detail_of_keeps_the_MESSAGE_when_both_are_present():
    """Mesaj varsa o ANA cümle; liste onu tamamlıyor, EZMİYOR."""
    govde = {"error": {"message": "Validation failed",
                       "details": [{"loc": ["body", "steps"], "msg": "too big"}]}}
    detay = providers.detail_of(govde)
    assert detay.startswith("Validation failed")
    assert "body.steps: too big" in detay


def test_detail_of_IGNORES_a_string_details_field():
    """MAI'nin gövdesinde de `details` var ama o bir DİZE ve mesaj zaten
    `error.message`da — o yolun baytları DEĞİŞMEMELİ."""
    govde = {"error": {"code": "BadRequest", "message": "prompt is required",
                       "details": "see docs"}}
    assert providers.detail_of(govde) == "prompt is required"


def test_detail_of_survives_a_details_list_of_JUNK():
    """Şekil doğrulanmadan gelen bir gövde ham istisna üretmemeli."""
    assert providers.detail_of({"error": {"details": [None, 3, "x"]}}) == ""
    assert providers.detail_of({"error": {"details": []}}) == ""
```

- [ ] **Step 2: Testleri koş, kırmızı olduklarını gör**

Run: `python -m pytest tests/test_providers.py -q -k "detail_of"`
Expected: FAIL — `assert '' == 'body.width: must be a multiple of 32'`

- [ ] **Step 3: `providers.detail_of`a liste dalını ekle**

`detail_of` tanımından ÖNCE:

```python
# FLUX'un 422'si mesajı DEĞİL bir LİSTE taşıyor: `error.details[]` içinde
# `{"loc": [...], "msg": "..."}` maddeleri. Mevcut hiçbir çözümleyici bunu
# tanımıyordu ve `error.message` boş olduğu için BÜTÜN 422'ler çıplak bir
# "HTTP 422"ya çöküyordu — yani kullanıcı hangi alanın yanlış olduğunu hiçbir
# yerde okumuyordu. Tam olarak `detail_of`un Gemini'nin tek öğelik dizisi için
# var olma sebebi, üçüncü bir şekilde.
#
# YALNIZ LİSTE OKUNUYOR: MAI'nin gövdesinde de `details` var ama o bir DİZE ve
# mesaj zaten `error.message`da — o yolun baytları değişmiyor.
#
# ÜÇ MADDE TAVANI: doğrulayıcı onlarca madde döndürebiliyor ve hepsini tek
# satıra dizmek kullanıcıya okunamayan bir duvar gösterirdi. Kesme SESSİZ
# SAPMA değil çünkü ilk madde neredeyse her zaman asıl kusuru söylüyor;
# tamamı zaten `errlog`da duruyor.
_DETAIL_LIMIT = 3


def _madde_metni(madde: dict) -> str:
    """Tek bir `details[]` maddesini `"body.width: must be …"` biçimine indirir.

    `msg` yoksa `message` deneniyor: iki ad da canlıda görülüyor ve hangisinin
    geldiğine göre boş dönmek, sebebi hiç göstermemek olurdu.
    """
    loc = madde.get("loc")
    yer = ".".join(str(p) for p in loc) if isinstance(loc, list) else ""
    msg = str(madde.get("msg") or madde.get("message") or "")
    if yer and msg:
        return f"{yer}: {msg}"
    return msg or yer


def _details_metni(err: dict) -> str:
    ayrintilar = err.get("details")
    if not isinstance(ayrintilar, list):
        return ""
    parcalar = []
    for madde in ayrintilar[:_DETAIL_LIMIT]:
        if not isinstance(madde, dict):
            continue
        metin = _madde_metni(madde)
        if metin:
            parcalar.append(metin)
    return "; ".join(parcalar)
```

`detail_of` içindeki `dict` dalını şöyle yap:

```python
    err = body.get("error")
    if isinstance(err, dict):
        mesaj = str(err.get("message", ""))
        # Liste MESAJI EZMİYOR, TAMAMLIYOR: ikisi de dolu gelebiliyor ve
        # mesajı düşürmek asıl cümleyi çöpe atmak olurdu.
        ayrintilar = _details_metni(err)
        if mesaj and ayrintilar:
            return f"{mesaj} ({ayrintilar})"
        return mesaj or ayrintilar
    if isinstance(err, str):
        return err
    return ""
```

`detail_of`un docstring'inin sonuna bir paragraf ekle:

```
    ÜÇÜNCÜ ŞEKİL — `error.details[]`: FLUX'un 422'si mesaj yerine bir LİSTE
    döndürüyor ve o liste okunmazsa bütün 422'ler çıplak bir "HTTP 422"ya
    çöküyor. Ayrıntı `_details_metni`de; Azure, OpenAI ve MAI'nin düz nesne
    yolu bayt bayt aynı kalıyor (onların `details`i ya yok ya bir dize).
```

- [ ] **Step 4: Testleri koş, yeşil olduklarını gör**

Run: `python -m pytest tests/test_providers.py tests/test_gemini_client.py tests/test_openai_client.py tests/test_azure_mai_client.py -q`
Expected: PASS — mevcut `detail_of` iddialarının hiçbiri kaymamalı.

- [ ] **Step 5: `catalog.py`'ye FLUX jetonlarını, etiketlerini ve markasını ekle**

`MAI_SIZES` bloğundan SONRA:

```python
# FLUX.2 `gpt-image-2`nin ÜÇ JETONUNU AYNEN kullanabiliyor: üçü de belgelenmiş
# 4 MP tavanının çok altında ve 32'nin katı. Kazanç somut ve ölçülebilir —
# gpt-image-2'den FLUX'a geçen kullanıcı "varsayılana düşüldü" uyarısı ALMIYOR
# (bkz. core.js `fillAxis`).
#
# MAI'de aynı şeyi yapmak MÜMKÜN DEĞİLDİ (bkz. MAI_SIZES): `1024x1536` ve
# `1536x1024` MAI'nin piksel tavanını %50 aşıyor. İki sağlayıcının iki ayrı
# demet taşımasının sebebi bu, üslup değil.
#
# FLUX'un GERÇEK boyut kabulü (alt sınır, 32'nin katı olma şartı) bu depoda
# ÖLÇÜLMEDİ; üç jeton tavanın çok altında kaldığı için ilk tur güvenli.
# Mandal: tests/test_catalog.py::test_FLUX_jetonlari_gpt_image_2_ile_AYNI.
FLUX_SIZES: tuple[str, ...] = ("1024x1024", "1024x1536", "1536x1024")
```

`QUALITY_LABELS` sözlüğünün SONUNA:

```python
    # FLUX.2-flex'in `steps`/`guidance` kademeleri. Sentetik bir jeton İSRAF
    # olurdu: belgelenmiş `steps` (≤50) ve `guidance` (1.5–10) kaliteyi
    # DOĞRUDAN belirliyor, yani burada gerçek bir eksen var (karar 4).
    #
    # JETONLAR ASCII ve bu deponun kurulu deseni: `low`, `1K`, `720p`, tema
    # adları — hepsi ASCII. Jeton `history.json`a, `prefs.json`a ve
    # `ResultParams.quality`ye yazılıyor; Türkçe metin ETİKETTE yaşıyor.
    # Jetonlar sağlayıcıya GİTMİYOR: `azure_flux_client.quality_axis` onları
    # sayılara çeviriyor.
    "hizli": "Hızlı · 10 adım",
    "dengeli": "Dengeli · 25 adım",
    "detayli": "Detaylı · 50 adım",
```

`PROVIDER_LOGOS`'a: `"azure-flux": "blackforestlabs.svg",`
`PROVIDER_BRANDS`'e: `"azure-flux": "Black Forest Labs",`

- [ ] **Step 6: FLUX katalog kapılarının testini yaz (kırmızı)**

`tests/test_catalog.py`'de MAI bloğundan SONRA:

```python
# ── Azure AI Foundry · FLUX.2 (v0.15) ──────────────────────────────────


def test_FLUX_jetonlari_gpt_image_2_ile_AYNI():
    """Aynı jeton kümesi = model değiştirirken "varsayılana düşüldü" uyarısı
    YOK. Ayrışırsa kullanıcı sebepsiz bir düşme uyarısı görür."""
    azure = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    assert set(catalog.FLUX_SIZES) == set(azure.sizes)


def test_FLUX_girdileri_jetonlari_PAYLASIYOR():
    flux = [m for m in catalog.IMAGE_MODELS if m.provider == "azure-flux"]
    assert len(flux) == 2, "katalogda iki FLUX girdisi olmalı"
    for m in flux:
        assert m.sizes is catalog.FLUX_SIZES, (
            f"{m.id}: jetonları kopyalamış, FLUX_SIZES'ı paylaşmıyor")
        assert m.credential == "azure_foundry", m.credential
        assert m.images_per_request == 1
        # `num_images` tavanı ÖLÇÜLMEDİ: eksik beyan yalnızca bir yeteneği
        # kullanmamak, fazla beyan seçilebilir bir hata. Kapasite de bunu
        # destekliyor (flex belgelenmiş RPM'de 5/dk).
        assert m.max_n == 1, f"{m.id}: num_images tavanı ölçülmedi (karar 5)"
        assert m.supports_edit is True and m.max_refs == 4


def test_FLUX_pro_nun_kalite_ekseni_GIZLI_flex_in_GERCEK():
    """Ayrım kararın kendisi: pro'da `quality` parametresi YOK (sentetik jeton
    + gizli knob), flex'te `steps`/`guidance` GERÇEK bir eksen."""
    pro = catalog.image_model("azure-flux-2-pro")
    flex = catalog.image_model("azure-flux-2-flex")

    assert pro.quality_hidden is True and pro.qualities == ("standard",)
    assert flex.quality_hidden is False
    assert flex.qualities == ("hizli", "dengeli", "detayli")
    # Tarife jetonların ÜÇÜNE de yazılı: eksik kalan jeton `cost_for`da
    # sessizce tabana düşer ve seçicideki karşılaştırma yalan söyler.
    assert set(dict(flex.credits_by_quality)) == set(flex.qualities)
    assert catalog.default_quality_of(flex) == "dengeli"
```

- [ ] **Step 7: Testleri koş, kırmızı olduklarını gör**

Run: `python -m pytest tests/test_catalog.py -q -k "FLUX"`
Expected: FAIL — "katalogda iki FLUX girdisi olmalı" ve `image_model("azure-flux-2-pro")` `None`.

- [ ] **Step 8: İki FLUX katalog girdisini ekle**

`IMAGE_MODELS`'ın SONUNA, MAI girdilerinden sonra:

```python
    # ── Azure AI Foundry · FLUX.2 (Black Forest Labs) ───────────────────
    #
    # KREDİLER GEÇİCİ: FLUX megapiksel başına faturalanıyor ve yayınlanmış
    # birim fiyat doğrulanamadı (Azure fiyat sayfaları JS ile çiziliyor,
    # tablo boş döndü). Çapa yine Azure `medium` = 8 kredi ≈ 0,04 USD.
    # Krediler zaten "doğrulanacak bir olgu değil, ürün kararı" — ama ORAN
    # yanlışsa seçicideki karşılaştırma yalan söyler, o yüzden takip ediliyor.
    #
    # `max_n=1` ve gerekçesi iki katmanlı: (1) `num_images`ın üst sınırı
    # ölçülmedi ve fazla beyan arayüzde seçilebilir bir hata; (2) FLUX
    # dağıtımlarının kapasitesi düşük (belgelenmiş RPM'de flex için 5/dk) —
    # dört paralel istek 429'a girerdi ve sonda sırasında `RateLimitReached`
    # gerçekten görüldü.
    #
    # ÇOK REFERANSLI DÜZENLEME 8/10 görsele kadar çıkıyor ama ilk tur
    # `app.MAX_EDIT_IMAGES` (4) tavanında kalıyor; not bu yüzden 8/10 SÖZÜ
    # VERMİYOR — uygulamanın yapmadığı bir şeyi seçicide vaat etmek bu
    # deponun yasakladığı sessiz sapmanın kendisi.
    #
    # İÇERİK FİLTRESİ YOK (Microsoft'un kendi uyarısı), yani
    # `providers.is_content_policy` bu sağlayıcıda hiç tetiklenmiyor. Not
    # adaptörün başlığında da yazılı ki ileride "neden çalışmıyor" diye
    # aranmasın.
    ImageModel(
        id="azure-flux-2-pro",
        label="Black Forest Labs · FLUX.2 pro",
        provider="azure-flux",
        wire_model="FLUX.2-pro",
        credential="azure_foundry",
        sizes=FLUX_SIZES,
        # `quality` parametresi YOK: tek sentetik jeton + gizli knob (karar 4).
        qualities=("standard",),
        quality_hidden=True,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=4,
        credits=16,
        note="En yüksek görsel kalite; yavaş ve pahalı. Tek turda 1 görsel.",
    ),
    ImageModel(
        id="azure-flux-2-flex",
        label="Black Forest Labs · FLUX.2 flex",
        provider="azure-flux",
        wire_model="FLUX.2-flex",
        credential="azure_foundry",
        sizes=FLUX_SIZES,
        # GERÇEK bir eksen (karar 4): jetonlar `steps`/`guidance` çiftlerine
        # çözülüyor (bkz. azure_flux_client._FLEX_QUALITY). Sentetik bir jeton
        # burada israf olurdu.
        qualities=("hizli", "dengeli", "detayli"),
        default_quality="dengeli",
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=4,
        credits=10,
        # Taban `dengeli` (25 adım); ötekiler adım oranından türetildi
        # (10/25 → 0,6× ve 50/25 → 1,6×, yuvarlanmış). ÜÇÜ DE GEÇİCİ —
        # megapiksel fiyatı doğrulanmadı.
        credits_by_quality=(("hizli", 6), ("dengeli", 10), ("detayli", 16)),
        note="Adım ve yönlendirme seçilebiliyor: metin ağırlıklı yerleşimler "
             "için. Tek turda 1 görsel.",
    ),
```

- [ ] **Step 9: `blackforestlabs.svg`'yi yaz**

`static/img/providers/blackforestlabs.svg`:

```xml
<!-- Black Forest Labs (FLUX.2) · saglayici isareti.
     KAYNAK YOK ve bu bilerek kaydediliyor: simple-icons ve iconify'da BFL
     girdisi bulunmuyor, yani kardes dosyalardaki CC0 zinciri burada
     kurulamiyor. Ureticinin tescilli isaretini elle yeniden cizmek yerine
     SOYUT bir yer tutucu kullaniliyor (uc agac silueti, "black forest");
     amaci yalnizca satirin hangi saglayiciya ait oldugunu ayirt ettirmek.
     CC0 bir kaynak cikarsa dosya oldugu gibi degistirilebilir,
     PROVIDER_LOGOS satiri ayni kalir.

     TEK RENK ve renk DOSYADA sabit (fill), currentColor DEGIL: dosya <img> ile
     yukleniyor ve <img> icerigi sayfanin rengini miras almaz. Sabit deger
     tema katmanindaki fg (#e8eaed) ile ayni ve uygulamanin DORT temasi da
     koyu, yani tek varyant hepsinde okunuyor. Bir gun acik tema gelirse dogru
     yol mask-image + background: currentColor'a gecmek olur.

     DIKKAT: bu yorumda cift tire (XML'de yasak) YOK, bu olcum sonucu. Ilk
     yazimda "fg" token'i cift tireyle yaziliydi; dosya gecerli XML olmaktan
     cikti, tarayici 200 alip HICBIR SEY cizmedi ve naturalWidth 0 kaldi.
     Sessiz kusur tam olarak buydu (bkz. tests/test_provider_logos.py). -->
<svg width="24" height="24" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#e8eaed"><title>Black Forest Labs</title><path d="M6 3 1.5 13h9zM18 3l-4.5 10h9zM12 10 4.5 21h15z"/></svg>
```

**Not:** yorumda **Türkçe harf ve çift tire YOK** (kardeş dosyaların kuralı). Dosyayı yazdıktan sonra doğrulayan yer zaten var — ayrı bir betik yazma, o testi koş:

```bash
python -m pytest tests/test_provider_logos.py -q
```

- [ ] **Step 10: İşaret ve katalog kapılarını koş**

Run: `python -m pytest tests/test_provider_logos.py tests/test_catalog.py -q`
Expected: `test_ADAPTORU_OLAN_her_saglayicinin_isareti_var` YEŞİL (işaret geldi) ama `test_providers.py::test_katalogdaki_her_saglayicinin_adaptoru_kayitli` KIRMIZI olacak — adaptör bir sonraki adımda.

Run: `python -m pytest tests/test_providers.py -q -k adaptoru`
Expected: FAIL — "`azure-flux` adaptörü _ADAPTERS'ta yok"

- [ ] **Step 11: `azure_flux_client.py`'yi yaz**

```python
"""Azure AI Foundry · FLUX.2 (Black Forest Labs) — BFL yolu.

`azure_mai_client`ın KARDEŞİ ama İKİZİ DEĞİL: aynı host, aynı `api-key`, ama
yol ve gövde farklı —

  • yol `/providers/blackforestlabs/v1/<model-path>?api-version=preview`
    ve `<model-path>` DAĞITIM ADI DEĞİL (`FLUX.2-pro` → `flux-2-pro`);
  • düzenleme AYRI BİR UÇ DEĞİL: referanslar aynı JSON gövdesine
    `input_image`, `input_image_2`, … olarak base64 giriyor;
  • flex'te `steps` + `guidance` GERÇEK bir kalite ekseni.

Tek bir `azure_foundry_client.py` REDDEDİLDİ: tek modül iki tel formatı
taşırdı, hata eşlemesi bulanıklaşırdı ve `PROVIDER_LOGOS` tek anahtara
düşerdi — oysa üretici gerçekten iki (Microsoft ve Black Forest Labs).

**FLUX'TA YERLEŞİK İÇERİK FİLTRESİ YOK** (Microsoft'un kendi uyarısı). Yani
`providers.is_content_policy` bu sağlayıcıda HİÇ tetiklenmeyecek ve bu bir
kusur değil, sağlayıcının özelliği. Açıkça yazılı ki ileride "içerik reddi
dalı neden çalışmıyor" diye aranmasın. `map_error`da o dal BİLEREK yok.

DOSYA KÖKTE ve DÜZ olmak ZORUNDA (Chaquopy `include "*.py"`; bkz.
azure_mai_client.py'nin başlığı ve tests/test_android_packaging.py).

CANLI DOĞRULAMANIN SINIRI (2026-09-08) ve bu dosyanın en büyük riski:
**FLUX'un 200 YANITI BU DEPODAN GÖRÜLMEDİ.** Şekil Microsoft'un kendi örnek
deposundan alındı (`data[0]["b64_json"]`, senkron) ve MAI ile gpt-image-2'nin
ikisi de aynı şekli döndürüyor, ama ölçüm YOK. Azaltma `decode_images`ta:
beklenmeyen şekil ham `KeyError` değil Türkçe bir `ImageError` üretiyor —
sarmalanmayan bir `KeyError` app.py'nin süzgecinden geçer ve kullanıcı
beklemenin sonunda yalnızca "Hata (500)" görür. ÖLÇÜLMEYEN diğer üç şey:
kimlik başlığının adı (bkz. AUTH_HEADER), `num_images`ın üst sınırı ve
FLUX'un gerçek boyut kabulü.

`api-version=preview` SABİT DEĞİL: bu takma ad ileride başka bir şemaya
işaret edebilir ve o gün değişecek tek yer `API_VERSION`.
"""
from __future__ import annotations

import base64

import azure_client as ac
import catalog
import credstore
import providers

# Kimlik başlığı: `azure_mai_client.AUTH_HEADER`ın aynı gerekçesi ve aynı
# ölçülmemiş tarafı. İki modülde ayrı sabit olmasının sebebi paylaşılan bir
# yardımcının iki sağlayıcıyı birbirine kaynatması (karar 8) — biri 401
# dönerse öteki dokunulmadan kalabiliyor.
AUTH_HEADER = "api-key"
API_VERSION = "preview"

# `num_images` gövdede AÇIKÇA 1: alanı hiç göndermemek sağlayıcının kendi
# varsayılanına güvenmek olurdu ve o değer belgelenmemiş. 1 olması
# `ImageModel.images_per_request=1` beyanının teldeki karşılığı — adet başına
# AYRI istek atılıyor ve `providers.read_timeout_for` bu yüzden adetle
# büyümeyen süreyi veriyor. `max_n` bir gün yükselirse iki seçenek var:
# döngüyü korumak (bu satır aynı kalır) ya da `images_per_request`i de
# yükseltip buraya `n` koymak. Yarısını yapmak, ödenen ücretle dönen görsel
# sayısının ayrışması demek.
NUM_IMAGES = 1

# TEL ADI → YOL PARÇASI. Dağıtım adı gövdedeki `model` alanına gidiyor, YOLA
# GİTMİYOR — ikisi farklı ve karıştırmak 404 demek. Tablo elle tutuluyor
# çünkü türetilebilir değil: `FLUX.2-pro` → `flux-2-pro` dönüşümü noktayı
# tireye çeviriyor ama `FLUX.2-flex` gibi başka bir ad yarın başka bir kalıp
# taşıyabilir. Bilinmeyen ad SESSİZ 404 değil Türkçe hata üretiyor.
_MODEL_PATHS: dict[str, str] = {
    "FLUX.2-pro": "flux-2-pro",
    "FLUX.2-flex": "flux-2-flex",
}

# Katalog jetonu → (steps, guidance). YALNIZ flex'te anlamlı; pro'nun
# `quality` parametresi yok ve tablo onun jetonunu ("standard") HİÇ
# tanımıyor, yani `quality_axis` None döndürüyor ve gövdeye iki alan da
# girmiyor. Değerler belgelenmiş aralıklardan: `steps` ≤ 50 (varsayılan 50),
# `guidance` 1.5–10 (varsayılan 4.5).
_FLEX_QUALITY: dict[str, tuple[int, float]] = {
    "hizli": (10, 3.0),
    "dengeli": (25, 4.5),
    "detayli": (50, 6.0),
}


def model_path(wire_model: str) -> str:
    """Tel adının YOL parçası. Bilinmeyen adda Türkçe `ImageError`.

    Ham `KeyError` BIRAKILMIYOR: katalog ile bu tablo ayrışırsa bu bir
    programlama hatası, ama yine de 502'ye çevrilebilir bir tür olmalı —
    ham 500'de arayüz gövdeyi ayrıştıramıyor (bkz. credstore'un
    "Tanımsız kimlik" dalı).
    """
    yol = _MODEL_PATHS.get(wire_model)
    if yol is None:
        raise ac.ImageError(
            f"FLUX yol eşlemesi yok: {wire_model}. Katalog ile "
            "azure_flux_client._MODEL_PATHS ayrışmış.")
    return yol


def endpoint_for(base_url: str, wire_model: str) -> str:
    """Tam uç adresi. `api-version` sorgu dizesinde ve SABİT DEĞİL (bkz. başlık)."""
    return (f"{base_url.rstrip('/')}/providers/blackforestlabs/v1/"
            f"{model_path(wire_model)}?api-version={API_VERSION}")


def split_size(token: str) -> tuple[int, int]:
    """`"1024x1536"` → `(1024, 1536)`. Bozuk jetonda Türkçe `ImageError`.

    `azure_mai_client.split_size`ın İKİZİ ve BİLEREK kopyalanmış: ortak bir
    yardımcıya çıkarmak iki sağlayıcıyı birbirine kaynatmak olurdu (karar 8)
    ve bu deponun yazılı kuralı `openai_client.py`nin başlığında —
    "İki kopya yeterli kanıt değil, ÜÇ kopya kanıttır". Üçüncü kopya
    ortaya çıktığında çıkarılacak yer o gün belli olur.
    """
    genislik, _, yukseklik = token.partition("x")
    try:
        return int(genislik), int(yukseklik)
    except ValueError:
        raise ac.ImageError(
            f"FLUX geometri jetonunu anlamadı: {token} "
            "(beklenen biçim: GENİŞLİKxYÜKSEKLİK).") from None


def quality_axis(quality: str) -> tuple[int, float] | None:
    """Kalite jetonu → `(steps, guidance)`; ekseni olmayan modelde None.

    None SESSİZ bir yol ve bilinçli: pro'nun jetonu ("standard") tabloda YOK
    ve gövdeye `steps`/`guidance` GİRMEMESİ gerekiyor. Bilinmeyen bir jetonu
    hata saymak, kalite ekseni olmayan modelde her üretimi düşürürdü.
    """
    return _FLEX_QUALITY.get(quality)


def build_payload(prompt: str, size: str, quality: str, *, api_model: str,
                  images=None) -> dict:
    """FLUX gövdesi. ÜRETİM ve DÜZENLEME AYNI gövdeyi kullanıyor.

    Düzenleme ayrı bir uç DEĞİL: referanslar `input_image`, `input_image_2`,
    `input_image_3`… alanlarına base64 olarak giriyor ve SIRA anlamlı (ilk
    görsel ana referans, adaptör sözleşmesinin kuralı). Numaralandırma 1'den
    DEĞİL 2'den başlıyor — ilk alanın adı sonek TAŞIMIYOR ve bu telin kendi
    kuralı, uydurulmuş bir simetri değil.
    """
    w, h = split_size(size)
    govde = {"model": api_model, "prompt": prompt,
             "width": w, "height": h, "num_images": NUM_IMAGES}
    eksen = quality_axis(quality)
    if eksen is not None:
        govde["steps"], govde["guidance"] = eksen
    for sira, (_ad, veri) in enumerate(images or ()):
        alan = "input_image" if sira == 0 else f"input_image_{sira + 1}"
        govde[alan] = base64.b64encode(veri).decode("ascii")
    return govde


def decode_images(response_json: dict) -> list[bytes]:
    """`data[].b64_json` → PNG baytları. ŞEKİL ÖLÇÜLMEDİ, o yüzden SARMALI.

    Spec'in 1. riski bu: FLUX'un 200'ü bu depodan görülmedi. Şekil değişirse
    doğru davranış ham `KeyError` değil Türkçe bir hata — sarmalanmayan bir
    `KeyError` app.py'nin `except ac.AzureImageError` süzgecinden GEÇER ve
    kullanıcı beklemenin sonunda yalnızca "Hata (500)" görür.
    """
    data = response_json.get("data")
    if not isinstance(data, list) or not data:
        raise ac.ImageError("FLUX yanıtı boş döndü (data yok). Tekrar deneyin.")
    out: list[bytes] = []
    for item in data:
        b64 = item.get("b64_json") if isinstance(item, dict) else None
        if not b64:
            raise ac.ImageError(
                "FLUX yanıtı beklenmedik biçimde geldi (b64_json yok).")
        out.append(base64.b64decode(b64))
    return out


def map_error(status_code: int, body: dict | list | None) -> str:
    """HTTP durumunu Türkçe mesaja çevirir.

    422 KENDİ DALINDA ve bu dosyanın en çok işe yarayan yeri: FLUX'un
    doğrulayıcısı mesaj yerine `error.details[]` listesi döndürüyor ve o liste
    okunmazsa bütün 422'ler çıplak bir "HTTP 422"ya çöküyor — yani kullanıcı
    hangi alanın yanlış olduğunu hiçbir yerde okumuyor. Listeyi tek cümleye
    indiren yer `providers.detail_of` (`_details_metni`), Türkçeye çeviren
    yer burası.

    İÇERİK REDDİ DALI BİLEREK YOK: FLUX'ta yerleşik içerik filtresi
    bulunmuyor (Microsoft'un kendi uyarısı), yani `providers.is_content_policy`
    burada hiç tetiklenmeyecek. Boş bir dal bırakmak, ileride "neden hiç
    çalışmıyor" diye aranan bir şey olurdu.
    """
    detail = providers.detail_of(body)
    if status_code == 401:
        return ("Azure AI Foundry yetkilendirme hatası (401): api-key geçersiz "
                "veya bu kaynağa ait değil. Ayarlar'dan yeniden kaydet.")
    if status_code == 404:
        return ("FLUX dağıtımı bulunamadı (404): bu model Foundry'de "
                "dağıtılmamış olabilir, ya da Ayarlar'daki Foundry adresi "
                "başka bir kaynağı gösteriyor." + (f" {detail}" if detail else ""))
    if status_code == 422:
        return ("FLUX isteği reddetti (422): "
                + (detail or "gövdedeki alanlardan biri geçersiz."))
    if status_code == 429:
        return ("FLUX kotası doldu (429): biraz bekleyip tekrar deneyin. "
                "FLUX dağıtımlarının kapasitesi düşük.")
    return (f"FLUX isteği başarısız (HTTP {status_code})."
            + (f" {detail}" if detail else ""))


def _post(endpoint: str, key: str, payload: dict, *, client, read: float) -> dict:
    """Ortak POST + hata çevirisi. Multipart YOK — düzenleme de JSON.

    `client` sözleşmede KORUNUYOR (adaptör sözleşmesinin `client=` anahtarı):
    testler `FakeClient` geçiriyor ve döngülü üretimde tek istemciyi yeniden
    kullanmak bağlantı başına TLS el sıkışmasını da ortadan kaldırıyor.
    """
    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        resp = client.post(endpoint,
                           headers={AUTH_HEADER: key,
                                    "Content-Type": "application/json"},
                           json=payload, timeout=ac.request_timeout(read))
    except httpx.TransportError as exc:
        # Mesaj `azure_client`tan geliyor, sağlayıcı adı düzeltiliyor: "Azure'a
        # bağlanılamadı" diyen bir metin kullanıcıyı Endpoint alanını
        # kurcalamaya iter. ÜCRET UYARISI korunuyor.
        raise ac.ImageError(
            ac.transport_error_message(exc, read).replace("Azure", "Foundry")) from exc
    finally:
        if owns:
            client.close()

    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = None
        raise ac.ImageError(map_error(resp.status_code, body))
    return resp.json()


def _uret(m: catalog.ImageModel, prompt: str, size: str, quality: str, n: int,
          images, *, client, credentials) -> list[bytes]:
    """`generate` ve `edit`in PAYLAŞILAN gövdesi — tek fark `images`.

    FLUX'ta düzenleme ayrı bir uç DEĞİL, o yüzden iki fonksiyonu ayrı yazmak
    aynı döngüyü ve aynı zaman aşımı hesabını iki yerde bakıma sokardı
    (`gemini_client._uret`in aynı gerekçesi).

    KİMLİK TEMBEL çözülüyor; DÖNGÜ adet başına ayrı istek atıyor
    (`images_per_request=1`). Bugün `max_n=1` olduğu için döngü tek tur
    dönüyor, ama yapısı `max_n` yükseldiği gün hazır: `providers.total_budget`
    zaten tur sayısıyla ölçekleniyor.
    """
    key, base_url = (credentials if credentials is not None
                     else credstore.resolve(m.credential))
    read = providers.read_timeout_for(m, n)
    endpoint = endpoint_for(base_url, m.wire_model)
    payload = build_payload(prompt, size, quality, api_model=m.wire_model,
                            images=images)

    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        out: list[bytes] = []
        while len(out) < n:
            out.extend(decode_images(
                _post(endpoint, key, payload, client=client, read=read)))
        return out[:n]
    finally:
        if owns:
            client.close()


def generate(m: catalog.ImageModel, prompt: str, size: str, quality: str, n: int,
             *, client=None, credentials=None) -> list[bytes]:
    return _uret(m, prompt, size, quality, n, None,
                 client=client, credentials=credentials)


def edit(m: catalog.ImageModel, prompt: str, images, size: str, quality: str,
         n: int, *, client=None, credentials=None) -> list[bytes]:
    """`images`: sıralı [(dosya_adı, png_baytları), ...] — ilk görsel ana
    referans ve gövdedeki `input_image` alanına giriyor."""
    return _uret(m, prompt, size, quality, n, images,
                 client=client, credentials=credentials)
```

- [ ] **Step 12: `providers.py`'ye FLUX adaptörünü kaydet**

`_mai_adapter` tanımından SONRA:

```python
def _flux_adapter():
    """`_mai_adapter`ın aynı gerekçesi: `azure_flux_client` bu modülü import
    ediyor (`read_timeout_for` ve `detail_of` için), yani modül düzeyinde
    import etmek DÖNGÜ olurdu. Düz `import` ifadesi, yalnız fonksiyon içinde —
    PyInstaller'ın statik analizi onu da görüyor."""
    import azure_flux_client
    return (azure_flux_client.generate, azure_flux_client.edit)
```

`_ADAPTERS`'e, `"azure-mai"` satırından sonra:

```python
    "azure-flux": _flux_adapter,
```

- [ ] **Step 13: FLUX adaptörünün testini yaz (kırmızı)**

Create `tests/test_azure_flux_client.py`:

```python
"""azure_flux_client: BFL telinin şekli, model-path eşlemesi ve 422 çevirisi.

Bu dosyanın en değerli üç iddiası:

  1. YOL DAĞITIM ADI DEĞİL. `FLUX.2-pro` gövdedeki `model` alanına gidiyor,
     yola ise `flux-2-pro` giriyor. İkisini karıştırmak 404 demek ve hata
     "model bulunamadı" derken kullanıcıyı anahtarını kurcalamaya iter.
  2. 422 MESAJ DEĞİL LİSTE taşıyor (`error.details[]`). Liste okunmazsa
     bütün 422'ler çıplak bir "HTTP 422"ya çöküyor.
  3. `steps`/`guidance` YALNIZ flex'te. pro'nun `quality` parametresi yok ve
     iki alanı göndermek beyan edilmemiş bir alan göndermek olurdu.

CANLI DOĞRULAMANIN SINIRI: FLUX'un 200 yanıtı bu depodan GÖRÜLMEDİ (şekil
Microsoft'un örnek deposundan). O yüzden `decode_images`ın sarmalama iddiası
bu dosyada en yüksek değerli test — şekil değişirse kullanıcı Türkçe bir
hata görmeli, ham 500 değil.
"""
import base64

import pytest

import azure_client as ac
import azure_flux_client as flux
import catalog
import providers

PRO = catalog.image_model("azure-flux-2-pro")
FLEX = catalog.image_model("azure-flux-2-flex")
CREDS = ("FOUNDRYKEY", "https://ai-ornek.services.ai.azure.com")


class FakeResponse:
    def __init__(self, status_code, json_body=None):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        if self._json is None:
            raise ValueError("gövde JSON değil")
        return self._json


class FakeClient:
    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json,
                           "timeout": timeout})
        return (self._responses[len(self.calls) - 1]
                if len(self._responses) > 1 else self._responses[0])


def _ok(sayi=1):
    b64 = base64.b64encode(b"\x89PNG").decode()
    return FakeResponse(200, {"data": [{"b64_json": b64}] * sayi})


# ── Yol eşlemesi ───────────────────────────────────────────────────────


@pytest.mark.parametrize("tel_adi, yol", [
    ("FLUX.2-pro", "flux-2-pro"),
    ("FLUX.2-flex", "flux-2-flex"),
])
def test_the_path_segment_is_NOT_the_deployment_name(tel_adi, yol):
    assert flux.model_path(tel_adi) == yol


def test_an_UNMAPPED_wire_name_raises_a_TURKISH_error_not_a_KeyError():
    with pytest.raises(ac.ImageError) as exc:
        flux.model_path("FLUX.9-imaginary")
    assert "_MODEL_PATHS" in str(exc.value)


def test_EVERY_catalog_flux_entry_has_a_path():
    """Katalog ile tablo ayrışırsa model seçilebilir olur ve üretim 404 alır."""
    for m in catalog.IMAGE_MODELS:
        if m.provider == "azure-flux":
            assert flux.model_path(m.wire_model)


def test_the_endpoint_carries_the_api_version_query():
    assert flux.endpoint_for("https://ai-ornek.services.ai.azure.com/", "FLUX.2-pro") == (
        "https://ai-ornek.services.ai.azure.com/providers/blackforestlabs/v1/"
        "flux-2-pro?api-version=preview")


# ── Gövdenin şekli ─────────────────────────────────────────────────────


def test_the_payload_carries_width_height_and_num_images():
    govde = flux.build_payload("kedi", "1024x1536", "standard",
                               api_model="FLUX.2-pro")
    assert govde == {"model": "FLUX.2-pro", "prompt": "kedi",
                     "width": 1024, "height": 1536, "num_images": 1}


def test_PRO_never_sends_steps_or_guidance():
    """pro'nun `quality` parametresi YOK; beyan edilmemiş bir alan göndermek
    "gönderdim, demek ki uygulandı" varsayımını doğurur."""
    govde = flux.build_payload("kedi", "1024x1024", "standard",
                               api_model="FLUX.2-pro")
    assert "steps" not in govde and "guidance" not in govde


@pytest.mark.parametrize("jeton, steps, guidance", [
    ("hizli", 10, 3.0),
    ("dengeli", 25, 4.5),
    ("detayli", 50, 6.0),
])
def test_FLEX_maps_the_quality_token_to_steps_and_guidance(jeton, steps, guidance):
    """Sentetik bir jeton burada İSRAF olurdu: `steps` ve `guidance` kaliteyi
    doğrudan belirliyor (karar 4)."""
    govde = flux.build_payload("kedi", "1024x1024", jeton,
                               api_model="FLUX.2-flex")
    assert govde["steps"] == steps
    assert govde["guidance"] == guidance


def test_EVERY_flex_catalog_token_maps_to_an_axis():
    """Katalog ile `_FLEX_QUALITY` ayrışırsa jeton sessizce eksen üretmez ve
    kullanıcı seçtiği kademeyi ALMAZ — üstelik farkı hiçbir yerde okumaz."""
    for jeton in FLEX.qualities:
        assert flux.quality_axis(jeton) is not None, jeton


def test_the_steps_and_guidance_stay_inside_the_documented_ranges():
    for steps, guidance in (flux.quality_axis(q) for q in FLEX.qualities):
        assert 1 <= steps <= 50
        assert 1.5 <= guidance <= 10


# ── Referans görseller ─────────────────────────────────────────────────


def test_the_reference_images_are_numbered_from_TWO():
    """İlk alanın adı sonek TAŞIMIYOR ve bu telin kendi kuralı."""
    gorseller = [("a.png", b"AAA"), ("b.png", b"BBB"), ("c.png", b"CCC")]
    govde = flux.build_payload("p", "1024x1024", "standard",
                               api_model="FLUX.2-pro", images=gorseller)

    assert govde["input_image"] == base64.b64encode(b"AAA").decode()
    assert govde["input_image_2"] == base64.b64encode(b"BBB").decode()
    assert govde["input_image_3"] == base64.b64encode(b"CCC").decode()
    assert "input_image_1" not in govde


def test_generation_carries_NO_input_image_field():
    govde = flux.build_payload("p", "1024x1024", "standard",
                               api_model="FLUX.2-pro")
    assert not [k for k in govde if k.startswith("input_image")]


def test_edit_and_generate_hit_the_SAME_endpoint():
    """FLUX'ta düzenleme ayrı bir uç DEĞİL; iki fonksiyonu ayrı yazmak aynı
    döngüyü iki yerde bakıma sokardı."""
    c1, c2 = FakeClient(_ok()), FakeClient(_ok())
    flux.generate(PRO, "p", "1024x1024", "standard", 1,
                  client=c1, credentials=CREDS)
    flux.edit(PRO, "p", [("a.png", b"AAA")], "1024x1024", "standard", 1,
              client=c2, credentials=CREDS)

    assert c1.calls[0]["url"] == c2.calls[0]["url"]
    assert c2.calls[0]["json"]["input_image"]


# ── İstek ve zaman aşımı ───────────────────────────────────────────────


def test_generate_sends_the_api_key_header_and_decodes():
    client = FakeClient(_ok())
    out = flux.generate(PRO, "kedi", "1024x1024", "standard", 1,
                        client=client, credentials=CREDS)

    assert out == [b"\x89PNG"]
    cagri = client.calls[0]
    assert cagri["headers"][flux.AUTH_HEADER] == "FOUNDRYKEY"
    assert cagri["timeout"].read == providers.read_timeout_for(PRO, 1)
    assert cagri["timeout"].read == ac.READ_TIMEOUT_FIRST


def test_the_identity_is_resolved_LAZILY_when_credentials_are_given(monkeypatch):
    def patlat(*a, **k):
        raise AssertionError("credentials verilmişken credstore çağrılmamalı")

    monkeypatch.setattr("credstore.resolve", patlat)
    assert flux.generate(PRO, "kedi", "1024x1024", "standard", 1,
                         client=FakeClient(_ok()), credentials=CREDS) == [b"\x89PNG"]


# ── Yanıt ve hata ──────────────────────────────────────────────────────


@pytest.mark.parametrize("govde", [
    {},
    {"data": []},
    {"data": [{}]},
    {"data": {"b64_json": "x"}},
])
def test_an_UNEXPECTED_200_becomes_a_TURKISH_error_not_a_KeyError(govde):
    """Spec'in 1. riskinin azaltması: FLUX'un 200'ü bu depodan görülmedi."""
    with pytest.raises(ac.ImageError):
        flux.decode_images(govde)


def test_the_422_details_list_reaches_the_user_as_ONE_turkish_sentence():
    """Liste okunmazsa bütün 422'ler çıplak bir "HTTP 422"ya çöküyor."""
    client = FakeClient(FakeResponse(422, {"error": {"details": [
        {"loc": ["body", "width"], "msg": "must be a multiple of 32"},
        {"loc": ["body", "steps"], "msg": "must be <= 50"},
    ]}}))

    with pytest.raises(ac.ImageError) as exc:
        flux.generate(PRO, "kedi", "1024x1024", "standard", 1,
                      client=client, credentials=CREDS)

    mesaj = str(exc.value)
    assert "422" in mesaj
    assert "body.width: must be a multiple of 32" in mesaj
    assert "body.steps: must be <= 50" in mesaj


def test_a_422_with_an_EMPTY_details_list_still_says_something_useful():
    mesaj = flux.map_error(422, {"error": {"details": []}})
    assert "geçersiz" in mesaj


def test_the_429_message_tells_the_user_to_WAIT():
    """FLUX dağıtımlarının kapasitesi düşük (flex belgelenmiş RPM'de 5/dk) ve
    sonda sırasında `RateLimitReached` gerçekten görüldü."""
    assert "bekleyip" in flux.map_error(429, None)


def test_map_error_has_NO_content_policy_branch():
    """FLUX'ta yerleşik içerik filtresi YOK (Microsoft'un kendi uyarısı).

    İçerik reddi gibi görünen bir metin gelse bile o dal bilerek yok: boş bir
    dal ileride "neden hiç çalışmıyor" diye aranan bir şey olurdu.
    """
    mesaj = flux.map_error(400, {"error": {"message": "content policy"}})
    assert "İçerik politikası" not in mesaj
    assert "HTTP 400" in mesaj


def test_a_TIMEOUT_becomes_a_TURKISH_error_that_names_FOUNDRY():
    import httpx

    class RaisingClient:
        def post(self, url, **kwargs):
            raise httpx.ReadTimeout("boom")

    with pytest.raises(ac.ImageError) as exc:
        flux.generate(PRO, "kedi", "1024x1024", "standard", 1,
                      client=RaisingClient(), credentials=CREDS)

    mesaj = str(exc.value)
    assert "Foundry" in mesaj and "Azure" not in mesaj
```

- [ ] **Step 14: Testleri koş ve yeşile getir**

Run: `python -m pytest tests/test_azure_flux_client.py -q`
Expected: PASS

- [ ] **Step 15: Tam takımı koş**

Run: `python -m pytest tests/ -q`
Expected: PASS (tamamı)

- [ ] **Step 16: Grafları yenile ve commit'le**

```bash
python tools/graf_uret.py && python tools/graf_uret.py --kontrol
```

```bash
git add azure_flux_client.py providers.py catalog.py static/img/providers/blackforestlabs.svg tests/test_azure_flux_client.py tests/test_providers.py tests/test_catalog.py docs/graflar
git commit -m "feat(foundry): FLUX.2 adaptoru, iki katalog girdisi ve detail_of liste dali

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Mevcut girdilerin notlarını gözden geçir ve turu kapat

Spec'in 9. kararının ikinci yarısı: "Mevcut girdilerin notları da bu turda gözden geçirilir — yeni satırlarla aynı soruyu ('ne zaman bunu seçerim') cevaplasınlar diye." Katalogda BEŞ mevcut girdi var (spec "altı" diyor; sayı yanlış, bkz. Sapma 2).

**Files:**
- Modify: `catalog.py` (beş mevcut `ImageModel`'in `note` alanı)
- Test: `tests/test_catalog.py` (not sözleşmesi)

**Interfaces:**
- Consumes: Task 2 ve 3'ün eklediği `azure-mai` / `azure-flux` girdileri (yeni notlarla karşılaştırma için).
- Produces: yeni bir simge YOK — yalnız `note` dizeleri ve bir test.

- [ ] **Step 1: Not sözleşmesinin testini yaz (kırmızı bekleniyor)**

`tests/test_catalog.py`'de FLUX bloğundan SONRA:

```python
# ── `note` sözleşmesi ──────────────────────────────────────────────────


@pytest.mark.parametrize("m", catalog.IMAGE_MODELS, ids=lambda m: m.id)
def test_her_gorsel_modelinin_notu_NE_ZAMAN_SECILIR_i_cevapliyor(m):
    """`note` seçicide model adının ALTINA yazılıyor (static/core.js) ve tek
    işi şu soruyu cevaplamak: "ne zaman bunu seçerim?".

    Boş bir not o satırı adı tekrar eden bir başlığa indiriyor. Uzunluk üst
    sınırı da gerçek: 360px'lik bir yüzeyde iki satırı aşan not kaydırma
    üretiyor ve komşu satırların hizasını bozuyor.
    """
    assert m.note, f"{m.id}: not yok — seçicideki satır sebepsiz kalıyor"
    assert 20 <= len(m.note) <= 110, (
        f"{m.id}: not {len(m.note)} karakter (beklenen 20-110)")
    # Adı TEKRAR ETMİYOR: etiket zaten satırın kendisi.
    assert m.label.lower() not in m.note.lower(), (
        f"{m.id}: not etiketi tekrar ediyor")


def test_her_ONIZLEME_modelinin_notu_bunu_SOYLUYOR():
    """MAI ailesinin üçü de önizleme: ad ya da sözleşme haber vermeden
    değişebilir. `openai-gpt-image-1`in duruşu benimseniyor — notta yazılı,
    kalkınca girdi silinir. Yazılmazsa kullanıcı kararlı bir model sanır.
    """
    for m in catalog.IMAGE_MODELS:
        if m.provider == "azure-mai":
            assert "Önizleme" in m.note, f"{m.id}: önizleme uyarısı yok"


def test_hicbir_not_uygulamanin_YAPMADIGI_bir_seyi_vaat_etmiyor():
    """FLUX 8/10 referans alabiliyor ama ilk tur `app.MAX_EDIT_IMAGES` (4)
    tavanında kalıyor ve `max_n=1`. Seçicide "8 referans" yazmak, uygulamanın
    yapmadığı bir şeyi vaat etmek olurdu — bu deponun yasakladığı sessiz
    sapmanın kendisi. Sayı bir gün yükselirse önce bu test kırmızıya döner.
    """
    import app as appmod

    for m in catalog.IMAGE_MODELS:
        for sayi in ("8 referans", "10 referans"):
            assert sayi not in m.note, (
                f"{m.id}: not {sayi} vaat ediyor, tavan "
                f"{min(m.max_refs, appmod.MAX_EDIT_IMAGES)}")
```

- [ ] **Step 2: Testi koş ve hangi notların düştüğünü gör**

Run: `python -m pytest tests/test_catalog.py -q -k "notu or ONIZLEME or YAPMADIGI"`
Expected: kısmen FAIL. Beş mevcut girdinin notları bu tur yazılmadan önce uzunluk/tekrar kapısına takılabiliyor. **Hangi girdilerin düştüğünü ÇIKTIDAN oku** — bir sonraki adım beşini de yeniden yazıyor, ama düşen satırların listesi doğrulamanın kanıtı. Yeni beş girdi (MAI ×3, FLUX ×2) ve önizleme/vaat iddiaları Task 2-3'ten YEŞİL gelmeli; gelmiyorsa kusur o görevlerdeki notlardadır, bu testte değil.

- [ ] **Step 3: Beş mevcut girdinin notunu yeniden yaz**

`catalog.py`'de, girdilerin `note=` satırlarını şöyle yap (yalnız `note` değişiyor; başka hiçbir alana dokunulmuyor):

`azure-gpt-image-2`:
```python
        note="Metin, tabela ve çok referanslı düzenlemede en güçlü; "
             "uygulamanın varsayılanı.",
```

`openai-gpt-image-2`:
```python
        note="Azure'daki modelin aynısı, kendi anahtarınla — kurumsal "
             "kaynağın yoksa bunu seç.",
```

`openai-gpt-image-1`:
```python
        note="Seçmeyin: 23 Ekim 2026'da API'den kalkıyor. gpt-image-2'ye geç.",
```

`gemini-nano-banana-2`:
```python
        note="En hızlı ve en ucuz tur; oran seçiliyor (piksel değil). "
             "Taslak için.",
```

`gemini-nano-banana-pro`:
```python
        note="Marka tutarlılığı ve uzun metin yerleşimi; pahalı ama en "
             "sadık.",
```

Notların yanına, `IMAGE_MODELS` demetinin başındaki yorum bloğuna bir paragraf ekle:

```python
# `note` SEÇİCİDE model adının ALTINA yazılıyor (static/core.js) ve tek işi
# şu soruyu cevaplamak: "ne zaman bunu seçerim?". Bu yüzden notlar bir yetenek
# listesi DEĞİL, bir KARAR cümlesi — ve UYGULAMANIN YAPMADIĞI bir şeyi vaat
# etmiyorlar: FLUX 8/10 referans alabiliyor ama ilk tur `app.MAX_EDIT_IMAGES`
# (4) tavanında kalıyor, o yüzden hiçbir not o sayıları yazmıyor. Mandal:
# tests/test_catalog.py'nin `note` sözleşmesi bloğu.
```

- [ ] **Step 4: Not testlerini koş, yeşil olduklarını gör**

Run: `python -m pytest tests/test_catalog.py -q`
Expected: PASS

- [ ] **Step 5: Tam takımı koş — kanıt olmadan iddia yok**

Run: `python -m pytest tests/ -q`
Expected: PASS (tamamı). Çıktıyı OKU; "hepsi geçti" demeden önce satırı gör.

- [ ] **Step 6: Harita kapısını ayrıca doğrula**

```bash
python tools/graf_uret.py && python tools/graf_uret.py --kontrol && python tools/graf_uret.py --ozet
```

Özette şunlar görünmeli: iki yeni modül (`azure_mai_client`, `azure_flux_client`) ve `providers`ın onları ERTELİ ithal ettiği (`gemini_client`/`openai_client`/`veo_client` ile aynı kalıp).

- [ ] **Step 7: Grafları yenile ve commit'le**

```bash
git add catalog.py tests/test_catalog.py docs/graflar
git commit -m "docs(katalog): mevcut bes girdinin notu ve not sozlesmesi mandali

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Açık Kalemler

Uygulama SIRASINDA çözülmüyor; kaydediliyor ki aranan bir şey olmasın.

1. **Kimlik başlığının adı ölçülmedi.** `AUTH_HEADER = "api-key"` iki adaptörde de sabit. İlk canlı çağrı 401 dönerse değiştirilecek TEK yer o iki satır (`Authorization` için değer `f"Bearer {key}"` olur). Sonda "aynı `api-key` üç yüzeyde de geçiyor" diyor ama başlığın adını yazmıyor.
2. **MAI düzenleme ucunun multipart alan adları ölçülmedi.** Bugün `model` + `prompt` + `width` + `height` + `image` gönderiliyor (üretim gövdesinin multipart karşılığı). MAI tanınmayan alanı SESSİZCE yutuyor, yani yanlış bir ad 400 değil "referans yok sayılmış bir düzenleme" üretir. İlk canlı düzenlemede çıktının gerçekten referansı kullandığı GÖZLE doğrulanmalı.
3. **FLUX'un 200 yanıtı bu depodan görülmedi.** Şekil Microsoft'un örnek deposundan. `decode_images` beklenmeyen şekli Türkçe hataya çeviriyor; ilk canlı üretimden sonra `tests/test_azure_flux_client.py`'ye gerçek gövde eklenmeli.
4. **FLUX'un `num_images` üst sınırı ölçülmedi.** `max_n=1` ve `NUM_IMAGES=1`. Yükseltmek iki karar demek: döngüyü korumak (`NUM_IMAGES` 1 kalır) ya da `images_per_request`i de yükseltip gövdeye `n` koymak. Yarısını yapmak, ödenen ücretle dönen görsel sayısının ayrışması olur.
5. **FLUX'un gerçek boyut kabulü ölçülmedi** (alt sınır, 32'nin katı olma şartı). Mevcut üç jeton 4 MP tavanının çok altında, ilk tur güvenli.
6. **Üç kredi değeri GEÇİCİ:** `MAI-Image-2.6-Flash` (4), `FLUX.2-pro` (16), `FLUX.2-flex` (10 + türetilen 6/16). Yayınlanmış birim fiyat doğrulanamadı (Azure fiyat sayfaları JS ile çiziliyor). ORAN yanlışsa seçicideki karşılaştırma yalan söyler.
7. **`max_refs` GÖRSEL düzenleme rotasında doğrulanmıyor.** `app._collect_edit_refs` yalnız küresel `MAX_EDIT_IMAGES`e bakıyor. MAI'nin kapısı adaptörde (`build_image_file`) ve kullanıcı 502 + Türkçe mesaj görüyor, ham bir sağlayıcı hatası değil. Rota kapısı eklemek bütün sağlayıcıları etkileyen yeni bir kapı; ayrı bir tur.
8. **`AZURE_FOUNDRY_BASE_URL` formdan temizlenemiyor** (bkz. Sapma 8). Yanlış yazılan adres yenisiyle düzeltilebiliyor; türetmeye dönmek `credentials.env`i elle düzenlemek demek.
9. **Foundry için Ayarlar'da "kayıtlı" satırı YOK.** `settings.js::renderProviderStatus` üç satırı elle sayıyor (`azure_image`, `openai`, `gemini`). Yeni kimlik `providers` haritasında dönüyor ama satırı çizilmiyor; gerçek sinyal şeritteki model satırının `available` alanı. Satır eklemek spec'in "tek yeni `<input>`" kapsamı dışında.
10. **`#model-settings-link` derin bağlantısı `azure-mai`/`azure-flux` için grup SEÇMİYOR.** `openSettings(provider)` eşleşmeyen bir dizeyi `select.value`ya yazmıyor (ikinci kapı), yani panel önceden seçili grupla açılıyor — varsayılan Azure grubu, ki yeni alan tam orada. Kırılma yok; ayrı bir `prov-*` grubu açmak yeni bir sağlayıcı seçeneği demek.
11. **`auto_aspect_ratio` ve `web_grounding` (MAI 2.6)**, **FLUX'un `seed`/`safety_tolerance`/`prompt_upsampling`**, **`cost_for`a boyut ekseni** ve **kaynakta dağıtılmamış FLUX.1 / MAI-2.5 varyantları**: spec'in "Sonraya bırakılan" listesi, olduğu gibi duruyor.
