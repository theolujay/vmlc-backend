import logging
import uuid

from django.db import transaction

from competition.models import (
    Enrollment,
    RankingSnapshot,
    RankingSnapshotEntry,
    StageExam,
)
from vmlc.models import CandidateExamResult, Exam

logger = logging.getLogger(__name__)


class RankingSnapshotGenerationError(Exception):
    pass


class RankingSnapshotGenerator:
    """
    Service to generate immutable RankingSnapshot and RankingEntry records
    for a given exam within a competition stage.
    """

    def __init__(self, stage_exam_id: uuid.UUID):
        self.stage_exam = StageExam.objects.select_related(
            "competition_stage__competition", "exam"
        ).get(id=stage_exam_id)
        self.competition = self.stage_exam.competition_stage.competition
        self.stage = self.stage_exam.competition_stage
        self.exam = self.stage_exam.exam

    @transaction.atomic
    def generate_and_save_ranking(
        self,
        ranking_policy: str = "dense_rank",  # e.g., 'dense_rank', 'sequential_rank'
        tie_break_strategy: str = "submission_time_asc",  # e.g., 'submission_time_asc', 'random'
        absentee_score: float = 0.0,
        published_by_staff_id: uuid.UUID = None,
    ) -> RankingSnapshot:
        """
        Generates RankingSnapshot and RankingEntry records from exam results.

        Args:
            ranking_policy: Defines how ranks are assigned (e.g., 'dense_rank').
            tie_break_strategy: How to resolve ties in score (e.g., 'submission_time_asc').
            absentee_score: Score to assign to candidates who were eligible but didn't submit.
            published_by_staff_id: Staff member initiating this generation.

        Returns:
            The newly created RankingSnapshot object.

        Raises:
            RankingSnapshotGenerationError: If validation fails or no results are found.
        """
        self._validate_preconditions()

        # Perform auto-scoring for all submissions before generating ranking
        from vmlc.utils.functions import compute_exam_results

        compute_exam_results(self.exam.id)

        # Fetch raw CandidateExamResults for the associated vmlc.Exam
        raw_results = CandidateExamResult.objects.filter(exam=self.exam).select_related(
            "candidate", "candidate__user"
        )
        logger.debug(
            f"RankingSnapshotGenerator: Found {raw_results.count()} raw CandidateExamResults for Exam {self.exam.id}."
        )

        # Identify all eligible candidates for this stage/exam
        eligible_candidate_ids = set(
            Enrollment.objects.filter(
                competition=self.competition,
                status=Enrollment.Status.ACTIVE,  # Only active participants
            ).values_list("candidate_id", flat=True)
        )
        logger.debug(
            f"RankingSnapshotGenerator: Found {len(eligible_candidate_ids)} eligible candidates for Competition {self.competition.id}."
        )

        # Map results to eligible candidates, handle absentees
        candidate_scores = (
            {}
        )  # {candidate_id: {'score': float, 'recorded_at': datetime}}
        for res in raw_results:
            if res.candidate_id in eligible_candidate_ids:
                candidate_scores[res.candidate_id] = {
                    "score": float(res.score),
                    "recorded_at": res.recorded_at,
                }
        logger.debug(
            f"RankingSnapshotGenerator: Mapped {len(candidate_scores)} candidate scores after eligibility check."
        )

        # Add absentees (eligible candidates without a result)
        for cand_id in eligible_candidate_ids:
            if cand_id not in candidate_scores:
                candidate_scores[cand_id] = {
                    "score": absentee_score,
                    "recorded_at": None,  # Mark as absent
                }

        if not candidate_scores:
            raise RankingSnapshotGenerationError(
                f"No eligible candidate results found for Exam {self.exam.id}."
            )

        # Sort and Rank candidates
        def sort_key(item):
            data = item[1]
            score = data["score"]
            secondary = 0
            if tie_break_strategy == "submission_time_asc":
                if data["recorded_at"]:
                    # Earlier time (smaller timestamp) -> larger negative value
                    secondary = -data["recorded_at"].timestamp()
                else:
                    # Absentees last -> smallest value
                    secondary = float("-inf")
            return (score, secondary)

        sorted_candidates = sorted(
            candidate_scores.items(),
            key=sort_key,
            reverse=True,  # Higher score first, then earlier submission time
        )

        ranking_entries_to_create = []
        previous_score = None
        current_rank = 0
        for idx, (candidate_id, data) in enumerate(sorted_candidates):
            score = data["score"]
            if score != previous_score:
                current_rank = idx + 1  # Dense rank

            # Find Enrollment for FK
            enrollment = Enrollment.objects.filter(
                candidate_id=candidate_id, competition=self.competition
            ).first()  # Should always exist if in eligible_candidate_ids

            ranking_entries_to_create.append(
                RankingSnapshotEntry(
                    candidate_id=candidate_id,
                    enrollment=enrollment,
                    exam_score=score,
                    rank=current_rank,
                )
            )
            previous_score = score
            # TODO: decide on dense rank or not:
            # the following applies skips for ties. E.g. [..., 5, 5, 7, ...]
            # current_rank = idx + 1

        # Attempt to get existing ranking for this exam with lock to prevent race conditions
        try:
            existing_ranking = RankingSnapshot.objects.select_for_update().get(
                exam=self.exam
            )
            # If found, delete it and its entries to ensure a clean regeneration
            existing_ranking.delete()
        except RankingSnapshot.DoesNotExist:
            pass  # No existing ranking, proceed with creation

        # Create RankingSnapshot record
        ranking = RankingSnapshot.objects.create(
            competition=self.competition,
            stage=self.stage.type,
            round=self.stage_exam.round,
            exam=self.exam,
            is_published=False,
            meta={
                "generated_by": (
                    str(published_by_staff_id) if published_by_staff_id else None
                ),
                "policy": ranking_policy,
                "tie_break": tie_break_strategy,
            },
        )

        # Assign ranking to entries and bulk create
        for entry in ranking_entries_to_create:
            entry.ranking_snapshot = ranking
        RankingSnapshotEntry.objects.bulk_create(ranking_entries_to_create)

        # Invalidate Caches
        from vmlc.v2.utils import (
            invalidate_staff_dashboard,
            invalidate_league_leaderboard,
            invalidate_exam_cache,
            invalidate_candidate_cache,
        )

        # Capture exam_id and candidate_ids explicitly to avoid closure issues
        exam_id = self.exam.id
        candidate_ids = list(candidate_scores.keys())

        def clear_ranking_cache():
            invalidate_staff_dashboard()
            invalidate_league_leaderboard()
            invalidate_exam_cache(exam_id)
            for cand_id in candidate_ids:
                invalidate_candidate_cache(cand_id)

        transaction.on_commit(clear_ranking_cache)

        return ranking

    def _validate_preconditions(self):
        """Internal validation before generating ranking."""
        if not self.exam.status == Exam.Status.CONCLUDED:
            raise RankingSnapshotGenerationError(
                f"Exam {self.exam.id} is not yet concluded."
            )
        # TODO: Add more validation, e.g., ensure no existing published ranking for this stage_exam
