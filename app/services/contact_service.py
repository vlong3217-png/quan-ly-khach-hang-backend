import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.contact import ContactCreate, ContactResponse, ContactTransfer, ContactUpdate, DecisionRole
from app.services.customer_service import FAKE_CUSTOMERS

INITIAL_CONTACTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "customer_id": 1,
        "name": "Nguyễn Văn Giám Đốc",
        "phone": "0912345678",
        "email": "giamdoc@abc-tech.vn",
        "position": "Tổng Giám Đốc",
        "decision_role": DecisionRole.DECISION_MAKER.value,
        "is_primary": True,
        "notes": "Đầu mối duyệt ngân sách chính",
        "history": [
            {
                "action": "CREATE",
                "from_customer_id": None,
                "to_customer_id": 1,
                "note": "Khởi tạo thông tin liên hệ ban đầu",
                "performed_by": "admin",
                "timestamp": datetime(2026, 1, 10, 8, 30, 0, tzinfo=timezone.utc),
            }
        ],
        "created_at": datetime(2026, 1, 10, 8, 30, 0, tzinfo=timezone.utc),
        "updated_at": None,
    },
    {
        "id": 2,
        "customer_id": 1,
        "name": "Trần Thị Trưởng Phòng Kỹ Thuật",
        "phone": "0987654321",
        "email": "techlead@abc-tech.vn",
        "position": "Trưởng phòng CNTT",
        "decision_role": DecisionRole.INFLUENCER.value,
        "is_primary": False,
        "notes": "Đánh giá mặt kỹ thuật và tích hợp hệ thống",
        "history": [
            {
                "action": "CREATE",
                "from_customer_id": None,
                "to_customer_id": 1,
                "note": "Khởi tạo người liên hệ kỹ thuật",
                "performed_by": "admin",
                "timestamp": datetime(2026, 1, 12, 9, 0, 0, tzinfo=timezone.utc),
            }
        ],
        "created_at": datetime(2026, 1, 12, 9, 0, 0, tzinfo=timezone.utc),
        "updated_at": None,
    },
    {
        "id": 3,
        "customer_id": 2,
        "name": "Lê Kế Toán Trưởng",
        "phone": "0901234567",
        "email": "ketoan@xyz-solutions.com",
        "position": "Kế toán trưởng",
        "decision_role": DecisionRole.BLOCKER.value,
        "is_primary": False,
        "notes": "Quan tâm sâu về chi phí và điều khoản thanh toán",
        "history": [
            {
                "action": "CREATE",
                "from_customer_id": None,
                "to_customer_id": 2,
                "note": "Khởi tạo liên hệ",
                "performed_by": "manager",
                "timestamp": datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc),
            }
        ],
        "created_at": datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc),
        "updated_at": None,
    },
]

FAKE_CONTACTS: List[Dict[str, Any]] = copy.deepcopy(INITIAL_CONTACTS)


def reset_fake_contacts() -> None:
    global FAKE_CONTACTS
    FAKE_CONTACTS = copy.deepcopy(INITIAL_CONTACTS)


def _check_customer_exists(customer_id: int) -> bool:
    return any(c["id"] == customer_id for c in FAKE_CUSTOMERS)


def list_contacts(customer_id: Optional[int] = None) -> List[Dict[str, Any]]:
    if customer_id is not None:
        return [c for c in FAKE_CONTACTS if c["customer_id"] == customer_id]
    return FAKE_CONTACTS


def get_contact_by_id(contact_id: int) -> Optional[Dict[str, Any]]:
    for c in FAKE_CONTACTS:
        if c["id"] == contact_id:
            return c
    return None


def create_contact(contact_data: ContactCreate, current_user_username: str = "system") -> Dict[str, Any]:
    if not _check_customer_exists(contact_data.customer_id):
        raise ValueError("Khách hàng không tồn tại")

    # Nếu đánh dấu is_primary = True, bỏ is_primary của các contact khác trong cùng công ty
    if contact_data.is_primary:
        for c in FAKE_CONTACTS:
            if c["customer_id"] == contact_data.customer_id:
                c["is_primary"] = False

    new_id = max([c["id"] for c in FAKE_CONTACTS], default=0) + 1
    now = datetime.now(timezone.utc)

    history_record = {
        "action": "CREATE",
        "from_customer_id": None,
        "to_customer_id": contact_data.customer_id,
        "note": "Tạo mới người liên hệ",
        "performed_by": current_user_username,
        "timestamp": now,
    }

    item = {
        "id": new_id,
        "customer_id": contact_data.customer_id,
        "name": contact_data.name,
        "phone": contact_data.phone,
        "email": contact_data.email,
        "position": contact_data.position,
        "decision_role": contact_data.decision_role.value if contact_data.decision_role else DecisionRole.INFLUENCER.value,
        "is_primary": contact_data.is_primary,
        "notes": contact_data.notes,
        "history": [history_record],
        "created_at": now,
        "updated_at": None,
    }
    FAKE_CONTACTS.append(item)
    return item


def update_contact(contact_id: int, update_data: ContactUpdate, current_user_username: str = "system") -> Optional[Dict[str, Any]]:
    contact = get_contact_by_id(contact_id)
    if not contact:
        return None

    update_dict = update_data.model_dump(exclude_unset=True)

    if update_dict.get("is_primary") is True:
        # Bỏ is_primary của các contact khác trong cùng công ty
        for c in FAKE_CONTACTS:
            if c["customer_id"] == contact["customer_id"] and c["id"] != contact_id:
                c["is_primary"] = False

    for key, value in update_dict.items():
        if key == "decision_role" and value is not None:
            contact[key] = value.value if hasattr(value, "value") else str(value)
        else:
            contact[key] = value

    now = datetime.now(timezone.utc)
    contact["updated_at"] = now
    contact["history"].append({
        "action": "UPDATE",
        "from_customer_id": contact["customer_id"],
        "to_customer_id": contact["customer_id"],
        "note": f"Cập nhật thông tin bởi {current_user_username}",
        "performed_by": current_user_username,
        "timestamp": now,
    })
    return contact


def delete_contact(contact_id: int) -> bool:
    for i, c in enumerate(FAKE_CONTACTS):
        if c["id"] == contact_id:
            FAKE_CONTACTS.pop(i)
            return True
    return False


def transfer_contact(
    contact_id: int,
    transfer_data: ContactTransfer,
    current_user_username: str = "system"
) -> Dict[str, Any]:
    contact = get_contact_by_id(contact_id)
    if not contact:
        raise ValueError("Người liên hệ không tồn tại")

    if not _check_customer_exists(transfer_data.to_customer_id):
        raise ValueError("Công ty chuyển đến không tồn tại")

    old_customer_id = contact["customer_id"]
    if old_customer_id == transfer_data.to_customer_id:
        raise ValueError("Công ty chuyển đến phải khác công ty hiện tại")

    now = datetime.now(timezone.utc)
    # Cập nhật công ty và huỷ is_primary nếu đang là primary của công ty cũ
    contact["customer_id"] = transfer_data.to_customer_id
    contact["is_primary"] = False
    contact["updated_at"] = now

    history_item = {
        "action": "TRANSFER",
        "from_customer_id": old_customer_id,
        "to_customer_id": transfer_data.to_customer_id,
        "note": transfer_data.note or f"Chuyển từ khách hàng #{old_customer_id} sang #{transfer_data.to_customer_id}",
        "performed_by": current_user_username,
        "timestamp": now,
    }
    contact["history"].append(history_item)
    return contact
