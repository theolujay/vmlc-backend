#!/bin/bash

set -euo pipefail

exec gunicorn config.asgi:application \
    --config config/gunicorn.conf.py