import logging

from django.core.cache import cache
from django.core.management.base import BaseCommand

from competition.models import Competition
from competition.services.enrollment import EnrollmentError, EnrollmentService
from identity.models import Candidate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Enrolls all existing candidates into the current active competition."

    def add_arguments(self, parser):
        parser.add_argument(
            "--competition-id",
            type=int,
            help="Specify a competition ID to enroll into. Defaults to the active competition.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Don't actually save changes, just show what would be done.",
        )

    def handle(self, *args, **options):
        competition_id = options.get("competition_id")
        dry_run = options.get("dry_run")

        if competition_id:
            try:
                competition = Competition.objects.get(id=competition_id)
            except Competition.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(
                        f"Competition with ID {competition_id} does not exist."
                    )
                )
                return
        else:
            competition = Competition.objects.filter(
                status=Competition.Status.ACTIVE
            ).first()
            if not competition:
                self.stderr.write(self.style.ERROR("No active competition found."))
                return

        self.stdout.write(f"Target Competition: {competition} (ID: {competition.id})")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Dry run enabled. No changes will be saved.")
            )
            # In a dry run, we just count how many WOULD be enrolled
            from competition.models import Enrollment

            enrolled_candidate_ids = Enrollment.objects.filter(
                competition=competition
            ).values_list("candidate_id", flat=True)
            candidates_to_enroll = Candidate.objects.exclude(
                pk__in=enrolled_candidate_ids
            )
            self.stdout.write(
                f"Found {candidates_to_enroll.count()} candidates to enroll."
            )
            return

        try:
            created_count = EnrollmentService.enroll_candidates(competition)
            if created_count == 0:
                self.stdout.write(
                    self.style.SUCCESS("All candidates are already enrolled.")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully enrolled {created_count} candidates."
                    )
                )
            self.stdout.write("Clearing cache...")
            cache.clear()
        except EnrollmentError as e:
            self.stderr.write(self.style.ERROR(str(e)))
