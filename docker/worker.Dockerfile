# syntax=docker/dockerfile:1
# python:3.12.11-slim-bookworm, pinned to its multi-platform manifest.
FROM docker:27.5.1-cli@sha256:851f91d241214e7c6db86513b270d58776379aacc5eb9c4a87e5b47115e3065c AS docker-cli
FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY requirements-prod.txt requirements-prod.lock ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip==25.0.1 \
    && /opt/venv/bin/pip install --requirement requirements-prod.txt

FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS runtime

ARG VERSION=dev
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="AhinArena worker" \
      org.opencontainers.image.description="AhinArena asynchronous match worker" \
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
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY api ./api
COPY engine ./engine
COPY worker ./worker

USER 10001:10001
ENTRYPOINT ["python", "-m", "worker.main"]
