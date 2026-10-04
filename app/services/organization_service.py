import copy
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import HTTPException, status

from app.schemas.organization import (
    OrganizationUnitCreate,
    OrganizationUnitUpdate,
)
from app.services import auth_service

INITIAL_ORGANIZATIONS = [
    {
        "id": 1,
        "code": "CORP-HQ",
        "name": "Khối Kinh Doanh Tổng Công Ty",
        "parent_id": None,
        "manager_id": 1,  # Admin / Tổng giám đốc
        "territories": ["Toàn quốc"],
        "description": "Quản lý toàn bộ hoạt động kinh doanh toàn quốc",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 2,
        "code": "SALES-NORTH",
        "name": "Phòng Kinh Doanh Miền Bắc",
        "parent_id": 1,
        "manager_id": 2,  # Manager Team A
        "territories": ["Hà Nội", "Hải Phòng", "Quảng Ninh"],
        "description": "Phụ trách thị trường miền Bắc",
        "created_at": datetime(2026, 1, 2, 8, 0, 0),
    },
    {
        "id": 3,
        "code": "SALES-SOUTH",
        "name": "Phòng Kinh Doanh Miền Nam",
        "parent_id": 1,
        "manager_id": None,
        "territories": ["TP. Hồ Chí Minh", "Bình Dương", "Đồng Nai"],
        "description": "Phụ trách thị trường miền Nam",
        "created_at": datetime(2026, 1, 3, 8, 0, 0),
    },
    {
        "id": 4,
        "code": "TEAM-ENTERPRISE-HN",
        "name": "Đội Doanh Nghiệp Lớn Hà Nội",
        "parent_id": 2,
        "manager_id": 2,
        "territories": ["Hà Nội"],
        "description": "Nhóm khách hàng doanh nghiệp lớn tại Hà Nội",
        "created_at": datetime(2026, 1, 4, 8, 0, 0),
    },
]

fake_org_db = copy.deepcopy(INITIAL_ORGANIZATIONS)


def reset_fake_orgs():
    global fake_org_db
    fake_org_db = copy.deepcopy(INITIAL_ORGANIZATIONS)


def _get_manager_name(manager_id: Optional[int]) -> Optional[str]:
    if not manager_id:
        return None
    user = auth_service.get_user_by_id(manager_id)
    return user["full_name"] if user else None


def _get_member_count(unit_id: int) -> int:
    """Đếm số nhân viên thuộc team này."""
    users = auth_service.fake_users_db
    return len([u for u in users if u.get("team_id") == unit_id])


def get_all_units(include_tree: bool = False) -> List[dict]:
    """Lấy danh sách các đơn vị tổ chức."""
    flat_list = []
    for u in fake_org_db:
        item = copy.deepcopy(u)
        item["manager_name"] = _get_manager_name(item.get("manager_id"))
        item["member_count"] = _get_member_count(item["id"])
        flat_list.append(item)

    if not include_tree:
        return flat_list

    return build_org_tree(flat_list)


def build_org_tree(units: List[dict]) -> List[dict]:
    """Xây dựng cây tổ chức phân cấp cha - con."""
    unit_map = {u["id"]: copy.deepcopy(u) for u in units}
    for u in unit_map.values():
        u["children"] = []
        u["level"] = 1

    tree = []
    for u_id, node in unit_map.items():
        p_id = node.get("parent_id")
        if p_id and p_id in unit_map:
            parent_node = unit_map[p_id]
            node["level"] = parent_node.get("level", 1) + 1
            parent_node["children"].append(node)
        else:
            tree.append(node)

    return tree


def get_unit_by_id(unit_id: int) -> dict:
    for u in fake_org_db:
        if u["id"] == unit_id:
            res = copy.deepcopy(u)
            res["manager_name"] = _get_manager_name(res.get("manager_id"))
            res["member_count"] = _get_member_count(unit_id)
            return res
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Không tìm thấy phòng ban / đội nhóm với ID {unit_id}",
    )


def is_descendant(parent_id: int, child_id: int) -> bool:
    """Kiểm tra child_id có phải là con cháu của parent_id không để tránh tạo chu trình (cycle)."""
    curr = child_id
    visited = set()
    while curr:
        if curr in visited:
            break
        visited.add(curr)
        unit = next((u for u in fake_org_db if u["id"] == curr), None)
        if not unit:
            break
        curr_parent = unit.get("parent_id")
        if curr_parent == parent_id:
            return True
        curr = curr_parent
    return False


def create_unit(unit_in: OrganizationUnitCreate) -> dict:
    clean_code = unit_in.code.strip().upper()
    if any(u["code"].upper() == clean_code for u in fake_org_db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã phòng ban '{clean_code}' đã tồn tại",
        )

    if unit_in.parent_id is not None:
        if not any(u["id"] == unit_in.parent_id for u in fake_org_db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Đơn vị cấp trên với ID {unit_in.parent_id} không tồn tại",
            )

    if unit_in.manager_id is not None:
        user = auth_service.get_user_by_id(unit_in.manager_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Trưởng nhóm / phòng với ID {unit_in.manager_id} không tồn tại",
            )

    next_id = max([u["id"] for u in fake_org_db], default=0) + 1
    new_unit = {
        "id": next_id,
        "code": clean_code,
        "name": unit_in.name.strip(),
        "parent_id": unit_in.parent_id,
        "manager_id": unit_in.manager_id,
        "territories": unit_in.territories,
        "description": unit_in.description.strip() if unit_in.description else None,
        "created_at": datetime.utcnow(),
    }
    fake_org_db.append(new_unit)
    res = copy.deepcopy(new_unit)
    res["manager_name"] = _get_manager_name(res.get("manager_id"))
    res["member_count"] = 0
    return res


def update_unit(unit_id: int, unit_in: OrganizationUnitUpdate) -> dict:
    unit = next((u for u in fake_org_db if u["id"] == unit_id), None)
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phòng ban với ID {unit_id}",
        )

    if unit_in.parent_id is not None:
        if unit_in.parent_id == unit_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Một phòng ban không thể là đơn vị cấp trên của chính nó",
            )
        if is_descendant(unit_id, unit_in.parent_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể gán đơn vị cấp trên là con cháu của chính nó (gây vòng lặp)",
            )
        if not any(u["id"] == unit_in.parent_id for u in fake_org_db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Đơn vị cấp trên với ID {unit_in.parent_id} không tồn tại",
            )
        unit["parent_id"] = unit_in.parent_id

    if unit_in.manager_id is not None:
        user = auth_service.get_user_by_id(unit_in.manager_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Trưởng nhóm với ID {unit_in.manager_id} không tồn tại",
            )
        unit["manager_id"] = unit_in.manager_id

    if unit_in.name is not None:
        unit["name"] = unit_in.name.strip()
    if unit_in.territories is not None:
        unit["territories"] = unit_in.territories
    if unit_in.description is not None:
        unit["description"] = unit_in.description.strip()

    res = copy.deepcopy(unit)
    res["manager_name"] = _get_manager_name(res.get("manager_id"))
    res["member_count"] = _get_member_count(unit_id)
    return res


def move_unit_parent(unit_id: int, target_parent_id: Optional[int]) -> dict:
    """
    AC S2-06: Luân chuyển cấp bậc hoặc thay đổi cấp trên trong cơ cấu tổ chức.
    """
    unit = next((u for u in fake_org_db if u["id"] == unit_id), None)
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phòng ban với ID {unit_id}",
        )

    if target_parent_id is not None:
        if target_parent_id == unit_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Đơn vị không thể là cấp trên của chính nó",
            )
        if is_descendant(unit_id, target_parent_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể chuyển phòng ban vào một phòng ban con của nó",
            )
        if not any(u["id"] == target_parent_id for u in fake_org_db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Đơn vị mục tiêu với ID {target_parent_id} không tồn tại",
            )

    unit["parent_id"] = target_parent_id
    res = copy.deepcopy(unit)
    res["manager_name"] = _get_manager_name(res.get("manager_id"))
    res["member_count"] = _get_member_count(unit_id)
    return res


def delete_unit(unit_id: int) -> dict:
    """Xóa đơn vị tổ chức nếu không có phòng ban con hoặc nhân viên trực thuộc."""
    unit = next((u for u in fake_org_db if u["id"] == unit_id), None)
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phòng ban với ID {unit_id}",
        )

    has_children = any(u.get("parent_id") == unit_id for u in fake_org_db)
    if has_children:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xoá phòng ban đang có các phòng ban con. Hãy chuyển hoặc xoá các phòng ban con trước.",
        )

    member_cnt = _get_member_count(unit_id)
    if member_cnt > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể xoá phòng ban đang có {member_cnt} nhân viên trực thuộc.",
        )

    fake_org_db.remove(unit)
    return {
        "success": True,
        "message": f"Đã xoá phòng ban '{unit['name']}' thành công.",
    }
