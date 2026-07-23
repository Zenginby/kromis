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
( sleep 1.5; open "http://$HOST:$PORT" 2>/dev/null || true ) &
exec uvicorn app:app --host "$HOST" --port "$PORT"
