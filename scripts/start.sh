#!/bin/bash

set -e

exec gunicorn config.wsgi:application \
--bind 0.0.0.0:8000 \
--workers 4 \
--max-requests 1200 \
--max-requests-jitter 50 \
--preload \
--timeout 30