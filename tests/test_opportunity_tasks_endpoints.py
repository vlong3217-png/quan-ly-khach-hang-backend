import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.opportunity_task_service import reset_fake_tasks

client = TestClient(app)


def get_token(email: str = "user@gmail.com", password: str = "123456") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_tasks()
    yield
    reset_fake_users()
    reset_fake_tasks()


def test_list_opportunity_tasks_empty():
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/opportunity-tasks", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["items"] == []
    assert data["total"] == 0


def test_create_and_get_opportunity_task():
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "opportunity_id": "1",
        "opportunity_title": "Dự án CRM Alpha",
        "customer_id": "10",
        "customer_name": "Công ty Alpha",
        "title": "Gọi điện chốt hợp đồng",
        "description": "Thảo luận điều khoản thanh toán",
        "assigned_to_id": 3,
        "assigned_to_name": "User 1",
        "due_date": "2026-10-25",
        "due_time": "14:00",
        "priority": "HIGH",
    }

    create_res = client.post("/opportunity-tasks", json=payload, headers=headers)
    assert create_res.status_code == 201
    task = create_res.json()
    assert task["id"] is not None
    assert task["title"] == "Gọi điện chốt hợp đồng"
    assert task["is_completed"] is False
    assert task["status"] == "TODO"

    # Get by ID
    get_res = client.get(f"/opportunity-tasks/{task['id']}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == task["id"]

    # Filter by opportunity
    list_opp_res = client.get("/opportunities/1/tasks", headers=headers)
    assert list_opp_res.status_code == 200
    opp_data = list_opp_res.json()
    assert len(opp_data["items"]) == 1
    assert opp_data["items"][0]["id"] == task["id"]


def test_update_and_postpone_task():
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/opportunity-tasks",
        json={"title": "Họp demo sản phẩm", "due_date": "2026-10-20"},
        headers=headers,
    )
    task_id = create_res.json()["id"]

    # Postpone task
    update_res = client.put(
        f"/opportunity-tasks/{task_id}",
        json={
            "due_date": "2026-10-28",
            "status": "POSTPONED",
            "postponed_reason": "Khách hàng bận công tác",
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["due_date"] == "2026-10-28"
    assert updated["status"] == "POSTPONED"
    assert updated["postponed_reason"] == "Khách hàng bận công tác"

    # Toggle complete
    complete_res = client.put(
        f"/opportunity-tasks/{task_id}",
        json={"is_completed": True},
        headers=headers,
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["is_completed"] is True
    assert complete_res.json()["status"] == "COMPLETED"


def test_delete_task():
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/opportunity-tasks",
        json={"title": "Task cần xóa", "due_date": "2026-10-20"},
        headers=headers,
    )
    task_id = create_res.json()["id"]

    del_res = client.delete(f"/opportunity-tasks/{task_id}", headers=headers)
    assert del_res.status_code == 204

    # Check not found
    get_res = client.get(f"/opportunity-tasks/{task_id}", headers=headers)
    assert get_res.status_code == 404


def test_task_not_found():
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/opportunity-tasks/non-existing-task-id", headers=headers)
    assert res.status_code == 404


def test_task_unauthorized():
    res = client.get("/opportunity-tasks")
    assert res.status_code == 401


def test_user_cannot_access_other_user_task():
    """User không có quyền xem/sửa task của người khác nếu thuộc nhóm khác và không phải admin/owner."""
    from app.services.auth_service import FAKE_USERS, hash_password
    # Tạo user mới ở team khác
    other_user = {
        "id": 99,
        "email": "other@gmail.com",
        "username": "other",
        "full_name": "Other User",
        "role": "USER",
        "is_active": True,
        "status": "ACTIVE",
        "hashed_password": hash_password("123456"),
        "team_id": 99,
    }
    FAKE_USERS.append(other_user)

    user1_token = get_token("user@gmail.com")
    user1_headers = {"Authorization": f"Bearer {user1_token}"}
    create_res = client.post(
        "/opportunity-tasks",
        json={"title": "Task của User 1", "due_date": "2026-10-25"},
        headers=user1_headers,
    )
    task_id = create_res.json()["id"]

    # Other user login
    other_token = get_token("other@gmail.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}

    get_res = client.get(f"/opportunity-tasks/{task_id}", headers=other_headers)
    assert get_res.status_code == 403

    update_res = client.put(f"/opportunity-tasks/{task_id}", json={"title": "Hacked"}, headers=other_headers)
    assert update_res.status_code == 403

    del_res = client.delete(f"/opportunity-tasks/{task_id}", headers=other_headers)
    assert del_res.status_code == 403
