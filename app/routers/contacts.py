from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import check_scope_access, get_current_user
from app.schemas.contact import ContactCreate, ContactResponse, ContactTransfer, ContactUpdate
from app.services import contact_service
from app.services.customer_service import get_raw_customer_by_id

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _get_customer_and_check_access(customer_id: int, current_user: dict) -> dict:
    customer = get_raw_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Khách hàng với ID {customer_id} không tồn tại",
        )
    if not check_scope_access(current_user, customer.get("owner_id", 0), customer.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu người liên hệ của khách hàng này",
        )
    return customer


@router.get("", response_model=List[ContactResponse])
def get_contacts(
    customer_id: Optional[int] = Query(None, description="Lọc theo khách hàng"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách người liên hệ, hỗ trợ lọc theo khách hàng cụ thể.
    Áp dụng kiểm tra data scope:
    - Nếu truyền customer_id: kiểm tra quyền truy cập của người dùng với khách hàng đó.
    - Nếu không truyền: lọc danh sách chỉ trả về các contacts thuộc các khách hàng được phép xem.
    """
    if customer_id is not None:
        _get_customer_and_check_access(customer_id, current_user)
        return contact_service.list_contacts(customer_id=customer_id, db=db)

    all_contacts = contact_service.list_contacts(db=db)
    allowed_contacts = []
    scope_cache = {}
    for c in all_contacts:
        cid = c.get("customer_id")
        if cid not in scope_cache:
            cust = get_raw_customer_by_id(cid)
            if cust and check_scope_access(current_user, cust.get("owner_id", 0), cust.get("team_id")):
                scope_cache[cid] = True
            else:
                scope_cache[cid] = False
        if scope_cache.get(cid):
            allowed_contacts.append(c)

    return allowed_contacts


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact_detail(
    contact_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Xem chi tiết người liên hệ kèm lịch sử luân chuyển công tác (kiểm tra data scope)."""
    contact = contact_service.get_contact_by_id(contact_id, db=db)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy thông tin người liên hệ",
        )
    _get_customer_and_check_access(contact["customer_id"], current_user)
    return contact


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
    contact_data: ContactCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tạo người liên hệ mới cho khách hàng (kiểm tra data scope)."""
    _get_customer_and_check_access(contact_data.customer_id, current_user)
    try:
        user_name = current_user.get("username") or current_user.get("full_name") or current_user.get("email") or "user"
        return contact_service.create_contact(
            contact_data=contact_data,
            current_user_username=user_name,
            db=db,
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
    db: Session = Depends(get_db),
):
    """Cập nhật thông tin người liên hệ / vai trò quyết định (kiểm tra data scope)."""
    contact = contact_service.get_contact_by_id(contact_id, db=db)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người liên hệ để cập nhật",
        )
    _get_customer_and_check_access(contact["customer_id"], current_user)
    user_name = current_user.get("username") or current_user.get("full_name") or current_user.get("email") or "user"
    updated = contact_service.update_contact(
        contact_id=contact_id,
        update_data=update_data,
        current_user_username=user_name,
        db=db,
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
    db: Session = Depends(get_db),
):
    """Xóa người liên hệ (kiểm tra data scope)."""
    contact = contact_service.get_contact_by_id(contact_id, db=db)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người liên hệ để xóa",
        )
    _get_customer_and_check_access(contact["customer_id"], current_user)
    success = contact_service.delete_contact(contact_id, db=db)
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
    db: Session = Depends(get_db),
):
    """
    Chuyển contact sang công ty khác nhưng giữ nguyên lịch sử tương tác/lịch sử chuyển.
    Yêu cầu quyền truy cập data scope ở cả khách hàng hiện tại và khách hàng chuyển tới.
    """
    contact = contact_service.get_contact_by_id(contact_id, db=db)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người liên hệ để chuyển",
        )
    # Kiểm tra quyền truy cập ở cả công ty xuất phát và công ty đích
    _get_customer_and_check_access(contact["customer_id"], current_user)
    _get_customer_and_check_access(transfer_data.to_customer_id, current_user)

    try:
        user_name = current_user.get("username") or current_user.get("full_name") or current_user.get("email") or "user"
        return contact_service.transfer_contact(
            contact_id=contact_id,
            transfer_data=transfer_data,
            current_user_username=user_name,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
