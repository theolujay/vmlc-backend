"""
Admin configuration for managing core models in the Django admin interface.

Includes custom display, filtering, and search options for:
- Candidate
- Staff
- Exam
- Question
- CandidateScore
"""


from django.forms import widgets
from django.db import models
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.forms import widgets
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
        "is_email_verified",
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
    """Admin interface for UserVerification model with enhanced security and functionality."""
    
    list_display = [
        'user_info',
        'verification_status', 
        'has_profile_photo',
        'has_id_card', 
        'has_verification_document',
        'date_created',
        'admin_actions'
    ]
    
    list_filter = [
        'is_pending', 
        'is_verified', 
        'date_created',
        'date_updated'
    ]
    
    search_fields = [
        'user__email', 
        'user__first_name', 
        'user__last_name'
    ]
    
    readonly_fields = [
        'user',
        'date_created', 
        'date_updated',
        'profile_photo_preview',
        'secure_file_links'
    ]
    
    list_select_related = ('user',)
    date_hierarchy = 'date_created'
    
    actions = ["approve_selected_verifications", "reject_selected_verifications"]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'date_created', 'date_updated')
        }),
        ('Verification Status', {
            'fields': ('is_pending', 'is_verified'),
        }),
        ('Uploaded Files', {
            'fields': (
                'profile_photo', 
                'profile_photo_preview',
                'id_card',
                'verification_document',
                'secure_file_links'
            ),
            'description': 'Profile photo is public. Other documents are private and require secure access.'
        }),
    )
    
    def get_queryset(self, request):
        """Optimize database queries by pre-fetching related user data."""
        return super().get_queryset(request).select_related('user')

    # --- Display Methods ---

    @admin.display(description='User', ordering='user__first_name')
    def user_info(self, obj):
        """Display user's full name and email with a link to their user admin page."""
        user_admin_url = reverse('admin:api_user_change', args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a><br><small>{}</small>',
            user_admin_url,
            obj.user.get_full_name() or obj.user.email,
            obj.user.email
        )

    @admin.display(description='Status')
    def verification_status(self, obj):
        """Display verification status with intuitive color-coding."""
        if obj.is_verified:
            return format_html('<span style="color: green; font-weight: bold;">✓ Verified</span>')
        elif obj.is_pending:
            return format_html('<span style="color: orange; font-weight: bold;">⏳ Pending</span>')
        else:
            return format_html('<span style="color: red;">❌ Not Verified</span>')

    @admin.display(description='Profile Photo', boolean=True)
    def has_profile_photo(self, obj):
        return bool(obj.profile_photo)

    @admin.display(description='ID Card', boolean=True)
    def has_id_card(self, obj):
        return bool(obj.id_card)

    @admin.display(description='Verification Doc', boolean=True)
    def has_verification_document(self, obj):
        return bool(obj.verification_document)

    @admin.display(description='Profile Photo Preview')
    def profile_photo_preview(self, obj):
        """Show a preview of the profile photo in the admin form."""
        if obj.profile_photo and obj.profile_photo.url:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 200px; max-height: 200px; border-radius: 4px;" /></a>',
                obj.profile_photo.url, obj.profile_photo.url
            )
        return "No photo uploaded."

    @admin.display(description='Private File Access')
    def secure_file_links(self, obj):
        """Generate secure, time-sensitive links for private documents."""
        links = []
        if obj.id_card:
            secure_url = self._get_admin_secure_url(obj, 'id_card')
            links.append(format_html(
                '<strong>ID Card:</strong> <a href="{}" target="_blank" class="button">View Securely</a>', secure_url
            ))
        else:
            links.append('<strong>ID Card:</strong> Not uploaded')
        
        if obj.verification_document:
            secure_url = self._get_admin_secure_url(obj, 'verification_document')
            links.append(format_html(
                '<strong>Verification Document:</strong> <a href="{}" target="_blank" class="button">View Securely</a>', secure_url
            ))
        else:
            links.append('<strong>Verification Document:</strong> Not uploaded')
        
        return format_html('<br><br>'.join(links))

    # --- Action Methods & URL Handling ---

    def _get_admin_secure_url(self, obj, file_type):
        """Generate a robust, secure access URL for a private file using reverse lookup."""
        return reverse('admin-verification-document', args=[file_type, obj.user.id])

    @admin.display(description='Actions')
    def admin_actions(self, obj):
        """Display approve/reject buttons for pending verifications."""
        if obj.is_pending and not obj.is_verified:
            approve_url = reverse('admin:user-verification-approve', args=[obj.pk])
            reject_url = reverse('admin:user-verification-reject', args=[obj.pk])
            return format_html(
                '<a href="{}" class="button" style="background-color: #81C784;">Approve</a>&nbsp;'
                '<a href="{}" class="button" style="background-color: #E57373;">Reject</a>',
                approve_url, reject_url
            )
        return "N/A"

    def get_urls(self):
        """Add custom URLs for the approve/reject actions."""
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/approve/', self.admin_site.admin_view(self.approve_view), name='user-verification-approve'),
            path('<path:object_id>/reject/', self.admin_site.admin_view(self.reject_view), name='user-verification-reject'),
        ]
        return custom_urls + urls

    def approve_view(self, request, object_id):
        """Handle the 'approve' action for a single verification object."""
        verification = self.get_object(request, object_id)
        if verification:
            verification.is_verified = True
            verification.is_pending = False
            verification.save()
            self.message_user(request, f"User '{verification.user.get_full_name()}' has been verified.", messages.SUCCESS)
        return HttpResponseRedirect("../../")

    def reject_view(self, request, object_id):
        """Handle the 'reject' action for a single verification object."""
        verification = self.get_object(request, object_id)
        if verification:
            verification.is_verified = False
            verification.is_pending = False
            verification.save()
            self.message_user(request, f"Verification for '{verification.user.get_full_name()}' has been rejected.", messages.WARNING)
        return HttpResponseRedirect("../../")

    # --- Bulk Actions ---

    @admin.action(description="Approve selected verifications")
    def approve_selected_verifications(self, request, queryset):
        """Bulk action to approve multiple verification requests."""
        updated_count = queryset.update(is_verified=True, is_pending=False)
        self.message_user(request, f'{updated_count} user(s) have been successfully verified.', messages.SUCCESS)

    @admin.action(description="Reject selected verifications")
    def reject_selected_verifications(self, request, queryset):
        """Bulk action to reject multiple verification requests."""
        updated_count = queryset.update(is_verified=False, is_pending=False)
        self.message_user(request, f'{updated_count} verification(s) have been rejected.', messages.WARNING)

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
        "total_score",
        "get_primary_key",
        "exams_taken",
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
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.with_scores()

    @admin.display(description="Total Score", ordering="total_score")
    def total_score(self, obj):
        return obj.total_score
    
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
    
    @admin.display(description="Exams Taken")
    def exams_taken(self, obj):
        return obj.exams_taken.count() if hasattr(obj, 'exams_taken') else 0


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
        "view_results_link",
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
    
    @admin.display(description="Results")
    def view_results_link(self, obj):
        from django.utils.html import format_html
        from django.urls import reverse

        url = reverse("api:api-exam-results", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">View Results</a>', url)


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
