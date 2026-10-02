from typing import Any, Dict, List
from fastapi import HTTPException, status
from app.services.auth_service import fake_users_db


def get_initial_assigned_data() -> List[Dict[str, Any]]:
    """
    Mock d??? li???u kh??ch h??ng / d??? li???u ph??? tr??ch thu???c v??? c??c user.
    Khi module Kh??ch h??ng (S2) ho??n thi???n v???i Database, service n??y s??? t??ch h???p
    tr???c ti???p v???i Customer Model th??ng qua truy v???n:
        UPDATE customers SET owner_id = :target_id WHERE owner_id = :source_id
    """
    return [
        {
            "id": 1,
            "type": "customer",
            "name": "C??ng ty TNHH ??nh D????ng",
            "contact_email": "contact@anhduong.vn",
            "owner_id": 3,  # Thu???c v??? user id 3 (Normal User)
            "assigned_at": "2026-09-01T08:00:00Z",
        },
        {
            "id": 2,
            "type": "customer",
            "name": "T???p ??o??n C??ng ngh??? Sao Mai",
            "contact_email": "info@saomai.com",
            "owner_id": 3,  # Thu???c v??? user id 3 (Normal User)
            "assigned_at": "2026-09-10T09:30:00Z",
        },
        {
            "id": 3,
            "type": "customer",
            "name": "Doanh nghi???p T?? nh??n Ho??ng Gia",
            "contact_email": "sales@hoanggia.com",
            "owner_id": 2,  # Thu???c v??? user id 2 (Manager)
            "assigned_at": "2026-09-15T10:00:00Z",
        },
    ]


assigned_data_store = get_initial_assigned_data()


def reset_handover_data_store():
    global assigned_data_store
    assigned_data_store.clear()
    assigned_data_store.extend(get_initial_assigned_data())


def get_user_assigned_data(user_id: int) -> List[Dict[str, Any]]:
    """L???y danh s??ch c??c d??? li???u ??ang do user ph??? tr??ch."""
    return [item for item in assigned_data_store if item.get("owner_id") == user_id]


def execute_handover(source_user_id: int, target_user_id: int) -> Dict[str, Any]:
    """
    Th???c hi???n chuy???n giao d??? li???u t??? source_user_id sang target_user_id.
    - Ki???m tra source_user t???n t???i
    - Ki???m tra target_user t???n t???i v?? ??ang ho???t ?????ng (kh??ng b??? kh??a)
    - Kh??ng cho ph??p chuy???n giao cho ch??nh m??nh
    - C???p nh???t owner_id cho t???t c??? d??? li???u li??n quan m?? kh??ng l??m m???t m??t th??ng tin
    """
    # 1. T??m source user
    source_user = next((u for u in fake_users_db if u["id"] == source_user_id), None)
    if not source_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kh??ng t??m th???y t??i kho???n ng?????i d??ng chuy???n giao v???i id {source_user_id}",
        )

    # 2. T??m target user
    target_user = next((u for u in fake_users_db if u["id"] == target_user_id), None)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kh??ng t??m th???y t??i kho???n ng?????i d??ng nh???n b??n giao v???i id {target_user_id}",
        )

    # 3. Kh??ng b??n giao cho ch??nh m??nh
    if source_user_id == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kh??ng th??? b??n giao d??? li???u cho ch??nh t??i kho???n n??y",
        )

    # 4. Ng?????i nh???n ph???i ??ang ACTIVE
    if not target_user.get("is_active", True) or target_user.get("status") == "LOCKED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kh??ng th??? b??n giao d??? li???u cho t??i kho???n ??ang b??? kh??a",
        )

    # 5. Chuy???n giao d??? li???u
    transferred_items = []
    for item in assigned_data_store:
        if item.get("owner_id") == source_user_id:
            item["owner_id"] = target_user_id
            transferred_items.append({
                "id": item["id"],
                "type": item.get("type", "customer"),
                "name": item.get("name"),
            })

    return {
        "success": True,
        "message": f"B??n giao th??nh c??ng {len(transferred_items)} m???c d??? li???u t??? user #{source_user_id} sang user #{target_user_id}",
        "source_user_id": source_user_id,
        "target_user_id": target_user_id,
        "transferred_items_count": len(transferred_items),
        "transferred_items": transferred_items,
    }
