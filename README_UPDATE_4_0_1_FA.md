# به‌روزرسانی ZohaOnline 4.0.1

این نسخه روی 4.0.0 نصب می‌شود و داده‌های موجود را حفظ می‌کند.

## اصلاحات

- تغییر قطعی عنوان «محتوا» به «ریز جنس محتوا» در داده پایه، فرم و اعتبارسنجی
- تغییر قطعی «محمول» به «ریز موضوع» در رابط و مدل داده
- ادغام کشور و شهر در ورودی چندگانه «اقلیم» با حفظ داده‌های قبلی
- بازطراحی ریسپانسیو موبایل برای دکمه‌ها، جدول‌ها، کارت‌های آماری و متن‌های بلند
- افزودن راهنمای یک‌صفحه‌ای در مسیر `documentation/`
- افزودن راهنمای Tooltip به بخش‌ها و فیلدهای اصلی

## نصب روی نسخه فعال

```bash
cd /root/zohaonline/revision4
unzip -o ZohaOnline_Revision4_v4.0.1_Installer.zip
cd ZohaOnline_Revision4_v4.0.1_Django
chmod +x install.sh install_or_upgrade_zoha.sh diagnose.sh
sudo env APP_DIR=/opt/zohaonline SERVER_IP=5.61.27.185 URL_PREFIX=zohaonline bash install.sh
```

## کنترل نهایی

```bash
curl -s http://127.0.0.1:18123/zohaonline/version/
sudo systemctl status zohaonline --no-pager
```

خروجی نسخه باید شامل `4.0.1` و `ZOHA-REVISION-4-401` باشد.
