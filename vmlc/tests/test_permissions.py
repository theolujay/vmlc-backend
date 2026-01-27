from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from identity.models import Staff
from vmlc.permissions import IsStaff

User = get_user_model()


class IsStaffPermissionTest(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="test@example.com", password="password"
        )
        self.staff_user = User.objects.create_user(
            email="staff@example.com", password="password"
        )
        Staff.objects.create(user=self.staff_user)

    def test_is_staff_permission(self):
        request = self.factory.get("/")
        request.user = self.staff_user
        permission = IsStaff()
        self.assertTrue(permission.has_permission(request, None))

    def test_is_not_staff_permission(self):
        request = self.factory.get("/")
        request.user = self.user
        permission = IsStaff()
        self.assertFalse(permission.has_permission(request, None))
