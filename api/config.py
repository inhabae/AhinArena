import os
from urllib.parse import urlparse

from api.env import load_dotenv


load_dotenv()


def get_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set to connect to the database.")
    return database_url


def _required(name: str, errors: list[str]) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        errors.append(f"{name} must be set in production.")
    return value


def _is_true(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_https_origin(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and not parsed.username
        and not parsed.password
        and parsed.path in ("", "/")
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )


def validate_production_configuration(*, require_sandbox: bool = False) -> None:
    """Fail fast when a production process has an unsafe or incomplete config."""
    if os.environ.get("DEPLOY_ENVIRONMENT", "").strip().lower() != "production":
        return

    errors: list[str] = []
    database_url = _required("DATABASE_URL", errors)
    if database_url and not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        errors.append("DATABASE_URL must use a PostgreSQL URL in production.")

    cors_raw = _required("CORS_ALLOWED_ORIGINS", errors)
    origins = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
    if not origins:
        errors.append("CORS_ALLOWED_ORIGINS must contain at least one explicit HTTPS origin in production.")
    elif any(origin == "*" or not _is_https_origin(origin) for origin in origins):
        errors.append("CORS_ALLOWED_ORIGINS must contain only explicit HTTPS origins; wildcards and paths are unsafe.")

    frontend_url = _required("FRONTEND_URL", errors)
    if frontend_url and not _is_https_origin(frontend_url):
        errors.append("FRONTEND_URL must be an HTTPS origin in production.")

    if not _is_true(_required("REQUIRE_SECURE_COOKIES", errors)):
        errors.append("REQUIRE_SECURE_COOKIES must be true in production.")

    resend_api_key = _required("RESEND_API_KEY", errors)
    email_from = _required("EMAIL_FROM", errors)
    if resend_api_key and len(resend_api_key) < 16:
        errors.append("RESEND_API_KEY appears invalid; provide the complete secret from the email provider.")
    if email_from and "@" not in email_from:
        errors.append("EMAIL_FROM must be a valid sender address (optionally with a display name).")

    if require_sandbox:
        sandbox_image = _required("BOT_SANDBOX_IMAGE", errors)
        if sandbox_image and "@sha256:" not in sandbox_image:
            errors.append("BOT_SANDBOX_IMAGE must be pinned by digest in production.")
        for name in ("DOCKER_BINARY", "BOT_SANDBOX_TEMP_DIR", "BOT_SANDBOX_MEMORY_LIMIT", "BOT_SANDBOX_CPU_LIMIT", "BOT_SANDBOX_PIDS_LIMIT", "BOT_SANDBOX_TMPFS_SIZE"):
            _required(name, errors)

    if errors:
        raise RuntimeError("Invalid production configuration:\n- " + "\n- ".join(errors))
