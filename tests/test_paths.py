import os
import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import paths


def test_dev_mode_paths_match_the_repo_layout():
    """Geliştirmede yollar bugünküyle birebir aynı olmalı (599 testin dayandığı varsayım)."""
    assert not paths.is_frozen()
    assert paths.data_dir() == paths.REPO_DIR
    assert paths.resource_dir() == paths.REPO_DIR
    assert paths.output_dir() == os.path.join(paths.REPO_DIR, "output")
    assert paths.assets_dir() == os.path.join(paths.REPO_DIR, "assets")
    assert paths.static_dir() == os.path.join(paths.REPO_DIR, "static")


def test_dev_mode_matches_the_app_settings_object():
    """`app.state.ayarlar` (Faz 0 / Adım 4) paths.py ile aynı yerleri göstermeli."""
    import app as appmod
    from services import ayar
    assert appmod.app.state.ayarlar == ayar.Ayarlar.varsayilan()
    assert appmod.app.state.ayarlar.data_dir == paths.data_dir()
    assert appmod.app.state.ayarlar.output_dir == paths.output_dir()
    assert appmod.app.state.ayarlar.static_dir == paths.static_dir()
    assert appmod.app.state.ayarlar.assets_dir == paths.assets_dir()


def test_kromis_data_dir_env_moves_the_writable_root_and_only_that(monkeypatch, tmp_path):
    """`KROMIS_DATA_DIR=/veri` (web/konteyner, 4. görevin çıkış ölçütü).

    Yazılabilir kök oraya iner, salt-okunur kaynak (`static/`) YERİNDE kalır:
    konteynerde bind-mount edilen dizin veri dizinidir, paket içeriği değil.
    Değişken frozen dalını da yener — açık işletmen kararı otomatik tahmini
    ezmeli; tersi bir konteyner imajının sessizce imajın içine yazması olurdu.
    """
    from services import ayar
    veri = str(tmp_path / "veri")
    monkeypatch.setenv(paths.DATA_DIR_ENV, veri)
    assert paths.data_dir() == veri
    assert paths.output_dir() == os.path.join(veri, "output")
    assert paths.assets_dir() == os.path.join(veri, "assets")
    assert paths.static_dir() == os.path.join(paths.REPO_DIR, "static")
    ayarlar = ayar.Ayarlar.varsayilan()
    assert (ayarlar.data_dir, ayarlar.output_dir) == (veri, os.path.join(veri, "output"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert paths.data_dir() == veri


def test_an_empty_kromis_data_dir_is_ignored(monkeypatch):
    """Boş dize "ayarlanmadı" demek — `KROMIS_DATA_DIR=` yazan bir compose dosyası
    kökü "" yapıp göreli yollara düşürmesin."""
    monkeypatch.setenv(paths.DATA_DIR_ENV, "")
    assert paths.data_dir() == paths.REPO_DIR


def test_frozen_mode_writes_under_application_support(monkeypatch):
    """macOS dalı. `sys.platform` SAHTELENİYOR: bu iddia macOS'un yerleşimini
    ölçüyor, koşan makinenin yerleşimini değil — aksi halde aynı test Windows'ta
    kırmızıya düşer ve iki platformun yerleşimi tek testte karışırdı."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass-test", raising=False)

    expected_data = os.path.join(
        os.path.expanduser("~/Library/Application Support"), "Kromis")
    assert paths.is_frozen()
    assert paths.data_dir() == expected_data
    assert paths.output_dir() == os.path.join(expected_data, "output")
    assert paths.assets_dir() == os.path.join(expected_data, "assets")


def test_frozen_mode_writes_under_local_appdata_on_windows(monkeypatch):
    """Windows dalı: veri `%LOCALAPPDATA%\\Kromis` altına gider.

    Roaming (`%APPDATA%`) DEĞİL: bu dizin üretilen görselleri tutuyor ve etki
    alanı profilinde ağ üzerinden taşınması istenmez.
    """
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Kullanicilar\test\AppData\Local")

    expected_data = os.path.join(r"C:\Kullanicilar\test\AppData\Local",
                                 "Kromis")
    assert paths.data_dir() == expected_data
    assert paths.output_dir() == os.path.join(expected_data, "output")
    assert paths.assets_dir() == os.path.join(expected_data, "assets")


def test_frozen_windows_falls_back_when_localappdata_is_missing(monkeypatch):
    """Ortam değişkeni yoksa yol yine çözülmeli — uygulama hiç açılmamaktansa."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    expected = os.path.join(os.path.expanduser("~"), "AppData", "Local",
                            "Kromis")
    assert paths.data_dir() == expected


def test_dev_mode_ignores_the_platform(monkeypatch):
    """Geliştirmede iki platformda da kök repo dizini — 1150+ testin dayandığı
    varsayım, platform dalı eklenirken kazara değişmemeli."""
    monkeypatch.setattr(sys, "platform", "win32")
    assert paths.data_dir() == paths.REPO_DIR


def test_frozen_mode_reads_resources_from_meipass(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass-test", raising=False)

    # Beklenti os.path.join ile kurulur, elle "/" ile DEĞİL: kod zaten
    # os.path.join kullanıyor, yani Windows'ta ayraç "\" olur ve elle yazılmış
    # bir POSIX yolu testi üründe hiçbir kusur yokken kırmızıya düşürür
    # (Windows paketleme turunda birebir bu oldu).
    assert paths.resource_dir() == "/tmp/meipass-test"
    assert paths.static_dir() == os.path.join("/tmp/meipass-test", "static")
    assert paths.bundled_prompts_dir() == os.path.join(
        "/tmp/meipass-test", "bundled", "prompts")


# ── Android dalı ────────────────────────────────────────────────────
# Desen yukarıdakilerle aynı: platform SAHTELENİYOR (burada ortam değişkeniyle),
# böylece iddialar Android'in yerleşimini ölçüyor, koşan makinenin değil.


def test_android_branch_opens_only_with_the_env_var(monkeypatch):
    """Ortam değişkeni yoksa Android dalı KAPALI kalmalı.

    Bu testin var oluş sebebi: Chaquopy'de `sys.platform` "linux" döner. Dal
    platforma bakarak açılsaydı Linux'ta geliştiren biri sessizce Android
    yoluna düşerdi — dalı ortam değişkenine bağlama kararının tek koruması bu.
    """
    monkeypatch.delenv(paths.ANDROID_DATA_ENV, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    assert not paths.is_android()
    assert paths.data_dir() == paths.REPO_DIR


def test_android_writes_under_the_app_private_dir(monkeypatch):
    """Yazılabilir kök Kotlin'in bildirdiği `filesDir`; `~` HİÇ kullanılmıyor."""
    monkeypatch.setenv(paths.ANDROID_DATA_ENV, "/data/user/0/com.zenginby.kromis/files")
    # `~`'ı bilerek saçma bir yere çekiyoruz: bir yol expanduser'a uğrarsa
    # iddia kırmızıya düşsün. Android'de HOME'un tanımsız/"/" olması tam olarak
    # bu sınıf bir hatayı üretirdi.
    monkeypatch.setenv("HOME", "/olmayan-ev")

    kok = "/data/user/0/com.zenginby.kromis/files"
    assert paths.is_android()
    assert paths.data_dir() == kok
    assert paths.output_dir() == os.path.join(kok, "output")
    assert paths.assets_dir() == os.path.join(kok, "assets")
    assert paths.chat_instructions_override() == os.path.join(kok, "chat-instructions.md")


def test_android_beats_the_frozen_branch(monkeypatch):
    """Android dalı frozen dallarının ÖNÜNDE olmalı.

    Chaquopy'de `sys.frozen` yok, ama sıra tersine kurulsaydı bir gün
    eklenecek bir işaret uygulamayı APK'nın salt-okunur içine yazmaya
    çalıştırırdı. Sıra bir davranış, yorum değil — bu yüzden teste bağlandı.
    """
    monkeypatch.setenv(paths.ANDROID_DATA_ENV, "/data/veri")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass-test", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")

    assert paths.data_dir() == "/data/veri"


def test_android_resources_come_from_the_copied_dir(monkeypatch):
    """static/ ve bundled/ APK assets'inden değil, kopyalandıkları dizinden okunur."""
    monkeypatch.setenv(paths.ANDROID_DATA_ENV, "/data/veri")
    monkeypatch.setenv(paths.ANDROID_RESOURCE_ENV, "/data/veri/resources")

    assert paths.resource_dir() == "/data/veri/resources"
    assert paths.static_dir() == os.path.join("/data/veri/resources", "static")
    assert paths.bundled_prompts_dir() == os.path.join(
        "/data/veri/resources", "bundled", "prompts")


def test_android_resource_dir_falls_back_under_data_dir(monkeypatch):
    """Kaynak değişkeni bildirilmezse yerleşim yine çözülmeli.

    Kotlin tarafı kopyalamayı `filesDir/resources/` altına yapıyor; iki taraftan
    biri unutulduğunda uygulama hiç açılmamaktansa doğru yere baksın.
    """
    monkeypatch.setenv(paths.ANDROID_DATA_ENV, "/data/veri")
    monkeypatch.delenv(paths.ANDROID_RESOURCE_ENV, raising=False)

    assert paths.resource_dir() == os.path.join("/data/veri", "resources")


def test_desktop_credential_paths_follow_the_current_app_name(monkeypatch):
    """Kimlik yolları `paths`'te tek yerde; masaüstü değerleri BUNLAR.

    TARİHÇE: bu testin adı `..._are_unchanged` idi ve gerekçesi "değişmesi
    kullanıcının Azure anahtarının kaybolması demek olurdu" diye yazılıydı.
    2026-09-10'da uygulama adı `Lumeo` → `Kromis` olurken yol DEĞİŞTİ; o
    gerekçe silinmedi, karşılığı kuruldu — `paths._migrate_from_old_name`
    dosyayı yeni ada taşıyor. Yani bu yolu bir daha değiştiren, göç
    sabitlerini (`OLD_CONFIG_DIRNAME`) de kaydırmak zorunda.

    `claude-tools` ile paylaşılan dosyanın yolu bu yeniden adlandırmadan
    ETKİLENMİYOR: o dosya başka bir projenin ve adı bizim adımız değil.
    """
    monkeypatch.delenv(paths.ANDROID_DATA_ENV, raising=False)

    assert paths.credentials_path() == os.path.expanduser(
        "~/.config/kromis/credentials.env")
    assert paths.shared_credentials_path() == os.path.expanduser(
        "~/.config/claude-tools/azure-gpt-image2.env")


def test_android_credentials_live_in_the_app_private_dir(monkeypatch):
    monkeypatch.setenv(paths.ANDROID_DATA_ENV, "/data/veri")

    assert paths.credentials_path() == os.path.join("/data/veri", "credentials.env")
    # Paylaşılan claude-tools dosyasının telefonda karşılığı yok.
    assert paths.shared_credentials_path() is None


def test_azure_client_reads_the_paths_module(monkeypatch):
    """`azure_client`'ın sabitleri `paths` ile aynı yeri göstermeli."""
    import azure_client as ac
    assert ac.APP_ENV_PATH == paths.credentials_path()
    assert ac.DEFAULT_ENV_PATH == paths.shared_credentials_path()


def test_candidate_paths_drop_the_missing_shared_file(monkeypatch):
    """Aday listesi `None`'ı elemeli — Android'de paylaşılan dosya yok.

    Elenmeseydi `_parse_env_file(None)` TypeError verirdi: kimlik okumanın
    tamamı, yani uygulamanın açılışı, telefonda patlardı.
    """
    import azure_client as ac
    monkeypatch.setattr(ac, "APP_ENV_PATH", "/data/veri/credentials.env")
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", None)

    assert ac._candidate_paths(None) == ["/data/veri/credentials.env"]
    # Masaüstündeki sıra ve içerik korunuyor.
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", "/ev/paylasilan.env")
    assert ac._candidate_paths(None) == [
        "/data/veri/credentials.env", "/ev/paylasilan.env"]


def test_ensure_data_dirs_runs_on_startup_not_on_import(monkeypatch):
    """Dizin açmak da bir yan etkidir — tohumlamayla aynı gerekçe (I3).

    `import app` eden herhangi bir araç (test, tip denetleyici, betik)
    kullanıcının gerçek `~/Library/Application Support/...` ağacını
    yaratmamalı; dizinler sunucu gerçekten başlarken açılır.
    """
    import app as appmod
    recorder = MagicMock()
    monkeypatch.setattr(appmod.paths, "ensure_data_dirs", recorder)

    TestClient(appmod.app)  # context yok → lifespan çalışmaz
    recorder.assert_not_called()

    with TestClient(appmod.app):
        recorder.assert_called_once()


def test_ensure_data_dirs_is_idempotent(monkeypatch, tmp_path):
    # Göç burada BİLEREK no-op: bu test `makedirs` idempotentliğini ölçüyor ve
    # bu dosya conftest'in göç guard'ından muaf (bkz. `_guard_against_real_migration`)
    # — patchlenmezse gerçek `~/.config/lumeo` dizinine dokunurdu.
    monkeypatch.setattr(paths, "_migrate_from_old_name", lambda: None)
    monkeypatch.setattr(paths, "data_dir", lambda: str(tmp_path / "veri"))

    paths.ensure_data_dirs()
    (tmp_path / "veri" / "output" / "dokunma.txt").write_text("kalmalı", encoding="utf-8")
    paths.ensure_data_dirs()  # ikinci çağrı hiçbir şeyi silmemeli

    assert (tmp_path / "veri" / "output").is_dir()
    assert (tmp_path / "veri" / "assets").is_dir()
    assert (tmp_path / "veri" / "output" / "dokunma.txt").read_text(encoding="utf-8") == "kalmalı"


# ── Ad göçü: Lumeo → Kromis ─────────────────────────────────────────
# Bu bölümün var oluş sebebi, bir önceki yeniden adlandırmadan (gpt-image-studio
# → lumeo) FARKLI: v0.15.0 `Lumeo` adıyla yayınlandı ve KULLANILDI. Yani
# `%LOCALAPPDATA%\Lumeo` ve `~/.config/lumeo/` altında gerçek kullanıcı verisi
# (üretilmiş görseller, kütüphane, Azure anahtarı) duruyor. Göç olmadan yeni
# sürüm boş bir uygulama gibi açılır ve kullanıcı verisini KAYBETTİĞİNİ sanar.
#
# Testlerin çoğu üretimin en alt katmanını (`_move_if_new_is_absent`) ölçüyor:
# kurallar orada ve yollar parametre olduğu için iddialar tmp_path'te kalıyor,
# koşan makinenin ev dizinine hiç dokunmuyor.


def test_migration_moves_the_old_directory(tmp_path):
    eski = tmp_path / "Lumeo"
    (eski / "output").mkdir(parents=True)
    (eski / "output" / "resim.png").write_bytes(b"veri")
    yeni = tmp_path / "Kromis"

    paths._move_if_new_is_absent(str(eski), str(yeni))

    assert not eski.exists(), "eski dizin taşındıktan sonra geride kalmamalı"
    assert (yeni / "output" / "resim.png").read_bytes() == b"veri"


def test_migration_does_not_touch_a_populated_new_directory(tmp_path):
    """En pahalı kırılma bu olurdu: TAZE veriyi bayat veriyle ezmek.

    Kullanıcı yeni adla bir süre çalıştıktan sonra eski dizin hâlâ diskte
    duruyor. Göç koşulsuz olsaydı ikinci bir açılış yeni kütüphaneyi eski
    hâline döndürürdü — ve `rename` atomik olduğu için geri dönüşü olmazdı.
    """
    eski = tmp_path / "Lumeo"
    eski.mkdir()
    (eski / "bayat.txt").write_text("eski", encoding="utf-8")
    yeni = tmp_path / "Kromis"
    yeni.mkdir()
    (yeni / "taze.txt").write_text("yeni", encoding="utf-8")

    paths._move_if_new_is_absent(str(eski), str(yeni))

    assert (yeni / "taze.txt").read_text(encoding="utf-8") == "yeni"
    assert not (yeni / "bayat.txt").exists()
    assert (eski / "bayat.txt").exists(), "hiçbir şey SİLİNMEZ"


def test_migration_uses_an_empty_new_directory(tmp_path):
    """Boş kabuk göçü ENGELLEMEZ.

    `ensure_data_dirs` bir önceki açılışta hedefi açıp bırakmış olabilir (göç
    eklenmeden önce yayınlanmış bir ara sürüm, ya da göçün patladığı bir
    açılış). Boş dizin "kullanıcı yeni adla çalıştı" demek değil; aksi hâlde
    göç bir kez atlanınca BİR DAHA hiç koşmazdı.
    """
    eski = tmp_path / "Lumeo"
    eski.mkdir()
    (eski / "veri.txt").write_text("tasinmali", encoding="utf-8")
    yeni = tmp_path / "Kromis"
    yeni.mkdir()

    paths._move_if_new_is_absent(str(eski), str(yeni))

    assert (yeni / "veri.txt").read_text(encoding="utf-8") == "tasinmali"


def test_migration_is_silent_when_there_is_nothing_to_move(tmp_path):
    """Eski dizin yoksa hedef de YARATILMAZ.

    Yaratılsaydı temiz bir kurulumda `_move_if_new_is_absent` boş bir kabuk
    bırakırdı ve bir sonraki maddenin ("boş dizin göçü engellemez") ölçtüğü
    durumu kendi eliyle üretirdi.
    """
    yeni = tmp_path / "Kromis"

    paths._move_if_new_is_absent(str(tmp_path / "hic-olmayan"), str(yeni))

    assert not yeni.exists()


def test_migration_is_idempotent(tmp_path):
    eski = tmp_path / "Lumeo"
    eski.mkdir()
    (eski / "veri.txt").write_text("bir", encoding="utf-8")
    yeni = tmp_path / "Kromis"

    paths._move_if_new_is_absent(str(eski), str(yeni))
    paths._move_if_new_is_absent(str(eski), str(yeni))  # ikinci çağrı no-op

    assert (yeni / "veri.txt").read_text(encoding="utf-8") == "bir"


def test_migration_swallows_oserror_and_records_it(monkeypatch, tmp_path):
    """Göç hatası uygulamayı açılamaz hâle GETİRMEMELİ; sessiz de kalmamalı.

    Gerçek sebepler: dosya başka bir süreçte açık (Windows), birim
    salt-okunur, ya da iki yol farklı sürücüde (`rename` birimler arası
    çalışmaz). Üçünde de doğru davranış aynı: eski dizin yerinde kalır,
    uygulama açılır, `hata.log` nereye bakılacağını söyler.
    """
    eski = tmp_path / "Lumeo"
    eski.mkdir()
    (eski / "veri.txt").write_text("bir", encoding="utf-8")
    yeni = tmp_path / "Kromis"
    monkeypatch.setattr(paths, "data_dir", lambda: str(tmp_path / "gunluk"))

    def _patla(*a, **k):
        raise OSError("cihaz mesgul")

    monkeypatch.setattr(paths.os, "rename", _patla)
    paths._move_if_new_is_absent(str(eski), str(yeni))  # patlamamalı

    assert (eski / "veri.txt").exists(), "başarısız göç veriyi yerinde bırakmalı"
    kayit = (tmp_path / "gunluk" / "hata.log").read_text(encoding="utf-8")
    assert "Lumeo" in kayit and "Kromis" in kayit and "cihaz mesgul" in kayit


def test_migration_never_runs_on_android(monkeypatch):
    """Telefonda göç YOK — `applicationId` değiştiği için eski uygulamanın
    app-private dizini bu uygulamaya kapalı; taşımaya çalışmak yalnız hata
    üretirdi. Veri kaybı bilinçli ve KURULUM.md'de yazılı."""
    monkeypatch.setenv(paths.ANDROID_DATA_ENV, "/data/veri")
    cagrilar = []
    monkeypatch.setattr(paths, "_move_if_new_is_absent",
                        lambda eski, yeni: cagrilar.append((eski, yeni)))

    paths._migrate_from_old_name()

    assert cagrilar == []


def test_migration_skips_the_data_root_in_dev_mode(monkeypatch):
    """Geliştirmede veri kökü REPO_DIR'dir — taşımak DEPONUN KENDİSİNİ oynatırdı.

    Kimlik dosyası ise frozen'dan bağımsız: kaynaktan çalıştıran da
    `~/.config/<ad>/credentials.env` kullanıyor, o yüzden tek çağrı kalıyor.
    """
    monkeypatch.delenv(paths.ANDROID_DATA_ENV, raising=False)
    cagrilar = []
    monkeypatch.setattr(paths, "_move_if_new_is_absent",
                        lambda eski, yeni: cagrilar.append((eski, yeni)))

    assert not paths.is_frozen()
    paths._migrate_from_old_name()

    assert cagrilar == [(paths._desktop_credentials_path(paths.OLD_CONFIG_DIRNAME),
                         paths.credentials_path())]


def test_migration_moves_both_roots_when_frozen(monkeypatch):
    """Paketlenmiş uygulamada İKİ kök taşınıyor: veri dizini + kimlik dosyası."""
    monkeypatch.delenv(paths.ANDROID_DATA_ENV, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    cagrilar = []
    monkeypatch.setattr(paths, "_move_if_new_is_absent",
                        lambda eski, yeni: cagrilar.append((eski, yeni)))

    paths._migrate_from_old_name()

    assert cagrilar == [
        (paths._desktop_data_root(paths.OLD_APP_NAME), paths.data_dir()),
        (paths._desktop_credentials_path(paths.OLD_CONFIG_DIRNAME),
         paths.credentials_path()),
    ]
    # Eski kök gerçekten ESKİ adı göstermeli; sabit boşalırsa göç sessizce
    # kendi kendini taşımaya çalışırdı.
    assert paths._desktop_data_root(paths.OLD_APP_NAME) != paths.data_dir()


def test_ensure_data_dirs_migrates_before_creating_the_dirs(monkeypatch, tmp_path):
    """SIRA sözleşmenin parçası, süs değil.

    `makedirs` önce koşsaydı hedef dizin göç sırasında ARTIK BOŞ OLMAZDI
    (`output/` ve `assets/` içinde) — "yeni dizin doluysa dokunma" kuralı
    tetiklenir ve göç ilk açılıştan sonra bir daha hiç koşmazdı. Bu iddia o
    yüzden çağrı sırasını değil, göçün GÖRDÜĞÜ dünyayı ölçüyor.
    """
    gordugu = {}

    def _goc():
        gordugu["output_vardi"] = (tmp_path / "veri" / "output").exists()

    monkeypatch.setattr(paths, "_migrate_from_old_name", _goc)
    monkeypatch.setattr(paths, "data_dir", lambda: str(tmp_path / "veri"))

    paths.ensure_data_dirs()

    assert gordugu["output_vardi"] is False
