import logging
import time
from django.core.cache import cache
from channels.db import database_sync_to_async
from ..models import HelpdeskThread

logger = logging.getLogger(__name__)


class WSHelpdeskThreadService:
    @staticmethod
    @database_sync_to_async
    def check_access(user, thread_id, is_staff):
        """Checks if the user has access to a specific helpdesk thread."""
        try:
            thread = HelpdeskThread.objects.get(id=thread_id)
            if is_staff:
                return True
            return (
                hasattr(user, "candidate_profile")
                and thread.candidate_id == user.candidate_profile.pk
            )
        except (HelpdeskThread.DoesNotExist, ValueError):
            return False

    @staticmethod
    @database_sync_to_async
    def get_user_type_set_name(user):
        """Returns the Redis set name based on user type (Candidate or Staff)."""
        # We use prefixed names to avoid collisions with other apps/environments
        base_name = (
            "online_candidates"
            if hasattr(user, "candidate_profile")
            else "online_staff"
        )
        return cache.make_key(base_name)

    @staticmethod
    async def set_presence(user_id, set_name, is_online):
        """Updates the user's presence using a Sorted Set (heartbeat pattern)."""
        key = f"user_online_{user_id}"

        try:
            client = cache.client.get_client()
            if is_online:
                # 1. Standard key for per-user check (uses cache prefix)
                cache.set(key, 1, timeout=60)
                # 2. Add to global ZSET (set_name is already prefixed)
                client.zadd(set_name, {str(user_id): time.time()})
                client.expire(set_name, 86400)
            else:
                cache.delete(key)
                client.zrem(set_name, str(user_id))
        except Exception as e:
            logger.warning(f"Failed to update presence for {user_id}: {e}")

    @staticmethod
    async def refresh_presence(user_id, set_name):
        """Refreshes the user's heartbeat in the Sorted Set."""
        cache.set(f"user_online_{user_id}", 1, timeout=60)
        try:
            client = cache.client.get_client()
            client.zadd(set_name, {str(user_id): time.time()})
        except:
            pass

    @staticmethod
    def get_online_counts():
        """Prunes stale members and returns active counts from ZSETs."""
        try:
            client = cache.client.get_client()
            now = time.time()
            # Align cutoff (60s) with the individual key TTL (60s)
            cutoff = now - 60

            c_set = cache.make_key("online_candidates")
            s_set = cache.make_key("online_staff")

            # Prune before counting
            client.zremrangebyscore(c_set, 0, cutoff)
            client.zremrangebyscore(s_set, 0, cutoff)

            return {
                "online_candidates": client.zcard(c_set),
                "online_staff": client.zcard(s_set),
            }
        except Exception as e:
            logger.warning(f"Failed to get online counts: {e}")
            return {"online_candidates": 0, "online_staff": 0}
