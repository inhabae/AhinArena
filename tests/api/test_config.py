import pytest

from api.config import validate_production_configuration


@pytest.fixture
def production_environment(monkeypatch):
    values = {
        "DEPLOY_ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql+psycopg://user:password@postgres:5432/ahin_arena",
        "CORS_ALLOWED_ORIGINS": "https://arena.example.com",
        "FRONTEND_URL": "https://arena.example.com",
        "REQUIRE_SECURE_COOKIES": "true",
        "RESEND_API_KEY": "re_12345678901234567890",
        "EMAIL_FROM": "AhinArena <noreply@arena.example.com>",
        "BOT_SANDBOX_IMAGE": "registry.example/runner@sha256:" + "a" * 64,
        "DOCKER_BINARY": "docker",
        "BOT_SANDBOX_TEMP_DIR": "/var/lib/ahinarena/bot-sandbox",
        "BOT_SANDBOX_MEMORY_LIMIT": "128m",
        "BOT_SANDBOX_CPU_LIMIT": "0.5",
        "BOT_SANDBOX_PIDS_LIMIT": "64",
        "BOT_SANDBOX_TMPFS_SIZE": "16m",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_production_configuration_accepts_safe_values(production_environment):
    validate_production_configuration(require_sandbox=True)


def test_production_configuration_reports_missing_and_unsafe_values(production_environment, monkeypatch):
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("REQUIRE_SECURE_COOKIES", "false")
    monkeypatch.setenv("BOT_SANDBOX_IMAGE", "ahinarena-bot-runner:latest")

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_configuration(require_sandbox=True)

    message = str(exc_info.value)
    assert "DATABASE_URL must be set" in message
    assert "CORS_ALLOWED_ORIGINS must contain only explicit HTTPS origins" in message
    assert "REQUIRE_SECURE_COOKIES must be true" in message
    assert "BOT_SANDBOX_IMAGE must be pinned by digest" in message


def test_development_configuration_does_not_require_production_values(monkeypatch):
    monkeypatch.setenv("DEPLOY_ENVIRONMENT", "development")
    for name in ("DATABASE_URL", "CORS_ALLOWED_ORIGINS", "FRONTEND_URL", "RESEND_API_KEY", "EMAIL_FROM"):
        monkeypatch.delenv(name, raising=False)

    validate_production_configuration(require_sandbox=True)
