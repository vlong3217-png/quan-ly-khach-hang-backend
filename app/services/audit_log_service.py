from datetime import datetime
from typing import Any, Dict, List, Optional
from app.schemas.audit_log import AuditLogEntry

# Danh mục các loại đối tượng nhạy cảm theo AC S2-04
VALID_ENTITY_TYPES = {"ROLE", "DISCOUNT", "TARGET", "DATA_OWNERSHIP"}

# Mock in-memory database cho Audit Log
fake_audit_logs_db: List[Dict[str, Any]] = [
    {
        "id": 1,
        "user_id": 1,
        "user_name": "Admin",
        "entity_type": "ROLE",
        "entity_id": "3",
        "action": "ASSIGN_ROLE",
        "field_name": "role",
        "old_value": "USER",
        "new_value": "MANAGER",
        "timestamp": datetime(2026, 9, 15, 10, 30, 0),
        "ip_address": "127.0.0.1",
    },
    {
        "id": 2,
        "user_id": 1,
        "user_name": "Admin",
        "entity_type": "DISCOUNT",
        "entity_id": "QUOTE-101",
        "action": "UPDATE_DISCOUNT",
        "field_name": "discount_rate",
        "old_value": "10%",
        "new_value": "25%",
        "timestamp": datetime(2026, 9, 20, 14, 15, 0),
        "ip_address": "127.0.0.1",
    },
    {
        "id": 3,
        "user_id": 2,
        "user_name": "Manager Team A",
        "entity_type": "TARGET",
        "entity_id": "USER-3",
        "action": "UPDATE_TARGET",
        "field_name": "monthly_quota",
        "old_value": "100000000",
        "new_value": "150000000",
        "timestamp": datetime(2026, 9, 25, 9, 0, 0),
        "ip_address": "127.0.0.1",
    },
    {
        "id": 4,
        "user_id": 1,
        "user_name": "Admin",
        "entity_type": "DATA_OWNERSHIP",
        "entity_id": "CUST-88",
        "action": "TRANSFER_OWNER",
        "field_name": "assigned_to",
        "old_value": "user1@gmail.com",
        "new_value": "user2@gmail.com",
        "timestamp": datetime(2026, 9, 28, 16, 45, 0),
        "ip_address": "127.0.0.1",
    },
]


def log_change(
    user_id: int,
    user_name: str,
    entity_type: str,
    entity_id: Optional[str],
    action: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    AC S2-04: Ghi lại mọi thay đổi trên chiết khấu, chỉ tiêu, quyền sở hữu dữ liệu và vai trò người dùng.
    Mỗi bản ghi có người thực hiện, thời điểm, giá trị trước và sau.
    """
    next_id = max([log["id"] for log in fake_audit_logs_db], default=0) + 1
    new_entry = {
        "id": next_id,
        "user_id": user_id,
        "user_name": user_name,
        "entity_type": entity_type.upper(),
        "entity_id": str(entity_id) if entity_id is not None else None,
        "action": action.upper(),
        "field_name": field_name,
        "old_value": str(old_value) if old_value is not None else None,
        "new_value": str(new_value) if new_value is not None else None,
        "timestamp": datetime.now(),
        "ip_address": ip_address or "127.0.0.1",
    }
    fake_audit_logs_db.append(new_entry)
    return new_entry


def get_audit_logs(
    user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    AC S2-04: Lọc theo người dùng, loại đối tượng, khoảng thời gian.
    """
    results = fake_audit_logs_db

    if user_id is not None:
        results = [l for l in results if l["user_id"] == user_id]

    if entity_type and entity_type.strip():
        et_upper = entity_type.strip().upper()
        results = [l for l in results if l["entity_type"] == et_upper]

    if from_date is not None:
        results = [l for l in results if l["timestamp"] >= from_date]

    if to_date is not None:
        results = [l for l in results if l["timestamp"] <= to_date]

    # Sắp xếp mới nhất trước
    sorted_results = sorted(results, key=lambda x: x["timestamp"], reverse=True)
    total = len(sorted_results)
    items = sorted_results[skip : skip + limit]

    return {
        "total": total,
        "items": items,
    }
