import os
from celery import Celery
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
        "schedule": 1800.0,
        "args": (),
    },
    "update-candidate-ranking-cache-every-30-minutes": {
        "task": "update_candidate_ranking_cache_task",
        "schedule": 1800.0,
    },
}
