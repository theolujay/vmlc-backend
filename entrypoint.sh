#!/bin/bash

set -e

echo "Ensuring logs directory exists and is owned by 'app' user..."
mkdir -p /home/app/web/logs

touch /home/app/web/logs/vmlc_api.log
chown -R app:app /home/app/web/logs
chmod -R 755 /home/app/web/logs

if [ "$1" = 'gunicorn' ]; then
    echo "Running migrations..."
    python manage.py makemigrations api --noinput
    python manage.py makemigrations --noinput
    python manage.py migrate --noinput

    echo "Ensuring media/staticfiles directories exist and are owned by 'app' user..."
    mkdir -p /home/app/web/staticfiles /home/app/web/media
    chown -R app:app /home/app/web/staticfiles /home/app/web/media

    echo "Running collectstatic..."
    python manage.py collectstatic --noinput
fi

echo "Executing command as 'app' user: $@"
exec gosu app "$@"