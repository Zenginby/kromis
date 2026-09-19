""".env TÜREVLERİ git'e görünmüyor mu — ve `.env.example` hâlâ görünüyor mu.

NEDEN VAR: `.gitignore` uzun süre yalnız `.env` satırını taşıdı. O satır dosya
adının TAMAMINI eşler, yani `.env` düzenlenirken alınan her yedek git'e görünür
kalıyordu. 2026-09-19'da tam olarak bu oldu: `.env.yedek-20260919`
`git status`ta untracked çıktı ve içinde `KROMIS_PLATFORM_*` sağlayıcı
anahtarları, `KROMIS_NESNE_DEPO_GIZLI` ve `SENTRY_DSN` vardı. Dosya elle
silindi, commit'lenmedi — ama "elle silindi" bir mekanizma değil; bir dahaki
sefere `git add -A` insandan hızlı davranır.

SIZINTI TARAMASI BU BOŞLUĞU KAPATMIYOR: `.github/workflows/ci.yml`deki
`sizinti` işi `gitleaks git … .` çağırıyor, yani GEÇMİŞİ tarıyor (bkz.
tests/test_ci_sizinti.py — geçmişin tamamını okuması bilinçli bir karar).
Bir yedek dosyası geçmişe ancak commit'lendiğinde girer; tarama onu o anda
yakalar ama sır artık depoyu klonlayan herkeste. Bu dosyadaki kapı bir adım
önce, dosya indekse hiç girmeden duruyor. İkisi yedek değil ARDIŞIK: biri
girmeyi, öteki girmiş olanı yakalıyor.

ÖLÇÜM `git check-ignore` ile, `.gitignore` METNİ AYRIŞTIRILARAK DEĞİL:
kuralların sırası, olumsuzlamaları ve git'in dışlanan bir DİZİNE hiç inmemesi
elle yeniden kurulamayacak kadar ince (aynı incelik `.gitignore`da
`.claude/*` + `!.claude/settings.json` çiftinin gerekçesinde yazılı). Tek
dürüst tanık git'in kendisi.

`--no-index` ŞART: `git check-ignore` öntanımlı olarak indekse de bakar ve
İZLENEN bir dosya için asla "yok sayılıyor" demez. `.env.example` izlendiği
için, `!.env.example` istisnası hiç yazılmasa bile aşağıdaki "yok sayılmıyor"
iddiası bayraksız YEŞİL kalırdı — yani kuralı değil indeksi ölçerdi
(2026-09-19'da git 2.55 ile ölçüldü).
"""
from __future__ import annotations

import os
import subprocess
import uuid

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Gerçekten görülmüş ya da elin kendiliğinden yazdığı türevler. Liste ELLE
# tutuluyor, ama kapı ona BAĞLI DEĞİL: `test_an_env_name_nobody_wrote_down…`
# listede olmayan bir adı ölçüyor, yani eksik bir liste kapıyı boşaltmıyor
# (CLAUDE.md § 5'in "elle tutulan KAPSAM listesi" uyarısının karşılığı bu).
TUREVLER = (
    ".env",
    ".env.yedek-20260919",   # 2026-09-19'da gerçekten oluşan yedek
    ".env.yedek",
    ".env.local",
    ".env.production",
    ".env.bak",
    ".env.eski",
    ".env.save",
)

# İZLENMEYE DEVAM ETMESİ gerekenler.
#   * `.env.example` — `.env` sözleşmesinin bekçisi; tests/test_docker_kapisi.py
#     onu `ENV_EXAMPLE` olarak okuyup anahtar adlarını katalogla karşılaştırıyor.
#     Yok sayılırsa dosya bir gün sessizce düşer ve o kapı dosyayı hiç bulamaz.
#   * `alembic/env.py` — adında "env" geçen ama sır taşımayan bir KAYNAK. Kural
#     `*env*` gibi geniş yazılsaydı göç hattının girişi sessizce kaybolurdu.
GORUNUR = (".env.example", "alembic/env.py")


def _yok_sayiliyor(yol: str) -> bool:
    """git'in kendi yanıtı: bu yol yok sayılıyor mu?

    Yolun DİSKTE olması gerekmiyor — check-ignore yalnız kuralları uyguluyor,
    bu yüzden ölçüm için gerçek bir sır dosyası yaratmak gerekmez. Çıkış
    kodları: 0 = yok sayılıyor, 1 = sayılmıyor, ötesi = git hatası; üçüncüsü
    sessizce "sayılmıyor"a çevrilirse kapı bozuk git çağrısında yeşile döner.
    """
    sonuc = subprocess.run(
        ["git", "-C", REPO, "check-ignore", "-q", "--no-index", "--", yol],
        capture_output=True, text=True)
    assert sonuc.returncode in (0, 1), (
        f"git check-ignore {yol!r} hata verdi (çıkış {sonuc.returncode}): "
        f"{sonuc.stderr.strip()}")
    return sonuc.returncode == 0


@pytest.mark.parametrize("ad", TUREVLER)
def test_every_env_derivative_stays_out_of_git(ad: str):
    assert _yok_sayiliyor(ad), (
        f"{ad} git'e görünür: `git add -A` onu indekse alır. `.gitignore`'da "
        "`.env` yerine türevleri de kapsayan bir kalıp olmalı.")


def test_an_env_name_nobody_wrote_down_is_ignored_too():
    """Kural bir LİSTE değil, KALIP olmak zorunda.

    Yukarıdaki türev listesi elle tutuluyor; tek başına bırakılsaydı listede
    olmayan bir ad (`.env.perşembe`, `.env.musteri-demo`, editörün ürettiği
    `.env.orig`) kapıyı hiç görmeden geçerdi — `fal_client.py` ve
    `static/i18n.js` tam olarak böyle kaçmıştı. Rastgele bir ad, kalıbın
    gerçekten kalıp olduğunu enumerasyona dayanmadan ölçüyor.
    """
    ad = f".env.{uuid.uuid4().hex}"
    assert _yok_sayiliyor(ad), (
        f"{ad} yok sayılmıyor: kural türevleri tek tek sayıyor, kapsamıyor.")


@pytest.mark.parametrize("yol", GORUNUR)
def test_the_files_that_must_stay_visible_are_not_ignored(yol: str):
    assert not _yok_sayiliyor(yol), (
        f"{yol} yok sayılıyor: kapsayıcı kalıp fazla yutmuş. Gerekçesi "
        "GORUNUR'da yazılı; kalıbın yanına bir `!` istisnası gerekiyor.")


def test_the_example_file_is_still_tracked():
    """Yok sayılmamak yetmez — dosyanın hâlâ İZLENİYOR olması gerekiyor.

    `!` istisnası doğru yazılıp dosya ayrı bir hamleyle indeksten düşerse
    üstteki iddia yeşil kalır, oysa tests/test_docker_kapisi.py'nin okuduğu
    şablon yeni klonda YOK olur.
    """
    sonuc = subprocess.run(
        ["git", "-C", REPO, "ls-files", "--", ".env.example"],
        check=True, capture_output=True, text=True)
    assert sonuc.stdout.split() == [".env.example"], (
        ".env.example artık izlenmiyor: `.env` sözleşmesinin şablonu yeni "
        "klonlarda hiç bulunmaz.")


def test_no_tracked_file_is_hidden_by_the_ignore_rules():
    """Kapsayıcı kalıbın ÖTEKİ yönü — ve bu ölçüt tamamen mekanik.

    Yok sayılan ama izlenen bir dosya git'in en sessiz tuzağı: çalışma
    ağacında durduğu için her şey normal görünür, ama `git clean -dX`, yeni
    bir `git add` ya da araçların "ignored" filtresi onu artık başka türlü
    görür. GORUNUR listesi yalnız bugün bildiğimiz iki dosyayı çiviliyor;
    bu iddia ise her yeni izlenen dosyayı kendiliğinden kapsıyor.
    """
    izlenen = subprocess.run(["git", "-C", REPO, "ls-files", "-z"],
                             check=True, capture_output=True)
    # `-z` iki yönde de geçerli: hem stdin hem stdout NUL ile ayrılıyor, yani
    # boşluklu/Türkçe adlar bölünmüyor. Metin kipi YOK — bayt üzerinden
    # okuyup tek noktada, açıkça utf-8 çözüyoruz.
    gizlenen = subprocess.run(
        ["git", "-C", REPO, "check-ignore", "--no-index", "--stdin", "-z"],
        input=izlenen.stdout, capture_output=True)
    # `_yok_sayiliyor` ile aynı sebep: bozuk bir git çağrısı boş stdout verir ve
    # aşağıdaki iddia sahte yeşile döner. 1 = hiçbiri yok sayılmıyor (beklenen).
    assert gizlenen.returncode in (0, 1), (
        f"git check-ignore --stdin hata verdi (çıkış {gizlenen.returncode}): "
        f"{gizlenen.stderr.decode('utf-8', 'replace').strip()}")
    adlar = [y for y in gizlenen.stdout.decode("utf-8").split("\0") if y]
    assert not adlar, (
        "izlendiği hâlde yok sayılan dosya(lar) var — `.gitignore` fazla "
        "yutuyor:\n  " + "\n  ".join(sorted(adlar)))
