# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""fal.ai kuyruk teli — VİDEO (Wan · PixVerse · Kling · Seedance · FLUX 3 · MiniMax)
ve GÖRSEL (Qwen Image · Seedream · FLUX.1 schnell).

Deponun BEŞİNCİ tel formatı ve ilk TOPLAYICISI: tek anahtar, çok marka.
Sağlayıcı İKİ tabloda birden: `providers._VIDEO_ADAPTERS` (v0.23) ve
`providers._ADAPTERS` (2026-09-23, Faz 4 / 1b-D). Görsel tarafı bu dosyaya
"geldiği gün eklenecek" diye yazılmıştı; o gün geldi ve eklendi
(`generate`/`edit`), video işlevleri `generate_video`/`animate` adını aldı —
sevk memurunun görsel sözleşmesi `generate` adını istiyor.

DOSYA BÖLÜNMÜYOR (`azure_mai_client`/`azure_flux_client` gibi değil) ve
gerekçe o bölünmenin ÖLÇÜTÜNDEN geliyor: orada iki AYRI tel formatı vardı
(farklı yol, farklı gövde, farklı hata şekli). fal'da protokol TEK — görsel
ve video AYNI kuyruk döngüsünden (`_kuyruk_dongusu`: submit → yokla → sonuç →
indir) geçiyor; değişen yalnız gövdenin alan adları (`ALANLAR` /
`GORSEL_ALANLAR`) ve sonucun okunduğu anahtar (`video.url` / `images[0].url`).

ŞEMA KAYNAKLARI (2026-09-23, Faz 4 / 1b-D): dört yeni video ve üç görsel
modelinin uç yolları, alan adları, tipleri ve enum'ları fal.ai'den DOĞRUDAN
OKUNAMADI — bu turun konteynerinde `fal.ai`/`docs.fal.ai` egress'te kapalı.
Hepsi fal'ın OpenAPI şemasını kodlayan AÇIK KAYNAK istemcilerden ÇAPRAZ okundu
(GitHub kod araması, aynı gün): NousResearch/hermes-agent
`plugins/video_gen/fal/__init__.py` (uç · alan · tip tablosu),
storytold/artcraft `crates/api_clients/fal_client` (Rust struct'ları, uç
başına), 0xsline/OpenChatCut `fal-catalog-input.verify.ts` (gövde
doğrulama örnekleri), simstudioai/sim `falai-video.ts`, TanStack/ai
`packages/ai-fal` (görsel alan adı tablosu), sandbaseai/sandbase-docs (H3
enum'ları), Comfy-Org/ComfyUI `nodes_minimax.py`. KURAL: bir ad/tip ancak en
az ÜÇ kaynak aynı şeyi söylüyorsa yazıldı; tek kaynakta kalan (H3'ün 480P/4K
kademeleri) yazılmadı. Canlı 422 ile DOĞRULANMADI (POST para harcardı) —
sahibin sandbox turu (her modelde bir üretim) canlı doğrulamadır ve
`tests/test_fal_client*.py` gövdenin KENDİSİNİ ölçer, telin cevabını değil.

DOSYA ADI PyPI'daki resmî `fal-client` paketini GÖLGELİYOR. O paket
kullanılmıyor ve kullanılmamalı: BYOK tasarımı yalnız `httpx` istiyor,
`kromis.spec`'in `hiddenimports=[]` değeri yeni bir bağımlılığı analiz
edemez ve Chaquopy kaynak kümesi `include "*.py"` ile kurulu. Biri
`fal-client`ı `requirements.txt`e eklerse kök modülü ONUN önüne geçer ve
hata yalnız o paketi kullanmaya çalışan kodda görünür.

DOSYA KÖKTE ve DÜZ olmak ZORUNDA (Chaquopy; bkz. tests/test_android_packaging.py).

ALAN TABLOSU (`ALANLAR`) bu dosyanın taşıyıcı kararı ve gerekçesi ÖLÇÜLDÜ
(2026-09-14, canlı uç):

  **Beyan edilmemiş alan 422 ÜRETMİYOR — SESSİZCE YOK SAYILIYOR.** Kling'in
  görsel→video ucuna, şemasında hiç olmayan `aspect_ratio` gönderildi ve
  istek şema doğrulamasını GEÇTİ. İlk tasarımın "fal pydantic tabanlı, yani
  fazladan alan 422 demek" varsayımı YANLIŞ çıktı.

Bu, tabloyu gereksiz kılmıyor — TAM TERSİ, daha gerekli kılıyor. 422 gürültülü
bir hatadır ve kendini gösterir; sessiz yok sayım göstermez: kullanıcı 9:16
seçer, tel isteği kabul eder, video 16:9 döner ve hiçbir yerde bir hata
okunmaz. Bu deponun her yerde adlandırdığı SESSİZ SAPMA'nın tam kendisi.

Kling'in görsel→video ucu `aspect_ratio` ve `resolution` alanlarını şemasında
SAYMIYOR (oranı ilk kareden türetiyor), metin ucu ise sayıyor; katalog
`sizes`ı yine beyan ediyor çünkü metin yolunda GERÇEK. Adaptör düzenleme
yolunda onu sessizce değil, TABLOYA BAKARAK düşürüyor.

İKİNCİ ÖLÇÜM TURU (2026-09-15, Görev 8'in canlı duman testinin ardından
tam OpenAPI şeması — bkz.
`.superpowers/sdd/2026-09-14-fal-video-saglayicisi/olcum-uc-semalari.md`)
`ALANLAR`ın kendi VARSAYIMINI kırdı: referans karenin GİTTİĞİ ad üç modelde
AYNI DEĞİL. PixVerse ve Kling gerçekten `image_url` okuyor, ama Wan'ın
görsel→video ucu yalnız `start_image_url`u ZORUNLU sayıyor — `image_url`
adı o şemada hiç yok. Kod bugüne kadar üçüne de sabit `image_url` yazıyordu,
yani Wan'ın görsel yolu HER istekte `422 Field required: start_image_url`
alıyordu. Aynı tur Wan'ın görsel ucunun `aspect_ratio`yu da kabul ettiğini
(iki uçta da var, `resolution`un aksine) ve Kling'in `duration`ının şemada
STRING enum (`"3".."15"`) olduğunu, kodun ise Python `int` gönderdiğini
gösterdi. `TelBicimi` bu üç bulguyu taşıyor: `gorsel_alani` referans
karenin adını, `sure_dize` süre alanının telde dize mi tamsayı mı gittiğini
söylüyor — ikisi de modele göre değişiyor, tek bir sabit varsayılamaz.
"""
from __future__ import annotations

import base64
import dataclasses
import re
import time

import azure_client as ac
import catalog
import credstore
import i18n
import providers
from services import saglayici_meta

# Yüklenen referans karenin MIME'ı. `app._to_png` girdiyi koşulsuz PNG'ye
# çevirdiği için sağlayıcıya sorulacak bir şey yok (`veo_client.PNG_MIME`
# ile aynı olgu).
PNG_MIME = "image/png"


@dataclasses.dataclass(frozen=True)
class TelBicimi:
    """Bir modelin tel biçimi — hangi alan hangi ADLA ve hangi TİPLE gidiyor.

    NEDEN tek dataclass, `gorsel_alani`/`sure_dize` için AYRI sözlükler DEĞİL:
    ikisi de modelden modele değişiyor (2026-09-15 ölçümü, bkz. bu dosyanın
    başlığı) ve `metin`/`gorsel` kümeleriyle SENKRONDA kalmaları gerekiyor.
    Paralel sözlükler `build_payload`ın docstring'inin `if model_id == …`
    zincirinden kaçınma gerekçesiyle AYNI hastalığı taşırdı: bir modeli
    güncelleyip ötekini (ya da bir sözlüğü) unutmak kolaylaşırdı.
    """

    metin: frozenset[str]        # metin→video ucunun okuduğu adlar
    gorsel: frozenset[str]       # görsel→video ucunun okuduğu adlar
    gorsel_alani: str            # referans karenin GİTTİĞİ ad (modele göre değişir)
    sure_dize: bool = False      # süre telde DİZE mi gidiyor (Kling)
    # KALİTE EKSENİ SES EKSENİ Mİ (Faz 4 / 1b-D, Kling V3 Pro): `True` ise
    # katalogdaki `quality` jetonu (`sessiz`/`sesli`) `resolution` olarak DEĞİL
    # `generate_audio` bool'u olarak gidiyor — şemada `resolution` yok, ses
    # anahtarı fiyatı ikiye bölüyor. `False` + kümede `generate_audio` varsa
    # (Seedance 2.5) değer HEP `True`: fiyat "sesli" rakamla yazıldı, kapalı
    # göndermek kullanıcının ödediği şeyi eksik teslim etmek olurdu.
    ses_ekseni: bool = False

    def __post_init__(self) -> None:
        # DEĞİŞMEZ: `gorsel_alani` `gorsel` kümesinin ÜYESİ olmak ZORUNDA —
        # değilse `build_payload`ın adı süzen tek satırı referans kareyi
        # SESSİZCE düşürür ve bu, F1'in (Wan'ın `start_image_url`u hiç
        # gönderilmemesi) aynısının başka bir modelde SESSİZ biçimidir. Bu
        # denetim `tests/test_fal_client.py`deki üç modelli mandalın
        # ikinci, ithal-zamanlı kopyası: modül YÜKLENİRKEN patlar, testin
        # unutulduğu/atlandığı bir çalıştırmada bile.
        if self.gorsel_alani not in self.gorsel:
            raise ValueError(
                f"gorsel_alani={self.gorsel_alani!r} gorsel kümesinde yok: "
                f"{sorted(self.gorsel)}")
        # SES EKSENİ ile `resolution` BİRLİKTE OLAMAZ: jeton ya çözünürlük ya
        # ses anahtarıdır; ikisi de kümedeyse `build_payload` `sesli` dizesini
        # `resolution` olarak da gönderir — şemada enum dışı, telde 422 ya da
        # (fal'ın ölçülmüş huyu) sessiz yok sayım. İthal zamanında patlasın.
        if self.ses_ekseni and ("resolution" in self.metin or "resolution" in self.gorsel
                                or "generate_audio" not in self.metin
                                or "generate_audio" not in self.gorsel):
            # ASCII: geliştiriciye konuşan ithal-zamanı hatası, kullanıcı metni
            # değil (`test_no_user_facing_module_still_carries_turkish_text`).
            raise ValueError(
                "ses_ekseni=True olan bicim `resolution` tasiyamaz ve iki ucta da "
                "`generate_audio` okumali")


# model id → TelBicimi.
#
# KATALOGDA DEĞİL BURADA: katalog "bu model ne yapabiliyor" diyor (yetenek
# beyanı, arayüz onu okuyor), bu tablo "bu uç hangi adı ve tipi okuyor" (tel
# biçimi, yalnız bu dosya okuyor). İkisini karıştırmak, arayüzün tel
# ayrıntısına bağlanması demekti.
ALANLAR: dict[str, TelBicimi] = {
    # Wan'ın görsel ucu `image_url` DEĞİL `start_image_url` okuyor — tek
    # zorunlu alanı bu (ölçüldü 2026-09-15). Aynı uç `aspect_ratio`yu da
    # kabul ediyor (`resolution`un aksine, iki uçta da var); önceki tabloda
    # bu alan eksikti ve kullanıcının seçtiği oran sessizce şemanın
    # `adaptive` varsayılanına düşüyordu.
    "fal-wan-3-0": TelBicimi(
        metin=frozenset({"prompt", "resolution", "aspect_ratio", "duration"}),
        gorsel=frozenset({"prompt", "start_image_url", "resolution",
                          "aspect_ratio", "duration"}),
        gorsel_alani="start_image_url",
    ),
    # PixVerse: `image_url` burada GERÇEKTEN doğru ad (Wan'dan farklı;
    # ölçüldü 2026-09-15) ve `duration` şemada tamsayı — `sure_dize`
    # varsayılanı (`False`) burada değişmiyor.
    "fal-pixverse-c1": TelBicimi(
        metin=frozenset({"prompt", "resolution", "aspect_ratio", "duration"}),
        gorsel=frozenset({"prompt", "image_url", "resolution", "duration"}),
        gorsel_alani="image_url",
    ),
    # Kling: `resolution` İKİ uçta da YOK (şema o alanı saymıyor; katalogda
    # `quality_hidden=True` ile tek sentetik jeton duruyor) ve `aspect_ratio`
    # yalnız METİN ucunda var. `image_url` burada da gerçek ad (PixVerse
    # gibi). `sure_dize=True`: şema `duration`ı STRING enum olarak
    # tanımlıyor (`"3","4",…,"15"`, varsayılan `"5"`) — kodun
    # `catalog.durations`tan okuduğu Python `int`i telde OLDUĞU GİBİ
    # gönderirse şemanın beyan ettiği TİPLE uyuşmaz. Bu canlı 422 ile
    # DOĞRULANMADI (POST para harcardı); düzeltme şemanın kendi beyanına
    # dayanıyor, ölçülmüş bir hataya değil.
    "fal-kling-v3-turbo-pro": TelBicimi(
        metin=frozenset({"prompt", "aspect_ratio", "duration"}),
        gorsel=frozenset({"prompt", "image_url", "duration"}),
        gorsel_alani="image_url",
        sure_dize=True,
    ),
    # ── Faz 4 / 1b-D (2026-09-23): dört yeni model. Kaynaklar ve "üç kaynak
    # kuralı" dosya başlığında; hiçbiri canlı 422 ile doğrulanmadı.
    #
    # Seedance 2.5: `duration` şemada DİZE enum (Kling'in deseni — hermes-agent
    # bu modelde `duration_int` bayrağını TAŞIMIYOR, OpenChatCut `'12'` dize
    # gönderiyor). Görsel ucu `aspect_ratio`yu YALNIZ "auto" olarak tanıyor
    # (oranı ilk kareden türetiyor) → o uçta düşürülüyor, PixVerse/Kling ile
    # aynı sessiz-sapma gerekçesi. `generate_audio` iki uçta da var, hep True
    # (`TelBicimi.ses_ekseni`nin yorumu). i2v'nin `end_image_url`u bilerek
    # gönderilmiyor (Wan'ın kararı; `supports_last_frame=False`).
    "fal-seedance-2-5": TelBicimi(
        metin=frozenset({"prompt", "resolution", "aspect_ratio", "duration",
                         "generate_audio"}),
        gorsel=frozenset({"prompt", "image_url", "resolution", "duration",
                          "generate_audio"}),
        gorsel_alani="image_url",
        sure_dize=True,
    ),
    # FLUX 3: `duration` TAMSAYI (şema `"auto" | 5..20`; hermes `duration_int`),
    # `aspect_ratio` ve `resolution` İKİ uçta da okunuyor (artcraft'ın i2v
    # struct'ı ikisini de taşıyor, atlascloud i2v'ye `aspect_ratio` gönderiyor).
    # Ses yerleşik ve fiyata dahil; bir ses anahtarı BEYAN EDİLMİYOR.
    "fal-flux-3": TelBicimi(
        metin=frozenset({"prompt", "resolution", "aspect_ratio", "duration"}),
        gorsel=frozenset({"prompt", "image_url", "resolution", "aspect_ratio",
                          "duration"}),
        gorsel_alani="image_url",
    ),
    # Kling V3 Pro: Turbo Pro ile AYNI şema ailesi — `resolution` YOK, dize
    # `duration`, i2v'de `aspect_ratio` yok — ama referans kare `image_url`
    # DEĞİL `start_image_url` (hermes `image_param_key`, OpenChatCut ve
    # aso-tracker'ın canlı çağrıları, TanStack belgesi). Turbo Pro'nun v0.23
    # ölçümünde `image_url` görülmüştü; iki uç ailesi farklı ad okuyor, biri
    # ötekine kopyalanmadı. `generate_audio` KALİTE EKSENİ (ses_ekseni).
    "fal-kling-v3-pro": TelBicimi(
        metin=frozenset({"prompt", "aspect_ratio", "duration", "generate_audio"}),
        gorsel=frozenset({"prompt", "start_image_url", "duration", "generate_audio"}),
        gorsel_alani="start_image_url",
        sure_dize=True,
        ses_ekseni=True,
    ),
    # MiniMax H3: `duration` TAMSAYI (sandbase şeması `integer`, hermes
    # `duration_int`), `resolution` enum'u BÜYÜK P (`768P`, `2K`) — katalog
    # jetonu bu yazımla tutuyor, tel dönüşümü yok. i2v `aspect_ratio` okumuyor
    # (oranı kareden alıyor; hermes `image_drop_keys`, MaxVideoAi tablosu).
    # Ses yerleşik, anahtarı yok.
    "fal-minimax-h3": TelBicimi(
        metin=frozenset({"prompt", "resolution", "aspect_ratio", "duration"}),
        gorsel=frozenset({"prompt", "image_url", "resolution", "duration"}),
        gorsel_alani="image_url",
    ),
}

# Kling V3 Pro'nun ses jetonları — katalogla AYNI dizeler (`catalog.QUALITY_LABELS`).
# Buraya kopyalanması `AUTH_HEADER`ın iki kez beyan edilme gerekçesi: katalog
# yaprak ve bu modül onu zaten ithal ediyor, ama jeton bir TEL sözleşmesi ve
# tel sözleşmeleri adaptörde literal durur (bekçisi tests/test_fal_client.py).
SESLI = "sesli"
SESSIZ = "sessiz"


def wire_path_for(m: catalog.ImageModel, *, images) -> str:
    """İstek hangi uca gidecek: metin→video mu, görsel→video mu.

    `wire_model_edit` BOŞSA `wire_model`e düşülüyor. Bu düşüş fal'da hiç
    yaşanmamalı (katalog mandalı boş bırakmayı yasaklıyor), ama sözleşme
    deponun geri kalanıyla tutarlı kalsın diye burada: uçları ayrışmamış bir
    sağlayıcı aynı yolu iki kez beyan etmek zorunda değil.
    """
    if images:
        return m.wire_model_edit or m.wire_model
    return m.wire_model


# Kuyruk adresinin taşıdığı segment sayısı — ÖLÇÜLMÜŞ bir sabit.
_UYGULAMA_SEGMENTI = 2


def queue_app_path(wire_path: str) -> str:
    """Kuyruk adreslerinin (`/requests/…`) kullandığı UYGULAMA yolu.

    GÖNDERİM yolu ile YOKLAMA yolu AYNI DEĞİL ve bu 2026-09-14'te canlı uçtan
    ölçüldü:

        gönderim : queue.fal.run/fal-ai/kling-video/v3/turbo/pro/text-to-video
        yoklama  : queue.fal.run/fal-ai/kling-video/requests/<id>/status

    Yani kuyruk adresi tam uç yolunu DEĞİL, yalnız ilk iki segmenti
    (sahip/uygulama) taşıyor; `v3/turbo/pro/text-to-video` düşüyor.

    NEDEN BU KADAR ÖNEMLİ: tam yolla kurulan adres 404 DÖNDÜRMÜYOR, BOŞ GÖVDE
    döndürüyor — yani döngü hatayla değil SESSİZCE ölüyor ve üretim duvar
    saatine kadar bekliyor. Ölçümde PixVerse ve Kling'in izlemesi tam bu
    yüzden 600 saniye boşa gitti; aynı `request_id`ler doğru adresle
    sorgulandığında ZATEN tamamlanmıştı. İptal `PUT`'u da aynı sebeple 405
    dönüyordu.

    Bu, adresin GÖVDEDEN alınmama kararını (bkz. `_durum_url`) değiştirmiyor
    — yalnız tabandan TÜRETME kuralını düzeltiyor.
    """
    parcalar = [p for p in wire_path.strip("/").split("/") if p]
    return "/".join(parcalar[:_UYGULAMA_SEGMENTI])


def _data_uri(png: bytes) -> str:
    """Referans kareyi base64 data URI'ye çevirir.

    YÜKLEME ADIMI YOK ve bu bilinçli: fal'ın dosya deposu ikinci bir kimlik
    yüzeyi, ikinci bir hata dalı ve ömrü sınırlı bir CDN adresi demekti.
    fal data URI'yi açıkça destekliyor; `gemini_client`in `inlineData`
    duruşunun aynısı.
    """
    return f"data:{PNG_MIME};base64," + base64.b64encode(png).decode("ascii")


def build_payload(m: catalog.ImageModel, prompt: str, size: str, quality: str,
                  duration: int, images) -> dict:
    """İstek gövdesi — YALNIZ `ALANLAR`ın izin verdiği anahtarlar, adları ve
    tipleriyle.

    Süzgeç `ALANLAR`dan geçiyor, `if model_id == …` zincirinden DEĞİL: zincir
    her yeni modelde büyür ve bir dalı unutmak, beyan edilmemiş alan göndermek
    (422) ya da gerekli alanı düşürmek demekti. Aynı gerekçeyle referans
    karenin ADI (`bicim.gorsel_alani`) ve sürenin TİPİ (`bicim.sure_dize`)
    de TABLODAN okunuyor, burada SABİT yazılmıyor — sabit bir `"image_url"`
    ve sabit bir `int` tam olarak F1/F3'ün kökündeki satırlardı (Wan'ın
    `start_image_url` beklemesi, Kling'in `duration`ı dize istemesi).

    `images` sıralı [(dosya_adı, png_baytları), ...]; YALNIZ İLKİ kullanılıyor
    (`max_refs=1`). Fazlası `app.animate`in kapısında zaten eleniyor, ama
    burada da kesiliyor — `providers.edit`in ikinci kapı disiplini.
    """
    bicim = ALANLAR[m.id]
    izin = bicim.gorsel if images else bicim.metin
    tum = {
        "prompt": prompt,
        "aspect_ratio": size,
        "resolution": quality,
        "duration": str(duration) if bicim.sure_dize else duration,
        # Ses: eksen ise jetondan, değilse HEP açık (gerekçe `TelBicimi.ses_ekseni`).
        # Kümede yoksa aşağıdaki süzgeç düşürür — FLUX 3 ve H3 hiç görmez.
        "generate_audio": (quality == SESLI) if bicim.ses_ekseni else True,
    }
    if images:
        tum[bicim.gorsel_alani] = _data_uri(images[0][1])
    return {ad: deger for ad, deger in tum.items() if ad in izin}


def detail_of(body: dict | list | None) -> str:
    """`providers.detail_of`un fal sarmalı — ÜST DÜZEY `detail` de okunuyor.

    `providers.detail_of` iki şekil tanıyor: `{"error": {"message": …}}` ve
    onun `details[]` listesi. fal FastAPI/pydantic tabanlı olduğu için
    doğrulama hatasını ÜST DÜZEYDE taşıyor —

        {"detail": [{"loc": ["body", "duration"], "msg": "…"}]}

    — yani paylaşılan fonksiyon boş dize döndürür ve BÜTÜN 422'ler çıplak bir
    "HTTP 422"ya çöker. Tam olarak FLUX'un `error.details[]` dalının var olma
    sebebi, dördüncü bir şekilde.

    `providers.detail_of` DEĞİŞTİRİLMİYOR: Azure, OpenAI, Gemini ve FLUX'un
    yolları bayt bayt aynı kalmalı ve o fonksiyonun docstring'i hangi şekli
    neden tanıdığını tek tek sayıyor. Sarmal, o listeyi `error.details`
    konumuna TAŞIYIP aynı ayrıştırıcıya veriyor — ikinci bir `{loc, msg}`
    çözümleyicisi yazmamak için.
    """
    paylasilan = providers.detail_of(body)
    if paylasilan:
        return paylasilan
    if isinstance(body, list) and len(body) == 1:
        body = body[0]
    if not isinstance(body, dict):
        return ""
    ust = body.get("detail")
    if isinstance(ust, str):
        return ust
    if isinstance(ust, list):
        return providers.detail_of({"error": {"details": ust}})
    return ""


def map_error(status_code: int, body: dict | list | None) -> str:
    """HTTP durumunu Türkçe mesaja çevirir. ŞEKİL paylaşılıyor, METİN değil.

    `veo_client.map_error`in duruşunun aynısı: "Veo" diyen bir metin fal
    faturasını arayan kullanıcıyı yanlış konsola yönlendirir.

    402 DALI BU DOSYANIN EN ÖNEMLİ YERİ ve `veo_client`in 403/429 dalının
    ikizi: **fal ön ödemeli.** Bakiyesi biten kullanıcıya "anahtarını kontrol
    et" demek, anahtarı GERÇEKTEN doğru olan birini çalışan kurulumunu
    bozmaya davet etmek olurdu.

    429 DA AYRI bir cümle: fal'da yeni hesaplar İKİ eşzamanlı istekle
    başlıyor, yani 429 çoğu zaman bir kota değil bir SIRA sorunu ve cevabı
    "bekle ve tekrar dene".
    """
    detail = detail_of(body)
    ek = f" {detail}" if detail else ""
    if status_code in (401, 403):
        return i18n.t("err.fal_denied", None, durum=status_code) + ek
    if status_code == 402:
        return i18n.t("err.fal_402") + ek
    if status_code == 404:
        return i18n.t("err.fal_404") + ek
    if status_code == 429:
        return i18n.t("err.fal_429") + ek
    if providers.is_content_policy(detail):
        return i18n.t("err.fal_content_policy", None, durum=status_code) + ek
    if status_code == 400 and providers.is_invalid_key(detail):
        return i18n.t("err.fal_bad_key") + ek
    if status_code == 422:
        return i18n.t("err.fal_422", None,
                      ayrinti=detail or i18n.t("err.fal_422_generic"))
    return i18n.t("err.fal_failed", None, durum=status_code) + ek


AUTH_HEADER = "Authorization"
# `Key ` ÖNEKİ ZORUNLU: fal'ın kabul ettiği tek biçim bu. `Bearer` ile
# gönderilen aynı anahtar 401 dönüyor (Replicate'in biçimi o).
AUTH_PREFIX = "Key "

# ÜÇ AYRI ZAMAN AŞIMI — `veo_client`in taşıyıcı kararının aynısı ve aynı
# sebeple: submit/yoklama metadata çağrısı (kısa), indirme megabaytlarca MP4
# (uzun), döngünün tamamı `providers.total_budget` (duvar saati).
#
# SABİTLER KOPYALANDI, `veo_client`ten İMPORT EDİLMEDİ:
# `azure_mai_client`/`azure_flux_client`in `AUTH_HEADER`ı iki kez beyan etme
# gerekçesinin aynısı — biri değişmek zorunda kaldığında öteki dokunulmadan
# kalabiliyor.
POLL_READ_TIMEOUT = 30.0
DOWNLOAD_READ_TIMEOUT = ac.read_timeout_for(1)
POLL_INTERVAL_START = 1.0
POLL_INTERVAL_MAX = 10.0
POLL_BACKOFF = 1.6

MAX_YONLENDIRME = 5
_YONLENDIRME_KODLARI = (301, 302, 303, 307, 308)

DURUM_TAMAM = "COMPLETED"

# `request_id`in KABUL EDİLEN karakterleri. Kuyruk adresleri gövdeden
# alınmıyor, TABANDAN kuruluyor (bkz. `_durum_url`) — ve o kurulumda id tek
# değişken parça. Süzgeç olmasaydı `../../..` taşıyan bir id yolu başka bir
# uca çevirebilirdi.
_REQUEST_ID = re.compile(r"\A[A-Za-z0-9_-]{1,128}\Z")


def _simdi() -> float:
    """Tek yönlü saat — TEST DİKİŞİ (`veo_client._simdi`nin aynı gerekçesi)."""
    return time.monotonic()


def _bekle(saniye: float) -> None:
    """Yoklama arası uyku — `_simdi` ile aynı gerekçe."""
    time.sleep(saniye)


def _durum_url(taban: str, yol: str, rid: str) -> str:
    """Yoklama adresi — GÜVENİLEN TABANDAN kuruluyor, yanıttan DEĞİL.

    fal'ın belgesi "dönen `status_url`'ü kullan, elle kurma" diyor ve biz
    BİLEREK tersini yapıyoruz. Gerekçe `veo_client._indir`in ölçülmüş
    kararı: gövdeden gelen bir adreste "hedef konağı gövdeyi yazan taraf
    seçiyor". Gövdeden alınan tek şey `request_id` ve o da `_REQUEST_ID`
    süzgecinden geçiyor.

    TAKAS AÇIK: fal kuyruğu bir gün bölgeselleştirirse (BFL'in
    `api.eu`/`api.us` uçlarında olduğu gibi) değişecek tek yer bu iki
    fonksiyon. Belirti net olur: 404.
    """
    return f"{taban}/{queue_app_path(yol)}/requests/{rid}/status"


def _sonuc_url(taban: str, yol: str, rid: str) -> str:
    """`_durum_url`in ikizi; aynı gerekçe."""
    return f"{taban}/{queue_app_path(yol)}/requests/{rid}"


def _istek(client, method: str, url: str, key: str | None, *, read: float,
           json=None):
    """Ortak HTTP + taşıma hatası çevirisi. Yanıtı ÇÖZÜMLEMİYOR.

    `key=None` KİMLİKSİZ istek demek ve tek kullanıcısı `_indir` —
    gerekçesi orada. `veo_client._istek`ten farkı tam olarak bu: orada
    indirme Google konağında anahtarı GÖNDERİYORDU, burada hiç göndermiyor.

    YÖNLENDİRME İZLENMİYOR (`follow_redirects` yok): `_indir` onu ELLE
    izliyor, çünkü httpx yönlendirmede özel başlıkları soymuyor.

    ÜÇ İSTİSNA SARMALANIYOR, YALNIZ `TransportError` DEĞİL: `url` iki
    yerde GÖVDEDEN geliyor (indirme adresi, `Location` başlığı) ve ikisi de
    `httpx.InvalidURL` fırlatabilir — bu sınıf `TransportError`
    HİYERARŞİSİNDE DEĞİL, düz bir `Exception` alt sınıfı, çünkü URL ayrıştırma
    isteğin kendisinden ÖNCE patlıyor. `httpx.DecodingError` de aynı şekilde
    dışarıda kalıyor (bozuk gzip/deflate gövdesi, yine gövdeyi yazan tarafın
    elinde). Sarmalanmazlarsa üçü de `ac.ImageError`in docstring'indeki aynı
    kadere düşer: `app.py`'nin süzgecinden GEÇİP ham 500 olurlar.
    """
    import httpx
    basliklar = {}
    if key:
        basliklar[AUTH_HEADER] = AUTH_PREFIX + key
    if json is not None:
        basliklar["Content-Type"] = "application/json"
    try:
        return client.request(method, url, headers=basliklar, json=json,
                              timeout=ac.request_timeout(read))
    except (httpx.TransportError, httpx.InvalidURL, httpx.DecodingError) as exc:
        # Mesaj `azure_client`tan geliyor, sağlayıcı adı düzeltiliyor:
        # "Azure'a bağlanılamadı" diyen bir metin kullanıcıyı Endpoint alanını
        # kurcalamaya iter (`veo_client._istek`in aynı satırı). `InvalidURL`/
        # `DecodingError` `TimeoutException`/`TransportError` DEĞİL, yani
        # `transport_error_message` bunları genel dala düşürüyor — o da
        # Türkçe ve `ac.ImageError`, ham 500'den her hâlükârda iyi.
        raise ac.ImageError(
            ac.transport_error_message(exc, read).replace("Azure", "fal.ai")) from exc


def _govde(resp):
    try:
        return resp.json()
    except Exception:
        return None


def _basarili(resp) -> bool:
    """Yanıt HTTP durumu BAŞARI mı — herhangi bir 2xx.

    ÖLÇÜLMÜŞ OLGU: Görev 8'in canlı duman testi (2026-09-15) `POST
    …/text-to-video`e `202 Accepted` aldı; Görev 1'in sondası aynı uçta bir
    gün önce (2026-09-14) `200` görmüştü. fal ya YÜKE/kuyruk durumuna göre
    ikisi arasında geçiyor ya da davranış değişti — hangisi olursa olsun kod
    İKİSİNİ de kabul etmek ZORUNDA. Yalnız `== 200` denetimi 202'yi hataya
    çevirip kullanıcıya 0,7 saniyede "HTTP 202" gösteriyordu; oysa 202 bir
    KUYRUK API'sinde "kabul edildi" demek, hata değil.

    TEK YÜKLEMDE toplanması BİLİNÇLİ: submit/yoklama/sonuç üç yerde de aynı
    kural geçmeli, aksi hâlde biri gevşer biri katı kalır ve fal hangi
    adımda hangi 2xx'i seçtiğine göre döngü yine sessizce kırılır.
    """
    return 200 <= resp.status_code < 300


def _video_url(sonuc: dict) -> str:
    """Sonuç gövdesinden MP4 adresi.

    BEKLENMEYEN ŞEKİL ham `KeyError` DEĞİL Türkçe `ImageError` üretiyor:
    `azure_flux_client.decode_images`in kararı — sarmalanmayan bir `KeyError`
    `app.py`'nin süzgecinden geçer ve kullanıcı dakikalarca bekledikten sonra
    yalnızca "Hata (500)" görür. Anahtarlar mesaja giriyor ki şekil
    değiştiğinde teşhis kullanıcının ekranında olsun.
    """
    video = sonuc.get("video") if isinstance(sonuc, dict) else None
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise ac.ImageError(
            i18n.t("err.fal_no_video_url", None,
                   anahtarlar=sorted(sonuc) if isinstance(sonuc, dict)
                   else "—"))
    return str(url)


def _gorsel_url(sonuc: dict) -> str:
    """`_video_url`un görsel ikizi: fal görsel uçları `images[]` listesi döndürüyor.

    YALNIZ İLK öğe okunuyor ve bu bir kesme değil sözleşme: `build_image_payload`
    `num_images=1` gönderiyor (`images_per_request=1`, adet döngüsü `_kuyruk_
    dongusu`nda), yani listede birden fazla öğe beklenmiyor. Şekil değişirse
    (boş liste, `url`süz öğe) Türkçe `ImageError`, ham `KeyError`/`IndexError`
    değil — `_video_url`un aynı gerekçesi.
    """
    liste = sonuc.get("images") if isinstance(sonuc, dict) else None
    ilk = liste[0] if isinstance(liste, list) and liste else None
    url = ilk.get("url") if isinstance(ilk, dict) else None
    if not url:
        raise ac.ImageError(
            i18n.t("err.fal_no_image_url", None,
                   anahtarlar=sorted(sonuc) if isinstance(sonuc, dict)
                   else "—"))
    return str(url)


# İndirme hedefinin uyması gereken şema. fal'ın CDN'i HER ZAMAN https
# veriyor; düz `http` kabul etmek görünürde zararsız ama sessizce bir
# ortadaki-adam saldırısına açık kapı bırakırdı — reddetmenin bedeli yok.
_IZIN_VERILEN_SEMA = "https"


def _guvenli_hedef_mi(url: str) -> bool:
    """İndirme adresi bir SSRF açığına yol açıyor mu — açıyorsa REDDET.

    ANAHTARSIZLIK (bkz. `_indir`'in docstring'i) ile bu kapı AYRI tehditleri
    kapatıyor: biri "bu adrese giden istek kimlik TAŞIMASIN" diyor, bu ise
    "bu adrese HİÇ istek gitmesin". İkisi de gerekli çünkü `url` YANIT
    GÖVDESİNDEN (ya da `Location` başlığından) geliyor — kimliksiz bir GET
    bile hedefi seçen tarafın işine yarar: bu MASAÜSTÜ bir uygulama, yani
    loopback yüzeyi (`http://127.0.0.1:…`) gerçek, bulut meta-veri servisi
    (`169.254.169.254`) de öyle. Gövde bu adreslerden birini yazarsa ve kapı
    yoksa dönen baytlar kullanıcıya "video" diye teslim edilir.

    `veo_client._google_konagi` bir ALLOWLIST taşıyordu çünkü Google'ın
    indirme konağı SABİTTİ (`*.googleapis.com` vb.). Burada DENY-LIST:
    fal'ın CDN konağı sabit değil (`v3.fal.media` gibi adlar sürüm/bölgeyle
    değişebiliyor), bir allowlist yanlış konakları da reddedip döngüyü
    sessizce kırardı. Yalnız özel/yerel aralıklar eleniyor, geri kalan her
    şeye izin veriliyor.

    AD ÇÖZÜMLEMESİ YAPILMIYOR (DNS'e HİÇ çıkılmıyor): bir sorgu hem yan
    etkili hem de TOCTOU açığı taşır (çözümleme ile asıl istek arasında ad
    başka bir IP'ye işaret edebilir). Yalnız adresin METNİ denetleniyor: host
    bir literal IP ise `ipaddress` onu private/loopback/link-local diye
    işaretliyor; `ipaddress` REDDEDERSE de otomatik "sıradan alan adı, izin
    ver" DENMİYOR — `ipaddress.ip_address()` yalnız NOKTALI-ONDALIK biçimi
    tanıyor, alternatif IPv4 yazımlarını (bkz. `_alan_adi_mi`) da `ValueError`
    ile reddediyor, yani o dal IP OLMAYANLA IP'nin TANINMAYAN YAZIMINI
    ayıramıyor. İkinci bir denetim (`_alan_adi_mi`) bu ikisini ayırıyor.
    """
    import ipaddress
    from urllib.parse import urlparse

    parcalar = urlparse(url)
    if parcalar.scheme != _IZIN_VERILEN_SEMA:
        return False
    konak = (parcalar.hostname or "").lower()
    if not konak or konak == "localhost" or konak.endswith(".localhost"):
        return False
    try:
        ip = ipaddress.ip_address(konak)
    except ValueError:
        return _alan_adi_mi(konak)
    return not (ip.is_loopback or ip.is_link_local or ip.is_private
                or ip.is_unspecified or ip.is_reserved or ip.is_multicast)


def _alan_adi_mi(konak: str) -> bool:
    """`ipaddress.ip_address()`in reddettiği bir host GERÇEKTEN bir alan adı
    mı — yoksa `ipaddress`in TANIMADIĞI alternatif bir IPv4 YAZIMI mı.

    ÖLÇÜLMÜŞ AÇIK (2026-09-15, ikinci inceleme turu): `ipaddress.ip_address()`
    yalnız noktalı-ondalık (`a.b.c.d`) biçimi tanıyor;

        https://2130706433/x       (decimal: 127.0.0.1'in tek sayısı)
        https://0x7f.1/x           (hex/ondalık karışık)
        https://127.1/x            (kısaltılmış — eksik oktet)
        https://017700000001/x     (oktal)

    dördü de birer IP LİTERALİ ama `ipaddress` hepsini `ValueError` ile
    reddediyor. İlk yazım bu reddi "sıradan bir alan adı" sanıp KAPIDAN
    GEÇİRİYORDU. Bu bir teorik açık değil: bu depo macOS ve Android'e de
    paketleniyor (`build.sh`, `kromis.spec`, Chaquopy) ve glibc'in
    `getaddrinfo`si bu dört biçimi de `127.0.0.1`'e ÇÖZÜYOR — Windows'ta
    `socket.getaddrinfo`nun aynısını çözememesi savunma DEĞİL, platforma
    bağlı bir baypas hâlâ baypas.

    KURAL: son etiket (TLD) bir HARFLE başlamalı. Sayısal biçimlerin
    DÖRDÜ de bunu ihlal ediyor — `2130706433` ve `017700000001` TEK etiket ve
    tamamı rakam; `0x7f.1` ve `127.1`'in son etiketi `1`. `v3.fal.media`,
    `fal.media`, `xn--...` (IDNA) gibi gerçek alan adları TLD'si harfle
    başladığı için geçiyor.

    KÖK NOKTA (`v3.fal.media.`) doğrulamadan ÖNCE soyuluyor: DNS'te geçerli
    bir biçim, onu reddetmek meşru bir adresi kırardı.
    """
    konak = konak.rstrip(".")
    if not konak:
        return False
    son_etiket = konak.rsplit(".", 1)[-1]
    return son_etiket[:1].isalpha()


def _indir(client, url: str) -> bytes:
    """MP4'ü indirir — ANAHTARSIZ, HEDEFİ DENETLENMİŞ ve yönlendirmeyi ELLE
    izleyerek.

    ANAHTARSIZ olması bu dosyanın ikinci güvenlik kararı: `url` YANIT
    GÖVDESİNDEN geliyor, yani hedef konağı gövdeyi yazan taraf seçiyor.
    fal'ın çıktı adresi genel erişime açık bir CDN, yani kimlik zaten
    gereksiz — göndermemek, sızma yolunu tamamen kapatıyor.
    (`veo_client._indir` Google konağında anahtarı gönderiyordu ve bu yüzden
    bir konak allowlist'i taşımak zorundaydı; burada ona gerek yok.)

    HEDEF de AYRICA denetleniyor (`_guvenli_hedef_mi`) ve bu BAŞKA bir karar:
    anahtarsızlık SIZINTIYI kapatıyor, hedef denetimi SSRF'i — `url` gövdeden
    gelmeseydi ikisi de gereksizdi, ama geldiği için ikisi de gerekli; biri
    ötekinin yerine geçmiyor. Denetim hem İLK adreste hem her `urljoin`
    SONRASINDA çalışıyor: yönlendirme zinciri de ilk adres kadar güvenilmez,
    aksi hâlde kapı yalnızca girişte durur, ikinci atlayışta atlanırdı.
    """
    from urllib.parse import urljoin

    def _kapiya_sor(adres: str) -> str:
        if not _guvenli_hedef_mi(adres):
            raise ac.ImageError(
                i18n.t("err.fal_ssrf", None, adres=adres))
        return adres

    url = _kapiya_sor(url)
    # +1: İLK istek bir yönlendirme DEĞİL, döngü `MAX_YONLENDIRME` kadar
    # yönlendirmeyi İZLESİN diye bir fazla dönüyor (`veo_client._indir`in
    # aynı deseni) — aksi hâlde tavan mesajı "5" derken gerçekte yalnızca 4
    # yönlendirme izlenmiş olurdu.
    for _ in range(MAX_YONLENDIRME + 1):
        resp = _istek(client, "GET", url, None, read=DOWNLOAD_READ_TIMEOUT)
        if resp.status_code == 200:
            return resp.content
        if resp.status_code not in _YONLENDIRME_KODLARI:
            raise ac.ImageError(
                i18n.t("err.fal_download_failed", None,
                       durum=resp.status_code))
        hedef = resp.headers.get("location")
        if not hedef:
            raise ac.ImageError(
                i18n.t("err.fal_redirect_no_location", None,
                       durum=resp.status_code))
        # GÖRECELİ adres de geçerli (RFC 7231); `urljoin` mutlaklaştırıyor.
        url = _kapiya_sor(urljoin(url, hedef))
    raise ac.ImageError(
        i18n.t("err.fal_too_many_redirects", None, adet=MAX_YONLENDIRME))


def _timeout_message(gecen: float, butce: float) -> str:
    """`veo_client._timeout_message`in ikizi ve aynı ÜCRET UYARISIYLA: iş fal
    tarafında tamamlanmış olabilir ve kullanıcı 'hata aldım, demek ki
    ücretlenmedim' diye düşünmemeli."""
    return i18n.t("err.fal_timeout", None, gecen=f"{gecen:.0f}",
                  butce=f"{butce:.0f}")


def _uret(m: catalog.ImageModel, prompt: str, size: str, quality: str,
          duration: int, n: int, images, *, client, credentials) -> list[bytes]:
    """`generate_video` ve `animate`in PAYLAŞILAN gövdesi — tek fark `images`.

    DÖRT ADIM: submit → `COMPLETED` olana kadar yokla → sonucu al → indir.
    `veo_client._uret`in üç adımından farkı, fal'ın sonucu DURUM yanıtında
    değil AYRI bir adreste vermesi.

    KİMLİK TEMBEL çözülüyor (`providers._azure_generate`in belgelenmiş
    kuralı). SON TARİH duvar saatiyle ölçülüyor, yoklama SAYISIYLA değil.

    SON TARİH BİR KEZ, BURADA hesaplanıyor (`son_tarih`) ve HER tura AYNI
    mutlak an olarak geçiyor — tur başına SIFIRLANMIYOR. `providers.
    total_budget` zaten `n` ile ölçekliyor ve docstring'i "DÖNGÜNÜN duvar
    saati tavanı" diyor, yani turların TOPLAMI: saat her turda sıfırlansaydı
    gerçek tavan `n · butce` olurdu (bugün `max_n=1` olduğu için görünmez,
    ama `total_budget`ın n-ile-çarpma kararını anlamsızlaştırırdı).

    DÖNGÜ adet başına ayrı istek atıyor (`images_per_request=1`). Bugün
    `max_n=1` olduğu için tek tur, ama yapısı tavan yükseldiği gün hazır.
    """
    payload = build_payload(m, prompt, size, quality, duration, images)
    return _kuyruk_dongusu(m, wire_path_for(m, images=images), payload, n,
                           client=client, credentials=credentials,
                           cikti_url=_video_url, hata_anahtari="err.fal_no_video")


def _kuyruk_dongusu(m: catalog.ImageModel, yol: str, payload: dict, n: int, *,
                    client, credentials, cikti_url, hata_anahtari: str) -> list[bytes]:
    """Video ve görselin PAYLAŞTIĞI adet döngüsü: kimlik, bütçe, `n` tur.

    2026-09-23'e kadar bu gövde `_uret`in içindeydi ve yalnız videoya
    hizmet ediyordu; görsel geldiğinde kopyalanmadı, PARAMETRELENDİ. Video ile
    görselin farkı iki şey: gövdeyi kim kuruyor (çağıran veriyor) ve sonuçta
    hangi anahtar okunuyor (`cikti_url`: `_video_url` / `_gorsel_url`, hata
    metni `hata_anahtari`). Kuyruk mekaniği, son tarih, hata çevirisi ve
    indirme kapıları (anahtarsızlık, SSRF) İKİ yol için de aynı satırlarda —
    biri sıkılaşırsa öteki de sıkılaşır, biri gevşerse test ikisini de görür.

    KİMLİK TEMBEL çözülüyor, SON TARİH BİR KEZ hesaplanıyor (gerekçeler
    `_uret`in docstring'inde).
    """
    key, base_url = (credentials if credentials is not None
                     else credstore.resolve(m.credential))
    taban = base_url.rstrip("/")
    yol = yol.strip("/")
    butce = providers.total_budget(m, n)
    son_tarih = _simdi() + butce

    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        out: list[bytes] = []
        while len(out) < n:
            out.append(_tek_uretim(client, key, taban, yol, payload, butce,
                                   son_tarih, cikti_url=cikti_url,
                                   hata_anahtari=hata_anahtari))
        return out[:n]
    finally:
        if owns:
            client.close()


def _tek_uretim(client, key: str, taban: str, yol: str, payload: dict,
                butce: float, son_tarih: float, *, cikti_url=_video_url,
                hata_anahtari: str = "err.fal_no_video") -> bytes:
    """Tek bir kuyruk turu: submit → yokla → sonuç → indir.

    `son_tarih` ÇAĞIRANDAN (`_kuyruk_dongusu`) geliyor ve TÜM turlarda SABİT —
    bu fonksiyon kendi saatini sıfırlamıyor (bkz. `_uret`'in gerekçesi).
    `butce` yalnız zaman aşımı MESAJINDA "kaç saniyede bitmedi" diye göstermek
    için taşınıyor, son tarih hesabına bir daha girmiyor. `cikti_url` sonuç
    gövdesinden indirilecek adresi çözüyor (video: `video.url`, görsel:
    `images[0].url`); öntanımları video, çünkü bu imzanın ilk ve en çok
    çağıranı o ve testleri o imzayla yazıldı.
    """
    # ── 1. Submit ────────────────────────────────────────────────────────
    # BAŞARI `_basarili` İLE (yalnız `== 200` DEĞİL): fal `202 Accepted` da
    # döndürebiliyor (bkz. `_basarili`'in docstring'i) ve bu satır `rid`yi
    # OKUYAN tek yer — katı `!= 200` kontrolü altında 202'lik bir gövde hiç
    # `_govde(resp)`e uğramadan hataya çevriliyordu. PARA BOYUTU: iş fal
    # tarafında gerçekten kuyruğa girip FATURALANMIŞ olsa bile `request_id`
    # okunmazsa elimizde onu yoklayacak/iptal edecek hiçbir şey kalmıyordu —
    # izlenemeyen, ödenmiş bir iş.
    resp = _istek(client, "POST", f"{taban}/{yol}", key,
                  read=POLL_READ_TIMEOUT, json=payload)
    if not _basarili(resp):
        raise ac.ImageError(map_error(resp.status_code, _govde(resp)))
    kuyruk = _govde(resp) or {}
    rid = str(kuyruk.get("request_id") or "")
    if not _REQUEST_ID.match(rid):
        raise ac.ImageError(
            i18n.t("err.fal_no_request_id", None, anahtarlar=sorted(kuyruk)))
    # Yan kanal (Faz 3 / 5, K8): doğrulanmış `request_id` işin satırına — fal tarafında
    # faturalanan işi fatura CSV'siyle eşlemenin tek anahtarı. Bağlam yoksa no-op.
    saglayici_meta.kaydet(request_id=rid)

    # ── 2. Yoklama ───────────────────────────────────────────────────────
    # Döngü UYKUYLA DEĞİL KONTROLLE başlıyor: kısa bir iş ilk yanıtta
    # `COMPLETED` olabilir ve uykuyla başlamak hazır sonucu bekletmek olurdu
    # (`veo_client`in aynı notu).
    durum_url = _durum_url(taban, yol, rid)
    aralik = POLL_INTERVAL_START
    durum = ""
    while durum != DURUM_TAMAM:
        kalan = son_tarih - _simdi()
        if kalan <= 0:
            raise ac.ImageError(_timeout_message(butce - kalan, butce))
        resp = _istek(client, "GET", durum_url, key, read=POLL_READ_TIMEOUT)
        if not _basarili(resp):
            raise ac.ImageError(map_error(resp.status_code, _govde(resp)))
        govde = _govde(resp) or {}
        durum = str(govde.get("status") or "")
        # TANINMAYAN ya da eksik `status` HATA sayılmıyor, "devam ediyor"
        # sayılıyor: fal ileride `IN_QUEUE`/`IN_PROGRESS`/`COMPLETED` dışında
        # bir ara durum eklerse döngü onu es geçip yoklamaya devam ediyor —
        # tek ÇIKIŞ koşulu `COMPLETED`, tek HATA koşulu HTTP durumu ya da son
        # tarih. Tek risk: iş gerçekten düşüp fal onu `COMPLETED` DIŞINDA bir
        # durum adıyla (`FAILED` gibi) işaretlerse — belgede böyle bir durum
        # görülmedi, o hâlde bu dal son tarih dolana kadar boşa yoklar.
        if durum == DURUM_TAMAM:
            break
        _bekle(min(aralik, max(0.0, kalan)))
        aralik = min(aralik * POLL_BACKOFF, POLL_INTERVAL_MAX)

    # SON TARİH yalnız SUBMIT + YOKLAMA'yı kapsıyor: `COMPLETED` görüldükten
    # sonraki SONUÇ ve İNDİRME adımları bütçeye bir daha sokulmuyor, kendi
    # OKUMA zaman aşımlarıyla sınırlı kalıyor (`POLL_READ_TIMEOUT`,
    # `DOWNLOAD_READ_TIMEOUT` × yönlendirme tavanı). Bilinçli sadeleştirme:
    # iş zaten `COMPLETED`, yani "vazgeçme" kararı anlamsızlaşıyor — kalan
    # yolun tek riski yavaş bir indirme ve o da kendi tavanıyla sınırlı (en
    # kötü hâl ~1110 sn: 30 sn sonuç + `MAX_YONLENDIRME + 1` = 6 indirme
    # denemesinin her biri en çok `DOWNLOAD_READ_TIMEOUT` = 180 sn).
    #
    # ── 3. Sonuç ─────────────────────────────────────────────────────────
    resp = _istek(client, "GET", _sonuc_url(taban, yol, rid), key,
                  read=POLL_READ_TIMEOUT)
    if not _basarili(resp):
        raise ac.ImageError(map_error(resp.status_code, _govde(resp)))
    sonuc = _govde(resp) or {}
    # `COMPLETED` BAŞARI DEMEK DEĞİL: fal işin BİTTİĞİNİ söylüyor, iyi
    # bittiğini değil — düşen iş de `COMPLETED` olup gövdesinde `error`
    # taşıyabiliyor. Denetim KOŞULSUZ: `veo_client._operation_hatasi`nin
    # "iş düştüyse sonuç geçersiz, gövdede bir video görünse bile teslim
    # edilmemeli" kararının aynısı — bayat/kısmi bir video, parayı zaten
    # harcamış DÜŞMÜŞ bir işin üstünü örtmemeli.
    #
    # `map_error` BURADA ÇAĞRILMIYOR: onun sözleşmesi bir HTTP DURUM KODUNU
    # çevirmek ve buradaki yanıt 200 — `map_error(200, …)` genel "istek
    # başarısız (HTTP 200)" dalına düşer, yani kullanıcıya anlamsız bir
    # cümle gösterirdi. Gerekçe doğrudan yazılıyor.
    hata = detail_of(sonuc)
    if hata:
        raise ac.ImageError(i18n.t(hata_anahtari, None, hata=hata))

    # ── 4. İndirme ───────────────────────────────────────────────────────
    return _indir(client, cikti_url(sonuc))


def generate_video(m: catalog.ImageModel, prompt: str, size: str, quality: str,
                   duration: int, n: int, *, client=None,
                   credentials=None) -> list[bytes]:
    """Video sözleşmesinin `generate_video`su (providers.py başlığı).

    2026-09-23'e kadar bu işlevin adı `generate` idi; görsel sözleşmesi o adı
    isteyince (`providers._ADAPTERS` çifti `(generate, edit)`) video tarafı
    sözleşmenin kendi adını aldı. `providers._fal_adapter` bu adı veriyor.
    """
    return _uret(m, prompt, size, quality, duration, n, None,
                 client=client, credentials=credentials)


def animate(m: catalog.ImageModel, prompt: str, images, size: str, quality: str,
            duration: int, n: int, *, last_frame=None, client=None,
            credentials=None) -> list[bytes]:
    """`images`: sıralı [(dosya_adı, png_baytları), ...] — yalnız ilki kullanılıyor.

    `last_frame` SÖZLEŞMEDE VAR ama bu sağlayıcıda DESTEKLENMİYOR.
    DÜZELTME (Görev 9, 2026-09-15): bu gerekçe önceden "üç modelin hiçbirinin
    i2v şemasında `tail_image_url` yok" diyordu — doğru ama BOŞ: o ad fal'da
    hiç kullanılmıyor. Görev 8'in tam şema ölçümü Wan'ın i2v ucunda GERÇEKTEN
    bir son-kare alanı olduğunu gösterdi (`end_image_url`, son kare desteği
    VAR); `ALANLAR` onu bu turda BİLİNÇLİ OLARAK göndermiyor, o yüzden bayrak
    dürüstçe `False`. PixVerse ve Kling'in şemalarında ise gerçekten hiçbir
    son-kare alanı yok. Kapı `providers.animate_video`'da
    (`supports_last_frame=False`) ve buradaki iddia onun İKİNCİ kapısı —
    `providers.edit`in ikinci kapı disiplininin aynısı.
    """
    if last_frame is not None:
        raise ac.ImageError(
            i18n.t("err.model_no_last_frame", None, model=m.label))
    return _uret(m, prompt, size, quality, duration, n, images,
                 client=client, credentials=credentials)


# ── GÖRSEL (Faz 4 / 1b-D, 2026-09-23) ────────────────────────────────────


@dataclasses.dataclass(frozen=True)
class GorselTelBicimi:
    """Bir GÖRSEL modelinin tel biçimi — `TelBicimi`nin görsel ikizi.

    AYRI SINIF, `TelBicimi`ye alan eklenmedi: video biçiminin `sure_dize`/
    `ses_ekseni` eksenleri görselde yok, görselin `output_format`/`image_size`
    eksenleri videoda yok; tek sınıfta yarısı hep `None` duran alanlar,
    `__post_init__`ün değişmezlerini de bulanıklaştırırdı.

    `duzenleme=None` = bu modelin DÜZENLEME UCU YOK (schnell). Katalog
    `supports_edit=False` diyor ve `providers.edit` orada zaten reddediyor; bu
    tablo İKİNCİ kapı (`providers.edit`in ikinci kapı disiplini): `edit` başka
    bir yoldan çağrılsa gövde kurulmadan Türkçe hata.
    """

    metin: frozenset[str]                  # metin→görsel ucunun okuduğu adlar
    duzenleme: frozenset[str] | None       # düzenleme ucunun okuduğu adlar; None = uç yok
    gorsel_alani: str = ""                 # referansların gittiği ad: tek `image_url` ya da liste `image_urls`

    def __post_init__(self) -> None:
        # Düzenleme ucu varsa referans alanı o kümenin ÜYESİ olmak ZORUNDA
        # (`TelBicimi.__post_init__`ün aynı değişmezi): değilse referans
        # sessizce düşer ve "düzenleme" metinden üretime döner.
        if self.duzenleme is not None and self.gorsel_alani not in self.duzenleme:
            raise ValueError(
                f"gorsel_alani={self.gorsel_alani!r} duzenleme kumesinde yok: "
                f"{sorted(self.duzenleme)}")
        if self.duzenleme is None and self.gorsel_alani:
            raise ValueError("duzenleme ucu yokken referans alani beyan edilmis")


# `image_urls` ile biten ad LİSTE alır, `image_url` TEK dize — fal'ın kendi
# adlandırma kuralı (TanStack/ai `image-field-overrides.ts` her ucu böyle
# etiketliyor: `single: 'image_urls'` Seedream'de, `image_url` Qwen'de).
_LISTE_ALANI_SONEKI = "urls"

# ÇIKTI BİÇİMİ: adaptör sözleşmesi PNG BAYTI istiyor (providers.py başlığı).
# `output_format` şemada olan uçlara "png" isteniyor; olmayanda (Seedream)
# dönen bayt `_png_garantile` ile PNG'ye çevriliyor — iki yol da aynı garantiyi
# veriyor, biri telde biri yerelde.
PNG_BICIMI = "png"

GORSEL_ALANLAR: dict[str, GorselTelBicimi] = {
    # Qwen Image: metin ucu `image_size` (`{width, height}` nesnesi — fal'ın
    # ortak `ImageSize` tipi, hazır ad ya da nesne), `num_images`,
    # `output_format`. Düzenleme ucu (`fal-ai/qwen-image-edit`) TEK `image_url`
    # (2509/plus varyantları `image_urls` alıyor, onlar listede değil) ve
    # `image_size`ı DA okuyor (fal'ın qwen-image-edit şeması listeliyor).
    # İlk sürüm alanı bu uçtan DÜŞÜRÜYORDU: kullanıcının seçtiği boyut
    # `check_capabilities`ten geçmiş, sonra sessizce referansın geometrisine
    # kaymıştı — "sessiz sapma yasak" (#80 incelemesi). Alanın canlıda kabulü
    # sahibin sandbox turunun bir durağı (Kling V3 Pro ve Seedance'tan sonra).
    "fal-qwen-image": GorselTelBicimi(
        metin=frozenset({"prompt", "image_size", "num_images", "output_format"}),
        duzenleme=frozenset({"prompt", "image_url", "image_size", "num_images",
                             "output_format"}),
        gorsel_alani="image_url",
    ),
    # Seedream V4: `image_size` nesne (kenar 1024–4096), `num_images`;
    # `output_format` şemada GÖRÜLMEDİ → gönderilmiyor, PNG yerelde
    # garantileniyor. Düzenleme ucu `image_urls` LİSTESİ (10'a kadar) ve
    # `image_size`ı da okuyor (fal-ai-community iş akışı örneği ikisini
    # birlikte gönderiyor).
    "fal-seedream-v4": GorselTelBicimi(
        metin=frozenset({"prompt", "image_size", "num_images"}),
        duzenleme=frozenset({"prompt", "image_urls", "image_size", "num_images"}),
        gorsel_alani="image_urls",
    ),
    # FLUX.1 [schnell]: yalnız metin→görsel; `image_size` nesne, `num_images`,
    # `output_format` (varsayılanı jpeg — png İSTENİYOR). Düzenleme ucu YOK.
    "fal-flux-1-schnell": GorselTelBicimi(
        metin=frozenset({"prompt", "image_size", "num_images", "output_format"}),
        duzenleme=None,
    ),
}


def _boyut(size: str) -> tuple[int, int]:
    """`"1024x768"` → `(1024, 768)`. Katalog jetonu; `models.check_capabilities`
    zaten kümeyle sınırladı, burada biçim dışı bir jeton programlama hatası."""
    w, h = size.lower().split("x", 1)
    return int(w), int(h)


def build_image_payload(m: catalog.ImageModel, prompt: str, size: str, n: int,
                        images) -> dict:
    """Görsel isteğinin gövdesi — `build_payload`ın görsel ikizi, aynı süzgeç disiplini.

    `num_images` HEP 1, `n` değil: katalog `images_per_request=1` diyor ve
    adet döngüsü `_kuyruk_dongusu`nda — fal'ın `num_images` tavanı modele göre
    değişiyor (ölçülmedi) ve tavanı aşan tek bir istek 422 üretirdi; adet
    başına ayrı istek her tavanın altında kalıyor. `n` imzada duruyor ki
    çağıranın niyeti görünür kalsın ve tavan ölçüldüğü gün tek yerde değişsin.

    `images` sıralı [(dosya_adı, png_baytları), ...]; tek alanlı uçta İLKİ,
    liste alanlı uçta `m.max_refs` kadarı gidiyor (fazlası rotada zaten elendi,
    burada ikinci kapı).
    """
    bicim = GORSEL_ALANLAR[m.id]
    if images:
        if bicim.duzenleme is None:
            # İkinci kapı (`providers.edit` birincisi): uç yokken referansla
            # çağrılan model metin ucuna DÜŞMEZ — o, kullanıcının yüklediği
            # görselin sessizce yok sayılması olurdu.
            raise ac.ImageError(
                i18n.t("err.model_no_reference", None, model=m.label))
        izin = bicim.duzenleme
    else:
        izin = bicim.metin
    w, h = _boyut(size)
    tum: dict = {
        "prompt": prompt,
        "image_size": {"width": w, "height": h},
        "num_images": 1,
        "output_format": PNG_BICIMI,
    }
    if images:
        uriler = [_data_uri(png) for _, png in images[:max(1, m.max_refs)]]
        tum[bicim.gorsel_alani] = (uriler if bicim.gorsel_alani.endswith(_LISTE_ALANI_SONEKI)
                                   else uriler[0])
    return {ad: deger for ad, deger in tum.items() if ad in izin}


_PNG_IMZASI = b"\x89PNG\r\n\x1a\n"


def _png_garantile(veri: bytes) -> bytes:
    """Dönen baytı PNG olarak teslim eder; PNG değilse Pillow ile çevirir.

    Sözleşme "çözülmüş PNG baytları" (providers.py başlığı) ve `storage.save`
    uzantıyı `kind`ten türetiyor (`.png`): JPEG baytını `.png` adıyla yazmak
    tarayıcıda açılır ama sessiz bir sapmadır (`composite` PNG bekler, meta
    okuyucular imzayı okur). `output_format` isteyebildiğimiz uçlarda bu yol
    hiç çalışmaz (imza tutar, bayt AYNEN geçer); Seedream'de çalışır.
    Çözülemeyen bayt Türkçe `ImageError`: ham `UnidentifiedImageError`
    `app.py`nin süzgecinden geçip 500 olurdu.
    """
    if veri.startswith(_PNG_IMZASI):
        return veri
    import io

    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(veri)) as im:
            # PNG yazıcı her modu bilmiyor: CMYK (JPEG'de yaygın) ya da YCbCr
            # `save(format="PNG")`de OSError verir ve o hata aşağıda "görsel
            # değil" diye okunurdu — oysa görsel geçerli, yalnız modu yabancı
            # (#80 incelemesi). Saydamlığı olan modlar RGBA'ya, ötekiler
            # RGB'ye çevrilir; PNG ikisini de yazar.
            saydam = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
            cikti = io.BytesIO()
            im.convert("RGBA" if saydam else "RGB").save(cikti, format="PNG")
    except (UnidentifiedImageError, OSError) as exc:
        raise ac.ImageError(i18n.t("err.fal_not_an_image")) from exc
    return cikti.getvalue()


def _gorsel_uret(m: catalog.ImageModel, prompt: str, size: str, n: int, images, *,
                 client, credentials) -> list[bytes]:
    """`generate`/`edit`in paylaşılan gövdesi — `_uret`in görsel ikizi."""
    payload = build_image_payload(m, prompt, size, n, images)
    ham = _kuyruk_dongusu(m, wire_path_for(m, images=images), payload, n,
                          client=client, credentials=credentials,
                          cikti_url=_gorsel_url, hata_anahtari="err.fal_no_image")
    return [_png_garantile(b) for b in ham]


def generate(m: catalog.ImageModel, prompt: str, size: str, quality: str, n: int,
             *, client=None, credentials=None) -> list[bytes]:
    """Görsel sözleşmesinin `generate`i (providers.py başlığı).

    `quality` BİLEREK YOK SAYILIYOR: üç fal görsel modelinin kalite ekseni yok
    (katalog tek sentetik jeton + `quality_hidden=True`); imzada sözleşme
    gereği duruyor — `azure_mai_client.generate`in aynı duruşu.
    """
    return _gorsel_uret(m, prompt, size, n, None, client=client, credentials=credentials)


def edit(m: catalog.ImageModel, prompt: str, images, size: str, quality: str,
         n: int, *, client=None, credentials=None) -> list[bytes]:
    """`images`: sıralı [(dosya_adı, png_baytları), ...] — ilk görsel ana referans.

    Referanslar base64 data URI olarak gövdede gidiyor (`_data_uri`; yükleme
    adımı yok — videonun aynı kararı). Uç yolu `wire_model_edit` (fal'da
    düzenleme AYRI uç, `wire_path_for`). Düzenleme ucu olmayan model
    `build_image_payload`da reddediliyor.
    """
    return _gorsel_uret(m, prompt, size, n, images, client=client, credentials=credentials)
