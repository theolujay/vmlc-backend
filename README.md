**Project Overview**

- **Name:** `vmlc-backend` — backend service for the Verboheit Mathematics League Competition (VMLC).
- **Purpose:** Provide APIs and real-time channels for participant registration, exams, scoring, leaderboards, and administrative workflows.
**Project Overview**

- **Name:** `vmlc-backend` — backend service for the Verboheit Mathematics League Competition (VMLC).
- **Purpose:** Provide HTTP APIs and realtime channels for participant registration, exams, scoring, leaderboards, and administrative workflows. The backend favors short-lived API responses and offloads heavy work (scoring, file validation, notifications) to Celery.

## Architecture (detailed)

- **HTTP API (REST):** Built with Django 5.x + Django REST Framework. Core business logic (models, serializers, viewsets) is in `vmlc/`. APIs follow DRF patterns with serializers in `vmlc/serializers/` and API routers registered in `config/urls.py` and `vmlc/urls.py`.
- **Real-time (WebSockets):** Implemented using `channels` + `daphne`. ASGI routing is wired in `config/asgi.py` which mounts `comms.routing.websocket_urlpatterns` behind `comms.middleware.DualAuthMiddlewareStack` (a custom auth stack that allows token and session fallback). Consumers and broadcast logic live in `comms/` and some consumers also in `vmlc/consumers.py`.
- **Background processing (Celery):** Celery is configured in `config/celery.py` and tasks are auto-discovered from installed apps. Workers run with named queues; the development compose file launches a `celery_worker` and `celery_beat`. Queue names used in `compose.dev.yml` include: `default,emails,comms,scoring,files,reports,cache` — keep new tasks aligned to these queues when possible.
- **Persistence & Storage:** PostgreSQL is the primary DB. Redis is used for caching and as the Celery broker. Media storage uses AWS S3 via `django-storages` and `boto3` (signed URLs and storage backends are implemented in `vmlc/storage_backends.py`).
- **Observability:** OpenTelemetry instrumentation is present; OTEL env vars are set in `compose.*.yml`. Grafana dashboards and Prometheus config live in `grafana/` and `prometheus.yml`.

## Key Files & Directories (expanded)

- `vmlc/` — core app: models (`vmlc/models.py`), view logic (`vmlc/views.py`), serializers (`vmlc/serializers/`), and application tasks (`vmlc/tasks.py`). Look here first for domain logic (exams, candidates, scoring).
- `comms/` — real-time module: `consumers.py`, `middleware.py` (check `DualAuthMiddlewareStack`), `routing.py`, `tasks.py` and `utils.py` used by broadcasts and websocket handlers. Review `comms/tests.py` for consumer test patterns.
- `config/` — project bootstrap: `asgi.py` (ASGI app + websocket stack), `wsgi.py`, `celery.py` (beat schedule + autoload), and `urls.py` (API routes + health endpoints).
- `scripts/` — container lifecycle helpers: `entrypoint.sh`, `runmigrations.sh` (DB wait, migrate, collectstatic for prod), `runserver.sh`. These are executed by containers; keep changes minimal and robust to missing env vars.
- `compose.*.yml` & `Dockerfile` — how the app is built and composed locally and in staging/prod. `Dockerfile` defines multiple stages (`development`, `test`, `staging`, `production`) — use the `development` stage for local iterative work.

## Developer Workflows & Commands (practical tips)

- Start the full development environment (recommended):

```bash
docker compose -f compose.yml -f compose.dev.yml up --build
docker compose exec django python manage.py migrate
```

Notes:
- The compose file uses service names `django`, `db`, `redis`, `celery_worker`, `celery_beat`. `db-migrate` runs `./scripts/runmigrations.sh` to perform safer migrations with readiness checks.
- If you change the Docker image or Python deps, rebuild the image and bring containers down first:

```bash
docker compose -f compose.yml -f compose.dev.yml down --volumes --remove-orphans
docker compose -f compose.yml -f compose.dev.yml up --build
```

- Running locally without Docker (development loop):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

- Running tests:

```bash
pytest
# or run tests for an app
pytest vmlc/tests
```

Tips:
- Use `DJANGO_SETTINGS_MODULE=config.settings.dev` (or `config.settings.docker_dev` inside containers). `manage.py` defaults to `config.settings.dev`.
- For quick shell work use: `docker compose exec django python manage.py shell`.

## Conventions & Patterns to Preserve (detailed)

- Environment-driven settings: code and scripts frequently rely on `DJANGO_SETTINGS_MODULE`. Containers use `config.settings.docker_dev` in `config/celery.py` and other scripts — changing defaults can break container entrypoints.
- Task discovery and queues: Celery uses `app.autodiscover_tasks()`; task functions are registered by name and routed to queues by the worker `-Q` argument in `compose.dev.yml`. Add new queues in both `compose` files and worker startup flags if needed.
- WebSocket authentication: `DualAuthMiddlewareStack` supports multiple auth schemes (session & token). Modify middleware with caution — tests for `comms/test_consumers.py` illustrate expected behaviors.
- Migrations & startup: `scripts/runmigrations.sh` contains strict checks (DB readiness, Django system checks). Avoid adding long-running initialization steps to this script; it's intended to be idempotent and fast.

## Integration & Infra Notes (concrete)

- S3 / Storage:
	- `django-storages` and `boto3` dependencies are present. Storage backends live in `vmlc/storage_backends.py` — review for signed URL generation and bucket naming conventions before changing behavior.

- OpenTelemetry & Metrics:
	- OTEL is enabled in compose via `OTEL_EXPORTER_OTLP_ENDPOINT` and related env vars. Instrumentation packages are listed in `requirements.txt` and `pyproject.toml`. Avoid duplicate instrumentation in both middleware and app startup.

- Deployment & CI:
	- Render manifests are in `render.yaml`. GitHub Actions workflows are in `.github/workflows/` (`deploy-staging.yml`, `deploy-prod.yml`) — coordinate infra changes with ops.

## Examples

1) Minimal Celery task skeleton (place in `vmlc/tasks.py` or `vmlc/tasks/<module>.py`):

```python
from celery import shared_task

@shared_task(name='recalculate_leaderboard')
def recalculate_leaderboard(league_id):
		# Import inside task to avoid startup cost
		from vmlc.models import Leaderboard

		# Implementation: fetch candidates, compute scores, persist snapshot
		Leaderboard.recalculate_for_league(league_id)

		return True
```

Notes: use short, stable task `name=` values for backward compatibility with worker queues and monitoring.

2) Minimal WebSocket consumer skeleton (in `comms/consumers.py` or a new file):

```python
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class NotificationsConsumer(AsyncJsonWebsocketConsumer):
		async def connect(self):
				# `DualAuthMiddlewareStack` ensures `scope["user"]` may be set
				if not self.scope.get('user') or not self.scope['user'].is_authenticated:
						await self.close()
						return
				await self.accept()

		async def receive_json(self, content, **kwargs):
				# Handle client messages
				await self.send_json({"echo": content})

		async def disconnect(self, code):
				pass
```

Register in `comms/routing.py` and ensure `config/asgi.py` mounts the `comms.routing.websocket_urlpatterns` with the `DualAuthMiddlewareStack`.

## Quick Editing Checklist

- Run linting and tests after changes: `pytest`, `pylint` (configured in `pyproject.toml`).
- If changing Celery tasks/queues, update `compose.*.yml` worker `- -Q` flags and add beat entries in `config/celery.py` if periodic.
- If changing auth or middleware: update `comms/tests.py` and `vmlc/tests` to cover token/session fallbacks.


