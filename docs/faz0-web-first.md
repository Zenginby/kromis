# Faz 0 — web-first zemin: görev listesi

**Tarih:** 2026-09-16 · **Karar:** web-first (Alperen Zengin, Slack) · **Dondurulan:** masaüstü + Android, v0.23.1
**Üst belge:** [superpowers/specs/2026-08-10-saas-transformation-master-design.md](superpowers/specs/2026-08-10-saas-transformation-master-design.md)

Faz 0'ın amacı ürün davranışını DEĞİŞTİRMEDEN, SaaS fazlarının (hesap, veri
tabanı, kredi, kuyruk) üstüne oturacağı zemini kurmak. Her madde bir PR; her
PR tek başına yeşil ve geri alınabilir. Sıra bağımlılığa göre: 2 → 3/4 (ikisi
2'ye dayanır), 5 ve 6 her an, 7 ve 8 sona.

Ölçüler bu belge yazılırken alındı (`98c781e` üstünde, Adım 1 dalında):
`app.py` 2.286 satır / 45 rota (`app.py:481` ilk, `app.py:2222` son rota);
takım 2.683 test, E2E dâhil 90 sn; ruff temiz (kapatılan kurallar
`pyproject.toml`da), mypy 77 bulgu / 24 dosya.

---

## 1. Web-first zemin — paketleme elle, düz-modül kilidi kalktı, ruff + mypy ✅ (bu PR)

**Kapsam.** `release.yml` yalnız `workflow_dispatch`; `ci.yml`den `kapsam` ve
üç paket işi silindi, `lint` işi eklendi (ruff kapı, mypy bilgi). Chaquopy
düz-modül mandalı `tests/test_android_packaging.py` silindi;
`tests/test_ci_paketleme_kapisi.py` silindi, yerine `tests/test_paketleme_dondurma.py`
(push/PR → paket YOK değişmezi + README'lerin dondurmayı söylediği).
`pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`), `requirements-dev.txt`e
`ruff==0.16.*`, `mypy==2.3.*`. Güvenli otomatik düzeltmeler uygulandı (64
bulgu, 42 dosya: ithal sırası, kullanılmayan ithal, `collections.abc.Callable`,
tırnaksız tip notu).

**Dokunulan.** `.github/workflows/{ci,release,_paket-*,build-pydantic-core-android}.yml`,
`catalog.py:28-38`, `providers.py:57-62` (docstring), `README.md`, `README.en.md`,
`docs/yayin-hatti.md`, `docs/dal-korumasi.md`, `docs/graflar/*`.

**Risk.** Düşük. Ürün kodu davranışı değişmiyor. Tek geri dönüşsüz etki:
main'e merge artık sürüm artırmaz; elle yayın yolu `Actions → Yayın`.

**Çıkış ölçütü.** Tam takım E2E dâhil yeşil, `ruff check .` temiz,
`graf_uret.py --kontrol` 0, PR açık.

---

## 2. `app.py` monolitini `routers/` + `services/` paketlerine böl

**Kapsam.** 45 rota ve yardımcıları alan bazlı `APIRouter`lara taşınır
(öneri: `routers/uretim.py` generate/edit/video/animate, `routers/galeri.py`
history/image/images/folders/import/output, `routers/sohbet.py` chat/chats,
`routers/ayarlar.py` settings/prefs/guncelleme, `routers/palet.py`,
`routers/bindirme.py` logo/banner/assets, `routers/kok.py` `/` + static).
Rota-dışı mantık (`_to_png`, `_read_png_file`, `_output_png_path`, redaksiyon,
`_model_available`) `services/` altına. `app.py` yalnız `FastAPI()` kurulumu,
middleware, `include_router` ve mount olur (~150 satır hedef).

**Test etkisi — ÖNCE ölçüldü.** Testler `import app as appmod` deyip modül
özniteliğini yamalıyor: `monkeypatch.setattr(appmod, "OUTPUT_DIR", …)` **47**
yerde, `ASSETS_DIR` **17**, `_to_png` **16**, `_dil` **3**, `STATIC_DIR` **2**
(ör. `tests/test_app.py:10`). Rota bir router modülüne taşınınca o modül
`appmod.OUTPUT_DIR`ı DEĞİL kendi kopyasını görür ve yama boşa gider — 47 test
sessizce geliştiricinin gerçek veri dizinine yazar (`tests/conftest.py`nin
lifespan koruması bunu kısmen yakalar). Bu yüzden 2, 4 ile birlikte
tasarlanmalı: dizinler bir ayar nesnesinden okunursa yamanın tek hedefi
kalır. Ara çözüm kabul edilebilir: router modülleri `import app` yapmadan
(döngü!) `services.ayarlar.OUTPUT_DIR()` gibi bir işlev çağırır; testler o
tek işlevi yamalar.

**Dokunulan.** `app.py` (bölünür), yeni `routers/__init__.py`, `services/__init__.py`;
`tools/graf_uret.py` (uç-nokta tarayıcısı `app.py`de `@app.<fiil>` arıyor —
`@router.<fiil>` ve `include_router(prefix=)` okumayı öğrenmeli, yoksa
`docs/graflar/uc-noktalar.md` boşalır ve `test_graflar` kırmızı olur);
`tests/test_i18n.py::test_every_shipped_module_is_classified` (yeni modüller
sınıflandırılmalı); `tests/test_telif_basligi.py` (`routers/*.py`,
`services/*.py` telif başlığı kapsamına girmeli — kalıp bugün yalnız kök ve
`tools/`); `kromis.spec` DOKUNULMAZ (dondurulmuş, PyInstaller `hiddenimports=[]`
varsayımı orada kalır ama artık yayın yolunda değil).

**Risk.** Orta-yüksek: en büyük diff, en çok test dokunuşu. Küçültme: bir
PR'da bir router (önce en bağımsızı `palet`), her adımda takım yeşil.

**Çıkış ölçütü.** `app.py` < 300 satır, 45 rota `uc-noktalar.md`de aynı yol ve
fiille görünüyor, hiçbir test `appmod.<rota yardımcısı>` yamalamıyor, takım yeşil.

---

## 3. Dilin (i18n) istek/hesap bağlamına taşınması

**Kapsam.** `i18n._AKTIF` ZATEN bir `contextvars.ContextVar`
(`i18n.py:121`; yazan `set_active` `i18n.py:126`, okuyan `i18n.py:138`) —
yani ASGI altında istek başına doğru izole. Asıl sorun KAYNAĞI: middleware
her istekte `prefs.read(OUTPUT_DIR).get("language")` okuyor
(`app.py:133-163`), yani dil tek kullanıcının `prefs.json`undan geliyor.
Çok kullanıcılı web'de dil isteğin kendisinden (çerez → `Accept-Language` →
hesap tercihi) çözülmeli; `prefs.json` yolu yalnız geriye dönük.

**Dokunulan.** `app.py` middleware (2'den sonra `services/dil.py`), `i18n.py`
(`set_active` imzası değişmez), `prefs.py` (dil alanı okunur ama yazar
kalmaz), `static/settings.js` dil seçimi (çerez yazacak), `bundled/i18n/*.json`
DEĞİŞMEZ; `tests/test_i18n.py`, `tests/test_playwright_dil.py`.

**Risk.** Orta. E2E `test_playwright_dil.py` ön tanımlı dilin İngilizce
kaldığını sınıyor (v0.22 kararı) — çerezsiz ilk istek İngilizce kalmalı.

**Çıkış ölçütü.** Aynı süreçte eş zamanlı iki istek farklı dille doğru cevap
alıyor (yeni test: iki `TestClient`, iki çerez); `prefs.json` okunmadan dil
çözülüyor; takım yeşil.

---

## 4. `OUTPUT_DIR` / `ASSETS_DIR` / `STATIC_DIR` → ayar nesnesi (bağımlılık enjeksiyonu)

**Kapsam.** `app.py:76-78` modül sabitleri (`paths.output_dir()` vb. ithal
anında hesaplanıyor) yerine tek `Ayarlar` (pydantic-settings YOK — stdlib
`dataclass` yeter, `catalog.py`nin deyimiyle) ve FastAPI `Depends(ayarlar)`.
Her store işlevi zaten dizini parametre alıyor (`storage.list_history(output_dir)`
`storage.py:250`, `jsonstore.write_atomic(path, …)` `jsonstore.py:68`) — yani
değişiklik STORE'larda değil, ÇAĞIRAN rotalarda. `paths.data_dir()`
(`paths.py:90`) dört dallı; web'de tek dal (env `KROMIS_DATA_DIR`) + dondurulmuş
kabuk dalları dokunulmadan kalır.

**Dokunulan.** `app.py`/`routers/*`, yeni `services/ayarlar.py`, `paths.py`
(yeni env), `tests/conftest.py` (tek `ayarlar` fixture'ı 47+17 yamanın yerine),
`.env.example` (8'de).

**Risk.** Orta. `tests/conftest.py`nin "gerçek veri dizinine yazma" koruması
fixture'a taşınmalı, yoksa 2'deki sızıntı sınıfı geri gelir.

**Çıkış ölçütü.** `grep -rn 'setattr(appmod, "OUTPUT_DIR"' tests/` → 0;
uygulama `KROMIS_DATA_DIR=/tmp/x` ile açılıp oraya yazıyor; takım yeşil.

---

## 5. Bağımlılık pinlerini yükselt: FastAPI / uvicorn / httpx / Pillow

**Kapsam.** `requirements.txt`: `fastapi==0.115.*` (2024), `uvicorn[standard]==0.32.*`,
`httpx==0.27.*`, `Pillow==11.*`, `python-multipart==0.0.*` → güncel kararlı
sürümlere. `pywebview`, `pythonnet`, `clr-loader` DONDURULMUŞ kabuğa ait —
bu PR'da ellenmez; web çalışma zamanı ayrı bir `requirements.txt` kümesine
ayrılabilir (`requirements-web.txt`?) ama `tools/test_ortami.py` gereksinim
dosyalarını `_test.yml`den okuyor, ekleme orada da görünmeli.

**Tripwire'lar.** `tests/test_bagimlilik_pinleri.py` (her satır pinli — biçim
korunur), `tests/test_python_surumu.py` (3.13 tabanı), `tests/test_test_ortami.py`
(gereksinim sırası `_test.yml`le aynı), `tests/test_playwright_kurulumu.py`
(playwright `requirements-dev.txt`e GİRMEZ). httpx 0.28 `proxies=` kaldırdı ve
istemci enjeksiyonu deseni (`azure_client.generate(client=…)`, `tests/test_azure_client_http.py`)
`httpx.MockTransport` kullanıyorsa imza değişikliği orada görünür. Pillow
sürüm atlaması `tests/fixtures/logo` altın görüntülerini bayt bayt değiştirebilir
(`tests/test_logo.py`, `tools/make_logo_goldens.py`) — altınlar yeniden
üretilir, fark gözle onaylanır.

**Risk.** Orta. Kırılma sınıfı: sessiz davranış farkı (Pillow yeniden örnekleme,
Starlette `TestClient` çerez davranışı).

**Çıkış ölçütü.** Pinler güncel, `pip install -r requirements.txt` temiz, tam
takım yeşil, altın farkları PR'da açıklanmış.

---

## 6. mypy'yi kapıya çevir (kademeli sıkılaştırma) + ruff `ignore` listesini eritme

**Kapsam.** Bugün: mypy 77 bulgu / 24 dosya — `app.py` 22, `providers.py` 8,
`winsec.py` 6 (dondurulmuş, `exclude`a alınabilir), `desktop.py` 4 (aynı),
`tools/graf_uret.py` 4; kod türleri `arg-type` 23, `attr-defined` 16,
`union-attr` 13, `name-defined` 6. Yol: (a) dondurulmuş kabuk modüllerini
`[tool.mypy] exclude`a al, (b) `app.py`/`providers.py` bulgularını 2 ile
birlikte kapat (bölünürken imza yazılır), (c) sıfıra inince `ci.yml`deki
`continue-on-error: true` kalkar, (d) `check_untyped_defs = true`, sonra
modül modül `strict`. Ruff tarafı: `pyproject.toml`daki `ignore` listesi
(E501 41, B904 17, E702 12, B905 11, B008 5 [kalıcı, FastAPI deyimi],
E741 4, UP031 4) ve dosya-bazlı F841/E402/E731 kural kural kapatılır;
`ruff format` ayrı bir "yalnız biçim" PR'ı (141/153 dosya değişir — tek
commit, `git blame` için `.git-blame-ignore-revs`).

**Dokunulan.** `pyproject.toml`, `ci.yml` (`lint` işi), dokunulan modüller.

**Risk.** Düşük; yalnız tip notu ve `from err` zincirleme. `B904`
düzeltmesi `providers.detail_of` gibi hata eşlemelerinde istisna zincirini
görünür kılar — hata mesajı redaksiyonu (`errlog.py`, `tests/test_errlog.py`)
zincirdeki `__cause__`ü de sansürlüyor mu, ölçülmeli.

**Çıkış ölçütü.** `mypy .` 0 bulgu ve `continue-on-error` kalkmış;
`[tool.ruff.lint] ignore` yalnız `B008` içeriyor.

---

## 7. Ön yüz: eslint + prettier, paketleme (bundler) kararı

**Kapsam.** `static/` 10 betik / ~10.900 satır, `static/index.html:1967-1988`
11 `<script>` etiketi, modül sistemi yok, tek küresel kapsam
(`docs/graflar/onyuz.md`). İki karar: (a) eslint (`no-undef`, `no-unused-vars`,
`eqeqeq`) + prettier `--check` — `package.json` + `ci.yml`e `lint-onyuz` işi;
(b) ES modüle geçilecek mi? Karşı ölçü: `tests/test_index.py` (286 test) ve
`tests/test_id_contract.py` (14) kaynak METNİNE ve küresel ad çakışmasına
iddia yazıyor; ES modül her `function foo()`yu yerel yapar ve 286 iddianın
bir bölümü anlamsızlaşır. Öneri: Faz 0'da yalnız (a); (b) SaaS ön yüzünün
çerçeve kararıyla (React/Svelte/vanilla) birlikte Faz 1'de.

**Dokunulan.** yeni `package.json`, `.eslintrc`/`eslint.config.js`,
`.prettierrc`, `ci.yml`; `static/*.js` yalnız otomatik düzeltme.
`tests/test_id_contract.py::test_the_scan_covers_every_shipped_script` ve
`test_telif_basligi.py` kapsamı değişmez.

**Risk.** Düşük (a) / yüksek (b). Node CI'da zaten var (Playwright `node.exe`
soğuk açılışı `tests/test_search_predicate.py` → `NODE_ZAMAN_ASIMI` — ikinci
bir Node aracı aynı süreyi ödeyebilir).

**Çıkış ölçütü.** `npx eslint static/` ve `npx prettier --check static/`
CI'da yeşil; bundler kararı bir `docs/superpowers/specs/…-onyuz-paketleme.md`
belgesiyle kayda geçmiş.

---

## 8. `Dockerfile` + `/health` + `.env.example`

**Kapsam.** Çok aşamalı `Dockerfile` (python:3.13-slim; `uvicorn app:app
--host 0.0.0.0` — `netguard:korumali_app` fabrikası DEĞİL: `run.sh:38`deki
loopback kapısı konteynerde her isteği 403'ler, `netguard` dondurulmuş
masaüstü kabuğuna ait), `.dockerignore` (`tests/`, `android/`, `docs/`,
`.venv/`), `GET /health` (`{"ok": true, "version": APP_VERSION}` — 4'teki
ayar nesnesinin veri dizinine yazılabilirliğini de raporlar),
`.env.example` (`KROMIS_DATA_DIR`, `PORT`, sağlayıcı anahtarlarının adları
`catalog.CREDENTIALS`tan türetilir — elle liste DEĞİL, `tests/test_settings_route.py`
dersi). `compose.yaml` yalnız yerel geliştirme için.

**Dokunulan.** yeni `Dockerfile`, `.dockerignore`, `compose.yaml`,
`.env.example`, `app.py`/`routers/kok.py` (`/health`), `ci.yml` (`docker
build` işi, imaj itmez), `docs/graflar/uc-noktalar.md` (yeni rota),
`README.md` geliştirici rehberi (`docker run` satırı), `tests/test_health.py`
(yeni), `tests/test_i18n.py` sınıflandırması (rota metni i18n'e girmiyor).

**Risk.** Düşük. Kimlik dosyası `~/.config/kromis/credentials.env`
(`paths.py:187`) konteynerde yok — BYOK web'de `POST /api/settings` ile
yazılıyor, yani `KROMIS_DATA_DIR` altındaki dizin yazılabilir olmalı;
`azure_client._atomic_write`in `os.fchmod(0o600)` çağrısı bind-mount'ta
çalışır, `tmpfs`te de çalışır.

**Çıkış ölçütü.** `docker build . && docker run -p 8765:8765 kromis` sonra
`curl /health` 200 ve `/` arayüzü açılıyor; CI `docker build` yeşil; takım yeşil.

---

## Faz 0 dışı, ama burada not edilen

* `guncelleme.py` (GitHub Releases sürüm denetimi, 39 test): dondurulmuş
  masaüstü kullanıcıya "yeni sürüm" demeye devam eder — web sürümleri
  tag'lendiğinde yanlış pozitif. Faz 1'de "son masaüstü sürümü" işaretçisi ya
  da web'de kapatma.
* `tests/test_release_manifest.py`, `test_paket_icerik_listesi.py`,
  `test_ci_varlik_saklama.py`, `test_windows_acilis.py`, `test_desktop.py`,
  `test_winclr.py`, `test_winsec.py`, `test_screencolor.py`, `test_netguard.py`,
  `test_android_*.py` (~190 test) dondurulmuş kabuğu koruyor. Silinmiyor —
  elle yayın yolu hâlâ onlara dayanıyor; kabuk ince WebView'a dönüştüğü gün
  toptan giderler.
