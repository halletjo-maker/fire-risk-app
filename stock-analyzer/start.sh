#!/usr/bin/env bash
# Lance le backend (port 8000) et le frontend (port 3000). Ctrl+C arrête les deux.
set -e
cd "$(dirname "$0")"
[ -f .env ] || { cp .env.example .env; echo "→ .env créé depuis .env.example (pense à le compléter)"; }

(cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT

IP=$( (hostname -I 2>/dev/null || ipconfig getifaddr en0 2>/dev/null) | awk '{print $1}')
echo ""
echo "  PC       : http://localhost:3000"
[ -n "$IP" ] && echo "  Mobile   : http://$IP:3000  (même Wi-Fi)"
echo ""
cd frontend && npm run dev
