from django.utils.deprecation import MiddlewareMixin

from competition.models import Competition, Enrollment
from vmlc.utils.cache import get_or_set_cache, CacheKeys  # TODO: [core] move to core/ app


class CompetitionContextMiddleware(MiddlewareMixin):
    """
    Middleware that attaches the candidate's active competition enrollment
    to the request object for easy access in views and permissions.
    """

    def process_request(self, request):
        if request.user.is_authenticated:
            # Check if user has a candidate profile
            if hasattr(request.user, "candidate_profile"):
                cache_key = CacheKeys.ENROLLMENT.format(user_id=request.user.id)
                request.enrollment = get_or_set_cache(
                    cache_key,
                    lambda: Enrollment.objects.filter(
                        candidate=request.user.candidate_profile,
                        competition__status=Competition.Status.ACTIVE,
                        status=Enrollment.Status.ACTIVE,
                    )
                    .select_related("competition", "current_stage")
                    .first(),
                    ttl=300,  # 5-minute cache for context
                )
            else:
                request.enrollment = None
        else:
            request.enrollment = None
        return None
