from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_current_user
from app.schemas.contact import ContactCreate, ContactResponse, ContactTransfer, ContactUpdate
from app.schemas.user import UserResponse
from app.services import contact_service

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=List[ContactResponse])
def get_contacts(
    customer_id: Optional[int] = Query(None, description="Lọc theo khách hàng"),
    current_user: dict = Depends(get_current_user),
):
    """Lấy danh sách người liên hệ, hỗ trợ lọc theo khách hàng cụ thể."""
    return contact_service.list_contacts(customer_id=customer_id)


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact_detail(
    contact_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Xem chi tiết người liên hệ kèm lịch sử luân chuyển công tác."""
    contact = contact_service.get_contact_by_id(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy thông tin người liên hệ",
        )
    return contact


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
    contact_data: ContactCreate,
    current_user: dict = Depends(get_current_user),
):
    """Tạo người liên hệ mới cho khách hàng."""
    try:
        user_name = current_user.get("username") or current_user.get("full_name") or current_user.get("email") or "user"
        return contact_service.create_contact(
            contact_data=contact_data,
            current_user_username=user_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    update_data: ContactUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Cập nhật thông tin người liên hệ / vai trò quyết định."""
    user_name = current_user.get("username") or current_user.get("full_name") or current_user.get("email") or "user"
    updated = contact_service.update_contact(
        contact_id=contact_id,
        update_data=update_data,
        current_user_username=user_name,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người liên hệ để cập nhật",
        )
    return updated


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Xóa người liên hệ."""
    success = contact_service.delete_contact(contact_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người liên hệ để xóa",
        )
    return None


@router.post("/{contact_id}/transfer", response_model=ContactResponse)
def transfer_contact(
    contact_id: int,
    transfer_data: ContactTransfer,
    current_user: dict = Depends(get_current_user),
):
    """Chuyển contact sang công ty khác nhưng giữ nguyên lịch sử tương tác/lịch sử chuyển."""
    try:
        user_name = current_user.get("username") or current_user.get("full_name") or current_user.get("email") or "user"
        return contact_service.transfer_contact(
            contact_id=contact_id,
            transfer_data=transfer_data,
            current_user_username=user_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

