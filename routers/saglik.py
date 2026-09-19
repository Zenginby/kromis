# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Sağlık ucu — `GET /health` (Faz 0 / Adım 8): konteynerin ve orkestratörün sondası.

NEDEN AYRI MODÜL, `routers/kok.py` DEĞİL: kök router'ın tek işi `index.html`i
sürüm ve çeviri yerleştirip servis etmek — okuyucusu tarayıcı. Bu ucun
okuyucusu ise `Dockerfile`ın `HEALTHCHECK`i, bir yük dengeleyici ya da bir
uptime sondası; gövdesi cümle değil MAKİNE OKUYAN JSON ve dil bağlamıyla,
şablonla, `no-store` gerekçesiyle hiçbir ilgisi yok. İki farklı okuyucunun
kodunu aynı dosyada tutmak, birinin gerekçesini ötekinin okumasına zorlardı.
(`tests/test_i18n.py` bu modülü bu yüzden "kullanıcıya konuşmayan" sayıyor.)

NE RAPORLAR: `{"ok", "version", "data_dir_writable", "db_reachable", "worker_alive",
"worker_last_heartbeat"}`.

* `version` — hangi imajın ayakta olduğunu SORUYA cevap: kayan bir `latest`
  etiketinin arkasında ne koştuğunu tek `curl` söylesin.
* `data_dir_writable` — ayar nesnesinin `data_dir`ine (konteynerde
  `KROMIS_DATA_DIR=/data`) GERÇEKTEN yazılabiliyor mu. Konteynerin en sık
  kusuru bu: bind-mount edilen dizin başka bir kullanıcıya ait, birim salt
  okunur ya da disk dolu — uygulama açılır, `/` 200 verir, ilk üretimde
  `history.json` yazılamaz. Sonda bunu ilk 30 saniyede söylemeli.
* `db_reachable` (Faz 1 / 1. görev) — `DATABASE_URL`deki Postgres `SELECT 1`e
  1 sn içinde cevap veriyor mu (`services/db.py::erisilebilir`). Üç durumda
  `false` ve üçü de "sağlıksız": değişken hiç verilmemiş (yapılandırma
  eksik), sunucu kapalı/ulaşılamıyor, ya da lifespan motoru kuramamış
  (bozuk URL — `hata.log`a düşer). "Yapılandırılmamış" AYRI bir değer
  (`null`) DEĞİL, bilerek: veri tabanı olmadan bu uygulama kullanıcı
  hesabı açamaz; sondanın "sağlıklı" demesi için bir sebep yok.

* `worker_alive` (Faz 2 / 9) — `isciler` tablosunda son kalbi `CANLI_ESIK`
  (90 sn; `services/depo_admin.py`nin sabiti, admin sayfasının "canlı"
  ölçütüyle AYNI eşik, iki yerde iki sayı olmasın) içinde bir işçi satırı var
  mı. `worker_last_heartbeat` o en son kalp (ISO 8601 UTC; satır yoksa
  `null`). Motor yoksa ya da DB'ye ulaşılamıyorsa İKİSİ DE `null`: cevap
  bilinmiyor, "hayır" değil. `isciler` tablosu yoksa (göç koşmamış) yine
  `null` — `db_reachable` bundan etkilenmez, o alanın anlamı `SELECT 1`.
  Aynı bağlantı, aynı 1 sn'lik bütçe (`db.sor`): sonda iki kez kapı çalmaz.

`ok` İKİ ölçütün VE'si — Faz 0 / 8'in notu ("ikinci bir ölçüt gelince `ok`
hepsinin VE'si olur, alan adları değişmez") burada yerine geldi. **`worker_alive`
`ok`a GİRMEZ** (belge §9): işçinin düşmesi web sürecini "sağlıksız" yapıp
platformun WEB'i yeniden başlatmasına yol açmamalı — işçinin sağlığı işçinin
kalbi, platform onu kendi yeniden başlatır; `/health`i işçi için okuyan bir
uyarı kuralı GÖVDEYE bakar (`worker_alive:false`), durum koduna değil
(KURULUM.md → Web sürümü, 9. adım).

NEDEN 503, "200 + ok:false" DEĞİL: sondayı okuyan şeylerin çoğu (Docker
`HEALTHCHECK`, Kubernetes readiness, uptime servisleri) gövdeyi değil DURUM
KODUNU okur; yazılamayan bir veri dizini ya da ulaşılamayan bir veri tabanı
"sağlıksız" demektir ve 200 dönmek o okuyucuların hepsine yalan söylemek
olurdu. Gövde yine de tam dönüyor ki `curl` ile bakan insan NEYİN sağlıksız
olduğunu okusun.
"""
from __future__ import annotations

import datetime as dt
import os
import tempfile

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import Connection, Engine, text

import version
from services import ayar, db, depo_admin, kuyruk, zaman

router = APIRouter()


def veri_dizini_yazilabilir(dizin: str) -> bool:
    """`dizin`e gerçekten bir dosya yazılıp silinebiliyor mu.

    NEDEN `os.access(dizin, os.W_OK)` DEĞİL: `access(2)` izin BİTLERİNE bakar,
    yazmanın olacağına değil. Üç yerde yanlış cevap verir ve üçü de konteynerde
    gündelik: (1) root olarak koşan süreçte bitler ne derse desin `True` döner
    — CI'daki koşucu ve pek çok konteyner root; (2) salt okunur bir bind-mount
    ya da `tmpfs` bitleri "yazılabilir" gösterirken yazımı reddeder; (3) dolu
    disk bitlerle hiç ilgili değildir. `mkstemp` ise cevabı çekirdekten alır:
    dosya açılıp bir bayt yazılabildiyse dizin yazılabilirdir, başka bir şeye
    güvenmek gerekmez.

    NEDEN `mkstemp`, `NamedTemporaryFile` DEĞİL: yazım BAŞARISIZ olursa
    (`ENOSPC`) dosya yine de silinmeli; `mkstemp` tanıtıcıyı ve yolu ayrı
    verdiği için kapatma ve silme adımları açıkça `finally`de duruyor. Sonda
    dizinde İZ BIRAKMAZ (bekçisi tests/test_health.py).

    Dizin yoksa cevap `False`: `_lifespan` onu açar, açamadıysa ya dizin
    yaratılamıyordur ya lifespan hiç koşmamıştır — ikisi de "yazılabilir"
    değildir.
    """
    try:
        fd, yol = tempfile.mkstemp(dir=dizin, prefix=".health-", suffix=".tmp")
    except OSError:
        return False
    try:
        os.write(fd, b"ok")
    except OSError:
        return False
    finally:
        os.close(fd)
        try:
            os.unlink(yol)
        except OSError:
            pass
    return True


def _sonda_sorgusu(baglanti: Connection) -> tuple[dt.datetime | None, bool]:
    """Tek bağlantıda: `SELECT 1`, sonra işçilerin son kalbi. Döner: (son kalp, kalp okunabildi).

    `SELECT 1` düşerse istisna `db.sor`a çıkar → `None` → `db_reachable:false`;
    dönebildiyse DB ulaşılabilir. Kalp sorgusu düşerse (`isciler` yok: göç
    koşmamış) ikinci öğe `False` — DB ulaşılabilir, işçi durumu bilinmiyor.
    `rollback`: Postgres düşen ifadeden sonra transaksiyonu bozuk sayar;
    bağlantı havuza temiz dönsün.
    """
    baglanti.execute(text("SELECT 1")).scalar_one()
    try:
        return kuyruk.isci_son_kalp(baglanti), True
    except Exception:
        baglanti.rollback()
        return None, False


def isci_durumu(motor: Engine | None, an: dt.datetime | None = None) -> tuple[bool, bool | None, str | None]:
    """(`db_reachable`, `worker_alive`, `worker_last_heartbeat`) — gövdenin DB'den gelen üç alanı.

    `worker_alive` = son kalp `an - CANLI_ESIK`ten YENİ (admin metriklerinin
    `canli` ölçütüyle birebir aynı karşılaştırma). Bilinmiyorsa `None`.
    Damga `zaman.damga_utc` (UTC, `Z`): API'nin öteki damgalarıyla (`/api/isler*`,
    `/api/admin/*`) aynı biçim — dilimsiz bir değer sondayı okuyan makinenin
    saatine göre kayardı.
    """
    sonuc = db.sor(motor, _sonda_sorgusu)
    if sonuc is None:
        return False, None, None
    son_kalp, okundu = sonuc
    if not okundu:
        return True, None, None
    if son_kalp is None:
        return True, False, None
    simdi = an if an is not None else zaman.an()
    return True, son_kalp > simdi - depo_admin.CANLI_ESIK, zaman.damga_utc(son_kalp)


@router.get("/health")
def health(ayarlar: ayar.Ayarlar = Depends(ayar.genel),
           motor: Engine | None = Depends(db.motor_varsa)) -> JSONResponse:
    """Sağlık sondası: yazılabilir veri dizini VE ulaşılabilir DB → 200, değilse 503.

    `motor_varsa` (`oturum` DEĞİL): motor yokluğu bu rota için hata değil
    raporlanacak durum — `oturum` 503 fırlatır ve gövde eksik kalırdı.
    `ayar.genel` (`ayarlar` DEĞİL): sonda oturum taşımaz ve sorduğu şey
    paylaşılan veri kökünün yazılabilirliği, bir kullanıcının dizini değil.

    `Cache-Control: no-store`: bir ara vekil (reverse proxy) bu cevabı
    önbelleğe alırsa sonda dakikalarca bayat bir "sağlıklı" okur.
    """
    yazilabilir = veri_dizini_yazilabilir(ayarlar.data_dir)
    db_erisilebilir, isci_canli, son_kalp = isci_durumu(motor)
    ok = yazilabilir and db_erisilebilir
    return JSONResponse(
        {"ok": ok, "version": version.APP_VERSION,
         "data_dir_writable": yazilabilir, "db_reachable": db_erisilebilir,
         "worker_alive": isci_canli, "worker_last_heartbeat": son_kalp},
        status_code=200 if ok else 503,
        headers={"Cache-Control": "no-store"})
