# Verboheit Mathematics League Competition API

This is an API for the [**Verboheit Mathematics League Competition (VMLC)**](https://verboheit.org/). A Django-based platform that powers the registration, examination, scoring, and leaderboard systems for a multi-stage mathematics competition.

The need for this project arose from the vision of scaling the VMLC into a nationwide event. I imagined that the continuous use of general-purpose tools  -- like Google Forms, Sheets, WhatsApp for communications -- may become tedious to work with at large scale. This therefore demands a custom, robust platform for efficient operations, participant management, and permission-controlled workflows. The VMLC API forms the core infrastructure of that system and can be integrated with any web or mobile frontend using the [API documentation](https://vlmc-api.readthedocs.io/latest/).

---

## Features

The VMLC API is built with a rich set of features to manage the entire competition lifecycle:

### User Management & Security
- **Secure Authentication**: JWT-based authentication with access/refresh tokens, API key protection for public endpoints, and a secure OTP-based password reset flow.
- **Role-Based Access Control (RBAC)**: Granular permissions for different user types.
  - **Candidate Roles**: `screening`, `league`, `final`, `winner`
  - **Staff Roles**: `volunteer`, `moderator`, `admin`, `owner`
- **User Registration & Verification**: Separate registration flows for candidates and staff, with a document upload system for user verification.
- **Account Management**: Endpoints for users to manage their own profile data.
- **Admin Controls**: Feature flags to toggle candidate and staff registration.

### Competition & Exam Engine
- **Comprehensive Exam Management**: Create, update, and manage multi-stage exams (`screening`, `league`).
- **Detailed Question Bank**: A robust system for managing questions with difficulty levels, options, and correct answers.
- **Automated & Manual Scoring**:
  - Candidates can take exams and submit answers for automated grading.
  - Staff can manually submit or override scores.
- **Exam History**: Track each candidate's performance and exam history.

### Data & Insights
- **Personalized Dashboards**: Separate dashboard views for candidates and staff, providing relevant stats and information at a glance.
- **Dynamic Leaderboard**: A real-time leaderboard system with controls for publishing and visibility.
- **Score Publishing**: System to take a snapshot of all scores for official publication.

### Developer Experience
- **Rich API Documentation**:
  - Interactive documentation via Swagger UI and ReDoc.
  - Comprehensive, human-written guides hosted on Read the Docs.
- **Containerized & Deployment Ready**: Dockerized for consistent environments and pre-configured for deployment on platforms like Render.
- **Visual Database Schema**: An Entity Relationship Diagram (ERD) is included in the documentation to visualize data models.

---

## Project Structure

```bash
verboheit_mlc/
├── api/                # DRF models, views, serializers, permissions, URL paths, and tests
├── core/               # Project settings and ASGI/WGI configuration
├── docs/               # Sphinx documentation, database ERD
├── staticfiles/        # Collected static files for deployment
├── manage.py           # Django entry point
├── requirements.txt    # All project dependencies
├── Dockerfile          # Containerization configuration
````

---

## Documentation

Visit the official API documentation for detailed usage instructions, endpoint listings, and role behavior guides:

Read the Docs: **[vlmc-api.readthedocs.io](https://vlmc-api.readthedocs.io/)**s

---

## Getting Started

There are two ways to run the project locally: using Docker (recommended for consistency) or setting up a manual Python environment.

### With Docker (Recommended)

This project is fully containerized using Docker and Docker Compose, which is the recommended way to run it locally. This setup includes the web server, a PostgreSQL database, Redis for caching/messaging, and Celery for background tasks.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/joseph-ezekiel/vlmc-api.git
    cd vlmc-api
    ```

2.  **Set up environment variables:**
    Copy the example environment file. The default values are configured to work with the `docker-compose` setup out of the box.
    ```bash
    cp .env.example .env
    ```

3.  **Build and run the services:**
    ```bash
    docker-compose up --build
    ```
    This will build the images and start all the services. The API will be available at `http://localhost:8000`.

4.  **Run database migrations (in a separate terminal):**
    Once the containers are running, open a new terminal and run the initial database migrations.
    ```bash
    docker-compose exec web python manage.py migrate
    ```

#### Running Management Commands
To run any `manage.py` command, use `docker-compose exec web`:
```bash
docker-compose exec web python manage.py createsuperuser
```

### Manual Setup

```bash
# Clone the repository
git clone https://github.com/joseph-ezekiel/vlmc-api.git
cd vlmc-api

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set up your .env file and configure settings in config/settings/dev.py
# Run database migrations
python manage.py migrate

# Start the server
python manage.py runserver
```

---

## Tech Stack

* Python 3.13
* Django 5+
* Django REST Framework
* PostgreSQL (via AWS RDS)
* Amazon S3 (for media file storage)
* Docker (for containerization)
* Render (for deployment & hosting)
* Read the Docs (for documentation)
* Pytest (for testing)

---

## License

This project is currently under a **proprietary license** intended for use within the Verboheit competition ecosystem. All rights reserved.

---

## Contributing

As this project is for a specific organization, the repository is private and contributions are managed internally. If you are a team member, please follow the standard fork-and-pull-request workflow on our private repository.

Ensure your code adheres to the existing style (checked with `black` and `isort`) and that all tests pass before submitting a pull request.

---

## Contact

For support or API key requests, contact:

- Email: `olujay.dev@gmail.com`
- Discord: `@olujay`

---