import re
import uuid
from html import unescape

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


def normalize_fa(value):
    """Normalize Persian text for duplicate detection and tolerant search."""
    value = unescape(value or "")
    replacements = {
        "ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه",
        "ؤ": "و", "إ": "ا", "أ": "ا", "ٱ": "ا", "ئ": "ی",
        "‌": " ", "ـ": "", "۰": "0", "۱": "1", "۲": "2",
        "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7",
        "۸": "8", "۹": "9",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"[\u064b-\u065f\u0670]", "", value)
    value = re.sub(r"[^\w\s-]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip().casefold()


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class IndexType(TimeStamped):
    DATA_TYPES = [
        ("text", "متن آزاد"), ("single", "انتخاب تکی"),
        ("multi", "انتخاب چندگانه"), ("number", "عدد"), ("date", "تاریخ"),
    ]
    name = models.CharField("نام نمایه", max_length=150)
    slug = models.SlugField(unique=True, max_length=80)
    description = models.TextField("راهنما", blank=True)
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default="multi")
    is_required = models.BooleanField(default=False)
    allow_new_values = models.BooleanField(default=True)
    allow_multiple = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "نوع نمایه"
        verbose_name_plural = "انواع نمایه"

    def __str__(self):
        return self.name


class IndexValueQuerySet(models.QuerySet):
    def visible_to(self, user):
        base = Q(visibility="global", approval_status="approved")
        if getattr(user, "is_authenticated", False):
            base |= Q(owner=user)
            if user.is_superuser or user.has_role("admin"):
                base = Q()
        return self.filter(base, is_active=True, merged_into__isnull=True)


class IndexValue(TimeStamped):
    VISIBILITY = [("global", "عمومی"), ("private", "شخصی")]
    APPROVAL = [("pending", "در انتظار تأیید"), ("approved", "تأییدشده"), ("rejected", "ردشده")]

    index_type = models.ForeignKey(IndexType, on_delete=models.CASCADE, related_name="values")
    title = models.CharField("عنوان", max_length=500)
    normalized_title = models.CharField(max_length=500, editable=False)
    aliases = models.TextField("نام‌های جایگزین", blank=True, help_text="هر نام در یک خط")
    description = models.TextField(blank=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    visibility = models.CharField(max_length=15, choices=VISIBILITY, default="global")
    approval_status = models.CharField(max_length=15, choices=APPROVAL, default="approved")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="private_index_values")
    is_active = models.BooleanField(default=True)
    merged_into = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="merged_items")
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_index_values")

    objects = IndexValueQuerySet.as_manager()

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(fields=["index_type", "normalized_title"], condition=Q(parent__isnull=True), name="uniq_index_value_root_normalized"),
            models.UniqueConstraint(fields=["index_type", "parent", "normalized_title"], condition=Q(parent__isnull=False), name="uniq_index_value_child_normalized"),
        ]
        indexes = [
            models.Index(fields=["index_type", "is_active"]),
            models.Index(fields=["visibility", "approval_status"]),
            GinIndex(fields=["normalized_title"], name="indexvalue_title_trgm", opclasses=["gin_trgm_ops"]),
        ]
        verbose_name = "مقدار نمایه"
        verbose_name_plural = "مقادیر نمایه"

    def save(self, *args, **kwargs):
        self.normalized_title = normalize_fa(self.title)
        if self.visibility == "global" and self.approval_status == "pending" and not self.owner_id:
            self.approval_status = "approved"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_label

    @property
    def display_label(self):
        if getattr(self.index_type, "slug", "") == "occasion":
            meta = self.metadata or {}
            day = meta.get("jalali_day")
            month = meta.get("jalali_month")
            if day and month:
                date_label = f"{day} {month}"
                if normalize_fa(date_label) not in normalize_fa(self.title):
                    return f"{date_label} — {self.title}"
        return self.title

    @property
    def usage_count(self):
        return sum([
            self.research_indexes.count(),
            self.topic_researches.count(),
            self.predicate_researches.count(),
            self.processing_key_analyses.count(),
            self.content_kind_researches.count(),
            self.content_category_researches.count(),
            self.main_format_researches.count(),
            self.sub_format_researches.count(),
            self.source_type_researches.count(),
            self.character_researches.count(),
            self.secondary_character_researches.count(),
            self.occasion_researches.count(),
            self.full_content_topics.count(),
            self.full_content_predicates.count(),
            self.full_content_processing_keys.count(),
            self.full_content_authors.count(),
            self.full_content_characters.count(),
            self.full_content_occasions.count(),
            self.full_content_places.count(),
        ])

    @property
    def alias_list(self):
        return [x.strip() for x in self.aliases.splitlines() if x.strip()]


class SourceQuerySet(models.QuerySet):
    def visible_to(self, user):
        base = Q(visibility="global", approval_status="approved")
        if getattr(user, "is_authenticated", False):
            base |= Q(owner=user)
            if user.is_superuser or user.has_role("admin"):
                base = Q()
        return self.filter(base, is_active=True, merged_into__isnull=True)


class Source(TimeStamped):
    VISIBILITY = IndexValue.VISIBILITY
    APPROVAL = IndexValue.APPROVAL

    title = models.CharField("نام منبع", max_length=500)
    normalized_title = models.CharField(max_length=500, editable=False)
    author_name = models.CharField("پدیدآور یا شخص مرتبط", max_length=500, blank=True)
    aliases = models.TextField("نام‌های جایگزین", blank=True)
    description = models.TextField("توضیح", blank=True)
    visibility = models.CharField(max_length=15, choices=VISIBILITY, default="global")
    approval_status = models.CharField(max_length=15, choices=APPROVAL, default="approved")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="private_sources")
    is_active = models.BooleanField(default=True)
    merged_into = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="merged_sources")

    objects = SourceQuerySet.as_manager()

    class Meta:
        ordering = ["title"]
        constraints = [models.UniqueConstraint(fields=["normalized_title"], name="uniq_source_normalized")]
        indexes = [
            models.Index(fields=["visibility", "approval_status", "is_active"], name="research_so_visibil_afe828_idx"),
            GinIndex(fields=["normalized_title"], name="source_title_trgm", opclasses=["gin_trgm_ops"]),
        ]
        verbose_name = "منبع"
        verbose_name_plural = "منابع"

    def save(self, *args, **kwargs):
        self.normalized_title = normalize_fa(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title}{' — ' + self.author_name if self.author_name else ''}"


class CustomCollection(TimeStamped):
    """دسته‌بندی اختصاصی و شخصی هر فیش‌نگار؛ مستقل از فرهنگ نمایه‌های عمومی ضحی."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="custom_collections", verbose_name="مالک")
    title = models.CharField("عنوان دسته‌بندی اختصاصی", max_length=180)
    description = models.TextField("توضیح", blank=True)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children", verbose_name="دسته مادر")
    is_active = models.BooleanField("فعال", default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "title"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "title"], condition=Q(parent__isnull=True), name="uniq_custom_collection_root"),
            models.UniqueConstraint(fields=["owner", "parent", "title"], condition=Q(parent__isnull=False), name="uniq_custom_collection_child"),
        ]
        verbose_name = "فیش‌برداری اختصاصی"
        verbose_name_plural = "دسته‌بندی‌های اختصاصی"

    def __str__(self):
        return self.title


class ResearchQuerySet(models.QuerySet):
    def visible_to(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.filter(status="published", access_level="public")
        if user.is_superuser or user.has_role("admin"):
            return self.all()
        return self.filter(
            Q(researcher=user)
            | Q(review_tasks__reviewer=user)
            | Q(status="published", access_level="public")
            | Q(access_level="team", team__memberships__user=user, team__memberships__is_active=True)
            | Q(access_level="team", team__owner=user)
        ).distinct()


class Research(TimeStamped):
    STATUS = [
        ("draft", "پیش‌نویس"), ("submitted", "ارسال‌شده"),
        ("in_review", "در حال ارزیابی"), ("changes_requested", "نیازمند اصلاح"),
        ("approved", "تأییدشده"), ("rejected", "ردشده"), ("published", "منتشرشده"),
    ]
    ACCESS_LEVEL = [("private", "فقط خودم"), ("team", "گروه کاری"), ("public", "عمومی")]
    LIFECYCLE_TRANSITIONS = {
        "draft": {"submitted", "in_review"},
        "submitted": {"in_review", "draft"},
        "in_review": {"changes_requested", "approved", "rejected", "published"},
        "changes_requested": {"in_review", "draft", "rejected"},
        "approved": {"published", "changes_requested"},
        "rejected": {"draft", "in_review"},
        "published": {"approved", "changes_requested"},
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    researcher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="researches", verbose_name="فیش‌نگار")
    title = models.CharField("عنوان فیش", max_length=160, blank=True, default="")
    abstract = models.TextField("خلاصه یا نکته کلیدی", blank=True)
    body = models.TextField("متن اصلی", blank=True)
    search_keywords = models.TextField("کلمات کلیدی", blank=True)
    author_explanation = models.TextField("توضیح نویسنده", blank=True)
    seo_tags = models.JSONField("برچسب‌های SEO", default=list, blank=True)
    external_references = models.JSONField("ارجاعات هوشمند", default=list, blank=True)
    ai_segments = models.JSONField("بخش‌های تشخیص‌داده‌شده متن", default=list, blank=True)
    ai_enrichment_status = models.CharField("وضعیت غنی‌سازی هوشمند", max_length=30, blank=True, default="")
    ai_enriched_at = models.DateTimeField(null=True, blank=True)
    featured_image = models.ImageField("تصویر شاخص", upload_to="featured/%Y/%m/", blank=True, null=True)
    search_document_normalized = models.TextField("سند جست‌وجوی نرمال‌شده", blank=True, default="", editable=False)

    content_kind = models.ForeignKey(IndexValue, on_delete=models.PROTECT, null=True, blank=True, related_name="content_kind_researches", verbose_name="جنس محتوا")
    content_category = models.ForeignKey(IndexValue, on_delete=models.PROTECT, null=True, blank=True, related_name="content_category_researches", verbose_name="ریز جنس محتوا")
    main_format = models.ForeignKey(IndexValue, on_delete=models.PROTECT, null=True, blank=True, related_name="main_format_researches", verbose_name="قالب اصلی فیش")
    sub_format = models.ForeignKey(IndexValue, on_delete=models.PROTECT, null=True, blank=True, related_name="sub_format_researches", verbose_name="ریزقالب")

    source_type = models.ForeignKey(IndexValue, on_delete=models.PROTECT, null=True, blank=True, related_name="source_type_researches", verbose_name="نوع منبع")
    source = models.ForeignKey(Source, on_delete=models.PROTECT, null=True, blank=True, related_name="researches", verbose_name="منبع")
    source_volume = models.CharField("جلد", max_length=80, blank=True)
    source_page = models.CharField("صفحه", max_length=80, blank=True)
    source_narrator = models.CharField("راوی", max_length=250, blank=True)
    source_url = models.URLField("پیوند اینترنتی", max_length=1000, blank=True)
    source_note = models.TextField("توضیح آزاد منبع", blank=True)
    source_file = models.FileField("فایل منبع", upload_to="research/%Y/%m/", blank=True, null=True)

    characters = models.ManyToManyField(IndexValue, blank=True, related_name="character_researches", verbose_name="شخصیت‌های اصلی")
    secondary_characters = models.ManyToManyField(IndexValue, blank=True, related_name="secondary_character_researches", verbose_name="شخصیت‌های فرعی / ناقلان")
    occasions = models.ManyToManyField(IndexValue, blank=True, related_name="occasion_researches", verbose_name="مناسبت‌ها")
    personal_collections = models.ManyToManyField(CustomCollection, blank=True, related_name="researches", verbose_name="فیش‌برداری اختصاصی")
    audience_profiles = models.JSONField(default=list, blank=True, verbose_name="مخاطبان")

    access_level = models.CharField(max_length=15, choices=ACCESS_LEVEL, default="private", verbose_name="سطح دسترسی")
    team = models.ForeignKey(
        "accounts.Team", on_delete=models.PROTECT, null=True, blank=True,
        related_name="researches", verbose_name="گروه کاری",
        help_text="برای سطح دسترسی گروه کاری الزامی است.",
    )
    duplicate_override = models.BooleanField(default=False, verbose_name="ثبت با وجود هشدار تشابه")

    status = models.CharField(max_length=30, choices=STATUS, default="draft", db_index=True)
    current_round = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    view_count = models.PositiveBigIntegerField("تعداد مشاهده عمومی", default=0)
    is_featured = models.BooleanField("منتخب صفحه عمومی", default=False, db_index=True)
    featured_order = models.PositiveIntegerField("ترتیب نمایش منتخب", default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    objects = ResearchQuerySet.as_manager()

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["researcher", "status"]),
            models.Index(fields=["status", "-updated_at"]),
            GinIndex(fields=["search_document_normalized"], name="research_search_trgm", opclasses=["gin_trgm_ops"]),
        ]
        verbose_name = "فیش"
        verbose_name_plural = "فیش‌ها"

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return (self.title or "").strip() or "فیش بدون عنوان"

    @property
    def can_be_edited(self):
        return self.status in {"draft", "changes_requested", "rejected"}

    @property
    def is_published(self):
        return self.status == "published" and self.access_level == "public"

    @property
    def is_validated(self):
        return self.status in {"approved", "published"}

    def can_transition_to(self, target):
        return target == self.status or target in self.LIFECYCLE_TRANSITIONS.get(self.status, set())

    def transition_to(self, target, *, save=True):
        if target not in dict(self.STATUS):
            raise ValidationError("وضعیت مقصد نامعتبر است.")
        if not self.can_transition_to(target):
            raise ValidationError(f"تغییر وضعیت از {self.get_status_display()} به {dict(self.STATUS)[target]} مجاز نیست.")
        self.status = target
        now = timezone.now()
        if target in {"submitted", "in_review"} and not self.submitted_at:
            self.submitted_at = now
        if target in {"approved", "published"}:
            self.approved_at = self.approved_at or now
        if save:
            self.save(update_fields=["status", "submitted_at", "approved_at", "updated_at"])
        return self

    def clean(self):
        super().clean()
        if self.access_level == "team" and not self.team_id:
            raise ValidationError({"team": "برای دسترسی گروه کاری باید یک گروه انتخاب شود."})
        if self.access_level != "team" and self.team_id:
            self.team = None

    @property
    def keyword_list(self):
        return [x.strip() for x in re.split(r"[,،;؛\n]+", self.search_keywords or "") if x.strip()]

    @property
    def word_count(self):
        return len(re.findall(r"\w+", re.sub("<[^>]+>", " ", self.body or "")))

    @property
    def has_structured_index(self):
        if any([self.content_kind_id, self.content_category_id, self.main_format_id, self.sub_format_id, self.source_type_id, self.source_id]):
            return True
        if self.characters.exists() or self.secondary_characters.exists() or self.occasions.exists() or self.topic_analyses.exists() or self.indexes.exists() or self.personal_collections.exists():
            return True
        return bool(self.audience_profiles)

    @property
    def completion_score(self):
        checks = [
            bool(re.sub("<[^>]+>", "", self.body or "").strip()),
            self.has_structured_index,
            bool(self.title), bool(self.abstract), bool(self.source_id or self.source_note),
            bool(self.search_keywords), bool(self.author_explanation),
        ]
        return round(sum(checks) * 100 / len(checks))


class ResearchReaction(TimeStamped):
    VALUE = [("like", "پسند"), ("dislike", "ناپسند")]
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="research_reactions")
    value = models.CharField(max_length=10, choices=VALUE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["research", "user"], name="uniq_research_reaction_user")]
        indexes = [models.Index(fields=["research", "value"], name="research_re_researc_0e1fe2_idx")]


class ContentReport(TimeStamped):
    REASONS = [("source", "ایراد سندی یا منبع"), ("typo", "خطای تایپی"), ("category", "دسته‌بندی اشتباه"), ("other", "سایر")]
    STATUS = [("pending", "در انتظار بررسی"), ("resolved", "رسیدگی‌شده"), ("dismissed", "ردشده")]
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="content_reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_reports")
    reason = models.CharField(max_length=20, choices=REASONS)
    description = models.TextField(blank=True, max_length=1000)
    status = models.CharField(max_length=20, choices=STATUS, default="pending", db_index=True)

    class Meta:
        indexes = [models.Index(fields=["research", "reporter", "-created_at"], name="research_co_researc_4b0a97_idx")]


class EducationCourse(TimeStamped):
    COURSE_TYPES = [("fish", "آموزش فیش‌برداری روش‌مند"), ("sermon", "آموزش منبرسازی روش‌مند")]
    title = models.CharField(max_length=200)
    course_type = models.CharField(max_length=20, choices=COURSE_TYPES, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["course_type", "order", "title"]

    def __str__(self):
        return self.title


class EducationLesson(TimeStamped):
    course = models.ForeignKey(EducationCourse, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=220)
    body = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title


class SubscriptionPlan(TimeStamped):
    title = models.CharField(max_length=120)
    duration_days = models.PositiveIntegerField(default=30)
    price = models.PositiveBigIntegerField(default=0)
    is_active = models.BooleanField(default=False, help_text="تا فاز فروش عمومی غیرفعال بماند.")

    def __str__(self):
        return self.title


class UserSubscription(TimeStamped):
    STATUS = [("pending", "در انتظار"), ("active", "فعال"), ("expired", "منقضی"), ("cancelled", "لغوشده")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=STATUS, default="pending", db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=190, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "status", "ends_at"], name="research_us_user_id_c92c8b_idx")]


class ResearchBookmark(TimeStamped):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="research_bookmarks", verbose_name="کاربر")
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="bookmarks", verbose_name="فیش")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "research"], name="uniq_research_bookmark_user")]
        ordering = ["-created_at"]
        verbose_name = "فیش ذخیره‌شده"
        verbose_name_plural = "فیش‌های ذخیره‌شده"

    def __str__(self):
        return f"{self.user} — {self.research.display_title}"


class ResearchAttachment(TimeStamped):
    KINDS = [("image", "تصویر"), ("audio", "صوت"), ("document", "سند"), ("other", "سایر")]
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="attachments", verbose_name="فیش")
    file = models.FileField("فایل", upload_to="research/attachments/%Y/%m/")
    kind = models.CharField("نوع", max_length=20, choices=KINDS, default="other")
    title = models.CharField("عنوان", max_length=250, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="research_attachments")

    class Meta:
        ordering = ["created_at"]
        verbose_name = "پیوست فیش"
        verbose_name_plural = "پیوست‌های فیش"

    def __str__(self):
        return self.title or self.file.name.rsplit("/", 1)[-1]


class FullContent(TimeStamped):
    """محتوای کامل: سخنرانی، کتاب، مقاله، مصاحبه، بیانیه و درسنامه."""
    KINDS = [
        ("speech", "سخنرانی"),
        ("article", "مقاله"),
        ("book", "کتاب"),
        ("broadcast", "گفتگوی تلویزیونی / رادیویی"),
        ("statement", "بیانیه"),
        ("interview", "مصاحبه"),
        ("lesson", "درسنامه تبلیغی برای دانش‌آموزان یا دانشجویان"),
    ]
    STATUS = [("draft", "پیش‌نویس"), ("ready", "آماده استفاده"), ("archived", "بایگانی‌شده")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="full_contents", verbose_name="ثبت‌کننده")
    title = models.CharField("عنوان محتوا", max_length=300)
    body = models.TextField("متن / توضیح محتوای کامل", blank=True)
    # ZOHA-W2.3-FULLCONTENT-SEMANTIC:START
    ai_segments = models.JSONField("بخش‌های معنایی تشخیص‌داده‌شده", default=list, blank=True)
    external_references = models.JSONField("ارجاعات معنایی", default=list, blank=True)
    # ZOHA-W2.3-FULLCONTENT-SEMANTIC:END
    file = models.FileField("فایل محتوای کامل", upload_to="full-content/%Y/%m/", blank=True, null=True)
    content_kind = models.CharField("جنس محتوای کامل", max_length=30, choices=KINDS)
    topic = models.ForeignKey(IndexValue, on_delete=models.PROTECT, null=True, blank=True, related_name="full_content_topics", verbose_name="موضوع")
    predicate = models.ForeignKey(IndexValue, on_delete=models.PROTECT, null=True, blank=True, related_name="full_content_predicates", verbose_name="ریز موضوع")
    processing_keys = models.ManyToManyField(IndexValue, blank=True, related_name="full_content_processing_keys", verbose_name="کلید پردازش")
    author_owner = models.ForeignKey(IndexValue, on_delete=models.PROTECT, null=True, blank=True, related_name="full_content_authors", verbose_name="صاحب اثر")
    characters = models.ManyToManyField(IndexValue, blank=True, related_name="full_content_characters", verbose_name="شخصیت")
    occasions = models.ManyToManyField(IndexValue, blank=True, related_name="full_content_occasions", verbose_name="مناسبت")
    audience_profiles = models.JSONField(default=list, blank=True, verbose_name="مخاطب")
    duration_minutes = models.PositiveIntegerField("مدت زمان ارائه (دقیقه)", null=True, blank=True)
    word_count = models.PositiveIntegerField("تعداد واژگان", default=0, editable=False)
    presentation_date = models.DateField("تاریخ ارائه محتوا", null=True, blank=True)
    presentation_place = models.ForeignKey(IndexValue, on_delete=models.PROTECT, null=True, blank=True, related_name="full_content_places", verbose_name="مکان ارائه / انتشار")
    status = models.CharField(max_length=20, choices=STATUS, default="draft", db_index=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["owner", "status"], name="research_fu_owner_i_1791d5_idx"), models.Index(fields=["content_kind", "-updated_at"], name="research_fu_content_c4424b_idx")]
        verbose_name = "محتوای کامل"
        verbose_name_plural = "محتواهای کامل"

    def save(self, *args, **kwargs):
        plain = re.sub(r"<[^>]+>", " ", self.body or "")
        self.word_count = len([x for x in re.split(r"\s+", plain.strip()) if x])
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class TopicAnalysis(TimeStamped):
    REVIEW_STATUS = [("unchecked", "بررسی‌نشده"), ("approved", "تأییدشده"), ("needs_changes", "نیازمند اصلاح")]

    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="topic_analyses")
    topic = models.ForeignKey(IndexValue, on_delete=models.PROTECT, related_name="topic_researches", verbose_name="موضوع")
    processing_keys = models.ManyToManyField(IndexValue, related_name="processing_key_analyses", verbose_name="کلیدهای پردازش")
    predicate = models.ForeignKey(IndexValue, on_delete=models.PROTECT, related_name="predicate_researches", null=True, blank=True, verbose_name="ریز موضوع")
    predicate_text = models.CharField("ریز موضوع پیشنهادی", max_length=500, blank=True)
    author_interpretation = models.TextField("برداشت نویسنده از این موضوع", blank=True)
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS, default="unchecked")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [models.UniqueConstraint(fields=["research", "topic"], name="uniq_topic_per_research")]
        verbose_name = "تحلیل موضوعی"
        verbose_name_plural = "تحلیل‌های موضوعی"

    def __str__(self):
        return f"{self.research.title} — {self.topic.title}"


class ResearchIndex(TimeStamped):
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="indexes")
    index_type = models.ForeignKey(IndexType, on_delete=models.PROTECT, related_name="research_indexes")
    index_value = models.ForeignKey(IndexValue, on_delete=models.PROTECT, related_name="research_indexes", null=True, blank=True)
    text_value = models.TextField("مقدار متنی", blank=True)
    source_excerpt = models.TextField("شاهد از متن", blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="added_research_indexes")

    class Meta:
        ordering = ["index_type__order", "order", "created_at"]
        indexes = [models.Index(fields=["research", "index_type"])]

    def clean(self):
        if not self.index_value and not self.text_value.strip():
            raise ValidationError("مقدار نمایه نمی‌تواند خالی باشد.")
        if self.index_value and self.index_value.index_type_id != self.index_type_id:
            raise ValidationError("مقدار متعلق به این نوع نمایه نیست.")

    @property
    def display_value(self):
        return self.index_value.title if self.index_value else self.text_value

    def __str__(self):
        return f"{self.index_type}: {self.display_value}"


class OptionAuditLog(models.Model):
    ACTIONS = [
        ("created", "ایجاد"), ("edited", "ویرایش"), ("approved", "تأیید"), ("rejected", "رد"),
        ("renamed", "تغییر نام"), ("deactivated", "غیرفعال‌سازی"),
        ("activated", "فعال‌سازی"), ("merged", "ادغام"),
    ]
    option = models.ForeignKey(IndexValue, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    source = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTIONS)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "سابقه تغییر گزینه"
        verbose_name_plural = "سوابق تغییر گزینه‌ها"


class ResearchVersion(models.Model):
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    snapshot = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        constraints = [models.UniqueConstraint(fields=["research", "version"], name="uniq_research_version")]


class ReviewerAssignment(TimeStamped):
    researcher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviewer_assignments_as_researcher")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviewer_assignments")
    scope = models.ForeignKey(IndexType, on_delete=models.CASCADE, null=True, blank=True, related_name="reviewer_assignments")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["researcher", "reviewer", "scope"], name="uniq_reviewer_assignment")]

    def __str__(self):
        return f"{self.researcher} ← {self.reviewer}"


class ReviewTask(TimeStamped):
    STATUS = [("pending", "منتظر"), ("in_review", "در حال بررسی"), ("changes_requested", "اصلاح"), ("approved", "تأیید"), ("rejected", "رد")]
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="review_tasks")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="review_tasks")
    scope = models.ForeignKey(IndexType, on_delete=models.PROTECT, null=True, blank=True, related_name="review_tasks")
    round = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=30, choices=STATUS, default="pending", db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["research", "reviewer", "scope", "round"], name="uniq_review_task_round")]


class ReviewComment(TimeStamped):
    SEVERITY = [("note", "نکته"), ("minor", "جزئی"), ("major", "مهم"), ("critical", "بحرانی")]
    RESOLUTION = [("open", "باز"), ("resolved", "رفع‌شده"), ("dismissed", "رد توضیح")]
    task = models.ForeignKey(ReviewTask, on_delete=models.CASCADE, related_name="comments")
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="review_comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="review_comments")
    index_type = models.ForeignKey(IndexType, on_delete=models.SET_NULL, null=True, blank=True)
    research_index = models.ForeignKey(ResearchIndex, on_delete=models.SET_NULL, null=True, blank=True)
    body = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY, default="major")
    resolution = models.CharField(max_length=20, choices=RESOLUTION, default="open")
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_review_comments")
    resolved_at = models.DateTimeField(null=True, blank=True)


class WorkflowEvent(models.Model):
    EVENT = [
        ("created", "ایجاد"), ("submitted", "ارسال"), ("assigned", "تخصیص"),
        ("commented", "ثبت خطا"), ("changes_requested", "برگشت اصلاح"),
        ("resubmitted", "ارسال مجدد"), ("approved", "تأیید"),
        ("rejected", "رد"), ("published", "انتشار"), ("updated", "ویرایش"),
    ]
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=30, choices=EVENT)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="zoha_notifications")
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    event = models.ForeignKey(WorkflowEvent, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read_at", "-created_at"])]

    @property
    def is_read(self):
        return bool(self.read_at)

    def mark_read(self):
        if not self.read_at:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])


class SearchLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    query = models.CharField(max_length=500, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    result_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class SermonStyle(TimeStamped):
    """الگوی قابل مدیریت برای ساخت منبر انسانی و هوش مصنوعی."""

    name = models.CharField("نام سبک منبر", max_length=180, unique=True)
    slug = models.SlugField(max_length=180, unique=True, allow_unicode=True)
    description = models.TextField("معرفی سبک", blank=True)
    system_prompt = models.TextField(
        "دستور تخصصی برای هوش مصنوعی",
        help_text="ویژگی‌های خطابی، محدودیت‌ها و روش نگارش این سبک را دقیق بنویسید.",
    )
    outline_template = models.TextField(
        "ساختار پیشنهادی منبر",
        blank=True,
        help_text="برای نمونه: آغاز عاطفی، طرح مسئله، سه محور، روایت، جمع‌بندی و اقدام عملی.",
    )
    tone = models.CharField("لحن", max_length=180, blank=True)
    language_level = models.CharField("سطح زبان", max_length=180, blank=True)
    duration_minutes = models.PositiveSmallIntegerField("مدت پیشنهادی به دقیقه", default=20)
    audience_guidance = models.TextField("راهنمای تطبیق با مخاطب", blank=True)
    is_active = models.BooleanField("فعال", default=True)
    is_default = models.BooleanField("سبک پیش‌فرض", default=False)
    order = models.PositiveIntegerField("ترتیب نمایش", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "سبک منبر"
        verbose_name_plural = "سبک‌های منبر"

    def save(self, *args, **kwargs):
        if self.is_default:
            SermonStyle.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PromotionProject(TimeStamped):
    STATUS = [
        ("draft", "در حال تدوین"),
        ("active", "فعال"),
        ("completed", "تکمیل‌شده"),
        ("archived", "بایگانی"),
    ]

    title = models.CharField("عنوان پروژه تبلیغی", max_length=180)
    description = models.TextField("توضیحات", blank=True)
    objective = models.TextField("هدف پروژه", blank=True)
    target_audience = models.CharField("خلاصه مخاطب هدف", max_length=500, blank=True)
    audience_profiles = models.JSONField(default=list, blank=True, verbose_name="مخاطب‌شناسی ساختاریافته")
    sermon_style = models.ForeignKey(
        SermonStyle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
        verbose_name="سبک منبر",
        help_text="هوش مصنوعی منبر را بر اساس این سبک، لحن و ساختار تولید می‌کند.",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="promotion_projects",
        verbose_name="مالک پروژه",
    )
    status = models.CharField(max_length=20, choices=STATUS, default="draft")
    is_active = models.BooleanField(default=True)
    indexes = models.ManyToManyField(
        IndexValue,
        blank=True,
        related_name="promotion_projects",
        verbose_name="نمایه‌های پروژه",
    )
    researches = models.ManyToManyField(
        Research,
        through="ProjectResearch",
        related_name="promotion_projects",
        verbose_name="فیش‌های پروژه",
    )

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "پروژه تبلیغی"
        verbose_name_plural = "پروژه‌های تبلیغی"

    def __str__(self):
        return self.title

    @property
    def research_count(self):
        return self.project_researches.count()


class ProjectResearch(models.Model):
    project = models.ForeignKey(
        PromotionProject,
        on_delete=models.CASCADE,
        related_name="project_researches",
    )
    research = models.ForeignKey(
        Research,
        on_delete=models.CASCADE,
        related_name="project_links",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_project_researches",
    )
    note = models.CharField("یادداشت", max_length=500, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "research"],
                name="uniq_research_per_promotion_project",
            )
        ]
        verbose_name = "فیش پروژه"
        verbose_name_plural = "فیش‌های پروژه"

    def __str__(self):
        return f"{self.project} — {self.research}"


class AIEndpointStatus(models.Model):
    STATUS = [
        ("active", "فعال"),
        ("inactive", "غیرفعال"),
        ("skipped", "نیازمند احراز هویت یا پیش‌نیاز"),
    ]

    provider_name = models.CharField(max_length=180)
    provider_path = models.CharField(max_length=500)
    model_name = models.CharField(max_length=250)
    status = models.CharField(max_length=20, choices=STATUS, default="inactive", db_index=True)
    needs_auth = models.BooleanField(default=False)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    response_excerpt = models.TextField(blank=True)
    last_error = models.TextField(blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["provider_name", "model_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider_path", "model_name"],
                name="uniq_ai_provider_model",
            )
        ]
        indexes = [models.Index(fields=["status", "last_checked_at"])]
        verbose_name = "وضعیت ارائه‌دهنده هوش مصنوعی"
        verbose_name_plural = "وضعیت ارائه‌دهندگان هوش مصنوعی"

    def __str__(self):
        return f"{self.provider_name} / {self.model_name}"


class AIProbeRun(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    total = models.PositiveIntegerField(default=0)
    active = models.PositiveIntegerField(default=0)
    inactive = models.PositiveIntegerField(default=0)
    skipped = models.PositiveIntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "اجرای پایش هوش مصنوعی"
        verbose_name_plural = "اجراهای پایش هوش مصنوعی"


class AIGenerationLog(models.Model):
    TASK_TYPES = [("indexing", "نمایه‌زنی"), ("sermon", "منبرسازی"), ("enrichment", "غنی‌سازی متن"), ("seo", "پیشنهاد SEO"), ("image", "تصویر شاخص")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_generation_logs",
    )
    endpoint = models.ForeignKey(
        AIEndpointStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_logs",
    )
    research = models.ForeignKey(
        Research,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_generation_logs",
    )
    project = models.ForeignKey(
        PromotionProject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_generation_logs",
    )
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    prompt = models.TextField()
    response = models.TextField(blank=True)
    succeeded = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "گزارش تولید هوش مصنوعی"
        verbose_name_plural = "گزارش‌های تولید هوش مصنوعی"


class AIIndexingRun(TimeStamped):
    STATUS = [("review", "در حال بررسی"), ("applied", "اعمال‌شده"), ("discarded", "کنار گذاشته‌شده")]

    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="ai_indexing_runs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="ai_indexing_runs")
    endpoint = models.ForeignKey(AIEndpointStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name="indexing_runs")
    generation_log = models.ForeignKey(AIGenerationLog, on_delete=models.SET_NULL, null=True, blank=True, related_name="indexing_runs")
    raw_response = models.TextField(blank=True)
    parsed_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="review", db_index=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "اجرای نمایه‌زنی هوش مصنوعی"
        verbose_name_plural = "اجراهای نمایه‌زنی هوش مصنوعی"


class AIIndexSuggestion(TimeStamped):
    KINDS = [
        ("topic_analysis", "تحلیل موضوعی"),
        ("character", "شخصیت"),
        ("occasion", "مناسبت"),
        ("audience", "مخاطب"),
        ("keyword", "کلمه کلیدی"),
    ]
    DECISIONS = [("pending", "در انتظار"), ("accepted", "پذیرفته"), ("rejected", "رد شده")]

    run = models.ForeignKey(AIIndexingRun, on_delete=models.CASCADE, related_name="suggestions")
    kind = models.CharField(max_length=30, choices=KINDS)
    label = models.CharField(max_length=500)
    payload = models.JSONField(default=dict, blank=True)
    match_data = models.JSONField(default=dict, blank=True)
    decision = models.CharField(max_length=20, choices=DECISIONS, default="pending", db_index=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="decided_ai_index_suggestions")
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "پیشنهاد نمایه هوش مصنوعی"
        verbose_name_plural = "پیشنهادهای نمایه هوش مصنوعی"


class SermonArtifact(TimeStamped):
    STATUS = [("draft", "پیش‌نویس"), ("final", "نهایی"), ("archived", "بایگانی")]

    project = models.ForeignKey(PromotionProject, on_delete=models.PROTECT, related_name="sermon_artifacts")
    style = models.ForeignKey(SermonStyle, on_delete=models.PROTECT, related_name="sermon_artifacts")
    endpoint = models.ForeignKey(AIEndpointStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name="sermon_artifacts")
    generation_log = models.ForeignKey(AIGenerationLog, on_delete=models.SET_NULL, null=True, blank=True, related_name="sermon_artifacts")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sermon_artifacts")
    title = models.CharField("عنوان منبر", max_length=250)
    topic = models.TextField("موضوع یا زاویه", blank=True)
    content = models.TextField("متن فعلی")
    # ZOHA-W2.3-SERMON-SEMANTIC:START
    ai_segments = models.JSONField("بخش‌های معنایی تشخیص‌داده‌شده", default=list, blank=True)
    external_references = models.JSONField("ارجاعات معنایی", default=list, blank=True)
    # ZOHA-W2.3-SERMON-SEMANTIC:END
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS, default="draft", db_index=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "منبر ذخیره‌شده"
        verbose_name_plural = "منبرهای ذخیره‌شده"

    def __str__(self):
        return self.title


class SermonRevision(models.Model):
    SOURCES = [("ai", "تولید هوش مصنوعی"), ("manual", "ویرایش دستی")]

    artifact = models.ForeignKey(SermonArtifact, on_delete=models.CASCADE, related_name="revisions")
    version = models.PositiveIntegerField()
    content = models.TextField()
    source = models.CharField(max_length=20, choices=SOURCES, default="manual")
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sermon_revisions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        constraints = [models.UniqueConstraint(fields=["artifact", "version"], name="uniq_sermon_artifact_version")]
        verbose_name = "نسخه منبر"
        verbose_name_plural = "نسخه‌های منبر"
