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
	docker compose exec -it django bash

## dev/psql: connect to local database
.PHONY: dev/psql
dev/psql:
	@docker compose exec -it db psql -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DB:-vmlc_dev}

# ==================================================================================== #
# DATABASE
# ==================================================================================== #

## db/makemigrations: create new migrations
.PHONY: db/makemigrations
db/makemigrations:
	python manage.py makemigrations

## db/migrate: apply pending migrations
.PHONY: db/migrate
db/migrate:
	python manage.py migrate

## db/migrate/plan: show migration plan without applying
.PHONY: db/migrate/plan
db/migrate/plan:
	python manage.py showmigrations

# ==================================================================================== #
# BUILD
# ==================================================================================== #

## build: build Docker images (no push)
.PHONY: build
build:
	docker compose build

## collectstatic: collect static files
.PHONY: collectstatic
collectstatic:
	docker compose exec django python manage.py collectstatic --noinput

# ==================================================================================== #
# QUALITY CONTROL
# ==================================================================================== #

## lint: run Ruff linter
.PHONY: lint
lint:
	ruff check .

## lint/fix: auto-fix lint issues
.PHONY: lint/fix
lint/fix:
	ruff check --fix .

## format: format code with Ruff formatter
.PHONY: format
format:
	ruff format .
	black .

## format/check: check formatting without changes
.PHONY: format/check
format/check:
	ruff format --check .

## pylint: run pylint (stricter checks)
.PHONY: pylint
pylint:
	pylint comms competition config core identity vmlc

## typecheck: run mypy type checking
.PHONY: typecheck
typecheck:
	mypy comms competition config core identity vmlc

## isort: sort imports
.PHONY: isort
isort:
	ruff check --select I --fix .

## test: run tests with pytest
.PHONY: test
test:
	python manage.py test --settings=config.settings.test --noinput --keepdb --failfast

## test/coverage: run tests with coverage report
.PHONY: test/coverage
test/coverage:
	coverage run -m pytest && coverage report

## test/docker: run tests inside the Django container
.PHONY: test/docker
test/docker:
	docker compose exec python manage.py test --settings=config.settings.test --noinput --keepdb --failfast

## security: run bandit security checks
.PHONY: security
security:
	bandit -r comms competition config core identity vmlc

## deadcode: find dead code with vulture
.PHONY: deadcode
deadcode:
	vulture comms competition config core identity vmlc --min-confidence 70

# ==================================================================================== #
# MANAGEMENT
# ==================================================================================== #

## shell: open Django shell
.PHONY: shell
shell:
	docker compose exec -it django python manage.py shell

## shell/plus: open Django shell_plus (requires django-extensions)
.PHONY: shell/plus
shell/plus:
	docker compose exec -it django python manage.py shell_plus

## dbshell: open Django database shell
.PHONY: dbshell
dbshell:
	docker compose exec -it django python manage.py dbshell

## createsuperuser: create a Django superuser
.PHONY: createsuperuser
createsuperuser:
	docker compose exec -it django python manage.py createsuperuser

## manage: run any manage.py command (usage: manage <command>)
.PHONY: manage
manage:
	docker compose exec -it django python manage.py $(filter-out $@,$(MAKECMDGOALS))

# ==================================================================================== #
# CELERY
# ==================================================================================== #

## celery/status: check Celery worker status
.PHONY: celery/status
celery/status:
	docker compose exec celery_worker celery -A config inspect ping

## celery/flower: enable Flower monitoring
.PHONY: celery/flower
celery/flower:
	docker compose up flower

## celery/logs: tail Celery worker logs
.PHONY: celery/logs
celery/logs:
	docker compose logs -f celery_worker

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

## infra/init: bootstrap a fresh VPS (run on server as root)
.PHONY: infra/init
infra/init: confirm
	sudo ./scripts/infra-init.sh --staging-env-file .env.staging --prod-env-file .env.production --infra-env-file .env.infra --deploy-pub-key ~/.ssh/github-actions-deploy.pub --deploy-apps

## infra/services: list all Swarm services
.PHONY: infra/services
infra/services:
	docker service ls

## infra/logs: tail logs from a Swarm service (usage: SERVICE=stack_service)
.PHONY: infra/logs
infra/logs:
	docker service logs -f ${SERVICE}
