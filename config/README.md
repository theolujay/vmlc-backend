# `config` Directory

The `config` directory houses the core configuration files for the Django project. It defines how the application behaves, connects to services, handles URLs, and manages settings for different environments.

## Key Modules and Their Responsibilities

-   **`__init__.py`**: Marks the `config` directory as a Python package.
-   **`asgi.py`**: Entry point for ASGI-compatible web servers (like Daphne or Uvicorn). It defines the ASGI application callable, primarily used for WebSocket and asynchronous request handling.
-   **`celery.py`**: Configures Celery, the asynchronous task queue. It defines the Celery application instance, loads task modules, and sets up broker/backend connections.
-   **`gunicorn.conf.py`**: Configuration file for Gunicorn, a Python WSGI HTTP server. This file specifies settings like the number of worker processes, binding address, timeouts, and logging for serving the Django application in production environments.
-   **`otel.py`**: Likely configuration for OpenTelemetry integration, setting up tracing, metrics, or logging exporters for observability purposes. It would define how telemetry data is collected and sent to services like Jaeger, Prometheus, or Loki.
-   **`urls.py`**: The project's main URL configuration. It includes URL patterns from various Django applications (e.g., `vmlc`, `comms`) and defines top-level routes for the API.
-   **`workers.py`**: Potentially defines or configures specific worker processes, possibly related to Celery tasks or other background processing.
-   **`wsgi.py`**: Entry point for WSGI-compatible web servers (like Gunicorn or uWSGI). It defines the WSGI application callable, used for synchronous HTTP request handling.
-   **`settings/`**: This subdirectory contains modularized Django settings files for different deployment environments.
    -   **`__init__.py`**: Manages which settings file is active based on environment variables (e.g., `DJANGO_SETTINGS_MODULE`).
    -   **`_utils.py`**: Helper utilities or common functions used across different settings files.
    -   **`base.py`**: Contains the default and common settings applicable to all environments (e.g., `SECRET_KEY`, `INSTALLED_APPS`, `MIDDLEWARE`, database configurations, static files, REST Framework settings).
    -   **`dev.py`**: Development-specific settings (e.g., `DEBUG=True`, local database, specific logging configurations).
    -   **`docker_dev.py`**: Settings for development within a Docker environment, potentially overriding database connections or other service URLs to point to Docker containers.
    -   **`prod.py`**: Production-specific settings (e.g., `DEBUG=False`, production database, strong logging, email backend, allowed hosts).
    -   **`staging.py`**: Staging-specific settings, typically mirroring production but for testing purposes.
    -   **`test.py`**: Settings optimized for running tests (e.g., in-memory database, faster password hashers).
    -   **`__pycache__/`**: Python bytecode cache.

## Interconnections

-   The main `urls.py` in `config` includes `urlpatterns` from `vmlc/urls.py` and `comms/urls.py`.
-   `celery.py` integrates with tasks defined in `vmlc/tasks.py` and `comms/tasks.py`.
-   `asgi.py` and `wsgi.py` are crucial for deploying the application with web servers.
-   The `settings/` modules determine the entire behavior of the Django application, affecting database connections (potentially with `docker/postgresql/`), caching, email, and logging.
-   `otel.py` is likely configured to send telemetry data to the infrastructure services defined in `infra/otel.yml`.

This directory is central to configuring and running the entire VMLC backend application.