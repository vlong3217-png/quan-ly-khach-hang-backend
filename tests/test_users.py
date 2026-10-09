import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import hash_password, create_access_token
from app.services.auth_service import reset_fake_users_db, fake_users_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users_db()
    yield
    reset_fake_users_db()


def get_token(email: str = "admin@gmail.com", user_id: int = 1, role: str = "ADMIN") -> str:
    return create_access_token({
        "sub": email,
        "id": user_id,
        "role": role,
    })


# ????????????????????????????????? 401 & 403 Authentication / Authorization Tests ?????????????????????????????????

def test_list_users_no_token_returns_401():
    """Request without token must return 401 Unauthorized."""
    response = client.get("/users")
    assert response.status_code == 401


def test_list_users_invalid_token_returns_401():
    """Request with invalid/malformed token must return 401 Unauthorized."""
    response = client.get("/users", headers={"Authorization": "Bearer invalid_token_xyz"})
    assert response.status_code == 401


def test_list_users_non_admin_returns_403():
    """Normal user (role USER) attempting to access /users must return 403 Forbidden."""
    user_token = get_token(email="user@gmail.com", user_id=3, role="USER")
    response = client.get("/users", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 403
    assert "Admin" in response.json()["detail"]


def test_list_users_manager_returns_403():
    """Manager (role MANAGER) attempting to access /users must return 403 Forbidden."""
    manager_token = get_token(email="manager@gmail.com", user_id=2, role="MANAGER")
    response = client.get("/users", headers={"Authorization": f"Bearer {manager_token}"})
    assert response.status_code == 403
    assert "Admin" in response.json()["detail"]


def test_get_user_non_admin_returns_403():
    """Non-admin requesting a specific user info must return 403 Forbidden."""
    user_token = get_token(email="user@gmail.com", user_id=3, role="USER")
    response = client.get("/users/1", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 403


def test_create_user_non_admin_returns_403():
    """Non-admin attempting to create a user must return 403 Forbidden."""
    user_token = get_token(email="user@gmail.com", user_id=3, role="USER")
    response = client.post(
        "/users",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "email": "test@example.com",
            "full_name": "Test User",
            "password": "password123",
            "role": "USER",
        },
    )
    assert response.status_code == 403


def test_update_user_non_admin_returns_403():
    """Non-admin attempting to update a user must return 403 Forbidden."""
    user_token = get_token(email="user@gmail.com", user_id=3, role="USER")
    response = client.put(
        "/users/1",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"full_name": "Hacked Name"},
    )
    assert response.status_code == 403


# ????????????????????????????????? Admin CRUD & Functional Tests ?????????????????????????????????

def test_admin_list_users_success():
    """Admin can get user list; response contains no passwords or password hashes."""
    admin_token = get_token()
    response = client.get("/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3

    for item in data:
        assert "id" in item
        assert "email" in item
        assert "full_name" in item
        assert "role" in item
        assert "is_active" in item
        # Ensure password and hash are never exposed
        assert "password" not in item
        assert "hashed_password" not in item
        assert "password_hash" not in item


def test_admin_list_users_search_and_filters():
    """Admin can search by keyword and filter by role and active status."""
    admin_token = get_token()

    # Search keyword
    res_search = client.get("/users?search=manager", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_search.status_code == 200
    data = res_search.json()
    assert len(data) == 1
    assert data[0]["email"] == "manager@gmail.com"

    # Filter role
    res_role = client.get("/users?role=ADMIN", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_role.status_code == 200
    for u in res_role.json():
        assert u["role"] == "ADMIN"

    # Filter is_active
    res_active = client.get("/users?is_active=true", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_active.status_code == 200
    assert len(res_active.json()) >= 3


def test_admin_get_user_by_id_success():
    """Admin can get a single user by ID."""
    admin_token = get_token()
    response = client.get("/users/2", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 2
    assert data["email"] == "manager@gmail.com"
    assert data["role"] == "MANAGER"
    assert "password" not in data
    assert "hashed_password" not in data


def test_admin_get_user_not_found():
    """Admin requesting non-existent user returns 404 Not Found."""
    admin_token = get_token()
    response = client.get("/users/9999", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 404
    assert "Không tìm thấy" in response.json()["detail"]


def test_admin_create_user_success_and_login():
    """
    Admin can create a new user:
    - Status code 201
    - Response has no plaintext/hashed password
    - New user can successfully log in using their credentials
    """
    admin_token = get_token()
    payload = {
        "email": "developer@company.com",
        "username": "developer",
        "full_name": "Developer Lead",
        "password": "devpassword123",
        "role": "MANAGER",
        "is_active": True,
    }
    response = client.post("/users", headers={"Authorization": f"Bearer {admin_token}"}, json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["email"] == "developer@company.com"
    assert created["username"] == "developer"
    assert created["full_name"] == "Developer Lead"
    assert created["role"] == "MANAGER"
    assert created["is_active"] is True
    assert "password" not in created
    assert "hashed_password" not in created

    # Verify that the created user can log in with new credentials
    login_res = client.post("/auth/login", json={
        "email": "developer@company.com",
        "password": "devpassword123",
    })
    assert login_res.status_code == 200
    assert login_res.json()["success"] is True
    assert login_res.json()["user"]["email"] == "developer@company.com"


def test_admin_create_user_duplicate_email():
    """Admin cannot create user with existing email (400 Bad Request)."""
    admin_token = get_token()
    payload = {
        "email": "admin@gmail.com",
        "full_name": "Duplicate Admin",
        "password": "password123",
    }
    response = client.post("/users", headers={"Authorization": f"Bearer {admin_token}"}, json=payload)
    assert response.status_code == 400
    assert "Email" in response.json()["detail"]


def test_admin_create_user_duplicate_username():
    """Admin cannot create user with existing username (400 Bad Request)."""
    admin_token = get_token()
    payload = {
        "email": "other@company.com",
        "username": "admin",
        "full_name": "Another User",
        "password": "password123",
    }
    response = client.post("/users", headers={"Authorization": f"Bearer {admin_token}"}, json=payload)
    assert response.status_code == 400
    assert "đã được sử dụng" in response.json()["detail"] or "sử dụng" in response.json()["detail"]


def test_admin_create_user_invalid_email_format():
    """Pydantic validation rejects invalid email format with 422 Unprocessable Entity."""
    admin_token = get_token()
    payload = {
        "email": "invalid-email-address",
        "full_name": "Invalid Email User",
        "password": "password123",
    }
    response = client.post("/users", headers={"Authorization": f"Bearer {admin_token}"}, json=payload)
    assert response.status_code == 422


def test_admin_create_user_short_password():
    """Pydantic validation rejects password shorter than 6 chars with 422."""
    admin_token = get_token()
    payload = {
        "email": "valid@example.com",
        "full_name": "Valid User",
        "password": "123",
    }
    response = client.post("/users", headers={"Authorization": f"Bearer {admin_token}"}, json=payload)
    assert response.status_code == 422


def test_admin_create_user_invalid_role():
    """Admin cannot create user with invalid role (400 Bad Request)."""
    admin_token = get_token()
    payload = {
        "email": "role_test@example.com",
        "full_name": "Role Test User",
        "password": "password123",
        "role": "SUPER_ADMIN",
    }
    response = client.post("/users", headers={"Authorization": f"Bearer {admin_token}"}, json=payload)
    assert response.status_code == 400
    assert "Vai trò không hợp lệ" in response.json()["detail"] or "hợp lệ" in response.json()["detail"]


def test_admin_update_user_put_and_patch():
    """Admin can update and partially update user information."""
    admin_token = get_token()

    # PUT update
    put_res = client.put(
        "/users/3",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "full_name": "Updated Normal User",
            "role": "MANAGER",
            "is_active": False,
        },
    )
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["full_name"] == "Updated Normal User"
    assert updated["role"] == "MANAGER"
    assert updated["is_active"] is False

    # PATCH partial update
    patch_res = client.patch(
        "/users/3",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": True},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is True
    assert patch_res.json()["full_name"] == "Updated Normal User"


def test_admin_update_user_duplicate_email():
    """Admin cannot update user email to an existing email (400 Bad Request)."""
    admin_token = get_token()
    response = client.put(
        "/users/3",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "admin@gmail.com"},
    )
    assert response.status_code == 400
    assert "Email" in response.json()["detail"]


def test_admin_update_user_password_and_login():
    """Admin can update user password and user can log in with new password."""
    admin_token = get_token()
    response = client.patch(
        "/users/3",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"password": "brandnewpassword123"},
    )
    assert response.status_code == 200

    # Old password no longer works
    old_login = client.post("/auth/login", json={"email": "user@gmail.com", "password": "123456"})
    assert old_login.status_code == 401

    # New password works
    new_login = client.post("/auth/login", json={"email": "user@gmail.com", "password": "brandnewpassword123"})
    assert new_login.status_code == 200
    assert new_login.json()["success"] is True
