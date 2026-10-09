"""
Opportunity API router with role-based access control and data scope filtering.
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
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityListResponse,
    OpportunityProductCreate,
    OpportunityProductResponse,
    OpportunityProductUpdate,
    OpportunityResponse,
    OpportunityUpdate,
)
from app.services.opportunity_service import (
    add_product_to_opportunity,
    create_opportunity_record,
    delete_opportunity_product,
    delete_opportunity_record,
    get_opportunities_by_scope,
    get_raw_opportunity_by_id,
    list_opportunity_products,
    update_opportunity_product,
    update_opportunity_record,
)

router = APIRouter(
    prefix="/opportunities",
    tags=["Opportunities"],
)


@router.get("", response_model=OpportunityListResponse)
def list_opportunities(
    scope: Optional[str] = Query(
        None,
        description="Data scope filter: MY, MY_TEAM, TEAM, or ALL. Defaults based on role.",
    ),
    search: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Search query alias"),
    current_user: dict = Depends(get_current_user),
):
    effective_scope = resolve_scope(current_user, scope)
    search_query = search or q
    opportunities = get_opportunities_by_scope(current_user, effective_scope, search=search_query)
    return {
        "scope": effective_scope.value,
        "total": len(opportunities),
        "opportunities": opportunities,
    }


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(
    opportunity_id: int,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )

    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu cơ hội này",
        )

    return opp


@router.post("", response_model=OpportunityResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityCreate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    new_opp = create_opportunity_record(payload.model_dump(), current_user)
    return new_opp


@router.put("/{opportunity_id}", response_model=OpportunityResponse)
def update_opportunity(
    opportunity_id: int,
    payload: OpportunityUpdate,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )

    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền chỉnh sửa dữ liệu cơ hội này",
        )

    updated = update_opportunity_record(opportunity_id, payload.model_dump(exclude_unset=True))
    return updated


@router.delete(
    "/{opportunity_id}",
    dependencies=[Depends(require_roles(["ADMIN"]))],
)
def delete_opportunity(opportunity_id: int):
    success = delete_opportunity_record(opportunity_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng để xóa",
        )
    return {"message": f"Đã xóa cơ hội bán hàng ID {opportunity_id}"}


# ============================================================================
# SẢN PHẨM / DỊCH VỤ TRONG CƠ HỘI (S5-03)
# ============================================================================

@router.get("/{opportunity_id}/products", response_model=list[OpportunityProductResponse])
def get_opportunity_products(
    opportunity_id: int,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )
    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập cơ hội này",
        )
    return list_opportunity_products(opportunity_id)


@router.post("/{opportunity_id}/products", response_model=OpportunityProductResponse, status_code=status.HTTP_201_CREATED)
def add_product(
    opportunity_id: int,
    payload: OpportunityProductCreate,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )
    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền thêm sản phẩm vào cơ hội này",
        )
    return add_product_to_opportunity(opportunity_id, payload.model_dump(), current_user)


@router.put("/{opportunity_id}/products/{item_id}", response_model=OpportunityProductResponse)
def update_product(
    opportunity_id: int,
    item_id: int,
    payload: OpportunityProductUpdate,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )
    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền cập nhật sản phẩm trong cơ hội này",
        )
    return update_opportunity_product(opportunity_id, item_id, payload.model_dump(exclude_unset=True))


@router.delete("/{opportunity_id}/products/{item_id}")
def delete_product(
    opportunity_id: int,
    item_id: int,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )
    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền xóa sản phẩm khỏi cơ hội này",
        )
    success = delete_opportunity_product(opportunity_id, item_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy dòng sản phẩm ID {item_id}",
        )
    return {"message": f"Đã xóa sản phẩm ID {item_id} khỏi cơ hội"}

