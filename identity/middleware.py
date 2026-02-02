from django.utils.deprecation import MiddlewareMixin
from competition.services.eligibility import EligibilityService
from vmlc.v2.utils import get_or_set_cache, CacheKeys

class CompetitionContextMiddleware(MiddlewareMixin):
    """
    Middleware that attaches the candidate's active competition participation 
    to the request object for easy access in views and permissions.
    """
    def process_request(self, request):
        if request.user.is_authenticated:
            # Check if user has a candidate profile
            if hasattr(request.user, 'candidate_profile'):
                cache_key = CacheKeys.PARTICIPATION.format(user_id=request.user.id)
                request.participation = get_or_set_cache(
                    cache_key,
                    lambda: EligibilityService.get_active_participation(
                        request.user.candidate_profile
                    ),
                    ttl=300 # 5-minute cache for context
                )
            else:
                request.participation = None
        else:
            request.participation = None
        return None
