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
    parçacığı başlatırdı."""
    monkeypatch.setattr(guncelleme, "_sor", lambda: None)

    guncelleme._tazele(veri_dizini)

    with open(os.path.join(veri_dizini, guncelleme.ONBELLEK_DOSYASI), encoding="utf-8") as f:
        assert float(json.load(f)["zaman"]) > 0


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
