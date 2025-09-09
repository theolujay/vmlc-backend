ARG PYTHON_VERSION=3.13.7
ARG UV_VERSION=0.8.15
ARG GOSU_VERSION=1.17
# ==========================================================================
#   Builder stage - compile dependencies and prepare virtual environment    
# ==========================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ARG UV_VERSION

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        curl \
        libpq-dev \
        build-essential && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN addgroup --system verboheit && \
    adduser --system --group verboheit --home /home/vmlc

ENV HOME=/home/vmlc

USER verboheit

RUN pip install --no-cache-dir --user uv==${UV_VERSION}

ENV PATH="/home/vmlc/.local/bin:${PATH}"

WORKDIR /home/vmlc/build

COPY --chown=verboheit:verboheit pyproject.toml uv.lock ./

RUN uv sync \
        --frozen \
        --no-cache \
        --compile-bytecode \
        --no-dev

# ==========================================================================
#   Base stage - common for dev, staging, and prod
# ==========================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

ARG GOSU_VERSION

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libmagic1 \
        postgresql-client \
        curl \
        ca-certificates \
        gnupg && \
    # Create temp GPG keyring and pull Tianon's public key
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

RUN addgroup --system --gid 1001 verboheit && \
    adduser --system --uid 1001 --group verboheit && \
    mkdir -p /home/vmlc/web/staticfiles /home/vmlc/web/media /home/vmlc/web/logs && \
    chown -R verboheit:verboheit /home/vmlc/


COPY --from=builder --chown=verboheit:verboheit /home/vmlc/build/.venv /home/vmlc/build/.venv

WORKDIR /home/vmlc/web

COPY --chown=verboheit:verboheit . .

RUN test -f ./entrypoint.sh && \
    chmod +x ./entrypoint.sh && \
    echo "#!/bin/sh\ncurl -f http://localhost:8000/v1/health/ -m 10 || exit 1" > /usr/local/bin/healthcheck.sh && \
    chmod +x /usr/local/bin/healthcheck.sh

USER verboheit

EXPOSE 8000

# ==========================================================================
#   Development stage... w/ config/settings/docker_dev.py and compose.yml
# ==========================================================================
FROM base AS development

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        vim \
        postgresql-client \
        redis-tools \
        curl && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

USER verboheit

ENV DJANGO_SETTINGS_MODULE=config.settings.docker_dev \
    PYTHONDEBUG=1 \
    DEBUG=1

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=2 \
    CMD python manage.py check || exit 1

ENTRYPOINT ["./entrypoint.sh"]

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ==========================================================================
#   Staging stage ... w/ config/settings/staging.py and compose.staging.yml
# ==========================================================================
FROM base AS staging

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client \
        curl && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

USER verboheit

ENV DJANGO_SETTINGS_MODULE=config.settings.staging \
    PYTHONOPTIMIZE=2


ENTRYPOINT ["./entrypoint.sh"]

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--max-requests", "1200", \
     "--max-requests-jitter", "50", \
     "--preload", \
     "--timeout", "30"]


HEALTHCHECK --interval=45s --timeout=10s --start-period=45s --retries=3 \
    CMD /usr/local/bin/healthcheck.sh

# ==========================================================================
#   Production stage ... w/ config/settings/prod.py and compose.prod.yml
# ==========================================================================
FROM base AS production

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/

USER verboheit

ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    PYTHONOPTIMIZE=2 \
    SERVER_SOFTWARE= \
    PYTHONPATH=/home/vmlc/web

ENTRYPOINT ["./entrypoint.sh"]

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--max-requests", "1200", \
     "--max-requests-jitter", "50", \
     "--preload", \
     "--timeout", "30"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /usr/local/bin/healthcheck.sh

LABEL version="0.1.0" \
      description="Backend service for the Verboheit Mathematics League Competition." \
      maintainer="Joseph Ezekiel <theolujay@gmail.com>"
