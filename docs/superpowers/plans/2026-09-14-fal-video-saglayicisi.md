# fal.ai Video Sağlayıcısı — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Video üretimini tek sağlayıcıdan (Gemini · Veo) kurtarmak: fal.ai kuyruk adaptörü ve üç video modeli (Wan 3.0 · PixVerse C1 · Kling V3 Turbo Pro) uçtan uca çalışır hâlde.

**Architecture:** `fal_client.py` kökte düz, yeni bir kuyruk adaptörü: submit → yoklama → sonuç → indirme. Kuyruk adresleri yanıttan DEĞİL güvenilen tabandan kuruluyor, indirme adımı anahtarsız. `ImageModel`'e tek yeni alan (`wire_model_edit`) giriyor çünkü fal'da metin→video ve görsel→video ayrı uçlar. Görsel tablosu (`providers._ADAPTERS`) hiç değişmiyor.

**Tech Stack:** Python 3.13, FastAPI, httpx, pydantic, pytest. Yeni bağımlılık YOK.

**Spec:** [docs/superpowers/specs/2026-09-14-fal-video-saglayicisi-design.md](../specs/2026-09-14-fal-video-saglayicisi-design.md)

## Global Constraints

Her görevin gereksinimleri bu bölümü ÖRTÜK olarak içerir.

- **Yorumlar ve belgeler TÜRKÇE**; test işlev adları İngilizce cümleler (`CLAUDE.md` §5).
- Yorum "ne yaptığını" değil **NEDEN öyle olduğunu** anlatır.
- **Dosyalar KÖKTE ve DÜZ** — `android/app/build.gradle` Chaquopy kaynak kümesini `include "*.py"` ile kuruyor; alt paket APK'ya hiç girmez. Mandal: `tests/test_android_packaging.py`.
- **Dinamik import YASAK.** Adaptör bağlama düz `import` ifadesiyle ve yalnız fonksiyon içinde (`importlib` DEĞİL) — `kromis.spec`'in `hiddenimports=[]` değeri PyInstaller'ın statik analizine dayanıyor.
- **`requirements.txt` DEĞİŞMİYOR.** Yalnız stdlib + zaten kurulu `httpx`.
- Metin dosyası açan her çağrı `encoding` VERMEK ZORUNDA (`tests/test_encoding_contract.py`); satır sonları LF (`.gitattributes`).
- **`providers._ADAPTERS` (görsel tablosu) DEĞİŞMİYOR.** "fal" yalnız `_VIDEO_ADAPTERS`'e giriyor.
- **`catalog.DEFAULT_VIDEO_MODEL` DEĞİŞMİYOR** — `"gemini-veo-3-1-lite"` kalıyor.
- Her görevin sonunda: `python tools/graf_uret.py` ve değişen graf dosyaları **AYNI commit'in İÇİNDE** (`CLAUDE.md` §2).
- Tam takım: `python -m pytest tests/ -q`.
- Commit mesajları Türkçe, `tip(kapsam): özet` biçiminde ve `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` ile bitiyor.

## Dosya Haritası

| dosya | sorumluluk | görev |
| --- | --- | --- |
| `catalog.py` | `wire_model_edit` alanı, `fal` Credential'ı, `FAL_VIDEO_ASPECT_RATIOS`, üç model, `PROVIDER_LOGOS["fal"]` | 2 · 3 · 7 |
| `app.py` | elle yazılmış `fal_key` dalının silinmesi | 3 |
| `static/index.html` | `<option value="fal">` + `#prov-fal` bloğu + `#set-fal-key` | 3 |
| `static/settings.js` | placeholder üçlüsü, `syncProviderFields` listesi, `saglayiciLogosu`nun video düzeltmesi | 3 |
| `fal_client.py` (**yeni**) | fal kuyruk teli: gövde kurma, hata çevirisi, submit/yoklama/indirme | 4 · 5 · 6 |
| `providers.py` | `_fal_adapter` geç bağlaması, `_VIDEO_ADAPTERS["fal"]` | 7 |
| `static/img/providers/fal.svg` (**yeni**) | sağlayıcı işareti | 7 |
| `tests/test_fal_client.py` (**yeni**) | telin tamamı, `FakeClient` dikişiyle | 4 · 5 · 6 |

---

### Task 1: Ölçüm sondası — katalog literalleri buradan doğuyor

Bu görev bir **spike**: ürettiği şey kod değil ÖLÇÜM. Betik depoya GİRMİYOR.

Gerekçe spec'te yazılı: `azure_flux_client.py`'nin başlığı "FLUX'un 200 YANITI BU DEPODAN GÖRÜLMEDİ" diye itiraf ediyor ve bu turun açık hedefi o borcu tekrarlamamak. Görev 7'deki katalog literalleri **yalnız buradan çıkan ölçüme** dayanacak.

**Files:**
- Create: `<scratchpad>/fal_sonda.py` (geçici — depoya girmez, `.gitignore` gerekmez çünkü scratchpad depo dışında)
- Modify: `docs/superpowers/specs/2026-09-14-fal-video-saglayicisi-design.md` (yeni "Ölçüm sonuçları" bölümü)

**Interfaces:**
- Consumes: yok (ilk görev)
- Produces: Görev 7'nin okuyacağı ölçüm tablosu — her model için kabul edilen `duration`, `aspect_ratio`, `resolution` jetonları; 200 yanıtının gerçek yuvalanması; hata gövdesinin anahtarı (`detail` mi `error` mi); saniye başına gerçek ücret.

- [ ] **Step 1: Anahtarın yerinde olduğunu doğrula**

Anahtar sohbete YAZILMIYOR. Kullanıcı `credentials.env`'e (uygulamanın `paths.py` ile bulduğu dosya) `FAL_KEY=…` satırını ekliyor. Doğrulama, değeri GÖSTERMEDEN:

```bash
python -c "import credstore; print('FAL_KEY var mı:', bool(credstore._values().get('FAL_KEY')))"
```

Beklenen: `FAL_KEY var mı: True`

- [ ] **Step 2: Sonda betiğini yaz**

Scratchpad'e `fal_sonda.py`. Deponun kendi `credstore`'undan okuyor, yani anahtar hiçbir yere kopyalanmıyor:

```python
"""fal kuyruk sondası — TEK KULLANIMLIK, depoya girmez.

Ölçtüğü şey: hangi `duration`/`aspect_ratio`/`resolution` jetonları GERÇEKTEN
kabul ediliyor, 200 yanıtı hangi şekilde geliyor, hata gövdesi hangi anahtarı
taşıyor. Katalog literalleri bu çıktıdan yazılacak.
"""
import json
import sys
import time

import httpx

sys.path.insert(0, ".")
import credstore  # noqa: E402

KEY = credstore._values().get("FAL_KEY", "")
assert KEY, "FAL_KEY yok"
TABAN = "https://queue.fal.run"

# En UCUZ istek: en kısa süre, en düşük çözünürlük.
DENEMELER = [
    ("alibaba/wan-3.0/text-to-video",
     {"prompt": "a red cube rotating", "duration": 5,
      "aspect_ratio": "16:9", "resolution": "480p"}),
    ("fal-ai/pixverse/c1/text-to-video",
     {"prompt": "a red cube rotating", "duration": 5,
      "aspect_ratio": "16:9", "resolution": "360p"}),
    ("fal-ai/kling-video/v3/turbo/pro/text-to-video",
     {"prompt": "a red cube rotating", "duration": 5,
      "aspect_ratio": "16:9"}),
]

# Jeton sondaları: SUBMIT'i geçiyor mu? 422 alırsak jeton kabul EDİLMİYOR.
# Kabul edilirse iş kuyruğa giriyor ve ücretleniyor — o yüzden yalnız
# doğrulama aşaması ölçülüyor, sonuç BEKLENMİYOR.
JETON_SONDALARI = [
    ("alibaba/wan-3.0/text-to-video", "duration", [10, 15]),
    ("fal-ai/pixverse/c1/text-to-video", "duration", [10, 15]),
    ("fal-ai/kling-video/v3/turbo/pro/text-to-video", "duration", [10, 15]),
    ("fal-ai/kling-video/v3/turbo/pro/image-to-video", "aspect_ratio", ["16:9"]),
]


def gonder(client, yol, govde):
    r = client.post(f"{TABAN}/{yol}",
                    headers={"Authorization": f"Key {KEY}",
                             "Content-Type": "application/json"},
                    json=govde, timeout=60.0)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"_ham": r.text[:500]}


def main():
    with httpx.Client() as client:
        for yol, govde in DENEMELER:
            kod, gvd = gonder(client, yol, govde)
            print(f"\n=== SUBMIT {yol} -> {kod}")
            print(json.dumps(gvd, indent=2, ensure_ascii=False)[:900])
            if kod != 200:
                continue
            rid = gvd.get("request_id")
            # Adresi TABANDAN kuruyoruz — ürün kodunun yapacağının aynısı.
            durum_url = f"{TABAN}/{yol}/requests/{rid}/status"
            sonuc_url = f"{TABAN}/{yol}/requests/{rid}"
            son = time.monotonic() + 600
            while time.monotonic() < son:
                d = client.get(durum_url,
                               headers={"Authorization": f"Key {KEY}"},
                               timeout=30.0).json()
                print("   durum:", d.get("status"), d.get("queue_position"))
                if d.get("status") == "COMPLETED":
                    break
                time.sleep(5)
            s = client.get(sonuc_url,
                           headers={"Authorization": f"Key {KEY}"},
                           timeout=60.0).json()
            print("--- SONUÇ ŞEKLİ:")
            print(json.dumps(s, indent=2, ensure_ascii=False)[:1200])

        for yol, alan, degerler in JETON_SONDALARI:
            for deger in degerler:
                govde = {"prompt": "a red cube rotating", alan: deger}
                if "image-to-video" in yol:
                    # 1x1 saydam PNG — en ucuz geçerli referans.
                    govde["image_url"] = (
                        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEA"
                        "AAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
                kod, gvd = gonder(client, yol, govde)
                print(f"\n=== JETON {yol} {alan}={deger} -> {kod}")
                if kod != 200:
                    print(json.dumps(gvd, indent=2, ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Sondayı çalıştır**

```bash
python "$SCRATCHPAD/fal_sonda.py" 2>&1 | tee "$SCRATCHPAD/fal_olcum.txt"
```

Beklenen: üç SUBMIT için `200` ve `request_id`; `COMPLETED` sonrası `{"video": {"url": …}}` şekli. Jeton sondalarında `200` = jeton KABUL, `422` = jeton RED.

Tahmini maliyet 1 USD altı. `202`/`403`/`402` görürsen dur ve bildir — bakiye ya da yetki sorunudur.

- [ ] **Step 4: Ölçümü spec'e yaz**

Spec'in sonuna, "Riskler" bölümünden ÖNCE:

```markdown
## Ölçüm sonuçları (2026-09-14, canlı uçtan)

| model | kabul edilen `duration` | `aspect_ratio` | `resolution` | USD/sn |
| --- | --- | --- | --- | --- |
| Wan 3.0 | … | … | … | … |
| PixVerse C1 | … | … | … | … |
| Kling V3 Turbo Pro | … | … | … | … |

200 yanıtının şekli: `…`
Hata gövdesinin anahtarı: `…`
Kling i2v `aspect_ratio`'yu reddediyor mu: `…`

Katalog literalleri (Görev 7) YALNIZ bu tablodan yazıldı.
```

Tabloyu Step 3'ün çıktısından doldur. **Tahmin yazma** — ölçülemeyen bir hücreye `ölçülemedi (sebep)` yaz.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-09-14-fal-video-saglayicisi-design.md
git commit -m "docs(spec): fal telinin canlı ölçümü — katalog literallerinin dayanağı"
```

---

### Task 2: `ImageModel.wire_model_edit`

fal'da metin→video ve görsel→video AYRI uçlar; `wire_model` tek alan. Varsayılanı `""` olduğu için mevcut on üç girdinin baytı değişmiyor.

**Files:**
- Modify: `catalog.py` (`ImageModel` dataclass — alan `credits`ten SONRA, bkz. Step 3'ün "Yer bağlayıcı" notu)
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: yok
- Produces: `catalog.ImageModel.wire_model_edit: str` (varsayılan `""`). Görev 4 ve 6 bunu okuyor; Görev 7 dolduruyor.

- [ ] **Step 1: Write the failing test**

`tests/test_catalog.py` sonuna:

```python
def test_wire_model_edit_defaults_to_empty_on_every_existing_entry():
    """Alan EKLENİYOR ama mevcut girdilerin hiçbirinin telini değiştirmiyor.

    Varsayılanın "" olması, "düzenleme ve üretim AYNI uca gidiyor" demek —
    Azure, OpenAI, Gemini, MAI, FLUX ve Veo'nun tamamı böyle. Bu test alanın
    varsayılanını mandallıyor: bir gün varsayılan değişirse on üç girdi
    sessizce başka bir uca gitmeye başlardı.
    """
    for m in catalog.IMAGE_MODELS + catalog.VIDEO_MODELS:
        assert m.wire_model_edit == "", f"{m.id} beklenmedik ikinci tel yolu"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_catalog.py::test_wire_model_edit_defaults_to_empty_on_every_existing_entry -q`
Expected: FAIL — `AttributeError: 'ImageModel' object has no attribute 'wire_model_edit'`

- [ ] **Step 3: Write minimal implementation**

`catalog.py`, `ImageModel` içinde `wire_model: str` satırının HEMEN ALTINA:

```python
    # İKİNCİ TEL YOLU (`wire_model`in ikizi) — yalnız uçları AYRIŞMIŞ
    # sağlayıcıda dolu.
    #
    # BURADA, `wire_model`in yanında DEĞİL: `dataclasses` varsayılanlı bir
    # alandan sonra varsayılansız alan kabul etmiyor ve `wire_model`i
    # `credential`, `sizes`, `qualities`, `max_n`, `credits` izliyor. Yerleşim
    # teknik zorunluluk, üslup tercihi değil.
    #
    # fal.ai'da metin→video ve görsel→video AYRI uçlar
    # (`…/text-to-video` ≠ `…/image-to-video`), oysa Azure, Gemini, MAI ve
    # FLUX'ta düzenleme aynı ucun bir ALANI. "" = ikisi aynı uca gidiyor,
    # yani bugünkü on üç girdinin hiçbirinin teli değişmiyor.
    #
    # UÇ YOLUNU ADAPTÖRDE TÜRETMEK reddedildi: kural ilk istisnada kırılıyor
    # (`fal-ai/veo3.1` metin tarafında ÇIPLAK, görsel tarafında
    # `/image-to-video`) ve kırılma telde 404 olarak görünürdü — bu dosyanın
    # her yerde uyardığı "arayüzde seçilebilir hata".
    #
    # MODEL BAŞINA İKİ GİRDİ de reddedildi: şerit iki kart gösterir ve
    # kullanıcı "(metin)" / "(görsel)" ayrımını elle yapardı — oysa
    # `supports_edit` bayrağı tam olarak bu ayrımı SAKLAMAK için var.
    wire_model_edit: str = ""
```

**Yer bağlayıcı:** alan `wire_model`'in hemen altında ve **varsayılanlı**, yani varsayılansız alanlardan SONRA gelmeli. `ImageModel`'de `credential`, `sizes`, `qualities`, `max_n`, `credits` varsayılansız; dataclass varsayılanlı bir alanın ardından varsayılansız alan kabul etmez. Bu yüzden alan **`credits`ten sonra**, `images_per_request` ile aynı bloğa konuyor — yorum yine `wire_model`e atıf yapıyor.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_catalog.py -q`
Expected: PASS (tüm katalog testleri)

- [ ] **Step 5: Graf + tam takım + commit**

```bash
python tools/graf_uret.py
python -m pytest tests/ -q
git add catalog.py tests/test_catalog.py docs/graflar/
git commit -m "feat(katalog): ImageModel'e wire_model_edit — uçları ayrışmış sağlayıcı için ikinci tel yolu"
```

---

### Task 3: `fal` kimliği uçtan uca — katalog, rota ve Ayarlar formu

Tek görev, çünkü bir gözden geçiren bunları **tek soruyla** kabul ya da reddediyor: "kullanıcı fal anahtarını Ayarlar'dan kaydedebiliyor mu?"

**Beklenmedik bulgu (spec, Karar 2):** `fal_key` v0.2.0'dan beri `POST /api/settings`'te kabul ediliyor ama `index.html`'de HİÇBİR alanı yok — bugün ancak `curl` ile yazılabiliyor.

**İkinci bulgu:** `settings.js:254` `saglayiciLogosu` yalnız `imageModels` içinde arıyor. fal **video-only** bir sağlayıcı, yani logosu Görev 7'den sonra bile sessizce hiç görünmezdi. `test_provider_logos.py`'nin başlığı bu sınıfı zaten adlandırıyor: "logo kusurları SESSİZ".

**Files:**
- Modify: `catalog.py` (`CREDENTIALS` demeti)
- Modify: `app.py:1222-1225` (elle yazılmış `fal_key` dalı siliniyor)
- Modify: `static/index.html` (`#set-provider` seçeneği + `#prov-fal` bloğu)
- Modify: `static/settings.js` (placeholder üçlüsü, `syncProviderFields`, `saglayiciLogosu`)
- Test: `tests/test_settings_route.py`, `tests/test_id_contract.py`

**Interfaces:**
- Consumes: yok
- Produces: `catalog.Credential(id="fal")` — Görev 7'deki üç model `credential="fal"` diyecek. `credstore.resolve("fal")` → `(key, "https://queue.fal.run")`; Görev 6 bunu çağırıyor.

- [ ] **Step 1: Write the failing tests**

`tests/test_settings_route.py` sonuna:

```python
def test_fal_key_is_written_through_the_catalog_loop():
    """`fal_key` artık KATALOGDAN yazılıyor, elle yazılmış bir daldan değil.

    Ayrım görünmez değil: katalog döngüsü aynı anda REDAKSİYONU da veriyor
    (`app._redact_validation_errors` gizli alan adlarını `CREDENTIALS`tan
    türetiyor). Elle yazılmış dal o türetmenin DIŞINDAYDI ve `Credential`
    docstring'i bunu "listenin elle tutulmasının bedeli" diye yazıyor.
    """
    cred = next(c for c in catalog.CREDENTIALS if c.id == "fal")
    assert cred.key_env == "FAL_KEY"
    assert cred.secret_field == "fal_key"
    assert cred.default_base_url == "https://queue.fal.run"
    # Adres alanı forma GİRMİYOR: fal'da kullanıcıya özel endpoint yok.
    assert cred.url_field is None


def test_fal_key_is_redacted_from_validation_errors():
    """Gizli alan kümesi katalogdan türediği için `fal_key` artık kapsamda."""
    assert "fal_key" in catalog.secret_field_names()
```

**`tests/test_id_contract.py`'ye DOKUNULMUYOR** ve bunu bilerek yazıyorum, çünkü ilk bakışta tersi görünüyor: o dosya `docs/flow-ui/id-baseline.txt`'teki 152 id'yi donduruyor ama iddiası **KALDIRILAN** id üzerine ("kayıp id defterde yazılı mı", "kaldırılan id'nin JS bağı da gitmiş mi"). YENİ id eklemek defter kaydı İSTEMİYOR; `test_baseline_matches_frozen_commit` de taban dosyasının uzunluğunu ölçüyor, HTML'inkini değil. Tek dolaylı kapı `test_toplevel_baglar_htmlde_duruyor` — ve Step 7'deki `settings.js` değişiklikleri fonksiyon İÇİNDE, üst düzeyde değil, yani o kapı da tetiklenmiyor.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_settings_route.py -q -k fal`
Expected: FAIL — `StopIteration` (katalogda `fal` kimliği yok)

- [ ] **Step 3: Kataloğa kimliği ekle**

`catalog.py`, `CREDENTIALS` demetinin SONUNA (`azure_foundry`'den sonra):

```python
    # fal.ai — TOPLAYICI: tek anahtar, çok model. Bu tur yalnız VİDEO
    # tarafında kullanılıyor (`providers._VIDEO_ADAPTERS`), görsel tablosuna
    # girmiyor.
    #
    # `FAL_KEY` YENİ DEĞİL: v0.2.0'dan beri `POST /api/settings`'te kabul
    # ediliyordu ama kataloğa girmediği için FORMUN DIŞINDAYDI — bugüne kadar
    # yalnız `curl` ile yazılabiliyordu. REDAKSİYONUN dışında değildi:
    # `app._SECRET_SUFFIXES` adı `_key` ile biten her alanı kataloğa
    # bakmaksızın zaten redakte ediyordu (bkz. Görev 8'in 2026-09-15
    # düzeltmesi, design.md "Karar 2").
    #
    # `url_field=None` ve bu `azure_chat`in duruşunun aynısı: fal'da
    # kullanıcıya özel endpoint YOK, adres tek ve sabit. Vekil arkasına almak
    # isteyen `credentials.env`'e `FAL_BASE_URL` yazıyor — forma alan
    # eklemeden (OpenAI girdisindeki aynı gerekçe).
    Credential(
        id="fal",
        label="fal.ai",
        key_env="FAL_KEY",
        url_env="FAL_BASE_URL",
        default_base_url="https://queue.fal.run",
        secret_field="fal_key",
        url_field=None,
    ),
```

- [ ] **Step 4: `app.py`'deki elle yazılmış dalı sil**

`app.py:1222-1225`'te ŞU İKİ SATIR siliniyor (blok yorumu ve `replicate_api_token` KALIYOR):

```python
        if req.fal_key is not None and req.fal_key.strip():
            updates["FAL_KEY"] = req.fal_key.strip()
```

Blok yorumunu güncelle — artık yalnız `replicate_api_token` için geçerli:

```python
        # Kataloğa girmemiş eski BYOK alanları. Katalog döngüsünün DIŞINDA
        # bilerek: bunların henüz bir modeli ve adaptörü yok, kataloğa yazmak
        # "bağlı" gibi görünmelerine yol açardı. Yazma yolu korunuyor çünkü
        # v0.2.0'dan beri kaydediliyorlar ve veri kaybı olmamalı.
        #
        # `fal_key` BURADAN ÇIKTI: adaptörü geldi, kataloğa girdi ve yukarıdaki
        # `for cred in catalog.CREDENTIALS` döngüsü onu aynı env'e aynı
        # "boş = dokunma" kuralıyla yazıyor. (Redaksiyonu "kendiliğinden
        # kapsıyor" DEMEK YANLIŞ olurdu — `_SECRET_SUFFIXES` onu zaten
        # kapsıyordu; kazanılan şey YAZMA yolu, bkz. yukarıdaki not.)
```

**DÜZELTME NOTU (Görev 8, 2026-09-15):** bu adımın kod yorumu taslağı
(yukarıdaki fenced blok) yürürlükteki `app.py`'ye ("üstelik redaksiyonu da
kendiliğinden kapsıyor") birebir bu hâliyle girdi ve o cümle YANLIŞ —
redaksiyon `fal_key`i kataloğa girmeden ÖNCE de kapsıyordu
(`_SECRET_SUFFIXES`, bkz. design.md "Karar 2"). Bu plan belgesindeki taslak
düzeltildi; canlı `app.py`deki asıl yorum bu turun kapsamı DIŞINDA bırakıldı
(brief yalnız iki belgeyi — design.md ve bu dosyayı — adlandırdı, kaynak
dosyayı değil) ve ayrı bir iş olarak işaretlendi.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_settings_route.py tests/test_settings.py tests/test_catalog.py -q`
Expected: PASS

- [ ] **Step 6: Forma alanı ekle**

`static/index.html`, `#set-provider` seçicisine (`gemini` seçeneğinden sonra):

```html
        <option value="fal">fal.ai</option>
```

Ardından `prov-gemini` bloğunun yanına, aynı kalıpla:

```html
      <!-- fal.ai — yalnız VİDEO modelleri. Adres alanı YOK: fal'da
           kullanıcıya özel endpoint yok (bkz. catalog.Credential id="fal"). -->
      <div id="prov-fal" hidden>
        <label for="set-fal-key">fal.ai API anahtarı</label>
        <input id="set-fal-key" type="password" autocomplete="off"
               spellcheck="false" placeholder="fal anahtarı">
      </div>
```

- [ ] **Step 7: `settings.js`'in üç elle yazılmış listesini güncelle**

```js
      ["set-openai-key", "openai", "sk-…"],
      ["set-gemini-key", "gemini", "AIza…"],
      ["set-fal-key", "fal", "fal anahtarı"],
```

```js
  for (const p of ["azure", "openai", "gemini", "fal"]) {
    $(`prov-${p}`).hidden = p !== secili;
  }
```

Ve `saglayiciLogosu` — bulgunun düzeltmesi:

```js
function saglayiciLogosu(deger) {
  // İKİ KATALOG birden taranıyor ve bu bir tamlık düzeltmesi değil, ÖLÇÜLMÜŞ
  // bir sessiz kusur: fal yalnız VİDEO sağlayıcısı, yani `imageModels`te HİÇ
  // görünmüyor ve tek başına o listeye bakmak fal'ın işaretini kalıcı olarak
  // kaybettirirdi. Kusur sessiz olurdu — kutu boş kalır, konsolda bir şey
  // yazmaz (test_provider_logos.py'nin başlığındaki sınıfın aynısı).
  const m = imageModels.find((x) => x.provider === deger)
         || videoModels.find((x) => x.provider === deger);
  return m && m.logo;
}
```

- [ ] **Step 8: Graf + tam takım + commit**

```bash
python tools/graf_uret.py
python -m pytest tests/ -q
git add catalog.py app.py static/index.html static/settings.js tests/ docs/graflar/
git commit -m "feat(ayarlar): fal.ai kimliği kataloğa girdi, anahtar forma geldi"
```

---

### Task 4: `fal_client.build_payload` ve uç → alan tablosu

Yaklaşım 1'in taşıyıcı parçası. Katalog "bu model ne yapabiliyor" diyor; bu tablo "bu uç hangi adı okuyor".

**Files:**
- Create: `fal_client.py`
- Test: `tests/test_fal_client.py`

**Interfaces:**
- Consumes: `catalog.ImageModel.wire_model_edit` (Görev 2)
- Produces:
  - `fal_client.ALANLAR: dict[str, tuple[frozenset[str], frozenset[str]]]`
  - `fal_client.wire_path_for(m: catalog.ImageModel, *, images) -> str`
  - `fal_client.build_payload(m, prompt: str, size: str, quality: str, duration: int, images) -> dict`

**NOT:** Testler kendi `catalog.ImageModel(...)` örneklerini kuruyor, `catalog.video_model(...)` ÇAĞIRMIYOR — katalog girdileri Görev 7'de geliyor ve gövde kurucusu ondan önce sınanabilir olmalı.

- [ ] **Step 1: Write the failing test**

`tests/test_fal_client.py` (yeni):

```python
"""fal_client: gövde kurma, uç seçimi ve alan tablosu.

Bu dosyanın en değerli iddiası ALAN TABLOSU. 2026-09-14'te canlı uçtan
ÖLÇÜLDÜ ki beyan edilmemiş bir alan 422 ÜRETMİYOR, SESSİZCE YOK SAYILIYOR —
Kling'in görsel→video ucu, şemasında hiç olmayan `aspect_ratio` ile şema
doğrulamasını geçti. Bu tabloyu gereksiz değil DAHA GEREKLİ kılıyor: 422
kendini gösterir, sessiz yok sayım göstermez. Kullanıcı 9:16 seçer, tel kabul
eder, video 16:9 döner ve hiçbir yerde hata okunmaz.

Model örnekleri BURADA kuruluyor, `catalog`tan okunmuyor: gövde kurucusu
katalog girdilerinden ÖNCE sınanabilir olmalı.
"""
import base64

import pytest

import catalog
import fal_client


def _model(model_id, wire, wire_edit):
    return catalog.ImageModel(
        id=model_id, label=model_id, provider="fal",
        wire_model=wire, wire_model_edit=wire_edit, credential="fal",
        sizes=("16:9", "9:16", "1:1"), qualities=("720p",), max_n=1,
        credits=16, durations=(5, 10), kind="video", supports_edit=True)


WAN = _model("fal-wan-3-0",
             "alibaba/wan-3.0/text-to-video",
             "alibaba/wan-3.0/image-to-video")
KLING = _model("fal-kling-v3-turbo-pro",
               "fal-ai/kling-video/v3/turbo/pro/text-to-video",
               "fal-ai/kling-video/v3/turbo/pro/image-to-video")

PNG = b"\x89PNG\r\n\x1a\n"
REFS = [("ilk.png", PNG)]


def test_the_edit_path_uses_the_SECOND_wire_endpoint():
    assert fal_client.wire_path_for(WAN, images=None) == WAN.wire_model
    assert fal_client.wire_path_for(WAN, images=REFS) == WAN.wire_model_edit


def test_wan_text_to_video_sends_aspect_ratio_and_resolution():
    p = fal_client.build_payload(WAN, "kedi", "16:9", "720p", 5, None)
    assert p == {"prompt": "kedi", "aspect_ratio": "16:9",
                 "resolution": "720p", "duration": 5}


def test_kling_IMAGE_to_video_sends_NEITHER_aspect_ratio_NOR_resolution():
    """Kling'in i2v şemasında o iki alan HİÇ yok.

    Göndermek 422 DEĞİL, SESSİZ SAPMA üretir (ölçüldü 2026-09-14): tel alanı
    kabul eder, kullanır mı belli değil, kullanıcı seçtiği oranı aldığını
    SANIR. Testin ölçtüğü şey gövdenin kendisi, telin cevabı değil — zaten
    bu yüzden ölçülebilir.
    """
    p = fal_client.build_payload(KLING, "kedi", "16:9", "1080p", 5, REFS)
    assert "aspect_ratio" not in p
    assert "resolution" not in p
    assert p["prompt"] == "kedi"
    assert p["duration"] == 5


def test_the_reference_image_travels_as_a_base64_data_uri():
    """Yükleme adımı YOK — `gemini_client`in inlineData duruşunun aynısı."""
    p = fal_client.build_payload(WAN, "kedi", "16:9", "720p", 5, REFS)
    onek = "data:image/png;base64,"
    assert p["image_url"].startswith(onek)
    assert base64.b64decode(p["image_url"][len(onek):]) == PNG


def test_only_the_FIRST_reference_is_sent():
    """`max_refs=1`; fazlası app.animate'in kapısında zaten eleniyor."""
    p = fal_client.build_payload(WAN, "kedi", "16:9", "720p", 5,
                                 [("bir.png", PNG), ("iki.png", b"XX")])
    assert base64.b64decode(p["image_url"].split(",", 1)[1]) == PNG


def test_every_field_table_entry_declares_prompt_and_only_i2v_takes_image_url():
    """Tablo ile katalog ayrışırsa gövde SESSİZCE boşalır — mandal bu."""
    for model_id, (t2v, i2v) in fal_client.ALANLAR.items():
        assert "prompt" in t2v and "prompt" in i2v, model_id
        assert "image_url" in i2v and "image_url" not in t2v, model_id


@pytest.mark.parametrize("tam_yol, uygulama", [
    ("alibaba/wan-3.0/text-to-video", "alibaba/wan-3.0"),
    ("alibaba/wan-3.0/image-to-video", "alibaba/wan-3.0"),
    ("fal-ai/pixverse/c1/text-to-video", "fal-ai/pixverse"),
    ("fal-ai/kling-video/v3/turbo/pro/text-to-video", "fal-ai/kling-video"),
    ("fal-ai/kling-video/v3/turbo/pro/image-to-video", "fal-ai/kling-video"),
])
def test_the_queue_path_keeps_only_the_owner_and_app_segments(tam_yol, uygulama):
    """ÖLÇÜLMÜŞ olgu (2026-09-14): yoklama adresi gönderim adresi DEĞİL.

    Tam yolla kurulan adres 404 değil BOŞ GÖVDE döndürüyor — yani döngü
    sessizce ölüyor ve üretim duvar saatine kadar bekliyor. Bu test o sessiz
    kusurun mandalı.
    """
    assert fal_client.queue_app_path(tam_yol) == uygulama
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fal_client.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fal_client'`

- [ ] **Step 3: Write minimal implementation**

`fal_client.py` (yeni, kökte):

```python
"""fal.ai kuyruk teli — Wan · PixVerse · Kling (VİDEO).

Deponun BEŞİNCİ tel formatı ve ilk TOPLAYICISI: tek anahtar, çok marka.
Sağlayıcı `providers._VIDEO_ADAPTERS`'e giriyor, `_ADAPTERS`'e GİRMİYOR —
görsel yolunun telde ürettiği baytlar bu turda dokunulmadan kalıyor.

DOSYA BÖLÜNMÜYOR (`azure_mai_client`/`azure_flux_client` gibi değil) ve
gerekçe o bölünmenin ÖLÇÜTÜNDEN geliyor: orada iki AYRI tel formatı vardı
(farklı yol, farklı gövde, farklı hata şekli). fal'da protokol TEK; modeller
arasında değişen yalnız ALAN ADLARI ve onlar `ALANLAR` tablosunda. fal'ın
görsel tarafı geldiği gün `generate`/`edit` BU dosyaya eklenecek.

DOSYA ADI PyPI'daki resmî `fal-client` paketini GÖLGELİYOR. O paket
kullanılmıyor ve kullanılmamalı: BYOK tasarımı yalnız `httpx` istiyor,
`kromis.spec`'in `hiddenimports=[]` değeri yeni bir bağımlılığı analiz
edemez ve Chaquopy kaynak kümesi `include "*.py"` ile kurulu. Biri
`fal-client`ı `requirements.txt`e eklerse kök modülü ONUN önüne geçer ve
hata yalnız o paketi kullanmaya çalışan kodda görünür.

DOSYA KÖKTE ve DÜZ olmak ZORUNDA (Chaquopy; bkz. tests/test_android_packaging.py).

ALAN TABLOSU (`ALANLAR`) bu dosyanın taşıyıcı kararı ve gerekçesi ÖLÇÜLDÜ
(2026-09-14, canlı uç):

  **Beyan edilmemiş alan 422 ÜRETMİYOR — SESSİZCE YOK SAYILIYOR.** Kling'in
  görsel→video ucuna, şemasında hiç olmayan `aspect_ratio` gönderildi ve
  istek şema doğrulamasını GEÇTİ. İlk tasarımın "fal pydantic tabanlı, yani
  fazladan alan 422 demek" varsayımı YANLIŞ çıktı.

Bu, tabloyu gereksiz kılmıyor — TAM TERSİ, daha gerekli kılıyor. 422 gürültülü
bir hatadır ve kendini gösterir; sessiz yok sayım göstermez: kullanıcı 9:16
seçer, tel isteği kabul eder, video 16:9 döner ve hiçbir yerde bir hata
okunmaz. Bu deponun her yerde adlandırdığı SESSİZ SAPMA'nın tam kendisi.

Kling'in görsel→video ucu `aspect_ratio` ve `resolution` alanlarını şemasında
SAYMIYOR (oranı ilk kareden türetiyor), metin ucu ise sayıyor; katalog
`sizes`ı yine beyan ediyor çünkü metin yolunda GERÇEK. Adaptör düzenleme
yolunda onu sessizce değil, TABLOYA BAKARAK düşürüyor.
"""
from __future__ import annotations

import base64

import catalog

# Yüklenen referans karenin MIME'ı. `app._to_png` girdiyi koşulsuz PNG'ye
# çevirdiği için sağlayıcıya sorulacak bir şey yok (`veo_client.PNG_MIME`
# ile aynı olgu).
PNG_MIME = "image/png"

# model id → (metin→video alanları, görsel→video alanları).
#
# KATALOGDA DEĞİL BURADA: katalog "bu model ne yapabiliyor" diyor (yetenek
# beyanı, arayüz onu okuyor), bu tablo "bu uç hangi adı okuyor" (tel biçimi,
# yalnız bu dosya okuyor). İkisini karıştırmak, arayüzün tel ayrıntısına
# bağlanması demekti.
ALANLAR: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "fal-wan-3-0": (
        frozenset({"prompt", "resolution", "aspect_ratio", "duration"}),
        frozenset({"prompt", "image_url", "resolution", "duration"}),
    ),
    "fal-pixverse-c1": (
        frozenset({"prompt", "resolution", "aspect_ratio", "duration"}),
        frozenset({"prompt", "image_url", "resolution", "duration"}),
    ),
    # Kling: `resolution` İKİ uçta da YOK (şema o alanı saymıyor; katalogda
    # `quality_hidden=True` ile tek sentetik jeton duruyor) ve `aspect_ratio`
    # yalnız METİN ucunda var.
    "fal-kling-v3-turbo-pro": (
        frozenset({"prompt", "aspect_ratio", "duration"}),
        frozenset({"prompt", "image_url", "duration"}),
    ),
}


def wire_path_for(m: catalog.ImageModel, *, images) -> str:
    """İstek hangi uca gidecek: metin→video mu, görsel→video mu.

    `wire_model_edit` BOŞSA `wire_model`e düşülüyor. Bu düşüş fal'da hiç
    yaşanmamalı (katalog mandalı boş bırakmayı yasaklıyor), ama sözleşme
    deponun geri kalanıyla tutarlı kalsın diye burada: uçları ayrışmamış bir
    sağlayıcı aynı yolu iki kez beyan etmek zorunda değil.
    """
    if images:
        return m.wire_model_edit or m.wire_model
    return m.wire_model


# Kuyruk adresinin taşıdığı segment sayısı — ÖLÇÜLMÜŞ bir sabit.
_UYGULAMA_SEGMENTI = 2


def queue_app_path(wire_path: str) -> str:
    """Kuyruk adreslerinin (`/requests/…`) kullandığı UYGULAMA yolu.

    GÖNDERİM yolu ile YOKLAMA yolu AYNI DEĞİL ve bu 2026-09-14'te canlı uçtan
    ölçüldü:

        gönderim : queue.fal.run/fal-ai/kling-video/v3/turbo/pro/text-to-video
        yoklama  : queue.fal.run/fal-ai/kling-video/requests/<id>/status

    Yani kuyruk adresi tam uç yolunu DEĞİL, yalnız ilk iki segmenti
    (sahip/uygulama) taşıyor; `v3/turbo/pro/text-to-video` düşüyor.

    NEDEN BU KADAR ÖNEMLİ: tam yolla kurulan adres 404 DÖNDÜRMÜYOR, BOŞ GÖVDE
    döndürüyor — yani döngü hatayla değil SESSİZCE ölüyor ve üretim duvar
    saatine kadar bekliyor. Ölçümde PixVerse ve Kling'in izlemesi tam bu
    yüzden 600 saniye boşa gitti; aynı `request_id`ler doğru adresle
    sorgulandığında ZATEN tamamlanmıştı. İptal `PUT`'u da aynı sebeple 405
    dönüyordu.

    Bu, adresin GÖVDEDEN alınmama kararını (bkz. `_durum_url`) değiştirmiyor
    — yalnız tabandan TÜRETME kuralını düzeltiyor.
    """
    parcalar = [p for p in wire_path.strip("/").split("/") if p]
    return "/".join(parcalar[:_UYGULAMA_SEGMENTI])


def _data_uri(png: bytes) -> str:
    """Referans kareyi base64 data URI'ye çevirir.

    YÜKLEME ADIMI YOK ve bu bilinçli: fal'ın dosya deposu ikinci bir kimlik
    yüzeyi, ikinci bir hata dalı ve ömrü sınırlı bir CDN adresi demekti.
    fal data URI'yi açıkça destekliyor; `gemini_client`in `inlineData`
    duruşunun aynısı.
    """
    return f"data:{PNG_MIME};base64," + base64.b64encode(png).decode("ascii")


def build_payload(m: catalog.ImageModel, prompt: str, size: str, quality: str,
                  duration: int, images) -> dict:
    """İstek gövdesi — YALNIZ `ALANLAR`ın izin verdiği anahtarlar.

    Süzgeç `ALANLAR`dan geçiyor, `if model_id == …` zincirinden DEĞİL: zincir
    her yeni modelde büyür ve bir dalı unutmak, beyan edilmemiş alan göndermek
    (422) ya da gerekli alanı düşürmek demekti.

    `images` sıralı [(dosya_adı, png_baytları), ...]; YALNIZ İLKİ kullanılıyor
    (`max_refs=1`). Fazlası `app.animate`in kapısında zaten eleniyor, ama
    burada da kesiliyor — `providers.edit`in ikinci kapı disiplini.
    """
    t2v, i2v = ALANLAR[m.id]
    izin = i2v if images else t2v
    tum = {
        "prompt": prompt,
        "aspect_ratio": size,
        "resolution": quality,
        "duration": duration,
    }
    if images:
        tum["image_url"] = _data_uri(images[0][1])
    return {ad: deger for ad, deger in tum.items() if ad in izin}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fal_client.py -q`
Expected: PASS (6 test)

- [ ] **Step 5: Graf + commit**

```bash
python tools/graf_uret.py
python -m pytest tests/ -q
git add fal_client.py tests/test_fal_client.py docs/graflar/
git commit -m "feat(fal): gövde kurucusu ve uç-alan tablosu"
```

---

### Task 5: `fal_client.map_error`

**Files:**
- Modify: `fal_client.py`
- Test: `tests/test_fal_client.py`

**Interfaces:**
- Consumes: `providers.detail_of`, `providers.is_invalid_key`, `providers.is_content_policy`
- Produces: `fal_client.map_error(status_code: int, body: dict | list | None) -> str`, `fal_client.detail_of(body) -> str`

- [ ] **Step 1: Write the failing test**

`tests/test_fal_client.py` sonuna:

```python
# ── Hata çevirisi ──────────────────────────────────────────────────────


def test_top_level_detail_list_is_read_like_fluxs_error_details():
    """fal FastAPI tabanlı: doğrulama hatası ÜST DÜZEY `detail` listesi.

    `providers.detail_of` `error.details[]` okuyor, üst düzey `detail`i
    DEĞİL — ve o fonksiyona dokunmak Azure/OpenAI/Gemini/FLUX yolunun
    baytlarını değiştirirdi. Sarmal bu yüzden burada.
    """
    govde = {"detail": [{"loc": ["body", "duration"],
                         "msg": "value is not a valid enumeration member"}]}
    assert "duration" in fal_client.detail_of(govde)


def test_a_plain_error_string_still_resolves():
    """Kuyruk `COMPLETED` iken hatayı düz bir dize olarak taşıyabiliyor."""
    assert fal_client.detail_of({"error": "boom"}) == "boom"


def test_401_names_the_fal_key_and_not_a_generic_key():
    mesaj = fal_client.map_error(401, {"detail": "Unauthorized"})
    assert "fal" in mesaj.lower()
    assert "401" in mesaj


def test_402_talks_about_BALANCE_and_never_about_the_key():
    """fal ÖN ÖDEMELİ. 'Anahtarını kontrol et' demek, anahtarı doğru olan
    kullanıcıyı çalışan kurulumunu bozmaya davet etmek olurdu —
    `veo_client`in 403/429 dalının birebir gerekçesi."""
    mesaj = fal_client.map_error(402, {"detail": "insufficient balance"})
    assert "bakiye" in mesaj.lower()
    assert "anahtar" not in mesaj.lower()


def test_429_talks_about_CONCURRENCY_and_not_about_the_key():
    mesaj = fal_client.map_error(429, None)
    assert "eşzamanlı" in mesaj.lower()
    assert "anahtar" not in mesaj.lower()


def test_content_refusal_is_recognised_through_the_shared_predicate():
    mesaj = fal_client.map_error(400, {"detail": "flagged by safety checker"})
    assert "içerik" in mesaj.lower()


def test_an_unknown_status_still_carries_the_detail():
    mesaj = fal_client.map_error(503, {"detail": "upstream down"})
    assert "503" in mesaj and "upstream down" in mesaj
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fal_client.py -q -k "error or detail or 401 or 402 or 429 or content"`
Expected: FAIL — `AttributeError: module 'fal_client' has no attribute 'detail_of'`

- [ ] **Step 3: Write minimal implementation**

`fal_client.py`'ye — `import providers` modül düzeyine EKLENMİYOR (döngü), `providers` bu dosyayı import etmiyor ama bu dosya `providers`ı import ediyor; `providers._fal_adapter` fonksiyon içinden bağladığı için modül düzeyinde `import providers` GÜVENLİ (aynı desen `veo_client`, `gemini_client`, `azure_flux_client`de zaten var). Üst kısma ekle:

```python
import azure_client as ac
import credstore
import providers
```

Ardından:

```python
def detail_of(body: dict | list | None) -> str:
    """`providers.detail_of`un fal sarmalı — ÜST DÜZEY `detail` de okunuyor.

    `providers.detail_of` iki şekil tanıyor: `{"error": {"message": …}}` ve
    onun `details[]` listesi. fal FastAPI/pydantic tabanlı olduğu için
    doğrulama hatasını ÜST DÜZEYDE taşıyor —

        {"detail": [{"loc": ["body", "duration"], "msg": "…"}]}

    — yani paylaşılan fonksiyon boş dize döndürür ve BÜTÜN 422'ler çıplak bir
    "HTTP 422"ya çöker. Tam olarak FLUX'un `error.details[]` dalının var olma
    sebebi, dördüncü bir şekilde.

    `providers.detail_of` DEĞİŞTİRİLMİYOR: Azure, OpenAI, Gemini ve FLUX'un
    yolları bayt bayt aynı kalmalı ve o fonksiyonun docstring'i hangi şekli
    neden tanıdığını tek tek sayıyor. Sarmal, o listeyi `error.details`
    konumuna TAŞIYIP aynı ayrıştırıcıya veriyor — ikinci bir `{loc, msg}`
    çözümleyicisi yazmamak için.
    """
    paylasilan = providers.detail_of(body)
    if paylasilan:
        return paylasilan
    if isinstance(body, list) and len(body) == 1:
        body = body[0]
    if not isinstance(body, dict):
        return ""
    ust = body.get("detail")
    if isinstance(ust, str):
        return ust
    if isinstance(ust, list):
        return providers.detail_of({"error": {"details": ust}})
    return ""


def map_error(status_code: int, body: dict | list | None) -> str:
    """HTTP durumunu Türkçe mesaja çevirir. ŞEKİL paylaşılıyor, METİN değil.

    `veo_client.map_error`in duruşunun aynısı: "Veo" diyen bir metin fal
    faturasını arayan kullanıcıyı yanlış konsola yönlendirir.

    402 DALI BU DOSYANIN EN ÖNEMLİ YERİ ve `veo_client`in 403/429 dalının
    ikizi: **fal ön ödemeli.** Bakiyesi biten kullanıcıya "anahtarını kontrol
    et" demek, anahtarı GERÇEKTEN doğru olan birini çalışan kurulumunu
    bozmaya davet etmek olurdu.

    429 DA AYRI bir cümle: fal'da yeni hesaplar İKİ eşzamanlı istekle
    başlıyor, yani 429 çoğu zaman bir kota değil bir SIRA sorunu ve cevabı
    "bekle ve tekrar dene".
    """
    detail = detail_of(body)
    ek = f" {detail}" if detail else ""
    if status_code in (401, 403):
        return ("fal.ai yetkilendirme hatası "
                f"({status_code}): anahtar geçersiz ya da bu modele erişimi "
                "yok. Ayarlar'dan yeniden kaydet." + ek)
    if status_code == 402:
        return ("fal.ai bakiyesi yetersiz (402): fal ön ödemeli çalışıyor, "
                "hesabına kredi yükleyip tekrar dene." + ek)
    if status_code == 404:
        return ("fal.ai modeli bulunamadı (404): bu uç yeniden adlandırılmış "
                "ya da kaldırılmış olabilir." + ek)
    if status_code == 429:
        return ("fal.ai eşzamanlı istek sınırı (429): bir önceki üretim hâlâ "
                "sürüyor olabilir. Yeni hesaplarda sınır ikidir; biraz "
                "bekleyip tekrar dene." + ek)
    if providers.is_content_policy(detail):
        return ("fal.ai isteği içerik kurallarıyla reddetti "
                f"(HTTP {status_code}): prompt'u ya da referans görseli "
                "değiştirip tekrar dene." + ek)
    if status_code == 400 and providers.is_invalid_key(detail):
        return ("fal.ai anahtarı geçersiz (400): Ayarlar'dan yeniden "
                "kaydet." + ek)
    if status_code == 422:
        return ("fal.ai isteği reddetti (422): "
                + (detail or "gövdedeki alanlardan biri geçersiz."))
    return f"fal.ai isteği başarısız (HTTP {status_code})." + ek
```

**Sıra bağlayıcı:** `is_content_policy` denetimi 422'DEN ÖNCE geliyor — Wan'ın güvenlik reddi 422 ile dönebiliyor ve "alanlardan biri geçersiz" demek kullanıcıyı gövdeyi kurcalamaya iterdi.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fal_client.py -q`
Expected: PASS (13 test)

- [ ] **Step 5: Graf + commit**

```bash
python tools/graf_uret.py
python -m pytest tests/ -q
git add fal_client.py tests/test_fal_client.py docs/graflar/
git commit -m "feat(fal): hata cevirisi — ust duzey detail listesi, 402 bakiye ve 429 esraman dallari"
```

---

### Task 6: Kuyruk döngüsü — submit, yoklama, sonuç, indirme

**Files:**
- Modify: `fal_client.py`
- Test: `tests/test_fal_client.py`

**Interfaces:**
- Consumes: `build_payload`, `wire_path_for`, `map_error` (Görev 4–5); `providers.total_budget`; `credstore.resolve`
- Produces:
  - `fal_client.generate(m, prompt, size, quality, duration, n, *, client=None, credentials=None) -> list[bytes]`
  - `fal_client.animate(m, prompt, images, size, quality, duration, n, *, last_frame=None, client=None, credentials=None) -> list[bytes]`
  - Test dikişleri: `fal_client._simdi()`, `fal_client._bekle(saniye)`

- [ ] **Step 1: Write the failing test**

`tests/test_fal_client.py` sonuna:

```python
# ── Kuyruk döngüsü ─────────────────────────────────────────────────────

CREDS = ("FALKEY", "https://queue.fal.run")
MP4 = b"\x00\x00\x00\x18ftypmp42"


class FakeResponse:
    def __init__(self, status_code, json_body=None, content=b"", headers=None):
        self.status_code = status_code
        self._json = json_body
        self.content = content
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("gövde JSON değil")
        return self._json


class FakeClient:
    """Sözleşmenin `client=` anahtarının açtığı dikiş."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append({"method": method, "url": url, "headers": headers or {},
                           "json": json, "timeout": timeout})
        return self._responses[min(len(self.calls) - 1,
                                   len(self._responses) - 1)]

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _saati_durdur(monkeypatch):
    """Uykuyu kaldırıyor; `_simdi`/`_bekle` dikişleri `veo_client`in deseni."""
    monkeypatch.setattr(fal_client, "_bekle", lambda s: None)


def _kuyruk_yanitlari(rid="abc123"):
    return [
        FakeResponse(200, {"request_id": rid,
                           # DÜŞMANCA adresler: ürün kodu bunları OKUMAMALI.
                           "status_url": "https://evil.example/status",
                           "response_url": "https://evil.example/response"}),
        FakeResponse(200, {"status": "IN_QUEUE", "queue_position": 2}),
        FakeResponse(200, {"status": "COMPLETED"}),
        FakeResponse(200, {"video": {"url": "https://v3.fal.media/x.mp4",
                                     "content_type": "video/mp4"}}),
        FakeResponse(200, content=MP4),
    ]


def test_the_happy_path_returns_the_downloaded_mp4_bytes():
    client = FakeClient(*_kuyruk_yanitlari())
    out = fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                              client=client, credentials=CREDS)
    assert out == [MP4]


def test_the_poll_and_result_urls_are_REBUILT_from_the_trusted_base():
    """Gövdedeki `status_url`/`response_url` OKUNMUYOR.

    `veo_client._indir`in ölçülmüş kararının aynısı: gövdeyi yazan taraf
    bizim GET'imizin hedefini seçememeli. fal'ın belgesi tersini öneriyor ve
    bu sapma bilinçli — bkz. fal_client başlığı.
    """
    client = FakeClient(*_kuyruk_yanitlari())
    fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                        client=client, credentials=CREDS)
    adresler = [c["url"] for c in client.calls]
    assert not any("evil.example" in u for u in adresler)
    # GÖNDERİM yolu tam (`…/text-to-video`), YOKLAMA yolu yalnız ilk iki
    # segment — ölçülmüş fark (bkz. `queue_app_path`).
    assert adresler[0] == (
        "https://queue.fal.run/alibaba/wan-3.0/text-to-video")
    assert adresler[1] == (
        "https://queue.fal.run/alibaba/wan-3.0/requests/abc123/status")
    assert adresler[3] == (
        "https://queue.fal.run/alibaba/wan-3.0/requests/abc123")


def test_the_download_step_carries_NO_credentials():
    """Çıktı adresi gövdeden geliyor; anahtar oraya GİTMEMELİ."""
    client = FakeClient(*_kuyruk_yanitlari())
    fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                        client=client, credentials=CREDS)
    indirme = client.calls[-1]
    assert indirme["url"] == "https://v3.fal.media/x.mp4"
    assert "Authorization" not in indirme["headers"]


def test_the_submit_step_uses_the_Key_prefixed_authorization_header():
    client = FakeClient(*_kuyruk_yanitlari())
    fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                        client=client, credentials=CREDS)
    assert client.calls[0]["headers"]["Authorization"] == "Key FALKEY"


def test_a_missing_request_id_fails_with_a_TURKISH_error():
    client = FakeClient(FakeResponse(200, {"queue_position": 0}))
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "fal" in str(exc.value).lower()


def test_a_hostile_request_id_is_REJECTED_before_any_url_is_built():
    """Yola segment enjekte etmeyi deneyen bir id kabul edilmemeli."""
    client = FakeClient(FakeResponse(200, {"request_id": "../../../admin"}))
    with pytest.raises(ac.ImageError):
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)


def test_COMPLETED_without_a_video_is_a_TURKISH_error_not_a_KeyError():
    """`azure_flux_client.decode_images`in kararı: sarmalanmayan bir KeyError
    app.py'nin süzgecinden geçer ve kullanıcı dakikalarca bekledikten sonra
    yalnızca 'Hata (500)' görür."""
    client = FakeClient(
        FakeResponse(200, {"request_id": "abc123"}),
        FakeResponse(200, {"status": "COMPLETED"}),
        FakeResponse(200, {"seed": 7}),
    )
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "video" in str(exc.value).lower()


def test_the_wall_clock_budget_ends_the_loop_with_its_own_message(monkeypatch):
    saat = iter([0.0] + [10_000.0] * 50)
    monkeypatch.setattr(fal_client, "_simdi", lambda: next(saat))
    client = FakeClient(
        FakeResponse(200, {"request_id": "abc123"}),
        FakeResponse(200, {"status": "IN_PROGRESS"}),
    )
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "bitmedi" in str(exc.value).lower()


def test_animate_uses_the_image_to_video_endpoint():
    client = FakeClient(*_kuyruk_yanitlari())
    fal_client.animate(WAN, "kedi", REFS, "16:9", "720p", 5, 1,
                       client=client, credentials=CREDS)
    assert client.calls[0]["url"].endswith("/image-to-video")


def test_a_download_redirect_is_followed_MANUALLY_and_capped():
    yanitlar = _kuyruk_yanitlari()[:-1] + [
        FakeResponse(302, headers={"location": "https://cdn.example/y.mp4"}),
    ]
    client = FakeClient(*yanitlar)
    with pytest.raises(ac.ImageError) as exc:
        fal_client.generate(WAN, "kedi", "16:9", "720p", 5, 1,
                            client=client, credentials=CREDS)
    assert "yönlendirme" in str(exc.value).lower()
```

`tests/test_fal_client.py`'nin en üstündeki import bloğuna `import azure_client as ac` ekle.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fal_client.py -q -k "happy or REBUILT or download or submit"`
Expected: FAIL — `AttributeError: module 'fal_client' has no attribute 'generate'`

- [ ] **Step 3: Write minimal implementation**

`fal_client.py`'ye ekle — üst kısma `import re` ve `import time`, ardından:

```python
AUTH_HEADER = "Authorization"
# `Key ` ÖNEKİ ZORUNLU: fal'ın kabul ettiği tek biçim bu. `Bearer` ile
# gönderilen aynı anahtar 401 dönüyor (Replicate'in biçimi o).
AUTH_PREFIX = "Key "

# ÜÇ AYRI ZAMAN AŞIMI — `veo_client`in taşıyıcı kararının aynısı ve aynı
# sebeple: submit/yoklama metadata çağrısı (kısa), indirme megabaytlarca MP4
# (uzun), döngünün tamamı `providers.total_budget` (duvar saati).
#
# SABİTLER KOPYALANDI, `veo_client`ten İMPORT EDİLMEDİ:
# `azure_mai_client`/`azure_flux_client`in `AUTH_HEADER`ı iki kez beyan etme
# gerekçesinin aynısı — biri değişmek zorunda kaldığında öteki dokunulmadan
# kalabiliyor.
POLL_READ_TIMEOUT = 30.0
DOWNLOAD_READ_TIMEOUT = ac.read_timeout_for(1)
POLL_INTERVAL_START = 1.0
POLL_INTERVAL_MAX = 10.0
POLL_BACKOFF = 1.6

MAX_YONLENDIRME = 5
_YONLENDIRME_KODLARI = (301, 302, 303, 307, 308)

DURUM_TAMAM = "COMPLETED"

# `request_id`in KABUL EDİLEN karakterleri. Kuyruk adresleri gövdeden
# alınmıyor, TABANDAN kuruluyor (bkz. `_durum_url`) — ve o kurulumda id tek
# değişken parça. Süzgeç olmasaydı `../../..` taşıyan bir id yolu başka bir
# uca çevirebilirdi.
_REQUEST_ID = re.compile(r"\A[A-Za-z0-9_-]{1,128}\Z")


def _simdi() -> float:
    """Tek yönlü saat — TEST DİKİŞİ (`veo_client._simdi`nin aynı gerekçesi)."""
    return time.monotonic()


def _bekle(saniye: float) -> None:
    """Yoklama arası uyku — `_simdi` ile aynı gerekçe."""
    time.sleep(saniye)


def _durum_url(taban: str, yol: str, rid: str) -> str:
    """Yoklama adresi — GÜVENİLEN TABANDAN kuruluyor, yanıttan DEĞİL.

    fal'ın belgesi "dönen `status_url`'ü kullan, elle kurma" diyor ve biz
    BİLEREK tersini yapıyoruz. Gerekçe `veo_client._indir`in ölçülmüş
    kararı: gövdeden gelen bir adreste "hedef konağı gövdeyi yazan taraf
    seçiyor". Gövdeden alınan tek şey `request_id` ve o da `_REQUEST_ID`
    süzgecinden geçiyor.

    TAKAS AÇIK: fal kuyruğu bir gün bölgeselleştirirse (BFL'in
    `api.eu`/`api.us` uçlarında olduğu gibi) değişecek tek yer bu iki
    fonksiyon. Belirti net olur: 404.
    """
    return f"{taban}/{queue_app_path(yol)}/requests/{rid}/status"


def _sonuc_url(taban: str, yol: str, rid: str) -> str:
    """`_durum_url`in ikizi; aynı gerekçe."""
    return f"{taban}/{queue_app_path(yol)}/requests/{rid}"


def _istek(client, method: str, url: str, key: str | None, *, read: float,
           json=None):
    """Ortak HTTP + taşıma hatası çevirisi. Yanıtı ÇÖZÜMLEMİYOR.

    `key=None` KİMLİKSİZ istek demek ve tek kullanıcısı `_indir` —
    gerekçesi orada. `veo_client._istek`ten farkı tam olarak bu: orada
    indirme Google konağında anahtarı GÖNDERİYORDU, burada hiç göndermiyor.

    YÖNLENDİRME İZLENMİYOR (`follow_redirects` yok): `_indir` onu ELLE
    izliyor, çünkü httpx yönlendirmede özel başlıkları soymuyor.
    """
    import httpx
    basliklar = {}
    if key:
        basliklar[AUTH_HEADER] = AUTH_PREFIX + key
    if json is not None:
        basliklar["Content-Type"] = "application/json"
    try:
        return client.request(method, url, headers=basliklar, json=json,
                              timeout=ac.request_timeout(read))
    except httpx.TransportError as exc:
        # Mesaj `azure_client`tan geliyor, sağlayıcı adı düzeltiliyor:
        # "Azure'a bağlanılamadı" diyen bir metin kullanıcıyı Endpoint alanını
        # kurcalamaya iter (`veo_client._istek`in aynı satırı).
        raise ac.ImageError(
            ac.transport_error_message(exc, read).replace("Azure", "fal.ai")) from exc


def _govde(resp):
    try:
        return resp.json()
    except Exception:
        return None


def _video_url(sonuc: dict) -> str:
    """Sonuç gövdesinden MP4 adresi.

    BEKLENMEYEN ŞEKİL ham `KeyError` DEĞİL Türkçe `ImageError` üretiyor:
    `azure_flux_client.decode_images`in kararı — sarmalanmayan bir `KeyError`
    `app.py`'nin süzgecinden geçer ve kullanıcı dakikalarca bekledikten sonra
    yalnızca "Hata (500)" görür. Anahtarlar mesaja giriyor ki şekil
    değiştiğinde teşhis kullanıcının ekranında olsun.
    """
    video = sonuc.get("video") if isinstance(sonuc, dict) else None
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise ac.ImageError(
            "fal.ai video döndürmedi: yanıtta `video.url` yok "
            f"(anahtarlar: {sorted(sonuc) if isinstance(sonuc, dict) else '—'}). "
            "Üretim fal tarafında tamamlanmış ve ücretlendirilmiş olabilir.")
    return str(url)


def _indir(client, url: str) -> bytes:
    """MP4'ü indirir — ANAHTARSIZ ve yönlendirmeyi ELLE izleyerek.

    ANAHTARSIZ olması bu dosyanın ikinci güvenlik kararı: `url` YANIT
    GÖVDESİNDEN geliyor, yani hedef konağı gövdeyi yazan taraf seçiyor.
    fal'ın çıktı adresi genel erişime açık bir CDN, yani kimlik zaten
    gereksiz — göndermemek, sızma yolunu tamamen kapatıyor.
    (`veo_client._indir` Google konağında anahtarı gönderiyordu ve bu yüzden
    bir konak allowlist'i taşımak zorundaydı; burada ona gerek yok.)
    """
    from urllib.parse import urljoin
    for _ in range(MAX_YONLENDIRME):
        resp = _istek(client, "GET", url, None, read=DOWNLOAD_READ_TIMEOUT)
        if resp.status_code == 200:
            return resp.content
        if resp.status_code not in _YONLENDIRME_KODLARI:
            raise ac.ImageError(
                f"fal.ai videosu indirilemedi (HTTP {resp.status_code}).")
        hedef = resp.headers.get("location")
        if not hedef:
            raise ac.ImageError(
                f"fal.ai videosu indirilemedi: {resp.status_code} "
                "yönlendirmesi adres taşımıyor.")
        # GÖRECELİ adres de geçerli (RFC 7231); `urljoin` mutlaklaştırıyor.
        url = urljoin(url, hedef)
    raise ac.ImageError(
        f"fal.ai videosu indirilemedi: {MAX_YONLENDIRME} yönlendirmeden "
        "sonra hâlâ bitmedi.")


def _timeout_message(gecen: float, butce: float) -> str:
    """`veo_client._timeout_message`in ikizi ve aynı ÜCRET UYARISIYLA: iş fal
    tarafında tamamlanmış olabilir ve kullanıcı 'hata aldım, demek ki
    ücretlenmedim' diye düşünmemeli."""
    return (f"fal.ai üretimi {gecen:.0f} saniyede bitmedi (tavan "
            f"{butce:.0f} sn). Süreyi ya da çözünürlüğü düşürüp tekrar dene. "
            "Not: üretim fal tarafında tamamlanmış ve ücretlendirilmiş "
            "olabilir, yalnızca sonuç bu tarafa ulaşmadı.")


def _uret(m: catalog.ImageModel, prompt: str, size: str, quality: str,
          duration: int, n: int, images, *, client, credentials) -> list[bytes]:
    """`generate` ve `animate`in PAYLAŞILAN gövdesi — tek fark `images`.

    DÖRT ADIM: submit → `COMPLETED` olana kadar yokla → sonucu al → indir.
    `veo_client._uret`in üç adımından farkı, fal'ın sonucu DURUM yanıtında
    değil AYRI bir adreste vermesi.

    KİMLİK TEMBEL çözülüyor (`providers._azure_generate`in belgelenmiş
    kuralı). SON TARİH duvar saatiyle ölçülüyor, yoklama SAYISIYLA değil.

    DÖNGÜ adet başına ayrı istek atıyor (`images_per_request=1`). Bugün
    `max_n=1` olduğu için tek tur, ama yapısı tavan yükseldiği gün hazır.
    """
    key, base_url = (credentials if credentials is not None
                     else credstore.resolve(m.credential))
    taban = base_url.rstrip("/")
    yol = wire_path_for(m, images=images).strip("/")
    butce = providers.total_budget(m, n)
    payload = build_payload(m, prompt, size, quality, duration, images)

    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        out: list[bytes] = []
        while len(out) < n:
            out.append(_tek_uretim(client, key, taban, yol, payload, butce))
        return out[:n]
    finally:
        if owns:
            client.close()


def _tek_uretim(client, key: str, taban: str, yol: str, payload: dict,
                butce: float) -> bytes:
    """Tek bir kuyruk turu: submit → yokla → sonuç → indir."""
    # ── 1. Submit ────────────────────────────────────────────────────────
    resp = _istek(client, "POST", f"{taban}/{yol}", key,
                  read=POLL_READ_TIMEOUT, json=payload)
    if resp.status_code != 200:
        raise ac.ImageError(map_error(resp.status_code, _govde(resp)))
    kuyruk = _govde(resp) or {}
    rid = str(kuyruk.get("request_id") or "")
    if not _REQUEST_ID.match(rid):
        raise ac.ImageError(
            "fal.ai işi başlatılamadı: yanıttaki `request_id` yok ya da "
            f"tanınmayan biçimde (anahtarlar: {sorted(kuyruk)}).")

    # ── 2. Yoklama ───────────────────────────────────────────────────────
    # Döngü UYKUYLA DEĞİL KONTROLLE başlıyor: kısa bir iş ilk yanıtta
    # `COMPLETED` olabilir ve uykuyla başlamak hazır sonucu bekletmek olurdu
    # (`veo_client`in aynı notu).
    durum_url = _durum_url(taban, yol, rid)
    baslangic = _simdi()
    aralik = POLL_INTERVAL_START
    durum = ""
    while durum != DURUM_TAMAM:
        gecen = _simdi() - baslangic
        if gecen >= butce:
            raise ac.ImageError(_timeout_message(gecen, butce))
        resp = _istek(client, "GET", durum_url, key, read=POLL_READ_TIMEOUT)
        if resp.status_code != 200:
            raise ac.ImageError(map_error(resp.status_code, _govde(resp)))
        govde = _govde(resp) or {}
        durum = str(govde.get("status") or "")
        if durum == DURUM_TAMAM:
            break
        _bekle(min(aralik, max(0.0, butce - gecen)))
        aralik = min(aralik * POLL_BACKOFF, POLL_INTERVAL_MAX)

    # ── 3. Sonuç ─────────────────────────────────────────────────────────
    resp = _istek(client, "GET", _sonuc_url(taban, yol, rid), key,
                  read=POLL_READ_TIMEOUT)
    if resp.status_code != 200:
        raise ac.ImageError(map_error(resp.status_code, _govde(resp)))
    sonuc = _govde(resp) or {}
    # `COMPLETED` BAŞARI DEMEK DEĞİL: fal işin BİTTİĞİNİ söylüyor, iyi
    # bittiğini değil — düşen iş de `COMPLETED` olup gövdesinde `error`
    # taşıyor (`veo_client`in `done: true` + video yok hâlinin ikizi).
    #
    # `map_error` BURADA ÇAĞRILMIYOR: onun sözleşmesi bir HTTP DURUM KODUNU
    # çevirmek ve buradaki yanıt 200 — `map_error(200, …)` genel "istek
    # başarısız (HTTP 200)" dalına düşer, yani kullanıcıya anlamsız bir
    # cümle gösterirdi. Gerekçe doğrudan yazılıyor.
    hata = detail_of(sonuc)
    if hata and not (isinstance(sonuc, dict) and sonuc.get("video")):
        raise ac.ImageError(f"fal.ai video üretmedi: {hata}")

    # ── 4. İndirme ───────────────────────────────────────────────────────
    return _indir(client, _video_url(sonuc))


def generate(m: catalog.ImageModel, prompt: str, size: str, quality: str,
             duration: int, n: int, *, client=None,
             credentials=None) -> list[bytes]:
    return _uret(m, prompt, size, quality, duration, n, None,
                 client=client, credentials=credentials)


def animate(m: catalog.ImageModel, prompt: str, images, size: str, quality: str,
            duration: int, n: int, *, last_frame=None, client=None,
            credentials=None) -> list[bytes]:
    """`images`: sıralı [(dosya_adı, png_baytları), ...] — yalnız ilki kullanılıyor.

    `last_frame` SÖZLEŞMEDE VAR ama bu sağlayıcıda DESTEKLENMİYOR: üç modelin
    hiçbirinin i2v şemasında `tail_image_url` yok. Kapı `providers.animate_video`'da
    (`supports_last_frame=False`) ve buradaki iddia onun İKİNCİ kapısı —
    `providers.edit`in ikinci kapı disiplininin aynısı.
    """
    if last_frame is not None:
        raise ac.ImageError(f"{m.label} bitiş görseli almıyor.")
    return _uret(m, prompt, size, quality, duration, n, images,
                 client=client, credentials=credentials)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fal_client.py -q`
Expected: PASS (24 test)

- [ ] **Step 5: Graf + tam takım + commit**

```bash
python tools/graf_uret.py
python -m pytest tests/ -q
git add fal_client.py tests/test_fal_client.py docs/graflar/
git commit -m "feat(fal): kuyruk dongusu — adres tabandan kuruluyor, indirme anahtarsiz"
```

---

### Task 7: Katalog girdileri, sevk memuru ve logo — modeller GÖRÜNÜR oluyor

Bu üçü **tek commit**, çünkü ayrı commit'lerde ara durum bozuk olurdu: katalog girdileri adaptörsüz eklenirse şeritte seçilebilen ama "video adaptörü yok" diyen modeller doğar — bu deponun her yerde yasakladığı "arayüzde seçilebilir hata".

**Literaller Görev 1'in ölçüm tablosundan yazılıyor.** Ölçümle çelişen bir hücre varsa ÖLÇÜM kazanır; aşağıdaki değerler ölçüm öncesi tasarım tahminidir.

**Files:**
- Modify: `catalog.py` (`FAL_VIDEO_ASPECT_RATIOS`, `VIDEO_MODELS`, `PROVIDER_LOGOS`)
- Modify: `providers.py` (`_fal_adapter`, `_VIDEO_ADAPTERS`)
- Create: `static/img/providers/fal.svg`
- Test: `tests/test_catalog.py`, `tests/test_providers.py`

**Interfaces:**
- Consumes: Görev 2'nin `wire_model_edit`'i, Görev 3'ün `fal` Credential'ı, Görev 6'nın `generate`/`animate`i, Görev 1'in ölçümü
- Produces: `catalog.video_model("fal-wan-3-0" | "fal-pixverse-c1" | "fal-kling-v3-turbo-pro")`; `providers.video_adapter_ids() == {"gemini", "fal"}`

- [ ] **Step 1: Write the failing tests**

`tests/test_catalog.py` sonuna:

```python
FAL_IDLER = ("fal-wan-3-0", "fal-pixverse-c1", "fal-kling-v3-turbo-pro")


@pytest.mark.parametrize("model_id", FAL_IDLER)
def test_every_fal_video_model_declares_BOTH_wire_endpoints(model_id):
    """Boş `wire_model_edit`, düzenleme isteğini METİN ucuna göndermek —
    yani telde 422 — demek olurdu."""
    m = catalog.video_model(model_id)
    assert m is not None, f"{model_id} katalogda yok"
    assert m.supports_edit
    assert m.wire_model_edit, f"{model_id} ikinci tel yolunu beyan etmiyor"
    assert m.wire_model != m.wire_model_edit


def test_the_default_video_model_is_UNCHANGED():
    """Varsayılanı kaydırmak her kullanıcının bir sonraki tıkına dokunurdu."""
    assert catalog.DEFAULT_VIDEO_MODEL == "gemini-veo-3-1-lite"


def test_fal_video_models_are_ordered_by_ASCENDING_cost():
    """Sıra ANLAMLI (görsel tarafının kuralı) ve burada artan maliyete göre."""
    fal = [m for m in catalog.VIDEO_MODELS if m.provider == "fal"]
    assert [m.credits for m in fal] == sorted(m.credits for m in fal)


@pytest.mark.parametrize("model_id", FAL_IDLER)
def test_fal_video_models_declare_no_last_frame(model_id):
    """Üç modelin hiçbirinin i2v şemasında `tail_image_url` yok."""
    assert catalog.video_model(model_id).supports_last_frame is False
```

`tests/test_providers.py` sonuna:

```python
def test_fal_is_registered_ONLY_in_the_video_table():
    """Görsel yolunun telde ürettiği baytlar bu turda DEĞİŞMİYOR."""
    assert "fal" in providers.video_adapter_ids()
    assert "fal" not in providers.adapter_ids()


def test_the_fal_video_adapter_resolves_to_fal_client():
    import fal_client
    assert providers._video_pair("fal") == (fal_client.generate,
                                            fal_client.animate)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_catalog.py tests/test_providers.py -q -k fal`
Expected: FAIL — `assert None is not None` (`fal-wan-3-0` katalogda yok)

- [ ] **Step 3: Kataloğa oran demetini ve üç modeli ekle**

`catalog.py`, `VIDEO_DURATIONS`ın altına:

```python
# fal'ın kabul ettiği oranlar. `VIDEO_ASPECT_RATIOS` (Veo'nun ikilisi) ile
# BİRLEŞTİRİLMEDİ: iki sağlayıcının kabulünü tek demete katlamak, birine oran
# ekleyip ötekini unutmanın kapısı olurdu — `ASPECT_RATIOS`in on jetonunun
# Veo'da kullanılmama gerekçesinin aynısı, bir eksen ötede.
FAL_VIDEO_ASPECT_RATIOS: tuple[str, ...] = ("16:9", "9:16", "1:1")
```

`VIDEO_MODELS` demetinin SONUNA (üç Veo girdisinden sonra), önce bir blok yorum:

```python
    # ── fal.ai (toplayıcı) ────────────────────────────────────────────
    #
    # SIRA artan maliyete göre ve Veo'dan SONRA: `DEFAULT_VIDEO_MODEL`
    # değişmiyor, yani varsayılan hâlâ Veo Lite.
    #
    # BEYAN KURALI: yalnız fal'ın ŞEMASININ AÇIKÇA saydığı jetonlar. 15 sn
    # Kling (3–15) ve PixVerse (1–15) şemalarında yazılı — Veo'nun 8 sn
    # tavanını aşan tek yeni yetenek. Wan'ın süresi 5·10'da kalıyor çünkü
    # şeması aralık VERMİYOR. Kling'in `qualities`i tek sentetik jeton
    # (`quality_hidden=True`): şema `resolution` alanını hiç saymıyor, yani
    # gönderilecek bir değer yok ama `qualities` de boş bırakılamıyor
    # (bkz. o alanın yorumu).
    ImageModel(
        id="fal-wan-3-0",
        label="Alibaba · Wan 3.0",
        provider="fal",
        wire_model="alibaba/wan-3.0/text-to-video",
        wire_model_edit="alibaba/wan-3.0/image-to-video",
        credential="fal",
        sizes=FAL_VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("480p", "720p", "1080p"),
        default_quality="720p",
        durations=(5, 10),
        default_duration=5,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        supports_last_frame=False,
        poll_timeout=420.0,
        credits=16,
        credits_by_quality=(("480p", 10), ("720p", 16), ("1080p", 24)),
        kind="video",
        note="En ucuz fal kademesi. 480p seçersen saniye maliyeti yarıya iner.",
    ),
    ImageModel(
        id="fal-pixverse-c1",
        label="PixVerse · C1",
        provider="fal",
        wire_model="fal-ai/pixverse/c1/text-to-video",
        wire_model_edit="fal-ai/pixverse/c1/image-to-video",
        credential="fal",
        sizes=FAL_VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("720p", "1080p"),
        default_quality="720p",
        durations=(5, 10, 15),
        default_duration=5,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        supports_last_frame=False,
        poll_timeout=600.0,
        credits=20,
        credits_by_quality=(("720p", 20), ("1080p", 32)),
        kind="video",
        note="15 saniyeye kadar klip — Veo'nun 8 sn tavanını aşan tek model.",
    ),
    ImageModel(
        id="fal-kling-v3-turbo-pro",
        label="Kling · V3 Turbo Pro",
        provider="fal",
        wire_model="fal-ai/kling-video/v3/turbo/pro/text-to-video",
        wire_model_edit="fal-ai/kling-video/v3/turbo/pro/image-to-video",
        credential="fal",
        sizes=FAL_VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("1080p",),
        quality_hidden=True,
        durations=(5, 10, 15),
        default_duration=5,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        supports_last_frame=False,
        poll_timeout=600.0,
        credits=30,
        kind="video",
        note="En iyi fal kademesi, 1080p ve lipsync. Saniyesi pahalı.",
    ),
```

`PROVIDER_LOGOS` sözlüğüne:

```python
    "fal": "fal.svg",
```

- [ ] **Step 4: Sevk memuruna kaydet**

`providers.py`, `_veo_adapter`ın altına:

```python
def _fal_adapter():
    """`_veo_adapter`ın aynı gerekçesi: `fal_client` bu modülü import ediyor
    (`total_budget`, `detail_of` ve iki paylaşılan yüklem için), yani modül
    düzeyinde import etmek DÖNGÜ olurdu. Düz `import` ifadesi, yalnız
    fonksiyon içinde — PyInstaller'ın statik analizi onu da görüyor, yani
    `hiddenimports=[]` korunuyor."""
    import fal_client
    return (fal_client.generate, fal_client.animate)
```

`_VIDEO_ADAPTERS`ı güncelle ve başlığındaki "boş kalmayan tek anahtar bugün `gemini`" cümlesini düzelt:

```python
# provider → (generate_video, animate_video). İKİ anahtar: doğrudan
# `gemini` (Veo) ve TOPLAYICI `fal` (Wan · PixVerse · Kling). Ölü uçların
# gerekçesi `catalog.VIDEO_MODELS`in başlığında duruyor — OpenAI'nin Videos
# API'si kapanıyor, Azure AI Foundry'de video barındırılmıyor, Anthropic'in
# video ucu hiç yok.
#
# `fal` BU TABLODA VAR, `_ADAPTERS`te YOK: bu turun kapsamı video ve görsel
# yolunun telde ürettiği baytlar dokunulmadan kalıyor. Bu asimetri tam
# olarak iki tablonun ayrı olma gerekçesi (bkz. dosya başlığı).
_VIDEO_ADAPTERS: dict[str, tuple] = {
    "gemini": _veo_adapter,
    "fal": _fal_adapter,
}
```

- [ ] **Step 5: Logoyu ekle**

`static/img/providers/fal.svg` — `test_provider_logos.py` üç şey istiyor: gerçek SVG, geçerli XML, `viewBox`. Mevcut logoların (`blackforestlabs.svg`) ölçüsüne bak ve aynı `viewBox` ölçeğini kullan.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" role="img" aria-hidden="true">
  <rect width="24" height="24" rx="5" fill="#0F0F10"/>
  <path d="M8.2 7.3h7.2v2.1h-4.8v2.6h4.3v2.1h-4.3v3.6H8.2z" fill="#fff"/>
</svg>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_catalog.py tests/test_providers.py tests/test_provider_logos.py tests/test_video_onyuz.py -q`
Expected: PASS

- [ ] **Step 7: Graf + tam takım + commit**

```bash
python tools/graf_uret.py
python -m pytest tests/ -q
git add catalog.py providers.py static/img/providers/fal.svg tests/ docs/graflar/
git commit -m "feat(video): fal.ai uc modeli — Wan 3.0, PixVerse C1, Kling V3 Turbo Pro"
```

---

### Task 8: Canlı duman testi ve belgeler

**Files:**
- Modify: `README.md`, `README.en.md`, `docs/ozellikler.md`
- Modify: `docs/superpowers/specs/2026-09-14-fal-video-saglayicisi-design.md` (ölçümle çelişen literal varsa düzeltme notu)

**Interfaces:**
- Consumes: Görev 7'nin çalışan katalog girdileri
- Produces: yok (son görev)

- [ ] **Step 1: Uygulamayı çalıştır ve gerçek bir video üret**

```bash
python desktop.py
```

Video sekmesinde **Wan 3.0**, 5 sn, 480p, 16:9 seç ve üret. Sonra galerideki bir görseli ilk kare yapıp **görsel→video** yolunu da dene (`wire_model_edit` telde ilk kez burada kullanılıyor).

Beklenen: iki üretim de tamamlanıyor, kayıt `.mp4` olarak diske düşüyor, kredi tahmini kartta görünüyor.

**Ölçümle çelişen bir şey çıkarsa** (`422`, yanlış süre, oran reddi) Görev 7'deki literali düzelt, spec'in ölçüm tablosunu güncelle ve ayrı bir `fix(katalog):` commit'i at. Bu bir başarısızlık değil — planın ölçüm önceliğinin işlemesi.

- [ ] **Step 2: Hata yolunu da bir kez gör**

Geçici olarak `credentials.env`'deki `FAL_KEY`i boz, bir üretim dene, sonra geri al.

Beklenen: Türkçe "fal.ai yetkilendirme hatası (401)…" — ham 500 DEĞİL.

- [ ] **Step 3: Belgeleri güncelle**

`README.md`'nin "Metinden video, tek tıkla canlandırma" bölümü artık tek sağlayıcı anlatmamalı. Veo'nun üç kademesinin yanına fal'ın üçünü ekle; **15 saniyelik klip** ve **1:1 oran** yeni yetenek olarak yazılsın. fal'ın **ön ödemeli** olduğu not düşülsün (Veo'nun "ücretsiz kademesi yoktur" uyarısının kardeşi). `README.en.md`'de aynısı.

`docs/ozellikler.md`'ye üç model, eksenleri ve kredi tarifesi.

- [ ] **Step 4: Tam takım + graf kapısı**

```bash
python tools/graf_uret.py --kontrol
python -m pytest tests/ -q
```

Expected: `graflar güncel`, tüm testler PASS.

- [ ] **Step 5: Commit ve PR**

```bash
git add README.md README.en.md docs/
git commit -m "docs(video): fal.ai sağlayıcısı ve 15 saniyelik klip ekseni"
git push -u origin feat/fal-video-saglayicisi
```

PR gövdesi (`gh pr create --title "feat(video): fal.ai video sağlayıcısı (Wan · PixVerse · Kling)" --body-file -`):

```markdown
Video tarafı artık tek sağlayıcıya bağlı değil. fal.ai kuyruk adaptörü ve üç
model geldi: Alibaba · Wan 3.0, PixVerse · C1, Kling · V3 Turbo Pro.

Yeni yetenekler
  · 15 saniyelik klip (PixVerse ve Kling) — Veo'nun 8 sn tavanını aşan ilk
    eksen.
  · 1:1 oran (üç modelde de) — Veo yalnız 16:9 ve 9:16 kabul ediyor.
  · Gemini anahtarı olmayan kullanıcı ilk kez video üretebiliyor.

Taşıyıcı kararlar
  · `ImageModel.wire_model_edit`: fal'da metin→video ve görsel→video AYRI
    uçlar. Varsayılanı "" olduğu için mevcut on üç girdinin teli değişmiyor.
  · Kuyruk adresleri YANITTAN değil güvenilen TABANDAN kuruluyor ve indirme
    adımı ANAHTARSIZ — `veo_client._indir`in ölçülmüş kararının devamı.
    fal'ın belgesine bilinçli bir sapma; gerekçesi `fal_client` başlığında.
  · `fal` yalnız `_VIDEO_ADAPTERS`'e girdi; görsel yolunun telde ürettiği
    baytlar bu turda DEĞİŞMEDİ.
  · `fal_key` v0.2.0'dan beri API'de kabul ediliyordu ama hiçbir arayüzü
    yoktu — kataloğa girdi, forma geldi, redaksiyona dâhil oldu.

Katalog literalleri TAHMİN DEĞİL: canlı uçtan ölçüldü (spec'teki "Ölçüm
sonuçları" tablosu). `azure_flux_client`'ın "200 yanıtı bu depodan
görülmedi" borcu bu turda tekrarlanmadı.

Tasarım: docs/superpowers/specs/2026-09-14-fal-video-saglayicisi-design.md
Plan: docs/superpowers/plans/2026-09-14-fal-video-saglayicisi.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## Ekler — uygulayıcının bilmesi gerekenler

**`ImageModel` alan sırası.** `dataclasses` varsayılanlı bir alandan sonra varsayılansız alan kabul etmiyor. `wire_model_edit` varsayılanlı (`""`), yani `credits`ten (son varsayılansız alan) SONRA konmalı — Görev 2 Step 3'te yazılı.

**`providers` döngüsü.** `fal_client` modül düzeyinde `providers`ı import EDEBİLİR; döngüyü kıran şey `providers`ın `fal_client`ı yalnız `_fal_adapter` fonksiyonunun İÇİNDE import etmesi. `veo_client`, `gemini_client`, `azure_flux_client` üçü de birebir bu desende.

**`n` döngüsü bugün tek tur.** Üç modelde de `max_n=1`. `_uret`in `while len(out) < n` döngüsü tavan yükseldiği gün hazır; `providers.total_budget` zaten tur sayısıyla ölçekleniyor.

**Testlerin `_bekle` yaması.** `autouse` fixture uykuyu kaldırıyor. Duvar saati testi ayrıca `_simdi`yi yamalıyor — ikisi de `veo_client`in test dikişi deseni.

**Graf kapısı.** `tests/test_graflar.py` commit'lenmiş graflar kaynakla aynı değilse KIRMIZI. Her `.py`/`static/` değişikliğinden sonra `python tools/graf_uret.py` ve çıktısı aynı commit'e.
