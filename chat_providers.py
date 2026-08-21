"""Sohbet sağlayıcı sevk memuru — `providers.py`'nin sohbet tarafındaki eşi.

Görsel tarafında bu ayrım v0.6'da kurulmuştu ve gerekçesi orada yazılı: model
tanımı → o modeli konuşan adaptör, tel formatına HİÇ karışmadan. Sohbet tarafı
o güne kadar TEK sağlayıcılıydı (Azure dağıtımı), yani sevk memuruna ihtiyaç
yoktu; `/api/chat` doğrudan `chat_client.complete`'i çağırıyordu.

ADAPTÖR SÖZLEŞMESİ — her sohbet adaptörü şu tek adı dışa veriyor:

    complete(m, messages, *, client=None, credentials=None, instructions=None)
        -> {"content": str, "finish_reason": str}

Dönüş şekli `chat_client.complete`'in bugünkü şeklinin AYNISI: `/api/chat`'in
yanıtı doğrudan bu sözlük ve arayüz iki alanı da okuyor (`finish_reason ==
"length"` uyarıyı yazıyor). Sözleşmeyi değiştirmek rotayı ve chat.js'i birden
değiştirmek olurdu.

`client=` / `credentials=` anahtarları KORUNUYOR: mevcut test koşumu
(tests/test_chat_client.py'deki FakeClient) bu dikişe dayanıyor ve her yeni
adaptör onu bedavaya alıyor.

AZURE YOLU BAYT BAYT DEĞİŞMİYOR. `_azure_complete` model tanımını DÜŞÜRÜP
`chat_client.complete`'e aynen devrediyor: o dosya dağıtım adını kendi içinde,
tembel biçimde çözüyor (`load_credentials`) ve rota testlerinin tamamı
`appmod.cc.complete`'i monkeypatch ediyor. Kimliği burada erken çözmek, tam
olarak `providers._azure_generate`'in docstring'inde ölçülmüş kırılmayı
tekrarlardı: stub'lanmış bir çağrı bile gerçek bir `credentials.env` isterdi.

Adaptörler modül düzeyinde STATİK import ediliyor, `importlib` ile DEĞİL
(`gpt-image-studio.spec`'in `hiddenimports=[]` değeri PyInstaller'ın statik
analizine dayanıyor). Döngü de yok: `openai_chat` bu modülü İMPORT ETMİYOR.

Dosya KÖKTE ve DÜZ — Chaquopy kaynak kümesi `include "*.py"` (bkz.
tests/test_android_packaging.py).
"""
from __future__ import annotations

import azure_client as ac
import catalog
import chat_client as cc
import credstore
import openai_chat


def _azure_complete(m, messages, *, client=None, credentials=None,
                    instructions=None):
    """Azure yolu: `chat_client`'a AYNEN devrediliyor (model tanımı düşüyor)."""
    return cc.complete(messages, client=client, credentials=credentials,
                       instructions=instructions)


def _openai_complete(m, messages, *, client=None, credentials=None,
                     instructions=None):
    """`openai_chat.complete`'e devrediyor — ama ADI ÇAĞRI ANINDA çözerek.

    Fonksiyon nesnesini tabloya doğrudan yazmak import anında bağlardı ve
    `monkeypatch.setattr(openai_chat, "complete", …)` görünmez olurdu:
    conftest.py'nin başındaki uyarının ("modül niteliğini yamala, adı içe alma")
    tam olarak ölçtüğü kırılma. Rota testlerinin tamamı bu dikişe dayanıyor.
    """
    return openai_chat.complete(m, messages, client=client,
                                credentials=credentials,
                                instructions=instructions)


# provider → adaptör. Kataloğa eklenen bir sağlayıcı buraya girmediği sürece
# çalışma anında "adaptör yok" hatası veriyor — sessizce Azure'a DÜŞMÜYOR.
# Mandal: tests/test_chat_providers.py.
#
# `openai` ve `gemini` AYNI adaptörü paylaşıyor ve bu bir kısayol değil ölçülmüş
# bir olgu: Gemini'nin OpenAI-uyumlu ucu aynı gövdeyi, aynı başlığı ve aynı
# yanıt şeklini kullanıyor. Ayrışan iki şey (yol ve hata metnindeki ad)
# KATALOGDAN okunuyor (`endpoint_path`, `Credential.label`), yani üçüncü bir
# uyumlu sağlayıcı tek katalog girdisiyle ekleniyor.
_ADAPTERS: dict[str, object] = {
    "azure": _azure_complete,
    "openai": _openai_complete,
    "gemini": _openai_complete,
}


def adapter_ids() -> frozenset[str]:
    return frozenset(_ADAPTERS)


def wire_model_of(m: catalog.ChatModel, env_path: str | None = None) -> str:
    """Sağlayıcıya GİDEN ad. Azure'da ortamdan, ötekilerde katalogdan.

    Katalog yaprak olduğu için ortama BAKAMIYOR (dosya G/Ç yok); okuma bu
    yüzden burada. `credstore.chat_is_configured` aynı env değerine bakıyor ama
    yalnız "boş mu" diye — iki taraf ayrışırsa arayüz modeli kurulu gösterir ve
    ilk mesaj 404 döner, o yüzden ikisi de TEK env adını (`wire_from_env`)
    kataloğun kendisinden okuyor.
    """
    if m.wire_from_env:
        return ac.read_env_values(env_path).get(m.wire_from_env, "").strip()
    return m.wire_model


def _resolve(model_id: str) -> catalog.ChatModel:
    m = catalog.chat_model(model_id)
    if m is None:
        # Bayat bir istemci artık var olmayan bir modeli isteyebilir ve bunun
        # cevabı ham 500 olmamalı: tür `cc.ChatError`, yani rota onu 502'ye ve
        # Türkçe bir gövdeye çeviriyor.
        raise cc.ChatError(f"Bilinmeyen sohbet modeli: {model_id}")
    if m.provider not in _ADAPTERS:
        raise cc.ChatError(
            f"{m.label} için sohbet adaptörü yok ({m.provider}).")
    return m


def is_configured(model_id: str, env_path: str | None = None) -> bool:
    """Modelin kimliği (ve gerekiyorsa dağıtım adı) girilmiş mi."""
    m = catalog.chat_model(model_id)
    return bool(m) and credstore.chat_is_configured(m, env_path)


def complete(model_id: str, messages: list[dict], *, client=None,
             credentials=None, instructions: str | None = None) -> dict:
    m = _resolve(model_id)
    return _ADAPTERS[m.provider](m, messages, client=client,
                                 credentials=credentials,
                                 instructions=instructions)
