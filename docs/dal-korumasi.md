# `main` dal koruması

**Şu an açık olan tek şey: `main` silinemez ve zorla gönderilemez.** PR
zorunluluğu ve zorunlu durum denetimi BİLEREK kapalı — sebebi aşağıda, ölçülmüş
hâliyle yazılı.

Kural kümesinin depodaki kopyası: [`.github/rulesets/main.json`](../.github/rulesets/main.json).
Bekçisi: `tests/test_dal_korumasi.py`.

## Neden Aşama 1 bu iki kuralla sınırlı

`main` 2026-09-12'ye kadar hiç korumada değildi (REST ile ölçüldü:
`"protected": false`). Koruma ancak depo public olduktan sonra kullanılabilir
hâle geldi; özel depoda ücretsiz planda kapalıydı.

Açılabilecek kuralların hepsi aynı bedeli taşımıyor:

| Kural | Bedeli | Karar |
| --- | --- | --- |
| Silmeyi engelle | yok | **açık** |
| Zorla göndermeyi engelle | yok — botun push'u sıradan bir fast-forward | **açık** |
| PR zorunlu | yayın hattını KIRAR (aşağı bak) | kapalı, Aşama 2 |
| Zorunlu durum denetimi | yayın hattını KIRAR | kapalı, Aşama 2 |
| N onay zorunlu | tek kişilik depoda kilit: kendi PR'ını onaylayamazsın | kapalı |
| İmzalı commit | `github-actions[bot]`'un sürüm commit'i imzasız → hat durur | kapalı |
| Doğrusal geçmiş | depo merge commit'i kullanıyor (`Merge pull request #8…`) | kapalı |

Açık olan iki kuralın karşılığı küçük ama telafisi olmayan iki kaza sınıfı:
geçmişin ezilmesi ve dalın silinmesi. 2026-09-10'da `main` gerçekten yeniden
yazıldı (kimlik temizliği, `docs/superpowers/plans/2026-09-10-kromis-yeniden-adlandirma.md`);
o gün BİLEREK yapılan şeyin kazayla olması geri dönüşü olmayan tek olaydır.

## Neden PR zorunluluğu bugün hattı kırar

`release.yml` → `surum-yaz` işi sürüm commit'ini (`chore(surum): vX.Y.Z [skip ci]`)
`GITHUB_TOKEN` ile DOĞRUDAN main'e itiyor:

```sh
git push origin HEAD:main
```

O token `github-actions[bot]` olarak davranıyor: yazma yetkisi var, admin değil.
"PR zorunlu" da "zorunlu durum denetimi" de doğrudan push'u kapsıyor — yani
ikisinden biri açılırsa bot reddedilir ve **her merge'de** yayın `surum-yaz`
adımında kırmızıya düşer. Hattın kendi hata mesajı bunu zaten öngörüyor
("main korumaya alınmış olabilir"), ama bir hata mesajı kapı değildir: kusur
ancak bir yayın harcandıktan sonra görünürdü. Kapı `tests/test_dal_korumasi.py`
→ `test_no_rule_rejects_the_release_bots_direct_push`.

## Nasıl içe aktarılır

GitHub bu JSON'u kendiliğinden OKUMUYOR; dosya bir içe aktarım artefaktı ve
kayıttır. Ayar elle açılır:

1. Settings → Rules → Rulesets → **New ruleset** → *Import a ruleset*
2. `.github/rulesets/main.json` seçilir → **Create**
3. (İsteğe bağlı) Bypass list → *Add bypass* → **Repository admin**

3. adım dosyada YAZILI DEĞİL, çünkü muafiyet dağıtmak bilerek yapılan görünür
bir tıklamadır. Muafiyet eklenmezse geçmişi bilerek yeniden yazmanın yolu kural
kümesini geçici olarak *Disabled* yapmaktır — daha görünür, dolayısıyla daha
güvenli.

## Ayrışma riski

Bu dosya JSON'un ne dediğini anlatır, GitHub'daki CANLI ayarı değil; test de
canlı ayarı göremez. İkisi ayrışabilir. Denetlemenin yolu:

```sh
gh api repos/Zenginby/kromis/rulesets --jq '.[] | {name, enforcement}'
gh api repos/Zenginby/kromis/rulesets/<id> --jq '.rules[].type'
```

Kural kümesi UI'dan değiştirilirse *Export* edilip bu dosyanın üzerine yazılmalı
— değişiklik böylece diff'te GÖRÜNÜR bir karar olur.

## Aşama 2 — sonraki iş (henüz yapılmadı)

Amaç: kırmızı bir PR'ın merge edilebilmesini yapısal olarak imkânsız kılmak.
Sıra ÖNEMLİ — önce bota yol açılır, sonra kural eklenir:

1. **Botun push'una yol aç.** Üç seçenek:
   * **(a) Admin PAT** — secret'a konur, `surum-yaz` onunla push eder. En kolay,
     en riskli: main'e yazan kalıcı bir kişisel anahtar.
   * **(b) GitHub App + `actions/create-github-app-token`** — app kural
     kümesinin bypass listesine eklenir. Kurulum bedeli var, anahtar kısa
     ömürlü ve depoya kapsanmış. **Önerilen.**
   * **(c) Hattı main'e hiç yazmayacak şekilde kurgulamak** — `version.py`,
     README rozeti ve `GUNCELLEME.md` tek commit'te yazıldığı için büyük iş;
     önerilmiyor.
2. **Kural kümesine ekle:** `pull_request` (onay sayısı **0**) ve
   `required_status_checks`.
3. **Zorunlu kontroller — adları birebir:**
   * `Testler / Pytest takımı`
   * `Sızıntı taraması`

   Paket işleri zorunlu YAPILMAZ — 2026-09-16'dan beri `ci.yml`'de paket işi
   zaten yok (paketleme elle, bkz. [yayin-hatti.md](yayin-hatti.md)); daha
   önce de koşulluydular ve koşmayan bir kontrol PR'ı süresiz "bekliyor"da
   bırakabilirdi. `Lint` işi eklenebilir; mypy adımı `continue-on-error`
   olduğu için işin kendisi yeşil kalır.
4. **"Require branches to be up to date" açılmaz:** her main commit'inde
   yeniden koşu demek, karşılığı yok — `release.yml` zaten paketlemeden önce
   tam takımı bir kez daha koşuyor.
5. `tests/test_dal_korumasi.py`'deki `BOTU_KESENLER` kara listesi o zaman
   daralır; testin kendi gerekçesi de orada yazılı.

Aşama 2'nin kazancı sınırlı olduğu için acelesi yok: merge sonrası `release.yml`
→ `test` işi zaten tam takımı koşuyor, yani kırmızı bir merge yayına dönüşmüyor.
Engellediği tek şey, kırmızı bir PR'ı elle merge etme ihtimali.
