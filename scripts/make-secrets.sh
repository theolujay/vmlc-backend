#!/usr/bin/env bash
set -euo pipefail

# Usage: ./make-secrets staging.env compose.staging.yml

env_file="${1:-}"
compose_file="${2:-}"

if [[ -z "$env_file" || -z "$compose_file" ]]; then
  echo "Usage: $0 <env_file> <compose_file>" >&2
  exit 1
fi

if [[ ! -f "$env_file" ]]; then
  echo "Error: env file '$env_file' not found" >&2
  exit 1
fi

# Derive folder name from env file (e.g., staging.env → secrets/staging)
env_name="$(basename "$env_file" .env)"
secrets_dir="secrets/$env_name"

echo -e "Creating secrets from $env_file → $secrets_dir \n ...loading..."
mkdir -p "$secrets_dir"

# Convert .env key-value pairs into individual secret files
grep -vE '^(#|$)' "$env_file" | while IFS='=' read -r key value; do
  [ -n "$key" ] || continue
  echo -n "$value" > "$secrets_dir/$key.txt"
done

# Now append secrets section to the compose file
echo -e "\nsecrets:" >> "$compose_file"

shopt -s nullglob
files=("$secrets_dir"/*.txt)

if (( ${#files[@]} == 0 )); then
  echo "No secrets created in $secrets_dir" >&2
  exit 1
fi

for f in "${files[@]}"; do
  [ -f "$f" ] || continue
  key=$(basename "$f" .txt)
  printf "  %s:\n    file: ./%s\n" "$key" "$f" >> "$compose_file"
done

echo "Secrets appended to $compose_file"

