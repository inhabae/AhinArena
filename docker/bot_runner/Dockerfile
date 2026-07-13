# Build from the repository root:
# docker build -t ahinarena-bot-runner:latest -f docker/bot_runner/Dockerfile .
FROM python:3.12-slim

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 sandbox \
    && useradd \
        --uid 10001 \
        --gid sandbox \
        --no-create-home \
        --home-dir /nonexistent \
        --shell /usr/sbin/nologin \
        sandbox \
    && mkdir -p /app /bot \
    && chown root:root /app /bot \
    && chmod 0555 /app /bot

WORKDIR /bot

COPY --chown=root:root engine /app/engine

RUN find /app/engine -type d -name __pycache__ -prune -exec rm -rf {} + \
    && find /app/engine -type f -name '*.py[co]' -delete \
    && chmod -R a-w /app/engine

USER sandbox:sandbox

ENTRYPOINT ["python", "/bot/source.py"]
