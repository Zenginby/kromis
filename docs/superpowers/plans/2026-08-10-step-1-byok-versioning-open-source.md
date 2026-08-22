# Uygulama Planı: Adım 1 — Sürüm Güncellemesi (v0.2.0), BYOK Sağlayıcı Ayarları, Güvenlik Sıkılaştırması, Windows & GitHub Releases CI/CD

**Tarih:** 2026-08-10  
**Hedef Sürüm:** v0.2.0  
**Kapsam:** GPT-Image Studio'nun sürümünü `0.2.0` yapmak, çoklu model (BYOK: OpenAI, Fal.ai, Replicate, ComfyUI, Ollama) anahtar/endpoint ayar altyapısını kurmak, gelişmiş güvenlik & redaksiyon korumalarını entegre etmek, Windows & macOS için otomatik GitHub Releases CI/CD workflow'u hazırlamak, MIT Lisansı ve açık kaynak dokümantasyonunu eklemek.

> ## ✅ Durum: teslim edildi — denetim 2026-08-22
>
> Bu plandaki her madde bugün depoda karşılığıyla duruyor; hedef sürüm v0.2.0
> geride kaldı, uygulama **v0.7.0**'da. Madde madde:
>
> | Plan maddesi | Bugünkü karşılığı |
> |---|---|
> | `APP_VERSION = 0.2.0` | ✅ `version.py` tek kaynak (bugün `0.7.0`); mandal `tests/test_version.py` |
> | Write-only API anahtarları | ✅ `GET /api/settings` anahtarı, son dört hanesini ve maskeli hâlini bile döndürmüyor (`tests/test_settings_route.py`) |
> | Redaksiyon exception handler | ✅ `errlog.redact_secrets` + `app._is_secret_loc` — doğrulama hatası da gizli alan yankılamıyor |
> | `chmod 0600` / `0700` | ✅ `azure_client._atomic_write`; Windows'ta ayrıca DACL (`winsec.py` — plandan **fazlası**) |
> | Ayarlar modalında sağlayıcı grupları | ✅ Azure OpenAI · OpenAI · Google Gemini grupları + yalnız-tek-sağlayıcı kurulumu |
> | `.github/workflows/release.yml` | ✅ üç platform hattı (`_paket-macos` / `_paket-windows` / `_paket-android`); hepsi yeşil olmadan etiket de yayın da yok |
> | `LICENSE` (MIT) | ✅ kökte |
> | `README.md` açık kaynak rehberi | ✅ indirme tablosu, BYOK kurulumu, geliştirici rehberi |
> | `gitleaks` geçmiş taraması | ⬜ **kaydı yok** — CI'da böyle bir iş tanımlı değil; elle yapıldıysa kanıtı depoda durmuyor |
>
> Plan **fal.ai / Replicate / ComfyUI / Ollama** anahtarlarını da sayıyordu:
> alanları ve durum bayrakları geldi (`azure_client.get_settings_status`), ama o
> dört sağlayıcının **adaptörü ve arayüzü hâlâ yok** — açık iş olarak master yol
> haritasının Faz 3'ünde duruyor.

---

## 1. Amaç ve Değişiklik Özeti

GPT-Image Studio'yu açık kaynak topluluğuna açmak, Windows ve macOS sürümlerini otomatik paketlemek ve güvenlik standartlarını en üst seviyeye çıkarmak için:
1. `version.py` dosyasında `APP_VERSION` değerini `0.2.0` olarak güncellemek.
2. **Güvenlik & Redaksiyon Sıkılaştırması:**
   - Public öncesi `gitleaks` ile tüm Git geçmişinin gizli anahtarlara karşı taranması.
   - `credentials.env` / `azure_client.py` ve `/api/settings` katmanında tüm yeni API anahtarlarının (OpenAI, Fal.ai, Replicate) **write-only** yapılması (istemciye dönmesinin engellenmesi).
   - FastAPI exception handler'larında API anahtarlarının otomatik redaksiyonu (loglara/yanıtlara düşmesini engelleme).
   - Dosya izinlerinin `chmod 0600` (dosya) ve `chmod 0700` (dizin) olarak sıkılaştırılması.
3. Ayarlar modalında sağlayıcı sekmeleri/grupları ekleyerek kullanıcı deneyimini iyileştirmek.
4. `.github/workflows/release.yml` ekleyerek her sürüm etiketinde **macOS arm64**, **macOS x86_64** ve **Windows x64** paketlerini derleyip otomatik **GitHub Release** olarak sunmak.
5. Repo köküne `LICENSE` (MIT) eklemek ve `README.md`'yi açık kaynak kullanım rehberine dönüştürmek.

---

## 2. Kullanıcı İncelemesi ve Tasarım Kararları

> [!CAUTION]
> **API Key & Confidentiality Protection:**
> `app.py` üzerindeki redaction exception handler yeni eklenen tüm gizli anahtarları (`OPENAI_API_KEY`, `FAL_KEY`, `REPLICATE_API_TOKEN`) kapsayacak şekilde güncellenecektir. `GET /api/settings` yanıtından API anahtarları hiçbir koşulda dönmez.

> [!IMPORTANT]
> **Çoklu Platform CI/CD & GitHub Releases:**
> `.github/workflows/release.yml` workflow'u `windows-latest`, `macos-14` (Apple Silicon) ve `macos-latest` (Intel) üzerinde paralel çalışarak 3 ZIP paketini üretir ve etikete bağlayarak GitHub Release olarak yayımlar.

---

## 3. Yapılacak Değişiklikler (Bileşen Bileşen)

### Backend, Yapılandırma & Güvenlik Katmanı

#### [MODIFY] `version.py`
- `APP_VERSION = "0.2.0"` olarak güncelleme.

#### [MODIFY] `azure_client.py`
- Yeni provider anahtarlarının tanımlanması (OpenAI, Fal.ai, Replicate, ComfyUI, Ollama).
- `get_settings_status()` metodunun sağlayıcı bazlı yapılandırma durumlarını gizli anahtarları açık etmeden dönmesi.

#### [MODIFY] `app.py`
- `SettingsPayload` Pydantic modelinin güncellenmesi.
- Redaction exception handler'ın tüm yeni gizli anahtar alanlarını silleşecek (redact edecek) şekilde genişletilmesi.

---

### Arayüz (Frontend UI)

#### [MODIFY] `static/index.html` & `static/app.js`
- Ayarlar modalının gruplandırılması (Azure OpenAI, OpenAI DALL-E 3, Fal.ai & Replicate, Yerel AI Motorları).
- Ayarlar modal alt bilgisinde `v0.2.0` sürümünün gösterilmesi.

---

### CI/CD, Paketleme & Dokümantasyon

#### [NEW] `.github/workflows/release.yml`
- GitHub Release otomasyon workflow'u (macOS arm64, macOS x86_64, Windows x64 matrix build).

#### [NEW] `LICENSE`
- MIT Açık Kaynak Lisansı dosyası.

#### [MODIFY] `README.md`
- Açık kaynak kullanımı, BYOK kurulum adımları, Windows ve macOS indirme bağlantıları talimatı.

---

## 4. Doğrulama Planı

### Otomatik Testler (Pytest & Security Audit)
```bash
.venv/bin/python -m pytest tests/ -v
```
- `tests/test_version.py`: `v0.2.0` sürüm kontrolü.
- `tests/test_settings.py`: Sağlayıcı anahtarları kaydetme, okuma ve redaksiyon güvenlik testleri.
- `gitleaks detect --source . -v`: Public öncesi Git geçmişi gizli veri taraması.

### Manuel Doğrulama
1. `./run.sh` ile uygulamayı başlatma.
2. Ayarlar modalını açıp `v0.2.0` sürümünü ve yeni sağlayıcı alanlarını doğrulama.
3. Hata durumunda API anahtarının loga düşmediğini redaksiyon kontrolüyle doğrulama.
