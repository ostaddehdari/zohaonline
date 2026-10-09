from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("research", "0004_model_state_polish")]

    operations = [
        migrations.AlterField(
            model_name="optionauditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("created", "ایجاد"), ("edited", "ویرایش"),
                    ("approved", "تأیید"), ("rejected", "رد"),
                    ("renamed", "تغییر نام"),
                    ("deactivated", "غیرفعال‌سازی"),
                    ("activated", "فعال‌سازی"), ("merged", "ادغام"),
                ],
                max_length=20,
            ),
        ),
    ]
