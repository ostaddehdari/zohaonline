# ارتقای ضحی آنلاین به نسخه ۲.۱.۱ با HTTP و HTTPS

این نسخه برای نصب موجود در `/opt/zohaonline` طراحی شده است و دیتابیس فعلی را حذف نمی‌کند.

اصلاحات این بسته:

- رفع خطای `bootstrap.min.css.map` و `bootstrap.bundle.min.js.map` در `collectstatic`
- فعال‌سازی مسیر `/zohaonline/` در server پورت ۸۰ و server پورت ۴۴۳
- افزودن هر دو origin زیر به تنظیمات CSRF:
  - `http://5.61.27.185`
  - `https://5.61.27.185`
- آزمایش نهایی Gunicorn، HTTP و HTTPS با پاسخ `200`
- حفظ امکان ورود از HTTP و HTTPS؛ انتقال اجباری HTTP به HTTPS فعال نمی‌شود

## اجرا

فایل ZIP را داخل `/root/zohaonline` یا `/root` قرار دهید و اجرا کنید:

```bash
cd /root/zohaonline
sudo apt-get install -y unzip rsync
unzip -o ZohaOnline_ProPlus_v2.1.1_Django_zohaonline.zip
cd ZohaOnline_ProPlus_Django_zohaonline
chmod +x update.sh diagnose.sh
sudo bash update.sh
```

اگر فایل ZIP را در `/root` آپلود کرده‌اید:

```bash
cd /root
sudo apt-get install -y unzip rsync
unzip -o ZohaOnline_ProPlus_v2.1.1_Django_zohaonline.zip
cd ZohaOnline_ProPlus_Django_zohaonline
chmod +x update.sh diagnose.sh
sudo bash update.sh
```

فایل Nginx پیش‌فرض:

```text
/etc/nginx/sites-available/tamap-mygram-router-v1039
```

این فایل باید شامل یک server برای پورت ۸۰ و یک server برای پورت ۴۴۳ با `server_name 5.61.27.185` باشد. در سرور فعلی این دو بلوک وجود دارند.

## خروجی موفق

```text
Gunicorn: HTTP 200
Nginx HTTP: HTTP 200
Nginx HTTPS: HTTP 200
```

نشانی‌ها:

```text
HTTP:  http://5.61.27.185/zohaonline/
HTTPS: https://5.61.27.185/zohaonline/
```

## نکته گواهی SSL

مسیر HTTPS از گواهی‌ای استفاده می‌کند که هم‌اکنون روی server پورت ۴۴۳ Nginx نصب شده است. اگر گواهی برای IP صادر نشده باشد، ممکن است مرورگر هشدار اعتماد یا عدم تطابق نام نشان دهد؛ بااین‌حال مسیریابی HTTPS و خود برنامه فعال خواهند بود.

## پشتیبان

قبل از ارتقا از دیتابیس، کد، `.env` و فایل Nginx نسخه پشتیبان ساخته می‌شود:

```text
/root/zohaonline-update-backup-YYYYMMDD-HHMMSS/
```
