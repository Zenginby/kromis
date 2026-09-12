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

# Zaman aşımı bilinçle kısa: bu çağrı hiçbir şeyi bloke etmiyor, ama bir
# iş parçacığını dakikalarca asılı bırakmasının da anlamı yok.
ZAMAN_ASIMI_SANIYE = 5.0

_KILIT = threading.Lock()
_KOSUYOR = False


def _onbellek_yolu(output_dir: str) -> str:
    return os.path.join(output_dir, ONBELLEK_DOSYASI)


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


def _tazele(output_dir: str) -> None:
    global _KOSUYOR
    try:
        sonuc = _sor()
        if sonuc is not None:
            _yaz(output_dir, {"zaman": time.time(), **sonuc})
        else:
            # Başarısız kontrol de damgalanıyor: yoksa ağı olmayan bir makinede
            # her `/api/settings` çağrısı yeni bir iş parçacığı başlatırdı.
            mevcut = _oku(output_dir)
            mevcut["zaman"] = time.time()
            _yaz(output_dir, mevcut)
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
    if time.time() - float(onbellek.get("zaman") or 0) > TTL_SANIYE:
        _tazeleme_baslat(output_dir)

    uzak = str(onbellek.get("surum") or "")
    if uzak and surum_daha_yeni(uzak, version.APP_VERSION):
        # Önbellekteki adres de doğrulanıyor, yalnız yazma anında değil: bu
        # dosya sürüm yükseltmelerini AŞARAK kalıyor, yani `_guvenli_url`
        # eklenmeden önce yazılmış (ya da elle bozulmuş) bir kayıt buraya
        # doğrulanmamış bir adresle girebilir.
        return {"surum": uzak, "url": _guvenli_url(onbellek.get("url"))}
    return None
