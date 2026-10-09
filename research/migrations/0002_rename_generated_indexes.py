from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("research", "0001_initial"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="indexvalue",
            old_name="research_in_index_t_d0cb4b_idx",
            new_name="research_in_index_t_b2aa5f_idx",
        ),
        migrations.RenameIndex(
            model_name="notification",
            old_name="research_no_recipie_693e84_idx",
            new_name="research_no_recipie_a6cb58_idx",
        ),
        migrations.RenameIndex(
            model_name="research",
            old_name="research_re_researc_266011_idx",
            new_name="research_re_researc_74bba1_idx",
        ),
        migrations.RenameIndex(
            model_name="research",
            old_name="research_re_status_3171c9_idx",
            new_name="research_re_status_43a7ca_idx",
        ),
        migrations.RenameIndex(
            model_name="researchindex",
            old_name="research_re_researc_e8e4e9_idx",
            new_name="research_re_researc_15c0c9_idx",
        ),
    ]
