from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum
from django import forms
from django.template.response import TemplateResponse

from identity.models import (
    Candidate,
    Staff,
    User,
    UserVerification,
    PreRegUser,
    EmailOTP,
)

# These are imported from vmlc as they are core to the application's admin functionality
from vmlc.tasks import send_mail_task
from vmlc.utils.email import create_email_html
from vmlc.utils.helpers import (
    invalidate_all_dashboard_caches,
    invalidate_all_staff_dashboards,
)
from vmlc.v2.utils import (
    invalidate_user_cache,
    invalidate_candidate_cache,
    invalidate_staff_cache,
    invalidate_staff_dashboard,
)


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


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
            recipient_emails = list(queryset.values_list("email", flat=True))

            send_mail_task.delay(
                subject=subject,
                message="",  # Plain text part is empty
                recipient_list=recipient_emails,
                html_message=html_message,
            )

            modeladmin.message_user(
                request, f"Scheduled sending emails to {len(recipient_emails)} users."
            )
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


class ChangeRoleForm(forms.Form):
    role = forms.ChoiceField(choices=[])

    def __init__(self, *args, **kwargs):
        choices = kwargs.pop("choices", [])
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = choices


@admin.action(description="Change role for selected candidates")
def change_candidate_role(modeladmin, request, queryset):
    if "apply" in request.POST:
        form = ChangeRoleForm(request.POST, choices=Candidate.Roles.choices)
        if form.is_valid():
            new_role = form.cleaned_data["role"]
            count = queryset.update(role=new_role)

            # Invalidate caches
            for candidate in queryset:
                modeladmin._invalidate_candidate_cache(candidate)

            modeladmin.message_user(
                request, f"Role changed to {new_role} for {count} candidates."
            )
            return None
    else:
        form = ChangeRoleForm(choices=Candidate.Roles.choices)

    return TemplateResponse(
        request,
        "admin/change_role_form.html",
        {
            "opts": modeladmin.model._meta,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
            "queryset": queryset,
            "form": form,
            "title": "Change Candidate Role",
            "action": "change_candidate_role",
        },
    )


@admin.action(description="Change role for selected staff")
def change_staff_role(modeladmin, request, queryset):
    if "apply" in request.POST:
        form = ChangeRoleForm(request.POST, choices=Staff.Roles.choices)
        if form.is_valid():
            new_role = form.cleaned_data["role"]
            count = queryset.update(role=new_role)

            # Invalidate caches
            for staff in queryset:
                modeladmin._invalidate_staff_cache(staff)

            modeladmin.message_user(
                request, f"Role changed to {new_role} for {count} staff members."
            )
            return None
    else:
        form = ChangeRoleForm(choices=Staff.Roles.choices)

    return TemplateResponse(
        request,
        "admin/change_role_form.html",
        {
            "opts": modeladmin.model._meta,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
            "queryset": queryset,
            "form": form,
            "title": "Change Staff Role",
            "action": "change_staff_role",
        },
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
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
    readonly_fields = ("date_joined", "id", "last_login")
    list_filter = ("is_active", "is_email_verified", "date_joined")
    search_fields = ("email", "first_name", "last_name")
    date_hierarchy = "date_joined"

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {
                "fields": (
                    "id",
                    "first_name",
                    "last_name",
                    "phone",
                    "state",
                    "profile_picture",
                    "date_joined",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_email_verified",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login",)}),
    )

    def save_model(self, request, obj, form, change):
        """Invalidate cache when user is updated."""
        super().save_model(request, obj, form, change)
        self._invalidate_user_cache(obj)

    def delete_model(self, request, obj):
        self._invalidate_user_cache(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_user_cache(obj)
        super().delete_queryset(request, queryset)

    def _invalidate_user_cache(self, user):
        """Invalidate all caches related to a user."""
        invalidate_user_cache(user.id)

    @admin.display(description="User Profile")
    def user_profile(self, obj):
        try:
            if hasattr(obj, "candidate_profile"):
                return "Candidate"
            if hasattr(obj, "staff_profile"):
                return "Staff"
        except ObjectDoesNotExist:
            return "—"
        return "—"


class UserVerificationAdminForm(forms.ModelForm):
    class Meta:
        model = UserVerification
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        is_approved = cleaned_data.get("is_approved")
        is_rejected = cleaned_data.get("is_rejected")
        rejection_reason = cleaned_data.get("rejection_reason")

        if rejection_reason and not is_rejected:
            raise forms.ValidationError(
                {
                    "rejection_reason": "A rejection reason can only be provided when rejecting an application."
                }
            )

        if is_approved and is_rejected:
            raise forms.ValidationError(
                "A verification can either be approved or rejected, not both."
            )

        if is_approved:
            cleaned_data["rejection_reason"] = ""

        return cleaned_data


@admin.register(UserVerification)
class UserVerificationAdmin(admin.ModelAdmin):
    """Simplified admin interface for UserVerification model."""

    form = UserVerificationAdminForm
    list_display = [
        "user",
        "verification_status",
        "has_face_id",
        "has_id_card",
        "has_verification_document",
        "action_by",
        "created_at",
    ]

    list_filter = [
        "is_pending",
        "is_approved",
        "is_rejected",
        "verification_document_type",
        "created_at",
    ]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    readonly_fields = ["created_at", "updated_at"]
    list_select_related = ("user", "action_by", "action_by__user")
    date_hierarchy = "created_at"

    actions = ["approve_selected", "reject_selected"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "user",
                    "is_pending",
                    "is_approved",
                    "is_rejected",
                    "rejection_reason",
                    "action_by",
                )
            },
        ),
        (
            "Files",
            {
                "fields": (
                    "face_id",
                    "id_card",
                    "verification_document",
                    "verification_document_type",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_verification_cache(obj)

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        self._invalidate_verification_cache(obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_verification_cache(obj)
        super().delete_queryset(request, queryset)

    def _invalidate_verification_cache(self, verification):
        user = verification.user
        invalidate_user_cache(user.id)
        if hasattr(user, "candidate_profile"):
            invalidate_candidate_cache(user.candidate_profile.id, user.id)
        invalidate_staff_dashboard()

    def _invalidate_queryset_cache(self, queryset):
        for verification in queryset:
            self._invalidate_verification_cache(verification)

    @admin.display(description="Status")
    def verification_status(self, obj):
        """Display verification status with color coding."""
        if obj.is_approved:
            return format_html('<span style="color: green;">✓ Verified</span>')
        if obj.is_pending:
            return format_html('<span style="color: orange;">⏳ Pending</span>')
        if obj.is_rejected:
            return format_html('<span style="color: red;">❌ Rejected</span>')
        return "—"

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
        self._invalidate_queryset_cache(queryset)

        users_to_notify = [v.user for v in queryset]
        count = queryset.update(
            is_approved=True, is_pending=False, is_rejected=False, rejection_reason=""
        )

        for user in users_to_notify:
            base_message = "Your verification details have been approved.\n\n"
            action_content = (
                'Kindly proceed to take the "Tour" of Verboheit MLC Portal.\n\n'
            )
            footer = "Best Regards,\nManagement."
            email_message = base_message + action_content + footer

            send_mail_task.delay(
                subject="Your User Verification Status",
                message=email_message,
                recipient_list=[user.email],
            )

        self.message_user(request, f"{count} verification(s) approved.")

    @admin.action(description="Reject selected verifications")
    def reject_selected(self, request, queryset):
        """Reject selected verification requests."""
        self._invalidate_queryset_cache(queryset)

        users_to_notify = [v.user for v in queryset]
        count = queryset.update(is_approved=False, is_pending=False, is_rejected=True)

        for user in users_to_notify:
            base_message = "Your verification details have been rejected.\n\n"
            action_content = "If you have any questions, please contact support.\n\n"
            footer = "Best Regards,\nManagement."
            email_message = base_message + action_content + footer

            send_mail_task.delay(
                subject="Your User Verification Status",
                message=email_message,
                recipient_list=[user.email],
            )

        self.message_user(request, f"{count} verification(s) rejected.")


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    """
    Admin interface for the Candidate model.
    Displays key candidate details and allows filtering by role, verification, and active status.
    """

    actions = [change_candidate_role]
    list_display = (
        "email",
        "full_name",
        "school_name",
        "school_type",
        "current_class",
        "role",
        "total_score_display",
        "get_primary_key",
        "exams_taken",
        "is_user_verified",
        "is_active",
        "created_at",
    )
    readonly_fields = ("created_at", "updated_at")
    list_filter = (
        "role",
        "school_type",
        "current_class",
        "user__is_active",
        "user__verification__is_approved",
        "created_at",
    )
    search_fields = ("user__email", "user__first_name", "user__last_name", "school_name")
    list_select_related = ("user", "user__verification")
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_candidate_cache(obj)

    def delete_model(self, request, obj):
        self._invalidate_candidate_cache(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_candidate_cache(obj)
        super().delete_queryset(request, queryset)

    def _invalidate_candidate_cache(self, candidate):
        invalidate_candidate_cache(candidate.id, candidate.user.id)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            total_score=Sum("results__score"),
            exams_taken_count=Count("results", distinct=True),
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
        description="Verified", boolean=True, ordering="user__verification__is_approved"
    )
    def is_user_verified(self, obj):
        return obj.is_user_verified

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

    actions = [change_staff_role]
    list_display = (
        "email",
        "full_name",
        "role",
        "occupation",
        "get_primary_key",
        "is_user_verified",
        "is_active",
        "created_at",
        "created_by_name",
    )
    readonly_fields = ("created_at", "updated_at")
    list_filter = (
        "role",
        "user__is_active",
        "user__verification__is_approved",
        "created_at",
    )
    search_fields = ("user__email", "user__first_name", "user__last_name", "occupation")
    list_select_related = ("user", "user__verification", "created_by", "created_by__user")
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_staff_cache(obj)

    def delete_model(self, request, obj):
        self._invalidate_staff_cache(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_staff_cache(obj)
        super().delete_queryset(request, queryset)

    def _invalidate_staff_cache(self, staff):
        invalidate_staff_cache(staff.user.id)

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
        description="Verified", boolean=True, ordering="user__verification__is_approved"
    )
    def is_user_verified(self, obj):
        return obj.is_user_verified

    @admin.display(description="Active", boolean=True, ordering="user__is_active")
    def is_active(self, obj):
        return obj.is_active

    @admin.display(description="Invited By", ordering="created_by__user__first_name")
    def created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.user.get_full_name()
        return None


@admin.register(PreRegUser)
class PreRegUserAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "interest_type", "created_at")
    list_filter = ("interest_type", "created_at")
    search_fields = ("full_name", "email", "phone")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "otp", "created_at", "expires_at", "is_expired_display")
    list_filter = ("created_at", "expires_at")
    search_fields = ("user__email", "otp")
    list_select_related = ("user",)
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

    @admin.display(description="Is Expired", boolean=True)
    def is_expired_display(self, obj):
        return obj.is_expired()