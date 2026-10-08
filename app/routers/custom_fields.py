from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user, require_roles
from app.schemas.custom_field import (
    CustomFieldCreate,
    CustomFieldResponse,
    CustomFieldUpdate,
    CustomFieldValuesValidateRequest,
    CustomFieldValuesValidateResponse,
    TargetEntity,
)
from app.services import custom_field_service

router = APIRouter(prefix="/custom-fields", tags=["Custom Fields"])


@router.get("", response_model=List[CustomFieldResponse])
def get_custom_fields(
    target_entity: Optional[TargetEntity] = Query(None, description="Lọc theo CUSTOMER hoặc OPPORTUNITY"),
    current_user: dict = Depends(get_current_user),
):
    """Lấy danh sách các trường tùy chỉnh theo đối tượng."""
    entity_val = target_entity.value if target_entity else None
    return custom_field_service.get_custom_fields(target_entity=entity_val)


@router.get("/{field_id}", response_model=CustomFieldResponse)
def get_custom_field_detail(
    field_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Xem chi tiết định nghĩa của trường tùy chỉnh."""
    return custom_field_service.get_custom_field_by_id(field_id)


@router.post("", response_model=CustomFieldResponse, status_code=status.HTTP_201_CREATED)
def create_custom_field(
    field_in: CustomFieldCreate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền thêm trường tùy biến")),
):
    """Tạo mới trường tùy biến (Text, Number, Date, Select) cho Khách hàng hoặc Cơ hội."""
    return custom_field_service.create_custom_field(field_in)


@router.put("/{field_id}", response_model=CustomFieldResponse)
def update_custom_field(
    field_id: int,
    field_in: CustomFieldUpdate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền chỉnh sửa trường tùy biến")),
):
    """Cập nhật nhãn, tùy chọn options, bắt buộc nhập hoặc thứ tự trường."""
    return custom_field_service.update_custom_field(field_id, field_in)


@router.delete("/{field_id}")
def delete_custom_field(
    field_id: int,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền xoá trường tùy biến")),
):
    """Xóa cấu hình trường tùy biến."""
    return custom_field_service.delete_custom_field(field_id)


@router.post("/validate", response_model=CustomFieldValuesValidateResponse)
def validate_custom_values(
    req: CustomFieldValuesValidateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Validate dữ liệu người dùng nhập vào các trường tùy biến khi tạo hoặc sửa Customer/Opportunity."""
    return custom_field_service.validate_custom_values(
        target_entity=req.target_entity.value,
        values=req.values,
    )
