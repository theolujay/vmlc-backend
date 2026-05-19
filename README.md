# VMLC Backend

> Backend service for the **Verboheit Mathematics League Competition**, a free annual mathematics competition for senior secondary school students (SS1–SS3) across Nigeria.

The backend powers the full competition lifecycle: candidate registration and identity verification, multi-stage exam delivery, automated scoring, cumulative leaderboards, real-time proctoring, helpdesk, and staff administration.

This project -- including the UIs, [vmlc-frontend](https://github.com/theolujay/vmlc-frontend) and [vmlc-landing](https://github.com/theolujay/vmlc-landing) -- was built to address a need for better administrative workflows and a more capable digital environment for running the competition, identified and led by [@theolujay](https://github.com/theolujay).

---

## Table of Contents

- [Competition Stages](#competition-stages)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## Competition Stages

| Stage | Format | Advancement |
|---|---|---|
| Screening | Virtual Test | A select number of top performers advance |
| League | Six rounds of virtual exams, one per week | Cumulative standings; top selction advance |
| Final | In-person exam | Knockout round among top qualifiers. Top three win |

Staff members determine the questions and exam constraints.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 5.2, Django REST Framework 3.16 |
| ASGI Server | Uvicorn + Gunicorn |
| Real-time | Django Channels 4, Redis channel layer |
| Background Jobs | Celery 5.5, Celery Beat, Redis broker |
| Database | PostgreSQL 17 |
| Cache / Broker | Redis 7 |
| Storage | AWS S3 via django-storages (public & private buckets) |
| Auth | JWT (SimpleJWT), API keys, session fallback |
| Observability | OpenTelemetry, Prometheus, Grafana, structured JSON logging |
| Monitoring | django-health-check, django-prometheus |

---

## Architecture

The application is fully ASGI. HTTP and WebSocket traffic share the same process and port, routed by a `ProtocolTypeRouter` in `config/asgi.py`.

### Request Layer

Incoming HTTP requests are handled by Uvicorn (behind Gunicorn) and dispatched to Django REST Framework views. WebSocket connections are handled by Django Channels consumers. Both share the same ASGI entrypoint.

### Application Layer

The codebase is split into four Django apps, each with a distinct responsibility:

- `identity` -- User accounts, candidate and staff profiles, registration, and authentication and authorization.
- `vmlc` -- The core exam engine: question delivery, candidate sessions, automated scoring, violation tracking, and WebSocket-based proctoring.
- `competition` -- Competition and stage lifecycle management; enrollments, stage promotions, ranking snapshots, and leaderboard publishing.
- `comms` -- Real-time communications: WebSocket consumers for notifications and helpdesk, Celery-backed broadcast dispatch, email, and SMS.

### Background Layer

Heavy operations are offloaded to Celery workers across named queues. This includes exam scoring, ranking computation, notification dispatch, cache warming, and file processing. Celery Beat handles scheduled jobs such as periodic cache updates and results publishing.

### Data Layer

PostgreSQL is the primary data store. Redis serves dual duty as the Celery broker and the Django Channels channel layer. Static and user-uploaded files are stored in AWS S3, with separate public and private buckets managed by custom storage backends.

---

## Project Structure

```
config/              Django project bootstrap
├── settings/        Environment-specific settings (dev, prod, staging, docker_dev)
├── asgi.py          ASGI application and WebSocket routing
├── celery.py        Celery app and beat schedule
└── urls.py          API route registration

identity/            User and authentication
├── models.py        User, Candidate, Staff, EmailOTP
├── permissions.py   Role hierarchy (superadmin → volunteer)
└── views.py         Registration, login, verification, profile

vmlc/                Core exam engine
├── models.py        Exam, Question, CandidateExamResult, Heartbeat, ViolationEvent
├── serializers/     DRF serializers
├── views.py         Exam-taking, scoring, leaderboards
├── consumers.py     WebSocket consumers for proctoring
├── tasks.py         Celery tasks (scoring, ranking, notifications)
└── storage_backends.py  S3 public/private storage backends

competition/         Competition lifecycle
├── models.py        Competition, Stage, StageExam, Enrollment, RankingSnapshot
├── views.py         Dashboards, rankings, leaderboards, stage promotions
└── tasks.py         Celery tasks (cache updates, notifications)

comms/               Communications and real-time
├── consumers.py     Unified WebSocket consumer (notifications, helpdesk, broadcasts)
├── middleware.py    DualAuthMiddlewareStack (JWT / session / API key)
├── models.py        HelpdeskThread, Broadcast, Notification, BackupLog
├── tasks.py         Celery tasks (broadcast dispatch, email, SMS)
└── routing.py       WebSocket URL patterns

scripts/             Container lifecycle entrypoints
docker/              Docker support files
infra/               Infrastructure and deployment manifests
```

---

## Quick Start

### Prerequisites

- Python 3.13
- PostgreSQL 17
- Redis 7

### Using Docker (recommended)

```bash
cp .example.env .env
docker compose up --build
```

Migrations run automatically via the `db-migrate` service. The Django server, Celery worker, and Celery Beat all start once migrations complete.

The API is available at `http://localhost:8000`. Postman Collection [here](./core/VMLC_API.postman_collection.json).

### Local Development

```bash
cp .example.env .env
uv sync --group dev
python manage.py migrate
python manage.py runserver
```

### Running Tests

```bash
make test
# OR
make test/docker # if running with Docker Compose
```

---

## Configuration

Settings are selected via the `DJANGO_SETTINGS_MODULE` environment variable:

| Environment | Settings Module | Config File |
|---|---|---|
| Local dev | `config.settings.dev` | `.env` |
| Docker dev | `config.settings.docker_dev` | `.env` |
| Test | `config.settings.test` | `.env` |
| Staging | `config.settings.staging` | Docker Secrets |
| Production | `config.settings.prod` | Docker Secrets |


See `.example.env` for all available variables and their defaults.

---

## Deployment

CI/CD is managed via GitHub Actions (`.github/workflows/`). Two pipelines are active:

| Branch | Environment | Steps |
|---|---|---|
| `release` / `preview` | Staging | Build → test → push to GHCR → deploy → health check → Slack notification |
| `main` | Production | Build → test → push to GHCR → deploy → health check → Slack notification |

---

## Contributing

Branch from `main`, make your changes, ensure all tests pass, then open a pull request against `release`.

```bash
# Branch naming
git checkout -b feat/your-feature-name
git checkout -b fix/short-description
```

Before submitting:

```bash
make test
make format
make deadcode
```

---

Built for Verboheit · [verboheit.org](https://verboheit.org)

If you'd like to be a volunteer, please register [here](https://verboheit.org/register?type=volunteer) or [send an email](mailto:verboheitconsulting@gmail.com)