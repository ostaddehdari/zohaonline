from django.conf import settings
import re
from django.db import migrations, models
import django.db.models.deletion


def normalize_audiences(apps, schema_editor):
    Research = apps.get_model('research', 'Research')
    IndexType = apps.get_model('research', 'IndexType')
    IndexValue = apps.get_model('research', 'IndexValue')
    audience_types = {}
    for slug in ('audience-job', 'audience-country', 'audience-city'):
        index_type = IndexType.objects.filter(slug=slug).first()
        audience_types[slug] = {str(x.pk): x.title for x in IndexValue.objects.filter(index_type=index_type)} if index_type else {}
    for item in Research.objects.exclude(audience_profiles=[]).iterator():
        changed = False
        rows = []
        for row in item.audience_profiles or []:
            if not isinstance(row, dict):
                continue
            row = dict(row)
            if 'countries' not in row:
                country = str(row.pop('country', '') or '').strip()
                row['countries'] = [country] if country else []
                changed = True
            if 'cities' not in row:
                city = str(row.pop('city', '') or '').strip()
                row['cities'] = [city] if city else []
                changed = True
            for key, slug in (('jobs','audience-job'), ('countries','audience-country'), ('cities','audience-city')):
                values = row.get(key) or []
                normalized = [audience_types[slug].get(str(value), str(value)) for value in values if str(value).strip()]
                if normalized != values:
                    row[key] = normalized
                    changed = True
            rows.append(row)
        if changed:
            item.audience_profiles = rows
            item.save(update_fields=['audience_profiles'])




def normalize_occasion_dates(apps, schema_editor):
    IndexType = apps.get_model('research', 'IndexType')
    IndexValue = apps.get_model('research', 'IndexValue')
    occasion_type = IndexType.objects.filter(slug='occasion').first()
    if not occasion_type:
        return
    months = 'فروردین اردیبهشت خرداد تیر مرداد شهریور مهر آبان آذر دی بهمن اسفند'.split()
    pattern = re.compile(r'([۰-۹0-9]{1,2})\s+(' + '|'.join(months) + r')')
    trans = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    for item in IndexValue.objects.filter(index_type=occasion_type).iterator():
        meta = dict(item.metadata or {})
        if meta.get('jalali_day') and meta.get('jalali_month'):
            continue
        match = pattern.search(item.title or '')
        if not match:
            continue
        meta['jalali_day'] = int(match.group(1).translate(trans))
        meta['jalali_month'] = match.group(2)
        item.metadata = meta
        item.save(update_fields=['metadata'])


def reverse_occasion_dates(apps, schema_editor):
    pass


def reverse_audiences(apps, schema_editor):
    Research = apps.get_model('research', 'Research')
    for item in Research.objects.exclude(audience_profiles=[]).iterator():
        rows = []
        changed = False
        for row in item.audience_profiles or []:
            if not isinstance(row, dict):
                continue
            row = dict(row)
            if 'countries' in row:
                row['country'] = (row.pop('countries') or [''])[0]
                changed = True
            if 'cities' in row:
                row['city'] = (row.pop('cities') or [''])[0]
                changed = True
            rows.append(row)
        if changed:
            item.audience_profiles = rows
            item.save(update_fields=['audience_profiles'])


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0003_team_access_domain'),
        ('research', '0010_aurora_250_baseline'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='indexvalue',
            name='uniq_index_value_normalized',
        ),
        migrations.AddConstraint(
            model_name='indexvalue',
            constraint=models.UniqueConstraint(
                fields=('index_type', 'normalized_title'),
                condition=models.Q(parent__isnull=True),
                name='uniq_index_value_root_normalized',
            ),
        ),
        migrations.AddConstraint(
            model_name='indexvalue',
            constraint=models.UniqueConstraint(
                fields=('index_type', 'parent', 'normalized_title'),
                condition=models.Q(parent__isnull=False),
                name='uniq_index_value_child_normalized',
            ),
        ),
        migrations.AddField(
            model_name='research',
            name='view_count',
            field=models.PositiveBigIntegerField(default=0, verbose_name='تعداد مشاهده عمومی'),
        ),
        migrations.CreateModel(
            name='ResearchBookmark',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('research', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookmarks', to='research.research', verbose_name='فیش')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='research_bookmarks', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={'verbose_name': 'فیش ذخیره‌شده', 'verbose_name_plural': 'فیش‌های ذخیره‌شده', 'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='researchbookmark',
            constraint=models.UniqueConstraint(fields=('user', 'research'), name='uniq_research_bookmark_user'),
        ),
        migrations.CreateModel(
            name='CustomCollection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=180, verbose_name='عنوان دسته‌بندی اختصاصی')),
                ('description', models.TextField(blank=True, verbose_name='توضیح')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('order', models.PositiveIntegerField(default=0)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_collections', to=settings.AUTH_USER_MODEL, verbose_name='مالک')),
            ],
            options={
                'verbose_name': 'فیش‌برداری اختصاصی',
                'verbose_name_plural': 'دسته‌بندی‌های اختصاصی',
                'ordering': ['order', 'title'],
            },
        ),
        migrations.AddConstraint(
            model_name='customcollection',
            constraint=models.UniqueConstraint(fields=('owner', 'title'), name='uniq_custom_collection_per_owner'),
        ),
        migrations.AlterField(
            model_name='research',
            name='title',
            field=models.CharField(blank=True, default='', max_length=160, verbose_name='عنوان فیش'),
        ),
        migrations.AlterField(
            model_name='topicanalysis',
            name='author_interpretation',
            field=models.TextField(blank=True, verbose_name='برداشت نویسنده از این موضوع'),
        ),
        migrations.AddField(
            model_name='research',
            name='personal_collections',
            field=models.ManyToManyField(blank=True, related_name='researches', to='research.customcollection', verbose_name='فیش‌برداری اختصاصی'),
        ),
        migrations.CreateModel(
            name='ResearchAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('file', models.FileField(upload_to='research/attachments/%Y/%m/', verbose_name='فایل')),
                ('kind', models.CharField(choices=[('image', 'تصویر'), ('audio', 'صوت'), ('document', 'سند'), ('other', 'سایر')], default='other', max_length=20, verbose_name='نوع')),
                ('title', models.CharField(blank=True, max_length=250, verbose_name='عنوان')),
                ('research', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='research.research', verbose_name='فیش')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='research_attachments', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'پیوست فیش', 'verbose_name_plural': 'پیوست‌های فیش', 'ordering': ['created_at']},
        ),
        migrations.RunPython(normalize_audiences, reverse_audiences),
        migrations.RunPython(normalize_occasion_dates, reverse_occasion_dates),
    ]
