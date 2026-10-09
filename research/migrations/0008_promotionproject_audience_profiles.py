from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("research", "0007_rename_generated_indexes")]

    operations = [
        migrations.AlterField(
            model_name="promotionproject",
            name="target_audience",
            field=models.CharField(blank=True, max_length=500, verbose_name="خلاصه مخاطب هدف"),
        ),
        migrations.AddField(
            model_name="promotionproject",
            name="audience_profiles",
            field=models.JSONField(blank=True, default=list, verbose_name="مخاطب‌شناسی ساختاریافته"),
        ),
    ]
