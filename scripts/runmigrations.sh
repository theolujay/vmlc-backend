#!/bin/bash

set -euo pipefail

if [ -f "$SECRET_KEY_FILE" ]; then
    export SECRET_KEY=$(cat "$SECRET_KEY_FILE")
fi

if [ -f "$DATABASE_URL_FILE" ]; then
    export DATABASE_URL=$(cat "$DATABASE_URL_FILE")
fi

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
        exit 1
    fi

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

    if [[ -z "${DJANGO_SETTINGS_MODULE:-}" ]]; then
        log_error "DJANGO_SETTINGS_MODULE environment variable is required"
        exit 1
    fi

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
        log_error "DATABASE_URL not set. Cannot start."
        exit 1
    fi

    local max_attempts=30
    local attempt=1
    local backoff=2

    # Wait for pg_isready first
    until pg_isready -d "$DATABASE_URL" >/dev/null 2>&1; do
        if [[ $attempt -ge $max_attempts ]]; then
            log_error "Database not ready after $max_attempts attempts. Exiting."
            exit 1
        fi
        log_warn "Database not ready (attempt $attempt/$max_attempts), waiting ${backoff}s..."
        sleep $backoff
        backoff=$(( backoff < 10 ? backoff * 2 : 10 ))
        ((attempt++))
    done

    log_info "Database responds to pg_isready. Verifying full connectivity..."
    
    # Additional check: try to actually connect and run a query
    attempt=1
    backoff=2
    until python -c "
import django
django.setup()
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    print('Database connection verified')
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
" 2>&1; do
        if [[ $attempt -ge 10 ]]; then
            log_error "Database connection verification failed after 10 attempts"
            exit 1
        fi
        log_warn "Database connection test failed (attempt $attempt/10), waiting ${backoff}s..."
        sleep $backoff
        backoff=$(( backoff < 8 ? backoff * 2 : 8 ))
        ((attempt++))
    done

    log_info "Database connection fully verified. Running system check..."

    # Run Django's system check for critical errors only
    if ! python manage.py check --fail-level CRITICAL; then
        log_error "Django system check failed with critical errors. Exiting."
        exit 1
    fi
    
    log_info "Database is ready and healthy"
}


setup_django_env() {
    log_info "Applying database migrations..."
    
    # Show migration plan first for debugging
    if ! python manage.py showmigrations --plan; then
        log_error "Failed to show migration plan"
        exit 1
    fi
    
    # Run migrations with verbose output
    if ! python manage.py migrate --no-input --verbosity 2; then
        log_error "Database migrations failed"
        exit 1
    fi
    
    log_info "Database migrations completed successfully"
    
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
    wait_for_db
    setup_django_env
}

preflight_check() {
    log_info "Running pre-flight checks..."
    
    if [[ ! -f "manage.py" ]]; then
        log_error "manage.py not found in current directory: $(pwd)"
        exit 1
    fi
    
    if ! python -c "import django" 2>/dev/null; then
        log_error "Django is not installed or not accessible"
        exit 1
    fi
    
    log_info "Pre-flight checks completed"
}

main()  {
    log_info "=== Starting migration script ==="
    log_info "Working directory: $(pwd)"
    log_info "Python executable: $(which python)"
    log_info "Python version: $(python --version)"
    
    security_check
    validate_environment
    preflight_check
    setup_application
    
    log_info "=== Migration completed successfully! ==="
}

main "$@"