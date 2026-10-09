from django.contrib.postgres.indexes import GinIndex
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("research", "0013_discovery_full_content_270")]

    operations = [
        migrations.AddIndex(
            model_name="indexvalue",
            index=GinIndex(
                fields=["normalized_title"],
                name="indexvalue_title_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
        migrations.AddIndex(
            model_name="source",
            index=models.Index(
                fields=["visibility", "approval_status", "is_active"],
                name="research_so_visibil_afe828_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="source",
            index=GinIndex(
                fields=["normalized_title"],
                name="source_title_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
