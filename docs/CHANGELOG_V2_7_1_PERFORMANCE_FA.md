# ضحی آنلاین ۲.۷.۱ — اصلاح گلوگاه‌های کارایی

## اصلاحات

- شمارنده‌های داشبورد از چند Query مستقل به یک Query تجمیعی تبدیل شدند.
- جست‌وجوی گزینه‌ها و منابع دیگر ۲۰۰۰ تا ۳۰۰۰ رکورد را برای محاسبه شباهت به Python منتقل نمی‌کند؛ در PostgreSQL از trigram و در SQLite از فیلتر محدود دیتابیس استفاده می‌شود.
- دو GIN trigram index برای `IndexValue.normalized_title` و `Source.normalized_title` و یک index ترکیبی برای وضعیت نمایش منبع اضافه شد.
- نمایه‌های صفحه جزئیات فیش با یک prefetch دریافت و در حافظه گروه‌بندی می‌شوند؛ N+1 Query حذف شد.
- ایجاد کارهای ارزیابی از Query داخل حلقه به `bulk_create(ignore_conflicts=True)` تغییر کرد.
- فراخوانی کند سرویس AI/تصویر از تراکنش سراسری ایجاد و ویرایش فیش خارج شد؛ در نتیجه اتصال و قفل دیتابیس هنگام انتظار شبکه نگه داشته نمی‌شود.
- health check اتصال PostgreSQL فعال شد.
- Gunicorn با ۳ worker و ۲ thread، بازیافت دوره‌ای worker، keep-alive و jitter تنظیم شد.

## استقرار

پس از جایگزینی فایل‌ها، migrationها اجرا و سرویس بازنشانی شود:

```bash
sudo -u zohaonline /opt/zohaonline/.venv/bin/python /opt/zohaonline/manage.py migrate
sudo systemctl daemon-reload
sudo systemctl restart zohaonline
```

## اعتبارسنجی

- `python -m compileall`: موفق
- `manage.py check`: موفق
- migration جدید روی دیتابیس تست اعمال شد.
- ۱۰ تست از ۱۲ تست موجود موفق‌اند. دو تست فرم قدیمی از قبل با قواعد جدید اعتبارسنجی کلمات کلیدی ناسازگارند و ارتباطی با اصلاحات کارایی ندارند.
