import importlib
import json
import re
from datetime import timedelta
from difflib import SequenceMatcher

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, TrigramSimilarity
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, connection, transaction
from django.db.models import Avg, Count, F, Prefetch, Q, TextField
from django.db.models.functions import Cast, TruncMonth
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import role_required
from accounts.models import User
from zoha.release import CODENAME, MARKER as RELEASE_MARKER, VERSION
from .forms import AssignmentForm, FullContentForm, PromotionProjectForm, ResearchForm, ReviewCommentForm, SermonStyleForm
from .models import (
    AIGenerationLog, AIEndpointStatus, AIIndexingRun, AIIndexSuggestion, AIProbeRun, ContentReport, EducationCourse, EducationLesson, IndexType, IndexValue, Notification,
    OptionAuditLog, ProjectResearch, CustomCollection, FullContent, PromotionProject, Research, ResearchAttachment, ResearchBookmark, ResearchIndex,
    ResearchReaction, ReviewerAssignment, ReviewComment, ReviewTask, SearchLog, SermonArtifact, SermonRevision, SermonStyle, Source,
    TopicAnalysis, WorkflowEvent, normalize_fa,
)
from .services import event_and_notify, submit_research
from .enrichment import enrich_before_submission, enrich_semantic_text, generate_featured_image, refresh_search_document, suggest_seo_tags
from .jalali import format_jalali, parse_jalali


@require_GET
def release_info(request):
    return JsonResponse({
        "application": "ZohaOnline",
        "version": VERSION,
        "codename": CODENAME,
        "marker": RELEASE_MARKER,
        "dashboard_skin": "zoha-discovery-270",
        "served_at": timezone.now().isoformat(),
    })



JALALI_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

def occasion_metadata_from_request(request, current=None):
    meta = dict(current or {})
    day_raw = (request.POST.get("jalali_day") or "").strip()
    month = (request.POST.get("jalali_month") or "").strip()
    if not day_raw and not month:
        return meta
    try:
        day = int(day_raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
    except (TypeError, ValueError):
        raise ValueError("روز شمسی نامعتبر است.")
    if day < 1 or day > 31 or month not in JALALI_MONTHS:
        raise ValueError("روز یا ماه شمسی نامعتبر است.")
    meta["jalali_day"] = day
    meta["jalali_month"] = month
    return meta

CORE_TYPES = {
    "content-kind", "content-category", "main-format", "content-subformat",
    "source-type", "subject", "processing-key", "predicate", "main-character",
    "occasion", "audience-job", "audience-country", "audience-city",
    "promotional-usage", "presentation-style",
}


def is_admin(user):
    return user.is_superuser or user.has_role("admin")


def can_edit(user, research):
    return is_admin(user) or (
        user.has_role("researcher") and research.researcher_id == user.id and research.can_be_edited
    )


def can_view(user, research):
    return Research.objects.visible_to(user).filter(pk=research.pk).exists()


def visible_values(user, slug, parent_id=None):
    qs = IndexValue.objects.visible_to(user).filter(index_type__slug=slug).select_related("index_type", "parent")
    if parent_id is not None:
        qs = qs.filter(parent_id=parent_id)
    return qs


def option_payload(option):
    return {
        "id": option.pk,
        "text": option.display_label,
        "title": option.title,
        "display": option.display_label,
        "type": option.index_type.slug,
        "parent": option.parent_id,
        "visibility": option.visibility,
        "approval": option.approval_status,
        "private": option.visibility == "private",
        "aliases": option.alias_list,
        "metadata": option.metadata or {},
    }


def similarity_score(a, b):
    return SequenceMatcher(None, normalize_fa(a), normalize_fa(b)).ratio()


def save_topic_analyses(research, rows, user):
    topic_type = get_object_or_404(IndexType, slug="subject")
    processing_type = get_object_or_404(IndexType, slug="processing-key")
    predicate_type = get_object_or_404(IndexType, slug="predicate")

    allowed_topics = IndexValue.objects.visible_to(user).filter(index_type=topic_type)
    allowed_processing = IndexValue.objects.visible_to(user).filter(index_type=processing_type)
    allowed_predicates = IndexValue.objects.visible_to(user).filter(index_type=predicate_type)

    research.topic_analyses.all().delete()
    for order, row in enumerate(rows):
        topic = get_object_or_404(allowed_topics, pk=row["topic"])
        predicate = None
        if row.get("predicate"):
            predicate = get_object_or_404(allowed_predicates, pk=row["predicate"])
        analysis = TopicAnalysis.objects.create(
            research=research,
            topic=topic,
            predicate=predicate,
            predicate_text=(row.get("predicate_text") or "").strip(),
            author_interpretation=(row.get("interpretation") or "").strip(),
            review_status=row.get("review_status") or "unchecked",
            order=order,
        )
        keys = allowed_processing.filter(pk__in=row.get("processing_keys") or [])
        analysis.processing_keys.set(keys)


def save_special_indexes(research, payload, user):
    """ذخیره کاربرد تبلیغی و شیوه پیشنهادی ارائه با تفکیک گزینه اصلی/تکمیلی."""
    for slug in ("promotional-usage",):
        try:
            index_type = IndexType.objects.get(slug=slug, is_active=True)
        except IndexType.DoesNotExist:
            continue
        row = (payload or {}).get(slug) or {}
        ids = [str(x) for x in (row.get("items") or []) if str(x).strip()]
        primary = str(row.get("primary") or "").strip() or None
        allowed = IndexValue.objects.visible_to(user).filter(index_type=index_type, pk__in=ids)
        allowed_map = {str(x.pk): x for x in allowed}
        research.indexes.filter(index_type=index_type).delete()
        for order, value_id in enumerate(ids):
            value = allowed_map.get(str(value_id))
            if not value:
                continue
            ResearchIndex.objects.create(
                research=research, index_type=index_type, index_value=value, added_by=user,
                is_primary=str(value.pk) == str(primary), order=order,
            )


def save_new_collection(research, user, title):
    title = re.sub(r"\s+", " ", (title or "")).strip()
    if not title:
        return None
    collection, _ = CustomCollection.objects.get_or_create(owner=user, title=title, defaults={"is_active": True})
    research.personal_collections.add(collection)
    return collection


def attachment_kind(upload):
    content_type = (getattr(upload, "content_type", "") or "").lower()
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("audio/"):
        return "audio"
    if content_type in {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"}:
        return "document"
    return "other"


def save_attachments(research, user, files):
    for upload in files or []:
        ResearchAttachment.objects.create(research=research, file=upload, kind=attachment_kind(upload), uploaded_by=user)


def research_form_context(request, form, research=None):
    def values(slug):
        return list(visible_values(request.user, slug).values("id", "title", "parent_id", "parent__title", "visibility", "metadata"))

    def grouped(slug):
        rows = values(slug)
        parents = [row for row in rows if not row.get("parent_id")]
        children = [row for row in rows if row.get("parent_id")]
        result = []
        for parent in parents:
            result.append({
                "id": parent["id"], "title": parent["title"], "visibility": parent["visibility"],
                "children": [row for row in children if row.get("parent_id") == parent["id"]],
            })
        orphan_ids = {row["id"] for group in result for row in group["children"]}
        orphan_children = [row for row in children if row["id"] not in orphan_ids]
        if orphan_children:
            result.append({"id": None, "title": "سایر", "visibility": "global", "children": orphan_children})
        return result

    index_types = (
        IndexType.objects.filter(is_active=True)
        .exclude(slug__in=CORE_TYPES)
        .annotate(item_count=Count("research_indexes", filter=Q(research_indexes__research=research)))
        if research else []
    )
    return {
        "form": form, "research": research, "index_types": index_types,
        "content_kind_options": values("content-kind"), "content_category_options": values("content-category"),
        "topic_options": values("subject"), "processing_options": values("processing-key"),
        "predicate_options": values("predicate"), "job_options": values("audience-job"),
        "country_options": values("audience-country"), "city_options": values("audience-city"),
        "usage_options": values("promotional-usage"), "usage_groups": grouped("promotional-usage"),
        "presentation_options": values("presentation-style"),
        "existing_analyses": form["topic_analyses_json"].value() or "[]",
        "existing_audiences": form["audiences_json"].value() or "[]",
        "existing_special_indexes": form["special_indexes_json"].value() or "{}",
        "attachments": research.attachments.all() if research else [],
    }


@login_required
def dashboard(request):
    user = request.user
    admin_system_scope = is_admin(user) and request.GET.get("scope") == "system"
    # 2.7: even admins who also work as fish collectors see their own real statistics by default.
    if user.has_role("researcher") and not admin_system_scope:
        mode = "researcher"
        scope = Research.objects.filter(researcher=user)
    elif admin_system_scope:
        mode = "admin"
        scope = Research.objects.all()
    elif user.has_role("reviewer"):
        mode = "reviewer"
        scope = Research.objects.visible_to(user)
    else:
        mode = "preacher"
        scope = Research.objects.visible_to(user)

    counters = scope.aggregate(
        total=Count("id"),
        draft=Count("id", filter=Q(status="draft")),
        pending=Count("id", filter=Q(status__in=["submitted", "in_review"])),
        changes=Count("id", filter=Q(status="changes_requested")),
        approved=Count("id", filter=Q(status__in=["approved", "published"])),
    )
    total = counters["total"]
    status_map = dict(Research.STATUS)
    status_rows = list(scope.values("status").annotate(total=Count("id")).order_by("status"))
    cards = [
        {"label": "فیش‌های من" if mode == "researcher" else "کل فیش‌ها", "value": total, "icon": "fa-file-lines", "tone": "primary", "url": reverse("research_list")},
        {"label": "پیش‌نویس‌ها", "value": counters["draft"], "icon": "fa-pen", "tone": "purple", "url": reverse("research_list") + "?status=draft"},
        {"label": "در انتظار بررسی", "value": counters["pending"], "icon": "fa-clock", "tone": "warning", "url": reverse("research_list") + "?status_group=pending"},
        {"label": "نیازمند اصلاح", "value": counters["changes"], "icon": "fa-pen-to-square", "tone": "danger", "url": reverse("research_list") + "?status=changes_requested"},
        {"label": "تأییدشده‌ها", "value": counters["approved"], "icon": "fa-circle-check", "tone": "success", "url": reverse("research_list") + "?status=approved"},
    ]
    if admin_system_scope:
        cards.extend([
            {"label": "گزینه‌های در انتظار", "value": IndexValue.objects.filter(approval_status="pending").count() + Source.objects.filter(approval_status="pending").count(), "icon": "fa-user-clock", "tone": "warning", "url": reverse("option_management")},
            {"label": "کاربران فعال", "value": User.objects.filter(is_active=True, is_enabled=True).count(), "icon": "fa-users", "tone": "success", "url": reverse("user_list")},
        ])
    context = {
        "mode": mode, "cards": cards, "recent": scope.select_related("researcher", "content_kind")[:6],
        "drafts": scope.filter(status="draft").select_related("content_kind")[:4],
        "pending": scope.filter(status__in=["submitted", "in_review"]).select_related("content_kind")[:4],
        "needs_action": scope.filter(status="changes_requested").select_related("content_kind")[:4],
        "approved_count": counters["approved"],
        "tasks": user.review_tasks.select_related("research", "scope")[:8] if user.has_role("reviewer") else [],
        "status_chart": {"labels": [status_map.get(row["status"], row["status"]) for row in status_rows], "values": [row["total"] for row in status_rows]},
        "admin_system_scope": admin_system_scope,
        "can_switch_system_scope": is_admin(user),
    }
    return render(request, "research/dashboard.html", context)


@login_required
def research_list(request):
    # ZOHA-W3.1-RESEARCH-LIST-FILTERS
    scope_mode = request.GET.get("scope", "").strip()

    if scope_mode == "mine":
        qs = Research.objects.filter(researcher=request.user)
    elif request.user.has_role("researcher") and not is_admin(request.user):
        qs = Research.objects.filter(researcher=request.user)
    else:
        qs = Research.objects.visible_to(request.user)

    qs = qs.select_related("researcher", "content_kind", "main_format", "team").prefetch_related("topic_analyses__topic")

    status = request.GET.get("status", "").strip()
    status_group = request.GET.get("status_group", "").strip()
    domain = request.GET.get("domain", "").strip()

    # ZOHA-W3.1.2-RESEARCH-DOMAIN-FILTER
    if domain == "complementary":

        complementary_ids = (
            ResearchIndex.objects
            .filter(
                index_type__slug="category",
                index_value__title="محتوای تکمیلی",
            )
            .values(
                "research_id"
            )
        )

        qs = qs.filter(
            pk__in=complementary_ids
        )

    elif domain == "generated":

        non_generated_ids = (
            ResearchIndex.objects
            .filter(
                index_type__slug="category",
                index_value__title__in=[
                    "محتوای تکمیلی",
                    "محتوای کامل",
                ],
            )
            .values(
                "research_id"
            )
        )

        qs = qs.exclude(
            pk__in=non_generated_ids
        )

    q = request.GET.get("q", "").strip()
    kind = request.GET.get("kind", "").strip()
    topic = request.GET.get("topic", "").strip()
    access = request.GET.get("access", "").strip()
    date_from_raw = request.GET.get("date_from", "").strip()
    date_to_raw = request.GET.get("date_to", "").strip()
    date_from = (parse_jalali(date_from_raw) or parse_date(date_from_raw)) if date_from_raw else None
    date_to = (parse_jalali(date_to_raw) or parse_date(date_to_raw)) if date_to_raw else None
    if status:
        qs = qs.filter(status=status)

    elif status_group == "pending":
        qs = qs.filter(
            status__in=[
                "submitted",
                "in_review",
            ]
        )

    elif status_group == "approved":
        qs = qs.filter(
            status__in=[
                "approved",
                "published",
            ]
        )

    elif status_group == "changes":
        qs = qs.filter(
            status="changes_requested"
        )

    elif status_group == "rejected":
        qs = qs.filter(
            status="rejected"
        )

    if q:
        normalized_q = normalize_fa(q)
        qs = qs.filter(
            Q(search_document_normalized__icontains=normalized_q)
            | Q(title__icontains=q) | Q(abstract__icontains=q) | Q(body__icontains=q)
            | Q(search_keywords__icontains=q) | Q(source__title__icontains=q)
            | Q(topic_analyses__topic__title__icontains=q)
            | Q(characters__title__icontains=q) | Q(secondary_characters__title__icontains=q)
        )
    if kind:
        qs = qs.filter(content_kind_id=kind)
    if topic:
        qs = qs.filter(topic_analyses__topic_id=topic)
    if access:
        qs = qs.filter(access_level=access)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    qs = qs.distinct().order_by("-updated_at")
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_params = request.GET.copy(); page_params.pop("page", None)
    return render(request, "research/research_list.html", {
        "researches": page_obj.object_list, "page_obj": page_obj, "status": status, "status_group": status_group,
        "domain": domain,
        "q": q, "kind": kind, "topic": topic, "access": access, "date_from": date_from_raw, "date_to": date_to_raw,
        "status_choices": Research.STATUS, "access_choices": Research.ACCESS_LEVEL,
        "kinds": visible_values(request.user, "content-kind"),
        "topics": visible_values(request.user, "subject")[:700],
        "page_query": page_params.urlencode(),
    })


def _maybe_generate_featured_image(research, user):
    """Generate a featured image automatically when an image provider is configured.

    Image generation is intentionally best-effort: a provider outage must never prevent
    saving/submitting a research card. Errors remain visible in AIGenerationLog.
    """
    if research.featured_image or not settings.ZOHA_IMAGE_API_URL:
        return False
    try:
        generate_featured_image(research, user=user)
        return True
    except Exception:
        return False


@role_required("researcher", "admin")
def research_create(request):
    form = ResearchForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        research = form.save(commit=False)
        research.researcher = request.user
        research.audience_profiles = form.cleaned_data["audiences_json"]
        research.seo_tags = research.seo_tags or []
        research.access_level = form.cleaned_data.get("access_level") or "private"
        research.status = "draft"
        research.save()
        form.save_m2m()
        save_new_collection(research, request.user, form.cleaned_data.get("new_collection_title"))
        save_topic_analyses(research, form.cleaned_data["topic_analyses_json"], request.user)
        save_special_indexes(research, form.cleaned_data["special_indexes_json"], request.user)
        save_attachments(research, request.user, form.cleaned_data.get("attachments"))
        refresh_search_document(research)
        WorkflowEvent.objects.create(research=research, actor=request.user, event_type="created", message="فیش جدید ایجاد شد.")
        if request.POST.get("save_mode") == "submit":
            enrich_before_submission(research, user=request.user)
            _maybe_generate_featured_image(research, request.user)
            count = submit_research(research, request.user)
            messages.success(request, "فیش ذخیره و برای بررسی ارسال شد." if count else "فیش ذخیره و ارسال شد؛ هنوز ارزیاب فعالی به شما تخصیص داده نشده است.")
            return redirect("research_detail", pk=research.pk)
        messages.success(request, "پیش‌نویس فیش با موفقیت ذخیره شد.")
        return redirect("research_edit", pk=research.pk)
    return render(request, "research/research_form.html", research_form_context(request, form))


@login_required
def research_edit(request, pk):
    research = get_object_or_404(Research, pk=pk)
    if not can_edit(request.user, research):
        raise PermissionDenied
    form = ResearchForm(request.POST or None, request.FILES or None, instance=research, user=request.user)
    if request.method == "POST" and form.is_valid():
        research = form.save(commit=False)
        research.audience_profiles = form.cleaned_data["audiences_json"]
        research.seo_tags = research.seo_tags or []
        research.access_level = form.cleaned_data.get("access_level") or "private"
        research.save()
        form.save_m2m()
        save_new_collection(research, request.user, form.cleaned_data.get("new_collection_title"))
        save_topic_analyses(research, form.cleaned_data["topic_analyses_json"], request.user)
        save_special_indexes(research, form.cleaned_data["special_indexes_json"], request.user)
        save_attachments(research, request.user, form.cleaned_data.get("attachments"))
        refresh_search_document(research)
        WorkflowEvent.objects.create(research=research, actor=request.user, event_type="updated", message="اطلاعات فیش ویرایش شد.")
        if request.POST.get("save_mode") == "submit":
            enrich_before_submission(research, user=request.user)
            _maybe_generate_featured_image(research, request.user)
            count = submit_research(research, request.user)
            messages.success(request, "فیش ذخیره و برای بررسی ارسال شد." if count else "فیش ذخیره و ارسال شد؛ هنوز ارزیاب فعالی به شما تخصیص داده نشده است.")
            return redirect("research_detail", pk=research.pk)
        messages.success(request, "اطلاعات فیش ذخیره شد.")
        return redirect("research_edit", pk=research.pk)
    return render(request, "research/research_form.html", research_form_context(request, form, research))


@login_required
def research_detail(request, pk):
    research = get_object_or_404(
        Research.objects.select_related(
            "researcher", "content_kind", "content_category", "main_format", "sub_format",
            "source_type", "source",
        ).prefetch_related(
            "characters", "secondary_characters", "occasions", "topic_analyses__topic",
            "topic_analyses__processing_keys", "topic_analyses__predicate",
            Prefetch("indexes", queryset=ResearchIndex.objects.select_related("index_type", "index_value").order_by("index_type__order", "order"), to_attr="prefetched_indexes"),
        ), pk=pk,
    )
    if not can_view(request.user, research):
        raise PermissionDenied
    grouped = {}
    for item in research.prefetched_indexes:
        grouped.setdefault(item.index_type, []).append(item)
    grouped_indexes = list(grouped.items())
    return render(request, "research/research_detail.html", {
        "research": research,
        "grouped_indexes": grouped_indexes,
        "tasks": research.review_tasks.select_related("reviewer", "scope"),
    })


@login_required
@require_POST
def research_delete(request, pk):
    research = get_object_or_404(Research, pk=pk)
    if research.researcher_id != request.user.id and not is_admin(request.user):
        raise PermissionDenied
    title = research.display_title
    research.delete()
    messages.success(request, f"فیش «{title}» حذف شد.")
    return redirect("research_list")


@role_required("researcher", "admin")
@require_POST
def research_submit(request, pk):
    research = get_object_or_404(Research, pk=pk)
    if not can_edit(request.user, research):
        raise PermissionDenied
    missing = []
    if not re.sub(r"<[^>]+>", "", research.body or "").strip():
        missing.append("متن اصلی")
    if not research.has_structured_index:
        missing.append("حداقل یک نمایه یا دسته ساختاریافته")
    if research.access_level == "team" and not research.team_id:
        missing.append("گروه کاری")
    if missing:
        messages.error(request, "برای ارسال این موارد را تکمیل کنید: " + "، ".join(missing))
        return redirect("research_edit", pk=research.pk)
    enrich_before_submission(research, user=request.user)
    _maybe_generate_featured_image(research, request.user)
    count = submit_research(research, request.user)
    messages.success(request, "فیش برای بررسی ارسال شد." if count else "فیش ارسال شد؛ هنوز ارزیاب فعالی به شما تخصیص داده نشده است.")
    return redirect("research_detail", pk=research.pk)


@login_required
def index_panel(request, pk, type_id):
    research = get_object_or_404(Research, pk=pk)
    index_type = get_object_or_404(IndexType, pk=type_id, is_active=True)
    if not can_edit(request.user, research):
        raise PermissionDenied
    items = research.indexes.filter(index_type=index_type).select_related("index_value")
    values = IndexValue.objects.visible_to(request.user).filter(index_type=index_type).annotate(usage=Count("research_indexes"))[:1000]
    return render(request, "research/partials/index_panel.html", {
        "research": research, "index_type": index_type, "items": items, "values": values,
    })


@login_required
@require_POST
@transaction.atomic
def index_add(request, pk, type_id):
    research = get_object_or_404(Research, pk=pk)
    index_type = get_object_or_404(IndexType, pk=type_id, is_active=True)
    if not can_edit(request.user, research):
        raise PermissionDenied
    value_id = request.POST.get("value_id")
    new_value = request.POST.get("new_value", "").strip()
    text_value = request.POST.get("text_value", "").strip()
    excerpt = request.POST.get("source_excerpt", "").strip()
    value = None
    if value_id:
        value = get_object_or_404(IndexValue.objects.visible_to(request.user), pk=value_id, index_type=index_type)
    elif new_value and index_type.allow_new_values:
        normalized = normalize_fa(new_value)
        value = IndexValue.objects.filter(index_type=index_type, normalized_title=normalized).first()
        if not value:
            value = IndexValue.objects.create(
                index_type=index_type, title=new_value, created_by=request.user, owner=None if is_admin(request.user) else request.user,
                visibility="global" if is_admin(request.user) else "private",
                approval_status="approved" if is_admin(request.user) else "pending",
            )
            OptionAuditLog.objects.create(option=value, actor=request.user, action="created")
    if not value and not text_value:
        return JsonResponse({"error": "یک گزینه یا مقدار متنی وارد کنید."}, status=400)
    if not index_type.allow_multiple:
        research.indexes.filter(index_type=index_type).delete()
    ResearchIndex.objects.get_or_create(
        research=research, index_type=index_type, index_value=value, text_value=text_value,
        defaults={"source_excerpt": excerpt, "added_by": request.user},
    )
    refresh_search_document(research)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def index_remove(request, pk, item_id):
    research = get_object_or_404(Research, pk=pk)
    if not can_edit(request.user, research):
        raise PermissionDenied
    get_object_or_404(ResearchIndex, pk=item_id, research=research).delete()
    refresh_search_document(research)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def value_delete(request, value_id):
    value = get_object_or_404(IndexValue, pk=value_id)
    if not (is_admin(request.user) or value.owner_id == request.user.id):
        raise PermissionDenied
    if value.usage_count:
        value.is_active = False
        value.save(update_fields=["is_active", "updated_at"])
    else:
        value.delete()
    return JsonResponse({"ok": True})


@require_GET
@login_required
def api_options(request):
    slug = request.GET.get("type", "").strip()
    query = request.GET.get("q", "").strip()
    parent = request.GET.get("parent")
    if not slug:
        return JsonResponse({"results": []})
    qs = visible_values(request.user, slug, parent_id=parent if parent else None)
    if query:
        normalized = normalize_fa(query)
        if connection.vendor == "postgresql":
            candidates = list(qs.annotate(similarity=TrigramSimilarity("normalized_title", normalized)).filter(
                Q(normalized_title__icontains=normalized) | Q(title__icontains=query) |
                Q(aliases__icontains=query) | Q(similarity__gte=0.18)
            ).order_by("-similarity", "title")[:60])
        else:
            candidates = list(qs.filter(
                Q(normalized_title__icontains=normalized) | Q(title__icontains=query) | Q(aliases__icontains=query)
            )[:60])
    else:
        candidates = list(qs[:60])
    return JsonResponse({"results": [option_payload(item) for item in candidates]})


@require_POST
@login_required
@transaction.atomic
def api_option_add(request):
    slug = request.POST.get("type", "").strip()
    title = request.POST.get("title", "").strip()
    aliases = request.POST.get("aliases", "").strip()
    parent_id = request.POST.get("parent") or None
    # ZOHA-W1.4-FORCE-CREATE:START
    force = str(request.POST.get("force", "")).strip().lower() in {"1", "true", "yes", "on"}
    # ZOHA-W1.4-FORCE-CREATE:END
    if not slug or not title:
        return JsonResponse({"error": "نوع گزینه و عنوان الزامی است."}, status=400)
    index_type = get_object_or_404(IndexType, slug=slug, is_active=True, allow_new_values=True)
    normalized = normalize_fa(title)
    exact_qs = IndexValue.objects.filter(index_type=index_type, normalized_title=normalized, merged_into__isnull=True)
    exact_qs = exact_qs.filter(parent_id=parent_id) if parent_id else exact_qs.filter(parent__isnull=True)
    exact = exact_qs.first()
    if exact:
        return JsonResponse({"error": "این گزینه از قبل وجود دارد.", "existing": option_payload(exact)}, status=409)
    similar = []
    for item in IndexValue.objects.filter(index_type=index_type, is_active=True, merged_into__isnull=True)[:3000]:
        score = similarity_score(title, item.title)
        if score >= 0.72:
            similar.append({**option_payload(item), "score": round(score * 100)})
    similar = sorted(similar, key=lambda x: -x["score"])[:8]
    if similar and not force:
        return JsonResponse({"error": "گزینه‌های مشابه پیدا شد.", "similar": similar}, status=409)
    parent = None
    if parent_id:
        parent = get_object_or_404(IndexValue, pk=parent_id, is_active=True, merged_into__isnull=True)
        if slug == "content-subformat" and parent.index_type.slug != "main-format":
            return JsonResponse({"error": "والد ریزقالب باید یکی از قالب‌های اصلی فیش باشد."}, status=400)
        if slug == "content-category" and parent.index_type.slug != "content-kind":
            return JsonResponse({"error": "والد محتوا باید یکی از گزینه‌های جنس محتوا باشد."}, status=400)
        if slug == "promotional-usage" and parent.index_type.slug != "promotional-usage":
            return JsonResponse({"error": "زیرگروه کاربرد تبلیغی باید زیر یکی از محورهای کاربرد قرار گیرد."}, status=400)
    try:
        metadata = occasion_metadata_from_request(request) if slug == "occasion" else {}
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    option = IndexValue.objects.create(
        index_type=index_type, title=title, aliases=aliases, parent=parent, metadata=metadata,
        visibility="global" if is_admin(request.user) else "private",
        approval_status="approved" if is_admin(request.user) else "pending",
        owner=None if is_admin(request.user) else request.user,
        created_by=request.user,
    )
    OptionAuditLog.objects.create(option=option, actor=request.user, action="created", details={"similar_override": bool(similar)})
    return JsonResponse({"ok": True, "option": option_payload(option)})


@require_GET
@login_required
def api_title_similar(request):
    title = request.GET.get("q", "").strip()
    if len(title) < 2:
        return JsonResponse({"results": []})
    normalized = normalize_fa(title)
    base = Research.objects.visible_to(request.user).select_related("content_kind")
    results = []
    if connection.vendor == "postgresql":
        candidates = (
            base.annotate(similarity=TrigramSimilarity("title", title))
            .filter(similarity__gte=0.18)
            .order_by("-similarity", "-updated_at")[:20]
        )
        for item in candidates:
            score = max(float(item.similarity or 0), 1.0 if normalize_fa(item.title) == normalized else 0.0)
            results.append({
                "id": str(item.pk), "title": item.title, "status": item.get_status_display(),
                "kind": item.content_kind.title if item.content_kind_id else "—",
                "score": round(score * 100), "url": reverse("research_detail", args=[item.pk]),
                "exact": normalize_fa(item.title) == normalized,
            })
    else:
        for item in base.only("id", "title", "status", "content_kind")[:3000]:
            score = similarity_score(normalized, item.title)
            if normalized in normalize_fa(item.title):
                score = max(score, 0.88)
            if score >= 0.62:
                results.append({
                    "id": str(item.pk), "title": item.title, "status": item.get_status_display(),
                    "kind": item.content_kind.title if item.content_kind_id else "—",
                    "score": round(score * 100), "url": reverse("research_detail", args=[item.pk]),
                    "exact": normalize_fa(item.title) == normalized,
                })
    return JsonResponse({"results": sorted(results, key=lambda x: -x["score"])[:10]})


@require_GET
@login_required
def api_sources(request):
    query = request.GET.get("q", "").strip()
    qs = Source.objects.visible_to(request.user)
    if query:
        normalized = normalize_fa(query)
        if connection.vendor == "postgresql":
            candidates = list(qs.annotate(similarity=TrigramSimilarity("normalized_title", normalized)).filter(
                Q(normalized_title__icontains=normalized) | Q(title__icontains=query) |
                Q(author_name__icontains=query) | Q(aliases__icontains=query) | Q(similarity__gte=0.18)
            ).order_by("-similarity", "title")[:50])
        else:
            candidates = list(qs.filter(
                Q(normalized_title__icontains=normalized) | Q(title__icontains=query) |
                Q(author_name__icontains=query) | Q(aliases__icontains=query)
            )[:50])
    else:
        candidates = list(qs[:50])
    return JsonResponse({"results": [{
        "id": item.pk, "text": str(item), "title": item.title, "author": item.author_name,
        "private": item.visibility == "private",
    } for item in candidates[:50]]})


@require_POST
@login_required
@transaction.atomic
def api_source_add(request):
    title = request.POST.get("title", "").strip()
    author = request.POST.get("author", "").strip()
    aliases = request.POST.get("aliases", "").strip()
    force = request.POST.get("force") == "1"
    if not title:
        return JsonResponse({"error": "نام منبع الزامی است."}, status=400)
    normalized = normalize_fa(title)
    exact = Source.objects.filter(normalized_title=normalized, merged_into__isnull=True).first()
    if exact:
        return JsonResponse({"error": "این منبع از قبل وجود دارد.", "existing": {"id": exact.pk, "text": str(exact)}}, status=409)
    similar = []
    for item in Source.objects.filter(is_active=True, merged_into__isnull=True)[:2000]:
        score = similarity_score(title, item.title)
        if score >= 0.72:
            similar.append({"id": item.pk, "text": str(item), "score": round(score * 100)})
    similar.sort(key=lambda x: -x["score"])
    if similar and not force:
        return JsonResponse({"error": "منابع مشابه پیدا شد.", "similar": similar[:8]}, status=409)
    source = Source.objects.create(
        title=title, author_name=author, aliases=aliases,
        visibility="global" if is_admin(request.user) else "private",
        approval_status="approved" if is_admin(request.user) else "pending",
        owner=None if is_admin(request.user) else request.user,
    )
    OptionAuditLog.objects.create(source=source, actor=request.user, action="created", details={"similar_override": bool(similar)})
    return JsonResponse({"ok": True, "source": {"id": source.pk, "text": str(source)}})


def apply_index_filter(qs, slug, value_id):
    paths = {
        "subject": "topic_analyses__topic_id",
        "processing-key": "topic_analyses__processing_keys__id",
        "predicate": "topic_analyses__predicate_id",
        "main-character": "characters__id",
        "occasion": "occasions__id",
        "content-kind": "content_kind_id",
        "content-category": "content_category_id",
        "main-format": "main_format_id",
        "content-subformat": "sub_format_id",
        "source-type": "source_type_id",
    }
    if slug in paths:
        return qs.filter(**{paths[slug]: value_id})
    return qs.filter(indexes__index_type__slug=slug, indexes__index_value_id=value_id)


def index_q(slug, value_id):
    paths = {
        "subject": "topic_analyses__topic_id",
        "processing-key": "topic_analyses__processing_keys__id",
        "predicate": "topic_analyses__predicate_id",
        "main-character": "characters__id",
        "occasion": "occasions__id",
        "content-kind": "content_kind_id",
        "content-category": "content_category_id",
        "main-format": "main_format_id",
        "content-subformat": "sub_format_id",
        "source-type": "source_type_id",
    }
    if slug in paths:
        return Q(**{paths[slug]: value_id})
    return Q(indexes__index_type__slug=slug, indexes__index_value_id=value_id)


def _legacy_text_search(qs, query, fields, word_mode):
    field_paths = {
        "title": ["title__icontains"],
        "abstract": ["abstract__icontains"],
        "body": ["body__icontains", "topic_analyses__author_interpretation__icontains"],
        "keywords": ["search_keywords__icontains"],
        "source": ["source__title__icontains", "source__author_name__icontains", "source_note__icontains"],
    }
    terms = [query] if word_mode == "exact" else [x for x in re.split(r"\s+", query) if x]
    if word_mode == "any":
        combined = Q()
        for term in terms:
            for field in fields:
                for path in field_paths.get(field, []):
                    combined |= Q(**{path: term})
        return qs.filter(combined)
    for term in terms:
        term_q = Q()
        for field in fields:
            for path in field_paths.get(field, []):
                term_q |= Q(**{path: term})
        qs = qs.filter(term_q)
    return qs


def _postgres_text_search(qs, query, fields, word_mode):
    field_weights = {
        "title": [("title", "A")],
        "abstract": [("abstract", "B")],
        "body": [("body", "C"), ("topic_analyses__author_interpretation", "B")],
        "keywords": [("search_keywords", "A")],
        "source": [("source__title", "A"), ("source__author_name", "B"), ("source_note", "C")],
    }
    vector = None
    for field in fields:
        for path, weight in field_weights.get(field, []):
            part = SearchVector(path, weight=weight, config="simple")
            vector = part if vector is None else vector + part
    if vector is None:
        vector = SearchVector("title", "abstract", "body", config="simple")

    terms = [x for x in re.split(r"\s+", query) if x]
    if word_mode == "exact":
        search_query = SearchQuery(query, search_type="phrase", config="simple")
    elif word_mode == "any":
        search_query = SearchQuery(" OR ".join(terms), search_type="websearch", config="simple")
    else:
        search_query = SearchQuery(" ".join(terms), search_type="plain", config="simple")

    return (
        qs.annotate(
            search_rank=SearchRank(vector, search_query),
            title_similarity=TrigramSimilarity("title", query),
        )
        .filter(Q(search_rank__gte=0.01) | Q(title_similarity__gte=0.18))
        .order_by("-search_rank", "-title_similarity", "-updated_at")
    )


@login_required
@require_POST
@transaction.atomic
def research_autosave(request, pk):
    research = get_object_or_404(Research, pk=pk)
    if not can_edit(request.user, research):
        raise PermissionDenied
    form = ResearchForm(request.POST, instance=research, user=request.user)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=422)
    research = form.save(commit=False)
    research.audience_profiles = form.cleaned_data["audiences_json"]
    research.seo_tags = research.seo_tags or []
    research.access_level = form.cleaned_data.get("access_level") or "private"
    research.save()
    form.save_m2m()
    save_new_collection(research, request.user, form.cleaned_data.get("new_collection_title"))
    save_topic_analyses(research, form.cleaned_data["topic_analyses_json"], request.user)
    save_special_indexes(research, form.cleaned_data["special_indexes_json"], request.user)
    refresh_search_document(research)
    return JsonResponse({"ok": True, "saved_at": timezone.localtime().strftime("%H:%M")})


@login_required
@require_POST
def attachment_delete(request, pk, attachment_id):
    research = get_object_or_404(Research, pk=pk)
    if not can_edit(request.user, research):
        raise PermissionDenied
    attachment = get_object_or_404(ResearchAttachment, pk=attachment_id, research=research)
    attachment.file.delete(save=False)
    attachment.delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def api_option_edit(request, value_id):
    option = get_object_or_404(IndexValue, pk=value_id)
    if not (is_admin(request.user) or option.owner_id == request.user.id):
        return JsonResponse({"error": "فقط گزینه‌های شخصی خودتان قابل ویرایش‌اند؛ گزینه عمومی توسط مدیر سامانه اصلاح می‌شود."}, status=403)
    title = re.sub(r"\s+", " ", request.POST.get("title", "")).strip()
    if not title:
        return JsonResponse({"error": "عنوان نمی‌تواند خالی باشد."}, status=400)
    normalized = normalize_fa(title)
    conflict_qs = IndexValue.objects.filter(index_type=option.index_type, normalized_title=normalized).exclude(pk=option.pk)
    conflict_qs = conflict_qs.filter(parent_id=option.parent_id) if option.parent_id else conflict_qs.filter(parent__isnull=True)
    conflict = conflict_qs.first()
    if conflict:
        return JsonResponse({"error": "گزینه‌ای با این عنوان از قبل وجود دارد.", "existing": option_payload(conflict)}, status=409)
    option.title = title
    option.aliases = request.POST.get("aliases", option.aliases or "")
    if option.index_type.slug == "occasion":
        try:
            option.metadata = occasion_metadata_from_request(request, option.metadata)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
    option.save()
    OptionAuditLog.objects.create(option=option, actor=request.user, action="edited")
    return JsonResponse({"ok": True, "option": option_payload(option)})


@login_required
@require_POST
def api_source_edit(request, source_id):
    source = get_object_or_404(Source, pk=source_id)
    if not (is_admin(request.user) or source.owner_id == request.user.id):
        return JsonResponse({"error": "فقط منبع شخصی خودتان قابل ویرایش است؛ منبع عمومی توسط مدیر سامانه اصلاح می‌شود."}, status=403)
    title = re.sub(r"\s+", " ", request.POST.get("title", "")).strip()
    if not title:
        return JsonResponse({"error": "نام منبع نمی‌تواند خالی باشد."}, status=400)
    source.title = title
    source.author_name = request.POST.get("author", source.author_name or "").strip()
    source.aliases = request.POST.get("aliases", source.aliases or "")
    source.save()
    return JsonResponse({"ok": True, "source": {"id": source.pk, "text": source.title, "title": source.title}})


def _public_researches():
    return Research.objects.filter(status="published", access_level="public").select_related("researcher", "content_kind", "source").prefetch_related("topic_analyses__topic", "occasions", "indexes__index_type", "indexes__index_value")


def public_home(request):
    qs = _public_researches()
    desired = ["آیات", "روایات", "تمثیل", "داستان", "سخن مشاهیر", "اشعار", "احکام", "ذکر مصیبت (روضه)", "اطلاعات و آمار علمی", "شبهه", "لطیفه"]
    kind_qs = IndexValue.objects.filter(index_type__slug="content-kind", is_active=True, visibility="global", approval_status="approved")
    by_title = {normalize_fa(x.title): x for x in kind_qs}
    kinds = [by_title.get(normalize_fa(title)) for title in desired]
    kinds = [x for x in kinds if x]
    topics = IndexValue.objects.filter(index_type__slug="subject", is_active=True, visibility="global", approval_status="approved").annotate(public_count=Count("topic_researches", filter=Q(topic_researches__research__status="published", topic_researches__research__access_level="public"))).order_by("-public_count", "title")[:10]
    featured = qs.filter(is_featured=True).order_by("featured_order", "-updated_at")[:8]
    if not featured.exists():
        featured = qs.order_by("-view_count", "-updated_at")[:8]
    story_popular = qs.filter(Q(content_kind__title__icontains="داستان") | Q(content_category__title__icontains="داستان")).order_by("-view_count", "-updated_at")[:8]
    weekly = qs.filter(occasions__isnull=False).distinct().order_by("-updated_at")[:8]
    return render(request, "public/home.html", {
        "featured": featured, "latest": qs.order_by("-updated_at")[:8],
        "popular": qs.order_by("-view_count", "-updated_at")[:8], "story_popular": story_popular,
        "weekly": weekly, "kinds": kinds, "topics": topics,
        "categories": IndexValue.objects.filter(index_type__slug="content-category", is_active=True),
        "formats": IndexValue.objects.filter(index_type__slug="main-format", is_active=True),
    })


def public_search(request):
    qs = _public_researches()
    q = request.GET.get("q", "").strip()
    scope = request.GET.get("scope", "all").strip()
    if scope not in {"all", "title", "topic", "body"}:
        scope = "all"
    kind = request.GET.get("kind", "").strip()
    category = request.GET.get("category", "").strip()
    main_format = request.GET.get("format", "").strip()
    sub_format = request.GET.get("subformat", "").strip()
    topic = request.GET.get("topic", "").strip()
    processing = request.GET.get("processing", "").strip()
    predicate = request.GET.get("predicate", "").strip()
    character = request.GET.get("character", "").strip()
    occasion = request.GET.get("occasion", "").strip()
    audience = request.GET.get("audience", "").strip()
    usage = request.GET.get("usage", "").strip()
    source_type = request.GET.get("source_type", "").strip()
    source = request.GET.get("source", "").strip()
    if q:
        normalized_q = normalize_fa(q)
        if scope == "title":
            if connection.vendor == "postgresql":
                qs = qs.annotate(title_similarity=TrigramSimilarity("title", q)).filter(
                    Q(title__icontains=q) | Q(title_similarity__gte=0.16)
                ).order_by("-title_similarity", "-updated_at")
            else:
                qs = qs.filter(title__icontains=q)
        elif scope == "topic":
            qs = qs.filter(
                Q(topic_analyses__topic__title__icontains=q)
                | Q(topic_analyses__topic__normalized_title__icontains=normalized_q)
            )
        elif scope == "body":
            qs = qs.filter(Q(body__icontains=q) | Q(abstract__icontains=q) | Q(search_keywords__icontains=q))
        elif connection.vendor == "postgresql":
            vector = (
                SearchVector("title", weight="A", config="simple")
                + SearchVector("abstract", weight="B", config="simple")
                + SearchVector("body", weight="C", config="simple")
                + SearchVector("search_keywords", weight="B", config="simple")
                + SearchVector("source__title", weight="B", config="simple")
                + SearchVector("source_note", weight="C", config="simple")
            )
            query = SearchQuery(q, config="simple", search_type="websearch")
            qs = qs.annotate(rank=SearchRank(vector, query), similarity=TrigramSimilarity("title", q)).filter(
                Q(rank__gte=0.005) | Q(similarity__gte=0.12) | Q(search_document_normalized__icontains=normalized_q)
                | Q(title__icontains=q) | Q(abstract__icontains=q) | Q(body__icontains=q)
                | Q(search_keywords__icontains=q) | Q(source__title__icontains=q)
                | Q(topic_analyses__topic__title__icontains=q) | Q(characters__title__icontains=q)
                | Q(secondary_characters__title__icontains=q)
            ).order_by("-rank", "-similarity", "-updated_at")
        else:
            qs = qs.filter(
                Q(search_document_normalized__icontains=normalized_q) | Q(title__icontains=q) | Q(abstract__icontains=q)
                | Q(body__icontains=q) | Q(search_keywords__icontains=q) | Q(source__title__icontains=q)
                | Q(topic_analyses__topic__title__icontains=q) | Q(characters__title__icontains=q)
                | Q(secondary_characters__title__icontains=q)
            )
    if kind:
        qs = qs.filter(content_kind_id=kind)
    if category:
        qs = qs.filter(content_category_id=category)
    if main_format:
        qs = qs.filter(main_format_id=main_format)
    if sub_format:
        qs = qs.filter(sub_format_id=sub_format)
    if topic:
        qs = qs.filter(topic_analyses__topic_id=topic)
    if processing:
        qs = qs.filter(topic_analyses__processing_keys__id=processing)
    if predicate:
        qs = qs.filter(topic_analyses__predicate_id=predicate)
    if character:
        qs = qs.filter(Q(characters__id=character) | Q(secondary_characters__id=character))
    if occasion:
        qs = qs.filter(occasions__id=occasion)
    if usage:
        qs = qs.filter(indexes__index_type__slug="promotional-usage", indexes__index_value_id=usage)
    if source_type:
        qs = qs.filter(source_type_id=source_type)
    if source:
        qs = qs.filter(source_id=source)
    if audience:
        qs = qs.annotate(_audience_text=Cast("audience_profiles", output_field=TextField())).filter(_audience_text__icontains=audience)
    qs = qs.distinct()
    paginator = Paginator(qs, 16)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_params = request.GET.copy(); page_params.pop("page", None)
    return render(request, "public/search.html", {
        "page_obj": page_obj, "results": page_obj.object_list, "count": paginator.count, "q": q, "scope": scope, "page_query": page_params.urlencode(),
        "kinds": IndexValue.objects.filter(index_type__slug="content-kind", is_active=True),
        "categories": IndexValue.objects.filter(index_type__slug="content-category", is_active=True),
        "formats": IndexValue.objects.filter(index_type__slug="main-format", is_active=True),
        "subformats": IndexValue.objects.filter(index_type__slug="content-subformat", is_active=True),
        "topics": IndexValue.objects.filter(index_type__slug="subject", is_active=True)[:700],
        "processing_keys": IndexValue.objects.filter(index_type__slug="processing-key", is_active=True),
        "predicates": IndexValue.objects.filter(index_type__slug="predicate", is_active=True),
        "characters": IndexValue.objects.filter(index_type__slug="main-character", is_active=True),
        "occasions": IndexValue.objects.filter(index_type__slug="occasion", is_active=True),
        "usages": IndexValue.objects.filter(index_type__slug="promotional-usage", is_active=True),
        "source_types": IndexValue.objects.filter(index_type__slug="source-type", is_active=True),
        "sources": Source.objects.filter(is_active=True),
        "params": request.GET,
    })


def public_research_detail(request, pk):
    research = get_object_or_404(_public_researches(), pk=pk)
    Research.objects.filter(pk=research.pk).update(view_count=F("view_count") + 1)
    research.view_count += 1
    usages = research.indexes.filter(index_type__slug="promotional-usage").select_related("index_value")
    related = _public_researches().filter(topic_analyses__topic__in=research.topic_analyses.values("topic")).exclude(pk=research.pk).distinct()[:4]
    bookmarked = request.user.is_authenticated and ResearchBookmark.objects.filter(user=request.user, research=research).exists()
    reaction_counts = dict(research.reactions.values_list("value").annotate(total=Count("id")))
    my_reaction = research.reactions.filter(user=request.user).values_list("value", flat=True).first() if request.user.is_authenticated else ""
    return render(request, "public/fish_detail.html", {"research": research, "usages": usages, "related": related, "bookmarked": bookmarked, "likes": reaction_counts.get("like", 0), "dislikes": reaction_counts.get("dislike", 0), "my_reaction": my_reaction, "report_reasons": ContentReport.REASONS})


@login_required
@require_POST
def public_reaction(request, pk):
    research = get_object_or_404(Research, pk=pk, status="published", access_level="public")
    value = request.POST.get("value")
    if value not in {"like", "dislike"}:
        return JsonResponse({"ok": False, "error": "بازخورد نامعتبر است."}, status=400)
    reaction, created = ResearchReaction.objects.get_or_create(research=research, user=request.user, defaults={"value": value})
    if not created and reaction.value == value:
        reaction.delete()
        selected = ""
    else:
        reaction.value = value
        reaction.save(update_fields=["value", "updated_at"])
        selected = value
    counts = dict(research.reactions.values_list("value").annotate(total=Count("id")))
    return JsonResponse({"ok": True, "selected": selected, "likes": counts.get("like", 0), "dislikes": counts.get("dislike", 0)})


@login_required
@require_POST
def public_report(request, pk):
    research = get_object_or_404(Research, pk=pk, status="published", access_level="public")
    reason = request.POST.get("reason")
    if reason not in dict(ContentReport.REASONS):
        messages.error(request, "نوع گزارش معتبر نیست.")
    else:
        recent = ContentReport.objects.filter(research=research, reporter=request.user, created_at__gte=timezone.now() - timedelta(hours=1)).exists()
        if recent:
            messages.warning(request, "گزارش شما قبلاً ثبت شده است.")
        else:
            ContentReport.objects.create(research=research, reporter=request.user, reason=reason, description=request.POST.get("description", "")[:1000])
            messages.success(request, "گزارش برای بررسی ثبت شد.")
    return redirect("public_research_detail", pk=pk)


def education_list(request):
    courses = EducationCourse.objects.filter(is_active=True).prefetch_related("lessons")
    return render(request, "public/education.html", {"courses": courses})


def education_lesson(request, pk):
    lesson = get_object_or_404(EducationLesson.objects.select_related("course"), pk=pk, is_active=True, course__is_active=True)
    return render(request, "public/education_lesson.html", {"lesson": lesson})


@login_required
@require_POST
def public_bookmark_toggle(request, pk):
    research = get_object_or_404(Research, pk=pk, status="published", access_level="public")
    bookmark = ResearchBookmark.objects.filter(user=request.user, research=research).first()
    if bookmark:
        bookmark.delete()
        messages.success(request, "فیش از ذخیره‌شده‌های شما حذف شد.")
    else:
        ResearchBookmark.objects.create(user=request.user, research=research)
        messages.success(request, "فیش در ذخیره‌شده‌های شما قرار گرفت.")
    next_url = request.POST.get("next") or reverse("public_research_detail", args=[research.pk])
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = reverse("public_research_detail", args=[research.pk])
    return redirect(next_url)


@login_required
def public_bookmarks(request):
    qs = _public_researches().filter(bookmarks__user=request.user).order_by("-bookmarks__created_at")
    paginator = Paginator(qs, 16)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "public/bookmarks.html", {"results": page_obj.object_list, "page_obj": page_obj, "count": paginator.count})


def public_about(request):
    return render(request, "public/info_page.html", {"page_key": "about", "title": "درباره ضحی آنلاین"})


def public_contact(request):
    return render(request, "public/info_page.html", {"page_key": "contact", "title": "تماس با ما", "public_email": settings.ZOHA_PUBLIC_EMAIL})


def public_help(request):
    return render(request, "public/info_page.html", {"page_key": "help", "title": "راهنمای استفاده و جست‌وجو"})


@login_required
def documentation(request):
    """راهنمای یک‌صفحه‌ای، قابل جست‌وجو و همگام با نسخه جاری محصول."""
    return render(request, "research/documentation.html", {"app_version": VERSION})


def public_faq(request):
    return render(request, "public/info_page.html", {"page_key": "faq", "title": "سؤالات متداول"})


def public_terms(request):
    return render(request, "public/info_page.html", {"page_key": "terms", "title": "قوانین استفاده"})


def public_privacy(request):
    return render(request, "public/info_page.html", {"page_key": "privacy", "title": "حریم خصوصی"})


def public_topics(request):
    rows = (IndexValue.objects.filter(index_type__slug="subject", is_active=True, visibility="global", approval_status="approved")
            .annotate(public_count=Count("topic_researches", filter=Q(topic_researches__research__status="published", topic_researches__research__access_level="public")))
            .order_by("-public_count", "title"))
    return render(request, "public/topics.html", {"topics": rows})


def public_channel(request):
    if settings.ZOHA_CHANNEL_URL:
        return redirect(settings.ZOHA_CHANNEL_URL)
    return render(request, "public/info_page.html", {"page_key": "channel", "title": "کانال ضحی", "channel_missing": True})


@require_POST
@login_required
def api_seo_suggest(request):
    body = request.POST.get("body", "")
    tags = suggest_seo_tags(body, user=request.user)
    return JsonResponse({"ok": True, "tags": tags})


@require_POST
@login_required
def research_generate_featured_image(request, pk):
    research = get_object_or_404(Research, pk=pk)
    if not can_edit(request.user, research):
        raise PermissionDenied
    try:
        url = generate_featured_image(research, user=request.user)
        return JsonResponse({"ok": True, "url": url})
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)


@login_required
def full_content_list(request):
    # ZOHA-W3.1-FULLCONTENT-LIST-FILTERS

    qs = (
        FullContent.objects
        .select_related(
            "owner",
            "topic",
            "author_owner",
        )
        .prefetch_related(
            "occasions"
        )
    )

    scope_mode = request.GET.get(
        "scope",
        "",
    ).strip()

    domain = request.GET.get(
        "domain",
        "",
    ).strip()

    status = request.GET.get(
        "status",
        "",
    ).strip()

    status_group = request.GET.get(
        "status_group",
        "",
    ).strip()


    if (
        scope_mode == "mine"
        or not is_admin(request.user)
    ):
        qs = qs.filter(
            owner=request.user
        )


    # ZOHA-W3.1.2-FULLCONTENT-CANONICAL-DOMAIN
    #
    # Every FullContent record belongs to the
    # "محتوای کامل" product domain.
    #
    # The legacy ?domain=full/complementary parameter
    # is intentionally ignored here. content_kind remains
    # available as the normal FullContent kind filter.


    if status:

        qs = qs.filter(
            status=status
        )

    elif status_group == "approved":

        qs = qs.filter(
            status__in=[
                "ready",
                "approved",
                "published",
            ]
        )

    elif status_group == "pending":

        qs = qs.filter(
            status__in=[
                "submitted",
                "in_review",
            ]
        )

    elif status_group == "changes":

        qs = qs.filter(
            status="changes_requested"
        )

    elif status_group == "rejected":

        qs = qs.filter(
            status="rejected"
        )


    q = request.GET.get(
        "q",
        "",
    ).strip()

    kind = request.GET.get(
        "kind",
        "",
    ).strip()


    if q:

        qs = qs.filter(
            Q(title__icontains=q)
            | Q(body__icontains=q)
            | Q(author_owner__title__icontains=q)
            | Q(topic__title__icontains=q)
        )


    if kind:

        qs = qs.filter(
            content_kind=kind
        )


    paginator = Paginator(
        qs.distinct().order_by(
            "-updated_at"
        ),
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get(
            "page"
        )
    )

    params = request.GET.copy()

    params.pop(
        "page",
        None,
    )


    return render(
        request,
        "research/full_content_list.html",
        {
            "items": page_obj.object_list,
            "page_obj": page_obj,
            "kinds": FullContent.KINDS,
            "q": q,
            "kind": kind,
            "domain": domain,
            "status": status,
            "status_group": status_group,
            "page_query": params.urlencode(),
        },
    )


@role_required("researcher", "admin")
@transaction.atomic
def full_content_create(request):
    form = FullContentForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.owner = request.user
        item.audience_profiles = form.cleaned_data.get("audience_text") or []
        item.presentation_date = form.cleaned_data.get("presentation_date_jalali")
        item.save(); form.save_m2m()
        # ZOHA-W2.3-FULLCONTENT-EDIT:START
        segments, references = enrich_semantic_text(
            item.body,
            user=request.user,
        )
        item.ai_segments = segments
        item.external_references = references
        item.save(
            update_fields=[
                "ai_segments",
                "external_references",
                "updated_at",
            ]
        )
        # ZOHA-W2.3-FULLCONTENT-CREATE:START
        segments, references = enrich_semantic_text(
            item.body,
            user=request.user,
        )
        item.ai_segments = segments
        item.external_references = references
        item.save(
            update_fields=[
                "ai_segments",
                "external_references",
                "updated_at",
            ]
        )
        messages.success(request, "محتوای کامل با موفقیت ثبت شد.")
        return redirect("full_content_detail", pk=item.pk)
    return render(request, "research/full_content_form.html", {"form": form, "item": None})


@login_required
@transaction.atomic
def full_content_edit(request, pk):
    item = get_object_or_404(FullContent, pk=pk)
    if not (is_admin(request.user) or item.owner_id == request.user.id):
        raise PermissionDenied
    form = FullContentForm(request.POST or None, request.FILES or None, instance=item, user=request.user)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.audience_profiles = form.cleaned_data.get("audience_text") or []
        item.presentation_date = form.cleaned_data.get("presentation_date_jalali")
        item.save(); form.save_m2m()
        messages.success(request, "محتوای کامل به‌روزرسانی شد.")
        return redirect("full_content_detail", pk=item.pk)
    return render(request, "research/full_content_form.html", {"form": form, "item": item})


@login_required
def full_content_detail(request, pk):
    item = get_object_or_404(FullContent.objects.select_related("owner", "topic", "predicate", "author_owner", "presentation_place").prefetch_related("processing_keys", "characters", "occasions"), pk=pk)
    if not (is_admin(request.user) or item.owner_id == request.user.id):
        raise PermissionDenied
    return render(request, "research/full_content_detail.html", {"item": item, "presentation_date_jalali": format_jalali(item.presentation_date)})


@role_required("researcher", "admin")
@transaction.atomic
def custom_collections(request):
    qs = CustomCollection.objects.filter(owner=request.user).select_related("parent").order_by("order", "title")
    if request.method == "POST":
        action = request.POST.get("action", "create")
        title = re.sub(r"\s+", " ", request.POST.get("title", "")).strip()
        collection_id = request.POST.get("collection_id")
        parent_id = request.POST.get("parent_id") or None
        parent = get_object_or_404(qs, pk=parent_id) if parent_id else None
        if action == "create":
            if not title:
                messages.error(request, "عنوان دسته‌بندی اختصاصی را وارد کنید.")
            elif qs.filter(title=title, parent=parent).exists():
                messages.warning(request, "دسته‌بندی‌ای با این عنوان از قبل وجود دارد.")
            else:
                CustomCollection.objects.create(owner=request.user, parent=parent, title=title, description=request.POST.get("description", "").strip())
                messages.success(request, "دسته‌بندی اختصاصی ایجاد شد.")
        else:
            collection = get_object_or_404(qs, pk=collection_id)
            if action == "edit":
                if not title:
                    messages.error(request, "عنوان دسته‌بندی نمی‌تواند خالی باشد.")
                elif parent and (parent.pk == collection.pk or parent.parent_id == collection.pk):
                    messages.error(request, "ساختار درختی انتخاب‌شده باعث حلقه می‌شود.")
                elif qs.filter(title=title, parent=parent).exclude(pk=collection.pk).exists():
                    messages.warning(request, "دسته‌بندی دیگری با این عنوان وجود دارد.")
                else:
                    collection.title = title
                    collection.description = request.POST.get("description", "").strip()
                    collection.parent = parent
                    collection.save(update_fields=["title", "description", "parent", "updated_at"])
                    messages.success(request, "دسته‌بندی اختصاصی ویرایش شد.")
            elif action == "toggle":
                collection.is_active = not collection.is_active
                collection.save(update_fields=["is_active", "updated_at"])
                messages.success(request, "وضعیت دسته‌بندی تغییر کرد.")
            elif action == "delete":
                if collection.researches.exists() or collection.children.exists():
                    messages.error(request, "دسته دارای فیش یا زیردسته است و قابل حذف نیست؛ ابتدا آن‌ها را منتقل کنید.")
                else:
                    collection.delete()
                    messages.success(request, "دسته‌بندی حذف شد.")
        return redirect("custom_collections")
    rows = qs.annotate(research_count=Count("researches"), child_count=Count("children", distinct=True))
    return render(request, "research/custom_collections.html", {"collections": rows, "parent_choices": qs.filter(is_active=True)})


@login_required
def advanced_search(request):
    qs = (
        Research.objects.visible_to(request.user)
        .select_related("researcher", "content_kind", "main_format", "team", "source")
        .prefetch_related("topic_analyses__topic")
    )

    project = None
    project_id = request.GET.get("project")
    if project_id:
        project_qs = PromotionProject.objects.select_related("owner", "sermon_style")
        if not is_admin(request.user):
            project_qs = project_qs.filter(owner=request.user)
        project = get_object_or_404(project_qs, pk=project_id, is_active=True)

    query = request.GET.get("q", "").strip()
    word_mode = request.GET.get("word_mode", "all")
    fields = request.GET.getlist("q_fields") or ["body", "abstract"]
    if query:
        if connection.vendor == "postgresql":
            qs = _postgres_text_search(qs, query, fields, word_mode)
        else:
            qs = _legacy_text_search(qs, query, fields, word_mode)

    type_ids = request.GET.getlist("filter_type")
    value_ids = request.GET.getlist("filter_value")
    pairs = []
    for type_id, value_id in zip(type_ids, value_ids):
        if not type_id or not value_id:
            continue
        index_type = IndexType.objects.filter(pk=type_id, is_active=True).first()
        value = IndexValue.objects.filter(pk=value_id, index_type=index_type).first() if index_type else None
        if index_type and value:
            pairs.append((index_type, value))
    match_mode = request.GET.get("index_match", "all")
    if pairs and match_mode == "any":
        combined = Q()
        for index_type, value in pairs:
            combined |= index_q(index_type.slug, value.pk)
        qs = qs.filter(combined)
    else:
        for index_type, value in pairs:
            qs = apply_index_filter(qs, index_type.slug, value.pk)

    researcher = request.GET.get("researcher")
    status = request.GET.get("status")
    if researcher:
        qs = qs.filter(researcher_id=researcher)
    if status and is_admin(request.user):
        qs = qs.filter(status=status)

    if not query or connection.vendor != "postgresql":
        qs = qs.order_by("-updated_at")
    qs = qs.distinct()
    count = qs.count()

    selected_filters = [{"type_id": t.pk, "type": t.name, "value_id": v.pk, "value": v.title} for t, v in pairs]
    if request.GET:
        SearchLog.objects.create(
            user=request.user,
            query=query,
            filters={"word_mode": word_mode, "fields": fields, "indexes": selected_filters, "match": match_mode, "project": project_id},
            result_count=count,
        )

    result_subquery = qs.order_by().values("pk")
    topic_facets = list(
        TopicAnalysis.objects.filter(research_id__in=result_subquery)
        .values("topic_id", "topic__title")
        .annotate(total=Count("research_id", distinct=True))
        .order_by("-total", "topic__title")[:12]
    )
    kind_facets = list(
        Research.objects.filter(id__in=result_subquery).exclude(content_kind__isnull=True)
        .values("content_kind_id", "content_kind__title")
        .annotate(total=Count("id"))
        .order_by("-total", "content_kind__title")[:12]
    )

    paginator = Paginator(qs, 24)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_params = request.GET.copy()
    page_params.pop("page", None)
    page_query = page_params.urlencode()
    subject_type_id = IndexType.objects.filter(slug="subject", is_active=True).values_list("id", flat=True).first()
    content_kind_type_id = IndexType.objects.filter(slug="content-kind", is_active=True).values_list("id", flat=True).first()
    project_research_ids = set()
    if project:
        project_research_ids = set(project.project_researches.values_list("research_id", flat=True))

    return render(request, "research/search.html", {
        "results": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "count": count,
        "search_backend": "postgresql" if connection.vendor == "postgresql" else "fallback",
        "page_query": page_query,
        "subject_type_id": subject_type_id,
        "content_kind_type_id": content_kind_type_id,
        "index_types": IndexType.objects.filter(is_active=True).order_by("order"),
        "researchers": User.objects.filter(roles__slug="researcher", is_enabled=True).distinct(),
        "params": request.GET,
        "selected_filters": selected_filters,
        "selected_fields": fields,
        "word_mode": word_mode,
        "match_mode": match_mode,
        "topic_facets": topic_facets,
        "kind_facets": kind_facets,
        "status_choices": Research.STATUS,
        "project": project,
        "project_research_ids": project_research_ids,
        "supplementary_open": bool(researcher or status),
    })

@role_required("admin")
def option_management(request):
    query = request.GET.get("q", "").strip()
    type_id = request.GET.get("type")
    state = request.GET.get("state", "pending")
    options = IndexValue.objects.select_related("index_type", "owner", "merged_into")
    sources = Source.objects.select_related("owner", "merged_into")
    if state == "pending":
        options = options.filter(approval_status="pending")
        sources = sources.filter(approval_status="pending")
    elif state == "inactive":
        options = options.filter(is_active=False)
        sources = sources.filter(is_active=False)
    elif state == "private":
        options = options.filter(visibility="private")
        sources = sources.filter(visibility="private")
    if type_id:
        options = options.filter(index_type_id=type_id)
        sources = sources.none()
    if query:
        options = options.filter(Q(title__icontains=query) | Q(aliases__icontains=query))
        sources = sources.filter(Q(title__icontains=query) | Q(author_name__icontains=query) | Q(aliases__icontains=query))
    return render(request, "research/option_management.html", {
        "options": options[:300], "sources": sources[:200],
        "index_types": IndexType.objects.filter(is_active=True),
        "state": state, "q": query, "type_id": type_id,
        "audit_logs": OptionAuditLog.objects.select_related("actor", "option", "source")[:30],
    })


@role_required("admin")
@require_POST
@transaction.atomic
def option_action(request, pk):
    option = get_object_or_404(IndexValue, pk=pk)
    action = request.POST.get("action")
    details = {}
    if action == "approve":
        option.visibility = "global"; option.approval_status = "approved"; option.is_active = True
        option.save(update_fields=["visibility", "approval_status", "is_active", "updated_at"])
        log_action = "approved"
    elif action == "reject":
        option.approval_status = "rejected"; option.is_active = False
        option.save(update_fields=["approval_status", "is_active", "updated_at"])
        log_action = "rejected"
    elif action == "deactivate":
        option.is_active = False; option.save(update_fields=["is_active", "updated_at"]); log_action = "deactivated"
    elif action == "activate":
        option.is_active = True; option.save(update_fields=["is_active", "updated_at"]); log_action = "activated"
    elif action == "merge":
        target = get_object_or_404(IndexValue, pk=request.POST.get("target_id"), index_type=option.index_type, is_active=True)
        if target.pk == option.pk:
            messages.error(request, "گزینه مقصد نمی‌تواند همان گزینه فعلی باشد.")
            return redirect("option_management")
        merge_option(option, target)
        details = {"target_id": target.pk, "target_title": target.title}
        log_action = "merged"
    else:
        return HttpResponseBadRequest("عملیات نامعتبر")
    OptionAuditLog.objects.create(option=option, actor=request.user, action=log_action, details=details)
    messages.success(request, "عملیات گزینه با موفقیت انجام شد.")
    return redirect(request.META.get("HTTP_REFERER") or "option_management")


def merge_option(old, target):
    """Merge a duplicate option without breaking unique topic analyses."""
    research_fields = ["content_kind", "content_category", "main_format", "sub_format", "source_type"]
    for field in research_fields:
        Research.objects.filter(**{field: old}).update(**{field: target})

    # Generic indexes may already contain the destination value on the same fish/type.
    for item in list(ResearchIndex.objects.filter(index_value=old).select_related("research", "index_type")):
        duplicate = ResearchIndex.objects.filter(
            research=item.research, index_type=item.index_type, index_value=target
        ).exclude(pk=item.pk).first()
        if duplicate:
            if item.source_excerpt and not duplicate.source_excerpt:
                duplicate.source_excerpt = item.source_excerpt
                duplicate.save(update_fields=["source_excerpt", "updated_at"])
            item.delete()
        else:
            item.index_value = target
            item.save(update_fields=["index_value", "updated_at"])

    # When both old and target topics exist on a fish, merge their analytical content.
    for analysis in list(TopicAnalysis.objects.filter(topic=old).prefetch_related("processing_keys")):
        existing = TopicAnalysis.objects.filter(research=analysis.research, topic=target).exclude(pk=analysis.pk).first()
        if existing:
            existing.processing_keys.add(*analysis.processing_keys.all())
            if not existing.predicate_id and analysis.predicate_id:
                existing.predicate = analysis.predicate
            if not existing.predicate_text and analysis.predicate_text:
                existing.predicate_text = analysis.predicate_text
            if analysis.author_interpretation and analysis.author_interpretation not in existing.author_interpretation:
                existing.author_interpretation = "\n\n".join(filter(None, [existing.author_interpretation, analysis.author_interpretation]))
            existing.save(update_fields=["predicate", "predicate_text", "author_interpretation", "updated_at"])
            analysis.delete()
        else:
            analysis.topic = target
            analysis.save(update_fields=["topic", "updated_at"])

    TopicAnalysis.objects.filter(predicate=old).update(predicate=target)
    for research in list(old.character_researches.all()):
        research.characters.add(target)
        research.characters.remove(old)
    for research in list(old.occasion_researches.all()):
        research.occasions.add(target)
        research.occasions.remove(old)
    for analysis in list(old.processing_key_analyses.all()):
        analysis.processing_keys.add(target)
        analysis.processing_keys.remove(old)

    old.children.update(parent=target)
    old.merged_into = target
    old.is_active = False
    old.save(update_fields=["merged_into", "is_active", "updated_at"])


@role_required("admin")
@require_POST
@transaction.atomic
def source_action(request, pk):
    source = get_object_or_404(Source, pk=pk)
    action = request.POST.get("action")
    details = {}
    if action == "approve":
        source.visibility = "global"; source.approval_status = "approved"; source.is_active = True; log_action = "approved"
    elif action == "reject":
        source.approval_status = "rejected"; source.is_active = False; log_action = "rejected"
    elif action == "deactivate":
        source.is_active = False; log_action = "deactivated"
    elif action == "activate":
        source.is_active = True; log_action = "activated"
    elif action == "merge":
        target = get_object_or_404(Source, pk=request.POST.get("target_id"), is_active=True)
        if target.pk == source.pk:
            messages.error(request, "منبع مقصد نمی‌تواند همان منبع فعلی باشد.")
            return redirect("option_management")
        Research.objects.filter(source=source).update(source=target)
        source.merged_into = target; source.is_active = False
        details = {"target_id": target.pk, "target_title": target.title}; log_action = "merged"
    else:
        return HttpResponseBadRequest("عملیات نامعتبر")
    source.save()
    OptionAuditLog.objects.create(source=source, actor=request.user, action=log_action, details=details)
    messages.success(request, "عملیات منبع انجام شد.")
    return redirect(request.META.get("HTTP_REFERER") or "option_management")


@role_required("reviewer", "admin")
def review_tasks(request):
    qs = ReviewTask.objects.select_related("research", "reviewer", "scope")
    if not is_admin(request.user):
        qs = qs.filter(reviewer=request.user)
    return render(request, "research/review_tasks.html", {"tasks": qs})


@role_required("reviewer", "admin")
def review_detail(request, task_id):
    task = get_object_or_404(ReviewTask.objects.select_related("research", "reviewer", "scope"), pk=task_id)
    if not is_admin(request.user) and task.reviewer_id != request.user.id:
        raise PermissionDenied
    if task.status == "pending":
        task.status = "in_review"; task.started_at = timezone.now(); task.save(update_fields=["status", "started_at", "updated_at"])
        if task.research.status == "submitted":
            task.research.transition_to("in_review")
    form = ReviewCommentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        comment = form.save(commit=False)
        comment.task = task; comment.research = task.research; comment.author = request.user; comment.save()
        event_and_notify(task.research, request.user, "commented", "یک نکته ارزیابی جدید ثبت شد.", [task.research.researcher])
        messages.success(request, "نظر ارزیابی ثبت شد.")
        return redirect("review_detail", task_id=task.pk)
    return render(request, "research/review_detail.html", {"task": task, "form": form, "comments": task.comments.select_related("author", "index_type")})


@role_required("reviewer", "admin")
@require_POST
def review_action(request, task_id, action):
    task = get_object_or_404(ReviewTask.objects.select_related("research"), pk=task_id)
    if not is_admin(request.user) and task.reviewer_id != request.user.id:
        raise PermissionDenied
    if action == "publish" and not is_admin(request.user):
        raise PermissionDenied
    research = task.research
    note = request.POST.get("note", "").strip()
    now = timezone.now()
    if action == "changes":
        task.status = "changes_requested"; research.transition_to("changes_requested", save=False)
        event_type = "changes_requested"; message = "فیش برای اصلاح به فیش‌نگار بازگردانده شد."
    elif action == "reject":
        task.status = "rejected"; research.transition_to("rejected", save=False)
        event_type = "rejected"; message = "فیش رد شد."
    elif action == "publish":
        task.status = "approved"; research.transition_to("published", save=False)
        research.access_level = "public"; research.team = None; research.approved_at = now
        event_type = "published"; message = "فیش منتشر شد."
    else:
        task.status = "approved"; event_type = "approved"; message = "بخش ارزیابی تأیید شد."
    task.completed_at = now
    task.save(update_fields=["status", "completed_at", "updated_at"])
    if action == "approve" and not research.review_tasks.filter(round=research.current_round).exclude(status="approved").exists():
        research.transition_to("approved", save=False); research.approved_at = now
        message = "تمام ارزیابی‌ها تأیید و فیش نهایی شد."
    research.save()
    event_and_notify(research, request.user, event_type, message + ((" " + note) if note else ""), [research.researcher])
    messages.success(request, message)
    return redirect("review_detail", task_id=task.pk)


@login_required
@require_POST
def resolve_comment(request, comment_id):
    comment = get_object_or_404(ReviewComment.objects.select_related("research"), pk=comment_id)
    if not (can_edit(request.user, comment.research) or is_admin(request.user)):
        raise PermissionDenied
    comment.resolution = "resolved"; comment.resolved_by = request.user; comment.resolved_at = timezone.now()
    comment.save(update_fields=["resolution", "resolved_by", "resolved_at", "updated_at"])
    messages.success(request, "نکته به‌عنوان رفع‌شده علامت خورد.")
    return redirect("research_detail", pk=comment.research_id)


@login_required
def notifications(request):
    return render(request, "research/notifications.html", {"notifications": request.user.zoha_notifications.select_related("research")[:200]})


@login_required
def notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_read()
    return redirect(notification.url or "notifications")


@role_required("admin")
def reports(request):
    researchers = User.objects.filter(roles__slug="researcher").annotate(
        total=Count("researches"),
        approved=Count("researches", filter=Q(researches__status__in=["approved", "published"])),
        returned=Count("researches", filter=Q(researches__status="changes_requested")),
    ).order_by("-total")
    reviewers = User.objects.filter(roles__slug="reviewer").annotate(
        total=Count("review_tasks"),
        approved=Count("review_tasks", filter=Q(review_tasks__status="approved")),
        returned=Count("review_tasks", filter=Q(review_tasks__status="changes_requested")),
    ).order_by("-total")
    top_topics = TopicAnalysis.objects.values("topic__title").annotate(total=Count("id")).order_by("-total")[:20]
    top_keys = TopicAnalysis.objects.values("processing_keys__title").annotate(total=Count("id")).order_by("-total")[:20]
    return render(request, "research/reports.html", {
        "researchers": researchers, "reviewers": reviewers,
        "status_stats": Research.objects.values("status").annotate(total=Count("id")).order_by("-total"),
        "top_topics": top_topics, "top_keys": top_keys,
        "avg_words": round(sum(r.word_count for r in Research.objects.only("body")) / max(Research.objects.count(), 1)),
        "search_count": SearchLog.objects.count(),
    })


@role_required("admin")
def assignments(request):
    form = AssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save(); messages.success(request, "تخصیص ارزیاب ذخیره شد."); return redirect("assignments")
    return render(request, "research/assignments.html", {"form": form, "items": ReviewerAssignment.objects.select_related("researcher", "reviewer", "scope")})


@role_required("admin")
@require_POST
def assignment_delete(request, pk):
    get_object_or_404(ReviewerAssignment, pk=pk).delete()
    messages.success(request, "تخصیص حذف شد.")
    return redirect("assignments")


@login_required
def sermon_style_management(request):
    if not is_admin(request.user):
        raise PermissionDenied
    edit_id = request.GET.get("edit") or request.POST.get("style_id")
    instance = SermonStyle.objects.filter(pk=edit_id).first() if edit_id else None
    form = SermonStyleForm(request.POST or None, instance=instance)
    if request.method == "POST" and request.POST.get("action") == "save_style" and form.is_valid():
        style = form.save()
        messages.success(request, f"سبک منبر «{style.name}» ذخیره شد.")
        return redirect("sermon_style_management")
    return render(request, "research/sermon_style_management.html", {
        "form": form,
        "editing_style": instance,
        "styles": SermonStyle.objects.annotate(project_count=Count("projects")).order_by("order", "name"),
    })


@login_required
@require_POST
def sermon_style_toggle(request, pk):
    if not is_admin(request.user):
        raise PermissionDenied
    style = get_object_or_404(SermonStyle, pk=pk)
    action = request.POST.get("action")
    if action == "default":
        style.is_default = True
        style.is_active = True
        style.save(update_fields=["is_default", "is_active", "updated_at"])
        messages.success(request, f"«{style.name}» سبک پیش‌فرض شد.")
    elif action == "toggle":
        style.is_active = not style.is_active
        if not style.is_active:
            style.is_default = False
        style.save(update_fields=["is_active", "is_default", "updated_at"])
        messages.success(request, "وضعیت سبک تغییر کرد.")
    return redirect("sermon_style_management")


def _project_queryset_for(user):
    qs = PromotionProject.objects.select_related("owner", "sermon_style")
    return qs if is_admin(user) else qs.filter(owner=user)




def project_form_context(request, form, project=None):
    job_values = list(
        IndexValue.objects.visible_to(request.user)
        .filter(index_type__slug="audience-job")
        .values("id", "title", "visibility")
        .order_by("title")
    )
    raw_audiences = form["audiences_json"].value() or "[]"
    if isinstance(raw_audiences, str):
        try:
            parsed_audiences = json.loads(raw_audiences)
        except (TypeError, json.JSONDecodeError):
            parsed_audiences = []
    else:
        parsed_audiences = raw_audiences if isinstance(raw_audiences, list) else []
    return {
        "form": form,
        "project": project,
        "project_items": project.project_researches.select_related(
            "research", "research__researcher", "research__content_kind", "added_by"
        ) if project else [],
        "project_indexes": project.indexes.select_related("index_type") if project else [],
        "index_types": IndexType.objects.filter(is_active=True).order_by("order"),
        "available_project_index_values": IndexValue.objects.visible_to(request.user)
            .select_related("index_type").order_by("index_type__order", "title"),
        "project_audience_jobs": job_values,
        "existing_project_audiences": parsed_audiences,
    }

def _active_ai_endpoints():
    stale_cutoff = timezone.now() - timedelta(hours=2)
    return AIEndpointStatus.objects.filter(
        status="active",
        last_checked_at__gte=stale_cutoff,
    ).order_by("provider_name", "model_name")


@login_required
def project_list(request):
    projects = _project_queryset_for(request.user).annotate(total_researches=Count("project_researches"))
    return render(request, "research/project_list.html", {"projects": projects})


@login_required
@transaction.atomic
def project_create(request):
    form = PromotionProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        messages.success(request, "پروژه تبلیغی ایجاد شد.")
        return redirect("project_edit", pk=project.pk)
    return render(request, "research/project_edit.html", project_form_context(request, form, None))


@login_required
@transaction.atomic
def project_edit(request, pk):
    project = get_object_or_404(_project_queryset_for(request.user), pk=pk)
    form = PromotionProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and request.POST.get("action") == "save_project" and form.is_valid():
        form.save()
        messages.success(request, "اطلاعات پروژه ذخیره شد.")
        return redirect("project_edit", pk=project.pk)
    return render(request, "research/project_edit.html", project_form_context(request, form, project))


@login_required
@require_POST
@transaction.atomic
def project_add_researches(request, pk):
    project = get_object_or_404(_project_queryset_for(request.user), pk=pk, is_active=True)
    research_ids = [x for x in request.POST.getlist("research_ids") if x]
    allowed = []
    for research in Research.objects.filter(pk__in=research_ids):
        if can_view(request.user, research):
            allowed.append(research)
    created = 0
    for research in allowed:
        _, was_created = ProjectResearch.objects.get_or_create(
            project=project,
            research=research,
            defaults={"added_by": request.user},
        )
        created += int(was_created)
    if created:
        messages.success(request, f"{created} فیش به پروژه «{project.title}» اضافه شد.")
    else:
        messages.info(request, "فیش تازه‌ای برای افزودن انتخاب نشده بود.")
    fallback_url = reverse("project_edit", kwargs={"pk": project.pk})
    next_url = request.POST.get("next") or fallback_url
    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = fallback_url
    return redirect(next_url)


@login_required
@require_POST
def project_remove_research(request, pk, link_id):
    project = get_object_or_404(_project_queryset_for(request.user), pk=pk)
    link = get_object_or_404(ProjectResearch, pk=link_id, project=project)
    link.delete()
    messages.success(request, "فیش از پروژه حذف شد.")
    return redirect("project_edit", pk=project.pk)


@login_required
@require_POST
def project_index_add(request, pk):
    project = get_object_or_404(_project_queryset_for(request.user), pk=pk)
    value = get_object_or_404(IndexValue.objects.visible_to(request.user), pk=request.POST.get("value_id"))
    project.indexes.add(value)
    messages.success(request, "نمایه به پروژه افزوده شد.")
    return redirect("project_edit", pk=project.pk)


@login_required
@require_POST
def project_index_remove(request, pk, value_id):
    project = get_object_or_404(_project_queryset_for(request.user), pk=pk)
    value = get_object_or_404(IndexValue, pk=value_id)
    project.indexes.remove(value)
    messages.success(request, "نمایه از پروژه حذف شد.")
    return redirect("project_edit", pk=project.pk)


@login_required
def ai_provider_status(request):
    endpoints = AIEndpointStatus.objects.all()
    active = endpoints.filter(status="active")
    return render(request, "research/ai_provider_status.html", {
        "endpoints": endpoints[:1000],
        "active_count": active.count(),
        "inactive_count": endpoints.filter(status="inactive").count(),
        "skipped_count": endpoints.filter(status="skipped").count(),
        "last_run": AIProbeRun.objects.first(),
    })


def _parse_ai_json(text):
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    if start < 0:
        raise ValueError("پاسخ هوش مصنوعی شامل JSON معتبر نیست.")
    decoder = json.JSONDecoder()
    payload, _ = decoder.raw_decode(cleaned[start:])
    if not isinstance(payload, dict):
        raise ValueError("ساختار خروجی نمایه‌زنی باید یک شیء JSON باشد.")
    return payload


def _suggestion_text(value):
    if isinstance(value, dict):
        for key in ("title", "name", "topic", "label", "value", "text"):
            if value.get(key):
                return str(value[key]).strip()
        return json.dumps(value, ensure_ascii=False)
    return str(value or "").strip()


def _best_index_match(user, slug, label):
    label = _suggestion_text(label)
    if not label:
        return None
    qs = IndexValue.objects.visible_to(user).filter(index_type__slug=slug)
    normalized = normalize_fa(label)
    exact = qs.filter(normalized_title=normalized).first()
    if exact:
        return {"id": exact.pk, "title": exact.title, "score": 1.0}
    if connection.vendor == "postgresql":
        candidate = qs.annotate(similarity=TrigramSimilarity("title", label)).order_by("-similarity").first()
        if candidate and (candidate.similarity or 0) >= 0.30:
            return {"id": candidate.pk, "title": candidate.title, "score": round(float(candidate.similarity), 3)}
        return None
    best = None
    best_score = 0.0
    for candidate in qs.only("id", "title")[:800]:
        score = similarity_score(label, candidate.title)
        if score > best_score:
            best, best_score = candidate, score
    if best and best_score >= 0.72:
        return {"id": best.pk, "title": best.title, "score": round(best_score, 3)}
    return None


def _create_ai_index_suggestions(run, payload, user):
    suggestions = []
    topics = payload.get("topics") or []
    for row in topics[:20]:
        row = row if isinstance(row, dict) else {"topic": _suggestion_text(row)}
        topic_label = _suggestion_text(row.get("topic") or row.get("title") or row)
        processing = row.get("processing_keys") or row.get("processingKeys") or []
        if isinstance(processing, str):
            processing = [processing]
        predicate = row.get("predicate") or ""
        match_data = {
            "topic": _best_index_match(user, "subject", topic_label),
            "processing_keys": [m for m in (_best_index_match(user, "processing-key", x) for x in processing) if m],
            "predicate": _best_index_match(user, "predicate", predicate),
        }
        suggestions.append(AIIndexSuggestion(
            run=run,
            kind="topic_analysis",
            label=topic_label or "تحلیل موضوعی",
            payload={
                "topic": topic_label,
                "processing_keys": [_suggestion_text(x) for x in processing if _suggestion_text(x)],
                "predicate": _suggestion_text(predicate),
                "interpretation": _suggestion_text(row.get("interpretation") or row.get("author_interpretation")),
            },
            match_data=match_data,
        ))

    for key, kind, slug in (
        ("characters", "character", "main-character"),
        ("occasions", "occasion", "occasion"),
    ):
        for value in (payload.get(key) or [])[:30]:
            label = _suggestion_text(value)
            if label:
                suggestions.append(AIIndexSuggestion(
                    run=run, kind=kind, label=label,
                    payload={"value": label},
                    match_data={"value": _best_index_match(user, slug, label)},
                ))

    for value in (payload.get("audiences") or [])[:20]:
        label = _suggestion_text(value)
        if label:
            suggestions.append(AIIndexSuggestion(
                run=run, kind="audience", label=label,
                payload=value if isinstance(value, dict) else {"value": label},
            ))

    for value in (payload.get("keywords") or [])[:40]:
        label = _suggestion_text(value)
        if label:
            suggestions.append(AIIndexSuggestion(
                run=run, kind="keyword", label=label, payload={"value": label},
            ))

    if suggestions:
        AIIndexSuggestion.objects.bulk_create(suggestions)


@login_required
def ai_indexing(request, pk):
    research = get_object_or_404(Research.objects.select_related("researcher"), pk=pk)
    if not can_edit(request.user, research):
        raise PermissionDenied
    endpoints = _active_ai_endpoints()
    error = ""
    selected_endpoint = request.POST.get("endpoint") or request.GET.get("endpoint")

    if request.method == "POST" and request.POST.get("action", "generate") == "generate":
        endpoint = get_object_or_404(endpoints, pk=selected_endpoint)
        prompt = (
            "شما دستیار نمایه‌زنی فیش‌های تبلیغی دینی هستید. فقط بر اساس متن داده‌شده پیشنهاد بدهید و چیزی جعل نکنید. "
            "فقط JSON معتبر با این ساختار برگردانید: "
            '{"topics":[{"topic":"...","processing_keys":["..."],"predicate":"...","interpretation":"..."}],'
            '"characters":["..."],"occasions":["..."],"audiences":[{"needs":"...","notes":"..."}],"keywords":["..."]}. '
            "نام موضوع، کلید پردازش، محمول، شخصیت و مناسبت را تا حد ممکن مطابق واژگان رایج و کوتاه پیشنهاد کنید.\n\n"
            f"عنوان: {research.title}\nخلاصه: {research.abstract}\nمتن: {re.sub('<[^>]+>', ' ', research.body)[:18000]}"
        )
        log = AIGenerationLog.objects.create(
            user=request.user, endpoint=endpoint, research=research,
            task_type="indexing", prompt=prompt,
        )
        try:
            from .ai_services import run_completion
            output = run_completion(endpoint, [{"role": "user", "content": prompt}], timeout=60)
            payload = _parse_ai_json(output)
            log.response = output
            log.succeeded = True
            log.save(update_fields=["response", "succeeded"])
            run = AIIndexingRun.objects.create(
                research=research, user=request.user, endpoint=endpoint,
                generation_log=log, raw_response=output, parsed_payload=payload,
            )
            _create_ai_index_suggestions(run, payload, request.user)
            messages.success(request, "پیشنهادهای هوش مصنوعی تولید شدند؛ هر مورد را بررسی و تأیید یا رد کنید.")
            return redirect(f"{reverse('ai_indexing', kwargs={'pk': research.pk})}?run={run.pk}")
        except Exception as exc:
            error = f"{exc.__class__.__name__}: {exc}"
            log.error = error
            log.save(update_fields=["error"])

    run_id = request.GET.get("run")
    runs = research.ai_indexing_runs.select_related("endpoint", "user")[:20]
    current_run = (
        research.ai_indexing_runs.filter(pk=int(run_id)).first()
        if run_id and run_id.isdigit()
        else research.ai_indexing_runs.first()
    )
    suggestions = current_run.suggestions.all() if current_run else []
    accepted_count = current_run.suggestions.filter(decision="accepted").count() if current_run else 0
    rejected_count = current_run.suggestions.filter(decision="rejected").count() if current_run else 0
    pending_count = current_run.suggestions.filter(decision="pending").count() if current_run else 0
    return render(request, "research/ai_indexing.html", {
        "research": research,
        "endpoints": endpoints,
        "selected_endpoint": selected_endpoint,
        "error": error,
        "runs": runs,
        "current_run": current_run,
        "suggestions": suggestions,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "pending_count": pending_count,
    })


@login_required
@require_POST
def ai_indexing_decision(request, run_id, suggestion_id, decision):
    if decision not in {"accepted", "rejected", "pending"}:
        return HttpResponseBadRequest("تصمیم نامعتبر است")
    run = get_object_or_404(AIIndexingRun.objects.select_related("research"), pk=run_id)
    if not can_edit(request.user, run.research) or run.status != "review":
        raise PermissionDenied
    suggestion = get_object_or_404(AIIndexSuggestion, pk=suggestion_id, run=run)
    suggestion.decision = decision
    suggestion.decided_by = request.user if decision != "pending" else None
    suggestion.decided_at = timezone.now() if decision != "pending" else None
    suggestion.save(update_fields=["decision", "decided_by", "decided_at", "updated_at"])
    return redirect(f"{reverse('ai_indexing', kwargs={'pk': run.research_id})}?run={run.pk}")


@login_required
@require_POST
@transaction.atomic
def ai_indexing_apply(request, run_id):
    run = get_object_or_404(AIIndexingRun.objects.select_related("research"), pk=run_id)
    research = run.research
    if not can_edit(request.user, research) or run.status != "review":
        raise PermissionDenied

    applied = 0
    skipped = 0
    audiences = list(research.audience_profiles or [])
    keyword_map = {normalize_fa(x): x for x in re.split(r"[,،\n]+", research.search_keywords or "") if x.strip()}

    for suggestion in run.suggestions.filter(decision="accepted"):
        match = suggestion.match_data or {}
        payload = suggestion.payload or {}
        if suggestion.kind == "topic_analysis":
            topic_match = match.get("topic") or {}
            if not topic_match.get("id") or not payload.get("interpretation"):
                skipped += 1
                continue
            predicate_match = match.get("predicate") or {}
            analysis, created = TopicAnalysis.objects.get_or_create(
                research=research,
                topic_id=topic_match["id"],
                defaults={
                    "predicate_id": predicate_match.get("id"),
                    "predicate_text": "" if predicate_match.get("id") else payload.get("predicate", ""),
                    "author_interpretation": payload.get("interpretation", ""),
                    "order": research.topic_analyses.count(),
                },
            )
            if not created:
                changed = []
                if not analysis.predicate_id and predicate_match.get("id"):
                    analysis.predicate_id = predicate_match["id"]
                    changed.append("predicate")
                if not analysis.predicate_id and not analysis.predicate_text and payload.get("predicate"):
                    analysis.predicate_text = payload["predicate"]
                    changed.append("predicate_text")
                if not analysis.author_interpretation.strip() and payload.get("interpretation"):
                    analysis.author_interpretation = payload["interpretation"]
                    changed.append("author_interpretation")
                if changed:
                    analysis.save(update_fields=changed + ["updated_at"])
            processing_ids = [x.get("id") for x in (match.get("processing_keys") or []) if x.get("id")]
            if processing_ids:
                analysis.processing_keys.add(*processing_ids)
            applied += 1
        elif suggestion.kind == "character":
            value = (match.get("value") or {}).get("id")
            if value:
                research.characters.add(value); applied += 1
            else:
                skipped += 1
        elif suggestion.kind == "occasion":
            value = (match.get("value") or {}).get("id")
            if value:
                research.occasions.add(value); applied += 1
            else:
                skipped += 1
        elif suggestion.kind == "keyword":
            label = suggestion.label.strip()
            if label:
                keyword_map.setdefault(normalize_fa(label), label)
                applied += 1
        elif suggestion.kind == "audience":
            row = payload if isinstance(payload, dict) else {"value": suggestion.label}
            normalized_row = {
                "is_primary": False,
                "general": bool(row.get("general", False)),
                "genders": row.get("genders") or [],
                "ages": row.get("ages") or [],
                "jobs": row.get("jobs") or [],
                "country": str(row.get("country") or "")[:120],
                "city": str(row.get("city") or "")[:120],
                "literacy": str(row.get("literacy") or "")[:80],
                "channels": row.get("channels") or [],
                "needs": str(row.get("needs") or row.get("value") or suggestion.label)[:500],
                "notes": str(row.get("notes") or "پیشنهاد هوش مصنوعی؛ بازبینی شود")[:500],
            }
            if normalized_row not in audiences:
                audiences.append(normalized_row)
            applied += 1

    research.search_keywords = "، ".join(keyword_map.values())
    research.audience_profiles = audiences
    research.save(update_fields=["search_keywords", "audience_profiles", "updated_at"])
    refresh_search_document(research)
    run.status = "applied"
    run.applied_at = timezone.now()
    run.save(update_fields=["status", "applied_at", "updated_at"])
    WorkflowEvent.objects.create(
        research=research, actor=request.user, event_type="updated",
        message=f"{applied} پیشنهاد هوش مصنوعی پس از تأیید پژوهشگر اعمال شد.",
        metadata={"ai_indexing_run": run.pk, "applied": applied, "skipped": skipped},
    )
    if skipped:
        messages.warning(request, f"{applied} پیشنهاد اعمال شد و {skipped} مورد به‌دلیل نبود تطبیق قطعی یا اطلاعات کافی اعمال نشد.")
    else:
        messages.success(request, f"{applied} پیشنهاد تأییدشده روی فیش اعمال شد.")
    return redirect("research_edit", pk=research.pk)


@login_required
def ai_sermon_builder(request):
    projects = _project_queryset_for(request.user).filter(is_active=True).select_related("sermon_style")
    endpoints = _active_ai_endpoints()
    styles = SermonStyle.objects.filter(is_active=True).order_by("order", "name")
    output = ""
    error = ""
    artifact = None
    selected_project = request.POST.get("project") or request.GET.get("project")
    selected_endpoint = request.POST.get("endpoint") or request.GET.get("endpoint")
    selected_style = request.POST.get("sermon_style") or request.GET.get("sermon_style")
    topic = request.POST.get("topic", "").strip()

    project = projects.filter(pk=selected_project).first() if selected_project else None
    if project and not selected_style and project.sermon_style_id:
        selected_style = str(project.sermon_style_id)
    if not selected_style:
        default_style = styles.filter(is_default=True).first()
        selected_style = str(default_style.pk) if default_style else ""

    if request.method == "POST":
        project = get_object_or_404(projects, pk=selected_project)
        endpoint = get_object_or_404(endpoints, pk=selected_endpoint)
        style = get_object_or_404(styles, pk=selected_style)
        fishes = list(project.researches.select_related("source").all()[:50])
        if not fishes:
            error = "این پروژه هنوز فیشی ندارد."
        else:
            audience_rows = project.audience_profiles or []
            audience_text = project.target_audience or "مخاطب عمومی"
            if audience_rows:
                audience_text = " | ".join(
                    [
                        ("مخاطب اصلی: " if row.get("is_primary") else "مخاطب تکمیلی: ")
                        + ("عموم مردم" if row.get("general") else "، ".join(
                            list(dict.fromkeys((row.get("ages") or []) + (row.get("genders") or []) + (row.get("jobs") or [])))
                        ))
                        + (f"؛ نیاز: {row.get('needs')}" if row.get("needs") else "")
                        + (f"؛ لحن: {row.get('notes')}" if row.get("notes") else "")
                        for row in audience_rows
                    ]
                )
            source_text = "\n\n".join(
                f"### {item.title}\nخلاصه: {item.abstract}\nمتن: {re.sub('<[^>]+>', ' ', item.body)[:5000]}\nمنبع: {item.source or 'ثبت نشده'}"
                for item in fishes
            )
            prompt = (
                "شما دستیار حرفه‌ای طراحی منبر فارسی هستید. فقط بر اساس فیش‌های پروژه بنویس و هیچ آیه، حدیث، "
                "نقل‌قول، آمار یا واقعیت تازه‌ای جعل نکن. کنار هر شاهد، عنوان فیش مأخذ را بنویس.\n\n"
                f"سبک الزامی منبر: {style.name}\n"
                f"معرفی سبک: {style.description}\n"
                f"دستور تخصصی سبک: {style.system_prompt}\n"
                f"ساختار پیشنهادی: {style.outline_template}\n"
                f"لحن: {style.tone or 'متناسب با مخاطب'}\n"
                f"سطح زبان: {style.language_level or 'روان'}\n"
                f"مدت پیشنهادی: {style.duration_minutes} دقیقه\n"
                f"راهنمای مخاطب: {style.audience_guidance}\n\n"
                f"پروژه: {project.title}\nهدف پروژه: {project.objective}\n"
                f"مخاطب‌شناسی پروژه: {audience_text}\n"
                f"موضوع یا زاویه درخواستی: {topic or project.title}\n\n"
                "خروجی شامل عنوان، هدف، قلاب آغازین، مقدمه، محورهای اصلی، شواهد هر محور، گذارهای کلامی، "
                "جمع‌بندی و اقدام عملی باشد و سبک انتخاب‌شده را در سراسر متن رعایت کند.\n\n"
                f"فیش‌های پروژه:\n{source_text}"
            )
            log = AIGenerationLog.objects.create(
                user=request.user, endpoint=endpoint, project=project,
                task_type="sermon", prompt=prompt,
            )
            try:
                from .ai_services import run_completion
                output = run_completion(endpoint, [{"role": "user", "content": prompt}], timeout=120)
                log.response = output
                log.succeeded = True
                log.save(update_fields=["response", "succeeded"])
                artifact_title = (topic or project.title).strip()[:220]
                with transaction.atomic():
                    artifact = SermonArtifact.objects.create(
                        project=project,
                        style=style,
                        endpoint=endpoint,
                        generation_log=log,
                        created_by=request.user,
                        title=artifact_title,
                        topic=topic,
                        content=output,
                        version=1,
                    )
                    SermonRevision.objects.create(
                        artifact=artifact, version=1, content=output,
                        source="ai", edited_by=request.user,
                    )

                # ZOHA-W2.3-SERMON-GENERATION:START
                segments, references = enrich_semantic_text(
                    output,
                    user=request.user,
                    project=project,
                    endpoint=endpoint,
                )

                artifact.ai_segments = segments
                artifact.external_references = references

                artifact.save(
                    update_fields=[
                        "ai_segments",
                        "external_references",
                        "updated_at",
                    ]
                )
                # ZOHA-W2.3-SERMON-GENERATION:END

                messages.success(request, "منبر تولید و به‌عنوان نسخه ۱ ذخیره شد.")
            except Exception as exc:
                error = f"{exc.__class__.__name__}: {exc}"
                log.error = error
                log.save(update_fields=["error"])

    recent_artifacts = SermonArtifact.objects.filter(project__in=projects).select_related("project", "style", "created_by")[:12]
    return render(request, "research/ai_sermon_builder.html", {
        "projects": projects,
        "endpoints": endpoints,
        "styles": styles,
        "selected_project": selected_project,
        "selected_endpoint": selected_endpoint,
        "selected_style": selected_style,
        "topic": topic,
        "output": output,
        "artifact": artifact,
        "recent_artifacts": recent_artifacts,
        "error": error,
    })


@login_required
@transaction.atomic
def sermon_artifact_detail(request, pk):
    artifact = get_object_or_404(
        SermonArtifact.objects.select_related("project", "style", "endpoint", "created_by"),
        pk=pk,
    )
    if not _project_queryset_for(request.user).filter(pk=artifact.project_id).exists():
        raise PermissionDenied

    if request.method == "POST":
        title = re.sub(r"\s+", " ", request.POST.get("title", "")).strip()[:250]
        content = request.POST.get("content", "").strip()
        status = request.POST.get("status", artifact.status)
        if not title or not content:
            messages.error(request, "عنوان و متن منبر نمی‌توانند خالی باشند.")
        elif status not in dict(SermonArtifact.STATUS):
            messages.error(request, "وضعیت انتخاب‌شده معتبر نیست.")
        else:
            content_changed = content != artifact.content
            artifact.title = title
            artifact.topic = request.POST.get("topic", "").strip()
            artifact.status = status
            if content_changed:
                artifact.version += 1
                artifact.content = content
            artifact.save()

            if content_changed:
                # ZOHA-W2.3-SERMON-EDIT:START
                segments, references = enrich_semantic_text(
                    artifact.content,
                    user=request.user,
                    project=artifact.project,
                    endpoint=artifact.endpoint,
                )

                artifact.ai_segments = segments
                artifact.external_references = references

                artifact.save(
                    update_fields=[
                        "ai_segments",
                        "external_references",
                        "updated_at",
                    ]
                )
                # ZOHA-W2.3-SERMON-EDIT:END

            if content_changed:
                SermonRevision.objects.create(
                    artifact=artifact,
                    version=artifact.version,
                    content=content,
                    source="manual",
                    edited_by=request.user,
                )
                messages.success(request, f"ویرایش ذخیره شد؛ نسخه {artifact.version} ایجاد شد.")
            else:
                messages.success(request, "اطلاعات منبر ذخیره شد.")
            return redirect("sermon_artifact_detail", pk=artifact.pk)

    return render(request, "research/sermon_artifact_detail.html", {
        "artifact": artifact,
        "revisions": artifact.revisions.select_related("edited_by")[:30],
    })
