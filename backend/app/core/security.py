from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded or is otherwise invalid."""


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str | int,
    extra: dict | None = None,
    expires_minutes: int | None = None,
) -> str:
    settings = get_settings()
    minutes = (
        expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    )

    now = datetime.now(UTC)
    expire = now + timedelta(minutes=minutes)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra:
        payload.update(extra)

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as err:
        raise InvalidTokenError(str(err)) from err
