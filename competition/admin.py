from django.contrib import admin
from django.utils.html import format_html
from vmlc.v2.utils import (
    invalidate_league_leaderboard,
    invalidate_candidate_cache,
    invalidate_exam_cache,
)
from vmlc.utils.helpers import invalidate_all_dashboard_caches
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
        "created_at",
    )
    list_filter = ("status", "edition")
    search_fields = ("name", "edition")
    inlines = [StageInline]
    date_hierarchy = "start_date"

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
        "created_at",
    )
    list_filter = ("competition", "type")
    ordering = ("competition", "order")
    inlines = [StageExamInline]
    list_select_related = ("competition",)

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
    list_filter = ("competition_stage__competition", "is_active")
    list_select_related = (
        "competition_stage",
        "competition_stage__competition",
        "exam",
    )

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
            url = f"/admin/vmlc/exam/{obj.exam.id}/change/"
            return format_html('<a href="{}">{}</a>', url, obj.exam)
        return "-"


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "candidate",
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
    raw_id_fields = ("candidate", "competition", "current_stage")
    list_select_related = (
        "candidate",
        "candidate__user",
        "competition",
        "current_stage",
    )
    date_hierarchy = "joined_at"

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
    list_display = ("enrollment", "stage", "status_display", "updated_at")
    list_filter = ("stage__competition", "stage", "status")
    raw_id_fields = ("enrollment", "stage")
    list_select_related = (
        "enrollment",
        "enrollment__candidate",
        "enrollment__candidate__user",
        "stage",
    )
    date_hierarchy = "updated_at"

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
        "exam",
        "facilitator_system",
        "is_published",
        "published_at",
    )
    list_filter = ("competition", "stage", "facilitator_system", "is_published")
    raw_id_fields = ("competition", "exam")
    inlines = [RankingSnapshotEntryInline]
    list_select_related = ("competition", "exam")
    date_hierarchy = "published_at"

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
    list_display = ("ranking_snapshot", "candidate", "exam_score", "rank", "percentile")
    list_filter = ("ranking_snapshot__competition", "ranking_snapshot__stage")
    search_fields = (
        "candidate__user__email",
        "candidate__user__first_name",
        "candidate__user__last_name",
    )
    raw_id_fields = ("ranking_snapshot", "candidate", "enrollment")
    list_select_related = (
        "ranking_snapshot",
        "candidate",
        "candidate__user",
        "enrollment",
    )

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


@admin.register(LeagueLeaderboard)
class LeagueLeaderboardAdmin(admin.ModelAdmin):
    list_display = ("competition", "stage", "as_of_round", "created_at")
    list_filter = ("competition", "stage")
    inlines = [LeagueLeaderboardEntryInline]
    list_select_related = ("competition",)
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_league_leaderboard()

    def delete_model(self, request, obj):
        invalidate_league_leaderboard()
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        invalidate_league_leaderboard()
        super().delete_queryset(request, queryset)


@admin.register(LeagueLeaderboardEntry)
class LeagueLeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ("leaderboard", "candidate", "total_score", "overall_rank")
    list_filter = ("leaderboard__competition", "leaderboard__stage")
    search_fields = (
        "candidate__user__email",
        "candidate__user__first_name",
        "candidate__user__last_name",
    )
    raw_id_fields = ("leaderboard", "candidate", "enrollment")
    list_select_related = ("leaderboard", "candidate", "candidate__user", "enrollment")

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
