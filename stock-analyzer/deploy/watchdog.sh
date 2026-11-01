#!/bin/bash
# =============================================================================
#  MM100 : surveillance du site (root, toutes les 5 minutes via systemd)
#  1. L'application répond-elle ? (http://127.0.0.1:8000/health)
#  2. Le site public répond-il ? (https, via Caddy)
#  Deux échecs de suite : redémarrage automatique. Toujours en panne : mail + notification
#  à l'administrateur (une seule fois), puis un message quand c'est rétabli.
# =============================================================================
set -uo pipefail

APP_DIR=/opt/analyse-boursiere
DATA_DIR=/var/lib/analyse-boursiere
STATE="$DATA_DIR/watchdog.state"
ENV_FILE="$APP_DIR/stock-analyzer/.env"
ALERT="$APP_DIR/stock-analyzer/deploy/watchdog_alert.py"
PY="$APP_DIR/venv/bin/python"

# Pendant une mise à jour, l'application redémarre : on ne surveille pas
systemctl is-active --quiet analyse-boursiere-update.service && exit 0

PUBLIC=$(grep -E '^APP_PUBLIC_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '[:space:]')
FAILS=0; ALERTED=0
[ -f "$STATE" ] && read -r FAILS ALERTED < "$STATE"
FAILS=${FAILS:-0}; ALERTED=${ALERTED:-0}

app_ok()    { local out; out=$(curl -fsS --max-time 20 http://127.0.0.1:8000/health 2>/dev/null) && [[ $out == *'"status":"ok"'* ]]; }
public_ok() { [ -z "$PUBLIC" ] || curl -fsS --max-time 20 -o /dev/null "$PUBLIC/api/health"; }
alert()     { runuser -u analyse -- "$PY" "$ALERT" "$1" "$2" || true; }
save()      { echo "$1 $2" > "$STATE"; }

if app_ok && public_ok; then
  [ "$ALERTED" = "1" ] && alert up "Rétabli le $(date '+%d/%m/%Y à %H:%M')."
  save 0 0
  exit 0
fi

FAILS=$((FAILS + 1))
echo "$(date -Is) surveillance : échec $FAILS (application $(app_ok && echo ok || echo KO), site public $(public_ok && echo ok || echo KO))"
if [ "$FAILS" -lt 2 ]; then save "$FAILS" "$ALERTED"; exit 0; fi

if [ "$FAILS" -eq 2 ] || [ $((FAILS % 12)) -eq 0 ]; then  # puis un nouvel essai chaque heure
  echo "$(date -Is) surveillance : redémarrage automatique"
  if app_ok; then systemctl restart caddy; else systemctl restart analyse-boursiere; fi
  sleep 60
  if app_ok && public_ok; then echo "$(date -Is) surveillance : réparé par le redémarrage"; save 0 0; exit 0; fi
fi

if [ "$ALERTED" != "1" ]; then
  if app_ok; then WHAT="l'application tourne mais le site public (https) ne répond pas : problème Caddy, certificat ou nom de domaine"
  else WHAT="l'application ne répond plus. Dernières lignes du journal : $(journalctl -u analyse-boursiere -n 3 --no-pager -o cat 2>/dev/null | tr '\n' ' ' | cut -c1-400)"; fi
  alert down "$WHAT"
  ALERTED=1
fi
save "$FAILS" "$ALERTED"
