import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.utils import timezone

from competition.models import (
    Competition,
    Stage,
    StageExam,
    CandidateCompetition,
    Standings,
    StandingsEntry,
)
from identity.models import Candidate
from vmlc.models import Exam, CandidateExamResult
from comms.models import Notification

logger = logging.getLogger(__name__)


class CandidateDashboardService:
    @staticmethod
    def get_dashboard_data(candidate: Candidate, participation: Optional[CandidateCompetition] = None) -> Dict[str, Any]:
        """
        Main entry point to get all candidate dashboard data.
        """
        active_comp = None
        if participation:
            active_comp = participation.competition
        else:
            active_comp = Competition.objects.filter(
                status=Competition.Status.ACTIVE
            ).first()

        context = CandidateDashboardService._get_context(candidate)

        if active_comp and not participation:
            participation = (
                CandidateCompetition.objects.filter(
                    candidate=candidate, competition=active_comp
                )
                .select_related("current_stage")
                .first()
            )

        progress = CandidateDashboardService._get_stage_progress(
            candidate, active_comp, participation
        )

        # 3. Active Exam
        active_exam_data = CandidateDashboardService._get_active_exam(
            candidate, active_comp, participation
        )

        # 4. Performance Snapshot
        performance = CandidateDashboardService._get_performance_snapshot(
            candidate, active_comp
        )

        # 5. Exam History
        history = CandidateDashboardService._get_exam_history(candidate)

        return {
            "candidate_context": context,
            "stage_progress": progress,
            "active_exam": active_exam_data,
            "performance_snapshot": performance,
            "exam_history": history,
        }

    @staticmethod
    def _get_context(candidate: Candidate) -> Dict[str, Any]:
        # Fetch last 5 unread notifications
        notifications = Notification.objects.filter(
            recipient=candidate.user,
            # TODO: use Notification.Type for better handling
            read=False,  # TODO: implement is_read_by_recipient
        ).order_by("-created_at")[:5]

        notification_list = [
            {
                "id": n.id,
                "type": "alert",  # TODO: improve this temporary placeholder later
                "message": n.message,
            }
            for n in notifications
        ]

        return {
            "full_name": candidate.user.get_full_name(),
            "role": candidate.role,
            "profile_picture": (
                candidate.user.profile_picture.url
                if candidate.user.profile_picture
                else None
            ),
            "is_setup_complete": candidate.user.is_setup_complete,
            "status": candidate.status,
            "notifications": notification_list,  # TODO: probably rename this to 'alert_notifications'
        }

    @staticmethod
    def _get_stage_progress(
        candidate: Candidate,
        active_comp: Optional[Competition],
        participation: Optional[CandidateCompetition],
    ) -> Dict[str, Any]:
        if not active_comp or not participation:
            # Return None instead of candidate.role
            # (as role is for permissions and no longer stage indication)
            return {
                "current_stage": None,
                "current_round": None,
                "total_rounds": 0,
                "published_rounds": 0,
                "has_taken_current_round": False,
                "qualification_status": None,
            }

        current_stage = participation.current_stage
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
        slots = StageExam.objects.filter(
            competition_stage=current_stage, is_active=True
        ).order_by("round")

        total_rounds = slots.count()

        # Published standings in current stage
        published_rounds = Standings.objects.filter(
            competition=active_comp, stage=current_stage.type, is_published=True
        ).count()

        # Current round (latest one that is active)
        latest_slot = slots.last()
        current_round = latest_slot.round if latest_slot else None

        has_taken_current_round = False
        if latest_slot:
            try:
                exam = latest_slot.exam
                has_taken_current_round = CandidateExamResult.objects.filter(
                    candidate=candidate, exam=exam
                ).exists()
            except Exam.DoesNotExist:
                pass

        # Qualification Status logic
        qualification_status = {
            "is_qualified": participation.status == CandidateCompetition.Status.ACTIVE,
            "advancement_policy": current_stage.config.get("advancement_policy", None),
            "message": (
                f"You are currently {participation.get_status_display()} "
                f"in the {current_stage.get_type_display()} stage."
            ),
        }

        return {
            "current_stage": current_stage.type,
            "current_round": current_round,
            "total_rounds": total_rounds,
            "published_rounds": published_rounds,
            "has_taken_current_round": has_taken_current_round,
            "qualification_status": qualification_status,
        }

    @staticmethod
    def _get_active_exam(
        candidate: Candidate,
        active_comp: Optional[Competition],
        participation: Optional[CandidateCompetition],
    ) -> Optional[Dict[str, Any]]:
        if not active_comp or not participation or not participation.current_stage:
            return None

        # Look for an ONGOING exam first, then the next SCHEDULED one in the current stage

        # Get all active slots for current stage
        slots = (
            StageExam.objects.filter(
                competition_stage=participation.current_stage, is_active=True
            )
            .select_related("exam", "exam__questions")
            .order_by("round")
        )

        active_exam_data = None
        for slot in slots:
            try:
                exam = slot.exam
                status = exam.status

                # Check if they already participated
                has_participated = CandidateExamResult.objects.filter(
                    candidate=candidate, exam=exam
                ).exists()

                if status in [Exam.Status.ONGOING, Exam.Status.SCHEDULED]:
                    active_exam_data = {
                        "id": str(exam.id),
                        "title": exam.get_title(),
                        "stage": participation.current_stage.type,
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
                        "has_participated": has_participated,
                    }
                    if status == Exam.Status.ONGOING and not has_participated:
                        # Found our primary target, an ongoing exam
                        # that the candidate hasn't yet participated in
                        break
            except Exam.DoesNotExist:
                continue

        return active_exam_data

    @staticmethod
    def _get_performance_snapshot(
        candidate: Candidate, active_comp: Optional[Competition]
    ) -> Dict[str, Any]:
        snapshot = {"screening_standing": None, "league_leaderboard": None}

        # Screening Standing
        screening_standings = Standings.objects.filter(
            competition=active_comp, stage=Stage.Type.SCREENING, is_published=True
        ).first()

        if screening_standings:
            entry = StandingsEntry.objects.filter(
                # at this point, we should find a relationship, since a standings
                # table is populated with StandingsEntry entities when generated
                # in competition/services/standings.py:155
                standings=screening_standings,
                candidate=candidate,
            ).first()
            if entry:
                snapshot["screening_standing"] = {
                    "rank": entry.rank,
                    "total_candidates": screening_standings.entries.count(),
                    "score": float(entry.exam_score),
                    "percentile": entry.percentile,
                }

        # League Leaderboard
        from competition.services.leaderboard import LeaderboardService

        leaderboard = LeaderboardService.get_latest_league_leaderboard(active_comp)

        if leaderboard:
            # processed_entries is a list of entries with rank_change annotated
            entry = next(
                (
                    e
                    for e in leaderboard.processed_entries
                    if e.candidate_id == candidate.pk
                ),
                None,
            )
            if entry:
                snapshot["league_leaderboard"] = {
                    "overall_rank": entry.overall_rank,
                    "total_candidates": leaderboard.entries.count(),
                    "total_score": float(entry.total_score),
                    "rank_change": getattr(entry, "rank_change", 0),
                    "as_of_round": leaderboard.as_of_round,
                }

        return snapshot

    @staticmethod
    def _get_exam_history(candidate: Candidate) -> List[Dict[str, Any]]:
        results = (
            CandidateExamResult.objects.filter(candidate=candidate)
            .select_related("exam", "exam__competition_slot__competition_stage")
            .order_by("-recorded_at")
        )

        history = []
        for res in results:
            exam = res.exam
            slot = exam.competition_slot
            history.append(
                {
                    "exam_id": str(exam.id),
                    "exam_title": exam.get_title(),
                    "stage": slot.competition_stage.type if slot else "N/A",
                    "round": slot.round if slot else None,
                    "score": float(res.score),
                    "percentage": float(res.score),
                    "date": res.recorded_at,
                    "status": exam.status,
                }
            )
        return history
