#!/bin/bash

set -e

# Function for logging with timestamps
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Ensure required directories exist
log "Setting up application directories..."
mkdir -p /home/app/web/staticfiles /home/app/web/media

# Only change ownership if running as root
if [ "$(id -u)" = "0" ]; then
    chown -R app:app /home/app/web/staticfiles /home/app/web/media
fi

if [ "$1" = 'gunicorn' ]; then
    log "Running Django setup..."
    
    # Wait for database to be ready (if DATABASE_URL is set)
    if [ -n "$DATABASE_URL" ]; then
        log "Waiting for database to be ready..."
        python -c "
import os, time, psycopg2
from urllib.parse import urlparse

url = urlparse(os.environ['DATABASE_URL'])
for i in range(30):
    try:
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port or 5432,
            user=url.username,
            password=url.password,
            database=url.path[1:],
            connect_timeout=1
        )
        conn.close()
        print('Database is ready!')
        break
    except:
        print(f'Database not ready, waiting... ({i+1}/30)')
        time.sleep(2)
else:
    print('Database connection timeout!')
    exit(1)
"
    fi

    log "Running migrations..."
    python manage.py makemigrations api --noinput
    python manage.py makemigrations --noinput
    python manage.py migrate --noinput

    log "Collecting static files..."
    python manage.py collectstatic --noinput --clear

    # Optional: Create superuser if credentials are provided
    if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
        log "Creating superuser..."
        python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='$DJANGO_SUPERUSER_EMAIL').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created')
else:
    print('Superuser already exists')
"
    fi
fi

log "Starting application as 'app' user: $*"
exec gosu app "$@"