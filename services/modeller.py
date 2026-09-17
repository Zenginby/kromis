# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Model kataloğunun arayüze ve Yönetmen'e giden hâlleri.

İki okuyan var — Ayarlar (`settings_payload`) ve Prompt Yönetmeni
(`director_context`) — ve ikisi de "hangi model kullanıcıya GÖRÜNÜR" sorusunu
`model_available` üzerinden, tek yerden soruyor. Ayrı router'larda dursalar
bu soru iki yerde iki cevap üretirdi.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

import azure_client as ac
import catalog
import credstore
import etiket
import i18n
import version
from services import depo_tercih


def model_available(configured: bool, plan: str) -> bool:
    """Bu model kullanıcıya GÖRÜNÜYOR mu — arayüzün sorduğu TEK soru.

    Görünmeme sebebi bugün tek: anahtar kayıtlı değil. Kredi/üyelik sistemi
    geldiğinde ikincisi ekleniyor — "kullanıcının planı bu modeli kapsamıyor" —
    ve o gün DEĞİŞECEK YER BURASI, istemci değil. Filtrenin istemcide olduğu
    bir dünyada iki sebebi ayrı ayrı sormak gerekirdi ve "hangi modeller
    görünür" sorusunun iki cevabı doğardı; `static/core.js secilebilirler`in
    var olma sebebi tam olarak o ikiliği önlemek.

    `plan` BUGÜN OKUNMUYOR ve bu bilinçli: parametre imzada duruyor çünkü
    kancanın YERİ burası, ama plan tablosu (kim hangi abonelikte) henüz yok —
    kullanıcı modeli, kimlik doğrulama ve bakiye SaaS dönüşümüne bağlı
    (docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md).
    Uydurma bir eşleştirme yazmak, olmayan bir gerçeği kodlamak olurdu.
    """
    return configured


def provider_logo_url(provider: str) -> str | None:
    """Sağlayıcı işaretinin ADRESİ — katalogdaki dosya adı + sürüm damgası.

    `?v=` cache-buster'ı `index()`in desenini tekrarlıyor ve gerekçesi de aynı:
    işaretin çizimi bir gün değişirse kullanıcının tarayıcısı eski dosyayı
    sunmasın. Adresi SUNUCU kuruyor, istemci değil — `settings.js`in sürüm
    alanını okuyup ikinci bir yerde dize birleştirmesi, aynı bilginin iki
    kopyası olurdu (core.js ile settings.js arasında da üst düzey ad çakışması
    üretirdi, bkz. tests/test_id_contract.py).

    Tanımsız sağlayıcıda None: katalogdaki `provider_logo`'nun sessiz yolu
    burada da korunuyor, istemci `logo` boşsa işareti hiç çizmiyor.
    """
    ad = catalog.provider_logo(provider)
    return f"/static/img/providers/{ad}?v={version.APP_VERSION}" if ad else None


def model_payload(m: catalog.ImageModel, cfg: dict, kisa: dict) -> dict:
    """Bir görsel/video modelinin arayüze giden hâli.

    ÇIKARILDI, kopyalanmadı: `image_models` ve `video_models` listelerinin
    ikisi de bu sözlüğü kuruyor ve elle iki kez yazmak, birine alan ekleyip
    ötekini unutmanın kapısı olurdu — `catalog.ASPECT_RATIOS`in paylaşılma
    gerekçesinin aynısı. Bugün ölçülebilir sonucu şu: `requires_plan` ya da
    `logo` bir gün değişirse iki şerit birlikte değişiyor.

    Jetonlar ETİKETLERİYLE gönderiliyor, çıplak dize değil: arayüz `<option>`
    listelerini bunlardan kuruyor ve etiketi istemcide tutmak `SIZE_RATIO`'nun
    bayatlayan aynası olurdu. `ratio` de sunucudan geliyor çünkü Gemini'nin
    jetonları `WxH` biçiminde DEĞİL — istemci ayrıştırma yapmamalı.
    """
    return {
        "id": m.id,
        "label": etiket.label_of(m),
        # ŞERİDİN adı ayrı bir alan: `label` hata metinlerinin ve
        # `#model-note`un okuduğu TAM ad ve orada marka ayırt edici
        # kalıyor (katalogda iki `gpt-image-2` var).
        "short_label": kisa[m.id],
        "provider": m.provider,
        "sizes": [{"value": s, "label": catalog.geometry_of(s)[0],
                   "ratio": catalog.geometry_of(s)[1]} for s in m.sizes],
        "qualities": [{"value": q, "label": etiket.quality_label(q)}
                      for q in m.qualities],
        "quality_hidden": m.quality_hidden,
        # SÜRE EKSENİ. Görsel modellerinde boş liste + 0, yani arayüz için
        # "bu knob yok" — `quality_hidden`ın kurulmuş kalıbının aynısı, tek
        # farkı bayrak yerine LİSTENİN BOŞLUĞUNUN işaret olması (boş bir
        # eksen için ayrı bir `duration_hidden` bayrağı ikinci bir gerçek
        # kaynağı olurdu).
        "durations": [{"value": d, "label": etiket.duration_label(d)}
                      for d in m.durations],
        "default_duration": catalog.default_duration_of(m),
        "default_size": catalog.default_size_of(m),
        "default_quality": catalog.default_quality_of(m),
        "max_n": m.max_n,
        "supports_edit": m.supports_edit,
        "max_refs": m.max_refs,
        # SON KARE yeteneği AYRI bir anahtar, `max_refs`in bir değeri değil:
        # arayüz "bitiş görseli yuvasını çizeyim mi" sorusunu buradan soruyor
        # ve sayıdan türetmek, ikinci referans ile son kareyi aynı sayının
        # arkasına saklamak olurdu (gerekçenin uzunu katalogda).
        "supports_last_frame": m.supports_last_frame,
        # Video modellerinde SANİYE BAŞINA (bkz. catalog.ImageModel.credits).
        # Arayüz farkı `durations`ın boş olup olmamasından biliyor ve süreyle
        # çarpıyor — ikinci bir birim alanı göndermek, aynı bilgiyi iki
        # yoldan taşımak olurdu.
        "credits": m.credits,
        "credits_by_quality": dict(m.credits_by_quality),
        "note": i18n.t(m.note) if m.note else None,
        # Sağlayıcı işaretinin adresi (yoksa None). Şerit yalnız SEÇİLİ
        # modelin işaretini çiziyor: native <option> görsel taşımıyor
        # (bkz. core.js renderModelOptions).
        "logo": provider_logo_url(m.provider),
        # TEK türetilmiş alan: modelin anahtarı GİRİLMİŞ mi. Arayüzün
        # "#go kilitli mi" kararı ve "anahtar gerekli" etiketi bundan geliyor.
        "configured": cfg.get(m.credential, False),
        # GÖRÜNÜRLÜK kararı — arayüzün filtresi YALNIZ bunu okuyor.
        # Bugün `configured` ile birebir aynı; ayrımın gerekçesi
        # model_available'da yazılı. `configured` KALIYOR çünkü MESAJ ondan
        # geliyor: "anahtar yok" ile "planın kapsamıyor" aynı cümle değil.
        "available": model_available(cfg.get(m.credential, False), m.plan),
        # Bugün her modelde "free". Arayüz bir gün "Pro" rozetini bundan
        # çizecek; alan şimdiden akıyor ki o gün şema değişikliği gerekmesin.
        "requires_plan": m.plan,
    }


def settings_payload() -> dict:
    """Kimlik DURUMU + hangi modeller var + hangileri kullanılabilir.

    `ac.get_settings_status()` GENİŞLETİLMEDİ, üzerine BURADA ekleniyor —
    `version`'ın aynı gerekçesi (o fonksiyonun docstring'i): `azure_client`'ın
    işi kimlik bilgisi, hangi modellerin var olduğunu bilmesi gereksiz bir bağ
    olurdu ve tests/test_settings.py'deki sözleşmesini genişletirdi. Mevcut
    anahtarların HEPSİ adıyla ve anlamıyla korunuyor, yani `settings.js` ve
    tests/test_settings_route.py etkilenmiyor.

    Bu fonksiyon GET ve POST'un PAYLAŞTIĞI gövde. `version`/`guncelleme`/
    `chat_instructions_path` bilerek DIŞINDA: onlar yalnız GET'te var (sürüm
    çalışma anında değişmiyor, mutasyon ucundan yansıtmak gürültü olurdu) ve
    settings.js'in `!== undefined` guard'ları tam olarak o daha dar POST
    gövdesine dayanıyor.

    ANAHTAR TAŞIMIYOR. `providers` yalnız boolean, `image_models[].configured`
    de öyle. Anahtarın son dört hanesi, uzunluğu ya da maskelenmiş hâli DE
    dönmüyor: `get_settings_status`'un sözleşmesi "API key'i ASLA döndürmez" ve
    "sadece son dört hane" o sözleşmenin öldüğü yerdir.
    """
    cfg = credstore.configured_map()
    chat_cfg = credstore.chat_configured_map()
    # Şeritte gösterilecek KISA adlar: sağlayıcı markası işaretle geldiği için
    # etiketten düşüyor. Liste bütününden hesaplanıyor (çakışma kuralı için),
    # o yüzden model başına değil bir kez (bkz. catalog.short_labels).
    kisa_gorsel = etiket.short_labels(catalog.IMAGE_MODELS)
    kisa_sohbet = etiket.short_labels(catalog.CHAT_MODELS)
    # Video şeridinin kısa adları AYRI hesaplanıyor, görselle BİRLİKTE değil:
    # `short_labels`ın çakışma kuralı verilen listenin BÜTÜNÜNE bakıyor ve
    # iki şeridi birleştirmek, ayrı seçicilerde duran iki modelin birbirine
    # marka öneki taktırması olurdu (kullanıcı hiçbir zaman aynı listede
    # `Veo 3.1` ile bir görsel modelini yan yana görmüyor).
    kisa_video = etiket.short_labels(catalog.VIDEO_MODELS)
    return {
        **ac.get_settings_status(),
        # {kimlik_id: bool}. Arayüz Ayarlar'daki sağlayıcı gruplarının
        # "Kayıtlı" durumunu buradan okuyor.
        "providers": cfg,
        "default_image_model": catalog.DEFAULT_IMAGE_MODEL,
        # Video şeridi. ANAHTARIN AYRI OLMASI şart: `image_models`a katmak,
        # bugün o listeyi okuyan her yerin (model kartları, arena sütun
        # seçicisi, `secilebilirler` süzgeci) videoyu görsel sanması demekti —
        # `catalog.VIDEO_MODELS`in ayrı bir demet olma gerekçesinin ön yüz
        # tarafındaki karşılığı.
        "default_video_model": catalog.DEFAULT_VIDEO_MODEL,
        "video_models": [model_payload(m, cfg, kisa_video)
                         for m in catalog.VIDEO_MODELS],
        "image_models": [model_payload(m, cfg, kisa_gorsel)
                         for m in catalog.IMAGE_MODELS],
        "default_chat_model": catalog.DEFAULT_CHAT_MODEL,
        "chat_models": [
            {"id": m.id, "label": etiket.label_of(m),
             # Görsel şeridiyle AYNI ayrım (bkz. yukarısı).
             "short_label": kisa_sohbet[m.id], "provider": m.provider,
             # `cfg` (KİMLİK tablosu) DEĞİL `chat_cfg` (MODEL tablosu):
             # Azure'ın dağıtım adı model düzeyinde bir koşul ve kimlik
             # tablosu onu ifade edemiyor — kimliği tam, dağıtımı boş bir
             # kurulumda arayüz modeli "kurulu" gösterir ve ilk mesaj 404
             # dönerdi (bkz. credstore.chat_is_configured).
             "configured": chat_cfg.get(m.id, False),
             # Görsel şeridiyle AYNI alan, aynı gerekçe (model_available).
             "available": model_available(chat_cfg.get(m.id, False), m.plan),
             "requires_plan": m.plan,
             # Ayarlar formunun dağıtım adı kutusunun kapısı: KATALOGDAN
             # türetiliyor, istemcide sağlayıcı adı literal olarak
             # sayılmıyor. Sayılsaydı, adı ortamdan okunan ikinci bir
             # sağlayıcı eklendiği gün kutu sessizce görünmez kalırdı.
             "needs_deployment": catalog.chat_needs_deployment(m),
             # Görsel şeridiyle AYNI alan adı ve aynı gerekçe.
             "logo": provider_logo_url(m.provider),
             "note": i18n.t(m.note) if m.note else None}
            for m in catalog.CHAT_MODELS
        ],
        # `ac.get_settings_status()`in AYNI ADLI alanını BİLEREK eziyor (bu
        # anahtar `**`ın sonrasında). O alan yalnız Azure'ı ölçüyor ve tek
        # sağlayıcı varken doğruydu; bugün yalnızca Gemini anahtarı olan bir
        # kullanıcıda Prompt Yönetmeni'ni kapalı gösterirdi. Ölçüt artık
        # "konuşulabilir EN AZ BİR sohbet modeli var mı".
        #
        # `azure_client` tarafındaki alan KALDIRILMADI: onun sözleşmesi
        # tests/test_settings.py'de donmuş ve orada "Azure sohbeti hazır mı"
        # sorusunun doğru cevabı hâlâ o.
        "chat_configured": any(chat_cfg.values()),
    }


def model_facts(m: catalog.ImageModel) -> dict:
    """Yönetmene giden model olguları — İKİ okuyanın ortak sözlüğü.

    Satır içi bir sözlükken yalnız bağlam bloğu okuyordu; model menüsü açılınca
    ikinci okuyan geldi ve elle yazılmış iki kopya kaçınılmaz olarak ayrışırdı
    (bağlam bloğuna bir eksen eklenip menüye eklenmemesi, yönetmenin seçili
    modelde bildiği bir şeyi öteki modellerde bilmemesi demek olurdu).
    Çıkarma, `model_payload`ın "ÇIKARILDI, kopyalanmadı" gerekçesinin aynısı.

    `model_payload` BURADA KULLANILAMAZ ve bu bir tembellik değil: o sözlük
    arayüzün sözleşmesi (etiket/değer çiftleri, logo adresi, `credits_by_quality`,
    `short_label`) ve sistem mesajına girdiğinde HER TURDA ödenen ölü karakter
    olurdu — bu yüzeyde prompt caching yok.

    `id` alanı ZORUNLU ve yeni: yönetmen artık model ÖNERİYOR, ön yüz de
    önerilen id'yi uyguluyor. Onsuz menü okunabilir ama işe yaramaz olurdu.
    """
    return {"id": m.id, "label": etiket.label_of(m), "kind": m.kind,
            "sizes": m.sizes, "qualities": m.qualities,
            "quality_hidden": m.quality_hidden, "max_n": m.max_n,
            "supports_edit": m.supports_edit, "max_refs": m.max_refs,
            "durations": m.durations, "supports_last_frame": m.supports_last_frame,
            "credits": m.credits}


def director_context(db: Session, kullanici_id: uuid.UUID) -> dict:
    """Yönetmenin sistem mesajına giren TUR bağlamı: seçili model + menü + yönlendirme.

    Bağlamı burada toplamanın sebebi katman kuralı: `chat_prompt` yalnızca
    diski okuyor (katman 1, tek bağımlılığı `paths`) ve `catalog`/tercih
    deposuna bakması onu yukarı çekerdi. Rotada ikisi de hâlihazırda var.
    Tercih KULLANICININ satırından (`tercihler`, Faz 1 / 6): rota isteğin
    `Session`ını ve kapının çözdüğü kullanıcıyı veriyor.

    MODEL BURADA TERCİHTEN okunuyor ve bu, `/api/chat` kararının ("model
    istekten, tercihlerden DEĞİL") istisnası değil TAMAMLAYANI: o karar
    yönetmenin konuşacağı SOHBET modeliyle ilgili ve tel üzerinde geliyor;
    buradaki ise kullanıcının üretimde kullanacağı GÖRSEL modeli, yani
    yönetmenin hangi jetonları önerebileceği. İstemci onu bu uçta göndermiyor
    (`ChatRequest` `extra="forbid"`) ve göndermesi de gerekmiyor: tercih
    satırı o seçimin zaten TEK kaynağı (bkz. prefs.py'nin "hangi modeli
    İSTİYORUM" kuralı).

    Bilinmeyen/bayat bir tercih sessizce bağlamsız kalıyor — `depo_tercih.oku`
    katalog üyeliğini zaten kapıyor, ama `image_model` yine None dönebilir ve
    o durumda doğru davranış bugünkü davranıştır: bağlamsız persona.

    MENÜ (`available_models`) seçili modelin YANINDA duruyor, onun yerine
    değil: bağlam bloğu "bu turda hangi jetonlar geçerli" sorusunu, menü
    "hangi modele GEÇİLEBİLİR" sorusunu cevaplıyor ve ikisi farklı sorular.

    Süzgeç `model_available`, ikinci bir "eksik mi" mantığı DEĞİL: arayüzün
    gösterdiği küme ile yönetmenin gördüğü küme ayrışsaydı yönetmen
    kullanıcının ekranında olmayan bir modeli önerirdi — o fonksiyonun var
    olma gerekçesi tam olarak bu ikiliği önlemek. `credstore.configured_map()`
    de altı kimliği BİR kez çözüyor; model başına `providers.is_configured`
    çağırmak aynı dosyayı on üç kez okumak olurdu.

    `selected` `model_facts`in İÇİNDE değil çünkü o bir MODEL olgusu değil bu
    TURUN olgusu — aynı sözlüğün iki bağlamda kullanılabilmesinin şartı bu
    ayrım. İki tercih birden işaretleniyor: video modu Yönetmen'e kapalı
    olmadığı için kullanıcının video seçimi de "seçili" sayılmalı.
    """
    p = depo_tercih.oku(db, kullanici_id)
    m = catalog.image_model(p["image_model"])
    cfg = credstore.configured_map()
    secili = {p["image_model"], p["video_model"]}
    # GÖRSEL + VİDEO tek listede: `catalog.video_model`in "birleşik arama YOK"
    # kuralı id ile ARAMA hakkında (yanlış türü doğru sanan bir çağıranı
    # sessizce geçirirdi); burada arama değil sıralı gösterim var ve tür her
    # satırda `kind` alanıyla açıkça taşınıyor.
    menu = [{**model_facts(x), "selected": x.id in secili}
            for x in catalog.IMAGE_MODELS + catalog.VIDEO_MODELS
            if model_available(cfg.get(x.credential, False), x.plan)]
    # DİL de bu turun olgusu: persona "kullanıcı hangi dilde yazıyorsa o dilde
    # konuş" diyor, ama ilk mesaj dilsiz olabiliyor (tek kelime, bir oran, bir
    # hex kodu) ve o turda modelin elinde hiçbir işaret kalmıyor. Arayüz dili
    # o boşluğun en iyi tahmini — kullanıcı onu bilerek seçmiş. Aynı sözlükten
    # okunuyor, ikinci bir kaynak açılmıyor.
    return {"model_facts": model_facts(m) if m is not None else None,
            "guidance": p["director_guidance"], "available_models": menu,
            "language": p["language"]}
