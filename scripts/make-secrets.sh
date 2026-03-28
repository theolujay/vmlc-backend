#!/usr/bin/env bash
set -euo pipefail

# Usage: ./make-secrets.sh <env_file> [--create]
# Creates Docker Swarm secrets from an .env file
# Use --create flag to immediately create secrets in Docker Swarm

env_file="${1:-}"
create_flag=""

if [[ "$env_file" == "--help" || "$env_file" == "-h" ]]; then
  echo "Usage: $0 <env_file> [--create]"
  echo ""
  echo "Creates Docker Swarm secrets from an .env file."
  echo "The secret name is derived from the variable name in uppercase."
  echo ""
  echo "Options:"
  echo "  --create    Create secrets in Docker Swarm immediately"
  echo ""
  echo "Example:"
  echo "  $0 .env.staging        # Preview what would be created"
  echo "  $0 .env.staging --create  # Create secrets in Docker Swarm"
  exit 0
fi

if [[ -z "$env_file" ]]; then
  echo "Error: env file required" >&2
  echo "Usage: $0 <env_file> [--create]" >&2
  exit 1
fi

if [[ "${2:-}" == "--create" ]]; then
  create_flag="true"
fi

if [[ ! -f "$env_file" ]]; then
  echo "Error: env file '$env_file' not found" >&2
  exit 1
fi

echo -e "Processing $env_file...\n"

# Convert .env key-value pairs into Docker secrets
grep -vE '^(#|$)' "$env_file" | while IFS='=' read -r key value; do
  [ -n "$key" ] || continue
  
  secret_name="${key^^}"  # Convert to uppercase
  
  if [[ "$create_flag" == "true" ]]; then
    # Check if secret already exists
    if docker secret ls --format '{{.Name}}' | grep -qx "$secret_name"; then
      echo "  ⚠️  Secret already exists: $secret_name"
    else
      printf "%s" "$value" | docker secret create "$secret_name" -
      echo "  ✓  Created secret: $secret_name"
    fi
  else
    echo "  Would create: $secret_name"
  fi
done

if [[ "$create_flag" == "true" ]]; then
  echo -e "\nDone! Run 'docker secret ls' to verify."
else
  echo -e "\nDry run complete. Use --create to create secrets in Docker Swarm."
fi