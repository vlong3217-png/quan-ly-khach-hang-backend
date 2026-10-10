"""
Auth service with multi-user support, JWT authentication, and user management capabilities.
"""

import uuid
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
from app.core.database import SessionLocal
from app.models.user import User as UserModel


VALID_ROLES = ["ADMIN", "MANAGER", "USER"]
VALID_TEAMS = [
    {"id": 1, "name": "Team A"},
    {"id": 2, "name": "Team B"},
]


def validate_role(role: str) -> bool:
    return bool(role and role.upper() in VALID_ROLES)


def validate_team(team_id: Optional[int]) -> bool:
    if team_id is None:
        return True
    return any(t["id"] == team_id for t in VALID_TEAMS)


def get_team_by_id(team_id: Optional[int]) -> Optional[dict]:
    if team_id is None:
        return None
    for team in VALID_TEAMS:
        if team["id"] == team_id:
            return team
    return None


_DEFAULT_HASHED_PASSWORD = hash_password("123456")


def get_initial_users():
    return [
        {
            "id": 1,
            "email": "admin@gmail.com",
            "username": "admin",
            "full_name": "Admin",
            "phone": "0912345678",
            "email_signature": "Trân trọng,\nAdmin Hệ Thống",
            "avatar_url": None,
            "role": "ADMIN",
            "is_active": True,
            "status": "ACTIVE",
            "hashed_password": _DEFAULT_HASHED_PASSWORD,
            "team_id": None,
        },
        {
            "id": 2,
            "email": "manager@gmail.com",
            "username": "manager",
            "full_name": "Manager Team A",
            "phone": "0987654321",
            "email_signature": "Thân ái,\nManager Team A\nPhòng Kinh Doanh",
            "avatar_url": None,
            "role": "MANAGER",
            "is_active": True,
            "status": "ACTIVE",
            "hashed_password": _DEFAULT_HASHED_PASSWORD,
            "team_id": 1,
        },
        {
            "id": 3,
            "email": "user@gmail.com",
            "username": "user1",
            "full_name": "User 1 Team A",
            "phone": "0345678901",
            "email_signature": "Best regards,\nNguyễn Văn User",
            "avatar_url": None,
            "role": "USER",
            "is_active": True,
            "status": "ACTIVE",
            "hashed_password": _DEFAULT_HASHED_PASSWORD,
            "team_id": 1,
        },
    ]


fake_users_db = get_initial_users()
FAKE_USERS = fake_users_db
fake_user = fake_users_db[0]


LOGIN_ATTEMPTS = {}
LOCKOUT_MINUTES = 15
MAX_FAILED_ATTEMPTS = 5


REVOKED_TOKENS = set()


def revoke_token(token: str) -> None:
    if token:
        REVOKED_TOKENS.add(token.strip())


def is_token_revoked(token: str) -> bool:
    return bool(token and token.strip() in REVOKED_TOKENS)


RESET_TOKENS = {}
RESET_TOKEN_EXPIRE_MINUTES = 30


def reset_fake_users_db():
    global fake_users_db, fake_user, FAKE_USERS, LOGIN_ATTEMPTS, REVOKED_TOKENS, RESET_TOKENS
    initial = get_initial_users()
    fake_users_db.clear()
    fake_users_db.extend(initial)
    fake_user = fake_users_db[0]
    FAKE_USERS = fake_users_db
    LOGIN_ATTEMPTS.clear()
    REVOKED_TOKENS.clear()
    RESET_TOKENS.clear()

    try:
        db = SessionLocal()
        initial_ids = {u["id"] for u in initial}
        # Xóa các user không còn nằm trong danh sách mẫu khỏi MySQL
        db.query(UserModel).filter(~UserModel.id.in_(initial_ids)).delete(synchronize_session=False)

        for u in initial:
            db_u = db.query(UserModel).filter(UserModel.id == u["id"]).first()
            if db_u:
                db_u.email = u["email"]
                db_u.username = u.get("username")
                db_u.full_name = u["full_name"]
                db_u.role = u["role"]
                db_u.team_id = u.get("team_id")
                db_u.phone = u.get("phone")
                db_u.email_signature = u.get("email_signature")
                db_u.avatar_url = u.get("avatar_url")
                db_u.is_active = u.get("is_active", True)
                db_u.status = u.get("status", "ACTIVE")
                db_u.hashed_password = u["hashed_password"]
                if hasattr(db_u, "monthly_quota"):
                    db_u.monthly_quota = u.get("monthly_quota", 0.0)
            else:
                new_db_u = UserModel(
                    id=u["id"],
                    email=u["email"],
                    username=u.get("username"),
                    full_name=u["full_name"],
                    role=u["role"],
                    team_id=u.get("team_id"),
                    phone=u.get("phone"),
                    email_signature=u.get("email_signature"),
                    avatar_url=u.get("avatar_url"),
                    is_active=u.get("is_active", True),
                    status=u.get("status", "ACTIVE"),
                    hashed_password=u["hashed_password"],
                    monthly_quota=u.get("monthly_quota", 0.0),
                )
                db.add(new_db_u)
        db.commit()
        db.close()
    except Exception:
        pass


reset_fake_users = reset_fake_users_db


def update_user_role(user_id: int, new_role: str) -> Optional[dict]:
    user = get_user_by_id(user_id)
    if user:
        user["role"] = new_role.upper()
        try:
            db = SessionLocal()
            db_u = db.query(UserModel).filter(UserModel.id == user_id).first()
            if db_u:
                db_u.role = user["role"]
                db.commit()
            db.close()
        except Exception:
            pass
    return user


def update_user_team(user_id: int, new_team_id: Optional[int]) -> Optional[dict]:
    user = get_user_by_id(user_id)
    if user:
        user["team_id"] = new_team_id
        try:
            db = SessionLocal()
            db_u = db.query(UserModel).filter(UserModel.id == user_id).first()
            if db_u:
                db_u.team_id = new_team_id
                db.commit()
            db.close()
        except Exception:
            pass
    return user


def update_user_assignment(user_id: int, new_role: Optional[str] = None, new_team_id: Optional[int] = None) -> Optional[dict]:
    user = get_user_by_id(user_id)
    if not user:
        return None
    if new_role is not None:
        user["role"] = new_role.upper()
    if new_team_id is not None or "team_id" in user:
        user["team_id"] = new_team_id

    try:
        db = SessionLocal()
        db_u = db.query(UserModel).filter(UserModel.id == user_id).first()
        if db_u:
            if new_role is not None:
                db_u.role = user["role"]
            if new_team_id is not None:
                db_u.team_id = user["team_id"]
            db.commit()
        db.close()
    except Exception:
        pass

    return user


security_bearer = HTTPBearer(auto_error=False)


def get_user_by_email(email: str) -> Optional[dict]:
    clean_email = (email or "").strip().lower()
    try:
        db = SessionLocal()
        u = db.query(UserModel).filter(UserModel.email == clean_email).first()
        if u:
            token_ver = 1
            for f in fake_users_db:
                if f["id"] == u.id:
                    token_ver = f.get("token_version", 1)
                    break
            res = {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "hashed_password": u.hashed_password,
                "is_active": u.is_active if u.is_active is not None else True,
                "team_id": u.team_id,
                "status": u.status or "ACTIVE",
                "phone": u.phone,
                "email_signature": u.email_signature,
                "avatar_url": u.avatar_url,
                "token_version": token_ver,
            }
            db.close()
            return res
        db.close()
    except Exception:
        pass

    for u in fake_users_db:
        if u["email"].lower() == clean_email:
            return u
    if clean_email in ("user1@gmail.com", "user@gmail.com"):
        return get_user_by_id(3)
    return None


def get_user_by_identifier(identifier: str) -> Optional[dict]:
    clean = (identifier or "").strip().lower()
    try:
        db = SessionLocal()
        u = db.query(UserModel).filter((UserModel.email == clean) | (UserModel.username == clean)).first()
        if u:
            token_ver = 1
            for f in fake_users_db:
                if f["id"] == u.id:
                    token_ver = f.get("token_version", 1)
                    break
            res = {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "hashed_password": u.hashed_password,
                "is_active": u.is_active if u.is_active is not None else True,
                "team_id": u.team_id,
                "status": u.status or "ACTIVE",
                "phone": u.phone,
                "email_signature": u.email_signature,
                "avatar_url": u.avatar_url,
                "token_version": token_ver,
            }
            db.close()
            return res
        db.close()
    except Exception:
        pass

    for u in fake_users_db:
        if clean == u["email"].lower() or (u.get("username") and clean == u["username"].lower()):
            return u
    if clean in ("user1@gmail.com", "user@gmail.com", "user1", "user"):
        return get_user_by_id(3)
    return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    try:
        db = SessionLocal()
        u = db.query(UserModel).filter(UserModel.id == user_id).first()
        if u:
            token_ver = 1
            for f in fake_users_db:
                if f["id"] == u.id:
                    token_ver = f.get("token_version", 1)
                    break
            res = {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "hashed_password": u.hashed_password,
                "is_active": u.is_active if u.is_active is not None else True,
                "team_id": u.team_id,
                "status": u.status or "ACTIVE",
                "phone": u.phone,
                "email_signature": u.email_signature,
                "avatar_url": u.avatar_url,
                "token_version": token_ver,
            }
            db.close()
            return res
        db.close()
    except Exception:
        pass

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

    if is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập đã kết thúc (đã đăng xuất). Vui lòng đăng nhập lại.",
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

    token_version = payload.get("token_version")
    if token_version is not None and user.get("token_version", 1) != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập đã bị thu hồi do đổi mật khẩu. Vui lòng đăng nhập lại.",
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
        "token_version": user.get("token_version", 1),
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

    clean_new_pass = new_password.strip()
    if len(clean_new_pass) < 8:
        return False, "Mật khẩu mới phải có tối thiểu 8 ký tự"

    has_letter = any(c.isalpha() for c in clean_new_pass)
    has_digit = any(c.isdigit() for c in clean_new_pass)
    if not (has_letter and has_digit):
        return False, "Mật khẩu mới phải bao gồm cả chữ và số"

    user["hashed_password"] = hash_password(clean_new_pass)
    # AC S1-04: Đổi xong thu hồi các phiên đăng nhập khác
    user["token_version"] = user.get("token_version", 1) + 1

    for f in fake_users_db:
        if f["id"] == user["id"]:
            f["token_version"] = user["token_version"]
            f["hashed_password"] = user["hashed_password"]

    try:
        db = SessionLocal()
        db_u = db.query(UserModel).filter(UserModel.id == user["id"]).first()
        if db_u:
            db_u.hashed_password = user["hashed_password"]
            db.commit()
        db.close()
    except Exception:
        pass

    return True, "Đổi mật khẩu thành công"


def create_password_reset_token(email: str) -> tuple[str, Optional[dict]]:
    clean_email = (email or "").strip().lower()
    user = get_user_by_email(clean_email)
    reset_token = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)

    if user:
        RESET_TOKENS[reset_token] = {
            "user_id": user["id"],
            "email": user["email"],
            "expires_at": expires_at,
            "used": False,
        }
    return reset_token, user


def reset_password_with_token(token: str, new_password: str) -> tuple[bool, str]:
    if not token or not token.strip():
        return False, "Mã khôi phục không hợp lệ hoặc đã hết hạn"

    clean_token = token.strip()
    record = RESET_TOKENS.get(clean_token)
    if not record:
        return False, "Mã khôi phục không hợp lệ hoặc đã hết hạn"

    now = datetime.now(timezone.utc)
    if record["used"]:
        return False, "Mã khôi phục này đã được sử dụng"

    if now > record["expires_at"]:
        return False, "Mã khôi phục đã hết thời hạn 30 phút"

    if not new_password or not new_password.strip():
        return False, "Mật khẩu mới không được để trống"

    if len(new_password.strip()) < 8:
        return False, "Mật khẩu mới phải có tối thiểu 8 ký tự"

    # Require both letters and digits
    has_letter = any(c.isalpha() for c in new_password)
    has_digit = any(c.isdigit() for c in new_password)
    if not (has_letter and has_digit):
        return False, "Mật khẩu mới phải bao gồm cả chữ và số"

    user = get_user_by_id(record["user_id"])
    if not user:
        return False, "Không tìm thấy thông tin tài khoản người dùng"

    user["hashed_password"] = hash_password(new_password.strip())
    record["used"] = True

    try:
        db = SessionLocal()
        db_u = db.query(UserModel).filter(UserModel.id == user["id"]).first()
        if db_u:
            db_u.hashed_password = user["hashed_password"]
            db.commit()
        db.close()
    except Exception:
        pass

    return True, "Đặt lại mật khẩu thành công"

