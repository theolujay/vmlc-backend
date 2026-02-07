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
        stage_exam1 = StageExam.objects.create(
            competition_stage=league,
            round=1,
            is_active=True
        )
        stage_exam2 = StageExam.objects.create(
            competition_stage=league,
            round=2,
            is_active=True
        )
        
        # Create vmlc.Exam linked to StageExam
        exam1 = Exam.objects.create(competition_slot=stage_exam1, is_active=True)
        exam2 = Exam.objects.create(competition_slot=stage_exam2, is_active=True)
        
        # Create inactive round/exam (StageExam inactive)
        stage_exam3 = StageExam.objects.create(
            competition_stage=league,
            round=3,
            is_active=False 
        )
        exam3 = Exam.objects.create(competition_slot=stage_exam3, is_active=True)
        
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
