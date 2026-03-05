import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Q
from django.utils import timezone

from competition.models import (
    Competition,
    Stage,
    StageExam,
    Enrollment,
    EnrollmentStageProgress,
    RankingSnapshot,
    RankingSnapshotEntry,
)

from competition.services.leaderboard import LeaderboardService
from competition.services.eligibility import EligibilityService
from identity.models import Candidate
from vmlc.models import Exam, CandidateExamResult, ExamAccess
from vmlc.v2.utils import truncate_float

logger = logging.getLogger(__name__)

STATUS_THEMES = {
    "success": {"color": "#018ABB", "bg_color": "#CCEEFB33", "icon": "check"},
    "pending": {"color": "#065F46", "bg_color": "#ECFDF5", "icon": "clock"},
    "info": {"color": "#3E4095", "bg_color": "#EFF6FF", "icon": "info"},
    "warning": {"color": "#667185", "bg_color": "#F9FAFB", "icon": "calendar"},
    "error": {"color": "#CB1A14", "bg_color": "#FBEAE9", "icon": "alert"},
    "eliminated": {"color": "#CB1A14", "bg_color": "#FBEAE9", "icon": "alert"},
    "disqualified": {"color": "#CB1A14", "bg_color": "#FBEAE9", "icon": "alert"},
}

STAGE_CONFIGS = {
    Stage.Type.SCREENING: {
        "label": "Screening Stage",
        "accent_color": "#4F46E5",
        "metric_label": "League Qualification Cut-off",
        "messages": {
            "success": (
                "Screening Passed",
                "You've made the cut. Welcome to the League stage.",
            ),
            "pending": (
                "Results on the Way",
                "We're reviewing your performance. Check back soon.",
            ),
            "info": (
                "Screening Upcoming",
                "The screening hasn't started yet. We'll notify you when it does.",
            ),
            "warning": (
                "Below Cut-off",
                "Your current rank is outside the qualification range.",
            ),
            "error": (
                "Round Missed",
                "You did not participate in the screening examination.",
            ),
            "eliminated": (
                "Eliminated",
                "Your score didn't meet the cut-off for the next stage.",
            ),
        },
    },
    Stage.Type.LEAGUE: {
        "label": "League Stage",
        "accent_color": "#3E4095",
        "metric_label": "Finalist Qualification Cut-off",
        "messages": {
            "success": (
                "On Track for the Finals",
                "You're within the qualification range. Keep it up.",
            ),
            "pending": (
                "Scores Being Tallied",
                "The leaderboard is updating. Check back shortly.",
            ),
            "warning": (
                "Outside Qualification Range",
                "There's still time to turn it around in the upcoming rounds.",
            ),
            "info": (
                "Round Not Started",
                "This round hasn't begun yet. Good luck when it does.",
            ),
            "error": (
                "Round Missed",
                "You missed a mandatory round and are at risk of elimination.",
            ),
            "eliminated": (
                "Eliminated",
                "You were absent from one round.",
            ),
        },
    },
    Stage.Type.FINAL: {
        "label": "Final Stage",
        "accent_color": "#D97706",
        "metric_label": "Champion Threshold",
        "messages": {
            "success": (
                "Congratulations!",
                "You made it to the very top of the competition",
            ),
            "pending": (
                "Results Being Verified",
                "Final results are being confirmed. An official update is coming soon.",
            ),
            "info": (
                "Finals Ahead",
                "Schedule and details for the final will be shared soon. Prepare well.",
            ),
            "error": (
                "Round Missed",
                "You did not participate in the final examination.",
            ),
            "eliminated": (
                "Finalist",
                "Kudos for making it this far, but some got farther.",
            ),
        },
    },
}

DEFAULT_MESSAGES = {
    "disqualified": (
        "Disqualified",
        "You have been disqualified for violating competition rules.",
    ),
    "eliminated": ("Eliminated", "You have been eliminated from the competition."),
    "error": ("Status Unavailable", "Hang in there for updates"),
}


class CandidateDashboardService:
    @staticmethod
    def get_dashboard_data(
        candidate: Candidate, enrollment: Optional[Enrollment] = None
    ) -> Dict[str, Any]:
        """
        Main entry point to get all candidate dashboard data.
        """
        active_comp = None
        if enrollment:
            active_comp = enrollment.competition
        else:
            active_comp = Competition.objects.filter(
                status=Competition.Status.ACTIVE
            ).first()

        if active_comp and not enrollment:
            enrollment = (
                Enrollment.objects.filter(candidate=candidate, competition=active_comp)
                .select_related("current_stage")
                .first()
            )

        progress = CandidateDashboardService._get_enrollment_stage_progress(
            candidate, active_comp, enrollment
        )

        active_exam_data = CandidateDashboardService._get_active_exam(
            candidate, active_comp, enrollment
        )

        performance = CandidateDashboardService._get_performance(
            candidate, active_comp, enrollment
        )

        history = CandidateDashboardService._get_exam_history(candidate)

        return {
            "enrollment_stage_progress": progress,
            "active_exam": active_exam_data,
            "performance": performance,
            "exam_history": history,
        }

    @staticmethod
    def _resolve_current_stage(
        candidate: Candidate,
        active_comp: Competition,
        enrollment: Optional[Enrollment],
    ) -> Optional[Stage]:
        """
        Returns the candidate's current stage object.
        Falls back to matching by candidate role if not enrolled or stage not set.
        """
        if enrollment and enrollment.current_stage:
            return enrollment.current_stage
        return Stage.objects.filter(
            competition=active_comp, type=candidate.role
        ).first()

    @staticmethod
    def _get_active_stage_slots(stage: Stage) -> Any:
        """
        Returns a queryset of StageExam slots for the given stage that are
        either explicitly active or whose exam has a scheduled date in the past.
        Ordered by scheduled date ascending.
        """
        now = timezone.now()
        return (
            StageExam.objects.filter(
                Q(competition_stage=stage)
                & (Q(is_active=True) | Q(exam__scheduled_date__lte=now))
                & Q(exam__isnull=False)
            )
            .select_related("exam")
            .order_by("exam__scheduled_date")
        )

    @staticmethod
    def _get_enrollment_stage_progress(
        candidate: Candidate,
        active_comp: Optional[Competition],
        enrollment: Optional[Enrollment],
    ) -> Dict[str, Any]:
        if not active_comp:
            return {
                "current_stage": None,
                "current_round": None,
                "total_rounds": 0,
                "published_rounds": 0,
                "has_taken_current_round": False,
                "qualification_status": None,
            }

        current_stage = CandidateDashboardService._resolve_current_stage(
            candidate, active_comp, enrollment
        )

        if not current_stage:
            return {
                "current_stage": None,
                "current_round": None,
                "total_rounds": 0,
                "published_rounds": 0,
                "has_taken_current_round": False,
                "qualification_status": None,
            }

        slots = CandidateDashboardService._get_active_stage_slots(current_stage)
        total_rounds = slots.count()

        published_rounds = RankingSnapshot.objects.filter(
            competition=active_comp, stage=current_stage.type, is_published=True
        ).count()

        # Most recent slot by scheduled date
        latest_slot = slots.last()
        current_round = latest_slot.round if latest_slot else None

        has_taken_current_round = False
        if latest_slot:
            try:
                has_taken_current_round = ExamAccess.objects.filter(
                    candidate=candidate,
                    exam=latest_slot.exam,
                    status=ExamAccess.Status.SUBMITTED,
                ).exists()
            except Exam.DoesNotExist:
                pass

        is_qualified = (
            enrollment.status == Enrollment.Status.ACTIVE
            if enrollment
            else True
        )
        status_display = enrollment.get_status_display() if enrollment else "Active"

        qualification_status = {
            "is_qualified": is_qualified,
            "advancement_policy": current_stage.config.get("advancement_policy", None),
            "message": (
                f"You are currently {status_display} "
                f"in the {current_stage.get_type_display()} stage."
            ),
        }

        history = []
        if enrollment:
            stage_progresses = (
                EnrollmentStageProgress.objects.filter(enrollment=enrollment)
                .select_related("stage")
                .order_by("stage__order")
            )
            for sp in stage_progresses:
                history.append(
                    {
                        "stage": sp.stage.type,
                        "status": sp.status,
                        "started_at": sp.started_at,
                        "completed_at": sp.completed_at,
                        "discontinued_at": sp.discontinued_at,
                    }
                )

        return {
            "current_stage": current_stage.type,
            "current_round": current_round,
            "total_rounds": total_rounds,
            "published_rounds": published_rounds,
            "has_taken_current_round": has_taken_current_round,
            "qualification_status": qualification_status,
            "history": history,
        }

    @staticmethod
    def _get_active_exam(
        candidate: Candidate,
        active_comp: Optional[Competition],
        enrollment: Optional[Enrollment],
    ) -> Optional[Dict[str, Any]]:
        if not active_comp:
            return None

        current_stage = CandidateDashboardService._resolve_current_stage(
            candidate, active_comp, enrollment
        )

        if not current_stage:
            return None

        slots = CandidateDashboardService._get_active_stage_slots(current_stage)

        active_exam_data = None
        for slot in slots:
            try:
                exam = slot.exam
                status = exam.status

                is_eligible = EligibilityService.can_take_exam(candidate, exam)

                access = ExamAccess.objects.filter(
                    candidate=candidate, exam=exam
                ).first()

                has_participated = (
                    access.status == ExamAccess.Status.SUBMITTED if access else False
                )

                attempt_data = None
                if access:
                    attempt_data = {
                        "started_at": access.started_at,
                        "deadline": access.deadline,
                        "submitted_at": access.submitted_at,
                    }

                if status in [Exam.Status.ONGOING, Exam.Status.SCHEDULED]:
                    exam_data = {
                        "id": str(exam.id),
                        "title": exam.get_title(),
                        "description": exam.description,
                        "stage": current_stage.type,
                        "round": slot.round,
                        "question_count": exam.get_question_count(),
                        "starts_at": exam.scheduled_date,
                        "ends_at": (
                            exam.scheduled_date
                            + timedelta(hours=exam.open_duration_hours)
                            if exam.scheduled_date
                            else None
                        ),
                        "duration_minutes": exam.countdown_minutes,
                        "status": status,
                        "attempt": attempt_data,
                        "access_status": access.status if access else None,
                    }
                    if (
                        status == Exam.Status.ONGOING
                        and is_eligible
                        and not has_participated
                    ):
                        active_exam_data = exam_data
                        break

                    if not active_exam_data:
                        active_exam_data = exam_data

                    if status == Exam.Status.CONCLUDED and has_participated:
                        ranking = RankingSnapshot.objects.filter(
                            exam=exam, is_published=True
                        ).first()
                        is_published = ranking is not None

                        if not active_exam_data:
                            active_exam_data = {
                                "id": str(exam.id),
                                "title": exam.get_title(),
                                "stage": current_stage.type,
                                "round": slot.round,
                                "status": (
                                    "results_published"
                                    if is_published
                                    else "awaiting_results"
                                ),
                                "attempt": attempt_data,
                            }
            except Exam.DoesNotExist:
                continue

        return active_exam_data

    # ---------------------------------------------------------------------------
    # _get_performance and its decomposed helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def _get_stage_rankings(
        candidate: Candidate,
        active_comp: Competition,
        league_leaderboard_data: Optional[Dict],
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetches the candidate's ranking data for each stage.
        Returns a dict keyed by Stage.Type with ranking dicts or None.
        """
        rankings: Dict[str, Optional[Dict]] = {
            Stage.Type.SCREENING: None,
            Stage.Type.LEAGUE: league_leaderboard_data,
            Stage.Type.FINAL: None,
        }

        entries = RankingSnapshotEntry.objects.filter(
            Q(ranking_snapshot__stage=Stage.Type.SCREENING)
            | Q(ranking_snapshot__stage=Stage.Type.FINAL),
            ranking_snapshot__competition=active_comp,
            ranking_snapshot__is_active=True,
            ranking_snapshot__is_published=True,
            candidate=candidate,
        ).select_related("ranking_snapshot", "ranking_snapshot__exam")

        for entry in entries:
            stage_type = entry.ranking_snapshot.stage
            rankings[stage_type] = {
                "position": entry.rank,
                "total_candidates": entry.ranking_snapshot.entries.count(),
                "score": (
                    truncate_float(float(entry.exam_score))
                    if entry.exam_score is not None
                    else None
                ),
                "percentile": entry.percentile,
                "exam_id": str(entry.ranking_snapshot.exam_id),
                "exam_title": entry.ranking_snapshot.exam.get_title(),
                "rank_change": 0,
                "is_active": True,
            }

        return rankings

    @staticmethod
    def _get_league_leaderboard_data(
        candidate: Candidate, active_comp: Competition
    ) -> Optional[Dict]:
        """
        Fetches the candidate's entry from the latest league leaderboard.
        Returns a ranking dict or None.
        """
        leaderboard = LeaderboardService.get_latest_league_leaderboard(active_comp)
        if not leaderboard:
            return None

        entry = next(
            (
                e
                for e in leaderboard.processed_entries
                if e.candidate_id == candidate.pk
            ),
            None,
        )
        if not entry:
            return None

        return {
            "position": entry.overall_rank,
            "total_candidates": leaderboard.entries.count(),
            "score": (
                truncate_float(float(entry.total_score))
                if entry.total_score is not None
                else 0
            ),
            "rank_change": getattr(entry, "rank_change", 0),
            "is_active": entry.overall_rank is not None,
            "as_of_round": leaderboard.as_of_round,
        }

    @staticmethod
    def _get_candidate_exam_state(
        candidate: Candidate, stage: Stage
    ) -> Tuple[bool, bool, bool, bool]:
        now = timezone.now()

        slots = (
            StageExam.objects.filter(
                Q(competition_stage=stage)
                & (Q(is_active=True) | Q(exam__scheduled_date__lte=now))
                & Q(exam__isnull=False)
            )
            .select_related("exam")
            .order_by("-exam__scheduled_date")
        )

        if not slots.exists():
            return False, False, False, False

        stage_exam_ids = list(slots.values_list("exam__id", flat=True))

        access = (
            ExamAccess.objects.filter(
                candidate=candidate,
                exam_id__in=stage_exam_ids,
            )
            .select_related("exam")
            .order_by("-exam__scheduled_date")
            .first()
        )

        if not access:
            latest_exam = slots.first().exam
            is_missed = latest_exam.status == Exam.Status.CONCLUDED
            return False, False, False, is_missed

        exam = access.exam
        has_started = access.status in [
            ExamAccess.Status.STARTED,
            ExamAccess.Status.SUBMITTED,
        ]
        has_submitted = access.status == ExamAccess.Status.SUBMITTED

        is_published = RankingSnapshot.objects.filter(
            exam=exam, is_published=True
        ).exists()
        is_awaiting_results = has_submitted and not is_published
        is_missed = exam.status == Exam.Status.CONCLUDED and not has_submitted

        return has_started, has_submitted, is_awaiting_results, is_missed

    @staticmethod
    def _resolve_metric_value_display(policy: Dict) -> str:
        """
        Converts an advancement policy dict into a human-readable cutoff string.
        """
        if not policy:
            return "N/A"
        mode = policy.get("mode")
        value = policy.get("value")
        if mode == "top_n":
            return f"Top {value}"
        if mode == "top_percent":
            return f"Top {round(value * 100)}%"
        return "N/A"

    @staticmethod
    def _resolve_status_type(
        enrollment: Optional[Enrollment],
        stage_type: str,
        ranking: Optional[Dict],
        policy: Dict,
        has_started: bool,
        has_submitted: bool,
        is_awaiting_results: bool,
        is_missed: bool,
    ) -> str:
        """
        Determines the status string for the active context status badge.
        Priority order: disqualified > eliminated > missed > pending > ranking-based > info > error.
        """
        enroll_status = (
            enrollment.status if enrollment else Enrollment.Status.ACTIVE
        )

        if enroll_status == Enrollment.Status.DISQUALIFIED:
            return "disqualified"
        if enroll_status == Enrollment.Status.ELIMINATED:
            return "eliminated"
        if is_missed:
            return "error"
        if is_awaiting_results or (has_started and not has_submitted):
            return "pending"

        if ranking:
            mode = policy.get("mode")
            value = policy.get("value")
            position = ranking.get("position")
            total = ranking.get("total_candidates")
            within_cutoff = True

            if policy and position is not None and value is not None:
                if mode == "top_n":
                    within_cutoff = position <= value
                elif mode == "top_percent" and total:
                    within_cutoff = (position / total) <= value

            if within_cutoff or stage_type == Stage.Type.FINAL:
                return "success"
            return "warning"

        if not has_started:
            return "info"

        return "error"

    @staticmethod
    def _build_active_context(
        candidate: Candidate,
        active_comp: Competition,
        enrollment: Optional[Enrollment],
        current_stage_obj: Stage,
        rankings: Dict[str, Optional[Dict]],
    ) -> Optional[Dict[str, Any]]:
        """
        Constructs the active_context dict for the performance section.
        Delegates exam state resolution and status determination to helpers.
        """
        current_stage_type = current_stage_obj.type
        config = STAGE_CONFIGS.get(current_stage_type, {})
        ranking = rankings.get(current_stage_type)
        policy = current_stage_obj.config.get("advancement_policy", {}) or {}

        has_started, has_submitted, is_awaiting_results, is_missed = (
            CandidateDashboardService._get_candidate_exam_state(
                candidate, current_stage_obj
            )
        )

        status_type = CandidateDashboardService._resolve_status_type(
            enrollment=enrollment,
            stage_type=current_stage_type,
            ranking=ranking,
            policy=policy,
            has_started=has_started,
            has_submitted=has_submitted,
            is_awaiting_results=is_awaiting_results,
            is_missed=is_missed,
        )

        theme = STATUS_THEMES.get(status_type, STATUS_THEMES["error"])
        status_label, status_subtext = config.get("messages", {}).get(
            status_type,
            DEFAULT_MESSAGES.get(status_type, DEFAULT_MESSAGES["error"]),
        )

        metric_value_display = CandidateDashboardService._resolve_metric_value_display(
            policy
        )

        enroll_status = (
            enrollment.status if enrollment else Enrollment.Status.ACTIVE
        )

        active_context = {
            "stage": current_stage_type,
            "stage_display": config.get("label"),
            "title": f"{config.get('label')} Performance",
            "accent_color": config.get("accent_color"),
            "ranking": ranking,
            "status_meta": {
                "has_taken_exam": has_submitted,
                "is_awaiting_results": is_awaiting_results,
                "is_qualified": enroll_status
                in [Enrollment.Status.ACTIVE, Enrollment.Status.PENDING],
                "metric_label": config.get("metric_label"),
                "metric_value_display": metric_value_display,
                "status_label": status_label,
                "status_subtext": status_subtext,
                "status_type": status_type,
                "color": theme["color"],
                "bg_color": theme["bg_color"],
                "icon": theme["icon"],
            },
        }

        # League-specific title showing round progress
        league_ranking = rankings.get(Stage.Type.LEAGUE)
        if current_stage_type == Stage.Type.LEAGUE and league_ranking:
            total_rounds = StageExam.objects.filter(
                competition_stage=current_stage_obj
            ).count()
            active_context["title"] = (
                f"League Performance • Round {league_ranking['as_of_round']} of {total_rounds}"
            )

        return active_context

    @staticmethod
    def _get_performance(
        candidate: Candidate,
        active_comp: Optional[Competition],
        enrollment: Optional[Enrollment] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves performance metrics and active stage context.
        """
        if not active_comp:
            return {"active_context": None, "history": []}

        current_stage_obj = CandidateDashboardService._resolve_current_stage(
            candidate, active_comp, enrollment
        )

        league_data = CandidateDashboardService._get_league_leaderboard_data(
            candidate, active_comp
        )
        rankings = CandidateDashboardService._get_stage_rankings(
            candidate, active_comp, league_data
        )

        history = []
        for stage_type in [Stage.Type.SCREENING, Stage.Type.LEAGUE, Stage.Type.FINAL]:
            if rankings.get(stage_type):
                history.append({"stage": stage_type, "ranking": rankings[stage_type]})

        active_context = None
        if current_stage_obj:
            active_context = CandidateDashboardService._build_active_context(
                candidate=candidate,
                active_comp=active_comp,
                enrollment=enrollment,
                current_stage_obj=current_stage_obj,
                rankings=rankings,
            )

        return {
            "active_context": active_context,
            "history": history,
        }

    @staticmethod
    def _get_exam_history(candidate: Candidate) -> List[Dict[str, Any]]:
        results = (
            CandidateExamResult.objects.filter(candidate=candidate)
            .select_related("exam", "exam__competition_slot__competition_stage")
            .order_by("-recorded_at")
        )

        published_exam_ids = set(
            RankingSnapshot.objects.filter(
                exam_id__in=[res.exam_id for res in results], is_published=True
            ).values_list("exam_id", flat=True)
        )

        history = []
        for res in results:
            exam = res.exam
            slot = exam.competition_slot
            is_published = exam.id in published_exam_ids

            history.append(
                {
                    "exam_id": str(exam.id),
                    "exam_title": exam.get_title(),
                    "stage": slot.competition_stage.type if slot else "N/A",
                    "round": slot.round if slot else None,
                    "score": (
                        truncate_float(float(res.score))
                        if is_published and res.score is not None
                        else None
                    ),
                    "percentage": (
                        truncate_float(float(res.score))
                        if is_published and res.score is not None
                        else None
                    ),
                    "date": res.recorded_at,
                    "status": exam.status,
                    "is_published": is_published,
                }
            )
        return history