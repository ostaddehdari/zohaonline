#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo 'این اسکریپت باید با sudo/root اجرا شود.' >&2; exit 1; }

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-/opt/zohaonline}"
APP_USER="${APP_USER:-zohaonline}"
SERVICE_NAME="${SERVICE_NAME:-zohaonline}"
APP_PORT="${APP_PORT:-18123}"
SERVER_IP="${SERVER_IP:-5.61.27.185}"
URL_PREFIX="${URL_PREFIX:-zohaonline}"
PURGE_DEMO_DATA="${PURGE_DEMO_DATA:-1}"
RELEASE_MARKER="ZOHA-DISCOVERY-270"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/root/zohaonline-inplace-270-backup-${STAMP}"

[[ -d "$APP_DIR" ]] || { echo "مسیر نصب فعلی پیدا نشد: $APP_DIR" >&2; exit 2; }
[[ -f "$APP_DIR/.env" ]] || { echo "فایل $APP_DIR/.env پیدا نشد؛ برای نصب تازه از install_or_upgrade_zoha.sh استفاده کنید." >&2; exit 2; }
[[ -x "$APP_DIR/.venv/bin/python" ]] || { echo "virtualenv نصب فعلی پیدا نشد؛ برای نصب تازه از install_or_upgrade_zoha.sh استفاده کنید." >&2; exit 2; }
[[ -f "$SOURCE_DIR/VERSION" && "$(cat "$SOURCE_DIR/VERSION")" == "2.7.0" ]] || { echo 'بسته معتبر 2.7.0 نیست.' >&2; exit 2; }
grep -q "$RELEASE_MARKER" "$SOURCE_DIR/zoha/release.py" || { echo 'Release marker معتبر نیست.' >&2; exit 2; }
command -v rsync >/dev/null || { echo 'rsync نصب نیست.' >&2; exit 2; }
command -v pg_dump >/dev/null || { echo 'PostgreSQL client نصب نیست.' >&2; exit 2; }

mkdir -p "$BACKUP_DIR"
echo '=================================================='
echo ' ZohaOnline 2.7.0 — Upgrade درجا و بدون نصب مجدد'
echo '=================================================='
echo "App: $APP_DIR"
echo "Release: $RELEASE_MARKER"
echo "Backup: $BACKUP_DIR"

# Backup application source/config, DB, Nginx and systemd. Media stays in place and is not modified.
tar --exclude='.venv' --exclude='media' --exclude='staticfiles' \
  -czf "$BACKUP_DIR/application-before-270.tar.gz" -C "$APP_DIR" .
cp -a "$APP_DIR/.env" "$BACKUP_DIR/.env"
cp -a "/etc/systemd/system/${SERVICE_NAME}.service" "$BACKUP_DIR/" 2>/dev/null || true
tar -C / -czf "$BACKUP_DIR/nginx-current.tar.gz" etc/nginx 2>/dev/null || true

DB_NAME="$(sed -n 's/^DB_NAME=//p' "$APP_DIR/.env" | tail -n1 | tr -d '\r')"
if [[ -n "$DB_NAME" && "$DB_NAME" =~ ^[A-Za-z0-9_]+$ ]]; then
  runuser -u postgres -- pg_dump -Fc "$DB_NAME" > "$BACKUP_DIR/${DB_NAME}.dump"
else
  echo 'هشدار: DB_NAME معتبر از .env خوانده نشد؛ Backup دیتابیس ایجاد نشد.' >&2
fi

on_error(){
  local code=$?
  echo >&2
  echo "❌ ارتقا با خطا متوقف شد (کد $code). Backup در: $BACKUP_DIR" >&2
  systemctl restart "$SERVICE_NAME" >/dev/null 2>&1 || true
  exit "$code"
}
trap on_error ERR

systemctl stop "$SERVICE_NAME"

# Preserve the live environment, venv, uploads and generated static directory.
rsync -a --delete \
  --exclude='.env' --exclude='.venv/' --exclude='media/' --exclude='staticfiles/' \
  "$SOURCE_DIR/" "$APP_DIR/"

# Only update the release marker and append new optional settings if missing.
python3 - "$APP_DIR/.env" "$RELEASE_MARKER" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); marker=sys.argv[2]
lines=p.read_text(encoding='utf-8').splitlines(); out=[]; seen=set()
defaults={
    'ZOHA_RELEASE': marker,
    'ZOHA_CHANNEL_URL': '',
    'ZOHA_IMAGE_API_URL': '',
    'ZOHA_IMAGE_API_KEY': '',
    'ZOHA_QURAN_REFERENCE_URL': 'https://quran.inoor.ir/fa/home',
    'ZOHA_HADITH_REFERENCE_URL': 'https://hadith.inoor.ir/',
    'ZOHA_POETRY_REFERENCE_URL': 'https://ganjoor.net/',
}
for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        key=line.split('=',1)[0].strip()
        if key=='ZOHA_RELEASE':
            out.append(f'ZOHA_RELEASE={marker}'); seen.add(key); continue
        if key in defaults: seen.add(key)
    out.append(line)
for key,value in defaults.items():
    if key not in seen: out.append(f'{key}={value}')
p.write_text('\n'.join(out)+'\n', encoding='utf-8')
PY

"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
chown -R "$APP_USER:www-data" "$APP_DIR"
chmod 750 "$APP_DIR" "$APP_DIR/media" "$APP_DIR/staticfiles"
chmod 640 "$APP_DIR/.env"

run_as_app(){ runuser -u "$APP_USER" -- "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" "$@"; }

# pg_trgm must exist before migration 0013 creates the trigram GIN index.
if [[ -n "${DB_NAME:-}" ]]; then
  runuser -u postgres -- psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm;'
fi

run_as_app migrate --noinput
if [[ "$PURGE_DEMO_DATA" == "1" ]]; then
  run_as_app upgrade_270_data --purge-demo --skip-search-rebuild
else
  run_as_app upgrade_270_data --skip-search-rebuild
fi
run_as_app seed_zoha
run_as_app upgrade_270_data --skip-search-rebuild
run_as_app rebuild_search_documents
run_as_app collectstatic --noinput --clear
run_as_app check
run_as_app makemigrations --check --dry-run

systemctl restart "$SERVICE_NAME"
sleep 3
systemctl is-active --quiet "$SERVICE_NAME" || { journalctl -u "$SERVICE_NAME" -n 120 --no-pager; false; }

DIRECT="$(curl -sS -H "Host: $SERVER_IP" "http://127.0.0.1:${APP_PORT}/${URL_PREFIX}/version/" || true)"
if ! grep -q "$RELEASE_MARKER" <<<"$DIRECT"; then
  echo 'Backend مستقیم Release جدید را گزارش نکرد.' >&2
  echo "$DIRECT" >&2
  false
fi

HTTP_CODE="$(curl -sS -o /tmp/zoha270-http.out -w '%{http_code}' -H "Host: $SERVER_IP" "http://127.0.0.1/${URL_PREFIX}/version/" || true)"
HTTPS_CODE="$(curl -ksS -o /tmp/zoha270-https.out -w '%{http_code}' --resolve "${SERVER_IP}:443:127.0.0.1" "https://${SERVER_IP}/${URL_PREFIX}/version/" || true)"

echo
if [[ "$HTTP_CODE" == "200" ]] && grep -q "$RELEASE_MARKER" /tmp/zoha270-http.out; then
  echo "✅ Nginx HTTP: $RELEASE_MARKER"
else
  echo "⚠️ Nginx HTTP فعلی Release جدید را گزارش نکرد (HTTP $HTTP_CODE). Nginx توسط این Patch تغییر داده نشده است."
fi
if [[ "$HTTPS_CODE" == "200" ]] && grep -q "$RELEASE_MARKER" /tmp/zoha270-https.out; then
  echo "✅ Nginx HTTPS: $RELEASE_MARKER"
else
  echo "⚠️ Nginx HTTPS فعلی Release جدید را گزارش نکرد (HTTP $HTTPS_CODE). Nginx توسط این Patch تغییر داده نشده است."
fi

trap - ERR
echo '=================================================='
echo ' ✅ ارتقای درجا به ZohaOnline 2.7.0 تکمیل شد'
echo '=================================================='
echo "سایت: https://${SERVER_IP}/${URL_PREFIX}/"
echo "نسخه: https://${SERVER_IP}/${URL_PREFIX}/version/"
echo "Backup: $BACKUP_DIR"
echo 'کاربران، رمزها، .env، Media، Nginx و Systemd موجود حفظ شدند.'
