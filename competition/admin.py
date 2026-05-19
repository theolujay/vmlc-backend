from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from core.utils.exceptions import ValidationError
from core.utils.cache import (
    invalidate_score_boards,
    invalidate_candidate_cache,
    invalidate_exam_cache,
)
from core.utils.helpers import invalidate_all_dashboard_caches
from .models import (
    Competition,
    Stage,
    StageExam,
    Enrollment,
    EnrollmentStageProgress,
    RankingSnapshot,
    RankingSnapshotEntry,
    LeagueLeaderboard,
    LeagueLeaderboardEntry,
)
from identity.admin import send_passcodes_via_email, send_passcodes_via_sms



class StageInline(admin.TabularInline):
    model = Stage
    extra = 0
    ordering = ["order"]


class StageExamInline(admin.TabularInline):
    model = StageExam
    extra = 0


class RankingSnapshotEntryInline(admin.TabularInline):
    model = RankingSnapshotEntry
    extra = 0
    raw_id_fields = ["candidate", "enrollment"]
    fields = [
        "candidate",
        "enrollment",
        "exam_score",
        "rank",
        "time_used",
        "proctoring_status",
        "violation_score",
    ]
    readonly_fields = ["proctoring_status", "violation_score"]


class LeagueLeaderboardEntryInline(admin.TabularInline):
    model = LeagueLeaderboardEntry
    extra = 0
    raw_id_fields = ["candidate", "enrollment"]


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "edition",
        "status_display",
        "start_date",
        "end_date",
        "enrollment_count",
        "created_at",
    )
    list_filter = ("status", "edition")
    search_fields = ("name", "edition")
    inlines = [StageInline]
    date_hierarchy = "start_date"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(enroll_count=Count("enrollments", distinct=True))
        )

    @admin.display(description="Enrollments", ordering="enroll_count")
    def enrollment_count(self, obj):
        return obj.enroll_count

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_all_dashboard_caches()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        invalidate_all_dashboard_caches()

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        invalidate_all_dashboard_caches()

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        colors = {
            Competition.Status.UPCOMING: "orange",
            Competition.Status.ACTIVE: "green",
            Competition.Status.CONCLUDED: "gray",
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, "black"),
            obj.get_status_display(),
        )


from django import forms


class StageAdminForm(forms.ModelForm):
    advancement_mode = forms.ChoiceField(
        choices=[
            ("top_n", "Top N (Fixed Count)"),
            ("top_percent", "Top Percent (Percentage)"),
        ],
        required=False,
        help_text="Select how candidates advance to the next stage.",
    )
    advancement_value = forms.FloatField(
        required=False,
        help_text="The value for the advancement mode (Integer for Top N, Decimal 0-1 for Top Percent).",
    )

    class Meta:
        model = Stage
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.config:
            policy = self.instance.config.get("advancement_policy", {})
            self.fields["advancement_mode"].initial = policy.get("mode")
            self.fields["advancement_value"].initial = policy.get("value")

    def save(self, commit=True):
        instance = super().save(commit=False)
        mode = self.cleaned_data.get("advancement_mode")
        value = self.cleaned_data.get("advancement_value")

        if not instance.config:
            instance.config = {}

        if mode and value is not None:
            instance.config["advancement_policy"] = {"mode": mode, "value": value}
            # Remove old promotion_cutoff if it exists to maintain consistency
            if "promotion_cutoff" in instance.config:
                del instance.config["promotion_cutoff"]

        if commit:
            instance.save()
        return instance


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    form = StageAdminForm
    list_display = (
        "competition",
        "type",
        "order",
        "get_advancement_policy",
        "exam_count",
        "created_at",
    )
    list_filter = ("competition", "type")
    search_fields = ("type", "competition__name")
    ordering = ("competition", "order")
    inlines = [StageExamInline]
    list_select_related = ("competition",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(e_count=Count("stage_exams", distinct=True))
        )

    @admin.display(description="Exams", ordering="e_count")
    def exam_count(self, obj):
        return obj.e_count

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_all_dashboard_caches()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        invalidate_all_dashboard_caches()

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        invalidate_all_dashboard_caches()

    @admin.display(description="Advancement Policy")
    def get_advancement_policy(self, obj):
        policy = obj.config.get("advancement_policy")
        if not policy:
            return "-"
        mode = policy.get("mode")
        value = policy.get("value")
        if mode == "top_n":
            return f"Top {int(value)} candidates"
        elif mode == "top_percent":
            return f"Top {float(value)*100}% of candidates"
        return f"{mode}: {value}"


@admin.register(StageExam)
class StageExamAdmin(admin.ModelAdmin):
    list_display = ("competition_stage", "round", "get_exam", "is_active")
    list_filter = (
        "competition_stage__competition",
        "competition_stage__type",
        "is_active",
    )
    list_select_related = (
        "competition_stage",
        "competition_stage__competition",
        "exam",
    )
    autocomplete_fields = ["competition_stage"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_all_dashboard_caches()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        invalidate_all_dashboard_caches()

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        invalidate_all_dashboard_caches()

    @admin.display(description="Exam")
    def get_exam(self, obj):
        if hasattr(obj, "exam"):
            url = reverse("admin:vmlc_exam_change", args=[obj.exam.id])
            return format_html('<a href="{}">{}</a>', url, obj.exam)
        return "-"


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    actions = [send_passcodes_via_email, send_passcodes_via_sms]
    list_display = (
        "candidate_email",
        "candidate_full_name",
        "competition",
        "status_display",
        "current_stage",
        "joined_at",
    )
    list_filter = ("competition", "status", "current_stage")
    search_fields = (
        "candidate__user__email",
        "candidate__user__first_name",
        "candidate__user__last_name",
    )
    autocomplete_fields = ["candidate", "competition", "current_stage"]
    list_select_related = (
        "candidate",
        "candidate__user",
        "competition",
        "current_stage",
    )
    date_hierarchy = "joined_at"

    @admin.display(description="Candidate Email", ordering="candidate__user__email")
    def candidate_email(self, obj):
        return obj.candidate.user.email

    @admin.display(description="Full Name", ordering="candidate__user__first_name")
    def candidate_full_name(self, obj):
        return obj.candidate.user.get_full_name()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_candidate_cache(obj.candidate)

    def delete_model(self, request, obj):
        self._invalidate_candidate_cache(obj.candidate)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_candidate_cache(obj.candidate)
        super().delete_queryset(request, queryset)

    def _invalidate_candidate_cache(self, candidate):
        invalidate_candidate_cache(candidate.pk, candidate.user.id)

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        colors = {
            Enrollment.Status.ACTIVE: "green",
            Enrollment.Status.ELIMINATED: "red",
            # Enrollment.Status.WITHDRAWN: "orange",
            Enrollment.Status.DISQUALIFIED: "darkred",
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, "black"),
            obj.get_status_display(),
        )


@admin.register(EnrollmentStageProgress)
class EnrollmentStageProgressAdmin(admin.ModelAdmin):
    list_display = ("candidate_email", "stage", "status_display", "updated_at")
    list_filter = ("stage__competition", "stage", "status")
    search_fields = ("enrollment__candidate__user__email",)
    autocomplete_fields = ["enrollment", "stage"]
    list_select_related = (
        "enrollment",
        "enrollment__candidate",
        "enrollment__candidate__user",
        "stage",
    )
    date_hierarchy = "updated_at"

    @admin.display(
        description="Candidate Email", ordering="enrollment__candidate__user__email"
    )
    def candidate_email(self, obj):
        return obj.enrollment.candidate.user.email

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_candidate_cache(obj.enrollment.candidate)

    def delete_model(self, request, obj):
        self._invalidate_candidate_cache(obj.enrollment.candidate)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_candidate_cache(obj.enrollment.candidate)
        super().delete_queryset(request, queryset)

    def _invalidate_candidate_cache(self, candidate):
        invalidate_candidate_cache(candidate.pk, candidate.user.id)

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        colors = {
            EnrollmentStageProgress.Status.PENDING: "orange",
            EnrollmentStageProgress.Status.IN_PROGRESS: "blue",
            EnrollmentStageProgress.Status.COMPLETED: "green",
            EnrollmentStageProgress.Status.DISCONTINUED: "red",
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, "black"),
            obj.get_status_display(),
        )


@admin.register(RankingSnapshot)
class RankingSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "competition",
        "stage",
        "round",
        "exam_link",
        "created_at",
        "is_active",
        "is_published",
        "published_at",
        "facilitator_system",
    )
    list_filter = ("competition", "stage", "facilitator_system", "is_published")
    search_fields = ("exam__description", "competition__name")
    autocomplete_fields = ["competition", "exam"]
    inlines = [RankingSnapshotEntryInline]
    list_select_related = ("competition", "exam")
    date_hierarchy = "published_at"
    actions = [
        "publish_rankings",
        "unpublish_rankings",
        "activate_rankings",
        "deactivate_rankings",
        "export_rankings_as_csv",
    ]

    @admin.display(description="Exam")
    def exam_link(self, obj):
        if obj.exam:
            url = reverse("admin:vmlc_exam_change", args=[obj.exam.id])
            return format_html('<a href="{}">{}</a>', url, obj.exam)
        return "-"

    @admin.action(description="Publish selected rankings")
    def publish_rankings(self, request, queryset):
        from django.utils import timezone

        # Capture exam IDs before update
        exam_ids = list(queryset.values_list("exam_id", flat=True))
        count = queryset.update(is_published=True, published_at=timezone.now())
        invalidate_all_dashboard_caches()
        for e_id in exam_ids:
            if e_id:
                invalidate_exam_cache(e_id)
        self.message_user(request, f"{count} rankings published.")

    @admin.action(description="Unpublish selected rankings")
    def unpublish_rankings(self, request, queryset):
        # Capture exam IDs before update
        exam_ids = list(queryset.values_list("exam_id", flat=True))
        count = queryset.update(is_published=False, published_at=None)
        invalidate_all_dashboard_caches()
        for e_id in exam_ids:
            if e_id:
                invalidate_exam_cache(e_id)
        self.message_user(request, f"{count} rankings unpublished.")

    @admin.action(description="Activate selected ranking")
    def activate_rankings(self, request, queryset):
        exam_ids = list(queryset.values_list("exam_id", flat=True))
        count = queryset.update(is_active=True)
        invalidate_all_dashboard_caches()
        for e_id in exam_ids:
            if e_id:
                invalidate_exam_cache(e_id)
        self.message_user(request, f"{count} rankings deactivated.")

    @admin.action(description="Deactivate selected rankings")
    def deactivate_rankings(self, request, queryset):
        exam_ids = list(queryset.values_list("exam_id", flat=True))
        count = queryset.update(is_active=False)
        invalidate_all_dashboard_caches()
        for e_id in exam_ids:
            if e_id:
                invalidate_exam_cache(e_id)
        self.message_user(request, f"{count} rankings deactivated.")

    @admin.action(description="Export selected Ranking Snapshots as CSV")
    def export_rankings_as_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="ranking_snapshots.csv"'
        writer = csv.writer(response)

        writer.writerow(
            [
                "Snapshot ID",
                "Snapshot Created At",
                "Competition",
                "Stage",
                "Round",
                "Exam Title",
                "Candidate Email",
                "Candidate Full Name",
                "Exam Score",
                "Rank",
                "Percentile",
            ]
        )

        snapshots = queryset.select_related("exam", "competition").prefetch_related(
            "entries__candidate__user"
        )

        for snapshot in snapshots:
            for entry in snapshot.entries.all():
                candidate = entry.candidate
                user = candidate.user
                writer.writerow(
                    [
                        snapshot.id,
                        snapshot.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        snapshot.competition.name,
                        snapshot.get_stage_display(),
                        snapshot.round if snapshot.round is not None else "",
                        snapshot.exam.get_title(),
                        user.email,
                        user.get_full_name(),
                        entry.exam_score,
                        entry.rank,
                        entry.percentile,
                    ]
                )

        return response

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_all_dashboard_caches()
        if obj.exam_id:
            invalidate_exam_cache(obj.exam_id)

    def delete_model(self, request, obj):
        exam_id = obj.exam_id
        super().delete_model(request, obj)
        invalidate_all_dashboard_caches()
        if exam_id:
            invalidate_exam_cache(exam_id)

    def delete_queryset(self, request, queryset):
        exam_ids = list(queryset.values_list("exam_id", flat=True))
        super().delete_queryset(request, queryset)
        invalidate_all_dashboard_caches()
        for e_id in exam_ids:
            if e_id:
                invalidate_exam_cache(e_id)


@admin.register(RankingSnapshotEntry)
class RankingSnapshotEntryAdmin(admin.ModelAdmin):
    list_display = (
        "ranking_snapshot",
        "candidate_email",
        "exam_score",
        "rank",
        "proctoring_status",
        "violation_score",
        "percentile",
    )
    list_filter = (
        "ranking_snapshot__competition",
        "ranking_snapshot__stage",
        "proctoring_status",
    )
    search_fields = (
        "candidate__user__email",
        "candidate__user__first_name",
        "candidate__user__last_name",
    )
    autocomplete_fields = ["ranking_snapshot", "candidate", "enrollment"]
    list_select_related = (
        "ranking_snapshot",
        "candidate",
        "candidate__user",
        "enrollment",
    )

    @admin.display(description="Candidate", ordering="candidate__user__email")
    def candidate_email(self, obj):
        return obj.candidate.user.email

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_entry_caches(obj)

    def delete_model(self, request, obj):
        self._invalidate_entry_caches(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        # Capture snapshots before deletion
        snapshots = list(
            queryset.select_related("ranking_snapshot").values_list(
                "ranking_snapshot__exam_id", "candidate_id", "candidate__user_id"
            )
        )
        super().delete_queryset(request, queryset)
        for exam_id, candidate_id, user_id in snapshots:
            if exam_id:
                invalidate_exam_cache(exam_id)
            invalidate_candidate_cache(candidate_id, user_id)

    def _invalidate_entry_caches(self, obj):
        invalidate_candidate_cache(obj.candidate.pk, obj.candidate.user.id)
        if obj.ranking_snapshot and obj.ranking_snapshot.exam_id:
            invalidate_exam_cache(obj.ranking_snapshot.exam_id)


@admin.register(LeagueLeaderboard)
class LeagueLeaderboardAdmin(admin.ModelAdmin):
    list_display = ("competition", "stage", "as_of_round", "is_public", "created_at")
    list_filter = ("competition", "stage", "is_public")
    search_fields = ("competition__name",)
    autocomplete_fields = ["competition"]
    inlines = [LeagueLeaderboardEntryInline]
    list_select_related = ("competition",)
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_score_boards()

    def delete_model(self, request, obj):
        invalidate_score_boards()
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        invalidate_score_boards()
        super().delete_queryset(request, queryset)


@admin.register(LeagueLeaderboardEntry)
class LeagueLeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ("leaderboard", "candidate_email", "total_score", "overall_rank")
    list_filter = ("leaderboard__competition", "leaderboard__stage")
    search_fields = (
        "candidate__user__email",
        "candidate__user__first_name",
        "candidate__user__last_name",
    )
    autocomplete_fields = ["leaderboard", "candidate", "enrollment"]
    list_select_related = ("leaderboard", "candidate", "candidate__user", "enrollment")

    @admin.display(description="Candidate", ordering="candidate__user__email")
    def candidate_email(self, obj):
        return obj.candidate.user.email

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_candidate_cache(obj.candidate)

    def delete_model(self, request, obj):
        self._invalidate_candidate_cache(obj.candidate)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_candidate_cache(obj.candidate)
        super().delete_queryset(request, queryset)

    def _invalidate_candidate_cache(self, candidate):
        invalidate_candidate_cache(candidate.pk, candidate.user.id)
