#!/bin/bash

# Enhanced Docker Compose management script with security and reliability improvements
# Author: DevOps Team
# Version: 2.0

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Script configuration
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly PID_FILE="/tmp/${SCRIPT_NAME}.pid"

# Default configuration - can be overridden by environment variables
readonly DEFAULT_LOG_DIR="./logs/compose"
readonly DEFAULT_ENVIRONMENT="development"
readonly DEFAULT_TIMEOUT=300  # 5 minutes timeout for health checks

# Colors for output (only if terminal supports it)
if [[ -t 1 ]]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[1;33m'
    readonly BLUE='\033[0;34m'
    readonly CYAN='\033[0;36m'
    readonly NC='\033[0m'
else
    readonly RED='' GREEN='' YELLOW='' BLUE='' CYAN='' NC=''
fi

# Global variables
ENVIRONMENT="${COMPOSE_ENV:-$DEFAULT_ENVIRONMENT}"
LOG_DIR="${COMPOSE_LOG_DIR:-$DEFAULT_LOG_DIR}"
TIMEOUT="${COMPOSE_TIMEOUT:-$DEFAULT_TIMEOUT}"
VERBOSE=false
QUIET=false
DRY_RUN=false
FORCE=false
HEALTH_CHECK=true
DETACH=false

# Logging functions with structured output
log_info() {
    [[ "$QUIET" == true ]] && return
    echo -e "${GREEN}[INFO]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") - $1" >&1
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") - $1" >&1
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") - $1" >&2
}

log_debug() {
    [[ "$VERBOSE" == true ]] || return
    echo -e "${BLUE}[DEBUG]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") - $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") - $1" >&1
}

# Signal handlers for graceful cleanup
cleanup() {
    log_info "Received interrupt signal, cleaning up..."
    
    # Remove PID file
    [[ -f "$PID_FILE" ]] && rm -f "$PID_FILE"
    
    # Kill any background jobs
    local jobs
    jobs=$(jobs -p)
    if [[ -n "$jobs" ]]; then
        log_debug "Killing background jobs: $jobs"
        # shellcheck disable=SC2086
        kill $jobs 2>/dev/null || true
        sleep 2
        # Force kill if still running
        # shellcheck disable=SC2086
        kill -9 $jobs 2>/dev/null || true
    fi
    
    log_info "Cleanup completed"
    exit 130  # Standard exit code for SIGINT
}

# Error handler
error_handler() {
    local exit_code=$?
    local line_number=$1
    log_error "Script failed at line $line_number with exit code $exit_code"
    cleanup
    exit $exit_code
}

# Trap signals and errors
trap cleanup SIGINT SIGTERM SIGQUIT
trap 'error_handler ${LINENO}' ERR

# Usage information
show_usage() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS] [COMMAND]

Enhanced Docker Compose management script with security and reliability features.

OPTIONS:
    -e, --environment ENV    Environment to deploy (development|staging|production)
                            Default: $DEFAULT_ENVIRONMENT
    -l, --log-dir DIR       Directory to store logs (default: $DEFAULT_LOG_DIR)
    -t, --timeout SECONDS   Timeout for health checks (default: $DEFAULT_TIMEOUT)
    -v, --verbose           Enable verbose output
    -q, --quiet             Suppress informational output
    -d, --detach           Run in detached mode
    -f, --force            Force rebuild and recreate containers
    --dry-run              Show commands that would be executed without running them
    --no-health-check      Skip health checks after startup
    -h, --help             Show this help message

COMMANDS:
    up          Start services (default)
    down        Stop and remove services
    restart     Restart services
    logs        Show service logs
    status      Show service status
    health      Check service health
    clean       Clean up unused resources

EXAMPLES:
    $SCRIPT_NAME --environment production up
    $SCRIPT_NAME --verbose --force up
    $SCRIPT_NAME down
    $SCRIPT_NAME logs web

ENVIRONMENT VARIABLES:
    COMPOSE_ENV             Set environment (overrides -e)
    COMPOSE_LOG_DIR         Set log directory (overrides -l)
    COMPOSE_TIMEOUT         Set timeout (overrides -t)

EOF
}

# Validation functions
validate_environment() {
    local env="$1"
    case "$env" in
        development|staging|production)
            return 0
            ;;
        *)
            log_error "Invalid environment: $env. Must be one of: development, staging, production"
            return 1
            ;;
    esac
}

validate_dependencies() {
    log_debug "Validating dependencies..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        return 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running or not accessible"
        return 1
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed or not accessible"
        return 1
    fi
    
    log_debug "Dependencies validation passed"
}

validate_compose_files() {
    log_debug "Validating compose files..."
    
    local base_file="compose.yml"
    if [[ ! -f "$base_file" ]]; then
        log_error "Base compose file not found: $base_file"
        return 1
    fi
    
    # Check environment-specific overrides
    case "$ENVIRONMENT" in
        development)
            if [[ -f "compose.override.yml" ]]; then
                log_debug "Found development override file"
            fi
            ;;
        staging)
            local staging_file="compose.staging.yml"
            if [[ ! -f "$staging_file" ]]; then
                log_error "Staging compose file not found: $staging_file"
                return 1
            fi
            ;;
        production)
            # Production uses only the base file for security
            log_debug "Using base compose file for production"
            ;;
    esac
    
    log_debug "Compose files validation passed"
}

# Setup logging directory and files
setup_logging() {
    log_debug "Setting up logging..."
    
    # Create log directory with secure permissions
    if [[ ! -d "$LOG_DIR" ]]; then
        mkdir -p "$LOG_DIR"
        chmod 750 "$LOG_DIR"
    fi
    
    # Generate log file names with timestamp
    local timestamp
    timestamp=$(date +"%Y%m%d_%H%M%S")
    readonly COMPOSE_LOG_FILE="$LOG_DIR/compose_${ENVIRONMENT}_${timestamp}.log"
    readonly ERROR_LOG_FILE="$LOG_DIR/errors_${ENVIRONMENT}_${timestamp}.log"
    readonly FULL_LOG_FILE="$LOG_DIR/full_${ENVIRONMENT}_${timestamp}.log"
    
    # Create log files with secure permissions
    for logfile in "$COMPOSE_LOG_FILE" "$ERROR_LOG_FILE" "$FULL_LOG_FILE"; do
        touch "$logfile"
        chmod 640 "$logfile"
    done
    
    log_debug "Logging setup completed"
    log_info "Logs will be written to: $LOG_DIR"
}

# Build compose command based on environment
build_compose_command() {
    local action="$1"
    local compose_cmd=""
    local compose_files=""
    local env_file=""

    # Determine compose files and env file based on environment
    case "$ENVIRONMENT" in
        development)
            env_file=".env"
            compose_files="-f compose.yml"
            if [[ -f "compose.override.yml" ]]; then
                compose_files+=" -f compose.override.yml"
            fi
            ;;
        staging)
            env_file="staging.env"
            compose_files="-f compose.yml -f compose.staging.yml"
            ;;
        production)
            env_file="prod.env"
            compose_files="-f compose.yml -f compose.prod.yml"
            ;;
    esac

    # Validate that the required env file exists
    if [[ ! -s "$env_file" ]]; then
        log_error "Required environment file '$env_file' not found or is empty!"
        return 1
    fi

    # Construct the base command
    compose_cmd="docker compose --env-file $env_file $compose_files"

    # Add action-specific options
    case "$action" in
        up)
            compose_cmd+=" up"
            [[ "$FORCE" == true ]] && compose_cmd+=" --build --force-recreate"
            [[ "$DETACH" == true ]] && compose_cmd+=" --detach"
            ;;
        down)
            compose_cmd+=" down"
            [[ "$FORCE" == true ]] && compose_cmd+=" --volumes --remove-orphans"
            ;;
        restart)
            compose_cmd+=" restart"
            ;;
        logs)
            compose_cmd+=" logs --follow --tail=100"
            ;;
        *)
            compose_cmd+=" $action"
            ;;
    esac
    
    echo "$compose_cmd"
}

# Enhanced error filtering with context
filter_logs() {
    local input_file="$1"
    local output_file="$2"
    
    # Enhanced error keywords including context
    local error_patterns="ERROR|CRITICAL|FATAL|Exception|Traceback|failed|Failed|FAILED|Cannot|refused|denied|timeout|Timeout|TIMEOUT|panic|Panic|PANIC|segfault|core dumped|Out of memory|Permission denied|Connection refused|No such file|command not found"
    
    # Filter with 2 lines of context before and after each match
    grep -E -i -A 2 -B 2 "$error_patterns" "$input_file" > "$output_file" 2>/dev/null || true
}

# Service health check with timeout
check_service_health() {
    local service="$1"
    local timeout="${2:-60}"
    local attempt=0
    local max_attempts=$((timeout / 5))
    
    log_info "Checking health of service: $service"
    
    while [[ $attempt -lt $max_attempts ]]; do
        local health_status
        health_status=$(docker compose ps --format json "$service" 2>/dev/null | jq -r '.[0].Health // "none"' 2>/dev/null || echo "unknown")
        
        case "$health_status" in
            "healthy")
                log_success "Service $service is healthy"
                return 0
                ;;
            "unhealthy")
                log_error "Service $service is unhealthy"
                return 1
                ;;
            "starting"|"none"|"unknown")
                log_debug "Service $service health status: $health_status (attempt $((attempt + 1))/$max_attempts)"
                sleep 5
                ((attempt++))
                ;;
            *)
                log_warn "Service $service has unknown health status: $health_status"
                sleep 5
                ((attempt++))
                ;;
        esac
    done
    
    log_error "Health check timeout for service: $service"
    return 1
}

# Check health of all services
check_all_services_health() {
    [[ "$HEALTH_CHECK" != true ]] && return 0
    
    log_info "Performing health checks on all services..."
    
    # Get list of running services
    local services
    services=$(docker compose ps --services 2>/dev/null || echo "")
    
    if [[ -z "$services" ]]; then
        log_warn "No services found to check"
        return 0
    fi
    
    local failed_services=()
    while IFS= read -r service; do
        [[ -z "$service" ]] && continue
        if ! check_service_health "$service" 30; then
            failed_services+=("$service")
        fi
    done <<< "$services"
    
    if [[ ${#failed_services[@]} -gt 0 ]]; then
        log_error "Health check failed for services: ${failed_services[*]}"
        return 1
    fi
    
    log_success "All services are healthy"
    return 0
}

# Main compose execution with enhanced logging
execute_compose_command() {
    local action="$1"
    local compose_cmd
    compose_cmd=$(build_compose_command "$action")
    
    log_info "Environment: $ENVIRONMENT"
    log_info "Executing: $compose_cmd"
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "DRY RUN: Would execute: $compose_cmd"
        return 0
    fi
    
    # Create a named pipe for real-time log processing
    local log_pipe
    log_pipe=$(mktemp -u)
    mkfifo "$log_pipe"
    
    # Start log processor in background
    {
        while IFS= read -r line; do
            echo "$line" | tee -a "$FULL_LOG_FILE"
            # Check for errors and write to error log
            if echo "$line" | grep -E -i "ERROR|CRITICAL|FATAL|Exception|failed|Cannot|refused" >/dev/null 2>&1; then
                echo "$line" >> "$ERROR_LOG_FILE"
            fi
        done < "$log_pipe"
    } &
    local log_processor_pid=$!
    
    # Execute compose command with full logging
    local exit_code=0
    if [[ "$VERBOSE" == true ]]; then
        # shellcheck disable=SC2086
        $compose_cmd 2>&1 | tee "$log_pipe" || exit_code=$?
    else
        # shellcheck disable=SC2086
        $compose_cmd >"$log_pipe" 2>&1 || exit_code=$?
    fi
    
    # Close pipe and wait for log processor
    exec 3>"$log_pipe"
    exec 3>&-
    wait $log_processor_pid 2>/dev/null || true
    rm -f "$log_pipe"
    
    return $exit_code
}

# Process command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -l|--log-dir)
                LOG_DIR="$2"
                shift 2
                ;;
            -t|--timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -q|--quiet)
                QUIET=true
                shift
                ;;
            -d|--detach)
                DETACH=true
                shift
                ;;
            -f|--force)
                FORCE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --no-health-check)
                HEALTH_CHECK=false
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            --)
                shift
                break
                ;;
            -*)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
            *)
                break
                ;;
        esac
    done
    
    # Set action (default to 'up')
    ACTION="${1:-up}"
    shift || true
    
    # Additional arguments
    EXTRA_ARGS=("$@")
}

# Check for another instance
check_single_instance() {
    if [[ -f "$PID_FILE" ]]; then
        local old_pid
        old_pid=$(cat "$PID_FILE")
        if kill -0 "$old_pid" 2>/dev/null; then
            log_error "Another instance is already running (PID: $old_pid)"
            exit 1
        else
            log_warn "Removing stale PID file"
            rm -f "$PID_FILE"
        fi
    fi
    
    echo $ > "$PID_FILE"
}

# Main execution function
main() {
    log_info "Starting $SCRIPT_NAME v2.0"
    
    # Parse command line arguments
    parse_arguments "$@"
    
    # Validate inputs
    validate_environment "$ENVIRONMENT"
    
    # Check for single instance
    check_single_instance
    
    # Validate dependencies and files
    validate_dependencies
    validate_compose_files
    
    # Setup logging
    setup_logging
    
    log_info "Starting Docker Compose operation: $ACTION"
    log_info "Environment: $ENVIRONMENT"
    log_info "Log directory: $LOG_DIR"
    
    # Execute the main command
    local exit_code=0
    if execute_compose_command "$ACTION"; then
        log_success "Docker Compose $ACTION completed successfully"
        
        # Perform health checks for 'up' action
        if [[ "$ACTION" == "up" ]] && [[ "$DETACH" == true ]]; then
            if ! check_all_services_health; then
                log_error "Some services failed health checks"
                exit_code=1
            fi
        fi
    else
        exit_code=$?
        log_error "Docker Compose $ACTION failed with exit code $exit_code"
    fi
    
    # Summary
    echo ""
    if [[ $exit_code -eq 0 ]]; then
        log_success "Operation completed successfully!"
        
        # Check if error log has content
        if [[ -s "$ERROR_LOG_FILE" ]]; then
            log_warn "Some errors were logged during execution"
            log_info "Error log: $ERROR_LOG_FILE"
        else
            log_debug "No errors detected, removing empty error log"
            rm -f "$ERROR_LOG_FILE"
        fi
    else
        log_error "Operation failed!"
        log_info "Full logs: $FULL_LOG_FILE"
        log_info "Error logs: $ERROR_LOG_FILE"
    fi
    
    # Cleanup
    rm -f "$PID_FILE"
    
    exit $exit_code
}

# Execute main function with all arguments
main "$@"