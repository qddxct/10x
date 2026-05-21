from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PHONE_REGEX = r"^1[3-9]\d{9}$"

Role = Literal["admin", "member"]


def _ensure_letters_and_digits(v: str) -> str:
    if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
        raise ValueError("password must contain both letters and digits")
    return v


class LoginRequest(BaseModel):
    phone: str = Field(..., pattern=PHONE_REGEX)
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str
    name: str
    role: Role


class TokenResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    phone: str = Field(..., pattern=PHONE_REGEX)
    name: str = Field(..., min_length=1, max_length=32)
    role: Role = "member"
    password: str = Field(..., min_length=8, max_length=64)

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, v: str) -> str:
        return _ensure_letters_and_digits(v)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=32)
    role: Role | None = None


class PasswordChange(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=64)

    @field_validator("new_password")
    @classmethod
    def validate_password_policy(cls, v: str) -> str:
        return _ensure_letters_and_digits(v)
