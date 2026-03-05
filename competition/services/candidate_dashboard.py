import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.db.models import Q
from django.utils import timezone

from competition.models import (
    Competition,
    Stage,
    StageExam,
    Enrollment,
    RankingSnapshot,
    RankingSnapshotEntry,
)
from comms.models import Notification
from competition.services.leaderboard import LeaderboardService
from competition.services.eligibility import EligibilityService
from competition.models import EnrollmentStageProgress
from identity.models import Candidate
from vmlc.models import Exam, CandidateExamResult, ExamAccess
from vmlc.v2.utils import truncate_float

logger = logging.getLogger(__name__)

STAGE_METADATA = {
    Stage.Type.SCREENING: {
        "label": "Screening Stage",
        "accent_color": "#4F46E5",
        "metric_label": "League Qualification Cut-off",
        "status_messages": {
            "success": {
                "label": "Screening Passed",
                "subtext": "You've made the cut. Welcome to the League stage.",
                "color": "#018ABB",
                "bg_color": "#CCEEFB33",
                "icon": "check",
            },
            "pending": {
                "label": "Results on the Way",
                "subtext": "We're reviewing your performance. Hang tight.",
                "color": "#065F46",
                "bg_color": "#ECFDF5",
                "icon": "clock",
            },
            "error": {
                "label": "Screening Not Passed",
                "subtext": "You didn't meet the cut-off and have been eliminated .",
                "color": "#CB1A14",
                "bg_color": "#FBEAE9",
                "icon": "alert",
            },
            "warning": {
                "label": "Screening Upcoming",
                "subtext": "The screening hasn't started yet. We'll let you know when it does.",
                "color": "#667185",
                "bg_color": "#F9FAFB",
                "icon": "calendar",
            },
        },
    },
    Stage.Type.LEAGUE: {
        "label": "League Stage",
        "accent_color": "#3E4095",
        "metric_label": "Finalist Qualification Cut-off",
        "status_messages": {
            "success": {
                "label": "On Track for the Final",
                "subtext": "You're within the qualification range. Keep it up.",
                "color": "#018ABB",
                "bg_color": "#CCEEFB33",
                "icon": "check",
            },
            "pending": {
                "label": "Scores Being Tallied",
                "subtext": "The leaderboard is updating... Check back shortly.",
                "color": "#065F46",
                "bg_color": "#ECFDF5",
                "icon": "clock",
            },
            "error": {
                "label": "Outside Qualification Range",
                "subtext": "There's still time to turn it around in the upcoming rounds.",
                "color": "#CB1A14",
                "bg_color": "#FBEAE9",
                "icon": "alert",
            },
            "warning": {
                "label": "Round Not Started",
                "subtext": "This round hasn't begun yet. Good luck when it does.",
                "color": "#667185",
                "bg_color": "#F9FAFB",
                "icon": "calendar",
            },
        },
    },
    Stage.Type.FINAL: {
        "label": "Grand Final",
        "accent_color": "#D97706",
        "metric_label": "Champion Threshold",
        "status_messages": {
            "success": {
                "label": "You're In",
                "subtext": "You're confirmed for the Grand Final. See you there.",
                "color": "#018ABB",
                "bg_color": "#CCEEFB33",
                "icon": "check",
            },
            "pending": {
                "label": "Results Being Verified",
                "subtext": "Final results are being confirmed. An official update is coming soon.",
                "color": "#065F46",
                "bg_color": "#ECFDF5",
                "icon": "clock",
            },
            "error": {
                "label": "Under Review",
                "subtext": "Your participation is being reviewed by the team. Sit tight.",
                "color": "#CB1A14",
                "bg_color": "#FBEAE9",
                "icon": "alert",
            },
            "warning": {
                "label": "Finals Ahead",
                "subtext": "Details and schedule for the final will be shared soon. Prepare well.",
                "color": "#667185",
                "bg_color": "#F9FAFB",
                "icon": "calendar",
            },
        },
    },
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

        # context = CandidateDashboardService._get_context(candidate)
        # notifications = CandidateDashboardService._get_notifications(candidate)

        if active_comp and not enrollment:
            enrollment = (
                Enrollment.objects.filter(candidate=candidate, competition=active_comp)
                .select_related("current_stage")
                .first()
            )

        progress = CandidateDashboardService._get_enrollment_stage_progress(
            candidate, active_comp, enrollment
        )

        # Active Exam
        active_exam_data = CandidateDashboardService._get_active_exam(
            candidate, active_comp, enrollment
        )

        # Performance Snapshot
        performance = CandidateDashboardService._get_performance(
            candidate, active_comp, enrollment
        )

        # Exam History
        history = CandidateDashboardService._get_exam_history(candidate)

        return {
            # "candidate_context": context,
            # "notifications": notifications,
            "enrollment_stage_progress": progress,
            "active_exam": active_exam_data,
            "performance": performance,
            "exam_history": history,
        }

    # @staticmethod
    # def _get_notifications(candidate: Candidate) -> Dict[str, Any]:

    #     # Fetch last 5 unread notifications
    #     notifications = Notification.objects.filter(
    #         recipient=candidate.user,
    #         is_read=False,
    #     ).order_by("-created_at")[:5]

    #     notification_map = {"info": [], "success": [], "error": []}
    #     n_type_key_map = {
    #         Notification.Type.INFO: "info",
    #         Notification.Type.SUCCESS: "success",
    #         Notification.Type.ERROR: "error",
    #     }

    #     for n in notifications:
    #         key = n_type_key_map.get(n.type)
    #         if key:
    #             notification_map[key].append(
    #                 {
    #                     "id": n.id,
    #                     "message": n.message,
    #                     "is_read": n.is_read
    #                 }
    #             )
    #     return notification_map

    # @staticmethod
    # def _get_context(candidate: Candidate) -> Dict[str, Any]:
    #     from vmlc.views.user.management import ProfileManager

    #     return ProfileManager.serialize_profile(candidate.user) or {}

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

        # Determine the current stage - fallback to candidate role if not enrolled
        current_stage = enrollment.current_stage if enrollment else None
        if not current_stage:
            current_stage = Stage.objects.filter(
                competition=active_comp, type=candidate.role
            ).first()

        if not current_stage:
            return {
                "current_stage": None,
                "current_round": None,
                "total_rounds": 0,
                "published_rounds": 0,
                "has_taken_current_round": False,
                "qualification_status": None,
            }

        # Rounds in current stage
        now = timezone.now()

        slots = (
            StageExam.objects.filter(
                Q(competition_stage=current_stage)
                & (Q(is_active=True) | Q(exam__scheduled_date__lte=now))
            )
            .select_related("exam")
            .order_by("round")
        )

        total_rounds = slots.count()

        # Published ranking in current stage
        published_rounds = RankingSnapshot.objects.filter(
            competition=active_comp, stage=current_stage.type, is_published=True
        ).count()

        # Current round (latest one that is active)
        latest_slot = slots.last()
        current_round = latest_slot.round if latest_slot else None

        has_taken_current_round = False
        if latest_slot:
            try:
                exam = latest_slot.exam
                has_taken_current_round = ExamAccess.objects.filter(
                    candidate=candidate,
                    exam=exam,
                    status=ExamAccess.Status.SUBMITTED,
                ).exists()
            except Exam.DoesNotExist:
                pass

        # Qualification Status logic
        is_qualified = (
            enrollment.status == Enrollment.Status.ACTIVE
            if enrollment
            else True  # Assume active if just discovered by role
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

        # Fetch full history of stage progress
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
            "current_stage": current_stage.type,  # TODO: compare with staff's competition dashboard to handle when exam's not started yet
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

        # Determine the current stage - fallback to candidate role if not enrolled
        current_stage = enrollment.current_stage if enrollment else None
        if not current_stage:
            current_stage = Stage.objects.filter(
                competition=active_comp, type=candidate.role
            ).first()

        if not current_stage:
            return None

        # Get all active slots for current stage
        now = timezone.now()

        slots = (
            StageExam.objects.filter(
                Q(competition_stage=current_stage)
                & (Q(is_active=True) | Q(exam__scheduled_date__lte=now))
            )
            .select_related("exam")
            .order_by("round")
        )

        active_exam_data = None
        for slot in slots:
            try:
                exam = slot.exam
                status = exam.status

                # Check eligibility
                is_eligible = EligibilityService.can_take_exam(candidate, exam)

                # Check access status
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
                        "duration_minutes": exam.countdown_minutes,  # TODO: rename tis to exam.duration_minutes
                        "status": status,
                        "attempt": attempt_data,
                        "access_status": (
                            access.status if access else None
                        ),  # TODO: reconsider if this is necessary
                    }
                    if (
                        status == Exam.Status.ONGOING
                        and is_eligible
                        and not has_participated
                    ):
                        # Found our primary target, an ongoing exam
                        # that the candidate hasn't yet participated in
                        active_exam_data = exam_data
                        break

                    if not active_exam_data:
                        active_exam_data = exam_data

                    if status == Exam.Status.CONCLUDED and has_participated:
                        # Check if ranking are published
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

        # 1. Identify Current Stage
        current_stage_type = None
        if enrollment and enrollment.current_stage:
            current_stage_type = enrollment.current_stage.type
        else:
            current_stage_type = candidate.role

        current_stage_obj = Stage.objects.filter(
            competition=active_comp, type=current_stage_type
        ).first()

        # 2. Gather All Ranking Data
        screening_ranking = None
        league_leaderboard = None
        final_ranking = None

        # Fetch Screening and Final RankingSnapshot Entries
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
            data = {
                "position": entry.rank,
                "total_candidates": entry.ranking_snapshot.entries.count(),
                "score": truncate_float(float(entry.exam_score)),
                "percentile": entry.percentile,
                "exam_id": str(entry.ranking_snapshot.exam_id),
                "exam_title": entry.ranking_snapshot.exam.get_title(),
                "rank_change": 0,
                "is_active": True,
            }

            if stage_type == Stage.Type.SCREENING:
                screening_ranking = data
            elif stage_type == Stage.Type.FINAL:
                final_ranking = data

        # League Leaderboard
        leaderboard = LeaderboardService.get_latest_league_leaderboard(active_comp)
        if leaderboard:
            entry = next(
                (
                    e
                    for e in leaderboard.processed_entries
                    if e.candidate_id == candidate.pk
                ),
                None,
            )
            if entry:
                league_leaderboard = {
                    "position": entry.overall_rank,
                    "total_candidates": leaderboard.entries.count(),
                    "score": truncate_float(float(entry.total_score)),
                    "rank_change": getattr(entry, "rank_change", 0),
                    "is_active": entry.overall_rank is not None,
                    "as_of_round": leaderboard.as_of_round,
                }

        # 3. Construct History
        history = []
        if screening_ranking:
            history.append({"stage": Stage.Type.SCREENING, "ranking": screening_ranking})
        if league_leaderboard:
            history.append({"stage": Stage.Type.LEAGUE, "ranking": league_leaderboard})
        if final_ranking:
            history.append({"stage": Stage.Type.FINAL, "ranking": final_ranking})

        # 4. Construct Active Context
        active_context = None
        if current_stage_obj:
            meta = STAGE_METADATA.get(current_stage_type, {})
            ranking = None
            if current_stage_type == Stage.Type.SCREENING:
                ranking = screening_ranking
            elif current_stage_type == Stage.Type.LEAGUE:
                ranking = league_leaderboard
            elif current_stage_type == Stage.Type.FINAL:
                ranking = final_ranking

            # Check for most recent exam in this stage
            latest_slot = (
                StageExam.objects.filter(competition_stage=current_stage_obj)
                .order_by("-round")
                .first()
            )

            has_taken_exam = False
            is_awaiting_results = False
            if latest_slot:
                access = ExamAccess.objects.filter(
                    candidate=candidate, exam=latest_slot.exam
                ).first()
                has_taken_exam = (
                    access and access.status == ExamAccess.Status.SUBMITTED
                )

                # Awaiting results if exam results are not yet published
                is_published = RankingSnapshot.objects.filter(
                    exam=latest_slot.exam, is_published=True
                ).exists()
                if has_taken_exam and not is_published:
                    is_awaiting_results = True

            # Advancement Policy Label
            policy = current_stage_obj.config.get("advancement_policy", {})
            metric_value_display = "N/A"
            if policy:
                mode = policy.get("mode")
                value = policy.get("value")
                if mode == "top_n":
                    metric_value_display = f"Top {value}"
                elif mode == "top_percent":
                    metric_value_display = f"Top {value}%"

            is_qualified = (
                enrollment.status == Enrollment.Status.ACTIVE if enrollment else True
            )

            # Determine UI Status Type
            status_type = "success"
            if is_awaiting_results:
                status_type = "pending"
            elif not has_taken_exam:
                status_type = "warning"
            elif not is_qualified:
                status_type = "error"

            status_messages = meta.get("status_messages", {}).get(status_type, {})

            active_context = {
                "stage": current_stage_type,
                "stage_display": meta.get("label"),
                "title": f"{meta.get('label')} Performance",
                "accent_color": meta.get("accent_color"),
                "ranking": ranking,
                "status_meta": {
                    "has_taken_exam": has_taken_exam,
                    "is_awaiting_results": is_awaiting_results,
                    "is_qualified": is_qualified,
                    "metric_label": meta.get("metric_label"),
                    "metric_value_display": metric_value_display,
                    "status_label": status_messages.get("label"),
                    "status_subtext": status_messages.get("subtext"),
                    "status_type": status_type,
                    "color": status_messages.get("color"),
                    "bg_color": status_messages.get("bg_color"),
                    "icon": status_messages.get("icon"),
                },
            }

            # Special Round-specific title for League
            if current_stage_type == Stage.Type.LEAGUE and league_leaderboard:
                total_rounds = StageExam.objects.filter(
                    competition_stage=current_stage_obj
                ).count()
                active_context["title"] = (
                    f"League Performance • Round {league_leaderboard['as_of_round']} of {total_rounds}"
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

        # Prefetch published ranking to avoid N+1
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
                    "score": truncate_float(float(res.score)) if is_published else None,
                    "percentage": (
                        truncate_float(float(res.score)) if is_published else None
                    ),
                    "date": res.recorded_at,
                    "status": exam.status,
                    "is_published": is_published,
                }
            )
        return history
