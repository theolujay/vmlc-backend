from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from identity.models import Candidate, Staff, User, UserVerification, CowrywiseKidProfile, PreRegUser
from vmlc.models import (
    CandidateExamResult,
    Exam,
    ExamAccess,
)
from competition.models import (
    Competition,
    Stage,
    RankingSnapshot,
    Enrollment,
    StageExam,
    RankingSnapshotEntry,
    LeagueLeaderboard,
    LeagueLeaderboardEntry,
)
from competition.tasks import generate_stats_overview_task
from vmlc.utils.cache import CacheKeys


def refresh_stats_overview_cache(sender=None, _instance=None, **kwargs):
    """
    Invalidates the cache for all decentralized stats and triggers regeneration.
    """
    keys_to_delete = [
        CacheKeys.STATS_CANDIDATES,
        CacheKeys.STATS_STAFF,
        CacheKeys.STATS_EXAMS,
        CacheKeys.STATS_COMPETITION,
        CacheKeys.STATS_HELPDESK,
        CacheKeys.STATS_FUNNEL,
        CacheKeys.STATS_GEOGRAPHICS,
        "stats_overview",
    ]
    cache.delete_many(keys_to_delete)
    cache.delete("registration_metrics")
    cache.delete_pattern("user_list_view_*")
    generate_stats_overview_task.delay()


def invalidate_dashboard_on_change(sender, instance, **kwargs):
    """Specific invalidations for dashboards when data changes."""
    from vmlc.utils.cache import (
        invalidate_candidate_cache,
        invalidate_staff_dashboard,
        invalidate_score_boards,
    )

    if isinstance(instance, Candidate):
        invalidate_candidate_cache(instance.pk, user_id=instance.user_id)
        invalidate_staff_dashboard()
    elif isinstance(instance, Staff):
        invalidate_staff_dashboard()
    elif isinstance(instance, CowrywiseKidProfile):
        invalidate_candidate_cache(
            instance.candidate_id, user_id=instance.candidate.user_id
        )
        invalidate_staff_dashboard()
    elif isinstance(instance, CandidateExamResult):
        invalidate_candidate_cache(
            instance.candidate_id, user_id=instance.candidate.user_id
        )
        invalidate_staff_dashboard()
    elif isinstance(instance, RankingSnapshot):
        invalidate_staff_dashboard()
        invalidate_score_boards(exam_id=instance.exam_id)
    elif isinstance(instance, RankingSnapshotEntry):
        invalidate_staff_dashboard()
        invalidate_score_boards(exam_id=instance.ranking_snapshot.exam_id)
    elif isinstance(instance, (Competition, Stage, Enrollment, StageExam, LeagueLeaderboard, LeagueLeaderboardEntry, ExamAccess)):
        invalidate_staff_dashboard()
        invalidate_score_boards()
    elif isinstance(instance, Exam):
        from vmlc.tasks import invalidate_exam_related_caches_task
        from django.db import transaction

        transaction.on_commit(
            lambda: invalidate_exam_related_caches_task.delay(str(instance.id))
        )


stats_models_to_watch = [
    User,
    Candidate,
    Staff,
    UserVerification,
    PreRegUser,
    CandidateExamResult,
    Exam,
    Competition,
    Stage,
    RankingSnapshot,
    Enrollment,
    StageExam,
    RankingSnapshotEntry,
    LeagueLeaderboard,
    LeagueLeaderboardEntry,
    ExamAccess,
]
for model in stats_models_to_watch:
    post_save.connect(refresh_stats_overview_cache, sender=model)
    post_delete.connect(refresh_stats_overview_cache, sender=model)

dashboard_models_to_watch = [
    Candidate,
    Staff,
    CandidateExamResult,
    Competition,
    Stage,
    RankingSnapshot,
    Enrollment,
    Exam,
    CowrywiseKidProfile,
    StageExam,
    RankingSnapshotEntry,
    LeagueLeaderboard,
    LeagueLeaderboardEntry,
    ExamAccess,
]
for model in dashboard_models_to_watch:
    post_save.connect(invalidate_dashboard_on_change, sender=model)
    post_delete.connect(invalidate_dashboard_on_change, sender=model)
