# vmlc-backend

This is the backend service for the Verboheit Mathematics League Competition (VMLC).
It provides APIs for participant registration, exams, scoring, leaderboards, and role-based workflows.

Built with Django and Django REST Framework, this project is designed to scale and integrates with PostgreSQL, Redis, and Celery. Frontends (web or mobile) will consume this API.

---

## Features

- JWT authentication with refresh tokens
- Role-based access control (RBAC) for staff and participants
- Secure document storage and verification
- Multi-stage competition structure (screening, league, final)
- Automated and manual scoring workflows
- Real-time leaderboard management
- Health Check endpoint for API operational status
- Swagger UI and ReDoc documentation
- Dockerized setup for development and staging environments.

---

## Project Structure


```bash
vmlc-backend/
├── vmlc/                 # Core Django app containing models, views, and serializers
├── config/              # Project settings, ASGI/WSGI entrypoints, and URL configurations
├── docs/                # Project documentation
├── staticfiles/         # Collected static files for production
├── manage.py            # Django's command-line utility for administrative tasks
├── requirements.txt     # Python application dependencies
├── build.sh             # Enhanced build script with intelligent error logging
├── Dockerfile           # Defines the Docker image for the application
├── compose.yml          # Base Docker Compose configuration for all environments
├── compose.override.yml # Development-specific Docker Compose overrides
├── compose.staging.yml  # Staging-specific Docker Compose configuration
````

---

## Setup

### Docker (Recommended)

The project is configured to run in multiple environments using Docker Compose.

**For Development:**

```bash
git clone https://github.com/theolujay/vmlc-backend.git
cd vmlc-backend

cp .env.example .env
docker compose up --build
docker compose exec web python manage.py migrate
```

App runs at `http://localhost:8000`.

For automating error logging, you can use the `compose_up.sh` script. It starts the containers and logs errors to a file.

**For Staging:**

```bash
git clone https://github.com/theolujay/vmlc-backend.git
cd vmlc-backend

cp .env.example .staging.env
# Update .stagin.env with staging-specific settings
docker compose -f compose.yml -f compose.staging.yml up -d --build
docker compose -f compose.yml -f compose.staging.yml exec web python manage.py migrate
```

---

### Manual Setup

```bash
git clone https://github.com/theolujay/vmlc-backend.git
cd vmlc-backend

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

---

## Testing

To run the test suite, use the following command:

```bash
pytest
```

---

## Tech Stack

* Python 3.13
* Django 5.x
* Django REST Framework
* PostgreSQL
* Redis
* Celery
* Docker & Docker Compose
* Pytest

---

## Deployment

Future `infra/` directory will include:

* Docker Compose orchestration (backend, frontend, db, redis, nginx)
* CI/CD pipelines
* Backup and restore scripts
* Reverse proxy configurations

---

## License

Proprietary. For internal VMLC use only.

---

## Contact

* X: [@theolujay](https://x.com/theolujay)
* Email: [theolujay@gmail.com](mailto:theolujay@gmail.com)
* GitHub Issues: [vmlc-backend](https://github.com/theolujay/vmlc-backend/issues)

---

## Known Build Warnings

The Docker build process may produce the following warnings:

*   `update-alternatives: warning: skip creation of ...`

These warnings are expected and can be safely ignored. The `build.sh` script is configured to handle these warnings and will not fail the build because of them. The build will only be marked as failed if other, unexpected errors occur.
