# `scripts` Directory

This directory contains various shell scripts used for automating common development, deployment, and maintenance tasks for the VMLC backend. These scripts are designed to streamline workflows and ensure consistency across different environments.

## Scripts and Their Functions

-   **`backup-crontab.txt`**: This file likely contains a crontab entry or configuration snippet used to schedule automated execution of backup tasks, such as `db-backup.sh`, at regular intervals.
-   **`build.sh`**: A versatile shell script responsible for building various components of the project. This could include:
    -   Building Docker images for the application.
    -   Compiling static assets (e.g., frontend code if applicable).
    -   Running build-related checks or optimizations.
-   **`db-backup.sh`**: A dedicated script for performing database backups. It typically handles:
    -   Connecting to the database (e.g., PostgreSQL).
    -   Dumping the database contents to a file (e.g., using `pg_dump`).
    -   Compressing the backup file.
    -   Potentially uploading the backup to remote storage (e.g., S3).
    -   Logging the backup operation (possibly interacting with `comms.models.BackupLog`).
-   **`db-restore.sh`**: A script designed to restore the database from a previously created backup. It would typically:
    -   Decompress the backup file.
    -   Connect to the database.
    -   Load the data from the backup file into the database (e.g., using `psql`).
    -   This script should be used with extreme caution as it can overwrite existing data.
-   **`deploy.sh`**: Handles the deployment process of the application to a target environment (e.g., staging, production). This script might orchestrate:
    -   Fetching the latest code.
    -   Building new Docker images (using `build.sh`).
    -   Running database migrations (`runmigrations.sh`).
    -   Restarting application services.
    -   Performing health checks.
-   **`entrypoint.sh`**: This script serves as the entrypoint for Docker containers. When a Docker container based on this project's `Dockerfile` starts, `entrypoint.sh` is the first command executed. It typically performs initial setup steps, such as:
    -   Waiting for the database to be available.
    -   Running migrations.
    -   Collecting static files.
    -   Starting the application server (e.g., Gunicorn for Django).
-   **`make-secrets.sh`**: A utility script for generating cryptographic keys, random strings, or other sensitive configuration values that are essential for application security (e.g., Django `SECRET_KEY`, API keys, database passwords). These generated secrets are usually stored in `.env` files or environment variables.
-   **`runmigrations.sh`**: Executes Django database migrations, applying schema changes and data migrations to the database. This is a critical step during deployments and database updates.
-   **`runserver.sh`**: A convenience script for starting the Django development server. It often includes:
    -   Setting up environment variables.
    -   Running `python manage.py runserver` with specific options.
    -   Useful for local development and testing.
-   **`update-secret.sh`**: A script intended for updating specific environment variables or secret values, potentially interacting with `.env` files or a secret management system.

## Usage and Best Practices

-   **Automation**: These scripts are primarily for automating repetitive tasks, reducing manual errors.
-   **Environment Variables**: Many scripts might rely on environment variables (e.g., defined in `.env` files or Docker environment configurations) for sensitive data or environment-specific settings.
-   **Permissions**: Ensure that these scripts have appropriate execution permissions (`chmod +x script_name.sh`).
-   **Safety**: Scripts like `db-restore.sh` should be used with extreme care, especially in production environments, due to potential data loss.
-   **Logging**: Scripts often include logging mechanisms to record their execution, success, or failure.

## Interconnections

-   These scripts often call each other (e.g., `deploy.sh` might call `build.sh` and `runmigrations.sh`).
-   `db-backup.sh` interacts with the database and potentially the `comms` application (via `comms.utils.send_backup_status_to_slack` or `comms.models.BackupLog`) for logging backup status.
-   `entrypoint.sh` sets up the environment before starting the main application process.
-   They are crucial for the CI/CD pipeline and operational maintenance of the VMLC backend.
