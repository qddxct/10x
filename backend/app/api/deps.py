from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import InvalidTokenError, decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers=_UNAUTH_HEADERS,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError as err:
        raise _unauthorized() from err

    sub = payload.get("sub")
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as err:
        raise _unauthorized() from err

    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise _unauthorized()

    return user


def require_roles(*roles: str):
    allowed = set(roles)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if allowed and user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return user

    return _dep
