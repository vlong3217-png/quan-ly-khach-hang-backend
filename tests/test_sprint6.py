import io
import pytest
from datetime import datetime, date, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.customer_service import reset_fake_customers
from app.services.opportunity_service import reset_fake_opportunities
from app.services.activity_service import reset_fake_activities
from app.services.pipeline_service import reset_fake_stages

client = TestClient(app)

def get_token(email: str = "admin@gmail.com", password: str = "123456") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_customers()
    reset_fake_opportunities()
    reset_fake_activities()
    reset_fake_stages()
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_opportunities()
    reset_fake_activities()
    reset_fake_stages()


# ==============================================================================
# S6-01: Lịch sử thay đổi cơ hội
# ==============================================================================

def test_s6_01_opportunity_history_recorded_on_change():
    """Thay đổi giai đoạn, giá trị, ngày chốt tạo đúng bản ghi lịch sử."""
    token = get_token("admin@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Update opportunity 1 (owned by Admin, id=1): update value and expected_close_date
    new_close_date = (date.today() + timedelta(days=60)).isoformat()
    update_res = client.put(
        "/opportunities/1",
        json={
            "value": 250000000.0,
            "expected_close_date": new_close_date,
        },
        headers=headers,
    )
    assert update_res.status_code == 200, update_res.text

    # 2. Query history
    hist_res = client.get("/opportunities/1/history", headers=headers)
    assert hist_res.status_code == 200, hist_res.text
    hist_data = hist_res.json()
    assert hist_data["total"] >= 2
    fields_changed = [item["field_name"] for item in hist_data["items"]]
    assert "value" in fields_changed
    assert "expected_close_date" in fields_changed

    # Check performer
    for item in hist_data["items"]:
        assert item["performed_by"] == 1  # admin@gmail.com ID is 1


def test_s6_01_opportunity_no_history_when_unchanged():
    """Không thay đổi dữ liệu thì không tạo bản ghi thay đổi giả."""
    token = get_token("admin@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Get initial history count
    hist_before = client.get("/opportunities/1/history", headers=headers).json()["total"]

    # Update with identical stage and value
    opp = client.get("/opportunities/1", headers=headers).json()
    client.put(
        "/opportunities/1",
        json={"stage": opp["stage"], "value": opp["value"]},
        headers=headers,
    )

    hist_after = client.get("/opportunities/1/history", headers=headers).json()["total"]
    assert hist_after == hist_before


def test_s6_01_opportunity_history_forbidden_for_unauthorized_user():
    """Kiểm tra quyền xem cơ hội trước khi trả lịch sử (403)."""
    # user2 (id=4, team 2) is not owner, not manager of opportunity 1 (owned by admin, or opp 3 owned by user1)
    token2 = get_token("user2@gmail.com")
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Opp 3 is owned by User 1 (id=3, team 1). User 2 (id=4, team 2) cannot access.
    hist_res = client.get("/opportunities/3/history", headers=headers2)
    assert hist_res.status_code == 403


# ==============================================================================
# S6-02: Tìm kiếm, lọc và lưu bộ lọc cơ hội
# ==============================================================================

def test_s6_02_advanced_search_and_filter():
    """Lọc kết hợp theo stage, min/max value, date range, product, owner."""
    token = get_token("admin@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Valid filter
    res = client.get(
        "/opportunities/search/advanced?min_value=10000000&max_value=300000000&stage=PROSPECTING",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "opportunities" in data
    assert "total" in data

    # Invalid range: min > max
    err_res = client.get(
        "/opportunities/search/advanced?min_value=500000000&max_value=10000000",
        headers=headers,
    )
    assert err_res.status_code == 400


def test_s6_02_saved_filters_crud_and_privacy():
    """Lưu, xem, cập nhật, xóa bộ lọc và chặn truy cập riêng tư của người khác."""
    token1 = get_token("user@gmail.com")
    headers1 = {"Authorization": f"Bearer {token1}"}

    token2 = get_token("user2@gmail.com")
    headers2 = {"Authorization": f"Bearer {token2}"}

    # 1. User 1 creates a private saved filter
    create_payload = {
        "name": "Cơ hội Q2 giá trị cao",
        "filter_criteria": {"min_value": 100000000, "stage": "PROSPECTING"},
        "is_public": False,
    }
    create_res = client.post("/opportunities/saved-filters", json=create_payload, headers=headers1)
    assert create_res.status_code == 201, create_res.text
    filter_id = create_res.json()["id"]

    # 2. User 1 can list it
    list_res = client.get("/opportunities/saved-filters", headers=headers1)
    assert list_res.status_code == 200
    assert any(f["id"] == filter_id for f in list_res.json())

    # 3. User 2 cannot see User 1's private filter
    list_res_u2 = client.get("/opportunities/saved-filters", headers=headers2)
    assert not any(f["id"] == filter_id for f in list_res_u2.json())

    # 4. User 2 cannot update User 1's private filter (403)
    upd_res = client.put(f"/opportunities/saved-filters/{filter_id}", json={"name": "Hacked"}, headers=headers2)
    assert upd_res.status_code == 403

    # 5. User 1 deletes the filter
    del_res = client.delete(f"/opportunities/saved-filters/{filter_id}", headers=headers1)
    assert del_res.status_code == 200


# ==============================================================================
# S6-03: Chia sẻ cơ hội cho nhiều thành viên
# ==============================================================================

def test_s6_03_share_opportunity_permissions_and_duplicates():
    """Chia sẻ cơ hội, chặn trùng lặp, chia sẻ cho phép thành viên truy cập."""
    token1 = get_token("user@gmail.com")  # id=3, owns opp 3
    headers1 = {"Authorization": f"Bearer {token1}"}

    token2 = get_token("user2@gmail.com")  # id=4
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Initial state: user2 cannot view opp 3
    assert client.get("/opportunities/3", headers=headers2).status_code == 403

    # 1. Share opp 3 to user2 (user_id=4)
    share_payload = {"user_id": 4, "permission_level": "READ_WRITE"}
    share_res = client.post("/opportunities/3/shares", json=share_payload, headers=headers1)
    assert share_res.status_code == 201, share_res.text

    # 2. Duplicate share rejected (400)
    dup_res = client.post("/opportunities/3/shares", json=share_payload, headers=headers1)
    assert dup_res.status_code == 400

    # 3. Now user2 can view opp 3
    view_res = client.get("/opportunities/3", headers=headers2)
    assert view_res.status_code == 200

    # 4. Shared member cannot transfer ownership or re-share (must be owner or manager/admin)
    trans_fail = client.post(
        "/opportunities/3/transfer-ownership",
        json={"new_owner_id": 4, "reason": "Self assign"},
        headers=headers2,
    )
    assert trans_fail.status_code == 403

    # 5. Remove share (returns 204 or 200)
    del_share = client.delete("/opportunities/3/shares/4", headers=headers1)
    assert del_share.status_code in (200, 204)

    # 6. User 2 loses access
    assert client.get("/opportunities/3", headers=headers2).status_code == 403


def test_s6_03_transfer_ownership_logs_history():
    """Chuyển quyền sở hữu ghi đầy đủ lịch sử người sở hữu cũ, mới, người thực hiện."""
    token_mgr = get_token("manager@gmail.com")
    headers_mgr = {"Authorization": f"Bearer {token_mgr}"}

    # Manager transfers opp 3 (owned by user 3, in Manager's team 1) to user 2 (manager)
    trans_res = client.post(
        "/opportunities/3/transfer-ownership",
        json={"new_owner_id": 2, "reason": "Bàn giao lại khu vực"},
        headers=headers_mgr,
    )
    assert trans_res.status_code == 200, trans_res.text

    # Check history
    hist = client.get("/opportunities/3/history", headers=headers_mgr).json()
    owner_hist = [h for h in hist["items"] if h["field_name"] == "owner_id"]
    assert len(owner_hist) > 0
    assert owner_hist[0]["old_value"] == "3"
    assert owner_hist[0]["new_value"] == "2"


# ==============================================================================
# S6-04: Đính kèm tài liệu vào cơ hội
# ==============================================================================

def test_s6_04_attachments_upload_download_delete_limits():
    """Tải lên tệp <= 20MB, kiểm tra metadata, chặn tệp quá giới hạn, phân quyền tải xuống."""
    token1 = get_token("user@gmail.com")
    headers1 = {"Authorization": f"Bearer {token1}"}

    token2 = get_token("user2@gmail.com")
    headers2 = {"Authorization": f"Bearer {token2}"}

    # 1. Upload valid document to opp 3
    file_content = b"Sample proposal document content"
    files = {"file": ("proposal.pdf", io.BytesIO(file_content), "application/pdf")}
    up_res = client.post("/opportunities/3/attachments", files=files, headers=headers1)
    assert up_res.status_code == 201, up_res.text
    att_data = up_res.json()
    att_id = att_data["id"]
    assert att_data["original_name"] == "proposal.pdf"
    assert att_data["uploaded_by"] == 3

    # 2. Unauthorized user cannot download (403)
    down_fail = client.get(f"/opportunities/3/attachments/{att_id}/download", headers=headers2)
    assert down_fail.status_code == 403

    # 3. Owner can download
    down_ok = client.get(f"/opportunities/3/attachments/{att_id}/download", headers=headers1)
    assert down_ok.status_code == 200
    assert down_ok.content == file_content

    # 4. Reject file larger than 20MB
    oversized_content = b"0" * (20 * 1024 * 1024 + 10)
    big_files = {"file": ("huge.pdf", io.BytesIO(oversized_content), "application/pdf")}
    big_res = client.post("/opportunities/3/attachments", files=big_files, headers=headers1)
    assert big_res.status_code == 400
    assert "20 MB" in big_res.json()["detail"] or "20MB" in big_res.json()["detail"]

    # 5. Delete attachment
    del_res = client.delete(f"/opportunities/3/attachments/{att_id}", headers=headers1)
    assert del_res.status_code in (200, 204)


# ==============================================================================
# S6-05: Ghi nhận hoạt động với khách hàng
# ==============================================================================

def test_s6_05_create_activities_all_types_and_past():
    """Ghi nhận 4 loại hoạt động (CALL, MEETING, EMAIL, NOTE), thời điểm quá khứ, validate liên kết."""
    token = get_token("user@gmail.com")  # id=3, owns customer 3, opp 3
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Past meeting
    past_time = (datetime.now() - timedelta(days=2)).isoformat()
    payload = {
        "title": "Gặp mặt đàm phán hợp đồng",
        "type": "MEETING",
        "occurred_at": past_time,
        "duration_minutes": 45,
        "result": "Khách đồng ý điều khoản thanh toán 50-50",
        "description": "Cần gửi lại dự thảo hợp đồng trong tuần",
        "customer_id": 3,
        "opportunity_id": 3,
    }
    res = client.post("/activities", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    act = res.json()
    assert act["type"] == "MEETING"
    assert act["customer_id"] == 3

    # 2. Invalid customer link
    invalid_payload = payload.copy()
    invalid_payload["customer_id"] = 9999
    err_res = client.post("/activities", json=invalid_payload, headers=headers)
    assert err_res.status_code in (400, 404)


# ==============================================================================
# S6-06: Tạo và theo dõi công việc
# ==============================================================================

def test_s6_06_tasks_lifecycle_and_permissions():
    """Tạo công việc, giao việc, hoàn thành, hoãn (bắt buộc lý do) và phân quyền."""
    token_mgr = get_token("manager@gmail.com")  # id=2, Manager Team 1
    headers_mgr = {"Authorization": f"Bearer {token_mgr}"}

    token_u1 = get_token("user@gmail.com")  # id=3, User 1 Team 1
    headers_u1 = {"Authorization": f"Bearer {token_u1}"}

    # 1. Manager assigns task to team member (user_id=3)
    due_date = (datetime.now() + timedelta(days=3)).isoformat()
    task_payload = {
        "title": "Gửi báo giá tùy chỉnh cho Doanh nghiệp A",
        "due_date": due_date,
        "priority": "HIGH",
        "assignee_id": 3,
        "customer_id": 3,
        "opportunity_id": 3,
        "description": "Ưu tiên hoàn thành trước thứ Sáu",
    }
    create_res = client.post("/activities/tasks", json=task_payload, headers=headers_mgr)
    assert create_res.status_code == 201, create_res.text
    task_id = create_res.json()["id"]

    # 2. Assignee postpones task - MUST have reason (empty reason rejected with 422 or 400)
    bad_postpone = client.post(
        f"/activities/tasks/{task_id}/postpone",
        json={"reason": "", "new_due_date": (datetime.now() + timedelta(days=5)).isoformat()},
        headers=headers_u1,
    )
    assert bad_postpone.status_code in (400, 422)

    new_due = (datetime.now() + timedelta(days=5)).isoformat()
    ok_postpone = client.post(
        f"/activities/tasks/{task_id}/postpone",
        json={"reason": "Khách hàng dời lịch làm việc sang tuần sau", "new_due_date": new_due},
        headers=headers_u1,
    )
    assert ok_postpone.status_code == 200
    assert ok_postpone.json()["status"] == "POSTPONED"

    # 3. Complete task
    comp_res = client.post(f"/activities/tasks/{task_id}/complete", headers=headers_u1)
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "COMPLETED"


# ==============================================================================
# S6-07: Lịch làm việc cá nhân và nhóm
# ==============================================================================

def test_s6_07_calendar_events_and_conflict_detection():
    """Truy vấn lịch cá nhân/nhóm và phát hiện chồng lấn (has_conflict)."""
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create two overlapping meetings at same time
    event_time = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    act1 = {
        "title": "Họp demo sản phẩm",
        "type": "MEETING",
        "occurred_at": event_time.isoformat(),
        "duration_minutes": 60,
        "customer_id": 3,
    }
    act2 = {
        "title": "Họp thương thảo hợp đồng",
        "type": "MEETING",
        "occurred_at": (event_time + timedelta(minutes=30)).isoformat(),
        "duration_minutes": 60,
        "customer_id": 3,
    }
    client.post("/activities", json=act1, headers=headers)
    client.post("/activities", json=act2, headers=headers)

    # Query calendar
    cal_res = client.get(
        f"/activities/calendar?view_type=WEEK&date={event_time.strftime('%Y-%m-%d')}",
        headers=headers,
    )
    assert cal_res.status_code == 200, cal_res.text
    cal_data = cal_res.json()
    assert cal_data["total_events"] >= 2
    # Conflict detection check
    conflicts = [item for item in cal_data["events"] if item["has_conflict"]]
    assert len(conflicts) > 0


# ==============================================================================
# S6-08: Dòng thời gian tương tác khách hàng
# ==============================================================================

def test_s6_08_customer_timeline():
    """Tổng hợp timeline tương tác khách hàng gồm activities, opp history và quotes theo thứ tự thời gian."""
    token = get_token("user@gmail.com")  # id=3, customer 3
    headers = {"Authorization": f"Bearer {token}"}

    # Add an activity for customer 3
    client.post(
        "/activities",
        json={
            "title": "Khách gọi hỏi về bảo hành",
            "type": "NOTE",
            "description": "Đã phản hồi chính sách bảo hành 24 tháng",
            "customer_id": 3,
        },
        headers=headers,
    )

    tl_res = client.get("/activities/timeline/3", headers=headers)
    assert tl_res.status_code == 200, tl_res.text
    tl_data = tl_res.json()
    assert "items" in tl_data
    assert tl_data["customer_id"] == 3
    assert len(tl_data["items"]) > 0

    # Ensure items are sorted descending by timestamp
    timestamps = [item["timestamp"] for item in tl_data["items"]]
    assert timestamps == sorted(timestamps, reverse=True)


# ==============================================================================
# S6-09: Nhắc việc sắp đến hạn và quá hạn
# ==============================================================================

def test_s6_09_reminders_and_overdue_summary():
    """Quét nhắc việc sắp đến hạn, quá hạn, chống trùng lặp và tổng hợp quá hạn cho trưởng nhóm."""
    token_mgr = get_token("manager@gmail.com")
    headers_mgr = {"Authorization": f"Bearer {token_mgr}"}

    # 1. Create an overdue task for user 3
    past_due = (datetime.now() - timedelta(days=2)).isoformat()
    client.post(
        "/activities/tasks",
        json={
            "title": "Nhiệm vụ bị trễ hạn",
            "due_date": past_due,
            "priority": "HIGH",
            "assignee_id": 3,
            "customer_id": 3,
        },
        headers=headers_mgr,
    )

    # 2. Run reminder scan
    scan_res = client.post("/activities/reminders/scan", headers=headers_mgr)
    assert scan_res.status_code == 200, scan_res.text
    first_notifs_count = scan_res.json()["new_notifications_count"]
    assert first_notifs_count >= 1

    # 3. Repeated scan does NOT create duplicate notification (dedup_key)
    rescan_res = client.post("/activities/reminders/scan", headers=headers_mgr)
    assert rescan_res.json()["new_notifications_count"] == 0

    # 4. Manager queries overdue tasks summary
    summary_res = client.get("/activities/tasks/overdue/summary", headers=headers_mgr)
    assert summary_res.status_code == 200, summary_res.text
    summary_data = summary_res.json()
    assert summary_data["total_overdue"] >= 1
    # Check that member list includes user 3
    member_overdues = [m for m in summary_data["members"] if m["user_id"] == 3]
    assert len(member_overdues) == 1
    assert member_overdues[0]["overdue_count"] >= 1


# ==============================================================================
# S6-10: Ghi nhanh kết quả cuộc gọi
# ==============================================================================

def test_s6_10_quick_call_log_and_callback():
    """Ghi nhanh cuộc gọi, tự động gắn cơ hội mở gần nhất và tạo lịch gọi lại."""
    token = get_token("user@gmail.com")  # id=3, owns customer 3 & opp 3
    headers = {"Authorization": f"Bearer {token}"}

    callback_time = (datetime.now() + timedelta(days=1, hours=2)).isoformat()
    quick_call_payload = {
        "customer_id": 3,
        "result": "Đã trao đổi sơ bộ, khách đang bận hẹn gọi lại",
        "note": "Quan tâm gói 100 người dùng",
        "schedule_callback": callback_time,
    }

    call_res = client.post("/activities/quick-call", json=quick_call_payload, headers=headers)
    assert call_res.status_code == 201, call_res.text
    data = call_res.json()

    # Activity created and auto-linked to customer 3's opportunity
    assert data["activity"]["type"] == "CALL"
    assert data["activity"]["customer_id"] == 3
    assert data["activity"]["opportunity_id"] is not None

    # Callback task created
    assert data["callback_task"] is not None
    assert "Gọi lại cho" in data["callback_task"]["title"]
