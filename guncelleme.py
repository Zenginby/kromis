# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Yeni bir sürüm çıktı mı? — GitHub'ın son yayınına bakan, sessiz kontrol.

NEDEN VAR: paketler artık main'e giren her değişiklikte otomatik üretiliyor,
yani yayınlar eskisinden çok daha sık çıkıyor. Kullanıcının bunu öğrenmesinin
tek yolu GUNCELLEME.md'yi kendiliğinden açıp bakmaktı — pratikte hiç olmayan
bir şey. Uygulama artık kendisi söylüyor.

BİLDİRİM, GÜNCELLEYİCİ DEĞİL: burada indirme, kurma ya da kendini değiştirme
YOK. Kullanıcıya yalnız "yeni sürüm var, bağlantı burada" deniyor. Otomatik
güncelleme üç platformda üç ayrı imzalama/notarization zinciri gerektirir ve
imzasız bir kendi kendini değiştirme yolu, uygulamaya açılmış bir kapıdır.

ÜÇ SÖZLEŞME — üçü de ihlal edilirse zarar sessiz olur, o yüzden testte:

  1. **Asla exception sızdırmaz.** Ağ yoksa, GitHub 500 dönerse, JSON bozuksa:
     `None`. Bu uygulama çevrimdışı da kullanılabiliyor (üretim dışında her şey
     yerelde koşuyor) ve bir sürüm kontrolünün ayarlar panelini açılamaz hâle
     getirmesi kabul edilemez.
  2. **İstek yolunu HİÇ bekletmez.** `/api/settings` senkron bir rota ve
     Starlette onu threadpool'da koşturuyor; oraya 5 saniyelik bir ağ çağrısı
     koymak paneli her açılışta bekletirdi. Kontrol arka planda koşuyor, rota
     yalnız ÖNBELLEĞE bakıyor: ilk açılışta cevap "bilmiyorum" (None) olur,
     birkaç saniye sonrakinde gerçek cevap gelir.
     TEK İSTİSNA `simdi_kontrol_et()`: onu kullanıcı KENDİ başlatıyor ve
     beklediği şey tam olarak cevap. Sözleşme AÇILIŞ yolunu koruyor, elle
     basılan bir düğmeyi değil — gerekçe o işlevin başlığında.
  3. **Kullanıcı kapatabilir.** `prefs.guncelleme_kontrolu` kapalıysa ağa hiç
     çıkılmaz. Uygulamanın kullanıcının haberi olmadan dışarıya bağlanması,
     kapatılabilir olmadığı sürece savunulamaz.

Depo public olduğu için uç nokta anonim çalışıyor — pakete gömülmüş bir token
YOK ve olmamalı.

BU CÜMLE BİR ŞART, BETIMLEME DEĞİL. Özel bir depoda `releases/latest` anonim
çağrıya 404 dönüyor ve 1. sözleşme (asla exception sızdırma) onu `None`'a
çeviriyor: kontrol sessizce ÖLÜR, kullanıcı yeni sürümü hiç öğrenmez ve
hiçbir yerde bir hata görünmez. 2026-09-10'da tam olarak bu durumdaydı —
depo o gün `private`'tı ve

    curl -s -o /dev/null -w "%{http_code}"       https://api.github.com/repos/Zenginby/kromis/releases/latest

404 döndürüyordu. Depo görünürlüğü değiştirilirse burası çalışmayacak; çözüm
pakete token gömmek DEĞİL (bir okuma token'ı bile paketi indiren herkese
verilmiş olurdu), yayın bilgisini token istemeyen bir yerden okumak ya da
özelliği kapatmak.

ŞART 2026-09-11'de SAĞLANDI ve ölçüldü: depo public'e açıldı, aynı `curl`
200 dönüyor, `_sor()` artık `None` değil `{"surum": …, "url": …}` veriyor.
Bu satır bir kutlama değil, kontrolün canlı olduğunun tarihli kanıtı —
görünürlük bir gün geri alınırsa yukarıdaki sessiz ölüm aynen geri gelir.
"""
from __future__ import annotations

import json
import os
import threading
import time
import traceback

import errlog
import jsonstore
import paths
import version

# Yayınların okunduğu depo. Sabit: uygulama kendi kaynağını biliyor.
DEPO = "Zenginby/kromis"
API = f"https://api.github.com/repos/{DEPO}/releases/latest"
YAYIN_SAYFASI = f"https://github.com/{DEPO}/releases/latest"

# Cevaptan gelen `html_url`in taşımak ZORUNDA olduğu önek. Bkz. `_guvenli_url`.
GECERLI_URL_ONEKI = f"https://github.com/{DEPO}/"

ONBELLEK_DOSYASI = "guncelleme.json"

# 24 saat. Daha sık kontrol etmenin kullanıcıya hiçbir faydası yok (yayın günde
# birkaç kez çıksa bile "yarın görürsün" yeterli), GitHub'a gereksiz istek
# göndermenin ise bir maliyeti var: anonim API saatte 60 istekle sınırlı ve o
# sınır IP başına — aynı ağdaki birkaç kullanıcı onu paylaşıyor.
TTL_SANIYE = 24 * 60 * 60

# BAŞARISIZ kontrolün geri çekilmesi — 24 saat DEĞİL, 30 dakika.
#
# Bir dönem başarısızlık da `zaman`ı damgalıyordu, yani tek bir zaman aşımı
# kullanıcıyı tam bir gün kör bırakıyordu. Telefonda bu, masaüstünden çok daha
# sık: `ZAMAN_ASIMI_SANIYE` 5 sn ve mobil veride (asansör, metro, uçak kipi,
# captive portal) o sınır kolayca aşılıyor. 2026-09-12'de ölçüldü — v0.20.1
# yayınlandı, telefon bildirimi hiç göstermedi; sebep kırık bir kod değil,
# başarısız bir kontrolün başarılı bir kontrolle AYNI cezayı almasıydı.
#
# Ayrı sabit ŞART, `TTL_SANIYE`yi kısaltmak değil: ikisi iki ayrı şeyi ölçüyor.
# `TTL_SANIYE` "elimizdeki cevap ne kadar tazedir", bu ise "başarısız bir
# denemeden sonra ne kadar bekleyelim". Tek sayıya indirgemek, ağı olmayan bir
# makinede her `/api/settings` çağrısının yeni bir iş parçacığı doğurmasına
# (aslen bu damgalamanın DOĞUŞ sebebi) geri dönmek olurdu.
HATA_TTL_SANIYE = 30 * 60

# Zaman aşımı bilinçle kısa: bu çağrı hiçbir şeyi bloke etmiyor, ama bir
# iş parçacığını dakikalarca asılı bırakmasının da anlamı yok.
ZAMAN_ASIMI_SANIYE = 5.0

_KILIT = threading.Lock()
_KOSUYOR = False


def web_yapisi() -> bool:
    """Web sürümü mü? — bu kontrol orada KAPALI (sahibin 2026-09-17 kararı, Faz 1 / 9).

    GitHub Releases denetimi dondurulmuş masaüstü/Android paketi için anlamlı:
    kullanıcı kendi paketini indirir. Web'de sunucuyu işleten güncelliyor;
    "yeni sürüm var" satırı kullanıcıya yapamayacağı bir iş söyler (yanlış
    pozitif) ve her açılış dış ağa gereksiz bir istek olur. Bayrak TEK ve
    ÖDÜNÇ: `DATABASE_URL` verilmişse web (`services.cerez.guvenli`nin ölçütüyle
    aynı) — ikinci bir `KROMIS_WEB` bayrağı iki ölçütün bir gün ayrışması demekti.
    Kapı rotada (routers/ayarlar.py): üç güncelleme rotası bu modüle hiç
    inmez, `guncelleme.json` da yazılmaz. `services.db` burada ERTELİ ithal:
    modül dondurulmuş kabukta da yükleniyor ve SQLAlchemy'yi bu bayrak için
    ithal anında yüklemek gereksiz.
    """
    from services import db

    return db.baglanti_dizesi() is not None


def _onbellek_yolu(output_dir: str) -> str:
    return os.path.join(output_dir, ONBELLEK_DOSYASI)


def _zaman(deger: object) -> float:
    """Önbellekteki bir zaman damgası — bozuksa 0 (yani "hiç").

    `float(...)` çıplak bırakılamaz: bu dosya elle düzenlenebiliyor ve
    `"zaman": "dün"` gibi bir değer `bilgi()`den ValueError olarak çıkıp
    `/api/settings`i 500'e düşürürdü. Birinci sözleşme (asla exception
    sızdırma) yalnız ağ yolunu değil, ÖNBELLEK yolunu da kapsıyor.
    """
    try:
        # `object` → `float()` mypy için bir tür hatası, burada ise sözleşmenin
        # kendisi: her tür bilerek kabul ediliyor ve `float`ın reddettiği
        # aşağıdaki `except`e düşüyor. Parametreyi daraltmak (`str | float`)
        # o kapıyı tip denetçisine taşırdı — davranış aynı kalsın diye yok sayılıyor.
        return float(deger or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _oku(output_dir: str) -> dict:
    """Önbellek. Bozuksa boş — okuma yolu HOŞGÖRÜLÜ (prefs.py ile aynı duruş)."""
    yol = _onbellek_yolu(output_dir)
    if not os.path.exists(yol):
        return {}
    try:
        with open(yol, encoding="utf-8") as f:
            veri = json.load(f)
        return veri if isinstance(veri, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _yaz(output_dir: str, veri: dict) -> None:
    try:
        jsonstore.write_atomic(_onbellek_yolu(output_dir), veri)
    except OSError:
        # Önbellek yazılamıyorsa (disk dolu, salt-okunur dizin) kontrol yine de
        # çalışmış olur; yalnız her seferinde yeniden sorulur. Kullanıcıya
        # gösterilecek bir hata yok.
        pass


def surum_daha_yeni(uzak: str, yerel: str) -> bool:
    """'0.10.0' > '0.9.0' — SAYISAL karşılaştırma.

    Sözlük sırası burada gerçek bir tuzak: '0.10.0' < '0.9.0' derdi ve onuncu
    yama sürümünden sonra uygulama güncellemeleri görmeyi bırakırdı. Kırılma
    sessiz: hiçbir hata çıkmaz, yalnız bildirim bir daha hiç gelmez.
    """
    def parcala(s: str) -> tuple[int, ...]:
        return tuple(int(p) for p in s.strip().lstrip("v").split("."))

    try:
        return parcala(uzak) > parcala(yerel)
    except (ValueError, AttributeError):
        return False


def _guvenli_url(ham: object) -> str:
    """`html_url` KENDİ depomuzu göstermiyorsa sabit yayın sayfasına düşülür.

    Bu adres arayüzde tıklanabilir bir "indir" bağlantısına dönüşüyor
    (`static/settings.js` → `#settings-update-link.href`), yani gövdeden gelen
    bir dizeyi doğrulamadan geçirmek kullanıcıyı tek tıkla yabancı bir adrese
    götürebilir.

    Risk soyut değil: `follow_redirects=True` bilinçli olarak açık (depo bir
    gün yeniden adlandırılırsa kontrol sessizce ölmesin diye) ve v0.5.3'te depo
    gerçekten taşındı — eski hesap adı boşaldı. Yayınlanmış eski istemciler
    hâlâ o yolu istiyor; o adı alan biri isteği kendi `releases/latest`ine
    yönlendirebilir. Bu doğrulamayla en kötü sonuç sahte bir "yeni sürüm var"
    satırı olur; bağlantı her hâlde bizim yayın sayfamıza gider.

    Yeniden adlandırma gerçekten olursa bu kapı yolu kırmıyor: sabit adres de
    aynı yönlendirmeyi izleyip yeni depoya varıyor.
    """
    url = str(ham or "")
    return url if url.startswith(GECERLI_URL_ONEKI) else YAYIN_SAYFASI


def _sor() -> dict | None:
    """GitHub'a sorar. Her hatada None — birinci sözleşme.

    `httpx` burada, modül düzeyinde DEĞİL fonksiyon içinde import ediliyor:
    modül `paths`/`prefs` gibi erken yüklenen bir zincire girse bile import
    maliyeti ödenmesin ve httpx bulunmayan bir ortamda (ör. yalnız bu modülü
    içe aktaran bir test) import zinciri kırılmasın.
    """
    try:
        import httpx

        yanit = httpx.get(
            API,
            timeout=ZAMAN_ASIMI_SANIYE,
            headers={"Accept": "application/vnd.github+json"},
            follow_redirects=True,
        )
        yanit.raise_for_status()
        veri = yanit.json()
        etiket = str(veri.get("tag_name") or "").strip()
        if not etiket:
            return None
        return {"surum": etiket.lstrip("v"), "url": _guvenli_url(veri.get("html_url"))}
    except Exception:                             # bilinçle geniş: bkz. 1. sözleşme
        # Sessiz ama İZSİZ değil: kullanıcı bir şey görmüyor, ama sürekli
        # başarısız olan bir kontrolün teşhis edilebilir olması gerekiyor.
        # `safe_append` loglama hatasında da patlamıyor — app.py'deki desenin
        # aynısı.
        errlog.safe_append(paths.data_dir(), "güncelleme kontrolü:\n" + traceback.format_exc())
        return None


def _son_basari(onbellek: dict) -> float:
    """Son BAŞARILI kontrolün zamanı. `surum` yoksa cevap hiç alınmamıştır.

    `surum` denetimi bir GÖÇ kapısı: eski düzende başarısız kontrol de `zaman`
    yazıyordu, yani diskte "damgalı ama cevapsız" kayıtlar var. O damgayı
    başarı saymak, düzeltilen kusuru bir tur daha yaşatırdı — kayıt yalnız
    `surum` taşıyorsa anlamlıdır.
    """
    if not onbellek.get("surum"):
        return 0.0
    return _zaman(onbellek.get("zaman"))


def _tazeleme_gerek(onbellek: dict) -> bool:
    """İKİ kapı: cevap bayat MI, ve son denemenin üstünden yeterince geçti Mİ."""
    simdi = time.time()
    if simdi - _son_basari(onbellek) <= TTL_SANIYE:
        return False                      # elimizdeki cevap hâlâ taze
    return simdi - _zaman(onbellek.get("son_deneme")) > HATA_TTL_SANIYE


def _kontrol_et(output_dir: str) -> bool:
    """Tek bir kontrol turu. Başarılıysa True. ASLA fırlatmaz (1. sözleşme).

    `_tazele`den AYRI bir işlev, çünkü elle tetiklenen kontrol (`simdi_kontrol_et`)
    aynı turu iş parçacığı bayrağına DOKUNMADAN koşmak zorunda: `_tazele`nin
    `finally`si `_KOSUYOR`u sıfırlıyor ve elle çağrı onu sıfırlasaydı, o sırada
    koşan bir arka plan tazelemesinin bayrağını düşürüp ikinci bir iş
    parçacığının doğmasına yol açardı.

    `son_deneme` HER İKİ dalda da yazılıyor, `zaman` yalnız başarıda: geri
    çekilmeyi ölçen damga ile cevabın tazeliğini ölçen damga aynı şey değil
    (bkz. HATA_TTL_SANIYE).
    """
    sonuc = _sor()
    simdi = time.time()
    if sonuc is not None:
        _yaz(output_dir, {"zaman": simdi, "son_deneme": simdi, **sonuc})
        return True
    # Başarısızlık da damgalanıyor — yoksa ağı olmayan bir makinede her
    # `/api/settings` çağrısı yeni bir iş parçacığı başlatırdı. Ama damga
    # `zaman` DEĞİL: elimizdeki cevabı tazelemedik, yalnız denedik.
    mevcut = _oku(output_dir)
    mevcut["son_deneme"] = simdi
    _yaz(output_dir, mevcut)
    return False


def _tazele(output_dir: str) -> None:
    global _KOSUYOR
    try:
        _kontrol_et(output_dir)
    finally:
        with _KILIT:
            _KOSUYOR = False


def _tazeleme_baslat(output_dir: str) -> None:
    """Arka planda tek bir tazeleme koşsun — ikinci sözleşme.

    Bayrak olmadan, ayarlar panelini üst üste açan bir kullanıcı her açılışta
    yeni bir iş parçacığı doğururdu.
    """
    global _KOSUYOR
    with _KILIT:
        if _KOSUYOR:
            return
        _KOSUYOR = True
    threading.Thread(
        target=_tazele, args=(output_dir,), name="guncelleme-kontrolu", daemon=True
    ).start()


def bilgi(output_dir: str, *, izin: bool = True) -> dict | None:
    """Kullanıcıya gösterilecek güncelleme bilgisi ya da None.

    None üç ayrı durumu birden anlatıyor ve arayüz için üçü de aynı: "gösterecek
    bir şey yok." (a) kontrol kapalı, (b) henüz cevap yok, (c) elimizdeki sürüm
    zaten en yenisi.
    """
    if not izin:
        return None                       # üçüncü sözleşme: ağa hiç çıkma

    onbellek = _oku(output_dir)
    if _tazeleme_gerek(onbellek):
        _tazeleme_baslat(output_dir)

    uzak = str(onbellek.get("surum") or "")
    if uzak and surum_daha_yeni(uzak, version.APP_VERSION):
        # Önbellekteki adres de doğrulanıyor, yalnız yazma anında değil: bu
        # dosya sürüm yükseltmelerini AŞARAK kalıyor, yani `_guvenli_url`
        # eklenmeden önce yazılmış (ya da elle bozulmuş) bir kayıt buraya
        # doğrulanmamış bir adresle girebilir.
        return {"surum": uzak, "url": _guvenli_url(onbellek.get("url"))}
    return None


# Elle kontrolün sonucu. `bilgi()`nin `None`ı burada YETMİYOR: o, "zaten
# güncelsin" ile "soramadım"ı aynı cevaba indiriyor ve arayüz için ikisi aynı
# olabiliyordu (satır gizli kalır). Kullanıcının BASTIĞI bir düğmede ise fark
# asıl bilginin kendisi — "kontrol ettim, güncelsin" bir cevap, sessizlik değil.
DURUM_YENI = "yeni"
DURUM_GUNCEL = "guncel"
DURUM_HATA = "hata"
DURUM_KAPALI = "kapali"


def simdi_kontrol_et(output_dir: str, *, izin: bool = True) -> dict:
    """Elle tetiklenen kontrol: TTL'i BAYPAS eder ve sonucu BEKLER.

    `{"durum": …, "guncelleme": {…}|None}` döner.

    İKİNCİ SÖZLEŞMEYİ (istek yolunu asla bekletme) BİLEREK UYGULAMIYOR ve bu
    bir ihlal değil, sözleşmenin kapsamı: o kural `/api/settings`i, yani
    uygulamanın AÇILIŞ yolunu koruyor — oraya 5 saniyelik bir ağ çağrısı koymak
    paneli her açılışta bekletirdi. Burada isteği kullanıcı KENDİ başlatıyor ve
    beklediği şey tam olarak cevap; arka plana atıp `None` dönmek, düğmeye
    basınca hiçbir şey olmaması demek olurdu. Rota senkron, yani Starlette onu
    threadpool'da koşturuyor: bekleyen istek olay döngüsünü tutmuyor.

    TTL'İN BAYPAS EDİLMESİ BU UCUN VAR OLMA SEBEBİ: yayın hızı kontrol
    aralığından hızlıysa (2026-09-12'de ölçüldü: ortalama 7.7 saatte bir yayın,
    24 saatte bir kontrol) kullanıcının önbelleği taze ama cevabı bayat olur ve
    beklemekten başka yolu kalmaz. Düğme o yolu açıyor.

    Üçüncü sözleşme burada da geçerli: kontrol kapalıysa ağa HİÇ çıkılmıyor.
    """
    if not izin:
        return {"durum": DURUM_KAPALI, "guncelleme": None}

    if not _kontrol_et(output_dir):
        return {"durum": DURUM_HATA, "guncelleme": None}

    # `bilgi()` yeniden okuyor: karşılaştırmanın ve URL doğrulamasının tek
    # kopyası orada kalsın — burada tekrarlanan bir `surum_daha_yeni` çağrısı,
    # bir gün yalnız birinde düzeltilecek İKİNCİ bir kural olurdu.
    g = bilgi(output_dir, izin=True)
    return {"durum": DURUM_YENI if g else DURUM_GUNCEL, "guncelleme": g}
