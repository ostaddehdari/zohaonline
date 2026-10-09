# تغییرات نسخه ۲.۱.۱

- رفع توقف `collectstatic` به‌علت نبود فایل‌های Bootstrap sourcemap
- پاک‌سازی static قبلی پیش از جمع‌آوری مجدد
- درج idempotent تنظیمات `/zohaonline/` در serverهای پورت ۸۰ و ۴۴۳
- پشتیبانی هم‌زمان از HTTP و HTTPS بدون redirect اجباری
- افزودن originهای HTTP و HTTPS به `CSRF_TRUSTED_ORIGINS`
- تست خودکار Gunicorn، HTTP و HTTPS در پایان نصب و ارتقا
- افزودن تشخیص خطای دقیق برای نبود یا تکرار serverهای ۸۰ و ۴۴۳
- حفظ پشتیبان دیتابیس، کد، `.env` و Nginx پیش از ارتقا
