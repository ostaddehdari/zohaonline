from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("research", "0011_zoha_260_editorial_workflow")]

    operations = [
        migrations.AddField(
            model_name="research",
            name="is_featured",
            field=models.BooleanField(db_index=True, default=False, verbose_name="منتخب صفحه عمومی"),
        ),
        migrations.AddField(
            model_name="research",
            name="featured_order",
            field=models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش منتخب"),
        ),
    ]
