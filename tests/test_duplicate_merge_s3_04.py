import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.contact_service import reset_fake_contacts, list_contacts
from app.services.customer_service import reset_fake_customers, FAKE_CUSTOMERS
from app.services.opportunity_service import reset_fake_opportunities
from app.services.activity_service import reset_fake_activities

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
    reset_fake_activities()
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_contacts()
    reset_fake_opportunities()
    reset_fake_activities()


def test_detect_duplicate_customers_by_similar_name_or_domain():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo một khách hàng mới có tên rất giống Customer 1 ("Công ty Cổ phần Công nghệ ABC")
    # và website gần giống
    resp_create = client.post(
        "/customers",
        json={
            "name": "Công nghệ ABC",
            "website": "https://abc-tech.vn/about",
            "phone": "0988888888",
            "email": "abc_dup@gmail.com",
        },
        headers=headers,
    )
    assert resp_create.status_code == 201
    new_cust = resp_create.json()
    new_id = new_cust["id"]

    # Kiểm tra phát hiện trùng
    resp = client.get(f"/customers/{new_id}/duplicates", headers=headers)
    assert resp.status_code == 200
    dups = resp.json()
    assert len(dups) >= 1
    # Customer 1 phải xuất hiện trong danh sách trùng lặp
    target_dup = next((d for d in dups if d["customer"]["id"] == 1), None)
    assert target_dup is not None
    assert target_dup["confidence_score"] > 0.5
    assert len(target_dup["match_reasons"]) >= 1


def test_merge_customers_as_manager_success():
    # Manager has role MANAGER
    token = get_auth_token("manager@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Merge customer 2 (secondary) into customer 1 (primary)
    merge_payload = {
        "primary_customer_id": 1,
        "secondary_customer_id": 2,
        "chosen_fields": {
            "address": "Địa chỉ sau khi gộp hai công ty",
        },
    }
    resp = client.post("/customers/merge", json=merge_payload, headers=headers)
    assert resp.status_code == 200
    merged = resp.json()
    assert merged["id"] == 1
    assert merged["address"] == "Địa chỉ sau khi gộp hai công ty"

    # Customer 2 should no longer exist
    resp_get2 = client.get("/customers/2", headers=headers)
    assert resp_get2.status_code == 404

    # Contacts from Customer 2 should now belong to Customer 1
    contacts_cust1 = list_contacts(customer_id=1)
    assert any(c["name"] == "Lê Kế Toán Trưởng" for c in contacts_cust1)


def test_merge_customers_as_user_forbidden():
    # User 1 has role USER -> Cannot merge
    token = get_auth_token("user1@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    merge_payload = {
        "primary_customer_id": 1,
        "secondary_customer_id": 2,
    }
    resp = client.post("/customers/merge", json=merge_payload, headers=headers)
    assert resp.status_code == 403
