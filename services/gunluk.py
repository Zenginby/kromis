# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Yapısal günlük — `kromis.*` günlükçülerine JSON satır biçimleyici, bağlam alanları, redaksiyon (Faz 2 / 9).

NEDEN VAR (ölçüldü, 2026-09-18 dumanı, Faz 2 / 8): uvicorn yalnız KENDİ
günlükçülerini (`uvicorn.*`) yapılandırır; kökte işleyici yok ve Python'un son
çare işleyicisi WARNING altını atar — `logging.getLogger("kromis.admin").info(
…)` satırı hiçbir yere yazılmıyordu. 8. görev bu modülü en küçük hâliyle
(`kromis` ad alanına tek stdout işleyicisi, düz `k=v`) doğurdu; 9. görev onu
belgenin (§9) istediği şeye çevirdi:

* **Satır başına bir JSON nesnesi** stdout'a (platform günlük toplayıcıları
  oradan okur, 12-factor; dosya yok). Alanlar: `ts` (UTC, ISO 8601), `seviye`,
  `logger`, `mesaj`, sonra BAĞLAM alanları (`istek_id`, `is_id`, `kullanici_id`
  — aşağıda), sonra kaydın kendi yapısal alanları (`olay`, `admin`, `hedef`,
  `sure_ms`, `durum`, …; `extra=` ile ya da `olay()` yardımcısıyla verilir),
  istisna varsa `hata` (iz metni). "Hangi iş ne kadar sürdü" sorusu
  `grep is_id` ile cevaplanır; toplayıcı JSON'u alanlara açar.
* **Bağlam bir `ContextVar`** (`bagla`/`coz`/`baglam`): istek ara katmanı
  (`services/istek_kimligi.py`) `istek_id`yi, işçi (`services/isci.py::kos`)
  `is_id` + `kullanici_id`yi bağlar ve o kapsamda ÜRETİLEN HER SATIR alanları
  taşır — günlük yazan yerin bağlamı bilmesi gerekmez. Deyim `services/kiraci.py`
  ve `kimlik_baglami.py`nin aynısı: async ara katman isteğin görevinde kurar,
  senkron rota iş parçacığı havuzuna bağlamın KOPYASIYLA gider ve değeri görür.
  İç içe bağlam BİRLEŞİR (istek içinde bir alt kapsam `istek_id`yi kaybetmez).
* **Redaksiyon `errlog.redact_secrets`** — AYNI işlev, ikinci bir kopya yok
  (belge §9: "her satır redact_secrets'ten geçer"). DEĞER DEĞER uygulanır,
  serileştirilmiş satıra DEĞİL: `redact_secrets`in sözlük deseni (`"AD": "değer"`)
  eşleşmeyi anahtarıyla birlikte siler ve bir JSON satırının içinde bu satırı
  geçersiz JSON'a çevirirdi (ölçüldü: `{"a": 1, [REDACTED_API_KEY]}`). Metin
  biçiminde ise satırın tamamı geçer (orada bozulacak yapı yok). Kural
  adı KEY/TOKEN/SECRET ile biten alan adları için de geçerli: böyle bir alanın
  değeri biçimi ne olursa olsun maskelenir (ad kuralı `errlog`unkinin aynısı;
  kısa/atipik bir platform anahtarı çıplak değer deseninden kaçabilir).
* **İki biçim**, `KROMIS_GUNLUK_BICIMI`: `json` (öntanımlı — web ve işçi
  platformda) ya da `metin` (yerelde okunur: `ts SEVİYE logger mesaj k=v …`).
  Bilinmeyen değer `ValueError`: sessizce JSON'a düşmek yapılandırma yazım
  hatasını gizlerdi; işçi 2 ile çıkar (`isci.es_zamanli`nın duruşu), web
  "Application startup failed" der.
* **Seviye**: INFO. Erişim satırı ve iş olayları INFO; `/health` ve `/static/*`
  erişimi DEBUG (sonda 30 sn'de bir sorar, statik dosyalar sayfa başına
  onlarca — ikisi de sinyal değil; `istek_kimligi.SESSIZ_YOLLAR`); SSE akışının
  1,5 sn'lik sorgusu ve `: kalp` yorumu (routers/isler.py) ile işçinin 1 sn'lik
  boş yoklaması HİÇ yazmaz. WARNING yalnız `uyari` olayı (kuyruk eşikleri,
  services/isci.py) ve kurulum sorunları; ERROR istisnalar.

`kur` İKİ KEZ ÇAĞRILABİLİR (testler, `TestClient(app)` her `with`te lifespan
koşturur): işleyici zaten varsa ikincisi eklenmez. `akim` parametresi test
için (StringIO); üretimde `sys.stdout`. Köke YAYILMAZ (`propagate = False` —
aynı satır iki kez basılmasın). Kullanıcıya konuşmaz: satırlar operatöre gider
(tests/test_i18n.py sınıflandırması).

KÖK GÜNLÜKÇÜ VE UVICORN (Faz 2 / 10; 9'un devri 1): `kromis.*` dışındaki her
şey — SQLAlchemy havuz uyarıları, httpx, uvicorn'un "Exception in ASGI
application" izi — 9'da stderr'e DÜZ METİN ve REDAKSİYONSUZ düşüyordu: Python'un
son çare işleyicisi WARNING+'ı olduğu gibi basar, uvicorn kendi günlükçülerine
kendi işleyicisini takar. Şimdi `kur` köke de bir işleyici takar (aynı
biçimleyici, aynı redaksiyon; kökün seviyesi WARNING kalır — üçüncü parti
INFO'su hâlâ susar) ve uvicorn'un iki günlükçüsünün (`uvicorn`, `uvicorn.error`; `uvicorn.access`
değil — sabitin yanında) işleyicilerini boşaltıp köke yayar: yaşam döngüsü
satırları (`Application startup complete`, INFO — uvicorn'un günlükçü seviyesi
INFO, kök işleyicinin seviyesi yok) ve ASGI izi (ERROR, `hata` alanında,
redakte) artık stdout'ta JSON. TEK AKIM — lifespan'dan ÖNCEKİ iki satır
(`Started server process`, `Waiting for application startup`) hariç: `kur`
henüz koşmamış, uvicorn'un stderr işleyicisi duruyor (ölçüldü, 2 satır). İşleyici `sys.stdout`u EMIT anında çözer
(`_StdoutIsleyici`): pytest her testte `sys.stdout`u değiştirir ve kuruluşta
yakalanan bir akım sonraki testte kapanmış olurdu ("I/O operation on closed
file"). Alembic'in `fileConfig`i (testler, aynı süreç) kökün işleyicilerini
SİLER; `kur` işaretli işleyiciyi görmediğinde yeniden takar. Erişim günlüğü
KAPALI (`--no-access-log`, Dockerfile) — erişim satırını `istek_kimligi`
yazar, iki satır aynı şeyi söylemesin.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
import os
import re
import sys
import traceback
from collections.abc import Iterator, Mapping
from contextvars import ContextVar, Token
from types import MappingProxyType
from typing import IO, Any

import errlog

__all__ = ["KOK", "KOK_ISARETI", "UVICORN_GUNLUKCULERI", "BICIM_ENV", "BICIM_JSON", "BICIM_METIN",
           "BICIMLER", "GIZLI_AD", "MASKE", "JsonBicimleyici", "MetinBicimleyici", "bicim",
           "bicimleyici", "kur", "kok_isleyicisi", "bagla", "coz", "baglam", "aktif", "sifirla",
           "olay", "alanlar"]

# `kromis.<alan>` — bu deponun bütün günlükçüleri bu ad altında; alan admin/istek/is/isci/platform.
KOK = "kromis"
# Kök günlükçüye taktığımız işleyicinin öznitelik işareti: `kur` ikinci kez
# çağrılınca ya da Alembic kökü silip yeniden kurunca "bizimki var mı" buradan okunur.
KOK_ISARETI = "kromis_kok_isleyicisi"
# İşleyicileri boşaltılıp köke yayılan uvicorn günlükçüleri (gerekçe modül başında).
# `uvicorn.access` YOK ve bilerek: uvicorn `--no-access-log`u o günlükçünün
# işleyicisini silip `propagate=False` yaparak uygular; onu köke yaysaydık
# kapatılan erişim satırı JSON olarak GERİ gelirdi (ölçüldü, 2026-09-19 dumanı:
# `GET /health` iki kez — bizim `olay=istek` ve uvicorn'unki). Bayrak verilmezse
# uvicorn'un erişim satırı kendi işleyicisinden düz metin gider (KURULUM.md 9).
UVICORN_GUNLUKCULERI: tuple[str, ...] = ("uvicorn", "uvicorn.error")

BICIM_ENV = "KROMIS_GUNLUK_BICIMI"
BICIM_JSON = "json"
BICIM_METIN = "metin"
BICIMLER: tuple[str, ...] = (BICIM_JSON, BICIM_METIN)

# Metin biçiminin sabit başı; yapısal alanlar ve bağlam arkasına `k=v` gelir.
_METIN_BASI = "%(asctime)s %(levelname)s %(name)s %(message)s"

# Bir `LogRecord`un STANDART öznitelikleri — bunların dışında kalan her şey
# `extra=` ile gelmiş yapısal alandır. Kümeyi elle yazmak yerine boş bir
# kayıttan türetiyoruz: CPython sürümleri arasında eklenen ad (`taskName`,
# 3.12) listeyi kendiliğinden günceller.
_STANDART_ALANLAR = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message", "asctime"}

# Değeri biçimine bakılmadan maskelenecek ALAN ADI kuralı — `errlog`un 4.
# deseninin ad yarısı (BÜYÜK_HARF + KEY/TOKEN/SECRET). Bir yapısal alan bu
# adı taşıyorsa değeri sırdır; `errlog.redact_secrets` yalnız `AD=değer`
# biçimindeki METNİ tanır, ayrı bir JSON anahtarını değil.
GIZLI_AD = re.compile(r"^[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET)$")
MASKE = "[REDACTED_API_KEY]"

_BOS: Mapping[str, Any] = MappingProxyType({})
_BAGLAM: ContextVar[Mapping[str, Any]] = ContextVar("kromis_gunluk", default=_BOS)


# ────────────────────────────────────────────────────────── bağlam

def bagla(**alanlar: Any) -> Token[Mapping[str, Any]]:
    """Bağlama alan ekler (var olanla BİRLEŞİR); dönen jeton `coz`a verilir."""
    return _BAGLAM.set(MappingProxyType({**_BAGLAM.get(), **alanlar}))


def coz(jeton: Token[Mapping[str, Any]]) -> None:
    """`bagla`nın geri alınışı — aynı görevde/iş parçacığında."""
    _BAGLAM.reset(jeton)


@contextlib.contextmanager
def baglam(**alanlar: Any) -> Iterator[None]:
    """`with gunluk.baglam(is_id=…):` — blok boyunca her satır bu alanları taşır."""
    jeton = bagla(**alanlar)
    try:
        yield
    finally:
        coz(jeton)


def aktif() -> Mapping[str, Any]:
    """Bu görevin/iş parçacığının bağlam alanları; yoksa boş."""
    return _BAGLAM.get()


def sifirla() -> None:
    """Bağlamı boşaltır — testler arası sızıntıya karşı."""
    _BAGLAM.set(_BOS)


# ────────────────────────────────────────────────────────── kayıt → alanlar

def _deger(deger: Any) -> Any:
    """JSON'a girecek değer: dize redakte, sözlük/dizi içine inilir, öteki tipler dizeye."""
    if isinstance(deger, str):
        return errlog.redact_secrets(deger)
    if isinstance(deger, bool | int | float) or deger is None:
        return deger
    if isinstance(deger, Mapping):
        return {str(k): MASKE if GIZLI_AD.match(str(k)) else _deger(v) for k, v in deger.items()}
    if isinstance(deger, list | tuple | set | frozenset):
        return [_deger(v) for v in deger]
    if isinstance(deger, dt.datetime):
        return deger.isoformat(timespec="milliseconds")
    return errlog.redact_secrets(str(deger))


def alanlar(record: logging.LogRecord) -> dict[str, Any]:
    """Kaydın yapısal alanları: önce bağlam, sonra `extra=` — ikisi de redakte. Sıra sözleşme (modül başı)."""
    sonuc: dict[str, Any] = {}
    for kaynak in (aktif(), {k: v for k, v in record.__dict__.items() if k not in _STANDART_ALANLAR}):
        for ad, deger in kaynak.items():
            sonuc[ad] = MASKE if GIZLI_AD.match(ad) else _deger(deger)
    return sonuc


def _hata_metni(record: logging.LogRecord) -> str | None:
    """`logger.exception(...)` / `exc_info=True`: izin metni (redakte). Yoksa `None`."""
    if record.exc_info:
        return errlog.redact_secrets("".join(traceback.format_exception(*record.exc_info)).rstrip())
    if record.exc_text:
        return errlog.redact_secrets(record.exc_text)
    return None


class JsonBicimleyici(logging.Formatter):
    """Satır başına bir JSON nesnesi: ts, seviye, logger, mesaj, bağlam + yapısal alanlar, hata."""

    def format(self, record: logging.LogRecord) -> str:
        satir: dict[str, Any] = {
            "ts": dt.datetime.fromtimestamp(record.created, dt.UTC).isoformat(timespec="milliseconds"),
            "seviye": record.levelname,
            "logger": record.name,
            "mesaj": errlog.redact_secrets(record.getMessage()),
        }
        satir.update(alanlar(record))
        hata = _hata_metni(record)
        if hata is not None:
            satir["hata"] = hata
        # `ensure_ascii=False`: Türkçe mesaj okunur kalsın; stdout UTF-8 (PYTHONUNBUFFERED
        # imajda, `encoding` sözleşmesi tests/test_encoding_contract.py). `default=str`:
        # `_deger` görmediği bir tip (UUID) gelirse satır yine yazılır, patlamaz.
        return json.dumps(satir, ensure_ascii=False, default=str)


class MetinBicimleyici(logging.Formatter):
    """Yerel okunur biçim: `ts SEVİYE logger mesaj k=v …`; satırın tamamı redakte."""

    def __init__(self) -> None:
        super().__init__(_METIN_BASI)

    def format(self, record: logging.LogRecord) -> str:
        bas = super().format(record)
        kuyruk = " ".join(f"{ad}={deger}" for ad, deger in alanlar(record).items())
        return errlog.redact_secrets(f"{bas} {kuyruk}" if kuyruk else bas)


# ────────────────────────────────────────────────────────── kurulum

class _StdoutIsleyici(logging.StreamHandler):
    """`StreamHandler`, akımı verilmemişse `sys.stdout`u HER EMİTTE yeniden çözen.

    Neden (modül başı): pytest `sys.stdout`u test başına değiştirir; kuruluş
    anında yakalanan nesne bir sonraki testte kapanmıştır. Sabit akım (`akim`
    verilmiş: testlerin StringIO'su) aynen tutulur.
    """

    def __init__(self, akim: IO[str] | None = None) -> None:
        self._sabit = akim
        super().__init__(akim if akim is not None else sys.stdout)

    @property
    def stream(self) -> IO[str]:
        return self._sabit if self._sabit is not None else sys.stdout

    @stream.setter
    def stream(self, deger: IO[str]) -> None:
        # `StreamHandler.__init__` ve `setStream` buraya yazar; sabit akım verilmişse onu güncelle,
        # verilmemişse yazılanı yut — dinamik `sys.stdout` kalsın.
        if self._sabit is not None:
            self._sabit = deger


def kok_isleyicisi() -> logging.Handler | None:
    """Kökteki BİZİM işleyici (işaretli), yoksa `None`."""
    for h in logging.getLogger().handlers:
        if getattr(h, KOK_ISARETI, False):
            return h
    return None


def _koku_kur(akim: IO[str] | None, bicimleyici_nesnesi: logging.Formatter) -> None:
    """Köke işaretli işleyici (yoksa) + uvicorn günlükçülerini köke yay (gerekçe modül başında)."""
    if kok_isleyicisi() is None:
        isleyici = _StdoutIsleyici(akim)
        isleyici.setFormatter(bicimleyici_nesnesi)
        setattr(isleyici, KOK_ISARETI, True)
        # Seviye YOK (NOTSET): süzgeç günlükçüde — kökün WARNING'i üçüncü partiyi
        # susturur, uvicorn'un INFO'su kendi günlükçüsünün seviyesiyle geçer.
        logging.getLogger().addHandler(isleyici)
    for ad in UVICORN_GUNLUKCULERI:
        gunlukcu = logging.getLogger(ad)
        gunlukcu.handlers.clear()
        gunlukcu.propagate = True
        # Alembic `fileConfig` (testlerde aynı süreç) var olan günlükçüleri KAPATIR; `kromis.*` için
        # `kur` ne yapıyorsa uvicorn'unkiler için de: yoksa yaşam döngüsü satırı sessizce yutulur.
        gunlukcu.disabled = False


def bicim(ortam: Mapping[str, str] | None = None) -> str:
    """`KROMIS_GUNLUK_BICIMI` — boşsa `json`; tanınmayan değer `ValueError` (gerekçe modül başında)."""
    ortam = os.environ if ortam is None else ortam
    deger = (ortam.get(BICIM_ENV) or BICIM_JSON).strip().lower()
    if deger not in BICIMLER:
        raise ValueError(f"{BICIM_ENV}={deger!r}: beklenen {', '.join(BICIMLER)}")
    return deger


def bicimleyici(ad: str) -> logging.Formatter:
    """Biçim adı → biçimleyici nesnesi."""
    return MetinBicimleyici() if ad == BICIM_METIN else JsonBicimleyici()


def kur(akim: IO[str] | None = None, *, bicim_adi: str | None = None) -> logging.Logger:
    """`kromis` günlükçüsünü INFO'da, tek stdout işleyicisiyle kurar; kurulmuşsa dokunmaz. Günlükçüyü döner.

    `bicim_adi` verilmezse ortamdan (`bicim()`); tanınmayan değer buradan
    `ValueError` olarak çıkar — çağıran (web lifespan, `isci.py`) karar verir.
    """
    kok = logging.getLogger(KOK)
    if not kok.handlers:
        isleyici: logging.Handler = _StdoutIsleyici(akim)
        isleyici.setFormatter(bicimleyici(bicim_adi or bicim()))
        kok.addHandler(isleyici)
    kok.setLevel(logging.INFO)
    kok.propagate = False
    # Kök + uvicorn (Faz 2 / 10): aynı biçimleyici nesnesi — biçim adı ortamdan bir kez okundu.
    _koku_kur(akim, kok.handlers[0].formatter or bicimleyici(bicim_adi or bicim()))
    # Aynı süreçte koşan Alembic `fileConfig` (testler) daha önce yaratılmış günlükçüleri
    # kapatabilir; kurulum onları yeniden açar — üretimde göç ayrı süreç, zararsız.
    kok.disabled = False
    for ad, gunlukcu in logging.Logger.manager.loggerDict.items():
        if ad.startswith(KOK + ".") and isinstance(gunlukcu, logging.Logger):
            gunlukcu.disabled = False
    return kok


def olay(gunlukcu: logging.Logger, ad: str, mesaj: str | None = None, *,
         seviye: int = logging.INFO, **degerler: Any) -> None:
    """Yapısal olay: `olay=<ad>` + alanlar; `mesaj` verilmezse olay adı. `extra=` yazımının kısa hâli.

    Sondaki alt çizgi DÜŞER (`is_=…` → `"is"`): `is` Python anahtar sözcüğü,
    anahtar-argüman olarak yazılamıyor; alan adı yine 8. görevin `k` anahtarı.
    """
    gunlukcu.log(seviye, mesaj if mesaj is not None else ad,
                 extra={"olay": ad, **{k.rstrip("_"): v for k, v in degerler.items()}})
