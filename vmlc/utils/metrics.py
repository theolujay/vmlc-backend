from datetime import timedelta
from django.db.models import Count, Q
from django.db.models.functions import TruncDay, TruncWeek
from django.utils import timezone
from identity.models import User, Candidate, Staff, PreRegUser
from ..models import Event

def get_registration_metrics(days=30, weeks=12):
    """
    Computes aggregated registration metrics for daily and weekly granularity.
    """
    now = timezone.now()
    
    # Daily metrics
    start_date_daily = now - timedelta(days=days)
    
    daily_users = User.objects.filter(date_joined__gte=start_date_daily) \
        .annotate(day=TruncDay('date_joined')) \
        .values('day') \
        .annotate(count=Count('id')) \
        .order_by('day')
        
    daily_candidates = Candidate.objects.filter(created_at__gte=start_date_daily) \
        .annotate(day=TruncDay('created_at')) \
        .values('day') \
        .annotate(count=Count('user_id')) \
        .order_by('day')
        
    daily_staff = Staff.objects.filter(created_at__gte=start_date_daily) \
            .annotate(day=TruncDay('created_at')) \
            .values('day') \
            .annotate(count=Count('user_id')) \
            .order_by('day')
        
    daily_pre_reg = PreRegUser.objects.filter(created_at__gte=start_date_daily) \
            .annotate(day=TruncDay('created_at')) \
            .values('day') \
            .annotate(count=Count('id')) \
            .order_by('day')

    # Weekly metrics
    start_date_weekly = now - timedelta(weeks=weeks)
    
    weekly_users = User.objects.filter(date_joined__gte=start_date_weekly) \
        .annotate(week=TruncWeek('date_joined')) \
        .values('week') \
        .annotate(count=Count('id')) \
        .order_by('week')
        
    weekly_candidates = Candidate.objects.filter(created_at__gte=start_date_weekly) \
        .annotate(week=TruncWeek('created_at')) \
        .values('week') \
        .annotate(count=Count('user_id')) \
        .order_by('week')
        
    weekly_staff = Staff.objects.filter(created_at__gte=start_date_weekly) \
        .annotate(week=TruncWeek('created_at')) \
        .values('week') \
        .annotate(count=Count('user_id')) \
        .order_by('week')
        
    weekly_pre_reg = PreRegUser.objects.filter(created_at__gte=start_date_weekly) \
        .annotate(week=TruncWeek('created_at')) \
        .values('week') \
        .annotate(count=Count('id')) \
        .order_by('week')

    return {
        "daily": {
            "total_users": list(daily_users),
            "candidates": list(daily_candidates),
            "staff": list(daily_staff),
            "pre_registrations": list(daily_pre_reg),
        },
        "weekly": {
            "total_users": list(weekly_users),
            "candidates": list(weekly_candidates),
            "staff": list(weekly_staff),
            "pre_registrations": list(weekly_pre_reg),
        }
    }

def get_funnel_metrics():
    """
    Computes registration funnel metrics leveraging Event logs for efficiency,
    broken down by interest type (candidate vs volunteer).
    """

    def calculate_stats(pre_events_qs, conv_events_qs, completed_fallback=None, pending_fallback=None):
        pre_count = pre_events_qs.count()
        conv_count = conv_events_qs.count()

        # Fallback to model counts for legacy data if no events exist yet
        if pre_count == 0 and completed_fallback is not None:
            conv_count = completed_fallback
            pre_count = conv_count + (pending_fallback or 0)

        conversion_percentage = 0
        if pre_count > 0:
            conversion_percentage = (conv_count / pre_count) * 100

        return {
            "pre_registrations": pre_count,
            "completed_registrations": conv_count,
            "conversion_percentage": round(conversion_percentage, 2)
        }

    # Total pre-registrations started
    total_pre = Event.objects.filter(event_name="PRE_REGISTRATION")
    # Pre-registrations that successfully converted to full registrations
    total_conv = Event.objects.filter(event_name="PRE_REG_CONVERSION")

    # Fallback data helpers
    registered_emails = User.objects.values_list('email', flat=True)
    
    # Overall
    overall_stats = calculate_stats(
        total_pre, 
        total_conv, 
        completed_fallback=User.objects.count(),
        pending_fallback=PreRegUser.objects.exclude(email__in=registered_emails).count()
    )

    # Candidate breakdown
    candidate_stats = calculate_stats(
        total_pre.filter(metadata__interest_type="candidate"),
        total_conv.filter(metadata__interest_type="candidate"),
        completed_fallback=Candidate.objects.count(),
        pending_fallback=PreRegUser.objects.filter(interest_type="candidate").exclude(email__in=registered_emails).count()
    )

    # Volunteer breakdown
    volunteer_stats = calculate_stats(
        total_pre.filter(metadata__interest_type="volunteer"),
        total_conv.filter(metadata__interest_type="volunteer"),
        completed_fallback=Staff.objects.count(),
        pending_fallback=PreRegUser.objects.filter(interest_type="volunteer").exclude(email__in=registered_emails).count()
    )

    return {
        "overall": overall_stats,
        "candidate": candidate_stats,
        "volunteer": volunteer_stats
    }