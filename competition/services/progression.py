import logging
from django.db import transaction
from django.utils import timezone
from competition.models import (
    Competition,
    RankingSnapshotEntry,
    Stage,
    Enrollment,
    EnrollmentStageProgress,
    RankingSnapshot,
)
from competition.services.leaderboard import LeaderboardService
from vmlc.v2.utils import invalidate_candidate_cache, invalidate_staff_dashboard

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
        from_stage_type: str,
        to_stage_type: str,
        cutoff_rank: int | None = None,
        competition_id: int | None = None
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
                            is_active=True,
                            is_published=True,
                        )
                        .order_by("-published_at")
                        .first()
                    )
                    if ranking:
                        total_active_in_stage = ranking.entries.count()
                    else:
                        raise ProgressionError(
                            f"No active, published {from_stage_type.title()} ranking available to promote candidates to {to_stage_type.title()} stage"
                        )
                elif from_stage_type == Stage.Type.LEAGUE:
                    leaderboard = LeaderboardService.get_latest_league_leaderboard(
                        competition
                    )
                    if leaderboard:
                        total_active_in_stage = leaderboard.entries.count()
                    else:
                        raise ProgressionError(
                            f"No {from_stage_type.title()} leaderboard to promote candidates to {to_stage_type.title()} stage"
                        )

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
                    is_active=True,
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
        # For now, let's just keep their role as is and not explicitly set it to screening.

        # Candidate.objects.filter(pk__in=candidate_ids_to_eliminate).update(role=Candidate.Roles.SCREENING)

        # TODO: decide on a base role or something other than screening, league... for candidates not in active competition

        # Update Old StageProgress
        from_stage = Stage.objects.filter(
            competition=competition, type=from_stage_type
        ).first()
        if from_stage:
            # Mark promoted as COMPLETED
            EnrollmentStageProgress.objects.filter(
                enrollment__competition=competition,
                enrollment__candidate_id__in=candidate_ids_to_promote,
                stage=from_stage,
            ).update(status=EnrollmentStageProgress.Status.COMPLETED, completed_at=now)

            # Mark eliminated as DISCONTINUED
            EnrollmentStageProgress.objects.filter(
                enrollment__competition=competition,
                enrollment__candidate_id__in=candidate_ids_to_eliminate,
                stage=from_stage,
            ).update(
                status=EnrollmentStageProgress.Status.DISCONTINUED, discontinued_at=now
            )

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
    @transaction.atomic
    def eliminate_league_absentees(ranking_snapshot_id):
        """
        Eliminates candidates who missed a league exam.
        """
        ranking = RankingSnapshot.objects.get(id=ranking_snapshot_id)
        if ranking.stage != Stage.Type.LEAGUE:
            return 0

        # Identify absentees in this ranking who are still ACTIVE
        # We look for entries with no exam_score.
        absentee_entries = RankingSnapshotEntry.objects.filter(
            ranking_snapshot=ranking,
            exam_score__isnull=True,
            enrollment__status=Enrollment.Status.ACTIVE,
        ).select_related("enrollment", "candidate__user")

        if not absentee_entries.exists():
            return 0

        now = timezone.now()
        enrollment_ids = [e.enrollment_id for e in absentee_entries]
        candidate_ids = [e.candidate_id for e in absentee_entries]
        # Update Enrollment status to ELIMINATED
        Enrollment.objects.filter(id__in=enrollment_ids).update(
            status=Enrollment.Status.ELIMINATED, last_active_at=now
        )
        # Update current StageProgress to DISCONTINUED
        EnrollmentStageProgress.objects.filter(
            enrollment_id__in=enrollment_ids,
            stage__type=Stage.Type.LEAGUE,
            status=EnrollmentStageProgress.Status.IN_PROGRESS,
        ).update(status=EnrollmentStageProgress.Status.DISCONTINUED, discontinued_at=now)
        # Send Notifications
        ProgressionService._send_absentee_notifications(
            competition=ranking.competition, absentee_entries=absentee_entries
        )
        # Invalidate Caches
        from vmlc.v2.utils import invalidate_candidate_cache, invalidate_staff_dashboard

        def clear_caches():
            for c_id in candidate_ids:
                invalidate_candidate_cache(c_id)
            invalidate_staff_dashboard()

        transaction.on_commit(clear_caches)

        logger.info(
            f"Eliminated {len(enrollment_ids)} absentees from league stage based on RankingSnapshot {ranking_snapshot_id}."
        )
        return len(enrollment_ids)

    @staticmethod
    @transaction.atomic
    def disqualify_candidate(candidate_id, competition_id=None, reason=None):
        """
        Disqualifies a candidate from the competition.
        """
        if competition_id:
            competition = Competition.objects.get(id=competition_id)
        else:
            competition = Competition.objects.filter(
                status=Competition.Status.ACTIVE
            ).first()

        if not competition:
            raise ProgressionError("No active competition found.")

        now = timezone.now()

        # Update Enrollment
        enrollment = Enrollment.objects.filter(
            competition=competition,
            candidate_id=candidate_id,
            status=Enrollment.Status.ACTIVE,
        ).first()

        if not enrollment:
            raise ProgressionError(
                f"No active enrollment found for candidate {candidate_id}."
            )

        enrollment.status = Enrollment.Status.DISQUALIFIED
        enrollment.last_active_at = now
        if reason:
            if not enrollment.metadata:
                enrollment.metadata = {}
            enrollment.metadata["disqualification_reason"] = reason
        enrollment.save()

        # Update current StageProgress
        EnrollmentStageProgress.objects.filter(
            enrollment=enrollment, stage=enrollment.current_stage
        ).update(
            status=EnrollmentStageProgress.Status.DISCONTINUED, discontinued_at=now
        )

        # Invalidate Caches
        invalidate_candidate_cache(candidate_id)
        invalidate_staff_dashboard()

        logger.info(f"Candidate {candidate_id} has been disqualified.")
        return True

    @staticmethod
    def _send_absentee_notifications(competition, absentee_entries):
        """
        Sends platform notifications to candidates about their elimination due to absence.
        """
        from comms.models import Notification
        from comms.signals import notifications_created

        notifications = []
        subject = f"Update: {competition.get_title()}"
        message = (
            "Dear {candidate_full_name},\n\n"
            f"You have been eliminated from {competition.get_title()} for missing a required league exam. "
            "Participation in all league rounds is mandatory. "
            "We hope to see you in future editions. \n\n"
            "Regards,\n"
            "VMLC Team."
        )
        for entry in absentee_entries:
            candidate_user = entry.candidate.user
            personalized_message = message.format(
                candidate_full_name=candidate_user.get_full_name()
            )
            notifications.append(
                Notification(
                    recipient=candidate_user,
                    subject=subject,
                    message=personalized_message,
                    type=Notification.Type.INFO,
                    metadata={"send_email": True},
                )
            )

        if notifications:
            created_notifications = Notification.objects.bulk_create(notifications)
            notifications_created.send(
                sender=ProgressionService._send_absentee_notifications,
                notifications=created_notifications,
            )
            logger.info(f"Sent {len(notifications)} absentee elimination notifications.")

    @staticmethod
    def _send_notifications(competition, promoted_ids, eliminated_ids, to_stage_type):
        """
        Sends platform notifications to candidates about their promotion or elimination.
        """
        from comms.models import Notification
        from comms.signals import notifications_created
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
                        metadata={"send_email": True},
                    )
                )

        # Eliminated Notifications
        if eliminated_ids:
            candidates = Candidate.objects.filter(pk__in=eliminated_ids).select_related(
                "user"
            )
            subject = f"Update: {competition.get_title()}"
            message = (
                "Dear {candidate_full_name},\n\n"
                f"Thank you for participating in {competition.name}. "
                "Unfortunately, you did not meet the cutoff for the next stage. "
                "We appreciate your effort and hope to see you in future editions.\n\n"
                "Regards,\n"
                "VMLC Team."
            )
            for cand in candidates:
                personalized_message = message.format(
                    candidate_full_name=cand.user.get_full_name()
                )
                notifications.append(
                    Notification(
                        recipient=cand.user,
                        subject=subject,
                        message=personalized_message,
                        type=Notification.Type.INFO,
                        metadata={"send_email": True},
                    )
                )

        if notifications:
            created_notifications = Notification.objects.bulk_create(notifications)
            notifications_created.send(
                sender=ProgressionService._send_notifications,
                notifications=created_notifications,
            )
            logger.info(f"Sent {len(notifications)} progression notifications.")
