import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("research", "0005_option_audit_edited"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIEndpointStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider_name", models.CharField(max_length=180)),
                ("provider_path", models.CharField(max_length=500)),
                ("model_name", models.CharField(max_length=250)),
                ("status", models.CharField(choices=[("active", "فعال"), ("inactive", "غیرفعال"), ("skipped", "نیازمند احراز هویت یا پیش‌نیاز")], db_index=True, default="inactive", max_length=20)),
                ("needs_auth", models.BooleanField(default=False)),
                ("latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("response_excerpt", models.TextField(blank=True)),
                ("last_error", models.TextField(blank=True)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("consecutive_failures", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "وضعیت ارائه‌دهنده هوش مصنوعی",
                "verbose_name_plural": "وضعیت ارائه‌دهندگان هوش مصنوعی",
                "ordering": ["provider_name", "model_name"],
            },
        ),
        migrations.CreateModel(
            name="AIProbeRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("total", models.PositiveIntegerField(default=0)),
                ("active", models.PositiveIntegerField(default=0)),
                ("inactive", models.PositiveIntegerField(default=0)),
                ("skipped", models.PositiveIntegerField(default=0)),
                ("details", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "اجرای پایش هوش مصنوعی",
                "verbose_name_plural": "اجراهای پایش هوش مصنوعی",
                "ordering": ["-started_at"],
            },
        ),
        migrations.CreateModel(
            name="PromotionProject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180, verbose_name="عنوان پروژه تبلیغی")),
                ("description", models.TextField(blank=True, verbose_name="توضیحات")),
                ("objective", models.TextField(blank=True, verbose_name="هدف پروژه")),
                ("target_audience", models.CharField(blank=True, max_length=300, verbose_name="مخاطب هدف")),
                ("status", models.CharField(choices=[("draft", "در حال تدوین"), ("active", "فعال"), ("completed", "تکمیل‌شده"), ("archived", "بایگانی")], default="draft", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("indexes", models.ManyToManyField(blank=True, related_name="promotion_projects", to="research.indexvalue", verbose_name="نمایه‌های پروژه")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="promotion_projects", to=settings.AUTH_USER_MODEL, verbose_name="مالک پروژه")),
            ],
            options={
                "verbose_name": "پروژه تبلیغی",
                "verbose_name_plural": "پروژه‌های تبلیغی",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="ProjectResearch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note", models.CharField(blank=True, max_length=500, verbose_name="یادداشت")),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("added_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="added_project_researches", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_researches", to="research.promotionproject")),
                ("research", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_links", to="research.research")),
            ],
            options={
                "verbose_name": "فیش پروژه",
                "verbose_name_plural": "فیش‌های پروژه",
                "ordering": ["order", "-created_at"],
            },
        ),
        migrations.AddField(
            model_name="promotionproject",
            name="researches",
            field=models.ManyToManyField(related_name="promotion_projects", through="research.ProjectResearch", to="research.research", verbose_name="فیش‌های پروژه"),
        ),
        migrations.CreateModel(
            name="AIGenerationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_type", models.CharField(choices=[("indexing", "نمایه‌زنی"), ("sermon", "منبرسازی")], max_length=20)),
                ("prompt", models.TextField()),
                ("response", models.TextField(blank=True)),
                ("succeeded", models.BooleanField(default=False)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("endpoint", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="generation_logs", to="research.aiendpointstatus")),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ai_generation_logs", to="research.promotionproject")),
                ("research", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ai_generation_logs", to="research.research")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ai_generation_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "گزارش تولید هوش مصنوعی",
                "verbose_name_plural": "گزارش‌های تولید هوش مصنوعی",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="aiendpointstatus",
            constraint=models.UniqueConstraint(fields=("provider_path", "model_name"), name="uniq_ai_provider_model"),
        ),
        migrations.AddIndex(
            model_name="aiendpointstatus",
            index=models.Index(fields=["status", "last_checked_at"], name="research_ai_status_25bd2a_idx"),
        ),
        migrations.AddConstraint(
            model_name="projectresearch",
            constraint=models.UniqueConstraint(fields=("project", "research"), name="uniq_research_per_promotion_project"),
        ),
    ]
