"""
Tests for Task S4-07: Lead Response Backend
- LeadRejectSchema validation (required reason)
- Lead model columns (rejection_reason, is_overdue_sla default False)
- lead_service functions: accept_lead, reject_lead, check_sla_violations
- API endpoints: POST /leads/{id}/accept, POST /leads/{id}/reject
"""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.models import Base
from app.models.lead import Lead
from app.schemas.lead import (
    LeadCreate,
    LeadRejectSchema,
    LeadResponse,
    LeadStatus,
)
from app.services import lead_service

client = TestClient(app)


def get_auth_headers(email: str = "sales@crm.vn", user_id: int = 10, role: str = "USER") -> dict:
    token = create_access_token({
        "sub": email,
        "id": user_id,
        "role": role,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Lead).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(Lead).delete()
        db.commit()
    finally:
        db.close()


# ==========================================
# 1. Tests for Schema: LeadRejectSchema
# ==========================================

def test_lead_reject_schema_valid():
    """LeadRejectSchema hợp lệ khi có trường reason."""
    schema = LeadRejectSchema(reason="Khách hàng không có nhu cầu trong năm nay")
    assert schema.reason == "Khách hàng không có nhu cầu trong năm nay"


def test_lead_reject_schema_missing_reason_raises_error():
    """LeadRejectSchema báo lỗi khi thiếu trường reason."""
    with pytest.raises(ValidationError):
        LeadRejectSchema()


def test_lead_reject_schema_empty_reason_raises_error():
    """LeadRejectSchema báo lỗi khi reason để trống hoặc toàn khoảng trắng."""
    with pytest.raises(ValidationError):
        LeadRejectSchema(reason="")
    with pytest.raises(ValidationError):
        LeadRejectSchema(reason="   ")


# ==========================================
# 2. Tests for Model: Lead
# ==========================================

def test_lead_model_columns():
    """Kiểm tra Lead model có cột rejection_reason và is_overdue_sla mặc định là False."""
    db = SessionLocal()
    try:
        lead = Lead(
            name="Nguyễn Văn Test",
            email="test@company.vn",
            phone="0901234567",
            status="UNASSIGNED",
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        assert lead.id is not None
        assert lead.name == "Nguyễn Văn Test"
        assert lead.rejection_reason is None
        assert lead.is_overdue_sla is False
    finally:
        db.close()


# ==========================================
# 3. Tests for Services: accept_lead, reject_lead, check_sla_violations
# ==========================================

def test_service_accept_lead():
    """accept_lead đổi status sang IN_PROGRESS và gán assigned_to nếu truyền user_id."""
    db = SessionLocal()
    try:
        lead = Lead(
            name="Công ty ABC",
            status="UNASSIGNED",
            assigned_to=None,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_id = lead.id

        updated = lead_service.accept_lead(lead_id=lead_id, user_id=99, db=db)
        assert updated.status == LeadStatus.IN_PROGRESS.value
        assert updated.assigned_to == 99
    finally:
        db.close()


def test_service_accept_lead_not_found():
    """accept_lead với ID không tồn tại trả về lỗi 404."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        lead_service.accept_lead(lead_id=99999)
    assert exc_info.value.status_code == 404


def test_service_reject_lead():
    """reject_lead đổi status sang UNASSIGNED, gán assigned_to=None, và lưu rejection_reason."""
    db = SessionLocal()
    try:
        lead = Lead(
            name="Công ty XYZ",
            status="IN_PROGRESS",
            assigned_to=45,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_id = lead.id

        reason = "Số điện thoại sai, không liên lạc được"
        updated = lead_service.reject_lead(lead_id=lead_id, reason=reason, db=db)

        assert updated.status == LeadStatus.UNASSIGNED.value
        assert updated.assigned_to is None
        assert updated.rejection_reason == reason
    finally:
        db.close()


def test_service_reject_lead_empty_reason_raises():
    """reject_lead từ chối khi không có lý do hoặc lý do rỗng."""
    from fastapi import HTTPException
    db = SessionLocal()
    try:
        lead = Lead(name="Test Lead", status="IN_PROGRESS")
        db.add(lead)
        db.commit()
        db.refresh(lead)

        with pytest.raises(HTTPException) as exc_info:
            lead_service.reject_lead(lead_id=lead.id, reason="", db=db)
        assert exc_info.value.status_code == 400
    finally:
        db.close()


def test_service_check_sla_violations():
    """check_sla_violations đánh dấu is_overdue_sla = True cho các lead quá hạn chưa tiếp nhận."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        # Lead 1: Quá hạn SLA (deadline ở quá khứ), chưa nhận -> vi phạm
        lead1 = Lead(
            name="Lead Quá Hạn",
            status="UNASSIGNED",
            sla_deadline=now - timedelta(hours=2),
            is_overdue_sla=False,
        )
        # Lead 2: Còn hạn SLA (deadline ở tương lai), chưa nhận -> không vi phạm
        lead2 = Lead(
            name="Lead Còn Hạn",
            status="UNASSIGNED",
            sla_deadline=now + timedelta(hours=5),
            is_overdue_sla=False,
        )
        # Lead 3: Deadline ở quá khứ nhưng đã IN_PROGRESS -> không vi phạm phản hồi
        lead3 = Lead(
            name="Lead Đã Xử Lý",
            status="IN_PROGRESS",
            sla_deadline=now - timedelta(hours=1),
            is_overdue_sla=False,
        )

        db.add_all([lead1, lead2, lead3])
        db.commit()

        violations = lead_service.check_sla_violations(current_time=now, db=db)

        violated_ids = [v.id for v in violations]
        assert lead1.id in violated_ids
        assert lead2.id not in violated_ids
        assert lead3.id not in violated_ids

        db.refresh(lead1)
        db.refresh(lead2)
        db.refresh(lead3)
        assert lead1.is_overdue_sla is True
        assert lead2.is_overdue_sla is False
        assert lead3.is_overdue_sla is False
    finally:
        db.close()


# ==========================================
# 4. Tests for API Endpoints: POST /{id}/accept, POST /{id}/reject
# ==========================================

def test_api_accept_lead_success():
    """API POST /leads/{id}/accept tiếp nhận lead thành công và đổi status thành IN_PROGRESS."""
    db = SessionLocal()
    try:
        lead = Lead(name="Khách Hàng Tiềm Năng 1", status="UNASSIGNED")
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_id = lead.id
    finally:
        db.close()

    headers = get_auth_headers(user_id=12)
    res = client.post(f"/leads/{lead_id}/accept", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == lead_id
    assert data["status"] == "IN_PROGRESS"
    assert data["assigned_to"] == 12


def test_api_accept_lead_not_found():
    """API POST /leads/{id}/accept trả về 404 nếu id không tồn tại."""
    res = client.post("/leads/999999/accept")
    assert res.status_code == 404


def test_api_reject_lead_success():
    """API POST /leads/{id}/reject từ chối lead thành công: status UNASSIGNED, assigned_to null, lưu lý do."""
    db = SessionLocal()
    try:
        lead = Lead(name="Khách Hàng Tiềm Năng 2", status="IN_PROGRESS", assigned_to=5)
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_id = lead.id
    finally:
        db.close()

    headers = get_auth_headers(user_id=5)
    payload = {"reason": "Khách hàng thông báo nhầm số, không có nhu cầu"}
    res = client.post(f"/leads/{lead_id}/reject", json=payload, headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["id"] == lead_id
    assert data["status"] == "UNASSIGNED"
    assert data["assigned_to"] is None
    assert data["rejection_reason"] == payload["reason"]


def test_api_reject_lead_missing_reason_returns_422():
    """API POST /leads/{id}/reject trả về 422 khi thiếu trường reason."""
    db = SessionLocal()
    try:
        lead = Lead(name="Khách Hàng Tiềm Năng 3", status="IN_PROGRESS", assigned_to=5)
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_id = lead.id
    finally:
        db.close()

    res = client.post(f"/leads/{lead_id}/reject", json={})
    assert res.status_code == 422


def test_api_reject_lead_empty_reason_returns_422():
    """API POST /leads/{id}/reject trả về 422 khi reason rỗng."""
    db = SessionLocal()
    try:
        lead = Lead(name="Khách Hàng Tiềm Năng 4", status="IN_PROGRESS", assigned_to=5)
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_id = lead.id
    finally:
        db.close()

    res = client.post(f"/leads/{lead_id}/reject", json={"reason": "   "})
    assert res.status_code == 422


def test_api_reject_lead_not_found():
    """API POST /leads/{id}/reject trả về 404 nếu id không tồn tại."""
    res = client.post("/leads/999999/reject", json={"reason": "Không rõ lý do"})
    assert res.status_code == 404


def test_api_v1_endpoints_compatibility():
    """Đảm bảo route /api/v1/leads/{id}/accept và /api/v1/leads/{id}/reject cũng hoạt động."""
    db = SessionLocal()
    try:
        lead = Lead(name="Khách Hàng V1", status="UNASSIGNED")
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_id = lead.id
    finally:
        db.close()

    # Accept via /api/v1
    res_acc = client.post(f"/api/v1/leads/{lead_id}/accept")
    assert res_acc.status_code == 200
    assert res_acc.json()["status"] == "IN_PROGRESS"

    # Reject via /api/v1
    res_rej = client.post(f"/api/v1/leads/{lead_id}/reject", json={"reason": "Từ chối kiểm tra qua API v1"})
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "UNASSIGNED"
    assert res_rej.json()["rejection_reason"] == "Từ chối kiểm tra qua API v1"
