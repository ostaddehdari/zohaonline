#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo 'این اسکریپت باید با sudo اجرا شود.' >&2; exit 1; }

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-/opt/zohaonline}"
APP_USER="${APP_USER:-zohaonline}"
SERVICE_NAME="${SERVICE_NAME:-zohaonline}"
SERVER_IP="${SERVER_IP:-5.61.27.185}"
URL_PREFIX="${URL_PREFIX:-zohaonline}"
APP_PORT="${APP_PORT:-18123}"
DB_NAME="${DB_NAME:-zohaonline_db}"
DB_USER="${DB_USER:-zohaonline_user}"
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
GENERATED_ADMIN_PASSWORD=0
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@zohaonline.local}"
RELEASE_MARKER="ZOHA-DISCOVERY-270"
SNIPPET="/etc/nginx/snippets/zohaonline-discovery-270.conf"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/root/zohaonline-discovery270-backup-${STAMP}"

[[ "$SERVER_IP" =~ ^[0-9a-fA-F:.]+$ ]] || { echo 'SERVER_IP نامعتبر است.' >&2; exit 1; }
[[ "$URL_PREFIX" =~ ^[A-Za-z0-9_-]+$ ]] || { echo 'URL_PREFIX نامعتبر است.' >&2; exit 1; }
[[ "$APP_PORT" =~ ^[0-9]+$ ]] || { echo 'APP_PORT نامعتبر است.' >&2; exit 1; }
[[ -f "$SOURCE_DIR/VERSION" ]] || { echo 'فایل VERSION در بسته پیدا نشد.' >&2; exit 1; }
[[ "$(cat "$SOURCE_DIR/VERSION")" == '2.7.0' ]] || { echo 'این بسته نسخه ۲.۷.۰ نیست.' >&2; exit 1; }
grep -q "$RELEASE_MARKER" "$SOURCE_DIR/zoha/release.py" || { echo 'نشان نسخه در مرجع مرکزی Release پیدا نشد.' >&2; exit 1; }

mkdir -p "$BACKUP_DIR"

echo '=================================================='
echo ' ZohaOnline Discovery & Full Content 2.7.0 — نصب/ارتقای یکپارچه'
echo '=================================================='
echo "نشانی: http://${SERVER_IP}/${URL_PREFIX}/"
echo "نسخه: $(cat "$SOURCE_DIR/VERSION") / ${RELEASE_MARKER}"
echo "پورت backend جدید: ${APP_PORT}"
echo "پشتیبان: ${BACKUP_DIR}"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-dev build-essential libpq-dev \
  postgresql postgresql-contrib nginx rsync curl ca-certificates iproute2 psmisc

# Back up current app, DB and complete Nginx config.
if [[ -d "$APP_DIR" ]]; then
  tar --exclude='.venv' --exclude='media' --exclude='staticfiles' \
      -czf "$BACKUP_DIR/application-before-discovery-270.tar.gz" -C "$APP_DIR" . || true
fi
if [[ -f "$APP_DIR/.env" ]]; then
  cp -a "$APP_DIR/.env" "$BACKUP_DIR/.env"
  CURRENT_DB="$(sed -n 's/^DB_NAME=//p' "$APP_DIR/.env" | tail -n1)"
  [[ -n "$CURRENT_DB" ]] && DB_NAME="$CURRENT_DB"
fi
[[ "$DB_NAME" =~ ^[A-Za-z0-9_]+$ ]] || { echo "نام دیتابیس نامعتبر: $DB_NAME" >&2; exit 2; }
runuser -u postgres -- pg_dump -Fc "$DB_NAME" > "$BACKUP_DIR/${DB_NAME}.dump" 2>/dev/null || true
tar -C / -czf "$BACKUP_DIR/nginx-before-discovery-270.tar.gz" etc/nginx

id "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
fuser -k 18015/tcp >/dev/null 2>&1 || true
fuser -k 18122/tcp >/dev/null 2>&1 || true
fuser -k "$APP_PORT/tcp" >/dev/null 2>&1 || true

# Preserve environment, virtualenv, uploads and generated static assets while replacing all source code.
PRESERVED_ENV=''
if [[ -f "$APP_DIR/.env" ]]; then
  PRESERVED_ENV="$BACKUP_DIR/preserved.env"
  cp -a "$APP_DIR/.env" "$PRESERVED_ENV"
fi
mkdir -p "$APP_DIR"
rsync -a --delete \
  --exclude='.env' --exclude='.venv/' --exclude='media/' --exclude='staticfiles/' \
  "$SOURCE_DIR/" "$APP_DIR/"
mkdir -p "$APP_DIR/media" "$APP_DIR/staticfiles"

# Create a new DB only when this is the first installation.
if [[ -z "$PRESERVED_ENV" ]]; then
  DB_PASSWORD="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(36))
PY
)"
  DJANGO_SECRET="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
)"
  runuser -u postgres -- psql -v ON_ERROR_STOP=1 \
    --set=db_name="$DB_NAME" --set=db_user="$DB_USER" --set=db_password="$DB_PASSWORD" <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE datname = :'db_name' AND pid <> pg_backend_pid();
SELECT format('DROP DATABASE IF EXISTS %I', :'db_name') \gexec
SELECT format('DROP ROLE IF EXISTS %I', :'db_user') \gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password') \gexec
SELECT format('CREATE DATABASE %I OWNER %I ENCODING %L TEMPLATE template0', :'db_name', :'db_user', 'UTF8') \gexec
SQL
  cat > "$APP_DIR/.env" <<ENV
DJANGO_SECRET_KEY=$DJANGO_SECRET
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=$SERVER_IP,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=http://$SERVER_IP,https://$SERVER_IP
DJANGO_URL_PREFIX=$URL_PREFIX
DB_ENGINE=postgresql
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=5432
TIME_ZONE=Asia/Tehran
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
ZOHA_RELEASE=$RELEASE_MARKER
ENV
else
  cp -a "$PRESERVED_ENV" "$APP_DIR/.env"
  python3 - "$APP_DIR/.env" "$SERVER_IP" "$URL_PREFIX" "$RELEASE_MARKER" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1]); ip=sys.argv[2]; prefix=sys.argv[3]; release=sys.argv[4]
updates={
 'DJANGO_ALLOWED_HOSTS':f'{ip},127.0.0.1,localhost',
 'DJANGO_CSRF_TRUSTED_ORIGINS':f'http://{ip},https://{ip}',
 'DJANGO_URL_PREFIX':prefix,
 'ZOHA_RELEASE':release,
}
lines=path.read_text().splitlines(); out=[]; seen=set()
for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        key=line.split('=',1)[0].strip()
        if key in updates:
            out.append(f'{key}={updates[key]}'); seen.add(key); continue
    out.append(line)
for key,value in updates.items():
    if key not in seen: out.append(f'{key}={value}')
path.write_text('\n'.join(out)+'\n')
PY
fi

if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --upgrade pip wheel
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

chown -R "$APP_USER:www-data" "$APP_DIR"
chmod 750 "$APP_DIR" "$APP_DIR/media" "$APP_DIR/staticfiles"
chmod 640 "$APP_DIR/.env"
run_as_app(){ runuser -u "$APP_USER" -- "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" "$@"; }
runuser -u postgres -- psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm;'
run_as_app migrate --noinput
PURGE_DEMO_DATA="${PURGE_DEMO_DATA:-1}"
SEED_DEMO_DATA="${SEED_DEMO_DATA:-0}"
# First rename/merge legacy vocabulary before seeding new canonical values. This avoids
# duplicate parent/child values during an in-place 2.6 -> 2.7 upgrade.
if [[ "$PURGE_DEMO_DATA" == "1" ]]; then
  run_as_app upgrade_270_data --purge-demo --skip-search-rebuild
else
  run_as_app upgrade_270_data --skip-search-rebuild
fi
run_as_app seed_zoha
# Now rebuild search documents against the final vocabulary.
run_as_app upgrade_270_data --skip-search-rebuild
run_as_app rebuild_search_documents
if [[ "$SEED_DEMO_DATA" == "1" ]]; then
  run_as_app seed_demo_content --reset-passwords
  echo "⚠️ داده نمایشی بنا به درخواست SEED_DEMO_DATA=1 ایجاد شد."
else
  echo "✅ محیط واقعی: داده نمایشی اجباری ایجاد نمی‌شود و آمار از داده واقعی محاسبه خواهد شد."
fi
if [[ -z "$PRESERVED_ENV" ]]; then
  if [[ -z "$ADMIN_PASSWORD" ]]; then
    ADMIN_PASSWORD="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(18))
PY
)"
    GENERATED_ADMIN_PASSWORD=1
  fi
  run_as_app ensure_admin --username "$ADMIN_USERNAME" --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD"
elif [[ -n "$ADMIN_PASSWORD" ]]; then
  run_as_app ensure_admin --username "$ADMIN_USERNAME" --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD"
  echo "✅ رمز مدیر طبق ADMIN_PASSWORD به‌روزرسانی شد."
else
  echo "✅ ارتقا: حساب‌ها و رمزهای موجود بدون تغییر حفظ شدند."
fi
run_as_app collectstatic --noinput --clear
run_as_app check
if ! run_as_app makemigrations --check --dry-run; then
  echo 'خطا: مدل‌ها هنوز Migration ثبت‌نشده دارند.' >&2
  exit 3
fi

# Install the new unmistakable backend on a distinct loopback port.
install -m 0644 "$APP_DIR/deploy/zohaonline.service" "/etc/systemd/system/${SERVICE_NAME}.service"
sed -i \
  -e "s|User=zohaonline|User=${APP_USER}|" \
  -e "s|WorkingDirectory=/opt/zohaonline|WorkingDirectory=${APP_DIR}|" \
  -e "s|EnvironmentFile=/opt/zohaonline/.env|EnvironmentFile=${APP_DIR}/.env|" \
  -e "s|/opt/zohaonline/.venv/bin/gunicorn|${APP_DIR}/.venv/bin/gunicorn|" \
  -e "s|127.0.0.1:18123|127.0.0.1:${APP_PORT}|" \
  "/etc/systemd/system/${SERVICE_NAME}.service"

sed \
  -e "s|User=zohaonline|User=${APP_USER}|g" \
  -e "s|WorkingDirectory=/opt/zohaonline|WorkingDirectory=${APP_DIR}|g" \
  -e "s|EnvironmentFile=/opt/zohaonline/.env|EnvironmentFile=${APP_DIR}/.env|g" \
  -e "s|ExecStart=/opt/zohaonline/.venv/bin/python /opt/zohaonline/manage.py|ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/manage.py|g" \
  -e "s|After=network-online.target zohaonline.service|After=network-online.target ${SERVICE_NAME}.service|g" \
  "$APP_DIR/deploy/zohaonline-ai-probe.service" > "/etc/systemd/system/${SERVICE_NAME}-ai-probe.service"
sed -e "s|Unit=zohaonline-ai-probe.service|Unit=${SERVICE_NAME}-ai-probe.service|g" \
  "$APP_DIR/deploy/zohaonline-ai-probe.timer" > "/etc/systemd/system/${SERVICE_NAME}-ai-probe.timer"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
systemctl enable --now "${SERVICE_NAME}-ai-probe.timer" || true
sleep 3
systemctl is-active --quiet "$SERVICE_NAME" || { journalctl -u "$SERVICE_NAME" -n 120 --no-pager; exit 4; }

# Build a release-specific snippet and forcibly replace every old /zohaonline route
# inside all plausible active HTTP/HTTPS server blocks.
mkdir -p /etc/nginx/snippets
sed \
  -e "s|/opt/zohaonline|${APP_DIR}|g" \
  -e "s|5\.61\.27\.185|${SERVER_IP}|g" \
  -e "s|/zohaonline|/${URL_PREFIX}|g" \
  -e "s|127\.0\.0\.1:18123|127.0.0.1:${APP_PORT}|g" \
  "$APP_DIR/deploy/zohaonline-aurora.nginx.conf" > "$SNIPPET"
python3 "$APP_DIR/deploy/force_patch_nginx.py" \
  --sites-enabled /etc/nginx/sites-enabled --snippet "$SNIPPET" --ip "$SERVER_IP"

if ! nginx -t; then
  echo 'Nginx معتبر نشد؛ تنظیمات کامل قبلی بازگردانده می‌شود.' >&2
  rm -rf /etc/nginx
  tar -C / -xzf "$BACKUP_DIR/nginx-before-discovery-270.tar.gz"
  nginx -t || true
  exit 5
fi
systemctl reload nginx
sleep 2

DIRECT_BODY=/tmp/zoha-discovery-direct.json
HTTP_BODY=/tmp/zoha-discovery-http.json
HTTPS_BODY=/tmp/zoha-discovery-https.json
LOGIN_BODY=/tmp/zoha-discovery-login.html
DASHBOARD_BODY=/tmp/zoha-discovery-dashboard.html

DIRECT_CODE="$(curl -sS -o "$DIRECT_BODY" -w '%{http_code}' -H "Host: ${SERVER_IP}" "http://127.0.0.1:${APP_PORT}/${URL_PREFIX}/version/" || true)"
HTTP_CODE="$(curl -sS -o "$HTTP_BODY" -w '%{http_code}' -H "Host: ${SERVER_IP}" "http://127.0.0.1/${URL_PREFIX}/version/" || true)"
HTTPS_CODE="$(curl -ksS -o "$HTTPS_BODY" -w '%{http_code}' --resolve "${SERVER_IP}:443:127.0.0.1" "https://${SERVER_IP}/${URL_PREFIX}/version/" || true)"
LOGIN_CODE="$(curl -sS -o "$LOGIN_BODY" -w '%{http_code}' -H "Host: ${SERVER_IP}" "http://127.0.0.1/${URL_PREFIX}/accounts/login/" || true)"

verify_marker(){ local file="$1" label="$2" code="$3"; if [[ "$code" != 200 ]] || ! grep -q "$RELEASE_MARKER" "$file"; then echo "❌ $label نسخه جست‌وجو و محتوای کامل را سرو نمی‌کند (HTTP $code)" >&2; cat "$file" 2>/dev/null | head -c 700 >&2 || true; echo >&2; return 1; else echo "✅ $label: HTTP $code / $RELEASE_MARKER"; fi; }
verify_marker "$DIRECT_BODY" 'Gunicorn مستقیم' "$DIRECT_CODE"
verify_marker "$HTTP_BODY" 'Nginx HTTP' "$HTTP_CODE"
verify_marker "$HTTPS_BODY" 'Nginx HTTPS' "$HTTPS_CODE"
verify_marker "$LOGIN_BODY" 'صفحه ورود عمومی' "$LOGIN_CODE"

echo
echo '=================================================='
echo ' ضحی آنلاین ۲.۷.۰ ـ جست‌وجو و محتوای کامل با موفقیت فعال شد'
echo '=================================================='
echo "HTTP:  http://${SERVER_IP}/${URL_PREFIX}/"
echo "HTTPS: https://${SERVER_IP}/${URL_PREFIX}/"
echo "تشخیص نسخه: http://${SERVER_IP}/${URL_PREFIX}/version/"
if [[ -n "$ADMIN_PASSWORD" ]]; then
  echo "نام کاربری مدیر: ${ADMIN_USERNAME}"
  if [[ "$GENERATED_ADMIN_PASSWORD" == "1" ]]; then
    echo "رمز موقت مدیر: ${ADMIN_PASSWORD}"
    echo "⚠️ پس از اولین ورود رمز مدیر را تغییر دهید."
  else
    echo "رمز مدیر: طبق ADMIN_PASSWORD اعمال شد."
  fi
else
  echo "حساب و رمزهای موجود حفظ شدند."
fi
echo "نشان قابل مشاهده: نسخه ۲.۷ جست‌وجو و محتوای کامل / ${RELEASE_MARKER}"
echo "پورت backend: ${APP_PORT}"
echo "پشتیبان: ${BACKUP_DIR}"

