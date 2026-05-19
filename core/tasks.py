import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    name="disable_expired_feature_flags_task",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def disable_expired_feature_flags_task(self, feature_flag_id):
    from vmlc.models import FeatureFlag

    try:
        feature_flag = FeatureFlag.objects.get(pk=feature_flag_id)
    except FeatureFlag.DoesNotExist:
        logger.error(f"FeatureFlag with id {feature_flag_id} does not exist")
        return {
            "status": "error",
            "message": f"FeatureFlag {feature_flag_id} not found",
        }

    try:
        if not feature_flag.auto_off_date:
            logger.info(
                f"FeatureFlag '{feature_flag.key}' (id: {feature_flag_id}) "
                "has no auto_off_date set - skipping"
            )
            return

        if not feature_flag.value:
            logger.info(
                f"FeatureFlag '{feature_flag.key}' (id: {feature_flag_id}) "
                "is already disabled"
            )
            return

        now = timezone.now()
        if feature_flag.auto_off_date > now:
            time_remaining = feature_flag.auto_off_date - now
            logger.info(
                f"FeatureFlag '{feature_flag.key}' (id: {feature_flag_id}) "
                f"not yet expired. Time remaining: {time_remaining}"
            )
            return

        feature_flag.value = False
        feature_flag.save(update_fields=["value"])
        cache.delete("status:registration")

        readable_flag_key = feature_flag.key.replace("_", " ").title()

        logger.info(
            f"Successfully auto-disabled feature flag '{feature_flag.key}' "
            f"(id: {feature_flag_id}) at {now.isoformat()}"
        )

        admin_emails = [email for _, email in settings.ADMINS]
        if admin_emails:
            from comms.tasks import send_mail_task

            send_mail_task.delay(
                subject=f"{readable_flag_key} Auto-Disabled - System Notification",
                message=(
                    f"This is an automated system notification.\n\n"
                    f"Feature Flag: {readable_flag_key}\n"
                    f"Status: Successfully disabled\n"
                    f"Scheduled Disable Time: {feature_flag.auto_off_date.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                    f"Actual Disable Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n\n"
                    f"This feature flag was automatically disabled as scheduled.\n\n"
                    f"Regards,\n"
                    f"VMLC System\n"
                ),
                recipient_list=admin_emails,
            )
            logger.info(
                f"Auto-disable notification sent for '{feature_flag.key}' "
                f"to {len(admin_emails)} admin(s)"
            )

        return

    except Exception as exc:
        logger.exception(
            f"Error disabling feature flag '{feature_flag.key}' "
            f"(id: {feature_flag_id}): {exc}"
        )

        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(
                f"Max retries exceeded for disabling feature flag "
                f"'{feature_flag.key}' (id: {feature_flag_id})"
            )
            return
