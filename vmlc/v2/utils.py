from django.core.cache import cache

from django.db.models import Count, Q

from vmlc.models import Question


DEFAULT_TTL = 86400  # 24h


class CacheKeys:
    """Centralized cache key patterns."""
    CANDIDATE_DASHBOARD = "dash:cand:{candidate_id}"
    CANDIDATE_DASHBOARD_V2 = "candidate_dashboard_v2_{candidate_id}"
    STAFF_DASHBOARD = "dash:staff:global"
    PARTICIPATION = "part:{user_id}"
    LEADERBOARD_LEAGUE = "lb:league:latest"

    @classmethod
    def get_candidate_keys(cls, candidate_id, user_id=None):
        keys = [
            cls.CANDIDATE_DASHBOARD.format(candidate_id=candidate_id),
            cls.CANDIDATE_DASHBOARD_V2.format(candidate_id=candidate_id),
        ]
        if user_id:
            keys.append(cls.PARTICIPATION.format(user_id=user_id))
        return keys


def get_or_set_cache(key, fn, ttl=DEFAULT_TTL):
    data = cache.get(key)
    if data is not None:
        return data
    data = fn()
    cache.set(key, data, ttl)
    return data


def delete_many_cache(keys):
    for key in keys:
        cache.delete(key)


def invalidate_candidate_cache(candidate_id, user_id=None):
    """Clear all cache entries related to a specific candidate."""
    keys = CacheKeys.get_candidate_keys(candidate_id, user_id)
    delete_many_cache(keys)


def invalidate_staff_dashboard():
    """Clear global staff dashboard cache."""
    cache.delete(CacheKeys.STAFF_DASHBOARD)


def invalidate_league_leaderboard():
    """Clear league leaderboard cache."""
    cache.delete(CacheKeys.LEADERBOARD_LEAGUE)


def question_pool_aggregate(qs):
    return qs.aggregate(
        total_questions=Count("id"),
        hard_questions_count=Count("id", filter=Q(difficulty=Question.Difficulty.HARD)),
        moderate_questions_count=Count(
            "id", filter=Q(difficulty=Question.Difficulty.MODERATE)
        ),
        easy_questions_count=Count("id", filter=Q(difficulty=Question.Difficulty.EASY)),
    )
