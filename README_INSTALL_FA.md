# نصب / ارتقای ضحی آنلاین 2.7.0

Release: `ZOHA-DISCOVERY-270`

## ارتقا روی نصب فعلی `/opt/zohaonline`

```bash
cd /root/zohaonline/ZohaOnline_Discovery_FullContent_v2.7.0_Django_zohaonline
chmod +x install_or_upgrade_zoha.sh diagnose.sh
sudo env APP_DIR=/opt/zohaonline SERVER_IP=5.61.27.185 URL_PREFIX=zohaonline bash install_or_upgrade_zoha.sh
```

در Upgrade، `.env`، کاربران، رمزها، دیتابیس و Media حفظ می‌شوند. اسکریپت قبل از تغییر از برنامه، PostgreSQL و Nginx Backup می‌سازد.

به‌صورت پیش‌فرض:
- `PURGE_DEMO_DATA=1` → داده‌های نمایشی شناخته‌شده حذف می‌شوند.
- `SEED_DEMO_DATA=0` → داده Demo جدید ساخته نمی‌شود.
- اگر `ADMIN_PASSWORD` ندهید، رمز مدیر موجود تغییر نمی‌کند.

برای نگه‌داشتن Demo:

```bash
sudo env APP_DIR=/opt/zohaonline SERVER_IP=5.61.27.185 URL_PREFIX=zohaonline PURGE_DEMO_DATA=0 bash install_or_upgrade_zoha.sh
```

پس از نصب:

```bash
curl -k https://5.61.27.185/zohaonline/version/
sudo systemctl status zohaonline --no-pager
sudo nginx -t
```

Endpoint نسخه باید `2.7.0` و `ZOHA-DISCOVERY-270` را گزارش کند.
