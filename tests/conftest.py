"""Paylaşılan test fixture'ları.

I3 bulgusu: "import'un yan etkisi yok" sözleşmesi yalnızca KURAL olarak
duruyordu — hiçbir mekanizma zorlamıyordu. `with TestClient(app)` FastAPI'nin
belgelediği standart kalıptır; bunu kullanan HERHANGİ bir test dosyası
lifespan'ı tetikler ve lifespan'daki yan etkiler GERÇEK dosya sistemine
(geliştiricinin repo kökündeki assets/ ve output/ dizinlerine) yazar.

Lifespan'da bugün BİR yan etki var: (2026-09-10'dan beri)
`paths._migrate_from_old_name` — eski `Lumeo` adıyla açılmış kullanıcı
dizinlerini yeni ada taşıyan göç. Guard'ı aşağıda, kendi bekçi dosyasında muaf.

TARİHÇE — iki guard daha vardı, ikisi de korudukları yan etkiyle birlikte gitti:
* `backup.backup_manifests_if_version_changed` (Faz 1 / 6'ya kadar): geliştiricinin
  repo kökünde gerçek `output/history.json` ve `assets/*/index.json` dosyaları
  VARDI, yani `with TestClient(app)` kullanan tek bir test `<repo>/backups/…` ve
  `<repo>/.last-version` bırakır, o kaçak damga da geliştiricinin bir sonraki
  sürüm yedeğini bir daha hiç almamasına yol açardı. Lifespan artık yedek
  ÇAĞIRMIYOR (manifest kalmadı, veri DB'de — docs/faz1-veritabani-hesaplar.md §6),
  yani yamalanacak çağrı yok; guard anlamsızlaştı ve kaldırıldı. Bekçisi
  tests/test_backup.py: `app.py` `backup`ı ithal etmez.
* `seed.seed_builtin_logos`: pakete gömülü yerleşik logoları kullanıcı
  kütüphanesine kopyalıyor ve `.logos-seeded`'i repo kökünde bırakıyordu.
  Uygulama marka-nötr olunca seed.py tümüyle kaldırıldı.

Aşağıdaki `pytest_configure` bir fixture DEĞİL: takım koşmadan önce
yorumlayıcının ön koşulunu (`os.fchmod`) bir kez sınıyor. Gerekçesi orada.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
import threading
import uuid
from collections.abc import Callable
from typing import Any, cast

import pytest
from fastapi import Depends, Request

import azure_client as azure_module
import kimlik_baglami
import paths as paths_module
from services import ayar, db, kiraci, sifre

# Salt kitaplık iki modül — takımın kendisi bir kuruluma bağlanmıyor:
# hangi dosyaların E2E olduğu TEK yerde ölçülüyor (gerekçesi orada); geçici
# Postgres kümesi de `tools/test_ortami.py --kontrol`ün açtığıyla aynı koddan.
from tools import gecici_postgres
from tools.test_ortami import e2e_dosyalari

_UNGUARDED_MIGRATION_FILENAME = "test_paths.py"

# Bu deponun ASGARİ Python sürümü — TEK tanım. README'nin "Gereksinimler"
# başlığı, requirements-dev.txt'in girişi ve CI'daki `python-version` pinleri
# buna göre sınanıyor (tests/test_python_surumu.py). Yani bu sayıyı değiştirmek
# tek bir yeri değil, o testin gösterdiği HER yeri değiştirmek demek.
ASGARI_PYTHON = (3, 13)

# Kapıyı bilerek atlamanın yolu; mesajın kendi içinde de yazılı.
ESKI_PYTHON_IZNI = "KROMIS_ALLOW_OLD_PYTHON"

# E2E'nin ATLANMASINI yasaklayan ortam değişkeni. CI bunu "1" veriyor
# (`_test.yml`), yani orada playwright kurulum adımı bir gün sessizce
# kaybolursa takım "yeşil ama eksik" olmaz, KIRMIZI olur.
E2E_ZORUNLU = "KROMIS_E2E_ZORUNLU"

# POSIX VARSAYAN TESTLERİN ATLANMASINI yasaklayan ortam değişkeni —
# `E2E_ZORUNLU`nun kardeşi ve aynı işi görüyor: CI bunu "1" veriyor
# (`_test.yml`), yani işaret bir gün Linux'ta da atlamaya başlarsa orada KIRMIZI
# olur. Gerekçesi `pytest_configure`daki kapıda.
POSIX_ZORUNLU = "KROMIS_POSIX_ZORUNLU"

# İŞARETİN TEK KOŞULU. `posix_gerekir` ile işaretlenmiş HER test buradan
# geçiyor; kapı (`pytest_configure`), özet (`_posix_atlama_ozeti`) ve bekçi
# (tests/test_posix_isareti.py) de aynı değeri okuyor. Koşulu bozmak bu yüzden
# dokuz yeri değil TEK yeri bozmak demek — ve o tek yer bozulduğunda CI'daki
# `KROMIS_POSIX_ZORUNLU=1` takımı hiç başlatmıyor. `_playwright_var()` ile aynı
# rol: "atlanacak mı" sorusunun tek yanıtı.
POSIX_ATLANACAK = sys.platform == "win32"

# İşaretli olup BU platformda atlanan testler: (nodeid, sebep).
# `_db_atlanan`ın ikizi — ama orada dosya adı yazılabiliyordu, burada test ADI:
# atlama fixture'da değil işaretin kendisinde olduğu için hangi testin
# atlandığı dürüstçe söylenebiliyor.
_posix_atlanan: list[tuple[str, str]] = []


def posix_gerekir(sebep: str):
    """POSIX varsayan bir testi Windows'ta ATLAR ve atlamayı GÖRÜNÜR kılar.

    ÖLÇÜLEN KUSUR (2026-09-19): Windows'ta tam takım "3808 passed, 9 failed"
    veriyordu ve dokuz kırmızının hiçbiri üründe kusur DEĞİLDİ — hepsi testin
    kendi yalıtımının POSIX varsayması: `os.sep`, izin bitleri, SIGTERM,
    `time.tzset`. Asıl sorun sayı değil, sayının SESSİZCE BÜYÜMESİYDİ:
    2026-09-18'de beş kırmızı vardı, PR #52 dört tane daha ekledi ve kimse fark
    etmedi. Dokuz "zaten kırmızı" satırın arasında ONUNCU — gerçek — bir
    gerileme Windows'ta hiç görünmezdi.

    NEDEN İŞARET, DÜZELTME DEĞİL: dokuzunun da sınadığı davranış ÜRETİMDE
    doğru ve CI (Linux) hepsini yeşil görüyor. Sınanan şey POSIX'e ait —
    testleri Windows'ta "yeşil" kılmak için gevşetmek, kapıyı Linux'ta da
    gevşetirdi.

    NEDEN DÜZ `skipif` YETMİYOR: `pytest_terminal_summary`nin yazdığı kural
    burada da geçerli — her atlama bir kusur değil; kusur olan, atlamanın
    GÖRÜNMEMESİ. Dokuz testi sessizce atlamak, CLAUDE.md §3'ün savaştığı
    "yeşil ama koşmamış" durumunun ta kendisi olurdu. Bu yüzden işaret üç
    mekanizmanın giriş kapısı: özet onları adıyla basıyor
    (`_posix_atlama_ozeti`), `KROMIS_POSIX_ZORUNLU` atlamayı hataya çeviriyor
    (`pytest_configure`), defter ile işaretin aynı küme olduğunu bir bekçi
    ölçüyor (tests/test_posix_isareti.py).

    NEDEN FABRİKA, PAYLAŞILAN TEK BİR `pytest.mark.skipif` DEĞİL: `reason`
    SOMUT olmak zorunda. "Windows" demek okuyana hiçbir şey öğretmiyor;
    "`time.tzset` Windows'ta yok" okuyana NEYİN eksik olduğunu ve düzeltmenin
    mümkün olup olmadığını söylüyor. Paylaşılan tek bir işaret o bilgiyi
    dokuzunda birden siler. Fabrika ikisini birden veriyor: koşul tek yerde
    (yukarıdaki `POSIX_ATLANACAK`), gerekçe her testte kendi.

    İki işaret birden takılıyor, biri atlamak biri SAYMAK için: `skipif` işi
    yapıyor, `pytest.mark.posix_gerekir` ise atlansın atlanmasın testin üstünde
    duruyor — bekçi defteri onunla karşılaştırıyor, yani işaret POSIX bir
    makinede de sayılabiliyor.
    """
    def _isaretle(islev):
        islev = pytest.mark.posix_gerekir(sebep)(islev)
        return pytest.mark.skipif(POSIX_ATLANACAK, reason=f"POSIX gerekir: {sebep}")(islev)
    return _isaretle


def pytest_collection_modifyitems(items) -> None:
    """İşaretli testlerden bu platformda ATLANACAK olanları toplar — özet onları adıyla basar."""
    _posix_atlanan.clear()
    if not POSIX_ATLANACAK:
        return
    for oge in items:
        isaret = oge.get_closest_marker("posix_gerekir")
        if isaret is not None:
            _posix_atlanan.append((oge.nodeid.replace("\\", "/"), str(isaret.args[0])))


def posix_atlananlar() -> list[tuple[str, str]]:
    """Bekçinin okuduğu kopya (tests/test_posix_isareti.py) — liste dışarıdan değiştirilmesin."""
    return list(_posix_atlanan)


# Postgres'e dokunan testlerin şablon veri tabanı: Alembic göçü BİR KEZ buraya
# uygulanır, her test dosyası `CREATE DATABASE … TEMPLATE` ile temiz bir kopya
# alır (TRUNCATE değil — kopya ~50 ms ve hiçbir tablo listesi tutmaz).
DB_SABLON = "kromis_sablon"

# `veritabani` fixture'ının Postgres bulamayıp ATLADIĞI test dosyaları —
# `pytest_terminal_summary` bunları E2E ile aynı gürültüyle basar.
_db_atlanan: set[str] = set()

# Takımın `KROMIS_SECRET_KEY`i (Faz 1 / 7) — SAHTE ve KAYNAKTA DÜZ METİN OLARAK
# YOK: değer 32 baytlık şu dizenin base64'ü, çalışma anında kuruluyor. Base64
# blobu kaynağa yazılsa sızıntı taraması onu bir anahtar sanırdı ve muafiyet
# listesi büyürdü (.gitleaks.toml "liste BÜYÜMEMELİ" diyor); `DUMMY` damgalı
# düz dize ise ilk kuralla zaten muaf. İkincisi döndürme testleri için "eski"
# anahtar. Tam 32 bayt: `sifre.kok_anahtarlar` uzunluğu sayıyor.
TEST_KOK_ANAHTARI = b"DUMMY-kromis-test-anahtari-00000"
TEST_ESKI_KOK_ANAHTARI = b"DUMMY-kromis-eski-anahtar-000000"


def sifre_anahtari(*kokler: bytes) -> str:
    """Kök bayt(lar)ından `KROMIS_SECRET_KEY` değeri — virgülle, en yenisi başta."""
    import base64
    return ",".join(base64.urlsafe_b64encode(k).decode() for k in kokler)


def _playwright_var() -> bool:
    return importlib.util.find_spec("playwright") is not None


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    """E2E atlandıysa takımın SONUNDA bunu bağıra bağıra söyler.

    NEDEN VAR (2026-09-13'te ölçüldü): `ci.yml` bu depoda dokuz kez kırmızıya
    döndü ve SEKİZİNDE düşen testler `tests/test_playwright_*.py`
    dosyalarındaydı. Playwright kurulu olmayan bir makinede o dosyalar
    `importorskip` ile ATLANIYOR ve pytest son satırda yine "passed" diyor.
    Kusur testlerde değil, SİNYALDE: "2531 passed, 11 skipped" cümlesi
    E2E'nin hiç koşmadığını söylemiyordu.

    NEDEN UYARI, KIRMIZI DEĞİL: playwright bilerek `requirements-dev.txt`te
    DEĞİL — paketleme işleri o dosyayı kurup pytest'i tarayıcısız koşturuyor
    ve orada atlama DOĞRU davranış (gerekçe: tests/test_playwright_kurulumu.py).
    Yani her atlama bir kusur değil; kusur olan, atlamanın GÖRÜNMEMESİ.
    Bilerek kırmızı isteyen için kapı ayrı: KROMIS_E2E_ZORUNLU=1.

    NEDEN SAYI DEĞİL DOSYA ADI: modül düzeyindeki `importorskip` tüm dosyayı
    tek bir "skipped" kaydına indiriyor, yani "kaç test atlandı" burada
    dürüstçe söylenemez. Atlanan DOSYALAR söyleniyor.
    """
    _db_atlama_ozeti(terminalreporter)
    _posix_atlama_ozeti(terminalreporter)
    if _playwright_var():
        return
    atlanan = e2e_dosyalari()
    if not atlanan:
        return
    # Eyleme dönük kısımlar ASCII: bu satırlar cp1252 bir konsola boru ile
    # yazıldığında Türkçe harfler `ı` kaçışlarına düşüyor (Faz 5 dersi,
    # bkz. pytest_configure'ın gerekçesi) — komut okunur kalmalı.
    terminalreporter.write_sep("=", "E2E ATLANDI: bu yesil, TAM yesil degil",
                               yellow=True, bold=True)
    terminalreporter.write_line(
        "playwright kurulu olmadigi icin su dosyalar HIC kosmadi:")
    for ad in atlanan:
        terminalreporter.write_line(f"    tests/{ad}")
    terminalreporter.write_line(
        "Bu depodaki ilk-kosu CI kirmizilarinin cogu tam olarak bu dosyalardi: "
        "arayuz metni, on tanimli dil ve DOM capasi degisiklikleri yalnizca "
        "burada gorunuyor.")
    terminalreporter.write_line("Ortami kur : python3 tools/test_ortami.py")
    terminalreporter.write_line(f"Atlamayi hataya cevir: {E2E_ZORUNLU}=1")
    terminalreporter.write_sep("=", yellow=True, bold=True)


def _db_atlama_ozeti(terminalreporter) -> None:
    """Postgres bulunamadığı için atlanan DB testleri — E2E uyarısının ikizi (Faz 1 / 1).

    Aynı kusur sınıfı, aynı çare: `veritabani` fixture'ı Postgres yoksa
    `pytest.skip` diyor ve pytest son satırda yine "passed" yazıyor. SQLite
    ile yeşil kalıp Postgres'te kırmızıya dönen bir göç dosyası tam olarak bu
    sessizlikte saklanırdı (docs/faz1-veritabani-hesaplar.md, K4). Dosya adı
    basılıyor, sayı değil: skip fixture'da olduğu için "kaç test" burada
    dürüstçe söylenemez.
    """
    if not _db_atlanan:
        return
    terminalreporter.write_sep("=", "POSTGRES YOK: DB testleri ATLANDI, bu yesil TAM yesil degil",
                               yellow=True, bold=True)
    terminalreporter.write_line(
        "ne KROMIS_TEST_DATABASE_URL verildi ne de makinede PostgreSQL ikilisi var; "
        "su dosyalardaki DB testleri HIC kosmadi:")
    for ad in sorted(_db_atlanan):
        terminalreporter.write_line(f"    tests/{ad}")
    terminalreporter.write_line("Kur: " + gecici_postgres.kurulum_yonergesi())
    terminalreporter.write_line("Denetle: python3 tools/test_ortami.py --kontrol")
    terminalreporter.write_line(f"Atlamayi hataya cevir: {E2E_ZORUNLU}=1")
    terminalreporter.write_sep("=", yellow=True, bold=True)


def _posix_atlama_ozeti(terminalreporter) -> None:
    """POSIX varsaydığı için bu platformda atlanan testler — E2E/DB uyarılarının üçüzü (2026-09-19).

    AYNI KUSUR SINIFI: pytest son satırda "3817 passed, 10 skipped" diyor ve o
    cümle, dokuz testin bu makinede HİÇ koşmadığını söylemiyor. Burada tehlike
    biraz daha sinsi, çünkü atlananlar bir dosya değil dokuz ayrı test: takımın
    geri kalanı gerçekten yeşil ve yeşil TAMMIŞ gibi duruyor.

    NEDEN DOSYA DEĞİL TEST ADI: E2E'de `importorskip` modül düzeyinde olduğu
    için "kaç test" dürüstçe söylenemiyordu; burada atlama işaretin kendisinde,
    yani hangi test olduğu tam olarak biliniyor. Sebep de basılıyor: okuyan
    kişi "Windows" diye bir şey değil, EKSİK OLAN ŞEYİ görsün.
    """
    atlanan = posix_atlananlar()
    if not atlanan:
        return
    # Eyleme dönük kısımlar ASCII (gerekçe: `pytest_configure`) — cp1252 bir
    # konsola boru ile yazıldığında komut ve değişken adı okunur kalmalı.
    terminalreporter.write_sep("=", f"POSIX VARSAYAN {len(atlanan)} TEST ATLANDI: bu yesil, TAM yesil degil",
                               yellow=True, bold=True)
    terminalreporter.write_line(
        f"bu platform ({sys.platform}) POSIX degil; su testler HIC kosmadi:")
    for nodeid, sebep in atlanan:
        terminalreporter.write_line(f"    {nodeid}")
        terminalreporter.write_line(f"        {sebep}")
    terminalreporter.write_line(
        "Hepsi CI'da (Linux) KOSUYOR ve yesil; urunde kusur degiller. Ama "
        "buradaki yesil onlari KAPSAMIYOR: bu dosyalardaki bir gerileme ancak "
        "CI'da gorunur.")
    terminalreporter.write_line("Defter : tests/test_posix_isareti.py")
    terminalreporter.write_line(f"Atlamayi hataya cevir: {POSIX_ZORUNLU}=1")
    terminalreporter.write_sep("=", yellow=True, bold=True)



def pytest_configure(config: pytest.Config) -> None:
    """`os.fchmod` yoksa takımı HİÇ başlatmaz; tek ve okunur bir hata verir.

    NEDEN VAR (2026-09-08): Windows + Python 3.12.10'da ölçüldü — takım
    "45 failed, 2142 passed" veriyor ve 45'inin de TEK sebebi
    azure_client.py:262'deki `os.fchmod`. Kimlik dosyası YAZAN her yol aynı
    satırdan geçtiği için kırmızı üç dosyaya birden yayılıyor (test_credstore
    12, test_settings 9, test_settings_route 24) ve hiçbiri sebebi söylemiyor:
    `AttributeError: module 'os' has no attribute 'fchmod'`. Üstelik sinyal
    YANLIŞTI — README "Python 3.10+" yazıyordu; geliştirici belgeye UYDUĞU için
    bu duvara çarpıyordu.

    NEDEN 3.13: `os.fchmod` CPython'un Windows yapısına o sürümde eklendi
    (belge: "Changed in version 3.13: Added support on Windows"). 3.12'de
    yedek bir yol da YOK — `os.chmod` orada dosya tanıtıcısı kabul etmiyor
    (aynı makinede ölçüldü: `os.chmod in os.supports_fd` → False).

    NEDEN DURDURMAK, uyarmak DEĞİL: 45 sebepsiz kırmızının içinde GERÇEK bir
    gerileme görünmez olur. winsec.py'deki ilkenin öteki yüzü — orada
    "testlerin yeşil olduğu bir yalan"dan kaçınılıyor; sebepsiz kırmızı da
    kapıyı aynı biçimde işlevsizleştirir. Bir kez söyle ve dur.

    NEDEN `hasattr(os, "fchmod")`, sürüm KARŞILAŞTIRMASI DEĞİL: sınanan şey
    yorumlayıcının NUMARASI değil, eksik olan YETENEK. POSIX'te `fchmod` 3.13
    öncesinde de var ve orada takımı durdurmanın hiçbir sebebi yok — kapı bu
    yüzden yalnızca gerçekten kırılan yerde kapanıyor. `winsec.is_supported()`
    ile aynı disiplin.

    NEDEN Türkçe metin: depo geleneği — ama ÖLÇÜLDÜ: cp1252 konsola boru ile
    yazıldığında pytest `backslashreplace` uyguluyor, yani harfler `\\u0131`
    kaçışlarına düşer ama UnicodeEncodeError ÇIKMIYOR
    (test_encoding_contract'ın Faz 5 dersi). Eyleme dönük kısımlar — sürümler,
    komutlar, ortam değişkeni — bu yüzden ASCII bırakıldı: kodlama ne olursa
    olsun onlar okunur kalıyor.
    """
    # E2E KAPISI (gerekçesi pytest_terminal_summary'de): atlama açıkça
    # yasaklandıysa takımı HİÇ başlatma. `_test.yml` bu değişkeni veriyor, yani
    # CI'da playwright kurulum adımı bir gün sessizce kaybolursa kapı kapanır —
    # `tests/test_playwright_kurulumu.py` workflow'un METNİNİ sınıyor, bu satır
    # da onun GERÇEKTEN iş görüp görmediğini.
    if os.environ.get(E2E_ZORUNLU) == "1" and not _playwright_var():
        raise pytest.UsageError(
            f"{E2E_ZORUNLU}=1 verildi ama playwright kurulu DEGIL: E2E "
            "testleri atlanacakti."
            "\n\n"
            "COZUM: python3 tools/test_ortami.py"
            "\n\n"
            f"Atlamaya izin vermek icin {E2E_ZORUNLU} degiskenini kaldirin "
            "(paketleme isleri pytest'i bilerek tarayicisiz kosturuyor)."
        )
    # AYNI KAPI, POSTGRES İÇİN (Faz 1 / 1. görev): değişkenin adı kaldı,
    # anlamı "tam takım zorunlu"ya genişledi. CI'da Postgres servisi bir gün
    # sessizce düşerse DB testleri atlanır ve takım yeşil kalırdı — burada
    # kırmızı olur. Yerelde verilmiyor; orada atlamanın GÖRÜNMESİ yeter
    # (`_db_atlama_ozeti`).
    if os.environ.get(E2E_ZORUNLU) == "1" and gecici_postgres.kaynak() is None:
        raise pytest.UsageError(
            f"{E2E_ZORUNLU}=1 verildi ama Postgres YOK: ne "
            f"{gecici_postgres.TEST_URL_ENV} verildi ne de makinede PostgreSQL "
            "ikilisi (initdb/pg_ctl) var; DB testleri atlanacakti."
            "\n\n"
            "COZUM: " + gecici_postgres.kurulum_yonergesi()
        )

    # AYNI KAPI, POSIX VARSAYAN TESTLER İÇİN (2026-09-19). Değişken ayrı
    # (`KROMIS_POSIX_ZORUNLU`), çünkü sorduğu soru ayrı: E2E/DB kapısı "ortam
    # kurulu mu" diye soruyor, bu "bu makine ATLAMAYA yol açar mı" diye.
    #
    # NEDEN TEK BİR KOŞULU SINAMAK YETİYOR: işaretli dokuz testin hepsi
    # `posix_gerekir` üstünden, o da yalnız `POSIX_ATLANACAK` üstünden
    # atlıyor. Yani "işaret bir gün Linux'ta da atlamaya başladı" durumunun
    # TEK yolu bu değişkenin orada doğrulanması — ve CI `KROMIS_POSIX_ZORUNLU=1`
    # verdiği için o gün takım yeşil kalmıyor, HİÇ başlamıyor. İşaretin doğru
    # testlerin üstünde durduğunu ise `tests/test_posix_isareti.py` ölçüyor;
    # ikisi farklı şeyler, biri mekanizmayı öteki defteri sınıyor.
    if os.environ.get(POSIX_ZORUNLU) == "1" and POSIX_ATLANACAK:
        raise pytest.UsageError(
            f"{POSIX_ZORUNLU}=1 verildi ama bu platform ({sys.platform}) POSIX "
            "DEGIL: POSIX varsayan testler atlanacakti."
            "\n\n"
            "COZUM: takimi bir POSIX makinede (ya da CI'da) kosturun; bu "
            "testler izin bitleri, SIGTERM ve time.tzset gibi POSIX "
            "yeteneklerini sinar."
            "\n\n"
            f"Atlamaya izin vermek icin {POSIX_ZORUNLU} degiskenini kaldirin: "
            "atlama yerelde DOGRU davranis, yanlis olan gorunmemesiydi "
            "(takimin sonundaki ozet onu kapatiyor)."
        )

    # NESNE DEPOLAMA ORTAMI TESTE SIZMASIN (Faz 2 / 2): `app.state.dosya` İTHAL
    # ANINDA `KROMIS_NESNE_DEPO_*`tan kuruluyor (services/dosya.py); geliştiricinin
    # kabuğunda gerçek R2 değerleri dururken takım koşsa 178 rota testi GERÇEK
    # kovaya yazardı. Fixture geç kalır (ithal toplama sırasında), o yüzden
    # burada — `_guard_against_the_developers_real_database`in ithal-öncesi ikizi.
    # Nesne depolamayı sınayan testler depoyu `app.state.dosya`ya kendileri koyar.
    for ad in list(os.environ):
        if ad.startswith("KROMIS_NESNE_DEPO_"):
            os.environ.pop(ad)

    if hasattr(os, "fchmod"):
        return
    if os.environ.get(ESKI_PYTHON_IZNI) == "1":
        return  # bilinçli atlama: yukarıda sayılan 45 test yine düşecek

    asgari = ".".join(str(parca) for parca in ASGARI_PYTHON)
    bulunan = ".".join(str(parca) for parca in sys.version_info[:3])
    raise pytest.UsageError(
        f"Bu depo Python {asgari}+ ISTIYOR - bulunan: {bulunan} ({sys.platform})."
        "\n\n"
        "NEDEN: azure_client._atomic_write, kimlik dosyasini yazmadan ONCE "
        "izinleri sikilastirmak icin `os.fchmod(fd, 0o600)` cagiriyor ve bu "
        "cagri CPython'un Windows yapisina ancak 3.13'te eklendi. Bu "
        "yorumlayicida kimlik YAZAN her test \"AttributeError: module 'os' has "
        "no attribute 'fchmod'\" ile duser (olculdu: 45 test) - kusur SENIN "
        "degisikliginde degil, yorumlayicida."
        "\n\n"
        "COZUM: 3.13 ya da ustunu kur (CI ve paketler 3.14 kullaniyor) ve "
        ".venv'i onunla yeniden yarat:\n"
        "    py -3.13 -m venv .venv\n"
        "    .venv\\Scripts\\python -m pip install -r requirements.txt "
        "-r requirements-dev.txt"
        "\n\n"
        "Kimlige dokunmayan testleri bu yorumlayicida yine de kosmak icin: "
        f"{ESKI_PYTHON_IZNI}=1 (o 45 test yine duser)."
    )


@pytest.fixture(autouse=True)
def _guard_against_leaking_android_env():
    """Android dalını açan ortam değişkenleri testler arasında SIZMASIN.

    Üçüncü guard, aynı sınıf bir tehdide karşı: `paths.py`'nin Android dalı
    `KROMIS_ANDROID_DATA_DIR` ortam değişkenine bakıyor ve o değişken KÜRESEL —
    `monkeypatch` yalnız KENDİ yazdığı değerleri geri alıyor. Ortam değişkenine
    doğrudan yazan bir üretim fonksiyonu (`android_main._prepare_environment`,
    Kotlin'in yaptığı işi taklit ederken) değeri geride bırakırsa, o noktadan
    SONRAKİ her test `paths.data_dir()`'i repo kökü yerine sahte bir Android
    dizini sanır.

    Bu teorik değil, ölçüldü: guard yazılmadan önce tek bir sızıntı
    test_chat_prompt / test_logo / test_paths'te 27 testi birden düşürdü —
    üstelik hata mesajları kaynağa hiç işaret etmiyordu. Guard, teşhisi zor bu
    kırılma sınıfını tümden kapatıyor.
    """
    yield
    for ad in (paths_module.ANDROID_DATA_ENV, paths_module.ANDROID_RESOURCE_ENV):
        os.environ.pop(ad, None)


@pytest.fixture(autouse=True)
def _guard_against_real_migration(request: pytest.FixtureRequest,
                                  monkeypatch: pytest.MonkeyPatch):
    """Ad göçünü varsayılan olarak no-op yapar (2026-09-10).

    DÖRDÜNCÜ guard, (kaldırılan) yedek guard'ıyla aynı sınıf bir tehdide karşı:
    `paths.ensure_data_dirs()` artık `_migrate_from_old_name()` çağırıyor ve o
    fonksiyon geliştiricinin GERÇEK `~/.config/lumeo/credentials.env` dosyasını
    `~/.config/kromis/` altına taşıyor. `with TestClient(app)` kullanan tek bir
    test, geliştiricinin ev dizinini oynatırdı — üstelik sessizce, çünkü göç
    başarılı olduğunda hiçbir şey söylemiyor.

    Muafiyet `test_paths.py`: göç davranışının bekçisi orada ve gerçek
    fonksiyonu koşturmak zorunda. O dosyadaki her göç testi yolları tmp_path'e
    çekiyor, yani muafiyet ev dizinini açıkta bırakmıyor.
    """
    if os.path.basename(str(request.node.fspath)) == _UNGUARDED_MIGRATION_FILENAME:
        yield
        return
    monkeypatch.setattr(paths_module, "_migrate_from_old_name", lambda: None)
    yield


@pytest.fixture(autouse=True)
def _dil_baglami_testler_arasinda_sizmasin():
    """Her testi `i18n.FALLBACK` bağlamıyla başlatır.

    BEŞİNCİ guard ve sebebi ÖLÇÜLDÜ (v0.22, ön tanımlı dil "en" olurken):
    `app._dil_baglami` her istekte `i18n.set_active` çağırıyor ve `TestClient`
    isteği kendi portalında koşturduğu için o değer ana bağlamda ASILI
    KALIYOR. Yani bir `client.post(...)`tan sonra koşan HER test, bağlamı hiç
    kurmadan `i18n.t(anahtar, None)` çağırdığında bir önceki testin dilini
    görüyor — sıraya bağlı, dosya dışına taşan bir sızıntı.

    Sızıntı ÖNCEDEN DE VARDI, yalnızca GÖRÜNMÜYORDU: ön tanımlı dil ile
    kaynak dil aynı olduğu sürece sızan değer zaten beklenen değerdi. İkisi
    ayrılınca `map_error`ı doğrudan çağıran testler (test_gemini_client ve
    yedi ikizi) tek başına YEŞİL, takımın içinde KIRMIZI oldu — testin kendi
    kusuru değil, bağlamın kusuru.

    `FALLBACK`, `DEFAULT` DEĞİL: bu fixture'ın kurduğu şey "kullanıcı yok"
    hâli ve `i18n._AKTIF`ın kendi varsayılanı da o (gerekçesi orada). Ürünün
    ön tanımlı dilinin bekçisi ayrı: `test_prefs.py` varsayılanı,
    `test_i18n.py` de hiç tercih yazılmamış bir kurulumun hangi dilde
    servis edildiğini sınıyor.

    `tercih.sifirla()` BURADAYDI (Faz 0 / Adım 3) ve Faz 1 / 4'te çıktı: dil
    zinciri `services/tercih.py`nin dosya imzalı önbelleğini artık okumuyor
    (3. halka `kullanicilar.dil`, services/dil.py), yani testler arasında
    sızacak bir önbellek okuyucusu kalmadı; Faz 1 / 6'da modülün kendisi de
    silindi (tercihler DB'de, `services/depo_tercih.py`).
    """
    import i18n
    i18n.set_active(i18n.FALLBACK)
    yield


# E2E SUNUCULARININ İKİ SÜRESİ, BİRLİKTE OKUNMAK ÜZERE BURADA.
#
# `KAPANIS_TAVANI_SN` her test sunucusunun `uvicorn.Config`ine veriliyor
# (`tests/test_e2e_sunucu_kapanisi.py` hiçbirinin unutulmadığını bekliyor).
# VERİLMEZSE uvicorn'un öntanımlısı `None`, yani "biten bir yanıt bekleyip
# SONSUZA KADAR dur". Tutan şey açık soket DEĞİL, BİTMEYEN YANIT (ürün yüzü:
# `isler` panelinin SSE akışı) — ölçüldü 2026-09-20: tavansız sunucu 8 sn
# sonra hâlâ yaşıyor, 1 sn tavanla 1,21 sn'de ölüyor. `stop()` yalnız
# `should_exit` yazıyor, beklemiyor; bekleyen aşağıdaki fixture ve o da her
# testte yeniden bekliyor. Sonuç iki kez görüldü (19 ve 20 Eylül, iki ayrı
# dosyanın sunucusu sızdı): takım 6 dakikadan 80+ dakikaya çıktı ve bitmedi.
#
# İKİSİ ARASINDAKİ İLİŞKİ ŞART: tavan `join` süresinden KÜÇÜK olmalı, yoksa
# fixture sunucu ölmeden vazgeçer ve aynı vergi geri gelir. Bekçisi
# `test_the_shutdown_ceiling_stays_under_the_join_deadline`.
KAPANIS_TAVANI_SN = 1
JOIN_TAVANI_SN = 10


@pytest.fixture(autouse=True)
def _eski_e2e_sunuculari_kapansin():
    """Önceki testin uvicorn iş parçacığı bitmeden yeni test başlamasın (Faz 1 / 3).

    YEDİNCİ guard ve ölçüldü — tam takımda iki kez, iki yönde: E2E dosyaları
    uvicorn'u daemon bir iş parçacığında koşturuyor ve `stop()` yalnız
    `should_exit` diyor, BEKLEMİYOR. Uygulama nesnesi ve `app.state` süreçte
    TEK; eski sunucunun geç kalan lifespan KAPANIŞI sonraki testin kurduğu
    motoru siliyordu (`test_playwright_hesap` ilk istek `database_unavailable`),
    geç kalan lifespan AÇILIŞI da sonraki testin postacısını eziyordu
    (`test_posta` "kapanışta None" iddiası). `app.py` kendi motorunu kimlikle
    düşürüyor (ilk emniyet); burası ikincisi: bir sonraki test başlamadan
    önce hâlâ yaşayan her uvicorn iş parçacığı bitirilir. Bedeli sıfıra yakın
    (`threading.enumerate` + `join`), E2E dışı testlerde eşleşen iş parçacığı
    yok. Zaman aşımı: `stop()` denmemiş bir sunucu takımı asmasın.

    "BEDELİ SIFIRA YAKIN" CÜMLESİ TEK BAŞINA DOĞRU DEĞİLDİ ve bunu bir kez
    ödedik: zaman aşımı asılmayı önlüyor ama ölmeyen bir sunucu varsa bedel
    sıfır değil, HER TESTTE `JOIN_TAVANI_SN` oluyor — 2026-09-19'da takımı 6
    dakikadan 80+ dakikaya çıkardı. Cümleyi doğru kılan şey artık yukarıdaki
    `KAPANIS_TAVANI_SN`: sunucu gerçekten ölüyor, `join` de anında dönüyor.
    Yani buradaki zaman aşımı SON emniyet, birinci emniyet o tavan.
    """
    import uvicorn
    for t in threading.enumerate():
        if isinstance(getattr(t, "server", None), uvicorn.Server) and t is not threading.current_thread():
            t.join(timeout=JOIN_TAVANI_SN)
    yield


@pytest.fixture(autouse=True)
def _sifre_anahtari_ve_kimlik_baglami(monkeypatch: pytest.MonkeyPatch):
    """Her test sahte bir `KROMIS_SECRET_KEY` ile ve BOŞ kimlik bağlamıyla başlar (Faz 1 / 7).

    ANAHTAR: `depo_kimlik_bilgisi` her okuma/yazmada `sifre.sifreci()` ile ortamı
    okuyor ve `app._lifespan` DB'li süreçte anahtarsız AÇILMIYOR — yani
    `depo_db`/`veritabani` kullanan her dosya ve E2E sunucuları anahtarı
    bekliyor. Tek kaynak BURASI (CI'a ikinci bir değer yazılmadı: iki kaynak
    ayrışır, yerel koşu CI'a bağımlı olmaz). Geliştiricinin kabuğundaki GERÇEK
    bir anahtar da testlere sızmaz: `setenv` onu bu test süresince ezer.
    Anahtarın kendisini sınayan testler `monkeypatch.delenv/setenv` ile ezer.

    BAĞLAM: `kimlik_baglami` bir ContextVar ve TestClient'ın portalı istekler
    arasında bağlamı taşıyabiliyor (`_dil_baglami_testler_arasinda_sizmasin`ın
    ölçtüğü sızıntı sınıfı). Bağımlılık rota dönünce çözüyor; burası ikinci
    emniyet — bir önceki testin sözlüğü sonrakine görünmesin.
    """
    monkeypatch.setenv(sifre.ANAHTAR_ENV, sifre_anahtari(TEST_KOK_ANAHTARI))
    kimlik_baglami.sifirla()
    kiraci.sifirla()
    yield
    kimlik_baglami.sifirla()
    # Kiracı bağlamı da bir ContextVar (Faz 2 / 7) ve aynı sızıntı sınıfına açık.
    kiraci.sifirla()


@pytest.fixture(autouse=True)
def _web_yolunda_kimlik_dosyasi_acilmaz(request: pytest.FixtureRequest,
                                        monkeypatch: pytest.MonkeyPatch):
    """DB'li testlerde `credentials.env` AÇILAMAZ: `azure_client._parse_env_all` patlar (Faz 1 / 7).

    Belge §7 çıkış ölçütü: web yolunda kimlik dosyası hiç açılmıyor. AST bekçisi
    (tests/test_galeri_db.py) çağrıyı kaynakta arıyor; bu guard ÇALIŞMA ZAMANINI
    ölçüyor — dolaylı bir yol (bir adaptörün `credentials=None` düşmesi, bir
    yardımcının eski okuyucuyu çağırması) dosyaya inerse rota testi kırmızı
    olur, sessizce geçmez. Yalnız `depo_db`/`veritabani` isteyen dosyalarda:
    dondurulmuş kabuğun dosya testleri (`test_settings.py`, `test_chat_client.py`
    …) o okuyucuyu bilerek kullanıyor.
    """
    if not {"depo_db", "veritabani"} & set(request.fixturenames):
        yield
        return

    def _patlat(path: str) -> dict[str, str]:
        raise AssertionError(
            f"web yolunda kimlik DOSYASI açıldı: {path} — kimlikler DB'den gelir "
            "(services/depo_kimlik_bilgisi.py); bkz. docs/faz1-veritabani-hesaplar.md §7")

    monkeypatch.setattr(azure_module, "_parse_env_all", _patlat)
    yield


@pytest.fixture(autouse=True)
def _guard_against_the_developers_real_database(monkeypatch: pytest.MonkeyPatch):
    """Geliştiricinin kabuğundaki `DATABASE_URL` testlere SIZMASIN (Faz 1 / 1).

    ALTINCI guard, Android/yedek/göç guard'larıyla aynı sınıf: `app._lifespan`
    `DATABASE_URL`i `os.environ`dan okuyor ve `with TestClient(app)` kullanan
    her test lifespan'ı koşturuyor. Kabukta gerçek bir bağlantı dizesi
    duruyorsa (yerelde compose'un Postgres'i, ya da daha kötüsü yönetilen
    bir sunucu) o testler ORAYA bağlanırdı — 2. görevden itibaren tablo
    yaratıp silen göç testleri dâhil. Testin göreceği tek URL `veritabani`
    fixture'ının kendisinin koyduğu URL.
    """
    monkeypatch.delenv(db.DATABASE_URL_ENV, raising=False)
    yield


def _yonetici_motor(url: str):
    """`CREATE/DROP DATABASE` için AUTOCOMMIT + havuzsuz motor (ikisi de transaksiyon dışı ister)."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    return create_engine(url, isolation_level="AUTOCOMMIT", poolclass=NullPool)


def _veritabani_urlsi(yonetici_url: str, ad: str) -> str:
    from sqlalchemy.engine import make_url
    return make_url(yonetici_url).set(database=ad).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def pg_kume(request: pytest.FixtureRequest) -> str:
    """Oturum boyunca TEK Postgres: `KROMIS_TEST_DATABASE_URL` ya da geçici küme.

    Döneni bakım DB'sine süper kullanıcı bağlantısıdır; testler bunu DOĞRUDAN
    kullanmaz, `veritabani` fixture'ı oradan kopya DB açar. Postgres HİÇ yoksa
    `pytest.skip` — gürültüsü `_db_atlama_ozeti`de, hataya çevrilmesi
    `pytest_configure`da (`KROMIS_E2E_ZORUNLU=1`).

    Gerekçe (docs/faz1-veritabani-hesaplar.md, 1. görev): GERÇEK Postgres,
    Docker'sız — CI'da servis konteyneri, yerelde makinedeki ikililerle
    `initdb` + `pg_ctl` (`tools/gecici_postgres.py`; ölçüldü, açılış ~0,8 sn).
    """
    kaynak = gecici_postgres.kaynak()
    if kaynak is None:
        pytest.skip("Postgres yok: ne KROMIS_TEST_DATABASE_URL ne de initdb/pg_ctl "
                    "(python3 tools/test_ortami.py --kontrol)")
    if kaynak == "env":
        return os.environ[gecici_postgres.TEST_URL_ENV]
    kume = gecici_postgres.GeciciKume(kaynak)
    request.addfinalizer(kume.kapat)
    return kume.ac()


@pytest.fixture(scope="session")
def pg_sablon(pg_kume: str) -> str:
    """Alembic göçü uygulanmış ŞABLON DB'nin adı — oturumda bir kez kurulur.

    Önce `DROP … WITH (FORCE)`: geliştiricinin kalıcı bir sunucusunda
    (`KROMIS_TEST_DATABASE_URL`) önceki koşunun şablonu durabilir ve eski bir
    göç hâlini taşırdı. Geçici kümede boşa bir komut.
    """
    from alembic.config import Config
    from sqlalchemy import text

    from alembic import command

    yonetici = _yonetici_motor(pg_kume)
    try:
        with yonetici.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {DB_SABLON} WITH (FORCE)"))
            c.execute(text(f"CREATE DATABASE {DB_SABLON}"))
        ayar_dosyasi = Config(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "alembic.ini"))
        # URL `attributes` ile: env.py bunu `DATABASE_URL`den ÖNCE okuyor.
        ayar_dosyasi.attributes["baglanti_dizesi"] = _veritabani_urlsi(pg_kume, DB_SABLON)
        command.upgrade(ayar_dosyasi, "head")
    finally:
        yonetici.dispose()
    return DB_SABLON


@pytest.fixture(scope="module")
def veritabani_url(request: pytest.FixtureRequest, pg_kume: str, pg_sablon: str):
    """Bu test DOSYASINA ait temiz DB (şablonun kopyası); dosya bitince düşer.

    Modül kapsamı bilinçli: dosya içindeki testler aynı DB'yi paylaşır (bir
    dosya kendi düzenini kendi kurar), dosyalar arası SIFIR sızıntı.
    """
    from sqlalchemy import text

    govde = re.sub(r"[^a-z0-9]+", "_", os.path.splitext(request.module.__name__.split(".")[-1])[0].lower())
    ad = f"kromis_t_{govde}"[:56] + "_" + os.urandom(3).hex()
    yonetici = _yonetici_motor(pg_kume)
    with yonetici.connect() as c:
        c.execute(text(f"CREATE DATABASE {ad} TEMPLATE {pg_sablon}"))
    yield _veritabani_urlsi(pg_kume, ad)
    with yonetici.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {ad} WITH (FORCE)"))
    yonetici.dispose()


@pytest.fixture
def veritabani(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """Testin uygulaması GERÇEK bir Postgres'e bağlansın: `DATABASE_URL` bu dosyanın DB'sine.

    Kullanımı: `with TestClient(app) as c` — motor lifespan'da kurulduğu için
    (services/db.py) `with` ŞART; `with`siz `TestClient(app)` `db_reachable:
    false` görür ve bu da bilerek sınanıyor (tests/test_health.py).

    Postgres yoksa dosya adı `_db_atlanan`a yazılır ve test atlanır; skip'i
    `pg_kume` atıyor, buradaki kayıt yalnız özetin dosya adını bilmesi için.
    """
    if gecici_postgres.kaynak() is None:
        _db_atlanan.add(os.path.basename(str(request.node.fspath)))
    url: str = request.getfixturevalue("veritabani_url")
    monkeypatch.setenv(db.DATABASE_URL_ENV, url)
    return url


@pytest.fixture(scope="module")
def veritabani_motor(veritabani_url: str):
    """Bu dosyanın DB'sine bağlı motor — `depo_db`/`db_oturumu` ve `kullanici` fixture'ının DB kipi.

    Uygulamanın `app.state.motor`u DEĞİL: 37 dosyanın `TestClient(app)`i
    `with`siz, yani lifespan koşmuyor ve motor yok. Depo rotaları (Faz 1 / 5)
    yine de bir `Session` istiyor; bu motor onu `db.oturum` override'ı üzerinden
    veriyor. Modül kapsamı `veritabani_url` ile aynı: dosya bitince `dispose`,
    sonra DB düşer (`WITH (FORCE)` açık bağlantıya takılmaz, ama havuz yine de
    kapansın).
    """
    from sqlalchemy import create_engine
    motor = create_engine(veritabani_url, pool_size=2, max_overflow=3)
    yield motor
    motor.dispose()


@pytest.fixture
def depo_db(veritabani: str, veritabani_motor):
    """Depo rotalarını (galeri, klasör, sohbet, palet, varlık, tercih) sınayan dosyaların OPT-IN kapısı (Faz 1 / 5-6).

    Kullanımı modül başında: `pytestmark = pytest.mark.usefixtures("depo_db")`.
    Etkisi `kullanici` fixture'ında: test kullanıcısı DB'ye GERÇEK bir satır
    olarak yazılır (`medya.kullanici_id` FK'sı sahte bir uuid'yi reddeder) ve
    `db.oturum` bu dosyanın motoruna bağlı bir `Session` verir — `TestClient(app)`
    `with`siz kalır, 178 çağrı değişmez. Döneni motor.

    `veritabani`nin kendisine bağlanmıyor ve bilerek: `veritabani`yi DOĞRUDAN
    isteyen dosyalar (`test_db.py`, `test_health.py`, `test_tablolar.py`) motoru
    ve `db.oturum`u kendileri sınıyor; override oraya sızsa "commit hatası 500
    olur" gibi iddialar sahte bir oturuma karşı koşardı.
    """
    return veritabani_motor


@pytest.fixture
def db_oturumu(depo_db):
    """Doğrudan DB'ye tohum yazan/okuyan testler için `Session` (test kullanıcısıyla aynı DB).

    `expire_on_commit=False`: test `commit()` sonra da döndürdüğü kayıtları
    okuyabilsin. Commit TESTİN işi — rota o satırı görmek zorundaysa tohumdan
    sonra `db_oturumu.commit()` çağrılır (iki ayrı bağlantı; commit'lenmemiş
    satır rotaya görünmez).
    """
    from sqlalchemy.orm import Session
    with Session(depo_db, expire_on_commit=False) as oturum:
        yield oturum
        oturum.rollback()


# Kimlik kapısını GERÇEKTEN sınayan dosyalar için işaret (aşağıdaki `kullanici`
# fixture'ı bunu görünce override kurmaz): hesap testleri, kapı testleri ve
# E2E dosyaları — orada tarayıcı gerçek bir oturum çerezi taşıyor.
GERCEK_KIMLIK = "gercek_kimlik"

# "Anahtar yok" kapısını (services/kapilar.py `check_anahtar`, Faz 2 / 6) GERÇEKTEN
# sınayan dosyalar için işaret — aşağıdaki `_anahtar_kapisi` fixture'ı bunu
# görünce kapıyı yamalamaz: tests/test_platform_anahtari.py, tests/test_kota.py,
# tests/test_kimlik.py (iki kullanıcı, iki anahtar).
GERCEK_ANAHTAR = "gercek_anahtar"

# İşçinin filigranını (services/filigran.py, Faz 3 / 4) GERÇEKTEN sınayan dosyalar
# için işaret — aşağıdaki `_filigran_yamasi` bunu görünce `uygula`yı yamalamaz:
# tests/test_filigran.py ve tests/test_isci.py'nin filigran testleri.
GERCEK_FILIGRAN = "gercek_filigran"

TEST_KULLANICISI_EPOSTA = "test@example.com"


@pytest.fixture(autouse=True)
def kullanici(request: pytest.FixtureRequest):
    """Her test "oturum açmış" bir kullanıcıyla koşar (Faz 1 / 4) — DB'siz, çerezsiz.

    NEDEN VAR: 4. görev 47 rotayı kimlik kapısının arkasına aldı
    (`kimlik.aktif_kullanici` / `sayfa_kullanicisi`) ve ayar nesnesi artık
    KULLANICIYA göre kuruluyor (`ayar.ayarlar` → `<data_dir>/kullanicilar/<uuid>/…`).
    37 dosyanın 178 `TestClient` çağrısı bu iki şeyi bilmiyor: çerez
    taşımıyor, Postgres istemiyor ve `dizinler(output_dir=tmp_path)` deyip
    `tmp_path / "x.png"`e iddia yazıyor. Faz 0 / 4'te 66 yamanın tek
    fixture'a inmesinin aynısı: üç `dependency_overrides` girdisi, 178 çağrı
    değişmeden geçer —

      * `kimlik.aktif_kullanici` ve `kimlik.sayfa_kullanicisi` → geçici bir
        `Kullanici` nesnesi (DB satırı DEĞİL; `id` rastgele, testler arasında
        sızmaz). Override `kimlik.bagla`yı çağırıyor ki üretim yolunun bağladığı
        iki şey — `request.state.kullanici` ve dil zincirinin 3. halkası
        (`kullanici.dil`) — burada da bağlansın: bir test `kullanici.dil = "tr"`
        deyip sayfanın dilini ölçebiliyor (tests/test_dil.py).
      * `ayar.ayarlar` → `app.state.ayarlar` (paylaşılan yerleşim). Yani test
        kullanıcısının dizinleri TAM OLARAK `dizinler(...)`in gösterdiği yerler:
        eski iddialar aynen geçerli. Üretimdeki gibi `aktif_kullanici`ye
        BAĞIMLI (yukarıdaki override'a düşer): yoksa 42 rotada kullanıcı hiç
        bağlanmaz, `kullanici.dil` sayfada işler ama API hatasında işlemezdi
        (ölçüldü: `test_the_chain_reaches_route_errors_through_dil_aktif`).
        Kullanıcıya göre dizin türetimi (`kullanici_icin`) ve kapının kendisi
        bu override'ın ARKASINDA kalıyor ve onları ölçen dosyalar override'sız
        koşuyor (aşağıda).

    OPT-OUT `@pytest.mark.gercek_kimlik` (modül düzeyinde `pytestmark`):
    tests/test_hesap.py, tests/test_kimlik.py ve `tests/test_playwright_*.py`.
    Orada `TestClient`/tarayıcı GERÇEK çerez taşır, `veritabani` fixture'ı
    Postgres'i verir; E2E için `e2e_oturum` DB'ye kullanıcı yazıp çerezi
    tarayıcıya koyar (belge §4: "her testte formu doldurmak değil — form akışı
    `test_playwright_hesap.py`nin işi").

    DB KİPİ (Faz 1 / 5) — dosya `depo_db`yi istiyorsa (`usefixtures`): galeri,
    klasör, üretim ve bindirme rotaları artık `medya`/`klasorler` satırı yazıyor
    ve `kullanici_id` FK'sı sahte bir uuid'yi reddeder. O zaman test kullanıcısı
    aynı e-postayla GERÇEK bir satır olur (öncekisi silinir — CASCADE önceki
    testin medya/klasörlerini de götürür, her test temiz başlar; e-posta
    sabit kalır ki `TEST_KULLANICISI_EPOSTA` okuyan iddialar değişmesin) ve
    dördüncü override `db.oturum`u bu dosyanın motoruna bağlar: `TestClient(app)`
    `with`siz, lifespan'sız, motorsuz kalır. Override'ın commit/rollback kuralı
    `db.oturum`unkiyle aynı (dönüşte commit, istisnada rollback) — aksi hâlde
    rota testleri üretimde olmayan bir "yarım yazım" davranışını yeşil görürdü.

    `dependency_overrides` uygulama nesnesi üzerinde KÜRESEL — bir sonraki test
    başlamadan temizleniyor; kirli kalan bir override `gercek_kimlik`li dosyanın
    401 iddiasını sessizce geçirirdi.
    """
    if request.node.get_closest_marker(GERCEK_KIMLIK):
        yield None
        return
    import uuid

    import app as appmod
    from services import hesap, kimlik
    from services.tablolar import Kullanici

    test_kullanicisi = Kullanici(id=uuid.uuid4(), eposta=TEST_KULLANICISI_EPOSTA,
                                 parola_ozeti=None, dogrulandi_at=hesap.simdi(),
                                 is_admin=False, dil=None)

    yamalar: dict[Callable[..., Any], Callable[..., Any]] = {}
    if "depo_db" in request.fixturenames:
        from sqlalchemy import delete
        from sqlalchemy.orm import Session

        motor = request.getfixturevalue("depo_db")
        # `expire_on_commit=False`: nesne oturum kapanınca da `id`/`dil` taşısın
        # (rota `kullanici.id` okuyor, `POST /api/prefs` `kullanici.dil` yazıyor).
        with Session(motor, expire_on_commit=False) as s:
            s.execute(delete(Kullanici).where(Kullanici.eposta == TEST_KULLANICISI_EPOSTA))
            s.add(test_kullanicisi)
            s.commit()

        def _db_oturumu():
            with Session(motor) as oturum:
                try:
                    yield oturum
                except BaseException:
                    oturum.rollback()
                    raise
                else:
                    oturum.commit()

        yamalar[db.oturum] = _db_oturumu

    # `istek: Request` notu ŞART ve `Request` MODÜL düzeyinde ithal: FastAPI
    # notsuz bir parametreyi sorgu parametresi sayar; bu dosya `from __future__
    # import annotations` ile yazıldığı için not bir DİZE ve FastAPI onu
    # işlevin modül küreselinde çözüyor — yerel ithal görünmez, sonuç yine
    # "zorunlu sorgu parametresi" ve her istek 422 (ölçüldü, iki kez).
    async def _oturumlu(istek: Request):
        return kimlik.bagla(istek, test_kullanicisi)

    def _paylasilan(istek: Request, _kullanici=Depends(kimlik.aktif_kullanici)):
        return appmod.app.state.ayarlar

    yamalar.update({kimlik.aktif_kullanici: _oturumlu, kimlik.sayfa_kullanicisi: _oturumlu,
                    ayar.ayarlar: _paylasilan})
    appmod.app.dependency_overrides.update(yamalar)
    # KİRACI BAĞLAMI (Faz 2 / 7) iki yerde bağlanır ve ikisi de gerekli: rota tarafı
    # `kimlik.bagla` üzerinden (override onu çağırıyor; isteğin görevinde), TEST
    # tarafı BURADA — testin kendi iş parçacığında açtığı oturumlar (`db_oturumu`,
    # `Session(depo_db)`) TestClient'ın portal iş parçacığını görmez, kendi
    # bağlamını taşır. Takım süper kullanıcıyla koşuyor, politika burada görünmez
    # (FORCE süper kullanıcıyı kapsamaz); yalıtım ikinci rolle tests/test_rls.py'de.
    kiraci_jetonu = kiraci.bagla(kullanici_id=test_kullanicisi.id)
    try:
        yield test_kullanicisi
    finally:
        kiraci.coz(kiraci_jetonu)
        for anahtar in yamalar:
            appmod.app.dependency_overrides.pop(anahtar, None)


@pytest.fixture
def plan_pro(request: pytest.FixtureRequest, kullanici):
    """Test kullanıcısını `pro` yapar (Faz 3 / 3) — video rotalarını ölçen dosyalar için OPT-IN.

    NEDEN VAR: 3. görev ücretsiz planda video modellerini kapattı
    (`kapilar.check_plan` → 403 `err.plan_kapsamiyor`, K7) ve conftest'in
    test kullanıcısı ÜCRETSİZ (sütunun `server_default`ı — kasıtlı: kapının
    öntanımlı hâli kapalı olsun, plan testleri onu açıkça açsın). Video
    rotasının SÖZLEŞMESİNİ ölçen dosyalar (`test_video_route` 33 çağrı,
    `test_isler_route`, `test_uretim_kapilar`) planı değil rotayı sınıyor; her
    birine "kullanıcıyı pro yap" satırı yazmak yerine tek fixture,
    `pytestmark = pytest.mark.usefixtures("depo_db", "plan_pro")`. Kapının
    kendisi tests/test_planlar.py'de ölçülür (free + video → 403).

    Yazım DB'ye (`UPDATE kullanicilar SET plan`; `plan` bakiye değil — defterin
    tek-yazar bekçisi `bakiye`/`kredi_hareketleri` içindir) ve nesneye: kapı
    planı DB'den okur (`defter.plan_oku`), nesne ise `kullanici.plan` okuyan
    bir test için. `depo_db`siz dosyada yalnız nesne yazılır.
    """
    kullanici.plan = "pro"
    if "depo_db" in request.fixturenames:
        from sqlalchemy import update
        from sqlalchemy.orm import Session

        from services.tablolar import Kullanici

        with Session(request.getfixturevalue("depo_db")) as s:
            s.execute(update(Kullanici).where(Kullanici.id == kullanici.id).values(plan="pro"))
            s.commit()
    return kullanici


@pytest.fixture(autouse=True)
def _anahtar_kapisi(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Her test "seçili modelin anahtarı var" öncülüyle koşar (Faz 2 / 6) — kapı yamalı.

    NEDEN VAR: 6. görev dört üretim rotasına ve yeniden gönderime "anahtar
    yok → 409, iş doğmaz" kapısını koydu (`kapilar.check_anahtar`). 26 test
    dosyasının üretim çağrıları anahtar bilmiyor: sağlayıcıyı yamalıyor, DB'de
    kimlik satırı yazmıyor, ortamda platform anahtarı yok — hepsi 409 alırdı.
    `kullanici` fixture'ının kimlik kapısı için yaptığı şeyin ikizi: yaygın
    çağrı yerleri değişmeden geçer, kapının KENDİSİNİ ölçen dosyalar
    `@pytest.mark.gercek_anahtar` ile yamasız koşar. Yama `"kullanici"`
    döndürür: o satırlar günlük kredi toplamına girmez (platform parası
    değil) ve `anahtar_kaynagi` CHECK'ten geçer.

    ORTAMA ANAHTAR EKLEMEK seçilmedi (ölçüldü): her sağlayıcıya sahte bir
    platform anahtarı vermek `GET /api/settings`in `providers`ını her yerde
    `true` yapar ve "kurulu değil" ölçen 30+ iddiayı kırardı — kapıyı
    yamalamak ise yalnız kapıya dokunur.
    """
    if request.node.get_closest_marker(GERCEK_ANAHTAR):
        yield
        return
    from services import kapilar
    monkeypatch.setattr(kapilar, "check_anahtar", lambda *a, **k: "kullanici")
    yield


@pytest.fixture(autouse=True)
def _filigran_yamasi(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Her test "filigran bindirme kimliktir" öncülüyle koşar (Faz 3 / 4) — `filigran.uygula` yamalı.

    NEDEN VAR: 4. görev işçiye `_uret` → `_yaz` arasında ücretsiz planın
    görselini filigranlama adımını koydu ve conftest'in test kullanıcısı
    ÜCRETSİZ (sütunun `server_default`ı; `plan_pro`nun gerekçesi). İşçiyi
    koşturan dosyalar (tests/test_isci.py, tests/test_isler_route.py, E2E
    `test_playwright_isler.py`) sağlayıcıyı 24 baytlık sahte bir "PNG" ile
    yamalıyor (`b"\x89PNG\r\n\x1a\n" + …`) ve depoya yazılanı o baytla
    karşılaştırıyor: gerçek `uygula` o baytı görsel diye açamaz
    (`GorselIslenemedi`) ve 40'tan çok test kırmızıya dönerdi. `kullanici` /
    `_anahtar_kapisi` yamalarının ikizi: yaygın çağrı yerleri değişmeden
    geçer, adımın KENDİSİNİ ölçen dosyalar `@pytest.mark.gercek_filigran`
    ile yamasız koşar ve gerçek bir PNG verir.

    Yama İŞLEVİ değil KARARI bırakıyor: `_filigranlanir` gerçek koşar, yani
    ücretsiz kullanıcının kaydı bu yamayla da `filigranli=True` taşır —
    plan/tür kararı her işçi testinde ölçülü kalır, yalnız piksel işi atlanır.
    """
    if request.node.get_closest_marker(GERCEK_FILIGRAN):
        yield
        return
    from services import filigran
    monkeypatch.setattr(filigran, "uygula", lambda png, **k: png)
    yield


class E2EOturum:
    """`e2e_oturum`un döndürdüğü şey: DB'de gerçek bir kullanıcı + oturum satırı, ham jeton elde."""

    def __init__(self, kullanici_id, eposta: str, jeton: str, motor=None):
        self.kullanici_id = kullanici_id
        self.eposta = eposta
        self.jeton = jeton
        self._motor = motor

    def db(self):
        """Bu kullanıcının DB'sine `Session` — E2E'nin galeri/klasör TOHUMU için (Faz 1 / 5).

        Sunucu `medya`/`klasorler`i DB'den okuyor; `storage.save`/`folders.create`
        ile kullanıcı dizinine yazılan manifest artık görünmez. Kullanımı:
        `with oturum.db() as db: depo_klasor.olustur(db, oturum.kullanici_id, …); db.commit()`.
        """
        from sqlalchemy.orm import Session
        return Session(self._motor, expire_on_commit=False)

    def cerez(self, sayfa_veya_baglam, taban: str) -> None:
        """Oturum çerezini tarayıcıya koyar — `page` ya da `BrowserContext` alır.

        `url` ile: Playwright alanı/yolu oradan türetir; `secure` düz http'de
        `False` kalır ve tarayıcı çerezi loopback'e taşır. Sunucu bayrağa
        bakmaz, jetona bakar.
        """
        from services import cerez as cerez_modulu
        baglam = getattr(sayfa_veya_baglam, "context", sayfa_veya_baglam)
        baglam.add_cookies([{"name": cerez_modulu.OTURUM_CEREZI, "value": self.jeton,
                             "url": taban}])

    def ayarlar(self) -> ayar.Ayarlar:
        """Bu kullanıcının dizinleri (`ayar.Ayarlar.kullanici_icin`), AÇILMIŞ hâlde."""
        import app as appmod
        ozel = appmod.app.state.ayarlar.kullanici_icin(self.kullanici_id)
        os.makedirs(ozel.output_dir, exist_ok=True)
        os.makedirs(ozel.assets_dir, exist_ok=True)
        return ozel


@pytest.fixture
def e2e_oturum(veritabani: str, tmp_path, dizinler):
    """E2E için oturum: DB'ye doğrulanmış kullanıcı + oturum yazar, çerezi tarayıcıya verir.

    Kullanımı: `oturum = e2e_oturum()` (isteğe bağlı `dil="tr"`), sonra
    `page.goto`dan ÖNCE `oturum.cerez(page, taban)`. Sunucu aynı süreçte
    (`ServerThread`) ve `DATABASE_URL`i `veritabani` fixture'ı verdi, yani
    kapı GERÇEK: çerezsiz sayfa 302 `/giris`e giderdi.

    `data_dir` burada `tmp_path`e çekiliyor ve bu ŞART: kullanıcı dizinleri
    `<data_dir>/kullanicilar/<uuid>/` altında açılıyor ve dev'de `data_dir`
    REPO KÖKÜ — fixture'sız bir E2E testi depoya `kullanicilar/` bırakırdı
    (2. görevin ölçtüğü sızıntı sınıfı). Dosya tohumlayan testler dizini
    `oturum.ayarlar().output_dir`den okur, `tmp_path / "output"`tan değil.
    """
    import uuid

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from services import hesap
    from services.tablolar import Kullanici

    dizinler(data_dir=str(tmp_path))
    motor = create_engine(veritabani)

    def _ac(dil: str | None = None) -> E2EOturum:
        eposta = f"e2e-{uuid.uuid4().hex[:8]}@example.com"
        an = hesap.simdi()
        with Session(motor) as db:
            k = Kullanici(eposta=eposta, parola_ozeti=None, dogrulandi_at=an, dil=dil)
            db.add(k)
            db.flush()
            jeton = hesap.oturum_ac(db, k, None, "e2e", an)
            kullanici_id = k.id
            db.commit()
        return E2EOturum(kullanici_id, eposta, jeton, motor)

    yield _ac
    motor.dispose()


@pytest.fixture
def dizinler(monkeypatch: pytest.MonkeyPatch):
    """Uygulamanın veri dizinlerini bu test süresince YÖNLENDİRİR (Faz 0 / Adım 4).

    Kullanımı: `dizinler(output_dir=str(tmp_path))`,
    `dizinler(output_dir=…, assets_dir=…)`, `dizinler(static_dir=…)`,
    `dizinler(data_dir=…)`. Verilmeyen alan olduğu gibi kalır; dönen `Ayarlar`
    nesnesinden yollar okunabilir.

    NEDEN TEK FİXTURE: Adım 4'e kadar 66 test `monkeypatch.setattr(appmod,
    "OUTPUT_DIR", …)` yazıyordu ve router'lar o adı `sys.modules["app"]`
    üzerinden okuyordu (services/yollar.py, artık yok). Dizinler artık
    `app.state.ayarlar`daki donmuş `Ayarlar` nesnesinde; rotalar onu
    `Depends(ayar.ayarlar)` ile alıyor, ara katman ve lifespan `app.state`ten
    okuyor. Yani yamanın TEK hedefi var ve o hedef burada — bir testin başka
    bir yolla dizin değiştirmesi (`paths`i yamalamak gibi) rotaya ULAŞMAZ.

    NEDEN FABRİKA (çağrılabilir döndürüyor), sabit yerleşim DEĞİL: mevcut
    testlerin yarısı `output_dir=tmp_path`, öteki yarısı `tmp_path/"output"`
    yerleşimini kullanıyor ve dosya yollarına iddia yazıyor
    (`tmp_path / "hata.log"`, `tmp_path / f"{id}.png"`). Tek bir yerleşim
    dayatmak o iddiaların hepsini elle yeniden yazdırırdı; fabrika eski
    yamayı bire bir karşılıyor.

    NEDEN `dataclasses.replace` + `monkeypatch.setattr(app.state, …)`:
    nesne donmuş (paylaşılan durum yanlışlıkla değişmesin), kopya alınıyor;
    `monkeypatch` testin sonunda eski nesneyi geri koyuyor. Art arda iki
    çağrı birikir (ikincisi birincinin kopyasından türer) ve LIFO geri alma
    sırayı doğru kapatır.

    `app` BURADA ithal ediliyor (modül başında değil): conftest'in kendisi
    `import app` yaparsa her test dosyası — `paths`i tek başına sınayanlar
    dâhil — bileşim kökünü ve 60 modülü yüklemiş olurdu.
    """
    import dataclasses

    import app as appmod
    from services import dosya

    def _yonlendir(**alanlar: str) -> ayar.Ayarlar:
        yeni = dataclasses.replace(appmod.app.state.ayarlar, **alanlar)
        monkeypatch.setattr(appmod.app.state, "ayarlar", yeni)
        # `data_dir` yönlendirilince DEPO da oraya (Faz 2 / 4): `app.state.dosya`
        # ithal anında `YerelDepo(paths.data_dir())` kuruldu ve dev'de o kök
        # REPO KÖKÜ. Üretim rotaları girdi nesnelerini KÖK GÖRELİ anahtarla
        # yazıyor (`kullanicilar/<uuid>/isler/…`); depo yerinde kalsa E2E ve
        # `uret_ve_bitir` testleri depoya `kullanicilar/` bırakırdı (Faz 1 /
        # 2'nin ölçtüğü sızıntı sınıfı). Yalnız yerel depo: nesne depo
        # yamalanmış bir testin kendi kararı.
        if "data_dir" in alanlar and isinstance(appmod.app.state.dosya, dosya.YerelDepo):
            monkeypatch.setattr(appmod.app.state, "dosya", dosya.YerelDepo(alanlar["data_dir"]))
        return yeni

    return _yonlendir


class _PaylasilanYerlesim(ayar.Ayarlar):
    """`kullanici_icin` KENDİNİ döndüren ayar nesnesi — `uret_ve_bitir`in işçiye verdiği yerleşim.

    `kullanici` fixture'ının `ayar.ayarlar` override'ının işçi tarafı: rota
    testleri `dizinler(output_dir=tmp_path)` deyip `tmp_path / f"{id}.png"`e
    iddia yazıyor ve rota o dizine yazıyordu. Üretim artık işçide
    (`isci._yaz` → `ayarlar.kullanici_icin(uid).output_dir`); işçi de aynı
    paylaşılan dizine yazsın ki eski iddialar aynen dursun. Kullanıcıya göre
    dizin türetimi override'ın ARKASINDA kalıyor — onu ölçen dosyalar
    (`test_kimlik`, `test_isci`) gerçek `Ayarlar` ile koşuyor.
    """

    def kullanici_icin(self, kullanici_id) -> ayar.Ayarlar:
        return self


class IsSonucu:
    """`uret_ve_bitir`in döndürdüğü şey: eski `TestClient` yanıtının ŞEKLİNDE, kuyruk üstünden.

    Rota 202 + iş döndürüyor, sonucu işçi yazıyor (Faz 2 / 4). 104 rota testi
    `r = c.post(...); r.status_code == 200; r.json()["images"]` deyimiyle
    yazılmıştı; bu nesne o üç iddiayı aynen karşılar ki eski testler tek
    satır (`c.post` → `uret_ve_bitir(c, …)`) değişerek dursun:

      * `status_code` — iş `bitti` ise **200** (eski mutlu yol), `hata` ise
        **502** (eski "sağlayıcı hatası → 502" eşlemesi; `json()["detail"]`
        işin `hata` metni). POST 202 vermediyse (422/413/404/429) GERÇEK
        yanıt olduğu gibi döner, bu sınıf hiç kurulmaz.
      * `json()` — `{"images": [kayıt, …]}` görsel türlerinde, `{"videos": …}`
        video türlerinde (rotanın eski anahtar kararı, `test_video_route`).
        Kayıtlar `GET /api/history`nin döktüğü sözlükler (`depo_medya.bul`),
        `sonuc.medya` sırasıyla.
      * `is` — işin son hâli (`kuyruk._json`), yeni iddialar için.
    """

    def __init__(self, is_: dict, kayitlar: list[dict]):
        self.is_ = is_
        self.kayitlar = kayitlar
        self.status_code = 200 if is_["durum"] == "bitti" else 502
        self.text = f"is {is_['id']} {is_['durum']}: {is_.get('hata')!r}"

    def json(self) -> dict:
        if self.is_["durum"] != "bitti":
            return {"detail": self.is_.get("hata") or ""}
        anahtar = "videos" if self.is_["tur"] in ("video", "animate") else "images"
        return {anahtar: self.kayitlar}


@pytest.fixture
def uret_ve_bitir(request: pytest.FixtureRequest, tmp_path, dizinler):
    """POST üretim rotası → 202 → `isci.tek_tur` → sonuç kayıtları (Faz 2 / 4; belge §4'ün test deseni).

    Kullanımı: `r = uret_ve_bitir(c, "/api/generate", json={...})` — `c.post`un
    yerine, aynı argümanlarla. Dönen `IsSonucu` eski yanıtın şeklinde (üstte).
    Sağlayıcı testin yaması (`ac.generate`, `providers.*`); işçi onu
    `providers` üzerinden çağırır, yani eski yamalar aynen işler.

    `depo_db` ŞART (modülün `pytestmark`ı): işçi `Session`ı bu dosyanın
    motorundan açılır (`tek_tur(db, …)` alım için, yazım `db.get_bind()`ten).
    `data_dir` `tmp_path`e çekilir (girdi nesneleri `kullanicilar/<uuid>/isler/`
    altına, depo da oraya — `dizinler`in kuralı); `output_dir` testin
    bıraktığı yerde kalır ve işçi ORAYA yazar (`_PaylasilanYerlesim`).
    """
    import dataclasses

    from sqlalchemy.orm import Session

    import app as appmod
    from services import depo_medya, isci, kuyruk, tablolar

    motor = request.getfixturevalue("depo_db")
    dizinler(data_dir=str(tmp_path))

    def _calistir(client, yol: str, **istek) -> Any:
        cevap = client.post(yol, **istek)
        if cevap.status_code != 202:
            return cevap
        is_id = cevap.json()["is"]["id"]
        yerlesim = _PaylasilanYerlesim(**dataclasses.asdict(appmod.app.state.ayarlar))
        with Session(motor) as db:
            kostu = isci.tek_tur(db, appmod.app.state.dosya, ayarlar=yerlesim)
            assert kostu, "kuyrukta iş yoktu — 202 döndü ama satır commit'lenmedi mi?"
        with Session(motor) as db:
            satir = db.get(tablolar.Is, uuid.UUID(is_id))
            assert satir is not None
            is_ = kuyruk._json(satir)
            medya = cast(list[str], (satir.sonuc or {}).get("medya") or [])
            kayitlar = [k for k in (depo_medya.bul(db, satir.kullanici_id, m) for m in medya)
                        if k is not None]
        return IsSonucu(is_, kayitlar)

    return _calistir


@pytest.fixture
def fake_composite():
    """composite.composite_logo yerine geçer: girdiyi olduğu gibi döndürür.

    tests/test_folders.py ve tests/test_palette_route.py'de birebir aynı
    (`_fake_composite`) olarak duruyordu — buraya taşındı.
    """
    def _fake_composite(base_path, **kwargs) -> bytes:
        # Rota kaynağı depodan BAYT olarak okuyup `io.BytesIO` veriyor (Faz 2 / 2);
        # dondurulmuş kabuk hâlâ yol verir — ikisi de geçsin.
        if hasattr(base_path, "read"):
            return base_path.read()
        with open(base_path, "rb") as f:
            return f.read()
    return _fake_composite


def tr(anahtar: str) -> str:
    """Bir çeviri anahtarının TÜRKÇE metni — arayüz metnine bakan testler için.

    Çoklu dil desteği (v0.21) arayüz metinlerini `static/*.js` ve
    `static/index.html` içinden `bundled/i18n/*.json`a taşıdı. Bunu ölçen
    testlerin İKİ farklı sorusu var ve ikisi ayrı yere bakmalı:

      · "Bu dal DOĞRU cümleyi mi seçiyor?" → betikte ANAHTARI ara
        (`t("gate.arena_no_edit")`). Metin değişse bile dal aynı kalır, yani
        test cümlenin yazımına değil KARARA bakmış olur.
      · "Cümle kullanıcıya şunu SÖYLÜYOR mu?" → metni buradan al. Anahtarın
        kendisini kopyalamak yetmezdi: sözlükten silinmiş bir anahtar
        `i18n.t` tarafından sessizce kendisine düşer ve test yine geçerdi.

    İkincisi için doğrudan `i18n.t` çağrılabilirdi; bu sarmalayıcı ADIYLA
    hangi soruyu sorduğunu söylüyor ve testlerin dile bağımlılığını tek bir
    yerde topluyor.
    """
    import i18n
    metin = i18n.t(anahtar, "tr")
    assert metin != anahtar, f"sözlükte yok: {anahtar}"
    return metin


def duz_rotalar(uygulama) -> list[tuple[str, str]]:
    """Çalışan uygulamanın (YÖNTEM, yol) çiftleri — ağaç değil DÜZ liste.

    NEDEN VAR (Faz 0 / Adım 5): FastAPI 0.137 `include_router`ı rotaları
    kopyalamayı bıraktı; `app.routes` artık takılan her router için tek bir
    `_IncludedRouter` düğümü taşıyor ve asıl rotalar onun
    `original_router.routes` altında (iç içe include'larda daha da derinde).
    0.115'te `app.routes` düz bir listeydi; onu doğrudan sayan iki test
    (`test_app_bolme`, `test_arena_onyuz`) 0.141'de yalnız `/docs` ailesini
    görüp kırmızıya döndü. Yürüyüş TEK yerde dursun ki bir sonraki iç yapı
    değişikliği iki testi ayrı ayrı değil burayı kırsın.

    Ön ek `include_context.prefix`ten toplanıyor: bugün `app.py` öneksiz
    takıyor, ama öneksiz varsayan bir yürüyüş ilk `prefix=` ile sessizce
    yanlış yol üretirdi. Belge rotaları (`/docs`, `/redoc`, `/openapi.json`)
    ve `Mount`lar (yöntemsiz) çağıranın süzgecine bırakılıyor.
    """
    bulunan: list[tuple[str, str]] = []

    def _yuru(rotalar, on_ek: str) -> None:
        for r in rotalar:
            ic = getattr(r, "original_router", None)
            if ic is not None:                      # FastAPI ≥ 0.137 düğümü
                baglam = getattr(r, "include_context", None)
                _yuru(ic.routes, on_ek + (getattr(baglam, "prefix", "") or ""))
                continue
            for yontem in getattr(r, "methods", None) or ():
                bulunan.append((yontem, on_ek + r.path))

    _yuru(uygulama.routes, "")
    return bulunan
