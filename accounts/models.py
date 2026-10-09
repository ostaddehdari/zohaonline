from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class Role(models.Model):
    name = models.CharField('نام', max_length=80)
    slug = models.SlugField('شناسه', max_length=40, unique=True)
    description = models.TextField('توضیح', blank=True)

    class Meta:
        verbose_name = 'نقش'
        verbose_name_plural = 'نقش‌ها'
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    email = models.EmailField('ایمیل', unique=True)
    mobile = models.CharField('شماره همراه', max_length=20, blank=True, null=True, unique=True)
    roles = models.ManyToManyField(Role, blank=True, related_name='users', verbose_name='نقش‌ها')
    is_enabled = models.BooleanField('فعال', default=True)
    expertise = models.CharField('تخصص', max_length=255, blank=True)
    preaching_field = models.CharField('حوزه فعالیت تبلیغی', max_length=255, blank=True)
    avatar = models.ImageField('تصویر', upload_to='avatars/', blank=True, null=True)

    def has_role(self, slug):
        return self.is_superuser or self.roles.filter(slug=slug).exists()

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def save(self, *args, **kwargs):
        # is_enabled is the product-level source of truth. Keeping Django's
        # is_active synchronized prevents disabled accounts from authenticating
        # through any view that only relies on Django authentication.
        if not self.is_superuser:
            self.is_active = bool(self.is_enabled)
        super().save(*args, **kwargs)


class TeamQuerySet(models.QuerySet):
    def visible_to(self, user):
        if not getattr(user, 'is_authenticated', False):
            return self.none()
        if user.is_superuser or user.has_role('admin'):
            return self.filter(is_active=True)
        return self.filter(
            Q(owner=user) | Q(memberships__user=user, memberships__is_active=True),
            is_active=True,
        ).distinct()


class Team(models.Model):
    name = models.CharField('نام گروه کاری', max_length=180)
    description = models.TextField('توضیح', blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_teams',
        verbose_name='مالک گروه',
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='TeamMembership',
        related_name='teams',
        verbose_name='اعضا',
    )
    is_active = models.BooleanField('فعال', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TeamQuerySet.as_manager()

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='uniq_team_name_per_owner')
        ]
        verbose_name = 'گروه کاری'
        verbose_name_plural = 'گروه‌های کاری'

    def __str__(self):
        return self.name

    @property
    def active_member_count(self):
        return self.memberships.filter(is_active=True).count()

    def has_member(self, user):
        if not getattr(user, 'is_authenticated', False):
            return False
        return (
            user.is_superuser
            or user.has_role('admin')
            or self.owner_id == user.id
            or self.memberships.filter(user=user, is_active=True).exists()
        )


class TeamMembership(models.Model):
    ROLES = [
        ('manager', 'مدیر گروه'),
        ('member', 'عضو'),
        ('viewer', 'مشاهده‌گر'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='team_memberships')
    role = models.CharField('نقش در گروه', max_length=20, choices=ROLES, default='member')
    is_active = models.BooleanField('عضویت فعال', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['team', 'user'], name='uniq_team_membership')]
        verbose_name = 'عضویت گروه کاری'
        verbose_name_plural = 'عضویت‌های گروه کاری'

    def __str__(self):
        return f'{self.team} — {self.user}'
