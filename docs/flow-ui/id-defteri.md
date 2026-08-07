# id defteri — bilerek kaldırılan element id'leri

Flow taşımasında `static/index.html`'den **kaldırılan** her id burada gerekçesiyle
yazılı. `tests/test_id_contract.py` bu dosyayı okur; defterde yazmayan bir id
kaybolduğu anda test kırmızıya döner.

## Neden defter, neden "boş diff" değil

Taşıma başlarken kural "id diff boş olmalı" idi. Ama tasarım bazı öğeleri
gerçekten kaldırıyor (sekmeler, üst şeritteki arama, ayrı düzenle paneli) ve
6 Ağustos kararıyla **bu öğelerin testleri de onlarla birlikte güncelleniyor.**
O yüzden boş diff kuralı düştü; yerine bu defter ve üç otomatik iddia geçti.

Defter, diff'ten **güçlü** bir yerde duruyor: ikinci iddia bir id'nin JS bağının
da silinmiş olmasını şart koşuyor, yani **yeniden adlandırmayı** da yakalıyor —
eski diff yalnızca yokluğu görüyordu.

## Kaldırmanın gerçek maliyeti

`static/core.js:10`'da `const $ = (id) => document.getElementById(id)`.
JS'ten `$()` ile **145 id**'ye dokunuluyor ve **56'sı top-level bağ** — yani dosya
yüklenirken çalışan `$("x").addEventListener(...)` satırları. Böyle bir id
kaybolursa `$()` `null` döner, `addEventListener` `TypeError` atar ve **o dosyanın
o satırdan sonraki tüm dinleyicileri hiç kurulmaz.** Yükleme sırası bağlayıcı:

    core.js → folders.js → assets.js → palette.js → settings.js

Bu yüzden bir id'yi deftere yazmak yetmez: JS bağını da aynı commit'te
kaldırmak gerekir. Testin ikinci iddiası bunu zorunlu tutuyor.

## Kaldırılanlar

Henüz kaldırılan id yok — Adım 1 yalnızca token katmanı, işaretlemeye
dokunmadı. Tablo Adım 2'de (kabuk) dolmaya başlayacak.

| id | Hangi tasarım kararıyla | JS bağı nerede kaldırıldı | Güncellenen test |
|---|---|---|---|

<!-- Tablo biçimi bağlayıcı: ilk hücre backtick içinde id olmak zorunda,
     test satırları böyle ayıklıyor. Örnek:
| `topbar-search` | Arama Medya görünümüne taşındı (plan §4.1) | `folders.js` — `searchInput` dinleyicisi kaldırıldı | `test_index.py::test_index_served` arama iddiası silindi |
-->
