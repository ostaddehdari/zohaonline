from django.db import migrations, models
import django.db.models.deletion


def seed_styles(apps, schema_editor):
    SermonStyle = apps.get_model("research", "SermonStyle")
    styles = [
        {
            "name": "منبر مسئله‌محور",
            "slug": "problem-based",
            "description": "شروع از مسئله واقعی مخاطب و حرکت مرحله‌ای به سوی تحلیل، شاهد و راهکار.",
            "system_prompt": "منبر را مسئله‌محور بنویس؛ با یک مسئله واقعی و ملموس آغاز کن، ریشه‌ها را تحلیل کن، هر محور را با شواهد فیش‌ها پشتیبانی کن و در پایان راهکارهای عملی و قابل اجرا ارائه بده.",
            "outline_template": "طرح مسئله؛ چرایی اهمیت؛ سه ریشه یا محور؛ شواهد؛ راهکارهای فردی و جمعی؛ جمع‌بندی و دعوت به عمل.",
            "tone": "صمیمی، تحلیلی و راه‌حل‌محور",
            "language_level": "عمومی و روان",
            "duration_minutes": 25,
            "audience_guidance": "مثال‌ها و اصطلاحات با سن، سطح سواد و دغدغه مخاطب پروژه تطبیق یابد.",
            "is_default": True,
            "order": 10,
        },
        {
            "name": "منبر روایی و داستانی",
            "slug": "narrative",
            "description": "پیشبرد پیام با روایت، تصویرسازی و گره‌های عاطفی.",
            "system_prompt": "منبر را روایی بساز؛ یک صحنه یا داستان کوتاه معتبر از فیش‌ها را محور قرار بده، روایت را در طول منبر ادامه بده و مفاهیم را در دل آن توضیح بده. از داستان‌سازی خارج از منابع خودداری کن.",
            "outline_template": "صحنه آغازین؛ گره روایت؛ نکته اول؛ بازگشت به روایت؛ نکته دوم و سوم؛ اوج عاطفی؛ نتیجه عملی.",
            "tone": "گرم، تصویری و عاطفی",
            "language_level": "روان و شنیداری",
            "duration_minutes": 20,
            "audience_guidance": "روایت‌ها کوتاه، قابل فهم و متناسب با تجربه زیسته مخاطب باشند.",
            "order": 20,
        },
        {
            "name": "منبر استدلالی و آموزشی",
            "slug": "analytical",
            "description": "ساختار منظم، تعریف دقیق، پاسخ به پرسش و جمع‌بندی آموزشی.",
            "system_prompt": "منبر را استدلالی و آموزشی بنویس؛ اصطلاحات را تعریف کن، ادعاها را مرحله‌به‌مرحله توضیح بده، پرسش‌ها و شبهات محتمل را پاسخ بده و میان گزاره‌ها پیوند منطقی روشن برقرار کن.",
            "outline_template": "تعریف موضوع؛ پرسش محوری؛ مبانی؛ سه استدلال؛ پاسخ به شبهه؛ نتیجه و تمرین عملی.",
            "tone": "جدی، روشن و منظم",
            "language_level": "متوسط تا تخصصی",
            "duration_minutes": 30,
            "audience_guidance": "سطح اصطلاحات با آشنایی دینی و تحصیلی مخاطب تنظیم شود.",
            "order": 30,
        },
        {
            "name": "منبر کوتاه رسانه‌ای",
            "slug": "short-media",
            "description": "مناسب کلیپ، شبکه اجتماعی و ارائه‌های کوتاه با پیام مرکزی واحد.",
            "system_prompt": "یک منبر کوتاه رسانه‌ای با یک پیام مرکزی، شروع قلاب‌دار، جمله‌های کوتاه، سه نکته فشرده و پایان ماندگار بساز. از پراکندگی و مقدمه طولانی پرهیز کن.",
            "outline_template": "قلاب ۳۰ ثانیه‌ای؛ پیام مرکزی؛ سه نکته کوتاه؛ شاهد؛ جمع‌بندی یک‌جمله‌ای و دعوت به اقدام.",
            "tone": "انرژی‌بخش، مستقیم و موجز",
            "language_level": "ساده و رسانه‌ای",
            "duration_minutes": 8,
            "audience_guidance": "برای شبکه اجتماعی، جمله‌ها کوتاه و قابلیت برش به بخش‌های مستقل داشته باشند.",
            "order": 40,
        },
        {
            "name": "منبر مناسبتی و حماسی",
            "slug": "occasion-epic",
            "description": "مناسب مناسبت‌های مذهبی و ملی با پیوند عاطفه، هویت و مسئولیت.",
            "system_prompt": "منبر را مناسبتی و حماسی بساز؛ مناسبت را با نیاز امروز مخاطب پیوند بده، از شعارزدگی دوری کن، هویت جمعی و مسئولیت عملی را برجسته کن و فقط از شواهد موجود در فیش‌ها استفاده کن.",
            "outline_template": "فضاسازی مناسبت؛ پیوند تاریخی و امروز؛ سه پیام هویتی؛ مسئولیت مخاطب؛ پایان امیدبخش.",
            "tone": "حماسی، امیدآفرین و مسئولیت‌ساز",
            "language_level": "عمومی",
            "duration_minutes": 25,
            "audience_guidance": "شدت عاطفی و واژگان حماسی با سن و بستر ارائه تنظیم شود.",
            "order": 50,
        },
    ]
    for data in styles:
        defaults = data.copy()
        slug = defaults.pop("slug")
        SermonStyle.objects.update_or_create(slug=slug, defaults=defaults)


class Migration(migrations.Migration):
    dependencies = [("research", "0008_promotionproject_audience_profiles")]

    operations = [
        migrations.CreateModel(
            name="SermonStyle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=180, unique=True, verbose_name="نام سبک منبر")),
                ("slug", models.SlugField(allow_unicode=True, max_length=180, unique=True)),
                ("description", models.TextField(blank=True, verbose_name="معرفی سبک")),
                ("system_prompt", models.TextField(help_text="ویژگی‌های خطابی، محدودیت‌ها و روش نگارش این سبک را دقیق بنویسید.", verbose_name="دستور تخصصی برای هوش مصنوعی")),
                ("outline_template", models.TextField(blank=True, help_text="برای نمونه: آغاز عاطفی، طرح مسئله، سه محور، روایت، جمع‌بندی و اقدام عملی.", verbose_name="ساختار پیشنهادی منبر")),
                ("tone", models.CharField(blank=True, max_length=180, verbose_name="لحن")),
                ("language_level", models.CharField(blank=True, max_length=180, verbose_name="سطح زبان")),
                ("duration_minutes", models.PositiveSmallIntegerField(default=20, verbose_name="مدت پیشنهادی به دقیقه")),
                ("audience_guidance", models.TextField(blank=True, verbose_name="راهنمای تطبیق با مخاطب")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("is_default", models.BooleanField(default=False, verbose_name="سبک پیش‌فرض")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")),
            ],
            options={"verbose_name": "سبک منبر", "verbose_name_plural": "سبک‌های منبر", "ordering": ["order", "name"]},
        ),
        migrations.AddField(
            model_name="promotionproject",
            name="sermon_style",
            field=models.ForeignKey(blank=True, help_text="هوش مصنوعی منبر را بر اساس این سبک، لحن و ساختار تولید می‌کند.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="projects", to="research.sermonstyle", verbose_name="سبک منبر"),
        ),
        migrations.RunPython(seed_styles, migrations.RunPython.noop),
    ]
