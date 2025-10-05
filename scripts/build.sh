#!/bin/bash
#
# Usage:
#   ./script.sh [version] [cache_option] [push_option]
#
# Arguments:
#   version        Optional. Image version tag. Defaults to 'latest' if omitted.
#   cache_option   Optional. Use 'nc' to disable Docker build cache.
#   push_option    Optional. Use 'p' to build multi-arch image and push to Docker Hub.
#
# Examples:
#   ./script.sh                 # Build ghcr.io/verboheit/vmlc-backend:latest with cache
#   ./script.sh 1.0             # Build ghcr.io/verboheit/vmlc-backend:1.0 with cache
#   ./script.sh 1.0 nc          # Build ghcr.io/verboheit/vmlc-backend:1.0 with --no-cache
#   ./script.sh "" "" p         # Build & push ghcr.io/verboheit/vmlc-backend:latest
#   ./script.sh 1.0 "" p        # Build & push ghcr.io/verboheit/vmlc-backend:1.0
#   ./script.sh 1.0 nc p        # Build & push ghcr.io/verboheit/vmlc-backend:1.0 (no cache)

set -e

# Configuration
LOG_FILE="${LOG_FILE:-build_errors.log}"
ERROR_KEYWORDS="ERROR|CRITICAL|Exception|Traceback|failed|Cannot|refused"
FALSE_POSITIVE_KEYWORDS="update-alternatives: warning"
version=$1
no_cache=$2
push=$3

# Function to run a command, log only errors, and show progress
run_with_clean_logging() {
    local command="$1"
    local tmp_log=$(mktemp)
    
    # Run the command, teeing stderr to a temporary file and also to the console
    if eval "$command" 2> >(tee "$tmp_log" >&2); then
        # Command was successful, filter for errors and append to the main log
        grep -E -i "$ERROR_KEYWORDS" "$tmp_log" >> "$LOG_FILE" || true
    else
        # Command failed, append the entire stderr to the main log
        cat "$tmp_log" >> "$LOG_FILE"
        rm -f "$tmp_log"
        return 1
    fi

    # Clean up the temporary log file
    rm -f "$tmp_log"
}

# --- Main script logic ---

# Initialize log file with a new session header
echo "===== Docker Build Session Started at $(date) =====" > "$LOG_FILE"

# Main build logic using case statements
case "${push:-}" in
    "")
        case "${version:-}" in
            "")
                echo "No version provided - building vmlc-backend with 'latest'..."
                if ! run_with_clean_logging "docker build --target production -t ghcr.io/verboheit/vmlc-backend:latest ."; then
                    echo "Build failed!"
                    echo "===== Build Failed at $(date) =====" >> "$LOG_FILE"
                    exit 1
                fi
                echo "Built as 'ghcr.io/verboheit/vmlc-backend:latest'"
                ;;
            *)
                # Version provided - check cache option
                if [[ "$no_cache" == "nc" ]]; then
                    echo "Building vmlc-backend v$version with no cache"
                    if ! run_with_clean_logging "docker build --target production -t ghcr.io/verboheit/vmlc-backend:$version . --no-cache"; then
                        echo "Build failed!"
                        echo "===== Build Failed at $(date) =====" >> "$LOG_FILE"
                        exit 1
                    fi
                else
                    echo "Building v$version with cache"
                    if ! run_with_clean_logging "docker build --target production -t ghcr.io/verboheit/vmlc-backend:$version ."; then
                        echo "Build failed!"
                        echo "===== Build Failed at $(date) =====" >> "$LOG_FILE"
                        exit 1
                    fi
                fi
                ;;
        esac
        ;;
    "p")
        case "${version:-}" in
            "")
                echo "Building then pushing vlatest to repo: ghcr.io/verboheit/vmlc-backend"
                if ! run_with_clean_logging "docker build --target production -t ghcr.io/verboheit/vmlc-backend:latest --push ."; then
                    echo "Build then push failed!"
                    echo "===== Build Then Push Failed at $(date) =====" >> "$LOG_FILE"
                    exit 1
                fi
                ;;
            *)
                echo "Building then pushing v$version to repo: ghcr.io/verboheit/vmlc-backend"
                if ! run_with_clean_logging "docker build --target production -t ghcr.io/verboheit/vmlc-backend:$version --push ."; then
                    echo "Build then push failed!"
                    echo "===== Build Then Push Failed at $(date) =====" >> "$LOG_FILE"
                    exit 1
                fi
                ;;
        esac
        ;;
esac

echo "===== Docker Build Session Completed at $(date) =====" | tee -a "$LOG_FILE"

# Final check for errors in the log file
if [ $(grep -v -E "$FALSE_POSITIVE_KEYWORDS" "$LOG_FILE" | grep -v -E "Docker Build Session" | wc -l) -eq 0 ]; then
    echo ""
    echo "✅ Build completed successfully with no errors!"
    rm -f "$LOG_FILE" # Remove the log file if no errors
else
    echo ""
    echo "⚠️ Some errors were logged during build. Check the log file for details:"
    echo "📄 $LOG_FILE"
fi
