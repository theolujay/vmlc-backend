ARG PYTHON_VERSION=3.13.7
ARG UV_VERSION=0.8.15
ARG GOSU_VERSION=1.17

# =============================================================================
# Builder stage - compile dependencies and prepare virtual environment
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ARG UV_VERSION

# Install build dependencies in a single layer with cleanup
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        curl \
        libpq-dev \
        build-essential && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create non-root user for build process
RUN addgroup --system vmlc && \
    adduser --system --group vmlc --home /home/vmlc

# Set home directory for the user
ENV HOME=/home/vmlc

# Install uv with pinned version
USER vmlc
RUN pip install --no-cache-dir --user uv==${UV_VERSION}

# Set up Python environment - Fix PATH to match actual venv location
ENV PATH="/home/vmlc/.local/bin:${PATH}"
WORKDIR /home/vmlc/build

# Copy dependency files for better caching
COPY --chown=vmlc:vmlc pyproject.toml uv.lock ./

# Install dependencies with uv
RUN uv sync \
        --frozen \
        --no-cache \
        --compile-bytecode \
        --no-dev

# =============================================================================
# Base runtime stage with security improvements
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

ARG GOSU_VERSION

# Install runtime dependencies and gosu with checksum verification
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libmagic1 \
        postgresql-client \
        curl \
        ca-certificates \
        gnupg && \
    # Import gosu GPG key for signature verification
    export GNUPGHOME="$(mktemp -d)" && \
    gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 && \
    # Download gosu with checksum verification for security
    dpkgArch="$(dpkg --print-architecture | awk -F- '{ print $NF }')" && \
    curl -o /usr/local/bin/gosu -fsSL "https://github.com/tianon/gosu/releases/download/${GOSU_VERSION}/gosu-${dpkgArch}" && \
    curl -o /usr/local/bin/gosu.asc -fsSL "https://github.com/tianon/gosu/releases/download/${GOSU_VERSION}/gosu-${dpkgArch}.asc" && \
    # Verify gosu signature
    gpg --batch --verify /usr/local/bin/gosu.asc /usr/local/bin/gosu && \
    rm -rf "${GNUPGHOME}" /usr/local/bin/gosu.asc && \
    chmod +x /usr/local/bin/gosu && \
    gosu --version && \
    # Cleanup
    apt-get remove -y curl gnupg && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Security and performance environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1 \
    PATH="/home/vmlc/build/.venv/bin:${PATH}" \
    TERM=xterm-256color \
    # Security: Use Python hash randomization for security (not disable it)
    PYTHONHASHSEED=random

# Create application user with explicit UID/GID for security
RUN addgroup --system --gid 1001 vmlc && \
    adduser --system --uid 1001 --group vmlc && \
    # Create application directories with proper ownership
    mkdir -p /home/vmlc/web/staticfiles /home/vmlc/web/media /home/vmlc/web/logs && \
    chown -R vmlc:vmlc /home/vmlc/

# Copy virtual environment from builder
COPY --from=builder --chown=vmlc:vmlc /home/vmlc/build/.venv /home/vmlc/build/.venv

# Set working directory and copy application code
WORKDIR /home/vmlc/web
COPY --chown=vmlc:vmlc . .

# Validate critical files exist and set permissions
RUN test -f ./entrypoint.sh && \
    chmod +x ./entrypoint.sh && \
    # Create a health check script for better monitoring
    echo "#!/bin/sh\ncurl -f http://localhost:8000/api/health/ -m 10 || exit 1" > /usr/local/bin/healthcheck.sh && \
    chmod +x /usr/local/bin/healthcheck.sh

# Switch to non-root user for security
USER vmlc

# Expose port
EXPOSE 8000

# =============================================================================
# Development stage
FROM base AS development

# Switch back to root to install dev tools, then switch back to vmlc user
USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        vim \
        postgresql-client \
        redis-tools \
        curl && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Development environment variables
ENV DJANGO_SETTINGS_MODULE=config.settings.docker_dev \
    PYTHONDEBUG=1 \
    # Enable Django debug mode for development
    DEBUG=1

USER vmlc

# Simple health check for development
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=2 \
    CMD python manage.py check || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# =============================================================================
# Staging stage
FROM base AS staging

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client \
        curl && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV DJANGO_SETTINGS_MODULE=config.settings.staging \
    PYTHONOPTIMIZE=2

USER vmlc

# Secure health check using our custom script
HEALTHCHECK --interval=45s --timeout=10s --start-period=45s --retries=3 \
    CMD /usr/local/bin/healthcheck.sh

ENTRYPOINT ["./entrypoint.sh"]
# Dynamic worker calculation: (CPU cores * 2) + 1, but default to 2 for staging
# CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-2} --max-requests 1000 --max-requests-jitter 100 --preload --log-level info --access-logfile - --error-logfile -"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]


# =============================================================================
# Production stage
FROM base AS production

# Install curl for health checks in production
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
USER vmlc

# Production environment variables
ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    PYTHONOPTIMIZE=2 \
    # Security: Don't expose server info
    SERVER_SOFTWARE= \
    # Performance: Optimize garbage collection
    PYTHONGC=1 \
    # Security: Restrict module loading
    PYTHONPATH=/home/vmlc/web

# Secure health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /usr/local/bin/healthcheck.sh

ENTRYPOINT ["./entrypoint.sh"]
# Production gunicorn with dynamic workers and security hardening
# CMD ["sh", "-c", "WORKERS=${GUNICORN_WORKERS:-$(($(nproc) * 2 + 1))} && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers $WORKERS --max-requests 1200 --max-requests-jitter 50 --preload --timeout 30 --log-level warning --access-logfile - --error-logfile - --capture-output"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
