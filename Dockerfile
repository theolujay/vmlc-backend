# Multi-stage build with uv for faster Python package installation
FROM python:3.13.1-slim-bookworm AS builder

# Install system dependencies with cleanup in same layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        build-essential && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install uv with pinned version for reproducibility
RUN pip install --no-cache-dir uv==0.4.30

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install Python dependencies with uv using project mode
RUN uv sync \
        --frozen \
        --no-cache \
        --compile-bytecode

# Set PATH to use uv's installed packages
ENV PATH="/.venv/bin:$PATH"

# Production stage
FROM python:3.13.1-slim-bookworm AS production

# Install runtime dependencies and gosu in single layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libmagic1 \
        curl && \
    # Install gosu
    curl -o /usr/local/bin/gosu -sL "https://github.com/tianon/gosu/releases/download/1.17/gosu-$(dpkg --print-architecture)" && \
    chmod +x /usr/local/bin/gosu && \
    gosu --version && \
    # Cleanup in same layer
    apt-get remove -y curl && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Python environment settings (consolidated for fewer layers)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2 \
    PATH="/.venv/bin:$PATH"

# Create non-root user and directories in single layer
RUN addgroup --system app && \
    adduser --system --group app && \
    mkdir -p /home/app/web/staticfiles /home/app/web/media && \
    chown -R app:app /home/app/web

# Copy virtual environment from builder stage
COPY --from=builder /.venv /.venv

# Set working directory
WORKDIR /home/app/web

# Copy application code with proper ownership (exclude files via .dockerignore)
COPY --chown=app:app . .

# Make entrypoint executable and validate it exists
RUN chmod +x ./entrypoint.sh && \
    test -f ./entrypoint.sh

# Add health check for Django
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD gosu app python -c "import requests; requests.get('http://localhost:8000/', timeout=5)" || exit 1

# Expose port
EXPOSE 8000

# Use entrypoint script with optimized gunicorn settings
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]