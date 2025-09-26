# auth/middleware.py (create this file)
import logging
from urllib.parse import parse_qs
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

User = get_user_model()
logger = logging.getLogger(__name__)


class JWTAuthMiddleware:
    """Middleware to authenticate user for channels using JWT from query parameters"""
    
    def __init__(self, app):
        """Initializing the app.""" 
        self.app = app

    async def __call__(self, scope, receive, send):
        """Authenticate the user based on jwt."""
        close_old_connections()
        
        try:
            # Get token from query parameters
            query_params = parse_qs(scope["query_string"].decode("utf8"))
            token = query_params.get('token', [None])[0]
            
            if token:
                logger.info(f"Token found")
                # Decode the token to get the user data
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                logger.info(f"User ID from token: {user_id}")
                # Get the user from database and add it to scope
                scope['user'] = await self.get_user(user_id)
                logger.info(f"User {scope['user']} added to scope.")
            else:
                scope['user'] = AnonymousUser()
                logger.info("No token found, user set to AnonymousUser.")
                
        except (TokenError, KeyError) as e:
            # Set user to Anonymous if token is invalid or expired
            logger.error(f"Token error: {e}")
            scope['user'] = AnonymousUser()
        
        return await self.app(scope, receive, send)

    @database_sync_to_async
    def get_user(self, user_id):
        """Return the user based on user id."""
        try:
            user = User.objects.get(id=user_id)
            logger.info(f"User {user} retrieved from database.")
            return user
        except User.DoesNotExist:
            logger.warning(f"User with ID {user_id} not found.")
            return AnonymousUser()


def JWTAuthMiddlewareStack(inner):
    """Wrap channels authentication stack with JWTAuthMiddleware."""
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))