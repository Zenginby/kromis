# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Ayarlar uçları: sağlayıcı kimlikleri, güncelleme denetimi, kullanıcı tercihleri."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

import azure_client as ac
import catalog
import guncelleme
import i18n
import paths
import prefs
import version
from models import PrefsRequest, SettingsRequest
from services import dil, modeller, tercih, yollar

router = APIRouter()


@router.get("/api/settings")
def get_settings() -> dict:
    """Yapılandırma durumu + uygulama sürümü. API key asla dönmez.

    `version` BURADA birleştiriliyor, azure_client'ta DEĞİL: onun işi kimlik
    bilgisi, uygulama sürümünü bilmesi gereksiz bir bağ olurdu ve
    tests/test_settings.py'deki get_settings_status sözleşmesini genişletirdi.

    Destek sorusu "hangi sürümdesiniz?" v1.8'de cevaplanamıyordu — sürüm
    yalnızca Info.plist'te vardı ve arayüz onu hiç göstermiyordu.

    `chat_instructions_path` da burada birleşiyor: talimatı ezme özelliği
    keşfedilebilir olmasa var olmakla olmamak arasında bir fark kalmaz. Video
    bölümünün ezmesi AYRI bir yol ve o da burada, aynı gerekçeyle: iki dosya
    ayrı çünkü video talimatı sistem mesajına yalnız video modeli
    yapılandırılmışsa giriyor (bkz. chat_prompt.build_system).

    `guncelleme` de burada: kullanılan sürümün YANINDA durması gerekiyor, çünkü
    kullanıcının sorduğu şey "hangi sürümdeyim" değil "güncel miyim". Ayrı bir
    uç nokta arayüze ikinci bir istek ekler ve ikisi ayrı zamanlarda gelirse
    panel bir an "0.4.2 — güncel" deyip sonra fikir değiştirirdi.

    Bu alan istek yolunu BEKLETMEZ: `guncelleme.bilgi()` yalnız önbelleğe
    bakıyor, ağ çağrısı arka planda koşuyor (bkz. guncelleme.py'deki 2.
    sözleşme). İlk açılışta değeri `null` olur, sonrakinde dolar.
    """
    output_dir = yollar.output_dir()
    return {**modeller.settings_payload(),
            "version": version.APP_VERSION,
            "guncelleme": guncelleme.bilgi(
                output_dir, izin=prefs.read(output_dir)["guncelleme_kontrolu"]),
            "chat_instructions_path": paths.chat_instructions_override(),
            "chat_video_instructions_path":
                paths.chat_video_instructions_override()}


@router.get("/api/guncelleme")
def get_guncelleme() -> dict:
    """Yalnız güncelleme cevabı — `/api/settings`'in ARDIL okuması.

    NEDEN AYRI BİR UÇ: `guncelleme.bilgi()` bayat önbellekte tazelemeyi arka
    plana atıp `None` döner (guncelleme.py'nin 2. sözleşmesi). Modül bunu
    "birkaç saniye sonrakinde gerçek cevap gelir" diye yazmıştı, ama ön yüz
    `/api/settings`'i YALNIZ açılışta bir kez soruyor (settings.js'nin tek
    `loadSettings(true)` çağrısı) — yani "sonraki" istek hiç gelmiyordu ve
    tazelenen cevap BİR SONRAKİ uygulama açılışına kadar diskte kalıyordu.
    Kullanıcı tarafından bakıldığında bu, "bildirim hiç gelmiyor"dan ayırt
    edilemez.

    Alan `/api/settings`'ten KALDIRILMADI ve kaldırılmamalı: oradaki gerekçe
    (sürüm satırıyla aynı yanıtta gelmezse panel bir an "güncelsin" deyip fikir
    değiştirir) ilk çizim için hâlâ geçerli. Bu uç onun YERİNE değil ARDINDAN
    geliyor — çağrıldığı anda sürüm zaten çizilmiş oluyor, dolayısıyla
    "fikir değiştirme" durumu doğmuyor.

    Ön yüz bunun için `/api/settings`'i yeniden çağıramaz: o yanıt
    `applyConfigured()` üzerinden formun tamamını yeniden yazıyor ve
    kullanıcının o sırada doldurduğu alanları ezerdi.

    İstek yolunu BEKLETMEZ — `/api/settings` ile aynı çağrı, aynı önbellek.
    """
    output_dir = yollar.output_dir()
    return {"guncelleme": guncelleme.bilgi(
        output_dir, izin=prefs.read(output_dir)["guncelleme_kontrolu"])}


@router.post("/api/guncelleme")
def post_guncelleme() -> dict:
    """"Şimdi kontrol et" — TTL'i baypas eden, SONUCU BEKLEYEN elle kontrol.

    NEDEN VAR: `GET` yalnız önbelleğe bakıyor ve önbellek 24 saat taze sayılıyor
    (`guncelleme.TTL_SANIYE`). Yayın hızı bundan yüksekse — 2026-09-12'de
    ölçüldü: son beş yayın ortalama 7.7 saatte bir çıkmış — kullanıcının
    önbelleği "taze" olduğu hâlde cevabı bayat kalıyor ve GitHub'a hiç
    sorulmuyor. Tam olarak yaşanan kusur bu: v0.20.1 yayınlandı, telefon
    bildirimi göstermedi, kullanıcının elinde tetikleyecek HİÇBİR yol yoktu
    (tercih anahtarını kapatıp açmak önbelleğe dokunmuyor).

    NEDEN POST, GET DEĞİL: bu uç yan etkili — ağa çıkıyor ve önbelleği yeniden
    yazıyor. Aynı adresin GET'i saf okuma olarak kalıyor, yani ön yüzün açılış
    yoklaması (`yoklaGuncelleme`) yanlışlıkla ağ çağrısı tetikleyemiyor.

    İSTEK YOLUNU BEKLETİR ve bu bilinçli — gerekçe `guncelleme.simdi_kontrol_et`
    başlığında: 2. sözleşme açılış yolunu koruyor, kullanıcının bastığı bir
    düğmeyi değil. Rota senkron, Starlette onu threadpool'da koşturuyor.

    Gövde `{"durum": …, "guncelleme": …}`; `durum` dört değerden biri
    (`guncelleme.DURUM_*`) ve arayüz her birini ayrı bir cümleye çeviriyor.
    """
    output_dir = yollar.output_dir()
    return guncelleme.simdi_kontrol_et(
        output_dir, izin=prefs.read(output_dir)["guncelleme_kontrolu"])


@router.post("/api/settings")
def post_settings(req: SettingsRequest) -> dict:
    """Sağlayıcı kimliklerini yalnızca-yazılır kaydeder; durumu döndürür (key'siz).

    Gizli alanda boş değer "mevcut korunur" demek — istemci kayıtlı anahtarı hiç
    görmediği için boş bir kutu "sildim" değil "dokunmadım"dır. Adres
    alanlarında boş "varsayılana dön" demek; ayrım her ikisinin de yazıldığı
    döngülerde yorumlu.

    Azure kimliği artık YALNIZ istek onu hedeflediğinde zorunlu (bkz. gövdedeki
    `azure_hedefli`): eskiden ilk kurulumda koşulsuz zorunluydu ve yalnızca
    başka bir sağlayıcının anahtarını girmek isteyen kullanıcı hiçbir şey
    kaydedemiyordu.

    Sohbet dağıtımı ve öteki sağlayıcılar, görsel kimliği doğrulamadan GEÇTİKTEN
    SONRA yazılıyor: geçersiz bir endpoint'le gelen istek hiçbir şey yazmadan
    422 dönmeli.
    """
    api_key = req.api_key.strip()
    base_url = (req.base_url or "").strip()
    # İSTEK AZURE'U HEDEFLİYOR MU: iki alandan biri doluysa evet. Bu ayrım
    # v0.6'da açıldı ve sebebi somut bir kilitti — kural "ilk kurulumda Azure
    # api_key + base_url ZORUNLU" biçimindeydi, yani yalnızca Gemini anahtarı
    # olan bir kullanıcı HİÇBİR ŞEY kaydedemiyordu ve aldığı 422 bambaşka bir
    # sağlayıcıdan söz ediyordu ("İlk kurulumda API key gerekli"). Çoklu
    # sağlayıcının önündeki en somut engel buydu.
    azure_hedefli = bool(api_key or base_url)

    # Mevcut Azure kimliği. Hata YÜKSELTİLMİYOR: Azure'ın hiç yapılandırılmamış
    # olması artık bir hata durumu değil, sıradan bir başlangıç hâli.
    try:
        mevcut_key, mevcut_url = ac.load_credentials()
    except ac.ImageError:
        mevcut_key, mevcut_url = "", ""
    # "Boş = mevcut korunur" kuralı KORUNUYOR (v1.x davranışı).
    api_key = api_key or mevcut_key
    base_url = base_url or mevcut_url

    if azure_hedefli:
        # Azure hedefleniyorsa İKİSİ de gerekli. Mesajlar bilerek ayrı: hangi
        # alanın eksik olduğunu söylemeyen bir hata kullanıcıyı formda arattırır.
        if not api_key:
            raise HTTPException(status_code=422, detail=i18n.t("err.first_setup_key", dil.aktif()))
        if not base_url:
            raise HTTPException(status_code=422, detail=i18n.t("err.first_setup_base_url", dil.aktif()))

    try:
        # Kimlik doğrulaması DİĞER alanların yazımından ÖNCE: geçersiz bir
        # endpoint'le gelen istek hiçbir şey yazmadan 422 dönmeli
        # (tests/test_settings_route.py bu sırayı sabitliyor).
        if azure_hedefli and api_key and base_url:
            ac.save_credentials(api_key, base_url)
        updates = {}

        if req.chat_deployment is not None:
            updates[ac.CHAT_DEPLOYMENT] = req.chat_deployment.strip()

        # GİZLİ alanlar: boş gönderim "mevcut korunur" demek, silme DEĞİL.
        # (Yalnızca-yazılır formun kuralı: istemci kayıtlı anahtarı hiç
        # görmüyor, o yüzden boş bir kutu "sildim" değil "dokunmadım"dır.)
        # Alan adı → env adı eşlemesi KATALOGDAN geliyor, elle sayılmıyor:
        # elle sayılan liste tam olarak redaksiyonun kaçırdığı hataydı.
        for cred in catalog.CREDENTIALS:
            if not cred.secret_field or cred.secret_field == "api_key":
                continue    # api_key yukarıda, kendi doğrulama yolundan geçiyor
            deger = getattr(req, cred.secret_field, None)
            if deger is not None and deger.strip():
                updates[cred.key_env] = deger.strip()

        # ADRES alanları: gizli DEĞİL ve boş gönderim "varsayılana dön" demek,
        # o yüzden `is not None` yeterli (gizli alanların aksine).
        #
        # TEK İSTİSNA ve gerekçesi kataloğun KENDİSİNDEN okunuyor:
        # `default_base_url`ü OLMAYAN kimlikte (bugün yalnız azure_image)
        # düşülecek bir varsayılan yok — orada boş adres "varsayılana dön"
        # değil "bağlantıyı kopar" demek olurdu. O yüzden boş kutu, gizli
        # alanlarla AYNI kuralı izliyor: "dokunmadım".
        #
        # Gerekçe simetri değil, ÖLÇÜLEN veri kaybı: yukarıdaki
        # `save_credentials` boş `base_url`de bilerek atlanıp mevcut
        # endpoint'i KORUYOR, ama bu döngü hemen ardından onu "" ile
        # eziyordu — tek istekte biri koruyup öteki siliyordu. İstemci
        # `base_url`i KOŞULSUZ gönderiyor (static/settings.js → saveSettings)
        # ve boş-adres kapısı yalnız sağlayıcı "azure" seçiliyken kuruluyor,
        # yani yalnızca OpenAI anahtarı kaydeden bir kullanıcı çalışan Azure
        # kurulumunu 200 alarak siliyordu.
        #
        # Yetenek KAYBI yok: boş endpoint hiçbir zaman "bağlantıyı kes"
        # gestürü değildi — istemci onu "Endpoint gerekli." ile reddediyor.
        for cred in catalog.CREDENTIALS:
            if not cred.url_field:
                continue
            deger = getattr(req, cred.url_field, None)
            if deger is None:
                continue
            if not deger.strip() and not cred.default_base_url:
                continue
            # ŞEMA KAPISI: Azure'ın adresinde ilk günden beri var olan denetim
            # (bkz. ac.check_base_url) öteki sağlayıcılarda YOKTU — şemasız bir
            # yapıştırma 200 alıyor, hata ancak ilk üretimde ve "bağlanılamadı"
            # kılığında görünüyordu. Boş değer bu kapıdan MUAF: yukarıdaki iki
            # satır onu zaten "varsayılana dön" olarak geçirdi.
            if deger.strip():
                ac.check_base_url(deger.strip(), cred.url_field)
            updates[cred.url_env] = deger.strip()

        # Kataloğa girmemiş eski BYOK alanları. Katalog döngüsünün DIŞINDA
        # bilerek: bunların henüz bir modeli ve adaptörü yok, kataloğa yazmak
        # "bağlı" gibi görünmelerine yol açardı. Yazma yolu korunuyor çünkü
        # v0.2.0'dan beri kaydediliyorlar ve veri kaybı olmamalı.
        #
        # `fal_key` BURADAN ÇIKTI: adaptörü geldi, kataloğa girdi ve yukarıdaki
        # `for cred in catalog.CREDENTIALS` döngüsü onu aynı env'e aynı
        # "boş = dokunma" kuralıyla yazıyor.
        #
        # DÜZELTME (Görev 9, 2026-09-15): bu satır önceden "üstelik
        # redaksiyonu da kendiliğinden kapsıyor" diyordu — bu YANLIŞTI.
        # `fal_key` bu daldan ÖNCE de tam redakte ediliyordu: hem
        # `/api/settings` `CREDENTIAL_ROUTES`ta olduğu için (rota kapısı),
        # hem `_key` soneki `SECRET_SUFFIXES`te olduğu için (alan-adı
        # kapısı; bkz. services/redaksiyon.py). Katalog girdisinin getirdiği
        # şey buradaki YAZMA yolu (form alanı + bu döngü) — redaksiyon değil,
        # o zaten vardı.
        if req.replicate_api_token is not None and req.replicate_api_token.strip():
            updates["REPLICATE_API_TOKEN"] = req.replicate_api_token.strip()
        # Aynı şema kapısı burada da: bu ikisi katalog döngüsünün DIŞINDA
        # (henüz modelleri yok) ve boş değer yine "temizle" demek.
        if req.comfyui_url is not None:
            if req.comfyui_url.strip():
                ac.check_base_url(req.comfyui_url.strip(), "comfyui_url")
            updates["COMFYUI_URL"] = req.comfyui_url.strip()
        if req.ollama_url is not None:
            if req.ollama_url.strip():
                ac.check_base_url(req.ollama_url.strip(), "ollama_url")
            updates["OLLAMA_URL"] = req.ollama_url.strip()

        if updates:
            ac.save_env(updates)
    except ac.ImageError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return modeller.settings_payload()


# ── Kullanıcı tercihleri ────────────────────────────────────────────────

@router.get("/api/prefs")
def get_prefs_route() -> dict:
    """Tercihlerin birleşik görünümü (bkz. prefs.py). Gizli alan taşımıyor."""
    return prefs.read(yollar.output_dir())


@router.post("/api/prefs")
def post_prefs_route(req: PrefsRequest, response: Response) -> dict:
    """Gönderilen tercihleri yazar, diğerlerine dokunmaz; yeni görünümü döndürür.

    Anahtar BİLEREK `/api/settings`'te DEĞİL: o uç kimlik formu ve `api_key` +
    `base_url` istiyor — bir tercihi çevirmek Azure kimliğini yeniden yazmak
    zorunda kalırdı ve Azure hiç yapılandırılmamışken anahtar çevrilemez olurdu.
    Değer de tek yerden okunuyor (`/api/settings` onu YANSITMIYOR): iki uç aynı
    değeri döndürseydi ayrışabilirlerdi.

    `language` yazıldığında cevap bir de ÇEREZ taşıyor (Faz 0 / Adım 3):
    dil zinciri (services/dil.py) çerezi diskteki tercihten ÖNCE okuyor, yani
    seçimi yapan tarayıcı bir sonraki isteğinde dilini kendisi getiriyor ve
    Faz 1'de aynı süreçteki başka bir tarayıcının başka bir dil görmesinin
    yolu açık. Ön yüz DEĞİŞMEDİ: `static/settings.js` yazımın ardından
    `location.reload()` yapıyor, yeni sayfa çerezle geliyor.

    `tercih.sifirla()` yazımdan hemen sonra: önbellek dosya imzasından
    zaten anlardı, ama yazan ile okuyan aynı süreçteyken sözleşme mekanizmaya
    tercih ediliyor (gerekçesi services/tercih.py'de). Yazım başarısızsa
    (422) çağrılmıyor — düşürecek bir şey değişmedi.
    """
    values = req.model_dump(exclude_none=True)
    try:
        sonuc = prefs.update(values, yollar.output_dir())
    except ValueError as e:
        # prefs katmanı da bilinmeyen anahtarı/yanlış türü reddediyor; buraya
        # düşmek pydantic ile prefs şemasının ayrışması demek olur.
        raise HTTPException(status_code=422, detail=str(e))
    tercih.sifirla()
    if "language" in values:
        dil.cerez_yaz(response, values["language"])
    return sonuc
