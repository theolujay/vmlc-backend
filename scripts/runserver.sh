#!/bin/bash

set -e

exec gunicorn config.wsgi:application \
--bind 0.0.0.0:8000 \
--workers 2 \
--timeout 30