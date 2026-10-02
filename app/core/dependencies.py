"""
S1-05: Permission & Data Scope Dependencies

Provides FastAPI dependencies for:
- Extracting current user from JWT token (get_current_user)
- Checking role-based access (require_roles)
- Filtering data by scope MY/TEAM/ALL (resolve_scope)
- Record-level scope access check (check_scope_access)
"""

from enum import Enum
from typing import List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.security import SECRET_KEY, ALGORITHM
from app.services.auth_service import get_user_by_id, get_user_by_identifier

# HTTP Bearer token scheme ??? returns 401 automatically if no token
security_scheme = HTTPBearer()


class DataScope(str, Enum):
    """Data scope levels for controlling data visibility."""
    MY = "MY"
    MY_TEAM = "MY_TEAM"
    TEAM = "TEAM"
    ALL = "ALL"


# Role -> allowed scopes mapping
# ADMIN can see everything, MANAGER can see their team, USER can only see own data
ROLE_SCOPE_MAP: dict[str, list[DataScope]] = {
    "ADMIN": [DataScope.ALL, DataScope.TEAM, DataScope.MY_TEAM, DataScope.MY],
    "MANAGER": [DataScope.TEAM, DataScope.MY_TEAM, DataScope.MY],
    "USER": [DataScope.MY],
}

# Default scope per role (used when no scope is explicitly requested)
ROLE_DEFAULT_SCOPE: dict[str, DataScope] = {
    "ADMIN": DataScope.ALL,
    "MANAGER": DataScope.TEAM,
    "USER": DataScope.MY,
}


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> dict:
    """
    Extract and validate the current user from JWT token.

    Returns a user dict with id, email, role, full_name, team_id, etc.
    Raises 401 if token is invalid/expired or user not found.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        if user_id is None:
            sub = payload.get("sub")
            if sub:
                found_user = get_user_by_identifier(sub)
                if found_user:
                    user_id = found_user["id"]
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token kh??ng h???p l???",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token kh??ng h???p l??? ho???c ???? h???t h???n",
        )

    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kh??ng t??m th???y ng?????i d??ng",
        )

    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="T??i kho???n ???? b??? v?? hi???u h??a",
        )

    return user


def require_roles(allowed_roles: List[str]):
    """
    Factory function that returns a dependency checking if the current user
    has one of the allowed roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_roles(["ADMIN"]))])
        def admin_endpoint(): ...

    Or inject the user:
        @router.get("/managers")
        def managers_endpoint(user=Depends(require_roles(["ADMIN", "MANAGER"]))): ...
    """
    def _check_role(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", "")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Kh??ng c?? quy???n truy c???p. Y??u c???u role: {', '.join(allowed_roles)}",
            )
        return current_user

    return _check_role


def resolve_scope(current_user: dict, requested_scope: Optional[str] = None) -> DataScope:
    """
    Resolve the effective data scope for a user.

    If requested_scope is provided, validate that the user's role allows it.
    If not provided, use the default scope for the user's role.
    """
    role = current_user.get("role", "USER")
    allowed_scopes = ROLE_SCOPE_MAP.get(role, [DataScope.MY])
    default_scope = ROLE_DEFAULT_SCOPE.get(role, DataScope.MY)

    if requested_scope is None:
        return default_scope

    try:
        scope = DataScope(requested_scope.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scope không hợp lệ: {requested_scope}. Các giá trị hợp lệ: MY, MY_TEAM, TEAM, ALL",
        )

    if scope not in allowed_scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' không được phép sử dụng scope '{scope.value}'",
        )

    return scope


def check_scope_access(
    current_user: dict,
    owner_id: int,
    team_id: Optional[int] = None,
) -> bool:
    """
    Check if current_user has access to a specific record based on role & scope:
    - ADMIN: full access to ALL records
    - MANAGER: access to records belonging to the same TEAM, or records owned by MANAGER
    - USER: access ONLY to records owned by this USER (MY scope)
    """
    role = current_user.get("role", "USER")
    if role == "ADMIN":
        return True
    if role == "MANAGER":
        user_team = current_user.get("team_id")
        return (user_team is not None and user_team == team_id) or (owner_id == current_user.get("id"))
    if role == "USER":
        return owner_id == current_user.get("id")
    return False
