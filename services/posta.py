# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""E-posta gönderimi — doğrulama ve sıfırlama iletileri, iki arka uç (Faz 1 / 3. görev).

Hesap akışının iki yerinde e-posta var: kayıtta doğrulama bağlantısı, "parolamı
unuttum"da sıfırlama bağlantısı. İkisi de DÜZ METİN (belge §3: "şablon HTML
değil"): tıklanabilir bir bağlantı yeter, HTML şablonu bir tasarım ve bir
test yüzeyi daha demek.

İKİ ARKA UÇ, tek arayüz (`Postaci`):

* `KonsolPostaci` — geliştirme ve test. İletiyi `hata.log`un yanına
  `posta.log`a yazar ve SON iletiyi `son`da tutar: E2E testi doğrulama
  bağlantısını buradan okuyor (`app.state.postaci.son`), gerçek bir gelen
  kutusundan değil. Ağa ÇIKMAZ — testler hiçbir zaman Resend'e istek atmaz.
* `ResendPostaci` — dağıtım. `https://api.resend.com/emails`e `httpx` ile
  JSON (K7: SDK yok, depo zaten httpx taşıyor). Anahtar `RESEND_API_KEY`,
  gönderen `KROMIS_POSTA_GONDEREN` (`Kromis Studio <no-reply@alan>` biçimi
  de geçer; alan adının SPF/DKIM'i sahibin işi).

SEÇİM (`postaci_kur`): `KROMIS_POSTA=konsol|resend` açıkça söylerse o; yoksa
`RESEND_API_KEY` doluysa `resend`, boşsa `konsol`. Yani anahtarı vermek
yetiyor, ama `KROMIS_POSTA=resend` deyip anahtarı unutan bir dağıtım SESSİZCE
konsola DÜŞMEZ: `BozukPostaci` gelir ve her gönderim `PostaHatasi` fırlatır —
rota bunu 503'e çevirir, sebep `hata.log`a düşer. Uygulama yine açılır
(`/health` bundan etkilenmez; açılmayan uygulamadan iyidir), ama kullanıcı
"iletiyi gönderdik" yalanını görmez.

METİNLER SÖZLÜKTEN (`bundled/i18n`, `posta.*` anahtarları): ileti alıcının
dilinde — kayıtta isteğin dili (`dil.aktif()`), sıfırlamada kullanıcının
kayıtlı dili varsa o. Bağlantının tabanı `KROMIS_KOKEN` (services/koken.py).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import httpx

import errlog
import i18n

POSTA_ENV = "KROMIS_POSTA"
GONDEREN_ENV = "KROMIS_POSTA_GONDEREN"
RESEND_ANAHTAR_ENV = "RESEND_API_KEY"

RESEND_ADRESI = "https://api.resend.com/emails"

# Konsol arka ucunun dosyası — `hata.log`un yanında, aynı `data_dir`de.
POSTA_LOG = "posta.log"

# Gönderen verilmediğinde (yalnız konsol arka ucunda anlamlı) — Resend bu
# adresi kabul etmez, orada `KROMIS_POSTA_GONDEREN` zorunlu.
VARSAYILAN_GONDEREN = "Kromis Studio <no-reply@localhost>"

# Resend'e bir istek için üst sınır: kayıt rotası bu çağrıyı BEKLİYOR
# (ileti gitmeden "gönderildi" denmiyor), o yüzden sonsuz bekleme yok.
ZAMAN_ASIMI_SN = 10.0


# Hiçbir arka ucun göndermeyeceği alan adları (Faz 4 / 5): silinen hesabın
# e-postası `silindi-<id>@anonim.invalid` olur (RFC 2606 rezerve TLD — hiçbir
# zaman çözülmez) ve bir gün bir kod yolu o adrese ileti kurarsa (hibe
# bildirimi, sıfırlama) Resend'e geçersiz alıcı gitmesin, konsol günlüğüne de
# anonim adres düşmesin. Kapı ARKA UCUN İÇİNDE değil sarmalda: iki arka uç da
# aynı `gonder`den geçsin, üçüncüsü eklenince unutulmasın.
GONDERILMEYEN_TLD = ".invalid"


class PostaHatasi(Exception):
    """İleti gönderilemedi — arka uç sebebi mesajda söyler; rota 503 döner."""


def alici_denetle(kime: str) -> None:
    """`.invalid` alıcıya ileti KURULMAZ (gerekçe `GONDERILMEYEN_TLD`nin üstünde); `PostaHatasi`."""
    if kime.strip().lower().endswith(GONDERILMEYEN_TLD):
        raise PostaHatasi("alici adresi .invalid: anonim hesaba ileti gitmez")


@dataclass(frozen=True)
class Posta:
    kime: str
    konu: str
    metin: str


class Postaci(Protocol):
    def gonder(self, posta: Posta) -> None: ...


class KonsolPostaci:
    """`posta.log`a yazar, sonuncuyu hafızada tutar (gerekçesi modül başında)."""

    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir
        self.son: Posta | None = None

    def gonder(self, posta: Posta) -> None:
        alici_denetle(posta.kime)
        self.son = posta
        yol = os.path.join(self.data_dir, POSTA_LOG)
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(yol, "a", encoding="utf-8", newline="\n") as f:
                f.write(f"\n--- KIME: {posta.kime}\n--- KONU: {posta.konu}\n{posta.metin}\n")
        except OSError as e:
            # Dosya yazılamadıysa ileti yine `son`da: E2E onu okuyabilir, ama
            # geliştirici günlüğü göremediğini bilsin.
            errlog.safe_append(self.data_dir, f"posta.log yazilamadi: {e!r}")


class ResendPostaci:
    """Resend HTTPS API'si. `istemci` testte `httpx.MockTransport` ile veriliyor."""

    def __init__(self, api_key: str, gonderen: str,
                 istemci: httpx.Client | None = None) -> None:
        if not api_key:
            raise ValueError(f"{RESEND_ANAHTAR_ENV} bos")
        if not gonderen:
            raise ValueError(f"{GONDEREN_ENV} bos")
        self.api_key = api_key
        self.gonderen = gonderen
        self.istemci = istemci or httpx.Client(timeout=ZAMAN_ASIMI_SN)

    def gonder(self, posta: Posta) -> None:
        alici_denetle(posta.kime)
        try:
            cevap = self.istemci.post(
                RESEND_ADRESI,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"from": self.gonderen, "to": [posta.kime],
                      "subject": posta.konu, "text": posta.metin},
            )
        except httpx.HTTPError as e:
            raise PostaHatasi(f"resend: baglanti hatasi: {e!r}") from e
        if cevap.status_code >= 300:
            # Gövde günlüğe DEĞİL hataya: `errlog.redact_secrets` anahtarı
            # siler, ama Resend'in gövdesinde alıcı adresi de var — rota
            # `hata.log`a yalnız durum kodunu yazsın.
            raise PostaHatasi(f"resend: HTTP {cevap.status_code}")


class BozukPostaci:
    """Yapılandırma eksik/yanlış: her gönderim `PostaHatasi` (gerekçesi modül başında)."""

    def __init__(self, sebep: str) -> None:
        self.sebep = sebep

    def gonder(self, posta: Posta) -> None:
        raise PostaHatasi(self.sebep)


def secim() -> str:
    """Hangi arka uç: `KROMIS_POSTA` açıkça, yoksa anahtarın varlığına göre."""
    acik = (os.environ.get(POSTA_ENV) or "").strip().lower()
    if acik:
        return acik
    return "resend" if (os.environ.get(RESEND_ANAHTAR_ENV) or "").strip() else "konsol"


def postaci_kur(data_dir: str) -> Postaci:
    """Sürecin postacısı — `app.py` lifespan'da bir kez kurar (`app.state.postaci`)."""
    ad = secim()
    if ad == "konsol":
        return KonsolPostaci(data_dir)
    if ad == "resend":
        try:
            return ResendPostaci((os.environ.get(RESEND_ANAHTAR_ENV) or "").strip(),
                                 (os.environ.get(GONDEREN_ENV) or "").strip())
        except ValueError as e:
            return BozukPostaci(f"{POSTA_ENV}=resend ama {e}")
    # Metin GELİŞTİRİCİYE gidiyor (`hata.log`), ekrana değil — ASCII kalıyor ki
    # tests/test_i18n.py'nin kaçan-metin taraması onu arayüz cümlesi sanmasın.
    return BozukPostaci(f"{POSTA_ENV}={ad!r} bilinmiyor (konsol|resend)")


# ── İleti şablonları ─────────────────────────────────────────────────

def dogrulama_postasi(kime: str, baglanti: str, lang: str, saat: int) -> Posta:
    """E-posta doğrulama iletisi, `lang` dilinde."""
    return Posta(kime=kime,
                 konu=i18n.t("posta.dogrulama_konu", lang),
                 metin=i18n.t("posta.dogrulama_govde", lang, baglanti=baglanti, saat=saat))


def sifirlama_postasi(kime: str, baglanti: str, lang: str, dakika: int) -> Posta:
    """Parola sıfırlama iletisi, `lang` dilinde."""
    return Posta(kime=kime,
                 konu=i18n.t("posta.sifirlama_konu", lang),
                 metin=i18n.t("posta.sifirlama_govde", lang, baglanti=baglanti, dakika=dakika))


def silme_postasi(kime: str, lang: str, gun: int) -> Posta:
    """Hesap kapatıldı iletisi (Faz 4 / 5): içerik `gun` gün sonra silinir; ASIL adrese, anonimleşmeden ÖNCE kurulur.

    Bağlantı yok: geri alma yok (K9), tıklanacak bir şey de yok. `gun` ortamdan
    (`KROMIS_HESAP_SILME_BEKLEME_GUN`); 0 = "hemen" cümlesi ayrı anahtar değil,
    "0 gün" — sayı doğru, cümle dürüst.
    """
    return Posta(kime=kime,
                 konu=i18n.t("posta.silme_konu", lang),
                 metin=i18n.t("posta.silme_govde", lang, gun=gun))


def mevcut_hesap_postasi(kime: str, giris_baglantisi: str, lang: str) -> Posta:
    """Doğrulanmış bir adrese yeniden kayıt denemesi: sahibine "zaten hesabın var".

    Kayıt cevabı adresin varlığını söylemiyor (routers/hesap.py); bilgi
    adresin SAHİBİNE gidiyor — ve isteyen gerçekten oysa, aradığı şey
    "parolamı unuttum" bağlantısı.
    """
    return Posta(kime=kime,
                 konu=i18n.t("posta.mevcut_hesap_konu", lang),
                 metin=i18n.t("posta.mevcut_hesap_govde", lang, baglanti=giris_baglantisi))
