# به‌روزرسانی ZohaOnline 5.0.0

این بسته روی نصب فعلی /opt/zohaonline ارتقا درجا انجام می‌دهد، از کد و پایگاه‌داده نسخه پشتیبان می‌گیرد، مهاجرت‌ها را اجرا می‌کند و سرویس را بررسی می‌کند.

## انتقال از Windows

    scp -i ~/.ssh/id_ed25519_vps -P 2233 "D:\\zip\\ZohaOnline_Revision5_v5.0.0_Installer.zip" root@5.61.27.185:/root/zohaonline/revision5/

## نصب یا ارتقا

    ssh -i ~/.ssh/id_ed25519_vps -p 2233 root@5.61.27.185
    cd /root/zohaonline/revision5
    unzip -o ZohaOnline_Revision5_v5.0.0_Installer.zip
    cd ZohaOnline_Revision5_v5.0.0_Django
    chmod +x install_or_upgrade_zoha.sh diagnose.sh
    sudo env APP_DIR=/opt/zohaonline SERVER_IP=5.61.27.185 URL_PREFIX=zohaonline bash install_or_upgrade_zoha.sh

پس از پایان، http://5.61.27.185/zohaonline/version/ را بررسی کنید. نسخه باید 5.0.0 و نشان ZOHA-REVISION-5-500 باشد.

## تغییرات اصلی

- صفحه نخست واکنش‌گرا مطابق طرح مرجع دسکتاپ و موبایل
- جست‌وجوی یکپارچه و سه درگاه مولد، ترکیبی و تکمیلی
- رفع گیرکردن backdrop و صفحه سیاه پنجره‌های افزودن
- حذف بارگذاری تکراری Bootstrap
- عنوان به‌عنوان تنها فیلد مسدودکننده
- حذف کشور، شهر و اقلیم و پاک‌سازی داده‌های قدیمی
- جلوگیری از خروج متن از دکمه، جدول و کارت آماری
- راهنمای contextual با tooltip در فرم‌ها
