"""
User API router — profile and user management endpoints (S1-05, S1-08, S1-10).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.database import get_db, SessionLocal
from app.models.user import User as UserModel
from app.schemas.user import (
    DataHandoverRequest,
    DataHandoverResponse,
    UserCreate,
    UserResponse,
    UserStatusResponse,
    UserStatusUpdate,
    UserUpdate,
    UserRoleUpdate,
    UserTeamUpdate,
    UserAssignmentUpdate,
    RoleInfo,
    TeamInfo,
    UserDetailResponse,
    UserImportPreviewResponse,
    UserImportSummaryResponse,
    UserProfileResponse,
    UserProfileUpdate,
    UserTargetUpdate,
)
from app.services.auth_service import (
    require_admin,
    validate_role,
    validate_team,
    get_team_by_id,
    update_user_role,
    update_user_team,
    update_user_assignment,
)
from app.services.data_handover_service import execute_handover
from app.services.user_service import (
    create_user,
    get_all_users,
    get_user_by_id,
    update_user,
    update_user_status,
    generate_user_template_excel,
    parse_and_validate_user_rows,
    execute_user_import,
)

router = APIRouter(
    prefix="/users",
    tags=["User Management"],
)


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Xem hồ sơ cá nhân của người dùng hiện tại",
)
def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S2-02: Xem hồ sơ cá nhân bao gồm họ tên, số điện thoại, chữ ký email.
    Sử dụng Database làm nguồn dữ liệu chính.
    """
    try:
        db_user = db.query(UserModel).filter(UserModel.id == current_user["id"]).first()
        if db_user:
            return {
                "id": db_user.id,
                "email": db_user.email,
                "username": db_user.username,
                "full_name": db_user.full_name,
                "role": db_user.role,
                "team_id": db_user.team_id,
                "phone": db_user.phone,
                "email_signature": db_user.email_signature,
                "avatar_url": db_user.avatar_url,
                "is_active": db_user.is_active if db_user.is_active is not None else True,
            }
    except Exception:
        pass

    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "username": current_user.get("username"),
        "full_name": current_user["full_name"],
        "role": current_user["role"],
        "team_id": current_user.get("team_id"),
        "phone": current_user.get("phone"),
        "email_signature": current_user.get("email_signature"),
        "avatar_url": current_user.get("avatar_url"),
        "is_active": current_user.get("is_active", True),
    }


@router.put(
    "/me",
    response_model=UserProfileResponse,
    summary="Cập nhật hồ sơ cá nhân của người dùng hiện tại",
)
def update_my_profile(
    profile_in: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S2-02:
    - Sửa được họ tên (full_name), số điện thoại (phone), chữ ký email (email_signature).
    - Database làm nguồn dữ liệu chính. Rollback và trả lỗi 500 khi lưu database thất bại.
    - Không tự đổi được email, nhóm (team_id) và vai trò (role).
    - Kiểm tra họ tên không được rỗng hoặc toàn khoảng trắng.
    - Kiểm tra định dạng số điện thoại Việt Nam.
    """
    import re

    # 1. Kiểm tra các trường cấm tự thay đổi (email, role, team_id)
    if profile_in.email is not None and profile_in.email.strip().lower() != current_user["email"].lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Người dùng không được phép tự thay đổi địa chỉ email của mình",
        )

    if profile_in.role is not None and profile_in.role.strip().upper() != current_user["role"].upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Người dùng không được phép tự thay đổi vai trò (role) của mình",
        )

    if profile_in.team_id is not None and profile_in.team_id != current_user.get("team_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Người dùng không được phép tự thay đổi nhóm kinh doanh (team) của mình",
        )

    # 2. Kiểm tra dữ liệu họ tên (không được rỗng / toàn khoảng trắng)
    target_full_name = None
    if profile_in.full_name is not None:
        stripped_name = profile_in.full_name.strip()
        if not stripped_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Họ và tên không được để trống hoặc chỉ chứa khoảng trắng",
            )
        target_full_name = stripped_name

    # 3. Kiểm tra định dạng số điện thoại Việt Nam nếu có nhập
    target_phone = current_user.get("phone")
    has_phone_update = False
    if profile_in.phone is not None and profile_in.phone.strip() != "":
        clean_phone = profile_in.phone.strip()
        # Định dạng chuẩn VN: 0[3|5|7|8|9]xxxxxxxx (10 chữ số) hoặc +84[3|5|7|8|9]xxxxxxxx
        vn_phone_pattern = re.compile(r"^(0|\+84)(3[2-9]|5[2689]|7[06-9]|8[1-9]|9[0-9])[0-9]{7}$")
        if not vn_phone_pattern.match(clean_phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số điện thoại không đúng định dạng Việt Nam hợp lệ (10 chữ số, đầu số 03, 05, 07, 08, 09 hoặc +84)",
            )
        target_phone = clean_phone
        has_phone_update = True
    elif profile_in.phone == "":
        target_phone = None
        has_phone_update = True

    # 4. Lưu vào Database làm nguồn dữ liệu chính với Transaction & Rollback
    user_id = current_user["id"]
    try:
        db_user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            db_user = UserModel(
                id=user_id,
                email=current_user["email"],
                username=current_user.get("username"),
                full_name=current_user["full_name"],
                role=current_user.get("role", "USER"),
                hashed_password=current_user.get("hashed_password", ""),
                is_active=current_user.get("is_active", True),
                team_id=current_user.get("team_id"),
                status=current_user.get("status", "ACTIVE"),
                phone=current_user.get("phone"),
                email_signature=current_user.get("email_signature"),
                avatar_url=current_user.get("avatar_url"),
            )
            db.add(db_user)

        if target_full_name is not None:
            db_user.full_name = target_full_name
        if has_phone_update:
            db_user.phone = target_phone
        if profile_in.email_signature is not None:
            db_user.email_signature = profile_in.email_signature

        db.commit()
        db.refresh(db_user)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi lưu thông tin hồ sơ vào cơ sở dữ liệu. Thao tác đã được hoàn tác.",
        )

    # Đồng bộ lại cache in-memory
    current_user["full_name"] = db_user.full_name
    current_user["phone"] = db_user.phone
    current_user["email_signature"] = db_user.email_signature

    return {
        "id": db_user.id,
        "email": db_user.email,
        "username": db_user.username,
        "full_name": db_user.full_name,
        "role": db_user.role,
        "team_id": db_user.team_id,
        "phone": db_user.phone,
        "email_signature": db_user.email_signature,
        "avatar_url": db_user.avatar_url,
        "is_active": db_user.is_active if db_user.is_active is not None else True,
    }


# ============================================================================
# S2-03: TẢI LÊN ẢNH ĐẠI DIỆN (AVATAR)
# ============================================================================

@router.post(
    "/me/avatar",
    response_model=UserProfileResponse,
    summary="Tải lên ảnh đại diện cá nhân (JPG/PNG tối đa 2MB, cắt vuông và tạo thumbnail)",
)
async def upload_my_avatar_endpoint(
    file: UploadFile = File(..., description="Tệp ảnh JPG/JPEG hoặc PNG (tối đa 2MB)"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S2-03:
    - Xác minh định dạng thực tế bằng Pillow (JPEG/PNG).
    - Giới hạn dung lượng đọc (tối đa 2MB) và kích thước pixel (min 16x16, max 4096x4096px).
    - Đảm bảo lỗi ghi database không để lại file mồ côi (rollback và dọn dẹp file).
    - Cắt vuông tâm và tạo bản thu nhỏ 256x256, hỗ trợ ảnh trong suốt.
    """
    import io
    import os
    import uuid
    from PIL import Image

    # 1. Kiểm tra phần mở rộng file
    allowed_extensions = {".jpg", ".jpeg", ".png"}
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ chấp nhận tệp hình ảnh định dạng JPG, JPEG hoặc PNG",
        )

    # 2. Giới hạn dung lượng đọc an toàn (tối đa 2MB)
    MAX_FILE_SIZE = 2 * 1024 * 1024
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dung lượng tệp vượt quá giới hạn tối đa cho phép là 2MB",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp ảnh rỗng, vui lòng chọn hình ảnh hợp lệ",
        )

    # 3. Mở và xác minh tính toàn vẹn và định dạng thực tế bằng Pillow
    try:
        img_verify = Image.open(io.BytesIO(content))
        real_format = img_verify.format
        img_verify.verify()
        img = Image.open(io.BytesIO(content))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp tải lên bị lỗi hoặc không phải là hình ảnh hợp lệ",
        )

    if real_format not in ("JPEG", "PNG"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Định dạng hình ảnh thực tế không hợp lệ. Hệ thống chỉ chấp nhận định dạng JPEG hoặc PNG",
        )

    # 4. Giới hạn kích thước pixel (min 16x16, max 4096x4096)
    MIN_DIMENSION = 16
    MAX_DIMENSION = 4096
    width, height = img.size
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kích thước ảnh quá nhỏ. Chiều rộng và chiều cao tối thiểu là {MIN_DIMENSION}px",
        )
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kích thước ảnh quá lớn. Chiều rộng và chiều cao tối đa là {MAX_DIMENSION}px",
        )

    # 5. Cắt vuông (center square crop) & tạo thumbnail
    min_dim = min(width, height)
    left = (width - min_dim) / 2
    top = (height - min_dim) / 2
    right = (width + min_dim) / 2
    bottom = (height + min_dim) / 2
    cropped_img = img.crop((left, top, right, bottom))

    thumbnail_size = (256, 256)
    cropped_img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)

    # 6. Lưu file vào uploads/avatars/
    avatar_dir = os.path.join(os.getcwd(), "uploads", "avatars")
    os.makedirs(avatar_dir, exist_ok=True)

    unique_filename = f"user_{current_user['id']}_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.join(avatar_dir, unique_filename)

    cropped_img.save(save_path, format="PNG")
    avatar_url = f"/uploads/avatars/{unique_filename}"

    # 7. Cập nhật Database — đảm bảo không để lại file mồ côi nếu DB thất bại
    try:
        db_user = db.query(UserModel).filter(UserModel.id == current_user["id"]).first()
        if not db_user:
            db_user = UserModel(
                id=current_user["id"],
                email=current_user["email"],
                username=current_user.get("username"),
                full_name=current_user["full_name"],
                role=current_user.get("role", "USER"),
                hashed_password=current_user.get("hashed_password", ""),
                is_active=current_user.get("is_active", True),
                team_id=current_user.get("team_id"),
                status=current_user.get("status", "ACTIVE"),
            )
            db.add(db_user)

        old_avatar = db_user.avatar_url
        db_user.avatar_url = avatar_url
        db.commit()
        db.refresh(db_user)

        # Xóa avatar cũ trên đĩa nếu khác
        if old_avatar and old_avatar != avatar_url and old_avatar.startswith("/uploads/"):
            old_file_path = os.path.join(os.getcwd(), old_avatar.lstrip("/"))
            if os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                except Exception:
                    pass

    except Exception:
        db.rollback()
        # DỌN DẸP FILE VỪA TẠO ĐỂ TRÁNH FILE MỒ CÔI
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi lưu thông tin ảnh đại diện vào cơ sở dữ liệu. Thao tác đã được hoàn tác.",
        )

    current_user["avatar_url"] = avatar_url

    return {
        "id": db_user.id,
        "email": db_user.email,
        "username": db_user.username,
        "full_name": db_user.full_name,
        "role": db_user.role,
        "team_id": db_user.team_id,
        "phone": db_user.phone,
        "email_signature": db_user.email_signature,
        "avatar_url": db_user.avatar_url,
        "is_active": db_user.is_active if db_user.is_active is not None else True,
    }


@router.delete(
    "/me/avatar",
    response_model=UserProfileResponse,
    summary="Xóa ảnh đại diện cá nhân",
)
def delete_my_avatar_endpoint(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Xóa ảnh đại diện hiện tại và xóa file trên máy chủ."""
    import os

    try:
        db_user = db.query(UserModel).filter(UserModel.id == current_user["id"]).first()
        if db_user:
            old_avatar = db_user.avatar_url
            if old_avatar and old_avatar.startswith("/uploads/"):
                old_file_path = os.path.join(os.getcwd(), old_avatar.lstrip("/"))
                if os.path.exists(old_file_path):
                    try:
                        os.remove(old_file_path)
                    except Exception:
                        pass
            db_user.avatar_url = None
            db.commit()
            db.refresh(db_user)
    except Exception:
        db.rollback()

    current_user["avatar_url"] = None

    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "username": current_user.get("username"),
        "full_name": current_user["full_name"],
        "role": current_user["role"],
        "team_id": current_user.get("team_id"),
        "phone": current_user.get("phone"),
        "email_signature": current_user.get("email_signature"),
        "avatar_url": None,
        "is_active": current_user.get("is_active", True),
    }




@router.get(
    "",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách tài khoản người dùng (ADMIN only)",
)
def list_users_endpoint(
    search: Optional[str] = Query(None, description="Tìm kiếm theo email, username hoặc họ tên"),
    role: Optional[str] = Query(None, description="Lọc theo vai trò (ADMIN, MANAGER, USER)"),
    is_active: Optional[bool] = Query(None, description="Lọc theo trạng thái hoạt động (true/false)"),
    skip: int = Query(0, ge=0, description="Vị trí bắt đầu"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng tối đa trả về (mặc định 20)"),
    admin_user: dict = Depends(require_admin),
):
    return get_all_users(
        search=search,
        role=role,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/template",
    summary="Tải tệp Excel mẫu để nhập người dùng (ADMIN only)",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
            },
            "description": "Tệp Excel mẫu tải về",
        }
    },
)
def download_user_template_endpoint(admin_user: dict = Depends(require_admin)):
    """
    AC S2-01: Tải được tệp mẫu Excel có định dạng chuẩn để nhập người dùng hàng loạt.
    """
    content = generate_user_template_excel()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=user_import_template.xlsx"
        },
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Lấy thông tin một tài khoản người dùng",
)
def get_user_endpoint(
    user_id: int,
    admin_user: dict = Depends(require_admin),
):
    return get_user_by_id(user_id)



@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo tài khoản người dùng mới",
)
def create_user_endpoint(
    user_in: UserCreate,
    admin_user: dict = Depends(require_admin),
):
    return create_user(user_in)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Cập nhật toàn bộ thông tin tài khoản người dùng",
)
def put_user_endpoint(
    user_id: int,
    user_in: UserUpdate,
    admin_user: dict = Depends(require_admin),
):
    prev_user = get_user_by_id(user_id)
    old_role = prev_user.get("role")
    res = update_user(user_id, user_in)
    if user_in.role and old_role != res["role"]:
        try:
            from app.services.audit_log_service import log_change
            log_change(
                user_id=admin_user["id"],
                user_name=admin_user.get("full_name", "Admin"),
                entity_type="ROLE",
                entity_id=str(user_id),
                action="UPDATE_ROLE",
                field_name="role",
                old_value=old_role,
                new_value=res["role"],
            )
        except Exception:
            pass
    return res


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Cập nhật một phần thông tin tài khoản người dùng",
)
def patch_user_endpoint(
    user_id: int,
    user_in: UserUpdate,
    admin_user: dict = Depends(require_admin),
):
    prev_user = get_user_by_id(user_id)
    old_role = prev_user.get("role")
    res = update_user(user_id, user_in)
    if user_in.role and old_role != res["role"]:
        try:
            from app.services.audit_log_service import log_change
            log_change(
                user_id=admin_user["id"],
                user_name=admin_user.get("full_name", "Admin"),
                entity_type="ROLE",
                entity_id=str(user_id),
                action="UPDATE_ROLE",
                field_name="role",
                old_value=old_role,
                new_value=res["role"],
            )
        except Exception:
            pass
    return res


@router.patch(
    "/{user_id}/status",
    response_model=UserStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Khóa hoặc mở khóa tài khoản người dùng (hỗ trợ bàn giao dữ liệu)",
)
def patch_user_status_endpoint(
    user_id: int,
    status_in: UserStatusUpdate,
    admin_user: dict = Depends(require_admin),
):
    res = update_user_status(
        user_id=user_id,
        status_in=status_in,
        current_admin=admin_user,
    )

    # Ghi nhật ký thay đổi quyền sở hữu/trạng thái tài khoản (AC S2-04)
    try:
        from app.services.audit_log_service import log_change
        log_change(
            user_id=admin_user["id"],
            user_name=admin_user.get("full_name", "Admin"),
            entity_type="DATA_OWNERSHIP" if status_in.handover_to_user_id else "ROLE",
            entity_id=str(user_id),
            action="LOCK_USER" if status_in.status.upper() == "LOCKED" else "UNLOCK_USER",
            field_name="status",
            old_value="ACTIVE" if status_in.status.upper() == "LOCKED" else "LOCKED",
            new_value=status_in.status.upper(),
        )
    except Exception:
        pass

    return res


@router.post(
    "/{user_id}/handover",
    response_model=DataHandoverResponse,
    status_code=status.HTTP_200_OK,
    summary="Bàn giao dữ liệu của tài khoản người dùng sang tài khoản khác",
)
def handover_user_data_endpoint(
    user_id: int,
    handover_in: DataHandoverRequest,
    admin_user: dict = Depends(require_admin),
):
    res = execute_handover(
        source_user_id=user_id,
        target_user_id=handover_in.target_user_id,
    )

    # Ghi log bàn giao dữ liệu (AC S2-04: DATA_OWNERSHIP)
    try:
        from app.services.audit_log_service import log_change
        log_change(
            user_id=admin_user["id"],
            user_name=admin_user.get("full_name", "Admin"),
            entity_type="DATA_OWNERSHIP",
            entity_id=f"USER-{user_id}",
            action="TRANSFER_OWNER",
            field_name="owner_id",
            old_value=f"user_{user_id}",
            new_value=f"user_{handover_in.target_user_id}",
        )
    except Exception:
        pass

    return res


# ============================================================================
# S1-09: ROLE & TEAM ASSIGNMENT ENDPOINTS (ADMIN ONLY)
# ============================================================================

@router.get("/{user_id}/role", response_model=RoleInfo)
def get_user_role_endpoint(
    user_id: int,
    admin_user: dict = Depends(require_admin),
):
    user = get_user_by_id(user_id)
    return RoleInfo(
        user_id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
    )


@router.put("/{user_id}/role", response_model=RoleInfo)
def assign_user_role_endpoint(
    user_id: int,
    payload: UserRoleUpdate,
    admin_user: dict = Depends(require_admin),
):
    user = get_user_by_id(user_id)

    # AC S1-09: Không thể tự thu hồi vai trò quản trị của chính mình
    if admin_user.get("id") == user_id and payload.role.upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự thu hồi vai trò quản trị của chính mình",
        )

    if not validate_role(payload.role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{payload.role}' không hợp lệ. Các role hợp lệ: ADMIN, MANAGER, USER",
        )

    # AC S1-09: Người giữ vai trò Trưởng nhóm (MANAGER) phải được gán một nhóm cụ thể
    if payload.role.upper() == "MANAGER" and not user.get("team_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Người giữ vai trò Trưởng nhóm (MANAGER) phải được gán một nhóm kinh doanh cụ thể",
        )

    old_role = user.get("role")
    updated_user = update_user_role(user_id, payload.role)

    # AC S2-04: Ghi log thay đổi vai trò người dùng
    from app.services.audit_log_service import log_change
    log_change(
        user_id=admin_user["id"],
        user_name=admin_user.get("full_name", "Admin"),
        entity_type="ROLE",
        entity_id=str(user_id),
        action="UPDATE_ROLE",
        field_name="role",
        old_value=old_role,
        new_value=updated_user["role"],
    )

    return RoleInfo(
        user_id=updated_user["id"],
        email=updated_user["email"],
        full_name=updated_user["full_name"],
        role=updated_user["role"],
    )


@router.get("/{user_id}/team", response_model=TeamInfo)
def get_user_team_endpoint(
    user_id: int,
    admin_user: dict = Depends(require_admin),
):
    user = get_user_by_id(user_id)
    team_info = get_team_by_id(user.get("team_id"))
    team_name = team_info["name"] if team_info else None
    return TeamInfo(
        user_id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        team_id=user.get("team_id"),
        team_name=team_name,
    )


@router.put("/{user_id}/team", response_model=TeamInfo)
def assign_user_team_endpoint(
    user_id: int,
    payload: UserTeamUpdate,
    admin_user: dict = Depends(require_admin),
):
    user = get_user_by_id(user_id)
    if not validate_team(payload.team_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team ID {payload.team_id} không tồn tại trong hệ thống",
        )

    # AC S1-09: Người giữ vai trò Trưởng nhóm (MANAGER) phải được gán một nhóm cụ thể
    if user.get("role", "").upper() == "MANAGER" and payload.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Người giữ vai trò Trưởng nhóm (MANAGER) bắt buộc phải thuộc một nhóm kinh doanh",
        )

    old_team = user.get("team_id")
    updated_user = update_user_team(user_id, payload.team_id)

    # Ghi log thay đổi nhóm kinh doanh (AC S2-04)
    try:
        from app.services.audit_log_service import log_change
        log_change(
            user_id=admin_user["id"],
            user_name=admin_user.get("full_name", "Admin"),
            entity_type="DATA_OWNERSHIP",
            entity_id=str(user_id),
            action="ASSIGN_TEAM",
            field_name="team_id",
            old_value=str(old_team) if old_team else "None",
            new_value=str(payload.team_id) if payload.team_id else "None",
        )
    except Exception:
        pass

    team_info = get_team_by_id(updated_user.get("team_id"))
    team_name = team_info["name"] if team_info else None
    return TeamInfo(
        user_id=updated_user["id"],
        email=updated_user["email"],
        full_name=updated_user["full_name"],
        team_id=updated_user.get("team_id"),
        team_name=team_name,
    )


@router.put("/{user_id}/assign", response_model=UserDetailResponse)
def assign_user_role_and_team_endpoint(
    user_id: int,
    payload: UserAssignmentUpdate,
    admin_user: dict = Depends(require_admin),
):
    user = get_user_by_id(user_id)

    target_role = payload.role.upper() if payload.role else user.get("role", "USER")
    target_team = payload.team_id if payload.team_id is not None else user.get("team_id")

    # AC S1-09: Không thể tự thu hồi vai trò quản trị của chính mình
    if admin_user.get("id") == user_id and payload.role and payload.role.upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự thu hồi vai trò quản trị của chính mình",
        )

    if payload.role is not None and not validate_role(payload.role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{payload.role}' không hợp lệ. Các role hợp lệ: ADMIN, MANAGER, USER",
        )

    if payload.team_id is not None and not validate_team(payload.team_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team ID {payload.team_id} không tồn tại trong hệ thống",
        )

    # AC S1-09: Người giữ vai trò Trưởng nhóm (MANAGER) phải được gán một nhóm cụ thể
    if target_role == "MANAGER" and target_team is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Người giữ vai trò Trưởng nhóm (MANAGER) bắt buộc phải thuộc một nhóm kinh doanh",
        )

    old_role = user.get("role")
    old_team = user.get("team_id")
    updated_user = update_user_assignment(user_id, new_role=target_role, new_team_id=target_team)

    # Ghi log thay đổi vai trò / nhóm vào Nhật ký hệ thống (AC S2-04)
    try:
        from app.services.audit_log_service import log_change
        if old_role != updated_user["role"]:
            log_change(
                user_id=admin_user["id"],
                user_name=admin_user.get("full_name", "Admin"),
                entity_type="ROLE",
                entity_id=str(user_id),
                action="UPDATE_ROLE",
                field_name="role",
                old_value=old_role,
                new_value=updated_user["role"],
            )
        if old_team != updated_user.get("team_id"):
            log_change(
                user_id=admin_user["id"],
                user_name=admin_user.get("full_name", "Admin"),
                entity_type="DATA_OWNERSHIP",
                entity_id=str(user_id),
                action="ASSIGN_TEAM",
                field_name="team_id",
                old_value=str(old_team) if old_team else "None",
                new_value=str(updated_user.get("team_id")),
            )
    except Exception:
        pass

    return UserDetailResponse(
        id=updated_user["id"],
        email=updated_user["email"],
        username=updated_user.get("username"),
        full_name=updated_user["full_name"],
        role=updated_user["role"],
        team_id=updated_user.get("team_id"),
        is_active=updated_user["is_active"],
    )


# ============================================================================
# S2-01: IMPORT USER HÀNG LOẠT TỪ EXCEL
# ============================================================================

@router.post(
    "/import-preview",
    response_model=UserImportPreviewResponse,
    summary="Xem trước và báo lỗi theo từng dòng tệp Excel trước khi nhập (ADMIN only)",
)
async def preview_user_import_endpoint(
    file: UploadFile = File(..., description="Tệp Excel (.xlsx) danh sách người dùng"),
    admin_user: dict = Depends(require_admin),
):
    """
    AC S2-01: Xem trước và báo lỗi theo từng dòng trước khi nhập.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Định dạng tệp không được hỗ trợ. Vui lòng tải lên tệp Excel (.xlsx hoặc .xls)",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp tải lên rỗng không có nội dung",
        )

    result = parse_and_validate_user_rows(contents)
    return result


@router.post(
    "/import",
    response_model=UserImportSummaryResponse,
    summary="Thực hiện nhập người dùng hàng loạt từ Excel (ADMIN only)",
)
async def execute_user_import_endpoint(
    file: UploadFile = File(..., description="Tệp Excel (.xlsx) danh sách người dùng"),
    admin_user: dict = Depends(require_admin),
):
    """
    AC S2-01: Dòng lỗi bị bỏ qua, dòng hợp lệ vẫn được nhập, có báo cáo tổng kết chi tiết.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Định dạng tệp không được hỗ trợ. Vui lòng tải lên tệp Excel (.xlsx hoặc .xls)",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp tải lên rỗng không có nội dung",
        )

    summary = execute_user_import(contents)
    return summary


@router.put(
    "/{user_id}/target",
    summary="Cập nhật chỉ tiêu kinh doanh cho người dùng (ADMIN only, ghi TARGET audit log)",
)
def update_user_target_endpoint(
    user_id: int,
    payload: UserTargetUpdate,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    AC S2-04: Cập nhật chỉ tiêu kinh doanh và tự động ghi log với entity_type='TARGET'.
    """
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng với ID {user_id}",
        )

    old_target = user.get("monthly_quota", 0.0)
    user["monthly_quota"] = payload.monthly_quota

    from app.services.audit_log_service import log_change
    log_change(
        user_id=admin_user["id"],
        user_name=admin_user.get("full_name", "Admin"),
        entity_type="TARGET",
        entity_id=f"USER-{user_id}",
        action="UPDATE_TARGET",
        field_name="monthly_quota",
        old_value=str(old_target),
        new_value=str(payload.monthly_quota),
        db=db,
    )
    db.commit()

    return {
        "success": True,
        "user_id": user_id,
        "monthly_quota": payload.monthly_quota,
        "message": "Cập nhật chỉ tiêu kinh doanh thành công",
    }



