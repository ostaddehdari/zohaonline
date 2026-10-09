# راهنمای نصب و ارتقای ضحی آنلاین شفق خطیب ۲.۴.۰

شناسه انتشار: `ZOHA-AURORA-240`

## ارتقا از نسخه فعلی

فایل ZIP را در `/root/zohaonline` قرار دهید و اجرا کنید:

```bash
cd /root/zohaonline
rm -rf ZohaOnline_Aurora_v2.4.0_Django_zohaonline
unzip -o ZohaOnline_Aurora_v2.4.0_Django_zohaonline.zip
cd ZohaOnline_Aurora_v2.4.0_Django_zohaonline
chmod +x install_or_upgrade_aurora.sh diagnose.sh
sudo bash install_or_upgrade_aurora.sh
```

این نصب‌کننده دیتابیس فعلی، فیش‌ها، پروژه‌ها، کاربران و فایل‌های رسانه‌ای را حفظ می‌کند و قبل از ارتقا نسخه پشتیبان می‌سازد.

## نشانی‌های مهم

- سامانه: `https://5.61.27.185/zohaonline/`
- تشخیص نسخه: `https://5.61.27.185/zohaonline/version/`
- مدیریت سبک‌های منبر: `https://5.61.27.185/zohaonline/sermon-styles/`
- منبرساز هوش مصنوعی: `https://5.61.27.185/zohaonline/ai/sermon/`

پاسخ صفحه نسخه باید شامل `ZOHA-AURORA-240` باشد. Backend روی همان پورت سالم `127.0.0.1:18123` اجرا می‌شود.

## سبک‌های اولیه

- منبر مسئله‌محور
- منبر روایی و داستانی
- منبر استدلالی و آموزشی
- منبر کوتاه رسانه‌ای
- منبر مناسبتی و حماسی

مدیر می‌تواند سبک‌ها را ایجاد، ویرایش، فعال/غیرفعال و پیش‌فرض کند.
