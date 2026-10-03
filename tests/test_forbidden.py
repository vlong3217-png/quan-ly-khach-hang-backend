"""
Automated unit & integration tests for Story S1-07: Error responses & Forbidden (401 & 403 handling).
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi import FastAPI, Depends, status
from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.security import ALGORITHM, SECRET_KEY, create_access_token
from app.core.dependencies import (
    get_current_user,
    require_roles,
    require_permissions,
    PermissionChecker,
)
from app.services.customer_service import reset_fake_customers

client = TestClient(app)


def get_auth_headers(email: str = "admin@gmail.com") -> dict:
    role_map = {
        "admin@gmail.com": ("ADMIN", 1, None),
        "manager@gmail.com": ("MANAGER", 2, 1),
        "user1@gmail.com": ("USER", 3, 1),
        "user2@gmail.com": ("USER", 4, 2),
    }
    role, uid, team = role_map.get(email, ("USER", 3, 1))
    token = create_access_token({
        "sub": email,
        "id": uid,
        "role": role,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def run_around_tests():
    reset_fake_customers()
    yield
    reset_fake_customers()


# 1. 401 Unauthorized tests

def test_missing_token_returns_401():
    res = client.get("/customers")
    assert res.status_code == 401


def test_invalid_token_returns_401():
    headers = {"Authorization": "Bearer invalid.jwt.token"}
    res = client.get("/customers", headers=headers)
    assert res.status_code == 401


def test_expired_token_returns_401():
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    payload = {"sub": "admin@gmail.com", "id": 1, "role": "ADMIN", "exp": past}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    res = client.get("/customers", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_disabled_user_returns_401():
    token = create_access_token({"sub": "disabled@gmail.com", "id": 5, "role": "USER"})
    res = client.get("/customers", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


# 2. 403 Forbidden tests

def test_user_cannot_access_admin_users_list_returns_403():
    headers = get_auth_headers("user1@gmail.com")
    res = client.get("/users", headers=headers)
    assert res.status_code == 403
    assert "quyền" in res.json()["detail"].lower()


def test_manager_cannot_access_admin_users_list_returns_403():
    headers = get_auth_headers("manager@gmail.com")
    res = client.get("/users", headers=headers)
    assert res.status_code == 403
    assert "quyền" in res.json()["detail"].lower()


def test_user_cannot_delete_customer_returns_403():
    headers = get_auth_headers("user1@gmail.com")
    res = client.delete("/customers/1", headers=headers)
    assert res.status_code == 403


def test_manager_cannot_delete_customer_returns_403():
    headers = get_auth_headers("manager@gmail.com")
    res = client.delete("/customers/1", headers=headers)
    assert res.status_code == 403


def test_user_cannot_create_customer_returns_403():
    headers = get_auth_headers("user1@gmail.com")
    res = client.post("/customers", json={"name": "Khách Test", "phone": "0912345678"}, headers=headers)
    assert res.status_code == 403


def test_user_and_manager_cannot_access_admin_menu_config_returns_403():
    user_headers = get_auth_headers("user1@gmail.com")
    mgr_headers = get_auth_headers("manager@gmail.com")

    assert client.get("/auth/menu/admin-config", headers=user_headers).status_code == 403
    assert client.get("/auth/menu/admin-config", headers=mgr_headers).status_code == 403


def test_restricted_menu_item_check_returns_403():
    user_headers = get_auth_headers("user1@gmail.com")
    mgr_headers = get_auth_headers("manager@gmail.com")

    for menu_id in ["menu-customers-export", "menu-reports", "menu-settings"]:
        assert client.get(f"/auth/menu/check/{menu_id}", headers=user_headers).status_code == 403

    assert client.get("/auth/menu/check/menu-settings", headers=mgr_headers).status_code == 403


def test_scope_elevation_returns_403():
    user_headers = get_auth_headers("user1@gmail.com")
    mgr_headers = get_auth_headers("manager@gmail.com")

    assert client.get("/customers?scope=TEAM", headers=user_headers).status_code == 403
    assert client.get("/customers?scope=ALL", headers=user_headers).status_code == 403
    assert client.get("/customers?scope=ALL", headers=mgr_headers).status_code == 403


def test_cross_scope_record_access_returns_403():
    user_headers = get_auth_headers("user1@gmail.com")  # id=3, team=1
    mgr_headers = get_auth_headers("manager@gmail.com")   # id=2, team=1

    assert client.get("/customers/4", headers=user_headers).status_code == 403
    assert client.put("/customers/2", json={"name": "Sửa trái phép"}, headers=user_headers).status_code == 403
    assert client.put("/customers/4", json={"name": "Manager sửa khác team"}, headers=mgr_headers).status_code == 403


# 3. Authorized access tests (200 / 201)

def test_authorized_user_requests_work_normally():
    admin_headers = get_auth_headers("admin@gmail.com")
    mgr_headers = get_auth_headers("manager@gmail.com")
    user_headers = get_auth_headers("user1@gmail.com")

    res_users = client.get("/users", headers=admin_headers)
    assert res_users.status_code == 200
    assert isinstance(res_users.json(), list)

    assert client.delete("/customers/1", headers=admin_headers).status_code == 200

    res_create = client.post("/customers", json={"name": "Khách Manager", "phone": "0987654321"}, headers=mgr_headers)
    assert res_create.status_code == 201

    assert client.get("/customers/2", headers=mgr_headers).status_code == 200

    res_profile = client.get("/users/me", headers=user_headers)
    assert res_profile.status_code == 200
    assert "email" in res_profile.json()

    assert client.get("/customers/3", headers=user_headers).status_code == 200
    assert client.get("/auth/menu", headers=user_headers).status_code == 200
    assert client.get("/auth/menu/check/menu-dashboard", headers=user_headers).status_code == 200


# 4. Dependency tests

def test_require_permissions_and_checker():
    test_app = FastAPI()

    @test_app.get("/report-feature", dependencies=[Depends(require_permissions(["REPORT_VIEW"]))])
    def report_feature():
        return {"feature": "reports"}

    checker = PermissionChecker(roles=["ADMIN", "MANAGER"], permissions=["CUSTOMER_EXPORT"])
    @test_app.get("/export-feature", dependencies=[Depends(checker)])
    def export_feature():
        return {"feature": "export"}

    test_c = TestClient(test_app)

    user_headers = get_auth_headers("user1@gmail.com")
    mgr_headers = get_auth_headers("manager@gmail.com")
    admin_headers = get_auth_headers("admin@gmail.com")

    assert test_c.get("/report-feature", headers=user_headers).status_code == 403
    assert test_c.get("/report-feature", headers=mgr_headers).status_code == 200

    assert test_c.get("/export-feature", headers=user_headers).status_code == 403
    assert test_c.get("/export-feature", headers=admin_headers).status_code == 200
