import os

import httpx


RESEND_EMAILS_URL = "https://api.resend.com/emails"
EMAIL_DELIVERY_MODE_ENV_VAR = "EMAIL_DELIVERY_MODE"
EMAIL_DELIVERY_MODE_DISABLED = "disabled"


class EmailDeliveryError(RuntimeError):
    pass


class EmailDeliveryConfigurationError(EmailDeliveryError):
    pass


def is_email_delivery_configured() -> bool:
    if os.environ.get(EMAIL_DELIVERY_MODE_ENV_VAR, "").strip().lower() == EMAIL_DELIVERY_MODE_DISABLED:
        return False

    return bool(os.environ.get("RESEND_API_KEY") and os.environ.get("EMAIL_FROM"))


def _resend_config() -> tuple[str, str]:
    api_key = os.environ.get("RESEND_API_KEY")
    email_from = os.environ.get("EMAIL_FROM")

    if not api_key or not email_from:
        raise EmailDeliveryConfigurationError(
            "RESEND_API_KEY and EMAIL_FROM must both be set to send email."
        )

    return api_key, email_from


def send_email(*, to: str, subject: str, text: str, html: str) -> None:
    api_key, email_from = _resend_config()
    timeout = float(os.environ.get("EMAIL_DELIVERY_TIMEOUT_SECONDS", "10"))

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                RESEND_EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": email_from,
                    "to": [to],
                    "subject": subject,
                    "text": text,
                    "html": html,
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise EmailDeliveryError(
            f"Email provider rejected the message with status {exc.response.status_code}."
        ) from exc
    except httpx.HTTPError as exc:
        raise EmailDeliveryError("Email provider request failed.") from exc


def send_verification_email(*, to: str, username: str, verification_url: str) -> None:
    send_email(
        to=to,
        subject="Verify your AhinArena email",
        text=(
            "Welcome to AhinArena! Please verify your email address to activate your account.\n\n"
            f"Verify your email: {verification_url}\n\n"
            "This link expires in 48 hours. If you didn't create an account, "
            "you can safely ignore this email.\n\n"
            "-- AhinLab"
        ),
        html=(
            "<p>Welcome to AhinArena! Please verify your email address to activate your account.</p>"
            f'<p>Verify your email: <a href="{verification_url}">{verification_url}</a></p>'
            "<p>This link expires in 48 hours. If you didn't create an account, "
            "you can safely ignore this email.</p>"
            "<p>-- AhinLab</p>"
        ),
    )


def send_password_reset_email(*, to: str, username: str, reset_url: str) -> None:
    send_email(
        to=to,
        subject="Reset your AhinArena password",
        text=(
            "Reset your AhinArena password using the link below.\n\n"
            f"Reset your password: {reset_url}\n\n"
            "This link expires in 1 hour. If you didn't request a password reset, "
            "you can safely ignore this email.\n\n"
            "-- AhinLab"
        ),
        html=(
            "<p>Reset your AhinArena password using the link below.</p>"
            f'<p>Reset your password: <a href="{reset_url}">{reset_url}</a></p>'
            "<p>This link expires in 1 hour. If you didn't request a password reset, "
            "you can safely ignore this email.</p>"
            "<p>-- AhinLab</p>"
        ),
    )
