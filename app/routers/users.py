"""
User API router — profile and user management endpoints (S1-05, S1-08, S1-10).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user
from app.schemas.user import (
    DataHandoverRequest,
    DataHandoverResponse,
    UserCreate,
    UserResponse,
    UserStatusResponse,
    UserStatusUpdate,
    UserUpdate,
)
from app.services.auth_service import require_admin
from app.services.data_handover_service import execute_handover
from app.services.user_service import (
    create_user,
    get_all_users,
    get_user_by_id,
    update_user,
    update_user_status,
)

router = APIRouter(
    prefix="/users",
    tags=["User Management"],
)


@router.get("/me")
def get_my_profile(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user's profile.
    Any authenticated user can access this endpoint.
    """
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "username": current_user.get("username"),
        "full_name": current_user["full_name"],
        "role": current_user["role"],
        "team_id": current_user.get("team_id"),
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
    limit: int = Query(50, ge=1, le=100, description="Số lượng tối đa trả về"),
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
