#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

HOST=127.0.0.1
PORT="${PORT:-8765}"

# Portta eski bir sunucu varsa onu DEĞİŞTİR. Aksi halde uvicorn "address already in
# use" ile çıkar, eski süreç ayakta kalır ve şu tuzağa düşülür: static/ her istekte
# diskten okunduğu için YENİ arayüz görünür, ama app.py yalnızca süreç başlarken
# okunduğundan backend BAYAT kalır — yeni alanlar sessizce yok sayılır.
STALE_PIDS="$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "$STALE_PIDS" ]]; then
  echo "→ $PORT portunda çalışan sunucu bulundu (PID: $(echo "$STALE_PIDS" | tr '\n' ' ')); kod değişikliklerini yükleyebilmek için yeniden başlatılıyor."
  # shellcheck disable=SC2086
  kill $STALE_PIDS 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || break
    sleep 0.3
  done
  # inatçı süreç kalırsa zorla
  REMAINING="$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  # shellcheck disable=SC2086
  [[ -n "$REMAINING" ]] && kill -9 $REMAINING 2>/dev/null || true
fi

( sleep 1.5; open "http://$HOST:$PORT" 2>/dev/null || true ) &
# `--factory netguard:korumali_app`, düz `app:app` DEĞİL: bu sunucu 8765'e
# SABİT ve kullanıcının tarayıcısındaki herhangi bir sayfa multipart uçlara
# (`/api/edit`, `/api/import`, `/api/assets/…`) ön uçuşsuz istek atabiliyordu.
# Fabrika, istek kaynağı kapısını app.py'ye dokunmadan takıyor (bkz. netguard.py).
exec uvicorn --factory netguard:korumali_app --host "$HOST" --port "$PORT"
