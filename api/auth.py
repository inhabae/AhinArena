import bcrypt


def password_security_errors(password: str) -> list[str]:
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if len(password) > 72:
        errors.append("Password must be 72 characters or fewer.")
    if not any(character.islower() for character in password):
        errors.append("Password must include a lowercase letter.")
    if not any(character.isupper() for character in password):
        errors.append("Password must include an uppercase letter.")
    if not any(character.isdigit() for character in password):
        errors.append("Password must include a number.")
    if not any(not character.isalnum() for character in password):
        errors.append("Password must include a symbol.")
    return errors


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
