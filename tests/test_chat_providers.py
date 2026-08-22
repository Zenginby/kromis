"""chat_providers: sohbet sevk memuru ve adaptör kayıt mandalı.

tests/test_providers.py'nin sohbet tarafındaki eşi. En değerli iddiası
"AZURE YOLU BAYT BAYT DEĞİŞMEDİ": sevk memuru araya girdi ama o yol hâlâ
`chat_client.complete`'e model tanımı DÜŞÜRÜLMÜŞ olarak gidiyor. Ayrışırsa
kayıtlı Azure kullanıcısının yönetmeni sessizce başka bir gövde gönderirdi.
"""
import ast
import pathlib

import pytest

import catalog
import chat_client as cc
import chat_providers
import openai_chat

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_katalogdaki_her_sohbet_saglayicisinin_adaptoru_kayitli():
    """Kataloğa sohbet modeli eklemek yetmiyor; adaptörü de kaydedilmiş olmalı.

    Kayıtlı olmayan sağlayıcı SESSİZCE Azure'a DÜŞMÜYOR (Türkçe hata veriyor) —
    ama bu testin işi o hatanın hiç oluşmaması. Sessiz düşme özellikle kötü
    olurdu: kullanıcı Gemini seçip Azure'a fatura keser.
    """
    for m in catalog.CHAT_MODELS:
        assert m.provider in chat_providers.adapter_ids(), (
            f"{m.id}: `{m.provider}` sohbet adaptörü _ADAPTERS'ta yok")


def test_adaptorler_STATIK_import_ediliyor():
    """`importlib` PyInstaller'ın statik analizinden KAÇAR ve hata yalnız
    paketlenmiş .app/.apk içinde görünür (providers.py'deki aynı mandal)."""
    tree = ast.parse((REPO / "chat_providers.py").read_text(encoding="utf-8"))
    ice_alinanlar = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            ice_alinanlar.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            ice_alinanlar.add(node.module.split(".")[0])
        elif isinstance(node, ast.Attribute) and node.attr == "import_module":
            pytest.fail("chat_providers.py `import_module` çağırıyor")
    assert "importlib" not in ice_alinanlar


def test_AZURE_yolu_chat_client_e_model_DUSURULEREK_gidiyor(monkeypatch):
    """Kayıtlı Azure kullanıcısı için sıfır davranış değişikliği güvencesi.

    `chat_client.complete` dağıtım adını KENDİ İÇİNDE, tembel biçimde çözüyor
    (`load_credentials`). Sevk memuru kimliği erken çözseydi rota testlerinin
    tamamı düşerdi: hepsi `appmod.cc.complete`'i yamalıyor ve hiçbiri gerçek bir
    `credentials.env` yazmıyor — `providers._azure_generate`'in docstring'inde
    ölçülmüş kırılmanın aynısı.
    """
    cagrilar = []

    def _fake(messages, **kw):
        cagrilar.append((messages, kw))
        return {"content": "pong", "finish_reason": "stop"}

    monkeypatch.setattr(cc, "complete", _fake)
    out = chat_providers.complete(catalog.DEFAULT_CHAT_MODEL, [{"role": "user"}])

    assert out["content"] == "pong"
    assert len(cagrilar) == 1
    mesajlar, kw = cagrilar[0]
    assert mesajlar == [{"role": "user"}]
    # Model tanımı DÜŞÜYOR: chat_client onu hiç görmüyor.
    assert set(kw) == {"client", "credentials", "instructions"}


@pytest.mark.parametrize("model_id", ["openai-gpt-5.6-terra", "gemini-3.7-flash"])
def test_UYUMLU_saglayicilar_openai_chat_e_MODEL_TANIMIYLA_gidiyor(monkeypatch, model_id):
    """İki sağlayıcı TEK adaptörü paylaşıyor; ayrışan tek şey model tanımı.

    Yama `openai_chat` MODÜL NİTELİĞİNE yapılıyor ve görülmesi tabloya
    fonksiyon nesnesinin yazılmadığını da ölçüyor (bkz. `_openai_complete`'in
    docstring'i): nesne import anında bağlanırsa bu test kırmızıya düşer.
    """
    gorulen = []
    monkeypatch.setattr(openai_chat, "complete",
                        lambda m, messages, **kw: gorulen.append(m) or {"content": "x"})
    chat_providers.complete(model_id, [{"role": "user"}])

    assert [m.id for m in gorulen] == [model_id]


def test_BILINMEYEN_model_turkce_ChatError_veriyor():
    """Bayat bir istemci katalogdan kalkmış bir modeli isteyebilir; cevabı ham
    500 olmamalı — rota `cc.ChatError`i 502'ye ve Türkçe gövdeye çeviriyor."""
    with pytest.raises(cc.ChatError) as e:
        chat_providers.complete("yok-boyle-model", [{"role": "user"}])
    assert "Bilinmeyen sohbet modeli" in str(e.value)


def test_ADAPTORSUZ_saglayici_SESSIZCE_azureye_dusmuyor(monkeypatch):
    """Kayıt tablosundan bir sağlayıcı düşerse hata YÜKSEK SESLE geliyor."""
    monkeypatch.setattr(chat_providers, "_ADAPTERS", {"azure": lambda *a, **k: None})
    with pytest.raises(cc.ChatError) as e:
        chat_providers.complete("gemini-3.7-flash", [{"role": "user"}])
    assert "sohbet adaptörü yok" in str(e.value)


# ── Ad çözümü ──────────────────────────────────────────────────────────


def test_AZURE_nun_adi_ORTAMDAN_okunuyor(tmp_path):
    env = tmp_path / "credentials.env"
    env.write_text("AZURE_CHAT_DEPLOYMENT=  gpt-5.6-luna  \n", encoding="utf-8")
    m = catalog.chat_model(catalog.DEFAULT_CHAT_MODEL)

    # Kırpma ölçülüyor: kullanıcı kutuya boşluklu yapıştırıyor ve `credstore`
    # "boş mu" sorusunu da kırparak soruyor — ikisi ayrışırsa arayüz modeli
    # kurulu gösterir, istek 404 döner.
    assert chat_providers.wire_model_of(m, str(env)) == "gpt-5.6-luna"


def test_OTEKILERIN_adi_KATALOGDAN_geliyor(tmp_path):
    """Ortamda hiçbir şey olmasa da ad hazır: aranan bir env değişkeninin
    yokluğu OpenAI/Gemini'yi sessizce kapatırdı."""
    env = tmp_path / "credentials.env"
    env.write_text("", encoding="utf-8")
    m = catalog.chat_model("gemini-3.7-flash")
    assert chat_providers.wire_model_of(m, str(env)) == "gemini-3.7-flash"


# ── Kurulu mu ──────────────────────────────────────────────────────────


def test_AZURE_modeli_DAGITIM_ADI_olmadan_kurulu_SAYILMIYOR(tmp_path):
    """Kimliği tam, dağıtımı boş: istek 404 döner. Arayüz "kurulu" gösterirse
    kullanıcı yönetmeni açar, ilk mesaj 502 olur ve sebebi görünmez."""
    env = tmp_path / "credentials.env"
    env.write_text("AZURE_IMAGE_API_KEY=K\n"
                   "AZURE_IMAGE_BASE_URL=https://ep/openai/v1/\n", encoding="utf-8")
    assert chat_providers.is_configured(catalog.DEFAULT_CHAT_MODEL, str(env)) is False

    env.write_text("AZURE_IMAGE_API_KEY=K\n"
                   "AZURE_IMAGE_BASE_URL=https://ep/openai/v1/\n"
                   "AZURE_CHAT_DEPLOYMENT=gpt-5.6-luna\n", encoding="utf-8")
    assert chat_providers.is_configured(catalog.DEFAULT_CHAT_MODEL, str(env)) is True


def test_UYUMLU_modeller_YALNIZ_anahtar_istiyor(tmp_path):
    env = tmp_path / "credentials.env"
    env.write_text("GEMINI_API_KEY=AIza\n", encoding="utf-8")
    assert chat_providers.is_configured("gemini-3.7-flash", str(env)) is True
    assert chat_providers.is_configured("openai-gpt-5.6-terra", str(env)) is False


def test_KATALOGDA_OLMAYAN_model_kurulu_sayilmiyor():
    assert chat_providers.is_configured("yok-boyle-model") is False
