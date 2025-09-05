#!/bin/bash

set -e

# Function for logging with timestamps
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

wait_for_db() {
    log "Waiting for database to be ready..."
    python -c "
import os, time, psycopg
from urllib.parse import urlparse

url = urlparse(os.environ['DATABASE_URL'])
for i in range(30):
    try:
        conn = psycopg.connect(
            host=url.hostname,
            port=url.port or 5432,
            user=url.username,
            password=url.password,
            dbname=url.path[1:],
            connect_timeout=1
        )
        conn.close()
        print('Database is ready!')
        break
    except Exception as e:
        print(f'Database not ready, waiting... ({i+1}/30) - {e}')
        time.sleep(2)
else:
    print('Database connection timeout!')
    exit(1)
"
}

# Create superuser if credentials are provided
create_superuser() {
    if [ -n "${SUPERUSER_EMAIL:-}" ] && [ -n "${SUPERUSER_PASSWORD:-}" ]; then
        log "Creating superuser..."
        gosu app python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='$SUPERUSER_EMAIL').exists():
    User.objects.create_superuser('$SUPERUSER_EMAIL', '$SUPERUSER_PASSWORD')
    print('Superuser created')
else:
    print('Superuser already exists')
"
    fi
}

# Function to handle Django setup, containing the repeated logic
setup_django_env() {
    log "Setting up Django environment..."
    log "Running migrations..."
    gosu app python manage.py makemigrations api --noinput
    gosu app python manage.py makemigrations --noinput
    gosu app python manage.py migrate --noinput

    log "Collecting static files..."
    gosu app python manage.py collectstatic --noinput --clear
}

# Ensure required directories exist
log "Setting up application directories..."
mkdir -p /home/app/web/staticfiles /home/app/web/media

# Only change ownership if running as root
if [ "$(id -u)" = "0" ]; then
    chown -R app:app /home/app/web/staticfiles /home/app/web/media
fi

case "$1" in
    'gunicorn')
        log "Setting up for production (gunicorn)..."
        if [ -n "${DATABASE_URL:-}" ]; then
            wait_for_db
            setup_django_env
            create_superuser
        fi
        ;;
    'python')
        if [[ "$2" = 'manage.py' && "$3" = 'runserver' ]]; then
            log "Setting up for development (runserver)..."
            setup_django_env
            create_superuser
        fi
        ;;
    *)
        log "Skipping Django setup for special command."
        ;;
esac

log "Starting application as 'app' user: $*"
exec gosu app "$@"
