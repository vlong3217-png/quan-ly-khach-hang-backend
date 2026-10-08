from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import desc
from app.schemas.audit_log import AuditLogEntry
from app.core.database import SessionLocal
from app.models.audit_log import AuditLog as AuditLogModel

# Danh mục các loại đối tượng nhạy cảm theo AC S2-04 và quản lý tài khoản người dùng
VALID_ENTITY_TYPES = {"ROLE", "DISCOUNT", "TARGET", "DATA_OWNERSHIP", "USER"}

# Bộ nhớ tạm (ban đầu rỗng - không có dữ liệu mẫu)
fake_audit_logs_db: List[Dict[str, Any]] = []


def _row_to_dict(row: AuditLogModel) -> Dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "user_name": row.user_name,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "action": row.action,
        "field_name": row.field_name,
        "old_value": row.old_value,
        "new_value": row.new_value,
        "timestamp": row.timestamp,
        "ip_address": row.ip_address or "127.0.0.1",
    }


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
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    AC S2-04: Ghi lại mọi thay đổi trên chiết khấu, chỉ tiêu, quyền sở hữu dữ liệu và vai trò người dùng.
    Mỗi bản ghi có người thực hiện, thời điểm, giá trị trước và sau.
    Đồng bộ lưu bền vững vào CSDL MySQL/SQLite cùng transaction với thay đổi nghiệp vụ.
    Bảo đảm lỗi ghi nhật ký KHÔNG bị bỏ qua và KHÔNG fallback RAM.
    """
    now = datetime.now()
    new_entry = {
        "user_id": user_id,
        "user_name": user_name,
        "entity_type": entity_type.upper(),
        "entity_id": str(entity_id) if entity_id is not None else None,
        "action": action.upper(),
        "field_name": field_name,
        "old_value": str(old_value) if old_value is not None else None,
        "new_value": str(new_value) if new_value is not None else None,
        "timestamp": now,
        "ip_address": ip_address or "127.0.0.1",
    }

    db_log = AuditLogModel(
        user_id=new_entry["user_id"],
        user_name=new_entry["user_name"],
        entity_type=new_entry["entity_type"],
        entity_id=new_entry["entity_id"],
        action=new_entry["action"],
        field_name=new_entry["field_name"],
        old_value=new_entry["old_value"],
        new_value=new_entry["new_value"],
        timestamp=new_entry["timestamp"],
        ip_address=new_entry["ip_address"],
    )

    if db is not None:
        db.add(db_log)
        db.flush()
        new_entry["id"] = db_log.id
    else:
        db_local = SessionLocal()
        try:
            db_local.add(db_log)
            db_local.commit()
            db_local.refresh(db_log)
            new_entry["id"] = db_log.id
        except Exception as e:
            db_local.rollback()
            raise e
        finally:
            db_local.close()

    fake_audit_logs_db.append(new_entry)
    return new_entry


def get_audit_logs(
    user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    AC S2-04: Lọc theo người dùng, loại đối tượng, khoảng thời gian.
    Đọc trực tiếp từ CSDL MySQL/SQLite. Không fallback RAM nếu DB gặp lỗi.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        query = db.query(AuditLogModel)

        if user_id is not None:
            query = query.filter(AuditLogModel.user_id == user_id)

        if entity_type and entity_type.strip():
            et_upper = entity_type.strip().upper()
            query = query.filter(AuditLogModel.entity_type == et_upper)

        if from_date is not None:
            query = query.filter(AuditLogModel.timestamp >= from_date)

        if to_date is not None:
            query = query.filter(AuditLogModel.timestamp <= to_date)

        total = query.count()
        rows = (
            query.order_by(desc(AuditLogModel.timestamp), desc(AuditLogModel.id))
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {
            "total": total,
            "items": [_row_to_dict(r) for r in rows],
        }
    except Exception as e:
        raise e
    finally:
        if own_session:
            db.close()


def clear_all_audit_logs() -> int:
    """Xóa sạch toàn bộ nhật ký thay đổi trong CSDL MySQL và RAM."""
    global fake_audit_logs_db
    deleted_count = len(fake_audit_logs_db)
    fake_audit_logs_db = []

    try:
        db = SessionLocal()
        db_count = db.query(AuditLogModel).count()
        db.query(AuditLogModel).delete()
        db.commit()
        db.close()
        return max(deleted_count, db_count)
    except Exception:
        return deleted_count

