from django.conf import settings
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations, models
import django.db.models.deletion


def consolidate_research_lifecycle(apps, schema_editor):
    Research = apps.get_model('research', 'Research')
    for research in Research.objects.all().iterator():
        status = research.status
        access_level = research.access_level
        if research.publication_status == 'published' or research.is_public:
            status = 'published'
            access_level = 'public'
        elif research.validation_status == 'approved' and status not in {'published'}:
            status = 'approved'
        elif research.validation_status == 'needs_changes' and status not in {'published', 'approved', 'rejected'}:
            status = 'changes_requested'
        # Historical "team" was only a label; there was no membership relation.
        # Convert it to private rather than accidentally widening access.
        if access_level == 'team':
            access_level = 'private'
        Research.objects.filter(pk=research.pk).update(status=status, access_level=access_level)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0003_team_access_domain'),
        ('research', '0009_sermon_styles'),
    ]

    operations = [
        TrigramExtension(),
        migrations.AddField(
            model_name='research',
            name='team',
            field=models.ForeignKey(blank=True, help_text='برای سطح دسترسی گروه کاری الزامی است.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='researches', to='accounts.team', verbose_name='گروه کاری'),
        ),
        migrations.RunPython(consolidate_research_lifecycle, noop_reverse),
        migrations.RemoveField(model_name='research', name='validation_status'),
        migrations.RemoveField(model_name='research', name='publication_status'),
        migrations.RemoveField(model_name='research', name='is_public'),
        migrations.CreateModel(
            name='AIIndexingRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('raw_response', models.TextField(blank=True)),
                ('parsed_payload', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('review', 'در حال بررسی'), ('applied', 'اعمال‌شده'), ('discarded', 'کنار گذاشته‌شده')], db_index=True, default='review', max_length=20)),
                ('applied_at', models.DateTimeField(blank=True, null=True)),
                ('endpoint', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='indexing_runs', to='research.aiendpointstatus')),
                ('generation_log', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='indexing_runs', to='research.aigenerationlog')),
                ('research', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_indexing_runs', to='research.research')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_indexing_runs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'اجرای نمایه‌زنی هوش مصنوعی', 'verbose_name_plural': 'اجراهای نمایه‌زنی هوش مصنوعی', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='AIIndexSuggestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('kind', models.CharField(choices=[('topic_analysis', 'تحلیل موضوعی'), ('character', 'شخصیت'), ('occasion', 'مناسبت'), ('audience', 'مخاطب'), ('keyword', 'کلمه کلیدی')], max_length=30)),
                ('label', models.CharField(max_length=500)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('match_data', models.JSONField(blank=True, default=dict)),
                ('decision', models.CharField(choices=[('pending', 'در انتظار'), ('accepted', 'پذیرفته'), ('rejected', 'رد شده')], db_index=True, default='pending', max_length=20)),
                ('decided_at', models.DateTimeField(blank=True, null=True)),
                ('decided_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='decided_ai_index_suggestions', to=settings.AUTH_USER_MODEL)),
                ('run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='suggestions', to='research.aiindexingrun')),
            ],
            options={'verbose_name': 'پیشنهاد نمایه هوش مصنوعی', 'verbose_name_plural': 'پیشنهادهای نمایه هوش مصنوعی', 'ordering': ['created_at', 'id']},
        ),
        migrations.CreateModel(
            name='SermonArtifact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=250, verbose_name='عنوان منبر')),
                ('topic', models.TextField(blank=True, verbose_name='موضوع یا زاویه')),
                ('content', models.TextField(verbose_name='متن فعلی')),
                ('version', models.PositiveIntegerField(default=1)),
                ('status', models.CharField(choices=[('draft', 'پیش‌نویس'), ('final', 'نهایی'), ('archived', 'بایگانی')], db_index=True, default='draft', max_length=20)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sermon_artifacts', to=settings.AUTH_USER_MODEL)),
                ('endpoint', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sermon_artifacts', to='research.aiendpointstatus')),
                ('generation_log', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sermon_artifacts', to='research.aigenerationlog')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sermon_artifacts', to='research.promotionproject')),
                ('style', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sermon_artifacts', to='research.sermonstyle')),
            ],
            options={'verbose_name': 'منبر ذخیره‌شده', 'verbose_name_plural': 'منبرهای ذخیره‌شده', 'ordering': ['-updated_at']},
        ),
        migrations.CreateModel(
            name='SermonRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField()),
                ('content', models.TextField()),
                ('source', models.CharField(choices=[('ai', 'تولید هوش مصنوعی'), ('manual', 'ویرایش دستی')], default='manual', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('artifact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='research.sermonartifact')),
                ('edited_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sermon_revisions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'نسخه منبر', 'verbose_name_plural': 'نسخه‌های منبر', 'ordering': ['-version']},
        ),
        migrations.AddConstraint(
            model_name='sermonrevision',
            constraint=models.UniqueConstraint(fields=('artifact', 'version'), name='uniq_sermon_artifact_version'),
        ),
    ]
