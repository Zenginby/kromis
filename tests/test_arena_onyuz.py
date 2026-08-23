"""Arena'nın ÖN YÜZ sözleşmeleri: fan-out, eksen çevirisi, tek yazar, yerleşim.

Sunucu tarafı (`tests/test_arena.py`) turun ETİKETİNİ ve kazananı ölçüyor;
arenanın asıl mekaniği ise burada, çünkü fan-out istemcide: N istek, N sütun,
kısmi başarısızlık.

Yöntem depodaki kalıp (bkz. tests/test_index.py): betikler servis edilip
KAYNAK METNİ denetleniyor. Kaba ama ucuz ve gerçek kırılmaları yakalıyor;
tarayıcı ölçümü Playwright dosyasının işi (CI'da koşmuyor).
"""
import re

from fastapi.testclient import TestClient

import app as appmod
import catalog


def _metin(yol: str) -> str:
    return TestClient(appmod.app).get(yol).text


def _core() -> str:
    return _metin("/static/core.js")


def _kodsuz(js: str) -> str:
    """Satır yorumlarını ayıklar.

    Deponun DÖRT kez düştüğü tuzak (bkz. tests/test_index.py): "burada
    şu yazmasın" biçimindeki bir iddia, kararın GEREKÇESİNDE geçen aynı
    sözcüğe takılıyor — yani test kendi açıklamasını hata sayıyor.
    """
    return re.sub(r"//[^\n]*", "", js)


def _govde(js: str, ad: str) -> str:
    """Bir fonksiyonun gövdesi (üst düzey, girintisiz kapanışa kadar)."""
    m = re.search(rf"function {ad}\([^)]*\)\s*\{{(.*?)\n\}}", js, re.S)
    assert m, f"{ad}() bulunamadı"
    return m.group(1)


# ── Fan-out ────────────────────────────────────────────────────────────


def test_the_round_fans_out_from_the_client_not_the_server():
    """Sütun başına AYRI istek. Sunucuda fan-out YOK ve bu ölçülü bir karar.

    Tek istekte fan-out, isteği en yavaş modele bağlardı (zaman aşımı bütçesi
    `providers.total_budget` ile MODEL BAŞINA hesaplanıyor) ve tek yollu 502
    "3 modelden 1'i düştü"yü ifade edemezdi.
    """
    govde = _govde(_core(), "runArena")
    assert "sutunlar.map" in govde, "sütunlar tek tek koşturulmuyor"
    assert 'fetch("/api/generate"' in govde, "üretim ucu çağrılmıyor"
    assert "Promise.all" in govde, "sütunlar paralel değil"
    # Sunucuda arena diye bir ÜRETİM ucu yok: turun yalnız etiketi ve kazananı var.
    yollar = {r.path for r in appmod.app.routes if hasattr(r, "path")}
    assert "/api/arena/{arena_id}/winner" in yollar
    assert not any(y.startswith("/api/arena") and y.endswith("generate") for y in yollar)


def test_every_column_carries_the_same_round_tag_and_a_single_image():
    """Turun ortak etiketi + sütun başına tek görsel.

    `n: 1` sabit: 4 model × 4 görsel hem ızgarayı hem faturayı okunmaz yapardı
    ve bir sonuç kaydının `image_ids` tavanı zaten bir TURUN çıktısı kadar.
    """
    govde = _govde(_core(), "runArena")
    assert "arena_id: arenaId" in govde, "istek turun etiketini taşımıyor"
    assert "n: 1" in govde, "sütun başına adet 1'e sabitlenmemiş"
    assert govde.count("const arenaId = arenaKimlik()") == 1, (
        "tur kimliği sütun başına yeniden üretiliyor — sütunlar birbirini bulamaz")


def test_a_failed_column_does_not_take_the_round_down():
    """Kısmi başarısızlık: hata O SÜTUNDA kalıyor, tur devam ediyor."""
    govde = _govde(_core(), "runArena")
    assert "failArenaSlot" in govde, "düşen sütun işaretlenmiyor"
    assert "catch" in govde, "sütun hatası yakalanmıyor"
    # Özet SAYIYLA: kullanıcı turun sonucunu tek bakışta görmeli.
    assert "tutan.length}/${sutunlar.length}" in govde, "tur özeti sayı vermiyor"


def test_a_round_with_no_surviving_column_leaves_no_orphan_turn():
    """`run()`ın kuralı arenada da geçerli: başarısız tur geçmişte kalmaz."""
    govde = _govde(_core(), "runArena")
    assert "dropPendingTurn(pending)" in govde
    assert '$("prompt").value = prompt' in govde, "prompt kutuya geri konmuyor"


def test_the_round_id_matches_the_store_guard():
    """İstemcinin ürettiği id `storage._SAFE_ID` ([0-9a-f]{8,32}) ile uyumlu olmalı.

    Uymazsa uç 422 döner ve arena HİÇ çalışmaz — sessiz değil ama tümden ölü.
    """
    govde = _govde(_core(), "arenaKimlik")
    assert "[^0-9a-f]" in govde, "id onaltılığa indirgenmiyor"
    assert "slice(0, 12)" in govde, "id uzunluğu sınırlanmıyor"


# ── Eksen çevirisi ─────────────────────────────────────────────────────


def test_the_axis_translation_lives_in_exactly_one_place():
    """Gösterilen fiyat ile gönderilen istek AYNI çeviriden geçmek zorunda.

    İki ayrı yerde çevrilseydi kullanıcıya "36 kredi" yazılıp başka bir tarife
    faturalanabilirdi — bu deponun en sevmediği kırılma sınıfı.
    """
    js = _core()
    assert js.count("function arenaSutunlari(") == 1
    assert "arenaSutunlari()" in _govde(js, "syncRunCost"), (
        "maliyet göstergesi çeviriyi kendi başına kuruyor")
    assert "arenaSutunlari()" in _govde(js, "runArena"), (
        "üretim isteği çeviriyi kendi başına kuruyor")


def test_size_is_translated_through_the_ratio_the_server_publishes():
    """Modellerin boyut JETONLARI farklı (`1024x1536` ↔ `2:3`); ortak olan ORAN.

    Oran SUNUCUDAN geliyor (`/api/settings` → `sizes[].ratio`), istemci jeton
    ayrıştırmıyor — Gemini'nin jetonları `WxH` biçiminde bile değil.
    """
    govde = _govde(_core(), "arenaSutunlari")
    assert "dataset.ratio" in govde, "oran seçili seçenekten okunmuyor"
    assert "s.ratio === oran" in govde, "hedef model oranla eşlenmiyor"
    assert "default_size" in govde, "oranı olmayan modelde varsayılana düşülmüyor"
    # Sunucu gerçekten yayınlıyor mu — sözleşmenin öteki ucu.
    ayarlar = TestClient(appmod.app).get("/api/settings").json()
    assert all("ratio" in s for m in ayarlar["image_models"] for s in m["sizes"])


def test_quality_is_translated_through_the_rank_not_the_token():
    """Kalite EKSENLERİ ortak değil (düşük/orta/yüksek ↔ 1K/2K/4K); ortak olan SIRA."""
    govde = _govde(_core(), "arenaSutunlari")
    assert "m.qualities[Math.min(sira" in govde, "kalite sıraya göre eşlenmiyor"
    assert "qualities.length - 1" in govde, "kısa demette son basamağa kırpılmıyor"


def test_the_rank_mapping_assumption_holds_in_the_catalog():
    """Eşleme demetlerin ARTAN sırada olmasına dayanıyor — katalog onu doğrulasın.

    Bir model bir gün kalitelerini karışık sırada bildirirse "yüksek" ile "4K"
    aynı basamağın iki adı olmaktan çıkar ve arena sessizce yanlış çeviri
    yapardı. Bu iddia o sessizliği kapatıyor.
    """
    for m in catalog.IMAGE_MODELS:
        if not m.credits_by_quality:
            continue
        tarife = [m.credits_by_quality[q] for q in m.qualities
                  if q in m.credits_by_quality]
        assert tarife == sorted(tarife), (
            f"{m.id}: kalite demeti artan sırada değil {m.qualities} → {tarife}")


def test_the_shared_size_list_is_the_intersection_of_the_chosen_models():
    """Kesişim dışı bir oran bazı sütunları sessizce kendi varsayılanına düşürürdü.

    Aynı prompt'u aynı koşulda koşturmak arenanın TANIMI: farklı çerçevelerde
    üretilmiş iki görsel karşılaştırma değildir.
    """
    js = _core()
    govde = _govde(js, "arenaOrtakBoyutlar")
    assert "every(" in govde, "kesişim alınmıyor"
    assert "arenaOrtakBoyutlar(idler)" in _govde(js, "arenaUygula")


def test_closing_the_arena_gives_the_axes_back():
    """Daraltma GERİ ALINMAK zorunda: arena `#size`i kesişime, `#n`i 1'e çekiyor.

    Geri açan kod yokken kırılma arena KAPANDIKTAN sonra görülüyordu — Nano
    Banana (10 oran) ile Azure (3) arasında bir arena kurup kapatan kullanıcı,
    TEK MODEL üretiminde de 3 oran görmeye devam ediyordu ve adet 1'e mıhlı
    kalıyordu. Model yeniden seçilmeden düzelmiyordu, yani sessiz.
    """
    js = _core()
    govde = _govde(js, "arenaUygula")
    kapanis = govde.split("} else if (currentModel) {")
    assert len(kapanis) == 2, "arena kapanışında eksenleri geri açan dal yok"
    assert 'fillAxis("size", currentModel.sizes' in kapanis[1], (
        "oran ekseni kesişimde takılı kalıyor")
    assert 'fillAxis("n", adetSecenekleri(currentModel)' in kapanis[1], (
        "adet ekseni 1'de takılı kalıyor")
    # Adet seçenekleri TEK yerden: iki kopyadan biri modelin tavanını unutabilirdi.
    assert js.count("function adetSecenekleri(") == 1
    assert "max_n" not in govde, "arena adet tavanını kendi başına kuruyor"


# ── Tek yazar / kapı ───────────────────────────────────────────────────


def test_arena_state_has_a_single_writer():
    """Görünen her sonucun TEK yazarı `arenaUygula` (deponun genel disiplini)."""
    js = _core()
    for satir in ('$("arena-btn").hidden', '$("model-pick").hidden',
                  '$("arena-btn-label").textContent'):
        assert js.count(satir) == 1, f"{satir} birden çok yerden yazılıyor"


def test_choosing_arena_models_does_not_rewrite_the_saved_preference():
    """Arena kümesindeki gezinme kullanıcının KALICI model tercihini bozmamalı.

    `#model`e yazılıyor ama `change` ATILMIYOR: o olayın dinleyicisi tercihi
    diske yazıyor (`savePref`).
    """
    govde = _govde(_core(), "arenaUygula")
    assert "applyModel(idler[0]" in govde, "birinci sütun eksenleri sürmüyor"
    assert "dispatchEvent" not in govde, "arena tercihi diske yazıyor"
    assert "savePref" not in govde


def test_the_go_gate_names_every_arena_blocker():
    """Kilitli bir düğmenin SEBEBİ yazılı olmak zorunda (#go kapısının kuralı)."""
    govde = _govde(_core(), "goBlockReason")
    assert "ARENA_MIN" in govde, "en az model sayısı kapıda değil"
    assert "Arena düzenlemeyle çalışmıyor" in govde, (
        "arena + referans hâli sessizce sıradan düzenlemeye düşüyor")
    assert "anahtar yok" in govde


def test_the_keyboard_path_asks_the_WHOLE_gate_not_just_the_column_count():
    """`runArena` kapının TAMAMINI soruyor, kendi kopyasını kurmuyor.

    Klavye yolu (⌘/Ctrl+Enter → `submitComposer`) `#go.disabled`a hiç bakmıyor.
    Yalnız sütun SAYISI ölçüldüğünde `goBlockReason`ın referans engeli ölü bir
    metne dönüyordu: referans ekliyken Enter, kaynağı sessizce düşürüp N tane
    ÜCRETLİ istek atıyordu — üstelik #go "Görseli düzenle" yazarken.
    """
    govde = _govde(_core(), "runArena")
    assert "const engel = goBlockReason();" in govde, (
        "tur kapının tamamını sormuyor — engelin bir kısmı uygulanmıyor")
    # Sıra bağlayıcı: kapı İSTEKTEN önce sorulmak zorunda.
    assert govde.index("goBlockReason()") < govde.index('fetch("/api/generate"'), (
        "kapı istek gönderildikten sonra soruluyor")


def test_a_stalled_history_refresh_does_not_wedge_the_go_button():
    """`runBusy` `finally`de bırakılıyor (`run()`ın deseni).

    `finishArenaTurn`/`loadHistory` kendi try/catch'ini tutmuyor: düz akışta
    sıfırlanan bir kilit, kopan bağlantıda #go'yu sayfa yenilenene kadar
    "Üretim sürüyor…" diye kapalı bırakıyordu — görseller diske düşmüşken.
    """
    govde = _kodsuz(_govde(_core(), "runArena"))
    kuyruk = govde.split("} finally {")
    assert len(kuyruk) == 2, "tur `finally` kullanmıyor"
    assert "runBusy = false" in kuyruk[1], "kilit `finally` dışında bırakılıyor"
    assert "runBusy = false" not in kuyruk[0], (
        "kilit ayrıca düz akışta da bırakılıyor — ikinci bir sahip")
    # Özet, patlayabilen döküm adımından ÖNCE yazılıyor: tur sonucu ekranda kalsın.
    assert govde.index("model üretti.") < govde.index("finishArenaTurn(pending"), (
        "tur özeti döküm adımından sonra yazılıyor — o adım patlarsa sonuç kaybolur")


def test_the_cap_is_enforced_on_the_checkbox_itself():
    """Beşinci modeli sessizce yok saymak 'bastım, hiçbir şey olmadı' demek."""
    js = _core()
    govde = _govde(js, "arenaKutucuk")
    assert "ARENA_MAX" in govde
    assert "kutucuk.checked = false" in govde, "tavan kutucuğa yansıtılmıyor"
    assert "statusEl.textContent" in govde, "tavan sessizce uygulanıyor"
    assert re.search(r"const ARENA_MAX = 4", js), "tavan 4 değil"
    assert re.search(r"const ARENA_MIN = 2", js), "taban 2 değil"


# ── Döküm ve yerleşim ──────────────────────────────────────────────────


def test_the_transcript_groups_a_round_into_one_row():
    """Sütunlar AYRI kayıt, satır ARDIŞIKLIKTAN doğuyor."""
    js = _metin("/static/chat.js")
    govde = _govde(js, "renderThread")
    assert "params || {}).arena_id" in govde, "gruplama etiketten okumuyor"
    assert "appendArenaRow(grup)" in govde
    # Canlı satır ile yeniden yüklenen satır AYNI çizim yolundan geçmeli.
    assert "arenaColumn(pending.row" in _govde(js, "fillArenaSlot")
    assert "arenaColumn(row, msg, arenaId)" in _govde(js, "appendArenaRow")


def test_each_column_waits_with_its_own_shimmer_box():
    """`pixel-canvas` singleton değil: sütun başına ayrı örnek, DOM'a girdikten
    SONRA başlatılıyor (bağlanmamış düğümde ölçü 0'dır)."""
    govde = _govde(_metin("/static/chat.js"), "beginArenaTurn")
    assert 'className = "pending-shimmer"' in govde
    assert "s.pixels.start()" in govde
    assert govde.index("appendChild(row)") < govde.index("s.pixels.start()"), (
        "kutu DOM'a girmeden başlatılıyor — tek piksel bile üretilmez")


def test_the_winner_mark_has_a_single_source_of_truth():
    """İşaret `history.json`da; döküm kaydına ikinci bir kopya YAZILMIYOR.

    İki kopya, oturum kaydedilmeyen bir turda sessizce ayrışırdı.
    """
    js = _metin("/static/chat.js")
    assert "arena_win" not in _govde(js, "finishArenaTurn"), (
        "kazanan döküm kaydına da yazılıyor — ikinci bir gerçek")
    isaret = _govde(js, "markArenaWinner")
    assert "/winner" in isaret, "kazanan ucu çağrılmıyor"
    assert isaret.index("chatApi") < isaret.index("syncArenaWinner"), (
        "düğme ucu beklemeden basılı hâle geçiyor — ekran diskle ayrışabilir")
    assert 'aria-pressed' in _govde(js, "syncArenaWinner")


def test_the_arena_row_never_shows_more_than_two_columns_on_a_phone():
    """360px'de dört sütun karo başına ~73px bırakıyor; o karşılaştırma değil."""
    css = _metin("/static/mobile.css")
    kural = re.search(r"\.chat-result\.arena-row[^{]*\{[^}]*\}", css)
    assert kural, "mobil arena kuralı yok"
    assert "repeat(2," in kural.group(0), "telefonda sütun sayısı sınırlanmamış"
    assert '[data-count="4"]' in kural.group(0), "4 sütunlu hâl mobilde ezilmiyor"


def test_the_arena_row_overrides_the_pending_flex_layout():
    """`.chat-result.is-pending` ORTALAYAN bir flex; ezilmezse sütunlar yığılır."""
    css = _metin("/static/style.css")
    kural = re.search(r"\.chat-result\.arena-row\.is-pending\s*\{[^}]*\}", css)
    assert kural and "display: grid" in kural.group(0), (
        "bekleyen arena satırı ızgara değil — sütunlar üst üste düşer")


def test_arena_is_hidden_in_director_mode():
    """Yönetmen bir SOHBET: karşılaştırılacak üretim yok, şerit yer kaplamamalı."""
    css = _metin("/static/style.css")
    assert '#composer[data-mode="director"] #arena-pick' in css


def test_the_arena_selection_holder_is_a_value_carrier_not_a_control():
    """`#model`in çoklu kardeşi, aynı gerekçelerle: değer DOM'da, klavye panelde."""
    html = _metin("/")
    blok = re.search(r'<select id="arena-models"[^>]*>', html)
    assert blok, "#arena-models yok"
    for oznitelik in ('class="sr-only"', 'tabindex="-1"', 'aria-hidden="true"', "multiple"):
        assert oznitelik in blok.group(0), f"{oznitelik} yok"
    assert 'id="arena-toggle"' in html and 'aria-pressed="false"' in html
