import os
from celery import Celery
from celery.schedules import crontab
from django.apps import apps
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pycparser")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.docker_dev")

app = Celery("vmlc-backend")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(lambda: [n.name for n in apps.get_app_configs()])

app.conf.beat_schedule = {
    "update-staff-dashboard-cache-every-30-minutes": {
        "task": "update_staff_dashboard_cache_task",
        "schedule": crontab(minute="0,15"),
    },
    "notify-prereg-users-every-4-days": {
        "task": "notify_prereg_users_via_whatsapp_task",
        "schedule": crontab(minute=0, hour=10, day_of_month="*/4"),
    },
    "generate-stats-overview-every-5-minutes": {
        "task": "generate_stats_overview_task",
        "schedule": crontab(minute="*/5"),
    },
    "check-exam-status-transitions-every-minute": {
        "task": "check_exam_status_transitions_task",
        "schedule": crontab(minute="*"),
    },
}
