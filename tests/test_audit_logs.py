from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.audit_log_service import fake_audit_logs_db, log_change, clear_all_audit_logs
from app.services.auth_service import reset_fake_users

client = TestClient(app)


def seed_test_audit_logs():
    clear_all_audit_logs()
    # 4 bản ghi phục vụ chạy test
    l1 = log_change(1, "Admin", "ROLE", "3", "ASSIGN_ROLE", "role", "USER", "MANAGER")
    l2 = log_change(1, "Admin", "DISCOUNT", "QUOTE-101", "UPDATE_DISCOUNT", "discount_rate", "10%", "25%")
    l3 = log_change(2, "Manager Team A", "TARGET", "USER-3", "UPDATE_TARGET", "monthly_quota", "100000000", "150000000")
    l4 = log_change(1, "Admin", "DATA_OWNERSHIP", "CUST-88", "TRANSFER_OWNER", "assigned_to", "user1@gmail.com", "user2@gmail.com")

    # Override timestamps cho các test lọc theo ngày
    from app.core.database import SessionLocal
    from app.models.audit_log import AuditLog
    db = SessionLocal()
    r1 = db.query(AuditLog).filter(AuditLog.id == l1["id"]).first()
    if r1: r1.timestamp = datetime(2026, 9, 15, 10, 30, 0)
    r2 = db.query(AuditLog).filter(AuditLog.id == l2["id"]).first()
    if r2: r2.timestamp = datetime(2026, 9, 20, 14, 15, 0)
    r3 = db.query(AuditLog).filter(AuditLog.id == l3["id"]).first()
    if r3: r3.timestamp = datetime(2026, 9, 25, 9, 0, 0)
    r4 = db.query(AuditLog).filter(AuditLog.id == l4["id"]).first()
    if r4: r4.timestamp = datetime(2026, 9, 28, 16, 45, 0)
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    seed_test_audit_logs()
    yield
    reset_fake_users()
    clear_all_audit_logs()


def get_auth_headers(email: str = "admin@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_audit_logs_unauthorized_returns_401():
    """Không có JWT token -> HTTP 401."""
    res = client.get("/audit-logs")
    assert res.status_code == 401


def test_list_audit_logs_non_admin_returns_403():
    """Người dùng không phải Admin -> HTTP 403."""
    user_headers = get_auth_headers("user1@gmail.com")
    res = client.get("/audit-logs", headers=user_headers)
    assert res.status_code == 403


def test_list_audit_logs_admin_success():
    """AC S2-04: Quản trị hệ thống xem danh sách nhật ký thay đổi dữ liệu nhạy cảm."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.get("/audit-logs", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 4
    assert len(data["items"]) >= 4

    # Kiểm tra cấu trúc bản ghi log
    item = data["items"][0]
    assert "user_id" in item
    assert "user_name" in item
    assert "entity_type" in item
    assert "action" in item
    assert "old_value" in item
    assert "new_value" in item
    assert "timestamp" in item


def test_filter_audit_logs_by_entity_type():
    """AC S2-04: Lọc theo loại đối tượng (ROLE, DISCOUNT, TARGET, DATA_OWNERSHIP)."""
    admin_headers = get_auth_headers("admin@gmail.com")

    # Lọc DISCOUNT
    res_discount = client.get("/audit-logs?entity_type=DISCOUNT", headers=admin_headers)
    assert res_discount.status_code == 200
    items_discount = res_discount.json()["items"]
    assert all(i["entity_type"] == "DISCOUNT" for i in items_discount)

    # Lọc ROLE
    res_role = client.get("/audit-logs?entity_type=ROLE", headers=admin_headers)
    assert res_role.status_code == 200
    items_role = res_role.json()["items"]
    assert all(i["entity_type"] == "ROLE" for i in items_role)


def test_filter_audit_logs_by_user():
    """AC S2-04: Lọc theo người thực hiện."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.get("/audit-logs?user_id=2", headers=admin_headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) >= 1
    assert all(i["user_id"] == 2 for i in items)


def test_filter_audit_logs_by_date_range():
    """AC S2-04: Lọc theo khoảng thời gian."""
    admin_headers = get_auth_headers("admin@gmail.com")

    # Lọc trong khoảng ngày 2026-09-18 đến 2026-09-22 (bản ghi DISCOUNT ở 2026-09-20)
    from_date = "2026-09-18T00:00:00"
    to_date = "2026-09-22T23:59:59"
    res = client.get(f"/audit-logs?from_date={from_date}&to_date={to_date}", headers=admin_headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["entity_type"] == "DISCOUNT"


def test_audit_log_invalid_entity_type_returns_400():
    """Lọc loại đối tượng không hợp lệ -> HTTP 400."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.get("/audit-logs?entity_type=INVALID_TYPE", headers=admin_headers)
    assert res.status_code == 400
    assert "Loại đối tượng không hợp lệ" in res.json()["detail"]


def test_role_change_automatically_writes_audit_log():
    """Khi Admin cập nhật vai trò người dùng, hệ thống tự động ghi nhật ký Audit Log."""
    admin_headers = get_auth_headers("admin@gmail.com")

    # Đổi role user 3 từ USER sang MANAGER
    assign_res = client.put("/users/3/role", json={"role": "MANAGER"}, headers=admin_headers)
    assert assign_res.status_code == 200

    # Kiểm tra log ghi nhận
    log_res = client.get("/audit-logs?entity_type=ROLE", headers=admin_headers)
    assert log_res.status_code == 200
    latest_log = log_res.json()["items"][0]
    assert latest_log["entity_id"] == "3"
    assert latest_log["old_value"] == "USER"
    assert latest_log["new_value"] == "MANAGER"
    assert latest_log["user_id"] == 1
