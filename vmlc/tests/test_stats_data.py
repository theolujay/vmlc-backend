from django.test import TestCase
from competition.models import Competition, Stage, StageExam
from vmlc.models import Exam
from vmlc.utils.stats import generate_stats_overview_data

class StatsOverviewDataTest(TestCase):
    def test_competition_stats(self):
        # Create active competition
        comp = Competition.objects.create(
            name="Test Comp",
            edition=1,
            status=Competition.Status.ACTIVE
        )
        
        # Create stages
        screening = Stage.objects.create(
            competition=comp,
            type=Stage.Type.SCREENING,
            order=1
        )
        league = Stage.objects.create(
            competition=comp,
            type=Stage.Type.LEAGUE,
            order=2
        )
        
        # Create rounds for league via StageExam
        # Need vmlc.Exam first
        exam1 = Exam.objects.create(title="Round 1 Exam", is_active=True)
        exam2 = Exam.objects.create(title="Round 2 Exam", is_active=True)
        
        StageExam.objects.create(
            competition_stage=league,
            vmlc_exam=exam1,
            round=1,
            is_active=True
        )
        StageExam.objects.create(
            competition_stage=league,
            vmlc_exam=exam2,
            round=2,
            is_active=True
        )
        
        # Create inactive round/exam (StageExam inactive)
        exam3 = Exam.objects.create(title="Round 3 Inactive", is_active=True)
        StageExam.objects.create(
            competition_stage=league,
            vmlc_exam=exam3,
            round=3,
            is_active=False 
        )
        
        # Call the function
        data = generate_stats_overview_data()
        
        # Assertions
        self.assertIn("competition", data)
        comp_stats = data["competition"]
        self.assertIsNotNone(comp_stats)
        self.assertEqual(comp_stats["active_competition_id"], comp.id)
        self.assertEqual(comp_stats["active_competition"], str(comp))
        
        stages = comp_stats["stages"]
        self.assertEqual(len(stages), 2)
        
        screening_data = next(s for s in stages if s["type"] == Stage.Type.SCREENING)
        self.assertEqual(screening_data["id"], screening.id)
        
        league_data = next(s for s in stages if s["type"] == Stage.Type.LEAGUE)
        self.assertEqual(league_data["id"], league.id)
        self.assertIn("rounds", league_data)
        self.assertEqual(league_data["rounds"], [1, 2]) # Round 3 is inactive

    def test_no_active_competition(self):
        # No active competition
        Competition.objects.create(
            name="Past Comp",
            edition=0,
            status=Competition.Status.CONCLUDED
        )
        
        data = generate_stats_overview_data()
        self.assertIsNone(data["competition"])
