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

wait_for_migrations() {
    log_info "Checking for database migrations..."
    if python manage.py showmigrations --plan | grep -q '\[ \]'; then
        log_info "Migrations pending. Waiting until complete..."
        local max_attempts=10
        local attempt=1
        local backoff=2

        until ! python manage.py showmigrations --plan | grep -q '\[ \]'; do
            if [[ $attempt -ge $max_attempts ]]; then
                log_error "Migrations not complete after $max_attempts attempts. Exiting."
                exit 1
            fi
            log_warn "Migrations not complete, waiting ${backoff}s before retrying..."
            sleep $backoff
            backoff=$(( backoff < 10 ? backoff * 2 : 10 ))
            ((attempt++))
        done
        log_info "Migrations complete"
    else
        log_info "No migrations pending"
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

check_startup_command() {
    for i in "$@"; do
        if [[ "$i" == "gunicorn" || "daphne" || "hypercorn" || "./scripts/runserver.sh" ]]; then
            echo -e "Starting up ASGI/WSGI server $i"
        elif [[ "$i" == "celery" ]]; then
            echo -e "Starting up celery worker"
        elif [[ "$i" == "python" && "${2:-}" == "manage.py" && "${3:-}" == "runserver" ]]; then
            echo -e "Starting up Django development server"
        fi
    done
}

# Main execution function
main() {
    log_info "Starting app startup entrypoint script..."
    log_info "Command: $*"
    log_info "Working directory: $(pwd)"
    log_info "Python executable: $(which python)"

    security_check
    preflight_check
    wait_for_migrations
    if [[ $# -eq 0 ]]; then
        log_error "No command provided to entrypoint"
        log_info "Usage: entrypoint.sh <command> [args...]"
        exit 1
    fi
    
    log_info "All checks completed successfully"
    log_info "Executing command: $*"
    check_startup_command

    exec "$@"
}

main "$@"
