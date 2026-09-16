# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İsteğin arayüz dili — yazan ara katman ve okuyan sarmalayıcı, tek dosyada."""
from __future__ import annotations

from fastapi import Request

import i18n
import prefs
from services import yollar


async def dil_baglami(request: Request, call_next):
    """Her isteğin başında arayüz dilini kurar. `i18n._AKTIF`ın TEK YAZARI.

    NEDEN ARA KATMAN, rotada tek tek okumak DEĞİL: metni üreten yerlerin çoğu
    rotada değil — sekiz sağlayıcı istemcisinin `map_error`ı, `catalog`ın
    model notları, `chat_prompt`ın bağlam bloğu. Onların hepsine dili
    parametre olarak taşımak beş kademelik bir imza genişletmesi olurdu ve o
    zincire eklenen her yeni fonksiyon parametreyi unutmaya açık kalırdı.
    Tek bir yazar, tek bir okuma noktası.

    İSTEK BAŞINA okunuyor, modül düzeyinde bir sabite ALINMIYOR: tercih
    çalışırken değişebiliyor (Ayarlar'daki seçici `POST /api/prefs` atıyor) ve
    donmuş bir değer, dili çeviren kullanıcıya sunucu yeniden başlayana kadar
    eski dili göstermeye devam ederdi. `prefs.read` yan etkisiz ve tek bir
    küçük JSON okuması — loopback'te ölçülebilir bir bedeli yok.

    `Accept-Language` BİLEREK okunmuyor: kaynak tek olmalı. Tarayıcı başlığı
    ile diskteki tercih ayrıştığında hangisinin kazandığı, kullanıcının
    seçimini sessizce ezebilecek bir soru olurdu — ve bu uygulamada tarayıcı
    çoğu zaman pywebview'ın penceresi, yani başlık kullanıcının bir tercihi
    bile değil. (Çok kullanıcılı web'de kaynak isteğin kendisi olacak —
    docs/faz0-web-first.md, 3. görev; bu dosya o değişikliğin yeri.)

    Hata YUTULUYOR: dil, bir isteği düşürecek kadar önemli bir şey değil.
    `prefs.read` bozuk dosyada zaten varsayılana düşüyor; bu kapı onun
    ötesindeki durumlar için (okunamayan veri dizini).
    """
    try:
        i18n.set_active(prefs.read(yollar.output_dir()).get("language"))
    except OSError:
        i18n.set_active(i18n.DEFAULT)
    return await call_next(request)


def aktif() -> str:
    """Bu isteğin arayüz dili. Yazan taraf yukarıdaki ara katman.

    İnce bir sarmalayıcı ve ADIYLA duruyor: rotalar `i18n.active()` çağırsaydı
    okuyan kişi "hangi istek?" sorusunu her seferinde yeniden sormak zorunda
    kalırdı. Testler dili sabitlemek için BURAYI yamalıyor
    (`monkeypatch.setattr(dil, "aktif", lambda: "en")`) — tek nokta.
    """
    return i18n.active()
