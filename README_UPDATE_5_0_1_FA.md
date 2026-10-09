# به‌روزرسانی تصویری ZohaOnline 5.0.1

این نسخه روی 5.0.0 یا نسخه‌های قدیمی‌تر نصب می‌شود و طراحی صفحه نخست را با تصاویر اختصاصی، منبر، کتابخانه، محراب و تزئینات اسلامی تکمیل می‌کند.

## انتقال

    ssh -p 2233 root@5.61.27.185 "mkdir -p /root/zohaonline/revision5"
    scp -P 2233 "ZohaOnline_Revision5_v5.0.1_Installer.zip" root@5.61.27.185:/root/zohaonline/revision5/

## نصب

    ssh -p 2233 root@5.61.27.185
    cd /root/zohaonline/revision5
    unzip -o ZohaOnline_Revision5_v5.0.1_Installer.zip
    cd ZohaOnline_Revision5_v5.0.1_Django
    chmod +x install_or_upgrade_zoha.sh diagnose.sh
    sudo env APP_DIR=/opt/zohaonline SERVER_IP=5.61.27.185 URL_PREFIX=zohaonline bash install_or_upgrade_zoha.sh

پس از نصب، با Ctrl+F5 کش مرورگر را نوسازی کنید.
