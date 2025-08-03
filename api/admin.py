"""
Admin configuration for managing core models in the Django admin interface.

Includes custom display, filtering, and search options for:
- Candidate
- Staff
- Exam
- Question
- CandidateScore
"""

from django.contrib import admin
from django.db.models import Count
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


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "id",
        "get_user_profile",
        "is_active",
        "date_joined",
    )
    list_filter = ("is_active", "date_joined")
    search_fields = ("email", "first_name")

    @admin.display(description="User Profile")
    def get_user_profile(self, obj):
        try:
            if hasattr(obj, "candidate_profile"):
                return "Candidate"
            elif hasattr(obj, "staff_profile"):
                return "Staff"
            else:
                return "—"
        except:
            return "—"


@admin.register(UserVerification)
class UserVerificationAdmin(admin.ModelAdmin):
    """Admin interface for UserVerification model."""
    list_display = (
        "get_user_email",
        "get_user_full_name", 
        "is_pending",
        "is_verified",
        "has_profile_photo",
        "has_id_card",
        "has_verification_document",
        "date_created",
    )
    list_filter = ("is_pending", "is_verified", "date_created")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    list_select_related = ("user",)
    readonly_fields = ("date_created", "date_updated")
    date_hierarchy = "date_created"

    @admin.display(description="Email", ordering="user__email")
    def get_user_email(self, obj):
        return obj.user.email

    @admin.display(description="Full Name", ordering="user__first_name")
    def get_user_full_name(self, obj):
        return obj.user.get_full_name()

    @admin.display(description="Profile Photo", boolean=True)
    def has_profile_photo(self, obj):
        return bool(obj.profile_photo)

    @admin.display(description="ID Card", boolean=True)
    def has_id_card(self, obj):
        return bool(obj.id_card)

    @admin.display(description="Verification Doc", boolean=True)
    def has_verification_document(self, obj):
        return bool(obj.verification_document)


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    """
    Admin interface for the Candidate model.
    Displays key candidate details and allows filtering by role, verification, and active status.
    """

    list_display = (
        "get_email",
        "get_full_name",
        "school",
        "role",
        "get_primary_key",
        "is_verified",
        "is_active", 
        "date_created",
    )
    readonly_fields = ("date_created", "date_updated")
    # Fixed: Use actual database fields for filtering
    list_filter = (
        "role", 
        "user__is_active",  # Filter by user's is_active field
        "user__verification__is_verified",  # Filter by verification status
        "date_created"
    )
    search_fields = (
        "user__email", "user__first_name", "user__last_name", "school"
    )
    list_select_related = ("user", "user__verification")
    date_hierarchy = "date_created"

    @admin.display(description="Email", ordering="user__email")
    def get_email(self, obj):
        return obj.user.email

    @admin.display(description="Full Name", ordering="user__first_name")
    def get_full_name(self, obj):
        return obj.user.get_full_name()

    @admin.display(description="ID")
    def get_primary_key(self, obj):
        return obj.pk

    @admin.display(description="Verified", boolean=True, ordering="user__verification__is_verified")
    def is_verified(self, obj):
        return obj.is_verified

    @admin.display(description="Active", boolean=True, ordering="user__is_active")
    def is_active(self, obj):
        return obj.is_active


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    """
    Admin interface for the Staff model.
    Displays key staff information and allows filtering by role, verification, and active status.
    """

    list_display = (
        "get_email",
        "get_full_name",
        "role",
        "occupation",
        "get_primary_key",
        "is_verified",
        "is_active",
        "date_created",
    )
    readonly_fields = ("date_created", "date_updated")
    # Fixed: Use actual database fields for filtering
    list_filter = (
        "role", 
        "user__is_active",  # Filter by user's is_active field
        "user__verification__is_verified",  # Filter by verification status
        "date_created"
    )
    search_fields = (
        "user__email", "user__first_name", "user__last_name", "occupation"
    )
    list_select_related = ("user", "user__verification")
    date_hierarchy = "date_created"

    @admin.display(description="Email", ordering="user__email")
    def get_email(self, obj):
        return obj.user.email

    @admin.display(description="Full Name", ordering="user__first_name")
    def get_full_name(self, obj):
        return obj.user.get_full_name()

    @admin.display(description="ID")
    def get_primary_key(self, obj):
        return obj.pk

    @admin.display(description="Verified", boolean=True, ordering="user__verification__is_verified")
    def is_verified(self, obj):
        return obj.is_verified

    @admin.display(description="Active", boolean=True, ordering="user__is_active")
    def is_active(self, obj):
        return obj.is_active


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
        "date_created",
    )
    readonly_fields = ("date_created", "date_updated")
    list_filter = ("stage", "is_active", "created_by")
    search_fields = ("title", "stage")
    date_hierarchy = "date_created"
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


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """
    Admin interface for the Question model.
    Displays question text, difficulty, and creator.
    """

    list_display = ("id", "text", "difficulty", "get_creator_name", "date_created")
    readonly_fields = ("date_created", "date_updated")
    list_filter = ("difficulty", "created_by")
    search_fields = ("text", "created_by__user__email")
    list_select_related = ("created_by__user",)
    date_hierarchy = "date_created"

    @admin.display(description="Created By", ordering="created_by__user__first_name")
    def get_creator_name(self, obj):
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
        "get_candidate_email",
        "get_exam_title",
        "score",
        "date_recorded",
        "auto_score",
    )
    readonly_fields = ("date_recorded", "date_updated")
    list_filter = ("exam", "auto_score")
    search_fields = ("candidate__user__email", "exam__title")
    list_select_related = ("candidate__user", "exam")
    date_hierarchy = "date_recorded"

    @admin.display(description="Candidate", ordering="candidate__user__email")
    def get_candidate_email(self, obj):
        return obj.candidate.user.email

    @admin.display(description="Exam", ordering="exam__title")
    def get_exam_title(self, obj):
        return obj.exam.title


@admin.register(CandidateAnswer)
class CandidateAnswerAdmin(admin.ModelAdmin):
    """
    Admin interface for the CandidateAnswer model.
    Displays answers provided by each candidate in specific exams.
    """

    list_display = (
        "id",
        "get_candidate_email",
        "get_exam_title",
        "get_question_text",
        "selected_option",
        "answered_at",
    )
    readonly_fields = ("answered_at",)
    list_filter = ("candidate_score__exam", "answered_at")
    search_fields = ("candidate_score__candidate__user__email", "question__text")
    autocomplete_fields = ("question", "candidate_score")
    list_select_related = ("candidate_score__candidate__user", "candidate_score__exam", "question")
    date_hierarchy = "answered_at"

    @admin.display(description="Candidate", ordering="candidate_score__candidate__user__email")
    def get_candidate_email(self, obj):
        return obj.candidate_score.candidate.user.email

    @admin.display(description="Exam", ordering="candidate_score__exam__title")
    def get_exam_title(self, obj):
        return obj.candidate_score.exam.title

    @admin.display(description="Question", ordering="question__text")
    def get_question_text(self, obj):
        return str(obj.question)[:50] + "..." if len(str(obj.question)) > 50 else str(obj.question)


@admin.register(LeaderboardSnapshot)
class LeaderboardSnapshotAdmin(admin.ModelAdmin):
    """
    Admin interface for the LeaderboardSnapshot model.
    Displays key details about each leaderboard snapshot.
    """

    list_display = (
        "id",
        "data_summary",
        "get_published_by_name",
        "created_at",
    )
    readonly_fields = ("created_at",)
    list_filter = ("created_at", "published_by")
    search_fields = ("published_by__user__email",)
    list_select_related = ("published_by__user",)
    date_hierarchy = "created_at"

    @admin.display(description="Published By", ordering="published_by__user__email")
    def get_published_by_name(self, obj):
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
        "get_published_by_name",
        "created_at",
    )
    readonly_fields = ("created_at",)
    list_filter = ("created_at", "published_by")
    search_fields = ("published_by__user__email",)
    list_select_related = ("published_by__user",)
    date_hierarchy = "created_at"

    @admin.display(description="Published By", ordering="published_by__user__email")
    def get_published_by_name(self, obj):
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