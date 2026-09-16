# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İsteğin arayüz dili — çözen zincir, yazan ara katman, okuyan sarmalayıcı.

Faz 0 / Adım 3 (docs/faz0-web-first.md): dil artık İSTEĞİN KENDİSİNDEN
çözülüyor ve diskteki tercih zincirin bir halkası, kaynağın tamamı değil.
Sıra (`coz`):

  1. isteğin açık işareti — `X-Kromis-Lang` başlığı, sonra `kromis_lang` çerezi
  2. diskteki KAYITLI tercih (services/tercih.py — önbellekli)
  3. tarayıcının `Accept-Language` başlığı
  4. `i18n.DEFAULT`

Geçersiz bir halka (bilinmeyen jeton, bozuk başlık) zinciri DÜŞÜRMEZ, sıra
bir sonrakine geçer: `kromis_lang=de` ile gelen istek hata almaz, kayıtlı
tercihini görür.

NEDEN BU SIRA: kullanıcının EN SON ve EN YAKIN seçimi kazanmalı. Çerez o
tarayıcının seçimi (Ayarlar'da dil seçildiğinde `POST /api/prefs` yazıyor);
dosya bu kurulumun seçimi; başlık tarayıcının varsayımı; `DEFAULT` ürünün
kararı. Faz 1'de hesap tercihi 2. halkanın yerine (ya da yanına) takılacak
ve zincirin geri kalanı da ara katman da değişmeyecek — bu dosyanın var
olma sebebi tam olarak o eklemenin tek bir yerde olması.

`Accept-Language` ÖNCEDEN BİLEREK okunmuyordu ("kaynak tek olmalı; tarayıcı
çoğu zaman pywebview'ın penceresi, başlık kullanıcının tercihi bile değil").
Web-first kararıyla (Alperen Zengin, 2026-09-16) o gerekçe tersine döndü:
tarayıcı artık gerçek bir tarayıcı ve hiç tercih yazmamış bir ziyaretçi
için başlık elimizdeki tek ipucu. Eski kaygının cevabı sırada: başlık yalnız
DİSKTE KAYIT YOKKEN konuşuyor, kullanıcının seçimini hiçbir zaman ezmiyor.
"""
from __future__ import annotations

from fastapi import Request, Response

import i18n
from services import tercih, yollar

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
    """Her isteğin başında arayüz dilini kurar. `i18n._AKTIF`ın TEK YAZARI.

    NEDEN ARA KATMAN, rotada tek tek okumak DEĞİL: metni üreten yerlerin çoğu
    rotada değil — sekiz sağlayıcı istemcisinin `map_error`ı, `catalog`ın
    model notları, `chat_prompt`ın bağlam bloğu. Onların hepsine dili
    parametre olarak taşımak beş kademelik bir imza genişletmesi olurdu ve o
    zincire eklenen her yeni fonksiyon parametreyi unutmaya açık kalırdı.
    Tek bir yazar, tek bir okuma noktası.

    Disk artık İSTEK BAŞINA okunmuyor (Adım 3): kayıtlı tercih
    `services.tercih`in dosya imzalı önbelleğinden geliyor — değişen dosya
    yine bir sonraki istekte görünür (eski gerekçe: donmuş bir değer dili
    çeviren kullanıcıya sunucu yeniden başlayana kadar eski dili gösterirdi),
    ama bedeli `open`+`json.load` değil tek bir `stat`.

    Hata YUTULUYOR: dil, bir isteği düşürecek kadar önemli bir şey değil.
    `prefs.read_stored` bozuk dosyada zaten boş sözlüğe düşüyor; bu kapı onun
    ötesindeki durumlar için (okunamayan veri dizini).
    """
    try:
        i18n.set_active(coz(request))
    except OSError:
        i18n.set_active(i18n.DEFAULT)
    return await call_next(request)


def coz(request: Request) -> str:
    """İsteğin dili — modül başlığındaki zincir. Her zaman geçerli bir jeton."""
    for aday in (request.headers.get(BASLIK), request.cookies.get(CEREZ)):
        if aday in i18n.LANGUAGES:
            return aday
    kayitli = tercih.dil(yollar.output_dir())
    if kayitli is not None:
        return kayitli
    return accept_language(request.headers.get("accept-language")) or i18n.DEFAULT


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
    gezinmelerde taşınır, başka siteden POST'ta taşınmaz. `secure` YOK ve
    bilinçli: uygulama bugün loopback `http://` üzerinde; `Secure` çerezi
    düz HTTP'de tarayıcı saklamaz ve seçim sessizce kaybolurdu. HTTPS
    arkasına çıkıldığında (Faz 1) buraya eklenecek — tek yer.
    """
    response.set_cookie(CEREZ, dil_kodu, max_age=CEREZ_OMRU, path="/",
                        httponly=True, samesite="lax")


def aktif() -> str:
    """Bu isteğin arayüz dili. Yazan taraf yukarıdaki ara katman.

    İnce bir sarmalayıcı ve ADIYLA duruyor: rotalar `i18n.active()` çağırsaydı
    okuyan kişi "hangi istek?" sorusunu her seferinde yeniden sormak zorunda
    kalırdı. Testler dili sabitlemek için BURAYI yamalıyor
    (`monkeypatch.setattr(dil, "aktif", lambda: "en")`) — tek nokta.
    """
    return i18n.active()
