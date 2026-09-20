# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İşçi mantığı — al → üret → yaz → bitir; rotanın gövdesi, istek olmadan (Faz 2 / 3. görev).

Bugün `routers/uretim.py`nin dört rotası sağlayıcıyı isteğin İÇİNDE çağırıyor
(1-6 dk açık bağlantı; sekme yenilenirse iş kayıp). Bu modül o gövdeyi bir
`isler` satırından okuyarak koşturur: `kos(is)` bir işi sonuna götürür,
`tek_tur(db, depo)` kuyruktan bir iş alıp `kos`u çağırır. Süreç kabuğu
(`isci.py`, kökte) iş parçacıklarını, kalp atışını ve SIGTERM'i bilir; burası
bilmez — testler süreci değil bu işlevleri çağırır (belge §3: "testlerde
işçi süreç DEĞİL işlev").

`istek` SÖZLEŞMESİ (JSONB; rota 4. görevde yazar, işçi okur — rota kaydı
`istek`e ne koyarsa iş onunla koşar, sonradan silinen palet/klasör işi
değiştirmez):

    ortak     : prompt, size, quality, n, folder_id, session_id
    generate  : + arena_id, palette (pal sözlüğü ya da null), prompt_sent
    edit      : + girdiler [{"ad": "x.png", "anahtar": "<depo yolu>"}, …] (ilk = ana
                referans), parent_id, palette, prompt_sent
    video     : + duration
    animate   : + girdiler (ilk kare), parent_id, duration, son_kare {"ad", "anahtar"} | null

`prompt_sent` ROTANIN hesabı (`palet.palette_prompt`): işçi yeniden
hesaplamaz — hesap kullanıcının O ANKİ paletine bağlı ve palet sonradan
silinse sonuç değişmemeli. Sağlayıcıya `prompt_sent` (yoksa `prompt`) gider;
`medya.prompt_sent` sütununa yalnız palet gerçekten uygulandıysa yazılır
(`storage.save`in "yalnızca farklıysa" sözleşmesi, rotadaki `if pal and
pal["applied"]` aynen). Model `isler.model` sütunundan (rota doğruladı ve
normalleştirdi). Kredi GERÇEK `catalog.cost_for` (görsel/video başına);
`isler.kredi_tahmini` sıraya girerken yazılmış TAHMİN, işçi ona bakmaz.

SIRA: nesne yaz → `depo_medya.kaydet` satırı (flush) → `kuyruk.bitir` →
`defter.onayla` → TEK commit. Satır ya da commit düşerse yazılan nesneler
`depo.sil` ile TELAFİ edilir ve iş `hata` — Faz 1 / 5'in "dosya + satır
atomik değil" borcu burada kapanır: web rotası akışın iki ucunu tutamıyordu (commit bağımlılıkta, rota
döndükten sonra), işçi tutuyor. Telafi `_YazimIzi` ile: `kaydet` dosya adını
kendi üretiyor ve flush düşerse adı çağırana hiç söyleyemez; yazılan her
yolu depo sarmalayıcısı kaydeder, düşüşte hepsi silinir. `bitir` `False`
dönerse (iş bu arada bayat düşürülmüş, `kalp_atisi` susmuş) sonuç yazılmaz,
nesneler yine silinir, iş `hata`da kalır — geç kalan işçi bayat işi
diriltemez (kuyruk.py'nin `WHERE` kararı).

SAĞLAYICI ÇAĞRISI SIRASINDA `Session` AÇIK DEĞİL. `kos` işi alınmış
(`calisiyor`, commit'lenmiş) bir satır olarak alır; kullanıcı ve kimlikleri
kısa bir oturumda okur ve kapatır; çağrıyı bağlantısız yapar; sonucu yeni
bir oturumda yazar. Çağrı dakikalarca sürüyor ve havuz küçük (services/db.py):
çağrı boyunca tutulan bir bağlantı, öteki iş parçacıklarının alımını
bekletirdi. Bekçisi tests/test_isci.py (çağrı anında `pool.checkedout() == 0`).

BAĞLAMLAR İŞ BAŞINA. `kimlik_baglami.bagla(depo_kimlik_bilgisi.oku(...))`:
adaptörler kimliği TEMBEL çözüyor (`credentials=None` → isteğin bağlamı;
providers._azure_generate'in 104 testlik dersi) ve işçi bir istek değil — bağlamı
kendisi kurar, `finally`de kendisi çözer. Çözmeyi unutmak iki kullanıcının
işini art arda koşturan bir iş parçacığında A'nın anahtarıyla B'nin işini
göndermek demek; bekçisi `[A, B]` testi (Faz 1 / 7'nin ikizi). Dil de öyle:
`hata` sütunu KULLANICIYA gösterilecek, sağlayıcı hatasının metni
(`map_error`) `i18n.active()`ten okuyor → `kullanicilar.dil`, seçmemişse ürünün
öntanımlısı (`i18n.DEFAULT`: "kullanıcı seçmemiş" sorusunun cevabı; `FALLBACK`
"kullanıcı yok" demek ve burada kullanıcı var). İş bitince `set_active(None)`.

KREDİ DEFTERİ (Faz 3 / 2; docs/faz3-kredi-defteri-filigran.md §2, K2): rota
platform anahtarlı işin TAHMİNİNİ sıraya girerken rezerve etti; işçi burada
kapatır. `bitti` → `kredi_gercek = Σ medya.credits` (`_kredi` × yazılan kayıt)
`kuyruk.bitir(kredi_gercek=)` ile satıra ve `defter.onayla` ile deftere AYNI
commit'te — iş `bitti` olup farkı iade edilmemiş bir ara durum yok. `hata`
(sağlayıcı ya da yazım hatası) → `_dusur` içinde `defter.iade` (rezervin
tamamı, `kuyruk.dusur`la aynı commit). Bayat düşürme → `kalp_turu` düşürdüğü
her işi admin bağlamında iade eder (`yonetici_ekler`, K4). `iade` idempotent:
bayat düşürülmüş bir işin işçisi sonra `_dusur` derse ikinci çağrı no-op.
BYOK iş (K3) rezerv taşımaz: `onayla`/`iade` rezerv bulamaz, `None` döner —
işçi kaynağa bakmaz, defter karar verir.

YENİDEN DENEME YOK (K8): sağlayıcı çağrısı faturalanır ve düşen bir işçinin
çağrıyı gönderip göndermediği bilinemez. `ac.ImageError` → `hata` (metin
`kuyruk.dusur`da redakte edilir — yazan yerde); başka istisna → `hata` + KOD
(`BEKLENMEYEN_HATASI: <TürAdı>`, mesaj DEĞİL: mesaj yol ve parametre taşıyabilir)
+ izi `hata.log`a (`errlog.safe_append`). Eksik girdi nesnesi (`DosyaYok`)
kullanıcıya konuşan bir hata: rotanın 404 metniyle (`err.source_image_missing`)
`ImageError` olarak yükseltilir — bu modül bu tek yerde kullanıcıya konuşur
(tests/test_i18n.py sınıflandırması).

Girdi nesneleri (`girdiler`, `son_kare`) iş bitince SİLİNMEZ — karar 4.
görevin (rota yazıyor, "yeniden gönder" aynı nesneleri kullanabilir;
`artik_dosya.py` `isler/` önekini tarar). İşçi yalnız okur.

KİRACI BAĞLAMI, İKİ ROL (Faz 2 / 7, RLS): işçi platformun ama her iş bir
kiracının. Kuyruk tarafı — `siradakini_al` (`kuyruk.al`: kuyruğun başı kimin
olursa olsun) ve `kalp_turu` (bütün kiracıların bayat işleri) — `app.rol =
'admin'` ile koşar: admin politikası `isler`de SELECT + UPDATE verir, ikisinin
ihtiyacı tam bu. `kos` ise işin `kullanici_id`sini bağlar: kimlik okuması,
medya satırı ve `bitir`/`dusur` o kiracının transaksiyonlarında — işçiye
BYPASSRLS verilmedi, çünkü o zaman işçide yazılan ham bir sorgu yine her
kiracıyı görürdü; bağlı işçi yanlışlıkla bile tek kiracının satırına dokunur.
Bağlam `kiraci.baglam(...)` ile ve `with` içinde: aynı iş parçacığı bir
sonraki işi başka kiracı için koşturur (yukarıdaki `[A, B]` dersi).

KALP TURU satırı bulamazsa (`isci_kalp` `False`) ve çağıran kimliği
vermişse (`kayit`) satırı aynı `id`yle YENİDEN YAZAR: `olu_iscileri_sil`
yaşayan bir işçinin satırını da götürebilir (5 dk kalp atamamış — DB
kesintisi, uzun duraklama — ya da dağıtımda boşalan eskinin satırını yeni
işçinin açılış turu silmiş). Süreç yaşıyor ve iş koşturuyorsa `/health`
onu ölü göstermemeli; `KalpOzeti.yeniden_kaydoldu` çağırana söyler, olay
oradan (`isci.py`, `olay=isci.yeniden_kaydoldu`).

BAKIM TURU (Faz 2 / 10): `bakim_turu` işçinin AYRI bakım iş parçacığında
AÇILIŞTA ve sonra `BAKIM_ARALIGI_SN`de (5 dk) bir koşar — kalp iş
parçacığında değil (bir tur nesne başına ağa çıkar ve dakikalar sürebilir;
kalp o sürede susarsa eldeki işler bayat düşer — gerekçe `isci.py` başında),
ayrı cron da yok, işçi zaten sürekli koşan tek süreç. Üç iş: (1) SAKLAMA — kapanmış ve `bitti` 30 günden
(`KROMIS_IS_SAKLAMA_GUN`) eski `isler` satırları silinir; sahipler admin
bağlamında bulunur (`kuyruk.saklama_sahipleri`), satırlar HER KİRACININ KENDİ
bağlamında silinir (`kuyruk.eskileri_sil`: admin politikası DELETE vermez,
0006_rls); (2) GİRDİ NESNELERİ — silinen işin `isler/<id>/` dizini ancak ona
bakan hiçbir satır kalmadığında silinir: "yeniden gönder" (Faz 2 / 5) eski
işin girdilerine REFERANS verir, kopyalamaz; kalan satırların referansları
(`kuyruk.girdi_referanslari`) ve dizinin kendi satırı (`kuyruk.mevcut_isler`)
sorulur, ikisi de yoksa `depo.listele(onek)` → `depo.sil` — aday dizinin
KİRACISI silinen işin sahibi değilse (`ayar.is_dizini_coz`) aday bile
olmaz, `olay=bakim.yabanci_dizin` (WARNING) düşer: `istek`i bugün yalnız
sunucu yazıyor ve yeniden gönderim sahibin anahtarlarını kopyalıyor, yani
bu dal bugün boş; derinlikli savunma, bir gün bir anahtar sızsa saklama
başka kiracının dizinini silmesin; (3) ÖLÜ İŞÇİ
SATIRLARI — `son_kalp` kalp eşiğinden eski `isciler` satırı silinir
(`kuyruk.olu_iscileri_sil`): SIGKILL/`kill_timeout` aşımıyla ölen işçi kendi
satırını silemez ve `/health` `worker_alive:false` sonsuza dek kalırdı (9'un
devri); açılıştaki tur bunu YENİ işçi kalkar kalkmaz kapatır — tek işçili
dağıtımda (K11) ölü satırı silecek başka işçi yok. Bayat İŞ düşürme buraya
TAŞINMADI: `kalp_turu` onu 30 sn'de bir zaten yapıyor (belge 5 dk der; daha
sık olması kullanıcıya daha erken "hata" demek, bedeli yok). `medya`ya
dokunulmaz (`isler.sonuc` yalnız id listesi).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import logging
import os
import time
import traceback
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any, NamedTuple

from sqlalchemy.orm import Session

import azure_client as ac
import catalog
import errlog
import i18n
import kimlik_baglami
import providers
from services import (
    ayar,
    defter,
    depo_kimlik_bilgisi,
    depo_medya,
    dil,
    dosya,
    filigran,
    gunluk,
    hata_izleme,
    kiraci,
    kuyruk,
    platform_anahtari,
    saglayici_meta,
    zaman,
)
from services.nesne_depo import Nesne
from services.planlar import PLAN_VARSAYILAN, PLANLAR
from services.tablolar import (
    IS_TURLERI,
    Is,
    Kullanici,
)

__all__ = ["ES_ZAMANLI_ENV", "ES_ZAMANLI_VARSAYILAN", "KALP_ESIGI_ENV", "KALP_ESIGI_VARSAYILAN",
           "SAKLAMA_ENV", "SAKLAMA_VARSAYILAN_GUN", "BAKIM_ARALIGI_SN",
           "KALP_ARALIGI_SN", "YOKLAMA_ARALIGI_SN", "BEKLENMEYEN_HATASI", "KULLANICI_YOK_HATASI",
           "UYARI_KUYRUK_DERINLIGI", "UYARI_EN_ESKI_BEKLEYEN_SN",
           "es_zamanli", "kalp_esigi", "saklama", "siradakini_al", "kos", "tek_tur", "kalp_turu",
           "KalpOzeti", "kuyruk_uyarisi", "bakim_turu", "BakimOzeti"]

# Aynı anda kaç iş (iş parçacığı) — `.env.example`, `compose.yaml` ve `isci.py`
# aynı adı buradan okur (bekçisi tests/test_docker_kapisi.py `ALTYAPI`).
ES_ZAMANLI_ENV = "KROMIS_ISCI_ES_ZAMANLI"
ES_ZAMANLI_VARSAYILAN = 4
# Kalbi bu kadar saniye susan `calisiyor` iş `hata` sayılır (K8; kuyruk.bayatlari_dusur).
# 300: en uzun sağlayıcı çağrısı 600 sn ama kalp çağrının İÇİNDE, ayrı iş
# parçacığında 30 sn'de bir atıyor — 10 atış kaçırmak işçinin öldüğü demek.
KALP_ESIGI_ENV = "KROMIS_IS_KALP_ESIGI_SN"
KALP_ESIGI_VARSAYILAN = 300
# Kapanmış iş satırı bu kadar gün sonra silinir (belge §10: 30; Faz 4'ün KVKK
# saklama kararı `istek.prompt`u da kapsar, kesin süre orada). `.env.example`
# ve `ALTYAPI` bekçisi aynı adı buradan okur.
SAKLAMA_ENV = "KROMIS_IS_SAKLAMA_GUN"
SAKLAMA_VARSAYILAN_GUN = 30
# Kalp atışı aralığı ve boş kuyrukta yoklama aralığı (belge §3: 30 sn / 1 sn;
# `LISTEN/NOTIFY` yok — senkron sürücüde ayrı bağlantı ister, 1 sn dakikalık işte görünmez).
KALP_ARALIGI_SN = 30.0
YOKLAMA_ARALIGI_SN = 1.0
# Bakım turunun aralığı (belge §10: 5 dk). Sabit, ortamdan değil: saklama ve
# ölü satır silme dakikalarla ölçülür, ayarlanacak bir şey yok; testler ve duman
# `isci.py --bakim-araligi` ile kısaltır.
BAKIM_ARALIGI_SN = 300.0

# `hata` sütununa yazılan KODLAR — cümle değil (kuyruk.BAYAT_HATASI'nın duruşu):
# cümleyi ön yüz kurar, metin sızıntı taşımasın diye istisna MESAJI değil TÜRÜ yazılır.
BEKLENMEYEN_HATASI = "beklenmeyen hata"
KULLANICI_YOK_HATASI = "kullanici yok"

# Uyarı eşikleri (docs/isletme.md § 6, Faz 2 / 9): kuyruk derinliği BUNDAN ÇOK ya
# da en eski bekleyen BUNDAN ESKİ ise kalp turu `olay=uyari` (WARNING) düşürür —
# işçi yetişmiyor ya da hiç yok. Sentry'de bu satıra bağlı uyarı kuralı
# sahibin panelinde (belge §9 "Sahibin adımı"). Sabit, ortamdan değil: eşikler
# belgenin sayısı; değişirse belgeyle birlikte değişsin.
UYARI_KUYRUK_DERINLIGI = 20
UYARI_EN_ESKI_BEKLEYEN_SN = 10 * 60

# İş olaylarının günlükçüsü (`is.alindi/basladi/bitti/hata`, `uyari`); işleyici ve
# biçim `kromis` kökünde (gunluk.kur — web lifespan'ı ve `isci.py` kurar).
_gunluk = logging.getLogger("kromis.is")


class _IsArtikCalismiyor(Exception):
    """`kuyruk.bitir` 0 satır: iş bu arada `hata`ya düşmüş (bayat), sonuç yazılamaz."""


# ────────────────────────────────────────────────────────── ortam

def _tam_sayi(ortam: Mapping[str, str], ad: str, varsayilan: int) -> int:
    ham = (ortam.get(ad) or "").strip()
    if not ham:
        return varsayilan
    try:
        deger = int(ham)
    except ValueError as e:
        raise ValueError(f"{ad} tam sayi olmali, verilen: {ham!r}") from e
    if deger < 1:
        raise ValueError(f"{ad} en az 1 olmali, verilen: {deger}")
    return deger


def es_zamanli(ortam: Mapping[str, str] | None = None) -> int:
    """`KROMIS_ISCI_ES_ZAMANLI` (öntanımlı 4); boş/yok → öntanımlı, bozuk/0 → `ValueError` (işçi açılmaz)."""
    return _tam_sayi(os.environ if ortam is None else ortam, ES_ZAMANLI_ENV, ES_ZAMANLI_VARSAYILAN)


def kalp_esigi(ortam: Mapping[str, str] | None = None) -> dt.timedelta:
    """`KROMIS_IS_KALP_ESIGI_SN` (öntanımlı 300) — `kuyruk.bayatlari_dusur`un eşiği."""
    return dt.timedelta(seconds=_tam_sayi(os.environ if ortam is None else ortam,
                                          KALP_ESIGI_ENV, KALP_ESIGI_VARSAYILAN))


def saklama(ortam: Mapping[str, str] | None = None) -> dt.timedelta:
    """`KROMIS_IS_SAKLAMA_GUN` (öntanımlı 30) — `bakim_turu`nun saklama süresi; bozuk/0 → `ValueError`."""
    return dt.timedelta(days=_tam_sayi(os.environ if ortam is None else ortam,
                                       SAKLAMA_ENV, SAKLAMA_VARSAYILAN_GUN))


# ────────────────────────────────────────────────────────── alım

def siradakini_al(db: Session, isci_id: uuid.UUID, an: dt.datetime) -> Is | None:
    """`kuyruk.al` + commit; satırı oturumdan AYIRIP döndürür (kuyruk boşsa `None`).

    `expunge` commit'ten ÖNCE: `expire_on_commit` oturumdaki her nesneyi
    süresi geçmiş sayar ve ilk öznitelik okuması yeni bir bağlantı açardı —
    tam da sağlayıcı çağrısı sırasında. Ayrılmış nesne RETURNING'in doldurduğu
    sütunları taşır, DB'ye bir daha sormaz. Commit alımı kalıcı kılar: bu
    işçi düşerse satır `calisiyor`da kalır ve bayat düşürme onu `hata` yapar
    (K8), `bekliyor`a dönmez.

    `app.rol = 'admin'` ile (RLS, Faz 2 / 7): kuyruğun başı herhangi bir
    kiracının; sahip politikası altında işçi yalnız bağlı kullanıcının işini
    görürdü, bağlamsız hiçbirini. `oturum=db`: çağıran `db`yi daha önce
    kullanmışsa transaksiyon açıktır ve `after_begin` kancası geçmiştir
    (testlerin `db_oturumu`su; işçi döngüsü her turda taze oturum açar, orada
    kanca yeter).
    """
    with kiraci.baglam(rol=kiraci.ADMIN, oturum=db):
        is_ = kuyruk.al(db, isci_id, an)
        if is_ is None:
            db.rollback()
            return None
        db.expunge(is_)
        db.commit()
    # `is_id` bağlam DEĞİL, alan: bağlamı `kos` kurar (alım ile koşum ayrı çağrılar).
    # `bekleme_ms`: sıraya girişten alınışa — "işçi yetişiyor mu" sorusunun ham sayısı.
    gunluk.olay(_gunluk, "is.alindi", is_id=str(is_.id), kullanici_id=str(is_.kullanici_id),
                tur=is_.tur, model=is_.model, isci_id=str(isci_id),
                bekleme_ms=round((an - is_.olusturuldu).total_seconds() * 1000))
    return is_


# ────────────────────────────────────────────────────────── telafi izi

class _YazimIzi:
    """`Depo`yu sarar, `yaz`ılan her yolu kaydeder — düşüşte `geri_al` hepsini siler.

    `depo_medya.kaydet` dosya adını içinde üretiyor (`uuid4().hex`) ve satırın
    `flush`u düşerse adı çağırana söyleyemez; nesne çoktan yazılmış olur.
    Sarmalayıcı adı yazım anında görür. Öteki yöntemler aynen devredilir —
    `kaydet` yalnız `yaz` çağırıyor, ama protokol tam dursun.
    """

    def __init__(self, depo: dosya.Depo) -> None:
        self._depo = depo
        self.yazilanlar: list[str] = []

    def yaz(self, yol: str, veri: bytes, mime: str) -> None:
        self._depo.yaz(yol, veri, mime)
        self.yazilanlar.append(yol)

    def oku(self, yol: str) -> bytes:
        return self._depo.oku(yol)

    def oku_akis(self, yol: str) -> Iterator[bytes]:
        return self._depo.oku_akis(yol)

    def sil(self, yol: str) -> bool:
        return self._depo.sil(yol)

    def var(self, yol: str) -> bool:
        return self._depo.var(yol)

    def url(self, yol: str, sure: int, *, indirme_adi: str | None = None) -> str | None:
        return self._depo.url(yol, sure, indirme_adi=indirme_adi)

    def listele(self, onek: str) -> Iterator[Nesne]:
        return self._depo.listele(onek)

    def geri_al(self) -> int:
        """Yazılanları siler; silme hatası telafiyi durdurmaz (artık kalırsa `artik_dosya` bulur)."""
        silinen = 0
        for yol in self.yazilanlar:
            with contextlib.suppress(Exception):
                if self._depo.sil(yol):
                    silinen += 1
        self.yazilanlar.clear()
        return silinen


# ────────────────────────────────────────────────────────── üretim

def _girdiler(istek: Mapping[str, Any], depo: dosya.Depo) -> list[tuple[str, bytes]]:
    """`istek["girdiler"]` → adaptör sözleşmesinin `[(ad, bayt), …]`i, sırası korunarak."""
    return [(str(g["ad"]), _nesne(depo, str(g["anahtar"]))) for g in istek.get("girdiler") or []]


def _nesne(depo: dosya.Depo, anahtar: str) -> bytes:
    try:
        return depo.oku(anahtar)
    except dosya.DosyaYok:
        # Rota bu durumda 404 + `err.source_image_missing` diyor (services/gorsel.py);
        # işçide aynı metin `hata` sütununa — kullanıcı aynı cümleyi görür.
        raise ac.ImageError(i18n.t("err.source_image_missing", dil.aktif()))


def _istek(is_: Is) -> dict[str, Any]:
    """`isler.istek` JSONB'si; sütun tipi `dict[str, object]`, okuma tarafı alanları biliyor."""
    return dict(is_.istek)


def _uret(is_: Is, depo: dosya.Depo) -> list[bytes]:
    """Tür → MEVCUT sağlayıcı sözleşmesi (imzalar değişmedi; `providers` modül niteliğiyle: testler yamalıyor)."""
    istek = _istek(is_)
    prompt = str(istek["prompt"])
    gonderilen = str(istek.get("prompt_sent") or prompt)
    size, quality = str(istek["size"]), str(istek["quality"])
    n = int(istek.get("n") or 1)
    if is_.tur == "generate":
        return providers.generate(is_.model, gonderilen, size, quality, n)
    if is_.tur == "edit":
        return providers.edit(is_.model, gonderilen, _girdiler(istek, depo), size, quality, n)
    duration = int(istek["duration"])
    if is_.tur == "video":
        return providers.generate_video(is_.model, prompt, size, quality, duration, n)
    if is_.tur == "animate":
        son = istek.get("son_kare")
        son_kare = _nesne(depo, str(son["anahtar"])) if son else None
        return providers.animate_video(is_.model, prompt, _girdiler(istek, depo), size, quality,
                                       duration, n, last_frame=son_kare)
    # CHECK (`ck_isler_tur_kumesi`) bunu DB'de reddediyor; buraya varılması programlama hatası.
    raise ValueError(f"bilinmeyen is turu: {is_.tur!r} (beklenen: {IS_TURLERI})")


def _meta(is_: Is, kredi: int, filigranli: bool = False) -> dict[str, Any]:
    """`depo_medya.kaydet`in `meta`sı — rotaların bugün yazdığı alanlar, aynı kurallarla (+ `filigranli`, Faz 3 / 4)."""
    istek = _istek(is_)
    pal = istek.get("palette")
    gonderilen = istek.get("prompt_sent")
    meta: dict[str, Any] = {
        "prompt": istek["prompt"], "size": istek["size"], "quality": istek["quality"],
        "parent_id": istek.get("parent_id"), "folder_id": istek.get("folder_id"),
        "palette": pal, "session_id": istek.get("session_id"),
        "arena_id": istek.get("arena_id"),
        "model": is_.model, "credits": kredi,
        # Rotalar bu alanı yazmaz (içe aktarma, bindirme uçları filigransız): yalnız işçi bilir.
        "filigranli": filigranli,
        # Ek düştüyse metin prompt'un birebir aynısı; storage sözleşmesi "yalnızca farklıysa".
        "prompt_sent": gonderilen if (pal and isinstance(pal, Mapping) and pal.get("applied")) else None,
    }
    if is_.tur in ("video", "animate"):
        meta["kind"] = "video"
        meta["duration"] = istek["duration"]
    return meta


def _filigranlanir(is_: Is, plan: str) -> bool:
    """Bu işin sonucu filigranlanır mı: planın `filigran`ı açık VE tür görsel (Faz 3 / 4, K7).

    `kind` KATALOGDAN (`_kredi`nin `spec`i), iş türünden değil — belge §4'ün
    kuralı "spec.kind == image". Katalogdan düşmüş bir model için spec None:
    o iş zaten `_uret`te `ImageError` ile düşer, buraya gelmez; yine de tür
    kümesine düşülür ki karar hiç `None`a bakmasın. Plan CHECK'ten geliyor —
    tanınmayan ad KeyError, sessiz "filigransız" değil (`planlar.kapsiyor`un duruşu).
    """
    if not PLANLAR[plan].filigran:
        return False
    if is_.tur in ("video", "animate"):
        spec: catalog.ImageModel | None = catalog.video_model(is_.model)
        return spec.kind == "image" if spec else False
    spec = catalog.image_model(is_.model)
    return spec.kind == "image" if spec else True


def _kredi(is_: Is) -> int:
    """Görsel/video BAŞINA gerçek maliyet (rotaların `catalog.cost_for` çağrısı aynen)."""
    istek = _istek(is_)
    if is_.tur in ("video", "animate"):
        spec = catalog.video_model(is_.model)
        return catalog.cost_for(spec, str(istek["quality"]), duration=int(istek["duration"])) if spec else 0
    spec = catalog.image_model(is_.model)
    return catalog.cost_for(spec, str(istek["quality"])) if spec else 0


# ────────────────────────────────────────────────────────── yazım ve kapanış

def _dusur(oturum_ac: Callable[[], Session], is_id: uuid.UUID, metin: str, an: dt.datetime,
           data_dir: str) -> bool:
    """İşi `hata`ya yazar ve rezervini iade eder (kendi oturumu, TEK commit); DB de düşerse izi `hata.log`a, patlamaz.

    `defter.iade` `dusur`un sonucuna bakmadan çağrılır: 0 satır "iş çoktan
    bayat düşürülmüş" demek ve kalp turu o işi iade etmiştir — ikinci çağrı
    idempotent no-op (`iade:<is_id>` anahtarı). Rezervsiz (BYOK) işte de `None`.
    """
    try:
        with oturum_ac() as db:
            tamam = kuyruk.dusur(db, is_id, metin, an)
            defter.iade(db, is_id, an=an)
            db.commit()
        return tamam
    except Exception:
        errlog.safe_append(data_dir, f"is {is_id} hata olarak yazilamadi:\n{traceback.format_exc()}")
        return False


def _yaz(is_: Is, sonuclar: list[bytes], oturum_ac: Callable[[], Session], depo: dosya.Depo,
         ayarlar: ayar.Ayarlar, an: dt.datetime, *, filigranli: bool = False,
         saglayici: saglayici_meta.Toplayici | None = None) -> bool:
    """Nesne → satır → `bitir` → tek commit; düşerse nesneler silinir ve iş `hata`.

    `saglayici` (Faz 3 / 5, K8): `_uret` boyunca yan kanalın topladığı sağlayıcı
    alanları — `bitir` aynı UPDATE'te `isler.saglayici_meta`/`saglayici_maliyet_usd`
    sütunlarına yazar (redaksiyon orada). Hiç kayıt yoksa sütunlar NULL kalır.
    Adı `meta` DEĞİL: aşağıdaki `meta` medya kaydının sözlüğü (`_meta`), ilk sürüm
    ikisini aynı adla yazdı ve `dict.sozluk` AttributeError'ı her işi düşürdü (ölçüldü).
    """
    izi = _YazimIzi(depo)
    output_dir = ayarlar.kullanici_icin(is_.kullanici_id).output_dir
    meta = _meta(is_, _kredi(is_), filigranli)
    try:
        with oturum_ac() as db:
            kayitlar = [depo_medya.kaydet(db, is_.kullanici_id, veri, dict(meta), output_dir,
                                          now=an, depo=izi) for veri in sonuclar]
            # GERÇEK kredi = yazılan kayıtların `credits` toplamı (kayıt başına `_kredi`;
            # spec katalogdan düşmüşse 0). Sağlayıcı istenenden az döndürdüyse toplam da az:
            # kullanıcı yalnız aldığı kadar öder, farkı `onayla` iade eder (K2).
            kredi_gercek = sum(int(k.get("credits") or 0) for k in kayitlar)
            if not kuyruk.bitir(db, is_.id, {"medya": [k["id"] for k in kayitlar]}, an,
                                kredi_gercek=kredi_gercek,
                                saglayici_meta=saglayici.sozluk() if saglayici is not None else None,
                                saglayici_maliyet_usd=saglayici.maliyet_usd if saglayici is not None else None):
                raise _IsArtikCalismiyor(str(is_.id))
            defter.onayla(db, is_.id, kredi_gercek, an=an)
            db.commit()
    except _IsArtikCalismiyor:
        # İş bu arada bayat düşürüldü (`hata`): sonuç yazılmaz, `dusur` da çağrılmaz
        # (satır zaten kapalı); üretilen nesne silinir, iz günlüğe.
        silinen = izi.geri_al()
        errlog.safe_append(ayarlar.data_dir,
                           f"is {is_.id} artik calisiyor degil (bayat dusurulmus); "
                           f"{silinen} nesne silindi, sonuc yazilmadi")
        return False
    except Exception as e:
        izi.geri_al()
        errlog.safe_append(ayarlar.data_dir,
                           f"is {is_.id} ({is_.tur}) satir/commit dustu, nesneler silindi:\n"
                           f"{traceback.format_exc()}")
        _gunluk.exception("is satir/commit dustu, nesneler silindi",
                          extra={"olay": "is.istisna", "tur": is_.tur})
        hata_izleme.istisna_bildir()
        _dusur(oturum_ac, is_.id, f"{BEKLENMEYEN_HATASI}: {type(e).__name__}", an, ayarlar.data_dir)
        return False
    return True


def kos(is_: Is, oturum_ac: Callable[[], Session], depo: dosya.Depo, ayarlar: ayar.Ayarlar,
        *, an: dt.datetime | None = None) -> bool:
    """Alınmış (`calisiyor`, commit'lenmiş, oturumdan ayrılmış) bir işi sonuna götürür.

    `True` = `bitti` (medya satırları + nesneler yazıldı), `False` = `hata`
    (ya da iş bu arada bayat düşürülmüştü). `oturum_ac` her çağrıda YENİ bir
    `Session` verir (`lambda: Session(motor)`); bu işlev onu üç kısa pencerede
    açar — kullanıcı/kimlik okuması, sonuç yazımı, düşüş — ve sağlayıcı
    çağrısı boyunca hiç açmaz.

    BİTİŞ ANI BİTİŞTE ÖLÇÜLÜR (`an` verilmemişse). 3. görevde `zaman.an()`
    işlevin BAŞINDA alınıp `bitti` sütununa yazılıyordu — yani `bitti ≈ basladi`,
    sağlayıcı dakikalarca sürse de. Faz 2 / 5'in E2E'si bunu ölçtü: SSE akışı
    "değişen iş"i `GREATEST(olusturuldu, basladi, bitti) > since` ile soruyor
    ve başlangıcına damgalanmış bir bitiş hiçbir `since`in ötesine geçmiyor —
    işçi işi bitiriyor, panel `calisiyor`da donuyordu. Panelin geçen süresi de
    aynı sütunu okur. `an` verilmişse (testler) aynen kullanılır.
    """
    def bitis() -> dt.datetime:
        return an if an is not None else zaman.an()

    # İşin KİRACISI `_kos` boyunca bağlı: `oturum_ac()` ile açılan her oturumun
    # ilk ifadesi `SET LOCAL app.kullanici_id` olur (services/db.py kancası) —
    # kimlik okuması, medya satırı, `bitir`/`dusur` hep o kullanıcının satırında.
    # GÜNLÜK BAĞLAMI da iş boyunca (Faz 2 / 9): bu blokta yazılan HER satır
    # (`is.basladi/bitti/hata`, depo hataları, iz) `is_id` + `kullanici_id`
    # taşır; Sentry kuruluysa aynı ikili iş kapsamının etiketi (`set_tag`).
    # Süre DUVAR SAATİ (`perf_counter`), `an` DEĞİL: testler `an`ı sabitliyor,
    # `sure_ms` yine gerçek geçen süreyi söylesin.
    baslangic = time.perf_counter()
    with (kiraci.baglam(kullanici_id=is_.kullanici_id),
          gunluk.baglam(is_id=str(is_.id), kullanici_id=str(is_.kullanici_id)),
          hata_izleme.is_baglami(is_.id, is_.kullanici_id)):
        gunluk.olay(_gunluk, "is.basladi", tur=is_.tur, model=is_.model,
                    anahtar_kaynagi=is_.anahtar_kaynagi)
        bitti = _kos(is_, oturum_ac, depo, ayarlar, bitis)
        gunluk.olay(_gunluk, "is.bitti" if bitti else "is.hata", tur=is_.tur, model=is_.model,
                    sure_ms=round((time.perf_counter() - baslangic) * 1000))
        return bitti


def _kos(is_: Is, oturum_ac: Callable[[], Session], depo: dosya.Depo, ayarlar: ayar.Ayarlar,
         bitis: Callable[[], dt.datetime]) -> bool:
    """`kos`un gövdesi, kiracı bağlı hâlde (sarmalayıcı yukarıda)."""
    with oturum_ac() as db:
        kullanici = db.get(Kullanici, is_.kullanici_id)
        # Değerler oturum KAPANMADAN kopyalanıyor: kapanış nesneyi ayırır ve
        # süresi geçmiş bir öznitelik okuması `DetachedInstanceError` olurdu.
        dil_kodu = kullanici.dil if kullanici is not None else None
        # Plan da burada okunur (`kullanicilar.plan`, `kos` işi alırken — belge §4):
        # filigran kararı sağlayıcı çağrısından SONRA veriliyor ama o sırada oturum yok.
        plan = kullanici.plan if kullanici is not None else PLAN_VARSAYILAN
        # Platform anahtarıyla TAMAMLANMIŞ sözlük (Faz 2 / 6): rota `anahtar_kaynagi`ni
        # sıraya alırken yazdı, işçi aynı çözüm sırasıyla (kullanıcı → platform) koşar.
        kimlikler, _ = (platform_anahtari.birlestir(depo_kimlik_bilgisi.oku(db, is_.kullanici_id))
                        if kullanici is not None else ({}, {}))
    if kullanici is None:
        # Hesap silinmiş: CASCADE işi de götürür, `dusur` 0 satır görür; yine de denenir.
        return _dusur(oturum_ac, is_.id, KULLANICI_YOK_HATASI, bitis(), ayarlar.data_dir)

    jeton = kimlik_baglami.bagla(kimlikler)
    i18n.set_active(dil_kodu or i18n.DEFAULT)
    try:
        try:
            # YAN KANAL (Faz 3 / 5, K8): adaptörler `saglayici_meta.kaydet` ile `usage`/
            # `request_id` bırakır; `_uret` bu iş parçacığında koşar, bağlam kaybolmaz
            # (havuza/başka parçacığa geçiş yok — tests/test_saglayici_meta.py ölçer). Toplanan,
            # `_yaz` → `bitir` ile satıra gider; hata yolunda yazılmaz (`dusur` imzası aynen).
            with saglayici_meta.toplayici() as meta:
                sonuclar = _uret(is_, depo)
            # FİLİGRAN (Faz 3 / 4, K7): `_uret` → `_yaz` arası, TEK yer, yalnız görsel,
            # yalnız planı isteyen (ücretsiz). `_uret` ve adaptörler değişmez; işaret
            # dosyası yoksa `FiligranDosyasiYok` aşağıdaki genel dala düşer — iş `hata`,
            # rezerv iade; SESSİZ filigransız yazım yok (services/filigran.py'nin gerekçesi).
            filigranli = _filigranlanir(is_, plan)
            if filigranli:
                sonuclar = [filigran.uygula(b) for b in sonuclar]
        except ac.ImageError as e:
            # Redaksiyon `kuyruk.dusur`da (yazan yerde).
            _dusur(oturum_ac, is_.id, str(e), bitis(), ayarlar.data_dir)
            return False
        except Exception as e:
            # İz üç yere: `hata.log` (belge §9: kalır), stdout JSON (`hata` alanı,
            # `is_id` bağlamdan) ve Sentry (kuruluysa). Kullanıcıya yalnız KOD.
            errlog.safe_append(ayarlar.data_dir,
                               f"is {is_.id} ({is_.tur}) beklenmeyen hata:\n{traceback.format_exc()}")
            _gunluk.exception("is beklenmeyen hata", extra={"olay": "is.istisna", "tur": is_.tur})
            hata_izleme.istisna_bildir()
            _dusur(oturum_ac, is_.id, f"{BEKLENMEYEN_HATASI}: {type(e).__name__}", bitis(),
                   ayarlar.data_dir)
            return False
        return _yaz(is_, sonuclar, oturum_ac, depo, ayarlar, bitis(), filigranli=filigranli, saglayici=meta)
    finally:
        # HER yolda: bir sonraki işin sahibi başka biri.
        kimlik_baglami.coz(jeton)
        i18n.set_active(None)


def tek_tur(db: Session, depo: dosya.Depo, an: dt.datetime | None = None, *,
            ayarlar: ayar.Ayarlar | None = None, isci_id: uuid.UUID | None = None) -> bool:
    """Bir kez `al`; iş varsa `kos`; bir iş KOŞTU MU döner (sonucu ne olursa olsun).

    Testlerin (ve `isci.py --tek-tur`un) deyimi: sağlayıcıyı yamala, işi
    sıraya koy, `tek_tur` — süreç yok, port yok, uyku yok. `db` yalnız alım
    için kullanılır ve commit'lenir; yazım `db.get_bind()`ten açılan yeni
    oturumlarda (çağrı sırasında bu oturum da bağlantı tutmaz — commit
    bağlantıyı havuza verdi). `isci_id` verilmezse rastgele: `isler.isci_id`
    FK değil, bir izdir.
    """
    simdi = an if an is not None else zaman.an()
    is_ = siradakini_al(db, isci_id if isci_id is not None else uuid.uuid4(), simdi)
    if is_ is None:
        return False
    motor = db.get_bind()
    kos(is_, lambda: Session(motor), depo, ayarlar if ayarlar is not None else ayar.Ayarlar.varsayilan(),
        an=an)
    return True


# ────────────────────────────────────────────────────────── kalp

class KalpOzeti(NamedTuple):
    """`kalp_turu`nun sonucu: bayat düşürülen iş sayısı ve işçi satırı yeniden yazıldı mı."""
    dusen: int
    yeniden_kaydoldu: bool


def kalp_turu(db: Session, isci_id: uuid.UUID, is_idleri: Iterable[uuid.UUID], an: dt.datetime,
              esik: dt.timedelta, kayit: kuyruk.IsciKaydi | None = None) -> KalpOzeti:
    """Kalp atışı iş parçacığının bir turu: işçi satırı + eldeki işler + bayat düşürme; `KalpOzeti`.

    AYRI iş parçacığında koşar (belge §3): sağlayıcı çağrısı adaptörün içinde
    dakikalarca bloklar ve çağıran iş parçacığı kalp atamaz. Kendi oturumu,
    kendi commit'i. Bayat düşürme burada: ölen bir işçinin işini yaşayan bir
    işçi `hata`ya çeker — 10. görevin periyodik bakımı aynı işlevi çağırır.
    `app.rol = 'admin'` ile (RLS): eldeki işler ve bayatlar her kiracının;
    `isciler` politikasız, rol ona dokunmaz. İşçi satırı yoksa ve `kayit`
    verilmişse satır aynı kimlikle yeniden yazılır (gerekçe modül başında);
    `kayit`sız çağrı (testler, `--tek-tur` yolu) eski davranış: yok say.
    """
    yeniden = False
    with kiraci.baglam(rol=kiraci.ADMIN, oturum=db):
        if not kuyruk.isci_kalp(db, isci_id, an) and kayit is not None:
            kuyruk.isci_yeniden_kaydet(db, isci_id, kayit, an)
            yeniden = True
        for is_id in is_idleri:
            kuyruk.kalp(db, is_id, an)
        dusenler = kuyruk.bayatlari_dusur(db, an, esik)
        # Düşen her işin rezervi geri (Faz 3 / 2, K2): admin bağlamı `kredi_hareketleri`ye
        # yalnız bu yoldan yazar (`yonetici_ekler`, K4). Aynı commit'te: iş `hata` olup
        # parası tutulmuş bir ara durum kalmasın. Geç kalan işçinin `_dusur`u aynı işi
        # ikinci kez iade edemez (`iade:<is_id>` anahtarı çakışır, no-op).
        for is_id in dusenler:
            defter.iade(db, is_id, an=an)
        db.commit()
    return KalpOzeti(len(dusenler), yeniden)


def kuyruk_uyarisi(db: Session, an: dt.datetime) -> dict[str, Any] | None:
    """Eşik aşıldıysa uyarı alanları (`derinlik`, `en_eski_bekleyen_sn`, `esik_*`), değilse `None`.

    Kalp turuyla aynı iş parçacığında, 30 sn'de bir (`isci.py`); TEK sorgu
    (`kuyruk.bekleyen_ozeti`). Koşul sürdükçe HER turda yeniden düşer, kenar
    tetiklemeli değil: Sentry/toplayıcı uyarı kuralları "son N dakikada K
    olay" sayar ve tek satır susan bir kuralı uyandırmaz; bedeli işçi başına
    en çok 120 satır/saat, o da yalnız işler birikirken. `app.rol='admin'`:
    bütün kiracıların bekleyeni (RLS).
    """
    with kiraci.baglam(rol=kiraci.ADMIN, oturum=db):
        derinlik, en_eski = kuyruk.bekleyen_ozeti(db, an)
        db.rollback()
    if derinlik <= UYARI_KUYRUK_DERINLIGI and (en_eski is None or en_eski <= UYARI_EN_ESKI_BEKLEYEN_SN):
        return None
    return {"derinlik": derinlik, "en_eski_bekleyen_sn": en_eski,
            "esik_derinlik": UYARI_KUYRUK_DERINLIGI, "esik_en_eski_sn": UYARI_EN_ESKI_BEKLEYEN_SN}


# ────────────────────────────────────────────────────────── bakım

class BakimOzeti(dict[str, int]):
    """`bakim_turu`nun döndürdüğü sayılar: `silinen_is`, `silinen_nesne`, `korunan_dizin`, `silinen_isci`, `hibe_satiri`.

    Sözlük (günlük alanı olarak düz yazılsın); `__bool__` "bir şey yapıldı mı":
    işçi olayı yalnız bir şey silindiğinde ya da hibe yazıldığında düşürür
    (`bayat`ın deyimi — boş turda 5 dk'da bir satır gürültüdür). `hibe_satiri`
    (Faz 3 / 3): bu turda yatan aylık hibe sayısı — dağıtım sonrası ilk turda
    bütün kullanıcılar, sonra ay başında; ay içinde 0 (belge §3 "Sahibin adımı":
    `olay=bakim` satırında `hibe_satiri=N`).
    """

    def __bool__(self) -> bool:
        return any(self.values())


def _dizini_sil(depo: dosya.Depo, onek: str) -> int:
    """Dizin önekinin altındaki her nesneyi siler; silinen sayı. Silme hatası turu durdurmaz (artık kalırsa `artik_dosya` bulur)."""
    silinen = 0
    for nesne in list(depo.listele(onek)):
        with contextlib.suppress(Exception):
            if depo.sil(nesne.anahtar):
                silinen += 1
    return silinen


def bakim_turu(db: Session, depo: dosya.Depo, an: dt.datetime, esik: dt.timedelta,
               saklama_suresi: dt.timedelta) -> BakimOzeti:
    """Bir bakım turu: saklama (satır + referanssız girdi dizini), ölü işçi satırları ve aylık hibe; özet sayılar.

    Sıra ve bağlamlar (gerekçe modül başında): sahipler ADMIN bağlamında
    bulunur ve aylık hibe (`defter.hibe_turu`, Faz 3 / 3) aynı bağlamda
    yatar; her kiracının satırları O KİRACININ bağlamında silinir ve commit
    edilir (kiracı başına bir transaksiyon — biri düşerse ötekiler durur);
    sonra ADMIN bağlamında kalan referanslar ve mevcut satırlar okunur, ona
    göre dizinler silinir. Ölü işçi satırı politikasız, bağlam gerekmez.
    `an`/`esik`/`saklama_suresi` çağıranın (testler saatle oynamaz).
    """
    ozet = BakimOzeti(silinen_is=0, silinen_nesne=0, korunan_dizin=0, silinen_isci=0, hibe_satiri=0)
    with kiraci.baglam(rol=kiraci.ADMIN, oturum=db):
        sahipler = kuyruk.saklama_sahipleri(db, an, saklama_suresi)
        ozet["silinen_isci"] = kuyruk.olu_iscileri_sil(db, an, esik)
        # Aylık hibe (Faz 3 / 3, K6) ADMİN bağlamında: `kredi_hareketleri`ye
        # bütün kiracılar adına yazar — `yonetici_ekler` politikası (K4) tam
        # bunun için var. Aynı commit: silme ile hibe aynı turun işi.
        ozet["hibe_satiri"] = defter.hibe_turu(db, an)
        db.commit()
    silinenler: list[kuyruk.SilinenIs] = []
    for kullanici_id in sahipler:
        with kiraci.baglam(kullanici_id=kullanici_id, oturum=db):
            silinenler += kuyruk.eskileri_sil(db, kullanici_id, an, saklama_suresi)
            db.commit()
    ozet["silinen_is"] = len(silinenler)
    if not silinenler:
        return ozet
    # Yalnız rotanın biçimindeki dizinler aday (`ayar.is_dizini_coz`): elle yazılmış
    # bir `istek`in tanınmayan anahtarı `foo/bar.png` → `foo/` gibi bir öneke çözülür ve
    # onun altını körlemesine silmek bu turun işi değil. Dizinin kiracısı silinen işin
    # sahibi değilse de aday değil (gerekçe modül başında): uyarı düşer, dizin durur.
    adaylar: dict[str, uuid.UUID] = {}
    for s in silinenler:
        for d in sorted(s.girdi_dizinleri):
            coz = ayar.is_dizini_coz(d)
            if coz is None:
                continue
            if coz.kullanici_id != s.kullanici_id:
                gunluk.olay(_gunluk, "bakim.yabanci_dizin", "silinen isin istegi baska kiracinin dizinine bakiyor, dokunulmadi",
                            seviye=logging.WARNING, is_id=str(s.is_id), kullanici_id=str(s.kullanici_id),
                            dizin=d)
                continue
            adaylar[d] = coz.is_id
    with kiraci.baglam(rol=kiraci.ADMIN, oturum=db):
        referansli = {ayar.girdi_dizini(a) for a in kuyruk.girdi_referanslari(db)}
        sahipli = kuyruk.mevcut_isler(db, list(adaylar.values()))
        db.rollback()
    for dizin, is_id in sorted(adaylar.items()):
        if dizin in referansli or is_id in sahipli:
            ozet["korunan_dizin"] += 1
            continue
        ozet["silinen_nesne"] += _dizini_sil(depo, dizin)
    return ozet
