"""
Auth service with multi-user support, JWT authentication, and user management capabilities.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


def get_initial_users():
    return [
        {
            "id": 1,
            "email": "admin@gmail.com",
            "username": "admin",
            "full_name": "Admin",
            "role": "ADMIN",
            "is_active": True,
            "status": "ACTIVE",
            "hashed_password": hash_password("123456"),
            "team_id": None,
        },
        {
            "id": 2,
            "email": "manager@gmail.com",
            "username": "manager",
            "full_name": "Manager Team A",
            "role": "MANAGER",
            "is_active": True,
            "status": "ACTIVE",
            "hashed_password": hash_password("123456"),
            "team_id": 1,
        },
        {
            "id": 3,
            "email": "user@gmail.com",
            "username": "user1",
            "full_name": "User 1 Team A",
            "role": "USER",
            "is_active": True,
            "status": "ACTIVE",
            "hashed_password": hash_password("123456"),
            "team_id": 1,
        },
        {
            "id": 4,
            "email": "user2@gmail.com",
            "username": "user2",
            "full_name": "User 2 Team B",
            "role": "USER",
            "is_active": True,
            "status": "ACTIVE",
            "hashed_password": hash_password("123456"),
            "team_id": 2,
        },
        {
            "id": 5,
            "email": "disabled@gmail.com",
            "username": "disabled",
            "full_name": "Disabled User",
            "role": "USER",
            "is_active": False,
            "status": "LOCKED",
            "hashed_password": hash_password("123456"),
            "team_id": 1,
        },
    ]


fake_users_db = get_initial_users()
FAKE_USERS = fake_users_db
fake_user = fake_users_db[0]


LOGIN_ATTEMPTS = {}
LOCKOUT_MINUTES = 15
MAX_FAILED_ATTEMPTS = 5


def reset_fake_users_db():
    global fake_users_db, fake_user, FAKE_USERS, LOGIN_ATTEMPTS
    fake_users_db.clear()
    fake_users_db.extend(get_initial_users())
    fake_user = fake_users_db[0]
    FAKE_USERS = fake_users_db
    LOGIN_ATTEMPTS.clear()


security_bearer = HTTPBearer(auto_error=False)


def get_user_by_email(email: str) -> Optional[dict]:
    clean_email = (email or "").strip().lower()
    for u in fake_users_db:
        if u["email"].lower() == clean_email:
            return u
    if clean_email in ("user1@gmail.com", "user@gmail.com"):
        return get_user_by_id(3)
    return None


def get_user_by_identifier(identifier: str) -> Optional[dict]:
    clean = (identifier or "").strip().lower()
    for u in fake_users_db:
        if clean == u["email"].lower() or (u.get("username") and clean == u["username"].lower()):
            return u
    if clean in ("user1@gmail.com", "user@gmail.com", "user1", "user"):
        return get_user_by_id(3)
    return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    for u in fake_users_db:
        if u["id"] == user_id:
            return u
    return None


def record_failed_login(identifier: str):
    clean = (identifier or "").strip().lower()
    now = datetime.now(timezone.utc)
    record = LOGIN_ATTEMPTS.get(clean, {"count": 0, "locked_until": None})

    # If previous lock expired, reset
    if record["locked_until"] and now > record["locked_until"]:
        record = {"count": 0, "locked_until": None}

    record["count"] += 1
    if record["count"] >= MAX_FAILED_ATTEMPTS:
        record["locked_until"] = now + timedelta(minutes=LOCKOUT_MINUTES)

    LOGIN_ATTEMPTS[clean] = record
    return record


def clear_failed_login(identifier: str):
    clean = (identifier or "").strip().lower()
    LOGIN_ATTEMPTS.pop(clean, None)


def is_temporarily_locked(identifier: str) -> bool:
    clean = (identifier or "").strip().lower()
    record = LOGIN_ATTEMPTS.get(clean)
    if not record or not record.get("locked_until"):
        return False
    now = datetime.now(timezone.utc)
    if now < record["locked_until"]:
        return True
    # Expired lock
    LOGIN_ATTEMPTS.pop(clean, None)
    return False


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> dict:
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif auth_header:
            token = auth_header.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa đăng nhập hoặc thiếu token xác thực",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    user_id = payload.get("id")

    user = None
    if user_id:
        user = get_user_by_id(user_id)
    if not user and email:
        user = get_user_by_email(email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không tìm thấy người dùng",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản đã bị vô hiệu hóa",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.get("status") == "LOCKED":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản đã bị khóa",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user.get("role", "").upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thực hiện thao tác này. Chỉ Admin mới có quyền truy cập.",
        )
    return current_user


def authenticate_user(
    identifier: str,
    password: str
):
    clean = (identifier or "").strip().lower()
    if is_temporarily_locked(clean):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản tạm thời bị khóa 15 phút do nhập sai quá 5 lần liên tiếp. Vui lòng thử lại sau.",
        )

    target_user = get_user_by_identifier(clean)
    if not target_user:
        record_failed_login(clean)
        return None

    if not verify_password(password, target_user["hashed_password"]):
        rec = record_failed_login(clean)
        if rec.get("locked_until"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tài khoản tạm thời bị khóa 15 phút do nhập sai quá 5 lần liên tiếp. Vui lòng thử lại sau.",
            )
        return None

    if not target_user.get("is_active", True) or target_user.get("status") == "LOCKED":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên.",
        )

    # Success: clear failed attempts
    clear_failed_login(clean)
    return target_user


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


def change_password(
    user: dict,
    current_password: str,
    new_password: str,
) -> tuple[bool, str]:
    if not current_password:
        return False, "Mật khẩu hiện tại không được để trống"

    if not verify_password(current_password, user["hashed_password"]):
        return False, "Mật khẩu hiện tại không chính xác"

    if not new_password or not new_password.strip():
        return False, "Mật khẩu mới không được để trống"

    if len(new_password.strip()) < 6:
        return False, "Mật khẩu mới phải có ít nhất 6 ký tự"

    user["hashed_password"] = hash_password(new_password.strip())
    return True, "Đổi mật khẩu thành công"
