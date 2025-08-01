"""
Authentication-related API views for login, logout, and registration.
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import SimpleRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from ..serializers import UserSerializer

logger = logging.getLogger(__name__)


class LoginRateThrottle(SimpleRateThrottle):
    """Throttle for login attempts to prevent brute force attacks."""

    scope = "login"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {"scope": self.scope, "ident": request.user.pk}
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from ..serializers import UserSerializer

logger = logging.getLogger(__name__)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customizes the JWT token response to include user details.
    """

    def validate(self, attrs):
        # The default result (access/refres tokens)
        data = super().validate(attrs)

        # Add user information to the response
        user_serializer = UserSerializer(self.user)
        data["user"] = user_serializer.data

        return data


class LoginView(TokenObtainPairView):
    """
    Custom login view to handle user authentication and token generation.
    Uses the custom serializer to include user data in the response.
    """

    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        username = request.data.get("username", "N/A")
        if response.status_code == status.HTTP_200_OK:
            logger.info("User %s logged in successfully", username)
        else:
            logger.warning("Failed login attempt for username: %s", username)
        return response


class LogoutView(APIView):
    """
    Handles user logout by blacklisting the provided refresh token.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Expects a 'refresh' token in the request body.
        """
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info("User %s logged out successfully", request.user.username)
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_204_NO_CONTENT,
            )
        except TokenError as e:
            logger.warning("Logout failed for user, %s: %s", request.user.username, e)
