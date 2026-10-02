from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.models.user import User

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
        },
        {
            "id": 2,
            "email": "manager@gmail.com",
            "username": "manager",
            "full_name": "Manager User",
            "role": "MANAGER",
            "is_active": True,
            "status": "ACTIVE",
            "hashed_password": hash_password("123456"),
        },
        {
            "id": 3,
            "email": "user@gmail.com",
            "username": "user",
            "full_name": "Normal User",
            "role": "USER",
            "is_active": True,
            "status": "ACTIVE",
            "hashed_password": hash_password("123456"),
        },
    ]


fake_users_db = get_initial_users()
fake_user = fake_users_db[0]


def reset_fake_users_db():
    global fake_users_db, fake_user
    fake_users_db.clear()
    fake_users_db.extend(get_initial_users())
    fake_user = fake_users_db[0]


security_bearer = HTTPBearer(auto_error=False)


def get_user_by_email(email: str):
    clean_email = (email or "").strip().lower()
    for u in fake_users_db:
        if u["email"].lower() == clean_email:
            return u
    return None


def get_user_by_id(user_id: int):
    for u in fake_users_db:
        if u["id"] == user_id:
            return u
    return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> dict:
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        # Fallback to Authorization header if Bearer prefix was missing or format variation
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif auth_header:
            token = auth_header.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ch??a ????ng nh???p ho???c thi???u token x??c th???c",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token kh??ng h???p l??? ho???c ???? h???t h???n",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    user_id = payload.get("id")

    user = get_user_by_email(email) if email else None
    if not user and user_id:
        user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ng?????i d??ng kh??ng t???n t???i",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True) or user.get("status") == "LOCKED":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="T??i kho???n ???? b??? kh??a",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user.get("role", "").upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="B???n kh??ng c?? quy???n th???c hi???n thao t??c n??y. Ch??? Admin m???i c?? quy???n truy c???p.",
        )
    return current_user


def authenticate_user(
    identifier: str,
    password: str
):
    clean_identifier = (identifier or "").strip().lower()

    target_user = None
    for u in fake_users_db:
        if (
            u["email"].lower() == clean_identifier
            or (u.get("username") and u["username"].lower() == clean_identifier)
        ):
            target_user = u
            break

    if not target_user:
        return None

    if not verify_password(
        password,
        target_user["hashed_password"]
    ):
        return None

    if not target_user.get("is_active", True) or target_user.get("status") == "LOCKED":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="T??i kho???n ???? b??? kh??a. Vui l??ng li??n h??? qu???n tr??? vi??n.",
        )

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
        return False, "M???t kh???u hi???n t???i kh??ng ???????c ????? tr???ng"

    if not verify_password(current_password, user["hashed_password"]):
        return False, "M???t kh???u hi???n t???i kh??ng ch??nh x??c"

    if not new_password or not new_password.strip():
        return False, "M???t kh???u m???i kh??ng ???????c ????? tr???ng"

    if len(new_password.strip()) < 6:
        return False, "M???t kh???u m???i ph???i c?? ??t nh???t 6 k?? t???"

    # Hash new password before saving
    user["hashed_password"] = hash_password(new_password.strip())
    return True, "?????i m???t kh???u th??nh c??ng"
