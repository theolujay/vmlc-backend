ARG PYTHON_VERSION=3.13.7
ARG UV_VERSION=0.8.15
ARG GOSU_VERSION=1.17
# ==========================================================================
# Builder: Compile dependencies in isolated env  
# ==========================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
ARG UV_VERSION

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        build-essential \
        curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN groupadd --system --gid 1001 verboheit && \
    useradd --system --uid 1001 --gid verboheit --home /home/verboheit --create-home verboheit

USER verboheit
WORKDIR /home/verboheit/build
ENV PATH="/home/verboheit/.local/bin:${PATH}" \
    UV_CACHE_DIR=/tmp/uv-cache
RUN pip install --no-cache-dir --user uv==${UV_VERSION}
COPY --chown=verboheit:verboheit pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache --compile-bytecode --no-dev && \
    rm -rf /tmp/uv-cache

# ==========================================================================
# Base: Common runtime
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
    # Create temp GPG keyring and verify gosu
    export GNUPGHOME="$(mktemp -d)" && \
    gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 && \
    dpkgArch="$(dpkg --print-architecture | awk -F- '{ print $NF }')" && \
    curl -fsSL -o /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/${GOSU_VERSION}/gosu-${dpkgArch}" && \
    curl -fsSL -o /usr/local/bin/gosu.asc "https://github.com/tianon/gosu/releases/download/${GOSU_VERSION}/gosu-${dpkgArch}.asc" && \
    gpg --batch --verify /usr/local/bin/gosu.asc /usr/local/bin/gosu && \
    chmod +x /usr/local/bin/gosu && \
    gosu --version && \
    # Cleanup in single layer
    rm -rf "${GNUPGHOME}" /usr/local/bin/gosu.asc && \
    apt-get purge -y curl gnupg && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1 \
    PYTHONHASHSEED=random \
    PYTHONIOENCODING=utf-8 \
    TERM=xterm-256color \
    PATH="/home/verboheit/build/.venv/bin:${PATH}" \
    DJANGO_SETTINGS_MODULE=config.settings.prod

RUN groupadd --system --gid 1001 verboheit && \
    useradd --system --uid 1001 --gid verboheit --home /home/verboheit --create-home verboheit && \
    mkdir -p /home/verboheit/web/{staticfiles,media,logs} && \
    chown -R verboheit:verboheit /home/verboheit

COPY --from=builder --chown=verboheit:verboheit /home/verboheit/build/.venv /home/verboheit/build/.venv

WORKDIR /home/verboheit/web
COPY --chown=verboheit:verboheit . .

RUN chmod +x ./scripts/entrypoint.sh ./scripts/start.sh && \
    echo "#!/bin/sh\ncurl -f http://localhost:8000/v1/health/ -m 10 || exit 1" > /usr/local/bin/healthcheck.sh && \
    chmod +x /usr/local/bin/healthcheck.sh

    # Create volumes for persistent data
VOLUME ["/home/verboheit/web/staticfiles", "/home/verboheit/web/media", "/home/verboheit/web/logs"]

USER verboheit
EXPOSE 8000

# ==========================================================================
# Development
# ==========================================================================
FROM base AS development
USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        vim \
        redis-tools \
        procps \
        iputils-ping && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

USER verboheit

ENV DJANGO_SETTINGS_MODULE=config.settings.docker_dev \
    PYTHONDEBUG=1 \
    DEBUG=1 \
    PYTHONOPTIMIZE=0

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD /usr/local/bin/healthcheck.sh

ENTRYPOINT ["./scripts/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ==========================================================================
# Staging
# ==========================================================================
FROM base AS staging

ENV DJANGO_SETTINGS_MODULE=config.settings.staging \
    PYTHONOPTIMIZE=2 \
    SERVER_SOFTWARE=

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD /usr/local/bin/healthcheck.sh

ENTRYPOINT ["./scripts/entrypoint.sh"]
CMD ["./scripts/start.sh"]

# ==========================================================================
# Production
# ==========================================================================
FROM base AS production

ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    PYTHONOPTIMIZE=2 \
    SERVER_SOFTWARE= \
    PYTHONPATH=/home/verboheit/web

HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=5 \
    CMD /usr/local/bin/healthcheck.sh

ENTRYPOINT ["./scripts/entrypoint.sh"]  
CMD ["./scripts/start.sh"]

# Metadata
LABEL version="0.1.0" \
      description="Backend service for the Verboheit Mathematics League Competition." \
      maintainer="Joseph Ezekiel <theolujay@gmail.com>"
