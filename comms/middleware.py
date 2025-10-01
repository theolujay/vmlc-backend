# vmlc/utils/middleware.py

import logging
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
    
    - API Key (X-Api-Key): Verifies the client application is authorized
    - JWT Token (Authorization: Bearer): Identifies the specific user
    
    Both must be valid for the connection to be accepted.
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        close_old_connections()
        
        scope['user'] = AnonymousUser()
        scope['api_key_authenticated'] = False
        scope['jwt_authenticated'] = False
        scope['fully_authenticated'] = False
        
        headers = dict(scope.get('headers', []))
        
        # Step 1: Validate API Key (Application Authentication)
        api_key_header = headers.get(b'x-api-key', None)
        
        if not api_key_header:
            logger.warning("Missing X-Api-Key header")
            return await self.app(scope, receive, send)
        
        api_key = api_key_header.decode('utf-8')
        logger.info(f"Validating API key: {api_key[:8]}...")
        
        is_api_key_valid = await self.validate_api_key(api_key)
        
        if not is_api_key_valid:
            logger.warning(f"Invalid API key: {api_key[:8]}...")
            return await self.app(scope, receive, send)
        
        scope['api_key_authenticated'] = True
        logger.info("API key validated - client application authorized")
        
        # Step 2: Validate JWT Token (User Authentication)
        auth_header = headers.get(b'authorization', None)
        
        if not auth_header:
            logger.warning("Missing Authorization header")
            return await self.app(scope, receive, send)
        
        auth_str = auth_header.decode('utf-8')
        
        if not auth_str.startswith('Bearer '):
            logger.warning("Invalid Authorization header format (expected 'Bearer <token>')")
            return await self.app(scope, receive, send)
        
        token = auth_str[7:]
        logger.info(f"Validating JWT token")
        
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = await self.get_user(user_id)
            
            if user and not user.is_anonymous:
                scope['user'] = user
                scope['jwt_authenticated'] = True
                scope['fully_authenticated'] = True
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
        return APIKey.objects.is_valid(key)


def DualAuthMiddlewareStack(inner):
    """Wrap with dual authentication middleware (API Key + JWT required)."""
    return DualAuthMiddleware(inner)