# Multi-stage build with uv for faster Python package installation
FROM python:3.13.7-slim-bookworm AS builder

# Install system dependencies with cleanup in same layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        curl \
        libpq-dev \
        build-essential && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create a non-root user with a home directory
RUN addgroup --system app && \
    adduser --system --group --home /home/app app

# Switch to the non-root user
USER app

# Set the working directory to the user's home directory
WORKDIR /home/app

# Set PATH to include user's local bin
ENV PATH="/home/app/.local/bin:${PATH}"

# Install uv with pinned version for reproducibility
RUN pip install --no-cache-dir --user uv==0.8.15

# Switch back to root to create and own the venv
USER root
RUN mkdir /.venv && chown -R app:app /.venv

# Switch back to the non-root user
USER app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install Python dependencies with uv using project mode
RUN uv sync \
        --frozen \
        --no-cache \
        --compile-bytecode

# Set PATH to use uv's installed packages
ENV PATH="/.venv/bin:${PATH}"

# =============================================================================
# Base runtime stage - shared between all environments
FROM python:3.13.7-slim-bookworm AS base

# Install minimal runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libmagic1 \
        curl && \
    # Install gosu for user switching
    curl -o /usr/local/bin/gosu -sL "https://github.com/tianon/gosu/releases/download/1.17/gosu-$(dpkg --print-architecture)" && \
    chmod +x /usr/local/bin/gosu && \
    gosu --version && \
    # Remove curl and cleanup
    apt-get remove -y curl && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Python environment settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/.venv/bin:${PATH}" \
    TERM=xterm-256color

# Create non-root user and directories
RUN addgroup --system app && \
    adduser --system --group --home /home/app app && \
    mkdir -p /home/app/web/staticfiles /home/app/web/media /home/app/web/logs && \
    chown -R app:app /home/app

# Copy virtual environment from builder stage
COPY --from=builder /.venv /.venv

# Set working directory
WORKDIR /home/app/web

# Copy entrypoint and make executable
COPY --chown=app:app entrypoint.sh ./
RUN chmod +x ./entrypoint.sh

# Copy application code with proper ownership
COPY --chown=app:app . .

# Expose port
EXPOSE 8000

# =============================================================================
# Development stage - includes development tools and hot-reloading support
FROM base AS development

# Install development tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        vim \
        postgresql-client \
        redis-tools && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Development-specific environment settings
ENV PYTHONDEBUG=1 \
    DJANGO_SETTINGS_MODULE=config.settings.docker_dev

# Development health check (simple check that doesn't require specific endpoints)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=2 \
    CMD python -c "import django; django.setup(); from django.db import connection; connection.ensure_connection()" || exit 1

# Use entrypoint script with Django development server
ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# =============================================================================
# Staging stage - production-like but with some debugging capabilities
FROM base AS staging

# Minimal additional tools for staging debugging
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Staging environment settings
ENV PYTHONOPTIMIZE=1 \
    DJANGO_SETTINGS_MODULE=config.settings.staging

# Staging health check (assumes you have a basic health endpoint)
HEALTHCHECK --interval=45s --timeout=10s --start-period=45s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health/', timeout=5)" || exit 1

# Use gunicorn but with more debugging-friendly settings
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--log-level", "info"]

# =============================================================================
# Production stage - optimized for performance and security
FROM base AS production

# Production environment settings
ENV PYTHONOPTIMIZE=2 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# Production health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health/', timeout=5)" || exit 1

# Use entrypoint script with optimized gunicorn settings
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "gevent", "--worker-connections", "1000"]
