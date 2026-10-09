"""
Service layer for Lead Management - Task S4-07: Lead Response
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.lead import Lead
from app.schemas.lead import LeadCreate, LeadRejectSchema, LeadStatus, LeadUpdate


def _get_db(db: Optional[Session] = None):
    if db is not None:
        return db, False
    return SessionLocal(), True


def get_lead_by_id(lead_id: int, db: Optional[Session] = None) -> Optional[Lead]:
    session, own = _get_db(db)
    try:
        return session.query(Lead).filter(Lead.id == lead_id).first()
    finally:
        if own:
            session.close()


def list_leads(
    status_filter: Optional[str] = None,
    is_overdue_sla: Optional[bool] = None,
    assigned_to: Optional[int] = None,
    db: Optional[Session] = None,
) -> List[Lead]:
    session, own = _get_db(db)
    try:
        query = session.query(Lead)
        if status_filter:
            query = query.filter(Lead.status == status_filter)
        if is_overdue_sla is not None:
            query = query.filter(Lead.is_overdue_sla == is_overdue_sla)
        if assigned_to is not None:
            query = query.filter(Lead.assigned_to == assigned_to)
        return query.order_by(Lead.id.desc()).all()
    finally:
        if own:
            session.close()


def create_lead(lead_data: LeadCreate, db: Optional[Session] = None) -> Lead:
    session, own = _get_db(db)
    try:
        lead_dict = lead_data.model_dump(exclude_unset=True)
        # Tự động gán sla_deadline nếu chưa có (mặc định 24h)
        if "sla_deadline" not in lead_dict or lead_dict["sla_deadline"] is None:
            lead_dict["sla_deadline"] = datetime.now(timezone.utc) + timedelta(hours=24)
        lead = Lead(**lead_dict)
        session.add(lead)
        session.commit()
        session.refresh(lead)
        return lead
    except Exception:
        session.rollback()
        raise
    finally:
        if own:
            session.close()


def update_lead(lead_id: int, lead_data: LeadUpdate, db: Optional[Session] = None) -> Lead:
    session, own = _get_db(db)
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead với ID {lead_id} không tồn tại",
            )
        update_data = lead_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(lead, key, value)
        lead.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(lead)
        return lead
    except Exception:
        session.rollback()
        raise
    finally:
        if own:
            session.close()


def delete_lead(lead_id: int, db: Optional[Session] = None) -> bool:
    session, own = _get_db(db)
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead với ID {lead_id} không tồn tại",
            )
        session.delete(lead)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        if own:
            session.close()


def accept_lead(lead_id: int, user_id: Optional[int] = None, db: Optional[Session] = None) -> Lead:
    """
    Tiếp nhận lead: đổi status sang IN_PROGRESS.
    Nếu user_id được chỉ định, gán assigned_to = user_id.
    """
    session, own = _get_db(db)
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead với ID {lead_id} không tồn tại",
            )

        lead.status = LeadStatus.IN_PROGRESS.value
        if user_id is not None:
            lead.assigned_to = user_id
        lead.updated_at = datetime.now(timezone.utc)

        session.commit()
        session.refresh(lead)
        return lead
    except Exception:
        session.rollback()
        raise
    finally:
        if own:
            session.close()


def reject_lead(
    lead_id: int,
    reason: str,
    user_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> Lead:
    """
    Từ chối tiếp nhận lead:
    - Bắt buộc phải có lý do (reason).
    - Đổi status sang UNASSIGNED.
    - Gán assigned_to = None.
    - Lưu rejection_reason.
    """
    if not reason or not str(reason).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lý do từ chối không được để trống",
        )

    session, own = _get_db(db)
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead với ID {lead_id} không tồn tại",
            )

        lead.status = LeadStatus.UNASSIGNED.value
        lead.assigned_to = None
        lead.rejection_reason = str(reason).strip()
        lead.updated_at = datetime.now(timezone.utc)

        session.commit()
        session.refresh(lead)
        return lead
    except Exception:
        session.rollback()
        raise
    finally:
        if own:
            session.close()


def check_sla_violations(
    sla_minutes: Optional[int] = None,
    current_time: Optional[datetime] = None,
    db: Optional[Session] = None,
) -> List[Lead]:
    """
    Kiểm tra vi phạm SLA phản hồi lead:
    - Áp dụng cho các lead chưa được tiếp nhận xử lý (status != IN_PROGRESS, CONVERTED, DISQUALIFIED)
    - Nếu đã qua sla_deadline hoặc vượt quá threshold (sla_minutes) thì gán is_overdue_sla = True.
    - Trả về danh sách các lead vi phạm SLA.
    """
    now = current_time or datetime.now(timezone.utc)
    session, own = _get_db(db)
    try:
        leads = session.query(Lead).all()
        violated_leads: List[Lead] = []
        for lead in leads:
            # Chỉ kiểm tra các lead chưa vào xử lý
            if lead.status in [LeadStatus.UNASSIGNED.value, LeadStatus.ASSIGNED.value]:
                is_overdue = False

                # Kiểm tra hạn chót sla_deadline
                if lead.sla_deadline is not None:
                    deadline = lead.sla_deadline
                    if deadline.tzinfo is None and now.tzinfo is not None:
                        deadline = deadline.replace(tzinfo=timezone.utc)
                    elif deadline.tzinfo is not None and now.tzinfo is None:
                        deadline = deadline.replace(tzinfo=None)
                    if now > deadline:
                        is_overdue = True

                # Kiểm tra số phút từ lúc tạo lead nếu có cấu hình sla_minutes
                if sla_minutes is not None and lead.created_at is not None:
                    created_at = lead.created_at
                    if created_at.tzinfo is None and now.tzinfo is not None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    elif created_at.tzinfo is not None and now.tzinfo is None:
                        created_at = created_at.replace(tzinfo=None)
                    if (now - created_at) > timedelta(minutes=sla_minutes):
                        is_overdue = True

                if is_overdue:
                    lead.is_overdue_sla = True
                    violated_leads.append(lead)

        session.commit()
        for v in violated_leads:
            session.refresh(v)
        return violated_leads
    except Exception:
        session.rollback()
        raise
    finally:
        if own:
            session.close()
