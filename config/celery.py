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
    "update-candidate-dashboard_cache_every-30-minutes": {
        "task": "update_candidate_dashboard_cache_task",
        "schedule": crontab(minute="0,15"),
    },
    "update-exam-statuses-task": {
        "task": "update_exam_statuses_task",
        "schedule": crontab(minute="*/30"),
    },
}
