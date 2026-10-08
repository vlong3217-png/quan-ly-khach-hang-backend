import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.contact_service import reset_fake_contacts
from app.services.customer_service import reset_fake_customers
from app.services.opportunity_service import reset_fake_opportunities
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
    reset_fake_opportunities()
    reset_fake_tickets()
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_contacts()
    reset_fake_opportunities()
    reset_fake_tickets()


def test_get_periodic_care_customers_list():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Lấy danh sách khách cần chăm sóc sau 30 ngày không tương tác
    resp = client.get("/customers/periodic-care?days=30", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    # Kiểm tra tính chất sắp xếp theo tổng giá trị hợp đồng giảm dần
    values = [item["total_contract_value"] for item in data]
    assert values == sorted(values, reverse=True)


def test_mark_customer_care_interaction_updates_timestamp():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Đánh dấu đã liên hệ chăm sóc Customer 1
    mark_payload = {
        "interaction_type": "CALL",
        "note": "Đã gọi điện hỏi thăm tình hình sử dụng dịch vụ trong quý",
    }
    resp = client.post("/customers/1/mark-care", json=mark_payload, headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["customer_id"] == 1
    assert "thành công" in result["message"]

    # Sau khi vừa liên hệ xong, Customer 1 sẽ có days_since_last_interaction = 0
    # nên không còn nằm trong danh sách cần chăm sóc (days >= 30) nữa
    resp_list = client.get("/customers/periodic-care?days=30", headers=headers)
    assert resp_list.status_code == 200
    care_customers = resp_list.json()
    assert not any(c["customer_id"] == 1 for c in care_customers)
