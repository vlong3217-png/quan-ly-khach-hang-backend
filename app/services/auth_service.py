???from datetime import datetime, timedelta
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
)

# C???u h??nh ch??nh s??ch b???o m???t kh??a t??i kho???n (Account Lockout Policy)
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# Danh s??ch ng?????i d??ng h??? th???ng theo ph??n quy???n vai tr?? (Admin, Manager, User/Staff)
USERS_DB = [
    {
        "id": 1,
        "email": "admin@gmail.com",
        "username": "admin",
        "full_name": "Qu???n Tr??? Vi??n",
        "role": "ADMIN",
        "team_id": 1,
        "team_name": "Ban Qu???n Tr???",
        "is_active": True,
        "hashed_password": hash_password("123456"),
    },
    {
        "id": 2,
        "email": "manager@gmail.com",
        "username": "manager",
        "full_name": "Tr?????ng Ph??ng Kinh Doanh",
        "role": "MANAGER",
        "team_id": 1,
        "team_name": "?????i Kinh Doanh 1",
        "is_active": True,
        "hashed_password": hash_password("123456"),
    },
    {
        "id": 3,
        "email": "user@gmail.com",
        "username": "user",
        "full_name": "Nh??n Vi??n Kinh Doanh",
        "role": "USER",
        "team_id": 1,
        "team_name": "?????i Kinh Doanh 1",
        "is_active": True,
        "hashed_password": hash_password("123456"),
    },
    {
        "id": 4,
        "email": "staff1@gmail.com",
        "username": "staff1",
        "full_name": "Nh??n Vi??n Kinh Doanh 1",
        "role": "USER",
        "team_id": 1,
        "team_name": "?????i Kinh Doanh 1",
        "is_active": True,
        "hashed_password": hash_password("123456"),
    },
]

# L??u v???t s??? l???n ????ng nh???p sai theo identifier (email/username):
# login_attempts = { "identifier": { "attempts": int, "locked_until": datetime | None } }
login_attempts: dict = {}


def get_lockout_info(identifier: str) -> dict:
    clean_id = (identifier or "").strip().lower()
    if clean_id not in login_attempts:
        return {"is_locked": False, "attempts": 0, "remaining_minutes": 0, "remaining_seconds": 0}

    entry = login_attempts[clean_id]
    locked_until = entry.get("locked_until")
    if locked_until:
        now = datetime.now()
        if now < locked_until:
            remaining_seconds = int((locked_until - now).total_seconds())
            remaining_minutes = max(1, (remaining_seconds + 59) // 60)
            return {
                "is_locked": True,
                "attempts": entry.get("attempts", MAX_FAILED_ATTEMPTS),
                "remaining_minutes": remaining_minutes,
                "remaining_seconds": remaining_seconds,
            }
        else:
            # ???? h???t 15 ph??t kh??a -> t??? ?????ng m??? kh??a v?? reset b??? ?????m
            entry["attempts"] = 0
            entry["locked_until"] = None
            return {"is_locked": False, "attempts": 0, "remaining_minutes": 0, "remaining_seconds": 0}

    return {
        "is_locked": False,
        "attempts": entry.get("attempts", 0),
        "remaining_minutes": 0,
        "remaining_seconds": 0,
    }


def record_failed_attempt(identifier: str) -> dict:
    clean_id = (identifier or "").strip().lower()
    now = datetime.now()
    if clean_id not in login_attempts:
        login_attempts[clean_id] = {"attempts": 0, "locked_until": None}

    entry = login_attempts[clean_id]
    entry["attempts"] = entry.get("attempts", 0) + 1

    if entry["attempts"] >= MAX_FAILED_ATTEMPTS:
        entry["locked_until"] = now + timedelta(minutes=LOCKOUT_MINUTES)
        return {
            "locked": True,
            "attempts": entry["attempts"],
            "remaining_minutes": LOCKOUT_MINUTES,
            "message": f"T??i kho???n ???? b??? t???m kh??a {LOCKOUT_MINUTES} ph??t do nh???p sai {MAX_FAILED_ATTEMPTS} l???n li??n ti???p. Vui l??ng th??? l???i sau.",
        }

    remaining_attempts = MAX_FAILED_ATTEMPTS - entry["attempts"]
    return {
        "locked": False,
        "attempts": entry["attempts"],
        "remaining_attempts": remaining_attempts,
        "message": "T??i kho???n ho???c m???t kh???u kh??ng ch??nh x??c",
    }


def record_successful_login(identifier: str):
    clean_id = (identifier or "").strip().lower()
    if clean_id in login_attempts:
        login_attempts[clean_id]["attempts"] = 0
        login_attempts[clean_id]["locked_until"] = None


def reset_lockout(identifier: str = None):
    if identifier:
        clean_id = (identifier or "").strip().lower()
        if clean_id in login_attempts:
            login_attempts[clean_id] = {"attempts": 0, "locked_until": None}
    else:
        login_attempts.clear()


def find_user_by_identifier(identifier: str):
    clean_id = (identifier or "").strip().lower()
    for user in USERS_DB:
        if clean_id == user["email"].lower() or clean_id == user["username"].lower():
            return user
    return None


def authenticate_user(identifier: str, password: str):
    user = find_user_by_identifier(identifier)
    if not user:
        return None

    if not verify_password(password, user["hashed_password"]):
        return None

    if not user["is_active"]:
        return None

    return user


def login_user(identifier: str, password: str):
    user = authenticate_user(identifier, password)
    if not user:
        return None

    access_token = create_access_token({
        "sub": user["email"],
        "id": user["id"],
        "role": user["role"],
        "team_id": user.get("team_id", 1),
    })

    return {
        "access_token": access_token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"],
            "team_id": user.get("team_id", 1),
            "team_name": user.get("team_name", "?????i Kinh Doanh 1"),
        },
    }