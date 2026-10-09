from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, Team, TeamMembership
from research.models import (
    IndexType,
    IndexValue,
    Notification,
    ProjectResearch,
    PromotionProject,
    Research,
    ResearchIndex,
    ReviewerAssignment,
    ReviewComment,
    ReviewTask,
    SermonStyle,
    Source,
    TopicAnalysis,
    WorkflowEvent,
    normalize_fa,
)

DEMO_PASSWORD = "Zoha@123456"
DEMO_MARKER = "ZOHA-DEMO-231"

RESEARCHERS = [
    ("demo_researcher_1", "علی", "رضایی", "پژوهش محتوای خانواده"),
    ("demo_researcher_2", "زهرا", "موسوی", "پژوهش جوان و هویت"),
    ("demo_researcher_3", "محمد", "حسینی", "پژوهش رسانه و اخلاق"),
]
REVIEWERS = [
    ("demo_reviewer_1", "مریم", "کاظمی", "ارزیابی محتوای دینی"),
    ("demo_reviewer_2", "حسن", "احمدی", "ارزیابی تبلیغ و مخاطب"),
]

THEMES = [
    {
        "title": "خانواده آرام؛ خانه گفت‌وگو",
        "objective": "تولید یک بسته تبلیغی کاربردی برای کاهش تعارض، تقویت گفت‌وگو و افزایش همدلی در خانواده.",
        "description": "این پروژه فیش‌های پژوهشی مرتبط با ارتباط همدلانه، حل تعارض، تربیت فرزند و آرامش خانوادگی را گردآوری می‌کند.",
        "audiences": [
            {
                "is_primary": True,
                "general": False,
                "genders": ["زن", "مرد"],
                "ages": ["جوان", "میانسال"],
                "jobs": ["معلم", "مبلغ"],
                "country": "ایران",
                "city": "",
                "literacy": "متوسط",
                "channels": ["جلسه خانوادگی", "مسجد", "شبکه اجتماعی"],
                "needs": "راهکارهای ساده برای گفت‌وگوی بدون سرزنش و مدیریت اختلاف‌های روزمره.",
                "notes": "لحن آرام، مثال‌های خانوادگی و پرهیز از قضاوت یک‌طرفه.",
            },
            {
                "is_primary": False,
                "general": False,
                "genders": ["زن", "مرد"],
                "ages": ["نوجوان"],
                "jobs": ["دانش‌آموز"],
                "country": "ایران",
                "city": "",
                "literacy": "مقدماتی",
                "channels": ["مدرسه", "شبکه اجتماعی"],
                "needs": "یادگیری بیان احساس و درخواست محترمانه از والدین.",
                "notes": "کوتاه، داستانی و متناسب با تجربه نوجوان.",
            },
        ],
        "subject": "خانواده",
        "predicate": "آرامش خانوادگی",
        "processing": ["راهکار", "آثار و محاسن"],
        "titles": [
            "گفت‌وگوی همدلانه؛ نخستین گام آرامش در خانه",
            "شنیدن فعال چگونه تعارض خانوادگی را کاهش می‌دهد؟",
            "مرز میان نصیحت و همراهی در تربیت فرزند",
            "نقش عذرخواهی والدین در اعتماد فرزندان",
            "مدیریت خشم پیش از گفت‌وگوی خانوادگی",
            "عدالت عاطفی میان فرزندان و پیامدهای آن",
            "آداب گفت‌وگو با نوجوان در دوره استقلال‌خواهی",
            "قدردانی روزانه و تقویت پیوند همسران",
            "حل اختلاف بدون تحقیر و برچسب‌زنی",
            "خانه امن؛ مسئولیت مشترک اعضای خانواده",
        ],
    },
    {
        "title": "جوان مؤمن؛ امید و هویت",
        "objective": "طراحی محتوای تبلیغی امیدآفرین برای تقویت هویت دینی، خودباوری و مسئولیت اجتماعی جوانان.",
        "description": "این پروژه میان پرسش‌های هویتی جوان، امید اجتماعی، انتخاب آگاهانه و معنویت روزمره پیوند ایجاد می‌کند.",
        "audiences": [
            {
                "is_primary": True,
                "general": False,
                "genders": ["زن", "مرد"],
                "ages": ["جوان"],
                "jobs": ["دانشجو", "طلبه"],
                "country": "ایران",
                "city": "",
                "literacy": "متوسط",
                "channels": ["دانشگاه", "کارگاه", "شبکه اجتماعی"],
                "needs": "پاسخ روشن به مسئله هویت، آینده، اثرگذاری و نسبت ایمان با زندگی واقعی.",
                "notes": "گفت‌وگومحور، مستدل، بدون شعار و همراه با نمونه‌های واقعی.",
            },
            {
                "is_primary": False,
                "general": False,
                "genders": ["زن", "مرد"],
                "ages": ["نوجوان"],
                "jobs": ["دانش‌آموز"],
                "country": "ایران",
                "city": "",
                "literacy": "مقدماتی",
                "channels": ["مدرسه", "هیئت"],
                "needs": "شناخت توانمندی‌ها و تجربه پیوند میان ایمان و امید.",
                "notes": "از زبان ساده، تمرین کوتاه و داستان استفاده شود.",
            },
        ],
        "subject": "جوان",
        "predicate": "هویت دینی",
        "processing": ["اهمیت", "راهکار"],
        "titles": [
            "امید مؤمنانه؛ تفاوت انتظار فعال با خوش‌بینی ساده",
            "هویت جوان در میان انتخاب‌های متعدد رسانه‌ای",
            "خودشناسی و کشف استعداد به‌عنوان مسئولیت دینی",
            "چگونه شکست را به تجربه رشد تبدیل کنیم؟",
            "دوستی‌های سازنده و نقش آن در آینده جوان",
            "معنویت روزمره؛ از عبادت تا مسئولیت اجتماعی",
            "پرسشگری جوان و آداب گفت‌وگوی دینی",
            "تصمیم‌گیری اخلاقی در فشار جمع همسالان",
            "کار داوطلبانه و تقویت احساس اثرگذاری",
            "آینده‌سازی با قدم‌های کوچک و پیوسته",
        ],
    },
    {
        "title": "رسانه مسئول؛ روایت اخلاقی",
        "objective": "تدوین بسته‌ای برای سواد رسانه‌ای، راستی‌آزمایی، روایت منصفانه و مسئولیت اخلاقی کاربران و فعالان رسانه.",
        "description": "فیش‌های این پروژه به تشخیص خبر درست، اخلاق بازنشر، مدیریت هیجان و تولید روایت مسئولانه می‌پردازند.",
        "audiences": [
            {
                "is_primary": True,
                "general": False,
                "genders": ["زن", "مرد"],
                "ages": ["جوان", "میانسال"],
                "jobs": ["مبلغ", "معلم", "دانشجو"],
                "country": "ایران",
                "city": "",
                "literacy": "پیشرفته",
                "channels": ["شبکه اجتماعی", "کارگاه", "رسانه عمومی"],
                "needs": "معیار عملی برای راستی‌آزمایی و تولید محتوای دقیق، منصفانه و اثرگذار.",
                "notes": "نمونه‌محور، به‌روز و همراه با چک‌لیست اجرایی.",
            },
            {
                "is_primary": False,
                "general": True,
                "genders": [],
                "ages": [],
                "jobs": [],
                "country": "ایران",
                "city": "",
                "literacy": "متوسط",
                "channels": ["شبکه اجتماعی"],
                "needs": "تشخیص محتوای مشکوک پیش از بازنشر.",
                "notes": "پیام کوتاه، تصویری و قابل استفاده برای عموم.",
            },
        ],
        "subject": "رسانه",
        "predicate": "مسئولیت اخلاقی",
        "processing": ["وظایف", "آفات و آسیب"],
        "titles": [
            "توقف پیش از بازنشر؛ یک مهارت اخلاقی رسانه‌ای",
            "راستی‌آزمایی خبر با سه پرسش ساده",
            "مرز نقد منصفانه و تخریب شخصیت در فضای مجازی",
            "هیجان چگونه قضاوت رسانه‌ای ما را منحرف می‌کند؟",
            "حفظ آبروی افراد در روایت رویدادها",
            "عنوان جذاب بدون فریب؛ اخلاق تیترنویسی",
            "تصویر ناقص چگونه واقعیت را تغییر می‌دهد؟",
            "مسئولیت تولیدکننده محتوا در اصلاح خطا",
            "مدیریت شایعه در گروه‌های خانوادگی و محلی",
            "روایت امیدآفرین بدون پنهان‌کردن مسئله",
        ],
    },
]


class Command(BaseCommand):
    help = "ایجاد داده نمایشی مرتبط: ۳۰ فیش، ۳ پروژه، ۳ پژوهشگر، ۲ ارزیاب و گفت‌وگوهای ارزیابی"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="بازنشانی رمز همه حساب‌های نمایشی به رمز اعلام‌شده",
        )

    def _type(self, slug: str) -> IndexType:
        return IndexType.objects.get(slug=slug)

    def _value(self, slug: str, title: str, *, parent: IndexValue | None = None) -> IndexValue:
        index_type = self._type(slug)
        value, _ = IndexValue.objects.update_or_create(
            index_type=index_type,
            normalized_title=normalize_fa(title),
            defaults={
                "title": title,
                "parent": parent,
                "visibility": "global",
                "approval_status": "approved",
                "owner": None,
                "is_active": True,
                "metadata": {"seed_marker": DEMO_MARKER},
            },
        )
        return value

    def _user(self, username, first_name, last_name, expertise, role, reset_passwords):
        User = get_user_model()
        user, created = User.objects.update_or_create(
            username=username,
            defaults={
                "email": f"{username}@demo.zoha.local",
                "first_name": first_name,
                "last_name": last_name,
                "expertise": expertise,
                "preaching_field": "تبلیغ دینی و تولید محتوای پژوهش‌محور",
                "is_active": True,
                "is_enabled": True,
            },
        )
        if created or reset_passwords or not user.has_usable_password():
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=["password"])
        user.roles.add(role)
        return user

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_zoha", verbosity=0)
        researcher_role = Role.objects.get(slug="researcher")
        reviewer_role = Role.objects.get(slug="reviewer")

        researchers = [
            self._user(*row, researcher_role, options["reset_passwords"])
            for row in RESEARCHERS
        ]
        reviewers = [
            self._user(*row, reviewer_role, options["reset_passwords"])
            for row in REVIEWERS
        ]
        demo_team, _ = Team.objects.update_or_create(
            owner=researchers[0],
            name="گروه نمونه پژوهش و ارزیابی ضحی",
            defaults={"description": "گروه کاری نمونه برای آزمون دسترسی تیمی نسخه ۲.۶", "is_active": True},
        )
        for member in researchers + reviewers:
            TeamMembership.objects.update_or_create(
                team=demo_team, user=member,
                defaults={"role": "manager" if member.pk == demo_team.owner_id else "member", "is_active": True},
            )

        content_kind = self._value("content-kind", "اطلاعات و آمار علمی")
        content_category = self._value("content-category", "اطلاعات و آمار علمی")
        main_format = self._value("main-format", "متن")
        sub_format = self._value("content-subformat", "مقاله", parent=main_format)
        source_type = self._value("source-type", "کتاب")
        character = self._value("main-character", "پیامبر اکرم")
        occasion = self._value("occasion", "ماه مبارک رمضان")
        tags_type = self._type("tags")
        category_type = self._type("category")
        takeaway_type = self._type("takeaway")
        subject_type = self._type("subject")

        source, _ = Source.objects.update_or_create(
            normalized_title=normalize_fa("مجموعه مطالعات کاربردی تبلیغ دینی ضحی"),
            defaults={
                "title": "مجموعه مطالعات کاربردی تبلیغ دینی ضحی",
                "author_name": "گروه پژوهش ضحی آنلاین",
                "description": "منبع نمونه داخلی برای نمایش گردش کامل پژوهش، نمایه‌زنی و ارزیابی.",
                "visibility": "global",
                "approval_status": "approved",
                "is_active": True,
            },
        )

        all_researches = []
        projects = []
        style_slugs = ["problem-based", "narrative", "short-media"]
        now = timezone.now()
        status_cycle = ["approved", "published", "in_review", "changes_requested", "submitted"]

        for theme_index, theme in enumerate(THEMES):
            owner = researchers[theme_index]
            sermon_style = SermonStyle.objects.filter(slug=style_slugs[theme_index], is_active=True).first()
            project, _ = PromotionProject.objects.update_or_create(
                title=theme["title"],
                defaults={
                    "description": theme["description"],
                    "objective": theme["objective"],
                    "target_audience": "؛ ".join(
                        [
                            "مخاطب اصلی: " + ", ".join(theme["audiences"][0]["ages"] + theme["audiences"][0]["jobs"]),
                            "مخاطب تکمیلی: " + ("عموم مردم" if theme["audiences"][1]["general"] else ", ".join(theme["audiences"][1]["ages"] + theme["audiences"][1]["jobs"])),
                        ]
                    ),
                    "audience_profiles": theme["audiences"],
                    "sermon_style": sermon_style,
                    "owner": owner,
                    "status": "active",
                    "is_active": True,
                },
            )
            projects.append(project)

            topic = self._value("subject", theme["subject"])
            secondary_topic = self._value("subject", f"{theme['subject']} و تربیت اجتماعی")
            predicate = self._value("predicate", theme["predicate"])
            secondary_predicate = self._value("predicate", "رشد اخلاقی")
            processing_values = [self._value("processing-key", title) for title in theme["processing"]]
            project.indexes.set([topic, predicate, *processing_values])

            for item_index, title in enumerate(theme["titles"]):
                global_index = theme_index * 10 + item_index
                researcher = researchers[global_index % len(researchers)]
                reviewer = reviewers[global_index % len(reviewers)]
                status = status_cycle[global_index % len(status_cycle)]
                keyword_list = [theme["subject"], theme["predicate"], theme["processing"][0], "تبلیغ دینی", "کاربردی"]
                abstract = (
                    f"این فیش، موضوع «{title}» را در چارچوب پروژه «{theme['title']}» بررسی می‌کند و "
                    f"برای مخاطبان پروژه، نکته‌های قابل استفاده در سخنرانی، کارگاه و محتوای رسانه‌ای ارائه می‌دهد."
                )
                body = (
                    f"<h2>{title}</h2>"
                    f"<p>مسئله اصلی این فیش، پیوند میان <strong>{theme['subject']}</strong> و "
                    f"<strong>{theme['predicate']}</strong> است. در نگاه تبلیغی، پیام زمانی اثرگذار می‌شود که "
                    "با تجربه واقعی مخاطب، نیازهای او و زبان قابل فهم برای او مرتبط باشد.</p>"
                    f"<p>در تحلیل نخست، کلید «{theme['processing'][0]}» به ما کمک می‌کند ابعاد عملی موضوع را "
                    "از توصیه کلی جدا کنیم. مبلغ یا پژوهشگر باید ابتدا موقعیت مخاطب را بشناسد، سپس یک پیام روشن، "
                    "یک نمونه ملموس و یک اقدام کوچک و قابل انجام پیشنهاد دهد.</p>"
                    f"<p>در تحلیل دوم، کلید «{theme['processing'][1]}» نشان می‌دهد که استمرار این رفتار چه اثرهایی "
                    "بر فرد و جامعه دارد. جمع‌بندی فیش آن است که تغییر پایدار با گفت‌وگوی محترمانه، تمرین تدریجی "
                    "و بازخورد صادقانه شکل می‌گیرد.</p>"
                    "<blockquote>پیام خوب، هم دقیق است، هم متناسب با مخاطب و هم راهی برای عمل نشان می‌دهد.</blockquote>"
                )

                research = Research.objects.filter(title=title).first()
                if research is None:
                    research = Research(title=title, researcher=researcher, body=body)
                research.researcher = researcher
                research.abstract = abstract
                research.body = body
                research.search_keywords = "، ".join(keyword_list)
                research.author_explanation = f"داده نمایشی مرتبط با {DEMO_MARKER}؛ مناسب برای آزمون جست‌وجو، پروژه و ارزیابی."
                research.content_kind = content_kind
                research.content_category = content_category
                research.main_format = main_format
                research.sub_format = sub_format
                research.source_type = source_type
                research.source = source
                research.source_volume = str(theme_index + 1)
                research.source_page = str(20 + global_index * 3)
                research.source_narrator = "گروه پژوهش ضحی"
                research.source_note = "منبع نمایشی داخلی؛ محتوای فیش با پروژه و مخاطب آن هماهنگ است."
                research.audience_profiles = theme["audiences"]
                research.access_level = "public" if status == "published" else "team"
                research.team = None if status == "published" else demo_team
                research.status = status
                research.is_featured = status == "published" and item_index in {1, 6}
                research.featured_order = global_index if research.is_featured else 0
                research.view_count = 120 + (30 - global_index) * 7 if status == "published" else research.view_count
                research.current_round = 1
                research.version = 1
                research.submitted_at = now - timedelta(days=35 - global_index)
                research.approved_at = now - timedelta(days=3 + item_index) if status in {"approved", "published"} else None
                research.save()
                research.characters.set([character])
                research.occasions.set([occasion] if item_index % 3 == 0 else [])

                research.topic_analyses.all().delete()
                first_analysis = TopicAnalysis.objects.create(
                    research=research,
                    topic=topic,
                    predicate=predicate,
                    author_interpretation=(
                        f"برای موضوع «{theme['subject']}»، این فیش بر {theme['processing'][0]} تمرکز دارد و "
                        "راه تبدیل مفهوم به پیام قابل اجرا را توضیح می‌دهد."
                    ),
                    review_status="approved" if status in {"approved", "published"} else "unchecked",
                    order=0,
                )
                first_analysis.processing_keys.set(processing_values)
                second_analysis = TopicAnalysis.objects.create(
                    research=research,
                    topic=secondary_topic,
                    predicate=secondary_predicate,
                    author_interpretation=(
                        f"از منظر تربیت اجتماعی، «{title}» می‌تواند به رشد مسئولیت‌پذیری و گفت‌وگوی اخلاقی کمک کند."
                    ),
                    review_status="unchecked",
                    order=1,
                )
                second_analysis.processing_keys.set([processing_values[1]])

                research.indexes.all().delete()
                tag_value = self._value("tags", theme["subject"])
                category_value = self._value("category", "محتوای مولد")
                takeaway_value = self._value("takeaway", f"یک اقدام کوچک درباره {theme['subject']} از همین امروز آغاز شود")
                ResearchIndex.objects.bulk_create(
                    [
                        ResearchIndex(research=research, index_type=tags_type, index_value=tag_value, is_primary=True, added_by=researcher),
                        ResearchIndex(research=research, index_type=category_type, index_value=category_value, added_by=researcher),
                        ResearchIndex(research=research, index_type=takeaway_type, index_value=takeaway_value, added_by=researcher),
                    ]
                )

                ProjectResearch.objects.update_or_create(
                    project=project,
                    research=research,
                    defaults={
                        "added_by": owner,
                        "note": f"فیش شماره {item_index + 1} پروژه؛ مرتبط با {theme['subject']} و {theme['predicate']}",
                        "order": item_index,
                    },
                )

                ReviewerAssignment.objects.get_or_create(
                    researcher=researcher,
                    reviewer=reviewer,
                    scope=subject_type,
                    defaults={"is_active": True},
                )
                task = ReviewTask.objects.filter(
                    research=research, reviewer=reviewer, scope=subject_type, round=1
                ).first()
                if task is None:
                    task = ReviewTask(research=research, reviewer=reviewer, scope=subject_type, round=1)
                task.status = "approved" if status in {"approved", "published"} else ("changes_requested" if status == "changes_requested" else "in_review")
                task.started_at = now - timedelta(days=10 + item_index)
                task.completed_at = now - timedelta(days=2 + item_index) if task.status == "approved" else None
                task.save()

                task.comments.filter(body__contains=DEMO_MARKER).delete()
                messages = [
                    (
                        reviewer,
                        f"[{DEMO_MARKER}] ساختار کلی فیش خوب است. لطفاً ارتباط کلید «{theme['processing'][0]}» با شاهد متن را روشن‌تر کنید.",
                        "major",
                        "open",
                    ),
                    (
                        researcher,
                        f"[{DEMO_MARKER}] اصلاح شد؛ در بند دوم یک اقدام عملی و توضیح مخاطب‌محور برای پروژه «{theme['title']}» اضافه کردم.",
                        "note",
                        "resolved",
                    ),
                    (
                        reviewer,
                        f"[{DEMO_MARKER}] ارتباط موضوع، محمول و مخاطب اکنون روشن است. فیش برای استفاده در بسته تبلیغی مناسب ارزیابی می‌شود.",
                        "minor",
                        "resolved" if task.status == "approved" else "open",
                    ),
                ]
                for message_order, (author, message, severity, resolution) in enumerate(messages):
                    comment = ReviewComment.objects.create(
                        task=task,
                        research=research,
                        author=author,
                        index_type=subject_type,
                        body=message,
                        severity=severity,
                        resolution=resolution,
                        resolved_by=reviewer if resolution == "resolved" else None,
                        resolved_at=now - timedelta(days=message_order) if resolution == "resolved" else None,
                    )
                    ReviewComment.objects.filter(pk=comment.pk).update(
                        created_at=now - timedelta(days=8 - message_order, minutes=global_index)
                    )

                research.events.filter(metadata__seed_marker=DEMO_MARKER).delete()
                event_created = WorkflowEvent.objects.create(
                    research=research,
                    actor=researcher,
                    event_type="created",
                    message="فیش نمایشی در بسته داده شفق ایجاد شد.",
                    metadata={"seed_marker": DEMO_MARKER, "project": project.title},
                )
                WorkflowEvent.objects.create(
                    research=research,
                    actor=reviewer,
                    event_type="commented",
                    message="گفت‌وگوی ارزیابی نمونه برای فیش ثبت شد.",
                    metadata={"seed_marker": DEMO_MARKER, "review_task": task.pk},
                )
                Notification.objects.filter(research=research, message__contains=DEMO_MARKER).delete()
                Notification.objects.create(
                    recipient=reviewer,
                    research=research,
                    event=event_created,
                    title="فیش جدید برای ارزیابی",
                    message=f"[{DEMO_MARKER}] فیش «{title}» برای ارزیابی در پروژه «{project.title}» آماده است.",
                    url=f"/zohaonline/reviews/{task.pk}/",
                )
                all_researches.append(research)

        self.stdout.write(self.style.SUCCESS("داده نمایشی شفق با موفقیت ایجاد/به‌روزرسانی شد."))
        self.stdout.write(f"نشان داده: {DEMO_MARKER}")
        self.stdout.write(f"فیش‌های مرتبط: {len(all_researches)}")
        self.stdout.write(f"پروژه‌های تبلیغی: {len(projects)}")
        self.stdout.write(f"پژوهشگران: {len(researchers)}")
        self.stdout.write(f"ارزیابان: {len(reviewers)}")
        self.stdout.write("گفت‌وگوهای ارزیابی: ۹۰ پیام")
        self.stdout.write(f"رمز مشترک حساب‌های نمایشی: {DEMO_PASSWORD}")
