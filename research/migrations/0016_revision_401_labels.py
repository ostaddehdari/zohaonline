from django.db import migrations


def rename_labels(apps, schema_editor):
    IndexType = apps.get_model("research", "IndexType")
    IndexType.objects.filter(slug="content-category").update(
        name="ریز جنس محتوا", description="زیرگونه محتوایی وابسته به جنس محتوا"
    )
    IndexType.objects.filter(slug="predicate").update(
        name="ریز موضوع", description="ریز موضوع وابسته به موضوع اصلی"
    )


class Migration(migrations.Migration):
    dependencies = [("research", "0015_product_revision_4")]
    operations = [migrations.RunPython(rename_labels, migrations.RunPython.noop)]
