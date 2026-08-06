"""Prompt Yönetmeni'nin sistem talimatını diskten yükler.

İki aday, bu sırayla: kullanıcının ezme dosyası → pakete gömülü varsayılan.
Gömülü dosya KOPYALANMIYOR, her çağrıda okunuyor: `seed.py`'nin "bir kez
kopyala" deseni burada YANLIŞ olurdu. O desen kullanıcı varlıkları silinse de
geri gelsin diye var; talimat ise tam tersini istiyor — bir sonraki sürümde
iyileştirilen varsayılan, kendi dosyasını özelleştirmemiş herkese ULAŞMALI.

Talimat neden `.py` içinde bir dize DEĞİL: on altı bin karakterlik Türkçe
markdown'ı kaynağa gömmek okunamaz hale getirir ve paketlenmiş `.app` içinde
düzenlenemez. Ayrı dosya olduğu için kullanıcı personayı `data_dir()`'e bir
dosya bırakarak değiştirebiliyor.

Bu sayı bir kez bayatladı: dosya 9 binden 15,4 bine çıkarken buradaki ve
`chat_client`'taki yorum "dokuz bin" demeye devam etti, yani birikmenin tek
kaydı sessizce yanlışa döndü. Üst sınır artık testte yaşıyor
(tests/test_chat_prompt.py, 18 bin karakter bütçesi).

Bu modül BİLEREK yalnızca `paths`'e bakıyor ve düz `ValueError` yükseltiyor;
`ChatError`'a çevirmek `chat_client`'ın işi. Tek yönlü bağımlılık
(`chat_client` → `chat_prompt`) döngüsel import'u imkânsız kılar.
"""
from __future__ import annotations

import os

import paths

INSTRUCTIONS_FILE = "prompt-yonetmeni.md"
# Boş ya da yarım kaydedilmiş bir dosya SESSİZCE persona'yı öldürür: model
# talimatsız kalır, Türkçe konuşmayı ve çıktı formatını bırakır, kullanıcı da
# "sohbet bozuldu" der. Uzunluk kapısı o sessiz kırılmayı gürültülüye çevirir.
MIN_INSTRUCTIONS_CHARS = 500


def candidate_paths() -> list[str]:
    """Talimat adayları, ÖNCELİK sırasıyla: [kullanıcı ezmesi, gömülü varsayılan]."""
    return [
        paths.chat_instructions_override(),
        os.path.join(paths.bundled_prompts_dir(), INSTRUCTIONS_FILE),
    ]


def load_instructions(*, paths_override: list[str] | None = None) -> str:
    """İlk okunabilir VE yeterince uzun talimat dosyasının metni.

    Kısa/boş bir aday ATLANIR (sonraki adaya düşer) — hata değil: kullanıcının
    yarım bıraktığı ezme dosyası yüzünden özellik tamamen ölmemeli.
    Hiçbir aday geçerli değilse ValueError.
    """
    candidates = candidate_paths() if paths_override is None else paths_override
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        if len(text.strip()) >= MIN_INSTRUCTIONS_CHARS:
            return text
    raise ValueError(
        "Prompt Yönetmeni talimat dosyası bulunamadı ya da çok kısa: "
        + ", ".join(candidates))
