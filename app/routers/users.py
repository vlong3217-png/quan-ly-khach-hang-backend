"""
User API router — profile and user management endpoints (S1-05, S1-08, S1-10).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.core.dependencies import get_current_user
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
def get_my_profile(current_user: dict = Depends(get_current_user)):
    """
    AC S2-02: Xem hồ sơ cá nhân bao gồm họ tên, số điện thoại, chữ ký email.
    """
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
):
    """
    AC S2-02:
    - Sửa được họ tên (full_name), số điện thoại (phone), chữ ký email (email_signature).
    - Không tự đổi được email, nhóm (team_id) và vai trò (role).
    - Kiểm tra định dạng số điện thoại Việt Nam (10 chữ số, hợp lệ mạng di động VN hoặc +84).
    """
    import re

    # 1. Kiểm tra nếu người dùng cố tình thay đổi email, role, team_id
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

    # 2. Kiểm tra định dạng số điện thoại Việt Nam nếu có nhập
    if profile_in.phone is not None and profile_in.phone.strip() != "":
        clean_phone = profile_in.phone.strip()
        # Định dạng chuẩn VN: 0[3|5|7|8|9]xxxxxxxx (10 chữ số) hoặc +84[3|5|7|8|9]xxxxxxxx
        vn_phone_pattern = re.compile(r"^(0|\+84)(3[2-9]|5[2689]|7[06-9]|8[1-9]|9[0-9])[0-9]{7}$")
        if not vn_phone_pattern.match(clean_phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số điện thoại không đúng định dạng Việt Nam hợp lệ (10 chữ số, đầu số 03, 05, 07, 08, 09 hoặc +84)",
            )
        current_user["phone"] = clean_phone
    elif profile_in.phone == "":
        current_user["phone"] = None

    # 3. Cập nhật họ tên
    if profile_in.full_name is not None and profile_in.full_name.strip():
        current_user["full_name"] = profile_in.full_name.strip()

    # 4. Cập nhật chữ ký email
    if profile_in.email_signature is not None:
        current_user["email_signature"] = profile_in.email_signature

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
    return update_user(user_id, user_in)


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
    return update_user(user_id, user_in)


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
    return update_user_status(
        user_id=user_id,
        status_in=status_in,
        current_admin=admin_user,
    )


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
    return execute_handover(
        source_user_id=user_id,
        target_user_id=handover_in.target_user_id,
    )


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

    updated_user = update_user_role(user_id, payload.role)
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

    updated_user = update_user_team(user_id, payload.team_id)
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

    updated_user = update_user_assignment(user_id, new_role=target_role, new_team_id=target_team)
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


