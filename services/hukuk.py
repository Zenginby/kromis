# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Hukuki metinler — sürüm sabiti, onay damgası, `bundled/hukuk/` parçalarının okuyucusu (Faz 4 / 6, K11).

TEK GERÇEK KAYNAK: `HUKUK_SURUMU` üç yerden okunuyor — kayıt (`routers/hesap.py`
onay damgası), checkout (`routers/odeme.py` 412 kapısı) ve `GET /api/hesap/ben`
(`sartlar_guncel`). Üçü de BURADAN okur; 4. görevin `services/odeme.py`deki
`SARTLAR_SURUMU = "0000-yer-tutucu"` sabiti bu modüle bağlandı ve silindi.
Metin değişince yalnız bu sabit ilerler: eski sürümle onaylanmış her hesap
`sartlar_guncel: false` görür, ayarlar banner'ı yeni onay ister
(`POST /api/hesap/sartlar-kabul`). `0000-yer-tutucu` ile damgalanmış satırlar
da aynı yoldan yeniden onaya düşer — belge §4 (b) bunu böyle bırakmıştı.

`HUKUK_ONAYLI = False`: metinler TASLAK, avukat/mali müşavir onayı sahibin adımı
(belge §6 "Risk"). Bayrak `False` iken her metnin başında görünür bir "TASLAK —
avukat onayı bekliyor" damgası çizilir (`static/hukuk.html`); onay gelince tek
satırlık PR bayrağı çevirir, metne dokunmaz. Kod mekanizması (sürüm, damga,
sayfa, kayıt kutusu) onaydan bağımsız gemiye biner.

METİN DOSYADA, SÖZLÜKTE DEĞİL: `bundled/hukuk/<slug>.<dil>.html` bir HTML
PARÇASI (başlık + bölümler, `<html>`/`<body>` yok) — kabuk `static/hukuk.html`,
yerleştirme `services/sablon.py`. Markdown kütüphanesi yok (yeni bağımlılık),
i18n JSON'una 40 KB metin girmiyor (K11). Dosya her istekte diskten okunuyor
(`sablon.sayfa` ile aynı gerekçe: düzenle → yenile → gör). Dil zinciri
`services/dil.py`nin — sayfa isteğin dilinde, `Content-Language` başlığı onu söyler.

Kullanıcıya konuşan cümle ÜRETMİYOR: metni dosya taşıyor, 404'ü rota kurar
(tests/test_i18n.py `KULLANICIYA_KONUSMAYAN`).
"""
from __future__ import annotations

import os

import paths

# Metinlerin sürümü: YYYY-AA. Metin değişince ilerler → yeni onay istenir (modül başı).
HUKUK_SURUMU = "2026-10"

# Avukat onayı geldi mi? `False` = her sayfada "TASLAK" damgası (belge §6 "Sahibin adımı").
HUKUK_ONAYLI = False

# Beyaz liste: `GET /hukuk/{slug}` yalnız bunları açar; başkası 404. Sıra sayfa
# altındaki gezinmenin sırası (şartlar → gizlilik → çerez → ticari haklar).
SLUG_KULLANIM_SARTLARI = "kullanim-sartlari"
SLUG_GIZLILIK = "gizlilik"
SLUG_CEREZ = "cerez"
SLUG_TICARI_HAKLAR = "ticari-haklar"
SLUGLAR: tuple[str, ...] = (SLUG_KULLANIM_SARTLARI, SLUG_GIZLILIK, SLUG_CEREZ, SLUG_TICARI_HAKLAR)

# Her slug'ın gezinme etiketi — i18n anahtarı (kabuk ve footer bağlantıları aynı anahtarları kullanır).
BASLIK_ANAHTARLARI: dict[str, str] = {
    SLUG_KULLANIM_SARTLARI: "hukuk.kullanim_sartlari",
    SLUG_GIZLILIK: "hukuk.gizlilik",
    SLUG_CEREZ: "hukuk.cerez",
    SLUG_TICARI_HAKLAR: "hukuk.ticari_haklar",
}


def dosya_yolu(slug: str, dil_kodu: str) -> str:
    """`bundled/hukuk/<slug>.<dil>.html` — slug beyaz listeden geçmiş olmalı (rota denetler)."""
    return os.path.join(paths.bundled_hukuk_dir(), f"{slug}.{dil_kodu}.html")


def metin(slug: str, dil_kodu: str) -> str | None:
    """Parçanın HTML'i; slug beyaz listede değilse ya da dosya yoksa `None` (rota 404 kurar).

    Dosya eksikliği sessiz bir 404: dört slug × iki dil sekiz dosyanın hepsinin
    var olduğunu tests/test_hukuk.py ölçüyor, yani canlıda bu dal ancak paket
    bozuksa görünür — o zaman da doğru cevap 500 değil "böyle bir metin yok".
    """
    if slug not in SLUGLAR:
        return None
    try:
        with open(dosya_yolu(slug, dil_kodu), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def guncel_mi(surum: str | None) -> bool:
    """Hesabın onayladığı sürüm bugünkü metnin sürümü mü? (`GET /api/hesap/ben` `sartlar_guncel`)

    `None` (hiç onaylamamış — 6. görevden önce açılmış hesap) ve `0000-yer-tutucu`
    (4. görevin metinsiz checkout onayı) ikisi de `False`: metni görmeden verilmiş
    bir onay, metnin onayı değildir.
    """
    return surum == HUKUK_SURUMU
