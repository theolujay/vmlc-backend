ARG PYTHON_VERSION=3.13.7
ARG UV_VERSION=0.8.15
ARG GOSU_VERSION=1.17
# ==========================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder-base
ARG UV_VERSION

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        build-essential \
        curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN groupadd --system --gid 999 verboheit && \
    useradd --system --uid 999 --gid verboheit --home /home/verboheit --create-home verboheit

USER verboheit
WORKDIR /home/verboheit/build
ENV PATH="/home/verboheit/.local/bin:${PATH}" \
    UV_CACHE_DIR=/tmp/uv-cache

RUN pip install --no-cache-dir --user uv==${UV_VERSION}
COPY --chown=verboheit:verboheit pyproject.toml uv.lock ./
# ==========================================================================
FROM builder-base AS builder-production

RUN uv sync --only-group prod --frozen --no-cache --compile-bytecode && \
    rm -rf /tmp/uv-cache
# ==========================================================================
FROM builder-base AS builder-development

RUN uv sync --group dev --group test --frozen --no-cache --compile-bytecode && \
    rm -rf /tmp/uv-cache
# ==========================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime-base
ARG GOSU_VERSION

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libmagic1 \
        postgresql-client \
        curl \
        ca-certificates \
        gnupg && \
    export GNUPGHOME="$(mktemp -d)" && \
    gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 && \
    dpkgArch="$(dpkg --print-architecture | awk -F- '{ print $NF }')" && \
    curl -fsSL -o /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/${GOSU_VERSION}/gosu-${dpkgArch}" && \
    curl -fsSL -o /usr/local/bin/gosu.asc "https://github.com/tianon/gosu/releases/download/${GOSU_VERSION}/gosu-${dpkgArch}.asc" && \
    gpg --batch --verify /usr/local/bin/gosu.asc /usr/local/bin/gosu && \
    chmod +x /usr/local/bin/gosu && \
    gosu --version && \
    rm -rf "${GNUPGHOME}" /usr/local/bin/gosu.asc && \
    apt-get purge -y gnupg && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PYTHONIOENCODING=utf-8 \
    TERM=xterm-256color

RUN groupadd --system --gid 999 verboheit && \
    useradd --system --uid 999 --gid verboheit --home /home/verboheit --create-home verboheit

USER verboheit
WORKDIR /home/verboheit/web
# ==========================================================================
FROM runtime-base AS production

COPY --from=builder-production --chown=verboheit:verboheit /home/verboheit/build/.venv /home/verboheit/build/.venv

ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    PYTHONOPTIMIZE=2 \
    SERVER_SOFTWARE= \
    PYTHONPATH=/home/verboheit/web \
    PATH="/home/verboheit/build/.venv/bin:${PATH}"

COPY --chown=verboheit:verboheit . .
RUN chmod +x ./scripts/entrypoint.sh ./scripts/runserver.sh

EXPOSE 8000
ENTRYPOINT ["./scripts/entrypoint.sh"]
CMD ["./scripts/runserver.sh"]

LABEL version="0.3.1" \
      description="Backend service for the Verboheit Mathematics League Competition." \
      maintainer="Joseph Ezekiel <theolujay@gmail.com>"
# ==========================================================================
FROM production AS staging

ENV DJANGO_SETTINGS_MODULE=config.settings.staging \
    PYTHONOPTIMIZE=2 \
    SERVER_SOFTWARE=
# ==========================================================================
FROM runtime-base AS development

COPY --from=builder-development --chown=verboheit:verboheit /home/verboheit/build/.venv /home/verboheit/build/.venv

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
    PYTHONOPTIMIZE=0 \
    PATH="/home/verboheit/build/.venv/bin:${PATH}"

COPY --chown=verboheit:verboheit . .
RUN chmod +x ./scripts/entrypoint.sh ./scripts/runserver.sh

EXPOSE 8000
ENTRYPOINT ["./scripts/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]