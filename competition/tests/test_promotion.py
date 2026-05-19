from django.test import TestCase
from django.utils import timezone

from competition.models import (
    Competition,
    Enrollment,
    EnrollmentStageProgress,
    RankingSnapshot,
    RankingSnapshotEntry,
    Stage,
    StageExam,
)
from competition.services.promotion import PromotionService
from identity.models import Candidate, User
from vmlc.models import Exam


class PromotionLogicTest(TestCase):
    def setUp(self):
        self.competition = Competition.objects.create(
            name="Test Comp", edition=1, status=Competition.Status.ACTIVE
        )
        self.screening_stage = Stage.objects.create(
            competition=self.competition,
            type=Stage.Type.SCREENING,
            order=1,
            config={"advancement_policy": {"mode": "top_n", "value": 1}},
        )
        self.league_stage = Stage.objects.create(
            competition=self.competition, type=Stage.Type.LEAGUE, order=2
        )

        # Create 2 candidates
        self.users = []
        self.candidates = []
        for i in range(2):
            user = User.objects.create_user(
                email=f"cand{i}@example.com", password="pass", username=f"cand{i}"
            )
            candidate = Candidate.objects.create(
                user=user, role=Candidate.Roles.SCREENING
            )
            self.users.append(user)
            self.candidates.append(candidate)

            enrollment = Enrollment.objects.create(
                candidate=candidate,
                competition=self.competition,
                current_stage=self.screening_stage,
                status=Enrollment.Status.ACTIVE,
            )
            EnrollmentStageProgress.objects.create(
                enrollment=enrollment,
                stage=self.screening_stage,
                status=EnrollmentStageProgress.Status.IN_PROGRESS,
                started_at=timezone.now(),
            )

    def test_discontinued_on_elimination(self):
        # Create an exam for the snapshot
        stage_exam = StageExam.objects.create(
            competition_stage=self.screening_stage, round=1, is_active=True
        )
        exam = Exam.objects.create(
            scheduled_date=timezone.now(),
            open_duration_hours=1,
            competition_slot=stage_exam,
            is_active=True,
        )

        # Setup a ranking snapshot to allow promotion/elimination
        # Candidate 0 rank 1 (promote), Candidate 1 rank 2 (eliminate)
        snapshot = RankingSnapshot.objects.create(
            competition=self.competition,
            stage=Stage.Type.SCREENING,
            exam=exam,
            is_published=True,
            is_active=True,
        )
        RankingSnapshotEntry.objects.create(
            ranking_snapshot=snapshot,
            candidate=self.candidates[0],
            enrollment=Enrollment.objects.get(candidate=self.candidates[0]),
            rank=1,
            exam_score=100,
        )
        RankingSnapshotEntry.objects.create(
            ranking_snapshot=snapshot,
            candidate=self.candidates[1],
            enrollment=Enrollment.objects.get(candidate=self.candidates[1]),
            rank=2,
            exam_score=50,
        )

        # Perform promotion
        PromotionService.promote_candidates(
            from_stage_type=Stage.Type.SCREENING, to_stage_type=Stage.Type.LEAGUE
        )

        # Check Candidate 0 (Promoted)
        esp0 = EnrollmentStageProgress.objects.get(
            enrollment__candidate=self.candidates[0], stage=self.screening_stage
        )
        self.assertEqual(esp0.status, EnrollmentStageProgress.Status.COMPLETED)
        self.assertIsNotNone(esp0.completed_at)

        # Check Candidate 1 (Eliminated)
        esp1 = EnrollmentStageProgress.objects.get(
            enrollment__candidate=self.candidates[1], stage=self.screening_stage
        )
        self.assertEqual(esp1.status, EnrollmentStageProgress.Status.DISCONTINUED)
        self.assertIsNotNone(esp1.discontinued_at)

    def test_disqualify_candidate(self):
        candidate = self.candidates[0]
        PromotionService.disqualify_candidate(
            candidate_id=candidate.pk, reason="Cheating"
        )

        # Check Enrollment
        enrollment = Enrollment.objects.get(
            candidate=candidate, competition=self.competition
        )
        self.assertEqual(enrollment.status, Enrollment.Status.DISQUALIFIED)
        self.assertEqual(enrollment.metadata["disqualification_reason"], "Cheating")

        # Check Progress
        esp = EnrollmentStageProgress.objects.get(
            enrollment=enrollment, stage=self.screening_stage
        )
        self.assertEqual(esp.status, EnrollmentStageProgress.Status.DISCONTINUED)
        self.assertIsNotNone(esp.discontinued_at)

    def test_undisqualify_candidate(self):
        candidate = self.candidates[0]
        # First disqualify
        PromotionService.disqualify_candidate(
            candidate_id=candidate.pk, reason="Cheating"
        )

        # Then undisqualify
        PromotionService.undisqualify_candidate(candidate_id=candidate.pk)

        # Check Enrollment
        enrollment = Enrollment.objects.get(
            candidate=candidate, competition=self.competition
        )
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)
        self.assertNotIn("disqualification_reason", enrollment.metadata)

        # Check Progress
        esp = EnrollmentStageProgress.objects.get(
            enrollment=enrollment, stage=self.screening_stage
        )
        self.assertEqual(esp.status, EnrollmentStageProgress.Status.IN_PROGRESS)
        self.assertIsNone(esp.discontinued_at)
