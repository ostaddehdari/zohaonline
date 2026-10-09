# ارتقای ضحی آنلاین 2.6 به 2.7

این بسته برای ارتقای درجا روی `/opt/zohaonline` طراحی شده است.

- دیتابیس PostgreSQL، فایل‌های media، `.env` و virtualenv حفظ می‌شوند.
- قبل از ارتقا از برنامه، دیتابیس و Nginx نسخه پشتیبان ساخته می‌شود.
- داده‌های نمایشی قدیمی به‌صورت پیش‌فرض حذف می‌شوند (`PURGE_DEMO_DATA=1`).
- داده نمایشی جدید به‌صورت پیش‌فرض ساخته نمی‌شود (`SEED_DEMO_DATA=0`).
- حساب‌ها و رمزهای موجود در ارتقا بدون تغییر حفظ می‌شوند؛ فقط اگر `ADMIN_PASSWORD` صریحاً داده شود رمز مدیر تغییر می‌کند.
- تنظیمات HTTPS موجود در `.env` در ارتقا بازنویسی نمی‌شوند.

## اجرای ارتقا

```bash
cd /root/zohaonline/ZohaOnline_Discovery_FullContent_v2.7.0_Django_zohaonline
chmod +x install_or_upgrade_zoha.sh diagnose.sh
sudo env APP_DIR=/opt/zohaonline SERVER_IP=5.61.27.185 URL_PREFIX=zohaonline bash install_or_upgrade_zoha.sh
```

برای نگه‌داشتن داده‌های Demo، `PURGE_DEMO_DATA=0` بدهید.
برای تغییر رمز مدیر در همین اجرا، `ADMIN_PASSWORD='...'` نیز اضافه کنید.

## تنظیمات اختیاری

در `/opt/zohaonline/.env` می‌توان این مقادیر را تعریف کرد:

- `ZOHA_CHANNEL_URL` لینک کانال ضحی
- `ZOHA_IMAGE_API_URL` endpoint سرویس تولید تصویر OpenAI-compatible
- `ZOHA_IMAGE_API_KEY` کلید سرویس تصویر
- `ZOHA_QURAN_REFERENCE_URL` آدرس مرجع قرآن
- `ZOHA_HADITH_REFERENCE_URL` آدرس مرجع حدیث
- `ZOHA_POETRY_REFERENCE_URL` آدرس مرجع شعر

پس از تغییر `.env` اجرا کنید:

```bash
sudo systemctl restart zohaonline
```
