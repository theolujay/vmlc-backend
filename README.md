<div align="center">
  <h1>VMLC Backend</h1>
  <p>
    <strong>Django/DRF ASGI backend for the Verboheit Math League</strong><br>
    A free annual mathematics competition for Nigerian senior secondary students.<br>
    Powers candidate exam-taking, automated scoring, and real-time leaderboards,<br>
    alongside staff management, proctoring, and dashboards.
  </p>
</div>

---

## About

The **Verboheit Mathematics League Competition (VMLC)** is a free annual mathematics competition for senior secondary school students (SS1–SS3) across Nigeria — Lagos, Ogun, Rivers, Cross River, and Abuja.

This backend service powers the entire competition lifecycle: candidate registration and verification, multi-stage exam delivery, automated scoring, cumulative leaderboards, real-time communications, and staff administration tools.

---

## Features

### For Candidates
- **Registration & Identity Verification** — Email OTP, document upload, facial capture
- **Multi-stage Exams** — Screening (MCQ) → 6-Week League → Knockout Final
- **Real-time Leaderboards** — Cumulative league table updated after each round
- **Proctoring** — Heartbeat telemetry, violation tracking, QR-based exam unlock
- **Notifications** — In-app, email, SMS, and WhatsApp broadcasts

### For Staff
- **Candidate & Enrollment Management** — Registration review, stage promotion
- **Exam Authoring & Administration** — Question banks, scheduling, delivery modes
- **Helpdesk** — Thread-based support with auto-assignment and escalation
- **Dashboards & Analytics** — Real-time staff dashboard with cached aggregation
- **Ranking & Results Publishing** — Snapshot-based ranking with scheduled publishing

---

## Competition Stages

| Stage | Format | Details |
|---|---|---|
| **Screening** | Online MCQ | Initial qualifying round; cutoff score determines advancement |
| **League** | Weekly quizzes × 6 weeks | Cumulative standings; top 10 advance to final |
| **Final** | In-person exam | Knockout round among top 10 candidates |

Questions are drawn from the senior secondary mathematics curriculum (WAEC, JAMB, SAT).

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Framework** | Django 5.2, Django REST Framework 3.16 |
| **ASGI Server** | Uvicorn + Gunicorn |
| **Real-time** | Django Channels 4, Redis channel layer |
| **Background Jobs** | Celery 5.5, Celery Beat, Redis broker |
| **Database** | PostgreSQL 17 |
| **Cache / Broker** | Redis 7 |
| **Storage** | AWS S3 via django-storages (public & private) |
| **Auth** | JWT (SimpleJWT), API keys, session fallback |
| **Observability** | OpenTelemetry, Prometheus, Grafana, structured JSON logging |
| **Monitoring** | django-health-check, django-prometheus |

---

## Architecture

```
                    HTTP                          WebSocket
                      |                              |
                ┌─────┴─────┐              ┌────────┴────────┐
                │  Uvicorn  │              │   Daphne/ASGI   │
                │  (Gunicorn)│              │  (Channels)     │
                └─────┬─────┘              └────────┬────────┘
                      │                              │
                ┌─────┴──────────────────────────────┴────────┐
                │               ProtocolTypeRouter             │
                │        (config/asgi.py)                      │
                └─────┬──────────────────────────────┬────────┘
                      │                              │
                ┌─────┴─────┐              ┌────────┴────────┐
                │  REST API  │              │   WebSocket     │
                │  (DRF)    │              │   Consumers     │
                └─────┬─────┘              └────────┬────────┘
                      │                              │
          ┌───────────┼───────────┬──────────────────┘
          │           │           │
    ┌─────┴────┐ ┌───┴───┐ ┌────┴────┐
    │ vmlc/    │ │identity│ │comms/   │
    │ (exams,  │ │ (users,│ │(realtime,│
    │ scoring) │ │ auth)  │ │ support)│
    └──────────┘ └───────┘ └─────────┘
          │
    ┌─────┴────┐
    │competition│
    │(stages,  │
    │rankings) │
    └──────────┘
          │
    ┌─────┴──────────────────────┐
    │        Celery Workers       │
    │  scoring │ emails │ comms  │
    │  files   │ reports│ cache  │
    └────────────────────────────┘
```

The backend is fully ASGI — HTTP and WebSocket traffic share the same port. Heavy operations (scoring, ranking computation, notification dispatch, file processing) are offloaded to Celery workers across named queues.

---

## Project Structure

```
config/              Django project bootstrap
├── settings/        Environment-specific settings (dev, prod, staging, docker_dev)
├── asgi.py          ASGI application + WebSocket routing
├── celery.py        Celery app + beat schedule
└── urls.py          API route registration

identity/            User & authentication
├── models.py        User, Candidate, Staff, EmailOTP, CowrywiseKidProfile
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
├── views.py         Dashboards, rankings, leaderboards, promotions
└── tasks.py         Celery tasks (cache updates, notifications)

comms/               Communications & real-time
├── consumers.py     Unified WebSocket consumer (notifications, helpdesk, broadcasts)
├── middleware.py     DualAuthMiddlewareStack (JWT / session / API key)
├── models.py        HelpdeskThread, Broadcast, Notification, BackupLog
├── tasks.py         Celery tasks (broadcast dispatch, email, SMS)
└── routing.py       WebSocket URL patterns

scripts/             Container lifecycle entrypoints
docker/              Docker support files
infra/               Infrastructure / deployment manifests
```

---

## Quick Start

### Using Docker (recommended)

```bash
cp .example.env .env
docker compose up --build
```

Migrations run automatically via the `db-migrate` service. The Django server, Celery worker, and Celery beat all start once migrations complete.

The API is available at `http://localhost:8000`. Swagger docs at `/docs/swagger/`.

### Local Development

Requires Python 3.13, PostgreSQL, and Redis.

```bash
python -m venv .venv && source .venv/bin/activate
cp .example.env .env
uv sync
python manage.py migrate
python manage.py runserver
```

### Running Tests

```bash
pytest
pytest vmlc/tests        # App-specific tests
pytest comms/tests       # WebSocket consumer tests
```

---

## Configuration

The project uses environment-driven settings via `DJANGO_SETTINGS_MODULE`:

| Environment | Settings Module | Config File |
|---|---|---|
| Local dev | `config.settings.dev` | `.env` |
| Docker dev | `config.settings.docker_dev` | `.env` |
| Test | `config.settings.test` | `.env` |
| Staging | `config.settings.staging` | `.env.staging` |
| Production | `config.settings.prod` | `.env.prod` |

See `.example.env` for all available variables.

---

## API Documentation

Interactive API docs are available when the server is running:

- **Swagger UI** — `/docs/swagger/`
- **ReDoc** — `/docs/redoc/`
- **OpenAPI Schema** — `/docs/schema.json`, `/docs/schema.yaml`

### API Versions

| Version | Prefix | Namespace |
|---|---|---|
| v1 | `/v1/` | Exams, questions, results, candidate management |
| v2 | `/v2/` | Refined registration, proctoring, auto-save, integrity audit |

---

## Deployment

CI/CD is managed via GitHub Actions (`.github/workflows/`):

| Branch | Environment | Pipeline |
|---|---|---|
| `release` / `preview` | Staging | Build, test, deploy to staging infra |
| `main` | Production | Build, test, deploy to production infra |

Both pipelines include: Docker image build → push to GHCR → Docker Stack Deploy → health verification → Slack notification.

---

## Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Run `pytest` and ensure all tests pass
4. Open a pull request against `main`

### Code Style

- Python: Black (88 chars), isort, Ruff
- Linting: `pylint` (configured in pyproject.toml)
- Type checking: MyPy-compatible type hints encouraged

---

<div align="center">
  <p>
    <a href="https://verboheit.org">Verboheit.org</a> ·
    <a href="https://vmlc.verboheit.org">VMLC Landing</a>
  </p>
  <p>
    Built by <a href="https://verboheit.org">Verboheit Consulting</a>
  </p>
</div>
