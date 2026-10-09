#!/usr/bin/env bash
set -u
SERVICE_NAME="${SERVICE_NAME:-zohaonline}"
SERVER_IP="${SERVER_IP:-5.61.27.185}"
URL_PREFIX="${URL_PREFIX:-zohaonline}"
APP_PORT="${APP_PORT:-18123}"
MARKER="ZOHA-DISCOVERY-270"

check(){ local label="$1" url="$2" extra="$3"; local file="/tmp/zoha-diag-$RANDOM"; local code; code=$(eval "curl $extra -sS -o '$file' -w '%{http_code}' '$url'" 2>/dev/null || true); if [[ "$code" == 200 ]] && grep -q "$MARKER" "$file"; then echo "✅ $label: HTTP $code / $MARKER"; else echo "❌ $label: HTTP $code"; head -c 500 "$file" 2>/dev/null || true; echo; fi; rm -f "$file"; }

printf '\n=== release files ===\n'
cat /opt/zohaonline/VERSION 2>/dev/null || true
grep -n "$MARKER" /opt/zohaonline/zoha/release.py 2>/dev/null | head || true

printf '\n=== systemd ===\n'
systemctl status "$SERVICE_NAME" --no-pager -l || true
printf '\n=== listeners ===\n'
ss -ltnp | grep -E ":(18015|18122|18123)[[:space:]]" || true

printf '\n=== release verification ===\n'
check 'Gunicorn مستقیم' "http://127.0.0.1:${APP_PORT}/${URL_PREFIX}/version/" "-H 'Host: ${SERVER_IP}'"
check 'Nginx HTTP' "http://127.0.0.1/${URL_PREFIX}/version/" "-H 'Host: ${SERVER_IP}'"
check 'Nginx HTTPS' "https://${SERVER_IP}/${URL_PREFIX}/version/" "-k --resolve '${SERVER_IP}:443:127.0.0.1'"

printf '\n=== Nginx headers ===\n'
curl -sSI -H "Host: ${SERVER_IP}" "http://127.0.0.1/${URL_PREFIX}/version/" | grep -iE 'HTTP/|X-Zoha|Server:' || true
printf '\n=== Nginx validation ===\n'
nginx -t || true
printf '\n=== active route excerpts ===\n'
nginx -T 2>&1 | grep -n -B8 -A38 -E "${URL_PREFIX}|discovery-270|18123" || true
printf '\n=== migration drift ===\n'
runuser -u zohaonline -- /opt/zohaonline/.venv/bin/python /opt/zohaonline/manage.py makemigrations --check --dry-run || true
printf '\n=== demo seed counts (should normally be zero in production) ===\n'
runuser -u zohaonline -- /opt/zohaonline/.venv/bin/python /opt/zohaonline/manage.py shell -c "from accounts.models import User; from research.models import Research,PromotionProject,ReviewComment; print('research=',Research.objects.filter(author_explanation__contains='ZOHA-DEMO-231').count(),'projects=',PromotionProject.objects.filter(title__in=['خانواده آرام؛ خانه گفت‌وگو','جوان مؤمن؛ امید و هویت','رسانه مسئول؛ روایت اخلاقی']).count(),'researchers=',User.objects.filter(username__in=['demo_researcher_1','demo_researcher_2','demo_researcher_3']).count(),'reviewers=',User.objects.filter(username__in=['demo_reviewer_1','demo_reviewer_2']).count(),'messages=',ReviewComment.objects.filter(body__contains='ZOHA-DEMO-231').count())" || true
