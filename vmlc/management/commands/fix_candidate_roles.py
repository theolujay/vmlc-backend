import logging

from django.core.management.base import BaseCommand

from identity.models import Candidate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Ensures all Candidate roles are consistent with defined choices (lowercase)."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Starting candidate role consistency check...")
        )

        fixed_count = 0
        total_candidates = Candidate.objects.count()

        for candidate in Candidate.objects.all():
            original_role = candidate.role

            # Check if the current role is one of the valid lowercase values
            if original_role not in Candidate.Roles.values:
                # If not, try to find a match ignoring case
                found_match = False
                for role_value, role_display in Candidate.Roles.choices:
                    if original_role.lower() == role_value:
                        candidate.role = role_value
                        candidate.save(update_fields=["role"])
                        fixed_count += 1
                        logger.info(
                            f"Fixed candidate {candidate.pk} role from '{original_role}' to '{candidate.role}'"
                        )
                        self.stdout.write(
                            self.style.WARNING(
                                f"Fixed candidate {candidate.pk} role from '{original_role}' to '{candidate.role}'"
                            )
                        )
                        found_match = True
                        break

                if not found_match:
                    # If no case-insensitive match, default to SCREENING or log an error
                    logger.error(
                        f"Candidate {candidate.pk} has an invalid role '{original_role}'. Defaulting to '{Candidate.Roles.SCREENING}'."
                    )
                    self.stdout.write(
                        self.style.ERROR(
                            f"Candidate {candidate.pk} has an invalid role '{original_role}'. Defaulting to '{Candidate.Roles.SCREENING}'."
                        )
                    )
                    candidate.role = Candidate.Roles.SCREENING
                    candidate.save(update_fields=["role"])
                    fixed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished candidate role consistency check. Total candidates: {total_candidates}, Roles fixed: {fixed_count}."
            )
        )
