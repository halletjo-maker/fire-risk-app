#!/bin/bash
# =============================================================================
#  Analyse Boursière : brancher un nom de domaine (lancé en root par systemd)
#  L'application (Profil → Nom de domaine) vérifie le DNS puis dépose
#  /var/lib/analyse-boursiere/domain.request contenant les noms, ex. « mm100.be www.mm100.be ».
#  Ce script : Caddy (https automatique pour ces noms + l'ancienne adresse), .env, redémarrage.
# =============================================================================
set -euo pipefail

APP_DIR=/opt/analyse-boursiere
DATA_DIR=/var/lib/analyse-boursiere
REQUEST="$DATA_DIR/domain.request"
STATUS="$DATA_DIR/domain.status"
CADDYFILE=${CADDYFILE:-/etc/caddy/Caddyfile}
ENV_FILE="$APP_DIR/stock-analyzer/.env"

[ -f "$REQUEST" ] || exit 0
RAW=$(head -c 300 "$REQUEST")
rm -f "$REQUEST"

# Noms autorisés uniquement (le fichier vient de l'application : on ne lui fait pas confiance)
NAMES=()
set -f  # pas d'expansion de « * » en noms de fichiers
for n in $RAW; do
  n=$(echo "$n" | tr 'A-Z' 'a-z')
  if [[ "$n" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$ ]]; then NAMES+=("$n"); fi
done
set +f
if [ ${#NAMES[@]} -eq 0 ]; then
  echo "error|Nom de domaine invalide|$(date -Is)" > "$STATUS"; chmod 644 "$STATUS"; exit 1
fi
PRIMARY="${NAMES[0]}"

# L'ancienne adresse IP.sslip.io reste servie pendant la transition
IP=$(curl -fsS --max-time 5 http://169.254.169.254/hetzner/v1/metadata/public-ipv4 2>/dev/null \
     || curl -4fsS --max-time 10 https://api.ipify.org)
SITES="$(printf '%s, ' "${NAMES[@]}")${IP}.sslip.io"

cp "$CADDYFILE" "$CADDYFILE.bak"
cat > "$CADDYFILE" <<EOF
${SITES} {
	encode gzip
	header {
		Strict-Transport-Security "max-age=31536000"
		X-Content-Type-Options "nosniff"
		X-Frame-Options "DENY"
		Referrer-Policy "same-origin"
		-Server
	}
	reverse_proxy 127.0.0.1:8000
}
EOF
if ! caddy validate --config "$CADDYFILE" --adapter caddyfile > /dev/null 2>&1; then
  mv -f "$CADDYFILE.bak" "$CADDYFILE"
  echo "error|Configuration refusée par Caddy|$(date -Is)" > "$STATUS"; chmod 644 "$STATUS"; exit 1
fi

set_env() {
  if grep -q "^$1=" "$ENV_FILE"; then sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"; else echo "$1=$2" >> "$ENV_FILE"; fi
}
ORIGINS=$(printf 'https://%s,' "${NAMES[@]}")"https://${IP}.sslip.io"
set_env APP_PUBLIC_URL "https://${PRIMARY}"
set_env CORS_ORIGINS "$ORIGINS"

systemctl reload caddy || systemctl restart caddy
systemctl restart analyse-boursiere
echo "ok|${NAMES[*]}|$(date -Is)" > "$STATUS"
chmod 644 "$STATUS"
echo "Nom de domaine activé : ${NAMES[*]}"
