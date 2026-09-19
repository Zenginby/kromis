# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kayıt zaman damgası — depoya yazılan her `created_at`ın tek kaynağı.

Ayrı ve küçük: her store işlevi `now=` parametresi alıyor (test edilebilirlik),
değeri üreten yer ise tek olmalı — biçim (`isoformat(timespec="seconds")`)
iki router'da iki kez yazılsaydı bir gün biri mikrosaniye taşırdı ve
`history.json`daki damgalar sıralanamaz olurdu.

İKİ BİÇİM, TEK KAYNAK (Faz 1 / 5): JSON depolar `simdi()`nin saniye
çözünürlüklü, saat dilimsiz yerel dizesini yazıyor; DB depoları
(`services/depo_medya.py`, `depo_klasor.py`) `timestamptz` sütununa `an()`ın
saat dilimli, MİKROSANİYELİ anını yazıyor ve dışarıya `damga()` ile yine
`simdi()` biçiminde döküyor. Mikrosaniye DB'de ŞART: `/api/generate` n=4'te
dört satırı aynı saniyede yazıyor ve galeri "en yeni üstte", arena "üretim
sırasında" istiyor — saniyeye kırpılmış bir damga bu sırayı kaybederdi.
Postgres'in `now()`u da olmazdı: transaksiyonun başlangıç anı, dört satırda
aynı. `damga()` yerel saate çevirip diliminden soyar, yani `created_at`
istemcinin bugüne kadar gördüğü dizeyle birebir aynı biçimde kalır
(`static/folders.js` bu dizeyi `localeCompare` ile sıralıyor).

ÜÇÜNCÜ BİÇİM, YİNE TEK KAYNAK (Faz 2 / 10): `damga_utc()` — UTC, saniye,
sonu `Z` (`2026-09-19T12:00:00Z`). "Tek biçim" kararı `created_at` için
duruyor: o dize masaüstünden beri istemcide dilimsiz okunuyor ve sunucuyla
aynı makinede anlamı var. İş uçları (`/api/isler*`, `/api/admin/*`) o
varsayımın DÜŞTÜĞÜ yer: web konteyneri UTC'de, kullanıcı başka dilimde ve
`static/isler.js` `basladi`yi `new Date()` ile KARŞILAŞTIRIYOR — dilimsiz
`2026-09-18T18:44:25`i tarayıcı kendi yerel saati sayıyor, UTC+3'teki
kullanıcı paneli "180:00"la açılıyordu (ölçüldü, docs/studyo-guncelleme-plani.md
B3). Dilimli dize `Date`e tek bir ANI söyler; `Z` seçildi (`+00:00` değil)
ki `localeCompare` sıralaması (isler.js `ciz`) sunucunun dilimi değişse de
kronolojik kalsın — bütün dizeler aynı ofsette. Galeri `created_at`i BU PR'DA
DEĞİŞMEDİ (aynı sınıf kusur "az önce/bugün" gösteriminde var, ama o dizeyi
okuyan üç betik ve dondurulmuş kabuk var; kalem docs/faz2 §10).
"""
from __future__ import annotations

import datetime as _dt


def simdi() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def an() -> _dt.datetime:
    """Şu an, saat dilimli (yerel) ve mikrosaniyeli — DB depolarının `olusturuldu`su."""
    return _dt.datetime.now().astimezone()


def damga(t: _dt.datetime) -> str:
    """Saat dilimli bir anı `simdi()` biçimine döker (yerel saat, saniye, dilimsiz).

    Dilimsiz (naive) gelen bir değer yerel saat sayılır — `simdi()`nin yazdığı
    şey zaten o. Böylece `damga(an())` ile `simdi()` aynı saniyede aynı dize.
    """
    if t.tzinfo is not None:
        t = t.astimezone()
    return t.replace(tzinfo=None).isoformat(timespec="seconds")


def damga_utc(t: _dt.datetime) -> str:
    """Bir anı UTC'de, saniye çözünürlüğünde ve `Z` sonekiyle döker (`2026-09-19T12:00:00Z`).

    Dilimsiz (naive) gelen değer `damga()`daki gibi yerel saat sayılır, sonra
    UTC'ye çevrilir. `fromisoformat` 3.11'den beri `Z`yi okur; `routers/isler.py
    _since` bu dizeyi geri aldığında dilimli görür ve `astimezone()` çağırmaz.
    """
    if t.tzinfo is None:
        t = t.astimezone()
    return t.astimezone(_dt.UTC).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
