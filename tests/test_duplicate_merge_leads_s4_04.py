import pytest
import json
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.customer_service import reset_fake_customers
from app.services.activity_service import reset_fake_activities, FAKE_ACTIVITIES
from app.services import lead_service
from app.core.database import SessionLocal
from app.models.lead import LeadMergeHistory, Lead

client = TestClient(app)


def get_auth_token(email: str = "admin@gmail.com", password: str = "123456") -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(autouse=True)
def setup_data():
    reset_fake_users()
    reset_fake_customers()
    reset_fake_activities()
    lead_service.reset_fake_leads()
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_activities()
    lead_service.reset_fake_leads()


# ==============================================================================
# 1. AC S4-04: Phát hiện trùng theo email, số điện thoại và tên công ty
# ==============================================================================

def test_detect_duplicate_by_email_normalized():
    """Phát hiện trùng email không phân biệt chữ hoa thường."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Lead 1 mẫu có email: hung.tran@smarttech.vn
    resp = client.post(
        "/leads/check-duplicates?email=HUNG.TRAN@SMARTTECH.VN",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_duplicates"] is True
    assert len(data["matching_leads"]) >= 1
    match = data["matching_leads"][0]
    assert match["lead"]["id"] == 1
    assert any("email" in r.lower() for r in match["match_reasons"])
    assert match["confidence_score"] >= 0.9


def test_detect_duplicate_by_phone_normalized():
    """Phát hiện trùng SĐT có định dạng dấu gạch nối hoặc khoảng trắng."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Lead 1 mẫu có SĐT: 0912345678
    resp = client.post(
        "/leads/check-duplicates?phone=0912-345-678",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_duplicates"] is True
    match = data["matching_leads"][0]
    assert match["lead"]["id"] == 1
    assert any("điện thoại" in r.lower() for r in match["match_reasons"])


def test_detect_duplicate_by_company_name():
    """Phát hiện trùng tên công ty khi đã loại bỏ tiền tố/hậu tố pháp lý (Công ty TNHH...)."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Lead 1 có công ty: Công ty TNHH SmartTech
    resp = client.post(
        "/leads/check-duplicates?company_name=SmartTech",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_duplicates"] is True
    assert len(data["matching_leads"]) >= 1


def test_get_duplicates_for_existing_lead_api():
    """API GET /leads/{id}/duplicates phát hiện trùng cho 1 lead cụ thể."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo thêm 1 lead có cùng email với lead 1
    client.post("/leads", json={
        "name": "Trần Văn Hùng Trùng Lặp",
        "email": "hung.tran@smarttech.vn",
        "phone": "0999888777",
        "source": "Sự kiện",
    }, headers=headers)

    resp = client.get("/leads/1/duplicates", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_duplicates"] is True
    # Phải tìm thấy lead vừa tạo (không tính chính lead 1)
    matched_ids = [m["lead"]["id"] for m in data["matching_leads"]]
    assert 1 not in matched_ids
    assert len(matched_ids) >= 1


# ==============================================================================
# 2. AC S4-04: Lead trùng với khách hàng đã có được gợi ý gắn thẳng vào khách hàng đó
# ==============================================================================

def test_detect_duplicate_with_existing_customer():
    """Phát hiện trùng với thông tin khách hàng (Customer) đã có trong hệ thống."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Khách hàng 1: Công ty Cổ phần Công nghệ ABC (contact@abc-tech.vn / 02431234567)
    resp = client.post(
        "/leads/check-duplicates?email=contact@abc-tech.vn",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_duplicates"] is True
    assert len(data["matching_customers"]) >= 1
    cust_match = data["matching_customers"][0]
    assert cust_match["customer"]["id"] == 1
    assert any("Khách hàng #1" in r for r in cust_match["match_reasons"])


def test_attach_lead_to_customer_creates_contact():
    """Gợi ý và gắn lead vào khách hàng đã có, tự động tạo Contact mới."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo 1 lead
    lead_res = client.post("/leads", json={
        "name": "Nguyễn Minh Đức",
        "email": "duc.nguyen@abc-tech.vn",
        "phone": "0918765432",
        "title": "Chuyên viên Mua hàng",
        "source": "Website",
        "company_name": "Công ty Cổ phần Công nghệ ABC",
    }, headers=headers)
    assert lead_res.status_code == 201
    lead_id = lead_res.json()["id"]

    # Gắn lead vào Khách hàng ID 1 (Công ty Cổ phần Công nghệ ABC)
    attach_payload = {
        "customer_id": 1,
        "create_contact": True,
    }
    resp = client.post(f"/leads/{lead_id}/attach-to-customer", json=attach_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Kiểm tra lead đã gắn customer_id và đổi status sang CONVERTED
    assert data["customer_id"] == 1
    assert data["status"] == "CONVERTED"
    assert data["created_contact"] is not None
    assert data["created_contact"]["name"] == "Nguyễn Minh Đức"
    assert data["created_contact"]["customer_id"] == 1


def test_attach_lead_to_nonexistent_customer_returns_404():
    """Gắn lead vào khách hàng không tồn tại trả về 404."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/leads/1/attach-to-customer", json={"customer_id": 999999}, headers=headers)
    assert resp.status_code == 404


# ==============================================================================
# 3. AC S4-04: Gộp giữ nguyên lịch sử của cả hai bản ghi
# ==============================================================================

def test_preview_lead_merge():
    """Xem trước so sánh giữa 2 lead và số hoạt động sẽ được chuyển giao."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Thêm 1 activity gắn với lead 2
    FAKE_ACTIVITIES.append({
        "id": 99,
        "title": "Cuộc gọi chăm sóc Lead 2",
        "type": "CALL",
        "description": "Đã gọi điện tư vấn",
        "lead_id": 2,
    })

    resp = client.post("/leads/merge-preview", json={
        "primary_lead_id": 1,
        "secondary_lead_id": 2,
    }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["primary"]["id"] == 1
    assert data["secondary"]["id"] == 2
    assert len(data["comparison_fields"]) > 0
    assert data["activities_to_transfer"] >= 1


def test_cannot_merge_lead_with_itself():
    """Không thể gộp một lead với chính nó."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/leads/merge", json={
        "primary_lead_id": 1,
        "secondary_lead_id": 1,
    }, headers=headers)
    assert resp.status_code == 400
    assert "chính nó" in resp.json()["detail"]


def test_merge_leads_preserves_history_and_activities():
    """Gộp 2 lead: giữ nguyên lịch sử hoạt động, lưu snapshot và đánh dấu MERGED."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Gắn hoạt động vào lead 2 (secondary)
    act_id = 999
    FAKE_ACTIVITIES.append({
        "id": act_id,
        "title": "Email trao đổi với Lead 2",
        "type": "EMAIL",
        "lead_id": 2,
    })

    merge_payload = {
        "primary_lead_id": 1,
        "secondary_lead_id": 2,
        "chosen_fields": {
            "title": "Giám đốc Marketing & CNTT",  # Chọn giữ chức danh tùy chỉnh
        },
    }
    resp = client.post("/leads/merge", json=merge_payload, headers=headers)
    assert resp.status_code == 200
    primary_data = resp.json()

    # 1. Lead 1 (primary) được cập nhật
    assert primary_data["id"] == 1
    assert primary_data["title"] == "Giám đốc Marketing & CNTT"
    assert "Gộp từ Lead #2" in primary_data["notes"]

    # 2. Hoạt động của Lead 2 được chuyển sang Lead 1
    act = next((a for a in FAKE_ACTIVITIES if a["id"] == act_id), None)
    assert act is not None
    assert act["lead_id"] == 1

    # 3. Lead 2 (secondary) chuyển sang trạng thái MERGED và có merged_into_id = 1
    db = SessionLocal()
    try:
        sec_lead = db.query(Lead).filter(Lead.id == 2).first()
        assert sec_lead.status == "MERGED"
        assert sec_lead.merged_into_id == 1

        # 4. Snapshot được lưu trong LeadMergeHistory
        history = db.query(LeadMergeHistory).filter(
            LeadMergeHistory.primary_lead_id == 1,
            LeadMergeHistory.secondary_lead_id == 2,
        ).first()
        assert history is not None
        assert history.secondary_lead_name == "Nguyễn Thị Mai"
        snapshot = json.loads(history.secondary_snapshot)
        assert snapshot["id"] == 2
        assert snapshot["email"] == "mai.nguyen@dainam.com"
    finally:
        db.close()

    # 5. Lead bị gộp không còn xuất hiện trong danh sách lead mặc định
    list_resp = client.get("/leads", headers=headers)
    assert list_resp.status_code == 200
    listed_ids = [l["id"] for l in list_resp.json()["items"]]
    assert 2 not in listed_ids
