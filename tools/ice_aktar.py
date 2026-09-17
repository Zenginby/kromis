#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Tek kullanıcılı `KROMIS_DATA_DIR` yerleşimini bir hesaba yükler (Faz 1 / 8).

    DATABASE_URL=… KROMIS_DATA_DIR=/data python tools/ice_aktar.py \\
        --kaynak ~/Library/Application\\ Support/Kromis --eposta ali@ornek.com \\
        [--kimlik-dosyasi ~/.config/kromis/credentials.env] [--kuru] [--yeniden] [--hedef /data]

NEDEN VAR: dondurulmuş masaüstü/Android kabuğu veriyi JSON manifestlerde
tutuyor (`output/history.json`, `folders.json`, `chats.json`, `palettes.json`,
`prefs.json`, `assets/<tur>/index.json`, artı `~/.config/kromis/credentials.env`);
web sürümü aynı veriyi kullanıcı başına DB satırlarında (Faz 1 / 5-7). Bu araç
o manifestleri `json.load` ile OKUYUP satıra ÇEVİRİR — `backup.py`nin "bayt
kopyala" kuralı burada geçerli değil, amaç tam tersi. Web yolu bu dosyaları hiç
açmaz (AST ve çalışma zamanı bekçileri, tests/test_galeri_db.py, conftest);
onları açan tek yer burası.

KAYNAK DOKUNULMAZ: medya ve varlık dosyaları kullanıcının dizinine
(`<hedef>/kullanicilar/<uuid>/{output,assets/<tur>}`) KOPYALANIR, taşınmaz;
kaynak dizinde hiçbir dosya değişmez, silinmez (`paths._move_if_new_is_absent`in
"hiçbir şey silinmez" kuralı). Test kaynağın özetini önce/sonra karşılaştırıyor.

KİMLİKLER KORUNUR: 12 haneli eski id'ler aynen yazılır (`_SAFE_ID` 8-32 kabul
ediyor, belge §2). Yalnız DB'de BAŞKA bir kullanıcının satırıyla çakışan id
yeniden üretilir ve her başvuru yeniden yazılır: `klasorler.parent_id`,
`medya.folder_id`/`parent_id`/`session_id`, `chats.messages[].image_ids`,
arena kardeşleri (`arena_id` başkasınınkiyle çakışıyorsa turun bütün sütunları
aynı yeni id'yi alır). Yeni id RASTGELE DEĞİL TÜRETİLMİŞ — `sha256(kullanici_id
| tablo | eski id)`nin ilk 32 hanesi (`turet`). Belge `uuid4().hex` diyordu;
sapmanın gerekçesi idempotenlik: aynı kaynağı ikinci kez koşturmak (ya da aynı
kaynağı iki hesaba yüklemek — o zaman HER id çakışır) rastgele id ile her
seferinde yeni satır açar, türetilmiş id ile aynı hedef id'yi bulur ve
"var olan" diye atlar. Çıktı yine 32 hane hex, aynı `CHECK`ten geçer.

İDEMPOTENT: bu kullanıcıda `(kullanici_id, id)` zaten varsa satır ATLANIR
(dosyaya da dokunulmaz); `--yeniden` var olanı kaynaktaki kayıtla EZER (satır
güncellenir, dosya yeniden kopyalanır) — kaynakta olmayan satır SİLİNMEZ,
yeniden bir "eşitleme" değil "kaynak kazanır" demektir. `--kuru` her şeyi hesaplar
ve sayıları basar ama hiçbir şey yazmaz: ne DB satırı ne dosya (satırlar
transaksiyonda `flush` edilir ki FK/UNIQUE hataları kuru koşuda da görünsün,
sonda `rollback`).

TEK TRANSAKSİYON, depo başına DEĞİL: depolar birbirine bağlı (`medya.folder_id`
→ `klasorler`, `medya.session_id` → sohbet id'leri, `chats.image_ids` → medya)
ve yarısı yüklenmiş bir hesap hiç yüklenmemiş olandan kötü — kullanıcı
galeriyi görür, klasörleri görmez, sebebini bilmez. Bir depo düşerse hepsi
geri alınır; bu koşuda KOPYALANAN dosyalar da silinir (kaynak değil, hedefe
yeni yazılanlar). Dosya + satır burada da atomik değil (`depo_medya.kaydet`in
kararı): kopya önce, satır sonra; commit düşerse temizlik denenir, kalan artık
dosya 9. görevin `artik_dosya` taramasına.

BOZUK VERİ ARACI DURDURMAZ: dosya JSON değilse ya da liste/nesne değilse o
depo "bozuk dosya" diye raporlanır ve öteki depolar sürer; kayıt sözlük
değilse, `id`si `_SAFE_ID`den geçmiyorsa ya da zorunlu alanı yoksa kayıt
raporlanır ve atlanır. Sonda depo başına özet (aktarılan / var olan /
yeni id / ezilen / dosyası eksik / düşürülen / bozuk) ve bozuk bir şey
atlandıysa çıkış kodu 3 — operatör "her şey geldi mi" sorusunu çıkış
kodundan okusun. `düşürülen`: onarılarak yüklenen alanlar — sarkan
`folder_id`/`parent_id` (FK'yi reddederdi) NULL, bilinmeyen kimlik adı ve
geçersiz tercih düşer; bunlar bozuk sayılmaz, kayıt gelir.

ZAMAN: eski `created_at` (yerel saat, saniye, dilimsiz — `zaman.simdi()`)
`olusturuldu timestamptz`ye yerel saat sayılarak çevrilir, mikrosaniye
alanına listedeki SIRA yazılır: eski galeri liste sırasına göre gösteriyordu
(`reversed(list)`), aynı saniyede yazılmış kayıtlar sırayı böyle korur.
Okunamayan damga koşu anına düşer (yine sıra korunur).

YOKLUK NULL: `imported`/`session_id`/`arena_id`/`kind`/`duration`/`arena_win`
anahtarı olmayan kayıt NULL alır (`services/tablolar.py`nin "yokluğun tanımlı
anlamı var" disiplini); `model` yoksa boş dize (içe aktarımın "üreteni yok"
değeri, `storage.save`in gerekçesi), `credits` yoksa 0. `prefs.json`dan yalnız
`prefs.read_stored`un geçirdiği alanlar gelir (tek kural kümesi); `language`
ayrıca `kullanicilar.dil`e yazılır (dil zinciri tercihi değil onu okuyor,
services/dil.py) — kullanıcı web'de dil seçmişse ezilmez. Ölü `uploads` türü
`logos`a iner (`assets_store.migrate_legacy_uploads`in kararı; web bu işlevi
artık çağırmıyor). Kimlik dosyası `azure_client.read_env_values(yol)` ile
okunur, `depo_kimlik_bilgisi.ADLAR` dışındaki adlar bildirilir ve düşer,
değerler `depo_kimlik_bilgisi.yaz` ile ŞİFRELİ yazılır — `KROMIS_SECRET_KEY`
yalnız bu seçenek verildiğinde ve her şeyden ÖNCE denetlenir. Hiçbir çıktıya
anahtar değeri yazılmaz.

ÇIKIŞ KODLARI: 0 tamam · 1 kullanıcı hatası (hesap yok, kaynak dizin yok,
kimlik dosyası yok) · 2 ortam hatası (`DATABASE_URL`/`KROMIS_SECRET_KEY` yok,
DB'ye ulaşılamıyor) · 3 tamamlandı ama bozuk kayıt/dosya atlandı.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import assets_store  # noqa: E402
import azure_client  # noqa: E402
import prefs  # noqa: E402
from services import ayar, db, depo_kimlik_bilgisi, depo_tercih, hesap, sifre, zaman  # noqa: E402
from services.tablolar import Klasor, Kullanici, Medya, Palet, Sohbet, Tercih, Varlik  # noqa: E402
from storage import _SAFE_ID  # noqa: E402

CIKIS_TAMAM = 0
CIKIS_KULLANICI = 1
CIKIS_ORTAM = 2
CIKIS_BOZUK = 3

# Kaynak yerleşimi — dondurulmuş kabuğun yazdığı yerler (docs/faz1-veritabani-
# hesaplar.md, Envanter). `guncelleme.json` bilerek yok: süreç önbelleği.
KLASORLER = "klasorler"
MEDYA = "medya"
SOHBETLER = "sohbetler"
PALETLER = "paletler"
VARLIKLAR = "varliklar"
TERCIHLER = "tercihler"
KIMLIKLER = "kimlikler"
DEPOLAR: tuple[str, ...] = (KLASORLER, MEDYA, SOHBETLER, PALETLER, VARLIKLAR, TERCIHLER, KIMLIKLER)

KAYNAK_DOSYALARI = {
    KLASORLER: ("output", "folders.json"),
    MEDYA: ("output", "history.json"),
    SOHBETLER: ("output", "chats.json"),
    PALETLER: ("output", "palettes.json"),
    TERCIHLER: ("output", "prefs.json"),
}
VARLIK_TURLERI: tuple[str, ...] = assets_store.KINDS + (assets_store.LEGACY_KIND,)


class IceAktarmaHatasi(Exception):
    """Koşuyu durduran, operatöre söylenecek hata (çıkış kodu çağıranın)."""


@dataclass
class Sayac:
    aktarilan: int = 0
    atlanan: int = 0        # bu kullanıcıda zaten vardı (`--yeniden` yoksa)
    yeni_kimlik: int = 0    # başkasının satırıyla çakıştı, id türetildi
    ezilen: int = 0         # `--yeniden` ile güncellendi
    dosya_eksik: int = 0    # satır geldi, kaynakta dosyası yoktu
    dusurulen: int = 0      # onarılan alan (sarkan bağ, bilinmeyen ad, geçersiz tercih)
    bozuk: int = 0          # atlanan kayıt / okunamayan dosya


@dataclass
class Rapor:
    depolar: dict[str, Sayac] = field(default_factory=lambda: {d: Sayac() for d in DEPOLAR})
    notlar: list[str] = field(default_factory=list)
    kuru: bool = False
    kopyalananlar: list[str] = field(default_factory=list)   # bu koşuda hedefe YENİ yazılanlar

    def not_(self, depo: str, mesaj: str) -> None:
        self.notlar.append(f"{depo}: {mesaj}")

    @property
    def bozuk_toplam(self) -> int:
        return sum(s.bozuk for s in self.depolar.values())

    def tablo(self) -> str:
        basliklar = ("depo", "aktarilan", "var olan", "yeni id", "ezilen", "dosya eksik",
                     "dusurulen", "bozuk")
        satirlar = [[d, str(s.aktarilan), str(s.atlanan), str(s.yeni_kimlik), str(s.ezilen),
                     str(s.dosya_eksik), str(s.dusurulen), str(s.bozuk)]
                    for d, s in self.depolar.items()]
        genislik = [max(len(b), *(len(r[i]) for r in satirlar)) for i, b in enumerate(basliklar)]
        biçim = "  ".join(f"{{:<{g}}}" if i == 0 else f"{{:>{g}}}" for i, g in enumerate(genislik))
        cikti = [biçim.format(*basliklar), biçim.format(*("-" * g for g in genislik))]
        cikti += [biçim.format(*r) for r in satirlar]
        if self.kuru:
            cikti.append("KURU KOSU: hicbir sey yazilmadi (ne satir ne dosya).")
        return "\n".join(cikti)


# ───────────────────────────────────────────────────────────── yardımcılar

def turet(kullanici_id: uuid.UUID, tablo: str, eski: str) -> str:
    """Çakışan eski id için bu kullanıcıya özgü, tekrar üretilebilir 32 haneli hex (gerekçe modül başında)."""
    return hashlib.sha256(f"{kullanici_id}|{tablo}|{eski}".encode()).hexdigest()[:32]


def _gecerli_id(deger: object) -> bool:
    return isinstance(deger, str) and _SAFE_ID.fullmatch(deger) is not None


def _id_ya_da_none(deger: object) -> str | None:
    """Başvuru alanları (`parent_id`, `folder_id`, …): geçerli id ise o, değilse NULL."""
    return deger if isinstance(deger, str) and _gecerli_id(deger) else None


def _metin(deger: object, varsayilan: str = "") -> str:
    return deger if isinstance(deger, str) else varsayilan


def _zaman(deger: object, sira: int, taban: dt.datetime) -> dt.datetime:
    """Eski `created_at` → `timestamptz`; mikrosaniyede liste sırası (gerekçe modül başında)."""
    an = taban
    if isinstance(deger, str):
        try:
            an = dt.datetime.fromisoformat(deger)
        except ValueError:
            pass
    if an.tzinfo is None:
        an = an.astimezone()   # dilimsiz = yerel saat (`zaman.simdi()`nin yazdığı)
    return an.replace(microsecond=sira % 1_000_000)


def _json_oku(yol: str, depo: str, rapor: Rapor, tur: type) -> Any:
    """Dosyayı `json.load` ile okur; yoksa None, bozuksa/türü yanlışsa None + bozuk sayacı."""
    if not os.path.isfile(yol):
        return None
    try:
        with open(yol, encoding="utf-8") as f:
            veri = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as hata:
        rapor.depolar[depo].bozuk += 1
        rapor.not_(depo, f"{yol} okunamadi ({type(hata).__name__}); depo atlandi")
        return None
    if not isinstance(veri, tur):
        rapor.depolar[depo].bozuk += 1
        rapor.not_(depo, f"{yol} beklenen biçimde degil ({tur.__name__} bekleniyordu); depo atlandi")
        return None
    return veri


def _kayitlar(veri: list | None, depo: str, rapor: Rapor,
              zorunlu: dict[str, type]) -> list[tuple[int, dict]]:
    """Listenin geçerli kayıtları `(sıra, kayıt)`; sözlük olmayan, id'si bozuk ya da zorunlu alanı eksik olan bozuk sayılır."""
    gecerli: list[tuple[int, dict]] = []
    for sira, kayit in enumerate(veri or []):
        if not isinstance(kayit, dict) or not _gecerli_id(kayit.get("id")):
            rapor.depolar[depo].bozuk += 1
            rapor.not_(depo, f"{sira}. kayit: sozluk degil ya da id gecersiz; atlandi")
            continue
        eksik = [ad for ad, tur in zorunlu.items() if not isinstance(kayit.get(ad), tur)]
        if eksik:
            rapor.depolar[depo].bozuk += 1
            rapor.not_(depo, f"{kayit['id']}: zorunlu alan eksik/yanlis türde {eksik}; atlandi")
            continue
        gecerli.append((sira, kayit))
    return gecerli


def _kimlik_haritasi(oturum: Session, tablo: Any, kullanici_id: uuid.UUID, kimlikler: Iterable[str],
                     depo: str, rapor: Rapor) -> tuple[dict[str, str], set[str]]:
    """{kaynak id: hedef id} ve hedef id'lerden bu kullanıcıda ZATEN var olanlar.

    Başkasının satırıyla çakışan id türetilir; türetilen id de başkasınınsa
    (256 bitin 128'i, pratikte imkânsız) araç durur — sessizce üçüncü bir
    id uydurmak, iki koşunun aynı sonucu vermesi sözünü bozardı.
    """
    kimlikler = list(dict.fromkeys(kimlikler))
    sahipler: dict[str, uuid.UUID] = {}
    if kimlikler:
        sahipler = {kimlik: sahip for kimlik, sahip in oturum.execute(
            select(tablo.id, tablo.kullanici_id).where(tablo.id.in_(kimlikler)))}
    harita: dict[str, str] = {}
    for k in kimlikler:
        sahip = sahipler.get(k)
        if sahip is None or sahip == kullanici_id:
            harita[k] = k
        else:
            harita[k] = turet(kullanici_id, depo, k)
            rapor.depolar[depo].yeni_kimlik += 1
            rapor.not_(depo, f"{k} baska bir kullanicida var; yeni id {harita[k]}")
    turetilen = [h for k, h in harita.items() if h != k]
    if turetilen:
        for h, sahip in oturum.execute(select(tablo.id, tablo.kullanici_id)
                                       .where(tablo.id.in_(turetilen))).all():
            if sahip != kullanici_id:
                raise IceAktarmaHatasi(f"{depo}: turetilmis id {h} de baska bir kullanicida; "
                                       "elle mudahale gerekir")
            sahipler[h] = sahip
    var_olan = {h for h in harita.values() if sahipler.get(h) == kullanici_id}
    return harita, var_olan


def _kopyala(kaynak: str, hedef: str, kuru: bool, kopyalananlar: list[str]) -> bool:
    """Kaynak dosyayı hedefe kopyalar (`copy2`, taşımaz); kaynak yoksa False. Kuru koşuda yalnız varlığa bakar."""
    if not os.path.isfile(kaynak):
        return False
    if kuru:
        return True
    os.makedirs(os.path.dirname(hedef), exist_ok=True)
    yeni = not os.path.exists(hedef)
    shutil.copy2(kaynak, hedef)
    if yeni:
        kopyalananlar.append(hedef)
    return True


def _ez(satir: object, **alanlar: object) -> None:
    for ad, deger in alanlar.items():
        setattr(satir, ad, deger)


# ───────────────────────────────────────────────────────────── depolar

@dataclass
class Baglam:
    oturum: Session
    kullanici: Kullanici
    kaynak: str
    ozel: ayar.Ayarlar          # hedef: kullanıcının kendi yerleşimi
    rapor: Rapor
    kuru: bool
    yeniden: bool
    taban: dt.datetime
    kopyalananlar: list[str] = field(default_factory=list)

    @property
    def kid(self) -> uuid.UUID:
        return self.kullanici.id

    def kaynak_yolu(self, *parcalar: str) -> str:
        return os.path.join(self.kaynak, *parcalar)


def _klasorler(b: Baglam) -> dict[str, str]:
    """`folders.json` → `klasorler`; ebeveynler önce (FK). Döneni id haritası (medya `folder_id` için)."""
    depo, s = KLASORLER, b.rapor.depolar[KLASORLER]
    veri = _json_oku(b.kaynak_yolu(*KAYNAK_DOSYALARI[depo]), depo, b.rapor, list)
    kayitlar = _kayitlar(veri, depo, b.rapor, {"name": str})
    harita, var_olan = _kimlik_haritasi(b.oturum, Klasor, b.kid, (k["id"] for _, k in kayitlar),
                                        depo, b.rapor)
    hedefler = set(harita.values())

    def yaz(yeni_id: str, sira: int, k: dict, ebeveyn: str | None) -> None:
        alanlar = dict(name=k["name"], parent_id=ebeveyn,
                       olusturuldu=_zaman(k.get("created_at"), sira, b.taban))
        if yeni_id in var_olan:
            if b.yeniden:
                _ez(b.oturum.get(Klasor, yeni_id), **alanlar)
                s.ezilen += 1
            else:
                s.atlanan += 1
            return
        b.oturum.add(Klasor(id=yeni_id, kullanici_id=b.kid, **alanlar))
        s.aktarilan += 1

    bekleyen = {harita[k["id"]]: (sira, k) for sira, k in kayitlar}
    yazilan: set[str] = set(var_olan)
    while bekleyen:
        ilerledi = False
        for yeni_id, (sira, k) in list(bekleyen.items()):
            ebeveyn = _id_ya_da_none(k.get("parent_id"))
            ebeveyn = harita.get(ebeveyn, ebeveyn) if ebeveyn else None
            if ebeveyn is not None and ebeveyn not in hedefler:
                # Sarkan ebeveyn: FK reddederdi, kök klasör olur (eski uygulama
                # da böyle bir klasörü hiçbir ağaçta göstermiyordu).
                b.rapor.not_(depo, f"{k['id']}: ebeveyn {ebeveyn} kaynakta yok; koke alindi")
                s.dusurulen += 1
                ebeveyn = None
            if ebeveyn is not None and ebeveyn not in yazilan:
                continue
            del bekleyen[yeni_id]
            ilerledi = True
            yazilan.add(yeni_id)
            yaz(yeni_id, sira, k, ebeveyn)
        if not ilerledi:
            # Döngü (a → b → a, FK buna izin verir): kalanlar köke alınır.
            for yeni_id, (sira, k) in bekleyen.items():
                b.rapor.not_(depo, f"{k['id']}: ebeveyn zinciri dongulu; koke alindi")
                s.dusurulen += 1
                yaz(yeni_id, sira, k, None)
            bekleyen = {}
    b.oturum.flush()
    return harita


def _sohbet_haritasi(b: Baglam) -> tuple[list[tuple[int, dict]], dict[str, str], set[str]]:
    """Sohbetler iki aşamalı: id haritası medyadan ÖNCE lazım (`session_id`), satırlar medyadan SONRA (`image_ids`)."""
    depo = SOHBETLER
    veri = _json_oku(b.kaynak_yolu(*KAYNAK_DOSYALARI[depo]), depo, b.rapor, list)
    kayitlar = _kayitlar(veri, depo, b.rapor, {"messages": list})
    harita, var_olan = _kimlik_haritasi(b.oturum, Sohbet, b.kid, (k["id"] for _, k in kayitlar),
                                        depo, b.rapor)
    return kayitlar, harita, var_olan


def _medya(b: Baglam, klasor_haritasi: dict[str, str], sohbet_haritasi: dict[str, str]) -> dict[str, str]:
    """`history.json` → `medya` + dosya kopyası. Döneni id haritası (sohbetlerin `image_ids`i için)."""
    depo, s = MEDYA, b.rapor.depolar[MEDYA]
    veri = _json_oku(b.kaynak_yolu(*KAYNAK_DOSYALARI[depo]), depo, b.rapor, list)
    kayitlar = _kayitlar(veri, depo, b.rapor, {"filename": str})
    harita, var_olan = _kimlik_haritasi(b.oturum, Medya, b.kid, (k["id"] for _, k in kayitlar),
                                        depo, b.rapor)
    # `filename` küresel UNIQUE: id çakışmasa da dosya adı başka bir satırda
    # olabilir (elle düzenlenmiş manifest). O zaman da id türetilir — dosya adı
    # id'den türediği için yeni ad boş.
    yeni_eklenecek = {harita[k["id"]]: k["filename"] for _, k in kayitlar
                      if harita[k["id"]] == k["id"] and k["id"] not in var_olan}
    if yeni_eklenecek:
        dolu = set(b.oturum.scalars(select(Medya.filename)
                                    .where(Medya.filename.in_(list(yeni_eklenecek.values())))))
        for eski, ad in yeni_eklenecek.items():
            if ad in dolu:
                harita[eski] = turet(b.kid, depo, eski)
                s.yeni_kimlik += 1
                b.rapor.not_(depo, f"{eski}: dosya adi {ad} DB'de dolu; yeni id {harita[eski]}")
    # Arena turu başkasınınkiyle çakışıyorsa kardeşler birlikte yeni id alır.
    arena_idler = {a for _, k in kayitlar if (a := _id_ya_da_none(k.get("arena_id"))) is not None}
    arena_haritasi: dict[str, str] = {}
    if arena_idler:
        yabanci = {a for a in b.oturum.scalars(select(Medya.arena_id).distinct()
                                                .where(Medya.arena_id.in_(list(arena_idler)),
                                                       Medya.kullanici_id != b.kid)) if a}
        for a in sorted(yabanci):
            arena_haritasi[a] = turet(b.kid, "arena", a)
            b.rapor.not_(depo, f"arena {a} baska bir kullanicida var; tur {arena_haritasi[a]} oldu")
    klasorler = set(klasor_haritasi.values())

    for sira, k in kayitlar:
        yeni_id = harita[k["id"]]
        _, uzanti = os.path.splitext(k["filename"])
        dosya_adi = k["filename"] if yeni_id == k["id"] else f"{yeni_id}{uzanti}"
        klasor = _id_ya_da_none(k.get("folder_id"))
        if klasor is not None:
            klasor = klasor_haritasi.get(klasor, klasor)
            if klasor not in klasorler:
                # Eski uygulama böyle bir kaydı hiçbir listede göstermiyordu
                # (klasör süzgeci boş dönerdi); köke almak onu geri kazandırır.
                b.rapor.not_(depo, f"{k['id']}: klasor {klasor} yok; koke alindi")
                s.dusurulen += 1
                klasor = None
        ebeveyn = _id_ya_da_none(k.get("parent_id"))
        oturum_id = _id_ya_da_none(k.get("session_id"))
        arena = _id_ya_da_none(k.get("arena_id"))
        palet = k.get("palette") if isinstance(k.get("palette"), dict) else None
        try:
            kredi = int(k.get("credits") or 0)
        except (TypeError, ValueError):
            kredi = 0
        try:
            sure = int(k["duration"]) if k.get("duration") else None
        except (TypeError, ValueError):
            sure = None
        alanlar = dict(
            filename=dosya_adi,
            prompt=_metin(k.get("prompt")),
            size=_metin(k.get("size")),
            quality=_metin(k.get("quality")),
            parent_id=harita.get(ebeveyn, ebeveyn) if ebeveyn else None,
            folder_id=klasor,
            palette=palet,
            prompt_sent=k.get("prompt_sent") if isinstance(k.get("prompt_sent"), str) else None,
            model=_metin(k.get("model")),
            credits=kredi,
            imported=True if k.get("imported") else None,
            session_id=sohbet_haritasi.get(oturum_id, oturum_id) if oturum_id else None,
            arena_id=arena_haritasi.get(arena, arena) if arena else None,
            kind=k.get("kind") if isinstance(k.get("kind"), str) and k.get("kind") else None,
            duration=sure,
            arena_win=True if k.get("arena_win") else None,
            olusturuldu=_zaman(k.get("created_at"), sira, b.taban),
        )
        if yeni_id in var_olan and not b.yeniden:
            s.atlanan += 1
            continue
        if not _kopyala(b.kaynak_yolu("output", k["filename"]),
                        os.path.join(b.ozel.output_dir, dosya_adi), b.kuru, b.kopyalananlar):
            s.dosya_eksik += 1
            b.rapor.not_(depo, f"{k['id']}: kaynakta {k['filename']} yok; satir yine yazildi")
        if yeni_id in var_olan:
            _ez(b.oturum.get(Medya, yeni_id), **alanlar)
            s.ezilen += 1
        else:
            b.oturum.add(Medya(id=yeni_id, kullanici_id=b.kid, **alanlar))
            s.aktarilan += 1
    b.oturum.flush()
    return harita


def _sohbetler(b: Baglam, kayitlar: list[tuple[int, dict]], harita: dict[str, str],
               var_olan: set[str], medya_haritasi: dict[str, str]) -> None:
    """`chats.json` → `sohbetler`; `image_ids` medya haritasından geçer, `cover_image_id` türetilir (yazılmaz)."""
    s = b.rapor.depolar[SOHBETLER]
    for sira, k in kayitlar:
        yeni_id = harita[k["id"]]
        mesajlar = []
        for m in k["messages"]:
            if isinstance(m, dict) and isinstance(m.get("image_ids"), list):
                m = {**m, "image_ids": [medya_haritasi.get(i, i) if isinstance(i, str) else i
                                        for i in m["image_ids"]]}
            mesajlar.append(m)
        alanlar = dict(title=_metin(k.get("title")), mesajlar=mesajlar,
                       olusturuldu=_zaman(k.get("created_at"), sira, b.taban),
                       guncellendi=_zaman(k.get("updated_at") or k.get("created_at"), sira, b.taban))
        if yeni_id in var_olan:
            if b.yeniden:
                _ez(b.oturum.get(Sohbet, yeni_id), **alanlar)
                s.ezilen += 1
            else:
                s.atlanan += 1
            continue
        b.oturum.add(Sohbet(id=yeni_id, kullanici_id=b.kid, **alanlar))
        s.aktarilan += 1
    b.oturum.flush()


def _paletler(b: Baglam) -> None:
    depo, s = PALETLER, b.rapor.depolar[PALETLER]
    veri = _json_oku(b.kaynak_yolu(*KAYNAK_DOSYALARI[depo]), depo, b.rapor, list)
    kayitlar = _kayitlar(veri, depo, b.rapor, {})
    harita, var_olan = _kimlik_haritasi(b.oturum, Palet, b.kid, (k["id"] for _, k in kayitlar),
                                        depo, b.rapor)
    for sira, k in kayitlar:
        yeni_id = harita[k["id"]]
        renkler = k.get("colors") if isinstance(k.get("colors"), list) else []
        alanlar = dict(name=_metin(k.get("name")), seed=_metin(k.get("seed")),
                       mode=_metin(k.get("mode")), strength=_metin(k.get("strength")),
                       colors=renkler, olusturuldu=_zaman(k.get("created_at"), sira, b.taban))
        if yeni_id in var_olan:
            if b.yeniden:
                _ez(b.oturum.get(Palet, yeni_id), **alanlar)
                s.ezilen += 1
            else:
                s.atlanan += 1
            continue
        b.oturum.add(Palet(id=yeni_id, kullanici_id=b.kid, **alanlar))
        s.aktarilan += 1
    b.oturum.flush()


def _varliklar(b: Baglam) -> None:
    """`assets/<tur>/index.json` ×4 → `varliklar` + dosya; ölü `uploads` → `logos`."""
    depo, s = VARLIKLAR, b.rapor.depolar[VARLIKLAR]
    toplanan: list[tuple[int, str, str, dict]] = []   # (sıra, kaynak tür, hedef tür, kayıt)
    sira = 0
    for tur in VARLIK_TURLERI:
        veri = _json_oku(b.kaynak_yolu("assets", tur, assets_store.MANIFEST_FILE), depo, b.rapor, list)
        hedef_tur = assets_store.LEGACY_TARGET if tur == assets_store.LEGACY_KIND else tur
        for _, k in _kayitlar(veri, depo, b.rapor, {"filename": str}):
            toplanan.append((sira, tur, hedef_tur, k))
            sira += 1
    harita, var_olan = _kimlik_haritasi(b.oturum, Varlik, b.kid, (k["id"] for *_, k in toplanan),
                                        depo, b.rapor)
    for sira, tur, hedef_tur, k in toplanan:
        yeni_id = harita[k["id"]]
        dosya_adi = k["filename"] if yeni_id == k["id"] else f"{yeni_id}.png"
        alanlar = dict(filename=dosya_adi, name=_metin(k.get("name")), tur=hedef_tur,
                       olusturuldu=_zaman(k.get("created_at"), sira, b.taban))
        if yeni_id in var_olan and not b.yeniden:
            s.atlanan += 1
            continue
        if not _kopyala(b.kaynak_yolu("assets", tur, k["filename"]),
                        os.path.join(b.ozel.assets_dir, hedef_tur, dosya_adi), b.kuru, b.kopyalananlar):
            s.dosya_eksik += 1
            b.rapor.not_(depo, f"{tur}/{k['id']}: kaynakta {k['filename']} yok; satir yine yazildi")
        if yeni_id in var_olan:
            _ez(b.oturum.get(Varlik, yeni_id), **alanlar)
            s.ezilen += 1
        else:
            b.oturum.add(Varlik(id=yeni_id, kullanici_id=b.kid, **alanlar))
            s.aktarilan += 1
    b.oturum.flush()


def _tercihler(b: Baglam) -> None:
    """`prefs.json` → `tercihler` (tek satır) + `kullanicilar.dil`; yalnız `prefs.read_stored`un geçirdiği alanlar."""
    depo, s = TERCIHLER, b.rapor.depolar[TERCIHLER]
    yol = b.kaynak_yolu(*KAYNAK_DOSYALARI[depo])
    ham = _json_oku(yol, depo, b.rapor, dict)
    if ham is None:
        return
    gecerli = prefs.read_stored(os.path.dirname(yol))
    dusen = sorted(set(ham) - set(gecerli))
    if dusen:
        s.dusurulen += len(dusen)
        b.rapor.not_(depo, f"gecersiz/bilinmeyen alanlar dusuruldu: {dusen}")
    if b.oturum.get(Tercih, b.kid) is not None and not b.yeniden:
        s.atlanan += len(gecerli)
        return
    ezme = b.oturum.get(Tercih, b.kid) is not None
    try:
        depo_tercih.guncelle(b.oturum, b.kid, dict(gecerli), now=b.taban)
    except depo_tercih.GecersizTercih as hata:
        # Tek çapraz kural `chat_model` ↔ `chat_provider` (`prefs.update`);
        # modeli düşürüp geri kalanı yaz.
        b.rapor.not_(depo, f"{hata.kod}: chat_model dusuruldu")
        s.dusurulen += 1
        gecerli.pop("chat_model", None)
        depo_tercih.guncelle(b.oturum, b.kid, dict(gecerli), now=b.taban)
    if gecerli.get("language") and (b.kullanici.dil is None or b.yeniden):
        b.kullanici.dil = gecerli["language"]
    if ezme:
        s.ezilen += len(gecerli)
    else:
        s.aktarilan += len(gecerli)
    b.oturum.flush()


def _kimlikler(b: Baglam, dosya: str) -> None:
    """`credentials.env` → `saglayici_kimlikleri` (şifreli). Bilinmeyen ad bildirilir ve düşer; değer basılmaz."""
    depo, s = KIMLIKLER, b.rapor.depolar[KIMLIKLER]
    degerler = azure_client.read_env_values(dosya)
    bilinmeyen = sorted(ad for ad in degerler if ad not in depo_kimlik_bilgisi.ADLAR)
    if bilinmeyen:
        s.dusurulen += len(bilinmeyen)
        b.rapor.not_(depo, f"bilinmeyen adlar dusuruldu: {bilinmeyen}")
    dolu = {ad: d for ad, d in degerler.items() if ad in depo_kimlik_bilgisi.ADLAR and d}
    mevcut = set(depo_kimlik_bilgisi.oku(b.oturum, b.kid))
    yazilacak = {ad: d for ad, d in dolu.items() if ad not in mevcut or b.yeniden}
    s.atlanan += len(dolu) - len(yazilacak)
    if yazilacak:
        depo_kimlik_bilgisi.yaz(b.oturum, b.kid, yazilacak, now=b.taban)
    for ad in yazilacak:
        if ad in mevcut:
            s.ezilen += 1
        else:
            s.aktarilan += 1


def aktar(oturum: Session, kullanici: Kullanici, kaynak: str, ozel: ayar.Ayarlar, *,
          kimlik_dosyasi: str | None = None, kuru: bool = False, yeniden: bool = False) -> Rapor:
    """Bütün depoları TEK transaksiyonda yükler; commit/rollback ÇAĞIRANIN (kuru koşu rollback).

    Sıra bağımlılığa göre: klasörler (FK) → sohbet haritası (`session_id`) →
    medya (dosyalar) → sohbet satırları (`image_ids`) → paletler → varlıklar →
    tercihler → kimlikler. Bir depo ortasında düşerse `flush` edilmiş her şey
    çağıranın `rollback`ıyla gider; kopyalanan dosyalar `temizle` ile.
    """
    b = Baglam(oturum=oturum, kullanici=kullanici, kaynak=kaynak, ozel=ozel, rapor=Rapor(kuru=kuru),
               kuru=kuru, yeniden=yeniden, taban=zaman.an())
    if not kuru:
        # `ayar._dizinleri_ac` ile aynı kural: kullanıcı kökü 0o700.
        os.makedirs(ozel.kullanici_koku(kullanici.id), mode=0o700, exist_ok=True)
        os.makedirs(ozel.output_dir, exist_ok=True)
        os.makedirs(ozel.assets_dir, exist_ok=True)
    try:
        klasor_haritasi = _klasorler(b)
        sohbet_kayitlari, sohbet_haritasi, sohbet_var = _sohbet_haritasi(b)
        medya_haritasi = _medya(b, klasor_haritasi, sohbet_haritasi)
        _sohbetler(b, sohbet_kayitlari, sohbet_haritasi, sohbet_var, medya_haritasi)
        _paletler(b)
        _varliklar(b)
        _tercihler(b)
        if kimlik_dosyasi:
            _kimlikler(b, kimlik_dosyasi)
    except BaseException:
        temizle(b.kopyalananlar)
        raise
    b.rapor.kopyalananlar = b.kopyalananlar
    return b.rapor


def temizle(kopyalananlar: list[str]) -> None:
    """Bu koşuda HEDEFE yeni yazılan dosyaları siler (DB geri alındıysa). Kaynağa dokunmaz."""
    for yol in kopyalananlar:
        try:
            os.remove(yol)
        except OSError:
            pass


# ───────────────────────────────────────────────────────────── CLI

def _ayristirici() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ice_aktar.py",
        description="Tek kullanicili KROMIS_DATA_DIR yerlesimini bir hesaba yukler (DB + dosya kopyasi).")
    p.add_argument("--kaynak", required=True, help="eski KROMIS_DATA_DIR (output/ ve assets/ burada)")
    p.add_argument("--eposta", required=True, help="hedef hesap (once tools/kullanici.py olustur)")
    p.add_argument("--kimlik-dosyasi", default=None,
                   help="eski credentials.env; KROMIS_SECRET_KEY ister, degerler sifreli yazilir")
    p.add_argument("--hedef", default=None,
                   help="web surumunun KROMIS_DATA_DIR'i; verilmezse ortamdaki KROMIS_DATA_DIR / paths.data_dir()")
    p.add_argument("--kuru", action="store_true", help="sayilari bas, hicbir sey yazma")
    p.add_argument("--yeniden", action="store_true",
                   help="bu kullanicida var olan satirlari kaynaktakiyle EZ (dosyalar yeniden kopyalanir)")
    return p


def main(argv: list[str]) -> int:
    args = _ayristirici().parse_args(argv)
    url = db.baglanti_dizesi()
    if not url:
        print(f"{db.DATABASE_URL_ENV} verilmedi: bu arac veri tabanina baglanir.", file=sys.stderr)
        return CIKIS_ORTAM
    if args.kimlik_dosyasi:
        try:
            sifre.dogrula_ortam()
        except sifre.AnahtarHatasi as hata:
            print(str(hata), file=sys.stderr)
            return CIKIS_ORTAM
        if not os.path.isfile(args.kimlik_dosyasi):
            print(f"kimlik dosyasi yok: {args.kimlik_dosyasi}", file=sys.stderr)
            return CIKIS_KULLANICI
    kaynak = os.path.abspath(args.kaynak)
    if not os.path.isdir(kaynak):
        print(f"kaynak dizin yok: {kaynak}", file=sys.stderr)
        return CIKIS_KULLANICI
    genel = ayar.Ayarlar.varsayilan()
    if args.hedef:
        genel = dataclasses.replace(genel, data_dir=os.path.abspath(args.hedef))

    motor = db.motor_kur(url)
    try:
        with Session(motor) as oturum:
            kullanici = hesap.kullanici_bul(oturum, args.eposta.strip())
            if kullanici is None:
                print(f"{args.eposta} diye bir hesap yok; once: python tools/kullanici.py olustur "
                      f"--eposta {args.eposta}", file=sys.stderr)
                return CIKIS_KULLANICI
            kullanici_id, eposta = kullanici.id, kullanici.eposta
            ozel = genel.kullanici_icin(kullanici_id)
            if os.path.realpath(os.path.join(kaynak, "output")) == os.path.realpath(ozel.output_dir):
                print("kaynak ile hedef ayni dizin; kopyalanacak bir sey yok", file=sys.stderr)
                return CIKIS_KULLANICI
            rapor = aktar(oturum, kullanici, kaynak, ozel, kimlik_dosyasi=args.kimlik_dosyasi,
                          kuru=args.kuru, yeniden=args.yeniden)
            if args.kuru:
                oturum.rollback()
            else:
                try:
                    oturum.commit()
                except BaseException:
                    temizle(rapor.kopyalananlar)
                    raise
    except IceAktarmaHatasi as hata:
        print(str(hata), file=sys.stderr)
        return CIKIS_KULLANICI
    except SQLAlchemyError as hata:
        print(f"veri tabani hatasi ({type(hata).__name__}): {str(hata).splitlines()[0]}",
              file=sys.stderr)
        return CIKIS_ORTAM
    finally:
        motor.dispose()

    for satir in rapor.notlar:
        print(satir, file=sys.stderr)
    print(f"hesap: {eposta} ({kullanici_id})\nkaynak: {kaynak}\nhedef: {ozel.kullanici_koku(kullanici_id)}")
    print(rapor.tablo())
    return CIKIS_BOZUK if rapor.bozuk_toplam else CIKIS_TAMAM


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
