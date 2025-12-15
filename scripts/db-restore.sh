#!/bin/bash
set -euo pipefail

# Usage: ./db-restore.sh <environment> [backup_filename] [--full]
# Example: ./db-restore.sh prod backup_2025-12-13T02-00-00.dump
# Example: ./db-restore.sh staging backup_2025-12-13T02-00-00.dump --full
# Example: ./db-restore.sh staging (uses latest local backup)

# Check if environment argument is provided
if [ $# -eq 0 ]; then
    echo "Error: Environment argument required"
    echo ""
    echo "Usage: $0 <environment> [backup_filename] [--full]"
    echo ""
    echo "Examples:"
    echo "  $0 staging                                    # Use latest local backup"
    echo "  $0 prod backup_2025-12-13T02-00-00.dump      # Restore specific backup"
    echo "  $0 staging --full                             # Full restore with latest local"
    echo "  $0 prod backup_2025-12-13T02-00-00.dump --full  # Full restore specific backup"
    exit 1
fi

ENV="${1}"
BACKUP_FILENAME="${2:-}"
FULL_RESTORE="${3:-}"

# Handle --full flag in position 2 if no backup filename provided
if [ "$BACKUP_FILENAME" == "--full" ]; then
    FULL_RESTORE="--full"
    BACKUP_FILENAME=""
fi

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

BACKUP_DIR="$HOME/.db_backups"
RESTORE_DIR="$HOME/.db_restores"

# If no backup filename provided, try to use latest local backup
if [ -z "$BACKUP_FILENAME" ]; then
    echo "Backup filename not provided."
    
    # Check if local backups exist
    if ls "$BACKUP_DIR"/backup_*.dump 1> /dev/null 2>&1; then
        LATEST_LOCAL=$(ls -t "$BACKUP_DIR"/backup_*.dump | head -n 1)
        BACKUP_FILENAME=$(basename "$LATEST_LOCAL")
        
        echo "Found latest local backup: $BACKUP_FILENAME"
        read -p "Use this backup? (yes/no): " USE_LOCAL
        
        if [ "$USE_LOCAL" == "yes" ]; then
            echo "Using local backup: $BACKUP_FILENAME"
            # Copy to restore directory
            mkdir -p "$RESTORE_DIR"
            cp "$LATEST_LOCAL" "$RESTORE_DIR/$BACKUP_FILENAME"
            SKIP_S3_DOWNLOAD=true
        else
            echo "Please specify a backup filename."
            echo "Available backups in S3:"
            aws s3 ls "s3://${S3_BUCKET}/${ENV}-db-backups/" | tail -10
            exit 1
        fi
    else
        echo "No local backups found in $BACKUP_DIR"
        echo "Available backups in S3:"
        aws s3 ls "s3://${S3_BUCKET}/${ENV}-db-backups/" | tail -10
        echo ""
        echo "Usage: $0 <environment> <backup_filename> [--full]"
        exit 1
    fi
fi

S3_PATH="s3://${S3_BUCKET}/${ENV}-db-backups/${BACKUP_FILENAME}"
LOCAL_BACKUP="${RESTORE_DIR}/${BACKUP_FILENAME}"
CONTAINER_BACKUP="/tmp/${BACKUP_FILENAME}"

# Find the DB container
DB_CONTAINER_ID=$(docker ps -qf "name=${STACK_NAME}_db.1")

if [ -z "$DB_CONTAINER_ID" ]; then
    echo "Error: Database container not found for stack ${STACK_NAME}"
    exit 1
fi

# Create restore directory
mkdir -p "$RESTORE_DIR"

echo "======================================"
echo "PostgreSQL Restore Process"
echo "======================================"
echo "Environment: $ENV"
echo "Database: $POSTGRES_DB"
echo "Backup: $BACKUP_FILENAME"
echo "Container: $DB_CONTAINER_ID"
echo ""

# Confirmation prompt
if [ "$FULL_RESTORE" == "--full" ]; then
    echo "⚠️  WARNING: FULL RESTORE WILL DROP AND RECREATE THE DATABASE!"
    echo "⚠️  ALL CURRENT DATA WILL BE LOST!"
else
    echo "This will restore data into the existing database."
    echo "Existing objects will be dropped and recreated."
fi

echo ""
read -p "Are you sure you want to proceed? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Download from S3 if not using local backup
if [ "${SKIP_S3_DOWNLOAD:-false}" != "true" ]; then
    echo ""
    echo "Step 1/5: Downloading backup from S3..."
    if aws s3 cp "$S3_PATH" "$LOCAL_BACKUP" --region "$S3_REGION"; then
        echo "✓ Download complete"
    else
        echo "✗ Failed to download backup from S3"
        exit 1
    fi
else
    echo ""
    echo "Step 1/5: Using local backup (skipping S3 download)..."
fi

echo ""
echo "Step 2/5: Copying backup to container..."
if docker cp "$LOCAL_BACKUP" "$DB_CONTAINER_ID:$CONTAINER_BACKUP"; then
    echo "✓ Copy complete"
else
    echo "✗ Failed to copy backup to container"
    exit 1
fi

if [ "$FULL_RESTORE" == "--full" ]; then
    echo ""
    echo "Step 3/5: Dropping and recreating database..."
    if docker exec -i "$DB_CONTAINER_ID" sh -c \
        "PGPASSWORD=\$(cat /run/secrets/db-password) psql -U $POSTGRES_USER -d postgres" <<EOF
DROP DATABASE IF EXISTS $POSTGRES_DB;
CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;
EOF
    then
        echo "✓ Database recreated"
    else
        echo "✗ Failed to recreate database"
        exit 1
    fi
else
    echo ""
    echo "Step 3/5: Skipping database recreation (incremental restore)..."
fi

echo ""
echo "Step 4/5: Restoring backup..."
RESTORE_FLAGS="-U $POSTGRES_USER -d $POSTGRES_DB -v"
if [ "$FULL_RESTORE" != "--full" ]; then
    RESTORE_FLAGS="$RESTORE_FLAGS --clean --if-exists"
fi

if docker exec -i "$DB_CONTAINER_ID" sh -c \
    "PGPASSWORD=\$(cat /run/secrets/db-password) pg_restore $RESTORE_FLAGS $CONTAINER_BACKUP"; then
    echo "✓ Restore complete"
else
    echo "⚠️  Restore completed with warnings (this is often normal)"
fi

echo ""
echo "Step 5/5: Cleaning up..."
docker exec "$DB_CONTAINER_ID" rm "$CONTAINER_BACKUP"
rm "$LOCAL_BACKUP"
echo "✓ Cleanup complete"

echo ""
echo "======================================"
echo "Restore completed successfully!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Verify data integrity"
echo "2. Check application functionality"
echo "3. Review application logs"