from typing import Any, Dict, List
from fastapi import HTTPException, status
from app.services.auth_service import fake_users_db


def get_initial_assigned_data() -> List[Dict[str, Any]]:
    return [
        {
            "id": 1,
            "type": "customer",
            "name": "Công ty TNHH Ánh Dương",
            "contact_email": "contact@anhduong.vn",
            "owner_id": 3,
            "assigned_at": "2026-09-01T08:00:00Z",
        },
        {
            "id": 2,
            "type": "customer",
            "name": "Tập đoàn Công nghệ Sao Mai",
            "contact_email": "info@saomai.com",
            "owner_id": 3,
            "assigned_at": "2026-09-10T09:30:00Z",
        },
        {
            "id": 3,
            "type": "customer",
            "name": "Doanh nghiệp Tư nhân Hoàng Gia",
            "contact_email": "sales@hoanggia.com",
            "owner_id": 2,
            "assigned_at": "2026-09-15T10:00:00Z",
        },
    ]


assigned_data_store = get_initial_assigned_data()


def reset_handover_data_store():
    global assigned_data_store
    assigned_data_store.clear()
    assigned_data_store.extend(get_initial_assigned_data())


def get_user_assigned_data(user_id: int) -> List[Dict[str, Any]]:
    return [item for item in assigned_data_store if item.get("owner_id") == user_id]


def execute_handover(source_user_id: int, target_user_id: int) -> Dict[str, Any]:
    # 1. Tìm source user
    source_user = next((u for u in fake_users_db if u["id"] == source_user_id), None)
    if not source_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài khoản người dùng chuyển giao với id {source_user_id}",
        )

    # 2. Tìm target user
    target_user = next((u for u in fake_users_db if u["id"] == target_user_id), None)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài khoản người dùng nhận bàn giao với id {target_user_id}",
        )

    # 3. Không bàn giao cho chính mình
    if source_user_id == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể bàn giao dữ liệu cho chính tài khoản này",
        )

    # 4. Người nhận phải đang ACTIVE
    if not target_user.get("is_active", True) or target_user.get("status") == "LOCKED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể bàn giao dữ liệu cho tài khoản đang bị khóa",
        )

    # 5. Chuyển giao dữ liệu
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
        "message": f"Bàn giao thành công {len(transferred_items)} mục dữ liệu từ user #{source_user_id} sang user #{target_user_id}",
        "source_user_id": source_user_id,
        "target_user_id": target_user_id,
        "transferred_items_count": len(transferred_items),
        "transferred_items": transferred_items,
    }
