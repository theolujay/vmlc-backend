#!/bin/bash

set -euo pipefail

exec gunicorn config.asgi:application \
    --config gunicorn.conf.py