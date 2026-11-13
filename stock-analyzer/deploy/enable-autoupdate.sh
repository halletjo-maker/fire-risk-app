#!/bin/bash
# =============================================================================
#  Analyse Boursière : mises à jour automatiques du serveur (à lancer en root)
#   - chaque nuit vers 04:30 (heure de Bruxelles)
#   - à la demande, via le bouton « Mettre à jour maintenant » (administrateur)
#  Usage : bash /opt/analyse-boursiere/stock-analyzer/deploy/enable-autoupdate.sh
# =============================================================================
set -euo pipefail

APP_DIR=/opt/analyse-boursiere
DATA_DIR=/var/lib/analyse-boursiere
REPO="halletjo-maker/fire-risk-app"
BRANCH="claude/stock-analysis-app-k16f0g"
LOG=/var/log/analyse-boursiere-update.log

# --- Script de mise à jour (récupère la dernière version, réinstalle, redémarre) ---
# Écrit dans un fichier temporaire puis déplacé : on ne modifie jamais un script en cours d'exécution.
cat > "$APP_DIR/update.sh.new" <<EOF
#!/bin/bash
set -euo pipefail
rm -f ${DATA_DIR}/update.request
echo "=== \$(date -Is) : mise à jour ==="
cd ${APP_DIR}
PREV=\$(git rev-parse HEAD)
git fetch --depth 1 "https://x-access-token:\$(cat /root/.github-token)@github.com/${REPO}.git" ${BRANCH}
# Filet de sécurité : installation + tests automatiques sur la nouvelle version AVANT la mise en ligne.
# Au moindre échec : retour à la version précédente (qui continue de tourner) et alerte à l'administrateur.
rollback() {
  trap - ERR
  echo "!!! \$1 : retour à la version \${PREV:0:7}"
  git reset --hard "\$PREV"
  ${APP_DIR}/venv/bin/pip install -q -r stock-analyzer/backend/requirements.txt || true
  runuser -u analyse -- ${APP_DIR}/venv/bin/python stock-analyzer/deploy/watchdog_alert.py update_failed "\$2" || true
  exit 1
}
trap 'rollback "erreur pendant l installation" "Installation des dépendances impossible (réseau ou version)."' ERR
git reset --hard FETCH_HEAD
${APP_DIR}/venv/bin/pip install -q -r stock-analyzer/backend/requirements.txt
# Tests sous l'utilisateur limité « analyse », base temporaire, sans mail réel
TESTDIR=\$(mktemp -d) && chown analyse "\$TESTDIR"
if ! (cd stock-analyzer/backend && runuser -u analyse -- env SMTP_HOST= SMTP_USER= SMTP_PASSWORD= \\
      DATABASE_PATH="\$TESTDIR/test.db" PYTHONDONTWRITEBYTECODE=1 TMPDIR="\$TESTDIR" timeout 600 \\
      ${APP_DIR}/venv/bin/python -m pytest -q -x -p no:cacheprovider > "\$TESTDIR/tests.log" 2>&1); then
  tail -n 30 "\$TESTDIR/tests.log"
  rollback "tests en échec" "\$(grep -E 'FAILED|Error' "\$TESTDIR/tests.log" | head -n 3 | cut -c1-300)"
fi
rm -rf "\$TESTDIR"
trap - ERR
git log -1 --format='%h|%cI|%s' > ${APP_DIR}/VERSION
bash ${APP_DIR}/stock-analyzer/deploy/enable-autoupdate.sh > /dev/null || true  # réapplique ces réglages s'ils ont changé
systemctl restart analyse-boursiere
echo "=== \$(date -Is) : terminé (\$(cut -d'|' -f1 ${APP_DIR}/VERSION)) ==="
EOF
chmod 700 "$APP_DIR/update.sh.new"
mv -f "$APP_DIR/update.sh.new" "$APP_DIR/update.sh"

# --- Service exécutant la mise à jour ---
cat > /etc/systemd/system/analyse-boursiere-update.service <<EOF
[Unit]
Description=Mise a jour d'Analyse Boursiere
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=${APP_DIR}/update.sh
StandardOutput=append:${LOG}
StandardError=append:${LOG}
TimeoutStartSec=15min
EOF

# --- Chaque nuit ---
cat > /etc/systemd/system/analyse-boursiere-update.timer <<EOF
[Unit]
Description=Mise a jour nocturne d'Analyse Boursiere

[Timer]
OnCalendar=*-*-* 04:30:00
RandomizedDelaySec=20min
Persistent=true

[Install]
WantedBy=timers.target
EOF

# --- À la demande : l'application dépose ce fichier (bouton administrateur) ---
cat > /etc/systemd/system/analyse-boursiere-update.path <<EOF
[Unit]
Description=Demande de mise a jour depuis l'application

[Path]
PathExists=${DATA_DIR}/update.request
Unit=analyse-boursiere-update.service

[Install]
WantedBy=multi-user.target
EOF

# --- Nom de domaine : l'application dépose domain.request (Profil → Nom de domaine) ---
cat > /etc/systemd/system/analyse-boursiere-domain.service <<EOF
[Unit]
Description=Branchement d'un nom de domaine (Analyse Boursiere)

[Service]
Type=oneshot
ExecStart=/bin/bash ${APP_DIR}/stock-analyzer/deploy/apply-domain.sh
StandardOutput=append:${LOG}
StandardError=append:${LOG}
EOF
cat > /etc/systemd/system/analyse-boursiere-domain.path <<EOF
[Unit]
Description=Demande de nom de domaine depuis l'application

[Path]
PathExists=${DATA_DIR}/domain.request
Unit=analyse-boursiere-domain.service

[Install]
WantedBy=multi-user.target
EOF

# --- Surveillance : toutes les 5 minutes, redémarre si besoin et prévient l'administrateur ---
cat > /etc/systemd/system/analyse-boursiere-watchdog.service <<EOF
[Unit]
Description=Surveillance d'Analyse Boursiere (MM100)

[Service]
Type=oneshot
ExecStart=/bin/bash ${APP_DIR}/stock-analyzer/deploy/watchdog.sh
StandardOutput=append:/var/log/analyse-boursiere-watchdog.log
StandardError=append:/var/log/analyse-boursiere-watchdog.log
EOF
cat > /etc/systemd/system/analyse-boursiere-watchdog.timer <<EOF
[Unit]
Description=Surveillance d'Analyse Boursiere toutes les 5 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF

[ -f "$APP_DIR/VERSION" ] || git -C "$APP_DIR" log -1 --format='%h|%cI|%s' > "$APP_DIR/VERSION" 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now analyse-boursiere-update.timer analyse-boursiere-update.path analyse-boursiere-domain.path \
  analyse-boursiere-watchdog.timer
echo "Mises à jour automatiques activées (chaque nuit + bouton dans l'application)."
