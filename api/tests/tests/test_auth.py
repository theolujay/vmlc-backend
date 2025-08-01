import pytest

from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def authenticated_api_client(api_client, settings):
    """API client with authentication credentials set"""
    test_api_key = "0pOS6SCd.XlirVyZ2Fq8wimnFjXG9SrWKo4o9Y67i"
    api_client.credentials(HTTP_AUTHORIZATION=f"Api-Key {test_api_key}")
    return api_client


@pytest.fixture
def login_url():
    return reverse("v1:api-login")


@pytest.fixture
def logout_url():
    return reverse("v1:api-logout")


@pytest.fixture
def create_logged_in_user(authenticated_api_client):
    def do_create(username="patrick", password="password123"):
        user = User.objects.create_user(username=username, password=password)
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        authenticated_api_client.force_authenticate(user=user)
        return user, str(refresh), str(refresh.access_token)

    return do_create


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, authenticated_api_client, login_url):
        User.objects.create_user(username="patrick", password="safepassword123")
        data = {"username": "patrick", "password": "safepassword123"}
        response = authenticated_api_client.post(login_url, data, format="json")
        assert response.status_code == 200
        assert "tokens" in response.data
        assert response.data["user"]["username"] == "patrick"

    def test_login_wrong_password(self, authenticated_api_client, login_url):
        User.objects.create_user(username="patrick", password="safepassword123")
        data = {"username": "patrick", "password": "wrongpass"}
        response = authenticated_api_client.post(login_url, data, format="json")
        assert response.status_code == 401
        assert "error" in response.data

    def test_login_missing_fields(self, authenticated_api_client, login_url):
        response = authenticated_api_client.post(login_url, {}, format="json")
        assert response.status_code == 400

    def test_login_inactive_user(self, authenticated_api_client, login_url):
        User.objects.create_user(
            username="patrick",
            email="patrick@test.com",
            password="safepassword123",
            is_active=False,
        )
        data = {"username": "patrick", "password": "safepassword123"}
        response = authenticated_api_client.post(login_url, data, format="json")
        assert response.status_code == 401
        assert "Invalid credentials" in response.data["error"]

    def test_login_short_username(self, authenticated_api_client, login_url):
        data = {"username": "pa", "password": "somepassword"}
        response = authenticated_api_client.post(login_url, data, format="json")
        assert response.status_code == 400
        assert "at least 3 characters" in response.data["error"]

    def test_login_wrong_method(self, authenticated_api_client, login_url):
        response = authenticated_api_client.get(login_url)
        assert response.status_code == 405


@pytest.mark.django_db
class TestLogout:
    def test_logout_success(
        self, authenticated_api_client, logout_url, create_logged_in_user
    ):
        user, refresh, access = create_logged_in_user()
        authenticated_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = authenticated_api_client.post(
            logout_url, {"refresh_token": refresh}, format="json"
        )
        assert response.status_code == 200
        assert "Logout successful" in response.data["message"]

    def test_logout_missing_token(
        self, authenticated_api_client, logout_url, create_logged_in_user
    ):
        _, _, access = create_logged_in_user()
        authenticated_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = authenticated_api_client.post(logout_url, {}, format="json")
        assert response.status_code == 400
        assert "Refresh token is required" in response.data["error"]

    def test_logout_invalid_token(
        self, authenticated_api_client, logout_url, create_logged_in_user
    ):
        _, _, access = create_logged_in_user()
        authenticated_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = authenticated_api_client.post(
            logout_url, {"refresh_token": "invalidtoken"}, format="json"
        )
        assert response.status_code == 400
        assert "Invalid" in response.data["error"]

    def test_logout_auth_required(self, authenticated_api_client, logout_url):
        response = authenticated_api_client.post(
            logout_url, {"refresh_token": "sometoken"}, format="json"
        )
        assert response.status_code == 401
