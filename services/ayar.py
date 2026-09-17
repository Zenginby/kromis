# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Veri dizinlerinin AYAR NESNESİ ve rotalara enjeksiyonu — KULLANICIYA GÖRE (Faz 0 / 4, Faz 1 / 4).

NEDEN VAR: Adım 4'e kadar `OUTPUT_DIR`/`ASSETS_DIR`/`STATIC_DIR` `app.py`nin
İTHAL ANINDA hesaplanan modül sabitleriydi ve router'lar onları
`services/yollar.py` üzerinden `sys.modules["app"]`a bakarak okuyordu — 66
testin `monkeypatch.setattr(appmod, "OUTPUT_DIR", …)` yamasını döngü açmadan
çalışır tutmanın geçici yolu (docs/faz0-web-first.md, 2. görevin sapmaları).
Geçiciydi çünkü iki kusuru vardı: dizin süreç başına TEK bir küresel değerdi
(çok kiracılı web'de her isteğin kendi dizini olacak) ve bir modülün başka
bir modülün özniteliğini ADIYLA okuması, kimsenin izleyemediği gizli bir bağdı.

ŞİMDİ (Faz 1 / 4, docs/faz1-veritabani-hesaplar.md → 4): iki ayar nesnesi var
ve ikisi de aynı donmuş `Ayarlar` sınıfından —

* `genel(request)` — sürecin PAYLAŞILAN yerleşimi (`app.state.ayarlar`):
  `data_dir` (hata.log, posta.log, yedek), `static_dir`, ve dondurulmuş
  kabuğun tek kullanıcılı `output/`-`assets/`i. Okuyanlar: `_lifespan`,
  oturum İSTEMEYEN rotalar (`/health`, `/giris`, hesap rotaları — kayıt
  olmadan kullanıcı yok, dizini de yok) ve `GET /` (yalnız `static_dir`).
* `ayarlar(request, kullanici)` — bu isteğin KULLANICISININ yerleşimi:

      <data_dir>/kullanicilar/<uuid>/output   ← medya dosyaları, guncelleme.json
      <data_dir>/kullanicilar/<uuid>/assets   ← logo/afiş/motto DOSYALARI (<tur>/<id>.png)

  Manifestler (history/folders/chats/palettes/prefs/index.json) burada ARTIK
  YOK — kayıtlar DB'de (Faz 1 / 5-6), dizinde yalnız dosyalar duruyor.

  `data_dir` ve `static_dir` AYNI kalır (belge: "data_dir aynı, static_dir
  aynı"). Kullanıcı `Depends(kimlik.aktif_kullanici)` ile gelir — yani
  `Depends(ayar.ayarlar)` yazan her rota KAPININ ARKASINDADIR, ayrı bir satır
  yazmadan: dizin isteyen bir rota kimin dizinini istediğini söylemek
  zorunda ve oturumsuz istek 401 alır. 44 stüdyo rotasının 42'si bu yoldan
  kapılı; dizin okumayan iki rota `kimlik.aktif_kullanici`yi doğrudan alır.
  Bekçisi tests/test_kimlik.py (kapı) ve tests/test_app_bolme.py (imza).

Router'lar DEĞİŞMEDİ (Faz 0 / 4'ün vaadi): `ayarlar.output_dir` okumaya devam
ediyorlar; kullanıcıya göre dizin bu işlevin İÇİNDE, tablo satırlarında değil
(docs/graflar/uc-noktalar.md başlığının söylediği tam olarak bu).

DİZİN İLK KULLANIMDA AÇILIR (`_dizinleri_ac`): kullanıcı kökü `0o700` — bir
kullanıcının medyası aynı makinedeki başka bir sistem kullanıcısına açık
olmasın; süreç başına kullanıcı başına BİR kez (`_acilanlar`), sonraki
istekler `makedirs` bile çağırmaz. `paths.ensure_data_dirs` DEĞİL: o işlev
eski ad göçünü (`_migrate_from_old_name`) de koşturuyor ve o göç sürecin
tek kullanıcılı ev dizinine ait; kullanıcı dizinlerinin onunla işi yok.

NEDEN `dataclass`, pydantic-settings DEĞİL: alan dört yol dizesi ve doğrulama
yok; `catalog.py`nin aynı deyimi. Donmuş (`frozen=True`) çünkü paylaşılan bir
nesne — bir rota "geçici olarak" alan değiştirse bütün istekler görürdü;
`kullanici_icin` ve testler `dataclasses.replace` ile kopya alıyor. İstek
başına yeni örnek: 4 dize, ölçülecek bir bedeli yok.

NEDEN `str`, `pathlib.Path` DEĞİL: depo `os.path.join` deyiminde, store'lar
`str` alıyor ve 60'tan fazla test `str(tmp_path)` veriyor. Türü değiştirmek
bu PR'ın konusu değil; davranışı birebir korumak öncelikli.

`str(uuid)` (tireli, 36 hane), `.hex` DEĞİL: `GET /api/hesap/ben`in döndürdüğü
`id` ile aynı yazım — diskte bir dizin gördüğünde hangi hesabın olduğunu
sorgulamak için dönüştürme gerekmesin.
"""
from __future__ import annotations

import dataclasses
import os
import threading
import uuid
from dataclasses import dataclass

from fastapi import Depends, Request

import paths
from services import kimlik
from services.tablolar import Kullanici

# Kullanıcı dizinlerinin `data_dir` altındaki kökü.
KULLANICILAR_DIZINI = "kullanicilar"

# Bu süreçte açılmış kullanıcı kökleri (tam yol): ilk istekten sonra dizin
# sistemine bir daha sorulmaz. Kilit `i18n._lock`un önbelleğiyle aynı
# gerekçe: iki istek aynı anda ilk kez gelebilir.
_acilanlar: set[str] = set()
_kilit = threading.Lock()


@dataclass(frozen=True)
class Ayarlar:
    """Uygulamanın dizin ayarları — istek yolunda okunan, ithal anında bağlanmayan.

    * `data_dir`   — yazılabilir kökün kendisi (yedekler, `hata.log`, `.last-version`, `kullanicilar/`)
    * `output_dir` — `history.json`, üretilen medya, tercihler, sohbetler, paletler
    * `assets_dir` — kullanıcının logo/afiş kütüphanesi
    * `static_dir` — `index.html` ve tarayıcı betikleri (salt okunur)
    """

    data_dir: str
    output_dir: str
    assets_dir: str
    static_dir: str

    @classmethod
    def varsayilan(cls) -> Ayarlar:
        """`paths`in bu makine/ortam için çözdüğü yerleşim — sürecin PAYLAŞILAN nesnesi.

        `paths` tek doğruluk kaynağı olarak kalıyor: Android/frozen/geliştirme
        dalları ve `KROMIS_DATA_DIR` orada. Bu işlev saf bir yol HESABI, dizin
        AÇMAZ — `app.py` onu ithal anında çağırıyor ve ithalin yan etkisi
        olmamalı (dizinler `_lifespan`da açılır).
        """
        return cls(data_dir=paths.data_dir(), output_dir=paths.output_dir(),
                   assets_dir=paths.assets_dir(), static_dir=paths.static_dir())

    def kullanici_koku(self, kullanici_id: uuid.UUID) -> str:
        """`<data_dir>/kullanicilar/<uuid>` — kullanıcının bütün verisinin altında durduğu dizin."""
        return os.path.join(self.data_dir, KULLANICILAR_DIZINI, str(kullanici_id))

    def kullanici_icin(self, kullanici_id: uuid.UUID) -> Ayarlar:
        """Bu yerleşimin `kullanici_id` için kopyası: `output_dir`/`assets_dir` kullanıcı kökünde.

        Saf yol hesabı, dizin AÇMAZ (`_dizinleri_ac` ayrı) — testler ve içe
        aktarma aracı (8. görev) yolu açmadan sorabilsin.
        """
        kok = self.kullanici_koku(kullanici_id)
        return dataclasses.replace(self, output_dir=os.path.join(kok, "output"),
                                   assets_dir=os.path.join(kok, "assets"))


def genel(request: Request) -> Ayarlar:
    """FastAPI bağımlılığı: sürecin PAYLAŞILAN ayarları (`app.state.ayarlar`), oturum istemez.

    Bileşim kökü (`app.py`) nesneyi ithal anında koyuyor; testler
    `tests/conftest.py::dizinler` ile değiştiriyor. Kullanıcı verisine
    dokunan bir rota BUNU DEĞİL `ayarlar`ı alır — bekçisi tests/test_kimlik.py.
    """
    return request.app.state.ayarlar


def ayarlar(request: Request,
            kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> Ayarlar:
    """FastAPI bağımlılığı: bu isteğin KULLANICISININ ayarları; oturum yoksa kapı 401 verir.

    Kullanıcıyı `kimlik.aktif_kullanici` çözüyor (tek sorgu, `request.state`e
    konur); burası yalnız yolu türetir ve dizini ilk kullanımda açar.
    """
    ozel = genel(request).kullanici_icin(kullanici.id)
    _dizinleri_ac(ozel, kullanici.id)
    return ozel


def _dizinleri_ac(ozel: Ayarlar, kullanici_id: uuid.UUID) -> None:
    """Kullanıcı kökünü (0o700) ve iki alt dizinini açar — süreç başına kullanıcı başına bir kez."""
    kok = ozel.kullanici_koku(kullanici_id)
    with _kilit:
        if kok in _acilanlar:
            return
    # `makedirs`in `mode`u yalnız SON dizine uygulanır; `kullanicilar/` üst
    # dizini süreç umask'ıyla açılır — orada gizlenecek bir şey yok, her
    # kullanıcının verisi kendi 0o700 kökünde.
    os.makedirs(kok, mode=0o700, exist_ok=True)
    os.makedirs(ozel.output_dir, exist_ok=True)
    os.makedirs(ozel.assets_dir, exist_ok=True)
    with _kilit:
        _acilanlar.add(kok)
