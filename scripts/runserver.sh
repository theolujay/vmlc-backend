#!/bin/bash

set -euo pipefail

# Run gunicorn with uvicorn workers
exec gunicorn config.asgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --threads 2 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    --capture-output
