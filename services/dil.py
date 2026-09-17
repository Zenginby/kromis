# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İsteğin arayüz dili — çözen zincir, yazan ara katman + kimlik kapısı, okuyan sarmalayıcı.

Faz 0 / Adım 3 (docs/faz0-web-first.md): dil İSTEĞİN KENDİSİNDEN çözülüyor.
Faz 1 / 4 (docs/faz1-veritabani-hesaplar.md → 4): 3. halka artık diskteki
`prefs.json` değil HESABIN dili. Sıra (`coz`):

  1. isteğin açık işareti — `X-Kromis-Lang` başlığı
  2. …sonra `kromis_lang` çerezi
  3. oturumun kullanıcısının kayıtlı dili — `kullanicilar.dil` (NULL = hiç seçmedi)
  4. tarayıcının `Accept-Language` başlığı
  5. `i18n.DEFAULT`

Geçersiz bir halka (bilinmeyen jeton, bozuk başlık) zinciri DÜŞÜRMEZ, sıra
bir sonrakine geçer: `kromis_lang=de` ile gelen istek hata almaz, hesabının
dilini görür.

NEDEN BU SIRA: kullanıcının EN SON ve EN YAKIN seçimi kazanmalı. Çerez o
tarayıcının seçimi (Ayarlar'da dil seçildiğinde `POST /api/prefs` yazıyor);
hesap dili bu KULLANICININ seçimi (aynı `POST /api/prefs` `kullanicilar.dil`e
de yazıyor — başka bir cihazdan, çerezsiz girişte oradan gelir); başlık
tarayıcının varsayımı; `DEFAULT` ürünün kararı.

İKİ YAZAR, İKİ AN — ve ikisi de bu dosyada (`i18n._AKTIF`ın yazıcısı tek
modül kalıyor):

* `dil_baglami` (ara katman) isteğin BAŞINDA 1-2. ve 4-5. halkayı kurar ve
  1-2. halkanın konuşup konuşmadığını `request.state.dil_acik`a yazar.
* `kullanici_dili` (3. halka) kimlik kapısı kullanıcıyı çözdüğü anda çağrılır
  (services/kimlik.py `bagla`): 1-2. halka konuşmamışsa ve hesabın dili varsa
  bağlamı ONA çevirir. Ara katman kullanıcıyı KENDİSİ sorgulamıyor, bilerek:
  sorguyu kapı zaten yapıyor (belge: "ek sorgu SIFIR"), ara katmanın kendi
  `Session`ı ve ayrılmış bir `Kullanici` nesnesi ikinci bir yol açardı.
  Bedeli: kapıdan ÖNCE üretilen cevaplar (köken 403'ü — zaten KOD, dil yok;
  oturumsuz 401'in kendisi — kullanıcı yok) yalnız 1-2. ve 4-5. halkayı görür.
  422 doğrulama hatası kapıdan SONRA gelir (FastAPI alt bağımlılıkları gövde
  doğrulamasından önce çözüyor), yani hesabın dilinde.

`services/tercih.py` (dosya imzalı `prefs.json` okuyucusu) web yolunda ARTIK
OKUNMUYOR — çıkış ölçütü "dil DB'den geliyor (`prefs.json` okunmuyor)". Modül
dondurulmuş kabuk için duruyor, kararı 6. görevde (`prefs` ile birlikte).

`Accept-Language` ÖNCEDEN BİLEREK okunmuyordu ("kaynak tek olmalı; tarayıcı
çoğu zaman pywebview'ın penceresi, başlık kullanıcının tercihi bile değil").
Web-first kararıyla (Alperen Zengin, 2026-09-16) o gerekçe tersine döndü:
tarayıcı artık gerçek bir tarayıcı ve hiç tercih yazmamış bir ziyaretçi
için başlık elimizdeki tek ipucu. Eski kaygının cevabı sırada: başlık yalnız
HESAPTA KAYIT YOKKEN konuşuyor, kullanıcının seçimini hiçbir zaman ezmiyor.
"""
from __future__ import annotations

from fastapi import Request, Response

import i18n
from services import cerez

# Tarayıcının taşıdığı dil seçimi. `POST /api/prefs` `language` yazdığında
# aynı cevapla kuruluyor (routers/ayarlar.py → `cerez_yaz`); ön yüz çerezi
# hiç görmüyor ve görmesi gerekmiyor — kaydın ardından `location.reload()`
# yapıyor (static/settings.js) ve yeni sayfa çerezle geliyor.
CEREZ = "kromis_lang"

# İstek başına AÇIK seçim: API istemcileri ve testler için. Çerezden ÖNCE
# geliyor çünkü daha yakın — çerez tarayıcının kalıcı hâli, başlık bu tek
# isteğin sözü.
BASLIK = "X-Kromis-Lang"

# Bir yıl: tercih dosyası gibi "unutulmayan" bir seçim, oturum çerezi değil.
CEREZ_OMRU = 365 * 24 * 60 * 60


async def dil_baglami(request: Request, call_next):
    """Her isteğin başında arayüz dilini kurar (1-2., 4-5. halka); 3. halka `kullanici_dili`.

    NEDEN ARA KATMAN, rotada tek tek okumak DEĞİL: metni üreten yerlerin çoğu
    rotada değil — sekiz sağlayıcı istemcisinin `map_error`ı, `catalog`ın
    model notları, `chat_prompt`ın bağlam bloğu. Onların hepsine dili
    parametre olarak taşımak beş kademelik bir imza genişletmesi olurdu ve o
    zincire eklenen her yeni fonksiyon parametreyi unutmaya açık kalırdı.
    Tek bir okuma noktası (`aktif`), yazarı tek modül.

    Disk YOK, sorgu YOK: bu ara katman yalnız başlık ve çerez okuyor. Faz 0'ın
    `services/tercih.py` önbelleği burada okunuyordu; hesabın dili artık kimlik
    kapısının zaten getirdiği satırdan geliyor (modül başlığı).
    """
    acik = acik_secim(request)
    request.state.dil_acik = acik is not None
    i18n.set_active(acik or tarayici_dili(request))
    return await call_next(request)


def acik_secim(request: Request) -> str | None:
    """1-2. halka: `X-Kromis-Lang` başlığı, sonra `kromis_lang` çerezi; geçerli değilse `None`."""
    for aday in (request.headers.get(BASLIK), request.cookies.get(CEREZ)):
        if aday in i18n.LANGUAGES:
            return aday
    return None


def tarayici_dili(request: Request) -> str:
    """4-5. halka: `Accept-Language`, yoksa `i18n.DEFAULT`. Her zaman geçerli bir jeton."""
    return accept_language(request.headers.get("accept-language")) or i18n.DEFAULT


def coz(request: Request, kullanici_dil: str | None = None) -> str:
    """Zincirin TAMAMI tek işlevde — `kullanici_dil` hesabın kayıtlı dili (3. halka).

    Ara katman ve kapı bunu ikiye bölerek uyguluyor (yukarıda, neden); bu
    işlev sıranın TEK yazılı hâli ve testlerin ölçtüğü sözleşme.
    """
    acik = acik_secim(request)
    if acik is not None:
        return acik
    if kullanici_dil in i18n.LANGUAGES:
        return kullanici_dil
    return tarayici_dili(request)


def kullanici_dili(request: Request, kullanici_dil: str | None) -> None:
    """3. halka: kimlik kapısı kullanıcıyı çözdüğünde çağırır (services/kimlik.py `bagla`).

    Yalnız 1-2. halka SUSMUŞSA ve hesabın geçerli bir dili varsa yazar; aksi
    hâlde ara katmanın kurduğu bağlam durur. `ContextVar` isteğin görevinde
    yazılıyor (kapı `async def`, gerekçesi orada) — rota havuza giderken
    kopyasını alır.
    """
    if getattr(request.state, "dil_acik", False):
        return
    if kullanici_dil in i18n.LANGUAGES:
        i18n.set_active(kullanici_dil)


def accept_language(deger: str | None) -> str | None:
    """`Accept-Language` başlığından desteklenen İLK dil; yoksa `None`.

    RFC 9110 §12.5.4'ün yeterli kısmı: virgülle ayrılmış `etiket;q=ağırlık`
    parçaları, ağırlık yoksa 1, `q=0` "istemiyorum". Yalnız BİRİNCİL alt
    etiket bakılıyor (`tr-TR` → `tr`): sözlük bölge ayırmıyor. `*` ve
    tanınmayan etiketler `None`a katkı yapmıyor — joker "ne verirsen" demek
    ve cevabı `DEFAULT` zaten veriyor. Bozuk bir `q` (`q=abc`) parçayı
    düşürür, başlığı değil: dil bir isteği 400'e götürecek bir şey değil.

    Eşit ağırlıkta başlıktaki sıra kazanıyor (`min` kararlı: `(-q, sıra)`).
    """
    if not deger:
        return None
    adaylar: list[tuple[float, int, str]] = []
    for sira, parca in enumerate(deger.split(",")):
        etiket, _, parametreler = parca.strip().partition(";")
        agirlik = 1.0
        for parametre in parametreler.split(";"):
            ad, _, sayi = parametre.strip().partition("=")
            if ad.strip().lower() == "q":
                try:
                    agirlik = float(sayi.strip())
                except ValueError:
                    agirlik = 0.0
        birincil = etiket.strip().split("-")[0].lower()
        if agirlik <= 0 or birincil not in i18n.LANGUAGES:
            continue
        adaylar.append((-agirlik, sira, birincil))
    return min(adaylar)[2] if adaylar else None


def cerez_yaz(response: Response, dil_kodu: str) -> None:
    """Tarayıcıya dil çerezini kurar — `POST /api/prefs`in `language` yazımında.

    `httponly`: betiğin çerezi okumasına gerek yok (seçili dili sayfadan
    okuyor, `window.KROMIS_LANG`). `samesite=lax`: aynı siteden gelen
    gezinmelerde taşınır, başka siteden POST'ta taşınmaz. `secure` kararı
    BURADA DEĞİL, `services/cerez.py`de (Faz 1 / 3): dondurulmuş kabuk
    loopback `http://` üzerinde ve orada `Secure` çerezi tarayıcı saklamaz —
    seçim sessizce kaybolurdu; web'de (DATABASE_URL var) ise açık. Oturum
    çerezi de aynı karardan okuyor — iki çerez ayrışamaz.
    """
    response.set_cookie(CEREZ, dil_kodu, max_age=CEREZ_OMRU, path="/",
                        httponly=True, samesite="lax", secure=cerez.guvenli())


def aktif() -> str:
    """Bu isteğin arayüz dili. Yazan taraf yukarıdaki ara katman.

    İnce bir sarmalayıcı ve ADIYLA duruyor: rotalar `i18n.active()` çağırsaydı
    okuyan kişi "hangi istek?" sorusunu her seferinde yeniden sormak zorunda
    kalırdı. Testler dili sabitlemek için BURAYI yamalıyor
    (`monkeypatch.setattr(dil, "aktif", lambda: "en")`) — tek nokta.
    """
    return i18n.active()
