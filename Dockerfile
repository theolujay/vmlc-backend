ARG GOSU_VERSION=1.17
# ==========================================================================
# Builder: Compile dependencies in isolated env  
# ==========================================================================
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

ARG INSTALL_DEV=false
ARG INSTALL_TEST=false
ARG INSTALL_DOCS=false

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        libffi-dev \
        libpq-dev \
        build-essential \
        curl \
        pkg-config \
        libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked \
    $(if [ "$INSTALL_DOCS" = "true" ]; then echo "--group docs"; fi) \
    $(if [ "$INSTALL_TEST" = "true" ]; then echo "--group test"; fi) \
    $(if [ "$INSTALL_DEV" = "true" ]; then echo "--group dev"; fi)

# ==========================================================================
# Base: Common runtime
# ==========================================================================
FROM python:3.13-slim-bookworm AS base

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
    apt-get purge -y gnupg && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN groupadd --system --gid 999 verboheit \
 && useradd --system --gid 999 --uid 999 --create-home verboheit

COPY --from=builder --chown=verboheit:verboheit /app /app

ENV PATH="/app/.venv/bin:$PATH"

USER verboheit
WORKDIR /app
ENV PYTHONDEBUG=1 \
    DEBUG=1 \
    PYTHONOPTIMIZE=0
RUN mkdir -p media staticfiles && \
    chmod -R 755 media staticfiles && \
    chmod +x ./scripts/*

EXPOSE 8000
# ==========================================================================
# Development
# ==========================================================================
FROM base AS development

ENV DJANGO_SETTINGS_MODULE=config.settings.docker_dev

# ==========================================================================
# Test
# ==========================================================================
FROM base AS test

ENV DJANGO_SETTINGS_MODULE=config.settings.test

# ==========================================================================
# Staging
# ==========================================================================
FROM base AS staging

ENV DJANGO_SETTINGS_MODULE=config.settings.staging \
    PYTHONDEBUG=0 \
    DEBUG=0 \
    PYTHONOPTIMIZE=2 \
    SERVER_SOFTWARE=

FROM base AS production

ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    PYTHONDEBUG=0 \
    DEBUG=0 \
    PYTHONOPTIMIZE=2 \
    SERVER_SOFTWARE=
