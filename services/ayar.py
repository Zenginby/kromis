# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Veri dizinlerinin AYAR NESNESİ ve rotalara enjeksiyonu (Faz 0 / Adım 4).

NEDEN VAR: Adım 4'e kadar `OUTPUT_DIR`/`ASSETS_DIR`/`STATIC_DIR` `app.py`nin
İTHAL ANINDA hesaplanan modül sabitleriydi ve router'lar onları
`services/yollar.py` üzerinden `sys.modules["app"]`a bakarak okuyordu — 66
testin `monkeypatch.setattr(appmod, "OUTPUT_DIR", …)` yamasını döngü açmadan
çalışır tutmanın geçici yolu (docs/faz0-web-first.md, 2. görevin sapmaları).
Geçiciydi çünkü iki kusuru vardı: dizin süreç başına TEK bir küresel değerdi
(çok kiracılı web'de her isteğin kendi dizini olacak) ve bir modülün başka
bir modülün özniteliğini ADIYLA okuması, kimsenin izleyemediği gizli bir bağdı.

ŞİMDİ: dizinler `Ayarlar` adlı donmuş bir veri sınıfında duruyor, nesne
`app.state.ayarlar`da yaşıyor ve rotalar onu FastAPI bağımlılığıyla alıyor:

    def rota(…, ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> dict:
        storage.list_history(ayarlar.output_dir)

Rotanın imzası dizine bağımlılığını AÇIK söylüyor; store işlevleri zaten
dizini parametre alıyordu (`storage.list_history(output_dir)`), değişen yalnız
ÇAĞIRAN taraf. Testler `app.state.ayarlar`ı tek bir fixture ile değiştiriyor
(`tests/conftest.py::dizinler`) — 66 yama yerine tek nokta.

FAZ 1 NOTU: kullanıcı hesabı / kiracı geldiğinde değişecek yer `ayarlar()`
işlevinin gövdesi — istekten kiracıyı çözüp o kiracının (ya da obje
depolamanın) `Ayarlar`ını döndürecek. Router'lar `ayarlar.output_dir` okumaya
devam eder, imza değişmez. Bu dosyanın var olma sebebi o değişikliğin tek bir
yerde olması.

NEDEN `dataclass`, pydantic-settings DEĞİL: alan dört yol dizesi ve doğrulama
yok; `catalog.py`nin aynı deyimi. Donmuş (`frozen=True`) çünkü paylaşılan bir
nesne — bir rota "geçici olarak" alan değiştirse bütün istekler görürdü;
testler `dataclasses.replace` ile kopya alıyor.

NEDEN `str`, `pathlib.Path` DEĞİL: depo `os.path.join` deyiminde, store'lar
`str` alıyor ve 60'tan fazla test `str(tmp_path)` veriyor. Türü değiştirmek
bu PR'ın konusu (kaynağın YERİ) değil; davranışı birebir korumak öncelikli.

NEDEN ARA KATMAN DA BURADAN OKUYOR: `services/dil.py` dil zincirinin 2.
halkasında diskteki tercihe bakıyor ve bir `Depends` alamıyor (ara katman
rota değil). O da `ayarlar(request)`i DOĞRUDAN çağırıyor — okuma noktası tek
kalıyor; Faz 1'de kiracı çözümü buraya girince ara katman da onu görür.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

import paths


@dataclass(frozen=True)
class Ayarlar:
    """Uygulamanın dizin ayarları — istek yolunda okunan, ithal anında bağlanmayan.

    * `data_dir`   — yazılabilir kökün kendisi (yedekler, `hata.log`, `.last-version`)
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
        """`paths`in bu makine/ortam için çözdüğü yerleşim.

        `paths` tek doğruluk kaynağı olarak kalıyor: Android/frozen/geliştirme
        dalları ve `KROMIS_DATA_DIR` orada. Bu işlev saf bir yol HESABI, dizin
        AÇMAZ — `app.py` onu ithal anında çağırıyor ve ithalin yan etkisi
        olmamalı (dizinler `_lifespan`da açılır).
        """
        return cls(data_dir=paths.data_dir(), output_dir=paths.output_dir(),
                   assets_dir=paths.assets_dir(), static_dir=paths.static_dir())


def ayarlar(request: Request) -> Ayarlar:
    """FastAPI bağımlılığı: bu isteğin ayarları. Bugün süreç geneli tek nesne.

    `request.app.state.ayarlar` — bileşim kökü (`app.py`) ithal anında koyuyor.
    Faz 1'de burası isteğe (kiracı, hesap) göre farklı bir nesne döndürecek ve
    hiçbir router değişmeyecek; okuma noktasının TEK olması bu yüzden şart.
    """
    return request.app.state.ayarlar
