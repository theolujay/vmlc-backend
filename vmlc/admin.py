from django.contrib import admin
from django.core.cache import cache
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count

from .models import (
    Exam,
    Question,
    CandidateExamResult,
    CandidateAnswer,
    LeaderboardSnapshot,
    FeatureFlag,
    CandidateExamResultSnapshot,
    SupportInquiry,
)

from .utils.helpers import (
    invalidate_all_dashboard_caches,
)


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    """
    Admin interface for the Exam model.
    Displays exam metadata and allows filtering by publication status.
    """

    list_display = (
        "id",
        "title",
        "scheduled_date",
        "get_question_count",
        "is_active",
        "is_currently_open",
        "view_results_link",
        "created_at",
    )
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("is_active", "created_by", "delivery_mode")
    search_fields = ("description",)
    date_hierarchy = "scheduled_date"
    filter_horizontal = ("questions",)
    list_select_related = ("created_by", "created_by__user", "competition_slot")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_exam_cache(obj)

    def delete_model(self, request, obj):
        self._invalidate_exam_cache(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_exam_cache(obj)
        super().delete_queryset(request, queryset)

    def _invalidate_exam_cache(self, exam):
        cache.delete(f"exam_detail_{exam.id}")
        cache.delete(f"exam_results_{exam.id}")
        cache.delete(f"exam_questions_{exam.id}")
        invalidate_all_dashboard_caches()
        for result in exam.results.all():
            cache.delete(f"account_management_{result.candidate.user.id}")

    @admin.display(description="Question Count", ordering="question_count")
    def get_question_count(self, obj):
        if hasattr(obj, "question_count"):
            return obj.question_count
        return obj.questions.count()

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(question_count=Count("questions"))

    @admin.display(description="Results")
    def view_results_link(self, obj):
        url = (
            reverse("admin:vmlc_candidateexamresult_changelist")
            + f"?exam__id__exact={obj.pk}"
        )
        return format_html('<a href="{}" target="_blank">View Results</a>', url)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """
    Admin interface for the Question model.
    Displays question text, difficulty, and creator.
    """

    list_display = (
        "id",
        "text_summary",
        "difficulty",
        "creator_name",
        "is_archived",
        "archived_at",
        "created_at",
    )
    readonly_fields = ("created_at", "updated_at", "archived_at")
    list_filter = ("difficulty", "created_by", "is_archived")
    search_fields = ("text", "created_by__user__email")
    list_select_related = ("created_by__user",)
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_question_cache(obj)

    def delete_model(self, request, obj):
        self._invalidate_question_cache(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_question_cache(obj)
        super().delete_queryset(request, queryset)

    def _invalidate_question_cache(self, question):
        cache.delete("question_pool_data")
        for exam in question.exams.all():
            cache.delete(f"exam_questions_{exam.id}")
            cache.delete(f"exam_detail_{exam.id}")
        invalidate_all_dashboard_caches()

    @admin.display(description="Text")
    def text_summary(self, obj):
        return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text

    @admin.display(description="Created By", ordering="created_by__user__first_name")
    def creator_name(self, obj):
        if obj.created_by:
            return obj.created_by.user.get_full_name()
        return None


@admin.register(CandidateExamResult)
class CandidateExamResultAdmin(admin.ModelAdmin):
    """
    Admin interface for the CandidateExamResult model.
    Displays result details per candidate and exam.
    """

    list_display = (
        "id",
        "candidate_email",
        "exam_title",
        "score",
        "recorded_at",
        "auto_score",
        "score_submitted_by_name",
    )
    readonly_fields = ("recorded_at", "updated_at")
    list_filter = ("exam", "auto_score", "score_submitted_by")
    search_fields = (
        "candidate__user__email",
        "exam__competition_slot__exam__description", # Exam doesn't have a direct title field anymore
        "score_submitted_by__user__email",
    )
    list_select_related = ("candidate__user", "exam", "score_submitted_by__user")
    date_hierarchy = "recorded_at"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_result_cache(obj)

    def delete_model(self, request, obj):
        self._invalidate_result_cache(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_result_cache(obj)
        super().delete_queryset(request, queryset)

    def _invalidate_result_cache(self, result):
        candidate = result.candidate
        exam = result.exam
        cache.delete(f"account_management_{candidate.user.id}")
        cache.delete(f"exam_history_{candidate.user.id}")
        cache.delete(f"exam_results_{exam.id}")
        invalidate_all_dashboard_caches()

    @admin.display(description="Candidate", ordering="candidate__user__email")
    def candidate_email(self, obj):
        return obj.candidate.user.email

    @admin.display(description="Exam")
    def exam_title(self, obj):
        return obj.exam.get_title()

    @admin.display(
        description="Score Submitted By",
        ordering="score_submitted_by__user__first_name",
    )
    def score_submitted_by_name(self, obj):
        if obj.score_submitted_by:
            return obj.score_submitted_by.user.get_full_name()
        return "Auto Score" if obj.auto_score else "N/A"


@admin.register(CandidateAnswer)
class CandidateAnswerAdmin(admin.ModelAdmin):
    """
    Admin interface for the CandidateAnswer model.
    Displays answers provided by each candidate in specific exams.
    """

    list_display = (
        "id",
        "candidate_email",
        "exam_title_display",
        "question_text",
        "selected_option",
        "answered_at",
    )
    readonly_fields = ("answered_at",)
    list_filter = ("candidate_exam_result__exam", "answered_at")
    search_fields = ("candidate_exam_result__candidate__user__email", "question__text")
    autocomplete_fields = ("question", "candidate_exam_result")
    list_select_related = (
        "candidate_exam_result__candidate__user",
        "candidate_exam_result__exam",
        "question",
    )
    date_hierarchy = "answered_at"

    @admin.display(
        description="Candidate", ordering="candidate_exam_result__candidate__user__email"
    )
    def candidate_email(self, obj):
        return obj.candidate_exam_result.candidate.user.email

    @admin.display(description="Exam")
    def exam_title_display(self, obj):
        return obj.candidate_exam_result.exam.get_title()

    @admin.display(description="Question", ordering="question__text")
    def question_text(self, obj):
        return (
            str(obj.question)[:50] + "..."
            if len(str(obj.question)) > 50
            else str(obj.question)
        )


@admin.register(LeaderboardSnapshot)
class LeaderboardSnapshotAdmin(admin.ModelAdmin):
    """
    Admin interface for the LeaderboardSnapshot model.
    Displays key details about each leaderboard snapshot.
    """

    list_display = (
        "id",
        "is_published",
        "data_summary",
        "published_by_name",
        "created_at",
    )
    readonly_fields = ("created_at",)
    list_filter = ("is_published", "created_at", "published_by")
    search_fields = ("published_by__user__email",)
    list_select_related = ("published_by__user",)
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        cache.delete_pattern("leaderboard_*")
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        cache.delete_pattern("leaderboard_*")
        super().delete_model(request, obj)

    @admin.display(description="Published By", ordering="published_by__user__email")
    def published_by_name(self, obj):
        if obj.published_by:
            return obj.published_by.user.get_full_name()
        return None

    @admin.display(description="Data Summary")
    def data_summary(self, obj):
        import json

        screening_leaderboard_data = {}
        league_leaderboard_data = {}

        if isinstance(obj.data, list):
            for item in obj.data:
                if isinstance(item, dict):
                    if item.get("stage") == "screening":
                        screening_leaderboard_data = item
                    elif item.get("stage") == "league":
                        league_leaderboard_data = item

        screening_leaderboard_str = str(json.dumps(screening_leaderboard_data))
        league_leaderboard_str = str(json.dumps(league_leaderboard_data))

        summary = {
            "screening_leaderboard": (
                (screening_leaderboard_str[:75] + "...")
                if len(screening_leaderboard_str) > 75
                else screening_leaderboard_str
            ),
            "league_leaderboard": (
                (league_leaderboard_str[:75] + "...")
                if len(league_leaderboard_str) > 75
                else league_leaderboard_str
            ),
        }
        return summary


@admin.register(CandidateExamResultSnapshot)
class CandidateExamResultSnapshotAdmin(admin.ModelAdmin):
    """
    Admin interface for the CandidateExamResultSnapshot model.
    Displays key details about each snapshot for the candidate results.
    """

    list_display = (
        "id",
        "published_at",
        "data_summary",
        "published_by_name",
        "created_at",
    )
    readonly_fields = ("created_at",)
    list_filter = ("created_at", "published_by")
    search_fields = ("published_by__user__email",)
    list_select_related = ("published_by__user",)
    date_hierarchy = "created_at"

    @admin.display(description="Published By", ordering="published_by__user__email")
    def published_by_name(self, obj):
        if obj.published_by:
            return obj.published_by.user.get_full_name()
        return None

    @admin.display(description="Data Summary")
    def data_summary(self, obj):
        import json

        summary = str(json.dumps(obj.data))
        return (summary[:75] + "...") if len(summary) > 75 else summary


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):

    list_display = ("key", "value", "auto_off_date")
    search_fields = ("key",)
    list_editable = ("value", "auto_off_date")

    def save_model(self, request, obj, form, change):
        from vmlc.tasks import disable_expired_feature_flags_task

        super().save_model(request, obj, form, change)
        cache.delete(f"feature_flag_{obj.key}")
        cache.delete("registration_status")

        if obj.auto_off_date:
            time_to_revoke = obj.auto_off_date
            disable_expired_feature_flags_task.apply_async(
                args=[obj.pk], eta=time_to_revoke
            )

    def delete_model(self, request, obj):
        cache.delete(f"feature_flag_{obj.key}")
        super().delete_model(request, obj)
        cache.delete("registration_status")

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            cache.delete(f"feature_flag_{obj.key}")
            cache.delete("registration_status")
        super().delete_queryset(request, queryset)


@admin.register(SupportInquiry)
class SupportInquiryAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "support_type", "organization", "status", "created_at")
    list_filter = ("support_type", "status", "created_at")
    search_fields = ("full_name", "email", "message", "organization")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("user",)