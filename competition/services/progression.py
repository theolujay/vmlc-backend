import logging
from django.db import transaction
from django.utils import timezone
from competition.models import (
    Competition,
    Stage,
    Enrollment,
    EnrollmentStageProgress,
    RankingSnapshot,
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
    def promote_candidates(
        from_stage_type, to_stage_type, cutoff_rank=None, competition_id=None
    ):
        """
        Promotes candidates from one stage to the next based on an advancement policy or explicit cutoff.
        """
        if competition_id:
            competition = Competition.objects.get(id=competition_id)
        else:
            competition = Competition.objects.filter(
                status=Competition.Status.ACTIVE
            ).first()

        if not competition:
            raise ProgressionError("No active competition found.")

        # Identify the stages
        from_stage = Stage.objects.filter(
            competition=competition, type=from_stage_type
        ).first()
        to_stage = Stage.objects.filter(
            competition=competition, type=to_stage_type
        ).first()

        if not from_stage:
            raise ProgressionError(f"Source stage '{from_stage_type}' not found.")
        if not to_stage:
            raise ProgressionError(f"Target stage '{to_stage_type}' not found.")

        # Determine the effective cutoff rank
        if cutoff_rank is None:
            # Prefer policy from the stage being exited
            policy = from_stage.config.get("advancement_policy")

            if not policy:
                raise ProgressionError(
                    f"No advancement_policy found for {from_stage_type} -> {to_stage_type}. AND cutoff_rank wasn't provided"
                )

            mode = policy.get("mode")
            value = policy.get("value")

            if mode == "top_n":
                cutoff_rank = int(value)
            elif mode == "top_percent":
                # Calculate total active candidates in from_stage to apply percentage
                total_active_in_stage = 0
                if from_stage_type == Stage.Type.SCREENING:
                    ranking = (
                        RankingSnapshot.objects.filter(
                            competition=competition,
                            stage=Stage.Type.SCREENING,
                            is_published=True,
                        )
                        .order_by("-published_at")
                        .first()
                    )
                    if ranking:
                        total_active_in_stage = ranking.entries.count()
                elif from_stage_type == Stage.Type.LEAGUE:
                    leaderboard = LeaderboardService.get_latest_league_leaderboard(
                        competition
                    )
                    if leaderboard:
                        total_active_in_stage = leaderboard.entries.count()

                if total_active_in_stage > 0:
                    import math

                    cutoff_rank = max(
                        1, math.ceil(total_active_in_stage * float(value))
                    )  # resolve cutoff_rank to at least 1
                else:
                    raise ProgressionError(
                        f"Cannot calculate top_percent: No enrollments found in {from_stage_type} stage."
                    )
            else:
                raise ProgressionError(f"Unsupported advancement mode: {mode}")

        logger.info(
            f"Advancement: Using cutoff_rank={cutoff_rank} for {from_stage_type} -> {to_stage_type}"
        )

        # Identify candidate IDs to promote
        candidate_ids_to_promote = []
        candidate_ids_to_eliminate = []

        if from_stage_type == Stage.Type.SCREENING:
            ranking = (
                RankingSnapshot.objects.filter(
                    competition=competition,
                    stage=Stage.Type.SCREENING,
                    is_published=True,
                )
                .order_by("-published_at")
                .first()
            )

            if not ranking:
                raise ProgressionError("No published Screening ranking snapshot found.")

            candidate_ids_to_promote = list(
                ranking.entries.filter(rank__lte=cutoff_rank).values_list(
                    "candidate_id", flat=True
                )
            )

            candidate_ids_to_eliminate = list(
                ranking.entries.filter(rank__gt=cutoff_rank).values_list(
                    "candidate_id", flat=True
                )
            )

        elif from_stage_type == Stage.Type.LEAGUE:
            leaderboard = LeaderboardService.get_latest_league_leaderboard(competition)
            if not leaderboard:
                raise ProgressionError("No League leaderboard found.")

            # Use the entries from the leaderboard
            candidate_ids_to_promote = [
                entry.candidate_id
                for entry in leaderboard.entries.filter(overall_rank__lte=cutoff_rank)
            ]
            candidate_ids_to_eliminate = [
                entry.candidate_id
                for entry in leaderboard.entries.filter(overall_rank__gt=cutoff_rank)
            ]

        else:
            raise ProgressionError(
                f"Promotion from stage '{from_stage_type}' is not supported."
            )

        if not candidate_ids_to_promote:
            return 0

        now = timezone.now()

        # Update Enrollment
        # Promote meeting cutoff
        Enrollment.objects.filter(
            competition=competition,
            candidate_id__in=candidate_ids_to_promote,
            status=Enrollment.Status.ACTIVE,
        ).update(current_stage=to_stage, last_active_at=now)

        # Eliminate below cutoff
        Enrollment.objects.filter(
            competition=competition,
            candidate_id__in=candidate_ids_to_eliminate,
            status=Enrollment.Status.ACTIVE,
        ).update(status=Enrollment.Status.ELIMINATED, last_active_at=now)

        # Update Candidate Roles (for permissions)
        from identity.models import Candidate

        Candidate.objects.filter(pk__in=candidate_ids_to_promote).update(
            role=to_stage_type
        )
        # Not sure if we should also move eliminated candidates back to 'screening' or just keep them.
        # For now, let's just keep their role as is, or we could explicitly set it to screening.
        # Candidate.objects.filter(pk__in=candidate_ids_to_eliminate).update(role=Candidate.Roles.SCREENING)
        # TODO: decide on 'base' role or something other than screening, league... for candidates not in active competition
        # Update Old StageProgress
        from_stage = Stage.objects.filter(
            competition=competition, type=from_stage_type
        ).first()
        if from_stage:
            EnrollmentStageProgress.objects.filter(
                enrollment__competition=competition,
                enrollment__candidate_id__in=(
                    candidate_ids_to_promote + candidate_ids_to_eliminate
                ),
                stage=from_stage,
            ).update(status=EnrollmentStageProgress.Status.COMPLETED, completed_at=now)

        # Create/Update New StageProgress
        enrollments = Enrollment.objects.filter(
            competition=competition, candidate_id__in=candidate_ids_to_promote
        )
        for enrollment in enrollments:
            EnrollmentStageProgress.objects.update_or_create(
                enrollment=enrollment,
                stage=to_stage,
                defaults={
                    "status": EnrollmentStageProgress.Status.IN_PROGRESS,
                    "started_at": now,
                },
            )

        # Send Notifications
        ProgressionService._send_notifications(
            competition=competition,
            promoted_ids=candidate_ids_to_promote,
            eliminated_ids=candidate_ids_to_eliminate,
            to_stage_type=to_stage_type,
        )

        # Invalidate Caches
        from vmlc.v2.utils import invalidate_candidate_cache, invalidate_staff_dashboard

        all_affected_ids = candidate_ids_to_promote + candidate_ids_to_eliminate

        def clear_batch_cache():
            for c_id in all_affected_ids:
                invalidate_candidate_cache(c_id)
            invalidate_staff_dashboard()

        transaction.on_commit(clear_batch_cache)

        logger.info(
            f"Successfully promoted {len(candidate_ids_to_promote)} candidates from {from_stage_type} to {to_stage_type}."
        )
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
            candidates = Candidate.objects.filter(pk__in=promoted_ids).select_related(
                "user"
            )
            subject = f"Congrats!"
            message = (
                f"Based on your performance in the previous stage of {competition.name}, "
                f"you have successfully advanced to the {to_stage_type.title()} stage. "
                "Check your dashboard for more information."
            )
            for cand in candidates:
                notifications.append(
                    Notification(
                        recipient=cand.user,
                        subject=subject,
                        message=message,
                        type=Notification.Type.SUCCESS,
                    )
                )

        # Eliminated Notifications
        if eliminated_ids:
            candidates = Candidate.objects.filter(pk__in=eliminated_ids).select_related(
                "user"
            )
            subject = f"Competition Update: {competition.name}"
            message = (
                f"Thank you for participating in {competition.name}. "
                "Unfortunately, you did not meet the cutoff for the next stage. "
                "We appreciate your effort and hope to see you in future editions."
            )
            for cand in candidates:
                notifications.append(
                    Notification(
                        recipient=cand.user,
                        subject=subject,
                        message=message,
                        type=Notification.Type.INFO,
                    )
                )

        if notifications:
            Notification.objects.bulk_create(notifications)
            logger.info(f"Sent {len(notifications)} progression notifications.")
