#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Configuration
LOG_FILE="${LOG_FILE:-build_errors.log}"
version=$1
no_cache=$2
push=$3

# Function to run a command, log only errors, and show progress
run_with_clean_logging() {
    local command="$1"
    
    # Send STDOUT (normal output) to the console
    # Send STDERR (errors) to the log file and also to the console with a red prefix
    # The eval is necessary to handle the command as a single string
    eval "$command" 2> >(tee -a "$LOG_FILE" >&2)
}

# --- Main script logic ---

# Initialize log file with a new session header
echo "===== Docker Build Session Started at $(date) =====" | tee "$LOG_FILE"

# Main build logic using case statements
case "${version:-}" in
    "")
        echo "No version provided - building vmlc-backend with 'latest'..."
        run_with_clean_logging "docker build -t vmlc-backend:latest ."
        echo "Built as 'vmlc-backend:latest'"
        ;;
    *)
        # Version provided - check cache option
        if [[ "$no_cache" == "nc" ]]; then
            echo "Building vmlc-backend v$version with no cache"
            run_with_clean_logging "docker build -t vmlc-backend:$version . --no-cache"
        else
            echo "Building v$version with cache"
            run_with_clean_logging "docker build -t vmlc-backend:$version ."
        fi
        
        # Capture the exit code of the last run_with_clean_logging command
        if [ $? -eq 0 ]; then
            echo "Built successfully. Now tagging for repo..."
            run_with_clean_logging "docker tag vmlc-backend:$version theolujay/vmlc-backend:$version"
            
            # Check push option
            if [[ "$push" == "p" ]]; then
                echo "Pushing v$version to repo: theolujay/vmlc-backend"
                run_with_clean_logging "docker push theolujay/vmlc-backend:$version"
                echo "Pushed to repo!"
            else
                echo "Not pushing to repo."
            fi
        else
            echo "Build failed!"
            echo "===== Build Failed at $(date) =====" >> "$LOG_FILE"
            exit 1
        fi
        ;;
esac

echo "===== Docker Build Session Completed at $(date) =====" | tee -a "$LOG_FILE"

# Final check for errors in the log file
if [ -s "$LOG_FILE" ]; then
    echo ""
    echo "⚠️ Some errors were logged during build. Check the log file for details:"
    echo "📄 $LOG_FILE"
else
    echo ""
    echo "✅ Build completed successfully with no errors!"
    rm -f "$LOG_FILE" # Remove the log file if no errors
fi
