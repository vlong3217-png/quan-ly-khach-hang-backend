"""
Tests for Sprint 4 - Task S4-09: Lead Filters & Saved Filters Backend
"Là Nhân viên kinh doanh, tôi muốn xem danh sách lead với bộ lọc và bộ lọc lưu sẵn, để mở máy buổi sáng là biết ngay hôm nay cần gọi ai."

Yêu cầu:
- API danh sách lead với bộ lọc đa dạng (status, source, grade, owner_id, khoảng thời gian).
- Lead quá hạn SLA (is_overdue_sla) được nhận diện và lọc nổi bật.
- Cho phép lưu và đặt tên các bộ lọc thường dùng (LeadSavedFilter).
- Kiểm tra quyền truy cập và scope dữ liệu (RBAC / Data Scope).
- Xử lý lỗi và validate dữ liệu đầy đủ.
"""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.models import Base
from app.models.lead import Lead, LeadSavedFilter

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
        db.query(LeadSavedFilter).delete()
        db.query(Lead).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(LeadSavedFilter).delete()
        db.query(Lead).delete()
        db.commit()
    finally:
        db.close()


# ============================================================================
# 1. Tests for Lead Filter Parameters (Status, Source, Grade, Owner, Date Range)
# ============================================================================

def test_filter_leads_by_status_and_source():
    """Lọc danh sách lead theo trạng thái (status) và nguồn (source)."""
    db = SessionLocal()
    try:
        lead1 = Lead(full_name="Nguyễn Văn A", email="a@crm.vn", status="NEW", source="Google Ads", owner_id=10)
        lead2 = Lead(full_name="Trần Thị B", email="b@crm.vn", status="IN_PROGRESS", source="Website Form", owner_id=10)
        lead3 = Lead(full_name="Lê Văn C", email="c@crm.vn", status="NEW", source="Facebook Ads", owner_id=10)
        db.add_all([lead1, lead2, lead3])
        db.commit()
    finally:
        db.close()

    headers = get_auth_headers(user_id=10, role="USER")

    # Lọc status=NEW
    res_status = client.get("/leads?status=NEW", headers=headers)
    assert res_status.status_code == 200
    data = res_status.json()
    assert data["total"] == 2
    assert all(item["status"] == "NEW" for item in data["items"])

    # Lọc source=Website Form
    res_source = client.get("/leads?source=Website Form", headers=headers)
    assert res_source.status_code == 200
    data_source = res_source.json()
    assert data_source["total"] == 1
    assert data_source["items"][0]["email"] == "b@crm.vn"


def test_filter_leads_by_grade_and_score():
    """Lọc danh sách lead theo phân loại Nóng/Ấm/Lạnh (grade) và điểm tối thiểu."""
    db = SessionLocal()
    try:
        lead_hot = Lead(full_name="Lead Hot", email="hot@crm.vn", grade="HOT", score=80, owner_id=10)
        lead_warm = Lead(full_name="Lead Warm", email="warm@crm.vn", grade="WARM", score=40, owner_id=10)
        lead_cold = Lead(full_name="Lead Cold", email="cold@crm.vn", grade="COLD", score=10, owner_id=10)
        db.add_all([lead_hot, lead_warm, lead_cold])
        db.commit()
    finally:
        db.close()

    headers = get_auth_headers(user_id=10, role="USER")

    res_grade = client.get("/leads?grade=HOT", headers=headers)
    assert res_grade.status_code == 200
    assert res_grade.json()["total"] == 1
    assert res_grade.json()["items"][0]["grade"] == "HOT"

    res_score = client.get("/leads?min_score=40", headers=headers)
    assert res_score.status_code == 200
    assert res_score.json()["total"] == 2


def test_filter_leads_by_date_range():
    """Lọc danh sách lead theo khoảng thời gian tạo (start_date, end_date)."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        lead_old = Lead(
            full_name="Lead Cũ",
            email="old@crm.vn",
            owner_id=10,
            created_at=now - timedelta(days=5),
        )
        lead_recent = Lead(
            full_name="Lead Mới Hôm Nay",
            email="recent@crm.vn",
            owner_id=10,
            created_at=now - timedelta(hours=2),
        )
        db.add_all([lead_old, lead_recent])
        db.commit()
    finally:
        db.close()

    headers = get_auth_headers(user_id=10, role="USER")

    # Lọc các lead được tạo trong vòng 1 ngày qua
    start_filter = (now - timedelta(days=1)).isoformat()
    res = client.get(f"/leads?start_date={start_filter}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["email"] == "recent@crm.vn"


# ============================================================================
# 2. Tests for SLA Overdue Identification & Filter
# ============================================================================

def test_filter_leads_by_sla_overdue_flag():
    """Nhận diện và lọc các lead vi phạm SLA phản hồi (is_overdue_sla=true)."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        # Lead 1: Quá hạn SLA (deadline ở quá khứ)
        lead_overdue = Lead(
            full_name="Lead Quá Hạn Phản Hồi",
            email="overdue@crm.vn",
            status="UNASSIGNED",
            sla_deadline=now - timedelta(hours=4),
            is_overdue_sla=False,  # Sẽ được tự động quét và đánh dấu True
            owner_id=10,
        )
        # Lead 2: Còn hạn SLA
        lead_ontime = Lead(
            full_name="Lead Còn Hạn",
            email="ontime@crm.vn",
            status="UNASSIGNED",
            sla_deadline=now + timedelta(hours=12),
            is_overdue_sla=False,
            owner_id=10,
        )
        db.add_all([lead_overdue, lead_ontime])
        db.commit()
    finally:
        db.close()

    headers = get_auth_headers(user_id=10, role="USER")

    # Lọc chỉ những lead quá hạn SLA để Sales buổi sáng mở máy là xử lý gấp
    res = client.get("/leads?is_overdue_sla=true", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["email"] == "overdue@crm.vn"
    assert data["items"][0]["is_overdue_sla"] is True


# ============================================================================
# 3. Tests for Data Scope & RBAC (User only sees own leads or unassigned)
# ============================================================================

def test_lead_list_data_scope_rbac():
    """
    Kiểm tra Scope dữ liệu:
    - USER chỉ thấy lead của mình hoặc lead chưa phân bổ (unassigned).
    - Không thấy lead được phân bổ riêng cho nhân viên khác.
    - ADMIN thấy toàn bộ lead trong hệ thống.
    """
    db = SessionLocal()
    try:
        lead_user10 = Lead(full_name="Lead của Sales 10", email="s10@crm.vn", owner_id=10, status="IN_PROGRESS")
        lead_user20 = Lead(full_name="Lead của Sales 20", email="s20@crm.vn", owner_id=20, status="IN_PROGRESS")
        lead_unassigned = Lead(full_name="Lead chung chưa nhận", email="free@crm.vn", owner_id=None, status="UNASSIGNED")
        db.add_all([lead_user10, lead_user20, lead_unassigned])
        db.commit()
    finally:
        db.close()

    # 1. Sales 10 gọi API: Thấy lead của mình và lead unassigned (Tổng: 2)
    headers_user10 = get_auth_headers(email="sales10@crm.vn", user_id=10, role="USER")
    res_user = client.get("/leads", headers=headers_user10)
    assert res_user.status_code == 200
    user_items = res_user.json()["items"]
    assert res_user.json()["total"] == 2
    emails = [item["email"] for item in user_items]
    assert "s10@crm.vn" in emails
    assert "free@crm.vn" in emails
    assert "s20@crm.vn" not in emails

    # 2. ADMIN gọi API: Thấy toàn bộ 3 lead
    headers_admin = get_auth_headers(email="admin@crm.vn", user_id=1, role="ADMIN")
    res_admin = client.get("/leads", headers=headers_admin)
    assert res_admin.status_code == 200
    assert res_admin.json()["total"] == 3


# ============================================================================
# 4. Tests for Lead Saved Filters (CRUD: Create, List, Delete, Reuse)
# ============================================================================

def test_lead_saved_filters_lifecycle():
    """
    Kiểm tra vòng đời của Bộ lọc lead đã lưu (S4-09):
    - Tạo bộ lọc lưu sẵn với tên cụ thể (VD: 'Hôm nay cần gọi - Lead Nóng').
    - Lấy danh sách bộ lọc của người dùng hiện tại (người dùng khác không thấy bộ lọc của nhau).
    - Xóa bộ lọc đã lưu.
    """
    headers_user10 = get_auth_headers(email="sales10@crm.vn", user_id=10, role="USER")
    headers_user20 = get_auth_headers(email="sales20@crm.vn", user_id=20, role="USER")

    # 1. User 10 tạo bộ lọc lưu sẵn
    payload_filter = {
        "name": "Mở máy buổi sáng - Cần gọi hôm nay",
        "filter_criteria": {
            "grade": "HOT",
            "is_overdue_sla": True,
            "status": "UNASSIGNED",
        },
    }
    res_create = client.post("/leads/saved-filters", json=payload_filter, headers=headers_user10)
    assert res_create.status_code == 201
    filter_data = res_create.json()
    assert filter_data["id"] is not None
    assert filter_data["name"] == "Mở máy buổi sáng - Cần gọi hôm nay"
    assert filter_data["filter_criteria"]["grade"] == "HOT"
    filter_id = filter_data["id"]

    # 2. User 10 xem danh sách bộ lọc của mình -> có filter_id
    res_list10 = client.get("/leads/saved-filters", headers=headers_user10)
    assert res_list10.status_code == 200
    list10_data = res_list10.json()
    assert len(list10_data) == 1
    assert list10_data[0]["id"] == filter_id

    # 3. User 20 xem danh sách bộ lọc của mình -> rỗng (độc lập quyền sở hữu)
    res_list20 = client.get("/leads/saved-filters", headers=headers_user20)
    assert res_list20.status_code == 200
    assert len(res_list20.json()) == 0

    # 4. User 10 xóa bộ lọc đã lưu
    res_delete = client.delete(f"/leads/saved-filters/{filter_id}", headers=headers_user10)
    assert res_delete.status_code == 204

    # 5. Kiểm tra lại danh sách bộ lọc của User 10 -> đã trống
    res_list10_after = client.get("/leads/saved-filters", headers=headers_user10)
    assert res_list10_after.status_code == 200
    assert len(res_list10_after.json()) == 0


def test_create_saved_filter_validation_empty_name():
    """Tạo bộ lọc lưu sẵn báo lỗi 422 hoặc 400 nếu để trống tên."""
    headers = get_auth_headers(user_id=10, role="USER")
    res = client.post("/leads/saved-filters", json={"name": "", "filter_criteria": {}}, headers=headers)
    assert res.status_code in [400, 422]


def test_delete_saved_filter_not_found():
    """Xóa bộ lọc không tồn tại trả về 404."""
    headers = get_auth_headers(user_id=10, role="USER")
    res = client.delete("/leads/saved-filters/999999", headers=headers)
    assert res.status_code == 404
