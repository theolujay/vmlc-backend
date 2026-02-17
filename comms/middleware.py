# vmlc/utils/middleware.py

import logging
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

User = get_user_model()
logger = logging.getLogger(__name__)


class DualAuthMiddleware:
    """
    Requires BOTH API key AND JWT token for WebSocket connections.

    - API Key: Via 'X-Api-Key' header OR 'api_key' query parameter.
    - JWT Token: Via 'Authorization: Bearer' header OR 'token' query parameter.

    Both must be valid for the connection to be accepted.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        await database_sync_to_async(close_old_connections)()

        scope["user"] = AnonymousUser()
        scope["api_key_authenticated"] = False
        scope["jwt_authenticated"] = False
        scope["fully_authenticated"] = False

        headers = dict(scope.get("headers", []))
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)

        # Step 1: Validate API Key (Application Authentication)
        # Try header first, then query param
        api_key = None
        api_key_header = headers.get(b"x-api-key", None)

        if api_key_header:
            api_key = api_key_header.decode("utf-8")
        else:
            api_key_list = query_params.get("api_key", [])
            if api_key_list:
                api_key = api_key_list[0]

        if not api_key:
            logger.warning(
                "Missing API Key (checked X-Api-Key header and 'api_key' query param)"
            )
            return await self.app(scope, receive, send)

        logger.info(f"Validating API key: {api_key[:8]}...")

        is_api_key_valid = await self.validate_api_key(api_key)

        if not is_api_key_valid:
            logger.warning(f"Invalid API key: {api_key[:8]}...")
            return await self.app(scope, receive, send)

        scope["api_key_authenticated"] = True
        logger.info("API key validated - client application authorized")

        # Step 2: Validate JWT Token (User Authentication)
        # Try header first, then query param
        token = None
        auth_header = headers.get(b"authorization", None)

        if auth_header:
            auth_str = auth_header.decode("utf-8")
            if auth_str.startswith("Bearer "):
                token = auth_str[7:]
            else:
                logger.warning(
                    "Invalid Authorization header format (expected 'Bearer <token>')"
                )

        if not token:
            token_list = query_params.get("token", [])
            if token_list:
                token = token_list[0]

        if not token:
            logger.warning(
                "Missing JWT Token (checked Authorization header and 'token' query param)"
            )
            return await self.app(scope, receive, send)

        logger.info("Validating JWT token")

        try:
            access_token = AccessToken(token)
            user_id = access_token["user_id"]
            user = await self.get_user(user_id)

            if user and not user.is_anonymous:
                scope["user"] = user
                scope["jwt_authenticated"] = True
                scope["fully_authenticated"] = True
                logger.info(f"JWT validated - user authenticated: {user.email}")
            else:
                logger.warning(f"User not found: {user_id}")
        except (TokenError, KeyError) as e:
            logger.warning(f"JWT validation failed: {e}")

        return await self.app(scope, receive, send)

    @database_sync_to_async
    def get_user(self, user_id):
        """Get user by ID for JWT authentication."""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()

    @database_sync_to_async
    def validate_api_key(self, key):
        """Validate API key using rest_framework_api_key."""
        from rest_framework_api_key.models import APIKey
        from django.conf import settings

        if settings.DEBUG:
            return True

        return APIKey.objects.is_valid(key)


def DualAuthMiddlewareStack(inner):
    """Wrap with dual authentication middleware (API Key + JWT required)."""
    return DualAuthMiddleware(inner)
