from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("research", "0003_professional_fish_schema"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="indexvalue",
            options={
                "ordering": ["title"],
                "verbose_name": "مقدار نمایه",
                "verbose_name_plural": "مقادیر نمایه",
            },
        ),
        migrations.AlterModelOptions(
            name="research",
            options={
                "ordering": ["-updated_at"],
                "verbose_name": "فیش",
                "verbose_name_plural": "فیش‌ها",
            },
        ),
        migrations.AlterField(
            model_name="research",
            name="source_file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="research/%Y/%m/",
                verbose_name="فایل منبع",
            ),
        ),
        migrations.AlterField(
            model_name="workflowevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("created", "ایجاد"), ("submitted", "ارسال"),
                    ("assigned", "تخصیص"), ("commented", "ثبت خطا"),
                    ("changes_requested", "برگشت اصلاح"),
                    ("resubmitted", "ارسال مجدد"), ("approved", "تأیید"),
                    ("rejected", "رد"), ("published", "انتشار"),
                    ("updated", "ویرایش"),
                ],
                max_length=30,
            ),
        ),
    ]
