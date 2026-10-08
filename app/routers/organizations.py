from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user, require_roles
from app.schemas.organization import (
    OrganizationMoveRequest,
    OrganizationUnitCreate,
    OrganizationUnitResponse,
    OrganizationUnitUpdate,
)
from app.services import organization_service

router = APIRouter(prefix="/organizations", tags=["Organization Structure"])


@router.get("", response_model=List[OrganizationUnitResponse])
def list_organizations(
    tree: bool = Query(False, description="Nếu true thì trả về dạng cây phân cấp lồng nhau (children)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Xem danh sách cơ cấu tổ chức (phẳng hoặc cây đa cấp).
    """
    return organization_service.get_all_units(include_tree=tree)


@router.get("/{unit_id}", response_model=OrganizationUnitResponse)
def get_organization_detail(
    unit_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Xem chi tiết một phòng ban / đội nhóm."""
    return organization_service.get_unit_by_id(unit_id)


@router.post("", response_model=OrganizationUnitResponse, status_code=status.HTTP_201_CREATED)
def create_organization_unit(
    unit_in: OrganizationUnitCreate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền thiết lập cơ cấu tổ chức")),
):
    """Tạo mới phòng ban / đội nhóm trong cơ cấu tổ chức."""
    return organization_service.create_unit(unit_in)


@router.put("/{unit_id}", response_model=OrganizationUnitResponse)
def update_organization_unit(
    unit_id: int,
    unit_in: OrganizationUnitUpdate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền cập nhật cơ cấu tổ chức")),
):
    """Cập nhật thông tin phòng ban, trưởng nhóm, khu vực phụ trách."""
    return organization_service.update_unit(unit_id, unit_in)


@router.post("/{unit_id}/move", response_model=OrganizationUnitResponse)
def move_organization_unit(
    unit_id: int,
    req: OrganizationMoveRequest,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền luân chuyển cơ cấu tổ chức")),
):
    """Luân chuyển nhánh phòng ban sang đơn vị cấp trên mới (kèm kiểm tra chống vòng lặp lồng nhau)."""
    return organization_service.move_unit_parent(unit_id, req.target_parent_id)


@router.delete("/{unit_id}")
def delete_organization_unit(
    unit_id: int,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền xoá phòng ban")),
):
    """Xóa phòng ban nếu không có phòng ban con hoặc nhân viên trực thuộc."""
    return organization_service.delete_unit(unit_id)
