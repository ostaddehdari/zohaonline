from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("research", "0006_projects_ai_workflow"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="aiendpointstatus",
            old_name="research_ai_status_25bd2a_idx",
            new_name="research_ai_status_b15980_idx",
        ),
        migrations.RenameIndex(
            model_name="indexvalue",
            old_name="research_in_visibil_5bf939_idx",
            new_name="research_in_visibil_be2e97_idx",
        ),
    ]
