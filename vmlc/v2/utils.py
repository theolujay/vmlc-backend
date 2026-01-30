from django.core.cache import cache

from django.db.models import Count, Q

from vmlc.models import Question


DEFAULT_TTL = 86400  # 24h


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


def question_pool_aggregate(qs):
    return qs.aggregate(
        total_questions=Count("id"),
        hard_questions_count=Count("id", filter=Q(difficulty=Question.Difficulty.HARD)),
        moderate_questions_count=Count(
            "id", filter=Q(difficulty=Question.Difficulty.MODERATE)
        ),
        easy_questions_count=Count("id", filter=Q(difficulty=Question.Difficulty.EASY)),
    )
