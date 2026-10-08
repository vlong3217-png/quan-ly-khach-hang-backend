import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.contact_service import reset_fake_contacts
from app.services.customer_service import reset_fake_customers
from app.services.ticket_service import reset_fake_tickets

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
    reset_fake_contacts()
    reset_fake_tickets()
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_contacts()
    reset_fake_tickets()


def test_create_and_update_support_ticket():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Tạo ticket hỗ trợ mới
    payload = {
        "customer_id": 1,
        "title": "Lỗi đồng bộ danh bạ khách hàng",
        "description": "Dữ liệu danh bạ không hiển thị trên mobile app",
        "priority": "HIGH",
        "status": "OPEN",
    }
    resp = client.post("/tickets", json=payload, headers=headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"] > 0
    assert created["priority"] == "HIGH"
    ticket_id = created["id"]

    # 2. Cập nhật ticket thành RESOLVED
    update_payload = {
        "status": "RESOLVED",
        "resolution_note": "Đã sửa xong phiên bản ứng dụng 2.1",
    }
    resp_update = client.put(f"/tickets/{ticket_id}", json=update_payload, headers=headers)
    assert resp_update.status_code == 200
    assert resp_update.json()["status"] == "RESOLVED"
    assert resp_update.json()["resolution_note"] == "Đã sửa xong phiên bản ứng dụng 2.1"


def test_churn_risk_flagging_and_customer_360():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Customer 1 ban đầu đã có Ticket 1 (priority: HIGH, status: OPEN)
    # Thêm 1 ticket nữa để làm rõ nguy cơ rời bỏ
    client.post(
        "/tickets",
        json={
            "customer_id": 1,
            "title": "Phàn nàn về dịch vụ chăm sóc chậm trễ",
            "priority": "CRITICAL",
            "status": "OPEN",
        },
        headers=headers,
    )

    # Đánh giá churn risk
    risk_resp = client.get("/tickets/churn-risk/1", headers=headers)
    assert risk_resp.status_code == 200
    rdata = risk_resp.json()
    assert rdata["is_at_risk"] is True
    assert rdata["risk_level"] == "HIGH"
    assert len(rdata["reasons"]) >= 1

    # Xem danh sách alert
    alerts_resp = client.get("/tickets/churn-risk-alerts", headers=headers)
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert any(a["customer_id"] == 1 for a in alerts)

    # Customer 360 của Customer 1 phải tự động phản ánh churn_risk = True
    c360_resp = client.get("/customers/1/360", headers=headers)
    assert c360_resp.status_code == 200
    assert c360_resp.json()["churn_risk"] is True
