import os

bind = f"0.0.0.0:{os.getenv("PORT", "8000")}"
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
worker_class = "workers.UvicornWorker"

timeout = 60
graceful_timeout = 30

max_requests = 2000
max_requests_jitter = 100

threads = 2

accessing = "-"
errorlog = "-"
capture_output = True
loglevel = "info"
