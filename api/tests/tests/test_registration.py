import pytest
import copy

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
def valid_candidate_data():
    """Factory function for candidate data to avoid mutation issues"""

    def _data(**overrides):
        data = {
            "user": {
                "username": "patrick",
                "first_name": "Patrick",
                "last_name": "Star",
                "email": "patrickstar@gmail.com",
            },
            "password1": "bikinibottom",
            "password2": "bikinibottom",
            "phone": "08033353762",
            "school": "Bikini Bottom College",
        }
        if overrides:
            # Deep merge overrides
            result = copy.deepcopy(data)
            for key, value in overrides.items():
                if key == "user" and isinstance(value, dict):
                    result["user"].update(value)
                else:
                    result[key] = value
            return result
        return copy.deepcopy(data)

    return _data


@pytest.fixture
def valid_staff_data():
    """Factory function for staff data to avoid mutation issues"""

    def _data(**overrides):
        data = {
            "user": {
                "username": "patrick",
                "first_name": "Patrick",
                "last_name": "Star",
                "email": "patrickstar@gmail.com",
            },
            "password1": "bikinibottom",
            "password2": "bikinibottom",
            "phone": "08033353762",
            "occupation": "SpongeBob's bestfriend",
        }
        if overrides:
            # Deep merge overrides
            result = copy.deepcopy(data)
            for key, value in overrides.items():
                if key == "user" and isinstance(value, dict):
                    result["user"].update(value)
                else:
                    result[key] = value
            return result
        return copy.deepcopy(data)

    return _data


@pytest.fixture
def candidate_registration_url():
    return reverse("v1:api-register-candidate")


@pytest.fixture
def staff_registration_url():
    return reverse("v1:api-register-staff")


@pytest.mark.django_db
class TestCandidateRegistration:
    def test_success(
        self, authenticated_api_client, candidate_registration_url, valid_candidate_data
    ):
        response = authenticated_api_client.post(
            candidate_registration_url, valid_candidate_data(), format="json"
        )
        assert response.status_code == 201
        assert "Registration successful" in response.data["message"]
        assert User.objects.filter(username="patrick").exists()

    def test_no_api_credentials(
        self, api_client, candidate_registration_url, valid_candidate_data
    ):
        response = api_client.post(
            candidate_registration_url, valid_candidate_data(), format="json"
        )
        assert response.status_code == 401
        assert "Authentication credentials were not provided." in response.data["error"]

    def test_invalid_api_key(
        self, api_client, candidate_registration_url, valid_candidate_data
    ):
        api_client.credentials(HTTP_AUTHORIZATION="Api-Key invalid-key")
        response = api_client.post(
            candidate_registration_url, valid_candidate_data(), format="json"
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.data["error"]

    def test_registration_invalid(
        self, authenticated_api_client, candidate_registration_url
    ):
        data = {}
        response = authenticated_api_client.post(
            candidate_registration_url, data, format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_duplicate_username(
        self, authenticated_api_client, candidate_registration_url, valid_candidate_data
    ):
        User.objects.create_user(username="patrick", email="existing@test.com")
        response = authenticated_api_client.post(
            candidate_registration_url, valid_candidate_data(), format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_duplicate_email(
        self, authenticated_api_client, candidate_registration_url, valid_candidate_data
    ):
        User.objects.create_user(username="existing", email="patrickstar@gmail.com")
        response = authenticated_api_client.post(
            candidate_registration_url, valid_candidate_data(), format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_invalid_email(
        self, authenticated_api_client, candidate_registration_url, valid_candidate_data
    ):
        data = valid_candidate_data(user={"email": "not-an-email"})
        response = authenticated_api_client.post(
            candidate_registration_url, data, format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_weak_password(
        self, authenticated_api_client, candidate_registration_url, valid_candidate_data
    ):
        data = valid_candidate_data(
            password1="123", user={"email": "patrickstar2@gmail.com"}
        )
        response = authenticated_api_client.post(
            candidate_registration_url, data, format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_long_username(
        self, authenticated_api_client, candidate_registration_url, valid_candidate_data
    ):
        data = valid_candidate_data(
            user={"username": "a" * 15, "email": "patrickstar3@gmail.com"}
        )
        response = authenticated_api_client.post(
            candidate_registration_url, data, format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_missing_user_fields(
        self, authenticated_api_client, candidate_registration_url
    ):
        data = {
            "user": {"username": "patrick"},
            "password1": "bikinibottom",
        }
        response = authenticated_api_client.post(
            candidate_registration_url, data, format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_wrong_method(self, api_client, candidate_registration_url):
        response = api_client.get(candidate_registration_url)
        assert response.status_code == 405

    def test_authenticated_user(
        self, authenticated_api_client, candidate_registration_url
    ):
        user = User.objects.create_user(username="existing", email="test@test.com")
        authenticated_api_client.force_authenticate(user=user)
        data = {
            "user": {
                "username": "newuser",
                "first_name": "New",
                "last_name": "User",
                "email": "newuser@test.com",
            },
            "password1": "bikinibottom",
            "password2": "bikinibottom",
            "phone": "08033353762",
            "school": "Test School",
        }
        response = authenticated_api_client.post(
            candidate_registration_url, data, format="json"
        )
        assert response.status_code == 400

    def test_missing_password(
        self, authenticated_api_client, candidate_registration_url, valid_candidate_data
    ):
        data = valid_candidate_data()
        del data["password1"]
        response = authenticated_api_client.post(
            candidate_registration_url, data, format="json"
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestStaffRegistration:
    def test_success(
        self, authenticated_api_client, staff_registration_url, valid_staff_data
    ):
        response = authenticated_api_client.post(
            staff_registration_url, valid_staff_data(), format="json"
        )
        assert response.status_code == 201
        assert "Registration successful" in response.data["message"]
        assert User.objects.filter(username="patrick").exists()

    def test_invalid(self, authenticated_api_client, staff_registration_url):
        response = authenticated_api_client.post(
            staff_registration_url, {}, format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_no_api_credentials(
        self, api_client, staff_registration_url, valid_staff_data
    ):
        response = api_client.post(
            staff_registration_url, valid_staff_data(), format="json"
        )
        assert response.status_code == 401
        assert "Authentication credentials were not provided." in response.data["error"]

    def test_duplicate_username(
        self, authenticated_api_client, staff_registration_url, valid_staff_data
    ):
        User.objects.create_user(username="patrick", email="existing@test.com")
        response = authenticated_api_client.post(
            staff_registration_url, valid_staff_data(), format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_duplicate_email(
        self, authenticated_api_client, staff_registration_url, valid_staff_data
    ):
        User.objects.create_user(username="existing", email="patrickstar@gmail.com")
        response = authenticated_api_client.post(
            staff_registration_url, valid_staff_data(), format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_invalid_email(
        self, authenticated_api_client, staff_registration_url, valid_staff_data
    ):
        data = valid_staff_data(user={"email": "not-an-email"})
        response = authenticated_api_client.post(
            staff_registration_url, data, format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_weak_password(
        self, authenticated_api_client, staff_registration_url, valid_staff_data
    ):
        data = valid_staff_data(
            password1="123", user={"email": "patrickstar2@gmail.com"}
        )
        response = authenticated_api_client.post(
            staff_registration_url, data, format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_long_username(
        self, authenticated_api_client, staff_registration_url, valid_staff_data
    ):
        data = valid_staff_data(
            user={"username": "a" * 15, "email": "patrickstar3@gmail.com"}
        )
        response = authenticated_api_client.post(
            staff_registration_url, data, format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_missing_user_fields(
        self, authenticated_api_client, staff_registration_url
    ):
        data = {
            "user": {
                "username": "patrick",
            },
            "password1": "bikinibottom",
        }
        response = authenticated_api_client.post(
            staff_registration_url, data, format="json"
        )
        assert response.status_code == 400
        assert "Registration failed" in response.data["error"]

    def test_wrong_method(self, api_client, staff_registration_url):
        response = api_client.get(staff_registration_url)
        assert response.status_code == 405

    def test_authenticated_user(self, authenticated_api_client, staff_registration_url):
        user = User.objects.create_user(username="existing", email="test@test.com")
        authenticated_api_client.force_authenticate(user=user)
        data = {
            "user": {
                "username": "newuser",
                "first_name": "New",
                "last_name": "User",
                "email": "newuser@test.com",
            },
            "password1": "bikinibottom",
            "password2": "bikinibottom",
            "phone": "08033353762",
            "occupation": "Test Occupation",
        }
        response = authenticated_api_client.post(
            staff_registration_url, data, format="json"
        )
        assert response.status_code == 400

    def test_missing_password(
        self, authenticated_api_client, staff_registration_url, valid_staff_data
    ):
        data = valid_staff_data()
        del data["password1"]
        response = authenticated_api_client.post(
            staff_registration_url, data, format="json"
        )
        assert response.status_code == 400
