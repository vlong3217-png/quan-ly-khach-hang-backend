"""
Tests for Sprint 5 - S5-07: Cảnh báo cơ hội đình trệ.

AC:
1. Cơ hội không có hoạt động trong N ngày (N theo giai đoạn) bị gắn cờ STAGNANT.
2. Cơ hội quá expected_close_date mà vẫn OPEN bị gắn cờ OVERDUE.
3. API danh sách cơ hội bị gắn cờ, phân quyền theo nhóm (MANAGER) / toàn quyền (ADMIN).
4. Service/endpoint quét để cập nhật cờ (daily job).
"""
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.services import activity_service, opportunity_service, pipeline_service
from app.services import opportunity_stagnant_service as svc

client = TestClient(app)

TODAY = date(2026, 10, 9)


def auth(email: str, role: str, user_id: int):
    token = create_access_token(data={"sub": email, "id": user_id, "role": role})
    return {"Authorization": f"Bearer {token}"}


ADMIN = lambda: auth("admin@gmail.com", "ADMIN", 1)
MANAGER = lambda: auth("manager@gmail.com", "MANAGER", 2)
USER = lambda: auth("user@gmail.com", "USER", 3)


def get_opp(opp_id: int) -> dict:
    return next(o for o in opportunity_service.FAKE_OPPORTUNITIES if o["id"] == opp_id)


@pytest.fixture(autouse=True)
def setup_data():
    pipeline_service.reset_fake_stages()
    opportunity_service.reset_fake_opportunities()
    activity_service.reset_fake_activities()
    # Mốc tạo cơ hội cố định: tất cả vừa mới tạo (chưa đình trệ)
    for o in opportunity_service.FAKE_OPPORTUNITIES:
        o["created_at"] = "2026-10-08T08:00:00"
    yield


# ---------------------------------------------------------------- AC1
def test_stagnant_threshold_per_stage():
    assert svc.get_stagnant_threshold_days("PROSPECTING") == 14
    assert svc.get_stagnant_threshold_days("NEGOTIATION") == 5
    # Cấu hình theo stage (admin chỉnh stagnant_days)
    resp = client.put("/pipeline-stages/3", json={"stagnant_days": 3}, headers=ADMIN())
    assert resp.status_code == 200
    assert resp.json()["stagnant_days"] == 3
    assert svc.get_stagnant_threshold_days("PROPOSAL") == 3


def test_stagnant_threshold_validation():
    resp = client.put("/pipeline-stages/3", json={"stagnant_days": 0}, headers=ADMIN())
    assert resp.status_code == 422


def test_opportunity_without_activity_for_n_days_is_stagnant():
    # Opp 1 ở PROPOSAL (N=7), tạo cách 8 ngày, không có activity
    get_opp(1)["created_at"] = "2026-10-01T08:00:00"
    ev = svc.evaluate_opportunity(get_opp(1), TODAY)
    assert ev["is_stagnant"] is True
    assert ev["flag_reasons"] == ["STAGNANT"]
    assert ev["days_inactive"] == 8
    assert ev["stagnant_threshold_days"] == 7


def test_recent_opportunity_not_flagged():
    get_opp(1)["created_at"] = "2026-10-05T08:00:00"  # 4 ngày < 7
    assert svc.evaluate_opportunity(get_opp(1), TODAY)["is_flagged"] is False


def test_recent_activity_resets_stagnation():
    get_opp(1)["created_at"] = "2026-09-01T08:00:00"
    assert svc.evaluate_opportunity(get_opp(1), TODAY)["is_stagnant"] is True
    resp = client.post(
        "/activities",
        json={"title": "Gọi khách", "type": "CALL", "opportunity_id": 1},
        headers=MANAGER(),
    )
    assert resp.status_code == 201
    assert resp.json()["opportunity_id"] == 1
    # Hoạt động mới tạo "hôm nay" (thời gian thực) -> đánh giá theo ngày hôm nay thực
    assert svc.evaluate_opportunity(get_opp(1), date.today())["is_stagnant"] is False


def test_activity_on_other_opportunity_does_not_count():
    get_opp(1)["created_at"] = "2026-09-01T08:00:00"
    activity_service.FAKE_ACTIVITIES.append(
        {"id": 99, "title": "x", "type": "CALL", "owner_id": 2, "team_id": 1,
         "opportunity_id": 2, "created_at": "2026-10-09T08:00:00"}
    )
    assert svc.evaluate_opportunity(get_opp(1), TODAY)["is_stagnant"] is True


def test_last_activity_at_field_counts():
    get_opp(1)["created_at"] = "2026-09-01T08:00:00"
    get_opp(1)["last_activity_at"] = "2026-10-08T10:00:00"
    assert svc.evaluate_opportunity(get_opp(1), TODAY)["is_stagnant"] is False


def test_threshold_boundary_exactly_n_days():
    get_opp(1)["created_at"] = "2026-10-02T08:00:00"  # đúng 7 ngày
    assert svc.evaluate_opportunity(get_opp(1), TODAY)["is_stagnant"] is True
    get_opp(1)["created_at"] = "2026-10-03T08:00:00"  # 6 ngày
    assert svc.evaluate_opportunity(get_opp(1), TODAY)["is_stagnant"] is False


# ---------------------------------------------------------------- AC2
def test_overdue_open_opportunity_flagged():
    get_opp(1)["expected_close_date"] = "2026-10-08"
    ev = svc.evaluate_opportunity(get_opp(1), TODAY)
    assert ev["is_overdue"] is True
    assert ev["days_overdue"] == 1
    assert "OVERDUE" in ev["flag_reasons"]
    assert ev["is_stagnant"] is False


def test_expected_close_today_or_future_not_overdue():
    get_opp(1)["expected_close_date"] = "2026-10-09"
    assert svc.evaluate_opportunity(get_opp(1), TODAY)["is_overdue"] is False
    get_opp(1)["expected_close_date"] = "2026-12-01"
    assert svc.evaluate_opportunity(get_opp(1), TODAY)["is_overdue"] is False


def test_closed_opportunity_never_flagged():
    # Opp 4 là CLOSED_WON
    get_opp(4)["created_at"] = "2025-01-01T08:00:00"
    get_opp(4)["expected_close_date"] = "2025-02-01"
    assert svc.evaluate_opportunity(get_opp(4), TODAY)["is_flagged"] is False
    # status không còn OPEN
    get_opp(1)["status"] = "LOST"
    get_opp(1)["expected_close_date"] = "2025-02-01"
    assert svc.evaluate_opportunity(get_opp(1), TODAY)["is_flagged"] is False


def test_both_reasons_together():
    get_opp(1)["created_at"] = "2026-09-01T08:00:00"
    get_opp(1)["expected_close_date"] = date(2026, 9, 30)
    ev = svc.evaluate_opportunity(get_opp(1), TODAY)
    assert ev["flag_reasons"] == ["STAGNANT", "OVERDUE"]


def test_create_opportunity_with_expected_close_date():
    resp = client.post(
        "/opportunities",
        json={"title": "Cơ hội mới", "value": 1000, "expected_close_date": "2026-01-01"},
        headers=MANAGER(),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "OPEN"
    assert resp.json()["expected_close_date"] == "2026-01-01"
    resp = client.post(
        "/opportunities",
        json={"title": "Sai ngày", "expected_close_date": "not-a-date"},
        headers=MANAGER(),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------- AC4
def test_scan_sets_flags_and_summary():
    get_opp(1)["created_at"] = "2026-09-01T08:00:00"       # stagnant
    get_opp(2)["expected_close_date"] = "2026-10-01"        # overdue
    summary = svc.run_daily_scan(TODAY)
    assert summary["scanned"] == 4
    assert summary["flagged"] == 2
    assert summary["stagnant"] == 1
    assert summary["overdue"] == 1
    assert get_opp(1)["is_flagged"] is True
    assert get_opp(1)["flagged_at"] is not None
    assert get_opp(3)["is_flagged"] is False


def test_scan_clears_flag_when_resolved():
    get_opp(2)["expected_close_date"] = "2026-10-01"
    svc.run_daily_scan(TODAY)
    assert get_opp(2)["is_flagged"] is True
    get_opp(2)["expected_close_date"] = "2026-11-01"
    svc.run_daily_scan(TODAY)
    assert get_opp(2)["is_flagged"] is False
    assert get_opp(2)["flagged_at"] is None


def test_scan_endpoint_permissions():
    assert client.post("/opportunities/flagged/scan", headers=USER()).status_code == 403
    assert client.post("/opportunities/flagged/scan").status_code in (401, 403)
    resp = client.post("/opportunities/flagged/scan?as_of=2026-10-09", headers=ADMIN())
    assert resp.status_code == 200
    assert resp.json()["scanned"] == 4
    assert resp.json()["scan_date"] == "2026-10-09"


def test_scan_endpoint_invalid_date():
    resp = client.post("/opportunities/flagged/scan?as_of=abc", headers=ADMIN())
    assert resp.status_code == 422


def test_manager_scan_limited_to_team():
    # Thêm cơ hội team 2 đình trệ
    opportunity_service.FAKE_OPPORTUNITIES.append({
        "id": 50, "title": "Team 2 stagnant", "value": 1.0, "stage": "PROPOSAL",
        "owner_id": 4, "team_id": 2, "created_at": "2026-09-01T08:00:00",
    })
    resp = client.post("/opportunities/flagged/scan?as_of=2026-10-09", headers=MANAGER())
    assert resp.status_code == 200
    assert resp.json()["scanned"] == 3  # chỉ cơ hội team 1
    assert "is_flagged" not in get_opp(50)


# ---------------------------------------------------------------- AC3
def _seed_flagged():
    get_opp(1)["created_at"] = "2026-09-01T08:00:00"        # team 1 stagnant
    get_opp(2)["expected_close_date"] = "2026-10-01"        # team 1 overdue
    opportunity_service.FAKE_OPPORTUNITIES.append({
        "id": 50, "title": "Team 2 stagnant", "value": 1.0, "stage": "PROPOSAL",
        "owner_id": 4, "team_id": 2, "created_at": "2026-09-01T08:00:00",
    })
    svc.run_daily_scan(TODAY)


def test_list_flagged_admin_sees_all():
    _seed_flagged()
    resp = client.get("/opportunities/flagged", headers=ADMIN())
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "ALL"
    assert {o["id"] for o in data["opportunities"]} == {1, 2, 50}
    by_id = {o["id"]: o for o in data["opportunities"]}
    assert by_id[1]["flag_reasons"] == ["STAGNANT"]
    assert by_id[2]["flag_reasons"] == ["OVERDUE"]


def test_list_flagged_manager_sees_only_team():
    _seed_flagged()
    resp = client.get("/opportunities/flagged", headers=MANAGER())
    assert resp.status_code == 200
    data = resp.json()
    assert {o["id"] for o in data["opportunities"]} == {1, 2}
    assert data["total"] == 2


def test_list_flagged_user_forbidden_and_unauthenticated():
    assert client.get("/opportunities/flagged", headers=USER()).status_code == 403
    assert client.get("/opportunities/flagged").status_code in (401, 403)


def test_list_flagged_manager_cannot_use_all_scope():
    assert client.get("/opportunities/flagged?scope=ALL", headers=MANAGER()).status_code == 403


def test_list_flagged_filter_by_reason():
    _seed_flagged()
    resp = client.get("/opportunities/flagged?reason=overdue", headers=ADMIN())
    assert resp.status_code == 200
    assert [o["id"] for o in resp.json()["opportunities"]] == [2]
    assert client.get("/opportunities/flagged?reason=bad", headers=ADMIN()).status_code == 400


def test_list_flagged_refresh_evaluates_now():
    get_opp(2)["expected_close_date"] = "2020-01-01"
    resp = client.get("/opportunities/flagged?refresh=true", headers=ADMIN())
    assert resp.status_code == 200
    assert 2 in {o["id"] for o in resp.json()["opportunities"]}
    # Không refresh và chưa quét thì không có cờ
    get_opp(2).pop("is_flagged", None)
    resp = client.get("/opportunities/flagged", headers=ADMIN())
    assert 2 not in {o["id"] for o in resp.json()["opportunities"]}


def test_flagged_route_not_shadowed_by_opportunity_id_route():
    resp = client.get("/opportunities/flagged", headers=ADMIN())
    assert resp.status_code == 200
    assert "opportunities" in resp.json()


def test_opportunity_detail_exposes_flags():
    get_opp(2)["expected_close_date"] = "2026-10-01"
    svc.run_daily_scan(TODAY)
    resp = client.get("/opportunities/2", headers=MANAGER())
    assert resp.status_code == 200
    assert resp.json()["is_overdue"] is True
    assert resp.json()["is_flagged"] is True
