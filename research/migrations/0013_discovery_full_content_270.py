import django.contrib.postgres.indexes
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("research", "0012_public_featured_curation"),
    ]

    operations = [
        migrations.AddField(
            model_name="research",
            name="seo_tags",
            field=models.JSONField(blank=True, default=list, verbose_name="برچسب‌های SEO"),
        ),
        migrations.AddField(
            model_name="research",
            name="external_references",
            field=models.JSONField(blank=True, default=list, verbose_name="ارجاعات هوشمند"),
        ),
        migrations.AddField(
            model_name="research",
            name="ai_segments",
            field=models.JSONField(blank=True, default=list, verbose_name="بخش‌های تشخیص‌داده‌شده متن"),
        ),
        migrations.AddField(
            model_name="research",
            name="ai_enrichment_status",
            field=models.CharField(blank=True, default="", max_length=30, verbose_name="وضعیت غنی‌سازی هوشمند"),
        ),
        migrations.AddField(
            model_name="research",
            name="ai_enriched_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="research",
            name="featured_image",
            field=models.ImageField(blank=True, null=True, upload_to="featured/%Y/%m/", verbose_name="تصویر شاخص"),
        ),
        migrations.AddField(
            model_name="research",
            name="search_document_normalized",
            field=models.TextField(blank=True, default="", editable=False, verbose_name="سند جست‌وجوی نرمال‌شده"),
        ),
        migrations.AlterField(
            model_name="research",
            name="characters",
            field=models.ManyToManyField(blank=True, related_name="character_researches", to="research.indexvalue", verbose_name="شخصیت‌های اصلی"),
        ),
        migrations.AddField(
            model_name="research",
            name="secondary_characters",
            field=models.ManyToManyField(blank=True, related_name="secondary_character_researches", to="research.indexvalue", verbose_name="شخصیت‌های فرعی / ناقلان"),
        ),
        migrations.AddIndex(
            model_name="research",
            index=django.contrib.postgres.indexes.GinIndex(fields=["search_document_normalized"], name="research_search_trgm", opclasses=["gin_trgm_ops"]),
        ),
        migrations.AlterField(
            model_name="aigenerationlog",
            name="task_type",
            field=models.CharField(choices=[("indexing", "نمایه‌زنی"), ("sermon", "منبرسازی"), ("enrichment", "غنی‌سازی متن"), ("seo", "پیشنهاد SEO"), ("image", "تصویر شاخص")], max_length=20),
        ),
        migrations.CreateModel(
            name="FullContent",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=300, verbose_name="عنوان محتوا")),
                ("body", models.TextField(blank=True, verbose_name="متن / توضیح محتوای کامل")),
                ("file", models.FileField(blank=True, null=True, upload_to="full-content/%Y/%m/", verbose_name="فایل محتوای کامل")),
                ("content_kind", models.CharField(choices=[("speech", "سخنرانی"), ("article", "مقاله"), ("book", "کتاب"), ("broadcast", "گفتگوی تلویزیونی / رادیویی"), ("statement", "بیانیه"), ("interview", "مصاحبه"), ("lesson", "درسنامه تبلیغی برای دانش‌آموزان یا دانشجویان")], max_length=30, verbose_name="جنس محتوای کامل")),
                ("audience_profiles", models.JSONField(blank=True, default=list, verbose_name="مخاطب")),
                ("duration_minutes", models.PositiveIntegerField(blank=True, null=True, verbose_name="مدت زمان ارائه (دقیقه)")),
                ("word_count", models.PositiveIntegerField(default=0, editable=False, verbose_name="تعداد واژگان")),
                ("presentation_date", models.DateField(blank=True, null=True, verbose_name="تاریخ ارائه محتوا")),
                ("status", models.CharField(choices=[("draft", "پیش‌نویس"), ("ready", "آماده استفاده"), ("archived", "بایگانی‌شده")], db_index=True, default="draft", max_length=20)),
                ("author_owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="full_content_authors", to="research.indexvalue", verbose_name="صاحب اثر")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="full_contents", to=settings.AUTH_USER_MODEL, verbose_name="ثبت‌کننده")),
                ("predicate", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="full_content_predicates", to="research.indexvalue", verbose_name="محمول")),
                ("presentation_place", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="full_content_places", to="research.indexvalue", verbose_name="مکان ارائه / انتشار")),
                ("topic", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="full_content_topics", to="research.indexvalue", verbose_name="موضوع")),
                ("characters", models.ManyToManyField(blank=True, related_name="full_content_characters", to="research.indexvalue", verbose_name="شخصیت")),
                ("occasions", models.ManyToManyField(blank=True, related_name="full_content_occasions", to="research.indexvalue", verbose_name="مناسبت")),
                ("processing_keys", models.ManyToManyField(blank=True, related_name="full_content_processing_keys", to="research.indexvalue", verbose_name="کلید پردازش")),
            ],
            options={
                "verbose_name": "محتوای کامل",
                "verbose_name_plural": "محتواهای کامل",
                "ordering": ["-updated_at"],
                "indexes": [models.Index(fields=["owner", "status"], name="research_fu_owner_i_6ea105_idx"), models.Index(fields=["content_kind", "-updated_at"], name="research_fu_content_76176c_idx")],
            },
        ),
    ]
