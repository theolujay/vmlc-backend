import logging
from typing import Any, Dict, List, Optional

from django.db.models import Avg, Count, Max, Min, Sum

from competition.models import (
    Competition,
    Enrollment,
    LeagueLeaderboardEntry,
    RankingSnapshotEntry,
    Stage,
    StageExam,
)
from identity.models import Candidate
from vmlc.models import CandidateExamResult, Exam

logger = logging.getLogger(__name__)


class CandidateRecordService:
    """
    Handles retrieval of candidate performance history and available exams
    by leveraging Competition context.
    """

    @staticmethod
    def get_candidate_records(candidate: Candidate) -> Dict[str, Any]:
        """
        Returns a dictionary of a candidate's performance stats, results, and available exams.
        """
        return {
            "performance": CandidateRecordService.get_performance_stats(candidate),
            "available_exams": CandidateRecordService.get_available_exams(candidate),
        }

    @staticmethod
    def get_available_exams(candidate: Candidate) -> List[Dict[str, Any]]:
        """
        Fetches exams available to the candidate based on their active competition enrollment.
        """
        # Get active competition and enrollment context
        enrollment = (
            Enrollment.objects.filter(
                candidate=candidate,
                competition__status=Competition.Status.ACTIVE,
                status=Enrollment.Status.ACTIVE,
            )
            .select_related("current_stage")
            .first()
        )

        if not enrollment or not enrollment.current_stage:
            logger.info(f"No active enrollment found for candidate {candidate.pk}")
            return []

        # Get exams for this specific stage
        stage_exams = (
            StageExam.objects.filter(
                competition_stage=enrollment.current_stage, is_active=True
            )
            .select_related("exam")
            .order_by("round")
        )

        available_exams_list = []
        for slot in stage_exams:
            try:
                exam = slot.exam
                # 3. Check if exam is currently open
                if exam.is_active and exam.is_currently_open:
                    # Check if they already participated in this exam
                    has_participated = CandidateExamResult.objects.filter(
                        candidate=candidate, exam=exam
                    ).exists()

                    if not has_participated:
                        available_exams_list.append(
                            {
                                "id": str(exam.id),
                                "title": exam.get_title(),
                                "description": exam.description,
                                "open_duration_hours": exam.open_duration_hours,
                                "scheduled_date": exam.scheduled_date,
                                "countdown_minutes": exam.countdown_minutes,
                                "question_count": exam.get_question_count(),
                                "stage": enrollment.current_stage.type,
                                "round": slot.round,
                            }
                        )
            except Exam.DoesNotExist:
                continue

        return available_exams_list

    @staticmethod
    def get_performance_stats(candidate: Candidate) -> Dict[str, Any]:
        """
        Computes performance statistics for the candidate leveraging modern RankingSnapshot and Leaderboards.
        """
        results_qs = CandidateExamResult.objects.filter(candidate=candidate)

        result_stats = results_qs.aggregate(
            total_exams_taken=Count("id"),
            average_score=Avg("score"),
            highest_score=Max("score"),
            lowest_score=Min("score"),
            total_score=Sum("score"),
        )

        recent_result = (
            results_qs.order_by("-recorded_at").select_related("exam").first()
        )

        latest_score_data = None
        if recent_result:
            latest_score_data = {
                "score": float(recent_result.score),
                "exam_title": recent_result.exam.get_title(),
                "date": recent_result.recorded_at,
            }

        # 2. Get Ranking info from Competition models
        ranking_info = CandidateRecordService._get_competition_ranking(candidate)

        return {
            "stats": {
                "total_score": float(result_stats["total_score"] or 0),
                "average_score": round(float(result_stats["average_score"] or 0), 2),
                "leaderboard_ranking": ranking_info,
                "latest_score": latest_score_data,
                "highest_score": float(result_stats["highest_score"] or 0),
                "total_exams_taken": result_stats["total_exams_taken"],
                "lowest_result": float(result_stats["lowest_score"] or 0),
                "highest_obtainable_score": 100.0,
            },
            "exams_taken": CandidateRecordService.get_exams_taken(
                candidate, results_qs
            ),
        }

    @staticmethod
    def _get_competition_ranking(candidate: Candidate) -> Optional[Dict[str, Any]]:
        """
        Retrieves the candidate's ranking from the latest aggregate leaderboard.
        """
        # Look for their entry in the latest published AggregateLeaderboard
        entry = (
            LeagueLeaderboardEntry.objects.filter(
                candidate=candidate,
                leaderboard__competition__status=Competition.Status.ACTIVE,
            )
            .select_related("leaderboard")
            .order_by("-leaderboard__as_of_round", "-leaderboard__created_at")
            .first()
        )

        if entry:
            return {
                "current_rank": entry.overall_rank,
                "total_candidates": entry.leaderboard.entries.count(),
                "as_of_round": entry.leaderboard.as_of_round,
            }

        # Fallback to Screening RankingSnapshot if not in League yet
        screening_entry = (
            RankingSnapshotEntry.objects.filter(
                candidate=candidate,
                ranking_snapshot__stage=Stage.Type.SCREENING,
                ranking_snapshot__is_published=True,
            )
            .select_related("ranking_snapshot")
            .order_by("-ranking_snapshot__created_at")
            .first()
        )

        if screening_entry:
            return {
                "current_rank": screening_entry.rank,
                "total_candidates": screening_entry.ranking_snapshot.entries.count(),
                "stage": "screening",
            }

        return None

    @staticmethod
    def get_exams_taken(candidate: Candidate, results_qs=None) -> List[Dict[str, Any]]:
        """
        Returns a list of exams taken by the candidate with detailed breakdown.
        """
        if results_qs is None:
            results_qs = CandidateExamResult.objects.filter(candidate=candidate)

        results = (
            results_qs.select_related(
                "exam",
                "exam__competition_slot__competition_stage",
                "score_submitted_by__user",
            )
            .prefetch_related("answers__question")
            .order_by("-recorded_at")
        )

        exams_taken_list = []
        for result in results:
            exam = result.exam
            slot = exam.competition_slot

            answers = result.answers.all()
            submission_list = []
            for answer in answers:
                submission_list.append(
                    {
                        "question_id": answer.question.id,
                        "question_text": answer.question.text,
                        "option_a": answer.question.option_a,
                        "option_b": answer.question.option_b,
                        "option_c": answer.question.option_c,
                        "option_d": answer.question.option_d,
                        "selected_option": answer.selected_option,
                        "answered_at": answer.answered_at.isoformat(),
                    }
                )

            exams_taken_list.append(
                {
                    "exam_id": str(exam.id),
                    "exam_title": exam.get_title(),
                    "exam_stage": slot.competition_stage.type if slot else "N/A",
                    "round": slot.round if slot else None,
                    "scheduled_date": exam.scheduled_date,
                    "score": float(result.score),
                    "recorded_at": result.recorded_at.isoformat(),
                    "score_submitted_by": (
                        result.score_submitted_by.user.get_full_name()
                        if result.score_submitted_by and result.score_submitted_by.user
                        else None
                    ),
                    "auto_score": result.auto_score,
                    "submission": submission_list,
                }
            )
        return exams_taken_list
