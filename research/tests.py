import json

from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Role, User
from .forms import PromotionProjectForm, ResearchForm
from .models import IndexType, IndexValue, Research, ResearchIndex, TopicAnalysis, normalize_fa


class ZohaRulesTests(TestCase):
    def setUp(self):
        self.preacher_role = Role.objects.create(name="مبلغ", slug="preacher")
        self.researcher_role = Role.objects.create(name="فیش‌نگار", slug="researcher")
        self.admin_role = Role.objects.create(name="مدیر", slug="admin")

    def test_public_signup_is_preacher_only(self):
        client = Client()
        response = client.post(reverse("signup"), {
            "username": "m1", "first_name": "م", "last_name": "الف",
            "mobile": "09120000001", "email": "m1@example.com",
            "expertise": "", "preaching_field": "",
            "password1": "StrongPass-12345", "password2": "StrongPass-12345",
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="m1")
        self.assertTrue(user.roles.filter(slug="preacher").exists())
        self.assertFalse(user.roles.filter(slug="researcher").exists())

    def test_persian_normalization_handles_arabic_letters_digits_and_half_space(self):
        self.assertEqual(normalize_fa("  كِتابِ‌ ۹ دی "), normalize_fa("کتاب 9 دی"))

    def test_private_option_is_visible_only_to_owner_and_admin(self):
        option_type = IndexType.objects.create(name="موضوع", slug="subject")
        owner = User.objects.create_user("owner", "owner@example.com", "x")
        other = User.objects.create_user("other", "other@example.com", "x")
        admin = User.objects.create_user("manager", "manager@example.com", "x")
        admin.roles.add(self.admin_role)
        option = IndexValue.objects.create(
            index_type=option_type, title="موضوع شخصی", visibility="private",
            approval_status="pending", owner=owner,
        )
        self.assertTrue(IndexValue.objects.visible_to(owner).filter(pk=option.pk).exists())
        self.assertFalse(IndexValue.objects.visible_to(other).filter(pk=option.pk).exists())
        self.assertTrue(IndexValue.objects.visible_to(admin).filter(pk=option.pk).exists())

    def test_used_value_is_counted_and_not_orphaned(self):
        user = User.objects.create_user("writer", "writer@example.com", "x")
        user.roles.add(self.researcher_role)
        option_type = IndexType.objects.create(name="برچسب", slug="tags")
        value = IndexValue.objects.create(index_type=option_type, title="نماز")
        fish = Research.objects.create(researcher=user, title="فیش نماز", body="متن اصلی")
        ResearchIndex.objects.create(
            research=fish, index_type=option_type, index_value=value, added_by=user,
        )
        self.assertEqual(value.usage_count, 1)


class ResearchFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("writer", "writer@example.com", "x")
        self.user.roles.add(Role.objects.create(name="فیش‌نگار", slug="researcher"))
        self.types = {}
        for slug, name in [
            ("content-kind", "جنس محتوا"), ("content-category", "محتوا"),
            ("main-format", "قالب اصلی فیش"), ("content-subformat", "ریزقالب"),
            ("source-type", "نوع منبع"), ("main-character", "شخصیت"),
            ("occasion", "مناسبت"), ("subject", "موضوع"),
            ("processing-key", "کلید پردازش"), ("predicate", "محمول"),
        ]:
            self.types[slug] = IndexType.objects.create(name=name, slug=slug)
        self.kind = IndexValue.objects.create(index_type=self.types["content-kind"], title="داستان")
        self.category = IndexValue.objects.create(index_type=self.types["content-category"], title="داستان، حکایت و لطیفه")
        self.main_format = IndexValue.objects.create(index_type=self.types["main-format"], title="متن")
        self.sub_format = IndexValue.objects.create(index_type=self.types["content-subformat"], title="مقاله", parent=self.main_format)
        self.topic = IndexValue.objects.create(index_type=self.types["subject"], title="اخلاق")
        self.key = IndexValue.objects.create(index_type=self.types["processing-key"], title="راهکار")
        self.predicate = IndexValue.objects.create(index_type=self.types["predicate"], title="خوش‌رفتاری")

    def payload(self):
        return {
            "title": "عنوان استاندارد فیش",
            "content_kind": self.kind.pk,
            "content_category": self.category.pk,
            "main_format": self.main_format.pk,
            "sub_format": self.sub_format.pk,
            "abstract": "خلاصه",
            "search_keywords": "رفتار",
            "author_explanation": "",
            "body": "<p>متن اصلی و معتبر فیش درباره رفتار است.</p>",
            "source_type": "", "source": "", "source_volume": "",
            "source_page": "", "source_narrator": "", "source_url": "",
            "source_note": "", "characters": [], "occasions": [],
            "access_level": "private", "duplicate_override": "0",
            "topic_analyses_json": json.dumps([{
                "topic": self.topic.pk,
                "processing_keys": [self.key.pk],
                "predicate": self.predicate.pk,
                "predicate_text": "",
                "interpretation": "برداشت اختصاصی این موضوع",
            }]),
            "audiences_json": "[]",
        }

    def test_complete_structured_fish_form_is_valid(self):
        form = ResearchForm(data=self.payload(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_topic_analysis_allows_optional_processing_key(self):
        payload = self.payload()
        rows = json.loads(payload["topic_analyses_json"])
        rows[0]["processing_keys"] = []
        payload["topic_analyses_json"] = json.dumps(rows)
        form = ResearchForm(data=payload, user=self.user)
        self.assertTrue(form.is_valid(), form.errors.as_json())


class PromotionProjectTests(TestCase):
    def setUp(self):
        self.role = Role.objects.create(name="فیش‌نگار", slug="researcher")
        self.user = User.objects.create_user("project-owner", "owner@example.com", "x")
        self.user.roles.add(self.role)
        self.fish = Research.objects.create(
            researcher=self.user, title="فیش پروژه", body="متن فیش", access_level="private"
        )
        self.client.force_login(self.user)

    def test_search_can_add_selected_research_to_project(self):
        from .models import PromotionProject, ProjectResearch
        project = PromotionProject.objects.create(title="پروژه محرم", owner=self.user)
        response = self.client.post(
            reverse("project_add_researches", kwargs={"pk": project.pk}),
            {"research_ids": [str(self.fish.pk)], "next": reverse("project_edit", kwargs={"pk": project.pk})},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProjectResearch.objects.filter(project=project, research=self.fish).exists())


    def test_project_audience_profiles_store_titles_and_primary_group(self):
        from .models import PromotionProject
        audience_type = IndexType.objects.create(name="صنف مخاطب", slug="audience-job")
        teacher = IndexValue.objects.create(index_type=audience_type, title="معلم")
        form = PromotionProjectForm(data={
            "title": "پروژه مخاطب‌محور",
            "description": "شرح",
            "objective": "هدف",
            "status": "active",
            "is_active": "on",
            "audiences_json": json.dumps([{
                "is_primary": True, "general": False,
                "genders": ["زن", "مرد"], "ages": ["جوان"],
                "jobs": [str(teacher.pk)], "country": "ایران", "city": "تهران",
                "literacy": "متوسط", "channels": ["کارگاه"],
                "needs": "آموزش کاربردی", "notes": "زبان روشن",
            }]),
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        project = form.save(commit=False)
        project.owner = self.user
        project.save()
        project.refresh_from_db()
        self.assertEqual(project.audience_profiles[0]["jobs"], ["معلم"])
        self.assertTrue(project.audience_profiles[0]["is_primary"])
        self.assertIn("معلم", project.target_audience)

    def test_other_user_cannot_open_private_project(self):
        from .models import PromotionProject
        project = PromotionProject.objects.create(title="پروژه خصوصی", owner=self.user)
        other = User.objects.create_user("other-project", "other-project@example.com", "x")
        self.client.force_login(other)
        response = self.client.get(reverse("project_edit", kwargs={"pk": project.pk}))
        self.assertEqual(response.status_code, 404)


class Aurora250AccessAndLifecycleTests(TestCase):
    def setUp(self):
        from accounts.models import Team, TeamMembership
        self.researcher_role = Role.objects.create(name="فیش‌نگار ۲.۵", slug="researcher-250")
        self.owner = User.objects.create_user("team-owner", "team-owner@example.com", "x")
        self.member = User.objects.create_user("team-member", "team-member@example.com", "x")
        self.outsider = User.objects.create_user("team-outsider", "team-outsider@example.com", "x")
        self.team = Team.objects.create(name="گروه تست ۲.۵", owner=self.owner)
        TeamMembership.objects.create(team=self.team, user=self.owner, role="manager")
        TeamMembership.objects.create(team=self.team, user=self.member, role="member")

    def test_team_research_is_visible_only_to_team(self):
        fish = Research.objects.create(
            researcher=self.owner, title="فیش گروهی", body="متن", access_level="team", team=self.team,
        )
        self.assertTrue(Research.objects.visible_to(self.member).filter(pk=fish.pk).exists())
        self.assertFalse(Research.objects.visible_to(self.outsider).filter(pk=fish.pk).exists())

    def test_public_access_requires_published_lifecycle(self):
        fish = Research.objects.create(
            researcher=self.owner, title="فیش عمومی تاییدنشده", body="متن", access_level="public", status="approved",
        )
        self.assertFalse(Research.objects.visible_to(self.outsider).filter(pk=fish.pk).exists())
        fish.status = "published"
        fish.save(update_fields=["status", "updated_at"])
        self.assertTrue(Research.objects.visible_to(self.outsider).filter(pk=fish.pk).exists())

    def test_disabled_user_is_synchronized_with_django_is_active(self):
        user = User.objects.create_user("disabled-250", "disabled-250@example.com", "x")
        user.is_enabled = False
        user.save()
        user.refresh_from_db()
        self.assertFalse(user.is_active)
