# Docker Compose Management Makefile
# Provides convenient commands for managing your Docker environment

# Configuration
COMPOSE_UP_SCRIPT := ./compose_up.sh
HEALTH_CHECK_SCRIPT := ./health_check.sh
SECRETS_SETUP_SCRIPT := ./setup_secrets.sh

# Default environment
ENV ?= development

# Colors for output
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m

# Default target
.DEFAULT_GOAL := help

# Ensure scripts are executable
$(COMPOSE_UP_SCRIPT) $(HEALTH_CHECK_SCRIPT) $(SECRETS_SETUP_SCRIPT):
	@chmod +x $@

## Development Commands

.PHONY: dev
dev: $(COMPOSE_UP_SCRIPT) ## Start development environment
	@echo -e "$(CYAN)Starting development environment...$(NC)"
	$(COMPOSE_UP_SCRIPT) --environment development --verbose up

.PHONY: dev-build
dev-build: $(COMPOSE_UP_SCRIPT) ## Start development with forced rebuild
	@echo -e "$(CYAN)Starting development with rebuild...$(NC)"
	$(COMPOSE_UP_SCRIPT) --environment development --verbose --force up

.PHONY: dev-detach
dev-detach: $(COMPOSE_UP_SCRIPT) ## Start development in detached mode
	@echo -e "$(CYAN)Starting development in background...$(NC)"
	$(COMPOSE_UP_SCRIPT) --environment development --detach up

## Staging Commands

.PHONY: staging
staging: $(COMPOSE_UP_SCRIPT) ## Start staging environment
	@echo -e "$(YELLOW)Starting staging environment...$(NC)"
	$(COMPOSE_UP_SCRIPT) --environment staging --verbose up

.PHONY: staging-build
staging-build: $(COMPOSE_UP_SCRIPT) ## Start staging with forced rebuild
	@echo -e "$(YELLOW)Starting staging with rebuild...$(NC)"
	$(COMPOSE_UP_SCRIPT) --environment staging --verbose --force up

.PHONY: staging-detach
staging-detach: $(COMPOSE_UP_SCRIPT) ## Start staging in detached mode
	@echo -e "$(YELLOW)Starting staging in background...$(NC)"
	$(COMPOSE_UP_SCRIPT) --environment staging --detach up

## Production Commands

.PHONY: prod
prod: $(COMPOSE_UP_SCRIPT) ## Start production environment
	@echo -e "$(RED)Starting production environment...$(NC)"
	@echo -e "$(RED)WARNING: This will start production services!$(NC)"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ]
	$(COMPOSE_UP_SCRIPT) --environment production --quiet up

.PHONY: prod-detach
prod-detach: $(COMPOSE_UP_SCRIPT) ## Start production in detached mode
	@echo -e "$(RED)Starting production in background...$(NC)"
	@echo -e "$(RED)WARNING: This will start production services!$(NC)"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ]
	$(COMPOSE_UP_SCRIPT) --environment production --detach up

## Management Commands

.PHONY: down
down: $(COMPOSE_UP_SCRIPT) ## Stop and remove all services
	@echo -e "$(CYAN)Stopping services for $(ENV) environment...$(NC)"
	$(COMPOSE_UP_SCRIPT) --environment $(ENV) down

.PHONY: down-all
down-all: ## Stop all environments (dev, staging, prod)
	@echo -e "$(CYAN)Stopping all environments...$(NC)"
	@for env in development staging production; do \
		echo -e "$(CYAN)Stopping $$env...$(NC)"; \
		$(COMPOSE_UP_SCRIPT) --environment $$env --quiet down || true; \
	done

.PHONY: restart
restart: $(COMPOSE_UP_SCRIPT) ## Restart services
	@echo -e "$(CYAN)Restarting $(ENV) environment...$(NC)"
	$(COMPOSE_UP_SCRIPT) --environment $(ENV) restart

.PHONY: clean
clean: $(COMPOSE_UP_SCRIPT) ## Clean up unused resources
	@echo -e "$(CYAN)Cleaning up Docker resources...$(NC)"
	$(COMPOSE_UP_SCRIPT) --environment $(ENV) clean
	docker system prune -f
	docker volume prune -f

.PHONY: purge
purge: ## Complete cleanup (removes volumes and images)
	@echo -e "$(RED)WARNING: This will remove all Docker data including volumes!$(NC)"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ]
	@echo -e "$(RED)Stopping all containers...$(NC)"
	-docker compose -f compose.yml -f compose.override.yml down -v --remove-orphans
	-docker compose -f compose.yml -f compose.staging.yml down -v --remove-orphans
	-docker compose -f compose.yml down -v --remove-orphans
	@echo -e "$(RED)Removing all images and volumes...$(NC)"
	-docker system prune -af --volumes
	@echo -e "$(GREEN)Cleanup complete!$(NC)"

## Health and Monitoring

.PHONY: health
health: $(HEALTH_CHECK_SCRIPT) ## Check health of all services
	@echo -e "$(GREEN)Checking service health...$(NC)"
	$(HEALTH_CHECK_SCRIPT) check

.PHONY: monitor
monitor: $(HEALTH_CHECK_SCRIPT) ## Start continuous health monitoring
	@echo -e "$(GREEN)Starting health monitoring...$(NC)"
	$(HEALTH_CHECK_SCRIPT) monitor

.PHONY: wait-healthy
wait-healthy: $(HEALTH_CHECK_SCRIPT) ## Wait for services to become healthy
	@echo -e "$(GREEN)Waiting for services to become healthy...$(NC)"
	$(HEALTH_CHECK_SCRIPT) wait 300

## Logs and Debugging

.PHONY: logs
logs: $(COMPOSE_UP_SCRIPT) ## Show service logs
	@echo -e "$(CYAN)Showing logs for $(ENV) environment...$(NC)"
	$(COMPOSE_UP_SCRIPT) --environment $(ENV) logs

.PHONY: logs-web
logs-web: ## Show web service logs
	@docker compose logs -f web

.PHONY: logs-db
logs-db: ## Show database logs  
	@docker compose logs -f db

.PHONY: logs-redis
logs-redis: ## Show Redis logs
	@docker compose logs -f redis

.PHONY: logs-celery
logs-celery: ## Show Celery worker logs
	@docker compose logs -f celery_worker

.PHONY: shell-web
shell-web: ## Open shell in web container
	@docker compose exec web bash

.PHONY: shell-db
shell-db: ## Open PostgreSQL shell
	@docker compose exec db psql -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DB:-postgres}

.PHONY: shell-redis
shell-redis: ## Open Redis shell
	@docker compose exec redis redis-cli

## Setup and Configuration

.PHONY: setup
setup: $(SECRETS_SETUP_SCRIPT) ## Run initial setup (secrets, environment)
	@echo -e "$(GREEN)Running initial setup...$(NC)"
	$(SECRETS_SETUP_SCRIPT)

.PHONY: setup-dev
setup-dev: $(SECRETS_SETUP_SCRIPT) ## Setup development environment only
	@echo -e "$(GREEN)Setting up development environment...$(NC)"
	@echo "1" | $(SECRETS_SETUP_SCRIPT)

.PHONY: setup-secrets
setup-secrets: $(SECRETS_SETUP_SCRIPT) ## Setup Docker secrets for production
	@echo -e "$(GREEN)Setting up Docker secrets...$(NC)"
	$(SECRETS_SETUP_SCRIPT)

.PHONY: validate-secrets
validate-secrets: $(SECRETS_SETUP_SCRIPT) ## Validate existing secrets
	@echo -e "$(GREEN)Validating secrets...$(NC)"
	@echo "4" | $(SECRETS_SETUP_SCRIPT)

## Status and Information

.PHONY: status
status: $(COMPOSE_UP_SCRIPT) ## Show service status
	@echo -e "$(CYAN)Service status for $(ENV) environment:$(NC)"
	$(COMPOSE_UP_SCRIPT) --environment $(ENV) status

.PHONY: ps
ps: ## Show running containers
	@docker compose ps --format table

.PHONY: top
top: ## Show running processes in containers
	@docker compose top

.PHONY: images
images: ## Show Docker images
	@docker compose images

## Testing

.PHONY: test
test: ## Run tests in web container
	@echo -e "$(GREEN)Running tests...$(NC)"
	@docker compose exec web python manage.py test

.PHONY: test-coverage
test-coverage: ## Run tests with coverage
	@echo -e "$(GREEN)Running tests with coverage...$(NC)"
	@docker compose exec web coverage run --source='.' manage.py test
	@docker compose exec web coverage report

.PHONY: lint
lint: ## Run code quality checks
	@echo -e "$(GREEN)Running linting...$(NC)"
	@docker compose exec web flake8 .
	@docker compose exec web black --check .
	@docker compose exec web isort --check-only .

.PHONY: format
format: ## Format code
	@echo -e "$(GREEN)Formatting code...$(NC)"
	@docker compose exec web black .
	@docker compose exec web isort .

## Database Operations

.PHONY: migrate
migrate: ## Run database migrations
	@echo -e "$(GREEN)Running database migrations...$(NC)"
	@docker compose exec web python manage.py migrate

.PHONY: makemigrations
makemigrations: ## Create new migrations
	@echo -e "$(GREEN)Creating migrations...$(NC)"
	@docker compose exec web python manage.py makemigrations

.PHONY: db-reset
db-reset: ## Reset database (development only)
	@if [ "$(ENV)" != "development" ]; then \
		echo -e "$(RED)ERROR: Database reset only allowed in development!$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)Resetting development database...$(NC)"
	@docker compose down
	@docker volume rm $$(docker volume ls -q | grep postgres) || true
	@$(MAKE) dev-detach
	@sleep 10
	@$(MAKE) migrate

.PHONY: superuser
superuser: ## Create Django superuser
	@echo -e "$(GREEN)Creating Django superuser...$(NC)"
	@docker compose exec web python manage.py createsuperuser

.PHONY: collectstatic
collectstatic: ## Collect static files
	@echo -e "$(GREEN)Collecting static files...$(NC)"
	@docker compose exec web python manage.py collectstatic --no-input

## Backup and Restore

.PHONY: backup-db
backup-db: ## Backup database
	@echo -e "$(GREEN)Creating database backup...$(NC)"
	@mkdir -p ./backups
	@docker compose exec db pg_dump -U $${POSTGRES_USER:-postgres} $${POSTGRES_DB:-postgres} | gzip > ./backups/db_backup_$$(date +%Y%m%d_%H%M%S).sql.gz
	@echo -e "$(GREEN)Database backup created in ./backups/$(NC)"

.PHONY: restore-db
restore-db: ## Restore database from backup
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo -e "$(RED)ERROR: BACKUP_FILE variable is required$(NC)"; \
		echo -e "$(CYAN)Usage: make restore-db BACKUP_FILE=./backups/db_backup_20231201_120000.sql.gz$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)Restoring database from $(BACKUP_FILE)...$(NC)"
	@echo -e "$(RED)WARNING: This will overwrite the current database!$(NC)"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ]
	@gunzip -c $(BACKUP_FILE) | docker compose exec -T db psql -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DB:-postgres}
	@echo -e "$(GREEN)Database restored successfully!$(NC)"

## Help

.PHONY: help
help: ## Show this help message
	@echo -e "$(CYAN)Docker Compose Management Commands$(NC)"
	@echo ""
	@echo -e "$(GREEN)Environment variable ENV controls target environment (development|staging|production)$(NC)"
	@echo -e "$(GREEN)Default: ENV=development$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "$(CYAN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort
	@echo ""
	@echo -e "$(YELLOW)Examples:$(NC)"
	@echo -e "$(CYAN)  make dev$(NC)                    # Start development environment"
	@echo -e "$(CYAN)  make staging ENV=staging$(NC)    # Start staging environment"  
	@echo -e "$(CYAN)  make health$(NC)                 # Check service health"
	@echo -e "$(CYAN)  make logs-web$(NC)               # Show web service logs"
	@echo -e "$(CYAN)  make shell-web$(NC)              # Open shell in web container"

.PHONY: info
info: ## Show environment information
	@echo -e "$(CYAN)Current Configuration:$(NC)"
	@echo -e "$(GREEN)Environment:$(NC) $(ENV)"
	@echo -e "$(GREEN)Compose Script:$(NC) $(COMPOSE_UP_SCRIPT)"
	@echo -e "$(GREEN)Health Script:$(NC) $(HEALTH_CHECK_SCRIPT)"
	@echo -e "$(GREEN)Secrets Script:$(NC) $(SECRETS_SETUP_SCRIPT)"
	@echo ""
	@echo -e "$(CYAN)Docker Information:$(NC)"
	@docker --version
	@docker compose version
	@echo ""
	@echo -e "$(CYAN)Available Compose Files:$(NC)"
	@ls -la compose*.yml 2>/dev/null || echo "No compose files found"
