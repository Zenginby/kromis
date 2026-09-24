# Hukuk kontrol listesi — DPA / DPF gözden geçirmesi ve yayın öncesi adımlar

**Tarih:** 2026-09-24 · **Durum:** SAHİBİN DOLDURACAĞI TABLO (Faz 4 / 6, [faz4-odeme-abonelik-kvkk.md](faz4-odeme-abonelik-kvkk.md) §6 "DPA gözden geçirmesi") · **Metinler:** `bundled/hukuk/` (`HUKUK_SURUMU = "2026-10"`, `HUKUK_ONAYLI = False` — `services/hukuk.py`)

Aydınlatma metni (`/hukuk/gizlilik` § 4) her alıcıyı adıyla sayıyor; bu tablo o
alıcıların her biri için veri işleme sözleşmesinin (DPA) durumunu, AB–ABD Veri
Gizliliği Çerçevesi (DPF) sertifikasyonunu, verinin fiziksel konumunu ve
sözleşmenin kabul edildiği tarihi kaydeder. Test (`tests/test_hukuk.py`) yalnız
dosyanın ve satırların VARLIĞINI ölçer; hücreleri sahip doldurur. Bir alıcı
eklenir ya da çıkarsa önce aydınlatma metni, sonra bu tablo değişir ve
`HUKUK_SURUMU` ilerler.

## Alıcılar

| alıcı | rol | aktarılan veri | DPA durumu | DPF (AB–ABD) | veri konumu | KVKK md. 9 yolu | kabul tarihi |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Polar (Polar Software Inc.) | Merchant of Record — KENDİ veri sorumlusu | e-posta, ad, fatura adresi, sipariş | _doldurulacak_ (MoR sözleşmesi; DPA mı ortak sorumluluk mu — Polar belgesi) | _doldurulacak_ | _doldurulacak_ (ABD?) | _avukat_ | _—_ |
| Microsoft Azure (Azure OpenAI, Azure Foundry modelleri) | veri işleyen — model sağlayıcısı | istem, girdi görseli | _doldurulacak_ (Microsoft Products and Services DPA) | _doldurulacak_ | _doldurulacak_ (bölge seçimi: `AZURE_*` uç noktaları) | _avukat_ | _—_ |
| Google (Gemini, Imagen, Veo — Gemini API) | veri işleyen — model sağlayıcısı | istem, girdi görseli | _doldurulacak_ (Gemini API Additional Terms / Cloud DPA) | _doldurulacak_ | _doldurulacak_ | _avukat_ | _—_ |
| fal.ai (üçüncü parti modeller: FLUX/BFL, Qwen …) | veri işleyen — model sağlayıcısı | istem, girdi görseli | _doldurulacak_ | _doldurulacak_ | _doldurulacak_ | _avukat_ | _—_ |
| Fly.io | veri işleyen — barındırma (web + işçi süreci) | tüm uygulama trafiği, günlükler | _doldurulacak_ | _doldurulacak_ | _doldurulacak_ (bölge: `fly.toml`) | _avukat_ | _—_ |
| Neon (PostgreSQL) | veri işleyen — veri tabanı | hesap, oturum, iş, defter, sipariş satırları | _doldurulacak_ | _doldurulacak_ | _doldurulacak_ (proje bölgesi) | _avukat_ | _—_ |
| Cloudflare R2 | veri işleyen — nesne deposu | üretilen medya, girdi görselleri, varlıklar | _doldurulacak_ (Cloudflare DPA) | _doldurulacak_ | _doldurulacak_ (kova konumu) | _avukat_ | _—_ |
| Sentry | veri işleyen — hata izleme (PII KAPALI, Faz 2 / 9) | hata türü, yığın izi, istek kimliği | _doldurulacak_ (Sentry DPA) | _doldurulacak_ | _doldurulacak_ (AB/ABD bölge seçimi) | _avukat_ | _—_ |
| Resend (e-posta servisi) | veri işleyen — hizmet iletileri | alıcı adresi, ileti içeriği | _doldurulacak_ | _doldurulacak_ | _doldurulacak_ | _avukat_ | _—_ |

## Yayın öncesi adımlar (sahip; sıra önemli)

1. **Avukat** — dört metnin içerik incelemesi. Metinlerde `[…]` içinde
   işaretli açık noktalar: veri sorumlusunun iletişim e-postası; KVKK md. 9
   yurt dışı aktarım yolu (alıcı başına — bu tablo); iade politikasının
   Mesafeli Sözleşmeler Yönetmeliği md. 15 ve AB tüketici hakları ile uyumu;
   yetki/tüketici maddesi; yaş sınırı (18). Ayrıca `ticari-haklar` metnindeki
   sağlayıcı politika bağlantıları (OpenAI, Google, BFL, fal) yayın öncesi elle
   doğrulanmalı — geliştirme ortamından bu konaklara erişilemedi.
2. **Mali müşavir** — anonim hesap satırı, `kredi_hareketleri` ve `siparisler`
   için saklama süresi (metin ve K10 tablosu **10 yıl** yazıyor — TTK 82 /
   VUK 253 teyidi); iade politikasının fatura tarafı (Polar üzerinden iade).
3. **Bu tablo** doldurulur; alıcı listesi aydınlatma metniyle birebir kalır.
4. **`HUKUK_ONAYLI = True`** — tek satırlık PR (`services/hukuk.py`); "TASLAK"
   damgası her sayfadan kalkar. Metin o PR'da DEĞİŞMEZ; içerik değişikliği
   ayrı bir PR ve `HUKUK_SURUMU` ilerlemesidir (tüm kullanıcılara yeniden onay).
5. **Polar production başvurusu** — yayında metin ister (belge §3 "sahibin
   sırası: avukat → damga → Polar başvurusu").

## Metin değiştiğinde

* `bundled/hukuk/<slug>.{tr,en}.html` — iki dil AYNI değişikliği alır
  (`tests/test_hukuk.py` bölüm sayılarını karşılaştırır).
* `services/hukuk.HUKUK_SURUMU` → yeni `YYYY-AA`. Sonuç: her kullanıcı bir
  sonraki açılışta ayarlarda "şartlar güncellendi" banner'ını görür ve
  `POST /api/hesap/sartlar-kabul` ile yeni sürümü damgalar; checkout 412'si
  hiç onaylamamış kullanıcıya aynı sürümü yazar.
* Çerezler değişirse (`services/cerez.py`, `services/dil.py`) `cerez` metni de
  değişir; alıcı değişirse `gizlilik` § 4 ve bu tablo.
