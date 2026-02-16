import io
from PIL import Image
from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_api_key.models import APIKey

from identity.models import Candidate, Staff
from competition.models import Competition, Stage, Enrollment, StageExam, EnrollmentStageProgress
from vmlc.models import Exam, ExamAccess, ExamAccessPasscode
from vmlc.services.exam_access import ExamAccessService

User = get_user_model()

class ExamAccessTests(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)

        # Create Staff
        self.staff_user = User.objects.create_user(
            email="staff@example.com", password="password123"
        )
        self.staff = Staff.objects.create(user=self.staff_user)

        # Create Competition and Stage
        self.competition = Competition.objects.create(
            name="Test Competition",
            edition=1,
            status=Competition.Status.ACTIVE,
            start_date=timezone.now()
        )
        self.stage = Stage.objects.create(
            competition=self.competition,
            type=Stage.Type.SCREENING,
            order=1
        )

        # Create Candidate and Enrollment
        self.candidate_user = User.objects.create_user(
            email="candidate@example.com", password="password123",
            first_name="John", last_name="Doe"
        )
        self.candidate = Candidate.objects.create(user=self.candidate_user)
        self.enrollment = Enrollment.objects.create(
            candidate=self.candidate,
            competition=self.competition,
            current_stage=self.stage,
            status=Enrollment.Status.ACTIVE
        )

        EnrollmentStageProgress.objects.create(
            enrollment=self.enrollment,
            stage=self.stage,
            status=EnrollmentStageProgress.Status.IN_PROGRESS
        )

        self.slot = StageExam.objects.create(
            competition_stage=self.stage,
            is_active=True
        )

        # Create Exam
        self.exam = Exam.objects.create(
            description="Test Exam",
            scheduled_date=timezone.now() - timedelta(hours=1),
            open_duration_hours=2,
            countdown_minutes=60,
            created_by=self.staff,
            competition_slot=self.slot
        )

    @patch('vmlc.services.exam_access.settings.FRONTEND_BASE_URL', 'https://example.com')
    def test_generate_passcodes(self):
        count = ExamAccessService.generate_passcodes(self.exam.id)
        self.assertEqual(count, 1)

        access = ExamAccess.objects.get(exam=self.exam, candidate=self.candidate)
        passcode_record = ExamAccessPasscode.objects.get(exam_access=access)
        self.assertIsNotNone(passcode_record.passcode)
        self.assertIn("passcode=", passcode_record.access_url)
        self.assertEqual(passcode_record.status, ExamAccessPasscode.Status.ISSUED)

    def test_authenticate_passcode(self):
        # Setup passcode
        access = ExamAccess.objects.create(
            exam=self.exam, candidate=self.candidate,
            status=ExamAccess.Status.ISSUED
        )
        passcode_record = ExamAccessPasscode.objects.create(
            exam_access=access,
            passcode="test-passcode",
            expiry_date=timezone.now() + timedelta(hours=1),
            status=ExamAccessPasscode.Status.ISSUED
        )

        data, error = ExamAccessService.authenticate_passcode("test-passcode")
        self.assertIsNone(error)
        self.assertIn('access', data)
        self.assertIn('refresh', data)
        self.assertEqual(data['profile']['user']['email'], self.candidate_user.email)

        passcode_record.refresh_from_db()
        self.assertEqual(passcode_record.status, ExamAccessPasscode.Status.USED)

    def test_direct_access_login_view(self):
        # Setup passcode
        access = ExamAccess.objects.create(
            exam=self.exam, candidate=self.candidate,
            status=ExamAccess.Status.ISSUED
        )
        passcode_record = ExamAccessPasscode.objects.create(
            exam_access=access,
            passcode="test-passcode",
            expiry_date=timezone.now() + timedelta(hours=1),
            status=ExamAccessPasscode.Status.ISSUED
        )

        url = reverse("vmlc-v2:direct-access-login")
        response = self.client.post(url, {"passcode": "test-passcode"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_face_capture_and_take_exam(self):
        self.client.force_authenticate(user=self.candidate_user)

        # 1. Try to take exam without face capture -> should fail
        url_take = reverse("vmlc-v2:take-exam", kwargs={"exam_id": self.exam.id})
        response = self.client.get(url_take)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("face capture", response.data['detail'])

        # 2. Upload face capture
        url_face = reverse("vmlc-v2:exam-face-capture", kwargs={"exam_id": self.exam.id})

        # Create a dummy image
        file = io.BytesIO()
        image = Image.new('RGBA', size=(100, 100), color=(155, 0, 0))
        image.save(file, 'png')
        file.name = 'test.png'
        file.seek(0)

        response = self.client.post(url_face, {"face_capture": file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        access = ExamAccess.objects.get(exam=self.exam, candidate=self.candidate)
        self.assertTrue(access.face_capture)
        self.assertEqual(access.status, ExamAccess.Status.PENDING)

        # 3. Try to take exam again -> should succeed
        response = self.client.get(url_take)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        access.refresh_from_db()
        self.assertEqual(access.status, ExamAccess.Status.STARTED)

    @patch('vmlc.v2.tasks.generate_and_send_exam_passcodes_task.delay')
    def test_passcode_task_triggered_on_scheduled(self, mock_task):
        from vmlc.v2.serializers.exam import ExamDetailV2Serializer

        # Create a DRAFT exam
        exam = Exam.objects.create(
            description="Draft Exam",
            created_by=self.staff
        )

        # Update it to SCHEDULED
        with self.captureOnCommitCallbacks(using='default') as callbacks:
            serializer = ExamDetailV2Serializer(
                instance=exam,
                data={
                    "description": "Now Scheduled",
                    "scheduled_date": timezone.now() + timedelta(days=1),
                    "open_duration_hours": 1,
                    "countdown_minutes": 30
                },
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

        # Manually execute the callbacks (transaction.on_commit)
        for callback in callbacks:
            callback()

        self.assertTrue(mock_task.called)
