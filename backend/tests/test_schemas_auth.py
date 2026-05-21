from dataclasses import dataclass

import pytest
from app.schemas import (
    LoginRequest,
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserOut,
    UserUpdate,
)
from pydantic import ValidationError


def test_login_request_valid():
    req = LoginRequest(phone="13800138000", password="abc")
    assert req.phone == "13800138000"
    assert req.password == "abc"


@pytest.mark.parametrize(
    "phone",
    [
        "12345",
        "12800138000",
        "1380013800",
        "138001380000",
        "",
    ],
)
def test_login_request_invalid_phone(phone):
    with pytest.raises(ValidationError):
        LoginRequest(phone=phone, password="abc")


def test_login_request_empty_password_rejected():
    with pytest.raises(ValidationError):
        LoginRequest(phone="13800138000", password="")


def test_user_create_valid():
    user = UserCreate(
        phone="13800138000",
        name="Alice",
        role="member",
        password="Abcd1234",
    )
    assert user.role == "member"

    default_role_user = UserCreate(
        phone="13800138000",
        name="Alice",
        password="Abcd1234",
    )
    assert default_role_user.role == "member"


@pytest.mark.parametrize("bad_role", ["superuser", "guest", "", "Admin", "MEMBER"])
def test_user_create_invalid_role_rejected(bad_role):
    with pytest.raises(ValidationError):
        UserCreate(
            phone="13800138000",
            name="Alice",
            role=bad_role,
            password="Abcd1234",
        )


@pytest.mark.parametrize(
    "bad_password",
    [
        "abcdefgh",
        "12345678",
    ],
)
def test_user_create_password_requires_letters_and_digits(bad_password):
    with pytest.raises(ValidationError):
        UserCreate(
            phone="13800138000",
            name="Alice",
            password=bad_password,
        )


def test_user_create_password_happy_case():
    user = UserCreate(
        phone="13800138000",
        name="Alice",
        password="abcd1234",
    )
    assert user.password == "abcd1234"


def test_user_create_password_too_short():
    with pytest.raises(ValidationError):
        UserCreate(
            phone="13800138000",
            name="Alice",
            password="ab12",
        )


def test_user_update_partial_name():
    partial_name = UserUpdate(name="new")
    assert partial_name.name == "new"
    assert partial_name.role is None


def test_user_update_partial_role():
    partial_role = UserUpdate(role="admin")
    assert partial_role.role == "admin"
    assert partial_role.name is None


@pytest.mark.parametrize("bad_role", ["bad", "superuser", "Admin", ""])
def test_user_update_invalid_role_rejected(bad_role):
    with pytest.raises(ValidationError):
        UserUpdate(role=bad_role)


@pytest.mark.parametrize(
    "bad_password",
    [
        "ab12",
        "abcdefgh",
        "12345678",
    ],
)
def test_password_change_invalid(bad_password):
    with pytest.raises(ValidationError):
        PasswordChange(new_password=bad_password)


def test_password_change_valid():
    ok = PasswordChange(new_password="Abcd1234")
    assert ok.new_password == "Abcd1234"


def test_user_out_from_orm_like_object():
    @dataclass
    class FakeUser:
        id: int
        phone: str
        name: str
        role: str

    obj = FakeUser(id=1, phone="13800138000", name="Alice", role="admin")
    user_out = UserOut.model_validate(obj)
    assert user_out.id == 1
    assert user_out.phone == "13800138000"
    assert user_out.name == "Alice"
    assert user_out.role == "admin"


def test_token_response_shape():
    user = UserOut(id=1, phone="13800138000", name="Alice", role="member")
    resp = TokenResponse(token="abc.def.ghi", user=user)
    assert resp.token == "abc.def.ghi"
    assert resp.token_type == "bearer"
    assert resp.user.id == 1
