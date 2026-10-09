# راهنمای نصب و ارتقای ضحی آنلاین شفق داده ۲.۳.۱

این نسخه با شناسه `ZOHA-AURORA-231` شامل داده نمونه داخلی و اصلاح مخاطب‌شناسی و تحلیل موضوعی است.

## محتوای Seed داخلی

- ۳۰ فیش پژوهشی نمایه‌خورده و مرتبط
- ۳ پروژه تبلیغی با ۱۰ فیش مرتبط در هر پروژه
- ۳ پژوهشگر نمونه
- ۲ ارزیاب نمونه
- ۳۰ کار ارزیابی و ۹۰ پیام گفت‌وگوی پژوهشگر و ارزیاب
- تحلیل موضوعی مستقل، کلیدهای پردازش، محمول، برداشت نویسنده، منبع و مخاطبان ساختاریافته

## حساب‌ها

- `admin` / `123456`
- `demo_researcher_1` تا `demo_researcher_3` / `Zoha@123456`
- `demo_reviewer_1` تا `demo_reviewer_2` / `Zoha@123456`

## نصب یا ارتقا

فایل ZIP را در `/root/zohaonline` قرار دهید و اجرا کنید:

```bash
cd /root/zohaonline
rm -rf ZohaOnline_Aurora_v2.3.1_Django_zohaonline
unzip -o ZohaOnline_Aurora_v2.3.1_Django_zohaonline.zip
cd ZohaOnline_Aurora_v2.3.1_Django_zohaonline
chmod +x install_or_upgrade_aurora.sh install.sh update.sh diagnose.sh
sudo bash install_or_upgrade_aurora.sh
```

نصب‌کننده دیتابیس موجود را حفظ و از آن پشتیبان تهیه می‌کند، Migrationها را اجرا می‌کند و فرمان `seed_demo_content --reset-passwords` را به‌صورت خودکار اجرا می‌کند. Seed تکرارپذیر است و با اجرای مجدد، ۳۰ فیش تکراری تولید نمی‌کند.

## نشانی‌ها

- HTTP: `http://5.61.27.185/zohaonline/`
- HTTPS: `https://5.61.27.185/zohaonline/`
- تشخیص نسخه: `http://5.61.27.185/zohaonline/version/`

خروجی endpoint نسخه باید شامل `ZOHA-AURORA-231` باشد. Backend این نسخه به‌طور پیش‌فرض روی `127.0.0.1:18123` اجرا می‌شود.

## اجرای دوباره Seed در صورت نیاز

```bash
sudo -u zohaonline /opt/zohaonline/.venv/bin/python \
  /opt/zohaonline/manage.py seed_demo_content --reset-passwords
```

## تشخیص استقرار

```bash
sudo bash diagnose.sh
```
