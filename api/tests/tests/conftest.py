import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import Candidate, Staff, Exam, Question

User = get_user_model()


@pytest.fixture
def api_client():
    """Returns a DRF APIClient instance."""
    return APIClient()


@pytest.fixture
def create_user():
    """Create a basic user."""

    def _create(username, email, password, **extra):
        return User.objects.create_user(
            username=username, email=email, password=password, **extra
        )

    return _create


@pytest.fixture
def create_logged_in_candidate(api_client):
    """Create and login a candidate with a specified role (default: screening)."""

    def _do(
        username="candidate",
        email="candidate@test.com",
        password="password123",
        role="screening",
    ):
        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        candidate = Candidate.objects.create(user=user, role=role)
        refresh = RefreshToken.for_user(user)
        api_client.force_authenticate(user=user)
        return candidate, str(refresh), str(refresh.access_token)

    return _do


@pytest.fixture
def create_logged_in_screening_candidate(api_client):
    """Create and login a screening candidate."""

    def _do(
        username="screening_candidate",
        email="screening_candidate@test.com",
        password="password123",
    ):
        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        candidate = Candidate.objects.create(user=user, role="screening")
        refresh = RefreshToken.for_user(user)
        api_client.force_authenticate(user=user)
        return candidate, str(refresh), str(refresh.access_token)

    return _do


@pytest.fixture
def create_logged_in_volunteer(api_client):
    """Create and login a volunteer user with a specified role."""

    def _do(
        username="volunteer",
        email="volunteer@test.com",
        password="password123",
        role="volunteer",
    ):
        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        staff = Staff.objects.create(user=user, role=role)
        refresh = RefreshToken.for_user(user)
        api_client.force_authenticate(user=user)
        return staff, str(refresh), str(refresh.access_token)

    return _do


@pytest.fixture
def create_logged_in_moderator(api_client):
    """Create and login a moderator user with a specified role."""

    def _do(
        username="moderator",
        email="moderator@test.com",
        password="password123",
        role="moderator",
    ):
        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        staff = Staff.objects.create(user=user, role=role)
        refresh = RefreshToken.for_user(user)
        api_client.force_authenticate(user=user)
        return staff, str(refresh), str(refresh.access_token)

    return _do


@pytest.fixture
def create_logged_in_admin(api_client):
    """Create and login an admin user with a specified role."""

    def _do(
        username="admin", email="admin@test.com", password="password123", role="admin"
    ):
        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        staff = Staff.objects.create(user=user, role=role)
        refresh = RefreshToken.for_user(user)
        api_client.force_authenticate(user=user)
        return staff, str(refresh), str(refresh.access_token)

    return _do


@pytest.fixture
def create_logged_in_owner(api_client):
    """Create and login an owner user with a specified role."""

    def _do(
        username="owner", email="owner@test.com", password="password123", role="owner"
    ):
        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        staff = Staff.objects.create(user=user, role=role)
        refresh = RefreshToken.for_user(user)
        api_client.force_authenticate(user=user)
        return staff, str(refresh), str(refresh.access_token)

    return _do


@pytest.fixture
def create_logged_in_league_candidate(api_client):
    """Create and login a league candidate."""

    def _do(
        username="league_candidate",
        email="league_candidate@test.com",
        password="password123",
    ):
        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        candidate = Candidate.objects.create(user=user, role="league")
        refresh = RefreshToken.for_user(user)
        api_client.force_authenticate(user=user)
        return candidate, str(refresh), str(refresh.access_token)

    return _do


@pytest.fixture
def create_logged_in_staff(api_client):
    """Create and login a staff user with a specified role."""

    def _do(
        username="staff",
        email="staff@test.com",
        password="password123",
        role="moderator",
    ):
        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        staff = Staff.objects.create(user=user, role=role)
        refresh = RefreshToken.for_user(user)
        api_client.force_authenticate(user=user)
        return staff, str(refresh), str(refresh.access_token)

    return _do


@pytest.fixture
def create_dummy_user():
    """Create a dummy user for testing purposes."""
    return User.objects.create_user(
        username="spongebob", email="spongebob@test.com", password="pineapple"
    )
