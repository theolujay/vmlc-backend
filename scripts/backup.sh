#!/bin/bash
set -euo pipefail

source ~/.backup_env
ENV="${1:-prod}"
MAX_RETRIES=10
RETRY_INTERVAL=600 

if [ "$ENV" == "prod" ]; then
    STACK_NAME="vmlc-prod"
    POSTGRES_DB="vmlc_prod"
    POSTGRES_USER="verboheit_prod"
    S3_BUCKET="vmlc-prod"
    S3_REGION="eu-central-1"
    WEBHOOK_URL="https://api.verboheit.org/api/webhooks/db-backup/"
elif [ "$ENV" == "staging" ]; then
    STACK_NAME="vmlc-staging"
    POSTGRES_DB="vmlc_staging"
    POSTGRES_USER="verboheit_staging"
    S3_BUCKET="vmlc-staging"
    S3_REGION="eu-central-1"
    WEBHOOK_URL="https://staging-api.verboheit.org/api/webhooks/db-backup/"
else
    echo "Invalid environment. Use 'prod' or 'staging'"
    exit 1
fi

# Backup configs
BACKUP_DIR="$HOME/.db_backups"
BACKUP_DATETIME=$(date +"%Y-%m-%dT%H-%M-%S")
BACKUP_FILENAME="backup_${BACKUP_DATETIME}.dump"
CONTAINER_BACKUP_PATH="/backups/${BACKUP_FILENAME}"
HOST_BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

# Find the DB container
DB_CONTAINER_ID=$(docker ps -qf "name=${STACK_NAME}_db.1")

send_notification() {
    local status=$1
    local error_msg=${2:-""}
    local timestamp=$(date +"%Y-%m-%dT%H:%M:%S")
    
    local payload=$(cat <<EOF
{
    "status": "$status",
    "environment": "$ENV",
    "timestamp": "$timestamp",
    "backup_filename": "$BACKUP_FILENAME",
    "error_message": "$error_msg"
}
EOF
)

    curl -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -H "x-api-key: $BACKUP_API_KEY" \
        -d "$payload" \
        --silent \
        --show-error \
        || echo "Warning: Failed to send notification"
}

run_backup() {
    if [ -z "$DB_CONTAINER_ID" ]; then
        echo "Error: Database container not found for stack ${STACK_NAME}"
        return 1
    fi

    mkdir -p "$BACKUP_DIR"

    echo "Starting backup for ${STACK_NAME}..."
    echo "Container ID: ${DB_CONTAINER_ID}"
    echo "Backup file: ${BACKUP_FILENAME}"

    if ! docker exec "$DB_CONTAINER_ID" sh -c \
        "PGPASSWORD=\$(cat /run/secrets/db-password) pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -Fc -b -v -f $CONTAINER_BACKUP_PATH"; then
        echo "Database backup failed"
        return 1
    fi
    
    echo "Database backup created successfully"

    # Upload to S3
    echo "Uploading to S3..."
    if ! aws s3 cp "$HOST_BACKUP_PATH" "s3://${S3_BUCKET}/${ENV}-db-backups/" --region "$S3_REGION"; then
        echo "Upload failed at $(date)"
        return 1
    fi
    
    echo "Upload successful at $(date)"

    echo "Cleaning up old local backups..."
    ls -t "$BACKUP_DIR"/backup_*.dump | tail -n +3 | xargs -r rm

    echo "Backup complete!"
    return 0
}

if run_backup; then
    send_notification "success"
    exit 0
else
    send_notification "first_failure" "Backup failed"

    for i in $(seq 1 $MAX_RETRIES); do
        echo "Retry $i of $MAX_RETRIES in 10 minutes..."
        sleep $RETRY_INTERVAL

        if run_backup; then
            send_notification "success_after_retry"
            exit 0
        fi
    done

    send_notification "final_failure" "All retries exhausted"
    exit 1
fi