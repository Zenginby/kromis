"""Görsel sağlayıcı sevk memuru: model tanımı → o modeli konuşan adaptör.

Bu dosya İKİ şey yapıyor ve üçüncüsünü BİLEREK yapmıyor:
  • `catalog.ImageModel` → adaptör eşlemesi ve çağrının kendisi,
  • zaman aşımı politikası (adet başına ayrı istek atan sağlayıcı için),
  • ve tel formatına HİÇ karışmıyor — o her adaptörün özel işi.

Üçüncüsü tasarımın taşıyıcı kararı: adaptörler ÇÖZÜLMÜŞ PNG BAYTLARI
döndürüyor. Böylece `azure_client.decode_images`'ın koşulsuz `data[].b64_json`
varsayımı Azure'ın özel meselesi olarak kalıyor; Gemini'nin
`candidates[].content.parts[].inlineData` şekli Gemini'nin; ve ileride URL
döndüren bir sağlayıcı (fal, Replicate) kendi `GET`'ini yapıp bayt döndürüyor.
Çağıran taraf aradaki farkı HİÇ öğrenmiyor.

ADAPTÖR SÖZLEŞMESİ — her adaptör modülü şu iki adı dışa veriyor:

    generate(m, prompt, size, quality, n, *, client=None, credentials=None) -> list[bytes]
    edit(m, prompt, images, size, quality, n, *, client=None, credentials=None) -> list[bytes]

`images`: sıralı [(dosya_adı, png_baytları), ...] — ilk görsel ana referans.
Biçimden bağımsız BİLEREK: Azure bunu multipart alanlarına, Gemini base64
`inlineData` bloklarına çeviriyor. `azure_client.build_image_files` bu yüzden
sözleşmeye HİÇ girmiyor.

`client=` / `credentials=` anahtarları KORUNUYOR: bunlar mevcut test koşumu
(tests/test_azure_client_http.py'deki FakeClient) ve her yeni adaptör aynı
dikişi bedavaya alıyor, testleri de bugünkülere benziyor.

Sınıf DEĞİL, fonksiyon modülü: bu depoda hiçbir yerde servis sınıfı yok.

Adaptörler modül düzeyinde STATİK import ediliyor, `importlib` ile DEĞİL.
Sebep: `gpt-image-studio.spec`'in `hiddenimports=[]` değeri PyInstaller'ın
statik analizine dayanıyor ve o dosyanın 50 satırlık yorumu bunu ölçülmüş bir
değişmez sayıyor. Dinamik import o analizden kaçar ve paketlenmiş uygulamada
adaptör bulunamaz.

Bu dosya KÖKTE ve DÜZ — bir `providers/` PAKETİ olamaz. Android'in Chaquopy
kaynak kümesi `include "*.py"` ile kurulu, yani alt paket APK'ya hiç girmez ve
hata yalnız telefonda görünür (bkz. tests/test_android_packaging.py).
"""
from __future__ import annotations

import azure_client as ac
import catalog
import credstore


def _azure_generate(m, prompt, size, quality, n, *, client=None, credentials=None):
    """Azure yolu: `azure_client`'a AYNEN devrediliyor.

    Model tanımı burada DÜŞÜRÜLÜYOR ve bu bilinçli. `azure_client.py` bu adımda
    hiç düzenlenmiyor — `build_payload`'ın ürettiği tam sözlük
    tests/test_azure_client.py'de donmuş durumda ve dosyanın her yorumu Azure'a
    özgü. Yani varsayılan yolun tel üzerindeki baytları DEĞİŞMEMİŞ bir fonksiyon
    üretmeye devam ediyor: "kayıtlı Azure kullanıcısı için sıfır davranış
    değişikliği" güvencesinin somut karşılığı bu.

    KİMLİK BURADA ÇÖZÜLMÜYOR, `credentials=None` aynen geçiliyor. İlk yazımda
    burada `credstore.resolve(...)` vardı ve 104 test birden düştü: rota
    testlerinin tamamı `ac.generate`'i monkeypatch'liyor ve kimliği HİÇ
    yapılandırmıyor — çünkü bugünkü `ac.generate` kimliği kendi İÇİNDE, tembel
    biçimde çözüyor. Erken çözüm o tembelliği bozuyor ve stub'lanmış bir
    çağrının bile gerçek bir `credentials.env` istemesine yol açıyordu.
    Testlerin ölçtüğü şey doğruydu: çözümü öne almak davranış DEĞİŞİKLİĞİ.
    Azure'ın iki dosyalı düşmesi de böylece tek bir yerde kalıyor.

    Yeni adaptörler kendi kimliğini `credstore.resolve(m.credential)` ile
    çözüyor — aynı tembellikle, yani kendi istek fonksiyonlarının içinde.
    """
    return ac.generate(prompt, size, quality, n, client=client, credentials=credentials)


def _azure_edit(m, prompt, images, size, quality, n, *, client=None, credentials=None):
    return ac.edit(prompt, images, size, quality, n, client=client, credentials=credentials)


# provider → (generate, edit). Yeni bir adaptör buraya girmediği sürece
# kataloğa eklenen model çalışma anında "bilinmeyen sağlayıcı" hatası verir —
# sessizce Azure'a düşmez. Mandal: tests/test_providers.py.
_ADAPTERS: dict[str, tuple] = {
    "azure": (_azure_generate, _azure_edit),
}


def adapter_ids() -> frozenset[str]:
    return frozenset(_ADAPTERS)


def _resolve(model_id: str) -> catalog.ImageModel:
    m = catalog.image_model(model_id)
    if m is None:
        # Kullanıcıya gösterilebilir Türkçe hata: bayat bir istemci artık var
        # olmayan bir modeli isteyebilir ve bunun cevabı ham 500 olmamalı.
        raise ac.ImageError(f"Bilinmeyen model: {model_id}")
    if m.provider not in _ADAPTERS:
        raise ac.ImageError(
            f"{m.label} için sağlayıcı adaptörü yok ({m.provider}).")
    return m


def read_timeout_for(m: catalog.ImageModel, n: int) -> float:
    """TEK isteğin okuma süresi.

    `azure_client.read_timeout_for`'un formülü (180 + 120·(n-1)) açık bir
    varsayıma dayanıyor ve kendi yorumunda yazılı: `build_payload` `n`'i gövdeye
    koyuyor, yani 4 görsel TEK POST'ta üretiliyor. Adet başına ayrı istek atan
    bir sağlayıcıda o varsayım YANLIŞ — her istek bir görsel döndürüyor, süre
    adetle büyümüyor. Büyüyen şey döngünün TOPLAMI (bkz. total_budget).

    Karışsa n=4'te her isteğe 540 saniye verilirdi: 36 dakikalık en kötü hâl.
    """
    if m.poll_timeout:
        return m.poll_timeout
    tek_istekteki = n if m.images_per_request > 1 else 1
    return ac.read_timeout_for(tek_istekteki)


def total_budget(m: catalog.ImageModel, n: int) -> float:
    """Döngünün duvar saati tavanı — kaç istek atılacağı ile ölçeklenen taraf."""
    tur = 1 if m.images_per_request > 1 else n
    return read_timeout_for(m, n) * tur


def detail_of(body: dict | None) -> str:
    """Sağlayıcı hata gövdesinden kullanıcıya gösterilebilir açıklama.

    ŞEKİL paylaşılıyor, MESAJ paylaşılmıyor: `{"error": {"message": …}}`
    biçimini Azure, OpenAI, Gemini ve Anthropic'in dördü de kullanıyor, ama
    Türkçe metinler sağlayıcıya özgü kalmak zorunda (`chat_client.map_error`'ın
    404 metni Azure AI Foundry'nin dağıtım alanından söz ediyor — o metni
    Gemini'ye göstermek kullanıcıyı olmayan bir forma yönlendirir).
    """
    if not isinstance(body, dict):
        return ""
    err = body.get("error")
    if isinstance(err, dict):
        return str(err.get("message", ""))
    if isinstance(err, str):
        return err
    return ""


def is_configured(model_id: str) -> bool:
    """Modelin kimliği girilmiş mi. Katalogda olmayan model için False."""
    m = catalog.image_model(model_id)
    return bool(m) and credstore.is_configured(m.credential)


def generate(model_id: str, prompt: str, size: str, quality: str, n: int,
             *, client=None, credentials=None) -> list[bytes]:
    m = _resolve(model_id)
    return _ADAPTERS[m.provider][0](m, prompt, size, quality, n,
                                    client=client, credentials=credentials)


def edit(model_id: str, prompt: str, images, size: str, quality: str, n: int,
         *, client=None, credentials=None) -> list[bytes]:
    m = _resolve(model_id)
    if not m.supports_edit:
        # Katalog kapısı rotada da var (app._check_edit_form); buradaki ikinci
        # kapı `providers.edit`'in başka bir çağıranı olduğu gün de korur.
        raise ac.ImageError(f"{m.label} referans görselle çalışmıyor.")
    return _ADAPTERS[m.provider][1](m, prompt, images, size, quality, n,
                                    client=client, credentials=credentials)
