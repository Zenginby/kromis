# GPT-Image Studio → Google Flow Arayüz Planı

**Amaç:** GPT-Image Studio'nun (FastAPI + vanilla JS, yerel masaüstü uygulaması)
arayüzünü Google Flow'un tasarım diline taşımak — aynı yetenekler, Flow'un kabuğu,
etkileşim grameri ve renk/tipografi sistemi.

**Sürüm:** v2 — 6 Ağustos 2026 geri bildirimi işlendi.

| Geri bildirim | Karar |
|---|---|
| "KURUM mavisi zorunlu değil, başka temalar da olabilir" | `--accent` **tek değiştirilebilir tema tokenı** oldu; 4 hazır tema, **varsayılan monokrom** (Flow'a birebir). §2.1 |
| "Prompt girilen yer ve Prompt Yönetmeni aynı chat kısmında olsun, (+) yanından geçiş" | Sekmeler kaldırıldı. **Tek composer + (+) yanında Görsel/Yönetmen mod anahtarı.** §4.2 |
| "Sohbet geçmişinde hem konuşmalar hem üretilen görseller tutulsun" | **Birleşik oturum**: döküm konuşma + üretim sonuçlarını aynı akışta tutuyor. Veri modeli ve bir ürün kararı çakışması: §5 |
| "Görsel arama Medya kısmında olsun" | Üst şeritteki arama pill'i **kaldırıldı**, arama Medya görünümüne taşındı; ray dörde indi. §4.1 |
| "Diğer tasarımlar iyi gibi" | Token, tipografi, kabuk, segmented kontrol, eylem hiyerarşisi, medya kartı **onaylandı** — dokunulmuyor. |

**Sürüm v3 — açık soruların hepsi kapandı, ekranlar üretildi.**

| Soru | Cevap | Nerede uygulandı |
|---|---|---|
| D1 · otomatik kayıt | **Evet, kaydedilsin** | §5, oturum listesi altındaki anahtar + Azure panelindeki anahtar |
| Oturum listesi | **Geri oku yerine hamburger düğmesi**, açılan liste | §4.1, `studio-session.html` sol drawer |
| Görsel modunda "Yönetmen'e sor" | **Olsun** | §4.2, composer'da metin yazınca çıkan tek metin düğmesi |
| En küçük pencere | Koddan okundu: `desktop.py` → `WINDOW_SIZE (1440, 900)`, **`MIN_WINDOW_SIZE (1024, 700)`** | §2.2, `flow.css` duyarlılık kuralları |
| Taşıma kapsamı | **Ayrı dalda** | §9, `feat/flow-ui` |

**Sürüm v4 — 7 Ağustos 2026: taşıma başladıktan sonraki gerçeklik düzeltmesi.**

Bu tur yeni tasarım kararı getirmiyor; **sözleşmenin koda uymayan iddialarını**
düzeltiyor. PR 1 (`a1478d4`) merge edildikten sonra beş referans ekran uygulamaya
karşı tek tek denetlendi ve 18 açık madde bulundu. Denetimin kendisi ve adım
ataması uygulama planında: `docs/superpowers/plans/2026-08-06-flow-arayuz-devri.md`
**§0.2** (denetim tabloları) ve **§0.3** (Adım 8/9/10).

| # | Düzeltilen iddia | Gerçek |
|---|---|---|
| V1 | "v1.17.0" (§ başlık ve §6; §2.2 yalnızca "sürüm pill'i" diyor, literal yok) | `25713f8`'de `APP_VERSION` **1.16.0**'dı; sürüm hiç 1.17.0 olmadı. 7 Ağustos'ta **2.0.0**'a çıkarıldı (arayüz baştan değişti + D1 bir ürün kararını tersine çeviriyor). Referans ekranlardaki `v1.17.0` **maket metnidir**, sözleşme değil. |
| V2 | "Yedekler artık sol rayda değil" (§4.1) | Yedek arayüzü **hiç var olmamıştı** — `25713f8`'in `index.html` ve `settings.js`'i denetlendi, raydan kaldırılan bir şey yok. `backup.py` yalnızca açılışta otomatik çalışıyor (`app.py:92`); kullanıcıya dönük ne panel ne rota var. |
| V3 | Ayarlar panelinin **Yedekler** yarısı (§4.1, §6, §7/5, §11) | **Ertelendi** (7 Ağustos kullanıcı kararı). Yazılmamış kapsam; arka uç rotası da gerektiriyor. Kabul ölçütünden düşürüldü, plan §0.2'de gerekçesiyle kayıtlı. |
| V4 | §1'in "arayüzde henüz hiçbir değişiklik yok" satırı | Bayat: PR 1 merge edildi. §1 artık **taşıma öncesi ölçüm** olarak etiketli. |
| V5 | §12 "Sonraki adım: ekranları gez, onay ver, taşımaya geçiyorum" | Taşıma başladı ve PR 1 bitti. §12 güncel duruma çevrildi. |

> **Sözleşme ↔ uygulama farkı bulunduğunda kural:** tasarım kararı haklıysa kod
> düzeltilir; sözleşme **kod hakkında yanlış bir şey söylüyorsa** (V1, V2, V4)
> sözleşme düzeltilir. Maket metinleri (ekranlardaki örnek prompt, tarih, sürüm
> pill'i) hiçbir zaman sözleşme değildir.

---

## 1. Taşıma öncesi ölçüm — `25713f8` (tarihsel taban, 6 Ağustos)

> **Bu tablo dondurulmuş bir ölçümdür, bugünün durumu DEĞİL.** PR 1 (`a1478d4`)
> merge edildi: `index.html` ve `style.css` yeniden yazıldı, `flow-tokens.css`
> eklendi, `test_id_contract.py` geldi (`pytest` tabanı 994 → 1000). Güncel durum
> için uygulama planının §0.1'ine bak. Tablo, "neyi korumak zorundayız" sorusunun
> cevabı olduğu için silinmiyor — 152 id kısıtının kaynağı burada.

| Ne | Durum (`25713f8`) |
|---|---|
| Depo | `~/Documents/Projects/Claude Code Projects/gpt-image-studio` — `git status` temiz, HEAD `25713f8`, `APP_VERSION` **1.16.0**. O tarihte arayüzde henüz hiçbir değişiklik yoktu. |
| Ön yüz | `static/index.html` (33 KB, **152 `id`**), `static/style.css` (55 KB, `:root`'ta 17 token), `core.js` `folders.js` `palette.js` `assets.js` `chat.js` `settings.js` `viewer.js` |
| Test | `tests/test_index.py` içinde **82 test**, servis edilen HTML'de **27 element id'sini** doğrudan doğruluyor |
| Veri | `history.json` (görseller, `storage.py`) ve `chats.json` (sohbetler, `chat_store.py`) — **bugün birbirinden tamamen bağımsız iki depo** |

> ⚠️ **En kritik mühendislik kısıtı:** 152 id hem JS bağlanma noktası hem test sözleşmesi.
> Yeniden tasarım = **kabuğu ve deriyi değiştir, id'leri koru.** `assets.js` id'lere `$()`
> ile doğrudan bağlanıyor — bir id kaybolursa script yüklenirken patlar ve ondan sonraki
> tüm dinleyiciler sessizce ölür.

---

## 2. Flow tasarım dili — kaynaktan ölçülen değerler

Değerler `google flow tasarımı/` klasöründeki 4 ekran görüntüsünden **piksel örneklemesiyle**
alındı (medyan, 8×8 kutu). Tahmin yok.

### 2.1 Renk ve tema

| Token | Değer | Nerede |
|---|---|---|
| `--bg` | `#000000` | uygulama tuvali, üst şerit |
| `--surface` | `#141415` | composer, sağ panel, modal, kart |
| `--surface-2` | `#1e1e1f` | input, select, boş segmented kutucuk, mesaj balonu |
| `--surface-3` | `#2a2a2b` | arama alanı, sıralama düğmesi, yükseltilmiş kontrol |
| `--selected` | `#353637` | sol raydaki aktif nav öğesi, aktif klasör çipi |
| `--selected-strong` | `#4d4e50` | segmented aktif kutucuk |
| `--fg` | `#e8eaed` | ana metin |
| `--muted` | `#9aa0a6` | ikincil metin, pasif nav etiketi (ölçüm: `#878888`) |
| `--placeholder` | `#8a8f94` | Flow'un ölçülen `#5f6368`'i 4.5:1'i geçmediği için yükseltildi |
| `--border` | `rgba(255,255,255,0.10)` | 1px hairline |
| `--primary` / `--on-primary` | `#ffffff` / `#101011` | tek birincil eylem rengi + aktif mod pill'i |

**Tema = tek token.** `--accent` yalnızca **durum** anlatır: üretim ilerlemesi, odak halkası,
seçili görsel çerçevesi, döküm sonuç satırının ikonu. Yüzeyler, metin ve birincil eylem (beyaz)
her temada aynı — bu yüzden hiçbir tema kontrastı bozamıyor.

| Tema | `--accent` | Not |
|---|---|---|
| **Monokrom (varsayılan)** | `#e8eaed` | Flow'a birebir; renk hiç yok |
| KURUM mavisi | `oklch(72% 0.11 245)` | logo varlıklarından ölçülen `#085888`'in koyu zeminde okunabilir türevi |
| Amber | `oklch(76% 0.14 68)` | motto turuncusu `#e08038` ailesinden |
| Menekşe | `oklch(72% 0.13 300)` | nötr üçüncü seçenek |

Tema, Ayarlar → Görünüm'de seçilir ve `settings.py`'nin yazdığı yerel ayara yazılır
(yeni bir alan; API anahtarıyla aynı dosya, aynı `0600` izni).

### 2.2 Geometri ve ölçü

- Pencere: açılış **1440×900**, en küçük **1024×700** (`desktop.py`). Tüm ekranlar
  1024×700'de taşmadan çalışır; **1200px** altında ray otomatik daralır, **760px**
  yükseklik altında üst şerit 60px'e iner.
- Sol ray: **228px** açık / **72px** daralt (`Daralt` en altta).
- Üst şerit: **72px** — sol: geri + oturum adı + kebab · sağ: yeni oturum, ayarlar, sürüm
  pill'i. **Arama yok** (§4.1).
- Yüzen composer: max **620px**, ortalanmış, alttan **24px**, `--surface`, radius **24px**.
- Sağ slide-over: **320px**, alta sabit beyaz birincil düğme.
- Modal medya seçici: **776 × 570**, kendi iç navigasyonu + arama + sıralama.
- Yarıçap: panel/modal/composer 24 · rail öğesi 12 · segmented kutucuk 10 · medya kartı 12 ·
  mesaj balonu 20 (kaynak köşesi 6) · pill 999.
- Boşluk ritmi: 8 / 12 / 16 / 24 / 32. Ray öğeleri arası 4px, gruplar arası 16px + hairline.

### 2.3 Hareket

- Süre **200ms**, easing `cubic-bezier(0.2, 0, 0, 1)`.
- Slide-over `translateX`, modal `scale(0.98) → 1` + opacity, kart eylemleri
  `opacity` + `translateY(4px)`. Sadece compositor dostu özellikler.
- `prefers-reduced-motion`: yalnızca opacity. Bounce/elastic yok.

### 2.4 Bileşen grameri

1. Her ekranda **tek** kalıcı sol ray; sekme yok.
2. Prompt her zaman **yüzen alt composer**'da; panel içine gömülmez.
3. Ayar = sağdan slide-over, alta sabit beyaz "Kaydet".
4. Seçim kontrolleri **segmented kutucuk**, açılır menü değil.
5. Boş durum = küçük tek glif + tek satır `--muted` metin.
6. İkonlar monoline, 1.6–1.8px stroke, `currentColor`, 20–24px. Emoji ikon yok.
7. Etiketler cümle düzeni; ALL-CAPS başlık yok.

---

## 3. Tipografi (onaylandı)

| Rol | Aile | Not |
|---|---|---|
| Display / başlık | **DM Sans** (bundle `woff2`) → `system-ui` | Google Sans'a en yakın karakter; yasaklı display listesine girmiyor |
| Gövde / UI | `-apple-system, "SF Pro Text", system-ui` | Yerel uygulama, ağ bağımlılığı yok |
| Mono | `ui-monospace, "SF Mono", "JetBrains Mono"` | Prompt bloğu, teknik JSON, boyut damgası, hex girişi |

Ölçek: 28 · 20 · 15 · 14 · 13 · 12. Satır yükseklikleri ≥20px için 1.3, gövde 1.5, ≤13px 1.5.
Harf aralığı: ≥28px `-0.015em` · 14px `0` · 12–13px `0.01em` · mono wordmark `0.08em`.
Mono **yalnızca** wordmark ve teknik bloklarda; bugünkü ALL-CAPS mono başlıklar
("SİPARİŞ", "TEMA RENGİ VE PALETLER") 13px cümle-düzeni gri etikete dönüşüyor.

---

## 4. Bilgi mimarisi (geri bildirimle değişen kısım)

### 4.1 Sol ray dörde indi

| Öğe | İçerik |
|---|---|
| **Stüdyo** | Aktif oturum: döküm + yüzen composer. Uygulamanın varsayılan ekranı. |
| **Medya** | Üretilen tüm görseller. **Arama burada** (prompt, klasör, boyut) + sıralama + **ızgara boyutu (S/M/L)** + çoklu seçim + sürükle-bırak içe aktarma. Bugünkü "KONTAK BASKI" film şeridi ve "KLASÖRLER" bölümü bu görünümde birleşiyor. |

**Klasörler gerçek gezinme, filtre değil** (bugünkü uygulamanın modeli):
kökte üstte **klasör kartları** (kapak görseli + ad + kartlardan hesaplanan görsel sayısı),
altında **"Klasörsüz görseller"** ızgarası. Bir klasöre tıklayınca içine giriliyor: başlık
şeridinde geri düğmesi, klasör adı, sayı ve klasör eylemleri (`folder-delete` id'si
bugünküyle aynı — silme kartta değil, klasör içindeki şeritte). Arama ise klasör
sınırından bağımsız: sorgu yazıldığı anda "Arama sonuçları — tüm klasörler" görünümüne
geçiyor, her kart hangi klasörde olduğunu künyesinde yazıyor. Kutucuk oranı arşiv
ızgarasında tek tip (1:1 + `cover`); gerçek boyut kart künyesinde.
| **Kütüphane** | Bindirme varlıkları: logolar, mottolar, bannerlar, yüklemeler. |
| **Araçlar** | Yalnızca iki şey: **Görünüm** (arayüz teması) ve **Tema rengi ve paletler** (palet üretimi + damlalık). Tasarım kararları burada. |

Alt grup: yalnızca **Daralt**. Üst şeritteki merkezi arama pill'i **kaldırıldı** —
aranacak tek şey medya, o yüzden arama medyanın yanında duruyor.

**Uygulama ayarları dişlide.** Üst şeridin sağındaki dişli düğmesi tek bir "Ayarlar"
slide-over'ı açıyor: **Azure · gpt-image-2** (endpoint, API anahtarı, Yönetmen dağıtım adı).
Ayrım kasıtlı: Araçlar = tasarım kararları (tema, palet), dişli = makine/kurulum
ayarları. Diğer ekranlardaki dişli `settings-panels.html#ayarlar` ile aynı paneli açıyor.

> **Yedekler yarısı ertelendi — 7 Ağustos (bkz. v4/V2, V3).** Panelin ikinci bölümü
> (otomatik yedek · eski biçim göçü · şimdi yedek al / klasörü aç) **şimdilik
> kapsam dışı.** Referans ekran `settings-panels.html` onu hâlâ gösteriyor; o
> maket, taahhüt değil.
>
> Bu paragraf daha önce "Yedekler artık sol rayda değil" diyordu — **yanlıştı.**
> `25713f8` denetlendi: yedek arayüzü hiç var olmamıştı, dolayısıyla raydan
> kaldırılmadı. Bu yazılmamış kapsamdır, gerileme değil. `backup.py` bugün
> yalnızca açılışta `backup_manifests_if_version_changed` ile çalışıyor
> (`app.py:92`); ne kullanıcı arayüzü ne API rotası var, yani panel işi arka uç
> da gerektiriyor.

**Oturum listesi.** Üst şeridin en solunda geri oku değil **hamburger** düğmesi var; soldan
320px'lik bir liste açılıyor (scrim + `Esc` ile kapanır). Her satır: kapak görseli, başlık,
tarih, görsel sayısı ve son mod etiketi. Listenin altında "oturumları otomatik kaydet"
anahtarı ve "tüm oturumları sil". Bu düğme bugünkü `chat-sidebar-toggle` id'sine bağlanacak.

### 4.2 Tek composer, iki mod

(+) işaretinin **yanında** iki durumlu pill (Flow'un beyaz "Ajan" pill'inin bulunduğu yer);
aktif taraf beyaz, pasif taraf `--muted`:

| Mod | Composer davranışı | Sağ taraf |
|---|---|---|
| **Görsel** | Prompt doğrudan üretime gider (bugünkü `POST /api/generate` akışı) | `1:1 · ORTA · x1` mono çipi → Üretim ayarları slide-over'ını açar |
| **Yönetmen** | Metin sohbete gider (bugünkü `POST /api/chat`) | Yönetmen talimatları ikonu |

- Klavye: `⌘/Ctrl + Enter` gönderir (bugünkü davranış korunur), `⌘/Ctrl + J` mod değiştirir.
- Mod, oturum başına hatırlanır; oturum listesinde son mod etiketi görünür.
- Yönetmen'in ürettiği prompt bloğunda **"Görsel modunda üret"** düğmesi var: modu
  değiştirip prompt'u composer'a basar. Eski etiketin ("Forma aktar") vaat ettiği
  diğer sekmeye gidiş geliş ortadan kalkıyor — **7 Ağustos'ta teslim edildi**
  (Adım 8, plan §0.8); sekmelerin kaldırılma gerekçesi bu maddeydi.
- Ters yön de var: **Görsel modunda** prompt kutusuna bir şey yazdığın anda sağda
  **"Yönetmen'e sor"** metin düğmesi çıkar — yazdığın ham metni yönetmene devreder.
  Kutu boşken görünmez (o yüzden ekranda ikinci bir dolu düğme oluşmaz).
  **7 Ağustos'ta teslim edildi**: metni TAŞIYOR (kopyalamıyor) ve yönetmenin
  yazılmış ama gönderilmemiş mesajının üstüne yazmıyor — altına ekliyor (K21).
- (+) menüsü her iki modda aynı: Referans görsel · Ek görsel · Medya'dan seç · Dosyadan yükle.

---

## 5. Birleşik oturum veri modeli — **arka ucu teslim edildi (7 Ağustos)**

> Aşağıdaki üç ekleme **kodda**: `storage.save`'de koşullu `session_id`,
> `models.ChatMessage`'ta `result` rolü, `chat_store._SUMMARY_FIELDS`'te
> `cover_image_id`. Göç gerçekten gerekmedi — geliştiricinin mevcut 5 oturumuna
> ve `history.json` kayıtlarına tek bir alan yazılmadı. Uygulama sırası ve
> ölçülen kanıtlar planın **§0.4**'ünde.
>
> Sözleşmeyi netleştiren üç karar aynı turda verildi:
> - **`params` kapalı bir şema:** `{kind, size, quality}`. Adet ayrı taşınmıyor,
>   `image_ids`'in uzunluğundan geliyor ("x2") — silinmiş bir görsel bile o sayıyı
>   dürüst tutuyor. `size`/`quality` Azure allowlist'ine karşı **doğrulanmıyor**:
>   allowlist daralırsa o boyutla üretilmiş eski oturumlar bir daha
>   kaydedilemez olurdu.
> - **`cover_image_id` istemciden gelmiyor, dökümden türetiliyor** — ilk sonuç
>   kaydının ilk görseli. Son sonuçtan alınsaydı liste küçük resmi her üretimde
>   değişirdi; istemciden alınsaydı dökümde bulunmayan bir görseli kapak yapabilirdi.
> - **Sonuç kayıtlarının kendi sayı payı var** (24 konuşma + 24 sonuç): aynı kotayı
>   paylaşsalardı üretim yapan oturum ~8 turda dolardı.
>
> **Ekran payı da teslim edildi (7 Ağustos, Adım 7a — plan §0.6).** Döküm
> `result` kayıtlarını künyeli kartlar olarak çiziyor, silinmiş görsel
> **"görsel silindi"** yer tutucusuna dönüyor, üretim açık oturumun dökümüne
> katılıyor. İki nokta bilinçli olarak sonraki turlarda:
> - Sonuç kartında **"Düzenle" / "+ Ek" hâlâ yok** (§0.6/K14): ikisi de tam bir
>   geçmiş kaydı istiyor, döküm yalnız id taşıyor. Adım 8'de ölçüldü ki "+ Ek"
>   bugün yapılabilir (yalnız id ister), "Düzenle" ise bir tercih gerektiriyor —
>   prompt'u dökümden yeniden kurmak mı, tek kayıt döndüren rotayı beklemek mi
>   (plan §0.8'in "bilerek yapılmayanlar" başlığı). Karar bekliyor.
> - **Görsel modu kendi oturumunu BAŞLATIYOR** (7 Ağustos, Adım 8 — plan
>   §0.8/K19): prompt yapısı gereği bir döküm turu, o yüzden koşulsuz basılıyor
>   ve oturum üretimden SONRA yazılıyor. Uydurma `session_id` yok; bedeli ilk
>   partide ters bağın eksik kalması (K20), ileri bağ tam.


Bugün iki ayrı depo var ve aralarında **hiçbir bağ yok**:

```
history.json  → {id, filename, prompt, size, quality, created_at,
                 parent_id, folder_id, palette, prompt_sent, imported?}
chats.json    → {id, title, messages:[{role, content}], created_at, updated_at}
```

Birleşik döküm için deponun kendi geleneğiyle (koşullu yazım + `.get()` ile okuma →
**göç gerekmez**) üç ekleme yeter:

1. **Görsel kaydına koşullu `session_id`.** Yalnızca bir oturum içinde üretildiyse yazılır —
   `imported: True` ile birebir aynı desen, böylece bugünkü kayıtlar bayt bayt aynı kalır
   (galeri ve `test_legacy_formats.py` buna bağlı). Eski kayıtlar Medya'da görünür,
   hiçbir oturuma bağlı olmaz.
2. **Dökümde üçüncü rol.** `{"role": "result", "image_ids": [...], "params": {...}}`.
   **Kritik:** `chat_client.py` Azure'a yalnızca `user`/`assistant` göndermeli; `result`
   kayıtları istemden **filtrelenir** ve `models.py`'deki `MAX_CHAT_TOTAL_CHARS`
   bütçesine **sayılmaz** (modele gitmiyorlar).
3. **Oturum özetine `cover_image_id`.** `chat_store._SUMMARY_FIELDS` bilerek `messages`'ı
   dışarıda bırakıyor (trafik); liste küçük resmi için tek bir id alanı ekleniyor.

**Dayanıklılık:** `storage.delete_many` bir görseli silince dökümde sarkan `image_id`
kalır. Döküm bu durumda çökmez, "görsel silindi" yer tutucusu gösterir — kabul ölçütü.

### ⚠️ Karar D1 — bu, bilinçli bir ürün kararını tersine çeviriyor

`chat_store.py`'nin başındaki not açık: **`POST /api/chat` bilerek diske hiçbir şey
yazmıyor**; yazan tek yol kullanıcının kendi başlattığı `/api/chats`. Gerekçe:
"modelden dönen her yanıtı sessizce diske almak ile kullanıcının 'bu sohbeti sakla'
demesi aynı şey değil."

"Sohbet geçmişinde hem konuşmalar hem üretilen görseller tutulsun" isteği bu kararı
kaldırmayı gerektiriyor — geçmiş ancak otomatik yazılırsa dolu olur.

**Karar: evet, otomatik kaydedilsin** (6 Ağu onayı). Üç güvenceyle —
(a) her şey yerelde kalır, bugünkü `output_dir` ve izinler değişmez;
(b) oturum menüsünde tek tıkla **sil** ve **tümünü sil**;
(c) Ayarlar'da "oturumları otomatik kaydet" anahtarı, kapatınca bugünkü davranışa döner.
Görseller zaten diske yazılıyor; yeni olan tek şey sohbet metni.

> **Arka ucu teslim edildi (7 Ağustos).** Üç güvence de mekanik: `prefs.py`
> deposu + `GET/POST /api/prefs` (anahtar), `DELETE /api/chats` (tümünü sil).
> Uygulama sırası ve kanıtlar planın **§0.5**'inde. Sözleşmeyi netleştiren üç
> nokta:
> - **Anahtar kimlik dosyasında değil**, kullanıcının veri dizinindeki
>   `prefs.json`'da. Ayarlar panelinde görünüyor ama kimlik formundan AYRI bir uç
>   kullanıyor: bir anahtarı çevirmek Azure kimliğini yeniden yazmamalı ve Azure
>   hiç yapılandırılmamışken de anahtar çevrilebilmeli.
> - **Anahtar kapalıyken sunucu gerçekten yazmıyor** (409), yalnız istemciye rica
>   etmiyor. Ayrımı taşıyan işaret: otomatik kaydın verecek bir ADI yok. Kullanıcının
>   kendi kaydettiği/adlandırdığı oturum her koşulda yazılıyor — "kapatınca bugünkü
>   davranış" tam olarak bu. Silme anahtardan bağımsız.
> - **Otomatik kaydedilen oturumun adı türetiliyor** (ilk kullanıcı turunun ilk
>   satırı; çip turunda ekranda görünen etiket). Kullanıcı kebaptan yeniden
>   adlandırabiliyor. "Adsız oturum olmaz" kuralı korundu.
>
> `POST /api/chat` **hâlâ hiçbir şey yazmıyor**: oturumu yazan taraf istemci.
> Sebep birleşik dökümün kendisi — Görsel modunda üretilen sonuç kayıtları
> tamamlama rotasına hiç uğramıyor, kalıcılık oraya konsa sohbetsiz bir oturum
> hiç kaydedilemezdi.

---

## 6. Yapısal eşleme (bugünkü → Flow)

| Bugün | Flow karşılığı |
|---|---|
| Wordmark + "Azure gpt-image-2 · yerel" + sağ üstte dişli | Üst şerit: oturum adı + kebab · sağda yeni oturum, ayarlar, sürüm pill'i. **Wordmark 7 Ağustos'ta raydan kaldırıldı**; kimlik oturum adına ve `<title>`a devredildi. Pill'de sürüm literali yok — tek kaynak `version.py` (bugün **2.0.0**). |
| `Görsel` / `Prompt Yönetmeni` sekmeleri | **Kalkıyor.** Sol ray + composer'daki mod anahtarı (§4.2) |
| SİPARİŞ paneli (prompt + boyut/kalite/adet + referans + renk + logo + CTA) | Prompt → composer; boyut/kalite/adet → sağ slide-over'da segmented; referans/ek görsel → (+) menüsü ve composer çipleri; tema rengi → Araçlar + slide-over; logo/motto → Kütüphane + önizleme paneli |
| Ortadaki büyük önizleme + `X` | Döküm içindeki sonuç kartına tıklayınca tam-kaplama önizleme (`viewer.js` korunur) |
| Alt çekmece "KONTAK BASKI · 17 KARE" + KLASÖRLER + film şeridi | **Medya** görünümü: arama + sıralama + ızgara boyutu + klasör kartları (kök) / klasör içi ızgara |
| Her küçük resmin altında sürekli görünen `İndir` `+Ek` | Kart üzerinde hover/focus'ta açılan eylem satırı + seçim onay kutusu (`select-bar` akışı korunur) |
| Modal'lar (Tema rengi, Kütüphane, Azure ayarları) | Tema rengi → Araçlar'dan sağ slide-over; Azure → üst şeritteki **dişli** düğmesinden "Ayarlar" slide-over'ı (Yedekler yarısı ertelendi, §4.1); Kütüphane → iç navigasyonlu medya seçici modalı |
| Sohbet: yan liste + döküm + ayrı composer | Aynı kabuk: oturum listesi (üst şeritteki geri oku) + tek döküm + tek composer. YÖNETMEN kartları `--surface-2` balon, seçenekler Flow çipi, PROMPT bloğu mono kalır |

---

## 7. Ekran dosyaları — **teslim edildi**

Hepsi ortak `flow.css` tasarım sistemini kullanıyor (tokenlar tek yerde, ekranlar ince).
`index.html` genel bakış / launcher.

1. `studio-session.html` — **birleşik oturum**: ray + üst şerit + döküm (kullanıcı mesajı,
   yönetmen kartı, seçenek çipleri, prompt bloğu, inline üretim sonucu) + mod anahtarlı
   composer + "Üretim ayarları" slide-over. Durumlar: boş oturum · Görsel modu · Yönetmen
   modu · üretim sürüyor · referans eklenmiş · ray daraltılmış.
2. `media-browser.html` — **Medya**: arama, sıralama, ızgara boyutu, klasör kartları
   ve klasör içi görünüm, ızgara, çoklu seçim
   şeridi, sürükle-bırak içe aktarma, "Referans olarak kullan" akışı, boş durum.
3. `studio-preview.html` — tam-kaplama önizleme + logo/motto/banner bindirme paneli
   (offset kaydırıcıları dahil) + düzenleme akışı.
4. `library-assets.html` — Kütüphane: logolar/mottolar/bannerlar/yüklemeler + yükleme akışı.
5. `settings-panels.html` — Araçlar: Görünüm (tema) · Tema rengi/paletler; dişliden açılan
   Ayarlar paneli (Azure; ekranda görünen **Yedekler** bölümü ertelendi — §4.1)
   (HSV alanı, ton kaydırıcısı, hex, damlalık, harmoni kartları, kayıtlı paletler).
6. `index.html` — genel bakış + token levhası (şu an yön onay levhası; mod anahtarı ve
   tema seçici çalışıyor).

**Gerçek içerik, yer tutucu değil.** Görsel üretimi bu projede yapılandırılmadığı için
(Fal API anahtarı yok) tel kafes yerine uygulamanın **kendi çıktıları** kullanıldı:
`output/`'tan 8 üretim ve `assets/`'ten 7 gerçek logo/motto/banner `assets/samples/` ve
`assets/brand/` altına küçültülerek kopyalandı. Prompt metinleri de `history.json`'daki
gerçek kayıtlardan. Uydurma metrik, lorem, emoji ikon yok.

**Çalışan etkileşimler** (statik ekran görüntüsü değil): mod anahtarı + `⌘J`, otomatik
büyüyen prompt kutusu, "Yönetmen'e sor" görünürlüğü, (+) menüsü, referans çipi silme,
oturum drawer'ı, üretim ayarları paneli ve çipin canlı güncellenmesi, Medya'da gerçek
arama + klasör filtresi + çoklu seçim + sıralama, bindirme panelinde canlı konum/ölçek/
kaydırma, Kütüphane'de tür filtresi + önizleme, renk seçicide HSV alanı (fare ve klavye)
ve altı paletin canlı üretimi, tema seçimi (`localStorage` ile tüm ekranlarda geçerli).

---

## 8. Etkileşim durumları ve kontrast kapıları

| Durum | Kural |
|---|---|
| hover (yüzey) | L +0.06 → `#1e1e1f` → `#2a2a2b`. Metin rengi **değişmez** |
| hover (beyaz birincil / aktif mod) | `#ffffff` → `#e8eaed`, metin `#101011` sabit |
| selected (ray, klasör çipi) | arka `#353637`, metin `#e8eaed` (≈9:1) |
| selected (segmented, mod) | segmented `#4d4e50` + `#fff`; mod beyaz + `#101011` |
| focus-visible | 2px `--accent` halka + 2px offset; her odaklanabilir öğede |
| disabled | tek kontrast düşürme izni olan durum |
| drag-over | tuvalde/ızgarada 2px kesikli `--accent` çerçeve + `#141415` overlay |
| üretim sürüyor | composer'da `--accent` ilerleme çizgisi + gönder düğmesi disabled |

Kapılar: gövde ≥4.5:1 · ≥18px ve ikon ≥3:1 · kontrol komşu yüzeye karşı ≥3:1.
Hedef boyutu ≥40px (masaüstü penceresi).

---

## 9. Gerçek depoya taşıma — **`feat/flow-ui` dalında**

Ana dal (`main`) bu iş bitene kadar bugünkü arayüzle kalır; taşıma ayrı dalda yapılıp
PR olarak açılacak (`git switch -c feat/flow-ui`).

> **"Altı adım altı commit" tahmini tutmadı (7 Ağustos).** Aşağıdaki altı madde
> *işin türlerini* doğru sayıyor ama sırayı/sayıyı değil: gerçekleşen bölünme
> **PR 1 = Adım 0–4** (merge edildi, `a1478d4`), **PR 2 = Adım 5–7**, artı
> denetimden doğan **Adım 8–10**. Kanonik sıra uygulama planında
> (`…/2026-08-06-flow-arayuz-devri.md` §0.1 tablosu + §0.3); bu liste taşımanın
> *kapsamını* anlatan tasarım metni olarak kalıyor.

1. **Token katmanı.** `static/style.css` `:root` → Flow paleti; `--panel`/`--panel-2` gibi
   eski adlar korunup yeni değerlere bağlanır (55 KB CSS yeniden yazılmadan tüm ekran
   Flow rengine döner). `--chat-user`/`--chat-bot` nötr yüzeylere yeniden tanımlanır.
2. **Kabuk.** `static/index.html`: ray + üst şerit + döküm + yüzen composer iskeleti.
   **152 id korunur**, yalnızca yer ve sarmalayıcı değişir. Sekme düğmeleri görünmez
   olur ama id'leri (JS/test bağı) yerinde kalır → mod anahtarı bunlara bağlanır.
3. **Bileşen CSS'i.** rail · topbar · composer+mode · thread · result · media-card ·
   media-head · grid-size · slide-over · segmented · chip · modal-picker · empty-state ·
   **viewer**.
   **Büyüteç yeniden yazılmıyor, yeniden giydiriliyor.** `viewer.js` bugün imleç-sabitli
   zoom, rubberband pan sınırı, ctrl+wheel pinch, 60px ok adımı ve küçük resimden
   büyüyerek açılma geçişini zaten yapıyor; bunlar korunuyor. Yalnızca `.viewer*` CSS'i
   Flow yüzeylerine geçiyor ve dokuz id (`viewer`, `viewer-stage`, `viewer-img`,
   `viewer-zoom-out`, `viewer-zoom-pct`, `viewer-zoom-in`, `viewer-fit`,
   `viewer-download`, `viewer-close`) aynen kalıyor — ekran dosyalarındaki kabuk bu
   dokuz id'yi birebir kullanıyor. Alt şerit dizilimi de bugünküyle aynı:
   `− %100 + Sığdır İndir ×`.
4. **Birleşik oturum (arka uç).** §5'teki üç alan + `result` rolünün istemden
   filtrelenmesi + D1 anahtarı. Bu adım **kozmetik değil**, kendi testleriyle gelir.
5. **JS dokunuş noktaları.** `core.js` (composer + döküm render), `chat.js` (mod anahtarı,
   result kartı), `folders.js` (Medya görünümü + arama), `palette.js`, `assets.js`,
   `settings.js` (tema + otomatik kayıt anahtarı), `viewer.js`.
6. **Doğrulama.** `pytest` tamamen yeşil + id farkı boş + uygulama açılıp
   1280/1440/1680/1920 genişliğinde ekran görüntüsü + klavye turu.

**Riskler**

- **R1** id kaybı → script yüklenirken patlar, sonraki dinleyiciler ölür. Önlem: yapı
  değişmeden önce `grep -oE 'id="[a-z0-9-]+"'` çıktısı alınır, sonra fark alınır (boş olmalı).
- **R2** Testler bazı şeyleri **negatif** doğruluyor (`type="color"`, `data-akind="palettes"`,
  `id="edit-panel"` olmamalı); yeni işaretlemede kazara geri gelmemeli.
- **R3** 55 KB CSS'te ölü kural birikmesi → 3. adımın sonunda temizlik turu.
- **R4** `result` rolü Azure istemine sızarsa sohbet bozulur veya token bütçesi şişer →
  filtre için birim testi zorunlu.
- **R5** Otomatik kayıt (D1) `MAX_CHAT_TOTAL_CHARS` sınırına daha hızlı çarpar; sonuç
  kayıtları bütçeye sayılmadığı için bu sadece uzun konuşmalarda olur, ama sınıra
  yaklaşınca kullanıcıya görünür uyarı gerekir.

---

## 10. Kapanan kararlar ve taşımada kalan sorular

Beş açık soru **kapandı** (üstteki v3 tablosu). Taşıma sırasında karar gerektirecek,
tasarımı değiştirmeyen üç teknik nokta kaldı:

1. **Sekme id'leri.** `tab-image` / `tab-chat` testlerde ve JS'te var. Mod anahtarı bu
   id'leri **devralacak** (görünmez sekme kabuğu yerine doğrudan yeni düğmelere taşınacak)
   mı, yoksa id'ler gizli bir sarmalayıcıda mı tutulacak? Testler yalnızca varlığını
   kontrol ediyor, ikisi de geçer — sadeliği için birincisi öneriliyor.
2. **Oturum ↔ sohbet id eşleşmesi.** Bugün `chats.json` kaydı `id` üretiyor; `session_id`
   olarak aynı id kullanılacak (yeni bir kimlik uzayı açılmayacak).
3. **Geçmiş sayfalama.** 23 kayıt bugün sorunsuz; birleşik döküm büyüdükçe Medya
   ızgarası sanal listeye geçmeli mi? Şimdilik gerek yok, eşiği 500 görselde ölçelim.

---

## 11. Kabul ölçütleri

- [ ] Sekme yok: tek ray + tek composer; mod anahtarı (+) işaretinin yanında ve klavyeyle
      erişilebilir.
- [x] Döküm konuşmayı ve üretilen görselleri **aynı akışta** gösteriyor.
      **7 Ağustos'ta teslim** (Adım 7a, plan §0.6): `result` kartı künyesiyle
      çiziliyor (`Üretildi · 1024² · Orta · x2`), kare büyüteci açıyor, üretim
      açık oturumun dökümüne katılıyor. **Kartta "İndir" var; "Düzenle" ve
      "+ Ek" YOK ve bu ölçülmüş bir karar** (§0.6/K14): ikisi de tam bir geçmiş
      kaydı istiyor, döküm yalnız id taşıyor — Adım 8'in composer turuna kaldı.
      Klasöre taşıma sonuç kartında hiç planlanmadı, Medya'nın işi.
- [x] Arama yalnızca Medya'da; üst şeritte arama alanı yok.
      **7 Ağustos'ta teslim** (Adım 7b, plan §0.7): sorgu üç alanda (prompt ·
      klasör adı · boyut), yazıldığı an klasör sınırı kalkıyor ("Arama
      sonuçları — tüm klasörler" + kartlarda klasör künyesi). Izgara boyutu
      S/M/L de aynı turda geldi.
- [ ] Dört tema da kontrast kapılarını geçiyor; monokrom varsayılan.
- [x] Silinmiş bir görselin sarkan `image_id`'si dökümü çökertmiyor, yer tutucu gösteriyor.
      **İki payı da bitti:** sunucu kaydı budamıyor ve 200 kalıyor (Adım 5);
      yer tutucu `resultThumb`'ın `error` dinleyicisiyle çiziliyor (Adım 7a).
      Ölçü gerçek koşul — dosya yoksa `/output/{id}.png` 404 döner (§0.6/K12).
- [x] `result` rolü Azure istemine gitmiyor ve token bütçesine sayılmıyor (birim testi).
      **7 Ağustos'ta teslim** — süzgeç rol düzeyinde, hem `chat_client.build_payload`'ta
      hem rotada; beşi de mutasyon testiyle doğrulandı (plan §0.4).
- [ ] Bugünkü tüm yetenekler temsil edilmiş: prompt, boyut/kalite/adet, referans + ek
      görsel, tema rengi/palet, logo/motto/banner + offset, klasörler, çoklu seçim,
      indirme, büyüteç, Azure ayarları, yönetmen sohbeti, içe aktarma.
      (**Yedekler bilerek düştü** — v4/V3, §4.1.)
- [x] §4.2 gerçekten teslim edildi: `chat.js`'te "Forma aktar" **kalmadı**, yerine
      "Görsel modunda üret"; Görsel modunda dolu kutuda "Yönetmen'e sor" çıkıyor.
      Sekmelerin kaldırılma gerekçesi bu maddedir — o yüzden ayrı kutu.
      **7 Ağustos'ta teslim** (Adım 8, plan §0.8): eski etiket yorumlarda da
      kalmadı; ters yön metni KOPYALAMIYOR taşıyor ve yönetmenin yazılmış
      mesajının üstüne yazmıyor (K21); düğme çerçevesiz metin (K22). Aynı turda
      Görsel modu kendi oturumunu başlatmaya başladı (K19).
- [ ] Tema seçici dört temayı gerçekten uyguluyor (`data-theme` yazılıyor) ve seçim
      kalıcı (§2.1). Token'ın var olması yetmez. **Kalıcılığın yeri değişti:**
      `settings` (kimlik dosyası) değil `prefs.json` — Adım 6'nın K6 kararı bir
      arayüz tercihini 0600'lük kimlik dosyasına koymayı reddetti ve tema o
      dosyayı otomatik kayıt anahtarıyla paylaşacak (seçici Adım 7b, kalıcılık Adım 9).
      **Seçici yarısı 7 Ağustos'ta teslim** (Adım 7b, plan §0.7): Araçlar →
      Görünüm dört temayı uyguluyor; monokrom özniteliği siliyor (K15) ve panel
      geçiciliği yazıyla söylüyor. Kutu kalıcılık gelmeden işaretlenmez.
- [ ] Emoji ikon yok, uydurma metrik yok, sol kenarı renkli yuvarlak kart yok, dekoratif
      gradient yok, aynı eylem için ikinci dolu düğme yok.
- [ ] Taşımada: `pytest` yeşil ve id sözleşmesi (`test_id_contract.py`) yeşil.

> **Bu liste tek başına yeterli değil.** 7 Ağustos denetimi, buradaki kaba
> ölçütlerin geçtiği hâlde 18 maddenin açık kalabildiğini gösterdi (wordmark,
> kebab, boş durum glifi, §4.2'nin iki düğmesi…). Madde-madde mandal uygulama
> planının **§7**'sinde: her açık maddenin kendi kutusu var ve bir madde ancak
> işaretlenerek ya da gerekçesiyle ertelenerek kapanıyor.

---

## 12. Nerede kaldık (7 Ağustos)

Bu bölüm "ekranları gez, onay ver, taşımaya başlayayım" diyordu — **o aşama
geçildi.** Ekranlar onaylandı, taşıma başladı, PR 1 merge edildi.

- **Bitti:** Adım 0–4 (tasarımın depoya alınması, token katmanı + id mandalı,
  kabuk, bileşen CSS'i, temizlik) → PR #16, `a1478d4`. Ayrıca 7 Ağustos'ta
  sürüm **2.0.0** ve wordmark'ın kaldırılması.
- **Bitti (`55b3356`, PR #19):** Adım 5 — §5'teki veri modeli. Koşullu
  `session_id`, `result` rolü + `params` şeması, türetilen `cover_image_id`,
  istem ve bütçe filtreleri. TDD ile: 32 test önce, `pytest` 1000 → **1032**.
- **Bitti (`55b3356`, PR #19):** Adım 6 — otomatik kayıt (D1) ve üç
  güvencesi. Yeni `prefs.py` deposu + `/api/prefs`, `DELETE /api/chats`,
  türetilen oturum adı, anahtar kapalıyken 409. `pytest` 1032 → **1062**.
- **Bitti (`55b3356`, PR #19):** Adım **7a** — PR 2'nin ekran payı ve
  bununla **PR 2 kapandı**. Sonuç kartı, "görsel silindi" yer tutucusu, sayı
  kapısının düzeltilmesi, başlıksız otomatik kayıt + anahtarın arayüzü + 409'un
  Türkçesi, "tüm oturumları sil", üretimin açık oturuma katılması, üst şeritteki
  oturum adı. `pytest` 1062 → **1080**; 18 mutasyonun hepsi kırmızı.
- **Bitti (`0223a19`, PR 3):** Adım **7b** — PR 1'in giydirme borcu
  (plan §0.2'nin A1–A6'sı): Kütüphane ve Araçlar kendi görünümleri, Medya'da
  arama (klasör sınırını aşan, künyeli), ızgara boyutu S/M/L, Azure/Tema
  panelleri slide-over, tema seçici (`data-theme` gerçekten yazılıyor; monokrom
  özniteliği siliyor). `pytest` 1080 → **1095**; iki id defterli kaldırıldı
  (`assets-modal`, `assets-close`). Kararlar K15–K18 ve kanıtlar plan §0.7'de.
- **Bitti (`2d97d94`, PR 3 · `APP_VERSION` 2.1.0):** Adım **8** — §4.2'nin manşeti.
  Prompt bloğunun düğmesi "Görsel modunda üret" (eski etiket yorumlarda da
  kalmadı), Görsel modunda dolu kutuda çerçevesiz "Yönetmen'e sor" (metni taşır,
  yönetmenin yazılmış mesajının üstüne yazmaz, sığmazsa kırpmaz reddeder) ve
  Görsel modu kendi oturumunu başlatıyor. `pytest` 1095 → **1106**; 9 mutasyonun
  hepsi kırmızı. Kararlar K19–K22 ve kanıtlar plan §0.8'de.
- **Sırada:** Adım **11 · 12 · 13** — 7 Ağustos kullanıcı denemesinin bulduğu üç
  açık, kendi planında: `docs/superpowers/plans/2026-08-07-flow-studio-tek-dokum.md`.
  11: Medya'da karta tıklamak büyüteci açar (+ kart eylemlerinin görünmez geri
  bildirimi). 12: (+) menüsünün dördüncü maddesi — bu dosyanın §4.2'de söz verdiği
  "Medya'dan seç" seçicisi (ölçüsü §2'de: 776×570). 13: `studio-session.html`'in
  kendisi — tek döküm, tek composer; mod değişince pencere de yazılan metin de
  değişmez.
- **Sonra:** Adım 9 (tema kalıcılığı — yeri `prefs.json`, bkz. §11 · Kütüphane
  "Yüklemeler" + "Tümü"), ardından Adım 10 (kozmetik süpürme; kebap menüsü ve
  **Medya sıralaması/D10** burada — sıralama Medya görünümüyle aynı turda gelsin
  diye Adım 12'nin seçicisine bilerek konmadı).
- **Ertelendi:** Yedekler paneli (v4/V3).
- **Karar bekleyen:** DM Sans bundle (§3 · plan §4) — indirme izni alındı, dosya
  adı ve boyutu söylenip son onay alınacak. Klasör "Yeniden adlandır" sözleşmeye
  girecek mi (plan §0.2/D17). Sonuç kartındaki "Düzenle" dökümden yeniden mi
  kurulacak, tek kayıt döndüren rotayı mı bekleyecek (plan §0.8 · K14).

**Sıra, adım ataması ve madde-madde mandal:**
`docs/superpowers/plans/2026-08-06-flow-arayuz-devri.md` — §0.1 (durum),
§0.2 (referans ekran ↔ uygulama denetimi), §0.3 (Adım 8/9/10),
§0.4 (Adım 5 kaydı: K1–K5), §0.5 (Adım 6 kaydı: K6–K9),
§0.6 (Adım 7a kaydı: K10–K14 + "aynı sürüm altında bayat JS" tuzağı),
§0.7 (Adım 7b kaydı: K15–K18 + mutasyon dersi),
§0.8 (Adım 8 kaydı: K19–K22 + "görünmez durum satırı" ve kaskad sırası
dersleri), §7 (kutular). Adım 0–8'in kaydı orada **kalıyor**; sıradaki turun
(11 · 12 · 13) tanımı ise ikinci planda:
`docs/superpowers/plans/2026-08-07-flow-studio-tek-dokum.md` — kararlar
A1–A9 (Medya kartı), B1–B11 (Medya seçici), C1–C8 (tek döküm) ve 12/13'ten
önce geçilecek Open Design mock kapısı.

> Bu dosya **tasarım sözleşmesi**; ne yapılacağını söyler. Uygulama planı
> **sıra ve kanıt**tan sorumludur. İkisi çeliştiğinde: tasarım kararı için bu
> dosya, deponun bugünkü hâli için plan geçerlidir.
