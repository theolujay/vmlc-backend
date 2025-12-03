#!/bin/bash

BACKUP_DIR="$HOME/.db_backups"
BACKUP_DATETIME=$(date +"%Y-%m-%dT%H-%M-%S")
BACKUP_FILE_NAME="$BACKUP_DIR/backup_$BACKUP_DATETIME"

DB_CONTAINER_ID=$(docker ps -q -f name="$ENV_NAME" + "db")
BACKUP_CMD=$(docker exec $DB_CONTAINER_ID pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -Fc -b $BACKUP_FILE_NAME)

mkdir -p $BACKUP_DIR

(time $BACKUP_CMD) 2>&1 | grep real | awk 'print $2}'

aws s3 cp 