# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Veri tabanı zemini — motor, istek başına `Session`, erişilebilirlik sondası (Faz 1 / 1. görev).

NEDEN VAR: çok kullanıcılı web (docs/faz1-veritabani-hesaplar.md) bugünkü
JSON depolarını PostgreSQL'e taşıyacak. Bu modül o taşımanın ZEMİNİ: tablo yok,
sorgu yok, yalnız bağlantının nereden geldiği, ne zaman kurulduğu ve bir
rotanın onu nasıl aldığı. Sonraki görevler (`services/tablolar.py`, depo
modülleri) buraya yaslanır, burası onlara dokunmaz.

ÜÇ KARAR, üçü de ölçüme dayanıyor:

* **Senkron `Session` + psycopg 3, asyncpg DEĞİL.** 46 rotanın 41'i senkron
  `def` ve zaten Starlette threadpool'unda koşuyor; async motor o 41 rotanın
  yeniden yazılmasını isterdi, kazancı yoktu (ağır iş — Pillow, 1-6 dk
  sağlayıcı çağrısı — zaten senkron ve Faz 2'de kuyruğa çıkacak). psycopg 3
  tek sürücüyle iki yolu da açık tutuyor (`postgresql+psycopg` hem `Engine`
  hem `AsyncEngine` verir); 5 `async def` rota DB'ye `run_in_threadpool` ile
  gidecek (5. görev).
* **Bağlantı dizesi `os.environ`dan, `Ayarlar`a alan EKLENMEDEN.** `Ayarlar`
  dizinlerin nesnesi (services/ayar.py) ve 4. görevde kullanıcıya göre
  değişecek; bağlantı dizesi ise süreç geneli tek bir şey. `paths.DATA_DIR_ENV`
  deyiminin aynısı: ad burada sabit, okuyan tek işlev (`baglanti_dizesi`).
* **Motor LİFESPAN'da kurulur, ithal anında DEĞİL.** `import app` bugün diske
  bile dokunmuyor (services/ayar.py, "ithal anında bağlanmaz") ve 37 test
  dosyasının `TestClient(app)`i `with`siz, yani lifespan'sız açılıyor — o
  testler Postgres'siz koşabilmeli. `app.py` `_lifespan`da `motor_kur` çağırır,
  `app.state.motor`a koyar, kapanışta `dispose` eder. `create_engine` kendisi
  bağlanmaz (ilk bağlantı ilk `connect`te); motor kurulamazsa (bozuk URL)
  uygulama yine açılır, `/health` `db_reachable:false` ile 503 der.

COMMIT NEREDE — bağımlılıkta, rota gövdesinde DEĞİL. `oturum` bir `yield`
bağımlılığı: rota başarıyla döndüyse commit, istisna fırlattıysa rollback.
Tek kural, 46 rotaya tek tek yazılmaz; `HTTPException` da istisna, yani
400/404 dönen bir rota yarım yazım bırakmaz. `OTURUM = Depends(oturum,
scope="function")` — `scope="function"` ŞART (FastAPI ≥ 0.118): öntanımlı
`request` kapsamı çıkış kodunu cevap GÖNDERİLDİKTEN sonra koşturur, yani
commit patlasa istemci çoktan 200 almış olurdu. `function` kapsamı commit'i
rota döner dönmez, cevap kurulmadan önce koşturur; commit hatası 500 olur.

`erisilebilir` — `/health`in ikinci ölçütü. `SELECT 1` ayrı bir iş
parçacığında ve `zaman_asimi` saniyede cevaplanmadıysa `False`: sonda 1 sn'de
dönmek zorunda (Docker `HEALTHCHECK --timeout=5s`, orkestratör okuyucuları),
oysa libpq'nun `connect_timeout` asgarisi 2 sn ve kara deliğe giden bir TCP
bağlantısı onu da aşabilir. Vazgeçilen iş parçacığı kendi kendine biter
(`connect_timeout` motor düzeyinde 2 sn), havuz bağlantısını da kendisi geri
verir.

HAVUZ KÜÇÜK (`pool_size=2`, `max_overflow=3`): yönetilen Postgres'lerin
bağlantı sınırı düşük (Neon/Supabase kendi pooler'ını öne koyuyor) ve bu
uygulamanın tek replikası istek başına bir bağlantıyı saniyeden kısa tutuyor.
`pool_pre_ping`: yönetilen servisler boşta kalan bağlantıyı sessizce kapatıyor;
ping olmadan ilk istek "server closed the connection" ile düşer.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as GelecekZamanAsimi

from fastapi import Depends, HTTPException, Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

# Bağlantı dizesinin ortam değişkeni — `postgresql+psycopg://kullanici:parola@konak/db`.
# `.env.example`, `compose.yaml` ve CI aynı adı kullanıyor (bekçisi
# tests/test_docker_kapisi.py). Boş dize "verilmemiş" sayılır.
DATABASE_URL_ENV = "DATABASE_URL"

# libpq `connect_timeout` asgarisi 2 sn (daha küçüğü 2'ye yuvarlanır); sondanın
# 1 sn'lik bütçesini iş parçacığı kapatıyor, bu değer vazgeçilen denemenin
# kaç saniyede kendi kendine biteceğini söylüyor.
BAGLANTI_ZAMAN_ASIMI_SN = 2

# `/health`in DB ölçütü için üst sınır — sonda bundan geç cevap vermez.
SONDA_ZAMAN_ASIMI_SN = 1.0


def baglanti_dizesi() -> str | None:
    """`DATABASE_URL` — verilmemişse ya da boşsa `None`.

    Tek okuma noktası: `app.py` lifespan'da, `alembic/env.py` göçte buradan
    okur; ikisinin ayrı ayrı `os.environ`a bakması, bir gün adın birinde
    değişip ötekinde kalması demekti.
    """
    return os.environ.get(DATABASE_URL_ENV) or None


def motor_kur(url: str) -> Engine:
    """Süreç geneli TEK motor. Bağlanmaz — ilk bağlantı ilk `connect`te.

    `connect_args={"connect_timeout": …}` psycopg'ye (libpq) gidiyor: sunucu
    yoksa istek saniyeler içinde hata alsın, sonsuza dek beklemesin.
    """
    return create_engine(
        url,
        pool_size=2,
        max_overflow=3,
        pool_pre_ping=True,
        pool_timeout=10,
        connect_args={"connect_timeout": BAGLANTI_ZAMAN_ASIMI_SN},
    )


def motor_varsa(request: Request) -> Engine | None:
    """Bu sürecin motoru — lifespan kurmadıysa (ya da URL verilmediyse) `None`.

    `/health` bunu kullanır: motor yokluğu bir HATA değil, raporlanacak bir
    DURUM (`db_reachable:false`). Rotalar `oturum`u kullanır; orada yokluk 503.
    """
    return getattr(request.app.state, "motor", None)


def erisilebilir(motor: Engine | None, zaman_asimi: float = SONDA_ZAMAN_ASIMI_SN) -> bool:
    """`SELECT 1` `zaman_asimi` saniye içinde cevaplandı mı? (gerekçe modül başında)

    Motor yoksa `False`: `DATABASE_URL` verilmemiş ya da lifespan kurulamamış
    bir süreç, veri tabanına ULAŞAMIYOR demektir — sondanın söylemesi gereken
    tam olarak bu.
    """
    if motor is None:
        return False

    def _sor() -> bool:
        with motor.connect() as baglanti:
            return baglanti.execute(text("SELECT 1")).scalar_one() == 1

    # Çağrı başına bir iş parçacığı: asılı kalan bir deneme sonraki sondayı
    # bloke etmesin. `shutdown(wait=False)`: vazgeçilen iş parçacığı libpq
    # zaman aşımında kendi biter, biz onu beklemeyiz.
    yurutucu = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kromis-db-sonda")
    try:
        return yurutucu.submit(_sor).result(timeout=zaman_asimi)
    except GelecekZamanAsimi:
        return False
    except Exception:
        # OperationalError (sunucu yok, parola yanlış), DBAPIError, ne olursa
        # olsun: sonda "ulaşılamıyor" der, sebebi uvicorn günlüğüne düşer.
        return False
    finally:
        yurutucu.shutdown(wait=False)


def oturum(request: Request) -> Iterator[Session]:
    """FastAPI bağımlılığı: istek başına bir `Session`; dönüşte commit, istisnada rollback.

    Rotanın imzasında `OTURUM` ile kullanılır (kapsam gerekçesi modül başında):

        def rota(…, db: Session = OTURUM) -> dict: …

    Motor yoksa 503: `DATABASE_URL` verilmemiş bir dağıtımda veri tabanı
    isteyen rota "sunucu hatası" (500) değil "hizmet yok" (503) demeli —
    okuyucu için fark, "kod bozuk" ile "yapılandırma eksik" arasındaki fark.
    `detail` bir KOD, cümle değil: bu modül kullanıcıya konuşmaz
    (tests/test_i18n.py sınıflandırması), cümleyi ön yüz kurar.
    """
    motor = motor_varsa(request)
    if motor is None:
        raise HTTPException(status_code=503, detail="database_unavailable")
    with Session(motor) as db:
        try:
            yield db
        except BaseException:
            db.rollback()
            raise
        else:
            db.commit()


# Rotaların kullanacağı TEK biçim — `Depends(db.oturum)` yazılmaz, çünkü
# öntanımlı kapsam commit'i cevaptan SONRAYA bırakır (gerekçe modül başında).
OTURUM = Depends(oturum, scope="function")
