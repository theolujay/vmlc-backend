import os
from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("vmlc")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()
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
