import logging
from django.db import transaction
from django.utils import timezone
from competition.models import (
    Competition,
    Stage,
    CandidateCompetition,
    CandidateStageProgress,
    Standings,
)
from competition.services.leaderboard import LeaderboardService

logger = logging.getLogger(__name__)

class ProgressionError(Exception):
    pass

class ProgressionService:
    """
    Service to handle candidate promotion between competition stages.
    """

    @staticmethod
    @transaction.atomic
    def promote_candidates(from_stage_type, to_stage_type, cutoff_rank=None, competition_id=None):
        """
        Promotes the top N candidates from one stage to the next.
        """
        if competition_id:
            competition = Competition.objects.get(id=competition_id)
        else:
            competition = Competition.objects.filter(status=Competition.Status.ACTIVE).first()

        if not competition:
            raise ProgressionError("No active competition found.")

        # Identify the 'to' stage object
        to_stage = Stage.objects.filter(competition=competition, type=to_stage_type).first()
        if not to_stage:
            raise ProgressionError(f"Target stage '{to_stage_type}' not found for this competition.")

        # If cutoff_rank not provided, try to get it from stage config
        if cutoff_rank is None:
            cutoff_rank = to_stage.config.get("promotion_cutoff")
            if cutoff_rank is None:
                raise ProgressionError(f"No cutoff_rank provided and 'promotion_cutoff' not found in {to_stage_type} config.")

        # Identify candidate IDs to promote
        candidate_ids_to_promote = []
        candidate_ids_to_eliminate = []
        
        if from_stage_type == Stage.Type.SCREENING:
            standings = Standings.objects.filter(
                competition=competition, 
                stage=Stage.Type.SCREENING, 
                is_published=True
            ).order_by('-published_at').first()
            
            if not standings:
                raise ProgressionError("No published Screening standings found.")
            
            candidate_ids_to_promote = list(standings.entries.filter(
                rank__lte=cutoff_rank
            ).values_list('candidate_id', flat=True))

            candidate_ids_to_eliminate = list(standings.entries.filter(
                rank__gt=cutoff_rank
            ).values_list('candidate_id', flat=True))

        elif from_stage_type == Stage.Type.LEAGUE:
            leaderboard = LeaderboardService.get_latest_league_leaderboard(competition)
            if not leaderboard:
                raise ProgressionError("No League leaderboard found.")
            
            # Use the entries from the leaderboard
            candidate_ids_to_promote = [
                entry.candidate_id for entry in leaderboard.entries.filter(overall_rank__lte=cutoff_rank)
            ]
            candidate_ids_to_eliminate = [
                entry.candidate_id for entry in leaderboard.entries.filter(overall_rank__gt=cutoff_rank)
            ]
        
        else:
            raise ProgressionError(f"Promotion from stage '{from_stage_type}' is not supported.")

        if not candidate_ids_to_promote:
            return 0

        now = timezone.now()
        
        # Update CandidateCompetition
        # Promote meeting cutoff
        CandidateCompetition.objects.filter(
            competition=competition,
            candidate_id__in=candidate_ids_to_promote,
            status=CandidateCompetition.Status.ACTIVE
        ).update(current_stage=to_stage, last_active_at=now)

        # Eliminate below cutoff
        CandidateCompetition.objects.filter(
            competition=competition,
            candidate_id__in=candidate_ids_to_eliminate,
            status=CandidateCompetition.Status.ACTIVE
        ).update(status=CandidateCompetition.Status.ELIMINATED, last_active_at=now)

        # Update Candidate Roles (for permissions)
        from identity.models import Candidate
        Candidate.objects.filter(pk__in=candidate_ids_to_promote).update(role=to_stage_type)
        # Not sure if we should also move eliminated candidates back to 'screening' or just keep them.
        # For now, let's just keep their role as is, or we could explicitly set it to screening.
        # Candidate.objects.filter(pk__in=candidate_ids_to_eliminate).update(role=Candidate.Roles.SCREENING)
        # TODO: decide on 'base' role or something other than screening, league... for candidates not in active competition
        # Update Old StageProgress
        from_stage = Stage.objects.filter(competition=competition, type=from_stage_type).first()
        if from_stage:
            CandidateStageProgress.objects.filter(
                candidate_competition__competition=competition,
                candidate_competition__candidate_id__in=(candidate_ids_to_promote + candidate_ids_to_eliminate),
                stage=from_stage
            ).update(status=CandidateStageProgress.Status.COMPLETED, completed_at=now)

        # Create/Update New StageProgress
        participations = CandidateCompetition.objects.filter(
            competition=competition, 
            candidate_id__in=candidate_ids_to_promote
        )
        
        for part in participations:
             CandidateStageProgress.objects.update_or_create(
                 candidate_competition=part,
                 stage=to_stage,
                 defaults={
                     'status': CandidateStageProgress.Status.IN_PROGRESS,
                     'started_at': now
                 }
             )

        # Send Notifications
        ProgressionService._send_notifications(
            competition=competition,
            promoted_ids=candidate_ids_to_promote,
            eliminated_ids=candidate_ids_to_eliminate,
            to_stage_type=to_stage_type
        )

        # Invalidate Caches
        from vmlc.v2.utils import invalidate_candidate_cache, invalidate_staff_dashboard
        all_affected_ids = candidate_ids_to_promote + candidate_ids_to_eliminate
        
        def clear_batch_cache():
            for c_id in all_affected_ids:
                invalidate_candidate_cache(c_id)
            invalidate_staff_dashboard()
            
        transaction.on_commit(clear_batch_cache)

        logger.info(f"Successfully promoted {len(candidate_ids_to_promote)} candidates from {from_stage_type} to {to_stage_type}.")
        return len(candidate_ids_to_promote)

    @staticmethod
    def _send_notifications(competition, promoted_ids, eliminated_ids, to_stage_type):
        """
        Sends platform notifications to candidates about their promotion or elimination.
        """
        from comms.models import Notification
        from identity.models import Candidate

        notifications = []

        # Promoted Notifications
        if promoted_ids:
            candidates = Candidate.objects.filter(pk__in=promoted_ids).select_related('user')
            subject = f"Congrats!"
            message = (
                f"Hii! Based on your performance in the previous stage of {competition.name}, "
                f"you have successfully advanced to the {to_stage_type.title()} stage. "
                "Check your dashboard for more information."
            )
            for cand in candidates:
                notifications.append(Notification(
                    recipient=cand.user,
                    subject=subject,
                    message=message
                ))

        # Eliminated Notifications
        if eliminated_ids:
            candidates = Candidate.objects.filter(pk__in=eliminated_ids).select_related('user')
            subject = f"Competition Update: {competition.name}"
            message = (
                f"Thank you for participating in {competition.name}. "
                "Unfortunately, you did not meet the cutoff for the next stage. "
                "We appreciate your effort and hope to see you in future editions."
            )
            for cand in candidates:
                notifications.append(Notification(
                    recipient=cand.user,
                    subject=subject,
                    message=message
                ))

        if notifications:
            Notification.objects.bulk_create(notifications)
            logger.info(f"Sent {len(notifications)} progression notifications.")

