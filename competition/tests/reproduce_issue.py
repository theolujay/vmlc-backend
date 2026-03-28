from django.test import TestCase
from django.utils import timezone
from competition.models import Competition, Stage, StageExam, RankingSnapshot
from vmlc.models import Exam

class RankingSnapshotReproductionTest(TestCase):
    def setUp(self):
        self.competition = Competition.objects.create(
            name="Test Comp", edition=1, status=Competition.Status.ACTIVE
        )
        self.stage = Stage.objects.create(
            competition=self.competition, type=Stage.Type.SCREENING, order=1
        )
        self.stage_exam = StageExam.objects.create(
            competition_stage=self.stage, round=1, is_active=True
        )
        self.exam = Exam.objects.create(
            scheduled_date=timezone.now() - timezone.timedelta(days=1),
            open_duration_hours=12,
            competition_slot=self.stage_exam,
            is_active=True,
        )

    def test_save_active_ranking_multiple_times(self):
        """
        Tests if saving an active ranking snapshot multiple times causes an error.
        In Django, select_for_update() + update() in the same queryset is generally disallowed.
        """
        ranking1 = RankingSnapshot.objects.create(
            competition=self.competition,
            stage=self.stage.type,
            round=1,
            exam=self.exam,
            is_active=True,
        )
        
        # This should trigger the save() method and its problematic logic
        ranking2 = RankingSnapshot(
            competition=self.competition,
            stage=self.stage.type,
            round=1,
            exam=self.exam,
            is_active=True,
        )
        # We expect this might raise an error due to the select_for_update().update() chain
        try:
            ranking2.save()
        except Exception as e:
            print(f"Caught expected exception: {type(e).__name__}: {e}")
            raise e

        ranking1.refresh_from_db()
        self.assertFalse(ranking1.is_active)
        self.assertTrue(ranking2.is_active)
