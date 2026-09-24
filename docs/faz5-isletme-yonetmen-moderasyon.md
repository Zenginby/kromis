# Faz 5 — İşletme: prompt yönetmeni kademeleri ve sohbet kredisi, kötüye kullanım ve moderasyon, ölçek, tatbikat, kapanış: görev listesi

**Tarih:** 2026-09-24 · **Durum:** **öneri — 0/8** (plan PR'ı `faz5/plan`; görevler `faz5/<slug>` dallarında, her biri bir PR, hepsi `main`e karşı) · **Karar:** K1–K12 **sahibin kabulünü bekliyor** ("kabul ediyorum" ya da madde madde değişiklik; Faz 3 ve Faz 4'ün deseni) · **Önceki faz:** [faz4-odeme-abonelik-kvkk.md](faz4-odeme-abonelik-kvkk.md) (8/8 ✅, kapanış 2026-09-24, PR #69–#86 arası; `main` `e52baa4` = #86 lisans geçişinin merge'i)
**Üst belge:** Faz 4 belgesinin "Faz 4 kapanışı" bölümündeki **"Faz 5'e devir listesi"** (on beş madde) bu belgenin girdisi; yol haritası Faz 5 kartı "işletme" (`docs/ozellikler.md` "Faz 5: SaaS & Bulut Altyapısı"). **Numaralama tuzağı** aynen (Faz 3 `:4`, Faz 4 `:4`): master spec'in "Faz 5"i ürün yol haritasının SaaS kartı; bu belge SaaS dönüşümünün İÇ dizisindeki Faz 5'tir (Faz 0 web-first → 1 DB/hesap → 2 kuyruk → 3 kredi defteri → 4 ödeme/KVKK → **5 işletme**). Otomasyon akışları planı ([otomasyon-akislari-plani.md](otomasyon-akislari-plani.md), PR #83) AYRI bir dizidir (A0–A5): bu belge onun iki "otomasyondan bağımsız bulgusunu" (silme/dışa aktarma kapsam bekçisi, C2PA görünürlüğü) ve Kromis Ajanı'nın önkoşulunu (sohbet kredi ekseni) alır; A1 ve sonrası kendi görev listesiyle gelir.

Faz 5'in amacı, para alan ve hesap silen bir ürünü (Faz 4) **işletilebilir** kılmak
ve sahibin 2026-09-21 yönlendirmesiyle ilk maddeye konan **prompt yönetmeni
modunu** getirmek: yönetmene **effort / kalite / düşünme kademesi** gelir ve
istek, o kademeyi karşılayan sohbet modelleri arasında ucuz-hızlıdan
pahalı-derin-düşünene yönlendirilir (K1, K2); sohbet ilk kez **kredilenir**
(bugün `POST /api/chat` defterle hiç konuşmuyor — K3, K4); ikinci adımda
yönetmen **öneri kartlarıyla** görsel/video üretimini kendisi kurar (K8).
İşletme yarısı: **kötüye kullanım ve moderasyon** (IP hız sınırı, sağlayıcı
içerik reddi sayacı ve üretim kilidi — K5), Faz 3'ten devreden **ölçek
kalemleri** (`tutarlilik` artımlı tarama, `silme_turu` sayfalama, dağıtımda
boşaltma — K7), **yedek geri yükleme tatbikatı** (isletme § 5 iskeletinin
doldurulması — K11), KVKK'nın iki eksiği (silme/dışa aktarma **kapsam
bekçisi**, admin'in bir hesap adına dışa aktarma/silme ucu — K10) ve Faz 4'ün
küçük devirleri (`core.js` tek yönlendirme, `siparisler.checkout_id`, `/giris`
`/planlar` `/hukuk`ta görünür "Kaynak kodu" bağlantısı, C2PA `saglayici_meta`
görünürlüğü). Kapanışta ölçümle karar: **BYOK'ta platform payı** (K10 — yalnız
ölçüm), **vanilla yeniden bakış** (K12), **TR ikinci ayak** (K9 — bu fazda yok,
ölçütü yazılı).

**BU FAZDA YOK** — gerekçeleri "Faz 5 dışı" bölümünde:

* **TR içi TRY satışı (iyzico/PayTR), e-Arşiv, taksit** → karar ölçütü K9'da;
  kod yok. MoR'un yerine değil yanına (master `:189-192`).
* **NSFW / içerik sınıflandırıcısı (ayrı model çağrısı)** → yok (K5): sağlayıcı
  süzgeçleri zaten reddediyor, biz REDDİ SAYARIZ; sınıflandırıcı iş başına ek
  çağrı + yanlış pozitif, Polar AUP incelemesi isterse yeniden açılır.
* **Yönetmenin sunucu tarafında araç çağıran otonom döngüsü** → yok (K8):
  otomasyon planı "Yönetmen güdümlü ajan"ı aynı gerekçeyle reddetti (maliyet ve
  çıktı önceden bilinmiyor); v1 "öner ve onayla".
* **Otomasyon akışları A1–A5** (`akislar`, zamanlama, yayın) → kendi belgesi ve
  görev listesi; bu fazla paralel gidebilir, ödeme koduna dokunmuyor.
* **E2/E3 hızlı araçlar mini fazı** (Faz 3 K10) → bu fazdan sonra, aynen.
* **Google girişi (3b), video filigranı, "iş bitti" e-postası, sağlayıcı
  idempotency anahtarı, `saglayici_maliyet_usd` otomatik** → Faz 3/4 açık
  kalemleri aynen; ürün kararı ya da sağlayıcı desteği bekliyor.
* **Yıllık plan, Max kademesi, kupon** (yol haritası kartı) → Polar destekliyor,
  ürün kararı yok; `urunler.tur` CHECK'i açık.

Her madde bir PR (`faz5/<slug>` dalı), her PR tek başına yeşil ve geri
alınabilir; her PR'da testler + `docs/graflar` aynı commit'te, tam takım E2E
dahil yerelde koşulur (`KROMIS_E2E_ZORUNLU=1`), ruff + mypy ayrıca. Sıra
bağımlılığa göre: **1** (şema + bekçiler, önce — tek göç K6, sonraki görevler
sütunları hazır bulur), **2 → 3** (yönetmen omurgası: kademeler → sohbet
kredisi), **4** (kötüye kullanım; 1'in sütunlarını kullanır, 2-3'ten bağımsız),
**5** (ölçek ve küçük kalemler; bağımsız), **6** (yönetmen ajanı; 2 ve 3'ten
sonra), **7** (tatbikat aracı; bağımsız — sahibin canlı adımı var), **8** en son
(operasyon, ölçümler, kapanış). 4, 5 ve 7 omurgayla paralel gidebilir.

**NEDEN TEK GÖÇ (`0009_isletme`) — dört görevin sütunları 1. görevin göçünde.**
Faz 3 ve Faz 4'ün gerekçesi aynen: `isler.tur` CHECK'ine `sohbet` (3),
`isler.hata_turu` (4), `kullanicilar.uretim_kilidi_bitis` (4),
`giris_denemeleri.tur` CHECK'ine iki IP türü (4), `siparisler.checkout_id` (5),
`isciler.son_tam_tarama` (5) — hepsi NULL/öntanımlı, geriye uyumlu, sahibin
canlıda BİR `tools/goc.py` koşusu. **Yeni tablo YOK** → tablo 17, RLS 10 tablo /
32 politika, `IS_TABLOLARI` 10 DEĞİŞMEZ (bekçiler aynen geçer). Sohbet için
`isler` satırı yazmak (K3) yeni tablo istemiyor; yönetmen ajanının önerileri
(K8) saklanmıyor, cevap gövdesinde gidiyor.

Ölçüler Faz 4 kapanışından (`e6fafee` = #85; #86 yalnız lisans): takım **4.301
geçti, 12 atlandı, ~296 sn** (E2E + Postgres zorunlu); **81 rota** (`ACIK` 10,
`KAPILI` 71, `ADMIN_ROTALAR` 9, `SAYFALAR` 4), **118 modül**, şema başı
**`0008_odeme`**, **17 tablo**, RLS **32**, `HAREKET_TURLERI` **7**,
`OPERATOR_ARACLARI` **11**, tarayıcı betiği **15**, şablon **6**, katalog **13
görsel + 10 video + 5 sohbet** (`CHAT_MODELS`: Azure dağıtımı, GPT-5.6
Terra/Luna/Sol, Gemini 3.7 Flash — `chat_providers._ADAPTERS` üç sağlayıcı:
`azure`, `openai`, `gemini`; `ChatModel.provider` yorumu `anthropic`i sayıyor
ama adaptörü yok), i18n **1.145** anahtar tr/en birebir. Bugünkü parçalar ve
Faz 5'in dokunacağı yerler:

* **Sohbet** `routers/sohbet.py::chat` — SENKRON, kullanıcının kendi
  kimliğiyle (`kimlik.KIMLIKLER`), `modeller.director_context(plan=…)` →
  `chat_prompt.build_system` → `chat_providers.complete(req.model or
  DEFAULT_CHAT_MODEL, …)`; **defter yok, `isler` satırı yok, kota yok**.
  `ChatModel(id, label, provider, credential, wire_model, wire_from_env,
  endpoint_path, needs_max_tokens, note, kind, plan)` — `plan` alanı var
  (1b-B'nin `kapsiyor(plan, spec, platform_anahtariyla=…)` kapısı görselde
  uygulanıyor, sohbette henüz değil). `chat_client.complete` Azure yolu;
  `openai_chat.complete` OpenAI + Gemini (OpenAI-uyumlu uç).
* **Kota** `services/kota.py`: `KROMIS_SAATLIK_IS_TAVANI` (60, herkese, BYOK
  dâhil — belgesi "Faz 5'in kötüye kullanım kartının tohumu" diyor),
  `KROMIS_GUNLUK_KREDI_TAVANI` (2.000, platform anahtarı), `isler`den sayılır;
  `kullanicilar.gunluk_kredi_tavani` kişi başı ezme. IP'ye bakan hiçbir şey yok.
  `routers/hesap.py`: `giris_denemeleri` (`tur` CHECK'li) hesap başına deneme
  sayacı, `_cok_deneme` 429 + `Retry-After`; dışa aktarma saatte 1 (bellekte
  `_DISA_AKTARIMLAR` — süreç yeniden başlayınca sıfırlanır).
* **İçerik reddi** `providers.is_content_policy` (OpenAI "content policy",
  Azure "content filter", Google "safety", fal) → her adaptör kendi
  `err.*_content_policy` metnini üretir → işçi işi `hata`ya yazar ve krediyi
  iade eder; **reddin türü hiçbir sütunda yok**, sayılamıyor.
* **İşçi** `services/isci.py`: `bakim_turu` 5 dk'da bir yedi adım
  (`hibe_turu`, `tutarlilik` TAM defter taraması, bayat, `silme_turu`,
  saklama, `olay_saklamasi`…), `KROMIS_IS_KALP_ESIGI_SN` 300 = `fly.toml`
  `kill_timeout`; SIGTERM kökteki `isci.py`de; `defter.tutarlilik(db)` her
  kullanıcıda iki kova SUM; `silme_turu` kiracı önekini listeler (R2 maliyeti
  ölçülmedi).
* **KVKK** `routers/hesap.py::sil` + `isci.silme_turu` ELLE TUTULAN tablo
  listesi; `services/disa_aktar.py` dokuz dosyalık ZIP, yine elle liste;
  **yeni bir RLS tablosunun iki listeden birine girmediğini yakalayan test
  yok** (otomasyon planı bulgu 2). Admin'in bir hesap adına dışa aktarma /
  silme ucu yok (Faz 4 §7 sapma g).
* **Ön yüz** `static/core.js::girisSayfasinaGit` `location.replace` (`:38`),
  401 gören her sarmal çağırıyor — iki eşzamanlı 401 iki yönlendirme (PR #85'in
  E2E yarışı, test tarafında sarıldı). `/giris`, `/planlar`, `/hukuk`
  şablonlarında kaynak adresi yalnız HTML yorumunda; `index.html:1555` sürüm
  sayfasına bağlantı var.
* **Yedek** `docs/isletme.md § 5` yedi adımlık geri yükleme iskeleti — "Faz
  5'in kalemi", hiç koşulmadı; § 8 ikinci kova `rclone sync` (sahibin cron'u).
* **Belgeler:** KURULUM.md web bölümü **11 adım**; `isletme.md` § 9 günlük
  işletme; `.env.example` 1. bölüm ↔ `ALTYAPI` birebir (bekçi
  `tests/test_docker_kapisi.py`); Faz 4 belgesi "Faz 5'e devir listesi".

---

## Envanter: bugünkü parçalar → Faz 5 parçaları

Adlar ÖNERİ (Türkçe, ASCII); her satır hangi görevde değiştiğini söylüyor.

| bugün | nerede | Faz 5'te | görev |
| --- | --- | --- | --- |
| `isler.tur` CHECK 4 tür; `hata` metni serbest; `giris_denemeleri.tur` hesap türleri; `siparisler`de checkout kimliği yok | `services/tablolar.py` | `0009_isletme`: `tur` +`sohbet`, `hata_turu` (`icerik`/`anahtar`/`zaman_asimi`/`saglayici`/`diger`, NULL), `kullanicilar.uretim_kilidi_bitis`, `giris_denemeleri.tur` +`ip_kayit`/`ip_giris`, `siparisler.checkout_id` (UNIQUE, NULL), `isciler.son_tam_tarama` | 1 |
| Silme/dışa aktarma listeleri bekçisiz | `tests/test_hesap_silme.py` | **Kapsam bekçisi:** RLS'li her tablo ∈ `silme_turu` listesi ∪ gerekçeli muafiyet (`kredi_hareketleri`, `siparisler` — mali kayıt K9) ve ∈ `disa_aktar` listesi ∪ gerekçeli muafiyet (sırlar: `saglayici_kimlikleri`, `oturumlar`, `jetonlar`); CLAUDE.md § 5 deyimi | 1 |
| `ChatModel.plan` var, kademe yok; 5 model, 3 adaptör | `catalog.py`, `chat_providers.py` | `ChatModel.kademe` (`hizli`/`dengeli`/`derin`) + `kredi` (tur başına); **`anthropic` sağlayıcısı** (`anthropic_chat.py`, `Credential("anthropic")`, Messages API, `needs_max_tokens=True`); yönlendirme `services/yonetmen_yolu.py::sec(kademe, plan, kimlikler)` | 2 |
| Yönetmen paneli model seçici | `static/chat.js`, `settings.js` | Kademe seçici (öntanımlı `dengeli`) + "Gelişmiş: modeli kendim seçerim"; tercih `yonetmen_kademe` (`depo_tercih`); kimlik yoksa kademe kartında "kur" bağlantısı | 2 |
| `POST /api/chat` kredisiz, `isler`siz | `routers/sohbet.py` | Platform anahtarı yolunda `isler` satırı `tur='sohbet'` (`durum` `calisiyor` → `tamam`/`hata` aynı istekte; kuyruk `sohbet`i HİÇ almaz) + `kapilar.rezerve_kredi` → `defter.onayla`/`iade`; BYOK'ta satır var, defter yok; 402 `err.kredi_yetersiz` aynen | 3 |
| Sohbette plan kapısı yok | `services/planlar.py::kapsiyor` | Aynı kapı sohbete: platform anahtarıyla `hizli`→`free`, `dengeli`→`temel`, `derin`→`pro`; BYOK eşiği aşar (1b-B kuralı) | 3 |
| Kota IP'siz; içerik reddi sayılmıyor | `services/kota.py`, `services/isci.py` | `services/hiz.py::check_ip(kapsam, ip)` DB'de kayan pencere (`giris_denemeleri`, `KROMIS_IP_SAATLIK_TAVANI` 30); işçi `hata_turu` yazar; `kota.check_icerik_kilidi` 403 `err.icerik_kilidi`; `KROMIS_ICERIK_REDDI_TAVANI` 10 / 24 s → `uretim_kilidi_bitis` +24 s; admin "Kötüye kullanım" sekmesi + kilit kaldır | 4 |
| `tutarlilik` tam tarama 5 dk'da; `silme_turu` sınırsız listeleme; SIGTERM davranışı belgesiz | `services/defter.py`, `services/isci.py`, `isci.py` | `tutarlilik(db, since=…)` yalnız son turdan beri hareketi olan kullanıcılar + günde bir tam tarama (`isciler.son_tam_tarama`, `KROMIS_TUTARLILIK_TAM_TARAMA_SAAT` 3); `silme_turu` tur başına `KROMIS_SILME_TUR_TAVANI` 5 hesap, sayfalı liste; SIGTERM → **boşalt** (yeni iş alma, eldekini bitir, kalp sürer) — ölçülür, isletme § 9'a "dağıtım penceresi" | 5 |
| `core.js` iki 401 → iki `location.replace`; teşekkür "son 15 dk"; "Kaynak kodu" yalnız yorumda; C2PA kaybı görünmez | `static/core.js`, `routers/odeme.py`, şablonlar, `fal_client._png_garantile`, `filigran.uygula` | `girisSayfasinaGit` idempotent (modül bayrağı); `siparisler.checkout_id` + `?checkout_id=` eşlemesi; üç sayfanın altına görünür "Kaynak kodu" (FSL, `TELIF.md`); `saglayici_meta.c2pa` = `var`/`dustu`/`yok` (otomasyon planı seçenek a — davranış değişmez) | 5 |
| Yönetmen yalnız metin döner | `chat_prompt.py`, `routers/sohbet.py`, `static/chat.js` | **Öneri kartları** (K8): yönetmen isteğe bağlı `oneriler: [{tur, model, prompt, boyut, kredi_tahmini}]` JSON bloğu döner (şemayla doğrulanır, katalogdan kredi); kart → tek tıkla bugünkü `POST /api/generate`/`/api/video`; otonom döngü yok | 6 |
| isletme § 5 iskelet, tatbikat yok | `docs/isletme.md`, `tools/` | `tools/tatbikat.py`: dump'ı BOŞ Postgres'e `pg_restore` → `goc.py` → sayımlar (`kullanicilar`, `medya`, `kredi_hareketleri`, iki kova SUM) → `rls_kontrol` → rapor; `--kova` ile `rclone size` karşılaştırması; CI'da KOŞMAZ (dump yok); sahip bir kez koşar, süreler § 5'e | 7 |
| BYOK payı, vanilla, TR ayağı kararsız; admin KVKK ucu yok; KURULUM 11 | `routers/admin.py`, `depo_admin.py`, belgeler | Admin metrik `anahtar_kaynagi` oranı (30 gün) + sohbet kredisi satırı; `POST /api/admin/kullanicilar/{id}/sil` + `GET …/disa-aktar` (kapı + günlük satırı `olay=admin.kvkk`); vanilla ölçümü (JS satırı, betik sayısı, Sentry ön yüz hata oranı) kapanışa; TR ayağı karar notu (K9 ölçütü); KURULUM **12. adım "İşletme"** (tatbikat, kilit, IP sınırı, Anthropic anahtarı); Faz 5 kapanışı | 8 |

---

## 1. Şema ve bekçiler — `0009_isletme`, silme/dışa aktarma kapsam bekçisi (PR: `faz5/sema-ve-bekciler`)

**Ne:** Tek göç `0009_isletme` (yukarıda "NEDEN TEK GÖÇ"): altı sütun/CHECK
genişlemesi, yeni tablo yok. `tablolar.IS_TURLERI` +`sohbet` (`isler.tur`
CHECK yeniden yazılır — Faz 2'nin CHECK deseni), `HATA_TURLERI` yeni küme
(`icerik`, `anahtar`, `zaman_asimi`, `saglayici`, `diger`) ↔ `isler.hata_turu`
CHECK; `giris_denemeleri.tur` CHECK'ine `ip_kayit`, `ip_giris`;
`kullanicilar.uretim_kilidi_bitis TIMESTAMPTZ NULL`; `siparisler.checkout_id
TEXT UNIQUE NULL`; `isciler.son_tam_tarama TIMESTAMPTZ NULL`. Göç `tools/goc.py`
ile; `alembic/` tek dosya, `downgrade` sütunları düşürür.

**Kapsam bekçisi (otomasyon planı bulgu 2, A1'in önkoşulu):**
`tests/test_hesap_silme.py`e `test_every_rls_table_is_deleted_or_exempted` ve
`test_every_rls_table_is_exported_or_exempted`: `tests/test_rls.py`nin RLS'li
tablo kümesi (10) üzerinden, `isci.SILINEN_TABLOLAR` ∪ `SILME_MUAF` ==
küme ve `disa_aktar.AKTARILAN_TABLOLAR` ∪ `AKTARMA_MUAF` == küme; muafiyet
sözlükleri GEREKÇELİ (`{"kredi_hareketleri": "mali kayıt, K9 — anonim
kalır", …}`), boş gerekçe test kırar. Bugünkü listeler sabit adlara taşınır
(davranış değişmez); Faz 4'ün `isler`/`medya`/… yedi tablosu ve
`saglayici_kimlikleri`/`oturumlar`/`jetonlar` sırları ilk doldurmadır.

**Testler:** `test_tablolar` (CHECK kümeleri, sütun varlığı, göç
`(head)`), `test_rls` 32 politika DEĞİŞMEDEN geçer, `test_goc` up/down,
kapsam bekçileri ×2, `test_kuyruk` "`sohbet` türünü işçi almaz" (kuyruk
`al`ın WHERE'ine `tur != 'sohbet'` — 3. görevin garantisi burada kurulur).
Beklenen +~20 test. **Belge çapası:** bu bölümdeki cümle
"`IS_TURLERI` 4 → 5: `sohbet`" ve "`HATA_TURLERI` beş tür" —
`test_tablolar` Faz 5 belgesini de okur (Faz 4'ün `BELGE_FAZ4` deseni,
`BELGE_FAZ5`).

**Sahibin adımı:** canlıda `tools/goc.py` bir kez (dağıtım ÖNCESİ, isletme § 1).

## 2. Yönetmen kademeleri ve Anthropic — `ChatModel.kademe`, `services/yonetmen_yolu.py`, `anthropic_chat.py` (PR: `faz5/yonetmen-kademeleri`)

**Ne (K1, K2):** Kullanıcı yönetmen panelinde **kademe** seçer: `hizli`
(ucuz, anlık), `dengeli` (öntanımlı), `derin` (uzun düşünen). Kademe, modeli
ve sağlayıcıyı GİZLEMEZ — kart "→ Claude Sonnet 5" diye gösterir (KVKK alt
işleyen şeffaflığı); "Gelişmiş" düğmesi bugünkü model seçicisini açar ve
seçim yönlendirmeyi atlar (bugünkü davranış aynen, `req.model` dolu).
`ChatModel`e iki alan: `kademe: str` (`KADEMELER = ("hizli", "dengeli",
"derin")`, CHECK'i test) ve `kredi: int` (tur başına, K3'ün birimi; BYOK'ta
okunmaz). Yönlendirme `services/yonetmen_yolu.py::sec(kademe, plan, kimlikler)
-> Secim(model, anahtar_kaynagi)`: `CHAT_MODELS` katalog sırasıyla, kademesi
eşit modeller arasında **önce kullanıcının kendi kimliği olan** (BYOK, bedava),
yoksa **platform kimliği olan ve `kapsiyor(plan, model,
platform_anahtariyla=True)` geçen**; hiçbiri yoksa 403 `err.plan_kapsamiyor`
(kademe adı ve gereken planla) ya da 409 `err.kademe_kimliksiz` (platform
anahtarı da yoksa — self-host). Katalog sırası kademe içinde "önce dengeli"
kuralını korur (`CHAT_MODELS` yorumu).

**Anthropic sağlayıcısı (K2):** `catalog.Credential("anthropic",
env="ANTHROPIC_API_KEY", base_url="https://api.anthropic.com")`,
`anthropic_chat.py` (Messages API `POST /v1/messages`, `x-api-key` +
`anthropic-version`, `system` ayrı alan, `max_tokens` ZORUNLU —
`needs_max_tokens=True` alanı bunun için yazılmıştı; `thinking` yalnız
`derin`de `{"type": "adaptive"}`; cevap `content[0].text`; 400 içerik reddi
`providers.is_content_policy` → `err.anthropic_content_policy`; 401
`is_invalid_key`). SDK EKLENMEZ — `httpx` ile ham uç, `openai_chat`ın deseni
(bağımlılık listesi değişmez). Üç girdi (fiyatlar 2026-06-24 tarihli Anthropic
listesi — **sahip doğrular**, `tarife_kontrol`a sohbet satırı gelir):
`anthropic-claude-haiku-4-5` (`hizli`, 1 USD / 5 USD per MTok),
`anthropic-claude-sonnet-5` (`dengeli`, 2 / 10), `anthropic-claude-opus-5`
(`derin`, 5 / 25). Mevcut beş girdinin kademesi: Azure dağıtımı `dengeli`
(model bilinmiyor — ortamdan), GPT-5.6 Terra `dengeli`, Luna `hizli`, Sol
`derin`, Gemini 3.7 Flash `hizli` — **öneri**, sahibin GPT/Gemini fiyat
doğrulamasıyla değişebilir. `chat_providers._ADAPTERS` +`anthropic` (mandal
testi 3 → 4), `ALTYAPI` +`ANTHROPIC_API_KEY` (platform anahtarı; kullanıcı
kendi anahtarını Ayarlar › Anahtarlar'a girer — `saglayici_kimlikleri`
`credential='anthropic'`, şifreli, bugünkü desen).

**Hukuk (K2'nin bedeli):** Anthropic yeni **alt işleyen** — `bundled/hukuk/`
aydınlatma metninde sağlayıcı listesine girer, `HUKUK_SURUMU` `2026-10` →
`2026-11`, var olan kullanıcı sürüm değişince yeniden onaylar (K11 Faz 4
mekanizması). Metin "taslak" damgasıyla; avukat onayı sahibin.

**Ön yüz:** `static/chat.js` kademe seçici (üç kart, seçili modeli ve kredisini
gösterir: "3 kredi/tur" ya da "kendi anahtarın — bedava"), tercih
`yonetmen_kademe`; `GET /api/models` sohbet listesine `kademe`, `kredi`;
`settings.js` Anahtarlar bölmesine Anthropic satırı. i18n +~25 (tr/en).

**Testler:** `test_catalog` kademe/kredi bekçileri (her kademede en az bir
model; `kredi` ≥ 1; `derin`in kredisi `hizli`nınkinden büyük), `test_chat_providers`
anthropic adaptörü (gövde, `max_tokens`, `system`, thinking yalnız derin,
hata eşlemesi — kaydedilmiş cevaplar), `test_yonetmen_yolu` seçim tablosu
(BYOK > platform, plan kapısı, kimliksiz), E2E kademe seçici + tercih kalıcı
(sahte sağlayıcı), `test_hukuk` sürüm ve yeniden onay, `test_araclar`
`tarife_kontrol` sohbet satırı. Beklenen +~60 test.

**Sahibin adımları:** Anthropic hesabı + platform anahtarı (`ANTHROPIC_API_KEY`
web sürecine); fiyat doğrulaması (Anthropic, OpenAI GPT-5.6 ×3, Gemini 3.7
Flash); kademe atamasına itiraz varsa PR yorumunda; aydınlatma metni avukata.

## 3. Sohbet kredisi — `isler` satırı `tur='sohbet'`, rezerv → onay/iade, plan kapısı (PR: `faz5/sohbet-kredisi`)

**Ne (K3, K4):** `POST /api/chat` platform anahtarı yolunda **ilk kez
defterle konuşur**. Akış: `yonetmen_yolu.sec` → `anahtar_kaynagi ==
'platform'` ise `kapilar.check_plan` (K4), `kota.check_saatlik` (herkese —
BYOK dâhil, iş satırı yazıldığı için sayaç kendiliğinden işler),
`kota.check_gunluk` (platform), `rezerve_kredi(model.kredi)` + `isler` satırı
(`tur='sohbet'`, `durum='calisiyor'`, `model`, `kredi_tahmini=model.kredi`,
`istek={"kademe": …, "mesaj_sayisi": n}` — mesaj GÖVDESİ YAZILMAZ, sohbet
içeriği `sohbetler`in işi ve kullanıcının "sakla"sı) AYNI transaksiyonda
(Faz 3 K1'in `kuyruk.ekle` deseni, `sohbet` için `kuyruk.sohbet_ac`); sağlayıcı
çağrısı; `defter.onayla` + `durum='tamam'` ya da `iade` + `durum='hata'` +
`hata_turu`. Tur başına SABİT kredi (`ChatModel.kredi`), jeton sayılmaz —
gerekçe K3'te. BYOK yolunda satır yazılır (kota, admin paneli, ölçüm) ama
defter çağrılmaz (`anahtar_kaynagi='kullanici'`, Faz 3 K3 aynen).
Kuyruk `sohbet`i almaz (1. görevin garantisi); bakım turunun bayat düşürmesi
`sohbet` satırına da bakar: istek düşerse (süreç ölür) `calisiyor` kalan satır
`KROMIS_IS_KALP_ESIGI_SN` sonra `hata` + iade — mevcut mekanizma, `sohbet`
için kalp yazılmaz, `olusturuldu` esas alınır.

**Ön yüz:** `krediYenile()` sohbet cevabından sonra (bugünkü `core.js`
deseni); 402 toast'ı `/planlar`a (Faz 4 K7 bağlantısı); Ayarlar › Kredi
"son hareketler"de `sohbet` satırı (`KREDI_HAREKET_ANAHTARI` değişmez — tür
`rezerv`/`onay`; iş türü satırın açıklamasında). Admin metriklerinde
`isler.tur` kırılımına `sohbet` kendiliğinden düşer (`test_admin` küme
bekçisi +1).

**Testler:** `test_chat_route` rezerv/onay/iade üçlüsü (sahte sağlayıcı: başarı,
502, içerik reddi), 402 ön denetim, BYOK'ta defter dokunulmaz, `isler` satırı
şekli (gövde yok), kademe-plan kapısı 403 (`free` + `derin`), `test_kota`
sohbet sayılır, `test_isci` bayat `sohbet` satırı iade, E2E: platform
anahtarıyla bir tur → bakiye `kredi` kadar düşer → Kredi bölmesinde satır.
Beklenen +~45 test. `tests/test_uretim_kapilar.py`nin AST bekçisi ("bakiye
yazan tek modül `defter.py`") aynen geçer.

**Sahibin adımı:** `ChatModel.kredi` sayıları (öneri: `hizli` 1, `dengeli` 3,
`derin` 15 — hesap K3'te) son kez; `KROMIS_GUNLUK_KREDI_TAVANI` sohbetle
paylaşılıyor, 2.000 yeterli mi.

## 4. Kötüye kullanım ve moderasyon — IP hız sınırı, içerik reddi sayacı, üretim kilidi, admin sekmesi (PR: `faz5/kotuye-kullanim`)

**Ne (K5):**

* **IP hız sınırı** `services/hiz.py::check_ip(db, kapsam, ip, tavan,
  pencere)`: `giris_denemeleri`ne `tur='ip_kayit'|'ip_giris'`,
  `anahtar=hash(ip)` (HMAC `KROMIS_SECRET_KEY` ile, ham IP YAZILMAZ — IP
  kişisel veri; satırlar 24 s sonra bakım turunda silinir, mevcut deneme
  temizliğiyle). Uygulanan uçlar: `POST /api/hesap/kayit`, `POST
  /api/hesap/giris`, `POST /api/hesap/sifre-sifirla*` (varsa),
  `POST /api/odeme/webhook` HARİÇ (imzalı). Tavan `KROMIS_IP_SAATLIK_TAVANI`
  (boş = 30; 0 = kapalı — self-host tek IP arkasında; bozuk → `ValueError`).
  İstemci IP'si: `Fly-Client-IP` > `X-Forwarded-For` ilk öğe **yalnız
  `KROMIS_PROXY_GUVEN=1` ise**, yoksa soket adresi — başlığa körü körüne
  güvenmek sınırı bir başlıkla deldirir. 429 + `Retry-After` (`_cok_deneme`
  aynen). Bellekteki `_DISA_AKTARIMLAR` da bu tabloya taşınır (`tur=
  'disa_aktarma'`) — süreç yeniden başlayınca sıfırlanma kusuru kapanır.
* **İçerik reddi sayacı:** işçi `hata`ya yazarken `hata_turu`nu sınıflar
  (`providers.is_content_policy` → `icerik`; `is_invalid_key` → `anahtar`;
  `httpx.TimeoutException` → `zaman_asimi`; öteki HTTP → `saglayici`; kalan
  → `diger`) — metin değişmez, sütun eklenir. `kota.check_icerik_kilidi`:
  `uretim_kilidi_bitis > now` ise 403 `err.icerik_kilidi` (bitiş saatiyle);
  işçi `icerik` yazdığında son 24 saatteki `icerik` sayısı ≥
  `KROMIS_ICERIK_REDDI_TAVANI` (boş = 10; 0 = kapalı) ise
  `uretim_kilidi_bitis = now + KROMIS_ICERIK_KILIDI_SAAT` (boş = 24), günlük
  `olay=kota.icerik_kilidi kullanici=… sayi=…` WARNING (Sentry'ye düşer —
  isletme § 6 uyarı olayı +1). Kilit yalnız ÜRETİMİ kapar (`generate`,
  `edit`, `video`, `animate`, `sohbet` platform yolu); giriş, galeri, hesap
  silme, dışa aktarma açık kalır (KVKK hakları kilitlenmez). Sağlayıcı reddi
  iade edilmeye devam eder (Faz 3 K2) — kilit iadeyi kaldırmaz; kötüye
  kullanan iade alır ama 24 saat üretemez, tekrarında admin.
* **Admin "Kötüye kullanım" sekmesi:** kilitli hesaplar (bitiş, sayı),
  son 7 günde en çok `icerik` reddi alan 20 hesap, IP sınırına takılan
  hash'ler (sayı), `POST /api/admin/kullanicilar/{id}/kilit-kaldir`
  (`ADMIN_ROTALAR` 9 → 10) ve `…/kilitle` (elle, süreyle).

**Testler:** `test_hiz` pencere/hash/`Retry-After`/başlık güveni/0 = kapalı,
`test_hesap` kayıt ve giriş 429 (IP), `test_isci` `hata_turu` sınıflaması
(beş tür, sahte sağlayıcı hataları), kilit eşiği (9 red → yok, 10. → kilit),
`test_uretim_kapilar` 403 kilit + KVKK uçları açık, `test_admin` sekme ve
iki rota, E2E: kilitli hesapta üret düğmesi 403 toast'ı. Beklenen +~50 test.
`.env.example`/`ALTYAPI` **+4** (`KROMIS_IP_SAATLIK_TAVANI`,
`KROMIS_PROXY_GUVEN`, `KROMIS_ICERIK_REDDI_TAVANI`, `KROMIS_ICERIK_KILIDI_SAAT`).

**Sahibin adımları:** Fly'da `KROMIS_PROXY_GUVEN=1` (Fly proxy `Fly-Client-IP`
yazar — doğrulanır); tavanlar ilk ay öntanımlı, admin sekmesinden bakılır;
kullanım şartlarının "kötüye kullanım" maddesine "geçici üretim kilidi"
cümlesi (avukat turuna eklenir).

## 5. Ölçek ve küçük devirler — artımlı `tutarlilik`, `silme_turu` tavanı, boşaltma, `core.js`, `checkout_id`, "Kaynak kodu", C2PA görünürlüğü (PR: `faz5/olcek-ve-devirler`)

**Ne (K7 + devirler):**

* `defter.tutarlilik(db, *, since=None)`: `since` verilirse yalnız
  `kredi_hareketleri.olusturuldu > since` olan kullanıcılar; bakım turu
  `isciler.son_tam_tarama`ya bakar — günde bir kez
  (`KROMIS_TUTARLILIK_TAM_TARAMA_SAAT`, boş = 3 UTC) tam tarama, aralarda
  artımlı (`since` = önceki turun `an`ı, `isciler` satırında). `BakimOzeti`
  +`tutarlilik_kapsami` (`tam`/`artimli`, taranan sayı). 1.000+ kullanıcıda
  ölçüm: sentetik 5.000 kullanıcı × 20 hareket fikstürüyle süre, belgeye.
* `silme_turu`: tur başına en çok `KROMIS_SILME_TUR_TAVANI` (boş = 5) hesap,
  kalanlar sonraki tura (sıra `temizlendi_at` yaşına göre); nesne listeleme
  `Depo.listele` sayfalı (`ContinuationToken`) — bugünkü tek çağrı 1.000
  nesnede kesiliyor mu ölçülür (S3 `MaxKeys` öntanımlısı 1.000; boto
  paginator).
* **Boşaltma:** kökteki `isci.py` SIGTERM'de `bosaltiliyor` bayrağı → ana
  döngü yeni iş ALMAZ, eldeki işler biter, kalp sürer; `kill_timeout` içinde
  bitmeyen iş bugünkü bayat mekanizmasıyla iade edilir (kayıp değil, iade —
  K7). `fly.toml` `kill_timeout` 300 aynen; isletme § 9'a "dağıtım penceresi:
  video işleri kuyruktayken dağıtma; `isler` bekleyen/koşan sayısı" satırı
  ve `/health`e `bosaltiliyor` alanı. Ayrı video işçisi süreci → K7
  alternatifi, `isler` video payı ölçüldükten sonra.
* `static/core.js::girisSayfasinaGit` modül düzeyinde `yonlendiriliyor`
  bayrağı: ikinci çağrı no-op; `tests/test_playwright_hesap.py:330`'un
  `wait_for_function` sarması `wait_for_url`a geri döner (PR #85'in sarması
  ürün garantisiyle kalkar).
* `siparisler.checkout_id` (1. görevin sütunu): checkout yaratılırken
  `polar.checkout_ac` dönen id yazılır (`siparisler` satırı henüz yok —
  `checkout_id` `odeme_olaylari`na değil, `kullanicilar` başına geçici
  `bekleyen_checkout` sözlüğüne DEĞİL: `order.paid` gövdesindeki
  `checkout_id` ile sipariş satırına yazılır; teşekkür sayfası
  `?checkout_id=` ile `siparisler` sorgular, "son 15 dk" ölçütü yedek kalır).
* **"Kaynak kodu"** bağlantısı `/giris`, `/planlar`, `/hukuk` alt bilgisine
  (FSL-1.1-ALv2, `TELIF.md`; i18n `footer.kaynak_kodu`); `index.html`
  Ayarlar › Hakkında'da zaten var (#86).
* **C2PA görünürlüğü** (otomasyon planı seçenek a): `fal_client._png_garantile`
  ve `filigran.uygula` dokunmadan önce `caBX`/APP11 varlığını ölçer,
  `saglayici_meta.c2pa` = `var` / `dustu` / `yok` yazar; davranış DEĞİŞMEZ;
  admin marj tablosunun yanında `c2pa_dustu` sayısı. Test: C2PA'lı JPEG
  fikstürü → `dustu`.

**Testler:** `test_defter` artımlı tarama (hareketi olmayan kullanıcı
taranmaz, tam taramada taranır; sapma yakalama iki kipte), `test_isci`
tam/artımlı seçimi ve `son_tam_tarama`, silme tavanı ve sıra, boşaltma
(SIGTERM → yeni iş alınmaz, eldeki biter), `test_odeme_route` `checkout_id`
eşlemesi, E2E: iki eşzamanlı 401 → TEK yönlendirme (PR #85'in yarışı ürün
testine döner), üç sayfada bağlantı görünür, `test_saglayici_meta` c2pa üç
değer. Beklenen +~40 test. `.env.example`/`ALTYAPI` **+2**.

## 6. Yönetmen ajanı v1 — öneri kartları, tek tıkla üretim (PR: `faz5/yonetmen-ajan`)

**Ne (K8):** Yönetmenin sistem talimatına (`chat_prompt.build_system`)
katalog özeti girer (kullanıcının planında açık modeller, kısa not, kredi;
`director_context` zaten plan biliyor) ve **isteğe bağlı** yapısal çıktı
kuralı: cevabın sonunda tek `oneriler` JSON bloğu (`[{"tur": "generate"|
"edit"|"video", "model": id, "prompt": …, "boyut"/"sure": …, "adet": 1-4}]`,
en çok 4). Sunucu (`services/yonetmen_oneri.py::ayikla`) bloğu ayırır,
şemayla doğrular (bilinmeyen model → öneri düşer, metin kalır), her öneriye
`catalog.cost_for` ile `kredi_tahmini` ekler ve `{"cevap": metin, "oneriler":
[...]}` döner (bugünkü `{"cevap"}` şekli korunur — alan eklenir). Ön yüz
`chat.js` kartları çizer: model, boyut, kredi, "Üret" düğmesi → bugünkü
`POST /api/generate`/`/api/video` (aynı kapılar: plan, kota, rezerv — YENİ
para yolu yok), "Hepsini üret" → sırayla; sonuç kartı işe bağlanır (bugünkü iş
paneli). Yönetmenin kendisi sunucuda hiçbir görsel/video çağrısı YAPMAZ;
"ajanlaşma" = öneri + kullanıcının tıkı. Sonraki adım (Faz 5 dışı):
`otomatik_uret` anahtarı — tek tıksız, bütçe tavanıyla; otomasyon planının
`yonetmen` adım türü aynı `ayikla`yı kullanır.

**Testler:** `test_yonetmen_oneri` ayıklama (blok yok / bozuk JSON / bilinmeyen
model / 5 öneri → 4 / planı aşan model düşer), kredi tahmini katalogla,
`test_chat_route` cevap şekli, E2E: sahte sağlayıcı öneri bloğu döner → kart
→ "Üret" → iş paneli satırı → bakiye düşer. Beklenen +~30 test. i18n +~12.

**Sahibin adımı:** talimat metninin Türkçe/İngilizce tonu (persona dosyası
`bundled/`de); ilk gerçek turlarda öneri kalitesi.

## 7. Yedek geri yükleme tatbikatı — `tools/tatbikat.py`, isletme § 5'in doldurulması (PR: `faz5/tatbikat`)

**Ne (K11):** `tools/tatbikat.py --dump kromis-….dump --hedef
$TATBIKAT_DATABASE_URL [--kova r2-yedek:kromis-yedek --asil r2:kromis]`:
(1) hedefin BOŞ olduğunu doğrular (tablo yoksa devam; varsa 3 çıkar — üretime
karşı çalıştırma kilidi: `DATABASE_URL` ile aynıysa reddeder); (2)
`pg_restore` alt süreç; (3) `tools/goc.py` hedefe (`(head)`); (4) sayımlar
`kullanicilar`, `medya`, `isler`, `kredi_hareketleri`, `siparisler` + her
kullanıcıda iki kova SUM == önbellek (`defter.tutarlilik` hedefte); (5)
`tools/rls_kontrol.py` hedefte 10 tablo / 32 politika; (6) `--kova` verilirse
`rclone size` iki kovada ve `medya` satır sayısıyla fark; (7) süreleri ve
farkları isletme § 5'in "Kayıt" tablosuna yazılacak biçimde basar (Markdown
satırı). Çıkış 0 tutarlı / 2 fark var / 3 ortam hatası (`polar_mutabakat`ın
deseni). `OPERATOR_ARACLARI` 11 → 12, `BAGLAM_TASIYAN_ARACLAR` +1.
**CI'da KOŞMAZ** (gerçek dump yok); testi Postgres fikstürüyle: küçük
`pg_dump` üretilir, boş ikinci şemaya geri yüklenir, sayımlar eşit; "hedef
dolu → 3"; "DATABASE_URL ile aynı → 3". `compose.yaml`a isteğe bağlı
`tatbikat-db` servisi (profil `tatbikat`).

**Sahibin adımı (canlı):** ayda bir — ilk tatbikat bu PR'dan sonra, Neon
dalı ya da yerel Postgres; süreler ve farklar isletme § 5'e satır; ikinci
kova `--kova` ile bir kez.

## 8. Operasyon, ölçümler ve Faz 5 kapanışı — admin KVKK ucu, BYOK/vanilla ölçümü, TR karar notu, KURULUM 12 (PR: `faz5/operasyon-kapanis`)

**Ne (K9, K10, K12):**

* **Admin KVKK ucu** (K10): `GET /api/admin/kullanicilar/{id}/disa-aktar`
  (aynı `disa_aktar.zip`, admin bağlamı) ve `POST …/sil` (aynı
  `hesap.sil` yolu: anonimleştir + kilitle, 7 gün sonra tur); ikisi de günlüğe
  `olay=admin.kvkk islem=… hedef=… yonetici=…` yazar (izlenebilirlik — 30
  günlük yasal süre içinde e-postayla gelen başvuru). `ADMIN_ROTALAR` +2.
* **BYOK ölçümü** (K10): admin metriklerine `anahtar_kaynagi` kırılımı (30
  gün: iş sayısı, sohbet turu, `saglayici_maliyet_usd` platform payı) —
  karar Faz 6'nın ya da bu belgenin kapanış notunun; kod fiyatlamaz.
* **Vanilla ölçümü** (K12): kapanışta `static/*.js` satır sayısı (bugün 15
  betik), Sentry ön yüz hata oranı (30 gün), E2E çapa sayısı; karar notu bu
  belgenin kapanış bölümüne — çerçeve değişimi Faz 5'te YOK.
* **TR ikinci ayak karar notu** (K9): bu belgenin "Faz 5 dışı" bölümünden
  isletme.md'ye kısa bölüm: ölçüt ve ilk adımlar (iyzico/PayTR sözleşmesi,
  e-Arşiv entegratörü, `urunler.para_birimi='try'`, `gelir` tablosunun çok
  para birimi) — kod yok.
* **Belgeler:** KURULUM **12. adım "İşletme"** (Anthropic anahtarı, IP sınırı ve
  proxy güveni, içerik kilidi, tatbikat aylık, boşaltma ile dağıtım);
  `isletme.md` § 5 doldurulmuş, § 6 +1 uyarı olayı, § 9 dağıtım penceresi;
  README tr/en bir cümle; `.env.example` ↔ `ALTYAPI` birebir;
  `docs/ozellikler.md` Faz 5 kartına tek `[x]` satırı; bu belge 8/8 ✅ +
  "Faz 5 kapanışı" (PR tablosu, ölçümler, sahibin canlı adımları, Faz 6 /
  otomasyon A1 devir listesi).

**Testler:** `test_admin` iki rota + günlük satırı + metrik kırılımı,
`test_docker_kapisi` KURULUM 12 / isletme / README / şablon bekçileri,
`test_araclar` `OPERATOR_ARACLARI` 12. Beklenen +~20 test.

---

## Faz 5 çıkış kriteri

Ücretsiz kullanıcı yönetmende **`hizli`** seçer → platform anahtarıyla Haiku
(ya da katalogda `hizli` olan ilk erişilebilir model) cevap verir → bakiye
**1 kredi** düşer, Kredi bölmesinde `sohbet` satırı → **`derin`** seçer → 403
"pro planı gerekir" → kendi Anthropic anahtarını girer → `derin` Opus'a gider,
bakiye DEĞİŞMEZ → yönetmen üç **öneri kartı** döner, "Üret" → iş kuyruğa,
rezerv → görsel galeride → kullanıcı aynı saatte **10 içerik reddi** alır →
`uretim_kilidi_bitis` dolu, üret düğmesi 403, galeri ve dışa aktarma AÇIK →
admin sekmesinde görünür, "kilit kaldır" → üretim açılır → aynı IP'den 31.
kayıt denemesi **429** → bakım turu artımlı `tutarlilik` (taranan < toplam),
03:00'te tam → `silme_turu` tur başına 5 hesap → SIGTERM'de işçi yeni iş
almaz, eldekini bitirir, `/health` `bosaltiliyor:true` → `tools/tatbikat.py`
boş Postgres'e geri yükleme, çıkış 0 → admin bir hesap adına ZIP indirir,
günlükte `olay=admin.kvkk` → `/giris`te "Kaynak kodu" bağlantısı → yeni bir
RLS tablosu iki listeden birine girmeden **kapsam bekçisi kırmızı** → tam
takım yeşil (E2E dahil, sahte sağlayıcılar ve sahte Polar ile).

---

## Veri modeli değişiklikleri — `0009_isletme` özeti

| tablo.sütun | tür | öntanımlı | görev | not |
| --- | --- | --- | --- | --- |
| `isler.tur` CHECK | +`sohbet` | — | 1/3 | `IS_TURLERI` 4 → 5: `sohbet`; kuyruk almaz |
| `isler.hata_turu` | `text` CHECK `HATA_TURLERI` | NULL | 1/4 | `HATA_TURLERI` beş tür: `icerik`, `anahtar`, `zaman_asimi`, `saglayici`, `diger`; işçi yazar |
| `kullanicilar.uretim_kilidi_bitis` | `timestamptz` | NULL | 1/4 | yalnız üretim uçları; admin kaldırır |
| `giris_denemeleri.tur` CHECK | +`ip_kayit`, `ip_giris`, `disa_aktarma` | — | 1/4 | `anahtar` = HMAC(ip); 24 s temizlik |
| `siparisler.checkout_id` | `text` UNIQUE | NULL | 1/5 | `order.paid` gövdesinden |
| `isciler.son_tam_tarama` | `timestamptz` | NULL | 1/5 | günde bir tam `tutarlilik` |

Yeni tablo yok; RLS politikası sayısı 32 aynen; `IS_TABLOLARI` 10 aynen.

---

## Güvenlik, RLS, KVKK notları

* **IP saklama:** ham IP hiçbir tabloya yazılmaz; HMAC anahtarı
  `KROMIS_SECRET_KEY` (döndürme § 3'te — döndürünce eski hash'ler eşleşmez,
  pencere zaten 1 saat). Aydınlatma metnine "kötüye kullanım önleme için IP
  özeti 24 saat" cümlesi (avukat turu).
* **Kilit KVKK haklarını kilitlemez:** dışa aktarma, hesap silme, giriş açık
  (K5). Kilitli kullanıcıya gerekçe gösterilir (`err.icerik_kilidi` bitiş
  saatiyle); itiraz kanalı hukuk metnindeki iletişim adresi.
* **Anthropic alt işleyen:** aydınlatma metni + `HUKUK_SURUMU` (2. görev);
  Anthropic API varsayılan veri saklama politikası metne yazılır (sahip
  doğrular — 30 gün mu, ZDR mi).
* **Admin KVKK ucu:** yalnız `app.rol = 'admin'` bağlamı, günlük satırı
  zorunlu; `yonetici_ekler` deseni; RLS politikası eklenmez (admin bağlamı
  zaten geçiyor).
* **Sohbet gövdesi `isler`e YAZILMAZ** (K3): `isler.istek` yalnız kademe ve
  mesaj sayısı; sohbet içeriği kullanıcının "sakla" kararıyla `sohbetler`de
  (v1.13 kararı aynen).
* **Yönetmen önerileri saklanmaz:** cevap gövdesinde gider; kullanıcı tıklarsa
  `isler` satırı bugünkü yoldan doğar.

---

## Test stratejisi — kesişen kararlar

* Beklenen artış **+~265 test** (4.301 → ~4.570), süre **+~40 sn**
  (kapsam bekçileri ve tatbikat Postgres fikstürü). Ölçüm kapanışta.
* Sahte sağlayıcı deseni sohbete: `conftest` `sahte_sohbet` fikstürü
  (kaydedilmiş Anthropic/OpenAI cevapları, içerik reddi ve 401 dalları);
  Anthropic canlı çağrı CI'da YOK.
* Kademe ve kredi bekçileri `test_catalog`ta katalog SIRASINI korur ("ranked
  list = catalog order" kuralı sohbet listesine de).
* Kapsam bekçileri (1. görev) bu fazın kendi tablolarını da bekler: Faz 5 yeni
  tablo eklemiyor, ama otomasyon A1'in `akislar`ı ilk kez bu bekçiyi görür.
* E2E yarışı (PR #85): 5. görev ürün garantisini getirince test sarması
  kalkar — sarma ürün kusurunu gizlemeye devam etmesin.
* `test_docker_kapisi` `ALTYAPI` **+7** değişken toplamda (2: 1; 4: 4; 5: 2).

---

## Sahibin karar noktaları — öneri ve gerekçe

**Durum: bekliyor.** "kabul ediyorum" ile aynen, ya da madde madde. K2 (yeni
sağlayıcı) ve K3 (kredi birimi) sahibin en çok bakması gereken ikisi; K9
ve K12 karar değil karar ölçütü.

| # | konu | öneri | neden | alternatif ve bedeli |
| --- | --- | --- | --- | --- |
| K1 | Yönetmen kademeleri | **Üç kademe** `hizli` / `dengeli` / `derin`, kullanıcı seçer (öntanımlı `dengeli`); `ChatModel.kademe`; yönlendirme katalog sırasıyla **kendi anahtarı > platform anahtarı + plan kapısı**; "Gelişmiş" ile açık model seçimi sürer; kademe modeli gizlemez | Sahibin isteği effort/kalite/düşünme ekseni — üç ad kullanıcıya anlaşılır, sağlayıcı parametresi değil; BYOK önceliği Faz 3 K3 ("kendi parası") ile tutarlı; açık seçim bugünkü kullanıcıyı kırmaz; alt işleyen şeffaflığı KVKK | Beş kademe ya da sürgü: seçici karmaşık, kredi tablosu uzar. Kademe = sağlayıcının `effort` parametresi (tek model): Azure dağıtımında model bile bilinmiyor, Gemini/OpenAI uyumlu uçta ad farklı. Modeli gizlemek: aydınlatma metniyle çelişir |
| K2 | `derin` için Anthropic | **Evet, yalnız sohbet:** `anthropic` sağlayıcısı (`httpx`, SDK yok), Haiku 4.5 `hizli`, Sonnet 5 `dengeli`, Opus 5 `derin` (`thinking: adaptive` yalnız derin); alt işleyen listesi + `HUKUK_SURUMU` | Sahip "Claude gibi çok düşünen" dedi; mevcut beş modelde `derin` yalnız GPT-5.6 Sol; `needs_max_tokens` alanı zaten bunun için yazıldı; ham uç `openai_chat` deseni — bağımlılık yok; fiyatlar (1/5, 2/10, 5/25 USD per MTok, 2026-06-24) sahip doğrular | Yeni sağlayıcı YOK (Faz 4 1b'nin kuralı): `derin` = Sol tek başına, Anthropic gelmez — sahibin isteği karşılanmaz. SDK ile: yeni bağımlılık + pin + Pydantic sürüm çakışması riski (polar-sdk 2.11 istiyor). Görsel tarafına da Anthropic: görsel ucu yok |
| K3 | Sohbet kredisi birimi | **Tur başına SABİT kredi** (`ChatModel.kredi`; öneri `hizli` 1, `dengeli` 3, `derin` 15), rezerv ÖNCE, onay/iade SONRA, `isler` satırı `tur='sohbet'` (gövde yok); BYOK bedava | Jeton sayısı adaptör başına farklı geliyor (Azure dağıtımında model bilinmiyor → fiyat bilinmiyor), rezerv jetonu önceden bilemez; sabit tur 402 ön denetimi ve defter deseniyle birebir; hesap: tipik tur ~3k giriş + ~0,6k çıkış → Haiku ≈ 0,006 USD (1,2 kredi), Sonnet ≈ 0,012 (2,4), Opus + düşünme ≈ 0,08 (16) — çıpa 0,005 USD/kredi; `isler` satırı kota ve admin paneline bedava girer | Jeton başına (kullanım sonrası düzeltme): iade/ek düşüm satırı her turda, negatif bakiye riski, Azure'da imkânsız. Ayrı `sohbet_hareketleri` tablosu: yeni tablo, RLS, silme/dışa aktarma listeleri, kota kör. Kredisiz sürdürmek: platform anahtarıyla sohbet açılamaz (otomasyon planı önkoşulu) |
| K4 | Sohbette plan kapısı | Platform anahtarıyla **`hizli`→`free`, `dengeli`→`temel`, `derin`→`pro`** (`ChatModel.plan`); BYOK her kademeyi açar (1b-B `kapsiyor` kuralı aynen) | Görselde kurulan kapı ve alan zaten var; ücretsiz kullanıcı yönetmeni ucuz modelle kullanır (dönüşüm), `derin`in maliyeti (15 kredi = 200'lük hibenin %7,5'i) ücretsiz planı eritmez; BYOK aşması Faz 3 K3 | Her kademe herkese: ücretsiz kullanıcı Opus'u 13 turda bitirir, kötüye kullanım kanalı. `dengeli` de `pro`ya: ücretsiz kullanıcının yönetmeni yalnız Haiku — deneme zayıf |
| K5 | Kötüye kullanım | **(a) IP hız sınırı** DB'de kayan pencere, HMAC'li IP, `Fly-Client-IP` yalnız `KROMIS_PROXY_GUVEN=1` ile, kayıt/giriş/sıfırlama, 30/saat, 0 = kapalı; **(b) içerik reddi sayacı** `isler.hata_turu`, 10 red / 24 s → 24 saat **üretim kilidi**, KVKK uçları açık, admin kaldırır; **(c) sınıflandırıcı YOK** | Redis yok (Faz 2 K1'in tek-Postgres kararı), `giris_denemeleri` deseni hazır; ham IP saklamak KVKK'da gereksiz veri; sağlayıcılar zaten süzüyor — bize düşen tekrar eden reddi görmek (Polar AUP "moderasyon kuralı" — K11'in uygulaması); ayrı sınıflandırıcı iş başına çağrı + yanlış pozitif + kendi politikası | Bellekte sayaç: çok süreçte tutarsız, yeniden başlayınca sıfır (`_DISA_AKTARIMLAR` kusuru). Prompt kelime listesi: kolay aşılır, dil bağımlı. Kilit yerine hesap kapatma: geri dönüşsüz, destek yükü. Sınıflandırıcı (OpenAI moderation ücretsiz ama yalnız metin/OpenAI; görsel çıktı sınıflandırma ayrı model): Polar incelemesi isterse |
| K6 | Tek göç | **`0009_isletme` 1. görevde**, altı sütun/CHECK, **yeni tablo yok** | Faz 3/4'ün gerekçesi; RLS 32 ve `IS_TABLOLARI` 10 sabit kalır — bekçiler dokunulmaz; sohbet `isler`e yazınca tablo istemez | Görev başına göç: sahibe üç `goc.py` koşusu, ara sürüm uyumsuzlukları |
| K7 | Ölçek ve boşaltma | **Artımlı `tutarlilik`** (son turdan beri hareketi olanlar) + günde bir tam; `silme_turu` tur başına 5 hesap, sayfalı liste; **SIGTERM → boşalt** (yeni iş alma, eldekini bitir); `kill_timeout` 300 aynen, bitmeyen iş **bayat iadesiyle** kapanır; ayrı video işçisi ÖLÇÜMDEN sonra | 5 dk'da tam tarama 1.000+ kullanıcıda dakikalar; artımlı doğruluk kaybetmez (sapma yalnız hareketle doğar), günlük tam tarama emniyet; boşaltma yeni süreç istemez; video işi kayıp değil iade — kullanıcı yeniden dener, dağıtım penceresi belgede | Tur seyrekleştirme: bayat ve silme turları da seyrekleşir. `kill_timeout` yükseltme: Fly üst sınırı 300 sn. Ayrı video işçisi şimdi: ikinci süreç, ikinci `isciler` satırı, `compose`/`fly.toml` — video payı bilinmeden |
| K8 | Yönetmen ajanı v1 | **Öner ve onayla:** yönetmen ≤ 4 yapısal öneri (model, prompt, boyut, kredi tahmini) döner, sunucu doğrular ve fiyatlar, kullanıcı tek tıkla bugünkü uçlardan üretir; sunucu tarafı araç döngüsü YOK | Maliyet ÖNCEDEN görünür (Kromis'in boşluk 3 argümanı), yeni para yolu yok, mevcut kapılar; otomasyon planı "Yönetmen güdümlü ajan"ı aynı gerekçeyle reddetti; öneriler saklanmadığı için şema yok; `yonetmen` adım türü (A1) aynı ayıklayıcıyı kullanır | Otonom araç döngüsü (yönetmen `generate` çağırır): maliyet ve çıktı bilinmez, sohbet isteği dakikalar sürer, iptal/iade karmaşası. Yalnız metin (bugün): sahibin ikinci adımı yok. `otomatik_uret` anahtarı: sonraki adım, bütçe tavanıyla |
| K9 | TR ikinci ayak (iyzico/PayTR, e-Arşiv, taksit) | **Bu fazda YOK; karar ölçütü yazılır:** TR IP'li ödeyen oranı > %30 (Polar `customer` ülke alanı, `siparisler`e ülke sütunu Faz 6) YA DA sahip TR pazarını açar → Faz 6'nın ilk görevi; şema açık (`urunler.para_birimi`, `tur` CHECK) | MoR omurgası yeni; TR yerel ödeme MoR'un yerine değil yanına (master `:189-192`), e-Arşiv ve KDV sahibin mali müşavir turunu ister; ölçmeden kurmak Faz 4'ün öğrettiği "doğrulanmamış varsayım" hatası | Şimdi iyzico: ikinci webhook, TRY fiyat aynası, e-Arşiv entegratörü, 3D Secure akışı — ödeyen TR kullanıcı sayısı bilinmeden. Hiç yazmamak: karar sürekli yeniden açılır |
| K10 | BYOK payı ve admin KVKK ucu | **BYOK: yalnız ÖLÇÜM** (admin metrik `anahtar_kaynagi` 30 gün; karar kapanış notunda); **admin KVKK ucu EVET** (`disa-aktar` + `sil`, günlük satırı) | Faz 4 K8 "Faz 5'te ölçümle" — ölçüm önce; KVKK başvurusu 30 gün yasal süre, giriş yapamayan (parolasını unutan, hesabı kilitli) kullanıcı e-postayla başvurur — admin'in yolu yoksa süre kaçar; iki uç mevcut servisleri çağırır (küçük) | BYOK'a 1 kredi/iş şimdi: gelir küçük, "kendi anahtarımla neden" itirazı (Faz 4 K8 aynen). Admin ucu yok: başvuru elle SQL — izsiz |
| K11 | Yedek tatbikatı | **Araç + sahibin canlı koşusu:** `tools/tatbikat.py` boş Postgres'e geri yükleme, sayım, iki kova SUM, `rls_kontrol`, kova karşılaştırması; CI'da koşmaz; aylık | Yedek geri yüklenebildiği ölçüde yedek (isletme § 5); araç adımları tekrarlanabilir kılar ve süreleri ölçer; üretime karşı çalışma kilidi; Postgres fikstürüyle test edilebilir | Yalnız belge (bugün): hiç koşulmadı, koşulmayacak. CI'da tatbikat: gerçek dump CI'da olamaz (kişisel veri) |
| K12 | Vanilla yeniden bakış (Faz 4 K12) | **Vanilla sürer;** kapanışta ölçüm (JS satırı, betik sayısı, Sentry ön yüz hata oranı, E2E çapa sayısı) ve karar notu; kademe seçici, öneri kartları ve admin sekmesi bugünkü desenle | Faz 5'in ekranları küçük (üç kart, kart listesi, tablo); çerçeve Node derleme + CI + 300 çapa yeniden yazımı; MoR ve Polar portalı büyük ekranları zaten üstlendi | React/Svelte şimdi: kazanç üç küçük ekran. Karar ölçütü yazmamak: her fazda yeniden tartışma |

---

## Üst belgeden ve önceki faz belgelerinden sapmalar — gerekçeli

* **Faz 4 "yeni sağlayıcı yok" (1b) → sohbette Anthropic** (K2): 1b'nin kuralı
  GÖRSEL/VİDEO kataloğu içindi ve gerekçesi adaptör + dış konak + `ALTYAPI`
  bekçisi maliyetiydi; sohbet tarafında sahibin açık isteği ("Claude gibi")
  var, bedel belgede.
* **Otomasyon planı "sohbet kredisinin birimi (jeton mu tur mu) — Kromis Ajanı
  aşamasında" → tur, bu fazda** (K3): Faz 5 kararı verir, A1+ hazır bulur.
* **Otomasyon planı "yönetmen güdümlü ajan reddedildi" → K8 bununla
  ÇELİŞMEZ:** akış tanımı deterministik kalır; K8 sohbet penceresinde öneri.
* **Faz 4 §7 sapma (g) "admin KVKK ucu ihtiyaç doğarsa" → doğdu sayılır**
  (K10): 30 günlük süre ihtiyacı beklemez.
* **Faz 3 devir "`tutarlilik` tur seyrekleşir ya da yalnız son turdan beri" →
  ikincisi** (K7).
* **Faz 4 K12 "yeniden bakış Faz 5 sonu" → ölçüm ve not, çerçeve yok** (K12).
* **Yol haritası kartı "Kullanıcı hesapları ve çoklu çalışma alanları
  (Workspaces)", "Nesne depolama + CDN"** → kuruluş yok (Faz 1 sapması), R2
  Faz 2'de geldi; kart kapanışta tek `[x]` satırı alır, geri kalanı tarihçe.

---

## Faz 5 dışı, ama burada not edilen

* **TR ikinci ayak** → K9 ölçütü; Faz 6.
* **`otomatik_uret`** (yönetmenin tıksız üretimi, bütçe tavanıyla) → K8'in
  sonraki adımı; otomasyon A1'in `yonetmen` adımı aynı ayıklayıcı.
* **Kromis Ajanı** (model gizli, platform kredisiyle) → K1 modeli GİZLEMEZ;
  gizli-model ürünü aydınlatma metnindeki alt işleyen listesiyle birlikte
  düşünülür (otomasyon planı "Kromis Ajanı" bölümü).
* **NSFW/görsel çıktı sınıflandırıcısı** → Polar AUP incelemesi ya da ilk
  gerçek kötüye kullanım vakası isterse.
* **Ayrı video işçisi** → K7, `isler` video payı ölçüldükten sonra.
* **C2PA yeniden imzalama (seçenek c), özgün bayt (b)** → otomasyon A3 /
  herkese açılış; bu faz yalnız (a) görünürlük.
* **Katalog kalemleri** (Faz 4 devri): boyut başına kredi (`credits_edit`),
  Seedance 1080p, GPT Image 2.5 `xhigh`/`max`, FLUX.2 pro → fal (9 → 6),
  BytePlus, Nano Banana Flex/Batch, **video plan basamağı** (Seedance 2.5 /
  FLUX 3 `pro`, Kling V3 Pro `temel` — ÖNERİ, sahip onaylamadı) → sahibin fal
  turu ve kararı; bu fazın kod PR'ı yok, sahip isterse `faz5/katalog-*` ek PR.
* **Polar tarafında doğrulanmayanlar** (Faz 4 devri): ücret tablosu
  (`POLAR_UCRET_ORAN=0.065`, `POLAR_UCRET_SABIT_KURUS=50` VARSAYIM), jeton
  kapsam adları, webhook yeniden deneme, aktif abonelikte yeni plan checkout'u,
  müşteri e-postaları, müşteri kaydının silinme yolu → sahibin sandbox turu;
  sonuç bu belgenin kapanışına.
* **Faz 4'ün on bir canlı adımı** (KURULUM 11 listesi, `HUKUK_ONAYLI`, ay sonu
  `polar_mutabakat`, köprü bayrağı silme, ikinci kova cron'u) aynen sahibin.
* **E2/E3 hızlı araçlar mini fazı**, **Google girişi + `hesap_silme` jeton
  amacı**, **video filigranı**, **"iş bitti" e-postası**, **sağlayıcı
  idempotency anahtarı**, **`saglayici_maliyet_usd` otomatik**, **Sentry
  WARNING breadcrumb** → Faz 3/4 açık kalemleri aynen.
* **Ölçülmeyen:** Anthropic gerçek tur maliyeti (K3'ün sayıları hesap),
  `silme_turu` R2 listeleme süresi büyük galeride (5. görev ölçer), boşaltma
  sırasında kaç iş bayata düşüyor (dağıtım günlüğünden), Fly `Fly-Client-IP`
  başlığının varlığı (sahip doğrular).

---

## Kaynaklar (erişim tarihi 2026-09-24)

Depo: `docs/faz4-odeme-abonelik-kvkk.md` "Faz 4 kapanışı" ve "Faz 4 dışı";
`docs/otomasyon-akislari-plani.md` ("Otomasyondan bağımsız iki bulgu",
"Kromis Ajanı", "Aşamalar"); `docs/isletme.md § 5, § 9`; `services/kota.py`
başlığı; `chat_providers.py`, `catalog.py` `ChatModel`; `static/core.js:38`;
`tests/test_tablolar.py` belge çapaları. Anthropic fiyat ve model listesi:
2026-06-24 tarihli Anthropic model tablosu (`claude-haiku-4-5` 1 / 5,
`claude-sonnet-5` 2 / 10, `claude-opus-5` 5 / 25 USD per MTok; Messages API
`max_tokens` zorunlu, `thinking: {"type": "adaptive"}`) — **sahip
doğrular**; polar.sh ve fal.ai belgeleri bu oturumun ağından erişilemedi (Faz
4 ile aynı).
