import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.services.auth_service import reset_fake_users_db
from app.services.data_handover_service import get_user_assigned_data, reset_handover_data_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users_db()
    reset_handover_data_store()
    yield
    reset_fake_users_db()
    reset_handover_data_store()


def get_token(email: str = "admin@gmail.com", user_id: int = 1, role: str = "ADMIN") -> str:
    return create_access_token({
        "sub": email,
        "id": user_id,
        "role": role,
    })


# ????????????????????????????????? 401 & 403 Authentication / Authorization Tests ?????????????????????????????????

def test_lock_account_no_token_returns_401():
    """Unauthenticated request to update user status must return 401."""
    response = client.patch("/users/3/status", json={"status": "LOCKED"})
    assert response.status_code == 401


def test_lock_account_invalid_token_returns_401():
    """Request with invalid/malformed token must return 401."""
    response = client.patch(
        "/users/3/status",
        headers={"Authorization": "Bearer invalid_token_abc"},
        json={"status": "LOCKED"},
    )
    assert response.status_code == 401


def test_lock_account_non_admin_returns_403():
    """Non-admin user (role USER) attempting to lock an account must return 403 Forbidden."""
    user_token = get_token(email="user@gmail.com", user_id=3, role="USER")
    response = client.patch(
        "/users/2/status",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"status": "LOCKED"},
    )
    assert response.status_code == 403
    assert "Ch??? Admin m???i c?? quy???n truy c???p" in response.json()["detail"]


def test_lock_account_manager_returns_403():
    """Manager (role MANAGER) attempting to lock an account must return 403 Forbidden."""
    manager_token = get_token(email="manager@gmail.com", user_id=2, role="MANAGER")
    response = client.patch(
        "/users/3/status",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"status": "LOCKED"},
    )
    assert response.status_code == 403
    assert "Ch??? Admin m???i c?? quy???n truy c???p" in response.json()["detail"]


# ????????????????????????????????? Status Update & Lock / Unlock Functionality ?????????????????????????????????

def test_lock_account_not_found_returns_404():
    """Locking non-existent user returns 404 Not Found."""
    admin_token = get_token()
    response = client.patch(
        "/users/9999/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "LOCKED"},
    )
    assert response.status_code == 404
    assert "Kh??ng t??m th???y" in response.json()["detail"]


def test_admin_cannot_self_lock():
    """Admin cannot lock their own account (400 Bad Request)."""
    admin_token = get_token(email="admin@gmail.com", user_id=1, role="ADMIN")
    response = client.patch(
        "/users/1/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "LOCKED"},
    )
    assert response.status_code == 400
    assert "Kh??ng th??? t??? kh??a t??i kho???n c???a ch??nh m??nh" in response.json()["detail"]


def test_lock_account_invalid_status_returns_400():
    """Updating with invalid status string returns 400 Bad Request."""
    admin_token = get_token()
    response = client.patch(
        "/users/3/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "SUSPENDED"},
    )
    assert response.status_code == 400
    assert "Tr???ng th??i kh??ng h???p l???" in response.json()["detail"]


def test_admin_lock_and_unlock_flow():
    """
    Test full lock and unlock cycle:
    1. Admin locks user (status -> LOCKED, is_active -> False)
    2. User cannot log in (401 with locked message)
    3. User's existing token cannot be used to call authenticated endpoints (401)
    4. Admin unlocks user (status -> ACTIVE, is_active -> True)
    5. User can log in again successfully
    6. User can make authenticated API requests again
    """
    admin_token = get_token()
    target_user_id = 3
    target_email = "user@gmail.com"
    target_password = "123456"

    # Step 0: Ensure target user can get token initially
    init_login = client.post("/auth/login", json={"email": target_email, "password": target_password})
    assert init_login.status_code == 200
    target_token = init_login.json()["access_token"]

    # Target token works for change password check
    check_auth = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {target_token}"},
        json={"current_password": "wrong_password", "new_password": "newpassword123"},
    )
    # Auth succeeded (raised 400 for wrong current password, not 401 for auth)
    assert check_auth.status_code == 400

    # Step 1: Admin locks user
    lock_res = client.patch(
        f"/users/{target_user_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "LOCKED"},
    )
    assert lock_res.status_code == 200
    lock_data = lock_res.json()
    assert lock_data["status"] == "LOCKED"
    assert lock_data["is_active"] is False
    assert "password" not in lock_data
    assert "hashed_password" not in lock_data

    # Step 2: User cannot log in
    locked_login = client.post("/auth/login", json={"email": target_email, "password": target_password})
    assert locked_login.status_code == 401
    assert "kh??a" in locked_login.json()["detail"].lower()

    # Step 3: Previously issued token cannot call authenticated APIs
    locked_req = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {target_token}"},
        json={"current_password": target_password, "new_password": "newpassword123"},
    )
    assert locked_req.status_code == 401
    assert "kh??a" in locked_req.json()["detail"].lower()

    # Step 4: Admin unlocks user
    unlock_res = client.patch(
        f"/users/{target_user_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "ACTIVE"},
    )
    assert unlock_res.status_code == 200
    unlock_data = unlock_res.json()
    assert unlock_data["status"] == "ACTIVE"
    assert unlock_data["is_active"] is True

    # Step 5: User can log in again
    re_login = client.post("/auth/login", json={"email": target_email, "password": target_password})
    assert re_login.status_code == 200
    new_token = re_login.json()["access_token"]

    # Step 6: User can call authenticated API again
    re_auth = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {new_token}"},
        json={"current_password": "wrong_password", "new_password": "newpassword123"},
    )
    assert re_auth.status_code == 400  # Passed auth, failed current_password check


# ????????????????????????????????? Data Handover Tests ?????????????????????????????????

def test_handover_data_standalone_api():
    """Test dedicated POST /users/{user_id}/handover endpoint."""
    admin_token = get_token()

    # User 3 initially owns 2 items (id 1 and id 2)
    initial_user3_items = get_user_assigned_data(3)
    assert len(initial_user3_items) == 2

    # Handover data from user 3 to user 2 (Manager)
    response = client.post(
        "/users/3/handover",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"target_user_id": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["transferred_items_count"] == 2
    assert data["source_user_id"] == 3
    assert data["target_user_id"] == 2

    # Verify user 3 now has 0 items and user 2 now has 3 items
    assert len(get_user_assigned_data(3)) == 0
    assert len(get_user_assigned_data(2)) == 3


def test_lock_account_with_handover_combined():
    """Test locking an account and handing over its data in a single PATCH /users/{id}/status call."""
    admin_token = get_token()

    # User 3 initially owns 2 items
    assert len(get_user_assigned_data(3)) == 2

    # Lock user 3 and handover data to user 2
    response = client.patch(
        "/users/3/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "status": "LOCKED",
            "handover_to_user_id": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "LOCKED"
    assert data["is_active"] is False
    assert data["handover"] is not None
    assert data["handover"]["transferred_items_count"] == 2
    assert data["handover"]["target_user_id"] == 2

    # Verify handover persistence in data store
    assert len(get_user_assigned_data(3)) == 0
    assert len(get_user_assigned_data(2)) == 3


def test_handover_to_self_returns_400():
    """Handover to the same user returns 400 Bad Request."""
    admin_token = get_token()
    response = client.post(
        "/users/3/handover",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"target_user_id": 3},
    )
    assert response.status_code == 400
    assert "ch??nh t??i kho???n n??y" in response.json()["detail"]


def test_handover_to_non_existent_target_returns_404():
    """Handover to non-existent target user returns 404 Not Found."""
    admin_token = get_token()
    response = client.post(
        "/users/3/handover",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"target_user_id": 9999},
    )
    assert response.status_code == 404
    assert "Kh??ng t??m th???y" in response.json()["detail"]


def test_handover_to_locked_target_returns_400():
    """Handover to a locked target user returns 400 Bad Request."""
    admin_token = get_token()

    # Lock user 2 first
    client.patch("/users/2/status", headers={"Authorization": f"Bearer {admin_token}"}, json={"status": "LOCKED"})

    # Try handing over user 3's data to locked user 2
    response = client.post(
        "/users/3/handover",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"target_user_id": 2},
    )
    assert response.status_code == 400
    assert "b??? kh??a" in response.json()["detail"]
