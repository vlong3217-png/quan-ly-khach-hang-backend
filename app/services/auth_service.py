"""
Auth service with multi-user support for permission testing.

Maintains backward compatibility with existing login API while adding:
- Multiple fake users with different roles (ADMIN, MANAGER, USER)
- Team assignments for TEAM scope testing
- get_user_by_id() for JWT token validation
"""

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
)


# Pre-hash passwords once at module load
_admin_password = hash_password("123456")
_manager_password = hash_password("123456")
_user1_password = hash_password("123456")
_user2_password = hash_password("123456")

# Fake user store ??? supports multiple roles and teams
FAKE_USERS = [
    {
        "id": 1,
        "email": "admin@gmail.com",
        "username": "admin",
        "full_name": "Admin",
        "role": "ADMIN",
        "is_active": True,
        "hashed_password": _admin_password,
        "team_id": None,  # ADMIN has no specific team ??? can see ALL
    },
    {
        "id": 2,
        "email": "manager@gmail.com",
        "username": "manager",
        "full_name": "Manager Team A",
        "role": "MANAGER",
        "is_active": True,
        "hashed_password": _manager_password,
        "team_id": 1,  # Team A
    },
    {
        "id": 3,
        "email": "user1@gmail.com",
        "username": "user1",
        "full_name": "User 1 Team A",
        "role": "USER",
        "is_active": True,
        "hashed_password": _user1_password,
        "team_id": 1,  # Team A
    },
    {
        "id": 4,
        "email": "user2@gmail.com",
        "username": "user2",
        "full_name": "User 2 Team B",
        "role": "USER",
        "is_active": True,
        "hashed_password": _user2_password,
        "team_id": 2,  # Team B
    },
    {
        "id": 5,
        "email": "disabled@gmail.com",
        "username": "disabled",
        "full_name": "Disabled User",
        "role": "USER",
        "is_active": False,
        "hashed_password": _user1_password,
        "team_id": 1,
    },
]


def get_user_by_id(user_id: int) -> dict | None:
    """Look up a user by ID. Returns user dict or None."""
    for user in FAKE_USERS:
        if user["id"] == user_id:
            return user
    return None


def get_user_by_identifier(identifier: str) -> dict | None:
    """Look up a user by email or username (case-insensitive)."""
    clean = (identifier or "").strip().lower()
    for user in FAKE_USERS:
        if clean == user["email"].lower() or clean == user["username"].lower():
            return user
    return None


def authenticate_user(
    identifier: str,
    password: str
):
    user = get_user_by_identifier(identifier)
    if user is None:
        return None

    if not verify_password(password, user["hashed_password"]):
        return None

    if not user["is_active"]:
        return None

    return user


def login_user(
    identifier: str,
    password: str
):
    user = authenticate_user(identifier, password)
    if not user:
        return None

    access_token = create_access_token({
        "sub": user["email"],
        "id": user["id"],
        "role": user["role"],
    })

    return {
        "access_token": access_token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"],
        }
    }
