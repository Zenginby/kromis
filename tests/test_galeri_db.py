"""Galeri ve klasörler DB'de — Faz 1 / 5'in bekçileri (docs/faz1-veritabani-hesaplar.md §5).

Dört soru, dört aile:

  (i)   SAHİPLİK — `services/depo_medya.py` ve `depo_klasor.py`de sorgu kuran
        HER işlev `kullanici_id`yi imzasında alıyor ve `WHERE`ine koyuyor
        (kaynak taraması) — ve iki kullanıcı depo düzeyinde birbirinin
        satırını ne listeler ne bulur ne siler (çalışma zamanı).
  (ii)  MANİFEST WEB YOLUNDAN ÇIKTI — `routers/`, `services/` ve `app.py`
        `storage`/`folders`ün manifest okuyan/yazan işlevlerini ÇAĞIRMAZ;
        saf yardımcılar (`media_type_for`, `safe_component` …) serbest.
  (iii) ŞEKİL — DB satırının JSON dökümü `storage.save`/`folders.create`
        kaydıyla anahtar anahtar, SIRA dâhil aynı; `created_at` aynı biçim;
        koşullu alanlar aynı koşulla var/yok.
  (iv)  ANLAM — klasör silme görseli köke düşürür ve alt ağacı götürür
        (SET NULL / CASCADE), görsel silme satır + dosya, arena kazananı tur
        başına tek ve tek UPDATE, aynı saniyedeki dört satır üretim sırasını
        korur (mikrosaniye).

Rota düzeyindeki iki-kullanıcı izolasyonu tests/test_kimlik.py'de (gerçek
çerezle); burada depo katmanı ve şekil. Postgres GERÇEK (`depo_db`).

FAZ 1 / 6: (i) ve (ii) aileleri altı depo modülüne ve altı dondurulmuş depoya
genişledi — `chat_store`/`palette_store`/`assets_store`/`prefs`in manifest
işlevleri de web yolunda çağrılamaz, `depo_sohbet`/`depo_palet`/`depo_varlik`/
`depo_tercih` de aynı imza ve süzgeç sözleşmesini taşır. O dört deponun (iii)
ve (iv) aileleri kendi dosyalarında: tests/test_{sohbet,palet,varlik,tercih}_db.py.

FAZ 2 / 1: sekizinci depo `services/kuyruk.py` — kullanıcı tarafı aynı imza ve
süzgeç sözleşmesini taşır; işçi tarafı (`al`, `kalp`, `bitir`, `dusur`,
`bayatlari_dusur`, `isci_*`) KİRACISIZ ve bunun defteri `KIRACISIZ`: işçi
platformun, kimsenin değil — muaf işlev `kullanici_id` ALMAZ (alsa süzmesi
gerekirdi), ilk parametresi `db`. Kuyruğun anlamı tests/test_kuyruk.py'de.
"""
from __future__ import annotations

import ast
import datetime as dt
import glob
import os
import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import app as appmod
import assets_store
import azure_client as ac
import chat_store
import folders
import palette_store
import prefs
import storage
from services import depo_klasor, depo_medya, hesap, tablolar, zaman

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Depo modülü → sorgu kuran EN AZ kaç işlev bekleniyor (bekçinin bekçisi: sıfıra
# düşen bir tarama "hepsi süzüyor" derdi). Sayılar kaynağın bugünkü hâli.
DEPOLAR = {
    "services/depo_medya.py": 9, "services/depo_klasor.py": 4,
    "services/depo_sohbet.py": 3, "services/depo_palet.py": 2,
    "services/depo_varlik.py": 3, "services/depo_tercih.py": 1,
    "services/depo_kimlik_bilgisi.py": 4,   # Faz 1 / 7
    "services/kuyruk.py": 10,               # Faz 2 / 1 (3 kullanıcı + 7 işçi tarafı; `ekle`/`isci_kaydet` `db.add`)
}
# `depo_*.py` kalıbının DIŞINDA kalan depolar — `test_the_repository_list_matches_the_files_on_disk`
# bunları da bekler; kalıba uymayan yeni bir depo buraya yazılmadan listeye giremez.
EK_DEPOLAR = ("services/kuyruk.py",)
# Kiracısız işlevler (Faz 2 / 1): işçi işi kimliğiyle sürer, kullanıcıyı bilmez —
# `al` kuyruğun BAŞINI alır (küresel FIFO, kimin işi olduğuna bakmaz), ötekiler
# `al`ın verdiği `is_id`/`isci_id` ile çalışır. Her ad gerekçesiyle; bekçinin
# bekçisi adların gerçek olduğunu ve muaf işlevin `kullanici_id` ALMADIĞINI sınar.
KIRACISIZ = {
    "services/kuyruk.py": {
        "al": "işçi kuyruğun başındaki işi alır; kiracı süzgeci FIFO'yu bozar",
        "kalp": "işçi elindeki işin kalp atışı; `is_id` `al`dan geldi",
        "bitir": "işçi elindeki işi kapatır; `is_id` `al`dan geldi",
        "dusur": "işçi elindeki işi düşürür; `is_id` `al`dan geldi",
        "bayatlari_dusur": "periyodik bakım: bütün kiracıların bayat işleri",
        "isci_kaydet": "`isciler` tablosunda kullanıcı sütunu yok",
        "isci_kalp": "`isciler` tablosunda kullanıcı sütunu yok",
        "isci_sil": "`isciler` tablosunda kullanıcı sütunu yok",
    },
}
DONDURULMUS = {"storage": storage, "folders": folders, "chat_store": chat_store,
               "palette_store": palette_store, "assets_store": assets_store, "prefs": prefs}

# Dondurulmuş depoların MANİFESTE dokunan işlevleri — web yolunda çağrılamaz.
# Saf yardımcılar (`ext_for`, `media_path_of`, `media_type_for`, `valid_id`,
# `safe_component`, `MEDIA_TYPES`, `cover_from`, `KINDS`, `_SCHEMA`, `_ENUMS`,
# `DEFAULTS`) listede DEĞİL: onlar dosya adı/MIME/şema kararı, manifestle
# ilgileri yok — depo modülleri onları ithal ediyor, kopyalamıyor.
MANIFEST_ISLEVLERI = {
    "storage": ("save", "list_history", "set_folder", "set_folder_many", "delete",
                "delete_many", "unfile_folder", "unfile_folders", "arena_round",
                "set_arena_winner", "_read_history", "_write_history", "_history_path"),
    "folders": ("create", "list_folders", "exists", "depth", "descendants", "delete_tree",
                "rename", "export_zip", "_read", "_write", "_folders_path"),
    # Faz 1 / 6
    "chat_store": ("create", "list_chats", "get", "update", "delete", "delete_all",
                   "_read", "_write", "_chats_path"),
    "palette_store": ("create", "list_palettes", "delete", "_read", "_write", "_palettes_path"),
    "assets_store": ("save_asset", "list_assets", "asset_path", "delete_asset",
                     "migrate_legacy_uploads", "_read_manifest", "_write_manifest",
                     "_manifest_path", "_kind_dir"),
    "prefs": ("read", "read_stored", "update", "_read_raw", "_write", "_prefs_path"),
}


# Kimlik DOSYASININ işlevleri (Faz 1 / 7, belge §7 çıkış ölçütü): web yolunda
# ÇAĞRILMAZ — kimlik kullanıcı başına DB'den (`depo_kimlik_bilgisi`), dosya
# dondurulmuş kabuğun ve `tools/ice_aktar.py`nin. Modülden bağımsız AD listesi:
# `ac.load_credentials` de `cc.load_credentials` de yakalanır. Saf ikizleri
# (`credentials_of`, `chat_credentials_of`, `settings_status_of`, `check_base_url`)
# serbest — dosya okumazlar.
KIMLIK_DOSYASI_ISLEVLERI = frozenset({
    "credentials_path", "shared_credentials_path",           # paths
    "save_env", "save_credentials", "read_env_values", "load_credentials",
    "resolve_chat_credentials", "get_settings_status",       # azure_client / chat_client
    "_parse_env_all", "_parse_env_file", "_candidate_paths", "_first_complete_credentials",
})
# Web yolu: bileşim kökü + paketler + kimliği çözen/sevk eden kök modüller.
KIMLIK_WEB_MODULLERI = ("credstore.py", "chat_providers.py", "providers.py")


def _oku(yol: str) -> str:
    with open(os.path.join(REPO, yol), encoding="utf-8") as f:
        return f.read()


def _web_yolu_dosyalari() -> list[str]:
    return ["app.py"] + sorted(os.path.relpath(p, REPO) for p in
                               glob.glob(os.path.join(REPO, "routers", "*.py")) +
                               glob.glob(os.path.join(REPO, "services", "*.py")))


# ── (ii) manifest web yolundan çıktı ──────────────────────────────────

def test_no_web_module_calls_a_manifest_function_of_storage_or_folders():
    """Belge §5 çıkış ölçütü: `history.json`/`folders.json` web yolunda hiç açılmıyor.

    Metin DEĞİL AST: gerekçe yorumları eski işlevleri adıyla anıyor
    (`storage.save`in kuralları …) ve o anmalar meşru. Aranan şey ÇAĞRI:
    `storage.<manifest işlevi>(…)` ya da `from storage import <o işlev>`.
    """
    for yol in _web_yolu_dosyalari():
        agac = ast.parse(_oku(yol))
        for dugum in ast.walk(agac):
            if isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Attribute) \
                    and isinstance(dugum.func.value, ast.Name):
                modul, ad = dugum.func.value.id, dugum.func.attr
                assert ad not in MANIFEST_ISLEVLERI.get(modul, ()), (
                    f"{yol}:{dugum.lineno}: `{modul}.{ad}(` — manifest web yolunda okunmaz/yazılmaz "
                    "(depo_medya/depo_klasor kullan)")
            if isinstance(dugum, ast.ImportFrom) and dugum.module in MANIFEST_ISLEVLERI:
                for takma in dugum.names:
                    assert takma.name not in MANIFEST_ISLEVLERI[dugum.module], (
                        f"{yol}: `from {dugum.module} import {takma.name}` — manifest işlevi")


def test_no_web_module_calls_a_credentials_file_function():
    """Belge §7 çıkış ölçütü: `credentials.env` web yolunda hiç açılmıyor — kaynak taraması.

    AST, metin DEĞİL (manifest bekçisiyle aynı gerekçe): yorumlar eski işlevleri
    adıyla anıyor. Aranan şey ÇAĞRI (`x.save_env(`, `load_credentials(`) ya da
    `from … import <işlev>`. Çalışma zamanı ikizi conftest'te:
    `_web_yolunda_kimlik_dosyasi_acilmaz` DB'li testlerde dosya okuyucuyu patlatır.
    """
    for yol in _web_yolu_dosyalari() + list(KIMLIK_WEB_MODULLERI):
        agac = ast.parse(_oku(yol))
        for dugum in ast.walk(agac):
            if isinstance(dugum, ast.Call):
                ad = (dugum.func.attr if isinstance(dugum.func, ast.Attribute)
                      else dugum.func.id if isinstance(dugum.func, ast.Name) else None)
                assert ad not in KIMLIK_DOSYASI_ISLEVLERI, (
                    f"{yol}:{dugum.lineno}: `{ad}(` — kimlik dosyası web yolunda okunmaz/yazılmaz "
                    "(depo_kimlik_bilgisi / credstore kullan)")
            if isinstance(dugum, ast.ImportFrom) and dugum.module in ("azure_client", "chat_client", "paths"):
                for takma in dugum.names:
                    assert takma.name not in KIMLIK_DOSYASI_ISLEVLERI, (
                        f"{yol}: `from {dugum.module} import {takma.name}` — kimlik dosyası işlevi")


def test_the_credentials_file_function_list_still_names_real_functions():
    """Bekçinin bekçisi: liste `azure_client`/`chat_client`/`paths`teki gerçek adları saymalı."""
    import chat_client
    import paths
    for ad in KIMLIK_DOSYASI_ISLEVLERI:
        assert any(callable(getattr(m, ad, None)) for m in (ac, chat_client, paths)), (
            f"{ad} hiçbir modülde yok — listeyi güncelle")


def test_the_manifest_function_list_still_matches_the_frozen_modules():
    """Bekçinin bekçisi: liste dondurulmuş modüllerdeki gerçek adları saymalı (yeniden adlandırma görünür)."""
    assert set(MANIFEST_ISLEVLERI) == set(DONDURULMUS)
    for modul, adlar in MANIFEST_ISLEVLERI.items():
        for ad in adlar:
            assert callable(getattr(DONDURULMUS[modul], ad, None)), f"{modul}.{ad} yok — listeyi güncelle"


def test_the_repository_list_matches_the_files_on_disk():
    """`services/depo_*.py` diskte ne varsa listede o var — yeni depo bekçisiz kalmaz."""
    diskte = sorted(os.path.relpath(p, REPO) for p in glob.glob(os.path.join(REPO, "services", "depo_*.py")))
    assert sorted(diskte + list(EK_DEPOLAR)) == sorted(DEPOLAR), f"listeyi güncelle: {diskte}"
    for yol in EK_DEPOLAR:
        assert os.path.isfile(os.path.join(REPO, yol)), yol


def test_the_tenantless_function_list_names_real_functions_that_take_no_owner():
    """Muafiyet defterinin bekçisi: ad gerçek, işlev `kullanici_id` almıyor (alsa süzmesi gerekirdi)."""
    for yol, adlar in KIRACISIZ.items():
        assert yol in DEPOLAR, yol
        islevler = {f.name: f for f in _islevler(yol)}
        for ad, gerekce in adlar.items():
            assert gerekce.strip(), f"{yol}::{ad} gerekçesiz"
            assert ad in islevler, f"{yol}::{ad} yok — defteri güncelle"
            parametreler = [a.arg for a in islevler[ad].args.args + islevler[ad].args.kwonlyargs]
            assert "kullanici_id" not in parametreler, (
                f"{yol}::{ad} `kullanici_id` alıyor — kiracısız değil, muafiyeti kaldır")


# ── (i) sahiplik süzgeci: kaynak ───────────────────────────────────────

def _islevler(yol: str) -> list[ast.FunctionDef]:
    return [d for d in ast.walk(ast.parse(_oku(yol))) if isinstance(d, ast.FunctionDef)]


def _sorgu_kuruyor(islev: ast.FunctionDef) -> bool:
    for d in ast.walk(islev):
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) \
                and d.func.id in ("select", "update", "delete"):
            return True
    return False


def _sahip_suzgeci_var(islev: ast.FunctionDef) -> bool:
    """`X.kullanici_id == kullanici_id` karşılaştırması ya da `_sahibin(kullanici_id)` çağrısı."""
    for d in ast.walk(islev):
        if isinstance(d, ast.Compare) and isinstance(d.left, ast.Attribute) \
                and d.left.attr == "kullanici_id" and len(d.comparators) == 1 \
                and isinstance(d.comparators[0], ast.Name) \
                and d.comparators[0].id == "kullanici_id":
            return True
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "_sahibin" \
                and any(isinstance(a, ast.Name) and a.id == "kullanici_id" for a in d.args):
            return True
    return False


@pytest.mark.parametrize("yol", sorted(DEPOLAR))
def test_every_query_building_function_filters_by_the_owner(yol):
    """Sorgu kuran her işlev `kullanici_id` parametresi alır VE onu süzgece koyar.

    `_sahibin(kullanici_id)` `SELECT … WHERE kullanici_id = :ben`in tek yazımı;
    `update`/`delete` onu kullanamadığı için karşılaştırmayı açık yazar. İkisi
    de yoksa o işlev başkasının satırına dokunabiliyor demek.
    """
    sorgulu = [f for f in _islevler(yol) if _sorgu_kuruyor(f)]
    assert len(sorgulu) >= DEPOLAR[yol], f"{yol}: taranan işlev şüpheli biçimde az ({len(sorgulu)})"
    muaf = KIRACISIZ.get(yol, {})
    for f in sorgulu:
        if f.name in muaf:
            continue
        parametreler = [a.arg for a in f.args.args + f.args.kwonlyargs]
        assert "kullanici_id" in parametreler, f"{yol}::{f.name} `kullanici_id` almıyor"
        assert _sahip_suzgeci_var(f), f"{yol}::{f.name} sorgusunda sahip süzgeci yok"


@pytest.mark.parametrize("yol", sorted(DEPOLAR))
def test_every_public_function_takes_the_session_and_the_owner_first(yol):
    """İmza sözleşmesi: `(db, kullanici_id, …)` — `output_dir`in yerine geçen şey (belge §2/§5).

    Sınıf gövdesindeki `__init__` (depo_tercih.GecersizTercih) alt çizgiyle başlıyor, taranmaz.
    """
    for f in _islevler(yol):
        if f.name.startswith("_") or f.name == "safe_component":
            continue
        adlar = [a.arg for a in f.args.args]
        if f.name in KIRACISIZ.get(yol, {}):
            assert adlar[:1] == ["db"], f"{yol}::{f.name}{adlar}"
            continue
        assert adlar[:2] == ["db", "kullanici_id"], f"{yol}::{f.name}{adlar}"


# ── (i) sahiplik: çalışma zamanı ───────────────────────────────────────

def _ikinci_kullanici(db) -> uuid.UUID:
    k = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                           dogrulandi_at=hesap.simdi())
    db.add(k)
    db.flush()
    return k.id


def test_two_users_never_see_each_others_rows_at_the_repository_layer(db_oturumu, kullanici, tmp_path):
    a, b = kullanici.id, _ikinci_kullanici(db_oturumu)
    out_a, out_b = str(tmp_path / "a"), str(tmp_path / "b")
    ka = depo_klasor.olustur(db_oturumu, a, "A klasoru")
    ma = depo_medya.kaydet(db_oturumu, a, b"\x89PNG", {"prompt": "a", "folder_id": ka["id"],
                                                        "arena_id": "aaaa1111bbbb"}, out_a)
    db_oturumu.commit()

    # B listelerinde A'nın hiçbir şeyi yok.
    assert depo_klasor.listele(db_oturumu, b) == []
    assert depo_medya.listele(db_oturumu, b) == []
    assert depo_medya.listele(db_oturumu, b, folder_id=ka["id"]) == []
    assert depo_medya.klasor_sayilari(db_oturumu, b) == {}
    assert depo_medya.arena_turu(db_oturumu, b, "aaaa1111bbbb") == []
    # B, A'nın id'leriyle hiçbir şey bulamaz/değiştiremez/silemez.
    assert depo_klasor.var_mi(db_oturumu, b, ka["id"]) is False
    assert depo_klasor.derinlik(db_oturumu, b, ka["id"]) == 0
    assert depo_klasor.altagac(db_oturumu, b, ka["id"]) == []
    assert depo_klasor.yeniden_adlandir(db_oturumu, b, ka["id"], "calinti") is None
    assert depo_klasor.zip_disa_aktar(db_oturumu, b, ka["id"], out_a) is None
    assert depo_klasor.agaci_sil(db_oturumu, b, ka["id"]) == []
    assert depo_medya.bul(db_oturumu, b, ma["id"]) is None
    assert depo_medya.dosya_yolu(db_oturumu, b, ma["id"], out_a) is None
    assert depo_medya.dosya_yolu_adiyla(db_oturumu, b, ma["filename"], out_a) is None
    assert depo_medya.klasor_ata(db_oturumu, b, ma["id"], None) is False
    assert depo_medya.klasor_ata_coklu(db_oturumu, b, [ma["id"]], None) == 0
    assert depo_medya.klasorden_cikar(db_oturumu, b, [ka["id"]]) == 0
    assert depo_medya.arena_kazanani(db_oturumu, b, "aaaa1111bbbb", ma["id"]) is False
    assert depo_medya.sil(db_oturumu, b, ma["id"], out_b) is False
    assert depo_medya.sil_coklu(db_oturumu, b, [ma["id"]], out_b) == 0
    # …ve A'nın verisi yerinde.
    assert [m["id"] for m in depo_medya.listele(db_oturumu, a, folder_id=ka["id"])] == [ma["id"]]
    assert depo_klasor.listele(db_oturumu, a)[0]["name"] == "A klasoru"
    assert os.path.isfile(os.path.join(out_a, ma["filename"]))


# ── (iii) şekil: DB dökümü = manifest kaydı ────────────────────────────

TAM_META = {"prompt": "kedi", "size": "1024x1024", "quality": "high", "parent_id": "aaaaaaaaaaaa",
            "folder_id": None, "palette": {"seed": "#c86a3c", "colors": [{"hex": "#c86a3c", "name": "Kiremit"}]},
            "prompt_sent": "kedi, Kiremit", "imported": True, "session_id": "bbbbbbbbbbbb",
            "arena_id": "cccccccccccc", "kind": "video", "duration": "6", "model": "veo", "credits": 7}
YALIN_META = {"prompt": "kedi", "size": "1024x1024", "quality": "low"}


@pytest.mark.parametrize("meta", [TAM_META, YALIN_META], ids=["butun-alanlar", "yalin"])
def test_the_row_dump_equals_the_manifest_record_key_for_key(meta, db_oturumu, kullanici, tmp_path):
    """Anahtarlar, SIRA ve değerler aynı; yalnız üretilen üçlü (`id`, `filename`, `created_at`) farklı.

    Ön yüz kayıt alanlarını adıyla okuyor (`static/folders.js`, `chat.js`);
    `tests/test_legacy_formats.py` kümeye bakıyor. Burada SIRA da eşit: ayrışmanın
    ilk belirtisi ve `list(dict)` ucuz.
    """
    an = dt.datetime(2026, 9, 17, 14, 3, 22, 123456).astimezone()
    eski = storage.save(b"x", dict(meta), str(tmp_path / "eski"), now=zaman.damga(an))
    yeni = depo_medya.kaydet(db_oturumu, kullanici.id, b"x", dict(meta), str(tmp_path / "yeni"), now=an)
    assert list(eski) == list(yeni)
    for anahtar in eski:
        if anahtar in ("id", "filename"):
            continue
        assert eski[anahtar] == yeni[anahtar], anahtar
    assert yeni["filename"] == yeni["id"] + storage.ext_for(meta.get("kind"))
    assert re.fullmatch(r"[0-9a-f]{32}", yeni["id"]) and storage.valid_id(yeni["id"])
    # DB'den geri okunan döküm de aynı (JSONB gidiş-dönüşü, koşullu alanlar).
    db_oturumu.commit()
    okunan = depo_medya.bul(db_oturumu, kullanici.id, yeni["id"])
    assert okunan == yeni


def test_the_folder_dump_equals_the_manifest_record(db_oturumu, kullanici, tmp_path):
    an = dt.datetime(2026, 9, 17, 14, 3, 22, 5).astimezone()
    eski = folders.create("Kurban", str(tmp_path), parent_id="aaaaaaaaaaaa", now=zaman.damga(an))
    ust = depo_klasor.olustur(db_oturumu, kullanici.id, "Ust", now=an)
    yeni = depo_klasor.olustur(db_oturumu, kullanici.id, "Kurban", parent_id=ust["id"], now=an)
    assert list(eski) == list(yeni)
    assert (eski["name"], eski["created_at"]) == (yeni["name"], yeni["created_at"])
    assert yeni["parent_id"] == ust["id"]


def test_created_at_keeps_the_manifest_format_to_the_second():
    """`zaman.damga` = `zaman.simdi()` biçimi: yerel saat, saniye, saat dilimi YOK.

    `static/folders.js` bu dizeyi `localeCompare` ile sıralıyor; mikrosaniye ya
    da `+03:00` eki ISO sıralamasını korur ama eski kayıtlarla karışık listede
    bayt düzeyinde farklı görünürdü ve alan-kaybı bekçisi biçime bakmıyor.
    """
    yerel = dt.datetime(2026, 9, 17, 14, 3, 22, 999999).astimezone()
    assert zaman.damga(yerel) == "2026-09-17T14:03:22"
    assert zaman.damga(yerel.astimezone(dt.UTC)) == "2026-09-17T14:03:22", "dilim yerel saate çevrilir"
    assert zaman.damga(dt.datetime(2026, 9, 17, 14, 3, 22)) == "2026-09-17T14:03:22", "dilimsiz = yerel"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", zaman.simdi())
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", zaman.damga(zaman.an()))
    assert zaman.an().tzinfo is not None and zaman.an().microsecond is not None


# ── (iv) anlam ─────────────────────────────────────────────────────────

def _client(tmp_path, monkeypatch, dizinler) -> TestClient:
    dizinler(output_dir=str(tmp_path / "output"))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    return TestClient(appmod.app)


def _uret(uret_ve_bitir, c, folder_id=None, **ek):
    govde = {"prompt": "kedi", "size": "1024x1024", "quality": "low", "n": 1, **ek}
    if folder_id:
        govde["folder_id"] = folder_id
    r = uret_ve_bitir(c, "/api/generate", json=govde)
    assert r.status_code == 200, r.text
    return r.json()["images"]


def test_deleting_a_folder_tree_unfiles_media_and_cascades_subfolders(tmp_path, monkeypatch, dizinler,
                                                                     db_oturumu, kullanici, uret_ve_bitir):
    """Rota: `deleted` ağacın tamamı (üstten alta), `unfiled` görsel sayısı; DB: satırlar gitti, `folder_id` NULL, dosyalar duruyor."""
    c = _client(tmp_path, monkeypatch, dizinler)
    kok = c.post("/api/folders", json={"name": "Kok"}).json()["folder"]["id"]
    cocuk = c.post("/api/folders", json={"name": "Cocuk", "parent_id": kok}).json()["folder"]["id"]
    torun = c.post("/api/folders", json={"name": "Torun", "parent_id": cocuk}).json()["folder"]["id"]
    kardes = c.post("/api/folders", json={"name": "Kardes"}).json()["folder"]["id"]
    gorseller = [_uret(uret_ve_bitir, c, fid)[0] for fid in (kok, cocuk, torun, torun)]
    kardesin = _uret(uret_ve_bitir, c, kardes)[0]

    r = c.delete(f"/api/folders/{kok}")
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": [kok, cocuk, torun], "folders": 3, "unfiled": 4}

    kalan = {k.id for k in db_oturumu.scalars(
        select(tablolar.Klasor).where(tablolar.Klasor.kullanici_id == kullanici.id))}
    assert kalan == {kardes}
    for g in gorseller:
        satir = db_oturumu.get(tablolar.Medya, g["id"])
        assert satir is not None and satir.folder_id is None
        assert (tmp_path / "output" / g["filename"]).is_file()
    assert db_oturumu.get(tablolar.Medya, kardesin["id"]).folder_id == kardes
    assert {g["id"] for g in c.get("/api/history").json()["images"]} == {g["id"] for g in gorseller}


def test_deleting_media_removes_the_row_and_the_file_in_that_order_contract(tmp_path, monkeypatch, dizinler,
                                                                             db_oturumu, kullanici, uret_ve_bitir):
    c = _client(tmp_path, monkeypatch, dizinler)
    g = _uret(uret_ve_bitir, c)[0]
    dosya = tmp_path / "output" / g["filename"]
    assert dosya.is_file() and db_oturumu.get(tablolar.Medya, g["id"]) is not None

    assert c.delete(f"/api/image/{g['id']}").json() == {"deleted": g["id"]}
    db_oturumu.expire_all()
    assert db_oturumu.get(tablolar.Medya, g["id"]) is None
    assert not dosya.exists()
    assert c.delete(f"/api/image/{g['id']}").status_code == 404
    # `storage.delete` sözleşmesi: kaydı olmayan ama dosyası olan id de silinmiş sayılır…
    (tmp_path / "output" / "deadbeef0000.png").write_bytes(b"x")
    assert depo_medya.sil(db_oturumu, kullanici.id, "deadbeef0000", str(tmp_path / "output")) is True
    assert not (tmp_path / "output" / "deadbeef0000.png").exists()
    # …ve dosyası olmayan kaydı silmek de başarılı.
    yalniz_satir = depo_medya.kaydet(db_oturumu, kullanici.id, b"x", {"prompt": "p"}, str(tmp_path / "baska"))
    os.remove(tmp_path / "baska" / yalniz_satir["filename"])
    assert depo_medya.sil(db_oturumu, kullanici.id, yalniz_satir["id"], str(tmp_path / "baska")) is True


def test_bulk_delete_counts_rows_and_stray_files_like_the_manifest_store(tmp_path, monkeypatch, dizinler,
                                                                        db_oturumu, kullanici, uret_ve_bitir):
    c = _client(tmp_path, monkeypatch, dizinler)
    a, b = _uret(uret_ve_bitir, c)[0], _uret(uret_ve_bitir, c)[0]
    (tmp_path / "output" / "deadbeef0000.png").write_bytes(b"x")
    r = c.request("DELETE", "/api/images", json={"ids": [a["id"], b["id"], "deadbeef0000",
                                                         "yokboyle", "../kacis"]})
    assert r.json() == {"deleted": 3}
    assert sorted(p.name for p in (tmp_path / "output").iterdir()) == []
    assert c.get("/api/history").json()["images"] == []


def test_bulk_helpers_guard_bad_ids_in_the_db_twin(db_oturumu, kullanici, tmp_path):
    """tests/test_folders.py'deki `storage` guard testlerinin DB ikizi."""
    out = str(tmp_path / "output")
    g = depo_medya.kaydet(db_oturumu, kullanici.id, b"x", {"prompt": "x"}, out)
    for bad in ("../../etc/passwd", "not-hex", "", None):
        assert depo_medya.klasor_ata_coklu(db_oturumu, kullanici.id, [bad], None) == 0
        assert depo_medya.sil_coklu(db_oturumu, kullanici.id, [bad], out) == 0
        assert depo_medya.klasor_ata(db_oturumu, kullanici.id, bad, None) is False
        assert depo_medya.bul(db_oturumu, kullanici.id, bad) is None
        assert depo_klasor.altagac(db_oturumu, kullanici.id, bad) == []
        assert depo_klasor.agaci_sil(db_oturumu, kullanici.id, bad) == []
    assert depo_medya.klasorden_cikar(db_oturumu, kullanici.id, ["aabbccddeeff"]) == 0
    assert depo_medya.klasorden_cikar(db_oturumu, kullanici.id, []) == 0
    assert [m["id"] for m in depo_medya.listele(db_oturumu, kullanici.id)] == [g["id"]]


def test_the_serving_paths_require_the_row_not_just_the_file(db_oturumu, kullanici, tmp_path):
    """Satırı olmayan dosya sunulmaz, dosyası olmayan satır da: servis yolunun gerçeği ikisi birden."""
    out = str(tmp_path / "output")
    g = depo_medya.kaydet(db_oturumu, kullanici.id, b"x", {"prompt": "x"}, out)
    assert depo_medya.dosya_yolu_adiyla(db_oturumu, kullanici.id, g["filename"], out) == os.path.join(out, g["filename"])
    assert depo_medya.dosya_yolu(db_oturumu, kullanici.id, g["id"], out) == os.path.join(out, g["filename"])
    (tmp_path / "output" / "deadbeef0000.png").write_bytes(b"x")
    assert depo_medya.dosya_yolu_adiyla(db_oturumu, kullanici.id, "deadbeef0000.png", out) is None
    assert depo_medya.dosya_yolu(db_oturumu, kullanici.id, "deadbeef0000", out) is None
    os.remove(os.path.join(out, g["filename"]))
    assert depo_medya.dosya_yolu_adiyla(db_oturumu, kullanici.id, g["filename"], out) is None
    assert depo_medya.dosya_yolu(db_oturumu, kullanici.id, g["id"], out) is None


def test_four_records_written_in_the_same_second_keep_their_production_order(db_oturumu, kullanici, tmp_path):
    """`/api/generate` n=4: liste en yeni üstte, arena turu üretim sırasında — saniye yetmez, mikrosaniye var."""
    out = str(tmp_path / "output")
    ids = [depo_medya.kaydet(db_oturumu, kullanici.id, b"x", {"prompt": f"s{i}", "arena_id": "aaaa1111bbbb"},
                             out)["id"] for i in range(4)]
    assert len({r["created_at"] for r in depo_medya.listele(db_oturumu, kullanici.id)}) <= 2, "aynı saniye (±1)"
    assert [r["id"] for r in depo_medya.arena_turu(db_oturumu, kullanici.id, "aaaa1111bbbb")] == ids
    assert [r["id"] for r in depo_medya.listele(db_oturumu, kullanici.id)] == list(reversed(ids))


def test_the_arena_winner_is_one_per_round_and_only_the_winner_carries_the_key(tmp_path, monkeypatch,
                                                                                dizinler, db_oturumu, kullanici, uret_ve_bitir):
    c = _client(tmp_path, monkeypatch, dizinler)
    tur = "aaaa1111bbbb"
    a, b = _uret(uret_ve_bitir, c, arena_id=tur)[0], _uret(uret_ve_bitir, c, arena_id=tur)[0]
    disarda = _uret(uret_ve_bitir, c)[0]
    assert "arena_win" not in a and "arena_win" not in b

    assert c.post(f"/api/arena/{tur}/winner", json={"image_id": a["id"]}).json() == {"arena_id": tur, "winner": a["id"]}
    kayitlar = {r["id"]: r for r in c.get(f"/api/arena/{tur}").json()["images"]}
    assert kayitlar[a["id"]]["arena_win"] is True and "arena_win" not in kayitlar[b["id"]]
    assert list(kayitlar) == [a["id"], b["id"]], "üretim sırası"
    # Kazanan değişir; tur başına TEK işaret kalır.
    assert c.post(f"/api/arena/{tur}/winner", json={"image_id": b["id"]}).status_code == 200
    kayitlar = {r["id"]: r for r in c.get(f"/api/arena/{tur}").json()["images"]}
    assert "arena_win" not in kayitlar[a["id"]] and kayitlar[b["id"]]["arena_win"] is True
    assert [k.arena_win for k in db_oturumu.scalars(select(tablolar.Medya)
                                                     .where(tablolar.Medya.arena_id == tur)
                                                     .order_by(tablolar.Medya.olusturuldu))] == [False, True]
    # Turun dışındaki görsel bir kazanan olamaz; anahtar taşımaz.
    assert c.post(f"/api/arena/{tur}/winner", json={"image_id": disarda["id"]}).status_code == 404
    assert "arena_win" not in next(r for r in c.get("/api/history").json()["images"] if r["id"] == disarda["id"])


def test_a_twelve_character_legacy_id_and_a_full_uuid_both_pass_the_same_gate(db_oturumu, kullanici, tmp_path):
    """Belge §2: içe aktarılan 12 haneli id KORUNUR, yeni satır tam `uuid4().hex`; kapı `_SAFE_ID` ikisine de açık."""
    db_oturumu.add(tablolar.Medya(id="aabbccddeeff", kullanici_id=kullanici.id, filename="aabbccddeeff.png",
                                  prompt="eski", size="", quality="", model="", credits=0))
    db_oturumu.flush()
    yeni = depo_medya.kaydet(db_oturumu, kullanici.id, b"x", {"prompt": "yeni"}, str(tmp_path))
    assert len(yeni["id"]) == 32
    assert depo_medya.bul(db_oturumu, kullanici.id, "aabbccddeeff")["prompt"] == "eski"
    assert depo_medya.klasor_ata(db_oturumu, kullanici.id, "aabbccddeeff", None) is True
    with pytest.raises(IntegrityError):
        db_oturumu.add(tablolar.Medya(id="KISA", kullanici_id=kullanici.id, filename="k.png",
                                      prompt="", size="", quality="", model="", credits=0))
        db_oturumu.flush()
    db_oturumu.rollback()
