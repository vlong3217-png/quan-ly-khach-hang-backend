import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.customer_service import reset_fake_customers

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_customers()
    yield
    reset_fake_users()
    reset_fake_customers()


def get_auth_headers(email: str = "admin@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# 1. AC S3-01: Khai báo đầy đủ thông tin khách hàng doanh nghiệp
def test_create_enterprise_customer_success():
    user_headers = get_auth_headers("user@gmail.com")  # User 3, Team A
    payload = {
        "name": "Công ty Cổ phần Công nghệ Tiên Phong",
        "tax_code": "0109998887",
        "industry": "Công nghệ thông tin",
        "company_size": "50 - 100 nhân sự",
        "website": "https://tienphong-tech.com",
        "address": "Duy Tân, Cầu Giấy, Hà Nội",
        "status": "PROSPECT",
    }
    res = client.post("/customers", json=payload, headers=user_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Công ty Cổ phần Công nghệ Tiên Phong"
    assert data["tax_code"] == "0109998887"
    assert data["industry"] == "Công nghệ thông tin"
    assert data["company_size"] == "50 - 100 nhân sự"
    assert data["status"] == "PROSPECT"
    assert data["owner_id"] == 3  # Tự động gán cho user tạo
    assert data["team_id"] == 1   # Team A


# 2. AC S3-01: Mã số thuế nếu có thì phải là duy nhất
def test_create_customer_duplicate_tax_code_fails():
    user_headers = get_auth_headers("user@gmail.com")
    payload = {
        "name": "Công ty Khác Trùng MST",
        "tax_code": "0101234567",  # Đã tồn tại ở Customer ID 1
        "industry": "Bán lẻ",
    }
    res = client.post("/customers", json=payload, headers=user_headers)
    assert res.status_code == 400
    assert "Mã số thuế" in res.json()["detail"]
    assert "đã tồn tại" in res.json()["detail"]


def test_create_customer_without_tax_code_succeeds():
    user_headers = get_auth_headers("user@gmail.com")
    payload = {
        "name": "Hộ kinh doanh cá thể",
        "tax_code": None,
        "status": "PROSPECT",
    }
    res = client.post("/customers", json=payload, headers=user_headers)
    assert res.status_code == 201
    assert res.json()["tax_code"] is None


# 3. AC S3-01: Khách hàng có 4 trạng thái chuẩn
def test_customer_statuses_supported():
    admin_headers = get_auth_headers("admin@gmail.com")
    statuses = ["PROSPECT", "IN_TRANSACTION", "CUSTOMER", "DISCONTINUED"]
    for idx, st in enumerate(statuses, start=10):
        payload = {
            "name": f"Công ty Test Trạng Thái {st}",
            "tax_code": f"01099900{idx}",
            "status": st,
        }
        res = client.post("/customers", json=payload, headers=admin_headers)
        assert res.status_code == 201
        assert res.json()["status"] == st


# 4. AC S3-01: Phân quyền phạm vi dữ liệu:
# - Nhân viên chỉ thấy khách hàng mình sở hữu;
# - Trưởng nhóm thấy toàn nhóm;
# - Admin thấy tất cả.
def test_customer_scope_visibility():
    # User 3 (user@gmail.com, Team A) chỉ sở hữu Customer ID 3
    user_headers = get_auth_headers("user@gmail.com")
    res_user = client.get("/customers", headers=user_headers)
    assert res_user.status_code == 200
    user_customers = res_user.json()["customers"]
    assert all(c["owner_id"] == 3 for c in user_customers)
    assert any(c["id"] == 3 for c in user_customers)
    assert not any(c["id"] in [1, 2, 4, 5] for c in user_customers)

    # Manager 2 (manager@gmail.com, Team A) thấy toàn bộ khách thuộc Team A (ID 1, 2, 3)
    mgr_headers = get_auth_headers("manager@gmail.com")
    res_mgr = client.get("/customers", headers=mgr_headers)
    assert res_mgr.status_code == 200
    mgr_customers = res_mgr.json()["customers"]
    assert all(c["team_id"] == 1 for c in mgr_customers)
    mgr_customer_ids = [c["id"] for c in mgr_customers]
    assert 2 in mgr_customer_ids
    assert 3 in mgr_customer_ids
    assert 4 not in mgr_customer_ids  # Team B

    # Admin 1 (admin@gmail.com) thấy tất cả
    admin_headers = get_auth_headers("admin@gmail.com")
    res_admin = client.get("/customers", headers=admin_headers)
    assert res_admin.status_code == 200
    assert res_admin.json()["total"] >= 5


# 5. AC S3-01: Cập nhật thông tin và kiểm tra trùng MST khi update
def test_update_customer_tax_code_validation():
    admin_headers = get_auth_headers("admin@gmail.com")
    # Sửa Customer 2 thành MST của Customer 1 -> Phải báo lỗi
    res_dup = client.put("/customers/2", json={"tax_code": "0101234567"}, headers=admin_headers)
    assert res_dup.status_code == 400
    assert "đã tồn tại" in res_dup.json()["detail"]

    # Sửa Customer 2 thành MST mới hợp lệ -> Thành công
    res_ok = client.put("/customers/2", json={"tax_code": "0309999999", "status": "CUSTOMER"}, headers=admin_headers)
    assert res_ok.status_code == 200
    assert res_ok.json()["tax_code"] == "0309999999"
    assert res_ok.json()["status"] == "CUSTOMER"
