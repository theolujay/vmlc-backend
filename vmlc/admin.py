from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum
from django import forms
from django.template.response import TemplateResponse
from vmlc.tasks import send_mail_task
from .models import (
    Candidate,
    Staff,
    Exam,
    Question,
    CandidateScore,
    CandidateAnswer,
    LeaderboardSnapshot,
    FeatureFlag,
    User,
    CandidateScoreSnapshot,
    UserVerification,
)

from .utils.email import create_email_html
class EmailForm(forms.Form):
    subject = forms.CharField(max_length=100, required=True)
    message = forms.CharField(widget=forms.Textarea, required=True)


@admin.action(description="Send email to selected users")
def send_email_to_users(modeladmin, request, queryset):
    if "apply" in request.POST:
        form = EmailForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data["subject"]
            message = form.cleaned_data["message"]
            html_message = create_email_html(subject=subject, message=message)
            recipient_emails = list(queryset.values_list('email', flat=True))

            send_mail_task.delay(
                subject=subject,
                message="", # Plain text part is empty
                recipient_list=recipient_emails,
                html_message=html_message
            )

            modeladmin.message_user(request, f"Scheduled sending emails to {len(recipient_emails)} users.")
            return None
    else:
        form = EmailForm()

    return TemplateResponse(
        request,
        "admin/send_email_form.html",
        {
            "opts": modeladmin.model._meta,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
            "queryset": queryset,
            "form": form,
            "title": "Send Email",
            "action": "send_email_to_users",
        },
    )


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    actions = [send_email_to_users]
    list_display = (
        "email",
        "first_name",
        "last_name",
        "user_profile",
        "is_email_verified",
        "is_active",
        "date_joined",
        "id",
    )
    readonly_fields = ("date_joined", "id")
    list_filter = ("is_active", "date_joined")
    search_fields = ("email", "first_name")

    @admin.display(description="User Profile")
    def user_profile(self, obj):
        try:
            if hasattr(obj, "candidate_profile"):
                return "Candidate"
            elif hasattr(obj, "staff_profile"):
                return "Staff"
        except ObjectDoesNotExist:
            return "—"


@admin.register(UserVerification)
class UserVerificationAdmin(admin.ModelAdmin):
    """Simplified admin interface for UserVerification model."""

    list_display = [
        "user",
        "verification_status",
        "has_face_id",
        "has_id_card",
        "has_verification_document",
        "created_at",
    ]

    list_filter = ["is_pending", "is_verified", "created_at"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    readonly_fields = ["created_at", "updated_at"]
    list_select_related = ("user",)
    date_hierarchy = "created_at"

    actions = ["approve_selected", "reject_selected"]

    fieldsets = (
        (None, {"fields": ("user", "is_pending", "is_verified")}),
        ("Files", {"fields": ("face_id", "id_card", "verification_document")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Status")
    def verification_status(self, obj):
        """Display verification status with color coding."""
        if obj.is_verified:
            return format_html('<span style="color: green;">✓ Verified</span>')
        elif obj.is_pending:
            return format_html('<span style="color: orange;">⏳ Pending</span>')
        elif obj.is_rejected:
            return format_html('<span style="color: red;">❌ Rejected</span>')

    @admin.display(description="Photo", boolean=True)
    def has_face_id(self, obj):
        return bool(obj.face_id)

    @admin.display(description="ID", boolean=True)
    def has_id_card(self, obj):
        return bool(obj.id_card)

    @admin.display(description="Doc", boolean=True)
    def has_verification_document(self, obj):
        return bool(obj.verification_document)

    @admin.action(description="Approve selected verifications")
    def approve_selected(self, request, queryset):
        """Approve selected verification requests."""
        count = queryset.update(is_verified=True, is_pending=False)
        self.message_user(request, f"{count} verification(s) approved.")

    @admin.action(description="Reject selected verifications")
    def reject_selected(self, request, queryset):
        """Reject selected verification requests."""
        count = queryset.update(is_verified=False, is_pending=False)
        self.message_user(request, f"{count} verification(s) rejected.")


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    """
    Admin interface for the Candidate model.
    Displays key candidate details and allows filtering by role, verification, and active status.
    """

    list_display = (
        "email",
        "full_name",
        "school",
        "role",
        "total_score_display",
        "get_primary_key",
        "exams_taken",
        "is_verified",
        "is_active",
        "created_at",
    )
    readonly_fields = ("created_at", "updated_at")
    # Fixed: Use actual database fields for filtering
    list_filter = (
        "role",
        "user__is_active",  # Filter by user's is_active field
        "user__verification__is_verified",  # Filter by verification status
        "created_at",
    )
    search_fields = ("user__email", "user__first_name", "user__last_name", "school")
    list_select_related = ("user", "user__verification")
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            total_score=Sum("scores__score"),
            exams_taken_count=Count("scores", distinct=True),
        )

    @admin.display(description="Total Score", ordering="total_score")
    def total_score_display(self, obj):
        return obj.total_score

    @admin.display(description="Email", ordering="user__email")
    def email(self, obj):
        return obj.user.email

    @admin.display(description="Full Name", ordering="user__first_name")
    def full_name(self, obj):
        return obj.user.get_full_name()

    @admin.display(description="ID")
    def get_primary_key(self, obj):
        return obj.pk

    @admin.display(
        description="Verified", boolean=True, ordering="user__verification__is_verified"
    )
    def is_verified(self, obj):
        return obj.is_verified

    @admin.display(description="Active", boolean=True, ordering="user__is_active")
    def is_active(self, obj):
        return obj.is_active

    @admin.display(description="Exams Taken", ordering="exams_taken_count")
    def exams_taken(self, obj):
        return obj.exams_taken_count


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    """
    Admin interface for the Staff model.
    Displays key staff information and allows filtering by role, verification, and active status.
    """

    list_display = (
        "email",
        "full_name",
        "role",
        "occupation",
        "get_primary_key",
        "is_verified",
        "is_active",
        "created_at",
        "created_by",
    )
    readonly_fields = ("created_at", "updated_at")
    # Fixed: Use actual database fields for filtering
    list_filter = (
        "role",
        "user__is_active",  # Filter by user's is_active field
        "user__verification__is_verified",  # Filter by verification status
        "created_at",
    )
    search_fields = ("user__email", "user__first_name", "user__last_name", "occupation")
    list_select_related = ("user", "user__verification")
    date_hierarchy = "created_at"

    @admin.display(description="Email", ordering="user__email")
    def email(self, obj):
        return obj.user.email

    @admin.display(description="Full Name", ordering="user__first_name")
    def full_name(self, obj):
        return obj.user.get_full_name()

    @admin.display(description="ID")
    def get_primary_key(self, obj):
        return obj.pk

    @admin.display(
        description="Verified", boolean=True, ordering="user__verification__is_verified"
    )
    def is_verified(self, obj):
        return obj.is_verified

    @admin.display(description="Active", boolean=True, ordering="user__is_active")
    def is_active(self, obj):
        return obj.is_active
    
    @admin.display(description="Invited Staff")
    def created_by(self, obj):
        if obj.created_by:
            return obj.created_by.user.get_full_name()
        return None

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    """
    Admin interface for the Exam model.
    Displays exam metadata and allows filtering by stage and publication status.
    """

    list_display = (
        "id",
        "title",
        "stage",
        "exam_date",
        "get_question_count",
        "is_active",
        "view_results_link",
        "created_at",
    )
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("stage", "is_active", "created_by")
    search_fields = ("title", "stage")
    date_hierarchy = "created_at"
    filter_horizontal = ("questions",)

    @admin.display(description="Question Count", ordering="question_count")
    def get_question_count(self, obj):
        # This will be efficient if the queryset is annotated
        if hasattr(obj, "question_count"):
            return obj.question_count
        return obj.questions.count()

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(question_count=Count("questions"))

    @admin.display(description="Results")
    def view_results_link(self, obj):
        url = (
            reverse("admin:vmlc_candidatescore_changelist") + f"?exam__id__exact={obj.pk}"
        )
        return format_html('<a href="{}" target="_blank">View Results</a>', url)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """
    Admin interface for the Question model.
    Displays question text, difficulty, and creator.
    """

    list_display = ("id", "text", "difficulty", "creator_name", "is_archived", "archived_at", "created_at")
    readonly_fields = ("created_at", "updated_at", "archived_at")
    list_filter = ("difficulty", "created_by", "is_archived")
    search_fields = ("text", "created_by__user__email")
    list_select_related = ("created_by__user",)
    date_hierarchy = "created_at"

    @admin.display(description="Created By", ordering="created_by__user__first_name")
    def creator_name(self, obj):
        if obj.created_by:
            return obj.created_by.user.get_full_name()
        return None


@admin.register(CandidateScore)
class CandidateScoreAdmin(admin.ModelAdmin):
    """
    Admin interface for the CandidateScore model.
    Displays score details per candidate and exam.
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
    search_fields = ("candidate__user__email", "exam__title", "score_submitted_by__user__email")
    list_select_related = ("candidate__user", "exam", "score_submitted_by__user")
    date_hierarchy = "recorded_at"

    @admin.display(description="Candidate", ordering="candidate__user__email")
    def candidate_email(self, obj):
        return obj.candidate.user.email

    @admin.display(description="Exam", ordering="exam__title")
    def exam_title(self, obj):
        return obj.exam.title

    @admin.display(description="Score Submitted By", ordering="score_submitted_by__user__first_name")
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
        "exam_title",
        "question_text",
        "selected_option",
        "answered_at",
    )
    readonly_fields = ("answered_at",)
    list_filter = ("candidate_score__exam", "answered_at")
    search_fields = ("candidate_score__candidate__user__email", "question__text")
    autocomplete_fields = ("question", "candidate_score")
    list_select_related = (
        "candidate_score__candidate__user",
        "candidate_score__exam",
        "question",
    )
    date_hierarchy = "answered_at"

    @admin.display(
        description="Candidate", ordering="candidate_score__candidate__user__email"
    )
    def candidate_email(self, obj):
        return obj.candidate_score.candidate.user.email

    @admin.display(description="Exam", ordering="candidate_score__exam__title")
    def exam_title(self, obj):
        return obj.candidate_score.exam.title

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


@admin.register(CandidateScoreSnapshot)
class CandidateScoreSnapshotAdmin(admin.ModelAdmin):
    """
    Admin interface for the CandidateScoreSnapshot model.
    Displays key details about each snapshot for the candidate scores.
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
    list_display = ("key", "value")
    search_fields = ("key",)
    list_editable = ("value",)
