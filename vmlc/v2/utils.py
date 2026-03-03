import math
from django.core.cache import cache

from django.db.models import Count, Q

from vmlc.models import Question


DEFAULT_TTL = 86400  # 24h


class CacheKeys:
    """Centralized cache key patterns."""

    # Dashboards
    CANDIDATE_DASHBOARD = "dash:cand:{candidate_id}"
    CANDIDATE_DASHBOARD_V2 = "dash:cand:v2:{candidate_id}"
    STAFF_DASHBOARD = "dash:staff:global"

    # Competition
    ENROLLMENT = "enrollment:{user_id}"
    LEADERBOARD_LEAGUE = "lb:league:latest"
    RANKING_SNAPSHOT = "ranking:snapshot:{exam_id}"
    RANKING_SNAPSHOT_ENTRY = "ranking:snapshot:entry:{exam_id}:{candidate_id}"
    RANKING_SNAPSHOT_LIST = "ranking:snapshot:list"

    # Exams
    EXAM_DETAIL = "exam:detail:{exam_id}"
    EXAM_TAKE_V2 = "exam:take:v2:{exam_id}"
    EXAM_QUESTIONS = "exam:questions:{exam_id}"
    EXAM_RESULTS = "exam:results:{exam_id}"
    CANDIDATE_EXAM_HISTORY = "cand:history:{candidate_id}"

    # Questions
    QUESTION_POOL = "pool:questions"

    # Identity & Account
    USER_ACCOUNT_MANAGEMENT = "user:account:{user_id}"
    USER_VERIFICATION = "user:verification:{user_id}"
    CANDIDATE_PROFILE = "cand:profile:{user_id}"
    CANDIDATE_DETAIL = "cand:detail:{user_id}"
    CANDIDATE_DETAIL_BY_PK = "cand:detail:pk:{candidate_id}"
    STAFF_PROFILE = "staff:profile:{user_id}"
    STAFF_DETAIL_BY_PK = "staff:detail:pk:{staff_id}"
    STAFF_DASHBOARD_DATA = "staff:dashboard:{user_id}"

    # Metrics & Status
    REGISTRATION_METRICS = "metrics:registration"
    REGISTRATION_STATUS = "status:registration"
    STATS_OVERVIEW = "status:stats:overview"
    STATS_CANDIDATES = "status:stats:candidates"
    STATS_STAFF = "status:stats:staff"
    STATS_EXAMS = "status:stats:exams"
    STATS_COMPETITION = "status:stats:competition"
    STATS_HELPDESK = "status:stats:helpdesk"
    STATS_FUNNEL = "status:stats:funnel"
    STATS_GEOGRAPHICS = "status:stats:geographics"

    # Feature Flags
    FEATURE_FLAG = "feature:flag:{key}"

    # Broadcasts
    BROADCAST_DETAIL = "broadcast_detail_{broadcast_id}"
    BROADCAST_SUMMARY = "broadcast_summary_data"

    # Notifications
    NOTIFICATIONS_VERSION = "notifications_version_{user_id}"
    NOTIFICATIONS_LIST = "notifications_{user_id}_{version}_{query_hash}"
    NOTIFICATION_STATS = "notification_stats_{user_id}_{version}"

    # Helpdesk
    HELPDESK_THREAD_DETAIL = "helpdesk:thread:detail:{thread_id}"
    HELPDESK_THREADS_VERSION_STAFF = "helpdesk_threads_version_staff"
    HELPDESK_THREAD_LIST_STAFF = (
        "helpdesk:threads:staff:{user_id}_{version}_{query_hash}"
    )

    # Legacy keys (for invalidation during transition)
    _LEGACY_CANDIDATE_DASHBOARD = "candidate_dashboard_{candidate_id}"
    _LEGACY_CANDIDATE_DASHBOARD_V2 = "candidate_dashboard_v2_{candidate_id}"
    _LEGACY_ACCOUNT_MANAGEMENT = "account_management_{user_id}"
    _LEGACY_USER_VERIFICATION = "user_verification_status_{user_id}"
    _LEGACY_CANDIDATE_PROFILE = "candidate_profile_{user_id}"
    _LEGACY_CANDIDATE_DETAIL = "candidate_detail_{user_id}"
    _LEGACY_STAFF_PROFILE = "staff_profile_{user_id}"
    _LEGACY_STAFF_DASHBOARD = "staff_dashboard_data_{user_id}"
    _LEGACY_EXAM_HISTORY = "exam_history_{user_id}"
    _LEGACY_QUESTION_POOL = "question_pool_data"
    _LEGACY_REGISTRATION_STATUS = "registration_status"
    _LEGACY_FEATURE_FLAG = "feature_flag_{key}"

    @classmethod
    def get_candidate_keys(cls, candidate_id, user_id=None):
        keys = [
            cls.CANDIDATE_DASHBOARD.format(candidate_id=candidate_id),
            cls.CANDIDATE_DASHBOARD_V2.format(candidate_id=candidate_id),
            cls.CANDIDATE_EXAM_HISTORY.format(candidate_id=candidate_id),
            # Include legacy keys to ensure they are cleared
            cls._LEGACY_CANDIDATE_DASHBOARD.format(candidate_id=candidate_id),
            cls._LEGACY_CANDIDATE_DASHBOARD_V2.format(candidate_id=candidate_id),
        ]
        if user_id:
            keys.extend(
                [
                    cls.ENROLLMENT.format(user_id=user_id),
                    cls.USER_ACCOUNT_MANAGEMENT.format(user_id=user_id),
                    cls.USER_VERIFICATION.format(user_id=user_id),
                    cls.CANDIDATE_PROFILE.format(user_id=user_id),
                    cls.CANDIDATE_DETAIL.format(user_id=user_id),
                    cls._LEGACY_ACCOUNT_MANAGEMENT.format(user_id=user_id),
                    cls._LEGACY_USER_VERIFICATION.format(user_id=user_id),
                    cls._LEGACY_CANDIDATE_PROFILE.format(user_id=user_id),
                    cls._LEGACY_CANDIDATE_DETAIL.format(user_id=user_id),
                    cls._LEGACY_EXAM_HISTORY.format(user_id=user_id),
                ]
            )
        return keys

    @classmethod
    def get_user_keys(cls, user_id):
        return [
            cls.USER_ACCOUNT_MANAGEMENT.format(user_id=user_id),
            cls.USER_VERIFICATION.format(user_id=user_id),
            cls.CANDIDATE_PROFILE.format(user_id=user_id),
            cls.CANDIDATE_DETAIL.format(user_id=user_id),
            cls.STAFF_PROFILE.format(user_id=user_id),
            cls.STAFF_DASHBOARD_DATA.format(user_id=user_id),
            cls.ENROLLMENT.format(user_id=user_id),
            # Legacy
            cls._LEGACY_ACCOUNT_MANAGEMENT.format(user_id=user_id),
            cls._LEGACY_USER_VERIFICATION.format(user_id=user_id),
            cls._LEGACY_CANDIDATE_PROFILE.format(user_id=user_id),
            cls._LEGACY_CANDIDATE_DETAIL.format(user_id=user_id),
            cls._LEGACY_STAFF_PROFILE.format(user_id=user_id),
            cls._LEGACY_STAFF_DASHBOARD.format(user_id=user_id),
            cls._LEGACY_EXAM_HISTORY.format(user_id=user_id),
        ]

    @classmethod
    def get_staff_keys(cls, user_id):
        return [
            cls.STAFF_PROFILE.format(user_id=user_id),
            cls.STAFF_DASHBOARD_DATA.format(user_id=user_id),
            cls.USER_ACCOUNT_MANAGEMENT.format(user_id=user_id),
            # Legacy
            cls._LEGACY_STAFF_PROFILE.format(user_id=user_id),
            cls._LEGACY_STAFF_DASHBOARD.format(user_id=user_id),
            cls._LEGACY_ACCOUNT_MANAGEMENT.format(user_id=user_id),
        ]

    @classmethod
    def get_exam_keys(cls, exam_id):
        return [
            cls.EXAM_DETAIL.format(exam_id=exam_id),
            cls.EXAM_TAKE_V2.format(exam_id=exam_id),
            cls.EXAM_QUESTIONS.format(exam_id=exam_id),
            cls.EXAM_RESULTS.format(exam_id=exam_id),
            cls.RANKING_SNAPSHOT.format(exam_id=exam_id),
        ]


def get_or_set_cache(key, fn, ttl=DEFAULT_TTL):
    data = cache.get(key)
    if data is not None:
        return data
    data = fn()
    cache.set(key, data, ttl)
    return data


def delete_many_cache(keys):
    cache.delete_many(keys)


def invalidate_candidate_cache(candidate_id, user_id=None):
    """Clear all cache entries related to a specific candidate."""
    keys = CacheKeys.get_candidate_keys(candidate_id, user_id)
    # Also clear dashboard-specific keys if we have candidate_id
    if candidate_id:
        keys.extend(
            [
                CacheKeys.CANDIDATE_DASHBOARD.format(candidate_id=candidate_id),
                CacheKeys.CANDIDATE_DASHBOARD_V2.format(candidate_id=candidate_id),
            ]
        )
    delete_many_cache(keys)


def invalidate_user_cache(user_id):
    """Clear all cache entries related to a specific user."""
    keys = CacheKeys.get_user_keys(user_id)
    delete_many_cache(keys)


def invalidate_staff_cache(user_id):
    """Clear all cache entries related to a specific staff member."""
    keys = CacheKeys.get_staff_keys(user_id)
    delete_many_cache(keys)


def invalidate_exam_cache(exam_id):
    """Clear all cache entries related to a specific exam."""
    keys = CacheKeys.get_exam_keys(exam_id)
    delete_many_cache(keys)

    # Since EXAM_DETAIL in ExamDetailV2View appends query params,
    # we use delete_pattern to clear all variations of it.
    detail_pattern = f"{CacheKeys.EXAM_DETAIL.format(exam_id=exam_id)}*"
    try:
        cache.delete_pattern(detail_pattern)
    except (AttributeError, NotImplementedError):
        # Fallback if the cache backend doesn't support delete_pattern
        pass


def invalidate_staff_dashboard():
    """Clear global staff dashboard cache."""
    cache.delete(CacheKeys.STAFF_DASHBOARD)


def invalidate_score_boards(exam_id=None):
    """Clear league leaderboard cache."""
    cache.delete(CacheKeys.LEADERBOARD_LEAGUE)
    cache.delete(CacheKeys.RANKING_SNAPSHOT.format(exam_id=exam_id))


def invalidate_question_pool():
    """Clear question pool cache."""
    cache.delete(CacheKeys.QUESTION_POOL)
    cache.delete(CacheKeys._LEGACY_QUESTION_POOL)


def invalidate_feature_flag(key):
    """Clear feature flag cache."""
    cache.delete(CacheKeys.FEATURE_FLAG.format(key=key))
    cache.delete(CacheKeys._LEGACY_FEATURE_FLAG.format(key=key))


def invalidate_registration_status():
    """Clear registration status cache."""
    cache.delete(CacheKeys.REGISTRATION_STATUS)
    cache.delete(CacheKeys._LEGACY_REGISTRATION_STATUS)


def invalidate_notifications(user_id):
    """Increment the notification version in the cache for a given user ID."""
    version_key = CacheKeys.NOTIFICATIONS_VERSION.format(user_id=user_id)
    try:
        cache.incr(version_key)
    except ValueError:
        # First time, set to 1 (next read will be version 1)
        cache.set(version_key, 1, 86400)

    # Also clear any cached notification lists for this user
    pattern = f"notifications_{user_id}_*"
    try:
        cache.delete_pattern(pattern)
    except (AttributeError, NotImplementedError):
        pass


def question_pool_aggregate(qs):
    return qs.aggregate(
        total_questions=Count("id"),
        hard_questions_count=Count("id", filter=Q(difficulty=Question.Difficulty.HARD)),
        moderate_questions_count=Count(
            "id", filter=Q(difficulty=Question.Difficulty.MODERATE)
        ),
        easy_questions_count=Count("id", filter=Q(difficulty=Question.Difficulty.EASY)),
    )


def truncate_float(val):
    """
    Truncates a float to a specified number
    of decimal places without rounding
    """
    factor = 10.0**2
    return math.trunc(val * factor) / factor
