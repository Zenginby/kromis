"""Güncelleme kontrolünün ÜÇ sözleşmesi (bkz. guncelleme.py başlığı).

Üçü de ihlal edildiğinde zarar SESSİZ olur — kırmızı bir test olmadan hiçbiri
fark edilmez:

  1. exception sızdırırsa → ayarlar paneli açılmaz (çevrimdışı kullanıcıda),
  2. istek yolunu bekletirse → panel her açılışta saniyelerce donar,
  3. tercihe uymazsa → uygulama kullanıcının haberi olmadan ağa çıkar.
"""
from __future__ import annotations

import json
import os
import re
import time

import pytest

import guncelleme
import version


@pytest.fixture(autouse=True)
def _bayragi_sifirla():
    """Modül düzeyindeki "tazeleme koşuyor" bayrağı testler arasında sızmasın.

    conftest.py'deki Android ortam-değişkeni guard'ıyla aynı sınıf: küresel bir
    durumu bir test bırakırsa SONRAKİ testler sahte davranır ve hata mesajı
    kaynağa hiç işaret etmez.
    """
    yield
    guncelleme._KOSUYOR = False


@pytest.fixture
def veri_dizini(tmp_path):
    return str(tmp_path)


def _onbellek_yaz(dizin: str, veri: dict) -> None:
    with open(os.path.join(dizin, guncelleme.ONBELLEK_DOSYASI), "w", encoding="utf-8") as f:
        json.dump(veri, f)


# --------------------------------------------------------------------------
# Sürüm karşılaştırması
# --------------------------------------------------------------------------

def test_surum_karsilastirmasi_sayisal():
    """Sözlük sırası '0.10.0' < '0.9.0' derdi ve uygulama onuncu yama
    sürümünden sonra güncellemeleri görmeyi SESSİZCE bırakırdı."""
    assert guncelleme.surum_daha_yeni("0.10.0", "0.9.0") is True
    assert guncelleme.surum_daha_yeni("0.9.0", "0.10.0") is False


def test_ayni_surum_yeni_sayilmaz():
    assert guncelleme.surum_daha_yeni("0.4.2", "0.4.2") is False


def test_v_oneki_tolere_edilir():
    """GitHub `tag_name`'i 'v0.5.0' döndürüyor, APP_VERSION öneksiz."""
    assert guncelleme.surum_daha_yeni("v0.5.0", "0.4.2") is True


def test_bozuk_surum_metni_patlatmaz():
    """Yayın etiketi bir gün 'sürüm-yok' olursa uygulama çökmemeli."""
    assert guncelleme.surum_daha_yeni("sürüm-yok", "0.4.2") is False
    assert guncelleme.surum_daha_yeni(None, "0.4.2") is False


# --------------------------------------------------------------------------
# 3. sözleşme — kullanıcı kapatabilir
# --------------------------------------------------------------------------

def test_izin_yoksa_aga_hic_cikilmaz(veri_dizini, monkeypatch):
    def patlat():
        raise AssertionError("izin kapalıyken ağa çıkıldı")

    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda *a, **k: patlat())
    assert guncelleme.bilgi(veri_dizini, izin=False) is None


# --------------------------------------------------------------------------
# 2. sözleşme — istek yolu beklemez
# --------------------------------------------------------------------------

def test_bilgi_ag_cagrisini_beklemez(veri_dizini, monkeypatch):
    """`bilgi()` yalnız önbelleğe bakar; tazelemeyi arka plana atar.

    Bu iddia olmadan biri `_sor()`'u doğrudan `bilgi()` içine taşıyabilir ve
    fark yalnız yavaş bir panel olarak, ölçülmeden görünürdü.
    """
    cagrildi = []
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: cagrildi.append(d))

    sonuc = guncelleme.bilgi(veri_dizini)

    assert sonuc is None                    # önbellek boş → gösterecek bir şey yok
    assert cagrildi == [veri_dizini]        # ama tazeleme başlatıldı


def test_taze_onbellek_yeniden_sorulmaz(veri_dizini, monkeypatch):
    """TTL dolmadan GitHub'a tekrar gitmek anonim istek sınırını (saatte 60,
    IP başına) gereksizce yakardı."""
    _onbellek_yaz(veri_dizini, {"zaman": time.time(), "surum": version.APP_VERSION})
    cagrildi = []
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: cagrildi.append(d))

    guncelleme.bilgi(veri_dizini)

    assert cagrildi == []


def test_bayat_onbellek_tazelenir(veri_dizini, monkeypatch):
    eski = time.time() - guncelleme.TTL_SANIYE - 1
    _onbellek_yaz(veri_dizini, {"zaman": eski, "surum": version.APP_VERSION})
    cagrildi = []
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: cagrildi.append(d))

    guncelleme.bilgi(veri_dizini)

    assert cagrildi == [veri_dizini]


def test_ayni_anda_tek_tazeleme_kosar(veri_dizini, monkeypatch):
    """Ayarlar panelini üst üste açan kullanıcı her açılışta yeni bir iş
    parçacığı doğurmasın."""
    baslatilan = []
    monkeypatch.setattr(guncelleme.threading, "Thread",
                        lambda **kw: type("T", (), {"start": lambda self: baslatilan.append(1)})())

    guncelleme._tazeleme_baslat(veri_dizini)
    guncelleme._tazeleme_baslat(veri_dizini)

    assert len(baslatilan) == 1


# --------------------------------------------------------------------------
# 1. sözleşme — asla patlamaz
# --------------------------------------------------------------------------

def test_ag_hatasi_none_dondurur(monkeypatch, tmp_path):
    """Çevrimdışı kullanım bu uygulamanın normal hâli: üretim dışında her şey
    yerelde koşuyor."""
    import httpx

    def patla(*a, **k):
        raise httpx.ConnectError("ağ yok")

    monkeypatch.setattr(httpx, "get", patla)
    monkeypatch.setattr(guncelleme.paths, "data_dir", lambda: str(tmp_path))

    assert guncelleme._sor() is None


def test_bozuk_json_none_dondurur(monkeypatch, tmp_path):
    import httpx

    class SahteYanit:
        def raise_for_status(self): pass
        def json(self): raise ValueError("bozuk JSON")

    monkeypatch.setattr(httpx, "get", lambda *a, **k: SahteYanit())
    monkeypatch.setattr(guncelleme.paths, "data_dir", lambda: str(tmp_path))

    assert guncelleme._sor() is None


def test_etiketsiz_yayin_none_dondurur(monkeypatch, tmp_path):
    import httpx

    class SahteYanit:
        def raise_for_status(self): pass
        def json(self): return {"html_url": "x"}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: SahteYanit())
    monkeypatch.setattr(guncelleme.paths, "data_dir", lambda: str(tmp_path))

    assert guncelleme._sor() is None


def test_bozuk_onbellek_dosyasi_patlatmaz(veri_dizini, monkeypatch):
    """Kullanıcının veri klasöründeki bozuk bir dosya uygulamayı açılamaz hâle
    getirmemeli — prefs.py'deki "okuma yolu hoşgörülü" duruşunun aynısı."""
    with open(os.path.join(veri_dizini, guncelleme.ONBELLEK_DOSYASI), "w",
              encoding="utf-8") as f:
        f.write("{bozuk")
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: None)

    assert guncelleme.bilgi(veri_dizini) is None


def test_basarisiz_kontrol_de_damgalanir(veri_dizini, monkeypatch):
    """Yoksa ağı olmayan bir makinede HER `/api/settings` çağrısı yeni bir iş
    parçacığı başlatırdı. Damga `son_deneme` — `zaman` DEĞİL: bkz. aşağısı."""
    monkeypatch.setattr(guncelleme, "_sor", lambda: None)

    guncelleme._tazele(veri_dizini)

    with open(os.path.join(veri_dizini, guncelleme.ONBELLEK_DOSYASI), encoding="utf-8") as f:
        kayit = json.load(f)
    assert float(kayit["son_deneme"]) > 0
    assert "zaman" not in kayit


def test_a_failed_check_does_not_cost_a_whole_day(veri_dizini, monkeypatch):
    """ASIL İDDİA — 2026-09-12'de ölçülen kusur.

    Başarısızlık `zaman`ı damgalıyordu, yani TEK bir zaman aşımı kullanıcıyı
    24 saat kör bırakıyordu. Telefonda bu masaüstünden çok daha sık (5 sn'lik
    zaman aşımı + mobil veri) ve sonucu "bildirim hiç gelmiyor"dan ayırt
    edilemez.
    """
    monkeypatch.setattr(guncelleme, "_sor", lambda: None)
    guncelleme._kontrol_et(veri_dizini)                  # ağ yok: başarısız tur

    cagrildi = []
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: cagrildi.append(d))

    # Hata geri çekilmesi dolar dolmaz yeniden denenmeli — 24 saat DEĞİL.
    # Değer ÖNCE yakalanıyor: `guncelleme.time` testin `time`ıyla AYNI modül
    # nesnesi, yani lambda içindeki `time.time()` yamanın kendisini çağırırdı.
    ileri = time.time() + guncelleme.HATA_TTL_SANIYE + 1
    monkeypatch.setattr(guncelleme.time, "time", lambda: ileri)
    guncelleme.bilgi(veri_dizini)

    assert cagrildi == [veri_dizini]
    assert guncelleme.HATA_TTL_SANIYE < guncelleme.TTL_SANIYE


def test_a_failed_check_is_not_retried_immediately(veri_dizini, monkeypatch):
    """Geri çekilmenin ÖBÜR yarısı: hata da olsa arka arkaya sorulmuyor.
    Bu, damgalamanın doğuş sebebi ve kısaltma onu geçersiz kılmamalı."""
    monkeypatch.setattr(guncelleme, "_sor", lambda: None)
    guncelleme._kontrol_et(veri_dizini)

    cagrildi = []
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: cagrildi.append(d))
    guncelleme.bilgi(veri_dizini)

    assert cagrildi == []


def test_a_successful_check_still_holds_for_a_day(veri_dizini, monkeypatch):
    """Kısaltma YALNIZ hataya ait: başarılı cevap 24 saat taze sayılmaya devam
    ediyor, yoksa anonim istek sınırı (saatte 60, IP başına) boşuna yakılırdı."""
    monkeypatch.setattr(guncelleme, "_sor",
                        lambda: {"surum": "99.0.0", "url": guncelleme.YAYIN_SAYFASI})
    guncelleme._kontrol_et(veri_dizini)

    cagrildi = []
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: cagrildi.append(d))
    # Değer ÖNCE yakalanıyor: `guncelleme.time` testin `time`ıyla AYNI modül
    # nesnesi, yani lambda içindeki `time.time()` yamanın kendisini çağırırdı.
    ileri = time.time() + guncelleme.HATA_TTL_SANIYE + 1
    monkeypatch.setattr(guncelleme.time, "time", lambda: ileri)
    guncelleme.bilgi(veri_dizini)

    assert cagrildi == []


def test_an_old_failure_stamp_is_not_mistaken_for_an_answer(veri_dizini, monkeypatch):
    """GÖÇ KAPISI: eski düzende başarısız kontrol de `zaman` yazıyordu ve
    diskte "damgalı ama cevapsız" kayıtlar duruyor. O damga başarı sayılsaydı
    düzeltilen kusur bir tur daha yaşanırdı."""
    _onbellek_yaz(veri_dizini, {"zaman": time.time()})   # eski biçim: surum YOK
    cagrildi = []
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: cagrildi.append(d))

    guncelleme.bilgi(veri_dizini)

    assert cagrildi == [veri_dizini]


def test_a_corrupt_timestamp_does_not_raise(veri_dizini, monkeypatch):
    """1. sözleşme ÖNBELLEK yolunda da geçerli: elle bozulmuş bir damga
    `bilgi()`den ValueError olarak çıkıp `/api/settings`i 500'e düşürürdü."""
    _onbellek_yaz(veri_dizini, {"zaman": "dün", "son_deneme": None, "surum": "99.0.0"})
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: None)

    assert guncelleme.bilgi(veri_dizini)["surum"] == "99.0.0"


# --------------------------------------------------------------------------
# Sonucun kendisi
# --------------------------------------------------------------------------

def test_yeni_surum_varsa_bilgi_doner(veri_dizini, monkeypatch):
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: None)
    yayin = guncelleme.GECERLI_URL_ONEKI + "releases/tag/v99.0.0"
    _onbellek_yaz(veri_dizini, {
        "zaman": time.time(), "surum": "99.0.0", "url": yayin,
    })

    sonuc = guncelleme.bilgi(veri_dizini)

    assert sonuc == {"surum": "99.0.0", "url": yayin}


def test_guncel_surumde_bilgi_yok(veri_dizini, monkeypatch):
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: None)
    _onbellek_yaz(veri_dizini, {"zaman": time.time(), "surum": version.APP_VERSION})

    assert guncelleme.bilgi(veri_dizini) is None


def test_url_yoksa_yayin_sayfasina_dusulur(veri_dizini, monkeypatch):
    """Bağlantısız bir bildirim kullanıcıyı çıkmaza sokar: "yeni sürüm var" der
    ama nereden alacağını söylemez."""
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: None)
    _onbellek_yaz(veri_dizini, {"zaman": time.time(), "surum": "99.0.0"})

    assert guncelleme.bilgi(veri_dizini)["url"] == guncelleme.YAYIN_SAYFASI


# --------------------------------------------------------------------------
# Bağlantının doğrulanması
# --------------------------------------------------------------------------

def test_yabanci_url_reddedilir(monkeypatch, tmp_path):
    """Cevaptaki `html_url` arayüzde tıklanabilir bir bağlantı oluyor
    (`static/settings.js` → `#settings-update-link.href`).

    Risk soyut değil: `follow_redirects=True` bilinçle açık ve v0.5.3'te depo
    taşındığında eski hesap adı boşaldı. O adı alan biri isteği kendi
    `releases/latest`ine yönlendirebilir; doğrulama olmadan uygulamanın "indir"
    bağlantısı yabancı bir yayın sayfasını gösterirdi.
    """
    import httpx

    class SahteYanit:
        def raise_for_status(self): pass
        def json(self): return {
            "tag_name": "v99.0.0",
            "html_url": "https://github.com/saldirgan/kromis/releases/tag/v99.0.0",
        }

    monkeypatch.setattr(httpx, "get", lambda *a, **k: SahteYanit())
    monkeypatch.setattr(guncelleme.paths, "data_dir", lambda: str(tmp_path))

    assert guncelleme._sor() == {"surum": "99.0.0", "url": guncelleme.YAYIN_SAYFASI}


def test_kendi_deponun_urli_oldugu_gibi_gecer(monkeypatch, tmp_path):
    """Doğrulama, işe yarayan hâli de geçirmek ZORUNDA: yoksa bağlantı her
    sürümde `releases/latest`e düşer ve kullanıcı çıkan sürümün notlarını
    değil, en yenisinin sayfasını görür."""
    import httpx

    dogru = guncelleme.GECERLI_URL_ONEKI + "releases/tag/v99.0.0"

    class SahteYanit:
        def raise_for_status(self): pass
        def json(self): return {"tag_name": "v99.0.0", "html_url": dogru}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: SahteYanit())
    monkeypatch.setattr(guncelleme.paths, "data_dir", lambda: str(tmp_path))

    assert guncelleme._sor()["url"] == dogru


def test_onbellekteki_yabanci_url_de_reddedilir(veri_dizini, monkeypatch):
    """Önbellek dosyası sürüm yükseltmelerini AŞARAK kalıyor: doğrulama
    eklenmeden önce yazılmış (ya da elle bozulmuş) bir kayıt okuma yolundan
    girebilir."""
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: None)
    _onbellek_yaz(veri_dizini, {
        "zaman": time.time(), "surum": "99.0.0",
        "url": "https://github.com/saldirgan/kromis/releases/latest",
    })

    assert guncelleme.bilgi(veri_dizini)["url"] == guncelleme.YAYIN_SAYFASI


# --------------------------------------------------------------------------
# Elle kontrol — `simdi_kontrol_et`
# --------------------------------------------------------------------------

def test_a_manual_check_bypasses_the_cache_window(veri_dizini, monkeypatch):
    """BU UCUN VAR OLMA SEBEBİ. Önbellek TAZE ama cevabı bayat: yayın hızı
    kontrol aralığından yüksekse (ölçüldü: ~7.7 saatte bir yayın, 24 saatte bir
    kontrol) `bilgi()` GitHub'a hiç sormaz ve kullanıcının elinde tetikleyecek
    hiçbir şey yoktur."""
    _onbellek_yaz(veri_dizini, {"zaman": time.time(), "son_deneme": time.time(),
                                "surum": version.APP_VERSION})
    monkeypatch.setattr(guncelleme, "_sor",
                        lambda: {"surum": "99.0.0", "url": guncelleme.YAYIN_SAYFASI})

    # Önce kanıt: normal yol taze önbellekte SORMUYOR.
    cagrildi = []
    monkeypatch.setattr(guncelleme, "_tazeleme_baslat", lambda d: cagrildi.append(d))
    assert guncelleme.bilgi(veri_dizini) is None
    assert cagrildi == []

    sonuc = guncelleme.simdi_kontrol_et(veri_dizini)

    assert sonuc["durum"] == guncelleme.DURUM_YENI
    assert sonuc["guncelleme"]["surum"] == "99.0.0"


def test_a_manual_check_reports_being_up_to_date(veri_dizini, monkeypatch):
    """"Güncelsin" ile "soramadım" AYRI cevaplar olmak zorunda: `bilgi()` ikisini
    de `None`a indiriyor ve elle basılan bir düğmede fark asıl bilgidir."""
    monkeypatch.setattr(guncelleme, "_sor",
                        lambda: {"surum": version.APP_VERSION,
                                 "url": guncelleme.YAYIN_SAYFASI})

    sonuc = guncelleme.simdi_kontrol_et(veri_dizini)

    assert sonuc == {"durum": guncelleme.DURUM_GUNCEL, "guncelleme": None}


def test_a_manual_check_reports_a_failure(veri_dizini, monkeypatch):
    monkeypatch.setattr(guncelleme, "_sor", lambda: None)

    sonuc = guncelleme.simdi_kontrol_et(veri_dizini)

    assert sonuc == {"durum": guncelleme.DURUM_HATA, "guncelleme": None}


def test_a_manual_check_obeys_the_preference(veri_dizini, monkeypatch):
    """3. sözleşme elle yolda da geçerli: kapalıysa ağa HİÇ çıkılmaz. Bir
    düğmenin varlığı, kullanıcının kapattığı şeyi açmanın gerekçesi değil."""
    def _patlar():
        raise AssertionError("kontrol kapalıyken ağa çıkıldı")

    monkeypatch.setattr(guncelleme, "_sor", _patlar)

    assert guncelleme.simdi_kontrol_et(veri_dizini, izin=False) == {
        "durum": guncelleme.DURUM_KAPALI, "guncelleme": None}


def test_a_manual_check_does_not_clear_the_background_flag(veri_dizini, monkeypatch):
    """`_tazele`nin `finally`si `_KOSUYOR`u sıfırlıyor. Elle çağrı o yolu
    kullansaydı, koşan bir arka plan tazelemesinin bayrağını düşürür ve ikinci
    bir iş parçacığının doğmasına yol açardı — `_kontrol_et`in ayrı bir işlev
    olmasının sebebi tam olarak bu."""
    monkeypatch.setattr(guncelleme, "_sor", lambda: None)
    guncelleme._KOSUYOR = True                    # arka planda biri koşuyor

    guncelleme.simdi_kontrol_et(veri_dizini)

    assert guncelleme._KOSUYOR is True


def test_the_browser_and_the_server_agree_on_the_status_names():
    """`durum` değerleri İKİ dilde yazılı: burada sabit, `settings.js`te düz
    dize. Ayrışma SESSİZ olurdu — sunucu "guncel" der, betik onu tanımaz ve
    `else` dalına düşüp kullanıcıya "kontrol edilemedi" gösterir. Yani doğru
    çalışan bir kontrol, kırıkmış gibi görünür.

    Betik tarafı `DURUM_HATA`yı ADIYLA karşılaştırmıyor (bilinçli: ağ hatası ve
    sunucunun "hata"sı aynı `else` dalına düşüyor), o yüzden ondan söz edilmesi
    beklenmiyor — ötekilerin üçü de geçmek zorunda.
    """
    yol = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "static", "settings.js")
    with open(yol, encoding="utf-8") as f:
        betik = f.read()

    karsilastirilan = set(re.findall(r'cevap\.durum === "([a-z]+)"', betik))

    assert karsilastirilan, "settings.js hiçbir `durum` değeriyle karşılaştırmıyor"
    tanimli = {guncelleme.DURUM_YENI, guncelleme.DURUM_GUNCEL,
               guncelleme.DURUM_HATA, guncelleme.DURUM_KAPALI}
    assert karsilastirilan <= tanimli, (
        f"settings.js tanımsız bir durum arıyor: {sorted(karsilastirilan - tanimli)}")
    assert karsilastirilan == tanimli - {guncelleme.DURUM_HATA}

