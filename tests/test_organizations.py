import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.organization_service import reset_fake_orgs

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_orgs()
    yield
    reset_fake_users()
    reset_fake_orgs()


def get_auth_headers(email: str = "admin@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# 1. AC S2-06: Cây tổ chức nhóm đa cấp, trưởng nhóm, khu vực địa lý
def test_get_organizations_flat_and_tree():
    admin_headers = get_auth_headers("admin@gmail.com")
    
    # Flat list
    res_flat = client.get("/organizations", headers=admin_headers)
    assert res_flat.status_code == 200
    flat_data = res_flat.json()
    assert len(flat_data) >= 4
    assert any(u["code"] == "CORP-HQ" for u in flat_data)

    # Tree list
    res_tree = client.get("/organizations?tree=true", headers=admin_headers)
    assert res_tree.status_code == 200
    tree_data = res_tree.json()
    assert len(tree_data) == 1  # Root CORP-HQ
    root = tree_data[0]
    assert root["code"] == "CORP-HQ"
    assert len(root["children"]) == 2  # SALES-NORTH and SALES-SOUTH
    north_child = next(c for c in root["children"] if c["code"] == "SALES-NORTH")
    assert len(north_child["children"]) == 1  # TEAM-ENTERPRISE-HN


# 2. AC S2-06: Tạo mới đơn vị phòng ban
def test_create_organization_unit():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "code": "SALES-CENTRAL",
        "name": "Phòng Kinh Doanh Miền Trung",
        "parent_id": 1,
        "manager_id": 2,
        "territories": ["Đà Nẵng", "Huế", "Quảng Nam"],
        "description": "Phụ trách khu vực miền Trung",
    }
    res = client.post("/organizations", json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "SALES-CENTRAL"
    assert data["name"] == "Phòng Kinh Doanh Miền Trung"
    assert data["manager_name"] is not None
    assert "Đà Nẵng" in data["territories"]


def test_create_organization_forbidden_for_user():
    user_headers = get_auth_headers("user@gmail.com")
    payload = {
        "code": "TEST-ORG",
        "name": "Thử nghiệm",
        "parent_id": 1,
    }
    res = client.post("/organizations", json=payload, headers=user_headers)
    assert res.status_code == 403


# 3. AC S2-06: Luân chuyển cấp bậc phòng ban (Move parent) & chống vòng lặp lồng nhau
def test_move_organization_unit_prevent_cycle():
    admin_headers = get_auth_headers("admin@gmail.com")
    # Chuyển cấp trên của CORP-HQ (ID 1) thành SALES-NORTH (ID 2 - vốn là con của ID 1) -> phải báo lỗi vòng lặp
    move_payload = {"target_parent_id": 2}
    res = client.post("/organizations/1/move", json=move_payload, headers=admin_headers)
    assert res.status_code == 400
    assert "vòng lặp" in res.json()["detail"] or "con" in res.json()["detail"]


def test_move_organization_unit_success():
    admin_headers = get_auth_headers("admin@gmail.com")
    # Chuyển TEAM-ENTERPRISE-HN (ID 4 - đang là con của ID 2) thành con trực tiếp của CORP-HQ (ID 1)
    move_payload = {"target_parent_id": 1}
    res = client.post("/organizations/4/move", json=move_payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["parent_id"] == 1


# 4. AC S2-06: Ràng buộc xoá đơn vị tổ chức
def test_delete_unit_fails_if_has_children():
    admin_headers = get_auth_headers("admin@gmail.com")
    # CORP-HQ (ID 1) có con -> Không được xoá
    res = client.delete("/organizations/1", headers=admin_headers)
    assert res.status_code == 400
    assert "phòng ban con" in res.json()["detail"]


def test_delete_leaf_unit_without_members_succeeds():
    admin_headers = get_auth_headers("admin@gmail.com")
    # Tạo 1 phòng ban trống không có con và không có nhân viên
    payload = {
        "code": "TEMP-LEAF",
        "name": "Nhóm tạm",
        "parent_id": 1,
        "territories": [],
    }
    create_res = client.post("/organizations", json=payload, headers=admin_headers)
    new_id = create_res.json()["id"]

    del_res = client.delete(f"/organizations/{new_id}", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True
