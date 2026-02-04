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
from vmlc.models import Exam, CandidateExamResult, ExamAccess
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
            is_read_by_recipient=False,
        ).order_by("-created_at")[:5]

        notification_map = {
            "info": [],
            "success": [],
            "error": []
        }
        n_type_key_map = {
            Notification.Type.INFO: "info",
            Notification.Type.SUCCESS: "success",
            Notification.Type.ERROR: "error",

        }
        
        for n in notifications:
            key = n_type_key_map.get(n.type)
            if key:
                notification_map[key].append({
                    "id": n.id,
                    "message": n.message,
                })

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
            "notifications": notification_map,
        }

    @staticmethod
    def _get_stage_progress(
        candidate: Candidate,
        active_comp: Optional[Competition],
        participation: Optional[CandidateCompetition],
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
        current_stage = participation.current_stage if participation else None
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
        from django.db.models import Q
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
                has_taken_current_round = ExamAccess.objects.filter(
                    candidate=candidate,
                    exam=exam,
                    status=ExamAccess.Status.SUBMITTED,
                ).exists()
            except Exam.DoesNotExist:
                pass

        # Qualification Status logic
        is_qualified = (
            participation.status == CandidateCompetition.Status.ACTIVE
            if participation
            else True  # Assume active if just discovered by role
        )
        status_display = (
            participation.get_status_display() if participation else "Active"
        )

        qualification_status = {
            "is_qualified": is_qualified,
            "advancement_policy": current_stage.config.get("advancement_policy", None),
            "message": (
                f"You are currently {status_display} "
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
        if not active_comp:
            return None

        # Determine the current stage - fallback to candidate role if not enrolled
        current_stage = participation.current_stage if participation else None
        if not current_stage:
            current_stage = Stage.objects.filter(
                competition=active_comp, type=candidate.role
            ).first()

        if not current_stage:
            return None

        # Get all active slots for current stage
        from django.db.models import Q
        from competition.services.eligibility import EligibilityService
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
                    candidate=candidate,
                    exam=exam
                ).first()
                
                has_participated = access.status == ExamAccess.Status.SUBMITTED if access else False

                if status in [Exam.Status.ONGOING, Exam.Status.SCHEDULED]:
                    exam_data = {
                        "id": str(exam.id),
                        "title": exam.get_title(),
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
                        "has_participated": has_participated,
                        "is_eligible": is_eligible,
                        "access_status": access.status if access else None,
                    }
                    if status == Exam.Status.ONGOING and is_eligible and not has_participated:
                        # Found our primary target, an ongoing exam
                        # that the candidate hasn't yet participated in
                        active_exam_data = exam_data
                        break
                    
                    if not active_exam_data:
                        active_exam_data = exam_data

                elif status == Exam.Status.CONCLUDED and has_participated:
                    # Check if standings are published
                    standing = Standings.objects.filter(
                        exam=exam, is_published=True
                    ).first()

                    is_published = standing is not None

                    if not active_exam_data:
                        active_exam_data = {
                            "id": str(exam.id),
                            "title": exam.get_title(),
                            "stage": current_stage.type,
                            "round": slot.round,
                            "status": "results_published" if is_published else "awaiting_results",
                            "has_participated": True,
                        }
            except Exam.DoesNotExist:
                continue

        return active_exam_data

    @staticmethod
    def _get_performance_snapshot(
        candidate: Candidate, active_comp: Optional[Competition]
    ) -> Dict[str, Any]:
        snapshot = {
            "screening_standing": None,
            "league_leaderboard": None,
            "final_standing": None,
        }

        if not active_comp:
            return snapshot

        from django.db.models import Q

        # 1. Fetch Screening and Final Standings Entries
        entries = StandingsEntry.objects.filter(
            Q(standings__stage=Stage.Type.SCREENING)
            | Q(standings__stage=Stage.Type.FINAL),
            standings__competition=active_comp,
            standings__is_published=True,
            candidate=candidate,
        ).select_related("standings")

        for entry in entries:
            stage_type = entry.standings.stage
            data = {
                "rank": entry.rank,
                "total_candidates": entry.standings.entries.count(),
                "score": float(entry.exam_score),
                "percentile": entry.percentile,
                "exam_id": str(entry.standings.exam_id),
                "exam_title": entry.standings.exam.get_title(),
            }

            if stage_type == Stage.Type.SCREENING:
                snapshot["screening_standing"] = data
            elif stage_type == Stage.Type.FINAL:
                snapshot["final_standing"] = data

        # 2. League Leaderboard
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
                    "is_active": entry.overall_rank is not None,
                }

        return snapshot

    @staticmethod
    def _get_exam_history(candidate: Candidate) -> List[Dict[str, Any]]:
        results = (
            CandidateExamResult.objects.filter(candidate=candidate)
            .select_related("exam", "exam__competition_slot__competition_stage")
            .order_by("-recorded_at")
        )

        # Prefetch published standings to avoid N+1
        published_exam_ids = set(
            Standings.objects.filter(
                exam_id__in=[res.exam_id for res in results],
                is_published=True
            ).values_list("exam_id", flat=True)
        )

        from vmlc.v2.utils import truncate_float
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
                    "percentage": truncate_float(float(res.score)) if is_published else None,
                    "date": res.recorded_at,
                    "status": exam.status,
                    "is_published": is_published,
                }
            )
        return history
