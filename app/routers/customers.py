"""
Customer API router with role-based access control and data scope filtering.

All endpoints require authentication (JWT token via HTTPBearer).
Role restrictions:
- ADMIN only: DELETE /customers/{customer_id}
- ADMIN & MANAGER: POST /customers
- ALL roles (ADMIN, MANAGER, USER): GET /customers, GET /customers/{customer_id}, PUT /customers/{customer_id}
  (data and actions are constrained by MY / TEAM / ALL scope).
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    DataScope,
    check_scope_access,
    get_current_user,
    require_roles,
    resolve_scope,
)
from app.schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
)
from app.services.customer_service import (
    create_customer_record,
    delete_customer_record,
    get_customers_by_scope,
    get_raw_customer_by_id,
    update_customer_record,
)

router = APIRouter(
    prefix="/customers",
    tags=["Customers"],
)


@router.get("", response_model=CustomerListResponse)
def list_customers(
    scope: Optional[str] = Query(
        None,
        description="Data scope filter: MY, MY_TEAM, TEAM, or ALL. Defaults based on role.",
    ),
    search: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Search query alias"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: PROSPECT, IN_TRANSACTION, CUSTOMER, DISCONTINUED"),
    page: Optional[int] = Query(None, ge=1, description="Số trang (bắt đầu từ 1)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng khách hàng mỗi trang (mặc định 20)"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu (offset)"),
    current_user: dict = Depends(get_current_user),
):
    """
    List customers based on the user's role and requested scope, with optional search, status filter, and pagination.

    - ADMIN: defaults to ALL, can request MY/MY_TEAM/TEAM/ALL
    - MANAGER: defaults to TEAM, can request MY/MY_TEAM/TEAM (ALL -> 403)
    - USER: defaults to MY, can only use MY (MY_TEAM/TEAM/ALL -> 403)
    """
    import math

    effective_scope = resolve_scope(current_user, scope)
    search_query = search or q

    # Xác định phân trang: hỗ trợ cả page + limit lẫn skip + limit
    effective_limit = limit if limit is not None else 20

    if page is not None:
        effective_skip = (page - 1) * effective_limit
        effective_page = page
    elif skip is not None:
        effective_skip = skip
        effective_page = (effective_skip // effective_limit) + 1
    else:
        # Nếu client không truyền skip hoặc page, mặc định trả từ đầu (skip = 0)
        effective_skip = 0
        effective_page = 1

    total, customers = get_customers_by_scope(
        current_user,
        effective_scope,
        search=search_query,
        skip=effective_skip,
        limit=effective_limit,
        status_filter=status,
    )

    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    return {
        "scope": effective_scope.value,
        "total": total,
        "customers": customers,
        "skip": effective_skip,
        "limit": effective_limit,
        "page": effective_page,
        "total_pages": total_pages,
    }



@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Get a single customer by ID, enforced by the user's data scope:
    - Returns 404 if the customer does not exist in the database.
    - Returns 403 if the customer exists but is outside the user's accessible scope.
    """
    customer = get_raw_customer_by_id(customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách hàng",
        )

    if not check_scope_access(current_user, customer["owner_id"], customer.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu khách hàng này",
        )

    return customer


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S3-01: Tạo mới hồ sơ khách hàng doanh nghiệp.
    Tất cả nhân viên kinh doanh đều có thể tạo khách hàng thuộc quyền sở hữu của mình.
    """
    new_customer = create_customer_record(payload.model_dump(), current_user)
    return new_customer


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update a customer record with scope verification:
    - 404 if customer does not exist.
    - 403 if user doesn't have permission to modify this customer (outside scope).
    - ADMIN can update any customer.
    - MANAGER can update customers within their team.
    - USER can only update customers they own.
    """
    customer = get_raw_customer_by_id(customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kh??ng t??m th???y kh??ch h??ng",
        )

    if not check_scope_access(current_user, customer["owner_id"], customer.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kh??ng c?? quy???n ch???nh s???a d??? li???u kh??ch h??ng n??y",
        )

    updated = update_customer_record(customer_id, payload.model_dump(exclude_unset=True))
    return updated


@router.delete(
    "/{customer_id}",
    dependencies=[Depends(require_roles(["ADMIN"]))],
)
def delete_customer(customer_id: int):
    """
    Delete a customer (ADMIN only).
    - Returns 403 Forbidden for MANAGER or USER.
    - Returns 404 Not Found if customer does not exist.
    """
    success = delete_customer_record(customer_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kh??ng t??m th???y kh??ch h??ng ????? x??a",
        )
    return {"message": f"???? x??a kh??ch h??ng ID {customer_id}"}
