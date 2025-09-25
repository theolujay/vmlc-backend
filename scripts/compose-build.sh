#!/bin/bash

# VMLC Backend Docker Build Script
# This script optimizes the build process by building the base image once
# and reusing it across all services.

set -e  # Exit on any error

echo "Building VMLC Backend - Optimized Docker Build"
echo "=================================================="

# Start timer
START_TIME=$(date +%s)

# Function to show elapsed time
show_time() {
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    MINUTES=$((ELAPSED / 60))
    SECONDS_REMAINDER=$((ELAPSED % 60))
    echo "⏱️  Build completed in: ${MINUTES}m ${SECONDS_REMAINDER}s"
}

# Trap to show time on exit
trap show_time EXIT

# Step 1: Build the base backend image (this is the slow part)
echo "📦 Step 1: Building backend base image..."
docker build \
    --target development \
    --tag vmlc-backend:dev \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    .

echo "Backend base image built successfully!"

# Step 2: Start services (they'll all use the same base image now)
echo "Step 2: Starting services..."
docker compose up -d --build

echo "All services started!"
echo ""
echo "Available services:"
echo "   • Web API: http://localhost:8000"
echo "   • Flower (Celery Monitor): http://localhost:5555 (admin/admin)"
echo "   • Grafana: http://localhost:3030"
echo "   • Prometheus: http://localhost:9090"
echo ""
echo "Useful commands:"
echo "   • View logs: docker compose logs -f [service_name]"
echo "   • Stop all: docker compose down"
echo "   • Rebuild: ./scripts/compose-build.sh"