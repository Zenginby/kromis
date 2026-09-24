# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Doğrulama hatası gövdesinden gizli değerlerin silinmesi (üç kapı)."""
from __future__ import annotations

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import catalog

# Kimlik FORMU olan rotalar: yanıtta hiçbir alanın değeri yankılanmak zorunda
# değil, o yüzden kapı alan adına değil ROTAYA bakıyor. Üç kapının en GÜÇLÜSÜ bu —
# yarın forma eklenen bir alan hiçbir şey hatırlanmadan kapsanıyor.
CREDENTIAL_ROUTES = frozenset({"/api/settings"})

# İkinci kapı: BAŞKA bir rotada geçebilecek gizli alan adları. Katalogdan
# TÜRETİLİYOR, elle sayılmıyor.
SECRET_FIELDS = frozenset({"api_key"}) | catalog.secret_field_names()
# Hesap alanları (Faz 1 / 3): `parola` bir doğrulama hatasında (`"8 karakterden
# kısa"`) `input` olarak gövdeye aynen dönerdi — kullanıcının yazdığı parola,
# hata cevabında. `jeton` tek kullanımlık e-posta bağlantısı; 422'ye düşse bile
# günlüğe ve cevaba girmesin. İkisi de bir soneke uymuyor, o yüzden adıyla.
SECRET_FIELDS |= {"parola", "jeton"}
# Üçüncü kapı: kataloğa hiç girmemiş alan da adının BİÇİMİNDEN yakalanıyor
# (bugünkü `fal_key` / `replicate_api_token` tam olarak bu kapıdan geçiyor).
SECRET_SUFFIXES = ("_api_key", "_key", "_token", "_secret")


def is_secret_loc(loc) -> bool:
    return any(str(p) in SECRET_FIELDS or str(p).endswith(SECRET_SUFFIXES)
               for p in loc)


async def redact_validation_errors(request: Request, exc: RequestValidationError):
    """Doğrulama hatası gövdesinde gizli değeri yankılama (FastAPI 'input' döner).

    v0.6'da GENELLEŞTİ ve sebebi ÖLÇÜLDÜ: kapı `loc` içinde birebir `"api_key"`
    arıyordu, yani BYOK alanları (`openai_api_key`, `fal_key`,
    `replicate_api_token` — üçü de v0.2.0'dan beri kabul ediliyor) kapsam
    DIŞINDAYDI. 500 karakteri aşan bir değer 422 alıyor ve anahtar `input`
    alanında istemciye AYNEN dönüyordu. `azure_client.py`'nin başındaki
    "bu yüzden ikinci bir gizli form alanı eklenmedi" notu tam olarak bu boşluğu
    tarif ediyor; boşluk kapandığı için o notun dayattığı kısıt da kalktı —
    çoklu sağlayıcı formu ancak bundan sonra eklenebilir.

    Üç kapı birlikte çünkü her biri diğerinin kaçırdığını yakalıyor:
      1. ROTA: /api/settings bir kimlik formu, hiçbir alanı yankılanmamalı.
      2. AD: katalogda gizli olarak beyan edilmiş alanlar (başka rotalarda da).
      3. SONEK: kataloğa girmemiş ama adı `_key`/`_token`/`_secret` ile bitenler.

    `ctx` de siliniyor, `input` gibi: pydantic uzunluk hatalarında bağlamda
    değerin kendisi ya da uzunluğu geçebiliyor.

    `app.py` bunu `add_exception_handler(RequestValidationError, …)` ile
    takıyor — dekoratörün birebir karşılığı.
    """
    kimlik_rotasi = request.url.path in CREDENTIAL_ROUTES
    safe = []
    for err in exc.errors():
        err = dict(err)
        if kimlik_rotasi or is_secret_loc(err.get("loc") or ()):
            err.pop("input", None)
            err.pop("ctx", None)
        safe.append(err)
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": safe}))
