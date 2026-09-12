# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Katalog verisinin KULLANICIYA giden hâli — etiketler ve kısa adlar.

NEDEN AYRI BİR MODÜL: bu işlevler `catalog` ile `i18n`in ikisine birden
ihtiyaç duyuyor, ama `catalog.py` YAPRAK kalmak zorunda — proje içinden
hiçbir şey import etmiyor ve bu bir mandal altında (`tests/test_catalog.py`,
`test_katalog_yaprak_kalmali`). Gerekçe orada yazılı: katalog `models`,
`prefs`, `storage` ve her adaptör tarafından import ediliyor, yani oraya
giren her bağımlılık döngü riski demek. `i18n` da `paths`i çekiyor, yani
kataloğu dosya sistemi olmadan test etmek imkânsızlaşırdı.

Ayrım şu: `catalog` neyin VAR OLDUĞUNU söylüyor (jetonlar, yetenekler,
etiket anahtarları), bu modül onu kullanıcının OKUYACAĞI metne çeviriyor.
Aynı seam `credstore`da da var: katalog neyin var olduğunu bilir, neyin
erişilebilir olduğunu bilmez.
"""
from __future__ import annotations

from collections.abc import Sequence

import catalog
import i18n


def label_of(x) -> str:
    """Katalog etiketinin KULLANICIYA giden hâli.

    Etiketlerin çoğu marka adı ("OpenAI · gpt-image-2") ve marka çevrilmez —
    o yüzden `label` alanı çeviri anahtarı olmak ZORUNDA DEĞİL: Türkçe sözcük
    taşıyan dördü anahtar, gerisi literal. Ayrımı bu fonksiyon görünmez
    kılıyor, çünkü `i18n.t` sözlükte olmayan bir anahtarı OLDUĞU GİBİ
    döndürüyor — marka adı kendisi olarak geçiyor.

    Neden 25 etiketin hepsi anahtara çevrilmedi: marka adlarını kataloğa
    taşımak onları çevrilebilir GÖSTERİRDİ ve bir gün biri "OpenAI"yi
    çevirmeye çalışırdı. Burada çevrilebilir olan, yalnız çevrilmesi gereken.

    KULLANICIYA GİDEN HER OKUMA buradan geçmeli; kaçan bir okuma ekranda ham
    anahtar gösterir. Bekçisi `tests/test_playwright_dil.py`: DOM'da sözlük
    anahtarı arıyor.
    """
    return i18n.t(x.label)


def quality_label(token: str) -> str:
    """Kalite jetonunun AKTİF dildeki etiketi.

    Bilinmeyen jeton HATA DEĞİL (tablonun kendi notu): yeni bir sağlayıcı
    eklerken etiketi unutmak, o modelin arayüzde HİÇ görünmemesine yol
    açmamalı — ham jeton çirkin ama çalışır.
    """
    anahtar = catalog.QUALITY_LABELS.get(token)
    return i18n.t(anahtar) if anahtar else token


def duration_label(seconds: int) -> str:
    """Süre jetonunun arayüzdeki etiketi.

    `GEOMETRY_LABELS`/`QUALITY_LABELS` gibi bir tablo YOK ve gerekmiyor:
    jeton sayı olduğu için etiket ondan türetilebiliyor. Tablo açmak, her
    yeni süre değerinde ikinci bir yere satır eklemeyi unutmanın kapısı
    olurdu — ve etiketi unutulan jeton arayüzde çıplak sayı olarak görünürdü.
    Etiketin SUNUCUDA türetilmesi ise `GEOMETRY_LABELS`in gerekçesiyle aynı:
    istemcide kurulan bir dize, aynı bilginin bayatlayabilen ikinci kopyası.
    """
    return i18n.t("gen.duration_label", None, sn=seconds)


# Marka ile adın arasındaki ayraç. Etiketlerin yazım kuralı bu ve `_drop_brand`
# aynı dizeyi hem ARIYOR hem UZUNLUĞUNU kullanıyor: iki yerde ayrı yazılmış
# olsaydı ("· " ile " · ") kırpma bir karakter kayar ve ad boşlukla başlardı.
_BRAND_SEP = " · "


def _drop_brand(label: str, provider: str) -> str:
    marka = catalog.PROVIDER_BRANDS.get(provider)
    if not marka:
        return label
    onek = f"{marka}{_BRAND_SEP}"
    return label[len(onek):] if label.startswith(onek) else label


def short_labels(
    models: Sequence[catalog.ImageModel] | Sequence[catalog.ChatModel],
) -> dict[str, str]:
    """Model id → ŞERİTTE gösterilecek ad: marka öneki düşürülmüş `label`.

    ÇAKIŞMA KURALI tek istisna ve ölçülmüş bir kırılmayı kapatıyor: önek
    düşünce `Azure · gpt-image-2` ile `OpenAI · gpt-image-2` AYNI satıra
    dönüşüyor — ikisinin de anahtarı olan kullanıcı açılan listede hangisini
    seçtiğini bilemez ve native bir `<option>` işaret taşıyamıyor, yani logo o
    satırları ayırmıyor. O yüzden kısa adı bir başkasıyla çakışan model TAM
    etiketini koruyor. Kullanıcının gördüğü fark şu: markası tekil olan her
    model (Gemini'nin ikisi, OpenAI'nin sohbet kademeleri) önekini bırakıyor,
    yalnız gerçekten iki yerde birden bulunan ad markasını taşımaya devam
    ediyor.

    Önek `f"{marka} · "` deseniyle aranıyor, "içinde marka geçiyor mu" diye
    DEĞİL: Azure'ın sohbet girdisi `Azure AI Foundry dağıtımı` ve orada marka
    adın PARÇASI (Azure'da model yok, dağıtım var) — kırpılırsa etiket
    anlamsızlaşır.

    `models` iki tür alıyor (`ImageModel` ve `ChatModel`); ortak alan olarak
    yalnız `id`, `label` ve `provider` okunuyor.
    """
    # ÇEVRİLMİŞ etiketten kırpılıyor, ham alandan değil: dört girdide `label`
    # bir çeviri anahtarı (bkz. `label_of`) ve anahtarın başında marka öneki
    # yok — kırpma orada hiç tutmazdı. Üstelik çakışma kuralı doğası gereği
    # GÖRÜNEN adla ilgili: kullanıcı ekranda aynı duran iki satırı ayırt
    # edemiyor, ham alanda farklı olmaları onu kurtarmıyor.
    cozulmus = {m.id: label_of(m) for m in models}
    kisa = {m.id: _drop_brand(cozulmus[m.id], m.provider) for m in models}
    adlar = list(kisa.values())
    cakisan = {ad for ad in adlar if adlar.count(ad) > 1}
    return {m.id: (cozulmus[m.id] if kisa[m.id] in cakisan else kisa[m.id])
            for m in models}
