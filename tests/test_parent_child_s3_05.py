import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.contact_service import reset_fake_contacts
from app.services.customer_service import reset_fake_customers
from app.services import opportunity_service
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
    opportunity_service.reset_fake_opportunities()
    reset_fake_activities()
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_contacts()
    opportunity_service.reset_fake_opportunities()
    reset_fake_activities()


def test_parent_child_company_creation_and_enrichment():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo công ty con của Customer 1 ("Công ty Cổ phần Công nghệ ABC")
    sub_payload = {
        "name": "Chi nhánh TP.HCM - Công ty ABC",
        "tax_code": "0101234567-001",
        "parent_company_id": 1,
        "industry": "Công nghệ thông tin",
        "status": "CUSTOMER",
    }
    resp = client.post("/customers", json=sub_payload, headers=headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["parent_company_id"] == 1
    assert created["parent_company_name"] == "Công ty Cổ phần Công nghệ ABC"


def test_get_group_company_tree_and_total_value():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Tạo chi nhánh con của Customer 1
    sub_payload = {
        "name": "Chi nhánh Đà Nẵng - Công ty ABC",
        "tax_code": "0101234567-002",
        "parent_company_id": 1,
        "industry": "Công nghệ thông tin",
        "status": "CUSTOMER",
    }
    resp_sub = client.post("/customers", json=sub_payload, headers=headers)
    assert resp_sub.status_code == 201
    sub_id = resp_sub.json()["id"]

    # 2. Thêm một hợp đồng đã ký cho chi nhánh này
    opportunity_service.FAKE_OPPORTUNITIES.append({
        "id": 101,
        "title": "Hợp đồng chi nhánh Đà Nẵng",
        "value": 25000000.0,
        "stage": "CLOSED_WON",
        "customer_id": sub_id,
        "owner_id": 1,
        "team_id": 1,
    })

    # 3. Lấy cây tập đoàn của công ty mẹ (Customer 1)
    resp_tree = client.get("/customers/1/group-tree", headers=headers)

    assert resp_tree.status_code == 200
    tree_data = resp_tree.json()

    assert tree_data["parent"]["id"] == 1
    assert tree_data["total_members"] >= 2
    assert any(s["id"] == sub_id for s in tree_data["subsidiaries"])
    # Doanh thu tập đoàn phải bao gồm cả của chi nhánh (25,000,000)
    assert tree_data["total_group_won_value"] >= 25000000.0
