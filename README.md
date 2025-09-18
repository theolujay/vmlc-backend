# vmlc-backend

This is the backend service for the Verboheit Mathematics League Competition (VMLC).
It provides APIs for participant registration, exams, scoring, leaderboards, and role-based workflows.

Built with Django and Django REST Framework, this project is designed to scale and integrates with PostgreSQL, Redis, and Celery. Frontends (web or mobile) will consume this API.

---

## Features

- **Comprehensive User Authentication**: Implemented full OTP-based email verification and secure password reset flows. Enhanced JWT login to include detailed candidate/staff profile information. API key protection for public endpoints using the `X-Api-Key` header.
- **Refined Role-Based Access Control (RBAC)**: Expanded and clarified permissions for all candidate and staff roles (`volunteer`, `moderator`, `admin`, `superadmin`), ensuring fine-grained access control across all API endpoints.
- **Advanced User Verification System**: Introduced a multi-step verification process with secure document uploads (profile photos, ID cards, verification documents), asynchronous validation, and secure access to private documents via AWS S3 signed URLs.
- **Multi-stage Competition Structure**: Supports `screening`, `league`, and `final` stages for exams and candidate progression.
- **Enhanced Exam Management**: Improved exam workflow for candidates, including bulk answer submission, robust eligibility checks, prevention of re-submission, and asynchronous auto-scoring. Added manual score submission for staff.
- **Dynamic Scoring & Leaderboards**: Implemented asynchronous generation and publishing of score and leaderboard snapshots. Introduced feature-flagged control for leaderboard visibility.
- **Personalized Dashboards**: Developed cached dashboard endpoints for both candidates and staff, with asynchronous updates for improved performance and user experience.
- **Asynchronous Operations**: Extensive use of Celery for various background tasks (email sending, file validation, score calculation, leaderboard/score snapshot generation), significantly boosting API responsiveness and scalability.
- **Feature Flag System**: Introduced a generic `FeatureFlag` model and associated views to dynamically enable/disable key application features (e.g., candidate/staff registration, leaderboard visibility).
- **Health Check Endpoint**: For monitoring API operational status.
- **Interactive API Documentation**: Powered by Swagger UI and ReDoc for easy API exploration.
- **Dockerized Setup**: For development and staging environments.

---

## Project Structure

```bash
vmlc-backend/
├── vmlc/                 # Core Django app containing models, views, and serializers
├── config/              # Project settings, ASGI/WSGI entrypoints, and URL configurations
├── docs/                # Project documentation
├── scripts/             # Utility scripts for entrypoint, start, and build
├── staticfiles/         # Collected static files for production
├── manage.py            # Django's command-line utility for administrative tasks
├── requirements.txt     # Python application dependencies
├── Dockerfile           # Defines the Docker image for the application
├── compose.yml          # Base Docker Compose configuration for all environments
├── compose.prod.yml     # Production-specific Docker Compose configuration
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
* AWS S3 (for media storage)

---

## Deployment

The VMLC backend is deployed on [Render](https://render.com/).

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