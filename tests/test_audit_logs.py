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


def test_clear_audit_logs_endpoint_removed():
    """AC S2-04: Đã loại bỏ endpoint xóa toàn bộ audit log khỏi API ứng dụng (405 Method Not Allowed)."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.delete("/audit-logs", headers=admin_headers)
    assert res.status_code == 405


def test_discount_change_automatically_writes_audit_log():
    """AC S2-04: Thay đổi chiết khấu / giá trị báo giá tự động ghi nhật ký với entity_type='DISCOUNT'."""
    admin_headers = get_auth_headers("admin@gmail.com")

    # Cập nhật giá trị báo giá ID 1 từ 55,000,000 lên 70,000,000
    update_res = client.put("/quotes/1", json={"amount": 70000000.0}, headers=admin_headers)
    assert update_res.status_code == 200

    # Kiểm tra log ghi nhận
    log_res = client.get("/audit-logs?entity_type=DISCOUNT", headers=admin_headers)
    assert log_res.status_code == 200
    latest_log = log_res.json()["items"][0]
    assert latest_log["entity_type"] == "DISCOUNT"
    assert latest_log["entity_id"] == "QUOTE-1"
    assert latest_log["action"] == "UPDATE_DISCOUNT"
    assert latest_log["field_name"] == "amount"
    assert "55000000" in latest_log["old_value"]
    assert "70000000" in latest_log["new_value"]


def test_target_change_automatically_writes_audit_log():
    """AC S2-04: Thay đổi chỉ tiêu kinh doanh tự động ghi nhật ký với entity_type='TARGET'."""
    admin_headers = get_auth_headers("admin@gmail.com")

    # Cập nhật chỉ tiêu kinh doanh cho user ID 3
    quota_res = client.put("/users/3/target", json={"monthly_quota": 250000000.0}, headers=admin_headers)
    assert quota_res.status_code == 200

    # Kiểm tra log ghi nhận
    log_res = client.get("/audit-logs?entity_type=TARGET", headers=admin_headers)
    assert log_res.status_code == 200
    latest_log = log_res.json()["items"][0]
    assert latest_log["entity_type"] == "TARGET"
    assert latest_log["entity_id"] == "USER-3"
    assert latest_log["field_name"] == "monthly_quota"
    assert latest_log["new_value"] == "250000000.0"


def test_data_ownership_change_automatically_writes_audit_log():
    """AC S2-04: Thay đổi quyền sở hữu dữ liệu khách hàng tự động ghi nhật ký với entity_type='DATA_OWNERSHIP'."""
    admin_headers = get_auth_headers("admin@gmail.com")

    # Chuyển quyền sở hữu khách hàng ID 1 cho user ID 4
    cust_res = client.put("/customers/1", json={"owner_id": 4}, headers=admin_headers)
    assert cust_res.status_code == 200

    # Kiểm tra log ghi nhận
    log_res = client.get("/audit-logs?entity_type=DATA_OWNERSHIP", headers=admin_headers)
    assert log_res.status_code == 200
    latest_log = log_res.json()["items"][0]
    assert latest_log["entity_type"] == "DATA_OWNERSHIP"
    assert latest_log["entity_id"] == "CUST-1"
    assert latest_log["field_name"] == "owner_id"
    assert latest_log["new_value"] == "4"


def test_audit_log_immutability_no_modification_endpoints():
    """AC S2-04: Tính bất biến của nhật ký - không có endpoint PUT, PATCH hoặc DELETE để sửa/xóa nhật ký."""
    admin_headers = get_auth_headers("admin@gmail.com")
    # Không cho phép DELETE /audit-logs -> 405 Method Not Allowed
    res_del_all = client.delete("/audit-logs", headers=admin_headers)
    assert res_del_all.status_code == 405

    # Không cho phép PUT hoặc PATCH trên /audit-logs -> 405 Method Not Allowed
    res_put_root = client.put("/audit-logs", json={"new_value": "hacked"}, headers=admin_headers)
    assert res_put_root.status_code == 405

    res_patch_root = client.patch("/audit-logs", json={"new_value": "hacked"}, headers=admin_headers)
    assert res_patch_root.status_code == 405

    # Không tồn tại bất kỳ endpoint chỉnh sửa hoặc xóa theo ID nào
    res_put_item = client.put("/audit-logs/1", json={"new_value": "hacked"}, headers=admin_headers)
    assert res_put_item.status_code in (404, 405)

    res_del_item = client.delete("/audit-logs/1", headers=admin_headers)
    assert res_del_item.status_code in (404, 405)


def test_audit_log_db_failure_does_not_fallback_to_ram(monkeypatch):
    """AC S2-04: Bảo đảm lỗi ghi nhật ký không bị bỏ qua và không fallback RAM âm thầm."""
    from unittest.mock import MagicMock
    from app.core.database import SessionLocal

    # Mock SessionLocal để commit ném ngoại lệ
    def mock_session_fail():
        session = MagicMock()
        session.commit.side_effect = Exception("Database connection failure during audit log write")
        return session

    monkeypatch.setattr("app.services.audit_log_service.SessionLocal", mock_session_fail)

    with pytest.raises(Exception) as exc_info:
        log_change(
            user_id=1,
            user_name="Admin",
            entity_type="ROLE",
            entity_id="99",
            action="UPDATE_ROLE",
            field_name="role",
            old_value="USER",
            new_value="MANAGER",
        )
    assert "Database connection failure" in str(exc_info.value)


def test_audit_log_same_transaction_rolls_back_on_error():
    """AC S2-04: Ghi log cùng transaction với thay đổi nghiệp vụ - rollback nghiệp vụ làm rollback cả audit log."""
    from app.core.database import SessionLocal
    from app.models.audit_log import AuditLog as AuditLogModel

    db = SessionLocal()
    count_before = db.query(AuditLogModel).count()

    try:
        # Giả lập transaction nghiệp vụ có ghi log
        log_change(
            user_id=1,
            user_name="Admin",
            entity_type="TARGET",
            entity_id="USER-999",
            action="UPDATE_TARGET",
            field_name="monthly_quota",
            old_value="0",
            new_value="100000000",
            db=db,
        )
        # Giả lập lỗi nghiệp vụ xảy ra trước khi commit -> rollback toàn bộ transaction
        raise ValueError("Nghiệp vụ cập nhật thất bại")
    except ValueError:
        db.rollback()
    finally:
        count_after = db.query(AuditLogModel).count()
        db.close()

    # Xác nhận bản ghi audit log KHÔNG bị lưu rời rạc vào DB khi transaction rollback
    assert count_after == count_before


def test_quote_discount_flow_writes_full_audit_logs():
    """AC S2-04: Ghi đầy đủ từ các luồng thay đổi chiết khấu: tạo báo giá và cập nhật unit_price/amount."""
    manager_headers = get_auth_headers("manager@gmail.com")
    admin_headers = get_auth_headers("admin@gmail.com")

    # 1. Tạo báo giá mới có chiết khấu/định giá
    create_payload = {
        "title": "Báo giá Dịch vụ Phần mềm Test S2-04",
        "amount": 40000000.0,
        "unit_price": 40000000.0,
        "product_id": 1,
    }
    res_create = client.post("/quotes", json=create_payload, headers=manager_headers)
    assert res_create.status_code == 201
    quote_id = res_create.json()["id"]

    # 2. Cập nhật unit_price và amount (thay đổi mức chiết khấu)
    update_payload = {
        "amount": 35000000.0,
        "unit_price": 35000000.0,
    }
    res_update = client.put(f"/quotes/{quote_id}", json=update_payload, headers=manager_headers)
    assert res_update.status_code == 200

    # 3. Quản trị viên kiểm tra nhật ký
    log_res = client.get("/audit-logs?entity_type=DISCOUNT", headers=admin_headers)
    assert log_res.status_code == 200
    items = log_res.json()["items"]

    # Phải có các bản ghi tương ứng với quote_id
    quote_logs = [l for l in items if l["entity_id"] == f"QUOTE-{quote_id}"]
    assert len(quote_logs) >= 2
    fields_logged = {l["field_name"] for l in quote_logs}
    assert "amount" in fields_logged or "unit_price" in fields_logged

