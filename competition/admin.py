from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Competition,
    Stage,
    StageExam,
    CandidateCompetition,
    CandidateStageProgress,
    Standings,
    StandingsEntry,
    AggregateLeaderboard,
    AggregateLeaderboardEntry,
)


class StageInline(admin.TabularInline):
    model = Stage
    extra = 0
    ordering = ["order"]


class StageExamInline(admin.TabularInline):
    model = StageExam
    extra = 0


class StandingsEntryInline(admin.TabularInline):
    model = StandingsEntry
    extra = 0
    raw_id_fields = ["candidate", "candidate_competition"]


class AggregateLeaderboardEntryInline(admin.TabularInline):
    model = AggregateLeaderboardEntry
    extra = 0
    raw_id_fields = ["candidate", "candidate_competition"]


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ("name", "edition", "status_display", "start_date", "end_date", "created_at")
    list_filter = ("status", "edition")
    search_fields = ("name", "edition")
    inlines = [StageInline]
    date_hierarchy = "start_date"

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


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("competition", "type", "order", "created_at")
    list_filter = ("competition", "type")
    ordering = ("competition", "order")
    inlines = [StageExamInline]
    list_select_related = ("competition",)


@admin.register(StageExam)
class StageExamAdmin(admin.ModelAdmin):
    list_display = ("competition_stage", "round", "is_active")
    list_filter = ("competition_stage__competition", "is_active")
    list_select_related = ("competition_stage", "competition_stage__competition")


@admin.register(CandidateCompetition)
class CandidateCompetitionAdmin(admin.ModelAdmin):
    list_display = ("candidate", "competition", "status_display", "current_stage", "joined_at")
    list_filter = ("competition", "status", "current_stage")
    search_fields = ("candidate__user__email", "candidate__user__first_name", "candidate__user__last_name")
    raw_id_fields = ("candidate", "competition", "current_stage")
    list_select_related = ("candidate", "candidate__user", "competition", "current_stage")
    date_hierarchy = "joined_at"

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        colors = {
            CandidateCompetition.Status.ENROLLED: "blue",
            CandidateCompetition.Status.ACTIVE: "green",
            CandidateCompetition.Status.ELIMINATED: "red",
            CandidateCompetition.Status.WITHDRAWN: "orange",
            CandidateCompetition.Status.DISQUALIFIED: "darkred",
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, "black"),
            obj.get_status_display(),
        )


@admin.register(CandidateStageProgress)
class CandidateStageProgressAdmin(admin.ModelAdmin):
    list_display = ("candidate_competition", "stage", "status_display", "updated_at")
    list_filter = ("stage__competition", "stage", "status")
    raw_id_fields = ("candidate_competition", "stage")
    list_select_related = ("candidate_competition", "candidate_competition__candidate", "candidate_competition__candidate__user", "stage")
    date_hierarchy = "updated_at"

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        colors = {
            CandidateStageProgress.Status.PENDING: "orange",
            CandidateStageProgress.Status.IN_PROGRESS: "blue",
            CandidateStageProgress.Status.COMPLETED: "green",
            CandidateStageProgress.Status.DISCONTINUED: "red",
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, "black"),
            obj.get_status_display(),
        )


@admin.register(Standings)
class StandingsAdmin(admin.ModelAdmin):
    list_display = ("competition", "stage", "round", "exam", "facilitator_system", "is_published", "published_at")
    list_filter = ("competition", "stage", "facilitator_system", "is_published")
    raw_id_fields = ("competition", "exam")
    inlines = [StandingsEntryInline]
    list_select_related = ("competition", "exam")
    date_hierarchy = "published_at"


@admin.register(StandingsEntry)
class StandingsEntryAdmin(admin.ModelAdmin):
    list_display = ("standings", "candidate", "exam_score", "rank", "percentile")
    list_filter = ("standings__competition", "standings__stage")
    raw_id_fields = ("standings", "candidate", "candidate_competition")
    list_select_related = ("standings", "candidate", "candidate__user", "candidate_competition")


@admin.register(AggregateLeaderboard)
class AggregateLeaderboardAdmin(admin.ModelAdmin):
    list_display = ("competition", "stage", "as_of_round", "created_at")
    list_filter = ("competition", "stage")
    inlines = [AggregateLeaderboardEntryInline]
    list_select_related = ("competition",)
    date_hierarchy = "created_at"


@admin.register(AggregateLeaderboardEntry)
class AggregateLeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ("leaderboard", "candidate", "total_score", "overall_rank")
    list_filter = ("leaderboard__competition", "leaderboard__stage")
    raw_id_fields = ("leaderboard", "candidate", "candidate_competition")
    list_select_related = ("leaderboard", "candidate", "candidate__user", "candidate_competition")