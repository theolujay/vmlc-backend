#!/bin/bash
set -euo pipefail

ENV="${1:-prod}"

if [ "$ENV" == "prod" ]; then
    STACK_NAME="vmlc-prod"
    POSTGRES_DB="vmlc_prod"
    POSTGRES_USER="verboheit_prod"
    S3_BUCKET="vmlc-prod"
    S3_REGION="eu-central-1"
elif [ "$ENV" == "staging" ]; then
    STACK_NAME="vmlc-staging"
    POSTGRES_DB="vmlc_staging"
    POSTGRES_USER="verboheit_staging"
    S3_BUCKET="vmlc-staging"
    S3_REGION="eu-central-1"
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

if [ -z "$DB_CONTAINER_ID" ]; then
    echo "Error: Database container not found for stack ${STACK_NAME}"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "Starting backup for ${STACK_NAME}..."
echo "Container ID: ${DB_CONTAINER_ID}"
echo "Backup file: ${BACKUP_FILENAME}"

if docker exec "$DB_CONTAINER_ID" sh -c \
    "PGPASSWORD=\$(cat /run/secrets/db-password) pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -Fc -b -v -f $CONTAINER_BACKUP_PATH"; then
    echo "Database backup created successfully"
else
    echo "Database backup failed"
    exit 1
fi

# Upload to S3
echo "Uploading to S3..."
if aws s3 cp "$HOST_BACKUP_PATH" "s3://${S3_BUCKET}/${ENV}-db-backups/" --region "$S3_REGION"; then
    echo "Upload successful at $(date)"
else
    echo "Upload failed at $(date)"
    exit 1
fi

echo "Cleaning up old local backups..."
ls -t "$BACKUP_DIR"/backup_*.dump | tail -n +3 | xargs -r rm

echo "Backup complete!"
exit 0