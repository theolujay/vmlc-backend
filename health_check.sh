#!/bin/bash

# Comprehensive Docker Compose health monitoring script
# Works with the improved compose_up.sh script

set -euo pipefail

# Configuration
readonly SCRIPT_NAME="$(basename "$0")"
readonly CHECK_INTERVAL="${HEALTH_CHECK_INTERVAL:-30}"
readonly MAX_RETRIES="${HEALTH_MAX_RETRIES:-3}"
readonly TIMEOUT="${HEALTH_TIMEOUT:-10}"

# Colors
if [[ -t 1 ]]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[1;33m'
    readonly BLUE='\033[0;34m'
    readonly NC='\033[0m'
else
    readonly RED='' GREEN='' YELLOW='' BLUE='' NC=''
fi

# Logging
log_info() { echo -e "${GREEN}[INFO]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") - $1" >&1; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") - $1" >&1; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") - $1" >&2; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $(date -u +"%Y-%m-%dT%H:%M:%SZ") - $1" >&1; }

# Service-specific health checks
check_web_service() {
    local service_name="$1"
    local port="${2:-8000}"
    
    # Check if container is running
    if ! docker compose ps "$service_name" --format json | jq -e '.[0].State == "running"' >/dev/null 2>&1; then
        return 1
    fi
    
    # Check HTTP endpoint
    local container_ip
    container_ip=$(docker compose ps "$service_name" --format json | jq -r '.[0].Publishers[0].TargetIP // "localhost"' 2>/dev/null || echo "localhost")
    
    if timeout "$TIMEOUT" curl -sf "http://${container_ip}:${port}/v1/health/" >/dev/null 2>&1; then
        return 0
    fi
    
    # Fallback: check if port is accessible
    if timeout "$TIMEOUT" nc -z "$container_ip" "$port" 2>/dev/null; then
        log_warn "Service $service_name port is open but health endpoint failed"
        return 0
    fi
    
    return 1
}

check_database_service() {
    local service_name="$1"
    
    # Check if container is running
    if ! docker compose ps "$service_name" --format json | jq -e '.[0].State == "running"' >/dev/null 2>&1; then
        return 1
    fi
    
    # Try to connect to PostgreSQL
    if docker compose exec -T "$service_name" pg_isready >/dev/null 2>&1; then
        return 0
    fi
    
    return 1
}

check_redis_service() {
    local service_name="$1"
    
    # Check if container is running  
    if ! docker compose ps "$service_name" --format json | jq -e '.[0].State == "running"' >/dev/null 2>&1; then
        return 1
    fi
    
    # Try Redis ping
    if docker compose exec -T "$service_name" redis-cli ping | grep -q "PONG" 2>/dev/null; then
        return 0
    fi
    
    return 1
}

check_celery_worker() {
    local service_name="$1"
    
    # Check if container is running
    if ! docker compose ps "$service_name" --format json | jq -e '.[0].State == "running"' >/dev/null 2>&1; then
        return 1
    fi
    
    # Check if celery worker is responsive
    if docker compose exec -T "$service_name" celery -A config inspect ping >/dev/null 2>&1; then
        return 0
    fi
    
    return 1
}

# Generic health check dispatcher
check_service_health() {
    local service_name="$1"
    local service_type="$2"
    
    case "$service_type" in
        "web"|"django")
            check_web_service "$service_name"
            ;;
        "database"|"postgres"|"db")
            check_database_service "$service_name"
            ;;
        "redis"|"cache")
            check_redis_service "$service_name"
            ;;
        "celery"|"worker")
            check_celery_worker "$service_name"
            ;;
        "generic")
            # Just check if container is running
            docker compose ps "$service_name" --format json | jq -e '.[0].State == "running"' >/dev/null 2>&1
            ;;
        *)
            log_warn "Unknown service type: $service_type for $service_name"
            return 1
            ;;
    esac
}

# Get service status with detailed information
get_service_status() {
    local service_name="$1"
    
    local status_json
    status_json=$(docker compose ps "$service_name" --format json 2>/dev/null || echo "[]")
    
    if [[ "$status_json" == "[]" ]]; then
        echo "not_found"
        return 1
    fi
    
    local state
    state=$(echo "$status_json" | jq -r '.[0].State // "unknown"')
    
    local health
    health=$(echo "$status_json" | jq -r '.[0].Health // "none"')
    
    echo "${state}:${health}"
}

# Monitor all services
monitor_services() {
    local -A service_types=(
        ["web"]="web"
        ["db"]="database"
        ["redis"]="redis"
        ["celery_worker"]="celery"
        ["flower"]="generic"
    )
    
    local failed_services=()
    local warning_services=()
    local healthy_services=()
    
    log_info "Starting comprehensive health check..."
    
    for service in "${!service_types[@]}"; do
        local service_type="${service_types[$service]}"
        local status
        status=$(get_service_status "$service")
        
        if [[ "$status" == "not_found" ]]; then
            log_warn "Service $service not found (may not be running in this environment)"
            continue
        fi
        
        local state="${status%%:*}"
        local health="${status##*:}"
        
        # Check if service is running
        if [[ "$state" != "running" ]]; then
            log_error "Service $service is not running (state: $state)"
            failed_services+=("$service")
            continue
        fi
        
        # Perform service-specific health check
        local attempt=0
        local success=false
        
        while [[ $attempt -lt $MAX_RETRIES ]]; do
            if check_service_health "$service" "$service_type"; then
                success=true
                break
            fi
            
            ((attempt++))
            if [[ $attempt -lt $MAX_RETRIES ]]; then
                log_warn "Health check failed for $service (attempt $attempt/$MAX_RETRIES), retrying..."
                sleep 2
            fi
        done
        
        if [[ "$success" == true ]]; then
            log_success "Service $service is healthy"
            healthy_services+=("$service")
        else
            if [[ "$health" == "healthy" ]]; then
                log_warn "Service $service has mixed health status (Docker: healthy, Custom: failed)"
                warning_services+=("$service")
            else
                log_error "Service $service failed health check after $MAX_RETRIES attempts"
                failed_services+=("$service")
            fi
        fi
    done
    
    # Summary
    echo ""
    log_info "=== Health Check Summary ==="
    log_success "Healthy services (${#healthy_services[@]}): ${healthy_services[*]:-none}"
    
    if [[ ${#warning_services[@]} -gt 0 ]]; then
        log_warn "Warning services (${#warning_services[@]}): ${warning_services[*]}"
    fi
    
    if [[ ${#failed_services[@]} -gt 0 ]]; then
        log_error "Failed services (${#failed_services[@]}): ${failed_services[*]}"
        return 1
    fi
    
    if [[ ${#warning_services[@]} -gt 0 ]]; then
        return 2  # Warning exit code
    fi
    
    return 0
}

# Continuous monitoring mode
continuous_monitor() {
    log_info "Starting continuous monitoring (interval: ${CHECK_INTERVAL}s)"
    log_info "Press Ctrl+C to stop monitoring"
    
    local consecutive_failures=0
    local max_consecutive_failures=3
    
    while true; do
        echo ""
        log_info "Running health check cycle at $(date)"
        
        if monitor_services; then
            consecutive_failures=0
            log_success "All services healthy, waiting ${CHECK_INTERVAL}s for next check..."
        else
            ((consecutive_failures++))
            log_error "Health check failed (consecutive failures: $consecutive_failures)"
            
            if [[ $consecutive_failures -ge $max_consecutive_failures ]]; then
                log_error "Too many consecutive failures ($consecutive_failures), stopping monitoring"
                return 1
            fi
            
            log_warn "Waiting ${CHECK_INTERVAL}s before retry..."
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

# Show detailed service information
show_service_details() {
    local service_name="${1:-}"
    
    if [[ -z "$service_name" ]]; then
        log_info "Available services:"
        docker compose ps --format table
        return 0
    fi
    
    log_info "Detailed information for service: $service_name"
    
    # Basic container info
    echo ""
    log_info "=== Container Status ==="
    docker compose ps "$service_name" --format table
    
    # Resource usage
    echo ""
    log_info "=== Resource Usage ==="
    local container_id
    container_id=$(docker compose ps -q "$service_name" 2>/dev/null || echo "")
    
    if [[ -n "$container_id" ]]; then
        docker stats --no-stream "$container_id" 2>/dev/null || log_warn "Could not get resource statistics"
    else
        log_warn "Container not running, cannot get resource statistics"
    fi
    
    # Recent logs
    echo ""
    log_info "=== Recent Logs (last 20 lines) ==="
    docker compose logs --tail=20 "$service_name" 2>/dev/null || log_warn "Could not retrieve logs"
    
    # Health check logs if available
    echo ""
    log_info "=== Health Check Status ==="
    if docker inspect "$(docker compose ps -q "$service_name" 2>/dev/null)" --format='{{json .State.Health}}' 2>/dev/null | jq -e '.Log' >/dev/null 2>&1; then
        docker inspect "$(docker compose ps -q "$service_name")" --format='{{json .State.Health.Log}}' | jq -r '.[] | "\(.Start): \(.Output)"' | tail -5
    else
        log_info "No health check logs available"
    fi
}

# Wait for services to become healthy
wait_for_healthy() {
    local timeout="${1:-300}"  # Default 5 minutes
    local start_time
    start_time=$(date +%s)
    
    log_info "Waiting for all services to become healthy (timeout: ${timeout}s)"
    
    while true; do
        local current_time
        current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [[ $elapsed -ge $timeout ]]; then
            log_error "Timeout reached ($timeout seconds), services not healthy"
            monitor_services
            return 1
        fi
        
        if monitor_services >/dev/null 2>&1; then
            log_success "All services are healthy (took ${elapsed}s)"
            return 0
        fi
        
        log_info "Services not ready yet, waiting... (${elapsed}s/${timeout}s)"
        sleep 10
    done
}

# Emergency service restart
emergency_restart() {
    local service_name="$1"
    
    log_warn "Performing emergency restart for service: $service_name"
    
    # Try graceful restart first
    if docker compose restart "$service_name"; then
        log_info "Graceful restart successful for $service_name"
        sleep 10
        
        # Check if it's healthy now
        if check_service_health "$service_name" "generic"; then
            log_success "Service $service_name is healthy after restart"
            return 0
        fi
    fi
    
    # Force recreation if graceful restart failed
    log_warn "Graceful restart failed, forcing recreation of $service_name"
    if docker compose up -d --force-recreate "$service_name"; then
        log_info "Force recreation completed for $service_name"
        sleep 15
        
        if check_service_health "$service_name" "generic"; then
            log_success "Service $service_name is healthy after recreation"
            return 0
        fi
    fi
    
    log_error "Emergency restart failed for service $service_name"
    return 1
}

# Usage information
show_usage() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS] [COMMAND] [SERVICE]

Comprehensive health monitoring for Docker Compose services.

COMMANDS:
    check           Run single health check (default)
    monitor         Continuous monitoring mode
    wait            Wait for services to become healthy
    details         Show detailed service information
    restart         Emergency restart for a service

OPTIONS:
    -i, --interval SECONDS    Check interval for monitoring (default: $CHECK_INTERVAL)
    -r, --retries COUNT       Max retries per service (default: $MAX_RETRIES)
    -t, --timeout SECONDS     Timeout per check (default: $TIMEOUT)
    -h, --help               Show this help message

EXAMPLES:
    $SCRIPT_NAME                           # Single health check
    $SCRIPT_NAME monitor                   # Continuous monitoring
    $SCRIPT_NAME wait 300                  # Wait up to 5 minutes for health
    $SCRIPT_NAME details web               # Show details for web service
    $SCRIPT_NAME restart web               # Emergency restart web service

ENVIRONMENT VARIABLES:
    HEALTH_CHECK_INTERVAL     Set monitoring interval
    HEALTH_MAX_RETRIES        Set max retries per service
    HEALTH_TIMEOUT            Set timeout per health check

EXIT CODES:
    0    All services healthy
    1    One or more services failed
    2    One or more services have warnings

EOF
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -i|--interval)
                CHECK_INTERVAL="$2"
                shift 2
                ;;
            -r|--retries)
                MAX_RETRIES="$2"
                shift 2
                ;;
            -t|--timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            -h|--help)
                show_usage
                exit 0
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
    
    # Set command and arguments
    COMMAND="${1:-check}"
    shift || true
    ARGS=("$@")
}

# Main function
main() {
    # Parse arguments
    parse_arguments "$@"
    
    # Check dependencies
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v jq >/dev/null 2>&1; then
        log_error "jq is required but not installed"
        exit 1
    fi
    
    # Execute command
    case "$COMMAND" in
        "check")
            monitor_services
            ;;
        "monitor")
            continuous_monitor
            ;;
        "wait")
            local timeout="${ARGS[0]:-300}"
            wait_for_healthy "$timeout"
            ;;
        "details")
            local service="${ARGS[0]:-}"
            show_service_details "$service"
            ;;
        "restart")
            local service="${ARGS[0]:-}"
            if [[ -z "$service" ]]; then
                log_error "Service name required for restart command"
                exit 1
            fi
            emergency_restart "$service"
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            show_usage
            exit 1
            ;;
    esac
}

# Signal handler
cleanup() {
    log_info "Monitoring stopped by user"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Execute main function
main "$@"
