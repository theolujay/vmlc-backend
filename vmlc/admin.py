from django.contrib import admin
from django.core.cache import cache
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Count

from .models import (
    Exam,
    Question,
    CandidateExamResult,
    CandidateAnswer,
    FeatureFlag,
    CandidateExamResultSnapshot,
    ExamAccess,
    ExamAccessPasscode,
    CacheManagement,
    ExamHeartbeat,
    ViolationEvent,
)

from .utils.helpers import (
    invalidate_all_dashboard_caches,
)
from vmlc.v2.utils import (
    invalidate_exam_cache,
    invalidate_question_pool,
    invalidate_candidate_cache,
    invalidate_feature_flag,
    invalidate_registration_status,
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
    actions = ["generate_and_send_passcodes"]

    @admin.action(description="Generate and Send Direct Access Passcodes")
    def generate_and_send_passcodes(self, request, queryset):
        from vmlc.v2.tasks import generate_and_send_exam_passcodes_task

        for exam in queryset:
            generate_and_send_exam_passcodes_task.delay(str(exam.id))
        self.message_user(
            request,
            f"Started passcode generation and email tasks for {queryset.count()} exams.",
        )

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
        invalidate_exam_cache(exam.id)
        invalidate_all_dashboard_caches()

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
    actions = [
        "archive_questions",
        "unarchive_questions",
    ]
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
        invalidate_question_pool()
        for exam in question.exams.all():
            invalidate_exam_cache(exam.id)
        invalidate_all_dashboard_caches()

    @admin.display(description="Text")
    def text_summary(self, obj):
        return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text

    @admin.display(description="Created By", ordering="created_by__user__first_name")
    def creator_name(self, obj):
        if obj.created_by:
            return obj.created_by.user.get_full_name()
        return None

    @admin.action(description="Archive selected questions")
    def archive_questions(self, request, queryset):
        count = queryset.update(is_archived=True)
        invalidate_question_pool()
        for question in queryset:
            for exam in question.exams.all():
                invalidate_exam_cache(exam.id)
        invalidate_all_dashboard_caches()
        self.message_user(request, f"{count} questions archived.")

    @admin.action(description="Unarchive selected questions")
    def unarchive_questions(self, request, queryset):
        count = queryset.update(is_archived=False)
        invalidate_question_pool()
        for question in queryset:
            for exam in question.exams.all():
                invalidate_exam_cache(exam.id)
        invalidate_all_dashboard_caches()
        self.message_user(request, f"{count} questions unarchived.")


class CandidateAnswerInline(admin.TabularInline):
    """
    Inline for CandidateAnswer to be shown within CandidateExamResultAdmin.
    """

    model = CandidateAnswer
    extra = 0
    fields = ("question", "selected_option", "answered_at")
    readonly_fields = ("answered_at",)
    autocomplete_fields = ("question",)


@admin.register(CandidateExamResult)
class CandidateExamResultAdmin(admin.ModelAdmin):
    """
    Admin interface for the CandidateExamResult model.
    Displays result details per candidate and exam.
    """

    inlines = [CandidateAnswerInline]
    list_display = (
        "id",
        "candidate_email",
        "exam_title",
        "score",
        "recorded_at",
        "auto_score",
        "is_auto_submit",
        "score_submitted_by_name",
    )
    readonly_fields = ("recorded_at", "updated_at")
    list_filter = ("exam", "auto_score", "is_auto_submit")
    search_fields = (
        "candidate__user__email",
        "exam__competition_slot__exam__description",  # Exam doesn't have a direct title field anymore
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
        invalidate_candidate_cache(candidate.pk, candidate.user.id)
        invalidate_exam_cache(exam.id)
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

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_answer_cache(obj)

    def delete_model(self, request, obj):
        self._invalidate_answer_cache(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_answer_cache(obj)
        super().delete_queryset(request, queryset)

    def _invalidate_answer_cache(self, answer):
        if answer.candidate_exam_result:
            candidate = answer.candidate_exam_result.candidate
            invalidate_candidate_cache(candidate.pk, candidate.user.id)
            invalidate_exam_cache(answer.candidate_exam_result.exam_id)
        invalidate_all_dashboard_caches()

    @admin.display(
        description="Candidate",
        ordering="candidate_exam_result__candidate__user__email",
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

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_all_dashboard_caches()

    def delete_model(self, request, obj):
        invalidate_all_dashboard_caches()
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        invalidate_all_dashboard_caches()
        super().delete_queryset(request, queryset)

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
        invalidate_feature_flag(obj.key)
        invalidate_registration_status()

        if obj.auto_off_date:
            time_to_revoke = obj.auto_off_date
            disable_expired_feature_flags_task.apply_async(
                args=[obj.pk], eta=time_to_revoke
            )

    def delete_model(self, request, obj):
        invalidate_feature_flag(obj.key)
        invalidate_registration_status()
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            invalidate_feature_flag(obj.key)
            invalidate_registration_status()
        super().delete_queryset(request, queryset)


class ExamAccessPasscodeInline(admin.StackedInline):
    """
    Shows passcode and access URL for the specific exam access.
    """

    model = ExamAccessPasscode
    extra = 0
    fields = ("passcode", "access_url", "status", "is_passcode_sent", "expiry_date")
    readonly_fields = ("passcode", "access_url")


class ExamHeartbeatInline(admin.TabularInline):
    """
    Shows telemetry heartbeats for the exam access.
    """

    model = ExamHeartbeat
    extra = 0
    fields = ("sequence_number", "suspicion_score", "timestamp", "view_details")
    readonly_fields = ("timestamp", "view_details")

    @admin.display(description="Action")
    def view_details(self, obj):
        url = reverse("admin:vmlc_examheartbeat_change", args=[obj.id])
        return format_html('<a href="{}" class="button">View Heartbeat & Events</a>', url)


@admin.register(ExamAccess)
class ExamAccessAdmin(admin.ModelAdmin):
    inlines = [ExamAccessPasscodeInline, ExamHeartbeatInline]
    list_display = (
        "id",
        "candidate_email",
        "exam_title",
        "status",
        "proctoring_status",
        "is_manually_reviewed",
        "is_unlocked",
        "started_at",
        "deadline",
        "submitted_at",
        "unlock_action",
    )
    list_filter = (
        "exam",
        "created_at",
        "status",
        "facilitator_system",
        "proctoring_status",
        "is_manually_reviewed",
        "is_unlocked",
    )
    search_fields = ("candidate__user__email", "exam__description")
    list_select_related = ("candidate__user", "exam", "unlocked_by__user")
    readonly_fields = ("created_at",)
    actions = ["unlock_exam_access"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<uuid:access_id>/unlock/",
                self.admin_site.admin_view(self.unlock_exam_view),
                name="examaccess-unlock",
            ),
        ]
        return custom_urls + urls

    @admin.action(description="Unlock selected exam sessions")
    def unlock_exam_access(self, request, queryset):
        from channels.layers import get_channel_layer
        from django.utils import timezone
        from asgiref.sync import async_to_sync
        from django.core.cache import cache

        channel_layer = get_channel_layer()
        unlocked_count = 0
        already_unlocked = 0

        for access in queryset:
            # Check for existing cache entry as well
            is_qr_unlocked = cache.get(f"qr_unlock:{access.candidate_id}:{access.exam_id}")
            if access.is_unlocked or is_qr_unlocked:
                already_unlocked += 1
                continue

            # is_unlocked is kept False by design as a manual override/verification flag.
            # The actual eligibility is granted via a temporary cache entry.
            access.is_unlocked = False
            access.unlocked_by = request.user.staff_profile if hasattr(request.user, "staff_profile") else None
            access.save(update_fields=["is_unlocked", "unlocked_by"])

            # Register a temporary QR unlock in cache for EligibilityService
            cache.set(f"qr_unlock:{access.candidate_id}:{access.exam_id}", True, timeout=300)

            # Send unlock signal via WebSocket to candidate's user group
            if channel_layer:
                try:
                    async_to_sync(channel_layer.group_send)(
                        f"user__{access.candidate_id}",
                        {
                            "type": "exam.unlocked",
                            "data": {
                                "exam_id": str(access.exam_id),
                                "unlocked_by_name": request.user.get_full_name() or request.user.email,
                                "timestamp": str(timezone.now().timestamp()),
                            },
                        }
                    )
                    unlocked_count += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f"Failed to send unlock signal for {access.candidate_email}: {e}",
                        level=messages.WARNING,
                    )
            else:
                self.message_user(
                    request,
                    "Channel layer not available. Exam unlocked in cache but no WebSocket signal sent.",
                    level=messages.WARNING,
                )
                unlocked_count += 1

        if unlocked_count:
            self.message_user(
                request,
                f"Unlocked {unlocked_count} exam session(s) in cache and sent WebSocket signal(s).",
                level=messages.SUCCESS,
            )
        if already_unlocked:
            self.message_user(
                request,
                f"{already_unlocked} session(s) were already unlocked.",
                level=messages.INFO,
            )

    def unlock_exam_view(self, request, access_id):
        """Individual unlock action from change form button."""
        from channels.layers import get_channel_layer
        from django.utils import timezone
        from asgiref.sync import async_to_sync
        from django.core.cache import cache

        access = self.get_object(request, access_id)
        if access is None:
            self.message_user(request, "Exam access not found.", level=messages.ERROR)
            return redirect("admin:vmlc_examaccess_changelist")

        is_qr_unlocked = cache.get(f"qr_unlock:{access.candidate_id}:{access.exam_id}")
        if access.is_unlocked or is_qr_unlocked:
            self.message_user(request, "This exam session is already unlocked.", level=messages.INFO)
            return redirect("admin:vmlc_examaccess_change", access_id)

        # is_unlocked is kept False by design as a manual override/verification flag.
        # The actual eligibility is granted via a temporary cache entry.
        access.is_unlocked = False
        access.unlocked_by = request.user.staff_profile if hasattr(request.user, "staff_profile") else None
        access.save(update_fields=["unlocked_by", "is_unlocked"])

        # Register a temporary QR unlock in cache for EligibilityService
        cache.set(f"qr_unlock:{access.candidate_id}:{access.exam_id}", True, timeout=300)

        channel_layer = get_channel_layer()
        if channel_layer:
            try:
                async_to_sync(channel_layer.group_send)(
                    f"user__{access.candidate_id}",
                    {
                        "type": "exam.unlocked",
                        "data": {
                            "exam_id": str(access.exam_id),
                            "unlocked_by_name": request.user.get_full_name() or request.user.email,
                            "timestamp": str(timezone.now().timestamp()),
                        },
                    }
                )
                self.message_user(
                    request,
                    f"Exam unlocked for {access.candidate.user.email} (cache only) — WebSocket signal sent.",
                    level=messages.SUCCESS,
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Exam unlocked in cache but WebSocket signal failed: {e}",
                    level=messages.WARNING,
                )
        else:
            self.message_user(
                request,
                "Exam unlocked in cache. Channel layer unavailable — no WebSocket signal sent.",
                level=messages.WARNING,
            )

        return redirect("admin:vmlc_examaccess_change", access_id)

    @admin.display(description="")
    def unlock_action(self, obj):
        if obj.is_unlocked:
            return format_html('<span style="color: #0f973d; font-weight: bold;">✓ Unlocked</span>')
        url = reverse("admin:examaccess-unlock", args=[obj.pk])
        return format_html(
            '<a href="{}" class="button" style="background: #3E4095; color: white; padding: 4px 10px; border-radius: 4px; text-decoration: none; font-size: 11px; font-weight: bold;">Unlock Exam</a>',
            url,
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_access_cache(obj)

    def delete_model(self, request, obj):
        self._invalidate_access_cache(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_access_cache(obj)
        super().delete_queryset(request, queryset)

    def _invalidate_access_cache(self, access):
        candidate = access.candidate
        invalidate_candidate_cache(candidate.pk, candidate.user.id)
        invalidate_exam_cache(access.exam_id)
        invalidate_all_dashboard_caches()

    @admin.display(description="Candidate", ordering="candidate__user__email")
    def candidate_email(self, obj):
        return obj.candidate.user.email

    @admin.display(description="Exam")
    def exam_title(self, obj):
        return obj.exam.get_title()


@admin.register(CacheManagement)
class CacheManagementAdmin(admin.ModelAdmin):
    """
    Admin interface for cache management.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True

    def changelist_view(self, request, extra_context=None):
        """
        Redirect the changelist view to the clear cache view or show a button.
        """
        from django.shortcuts import render, redirect
        from django.contrib import messages

        if "clear" in request.GET:
            cache.clear()
            self.message_user(
                request, "All caches cleared successfully.", messages.SUCCESS
            )
            return redirect("admin:vmlc_cachemanagement_changelist")

        extra_context = extra_context or {}
        extra_context["title"] = "Cache Management"
        return render(request, "admin/cache_management.html", extra_context)


@admin.register(ExamAccessPasscode)
class ExamAccessPasscodeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "candidate_email",
        "exam_title",
        "status",
        "is_passcode_sent",
        "expiry_date",
        "created_at",
    )
    list_filter = ("status", "is_passcode_sent", "created_at")
    search_fields = (
        "passcode",
        "exam_access__candidate__user__email",
        "exam_access__exam__description",
    )
    list_select_related = (
        "exam_access__candidate__user",
        "exam_access__exam",
    )
    readonly_fields = ("created_at", "updated_at")

    @admin.display(
        description="Candidate", ordering="exam_access__candidate__user__email"
    )
    def candidate_email(self, obj):
        return obj.exam_access.candidate.user.email

    @admin.display(description="Exam")
    def exam_title(self, obj):
        return obj.exam_access.exam.get_title()


class ViolationEventInline(admin.TabularInline):
    """
    Shows individual violation events within a heartbeat.
    """

    model = ViolationEvent
    extra = 0
    fields = ("event_type", "is_critical", "timestamp", "metadata")
    readonly_fields = ("timestamp",)


@admin.register(ExamHeartbeat)
class ExamHeartbeatAdmin(admin.ModelAdmin):
    inlines = [ViolationEventInline]
    list_display = (
        "id",
        "exam_access",
        "sequence_number",
        "suspicion_score",
        "timestamp",
    )
    list_filter = ("timestamp",)
    search_fields = ("exam_access__candidate__user__email",)
    readonly_fields = ("timestamp",)


@admin.register(ViolationEvent)
class ViolationEventAdmin(admin.ModelAdmin):
    list_display = ("id", "heartbeat", "event_type", "is_critical", "timestamp")
    list_filter = ("event_type", "is_critical", "timestamp")
    search_fields = ("heartbeat__exam_access__candidate__user__email",)
