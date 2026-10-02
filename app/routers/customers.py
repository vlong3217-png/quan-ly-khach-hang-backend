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
        description="Data scope filter: MY, TEAM, or ALL. Defaults based on role.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    List customers based on the user's role and requested scope.

    - ADMIN: defaults to ALL, can request MY/TEAM/ALL
    - MANAGER: defaults to TEAM, can request MY/TEAM (ALL -> 403)
    - USER: defaults to MY, can only use MY (TEAM/ALL -> 403)
    """
    effective_scope = resolve_scope(current_user, scope)
    customers = get_customers_by_scope(current_user, effective_scope)
    return {
        "scope": effective_scope.value,
        "total": len(customers),
        "customers": customers,
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
            detail="Kh??ng t??m th???y kh??ch h??ng",
        )

    if not check_scope_access(current_user, customer["owner_id"], customer.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kh??ng c?? quy???n truy c???p d??? li???u kh??ch h??ng n??y",
        )

    return customer


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    """
    Create a new customer (ADMIN or MANAGER only).
    - USER role calling this will receive 403 Forbidden.
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
