# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Satır düzeyi güvenlik (RLS) — sekiz iş tablosunda sahip ve admin politikaları, FORCE (Faz 2 / 7. görev).

Revision: 0006_rls
Önceki:   0005_kota
Tarih:    2026-09-18

NEDEN: Faz 1 / 2 şemayı RLS'e hazır bıraktı ("politika Faz 2/3'te"): her iş
tablosunda `kullanici_id`, uygulama süzgeci `services/depo_*`de ve bekçisi bir
AST taraması. Bekçi yalnız depo imzalarını görür; ham `select(Medya)` yazan
bir admin rotası ya da bakım aracı ondan kaçar. Bu göç süzgeci VERİ TABANINA
indirir (docs/faz2-kuyruk-anahtarlar-depolama.md §7): satır, transaksiyonun
`app.kullanici_id` ayarı sahibine eşitse görünür ve yazılır; `app.rol =
'admin'` her satırı OKUR ve GÜNCELLER ama eklemez, silmez (8. görevin
tavan/iptal yazımları için tam bu ikisi). Ayarı `services/kiraci.py` yazar
(`SET LOCAL` gücünde `set_config`), okuyan bu politikalar.

ÜÇ POLİTİKA / TABLO: `sahip` (ALL; USING ve WITH CHECK aynı ifade — başkasının
`kullanici_id`siyle INSERT/UPDATE de reddedilir), `yonetici_okur` (SELECT),
`yonetici_gunceller` (UPDATE). Politikalar PERMISSIVE: biri geçirirse satır
geçer, yani admin bağlamı kendi satırlarını da görür. Ayar `NULLIF(…, '')`
ile okunur: `current_setting(ad, true)` ayar yoksa NULL verir, uygulama
"bağlı değil"i boş dizeyle yazabilir — ikisi de `NULL::uuid`, hiçbir satırla
eşleşmez, DÖNÜŞÜM HATASI DEĞİL (`''::uuid` hata verirdi ve bağlamsız her
sorgu 500 olurdu; istenen 0 satır).

FORCE ŞART: yönetilen Postgres'te uygulama rolü çoğu zaman tablonun da SAHİBİ
(bazı sağlayıcılar tek rol veriyor: göç ve uygulama aynı rolle bağlanıyor) ve
sahip RLS'i öntanımlı ATLAR — `FORCE` olmadan politika hiç işlemezdi. FORCE
süper kullanıcıyı ve BYPASSRLS rolünü YİNE kapsamaz — ve bazı sağlayıcılar
kutudan tam da öyle bir rol veriyor (Railway'de ölçüldü, 2026-09-18: `postgres`
rolü ikisini de taşıyor; KURULUM.md'nin ayrı rol yolu orada zorunlu). Test
takımı süper kullanıcıyla koşuyor ve orada politika görünmez; yalıtım
iddiaları tests/test_rls.py'de ikinci bir rolle ölçülür, canlıda rolün ikisi de
olmadığı `pg_roles`tan doğrulanır (`tools/rls_kontrol.py`, KURULUM.md).

KAPSAM `kullanici_id` taşıyan ve hesap tablosu OLMAYAN her tablo: Faz 1'in
yedisi + `isler`. Hesap tabloları (`kullanicilar`, `oturumlar`, `jetonlar`,
`giris_denemeleri`) DIŞARIDA ve bilerek — kimlik çözülmeden koşan sorgular
(`oturumlar ⋈ kullanicilar`) oradadır ve bağlam o an yoktur. `isciler`
kiracısız. Liste `services/kiraci.py::IS_TABLOLARI` ile aynı; bekçi
(tests/test_rls.py) ikisini metadata'dan türetilen kümeyle ve DB'nin
`pg_class.relforcerowsecurity`siyle karşılaştırır — buradaki literal TARİHÇE,
oradaki liste kod; ikisi ayrışırsa test söyler.

GERİ ALINABİLİR: `downgrade` politikaları düşürür, FORCE'u ve RLS'i kapatır;
veri dokunulmaz. `alembic check` politikaları KARŞILAŞTIRMIYOR (kısmi indeks
`WHERE`i ve CHECK'ler gibi) — bekçisi tests/test_rls.py, `pg_policies`.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_rls"
down_revision: str | Sequence[str] | None = "0005_kota"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Göç dosyasının kendi literali (tarihçe): services/kiraci.py::IS_TABLOLARI'nın 2026-09-18 hâli.
TABLOLAR: tuple[str, ...] = ("klasorler", "medya", "sohbetler", "paletler", "varliklar",
                             "tercihler", "saglayici_kimlikleri", "isler")

_SAHIP = "kullanici_id = NULLIF(current_setting('app.kullanici_id', true), '')::uuid"
_ADMIN = "current_setting('app.rol', true) = 'admin'"


def upgrade() -> None:
    for tablo in TABLOLAR:
        op.execute(f"ALTER TABLE {tablo} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tablo} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY sahip ON {tablo} USING ({_SAHIP}) WITH CHECK ({_SAHIP})")
        op.execute(f"CREATE POLICY yonetici_okur ON {tablo} FOR SELECT USING ({_ADMIN})")
        op.execute(f"CREATE POLICY yonetici_gunceller ON {tablo} FOR UPDATE USING ({_ADMIN})")


def downgrade() -> None:
    for tablo in reversed(TABLOLAR):
        op.execute(f"DROP POLICY yonetici_gunceller ON {tablo}")
        op.execute(f"DROP POLICY yonetici_okur ON {tablo}")
        op.execute(f"DROP POLICY sahip ON {tablo}")
        op.execute(f"ALTER TABLE {tablo} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tablo} DISABLE ROW LEVEL SECURITY")
