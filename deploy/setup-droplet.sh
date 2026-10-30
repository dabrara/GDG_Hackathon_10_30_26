#!/usr/bin/env bash
# Install PlainSight on a fresh Ubuntu 22.04/24.04 DigitalOcean Droplet (GPU Droplet recommended).
# Run as root from inside the project:   APP_PASS='choose-a-password' bash deploy/setup-droplet.sh
# Optional env: APP_USER (default demo), DOMAIN (default <ip>.sslip.io), MODEL (default: chosen from RAM).
set -euo pipefail
: "${APP_PASS:?Set APP_PASS to the password people will use to open the site}"
APP_USER_NAME="${APP_USER:-demo}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR=/opt/plainsight
IP="$(curl -fsS http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address 2>/dev/null || curl -fsS https://api.ipify.org)"
DOMAIN="${DOMAIN:-$IP.sslip.io}"   # sslip.io gives a free hostname so Caddy can get a real HTTPS certificate

apt-get update -y
apt-get install -y python3-venv python3-pip curl rsync gpg debian-keyring debian-archive-keyring apt-transport-https ufw

# 1) Ollama (listens on 127.0.0.1 only; never open port 11434)
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
systemctl enable --now ollama
sleep 3

# 2) App files, venv, model
id plainsight >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin plainsight
mkdir -p "$APP_DIR"; rsync -a --delete --exclude .venv --exclude deploy --exclude .ui_cache.json "$SRC"/ "$APP_DIR"/
python3 -m venv "$APP_DIR/.venv"; "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
MODEL="${MODEL:-$(python3 "$APP_DIR/scripts/select_model.py" --model-only)}"
[[ "$MODEL" =~ ^gemma(2|3|3n|4)?:[a-z0-9._-]+$ ]] || { echo "MODEL must be a Gemma tag, e.g. gemma4:e4b or gemma3:12b"; exit 1; }
ollama pull "$MODEL"
"$APP_DIR/.venv/bin/python" "$APP_DIR/scripts/make_samples.py" >/dev/null
chown -R plainsight:plainsight "$APP_DIR"

# 3) App as a service, bound to localhost
cat > /etc/systemd/system/plainsight.service <<UNIT
[Unit]
Description=PlainSight
After=network.target ollama.service
[Service]
User=plainsight
WorkingDirectory=$APP_DIR
Environment=MODEL=$MODEL
Environment="DEPLOY_HOST=DigitalOcean ${DO_LABEL:-GPU Droplet}"
ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload; systemctl enable --now plainsight

# 4) Caddy: HTTPS + password. The app itself has no login, so never expose it without this.
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y; apt-get install -y caddy
fi
HASH="$(caddy hash-password --plaintext "$APP_PASS")"
cat > /etc/caddy/Caddyfile <<CADDY
$DOMAIN {
	basicauth {
		$APP_USER_NAME $HASH
	}
	encode gzip
	reverse_proxy 127.0.0.1:8000 {
		flush_interval -1
	}
}
CADDY
systemctl restart caddy

# 5) Firewall: SSH + web only
ufw allow OpenSSH; ufw allow 80/tcp; ufw allow 443/tcp; ufw --force enable

echo; echo "PlainSight is running with $MODEL"; echo "Open https://$DOMAIN  (user: $APP_USER_NAME)"
