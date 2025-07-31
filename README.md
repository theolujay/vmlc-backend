# Verboheit Mathematics League Competition API

This is an API for the [**Verboheit Mathematics League Competition (VMLC)**](https://verboheit.org/). A Django-based platform that powers the registration, examination, scoring, and leaderboard systems for a multi-stage mathematics competition.

The need for this project arose from the vision of scaling the VMLC into a nationwide event. I imagined that the continuous use of general-purpose tools  -- like Google Forms, Sheets, WhatsApp for communications -- may become tedious to work with at large scale. This therefore demands a custom, robust platform for efficient operations, participant management, and permission-controlled workflows. The VMLC API forms the core infrastructure of that system and can be integrated with any web or mobile frontend using the [API documentation](https://vlmc-api.readthedocs.io/latest/).

---

## Features

- **JWT Authentication**: Secure login and access token management
- **Role-Based Access Control**:
  - Candidate roles: `screening`, `league`, `final`, `winner`
  - Staff roles: `volunteer`, `moderator`, `admin`, `owner`
- **Exam & Question Management**:
  - Multi-stage exam creation
  - Question upload & retrieval
  - Permission-based exams
- **Candidate Scoring System**:
  - Manual and automated scoring systems
  - Track scores, histories, and rankings
- **Leaderboard Snapshots**:
  - Toggle visibility and publish updated standings
- **Feature Flags**:
  - Toggle registration
- **API Documentation**:
  - Auto-generated via Swagger/Redoc
  - Human-written docs hosted on Read the Docs
- **Deployment**: Live and stable on [Render](https://render.com/)
- **Visual Schema**:
  - Database Entity Relationship Diagram (ERD) included in docs

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
├── render.yaml         # Render deployment configuration
````

---

## Documentation

Visit the official API documentation for detailed usage instructions, endpoint listings, and role behavior guides:

Read the Docs: **[vlmc-api.readthedocs.io](https://vlmc-api.readthedocs.io/)**

---

## Getting Started (Locally)

To run the project locally:

```bash
# Clone the repository
git clone https://github.com/joseph-ezekiel/vlmc-api.git
cd vlmc-api

# Create virtual environment and activate it
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure database in settings
# Run migrations
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
* Render (for deployment)
* Read the Docs (for documentation)
* Pytest (for testing)

---

<!-- ## License

This project is currently under a **proprietary license** intended for use within the Verboheit competition ecosystem. All rights reserved.

---

### Collaboration

 

--- -->

---

## Contact

For support or API key requests, contact:

- Email: `ezekieloluj@gmail.com`
- Discord: `@olujay`

---