#!/bin/bash

# Configuration
LOG_FILE="${1:-compose_errors.log}"
# Keywords to filter for in stderr. Add or remove as needed.
ERROR_KEYWORDS="ERROR|CRITICAL|Exception|Traceback|failed|Cannot|refused"

# Clean start
if [ -f "$LOG_FILE" ]; then
    rm "$LOG_FILE"
fi

echo "===== Start of Docker Compose at $(date) ======" | tee -a "$LOG_FILE"

# Run docker compose.
# Pipe stderr through a filter to capture only lines containing error-related keywords.
# The `stdbuf -oL` command is used to ensure that the output is line-buffered,
# so we see errors in real-time.
# We use a process substitution to tee the filtered output to the log file and to the console's stderr.
docker compose up --build 2> >(stdbuf -oL grep -E -i "$ERROR_KEYWORDS" | tee -a "$LOG_FILE" >&2)

COMPOSE_EXIT_CODE=$?

echo "===== End of Docker Compose at $(date) ======" | tee -a "$LOG_FILE"

# Check the exit code and provide summary
if [ $COMPOSE_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Docker Compose completed successfully!"
    # Check if the log file (minus the start/end lines) is empty.
    if [ $(grep -v -E "Start of Docker Compose|End of Docker Compose" "$LOG_FILE" | wc -l) -eq 0 ]; then
        echo "No critical errors were logged."
        echo "Cleaning up log file...."
        rm "$LOG_FILE"
    else
        echo "Potential errors logged to: $LOG_FILE"
    fi
else
    echo ""
    echo "❌ Docker Compose failed with exit code $COMPOSE_EXIT_CODE"
    echo "📄 Errors logged to: $LOG_FILE"
fi

exit $COMPOSE_EXIT_CODE
