# ==================================================================================== #
# VARIABLES
# ==================================================================================== #

APPS = comms competition config core identity vmlc
MANAGE = python manage.py
DOCKER_DJANGO = docker compose exec django
DOCKER_DB = docker compose exec db
CELERY_WORKER = celery_worker

# ==================================================================================== #
# HELPERS
# ==================================================================================== #

## help: print this help message
.PHONY: help
help:
	@echo 'Usage:'
	@sed -n 's/^##//p' ${MAKEFILE_LIST} | column -t -s ':' | sed -e 's/^/ /'

.PHONY: confirm
confirm:
	@echo -n 'Are you sure? [y/N] ' && read ans && [ $${ans:-N} = y ]

# ==================================================================================== #
# DEVELOPMENT
# ==================================================================================== #

## dev: run the full stack locally (Docker Compose)
.PHONY: dev
dev:
	docker compose up --build

## dev/detach: run stack in background
.PHONY: dev/detach
dev/detach:
	docker compose up --build -d

## dev/down: stop the local stack
.PHONY: dev/down
dev/down:
	docker compose down

## dev/clean: stop and remove volumes (destroys data)
.PHONY: dev/clean
dev/clean: confirm
	docker compose down -v

## dev/logs: tail logs from all services
.PHONY: dev/logs
dev/logs:
	docker compose logs -f

## dev/watch: hot-reload with Docker Compose watch
.PHONY: dev/watch
dev/watch:
	docker compose watch

## dev/shell: open a shell in the Django container
.PHONY: dev/shell
dev/shell:
	$(DOCKER_DJANGO) bash

## dev/psql: connect to local database
.PHONY: dev/psql
dev/psql:
	@$(DOCKER_DB) psql -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DB:-vmlc_dev}

# ==================================================================================== #
# PACKAGE MANAGEMENT (UV)
# ==================================================================================== #

## uv/sync: sync dependencies with uv
.PHONY: uv/sync
uv/sync:
	uv sync --group dev --group test --group docs

# ==================================================================================== #
# DATABASE
# ==================================================================================== #

## db/makemigrations: create new migrations
.PHONY: db/makemigrations
db/makemigrations:
	$(MANAGE) makemigrations

## db/migrate: apply pending migrations
.PHONY: db/migrate
db/migrate:
	$(MANAGE) migrate

## db/migrate/plan: show migration plan without applying
.PHONY: db/migrate/plan
db/migrate/plan:
	$(MANAGE) showmigrations

# ==================================================================================== #
# BUILD & STATIC FILES
# ==================================================================================== #

## build: build Docker images
.PHONY: build
build:
	docker compose build

## collectstatic: collect static files inside container
.PHONY: collectstatic
collectstatic:
	$(DOCKER_DJANGO) $(MANAGE) collectstatic --noinput

# ==================================================================================== #
# QUALITY CONTROL
# ==================================================================================== #

## lint: run Ruff linter
.PHONY: lint
lint:
	ruff check .

## lint/fix: auto-fix lint issues with Ruff
.PHONY: lint/fix
lint/fix:
	ruff check --fix .

## format: format code with Ruff
.PHONY: format
format:
	ruff format .
	ruff check --select I --fix .

## format/check: check formatting without changes
.PHONY: format/check
format/check:
	ruff format --check .

## typecheck: run mypy type checking
.PHONY: typecheck
typecheck:
	mypy $(APPS)

## pylint: run pylint (stricter checks)
.PHONY: pylint
pylint:
	pylint $(APPS)

## isort: sort imports (using Ruff)
.PHONY: isort
isort:
	ruff check --select I --fix .

## security: run bandit security checks
.PHONY: security
security:
	bandit -r $(APPS)

## deadcode: find dead code with vulture
.PHONY: deadcode
deadcode:
	vulture $(APPS) --min-confidence 70

## test: run tests with Django test runner
.PHONY: test
test:
	$(MANAGE) test --settings=config.settings.test --noinput --keepdb --failfast

## test/coverage: run tests with coverage report
.PHONY: test/coverage
test/coverage:
	coverage run -m pytest && coverage report

## test/docker: run tests inside the Django container
.PHONY: test/docker
test/docker:
	$(DOCKER_DJANGO) $(MANAGE) test --settings=config.settings.test --noinput --keepdb --failfast

# ==================================================================================== #
# MANAGEMENT
# ==================================================================================== #

## shell: open Django shell inside container
.PHONY: shell
shell:
	$(DOCKER_DJANGO) $(MANAGE) shell

## shell/plus: open Django shell_plus inside container
.PHONY: shell/plus
shell/plus:
	$(DOCKER_DJANGO) $(MANAGE) shell_plus

## dbshell: open Django database shell inside container
.PHONY: dbshell
dbshell:
	$(DOCKER_DJANGO) $(MANAGE) dbshell

## createsuperuser: create a Django superuser inside container
.PHONY: createsuperuser
createsuperuser:
	$(DOCKER_DJANGO) $(MANAGE) createsuperuser

## manage: run any manage.py command (usage: make manage <command>)
.PHONY: manage
manage:
	$(DOCKER_DJANGO) $(MANAGE) $(filter-out $@,$(MAKECMDGOALS))

# ==================================================================================== #
# CELERY
# ==================================================================================== #

## celery/status: check Celery worker status
.PHONY: celery/status
celery/status:
	docker compose exec $(CELERY_WORKER) celery -A config inspect ping

## celery/flower: enable Flower monitoring
.PHONY: celery/flower
celery/flower:
	docker compose up flower

## celery/logs: tail Celery worker logs
.PHONY: celery/logs
celery/logs:
	docker compose logs -f $(CELERY_WORKER)

# ==================================================================================== #
# INFRASTRUCTURE (Docker Swarm)
# ==================================================================================== #

## infra/secrets/preview: preview secrets that would be created from .env
.PHONY: infra/secrets/preview
infra/secrets/preview:
	./scripts/make-secrets.sh .env.production

## infra/secrets/create: create secrets in Swarm from .env
.PHONY: infra/secrets/create
infra/secrets/create: confirm
	./scripts/make-secrets.sh .env.production --create

## infra/secrets/update: rotate secrets in Swarm (zero-downtime)
.PHONY: infra/secrets/update
infra/secrets/update: confirm
	./scripts/make-secrets.sh .env.production --update

## infra/deploy/staging: deploy the staging app stack
.PHONY: infra/deploy/staging
infra/deploy/staging:
	docker stack deploy -c infra/stack.base.yml -c infra/stack.staging.yml vmlc-staging

## infra/deploy/production: deploy the production app stack
.PHONY: infra/deploy/production
infra/deploy/production:
	docker stack deploy -c infra/stack.base.yml -c infra/stack.prod.yml vmlc-prod

## infra/rm/staging: remove the staging stack
.PHONY: infra/rm/staging
infra/rm/staging: confirm
	docker stack rm vmlc-staging

## infra/rm/production: remove the production stack
.PHONY: infra/rm/production
infra/rm/production: confirm
	docker stack rm vmlc-prod

## infra/services: list all Swarm services
.PHONY: infra/services
infra/services:
	docker service ls

## infra/logs: tail logs from a Swarm service (usage: make infra/logs SERVICE=stack_service)
.PHONY: infra/logs
infra/logs:
	docker service logs -f ${SERVICE}
