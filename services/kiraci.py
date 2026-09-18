# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kiracı bağlamı — RLS politikasının okuduğu `app.kullanici_id` / `app.rol` ayarlarının kaynağı (Faz 2 / 7).

İKİNCİ KAT: uygulama süzgeci (`services/depo_*`nin `kullanici_id` parametresi,
bekçisi tests/test_galeri_db.py) bir AST bekçisiyle korunuyor, ama bekçi yalnız
depo imzalarını görür — ham `select(Medya)` yazan bir rota ya da araç ondan
kaçar. Göç `0006_rls` sekiz iş tablosuna (`IS_TABLOLARI`) Postgres politikası
koyar: satır ancak `kullanici_id = current_setting('app.kullanici_id')` ise
görünür/yazılır; `app.rol = 'admin'` hepsini OKUR ve GÜNCELLER (silmez,
eklemez). Politika SORGUYU değil BAĞLANTIYI kısıtlar: süzgeç unutulursa sonuç
boş, sızıntı değil (docs/faz2-kuyruk-anahtarlar-depolama.md §7).

BU MODÜL politikanın uygulama tarafı: "bu transaksiyon KİMİN adına?" sorusunun
tek cevabı. Bir `ContextVar` (deyim `kimlik_baglami.py`nin aynısı — async
bağımlılık isteğin görevinde kurar, senkron rota iş parçacığı havuzuna
bağlamın KOPYASIYLA gider ve değeri görür; anyio `run_sync`) ve bağlamı
Postgres'e yazan tek ifade (`uygula`). Ayar `SET LOCAL` gücünde
(`set_config(..., true)`): TRANSAKSİYONLA biter, havuza dönen bağlantı bir
sonraki transaksiyona kiracı taşımaz — pooler'ın transaksiyon kipi
(Supavisor/pgbouncer) bunu geçirir, oturum kipinde de sorun yok.

ÜÇ YAZAR:

* `services/db.py` — `Session` `after_begin` olayında `uygula(baglanti)`:
  bağlam VARSA transaksiyonun ilk ifadesi bağlamdır. Bağlam yoksa hiçbir şey
  yazmaz: açık rotalar (`/health`, `/giris`, hesap uçları) hesap tablolarında
  çalışır, onlar politikasız; iş tablosuna bağlamsız giden bir sorgu 0 satır.
* `services/kimlik.py` — kullanıcı çözüldüğünde `bagla(kullanici_id=…)` VE
  `uygula(db)`: kimlik sorgusu (`oturumlar ⋈ kullanicilar`) transaksiyonu
  ÇOKTAN başlatmış, `after_begin` geçmiş; bağlam aynı transaksiyona sonradan
  yazılır. Test override'ı (tests/conftest.py `kullanici`) `kimlik.bagla`yı
  çağırıyor, yani orada da bağlanır ve ilk sorgu `after_begin`den geçer.
* `services/isci.py` — işçi platformun, ama HER İŞ BİR KİRACININ: `siradakini_al`
  ve `kalp_turu` `rol=ADMIN` ile (kuyruğun başı kimin olursa olsun alınır;
  bayat düşürme bütün kiracılar), `kos` işin `kullanici_id`siyle koşar —
  BYPASSRLS DEĞİL: işçi yanlışlıkla ham bir sorgu yazsa yine tek kiracının
  satırını görür. `tools/*` da aynı iki yolu kullanır (artik_dosya,
  anahtar_dondur, kullanici → admin; ice_aktar → aktarılan kullanıcı, çünkü
  admin politikası INSERT vermez ve araç tek bir hesabın satırlarını yazar).

KÖKTE ve YAPRAK (depo modülü ithal etmiyor): `db.py` bunu ithal ediyor,
`kimlik.py`/`isci.py` de; tersi bir kenar döngü olurdu. Kullanıcıya konuşmaz
(tests/test_i18n.py sınıflandırması): ayar adları ve `set_config` ifadesi
ASCII, cümle yok.

BOŞ DEĞER `''`, NULL DEĞİL: `set_config(ad, NULL, true)` sürümler arasında
farklı davranıyor (eski sürümde hata, yenisinde boş dize) — modül her zaman
dize yazar ve politika `NULLIF(current_setting(...), '')::uuid` ile boş dizeyi
de "bağlı değil" sayar; bağlam yokken bile `''::uuid` dönüşüm hatası
üretilmez (test: `test_an_empty_setting_yields_no_rows_instead_of_a_cast_error`).
"""
from __future__ import annotations

import contextlib
import dataclasses
import uuid
from collections.abc import Iterator
from contextvars import ContextVar, Token

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

__all__ = ["ADMIN", "AYAR_KULLANICI", "AYAR_ROL", "IS_TABLOLARI", "Baglam",
           "bagla", "coz", "aktif", "sifirla", "baglam", "uygula"]

# `app.rol`un tek anlamlı değeri. Politika bu dizeyle karşılaştırıyor (0006_rls);
# 8. görevin `kimlik.admin_kullanici` bağımlılığı da bunu bağlar.
ADMIN = "admin"

# Politikanın okuduğu iki oturum ayarı. Nokta ŞART: Postgres özel (`custom`)
# ayarları yalnız `onek.ad` biçiminde kabul eder; `ALTER SYSTEM`/`postgresql.conf`
# gerekmez, `set_config` ilk yazımda yaratır.
AYAR_KULLANICI = "app.kullanici_id"
AYAR_ROL = "app.rol"

# RLS'in kapsadığı SEKİZ iş tablosu — `kullanici_id` taşıyan ve hesap tablosu
# olmayan her tablo (Faz 1'in yedisi + `isler`). Elle tutulan liste; bekçisi
# tests/test_rls.py: `services/tablolar.py` metadata'sından türetilen küme,
# göç dosyasının literali ve DB'deki `pg_class.relforcerowsecurity` üçü aynı
# olmak zorunda (CLAUDE.md §5 — listede olmayan tablo muaf demek, o yüzden
# liste metadata'yla karşılaştırılır). Hesap tabloları (`kullanicilar`,
# `oturumlar`, `jetonlar`, `giris_denemeleri`) ve `isciler` politikasız:
# kimlik çözülmeden koşan sorgular oradadır ve `kullanicilar.gunluk_kredi_tavani`
# yazımı 8. görevin sütun düzeyi GRANT'ına kalır (belge §6 devir).
IS_TABLOLARI: tuple[str, ...] = ("klasorler", "medya", "sohbetler", "paletler", "varliklar",
                                 "tercihler", "saglayici_kimlikleri", "isler")

# İki ayarı TEK ifadede yazar (bir gidiş-dönüş). `set_config(..., true)` = SET
# LOCAL: transaksiyon sonunda düşer. `SET` bind parametresi almıyor; `set_config`
# alıyor — uuid dize olarak gider, SQL birleştirmesi yok.
_UYGULA = text(f"SELECT set_config('{AYAR_KULLANICI}', :kullanici, true), "
               f"set_config('{AYAR_ROL}', :rol, true)")


@dataclasses.dataclass(frozen=True)
class Baglam:
    """Bir transaksiyonun kiracısı: kullanıcı, admin ya da ikisi (admin rotası kendi satırını da görür)."""
    kullanici_id: uuid.UUID | None = None
    rol: str | None = None

    def parametreler(self) -> dict[str, str]:
        return {"kullanici": str(self.kullanici_id) if self.kullanici_id is not None else "",
                "rol": self.rol or ""}


_AKTIF: ContextVar[Baglam | None] = ContextVar("kromis_kiraci", default=None)


def bagla(*, kullanici_id: uuid.UUID | None = None, rol: str | None = None) -> Token[Baglam | None]:
    """Bağlamı kurar; dönen jeton `coz`a verilir. İkisi de `None` ise bağlam "bağlı değil"."""
    if kullanici_id is None and rol is None:
        return _AKTIF.set(None)
    return _AKTIF.set(Baglam(kullanici_id=kullanici_id, rol=rol))


def coz(jeton: Token[Baglam | None]) -> None:
    """`bagla`nın geri alınışı — aynı görevde/iş parçacığında."""
    _AKTIF.reset(jeton)


def aktif() -> Baglam | None:
    """Bu görevin kiracısı; bağlanmamışsa `None` (politika altında 0 satır)."""
    return _AKTIF.get()


def sifirla() -> None:
    """Bağlamı boşaltır — testler arası sızıntıya karşı (tests/conftest.py)."""
    _AKTIF.set(None)


@contextlib.contextmanager
def baglam(*, kullanici_id: uuid.UUID | None = None, rol: str | None = None,
           oturum: Session | None = None) -> Iterator[Baglam | None]:
    """`with kiraci.baglam(kullanici_id=…):` — bloğun süresince bağlı, çıkışta HER yolda çözülür.

    İşçinin deyimi: aynı iş parçacığı art arda iki kiracının işini koşturur;
    `finally`siz bir bağlama A'nın işinden sonra B'nin işini A olarak yazardı
    (kimlik_baglami'nin `[A, B]` dersi, Faz 1 / 7).

    `oturum` verilmişse bağlam ona hemen `uygula`nır: çağıran o oturumu daha
    önce kullanmış olabilir (transaksiyon açık, `after_begin` geçmiş) — işçinin
    `siradakini_al`/`kalp_turu`su ve `ice_aktar`ın `kullanici_bul`dan sonraki
    yazımı. Taze oturumda `uygula` susar ve kancaya bırakır.
    """
    jeton = bagla(kullanici_id=kullanici_id, rol=rol)
    try:
        if oturum is not None:
            uygula(oturum)
        yield _AKTIF.get()
    finally:
        _AKTIF.reset(jeton)


def uygula(hedef: Session | Connection) -> bool:
    """Bağlamı `hedef`in AÇIK transaksiyonuna yazar; yazıldıysa `True`.

    Bağlam yoksa yazmaz (`False`): bağlamsız bir transaksiyonda ayar hiç
    yaratılmaz, `current_setting(…, true)` NULL döner, politika 0 satır.

    `Session` verilmiş ve henüz transaksiyonu YOKSA da yazmaz: ilk ifade
    transaksiyonu başlatacak ve `services/db.py`nin `after_begin` kancası
    bağlamı o anda yazacak — burada yazmak aynı ifadeyi iki kez göndermek
    olurdu. Transaksiyon açıksa (kimlik sorgusu geçmiş: `kimlik._coz`; ya da
    çağıran aynı oturumu önceden kullanmış: `isci.siradakini_al`in `db`si)
    kanca çoktan geçti, ayar BURADAN yazılır. `Connection` her zaman yazar
    (çağıran transaksiyonu kendi yönetiyor).
    """
    b = _AKTIF.get()
    if b is None:
        return False
    if isinstance(hedef, Session) and not hedef.in_transaction():
        return False
    hedef.execute(_UYGULA, b.parametreler())
    return True
