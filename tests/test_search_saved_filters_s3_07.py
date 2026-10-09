import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.contact_service import reset_fake_contacts
from app.services.customer_service import reset_fake_customers

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
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_contacts()


def test_search_and_filter_multi_criteria():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Filter by industry
    resp = client.get("/customers?industry=Công nghệ thông tin", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert all("Công nghệ" in c.get("industry", "") for c in data["customers"])

    # 2. Filter by status and address
    resp2 = client.get("/customers?status=CUSTOMER&address=Hà Nội", headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["customers"]) >= 1
    assert data2["customers"][0]["id"] == 1


def test_saved_filters_lifecycle():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Tạo bộ lọc đã lưu
    create_payload = {
        "name": "Bộ lọc khách hàng bán lẻ",
        "filter_criteria": {
            "industry": "Bán lẻ & Tiêu dùng",
            "status": "PROSPECT",
        },
    }
    resp = client.post("/customers/saved-filters", json=create_payload, headers=headers)
    assert resp.status_code == 201
    created = resp.json()
    filter_id = created["id"]
    assert created["name"] == "Bộ lọc khách hàng bán lẻ"

    # 2. Lấy danh sách bộ lọc
    resp_list = client.get("/customers/saved-filters", headers=headers)
    assert resp_list.status_code == 200
    filters = resp_list.json()
    assert any(f["id"] == filter_id for f in filters)

    # 3. Xóa bộ lọc
    resp_del = client.delete(f"/customers/saved-filters/{filter_id}", headers=headers)
    assert resp_del.status_code == 204

    # Kiểm tra lại danh sách
    resp_list2 = client.get("/customers/saved-filters", headers=headers)
    assert not any(f["id"] == filter_id for f in resp_list2.json())
