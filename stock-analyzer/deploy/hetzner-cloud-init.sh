#!/bin/bash
# =============================================================================
#  Analyse Boursière : installation automatique sur un serveur Ubuntu 24.04
#  (Hetzner Cloud : à coller dans le champ « Cloud config » à la création)
#
#  Remplis les 2 lignes ci-dessous, rien d'autre.
# =============================================================================
EMAIL="ton.adresse@exemple.be"      # ton adresse mail (compte administrateur ; tes amis : bouton « Inviter un ami »)
GITHUB_TOKEN="colle_ici_ton_jeton"  # jeton GitHub en lecture seule (voir le guide)
# =============================================================================

REPO="halletjo-maker/fire-risk-app"
BRANCH="claude/stock-analysis-app-k16f0g"
APP_DIR=/opt/analyse-boursiere
DATA_DIR=/var/lib/analyse-boursiere
APP_USER=analyse

set -euo pipefail
exec > >(tee -a /var/log/analyse-boursiere-install.log) 2>&1
echo "=== Installation démarrée : $(date) ==="
export DEBIAN_FRONTEND=noninteractive

# --- Adresse publique et nom https gratuit (sslip.io : 1.2.3.4.sslip.io -> 1.2.3.4) ---
IP=$(curl -fsS --max-time 5 http://169.254.169.254/hetzner/v1/metadata/public-ipv4 || curl -4fsS --max-time 10 https://api.ipify.org)
DOMAIN="${IP}.sslip.io"
echo "Adresse : https://${DOMAIN}"

# --- Mémoire d'appoint (2 Go) : évite les manques de RAM pendant les calculs ---
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# --- Paquets : Python, git, Caddy (https automatique), pare-feu, anti-intrusion ---
apt-get update -q
apt-get install -y -q python3-venv python3-pip git caddy ufw fail2ban unattended-upgrades
timedatectl set-timezone Europe/Brussels || true

# --- Code de l'application (le jeton reste dans un fichier lisible par root seul) ---
install -m 600 /dev/null /root/.github-token
printf '%s' "$GITHUB_TOKEN" > /root/.github-token
rm -rf "$APP_DIR"
git clone --depth 1 -b "$BRANCH" "https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO}.git" "$APP_DIR"
git -C "$APP_DIR" remote set-url origin "https://github.com/${REPO}.git"

# --- Utilisateur système dédié + environnement Python ---
id "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$DATA_DIR"
chown -R "$APP_USER:$APP_USER" "$DATA_DIR"
chmod 750 "$DATA_DIR"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/stock-analyzer/backend/requirements.txt"

# --- Configuration (.env lisible uniquement par l'application) ---
ENV_FILE="$APP_DIR/stock-analyzer/.env"
if [ ! -f "$ENV_FILE" ]; then
  cp "$APP_DIR/stock-analyzer/.env.example" "$ENV_FILE"
fi
set_env() {  # set_env CLE valeur : remplace la ligne CLE=... ou l'ajoute
  if grep -q "^$1=" "$ENV_FILE"; then sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"; else echo "$1=$2" >> "$ENV_FILE"; fi
}
set_env APP_PUBLIC_URL "https://${DOMAIN}"
set_env ALLOWED_EMAILS "$EMAIL"
set_env DATABASE_PATH "${DATA_DIR}/stock_analyzer.db"
set_env CORS_ORIGINS "https://${DOMAIN}"
chown root:"$APP_USER" "$ENV_FILE"
chmod 640 "$ENV_FILE"

# --- Service : démarre au boot, redémarre en cas de plantage ---
cat > /etc/systemd/system/analyse-boursiere.service <<EOF
[Unit]
Description=Analyse Boursiere
After=network-online.target
Wants=network-online.target

[Service]
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}/stock-analyzer/backend
Environment=HOME=${DATA_DIR}
Environment=XDG_CACHE_HOME=${DATA_DIR}/.cache
Environment=NUMBA_CACHE_DIR=${DATA_DIR}/.cache/numba
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=${APP_DIR}/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=${DATA_DIR}

[Install]
WantedBy=multi-user.target
EOF

# --- Caddy : https (certificat Let's Encrypt automatique) devant l'application ---
cat > /etc/caddy/Caddyfile <<EOF
${DOMAIN} {
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

# --- Script de mise à jour : sudo /opt/analyse-boursiere/update.sh ---
cat > "$APP_DIR/update.sh" <<EOF
#!/bin/bash
set -euo pipefail
cd ${APP_DIR}
git fetch --depth 1 "https://x-access-token:\$(cat /root/.github-token)@github.com/${REPO}.git" ${BRANCH}
git reset --hard FETCH_HEAD
${APP_DIR}/venv/bin/pip install -q -r stock-analyzer/backend/requirements.txt
systemctl restart analyse-boursiere
echo "Mise à jour terminée."
EOF
chmod 700 "$APP_DIR/update.sh"

# --- Pare-feu : seulement SSH, http (redirigé) et https ---
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

systemctl daemon-reload
systemctl enable --now analyse-boursiere
systemctl enable fail2ban
systemctl restart fail2ban caddy

# --- Vérification ---
for i in $(seq 1 30); do
  if curl -fs http://127.0.0.1:8000/health >/dev/null; then break; fi
  sleep 2
done
curl -fs http://127.0.0.1:8000/health >/dev/null && STATUS="OK" || STATUS="ECHEC (voir journalctl -u analyse-boursiere)"
cat > /root/INSTALLATION.txt <<EOF
Analyse Boursière : installation du $(date)
Application : ${STATUS}
Adresse     : https://${DOMAIN}
Compte      : ${EMAIL} (crée ton mot de passe à la première ouverture)
Données     : ${DATA_DIR}
Mise à jour : sudo ${APP_DIR}/update.sh
Journal     : journalctl -u analyse-boursiere -f
EOF
cat /root/INSTALLATION.txt
echo "=== Installation terminée : $(date) ==="
