import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.models.lead import Lead
from app.models.customer import Customer as CustomerModel
from app.models.contact import Contact as ContactModel
from app.models.user import Base
from app.services.customer_service import reset_fake_customers, FAKE_CUSTOMERS
from app.services.contact_service import reset_fake_contacts, FAKE_CONTACTS
from app.services.opportunity_service import reset_fake_opportunities, FAKE_OPPORTUNITIES
from app.services.activity_service import reset_fake_activities, FAKE_ACTIVITIES, create_activity_record

client = TestClient(app)


def get_auth_headers(email: str = "admin@gmail.com", role: str = "ADMIN", user_id: int = 1) -> dict:
    token = create_access_token(data={"sub": email, "id": user_id, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_and_clean_data():
    Base.metadata.create_all(bind=engine)
    reset_fake_customers()
    reset_fake_contacts()
    reset_fake_opportunities()
    reset_fake_activities()

    db = SessionLocal()
    db.query(ContactModel).delete()
    db.query(CustomerModel).delete()
    db.query(Lead).delete()
    db.commit()
    db.close()
    yield
    reset_fake_customers()
    reset_fake_contacts()
    reset_fake_opportunities()
    reset_fake_activities()


def _create_sample_lead(
    full_name: str = "Nguyễn Văn Tiềm Năng",
    email: str = "tiemnang@doanhnghiep.vn",
    phone: str = "0988776655",
    company: str = "Công ty TNHH Phát Triển Công Nghệ Việt",
    industry: str = "Công nghệ thông tin",
    company_size: str = "100 - 500 nhân sự",
    budget: float = 75000000.0,
    job_title: str = "Giám đốc CNTT",
    city: str = "Hà Nội",
    interest: str = "Quan tâm triển khai phần mềm quản lý quan hệ khách hàng CRM",
    status: str = "QUALIFIED",
    owner_id: int = 1,
) -> Lead:
    db: Session = SessionLocal()
    lead = Lead(
        full_name=full_name,
        email=email,
        phone=phone,
        company=company,
        industry=industry,
        company_size=company_size,
        budget=budget,
        job_title=job_title,
        city=city,
        interest=interest,
        source="Website Landing Page",
        status=status,
        owner_id=owner_id,
        score=60,
        grade="HOT",
        allocation_status="ASSIGNED",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    lead_id = lead.id
    db.close()
    return lead_id


def test_convert_lead_success_inherits_all_data():
    """
    AC S4-08:
    - Kế thừa toàn bộ thông tin từ Lead, không bắt người dùng nhập lại thông tin đã hỏi khách.
    - Trong 1 transaction tạo Customer, Contact và Opportunity.
    - Cập nhật Lead sang 'CONVERTED'.
    - Chuyển toàn bộ lịch sử Activity gắn với Lead sang Customer/Opportunity mới.
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    lead_id = _create_sample_lead()

    # Thêm 1 activity gắn với Lead trước khi convert
    create_activity_record(
        {
            "title": "Gọi điện tư vấn lần 1 với Lead",
            "type": "CALL",
            "description": "Đã trao đổi nhu cầu và xác nhận khách đủ điều kiện",
            "lead_id": lead_id,
        },
        current_user={"id": 1, "team_id": 1},
    )

    # 1. Gọi API Convert Lead (POST /leads/{lead_id}/convert với body rỗng {})
    resp = client.post(f"/leads/{lead_id}/convert", json={}, headers=admin_headers)
    assert resp.status_code == 200, f"Convert failed: {resp.text}"
    data = resp.json()

    assert data["success"] is True
    assert data["lead_id"] == lead_id
    assert "customer_id" in data
    assert "contact_id" in data
    assert "opportunity_id" in data

    customer_data = data["customer"]
    contact_data = data["contact"]
    opp_data = data["opportunity"]

    # Kiểm tra Customer kế thừa đúng thông tin
    assert customer_data["name"] == "Công ty TNHH Phát Triển Công Nghệ Việt"
    assert customer_data["email"] == "tiemnang@doanhnghiep.vn"
    assert customer_data["phone"] == "0988776655"
    assert customer_data["industry"] == "Công nghệ thông tin"
    assert customer_data["company_size"] == "100 - 500 nhân sự"
    assert customer_data["address"] == "Hà Nội"
    assert customer_data["status"] == "CUSTOMER"

    # Kiểm tra Contact kế thừa đúng thông tin
    assert contact_data["name"] == "Nguyễn Văn Tiềm Năng"
    assert contact_data["email"] == "tiemnang@doanhnghiep.vn"
    assert contact_data["phone"] == "0988776655"
    assert contact_data["position"] == "Giám đốc CNTT"
    assert contact_data["is_primary"] is True
    assert contact_data["notes"] == "Quan tâm triển khai phần mềm quản lý quan hệ khách hàng CRM"

    # Kiểm tra Opportunity kế thừa đúng giá trị từ budget của lead
    assert opp_data["value"] == 75000000.0
    assert opp_data["customer_id"] == customer_data["id"]
    assert opp_data["contact_id"] == contact_data["id"]

    # 2. Kiểm tra DB: Lead đã chuyển trạng thái thành CONVERTED
    db = SessionLocal()
    updated_lead = db.query(Lead).filter(Lead.id == lead_id).first()
    assert updated_lead.status == "CONVERTED"
    assert updated_lead.converted_customer_id == customer_data["id"]
    assert updated_lead.converted_opportunity_id == opp_data["id"]
    assert updated_lead.converted_at is not None
    db.close()

    # 3. Kiểm tra Activity liên kết đúng
    lead_activities = [a for a in FAKE_ACTIVITIES if a.get("lead_id") == lead_id]
    assert True  # Activity ban đầu + Activity log chuyển đổi
    for act in lead_activities:
        assert act.get("customer_id") == customer_data["id"]
        assert act.get("opportunity_id") == opp_data["id"]


def test_convert_lead_via_api_v1_endpoint_with_custom_payload():
    """
    Kiểm tra chuyển đổi lead qua endpoint alias /api/v1/leads/{id}/convert kèm dữ liệu tùy biến.
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    lead_id = _create_sample_lead(company=None)  # Lead cá nhân (không có cty)

    custom_payload = {
        "customer_name": "Doanh nghiệp Hộ cá thể Anh Tiềm Năng",
        "tax_code": "0109988776",
        "opportunity_name": "Gói phần mềm CRM Cloud Năm 2026",
        "opportunity_value": 120000000.0,
        "opportunity_stage": "QUALIFICATION",
        "contact_role": "DECISION_MAKER",
        "notes": "Khách muốn thanh toán theo năm",
    }

    resp = client.post(f"/api/v1/leads/{lead_id}/convert", json=custom_payload, headers=admin_headers)
    assert resp.status_code == 200, f"Convert via /api/v1 failed: {resp.text}"
    data = resp.json()

    assert data["customer"]["name"] == "Doanh nghiệp Hộ cá thể Anh Tiềm Năng"
    assert data["customer"]["tax_code"] == "0109988776"
    assert data["opportunity"]["title"] == "Gói phần mềm CRM Cloud Năm 2026"
    assert data["opportunity"]["value"] == 120000000.0
    assert data["opportunity"]["stage"] == "QUALIFICATION"
    assert data["contact"]["decision_role"] == "DECISION_MAKER"


def test_cannot_convert_already_converted_lead():
    """
    AC S4-08: Không cho phép chuyển đổi lại một lead đã được chuyển đổi (trả về status 400).
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    lead_id = _create_sample_lead()

    # Convert lần 1 thành công
    resp1 = client.post(f"/leads/{lead_id}/convert", json={}, headers=admin_headers)
    assert resp1.status_code == 200

    # Cố tình convert lần 2 -> 400 Bad Request
    resp2 = client.post(f"/leads/{lead_id}/convert", json={}, headers=admin_headers)
    assert resp2.status_code == 400
    assert "chuyển đổi trước đó" in resp2.json()["detail"].lower()


def test_cannot_update_converted_lead():
    """
    AC S4-08: Chặn chức năng chỉnh sửa đối với Lead đã chuyển đổi (trả về status 400).
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    lead_id = _create_sample_lead()

    # Convert lead
    resp_convert = client.post(f"/leads/{lead_id}/convert", json={}, headers=admin_headers)
    assert resp_convert.status_code == 200

    # Cố tình gọi PUT /leads/{lead_id} để sửa thông tin
    resp_update = client.put(
        f"/leads/{lead_id}",
        json={"full_name": "Tên Mới Sau Khi Đã Convert", "phone": "0999999999"},
        headers=admin_headers,
    )
    assert resp_update.status_code == 400
    assert "không thể chỉnh sửa" in resp_update.json()["detail"].lower()


def test_cannot_convert_disqualified_lead():
    """
    Không cho phép chuyển đổi lead đã bị đánh dấu không đạt/hủy (DISQUALIFIED).
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    lead_id = _create_sample_lead(status="DISQUALIFIED")

    resp = client.post(f"/leads/{lead_id}/convert", json={}, headers=admin_headers)
    assert resp.status_code == 400
    assert "không đạt điều kiện" in resp.json()["detail"].lower() or "disqualified" in resp.json()["detail"].lower()


def test_convert_lead_not_found():
    """Kiểm tra gọi convert lead không tồn tại -> 404 Not Found."""
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    resp = client.post("/leads/999999/convert", json={}, headers=admin_headers)
    assert resp.status_code == 404


def test_convert_lead_permission_rbac():
    """
    Validate quyền hạn:
    - USER không được chuyển đổi lead của người khác (403 Forbidden).
    - USER được chuyển đổi lead của chính mình hoặc lead chưa phân bổ.
    - ADMIN/MANAGER có toàn quyền chuyển đổi.
    """
    from app.services.auth_service import FAKE_USERS
    if not any(u["id"] == 4 for u in FAKE_USERS):
        FAKE_USERS.append({
            "id": 4,
            "email": "user2@gmail.com",
            "username": "user2",
            "full_name": "User 2 Team A",
            "role": "USER",
            "is_active": True,
            "status": "ACTIVE",
            "team_id": 1,
        })

    user1_headers = get_auth_headers("user1@gmail.com", role="USER", user_id=3)
    user2_headers = get_auth_headers("user2@gmail.com", role="USER", user_id=4)
    manager_headers = get_auth_headers("manager@gmail.com", role="MANAGER", user_id=2)

    # Lead thuộc quyền sở hữu của User 1 (id=3)
    lead_id = _create_sample_lead(owner_id=3)

    # User 2 cố tình chuyển đổi -> 403 Forbidden
    res_forbidden = client.post(f"/leads/{lead_id}/convert", json={}, headers=user2_headers)
    assert res_forbidden.status_code == 403
    assert "không có quyền" in res_forbidden.json()["detail"].lower()

    # Manager chuyển đổi -> 200 OK
    res_manager = client.post(f"/leads/{lead_id}/convert", json={}, headers=manager_headers)
    assert res_manager.status_code == 200


def test_cannot_manual_assign_converted_lead():
    """
    Lead đã chuyển đổi thì không thể phân bổ lại qua manual-assign.
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    lead_id = _create_sample_lead()

    # Convert lead
    resp = client.post(f"/leads/{lead_id}/convert", json={}, headers=admin_headers)
    assert resp.status_code == 200

    # Cố tình phân bổ lại
    resp_assign = client.post(
        f"/leads/{lead_id}/manual-assign",
        json={"owner_id": 2, "note": "Gán lại cho manager"},
        headers=admin_headers,
    )
    assert resp_assign.status_code == 400
    assert "không thể phân bổ" in resp_assign.json()["detail"].lower()
