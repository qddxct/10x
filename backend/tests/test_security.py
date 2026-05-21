import pytest
from app.core.config import get_settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from jose import jwt


def test_hash_and_verify_roundtrip() -> None:
    plain = "s3cret!"
    hashed = hash_password(plain)

    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_hash_is_non_deterministic() -> None:
    plain = "same-password"
    assert hash_password(plain) != hash_password(plain)


def test_create_and_decode_token_roundtrip() -> None:
    token = create_access_token(subject="42", extra={"role": "admin"})
    payload = decode_access_token(token)

    assert payload["sub"] == "42"
    assert payload["role"] == "admin"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert payload["exp"] > payload["iat"]


def test_create_token_accepts_int_subject() -> None:
    token = create_access_token(subject=42)
    payload = decode_access_token(token)
    assert payload["sub"] == "42"


def test_decode_expired_token_raises() -> None:
    token = create_access_token(subject="1", expires_minutes=-1)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_decode_tampered_token_raises() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-real-token")


def test_decode_wrong_secret_raises() -> None:
    settings = get_settings()
    bogus_token = jwt.encode(
        {"sub": "99"},
        "a-completely-different-secret",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(bogus_token)
