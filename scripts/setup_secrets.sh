#!/bin/bash

# Secure environment file setup and validation script for Docker deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Generate secure random string
generate_secret() {
    local length=${1:-50}
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

# Generate Django secret key (specific format)
generate_django_secret() {
    python3 -c "
import secrets
import string
chars = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
print(''.join(secrets.choice(chars) for _ in range(50)))
"
}

# Setup development environment
setup_development() {
    log_info "Setting up development environment..."
    
    local env_file=".env"
    if [[ -f "$env_file" ]]; then
        log_warn ".env file already exists"
        read -p "Overwrite with a new generated file? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Skipping .env file generation."
            return 0
        fi
    fi
    
    log_info "Generating new .env file..."
    cat > "$env_file" << EOF
# Development environment variables
# WARNING: This file contains sensitive data - never commit to version control!

# Django settings
DJANGO_SETTINGS_MODULE=config.settings.docker_dev
DEBUG=1
SECRET_KEY=$(generate_django_secret)

# Database settings
POSTGRES_DB=myapp_dev
POSTGRES_USER=myapp_user
POSTGRES_PASSWORD=$(generate_secret 32)
DATABASE_URL=postgresql://myapp_user:\${POSTGRES_PASSWORD}@db:5432/myapp_dev

# Redis settings
REDIS_URL=redis://redis:6379/0

# Superuser settings (optional)
SUPERUSER_EMAIL=admin@example.com
SUPERUSER_PASSWORD=admin123

# Flower monitoring (optional)
FLOWER_USER=admin
FLOWER_PASSWORD=$(generate_secret 16)

# Development settings
PYTHONDEBUG=1
SQL_DEBUG=1
DJANGO_LOG_LEVEL=DEBUG
EOF
    
    chmod 600 "$env_file"
    log_info "Development .env file created: $env_file"
    log_warn "Remember to add .env to your .gitignore file!"
}

# Validate staging environment
validate_staging() {
    log_info "Validating staging environment..."
    local env_file="staging.env"

    if [[ -s "$env_file" ]]; then
        log_info "Validation successful: '$env_file' found and is not empty."
        return 0
    else
        log_error "Validation failed: '$env_file' not found or is empty."
        return 1
    fi
}

# Validate production environment
validate_production() {
    log_info "Validating production environment..."
    local env_file="prod.env"

    if [[ -s "$env_file" ]]; then
        log_info "Validation successful: '$env_file' found and is not empty."
        return 0
    else
        log_error "Validation failed: '$env_file' not found or is empty."
        return 1
    fi
}

# Validate permissions on all .env files
validate_permissions() {
    log_info "Validating environment file permissions..."
    
    local errors=0
    local env_files=(".env" "staging.env" "prod.env")

    for file in "${env_files[@]}"; do
        if [[ -f "$file" ]]; then
            local perms
            perms=$(stat -c %a "$file")
            if [[ "$perms" != "600" ]]; then
                log_warn "Insecure permissions on $file ($perms). Recommended: 600."
                read -p "Fix permissions for $file? (Y/n): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                    chmod 600 "$file"
                    log_info "Permissions for $file set to 600."
                fi
            else
                log_info "Permissions for $file are secure (600)."
            fi
        fi
    done
    
    return $errors
}

# Create .gitignore entries
setup_gitignore() {
    local gitignore=".gitignore"
    
    log_info "Ensuring .gitignore is configured correctly..."
    local entries=(
        "# Secrets and environment files"
        ".env"
        "staging.env"
        "prod.env"
        "secrets/"
        "data/"
        "logs/"
    )
    
    for entry in "${entries[@]}"; do
        if ! grep -qF "$entry" "$gitignore" 2>/dev/null; then
            echo "$entry" >> "$gitignore"
            log_info "Added '$entry' to .gitignore"
        fi
    done
    
    log_info ".gitignore setup is complete."
}

# Main menu
show_menu() {
    echo
    log_info "Environment File Setup and Validation"
    echo "1. Setup/Generate Development Environment (.env)"
    echo "2. Validate Staging Environment (staging.env)"
    echo "3. Validate Production Environment (prod.env)"
    echo "4. Validate All Environment Files"
    echo "5. Check/Fix File Permissions"
    echo "6. Configure .gitignore"
    echo "0. Exit"
    echo
}

# Main execution
main() {
    log_info "Starting environment file validation script..."
    
    # Check prerequisites
    if ! command -v openssl &> /dev/null; then
        log_error "openssl is required for secret generation but not installed"
    fi
    if ! command -v python3 &> /dev/null; then
        log_error "python3 is required for secret generation but not installed"
    fi
    
    if [[ $# -gt 0 ]]; then
        case $1 in
            1) setup_development; exit $? ;;
            2) validate_staging; exit $? ;;
            3) validate_production; exit $? ;;
            4) validate_staging && validate_production; exit $? ;;
        esac
    fi

    while true; do
        show_menu
        read -p "Select an option: " choice
        
        case $choice in
            1) setup_development ;;
            2) validate_staging ;;
            3) validate_production ;;
            4) 
                log_info "Validating all environments..."
                setup_development
                validate_staging
                validate_production
                ;;
            5) validate_permissions ;;
            6) setup_gitignore ;;
            0) 
                log_info "Exiting..."
                exit 0
                ;;
            *)
                log_error "Invalid option: $choice"
                ;;
        esac
        
        echo
        read -p "Press Enter to continue..."
    done
}

# Run main function
main "$@"