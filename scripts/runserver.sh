#!/bin/bash

set -euo pipefail

exec gunicorn config.asgi:application \
    -k uvicorn_worker.UvicornWorker \
    -w 2 \
    -b 0.0.0.0:8000 \
    --timeout 60 \
    --graceful-timeout 30 \
    --max-requests 2000 \
    --max-requests-jitter 100 \
    --threads 2 \
    --error-logfile - \
    --capture-output
