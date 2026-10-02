from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
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


@router.get(
    "",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="L???y danh s??ch t??i kho???n ng?????i d??ng",
)
def list_users_endpoint(
    search: Optional[str] = Query(None, description="T??m ki???m theo email, username ho???c h??? t??n"),
    role: Optional[str] = Query(None, description="L???c theo vai tr?? (ADMIN, MANAGER, USER)"),
    is_active: Optional[bool] = Query(None, description="L???c theo tr???ng th??i ho???t ?????ng (true/false)"),
    skip: int = Query(0, ge=0, description="V??? tr?? b???t ?????u"),
    limit: int = Query(50, ge=1, le=100, description="S??? l?????ng t???i ??a tr??? v???"),
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
    summary="L???y th??ng tin m???t t??i kho???n ng?????i d??ng",
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
    summary="T???o t??i kho???n ng?????i d??ng m???i",
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
    summary="C???p nh???t to??n b??? th??ng tin t??i kho???n ng?????i d??ng",
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
    summary="C???p nh???t m???t ph???n th??ng tin t??i kho???n ng?????i d??ng",
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
    summary="Kh??a ho???c m??? kh??a t??i kho???n ng?????i d??ng (h??? tr??? b??n giao d??? li???u)",
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
    summary="B??n giao d??? li???u c???a t??i kho???n ng?????i d??ng sang t??i kho???n kh??c",
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
