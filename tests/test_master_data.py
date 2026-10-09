import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.master_data_service import reset_fake_master_data

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_master_data()
    yield
    reset_fake_users()
    reset_fake_master_data()


def get_auth_headers(email: str = "admin@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# 1. AC S2-07: Xem danh mục dùng chung (Ngành nghề, quy mô, nguồn lead, loại hoạt động)
def test_get_master_data_by_category():
    admin_headers = get_auth_headers("admin@gmail.com")
    
    res = client.get("/master-data?category=INDUSTRY", headers=admin_headers)
    assert res.status_code == 200
    industries = res.json()
    assert len(industries) == 3
    assert all(i["category"] == "INDUSTRY" for i in industries)
    # Kiểm tra thứ tự sắp xếp
    sort_orders = [i["sort_order"] for i in industries]
    assert sort_orders == sorted(sort_orders)


# 2. AC S2-07: Thêm mới danh mục
def test_create_master_data_success():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "category": "INDUSTRY",
        "code": "HEALTHCARE",
        "name": "Y tế & Dược phẩm",
        "sort_order": 4,
        "is_active": True,
        "description": "Bệnh viện, phòng khám, nhà thuốc",
    }
    res = client.post("/master-data", json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "HEALTHCARE"
    assert data["name"] == "Y tế & Dược phẩm"
    assert data["category"] == "INDUSTRY"


def test_create_master_data_duplicate_code_fails():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "category": "INDUSTRY",
        "code": "TECH",  # Đã tồn tại trong INDUSTRY
        "name": "Trùng mã ngành",
        "sort_order": 10,
    }
    res = client.post("/master-data", json=payload, headers=admin_headers)
    assert res.status_code == 400
    assert "đã tồn tại" in res.json()["detail"]


# 3. AC S2-07: Sắp xếp thứ tự hiển thị
def test_reorder_master_data():
    admin_headers = get_auth_headers("admin@gmail.com")
    reorder_payload = {
        "items": [
            {"id": 1, "sort_order": 10},
            {"id": 2, "sort_order": 1},
            {"id": 3, "sort_order": 2},
        ]
    }
    res = client.post("/master-data/reorder?category=INDUSTRY", json=reorder_payload, headers=admin_headers)
    assert res.status_code == 200
    updated_list = res.json()
    # Sau khi reorder, ID 2 phải lên đầu (sort_order = 1)
    assert updated_list[0]["id"] == 2
    assert updated_list[0]["sort_order"] == 1


# 4. AC S2-07: Ràng buộc xóa: không cho xóa nếu có bản ghi tham chiếu, chỉ cho ẩn (Inactive)
def test_delete_referenced_master_data_fails():
    admin_headers = get_auth_headers("admin@gmail.com")
    # ID 1 (TECH) đang có tham chiếu
    res = client.delete("/master-data/1", headers=admin_headers)
    assert res.status_code == 400
    assert "đang có các bản ghi khách hàng/cơ hội tham chiếu" in res.json()["detail"]


def test_deactivate_referenced_master_data_succeeds():
    admin_headers = get_auth_headers("admin@gmail.com")
    # Cập nhật is_active = False thay vì xóa
    update_res = client.put("/master-data/1", json={"is_active": False}, headers=admin_headers)
    assert update_res.status_code == 200
    assert update_res.json()["is_active"] is False

    # Lấy danh sách chỉ kích hoạt -> ID 1 không xuất hiện
    list_res = client.get("/master-data?category=INDUSTRY&active_only=true", headers=admin_headers)
    assert list_res.status_code == 200
    active_ids = [m["id"] for m in list_res.json()]
    assert 1 not in active_ids


def test_delete_unreferenced_master_data_succeeds():
    admin_headers = get_auth_headers("admin@gmail.com")
    # ID 2 (FINANCE) không nằm trong REFERENCED_MASTER_DATA_IDS
    res = client.delete("/master-data/2", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["success"] is True
