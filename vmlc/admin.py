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
            user_ids = list(queryset.values_list('id', flat=True))

            html_template = '''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" lang="en">
<head>
<title></title>
<meta charset="UTF-8" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<!--[if !mso]>-->
<meta http-equiv="X-UA-Compatible" content="IE=edge" />
<!--<![endif]-->
<meta name="x-apple-disable-message-reformatting" content="" />
<meta content="target-densitydpi=device-dpi" name="viewport" />
<meta content="true" name="HandheldFriendly" />
<meta content="width=device-width" name="viewport" />
<meta name="format-detection" content="telephone=no, date=no, address=no, email=no, url=no" />
<style type="text/css">
table {
border-collapse: separate;
table-layout: fixed;
mso-table-lspace: 0pt;
mso-table-rspace: 0pt
}
table td {
border-collapse: collapse
}
.ExternalClass {
width: 100%
}
.ExternalClass,
.ExternalClass p,
.ExternalClass span,
.ExternalClass font,
.ExternalClass td,
.ExternalClass div {
line-height: 100%
}
body, a, li, p, h1, h2, h3 {
-ms-text-size-adjust: 100%;
-webkit-text-size-adjust: 100%;
}
html {
-webkit-text-size-adjust: none !important
}
body {
min-width: 100%;
Margin: 0px;
padding: 0px;
}
body, #innerTable {
-webkit-font-smoothing: antialiased;
-moz-osx-font-smoothing: grayscale
}
#innerTable img+div {
display: none;
display: none !important
}
img {
Margin: 0;
padding: 0;
-ms-interpolation-mode: bicubic
}
h1, h2, h3, p, a {
line-height: inherit;
overflow-wrap: normal;
white-space: normal;
word-break: break-word
}
a {
text-decoration: none
}
h1, h2, h3, p {
min-width: 100%!important;
width: 100%!important;
max-width: 100%!important;
display: inline-block!important;
border: 0;
padding: 0;
margin: 0
}
a[x-apple-data-detectors] {
color: inherit !important;
text-decoration: none !important;
font-size: inherit !important;
font-family: inherit !important;
font-weight: inherit !important;
line-height: inherit !important
}
u + #body a {
color: inherit;
text-decoration: none;
font-size: inherit;
font-family: inherit;
font-weight: inherit;
line-height: inherit;
}
a[href^="mailto"],
a[href^="tel"],
a[href^="sms"] {
color: inherit;
text-decoration: none
}
</style>
<style type="text/css">
 @media/** (min-width: 481px) {
.hd { display: none!important }
}
</style>
<style type="text/css">
 @media/** (max-width: 480px) {
.hm { display: none!important }
}
</style>
<style type="text/css">
 @media/** (max-width: 480px) {
.t35,.t40{mso-line-height-alt:0px!important;line-height:0!important;display:none!important}.t36{padding:40px!important;border-radius:0!important}.t26{text-align:center!important}.t25{vertical-align:top!important;width:auto!important;max-width:100%!important}
}
</style>
<!--[if !mso]>-->
<link href="https://fonts.googleapis.com/css2?family=Arimo:wght @700&amp;family=Roboto+Mono:wght @600&amp;family=Open+Sans:ital,wght @0,400;0,600;1,400&amp;display=swap" rel="stylesheet" type="text/css" />
<!--<![endif]-->
<!--[if mso]>
<xml>
<o:OfficeDocumentSettings>
<o:AllowPNG/>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
<![endif]-->
</head>
<body id="body" class="t43" style="min-width:100%;Margin:0px;padding:0px;background-color:#FFFFFF;"><div class="t42" style="background-color:#FFFFFF;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" align="center"><tr><td class="t41" style="font-size:0;line-height:0;mso-line-height-rule:exactly;background-color:#FFFFFF;" valign="top" align="center">
<!--[if mso]>
<v:background xmlns:v="urn:schemas-microsoft-com:vml" fill="true" stroke="false">
<v:fill color="#FFFFFF"/>
</v:background>
<![endif]-->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" align="center" id="innerTable"><tr><td><div class="t35" style="mso-line-height-rule:exactly;mso-line-height-alt:50px;line-height:50px;font-size:1px;display:block;">&nbsp;&nbsp;</div></td></tr><tr><td align="center">
<table class="t39" role="presentation" cellpadding="0" cellspacing="0" style="Margin-left:auto;Margin-right:auto;"><tr><td width="600" class="t38" style="width:600px;">
<table class="t37" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t36" style="border:1px solid #EBEBEB;overflow:hidden;background-color:#FFFFFF;padding:44px 42px 32px 42px;border-radius:3px 3px 3px 3px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100% !important;"><tr><td align="left">
<table class="t4" role="presentation" cellpadding="0" cellspacing="0" style="Margin-right:auto;"><tr><td width="79" class="t3" style="width:79px;">
<table class="t2" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t1"><div style="font-size:0px;"><img class="t0" style="display:block;border:0;height:auto;width:100%;Margin:0;max-width:100%;" width="79" height="17.643333333333334" alt="" src="https://78cb1dc4-6156-4b00-a1ab-aa0c1ed6c8f8.b-cdn.net/e/629f70ca-d841-4218-8ebc-d3a0670039d8/63418ce1-d325-4122-9886-732d6916f714.png"/></div></td></tr></table>
</td></tr></table>
</td></tr><tr><td><div class="t5" style="mso-line-height-rule:exactly;mso-line-height-alt:10px;line-height:10px;font-size:1px;display:block;">&nbsp;&nbsp;</div></td></tr><tr><td align="center">
<table class="t10" role="presentation" cellpadding="0" cellspacing="0" style="Margin-left:auto;Margin-right:auto;"><tr><td width="514" class="t9" style="width:600px;">
<table class="t8" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t7" style="border-bottom:1px solid #EFF1F4;padding:0 0 12px 0;"><h1 class="t6" style="margin:0;Margin:0;font-family:Arimo,BlinkMacSystemFont,Segoe UI,Helvetica Neue,Arial,sans-serif;line-height:20px;font-weight:700;font-style:normal;font-size:20px;text-decoration:none;text-transform:none;letter-spacing:2px;direction:ltr;color:#141414;text-align:left;mso-line-height-rule:exactly;">Your OTP Code</h1></td></tr></table>
</td></tr></table>
</td></tr><tr><td><div class="t11" style="mso-line-height-rule:exactly;mso-line-height-alt:15px;line-height:15px;font-size:1px;display:block;">&nbsp;&nbsp;</div></td></tr><tr><td align="center">
<table class="t16" role="presentation" cellpadding="0" cellspacing="0" style="Margin-left:auto;Margin-right:auto;"><tr><td width="305" class="t15" style="width:305px;">
<table class="t14" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t13" style="padding:20px 0 40px 0;"><p class="t12" style="margin:0;Margin:0;font-family:Roboto Mono,monospace;line-height:25px;font-weight:600;font-style:normal;font-size:40px;text-decoration:none;text-transform:none;letter-spacing:2px;direction:ltr;color:#141414;text-align:center;mso-line-height-rule:exactly;mso-text-raise:-4px;">123456</p></td></tr></table>
</td></tr></table>
</td></tr><tr><td align="center">
<table class="t21" role="presentation" cellpadding="0" cellspacing="0" style="Margin-left:auto;Margin-right:auto;"><tr><td width="514" class="t20" style="width:600px;">
<table class="t19" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t18"><p class="t17" style="margin:0;Margin:0;font-family:Open Sans,BlinkMacSystemFont,Segoe UI,Helvetica Neue,Arial,sans-serif;line-height:25px;font-weight:400;font-style:italic;font-size:12px;text-decoration:none;text-transform:none;letter-spacing:-0.1px;direction:ltr;color:#141414;text-align:right;mso-line-height-rule:exactly;mso-text-raise:4px;">...expires in 10 minutes.</p></td></tr></table>
</td></tr></table>
</td></tr><tr><td><div class="t30" style="mso-line-height-rule:exactly;mso-line-height-alt:10px;line-height:10px;font-size:1px;display:block;">&nbsp;&nbsp;</div></td></tr><tr><td align="center">
<table class="t34" role="presentation" cellpadding="0" cellspacing="0" style="Margin-left:auto;Margin-right:auto;"><tr><td width="514" class="t33" style="width:600px;">
<table class="t32" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;"><tr><td class="t31" style="border-top:1px solid #DFE1E4;padding:24px 0 0 0;"><div class="t29" style="width:100%;text-align:center;"><div class="t28" style="display:inline-block;"><table class="t27" role="presentation" cellpadding="0" cellspacing="0" align="center" valign="top">
<tr class="t26"><td></td><td class="t25" valign="top">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="t24" style="width:auto;"><tr><td class="t23" style="background-color:#FFFFFF;text-align:center;line-height:20px;mso-line-height-rule:exactly;mso-text-raise:2px;"><span class="t22" style="display:block;margin:0;Margin:0;font-family:Open Sans,BlinkMacSystemFont,Segoe UI,Helvetica Neue,Arial,sans-serif;line-height:20px;font-weight:600;font-style:normal;font-size:14px;text-decoration:none;direction:ltr;color:#222222;text-align:center;mso-line-height-rule:exactly;mso-text-raise:2px;">Verboheit Consulting</span></td></tr></table>
</td>
<td></td></tr>
</table></div></div></td></tr></table>
</td></tr></table>
</td></tr></table></td></tr></table>
</td></tr></table>
</td></tr><tr><td><div class="t40" style="mso-line-height-rule:exactly;mso-line-height-alt:50px;line-height:50px;font-size:1px;display:block;">&nbsp;&nbsp;</div></td></tr></table></td></tr></table></div><div class="gmail-fix" style="display: none; white-space: nowrap; font: 15px courier; line-height: 0;">&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;</div></body>
</html>'''

            # Replace placeholders
            html_message = html_template.replace("Your OTP Code", subject)
            html_message = html_message.replace(
                '<p class="t12" style="margin:0;Margin:0;font-family:Roboto Mono,monospace;line-height:25px;font-weight:600;font-style:normal;font-size:40px;text-decoration:none;text-transform:none;letter-spacing:2px;direction:ltr;color:#141414;text-align:center;mso-line-height-rule:exactly;mso-text-raise:-4px;">123456</p>',
                f'<p style="font-family:Open Sans,BlinkMacSystemFont,Segoe UI,Helvetica Neue,Arial,sans-serif; line-height: 25px; font-size: 16px; color: #141414; text-align: left; white-space: pre-wrap; word-break: break-word;">{message}</p>'
            )
            html_message = html_message.replace(
                '<p class="t17" style="margin:0;Margin:0;font-family:Open Sans,BlinkMacSystemFont,Segoe UI,Helvetica Neue,Arial,sans-serif;line-height:25px;font-weight:400;font-style:italic;font-size:12px;text-decoration:none;text-transform:none;letter-spacing:-0.1px;direction:ltr;color:#141414;text-align:right;mso-line-height-rule:exactly;mso-text-raise:4px;">...expires in 10 minutes.</p>',
                ''
            )

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
    )
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

    list_display = ("id", "text", "difficulty", "creator_name", "created_at")
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("difficulty", "created_by")
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
    )
    readonly_fields = ("recorded_at", "updated_at")
    list_filter = ("exam", "auto_score")
    search_fields = ("candidate__user__email", "exam__title")
    list_select_related = ("candidate__user", "exam")
    date_hierarchy = "recorded_at"

    @admin.display(description="Candidate", ordering="candidate__user__email")
    def candidate_email(self, obj):
        return obj.candidate.user.email

    @admin.display(description="Exam", ordering="exam__title")
    def exam_title(self, obj):
        return obj.exam.title


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
