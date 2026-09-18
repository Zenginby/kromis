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

SIRA: nesne yaz → `depo_medya.kaydet` satırı (flush) → `kuyruk.bitir` → TEK
commit. Satır ya da commit düşerse yazılan nesneler `depo.sil` ile TELAFİ
edilir ve iş `hata` — Faz 1 / 5'in "dosya + satır atomik değil" borcu burada
kapanır: web rotası akışın iki ucunu tutamıyordu (commit bağımlılıkta, rota
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
"""
from __future__ import annotations

import contextlib
import datetime as dt
import os
import traceback
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any

from sqlalchemy.orm import Session

import azure_client as ac
import catalog
import errlog
import i18n
import kimlik_baglami
import providers
from services import (
    ayar,
    depo_kimlik_bilgisi,
    depo_medya,
    dil,
    dosya,
    kuyruk,
    platform_anahtari,
    zaman,
)
from services.nesne_depo import Nesne
from services.tablolar import (
    IS_TURLERI,
    Is,
    Kullanici,
)

__all__ = ["ES_ZAMANLI_ENV", "ES_ZAMANLI_VARSAYILAN", "KALP_ESIGI_ENV", "KALP_ESIGI_VARSAYILAN",
           "KALP_ARALIGI_SN", "YOKLAMA_ARALIGI_SN", "BEKLENMEYEN_HATASI", "KULLANICI_YOK_HATASI",
           "es_zamanli", "kalp_esigi", "siradakini_al", "kos", "tek_tur", "kalp_turu"]

# Aynı anda kaç iş (iş parçacığı) — `.env.example`, `compose.yaml` ve `isci.py`
# aynı adı buradan okur (bekçisi tests/test_docker_kapisi.py `ALTYAPI`).
ES_ZAMANLI_ENV = "KROMIS_ISCI_ES_ZAMANLI"
ES_ZAMANLI_VARSAYILAN = 4
# Kalbi bu kadar saniye susan `calisiyor` iş `hata` sayılır (K8; kuyruk.bayatlari_dusur).
# 300: en uzun sağlayıcı çağrısı 600 sn ama kalp çağrının İÇİNDE, ayrı iş
# parçacığında 30 sn'de bir atıyor — 10 atış kaçırmak işçinin öldüğü demek.
KALP_ESIGI_ENV = "KROMIS_IS_KALP_ESIGI_SN"
KALP_ESIGI_VARSAYILAN = 300
# Kalp atışı aralığı ve boş kuyrukta yoklama aralığı (belge §3: 30 sn / 1 sn;
# `LISTEN/NOTIFY` yok — senkron sürücüde ayrı bağlantı ister, 1 sn dakikalık işte görünmez).
KALP_ARALIGI_SN = 30.0
YOKLAMA_ARALIGI_SN = 1.0

# `hata` sütununa yazılan KODLAR — cümle değil (kuyruk.BAYAT_HATASI'nın duruşu):
# cümleyi ön yüz kurar, metin sızıntı taşımasın diye istisna MESAJI değil TÜRÜ yazılır.
BEKLENMEYEN_HATASI = "beklenmeyen hata"
KULLANICI_YOK_HATASI = "kullanici yok"


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


# ────────────────────────────────────────────────────────── alım

def siradakini_al(db: Session, isci_id: uuid.UUID, an: dt.datetime) -> Is | None:
    """`kuyruk.al` + commit; satırı oturumdan AYIRIP döndürür (kuyruk boşsa `None`).

    `expunge` commit'ten ÖNCE: `expire_on_commit` oturumdaki her nesneyi
    süresi geçmiş sayar ve ilk öznitelik okuması yeni bir bağlantı açardı —
    tam da sağlayıcı çağrısı sırasında. Ayrılmış nesne RETURNING'in doldurduğu
    sütunları taşır, DB'ye bir daha sormaz. Commit alımı kalıcı kılar: bu
    işçi düşerse satır `calisiyor`da kalır ve bayat düşürme onu `hata` yapar
    (K8), `bekliyor`a dönmez.
    """
    is_ = kuyruk.al(db, isci_id, an)
    if is_ is None:
        db.rollback()
        return None
    db.expunge(is_)
    db.commit()
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


def _meta(is_: Is, kredi: int) -> dict[str, Any]:
    """`depo_medya.kaydet`in `meta`sı — rotaların bugün yazdığı alanlar, aynı kurallarla."""
    istek = _istek(is_)
    pal = istek.get("palette")
    gonderilen = istek.get("prompt_sent")
    meta: dict[str, Any] = {
        "prompt": istek["prompt"], "size": istek["size"], "quality": istek["quality"],
        "parent_id": istek.get("parent_id"), "folder_id": istek.get("folder_id"),
        "palette": pal, "session_id": istek.get("session_id"),
        "arena_id": istek.get("arena_id"),
        "model": is_.model, "credits": kredi,
        # Ek düştüyse metin prompt'un birebir aynısı; storage sözleşmesi "yalnızca farklıysa".
        "prompt_sent": gonderilen if (pal and isinstance(pal, Mapping) and pal.get("applied")) else None,
    }
    if is_.tur in ("video", "animate"):
        meta["kind"] = "video"
        meta["duration"] = istek["duration"]
    return meta


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
    """İşi `hata`ya yazar (kendi oturumu, kendi commit'i); DB de düşerse izi `hata.log`a, patlamaz."""
    try:
        with oturum_ac() as db:
            tamam = kuyruk.dusur(db, is_id, metin, an)
            db.commit()
        return tamam
    except Exception:
        errlog.safe_append(data_dir, f"is {is_id} hata olarak yazilamadi:\n{traceback.format_exc()}")
        return False


def _yaz(is_: Is, sonuclar: list[bytes], oturum_ac: Callable[[], Session], depo: dosya.Depo,
         ayarlar: ayar.Ayarlar, an: dt.datetime) -> bool:
    """Nesne → satır → `bitir` → tek commit; düşerse nesneler silinir ve iş `hata`."""
    izi = _YazimIzi(depo)
    output_dir = ayarlar.kullanici_icin(is_.kullanici_id).output_dir
    meta = _meta(is_, _kredi(is_))
    try:
        with oturum_ac() as db:
            kayitlar = [depo_medya.kaydet(db, is_.kullanici_id, veri, dict(meta), output_dir,
                                          now=an, depo=izi) for veri in sonuclar]
            if not kuyruk.bitir(db, is_.id, {"medya": [k["id"] for k in kayitlar]}, an):
                raise _IsArtikCalismiyor(str(is_.id))
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

    with oturum_ac() as db:
        kullanici = db.get(Kullanici, is_.kullanici_id)
        # Değerler oturum KAPANMADAN kopyalanıyor: kapanış nesneyi ayırır ve
        # süresi geçmiş bir öznitelik okuması `DetachedInstanceError` olurdu.
        dil_kodu = kullanici.dil if kullanici is not None else None
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
            sonuclar = _uret(is_, depo)
        except ac.ImageError as e:
            # Redaksiyon `kuyruk.dusur`da (yazan yerde).
            _dusur(oturum_ac, is_.id, str(e), bitis(), ayarlar.data_dir)
            return False
        except Exception as e:
            errlog.safe_append(ayarlar.data_dir,
                               f"is {is_.id} ({is_.tur}) beklenmeyen hata:\n{traceback.format_exc()}")
            _dusur(oturum_ac, is_.id, f"{BEKLENMEYEN_HATASI}: {type(e).__name__}", bitis(),
                   ayarlar.data_dir)
            return False
        return _yaz(is_, sonuclar, oturum_ac, depo, ayarlar, bitis())
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

def kalp_turu(db: Session, isci_id: uuid.UUID, is_idleri: Iterable[uuid.UUID], an: dt.datetime,
              esik: dt.timedelta) -> int:
    """Kalp atışı iş parçacığının bir turu: işçi satırı + eldeki işler + bayat düşürme; düşürülen sayı.

    AYRI iş parçacığında koşar (belge §3): sağlayıcı çağrısı adaptörün içinde
    dakikalarca bloklar ve çağıran iş parçacığı kalp atamaz. Kendi oturumu,
    kendi commit'i. Bayat düşürme burada: ölen bir işçinin işini yaşayan bir
    işçi `hata`ya çeker — 10. görevin periyodik bakımı aynı işlevi çağırır.
    """
    kuyruk.isci_kalp(db, isci_id, an)
    for is_id in is_idleri:
        kuyruk.kalp(db, is_id, an)
    dusen = kuyruk.bayatlari_dusur(db, an, esik)
    db.commit()
    return dusen
