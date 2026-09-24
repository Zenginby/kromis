# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kök sayfa: `index.html`in sürüm ve çeviri yerleştirilmiş hâli.

`/static` mount'u BURADA DEĞİL, `app.py`de: mount bir rota değil bir alt
uygulama ve `include_router` onu taşıyamaz. İki şeyin ayrı yerde durmasının
gerekçesi `app.py`deki mount yorumunda (no-store / önbellek asimetrisi).

Yerleştirmenin KENDİSİ de burada değil, `services/sablon.py`de (Faz 1 / 3):
ikinci sayfa (`GET /giris`, routers/hesap.py) aynı işi istedi ve router'lar
birbirini ithal edemez. `FileResponse` yerine neden şablon, neden `no-store`,
neden okuma hatası 500 HTML — üç gerekçe oraya taşındı.

SATIŞ YÜZÜ (Faz 4 / 4, belge §4): `GET /planlar` (`static/planlar.html` —
plan ve paket kartları, "Satın al" → `POST /api/odeme/checkout`) ve `GET
/odeme/tesekkur` (`static/tesekkur.html` — Polar'ın `success_url`u, bakiyeyi
yoklar). İkisi de `index` gibi `kimlik.sayfa_kullanicisi` taşır (oturumsuz 302
`/giris?sonra=<yol>`, `SAYFALAR`): teşekkür sayfası kullanıcının bakiyesini
okur, planlar sayfası da satın alma DÜĞMESİ taşır — fiyat listesinin kendisi
oturumsuz uçta (`GET /api/odeme/urunler`). Kendi belgeleri, stüdyonun 13
betiği YÜKLENMEZ (giris.html'in gerekçesi): oturumsuz ziyaretçiye ve bir
ödeme dönüşüne stüdyoyu indirmenin anlamı yok.

HUKUKİ METİNLER (Faz 4 / 6, belge §6): `GET /hukuk/{slug}` — `static/hukuk.html`
kabuğu + `bundled/hukuk/<slug>.<dil>.html` parçası (`services/hukuk.py`). AÇIK
rota (tests/test_kimlik.py `ACIK_ROTALAR`, gerekçesiyle): kayıt kutusu bu
sayfalara BAĞLANIYOR ve kayıt olmayan ziyaretçi metni okuyamazsa onay
"okudum" olmaz. Slug beyaz listede değilse 404 (kabuk yok — metin yok).
Dil `services/dil.py` zinciri (oturumsuz: başlık → çerez → Accept-Language),
cevabın `Content-Language` başlığı hangi dilin çizildiğini söyler.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

import i18n
from services import ayar, dil, hukuk, kimlik, sablon
from services.tablolar import Kullanici

router = APIRouter()


@router.get("/")
def index(kullanici: Kullanici = Depends(kimlik.sayfa_kullanicisi),
          ayarlar: ayar.Ayarlar = Depends(ayar.genel)) -> HTMLResponse:
    """index.html'i sürüm, dil ve sözlük yerine konarak servis eder (services/sablon.py).

    KAPI (Faz 1 / 4): oturumsuz ziyaretçi **302 `/giris`** alır —
    `kimlik.sayfa_kullanicisi`, API rotalarının 401'i değil; bu tarayıcı
    GEZİNMESİ olan tek rota (gerekçesi services/kimlik.py). Kullanıcı
    bağımlılığı ÖNCE: FastAPI alt bağımlılıkları imza sırasıyla çözüyor ve
    kapı ilk soru olmalı. Ayar nesnesi `ayar.genel`: sayfanın okuduğu tek
    dizin paylaşılan `static_dir`, kullanıcı dizini burada gerekmiyor —
    `ayar.ayarlar` kapıyı 401'le taşırdı. Dil zincirinin 3. halkası
    (`kullanicilar.dil`) kapıda uygulanıyor, yani sayfa hesabın dilinde çizilir.
    """
    return sablon.sayfa(ayarlar, "index.html")


@router.get("/planlar")
def planlar(kullanici: Kullanici = Depends(kimlik.sayfa_kullanicisi),
            ayarlar: ayar.Ayarlar = Depends(ayar.genel)) -> HTMLResponse:
    """`static/planlar.html` — satış sayfası (Faz 4 / 4); aynı yerleştirme, aynı kapı (gerekçe modül başında)."""
    return sablon.sayfa(ayarlar, "planlar.html")


@router.get("/odeme/tesekkur")
def odeme_tesekkur(kullanici: Kullanici = Depends(kimlik.sayfa_kullanicisi),
                   ayarlar: ayar.Ayarlar = Depends(ayar.genel)) -> HTMLResponse:
    """`static/tesekkur.html` — Polar'dan dönüş (Faz 4 / 4): `/api/kredi`yi 2 sn'de bir 30 sn yoklar."""
    return sablon.sayfa(ayarlar, "tesekkur.html")


def _hukuk_gezinme(secili: str) -> str:
    """Kabuğun alt gezinmesi: dört metne bağlantı, seçili olan `aria-current="page"`.

    Şablonda değil burada kuruluyor: seçili işaret slug'a bağlı ve `{{t:…}}`
    yalnız metin çevirir, öznitelik kuramaz. Etiketler `{{t:…}}` olarak kalıyor
    — yerleştirme `{{t:…}}`den ÖNCE koştuğu için çeviri yine `sablon.sayfa`da olur.
    """
    parcalar = []
    for slug in hukuk.SLUGLAR:
        simdiki = ' aria-current="page"' if slug == secili else ""
        parcalar.append(f'<a href="/hukuk/{slug}"{simdiki}>{{{{t:{hukuk.BASLIK_ANAHTARLARI[slug]}}}}}</a>')
    return "\n".join(parcalar)


@router.get("/hukuk/{slug}")
def hukuk_metni(slug: str, ayarlar: ayar.Ayarlar = Depends(ayar.genel)) -> HTMLResponse:
    """`bundled/hukuk/<slug>.<dil>.html` parçasını `static/hukuk.html` kabuğunda servis eder (gerekçe modül başında).

    Damga satırı `HUKUK_ONAYLI` `False` iken görünür (`__HUKUK_TASLAK_GIZLI__`
    boş), `True` olunca `hidden` — metin dosyasına dokunulmaz. Sürüm satırı
    `HUKUK_SURUMU`: kullanıcı onayladığı sürümü sayfada görür (kayıt damgası
    aynı sabiti yazıyor).
    """
    dil_kodu = dil.aktif()
    govde = hukuk.metin(slug, dil_kodu)
    if govde is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.hukuk_metni_yok", dil_kodu))
    cevap = sablon.sayfa(ayarlar, "hukuk.html", yerlestir={
        "__HUKUK_GOVDE__": govde,
        "__HUKUK_GEZINME__": _hukuk_gezinme(slug),
        "__HUKUK_SURUM__": hukuk.HUKUK_SURUMU,
        "__HUKUK_TASLAK_GIZLI__": "" if not hukuk.HUKUK_ONAYLI else "hidden",
    })
    cevap.headers["Content-Language"] = dil_kodu
    return cevap
