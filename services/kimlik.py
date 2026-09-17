# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kimlik kapısı — `aktif_kullanici` bağımlılığı: çerezden kullanıcı, yoksa 401 (Faz 1 / 3).

Bu PR'da yalnız hesap rotaları kullanıyor (`GET /api/hesap/ben`, `POST
/api/hesap/cikis`). Öteki 44 rotaya kapı 4. görevde giriyor
(docs/faz1-veritabani-hesaplar.md → 4): oraya kadar stüdyo oturumsuz
çalışmaya devam ediyor ve E2E takımı onu öyle sınıyor. Kapı ARA KATMAN DEĞİL
BAĞIMLILIK, bilerek: hangi rotanın açık olduğu imzasında okunur (Faz 0 / 4'ün
"imza bağımlılığı söyler" ilkesi) ve 4. görevin bekçi testi tam olarak o
imzayı sayacak.

401 JSON, 302 DEĞİL: `fetch` yönlendirmeyi takip eder ve JSON bekleyen çağrı
HTML alırdı; ön yüz 401'i görünce `/giris`e kendisi gider. Tarayıcı
gezinmesi olan tek rota `GET /` ve onun 302'si 4. görevin işi.

KAYAN ÖMÜR BURADAN YAZILIR: `hesap.oturum_dogrula` `son_gorulme`yi 5 dk
çözünürlükle ilerlettiğinde çerezin `Max-Age`i de yenilenmeli — yoksa DB'de
30 gün daha yaşayan bir oturumun çerezi tarayıcıda ilk 30 günün sonunda
düşerdi. Bağımlılık `response: Response` alabiliyor (FastAPI bunu rotanın
cevabına birleştiriyor), yani rota bunu bilmek zorunda değil.
"""
from __future__ import annotations

from fastapi import HTTPException, Request, Response
from sqlalchemy.orm import Session

import i18n
from services import cerez, dil, hesap
from services.db import OTURUM
from services.tablolar import Kullanici


def aktif_kullanici(request: Request, response: Response, db: Session = OTURUM) -> Kullanici:
    """FastAPI bağımlılığı: bu isteğin kullanıcısı; oturum yoksa/bitmişse 401.

    `request.state.kullanici`ya da konur: aynı istekte ikinci kez soran
    (ara katman, günlük) sorgu tekrarlamasın (4. görevin `ayarlar(request)`
    kapısı da buradan okuyacak).
    """
    ham = request.cookies.get(cerez.OTURUM_CEREZI)
    sonuc = hesap.oturum_dogrula(db, ham, hesap.simdi()) if ham else None
    if ham is None or sonuc is None:
        raise HTTPException(status_code=401,
                            detail=i18n.t("err.hesap_giris_gerekli", dil.aktif()))
    kullanici, yenilendi = sonuc
    if yenilendi:
        cerez.oturum_yaz(response, ham)
    request.state.kullanici = kullanici
    return kullanici
