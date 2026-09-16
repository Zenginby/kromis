"""Kullanıcı metninin YANIT BAŞLIĞINA ve ZIP yoluna indiği yerin bekçisi.

Ölçülmüş kusur: klasör adı `/api/folders/{id}/download` ucunda
`Content-Disposition` DEĞERİNE giriyordu ve oradaki süzgeç (`[^\\w\\s-]`) `\\s`
sınıfı yüzünden CR/LF'yi KORUYORDU. Adı `kotu\\r\\nX-Injected: yes` olan bir
klasörde başlık `attachment; filename="kotu\\r\\nX-Injected_yes…` olarak
kuruluyordu — yani kullanıcı metni yanıt başlıklarının arasına satır atabiliyor.

Bugünkü uvicorn o başlığı reddediyor (`RuntimeError: Invalid HTTP header
value`), yani gözlenen sonuç yanıt bölme DEĞİL, yakalanmamış bir ASGI hatası ve
o klasörün kalıcı olarak indirilemez olmasıydı. Savunmanın ASGI SUNUCUSUNUN
sürümünde durması kabul edilemez: başka bir sunucunun altında aynı girdi
gerçek bir response splitting olur. Bu yüzden iki kapı var ve ikisi de burada
ayrı ayrı sınanıyor:

  1. ÇIKIŞ — `folders.safe_component`: adı ne olursa olsun başlığa/ZIP yoluna
     tek satırlık bir ad iner. Asıl kapı bu, çünkü DEPODAKİ eski adlar da
     bu yoldan geçiyor.
  2. GİRİŞ — `FolderRequest`: kontrol karakteri taşıyan ad hiç kaydedilmez.
"""
import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app as appmod
import folders
from models import FolderRequest

# Denemenin kendisi: iki satır sonu + araya sıkıştırılmış sahte bir başlık.
KOTU_AD = "kotu\r\nX-Injected: yes\r\n\r\nPWNED"

# "Görünmeyen" sayılan ve adın içinden düşmesi gereken karakterler.
KONTROL_KARAKTERLERI = ["\r", "\n", "\t", "\x00", "\x0b", "\x0c", "\x1b", "\x7f"]


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    return TestClient(appmod.app)


# ── 1. kapı: çıkış süzgeci ──────────────────────────────────────────

@pytest.mark.parametrize("ch", KONTROL_KARAKTERLERI)
def test_safe_component_drops_every_control_character(ch):
    assert ch not in folders.safe_component(f"once{ch}sonra")


def test_safe_component_keeps_the_words_around_a_newline():
    """CR/LF DÜŞÜRÜLMÜYOR, boşluğa İNİYOR: iki kelime birbirine yapışmamalı."""
    assert folders.safe_component("kotu\r\nad") == "kotu_ad"


def test_safe_component_cannot_produce_a_path_or_a_parent_reference():
    """`.` ve `/` de düşüyor — ZIP girdisi zip-slip taşıyamaz."""
    assert folders.safe_component("../../etc/passwd") == "etcpasswd"


def test_safe_component_falls_back_when_nothing_survives():
    assert folders.safe_component("!!!") == "klasor"
    assert folders.safe_component("") == "klasor"


def test_safe_component_leaves_ordinary_turkish_names_alone():
    """Kusuru kapatan değişiklik sıradan adları BOZMAMALI."""
    assert folders.safe_component("Yaz Kampanyası 2026") == "Yaz_Kampanyası_2026"


# ── 2. kapı: giriş doğrulaması ──────────────────────────────────────

@pytest.mark.parametrize("ch", KONTROL_KARAKTERLERI)
def test_folder_request_rejects_control_characters(ch):
    with pytest.raises(ValidationError):
        FolderRequest(name=f"once{ch}sonra")


def test_folder_request_accepts_visible_punctuation_and_emoji():
    """Reddedilen ÇİZİLMEYEN karakter; görünür her şey geçerli bir klasör adı."""
    assert FolderRequest(name="Müşteri #3 — logolar 🎨").name


def test_create_folder_route_rejects_a_crlf_name(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/folders", json={"name": KOTU_AD}).status_code == 422


# ── İkisi birlikte: uçtan uca ───────────────────────────────────────

def test_download_header_has_no_line_break_even_for_a_stored_bad_name(
        tmp_path, monkeypatch):
    """Depoda ZATEN böyle bir ad varsa (giriş kapısından önce açılmış klasör)
    indirme yine de çalışmalı ve başlık tek satır kalmalı."""
    c = _client(tmp_path, monkeypatch)
    # Rotayı ATLAYARAK doğrudan depoya yaz: giriş kapısı artık bunu geçirmiyor,
    # ama v0.x'te açılmış bir klasör diskte hâlâ böyle durabilir.
    fid = folders.create(KOTU_AD, appmod.OUTPUT_DIR, now="2026-01-01T00:00:00")["id"]

    r = c.get(f"/api/folders/{fid}/download")

    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    assert "\r" not in cd and "\n" not in cd
    assert "X-Injected" not in r.headers          # sahte başlık DOĞMADI
    assert cd.startswith('attachment; filename="kotu_X-Injected_yes_PWNED.zip"')


def test_download_header_still_carries_the_utf8_name(tmp_path, monkeypatch):
    """Türkçe ad `filename*` tarafında AYNEN duruyor — düzeltme onu bozmadı."""
    c = _client(tmp_path, monkeypatch)
    fid = folders.create("Şubat Çalışması", appmod.OUTPUT_DIR,
                         now="2026-01-01T00:00:00")["id"]

    cd = c.get(f"/api/folders/{fid}/download").headers["content-disposition"]

    assert "filename*=UTF-8''%C5%9Eubat%20%C3%87al%C4%B1%C5%9Fmas%C4%B1.zip" in cd


def test_no_route_builds_a_header_from_the_old_pattern():
    """Süzgecin ÜÇÜNCÜ bir kopyası doğmasın: `\\s` koruyan desen kaynakta yok.

    Kusurun kökü desenin İKİ yerde kopyalanmış olmasıydı; biri düzeltilip
    öteki unutulabilirdi. Tek yer `folders.safe_component`."""
    for yol in ("app.py", "folders.py"):
        with open(yol, encoding="utf-8") as f:
            kaynak = f.read()
        # Yorumlarda desen ANLATILIYOR (gerekçe orada yaşıyor); aranan şey
        # çalıştırılabilir bir `re.sub(...)` çağrısı.
        assert not re.search(r"re\.sub\(\s*r?['\"]\[\^\\w\\s-\]", kaynak), yol
