# syntax=docker/dockerfile:1
# python:3.12.11-slim-bookworm, pinned to its multi-platform manifest.
FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY requirements-prod.txt requirements-prod.lock ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip==25.0.1 \
    && /opt/venv/bin/pip install --requirement requirements-prod.txt

FROM alpine:3.20 AS default-bots

WORKDIR /build
COPY players/builtin_player.c ./builtin_player.c
RUN apk add --no-cache build-base \
    && mkdir -p /out \
    && cc -O2 -static -s -DBOARD_SIZE=3 -o /out/tictactoe builtin_player.c \
    && cc -O2 -static -s -DBOARD_SIZE=7 -DCONNECT_FOUR=1 -o /out/connect-four builtin_player.c

FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS runtime

ARG VERSION=dev
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="AhinArena API" \
      org.opencontainers.image.description="AhinArena FastAPI production service" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/inhabae/AhinArena"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEPLOY_ENVIRONMENT=production \
    REQUIRE_SECURE_COOKIES=true

RUN groupadd --gid 10001 ahinarena \
    && useradd --uid 10001 --gid ahinarena --create-home --shell /usr/sbin/nologin ahinarena

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY api ./api
COPY engine ./engine
COPY --from=default-bots /out ./default-bots

USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["uvicorn", "api.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
