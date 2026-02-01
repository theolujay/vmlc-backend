import logging
from django.db.models import Count, Avg, Q
from competition.models import (
    Competition,
    Stage, 
    StageExam, 
    CandidateCompetition, 
    Standings
)
from vmlc.models import Exam, CandidateExamResult
from competition.services.leaderboard import LeaderboardService

logger = logging.getLogger(__name__)

class CompetitionDashboardService:
    @staticmethod
    def get_dashboard_data():
        active_comp = Competition.objects.filter(status=Competition.Status.ACTIVE).first()
        if not active_comp:
            return None
        
        # TODO: set registered candidate to CandidateCompetition.Status.DISQUALIFIED
        # when set to candidate.user.is_active=False in order to count them out of the
        # following stats queryset

        # Get Stats
        stats = CandidateCompetition.objects.filter(competition=active_comp).aggregate(
            enrolled=Count('id', filter=Q(status=CandidateCompetition.Status.ENROLLED)),
            active=Count('id', filter=Q(status=CandidateCompetition.Status.ACTIVE)),
            eliminated=Count('id', filter=Q(status=CandidateCompetition.Status.ELIMINATED)),
        )

        # Compute Progress

        # Determine current stage and round based on the latest active StageExam
        latest_active_slot = StageExam.objects.filter(
            competition_stage__competition=active_comp,
            is_active=True
        ).select_related('competition_stage').order_by('-competition_stage__order', '-round').first()

        current_stage_type = latest_active_slot.competition_stage.type if latest_active_slot else None
        current_round = latest_active_slot.round if latest_active_slot else None
        
        total_rounds = 0
        published_rounds = 0
        if current_stage_type is not None:
             total_rounds = StageExam.objects.filter(
                 competition_stage__competition=active_comp,
                 competition_stage__type=current_stage_type
             ).count()
             
             published_rounds = Standings.objects.filter(
                 competition=active_comp,
                 stage=current_stage_type,
                 is_published=True
             ).count()

        progress = {
            "current_stage": current_stage_type,
            "current_round": current_round,
            "total_rounds": total_rounds,
            "published_rounds": published_rounds
        }

        # Gather Exams data
        exams_list = []
        # Get all slots for this competition
        slots = StageExam.objects.filter(
            competition_stage__competition=active_comp
        ).select_related('competition_stage').order_by('competition_stage__order', 'round')

        for slot in slots:
            try:
                # OneToOneField backref
                exam = slot.exam
            except Exam.DoesNotExist:
                continue
            
            # skip if exam is in draft or is cancelled
            if exam.status == Exam.Status.DRAFT or Exam.Status.CANCELLED:
                continue
            # Calculate stats for this exam
            res_stats = CandidateExamResult.objects.filter(exam=exam).aggregate(
                sat=Count('id'),
                avg=Avg('score')
            )
            
            # check standings status
            standings = Standings.objects.filter(exam=exam).first()
            standings_status = "pending"
            if standings:
                standings_status = "published" if standings.is_published else "ready"

            # TODO: calculate absent count when eligibility logic is adequate
            # For now, keep it simple as per SAT stats
            
            exams_list.append({
                "id": exam.id,
                "title": str(exam),
                "stage": slot.competition_stage.type,
                "status": exam.status,
                "standings_status": standings_status,
                "stats": {
                    "candidates_sat": res_stats['sat'],
                    "avg_score": float(res_stats['avg'] or 0)
                }
            })

        # Leaderboard Summary (Top 3)
        leaderboard_summary = []
        latest_leaderboard = LeaderboardService.get_latest_league_leaderboard(active_comp)
        if latest_leaderboard:
            # The service annotates processed_entries
            leaderboard_summary = latest_leaderboard.processed_entries[:3]

        # Latest Standings Summary (Top 3)
        latest_standings_summary = None
        latest_published_standings = Standings.objects.filter(
            competition=active_comp,
            is_published=True
        ).select_related('exam').order_by('-published_at', '-created_at').first()

        if latest_published_standings:
            entries = latest_published_standings.entries.select_related('candidate__user').order_by('rank')[:3]
            from competition.serializers import StandingsEntrySerializer
            latest_standings_summary = {
                "exam_id": latest_published_standings.exam_id,
                "exam_title": str(latest_published_standings.exam),
                "entries": StandingsEntrySerializer(entries, many=True).data
            }

        return {
            "stats": stats,
            "progress": progress,
            "exams": exams_list,
            "leaderboard_summary": leaderboard_summary,
            "latest_standings_summary": latest_standings_summary
        }
