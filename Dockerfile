# Multi-stage build with uv for faster Python package installation
FROM python:3.13.1-slim-bookworm AS builder

# Install system dependencies needed for building Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install uv - much faster than pip
RUN pip install --no-cache-dir uv

# Create virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN uv venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies with uv
RUN uv pip install \
    --no-cache \
    -r requirements.txt

# Production stage
FROM python:3.13.1-slim-bookworm

# Install runtime dependencies only
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Install gosu for proper user switching
RUN set -eux; \
    curl -o /usr/local/bin/gosu -sL "https://github.com/tianon/gosu/releases/download/1.17/gosu-$(dpkg --print-architecture)"; \
    chmod +x /usr/local/bin/gosu; \
    gosu --version

# Python environment settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Create non-root user
RUN addgroup --system app && adduser --system --group app

# Copy virtual environment from builder stage
COPY --from=builder $VIRTUAL_ENV $VIRTUAL_ENV

# Set working directory
WORKDIR /home/app/web

# Copy application code with proper ownership
COPY --chown=app:app . .

# Make entrypoint executable
RUN chmod +x ./entrypoint.sh

# Directories will be created by entrypoint.sh at runtime

# Expose port
EXPOSE 8000

# Use entrypoint script
ENTRYPOINT ["/home/app/web/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]