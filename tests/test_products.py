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


# 6. AC S2-05: Lưu sản phẩm vào MySQL/SQLite bằng SQLAlchemy
def test_product_stored_in_sqlalchemy_database():
    from app.core.database import SessionLocal
    from app.models.product import Product as ProductModel

    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "code": "PROD-DB-SQLA",
        "name": "Hệ thống Quản lý Dự án Doanh nghiệp",
        "product_type": "ONE_TIME",
        "unit": "Hệ thống",
        "list_price": 45000000.0,
        "floor_price": 38000000.0,
        "cost_price": 20000000.0,
    }
    res = client.post("/products", json=payload, headers=admin_headers)
    assert res.status_code == 201
    prod_id = res.json()["id"]

    db = SessionLocal()
    try:
        db_prod = db.query(ProductModel).filter(ProductModel.id == prod_id).first()
        assert db_prod is not None
        assert db_prod.code == "PROD-DB-SQLA"
        assert db_prod.name == "Hệ thống Quản lý Dự án Doanh nghiệp"
        assert db_prod.list_price == 45000000.0
        assert db_prod.floor_price == 38000000.0
        assert db_prod.cost_price == 20000000.0
        assert db_prod.status == "ACTIVE"
    finally:
        db.close()


# 7. AC S2-05: Kiểm tra giá hợp lệ trước khi cập nhật và tránh thay đổi dữ liệu khi trả lỗi
def test_update_product_invalid_price_does_not_mutate_data():
    manager_headers = get_auth_headers("manager@gmail.com")
    res_before = client.get("/products/1", headers=manager_headers)
    assert res_before.status_code == 200
    orig_name = res_before.json()["name"]
    orig_list_price = res_before.json()["list_price"]
    orig_floor_price = res_before.json()["floor_price"]

    # Thử update với tên mới và floor_price > list_price (hợp lệ tên, nhưng sai giá)
    invalid_update = {
        "name": "Tên Bị Đổi Nếu Có Lỗi",
        "floor_price": 999000000.0,  # Lớn hơn list_price
    }
    res_err = client.put("/products/1", json=invalid_update, headers=manager_headers)
    assert res_err.status_code == 400
    assert "Giá sàn không được lớn hơn giá niêm yết" in res_err.json()["detail"]

    # Xác minh dữ liệu không bị sửa đổi một phần
    res_after = client.get("/products/1", headers=manager_headers)
    assert res_after.status_code == 200
    assert res_after.json()["name"] == orig_name
    assert res_after.json()["list_price"] == orig_list_price
    assert res_after.json()["floor_price"] == orig_floor_price


# 8. AC S2-05: Thay QUOTED_PRODUCT_IDS bằng kiểm tra quan hệ quote_items thực tế
def test_delete_product_dynamic_quote_relationship():
    from app.services.quote_service import reset_fake_quotes

    reset_fake_quotes()
    admin_headers = get_auth_headers("admin@gmail.com")
    manager_headers = get_auth_headers("manager@gmail.com")

    # Sản phẩm ID 3 ban đầu chưa có trong báo giá
    # Tạo một báo giá mới liên kết với sản phẩm ID 3
    quote_payload = {
        "title": "Báo giá Dịch vụ Bảo trì Đột xuất",
        "amount": 12000000.0,
        "unit_price": 12000000.0,
        "product_id": 3,
    }
    res_q = client.post("/quotes", json=quote_payload, headers=manager_headers)
    assert res_q.status_code == 201

    # Thử xóa sản phẩm ID 3 -> Hệ thống phát hiện báo giá thực tế và chuyển sang DISCONTINUED thay vì DELETED
    res_del = client.delete("/products/3", headers=admin_headers)
    assert res_del.status_code == 200
    data = res_del.json()
    assert data["action"] == "DISCONTINUED"
    assert "không thể xoá" in data["message"]
    assert data["product"]["status"] == "DISCONTINUED"

    # Kiểm tra lại sản phẩm 3 vẫn tồn tại với trạng thái DISCONTINUED
    res_detail = client.get("/products/3", headers=admin_headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["status"] == "DISCONTINUED"


# 9. AC S2-05: Tích hợp kiểm tra giá sàn vào quy trình tạo và cập nhật báo giá
def test_quote_integration_floor_price_workflow():
    from app.services.quote_service import reset_fake_quotes

    reset_fake_quotes()
    manager_headers = get_auth_headers("manager@gmail.com")

    # Tạo báo giá với unit_price < floor_price (Product 1 có floor_price = 15,000,000)
    quote_below_floor = {
        "title": "Báo giá giảm sâu dưới sàn",
        "amount": 11000000.0,
        "unit_price": 11000000.0,
        "product_id": 1,
    }
    res_created = client.post("/quotes", json=quote_below_floor, headers=manager_headers)
    assert res_created.status_code == 201
    q_data = res_created.json()
    assert q_data["requires_discount_approval"] is True
    assert q_data["discount_approval_status"] == "PENDING_APPROVAL"

    # Tạo báo giá với unit_price >= floor_price
    quote_above_floor = {
        "title": "Báo giá đạt sàn",
        "amount": 16000000.0,
        "unit_price": 16000000.0,
        "product_id": 1,
    }
    res_approved = client.post("/quotes", json=quote_above_floor, headers=manager_headers)
    assert res_approved.status_code == 201
    assert res_approved.json()["requires_discount_approval"] is False
    assert res_approved.json()["discount_approval_status"] == "APPROVED"

    # Cập nhật báo giá trên hạ giá < floor_price -> Yêu cầu duyệt lại
    qid = res_approved.json()["id"]
    res_up = client.put(f"/quotes/{qid}", json={"unit_price": 13000000.0, "amount": 13000000.0}, headers=manager_headers)
    assert res_up.status_code == 200
    assert res_up.json()["requires_discount_approval"] is True
    assert res_up.json()["discount_approval_status"] == "PENDING_APPROVAL"


# 10. AC S2-05: Sử dụng Database làm nguồn dữ liệu duy nhất
def test_product_database_single_source_of_truth_survives_ram_clear():
    from app.services.product_service import fake_products_db

    admin_headers = get_auth_headers("admin@gmail.com")
    new_product_payload = {
        "code": "PROD-DB-ONLY-01",
        "name": "Sản phẩm DB Độc Lập",
        "product_type": "ONE_TIME",
        "unit": "Gói",
        "list_price": 18000000.0,
        "floor_price": 14000000.0,
        "cost_price": 7000000.0,
    }
    create_res = client.post("/products", json=new_product_payload, headers=admin_headers)
    assert create_res.status_code == 201
    prod_id = create_res.json()["id"]

    # Xóa sạch bộ nhớ RAM fake_products_db để chứng minh dữ liệu đọc 100% từ CSDL
    fake_products_db.clear()

    # Truy vấn GET detail và GET list
    detail_res = client.get(f"/products/{prod_id}", headers=admin_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["code"] == "PROD-DB-ONLY-01"
    assert detail_res.json()["name"] == "Sản phẩm DB Độc Lập"

    list_res = client.get("/products?search=PROD-DB-ONLY-01", headers=admin_headers)
    assert list_res.status_code == 200
    assert any(p["code"] == "PROD-DB-ONLY-01" for p in list_res.json()["products"])


# 11. AC S2-05: Không bỏ qua lỗi ghi database khi CRUD (Xử lý lỗi nghiêm ngặt)
def test_create_product_db_error_returns_500(monkeypatch):
    from sqlalchemy.orm import Session
    admin_headers = get_auth_headers("admin@gmail.com")

    def mock_commit(self):
        raise Exception("Database disk full error")

    monkeypatch.setattr(Session, "commit", mock_commit)

    payload = {
        "code": "PROD-ERR-500",
        "name": "Sản phẩm lỗi DB",
        "product_type": "ONE_TIME",
        "unit": "Bộ",
        "list_price": 10000000.0,
        "floor_price": 8000000.0,
    }
    res = client.post("/products", json=payload, headers=admin_headers)
    assert res.status_code == 500
    assert "Lỗi ghi CSDL" in res.json()["detail"]


def test_update_product_db_error_returns_500(monkeypatch):
    from sqlalchemy.orm import Session
    manager_headers = get_auth_headers("manager@gmail.com")

    def mock_commit(self):
        raise Exception("Database transaction timeout")

    monkeypatch.setattr(Session, "commit", mock_commit)

    res = client.put("/products/1", json={"name": "Tên mới lỗi"}, headers=manager_headers)
    assert res.status_code == 500
    assert "Lỗi ghi CSDL" in res.json()["detail"]


def test_delete_product_db_error_returns_500(monkeypatch):
    from sqlalchemy.orm import Session
    admin_headers = get_auth_headers("admin@gmail.com")

    def mock_commit(self):
        raise Exception("Database foreign key lock")

    monkeypatch.setattr(Session, "commit", mock_commit)

    res = client.delete("/products/3", headers=admin_headers)
    assert res.status_code == 500
    assert "Lỗi ghi CSDL" in res.json()["detail"]


# 12. AC S2-05: Kiểm tra quyền giá vốn đúng vai trò Giám đốc kinh doanh (MANAGER)
def test_cost_price_permissions_business_director():
    manager_headers = get_auth_headers("manager@gmail.com")
    user_headers = get_auth_headers("user@gmail.com")

    # Giám đốc kinh doanh (MANAGER) xem được giá vốn
    res_m = client.get("/products/1", headers=manager_headers)
    assert res_m.status_code == 200
    assert res_m.json()["cost_price"] is not None

    # Giám đốc kinh doanh (MANAGER) cập nhật được giá vốn
    res_update = client.put("/products/1", json={"cost_price": 8500000.0}, headers=manager_headers)
    assert res_update.status_code == 200
    assert res_update.json()["cost_price"] == 8500000.0

    # Nhân viên thông thường không xem được giá vốn (bị ẩn thành None)
    res_u = client.get("/products/1", headers=user_headers)
    assert res_u.status_code == 200
    assert res_u.json()["cost_price"] is None

    # Nhân viên thông thường không có quyền cập nhật sản phẩm / giá vốn (403)
    res_u_update = client.put("/products/1", json={"cost_price": 9999999.0}, headers=user_headers)
    assert res_u_update.status_code == 403


# 13. AC S2-05: Bảo đảm không xóa sản phẩm đã nằm trong báo giá thật (Lưu giữ trong CSDL)
def test_quoted_product_retained_in_database_as_discontinued():
    from app.core.database import SessionLocal
    from app.models.product import Product as ProductModel

    admin_headers = get_auth_headers("admin@gmail.com")

    # Sản phẩm ID 1 đã nằm trong báo giá số 1
    del_res = client.delete("/products/1", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["action"] == "DISCONTINUED"

    # Kiểm tra trực tiếp trong CSDL: bản ghi vẫn tồn tại với status DISCONTINUED
    db = SessionLocal()
    try:
        db_p = db.query(ProductModel).filter(ProductModel.id == 1).first()
        assert db_p is not None, "Sản phẩm đã nằm trong báo giá không được bị xóa khỏi CSDL"
        assert db_p.status == "DISCONTINUED"
        assert db_p.code == "PROD-CRM-BASE"
    finally:
        db.close()

