from django.utils.deprecation import MiddlewareMixin
from competition.services.eligibility import EligibilityService

class CompetitionContextMiddleware(MiddlewareMixin):
    """
    Middleware that attaches the candidate's active competition participation 
    to the request object for easy access in views and permissions.
    """
    def process_request(self, request):
        if request.user.is_authenticated:
            # Check if user has a candidate profile
            if hasattr(request.user, 'candidate_profile'):
                request.participation = EligibilityService.get_active_participation(
                    request.user.candidate_profile
                )
            else:
                request.participation = None
        else:
            request.participation = None
        return None
