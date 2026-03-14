import logging
import uuid
from datetime import datetime, timezone

from django.db import transaction

from competition.models import (
    Enrollment,
    RankingSnapshot,
    RankingSnapshotEntry,
    StageExam,
)
from vmlc.models import CandidateExamResult, Exam, ExamAccess
from identity.models import Candidate
from vmlc.utils.functions import compute_exam_results

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
        ranking_policy: str = "standard",  # 'standard' | 'dense'
        tie_break_strategy: str = "submission_time_asc",  # only applied when ranking_policy='dense'
        absentee_score: float | None = None,
        actor_id: uuid.UUID = None,
    ) -> RankingSnapshot:
        """
        Generates RankingSnapshot and RankingEntry records from exam results.

        Args:
            ranking_policy: Defines how ranks are assigned ('standard' or 'dense').
                - 'standard': Ties are preserved. Identical scores receive the same rank,
                  and a gap is introduced in subsequent ranks (1, 1, 3, 4...).
                - 'dense': tie_break_strategy is applied to resolve ties by submission time.
                  Candidates only share a rank if both score and submission time are identical
                  (1, 2, 3, 4...).
            tie_break_strategy: How to resolve ties when ranking_policy='dense'.
                Ignored entirely for 'standard' policy.
                Currently supported: 'submission_time_asc'.
            absentee_score: Score to assign to candidates who were eligible but didn't submit.
                If None, they are marked as 'absent'.
            actor_id: Staff member initiating this generation.

        Returns:
            The newly created RankingSnapshot object.

        Raises:
            RankingSnapshotGenerationError: If validation fails or no results are found.
        """
        self._validate_preconditions()

        # Perform auto-scoring for all submissions before generating ranking
        _ = compute_exam_results(self.exam.id)

        eligible_candidate_ids = self._find_eligible_candidate_ids()
        candidate_scores = self._build_candidate_scores(eligible_candidate_ids, absentee_score)

        if not candidate_scores:
            raise RankingSnapshotGenerationError(
                f"No eligible candidate results found for Exam {self.exam.id}."
            )

        sorted_candidates = self._sort_candidates(candidate_scores, ranking_policy, tie_break_strategy)
        ranking_entries_to_create = self._assign_ranks(sorted_candidates, ranking_policy)
        ranking = self._create_ranking_snapshot(ranking_policy, tie_break_strategy, actor_id)

        for entry in ranking_entries_to_create:
            entry.ranking_snapshot = ranking
        RankingSnapshotEntry.objects.bulk_create(ranking_entries_to_create)

        candidate_ids = list(candidate_scores.keys())
        self._register_cache_invalidation(candidate_ids)

        return ranking

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_eligible_candidate_ids(self) -> set:
        """
        Returns the set of candidate IDs who are:
          - Associated with an active, email-verified user account.
          - Actively enrolled in the competition tied to this stage exam.
        """
        active_candidate_ids = set(
            Candidate.objects.filter(
                user__is_active=True,
                user__is_email_verified=True,
            ).values_list("pk", flat=True)
        )

        eligible_candidate_ids = set(
            Enrollment.objects.filter(
                competition=self.competition,
                status=Enrollment.Status.ACTIVE,
                candidate_id__in=active_candidate_ids,
            ).values_list("candidate_id", flat=True)
        )

        logger.debug(
            f"RankingSnapshotGenerator: Found {len(eligible_candidate_ids)} eligible candidates "
            f"for Competition {self.competition.id}."
        )

        return eligible_candidate_ids

    def _build_candidate_scores(
        self,
        eligible_candidate_ids: set,
        absentee_score: float | None,
    ) -> dict:
        """
        Maps CandidateExamResults to eligible candidates and appends absentees.

        Returns:
            A dict keyed by candidate_id:
            {
                candidate_id: {
                    'score': float | 'absent',
                    'time_used': float | None,  # seconds elapsed from exam start to submission
                }
            }
        """
        raw_results = CandidateExamResult.objects.filter(
            exam=self.exam,
        ).select_related("candidate", "candidate__user")

        logger.debug(
            f"RankingSnapshotGenerator: Found {raw_results.count()} raw CandidateExamResults "
            f"for Exam {self.exam.id}."
        )

        from django.db.models import Avg
        exam_access_by_candidate = {
            item["candidate_id"]: item
            for item in ExamAccess.objects.filter(
                candidate_id__in=eligible_candidate_ids,
                exam=self.exam,
            ).annotate(avg_suspicion=Avg("heartbeats__suspicion_score")).values(
                "candidate_id", "status", "started_at", "submitted_at", "proctoring_status", "avg_suspicion"
            )
        }

        candidate_scores = {}

        for res in raw_results:
            if res.candidate_id in eligible_candidate_ids:
                access = exam_access_by_candidate.get(res.candidate_id, {})
                started_at = access.get("started_at")
                submitted_at = access.get("submitted_at")
                time_used = (
                    (submitted_at - started_at).total_seconds()
                    if started_at and submitted_at
                    else None
                )
                
                candidate_scores[res.candidate_id] = {
                    "score": float(res.score),
                    "time_used": time_used,  # seconds elapsed between start and submission
                    "proctoring_status": access.get("proctoring_status"),
                    "violation_score": access.get("avg_suspicion") or 0.0,
                }

        # Add absentees — eligible candidates with no submitted result
        for cand_id in eligible_candidate_ids:
            if cand_id not in candidate_scores:
                candidate_scores[cand_id] = {
                    "score": absentee_score if absentee_score is not None else "absent",
                    "time_used": None,
                    "proctoring_status": None,
                    "violation_score": 0.0,
                }

        logger.debug(
            f"RankingSnapshotGenerator: Mapped {len(candidate_scores)} candidate scores "
            f"after eligibility check."
        )

        return candidate_scores

    def _sort_candidates(
        self,
        candidate_scores: dict,
        ranking_policy: str,
        tie_break_strategy: str,
    ) -> list[tuple]:
        """
        Sorts candidates in preparation for rank assignment.

        - 'standard': Sort by score only (descending). Ties are intentionally preserved.
        - 'dense': Sort by score descending, then by time_used (submitted_at - started_at)
          ascending to break ties. This is fairer than sorting by submitted_at alone, since
          candidates can begin the exam at any point during a multi-hour access window.
          Absentees (time_used=None) are always placed last.
        """
        def score_as_float(item):
            score = item[1]["score"]
            return -1.0 if score == "absent" else float(score)

        if ranking_policy == "dense" and tie_break_strategy == "submission_time_asc":
            return sorted(
                candidate_scores.items(),
                key=lambda item: (
                    -score_as_float(item),  # negate so highest score sorts first (ascending)
                    # Lower time_used (faster completion) ranks higher.
                    # Absentees (time_used=None) sort last via float("inf").
                    item[1]["time_used"] if item[1]["time_used"] is not None else float("inf"),
                ),
            )

        # Standard policy: sort by score only (descending), ties preserved naturally.
        return sorted(candidate_scores.items(), key=lambda item: -score_as_float(item))

    def _assign_ranks(
        self,
        sorted_candidates: list[tuple],
        ranking_policy: str,
    ) -> list[RankingSnapshotEntry]:
        """
        Iterates over sorted candidates and assigns ranks according to the ranking policy.

        - 'standard': Identical scores share the same rank. A gap is introduced afterward
          (1, 1, 3, 4...). Ties are expected and no tie_break_reason is recorded.
        - 'dense': Ranks increment by 1 for each unique (score, time_used) pair.
          Two candidates only share a rank in the practically unlikely event of an identical
          score AND identical time_used (1, 2, 3, 4...).
        """
        entries = []
        previous_score = None
        previous_time_used = None
        current_rank = 0
        total_candidates = len(sorted_candidates)

        for idx, (candidate_id, data) in enumerate(sorted_candidates):
            score = data["score"]
            time_used = data["time_used"]
            tie_break_reason = None

            if ranking_policy == "dense":
                is_tied = (
                    score == previous_score
                    and time_used == previous_time_used
                )
                if not is_tied:
                    current_rank += 1
                else:
                    tie_break_reason = (
                        f"Tied at score {score} with identical time used ({time_used}s); "
                        f"rank held at {current_rank} ('dense' policy)."
                    )
            else:  # standard
                if score != previous_score:
                    current_rank = idx + 1
                # else: same rank, no comment needed — ties are intentional

            percentile = ((total_candidates - current_rank) / total_candidates) * 100 if total_candidates > 0 else 0.0

            enrollment = Enrollment.objects.filter(
                candidate_id=candidate_id,
                competition=self.competition,
            ).first()

            entries.append(
                RankingSnapshotEntry(
                    candidate_id=candidate_id,
                    enrollment=enrollment,
                    exam_score=None if score == "absent" else score,
                    rank=current_rank,
                    percentile=percentile,
                    time_used=time_used,
                    tie_break_reason=tie_break_reason,
                    proctoring_status=data.get("proctoring_status"),
                    violation_score=data.get("violation_score", 0.0),
                )
            )

            previous_score = score
            previous_time_used = time_used

        return entries

    def _create_ranking_snapshot(
        self,
        ranking_policy: str,
        tie_break_strategy: str,
        actor_id: uuid.UUID | None,
    ) -> RankingSnapshot:
        """
        Creates and persists the RankingSnapshot record.
        Setting is_active=True triggers RankingSnapshot.save() to deactivate
        all prior snapshots for this exam.
        """
        return RankingSnapshot.objects.create(
            competition=self.competition,
            stage=self.stage.type,
            round=self.stage_exam.round,
            exam=self.exam,
            is_active=True,
            is_published=False,
            meta={
                "generated_by": str(actor_id) if actor_id else None,
                "ranking_policy": ranking_policy,
                "tie_break_strategy": tie_break_strategy if ranking_policy == "dense" else None,
            },
        )

    def _register_cache_invalidation(self, candidate_ids: list) -> None:
        """
        Registers a post-commit hook to invalidate all ranking-related caches.
        candidate_ids and exam_id are captured explicitly to avoid closure issues.
        """
        from vmlc.v2.utils import (
            invalidate_staff_dashboard,
            invalidate_score_boards,
            invalidate_exam_cache,
            invalidate_candidate_cache,
        )

        exam_id = self.exam.id

        def clear_ranking_cache():
            invalidate_staff_dashboard()
            invalidate_score_boards()
            invalidate_exam_cache(exam_id)
            for cand_id in candidate_ids:
                invalidate_candidate_cache(cand_id)

        transaction.on_commit(clear_ranking_cache)

    def _validate_preconditions(self):
        """Raises if the exam has not yet concluded."""
        if self.exam.status != Exam.Status.CONCLUDED:
            raise RankingSnapshotGenerationError(
                f"Exam {self.exam.id} is not yet concluded."
            )