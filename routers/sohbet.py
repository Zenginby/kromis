# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Prompt Yönetmeni: sohbet tamamlama ve kayıtlı oturumlar."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import catalog
import chat_client as cc
import chat_prompt
import chat_providers
import i18n
from models import MAX_CHAT_TITLE_CHARS, ChatRequest, ChatSaveRequest, wire_messages
from services import depo_sohbet, depo_tercih, dil, kimlik, modeller, zaman
from services.db import OTURUM
from services.tablolar import Kullanici

router = APIRouter()

# Sohbetler ve tercihler DB'de (Faz 1 / 6): bu dosyanın hiçbir rotası dizin
# okumuyor, `ayar.ayarlar` almıyor — kapı doğrudan `kimlik.aktif_kullanici`,
# satırlar isteğin `Session`ında (`OTURUM`, commit `db.oturum`da).
# `chat_store`/`prefs` buradan artık OKUNMAZ (bekçisi tests/test_galeri_db.py).


@router.post("/api/chat")
def chat(req: ChatRequest, db: Session = OTURUM,
         kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Prompt Yönetmeni: kullanıcının dilinde sohbet → İngilizce prompt.

    SENKRON `def` (bilinçli): httpx çağrısı bloklayıcı, Starlette bunu kendi
    threadpool'unda koşturur ve olay döngüsü — yani pencere — donmaz;
    `/api/generate`'in aynısı.

    BU ROTA diske hiçbir şey yazmaz ve v1.15'ten sonra da yazmıyor. v1.13'ün
    "karar 4"ü iptal edilmedi, KAPSAMI daraldı: sohbetler artık saklanabiliyor
    ama yazan tek yol kullanıcının kendi başlattığı `/api/chats` (bkz.
    chat_store.py). Modelden dönen her yanıtı sessizce diske almak ile
    kullanıcının "bunu sakla" demesi aynı şey değil; ayrımı
    tests/test_chat_route.py mekanik olarak koruyor.

    Tel mesajlarını `models.wire_messages` kuruyor ve o bir SÜZGEÇ DEĞİL
    ÇEVİRMEN: `display` gibi arayüz alanlarını allowlist'le dışarıda tutmaya
    devam ediyor (çıplak `model_dump()` onları tele koyar ve istek 400 döner),
    ama `result` kayıtlarını artık DÜŞÜRMÜYOR — kısa bir nota çeviriyor, çünkü
    yönetmenin ne ürettiğini bilmesi gerekiyor.

    `chat_client.build_payload`'ın kendi rol/alan süzgeci YERİNDE DURUYOR ve
    gövdesine dokunulmadı: o telin gerçek sınırı, yani son savunma. Çevirmen
    bir gün yeni bir rolü çevirmeyi unutursa istek yine 400 almasın diye.

    ÇAĞRI ARTIK SEVK MEMURUNDAN geçiyor (`chat_providers`), doğrudan
    `chat_client`'tan değil: yönetmen üç sağlayıcı konuşabiliyor ve hangisinin
    konuşulacağı `req.model`'da. Azure yolunun tel üzerindeki baytları
    DEĞİŞMEDİ — sevk memuru model tanımını düşürüp `cc.complete`'e aynen
    devrediyor (bkz. chat_providers._azure_complete).
    """
    try:
        # MODEL İSTEKTEN, tercihlerden DEĞİL. `/api/generate`'in aynı duruşu:
        # seçim ekranda yaşıyor ve tel üzerinde geliyor. `prefs.json`'ı ikinci
        # bir kaynak yapmak, kullanıcının bu turda seçtiği modelle sunucunun
        # kullandığı modelin ayrışmasına kapı açardı (tercih yazımı ağ üstünden
        # ve başarısız olabiliyor — bkz. core.js savePref).
        #
        # `or DEFAULT_CHAT_MODEL`: alanı hiç göndermeyen bayat bir istemci
        # bugünkü modele gidiyor. Geçerlilik `ChatRequest`'te ölçüldü, burada
        # ikinci bir kapı yok — `chat_providers._resolve` yine de bilinmeyen
        # id'yi Türkçe bir 502'ye çeviriyor (bayat istemci + katalogdan kalkmış
        # model).
        # `instructions` ARTIK ROTADAN geçiyor. Adaptörler onu zaten
        # destekliyordu (`complete(..., instructions=None)`), yani imza
        # değişmedi — değişen tek şey, `None` bırakıldığında adaptörün diskten
        # okuduğu personanın yerine burada KURULMUŞ olanın gelmesi.
        #
        # `ValueError` → `cc.ChatError`: talimat dosyası bulunamadığında
        # kullanıcının okuduğu metin, `chat_client`'ın kendi dalında ürettiğiyle
        # AYNI kalmalı. İki yerde iki Türkçe cümle olsaydı aynı kusur, çağrının
        # hangi yoldan gittiğine göre iki farklı hata okuturdu.
        # Bağlam TOPLAMA `try`nin DIŞINDA: `except ValueError` yalnız talimat
        # dosyasının hatasını yakalamalı; bağlamdan (tercih satırı, katalog)
        # gelen bir hata "talimat yüklenemedi" kılığına girmesin. (Bozuk
        # `prefs.json` senaryosu Faz 1 / 6'da kalktı — tercih DB'de.)
        baglam = modeller.director_context(db, kullanici.id)
        try:
            instructions = chat_prompt.build_system(**baglam)
        except ValueError as e:
            raise cc.ChatError(i18n.t("err.persona_load_failed", None, hata=e))
        return chat_providers.complete(
            req.model or catalog.DEFAULT_CHAT_MODEL,
            wire_messages(req.messages),
            instructions=instructions)
    except cc.ChatError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Kayıtlı oturumlar ───────────────────────────────────────────────────
# Kalıcılık SUNUCUDA, istemcide değil: `desktop.py` pencereyi private mode'da
# açıyor (pywebview varsayılanı) ve orada localStorage her kapanışta silinir —
# paketlenmiş .app'te geçmiş sessizce buharlaşırdı.


def _guard_autosave(title: str | None, db: Session, kullanici_id: uuid.UUID) -> None:
    """Otomatik yazımı anahtar kapalıyken reddeder (409). Karar D1, güvence (c).

    Ayrımı taşıyan işaret zaten elde: **otomatik kaydın verecek bir ADI yok.**
    Kullanıcı bir oturumu kendisi kaydediyor ya da yeniden adlandırıyorsa istekte
    başlık VAR; tur sonunda kendi kendine büyüyen yazımda YOK. Yani "başlıksız
    yazım = otomatik yazım" ve kapalı anahtarda durduruluyor — adlandırılmış yazım
    her koşulda çalışıyor, yani "kapatınca bugünkü davranış" (v1.15) gerçekten
    sağlanıyor.

    İsteğe "bu otomatik" diye bir bayrak KONMADI: bayat/hatalı bir istemci onu
    yanlış gönderdiğinde anahtar sessizce delinirdi. Başlığın yokluğu ise
    uydurulamaz bir işaret.

    409, 422 değil: gövde geçerli, reddin sebebi kullanıcının AYARI. 403 de değil —
    yerel tek kullanıcılı bir uygulamada yetkilendirme çağrışımı yanlış olurdu.
    """
    if title is None and not depo_tercih.oku(db, kullanici_id)["autosave_sessions"]:
        raise HTTPException(status_code=409,
                            detail=i18n.t("err.autosave_off", dil.aktif()))


def _auto_title(messages: list[dict]) -> str:
    """Otomatik kaydedilen oturumun adı: ilk KULLANICI turunun ilk satırı.

    `display` varsa o kazanıyor: çip turunda modele giden cümle ile ekranda
    görünen etiket farklı (v1.16) ve panelde kullanıcının GÖRDÜĞÜ metin durmalı.

    Tek satır + sıkıştırılmış boşluk: kenar paneli tek satır çiziyor, gövdedeki
    satır sonu oraya boşluk olarak sızardı. Sınır `MAX_CHAT_TITLE_CHARS` (kayıt
    kapısıyla aynı sayı) ve kesme işareti görünür — kırpıldığı belli olsun.

    Sonuç kaydıyla başlayan döküm (Görsel modunda üretimle açılan oturum) için
    yedek ad var: kullanıcı mesajı olmayabilir, ama adsız oturum olamaz.
    """
    for m in messages:
        if m.get("role") != "user":
            continue
        text = " ".join((m.get("display") or m.get("content") or "").split("\n")[0].split())
        if text:
            return (text if len(text) <= MAX_CHAT_TITLE_CHARS
                    else text[:MAX_CHAT_TITLE_CHARS - 1] + "…")
    return i18n.t("chat.untitled_session", dil.aktif())


@router.get("/api/chats")
def list_chats_route(db: Session = OTURUM,
                     kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Kenar panelinin listesi: başlıklar, gövdeler DEĞİL (bkz. depo_sohbet)."""
    return {"chats": depo_sohbet.listele(db, kullanici.id)}


@router.get("/api/chats/{chat_id}")
def get_chat_route(chat_id: str, db: Session = OTURUM,
                   kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    rec = depo_sohbet.bul(db, kullanici.id, os.path.basename(chat_id))
    if rec is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.chat_missing", dil.aktif()))
    return {"chat": rec}


@router.post("/api/chats")
def create_chat_route(req: ChatSaveRequest, db: Session = OTURUM,
                      kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Yeni kayıt. Gövde ZORUNLU, başlık DEĞİL (v2.0: otomatik kayıt).

    Başlık gelmediyse ilk mesajdan türetiliyor (`_auto_title`) — kural aynı
    kalıyor ("adsız sohbet olmaz"), onu sağlayan taraf değişti: otomatik kaydın
    ad verecek bir kullanıcı eylemi yok. BOŞ gelen başlık ise hâlâ 422; "alan hiç
    gelmedi" ile "boş geldi" ayrımı `chat_deployment`'taki geleneğin aynısı.

    Kaydetmede allowlist DEĞİL `exclude_none` var — ayrım bilinçli: tamamlama
    yolunun sınırı Azure'ın şeması, kaydetmenin sınırı ise kayıttaki biçim.
    `display` kayda YAZILMAK ZORUNDA (pil yeniden açılışta sağ kalsın), ama
    `display: null` satırları eski sohbetlerin gövdesini sebepsiz büyütür.
    """
    if req.title is not None and not req.title.strip():
        raise HTTPException(status_code=422, detail=i18n.t("err.chat_title_empty", dil.aktif()))
    if not req.messages:
        raise HTTPException(status_code=422, detail=i18n.t("err.nothing_to_save", dil.aktif()))
    messages = [m.model_dump(exclude_none=True) for m in req.messages]
    _guard_autosave(req.title, db, kullanici.id)
    title = req.title.strip() if req.title else _auto_title(messages)
    return {"chat": depo_sohbet.olustur(db, kullanici.id, title, messages, now=zaman.an())}


@router.delete("/api/chats")
def delete_all_chats_route(db: Session = OTURUM,
                           kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Tüm oturumları siler (karar D1'in güvence b'si: "tümünü sil").

    Boş depoda 404 DEĞİL: tek kayıt silmede 404'ün anlamı "hangi kayıt?" sorusunun
    cevapsız kalması; burada soru yok, istenen durum zaten sağlanmış.
    """
    return {"deleted": depo_sohbet.hepsini_sil(db, kullanici.id)}


@router.put("/api/chats/{chat_id}")
def update_chat_route(chat_id: str, req: ChatSaveRequest, db: Session = OTURUM,
                      kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Gövdeyi ve/veya başlığı değiştirir (tur sonu kaydı + yeniden adlandırma).

    Başlık BOŞ dizeyle gelirse reddedilir: adsız bir sohbet kenar panelinde
    tıklanacak hiçbir şey bırakmaz.
    """
    title = None if req.title is None else req.title.strip()
    if title is not None and not title:
        raise HTTPException(status_code=422, detail=i18n.t("err.chat_title_empty", dil.aktif()))
    # Gövde-yalnız `PUT` = tur sonu otomatik yazımı (bkz. _guard_autosave).
    if req.messages is not None:
        _guard_autosave(req.title, db, kullanici.id)
    messages = (None if req.messages is None
                else [m.model_dump(exclude_none=True) for m in req.messages])
    rec = depo_sohbet.guncelle(db, kullanici.id, os.path.basename(chat_id),
                               messages=messages, title=title, now=zaman.an())
    if rec is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.chat_missing", dil.aktif()))
    return {"chat": rec}


@router.delete("/api/chats/{chat_id}")
def delete_chat_route(chat_id: str, db: Session = OTURUM,
                      kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    cid = os.path.basename(chat_id)
    if not depo_sohbet.sil(db, kullanici.id, cid):
        raise HTTPException(status_code=404, detail=i18n.t("err.chat_missing", dil.aktif()))
    return {"deleted": cid}
