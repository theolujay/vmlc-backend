#!/bin/bash

set -euo pipefail # Exit on error, undefined variables, or pipe failures

# Color codes for better logging readability (if terminal supports it)
if [[ -t 1 ]]; then # checks if stdout is connected to a terminal. '1' is stdout file descriptor
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") PID=$$ - $1" >&1 # The Z means “Zulu time”, which is just UTC.
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") PID=$$ - $1" >&1 # '1' is stdout file descriptor
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") PID=$$ - $1" >&2 # '2' is stderr file descriptor
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

    # Validate required Django settings
    if [[ -z "${DJANGO_SETTINGS_MODULE:-}" ]]; then
        log_error "DJANGO_SETTINGS_MODULE environment variable is required"
        exit 1
    fi

    # Validate superuser credentials if provided
    if [[ -n "${SUPERUSER_EMAIL:-}" ]]; then
        if [[ ! "${SUPERUSER_EMAIL}" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
            log_error "Invalid SUPERUSER_EMAIL format"
            exit 1
        fi
    fi

    # Check if running in production and validate critical settings
    if [[ "${DJANGO_SETTINGS_MODULE}" == *"prod"* ]]; then
        local required_prod_vars=("SECRET_KEY" "DATABASE_URL" "ALLOWED_HOSTS")
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
    log_info "Setting up Django environment..."
    
    # Run Django system checks first
    log_info "Running Django system checks..."
    if ! python manage.py check --deploy --fail-level WARNING; then
        if [[ "${DJANGO_SETTINGS_MODULE}" == *"prod"* ]]; then
            log_error "Django system checks failed in production mode"
            exit 1
        else
            log_warn "Django system checks found issues (continuing in non-production mode)"
        fi
    fi
    
    # Database migrations
    log_info "Checking for database migrations..."
    if python manage.py showmigrations --plan | grep -q '\[ \]'; then
        log_info "Running pending database migrations..."
        python manage.py makemigrations
        python manage.py migrate --no-input
        log_info "Database migrations completed"
    else
        log_info "No pending migrations found"
    fi
    
    # Static files collection (only in production/staging)
    if [[ "${DJANGO_SETTINGS_MODULE}" == *"prod"* ]] || [[ "${DJANGO_SETTINGS_MODULE}" == *"staging"* ]]; then
        log_info "Setting up directories..."
        mkdir -p /home/verboheit/web/staticfiles
        mkdir -p /home/verboheit/web/media
        log_info "Directories setup completed"
        log_info "Collecting static files..."
        python manage.py collectstatic --no-input --clear
        log_info "Static files collection completed"
    else
        log_info "Skipping static files collection in development mode"
    fi
}

setup_application() {
    if [[ "$1" == "opentelemetry-instrument" ]]; then
        local command="$6"
    else
        local command="$1"
    fi
    
    local should_setup=false
    
    case "$command" in
        'gunicorn'|'daphne'|'hypercorn' | './scripts/runserver.sh')
            log_info "Setting up for ASGI/WSGI server ($command)..."
            should_setup=true
            ;;
        'python')
            if [[ "${2:-}" == 'manage.py' && "${3:-}" == 'runserver' ]]; then
                log_info "Setting up for Django development server..."
                should_setup=true
            fi
            ;;
        'celery')
            log_info "Setting up for Celery worker..."
            # Celery workers need database access for some tasks
            wait_for_db
            ;;
        *)
            log_info "Skipping Django setup for command: $command"
            ;;
    esac
    
    if [[ "$should_setup" == true ]]; then
        wait_for_db
        setup_django_env
        create_superuser
    fi
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

# Main execution function
main() {
    log_info "Starting secure entrypoint script..."
    log_info "Command: $*"
    log_info "Working directory: $(pwd)"
    log_info "Python executable: $(which python)"
    
    # Run all security and validation checks
    security_check
    validate_environment
    preflight_check
    
    # Handle special case of no arguments
    if [[ $# -eq 0 ]]; then
        log_error "No command provided to entrypoint"
        log_info "Usage: entrypoint.sh <command> [args...]"
        exit 1
    fi
    
    # Setup application based on command
    setup_application "$@"
    
    log_info "All checks completed successfully"
    log_info "Executing command: $*"
    
    # Execute the command with all arguments
    exec "$@"
}

# Call main function with all script arguments
main "$@"
