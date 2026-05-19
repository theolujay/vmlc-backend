from django.core.management.base import BaseCommand

from identity.models import PreRegUser, User
from vmlc.models import Event
from core.utils.events import log_event


class Command(BaseCommand):
    help = "Backfills Pre-registration events for older data"

    def handle(self, *args, **options):
        def backfill_pre_registration_events():
            """
            Generate PRE_REGISTRATION events for pre-registered users who don't have them.
            Excludes users who have already completed full registration.
            """
            # Get emails of fully registered users
            registered_emails = set(User.objects.values_list("email", flat=True))

            # Get emails that already have pre-registration events
            emails_with_events = set(
                Event.objects.filter(event_name="PRE_REGISTRATION").values_list(
                    "metadata__email", flat=True
                )
            )

            # Get all pre-registration users
            all_pre_reg_users = PreRegUser.objects.all()
            all_pre_reg_emails = set(all_pre_reg_users.values_list("email", flat=True))

            # Find emails that need events (missing events and not fully registered)
            emails_needing_events = (
                all_pre_reg_emails - emails_with_events
            ) - registered_emails

            # Generate events for the missing records
            pre_reg_users_to_process = PreRegUser.objects.filter(
                email__in=emails_needing_events
            )
            success_count = 0
            for pre_reg_user in pre_reg_users_to_process:
                if generate_event(
                    email=pre_reg_user.email, interest_type=pre_reg_user.interest_type
                ):
                    success_count += 1
                print(f"Event generated for {pre_reg_user.email}")

            return success_count, len(emails_needing_events)

        def generate_event(email, interest_type):
            """Create a PRE_REGISTRATION event for the given email."""
            try:
                log_event(
                    event_name="PRE_REGISTRATION",
                    metadata={"email": email, "interest_type": interest_type},
                )
                return True
            except Exception:
                # Consider logging this exception for debugging
                return False

        backfill_pre_registration_events()

        self.stdout.write(
            self.style.SUCCESS(
                "Database populated successfully with comprehensive test data!"
            )
        )
