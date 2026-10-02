"""
User API router ??? profile and user management endpoints.

Demonstrates:
- get_current_user dependency for /me endpoint
- ADMIN-only access for listing all users (require_roles(["ADMIN"]))
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, require_roles
from app.services.auth_service import FAKE_USERS

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get("/me")
def get_my_profile(current_user: dict = Depends(get_current_user)):
    """
    Get the current authenticated user's profile.
    Any authenticated user can access this.
    """
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "username": current_user.get("username"),
        "full_name": current_user["full_name"],
        "role": current_user["role"],
        "team_id": current_user.get("team_id"),
    }


@router.get("")
def list_users(current_user: dict = Depends(require_roles(["ADMIN"]))):
    """
    List all users (ADMIN only).
    MANAGER or USER will receive 403 Forbidden.
    """
    return {
        "total": len(FAKE_USERS),
        "users": [
            {
                "id": u["id"],
                "email": u["email"],
                "username": u.get("username"),
                "full_name": u["full_name"],
                "role": u["role"],
                "team_id": u.get("team_id"),
                "is_active": u["is_active"],
            }
            for u in FAKE_USERS
        ],
    }
