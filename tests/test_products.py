import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.product_service import reset_fake_products

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_products()
    yield
    reset_fake_users()
    reset_fake_products()


def get_auth_headers(email: str = "admin@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# 1. AC S2-05: Khai báo mã, tên, loại sản phẩm (1 lần / thuê bao), đơn vị tính, giá niêm yết, giá sàn, giá vốn
def test_create_product_success_admin():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "code": "PROD-ERP-01",
        "name": "Hệ thống ERP Doanh nghiệp",
        "product_type": "ONE_TIME",
        "unit": "Hệ thống",
        "list_price": 50000000.0,
        "floor_price": 40000000.0,
        "cost_price": 25000000.0,
    }
    res = client.post("/products", json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "PROD-ERP-01"
    assert data["name"] == "Hệ thống ERP Doanh nghiệp"
    assert data["product_type"] == "ONE_TIME"
    assert data["unit"] == "Hệ thống"
    assert data["list_price"] == 50000000.0
    assert data["floor_price"] == 40000000.0
    assert data["cost_price"] == 25000000.0
    assert data["status"] == "ACTIVE"


def test_create_product_forbidden_for_normal_user():
    user_headers = get_auth_headers("user@gmail.com")
    payload = {
        "code": "PROD-TEST",
        "name": "Sản phẩm test",
        "product_type": "ONE_TIME",
        "unit": "Cái",
        "list_price": 100000.0,
        "floor_price": 80000.0,
    }
    res = client.post("/products", json=payload, headers=user_headers)
    assert res.status_code == 403


def test_create_product_duplicate_code_fails():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "code": "PROD-CRM-BASE",  # Đã tồn tại trong danh mục ban đầu
        "name": "Gói trùng mã",
        "product_type": "ONE_TIME",
        "unit": "Gói",
        "list_price": 20000000.0,
        "floor_price": 15000000.0,
    }
    res = client.post("/products", json=payload, headers=admin_headers)
    assert res.status_code == 400
    assert "đã tồn tại" in res.json()["detail"]


def test_create_product_floor_price_greater_than_list_price_fails():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "code": "PROD-INVALID-PRICE",
        "name": "Giá sàn cao hơn niêm yết",
        "product_type": "ONE_TIME",
        "unit": "Bộ",
        "list_price": 1000000.0,
        "floor_price": 1500000.0,  # Invalid
    }
    res = client.post("/products", json=payload, headers=admin_headers)
    assert res.status_code == 400
    assert "Giá sàn không được lớn hơn giá niêm yết" in res.json()["detail"]


# 2. AC S2-05: Bảo mật giá vốn (cost_price)
def test_cost_price_masked_for_normal_user_on_list_and_detail():
    user_headers = get_auth_headers("user@gmail.com")
    
    # Check list
    res = client.get("/products", headers=user_headers)
    assert res.status_code == 200
    products = res.json()["products"]
    assert len(products) > 0
    for p in products:
        assert p["cost_price"] is None

    # Check detail
    res_detail = client.get("/products/1", headers=user_headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["cost_price"] is None


def test_cost_price_visible_for_manager_and_admin():
    manager_headers = get_auth_headers("manager@gmail.com")
    res_m = client.get("/products/1", headers=manager_headers)
    assert res_m.status_code == 200
    assert res_m.json()["cost_price"] == 8000000.0

    admin_headers = get_auth_headers("admin@gmail.com")
    res_a = client.get("/products/1", headers=admin_headers)
    assert res_a.status_code == 200
    assert res_a.json()["cost_price"] == 8000000.0


# 3. AC S2-05: Cập nhật sản phẩm
def test_update_product_success_manager():
    manager_headers = get_auth_headers("manager@gmail.com")
    update_data = {
        "name": "Phần mềm Quản lý Khách hàng - Gói Nâng Cấp Pro",
        "list_price": 25000000.0,
        "floor_price": 18000000.0,
        "cost_price": 9000000.0,
    }
    res = client.put("/products/1", json=update_data, headers=manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Phần mềm Quản lý Khách hàng - Gói Nâng Cấp Pro"
    assert data["list_price"] == 25000000.0
    assert data["floor_price"] == 18000000.0
    assert data["cost_price"] == 9000000.0


# 4. AC S2-05: Xóa sản phẩm đã xuất hiện trong báo giá -> tự động chuyển sang NGỪNG KINH DOANH (DISCONTINUED)
def test_delete_quoted_product_turns_into_discontinued():
    admin_headers = get_auth_headers("admin@gmail.com")
    # Sản phẩm ID 1 đã nằm trong QUOTED_PRODUCT_IDS
    res = client.delete("/products/1", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "DISCONTINUED"
    assert "không thể xoá" in data["message"]
    assert data["product"]["status"] == "DISCONTINUED"

    # Kiểm tra lại qua GET detail
    res_detail = client.get("/products/1", headers=admin_headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["status"] == "DISCONTINUED"


def test_delete_unquoted_product_completely_removes():
    admin_headers = get_auth_headers("admin@gmail.com")
    # Sản phẩm ID 3 chưa xuất hiện trong báo giá -> Xoá hẳn
    res = client.delete("/products/3", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "DELETED"

    res_detail = client.get("/products/3", headers=admin_headers)
    assert res_detail.status_code == 404


# 5. AC S2-05: Kiểm tra duyệt chiết khấu dựa trên giá sàn (floor_price)
def test_check_discount_requires_approval_when_below_floor_price():
    user_headers = get_auth_headers("user@gmail.com")
    # Sản phẩm ID 1 có floor_price = 15,000,000
    payload = {
        "product_id": 1,
        "proposed_price": 12000000.0,  # < 15,000,000 -> Cần duyệt
    }
    res = client.post("/products/check-discount", json=payload, headers=user_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["needs_approval"] is True
    assert "thấp hơn giá sàn" in data["reason"]
    assert "Bắt buộc phải có phê duyệt" in data["reason"]


def test_check_discount_no_approval_when_equal_or_above_floor_price():
    user_headers = get_auth_headers("user@gmail.com")
    # Sản phẩm ID 1 có floor_price = 15,000,000
    payload = {
        "product_id": 1,
        "proposed_price": 16000000.0,  # >= 15,000,000 -> Không cần duyệt
    }
    res = client.post("/products/check-discount", json=payload, headers=user_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["needs_approval"] is False
    assert "Không cần duyệt chiết khấu" in data["reason"]
