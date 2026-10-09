import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("research", "0002_rename_generated_indexes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="indexvalue", name="aliases",
            field=models.TextField(blank=True, help_text="هر نام در یک خط", verbose_name="نام‌های جایگزین"),
        ),
        migrations.AddField(
            model_name="indexvalue", name="approval_status",
            field=models.CharField(choices=[("pending", "در انتظار تأیید"), ("approved", "تأییدشده"), ("rejected", "ردشده")], default="approved", max_length=15),
        ),
        migrations.AddField(
            model_name="indexvalue", name="merged_into",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="merged_items", to="research.indexvalue"),
        ),
        migrations.AddField(
            model_name="indexvalue", name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="indexvalue", name="owner",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="private_index_values", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="indexvalue", name="parent",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="children", to="research.indexvalue"),
        ),
        migrations.AddField(
            model_name="indexvalue", name="visibility",
            field=models.CharField(choices=[("global", "عمومی"), ("private", "شخصی")], default="global", max_length=15),
        ),
        migrations.AddIndex(
            model_name="indexvalue",
            index=models.Index(fields=["visibility", "approval_status"], name="research_in_visibil_5bf939_idx"),
        ),
        migrations.CreateModel(
            name="Source",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=500, verbose_name="نام منبع")),
                ("normalized_title", models.CharField(editable=False, max_length=500)),
                ("author_name", models.CharField(blank=True, max_length=500, verbose_name="پدیدآور یا شخص مرتبط")),
                ("aliases", models.TextField(blank=True, verbose_name="نام‌های جایگزین")),
                ("description", models.TextField(blank=True, verbose_name="توضیح")),
                ("visibility", models.CharField(choices=[("global", "عمومی"), ("private", "شخصی")], default="global", max_length=15)),
                ("approval_status", models.CharField(choices=[("pending", "در انتظار تأیید"), ("approved", "تأییدشده"), ("rejected", "ردشده")], default="approved", max_length=15)),
                ("is_active", models.BooleanField(default=True)),
                ("merged_into", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="merged_sources", to="research.source")),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="private_sources", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "منبع", "verbose_name_plural": "منابع", "ordering": ["title"]},
        ),
        migrations.AddConstraint(
            model_name="source",
            constraint=models.UniqueConstraint(fields=("normalized_title",), name="uniq_source_normalized"),
        ),
        migrations.AlterField(
            model_name="research", name="title",
            field=models.CharField(max_length=100, verbose_name="عنوان فیش"),
        ),
        migrations.AlterField(
            model_name="research", name="researcher",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="researches", to=settings.AUTH_USER_MODEL, verbose_name="فیش‌نگار"),
        ),
        migrations.AlterField(
            model_name="research", name="abstract",
            field=models.TextField(blank=True, verbose_name="خلاصه یا نکته کلیدی"),
        ),
        migrations.AlterField(
            model_name="research", name="body",
            field=models.TextField(verbose_name="متن اصلی"),
        ),
        migrations.AlterField(
            model_name="research", name="search_keywords",
            field=models.TextField(blank=True, verbose_name="کلمات کلیدی"),
        ),
        migrations.AddField(
            model_name="research", name="access_level",
            field=models.CharField(choices=[("private", "فقط خودم"), ("team", "گروه کاری"), ("public", "عمومی")], default="private", max_length=15, verbose_name="سطح دسترسی"),
        ),
        migrations.AddField(
            model_name="research", name="audience_profiles",
            field=models.JSONField(blank=True, default=list, verbose_name="مخاطبان"),
        ),
        migrations.AddField(
            model_name="research", name="author_explanation",
            field=models.TextField(blank=True, verbose_name="توضیح نویسنده"),
        ),
        migrations.AddField(
            model_name="research", name="content_category",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="content_category_researches", to="research.indexvalue", verbose_name="محتوا"),
        ),
        migrations.AddField(
            model_name="research", name="content_kind",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="content_kind_researches", to="research.indexvalue", verbose_name="جنس محتوا"),
        ),
        migrations.AddField(
            model_name="research", name="duplicate_override",
            field=models.BooleanField(default=False, verbose_name="ثبت با وجود هشدار تشابه"),
        ),
        migrations.AddField(
            model_name="research", name="main_format",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="main_format_researches", to="research.indexvalue", verbose_name="قالب اصلی فیش"),
        ),
        migrations.AddField(
            model_name="research", name="publication_status",
            field=models.CharField(choices=[("draft", "پیش‌نویس"), ("published", "منتشرشده"), ("archived", "بایگانی")], default="draft", max_length=20),
        ),
        migrations.AddField(
            model_name="research", name="source",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="researches", to="research.source", verbose_name="منبع"),
        ),
        migrations.AddField(
            model_name="research", name="source_narrator",
            field=models.CharField(blank=True, max_length=250, verbose_name="راوی"),
        ),
        migrations.AddField(
            model_name="research", name="source_note",
            field=models.TextField(blank=True, verbose_name="توضیح آزاد منبع"),
        ),
        migrations.AddField(
            model_name="research", name="source_page",
            field=models.CharField(blank=True, max_length=80, verbose_name="صفحه"),
        ),
        migrations.AddField(
            model_name="research", name="source_type",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="source_type_researches", to="research.indexvalue", verbose_name="نوع منبع"),
        ),
        migrations.AddField(
            model_name="research", name="source_url",
            field=models.URLField(blank=True, max_length=1000, verbose_name="پیوند اینترنتی"),
        ),
        migrations.AddField(
            model_name="research", name="source_volume",
            field=models.CharField(blank=True, max_length=80, verbose_name="جلد"),
        ),
        migrations.AddField(
            model_name="research", name="sub_format",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sub_format_researches", to="research.indexvalue", verbose_name="ریزقالب"),
        ),
        migrations.AddField(
            model_name="research", name="validation_status",
            field=models.CharField(choices=[("unchecked", "بررسی‌نشده"), ("approved", "تأیید اعتبار"), ("needs_changes", "نیازمند اصلاح")], default="unchecked", max_length=20),
        ),
        migrations.AddField(
            model_name="research", name="characters",
            field=models.ManyToManyField(blank=True, related_name="character_researches", to="research.indexvalue", verbose_name="شخصیت‌ها"),
        ),
        migrations.AddField(
            model_name="research", name="occasions",
            field=models.ManyToManyField(blank=True, related_name="occasion_researches", to="research.indexvalue", verbose_name="مناسبت‌ها"),
        ),
        migrations.CreateModel(
            name="TopicAnalysis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("predicate_text", models.CharField(blank=True, max_length=500, verbose_name="محمول پیشنهادی")),
                ("author_interpretation", models.TextField(verbose_name="برداشت نویسنده از این موضوع")),
                ("review_status", models.CharField(choices=[("unchecked", "بررسی‌نشده"), ("approved", "تأییدشده"), ("needs_changes", "نیازمند اصلاح")], default="unchecked", max_length=20)),
                ("order", models.PositiveIntegerField(default=0)),
                ("predicate", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="predicate_researches", to="research.indexvalue", verbose_name="محمول")),
                ("research", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="topic_analyses", to="research.research")),
                ("topic", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="topic_researches", to="research.indexvalue", verbose_name="موضوع")),
                ("processing_keys", models.ManyToManyField(related_name="processing_key_analyses", to="research.indexvalue", verbose_name="کلیدهای پردازش")),
            ],
            options={"verbose_name": "تحلیل موضوعی", "verbose_name_plural": "تحلیل‌های موضوعی", "ordering": ["order", "created_at"]},
        ),
        migrations.AddConstraint(
            model_name="topicanalysis",
            constraint=models.UniqueConstraint(fields=("research", "topic"), name="uniq_topic_per_research"),
        ),
        migrations.CreateModel(
            name="OptionAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("created", "ایجاد"), ("approved", "تأیید"), ("rejected", "رد"), ("renamed", "تغییر نام"), ("deactivated", "غیرفعال‌سازی"), ("activated", "فعال‌سازی"), ("merged", "ادغام")], max_length=20)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("option", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to="research.indexvalue")),
                ("source", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to="research.source")),
            ],
            options={"verbose_name": "سابقه تغییر گزینه", "verbose_name_plural": "سوابق تغییر گزینه‌ها", "ordering": ["-created_at"]},
        ),
    ]
