"""Sürüm değiştiğinde manifest'lerin BİR KEZ yedeklenmesi.

Neden: ofis çalışanı yükseltmeyi `.app`'i değiştirerek yapıyor. Verisi
`~/Library/Application Support/GPT-Image Studio/` altında kalıyor ve bugün de
kaybolmuyor — ama yeni sürümdeki bir veri biçimi hatası (yeniden adlandırılmış
bir alan, bozulmuş bir yazım) kütüphaneyi okunamaz hale getirebilir ve bunu
ilk fark eden çalışan olur. Yedek o hatanın geri dönüşünü mümkün kılıyor.

Kopyalanan şey yalnızca küçük liste dosyaları (altı JSON, birkaç KB).
GÖRSELLER KOPYALANMAZ — asıl hacim onlar ve zaten yerlerinde duruyorlar.

SERT KURAL: bu modül ASLA `json.load` çağırmaz, BAYT kopyalar. Bütün amaç
dosyanın mevcut sürümce OKUNAMADIĞI durumu atlatmak; yedek yoluna bir parser
koymak, hedge ettiği hatayı miras almak olurdu.

Kapsam dışı bırakılanlar (unutulma değil, karar):
  · `*.png` — asıl hacim, yedeğin amacı değil.
  · `hata.log` — teşhis kaydı, kullanıcı verisi değil.
  · yarım yazımdan kalan `*.tmp` dosyaları — çöp.
  · `credentials.env` — `data_dir` DIŞINDA (~/.config/...) ve Azure API
    ANAHTARINI taşıyor. Kullanıcının zipleyip e-postayla gönderebileceği bir
    klasöre asla girmemeli. Kaynak tablosunu genişletirken bu satır okunmalı.

RETENTION (eski yedeklerin silinmesi) BİLEREK YOK. Yedek başına birkaç KB, yani
20 yükseltmede ~200 KB — görünmez maliyet. Karşılığında silme, kullanıcının veri
dizininden dizin kaldıran tek kod olurdu ve arıza modu tam olarak bu özelliğin
korumak için var olduğu şeyi yok etmek. Gerekirse ayrı ve tek başına geri
alınabilir bir iş olarak eklenir.

Şekil olarak seed.py'nin kardeşi: kökler dışarıdan geçer (modül düzeyinde yol
durumu yok), `now` enjekte edilir, iş bir marker dosyasıyla bir kez yapılır.
"""
from __future__ import annotations

import os
import re
import shutil
import uuid

import assets_store
import chat_store
import folders
import palette_store
import storage

STAMP_FILE = ".last-version"
BACKUPS_DIR = "backups"
UNKNOWN_VERSION = "bilinmeyen"

# (yedek içindeki kök etiketi, o kökün altındaki göreli parçalar)
#
# Dosya adları YAZICILARIN KENDİ sabitlerinden türetiliyor: elle ikinci bir
# liste tutulsa bir sabitin değeri değiştiğinde yedek sessizce boş yedek alırdı.
_SOURCES = (
    ("output", (storage.HISTORY_FILE,)),
    ("output", (folders.FOLDERS_FILE,)),
    ("output", (palette_store.PALETTES_FILE,)),
    # v1.15: kaydedilmiş sohbetler. Bu listeye eklenmezse sürüm değişiminde
    # yedeklenmeyen tek manifest olurdu — ve içindeki prompt'lar başka hiçbir
    # yerde durmuyor (history.json yalnız ÜRETİLMİŞ prompt'u taşıyor).
    ("output", (chat_store.CHATS_FILE,)),
    *(("assets", (kind, assets_store.MANIFEST_FILE)) for kind in assets_store.KINDS),
)

# Yedek dizini adı: "<sürüm>-<YYYY-MM-DD>". Üretici, ürettiği adın bu desene
# uyduğunu doğrular — ayrıştırılamayan bir ad yaratmak, sonradan hiçbir aracın
# tanıyamayacağı bir dizin bırakmak olurdu.
_BACKUP_NAME = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]{0,31}-\d{4}-\d{2}-\d{2}")


def stamp_path(data_dir: str) -> str:
    """`data_dir` altındaki son-görülen-sürüm damgasının yolu."""
    return os.path.join(data_dir, STAMP_FILE)


def backups_root(data_dir: str) -> str:
    """Yedeklerin kökü — `output/` ve `assets/`'in KARDEŞİ.

    İçlerinden birinin altına gömülmedi: yedek ikisinden de kopya taşıyor
    (asimetrik olurdu) ve `output/` ayrıca bir rota tarafından servis ediliyor.
    `data_dir` zaten defter tutma katmanı (`.logos-seeded`, `hata.log`).
    """
    return os.path.join(data_dir, BACKUPS_DIR)


def read_stamp(data_dir: str) -> str | None:
    """Kayıtlı sürüm; damga yok/okunamıyor/boşsa None.

    Düz metin BİLEREK (JSON değil): bir `state.json` bu değişikliğin korunmaya
    çalıştığı hata sınıfının kendisi olan BEŞİNCİ manifest olurdu. Düz metin
    "bozuk" olamaz — herhangi bir çöp APP_VERSION'a eşit olmadığı için hata yönü
    *bir fazla yedek*, yani güvenli taraf. Okuma sınırlı: patolojik bir dosya
    belleğe çekilmesin.
    """
    try:
        with open(stamp_path(data_dir), encoding="utf-8", errors="replace") as f:
            return f.read(64).strip() or None
    except OSError:
        return None


def write_stamp(data_dir: str, version: str) -> None:
    """Damgayı atomik yazar (manifest'lerin `_write` deyimi).

    Yarım yazılmış bir damga "bu sürümü gördüm" der ve yedek bir daha hiç
    alınmazdı; os.replace o pencereyi kapatıyor.
    """
    os.makedirs(data_dir, exist_ok=True)
    path = stamp_path(data_dir)
    tmp_path = f"{path}.{uuid.uuid4().hex[:8]}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(version)
    os.replace(tmp_path, path)


def _existing_sources(output_dir: str, assets_dir: str) -> list[tuple[str, str]]:
    """Var olan manifest'ler: [(yedek içindeki göreli yol, kaynak yol)].

    "Veri var mı" testi DOSYA VARLIĞI, "ayrıştırılmış liste boş değil" değil:
    `[]` içeren bir history.json da kopyalanır ve karar parser'sız kalır
    (bkz. modül docstring'indeki sert kural).
    """
    roots = {"output": output_dir, "assets": assets_dir}
    found = []
    for label, parts in _SOURCES:
        source = os.path.join(roots[label], *parts)
        if os.path.isfile(source):
            found.append((os.path.join(label, *parts), source))
    return found


def backup_manifests_if_version_changed(data_dir: str, output_dir: str,
                                        assets_dir: str, *, version: str,
                                        now: str) -> str | None:
    """Sürüm değiştiyse manifest'leri yedekler; yedek dizinini döner (yoksa None).

    Sıra: KOPYALA → DAMGALA. Damga ancak başarılı kopyadan sonra yazılıyor, yani
    yarım kalmış bir yedek (dolu disk) "yapıldı" diye kaydedilmiyor, sonraki
    açılışta yeniden deneniyor. Bozukken her açılış bir hata.log bloğu demek —
    çalışmayan bir emniyet özelliği için doğru gürültü seviyesi, ve errlog'un
    1 MB rotasyonu büyümeyi zaten sınırlıyor.
    """
    last = read_stamp(data_dir)
    if last == version:
        return None                      # olağan açılış: yapacak iş yok

    sources = _existing_sources(output_dir, assets_dir)
    if not sources:
        # TAZE KURULUM — seed.py'deki "kopyalamadan damgala" ile birebir.
        # Kullanıcının hiç verisi yok; boş bir backups/ dizini açmak anlamsız.
        write_stamp(data_dir, version)
        return None

    # Ad ESKİ (giden) sürümle kuruluyor: o klasördeki baytları O sürüm yazdı ve
    # geri yüklerken sorulan tek soru bu. Yeni sürümle adlandırmak her yedeği
    # onu YAZMAYAN sürümle etiketlerdi.
    #
    # Damga yoksa taze kurulum mu v1.8 yükseltmesi mi ayırt edilemez — ama
    # manifest'lerin varlığı yukarıda bunu zaten söyledi: kullanıcının
    # kütüphanesi var, yani bu bir yükseltme. Sürümü bilmediğimiz için
    # "bilinmeyen" deniyor; v1.9'a geçiş tam olarak bu daldan geçecek ve bu,
    # özelliğin alacağı en değerli yedek.
    name = f"{last or UNKNOWN_VERSION}-{now[:10]}"
    if not _BACKUP_NAME.fullmatch(name):
        raise ValueError(f"geçersiz yedek dizini adı üretildi: {name!r}")

    root = backups_root(data_dir)
    final = os.path.join(root, name)
    # Sahneleme dizini + rename: manifest'lerin `_write` deyiminin dizin hâli.
    # Yarım kopyalanmış bir dizinin geçerli yedek gibi görünmesini engelliyor.
    staging = f"{final}.{uuid.uuid4().hex[:8]}.tmp"
    os.makedirs(staging)
    try:
        for rel, source in sources:
            target = os.path.join(staging, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(source, target)   # BAYT kopya; metadata taşımıyor
        if os.path.exists(final):
            # Aynı gün, damgası düşmüş bir yeniden deneme: mevcut yedek KORUNUR
            # (daha eski, yani hataya daha yakın hâli o taşıyor).
            shutil.rmtree(staging)
        else:
            os.rename(staging, final)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    write_stamp(data_dir, version)
    return final
