# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Çerez bayrakları — iki çerezin (dil, oturum) TEK yerden aldığı karar (Faz 1 / 3. görev).

NEDEN AYRI MODÜL: `Secure` bayrağı bir çerezin değil DAĞITIMIN özelliği.
`services/dil.py` dil çerezini yazıyor, `routers/hesap.py` oturum çerezini;
ikisi bayrağı kendi başına kararlaştırsaydı bir gün biri `Secure`, öteki
`Secure`süz giderdi ve düz HTTP'de biri saklanıp öteki düşerdi — kullanıcı
dilini görür ama oturumunu kaybeder, teşhisi zor bir kusur. Karar burada,
okuyan iki yer.

`Secure` NE ZAMAN: bayrak açıkken tarayıcı çerezi yalnız HTTPS'te saklar ve
gönderir. Bu uygulamanın İKİ hâli var ve ikisinin doğru cevabı farklı:

* **Web** (`DATABASE_URL` verilmiş — çok kullanıcılı dağıtım, TLS arkasında):
  `Secure` AÇIK. Oturum çerezi bir kimlik; düz HTTP'de taşınması sızıntıdır.
* **Dondurulmuş kabuk** (masaüstü/Android, `DATABASE_URL` yok, loopback
  `http://127.0.0.1`): `Secure` KAPALI — WKWebView ve eski Safari düz HTTP'de
  `Secure` çerezi saklamaz, dil seçimi sessizce kaybolurdu (services/dil.py'nin
  Faz 0'daki gerekçesi aynen geçerli, o kabuk hâlâ yaşıyor).

Yani öntanımlı karar "web modu = güvenli" ve web modunun bayrağı belgenin
başka yerde de kullandığı tek bayrak: `DATABASE_URL`in varlığı
(docs/faz1-veritabani-hesaplar.md, `guncelleme.py` notu — "tek bayrak,
services/db.py'nin okuduğuyla aynı kaynak"). `KROMIS_GUVENLI_CEREZ` bu
kararı EZER: yerel `compose.yaml` `0` verir (Safari `localhost`ta bile düz
HTTP'de `Secure` çerezi saklamaz; Chrome/Firefox saklar), TLS'siz bir iç ağ
denemesi de aynı kapıdan geçer. Bekçi test öntanımlının web'de AÇIK
olduğunu sınar (tests/test_hesap.py).
"""
from __future__ import annotations

import os

from fastapi import Response

from services import db

# Oturum çerezinin adı — ham jeton burada, SHA-256 özeti `oturumlar`da
# (services/hesap.py). `kromis_lang` ile aynı önek: tarayıcının çerez
# listesinde ikisi yan yana dursun.
OTURUM_CEREZI = "kromis_oturum"

# Kayan ömür: 30 gün (belge, §3 "30 gün kayan ömür"). Çerezin `Max-Age`i ve
# `oturumlar.bitis` aynı sayıdan; `son_gorulme` ilerlediğinde ikisi birlikte
# yenilenir (hesap.oturum_dogrula).
OTURUM_OMRU_SN = 30 * 24 * 60 * 60

# `Secure` kararını ezen ortam değişkeni: `0`/`false`/`hayir` kapatır, başka
# her dolu değer açar, boş/yok = öntanımlı kural (modül başında).
GUVENLI_ENV = "KROMIS_GUVENLI_CEREZ"

_KAPALI = frozenset({"0", "false", "hayir", "no", "off"})


def guvenli() -> bool:
    """Bu süreçte çerezler `Secure` bayrağıyla mı yazılıyor? (kural modül başında)"""
    deger = (os.environ.get(GUVENLI_ENV) or "").strip().lower()
    if deger:
        return deger not in _KAPALI
    return db.baglanti_dizesi() is not None


def oturum_yaz(response: Response, jeton: str) -> None:
    """Oturum çerezini kurar — girişte ve kayan ömür yenilenirken.

    `httponly`: betiğin jetona dokunması için hiçbir sebep yok; XSS'in ilk
    hedefi tam olarak bu çerez. `samesite=lax`: başka siteden gelen POST'ta
    taşınmaz (CSRF'nin ilk katı; ikincisi services/koken.py). `path=/`: her
    rota aynı oturumu görür.
    """
    response.set_cookie(OTURUM_CEREZI, jeton, max_age=OTURUM_OMRU_SN, path="/",
                        httponly=True, samesite="lax", secure=guvenli())


def oturum_sil(response: Response) -> None:
    """Çıkışta çerezi düşürür. Bayraklar YAZANLA AYNI olmak zorunda: tarayıcı
    çerezi ad + yol + bayrak üçlüsüyle eşliyor, farklı bayrakla gönderilen bir
    silme komutu başka bir çerezi hedefler ve asıl çerez yerinde kalır."""
    response.delete_cookie(OTURUM_CEREZI, path="/", httponly=True, samesite="lax",
                           secure=guvenli())
