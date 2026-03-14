# import uuid
# from django.test import TestCase
# from django.utils import timezone
# from vmlc.models import Exam, ExamAccess, ExamHeartbeat
# from identity.models import Candidate, User
# from vmlc.services.proctoring import ProctoringService
# from competition.services.ranking import RankingSnapshotGenerator
# from competition.models import Competition, CompetitionStage, StageExam, Enrollment, RankingSnapshotEntry

# class ProctoringServiceTest(TestCase):
#     def setUp(self):
#         self.user = User.objects.create(username="testuser", email="test@example.com")
#         self.candidate = Candidate.objects.create(user=self.user)
#         self.exam = Exam.objects.create(
#             title="Test Exam",
#             status=Exam.Status.CONCLUDED,
#             scheduled_date=timezone.now() - timezone.timedelta(hours=2),
#             open_duration_hours=1
#         )
#         self.access = ExamAccess.objects.create(
#             exam=self.exam,
#             candidate=self.candidate,
#             status=ExamAccess.Status.ISSUED
#         )

#         # Setup for ranking test
#         self.competition = Competition.objects.create(title="Test Competition")
#         self.stage = CompetitionStage.objects.create(
#             competition=self.competition,
#             type=CompetitionStage.StageType.QUALIFICATION,
#             round=1
#         )
#         self.stage_exam = StageExam.objects.create(
#             competition_stage=self.stage,
#             exam=self.exam,
#             round=1
#         )
#         self.enrollment = Enrollment.objects.create(
#             candidate=self.candidate,
#             competition=self.competition,
#             status=Enrollment.Status.ACTIVE
#         )

#     def test_absent_candidate_has_null_proctoring_status(self):
#         """
#         Verify that a candidate with no heartbeats has a null auto_status and proctoring_status.
#         """
#         summary = ProctoringService.get_proctoring_summary(self.access)
#         self.assertIsNone(summary["auto_status"])
#         self.assertIsNone(self.access.proctoring_status)

#     def test_ranking_generator_copies_proctoring_status_for_absent(self):
#         """
#         Verify that RankingSnapshotGenerator sets proctoring_status to null for absentees.
#         """
#         generator = RankingSnapshotGenerator(self.stage_exam.id)
#         snapshot = generator.generate_and_save_ranking()

#         entry = RankingSnapshotEntry.objects.get(ranking_snapshot=snapshot, candidate=self.candidate)
#         self.assertIsNone(entry.proctoring_status)
#         self.assertEqual(entry.violation_score, 0.0)

#     def test_proctoring_status_updates_after_heartbeat(self):
#         """
#         Verify that proctoring_status is updated from null to 'clear' after a heartbeat is processed.
#         """
#         # Create a heartbeat
#         heartbeat = ExamHeartbeat.objects.create(
#             exam_access=self.access,
#             sequence_number=1,
#             client_uuid=str(uuid.uuid4()),
#             period_start=timezone.now(),
#             period_end=timezone.now() + timezone.timedelta(seconds=30),
#             summary={},
#             suspicion_score=0.1
#         )

#         # Process events and score (this updates access.proctoring_status)
#         ProctoringService.process_events_and_score(heartbeat.id, [])

#         self.access.refresh_from_db()
#         self.assertEqual(self.access.proctoring_status, "clear")

#         # Also check ranking entry if it exists
#         generator = RankingSnapshotGenerator(self.stage_exam.id)
#         snapshot = generator.generate_and_save_ranking()

#         # Another heartbeat with higher suspicion
#         heartbeat2 = ExamHeartbeat.objects.create(
#             exam_access=self.access,
#             sequence_number=2,
#             client_uuid=str(uuid.uuid4()),
#             period_start=timezone.now(),
#             period_end=timezone.now() + timezone.timedelta(seconds=30),
#             summary={"TAB_SWITCH": 10}, # This should trigger higher suspicion
#             suspicion_score=0.8
#         )

#         ProctoringService.process_events_and_score(heartbeat2.id, [])

#         self.access.refresh_from_db()
#         self.assertEqual(self.access.proctoring_status, "flagged")

#         entry = RankingSnapshotEntry.objects.get(ranking_snapshot=snapshot, candidate=self.candidate)
#         self.assertEqual(entry.proctoring_status, "flagged")
#         # Avg of 0.1 and 0.8 is 0.45
#         self.assertAlmostEqual(entry.violation_score, 0.45)
