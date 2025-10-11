#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e
# The docker-compose file to use
COMPOSE_FILE="compose.staging.yml"
echo "Commencing upgrade..."
# Start migration service, which then triggers auto-restart for dependents
echo "Running database migrations..."
docker compose -f $COMPOSE_FILE restart migrate
echo "Upgrade in progress, services restarting..."
