#!/bin/bash

set -euo pipefail

log_info() {
    echo -e "[INFO] $(date -u +"%Y-%m-%dT%H:%M:%SZ") PID=$$ - $1" >&1
}
log_warn() {
    echo -e "[WARN] $(date -u +"%Y-%m-%dT%H:%M:%SZ") PID=$$ - $1" >&1
}
log_error() {
    echo -e "[ERROR] $(date -u +"%Y-%m-%dT%H:%M:%SZ") PID=$$ - $1" >&2
}

cleanup() {
    log_info "Shutting down gracefully..."
    jobs -p | xargs -r kill 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT SIGQUIT SIGHUP


security_check() {
    if [[ "$(id -u)" -eq 0 ]]; then
        log_error "Security violation: Container is running as root user!"
        log_error "This is a serious security risk. Exiting..."
        exit 1 # '1' mark as failure
    fi

    # Verify we're running as the expected non-root user
    local current_user
    current_user=$(whoami)
    if [[ "$current_user" != "verboheit" ]]; then
        log_warn "Running as unexpected user: '$current_user' instead of 'verboheit' user"
    fi

    log_info "Security check passed - running as user: $current_user ($(id))"
}


validate_environment() {
    log_info "Validating environment variables..."

    if [[ -z "${DATABASE_URL:-}" && -n "${DATABASE_URL_FILE:-}" && -f "${DATABASE_URL_FILE}" ]]; then
        log_info "DATABASE_URL not set, reading from ${DATABASE_URL_FILE}"
        export DATABASE_URL=$(cat "${DATABASE_URL_FILE}")
    fi

    # Validate required Django settings
    if [[ -z "${DJANGO_SETTINGS_MODULE:-}" ]]; then
        log_error "DJANGO_SETTINGS_MODULE environment variable is required"
        exit 1
    fi

    # Validate superuser credentials if provided
    # if [[ -n "${SUPERUSER_EMAIL:-}" ]]; then
    #     if [[ ! "${SUPERUSER_EMAIL}" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
    #         log_error "Invalid SUPERUSER_EMAIL format"
    #         exit 1
    #     fi
    # fi

    # Check if running in production and validate critical settings
    if [[ "${DJANGO_SETTINGS_MODULE}" == *"prod"* ]]; then
        local required_prod_vars=("SECRET_KEY" "DATABASE_URL")
        for var in "${required_prod_vars[@]}"; do
            if [[ -z "${!var:-}" ]]; then
                log_error "Production environment requires '$var' to be set"
                exit 1
            fi
        done
    fi
    log_info "Environment validation passed"
}


wait_for_db() {
    log_info "Waiting for database..."
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log_error "DATABASE_URL not set. Cannot start in production."
        exit 1
    fi

    local max_attempts=30
    local attempt=1
    local backoff=2

    until pg_isready -d "$DATABASE_URL" >/dev/null 2>&1; do
        if [[ $attempt -ge $max_attempts ]]; then
            log_error "Database not ready after $max_attempts attempts. Exiting."
            exit 1
        fi
        log_warn "Database not ready, waiting ${backoff}s before retrying..."
        sleep $backoff
        backoff=$(( backoff < 10 ? backoff * 2 : 10 ))
        ((attempt++))
    done

    log_info "Database connection established. Checking health..."

    # Now run Django's system check for critical errors only
    if ! python manage.py check --fail-level CRITICAL; then
        log_error "Django system check failed with critical errors. Exiting."
        exit 1
    fi
}


create_superuser() {
    if [[ -n "${SUPERUSER_EMAIL:-}" ]] && [[ -n "${SUPERUSER_PASSWORD:-}" ]]; then
        log_info "Creating superuser if not exists..."

        # Use python -c to execute a self-contained script. This is more robust than using a heredoc with `manage.py shell`.
        python manage.py shell -c "
import os, sys
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()
email = os.environ.get('SUPERUSER_EMAIL')
password = os.environ.get('SUPERUSER_PASSWORD')

if not email or not password:
    print('Django: Missing superuser credentials, skipping creation.')
elif User.objects.filter(email=email).exists():
    print('Django: Superuser already exists.')
else:
    try:
        User.objects.create_superuser(email=email, password=password)
        print('Superuser created successfully.')
    except (IntegrityError, ValueError) as e:
        print(f'Error creating superuser: {e}', file=sys.stderr)
        sys.exit(1)
"
        log_info "Superuser creation check completed."
    else
        log_info "Superuser credentials not provided, skipping superuser creation"
    fi
}


setup_django_env() {
    # log_info "Setting up Django environment for migrations..."

    # log_info "Running Django system checks..."
    # if ! python manage.py check --deploy --fail-level WARNING; then
    #     if [[ "${DJANGO_SETTINGS_MODULE}" == *"prod"* ]]; then
    #         log_error "Django system checks failed in production mode"
    #         exit 1
    #     else
    #         log_warn "Django system checks found issues (continuing in non-production mode)"
    #     fi
    # fi

    log_info "Applying database migrations..."
    python manage.py migrate --no-input
    log_info "Database migrations completed"
    
    # Static files collection (only in production/staging)
    if [[ "${DJANGO_SETTINGS_MODULE}" == *"prod"* ]] || [[ "${DJANGO_SETTINGS_MODULE}" == *"staging"* ]]; then
        log_info "Setting up directories..."
        mkdir -p /home/verboheit/web/staticfiles
        mkdir -p /home/verboheit/web/media
        log_info "Directories setup completed"

        log_info "Collecting static files..."
        python manage.py collectstatic --no-input --skip-checks
        log_info "Static files collection completed"
    else
        log_info "Skipping static files collection in development mode"
    fi
}

setup_application() {
    # wait_for_db
    setup_django_env
    # create_superuser
}

preflight_check() {
    log_info "Running pre-flight checks..."
    
    # Check if manage.py exists
    if [[ ! -f "manage.py" ]]; then
        log_error "manage.py not found in current directory: $(pwd)"
        exit 1
    fi
    
    # Check if Python can import Django
    if ! python -c "import django" 2>/dev/null; then
        log_error "Django is not installed or not accessible"
        exit 1
    fi
    
    log_info "Pre-flight checks completed"
}

main()  {
    log_info "Starting migration script..."
    log_info "Working directory: $(pwd)"
    log_info "Python executable: $(which python)"
    security_check
    validate_environment
    setup_application
    log_info "Migration complete!"
}

main "$@"
