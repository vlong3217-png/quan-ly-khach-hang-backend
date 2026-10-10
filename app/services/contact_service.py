import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.database import SessionLocal
from app.models.contact import Contact as ContactModel, ContactCompanyHistory as ContactCompanyHistoryModel
from app.schemas.contact import ContactCreate, ContactTransfer, ContactUpdate, DecisionRole
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


def _model_to_dict(contact_model: ContactModel) -> dict:
    history_items = []
    if hasattr(contact_model, "history") and contact_model.history:
        for h in contact_model.history:
            history_items.append({
                "action": h.action,
                "from_customer_id": h.from_customer_id,
                "to_customer_id": h.to_customer_id,
                "note": h.note,
                "performed_by": h.performed_by,
                "timestamp": h.timestamp,
            })
    return {
        "id": contact_model.id,
        "customer_id": contact_model.customer_id,
        "name": contact_model.name,
        "phone": contact_model.phone,
        "email": contact_model.email,
        "position": contact_model.position,
        "decision_role": contact_model.decision_role,
        "is_primary": bool(contact_model.is_primary),
        "notes": contact_model.notes,
        "history": history_items,
        "created_at": contact_model.created_at,
        "updated_at": contact_model.updated_at,
    }


def reset_fake_contacts() -> None:
    """Khởi tạo lại dữ liệu danh bạ liên hệ mẫu trong CSDL MySQL/SQLite."""
    global FAKE_CONTACTS
    FAKE_CONTACTS = copy.deepcopy(INITIAL_CONTACTS)
    db = SessionLocal()
    try:
        db.query(ContactCompanyHistoryModel).delete()
        db.query(ContactModel).delete()
        for c in INITIAL_CONTACTS:
            c_model = ContactModel(
                id=c["id"],
                customer_id=c["customer_id"],
                name=c["name"],
                phone=c["phone"],
                email=c["email"],
                position=c["position"],
                decision_role=c["decision_role"],
                is_primary=c["is_primary"],
                notes=c["notes"],
                created_at=c["created_at"],
                updated_at=c["updated_at"],
            )
            db.merge(c_model)
            for h in c.get("history", []):
                h_model = ContactCompanyHistoryModel(
                    contact_id=c["id"],
                    action=h["action"],
                    from_customer_id=h["from_customer_id"],
                    to_customer_id=h["to_customer_id"],
                    note=h["note"],
                    performed_by=h["performed_by"],
                    timestamp=h["timestamp"],
                )
                db.add(h_model)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def _check_customer_exists(customer_id: int, db: Optional[Session] = None) -> bool:
    from app.models.customer import Customer as CustomerModel
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        cust = db.query(CustomerModel).filter(CustomerModel.id == customer_id).first()
        if cust:
            return True
        return any(c["id"] == customer_id for c in FAKE_CUSTOMERS)
    finally:
        if own_session:
            db.close()


def list_contacts(customer_id: Optional[int] = None, db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """
    AC S3-02: Lấy danh sách liên hệ từ CSDL làm nguồn dữ liệu chính.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        q = db.query(ContactModel)
        if customer_id is not None:
            q = q.filter(ContactModel.customer_id == customer_id)
        db_items = q.order_by(ContactModel.id.asc()).all()
        return [_model_to_dict(c) for c in db_items]
    finally:
        if own_session:
            db.close()


def get_contact_by_id(contact_id: int, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """
    AC S3-02: Lấy chi tiết liên hệ và lịch sử luân chuyển từ CSDL làm nguồn chính.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        c = db.query(ContactModel).filter(ContactModel.id == contact_id).first()
        if c:
            return _model_to_dict(c)
        return None
    finally:
        if own_session:
            db.close()


def create_contact(
    contact_data: ContactCreate,
    current_user_username: str = "system",
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    AC S3-02: Tạo người liên hệ mới và lưu lịch sử vào CSDL.
    Ràng buộc một đầu mối chính cho mỗi khách hàng ở DB.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        if isinstance(contact_data, dict):
            from app.schemas.contact import ContactCreate
            contact_data = ContactCreate(**contact_data)
        if isinstance(current_user_username, dict):
            current_user_username = (
                current_user_username.get("full_name")
                or current_user_username.get("username")
                or current_user_username.get("email")
                or "system"
            )

        if not _check_customer_exists(contact_data.customer_id, db=db):
            raise ValueError("Khách hàng không tồn tại")

        now = datetime.now(timezone.utc)

        # Ràng buộc một đầu mối chính ở DB: nếu is_primary = True, đổi các liên hệ khác của khách hàng thành False
        if contact_data.is_primary:
            db.query(ContactModel).filter(
                ContactModel.customer_id == contact_data.customer_id
            ).update({"is_primary": False})

        new_contact = ContactModel(
            customer_id=contact_data.customer_id,
            name=contact_data.name.strip(),
            phone=contact_data.phone,
            email=str(contact_data.email) if contact_data.email else None,
            position=contact_data.position,
            decision_role=contact_data.decision_role.value if contact_data.decision_role else DecisionRole.INFLUENCER.value,
            is_primary=bool(contact_data.is_primary),
            notes=contact_data.notes,
            created_at=now,
            updated_at=None,
        )
        db.add(new_contact)
        db.flush()

        history_record = ContactCompanyHistoryModel(
            contact_id=new_contact.id,
            action="CREATE",
            from_customer_id=None,
            to_customer_id=contact_data.customer_id,
            note="Tạo mới người liên hệ",
            performed_by=current_user_username,
            timestamp=now,
        )
        db.add(history_record)

        try:
            db.commit()
            db.refresh(new_contact)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi ghi CSDL khi tạo người liên hệ: {str(e)}",
            )

        res_dict = _model_to_dict(new_contact)
        FAKE_CONTACTS.append(res_dict)
        return res_dict
    finally:
        if own_session:
            db.close()


def update_contact(
    contact_id: int,
    update_data: ContactUpdate,
    current_user_username: str = "system",
    db: Optional[Session] = None,
) -> Optional[Dict[str, Any]]:
    """
    AC S3-02: Cập nhật người liên hệ và lưu lịch sử vào CSDL.
    Ràng buộc một đầu mối chính cho mỗi khách hàng ở DB.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        c_model = db.query(ContactModel).filter(ContactModel.id == contact_id).first()
        if not c_model:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        now = datetime.now(timezone.utc)

        # Ràng buộc một đầu mối chính cho mỗi khách hàng ở DB
        if update_dict.get("is_primary") is True:
            db.query(ContactModel).filter(
                ContactModel.customer_id == c_model.customer_id,
                ContactModel.id != contact_id,
            ).update({"is_primary": False})

        for key, value in update_dict.items():
            if key == "decision_role" and value is not None:
                setattr(c_model, key, value.value if hasattr(value, "value") else str(value))
            elif hasattr(c_model, key):
                setattr(c_model, key, value)
        c_model.updated_at = now

        hist = ContactCompanyHistoryModel(
            contact_id=contact_id,
            action="UPDATE",
            from_customer_id=c_model.customer_id,
            to_customer_id=c_model.customer_id,
            note=f"Cập nhật thông tin bởi {current_user_username}",
            performed_by=current_user_username,
            timestamp=now,
        )
        db.add(hist)

        try:
            db.commit()
            db.refresh(c_model)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi ghi CSDL khi cập nhật người liên hệ: {str(e)}",
            )

        res_dict = _model_to_dict(c_model)
        # Đồng bộ fake_contacts
        for idx, c in enumerate(FAKE_CONTACTS):
            if c["id"] == contact_id:
                FAKE_CONTACTS[idx] = res_dict
                break
        return res_dict
    finally:
        if own_session:
            db.close()


def delete_contact(contact_id: int, db: Optional[Session] = None) -> bool:
    """
    AC S3-02: Xóa người liên hệ trong CSDL.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        c = db.query(ContactModel).filter(ContactModel.id == contact_id).first()
        if not c:
            return False

        db.delete(c)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi ghi CSDL khi xóa người liên hệ: {str(e)}",
            )

        global FAKE_CONTACTS
        FAKE_CONTACTS = [fc for fc in FAKE_CONTACTS if fc["id"] != contact_id]
        return True
    finally:
        if own_session:
            db.close()


def transfer_contact(
    contact_id: int,
    transfer_data: ContactTransfer,
    current_user_username: str = "system",
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    AC S3-02: Chuyển contact sang công ty khác nhưng giữ nguyên lịch sử chuyển công ty trong CSDL.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        c_model = db.query(ContactModel).filter(ContactModel.id == contact_id).first()
        if not c_model:
            raise ValueError("Người liên hệ không tồn tại")

        if not _check_customer_exists(transfer_data.to_customer_id, db=db):
            raise ValueError("Công ty chuyển đến không tồn tại")

        old_customer_id = c_model.customer_id
        if old_customer_id == transfer_data.to_customer_id:
            raise ValueError("Công ty chuyển đến phải khác công ty hiện tại")

        now = datetime.now(timezone.utc)

        c_model.customer_id = transfer_data.to_customer_id
        c_model.is_primary = False  # Tránh xung đột liên hệ chính ở công ty mới
        c_model.updated_at = now

        hist = ContactCompanyHistoryModel(
            contact_id=contact_id,
            action="TRANSFER",
            from_customer_id=old_customer_id,
            to_customer_id=transfer_data.to_customer_id,
            note=transfer_data.note or f"Chuyển từ khách hàng #{old_customer_id} sang #{transfer_data.to_customer_id}",
            performed_by=current_user_username,
            timestamp=now,
        )
        db.add(hist)

        try:
            db.commit()
            db.refresh(c_model)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi ghi CSDL khi luân chuyển người liên hệ: {str(e)}",
            )

        res_dict = _model_to_dict(c_model)
        for idx, c in enumerate(FAKE_CONTACTS):
            if c["id"] == contact_id:
                FAKE_CONTACTS[idx] = res_dict
                break
        return res_dict
    finally:
        if own_session:
            db.close()
