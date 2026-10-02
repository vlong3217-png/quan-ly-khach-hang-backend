from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from app.core.security import hash_password
from app.schemas.user import UserCreate, UserStatusUpdate, UserUpdate
from app.services.auth_service import fake_users_db
from app.services.data_handover_service import execute_handover

ALLOWED_ROLES = {"ADMIN", "MANAGER", "USER"}
ALLOWED_STATUSES = {"ACTIVE", "LOCKED"}


def get_all_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[dict]:
    results = fake_users_db

    if search and search.strip():
        term = search.strip().lower()
        results = [
            u for u in results
            if term in u["email"].lower()
            or term in u.get("full_name", "").lower()
            or (u.get("username") and term in u["username"].lower())
        ]

    if role and role.strip():
        role_clean = role.strip().upper()
        results = [u for u in results if u.get("role", "").upper() == role_clean]

    if is_active is not None:
        results = [u for u in results if u.get("is_active") == is_active]

    return results[skip : skip + limit]


def get_user_by_id(user_id: int) -> dict:
    for u in fake_users_db:
        if u["id"] == user_id:
            # Ensure status attribute is present
            if "status" not in u:
                u["status"] = "ACTIVE" if u.get("is_active", True) else "LOCKED"
            return u
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Kh??ng t??m th???y t??i kho???n ng?????i d??ng v???i id {user_id}",
    )


def create_user(user_in: UserCreate) -> dict:
    clean_email = user_in.email.strip().lower()

    # Check email duplicate
    for u in fake_users_db:
        if u["email"].lower() == clean_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email ???? ???????c s??? d???ng",
            )

    # Check username duplicate if provided
    clean_username = user_in.username.strip().lower() if user_in.username else None
    if clean_username:
        for u in fake_users_db:
            if u.get("username") and u["username"].lower() == clean_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="T??n ????ng nh???p ???? ???????c s??? d???ng",
                )

    # Validate role
    role = (user_in.role or "USER").strip().upper()
    if role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vai tr?? kh??ng h???p l???. C??c vai tr?? cho ph??p: {', '.join(sorted(ALLOWED_ROLES))}",
        )

    # Hash password - never store plaintext
    hashed = hash_password(user_in.password)

    new_id = max([u["id"] for u in fake_users_db], default=0) + 1
    is_active = True if user_in.is_active is None else user_in.is_active
    new_user = {
        "id": new_id,
        "email": user_in.email.strip(),
        "username": user_in.username.strip() if user_in.username else clean_email.split("@")[0],
        "full_name": user_in.full_name.strip(),
        "role": role,
        "is_active": is_active,
        "status": "ACTIVE" if is_active else "LOCKED",
        "hashed_password": hashed,
    }

    fake_users_db.append(new_user)
    return new_user


def update_user(user_id: int, user_in: UserUpdate) -> dict:
    user = get_user_by_id(user_id)

    # Email update & duplicate check
    if user_in.email is not None:
        clean_email = user_in.email.strip().lower()
        for u in fake_users_db:
            if u["id"] != user_id and u["email"].lower() == clean_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email ???? ???????c s??? d???ng b???i t??i kho???n kh??c",
                )
        user["email"] = user_in.email.strip()

    # Username update & duplicate check
    if user_in.username is not None:
        clean_username = user_in.username.strip().lower()
        for u in fake_users_db:
            if u["id"] != user_id and u.get("username") and u["username"].lower() == clean_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="T??n ????ng nh???p ???? ???????c s??? d???ng b???i t??i kho???n kh??c",
                )
        user["username"] = user_in.username.strip()

    # Full name update
    if user_in.full_name is not None:
        if not user_in.full_name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="H??? v?? t??n kh??ng ???????c ????? tr???ng",
            )
        user["full_name"] = user_in.full_name.strip()

    # Role update
    if user_in.role is not None:
        role = user_in.role.strip().upper()
        if role not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vai tr?? kh??ng h???p l???. C??c vai tr?? cho ph??p: {', '.join(sorted(ALLOWED_ROLES))}",
            )
        user["role"] = role

    # is_active update
    if user_in.is_active is not None:
        user["is_active"] = user_in.is_active
        user["status"] = "ACTIVE" if user_in.is_active else "LOCKED"

    # Password update
    if user_in.password is not None:
        if len(user_in.password.strip()) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="M???t kh???u ph???i c?? ??t nh???t 6 k?? t???",
            )
        user["hashed_password"] = hash_password(user_in.password.strip())

    return user


def update_user_status(
    user_id: int,
    status_in: UserStatusUpdate,
    current_admin: dict,
) -> Dict[str, Any]:
    """
    C???p nh???t tr???ng th??i t??i kho???n: ACTIVE ho???c LOCKED.
    - Kh??ng cho ph??p Admin t??? kh??a t??i kho???n c???a ch??nh m??nh.
    - Khi kh??a (LOCKED): ?????t is_active = False, status = LOCKED.
    - H??? tr??? b??n giao d??? li???u n???u c?? ch??? ?????nh handover_to_user_id.
    - Khi m??? kh??a (ACTIVE): ?????t is_active = True, status = ACTIVE.
    """
    user = get_user_by_id(user_id)

    status_upper = status_in.status.strip().upper()
    if status_upper not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tr???ng th??i kh??ng h???p l???. Ch??? ch???p nh???n c??c gi?? tr???: {', '.join(sorted(ALLOWED_STATUSES))}",
        )

    # Kh??ng cho ph??p admin t??? kh??a t??i kho???n c???a ch??nh m??nh
    if status_upper == "LOCKED" and current_admin.get("id") == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kh??ng th??? t??? kh??a t??i kho???n c???a ch??nh m??nh",
        )

    handover_result = None

    if status_upper == "LOCKED":
        user["status"] = "LOCKED"
        user["is_active"] = False
        message = f"???? kh??a t??i kho???n th??nh c??ng cho user #{user_id}"

        # B??n giao d??? li???u n???u c?? y??u c???u
        if status_in.handover_to_user_id is not None:
            handover_result = execute_handover(
                source_user_id=user_id,
                target_user_id=status_in.handover_to_user_id,
            )
            message += f" v?? b??n giao d??? li???u sang user #{status_in.handover_to_user_id}"
    else:
        user["status"] = "ACTIVE"
        user["is_active"] = True
        message = f"???? m??? kh??a t??i kho???n th??nh c??ng cho user #{user_id}"

    return {
        "id": user["id"],
        "email": user["email"],
        "username": user.get("username"),
        "full_name": user["full_name"],
        "role": user["role"],
        "is_active": user["is_active"],
        "status": user["status"],
        "message": message,
        "handover": handover_result,
    }
