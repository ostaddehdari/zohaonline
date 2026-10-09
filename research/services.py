from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Notification, ResearchVersion, ReviewerAssignment, ReviewTask, WorkflowEvent


def snapshot_research(research, user, reason=""):
    analyses = []
    for item in research.topic_analyses.select_related("topic", "predicate").prefetch_related("processing_keys"):
        analyses.append({
            "topic": item.topic.title,
            "processing_keys": list(item.processing_keys.values_list("title", flat=True)),
            "predicate": item.predicate.title if item.predicate_id else item.predicate_text,
            "author_interpretation": item.author_interpretation,
            "review_status": item.review_status,
        })
    data = {
        "title": research.title,
        "abstract": research.abstract,
        "body": research.body,
        "search_keywords": research.search_keywords,
        "author_explanation": research.author_explanation,
        "content_kind": research.content_kind.title if research.content_kind_id else None,
        "content_category": research.content_category.title if research.content_category_id else None,
        "main_format": research.main_format.title if research.main_format_id else None,
        "sub_format": research.sub_format.title if research.sub_format_id else None,
        "source": {
            "type": research.source_type.title if research.source_type_id else None,
            "name": str(research.source) if research.source_id else None,
            "volume": research.source_volume,
            "page": research.source_page,
            "narrator": research.source_narrator,
            "url": research.source_url,
            "note": research.source_note,
        },
        "characters": list(research.characters.values_list("title", flat=True)),
        "secondary_characters": list(research.secondary_characters.values_list("title", flat=True)),
        "occasions": list(research.occasions.values_list("title", flat=True)),
        "seo_tags": list(research.seo_tags or []),
        "external_references": list(research.external_references or []),
        "ai_segments": list(research.ai_segments or []),
        "featured_image": research.featured_image.name if research.featured_image else None,
        "audiences": research.audience_profiles,
        "topic_analyses": analyses,
        "access_level": research.access_level,
        "team": research.team.name if research.team_id else None,
        "status": research.status,
        "indexes": [
            {
                "type": item.index_type.name,
                "value": item.display_value,
                "excerpt": item.source_excerpt,
            }
            for item in research.indexes.select_related("index_type", "index_value")
        ],
    }
    ResearchVersion.objects.update_or_create(
        research=research,
        version=research.version,
        defaults={"snapshot": data, "created_by": user, "reason": reason},
    )


def event_and_notify(research, actor, event_type, message, recipients=()):
    event = WorkflowEvent.objects.create(
        research=research, actor=actor, event_type=event_type, message=message
    )
    url = reverse("research_detail", args=[research.pk])
    Notification.objects.bulk_create([
        Notification(
            recipient=recipient,
            research=research,
            event=event,
            title=message[:255],
            message=message,
            url=url,
        )
        for recipient in set(recipients)
        if recipient and recipient != actor
    ])
    return event


@transaction.atomic
def submit_research(research, actor):
    snapshot_research(research, actor, "ارسال برای ارزیابی")
    old_status = research.status
    research.current_round += 1
    research.transition_to("in_review", save=False)
    research.submitted_at = timezone.now()
    research.version += 1
    research.save(update_fields=[
        "current_round", "status", "submitted_at", "version", "updated_at",
    ])
    assignments = ReviewerAssignment.objects.filter(
        researcher=research.researcher, is_active=True
    ).select_related("reviewer", "scope")
    assignments = list(assignments)
    ReviewTask.objects.bulk_create([
        ReviewTask(
            research=research,
            reviewer=assignment.reviewer,
            scope=assignment.scope,
            round=research.current_round,
        )
        for assignment in assignments
    ], ignore_conflicts=True)
    reviewers = [assignment.reviewer for assignment in assignments]
    event_and_notify(
        research,
        actor,
        "resubmitted" if old_status == "changes_requested" else "submitted",
        "فیش برای ارزیابی ارسال شد.",
        reviewers,
    )
    return len(reviewers)
