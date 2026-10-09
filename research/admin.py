from django.contrib import admin

from .models import (
    AIGenerationLog, AIEndpointStatus, AIIndexingRun, AIIndexSuggestion, AIProbeRun, ContentReport, EducationCourse, EducationLesson, IndexType, IndexValue, Notification,
    OptionAuditLog, ProjectResearch, PromotionProject, Research, ResearchAttachment, ResearchBookmark, ResearchIndex, CustomCollection,
    ResearchReaction, ReviewerAssignment, ReviewComment, ReviewTask, SearchLog, SermonArtifact, SermonRevision, SermonStyle, Source, SubscriptionPlan, TopicAnalysis, FullContent, UserSubscription,
    WorkflowEvent,
)


class TopicAnalysisInline(admin.TabularInline):
    model = TopicAnalysis
    extra = 0


@admin.register(Research)
class ResearchAdmin(admin.ModelAdmin):
    list_display = ("title", "researcher", "content_kind", "main_format", "status", "access_level", "is_featured", "featured_order", "team", "updated_at")
    list_filter = ("status", "access_level", "is_featured", "team", "content_kind", "main_format")
    search_fields = ("title", "abstract", "body", "search_keywords", "source__title")
    autocomplete_fields = ("researcher", "team", "content_kind", "content_category", "main_format", "sub_format", "source_type", "source")
    filter_horizontal = ("characters", "secondary_characters", "occasions")
    list_editable = ("is_featured", "featured_order")
    inlines = [TopicAnalysisInline]


@admin.register(IndexType)
class IndexTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "data_type", "is_required", "is_active", "order")
    list_editable = ("is_required", "is_active", "order")
    search_fields = ("name", "slug")


@admin.register(IndexValue)
class IndexValueAdmin(admin.ModelAdmin):
    list_display = ("title", "index_type", "visibility", "approval_status", "owner", "is_active")
    list_filter = ("index_type", "visibility", "approval_status", "is_active")
    search_fields = ("title", "normalized_title", "aliases")
    autocomplete_fields = ("parent", "owner", "merged_into", "created_by")

    def has_delete_permission(self, request, obj=None):
        if obj and obj.usage_count:
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        previous = IndexValue.objects.filter(pk=obj.pk).first() if change else None
        super().save_model(request, obj, form, change)
        action = "created"
        details = {}
        if previous:
            action = "edited"
            if previous.title != obj.title:
                action = "renamed"
                details = {"from": previous.title, "to": obj.title}
            elif previous.is_active and not obj.is_active:
                action = "deactivated"
            elif not previous.is_active and obj.is_active:
                action = "activated"
            elif previous.approval_status != obj.approval_status:
                action = "approved" if obj.approval_status == "approved" else "rejected"
        OptionAuditLog.objects.create(option=obj, actor=request.user, action=action, details=details)


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("title", "author_name", "visibility", "approval_status", "owner", "is_active")
    list_filter = ("visibility", "approval_status", "is_active")
    search_fields = ("title", "author_name", "aliases")

    def has_delete_permission(self, request, obj=None):
        if obj and obj.researches.exists():
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        previous = Source.objects.filter(pk=obj.pk).first() if change else None
        super().save_model(request, obj, form, change)
        action = "created"
        details = {}
        if previous:
            action = "edited"
            if previous.title != obj.title:
                action = "renamed"
                details = {"from": previous.title, "to": obj.title}
            elif previous.is_active and not obj.is_active:
                action = "deactivated"
            elif not previous.is_active and obj.is_active:
                action = "activated"
            elif previous.approval_status != obj.approval_status:
                action = "approved" if obj.approval_status == "approved" else "rejected"
        OptionAuditLog.objects.create(source=obj, actor=request.user, action=action, details=details)


@admin.register(TopicAnalysis)
class TopicAnalysisAdmin(admin.ModelAdmin):
    list_display = ("research", "topic", "predicate", "review_status", "order")
    list_filter = ("review_status", "topic")
    search_fields = ("research__title", "topic__title", "predicate__title", "predicate_text", "author_interpretation")
    filter_horizontal = ("processing_keys",)


@admin.register(SermonStyle)
class SermonStyleAdmin(admin.ModelAdmin):
    list_display = ("name", "tone", "duration_minutes", "is_default", "is_active", "order")
    list_filter = ("is_default", "is_active", "tone")
    list_editable = ("is_default", "is_active", "order")
    search_fields = ("name", "slug", "description", "system_prompt", "outline_template")
    prepopulated_fields = {"slug": ("name",)}


admin.site.register([
    ResearchIndex, ReviewTask, ReviewComment, ReviewerAssignment,
    WorkflowEvent, Notification, SearchLog, OptionAuditLog, PromotionProject,
    ProjectResearch, CustomCollection, ResearchAttachment, ResearchBookmark, AIEndpointStatus, AIProbeRun, AIGenerationLog, AIIndexingRun,
    AIIndexSuggestion, SermonArtifact, SermonRevision, FullContent, ResearchReaction, ContentReport,
    EducationCourse, EducationLesson, SubscriptionPlan, UserSubscription,
])
