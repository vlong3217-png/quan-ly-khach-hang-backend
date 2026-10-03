"""
Unit & Integration Tests for User Story S1-09: G??n Role + Nh??m/Team.

Requirements covered:
1. Admin g??n Role th??nh c??ng.
2. Admin g??n Team th??nh c??ng.
3. Xem Role & Team hi???n t???i c???a user.
4. Role/Team kh??ng t???n t???i -> HTTP 400 Bad Request.
5. User_id kh??ng t???n t???i -> HTTP 404 Not Found.
6. User kh??ng ph???i Admin (MANAGER / USER) -> HTTP 403 Forbidden.
7. Ch??a ????ng nh???p / JWT kh??ng h???p l??? -> HTTP 401 Unauthorized.
8. M???t kh???u / password_hash kh??ng b??? l??? trong response.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    """Reset fake users before each test."""
    reset_fake_users()
    yield
    reset_fake_users()


def get_auth_headers(email: str, password: str = "123456") -> dict:
    """Helper login function to get authorization headers."""
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed for {email}: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. AUTHENTICATION & PERMISSION CHECKS (401 & 403)
# ============================================================================

def test_unauthenticated_access_returns_401():
    """Ch??a ????ng nh???p -> HTTP 401."""
    assert client.get("/users/3/role").status_code == 401
    assert client.put("/users/3/role", json={"role": "MANAGER"}).status_code == 401
    assert client.get("/users/3/team").status_code == 401
    assert client.put("/users/3/team", json={"team_id": 2}).status_code == 401
    assert client.put("/users/3/assign", json={"role": "MANAGER", "team_id": 2}).status_code == 401


def test_invalid_token_returns_401():
    """JWT kh??ng h???p l??? -> HTTP 401."""
    headers = {"Authorization": "Bearer invalid_token_123"}
    res = client.get("/users/3/role", headers=headers)
    assert res.status_code == 401
    assert "Token kh??ng h???p l???" in res.json()["detail"]


def test_non_admin_user_returns_403():
    """User ???? ????ng nh???p nh??ng kh??ng ph???i Admin (MANAGER / USER) -> HTTP 403."""
    user_headers = get_auth_headers("user1@gmail.com")
    mgr_headers = get_auth_headers("manager@gmail.com")

    # USER role
    res_usr_role = client.get("/users/3/role", headers=user_headers)
    assert res_usr_role.status_code == 403
    assert "Y??u c???u role: ADMIN" in res_usr_role.json()["detail"]

    res_usr_put = client.put("/users/3/role", json={"role": "ADMIN"}, headers=user_headers)
    assert res_usr_put.status_code == 403

    # MANAGER role
    res_mgr_team = client.get("/users/3/team", headers=mgr_headers)
    assert res_mgr_team.status_code == 403

    res_mgr_assign = client.put("/users/3/assign", json={"role": "ADMIN", "team_id": 1}, headers=mgr_headers)
    assert res_mgr_assign.status_code == 403


# ============================================================================
# 2. VIEWING ROLE & TEAM (ADMIN ONLY)
# ============================================================================

def test_admin_get_user_role_success():
    """Admin xem Role hi???n t???i c???a user th??nh c??ng."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.get("/users/3/role", headers=admin_headers)

    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == 3
    assert data["email"] == "user1@gmail.com"
    assert data["role"] == "USER"
    assert "password" not in data
    assert "hashed_password" not in data


def test_admin_get_user_team_success():
    """Admin xem Team hi???n t???i c???a user th??nh c??ng."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.get("/users/3/team", headers=admin_headers)

    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == 3
    assert data["team_id"] == 1
    assert data["team_name"] == "Team A"
    assert "password" not in data
    assert "hashed_password" not in data


# ============================================================================
# 3. ASSIGNING ROLE & TEAM (ADMIN ONLY)
# ============================================================================

def test_admin_assign_role_success():
    """Admin g??n Role th??nh c??ng."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.put(
        "/users/3/role",
        json={"role": "MANAGER"},
        headers=admin_headers,
    )

    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == 3
    assert data["role"] == "MANAGER"

    # Ki???m tra l???i profile user
    user1_headers = get_auth_headers("user1@gmail.com")
    me_res = client.get("/users/me", headers=user1_headers)
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "MANAGER"


def test_admin_assign_team_success():
    """Admin g??n Team th??nh c??ng."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.put(
        "/users/3/team",
        json={"team_id": 2},
        headers=admin_headers,
    )

    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == 3
    assert data["team_id"] == 2
    assert data["team_name"] == "Team B"


def test_admin_assign_role_and_team_combined():
    """Admin g??n c??? Role v?? Team b???ng API /assign th??nh c??ng."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.put(
        "/users/4/assign",
        json={"role": "MANAGER", "team_id": 1},
        headers=admin_headers,
    )

    assert res.status_code == 200
    data = res.json()
    assert data["id"] == 4
    assert data["role"] == "MANAGER"
    assert data["team_id"] == 1
    assert "password" not in data
    assert "hashed_password" not in data


# ============================================================================
# 4. VALIDATION & ERROR HANDLING (400 & 404)
# ============================================================================

def test_assign_invalid_role_returns_400():
    """G??n Role kh??ng t???n t???i -> HTTP 400."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.put(
        "/users/3/role",
        json={"role": "SUPER_SUPER_ADMIN"},
        headers=admin_headers,
    )

    assert res.status_code == 400
    assert "Role 'SUPER_SUPER_ADMIN' kh??ng h???p l???" in res.json()["detail"]


def test_assign_invalid_team_returns_400():
    """G??n Team kh??ng t???n t???i -> HTTP 400."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.put(
        "/users/3/team",
        json={"team_id": 99999},
        headers=admin_headers,
    )

    assert res.status_code == 400
    assert "Team ID 99999 kh??ng t???n t???i" in res.json()["detail"]


def test_non_existent_user_id_returns_404():
    """User ID kh??ng t???n t???i -> HTTP 404."""
    admin_headers = get_auth_headers("admin@gmail.com")

    assert client.get("/users/9999/role", headers=admin_headers).status_code == 404
    assert client.put("/users/9999/role", json={"role": "MANAGER"}, headers=admin_headers).status_code == 404
    assert client.get("/users/9999/team", headers=admin_headers).status_code == 404
    assert client.put("/users/9999/team", json={"team_id": 1}, headers=admin_headers).status_code == 404
