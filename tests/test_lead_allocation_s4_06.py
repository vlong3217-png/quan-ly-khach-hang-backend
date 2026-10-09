import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, engine
from app.models.lead import Lead, LeadAllocationRule, LeadAllocationLog
from app.models.user import Base
from app.core.security import create_access_token

client = TestClient(app)


def get_auth_headers(email: str = "admin@gmail.com", role: str = "ADMIN", user_id: int = 1) -> dict:
    token = create_access_token(data={"sub": email, "id": user_id, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_allocation_tables():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(Lead).delete()
    db.query(LeadAllocationRule).delete()
    db.query(LeadAllocationLog).delete()
    db.commit()
    db.close()
    yield


def test_allocation_rules_configuration_and_rbac():
    """
    AC S4-06: Khai báo quy tắc phân bổ theo khu vực, ngành nghề hoặc xoay vòng.
    - Quản lý thứ tự ưu tiên (priority).
    - Kiểm tra phân quyền: Chỉ ADMIN/MANAGER được cấu hình quy tắc.
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    manager_headers = get_auth_headers("manager@gmail.com", role="MANAGER", user_id=2)
    user_headers = get_auth_headers("user1@gmail.com", role="USER", user_id=3)

    # 1. USER không có quyền tạo quy tắc (403 Forbidden)
    res_forbidden = client.post(
        "/leads/allocation-rules",
        json={
            "name": "Quy tắc test",
            "priority": 1,
            "criterion_type": "REGION",
            "criterion_value": "Hà Nội",
            "allocation_method": "ROUND_ROBIN",
            "assignee_user_ids": [3, 4],
        },
        headers=user_headers,
    )
    assert res_forbidden.status_code == 403

    # 2. MANAGER tạo quy tắc ưu tiên 1: Ngành Tài chính
    r1 = {
        "name": "Ưu tiên Ngành Tài chính - Ngân hàng",
        "priority": 1,
        "criterion_type": "INDUSTRY",
        "criterion_value": "Tài chính, Ngân hàng",
        "allocation_method": "SPECIFIC_USER",
        "assignee_user_ids": [3],
    }
    res1 = client.post("/leads/allocation-rules", json=r1, headers=manager_headers)
    assert res1.status_code == 201
    assert res1.json()["id"] is not None
    rule1_id = res1.json()["id"]

    # 3. ADMIN tạo quy tắc ưu tiên 2: Khu vực Miền Bắc (xoay vòng giữa 4 và 5)
    r2 = {
        "name": "Khu vực Miền Bắc (Xoay vòng)",
        "priority": 2,
        "criterion_type": "REGION",
        "criterion_value": "Hà Nội, Hải Phòng, Bắc Ninh",
        "allocation_method": "ROUND_ROBIN",
        "assignee_user_ids": [4, 5],
    }
    res2 = client.post("/leads/allocation-rules", json=r2, headers=admin_headers)
    assert res2.status_code == 201

    # 4. Xem danh sách quy tắc - đã sắp xếp theo priority
    res_list = client.get("/leads/allocation-rules", headers=user_headers)
    assert res_list.status_code == 200
    items = res_list.json()
    assert len(items) == 2
    assert items[0]["priority"] <= items[1]["priority"]

    # 5. Cập nhật quy tắc
    res_up = client.put(
        f"/leads/allocation-rules/{rule1_id}",
        json={"name": "Ưu tiên Khối Tài chính & Chứng khoán"},
        headers=admin_headers,
    )
    assert res_up.status_code == 200
    assert res_up.json()["name"] == "Ưu tiên Khối Tài chính & Chứng khoán"

    # 6. Xóa quy tắc
    res_del = client.delete(f"/leads/allocation-rules/{rule1_id}", headers=admin_headers)
    assert res_del.status_code == 204


def test_priority_and_round_robin_lead_allocation():
    """
    AC S4-06:
    - Nhiều quy tắc có thứ tự ưu tiên (ưu tiên cao hơn được khớp trước).
    - Phân bổ xoay vòng (Round Robin) công bằng lần lượt giữa các nhân viên.
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    user_headers = get_auth_headers("user@gmail.com", role="USER", user_id=3)

    # Quy tắc 1: Ưu tiên 1 - Ngành Tài chính -> gán cố định cho User 3
    client.post(
        "/leads/allocation-rules",
        json={
            "name": "Team Tài chính",
            "priority": 1,
            "criterion_type": "INDUSTRY",
            "criterion_value": "Tài chính",
            "allocation_method": "SPECIFIC_USER",
            "assignee_user_ids": [3],
        },
        headers=admin_headers,
    )

    # Quy tắc 2: Ưu tiên 2 - Khu vực Hà Nội -> xoay vòng [4, 5]
    client.post(
        "/leads/allocation-rules",
        json={
            "name": "Team Hà Nội Round-Robin",
            "priority": 2,
            "criterion_type": "REGION",
            "criterion_value": "Hà Nội",
            "allocation_method": "ROUND_ROBIN",
            "assignee_user_ids": [4, 5],
        },
        headers=admin_headers,
    )

    # Lead 1: Ngành Tài chính ở Hà Nội -> Khớp Rule 1 trước (vì priority 1 > 2) -> gán cho User 3
    res_l1 = client.post(
        "/leads",
        json={"full_name": "Ngân hàng ABC", "email": "abc@bank.vn", "industry": "Tài chính", "city": "Hà Nội"},
        headers=user_headers,
    )
    assert res_l1.status_code == 201
    lead1 = res_l1.json()
    assert lead1["owner_id"] == 3
    assert lead1["allocation_status"] == "ASSIGNED"

    # Lead 2: Ngành Bán lẻ ở Hà Nội -> Không khớp Rule 1, khớp Rule 2 -> Lượt 1 của Round-Robin -> gán cho User 4
    res_l2 = client.post(
        "/leads",
        json={"full_name": "Siêu thị HN 1", "email": "hn1@mart.vn", "industry": "Bán lẻ", "city": "Hà Nội"},
        headers=user_headers,
    )
    assert res_l2.status_code == 201
    lead2 = res_l2.json()
    assert lead2["owner_id"] == 4
    assert lead2["allocation_status"] == "ASSIGNED"

    # Lead 3: Ngành Giáo dục ở Hà Nội -> Khớp Rule 2 -> Lượt 2 của Round-Robin -> gán cho User 5
    res_l3 = client.post(
        "/leads",
        json={"full_name": "Trường học HN 2", "email": "hn2@edu.vn", "industry": "Giáo dục", "city": "Hà Nội"},
        headers=user_headers,
    )
    assert res_l3.status_code == 201
    lead3 = res_l3.json()
    assert lead3["owner_id"] == 5

    # Lead 4: Ngành Du lịch ở Hà Nội -> Khớp Rule 2 -> Lượt 3 xoay vòng trở lại User 4
    res_l4 = client.post(
        "/leads",
        json={"full_name": "Công ty Tour HN 3", "email": "hn3@tour.vn", "industry": "Du lịch", "city": "Hà Nội"},
        headers=user_headers,
    )
    assert res_l4.status_code == 201
    lead4 = res_l4.json()
    assert lead4["owner_id"] == 4


def test_unmatched_leads_enter_queue_and_manual_assignment():
    """
    AC S4-06:
    - Lead không khớp quy tắc vào hàng chờ (QUEUED) để trưởng nhóm phân tay.
    - Trưởng nhóm (MANAGER) phân bổ thủ công kèm ghi chú.
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    manager_headers = get_auth_headers("manager@gmail.com", role="MANAGER", user_id=2)
    user_headers = get_auth_headers("user@gmail.com", role="USER", user_id=3)

    # Cấu hình quy tắc chỉ nhận khu vực Hà Nội
    client.post(
        "/leads/allocation-rules",
        json={
            "name": "Chỉ nhận Hà Nội",
            "priority": 1,
            "criterion_type": "REGION",
            "criterion_value": "Hà Nội",
            "allocation_method": "SPECIFIC_USER",
            "assignee_user_ids": [3],
        },
        headers=admin_headers,
    )

    # Tạo lead ở Cần Thơ (không khớp quy tắc)
    res_lead = client.post(
        "/leads",
        json={"full_name": "Công ty Miền Tây", "email": "mientay@corp.vn", "city": "Cần Thơ", "industry": "Nông nghiệp"},
        headers=user_headers,
    )
    assert res_lead.status_code == 201
    lead = res_lead.json()
    lead_id = lead["id"]
    assert lead["owner_id"] is None
    assert lead["allocation_status"] == "QUEUED"
    assert "hàng chờ phân bổ" in lead["allocation_note"]

    # Kiểm tra hàng chờ phân bổ
    res_queue = client.get("/leads/allocation-queue", headers=manager_headers)
    assert res_queue.status_code == 200
    assert res_queue.json()["total"] == 1
    assert res_queue.json()["items"][0]["id"] == lead_id

    # Trưởng nhóm phân bổ thủ công từ hàng chờ cho User 4 kèm ghi chú
    res_manual = client.post(
        f"/leads/{lead_id}/manual-assign",
        json={"owner_id": 4, "note": "Giao cho phụ trách khu vực Tây Nam Bộ"},
        headers=manager_headers,
    )
    assert res_manual.status_code == 200
    assigned_lead = res_manual.json()
    assert assigned_lead["owner_id"] == 4
    assert assigned_lead["allocation_status"] == "ASSIGNED"
    assert "Tây Nam Bộ" in assigned_lead["allocation_note"]

    # Hàng chờ bây giờ phải trống
    res_empty_queue = client.get("/leads/allocation-queue", headers=manager_headers)
    assert res_empty_queue.json()["total"] == 0

    # Kiểm tra nhật ký phân bổ
    res_logs = client.get(f"/leads/allocation-logs?lead_id={lead_id}", headers=manager_headers)
    assert res_logs.status_code == 200
    logs = res_logs.json()
    assert len(logs) >= 2  # 1 log QUEUED lúc tạo, 1 log MANUAL lúc phân tay
    assert any(log["status"] == "MANUAL" and log["assigned_to"] == 4 for log in logs)


def test_batch_and_background_lead_allocation():
    """
    AC S4-06: Phân bổ chạy nền và hoàn tất trong vòng 5 phút.
    - Kích hoạt quy trình xử lý hàng loạt tất cả lead trong hàng chờ khi có quy tắc mới.
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    manager_headers = get_auth_headers("manager@gmail.com", role="MANAGER", user_id=2)
    user_headers = get_auth_headers("user@gmail.com", role="USER", user_id=3)

    # Chưa có quy tắc nào -> Tạo 3 lead, cả 3 đều vào hàng chờ QUEUED
    for i in range(3):
        res = client.post(
            "/leads",
            json={"full_name": f"Khách Hàng Chờ {i+1}", "email": f"queued{i+1}@test.com", "industry": "Logistics"},
            headers=user_headers,
        )
        assert res.json()["allocation_status"] == "QUEUED"

    # Kiểm tra hàng chờ có 3 lead
    res_q = client.get("/leads/allocation-queue", headers=manager_headers)
    assert res_q.json()["total"] == 3

    # Giám đốc bổ sung quy tắc nhận tất cả lead (ANY) và xoay vòng giữa [3, 4]
    client.post(
        "/leads/allocation-rules",
        json={
            "name": "Quy tắc chung nhận hàng chờ",
            "priority": 1,
            "criterion_type": "ANY",
            "allocation_method": "ROUND_ROBIN",
            "assignee_user_ids": [3, 4],
        },
        headers=admin_headers,
    )

    # Kích hoạt quét nền toàn bộ hàng chờ
    res_bg = client.post("/leads/allocation/run-background", headers=manager_headers)
    assert res_bg.status_code == 200
    bg_result = res_bg.json()
    assert bg_result["success"] is True
    assert bg_result["total_processed"] == 3
    assert bg_result["assigned_count"] == 3
    assert bg_result["queued_count"] == 0

    # Hàng chờ đã xử lý hết sạch
    res_q_after = client.get("/leads/allocation-queue", headers=manager_headers)
    assert res_q_after.json()["total"] == 0
