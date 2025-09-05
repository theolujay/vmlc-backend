from celery import Celery

app = Celery("vmlc-backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
