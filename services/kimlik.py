# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kimlik kapısı — çerezden kullanıcı; yoksa API'de 401, sayfada 302 (Faz 1 / 3-4).

İKİ BAĞIMLILIK, TEK ÇÖZÜM (`_coz`): oturum çerezi → `oturumlar ⋈ kullanicilar`
tek sorgu → `request.state.kullanici`. Farkları yalnız oturumsuz cevap:

* `aktif_kullanici` — **401 JSON** (`{"detail": …}` i18n'li). JSON bekleyen
  bir `fetch` çağrısına 302 verilmez: `fetch` yönlendirmeyi takip eder ve 35
  çağrı yeri HTML alırdı; ön yüz 401'i görünce `/giris`e kendisi gider
  (static/core.js, `window.fetch` sarmalı). 47 rota bunu taşıyor — 44 stüdyo
  rotasının 42'si `Depends(ayar.ayarlar)` ÜZERİNDEN (ayar nesnesi kullanıcıya
  göre kurulduğu için kapı onun içinde; gerekçesi services/ayar.py), ikisi
  (`POST /api/settings`, `POST /api/palette/suggest` — dizin okumazlar)
  doğrudan; artı `GET /api/hesap/ben`, `POST /api/hesap/cikis`.
* `sayfa_kullanicisi` — **302 `/giris`**. Tarayıcı GEZİNMESİ olan tek rota
  `GET /` (routers/kok.py); oturumsuz bir ziyaretçiye 401 JSON göstermek
  yanlış olurdu. Yönlendirme `GirisSayfasi` istisnasıyla: FastAPI bağımlılığı
  cevap DÖNDÜREMEZ, fırlatabilir; app.py `giris_sayfasina`yı işleyici olarak
  takıyor. `?sonra=` YOK: belge "302 `/giris`" diyor ve tek sayfa `/`.

Kapı ARA KATMAN DEĞİL BAĞIMLILIK, bilerek: hangi rotanın açık olduğu
imzasında (ya da imzasındaki `ayar.ayarlar`ın imzasında) okunur (Faz 0 / 4'ün
"imza bağımlılığı söyler" ilkesi). Açık rotaların listesi elle tutuluyor ve
bekçisi var: tests/test_kimlik.py her rotanın YA kapılı YA gerekçeli açık
listede olduğunu sınar — listede olmayan yeni bir rota öntanımlı olarak
"kapılı" DEĞİL, "sınıflandırılmamış"tır ve takım kırmızıdır (CLAUDE.md §5).

NEDEN `async def` (3. görevde `def` idi): dil zincirinin 3. halkası
`kullanicilar.dil` (services/dil.py) ve halka kullanıcı çözüldüğü anda,
BURADAN uygulanıyor — oturum sorgusu kullanıcıyı zaten getirdi, dil için ek
sorgu SIFIR. Arayüz dili bir `ContextVar` (i18n.py) ve FastAPI senkron bir
bağımlılığı iş parçacığı havuzunda KOPYA bağlamla koşturur: orada yapılan
`set_active` rotaya hiç ulaşmazdı (anyio `to_thread.run_sync` bağlamı
kopyalar, geri yazmaz — ölçüldü). Async bağımlılık isteğin kendi görevinde
koşar; rota (sync `def`) havuza giderken o bağlamın kopyasını alır ve dili
görür. DB sorgusu `run_in_threadpool` ile: senkron sürücü (K1) olay
döngüsünü kilitlemesin. `Session` iş parçacığına bağlı değil — `db.oturum`
onu bir havuz iş parçacığında açıyor, burası başkasında kullanıyor, rota
üçüncüsünde; SQLAlchemy ve psycopg 3 için sıralı kullanım yeterli.

KAYAN ÖMÜR BURADAN YAZILIR: `hesap.oturum_dogrula` `son_gorulme`yi 5 dk
çözünürlükle ilerlettiğinde çerezin `Max-Age`i de yenilenmeli — yoksa DB'de
30 gün daha yaşayan bir oturumun çerezi tarayıcıda ilk 30 günün sonunda
düşerdi. Bağımlılık `response: Response` alabiliyor (FastAPI bunu rotanın
cevabına birleştiriyor), yani rota bunu bilmek zorunda değil.

TESTLERDE: `tests/conftest.py::kullanici` (autouse) iki bağımlılığı da
`dependency_overrides` ile bir test kullanıcısına bağlıyor — 37 dosyanın 178
`TestClient` çağrısı değişmeden geçiyor; override `bagla()`yı çağırıyor ki 3.
halka orada da işlesin. Kapının KENDİSİNİ sınayan dosyalar `gercek_kimlik`
işaretiyle override'sız koşuyor.

ÜÇÜNCÜ BAĞIMLILIK — `kimlik_bilgileri` / `KIMLIKLER` (Faz 1 / 7): kullanıcının
SAĞLAYICI kimlikleri (`saglayici_kimlikleri`, şifreli) istek başına BİR kez
çözülür, `request.state.kimlikler`e ve `kimlik_baglami`na konur; rota
dönünce bağlam çözülür. Yalnız sağlayıcı anahtarı okuyan rotalar taşır
(`/api/settings`, `/api/chat`, dört üretim rotası) — hangi rotanın anahtar
okuduğu İMZASINDA yazılı, bekçisi tests/test_kimlik.py. Override YOK: test
kullanıcısı `depo_db` kipinde gerçek satır, sözlüğü gerçekten DB'den çözülür.

PLATFORM ANAHTARI (Faz 2 / 6): kullanıcının sözlüğü DB'den çıkar çıkmaz
`platform_anahtari.kimlikler(...)` ile tamamlanır — ad ad kullanıcı →
platform → yok; rota ve adaptörler TEK sözlük görür, `kaynaklar` özniteliği
"hangisi kimden" sorusunu taşır (`isler.anahtar_kaynagi`). Dört üretim rotası
ve yeniden gönderim bu bağımlılığı geri aldı: "anahtar yok" kapısı sıraya
yazmadan ÖNCE, rotada bir kez sorulur (services/kapilar.py `check_anahtar`).
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from fastapi import Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

import i18n
import kimlik_baglami
from services import cerez, depo_kimlik_bilgisi, dil, hesap, platform_anahtari
from services.db import OTURUM
from services.tablolar import Kullanici

# Oturumsuz tarayıcı gezinmesinin gittiği yer (`GET /giris`, routers/hesap.py).
GIRIS_SAYFASI = "/giris"


class GirisSayfasi(Exception):
    """Oturumsuz TARAYICI GEZİNMESİ — işleyicisi `giris_sayfasina` (302 `/giris`).

    `HTTPException(302)` DEĞİL: FastAPI onu JSON gövdeli bir cevaba çevirir
    ve `Location`ı `headers`tan taşımak durum kodunun anlamını dolaylı kılar.
    Adı olan bir istisna + tek işleyici, `RedirectResponse`u tek yerde kurar.
    """


def bagla(request: Request, kullanici: Kullanici) -> Kullanici:
    """Çözülen kullanıcıyı isteğe bağlar: `request.state.kullanici` + dil zincirinin 3. halkası.

    `_coz`un son adımı ve test override'ının ÇAĞIRDIĞI tek üretim işlevi:
    dil halkası burada olmasa override'lı 3.100 test kullanıcının dilini hiç
    görmez, kapının kendisini sınayan 40 test görürdü — iki yolun aynı yerden
    geçmesi, yolların ayrışmamasının garantisi.
    """
    request.state.kullanici = kullanici
    dil.kullanici_dili(request, kullanici.dil)
    return kullanici


async def _coz(request: Request, response: Response, db: Session) -> Kullanici | None:
    """Çerez → oturum → kullanıcı; yoksa/bitmişse `None`. Aynı istekte ikinci kez sormaz."""
    mevcut = getattr(request.state, "kullanici", None)
    if mevcut is not None:
        return mevcut
    ham = request.cookies.get(cerez.OTURUM_CEREZI)
    if not ham:
        return None
    sonuc = await run_in_threadpool(hesap.oturum_dogrula, db, ham, hesap.simdi())
    if sonuc is None:
        return None
    kullanici, yenilendi = sonuc
    if yenilendi:
        cerez.oturum_yaz(response, ham)
    return bagla(request, kullanici)


async def aktif_kullanici(request: Request, response: Response,
                          db: Session = OTURUM) -> Kullanici:
    """FastAPI bağımlılığı (API): bu isteğin kullanıcısı; oturum yoksa/bitmişse 401 JSON."""
    kullanici = await _coz(request, response, db)
    if kullanici is None:
        raise HTTPException(status_code=401,
                            detail=i18n.t("err.hesap_giris_gerekli", dil.aktif()))
    return kullanici


async def sayfa_kullanicisi(request: Request, response: Response,
                            db: Session = OTURUM) -> Kullanici:
    """FastAPI bağımlılığı (HTML sayfa): kullanıcı; oturum yoksa 302 `/giris` (`GirisSayfasi`)."""
    kullanici = await _coz(request, response, db)
    if kullanici is None:
        raise GirisSayfasi()
    return kullanici


async def giris_sayfasina(request: Request, exc: GirisSayfasi) -> RedirectResponse:
    """`GirisSayfasi` işleyicisi — app.py takıyor. `no-store`: vekil oturumsuz 302'yi saklamasın."""
    return RedirectResponse(GIRIS_SAYFASI, status_code=302,
                            headers={"Cache-Control": "no-store"})


async def kimlik_bilgileri(request: Request, db: Session = OTURUM,
                           kullanici: Kullanici = Depends(aktif_kullanici),
                           ) -> AsyncIterator[Mapping[str, str]]:
    """FastAPI bağımlılığı: bu isteğin kullanıcısının sağlayıcı kimlikleri, çözülmüş düz sözlük.

    DB'den bir kez (`depo_kimlik_bilgisi.oku`, `run_in_threadpool` — senkron
    sürücü olay döngüsünü kilitlemesin), `request.state.kimlikler`e ve
    `kimlik_baglami`na. `yield`: bağlam rota döner dönmez, AYNI görevde
    çözülür (`scope="function"`, `db.OTURUM`un gerekçesi) — TestClient'ın
    portalı istekler arasında bağlamı taşıyabiliyor (conftest'in dil sızıntısı
    dersi), yani "kendiliğinden biter" diye bırakılmaz. Aynı istekte ikinci
    kez sormaz (`request.state` önbelleği, `_coz`un deseni).
    """
    mevcut: Mapping[str, str] | None = getattr(request.state, "kimlikler", None)
    if mevcut is None:
        kullanicinin = await run_in_threadpool(depo_kimlik_bilgisi.oku, db, kullanici.id)
        # Platform anahtarıyla TAMAMLANMIŞ sözlük (Faz 2 / 6): ortam okuması ucuz, DB'ye ek sorgu yok.
        mevcut = platform_anahtari.kimlikler(kullanicinin)
        request.state.kimlikler = mevcut
    jeton = kimlik_baglami.bagla(mevcut)
    try:
        yield mevcut
    finally:
        kimlik_baglami.coz(jeton)


# Rotaların kullanacağı TEK biçim — `scope="function"` ŞART (gerekçe yukarıda).
KIMLIKLER = Depends(kimlik_bilgileri, scope="function")
