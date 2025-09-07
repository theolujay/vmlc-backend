#!/bin/bash

# Secure secrets setup script for Docker deployment
# This script helps create and manage secrets securely

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
log_debug() { echo -e "${BLUE}[DEBUG]${NC} $1"; }

# Configuration
SECRETS_DIR="./secrets"
STAGING_SECRETS_DIR="./secrets/staging"
PRODUCTION_SECRETS_DIR="./secrets/production"

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

# Create secrets directory structure
setup_directories() {
    log_info "Setting up secrets directories..."
    
    for dir in "$SECRETS_DIR" "$STAGING_SECRETS_DIR" "$PRODUCTION_SECRETS_DIR"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            log_debug "Created directory: $dir"
        fi
        
        # Set restrictive permissions
        chmod 700 "$dir"
    done
    
    log_info "Directories created with secure permissions (700)"
}

# Create a secret file with proper permissions
create_secret_file() {
    local file_path="$1"
    local secret_value="$2"
    local description="$3"
    
    if [[ -f "$file_path" ]]; then
        log_warn "$description already exists at $file_path"
        read -p "Overwrite? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 0
        fi
    fi
    
    echo -n "$secret_value" > "$file_path"
    chmod 600 "$file_path"
    log_info "Created $description: $file_path"
}

# Generate database URL
generate_database_url() {
    local env="$1"
    local db_name db_user db_password db_host db_port
    
    echo "Enter database configuration for $env:"
    read -p "Database host (default: db): " db_host
    db_host=${db_host:-db}
    
    read -p "Database port (default: 5432): " db_port
    db_port=${db_port:-5432}
    
    read -p "Database name: " db_name
    if [[ -z "$db_name" ]]; then
        log_error "Database name is required"
        return 1
    fi
    
    read -p "Database user: " db_user
    if [[ -z "$db_user" ]]; then
        log_error "Database user is required"
        return 1
    fi
    
    echo "Generate random password? (recommended)"
    read -p "Use random password? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        read -s -p "Enter database password: " db_password
        echo
        if [[ -z "$db_password" ]]; then
            log_error "Password cannot be empty"
            return 1
        fi
    else
        db_password=$(generate_secret 32)
        log_info "Generated random password for database"
    fi
    
    local database_url="postgresql://${db_user}:${db_password}@${db_host}:${db_port}/${db_name}"
    
    # Store individual components for PostgreSQL container
    echo -n "$db_name" > "$2/postgres_db.txt"
    echo -n "$db_user" > "$2/postgres_user.txt" 
    echo -n "$db_password" > "$2/postgres_password.txt"
    echo -n "$database_url" > "$2/database_url.txt"
    
    chmod 600 "$2"/*.txt
    
    log_info "Database secrets created for $env environment"
    log_warn "Database password: $db_password (save this securely!)"
}

# Setup development environment
setup_development() {
    log_info "Setting up development environment..."
    log_warn "Development uses .env file instead of Docker secrets for easier debugging"
    
    local env_file=".env"
    if [[ -f "$env_file" ]]; then
        log_warn ".env file already exists"
        read -p "Overwrite? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 0
        fi
    fi
    
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

# Setup staging environment
setup_staging() {
    log_info "Setting up staging environment secrets..."
    
    # Django secret key
    create_secret_file "$STAGING_SECRETS_DIR/django_secret_key.txt" "$(generate_django_secret)" "Django secret key (staging)"
    
    # Database configuration
    log_info "Configuring staging database..."
    generate_database_url "staging" "$STAGING_SECRETS_DIR"
    
    log_info "Staging secrets setup completed"
}

# Setup production environment
setup_production() {
    log_info "Setting up production environment secrets..."
    
    log_warn "Production setup requires careful consideration of security!"
    log_warn "Ensure you're in a secure environment and using proper secret management."
    
    read -p "Continue with production setup? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        return 0
    fi
    
    # Django secret key
    create_secret_file "$PRODUCTION_SECRETS_DIR/django_secret_key.txt" "$(generate_django_secret)" "Django secret key (production)"
    
    # Database configuration
    log_info "Configuring production database..."
    generate_database_url "production" "$PRODUCTION_SECRETS_DIR"
    
    log_info "Production secrets setup completed"
    log_warn "Store production secrets securely and consider using external secret management!"
}

# Validate secrets
validate_secrets() {
    log_info "Validating secrets..."
    
    local errors=0
    
    # Check file permissions
    find "$SECRETS_DIR" -type f -not -perm 600 | while read -r file; do
        log_error "Insecure permissions on: $file ($(stat -c %a "$file"))"
        ((errors++))
    done
    
    # Check directory permissions
    find "$SECRETS_DIR" -type d -not -perm 700 | while read -r dir; do
        log_error "Insecure directory permissions on: $dir ($(stat -c %a "$dir"))"
        ((errors++))
    done
    
    if [[ $errors -eq 0 ]]; then
        log_info "All secrets have secure permissions"
    else
        log_error "Found $errors permission issues"
        return 1
    fi
}

# Create .gitignore entries
setup_gitignore() {
    local gitignore=".gitignore"
    
    # Entries to add
    local entries=(
        "# Secrets and environment files"
        ".env"
        ".env.*"
        "secrets/"
        "data/"
        "logs/"
        ""
        "# Docker volumes"
        "docker-compose.override.local.yml"
    )
    
    for entry in "${entries[@]}"; do
        if ! grep -qF "$entry" "$gitignore" 2>/dev/null; then
            echo "$entry" >> "$gitignore"
        fi
    done
    
    log_info "Updated .gitignore with security entries"
}

# Main menu
show_menu() {
    echo
    log_info "Docker Secrets Setup Script"
    echo "1. Setup Development Environment (.env file)"
    echo "2. Setup Staging Environment (Docker secrets)"
    echo "3. Setup Production Environment (Docker secrets)"
    echo "4. Validate Existing Secrets"
    echo "5. Setup .gitignore"
    echo "6. Setup All Environments"
    echo "0. Exit"
    echo
}

# Main execution
main() {
    log_info "Starting Docker secrets setup..."
    
    # Check prerequisites
    if ! command -v openssl &> /dev/null; then
        log_error "openssl is required but not installed"
        exit 1
    fi
    
    if ! command -v python3 &> /dev/null; then
        log_error "python3 is required but not installed"
        exit 1
    fi
    
    setup_directories
    setup_gitignore
    
    while true; do
        show_menu
        read -p "Select an option: " choice
        
        case $choice in
            1) setup_development ;;
            2) setup_staging ;;
            3) setup_production ;;
            4) validate_secrets ;;
            5) setup_gitignore ;;
            6) 
                setup_development
                setup_staging
                setup_production
                validate_secrets
                ;;
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
