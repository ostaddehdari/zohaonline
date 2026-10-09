from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_alter_user_options_alter_user_groups'),
    ]

    operations = [
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=180, verbose_name='نام گروه کاری')),
                ('description', models.TextField(blank=True, verbose_name='توضیح')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='owned_teams', to=settings.AUTH_USER_MODEL, verbose_name='مالک گروه')),
            ],
            options={
                'verbose_name': 'گروه کاری',
                'verbose_name_plural': 'گروه‌های کاری',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='TeamMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('manager', 'مدیر گروه'), ('member', 'عضو'), ('viewer', 'مشاهده‌گر')], default='member', max_length=20, verbose_name='نقش در گروه')),
                ('is_active', models.BooleanField(default=True, verbose_name='عضویت فعال')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='accounts.team')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='team_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'عضویت گروه کاری',
                'verbose_name_plural': 'عضویت‌های گروه کاری',
            },
        ),
        migrations.AddField(
            model_name='team',
            name='members',
            field=models.ManyToManyField(related_name='teams', through='accounts.TeamMembership', to=settings.AUTH_USER_MODEL, verbose_name='اعضا'),
        ),
        migrations.AddConstraint(
            model_name='team',
            constraint=models.UniqueConstraint(fields=('owner', 'name'), name='uniq_team_name_per_owner'),
        ),
        migrations.AddConstraint(
            model_name='teammembership',
            constraint=models.UniqueConstraint(fields=('team', 'user'), name='uniq_team_membership'),
        ),
    ]
