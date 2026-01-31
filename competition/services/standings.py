import uuid

from django.db import transaction

from competition.models import (
    CandidateCompetition,
    Standings,
    StandingsEntry,
    StageExam,
)
from vmlc.models import CandidateExamResult, Exam


class StandingsGenerationError(Exception):
    pass


class StandingsGenerator:
    """
    Service to generate immutable Standings and StandingsEntry records
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
    def generate_and_save_standings(
        self,
        ranking_policy: str = "dense_rank",  # e.g., 'dense_rank', 'sequential_rank'
        tie_break_strategy: str = "submission_time_asc",  # e.g., 'submission_time_asc', 'random'
        absentee_score: float = 0.0,
        published_by_staff_id: uuid.UUID = None,
    ) -> Standings:
        """
        Generates Standings and StandingsEntry records from exam results.

        Args:
            ranking_policy: Defines how ranks are assigned (e.g., 'dense_rank').
            tie_break_strategy: How to resolve ties in score (e.g., 'submission_time_asc').
            absentee_score: Score to assign to candidates who were eligible but didn't submit.
            published_by_staff_id: Staff member initiating this generation.

        Returns:
            The newly created Standings object.

        Raises:
            StandingsGenerationError: If validation fails or no results are found.
        """
        self._validate_preconditions()

        # Perform auto-scoring for all submissions before generating standings
        from vmlc.utils.functions import score_exam_submissions
        score_exam_submissions(self.exam.id)

        # Fetch raw CandidateExamResults for the associated vmlc.Exam
        raw_results = CandidateExamResult.objects.filter(exam=self.exam).select_related(
            "candidate", "candidate__user"
        )

        # Identify all eligible candidates for this stage/exam
        eligible_candidate_ids = set(
            CandidateCompetition.objects.filter(
                competition=self.competition,
                status=CandidateCompetition.Status.ACTIVE,  # Only active participants
            ).values_list("candidate_id", flat=True)
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

        # Add absentees (eligible candidates without a result)
        for cand_id in eligible_candidate_ids:
            if cand_id not in candidate_scores:
                candidate_scores[cand_id] = {
                    "score": absentee_score,
                    "recorded_at": None,  # Mark as absent
                }

        if not candidate_scores:
            raise StandingsGenerationError(
                f"No eligible candidate results found for Exam {self.exam.id}."
            )

        # Sort and Rank candidates
        sorted_candidates = sorted(
            candidate_scores.items(),
            key=lambda item: (
                item[1]["score"],
                (
                    item[1]["recorded_at"]
                    if tie_break_strategy == "submission_time_asc"
                    else None
                ),
            ),
            reverse=True,  # Higher score first, then earlier submission time
        )

        standings_entries_to_create = []
        previous_score = None
        current_rank = 0
        for idx, (candidate_id, data) in enumerate(sorted_candidates):
            score = data["score"]
            if score != previous_score:
                current_rank = idx + 1  # Dense rank

            # Find CandidateCompetition for FK
            candidate_competition = CandidateCompetition.objects.filter(
                candidate_id=candidate_id, competition=self.competition
            ).first()  # Should always exist if in eligible_candidate_ids

            standings_entries_to_create.append(
                StandingsEntry(
                    candidate_id=candidate_id,
                    candidate_competition=candidate_competition,
                    exam_score=score,
                    rank=current_rank,
                )
            )
            previous_score = score
            # TODO: decide on dense rank or not:
            # the following applies skips for ties. E.g. [..., 5, 5, 7, ...]
            # current_rank = idx + 1

        # Create Standings record
        standings = Standings.objects.create(
            competition=self.competition,
            stage=self.stage.type,  # Use the string type, as Standings takes string
            round=self.stage_exam.round,  # Using 'round' as defined in StageExam
            exam=self.exam,
            is_published=False,  # Must be explicitly published
            meta={
                "generated_by": str(published_by_staff_id) if published_by_staff_id else None,
                "policy": ranking_policy,
                "tie_break": tie_break_strategy,
            },
            # data_json is for denormalized export, not internal use. Leave blank.
        )

        # Assign standings to entries and bulk create
        for entry in standings_entries_to_create:
            entry.standings = standings
        StandingsEntry.objects.bulk_create(standings_entries_to_create)

        return standings


    def _validate_preconditions(self):
        """Internal validation before generating standings."""
        if not self.exam.status == Exam.Status.CONCLUDED:
            raise StandingsGenerationError(f"Exam {self.exam.id} is not yet concluded.")
        # TODO: Add more validation, e.g., ensure no existing published standings for this stage_exam
