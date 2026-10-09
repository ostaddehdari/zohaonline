from django.db import migrations, models

def remove_geography(apps, schema_editor):
    Research = apps.get_model("research", "Research")
    for item in Research.objects.exclude(audience_profiles=[]).iterator():
        cleaned = []
        for row in item.audience_profiles or []:
            if isinstance(row, dict):
                row = dict(row)
                for key in ("regions", "countries", "cities", "climates", "country", "city", "climate"):
                    row.pop(key, None)
                cleaned.append(row)
        item.audience_profiles = cleaned
        item.save(update_fields=["audience_profiles"])

class Migration(migrations.Migration):
    dependencies = [("research", "0016_revision_401_labels")]
    operations = [
        migrations.AlterField(model_name="research", name="body", field=models.TextField(blank=True, verbose_name="متن اصلی")),
        migrations.RunPython(remove_geography, migrations.RunPython.noop),
    ]
