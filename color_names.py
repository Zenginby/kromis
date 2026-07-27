"""Renkleri prompt'a uygun İngilizce adlara çevirir.

Neden dış servis sadece BURADA: palet metin prompt'una giriyor ve görsel
modelleri `#b5651d` gibi hex kodlarına zayıf, `"terracotta orange"` gibi
adlara güçlü tepki veriyor. Yani thecolorapi'nin değeri palet üretmek değil,
renkleri isimlendirmek.

Dört katmanlı düşüş — hiçbiri kilitlenemez, hiçbiri istisna sızdırmaz:

1. süreç-içi önbellek (sayfa yenilemelerini de atlatır),
2. thecolorapi `/id` (kısa timeout + devre kesici),
3. gömülü ~90 tasarım/pigment adı, OKLab'da en yakın komşu (ΔE kapılı),
4. OKLCH bantlarından türetilen betimleyici — ASLA başarısız olmaz.

Üretim yolu (`/api/generate`, `/api/edit`) bu modülü `offline=True` ile çağırır
ve ağa hiç çıkmaz; thecolorapi çökse bile görsel üretimi etkilenmez.
"""
from __future__ import annotations

import math
import re
import time
from collections.abc import Iterable

import palette

API_URL = "https://www.thecolorapi.com/id"
API_TIMEOUT = 1.2       # tek istek
API_BUDGET = 2.5        # bir toplu çağrının tamamı
BREAKER_FAILS = 2       # üst üste bu kadar hatadan sonra devre açılır
BREAKER_COOLDOWN = 120.0
MAX_CACHE = 2000

# OKLab'da bu mesafeden uzaktaki tablo girdisi "yakın" sayılmaz; ad uydurmak
# yerine türetilmiş betimleyiciye düşülür.
TABLE_MAX_DISTANCE = 0.10

# Ad üçüncü taraftan geliyor ve Azure'a giden prompt'un içine düşüyor:
# yalnızca harf, rakam, boşluk, kesme ve tire geçer. Satır sonu / açılı
# parantez / noktalama buradan geçemez.
_ALLOWED = re.compile(r"[^A-Za-z0-9 '\-]")
MAX_NAME_LEN = 32
# Gerçek renk adları 1–3 kelimedir. Kelime sınırı, noktalama temizlendikten
# sonra geriye kalan bir talimat cümlesini de kesip atar.
MAX_NAME_WORDS = 3

_CACHE: dict[str, str] = {}
_fail_streak = 0
_offline_until = 0.0


# ── Ton / açıklık / kroma sözcükleri ────────────────────────────────────────

# (üst_sınır°, sözcük). OKLCH ton açıları HSL'den belirgin farklı: turuncu
# 53°, sarı 110°, mavi 264°. Bantlar ölçülerek belirlendi, tahminle değil.
_HUE_BANDS = (
    (40, "red"), (85, "orange"), (125, "yellow"), (170, "green"),
    (220, "teal"), (278, "blue"), (318, "purple"), (350, "magenta"),
)
_HUE_WRAP = "pink"  # 350°–15° arası

_LIGHT_BANDS = ((0.22, "very dark"), (0.40, "dark"), (0.58, "deep"),
                (0.74, ""), (0.88, "light"))
_LIGHT_TOP = "pale"

_CHROMA_BANDS = ((0.08, "muted"), (0.16, ""))
_CHROMA_TOP = "vivid"

_ACHROMATIC_BANDS = ((0.12, "black"), (0.35, "charcoal grey"),
                     (0.62, "grey"), (0.85, "silver grey"))
_ACHROMATIC_TOP = "white"

# Kroması düşük, koyu turuncu/kırmızı = kahverengi. Ton bandı "orange" derdi
# ama modele "brown" demek çok daha doğru sinyal.
_BROWN_MAX_L = 0.52
_BROWN_MAX_C = 0.13


def _band(value: float, bands, top: str) -> str:
    for limit, word in bands:
        if value < limit:
            return word
    return top


def basic_hue(hex_color: str) -> str:
    """Rengin TEK KELİMELİK temel ton adı: red, blue, brown, grey, white…

    Üçüncü taraf adlarının yanına eklenerek kullanılır (bkz. `ensure_basic`).
    """
    lightness, chroma, hue = palette.hex_to_oklch(hex_color)
    if chroma < 0.04:
        return "grey" if 0.12 <= lightness < 0.85 else ("black" if lightness < 0.12 else "white")
    if hue < 15 or hue >= 350:
        return _HUE_WRAP
    word = _band(hue, _HUE_BANDS, _HUE_WRAP)
    if word in ("red", "orange") and lightness < _BROWN_MAX_L and chroma < _BROWN_MAX_C:
        return "brown"
    return word


def derive(hex_color: str) -> str:
    """OKLCH bantlarından betimleyici ad. Her zaman boş olmayan bir metin döner."""
    lightness, chroma, hue = palette.hex_to_oklch(hex_color)
    if chroma < 0.04:
        return _band(lightness, _ACHROMATIC_BANDS, _ACHROMATIC_TOP)
    hue_word = basic_hue(hex_color)
    light_word = _band(lightness, _LIGHT_BANDS, _LIGHT_TOP)
    chroma_word = _band(chroma, _CHROMA_BANDS, _CHROMA_TOP)
    # "pale vivid yellow" kendi içinde çelişiyor ve modele bulanık sinyal
    # veriyor; açık + doygun tek kelimeyle "bright".
    if chroma_word == _CHROMA_TOP and light_word in ("light", _LIGHT_TOP):
        return f"bright {hue_word}"
    return " ".join(w for w in (light_word, chroma_word, hue_word) if w)


# ── Gömülü tasarım adları ───────────────────────────────────────────────────

# (ad, hex, temel_ton). Bilinçli olarak CSS'in 148 adlandırılmış rengi
# DEĞİL: "papayawhip", "gainsboro", "lightgoldenrodyellow" görsel modeline
# kötü sinyal. Buradaki adlar pigment/tasarım sözlüğünden — modelin eğitim
# verisinde gerçekten renk olarak geçen kelimeler.
_TABLE: tuple[tuple[str, str, str], ...] = (
    # kırmızı / bordo
    ("crimson", "#dc143c", "red"), ("scarlet", "#ff2400", "red"),
    ("ruby", "#9b111e", "red"), ("oxblood", "#4a0000", "red"),
    ("burgundy", "#800020", "red"), ("brick", "#8b3a3a", "red"),
    ("cherry", "#d2042d", "red"),
    # pembe / gül
    ("coral", "#ff7f50", "pink"), ("salmon", "#fa8072", "pink"),
    ("rose", "#ff007f", "pink"), ("blush", "#de5d83", "pink"),
    ("dusty rose", "#c08081", "pink"), ("fuchsia", "#c154c1", "pink"),
    ("magenta", "#ff00ff", "magenta"),
    # mor
    ("plum", "#8e4585", "purple"), ("mauve", "#e0b0ff", "purple"),
    ("lavender", "#b57edc", "purple"), ("violet", "#7f00ff", "purple"),
    ("aubergine", "#3d0734", "purple"), ("orchid", "#da70d6", "purple"),
    # mavi
    ("indigo", "#4b0082", "blue"), ("royal blue", "#4169e1", "blue"),
    ("cobalt", "#0047ab", "blue"), ("navy", "#000080", "blue"),
    ("midnight blue", "#191970", "blue"), ("azure", "#007fff", "blue"),
    ("sky blue", "#87ceeb", "blue"), ("powder blue", "#b0e0e6", "blue"),
    ("steel blue", "#4682b4", "blue"), ("slate blue", "#6a5acd", "blue"),
    ("denim", "#1560bd", "blue"), ("periwinkle", "#ccccff", "blue"),
    # turkuaz / camgöbeği
    ("teal", "#008080", "teal"), ("turquoise", "#40e0d0", "teal"),
    ("aquamarine", "#7fffd4", "teal"), ("petrol", "#005f6a", "teal"),
    ("cyan", "#00ffff", "teal"), ("seafoam", "#9fe2bf", "teal"),
    # yeşil
    ("emerald", "#50c878", "green"), ("jade", "#00a86b", "green"),
    ("forest green", "#228b22", "green"), ("olive", "#808000", "green"),
    ("sage", "#9caf88", "green"), ("moss", "#8a9a5b", "green"),
    ("mint", "#98ff98", "green"), ("lime", "#bfff00", "green"),
    ("pine", "#01796f", "green"), ("fern", "#4f7942", "green"),
    # sarı / altın
    ("mustard", "#ffdb58", "yellow"), ("gold", "#ffd700", "yellow"),
    ("amber", "#ffbf00", "yellow"), ("lemon", "#fff700", "yellow"),
    ("wheat", "#f5deb3", "yellow"), ("honey", "#eba937", "yellow"),
    # turuncu
    ("ochre", "#cc7722", "orange"), ("terracotta", "#e2725b", "orange"),
    ("burnt sienna", "#e97451", "orange"), ("rust", "#b7410e", "orange"),
    ("copper", "#b87333", "orange"), ("apricot", "#fbceb1", "orange"),
    ("tangerine", "#f28500", "orange"), ("pumpkin", "#ff7518", "orange"),
    # kahverengi / nötr sıcak
    ("bronze", "#cd7f32", "brown"), ("tan", "#d2b48c", "brown"),
    ("caramel", "#af6e4d", "brown"), ("chocolate", "#7b3f00", "brown"),
    ("coffee", "#6f4e37", "brown"), ("taupe", "#483c32", "brown"),
    ("sand", "#c2b280", "brown"), ("khaki", "#c3b091", "brown"),
    ("umber", "#635147", "brown"), ("sepia", "#704214", "brown"),
    ("walnut", "#5c4033", "brown"), ("clay", "#b66a50", "brown"),
    # açık nötrler
    ("beige", "#f5f5dc", "beige"), ("cream", "#fffdd0", "white"),
    ("ivory", "#fffff0", "white"), ("bone", "#e3dac9", "white"),
    ("off-white", "#faf9f6", "white"), ("pearl", "#eae0c8", "white"),
    ("linen", "#faf0e6", "white"),
    # griler / siyahlar
    ("charcoal", "#36454f", "grey"), ("slate grey", "#708090", "grey"),
    ("silver", "#c0c0c0", "grey"), ("ash grey", "#b2beb5", "grey"),
    ("graphite", "#3b3c36", "grey"), ("gunmetal", "#2a3439", "grey"),
    ("ink black", "#0b0b0d", "black"), ("soft black", "#232326", "black"),
)

# İçe alırken bir kez OKLab'a çevrilir; her arama saf aritmetik olur.
_TABLE_LAB: tuple[tuple[str, str, tuple[float, float, float]], ...] = tuple(
    (name, basic, palette.oklab(hex_color)) for name, hex_color, basic in _TABLE
)


def ensure_basic(name: str, basic: str) -> str:
    """Ada temel ton kelimesini ekler (zaten varsa dokunmaz).

    thecolorapi "Fuzzy Wuzzy", "Sea Buckthorn", "Hippie Blue" gibi adlar
    döndürüyor. Prompt'a olduğu gibi girerlerse jenerik bir addan DAHA KÖTÜ
    sinyal olurlar: model "sea buckthorn"un ne rengi olduğunu bilmez.
    "sea buckthorn orange" ise hem karakteri hem tonu taşır.
    """
    if not name:
        return basic
    # Alt metin araması (kelime değil): "off-white" + "white" → "off-white",
    # "navy blue" + "blue" → "navy blue", ikisinde de tekrar üretmez.
    if basic in name.lower():
        return name
    return f"{name} {basic}"


def sanitize(name: str) -> str:
    """Üçüncü taraf adını prompt'a girmeye uygun hale getirir."""
    if not isinstance(name, str):
        return ""
    words = _ALLOWED.sub(" ", name).split()[:MAX_NAME_WORDS]
    return " ".join(words).lower()[:MAX_NAME_LEN].strip()


def nearest_table(hex_color: str) -> str | None:
    """Gömülü tablodan en yakın ad; hiçbiri yeterince yakın değilse None."""
    target = palette.oklab(hex_color)
    best_name, best_basic, best_distance = None, "", TABLE_MAX_DISTANCE
    for name, basic, lab in _TABLE_LAB:
        distance = math.dist(target, lab)
        if distance < best_distance:
            best_name, best_basic, best_distance = name, basic, distance
    if best_name is None:
        return None
    return ensure_basic(best_name, best_basic)


# ── Ağ katmanı ──────────────────────────────────────────────────────────────

def _fetch_name(hex_color: str) -> str | None:
    """TEST DİKİŞİ: testler bunu monkeypatch eder; ağ yalnızca burada.

    `azure_client` deseniyle aynı: httpx fonksiyon içinde import edilir.
    """
    import httpx

    response = httpx.get(API_URL, params={"hex": hex_color.lstrip("#")},
                         timeout=API_TIMEOUT)
    if response.status_code != 200:
        return None
    value = ((response.json() or {}).get("name") or {}).get("value")
    return value if isinstance(value, str) else None


def _breaker_open() -> bool:
    return time.monotonic() < _offline_until


def _record_failure() -> None:
    """Üst üste hatadan sonra ağı bir süre hiç denememek için.

    Bu olmadan çevrimdışı bir makinede her önbelleklenmemiş renk için
    API_TIMEOUT kadar beklenir — 5 renklik bir palet 6 saniye sürer.
    """
    global _fail_streak, _offline_until
    _fail_streak += 1
    if _fail_streak >= BREAKER_FAILS:
        _offline_until = time.monotonic() + BREAKER_COOLDOWN


def _record_success() -> None:
    global _fail_streak
    _fail_streak = 0


def reset_breaker() -> None:
    """Testler için: modül seviyesindeki devre kesici durumunu sıfırlar."""
    global _fail_streak, _offline_until
    _fail_streak, _offline_until = 0, 0.0
    _CACHE.clear()


def local_name(hex_color: str) -> str:
    """Ağa çıkmadan bulunabilen en iyi ad: tablo eşi, yoksa betimleyici.

    Her zaman boş olmayan bir metin döner — isimlendirmenin taban katmanı.
    """
    return nearest_table(hex_color) or derive(hex_color)


def name_for(hex_color: str, *, offline: bool = False,
             deadline: float | None = None) -> str:
    """Tek rengin adı. Asla istisna fırlatmaz, asla boş dönmez."""
    key = palette.parse_hex(hex_color)
    cached = _CACHE.get(key)
    if cached:
        return cached

    # Gömülü tablo ÖNCE gelir. Ölçülen karşılaştırma (aynı palet):
    #   tablo → brick red, copper orange, steel blue, sky blue, tan brown
    #   API   → rope brown, cedar chest orange, bondi blue, picton blue, tacao orange
    # Kanonik adlar görsel modeline belirgin daha iyi sinyal; API'nin boya
    # kataloğu adlarının ("cedar chest", "tacao") modele anlattığı tek şey
    # zaten bizim eklediğimiz ton kelimesi. Tablo önce olunca ayrıca öneri
    # kartındaki ad ile kaydedilen paletteki ad da tutarlı kalıyor.
    #
    # API böylece tam olarak DEĞER KATTIĞI yerde kalıyor: tablonun yeterince
    # yakın karşılığı olmayan renkler (doygun/sıra dışı tonlar), ki orada
    # alternatif "bright green" gibi jenerik bir betimleyici olurdu.
    local = nearest_table(key)
    if local:
        return local

    blocked = offline or _breaker_open() or (
        deadline is not None and time.monotonic() >= deadline)
    if blocked:
        # Türetilmiş adı ÖNBELLEĞE ALMA: sonraki çevrimiçi çağrı daha iyi bir
        # adla güncelleyebilsin.
        return derive(key)

    # Buradaki local_name çağrıları tabloya ikinci kez bakıyor (yukarıda
    # nearest_table zaten None döndü). Bilinçli: geri düşüş "bulunabilen en iyi
    # yerel ad" olarak kalıyor, "tablonun kaçırdığını biliyoruz" varsayımına
    # bağlanmıyor. Maliyet ~90 kayan nokta karşılaştırması, ihmal edilebilir.
    try:
        raw = _fetch_name(key)
    except Exception:
        _record_failure()
        return local_name(key)

    _record_success()
    cleaned = sanitize(raw or "")
    if not cleaned:
        return local_name(key)
    name = ensure_basic(cleaned, basic_hue(key))
    if len(_CACHE) >= MAX_CACHE:
        _CACHE.clear()  # tek kullanıcılı yerel araç: LRU'ya gerek yok
    _CACHE[key] = name
    return name


# Tekrarlı adı ayırmak için açıklık merdiveni. Grup boyutuna göre seçilir.
_LADDERS = {
    2: ("dark", "light"),
    3: ("dark", "mid", "light"),
    4: ("darkest", "dark", "light", "lightest"),
    5: ("darkest", "dark", "mid", "light", "lightest"),
}


def _distinct(candidate: str, name: str, rank: int, taken: set[str]) -> str:
    """Aday ad zaten alınmışsa tekilliği koruyan bir sonrakine geçer.

    Merdiven sözcüğü tek başına yetmediği iki durum var: (a) aday, listede
    zaten var olan BAŞKA bir adla çakışıyor, (b) sözcük adın içinde olduğu
    için ad hiç değişmedi ve grubun bir diğer üyesiyle aynı kaldı.
    """
    if candidate not in taken:
        return candidate
    alternative = f"shade {rank + 1} {name}"
    counter = 2
    while alternative in taken:
        alternative = f"shade {rank + 1} {name} {counter}"
        counter += 1
    return alternative


def dedupe_names(colors: list[dict]) -> list[dict]:
    """Aynı ada düşen renkleri açıklık sırasına göre ayırır (yeni liste döner).

    Tekrarlı ad prompt'ta zayıf ve çelişkili sinyal: model aynı adı iki farklı
    hex'le görür ve hangisini kullanacağını bilemez. Gömülü tablo, komşu
    harmonisinin 30°'lik adımına göre bazı ton bölgelerinde seyrek kaldığı için
    bu gerçekten oluşuyor (ölçüldü: `#c86a3c` komşu paletinde iki "blush pink"
    ve iki "copper orange").

    Çözüm gruptaki renkleri açıklığa göre sıralayıp "dark/light" gibi bir
    sözcük eklemek: tekilliği garanti eder, doğal okunur ve bilgi taşır.

    Üretilen ad LİSTENİN TAMAMINA karşı kontrol edilir, yalnızca kendi grubuna
    karşı değil: ["dark blue", "blue", "blue"] girdisinde merdiven ikinci
    girdiyi "dark blue" yapıp birinciyle çakıştırıyordu.
    """
    groups: dict[str, list[int]] = {}
    for index, color in enumerate(colors):
        groups.setdefault(color["name"], []).append(index)

    renamed = list(colors)
    # Tek başına duran adlar dokunulmadan kalacağı için baştan "alınmış" sayılır.
    taken = {name for name, indexes in groups.items() if len(indexes) < 2}
    for name, indexes in groups.items():
        if len(indexes) < 2:
            continue
        ladder = _LADDERS.get(len(indexes))
        by_lightness = sorted(indexes, key=lambda i: palette.hex_to_oklch(colors[i]["hex"])[0])
        for rank, index in enumerate(by_lightness):
            # Merdiven yoksa (çok büyük grup) sırayı sayıyla ver — tekillik şart.
            word = ladder[rank] if ladder else f"shade {rank + 1}"
            # Sözcük adın içindeyse tekrar etme ("dark dark rose").
            candidate = name if word in name else f"{word} {name}"
            candidate = _distinct(candidate, name, rank, taken)
            taken.add(candidate)
            renamed[index] = {**colors[index], "name": candidate}
    return renamed


def names_map(hexes: Iterable[str], *, offline: bool = False) -> dict[str, str]:
    """Tekilleştirilmiş `hex → ad`. TEK ağ bütçesi paylaşılır.

    Bütçenin çağrı başına değil PARTİ başına olması önemli: altı harmoniyi ayrı
    ayrı çözümlemek her birine yeni bir API_BUDGET verir ve toplam süre altıya
    katlanır (ölçüldü: 2.5 sn hedefine karşılık 11 sn). Tek çağrı + tekilleştirme
    üst sınırı gerçekten uygular; tohum rengi altı palette de geçtiği için
    tekilleştirme ayrıca beş gereksiz aramayı da eler.
    """
    deadline = None if offline else time.monotonic() + API_BUDGET
    resolved: dict[str, str] = {}
    for hex_color in hexes:
        key = palette.parse_hex(hex_color)
        if key not in resolved:
            resolved[key] = name_for(key, offline=offline, deadline=deadline)
    return resolved


def names_for(hexes: Iterable[str], *, offline: bool = False) -> list[str]:
    """Renk listesinin adları, sırayı ve tekrarları koruyarak."""
    items = list(hexes)
    resolved = names_map(items, offline=offline)
    return [resolved[palette.parse_hex(h)] for h in items]
