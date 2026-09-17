# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""`giris_denemeleri.tur` — üç deneme sayacı tek tabloda (Faz 1 / 3. görev).

Revision: 0002_deneme_turu
Önceki:   0001_veri_modeli
Tarih:    2026-09-17

NEDEN: belge (§3, "Hız sınırı") üç sayaç istiyor — başarısız giriş (e-posta
10 / IP 30, 15 dk), kayıt isteği ve sıfırlama isteği (IP 5, 1 sa) — ve
`giris_denemeleri` 2. görevde yalnız `(eposta, ip, zaman)` ile doğdu. Aynı
satırları ayrım yapmadan saymak, parolasını beş kez yanlış yazan kullanıcıyı
"parolamı unuttum"dan da kilitlerdi. Yeni bir tablo yerine bir `tur` sütunu:
üçünün de indeksi, penceresi ve sorgusu aynı biçimde (services/hesap.py).

`server_default 'giris'` + `NOT NULL`: 0001'den kalan satır varsa (bugün yok —
hesap rotaları bu göçle birlikte geliyor) hepsi başarısız girişti, başka
yazan yoktu. Değer kümesi `text + CHECK` — 2. görevin enum kararı aynen;
küme `services/tablolar.py::DENEME_TURLERI`nden, adı kurala göre
`ck_giris_denemeleri_tur_kumesi`. GERİ ALINABİLİR: `downgrade` kısıtı ve
sütunu düşürür (ileri-geri-ileri döngüsü tests/test_db.py'de).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_deneme_turu"
down_revision: str | Sequence[str] | None = "0001_veri_modeli"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("giris_denemeleri",
                  sa.Column("tur", sa.Text(), server_default=sa.text("'giris'"), nullable=False))
    op.create_check_constraint(op.f("ck_giris_denemeleri_tur_kumesi"), "giris_denemeleri",
                               "tur IN ('giris', 'kayit', 'sifirlama')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_giris_denemeleri_tur_kumesi"), "giris_denemeleri", type_="check")
    op.drop_column("giris_denemeleri", "tur")
