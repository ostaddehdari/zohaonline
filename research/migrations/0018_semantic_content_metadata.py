from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "research",
            "0017_revision5_title_and_audience",
        ),
    ]

    operations = [

        migrations.AddField(
            model_name="fullcontent",
            name="ai_segments",
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name="بخش‌های معنایی تشخیص‌داده‌شده",
            ),
        ),

        migrations.AddField(
            model_name="fullcontent",
            name="external_references",
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name="ارجاعات معنایی",
            ),
        ),

        migrations.AddField(
            model_name="sermonartifact",
            name="ai_segments",
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name="بخش‌های معنایی تشخیص‌داده‌شده",
            ),
        ),

        migrations.AddField(
            model_name="sermonartifact",
            name="external_references",
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name="ارجاعات معنایی",
            ),
        ),
    ]
