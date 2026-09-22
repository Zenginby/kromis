# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İstekle gelen kimliklerin (klasör, oturum, arena, varlık türü) kapıları.

Hepsi aynı sözleşmeyi paylaşıyor: boş/None → "yok" (None), dolu → doğrula,
geçersizse HTTPException. Hangi kapının VARLIK, hangisinin yalnız BİÇİM
denetlediği her işlevin başında yazılı — ayrım bilinçli ve gerekçeli.

Beşinci kapı başka türden (Faz 2 / 4): `check_is_tavani` bir kimlik değil
bir SAYI denetler — kullanıcının aynı anda sırada/işçide tutabileceği iş
sayısı. Rotalar sağlayıcıyı çağırmayı bıraktı ve 202 ile döndü; sınırsız
sıraya yazma, tek kullanıcının kuyruğu (ve platform parasını, 6. görev)
tek başına doldurması demekti.

Altıncı kapı `check_anahtar` (Faz 2 / 6): seçilen modelin sağlayıcısına
ULAŞILABİLİYOR mu — kullanıcının kendi anahtarı ya da platformun. 4. ve 5.
görevde anahtarsız kullanıcı 202 alıp panelde `hata`lı bir iş görüyordu
("Kimlik bilgileri eksik…", duman testinin ilk turu); şimdi cevap 409 ve iş
HİÇ doğmaz — `hata` satırı o günden sonra yalnız gerçek sağlayıcı hatasını
taşır. Kapı `credstore.is_configured`u çağırır (arayüzün "kurulu" dediğiyle
rotanın kabul ettiği ayrışmasın; credstore'un var olma gerekçesi) ve işin
`anahtar_kaynagi`ni döndürür. Kota kapıları services/kota.py'de.

Yedinci kapı `check_bakiye` + `rezerve_kredi` (Faz 3 / 2, K2/K9/K11): platform
anahtarıyla koşacak işin TAHMİNİ kadar kredi var mı (Faz 4 / 2'den beri iki
kovanın TOPLAMI — hibe + paket; bölüşümü defter yapar). İki yarım, iki sebep:
`check_bakiye` SALT OKUR (`defter.bakiye(...).toplam < tahmin` → 402) ve `_kapilar`
zincirinin sonunda, girdi nesnesi yazılmadan ÖNCE koşar — 429 gibi 402 de
depoya nesne bırakmasın; `rezerve_kredi` ise YAZAR (`defter.rezerve`, atomik
`UPDATE … WHERE bakiye >= :m`) ve ancak `kuyruk.ekle`den sonra çağrılabilir
(rezerv satırı `is_id` ister, FK). Asıl kapı ikincisi: ön denetim geçip iki
istek aynı bakiyeye yarışsa Postgres'in satır kilidi kaybedene 402 der ve
transaksiyon geri alınır — iş satırı da (rota `OTURUM`u istisnada rollback).
İkisi de aynı gövdeyi kurar (`_yetersiz_bakiye`): `{"kod": "err.kredi_yetersiz",
"bakiye", "gereken", "plan"}` — 402 "ödeme gerekir", 429 (kota, `Retry-After`lı)
ve 403 (plan/yetki) ile karışmasın (K11); cümleyi ön yüz `kod`dan kurar
(palette.js `detailText`). BYOK (`kullanici`) iş defteri hiç görmez (K3).

Sekizinci kapı `check_plan` (Faz 3 / 3, K5/K7; Faz 4 / 1b, 1b-A/1b-B):
kullanıcının PLANI seçilen modeli kapsıyor mu (`planlar.kapsiyor` — model
basamağı + video ↔ `Plan.video`; `modeller.model_available`ın rota tarafındaki
ikizi). Hayırsa **403** JSON `{"kod": "err.plan_kapsamiyor", "model", "plan"}`
— 403 "yetki/plan", 402 "para", 429 "kota" (K11 ayrımı); cümleyi ön yüz
`kod`dan kurar.

Zincirin EN BAŞINDA, anahtar kapısından ÖNCE — ve bu sıra 1b'den SONRA da
duruyor, ama artık bir inceliği var. Kapının VİDEO yarısı anahtar kaynağından
BAĞIMSIZ (BYOK'lu ücretsiz kullanıcı da video alamaz — sebebi filigran
yokluğu, anahtarın kimin olduğu onu değiştirmez); MODEL EŞİĞİ yarısı ise
anahtara BAKAR (1b-A). Eşik için kaynağı öğrenmek `check_anahtar`ı öne almayı
GEREKTİRMİYOR: `platform_anahtari.kaynak` aynı soruyu 409 fırlatmadan
cevaplıyor, o yüzden rota "planında yok" derken anahtar kapısı hâlâ hiç
sorulmamış oluyor (bekçisi tests/test_planlar.py). Sıranın kendisi neden
korundu: planın kapsamadığı modele "anahtar yok" (409) demek kullanıcıyı
anahtar girmeye yönlendirirdi ve anahtar girse de kapı açılmazdı. Plan yüklü
satırdan, yoksa DB'den (`kullanici_plani`) — istek başına ek sorgu yok.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Mapping

from fastapi import HTTPException
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session

import assets_store
import catalog
import chat_store
import credstore
import etiket
import i18n
import storage
from services import defter, depo_klasor, dil, kuyruk, planlar, platform_anahtari
from services.tablolar import Kullanici

# Kullanıcı başına eş zamanlı (`bekliyor` + `calisiyor`) iş tavanı — `.env.example`
# aynı adı buradan okur (bekçisi tests/test_docker_kapisi.py `ALTYAPI`).
# 4, çünkü arena turu istemci fan-out'uyla 2-4 AYRI istek (core.js `runArena`) ve
# dördüncü sütunun 429 yemesi turu "3/4" diye bitirirdi. Küresel işçi kapasitesi
# ayrı bir kapı (`KROMIS_ISCI_ES_ZAMANLI` × işçi sayısı, services/isci.py).
ES_ZAMANLI_IS_ENV = "KROMIS_KULLANICI_ES_ZAMANLI_IS"
ES_ZAMANLI_IS_VARSAYILAN = 4
# 429'un `Retry-After`ı (sn), belge §4'ün sayısı: sağlayıcı çağrısı saniyelerle
# değil dakikalarla ölçülüyor, daha sık gelen bir yeniden deneme aynı cevabı
# alırdı; istemci (core.js) bunu bir ipucu olarak okur, uyumak zorunda değil.
RETRY_AFTER_SN = 30


def check_folder(folder_id: str | None, db: Session, kullanici_id: uuid.UUID) -> str | None:
    """Boş/None ise kök (None). Doluysa klasörün BU KULLANICININ olduğunu doğrular, yoksa 404.

    `(db, kullanici_id)` ÇAĞIRANDAN geliyor (rotanın `OTURUM`u ve kapının
    çözdüğü kullanıcı): bu kapı VARLIK soruyor, yani depoya bakıyor ve hangi
    kullanıcının klasörlerine bakacağını rota söyler — süreç geneli bir okuma
    kapısı değil (Faz 0 / 4; Faz 1 / 5'te `output_dir` → `klasorler` satırı).
    Başkasının klasörü "yok" sayılır: 403 id uzayını sızdırırdı.
    """
    if not folder_id:
        return None
    if not depo_klasor.var_mi(db, kullanici_id, folder_id):
        raise HTTPException(status_code=404, detail=i18n.t("err.folder_missing", dil.aktif()))
    return folder_id


def check_session(session_id: str | None) -> str | None:
    """Boş/None ise oturum dışı üretim (None). Doluysa BİÇİMİ doğrular, 422.

    `check_folder`'ın aksine VARLIK kapısı yok — bilerek. Konsaydı, oturum kaydı
    diske yazılmadan önce (otomatik kayıt kapalıyken hiç yazılmıyor) ya da oturum
    başka bir sekmede silindikten sonra yapılan üretim 422 ile düşerdi: pahalı bir
    Azure turu bir ETİKET yüzünden kaybedilirdi. Ters yön de zaten hoşgörülü —
    silinmiş görselin dökümde bıraktığı sarkan id kaydı çökertmiyor (tasarım §5),
    simetrik duruş tutarlı olan.

    Sessizce düşürmek seçenek değil: kullanıcı üretimini oturumda göremez ve
    sebebi hiçbir yerde görünmezdi.
    """
    if not session_id:
        return None
    if not chat_store.valid_id(session_id):
        raise HTTPException(status_code=422, detail=i18n.t("err.bad_session_id", dil.aktif()))
    return session_id


def check_arena(arena_id: str | None) -> str | None:
    """Boş/None ise arena değil (None). Doluysa BİÇİMİ doğrular, 422.

    `check_session` ile aynı duruş: VARLIK kapısı yok (turun ilk isteği
    yazıldığında ortada henüz başka kayıt yoktur), yalnız biçim. Biçim kapısı
    ise zorunlu — geçersiz bir id depoda sessizce düşerdi ve turun sütunları
    birbirini hiç bulamazdı.
    """
    if not arena_id:
        return None
    if not storage.valid_id(arena_id):
        raise HTTPException(status_code=422, detail=i18n.t("err.bad_arena_id", dil.aktif()))
    return arena_id


def check_asset_kind(kind: str, *, allow_all: bool = False) -> None:
    if allow_all and kind == "all":
        return
    if kind not in assets_store.KINDS:
        raise HTTPException(status_code=404, detail=i18n.t("err.unknown_kind", dil.aktif()))


def es_zamanli_is_tavani(ortam: Mapping[str, str] | None = None) -> int:
    """`KROMIS_KULLANICI_ES_ZAMANLI_IS`; boşsa 4. Bozuk değer YÜKSEK SESLE: sessizce 4'e
    düşen bir tavan, operatörün "10 yaptım" sanmasıyla biterdi."""
    ham = ((os.environ if ortam is None else ortam).get(ES_ZAMANLI_IS_ENV) or "").strip()
    if not ham:
        return ES_ZAMANLI_IS_VARSAYILAN
    try:
        deger = int(ham)
    except ValueError as e:
        raise ValueError(f"{ES_ZAMANLI_IS_ENV} tam sayi olmali, verilen: {ham!r}") from e
    if deger < 1:
        raise ValueError(f"{ES_ZAMANLI_IS_ENV} en az 1 olmali, verilen: {deger}")
    return deger


def check_is_tavani(db: Session, kullanici_id: uuid.UUID) -> None:
    """Kullanıcının aktif işi tavana ulaşmışsa 429 + `Retry-After`; değilse sessiz.

    Sayım `kuyruk.aktif_sayisi` (`bekliyor` + `calisiyor`): bitmiş/düşmüş/iptal
    işler sayılmaz — geçmiş bir ceza değil, o anki yük. Kapı doğrulamanın
    SONUNDA ve girdi nesnesi yazılmadan ÖNCE koşar: 422 alacak bir istek 429
    ile maskelenmesin, 429 alacak bir istek depoya nesne bırakmasın. Her
    istekte ortamı yeniden okur (süreç başına bir kez okumak testte
    yamalanamazdı; bir `os.environ.get` ölçülecek bedel değil).
    """
    tavan = es_zamanli_is_tavani()
    if kuyruk.aktif_sayisi(db, kullanici_id) >= tavan:
        raise HTTPException(status_code=429,
                            detail=i18n.t("err.is_kuyrugu_dolu", dil.aktif(), tavan=tavan),
                            headers={"Retry-After": str(RETRY_AFTER_SN)})


def check_anahtar(cred_id: str, kimlikler: Mapping[str, str]) -> str:
    """Bu kimlikle üretilebiliyor mu; evetse işin `anahtar_kaynagi`, hayırsa 409.

    409 (çakışma: hesabın durumu isteği karşılamıyor), 502 DEĞİL — 502
    sağlayıcının cevabıydı (Faz 1), burada sağlayıcıya hiç gidilmiyor; 422 de
    değil, istek biçimce doğru. Cümle sağlayıcının ADINI ve ortam değişkenini
    söyler (`credstore.resolve`ın kararı): kullanıcı Ayarlar'da neyi arayacağını
    bilmeli. Kaynak `None` çıkarsa (`is_configured` geçti ama anahtar adı
    eşlenemedi — bugün olmayan bir katalog durumu) `kullanici` sayılır: platform
    parasını harcamadan sayılmasın diye değil, tavanı gevşetmesin diye — o iş
    günlük toplama girmez ama sahibin de anahtarı değildir.
    """
    if not credstore.is_configured(cred_id, kimlikler):
        cred = catalog.credential(cred_id)
        raise HTTPException(
            status_code=409,
            detail=i18n.t("err.anahtar_yok", dil.aktif(),
                          kimlik=etiket.label_of(cred) if cred is not None else cred_id,
                          env=cred.key_env if cred is not None else cred_id))
    return platform_anahtari.kaynak(cred_id, kimlikler) or platform_anahtari.KAYNAK_KULLANICI


def kullanici_plani(db: Session, kullanici: Kullanici) -> str:
    """İsteğin kullanıcısının planı — YÜKLÜ nesneden, yüklü değilse DB'den (`defter.plan_oku`).

    Kimlik kapısı satırı çoktan çekti (`oturumlar` ⋈ `kullanicilar`, tek sorgu;
    tests/test_kimlik.py "istek başına tam bir sorgu" bekçisi): plan orada.
    Ek SELECT yalnız öznitelik YÜKLÜ DEĞİLSE — testlerin `kullanici` override'ı
    (`server_default`lı sütun flush'ta expire olur, oturum kapanmış:
    `DetachedInstanceError`; `_yetersiz_bakiye`nin dersi). `inspect().dict`
    lazy yüklemeyi TETİKLEMEZ, o yüzden o hataya hiç varılmaz.
    """
    yuklu = sa_inspect(kullanici).dict.get("plan")
    return str(yuklu) if yuklu else defter.plan_oku(db, kullanici.id)


def check_plan(db: Session, kullanici: Kullanici, spec: catalog.ImageModel,
               kimlikler: Mapping[str, str]) -> str:
    """Kullanıcının planı bu modeli kapsıyor mu; evetse plan adı, hayırsa 403 `err.plan_kapsamiyor` (Faz 3 / 3, K7).

    Gövde `{"kod", "model", "plan"}` — cümle YOK, ön yüz `kod`u kendi dilinde
    kurar (`err.plan_kapsamiyor`), iki alan "hangi model, hangi plan" der.
    Karar `planlar.kapsiyor`da — model dökümünün `sebep: "plan"` dediği modele
    rota da 403 der, iki cevap doğmaz.

    `kimlikler` YALNIZ anahtarın KAYNAĞINI okumak için (Faz 4 / 1b, 1b-A);
    `platform_anahtari.kaynak` hata FIRLATMAZ, o yüzden bu kapı hâlâ anahtar
    kapısından önce koşabiliyor ve 403'te `check_anahtar` hiç sorulmuyor —
    `sebep`in "plan önce" duruşu rotada da böyle korunuyor.
    """
    plan = kullanici_plani(db, kullanici)
    kaynak = platform_anahtari.kaynak(spec.credential, kimlikler)
    if not planlar.kapsiyor(plan, spec, platform_anahtariyla=kaynak == platform_anahtari.KAYNAK_PLATFORM):
        raise HTTPException(status_code=403,
                            detail={"kod": "err.plan_kapsamiyor", "model": spec.id, "plan": plan})
    return plan


def _yetersiz_bakiye(db: Session, kullanici: Kullanici, bakiye: int, gereken: int, *,
                     hibe: int, paket: int) -> HTTPException:
    """402 gövdesi (K11): `kod` + sayılar/ad; cümle YOK — ön yüz `kod`u kendi dilinde kurar
    (`err.kredi_yetersiz`), alanlar kullanıcıya "ne kadar var, ne kadar lazım, hangi plan" der.
    `bakiye` iki kovanın TOPLAMI (Faz 3'ün adı korunur — ön yüz onu okur), `hibe`/`paket` kovalar ayrı (Faz 4 / 2).

    `plan` DB'den, `kullanici.plan`dan değil: sütun `server_default`lı ve
    bağımlılığın verdiği nesne başka bir oturumdan gelmiş/süresi geçmiş
    olabilir (testlerin `kullanici` override'ı ayrılmış bir nesne verir) —
    `DetachedInstanceError` yerine tek `SELECT`, yalnız hata yolunda.
    """
    plan = db.scalar(select(Kullanici.plan).where(Kullanici.id == kullanici.id))
    return HTTPException(status_code=402,
                         detail={"kod": "err.kredi_yetersiz", "bakiye": bakiye, "gereken": gereken,
                                 "plan": plan, "hibe": hibe, "paket": paket})


def check_bakiye(db: Session, kullanici: Kullanici, kredi_tahmini: int, anahtar_kaynagi: str | None) -> None:
    """Salt okunur ön denetim: platform işinde iki kovanın TOPLAMI `< tahmin` ise 402; BYOK'ta sessiz (K3).

    Kapı zincirinin SONUNDA, `check_gunluk`ten sonra (K9: tavan önce sorulur,
    429 dediyse bakiye hiç okunmaz bile). Kesin karar `rezerve_kredi`nin —
    bu okuma yalnız girdi nesnesi yazılmadan önce çoğunluğu çevirir.
    """
    if anahtar_kaynagi != platform_anahtari.KAYNAK_PLATFORM:
        return
    b = defter.bakiye(db, kullanici.id)
    if b.toplam < kredi_tahmini:
        raise _yetersiz_bakiye(db, kullanici, b.toplam, kredi_tahmini, hibe=b.hibe, paket=b.paket)


def rezerve_kredi(db: Session, kullanici: Kullanici, is_id: uuid.UUID, kredi_tahmini: int,
                  anahtar_kaynagi: str | None) -> defter.Hareket | None:
    """Platform işinin tahminini defterden düşer (`defter.rezerve`, atomik); yetmezse 402. BYOK → `None`.

    `kuyruk.ekle`den SONRA, aynı transaksiyonda (rezerv satırı `is_id` taşır);
    402 fırlarsa rota `OTURUM`u geri alır — kuyrukta öksüz iş kalmaz, bakiye
    değişmez (`rezerve` yetmeyince satır da yazmaz).
    """
    if anahtar_kaynagi != platform_anahtari.KAYNAK_PLATFORM:
        return None
    try:
        return defter.rezerve(db, kullanici.id, is_id, kredi_tahmini)
    except defter.YetersizBakiye as e:
        raise _yetersiz_bakiye(db, kullanici, e.bakiye, e.gereken, hibe=e.hibe, paket=e.paket) from e
