#!/bin/bash

# Exit on any error
set -e

# Ensure logs directory exists for all Django services (needed by settings.py)
echo "Ensuring logs directory exists and is owned by 'app' user..."
mkdir -p /home/app/web/logs
chown -R app:app /home/app/web/logs
chmod -R 755 /home/app/web/logs

# Only run setup steps for the main web application (gunicorn)
# Celery workers and flower don't need to run migrations
if [ "$1" = 'gunicorn' ]; then
    echo "Running migrations..."
    python manage.py makemigrations api --noinput
    python manage.py makemigrations --noinput
    python manage.py migrate --noinput

    # This is safer than changing ownership of the entire project directory.
    echo "Ensuring media/staticfiles directories exist and are owned by 'app' user..."
    mkdir -p /home/app/web/staticfiles /home/app/web/media
    chown -R app:app /home/app/web/staticfiles /home/app/web/media

    echo "Running collectstatic..."
    python manage.py collectstatic --noinput
fi

echo "Executing command as 'app' user: $@"
exec gosu app "$@"